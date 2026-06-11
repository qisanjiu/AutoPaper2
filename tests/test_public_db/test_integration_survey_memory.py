"""Integration tests for SurveyMemory ↔ PublicLiteratureDB bridge.

Validates that the SurveyMemoryManager can seed from and export to
the public literature database.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from spiral.public_db.config import DBConfig
from spiral.public_db.manager import PublicLiteratureDB
from spiral.survey_memory import SurveyMemoryManager, Source


class TestSurveyMemoryIntegration(unittest.TestCase):
    """End-to-end tests for survey memory + public DB integration."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="pldb_sm_test_")
        self.project_root = Path(self.tmpdir) / "test-project-20260101-120000"
        self.project_root.mkdir(parents=True, exist_ok=True)

        db_path = os.path.join(self.tmpdir, "lit.db")
        self.public_db = PublicLiteratureDB(DBConfig(db_path=db_path, enabled=True))
        self.public_db.init()

    def tearDown(self) -> None:
        self.public_db.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _close_sm(self, sm) -> None:
        """Close any auto-connected public_db inside a SurveyMemoryManager."""
        if getattr(sm, "public_db", None) is not None and sm.public_db is not self.public_db:
            try:
                sm.public_db.close()
            except Exception:
                pass

    def test_public_db_disabled_by_default(self):
        """SurveyMemory without public_db should work normally."""
        sm = SurveyMemoryManager(self.project_root, auto_connect=False)
        memory = sm.init("Test Topic")
        self.assertEqual(memory.topic, "Test Topic")

    def test_close_does_not_close_injected_public_db(self):
        """Managers should not close externally owned public DB handles."""
        sm = SurveyMemoryManager(
            self.project_root,
            public_db=self.public_db,
            project_name="test-project",
        )

        sm.close()

        from tests.test_public_db.test_core import _make_paper
        pid = self.public_db.insert_paper(_make_paper(title="Still Open"), auto_tag=False)
        self.assertTrue(pid)

    def test_search_with_public_db_returns_results(self):
        """Pre-seeded public DB should return matching sources."""
        # Seed public DB
        from tests.test_public_db.test_core import _make_paper
        for i in range(5):
            paper = _make_paper(
                title=f"Transformer Paper {i}",
                authors=[f"Author {i}"],
                year=2023,
            )
            self.public_db.insert_paper(paper, auto_tag=True)

        sm = SurveyMemoryManager(
            self.project_root,
            public_db=self.public_db,
            project_name="test-project",
            min_hit_threshold=3,
        )

        db_sources, web_sources = sm.search_with_public_db(
            queries=["transformer"],
        )
        self.assertEqual(len(db_sources), 5)
        self.assertEqual(len(web_sources), 0)
        self._close_sm(sm)

    def test_import_sources_to_public_db(self):
        """Project sources should be exportable to public DB."""
        sm = SurveyMemoryManager(
            self.project_root,
            public_db=self.public_db,
            project_name="test-project",
        )
        memory = sm.init("Test Topic")

        src = Source(
            id="smith2023test",
            title="Test Source",
            authors=["John Smith"],
            venue="ICML",
            date="2023-07",
            credibility_score=4,
            limitations_noted=["small dataset"],
            artifacts=[
                {
                    "artifact_id": "manual-artifact",
                    "artifact_type": "pdf",
                    "uri": "https://example.org/test.pdf",
                    "status": "failed",
                    "failure_reason": "download blocked",
                    "recovery_actions": ["use abstract"],
                }
            ],
            parse_profile={
                "metadata_status": "complete",
                "fulltext_status": "metadata_only",
                "parse_status": "partial",
                "parse_backend": "abstract_only",
                "extraction_sources": ["abstract"],
                "missing_fields": ["experiment_setup"],
                "section_summaries": {"method": "test method"},
                "downstream_signals": {"M2": {}, "M3": {}, "M4": {}, "M5": {}},
            },
        )
        memory.add_source(src)
        sm.save(memory)

        result = sm.import_sources_to_public_db(list(memory.source_registry.values()))
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["merged"], 0)
        self.assertEqual(result["artifacts"], 1)
        self.assertEqual(result["extractions"], 1)

        paper = self.public_db.get_paper("smith2023test")
        self.assertIsNotNone(paper)
        self.assertEqual(paper.credibility_score, 4)
        self.assertEqual(self.public_db.list_artifacts("smith2023test")[0].status, "failed")
        self.assertEqual(self.public_db.get_extraction("smith2023test").parse_status, "partial")

    def test_import_merge_existing(self):
        """Re-importing same source should merge instead of duplicate."""
        sm = SurveyMemoryManager(
            self.project_root,
            public_db=self.public_db,
            project_name="test-project",
        )

        src1 = Source(id="dup", title="Original", authors=["A"])
        sm.import_sources_to_public_db([src1])

        src2 = Source(id="dup", title="Updated Longer Title", authors=["A"], credibility_score=5)
        result = sm.import_sources_to_public_db([src2])

        self.assertEqual(result["merged"], 1)
        paper = self.public_db.get_paper("dup")
        self.assertEqual(paper.title, "Updated Longer Title")
        self.assertEqual(paper.survey_count, 2)

    def test_source_to_paper_roundtrip(self):
        """Source → Paper → Source conversion should preserve core fields."""
        src = Source(
            id="roundtrip",
            title="Roundtrip Test",
            authors=["Alice", "Bob"],
            venue="NeurIPS",
            date="2024-12",
            url="https://example.com",
            type="academic",
            credibility_score=5,
            verification_status="confirmed",
            code_availability="open_source",
            limitations_noted=["slow", "expensive"],
        )

        paper = SurveyMemoryManager._source_to_paper(src)
        self.assertEqual(paper.paper_id, "roundtrip")
        self.assertEqual(paper.title, "Roundtrip Test")
        self.assertEqual(paper.credibility_score, 5)
        self.assertEqual(len(paper.limitations_noted), 2)
        self.assertEqual(paper.limitations_noted[0].limitation, "slow")

    def test_paper_to_source_roundtrip(self):
        """Paper → Source conversion should preserve core fields."""
        from spiral.public_db.models import LimitationEntry, Paper, PaperIdentifiers

        paper = Paper(
            paper_id="rt",
            title="Test",
            authors=["A"],
            venue="X",
            date="2024-01",
            url="https://x.com",
            type="academic",
            identifiers=PaperIdentifiers(),
            credibility_score=4,
            verification_status="partial",
            code_availability="open_source",
            code_url="https://github.com/x",
            limitations_noted=[
                LimitationEntry("memory", "proj-a"),
                LimitationEntry("speed", "proj-b"),
            ],
        )

        src = SurveyMemoryManager._paper_to_source(paper)
        self.assertEqual(src.id, "rt")
        self.assertEqual(src.credibility_score, 4)
        self.assertEqual(src.code_availability, "open_source")
        self.assertEqual(src.limitations_noted, ["memory", "speed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
