"""Section-anchor helpers for safer in-place Markdown revisions."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

ANCHOR_RE = re.compile(
    r"^<!-- ap2:section id=(?P<id>[A-Za-z0-9_.:-]+) sha256=(?P<sha>[a-f0-9]{64}) -->$",
    re.MULTILINE,
)
HEADING_RE = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class SectionCheck:
    section_id: str
    expected_sha256: str
    actual_sha256: str
    ok: bool


def hash_section_content(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _slug(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"`([^`]+)`", r"\1", lowered)
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", lowered)
    return lowered.strip("_") or "section"


def strip_section_anchors(text: str) -> str:
    return ANCHOR_RE.sub("", text).replace("\n\n\n", "\n\n")


def add_or_refresh_heading_anchors(text: str, namespace: str) -> str:
    """Insert or refresh anchors before Markdown headings.

    Existing AutoPaper2 anchors are stripped first so the output has one marker
    per heading and hashes reflect the current section body.
    """
    clean = strip_section_anchors(text)
    matches = list(HEADING_RE.finditer(clean))
    if not matches:
        return clean

    parts: list[str] = []
    cursor = 0
    seen: dict[str, int] = {}
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(clean)
        section = clean[start:end]
        title = match.group("title")
        base_id = f"{namespace}.{_slug(title)}" if namespace else _slug(title)
        count = seen.get(base_id, 0) + 1
        seen[base_id] = count
        section_id = base_id if count == 1 else f"{base_id}.{count}"
        parts.append(clean[cursor:start])
        parts.append(f"<!-- ap2:section id={section_id} sha256={hash_section_content(section)} -->\n")
        parts.append(section)
        cursor = end
    parts.append(clean[cursor:])
    return "".join(parts)


def verify_section_anchors(text: str) -> list[SectionCheck]:
    matches = list(ANCHOR_RE.finditer(text))
    checks: list[SectionCheck] = []
    for idx, match in enumerate(matches):
        content_start = match.end()
        if content_start < len(text) and text[content_start] == "\n":
            content_start += 1
        content_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        content = text[content_start:content_end]
        actual = hash_section_content(content)
        expected = match.group("sha")
        checks.append(
            SectionCheck(
                section_id=match.group("id"),
                expected_sha256=expected,
                actual_sha256=actual,
                ok=actual == expected,
            )
        )
    return checks
