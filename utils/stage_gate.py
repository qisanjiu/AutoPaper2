"""Stage gate — quality checks for specific stages."""

from __future__ import annotations

import re
import json
import sys
from pathlib import Path
from typing import Any

# Import shared verdict parser to avoid duplicating regex/parsing logic.
_framework_root = Path(__file__).parent.parent.resolve()
if str(_framework_root) not in sys.path:
    sys.path.insert(0, str(_framework_root))

from spiral.verdict_parser import (
    extract_stage_review_verdict,
    extract_m3s04_decision,
    missing_m3_repair_fields,
    extract_m3_repair_field_value,
    is_valid_rebuild_mode,
)
from utils.file_guard import find_alternate_outputs

_STAGE_REVIEW_REQUIREMENTS: dict[str, dict[str, str]] = {
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
        "m3_baseline_lock_audit": "knowledge/reviews/M3S02_baseline_lock_audit.md",
    },
    "M3S03": {
        "m3_main_result_review": "knowledge/reviews/M3S03_main_result_review.md",
    },
    "M4S01": {
        "m4_findings_audit": "knowledge/reviews/M4S01_findings_audit_review.md",
    },
    "M4S02": {
        "m4_analysis_design_review": "knowledge/reviews/M4S02_analysis_design_review.md",
        "m4_execution_readiness_review": "knowledge/reviews/M4S02_execution_readiness_review.md",
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
    "M5S09": {
        "m5_full_polish_review": "knowledge/reviews/M5S09_full_polish_review.md",
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

_M1S02_ROUND_REVIEW_REQUIREMENTS: dict[int, str] = {
    1: "knowledge/reviews/M1S02_round1_review.md",
    2: "knowledge/reviews/M1S02_round2_review.md",
    3: "knowledge/reviews/M1S02_round3_review.md",
}

_M5S01_REQUIRED_UPSTREAM_DOCS: dict[str, str] = {
    "M1S02_literature_deepdive.md": "knowledge/M1/M1S02_literature_deepdive.md",
    "M1_source_log.yaml": "knowledge/M1/M1_source_log.yaml",
    "M1S03_research_question.md": "knowledge/M1/M1S03_research_question.md",
    "M1S04_hypothesis_generation.md": "knowledge/M1/M1S04_hypothesis_generation.md",
    "M2S03_method_architecture.md": "knowledge/M2/M2S03_method_architecture.md",
    "M2S04_algorithm_theory.md": "knowledge/M2/M2S04_algorithm_theory.md",
    "M2S05_experiment_setup.md": "knowledge/M2/M2S05_experiment_setup.md",
    "M2S06_full_experiment_plan.md": "knowledge/M2/M2S06_full_experiment_plan.md",
    "M3S03_main_experiment.md": "knowledge/M3/M3S03_main_experiment.md",
    "M3S04_result_validation.md": "knowledge/M3/M3S04_result_validation.md",
    "M4S03_analysis_experiment.md": "knowledge/M4/M4S03_analysis_experiment.md",
    "M4S04_analysis_results.md": "knowledge/M4/M4S04_analysis_results.md",
    "handoff_M4_M5.md": "knowledge/handoff_M4_M5.md",
}

def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _file_has_content(path: Path) -> bool:
    try:
        return path.exists() and path.is_file() and bool(path.read_text(encoding="utf-8").strip())
    except Exception:
        return False


def _positive_m5_readiness_line(text: str) -> bool:
    """Return True only for an explicit, completed continue-writing decision."""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if not _contains_any(line, ("是否建议继续写作", "continue writing", "writing readiness", "审计结论")):
            continue
        if any(marker in lowered for marker in ("yes / no", "yes/no", "是 / 否", "是/否", "...", "todo", "tbd", "待定")):
            continue
        if re.search(r"[:：]\s*(no|否|not[_ -]?ready|block)", lowered):
            continue
        if re.search(r"[:：]\s*(yes|是|ready|proceed|continue)", lowered):
            return True
    return False


def _has_m5_blocking_gap(text: str) -> bool:
    """Detect completed M5S01 rows that still mark high-severity gaps as blocking."""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if not _contains_any(line, ("high", "高")):
            continue
        if not _contains_any(line, ("block", "阻塞", "必须先修复")):
            continue
        if _contains_any(line, ("no", "none", "0", "否", "无", "not blocking", "非阻塞")):
            continue
        if _contains_any(line, ("yes", "是", "blocking", "阻塞")):
            return True
    return False


def _m5_reference_count_declared(text: str) -> bool:
    patterns = (
        r"(?i)(?:reference|exemplar|sample|style)\s*(?:paper|papers|count|samples)[^\n:：]*[:：]?\s*(?:3|4|5)\b",
        r"(?:高层次论文样本数|参照论文数量|风格参照论文)[^\n:：]*[:：]?\s*(?:3|4|5)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _check_m5s01_prewrite_audit(root: Path) -> tuple[bool, list[str]]:
    doc = root / "knowledge" / "M5" / "M5S01_pre_write_audit.md"
    messages: list[str] = []
    ok = True
    if not doc.exists():
        return False, ["[FAIL] M5S01: knowledge/M5/M5S01_pre_write_audit.md missing"]

    text = doc.read_text(encoding="utf-8")
    required = [
        ("evidence gap", "证据缺口"),
        ("narrative gap", "叙事缺口"),
        ("citation gap", "引用缺口"),
    ]
    for terms in required:
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] M5S01: missing required audit signal: {terms[0]}")
            ok = False
        else:
            messages.append(f"[PASS] M5S01: includes {terms[0]}")

    if not _contains_any(text, ("上游文档完整性", "upstream document", "upstream completeness")):
        messages.append("[FAIL] M5S01: upstream document completeness audit missing")
        ok = False
    else:
        messages.append("[PASS] M5S01: upstream document completeness audit present")

    missing_upstream = [
        name
        for name, rel_path in _M5S01_REQUIRED_UPSTREAM_DOCS.items()
        if not _file_has_content(root / rel_path)
    ]
    if missing_upstream:
        messages.append("[FAIL] M5S01: missing/nonempty upstream documents: " + ", ".join(missing_upstream))
        ok = False
    else:
        messages.append("[PASS] M5S01: required upstream documents exist and are nonempty")

    if not _contains_any(text, ("contribution", "核心贡献", "贡献点")):
        messages.append("[FAIL] M5S01: contribution articulation missing")
        ok = False
    elif not _contains_any(text, ("fully_supported", "fully supported", "充分支撑", "完全支撑")):
        messages.append("[FAIL] M5S01: no fully_supported contribution identified")
        ok = False
    else:
        messages.append("[PASS] M5S01: at least one fully_supported contribution identified")

    if not _contains_any(text, ("支撑证据", "evidence path", "evidence_paths", "knowledge/M3", "knowledge/M4")):
        messages.append("[FAIL] M5S01: contribution evidence paths missing")
        ok = False
    else:
        messages.append("[PASS] M5S01: contribution evidence paths documented")

    if not _contains_any(text, ("style", "风格", "排版", "layout", "exemplar", "参照论文")):
        messages.append("[FAIL] M5S01: no style/layout reference audit found")
        ok = False
    elif not _contains_any(text, ("风格蒸馏", "style distillation", "不复制", "不得复制", "do not copy")):
        messages.append("[FAIL] M5S01: style/layout audit missing distillation anti-copy boundary")
        ok = False
    else:
        messages.append("[PASS] M5S01: style/layout reference audit and anti-copy boundary present")

    consistency_terms = (
        ("main metric", "主指标"),
        ("baseline", "基线"),
        ("dataset", "数据集"),
        ("method name", "方法名称"),
        ("consistent", "一致"),
    )
    for terms in consistency_terms:
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] M5S01: data consistency audit missing {terms[0]}")
            ok = False
        else:
            messages.append(f"[PASS] M5S01: data consistency audit includes {terms[0]}")

    if _has_m5_blocking_gap(text):
        messages.append("[FAIL] M5S01: high-severity blocking gap remains unresolved")
        ok = False
    else:
        messages.append("[PASS] M5S01: no high-severity blocking gap marked unresolved")

    if not _positive_m5_readiness_line(text):
        messages.append("[FAIL] M5S01: missing explicit positive continue-writing decision")
        ok = False
    else:
        messages.append("[PASS] M5S01: explicit positive continue-writing decision present")

    return ok, messages


def _check_m5s02_outline_profile(root: Path) -> tuple[bool, list[str]]:
    doc = root / "knowledge" / "M5" / "M5S02_paper_outline.md"
    messages: list[str] = []
    ok = True
    if not doc.exists():
        return False, ["[FAIL] M5S02: knowledge/M5/M5S02_paper_outline.md missing"]

    text = doc.read_text(encoding="utf-8")
    required = [
        ("venue", "Venue"),
        ("plotting plan", "Plotting Plan"),
        ("terminology", "Terminology"),
        ("section plan", "Section Plan"),
        ("style & layout profile", "Style & Layout Profile"),
        ("figure style profile", "Figure Style Profile"),
    ]
    for terms in required:
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] M5S02: missing required outline signal: {terms[0]}")
            ok = False
        else:
            messages.append(f"[PASS] M5S02: includes {terms[0]}")

    if not _m5_reference_count_declared(text):
        messages.append("[FAIL] M5S02: missing explicit 3-5 reference/exemplar paper count")
        ok = False
    else:
        messages.append("[PASS] M5S02: declares 3-5 reference/exemplar papers")

    if not _contains_any(text, ("结构", "paragraph function", "段落功能", "rhythm", "图表密度", "layout constraint", "版式约束")):
        messages.append("[FAIL] M5S02: Style & Layout Profile missing transferable structure/layout signals")
        ok = False
    else:
        messages.append("[PASS] M5S02: Style & Layout Profile includes transferable structure/layout signals")

    if not _contains_any(text, ("不可迁移", "do not copy", "不得复制", "不复制", "禁止模仿", "avoid copying")):
        messages.append("[FAIL] M5S02: style/layout profile missing explicit anti-copy boundary")
        ok = False
    else:
        messages.append("[PASS] M5S02: anti-copy boundary documented")

    if not _contains_any(text, ("palette", "color grammar", "颜色语法", "visual richness", "视觉丰富度", "layout grammar", "布局语法", "venue preset")):
        messages.append("[FAIL] M5S02: Figure Style Profile missing venue preset / palette / layout grammar")
        ok = False
    else:
        messages.append("[PASS] M5S02: Figure Style Profile contains venue preset / palette / layout grammar")

    if not _contains_any(text, ("gpt-image-2", "image2", "draw.io", "drawio", "matplotlib", "seaborn", "plt")):
        messages.append("[FAIL] M5S02: figure backend policy missing")
        ok = False
    else:
        messages.append("[PASS] M5S02: figure backend policy present")
    if not _contains_any(text, ("gpt-image-2", "image2")):
        messages.append("[FAIL] M5S02: architecture/method figure policy must name image2/gpt-image-2")
        ok = False
    else:
        messages.append("[PASS] M5S02: architecture/method figure policy names image2/gpt-image-2")
    if not _contains_any(text, ("paper-framework-figure-studio-pro", "framework figure studio", "c-narcissus")):
        messages.append("[FAIL] M5S02: method/framework figure style reference missing")
        ok = False
    else:
        messages.append("[PASS] M5S02: method/framework figure style reference documented")
    if not _contains_any(text, ("nature-figure", "Nature figure", "nature figure")):
        messages.append("[FAIL] M5S02: experiment plot style reference missing")
        ok = False
    else:
        messages.append("[PASS] M5S02: experiment plot style reference documented")

    return ok, messages


def _extract_m6_internal_review_score(text: str) -> float | None:
    """Extract the final M6 internal-review aggregate score.

    Reviewer-level scores are intentionally ignored here.  The internal review
    must provide one explicit aggregate line so the M6S01 gate can enforce the
    user-facing 8/10 threshold deterministically.
    """
    patterns = (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?(?:internal review score|final internal score|overall internal score|average internal score|aggregate internal score)(?:\*\*)?\s*[:：]\s*(\d+(?:\.\d+)?)\s*/\s*10\s*$",
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?(?:内部审查评分|内部评审评分|内部审稿评分|综合评分|平均分)(?:\*\*)?\s*[:：]\s*(\d+(?:\.\d+)?)\s*/\s*10\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
    return None


def _check_m6_internal_peer_review(root: Path) -> tuple[bool, list[str]]:
    """Validate the mandatory M6 internal peer-review loop."""
    review_path = root / "knowledge" / "reviews" / "M6S01_internal_peer_review.md"
    messages: list[str] = []
    ok = True

    if not review_path.exists():
        return False, ["[FAIL] M6S01: internal peer review missing"]

    try:
        text = review_path.read_text(encoding="utf-8")
    except Exception as exc:
        return False, [f"[FAIL] M6S01: internal peer review unreadable: {exc}"]

    reviewer_ids = set(re.findall(r"(?im)^#{2,4}\s*Reviewer\s+([A-Za-z0-9_-]+)\b", text))
    if len(reviewer_ids) < 3:
        messages.append(
            f"[FAIL] M6S01: internal review has {len(reviewer_ids)} reviewer persona(s); expected at least 3"
        )
        ok = False
    else:
        messages.append(f"[PASS] M6S01: internal review includes {len(reviewer_ids)} reviewer personas")

    score = _extract_m6_internal_review_score(text)
    if score is None:
        messages.append("[FAIL] M6S01: internal review missing final Internal Review Score: X/10")
        ok = False
    elif score < 8.0:
        messages.append(f"[FAIL] M6S01: internal review score {score:.1f}/10 is below required 8.0/10")
        ok = False
    else:
        messages.append(f"[PASS] M6S01: internal review score {score:.1f}/10 meets required 8.0/10")

    high_zero = re.search(
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"(?:unresolved high(?:-priority)? issues|high unresolved|未解决\s*high\s*问题|high\s*未解决问题)"
        r"(?:\*\*)?\s*[:：]\s*0\s*$",
        text,
    )
    if not high_zero:
        messages.append("[FAIL] M6S01: internal review must state unresolved high-priority issues: 0")
        ok = False
    else:
        messages.append("[PASS] M6S01: internal review has no unresolved high-priority issues")

    if not _contains_any(text, ("revision loop", "backtrack", "回溯", "迭代", "accept/revert")):
        messages.append("[FAIL] M6S01: internal review missing revision/backtrack loop evidence")
        ok = False
    else:
        messages.append("[PASS] M6S01: internal review documents revision/backtrack loop evidence")

    return ok, messages


def _check_m6_submission_log(root: Path, *, label: str = "M6S02") -> tuple[bool, list[str]]:
    """Validate paperreview.ai submission evidence.

    M6 cannot rely on a prose report alone.  The submission log is produced by
    ``scripts/paperreview_uploader.py`` and is the durable proof that the
    external review request was actually attempted and accepted.
    """
    log = root / "knowledge" / "M6" / "M6S02_submission_log.json"
    messages: list[str] = []
    ok = True

    if not log.exists():
        return False, [f"[FAIL] {label}: submission log JSON not found"]

    try:
        log_data = json.loads(log.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"[FAIL] {label}: submission log unreadable: {exc}"]

    status = str(log_data.get("status", "")).lower()
    if status != "success":
        messages.append(f"[FAIL] {label}: submission log status is not success ({status or 'unset'})")
        ok = False
    else:
        messages.append(f"[PASS] {label}: submission log status success")

    platform = str(log_data.get("platform", "")).lower()
    url = str(log_data.get("url", "")).lower()
    if "paperreview.ai" not in platform and "paperreview.ai" not in url:
        messages.append(f"[FAIL] {label}: submission log missing paperreview.ai platform/url")
        ok = False
    else:
        messages.append(f"[PASS] {label}: submission log identifies paperreview.ai")

    for field in ("submitted_at", "pdf_path", "email"):
        if not str(log_data.get(field, "")).strip():
            messages.append(f"[FAIL] {label}: submission log missing {field}")
            ok = False
        else:
            messages.append(f"[PASS] {label}: submission log includes {field}")

    tracking = log_data.get("tracking")
    if not isinstance(tracking, dict) or not tracking:
        messages.append(f"[FAIL] {label}: submission log missing tracking info")
        ok = False
    elif not any(str(v).strip() for v in tracking.values()):
        messages.append(f"[FAIL] {label}: submission log tracking info is empty")
        ok = False
    else:
        messages.append(f"[PASS] {label}: submission log tracking info present")

    return ok, messages


def _check_m6_review_email(root: Path, *, label: str = "M6S03") -> tuple[bool, list[str]]:
    """Validate raw paperreview.ai review email evidence."""
    email_json = root / "knowledge" / "M6" / "M6S03_review_email.json"
    messages: list[str] = []
    ok = True

    if not email_json.exists():
        return False, [f"[FAIL] {label}: review email JSON not found"]

    try:
        email_data = json.loads(email_json.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"[FAIL] {label}: review email unreadable: {exc}"]

    status = str(email_data.get("status", "")).lower()
    if status != "success":
        messages.append(f"[FAIL] {label}: review email status is not success ({status or 'unset'})")
        ok = False
    else:
        messages.append(f"[PASS] {label}: review email status success")

    found_email = email_data.get("found_email") or {}
    if not isinstance(found_email, dict):
        messages.append(f"[FAIL] {label}: found_email payload must be an object")
        return False, messages

    body = str(found_email.get("body", "")).strip()
    if not body:
        messages.append(f"[FAIL] {label}: review email body missing")
        ok = False
    else:
        messages.append(f"[PASS] {label}: review email body present")

    if not any(str(found_email.get(field, "")).strip() for field in ("subject", "from", "message_id", "date")):
        messages.append(f"[FAIL] {label}: review email missing raw metadata (subject/from/message_id/date)")
        ok = False
    else:
        messages.append(f"[PASS] {label}: review email raw metadata present")

    return ok, messages


def _check_m6_review_matrix(root: Path, *, label: str = "M6S03") -> tuple[bool, list[str]]:
    """Validate that the external review matrix is atomic, not a placeholder."""
    matrix = root / "knowledge" / "M6" / "M6S03_review_matrix.md"
    messages: list[str] = []
    ok = True

    if not matrix.exists():
        return False, [f"[FAIL] {label}: review matrix not found"]

    try:
        text = matrix.read_text(encoding="utf-8")
    except Exception as exc:
        return False, [f"[FAIL] {label}: review matrix unreadable: {exc}"]

    if not re.search(r"\bPR-[A-Za-z0-9_-]+\b", text):
        messages.append(f"[FAIL] {label}: review matrix missing atomic PR-* item ids")
        ok = False
    else:
        messages.append(f"[PASS] {label}: review matrix contains atomic PR-* item ids")

    required_terms = {
        "original_text": ("original_text", "原文", "review text"),
        "class": ("class", "类别", "classification"),
        "severity": ("severity", "严重", "high", "medium", "low"),
        "route": ("preliminary_route", "target_stage", "route", "回溯", "修订"),
    }
    for field, terms in required_terms.items():
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] {label}: review matrix missing {field}")
            ok = False
        else:
            messages.append(f"[PASS] {label}: review matrix includes {field}")

    return ok, messages


def _extract_pr_ids(text: str) -> set[str]:
    return {match.group(0) for match in re.finditer(r"\bPR-[A-Za-z0-9_-]+\b", text)}


def _extract_pr_blocks(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?im)^\s*(?:#{1,6}\s*)?(?:[-*]\s*)?(PR-[A-Za-z0-9_-]+)\b", text))
    blocks: dict[str, str] = {}
    if matches:
        for index, match in enumerate(matches):
            item_id = match.group(1)
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            blocks[item_id] = text[match.start():end]
    for item_id in _extract_pr_ids(text):
        blocks.setdefault(item_id, text)
    return blocks


def _extract_pr_severities(text: str) -> dict[str, str]:
    severities: dict[str, str] = {}
    for item_id, block in _extract_pr_blocks(text).items():
        match = re.search(r"(?im)(?:severity|严重程度|严重性)\s*[:：]?\s*\**\s*(High|Medium|Low)\b", block)
        if not match:
            match = re.search(r"\b(High|Medium|Low)\b", block, re.IGNORECASE)
        severities[item_id] = match.group(1).title() if match else "Unknown"
    return severities


def _m6_review_item_ids(root: Path) -> set[str]:
    matrix = root / "knowledge" / "M6" / "M6S03_review_matrix.md"
    if not matrix.exists():
        return set()
    try:
        return _extract_pr_ids(matrix.read_text(encoding="utf-8"))
    except Exception:
        return set()


def _m6_action_plan_ids(root: Path) -> set[str]:
    action_plan = root / "knowledge" / "M6" / "M6S04_action_plan.md"
    if not action_plan.exists():
        return set()
    try:
        return _extract_pr_ids(action_plan.read_text(encoding="utf-8"))
    except Exception:
        return set()


def _check_m6s04_item_coverage(root: Path) -> tuple[bool, list[str]]:
    """Ensure every external-review item is converted into an executable action."""
    strategy = root / "knowledge" / "M6" / "M6S04_rebuttal_strategy.md"
    action_plan = root / "knowledge" / "M6" / "M6S04_action_plan.md"
    matrix = root / "knowledge" / "M6" / "M6S03_review_matrix.md"
    messages: list[str] = []
    ok = True

    if not matrix.exists() or not action_plan.exists():
        return ok, messages

    matrix_text = matrix.read_text(encoding="utf-8")
    action_text = action_plan.read_text(encoding="utf-8")
    matrix_ids = _extract_pr_ids(matrix_text)
    action_ids = _extract_pr_ids(action_text)
    if matrix_ids:
        missing = sorted(matrix_ids - action_ids)
        if missing:
            messages.append(f"[FAIL] M6S04: action plan missing review item ids: {', '.join(missing)}")
            ok = False
        else:
            messages.append("[PASS] M6S04: action plan covers all review matrix PR-* items")

    if strategy.exists():
        strategy_ids = _extract_pr_ids(strategy.read_text(encoding="utf-8"))
        missing = sorted(matrix_ids - strategy_ids)
        if missing:
            messages.append(f"[FAIL] M6S04: rebuttal strategy missing review item ids: {', '.join(missing)}")
            ok = False
        elif matrix_ids:
            messages.append("[PASS] M6S04: rebuttal strategy covers all review matrix PR-* items")

    required_item_fields = ("class", "severity", "target_stage", "required_fix", "success_criteria", "rebuild_mode", "rerun_scope", "priority")
    blocks = _extract_pr_blocks(action_text)
    for item_id in sorted(matrix_ids or action_ids):
        block = blocks.get(item_id, "")
        missing_fields = [field for field in required_item_fields if field not in block]
        if missing_fields:
            messages.append(f"[FAIL] M6S04: {item_id} missing action fields: {', '.join(missing_fields)}")
            ok = False
        else:
            messages.append(f"[PASS] M6S04: {item_id} has executable action fields")
    return ok, messages


def _check_m6s05_item_execution(root: Path) -> tuple[bool, list[str]]:
    """Ensure every external-review item was actually executed or explicitly handled."""
    execution = root / "knowledge" / "M6" / "M6S05_revision_execution.md"
    messages: list[str] = []
    ok = True

    if not execution.exists():
        return ok, messages

    text = execution.read_text(encoding="utf-8")
    expected_ids = _m6_review_item_ids(root) | _m6_action_plan_ids(root)
    if not expected_ids:
        return ok, messages

    execution_ids = _extract_pr_ids(text)
    missing = sorted(expected_ids - execution_ids)
    if missing:
        messages.append(f"[FAIL] M6S05: revision execution missing review item ids: {', '.join(missing)}")
        ok = False
    else:
        messages.append("[PASS] M6S05: revision execution covers all PR-* items")

    blocks = _extract_pr_blocks(text)
    completion_terms = ("done", "completed", "resolved", "executed", "fixed", "修订完成", "已完成", "已解决", "执行完成")
    evidence_terms = ("evidence", "path", "artifact", "output", "file", "证据", "路径", "产物", "输出")
    bad_terms = ("pending", "unresolved", "failed", "todo", "not done", "未完成", "未解决", "失败")
    for item_id in sorted(expected_ids):
        block = blocks.get(item_id, "")
        lowered = block.lower()
        if any(term in lowered for term in bad_terms):
            messages.append(f"[FAIL] M6S05: {item_id} execution is marked pending/failed/unresolved")
            ok = False
        elif not _contains_any(block, completion_terms):
            messages.append(f"[FAIL] M6S05: {item_id} execution missing completion status")
            ok = False
        else:
            messages.append(f"[PASS] M6S05: {item_id} execution has completion status")
        if not _contains_any(block, evidence_terms):
            messages.append(f"[FAIL] M6S05: {item_id} execution missing evidence/output path")
            ok = False
        else:
            messages.append(f"[PASS] M6S05: {item_id} execution includes evidence/output path")
    return ok, messages


def _check_m6s06_item_resolution(root: Path) -> tuple[bool, list[str]]:
    """Ensure final validation resolves every external-review item."""
    validation = root / "knowledge" / "M6" / "M6S06_revision_validation.md"
    execution = root / "knowledge" / "M6" / "M6S05_revision_execution.md"
    matrix = root / "knowledge" / "M6" / "M6S03_review_matrix.md"
    messages: list[str] = []
    ok = True

    if not validation.exists():
        return ok, messages

    text = validation.read_text(encoding="utf-8")
    expected_ids = _m6_review_item_ids(root) | _m6_action_plan_ids(root)
    if not expected_ids:
        return ok, messages

    validation_ids = _extract_pr_ids(text)
    missing = sorted(expected_ids - validation_ids)
    if missing:
        messages.append(f"[FAIL] M6S06: validation missing review item ids: {', '.join(missing)}")
        ok = False
    else:
        messages.append("[PASS] M6S06: validation covers all PR-* items")

    if execution.exists():
        execution_ids = _extract_pr_ids(execution.read_text(encoding="utf-8"))
        missing_execution = sorted(expected_ids - execution_ids)
        if missing_execution:
            messages.append(f"[FAIL] M6S06: M6S05 execution missing review item ids: {', '.join(missing_execution)}")
            ok = False
        else:
            messages.append("[PASS] M6S06: M6S05 execution covers all PR-* items")

    severities = _extract_pr_severities(matrix.read_text(encoding="utf-8")) if matrix.exists() else {}
    high_ids = sorted(item_id for item_id, severity in severities.items() if severity == "High")
    if high_ids:
        if not re.search(r"(?is)(High\s*(?:解决率|resolution).{0,160}100\s*%|100\s*%.{0,160}(?:High\s*(?:解决率|resolution)))", text):
            messages.append("[FAIL] M6S06: High-priority review items require explicit 100% resolution rate")
            ok = False
        else:
            messages.append("[PASS] M6S06: High-priority resolution rate is 100%")

    blocks = _extract_pr_blocks(text)
    resolved_terms = ("resolved", "pass", "done", "completed", "closed", "已解决", "通过", "完成", "解决")
    bad_terms = ("unresolved", "failed", "needs_more_work", "open", "pending", "未解决", "失败", "待处理")
    for item_id in sorted(expected_ids):
        block = blocks.get(item_id, "")
        lowered = block.lower()
        if any(term in lowered for term in bad_terms):
            messages.append(f"[FAIL] M6S06: {item_id} validation is unresolved/failed/pending")
            ok = False
        elif not _contains_any(block, resolved_terms):
            messages.append(f"[FAIL] M6S06: {item_id} validation missing resolved status")
            ok = False
        else:
            messages.append(f"[PASS] M6S06: {item_id} validation resolved")
    return ok, messages


def _count_exp_ids(text: str) -> int:
    return len(set(re.findall(r"\bExp-[A-Za-z0-9_-]+\b", text, flags=re.IGNORECASE)))


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "y", "1", "pass", "passed", "ok", "eligible", "是", "已验证"}
    return False


def _parse_floatish(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    is_percent = text.endswith("%")
    text = text.rstrip("%").strip()
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed / 100.0 if is_percent else parsed


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _resolve_project_path(root: Path, value: Any) -> Path | None:
    text = str(value or "").strip().strip("`'\"")
    if not text or text.lower() in {"n/a", "na", "none", "null", "-"}:
        return None
    text = text.removeprefix("project:").lstrip("./")
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _project_path_exists(root: Path, value: Any) -> bool:
    candidate = _resolve_project_path(root, value)
    return bool(candidate and candidate.exists())


def _looks_like_ablation_baseline(raw: dict[str, Any]) -> bool:
    fields = (
        raw.get("comparison_role"),
        raw.get("comparator_type"),
        raw.get("baseline_type"),
        raw.get("analysis_type"),
        raw.get("baseline_id"),
        raw.get("name"),
        raw.get("notes"),
    )
    text = " ".join(str(field or "") for field in fields).lower()
    if _truthy(raw.get("ablation_of_ours")) or _truthy(raw.get("is_ablation")):
        return True
    return any(marker in text for marker in ("ablation", "ablated", "消融"))


def _looks_simplified_implementation(raw: dict[str, Any]) -> bool:
    fields = (
        raw.get("implementation_fidelity"),
        raw.get("fidelity"),
        raw.get("implementation_note"),
        raw.get("notes"),
        raw.get("source"),
    )
    text = " ".join(str(field or "") for field in fields).lower()
    return any(marker in text for marker in ("simple", "simplified", "minimal", "toy", "简化", "简单", "玩具"))


def _first_nested_value(raw: dict[str, Any], paths: tuple[tuple[str, ...], ...]) -> Any:
    for path in paths:
        current: Any = raw
        found = True
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                found = False
                break
        if found and current is not None and str(current).strip() != "":
            return current
    return None


def _baseline_reference_value(raw: dict[str, Any]) -> Any:
    return _first_nested_value(
        raw,
        (
            ("reference_result", "value"),
            ("reference_result", "paper_value"),
            ("reference_result", "reported_value"),
            ("reference_result", "metric_value"),
            ("paper_value",),
            ("reference_value",),
            ("official_value",),
            ("historical_value",),
        ),
    )


def _baseline_local_value(raw: dict[str, Any], primary_metric: dict[str, Any] | None = None) -> Any:
    if primary_metric is None:
        metrics = raw.get("metrics")
        primary_metric = metrics.get("primary") if isinstance(metrics, dict) else {}
    return _first_nested_value(
        {"raw": raw, "primary": primary_metric if isinstance(primary_metric, dict) else {}},
        (
            ("raw", "local_validation", "local_value"),
            ("raw", "local_validation", "local_mean"),
            ("raw", "local_validation", "mean"),
            ("raw", "local_value"),
            ("raw", "value"),
            ("primary", "value"),
        ),
    )


def _baseline_declared_deviation(raw: dict[str, Any]) -> Any:
    return _first_nested_value(
        raw,
        (
            ("deviation", "relative_delta"),
            ("deviation", "relative_deviation"),
            ("relative_deviation",),
            ("relative_delta",),
        ),
    )


def _baseline_deviation_tolerance(raw: dict[str, Any]) -> float:
    value = _first_nested_value(
        raw,
        (
            ("deviation", "tolerance"),
            ("deviation", "tolerance_value"),
            ("reference_result", "tolerance"),
            ("relative_deviation_tolerance",),
            ("deviation_tolerance",),
        ),
    )
    parsed = _parse_floatish(value)
    return abs(parsed) if parsed is not None else 0.10


def _baseline_anomaly_triage(raw: dict[str, Any]) -> dict[str, Any]:
    triage = (
        raw.get("anomaly_triage")
        or raw.get("deviation_triage")
        or raw.get("deviation_analysis")
        or raw.get("anomaly_report")
    )
    return triage if isinstance(triage, dict) else {}


def _project_any_path_exists(root: Path, value: Any) -> bool:
    if isinstance(value, list):
        return any(_project_any_path_exists(root, item) for item in value)
    return _project_path_exists(root, value)


def _metric_range_bounds(value: Any) -> tuple[float, float] | None:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        low = _parse_floatish(value[0])
        high = _parse_floatish(value[1])
        if low is not None and high is not None:
            return (min(low, high), max(low, high))
    if isinstance(value, dict):
        low = _parse_floatish(value.get("min", value.get("low")))
        high = _parse_floatish(value.get("max", value.get("high")))
        if low is not None and high is not None:
            return (min(low, high), max(low, high))
    text = str(value or "").strip()
    if text:
        numbers = re.findall(r"-?\d+(?:\.\d+)?%?", text)
        if len(numbers) >= 2:
            low = _parse_floatish(numbers[0])
            high = _parse_floatish(numbers[1])
            if low is not None and high is not None:
                return (min(low, high), max(low, high))
    return None


def _metric_key_from(raw: dict[str, Any]) -> str:
    metrics = raw.get("metrics")
    primary = metrics.get("primary") if isinstance(metrics, dict) else {}
    return str(
        raw.get("metric")
        or raw.get("metric_key")
        or raw.get("primary_metric")
        or (primary.get("key") if isinstance(primary, dict) else "")
        or ""
    ).strip()


def _metric_protocol_id_from(raw: dict[str, Any]) -> str:
    protocol = raw.get("metric_protocol") if isinstance(raw.get("metric_protocol"), dict) else {}
    return str(
        raw.get("metric_protocol_id")
        or raw.get("protocol_id")
        or protocol.get("metric_protocol_id")
        or protocol.get("protocol_id")
        or protocol.get("id")
        or ""
    ).strip()


def _m2_metric_protocol_path(root: Path) -> Path:
    return root / "knowledge" / "M2" / "M2S05_metric_protocol.yaml"


def _load_m2_metric_protocol_registry(root: Path) -> tuple[bool, list[str], dict[str, dict[str, Any]]]:
    path = _m2_metric_protocol_path(root)
    messages: list[str] = []
    protocols_by_id: dict[str, dict[str, Any]] = {}
    ok = True
    if not path.exists():
        return False, [f"[FAIL] M2 metric protocol registry not found: {path.relative_to(root)}"], {}
    try:
        data = _load_yaml_mapping(path)
    except Exception as exc:
        return False, [f"[FAIL] M2 metric protocol registry unreadable: {exc}"], {}
    protocols = data.get("metric_protocols") or data.get("protocols")
    if not isinstance(protocols, list) or not protocols:
        return False, ["[FAIL] M2 metric protocol registry missing nonempty metric_protocols list"], {}

    messages.append(f"[PASS] M2 metric protocol registry lists {len(protocols)} protocol(s)")
    allowed_directions = {"higher_is_better", "lower_is_better"}
    for index, raw in enumerate(protocols, start=1):
        if not isinstance(raw, dict):
            messages.append(f"[FAIL] M2 metric protocol[{index}] must be a mapping")
            ok = False
            continue
        protocol_id = str(raw.get("metric_protocol_id") or raw.get("protocol_id") or raw.get("id") or "").strip()
        label = f"M2 metric protocol[{protocol_id or index}]"
        if not protocol_id:
            messages.append(f"[FAIL] {label}: missing metric_protocol_id")
            ok = False
            continue
        if protocol_id in protocols_by_id:
            messages.append(f"[FAIL] {label}: duplicate metric_protocol_id")
            ok = False
        protocols_by_id[protocol_id] = raw

        required_fields = {
            "dataset": raw.get("dataset"),
            "scenario": raw.get("scenario") or raw.get("task") or raw.get("task_type"),
            "split": raw.get("split"),
            "metric_key": raw.get("metric_key") or raw.get("metric"),
            "definition": raw.get("definition") or raw.get("metric_definition"),
            "calculation": raw.get("calculation") or raw.get("computation") or raw.get("formula"),
            "protocol_source": raw.get("protocol_source") or raw.get("source") or raw.get("reference"),
        }
        for field, value in required_fields.items():
            if not _nonempty(value):
                messages.append(f"[FAIL] {label}: missing {field}")
                ok = False
            else:
                messages.append(f"[PASS] {label}: includes {field}")

        direction = str(raw.get("direction") or "").strip().lower()
        if direction not in allowed_directions:
            messages.append(f"[FAIL] {label}: direction must be higher_is_better or lower_is_better")
            ok = False
        else:
            messages.append(f"[PASS] {label}: direction={direction}")

        value_range = _metric_range_bounds(raw.get("value_range"))
        normal_range = _metric_range_bounds(raw.get("normal_reference_range") or raw.get("normal_range"))
        if value_range is None:
            messages.append(f"[FAIL] {label}: missing valid value_range")
            ok = False
        else:
            messages.append(f"[PASS] {label}: value_range valid")
        if normal_range is None:
            messages.append(f"[FAIL] {label}: missing valid normal_reference_range")
            ok = False
        elif value_range and (normal_range[0] < value_range[0] or normal_range[1] > value_range[1]):
            messages.append(f"[FAIL] {label}: normal_reference_range must be inside value_range")
            ok = False
        else:
            messages.append(f"[PASS] {label}: normal_reference_range valid")

        sanity = raw.get("metric_sanity_check") or raw.get("implementation_check") or raw.get("sanity_check")
        if not isinstance(sanity, dict):
            messages.append(f"[FAIL] {label}: missing metric_sanity_check mapping")
            ok = False
        else:
            for field in ("test_case", "expected_value", "tolerance"):
                if not _nonempty(sanity.get(field)):
                    messages.append(f"[FAIL] {label}: metric_sanity_check missing {field}")
                    ok = False
            if all(_nonempty(sanity.get(field)) for field in ("test_case", "expected_value", "tolerance")):
                messages.append(f"[PASS] {label}: metric_sanity_check complete")

    return ok, messages, protocols_by_id


def _check_m3s02_metric_protocol_alignment(
    root: Path,
    label: str,
    raw: dict[str, Any],
    protocols_by_id: dict[str, dict[str, Any]],
    *,
    eligible: bool = False,
    primary: bool = False,
) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True
    protocol_id = _metric_protocol_id_from(raw)
    if not protocol_id:
        messages.append(f"[FAIL] {label}: missing metric_protocol_id from M2S05_metric_protocol.yaml")
        return False, messages
    protocol = protocols_by_id.get(protocol_id)
    if not protocol:
        messages.append(f"[FAIL] {label}: unknown metric_protocol_id {protocol_id}")
        return False, messages
    messages.append(f"[PASS] {label}: metric_protocol_id={protocol_id} found in M2")

    comparisons = {
        "dataset": str(raw.get("dataset") or "").strip(),
        "split": str(raw.get("split") or "").strip(),
        "metric": _metric_key_from(raw),
    }
    expected = {
        "dataset": str(protocol.get("dataset") or "").strip(),
        "split": str(protocol.get("split") or "").strip(),
        "metric": str(protocol.get("metric_key") or protocol.get("metric") or "").strip(),
    }
    scenario = str(raw.get("scenario") or raw.get("task") or raw.get("task_type") or "").strip()
    expected_scenario = str(protocol.get("scenario") or protocol.get("task") or protocol.get("task_type") or "").strip()
    if primary or eligible:
        comparisons["scenario"] = scenario
        expected["scenario"] = expected_scenario

    for field, actual in comparisons.items():
        expected_value = expected[field]
        if not actual:
            messages.append(f"[FAIL] {label}: missing {field} for metric protocol alignment")
            ok = False
        elif expected_value and actual.lower() != expected_value.lower():
            messages.append(f"[FAIL] {label}: {field}={actual} does not match M2 metric protocol {expected_value}")
            ok = False
        else:
            messages.append(f"[PASS] {label}: {field} matches M2 metric protocol")

    metrics = raw.get("metrics")
    primary_metric = metrics.get("primary") if isinstance(metrics, dict) else {}
    direction = str(
        raw.get("direction")
        or raw.get("metric_direction")
        or (primary_metric.get("direction") if isinstance(primary_metric, dict) else "")
        or ""
    ).strip().lower()
    expected_direction = str(protocol.get("direction") or "").strip().lower()
    if expected_direction and direction and direction != expected_direction:
        messages.append(f"[FAIL] {label}: metric direction {direction} does not match M2 protocol {expected_direction}")
        ok = False
    elif expected_direction and not direction and (primary or eligible):
        messages.append(f"[FAIL] {label}: missing metric direction from M2 protocol")
        ok = False
    else:
        messages.append(f"[PASS] {label}: metric direction aligned")

    local_value = _parse_floatish(_baseline_local_value(raw, primary_metric if isinstance(primary_metric, dict) else {}))
    value_range = _metric_range_bounds(protocol.get("value_range"))
    normal_range = _metric_range_bounds(protocol.get("normal_reference_range") or protocol.get("normal_range"))
    if local_value is not None and value_range and not (value_range[0] <= local_value <= value_range[1]):
        messages.append(f"[FAIL] {label}: local metric value {local_value:.3g} outside protocol value_range {value_range}")
        ok = False
    elif local_value is not None and value_range:
        messages.append(f"[PASS] {label}: local metric value inside protocol value_range")
    if local_value is not None and normal_range and not (normal_range[0] <= local_value <= normal_range[1]):
        messages.append(f"[FAIL] {label}: local metric value {local_value:.3g} outside normal_reference_range {normal_range}")
        triage_ok, triage_messages = _check_m3s02_anomaly_triage(root, label, raw)
        messages.extend(triage_messages)
        ok = ok and triage_ok
    elif local_value is not None and normal_range:
        messages.append(f"[PASS] {label}: local metric value inside normal_reference_range")

    validation = raw.get("metric_validation") or raw.get("metric_implementation_check")
    if not isinstance(validation, dict):
        messages.append(f"[FAIL] {label}: missing metric_validation mapping")
        ok = False
    else:
        status = str(validation.get("status") or validation.get("verdict") or "").strip().lower()
        if status not in {"pass", "passed", "verified", "ok"}:
            messages.append(f"[FAIL] {label}: metric_validation status must be pass/verified")
            ok = False
        else:
            messages.append(f"[PASS] {label}: metric_validation status={status}")
        evidence = validation.get("evidence_path") or validation.get("evidence_paths") or validation.get("log_path")
        if not _project_any_path_exists(root, evidence):
            messages.append(f"[FAIL] {label}: metric_validation missing existing evidence path")
            ok = False
        else:
            messages.append(f"[PASS] {label}: metric_validation evidence path exists")

    return ok, messages


def _check_m3s02_anomaly_triage(root: Path, label: str, raw: dict[str, Any]) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True
    triage = _baseline_anomaly_triage(raw)
    if not triage:
        return False, [f"[FAIL] {label}: large paper/local deviation requires anomaly_triage/deviation_analysis"]

    status = str(triage.get("status") or triage.get("verdict") or "").strip().lower()
    accepted_statuses = {
        "resolved",
        "fixed",
        "explained",
        "accepted_with_waiver",
        "waived",
        "not_reproducible_but_bounded",
        "bounded_caveat",
    }
    if status not in accepted_statuses:
        messages.append(f"[FAIL] {label}: anomaly_triage status must be resolved/explained/accepted_with_waiver, got {status or 'unset'}")
        ok = False
    else:
        messages.append(f"[PASS] {label}: anomaly_triage status={status}")

    cause = str(
        triage.get("root_cause")
        or triage.get("cause")
        or triage.get("explanation")
        or triage.get("reason")
        or ""
    ).strip()
    if not cause:
        messages.append(f"[FAIL] {label}: anomaly_triage missing root_cause/explanation")
        ok = False
    else:
        messages.append(f"[PASS] {label}: anomaly_triage explains root cause")

    evidence = (
        triage.get("evidence_paths")
        or triage.get("evidence_path")
        or triage.get("log_path")
        or triage.get("raw_log_path")
    )
    if not _project_any_path_exists(root, evidence):
        messages.append(f"[FAIL] {label}: anomaly_triage missing existing evidence path")
        ok = False
    else:
        messages.append(f"[PASS] {label}: anomaly_triage evidence path exists")
    return ok, messages


def _check_m3s02_reference_deviation(
    root: Path,
    label: str,
    raw: dict[str, Any],
    *,
    verdict: str,
    waiver: str = "",
    scope_limit: str = "",
    eligible: bool = False,
    primary: bool = False,
) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True
    reference_raw = _baseline_reference_value(raw)
    local_raw = _baseline_local_value(raw)
    reference_value = _parse_floatish(reference_raw)
    local_value = _parse_floatish(local_raw)
    needs_hard_reference = primary or eligible or verdict in {"verified_match", "verified_close"}

    if reference_raw is None:
        if needs_hard_reference and verdict != "trusted_with_caveats":
            messages.append(f"[FAIL] {label}: missing paper/reference result for baseline verification")
            ok = False
        elif verdict == "trusted_with_caveats" and waiver and scope_limit:
            messages.append(f"[PASS] {label}: missing reference result is bounded by trusted_with_caveats")
        else:
            messages.append(f"[WARN] {label}: paper/reference result not recorded")
        return ok, messages

    if reference_value is None:
        messages.append(f"[FAIL] {label}: paper/reference result is not numeric: {reference_raw}")
        return False, messages
    if local_value is None:
        messages.append(f"[FAIL] {label}: local baseline result is not numeric or missing")
        return False, messages

    messages.append(f"[PASS] {label}: paper/reference and local numeric results recorded")

    denominator = abs(reference_value) if abs(reference_value) > 1e-12 else 1.0
    computed_deviation = (local_value - reference_value) / denominator
    declared_raw = _baseline_declared_deviation(raw)
    declared_deviation = _parse_floatish(declared_raw)
    tolerance = _baseline_deviation_tolerance(raw)

    if declared_deviation is None:
        if needs_hard_reference:
            messages.append(
                f"[FAIL] {label}: relative_deviation must be recorded "
                f"(computed {computed_deviation:.3g}, tolerance {tolerance:.3g})"
            )
            ok = False
        else:
            messages.append(f"[WARN] {label}: relative_deviation not recorded")
        effective_deviation = computed_deviation
    else:
        effective_deviation = declared_deviation
        if abs(declared_deviation - computed_deviation) > max(0.02, tolerance * 0.25):
            messages.append(
                f"[FAIL] {label}: declared relative_deviation={declared_deviation:.3g} "
                f"does not match computed {computed_deviation:.3g}"
            )
            ok = False
        else:
            messages.append(f"[PASS] {label}: relative_deviation recorded and consistent")

    if abs(effective_deviation) > tolerance:
        messages.append(
            f"[FAIL] {label}: paper/local deviation {effective_deviation:.3g} exceeds tolerance {tolerance:.3g}"
        )
        ok = False
        triage_ok, triage_messages = _check_m3s02_anomaly_triage(root, label, raw)
        messages.extend(triage_messages)
        ok = ok and triage_ok
        if verdict in {"verified_match", "verified_close"}:
            messages.append(f"[FAIL] {label}: large deviation cannot be marked {verdict}")
            ok = False
        if eligible and (not waiver or not scope_limit):
            messages.append(f"[FAIL] {label}: eligible large-deviation baseline requires waiver and comparison_scope_limit")
            ok = False
    else:
        messages.append(f"[PASS] {label}: paper/local deviation within tolerance")

    return ok, messages


def _check_m3s02_baseline_lock_manifest(root: Path, baseline_contracts: list[Path]) -> tuple[bool, list[str]]:
    """Validate the structured M3S02 baseline lock manifest.

    The prose baseline report is useful, but M3S03 needs a deterministic
    machine-readable contract so it cannot silently move ahead with an
    unfinished or non-comparable baseline.
    """
    lock = root / "experiments" / "baselines" / "baseline_lock.yaml"
    messages: list[str] = []
    ok = True

    if not lock.exists():
        return False, ["[FAIL] M3S02: experiments/baselines/baseline_lock.yaml not found"]

    try:
        data = _load_yaml_mapping(lock)
    except Exception as exc:
        return False, [f"[FAIL] M3S02: baseline_lock.yaml unreadable: {exc}"]

    if not data:
        return False, ["[FAIL] M3S02: baseline_lock.yaml must contain a mapping"]

    baselines = data.get("baselines")
    if not isinstance(baselines, list) or not baselines:
        return False, ["[FAIL] M3S02: baseline_lock.yaml missing nonempty baselines list"]

    messages.append(f"[PASS] M3S02: baseline_lock.yaml lists {len(baselines)} baseline(s)")

    immutable = data.get("baseline_code_immutable_after_lock", data.get("immutable_after_lock"))
    if not _truthy(immutable):
        messages.append("[FAIL] M3S02: baseline_lock.yaml must set baseline_code_immutable_after_lock: true")
        ok = False
    else:
        messages.append("[PASS] M3S02: baseline code immutable after lock")

    registry_ok, registry_msgs, protocols_by_id = _load_m2_metric_protocol_registry(root)
    messages.extend(
        f"[{msg.split('] ', 1)[0].lstrip('[')}] M3S02 upstream: {msg.split('] ', 1)[1]}"
        if msg.startswith("[") and "] " in msg
        else msg
        for msg in registry_msgs
    )
    ok = ok and registry_ok

    contract_rel_paths = {
        str(path.relative_to(root)).replace("\\", "/")
        for path in baseline_contracts
        if path.exists()
    }
    primary_eligible = 0
    seen_primary_ids: list[str] = []

    for index, raw in enumerate(baselines, start=1):
        if not isinstance(raw, dict):
            messages.append(f"[FAIL] M3S02: baseline_lock baselines[{index}] must be a mapping")
            ok = False
            continue

        baseline_id = str(raw.get("baseline_id") or raw.get("id") or raw.get("name") or f"baseline_{index}").strip()
        label = f"M3S02 baseline_lock[{baseline_id}]"
        role = str(raw.get("comparison_role") or raw.get("role") or "").strip().lower()
        source = str(raw.get("source") or raw.get("implementation_source") or "").strip().lower()
        eligible = _truthy(raw.get("m3s03_eligible"))
        verdict = str(raw.get("verification_verdict") or "").strip().lower()
        waiver = str(raw.get("caveat_waiver_reason") or raw.get("waiver_reason") or "").strip()
        scope_limit = str(raw.get("comparison_scope_limit") or raw.get("scope_limit") or "").strip()

        if _looks_like_ablation_baseline(raw):
            messages.append(
                f"[FAIL] {label}: M3 baseline cannot be an ablation or variant of the proposed method; ablations belong to M4."
            )
            ok = False
        else:
            messages.append(f"[PASS] {label}: comparator is not marked as an ablation")

        if _looks_simplified_implementation(raw):
            messages.append(f"[FAIL] {label}: simplified/toy/minimal baseline implementations are forbidden")
            ok = False

        implementation_fidelity = str(raw.get("implementation_fidelity") or raw.get("fidelity") or "").strip().lower()
        reimplementation_sources = {
            "reimplementation",
            "self_implemented",
            "self-implemented",
            "from_scratch",
            "reproduce",
            "自行实现",
            "复现",
        }
        if source in reimplementation_sources:
            allowed_fidelity = {"full_reproduction", "paper_faithful_reproduction", "official_equivalent"}
            if implementation_fidelity not in allowed_fidelity:
                messages.append(
                    f"[FAIL] {label}: reimplemented baselines must set implementation_fidelity to "
                    "full_reproduction, paper_faithful_reproduction, or official_equivalent"
                )
                ok = False
            else:
                messages.append(f"[PASS] {label}: reimplemented baseline declares full reproduction fidelity")

            fidelity_evidence = (
                raw.get("fidelity_evidence")
                or raw.get("reproduction_evidence")
                or raw.get("architecture_match_evidence")
            )
            if not _project_path_exists(root, fidelity_evidence):
                messages.append(f"[FAIL] {label}: reimplemented baseline missing existing fidelity_evidence path")
                ok = False
            else:
                messages.append(f"[PASS] {label}: fidelity_evidence path exists")

        if "primary" in role:
            seen_primary_ids.append(baseline_id)
            if eligible:
                primary_eligible += 1

        for field in ("dataset", "split"):
            if not str(raw.get(field, "")).strip():
                messages.append(f"[FAIL] {label}: missing {field}")
                ok = False
            else:
                messages.append(f"[PASS] {label}: includes {field}")

        primary_metric = {}
        metrics = raw.get("metrics")
        if isinstance(metrics, dict):
            primary_metric = metrics.get("primary") or {}
        metric_key = raw.get("metric") or (primary_metric.get("key") if isinstance(primary_metric, dict) else "")
        local_value = raw.get("local_value", raw.get("value", primary_metric.get("value") if isinstance(primary_metric, dict) else None))
        if not str(metric_key).strip():
            messages.append(f"[FAIL] {label}: missing primary metric key")
            ok = False
        else:
            messages.append(f"[PASS] {label}: includes primary metric key")
        if local_value is None or str(local_value).strip() == "":
            messages.append(f"[FAIL] {label}: missing local baseline metric value")
            ok = False
        else:
            messages.append(f"[PASS] {label}: includes local baseline metric value")

        contract_ref = str(raw.get("metric_contract") or raw.get("metric_contract_path") or raw.get("contract_path") or "").strip()
        if not contract_ref:
            messages.append(f"[FAIL] {label}: missing metric_contract path")
            ok = False
        else:
            contract_rel = contract_ref.removeprefix("project:").lstrip("./")
            contract_path = root / contract_rel
            if not contract_path.exists():
                messages.append(f"[FAIL] {label}: metric_contract path does not exist: {contract_ref}")
                ok = False
            elif contract_rel not in contract_rel_paths:
                messages.append(f"[WARN] {label}: metric_contract exists but is outside experiments/baselines/** scan: {contract_ref}")
            else:
                messages.append(f"[PASS] {label}: metric_contract path exists")

        checkpoint = raw.get("checkpoint") if isinstance(raw.get("checkpoint"), dict) else {}
        checkpoint_required = _truthy(raw.get("checkpoint_required")) or _truthy(checkpoint.get("required"))
        checkpoint_status = str(raw.get("checkpoint_status") or checkpoint.get("status") or "").strip().lower()
        checkpoint_has_path = bool(str(raw.get("checkpoint_local_path") or checkpoint.get("local_path") or "").strip())
        checkpoint_verified = (
            _truthy(raw.get("checkpoint_verified_loadable"))
            or _truthy(checkpoint.get("verified_loadable"))
            or checkpoint_status in {"verified_loadable", "verified", "loaded", "已验证加载"}
        )
        checkpoint_not_applicable = checkpoint_status in {"not_applicable", "not applicable", "none", "no_checkpoint", "不适用", "无"}
        if (checkpoint_required or checkpoint_has_path) and not checkpoint_verified:
            messages.append(f"[FAIL] {label}: checkpoint is required/present but not verified loadable")
            ok = False
        elif checkpoint_required or checkpoint_has_path:
            messages.append(f"[PASS] {label}: checkpoint verified loadable")
        elif checkpoint_not_applicable:
            messages.append(f"[PASS] {label}: checkpoint marked not applicable")
        else:
            messages.append(f"[WARN] {label}: checkpoint applicability not declared")

        metric_ok, metric_msgs = _check_m3s02_metric_protocol_alignment(
            root,
            label,
            raw,
            protocols_by_id,
            eligible=eligible,
            primary="primary" in role,
        )
        messages.extend(metric_msgs)
        ok = ok and metric_ok

        deviation_ok, deviation_msgs = _check_m3s02_reference_deviation(
            root,
            label,
            raw,
            verdict=verdict,
            waiver=waiver,
            scope_limit=scope_limit,
            eligible=eligible,
            primary="primary" in role,
        )
        messages.extend(deviation_msgs)
        ok = ok and deviation_ok

        allowed_verdicts = {"verified_match", "verified_close"}
        if verdict in allowed_verdicts:
            messages.append(f"[PASS] {label}: verification_verdict={verdict}")
        elif verdict == "trusted_with_caveats":
            if not waiver or not scope_limit:
                messages.append(f"[FAIL] {label}: trusted_with_caveats requires caveat_waiver_reason and comparison_scope_limit")
                ok = False
            else:
                messages.append(f"[PASS] {label}: trusted_with_caveats has waiver and scope limit")
        else:
            messages.append(f"[FAIL] {label}: verification_verdict must be verified_match, verified_close, or justified trusted_with_caveats")
            ok = False

        if "primary" in role and not eligible:
            messages.append(f"[FAIL] {label}: primary baseline must set m3s03_eligible: true")
            ok = False

    if not seen_primary_ids:
        messages.append("[FAIL] M3S02: no primary baseline declared in baseline_lock.yaml")
        ok = False
    elif primary_eligible < 1:
        messages.append("[FAIL] M3S02: no primary baseline is eligible for M3S03")
        ok = False
    else:
        messages.append(f"[PASS] M3S02: {primary_eligible} primary baseline(s) eligible for M3S03")

    m3s03_contract = data.get("m3s03_contract")
    if not isinstance(m3s03_contract, dict):
        messages.append("[FAIL] M3S02: baseline_lock.yaml missing m3s03_contract mapping")
        ok = False
    else:
        for field in ("primary_baseline_id", "metric_contract", "dataset", "split", "metric"):
            if not str(m3s03_contract.get(field, "")).strip():
                messages.append(f"[FAIL] M3S02: m3s03_contract missing {field}")
                ok = False
            else:
                messages.append(f"[PASS] M3S02: m3s03_contract includes {field}")

    return ok, messages


def _load_m4_task_queue(root: Path) -> tuple[bool, list[str], list[dict[str, Any]]]:
    path = root / "experiments" / "configs" / "m4_task_queue.yaml"
    if not path.exists():
        return False, ["[FAIL] M4S02: experiments/configs/m4_task_queue.yaml not found"], []
    try:
        data = _load_yaml_mapping(path)
    except Exception as exc:
        return False, [f"[FAIL] M4S02: m4_task_queue.yaml unreadable: {exc}"], []
    tasks = data.get("tasks") or data.get("queue")
    if not isinstance(tasks, list) or not tasks:
        return False, ["[FAIL] M4S02: m4_task_queue.yaml missing nonempty tasks list"], []
    if not all(isinstance(task, dict) for task in tasks):
        return False, ["[FAIL] M4S02: every m4_task_queue task must be a mapping"], []
    return True, [f"[PASS] M4S02: m4_task_queue.yaml lists {len(tasks)} task(s)"], tasks


def _task_ana_id(task: dict[str, Any]) -> str:
    raw = str(task.get("task_id") or task.get("slice") or task.get("ana_id") or "").strip()
    match = re.search(r"\bAna-\d+\b", raw, flags=re.IGNORECASE)
    return match.group(0) if match else raw


def _task_baseline_required(task: dict[str, Any]) -> bool:
    value = task.get("baseline_required", task.get("baseline_inclusion", ""))
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"required", "true", "yes", "y", "1", "必须", "需要"}


def _check_m4s02_task_queue(root: Path, design_text: str) -> tuple[bool, list[str]]:
    ok, messages, tasks = _load_m4_task_queue(root)
    if not ok:
        return False, messages

    design_ids = set(re.findall(r"\bAna-\d+\b", design_text, flags=re.IGNORECASE))
    task_ids = {_task_ana_id(task) for task in tasks if _task_ana_id(task)}
    if len(task_ids) < 3:
        messages.append(f"[FAIL] M4S02: m4_task_queue has fewer than 3 Ana-* task ids ({len(task_ids)})")
        ok = False
    else:
        messages.append(f"[PASS] M4S02: m4_task_queue has {len(task_ids)} Ana-* task ids")

    missing = sorted(design_ids - task_ids)
    if missing:
        messages.append("[FAIL] M4S02: m4_task_queue missing design slice ids: " + ", ".join(missing))
        ok = False
    elif design_ids:
        messages.append("[PASS] M4S02: m4_task_queue.yaml covers all design Ana-* ids")

    for task in tasks:
        task_id = _task_ana_id(task) or "<missing>"
        label = f"M4S02 task_queue[{task_id}]"
        required = {
            "command": task.get("command"),
            "analysis_type": task.get("analysis_type"),
            "dependencies": task.get("dependencies", None),
            "resource_requirements": task.get("resource_requirements"),
            "expected_artifacts": task.get("expected_artifacts"),
            "success_criteria": task.get("success_criteria"),
        }
        for field, value in required.items():
            if field == "dependencies":
                missing_value = value is None
            else:
                missing_value = (
                    value is None
                    or (isinstance(value, str) and not value.strip())
                    or (isinstance(value, list) and not value)
                )
            if missing_value:
                messages.append(f"[FAIL] {label}: missing {field}")
                ok = False
            else:
                messages.append(f"[PASS] {label}: includes {field}")
        if not task.get("baseline_inclusion") and "baseline_required" not in task:
            messages.append(f"[FAIL] {label}: missing baseline_inclusion/baseline_required")
            ok = False
        elif _task_baseline_required(task) and not str(task.get("fairness_key", "")).strip():
            messages.append(f"[FAIL] {label}: baseline-required task missing fairness_key")
            ok = False
        else:
            messages.append(f"[PASS] {label}: baseline/fairness policy declared")

    return ok, messages


def _check_m4s03_task_queue_coverage(root: Path, analysis_lines: list[str]) -> tuple[bool, list[str]]:
    queue_ok, queue_msgs, tasks = _load_m4_task_queue(root)
    messages = [msg.replace("M4S02", "M4S03") for msg in queue_msgs]
    ok = queue_ok
    if not queue_ok:
        return False, messages
    try:
        import csv

        rows = list(csv.DictReader(analysis_lines, delimiter="\t"))
    except Exception as exc:
        return False, messages + [f"[FAIL] M4S03: analysis_results.tsv task coverage parse failed: {exc}"]

    if not rows:
        return False, messages + ["[FAIL] M4S03: analysis_results.tsv has no rows for task coverage"]

    slice_key = next((key for key in rows[0].keys() if str(key).strip().lower() == "slice"), "")
    method_key = next((key for key in rows[0].keys() if str(key).strip().lower() == "method"), "")
    if not slice_key or not method_key:
        return False, messages + ["[FAIL] M4S03: analysis_results.tsv missing slice/method columns for task coverage"]

    result_ids = {str(row.get(slice_key, "")).strip() for row in rows if str(row.get(slice_key, "")).strip()}
    task_ids = {_task_ana_id(task) for task in tasks if _task_ana_id(task)}
    missing = sorted(task_ids - result_ids)
    if missing:
        messages.append("[FAIL] M4S03: analysis_results.tsv missing task_queue slices: " + ", ".join(missing))
        ok = False
    else:
        messages.append("[PASS] M4S03: analysis_results.tsv covers all task_queue slices")

    for task in tasks:
        task_id = _task_ana_id(task)
        if not task_id or not _task_baseline_required(task):
            continue
        methods = {
            str(row.get(method_key, "")).strip().lower()
            for row in rows
            if str(row.get(slice_key, "")).strip() == task_id
        }
        if "baseline" not in methods:
            messages.append(f"[FAIL] M4S03: baseline-required slice {task_id} missing baseline row")
            ok = False
        elif not ({"ours", "proposed", "full", "full_model"} & methods):
            messages.append(f"[FAIL] M4S03: baseline-required slice {task_id} missing ours/proposed/full row")
            ok = False
        else:
            messages.append(f"[PASS] M4S03: baseline-required slice {task_id} has baseline and method rows")

    return ok, messages


def _contains_table_with_headers(text: str, headers: tuple[str, ...]) -> bool:
    """Heuristic check for a markdown table/list carrying all required headers."""
    lowered = text.lower()
    return all(header.lower() in lowered for header in headers)


def _load_m1_gap_ids(root: Path) -> set[str]:
    source_log = root / "knowledge" / "M1" / "M1_source_log.yaml"
    if not source_log.exists():
        return set()
    try:
        import yaml

        data = yaml.safe_load(source_log.read_text(encoding="utf-8")) or {}
    except Exception:
        return set()
    gap_map = data.get("gap_evidence_map", {}) or {}
    return {str(gap_id) for gap_id in gap_map.keys() if str(gap_id).strip()}


def _mentioned_m1_gap_ids(root: Path, text: str) -> set[str]:
    gap_ids = _load_m1_gap_ids(root)
    lowered = text.lower()
    return {gap_id for gap_id in gap_ids if gap_id.lower() in lowered}


def _check_m1_layer_terms(text: str, label: str) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True
    required = {
        "large direction problem": ("大方向", "large direction", "large", "big direction", "scenario", "场景", "领域"),
        "middle direction problem": ("中方向", "middle direction", "middle", "mid direction", "model", "metric", "模型", "指标", "精度"),
        "small direction problem": ("小方向", "small direction", "small", "micro", "component", "组件", "方法细节", "缺陷程度"),
    }
    for item, terms in required.items():
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] {label}: missing {item}")
            ok = False
        else:
            messages.append(f"[PASS] {label}: includes {item}")
    return ok, messages


def _check_m1s02_research_report(text: str) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True
    layer_ok, layer_msgs = _check_m1_layer_terms(text, "M1S02")
    messages.extend(layer_msgs)
    ok = ok and layer_ok
    required = {
        "search strategy / provenance": ("检索策略", "search strategy", "search provenance", "搜索日志"),
        "database or internet search source": ("数据库", "public_db", "internet", "web", "互联网", "文库"),
        "screening criteria": ("筛选", "screening", "inclusion", "exclusion", "纳入", "排除"),
        "perspective coverage ledger": ("perspective coverage", "视角覆盖", "scenario/task", "model/method", "metric/performance", "failure/limitation"),
        "research gap analysis": ("研究空白", "Research Gaps", "gap"),
        "evidence chain / argument": ("证据链", "论证", "evidence chain", "supporting sources", "source log"),
        "detailed research report": ("详细", "research report", "Detailed Research Report"),
    }
    for label, terms in required.items():
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] M1S02: missing {label}")
            ok = False
        else:
            messages.append(f"[PASS] M1S02: includes {label}")
    return ok, messages


def _check_m1s03_research_question(root: Path) -> tuple[bool, list[str]]:
    doc = root / "knowledge" / "M1" / "M1S03_research_question.md"
    if not doc.exists():
        return False, ["[FAIL] M1S03: M1S03_research_question.md not found"]
    text = doc.read_text(encoding="utf-8")
    messages: list[str] = []
    ok = True

    layer_ok, layer_msgs = _check_m1_layer_terms(text, "M1S03")
    messages.extend(layer_msgs)
    ok = ok and layer_ok

    required = {
        "gap-to-question derivation": ("从 Gap 到问题", "gap to question", "Gap", "GAP-"),
        "main research question": ("主问题", "research question", "研究问题"),
        "FINER feasibility": ("Feasible", "F**easible", "**F**", "FINER"),
        "FINER interesting": ("Interesting", "I**nteresting", "**I**"),
        "FINER novelty": ("Novel", "N**ovel", "**N**"),
        "FINER ethical": ("Ethical", "E**thical", "**E**"),
        "FINER relevance": ("Relevant", "R**elevant", "**R**"),
        "subquestion decomposition": ("子问题", "subquestion", "问题分解", "验证方式"),
        "innovation type": ("创新类型", "空白填补", "架构改进", "验证深化", "innovation type"),
        "scope boundary": ("范围界定", "包含", "排除", "scope"),
    }
    for label, terms in required.items():
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] M1S03: missing {label}")
            ok = False
        else:
            messages.append(f"[PASS] M1S03: includes {label}")

    mentioned = _mentioned_m1_gap_ids(root, text)
    if not mentioned:
        messages.append("[FAIL] M1S03: does not cite any gap ID from M1_source_log.yaml")
        ok = False
    else:
        messages.append(f"[PASS] M1S03: cites source-log gap IDs: {', '.join(sorted(mentioned))}")
    return ok, messages


def _check_m1s04_hypothesis(root: Path) -> tuple[bool, list[str]]:
    doc = root / "knowledge" / "M1" / "M1S04_hypothesis_generation.md"
    if not doc.exists():
        return False, ["[FAIL] M1S04: M1S04_hypothesis_generation.md not found"]
    text = doc.read_text(encoding="utf-8")
    messages: list[str] = []
    ok = True
    required = {
        "core hypothesis": ("核心假设", "Hypothesis", "H1"),
        "measurable prediction": ("可测量预测", "prediction", "预测"),
        "measurement metric": ("测量指标", "metric", "指标"),
        "experiment design link": ("实验设计", "experiment design"),
        "null hypothesis": ("零假设", "H0", "null hypothesis"),
        "gap-question-hypothesis mapping": ("Gap", "问题", "假设", "预测", "Gap-Question", "GAP-"),
    }
    for label, terms in required.items():
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] M1S04: missing {label}")
            ok = False
        else:
            messages.append(f"[PASS] M1S04: includes {label}")
    mentioned = _mentioned_m1_gap_ids(root, text)
    if not mentioned:
        messages.append("[FAIL] M1S04: does not cite any gap ID from M1_source_log.yaml")
        ok = False
    else:
        messages.append(f"[PASS] M1S04: cites source-log gap IDs: {', '.join(sorted(mentioned))}")
    return ok, messages


def _check_m1s05_novelty_feasibility(root: Path) -> tuple[bool, list[str]]:
    doc = root / "knowledge" / "M1" / "M1S05_novelty_feasibility.md"
    if not doc.exists():
        return False, ["[FAIL] M1S05: M1S05_novelty_feasibility.md not found"]
    text = doc.read_text(encoding="utf-8")
    messages: list[str] = []
    ok = True

    layer_ok, layer_msgs = _check_m1_layer_terms(text, "M1S05")
    messages.extend(layer_msgs)
    ok = ok and layer_ok

    required = {
        "novelty assessment": ("新颖性评估", "novelty", "问题新颖性", "方法新颖性"),
        "literature comparison": ("文献对比", "已有工作", "本研究", "差异"),
        "source-backed evidence": ("证据", "Source", "src", "GAP-"),
        "feasibility analysis": ("可行性", "技术可行性", "数据可行性", "计算资源", "feasibility"),
        "risk mitigation": ("风险", "缓解", "mitigation"),
        "final proceed decision": ("PROCEED", "建议", "最终判断"),
    }
    for label, terms in required.items():
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] M1S05: missing {label}")
            ok = False
        else:
            messages.append(f"[PASS] M1S05: includes {label}")

    mentioned = _mentioned_m1_gap_ids(root, text)
    if not mentioned:
        messages.append("[FAIL] M1S05: does not cite any gap ID from M1_source_log.yaml")
        ok = False
    else:
        messages.append(f"[PASS] M1S05: cites source-log gap IDs: {', '.join(sorted(mentioned))}")

    handoff = root / "knowledge" / "handoff_M1_M2.md"
    if not handoff.exists():
        messages.append("[FAIL] M1S05: handoff_M1_M2.md not found")
        ok = False
    else:
        handoff_text = handoff.read_text(encoding="utf-8")
        if not _contains_any(handoff_text, ("Gap", "GAP-", "hypothesis", "假设", "research question", "研究问题")):
            messages.append("[FAIL] M1S05: handoff_M1_M2.md missing gap/hypothesis handoff content")
            ok = False
        else:
            messages.append("[PASS] M1S05: handoff_M1_M2.md contains gap/hypothesis handoff")
    return ok, messages


def _check_m2s05_experiment_design(root: Path, text: str) -> tuple[bool, list[str]]:
    """Validate M2S05 experiment setup against the user's requirements."""
    messages: list[str] = []
    ok = True

    required_signals = {
        "dataset selection": ("数据集", "dataset"),
        "dataset acquisition": ("下载方式", "获取方式", "download", "checksum", "校验"),
        "baseline methods": ("基线", "baseline"),
        "evaluation metrics": ("指标", "metric"),
        "related-work protocol reference": ("相关工作实验设置", "related work experiment", "reference protocol", "参考论文"),
        "per-experiment purpose/hypothesis": ("目的", "purpose", "目标假设", "实验目标"),
        "fairness constraints": ("相同的数据划分", "same split", "公平", "fairness", "相同的评估指标"),
        "fixed seed": ("随机种子", "seed", "42"),
        "single-run validation": ("单次", "fixed seed", "seed=42", "42"),
        "reproducibility checklist": ("可复现", "reproducibility", "requirements", "git commit"),
    }
    for label, terms in required_signals.items():
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] M2S05: missing {label}")
            ok = False
        else:
            messages.append(f"[PASS] M2S05: includes {label}")

    if not re.search(r"(?i)(?:seed|随机种子)[^\n]{0,80}\b42\b|\b42\b[^\n]{0,80}(?:seed|随机种子)", text):
        messages.append("[FAIL] M2S05: experiment design must fix random seed to 42")
        ok = False
    else:
        messages.append("[PASS] M2S05: random seed fixed to 42")

    if not _contains_table_with_headers(text, ("数据集", "规模", "选择理由", "获取方式", "许可证")):
        messages.append("[FAIL] M2S05: dataset table missing dataset/size/reason/acquisition/license fields")
        ok = False
    else:
        messages.append("[PASS] M2S05: dataset table fields present")

    if not _contains_table_with_headers(text, ("实验 ID", "目的", "目标假设", "对照组", "指标")):
        messages.append("[FAIL] M2S05: experiment target table missing id/purpose/hypothesis/baseline/metric fields")
        ok = False
    else:
        messages.append("[PASS] M2S05: experiment target table fields present")

    exp_count = _count_exp_ids(text)
    if exp_count < 3:
        messages.append(f"[FAIL] M2S05: fewer than 3 experiment IDs found ({exp_count})")
        ok = False
    else:
        messages.append(f"[PASS] M2S05: {exp_count} experiment IDs found")

    registry_ok, registry_msgs, _protocols = _load_m2_metric_protocol_registry(root)
    messages.extend(f"[{msg.split('] ', 1)[0].lstrip('[')}] M2S05: {msg.split('] ', 1)[1]}" if msg.startswith("[") and "] " in msg else msg for msg in registry_msgs)
    ok = ok and registry_ok

    return ok, messages


def _check_m2s06_experiment_plan(root: Path, text: str) -> tuple[bool, list[str]]:
    """Validate M2S06 full experiment plan/report blueprint."""
    messages: list[str] = []
    ok = True

    exp_count = _count_exp_ids(text)
    if exp_count < 3:
        messages.append(f"[FAIL] M2S06: fewer than 3 experiment IDs found ({exp_count})")
        ok = False
    else:
        messages.append(f"[PASS] M2S06: {exp_count} experiment IDs found")

    required_signals = {
        "execution order": ("执行顺序", "Phase", "phase", "依赖"),
        "branch/backtrack logic": ("BACKTRACK", "回溯", "失败判定", "诊断"),
        "success criteria": ("成功标准", "success criteria", "显著优于"),
        "risk control": ("风险", "risk", "应对"),
        "resource budget": ("资源", "GPU", "storage", "时间预算", "预算"),
        "full experiment report blueprint": ("完整实验报告蓝图", "experiment report blueprint"),
        "related-work protocol per experiment": ("参考相关工作实验设置", "reference protocol", "论文"),
        "dataset/split per experiment": ("数据集与划分", "dataset", "split"),
        "baseline/control per experiment": ("Baselines", "baseline", "对照组"),
        "metric per experiment": ("评价指标", "metric"),
        "run protocol per experiment": ("运行协议", "seed", "epoch", "hardware", "超参"),
        "required evidence": ("raw logs", "config", "checkpoint", "results.tsv", "plot script"),
        "failure diagnosis": ("失败时诊断路径", "implementation", "design", "hypothesis", "data", "baseline"),
    }
    for label, terms in required_signals.items():
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] M2S06: missing {label}")
            ok = False
        else:
            messages.append(f"[PASS] M2S06: includes {label}")

    if not re.search(r"(?i)(?:seed|随机种子)[^\n]{0,80}\b42\b|\b42\b[^\n]{0,80}(?:seed|随机种子)", text):
        messages.append("[FAIL] M2S06: full experiment plan must fix random seed to 42")
        ok = False
    else:
        messages.append("[PASS] M2S06: random seed fixed to 42")

    if not _contains_table_with_headers(text, ("实验 ID", "目的", "预估时间", "依赖", "优先级")):
        messages.append("[FAIL] M2S06: plan overview table missing id/purpose/time/dependency/priority fields")
        ok = False
    else:
        messages.append("[PASS] M2S06: plan overview table fields present")

    if not re.search(r"(?im)^#{2,4}\s*Exp-\[?N\]?|^#{2,4}\s*Exp-[A-Za-z0-9_-]+", text):
        messages.append("[FAIL] M2S06: report blueprint missing per-experiment Exp-* subsection")
        ok = False
    else:
        messages.append("[PASS] M2S06: report blueprint has per-experiment subsection")

    registry_ok, registry_msgs, protocols = _load_m2_metric_protocol_registry(root)
    messages.extend(f"[{msg.split('] ', 1)[0].lstrip('[')}] M2S06 upstream: {msg.split('] ', 1)[1]}" if msg.startswith("[") and "] " in msg else msg for msg in registry_msgs)
    ok = ok and registry_ok
    if protocols:
        if "metric_protocol_id" not in text and "指标协议" not in text:
            messages.append("[FAIL] M2S06: plan must reference metric_protocol_id from M2S05")
            ok = False
        else:
            messages.append("[PASS] M2S06: plan references metric protocol IDs")
        for protocol_id in protocols:
            if protocol_id not in text:
                messages.append(f"[FAIL] M2S06: missing metric protocol reference {protocol_id}")
                ok = False
            else:
                messages.append(f"[PASS] M2S06: references metric protocol {protocol_id}")

    return ok, messages


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _primary_metric_mapping(data: Any) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    primary = data.get("primary_metric")
    if isinstance(primary, dict):
        return primary
    metrics = data.get("metrics")
    if isinstance(metrics, dict) and isinstance(metrics.get("primary"), dict):
        return metrics["primary"]
    return None


def _check_m3s04_result_validation(root: Path) -> tuple[bool, list[str]]:
    """Validate M3S04 result validation and the evidence package needed by M4."""
    doc = root / "knowledge" / "M3" / "M3S04_result_validation.md"
    messages: list[str] = []
    ok = True

    if not doc.exists():
        return False, ["[FAIL] M3S04: M3S04_result_validation.md not found"]

    text = doc.read_text(encoding="utf-8")
    decision = extract_m3s04_decision(text)
    if decision is None:
        messages.append("[FAIL] M3S04: Missing explicit KEEP/FIX/BACKTRACK decision")
        ok = False
    else:
        messages.append(f"[PASS] M3S04: Decision found: {decision}")

    required_sections = {
        "experiment stop reason": ("实验停止原因", "停止条件", "stop reason", "Evidence Ladder", "best 指标"),
        "data quality checks": ("数据质量", "过拟合", "数据泄露", "训练稳定性", "可复现", "data quality"),
        "single-seed validation": ("seed", "42", "固定种子", "单次运行", "single"),
        "hypothesis mapping": ("与假设的对应验证", "假设", "预期结果", "实际结果", "支持程度", "hypothesis"),
        "root-cause analysis": ("潜在问题", "根因", "critical", "major", "minor", "root cause"),
        "negative result handling": ("负面结果", "negative result", "failure"),
        "evidence artifact packaging": (
            "Evidence Artifact",
            "Artifact 清单",
            "manifest.yaml",
            "metric_contract.yaml",
            "comparison_table",
        ),
        "limitations": ("已知限制", "局限性", "limitation"),
        "downstream handoff content": ("传递给下游", "M4", "分析方向", "handoff"),
    }
    for label, terms in required_sections.items():
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] M3S04: missing {label}")
            ok = False
        else:
            messages.append(f"[PASS] M3S04: includes {label}")

    if decision in {"FIX", "BACKTRACK"}:
        missing_fields = _missing_structured_fields(text)
        has_guidance = bool(
            re.search(r"(?im)^\s*#{1,6}\s*回溯修改方向\b", text)
            or re.search(r"(?im)^\s*#{1,6}\s*修改方向/建议\b", text)
            or "回溯修改方向" in text
        )
        if not has_guidance:
            messages.append("[FAIL] M3S04: FIX/BACKTRACK decision missing '回溯修改方向' section")
            ok = False
        else:
            messages.append("[PASS] M3S04: backtrack guidance section found")
        if missing_fields:
            messages.append(
                f"[FAIL] M3S04: FIX/BACKTRACK decision missing repair advice fields: {', '.join(missing_fields)}"
            )
            ok = False
        else:
            messages.append("[PASS] M3S04: repair advice fields found")
        messages.append("[FAIL] M3S04: FIX/BACKTRACK decision blocks advancement until the requested rerun is executed")
        return False, messages

    if decision != "KEEP":
        return False, messages

    trained_ok, trained_msgs = _check_m3s03_trained_weight_evidence(root, doc_text=text)
    messages.extend(trained_msgs)
    ok = ok and trained_ok

    artifact_dir = root / "experiments" / "artifacts" / "main_experiment"
    required_files = {
        "manifest": artifact_dir / "manifest.yaml",
        "metric contract": artifact_dir / "metric_contract.yaml",
        "comparison table": artifact_dir / "comparison_table.csv",
        "reproduction guide": artifact_dir / "reproduction.md",
    }
    for label, path in required_files.items():
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            messages.append(f"[FAIL] M3S04: {label} missing or empty: {path.relative_to(root)}")
            ok = False
        else:
            messages.append(f"[PASS] M3S04: {label} artifact present")

    manifest_path = required_files["manifest"]
    if manifest_path.exists():
        try:
            import yaml

            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            messages.append(f"[FAIL] M3S04: manifest.yaml unreadable: {exc}")
            ok = False
            manifest = {}
        if not isinstance(manifest, dict):
            messages.append("[FAIL] M3S04: manifest.yaml must contain a mapping")
            ok = False
            manifest = {}
        for field in ("experiment_id", "method", "dataset", "environment"):
            if not _nonempty(manifest.get(field)):
                messages.append(f"[FAIL] M3S04: manifest.yaml missing {field}")
                ok = False
            else:
                messages.append(f"[PASS] M3S04: manifest.yaml includes {field}")
        baseline_refs = manifest.get("baseline_refs")
        if not isinstance(baseline_refs, list) or not any(_nonempty(item) for item in baseline_refs):
            messages.append("[FAIL] M3S04: manifest.yaml missing non-empty baseline_refs")
            ok = False
        else:
            messages.append("[PASS] M3S04: manifest.yaml includes baseline_refs")
        primary = _primary_metric_mapping(manifest)
        if not primary:
            messages.append("[FAIL] M3S04: manifest.yaml missing primary_metric")
            ok = False
        else:
            missing_metric = [field for field in ("key", "value") if not _nonempty(primary.get(field))]
            if missing_metric:
                messages.append(f"[FAIL] M3S04: manifest.yaml primary_metric missing {', '.join(missing_metric)}")
                ok = False
            else:
                messages.append("[PASS] M3S04: manifest.yaml primary_metric includes key/value")
        seeds = manifest.get("seeds")
        seed_value = manifest.get("seed")
        seed_values = set()
        if isinstance(seeds, list):
            seed_values.update(str(seed).strip() for seed in seeds if _nonempty(seed))
        if _nonempty(seed_value):
            seed_values.add(str(seed_value).strip())
        if "42" not in seed_values:
            messages.append("[FAIL] M3S04: manifest.yaml must record fixed seed 42")
            ok = False
        else:
            messages.append("[PASS] M3S04: manifest.yaml records fixed seed 42")

    contract_path = required_files["metric contract"]
    if contract_path.exists():
        try:
            import yaml

            contract = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            messages.append(f"[FAIL] M3S04: metric_contract.yaml unreadable: {exc}")
            ok = False
            contract = {}
        if not isinstance(contract, dict):
            messages.append("[FAIL] M3S04: metric_contract.yaml must contain a mapping")
            ok = False
            contract = {}
        method = contract.get("method") or contract.get("method_name") or contract.get("system")
        if not _nonempty(method):
            messages.append("[FAIL] M3S04: metric_contract.yaml missing method")
            ok = False
        else:
            messages.append("[PASS] M3S04: metric_contract.yaml includes method")
        primary = _primary_metric_mapping(contract)
        if not primary:
            messages.append("[FAIL] M3S04: metric_contract.yaml missing primary metric")
            ok = False
        else:
            missing_metric = [field for field in ("key", "value") if not _nonempty(primary.get(field))]
            if missing_metric:
                messages.append(f"[FAIL] M3S04: metric_contract.yaml primary metric missing {', '.join(missing_metric)}")
                ok = False
            else:
                messages.append("[PASS] M3S04: metric_contract.yaml primary metric includes key/value")

    comparison_path = required_files["comparison table"]
    if comparison_path.exists():
        try:
            import csv

            rows = list(csv.DictReader(comparison_path.read_text(encoding="utf-8").splitlines()))
        except Exception as exc:
            messages.append(f"[FAIL] M3S04: comparison_table.csv unreadable: {exc}")
            ok = False
            rows = []
        if not rows:
            messages.append("[FAIL] M3S04: comparison_table.csv has no data rows")
            ok = False
        else:
            messages.append("[PASS] M3S04: comparison_table.csv has data rows")
            joined = json.dumps(rows, ensure_ascii=False).lower()
            if "baseline" not in joined:
                messages.append("[FAIL] M3S04: comparison_table.csv missing baseline rows")
                ok = False
            else:
                messages.append("[PASS] M3S04: comparison_table.csv includes baseline rows")
            if "ours" not in joined and "proposed" not in joined:
                messages.append("[FAIL] M3S04: comparison_table.csv missing ours/proposed row")
                ok = False
            else:
                messages.append("[PASS] M3S04: comparison_table.csv includes ours/proposed row")
            headers = {str(header).lower() for header in rows[0].keys()}
            if "seed" not in headers:
                messages.append("[FAIL] M3S04: comparison_table.csv missing fixed seed column")
                ok = False
            else:
                seed_key = next((key for key in rows[0].keys() if str(key).lower() == "seed"), "seed")
                has_seed_42 = any(str(row.get(seed_key, "")).strip() == "42" for row in rows)
                if not has_seed_42:
                    messages.append("[FAIL] M3S04: comparison_table.csv must record fixed seed 42")
                    ok = False
                else:
                    messages.append("[PASS] M3S04: comparison_table.csv records fixed seed 42")

    handoff = root / "knowledge" / "handoff_M3_M4.md"
    if not handoff.exists() or not handoff.read_text(encoding="utf-8").strip():
        messages.append("[FAIL] M3S04: handoff_M3_M4.md missing or empty")
        ok = False
    else:
        handoff_text = handoff.read_text(encoding="utf-8")
        handoff_terms = {
            "KEEP decision": ("KEEP", "validated", "验证通过"),
            "claim/evidence bridge": ("claim", "evidence", "证据", "主张"),
            "M3S04 provenance": ("M3S04", "result validation"),
            "artifact path": ("experiments/artifacts/main_experiment", "manifest.yaml", "comparison_table.csv"),
            "M4 analysis direction": ("M4", "analysis", "消融", "鲁棒", "机制"),
        }
        for label, terms in handoff_terms.items():
            if not _contains_any(handoff_text, terms):
                messages.append(f"[FAIL] M3S04: handoff_M3_M4.md missing {label}")
                ok = False
            else:
                messages.append(f"[PASS] M3S04: handoff_M3_M4.md includes {label}")

    return ok, messages


def _extract_latex_cite_keys(tex_text: str) -> set[str]:
    keys: set[str] = set()
    pattern = (
        r"\\(?:cite|citep|citet|citealt|citeauthor|citeyear|parencite|textcite|autocite)"
        r"\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}"
    )
    for match in re.finditer(pattern, tex_text):
        keys.update(key.strip() for key in match.group(1).split(",") if key.strip())
    return keys


def _extract_bib_keys(bib_text: str) -> set[str]:
    return {
        match.group(1).strip()
        for match in re.finditer(r"(?im)^\s*@\w+\s*\{\s*([^,\s]+)", bib_text)
        if match.group(1).strip()
    }


def _extract_includegraphics_paths(tex_text: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex_text)
        if match.group(1).strip()
    ]


def _latex_asset_exists(root: Path, graphic_path: str) -> bool:
    clean = graphic_path.strip().replace("\\", "/")
    if clean.startswith("artifacts/"):
        base = root / clean
    else:
        base = root / "artifacts" / clean
    if base.exists():
        return True
    if base.suffix:
        return False
    return any(base.with_suffix(ext).exists() for ext in (".pdf", ".png", ".jpg", ".jpeg", ".eps"))


def _report_matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL) for pattern in patterns)


def _check_m5s08_final_compilation(root: Path) -> tuple[bool, list[str]]:
    """Validate that M5S08 assembled a real paper package, not placeholder files."""
    artifacts = root / "artifacts"
    pdf = artifacts / "paper.pdf"
    tex = artifacts / "paper.tex"
    refs = artifacts / "refs.bib"
    report = root / "knowledge" / "M5" / "M5S08_final_compilation.md"
    messages: list[str] = []
    ok = True

    if not pdf.exists():
        messages.append("[FAIL] M5S08: artifacts/paper.pdf not found")
        ok = False
    else:
        pdf_bytes = pdf.read_bytes()
        if not pdf_bytes:
            messages.append("[FAIL] M5S08: artifacts/paper.pdf is empty")
            ok = False
        elif not pdf_bytes.startswith(b"%PDF"):
            messages.append("[FAIL] M5S08: artifacts/paper.pdf does not look like a PDF")
            ok = False
        else:
            messages.append("[PASS] M5S08: paper.pdf exists and has PDF header")

    tex_text = ""
    if not tex.exists():
        messages.append("[FAIL] M5S08: artifacts/paper.tex not found")
        ok = False
    else:
        tex_text = tex.read_text(encoding="utf-8")
        if len(tex_text.strip()) < 800:
            messages.append("[FAIL] M5S08: paper.tex is too short for a complete draft")
            ok = False
        else:
            messages.append("[PASS] M5S08: paper.tex has substantive length")
        placeholder_patterns = (
            r"\bTODO\b",
            r"\bTBD\b",
            r"\[INSERT[^\]]*\]",
            r"lorem\s+ipsum",
            r"\?\?\?",
            r"待补充",
            r"占位",
            r"placeholder",
        )
        placeholders = [pattern for pattern in placeholder_patterns if re.search(pattern, tex_text, re.IGNORECASE)]
        if placeholders:
            messages.append("[FAIL] M5S08: paper.tex contains placeholder text")
            ok = False
        else:
            messages.append("[PASS] M5S08: paper.tex has no obvious placeholders")
        required_tex_signals = {
            "LaTeX document wrapper": ("\\documentclass", "\\begin{document}", "\\end{document}"),
            "abstract": ("\\begin{abstract}", "\\abstract", "Abstract"),
            "introduction": ("\\section{Introduction}", "\\section*{Introduction}", "Introduction"),
            "related work": ("Related Work", "related work"),
            "method section": ("Method", "Methodology", "方法"),
            "experiment/results section": ("Experiment", "Results", "实验", "结果"),
            "analysis/discussion section": ("Analysis", "Discussion", "分析", "讨论"),
            "conclusion": ("Conclusion", "结论"),
            "bibliography command": ("\\bibliography", "\\printbibliography", "\\addbibresource"),
        }
        for label, terms in required_tex_signals.items():
            if not _contains_any(tex_text, terms):
                messages.append(f"[FAIL] M5S08: paper.tex missing {label}")
                ok = False
            else:
                messages.append(f"[PASS] M5S08: paper.tex includes {label}")

        graphics = _extract_includegraphics_paths(tex_text)
        if not graphics:
            messages.append("[FAIL] M5S08: paper.tex has no included figure assets")
            ok = False
        else:
            missing_graphics = [path for path in graphics if not _latex_asset_exists(root, path)]
            if missing_graphics:
                messages.append(f"[FAIL] M5S08: missing included figure assets: {', '.join(missing_graphics)}")
                ok = False
            else:
                messages.append(f"[PASS] M5S08: {len(graphics)} included figure asset(s) exist")
        figure_table_signals = {
            "figure label/reference": ("\\label{fig:", "\\ref{fig:", "Figure~\\ref"),
            "table label/reference": ("\\label{tab:", "\\ref{tab:", "Table~\\ref"),
            "booktabs table style": ("\\toprule", "\\midrule", "\\bottomrule"),
        }
        for label, terms in figure_table_signals.items():
            if not _contains_any(tex_text, terms):
                messages.append(f"[FAIL] M5S08: paper.tex missing {label}")
                ok = False
            else:
                messages.append(f"[PASS] M5S08: paper.tex includes {label}")

    if not refs.exists() or not refs.read_text(encoding="utf-8").strip():
        messages.append("[FAIL] M5S08: artifacts/refs.bib missing or empty")
        ok = False
    elif tex_text:
        cite_keys = _extract_latex_cite_keys(tex_text)
        bib_keys = _extract_bib_keys(refs.read_text(encoding="utf-8"))
        if not cite_keys:
            messages.append("[FAIL] M5S08: paper.tex has no citations")
            ok = False
        else:
            messages.append(f"[PASS] M5S08: paper.tex cites {len(cite_keys)} key(s)")
        orphan = sorted(cite_keys - bib_keys)
        if orphan:
            messages.append(f"[FAIL] M5S08: orphan citation keys: {', '.join(orphan)}")
            ok = False
        else:
            messages.append("[PASS] M5S08: orphan citation gate passed")

    if not report.exists():
        messages.append("[FAIL] M5S08: knowledge/M5/M5S08_final_compilation.md missing")
        ok = False
    else:
        report_text = report.read_text(encoding="utf-8")
        report_checks = {
            "compile PASS verdict": (
                r"^\s*(?:final\s+)?verdict\s*[:：]\s*PASS\b",
                r"编译状态\s*[:：]\s*(?:成功|PASS)",
            ),
            "pdflatex command record": (r"pdflatex",),
            "bibtex/biber command record": (r"\b(?:bibtex|biber)\b",),
            "zero fatal errors": (r"fatal errors?\s*[:：]\s*0\b", r"Fatal Errors\s*[:：]\s*0\b"),
            "zero undefined references": (r"undefined refs?(?:erences?)?\s*[:：]\s*0\b", r"未定义引用\s*[:：]\s*0\b"),
            "zero undefined citations": (r"undefined citations?\s*[:：]\s*0\b", r"未定义 citations\s*[:：]\s*0\b"),
            "orphan cite gate pass": (
                r"orphan cites?\s*[:：]\s*(?:0|\[\]|none|无)\b",
                r"Orphan Cite Gate.{0,80}(?:PASS|通过)",
            ),
            "anti-leakage pass": (r"Anti[- ]Leakage.{0,80}(?:PASS|passed|通过)", r"泄露.{0,80}(?:通过|0)"),
            "page count": (r"(?:PDF\s+)?(?:page count|pages|页数)\s*[:：]\s*\d+",),
            "style/layout compliance": (r"style\s*&\s*layout", r"style/layout", r"风格", r"排版"),
            "figure compliance": (r"figure compliance", r"图像", r"图表", r"generated-images", r"绘图脚本"),
            "venue style compliance": (r"figure style profile", r"style preset", r"venue preset", r"palette", r"visual richness"),
            "final artifact list": (r"artifacts/paper\.tex", r"artifacts/paper\.pdf"),
        }
        for label, patterns in report_checks.items():
            if not _report_matches_any(report_text, patterns):
                messages.append(f"[FAIL] M5S08: final compilation report missing {label}")
                ok = False
            else:
                messages.append(f"[PASS] M5S08: final compilation report includes {label}")

    return ok, messages


def _analysis_type_coverage(text: str) -> set[str]:
    lowered = text.lower()
    groups = {
        "ablation": ("ablation", "消融"),
        "mechanism": ("mechanism", "机制", "visualization", "可视化", "probe", "attribution"),
        "robustness": ("robust", "鲁棒", "stress", "noise", "shift", "泛化"),
        "efficiency": (
            "efficiency",
            "效率",
            "runtime",
            "latency",
            "throughput",
            "flops",
            "macs",
            "params",
            "参数量",
            "推理时间",
            "训练时间",
            "显存",
            "峰值内存",
        ),
        "failure": ("failure", "negative", "失败", "负面", "边界"),
    }
    return {name for name, terms in groups.items() if any(term in lowered for term in terms)}


def _m4_efficiency_decision(text: str) -> tuple[bool, bool, bool]:
    """Return (decision_present, required, waived_or_not_required)."""
    lowered = text.lower()
    decision_present = (
        "efficiency_required" in lowered
        or "efficiency waiver" in lowered
        or "efficiency_waiver" in lowered
        or "效率触发" in text
        or "效率豁免" in text
        or "效率分析" in text
    )
    required = bool(
        re.search(r"efficiency_required\s*[:：]\s*(yes|required|true|1)\b", lowered)
        or re.search(r"efficiency_required\s*[:：]\s*(?:是|需要|必须)", text)
        or re.search(r"效率分析.{0,20}(?:required|yes|需要|必须)", text, flags=re.IGNORECASE)
    )
    waived = bool(
        re.search(r"efficiency_required\s*[:：]\s*(no|false|0|waived|not_required)\b", lowered)
        or re.search(r"efficiency_required\s*[:：]\s*(?:否|不需要|豁免)", text)
        or "efficiency_waiver" in lowered
        or "efficiency waiver" in lowered
        or "效率豁免" in text
    )
    return decision_present, required, waived


def _m4_efficiency_metrics_present(text: str) -> bool:
    return _contains_any(
        text,
        (
            "params_m",
            "parameters",
            "参数量",
            "flops",
            "macs",
            "train_time_sec",
            "training time",
            "训练时间",
            "inference_latency_ms",
            "latency",
            "推理时间",
            "throughput",
            "吞吐",
            "peak_mem_mb",
            "memory",
            "显存",
        ),
    )


def _m4_efficiency_slice_present(text: str) -> bool:
    lowered = text.lower()
    return bool(
        re.search(r"analysis_type\s*[:=：]\s*efficiency\b", lowered)
        or re.search(r"analysis_type\s*[:=：].{0,30}效率", text, flags=re.IGNORECASE)
        or re.search(r"slice\s*:\s*ana-\d+.{0,120}efficiency", lowered, flags=re.DOTALL)
    )


def _m4_component_claim_matrix_present(text: str) -> bool:
    return _contains_any(
        text,
        (
            "component claim analysis matrix",
            "component_claim_analysis_matrix",
            "component / claim",
            "component/claim",
            "组件/claim",
            "组件 claim",
            "组件/Claim",
            "组件/主张",
        ),
    )


def _m4_paper_protocol_present(text: str) -> bool:
    return _contains_any(
        text,
        (
            "paper protocol adaptation",
            "paper_protocol_adaptation",
            "protocol adaptation",
            "reference_paper",
            "source_id",
            "task_setup",
            "baseline_protocol",
            "adoption_decision",
            "论文协议适配",
            "高水平论文",
        ),
    )


def _find_m4_artifact_dir(root: Path) -> Path | None:
    for rel in (
        "experiments/artifacts/analysis_experiment",
        "experiments/artifacts/deep_analysis",
        "experiments/artifacts/m4_analysis",
    ):
        path = root / rel
        if path.exists():
            return path
    return None


def _check_m4s04_analysis_results(root: Path) -> tuple[bool, list[str]]:
    """Validate M4 analysis integration against the how/where/why evidence contract."""
    doc = root / "knowledge" / "M4" / "M4S04_analysis_results.md"
    handoff = root / "knowledge" / "handoff_M4_M5.md"
    results = root / "experiments" / "analysis_results.tsv"
    messages: list[str] = []
    ok = True

    if not doc.exists():
        messages.append("[FAIL] M4S04: M4S04_analysis_results.md not found")
        return False, messages

    text = doc.read_text(encoding="utf-8")
    required_sections = {
        "statistical analysis": ("统计分析", "p-value", "效应量", "置信区间", "statistical"),
        "Claim Ledger": ("Claim Ledger", "Claim ID", "Status"),
        "insight articulation": ("洞察提炼", "Insight", "So what"),
        "limitations": ("局限性", "limitation"),
        "evidence usability": ("证据可用性", "usable", "weak", "unusable", "removed"),
        "M4 to M5 handoff section": ("M4→M5", "M4->M5", "Handoff", "交接"),
        "how/where/why explanation": ("how", "where", "why", "怎么", "哪里", "为什么"),
        "baseline-aware comparison": ("baseline", "基线", "对照"),
        "literature/design basis": ("literature_basis", "文献", "参考", "M2"),
        "visualization/provenance": ("visualization", "可视化", "figure", "图表", "plot", "图像"),
        "efficiency decision": ("efficiency_required", "efficiency", "效率分析", "效率豁免"),
        "paper protocol adaptation": ("paper_protocol_adaptation", "Paper Protocol", "论文协议适配", "reference_paper", "source_id"),
    }
    for label, terms in required_sections.items():
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] M4S04: missing {label}")
            ok = False
        else:
            messages.append(f"[PASS] M4S04: includes {label}")

    coverage = _analysis_type_coverage(text)
    required_coverage = {"ablation", "mechanism", "robustness", "failure"}
    missing_coverage = sorted(required_coverage - coverage)
    if missing_coverage:
        messages.append("[FAIL] M4S04: missing analysis coverage: " + ", ".join(missing_coverage))
        ok = False
    else:
        messages.append("[PASS] M4S04: covers ablation/mechanism/robustness/failure")

    if not _m4_component_claim_matrix_present(text):
        messages.append("[FAIL] M4S04: component/claim analysis matrix missing")
        ok = False
    else:
        messages.append("[PASS] M4S04: component/claim analysis matrix present")
    if not _m4_paper_protocol_present(text):
        messages.append("[FAIL] M4S04: paper protocol adaptation summary missing")
        ok = False
    else:
        messages.append("[PASS] M4S04: paper protocol adaptation summary present")
    efficiency_decision, efficiency_required, efficiency_waived = _m4_efficiency_decision(text)
    if not efficiency_decision:
        messages.append("[FAIL] M4S04: efficiency_required decision or waiver missing")
        ok = False
    elif efficiency_required:
        if "efficiency" not in coverage:
            messages.append("[FAIL] M4S04: efficiency_required=yes but efficiency evidence missing")
            ok = False
        else:
            messages.append("[PASS] M4S04: efficiency evidence present")
        if not _m4_efficiency_metrics_present(text):
            messages.append("[FAIL] M4S04: efficiency_required=yes but efficiency metrics missing")
            ok = False
        else:
            messages.append("[PASS] M4S04: efficiency metrics present")
    elif efficiency_waived:
        messages.append("[PASS] M4S04: efficiency analysis explicitly waived/not required")
    else:
        messages.append("[PASS] M4S04: efficiency analysis decision present")

    problematic_claims = []
    for line in text.splitlines():
        lowered = line.lower()
        if ("unsupported" in lowered or "deferred" in lowered or "unusable" in lowered) and "main_text" in lowered:
            problematic_claims.append(line.strip())
    if problematic_claims:
        messages.append("[FAIL] M4S04: unsupported/deferred/unusable evidence assigned to main_text")
        ok = False
    else:
        messages.append("[PASS] M4S04: unsupported/deferred/unusable evidence is not assigned to main_text")

    if not results.exists():
        messages.append("[FAIL] M4S04: experiments/analysis_results.tsv not found")
        ok = False
    else:
        lines = [line for line in results.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(lines) < 2:
            messages.append("[FAIL] M4S04: experiments/analysis_results.tsv has no data rows")
            ok = False
        else:
            try:
                import csv

                rows = list(csv.DictReader(lines, delimiter="\t"))
            except Exception as exc:
                rows = []
                messages.append(f"[FAIL] M4S04: analysis_results.tsv parsing failed: {exc}")
                ok = False
            if rows:
                messages.append(f"[PASS] M4S04: analysis_results.tsv has {len(rows)} data rows")
                headers = {str(header).lower() for header in (rows[0].keys() if rows else [])}
                required_header_groups = {
                    "slice/analysis id": {"slice", "analysis_id", "evidence_id"},
                    "analysis type": {"analysis_type", "type"},
                    "method/system": {"method", "system"},
                    "dataset": {"dataset", "data"},
                    "split": {"split", "fold"},
                    "seed": {"seed", "random_seed"},
                    "config/run id": {"config_id", "run_id", "config", "run"},
                    "metric": {"metric"},
                    "value/result": {"value", "result", "mean"},
                    "baseline inclusion": {"baseline_inclusion", "baseline"},
                    "artifact/evidence path": {"artifact_path", "evidence_path", "path"},
                    "runtime": {"runtime_sec", "time_sec", "runtime"},
                    "parameter count": {"params_m", "parameters", "params"},
                    "memory": {"peak_mem_mb", "memory_mb", "peak_memory"},
                    "notes": {"notes", "comment"},
                }
                for label, options in required_header_groups.items():
                    if not (headers & options):
                        messages.append(f"[FAIL] M4S04: analysis_results.tsv missing {label} column")
                        ok = False
                    else:
                        messages.append(f"[PASS] M4S04: analysis_results.tsv includes {label} column")
                joined_rows = json.dumps(rows, ensure_ascii=False).lower()
                row_coverage = _analysis_type_coverage(joined_rows)
                missing_row_coverage = sorted({"ablation", "mechanism", "robustness"} - row_coverage)
                if missing_row_coverage:
                    messages.append(
                        "[FAIL] M4S04: analysis_results.tsv missing rows for "
                        + ", ".join(missing_row_coverage)
                    )
                    ok = False
                else:
                    messages.append("[PASS] M4S04: analysis_results.tsv covers ablation/mechanism/robustness")
                method_values = [
                    str(row.get("method") or row.get("system") or "").lower()
                    for row in rows
                ]
                if not any("baseline" in value or "基线" in value for value in method_values):
                    messages.append("[FAIL] M4S04: analysis_results.tsv missing baseline comparison rows")
                    ok = False
                else:
                    messages.append("[PASS] M4S04: analysis_results.tsv includes baseline comparison rows")
                if not any(
                    "ours" in value or "proposed" in value or "our_method" in value
                    for value in method_values
                ):
                    messages.append("[FAIL] M4S04: analysis_results.tsv missing ours/proposed rows")
                    ok = False
                else:
                    messages.append("[PASS] M4S04: analysis_results.tsv includes ours/proposed rows")
                if efficiency_required:
                    if "efficiency" not in joined_rows and "效率" not in joined_rows:
                        messages.append("[FAIL] M4S04: analysis_results.tsv missing efficiency rows")
                        ok = False
                    else:
                        messages.append("[PASS] M4S04: analysis_results.tsv includes efficiency rows")
                    if not any(
                        header in headers
                        for header in {
                            "flops_g",
                            "macs_g",
                            "inference_latency_ms",
                            "latency_ms",
                            "throughput",
                            "train_time_sec",
                        }
                    ):
                        messages.append("[FAIL] M4S04: analysis_results.tsv missing efficiency metric columns")
                        ok = False
                    else:
                        messages.append("[PASS] M4S04: analysis_results.tsv includes efficiency metric columns")

    artifact_dir = _find_m4_artifact_dir(root)
    if artifact_dir is None:
        messages.append("[FAIL] M4S04: analysis artifact directory missing")
        ok = False
    else:
        messages.append(f"[PASS] M4S04: analysis artifact directory found: {artifact_dir.relative_to(root)}")
        manifest = artifact_dir / "manifest.yaml"
        reproduction = artifact_dir / "reproduction.md"
        if not manifest.exists() or not manifest.read_text(encoding="utf-8").strip():
            messages.append("[FAIL] M4S04: analysis artifact manifest.yaml missing or empty")
            ok = False
            manifest_data: Any = {}
        else:
            try:
                import yaml

                manifest_data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            except Exception as exc:
                manifest_data = {}
                messages.append(f"[FAIL] M4S04: analysis artifact manifest.yaml unreadable: {exc}")
                ok = False
            if isinstance(manifest_data, dict):
                slices = manifest_data.get("analysis_slices") or manifest_data.get("slices") or []
                if not isinstance(slices, list) or len(slices) < 3:
                    messages.append("[FAIL] M4S04: manifest.yaml must list at least 3 analysis_slices")
                    ok = False
                else:
                    messages.append("[PASS] M4S04: manifest.yaml lists at least 3 analysis_slices")
                manifest_text = json.dumps(manifest_data, ensure_ascii=False).lower()
                manifest_coverage = _analysis_type_coverage(manifest_text)
                missing_manifest_coverage = sorted({"ablation", "mechanism", "robustness"} - manifest_coverage)
                if missing_manifest_coverage:
                    messages.append(
                        "[FAIL] M4S04: manifest.yaml missing analysis types: "
                        + ", ".join(missing_manifest_coverage)
                    )
                    ok = False
                else:
                    messages.append("[PASS] M4S04: manifest.yaml covers ablation/mechanism/robustness")
                if "baseline" not in manifest_text and "基线" not in manifest_text:
                    messages.append("[FAIL] M4S04: manifest.yaml missing baseline inclusion/provenance")
                    ok = False
                else:
                    messages.append("[PASS] M4S04: manifest.yaml includes baseline inclusion/provenance")
                if "literature" not in manifest_text and "文献" not in manifest_text:
                    messages.append("[FAIL] M4S04: manifest.yaml missing literature/design basis")
                    ok = False
                else:
                    messages.append("[PASS] M4S04: manifest.yaml includes literature/design basis")
                if not _m4_component_claim_matrix_present(manifest_text):
                    messages.append("[FAIL] M4S04: manifest.yaml missing component/claim coverage")
                    ok = False
                else:
                    messages.append("[PASS] M4S04: manifest.yaml includes component/claim coverage")
                if not _m4_paper_protocol_present(manifest_text):
                    messages.append("[FAIL] M4S04: manifest.yaml missing paper protocol adaptation")
                    ok = False
                else:
                    messages.append("[PASS] M4S04: manifest.yaml includes paper protocol adaptation")
        if not reproduction.exists() or not reproduction.read_text(encoding="utf-8").strip():
            messages.append("[FAIL] M4S04: analysis artifact reproduction.md missing or empty")
            ok = False
        else:
            messages.append("[PASS] M4S04: analysis artifact reproduction.md present")
        figure_roots = [artifact_dir, root / "experiments" / "figures"]
        figure_exts = {".pdf", ".png", ".jpg", ".jpeg", ".svg"}
        figures = [
            path for figure_root in figure_roots if figure_root.exists()
            for path in figure_root.rglob("*")
            if path.is_file() and path.suffix.lower() in figure_exts
        ]
        if not figures:
            messages.append("[FAIL] M4S04: no analysis visualization/figure artifact found")
            ok = False
        else:
            messages.append(f"[PASS] M4S04: {len(figures)} analysis visualization/figure artifact(s) found")

    if not handoff.exists() or not handoff.read_text(encoding="utf-8").strip():
        messages.append("[FAIL] M4S04: handoff_M4_M5.md missing or empty")
        ok = False
    else:
        handoff_text = handoff.read_text(encoding="utf-8")
        handoff_terms = {
            "claim/evidence mapping": ("Claim", "Evidence", "证据", "主张"),
            "artifact path list": ("experiments/analysis_results.tsv", "experiments/artifacts", "图表", "figure"),
            "M5 writing guidance": ("M5", "Introduction", "Method", "Experiments", "Analysis", "论文结构"),
            "limitations/caveats": ("limitation", "局限", "caveat", "weak"),
            "usable evidence status": ("supported", "partially_supported", "usable", "weak"),
        }
        for label, terms in handoff_terms.items():
            if not _contains_any(handoff_text, terms):
                messages.append(f"[FAIL] M4S04: handoff_M4_M5.md missing {label}")
                ok = False
            else:
                messages.append(f"[PASS] M4S04: handoff_M4_M5.md includes {label}")

    return ok, messages


def _check_m3s01_execution_config(
    env_data: dict[str, Any],
    *,
    doc_text: str = "",
) -> tuple[bool, list[str], str]:
    """Validate that M3S01 uses a concrete local/ssh execution configuration."""
    messages: list[str] = []
    ok = True
    execution = env_data.get("execution", {}) if isinstance(env_data, dict) else {}
    if not isinstance(execution, dict):
        return False, ["[FAIL] M3S01: execution_env.yaml missing execution mapping"], ""

    mode = str(execution.get("mode", "")).strip().lower()
    messages.append(f"[PASS] M3S01: execution_env.yaml readable (mode={mode or 'unset'})")
    if mode not in {"local", "ssh"}:
        messages.append("[FAIL] M3S01: execution.mode must be explicitly local or ssh")
        ok = False
        return ok, messages, mode

    doc_lower = doc_text.lower()
    if mode == "local":
        if doc_text and not _contains_any(doc_lower, ("local", "本地")):
            messages.append("[FAIL] M3S01: implementation doc does not match local execution mode")
            ok = False
        else:
            messages.append("[PASS] M3S01: implementation doc records local execution mode")
        local = execution.get("local", {})
        if not isinstance(local, dict):
            messages.append("[FAIL] M3S01: execution.local must be a mapping for local mode")
            ok = False
        else:
            env_manager = str(local.get("env_manager", "")).strip().lower()
            if env_manager not in {"conda", "venv", "uv", "docker"}:
                messages.append("[FAIL] M3S01: local env_manager must be conda/venv/uv/docker")
                ok = False
            else:
                messages.append(f"[PASS] M3S01: local env_manager={env_manager}")
            if not str(local.get("python_version", "")).strip():
                messages.append("[FAIL] M3S01: local python_version missing")
                ok = False
            else:
                messages.append("[PASS] M3S01: local python_version present")

    if mode == "ssh":
        if doc_text and not _contains_any(doc_lower, ("ssh", "remote", "rsync", "远程")):
            messages.append("[FAIL] M3S01: implementation doc does not match ssh/remote execution mode")
            ok = False
        else:
            messages.append("[PASS] M3S01: implementation doc records ssh/remote execution mode")
        ssh = execution.get("ssh", {})
        if not isinstance(ssh, dict):
            messages.append("[FAIL] M3S01: execution.ssh must be a mapping for ssh mode")
            ok = False
        else:
            required = {
                "host": "ssh host",
                "user": "ssh user",
                "framework_root": "ssh framework_root",
                "workspace_path": "ssh workspace_path",
                "dataset_path": "ssh dataset_path",
                "env_manager": "ssh env_manager",
                "python_version": "ssh python_version",
            }
            for field, label in required.items():
                if not str(ssh.get(field, "")).strip():
                    messages.append(f"[FAIL] M3S01: {label} missing")
                    ok = False
                else:
                    messages.append(f"[PASS] M3S01: {label} present")
            sync = ssh.get("sync", {})
            sync_method = str(sync.get("method", "")).strip().lower() if isinstance(sync, dict) else ""
            if sync_method not in {"rsync", "scp"}:
                messages.append("[FAIL] M3S01: ssh sync.method must be rsync or scp")
                ok = False
            else:
                messages.append(f"[PASS] M3S01: ssh sync.method={sync_method}")

    return ok, messages, mode


def _check_m3s01_longrun_ledger(root: Path, execution_mode: str = "") -> tuple[bool, list[str]]:
    """Validate the M3S01 long-running execution ledger."""
    ledger = root / "experiments" / "logs" / "m3s01_longrun_ledger.md"
    messages: list[str] = []
    ok = True

    if not ledger.exists():
        return False, ["[FAIL] M3S01: long-running execution ledger missing: experiments/logs/m3s01_longrun_ledger.md"]

    try:
        text = ledger.read_text(encoding="utf-8")
    except Exception as exc:
        return False, [f"[FAIL] M3S01: long-running execution ledger unreadable: {exc}"]

    required_groups = {
        "execution mode": ("execution mode", "mode", "执行模式"),
        "command": ("command", "cmd", "命令"),
        "status": ("status", "state", "状态"),
        "log path": ("log path", "log_path", "日志路径", "日志"),
        "patience/polling": ("patience", "timeout", "poll", "poll_interval", "等待", "轮询"),
        "resume/retry": ("resume", "resume_command", "retry", "recover", "断点续传", "恢复"),
        "permission/approval": ("permission", "approval", "allowed", "allow", "权限", "批准"),
    }
    for label, terms in required_groups.items():
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] M3S01: long-running ledger missing {label} evidence")
            ok = False
        else:
            messages.append(f"[PASS] M3S01: long-running ledger includes {label} evidence")

    prohibited_patterns = (
        r"(?i)skip(?:ped)?\s+because\s+(?:it\s+is\s+)?too\s+large",
        r"(?i)too\s+large\s+to\s+(?:download|upload|transfer)",
        r"(?i)too\s+slow\s+to\s+(?:download|upload|wait)",
        r"太大.{0,12}(?:不下|不下载|跳过|放弃)",
        r"太慢.{0,12}(?:跳过|放弃|不等)",
    )
    for pattern in prohibited_patterns:
        if re.search(pattern, text):
            messages.append("[FAIL] M3S01: long-running ledger records an invalid size/time-based skip")
            ok = False
            break

    mode = (execution_mode or "").lower()
    if mode == "ssh":
        if not _contains_any(text, ("ssh", "rsync", "remote", "远程")):
            messages.append("[FAIL] M3S01: SSH mode ledger missing remote execution/rsync evidence")
            ok = False
        else:
            messages.append("[PASS] M3S01: SSH mode ledger includes remote execution/rsync evidence")
    elif mode == "local":
        if not _contains_any(text, ("local", "本地")):
            messages.append("[FAIL] M3S01: local mode ledger missing local execution evidence")
            ok = False
        else:
            messages.append("[PASS] M3S01: local mode ledger includes local execution evidence")

    return ok, messages


def _check_experiment_sandbox_profile(
    root: Path,
    *,
    env_data: dict[str, Any] | None = None,
    require_m4_execution_doc: bool = False,
) -> tuple[bool, list[str]]:
    """Validate sandbox/container profile evidence for experiment execution."""
    messages: list[str] = []
    ok = True

    if env_data is None:
        env_cfg = root / "config" / "execution_env.yaml"
        if not env_cfg.exists():
            return False, ["[FAIL] Experiment sandbox: config/execution_env.yaml not found"]
        try:
            import yaml

            env_data = yaml.safe_load(env_cfg.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            return False, [f"[FAIL] Experiment sandbox: execution_env.yaml unreadable: {exc}"]

    execution = env_data.get("execution", {}) if isinstance(env_data, dict) else {}
    sandbox = execution.get("sandbox", {}) if isinstance(execution, dict) else {}
    profile_path = root / "experiments" / "configs" / "sandbox_profile.yaml"

    if not sandbox:
        messages.append("[FAIL] Experiment sandbox: execution.sandbox profile missing in config/execution_env.yaml")
        ok = False
    else:
        messages.append("[PASS] Experiment sandbox: execution.sandbox profile present")
        enabled = sandbox.get("enabled")
        if enabled is not True:
            messages.append("[FAIL] Experiment sandbox: execution.sandbox.enabled must be true")
            ok = False
        else:
            messages.append("[PASS] Experiment sandbox: sandbox enabled")
        mode = str(sandbox.get("mode", "")).strip().lower()
        if mode not in {"docker", "conda", "venv", "uv", "ssh_remote", "none"}:
            messages.append(f"[FAIL] Experiment sandbox: invalid sandbox mode={mode or 'unset'}")
            ok = False
        elif mode == "none":
            messages.append("[FAIL] Experiment sandbox: mode=none is not allowed for M3/M4 experiment execution")
            ok = False
        else:
            messages.append(f"[PASS] Experiment sandbox: mode={mode}")
        execution_mode = str(execution.get("mode", "")).strip().lower()
        if execution_mode == "ssh" and mode != "ssh_remote":
            messages.append("[FAIL] Experiment sandbox: execution.mode=ssh requires sandbox.mode=ssh_remote")
            ok = False
        elif execution_mode == "local" and mode == "ssh_remote":
            messages.append("[FAIL] Experiment sandbox: execution.mode=local cannot use sandbox.mode=ssh_remote")
            ok = False
        elif execution_mode in {"local", "ssh"}:
            messages.append("[PASS] Experiment sandbox: sandbox mode matches execution.mode")

        required_fields = {
            "network_policy": ("network", "网络"),
            "filesystem_policy": ("filesystem", "read_only", "write_paths", "文件"),
            "secrets_policy": ("secret", "credential", "凭证", "密钥"),
            "resource_limits": ("cpu", "memory", "gpu", "timeout", "资源"),
            "allowed_write_paths": ("write", "artifacts", "runs", "logs", "写入"),
            "reproducibility": ("image", "lock", "requirements", "digest", "seed", "可复现"),
        }
        sandbox_text = json.dumps(sandbox, ensure_ascii=False, sort_keys=True)
        for label, terms in required_fields.items():
            if not _contains_any(sandbox_text, terms):
                messages.append(f"[FAIL] Experiment sandbox: missing {label}")
                ok = False
            else:
                messages.append(f"[PASS] Experiment sandbox: includes {label}")

    if not profile_path.exists():
        messages.append("[FAIL] Experiment sandbox: experiments/configs/sandbox_profile.yaml not found")
        ok = False
    else:
        try:
            import yaml

            profile_data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
            profile_text = json.dumps(profile_data, ensure_ascii=False, sort_keys=True)
        except Exception as exc:
            messages.append(f"[FAIL] Experiment sandbox: sandbox_profile.yaml unreadable: {exc}")
            ok = False
            profile_text = ""
        if profile_text:
            for term in ("network", "filesystem", "secrets", "resource", "write", "reproducibility"):
                if term not in profile_text.lower():
                    messages.append(f"[FAIL] Experiment sandbox: sandbox_profile.yaml missing {term} section")
                    ok = False
                else:
                    messages.append(f"[PASS] Experiment sandbox: sandbox_profile.yaml includes {term}")

    if require_m4_execution_doc:
        doc = root / "knowledge" / "M4" / "M4S03_analysis_experiment.md"
        if not doc.exists():
            messages.append("[FAIL] M4S03: analysis execution doc missing for sandbox audit")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            if not _contains_any(text, ("sandbox", "container", "docker", "隔离", "execution.sandbox", "sandbox_profile")):
                messages.append("[FAIL] M4S03: sandbox/container execution record missing")
                ok = False
            else:
                messages.append("[PASS] M4S03: sandbox/container execution record present")

    return ok, messages


def _check_m3s01_resource_plan(
    root: Path,
    *,
    env_data: dict[str, Any] | None = None,
    doc_text: str = "",
) -> tuple[bool, list[str]]:
    """Validate the M3S01 resource optimization contract."""
    messages: list[str] = []
    ok = True

    execution = env_data.get("execution", {}) if isinstance(env_data, dict) else {}
    optimization = execution.get("resource_optimization", {}) if isinstance(execution, dict) else {}
    if not isinstance(optimization, dict) or not optimization:
        messages.append("[FAIL] M3S01: execution.resource_optimization missing")
        ok = False
    elif optimization.get("enabled") is not True:
        messages.append("[FAIL] M3S01: execution.resource_optimization.enabled must be true")
        ok = False
    else:
        messages.append("[PASS] M3S01: resource optimization enabled")

    plan_path = root / "experiments" / "configs" / "resource_plan.yaml"
    if not plan_path.exists():
        messages.append("[FAIL] M3S01: experiments/configs/resource_plan.yaml not found")
        return False, messages

    try:
        import yaml

        plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        messages.append(f"[FAIL] M3S01: resource_plan.yaml unreadable: {exc}")
        return False, messages

    if not isinstance(plan, dict):
        messages.append("[FAIL] M3S01: resource_plan.yaml must contain a mapping")
        return False, messages

    messages.append("[PASS] M3S01: resource_plan.yaml readable")
    plan_text = json.dumps(plan, ensure_ascii=False, sort_keys=True).lower()
    required = {
        "available hardware": ("available", "cpu", "gpus"),
        "resource allocation": ("allocation", "gpu_count", "cpu_cores"),
        "execution strategy": ("strategy", "device_mode", "dataloader"),
        "launch command": ("launch", "command_template"),
        "monitoring policy": ("monitoring", "min_gpu_utilization_pct", "min_cpu_utilization_pct"),
    }
    for label, terms in required.items():
        if not all(term.lower() in plan_text for term in terms):
            messages.append(f"[FAIL] M3S01: resource_plan.yaml missing {label}")
            ok = False
        else:
            messages.append(f"[PASS] M3S01: resource_plan.yaml includes {label}")

    pool_ok, pool_msgs = _check_resource_pool_plan(root, plan, label="M3S01")
    messages.extend(pool_msgs)
    ok = ok and pool_ok

    available = plan.get("available", {}) if isinstance(plan.get("available"), dict) else {}
    allocation = plan.get("allocation", {}) if isinstance(plan.get("allocation"), dict) else {}
    strategy = plan.get("strategy", {}) if isinstance(plan.get("strategy"), dict) else {}
    launch = plan.get("launch", {}) if isinstance(plan.get("launch"), dict) else {}
    gpus = available.get("gpus", [])
    visible_gpu_count = len(gpus) if isinstance(gpus, list) else 0
    allocated_gpu_count = _safe_int(allocation.get("gpu_count"), default=0)
    allocated_cpu = _safe_int(allocation.get("cpu_cores"), default=0)
    cpu = available.get("cpu", {}) if isinstance(available.get("cpu"), dict) else {}
    visible_cpu = _safe_int(cpu.get("cores"), default=0)

    if visible_gpu_count >= 2 and allocated_gpu_count < 2:
        explanation_terms = (
            "ddp not supported",
            "task_parallel",
            "fairness",
            "quota",
            "显存不足",
            "不兼容",
            "配额",
            "公平",
        )
        if not _contains_any(doc_text + plan_text, explanation_terms):
            messages.append("[FAIL] M3S01: multiple GPUs visible but resource plan does not allocate/use them or explain why")
            ok = False
        else:
            messages.append("[PASS] M3S01: partial GPU allocation has documented rationale")
    elif visible_gpu_count >= 2:
        strategy_text = json.dumps(strategy, ensure_ascii=False).lower()
        launch_text = json.dumps(launch, ensure_ascii=False).lower()
        if not _contains_any(strategy_text + launch_text, ("ddp", "distributed", "torchrun", "task_parallel")):
            messages.append("[FAIL] M3S01: multiple GPUs allocated without DDP/task-parallel strategy")
            ok = False
        else:
            messages.append("[PASS] M3S01: multi-GPU strategy present")

    dataloader = strategy.get("dataloader", {}) if isinstance(strategy.get("dataloader"), dict) else {}
    num_workers = _safe_int(dataloader.get("num_workers"), default=-1)
    if visible_cpu >= 4 and allocated_cpu >= 4 and num_workers <= 0:
        messages.append("[FAIL] M3S01: multi-core CPU available but dataloader num_workers is not planned")
        ok = False
    elif visible_cpu >= 4 and allocated_cpu >= 4:
        messages.append(f"[PASS] M3S01: dataloader num_workers planned ({num_workers})")

    return ok, messages


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        if value is None or isinstance(value, bool):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _resource_pool_resources(plan: dict[str, Any]) -> list[dict[str, Any]]:
    pool = plan.get("resource_pool", {}) if isinstance(plan.get("resource_pool"), dict) else {}
    resources = pool.get("resources", []) if isinstance(pool.get("resources"), list) else []
    return [resource for resource in resources if isinstance(resource, dict) and resource.get("enabled", True) is not False]


def _resource_pool_enabled(plan: dict[str, Any]) -> bool:
    pool = plan.get("resource_pool", {}) if isinstance(plan.get("resource_pool"), dict) else {}
    return bool(pool.get("enabled") is True or len(_resource_pool_resources(plan)) > 1)


def _check_resource_pool_plan(
    root: Path,
    plan: dict[str, Any],
    *,
    label: str,
    require_allocation: bool = False,
    allocation_name: str = "m3_task_allocation.yaml",
    doc_text: str = "",
) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True
    pool = plan.get("resource_pool", {}) if isinstance(plan.get("resource_pool"), dict) else {}
    resources = _resource_pool_resources(plan)
    if not _resource_pool_enabled(plan):
        messages.append(f"[PASS] {label}: multi-resource pool not enabled")
        return True, messages

    messages.append(f"[PASS] {label}: multi-resource pool enabled with {len(resources)} resource(s)")
    if len(resources) < 2:
        messages.append(f"[FAIL] {label}: resource_pool enabled but fewer than 2 enabled resources are listed")
        ok = False

    pool_text = json.dumps(pool, ensure_ascii=False, sort_keys=True).lower()
    required_terms = {
        "resource identifiers": ("resource_id", "kind"),
        "capacity": ("gpu_count", "cpu_cores"),
        "scheduling policy": ("parallel", "fairness", "task", "sync"),
    }
    for field, terms in required_terms.items():
        if not all(term in pool_text for term in terms):
            messages.append(f"[FAIL] {label}: resource_pool missing {field}")
            ok = False
        else:
            messages.append(f"[PASS] {label}: resource_pool includes {field}")

    for resource in resources:
        kind = str(resource.get("kind", "")).lower()
        rid = str(resource.get("resource_id") or resource.get("server_id") or "resource")
        if kind == "ssh":
            if not str(resource.get("server_id", "")).strip() or not str(resource.get("lease_id", "")).strip():
                messages.append(f"[FAIL] {label}: SSH resource {rid} missing server_id/lease_id")
                ok = False
            elif not str(resource.get("workspace_path", "")).strip():
                messages.append(f"[FAIL] {label}: SSH resource {rid} missing workspace_path")
                ok = False
            else:
                messages.append(f"[PASS] {label}: SSH resource {rid} has server/lease/workspace")

    if require_allocation:
        allocation_path = root / "experiments" / "configs" / allocation_name
        if not allocation_path.exists():
            messages.append(f"[FAIL] {label}: experiments/configs/{allocation_name} not found for multi-resource execution")
            ok = False
            return ok, messages
        try:
            import yaml

            allocation = yaml.safe_load(allocation_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            messages.append(f"[FAIL] {label}: {allocation_name} unreadable: {exc}")
            ok = False
            return ok, messages
        if not isinstance(allocation, dict):
            messages.append(f"[FAIL] {label}: {allocation_name} must contain a mapping")
            ok = False
            return ok, messages
        assignments = allocation.get("assignments", [])
        waves = allocation.get("waves", [])
        if not isinstance(assignments, list) or not assignments:
            messages.append(f"[FAIL] {label}: {allocation_name} missing nonempty assignments")
            ok = False
        else:
            messages.append(f"[PASS] {label}: {allocation_name} has {len(assignments)} assignment(s)")
        if not isinstance(waves, list) or not waves:
            messages.append(f"[FAIL] {label}: {allocation_name} missing execution waves")
            ok = False
        else:
            messages.append(f"[PASS] {label}: {allocation_name} has execution waves")
        assignment_text = json.dumps(assignments, ensure_ascii=False, sort_keys=True).lower()
        for term in ("resource_id", "resource_kind", "gpu_ids", "resource_monitor"):
            if term not in assignment_text:
                messages.append(f"[FAIL] {label}: {allocation_name} assignments missing {term}")
                ok = False
            else:
                messages.append(f"[PASS] {label}: {allocation_name} assignments include {term}")
        blocked = allocation.get("blocked_tasks", [])
        if isinstance(blocked, list) and blocked:
            if not _contains_any(doc_text + "\n" + json.dumps(blocked, ensure_ascii=False), ("blocked", "reason", "依赖", "显存", "同步", "fairness", "配额", "不可达", "原因")):
                messages.append(f"[FAIL] {label}: blocked allocation tasks lack explanation in stage output")
                ok = False
            else:
                messages.append(f"[PASS] {label}: blocked allocation tasks have explanation")
    return ok, messages


def _resource_monitor_summary(path: Path) -> tuple[bool, str]:
    try:
        import csv

        rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    except Exception as exc:
        return False, f"unreadable ({exc})"
    if not rows:
        return False, "empty"
    headers = set(rows[0].keys())
    if "timestamp" not in headers or ("cpu_load_pct" not in headers and "gpu_util_pct" not in headers):
        return False, "missing timestamp/cpu/gpu utilization columns"
    return True, f"{len(rows)} sample row(s)"


def _check_m3s03_resource_execution(root: Path, *, doc_text: str = "") -> tuple[bool, list[str]]:
    """Validate resource utilization evidence for M3S03."""
    messages: list[str] = []
    ok = True
    plan_path = root / "experiments" / "configs" / "resource_plan.yaml"
    if not plan_path.exists():
        messages.append("[FAIL] M3S03: resource_plan.yaml not found")
        ok = False
        plan: dict[str, Any] = {}
    else:
        try:
            import yaml

            plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
            messages.append("[PASS] M3S03: resource_plan.yaml found")
        except Exception as exc:
            messages.append(f"[FAIL] M3S03: resource_plan.yaml unreadable: {exc}")
            ok = False
            plan = {}

    if not _contains_any(doc_text, ("resource_plan", "resource plan", "资源执行", "资源利用", "resource_monitor")):
        messages.append("[FAIL] M3S03: main experiment doc missing resource utilization record")
        ok = False
    else:
        messages.append("[PASS] M3S03: main experiment doc records resource utilization")

    monitors = sorted((root / "experiments" / "runs").rglob("resource_monitor.csv")) if (root / "experiments" / "runs").exists() else []
    if not monitors:
        messages.append("[FAIL] M3S03: no resource_monitor.csv found under experiments/runs/")
        ok = False
    else:
        valid = 0
        for monitor in monitors:
            monitor_ok, summary = _resource_monitor_summary(monitor)
            if monitor_ok:
                valid += 1
                messages.append(f"[PASS] M3S03: {monitor.relative_to(root)} has {summary}")
            else:
                messages.append(f"[FAIL] M3S03: {monitor.relative_to(root)} {summary}")
                ok = False
        if valid:
            messages.append(f"[PASS] M3S03: {valid} resource monitor file(s) found")

    allocation = plan.get("allocation", {}) if isinstance(plan.get("allocation"), dict) else {}
    strategy = plan.get("strategy", {}) if isinstance(plan.get("strategy"), dict) else {}
    allocated_gpu_count = _safe_int(allocation.get("gpu_count"), default=0)

    pool_ok, pool_msgs = _check_resource_pool_plan(
        root,
        plan,
        label="M3S03",
        require_allocation=True,
        allocation_name="m3_task_allocation.yaml",
        doc_text=doc_text,
    )
    messages.extend(pool_msgs)
    ok = ok and pool_ok

    if allocated_gpu_count >= 2:
        combined = doc_text + "\n" + json.dumps(strategy, ensure_ascii=False)
        if not _contains_any(combined, ("ddp", "distributed", "torchrun", "task_parallel", "多卡", "任务并行")):
            messages.append("[FAIL] M3S03: multi-GPU allocation lacks DDP/task-parallel execution evidence")
            ok = False
        else:
            messages.append("[PASS] M3S03: multi-GPU execution strategy documented")

    if _contains_any(doc_text, ("low utilization", "低利用率", "underutilized")):
        if not _contains_any(doc_text, ("optimized", "documented blocker", "not observed", "none", "不可优化", "已调", "原因", "无")):
            messages.append("[FAIL] M3S03: low utilization mentioned without optimize-or-document outcome")
            ok = False
        else:
            messages.append("[PASS] M3S03: low utilization has optimize-or-document outcome")

    if _resource_pool_enabled(plan):
        if not _contains_any(doc_text, ("resource_id", "resource kind", "resource_kind", "server_id", "m3_task_allocation", "同步", "sync")):
            messages.append("[FAIL] M3S03: multi-resource execution missing resource_id/server/sync record in main doc")
            ok = False
        else:
            messages.append("[PASS] M3S03: multi-resource execution record present in main doc")

    return ok, messages


def _jsonl_has_watchdog_event(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        return False, f"unreadable ({exc})"
    if not lines:
        return False, "empty"

    watchdog_events = 0
    decision_required = 0
    for line in lines:
        lowered = line.lower()
        has_watchdog_marker = "watchdog" in lowered
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            event = {}
        if str(event.get("event_type", "")).lower() == "watchdog_check":
            has_watchdog_marker = True
        if has_watchdog_marker:
            watchdog_events += 1
        if isinstance(event, dict) and event.get("decision_required") is True:
            decision_required += 1
    if watchdog_events <= 0:
        return False, f"{len(lines)} line(s), but no watchdog event"
    suffix = f"; {decision_required} decision-required event(s)" if decision_required else ""
    return True, f"{len(lines)} line(s), {watchdog_events} watchdog event marker(s){suffix}"


def _check_m3s03_runtime_watchdog(root: Path, *, doc_text: str = "") -> tuple[bool, list[str]]:
    """Validate runtime watchdog supervision for long-running M3S03 runs."""
    messages: list[str] = []
    ok = True

    if not _contains_any(doc_text, ("watchdog", "runtime_events", "巡检", "告警", "早停", "early_stop")):
        messages.append("[FAIL] M3S03: main experiment doc missing runtime watchdog/alert supervision record")
        ok = False
    else:
        messages.append("[PASS] M3S03: main experiment doc records runtime watchdog/alert supervision")

    runtime_events = root / "experiments" / "logs" / "runtime_events.jsonl"
    runtime_ok, runtime_summary = _jsonl_has_watchdog_event(runtime_events)
    if not runtime_ok:
        messages.append(f"[FAIL] M3S03: experiments/logs/runtime_events.jsonl {runtime_summary}")
        ok = False
    else:
        messages.append(f"[PASS] M3S03: runtime_events.jsonl has {runtime_summary}")

    runs_dir = root / "experiments" / "runs"
    checks = sorted(runs_dir.rglob("watchdog_checks.jsonl")) if runs_dir.exists() else []
    if not checks:
        messages.append("[FAIL] M3S03: no watchdog_checks.jsonl found under experiments/runs/")
        ok = False
    else:
        valid_checks = 0
        for check in checks:
            check_ok, summary = _jsonl_has_watchdog_event(check)
            if check_ok:
                valid_checks += 1
                messages.append(f"[PASS] M3S03: {check.relative_to(root)} has {summary}")
            else:
                messages.append(f"[FAIL] M3S03: {check.relative_to(root)} {summary}")
                ok = False
        if valid_checks:
            messages.append(f"[PASS] M3S03: {valid_checks} watchdog check file(s) found")

    alerts = sorted(runs_dir.rglob("watchdog_alerts.jsonl")) if runs_dir.exists() else []
    nonempty_alerts = [path for path in alerts if _file_has_content(path)]
    if nonempty_alerts:
        if not _contains_any(
            doc_text,
            (
                "Agent 决策",
                "agent decision",
                "continue",
                "fix_and_rerun",
                "early_stop",
                "backtrack_request",
                "继续",
                "修复",
                "早停",
                "回溯",
            ),
        ):
            messages.append("[FAIL] M3S03: watchdog alerts exist but Agent decision log is missing")
            ok = False
        else:
            messages.append("[PASS] M3S03: watchdog alerts have Agent decision evidence in main doc")
    else:
        messages.append("[PASS] M3S03: no nonempty watchdog alert file requiring decision log")

    if _contains_any(doc_text, ("watchdog auto stop", "watchdog auto-stop", "watchdog 自动终止", "脚本自动结束")):
        messages.append("[FAIL] M3S03: watchdog must not automatically terminate experiments")
        ok = False
    else:
        messages.append("[PASS] M3S03: watchdog policy does not claim automatic termination")

    return ok, messages


def _row_first(row: dict[str, Any], names: tuple[str, ...]) -> str:
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _jsonl_has_completion_event(path: Path, run_ids: set[str]) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        return False, f"unreadable ({exc})"
    if not lines:
        return False, "empty"

    completion_events = {
        "training_completed",
        "run_completed",
        "experiment_completed",
        "main_experiment_completed",
        "checkpoint_saved",
    }
    running_after_completion: set[str] = set()
    completed_for_target = 0
    completion_total = 0
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            event = {}
        event_type = str(event.get("event_type", "")).strip().lower()
        run_id = str(event.get("run_id", "")).strip()
        status = str(event.get("status", "")).strip().lower()
        if event_type in completion_events or status in {"completed", "succeeded", "finished", "done"}:
            completion_total += 1
            if not run_ids or run_id in run_ids:
                completed_for_target += 1
                running_after_completion.discard(run_id)
        if run_id in run_ids and (event_type in {"training_started", "run_started"} or status in {"running", "queued"}):
            running_after_completion.add(run_id)
    if completed_for_target <= 0:
        return False, f"{len(lines)} line(s), but no completion event for proposed run"
    if running_after_completion:
        return False, "latest visible status includes running/queued proposed run(s): " + ", ".join(sorted(running_after_completion))
    return True, f"{completion_total} completion event marker(s), {completed_for_target} for proposed run(s)"


def _check_m3s03_trained_weight_evidence(root: Path, *, doc_text: str = "") -> tuple[bool, list[str]]:
    """Require final M3S03 results to come from completed trained weights."""
    messages: list[str] = []
    ok = True
    results = root / "experiments" / "results.tsv"
    if not results.exists():
        return False, ["[FAIL] M3S03: results.tsv missing, cannot verify trained-weight evidence"]

    try:
        import csv

        rows = list(csv.DictReader(results.read_text(encoding="utf-8").splitlines(), delimiter="\t"))
    except Exception as exc:
        return False, [f"[FAIL] M3S03: results.tsv unreadable for trained-weight verification: {exc}"]

    if not rows:
        return False, ["[FAIL] M3S03: results.tsv has no rows for trained-weight verification"]

    proposed_rows: list[dict[str, Any]] = []
    for row in rows:
        method_text = " ".join(
            _row_first(row, names)
            for names in (
                ("method", "model", "system", "name"),
                ("role", "method_role", "comparison_role"),
            )
        ).lower()
        if any(marker in method_text for marker in ("ours", "proposed", "our_method", "本文", "方法")):
            proposed_rows.append(row)

    if not proposed_rows:
        messages.append("[FAIL] M3S03: results.tsv has no proposed/ours row for trained-weight verification")
        return False, messages

    completed_statuses = {"completed", "succeeded", "success", "finished", "done", "pass", "passed"}
    trained_states = {
        "trained",
        "trained_checkpoint",
        "fine_tuned",
        "finetuned",
        "verified_trained",
        "verified_loadable",
        "completed_training",
    }
    invalid_states = {"random", "random_init", "random_weights", "untrained", "init", "e0", "epoch0", "scratch_untrained"}
    proposed_run_ids: set[str] = set()
    valid_rows = 0

    for idx, row in enumerate(proposed_rows, start=1):
        row_label = f"M3S03 proposed result row {idx}"
        run_id = _row_first(row, ("run_id", "run", "id"))
        if run_id:
            proposed_run_ids.add(run_id)

        status = _row_first(row, ("run_status", "training_status", "status", "completion_status")).lower()
        if status not in completed_statuses:
            messages.append(f"[FAIL] {row_label}: run_status/training_status must be completed, got {status or 'unset'}")
            ok = False
            continue

        weight_state = _row_first(row, ("weight_state", "weights_state", "checkpoint_status", "model_state")).lower()
        if weight_state in invalid_states:
            messages.append(f"[FAIL] {row_label}: final result uses invalid weight_state={weight_state}")
            ok = False
            continue
        if weight_state not in trained_states:
            messages.append(f"[FAIL] {row_label}: weight_state must prove trained weights, got {weight_state or 'unset'}")
            ok = False
            continue

        checkpoint_path = _row_first(row, ("checkpoint_path", "weights_path", "model_checkpoint", "trained_checkpoint", "checkpoint"))
        if not checkpoint_path:
            messages.append(f"[FAIL] {row_label}: missing checkpoint_path/weights_path for trained weights")
            ok = False
            continue
        if not _project_path_exists(root, checkpoint_path):
            messages.append(f"[FAIL] {row_label}: checkpoint path does not exist: {checkpoint_path}")
            ok = False
            continue

        steps_value = _row_first(row, ("training_steps", "steps", "global_step", "epochs", "epoch"))
        steps = _parse_floatish(steps_value)
        if steps is not None and steps <= 0:
            messages.append(f"[FAIL] {row_label}: training_steps/epoch must be > 0, got {steps_value}")
            ok = False
            continue

        valid_rows += 1

    if valid_rows <= 0:
        messages.append("[FAIL] M3S03: no proposed/ours result row is backed by completed trained weights")
        ok = False
    else:
        messages.append(f"[PASS] M3S03: {valid_rows} proposed/ours result row(s) use completed trained checkpoints")

    runtime_events = root / "experiments" / "logs" / "runtime_events.jsonl"
    completion_ok, completion_summary = _jsonl_has_completion_event(runtime_events, proposed_run_ids)
    if completion_ok:
        messages.append(f"[PASS] M3S03: runtime_events.jsonl records training completion ({completion_summary})")
    else:
        messages.append(f"[FAIL] M3S03: runtime_events.jsonl lacks completed-training evidence ({completion_summary})")
        ok = False

    if _contains_any(doc_text, ("random weights as final", "随机权重作为最终", "untrained final", "E0 only", "E0 只用")):
        messages.append("[FAIL] M3S03: main experiment doc describes random/untrained weights as final evidence")
        ok = False

    return ok, messages


# Backward-compatible aliases for internal callers
_extract_structured_field_value = extract_m3_repair_field_value
_extract_review_verdict = extract_stage_review_verdict


def _missing_structured_fields(text: str, fields: tuple[str, ...] | None = None) -> list[str]:
    """Return missing required repair-advice fields from review text.

    Defaults to the critical scalar fields (matching VerdictParser semantics).
    Callers may pass a custom *fields* tuple for stricter checks.
    """
    if fields is None:
        fields = ("blocking_reason", "required_fix", "success_criteria",
                  "rebuild_mode", "rerun_scope")
    return missing_m3_repair_fields(text, fields)


def _check_stage_reviews(root: Path, stage: str) -> tuple[bool, list[str]]:
    """Validate required stage-review documents before stage advance."""
    messages: list[str] = []
    ok = True

    requirements = _STAGE_REVIEW_REQUIREMENTS.get(stage, {})
    if not requirements:
        return True, messages

    for checker, rel_path in requirements.items():
        review_path = root / rel_path
        alternates = find_alternate_outputs(review_path.parent, review_path.name)
        if alternates:
            messages.append(
                f"[FAIL] {stage}: alternate stage review file(s) found for {review_path.name}: "
                + ", ".join(path.name for path in alternates)
                + "; update the canonical review in place instead of creating v2/new/revised copies."
            )
            ok = False
        if not review_path.exists():
            messages.append(f"[FAIL] {stage}: required stage review missing: {review_path.name}")
            ok = False
            continue

        try:
            text = review_path.read_text(encoding="utf-8")
        except Exception as exc:
            messages.append(f"[FAIL] {stage}: unreadable stage review {review_path}: {exc}")
            ok = False
            continue

        verdict = _extract_review_verdict(text)
        if not verdict:
            messages.append(f"[FAIL] {stage}: stage review {review_path.name} missing explicit verdict")
            ok = False
            continue

        if verdict != "PASS":
            if verdict == "HALT":
                messages.append(
                    f"[FAIL] {stage}: stage review {review_path.name} verdict=HALT; advance blocked until human intervention."
                )
                ok = False
                continue
            missing_fields = _missing_structured_fields(text)
            if missing_fields:
                messages.append(
                    f"[FAIL] {stage}: stage review {review_path.name} verdict={verdict}; "
                    f"missing repair advice fields: {', '.join(missing_fields)}"
                )
            else:
                rebuild_mode = _extract_structured_field_value(text, "rebuild_mode")
                if not is_valid_rebuild_mode(rebuild_mode):
                    messages.append(
                        f"[FAIL] {stage}: stage review {review_path.name} has invalid rebuild_mode={rebuild_mode or 'unset'} "
                        f"(expected incremental_replay or full_regenerate)"
                    )
                    ok = False
                else:
                    messages.append(
                        f"[PASS] {stage}: stage review {review_path.name} includes repair advice fields"
                    )
            messages.append(
                f"[FAIL] {stage}: stage review {review_path.name} verdict={verdict}; "
                f"advance blocked until reviewer returns PASS."
            )
            ok = False
        else:
            messages.append(f"[PASS] {stage}: stage review {checker} PASS")

    return ok, messages


def _check_m1s02_rounds(root: Path) -> tuple[bool, list[str]]:
    """Validate the full M1S02 3-round search/review loop."""
    messages: list[str] = []
    ok = True

    survey_mem_path = root / "state" / "survey_memory.yaml"
    if not survey_mem_path.exists():
        messages.append("[FAIL] M1S02: survey_memory.yaml not found")
        return False, messages

    try:
        import yaml

        mem = yaml.safe_load(survey_mem_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        messages.append(f"[FAIL] M1S02: could not parse survey_memory.yaml: {exc}")
        return False, messages

    batches = mem.get("search_batches", [])
    batch_by_round: dict[int, list[dict[str, Any]]] = {1: [], 2: [], 3: []}
    for batch in batches:
        round_num = batch.get("round")
        if round_num in batch_by_round:
            batch_by_round[round_num].append(batch)

    for round_num in (1, 2, 3):
        review_path = root / _M1S02_ROUND_REVIEW_REQUIREMENTS[round_num]
        alternates = find_alternate_outputs(review_path.parent, review_path.name)
        if alternates:
            messages.append(
                f"[FAIL] M1S02: alternate round {round_num} review file(s) found: "
                + ", ".join(path.name for path in alternates)
                + "; update the canonical review in place instead of creating v2/new/revised copies."
            )
            ok = False
        if not review_path.exists():
            messages.append(f"[FAIL] M1S02: missing round {round_num} review file: {review_path.name}")
            ok = False
        else:
            try:
                review_text = review_path.read_text(encoding="utf-8")
            except Exception as exc:
                messages.append(f"[FAIL] M1S02: unreadable round {round_num} review {review_path}: {exc}")
                ok = False
            else:
                verdict = _extract_review_verdict(review_text)
                if verdict != "PASS":
                    messages.append(
                        f"[FAIL] M1S02: round {round_num} review {review_path.name} verdict={verdict or 'unset'}; advance blocked until PASS."
                    )
                    ok = False
                else:
                    messages.append(f"[PASS] M1S02: round {round_num} review PASS")

        round_batches = batch_by_round.get(round_num, [])
        if not round_batches:
            messages.append(f"[FAIL] M1S02: round {round_num} batch not found in survey_memory.yaml")
            ok = False
            continue
        passed = any(str(batch.get("status", "")).lower() == "passed" for batch in round_batches)
        if not passed:
            statuses = [batch.get("status") for batch in round_batches]
            messages.append(f"[FAIL] M1S02: round {round_num} batch status not PASS (status={statuses})")
            ok = False
        else:
            messages.append(f"[PASS] M1S02: round {round_num} batch passed")
            queries = [
                str(query).strip()
                for batch in round_batches
                for query in batch.get("queries", [])
                if str(query).strip()
            ]
            sources_found = sum(
                batch.get("sources_found", 0)
                for batch in round_batches
                if isinstance(batch.get("sources_found", 0), (int, float))
            )
            if not queries:
                messages.append(f"[FAIL] M1S02: round {round_num} search batch missing queries")
                ok = False
            else:
                messages.append(f"[PASS] M1S02: round {round_num} records {len(queries)} query/queries")
            if sources_found <= 0:
                messages.append(f"[FAIL] M1S02: round {round_num} search batch missing positive sources_found")
                ok = False
            else:
                messages.append(f"[PASS] M1S02: round {round_num} records sources_found={sources_found}")

    round_reviews = mem.get("round_reviews", [])
    if not round_reviews:
        messages.append("[FAIL] M1S02: round_reviews missing in survey_memory.yaml")
        ok = False
    else:
        for round_num in (1, 2, 3):
            rr = [r for r in round_reviews if r.get("round") == round_num]
            if not rr:
                messages.append(f"[FAIL] M1S02: round {round_num} review entry missing in survey_memory.yaml")
                ok = False
            elif not any(str(r.get("verdict", "")).upper() == "PASS" for r in rr):
                verdicts = [r.get("verdict") for r in rr]
                messages.append(f"[FAIL] M1S02: round {round_num} review entry not PASS (verdict={verdicts})")
                ok = False
            else:
                messages.append(f"[PASS] M1S02: round {round_num} review entry PASS")

    return ok, messages


def check_stage(project_root: str | Path, stage: str) -> tuple[bool, list[str]]:
    """Run stage-specific quality checks.

    Returns (ok, messages).
    """
    root = Path(project_root)
    messages: list[str] = []
    ok = True

    # M1S02: Literature Deep Dive
    if stage == "M1S02":
        src_log = root / "knowledge" / "M1" / "M1_source_log.yaml"
        if not src_log.exists():
            messages.append("[FAIL] M1S02: M1_source_log.yaml not found")
            ok = False
        else:
            messages.append("[PASS] M1S02: M1_source_log.yaml exists")

        # --- 3-Round Search→Review→Iterate enforcement ---
        rounds_ok, round_msgs = _check_m1s02_rounds(root)
        messages.extend(round_msgs)
        ok = ok and rounds_ok

        # --- Round version integrity check ---
        m1s02_doc = root / "knowledge" / "M1" / "M1S02_literature_deepdive.md"
        if m1s02_doc.exists():
            text = m1s02_doc.read_text(encoding="utf-8")
            has_round1 = "### Round 1" in text or "## Round 1" in text
            has_round2 = "### Round 2" in text or "## Round 2" in text
            has_round3 = "### Round 3" in text or "## Round 3" in text
            missing_rounds = []
            if not has_round1:
                missing_rounds.append("Round 1")
            if not has_round2:
                missing_rounds.append("Round 2")
            if not has_round3:
                missing_rounds.append("Round 3")
            if missing_rounds:
                messages.append(f"[FAIL] M1S02: M1S02_literature_deepdive.md missing sections: {', '.join(missing_rounds)}")
                ok = False
            else:
                messages.append("[PASS] M1S02: All 3 Round sections present in document")
            report_ok, report_msgs = _check_m1s02_research_report(text)
            messages.extend(report_msgs)
            ok = ok and report_ok
        else:
            messages.append("[FAIL] M1S02: M1S02_literature_deepdive.md not found")
            ok = False

        try:
            from utils.source_log_validator import validate as validate_source_log

            source_ok, source_msgs = validate_source_log(root, module="M1")
            messages.extend(source_msgs)
            ok = ok and source_ok
        except Exception as exc:
            messages.append(f"[FAIL] M1S02: source log validation failed: {exc}")
            ok = False

    # M1S03: Research Question
    if stage == "M1S03":
        m1s03_ok, m1s03_msgs = _check_m1s03_research_question(root)
        messages.extend(m1s03_msgs)
        ok = ok and m1s03_ok

    # M1S04: Hypothesis Generation
    if stage == "M1S04":
        m1s04_ok, m1s04_msgs = _check_m1s04_hypothesis(root)
        messages.extend(m1s04_msgs)
        ok = ok and m1s04_ok

    # M1S05: Novelty & Feasibility (Gate G1)
    if stage == "M1S05":
        m1s05_ok, m1s05_msgs = _check_m1s05_novelty_feasibility(root)
        messages.extend(m1s05_msgs)
        ok = ok and m1s05_ok

    # M2S01: Cross-Domain Search
    if stage == "M2S01":
        doc = root / "knowledge" / "M2" / "M2S01_cross_domain_search.md"
        log = root / "knowledge" / "M2" / "M2_source_log.yaml"
        if not doc.exists():
            messages.append("[FAIL] M2S01: M2S01_cross_domain_search.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            # Check search dimensions
            dim_markers = ["同模态不同任务", "不同模态同任务", "底层原理", "优化目标",
                           "same_modality", "diff_modality", "method_paradigm", "optimization_target"]
            dim_count = sum(1 for m in dim_markers if m in text)
            if dim_count < 2:
                messages.append(f"[WARN] M2S01: Only {dim_count} search dimension markers found (expected ≥2)")
            else:
                messages.append(f"[PASS] M2S01: Search dimensions found ({dim_count})")
            # Check candidate solutions
            if "候选方案" not in text and "candidate" not in text.lower():
                messages.append("[WARN] M2S01: Missing candidate solution pool section")
            else:
                messages.append("[PASS] M2S01: Candidate solution pool section found")
        if not log.exists():
            messages.append("[FAIL] M2S01: M2_source_log.yaml not found")
            ok = False
        else:
            messages.append("[PASS] M2S01: M2_source_log.yaml exists")
            try:
                from utils.source_log_validator import validate as validate_source_log

                source_ok, source_msgs = validate_source_log(root, module="M2")
                messages.extend(source_msgs)
                if not source_ok:
                    ok = False
            except Exception as exc:
                messages.append(f"[FAIL] M2S01: M2 source log validation failed: {exc}")
                ok = False

    # M2S02: Method Inspiration
    if stage == "M2S02":
        doc = root / "knowledge" / "M2" / "M2S02_method_inspiration.md"
        if not doc.exists():
            messages.append("[FAIL] M2S02: M2S02_method_inspiration.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            # Check deep analysis of ≥2 papers
            paper_sections = text.count("### 论文") + text.count("### Paper")
            if paper_sections < 2:
                messages.append(f"[WARN] M2S02: Only {paper_sections} paper analysis sections (expected ≥2)")
            else:
                messages.append(f"[PASS] M2S02: {paper_sections} paper analysis sections")
            # Check mapping sections
            has_structure = "问题结构映射" in text or "structure mapping" in text.lower()
            has_mechanism = "核心机制映射" in text or "mechanism mapping" in text.lower()
            if not has_structure:
                messages.append("[WARN] M2S02: Missing problem structure mapping")
            if not has_mechanism:
                messages.append("[WARN] M2S02: Missing core mechanism mapping")
            if has_structure and has_mechanism:
                messages.append("[PASS] M2S02: Both structure and mechanism mappings present")
            # Check improvement points
            if "IMP-" not in text:
                messages.append("[WARN] M2S02: No improvement points (IMP-*) found")
            else:
                messages.append("[PASS] M2S02: Improvement points found")
            # Check honesty self-check
            if "诚实性自检" not in text and "honesty" not in text.lower():
                messages.append("[WARN] M2S02: Missing honesty self-check")
            else:
                messages.append("[PASS] M2S02: Honesty self-check present")

    # M2S03: Method Architecture Design
    if stage == "M2S03":
        doc = root / "knowledge" / "M2" / "M2S03_method_architecture.md"
        if not doc.exists():
            messages.append("[FAIL] M2S03: M2S03_method_architecture.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            # Check symbol definitions
            has_symbols = "符号定义" in text or "符号" in text
            if not has_symbols:
                messages.append("[WARN] M2S03: Missing symbol definition section")
            else:
                messages.append("[PASS] M2S03: Symbol definition section found")
            # Check architecture components
            has_components = "组件" in text or "component" in text.lower()
            if not has_components:
                messages.append("[WARN] M2S03: Missing architecture components")
            else:
                messages.append("[PASS] M2S03: Architecture components present")
            # Check correspondence to M2S02
            has_correspondence = "M2S02" in text or "对应关系" in text
            if not has_correspondence:
                messages.append("[WARN] M2S03: Missing correspondence to M2S02")
            else:
                messages.append("[PASS] M2S03: Correspondence to M2S02 present")
            # Check design decisions
            has_decisions = "设计决策" in text or "decision" in text.lower()
            if not has_decisions:
                messages.append("[WARN] M2S03: Missing design decision records")
            else:
                messages.append("[PASS] M2S03: Design decision records present")

    # M2S04: Algorithm & Theory Design
    if stage == "M2S04":
        doc = root / "knowledge" / "M2" / "M2S04_algorithm_theory.md"
        if not doc.exists():
            messages.append("[FAIL] M2S04: M2S04_algorithm_theory.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            # Check pseudocode/algorithm
            has_algo = "Algorithm" in text or "算法" in text
            if not has_algo:
                messages.append("[WARN] M2S04: Missing algorithm/pseudocode")
            else:
                messages.append("[PASS] M2S04: Algorithm/pseudocode present")
            # Check complexity analysis
            has_complexity = "复杂度" in text or "complexity" in text.lower()
            if not has_complexity:
                messages.append("[WARN] M2S04: Missing complexity analysis")
            else:
                messages.append("[PASS] M2S04: Complexity analysis present")
            # Check theoretical analysis
            has_theory = "定理" in text or "证明" in text or "theorem" in text.lower() or "proof" in text.lower()
            if not has_theory:
                messages.append("[WARN] M2S04: Missing theoretical analysis")
            else:
                messages.append("[PASS] M2S04: Theoretical analysis present")
            # Check comparison with existing work
            has_relation = "现有工作" in text or "related work" in text.lower() or "对比" in text
            if not has_relation:
                messages.append("[WARN] M2S04: Missing comparison with existing work")
            else:
                messages.append("[PASS] M2S04: Comparison with existing work present")
            # Check honesty declaration
            has_honesty = "诚实性声明" in text or "honesty" in text.lower()
            if not has_honesty:
                messages.append("[WARN] M2S04: Missing honesty declaration")
            else:
                messages.append("[PASS] M2S04: Honesty declaration present")

    if stage in {"M2S01", "M2S02", "M2S03", "M2S04"}:
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M2S05: Experiment Setup
    if stage == "M2S05":
        doc = root / "knowledge" / "M2" / "M2S05_experiment_setup.md"
        if not doc.exists():
            messages.append("[FAIL] M2S05: M2S05_experiment_setup.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            design_ok, design_msgs = _check_m2s05_experiment_design(root, text)
            messages.extend(design_msgs)
            ok = ok and design_ok
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M2S06: Full Experiment Plan
    if stage == "M2S06":
        doc = root / "knowledge" / "M2" / "M2S06_full_experiment_plan.md"
        if not doc.exists():
            messages.append("[FAIL] M2S06: M2S06_full_experiment_plan.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            plan_ok, plan_msgs = _check_m2s06_experiment_plan(root, text)
            messages.extend(plan_msgs)
            ok = ok and plan_ok
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    def _load_yaml(path: Path) -> dict[str, Any]:
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # M3S01: Dataset & Environment Review
    if stage == "M3S01":
        doc = root / "knowledge" / "M3" / "M3S01_implementation.md"
        env_cfg = root / "config" / "execution_env.yaml"
        req_lock = root / "experiments" / "requirements.lock"
        req_txt = root / "experiments" / "requirements.txt"
        data_dir = root / "experiments" / "data"
        experiments = root / "experiments"
        execution_mode = ""
        env_data: dict[str, Any] | None = None
        m3s01_text = ""

        if not doc.exists():
            messages.append("[FAIL] M3S01: M3S01_implementation.md not found")
            ok = False
        else:
            m3s01_text = doc.read_text(encoding="utf-8")
            if "数据集" not in m3s01_text and "dataset" not in m3s01_text.lower():
                messages.append("[WARN] M3S01: implementation doc missing dataset review section")
            else:
                messages.append("[PASS] M3S01: dataset review section found")
            if "环境" not in m3s01_text and "execution_env" not in m3s01_text and "local / ssh" not in m3s01_text:
                messages.append("[WARN] M3S01: implementation doc missing environment review section")
            else:
                messages.append("[PASS] M3S01: environment review section found")
            if not _contains_any(m3s01_text, ("long-running", "longrun", "long run", "等待策略", "权限", "m3s01_longrun_ledger")):
                messages.append("[FAIL] M3S01: implementation doc missing long-running execution policy/ledger section")
                ok = False
            else:
                messages.append("[PASS] M3S01: implementation doc includes long-running execution policy/ledger section")

        if not env_cfg.exists():
            messages.append("[FAIL] M3S01: config/execution_env.yaml not found")
            ok = False
        else:
            try:
                env_data = _load_yaml(env_cfg)
                config_ok, config_msgs, execution_mode = _check_m3s01_execution_config(
                    env_data,
                    doc_text=m3s01_text,
                )
                messages.extend(config_msgs)
                ok = ok and config_ok
            except Exception as exc:
                messages.append(f"[FAIL] M3S01: execution_env.yaml unreadable: {exc}")
                ok = False

        sandbox_ok, sandbox_msgs = _check_experiment_sandbox_profile(root, env_data=env_data)
        messages.extend(sandbox_msgs)
        ok = ok and sandbox_ok

        resource_ok, resource_msgs = _check_m3s01_resource_plan(
            root,
            env_data=env_data,
            doc_text=m3s01_text,
        )
        messages.extend(resource_msgs)
        ok = ok and resource_ok

        if not req_lock.exists() and not req_txt.exists():
            messages.append("[FAIL] M3S01: requirements.lock / requirements.txt not found")
            ok = False
        elif req_lock.exists():
            messages.append("[PASS] M3S01: requirements.lock exists")
        else:
            messages.append("[WARN] M3S01: requirements.lock missing, requirements.txt used as fallback")

        if not data_dir.exists():
            messages.append("[WARN] M3S01: experiments/data/ not found yet")
        else:
            dataset_entries = [p for p in data_dir.iterdir() if p.exists()]
            if len(dataset_entries) == 0:
                messages.append("[WARN] M3S01: experiments/data/ is empty")
            else:
                messages.append(f"[PASS] M3S01: dataset directory prepared ({len(dataset_entries)} entries)")

        code_files = list(experiments.rglob("*.py"))
        if len(code_files) < 1:
            messages.append("[FAIL] M3S01: No Python code files found in experiments/")
            ok = False
        else:
            total_lines = sum(len(f.read_text(encoding="utf-8").splitlines()) for f in code_files)
            if total_lines < 20:
                messages.append(f"[FAIL] M3S01: Total code lines < 20 ({total_lines})")
                ok = False
            else:
                messages.append(f"[PASS] M3S01: {len(code_files)} code files, {total_lines} lines")

        longrun_ok, longrun_msgs = _check_m3s01_longrun_ledger(root, execution_mode)
        messages.extend(longrun_msgs)
        ok = ok and longrun_ok

        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M3S02: Baseline Result Review
    if stage == "M3S02":
        baseline_doc = root / "knowledge" / "M3" / "M3S02_baseline_lock.md"
        baseline_contracts = list((root / "experiments" / "baselines").rglob("metric_contract.yaml")) if (root / "experiments" / "baselines").exists() else []
        if not baseline_doc.exists():
            messages.append("[FAIL] M3S02: M3S02_baseline_lock.md not found")
            ok = False
        else:
            text = baseline_doc.read_text(encoding="utf-8")
            if "baseline" not in text.lower() and "基线" not in text:
                messages.append("[FAIL] M3S02: baseline document missing baseline-result review cues")
                ok = False
            else:
                messages.append("[PASS] M3S02: baseline result review document found")
            if not any(term in text for term in ["### Baseline 1", "Baseline 1:", "### Baseline-1", "Baseline-1"]):
                messages.append("[FAIL] M3S02: baseline review missing at least one baseline subsection")
                ok = False
            else:
                messages.append("[PASS] M3S02: baseline subsection found")
            if not any(token in text for token in ["attach", "import", "verify-local-existing", "reproduce", "repair"]):
                messages.append("[FAIL] M3S02: baseline verification path not recorded")
                ok = False
            else:
                messages.append("[PASS] M3S02: baseline verification path recorded")
            if "Smoke Test" not in text and "smoke" not in text.lower():
                messages.append("[FAIL] M3S02: smoke test section not found")
                ok = False
            else:
                messages.append("[PASS] M3S02: smoke test section found")
        if len(baseline_contracts) < 1:
            messages.append("[FAIL] M3S02: No baseline metric_contract.yaml found")
            ok = False
        else:
            verified = 0
            registry_ok, registry_msgs, protocols_by_id = _load_m2_metric_protocol_registry(root)
            messages.extend(
                f"[{msg.split('] ', 1)[0].lstrip('[')}] M3S02 contract upstream: {msg.split('] ', 1)[1]}"
                if msg.startswith("[") and "] " in msg
                else msg
                for msg in registry_msgs
            )
            ok = ok and registry_ok
            for contract in baseline_contracts:
                try:
                    data = _load_yaml(contract)
                except Exception as exc:
                    messages.append(f"[FAIL] M3S02: unreadable contract {contract}: {exc}")
                    ok = False
                    continue
                verdict = str(data.get("verification_verdict", "")).lower()
                primary = data.get("metrics", {}).get("primary", {})
                if not primary.get("key") or primary.get("value") is None:
                    messages.append(f"[FAIL] M3S02: incomplete primary metric in {contract}")
                    ok = False
                    continue
                metric_ok, metric_msgs = _check_m3s02_metric_protocol_alignment(
                    root,
                    f"M3S02 metric_contract[{contract.relative_to(root)}]",
                    data,
                    protocols_by_id,
                    eligible=True,
                    primary=True,
                )
                messages.extend(metric_msgs)
                ok = ok and metric_ok
                if verdict in {"verified_match", "verified_close", "trusted_with_caveats"}:
                    verified += 1
                elif verdict == "diverged":
                    messages.append(f"[FAIL] M3S02: diverged baseline contract: {contract}")
                    ok = False
                else:
                    messages.append(f"[WARN] M3S02: unknown verification verdict in {contract}: {verdict or 'unset'}")
            if verified < 1:
                messages.append("[FAIL] M3S02: No verified baseline contract found")
                ok = False
            else:
                messages.append(f"[PASS] M3S02: {verified} verified baseline contract(s) found")

        lock_ok, lock_msgs = _check_m3s02_baseline_lock_manifest(root, baseline_contracts)
        messages.extend(lock_msgs)
        ok = ok and lock_ok

        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M3S03: Main Experiment Result Review
    if stage == "M3S03":
        main_doc = root / "knowledge" / "M3" / "M3S03_main_experiment.md"
        results = root / "experiments" / "results.tsv"
        runs_dir = root / "experiments" / "runs"
        if not main_doc.exists():
            messages.append("[FAIL] M3S03: M3S03_main_experiment.md not found")
            ok = False
        else:
            text = main_doc.read_text(encoding="utf-8")
            required_sections = [
                "Run Contract",
                "迭代循环记录",
                "Evidence Ladder",
                "随机种子",
            ]
            for marker in required_sections:
                if marker not in text:
                    messages.append(f"[FAIL] M3S03: main experiment doc missing section marker: {marker}")
                    ok = False
                else:
                    messages.append(f"[PASS] M3S03: main experiment doc includes {marker}")

            resource_ok, resource_msgs = _check_m3s03_resource_execution(root, doc_text=text)
            messages.extend(resource_msgs)
            ok = ok and resource_ok

            watchdog_ok, watchdog_msgs = _check_m3s03_runtime_watchdog(root, doc_text=text)
            messages.extend(watchdog_msgs)
            ok = ok and watchdog_ok

            trained_ok, trained_msgs = _check_m3s03_trained_weight_evidence(root, doc_text=text)
            messages.extend(trained_msgs)
            ok = ok and trained_ok

        if not runs_dir.exists():
            messages.append("[FAIL] M3S03: experiments/runs/ not found")
            ok = False
        else:
            run_entries = [p for p in runs_dir.iterdir() if p.exists()]
            if len(run_entries) < 1:
                messages.append("[FAIL] M3S03: experiments/runs/ is empty")
                ok = False
            else:
                messages.append(f"[PASS] M3S03: experiments/runs/ contains {len(run_entries)} entries")

        if not results.exists():
            messages.append("[FAIL] M3S03: experiments/results.tsv not found")
            ok = False
        else:
            lines = [line for line in results.read_text(encoding="utf-8").splitlines() if line.strip()]
            if len(lines) < 2:
                messages.append("[FAIL] M3S03: results.tsv has no data rows")
                ok = False
            else:
                try:
                    import csv

                    rows = list(csv.DictReader(lines, delimiter="\t"))
                    seed_keys = [key for key in (rows[0].keys() if rows else []) if str(key).lower() in {"seed", "random_seed", "rng_seed"}]
                    if not seed_keys:
                        messages.append("[FAIL] M3S03: results.tsv missing seed column")
                        ok = False
                    else:
                        seed_key = seed_keys[0]
                        seed_values = {
                            str(row.get(seed_key, "")).strip()
                            for row in rows
                            if str(row.get(seed_key, "")).strip()
                        }
                        seed_values = {s for s in seed_values if s.lower() not in {"mean", "std", "mean±std", "mean/std"}}
                        if "42" not in seed_values:
                            messages.append("[FAIL] M3S03: results.tsv must use fixed seed 42")
                            ok = False
                        else:
                            messages.append("[PASS] M3S03: results.tsv records fixed seed 42")
                    plan_path = root / "experiments" / "configs" / "resource_plan.yaml"
                    if plan_path.exists():
                        try:
                            import yaml

                            plan_data = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
                        except Exception:
                            plan_data = {}
                        if isinstance(plan_data, dict) and _resource_pool_enabled(plan_data):
                            headers = {str(key).strip().lower() for key in (rows[0].keys() if rows else [])}
                            resource_headers = {"resource_id", "resource_kind", "resource_monitor"}
                            missing_resource_headers = sorted(resource_headers - headers)
                            if missing_resource_headers:
                                messages.append(
                                    "[FAIL] M3S03: multi-resource results.tsv missing columns: "
                                    + ", ".join(missing_resource_headers)
                                )
                                ok = False
                            else:
                                messages.append("[PASS] M3S03: results.tsv includes multi-resource columns")
                except Exception as exc:
                    messages.append(f"[FAIL] M3S03: results.tsv seed parsing failed: {exc}")
                    ok = False
                text = "\n".join(lines).lower()
                if "baseline" not in text:
                    messages.append("[FAIL] M3S03: results.tsv missing baseline comparison rows")
                    ok = False
                else:
                    messages.append("[PASS] M3S03: baseline comparison rows found")
                if "ours" not in text and "proposed" not in text:
                    messages.append("[FAIL] M3S03: results.tsv missing our-method row")
                    ok = False
                else:
                    messages.append("[PASS] M3S03: our-method row found")
                if "42" not in text:
                    messages.append("[FAIL] M3S03: results.tsv missing fixed seed 42 evidence")
                    ok = False
                else:
                    messages.append("[PASS] M3S03: fixed seed 42 evidence found")
                messages.append("[PASS] M3S03: results.tsv exists")

        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M4S01: Post-Experiment Audit
    if stage == "M4S01":
        doc = root / "knowledge" / "M4" / "M4S01_other_findings.md"
        if not doc.exists():
            messages.append("[FAIL] M4S01: M4S01_other_findings.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                "数据质量审计",
                "主实验结果摘要",
                "意外发现",
                "边界条件探索",
                "负面结果",
                "Claim 初筛",
                "分析战役规划草案",
                "论文面向映射初稿",
            ]
            for marker in required:
                if marker not in text:
                    messages.append(f"[FAIL] M4S01: missing section marker: {marker}")
                    ok = False
                else:
                    messages.append(f"[PASS] M4S01: includes {marker}")
            coverage_groups = {
                "ablation": ["消融", "ablation"],
                "mechanism": ["机制", "mechanism"],
                "robustness": ["鲁棒", "robust"],
            }
            missing_groups = [
                name for name, terms in coverage_groups.items()
                if not any(term.lower() in text.lower() for term in terms)
            ]
            if missing_groups:
                messages.append(
                    "[FAIL] M4S01: analysis directions missing coverage for "
                    + ", ".join(missing_groups)
                )
                ok = False
            else:
                messages.append("[PASS] M4S01: analysis directions cover ablation/mechanism/robustness")
            if not _m4_component_claim_matrix_present(text):
                messages.append("[FAIL] M4S01: component/claim analysis matrix missing")
                ok = False
            else:
                messages.append("[PASS] M4S01: component/claim analysis matrix present")
            if not _m4_paper_protocol_present(text):
                messages.append("[FAIL] M4S01: paper protocol adaptation table missing")
                ok = False
            else:
                messages.append("[PASS] M4S01: paper protocol adaptation table present")
            efficiency_decision, efficiency_required, efficiency_waived = _m4_efficiency_decision(text)
            if not efficiency_decision:
                messages.append("[FAIL] M4S01: efficiency_required decision or waiver missing")
                ok = False
            elif efficiency_required and not _m4_efficiency_metrics_present(text):
                messages.append("[FAIL] M4S01: efficiency required but candidate metrics missing")
                ok = False
            elif efficiency_required:
                messages.append("[PASS] M4S01: efficiency analysis trigger and metrics present")
            elif efficiency_waived:
                messages.append("[PASS] M4S01: efficiency analysis explicitly waived/not required")
            else:
                messages.append("[PASS] M4S01: efficiency analysis decision present")
            if not any(term in text for term in ["文献", "数据库", "literature_basis"]):
                messages.append("[FAIL] M4S01: literature/database basis missing")
                ok = False
            else:
                messages.append("[PASS] M4S01: literature/database basis present")

        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M4S02: Deep Analysis Experiment Design
    if stage == "M4S02":
        doc = root / "knowledge" / "M4" / "M4S02_analysis_experiment_design.md"
        if not doc.exists():
            messages.append("[FAIL] M4S02: M4S02_analysis_experiment_design.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                "分析目标",
                "Slice 列表",
                "Comparability Contract",
                "执行信封审计",
            ]
            for marker in required:
                if marker not in text:
                    messages.append(f"[FAIL] M4S02: missing section marker: {marker}")
                    ok = False
                else:
                    messages.append(f"[PASS] M4S02: includes {marker}")
            coverage_groups = {
                "ablation": ["消融", "ablation"],
                "mechanism": ["机制", "mechanism"],
                "robustness": ["鲁棒", "robust"],
                "failure": ["失败", "负面", "failure", "negative"],
            }
            for name, terms in coverage_groups.items():
                if not any(term.lower() in text.lower() for term in terms):
                    messages.append(f"[FAIL] M4S02: missing analysis coverage marker: {name}")
                    ok = False
                else:
                    messages.append(f"[PASS] M4S02: covers {name}")
            if not _m4_component_claim_matrix_present(text):
                messages.append("[FAIL] M4S02: component/claim analysis matrix missing")
                ok = False
            else:
                messages.append("[PASS] M4S02: component/claim analysis matrix present")
            if not _m4_paper_protocol_present(text):
                messages.append("[FAIL] M4S02: paper protocol adaptation table missing")
                ok = False
            else:
                messages.append("[PASS] M4S02: paper protocol adaptation table present")
            efficiency_decision, efficiency_required, efficiency_waived = _m4_efficiency_decision(text)
            if not efficiency_decision:
                messages.append("[FAIL] M4S02: efficiency_required decision or waiver missing")
                ok = False
            elif efficiency_required:
                if not _m4_efficiency_slice_present(text):
                    messages.append("[FAIL] M4S02: efficiency_required=yes but efficiency slice coverage missing")
                    ok = False
                else:
                    messages.append("[PASS] M4S02: efficiency slice coverage present")
                if not _m4_efficiency_metrics_present(text):
                    messages.append("[FAIL] M4S02: efficiency_required=yes but efficiency metrics missing")
                    ok = False
                else:
                    messages.append("[PASS] M4S02: efficiency metrics present")
            elif efficiency_waived:
                messages.append("[PASS] M4S02: efficiency analysis explicitly waived/not required")
            else:
                messages.append("[PASS] M4S02: efficiency analysis decision present")
            if "baseline_inclusion" not in text:
                messages.append("[FAIL] M4S02: baseline comparison contract missing")
                ok = False
            else:
                messages.append("[PASS] M4S02: baseline comparison contract present")
                if "required" not in text.lower():
                    messages.append("[FAIL] M4S02: no baseline_inclusion=required slice found")
                    ok = False
                else:
                    messages.append("[PASS] M4S02: at least one baseline-required slice present")
            if "analysis_type" not in text:
                messages.append("[FAIL] M4S02: analysis_type field missing")
                ok = False
            else:
                messages.append("[PASS] M4S02: analysis_type field present")
            if "evidence_criteria" not in text:
                messages.append("[FAIL] M4S02: evidence_criteria field missing")
                ok = False
            else:
                messages.append("[PASS] M4S02: evidence_criteria field present")
            design_terms = {
                "how target": ("how", "怎么", "机制如何", "如何"),
                "where target": ("where", "哪里", "条件", "场景", "边界"),
                "why target": ("why", "为什么", "原因", "mechanism"),
                "upstream M2/M3 basis": ("M2", "M2S05", "M2S06", "M3", "M3S04", "handoff_M3_M4"),
                "comparison target": ("comparison_target", "比较对象", "comparison target"),
                "expected pattern": ("expected_pattern", "预期模式", "expected pattern"),
                "claim links": ("claim_links", "Claim", "claim"),
            }
            for label, terms in design_terms.items():
                if not _contains_any(text, terms):
                    messages.append(f"[FAIL] M4S02: missing {label}")
                    ok = False
                else:
                    messages.append(f"[PASS] M4S02: includes {label}")
            ana_ids = set(re.findall(r"\bAna-\d+\b", text, flags=re.IGNORECASE))
            if len(ana_ids) < 3:
                messages.append(f"[FAIL] M4S02: fewer than 3 concrete Ana-* slice IDs found ({len(ana_ids)})")
                ok = False
            else:
                messages.append(f"[PASS] M4S02: {len(ana_ids)} concrete Ana-* slice IDs found")
            if "literature_basis" not in text and "数据库" not in text and "文献" not in text:
                messages.append("[FAIL] M4S02: literature/database basis missing")
                ok = False
            else:
                messages.append("[PASS] M4S02: literature/database basis present")
            queue_ok, queue_msgs = _check_m4s02_task_queue(root, text)
            messages.extend(queue_msgs)
            ok = ok and queue_ok
            plan_path = root / "experiments" / "configs" / "resource_plan.yaml"
            if plan_path.exists():
                try:
                    import yaml

                    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
                except Exception:
                    plan = {}
                if isinstance(plan, dict) and _resource_pool_enabled(plan):
                    for label, terms in {
                        "parallelizable slice flags": ("parallelizable", "可并行"),
                        "slice dependencies": ("dependencies", "依赖"),
                        "resource requirements": ("resource_requirements", "资源需求"),
                        "fairness key": ("fairness_key", "公平"),
                    }.items():
                        if not _contains_any(text, terms):
                            messages.append(f"[FAIL] M4S02: multi-resource design missing {label}")
                            ok = False
                        else:
                            messages.append(f"[PASS] M4S02: multi-resource design includes {label}")

        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M4S03: Deep Analysis Experiment Execution
    if stage == "M4S03":
        doc = root / "knowledge" / "M4" / "M4S03_analysis_experiment.md"
        results = root / "experiments" / "analysis_results.tsv"
        if not doc.exists():
            messages.append("[FAIL] M4S03: M4S03_analysis_experiment.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                "执行摘要",
                "Slice 执行记录",
                "负面/失败结果记录",
                "原始数据与日志",
                "初步审查摘要",
            ]
            for marker in required:
                if marker not in text:
                    messages.append(f"[FAIL] M4S03: missing section marker: {marker}")
                    ok = False
                else:
                    messages.append(f"[PASS] M4S03: includes {marker}")
            if not any(term in text for term in ["stage_in_fix", "stage_out_backtrack", "continue", "stage-in", "stage-out"]):
                messages.append("[FAIL] M4S03: missing stage-in/stage-out routing in initial review")
                ok = False
            else:
                messages.append("[PASS] M4S03: initial review includes stage routing")
            if not any(term in text for term in ["environment", "setup", "model", "data", "metric", "method", "unknown", "环境", "模型", "数据", "指标", "方法"]):
                messages.append("[FAIL] M4S03: initial review did not classify abnormal results")
                ok = False
            else:
                messages.append("[PASS] M4S03: initial review classifies abnormal results")
        if not results.exists():
            messages.append("[FAIL] M4S03: experiments/analysis_results.tsv not found")
            ok = False
        else:
            lines = [line for line in results.read_text(encoding="utf-8").splitlines() if line.strip()]
            if len(lines) < 2:
                messages.append("[FAIL] M4S03: experiments/analysis_results.tsv has no data rows")
                ok = False
            else:
                messages.append("[PASS] M4S03: experiments/analysis_results.tsv has data rows")
                headers = {header.strip().lower() for header in lines[0].split("\t") if header.strip()}
                required_headers = {
                    "slice",
                    "analysis_type",
                    "method",
                    "dataset",
                    "split",
                    "seed",
                    "config_id",
                    "run_id",
                    "metric",
                    "value",
                    "baseline_inclusion",
                    "artifact_path",
                    "runtime_sec",
                    "params_m",
                    "peak_mem_mb",
                    "resource_id",
                    "resource_kind",
                    "server_id",
                    "gpu_ids",
                    "resource_monitor",
                    "notes",
                }
                missing_headers = sorted(required_headers - headers)
                if missing_headers:
                    messages.append(
                        "[FAIL] M4S03: analysis_results.tsv missing required columns: "
                        + ", ".join(missing_headers)
                    )
                    ok = False
                else:
                    messages.append("[PASS] M4S03: analysis_results.tsv includes extended M4 schema")
                coverage_ok, coverage_msgs = _check_m4s03_task_queue_coverage(root, lines)
                messages.extend(coverage_msgs)
                ok = ok and coverage_ok

        sandbox_ok, sandbox_msgs = _check_experiment_sandbox_profile(root, require_m4_execution_doc=True)
        messages.extend(sandbox_msgs)
        ok = ok and sandbox_ok

        plan_path = root / "experiments" / "configs" / "resource_plan.yaml"
        if plan_path.exists():
            try:
                import yaml

                plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
            except Exception as exc:
                messages.append(f"[FAIL] M4S03: resource_plan.yaml unreadable: {exc}")
                ok = False
                plan = {}
            if isinstance(plan, dict) and _resource_pool_enabled(plan):
                doc_text = doc.read_text(encoding="utf-8") if doc.exists() else ""
                pool_ok, pool_msgs = _check_resource_pool_plan(
                    root,
                    plan,
                    label="M4S03",
                    require_allocation=True,
                    allocation_name="m4_task_allocation.yaml",
                    doc_text=doc_text,
                )
                messages.extend(pool_msgs)
                ok = ok and pool_ok
                if not _contains_any(doc_text, ("resource_id", "resource_kind", "server_id", "m4_task_allocation", "sync", "同步")):
                    messages.append("[FAIL] M4S03: multi-resource execution record missing resource/sync evidence")
                    ok = False
                else:
                    messages.append("[PASS] M4S03: multi-resource execution record includes resource/sync evidence")

        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M3S04: Result Validation
    if stage == "M3S04":
        m3s04_ok, m3s04_msgs = _check_m3s04_result_validation(root)
        messages.extend(m3s04_msgs)
        ok = ok and m3s04_ok

    # M4S04: Analysis Results Integration
    if stage == "M4S04":
        m4s04_ok, m4s04_msgs = _check_m4s04_analysis_results(root)
        messages.extend(m4s04_msgs)
        ok = ok and m4s04_ok

    # M5S01: Pre-Write Audit & Contribution Articulation
    if stage == "M5S01":
        m5s01_ok, m5s01_msgs = _check_m5s01_prewrite_audit(root)
        messages.extend(m5s01_msgs)
        ok = ok and m5s01_ok
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M5S02: Paper Outline
    if stage == "M5S02":
        m5s02_ok, m5s02_msgs = _check_m5s02_outline_profile(root)
        messages.extend(m5s02_msgs)
        ok = ok and m5s02_ok
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M5S03: Introduction & Related Work
    if stage == "M5S03":
        doc = root / "knowledge" / "M5" / "M5S03_introduction_relatedwork.md"
        if not doc.exists():
            messages.append("[FAIL] M5S03: knowledge/M5/M5S03_introduction_relatedwork.md missing")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                ("introduction", "Introduction"),
                ("related work", "Related Work"),
                ("contribution", "贡献"),
            ]
            for terms in required:
                if not _contains_any(text, terms):
                    messages.append(f"[FAIL] M5S03: missing required writing signal: {terms[0]}")
                    ok = False
                else:
                    messages.append(f"[PASS] M5S03: includes {terms[0]}")
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M5S04: Methodology
    if stage == "M5S04":
        doc = root / "knowledge" / "M5" / "M5S04_methodology.md"
        if not doc.exists():
            messages.append("[FAIL] M5S04: knowledge/M5/M5S04_methodology.md missing")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                ("problem formulation", "问题定义"),
                ("method", "方法"),
                ("algorithm", "算法"),
            ]
            for terms in required:
                if not _contains_any(text, terms):
                    messages.append(f"[FAIL] M5S04: missing required methodology signal: {terms[0]}")
                    ok = False
                else:
                    messages.append(f"[PASS] M5S04: includes {terms[0]}")
            if not _contains_any(text, ("架构", "机制图", "figure", "gpt-image-2", "draw.io", "drawio", "generated-images")):
                messages.append("[FAIL] M5S04: architecture/mechanism figure provenance missing")
                ok = False
            else:
                messages.append("[PASS] M5S04: architecture/mechanism figure provenance present")
            if not _contains_any(text, ("gpt-image-2", "image2")):
                messages.append("[FAIL] M5S04: method/framework figures must record image2/gpt-image-2 usage")
                ok = False
            else:
                messages.append("[PASS] M5S04: method/framework figures record image2/gpt-image-2 usage")
            if not _contains_any(text, ("style preset", "figure style profile", "venue", "palette", "richness")):
                messages.append("[FAIL] M5S04: figure style preset/source missing or too weak")
                ok = False
            else:
                messages.append("[PASS] M5S04: figure style preset/source documented")
            if not _contains_any(text, ("paper-framework-figure-studio-pro", "framework figure studio", "c-narcissus")):
                messages.append("[FAIL] M5S04: paper-framework-figure-studio-pro style reference missing")
                ok = False
            else:
                messages.append("[PASS] M5S04: paper-framework-figure-studio-pro style reference documented")
            if not _contains_any(text, ("allowed labels", "forbidden invented labels", "不得自行补充", "no invented", "禁止发明")):
                messages.append("[FAIL] M5S04: allowed/forbidden label boundary missing")
                ok = False
            else:
                messages.append("[PASS] M5S04: allowed/forbidden label boundary documented")
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M5S05: Experiments & Results
    if stage == "M5S05":
        doc = root / "knowledge" / "M5" / "M5S05_experiments_results.md"
        if not doc.exists():
            messages.append("[FAIL] M5S05: knowledge/M5/M5S05_experiments_results.md missing")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                ("dataset", "数据集"),
                ("baseline", "Baseline", "基线"),
                ("results", "结果"),
                ("provenance", "绘图脚本", "数据源"),
                ("nature-figure", "Nature figure", "nature figure"),
            ]
            for terms in required:
                if not _contains_any(text, terms):
                    messages.append(f"[FAIL] M5S05: missing required experiment signal: {terms[0]}")
                    ok = False
                else:
                    messages.append(f"[PASS] M5S05: includes {terms[0]}")
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M5S06: Analysis & Discussion
    if stage == "M5S06":
        doc = root / "knowledge" / "M5" / "M5S06_analysis_discussion.md"
        if not doc.exists():
            messages.append("[FAIL] M5S06: knowledge/M5/M5S06_analysis_discussion.md missing")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                ("analysis", "分析"),
                ("discussion", "讨论"),
                ("limitations", "limitations", "局限"),
            ]
            for terms in required:
                if not _contains_any(text, terms):
                    messages.append(
                        f"[FAIL] M5S06: missing required discussion signal: {terms[0]}"
                    )
                    ok = False
                else:
                    messages.append(f"[PASS] M5S06: includes {terms[0]}")
            if not _contains_any(text, ("negative", "failure", "failed", "负面", "失败", "边界")):
                messages.append("[FAIL] M5S06: no explicit limitations or negative-result discussion found")
                ok = False
            else:
                messages.append("[PASS] M5S06: limitations / negative-result discussion present")
            if not _contains_any(
                text,
                ("图来源", "backend", "gpt-image-2", "draw.io", "drawio", "plt", "matplotlib", "seaborn", "无新增分析图", "no analysis figure"),
            ):
                messages.append("[FAIL] M5S06: analysis figure provenance missing")
                ok = False
            else:
                messages.append("[PASS] M5S06: analysis figure provenance present")
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M5S07: Abstract & Conclusion
    if stage == "M5S07":
        doc = root / "knowledge" / "M5" / "M5S07_abstract_conclusion.md"
        if not doc.exists():
            messages.append("[FAIL] M5S07: knowledge/M5/M5S07_abstract_conclusion.md missing")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                ("abstract", "摘要"),
                ("conclusion", "结论"),
            ]
            for terms in required:
                if not _contains_any(text, terms):
                    messages.append(f"[FAIL] M5S07: missing required section signal: {terms[0]}")
                    ok = False
                else:
                    messages.append(f"[PASS] M5S07: includes {terms[0]}")
            if not _contains_any(text, ("数值一致", "一致性", "consistent", "consistency")):
                messages.append("[FAIL] M5S07: numerical consistency check not documented")
                ok = False
            else:
                messages.append("[PASS] M5S07: numerical consistency check documented")
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M5S09: Full-Polish & Narrative Coherence Review
    if stage == "M5S09":
        doc = root / "knowledge" / "M5" / "M5S09_full_polish.md"
        tex = root / "artifacts" / "paper.tex"
        pdf = root / "artifacts" / "paper.pdf"
        refs = root / "artifacts" / "refs.bib"
        handoff = root / "knowledge" / "handoff_M5_completion.md"
        if not doc.exists():
            messages.append("[FAIL] M5S09: knowledge/M5/M5S09_full_polish.md missing")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                ("narrative coherence", "叙事连贯", "承诺兑现"),
                ("Intro-Method", "Introduction-Method", "Intro Method"),
                ("Method-Experiments", "Method Experiments"),
                ("Experiments-Analysis", "Experiments Analysis", "M5S05", "M5S06"),
                ("terminology consistency", "术语一致"),
                ("numerical consistency", "数值一致"),
                ("language refinement", "语言精炼", "润色"),
                ("paper.tex", "LaTeX", "latex"),
                ("paper.pdf", "PDF"),
                ("recompile", "重新编译", "compile"),
                ("Anti-Leakage", "anti leakage", "防泄露"),
            ]
            for terms in required:
                if not _contains_any(text, terms):
                    messages.append(f"[FAIL] M5S09: missing required polish signal: {terms[0]}")
                    ok = False
                else:
                    messages.append(f"[PASS] M5S09: includes {terms[0]}")
        for label, path in {
            "artifacts/paper.tex": tex,
            "artifacts/paper.pdf": pdf,
            "artifacts/refs.bib": refs,
            "knowledge/handoff_M5_completion.md": handoff,
        }.items():
            if not path.exists() or not path.read_bytes():
                messages.append(f"[FAIL] M5S09: required final artifact missing or empty: {label}")
                ok = False
            else:
                messages.append(f"[PASS] M5S09: required final artifact present: {label}")
        if pdf.exists() and pdf.read_bytes() and not pdf.read_bytes().startswith(b"%PDF"):
            messages.append("[FAIL] M5S09: artifacts/paper.pdf does not look like a PDF")
            ok = False
        elif pdf.exists() and pdf.read_bytes():
            messages.append("[PASS] M5S09: paper.pdf exists and has PDF header")
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M5S08: Final Compilation
    if stage == "M5S08":
        m5s08_ok, m5s08_msgs = _check_m5s08_final_compilation(root)
        messages.extend(m5s08_msgs)
        ok = ok and m5s08_ok
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M6S01: Submission Audit & Package Assembly
    if stage == "M6S01":
        doc = root / "knowledge" / "M6" / "M6S01_submission_audit.md"
        handoff = root / "knowledge" / "handoff_M5_completion.md"
        pdf = root / "artifacts" / "paper.pdf"
        tex = root / "artifacts" / "paper.tex"
        if not doc.exists():
            messages.append("[FAIL] M6S01: M6S01_submission_audit.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                ("integrity audit", "完整性审计", "投稿包"),
                ("venue compliance", "Venue", "页数", "匿名"),
                ("audit conclusion", "审计结论", "READY", "NOT_READY"),
            ]
            for terms in required:
                if not _contains_any(text, terms):
                    messages.append(f"[FAIL] M6S01: missing submission audit signal: {terms[0]}")
                    ok = False
                else:
                    messages.append(f"[PASS] M6S01: includes {terms[0]}")
            if not _contains_any(text, ("Blockers", "Warnings", "blocker", "warning")):
                messages.append("[FAIL] M6S01: blockers/warnings section missing")
                ok = False
            else:
                messages.append("[PASS] M6S01: blockers/warnings section present")
        for name, path in {
            "handoff_M5_completion.md": handoff,
            "artifacts/paper.pdf": pdf,
            "artifacts/paper.tex": tex,
        }.items():
            if not path.exists():
                messages.append(f"[FAIL] M6S01: required file missing: {name}")
                ok = False
            else:
                messages.append(f"[PASS] M6S01: required file present: {name}")
        internal_ok, internal_msgs = _check_m6_internal_peer_review(root)
        messages.extend(internal_msgs)
        ok = ok and internal_ok
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M6S02: External Submission Review
    if stage == "M6S02":
        doc = root / "knowledge" / "M6" / "M6S02_external_review_submission.md"
        log = root / "knowledge" / "M6" / "M6S02_submission_log.json"
        internal_ok, internal_msgs = _check_m6_internal_peer_review(root)
        messages.extend(internal_msgs)
        ok = ok and internal_ok
        if not doc.exists():
            messages.append("[FAIL] M6S02: M6S02_external_review_submission.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                ("submission info", "提交信息", "paperreview.ai"),
                ("submission status", "提交状态", "tracking"),
                ("next step", "下一步", "review邮件", "审稿邮件"),
            ]
            for terms in required:
                if not _contains_any(text, terms):
                    messages.append(f"[FAIL] M6S02: missing submission record signal: {terms[0]}")
                    ok = False
                else:
                    messages.append(f"[PASS] M6S02: includes {terms[0]}")
        submission_ok, submission_msgs = _check_m6_submission_log(root, label="M6S02")
        messages.extend(submission_msgs)
        ok = ok and submission_ok
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M6S03: Review Parsing
    if stage == "M6S03":
        doc = root / "knowledge" / "M6" / "M6S03_review_parsing.md"
        email_json = root / "knowledge" / "M6" / "M6S03_review_email.json"
        matrix = root / "knowledge" / "M6" / "M6S03_review_matrix.md"
        if not doc.exists():
            messages.append("[FAIL] M6S03: M6S03_review_parsing.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                ("overall score", "总体评分", "Soundness"),
                ("review matrix", "Review Matrix", "PR-"),
                ("atomicization", "原子化", "class", "severity"),
            ]
            for terms in required:
                if not _contains_any(text, terms):
                    messages.append(f"[FAIL] M6S03: missing review parsing signal: {terms[0]}")
                    ok = False
                else:
                    messages.append(f"[PASS] M6S03: includes {terms[0]}")
        for name, path in {
            "knowledge/M6/M6S03_review_email.json": email_json,
            "knowledge/M6/M6S03_review_matrix.md": matrix,
        }.items():
            if not path.exists():
                messages.append(f"[FAIL] M6S03: required file missing: {name}")
                ok = False
            else:
                messages.append(f"[PASS] M6S03: required file present: {name}")
        email_ok, email_msgs = _check_m6_review_email(root, label="M6S03")
        messages.extend(email_msgs)
        ok = ok and email_ok
        matrix_ok, matrix_msgs = _check_m6_review_matrix(root, label="M6S03")
        messages.extend(matrix_msgs)
        ok = ok and matrix_ok
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M6S04: Rebuttal Strategy & Backtrack Planning
    if stage == "M6S04":
        doc = root / "knowledge" / "M6" / "M6S04_rebuttal_strategy.md"
        action_plan = root / "knowledge" / "M6" / "M6S04_action_plan.md"
        if not doc.exists():
            messages.append("[FAIL] M6S04: M6S04_rebuttal_strategy.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                ("classification summary", "意见分类汇总", "Action Plan"),
                ("backtrack mapping", "回溯目标映射", "target_stage"),
                ("honest limitation", "诚实限制", "cannot_fully_address"),
            ]
            for terms in required:
                if not _contains_any(text, terms):
                    messages.append(f"[FAIL] M6S04: missing rebuttal strategy signal: {terms[0]}")
                    ok = False
                else:
                    messages.append(f"[PASS] M6S04: includes {terms[0]}")
        if not action_plan.exists():
            messages.append("[FAIL] M6S04: M6S04_action_plan.md not found")
            ok = False
        else:
            text = action_plan.read_text(encoding="utf-8")
            required_fields = [
                "target_stage",
                "required_fix",
                "success_criteria",
                "rebuild_mode",
                "rerun_scope",
                "priority",
            ]
            for field in required_fields:
                if field not in text:
                    messages.append(f"[FAIL] M6S04: action plan missing field: {field}")
                    ok = False
                else:
                    messages.append(f"[PASS] M6S04: action plan includes {field}")
            if "PR-" not in text:
                messages.append("[FAIL] M6S04: action plan missing review item ids")
                ok = False
            else:
                messages.append("[PASS] M6S04: action plan references review item ids")
        item_ok, item_msgs = _check_m6s04_item_coverage(root)
        messages.extend(item_msgs)
        ok = ok and item_ok
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M6S05: Revision Execution
    if stage == "M6S05":
        doc = root / "knowledge" / "M6" / "M6S05_revision_execution.md"
        pdf = root / "artifacts" / "paper.pdf"
        if not doc.exists():
            messages.append("[FAIL] M6S05: M6S05_revision_execution.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                ("revision list", "修订清单", "Action Plan ID"),
                ("recompile", "重新编译", "paper.pdf"),
                ("negative results", "负面结果", "failed"),
            ]
            for terms in required:
                if not _contains_any(text, terms):
                    messages.append(f"[FAIL] M6S05: missing revision execution signal: {terms[0]}")
                    ok = False
                else:
                    messages.append(f"[PASS] M6S05: includes {terms[0]}")
        item_ok, item_msgs = _check_m6s05_item_execution(root)
        messages.extend(item_msgs)
        ok = ok and item_ok
        if not pdf.exists():
            messages.append("[FAIL] M6S05: artifacts/paper.pdf missing after revision")
            ok = False
        else:
            messages.append("[PASS] M6S05: artifacts/paper.pdf exists after revision")
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    # M6S06: Revision Validation & Completion
    if stage == "M6S06":
        doc = root / "knowledge" / "M6" / "M6S06_revision_validation.md"
        handoff = root / "knowledge" / "handoff_M6_completion.md"
        pdf = root / "artifacts" / "paper.pdf"
        final_pdf = root / "artifacts" / "submission_package" / "paper_final.pdf"
        source_zip = root / "artifacts" / "submission_package" / "source.zip"
        if not doc.exists():
            messages.append("[FAIL] M6S06: M6S06_revision_validation.md not found")
            ok = False
        else:
            text = doc.read_text(encoding="utf-8")
            required = [
                ("resolution rate", "综合解决度", "High 解决率"),
                ("quality preservation", "质量保持度", "Gate G5"),
                ("completion verdict", "判定结果", "PASS"),
                ("external review evidence", "外部审稿证据", "M6S02_submission_log", "M6S03_review_email"),
            ]
            for terms in required:
                if not _contains_any(text, terms):
                    messages.append(f"[FAIL] M6S06: missing validation signal: {terms[0]}")
                    ok = False
                else:
                    messages.append(f"[PASS] M6S06: includes {terms[0]}")
            if not re.search(r"(?im)^\s*(?:\*\*)?判定结果(?:\*\*)?\s*[:：]\s*PASS\s*$", text):
                messages.append("[FAIL] M6S06: final verdict is not explicit PASS")
                ok = False
            else:
                messages.append("[PASS] M6S06: final verdict PASS is explicit")
        item_ok, item_msgs = _check_m6s06_item_resolution(root)
        messages.extend(item_msgs)
        ok = ok and item_ok
        for name, path in {
            "handoff_M6_completion.md": handoff,
            "artifacts/paper.pdf": pdf,
            "artifacts/submission_package/paper_final.pdf": final_pdf,
            "artifacts/submission_package/source.zip": source_zip,
        }.items():
            if not path.exists():
                messages.append(f"[FAIL] M6S06: required file missing: {name}")
                ok = False
            else:
                messages.append(f"[PASS] M6S06: required file present: {name}")
        submission_ok, submission_msgs = _check_m6_submission_log(root, label="M6S06")
        messages.extend(submission_msgs)
        ok = ok and submission_ok
        email_ok, email_msgs = _check_m6_review_email(root, label="M6S06")
        messages.extend(email_msgs)
        ok = ok and email_ok
        matrix_ok, matrix_msgs = _check_m6_review_matrix(root, label="M6S06")
        messages.extend(matrix_msgs)
        ok = ok and matrix_ok
        review_ok, review_msgs = _check_stage_reviews(root, stage)
        messages.extend(review_msgs)
        ok = ok and review_ok

    if not messages:
        messages.append(f"[INFO] No specific checks for {stage}")

    return ok, messages
