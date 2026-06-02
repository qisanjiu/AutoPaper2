#!/usr/bin/env python3
"""Inspect an AutoPaper2 dispatch packet for context-size risks.

The checker is intentionally cheap: it parses packet metadata and uses file
stats only. It does not read large input documents or recurse into run
directories.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_WARN_CHARS = 200_000
DEFAULT_FAIL_CHARS = 800_000


def _strip_ticks(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        return value[1:-1].strip()
    return value


def _load_json_packet(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_markdown_packet(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    packet: dict[str, Any] = {"packet_path": str(path), "input_docs": [], "context_policy": {}}
    in_inputs = False
    in_policy = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            in_inputs = line == "## Input Paths"
            in_policy = line == "## Context Policy"
            continue
        if not line.startswith("- "):
            continue

        body = line[2:].strip()
        if in_policy:
            match = re.match(r"([A-Za-z0-9_]+):\s*(.*)", body)
            if match:
                key, value = match.groups()
                if value == "True":
                    packet["context_policy"][key] = True
                elif value == "False":
                    packet["context_policy"][key] = False
                else:
                    packet["context_policy"][key] = _strip_ticks(value)
                continue

        if in_inputs:
            if body.startswith("`") and body.endswith("`"):
                packet["input_docs"].append(_strip_ticks(body))
                continue
            if body.startswith("subject_output:"):
                packet["subject_output"] = _strip_ticks(body.split(":", 1)[1])
                continue
            if body.startswith("md_protocol:"):
                packet["md_protocol"] = _strip_ticks(body.split(":", 1)[1])
                continue

        match = re.match(r"([A-Za-z0-9_]+):\s*(.*)", body)
        if match:
            key, value = match.groups()
            packet[key] = _strip_ticks(value)
    return packet


def load_packet(path: str | Path) -> dict[str, Any]:
    packet_path = Path(path)
    if packet_path.suffix.lower() == ".json":
        packet = _load_json_packet(packet_path)
    else:
        packet = _load_markdown_packet(packet_path)
    packet.setdefault("packet_path", str(packet_path))
    packet["_runtime_packet_path"] = str(packet_path)
    packet.setdefault("input_docs", [])
    return packet


def _looks_like_framework_root(path: Path) -> bool:
    return (path / "spiral").is_dir() and (path / "docs" / "AGENTS").is_dir()


def _framework_root_from_runtime(packet_path: Path | None = None, project_root: Path | None = None) -> Path:
    env_root = os.environ.get("SPIRAL_FRAMEWORK_ROOT")
    if env_root and _looks_like_framework_root(Path(env_root)):
        return Path(env_root).resolve()
    candidates: list[Path] = [Path.cwd(), Path(__file__).parent.parent]
    if packet_path:
        candidates.extend(packet_path.resolve().parents)
    if project_root:
        candidates.extend(project_root.resolve().parents)
    for candidate in candidates:
        if _looks_like_framework_root(candidate):
            return candidate.resolve()
    return Path(__file__).parent.parent.resolve()


def _project_root_from_packet(packet: dict[str, Any], packet_path: Path | None = None) -> Path | None:
    raw_root = str(packet.get("project_root", "") or "").strip()
    if raw_root and not raw_root.startswith(("project:", "framework:")):
        path = Path(raw_root)
        if path.is_absolute():
            return path.resolve()
        candidate = Path.cwd() / path
        if candidate.exists():
            return candidate.resolve()

    if packet_path:
        resolved = packet_path.resolve()
        parents = [resolved.parent, *resolved.parents]
        for parent in parents:
            if parent.name == "state":
                return parent.parent.resolve()
            if parent.name == "dispatch" and parent.parent.name == "state":
                return parent.parent.parent.resolve()
    return None


def resolve_packet_path(
    value: str | Path,
    packet: dict[str, Any] | None = None,
    *,
    packet_path: str | Path | None = None,
    project_root: str | Path | None = None,
    framework_root: str | Path | None = None,
) -> Path:
    """Resolve portable dispatch path refs for the current runtime."""
    text = _strip_ticks(str(value))
    packet = packet or {}
    runtime_packet_path = str(packet_path or packet.get("_runtime_packet_path") or packet.get("packet_path") or "")
    packet_file = None if runtime_packet_path.startswith(("project:", "framework:")) or not runtime_packet_path else Path(runtime_packet_path)
    project = Path(project_root).resolve() if project_root else _project_root_from_packet(packet, packet_file)
    framework = Path(framework_root).resolve() if framework_root else _framework_root_from_runtime(packet_file, project)

    if text.startswith("project:"):
        rel = text.split(":", 1)[1].strip()
        if rel in {"", "."}:
            return project or Path.cwd()
        return (project or Path.cwd()) / rel
    if text.startswith("framework:"):
        rel = text.split(":", 1)[1].strip()
        if rel in {"", "."}:
            return framework
        return framework / rel

    path = Path(text)
    if path.is_absolute():
        return path
    if project:
        project_path = project / path
        if project_path.exists():
            return project_path
    framework_path = framework / path
    if framework_path.exists():
        return framework_path
    if project:
        return project / path
    return Path.cwd() / path


def _path_info(value: str, packet: dict[str, Any], warn_chars: int = DEFAULT_WARN_CHARS) -> dict[str, Any]:
    path = resolve_packet_path(value, packet)
    info: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "kind": "missing",
        "bytes": 0,
        "context_risk": "missing",
    }
    if not path.exists():
        return info
    if path.is_dir():
        info.update({"kind": "directory", "context_risk": "index_before_read"})
        return info
    try:
        size = path.stat().st_size
    except OSError:
        info.update({"kind": "unreadable", "context_risk": "stat_failed"})
        return info
    suffix = path.suffix.lower()
    risk = "normal"
    if suffix in {".pdf", ".png", ".jpg", ".jpeg", ".pt", ".pth", ".ckpt", ".zip", ".tar", ".gz"}:
        risk = "binary_or_large_artifact"
    elif size > warn_chars:
        risk = "large_text"
    info.update({"kind": "file", "bytes": size, "context_risk": risk})
    return info


def build_report(packet: dict[str, Any], warn_chars: int = DEFAULT_WARN_CHARS, fail_chars: int = DEFAULT_FAIL_CHARS) -> dict[str, Any]:
    paths: list[str] = []
    for key in ("agent_md", "md_protocol", "subject_output", "output_path", "role_spec"):
        value = str(packet.get(key, "") or "")
        if value:
            paths.append(value)
    shared_contracts = packet.get("shared_contracts", [])
    if isinstance(shared_contracts, str):
        shared_contracts = [item.strip().strip("`") for item in shared_contracts.split(",")]
    paths.extend(str(p) for p in shared_contracts if str(p))
    paths.extend(str(p) for p in packet.get("input_docs", []) if str(p))

    seen: set[str] = set()
    infos: list[dict[str, Any]] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        infos.append(_path_info(path, packet, warn_chars=warn_chars))

    packet_path = Path(str(packet.get("packet_path", "")))
    packet_bytes = packet_path.stat().st_size if packet_path.exists() and packet_path.is_file() else 0
    direct_read_chars = packet_bytes + sum(int(info["bytes"]) for info in infos if info["kind"] == "file")
    warnings: list[str] = []
    if packet.get("context_policy", {}).get("no_parent_context") is not True and packet.get("no_parent_context") != "True":
        warnings.append("packet does not explicitly set context_policy.no_parent_context=true")
    for info in infos:
        if info["kind"] == "directory":
            warnings.append(f"directory input requires indexing before reading: {info['path']}")
        elif info["context_risk"] in {"binary_or_large_artifact", "large_text"}:
            warnings.append(f"{info['context_risk']}: {info['path']} ({info['bytes']} bytes)")

    status = "OK"
    if direct_read_chars >= fail_chars:
        status = "FAIL"
    elif direct_read_chars >= warn_chars or warnings:
        status = "WARN"

    return {
        "status": status,
        "packet_path": str(packet.get("packet_path", "")),
        "packet_bytes": packet_bytes,
        "estimated_direct_read_chars": direct_read_chars,
        "estimated_tokens_if_read_all": max(1, direct_read_chars // 4),
        "path_count": len(infos),
        "warnings": warnings,
        "largest_paths": sorted(infos, key=lambda item: int(item["bytes"]), reverse=True)[:10],
    }


def render_report(report: dict[str, Any]) -> str:
    lines = [
        "Context Budget Report",
        f"- status: {report['status']}",
        f"- packet: {report['packet_path']}",
        f"- packet_bytes: {report['packet_bytes']}",
        f"- estimated_direct_read_chars: {report['estimated_direct_read_chars']}",
        f"- estimated_tokens_if_read_all: {report['estimated_tokens_if_read_all']}",
        f"- path_count: {report['path_count']}",
    ]
    warnings = report.get("warnings", [])
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in warnings:
            lines.append(f"- {warning}")
    lines.append("")
    lines.append("Largest paths:")
    for info in report.get("largest_paths", []):
        lines.append(f"- {info['bytes']} bytes | {info['kind']} | {info['context_risk']} | {info['path']}")
    lines.append("")
    lines.append("Delegation rule: pass only the compact launch prompt/packet path to the subagent.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, help="Dispatch packet path (.md or .json)")
    parser.add_argument("--warn-chars", type=int, default=DEFAULT_WARN_CHARS)
    parser.add_argument("--fail-chars", type=int, default=DEFAULT_FAIL_CHARS)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    packet = load_packet(args.packet)
    report = build_report(packet, warn_chars=args.warn_chars, fail_chars=args.fail_chars)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_report(report))
    return 2 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
