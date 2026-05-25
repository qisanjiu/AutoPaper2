#!/usr/bin/env python3
"""Integration tests for M1 module (Domain Survey) after gap-type enhancement."""

from __future__ import annotations

import os
import sys
import shutil
import tempfile
import unittest
import uuid
import yaml
from pathlib import Path

# Add project root to path
_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from spiral.survey_memory import (
    Gap, GapType, SurveyMemory, SurveyMemoryManager, Source, SearchBatch, RoundReview
)
from spiral.project import ProjectManager
from spiral.state import PipelineState
from utils.source_log_validator import validate as validate_source_log
from utils.stage_gate import check_stage


def _rich_source(source_id: str, title: str, author: str) -> dict:
    return {
        "id": source_id,
        "title": title,
        "type": "academic",
        "credibility": 4,
        "authors": [author],
        "background": f"Background for {title}",
        "contributions": [f"Contribution of {title}"],
        "model": f"Model used in {title}",
        "method": f"Method details for {title}",
        "experiment_setup": "datasets, metrics, baselines, protocol, and seeds",
        "results": f"Results reported by {title}",
        "analysis": f"Analysis from {title}",
        "conclusion": f"Conclusion of {title}",
    }


def _gap(gap_id: str, level: str, gap_type: str, sources: list[str]) -> dict:
    labels = {
        "large": "Large direction scenario-level gap",
        "middle": "Middle direction model/metric gap",
        "small": "Small direction component-level gap",
    }
    return {
        "id": gap_id,
        "supporting_sources": sources,
        "gap_type": gap_type,
        "level": level,
        "description": labels[level],
    }


def _search_provenance(source_ids: list[str] | None = None) -> dict:
    ids = source_ids or ["s1", "s2", "s3", "s4", "s5"]
    return {
        "databases": ["public_db", "Semantic Scholar", "arXiv", "internet web search"],
        "inclusion_criteria": ["peer-reviewed or authoritative source", "reports methods and experiments"],
        "exclusion_criteria": ["irrelevant task", "missing experimental evidence"],
        "rounds": [
            {
                "round": 1,
                "goal": "breadth",
                "queries": ["topic survey baseline", "task dataset metric"],
                "retrieved_count": 40,
                "screened_count": 18,
                "retained_source_ids": ids[:2],
            },
            {
                "round": 2,
                "goal": "depth",
                "queries": ["gap targeted method", "failure analysis"],
                "retrieved_count": 25,
                "screened_count": 12,
                "retained_source_ids": ids[2:4],
            },
            {
                "round": 3,
                "goal": "blindspot",
                "queries": ["recent negative result", "seminal key author"],
                "retrieved_count": 18,
                "screened_count": 10,
                "retained_source_ids": ids[1:2] + ids[-1:],
            },
        ],
        "blindspot_checks": {
            "recent_work": "checked recent 6 months and latest 2026 work",
            "negative_results": "checked negative/opposing/contradictory results",
            "seminal_work": "checked seminal classic foundation papers",
            "key_authors": "checked key author and team follow-up work",
            "source_log_consistency": "checked Source Log consistency with report",
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
                "finding": "Dataset/protocol perspective identifies benchmark and experimental setup gaps.",
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


def _m2_source(source_id: str, dimension: str, target_gap: str, domain: str, author: str) -> dict:
    return {
        "id": source_id,
        "title": f"{domain} transferable method",
        "type": "academic",
        "credibility": 4,
        "authors": [author],
        "search_dimension": dimension,
        "target_gap": target_gap,
        "source_domain": domain,
        "core_mechanism": f"{domain} mechanism can transfer to {target_gap}",
        "adaptation_potential": "high",
        "discovery_source": "public_db" if dimension != "same_task_diff_modality" else "web_search",
        "discovery_query": f"{domain} {dimension} transferable mechanism",
    }


def _m2_search_statistics(source_ids: list[str]) -> dict:
    return {
        "total_queries": 4,
        "public_db_hits": 12,
        "web_search_hits": 8,
        "citation_chain_hits": 6,
        "unique_papers_discovered": 18,
        "papers_shortlisted": len(source_ids),
        "shortlisted_source_ids": source_ids,
        "search_dimensions_covered": [
            "same_modality_diff_task",
            "same_task_diff_modality",
            "shared_principle",
            "similar_structure",
        ],
        "query_ledger": [
            {"query": "vision same modality mechanism", "source": "public_db", "results_count": 12},
            {"query": "speech same task different modality", "source": "web_search", "results_count": 8},
            {"query": "optimization shared principle", "source": "citation_chain", "results_count": 6},
            {"query": "control similar structure", "source": "public_db", "results_count": 5},
        ],
    }


class TestGapDataclass(unittest.TestCase):
    """Test Gap dataclass with new gap_type fields."""

    def test_vacancy_gap_default(self):
        g = Gap(id="gap_1", description="some gap")
        assert g.gap_type == GapType.VACANCY
        assert g.to_dict()["gap_type"] == "vacancy"
        print("  [PASS] Default vacancy gap")

    def test_enhancement_gap(self):
        g = Gap(
            id="gap_e1",
            description="attention module bottleneck",
            gap_type=GapType.ENHANCEMENT,
            target_component="attention",
            baseline_framework="Transformer",
            bottleneck_description="cannot distinguish foreground/background",
        )
        d = g.to_dict()
        assert d["gap_type"] == "enhancement"
        assert d["target_component"] == "attention"
        assert d["baseline_framework"] == "Transformer"
        print("  [PASS] Enhancement gap with component fields")

    def test_gap_from_dict(self):
        data = {
            "id": "gap_v1",
            "description": "test",
            "gap_type": "validation",
            "evidence_sources": ["src1"],
        }
        g = Gap.from_dict(data)
        assert g.gap_type == GapType.VALIDATION
        print("  [PASS] Gap from_dict with validation type")


class TestSurveyMemory(unittest.TestCase):
    """Test SurveyMemory persistence and gap management."""

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def test_add_gap_with_type(self):
        mem = SurveyMemory(topic="test")
        g = Gap(id="gap_e1", gap_type=GapType.ENHANCEMENT, target_component="conv")
        mem.add_gap(g)
        gaps = mem.findings.get("gaps", [])
        assert len(gaps) == 1
        assert gaps[0]["gap_type"] == "enhancement"
        assert gaps[0]["target_component"] == "conv"
        print("  [PASS] SurveyMemory.add_gap with enhancement type")

    def test_persistence_roundtrip(self):
        mgr = SurveyMemoryManager(self.tmp_path, auto_connect=False)
        mem = SurveyMemory(topic="test topic")
        mem.add_gap(Gap(id="g1", gap_type=GapType.VACANCY))
        mem.add_gap(Gap(id="g2", gap_type=GapType.ENHANCEMENT, target_component="attn"))
        mgr.save(mem)

        loaded = mgr.load()
        gaps = loaded.findings.get("gaps", [])
        assert len(gaps) == 2
        types = {g["gap_type"] for g in gaps}
        assert types == {"vacancy", "enhancement"}
        print("  [PASS] SurveyMemory persistence roundtrip")


class TestSourceLogValidator(unittest.TestCase):
    """Test source_log_validator with gap-type checks."""

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def _create_project_with_source_log(self, gaps: list[dict], sources: list[dict]) -> Path:
        import uuid
        proj = self.tmp_path / f"test_project_{uuid.uuid4().hex[:8]}"
        proj.mkdir()
        (proj / "knowledge" / "M1").mkdir(parents=True)
        (proj / "state").mkdir(parents=True)

        source_log = {
            "sources": sources,
            "gap_evidence_map": {g["id"]: g for g in gaps},
            "search_provenance": _search_provenance([s["id"] for s in sources]),
        }
        with open(proj / "knowledge" / "M1" / "M1_source_log.yaml", "w") as f:
            yaml.dump(source_log, f)
        return proj

    def _create_project_with_m2_source_log(self, include_stats: bool = True) -> Path:
        proj = self.tmp_path / f"test_project_{uuid.uuid4().hex[:8]}"
        proj.mkdir()
        (proj / "knowledge" / "M2").mkdir(parents=True)
        sources = [
            _m2_source("m2s1", "same_modality_diff_task", "gap_1", "vision", "A"),
            _m2_source("m2s2", "same_task_diff_modality", "gap_2", "speech", "B"),
            _m2_source("m2s3", "shared_principle", "gap_3", "optimization", "C"),
            _m2_source("m2s4", "similar_structure", "gap_1", "control", "D"),
        ]
        source_log = {
            "sources": sources,
            "gap_solution_map": {
                "gap_1": {"solutions": ["m2s1", "m2s4"], "selected_solution": "m2s1"},
                "gap_2": {"solutions": ["m2s2"], "selected_solution": "m2s2"},
                "gap_3": {"solutions": ["m2s3"], "selected_solution": "m2s3"},
            },
        }
        if include_stats:
            source_log["search_statistics"] = _m2_search_statistics([source["id"] for source in sources])
        with open(proj / "knowledge" / "M2" / "M2_source_log.yaml", "w") as f:
            yaml.dump(source_log, f)
        return proj

    def test_gap_type_distribution_warning(self):
        gaps = [
            _gap("gap_1", "large", "vacancy", ["s1", "s2"]),
            _gap("gap_2", "middle", "vacancy", ["s1", "s2"]),
            _gap("gap_3", "small", "vacancy", ["s1", "s2"]),
        ]
        sources = [_rich_source("s1", "Paper 1", "A"), _rich_source("s2", "Paper 2", "B")]
        proj = self._create_project_with_source_log(gaps, sources)
        ok, msgs = validate_source_log(proj, module="M1")
        warn_msgs = [m for m in msgs if "vacancy-type" in m]
        assert len(warn_msgs) >= 1, f"Expected vacancy-type warning, got: {msgs}"
        print("  [PASS] Validator warns on all-vacancy gaps")

    def test_gap_type_distribution_pass(self):
        gaps = [
            _gap("gap_1", "large", "vacancy", ["s1", "s2"]),
            _gap("gap_2", "middle", "enhancement", ["s1", "s2"]),
            _gap("gap_3", "small", "vacancy", ["s1", "s2"]),
        ]
        sources = [_rich_source("s1", "Paper 1", "A"), _rich_source("s2", "Paper 2", "B")]
        proj = self._create_project_with_source_log(gaps, sources)
        ok, msgs = validate_source_log(proj, module="M1")
        pass_msgs = [m for m in msgs if "EG/ValG gap(s) found" in m]
        assert len(pass_msgs) >= 1, f"Expected EG/ValG pass message, got: {msgs}"
        print("  [PASS] Validator passes on mixed gap types")

    def test_missing_deep_reading_fields_fail(self):
        gaps = [
            _gap("gap_1", "large", "enhancement", ["s1", "s2"]),
            _gap("gap_2", "middle", "validation", ["s2", "s3"]),
            _gap("gap_3", "small", "vacancy", ["s4", "s5"]),
        ]
        sources = [
            _rich_source(f"s{i}", f"Paper {i}", f"Author {i}")
            for i in range(1, 6)
        ]
        sources[0].pop("experiment_setup")
        proj = self._create_project_with_source_log(gaps, sources)

        ok, msgs = validate_source_log(proj, module="M1")

        assert ok is False, f"Expected missing deep-reading fields to fail, got: {msgs}"
        fail_msgs = [m for m in msgs if "missing deep-reading fields" in m and "[FAIL]" in m]
        assert fail_msgs, f"Expected deep-reading failure, got: {msgs}"
        print("  [PASS] Validator fails on missing deep-reading fields")

    def test_missing_search_provenance_fail(self):
        gaps = [
            _gap("gap_1", "large", "enhancement", ["s1", "s2"]),
            _gap("gap_2", "middle", "validation", ["s2", "s3"]),
            _gap("gap_3", "small", "vacancy", ["s4", "s5"]),
        ]
        sources = [
            _rich_source(f"s{i}", f"Paper {i}", f"Author {i}")
            for i in range(1, 6)
        ]
        proj = self._create_project_with_source_log(gaps, sources)
        log_path = proj / "knowledge" / "M1" / "M1_source_log.yaml"
        data = yaml.safe_load(log_path.read_text(encoding="utf-8"))
        data.pop("search_provenance")
        log_path.write_text(yaml.dump(data), encoding="utf-8")

        ok, msgs = validate_source_log(proj, module="M1")

        assert ok is False
        assert any("search_provenance missing" in msg for msg in msgs), msgs
        print("  [PASS] Validator fails on missing M1 search_provenance")

    def test_missing_perspective_coverage_fail(self):
        gaps = [
            _gap("gap_1", "large", "enhancement", ["s1", "s2"]),
            _gap("gap_2", "middle", "validation", ["s2", "s3"]),
            _gap("gap_3", "small", "vacancy", ["s4", "s5"]),
        ]
        sources = [
            _rich_source(f"s{i}", f"Paper {i}", f"Author {i}")
            for i in range(1, 6)
        ]
        proj = self._create_project_with_source_log(gaps, sources)
        log_path = proj / "knowledge" / "M1" / "M1_source_log.yaml"
        data = yaml.safe_load(log_path.read_text(encoding="utf-8"))
        data["search_provenance"].pop("perspective_coverage")
        log_path.write_text(yaml.safe_dump(data), encoding="utf-8")

        ok, msgs = validate_source_log(proj, module="M1")

        assert ok is False
        assert any("perspective_coverage missing" in msg for msg in msgs), msgs
        print("  [PASS] Validator fails on missing M1 perspective_coverage")

    def test_bidirectional_consistency(self):
        gaps = [
            _gap("gap_1", "large", "vacancy", ["s1", "s2"]),
            _gap("gap_2", "middle", "enhancement", ["s1", "s2"]),
            _gap("gap_3", "small", "validation", ["s1", "s2"]),
        ]
        sources = [_rich_source("s1", "Paper 1", "A"), _rich_source("s2", "Paper 2", "B")]
        proj = self._create_project_with_source_log(gaps, sources)

        # Create survey_memory with different gaps (simulating out-of-sync)
        mem = SurveyMemory(topic="test")
        mem.add_gap(Gap(id="gap_1", gap_type=GapType.VACANCY))
        mem.add_gap(Gap(id="gap_2", gap_type=GapType.ENHANCEMENT))
        mgr = SurveyMemoryManager(proj, auto_connect=False)
        mgr.save(mem)

        ok, msgs = validate_source_log(proj, module="M1")
        warn_msgs = [m for m in msgs if "not in survey_memory" in m or "not in Source Log" in m]
        assert len(warn_msgs) >= 1, f"Expected consistency warning, got: {msgs}"
        print("  [PASS] Validator detects Source Log ↔ Survey Memory inconsistency")

    def test_m2_source_log_accepts_search_statistics(self):
        proj = self._create_project_with_m2_source_log(include_stats=True)

        ok, msgs = validate_source_log(proj, module="M2")

        assert ok is True, msgs
        assert any("M2 search_statistics records total_queries" in msg for msg in msgs), msgs
        assert any("M2 search/adaptation fields complete" in msg for msg in msgs), msgs
        print("  [PASS] Validator accepts M2 search statistics and adaptation provenance")

    def test_m2_missing_search_statistics_fail(self):
        proj = self._create_project_with_m2_source_log(include_stats=False)

        ok, msgs = validate_source_log(proj, module="M2")

        assert ok is False
        assert any("M2 search_statistics missing" in msg for msg in msgs), msgs
        print("  [PASS] Validator fails on missing M2 search_statistics")


class TestStageGate(unittest.TestCase):
    """Test stage_gate M1 enforcement."""

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def _create_project_with_survey_memory(self, batches: list[dict]) -> Path:
        import uuid
        proj = self.tmp_path / f"test_project_{uuid.uuid4().hex[:8]}"
        proj.mkdir()
        (proj / "knowledge" / "M1").mkdir(parents=True)
        (proj / "knowledge" / "reviews").mkdir(parents=True)
        (proj / "state").mkdir(parents=True)

        # Create source log that satisfies the large/middle/small M1 report contract.
        sources = [
            _rich_source("s1", "P1", "A"),
            _rich_source("s2", "P2", "B"),
            _rich_source("s3", "P3", "C"),
            _rich_source("s4", "P4", "D"),
            _rich_source("s5", "P5", "E"),
        ]
        source_log = {
            "sources": sources,
            "gap_evidence_map": {
                "gap_1": _gap("gap_1", "large", "vacancy", ["s1", "s2"]),
                "gap_2": _gap("gap_2", "middle", "enhancement", ["s3", "s4"]),
                "gap_3": _gap("gap_3", "small", "validation", ["s2", "s5"]),
            },
            "search_provenance": _search_provenance(),
        }
        with open(proj / "knowledge" / "M1" / "M1_source_log.yaml", "w") as f:
            yaml.dump(source_log, f)

        # Create survey_memory with batches and round_reviews
        mem = SurveyMemory(topic="test")
        for b in batches:
            batch = SearchBatch(
                batch_id=b["batch_id"],
                round=b["round"],
                status=b["status"],
                queries=b.get("queries", []),
                sources_found=b.get("sources_found", 5 if b["status"] == "passed" else 0),
            )
            mem.search_batches.append(batch)
            # Add round review for each batch's round
            from spiral.survey_memory import RoundReview
            mem.add_round_review(RoundReview(
                round=b["round"],
                verdict="PASS" if b["status"] == "passed" else "REWORK",
                score=0.8,
            ))
        mgr = SurveyMemoryManager(proj, auto_connect=False)
        mgr.save(mem)

        # Create round review files for all rounds present in batches
        round_nums_present = {b["round"] for b in batches}
        for rn in (1, 2, 3):
            review_file = proj / "knowledge" / "reviews" / f"M1S02_round{rn}_review.md"
            if rn in round_nums_present:
                # Match batch status for that round
                batch_statuses = [b["status"] for b in batches if b["round"] == rn]
                verdict = "PASS" if any(s == "passed" for s in batch_statuses) else "REWORK"
            else:
                verdict = "REWORK"
            review_file.write_text(f"# Round {rn} Review\n\nVerdict: {verdict}\n", encoding="utf-8")

        # Create M1S02 doc with all 3 rounds
        doc = proj / "knowledge" / "M1" / "M1S02_literature_deepdive.md"
        doc.write_text(
            "# Test\n### Round 1\n### Round 2\n### Round 3\n\n"
            "## 检索策略 search strategy\n"
            "数据库 public_db and internet web search; screening inclusion/exclusion criteria recorded.\n\n"
            "## Perspective Coverage\n"
            "Perspective coverage covers scenario/task, model/method, metric/performance, "
            "dataset/protocol, failure/limitation, and baseline/comparison views.\n\n"
            "## Detailed Research Report\n"
            "研究空白 gap report covers 大方向 large direction scenario issues, "
            "中方向 middle direction model/metric issues, and 小方向 small direction component issues.\n"
            "证据链 evidence chain cites the Source Log supporting sources for every gap.\n"
        )

        return proj

    def _create_project_with_m1_gap_chain(self) -> Path:
        proj = self.tmp_path / f"test_project_{uuid.uuid4().hex[:8]}"
        proj.mkdir()
        (proj / "knowledge" / "M1").mkdir(parents=True)
        (proj / "knowledge" / "reviews").mkdir(parents=True)
        (proj / "state").mkdir(parents=True)
        sources = [
            _rich_source("s1", "P1", "A"),
            _rich_source("s2", "P2", "B"),
            _rich_source("s3", "P3", "C"),
            _rich_source("s4", "P4", "D"),
            _rich_source("s5", "P5", "E"),
        ]
        source_log = {
            "sources": sources,
            "gap_evidence_map": {
                "gap_large": _gap("gap_large", "large", "vacancy", ["s1", "s2"]),
                "gap_middle": _gap("gap_middle", "middle", "enhancement", ["s3", "s4"]),
                "gap_small": _gap("gap_small", "small", "validation", ["s2", "s5"]),
            },
            "search_provenance": _search_provenance(),
        }
        with open(proj / "knowledge" / "M1" / "M1_source_log.yaml", "w") as f:
            yaml.dump(source_log, f)
        return proj

    def test_missing_round3(self):
        proj = self._create_project_with_survey_memory([
            {"batch_id": 1, "round": 1, "status": "passed", "queries": ["q1"]},
            {"batch_id": 2, "round": 2, "status": "passed", "queries": ["q2"]},
        ])
        ok, msgs = check_stage(proj, "M1S02")
        fail_msgs = [m for m in msgs if "round 3" in m.lower() and "FAIL" in m]
        assert len(fail_msgs) >= 1, f"Expected Round 3 FAIL, got: {msgs}"
        print("  [PASS] stage_gate blocks when Round 3 missing")

    def test_round3_not_passed(self):
        proj = self._create_project_with_survey_memory([
            {"batch_id": 1, "round": 1, "status": "passed", "queries": ["q1"]},
            {"batch_id": 2, "round": 2, "status": "passed", "queries": ["q2"]},
            {"batch_id": 3, "round": 3, "status": "awaiting_review", "queries": ["q3"]},
        ])
        ok, msgs = check_stage(proj, "M1S02")
        fail_msgs = [m for m in msgs if "round 3" in m.lower() and ("not pass" in m.lower() or "not passed" in m.lower())]
        assert len(fail_msgs) >= 1, f"Expected Round 3 not-passed FAIL, got: {msgs}"
        print("  [PASS] stage_gate blocks when Round 3 not passed")

    def test_round3_passed(self):
        proj = self._create_project_with_survey_memory([
            {"batch_id": 1, "round": 1, "status": "passed", "queries": ["q1"]},
            {"batch_id": 2, "round": 2, "status": "passed", "queries": ["q2"]},
            {"batch_id": 3, "round": 3, "status": "passed", "queries": ["q3"]},
        ])
        ok, msgs = check_stage(proj, "M1S02")
        pass_msgs = [m for m in msgs if "round 3" in m.lower() and "passed" in m.lower()]
        assert len(pass_msgs) >= 1, f"Expected Round 3 passed, got: {msgs}"
        print("  [PASS] stage_gate passes when Round 3 completed")

    def test_m1s03_blocks_question_without_gap_chain(self):
        proj = self._create_project_with_m1_gap_chain()
        (proj / "knowledge" / "M1" / "M1S03_research_question.md").write_text(
            "# Research Question\n\nA vague research question.\n",
            encoding="utf-8",
        )

        ok, msgs = check_stage(proj, "M1S03")

        assert ok is False
        assert any("missing large direction problem" in msg for msg in msgs), msgs
        assert any("does not cite any gap ID" in msg for msg in msgs), msgs

    def test_m1s03_accepts_source_backed_question(self):
        proj = self._create_project_with_m1_gap_chain()
        (proj / "knowledge" / "M1" / "M1S03_research_question.md").write_text(
            "# Research Question\n\n"
            "## 1. 从 Gap 到问题\n"
            "大方向 large direction gap_large, 中方向 middle direction gap_middle, "
            "小方向 small direction gap_small are mapped into the question.\n\n"
            "## 2. 研究问题\n"
            "**主问题**: research question from gap_large/gap_middle/gap_small.\n\n"
            "### FINER 标准验证\n"
            "- Feasible: yes\n- Interesting: yes\n- Novel: source-backed\n"
            "- Ethical: yes\n- Relevant: yes\n\n"
            "## 3. 问题分解\n"
            "| 子问题 | 依赖 | 验证方式 |\n|---|---|---|\n| Q1 | gap_large | experiment |\n\n"
            "## 4. 创新类型声明\n"
            "架构改进型 innovation type.\n\n"
            "## 5. 范围界定\n"
            "包含 gap_large/gap_middle/gap_small; 排除 unrelated scope.\n",
            encoding="utf-8",
        )

        ok, msgs = check_stage(proj, "M1S03")

        assert ok is True, msgs
        assert any("cites source-log gap IDs" in msg for msg in msgs), msgs

    def test_m1s04_blocks_hypothesis_without_metrics_or_h0(self):
        proj = self._create_project_with_m1_gap_chain()
        (proj / "knowledge" / "M1" / "M1S04_hypothesis_generation.md").write_text(
            "# Hypothesis\n\nH1 might work.\n",
            encoding="utf-8",
        )

        ok, msgs = check_stage(proj, "M1S04")

        assert ok is False
        assert any("missing null hypothesis" in msg for msg in msgs), msgs
        assert any("does not cite any gap ID" in msg for msg in msgs), msgs

    def test_m1s04_accepts_measurable_hypothesis_chain(self):
        proj = self._create_project_with_m1_gap_chain()
        (proj / "knowledge" / "M1" / "M1S04_hypothesis_generation.md").write_text(
            "# Hypothesis Generation\n\n"
            "## 1. 核心假设\n"
            "| 假设 ID | 假设陈述 | 来源 |\n|---|---|---|\n"
            "| H1 | improves the target behavior | gap_large, gap_middle, gap_small |\n\n"
            "## 2. 可测量预测\n"
            "| 假设 | 预测 | 测量指标 | 实验设计 |\n|---|---|---|---|\n"
            "| H1 | better than baseline | accuracy metric | experiment design |\n\n"
            "## 3. 零假设\n"
            "| 假设 | 零假设 H0 |\n|---|---|\n| H1 | no difference |\n\n"
            "## 4. 假设-问题映射\n"
            "Gap gap_large -> 问题 Q1 -> 假设 H1 -> 预测 P1; gap_middle and gap_small are secondary.\n",
            encoding="utf-8",
        )

        ok, msgs = check_stage(proj, "M1S04")

        assert ok is True, msgs

    def test_m1s05_blocks_novelty_without_handoff_and_evidence(self):
        proj = self._create_project_with_m1_gap_chain()
        (proj / "knowledge" / "M1" / "M1S05_novelty_feasibility.md").write_text(
            "# Novelty\n\nLooks novel.\n",
            encoding="utf-8",
        )

        ok, msgs = check_stage(proj, "M1S05")

        assert ok is False
        assert any("missing literature comparison" in msg for msg in msgs), msgs
        assert any("handoff_M1_M2.md not found" in msg for msg in msgs), msgs

    def test_m1s05_accepts_novelty_feasibility_and_handoff(self):
        proj = self._create_project_with_m1_gap_chain()
        (proj / "knowledge" / "M1" / "M1S05_novelty_feasibility.md").write_text(
            "# Novelty & Feasibility Assessment\n\n"
            "## 1. 新颖性评估\n"
            "Novelty is supported by Source s1-s5 and GAP IDs gap_large/gap_middle/gap_small. "
            "大方向 large direction, 中方向 middle direction, 小方向 small direction are explicit.\n\n"
            "## 2. 文献对比\n"
            "| 对比维度 | 已有工作 | 本研究 | 差异 |\n|---|---|---|---|\n"
            "| scenario | s1 | gap_large | source-backed difference |\n\n"
            "## 3. 可行性分析\n"
            "- 技术可行性: yes\n- 数据可行性: yes\n- 计算资源: bounded\n\n"
            "## 4. 风险评估\n"
            "| 风险 | 概率 | 影响 | 缓解措施 |\n|---|---|---|---|\n| risk | 中 | 中 | mitigation |\n\n"
            "## 5. 最终判断\n"
            "**建议**: PROCEED\n",
            encoding="utf-8",
        )
        (proj / "knowledge" / "handoff_M1_M2.md").write_text(
            "# Handoff\n\nResearch question and hypothesis from gap_large, gap_middle, gap_small.\n",
            encoding="utf-8",
        )

        ok, msgs = check_stage(proj, "M1S05")

        assert ok is True, msgs


class TestProjectCreation(unittest.TestCase):
    """Test project creation initializes SurveyMemory correctly."""

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    def test_survey_memory_init(self):
        proj = ProjectManager.create(
            topic="Test Topic",
            display_name="Test-Project",
            projects_root=self.tmp_path,
        )
        mgr = SurveyMemoryManager(proj, auto_connect=False)
        mem = mgr.load()
        assert mem.topic == "Test Topic"
        assert mem.status.value == "planning"
        print("  [PASS] Project creation initializes SurveyMemory")


if __name__ == "__main__":
    unittest.main()
