"""Comprehensive test suite for the Public Literature Database.

Covers:
  - Unit tests for individual modules (identifier, merge, tag engine, cache)
  - Integration tests for full CRUD + search workflows
  - Performance tests for large datasets
  - Concurrency tests for multi-threaded access
"""

from __future__ import annotations

import json
import os
import random
import shutil
import string
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

# Ensure imports work from project root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from spiral.public_db.config import DBConfig, MergePolicyConfig
from spiral.public_db.db import DatabaseManager, DatabaseError
from spiral.public_db.identifier import IdentificationError, PaperIdentifier
from spiral.public_db.merge import MergePolicy, deserialize_limitations, merge_papers, serialize_limitations
from spiral.public_db.models import (
    Claim,
    DomainTag,
    LimitationEntry,
    Paper,
    PaperIdentifiers,
    PaperTag,
    QueryCacheEntry,
    Survey,
)
from spiral.public_db.query_cache import QueryCache
from spiral.public_db.tag_engine import TagEngine, TagRule
from spiral.public_db.manager import PublicLiteratureDB
from spiral.public_db.importer import ProjectImporter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_paper(
    paper_id: str = "",
    title: str = "Test Paper",
    authors: list[str] | None = None,
    year: int = 2023,
    arxiv_id: str = "",
    doi: str = "",
    tags: list[str] | None = None,
    **kwargs,
) -> Paper:
    """Factory for test papers."""
    return Paper(
        paper_id=paper_id,
        title=title,
        authors=authors or ["Alice Author", "Bob Coauthor"],
        venue=kwargs.get("venue", "NeurIPS"),
        year=year,
        date=kwargs.get("date", f"{year}-12"),
        url=kwargs.get("url", "https://example.com/paper"),
        pdf_url=kwargs.get("pdf_url", ""),
        type=kwargs.get("type", "academic"),
        identifiers=PaperIdentifiers(
            arxiv_id=arxiv_id,
            doi=doi,
        ),
        credibility_score=kwargs.get("credibility_score", 3),
        verification_status=kwargs.get("verification_status", "unverified"),
        code_availability=kwargs.get("code_availability", "closed"),
        code_url=kwargs.get("code_url", ""),
        abstract=kwargs.get("abstract", "This is a test abstract about transformers."),
        problem_statement=kwargs.get("problem_statement", ""),
        method_summary=kwargs.get("method_summary", ""),
        key_results=kwargs.get("key_results", []),
        limitations_noted=kwargs.get("limitations_noted", []),
        survey_count=kwargs.get("survey_count", 1),
        citation_count=kwargs.get("citation_count", 0),
    )


class TempDBMixin:
    """Provides a temporary database for each test."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="pldb_test_")
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.config = DBConfig(
            db_path=self.db_path,
            enabled=True,
            auto_tagging=True,
        )
        self.db = PublicLiteratureDB(self.config)
        self.db.init()

    def tearDown(self) -> None:
        self.db.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 1. Unit Tests — Identifier
# ---------------------------------------------------------------------------

class TestIdentifier(unittest.TestCase):
    """Tests for PaperIdentifier deduplication logic."""

    def test_canonical_id_from_doi(self):
        paper = _make_paper(doi="10.5555/12345678")
        cid = PaperIdentifier.canonical_id(paper)
        self.assertEqual(cid, "doi:10.5555/12345678")

    def test_canonical_id_from_arxiv(self):
        paper = _make_paper(arxiv_id="2101.12345")
        cid = PaperIdentifier.canonical_id(paper)
        self.assertEqual(cid, "arxiv:2101.12345")

    def test_canonical_id_from_arxiv_with_prefix(self):
        paper = _make_paper(arxiv_id="arxiv:2101.12345")
        cid = PaperIdentifier.canonical_id(paper)
        self.assertEqual(cid, "arxiv:2101.12345")

    def test_canonical_id_fallback(self):
        paper = _make_paper(title="Attention Is All You Need", authors=["Vaswani, Ashish"], year=2017)
        cid = PaperIdentifier.canonical_id(paper)
        self.assertTrue(cid.startswith("Vaswani2017"))

    def test_canonical_id_raises_on_empty(self):
        paper = _make_paper(title="", authors=[], year=0)
        with self.assertRaises(IdentificationError):
            PaperIdentifier.canonical_id(paper)

    def test_extract_last_name_formats(self):
        self.assertEqual(PaperIdentifier._extract_last_name("Smith, John"), "Smith")
        self.assertEqual(PaperIdentifier._extract_last_name("John Smith"), "Smith")
        self.assertEqual(PaperIdentifier._extract_last_name("J. R. R. Tolkien"), "Tolkien")
        self.assertEqual(PaperIdentifier._extract_last_name("Dr. Martin Luther King Jr."), "King")

    def test_title_similarity_identical(self):
        a = "attention is all you need"
        self.assertEqual(PaperIdentifier._title_similarity(a, a), 1.0)

    def test_title_similarity_zero(self):
        self.assertEqual(PaperIdentifier._title_similarity("abc", "xyz"), 0.0)

    def test_title_similarity_partial(self):
        a = "transformer for time series forecasting"
        b = "transformer architecture in nlp"
        sim = PaperIdentifier._title_similarity(a, b)
        self.assertGreater(sim, 0.0)
        self.assertLess(sim, 1.0)


# ---------------------------------------------------------------------------
# 2. Unit Tests — Merge Policy
# ---------------------------------------------------------------------------

class TestMergePolicy(unittest.TestCase):
    """Tests for paper field merging logic."""

    def test_merge_takes_longer_title(self):
        existing = _make_paper(title="Short")
        incoming = _make_paper(title="A Much Longer Title Here")
        merged = merge_papers(existing, incoming)
        self.assertEqual(merged.title, "A Much Longer Title Here")

    def test_merge_credibility_weighted_average(self):
        existing = _make_paper(credibility_score=5, survey_count=3)
        incoming = _make_paper(credibility_score=3, survey_count=1)
        merged = merge_papers(existing, incoming)
        # (5*3 + 3) / 4 = 4.5 → round = 5
        self.assertEqual(merged.credibility_score, 5)

    def test_merge_limitations_append_unique(self):
        existing = _make_paper(
            limitations_noted=[LimitationEntry("slow training", "proj-a")]
        )
        incoming = _make_paper(
            limitations_noted=[
                LimitationEntry("slow training", "proj-b"),  # duplicate text
                LimitationEntry("high memory", "proj-b"),
            ]
        )
        merged = merge_papers(existing, incoming)
        self.assertEqual(len(merged.limitations_noted), 2)
        texts = [lim.limitation for lim in merged.limitations_noted]
        self.assertIn("slow training", texts)
        self.assertIn("high memory", texts)

    def test_merge_verification_upgrade(self):
        existing = _make_paper(verification_status="unverified")
        incoming = _make_paper(verification_status="confirmed")
        merged = merge_papers(existing, incoming)
        self.assertEqual(merged.verification_status, "confirmed")

    def test_merge_code_url_inheritance(self):
        existing = _make_paper(code_url="")
        incoming = _make_paper(code_url="https://github.com/test/repo")
        merged = merge_papers(existing, incoming)
        self.assertEqual(merged.code_url, "https://github.com/test/repo")

    def test_merge_survey_count_increment(self):
        existing = _make_paper(survey_count=5)
        incoming = _make_paper(survey_count=1)
        merged = merge_papers(existing, incoming)
        self.assertEqual(merged.survey_count, 6)

    def test_serialize_deserialize_limitations(self):
        lims = [LimitationEntry("issue A", "p1"), LimitationEntry("issue B", "p2")]
        raw = serialize_limitations(lims)
        restored = deserialize_limitations(raw)
        self.assertEqual(len(restored), 2)
        self.assertEqual(restored[0].limitation, "issue A")
        self.assertEqual(restored[0].source_project, "p1")

    def test_deserialize_legacy_strings(self):
        raw = json.dumps(["old string lim 1", "old string lim 2"])
        restored = deserialize_limitations(raw)
        self.assertEqual(len(restored), 2)
        self.assertEqual(restored[0].limitation, "old string lim 1")


# ---------------------------------------------------------------------------
# 3. Unit Tests — Tag Engine
# ---------------------------------------------------------------------------

class TestTagEngine(unittest.TestCase):
    """Tests for domain tag auto-derivation."""

    def test_matches_transformer(self):
        engine = TagEngine()
        paper = _make_paper(title="A New Transformer Architecture", abstract="We propose a novel attention mechanism.")
        tags = engine.tag_paper(paper)
        tag_ids = [t.tag_id for t in tags]
        self.assertIn("transformer", tag_ids)

    def test_matches_cv(self):
        engine = TagEngine()
        paper = _make_paper(title="Image Classification with CNNs")
        tags = engine.tag_paper(paper)
        tag_ids = [t.tag_id for t in tags]
        self.assertIn("computer_vision", tag_ids)
        self.assertIn("cnn", tag_ids)

    def test_no_false_positive(self):
        engine = TagEngine()
        paper = _make_paper(title="Gardening Tips for Beginners", abstract="How to grow tomatoes.")
        tags = engine.tag_paper(paper)
        tag_ids = [t.tag_id for t in tags]
        self.assertNotIn("transformer", tag_ids)
        self.assertNotIn("deep_learning", tag_ids)

    def test_custom_rule(self):
        engine = TagEngine()
        engine.add_rule(TagRule("custom_tag", ["xyzzy123"]))
        paper = _make_paper(title="Paper about xyzzy123")
        tags = engine.tag_paper(paper)
        tag_ids = [t.tag_id for t in tags]
        self.assertIn("custom_tag", tag_ids)

    def test_suggest_tags_for_query(self):
        engine = TagEngine()
        suggestions = engine.suggest_tags_for_query("vision transformer for object detection")
        self.assertIn("computer_vision", suggestions)
        self.assertIn("vision_transformer", suggestions)
        self.assertIn("object_detection", suggestions)


# ---------------------------------------------------------------------------
# 4. Unit Tests — Query Cache
# ---------------------------------------------------------------------------

class TestQueryCache(TempDBMixin, unittest.TestCase):
    """Tests for query caching layer."""

    def test_cache_roundtrip(self):
        cache = QueryCache(self.db.db, ttl_days=1)
        cache.set(["transformer", "forecasting"], [{"paper_id": "p1"}, {"paper_id": "p2"}], total_hits=10)

        entry = cache.get(["transformer", "forecasting"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry.total_hits, 10)
        self.assertEqual(len(entry.results), 2)

    def test_cache_order_independent(self):
        cache = QueryCache(self.db.db, ttl_days=1)
        cache.set(["a", "b"], [{"paper_id": "p1"}])

        entry = cache.get(["b", "a"])
        self.assertIsNotNone(entry)

    def test_cache_expiration(self):
        cache = QueryCache(self.db.db, ttl_days=0)
        cache.set(["old"], [{"paper_id": "p1"}])

        # Simulate immediate expiration by manipulating the DB directly
        self.db.db.execute(
            "UPDATE query_cache SET expires_at = datetime('now', '-1 day') WHERE query_hash = ?",
            ("b026324c6904b2a9cb4b88d6d61c81d1",),  # hash of "old" after sort
        )
        entry = cache.get(["old"])
        self.assertIsNone(entry)

    def test_cleanup_expired(self):
        cache = QueryCache(self.db.db, ttl_days=0)
        cache.set(["q1"], [{"paper_id": "p1"}])
        cache.set(["q2"], [{"paper_id": "p2"}])

        # Force expiration
        self.db.db.execute("UPDATE query_cache SET expires_at = datetime('now', '-1 day')")
        removed = cache.cleanup_expired()
        self.assertEqual(removed, 2)


# ---------------------------------------------------------------------------
# 5. Unit Tests — Database Manager
# ---------------------------------------------------------------------------

class TestDatabaseManager(unittest.TestCase):
    """Tests for low-level SQLite management."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.db = DatabaseManager(self.db_path)

    def tearDown(self) -> None:
        self.db.close_all()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_schema_creates_tables(self):
        self.db.init_schema()
        self.assertTrue(self.db.verify_schema())

    def test_transaction_rollback_on_error(self):
        self.db.init_schema()
        with self.assertRaises(ZeroDivisionError):
            with self.db.transaction() as conn:
                conn.execute("INSERT INTO _schema_version (version) VALUES (999)")
                1 / 0

        # Should not have been committed
        val = self.db.fetchval("SELECT COUNT(*) FROM _schema_version WHERE version = 999")
        self.assertEqual(val, 0)

    def test_savepoint_nested(self):
        self.db.init_schema()
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO _schema_version (version) VALUES (100)")
            with self.db.savepoint("inner"):
                conn.execute("INSERT INTO _schema_version (version) VALUES (200)")
                # inner savepoint releases normally

        vals = [r[0] for r in self.db.fetchall("SELECT version FROM _schema_version WHERE version IN (100, 200)")]
        self.assertIn(100, vals)
        self.assertIn(200, vals)

    def test_savepoint_rollback(self):
        self.db.init_schema()
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO _schema_version (version) VALUES (100)")
            with self.assertRaises(RuntimeError):
                with self.db.savepoint("inner"):
                    conn.execute("INSERT INTO _schema_version (version) VALUES (200)")
                    raise RuntimeError("abort inner")

        # 100 committed, 200 rolled back
        vals = [r[0] for r in self.db.fetchall("SELECT version FROM _schema_version WHERE version IN (100, 200)")]
        self.assertIn(100, vals)
        self.assertNotIn(200, vals)

    def test_close_all_closes_worker_thread_connections(self):
        self.db.init_schema()
        worker_connection_ids: list[int] = []

        def worker() -> None:
            conn = self.db.get_connection()
            worker_connection_ids.append(id(conn))
            conn.execute("SELECT 1").fetchone()

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

        self.assertEqual(len(worker_connection_ids), 1)
        self.assertGreaterEqual(len(self.db._connections), 1)

        self.db.close_all()

        self.assertEqual(len(self.db._connections), 0)

    def test_registered_json_functions_parse_json_arrays(self):
        self.db.init_schema()
        self.db.register_json_functions()

        self.assertEqual(
            self.db.fetchval("SELECT py_json_contains(?, ?)", ('["alpha", "beta"]', "beta")),
            1,
        )
        self.assertEqual(
            self.db.fetchval("SELECT py_json_array_length(?)", ('["alpha", "beta"]',)),
            2,
        )


# ---------------------------------------------------------------------------
# 6. Integration Tests — Full CRUD + Search
# ---------------------------------------------------------------------------

class TestIntegration(TempDBMixin, unittest.TestCase):
    """End-to-end integration tests."""

    def test_insert_and_get_paper(self):
        paper = _make_paper(title="Integration Test Paper", year=2024)
        pid = self.db.insert_paper(paper)
        self.assertTrue(pid)

        fetched = self.db.get_paper(pid)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "Integration Test Paper")
        self.assertEqual(fetched.year, 2024)

    def test_insert_duplicate_raises(self):
        paper = _make_paper(arxiv_id="2401.00001")
        self.db.insert_paper(paper)

        dup = _make_paper(arxiv_id="2401.00001", title="Different Title")
        with self.assertRaises(ValueError):
            self.db.insert_paper(dup)

    def test_update_paper_merge(self):
        p1 = _make_paper(title="Original", credibility_score=3, survey_count=1)
        pid = self.db.insert_paper(p1)

        p2 = _make_paper(title="Updated Longer Title", credibility_score=5, survey_count=1)
        p2.paper_id = pid
        self.db.update_paper(p2)

        fetched = self.db.get_paper(pid)
        self.assertEqual(fetched.title, "Updated Longer Title")
        # Weighted: (3*1 + 5) / 2 = 4
        self.assertEqual(fetched.credibility_score, 4)
        self.assertEqual(fetched.survey_count, 2)

    def test_delete_paper(self):
        paper = _make_paper()
        pid = self.db.insert_paper(paper)
        self.assertTrue(self.db.delete_paper(pid))
        self.assertIsNone(self.db.get_paper(pid))
        self.assertFalse(self.db.delete_paper(pid))

    def test_fts_search(self):
        p1 = _make_paper(title="Attention Is All You Need", abstract="We propose transformer.")
        p2 = _make_paper(title="BERT Pretraining", abstract="Deep bidirectional transformers.")
        p3 = _make_paper(title="ImageNet Classification", abstract="Convolutional neural networks.")

        self.db.insert_paper(p1)
        self.db.insert_paper(p2)
        self.db.insert_paper(p3)

        # Small delay for FTS index to settle
        time.sleep(0.1)

        result = self.db.query(keywords=["transformer"])
        titles = {p.title for p in result.papers}
        self.assertIn("Attention Is All You Need", titles)
        self.assertIn("BERT Pretraining", titles)
        self.assertNotIn("ImageNet Classification", titles)

    def test_tag_filtering(self):
        paper = _make_paper(title="Vision Transformer Paper")
        pid = self.db.insert_paper(paper)

        self.db.insert_or_update_tag(DomainTag(tag_id="vision_transformer", name="Vision Transformer", level=3))
        self.db.tag_paper(pid, "vision_transformer", confidence="high")

        result = self.db.query(domain_tags=["vision_transformer"])
        self.assertEqual(len(result.papers), 1)
        self.assertEqual(result.papers[0].paper_id, pid)

    def test_year_range_filter(self):
        for yr in [2020, 2021, 2022, 2023, 2024]:
            self.db.insert_paper(_make_paper(title=f"Paper {yr}", year=yr))

        result = self.db.query(year_range=(2022, 2024))
        years = {p.year for p in result.papers}
        self.assertEqual(years, {2022, 2023, 2024})

    def test_venue_filter(self):
        self.db.insert_paper(_make_paper(title="A", venue="NeurIPS"))
        self.db.insert_paper(_make_paper(title="B", venue="ICML"))
        self.db.insert_paper(_make_paper(title="C", venue="ICLR"))

        result = self.db.query(venue_filter=["NeurIPS", "ICML"])
        venues = {p.venue for p in result.papers}
        self.assertEqual(venues, {"NeurIPS", "ICML"})

    def test_credibility_filter(self):
        self.db.insert_paper(_make_paper(title="Low", credibility_score=2))
        self.db.insert_paper(_make_paper(title="High", credibility_score=5))

        result = self.db.query(min_credibility=4)
        self.assertEqual(len(result.papers), 1)
        self.assertEqual(result.papers[0].title, "High")

    def test_find_similar_by_tag(self):
        p1 = _make_paper(title="Paper A")
        p2 = _make_paper(title="Paper B")
        p3 = _make_paper(title="Paper C")

        self.db.insert_paper(p1, auto_tag=False)
        self.db.insert_paper(p2, auto_tag=False)
        self.db.insert_paper(p3, auto_tag=False)

        self.db.insert_or_update_tag(DomainTag(tag_id="shared_tag", name="Shared", level=2))
        self.db.tag_paper(p1.paper_id, "shared_tag")
        self.db.tag_paper(p2.paper_id, "shared_tag")

        similar = self.db.find_similar(p1.paper_id, by="tag")
        self.assertEqual(len(similar), 1)
        self.assertEqual(similar[0].paper_id, p2.paper_id)

    def test_claim_crud(self):
        # Pre-insert referenced papers to satisfy FK constraints
        for pid in ["p1", "p2", "p3"]:
            self.db.insert_paper(_make_paper(paper_id=pid, title=f"Paper {pid}"), auto_tag=False)

        claim = Claim(
            claim_id="c_test",
            statement="Test claim",
            supporting_papers=["p1", "p2"],
            contradicting_papers=["p3"],
        )
        self.db.insert_or_update_claim(claim)

        fetched = self.db.get_claim("c_test")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.statement, "Test claim")
        self.assertEqual(set(fetched.supporting_papers), {"p1", "p2"})
        self.assertEqual(fetched.contradicting_papers, ["p3"])

    def test_survey_crud(self):
        survey = Survey(
            survey_id="s_001",
            project_name="test-project",
            topic="Test Topic",
            status="completed",
            papers_from_db=5,
            papers_from_web=10,
        )
        self.db.insert_survey(survey)

        fetched = self.db.get_survey("s_001")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.papers_from_db, 5)
        self.assertEqual(fetched.papers_from_web, 10)

    def test_analytics_tag_stats(self):
        self.db.insert_paper(_make_paper(title="P1", credibility_score=4))
        self.db.insert_paper(_make_paper(title="P2", credibility_score=5))

        self.db.insert_or_update_tag(DomainTag(tag_id="stat_tag", name="Stat Tag", level=2))
        for p in self.db.query().papers:
            self.db.tag_paper(p.paper_id, "stat_tag")

        stats = self.db.get_tag_statistics()
        stat = next((s for s in stats if s["tag_id"] == "stat_tag"), None)
        self.assertIsNotNone(stat)
        self.assertEqual(stat["paper_count"], 2)
        self.assertAlmostEqual(stat["avg_credibility"], 4.5)

    def test_top_papers(self):
        self.db.insert_paper(_make_paper(title="Top", credibility_score=5, survey_count=10))
        self.db.insert_paper(_make_paper(title="Bottom", credibility_score=1, survey_count=1))

        top = self.db.get_top_papers(limit=2)
        self.assertEqual(top[0].title, "Top")

    def test_count_papers(self):
        self.assertEqual(self.db.count_papers(), 0)
        self.db.insert_paper(_make_paper())
        self.assertEqual(self.db.count_papers(), 1)

    def test_auto_tagging_on_insert(self):
        paper = _make_paper(title="Vision Transformer for Image Classification")
        pid = self.db.insert_paper(paper, auto_tag=True)

        tags = self.db.get_paper_tags(pid)
        tag_ids = {t.tag_id for t in tags}
        self.assertIn("computer_vision", tag_ids)
        self.assertIn("vision_transformer", tag_ids)

    def test_query_result_metadata(self):
        self.db.insert_paper(_make_paper(title="Q1"))
        self.db.insert_paper(_make_paper(title="Q2"))

        result = self.db.query()
        self.assertEqual(result.total_count, 2)
        self.assertGreaterEqual(result.query_time_ms, 0)
        self.assertFalse(result.from_cache)

    def test_query_cache_populated(self):
        self.db.insert_paper(_make_paper(title="CacheTest", abstract="About transformers and attention."))
        time.sleep(0.1)

        result = self.db.query(keywords=["transformers"])
        self.assertFalse(result.from_cache)

        result2 = self.db.query(keywords=["transformers"])
        self.assertTrue(result2.from_cache)


# ---------------------------------------------------------------------------
# 7. Integration Tests — Importer
# ---------------------------------------------------------------------------

class TestImporter(TempDBMixin, unittest.TestCase):
    """Tests for project-level import/export."""

    def test_import_from_source_log(self):
        importer = ProjectImporter(self.db)

        source_log = {
            "sources": [
                {
                    "id": "smith2023example",
                    "title": "An Example Paper",
                    "authors": ["John Smith"],
                    "venue": "ICML",
                    "date": "2023-07",
                    "type": "academic",
                    "credibility": 4,
                    "verification": "confirmed",
                    "limitations_noted": ["limited scale"],
                }
            ],
            "gap_evidence_map": {},
        }

        log_path = os.path.join(self.tmpdir, "M1_source_log.yaml")
        with open(log_path, "w", encoding="utf-8") as f:
            import yaml
            yaml.dump(source_log, f, allow_unicode=True)

        summary = importer.import_from_source_log(log_path, "test-project", domain_tags=["deep_learning"])
        self.assertEqual(summary["imported"], 1)

        paper = self.db.get_paper("smith2023example")
        self.assertIsNotNone(paper)
        self.assertEqual(paper.venue, "ICML")

    def test_import_merge_existing(self):
        importer = ProjectImporter(self.db)

        # First import
        source_log = {
            "sources": [{"id": "dup", "title": "Original", "authors": ["A"], "venue": "X", "type": "academic"}],
            "gap_evidence_map": {},
        }
        log_path = os.path.join(self.tmpdir, "log1.yaml")
        with open(log_path, "w", encoding="utf-8") as f:
            import yaml
            yaml.dump(source_log, f, allow_unicode=True)
        importer.import_from_source_log(log_path, "proj-a")

        # Second import with same id
        source_log2 = {
            "sources": [{"id": "dup", "title": "Updated Longer", "authors": ["A"], "venue": "X", "type": "academic"}],
            "gap_evidence_map": {},
        }
        log_path2 = os.path.join(self.tmpdir, "log2.yaml")
        with open(log_path2, "w", encoding="utf-8") as f:
            import yaml
            yaml.dump(source_log2, f, allow_unicode=True)
        summary = importer.import_from_source_log(log_path2, "proj-b")

        self.assertEqual(summary["merged"], 1)
        paper = self.db.get_paper("dup")
        self.assertEqual(paper.title, "Updated Longer")
        self.assertEqual(paper.survey_count, 2)


# ---------------------------------------------------------------------------
# 8. Performance Tests
# ---------------------------------------------------------------------------

class TestPerformance(TempDBMixin, unittest.TestCase):
    """Tests for query performance with large datasets."""

    N_PAPERS = 1000

    def setUp(self) -> None:
        super().setUp()
        self._seed_large_db()

    def _seed_large_db(self) -> None:
        """Insert a large number of papers with varied metadata."""
        tags = ["transformer", "cnn", "nlp", "computer_vision", "time_series_forecasting"]
        venues = ["NeurIPS", "ICML", "ICLR", "CVPR", "ACL", "EMNLP"]

        self.db.insert_or_update_tag(DomainTag(tag_id="transformer", name="Transformer", level=3))
        self.db.insert_or_update_tag(DomainTag(tag_id="cnn", name="CNN", level=3))
        self.db.insert_or_update_tag(DomainTag(tag_id="nlp", name="NLP", level=2))
        self.db.insert_or_update_tag(DomainTag(tag_id="computer_vision", name="CV", level=2))
        self.db.insert_or_update_tag(DomainTag(tag_id="time_series_forecasting", name="TSF", level=3))

        batch_size = 100
        for batch_start in range(0, self.N_PAPERS, batch_size):
            with self.db.db.transaction() as conn:
                for i in range(batch_start, min(batch_start + batch_size, self.N_PAPERS)):
                    tag = tags[i % len(tags)]
                    venue = venues[i % len(venues)]
                    paper = _make_paper(
                        title=f"Large Scale Paper {i:04d} about {tag}",
                        authors=[f"Author{i}"],
                        year=2015 + (i % 10),
                        venue=venue,
                        credibility_score=1 + (i % 5),
                        citation_count=i * 10,
                        abstract=f"This paper explores {tag} methods in {venue}.",
                    )
                    # Bypass high-level insert to avoid per-paper overhead
                    paper.paper_id = PaperIdentifier.canonical_id(paper)
                    conn.execute(
                        """
                        INSERT INTO papers (paper_id, title, authors, venue, year, date, url, pdf_url, type,
                            identifiers, credibility_score, verification_status, code_availability, code_url,
                            abstract, problem_statement, method_summary, key_results, limitations_noted,
                            first_surveyed_at, last_updated_at, survey_count, citation_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            paper.paper_id,
                            paper.title,
                            json.dumps(paper.authors),
                            paper.venue,
                            paper.year,
                            paper.date,
                            paper.url,
                            paper.pdf_url,
                            paper.type,
                            json.dumps(paper.identifiers.to_dict()),
                            paper.credibility_score,
                            paper.verification_status,
                            paper.code_availability,
                            paper.code_url,
                            paper.abstract,
                            paper.problem_statement,
                            paper.method_summary,
                            json.dumps(paper.key_results),
                            serialize_limitations(paper.limitations_noted),
                            datetime.now().isoformat(),
                            datetime.now().isoformat(),
                            1,
                            paper.citation_count,
                        ),
                    )
                    # Tag every 3rd paper
                    if i % 3 == 0:
                        conn.execute(
                            "INSERT OR IGNORE INTO paper_tags (paper_id, tag_id) VALUES (?, ?)",
                            (paper.paper_id, tag),
                        )

    def test_query_performance_under_100ms(self):
        """Simple tag-filtered queries should complete in <100ms for 1000 papers."""
        start = time.perf_counter()
        result = self.db.query(domain_tags=["transformer"], limit=20)
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertLess(elapsed_ms, 100.0, f"Query took {elapsed_ms:.1f}ms, expected <100ms")
        self.assertGreater(len(result.papers), 0)

    def test_fts_query_performance(self):
        """FTS queries should complete in <200ms for 1000 papers."""
        time.sleep(0.2)  # Allow FTS index to settle
        start = time.perf_counter()
        result = self.db.query(keywords=["transformer"], limit=20)
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertLess(elapsed_ms, 200.0, f"FTS query took {elapsed_ms:.1f}ms, expected <200ms")

    def test_count_performance(self):
        start = time.perf_counter()
        count = self.db.count_papers()
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertEqual(count, self.N_PAPERS)
        self.assertLess(elapsed_ms, 10.0, f"Count took {elapsed_ms:.1f}ms")


# ---------------------------------------------------------------------------
# 9. Concurrency Tests
# ---------------------------------------------------------------------------

class TestConcurrency(TempDBMixin, unittest.TestCase):
    """Tests for multi-threaded access under WAL mode."""

    def test_concurrent_inserts(self):
        """Multiple threads inserting distinct papers concurrently."""
        errors: list[Exception] = []
        success_count = [0]

        def worker(thread_id: int) -> None:
            try:
                for i in range(10):
                    paper = _make_paper(
                        title=f"Thread {thread_id} Paper {i}",
                        authors=[f"Author-{thread_id}-{i}"],
                        year=2020 + thread_id,
                    )
                    self.db.insert_paper(paper)
                    success_count[0] += 1
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Concurrent inserts raised errors: {errors}")
        self.assertEqual(success_count[0], 50)
        self.assertEqual(self.db.count_papers(), 50)

    def test_concurrent_reads_during_writes(self):
        """Readers should not block writers under WAL mode."""
        barrier = threading.Barrier(4)
        results: list[int] = []

        def writer() -> None:
            tid = threading.current_thread().name
            barrier.wait()
            for i in range(20):
                paper = _make_paper(title=f"Write Paper {tid}-{i}", authors=[f"W{tid}-{i}"])
                self.db.insert_paper(paper)
                time.sleep(0.001)

        def reader() -> None:
            barrier.wait()
            for _ in range(20):
                count = self.db.count_papers()
                results.append(count)
                time.sleep(0.001)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should have succeeded (no deadlocks)
        self.assertEqual(len(results), 40)
        # Final count should be 40 (2 writers * 20 papers)
        self.assertEqual(self.db.count_papers(), 40)

    def test_thread_pool_executor_stress(self):
        """Stress test with ThreadPoolExecutor."""
        def task(i: int) -> str:
            paper = _make_paper(title=f"Stress {i}", authors=[f"S{i}"])
            return self.db.insert_paper(paper)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(task, i) for i in range(100)]
            pids = [f.result() for f in as_completed(futures)]

        self.assertEqual(len(set(pids)), 100)  # All distinct
        self.assertEqual(self.db.count_papers(), 100)


# ---------------------------------------------------------------------------
# 10. Edge Case & Robustness Tests
# ---------------------------------------------------------------------------

class TestEdgeCases(TempDBMixin, unittest.TestCase):
    """Edge cases and robustness checks."""

    def test_empty_query(self):
        result = self.db.query()
        self.assertEqual(result.papers, [])
        self.assertEqual(result.total_count, 0)

    def test_unicode_in_titles(self):
        paper = _make_paper(title="注意力机制 is All You Need 注意力")
        pid = self.db.insert_paper(paper)
        fetched = self.db.get_paper(pid)
        self.assertEqual(fetched.title, "注意力机制 is All You Need 注意力")

    def test_very_long_title(self):
        long_title = "A " + "very " * 1000 + "long title"
        paper = _make_paper(title=long_title)
        pid = self.db.insert_paper(paper)
        fetched = self.db.get_paper(pid)
        self.assertEqual(fetched.title, long_title)

    def test_many_authors(self):
        authors = [f"Author {i}" for i in range(100)]
        paper = _make_paper(authors=authors)
        pid = self.db.insert_paper(paper)
        fetched = self.db.get_paper(pid)
        self.assertEqual(len(fetched.authors), 100)

    def test_paper_with_all_fields(self):
        paper = Paper(
            paper_id="full_test",
            title="Complete Paper",
            authors=["A", "B"],
            venue="Nature",
            year=2024,
            date="2024-01",
            url="https://nature.com",
            pdf_url="https://nature.com/pdf",
            type="academic",
            identifiers=PaperIdentifiers(arxiv_id="2401.00001", doi="10.1038/s41586"),
            credibility_score=5,
            verification_status="confirmed",
            code_availability="open_source",
            code_url="https://github.com/test",
            abstract="Full abstract.",
            problem_statement="The problem.",
            method_summary="The method.",
            key_results=["Result 1", "Result 2"],
            limitations_noted=[LimitationEntry("Limit 1", "proj")],
            first_surveyed_at="2024-01-01T00:00:00",
            last_updated_at="2024-01-02T00:00:00",
            survey_count=3,
            citation_count=1000,
        )
        self.db.insert_paper(paper)
        fetched = self.db.get_paper("full_test")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.code_url, "https://github.com/test")
        self.assertEqual(fetched.key_results, ["Result 1", "Result 2"])
        self.assertEqual(len(fetched.limitations_noted), 1)

    def test_invalid_year_range(self):
        # Should not crash, just return nothing
        result = self.db.query(year_range=(3000, 4000))
        self.assertEqual(result.papers, [])

    def test_sql_injection_in_keywords(self):
        paper = _make_paper(title="Safe Paper")
        self.db.insert_paper(paper)
        time.sleep(0.1)

        # FTS5 handles this safely via parameterization
        result = self.db.query(keywords=["'; DROP TABLE papers; --"])
        # Should not crash and table should still exist
        self.assertTrue(self.db.db.verify_schema())

    def test_tag_nonexistent_paper(self):
        self.db.insert_or_update_tag(DomainTag(tag_id="orphan", name="Orphan", level=1))
        # Should not raise
        self.db.tag_paper("nonexistent", "orphan")
        # Foreign key constraint in SQLite prevents bad data, but ON CONFLICT may hide it
        # The tag association may or may not exist depending on FK enforcement

    def test_get_paper_tags_empty(self):
        paper = _make_paper()
        pid = self.db.insert_paper(paper, auto_tag=False)
        tags = self.db.get_paper_tags(pid)
        self.assertEqual(tags, [])

    def test_list_tags_empty(self):
        tags = self.db.list_tags()
        self.assertEqual(tags, [])

    def test_query_cache_invalidation(self):
        cache = QueryCache(self.db.db, ttl_days=1)
        cache.set(["q"], [{"paper_id": "p1"}])
        self.assertTrue(cache.invalidate(["q"]))
        self.assertIsNone(cache.get(["q"]))
        self.assertFalse(cache.invalidate(["q"]))

    def test_reset_database(self):
        self.db.insert_paper(_make_paper())
        self.assertEqual(self.db.count_papers(), 1)
        self.db.reset()
        self.assertEqual(self.db.count_papers(), 0)
        self.assertTrue(self.db.db.verify_schema())

    def test_multiple_external_identifiers(self):
        paper = Paper(
            paper_id="multi_id",
            title="Multi ID Paper",
            authors=["X"],
            year=2023,
            identifiers=PaperIdentifiers(
                arxiv_id="2301.00001",
                doi="10.1000/test",
                semantic_scholar_id="s2abc",
                dblp_id="dblp:123",
            ),
        )
        self.db.insert_paper(paper)

        # Check identifier lookup table
        rows = self.db.db.fetchall(
            "SELECT id_type, id_value FROM paper_identifiers WHERE paper_id = ?",
            ("multi_id",),
        )
        id_map = {row["id_type"]: row["id_value"] for row in rows}
        self.assertIn("arxiv", id_map)
        self.assertIn("doi", id_map)
        self.assertIn("s2", id_map)
        self.assertIn("dblp", id_map)

    def test_update_syncs_identifiers(self):
        p1 = Paper(
            paper_id="id_sync",
            title="Sync Test",
            authors=["Y"],
            year=2022,
            identifiers=PaperIdentifiers(arxiv_id="2201.00001"),
        )
        self.db.insert_paper(p1)

        p2 = Paper(
            paper_id="id_sync",
            title="Sync Test Updated",
            authors=["Y"],
            year=2022,
            identifiers=PaperIdentifiers(doi="10.1000/sync"),
        )
        self.db.update_paper(p2)

        rows = self.db.db.fetchall(
            "SELECT id_type FROM paper_identifiers WHERE paper_id = ?",
            ("id_sync",),
        )
        types = {row["id_type"] for row in rows}
        self.assertEqual(types, {"arxiv", "doi"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
