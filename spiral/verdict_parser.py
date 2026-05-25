"""Verdict Parser — Stand-alone review/gate verdict extraction.

This module is responsible ONLY for parsing structured verdicts from review
documents (markdown or YAML). It performs NO state mutations, NO orchestration
decisions, and NO backtracking logic.

All stateful orchestration (backtracking, stale marking, spiral counting)
remains the sole responsibility of Conductor.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Stage-review verdict patterns
# ---------------------------------------------------------------------------

_STAGE_REVIEW_VERDICT_RE = re.compile(
    r"(?im)^(?:\*\*)?verdict(?:\*\*)?\s*[:：]\s*(PASS|REVISE|REWORK|BACKTRACK|HALT|FIX)\s*$"
)
_STAGE_REVIEW_SECTION_VERDICT_RE = re.compile(
    r"(?ims)^##+\s*verdict\s*\n\s*(?:\*\*)?(PASS|REVISE|REWORK|BACKTRACK|HALT|FIX)(?:\*\*)?\s*$"
)

_STAGE_REVIEW_FIELDS: tuple[str, ...] = (
    "target_stage",
    "blocking_reason",
    "required_fix",
    "success_criteria",
    "evidence_paths",
    "rebuild_mode",
    "rerun_scope",
    "handoff_updates",
)

_STAGE_REVIEW_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    field: re.compile(
        rf"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?`?{re.escape(field)}`?(?:\*\*)?\s*[:：]\s*(.+?)\s*$"
    )
    for field in _STAGE_REVIEW_FIELDS
}

# ---------------------------------------------------------------------------
# M3-specific repair fields
# ---------------------------------------------------------------------------

_M3_REPAIR_FIELDS: tuple[str, ...] = (
    "target_stage",
    "blocking_reason",
    "required_fix",
    "success_criteria",
    "evidence_paths",
    "rebuild_mode",
    "rerun_scope",
    "handoff_updates",
)

_M3_REPAIR_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    field: re.compile(
        rf"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?`?{re.escape(field)}`?(?:\*\*)?\s*[:：]"
    )
    for field in _M3_REPAIR_FIELDS
}

_M3_REPAIR_FIELD_VALUE_PATTERNS: dict[str, re.Pattern[str]] = {
    field: re.compile(
        rf"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?`?{re.escape(field)}`?(?:\*\*)?\s*[:：]\s*(.+?)\s*$"
    )
    for field in _M3_REPAIR_FIELDS
}

_M3_REBUILD_MODES: set[str] = {"incremental_replay", "full_regenerate"}

# ---------------------------------------------------------------------------
# Low-level extraction helpers
# ---------------------------------------------------------------------------


def extract_stage_review_verdict(text: str) -> str | None:
    """Extract an explicit verdict string from a stage-review markdown text."""
    match = _STAGE_REVIEW_VERDICT_RE.search(text)
    if match:
        return match.group(1).upper()
    match = _STAGE_REVIEW_SECTION_VERDICT_RE.search(text)
    if match:
        return match.group(1).upper()
    return None


def extract_stage_review_field(text: str, field: str) -> str:
    """Extract the value of a single structured field from review text."""
    pattern = _STAGE_REVIEW_FIELD_PATTERNS.get(field)
    if pattern is None:
        return ""
    match = pattern.search(text)
    return match.group(1).strip(" `*") if match else ""


def extract_stage_review_payload(text: str) -> dict[str, Any]:
    """Extract the full structured payload from a stage-review document."""
    payload: dict[str, Any] = {"verdict": extract_stage_review_verdict(text)}
    for field in _STAGE_REVIEW_FIELDS:
        value = extract_stage_review_field(text, field)
        if field in {"evidence_paths", "handoff_updates"}:
            if value:
                payload[field] = [item.strip() for item in re.split(r"[,\n;]+", value) if item.strip()]
            else:
                payload[field] = []
        else:
            payload[field] = value
    return payload


# ---------------------------------------------------------------------------
# M3-specific helpers
# ---------------------------------------------------------------------------


def has_m3_repair_field(text: str, field: str) -> bool:
    """Return True if *text* contains the given M3 repair field header."""
    pattern = _M3_REPAIR_FIELD_PATTERNS.get(field)
    if pattern is None:
        return False
    return bool(pattern.search(text))


def missing_m3_repair_fields(text: str, fields: tuple[str, ...] | None = None) -> list[str]:
    """Return the list of M3 repair fields that are missing from *text*."""
    if fields is None:
        fields = _M3_REPAIR_FIELDS
    return [field for field in fields if not has_m3_repair_field(text, field)]


def extract_m3_repair_field_value(text: str, field: str) -> str:
    """Extract the value of a single M3 repair field."""
    pattern = _M3_REPAIR_FIELD_VALUE_PATTERNS.get(field)
    if pattern is None:
        return ""
    match = pattern.search(text)
    return match.group(1).strip(" `*") if match else ""


def extract_m3s04_decision(text: str) -> str | None:
    """Extract the KEEP/FIX/BACKTRACK decision from an M3S04 document."""
    decision_patterns = [
        r"决策\s*[:：]\s*(KEEP|FIX|BACKTRACK)",
        r"\*\*决策\*\*\s*[:：]\s*(KEEP|FIX|BACKTRACK)",
        r"Decision\s*[:：]\s*(KEEP|FIX|BACKTRACK)",
    ]
    for pattern in decision_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


def is_valid_rebuild_mode(mode: str | None) -> bool:
    """Return True if *mode* is a recognised rebuild mode."""
    return mode in _M3_REBUILD_MODES


# ---------------------------------------------------------------------------
# Structured parsing for Conductor orchestration
# ---------------------------------------------------------------------------


class StageReviewParseResult:
    """Immutable result of parsing a single stage-review file."""

    def __init__(self, checker: str, review_path: Path, text: str):
        self.checker = checker
        self.review_path = review_path
        self.raw_text = text
        self.payload = extract_stage_review_payload(text)

    @property
    def verdict(self) -> str | None:
        return self.payload.get("verdict")

    @property
    def target_stage(self) -> str:
        return self.payload.get("target_stage", "")

    @property
    def blocking_reason(self) -> str:
        return self.payload.get("blocking_reason", "")

    @property
    def required_fix(self) -> str:
        return self.payload.get("required_fix", "")

    @property
    def success_criteria(self) -> str:
        return self.payload.get("success_criteria", "")

    @property
    def rebuild_mode(self) -> str:
        return self.payload.get("rebuild_mode", "")

    @property
    def rerun_scope(self) -> str:
        return self.payload.get("rerun_scope", "")

    @property
    def evidence_paths(self) -> list[str]:
        return self.payload.get("evidence_paths", [])

    @property
    def handoff_updates(self) -> list[str]:
        return self.payload.get("handoff_updates", [])

    @property
    def missing_fields(self) -> list[str]:
        """Return fields that are required but absent (for non-PASS verdicts).

        Only scalar repair-advice fields are strictly required.
        List fields (evidence_paths, handoff_updates) may be empty.
        target_stage defaults to the current stage if omitted.
        """
        if self.verdict == "PASS":
            return []
        required = ("blocking_reason", "required_fix", "success_criteria",
                    "rebuild_mode", "rerun_scope")
        missing: list[str] = []
        for field in required:
            val = self.payload.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(field)
        return missing

    @property
    def is_valid(self) -> tuple[bool, str]:
        """Return (ok, error_message) for basic structural validity."""
        if not self.verdict:
            return False, f"missing explicit verdict"
        if self.verdict == "HALT":
            return True, ""  # HALT is structurally valid; orchestrator decides what to do
        if self.verdict == "PASS":
            return True, ""
        # Non-PASS verdicts must have repair advice fields
        missing = self.missing_fields
        if missing:
            return False, f"missing repair advice fields: {', '.join(missing)}"
        if not is_valid_rebuild_mode(self.rebuild_mode):
            return False, f"invalid rebuild_mode={self.rebuild_mode or 'unset'}"
        return True, ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for Conductor state decisions."""
        return {
            "checker": self.checker,
            "review_path": str(self.review_path),
            "verdict": self.verdict,
            "target_stage": self.target_stage,
            "blocking_reason": self.blocking_reason,
            "required_fix": self.required_fix,
            "success_criteria": self.success_criteria,
            "rebuild_mode": self.rebuild_mode,
            "rerun_scope": self.rerun_scope,
            "evidence_paths": self.evidence_paths,
            "handoff_updates": self.handoff_updates,
            "missing_fields": self.missing_fields,
        }


class VerdictParser:
    """Pure parser: reads review files and produces structured results.

    This class is deliberately stateless and side-effect free. It may raise
    ``IOError`` when a file cannot be read, but it never mutates project state.
    """

    @staticmethod
    def parse_stage_review(checker: str, review_path: Path) -> StageReviewParseResult:
        """Read a single stage-review file and return structured data."""
        text = review_path.read_text(encoding="utf-8")
        return StageReviewParseResult(checker, review_path, text)

    @staticmethod
    def parse_all_stage_reviews(
        review_outputs: dict[str, Path]
    ) -> list[StageReviewParseResult]:
        """Parse every configured stage-review file.

        Raises FileNotFoundError if any file is missing so that the caller
        (Conductor) can decide whether to BLOCK or proceed.
        """
        results: list[StageReviewParseResult] = []
        for checker, path in review_outputs.items():
            if not path.exists():
                raise FileNotFoundError(f"Stage review missing: {path.name}")
            results.append(VerdictParser.parse_stage_review(checker, path))
        return results

    @staticmethod
    def select_dominant_non_pass(
        reviews: list[StageReviewParseResult],
    ) -> StageReviewParseResult | None:
        """Given a list of parsed reviews, pick the most severe non-PASS result.

        Severity order: BACKTRACK > FIX > REVISE > REWORK.
        Returns ``None`` if all reviews are PASS.
        """
        non_pass = [r for r in reviews if r.verdict != "PASS"]
        if not non_pass:
            return None
        severity = {"BACKTRACK": 4, "FIX": 3, "REVISE": 2, "REWORK": 1}
        return max(non_pass, key=lambda r: severity.get(r.verdict or "", 0))
