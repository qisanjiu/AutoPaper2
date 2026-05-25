#!/usr/bin/env python3
"""End-to-end tests for M1 module (Domain Survey) flow.

Tests:
1. Project creation initializes survey_memory.yaml correctly
2. M1S02 advance blocked when Round 3 missing
3. M1S02 advance blocked when Round 3 not passed
4. M1S02 advance succeeds when Round 3 passed
5. Backtrack from M1S05 to M1S02 marks downstream stale
6. _sync_source_log_to_survey_memory imports sources and gaps correctly
7. Gate G1: advancing M1S05 marks M1 completed; M2 blocked without M1 completed
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
import uuid
import yaml
from pathlib import Path
from unittest.mock import patch

# Add project root to path
_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from spiral.project import ProjectManager
from spiral.state import PipelineState
from spiral.conductor import Conductor
from spiral.survey_memory import (
    SurveyMemoryManager,
    SurveyMemory,
    SearchBatch,
    Source,
    Gap,
    GapType,
    SurveyStatus,
)
from scripts.state_manager import (
    cmd_advance,
    _sync_source_log_to_survey_memory,
    cmd_run_module,
)
from utils.gate_rubric import get_gate_rubric
from utils.stage_gate import check_stage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MIN_SOURCES = 5


def _create_diverse_sources(count: int = MIN_SOURCES) -> list[dict]:
    """Create source log entries with diverse first authors."""
    authors = [
        "Alice Smith",
        "Bob Jones",
        "Charlie Brown",
        "Diana Prince",
        "Eve Davis",
        "Frank Miller",
        "Grace Hopper",
    ]
    return [
        {
            "id": f"s{i+1}",
            "title": f"Paper {i+1}",
            "type": "academic",
            "credibility": 4,
            "authors": [authors[i % len(authors)]],
            "venue": "Test Venue",
            "date": "2024",
            "background": f"Background for Paper {i+1}",
            "contributions": [f"Contribution for Paper {i+1}"],
            "model": f"Model for Paper {i+1}",
            "method": f"Method for Paper {i+1}",
            "experiment_setup": "datasets, metrics, baselines, protocol, and seeds",
            "results": f"Results for Paper {i+1}",
            "analysis": f"Analysis for Paper {i+1}",
            "conclusion": f"Conclusion for Paper {i+1}",
        }
        for i in range(count)
    ]


def _create_gap_evidence_map() -> dict[str, dict]:
    return {
        "gap_1": {
            "supporting_sources": ["s1", "s2"],
            "gap_type": "vacancy",
            "level": "large",
            "confidence": "medium",
            "description": "Large direction scenario-level coverage gap.",
        },
        "gap_2": {
            "supporting_sources": ["s3", "s4"],
            "gap_type": "enhancement",
            "level": "middle",
            "confidence": "high",
            "description": "Middle direction model/metric bottleneck.",
        },
        "gap_3": {
            "supporting_sources": ["s2", "s5"],
            "gap_type": "validation",
            "level": "small",
            "confidence": "high",
            "description": "Small direction component-level limitation.",
        },
    }


def _create_search_provenance(source_ids: list[str] | None = None) -> dict:
    ids = source_ids or ["s1", "s2", "s3", "s4", "s5"]
    return {
        "databases": ["public_db", "Semantic Scholar", "arXiv", "internet web search"],
        "inclusion_criteria": ["academic or authoritative", "contains method and experiment evidence"],
        "exclusion_criteria": ["off-topic", "no usable evidence"],
        "rounds": [
            {
                "round": 1,
                "goal": "breadth",
                "queries": ["topic survey baseline", "dataset metric benchmark"],
                "retrieved_count": 40,
                "screened_count": 18,
                "retained_source_ids": ids[:2],
            },
            {
                "round": 2,
                "goal": "depth",
                "queries": ["target gap method", "limitation analysis"],
                "retrieved_count": 25,
                "screened_count": 12,
                "retained_source_ids": ids[2:4],
            },
            {
                "round": 3,
                "goal": "blindspot",
                "queries": ["recent negative result", "classic key author"],
                "retrieved_count": 18,
                "screened_count": 10,
                "retained_source_ids": ids[1:2] + ids[-1:],
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
                "source_ids": ids[:2],
                "finding": "Scenario/task perspective identifies deployment and task-level gaps.",
            },
            "model_method": {
                "status": "covered",
                "queries": ["model method architecture limitation"],
                "source_ids": ids[1:3],
                "finding": "Model/method perspective identifies architecture and algorithm limitations.",
            },
            "metric_performance": {
                "status": "covered",
                "queries": ["metric accuracy performance efficiency"],
                "source_ids": ids[2:4],
                "finding": "Metric/performance perspective identifies accuracy and efficiency gaps.",
            },
            "dataset_protocol": {
                "status": "covered",
                "queries": ["dataset benchmark experiment protocol"],
                "source_ids": ids[3:5] or ids[-2:],
                "finding": "Dataset/protocol perspective identifies benchmark and experiment setup gaps.",
            },
            "failure_limitation": {
                "status": "covered",
                "queries": ["failure negative limitation defect"],
                "source_ids": ids[1:2] + ids[-1:],
                "finding": "Failure/limitation perspective identifies negative results and defects.",
            },
            "baseline_comparison": {
                "status": "covered",
                "queries": ["baseline comparison sota comparator"],
                "source_ids": ids[:1] + ids[-1:],
                "finding": "Baseline/comparison perspective identifies comparator and SOTA gaps.",
            },
        },
    }


def _write_source_log(proj_dir: Path, sources: list[dict], gaps: dict[str, dict]) -> None:
    log_path = proj_dir / "knowledge" / "M1" / "M1_source_log.yaml"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "sources": sources,
                "gap_evidence_map": gaps,
                "search_provenance": _create_search_provenance([s["id"] for s in sources]),
            },
            f,
        )


def _write_survey_memory(
    proj_dir: Path,
    batches: list[dict],
    topic: str = "Test Topic",
) -> None:
    mem = SurveyMemory(topic=topic)
    for b in batches:
        batch = SearchBatch(
            batch_id=b["batch_id"],
            round=b["round"],
            status=b["status"],
            queries=b.get("queries", []),
            sources_found=b.get("sources_found", 5 if b["status"] == "passed" else 0),
        )
        mem.search_batches.append(batch)
        # Add round review entry matching batch status
        from spiral.survey_memory import RoundReview
        mem.add_round_review(RoundReview(
            round=b["round"],
            verdict="PASS" if b["status"] == "passed" else "REWORK",
            score=0.8,
        ))
    mgr = SurveyMemoryManager(proj_dir, auto_connect=False)
    mgr.save(mem)


def _write_m1s02_doc(proj_dir: Path) -> None:
    doc = proj_dir / "knowledge" / "M1" / "M1S02_literature_deepdive.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        "# Literature Deep Dive\n\n"
        "### Round 1\nSome content\n\n"
        "### Round 2\nSome content\n\n"
        "### Round 3\nSome content\n\n"
        "## 检索策略 search strategy\n"
        "数据库 public_db and internet web search; screening inclusion/exclusion criteria recorded.\n\n"
        "## Perspective Coverage\n"
        "Perspective coverage covers scenario/task, model/method, metric/performance, "
        "dataset/protocol, failure/limitation, and baseline/comparison views.\n\n"
        "## Detailed Research Report\n"
        "研究空白 Research Gaps are organized into 大方向 large direction scenario gap, "
        "中方向 middle direction model/metric gap, and 小方向 small direction component gap.\n\n"
        "### Gap 论证\n"
        "证据链 evidence chain uses supporting sources from the Source Log for gap_1, gap_2, and gap_3.\n",
        encoding="utf-8",
    )


def _write_m1s03_doc(proj_dir: Path) -> None:
    doc = proj_dir / "knowledge" / "M1" / "M1S03_research_question.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# Research Question\n\n", encoding="utf-8")


def _write_m1s04_doc(proj_dir: Path) -> None:
    doc = proj_dir / "knowledge" / "M1" / "M1S04_hypothesis_generation.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# Hypothesis Generation\n\n", encoding="utf-8")


def _write_m1s05_doc(proj_dir: Path) -> None:
    doc = proj_dir / "knowledge" / "M1" / "M1S05_novelty_feasibility.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        "# Novelty & Feasibility\n\n"
        "## 3. 文献对比\n\n"
        "## 4. 可行性评估\n\n",
        encoding="utf-8",
    )


def _write_gate_review(proj_dir: Path, gate_id: str = "G1") -> None:
    review = proj_dir / "knowledge" / "reviews" / f"{gate_id}_aggregate.md"
    review.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {gate_id} Aggregate Review",
        "",
        "Verdict: PASS",
        "",
        "## Rubric Results",
        "",
        "| Rubric ID | Verdict | Score | Evidence paths | Notes |",
        "|---|---|---|---|---|",
    ]
    for item in get_gate_rubric(gate_id).get("items", []):
        evidence = next(
            (rel for rel in item.get("evidence_examples", []) if (proj_dir / rel).exists()),
            item.get("evidence_examples", ["knowledge/reviews"])[0],
        )
        lines.append(f"| {item.get('id', '')} | PASS | 2/2 | {evidence} | test evidence |")
    review.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _set_current_stage(proj_dir: Path, stage: str, status: str = "in_progress") -> None:
    state = PipelineState(proj_dir)
    state.set_stage(stage, status)


def _call_advance(
    project_dir: str,
    stage: str,
    agent: str,
    output_file: str,
    force: bool = False,
    skip_gates: bool = False,
) -> tuple[int | None, str]:
    """Call cmd_advance and capture exit code + stdout."""
    stdout_capture = io.StringIO()
    exit_code = None
    try:
        with patch("sys.stdout", new=stdout_capture):
            cmd_advance(project_dir, stage, agent, output_file, force=force, skip_gates=skip_gates)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
    return exit_code, stdout_capture.getvalue()


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

class TestProjectCreation(unittest.TestCase):
    """Test 1: ProjectManager.create() initializes survey_memory.yaml."""

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_path)

    def test_survey_memory_init(self) -> None:
        proj = ProjectManager.create(
            topic="E2E Test Topic",
            display_name="E2E-Test",
            projects_root=self.tmp_path,
        )
        survey_path = proj / "state" / "survey_memory.yaml"
        assert survey_path.exists(), "survey_memory.yaml should exist after project creation"

        mgr = SurveyMemoryManager(proj, auto_connect=False)
        mem = mgr.load()
        assert mem.topic == "E2E Test Topic", f"Expected topic 'E2E Test Topic', got '{mem.topic}'"
        assert str(mem.status.value) == "planning", f"Expected status 'planning', got '{mem.status}'"
        print("  [PASS] Project creation initializes SurveyMemory correctly")


class TestM1S02Advance3Round(unittest.TestCase):
    """Test 2-4: M1S02 advance behavior with 3-Round survey memory checks."""

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_path)

    def _setup_project_for_m1s02(
        self, batches: list[dict], current_stage: str = "M1S02"
    ) -> Path:
        proj = self.tmp_path / f"test_proj_{uuid.uuid4().hex[:8]}"
        proj.mkdir(parents=True)

        # Initialize state manually
        (proj / "state").mkdir(parents=True, exist_ok=True)
        (proj / "knowledge" / "reviews").mkdir(parents=True, exist_ok=True)
        state = PipelineState(proj)
        state.data["project"] = {
            "name": proj.name,
            "topic": "Test",
            "display_name": "Test",
            "created_at": "2024-01-01T00:00:00",
            "venue": {"id": "arxiv", "name": "arXiv"},
        }
        state.set_stage(current_stage, "in_progress")

        # Write source log
        sources = _create_diverse_sources()
        gaps = _create_gap_evidence_map()
        _write_source_log(proj, sources, gaps)

        # Write survey memory
        _write_survey_memory(proj, batches)

        # Create round review files
        round_nums_present = {b["round"] for b in batches}
        for rn in (1, 2, 3):
            review_file = proj / "knowledge" / "reviews" / f"M1S02_round{rn}_review.md"
            if rn in round_nums_present:
                batch_statuses = [b["status"] for b in batches if b["round"] == rn]
                verdict = "PASS" if any(s == "passed" for s in batch_statuses) else "REWORK"
            else:
                verdict = "REWORK"
            review_file.write_text(f"# Round {rn} Review\n\nVerdict: {verdict}\n", encoding="utf-8")

        # Write M1S02 doc
        _write_m1s02_doc(proj)

        return proj

    def _advance_m1s02(self, proj: Path, force: bool = False, skip_gates: bool = False) -> tuple[int | None, str]:
        output_file = str(proj / "knowledge" / "M1" / "M1S02_literature_deepdive.md")
        return _call_advance(str(proj), "M1S02", "survey", output_file, force=force, skip_gates=skip_gates)

    def test_blocked_when_round3_missing(self) -> None:
        proj = self._setup_project_for_m1s02([
            {"batch_id": 1, "round": 1, "status": "passed", "queries": ["q1"]},
            {"batch_id": 2, "round": 2, "status": "passed", "queries": ["q2"]},
        ])
        exit_code, output = self._advance_m1s02(proj)
        assert exit_code == 1, f"Expected exit code 1, got {exit_code}. Output: {output}"
        assert "round 3 batch not found" in output.lower() or "round 3" in output.lower(), (
            f"Expected Round 3 blocking message, got: {output}"
        )
        print("  [PASS] M1S02 advance blocked when Round 3 missing")

    def test_blocked_when_round3_not_passed(self) -> None:
        proj = self._setup_project_for_m1s02([
            {"batch_id": 1, "round": 1, "status": "passed", "queries": ["q1"]},
            {"batch_id": 2, "round": 2, "status": "passed", "queries": ["q2"]},
            {"batch_id": 3, "round": 3, "status": "awaiting_review", "queries": ["q3"]},
        ])
        exit_code, output = self._advance_m1s02(proj)
        assert exit_code == 1, f"Expected exit code 1, got {exit_code}. Output: {output}"
        assert "not pass" in output.lower() or "not 'passed'" in output or "not passed" in output, (
            f"Expected Round 3 not-passed message, got: {output}"
        )
        print("  [PASS] M1S02 advance blocked when Round 3 not passed")

    def test_ok_when_round3_passed(self) -> None:
        proj = self._setup_project_for_m1s02([
            {"batch_id": 1, "round": 1, "status": "passed", "queries": ["q1"]},
            {"batch_id": 2, "round": 2, "status": "passed", "queries": ["q2"]},
            {"batch_id": 3, "round": 3, "status": "passed", "queries": ["q3"]},
        ])
        exit_code, output = self._advance_m1s02(proj)
        assert exit_code is None, f"Expected success (no exit), got exit code {exit_code}. Output: {output}"
        assert "ADVANCED" in output, f"Expected ADVANCE message, got: {output}"

        # Verify state advanced to M1S03
        state = PipelineState(proj)
        assert state.get_current_stage() == "M1S03", (
            f"Expected current stage M1S03, got {state.get_current_stage()}"
        )
        print("  [PASS] M1S02 advance succeeds when Round 3 passed")


class TestBacktrackStaleStages(unittest.TestCase):
    """Test 5: Backtrack from M1S05 to M1S02 marks M1S03-M1S05 stale."""

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_path)

    def test_backtrack_marks_downstream_stale(self) -> None:
        proj = self.tmp_path / f"test_proj_{uuid.uuid4().hex[:8]}"
        proj.mkdir(parents=True)
        (proj / "state").mkdir(parents=True, exist_ok=True)

        # Set up state: at M1S05, M1 completed
        state = PipelineState(proj)
        state.data["project"] = {
            "name": proj.name,
            "topic": "Test",
            "display_name": "Test",
            "created_at": "2024-01-01T00:00:00",
            "venue": {"id": "arxiv", "name": "arXiv"},
        }
        state.set_stage("M1S05", "in_progress")
        state.set_module_status("M1", "completed", "M1S05")

        # Create required docs for later validation
        _write_m1s02_doc(proj)
        _write_m1s03_doc(proj)
        _write_m1s04_doc(proj)
        _write_m1s05_doc(proj)

        conductor = Conductor(proj)
        result = conductor.backtrack("M1S05", "M1S02", "Need more literature")

        assert result["ok"] is True, f"Backtrack failed: {result}"
        stale = result.get("stale_stages", [])
        assert "M1S03" in stale, f"M1S03 should be stale. Got: {stale}"
        assert "M1S04" in stale, f"M1S04 should be stale. Got: {stale}"
        assert "M1S05" in stale, f"M1S05 should be stale. Got: {stale}"

        # Verify module M1 reopened (reload from disk)
        state_after = PipelineState(proj)
        mod_status = state_after.get_module_status("M1")
        assert mod_status.get("status") == "reopened", (
            f"M1 should be reopened after backtrack, got: {mod_status}"
        )
        print("  [PASS] Backtrack M1S05→M1S02 marks M1S03-M1S05 stale and reopens M1")


class TestSyncSourceLogToSurveyMemory(unittest.TestCase):
    """Test 6: _sync_source_log_to_survey_memory imports sources and gaps."""

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_path)

    def test_sync_imports_sources_and_gaps(self) -> None:
        proj = self.tmp_path / f"test_proj_{uuid.uuid4().hex[:8]}"
        proj.mkdir(parents=True)
        (proj / "knowledge" / "M1").mkdir(parents=True)
        (proj / "state").mkdir(parents=True)

        sources = _create_diverse_sources(5)
        gaps = _create_gap_evidence_map()
        _write_source_log(proj, sources, gaps)

        # Initialize empty survey memory
        mgr = SurveyMemoryManager(proj, auto_connect=False)
        mgr.init(topic="Test Sync")

        # Sync
        _sync_source_log_to_survey_memory(str(proj))

        # Verify (use fresh manager to avoid stale cache)
        mgr2 = SurveyMemoryManager(proj, auto_connect=False)
        loaded = mgr2.load()
        assert len(loaded.source_registry) == 5, (
            f"Expected 5 sources in survey memory, got {len(loaded.source_registry)}"
        )
        for s in sources:
            assert s["id"] in loaded.source_registry, (
                f"Source {s['id']} not found in survey memory"
            )

        mem_gaps = loaded.findings.get("gaps", [])
        gap_ids = {g["id"] for g in mem_gaps}
        assert "gap_1" in gap_ids, "gap_1 not found in survey memory gaps"
        assert "gap_2" in gap_ids, "gap_2 not found in survey memory gaps"

        # Verify status set to completed
        assert str(loaded.status.value) == "completed", f"Expected status 'completed', got {loaded.status}"
        print("  [PASS] _sync_source_log_to_survey_memory imports sources and gaps correctly")


class TestGateG1Prerequisite(unittest.TestCase):
    """Test 7: Gate G1 — M1S05 advance marks M1 completed; M2 requires M1 completed."""

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_path)

    def _setup_project_at_m1s05(self, m1_completed: bool = True) -> Path:
        proj = self.tmp_path / f"test_proj_{uuid.uuid4().hex[:8]}"
        proj.mkdir(parents=True)
        (proj / "state").mkdir(parents=True, exist_ok=True)

        state = PipelineState(proj)
        state.data["project"] = {
            "name": proj.name,
            "topic": "Test",
            "display_name": "Test",
            "created_at": "2024-01-01T00:00:00",
            "venue": {"id": "arxiv", "name": "arXiv"},
        }
        state.set_stage("M1S05", "in_progress")
        if m1_completed:
            state.set_module_status("M1", "completed", "M1S05")
        else:
            state.set_module_status("M1", "in_progress", "M1S04")

        _write_m1s02_doc(proj)
        _write_m1s03_doc(proj)
        _write_m1s04_doc(proj)
        _write_m1s05_doc(proj)
        _write_gate_review(proj, "G1")

        return proj

    def test_m1s05_advance_marks_m1_completed(self) -> None:
        proj = self._setup_project_at_m1s05(m1_completed=False)

        output_file = str(proj / "knowledge" / "reviews" / "G1_aggregate.md")
        exit_code, output = _call_advance(
            str(proj), "M1S05", "ideation", output_file, skip_gates=True
        )
        assert exit_code is None, f"Expected success, got exit {exit_code}. Output: {output}"
        assert "MODULE COMPLETE" in output, f"Expected MODULE COMPLETE, got: {output}"

        state = PipelineState(proj)
        mod_status = state.get_module_status("M1")
        assert mod_status.get("status") == "completed", (
            f"M1 should be completed after advancing M1S05, got: {mod_status}"
        )
        print("  [PASS] Advancing M1S05 marks M1 as completed")

    def test_m2_blocked_without_m1_completed(self) -> None:
        proj = self._setup_project_at_m1s05(m1_completed=False)

        # Ensure M1 is NOT completed
        state = PipelineState(proj)
        state.set_module_status("M1", "in_progress", "M1S04")

        # Try to run M2
        exit_code = None
        try:
            with patch("sys.stdout", new=io.StringIO()):
                cmd_run_module(str(proj), "M2")
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else 1

        assert exit_code == 1, f"Expected M2 start to be blocked (exit 1), got {exit_code}"
        print("  [PASS] M2 blocked when M1 not completed")


class TestStageGateIntegration(unittest.TestCase):
    """Test 8: check_stage enforces 3-Round and document completeness."""

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_path)

    def test_check_stage_blocks_missing_round3(self) -> None:
        proj = self.tmp_path / f"test_proj_{uuid.uuid4().hex[:8]}"
        proj.mkdir(parents=True)
        (proj / "knowledge" / "M1").mkdir(parents=True)
        (proj / "knowledge" / "reviews").mkdir(parents=True)
        (proj / "state").mkdir(parents=True)

        sources = [_create_diverse_sources(1)[0]]
        _write_source_log(proj, sources, {})
        _write_survey_memory(proj, [
            {"batch_id": 1, "round": 1, "status": "passed", "queries": ["q1"]},
            {"batch_id": 2, "round": 2, "status": "passed", "queries": ["q2"]},
        ])
        # Create round review files for rounds 1 and 2
        for rn in (1, 2):
            review_file = proj / "knowledge" / "reviews" / f"M1S02_round{rn}_review.md"
            review_file.write_text(f"# Round {rn} Review\n\nVerdict: PASS\n", encoding="utf-8")
        _write_m1s02_doc(proj)

        ok, msgs = check_stage(proj, "M1S02")
        assert ok is False, f"Expected check_stage to fail, got ok={ok}"
        fail_msgs = [m for m in msgs if "round 3" in m.lower() and "FAIL" in m]
        assert len(fail_msgs) >= 1, f"Expected Round 3 FAIL message, got: {msgs}"
        print("  [PASS] check_stage blocks M1S02 when Round 3 missing")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
