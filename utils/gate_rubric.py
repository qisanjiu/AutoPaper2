"""Gate rubric validation for aggregate reviews."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from utils.file_guard import find_alternate_outputs
from utils.review_integrity import find_pass_integrity_issues

RUBRIC_CONFIG_PATH = Path(__file__).parent.parent / "config" / "gate_rubrics.yaml"

_VERDICT_RE = re.compile(r"(?im)^\s*(?:\*\*)?verdict(?:\*\*)?\s*[:：]?\s*(PASS|REVISE|REWORK|BACKTRACK|FIX|HALT)\s*$")
_DECLARED_VERDICT_RE = re.compile(r"(?im)^\s*(?:\*\*)?verdict(?:\*\*)?\s*[:：]?\s*([A-Z][A-Z0-9_ -]*)\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
_GATE_CRITICS: dict[str, list[str]] = {
    "G1": ["logic", "coverage"],
    "G2": ["logic", "method", "novelty"],
    "G3": ["method", "evidence"],
    "G4": ["logic", "evidence", "novelty"],
    "G5": ["logic", "writing", "evidence", "novelty", "ethics"],
    "G6": ["logic", "evidence", "writing", "resolution"],
}
_REPAIR_FIELDS: tuple[str, ...] = (
    "target_stage",
    "blocking_reason",
    "required_fix",
    "success_criteria",
    "rebuild_mode",
    "rerun_scope",
)
_REPAIR_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    field: re.compile(
        rf"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?`?{re.escape(field)}`?(?:\*\*)?\s*[:：]\s*(.+?)\s*$"
    )
    for field in _REPAIR_FIELDS
}


def load_gate_rubrics(path: str | Path | None = None) -> dict[str, Any]:
    """Load the configured gate rubrics."""
    cfg_path = Path(path) if path else RUBRIC_CONFIG_PATH
    with cfg_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def get_gate_rubric(gate_id: str, path: str | Path | None = None) -> dict[str, Any]:
    """Return one gate rubric definition, or an empty dict if missing."""
    data = load_gate_rubrics(path)
    gates = data.get("gates", {}) if isinstance(data, dict) else {}
    rubric = gates.get(gate_id, {}) if isinstance(gates, dict) else {}
    return rubric if isinstance(rubric, dict) else {}


def required_rubric_ids(gate_id: str, path: str | Path | None = None) -> list[str]:
    """Return configured rubric item IDs for a gate."""
    rubric = get_gate_rubric(gate_id, path)
    items = rubric.get("items", [])
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items:
        if isinstance(item, dict) and item.get("id"):
            out.append(str(item["id"]))
    return out


def render_gate_rubric_block(gate_id: str, path: str | Path | None = None) -> str:
    """Render a compact rubric block for dispatch prompts."""
    rubric = get_gate_rubric(gate_id, path)
    if not rubric:
        return ""
    lines = [
        f"Gate rubric: {gate_id} - {rubric.get('title', '').strip()}",
        "The aggregate review must include a `Rubric Results` table with one row per item:",
        "`| Rubric ID | Verdict | Score | Evidence paths | Notes |`",
    ]
    for item in rubric.get("items", []):
        if not isinstance(item, dict):
            continue
        lines.append(f"- {item.get('id', '')}: {item.get('criterion', '')}")
        examples = item.get("evidence_examples", [])
        if examples:
            lines.append(f"  evidence examples: {', '.join(str(p) for p in examples)}")
    lines.append("PASS requires every row to be PASS, score 2/2, and cite at least one existing evidence path.")
    return "\n".join(lines)


def _extract_verdict(text: str) -> str | None:
    match = _VERDICT_RE.search(text)
    if match:
        return match.group(1).upper()
    return None


def _extract_declared_verdict(text: str) -> str | None:
    match = _DECLARED_VERDICT_RE.search(text)
    if match:
        return match.group(1).strip().upper()
    return None


def _missing_repair_fields(text: str) -> list[str]:
    missing: list[str] = []
    for field, pattern in _REPAIR_FIELD_PATTERNS.items():
        match = pattern.search(text)
        if not match or not match.group(1).strip(" `*"):
            missing.append(field)
    return missing


def gate_critic_review_paths(project_root: str | Path, gate_id: str) -> dict[str, Path]:
    """Return the canonical individual critic-review paths for one gate."""
    root = Path(project_root)
    return {
        critic: root / "knowledge" / "reviews" / f"{gate_id}_{critic}_review.md"
        for critic in _GATE_CRITICS.get(gate_id, [])
    }


def validate_gate_critic_reviews(
    project_root: str | Path,
    gate_id: str,
) -> tuple[bool, list[str]]:
    """Validate individual gate critic reviews before aggregate advancement.

    The aggregate file may summarize critic results, but it must not override
    them.  Any missing, malformed, unsupported, or non-PASS critic verdict
    blocks advancement and requires normal backtrack/re-review handling.
    """
    root = Path(project_root)
    messages: list[str] = []
    ok = True
    paths = gate_critic_review_paths(root, gate_id)
    if not paths:
        return True, [f"[WARN] Gate {gate_id}: no configured critic reviews"]

    for critic, review_path in paths.items():
        alternates = find_alternate_outputs(review_path.parent, review_path.name)
        if alternates:
            messages.append(
                f"[FAIL] Gate {gate_id}: alternate critic review file(s) found for {review_path.name}: "
                + ", ".join(path.name for path in alternates)
                + "; update the canonical review in place instead of creating revised copies."
            )
            ok = False
        if not review_path.exists():
            messages.append(f"[FAIL] Gate {gate_id}: required critic review missing: {review_path.name}")
            ok = False
            continue

        try:
            text = review_path.read_text(encoding="utf-8")
        except Exception as exc:
            messages.append(f"[FAIL] Gate {gate_id}: critic review {review_path.name} unreadable: {exc}")
            ok = False
            continue

        verdict = _extract_verdict(text)
        if verdict is None:
            declared = _extract_declared_verdict(text)
            if declared:
                messages.append(
                    f"[FAIL] Gate {gate_id}: critic review {review_path.name} uses unsupported verdict={declared}; "
                    "allowed verdicts are PASS, REVISE, REWORK, BACKTRACK, FIX, HALT."
                )
            else:
                messages.append(f"[FAIL] Gate {gate_id}: critic review {review_path.name} missing explicit verdict")
            ok = False
            continue

        if verdict != "PASS":
            messages.append(
                f"[FAIL] Gate {gate_id}: critic review {review_path.name} verdict={verdict}; "
                "aggregate PASS cannot override individual critic verdicts."
            )
            missing = _missing_repair_fields(text)
            if missing:
                messages.append(
                    f"[FAIL] Gate {gate_id}: critic review {review_path.name} missing repair advice fields: "
                    + ", ".join(missing)
                )
            ok = False
        else:
            integrity_issues = find_pass_integrity_issues(text)
            if integrity_issues:
                messages.append(
                    f"[FAIL] Gate {gate_id}: critic review {review_path.name} has PASS verdict but contains "
                    "blocking/ambiguous language: " + " | ".join(integrity_issues[:3])
                )
                ok = False
            else:
                messages.append(f"[PASS] Gate {gate_id}: critic review {critic} PASS")

    return ok, messages


def _parse_markdown_tables(text: str) -> list[list[dict[str, str]]]:
    tables: list[list[dict[str, str]]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines) - 1:
        header_line = lines[i].strip()
        sep_line = lines[i + 1].strip()
        if "|" not in header_line or not _TABLE_SEPARATOR_RE.match(sep_line):
            i += 1
            continue
        headers = [cell.strip().lower() for cell in header_line.strip("|").split("|")]
        rows: list[dict[str, str]] = []
        i += 2
        while i < len(lines) and "|" in lines[i]:
            raw = lines[i].strip()
            if not raw:
                break
            cells = [cell.strip() for cell in raw.strip("|").split("|")]
            if len(cells) < len(headers):
                cells.extend([""] * (len(headers) - len(cells)))
            rows.append({headers[idx]: cells[idx] for idx in range(len(headers))})
            i += 1
        if rows:
            tables.append(rows)
        continue
    return tables


def _score_passes(value: str, minimum: int = 2) -> bool:
    text = value.strip().lower()
    patterns = (
        r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)",
        r"score\s*[:=]\s*(\d+(?:\.\d+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            score = float(match.group(1))
            denom = float(match.group(2)) if len(match.groups()) > 1 and match.group(2) else float(minimum)
        except ValueError:
            return False
        return score >= minimum and denom >= minimum
    try:
        return float(text) >= minimum
    except ValueError:
        return False


def _split_evidence_paths(value: str) -> list[str]:
    cleaned = value.replace("<br>", ",").replace("<br/>", ",").replace("<br />", ",")
    cleaned = cleaned.replace("`", "")
    return [item.strip() for item in re.split(r"[,;]+", cleaned) if item.strip()]


def _path_exists(project_root: Path, evidence_path: str) -> bool:
    if not evidence_path or evidence_path.upper() in {"N/A", "NA", "NONE"}:
        return False
    candidate = Path(evidence_path)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    try:
        candidate.resolve().relative_to(project_root.resolve())
    except ValueError:
        return False
    return candidate.exists()


def validate_gate_rubric(
    project_root: str | Path,
    gate_id: str,
    aggregate_file: str | Path,
    *,
    rubric_path: str | Path | None = None,
    require_critic_reviews: bool = True,
) -> tuple[bool, list[str]]:
    """Validate a gate aggregate review against the configured rubric."""
    root = Path(project_root)
    aggregate = Path(aggregate_file)
    messages: list[str] = []
    ok = True

    if require_critic_reviews:
        critic_ok, critic_messages = validate_gate_critic_reviews(root, gate_id)
        messages.extend(critic_messages)
        ok = ok and critic_ok

    rubric_ids = required_rubric_ids(gate_id, rubric_path)
    if not rubric_ids:
        return True, [f"[WARN] Gate {gate_id}: no configured rubric items"]

    if gate_id == "G3":
        from utils.stage_gate import check_stage

        m3_ok, m3_messages = check_stage(root, "M3S03")
        if not m3_ok:
            messages.append("[FAIL] Gate G3: M3S03 evidence gate is not currently PASS; aggregate review cannot advance.")
            messages.extend(message for message in m3_messages if message.startswith("[FAIL] M3S03"))
            ok = False
        else:
            messages.append("[PASS] Gate G3: M3S03 evidence gate PASS, including trained-weight checks")

    if not aggregate.exists():
        return False, [f"[FAIL] Gate {gate_id}: aggregate review missing: {aggregate}"]

    try:
        text = aggregate.read_text(encoding="utf-8")
    except Exception as exc:
        return False, [f"[FAIL] Gate {gate_id}: aggregate review unreadable: {exc}"]

    verdict = _extract_verdict(text)
    if verdict != "PASS":
        messages.append(f"[FAIL] Gate {gate_id}: aggregate verdict must be explicit PASS for advancement")
        ok = False
    else:
        integrity_issues = find_pass_integrity_issues(text)
        if integrity_issues:
            messages.append(
                f"[FAIL] Gate {gate_id}: aggregate verdict PASS but review contains "
                "blocking/ambiguous language: " + " | ".join(integrity_issues[:3])
            )
            ok = False
        else:
            messages.append(f"[PASS] Gate {gate_id}: aggregate verdict PASS")

    if "rubric results" not in text.lower() and "rubric id" not in text.lower():
        messages.append(f"[FAIL] Gate {gate_id}: aggregate review missing Rubric Results table")
        ok = False

    rows_by_id: dict[str, dict[str, str]] = {}
    for table in _parse_markdown_tables(text):
        for row in table:
            row_id = row.get("rubric id") or row.get("id") or row.get("rubric")
            if row_id:
                rows_by_id[row_id.strip()] = row

    for rubric_id in rubric_ids:
        row = rows_by_id.get(rubric_id)
        if row is None:
            messages.append(f"[FAIL] Gate {gate_id}: missing rubric row {rubric_id}")
            ok = False
            continue

        verdict_cell = (row.get("verdict") or row.get("status") or "").strip().upper()
        if verdict_cell != "PASS":
            messages.append(f"[FAIL] Gate {gate_id}: rubric {rubric_id} verdict is not PASS")
            ok = False
        else:
            messages.append(f"[PASS] Gate {gate_id}: rubric {rubric_id} verdict PASS")

        score_cell = row.get("score") or ""
        if not _score_passes(score_cell):
            messages.append(f"[FAIL] Gate {gate_id}: rubric {rubric_id} score must be 2/2")
            ok = False
        else:
            messages.append(f"[PASS] Gate {gate_id}: rubric {rubric_id} score 2/2")

        evidence_cell = (
            row.get("evidence paths")
            or row.get("evidence")
            or row.get("evidence path")
            or ""
        )
        evidence_paths = _split_evidence_paths(evidence_cell)
        existing = [path for path in evidence_paths if _path_exists(root, path)]
        if not existing:
            messages.append(f"[FAIL] Gate {gate_id}: rubric {rubric_id} has no existing evidence path")
            ok = False
        else:
            messages.append(f"[PASS] Gate {gate_id}: rubric {rubric_id} evidence path exists")

    return ok, messages
