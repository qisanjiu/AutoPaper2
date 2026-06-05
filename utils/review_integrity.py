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
        r"\b(todo|tbd|placeholder|to\s+be\s+filled|to\s+be\s+done)\b",
        r"(待定|暂定|占位|待补|待处理|未完成|未解决|失败|缺失|不可用|无法下载|下载失败|未下载|未验证|仍在运行|等待人工|需要人工|需要用户)",
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
