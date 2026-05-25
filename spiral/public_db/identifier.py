"""Paper identification and deduplication logic.

Resolves canonical paper IDs across multiple external identifier systems
(arXiv, DOI, Semantic Scholar, DBLP) and provides robust fuzzy matching
for title/author/year fallback.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from .models import Paper, PaperIdentifiers


class IdentificationError(Exception):
    """Raised when paper identification fails or produces ambiguous results."""
    pass


class PaperIdentifier:
    """Generates canonical paper IDs and performs deduplication lookups.

    Deduplication priority:
        1. DOI (most stable)
        2. arXiv ID
        3. Semantic Scholar ID
        4. DBLP ID
        5. Normalized title + first-author surname + year (fuzzy fallback)
    """

    # Normalization regexes
    _RE_WHITESPACE = re.compile(r"\s+")
    _RE_NON_ALPHANUM = re.compile(r"[^\w\s-]+")
    _RE_ARXIV = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
    _RE_DOI = re.compile(r"^10\.\d{4,}/.+$")

    @classmethod
    def canonical_id(cls, paper: Paper) -> str:
        """Generate a canonical paper_id from available identifiers.

        Raises:
            IdentificationError: If no usable identifier can be derived.
        """
        ids = paper.identifiers

        if ids.doi and cls._RE_DOI.match(ids.doi.strip()):
            return f"doi:{ids.doi.strip().lower()}"

        if ids.arxiv_id:
            arxiv = ids.arxiv_id.strip().lower()
            arxiv = arxiv.replace("arxiv:", "").replace("arxiv.org/abs/", "")
            if cls._RE_ARXIV.match(arxiv):
                return f"arxiv:{arxiv}"

        if ids.semantic_scholar_id:
            return f"s2:{ids.semantic_scholar_id.strip()}"

        if ids.dblp_id:
            return f"dblp:{ids.dblp_id.strip()}"

        # Fallback: first-author surname + year + title hash
        if not paper.authors or paper.year == 0 or not paper.title:
            raise IdentificationError(
                "Cannot generate canonical_id: missing authors, year, or title, "
                f"and no external identifiers provided. Paper title={paper.title!r}"
            )

        first_author = cls._extract_last_name(paper.authors[0])
        title_hash = cls._hash_title(paper.title)
        return f"{first_author}{paper.year}{title_hash}"

    @classmethod
    def find_existing(
        cls,
        db_manager,
        title: str,
        authors: list[str],
        year: int,
        arxiv_id: Optional[str] = None,
        doi: Optional[str] = None,
        semantic_scholar_id: Optional[str] = None,
        dblp_id: Optional[str] = None,
        paper_id: Optional[str] = None,
    ) -> Optional[str]:
        """Check whether a paper already exists in the database.

        Returns the existing ``paper_id`` if found, else ``None``.

        Strategy:
            0. Exact match on provided paper_id
            1. Exact match on external identifiers (DOI, arXiv, S2, DBLP)
            2. Exact match on canonical fallback ID
            3. Fuzzy title + first-author + year match
        """
        # 0. Direct paper_id match
        if paper_id:
            row = db_manager.fetchone(
                "SELECT paper_id FROM papers WHERE paper_id = ?", (paper_id,)
            )
            if row:
                return row["paper_id"]

        # Build a temporary Paper to compute canonical_id
        temp = Paper(
            paper_id="",
            title=title,
            authors=authors,
            year=year,
            identifiers=PaperIdentifiers(
                arxiv_id=arxiv_id,
                doi=doi,
                semantic_scholar_id=semantic_scholar_id,
                dblp_id=dblp_id,
            ),
        )

        try:
            canonical = cls.canonical_id(temp)
        except IdentificationError:
            canonical = None

        # 1. External identifier exact match
        id_conditions: list[tuple[str, Optional[str]]] = [
            ("arxiv", arxiv_id),
            ("doi", doi),
            ("s2", semantic_scholar_id),
            ("dblp", dblp_id),
        ]
        for id_type, id_value in id_conditions:
            if id_value:
                row = db_manager.fetchone(
                    "SELECT paper_id FROM paper_identifiers WHERE id_type = ? AND id_value = ?",
                    (id_type, id_value.strip().lower()),
                )
                if row:
                    return row["paper_id"]

        # 2. Canonical ID match
        if canonical:
            row = db_manager.fetchone(
                "SELECT paper_id FROM papers WHERE paper_id = ?", (canonical,)
            )
            if row:
                return row["paper_id"]

        # 3. Fuzzy title + first-author + year match
        if title and authors and year:
            first_author_last = cls._extract_last_name(authors[0])
            normalized_title = cls._normalize_title(title)
            # Use a relaxed LIKE query on normalized title + year constraint
            rows = db_manager.fetchall(
                """
                SELECT paper_id, title, authors, year FROM papers
                WHERE year = ?
                """,
                (year,),
            )
            for row in rows:
                row_authors = row["authors"]
                if row_authors:
                    try:
                        import json
                        row_authors_list = json.loads(row_authors)
                    except json.JSONDecodeError:
                        row_authors_list = []
                else:
                    row_authors_list = []

                if row_authors_list:
                    row_first = cls._extract_last_name(row_authors_list[0])
                    if row_first.lower() != first_author_last.lower():
                        continue

                row_title_norm = cls._normalize_title(row["title"])
                if cls._title_similarity(normalized_title, row_title_norm) >= 0.85:
                    return row["paper_id"]

        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _extract_last_name(cls, author: str) -> str:
        """Extract surname from 'First Last', 'Last, First', or 'F. Last' formats."""
        author = author.strip()
        if not author:
            return "unknown"

        # Handle "Last, First" format
        if "," in author:
            parts = [p.strip() for p in author.split(",")]
            return parts[0] if parts[0] else "unknown"

        # Handle "First M. Last" format — take last token
        parts = author.split()
        if len(parts) == 1:
            return parts[0]
        # Skip common suffixes
        suffixes = {"jr", "sr", "ii", "iii", "iv", "v", "phd", "md"}
        last = parts[-1].strip(".")
        if last.lower() in suffixes and len(parts) > 2:
            last = parts[-2].strip(".")
        return last

    @classmethod
    def _hash_title(cls, title: str) -> str:
        """Produce a short, deterministic hash of the normalized title."""
        norm = cls._normalize_title(title)
        digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        return digest[:10]

    @classmethod
    def _normalize_title(cls, title: str) -> str:
        """Lowercase, remove non-alphanumeric, collapse whitespace."""
        title = title.lower().strip()
        title = cls._RE_NON_ALPHANUM.sub(" ", title)
        title = cls._RE_WHITESPACE.sub(" ", title)
        return title.strip()

    @classmethod
    def _title_similarity(cls, a: str, b: str) -> float:
        """Simple Jaccard similarity over word sets."""
        if not a or not b:
            return 0.0
        set_a = set(a.split())
        set_b = set(b.split())
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)
