"""Survey Memory — Persistent research memory for Module 1 (Domain Survey).

Inspired by deepResearch's Memory & Persistence System.
Provides structured tracking of search batches, findings, sources, and gaps
across iterative search loops.
"""

from __future__ import annotations

import yaml
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class SurveyStatus(str, Enum):
    PLANNING = "planning"
    SEARCHING = "searching"
    VERIFYING = "verifying"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VerificationStatus(str, Enum):
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"


class SourceType(str, Enum):
    ACADEMIC = "academic"
    NEWS = "news"
    OFFICIAL = "official"
    EXPERT = "expert"
    BLOG = "blog"


class CodeAvailability(str, Enum):
    OPEN_SOURCE = "open_source"
    BROKEN = "broken"
    CLOSED = "closed"


class BatchStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    PASSED = "passed"
    REWORK = "rework"
    FAILED = "failed"


@dataclass
class SearchBatch:
    batch_id: int
    status: str = "in_progress"  # in_progress | awaiting_review | passed | rework | failed
    round: int = 1  # Which search round this batch belongs to (1-3)
    queries: list[str] = field(default_factory=list)
    sources_found: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchBatch:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class RoundReview:
    round: int
    verdict: str = ""  # PASS | REWORK | HALT
    score: float = 0.0
    reviewer_batch_id: int = 0
    high_priority_issues: int = 0
    medium_priority_issues: int = 0
    low_priority_issues: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoundReview:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class KeyClaim:
    id: str
    claim: str = ""
    confidence: str = ConfidenceLevel.MEDIUM
    sources: list[str] = field(default_factory=list)
    verification_status: str = VerificationStatus.UNVERIFIED
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["confidence"] = str(self.confidence.value if isinstance(self.confidence, ConfidenceLevel) else self.confidence)
        d["verification_status"] = str(self.verification_status.value if isinstance(self.verification_status, VerificationStatus) else self.verification_status)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KeyClaim:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class GapType(str, Enum):
    VACANCY = "vacancy"       # VG: 空白型 Gap
    ENHANCEMENT = "enhancement"  # EG: 改进型 Gap
    VALIDATION = "validation"    # ValG: 验证型 Gap


@dataclass
class Gap:
    id: str
    description: str = ""
    evidence_sources: list[str] = field(default_factory=list)
    confidence: str = ConfidenceLevel.MEDIUM
    related_solution: str = ""  # Link to Solution Arsenal
    gap_type: str = GapType.VACANCY  # vacancy | enhancement | validation
    # Enhancement Gap 专用字段
    target_component: str = ""  # 被改进的组件/模块名称（仅 EG 填写）
    baseline_framework: str = ""  # 目标基线框架（仅 EG 填写）
    bottleneck_description: str = ""  # 具体瓶颈描述（仅 EG 填写）

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["confidence"] = str(self.confidence.value if isinstance(self.confidence, ConfidenceLevel) else self.confidence)
        d["gap_type"] = str(self.gap_type.value if isinstance(self.gap_type, GapType) else self.gap_type)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Gap:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Contradiction:
    id: str
    claim_a: str = ""
    claim_b: str = ""
    resolution: str = ""
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Contradiction:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Source:
    id: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    venue: str = ""
    date: str = ""
    url: str = ""
    type: str = SourceType.ACADEMIC
    credibility_score: int = 3  # 1-5
    verification_status: str = VerificationStatus.UNVERIFIED
    key_claims: list[str] = field(default_factory=list)
    limitations_noted: list[str] = field(default_factory=list)
    code_availability: str = CodeAvailability.CLOSED
    relevance_to_our_gap: str = ""
    background: str = ""
    contributions: list[str] = field(default_factory=list)
    model: str = ""
    method: str = ""
    experiment_setup: str = ""
    results: str = ""
    analysis: str = ""
    conclusion: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = str(self.type.value if isinstance(self.type, SourceType) else self.type)
        d["verification_status"] = str(self.verification_status.value if isinstance(self.verification_status, VerificationStatus) else self.verification_status)
        d["code_availability"] = str(self.code_availability.value if isinstance(self.code_availability, CodeAvailability) else self.code_availability)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Source:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SurveyMemory:
    """In-memory representation of survey memory."""

    topic: str = ""
    status: str = SurveyStatus.PLANNING
    search_batches: list[SearchBatch] = field(default_factory=list)
    round_reviews: list[RoundReview] = field(default_factory=list)
    findings: dict[str, Any] = field(default_factory=lambda: {
        "key_claims": [],
        "gaps": [],
        "contradictions": [],
    })
    source_registry: dict[str, Source] = field(default_factory=dict)

    def add_batch(self, queries: list[str], round_num: int = 1) -> SearchBatch:
        batch = SearchBatch(
            batch_id=len(self.search_batches) + 1,
            queries=queries,
            round=round_num,
        )
        self.search_batches.append(batch)
        self.status = SurveyStatus.SEARCHING
        return batch

    def complete_batch(self, batch_id: int, sources_found: int) -> None:
        for batch in self.search_batches:
            if batch.batch_id == batch_id:
                batch.status = "completed"
                batch.sources_found = sources_found
                break

    def set_batch_status(self, batch_id: int, status: str) -> None:
        for batch in self.search_batches:
            if batch.batch_id == batch_id:
                batch.status = status
                break

    def add_source(self, source: Source) -> None:
        self.source_registry[source.id] = source

    def add_claim(self, claim: KeyClaim) -> None:
        claims = self.findings.setdefault("key_claims", [])
        claims[:] = [c for c in claims if c.get("id") != claim.id]
        claims.append(claim.to_dict())

    def add_gap(self, gap: Gap) -> None:
        gaps = self.findings.setdefault("gaps", [])
        gaps[:] = [g for g in gaps if g.get("id") != gap.id]
        gaps.append(gap.to_dict())

    def add_contradiction(self, contradiction: Contradiction) -> None:
        contradictions = self.findings.setdefault("contradictions", [])
        contradictions[:] = [c for c in contradictions if c.get("id") != contradiction.id]
        contradictions.append(contradiction.to_dict())

    def add_round_review(self, review: RoundReview) -> None:
        self.round_reviews[:] = [r for r in self.round_reviews if r.round != review.round]
        self.round_reviews.append(review)

    def get_source(self, source_id: str) -> Optional[Source]:
        return self.source_registry.get(source_id)

    def get_gap_confidence(self, gap_id: str) -> str:
        for g in self.findings.get("gaps", []):
            if g.get("id") == gap_id:
                return g.get("confidence", ConfidenceLevel.LOW)
        return ConfidenceLevel.LOW

    def get_sources_for_gap(self, gap_id: str) -> list[str]:
        for g in self.findings.get("gaps", []):
            if g.get("id") == gap_id:
                return g.get("evidence_sources", [])
        return []

    def get_round_batches(self, round_num: int) -> list[SearchBatch]:
        return [b for b in self.search_batches if b.round == round_num]

    def get_round_review(self, round_num: int) -> Optional[RoundReview]:
        for r in self.round_reviews:
            if r.round == round_num:
                return r
        return None

    def get_round_summary(self, round_num: int) -> dict[str, Any]:
        batches = self.get_round_batches(round_num)
        review = self.get_round_review(round_num)
        return {
            "round": round_num,
            "batch_count": len(batches),
            "total_sources_found": sum(b.sources_found for b in batches),
            "review_verdict": review.verdict if review else "none",
            "review_score": review.score if review else 0.0,
        }

    def undo_batch(self, batch_id: int) -> bool:
        """Remove a batch and all sources added in that batch.
        
        Returns True if a batch was removed.
        """
        original_len = len(self.search_batches)
        removed_batch = None
        for batch in self.search_batches:
            if batch.batch_id == batch_id:
                removed_batch = batch
                break
        
        if removed_batch is None:
            return False
            
        self.search_batches = [b for b in self.search_batches if b.batch_id != batch_id]
        
        # Also remove the review for this round if it's the only batch in that round
        round_batches = self.get_round_batches(removed_batch.round)
        if not round_batches:
            self.round_reviews = [r for r in self.round_reviews if r.round != removed_batch.round]
        
        return len(self.search_batches) < original_len

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "status": self.status.value if isinstance(self.status, SurveyStatus) else self.status,
            "search_batches": [b.to_dict() for b in self.search_batches],
            "round_reviews": [r.to_dict() for r in self.round_reviews],
            "findings": self.findings,
            "source_registry": {
                k: v.to_dict() for k, v in self.source_registry.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SurveyMemory:
        raw_status = data.get("status", SurveyStatus.PLANNING)
        status = raw_status if isinstance(raw_status, SurveyStatus) else SurveyStatus(raw_status)
        memory = cls(
            topic=data.get("topic", ""),
            status=status,
        )
        memory.search_batches = [
            SearchBatch.from_dict(b) for b in data.get("search_batches", [])
        ]
        memory.round_reviews = [
            RoundReview.from_dict(r) for r in data.get("round_reviews", [])
        ]
        memory.findings = data.get("findings", {
            "key_claims": [],
            "gaps": [],
            "contradictions": [],
        })
        memory.source_registry = {
            k: Source.from_dict(v)
            for k, v in data.get("source_registry", {}).items()
        }
        return memory


class SurveyMemoryManager:
    """Manages persistence of SurveyMemory to/from YAML file.

    Integrates with the framework-wide Public Literature Database for
    cross-project literature reuse.  If ``public_db`` is not provided,
    the manager auto-discovers the shared database located alongside
    the AutoPaper2 framework installation.
    """

    FILENAME = "survey_memory.yaml"

    def __init__(
        self,
        project_root: Path,
        public_db: Any | None = None,
        project_name: str = "",
        min_hit_threshold: int = 10,
        auto_connect: bool = True,
    ):
        self.path = project_root / "state" / self.FILENAME
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._memory: Optional[SurveyMemory] = None
        self.project_name = project_name or project_root.name
        self.min_hit_threshold = min_hit_threshold
        self._owns_public_db = False

        if public_db is not None:
            self.public_db = public_db
        elif auto_connect:
            self.public_db = self._auto_connect_public_db()
            self._owns_public_db = self.public_db is not None
        else:
            self.public_db = None

    @staticmethod
    def _auto_connect_public_db() -> Any | None:
        """Discover and connect to the framework-wide public literature DB.

        Returns a connected ``PublicLiteratureDB`` instance, or ``None`` if
        the framework configuration disables it or discovery fails.
        """
        try:
            from .public_db.config import DBConfig
            from .public_db.manager import PublicLiteratureDB

            cfg = DBConfig.default()
            if not cfg.enabled:
                return None

            db = PublicLiteratureDB(cfg)
            db.init_if_needed()
            return db
        except Exception:
            # Graceful degradation — public DB is optional
            return None

    def load(self) -> SurveyMemory:
        if self._memory is not None:
            return self._memory
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._memory = SurveyMemory.from_dict(data)
        else:
            self._memory = SurveyMemory()
        return self._memory

    def save(self, memory: SurveyMemory) -> None:
        self._memory = memory
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.dump(memory.to_dict(), f, allow_unicode=True, sort_keys=False)

    def close(self) -> None:
        public_db = getattr(self, "public_db", None)
        if self._owns_public_db and public_db is not None and hasattr(public_db, "close"):
            public_db.close()

    def __enter__(self) -> SurveyMemoryManager:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def exists(self) -> bool:
        return self.path.exists()

    def init(self, topic: str) -> SurveyMemory:
        memory = SurveyMemory(topic=topic, status=SurveyStatus.PLANNING)
        self.save(memory)
        return memory

    # ------------------------------------------------------------------
    # Public Literature Database integration
    # ------------------------------------------------------------------

    def search_with_public_db(
        self,
        queries: list[str],
        domain_tags: list[str] | None = None,
    ) -> tuple[list[Source], list[Source]]:
        """Search literature, returning (from_public_db, from_web) sources.

        Workflow:
            1. Check query cache in public DB.
            2. Query public DB for matching papers.
            3. If hits < min_hit_threshold, fall back to web search.
            4. Import new web results into public DB.
            5. Update query cache.
        """
        if self.public_db is None or not getattr(self.public_db, "config", None) or not self.public_db.config.enabled:
            # Public DB disabled — return empty DB results, all from web
            return [], []

        # Query public DB
        db_results: list[Source] = []
        for q in queries:
            result = self.public_db.query(
                keywords=q.split(),
                domain_tags=domain_tags,
                limit=self.min_hit_threshold * 2,
            )
            for paper in result.papers:
                src = self._paper_to_source(paper)
                if src.id not in {s.id for s in db_results}:
                    db_results.append(src)

        return db_results, []

    def import_sources_to_public_db(self, sources: list[Source]) -> dict[str, int]:
        """Export sources from this project's survey memory into the public DB."""
        if self.public_db is None:
            return {"imported": 0, "merged": 0}

        imported = 0
        merged = 0
        for src in sources:
            paper = self._source_to_paper(src)
            existing_id = self.public_db.check_duplicate(paper)
            if existing_id:
                self.public_db.update_paper(paper, source_project=self.project_name)
                merged += 1
            else:
                self.public_db.insert_paper(paper, source_project=self.project_name)
                imported += 1

        return {"imported": imported, "merged": merged}

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _paper_to_source(paper: Any) -> Source:
        """Convert a public DB Paper to a project-level Source."""
        return Source(
            id=paper.paper_id,
            title=paper.title,
            authors=paper.authors,
            venue=paper.venue,
            date=paper.date,
            url=paper.url,
            type=paper.type,
            credibility_score=paper.credibility_score,
            verification_status=paper.verification_status,
            key_claims=[],
            limitations_noted=[lim.limitation for lim in paper.limitations_noted],
            code_availability=paper.code_availability,
            relevance_to_our_gap="",
        )

    @staticmethod
    def _source_to_paper(src: Source) -> Any:
        """Convert a project-level Source to a public DB Paper."""
        from .public_db.models import LimitationEntry, Paper, PaperIdentifiers

        return Paper(
            paper_id=src.id,
            title=src.title,
            authors=src.authors,
            venue=src.venue,
            date=src.date,
            url=src.url,
            type=src.type,
            identifiers=PaperIdentifiers(),
            credibility_score=src.credibility_score,
            verification_status=src.verification_status,
            code_availability=src.code_availability,
            limitations_noted=[
                LimitationEntry(limitation=lim) for lim in src.limitations_noted
            ],
        )
