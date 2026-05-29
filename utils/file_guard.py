"""File guard — naming and location validation for stage outputs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from spiral.project import MODULE_STAGES, GATE_STAGES

VALID_STAGE_PATTERN = re.compile(r"^M[1-6]S\d{2}$")
VALID_GATE_PATTERN = re.compile(r"^G[1-6]$")

ALLOWED_EXTRA_STAGE_OUTPUTS = {
    # M6S03/M6S04 deliberately produce one primary stage report plus one
    # structured companion file used by downstream review/rebuttal planning.
    "M6S03": {"M6S03_review_matrix.md"},
    "M6S04": {"M6S04_action_plan.md"},
}


def _get_canonical_name(stage: str) -> str:
    """Map stage to canonical output filename (without extension)."""
    canonical_names = {
        # M1
        "M1S01": "topic_scoping",
        "M1S02": "literature_deepdive",
        "M1S03": "research_question",
        "M1S04": "hypothesis_generation",
        "M1S05": "novelty_feasibility",
        # M2 (updated for 6-Stage design)
        "M2S01": "cross_domain_search",
        "M2S02": "method_inspiration",
        "M2S03": "method_architecture",
        "M2S04": "algorithm_theory",
        "M2S05": "experiment_setup",
        "M2S06": "full_experiment_plan",
        # M3 (updated for 4-Stage design)
        "M3S01": "implementation",
        "M3S02": "baseline_lock",
        "M3S03": "main_experiment",
        "M3S04": "result_validation",
        # M4
        "M4S01": "other_findings",
        "M4S02": "analysis_experiment_design",
        "M4S03": "analysis_experiment",
        "M4S04": "analysis_results",
        # M5
        "M5S01": "pre_write_audit",
        "M5S02": "paper_outline",
        "M5S03": "introduction_relatedwork",
        "M5S04": "methodology",
        "M5S05": "experiments_results",
        "M5S06": "analysis_discussion",
        "M5S07": "abstract_conclusion",
        "M5S09": "full_polish",
        "M5S08": "final_compilation",
        # M6
        "M6S01": "submission_audit",
        "M6S02": "external_review_submission",
        "M6S03": "review_parsing",
        "M6S04": "rebuttal_strategy",
        "M6S05": "revision_execution",
        "M6S06": "revision_validation",
    }
    return canonical_names.get(stage, stage.lower())


def get_canonical_output_path(project_root: str | Path, stage: str) -> Path:
    """Return the canonical output path for a stage."""
    root = Path(project_root)
    mod = stage[:2]
    canonical = _get_canonical_name(stage)
    return root / "knowledge" / mod / f"{stage}_{canonical}.md"


def validate_stage_output(
    project_root: str | Path,
    stage: str,
    output_file: str | Path,
) -> tuple[bool, str]:
    """Validate a stage output file."""
    root = Path(project_root)
    out = Path(output_file)

    if not VALID_STAGE_PATTERN.match(stage):
        return False, f"Invalid stage format: {stage}"

    # Must be under knowledge/
    knowledge_dir = root / "knowledge"
    try:
        _ = out.resolve().relative_to(knowledge_dir.resolve())
    except ValueError:
        return False, f"Output must be under {knowledge_dir}: {out}"

    # Must match S{NN}_{canonical_name}.md
    mod = stage[:2]
    expected_name = f"{stage}_{_get_canonical_name(stage)}.md"
    if out.name != expected_name:
        return False, (
            f"Filename mismatch. Expected: {expected_name}, Got: {out.name}\n"
            f"Canonical path: {get_canonical_output_path(root, stage)}"
        )

    if not out.exists():
        return False, f"Output file does not exist: {out}"

    return True, f"file_guard: OK — {out.name}"


def check_single_file_principle(
    project_root: str | Path,
    stage: str,
) -> tuple[bool, str]:
    """Ensure only one output file exists for this stage."""
    root = Path(project_root)
    mod = stage[:2]
    stage_dir = root / "knowledge" / mod

    if not stage_dir.exists():
        return True, "No stage dir yet — single file principle not applicable"

    candidates = list(stage_dir.glob(f"{stage}_*.md"))
    allowed_names = {
        f"{stage}_{_get_canonical_name(stage)}.md",
        *ALLOWED_EXTRA_STAGE_OUTPUTS.get(stage, set()),
    }
    unexpected = [c for c in candidates if c.name not in allowed_names]
    if unexpected:
        names = [c.name for c in unexpected]
        return False, (
            f"Single file principle violated: found unexpected files for {stage}:\n"
            f"  {', '.join(names)}\n"
            f"Allowed files: {', '.join(sorted(allowed_names))}"
        )
    return True, "Single file principle: OK"


def validate_gate_review(
    project_root: str | Path,
    gate_id: str,
    output_file: str | Path,
) -> tuple[bool, str]:
    """Validate a Gate review aggregate file."""
    root = Path(project_root)
    out = Path(output_file)

    if not VALID_GATE_PATTERN.match(gate_id):
        return False, f"Invalid gate format: {gate_id}"

    knowledge_dir = root / "knowledge"
    try:
        _ = out.resolve().relative_to(knowledge_dir.resolve())
    except ValueError:
        return False, f"Gate review must be under {knowledge_dir}: {out}"

    expected_name = f"{gate_id}_aggregate.md"
    reviews_dir = knowledge_dir / "reviews"
    if out.resolve().parent != reviews_dir.resolve():
        return False, f"Gate review must be in knowledge/reviews/: {out}"
    if out.name != expected_name:
        return False, f"Expected: {expected_name}, Got: {out.name}"

    return True, f"Gate review file_guard: OK — {out.name}"
