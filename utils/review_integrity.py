"""Review/gate integrity helpers.

These checks catch contradictory PASS documents: a review or gate cannot say
PASS while also saying evidence is pending, unavailable, ambiguous, or waiting
for manual work.
"""

from __future__ import annotations

import re


_NEGATING_OK_RE = re.compile(
    r"(?i)\b(no|none|zero|0|resolved|completed|passed|verified|not applicable|n/a)\b|"
    r"(无|没有|不存在|已解决|已完成|已通过|已验证|不适用)"
)

_BLOCKER_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(pending|blocked|failed|unresolved|missing|unavailable)\b",
        r"\b(not\s+done|not\s+complete|not\s+completed|not\s+verified|not\s+available)\b",
        r"\b(unable|cannot|can't)\s+(?:to\s+)?(?:download|fetch|acquire|load|verify|access)",
        r"\b(download|fetch|acquire|checkpoint|dataset|baseline).{0,32}\b(failed|unavailable|missing|pending|blocked)\b",
        r"\b(wait(?:ing)?\s+for\s+(?:user|human|manual|approval|credentials?))\b",
        r"\b(still\s+running|running\s+on\s+server|queued)\b",
        r"\b(ineligible|not\s+eligible|not\s+comparable|non[-\s]?comparable)\b",
        r"\b(not\s+implemented|not\s+run|not\s+executed|not\s+trained|undertrained)\b",
        r"\b(proxy\s+only|reference\s+only|rough\s+reference|used\s+for\s+rough\s+reference)\b",
        r"\b(insufficient\s+training|baseline\s+(?:match|eligibility|comparability)\s*(?:fail|failed|no))\b",
        r"\b(?:data|metric|label|target|test[-\s]?set)?\s*leakage\b",
        r"\b(shortcut|invalid\s+result|diagnostic\s+only|outside\s+(?:normal_)?reference\s+range)\b",
        r"\b(defer(?:red)?\s+to\s+M4|address(?:ed)?\s+in\s+M4)\b",
        r"\b(todo|tbd|placeholder|to\s+be\s+filled|to\s+be\s+done)\b",
        r"(待定|暂定|占位|待补|待处理|未完成|未解决|失败|缺失|不可用|无法下载|下载失败|未下载|未验证|仍在运行|等待人工|需要人工|需要用户|不合格|不可比较|未实现|未运行|训练不足|仅作参考|只作参考|泄露|无效结果|诊断结果|推迟到M4|留到M4)",
        r"(数据集|dataset|baseline|基线|checkpoint|权重).{0,24}(无法|失败|缺失|不可用|未下载|未验证|等待|待人工)",
    )
)

_AMBIGUOUS_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(maybe|probably|likely|roughly|generally|mostly|seems?|appears?|should\s+be|could\s+be)\b",
        r"\b(acceptable\s+enough|good\s+enough|basically\s+ok|looks\s+ok)\b",
        r"(可能|大概|大致|基本可以|基本通过|看起来|似乎|应该可以|差不多|暂时通过|先通过|先推进)",
    )
)


def _line_is_negated_ok(line: str) -> bool:
    """Return True for explicit no-problem lines such as unresolved issues: 0."""
    return bool(_NEGATING_OK_RE.search(line))


def find_pass_integrity_issues(text: str) -> list[str]:
    """Return contradictory/blocking phrases that make a PASS invalid.

    The scan is line based so the caller can report concise evidence. Lines
    that explicitly say there are zero/no unresolved items are exempt.
    """
    issues: list[str] = []
    in_fence = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line:
            continue
        lowered = line.lower()
        if lowered.startswith("|---") or lowered.startswith("---"):
            continue
        if _line_is_negated_ok(line):
            continue
        if any(pattern.search(line) for pattern in _BLOCKER_PATTERNS):
            issues.append(line[:220])
            continue
        if any(pattern.search(line) for pattern in _AMBIGUOUS_PATTERNS):
            issues.append(line[:220])
    return issues


REPAIR_ADVICE_REQUIRED_FIELDS: tuple[str, ...] = (
    "target_stage",
    "blocking_reason",
    "required_fix",
    "success_criteria",
    "evidence_paths",
    "rebuild_mode",
    "rerun_scope",
    "handoff_updates",
)

_REPAIR_FIELD_VALUE_PATTERNS: dict[str, re.Pattern[str]] = {
    field: re.compile(
        rf"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?`?{re.escape(field)}`?(?:\*\*)?\s*[:：]\s*(.+?)\s*$"
    )
    for field in REPAIR_ADVICE_REQUIRED_FIELDS
}

_CODE_EVIDENCE_EXTENSIONS = (
    ".py",
    ".ipynb",
    ".sh",
    ".bash",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".txt",
    ".log",
    ".tsv",
    ".csv",
)


def extract_review_field_value(text: str, field: str) -> str:
    """Extract a single repair-advice field value from Markdown review text."""
    pattern = _REPAIR_FIELD_VALUE_PATTERNS.get(field)
    if pattern is None:
        return ""
    match = pattern.search(text)
    return match.group(1).strip(" `*") if match else ""


def missing_review_repair_fields(
    text: str,
    fields: tuple[str, ...] = REPAIR_ADVICE_REQUIRED_FIELDS,
) -> list[str]:
    """Return missing or empty repair-advice fields from Markdown review text."""
    missing: list[str] = []
    for field in fields:
        if not extract_review_field_value(text, field):
            missing.append(field)
    return missing


def _split_review_path_list(value: str) -> list[str]:
    return [item.strip().strip("`*[]()") for item in re.split(r"[,;\n]+", value) if item.strip()]


def _extract_evidence_checked_paths(text: str) -> list[str]:
    """Extract likely evidence paths from Evidence Checked and evidence_paths."""
    paths = _split_review_path_list(extract_review_field_value(text, "evidence_paths"))
    in_evidence = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if re.match(r"^##+\s+evidence\s+checked\b", lowered):
            in_evidence = True
            continue
        if in_evidence and line.startswith("##"):
            in_evidence = False
        if not in_evidence or not line.startswith(("-", "*")):
            continue
        body = re.sub(r"^[-*]\s*", "", line).strip()
        match = re.search(
            r"(?:project:|framework:)?[A-Za-z0-9_.@+/\-]+\.[A-Za-z0-9]+",
            body,
        )
        if match:
            paths.append(match.group(0).strip("`*[]()"))
            continue
        candidate = body.split(":", 1)[0].strip().strip("`*[]()")
        if candidate:
            paths.append(candidate)
    return paths


def _path_is_direct_code_evidence(path_text: str) -> bool:
    """Return True for direct non-Markdown code/config/log/table evidence paths."""
    path = path_text.strip().strip("`*[]()")
    if not path:
        return False
    path = re.sub(r"^(?:project|framework):", "", path)
    lowered = path.lower()
    if lowered.endswith((".md", ".markdown", ".tex", ".pdf")):
        return False
    return lowered.endswith(_CODE_EVIDENCE_EXTENSIONS)


def _required_fix_is_code_level_patch(required_fix: str) -> bool:
    """Detect exact implementation prescriptions rather than task-level advice."""
    lowered = required_fix.lower()
    code_level_patterns = (
        r"\bline\s+\d+\b",
        r"\b(?:change|replace|edit|modify|rewrite|set)\b.{0,80}\b(?:to|with|as)\b.{0,160}`[^`]+`",
        r"\b(?:change|replace|edit|modify|rewrite|set)\b.{0,120}\.(?:py|ipynb|sh|yaml|yml|json|toml|ini|cfg)\b",
        r"\b(?:def|class)\s+[a-zA-Z_]\w*\s*\(",
        r"\bself\.[a-zA-Z_]\w*\s*\(",
        r"\btorch\.[a-zA-Z_]\w*",
        r"\bpython\s+[-\w./]+\.py\b",
        r"\b(?:pip|pytest|bash|sh)\s+[-\w./]",
        r"`[^`]*(?:self\.|torch\.|def\s+|class\s+|\.py|\.yaml|\.yml|\.json|python\s+)[^`]*`",
    )
    task_level_patterns = (
        "inspect",
        "verify",
        "diagnose",
        "triage",
        "audit",
        "review implementation",
        "检查",
        "验证",
        "排查",
        "审计",
    )
    if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in code_level_patterns):
        return True
    if "experiments/" in lowered and not any(term in lowered for term in task_level_patterns):
        return True
    return False


def check_repair_advice_evidence_scope(label: str, text: str) -> tuple[bool, list[str]]:
    """Require code-level repair advice to cite direct code/config/log evidence."""
    required_fix = extract_review_field_value(text, "required_fix")
    if not required_fix or not _required_fix_is_code_level_patch(required_fix):
        return True, []

    evidence_paths = _extract_evidence_checked_paths(text)
    if any(_path_is_direct_code_evidence(path) for path in evidence_paths):
        return True, [f"[PASS] {label}: code-level repair advice is backed by direct code/config/log evidence"]

    return False, [
        f"[FAIL] {label}: code-level repair advice lacks direct code/config/log evidence; "
        "when the reviewer only checked Markdown outputs, required_fix must be task-level "
        "(inspect/verify/repair/add evidence/rerun) rather than an exact patch"
    ]
