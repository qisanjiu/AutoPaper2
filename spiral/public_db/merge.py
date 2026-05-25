"""Incremental merge logic for importing papers into the public database.

When a paper already exists, fields are merged according to a configurable
policy rather than overwritten.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .models import LimitationEntry, Paper

logger = logging.getLogger(__name__)


@dataclass
class MergePolicy:
    """Configurable merge policy for paper field conflicts.

    All flags default to ``True`` (cooperative accumulation).
    """

    merge_limitations: bool = True
    inherit_credibility: bool = True
    inherit_tags: bool = True
    inherit_verification: bool = True
    inherit_code_url: bool = True
    max_limitations: int = 50

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MergePolicy:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def merge_papers(
    existing: Paper,
    incoming: Paper,
    policy: MergePolicy | None = None,
) -> Paper:
    """Merge ``incoming`` paper into ``existing``, returning a new Paper.

    Rules (in order of precedence):
        1. Scalar metadata: keep longest / most complete.
        2. Credibility score: weighted average by survey_count.
        3. Limitations: append unique entries up to ``max_limitations``.
        4. Tags / claims: handled at association level (not here).
        5. survey_count: increment by 1.
        6. last_updated_at: refresh to now.
    """
    policy = policy or MergePolicy()
    result = Paper.from_dict(existing.to_dict())  # deep copy

    # 1. Identifiers — fill missing
    if not result.identifiers.doi and incoming.identifiers.doi:
        result.identifiers.doi = incoming.identifiers.doi
    if not result.identifiers.arxiv_id and incoming.identifiers.arxiv_id:
        result.identifiers.arxiv_id = incoming.identifiers.arxiv_id
    if not result.identifiers.semantic_scholar_id and incoming.identifiers.semantic_scholar_id:
        result.identifiers.semantic_scholar_id = incoming.identifiers.semantic_scholar_id
    if not result.identifiers.dblp_id and incoming.identifiers.dblp_id:
        result.identifiers.dblp_id = incoming.identifiers.dblp_id

    # 2. Text fields — keep longest
    for attr in ("title", "abstract", "problem_statement", "method_summary", "venue"):
        old = getattr(result, attr) or ""
        new = getattr(incoming, attr) or ""
        if len(new) > len(old):
            setattr(result, attr, new)

    # 3. Authors — prefer longer list
    if len(incoming.authors) > len(result.authors):
        result.authors = list(incoming.authors)

    # 4. URL / PDF / Code URL — prefer non-empty
    for attr in ("url", "pdf_url", "code_url"):
        if getattr(incoming, attr):
            setattr(result, attr, getattr(incoming, attr))

    # 5. Year / Date — prefer non-zero / non-empty
    if incoming.year and (not result.year or incoming.year < result.year):
        # For year, prefer earliest (publication year shouldn't change)
        pass
    if incoming.date and not result.date:
        result.date = incoming.date

    # 6. Type — keep existing if set, else incoming
    if result.type == "academic" and incoming.type != "academic":
        result.type = incoming.type

    # 7. Credibility score — weighted average
    if policy.inherit_credibility and incoming.credibility_score != 3:
        total = existing.survey_count + 1
        if total > 1:
            result.credibility_score = round(
                (existing.credibility_score * existing.survey_count + incoming.credibility_score)
                / total
            )
        else:
            result.credibility_score = incoming.credibility_score

    # 8. Verification status — upgrade to higher confidence
    if policy.inherit_verification:
        priority = {"confirmed": 3, "partial": 2, "unverified": 1, "contradicted": 0}
        old_pri = priority.get(existing.verification_status, 1)
        new_pri = priority.get(incoming.verification_status, 1)
        if new_pri > old_pri:
            result.verification_status = incoming.verification_status

    # 9. Code availability — upgrade openness
    if policy.inherit_code_url:
        openness = {"open_source": 2, "broken": 1, "closed": 0}
        old_open = openness.get(existing.code_availability, 0)
        new_open = openness.get(incoming.code_availability, 0)
        if new_open > old_open:
            result.code_availability = incoming.code_availability
        if incoming.code_url and not result.code_url:
            result.code_url = incoming.code_url

    # 10. Key results — append unique
    existing_results_lower = {r.lower() for r in result.key_results}
    for kr in incoming.key_results:
        if kr.lower() not in existing_results_lower:
            result.key_results.append(kr)
            existing_results_lower.add(kr.lower())

    # 11. Limitations — append unique with provenance
    if policy.merge_limitations:
        existing_texts = {lim.limitation.lower() for lim in result.limitations_noted}
        for lim in incoming.limitations_noted:
            text = lim.limitation.lower()
            if text not in existing_texts and len(result.limitations_noted) < policy.max_limitations:
                result.limitations_noted.append(lim)
                existing_texts.add(text)

    # 12. Citation count — take max
    if incoming.citation_count > result.citation_count:
        result.citation_count = incoming.citation_count

    # 13. Survey metadata
    result.survey_count = existing.survey_count + 1
    result.last_updated_at = datetime.now().isoformat()
    if not result.first_surveyed_at:
        result.first_surveyed_at = incoming.first_surveyed_at or datetime.now().isoformat()

    return result


def serialize_limitations(lims: list[LimitationEntry]) -> str:
    """Serialize limitations to JSON string for SQLite storage."""
    return json.dumps([lim.to_dict() for lim in lims], ensure_ascii=False)


def deserialize_limitations(raw: str | None) -> list[LimitationEntry]:
    """Deserialize limitations from JSON string."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if data and isinstance(data[0], str):
            # Legacy migration
            return [LimitationEntry(limitation=item) for item in data]
        return [LimitationEntry.from_dict(item) for item in data]
    except (json.JSONDecodeError, TypeError):
        return []
