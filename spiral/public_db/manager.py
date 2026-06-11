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
    LiteratureArtifact,
    LiteratureDiscovery,
    LiteratureExtraction,
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
            self._upsert_extraction_from_paper(conn, paper)

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
            self._upsert_extraction_from_paper(conn, merged)

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

    def count_artifacts(self, status: str | None = None, artifact_type: str | None = None) -> int:
        """Return the number of artifact acquisition records."""
        self._ensure_init()
        conditions: list[str] = []
        params: list[Any] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if artifact_type:
            conditions.append("artifact_type = ?")
            params.append(artifact_type)
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        return self.db.fetchval(f"SELECT COUNT(*) FROM literature_artifacts{where_clause}", tuple(params)) or 0

    def count_extractions(self, parse_status: str | None = None) -> int:
        """Return the number of structured parse profiles."""
        self._ensure_init()
        if parse_status:
            return self.db.fetchval(
                "SELECT COUNT(*) FROM literature_extractions WHERE parse_status = ?",
                (parse_status,),
            ) or 0
        return self.db.fetchval("SELECT COUNT(*) FROM literature_extractions") or 0

    def count_discoveries(self) -> int:
        """Return the number of retained/search discovery records."""
        self._ensure_init()
        return self.db.fetchval("SELECT COUNT(*) FROM literature_discovery") or 0

    # ------------------------------------------------------------------
    # Literature ingestion provenance
    # ------------------------------------------------------------------

    def upsert_discovery(self, discovery: LiteratureDiscovery) -> str:
        """Record where a paper was found and how it was screened."""
        self._ensure_init()
        if not discovery.discovery_id:
            discovery.discovery_id = self._make_discovery_id(discovery)
        discovery.discovered_at = discovery.discovered_at or datetime.now().isoformat()
        self.db.execute(
            """
            INSERT INTO literature_discovery (
                discovery_id, paper_id, search_surface, query_text, result_rank,
                result_url, metadata_source, discovered_at, screened_status,
                retained_reason, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(discovery_id) DO UPDATE SET
                paper_id = excluded.paper_id,
                search_surface = excluded.search_surface,
                query_text = excluded.query_text,
                result_rank = excluded.result_rank,
                result_url = excluded.result_url,
                metadata_source = excluded.metadata_source,
                discovered_at = excluded.discovered_at,
                screened_status = excluded.screened_status,
                retained_reason = excluded.retained_reason,
                notes = excluded.notes
            """,
            (
                discovery.discovery_id,
                discovery.paper_id,
                discovery.search_surface,
                discovery.query_text,
                discovery.result_rank,
                discovery.result_url,
                discovery.metadata_source,
                discovery.discovered_at,
                discovery.screened_status,
                discovery.retained_reason,
                discovery.notes,
            ),
        )
        return discovery.discovery_id

    def list_discoveries(self, paper_id: str | None = None, limit: int = 100) -> list[LiteratureDiscovery]:
        """List discovery provenance records, newest first."""
        self._ensure_init()
        if paper_id:
            rows = self.db.fetchall(
                """
                SELECT * FROM literature_discovery
                WHERE paper_id = ?
                ORDER BY discovered_at DESC
                LIMIT ?
                """,
                (paper_id, limit),
            )
        else:
            rows = self.db.fetchall(
                """
                SELECT * FROM literature_discovery
                ORDER BY discovered_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        return [self._row_to_discovery(row) for row in rows]

    def upsert_artifact(self, artifact: LiteratureArtifact) -> str:
        """Record PDF/HTML/BibTeX acquisition status for a paper."""
        self._ensure_init()
        if not artifact.artifact_id:
            artifact.artifact_id = self._make_artifact_id(artifact)
        artifact.attempted_at = artifact.attempted_at or datetime.now().isoformat()
        artifact.updated_at = artifact.updated_at or datetime.now().isoformat()
        self.db.execute(
            """
            INSERT INTO literature_artifacts (
                artifact_id, paper_id, artifact_type, uri, local_path, status, sha256,
                attempted_at, updated_at, failure_reason, recovery_actions,
                license_note, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(artifact_id) DO UPDATE SET
                paper_id = excluded.paper_id,
                artifact_type = excluded.artifact_type,
                uri = excluded.uri,
                local_path = excluded.local_path,
                status = excluded.status,
                sha256 = excluded.sha256,
                attempted_at = excluded.attempted_at,
                updated_at = excluded.updated_at,
                failure_reason = excluded.failure_reason,
                recovery_actions = excluded.recovery_actions,
                license_note = excluded.license_note,
                notes = excluded.notes
            """,
            (
                artifact.artifact_id,
                artifact.paper_id,
                artifact.artifact_type,
                artifact.uri,
                artifact.local_path,
                artifact.status,
                artifact.sha256,
                artifact.attempted_at,
                artifact.updated_at,
                artifact.failure_reason,
                json.dumps(artifact.recovery_actions, ensure_ascii=False),
                artifact.license_note,
                artifact.notes,
            ),
        )
        return artifact.artifact_id

    def list_artifacts(
        self,
        paper_id: str | None = None,
        *,
        status: str | None = None,
        artifact_type: str | None = None,
        limit: int = 100,
    ) -> list[LiteratureArtifact]:
        """List artifact acquisition records."""
        self._ensure_init()
        conditions: list[str] = []
        params: list[Any] = []
        if paper_id:
            conditions.append("paper_id = ?")
            params.append(paper_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if artifact_type:
            conditions.append("artifact_type = ?")
            params.append(artifact_type)
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self.db.fetchall(
            f"""
            SELECT * FROM literature_artifacts
            {where_clause}
            ORDER BY updated_at DESC, attempted_at DESC
            LIMIT ?
            """,
            tuple(params + [limit]),
        )
        return [self._row_to_artifact(row) for row in rows]

    def upsert_extraction(self, extraction: LiteratureExtraction) -> str:
        """Record structured parsed content and downstream-module readiness."""
        self._ensure_init()
        if not extraction.paper_id:
            raise ValueError("LiteratureExtraction.paper_id is required")
        extraction.parsed_at = extraction.parsed_at or datetime.now().isoformat()
        self.db.execute(
            """
            INSERT INTO literature_extractions (
                paper_id, metadata_status, fulltext_status, parse_status, parse_backend,
                parsed_at, extraction_sources, missing_fields, section_summaries,
                downstream_signals, confidence, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(paper_id) DO UPDATE SET
                metadata_status = excluded.metadata_status,
                fulltext_status = excluded.fulltext_status,
                parse_status = excluded.parse_status,
                parse_backend = excluded.parse_backend,
                parsed_at = excluded.parsed_at,
                extraction_sources = excluded.extraction_sources,
                missing_fields = excluded.missing_fields,
                section_summaries = excluded.section_summaries,
                downstream_signals = excluded.downstream_signals,
                confidence = excluded.confidence,
                notes = excluded.notes
            """,
            (
                extraction.paper_id,
                extraction.metadata_status,
                extraction.fulltext_status,
                extraction.parse_status,
                extraction.parse_backend,
                extraction.parsed_at,
                json.dumps(extraction.extraction_sources, ensure_ascii=False),
                json.dumps(extraction.missing_fields, ensure_ascii=False),
                json.dumps(extraction.section_summaries, ensure_ascii=False),
                json.dumps(extraction.downstream_signals, ensure_ascii=False),
                extraction.confidence,
                extraction.notes,
            ),
        )
        return extraction.paper_id

    def get_extraction(self, paper_id: str) -> LiteratureExtraction | None:
        """Retrieve a paper's structured parse profile."""
        self._ensure_init()
        row = self.db.fetchone(
            "SELECT * FROM literature_extractions WHERE paper_id = ?",
            (paper_id,),
        )
        return self._row_to_extraction(row) if row else None

    def list_extractions(
        self,
        *,
        parse_status: str | None = None,
        metadata_status: str | None = None,
        limit: int = 100,
    ) -> list[LiteratureExtraction]:
        """List parse profiles, optionally filtered by status."""
        self._ensure_init()
        conditions: list[str] = []
        params: list[Any] = []
        if parse_status:
            conditions.append("parse_status = ?")
            params.append(parse_status)
        if metadata_status:
            conditions.append("metadata_status = ?")
            params.append(metadata_status)
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self.db.fetchall(
            f"""
            SELECT * FROM literature_extractions
            {where_clause}
            ORDER BY parsed_at DESC
            LIMIT ?
            """,
            tuple(params + [limit]),
        )
        return [self._row_to_extraction(row) for row in rows]

    def ingestion_summary(self) -> dict[str, Any]:
        """Return high-level acquisition/parse health metrics for the public DB."""
        self._ensure_init()
        artifact_rows = self.db.fetchall(
            """
            SELECT artifact_type, status, COUNT(*) AS count
            FROM literature_artifacts
            GROUP BY artifact_type, status
            ORDER BY artifact_type, status
            """
        )
        extraction_rows = self.db.fetchall(
            """
            SELECT parse_status, COUNT(*) AS count
            FROM literature_extractions
            GROUP BY parse_status
            ORDER BY parse_status
            """
        )
        missing_rows = self.db.fetchall(
            """
            SELECT metadata_status, COUNT(*) AS count
            FROM literature_extractions
            GROUP BY metadata_status
            ORDER BY metadata_status
            """
        )
        return {
            "papers": self.count_papers(),
            "discoveries": self.count_discoveries(),
            "artifacts": [
                {"artifact_type": row["artifact_type"], "status": row["status"], "count": row["count"]}
                for row in artifact_rows
            ],
            "extractions": [
                {"parse_status": row["parse_status"], "count": row["count"]}
                for row in extraction_rows
            ],
            "metadata": [
                {"metadata_status": row["metadata_status"], "count": row["count"]}
                for row in missing_rows
            ],
        }

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

    def _row_to_discovery(self, row: Any) -> LiteratureDiscovery:
        """Convert a sqlite3.Row to a LiteratureDiscovery dataclass."""
        return LiteratureDiscovery(
            discovery_id=row["discovery_id"],
            paper_id=row["paper_id"],
            search_surface=row["search_surface"],
            query_text=row["query_text"],
            result_rank=row["result_rank"],
            result_url=row["result_url"],
            metadata_source=row["metadata_source"],
            discovered_at=row["discovered_at"],
            screened_status=row["screened_status"],
            retained_reason=row["retained_reason"],
            notes=row["notes"],
        )

    def _row_to_artifact(self, row: Any) -> LiteratureArtifact:
        """Convert a sqlite3.Row to a LiteratureArtifact dataclass."""
        return LiteratureArtifact(
            artifact_id=row["artifact_id"],
            paper_id=row["paper_id"],
            artifact_type=row["artifact_type"],
            uri=row["uri"],
            local_path=row["local_path"],
            status=row["status"],
            sha256=row["sha256"],
            attempted_at=row["attempted_at"],
            updated_at=row["updated_at"],
            failure_reason=row["failure_reason"],
            recovery_actions=json.loads(row["recovery_actions"] or "[]"),
            license_note=row["license_note"],
            notes=row["notes"],
        )

    def _row_to_extraction(self, row: Any) -> LiteratureExtraction:
        """Convert a sqlite3.Row to a LiteratureExtraction dataclass."""
        return LiteratureExtraction(
            paper_id=row["paper_id"],
            metadata_status=row["metadata_status"],
            fulltext_status=row["fulltext_status"],
            parse_status=row["parse_status"],
            parse_backend=row["parse_backend"],
            parsed_at=row["parsed_at"],
            extraction_sources=json.loads(row["extraction_sources"] or "[]"),
            missing_fields=json.loads(row["missing_fields"] or "[]"),
            section_summaries=json.loads(row["section_summaries"] or "{}"),
            downstream_signals=json.loads(row["downstream_signals"] or "{}"),
            confidence=row["confidence"],
            notes=row["notes"],
        )

    @staticmethod
    def _make_discovery_id(discovery: LiteratureDiscovery) -> str:
        raw = "|".join(
            [
                discovery.paper_id,
                discovery.search_surface,
                discovery.query_text,
                discovery.result_url,
                str(discovery.result_rank),
            ]
        )
        import hashlib

        return "disc:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _make_artifact_id(artifact: LiteratureArtifact) -> str:
        raw = "|".join(
            [
                artifact.paper_id,
                artifact.artifact_type,
                artifact.uri,
                artifact.local_path,
            ]
        )
        import hashlib

        return "art:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _paper_missing_fields(paper: Paper) -> list[str]:
        fields = []
        for attr in ("title", "authors", "venue", "year", "url", "abstract", "method_summary"):
            value = getattr(paper, attr)
            if value in ("", 0, [], None):
                fields.append(attr)
        return fields

    def _upsert_extraction_from_paper(self, conn: Any, paper: Paper) -> None:
        """Keep a baseline parse profile for metadata-only imports."""
        missing_fields = self._paper_missing_fields(paper)
        if paper.method_summary and paper.key_results and paper.abstract:
            parse_status = "partial"
            metadata_status = "complete" if not missing_fields else "partial"
        elif paper.title and (paper.abstract or paper.method_summary):
            parse_status = "partial"
            metadata_status = "partial"
        else:
            parse_status = "not_attempted"
            metadata_status = "partial" if paper.title else "missing"

        row = conn.execute(
            "SELECT parse_status FROM literature_extractions WHERE paper_id = ?",
            (paper.paper_id,),
        ).fetchone()
        if row and row["parse_status"] == "complete":
            return

        downstream_signals = {
            "M2": {"method_reference": bool(paper.method_summary), "method_summary": paper.method_summary},
            "M3": {"experiment_protocol": False, "basis": ""},
            "M4": {"analysis_patterns": bool(paper.key_results), "basis": paper.key_results},
            "M5": {"citation_ready": bool(paper.title and paper.authors), "bibtex_ready": bool(paper.identifiers.doi or paper.identifiers.arxiv_id)},
        }
        section_summaries = {
            "abstract": paper.abstract,
            "problem": paper.problem_statement,
            "method": paper.method_summary,
            "results": paper.key_results,
            "limitations": [lim.limitation for lim in paper.limitations_noted],
        }
        conn.execute(
            """
            INSERT INTO literature_extractions (
                paper_id, metadata_status, fulltext_status, parse_status, parse_backend,
                parsed_at, extraction_sources, missing_fields, section_summaries,
                downstream_signals, confidence, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(paper_id) DO UPDATE SET
                metadata_status = CASE
                    WHEN literature_extractions.metadata_status = 'complete' THEN literature_extractions.metadata_status
                    ELSE excluded.metadata_status
                END,
                fulltext_status = CASE
                    WHEN literature_extractions.fulltext_status IN ('parsed', 'parsed_fulltext') THEN literature_extractions.fulltext_status
                    ELSE excluded.fulltext_status
                END,
                parse_status = CASE
                    WHEN literature_extractions.parse_status = 'complete' THEN literature_extractions.parse_status
                    ELSE excluded.parse_status
                END,
                parse_backend = CASE
                    WHEN literature_extractions.parse_backend != '' THEN literature_extractions.parse_backend
                    ELSE excluded.parse_backend
                END,
                parsed_at = excluded.parsed_at,
                extraction_sources = CASE
                    WHEN literature_extractions.parse_status = 'complete' THEN literature_extractions.extraction_sources
                    ELSE excluded.extraction_sources
                END,
                missing_fields = excluded.missing_fields,
                section_summaries = CASE
                    WHEN literature_extractions.parse_status = 'complete' THEN literature_extractions.section_summaries
                    ELSE excluded.section_summaries
                END,
                downstream_signals = CASE
                    WHEN literature_extractions.parse_status = 'complete' THEN literature_extractions.downstream_signals
                    ELSE excluded.downstream_signals
                END,
                confidence = CASE
                    WHEN literature_extractions.confidence = 'high' THEN literature_extractions.confidence
                    ELSE excluded.confidence
                END,
                notes = CASE
                    WHEN literature_extractions.notes != '' THEN literature_extractions.notes
                    ELSE excluded.notes
                END
            """,
            (
                paper.paper_id,
                metadata_status,
                "metadata_only",
                parse_status,
                "metadata_import",
                datetime.now().isoformat(),
                json.dumps(["metadata"], ensure_ascii=False),
                json.dumps(missing_fields, ensure_ascii=False),
                json.dumps(section_summaries, ensure_ascii=False),
                json.dumps(downstream_signals, ensure_ascii=False),
                "medium" if parse_status == "partial" else "low",
                "Auto-created from paper metadata; replace with full-text parse when PDF/HTML is readable.",
            ),
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
