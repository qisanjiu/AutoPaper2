#!/usr/bin/env python3
"""Generate M5 architecture/mechanism figures or Draw.io diagram stubs."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shlex
import subprocess
import time
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib

import requests
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "image_generation.yaml"
LOCAL_CONFIG = ROOT / "config" / "image_generation.local.yaml"
STYLE_CONFIG = ROOT / "config" / "figure_style_profiles.yaml"
STYLE_LOCAL_CONFIG = ROOT / "config" / "figure_style_profiles.local.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "generated-images"
CODEX_ROOT = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_config() -> dict[str, Any]:
    config = _load_yaml(DEFAULT_CONFIG)
    local = _load_yaml(LOCAL_CONFIG)
    if local:
        config = _deep_merge(config, local)
    return config.get("figure_generation", config)


def _load_style_config() -> dict[str, Any]:
    config = _load_yaml(STYLE_CONFIG)
    local = _load_yaml(STYLE_LOCAL_CONFIG)
    if local:
        config = _deep_merge(config, local)
    return config.get("figure_styles", config)


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    return data if isinstance(data, dict) else {}


def _extract_markdown_section(text: str, headings: tuple[str, ...]) -> str:
    if not text.strip():
        return ""
    heading_re = re.compile(
        r"^(#{1,6})\s+(?:\d+(?:\.\d+)*[.)]?\s+)?(?:" + "|".join(re.escape(h) for h in headings) + r")\s*$",
        re.IGNORECASE,
    )
    capture = False
    start_level = 0
    buf: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not capture:
            match = heading_re.match(stripped)
            if match:
                capture = True
                start_level = len(match.group(1))
                buf.append(line)
            continue
        match = re.match(r"^(#{1,6})\s+", stripped)
        if match and len(match.group(1)) <= start_level:
            break
        buf.append(line)
    extracted = "\n".join(buf).strip()
    return extracted or text.strip()


def _load_style_profile_text(spec: str) -> tuple[str, str]:
    if not spec:
        return "", ""
    path = Path(spec).expanduser()
    if path.exists() and path.is_file():
        raw = path.read_text(encoding="utf-8")
        extracted = _extract_markdown_section(
            raw,
            ("Figure Style Profile", "Style & Layout Profile"),
        )
        return str(path), extracted
    return "inline", spec.strip()


def _normalize_style_value(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{k}={v}" for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return "; ".join(str(item) for item in value)
    return str(value)


def _select_style_preset(
    style_cfg: dict[str, Any],
    venue: str,
    explicit_preset: str = "",
) -> tuple[str, dict[str, Any]]:
    presets = style_cfg.get("presets", {}) or {}
    venue_map = style_cfg.get("venue_map", {}) or {}
    default_preset = style_cfg.get("default_preset", "journal_generic")

    chosen = (explicit_preset or "").strip()
    venue_key = (venue or "").strip().lower()
    if not chosen and venue_key:
        chosen = str(venue_map.get(venue_key, "")).strip()
    if not chosen and venue_key in presets:
        chosen = venue_key
    if not chosen:
        chosen = default_preset
    if chosen not in presets:
        chosen = default_preset if default_preset in presets else next(iter(presets), "")
    return chosen, presets.get(chosen, {})


def _compose_style_prompt(
    *,
    style_cfg: dict[str, Any],
    venue: str,
    explicit_preset: str = "",
    style_profile_spec: str = "",
) -> tuple[str, dict[str, Any]]:
    preset_name, preset = _select_style_preset(style_cfg, venue, explicit_preset)
    style_source, style_text = _load_style_profile_text(style_profile_spec)

    lines: list[str] = ["[Figure Style Profile]"]
    if venue:
        lines.append(f"Venue: {venue}")
    if preset_name:
        lines.append(f"Preset: {preset_name}")
    lines.append(
        "Content fidelity: use only components, labels, relationships, model names, "
        "datasets, and examples explicitly provided in the Task Prompt; do not invent "
        "extra submodules or technical terms."
    )
    for key in ("tone", "notes"):
        value = preset.get(key)
        if value:
            label = key.replace("_", " ").title()
            lines.append(f"{label}: {_normalize_style_value(value)}")
    palette = preset.get("palette")
    if palette:
        lines.append(f"Palette: {_normalize_style_value(palette)}")
    for key in ("layout", "typography", "richness", "avoid"):
        value = preset.get(key)
        if value:
            label = key.replace("_", " ").title()
            lines.append(f"{label}: {_normalize_style_value(value)}")
    if style_text:
        lines.append("Distilled style signals:")
        lines.append(style_text.strip())

    prompt = "\n".join(lines).strip()
    meta = {
        "venue": venue,
        "preset": preset_name,
        "style_profile_source": style_source,
        "style_profile_chars": len(style_text),
    }
    return prompt, meta


def _compose_final_prompt(
    prompt: str,
    *,
    venue: str,
    style_cfg: dict[str, Any],
    explicit_preset: str = "",
    style_profile_spec: str = "",
) -> tuple[str, dict[str, Any]]:
    style_prompt, meta = _compose_style_prompt(
        style_cfg=style_cfg,
        venue=venue,
        explicit_preset=explicit_preset,
        style_profile_spec=style_profile_spec,
    )
    if style_prompt:
        final_prompt = f"{style_prompt}\n\nTask Prompt:\n{prompt}"
    else:
        final_prompt = prompt
    meta["final_prompt_chars"] = len(final_prompt)
    return final_prompt, meta


def _join_api_root(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    if base_url.endswith("/v1"):
        return base_url
    return f"{base_url}/v1"


def _resolve_base_url(image_cfg: dict[str, Any]) -> str:
    env = os.getenv("OPENAI_BASE_URL")
    if env:
        return _join_api_root(env)

    configured = image_cfg.get("api_base_url")
    if configured:
        return _join_api_root(str(configured))

    config = _load_toml(CODEX_ROOT / "config.toml")
    provider_name = config.get("model_provider")
    providers = config.get("model_providers", {})
    if provider_name and provider_name in providers:
        base_url = providers[provider_name].get("base_url")
        if base_url:
            return _join_api_root(str(base_url))
    for provider in providers.values():
        if isinstance(provider, dict) and provider.get("base_url"):
            return _join_api_root(str(provider["base_url"]))

    raise SystemExit("Unable to resolve base URL. Set OPENAI_BASE_URL or configure api_base_url.")


def _resolve_api_key(image_cfg: dict[str, Any]) -> str:
    env = os.getenv("OPENAI_API_KEY")
    if env:
        return env

    env_name = str(image_cfg.get("api_key_env", "OPENAI_API_KEY"))
    env = os.getenv(env_name)
    if env:
        return env

    configured = str(image_cfg.get("api_key") or "").strip()
    if configured:
        return configured

    auth_path = CODEX_ROOT / "auth.json"
    if auth_path.exists():
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        key = auth.get("OPENAI_API_KEY") or auth.get("api_key")
        if key:
            return str(key)

    raise SystemExit("OPENAI_API_KEY not found in env, config, or ~/.codex/auth.json")


def _slugify(text: str, limit: int = 48) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:limit] or f"figure-{int(time.time())}"


def _ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_output_dir(cfg: dict[str, Any], backend_cfg: dict[str, Any] | None = None) -> Path:
    raw = (backend_cfg or {}).get("output_dir") or cfg.get("output_dir") or DEFAULT_OUTPUT_DIR
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _save_png_from_b64(b64_json: str, output: Path) -> Path:
    output.write_bytes(base64.b64decode(b64_json))
    return output


def _extract_image_asset(response: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(response, dict):
        return None

    top_level_keys = ("b64_json", "url", "base64", "b64", "image", "output")
    for key in top_level_keys:
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return {"type": key, "value": value}

    for container_key in ("data", "images", "output", "result"):
        container = response.get(container_key)
        if isinstance(container, dict):
            container = [container]
        if not isinstance(container, list):
            continue
        for item in container:
            if not isinstance(item, dict):
                continue
            for key in ("b64_json", "base64", "b64", "image", "url"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return {"type": key, "value": value}
    return None


def _save_image_from_response(response: dict[str, Any], output: Path) -> Path:
    asset = _extract_image_asset(response)
    if not asset:
        raise SystemExit(
            "Image generation response did not contain a recognizable image payload. "
            f"Top-level keys: {sorted(response.keys()) if isinstance(response, dict) else type(response)}"
        )

    if asset["type"] in {"b64_json", "base64", "b64"}:
        return _save_png_from_b64(asset["value"], output)
    if asset["type"] == "image":
        raw = asset["value"]
        try:
            return _save_png_from_b64(raw, output)
        except Exception:
            output.write_bytes(raw.encode("utf-8"))
            return output
    if asset["type"] == "url":
        img_resp = requests.get(asset["value"], timeout=180)
        img_resp.raise_for_status()
        output.write_bytes(img_resp.content)
        return output
    raise SystemExit(f"Unsupported image payload type: {asset['type']}")


def _image2_generate(prompt: str, args: argparse.Namespace, cfg: dict[str, Any]) -> Path:
    image_cfg = cfg.get("image2", {})
    base_url = _resolve_base_url(image_cfg)
    api_key = _resolve_api_key(image_cfg)
    style_cfg = _load_style_config()
    final_prompt, _style_meta = _compose_final_prompt(
        prompt,
        venue=args.venue,
        style_cfg=style_cfg,
        explicit_preset=args.style_preset,
        style_profile_spec=args.style_profile,
    )

    model = args.model or image_cfg.get("model", "gpt-image-2")
    size = args.size or image_cfg.get("size", "1024x1024")
    quality = args.quality or image_cfg.get("quality", "medium")
    output_dir = _ensure_output_dir(_resolve_output_dir(cfg, image_cfg))
    output_name = args.output or f"{_slugify(prompt)}-{int(time.time())}.png"
    output = Path(output_name)
    if not output.is_absolute():
        output = output_dir / output
    output.parent.mkdir(parents=True, exist_ok=True)

    url = base_url.rstrip("/") + "/images/generations"
    payload: dict[str, Any] = {
        "model": model,
        "prompt": final_prompt,
        "size": size,
        "quality": quality,
        "n": 1,
    }
    if args.background:
        payload["background"] = args.background

    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.post(url, json=payload, headers=headers, timeout=180)
    response.raise_for_status()
    data = response.json()
    return _save_image_from_response(data, output)


def _image_edit(prompt: str, args: argparse.Namespace, cfg: dict[str, Any]) -> Path:
    image_cfg = cfg.get("image2", {})
    base_url = _resolve_base_url(image_cfg)
    api_key = _resolve_api_key(image_cfg)
    style_cfg = _load_style_config()
    final_prompt, _style_meta = _compose_final_prompt(
        prompt,
        venue=args.venue,
        style_cfg=style_cfg,
        explicit_preset=args.style_preset,
        style_profile_spec=args.style_profile,
    )

    model = args.model or image_cfg.get("model", "gpt-image-2")
    size = args.size or image_cfg.get("size", "1024x1024")
    quality = args.quality or image_cfg.get("quality", "medium")
    output_dir = _ensure_output_dir(_resolve_output_dir(cfg, image_cfg))
    output_name = args.output or f"{_slugify(prompt)}-edit-{int(time.time())}.png"
    output = Path(output_name)
    if not output.is_absolute():
        output = output_dir / output
    output.parent.mkdir(parents=True, exist_ok=True)

    url = base_url.rstrip("/") + "/images/edits"
    headers = {"Authorization": f"Bearer {api_key}"}
    files: dict[str, tuple[str, Any, str]] = {}
    with open(args.image, "rb") as image_f:
        files["image"] = (Path(args.image).name, image_f, "image/png")
        if args.mask:
            with open(args.mask, "rb") as mask_f:
                files["mask"] = (Path(args.mask).name, mask_f, "image/png")
                response = requests.post(
                    url,
                    files=files,
                    data={"model": model, "prompt": final_prompt, "size": size, "quality": quality, "n": 1},
                    headers=headers,
                    timeout=180,
                )
        else:
            response = requests.post(
                url,
                files=files,
                data={"model": model, "prompt": final_prompt, "size": size, "quality": quality, "n": 1},
                headers=headers,
                timeout=180,
            )
    response.raise_for_status()
    data = response.json()
    return _save_image_from_response(data, output)


def _resolve_drawio_output(prompt: str, args: argparse.Namespace, cfg: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    drawio_cfg = cfg.get("drawio", {})
    output_dir = _ensure_output_dir(_resolve_output_dir(cfg, drawio_cfg))
    output_name = args.output or f"{_slugify(prompt)}-{int(time.time())}{drawio_cfg.get('editable_ext', '.drawio')}"
    output = Path(output_name)
    if not output.is_absolute():
        output = output_dir / output
    output.parent.mkdir(parents=True, exist_ok=True)
    return output, drawio_cfg


def _run_drawio_mcp_command(prompt: str, output: Path, drawio_cfg: dict[str, Any]) -> Path | None:
    command_template = os.getenv("DRAWIO_MCP_COMMAND") or str(drawio_cfg.get("mcp_command") or "").strip()
    if not command_template:
        return None

    output_dir = output.parent
    token_map = {
        "prompt": shlex.quote(prompt),
        "output": shlex.quote(str(output)),
        "output_dir": shlex.quote(str(output_dir)),
        "mcp_server": shlex.quote(str(drawio_cfg.get("mcp_server", "drawio"))),
    }
    formatted = command_template.format(
        **token_map,
    )
    completed = subprocess.run(
        shlex.split(formatted),
        check=True,
        text=True,
        capture_output=True,
        timeout=int(drawio_cfg.get("timeout_seconds", 300)),
    )
    stdout = completed.stdout.strip()
    if output.exists():
        return output
    if stdout:
        candidate = Path(stdout.splitlines()[-1].strip())
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.exists():
            return candidate
    raise SystemExit(
        "Draw.io MCP command completed but did not produce the expected output file: "
        f"{output}"
    )


def _drawio_stub(prompt: str, output: Path) -> Path:
    safe_prompt = xml_escape(prompt)
    xml = f"""<mxfile host="app.diagrams.net" version="24.7.17">
  <diagram id="m5-diagram" name="Page-1">
    <mxGraphModel dx="1000" dy="700" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="850" pageHeight="1100" math="0" shadow="0">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="2" value="{safe_prompt}" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;fontSize=14;" vertex="1" parent="1">
          <mxGeometry x="80" y="80" width="620" height="260" as="geometry"/>
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""
    output.write_text(xml, encoding="utf-8")
    return output


def _drawio_generate(prompt: str, args: argparse.Namespace, cfg: dict[str, Any]) -> Path:
    output, drawio_cfg = _resolve_drawio_output(prompt, args, cfg)
    style_cfg = _load_style_config()
    final_prompt, _style_meta = _compose_final_prompt(
        prompt,
        venue=args.venue,
        style_cfg=style_cfg,
        explicit_preset=args.style_preset,
        style_profile_spec=args.style_profile,
    )
    mcp_output = _run_drawio_mcp_command(final_prompt, output, drawio_cfg)
    if mcp_output is not None:
        return mcp_output
    return _drawio_stub(final_prompt, output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate M5 figures/diagrams")
    parser.add_argument("prompt", help="Figure prompt")
    parser.add_argument("--backend", choices=["auto", "image2", "drawio"], default="auto")
    parser.add_argument("--model", default="")
    parser.add_argument("--size", default="")
    parser.add_argument("--quality", default="")
    parser.add_argument("--background", default="")
    parser.add_argument("--image", default="")
    parser.add_argument("--mask", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--venue", default="", help="Venue identifier used to select a figure style preset")
    parser.add_argument("--style-preset", default="", help="Explicit figure style preset override")
    parser.add_argument(
        "--style-profile",
        default="",
        help="Path to or inline text of a figure style profile to distill into the prompt",
    )
    args = parser.parse_args()

    cfg = _load_config()
    backend = args.backend if args.backend != "auto" else cfg.get("default_backend", "image2")

    if backend == "drawio":
        if args.image or args.mask:
            raise SystemExit("drawio backend does not support --image or --mask")
        out = _drawio_generate(args.prompt, args, cfg)
    elif backend == "image2":
        if args.image:
            out = _image_edit(args.prompt, args, cfg)
        else:
            out = _image2_generate(args.prompt, args, cfg)
    else:
        raise SystemExit(f"Unsupported backend: {backend}")

    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
