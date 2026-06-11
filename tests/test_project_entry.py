"""Tests for flexible project entry manifests."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.conductor_helper import get_input_docs
from spiral.project import ProjectManager, validate_project_name
from spiral.state import PipelineState
from utils.source_log_validator import validate


def _deep_fields(title: str) -> dict:
    return {
        "background": f"Background for {title}",
        "contributions": [f"Contribution of {title}"],
        "model": f"Model for {title}",
        "method": f"Method for {title}",
        "experiment_setup": "datasets, metrics, baselines, protocol, and seeds",
        "results": f"Results for {title}",
        "analysis": f"Analysis for {title}",
        "conclusion": f"Conclusion for {title}",
    }


def _ingestion_fields(source_id: str, title: str, rank: int = 1) -> dict:
    return {
        "discovery_records": [
            {
                "search_surface": "public_db",
                "query_text": f"{title} method experiment evidence",
                "result_rank": rank,
                "result_url": f"https://example.com/{source_id}",
                "screened_status": "retained",
                "retained_reason": "Covers project-entry source-log fixture",
            }
        ],
        "artifacts": [
            {
                "artifact_type": "pdf",
                "uri": f"https://example.com/{source_id}.pdf",
                "status": "available",
            }
        ],
        "parse_profile": {
            "metadata_status": "complete",
            "fulltext_status": "parsed",
            "parse_status": "complete",
            "parse_backend": "manual_card",
            "extraction_sources": ["pdf"],
            "section_summaries": {
                "abstract": f"Abstract for {title}",
                "method": f"Method for {title}",
                "experiment_setup": "datasets, metrics, baselines, protocol, and seeds",
                "results": f"Results for {title}",
                "analysis": f"Analysis for {title}",
            },
            "downstream_signals": {
                "M2": {"method_reference": True, "core_mechanism": f"Method for {title}"},
                "M3": {"experiment_protocol": True, "datasets_metrics_baselines": "datasets, metrics, baselines"},
                "M4": {"analysis_patterns": True, "analysis": f"Analysis for {title}"},
                "M5": {"citation_ready": True, "writing_context": f"Context for {title}"},
            },
            "confidence": "high",
        },
    }


def _search_provenance(source_ids: list[str]) -> dict:
    return {
        "databases": ["public_db", "Semantic Scholar", "arXiv", "internet web search"],
        "inclusion_criteria": ["anchor or relevant academic source", "contains method and experiment evidence"],
        "exclusion_criteria": ["off-topic", "no usable evidence"],
        "rounds": [
            {
                "round": 1,
                "goal": "breadth",
                "queries": ["anchor validation survey", "foundation reference baseline"],
                "retrieved_count": 30,
                "screened_count": 12,
                "retained_source_ids": source_ids[:2],
            },
            {
                "round": 2,
                "goal": "depth",
                "queries": ["targeted gap method", "experimental protocol"],
                "retrieved_count": 22,
                "screened_count": 10,
                "retained_source_ids": source_ids[2:4],
            },
            {
                "round": 3,
                "goal": "blindspot",
                "queries": ["recent negative result", "classic key author"],
                "retrieved_count": 18,
                "screened_count": 9,
                "retained_source_ids": source_ids[1:2] + source_ids[-1:],
            },
        ],
        "blindspot_checks": {
            "recent_work": "checked latest and recent 6 months 2026 work",
            "negative_results": "checked negative/opposing/contradictory results",
            "seminal_work": "checked seminal classic foundation work",
            "key_authors": "checked key author and team follow-up work",
            "source_log_consistency": "checked Source Log consistency",
        },
        "perspective_coverage": {
            "scenario_task": {
                "status": "covered",
                "queries": ["scenario task application gap"],
                "source_ids": source_ids[:2],
                "finding": "Scenario/task perspective identifies deployment and task-level gaps.",
            },
            "model_method": {
                "status": "covered",
                "queries": ["model method architecture limitation"],
                "source_ids": source_ids[1:3],
                "finding": "Model/method perspective identifies architecture and algorithm limitations.",
            },
            "metric_performance": {
                "status": "covered",
                "queries": ["metric accuracy performance efficiency"],
                "source_ids": source_ids[2:4],
                "finding": "Metric/performance perspective identifies accuracy and efficiency gaps.",
            },
            "dataset_protocol": {
                "status": "covered",
                "queries": ["dataset benchmark experiment protocol"],
                "source_ids": source_ids[3:5] or source_ids[-2:],
                "finding": "Dataset/protocol perspective identifies benchmark and experiment setup gaps.",
            },
            "failure_limitation": {
                "status": "covered",
                "queries": ["failure negative limitation defect"],
                "source_ids": source_ids[1:2] + source_ids[-1:],
                "finding": "Failure/limitation perspective identifies negative results and defects.",
            },
            "baseline_comparison": {
                "status": "covered",
                "queries": ["baseline comparison sota comparator"],
                "source_ids": source_ids[:1] + source_ids[-1:],
                "finding": "Baseline/comparison perspective identifies comparator and SOTA gaps.",
            },
        },
    }


class TestProjectEntryManifest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_path)

    def test_project_display_name_must_match_folder_base_rules(self) -> None:
        valid_names = ["Entry-Test", "Entry.Test_01", "A1"]
        for name in valid_names:
            with self.subTest(name=name):
                self.assertEqual(validate_project_name(name), name)

        invalid_names = [
            "Bad Name",
            "Bad/Name",
            "-BadName",
            "BadName_",
            "CON",
            "Project中文",
            "a" * 81,
        ]
        for name in invalid_names:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    validate_project_name(name)

    def test_create_rejects_invalid_project_display_name(self) -> None:
        projects_root = self.tmp_path / "invalid-root"
        with self.assertRaises(ValueError):
            ProjectManager.create(
                topic="Invalid project name",
                display_name="Invalid Name",
                projects_root=projects_root,
            )
        self.assertFalse(projects_root.exists())

    def test_create_uses_valid_project_name_as_timestamped_folder_base(self) -> None:
        proj = ProjectManager.create(
            topic="Strict Project Name",
            display_name="Strict.Project_01",
            projects_root=self.tmp_path,
        )

        self.assertRegex(proj.name, r"^Strict\.Project_01-\d{8}-\d{6}$")

    def test_create_writes_research_brief_with_anchors(self) -> None:
        proj = ProjectManager.create(
            topic="Adaptive Time Series Forecasting",
            display_name="Entry-Test",
            projects_root=self.tmp_path,
            keywords=["time series forecasting, adaptive calibration"],
            reference_papers=["A Close Reference Paper"],
            foundation_papers=["https://arxiv.org/abs/1234.56789"],
        )

        brief_path = proj / "state" / "research_brief.yaml"
        self.assertTrue(brief_path.exists())

        brief = yaml.safe_load(brief_path.read_text(encoding="utf-8"))
        self.assertEqual(brief["project"]["anchor_count"], 2)
        self.assertEqual(brief["project"]["paper_anchor_count"], 2)
        self.assertIn("time series forecasting", brief["keywords"])
        self.assertIn("adaptive calibration", brief["keywords"])

        roles = {anchor["canonical_value"]: anchor["role"] for anchor in brief["anchors"]}
        self.assertEqual(roles["A Close Reference Paper"], "reference")
        self.assertEqual(roles["https://arxiv.org/abs/1234.56789"], "foundation")

        state = PipelineState(proj)
        self.assertEqual(state.data["project"]["entry_brief"], "state/research_brief.yaml")
        self.assertEqual(state.data["project"]["anchor_count"], 2)

    def test_stage_inputs_include_research_brief(self) -> None:
        proj = ProjectManager.create(
            topic="Entry Brief Stage Input",
            display_name="Entry-Stage",
            projects_root=self.tmp_path,
            reference_papers=["Reference Paper"],
        )

        inputs = get_input_docs(proj, "M1S01")
        self.assertIn(proj / "state" / "research_brief.yaml", inputs)

    def test_source_log_validator_accepts_entry_anchor_match(self) -> None:
        proj = ProjectManager.create(
            topic="Anchor Validation",
            display_name="Anchor-Validation",
            projects_root=self.tmp_path,
            foundation_papers=["Foundation Paper"],
            reference_papers=["Reference Paper"],
        )

        source_log = proj / "knowledge" / "M1" / "M1_source_log.yaml"
        sources = [
            {
                "id": "anchor_source_1",
                "title": "Foundation Paper",
                "authors": ["A. Author"],
                "venue": "Test Venue",
                "date": "2024-01",
                "url": "https://example.com/foundation",
                "type": "academic",
                "credibility": 5,
                "verification": "confirmed",
                "key_claims": ["claim_1"],
                "limitations_noted": ["limitation_1"],
                "code_availability": "open_source",
                "relevance_to_our_gap": "gap_1",
                "entry_anchor_id": "anchor_01",
                "entry_anchor_role": "foundation",
                **_deep_fields("Foundation Paper"),
            },
            {
                "id": "anchor_source_2",
                "title": "Reference Paper",
                "authors": ["B. Author"],
                "venue": "Test Venue",
                "date": "2024-02",
                "url": "https://example.com/reference",
                "type": "academic",
                "credibility": 4,
                "verification": "confirmed",
                "key_claims": ["claim_2"],
                "limitations_noted": ["limitation_2"],
                "code_availability": "closed",
                "relevance_to_our_gap": "gap_1",
                **_deep_fields("Reference Paper"),
            },
            {
                "id": "anchor_source_3",
                "title": "Extra Paper 3",
                "authors": ["C. Author"],
                "venue": "Test Venue",
                "date": "2024-03",
                "url": "https://example.com/3",
                "type": "academic",
                "credibility": 4,
                "verification": "confirmed",
                "key_claims": ["claim_3"],
                "limitations_noted": ["limitation_3"],
                "code_availability": "closed",
                "relevance_to_our_gap": "gap_1",
                **_deep_fields("Extra Paper 3"),
            },
            {
                "id": "anchor_source_4",
                "title": "Extra Paper 4",
                "authors": ["D. Author"],
                "venue": "Test Venue",
                "date": "2024-04",
                "url": "https://example.com/4",
                "type": "academic",
                "credibility": 3,
                "verification": "confirmed",
                "key_claims": ["claim_4"],
                "limitations_noted": ["limitation_4"],
                "code_availability": "closed",
                "relevance_to_our_gap": "gap_1",
                **_deep_fields("Extra Paper 4"),
            },
            {
                "id": "anchor_source_5",
                "title": "Extra Paper 5",
                "authors": ["E. Author"],
                "venue": "Test Venue",
                "date": "2024-05",
                "url": "https://example.com/5",
                "type": "academic",
                "credibility": 3,
                "verification": "confirmed",
                "key_claims": ["claim_5"],
                "limitations_noted": ["limitation_5"],
                "code_availability": "closed",
                "relevance_to_our_gap": "gap_1",
                **_deep_fields("Extra Paper 5"),
            },
        ]
        for rank, src in enumerate(sources, start=1):
            src.update(_ingestion_fields(src["id"], src["title"], rank))
        gap_evidence_map = {
            "gap_1": {
                "supporting_sources": ["anchor_source_1", "anchor_source_2"],
                "contradicting_sources": [],
                "confidence": "high",
                "gap_type": "vacancy",
                "level": "large",
                "description": "Large direction scenario-level gap.",
            },
            "gap_2": {
                "supporting_sources": ["anchor_source_3", "anchor_source_4"],
                "contradicting_sources": [],
                "confidence": "medium",
                "gap_type": "enhancement",
                "level": "middle",
                "description": "Middle direction model/metric gap.",
            },
            "gap_3": {
                "supporting_sources": ["anchor_source_2", "anchor_source_5"],
                "contradicting_sources": [],
                "confidence": "medium",
                "gap_type": "validation",
                "level": "small",
                "description": "Small direction component-level gap.",
            }
        }
        source_log.write_text(
            yaml.safe_dump(
                {
                    "sources": sources,
                    "gap_evidence_map": gap_evidence_map,
                    "search_provenance": _search_provenance([src["id"] for src in sources]),
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        ok, messages = validate(proj, "M1")
        self.assertTrue(ok, messages)
        self.assertTrue(any("Entry paper anchor covered" in msg for msg in messages))


if __name__ == "__main__":
    unittest.main()
