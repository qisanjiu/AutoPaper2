"""Project entry manifest helpers.

This module normalizes the flexible project entrance inputs into a single
`state/research_brief.yaml` file that downstream stages can read.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

import yaml


ENTRY_BRIEF_FILENAME = "research_brief.yaml"


_ROLE_STAGE_MAP_PAPER: dict[str, list[str]] = {
    "foundation": [
        "M1S01",
        "M1S02",
        "M1S03",
        "M1S04",
        "M1S05",
        "M2S01",
        "M2S02",
        "M2S03",
        "M2S04",
        "M2S05",
        "M5S01",
        "M5S02",
        "M5S03",
        "M5S04",
        "M5S05",
    ],
    "reference": [
        "M1S01",
        "M1S02",
        "M1S03",
        "M2S01",
        "M2S02",
        "M2S03",
        "M5S01",
        "M5S03",
        "M5S04",
    ],
}

_ROLE_STAGE_MAP_CODE: dict[str, list[str]] = {
    "foundation": [
        "M2S02",
        "M2S03",
        "M2S05",
        "M3S01",
        "M3S02",
        "M5S01",
        "M5S04",
    ],
    "reference": [
        "M2S02",
        "M3S01",
        "M3S02",
        "M5S03",
        "M5S04",
    ],
}


@dataclass
class ProjectEntryAnchor:
    id: str
    role: str
    kind: str
    input_type: str
    raw_value: str
    title_hint: str = ""
    url: str = ""
    source_path: str = ""
    local_asset: str = ""
    status: str = "pending"
    notes: str = ""
    source: str = "cli"
    recommended_stages: list[str] = field(default_factory=list)
    canonical_value: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_input_manifest(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    manifest_path = Path(path).expanduser()
    if not manifest_path.exists():
        raise FileNotFoundError(f"Input manifest not found: {manifest_path}")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def normalize_keywords(values: Iterable[str] | str | None) -> list[str]:
    keywords: list[str] = []
    if not values:
        return keywords
    raw_values: Iterable[str]
    if isinstance(values, str):
        raw_values = [values]
    else:
        raw_values = values
    for value in raw_values:
        if not value:
            continue
        for piece in re.split(r"[,;|\n]+", str(value)):
            item = piece.strip()
            if item and item not in keywords:
                keywords.append(item)
    return keywords


def parse_anchor_input(raw: str, default_role: str = "reference") -> tuple[str, str]:
    value = (raw or "").strip()
    if not value:
        return default_role, value
    if ":" in value:
        prefix, remainder = value.split(":", 1)
        prefix = prefix.strip().lower()
        if prefix in {"foundation", "reference", "both"}:
            role = prefix
            value = remainder.strip()
        elif prefix in {"base", "extend", "extended"}:
            role = "foundation"
            value = remainder.strip()
        elif prefix in {"compare", "related"}:
            role = "reference"
            value = remainder.strip()
        elif prefix in {"github", "code", "repo", "url", "pdf", "path", "file", "arxiv", "doi", "title", "paper"}:
            role = default_role
            value = remainder.strip()
        else:
            role = default_role
    else:
        role = default_role
    return role, value


def infer_input_type(value: str) -> str:
    text = value.strip()
    lowered = text.lower()
    if lowered.startswith("doi:") or "doi.org/" in lowered or re.fullmatch(r"10\.\d{4,9}/\S+", text, flags=re.IGNORECASE):
        return "doi"
    if lowered.startswith("arxiv:") or "arxiv.org/" in lowered or re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", text):
        return "arxiv"
    if lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("www."):
        if "github.com" in lowered:
            return "github"
        return "url"
    path = Path(text).expanduser()
    if path.suffix.lower() == ".pdf" or path.exists():
        return "pdf" if path.suffix.lower() == ".pdf" else "path"
    return "title"


def infer_kind(input_type: str) -> str:
    if input_type in {"github"}:
        return "code"
    return "paper"


def _canonical_roles(role: str, kind: str) -> list[str]:
    role_text = (role or "").strip().lower()
    if role_text in {"both", "dual"}:
        return ["foundation", "reference"]
    if role_text in {"foundation", "base", "extend", "extended"}:
        return ["foundation"]
    if role_text in {"reference", "ref", "compare", "related"}:
        return ["reference"]
    if kind == "code":
        return ["reference"]
    return ["reference"]


def _stage_recommendations(role: str, kind: str) -> list[str]:
    stages: list[str] = []
    role_keys = _canonical_roles(role, kind)
    stage_map = _ROLE_STAGE_MAP_CODE if kind == "code" else _ROLE_STAGE_MAP_PAPER
    for key in role_keys:
        for stage in stage_map.get(key, []):
            if stage not in stages:
                stages.append(stage)
    return stages


def _copy_local_pdf(raw_value: str, project_root: Path, anchor_id: str) -> tuple[str, str]:
    source_path = Path(raw_value).expanduser()
    if not source_path.exists() or not source_path.is_file():
        return str(source_path), ""

    inputs_dir = project_root / "artifacts" / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", source_path.stem).strip("._-") or "anchor"
    target = inputs_dir / f"{anchor_id}_{safe_stem}{source_path.suffix.lower()}"
    suffix_index = 2
    while target.exists():
        target = inputs_dir / f"{anchor_id}_{safe_stem}_{suffix_index}{source_path.suffix.lower()}"
        suffix_index += 1
    shutil.copy2(source_path, target)
    return str(source_path), str(target.relative_to(project_root))


def _anchor_from_value(
    raw_value: str,
    *,
    role: str,
    source: str,
    project_root: Path,
    anchor_index: int,
    notes: str = "",
) -> ProjectEntryAnchor:
    cleaned = (raw_value or "").strip()
    input_type = infer_input_type(cleaned)
    kind = infer_kind(input_type)
    if cleaned.lower().startswith("file://"):
        cleaned = cleaned[7:]
        input_type = infer_input_type(cleaned)
        kind = infer_kind(input_type)

    anchor_id = f"anchor_{anchor_index:02d}"
    source_path = ""
    local_asset = ""
    status = "pending"
    title_hint = cleaned if input_type in {"title", "path"} else ""
    url = cleaned if input_type in {"url", "github", "arxiv", "doi"} else ""

    if input_type in {"pdf", "path"}:
        source_path, local_asset = _copy_local_pdf(cleaned, project_root, anchor_id)
        status = "copied" if local_asset else "missing_local_file"
    elif input_type in {"github", "url", "arxiv", "doi"}:
        status = "external_reference"
    elif input_type == "title":
        status = "needs_search"

    canonical_value = cleaned
    anchor = ProjectEntryAnchor(
        id=anchor_id,
        role=role,
        kind=kind,
        input_type=input_type,
        raw_value=raw_value,
        title_hint=title_hint,
        url=url,
        source_path=source_path,
        local_asset=local_asset,
        status=status,
        notes=notes,
        source=source,
        recommended_stages=_stage_recommendations(role, kind),
        canonical_value=canonical_value,
    )
    return anchor


def _load_anchor_records(raw_value: Any, default_role: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if raw_value is None:
        return records
    if isinstance(raw_value, str):
        records.append({"role": default_role, "value": raw_value})
        return records
    if isinstance(raw_value, dict):
        records.append(raw_value)
        return records
    if isinstance(raw_value, list):
        for item in raw_value:
            records.extend(_load_anchor_records(item, default_role))
        return records
    records.append({"role": default_role, "value": str(raw_value)})
    return records


def _load_manifest_anchors(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for key, default_role in (
        ("foundation_papers", "foundation"),
        ("foundations", "foundation"),
        ("base_papers", "foundation"),
        ("reference_papers", "reference"),
        ("references", "reference"),
        ("anchors", "reference"),
    ):
        for item in _load_anchor_records(manifest.get(key), default_role):
            item = dict(item)
            item.setdefault("role", default_role)
            anchors.append(item)
    return anchors


def build_project_entry(
    *,
    project_root: Path,
    topic: str,
    display_name: str,
    keywords: Iterable[str] | None = None,
    reference_inputs: Iterable[str] | None = None,
    foundation_inputs: Iterable[str] | None = None,
    input_manifest: str | Path | None = None,
    notes: str = "",
) -> dict[str, Any]:
    manifest = load_input_manifest(input_manifest)
    merged_keywords = normalize_keywords(keywords)
    merged_keywords.extend(normalize_keywords(manifest.get("keywords")))
    merged_keywords = normalize_keywords(merged_keywords)

    manifest_notes = str(manifest.get("notes", "")).strip()
    notes = notes.strip()
    if manifest_notes:
        notes = f"{notes}\n{manifest_notes}".strip() if notes else manifest_notes

    anchor_records: list[dict[str, Any]] = []
    anchor_records.extend(_load_manifest_anchors(manifest))
    if reference_inputs:
        for value in reference_inputs:
            anchor_records.append({"role": "reference", "value": value, "source": "cli"})
    if foundation_inputs:
        for value in foundation_inputs:
            anchor_records.append({"role": "foundation", "value": value, "source": "cli"})

    anchors: list[ProjectEntryAnchor] = []
    for index, record in enumerate(anchor_records, start=1):
        raw_value = str(record.get("value", "")).strip()
        if not raw_value:
            continue
        role, normalized_value = parse_anchor_input(raw_value, record.get("role", "reference"))
        anchor = _anchor_from_value(
            normalized_value,
            role=role,
            source=str(record.get("source", "manifest")),
            project_root=project_root,
            anchor_index=len(anchors) + 1,
            notes=str(record.get("notes", "")).strip(),
        )
        anchors.append(anchor)

    # Merge duplicate anchors by canonical value. If the same paper is both a
    # foundation and a key reference, keep a single anchor with role=both.
    deduped: dict[str, ProjectEntryAnchor] = {}
    for anchor in anchors:
        key = anchor.canonical_value.lower()
        if key not in deduped:
            deduped[key] = anchor
            continue
        existing = deduped[key]
        merged_roles = set(_canonical_roles(existing.role, existing.kind))
        merged_roles.update(_canonical_roles(anchor.role, anchor.kind))
        if {"foundation", "reference"}.issubset(merged_roles):
            existing.role = "both"
        elif "foundation" in merged_roles:
            existing.role = "foundation"
        else:
            existing.role = "reference"
        if not existing.title_hint and anchor.title_hint:
            existing.title_hint = anchor.title_hint
        if not existing.url and anchor.url:
            existing.url = anchor.url
        if not existing.source_path and anchor.source_path:
            existing.source_path = anchor.source_path
        if not existing.local_asset and anchor.local_asset:
            existing.local_asset = anchor.local_asset
        if existing.status == "pending" and anchor.status != "pending":
            existing.status = anchor.status
        for stage in _stage_recommendations(existing.role, existing.kind):
            if stage not in existing.recommended_stages:
                existing.recommended_stages.append(stage)
        for stage in anchor.recommended_stages:
            if stage not in existing.recommended_stages:
                existing.recommended_stages.append(stage)

    final_anchors = list(deduped.values())

    stage_guidance: dict[str, dict[str, Any]] = {}
    for anchor in final_anchors:
        for stage in anchor.recommended_stages:
            entry = stage_guidance.setdefault(
                stage,
                {
                    "anchor_ids": [],
                    "guidance": [],
                },
            )
            if anchor.id not in entry["anchor_ids"]:
                entry["anchor_ids"].append(anchor.id)
            guidance = _stage_guidance_text(stage, anchor)
            if guidance and guidance not in entry["guidance"]:
                entry["guidance"].append(guidance)

    entry_mode = "topic_only"
    if final_anchors:
        has_paper_anchor = any(a.kind == "paper" for a in final_anchors)
        has_code_anchor = any(a.kind == "code" for a in final_anchors)
        if has_paper_anchor and has_code_anchor:
            entry_mode = "topic_plus_paper_and_code"
        elif has_paper_anchor:
            entry_mode = "topic_plus_paper"
        elif has_code_anchor:
            entry_mode = "topic_plus_code"

    brief = {
        "version": 1,
        "project": {
            "topic": topic,
            "display_name": display_name,
            "keywords": merged_keywords,
            "notes": notes,
            "source_manifest": str(input_manifest) if input_manifest else "",
            "created_at": datetime.now().isoformat(),
            "entry_mode": entry_mode,
            "anchor_count": len(final_anchors),
            "paper_anchor_count": sum(1 for a in final_anchors if a.kind == "paper"),
            "code_anchor_count": sum(1 for a in final_anchors if a.kind == "code"),
        },
        "keywords": merged_keywords,
        "notes": notes,
        "anchors": [anchor.to_dict() for anchor in final_anchors],
        "stage_guidance": stage_guidance,
    }
    return brief


def _stage_guidance_text(stage: str, anchor: ProjectEntryAnchor) -> str:
    if anchor.kind == "code":
        if stage.startswith("M2"):
            return "Treat this code anchor as a baseline or implementation reference; verify compatibility before reuse."
        if stage.startswith("M3"):
            return "Use this code anchor to evaluate implementation constraints, dependency layout, and baseline reproducibility."
        if stage.startswith("M5"):
            return "Use this code anchor when writing implementation, experiment setup, or reproducibility notes."
        return "Use this code anchor as a technical reference only after the related paper lineage is clear."

    if "foundation" in _canonical_roles(anchor.role, anchor.kind):
        if stage == "M1S01":
            return "Use this paper as the lineage anchor when defining the topic boundary."
        if stage == "M1S02":
            return "Deep-read this paper and decide whether it is the true base work or just a close relative."
        if stage in {"M1S03", "M1S04", "M1S05"}:
            return "Use this paper to test whether the research question is a real extension of the base line."
        if stage.startswith("M2"):
            return "Use this paper as the closest baseline family when mapping the gap to a method."
        if stage.startswith("M3"):
            return "Use this paper to lock the inherited baseline, code lineage, and fairness constraints."
        if stage.startswith("M5"):
            return "Use this paper as the lineage anchor for comparisons and contribution wording."
        return "Use this paper as the primary lineage anchor when relevant."

    if stage == "M1S01":
        return "Use this paper to narrow the topic and vocabulary, but do not overfit the scope too early."
    if stage == "M1S02":
        return "Use this paper for close reading, citation tracing, and related-work positioning."
    if stage in {"M1S03", "M1S04", "M1S05"}:
        return "Use this paper as a comparison point when selecting the most defensible direction."
    if stage.startswith("M2"):
        return "Use this paper as a comparison point for mechanisms, not necessarily as the main baseline."
    if stage.startswith("M5"):
        return "Use this paper when composing related work and comparison language."
    return "Use this paper only when its evidence is directly relevant to the current stage."
