"""Query cache for search results to avoid redundant API calls."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from .models import QueryCacheEntry

if TYPE_CHECKING:
    from .db import DatabaseManager

logger = logging.getLogger(__name__)


def _hash_query(queries: list[str]) -> str:
    """Deterministic hash of a list of query strings."""
    normalized = "|".join(sorted(q.strip().lower() for q in queries))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class QueryCache:
    """SQLite-backed query cache with TTL expiration."""

    def __init__(self, db: DatabaseManager, ttl_days: int = 180):
        self.db = db
        self.ttl_days = ttl_days

    def get(self, queries: list[str]) -> QueryCacheEntry | None:
        """Retrieve cached results if not expired."""
        qhash = _hash_query(queries)
        row = self.db.fetchone(
            "SELECT * FROM query_cache WHERE query_hash = ?", (qhash,)
        )
        if not row:
            return None

        entry = QueryCacheEntry(
            query_hash=row["query_hash"],
            query_text=row["query_text"],
            cached_at=row["cached_at"],
            expires_at=row["expires_at"],
            results=json.loads(row["results"] or "[]"),
            total_hits=row["total_hits"],
        )

        if entry.is_expired():
            logger.debug("Cache entry %s expired, removing", qhash)
            self.db.execute("DELETE FROM query_cache WHERE query_hash = ?", (qhash,))
            return None

        return entry

    def set(
        self,
        queries: list[str],
        results: list[dict[str, Any]],
        total_hits: int = 0,
    ) -> QueryCacheEntry:
        """Store results in cache."""
        qhash = _hash_query(queries)
        query_text = " | ".join(queries)
        cached_at = datetime.now().isoformat()
        expires_at = (datetime.now() + timedelta(days=self.ttl_days)).isoformat()

        self.db.execute(
            """
            INSERT INTO query_cache (query_hash, query_text, cached_at, expires_at, results, total_hits)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(query_hash) DO UPDATE SET
                query_text=excluded.query_text,
                cached_at=excluded.cached_at,
                expires_at=excluded.expires_at,
                results=excluded.results,
                total_hits=excluded.total_hits
            """,
            (qhash, query_text, cached_at, expires_at, json.dumps(results), total_hits),
        )

        return QueryCacheEntry(
            query_hash=qhash,
            query_text=query_text,
            cached_at=cached_at,
            expires_at=expires_at,
            results=results,
            total_hits=total_hits,
        )

    def invalidate(self, queries: list[str]) -> bool:
        """Remove a specific cache entry. Returns True if existed."""
        qhash = _hash_query(queries)
        cur = self.db.execute("DELETE FROM query_cache WHERE query_hash = ?", (qhash,))
        return cur.rowcount > 0

    def invalidate_all(self) -> int:
        """Remove all cache entries. Returns count removed."""
        cur = self.db.execute("DELETE FROM query_cache")
        return cur.rowcount

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        now = datetime.now().isoformat()
        cur = self.db.execute("DELETE FROM query_cache WHERE expires_at < ?", (now,))
        return cur.rowcount
