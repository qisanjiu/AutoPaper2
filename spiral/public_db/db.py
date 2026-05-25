"""SQLite database layer for the Public Literature Database.

Provides connection management, transaction handling, schema initialization,
migrations, and WAL mode for improved concurrency.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional

from .models import CREATE_TABLES_SQL, MIGRATIONS, SCHEMA_VERSION

logger = logging.getLogger(__name__)

# SQLite pragmas for robustness and performance
PRAGMAS = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA foreign_keys=ON;",
    "PRAGMA temp_store=MEMORY;",
    "PRAGMA mmap_size=268435456;",  # 256 MB memory-mapped I/O
    "PRAGMA cache_size=-65536;",  # 64 MB page cache
]


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


class SchemaError(DatabaseError):
    """Raised when schema initialization or migration fails."""
    pass


class DatabaseManager:
    """Manages SQLite connections, transactions, and schema lifecycle.

    Thread-safe via connection-per-thread pooling and WAL mode.
    """

    def __init__(
        self,
        db_path: str | Path,
        timeout: float = 30.0,
        detect_types: bool = False,
    ):
        self.db_path = Path(db_path)
        self.timeout = timeout
        self.detect_types = detect_types
        self._local = threading.local()
        self._lock = threading.RLock()
        self._connections: set[sqlite3.Connection] = set()
        self._initialized = False

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Create a new SQLite connection with optimal settings."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=self.timeout,
            detect_types=sqlite3.PARSE_DECLTYPES if self.detect_types else 0,
            isolation_level=None,  # We manage transactions explicitly
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        # Enable access to columns by name
        conn.execute("PRAGMA case_sensitive_like=OFF;")
        for pragma in PRAGMAS:
            try:
                conn.execute(pragma)
            except sqlite3.Error as exc:
                logger.warning("Failed to set pragma %s: %s", pragma, exc)
        return conn

    def get_connection(self) -> sqlite3.Connection:
        """Return a thread-local connection, creating one if necessary."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = self._connect()
            with self._lock:
                self._connections.add(self._local.conn)
        return self._local.conn

    def close(self) -> None:
        """Close the thread-local connection if open."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            conn = self._local.conn
            try:
                conn.close()
            except sqlite3.Error:
                pass
            with self._lock:
                self._connections.discard(conn)
            self._local.conn = None

    def close_all(self) -> None:
        """Close all known connections across threads (best-effort)."""
        self.close()
        with self._lock:
            connections = list(self._connections)
            self._connections.clear()
        for conn in connections:
            try:
                conn.close()
            except sqlite3.Error:
                pass

    def __enter__(self) -> DatabaseManager:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close_all()

    def __del__(self) -> None:
        try:
            self.close_all()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Transaction context manager
    # ------------------------------------------------------------------

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for atomic transactions with automatic rollback on error.

        Usage::
            with db.transaction() as conn:
                conn.execute("INSERT INTO ...")
                conn.execute("UPDATE ...")
        """
        conn = self.get_connection()
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    @contextmanager
    def savepoint(self, name: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
        """Nested savepoint for complex operations."""
        conn = self.get_connection()
        sp_name = name or f"sp_{int(time.time() * 1000)}"
        conn.execute(f"SAVEPOINT {sp_name}")
        try:
            yield conn
            conn.execute(f"RELEASE SAVEPOINT {sp_name}")
        except Exception:
            conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
            raise

    # ------------------------------------------------------------------
    # Schema lifecycle
    # ------------------------------------------------------------------

    def init_schema(self) -> None:
        """Initialize or upgrade the database schema."""
        with self._lock:
            conn = self.get_connection()
            # executescript() implicitly commits, so we do NOT wrap it in our
            # transaction() context manager.
            conn.executescript(CREATE_TABLES_SQL)

            # Schema version tracking (now run inside an explicit transaction)
            conn.execute("BEGIN IMMEDIATE")
            try:
                cur = conn.execute(
                    "SELECT version FROM _schema_version ORDER BY version DESC LIMIT 1"
                )
                row = cur.fetchone()
                current_version = row[0] if row else 0

                if current_version < SCHEMA_VERSION:
                    logger.info(
                        "Migrating schema from %d to %d", current_version, SCHEMA_VERSION
                    )
                    for ver in range(current_version + 1, SCHEMA_VERSION + 1):
                        migration = MIGRATIONS.get(ver)
                        if migration:
                            conn.executescript(migration)
                            logger.info("Applied migration %d", ver)
                    conn.execute(
                        "INSERT INTO _schema_version(version) VALUES (?)",
                        (SCHEMA_VERSION,),
                    )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

            self._initialized = True
            logger.info("Schema initialized at version %d", SCHEMA_VERSION)

    def verify_schema(self) -> bool:
        """Quick sanity check that required tables exist."""
        required = {
            "papers",
            "claims",
            "domain_tags",
            "paper_tags",
            "surveys",
            "query_cache",
            "paper_identifiers",
            "claim_papers",
        }
        conn = self.get_connection()
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        existing = {row[0] for row in cur.fetchall()}
        return required.issubset(existing)

    def reset_schema(self) -> None:
        """Drop and recreate all tables (DESTRUCTIVE — testing only).

        Closes the connection, deletes the database file (and WAL/shm
        companions), then re-initializes a fresh schema.
        """
        self.close_all()
        db_path = Path(self.db_path)
        for suffix in ("", "-wal", "-shm"):
            file = db_path.with_suffix(db_path.suffix + suffix)
            if file.exists():
                file.unlink()
        # Reconnect and init
        self._local.conn = None
        self.init_schema()

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def execute(
        self,
        sql: str,
        parameters: tuple[Any, ...] | list[tuple[Any, ...]] | None = None,
    ) -> sqlite3.Cursor:
        """Execute SQL with the current connection."""
        conn = self.get_connection()
        if parameters is None:
            return conn.execute(sql)
        if isinstance(parameters, list):
            return conn.executemany(sql, parameters)
        return conn.execute(sql, parameters)

    def fetchone(self, sql: str, parameters: tuple[Any, ...] | None = None) -> Optional[sqlite3.Row]:
        """Execute and return the first row."""
        cur = self.execute(sql, parameters)
        try:
            return cur.fetchone()
        finally:
            cur.close()

    def fetchall(self, sql: str, parameters: tuple[Any, ...] | None = None) -> list[sqlite3.Row]:
        """Execute and return all rows."""
        cur = self.execute(sql, parameters)
        try:
            return cur.fetchall()
        finally:
            cur.close()

    def fetchval(self, sql: str, parameters: tuple[Any, ...] | None = None) -> Any:
        """Execute and return a single scalar value."""
        row = self.fetchone(sql, parameters)
        return row[0] if row else None

    # ------------------------------------------------------------------
    # JSON helpers (SQLite 3.9+ has json1; we use text fallback for safety)
    # ------------------------------------------------------------------

    def register_json_functions(self) -> None:
        """Register Python-based JSON helpers if sqlite3 lacks json1."""
        conn = self.get_connection()
        conn.create_function("py_json_contains", 2, _py_json_contains, deterministic=True)
        conn.create_function("py_json_array_length", 1, _py_json_array_length, deterministic=True)


def _py_json_contains(json_text: str, value: str) -> int:
    """Return 1 if JSON array contains value, else 0."""
    try:
        arr = json.loads(json_text or "[]")
        return 1 if value in arr else 0
    except Exception:
        return 0


def _py_json_array_length(json_text: str) -> int:
    """Return length of JSON array."""
    try:
        arr = json.loads(json_text or "[]")
        return len(arr)
    except Exception:
        return 0
