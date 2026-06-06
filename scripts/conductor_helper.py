"""Conductor helper — cross-stage input resolution and planning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spiral.project import MODULE_STAGES
from spiral.review_registry import STAGE_REVIEW_OUTPUTS

# Cross-stage input mapping: stage -> list of required upstream docs
# Filenames follow the canonical naming from utils.file_guard._get_canonical_name()
CROSS_STAGE_INPUTS: dict[str, list[str]] = {
    # M1: Domain Survey
    "M1S01": [],
    "M1S02": ["M1S01_topic_scoping.md"],
    "M1S03": ["M1S01_topic_scoping.md", "M1S02_literature_deepdive.md"],
    "M1S04": ["M1S02_literature_deepdive.md", "M1S03_research_question.md"],
    "M1S05": ["M1S03_research_question.md", "M1S04_hypothesis_generation.md"],
    # M2: Method Design (5-Stage)
    "M2S01": ["handoff_M1_M2.md", "M1S03_research_question.md", "M1S04_hypothesis_generation.md", "M1S02_literature_deepdive.md"],
    "M2S02": ["M2S01_cross_domain_search.md", "M1S02_literature_deepdive.md"],
    "M2S03": ["M2S02_method_inspiration.md", "M1S03_research_question.md", "M1S04_hypothesis_generation.md"],
    "M2S04": ["M2S03_method_architecture.md", "M2S02_method_inspiration.md"],
    "M2S05": ["M2S04_algorithm_theory.md", "M1S02_literature_deepdive.md"],
    # M3: Main experiment design, implementation, baselines, execution, validation
    "M3S01": ["handoff_M2_M3.md", "M2S03_method_architecture.md", "M2S04_algorithm_theory.md", "M2S05_experiment_setup.md", "M2S05_metric_protocol.yaml"],
    "M3S02": ["M3S01_main_experiment_design.md", "handoff_M2_M3.md", "M2S03_method_architecture.md", "M2S04_algorithm_theory.md", "M2S05_experiment_setup.md"],
    "M3S03": ["M3S02_implementation.md", "M3S01_main_experiment_design.md", "M2S05_experiment_setup.md", "M1S02_literature_deepdive.md"],
    "M3S04": ["M3S03_baseline_lock.md", "M3S01_main_experiment_design.md", "M1S04_hypothesis_generation.md", "M3S02_implementation.md"],
    "M3S05": ["M3S04_main_experiment.md", "M3S03_baseline_lock.md", "M3S01_main_experiment_design.md", "M1S04_hypothesis_generation.md"],
    # M4: Deep Analysis
    "M4S01": [
        "handoff_M3_M4.md",
        "M3S04_main_experiment.md",
        "M3S05_result_validation.md",
        "M3S03_baseline_lock.md",
        "M3S01_main_experiment_design.md",
        "M2S05_experiment_setup.md",
        "M2_source_log.yaml",
        "M1S02_literature_deepdive.md",
        "M1_source_log.yaml",
        "survey_memory.yaml",
    ],
    "M4S02": [
        "handoff_M3_M4.md",
        "M4S01_other_findings.md",
        "M3S05_result_validation.md",
        "M3S04_main_experiment.md",
        "M3S03_baseline_lock.md",
        "M3S01_main_experiment_design.md",
        "M2S03_method_architecture.md",
        "M2S05_experiment_setup.md",
        "M2_source_log.yaml",
        "M1S02_literature_deepdive.md",
        "M1_source_log.yaml",
        "survey_memory.yaml",
    ],
    "M4S03": ["handoff_M3_M4.md", "M4S02_analysis_experiment_design.md", "M4S01_other_findings.md", "M3S02_implementation.md", "M3S03_baseline_lock.md", "M3S04_main_experiment.md", "M3S05_result_validation.md", "M3S01_main_experiment_design.md"],
    "M4S04": ["handoff_M3_M4.md", "M3S04_main_experiment.md", "M3S05_result_validation.md", "M3S03_baseline_lock.md", "M4S01_other_findings.md", "M4S02_analysis_experiment_design.md", "M4S03_analysis_experiment.md"],
    # M5: Writing & Finalization
    "M5S01": [
        "handoff_M4_M5.md",
        "M1S02_literature_deepdive.md",
        "M1_source_log.yaml",
        "M1S03_research_question.md",
        "M1S04_hypothesis_generation.md",
        "M2S03_method_architecture.md",
        "M2S04_algorithm_theory.md",
        "M2S05_experiment_setup.md",
        "M3S01_main_experiment_design.md",
        "M3S04_main_experiment.md",
        "M3S05_result_validation.md",
        "M4S03_analysis_experiment.md",
        "M4S04_analysis_results.md",
    ],
    "M5S02": ["M5S01_pre_write_audit.md", "M1S02_literature_deepdive.md", "M1_source_log.yaml", "M1S04_hypothesis_generation.md", "M2S03_method_architecture.md"],
    "M5S04": ["M5S02_paper_outline.md", "M2S03_method_architecture.md", "M2S04_algorithm_theory.md", "M5S01_pre_write_audit.md"],
    "M5S05": ["M5S02_paper_outline.md", "M3S04_main_experiment.md", "M3S05_result_validation.md", "M3S03_baseline_lock.md", "M5S04_methodology.md"],
    "M5S06": ["M5S02_paper_outline.md", "M4S04_analysis_results.md", "M4S03_analysis_experiment.md", "M5S05_experiments_results.md"],
    "M5S03": ["M5S02_paper_outline.md", "M1S02_literature_deepdive.md", "M5S01_pre_write_audit.md", "M5S04_methodology.md", "M5S05_experiments_results.md", "M5S06_analysis_discussion.md"],
    "M5S07": ["M5S02_paper_outline.md", "M5S03_introduction_relatedwork.md", "M5S04_methodology.md", "M5S05_experiments_results.md", "M5S06_analysis_discussion.md"],
    "M5S08": ["M5S02_paper_outline.md", "M5S03_introduction_relatedwork.md", "M5S04_methodology.md", "M5S05_experiments_results.md", "M5S06_analysis_discussion.md", "M5S07_abstract_conclusion.md"],
    "M5S09": ["M5S02_paper_outline.md", "M5S03_introduction_relatedwork.md", "M5S04_methodology.md", "M5S05_experiments_results.md", "M5S06_analysis_discussion.md", "M5S07_abstract_conclusion.md", "M5S08_final_compilation.md"],
    # M6: Submission Review & Revision Loop
    "M6S01": ["handoff_M5_completion.md"],
    "M6S02": ["M6S01_submission_audit.md", "M6S01_internal_peer_review.md"],
    "M6S03": ["M6S02_external_review_submission.md"],
    "M6S04": ["M6S03_review_parsing.md", "M6S03_review_matrix.md"],
    "M6S05": ["M6S04_rebuttal_strategy.md", "M6S04_action_plan.md"],
    "M6S06": ["M6S05_revision_execution.md", "M6S04_action_plan.md"],
}


# Backward-compatible aliases for projects created before canonical names
# stabilized. The first existing file wins.
INPUT_ALIASES: dict[str, list[str]] = {
    "M2S03_method_architecture.md": [
        "M2S03_method_architecture.md",
        "M2S03_methodology_design.md",
        "M2S03_experiment_protocol.md",
    ],
    "M2S04_algorithm_theory.md": [
        "M2S04_algorithm_theory.md",
        "M2S03_methodology_design.md",
    ],
    "M2S05_experiment_setup.md": [
        "M2S05_experiment_setup.md",
        "M2S04_experiment_setup.md",
        "M2S04_baseline_selection.md",
    ],
    "M3S01_main_experiment_design.md": [
        "M3S01_main_experiment_design.md",
    ],
}


ENTRY_BRIEF_RELATIVE_PATH = Path("state") / "research_brief.yaml"


def _resolve_input_doc(knowledge_dir: Path, stage: str, filename: str) -> Path | None:
    candidates = INPUT_ALIASES.get(filename, [filename])

    for candidate_name in candidates:
        if candidate_name == "survey_memory.yaml":
            candidate = knowledge_dir.parent / "state" / "survey_memory.yaml"
            if candidate.exists():
                return candidate
            continue

        if candidate_name.startswith("handoff_"):
            candidate = knowledge_dir / candidate_name
            if candidate.exists():
                return candidate
            continue

        mod = stage[:2]
        candidate = knowledge_dir / mod / candidate_name
        if candidate.exists():
            return candidate

        if knowledge_dir.exists():
            for subdir in knowledge_dir.iterdir():
                if subdir.is_dir():
                    alt = subdir / candidate_name
                    if alt.exists():
                        return alt

        candidate = knowledge_dir / candidate_name
        if candidate.exists():
            return candidate

    return None


def get_input_docs(project_root: Path, stage: str) -> list[Path]:
    """Resolve input documents for a given stage."""
    inputs: list[Path] = []
    knowledge_dir = project_root / "knowledge"
    required = CROSS_STAGE_INPUTS.get(stage, [])
    seen: set[Path] = set()

    entry_brief = project_root / ENTRY_BRIEF_RELATIVE_PATH
    if entry_brief.exists():
        inputs.append(entry_brief)
        seen.add(entry_brief)

    for filename in required:
        candidate = _resolve_input_doc(knowledge_dir, stage, filename)
        if candidate and candidate not in seen:
            inputs.append(candidate)
            seen.add(candidate)

    if stage == "M5S09":
        for artifact in (
            project_root / "artifacts" / "paper.tex",
            project_root / "artifacts" / "paper.pdf",
            project_root / "artifacts" / "refs.bib",
        ):
            if artifact not in seen:
                inputs.append(artifact)
                seen.add(artifact)

    # Always include survey_memory for M1 stages (after S01)
    if stage.startswith("M1") and stage != "M1S01":
        mem = project_root / "state" / "survey_memory.yaml"
        if mem.exists():
            inputs.append(mem)

    return inputs


def get_stage_review_outputs(project_root: Path, stage: str) -> dict[str, Path]:
    """Return required stage-review output paths for a stage."""
    root = Path(project_root)
    outputs = STAGE_REVIEW_OUTPUTS.get(stage, {})
    return {checker: root / rel_path for checker, rel_path in outputs.items()}


def get_module_for_stage(stage: str) -> str:
    for mod, stages in MODULE_STAGES.items():
        if stage in stages:
            return mod
    return "M1"
