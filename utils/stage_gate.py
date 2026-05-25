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


def _check_m2s05_experiment_design(text: str) -> tuple[bool, list[str]]:
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
        "random seeds": ("随机种子", "seed"),
        "statistical test": ("统计检验", "t-test", "wilcoxon", "bootstrap", "显著性"),
        "reproducibility checklist": ("可复现", "reproducibility", "requirements", "git commit"),
    }
    for label, terms in required_signals.items():
        if not _contains_any(text, terms):
            messages.append(f"[FAIL] M2S05: missing {label}")
            ok = False
        else:
            messages.append(f"[PASS] M2S05: includes {label}")

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

    return ok, messages


def _check_m2s06_experiment_plan(text: str) -> tuple[bool, list[str]]:
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
        "statistical validation": ("统计显著性", "p-value", "effect size", "效应量", "置信区间", "多重比较"),
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
            missing_metric = [field for field in ("key", "value", "std") if not _nonempty(primary.get(field))]
            if missing_metric:
                messages.append(f"[FAIL] M3S04: manifest.yaml primary_metric missing {', '.join(missing_metric)}")
                ok = False
            else:
                messages.append("[PASS] M3S04: manifest.yaml primary_metric includes key/value/std")
        seeds = manifest.get("seeds")
        if not isinstance(seeds, list) or len({str(seed) for seed in seeds if _nonempty(seed)}) < 3:
            messages.append("[FAIL] M3S04: manifest.yaml must record at least 3 seeds")
            ok = False
        else:
            messages.append("[PASS] M3S04: manifest.yaml records at least 3 seeds")

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
            missing_metric = [field for field in ("key", "value", "std") if not _nonempty(primary.get(field))]
            if missing_metric:
                messages.append(f"[FAIL] M3S04: metric_contract.yaml primary metric missing {', '.join(missing_metric)}")
                ok = False
            else:
                messages.append("[PASS] M3S04: metric_contract.yaml primary metric includes key/value/std")

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
            if not any(header in headers for header in ("std", "stderr", "ci", "confidence_interval")):
                messages.append("[FAIL] M3S04: comparison_table.csv missing uncertainty column")
                ok = False
            else:
                messages.append("[PASS] M3S04: comparison_table.csv includes uncertainty column")

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
    handoff = root / "knowledge" / "handoff_M5_completion.md"
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

    if not handoff.exists() or not handoff.read_text(encoding="utf-8").strip():
        messages.append("[FAIL] M5S08: handoff_M5_completion.md missing or empty")
        ok = False
    else:
        handoff_text = handoff.read_text(encoding="utf-8")
        handoff_terms = {
            "M6 readiness": ("M6", "submission", "投稿", "ready"),
            "paper artifacts": ("artifacts/paper.pdf", "artifacts/paper.tex", "refs.bib"),
            "compilation status": ("PASS", "compiled", "编译", "verdict"),
        }
        for label, terms in handoff_terms.items():
            if not _contains_any(handoff_text, terms):
                messages.append(f"[FAIL] M5S08: handoff_M5_completion.md missing {label}")
                ok = False
            else:
                messages.append(f"[PASS] M5S08: handoff_M5_completion.md includes {label}")

    return ok, messages


def _analysis_type_coverage(text: str) -> set[str]:
    lowered = text.lower()
    groups = {
        "ablation": ("ablation", "消融"),
        "mechanism": ("mechanism", "机制", "visualization", "可视化", "probe", "attribution"),
        "robustness": ("robust", "鲁棒", "stress", "noise", "shift", "泛化"),
        "failure": ("failure", "negative", "失败", "负面", "边界"),
    }
    return {name for name, terms in groups.items() if any(term in lowered for term in terms)}


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
                    "metric": {"metric"},
                    "value/result": {"value", "result", "mean"},
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
                if "baseline" not in joined_rows and "基线" not in joined_rows:
                    messages.append("[FAIL] M4S04: analysis_results.tsv missing baseline comparison rows")
                    ok = False
                else:
                    messages.append("[PASS] M4S04: analysis_results.tsv includes baseline comparison rows")
                if "ours" not in joined_rows and "proposed" not in joined_rows and "our_method" not in joined_rows:
                    messages.append("[FAIL] M4S04: analysis_results.tsv missing ours/proposed rows")
                    ok = False
                else:
                    messages.append("[PASS] M4S04: analysis_results.tsv includes ours/proposed rows")

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
                "workspace_path": "ssh workspace_path",
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
            design_ok, design_msgs = _check_m2s05_experiment_design(text)
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
            plan_ok, plan_msgs = _check_m2s06_experiment_plan(text)
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
                        if len(seed_values) < 3:
                            messages.append(f"[FAIL] M3S03: results.tsv seed coverage insufficient (<3 unique seeds, got {len(seed_values)})")
                            ok = False
                        else:
                            messages.append(f"[PASS] M3S03: results.tsv includes {len(seed_values)} unique seeds")
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
                if "mean" not in text and "std" not in text:
                    messages.append("[FAIL] M3S03: results.tsv missing summary statistics")
                    ok = False
                else:
                    messages.append("[PASS] M3S03: summary statistics found")
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

        sandbox_ok, sandbox_msgs = _check_experiment_sandbox_profile(root, require_m4_execution_doc=True)
        messages.extend(sandbox_msgs)
        ok = ok and sandbox_ok

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
