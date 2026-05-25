"""Public Literature Database — Cross-project literature reuse system for AutoPaper2."""

from __future__ import annotations

__all__ = [
    "PublicLiteratureDB",
    "Paper",
    "Claim",
    "DomainTag",
    "PaperTag",
    "Survey",
    "QueryCacheEntry",
    "PaperIdentifier",
    "MergePolicy",
    "TagEngine",
    "DBConfig",
]

from .models import (
    Paper,
    Claim,
    DomainTag,
    PaperTag,
    Survey,
    QueryCacheEntry,
    SourceType,
    VerificationStatus,
    ConfidenceLevel,
    CodeAvailability,
    QueryResult,
)
from .identifier import PaperIdentifier
from .merge import MergePolicy
from .tag_engine import TagEngine
from .config import DBConfig
from .manager import PublicLiteratureDB
