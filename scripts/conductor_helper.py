"""Conductor helper — cross-stage input resolution and planning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spiral.project import MODULE_STAGES

# Cross-stage input mapping: stage -> list of required upstream docs
# Filenames follow the canonical naming from utils.file_guard._get_canonical_name()
CROSS_STAGE_INPUTS: dict[str, list[str]] = {
    # M1: Domain Survey
    "M1S01": [],
    "M1S02": ["M1S01_topic_scoping.md"],
    "M1S03": ["M1S01_topic_scoping.md", "M1S02_literature_deepdive.md"],
    "M1S04": ["M1S02_literature_deepdive.md", "M1S03_research_question.md"],
    "M1S05": ["M1S03_research_question.md", "M1S04_hypothesis_generation.md"],
    # M2: Method Design (6-Stage)
    "M2S01": ["handoff_M1_M2.md", "M1S03_research_question.md", "M1S04_hypothesis_generation.md", "M1S02_literature_deepdive.md"],
    "M2S02": ["M2S01_cross_domain_search.md", "M1S02_literature_deepdive.md"],
    "M2S03": ["M2S02_method_inspiration.md", "M1S03_research_question.md", "M1S04_hypothesis_generation.md"],
    "M2S04": ["M2S03_method_architecture.md", "M2S02_method_inspiration.md"],
    "M2S05": ["M2S04_algorithm_theory.md", "M1S02_literature_deepdive.md"],
    "M2S06": ["M2S03_method_architecture.md", "M2S04_algorithm_theory.md", "M2S05_experiment_setup.md"],
    # M3: Experiment Implementation & Execution (4-Stage)
    "M3S01": ["handoff_M2_M3.md", "M2S03_method_architecture.md", "M2S04_algorithm_theory.md", "M2S05_experiment_setup.md", "M2S06_full_experiment_plan.md"],
    "M3S02": ["M3S01_implementation.md", "M2S05_experiment_setup.md", "M2S06_full_experiment_plan.md", "M1S02_literature_deepdive.md"],
    "M3S03": ["M3S02_baseline_lock.md", "M2S06_full_experiment_plan.md", "M1S04_hypothesis_generation.md", "M3S01_implementation.md"],
    "M3S04": ["M3S03_main_experiment.md", "M3S02_baseline_lock.md", "M1S04_hypothesis_generation.md"],
    # M4: Deep Analysis
    "M4S01": ["handoff_M3_M4.md", "M3S03_main_experiment.md", "M3S04_result_validation.md", "M3S02_baseline_lock.md", "M1S02_literature_deepdive.md"],
    "M4S02": ["handoff_M3_M4.md", "M4S01_other_findings.md", "M3S04_result_validation.md", "M3S03_main_experiment.md", "M3S02_baseline_lock.md", "M2S03_method_architecture.md", "M2S05_experiment_setup.md", "M2S06_full_experiment_plan.md", "M1S02_literature_deepdive.md"],
    "M4S03": ["handoff_M3_M4.md", "M4S02_analysis_experiment_design.md", "M4S01_other_findings.md", "M3S01_implementation.md", "M3S02_baseline_lock.md", "M3S03_main_experiment.md", "M3S04_result_validation.md", "M2S06_full_experiment_plan.md"],
    "M4S04": ["handoff_M3_M4.md", "M3S03_main_experiment.md", "M3S04_result_validation.md", "M3S02_baseline_lock.md", "M4S01_other_findings.md", "M4S02_analysis_experiment_design.md", "M4S03_analysis_experiment.md"],
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
        "M2S06_full_experiment_plan.md",
        "M3S03_main_experiment.md",
        "M3S04_result_validation.md",
        "M4S03_analysis_experiment.md",
        "M4S04_analysis_results.md",
    ],
    "M5S02": ["M5S01_pre_write_audit.md", "M1S02_literature_deepdive.md", "M1_source_log.yaml", "M1S04_hypothesis_generation.md", "M2S03_method_architecture.md"],
    "M5S03": ["M5S02_paper_outline.md", "M1S02_literature_deepdive.md", "M5S01_pre_write_audit.md"],
    "M5S04": ["M5S02_paper_outline.md", "M2S03_method_architecture.md", "M2S04_algorithm_theory.md", "M5S03_introduction_relatedwork.md"],
    "M5S05": ["M5S02_paper_outline.md", "M3S03_main_experiment.md", "M3S04_result_validation.md", "M3S02_baseline_lock.md", "M5S04_methodology.md"],
    "M5S06": ["M5S02_paper_outline.md", "M4S04_analysis_results.md", "M4S03_analysis_experiment.md", "M5S05_experiments_results.md"],
    "M5S07": ["M5S02_paper_outline.md", "M5S03_introduction_relatedwork.md", "M5S04_methodology.md", "M5S05_experiments_results.md", "M5S06_analysis_discussion.md"],
    "M5S08": ["M5S02_paper_outline.md", "M5S03_introduction_relatedwork.md", "M5S04_methodology.md", "M5S05_experiments_results.md", "M5S06_analysis_discussion.md", "M5S07_abstract_conclusion.md"],
    # M6: Submission Review & Revision Loop
    "M6S01": ["handoff_M5_completion.md"],
    "M6S02": ["M6S01_submission_audit.md", "M6S01_internal_peer_review.md"],
    "M6S03": ["M6S02_external_review_submission.md"],
    "M6S04": ["M6S03_review_parsing.md", "M6S03_review_matrix.md"],
    "M6S05": ["M6S04_rebuttal_strategy.md", "M6S04_action_plan.md"],
    "M6S06": ["M6S05_revision_execution.md", "M6S04_action_plan.md"],
}


# Backward-compatible aliases for projects created before the M2 six-stage
# canonical names stabilized. The first existing file wins.
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
    "M2S06_full_experiment_plan.md": [
        "M2S06_full_experiment_plan.md",
        "M2S05_full_experiment_plan.md",
    ],
}


STAGE_REVIEW_OUTPUTS: dict[str, dict[str, str]] = {
    "M2S01": {
        "m2_search_quality": "knowledge/reviews/M2S01_search_quality_review.md",
    },
    "M2S02": {
        "m2_migration": "knowledge/reviews/M2S02_migration_review.md",
    },
    "M2S03": {
        "m2_design_review": "knowledge/reviews/M2S03_design_review.md",
    },
    "M2S04": {
        "m2_design_review": "knowledge/reviews/M2S04_design_review.md",
    },
    "M2S05": {
        "m2_experiment_design_review": "knowledge/reviews/M2S05_experiment_design_review.md",
    },
    "M2S06": {
        "m2_experiment_plan_review": "knowledge/reviews/M2S06_experiment_plan_review.md",
    },
    "M3S01": {
        "m3_dataset_env_review": "knowledge/reviews/M3S01_dataset_env_review.md",
    },
    "M3S02": {
        "m3_baseline_result_review": "knowledge/reviews/M3S02_baseline_result_review.md",
    },
    "M3S03": {
        "m3_main_result_review": "knowledge/reviews/M3S03_main_result_review.md",
    },
    "M4S01": {
        "m4_findings_audit": "knowledge/reviews/M4S01_findings_audit_review.md",
    },
    "M4S02": {
        "m4_analysis_design_review": "knowledge/reviews/M4S02_analysis_design_review.md",
    },
    "M4S03": {
        "m4_analysis_execution_review": "knowledge/reviews/M4S03_analysis_execution_review.md",
    },
    "M5S01": {
        "m5_prewrite_review": "knowledge/reviews/M5S01_prewrite_review.md",
    },
    "M5S02": {
        "m5_outline_style_review": "knowledge/reviews/M5S02_outline_style_review.md",
    },
    "M5S03": {
        "m5_intro_relatedwork_review": "knowledge/reviews/M5S03_intro_relatedwork_review.md",
    },
    "M5S04": {
        "m5_method_figure_review": "knowledge/reviews/M5S04_method_figure_review.md",
    },
    "M5S05": {
        "m5_experiments_results_review": "knowledge/reviews/M5S05_experiments_results_review.md",
    },
    "M5S06": {
        "m5_analysis_discussion_review": "knowledge/reviews/M5S06_analysis_discussion_review.md",
    },
    "M5S07": {
        "m5_abstract_conclusion_review": "knowledge/reviews/M5S07_abstract_conclusion_review.md",
    },
    "M5S08": {
        "m5_final_compilation_review": "knowledge/reviews/M5S08_final_compilation_review.md",
    },
    "M6S01": {
        "m6_internal_peer_review": "knowledge/reviews/M6S01_internal_peer_review.md",
        "m6_submission_audit": "knowledge/reviews/M6S01_submission_audit_review.md",
    },
    "M6S02": {
        "m6_external_submission_review": "knowledge/reviews/M6S02_external_submission_review.md",
    },
    "M6S03": {
        "m6_review_parsing_review": "knowledge/reviews/M6S03_review_parsing_review.md",
    },
    "M6S04": {
        "m6_rebuttal_strategy_review": "knowledge/reviews/M6S04_rebuttal_strategy_review.md",
    },
    "M6S05": {
        "m6_revision_execution_review": "knowledge/reviews/M6S05_revision_execution_review.md",
    },
    "M6S06": {
        "m6_revision_validation_review": "knowledge/reviews/M6S06_revision_validation_review.md",
    },
}

ENTRY_BRIEF_RELATIVE_PATH = Path("state") / "research_brief.yaml"


def _resolve_input_doc(knowledge_dir: Path, stage: str, filename: str) -> Path | None:
    candidates = INPUT_ALIASES.get(filename, [filename])

    for candidate_name in candidates:
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
