"""Data models for the Public Literature Database.

Defines dataclasses for all entities and the complete SQLite schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class SourceType(str, Enum):
    ACADEMIC = "academic"
    NEWS = "news"
    OFFICIAL = "official"
    EXPERT = "expert"
    BLOG = "blog"


class VerificationStatus(str, Enum):
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CodeAvailability(str, Enum):
    OPEN_SOURCE = "open_source"
    BROKEN = "broken"
    CLOSED = "closed"


class ArtifactStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    PENDING = "pending"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


class ParseStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    NOT_ATTEMPTED = "not_attempted"


class MetadataStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


@dataclass
class LiteratureDiscovery:
    """Search-result provenance for a retained or screened paper."""

    discovery_id: str
    paper_id: str = ""
    search_surface: str = ""  # public_db | semantic_scholar | openalex | arxiv | crossref | web | citation_chain
    query_text: str = ""
    result_rank: int = 0
    result_url: str = ""
    metadata_source: str = ""
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    screened_status: str = "retained"  # retained | rejected | duplicate | pending
    retained_reason: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LiteratureDiscovery:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class LiteratureArtifact:
    """Acquisition state for a paper artifact such as PDF, HTML, BibTeX, or source TeX."""

    artifact_id: str
    paper_id: str = ""
    artifact_type: str = "pdf"  # pdf | html | xml | abstract | bibtex | source_tex | supplement
    uri: str = ""
    local_path: str = ""
    status: str = ArtifactStatus.UNKNOWN
    sha256: str = ""
    attempted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    failure_reason: str = ""
    recovery_actions: list[str] = field(default_factory=list)
    license_note: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LiteratureArtifact:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class LiteratureExtraction:
    """Structured parse profile used by M2/M3/M4/M5 instead of ad hoc notes."""

    paper_id: str
    metadata_status: str = MetadataStatus.PARTIAL
    fulltext_status: str = "metadata_only"  # parsed_fulltext | partial_fulltext | metadata_only | parse_failed | unavailable
    parse_status: str = ParseStatus.PARTIAL
    parse_backend: str = ""  # pdftotext | pdfminer | pymupdf | html_text | xml_text | source_log_card | manual_card
    parsed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    extraction_sources: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    section_summaries: dict[str, Any] = field(default_factory=dict)
    downstream_signals: dict[str, Any] = field(default_factory=dict)
    confidence: str = ConfidenceLevel.MEDIUM
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LiteratureExtraction:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class LimitationEntry:
    """A single limitation note with provenance."""

    limitation: str
    source_project: str = ""
    noted_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LimitationEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PaperIdentifiers:
    """Multiple external identifiers for a paper."""

    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    dblp_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PaperIdentifiers:
        if not data:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Paper:
    """A paper entity in the public literature database."""

    paper_id: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    venue: str = ""
    year: int = 0
    date: str = ""
    url: str = ""
    pdf_url: str = ""
    type: str = SourceType.ACADEMIC

    # Identifiers
    identifiers: PaperIdentifiers = field(default_factory=PaperIdentifiers)

    # Assessments
    credibility_score: int = 3
    verification_status: str = VerificationStatus.UNVERIFIED
    code_availability: str = CodeAvailability.CLOSED
    code_url: str = ""

    # Content summaries
    abstract: str = ""
    problem_statement: str = ""
    method_summary: str = ""
    key_results: list[str] = field(default_factory=list)

    # Limitations with provenance
    limitations_noted: list[LimitationEntry] = field(default_factory=list)

    # Metadata
    first_surveyed_at: str = ""
    last_updated_at: str = ""
    survey_count: int = 0
    citation_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["identifiers"] = self.identifiers.to_dict()
        d["limitations_noted"] = [lim.to_dict() for lim in self.limitations_noted]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Paper:
        kwargs = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        kwargs["identifiers"] = PaperIdentifiers.from_dict(data.get("identifiers"))
        raw_lims = data.get("limitations_noted", [])
        if raw_lims and isinstance(raw_lims[0], str):
            # Legacy string format migration
            kwargs["limitations_noted"] = [
                LimitationEntry(limitation=lim) for lim in raw_lims
            ]
        else:
            kwargs["limitations_noted"] = [
                LimitationEntry.from_dict(lim) for lim in raw_lims
            ]
        return cls(**kwargs)


@dataclass
class Claim:
    """A domain-agnostic claim supported or contradicted by papers."""

    claim_id: str
    statement: str = ""
    confidence: str = ConfidenceLevel.MEDIUM
    supporting_papers: list[str] = field(default_factory=list)
    contradicting_papers: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    first_stated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Claim:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DomainTag:
    """A tag in the hierarchical domain taxonomy."""

    tag_id: str
    name: str = ""
    aliases: list[str] = field(default_factory=list)
    parent: Optional[str] = None
    level: int = 1
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainTag:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PaperTag:
    """Association between a paper and a domain tag."""

    paper_id: str
    tag_id: str
    confidence: str = ConfidenceLevel.MEDIUM
    source: str = "manual"  # manual | auto_keyword | auto_abstract
    added_by_project: str = ""
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaperTag:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Survey:
    """A survey session tracking provenance and reuse statistics."""

    survey_id: str
    project_name: str = ""
    topic: str = ""
    status: str = "in_progress"  # in_progress | completed | failed
    start_at: str = ""
    end_at: str = ""
    search_queries: list[str] = field(default_factory=list)
    papers_discovered: list[str] = field(default_factory=list)
    papers_from_db: int = 0
    papers_from_web: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Survey:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class QueryCacheEntry:
    """Cached search query results."""

    query_hash: str
    query_text: str
    cached_at: str
    expires_at: str
    results: list[dict[str, Any]] = field(default_factory=list)
    total_hits: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueryCacheEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def is_expired(self) -> bool:
        try:
            return datetime.now() > datetime.fromisoformat(self.expires_at)
        except (ValueError, TypeError):
            return True


@dataclass
class QueryResult:
    """Result of a literature database query."""

    papers: list[Paper] = field(default_factory=list)
    total_count: int = 0
    query_time_ms: float = 0.0
    from_cache: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "papers": [p.to_dict() for p in self.papers],
            "total_count": self.total_count,
            "query_time_ms": self.query_time_ms,
            "from_cache": self.from_cache,
        }


# ---------------------------------------------------------------------------
# SQL Schema Definition
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 2

CREATE_TABLES_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS _schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Papers: core literature entities
CREATE TABLE IF NOT EXISTS papers (
    paper_id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    authors TEXT NOT NULL DEFAULT '[]',  -- JSON array
    venue TEXT NOT NULL DEFAULT '',
    year INTEGER NOT NULL DEFAULT 0,
    date TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    pdf_url TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL DEFAULT 'academic',
    identifiers TEXT NOT NULL DEFAULT '{}',  -- JSON object
    credibility_score INTEGER NOT NULL DEFAULT 3 CHECK (credibility_score BETWEEN 1 AND 5),
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    code_availability TEXT NOT NULL DEFAULT 'closed',
    code_url TEXT NOT NULL DEFAULT '',
    abstract TEXT NOT NULL DEFAULT '',
    problem_statement TEXT NOT NULL DEFAULT '',
    method_summary TEXT NOT NULL DEFAULT '',
    key_results TEXT NOT NULL DEFAULT '[]',  -- JSON array
    limitations_noted TEXT NOT NULL DEFAULT '[]',  -- JSON array of objects
    first_surveyed_at TEXT NOT NULL DEFAULT '',
    last_updated_at TEXT NOT NULL DEFAULT '',
    survey_count INTEGER NOT NULL DEFAULT 0,
    citation_count INTEGER NOT NULL DEFAULT 0
);

-- Full-text search virtual table for papers
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    title,
    abstract,
    problem_statement,
    method_summary,
    content='papers',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS index synchronized
CREATE TRIGGER IF NOT EXISTS papers_ai AFTER INSERT ON papers BEGIN
    INSERT INTO papers_fts(rowid, title, abstract, problem_statement, method_summary)
    VALUES (new.rowid, new.title, new.abstract, new.problem_statement, new.method_summary);
END;

CREATE TRIGGER IF NOT EXISTS papers_ad AFTER DELETE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, abstract, problem_statement, method_summary)
    VALUES ('delete', old.rowid, old.title, old.abstract, old.problem_statement, old.method_summary);
END;

CREATE TRIGGER IF NOT EXISTS papers_au AFTER UPDATE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, abstract, problem_statement, method_summary)
    VALUES ('delete', old.rowid, old.title, old.abstract, old.problem_statement, old.method_summary);
    INSERT INTO papers_fts(rowid, title, abstract, problem_statement, method_summary)
    VALUES (new.rowid, new.title, new.abstract, new.problem_statement, new.method_summary);
END;

-- External identifier lookups
CREATE TABLE IF NOT EXISTS paper_identifiers (
    paper_id TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    id_type TEXT NOT NULL,  -- 'arxiv', 'doi', 's2', 'dblp'
    id_value TEXT NOT NULL,
    PRIMARY KEY (id_type, id_value)
);

CREATE INDEX IF NOT EXISTS idx_paper_identifiers_paper ON paper_identifiers(paper_id);

-- Search-result provenance. Retained papers are linked after canonicalization;
-- rejected candidates may be imported later when a canonical paper is created.
CREATE TABLE IF NOT EXISTS literature_discovery (
    discovery_id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    search_surface TEXT NOT NULL DEFAULT '',
    query_text TEXT NOT NULL DEFAULT '',
    result_rank INTEGER NOT NULL DEFAULT 0,
    result_url TEXT NOT NULL DEFAULT '',
    metadata_source TEXT NOT NULL DEFAULT '',
    discovered_at TEXT NOT NULL DEFAULT (datetime('now')),
    screened_status TEXT NOT NULL DEFAULT 'retained',
    retained_reason TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_literature_discovery_paper ON literature_discovery(paper_id);
CREATE INDEX IF NOT EXISTS idx_literature_discovery_query ON literature_discovery(query_text);
CREATE INDEX IF NOT EXISTS idx_literature_discovery_surface ON literature_discovery(search_surface);

-- Acquisition state for PDFs, HTML, BibTeX, source TeX, and supplements.
CREATE TABLE IF NOT EXISTS literature_artifacts (
    artifact_id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL DEFAULT 'pdf',
    uri TEXT NOT NULL DEFAULT '',
    local_path TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'unknown',
    sha256 TEXT NOT NULL DEFAULT '',
    attempted_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    failure_reason TEXT NOT NULL DEFAULT '',
    recovery_actions TEXT NOT NULL DEFAULT '[]',
    license_note TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_literature_artifacts_paper ON literature_artifacts(paper_id);
CREATE INDEX IF NOT EXISTS idx_literature_artifacts_status ON literature_artifacts(status);
CREATE INDEX IF NOT EXISTS idx_literature_artifacts_type ON literature_artifacts(artifact_type);

-- Structured parse profile consumed by downstream modules.
CREATE TABLE IF NOT EXISTS literature_extractions (
    paper_id TEXT PRIMARY KEY REFERENCES papers(paper_id) ON DELETE CASCADE,
    metadata_status TEXT NOT NULL DEFAULT 'partial',
    fulltext_status TEXT NOT NULL DEFAULT 'metadata_only',
    parse_status TEXT NOT NULL DEFAULT 'partial',
    parse_backend TEXT NOT NULL DEFAULT '',
    parsed_at TEXT NOT NULL DEFAULT (datetime('now')),
    extraction_sources TEXT NOT NULL DEFAULT '[]',
    missing_fields TEXT NOT NULL DEFAULT '[]',
    section_summaries TEXT NOT NULL DEFAULT '{}',
    downstream_signals TEXT NOT NULL DEFAULT '{}',
    confidence TEXT NOT NULL DEFAULT 'medium',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_literature_extractions_parse_status ON literature_extractions(parse_status);
CREATE INDEX IF NOT EXISTS idx_literature_extractions_metadata_status ON literature_extractions(metadata_status);

-- Claims: domain-agnostic knowledge claims
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    statement TEXT NOT NULL DEFAULT '',
    confidence TEXT NOT NULL DEFAULT 'medium',
    domains TEXT NOT NULL DEFAULT '[]',  -- JSON array
    first_stated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Claim-paper associations
CREATE TABLE IF NOT EXISTS claim_papers (
    claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    paper_id TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    relation TEXT NOT NULL DEFAULT 'supporting',  -- supporting | contradicting
    PRIMARY KEY (claim_id, paper_id, relation)
);

CREATE INDEX IF NOT EXISTS idx_claim_papers_claim ON claim_papers(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_papers_paper ON claim_papers(paper_id);

-- Domain tags: hierarchical taxonomy
CREATE TABLE IF NOT EXISTS domain_tags (
    tag_id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    aliases TEXT NOT NULL DEFAULT '[]',  -- JSON array
    parent TEXT REFERENCES domain_tags(tag_id) ON DELETE SET NULL,
    level INTEGER NOT NULL DEFAULT 1,
    description TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_domain_tags_parent ON domain_tags(parent);

-- Paper-tag associations
CREATE TABLE IF NOT EXISTS paper_tags (
    paper_id TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    tag_id TEXT NOT NULL REFERENCES domain_tags(tag_id) ON DELETE CASCADE,
    confidence TEXT NOT NULL DEFAULT 'medium',
    source TEXT NOT NULL DEFAULT 'manual',
    added_by_project TEXT NOT NULL DEFAULT '',
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (paper_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_tags_tag ON paper_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_paper_tags_project ON paper_tags(added_by_project);

-- Surveys: survey session tracking
CREATE TABLE IF NOT EXISTS surveys (
    survey_id TEXT PRIMARY KEY,
    project_name TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'in_progress',
    start_at TEXT NOT NULL DEFAULT '',
    end_at TEXT NOT NULL DEFAULT '',
    search_queries TEXT NOT NULL DEFAULT '[]',  -- JSON array
    papers_discovered TEXT NOT NULL DEFAULT '[]',  -- JSON array
    papers_from_db INTEGER NOT NULL DEFAULT 0,
    papers_from_web INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_surveys_project ON surveys(project_name);

-- Query cache
CREATE TABLE IF NOT EXISTS query_cache (
    query_hash TEXT PRIMARY KEY,
    query_text TEXT NOT NULL DEFAULT '',
    cached_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL DEFAULT '',
    results TEXT NOT NULL DEFAULT '[]',  -- JSON array
    total_hits INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_query_cache_expires ON query_cache(expires_at);

-- Paper statistics / analytics view
CREATE TABLE IF NOT EXISTS paper_tag_stats (
    tag_id TEXT NOT NULL REFERENCES domain_tags(tag_id) ON DELETE CASCADE,
    paper_count INTEGER NOT NULL DEFAULT 0,
    avg_credibility REAL NOT NULL DEFAULT 0.0,
    last_updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (tag_id)
);
"""

MIGRATIONS: dict[int, str] = {
    # CREATE_TABLES_SQL is idempotent and creates v2 literature ingestion tables
    # before this version marker is advanced.
    2: "",
}
