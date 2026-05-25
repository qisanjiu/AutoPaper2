"""Main manager class for the Public Literature Database.

Provides high-level CRUD, search, deduplication, tagging, and analytics
over the SQLite-backed literature store.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from .config import DBConfig, MergePolicyConfig
from .db import DatabaseManager
from .identifier import IdentificationError, PaperIdentifier
from .merge import MergePolicy, merge_papers, deserialize_limitations, serialize_limitations
from .models import (
    Claim,
    DomainTag,
    LimitationEntry,
    Paper,
    PaperIdentifiers,
    PaperTag,
    QueryResult,
    Survey,
)
from .query_cache import QueryCache
from .tag_engine import TagEngine

logger = logging.getLogger(__name__)


class PublicLiteratureDB:
    """Public Literature Database — cross-project literature reuse system.

    Thread-safe via WAL mode SQLite and connection-per-thread pooling.
    """

    def __init__(self, config: DBConfig | None = None):
        self.config = config or DBConfig.default()
        self.db = DatabaseManager(
            db_path=self.config.db_path,
            timeout=self.config.timeout,
        )
        self.cache = QueryCache(self.db, ttl_days=self.config.query_cache_ttl_days)
        self.tag_engine = TagEngine()
        self.identifier = PaperIdentifier()
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Initialize schema if not already present."""
        if self._initialized:
            return
        self.db.init_schema()
        self.db.register_json_functions()
        self._initialized = True
        logger.info("PublicLiteratureDB initialized at %s", self.config.db_path)

    def init_if_needed(self) -> bool:
        """Initialize schema only if the database file does not yet exist.

        Returns True if initialization was performed, False if already exists.
        This is safe to call repeatedly — it is idempotent.
        """
        if self._initialized:
            return False
        db_path = Path(self.config.db_path)
        if db_path.exists() and db_path.stat().st_size > 0:
            # File exists — just verify schema and register functions
            self.db.init_schema()
            self.db.register_json_functions()
            self._initialized = True
            return False
        # First time — create directory, init schema
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db.init_schema()
        self.db.register_json_functions()
        self._initialized = True
        logger.info("PublicLiteratureDB auto-initialized at %s", self.config.db_path)
        return True

    def close(self) -> None:
        """Close database connections."""
        self.db.close_all()
        self._initialized = False

    def __enter__(self) -> PublicLiteratureDB:
        self.init_if_needed()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def reset(self) -> None:
        """Drop and recreate all tables (DESTRUCTIVE)."""
        self.db.reset_schema()
        self._initialized = True

    # ------------------------------------------------------------------
    # Paper CRUD
    # ------------------------------------------------------------------

    def insert_paper(
        self,
        paper: Paper,
        source_project: str = "",
        auto_tag: bool | None = None,
    ) -> str:
        """Insert a new paper. Returns the canonical paper_id.

        Raises:
            IdentificationError: If no canonical ID can be generated.
            ValueError: If paper already exists (use ``update_paper`` instead).
        """
        self._ensure_init()

        if not paper.paper_id:
            paper.paper_id = self.identifier.canonical_id(paper)

        # Deduplication check
        existing = self.check_duplicate(paper)
        if existing:
            raise ValueError(
                f"Paper already exists with ID {existing}. Use update_paper() to merge."
            )

        now = datetime.now().isoformat()
        paper.first_surveyed_at = paper.first_surveyed_at or now
        paper.last_updated_at = now
        paper.survey_count = max(1, paper.survey_count)

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO papers (
                    paper_id, title, authors, venue, year, date, url, pdf_url, type,
                    identifiers, credibility_score, verification_status, code_availability, code_url,
                    abstract, problem_statement, method_summary, key_results, limitations_noted,
                    first_surveyed_at, last_updated_at, survey_count, citation_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper.paper_id,
                    paper.title,
                    json.dumps(paper.authors, ensure_ascii=False),
                    paper.venue,
                    paper.year,
                    paper.date,
                    paper.url,
                    paper.pdf_url,
                    paper.type,
                    json.dumps(paper.identifiers.to_dict(), ensure_ascii=False),
                    paper.credibility_score,
                    paper.verification_status,
                    paper.code_availability,
                    paper.code_url,
                    paper.abstract,
                    paper.problem_statement,
                    paper.method_summary,
                    json.dumps(paper.key_results, ensure_ascii=False),
                    serialize_limitations(paper.limitations_noted),
                    paper.first_surveyed_at,
                    paper.last_updated_at,
                    paper.survey_count,
                    paper.citation_count,
                ),
            )
            self._sync_identifiers(conn, paper)

        # Auto-tagging
        if auto_tag if auto_tag is not None else self.config.auto_tagging:
            self._auto_tag_paper(paper, source_project)

        logger.debug("Inserted paper %s", paper.paper_id)
        return paper.paper_id

    def update_paper(
        self,
        paper: Paper,
        source_project: str = "",
        policy: MergePolicy | None = None,
    ) -> str:
        """Merge incoming paper data into an existing paper record.

        Returns the paper_id of the updated record.
        """
        self._ensure_init()

        if not paper.paper_id:
            paper.paper_id = self.identifier.canonical_id(paper)

        existing = self.get_paper(paper.paper_id)
        if existing is None:
            # Try fuzzy match
            existing_id = self.check_duplicate(paper)
            if existing_id:
                existing = self.get_paper(existing_id)
                paper.paper_id = existing_id
            else:
                # Not found — treat as insert
                return self.insert_paper(paper, source_project=source_project)

        if existing is None:
            raise RuntimeError("Unexpected null existing paper after deduplication")

        merged = merge_papers(
            existing, paper, policy or MergePolicy.from_dict(self.config.merge_policy.to_dict())
        )

        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE papers SET
                    title = ?,
                    authors = ?,
                    venue = ?,
                    year = ?,
                    date = ?,
                    url = ?,
                    pdf_url = ?,
                    type = ?,
                    identifiers = ?,
                    credibility_score = ?,
                    verification_status = ?,
                    code_availability = ?,
                    code_url = ?,
                    abstract = ?,
                    problem_statement = ?,
                    method_summary = ?,
                    key_results = ?,
                    limitations_noted = ?,
                    first_surveyed_at = ?,
                    last_updated_at = ?,
                    survey_count = ?,
                    citation_count = ?
                WHERE paper_id = ?
                """,
                (
                    merged.title,
                    json.dumps(merged.authors, ensure_ascii=False),
                    merged.venue,
                    merged.year,
                    merged.date,
                    merged.url,
                    merged.pdf_url,
                    merged.type,
                    json.dumps(merged.identifiers.to_dict(), ensure_ascii=False),
                    merged.credibility_score,
                    merged.verification_status,
                    merged.code_availability,
                    merged.code_url,
                    merged.abstract,
                    merged.problem_statement,
                    merged.method_summary,
                    json.dumps(merged.key_results, ensure_ascii=False),
                    serialize_limitations(merged.limitations_noted),
                    merged.first_surveyed_at,
                    merged.last_updated_at,
                    merged.survey_count,
                    merged.citation_count,
                    merged.paper_id,
                ),
            )
            self._sync_identifiers(conn, merged)

        logger.debug("Updated paper %s", merged.paper_id)
        return merged.paper_id

    def get_paper(self, paper_id: str) -> Paper | None:
        """Retrieve a paper by its canonical ID."""
        self._ensure_init()
        row = self.db.fetchone("SELECT * FROM papers WHERE paper_id = ?", (paper_id,))
        if not row:
            return None
        return self._row_to_paper(row)

    def delete_paper(self, paper_id: str) -> bool:
        """Delete a paper and all its associations. Returns True if existed."""
        self._ensure_init()
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM papers WHERE paper_id = ?", (paper_id,))
        return cur.rowcount > 0

    def paper_exists(self, paper_id: str) -> bool:
        """Check whether a paper exists."""
        self._ensure_init()
        return self.db.fetchval(
            "SELECT 1 FROM papers WHERE paper_id = ?", (paper_id,)
        ) is not None

    def count_papers(self) -> int:
        """Return total number of papers in the database."""
        self._ensure_init()
        return self.db.fetchval("SELECT COUNT(*) FROM papers") or 0

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def check_duplicate(self, paper: Paper) -> str | None:
        """Check whether a paper already exists. Returns existing paper_id or None."""
        self._ensure_init()
        return self.identifier.find_existing(
            db_manager=self.db,
            title=paper.title,
            authors=paper.authors,
            year=paper.year,
            arxiv_id=paper.identifiers.arxiv_id,
            doi=paper.identifiers.doi,
            semantic_scholar_id=paper.identifiers.semantic_scholar_id,
            dblp_id=paper.identifiers.dblp_id,
            paper_id=paper.paper_id or None,
        )

    # ------------------------------------------------------------------
    # Search / Query
    # ------------------------------------------------------------------

    def query(
        self,
        keywords: list[str] | None = None,
        domain_tags: list[str] | None = None,
        year_range: tuple[int, int] | None = None,
        venue_filter: list[str] | None = None,
        min_credibility: int = 1,
        min_citation_count: int = 0,
        require_code: bool = False,
        fts_query: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> QueryResult:
        """Multi-dimensional query over the public literature database.

        Results are sorted by:
            1. Tag match score (more overlapping tags = higher)
            2. Credibility score (descending)
            3. Citation count (descending)
            4. Survey count (descending)
        """
        self._ensure_init()
        start = time.perf_counter()
        limit = limit or self.config.default_limit
        limit = min(limit, self.config.max_limit)

        # Check cache for simple keyword-only queries
        if keywords and not any([domain_tags, year_range, venue_filter, fts_query]):
            cached = self.cache.get(keywords)
            if cached:
                paper_ids = [r["paper_id"] for r in cached.results]
                papers = [self.get_paper(pid) for pid in paper_ids]
                papers = [p for p in papers if p]
                return QueryResult(
                    papers=papers,
                    total_count=cached.total_hits,
                    query_time_ms=(time.perf_counter() - start) * 1000,
                    from_cache=True,
                )

        # Build dynamic SQL
        conditions: list[str] = []
        params: list[Any] = []

        if keywords:
            # FTS5 search across title/abstract/problem_statement/method_summary
            fts_expr = " OR ".join(f"{kw}" for kw in keywords)
            conditions.append(
                f"papers.rowid IN (SELECT rowid FROM papers_fts WHERE papers_fts MATCH ?)"
            )
            params.append(fts_expr)

        if fts_query:
            conditions.append(
                f"papers.rowid IN (SELECT rowid FROM papers_fts WHERE papers_fts MATCH ?)"
            )
            params.append(fts_query)

        # Tag scoring subquery (built first so its params come before WHERE params)
        tag_score_sql = ""
        tag_params: list[Any] = []
        if domain_tags:
            placeholders = ",".join("?" * len(domain_tags))
            tag_score_sql = f"""
                LEFT JOIN (
                    SELECT paper_id, COUNT(*) as tag_score
                    FROM paper_tags
                    WHERE tag_id IN ({placeholders})
                    GROUP BY paper_id
                ) ts ON papers.paper_id = ts.paper_id
            """
            tag_params = list(domain_tags)
            conditions.append(
                f"papers.paper_id IN (SELECT paper_id FROM paper_tags WHERE tag_id IN ({placeholders}))"
            )
            params.extend(list(domain_tags))

        if year_range:
            conditions.append("papers.year BETWEEN ? AND ?")
            params.extend(year_range)

        if venue_filter:
            placeholders = ",".join("?" * len(venue_filter))
            conditions.append(f"papers.venue IN ({placeholders})")
            params.extend(venue_filter)

        if min_credibility > 1:
            conditions.append("papers.credibility_score >= ?")
            params.append(min_credibility)

        if min_citation_count > 0:
            conditions.append("papers.citation_count >= ?")
            params.append(min_citation_count)

        if require_code:
            conditions.append("papers.code_availability = 'open_source'")

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Combined params: JOIN params first, then WHERE params
        all_params = tag_params + params

        # Count total
        count_sql = f"""
            SELECT COUNT(DISTINCT papers.paper_id)
            FROM papers
            {tag_score_sql}
            {where_clause}
        """
        try:
            total_count = self.db.fetchval(count_sql, tuple(all_params)) or 0
        except Exception as exc:
            logger.warning("Query count failed (possibly FTS syntax error): %s", exc)
            return QueryResult(papers=[], total_count=0, query_time_ms=(time.perf_counter() - start) * 1000)

        # Main query with ranking
        tag_order = "ts.tag_score DESC, " if domain_tags else ""
        main_sql = f"""
            SELECT papers.*
            FROM papers
            {tag_score_sql}
            {where_clause}
            ORDER BY {tag_order} papers.credibility_score DESC,
                     papers.citation_count DESC,
                     papers.survey_count DESC,
                     papers.year DESC
            LIMIT ? OFFSET ?
        """
        query_params = list(all_params)
        query_params.extend([limit, offset])

        try:
            rows = self.db.fetchall(main_sql, tuple(query_params))
            papers = [self._row_to_paper(row) for row in rows]
        except Exception as exc:
            logger.warning("Query failed (possibly FTS syntax error): %s", exc)
            return QueryResult(papers=[], total_count=0, query_time_ms=(time.perf_counter() - start) * 1000)

        elapsed_ms = (time.perf_counter() - start) * 1000

        # Cache simple keyword results
        if keywords and not any([domain_tags, year_range, venue_filter, fts_query]):
            self.cache.set(
                keywords,
                [{"paper_id": p.paper_id} for p in papers],
                total_hits=total_count,
            )

        return QueryResult(
            papers=papers,
            total_count=total_count,
            query_time_ms=elapsed_ms,
            from_cache=False,
        )

    def find_similar(
        self,
        paper_id: str,
        by: Literal["tag", "citation", "year_venue"] = "tag",
        limit: int = 10,
    ) -> list[Paper]:
        """Find papers similar to the given paper_id.

        - ``tag``: Same domain tags (most overlapping first)
        - ``citation``: Same venue, close year
        - ``year_venue``: Same venue + close year
        """
        self._ensure_init()
        paper = self.get_paper(paper_id)
        if not paper:
            return []

        if by == "tag":
            tag_ids = [t["tag_id"] for t in self.db.fetchall(
                "SELECT tag_id FROM paper_tags WHERE paper_id = ?", (paper_id,)
            )]
            if not tag_ids:
                return []
            placeholders = ",".join("?" * len(tag_ids))
            rows = self.db.fetchall(
                f"""
                SELECT p.*, COUNT(pt.tag_id) as overlap
                FROM papers p
                JOIN paper_tags pt ON p.paper_id = pt.paper_id
                WHERE pt.tag_id IN ({placeholders})
                  AND p.paper_id != ?
                GROUP BY p.paper_id
                ORDER BY overlap DESC, p.credibility_score DESC
                LIMIT ?
                """,
                tuple(tag_ids + [paper_id, limit]),
            )
            return [self._row_to_paper(row) for row in rows]

        elif by == "citation":
            # Same venue, ordered by citation count
            rows = self.db.fetchall(
                """
                SELECT * FROM papers
                WHERE venue = ? AND paper_id != ?
                ORDER BY citation_count DESC
                LIMIT ?
                """,
                (paper.venue, paper_id, limit),
            )
            return [self._row_to_paper(row) for row in rows]

        elif by == "year_venue":
            rows = self.db.fetchall(
                """
                SELECT * FROM papers
                WHERE venue = ? AND paper_id != ? AND ABS(year - ?) <= 2
                ORDER BY year DESC, citation_count DESC
                LIMIT ?
                """,
                (paper.venue, paper_id, paper.year, limit),
            )
            return [self._row_to_paper(row) for row in rows]

        return []

    # ------------------------------------------------------------------
    # Tagging
    # ------------------------------------------------------------------

    def tag_paper(
        self,
        paper_id: str,
        tag_id: str,
        confidence: str = "medium",
        source: str = "manual",
        added_by_project: str = "",
    ) -> bool:
        """Associate a tag with a paper. Returns True if newly inserted."""
        self._ensure_init()
        try:
            self.db.execute(
                """
                INSERT INTO paper_tags (paper_id, tag_id, confidence, source, added_by_project, added_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(paper_id, tag_id) DO UPDATE SET
                    confidence = excluded.confidence,
                    source = excluded.source,
                    added_by_project = excluded.added_by_project,
                    added_at = excluded.added_at
                """,
                (paper_id, tag_id, confidence, source, added_by_project),
            )
            return True
        except Exception as exc:
            logger.warning("Failed to tag paper %s with %s: %s", paper_id, tag_id, exc)
            return False

    def untag_paper(self, paper_id: str, tag_id: str) -> bool:
        """Remove a tag association. Returns True if existed."""
        self._ensure_init()
        cur = self.db.execute(
            "DELETE FROM paper_tags WHERE paper_id = ? AND tag_id = ?",
            (paper_id, tag_id),
        )
        return cur.rowcount > 0

    def get_paper_tags(self, paper_id: str) -> list[PaperTag]:
        """Return all tag associations for a paper."""
        self._ensure_init()
        rows = self.db.fetchall(
            "SELECT * FROM paper_tags WHERE paper_id = ?", (paper_id,)
        )
        return [PaperTag(**dict(row)) for row in rows]

    def get_tagged_papers(self, tag_id: str, limit: int = 100) -> list[Paper]:
        """Return papers associated with a given tag."""
        self._ensure_init()
        rows = self.db.fetchall(
            """
            SELECT p.* FROM papers p
            JOIN paper_tags pt ON p.paper_id = pt.paper_id
            WHERE pt.tag_id = ?
            ORDER BY p.credibility_score DESC, p.citation_count DESC
            LIMIT ?
            """,
            (tag_id, limit),
        )
        return [self._row_to_paper(row) for row in rows]

    # ------------------------------------------------------------------
    # Domain Tags
    # ------------------------------------------------------------------

    def insert_or_update_tag(self, tag: DomainTag) -> None:
        """Upsert a domain tag into the taxonomy."""
        self._ensure_init()
        self.db.execute(
            """
            INSERT INTO domain_tags (tag_id, name, aliases, parent, level, description)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tag_id) DO UPDATE SET
                name = excluded.name,
                aliases = excluded.aliases,
                parent = excluded.parent,
                level = excluded.level,
                description = excluded.description
            """,
            (
                tag.tag_id,
                tag.name,
                json.dumps(tag.aliases, ensure_ascii=False),
                tag.parent,
                tag.level,
                tag.description,
            ),
        )

    def get_tag(self, tag_id: str) -> DomainTag | None:
        """Retrieve a domain tag by ID."""
        self._ensure_init()
        row = self.db.fetchone("SELECT * FROM domain_tags WHERE tag_id = ?", (tag_id,))
        if not row:
            return None
        return DomainTag(
            tag_id=row["tag_id"],
            name=row["name"],
            aliases=json.loads(row["aliases"] or "[]"),
            parent=row["parent"],
            level=row["level"],
            description=row["description"],
        )

    def list_tags(self, parent: str | None = None) -> list[DomainTag]:
        """List tags, optionally filtered by parent."""
        self._ensure_init()
        if parent is not None:
            rows = self.db.fetchall(
                "SELECT * FROM domain_tags WHERE parent = ? ORDER BY level, name",
                (parent,),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM domain_tags ORDER BY level, name"
            )
        return [
            DomainTag(
                tag_id=row["tag_id"],
                name=row["name"],
                aliases=json.loads(row["aliases"] or "[]"),
                parent=row["parent"],
                level=row["level"],
                description=row["description"],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Claims
    # ------------------------------------------------------------------

    def insert_or_update_claim(self, claim: Claim) -> None:
        """Upsert a claim."""
        self._ensure_init()
        self.db.execute(
            """
            INSERT INTO claims (claim_id, statement, confidence, domains, first_stated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(claim_id) DO UPDATE SET
                statement = excluded.statement,
                confidence = excluded.confidence,
                domains = excluded.domains
            """,
            (
                claim.claim_id,
                claim.statement,
                claim.confidence,
                json.dumps(claim.domains, ensure_ascii=False),
                claim.first_stated_at,
            ),
        )

        # Sync claim-paper associations
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM claim_papers WHERE claim_id = ?",
                (claim.claim_id,),
            )
            for paper_id in claim.supporting_papers:
                conn.execute(
                    "INSERT INTO claim_papers (claim_id, paper_id, relation) VALUES (?, ?, 'supporting')",
                    (claim.claim_id, paper_id),
                )
            for paper_id in claim.contradicting_papers:
                conn.execute(
                    "INSERT INTO claim_papers (claim_id, paper_id, relation) VALUES (?, ?, 'contradicting')",
                    (claim.claim_id, paper_id),
                )

    def get_claim(self, claim_id: str) -> Claim | None:
        """Retrieve a claim with its paper associations."""
        self._ensure_init()
        row = self.db.fetchone("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
        if not row:
            return None

        supporting = [
            r["paper_id"]
            for r in self.db.fetchall(
                "SELECT paper_id FROM claim_papers WHERE claim_id = ? AND relation = 'supporting'",
                (claim_id,),
            )
        ]
        contradicting = [
            r["paper_id"]
            for r in self.db.fetchall(
                "SELECT paper_id FROM claim_papers WHERE claim_id = ? AND relation = 'contradicting'",
                (claim_id,),
            )
        ]

        return Claim(
            claim_id=row["claim_id"],
            statement=row["statement"],
            confidence=row["confidence"],
            domains=json.loads(row["domains"] or "[]"),
            supporting_papers=supporting,
            contradicting_papers=contradicting,
            first_stated_at=row["first_stated_at"],
        )

    # ------------------------------------------------------------------
    # Surveys
    # ------------------------------------------------------------------

    def insert_survey(self, survey: Survey) -> None:
        """Upsert a survey session."""
        self._ensure_init()
        self.db.execute(
            """
            INSERT INTO surveys (
                survey_id, project_name, topic, status, start_at, end_at,
                search_queries, papers_discovered, papers_from_db, papers_from_web
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(survey_id) DO UPDATE SET
                project_name = excluded.project_name,
                topic = excluded.topic,
                status = excluded.status,
                start_at = excluded.start_at,
                end_at = excluded.end_at,
                search_queries = excluded.search_queries,
                papers_discovered = excluded.papers_discovered,
                papers_from_db = excluded.papers_from_db,
                papers_from_web = excluded.papers_from_web
            """,
            (
                survey.survey_id,
                survey.project_name,
                survey.topic,
                survey.status,
                survey.start_at,
                survey.end_at,
                json.dumps(survey.search_queries, ensure_ascii=False),
                json.dumps(survey.papers_discovered, ensure_ascii=False),
                survey.papers_from_db,
                survey.papers_from_web,
            ),
        )

    def get_survey(self, survey_id: str) -> Survey | None:
        """Retrieve a survey session."""
        self._ensure_init()
        row = self.db.fetchone("SELECT * FROM surveys WHERE survey_id = ?", (survey_id,))
        if not row:
            return None
        return Survey(
            survey_id=row["survey_id"],
            project_name=row["project_name"],
            topic=row["topic"],
            status=row["status"],
            start_at=row["start_at"],
            end_at=row["end_at"],
            search_queries=json.loads(row["search_queries"] or "[]"),
            papers_discovered=json.loads(row["papers_discovered"] or "[]"),
            papers_from_db=row["papers_from_db"],
            papers_from_web=row["papers_from_web"],
        )

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def get_tag_statistics(self) -> list[dict[str, Any]]:
        """Return per-tag paper counts and average credibility."""
        self._ensure_init()
        rows = self.db.fetchall(
            """
            SELECT
                pt.tag_id,
                dt.name,
                COUNT(*) as paper_count,
                ROUND(AVG(p.credibility_score), 2) as avg_credibility
            FROM paper_tags pt
            JOIN papers p ON pt.paper_id = p.paper_id
            JOIN domain_tags dt ON pt.tag_id = dt.tag_id
            GROUP BY pt.tag_id
            ORDER BY paper_count DESC
            """
        )
        return [dict(row) for row in rows]

    def get_top_papers(self, tag_id: str | None = None, limit: int = 10) -> list[Paper]:
        """Return top papers by composite score (credibility * survey_count)."""
        self._ensure_init()
        if tag_id:
            rows = self.db.fetchall(
                """
                SELECT p.* FROM papers p
                JOIN paper_tags pt ON p.paper_id = pt.paper_id
                WHERE pt.tag_id = ?
                ORDER BY (p.credibility_score * p.survey_count) DESC
                LIMIT ?
                """,
                (tag_id, limit),
            )
        else:
            rows = self.db.fetchall(
                """
                SELECT * FROM papers
                ORDER BY (credibility_score * survey_count) DESC
                LIMIT ?
                """,
                (limit,),
            )
        return [self._row_to_paper(row) for row in rows]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_init(self) -> None:
        if not self._initialized:
            self.init()

    def _row_to_paper(self, row: Any) -> Paper:
        """Convert a sqlite3.Row to a Paper dataclass."""
        return Paper(
            paper_id=row["paper_id"],
            title=row["title"],
            authors=json.loads(row["authors"] or "[]"),
            venue=row["venue"],
            year=row["year"],
            date=row["date"],
            url=row["url"],
            pdf_url=row["pdf_url"],
            type=row["type"],
            identifiers=PaperIdentifiers.from_dict(json.loads(row["identifiers"] or "{}")),
            credibility_score=row["credibility_score"],
            verification_status=row["verification_status"],
            code_availability=row["code_availability"],
            code_url=row["code_url"],
            abstract=row["abstract"],
            problem_statement=row["problem_statement"],
            method_summary=row["method_summary"],
            key_results=json.loads(row["key_results"] or "[]"),
            limitations_noted=deserialize_limitations(row["limitations_noted"]),
            first_surveyed_at=row["first_surveyed_at"],
            last_updated_at=row["last_updated_at"],
            survey_count=row["survey_count"],
            citation_count=row["citation_count"],
        )

    def _sync_identifiers(self, conn, paper: Paper) -> None:
        """Sync external identifiers into the lookup table."""
        conn.execute(
            "DELETE FROM paper_identifiers WHERE paper_id = ?",
            (paper.paper_id,),
        )
        id_map = {
            "arxiv": paper.identifiers.arxiv_id,
            "doi": paper.identifiers.doi,
            "s2": paper.identifiers.semantic_scholar_id,
            "dblp": paper.identifiers.dblp_id,
        }
        for id_type, id_value in id_map.items():
            if id_value:
                conn.execute(
                    "INSERT OR REPLACE INTO paper_identifiers (paper_id, id_type, id_value) VALUES (?, ?, ?)",
                    (paper.paper_id, id_type, id_value.strip().lower()),
                )

    def _auto_tag_paper(self, paper: Paper, source_project: str) -> None:
        """Automatically derive tags and store associations."""
        tags = self.tag_engine.tag_paper(paper, source_project=source_project)
        for tag in tags:
            # Ensure tag exists in taxonomy
            if not self.get_tag(tag.tag_id):
                rule = self.tag_engine.get_rule(tag.tag_id)
                if rule:
                    self.insert_or_update_tag(
                        DomainTag(
                            tag_id=rule.tag_id,
                            name=rule.tag_id.replace("_", " ").title(),
                            level=3,
                        )
                    )
            self.tag_paper(
                paper_id=tag.paper_id,
                tag_id=tag.tag_id,
                confidence=tag.confidence,
                source="auto_keyword",
                added_by_project=source_project,
            )
