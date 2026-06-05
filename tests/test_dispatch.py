from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.context_budget import resolve_packet_path
from spiral.conductor import Conductor
from spiral.dispatch import (
    build_packets,
    build_stage_execution_packet,
    build_stage_review_packets,
    build_ssh_ops_packet,
    write_packets,
)
from spiral.revision_router import build_revision_routes
from spiral.state import PipelineState
from utils.stage_gate import check_stage


def _valid_m2_source_log() -> dict:
    sources = []
    for idx, (dimension, gap_id, domain, discovery_source) in enumerate(
        [
            ("same_modality_diff_task", "gap_1", "vision", "public_db"),
            ("same_task_diff_modality", "gap_2", "speech", "web_search"),
            ("shared_principle", "gap_3", "optimization", "citation_chain"),
            ("similar_structure", "gap_1", "control", "public_db"),
        ],
        start=1,
    ):
        sources.append(
            {
                "id": f"m2s{idx}",
                "title": f"{domain} transferable method",
                "type": "academic",
                "credibility": 4,
                "authors": [f"Author {idx}"],
                "search_dimension": dimension,
                "target_gap": gap_id,
                "source_domain": domain,
                "core_mechanism": f"{domain} mechanism",
                "adaptation_potential": "high",
                "discovery_source": discovery_source,
                "discovery_query": f"{domain} {dimension} transferable mechanism",
            }
        )
    return {
        "search_statistics": {
            "total_queries": 4,
            "public_db_hits": 12,
            "web_search_hits": 8,
            "citation_chain_hits": 6,
            "unique_papers_discovered": 18,
            "papers_shortlisted": 4,
            "shortlisted_source_ids": [source["id"] for source in sources],
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
        },
        "sources": sources,
        "gap_solution_map": {
            "gap_1": {"solutions": ["m2s1", "m2s4"], "selected_solution": "m2s1"},
            "gap_2": {"solutions": ["m2s2"], "selected_solution": "m2s2"},
            "gap_3": {"solutions": ["m2s3"], "selected_solution": "m2s3"},
        },
    }


def _make_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    for rel in (
        "state",
        "knowledge/M1",
        "knowledge/M2",
        "knowledge/M6",
        "knowledge/reviews",
        "drafts",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)

    state = {
        "project": {
            "name": "dispatch-test",
            "display_name": "dispatch-test",
            "topic": "dispatch test",
            "venue": {"id": "arxiv", "name": "arXiv"},
        },
        "current": {"module": "M2", "stage": "M2S01", "status": "in_progress"},
        "modules": {
            "M1": {"status": "completed", "completed_at": None, "last_stage": "M1S05"},
            "M2": {"status": "in_progress", "completed_at": None, "last_stage": None},
            "M3": {"status": "pending", "completed_at": None, "last_stage": None},
            "M4": {"status": "pending", "completed_at": None, "last_stage": None},
            "M5": {"status": "pending", "completed_at": None, "last_stage": None},
            "M6": {"status": "pending", "completed_at": None, "last_stage": None},
        },
        "settings": {"auto_advance_modules": False},
        "history": [],
        "backtrack_log": [],
        "spiral_count": {},
        "agents": {},
        "gates": {},
        "stale_stages": [],
        "gate_re_review": {},
        "human_reviews": [],
        "decision_log": [],
    }
    (root / "state" / "pipeline_state.yaml").write_text(
        yaml.safe_dump(state, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (root / "knowledge" / "M1" / "M1S02_literature_deepdive.md").write_text(
        "# M1S02\n## Round 1\n## Round 2\n## Round 3\n",
        encoding="utf-8",
    )
    (root / "knowledge" / "M1" / "M1_source_log.yaml").write_text(
        "sources: []\ngap_evidence_map: {}\n",
        encoding="utf-8",
    )
    (root / "knowledge" / "M2" / "M2S01_cross_domain_search.md").write_text(
        "# M2S01\n同模态不同任务\n底层原理\n候选方案\n",
        encoding="utf-8",
    )
    (root / "knowledge" / "M2" / "M2_source_log.yaml").write_text(
        yaml.safe_dump(_valid_m2_source_log(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (root / "state" / "survey_memory.yaml").write_text(
        "findings:\n  gaps: []\n",
        encoding="utf-8",
    )
    return root


class TestDispatchPackets(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = _make_project(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_stage_execution_packet_requires_method_subagent(self) -> None:
        packet = build_stage_execution_packet(self.root, "M2S01")

        self.assertEqual(packet["task_type"], "stage_execution")
        self.assertTrue(packet["delegation_required"])
        self.assertEqual(packet["role"], "method")
        self.assertTrue(packet["agent_md"].endswith("docs/AGENTS/method/AGENT.md"))
        self.assertTrue(packet["output_path"].endswith("knowledge/M2/M2S01_cross_domain_search.md"))
        self.assertIn("must not edit knowledge/", "\n".join(packet["main_agent_boundaries"]))

    def test_stage_execution_packet_has_compact_launch_contract(self) -> None:
        packet = build_stage_execution_packet(self.root, "M2S01")

        self.assertEqual(packet["schema_version"], "dispatch.v2")
        self.assertEqual(packet["project_root"], "project:.")
        self.assertEqual(packet["context_policy"]["handoff_mode"], "packet_path_only")
        self.assertIs(packet["context_policy"]["no_parent_context"], True)
        self.assertTrue(any(path == "framework:docs/AGENTS/_shared/runtime_contract.md" for path in packet["shared_contracts"]))
        self.assertTrue(resolve_packet_path(packet["role_spec"], packet, project_root=self.root).exists())
        self.assertTrue(packet["agent_md"].startswith("framework:"))
        self.assertTrue(packet["output_path"].startswith("project:"))
        self.assertTrue(packet["role_spec"].endswith("docs/AGENTS/_specs/method.md"))
        self.assertIn("Do not use the parent conversation", packet["subagent_launch_prompt"])
        self.assertIn("Read and execute this AutoPaper2 dispatch packet", packet["subagent_launch_prompt"])
        self.assertIn("Resolve project: refs", packet["subagent_launch_prompt"])
        self.assertIn("Role spec:", packet["subagent_launch_prompt"])
        self.assertIn("docs/AGENTS/_specs/method.md", packet["subagent_launch_prompt"])
        self.assertLessEqual(len(packet["subagent_launch_prompt"]), packet["context_policy"]["max_initial_prompt_chars"])

    def test_stage_execution_packet_requires_canonical_in_place_output(self) -> None:
        packet = build_stage_execution_packet(self.root, "M2S01")

        policy = packet["output_write_policy"]
        self.assertEqual(policy["mode"], "canonical_in_place")
        self.assertEqual(policy["target_path"], packet["output_path"])
        self.assertIs(policy["overwrite_existing"], True)
        self.assertIs(policy["forbid_alternate_outputs"], True)
        self.assertIn("_revised", policy["forbidden_suffixes"])
        self.assertIn("canonical_in_place", packet["subagent_prompt"])
        self.assertIn("do not create v2/new/revised/backtrack", packet["subagent_launch_prompt"])

    def test_written_markdown_packet_exposes_only_compact_launch_prompt(self) -> None:
        packet = build_stage_execution_packet(self.root, "M2S01")
        paths = write_packets(self.root, [packet], fmt="markdown")

        text = paths[0].read_text(encoding="utf-8")
        self.assertIn("packet_path: `project:state/dispatch/", text)
        self.assertIn("## Compact Launch Prompt", text)
        self.assertIn("## Context Policy", text)
        self.assertIn("handoff_mode: packet_path_only", text)
        self.assertIn("role_spec:", text)
        self.assertIn("docs/AGENTS/_specs/method.md", text)
        self.assertIn("output_write_policy:", text)
        self.assertNotIn("## Subagent Prompt", text)

    def test_ssh_ops_packet_targets_ssh_agent(self) -> None:
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config" / "execution_env.yaml").write_text("execution:\n  mode: ssh\n", encoding="utf-8")

        packet = build_ssh_ops_packet(self.root, "alloc")

        self.assertEqual(packet["task_type"], "ssh_ops")
        self.assertTrue(packet["delegation_required"])
        self.assertEqual(packet["role"], "ssh")
        self.assertTrue(packet["agent_md"].endswith("docs/AGENTS/ssh/AGENT.md"))
        self.assertIn("SSH operation: alloc", packet["subagent_prompt"])
        self.assertIn("Do not store passwords", packet["subagent_prompt"])

    def test_m4_dispatch_packets_include_analysis_handoff_inputs(self) -> None:
        for rel_path in (
            "knowledge/handoff_M3_M4.md",
            "knowledge/M1/M1_source_log.yaml",
            "knowledge/M2/M2_source_log.yaml",
            "knowledge/M2/M2S05_experiment_setup.md",
            "knowledge/M2/M2S06_full_experiment_plan.md",
            "knowledge/M3/M3S04_result_validation.md",
            "knowledge/M4/M4S01_other_findings.md",
            "knowledge/M4/M4S02_analysis_experiment_design.md",
        ):
            path = self.root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {path.name}\n", encoding="utf-8")

        m4s02 = build_stage_execution_packet(self.root, "M4S02")
        m4s03 = build_stage_execution_packet(self.root, "M4S03")

        self.assertEqual(m4s02["role"], "analysis")
        self.assertTrue(any(path.endswith("knowledge/handoff_M3_M4.md") for path in m4s02["input_docs"]))
        self.assertTrue(any(path.endswith("knowledge/M2/M2S06_full_experiment_plan.md") for path in m4s02["input_docs"]))
        self.assertTrue(any(path.endswith("knowledge/M1/M1_source_log.yaml") for path in m4s02["input_docs"]))
        self.assertTrue(any(path.endswith("knowledge/M2/M2_source_log.yaml") for path in m4s02["input_docs"]))
        self.assertTrue(any(path.endswith("state/survey_memory.yaml") for path in m4s02["input_docs"]))

        self.assertEqual(m4s03["role"], "experiment")
        self.assertTrue(any(path.endswith("knowledge/handoff_M3_M4.md") for path in m4s03["input_docs"]))
        self.assertTrue(any(path.endswith("knowledge/M3/M3S04_result_validation.md") for path in m4s03["input_docs"]))

    def test_m2_stage_review_packet_has_canonical_output(self) -> None:
        packets = build_stage_review_packets(self.root, "M2S01")

        self.assertEqual(len(packets), 1)
        packet = packets[0]
        self.assertEqual(packet["role"], "m2_search_quality")
        self.assertTrue(packet["output_path"].endswith("knowledge/reviews/M2S01_search_quality_review.md"))
        self.assertTrue(packet["subject_output"].endswith("knowledge/M2/M2S01_cross_domain_search.md"))

    def test_gate_review_packet_includes_rubric_block(self) -> None:
        packets = build_packets(self.root, "gate", "G2")

        self.assertGreaterEqual(len(packets), 1)
        packet = packets[0]
        self.assertEqual(packet["task_type"], "gate_review")
        self.assertEqual(packet["gate_id"], "G2")
        self.assertIn("Gate rubric: G2", packet["gate_rubric"])
        self.assertIn("G2-R1", packet["subagent_prompt"])
        self.assertIn("Rubric Results", packet["subagent_prompt"])

    def test_m1s02_review_dispatch_creates_three_round_packets(self) -> None:
        packets = build_stage_review_packets(self.root, "M1S02")

        self.assertEqual([packet["round"] for packet in packets], [1, 2, 3])
        self.assertTrue(packets[0]["output_path"].endswith("knowledge/reviews/M1S02_round1_review.md"))
        self.assertTrue(packets[2]["output_path"].endswith("knowledge/reviews/M1S02_round3_review.md"))

    def test_m6s01_review_dispatch_includes_internal_peer_review(self) -> None:
        packets = build_stage_review_packets(self.root, "M6S01")

        roles = [packet["role"] for packet in packets]
        self.assertEqual(roles, ["m6_internal_peer_review", "m6_submission_audit"])
        internal = packets[0]
        self.assertTrue(internal["agent_md"].endswith("docs/AGENTS/critic/m6_internal_peer_review/AGENT.md"))
        self.assertTrue(internal["output_path"].endswith("knowledge/reviews/M6S01_internal_peer_review.md"))
        self.assertTrue(any(path.endswith("artifacts/paper.pdf") for path in internal["input_docs"]))

    def test_m2_stage_gate_requires_stage_review(self) -> None:
        ok, messages = check_stage(self.root, "M2S01")

        self.assertFalse(ok)
        self.assertTrue(any("required stage review missing" in message for message in messages))

    def test_m2s01_stage_gate_accepts_valid_search_provenance(self) -> None:
        (self.root / "knowledge" / "reviews" / "M2S01_search_quality_review.md").write_text(
            "# M2S01 Search Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )

        ok, messages = check_stage(self.root, "M2S01")

        self.assertTrue(ok, messages)
        self.assertTrue(any("M2 search_statistics records total_queries" in message for message in messages))

    def test_m2s01_stage_gate_blocks_missing_search_statistics(self) -> None:
        (self.root / "knowledge" / "reviews" / "M2S01_search_quality_review.md").write_text(
            "# M2S01 Search Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )
        source_log = _valid_m2_source_log()
        source_log.pop("search_statistics")
        (self.root / "knowledge" / "M2" / "M2_source_log.yaml").write_text(
            yaml.safe_dump(source_log, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        ok, messages = check_stage(self.root, "M2S01")

        self.assertFalse(ok)
        self.assertTrue(any("M2 search_statistics missing" in message for message in messages), messages)

    def test_m2s05_stage_review_packet_has_canonical_output(self) -> None:
        packets = build_stage_review_packets(self.root, "M2S05")

        self.assertEqual(len(packets), 1)
        packet = packets[0]
        self.assertEqual(packet["role"], "m2_experiment_design_review")
        self.assertTrue(packet["agent_md"].endswith("docs/AGENTS/critic/m2_experiment_design_review/AGENT.md"))
        self.assertTrue(packet["output_path"].endswith("knowledge/reviews/M2S05_experiment_design_review.md"))
        self.assertTrue(packet["subject_output"].endswith("knowledge/M2/M2S05_experiment_setup.md"))

    def test_m2s06_stage_review_packet_has_canonical_output(self) -> None:
        packets = build_stage_review_packets(self.root, "M2S06")

        self.assertEqual(len(packets), 1)
        packet = packets[0]
        self.assertEqual(packet["role"], "m2_experiment_plan_review")
        self.assertTrue(packet["agent_md"].endswith("docs/AGENTS/critic/m2_experiment_plan_review/AGENT.md"))
        self.assertTrue(packet["output_path"].endswith("knowledge/reviews/M2S06_experiment_plan_review.md"))
        self.assertTrue(packet["subject_output"].endswith("knowledge/M2/M2S06_full_experiment_plan.md"))

    def _write_pass_review(self, rel_path: str) -> None:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Review\n\n## Verdict\nVerdict: PASS\n", encoding="utf-8")

    def _write_valid_m2s05(self) -> None:
        (self.root / "knowledge" / "M2" / "M2S05_experiment_setup.md").write_text(
            "# M2S05 Experiment Setup\n\n"
            "## Dataset Selection\n\n"
            "| 数据集 | 规模 | 任务类型 | 选择理由 | 获取方式 | 许可证 |\n"
            "|---|---|---|---|---|---|\n"
            "| DemoSet | 1GB | classification | matches the gap | download URL with checksum 校验 | CC-BY |\n\n"
            "## Baseline Methods\n"
            "Baseline fairness uses 相同的数据划分, 相同的评估指标, same split, same training budget.\n\n"
            "## 相关工作实验设置\n"
            "Reference protocol from PaperX maps dataset, baseline, metric, and protocol to this project.\n\n"
            "## Experiment Targets\n"
            "| 实验 ID | 目的 | 目标假设 | 验证内容 | 对照组 | 指标 | 必需/可选 |\n"
            "|---|---|---|---|---|---|---|\n"
            "| Exp-1 | main purpose | H1 | main comparison | baseline | accuracy metric | 必需 |\n"
            "| Exp-2 | component purpose | H2 | component check | baseline | accuracy metric | 必需 |\n"
            "| Exp-3 | robustness purpose | H3 | robustness | baseline | accuracy metric | 可选 |\n\n"
            "随机种子 seed: 42. 单次固定 seed 实验。 "
            "可复现 reproducibility requirements include git commit and environment lock.\n",
            encoding="utf-8",
        )
        (self.root / "knowledge" / "M2" / "M2S05_metric_protocol.yaml").write_text(
            "schema_version: 1\n"
            "metric_protocols:\n"
            "  - metric_protocol_id: mp_demo_accuracy\n"
            "    dataset: DemoSet\n"
            "    scenario: classification\n"
            "    split: test\n"
            "    metric_key: accuracy\n"
            "    definition: fraction of correct labels\n"
            "    calculation: correct / total over the test split\n"
            "    direction: higher_is_better\n"
            "    value_range: [0.0, 1.0]\n"
            "    normal_reference_range: [0.5, 0.95]\n"
            "    protocol_source:\n"
            "      source_id: PaperX\n"
            "      table_or_section: Table 1\n"
            "      rationale: standard classification metric for DemoSet\n"
            "    metric_sanity_check:\n"
            "      test_case: two correct out of four examples\n"
            "      expected_value: 0.5\n"
            "      tolerance: 1.0e-6\n",
            encoding="utf-8",
        )

    def _write_valid_m2s06(self) -> None:
        (self.root / "knowledge" / "M2" / "M2S06_full_experiment_plan.md").write_text(
            "# M2S06 Full Experiment Plan\n\n"
            "## 1. 计划总览\n\n"
            "| 阶段 | 实验 ID | 目的 | 预估时间 | 依赖 | 优先级 |\n"
            "|---|---|---|---|---|---|\n"
            "| 1 | Exp-1 | main purpose | 2h | none | P0 |\n"
            "| 2 | Exp-2 | component purpose | 1h | Exp-1 | P0 |\n"
            "| 3 | Exp-3 | robustness purpose | 1h | Exp-1 | P1 |\n\n"
            "## 2. 执行顺序与分支逻辑\n"
            "Phase 1 -> Phase 2. If failure, BACKTRACK 回溯 after 失败判定 and 诊断.\n\n"
            "## 3. 成功/失败判定标准\n"
            "成功标准 success criteria: significant improvement. failure diagnosis covers implementation, design, hypothesis, data, baseline.\n\n"
            "## 4. 风险与应对\n"
            "风险 risk control and 应对 measures.\n\n"
            "## 5. 资源预算\n"
            "资源 GPU storage 时间预算 budget.\n\n"
            "## 7. 完整实验报告蓝图\n\n"
            "### Exp-[N]: template\n"
            "- 目的: ...\n"
            "- 对应假设 / Gap: ...\n"
            "- 参考相关工作实验设置: PaperX reference protocol 论文\n"
            "- 数据集与划分: DemoSet dataset split\n"
            "- Baselines / 对照组: baseline\n"
            "- 评价指标: metric_protocol_id=mp_demo_accuracy accuracy metric\n"
            "- 运行协议: seed=42 epoch hardware 超参\n"
            "- 预期结果形态: table plot\n"
            "- 成功标准: ...\n"
            "- 失败时诊断路径: implementation / design / hypothesis / data / baseline\n"
            "- 需要保存的证据: raw logs, config, checkpoint, results.tsv, plot script\n",
            encoding="utf-8",
        )

    def test_m2s05_stage_gate_blocks_incomplete_experiment_design(self) -> None:
        (self.root / "knowledge" / "M2" / "M2S05_experiment_setup.md").write_text(
            "# M2S05\n\nBaseline and metric only.\n",
            encoding="utf-8",
        )

        ok, messages = check_stage(self.root, "M2S05")

        self.assertFalse(ok)
        self.assertTrue(any("missing dataset acquisition" in message for message in messages))
        self.assertTrue(any("required stage review missing" in message for message in messages))

    def test_m2s05_stage_gate_accepts_complete_design_with_pass_review(self) -> None:
        self._write_valid_m2s05()
        self._write_pass_review("knowledge/reviews/M2S05_experiment_design_review.md")

        ok, messages = check_stage(self.root, "M2S05")

        self.assertTrue(ok, "\n".join(messages))
        self.assertTrue(any("3 experiment IDs found" in message for message in messages))
        self.assertTrue(any("m2_experiment_design_review PASS" in message for message in messages))

    def test_m2s05_stage_gate_requires_metric_protocol_registry(self) -> None:
        self._write_valid_m2s05()
        (self.root / "knowledge" / "M2" / "M2S05_metric_protocol.yaml").unlink()
        self._write_pass_review("knowledge/reviews/M2S05_experiment_design_review.md")

        ok, messages = check_stage(self.root, "M2S05")

        self.assertFalse(ok)
        self.assertTrue(any("metric protocol registry not found" in message for message in messages), messages)

    def test_m2s06_stage_gate_blocks_incomplete_full_plan(self) -> None:
        (self.root / "knowledge" / "M2" / "M2S06_full_experiment_plan.md").write_text(
            "# M2S06\n\nExp-1 only.\n",
            encoding="utf-8",
        )

        ok, messages = check_stage(self.root, "M2S06")

        self.assertFalse(ok)
        self.assertTrue(any("fewer than 3 experiment IDs" in message for message in messages))
        self.assertTrue(any("missing full experiment report blueprint" in message for message in messages))
        self.assertTrue(any("required stage review missing" in message for message in messages))

    def test_m2s06_stage_gate_accepts_full_plan_with_pass_review(self) -> None:
        self._write_valid_m2s05()
        self._write_valid_m2s06()
        self._write_pass_review("knowledge/reviews/M2S06_experiment_plan_review.md")

        ok, messages = check_stage(self.root, "M2S06")

        self.assertTrue(ok, "\n".join(messages))
        self.assertTrue(any("3 experiment IDs found" in message for message in messages))
        self.assertTrue(any("m2_experiment_plan_review PASS" in message for message in messages))

    def _write_m6s01_gate_files(self, score: str = "8.2", high: str = "0") -> None:
        (self.root / "artifacts").mkdir(parents=True, exist_ok=True)
        (self.root / "knowledge" / "handoff_M5_completion.md").write_text("# handoff", encoding="utf-8")
        (self.root / "artifacts" / "paper.pdf").write_text("pdf", encoding="utf-8")
        (self.root / "artifacts" / "paper.tex").write_text("tex", encoding="utf-8")
        (self.root / "knowledge" / "M6" / "M6S01_submission_audit.md").write_text(
            "# M6S01\n\n"
            "## Integrity Audit\n"
            "## Venue Compliance\n"
            "## Audit Conclusion\n"
            "- READY\n"
            "- Blockers: []\n"
            "- Warnings: []\n",
            encoding="utf-8",
        )
        (self.root / "knowledge" / "reviews" / "M6S01_internal_peer_review.md").write_text(
            "# M6S01 Internal Peer Review\n\n"
            "## Reviewer A\n"
            "### Overall Score: 8/10\n"
            "## Reviewer B\n"
            "### Overall Score: 8/10\n"
            "## Reviewer C\n"
            "### Overall Score: 8/10\n\n"
            "## Aggregate Score\n"
            f"- **Internal Review Score**: {score}/10\n"
            f"- **Unresolved high-priority issues**: {high}\n\n"
            "## Revision Loop Decision\n"
            "- Continue internal revision loop: no\n"
            "- Accept/Revert note: accept current version\n\n"
            "## Verdict\n"
            "Verdict: PASS\n",
            encoding="utf-8",
        )
        (self.root / "knowledge" / "reviews" / "M6S01_submission_audit_review.md").write_text(
            "# M6S01 Submission Audit Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )

    def test_m6s01_stage_gate_requires_internal_review_score_8(self) -> None:
        self._write_m6s01_gate_files(score="7.9", high="0")

        ok, messages = check_stage(self.root, "M6S01")

        self.assertFalse(ok)
        self.assertTrue(any("below required 8.0/10" in message for message in messages))

    def test_m6s01_stage_gate_accepts_internal_review_score_8(self) -> None:
        self._write_m6s01_gate_files(score="8.2", high="0")

        ok, messages = check_stage(self.root, "M6S01")

        self.assertTrue(ok, "\n".join(messages))
        self.assertTrue(any("meets required 8.0/10" in message for message in messages))

    def test_m6s05_dispatch_uses_revision_routing_not_conductor_output(self) -> None:
        state_path = self.root / "state" / "pipeline_state.yaml"
        state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        state["current"] = {"module": "M6", "stage": "M6S05", "status": "in_progress"}
        state["modules"]["M5"] = {"status": "completed", "completed_at": None, "last_stage": "M5S09"}
        state["modules"]["M6"] = {"status": "in_progress", "completed_at": None, "last_stage": "M6S04"}
        state_path.write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")

        action_plan = self.root / "knowledge" / "M6" / "M6S04_action_plan.md"
        action_plan.write_text(
            "# Action Plan\n\n"
            "### PR-A1\n"
            "- **class**: evidence_gap\n"
            "- **severity**: High\n"
            "- **target_stage**: M4S02\n"
            "- **required_fix**: Add ablation design for component X\n"
            "- **success_criteria**: M4S02 includes an executable ablation slice\n"
            "- **rebuild_mode**: incremental_replay\n"
            "- **rerun_scope**: M4S02 -> M4S03 -> M4S04 -> M5S08 -> M5S09\n"
            "- **priority**: P0\n\n"
            "### PR-A2\n"
            "- **class**: text_only\n"
            "- **severity**: Medium\n"
            "- **target_stage**: M5S03\n"
            "- **required_fix**: Clarify motivation in introduction\n"
            "- **success_criteria**: M5S03 addresses reviewer confusion\n"
            "- **rebuild_mode**: incremental_replay\n"
            "- **rerun_scope**: M5S03 -> M5S07 -> M5S08 -> M5S09\n"
            "- **priority**: P1\n",
            encoding="utf-8",
        )
        (self.root / "knowledge" / "M6" / "M6S04_rebuttal_strategy.md").write_text("# strategy", encoding="utf-8")

        packet = build_stage_execution_packet(self.root, "M6S05")
        routing = packet["revision_routing"]

        self.assertEqual(packet["task_type"], "revision_routing")
        self.assertTrue(packet["delegation_required"])
        self.assertEqual(packet["role"], "revision")
        self.assertTrue(packet["agent_md"].endswith("docs/AGENTS/revision/AGENT.md"))
        self.assertTrue(packet["output_path"].endswith("knowledge/M6/M6S05_revision_execution.md"))
        self.assertEqual(routing["earliest_target_stage"], "M4S02")
        self.assertEqual(
            [(route["target_stage"], route["responsible_agent"]) for route in routing["routes"]],
            [("M4S02", "analysis"), ("M5S03", "writing")],
        )
        self.assertIn("stage_backtrack_advice", routing)
        self.assertEqual(routing["stage_backtrack_advice"]["M4S02"]["direct_item_ids"], ["PR-A1"])
        self.assertEqual(routing["stage_backtrack_advice"]["M5S03"]["direct_item_ids"], ["PR-A2"])
        self.assertIn("PR-A1", routing["stage_backtrack_advice"]["M4S03"]["downstream_item_ids"])
        self.assertIn("stage_backtrack_advice", packet["subagent_prompt"])
        self.assertNotEqual(packet["role"], "conductor_routed")

    def test_m6s05_dispatch_scope_uses_revision_packet(self) -> None:
        packets = build_packets(self.root, "stage", "M6S05")

        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0]["task_type"], "revision_routing")

    def test_m6_routing_backtrack_persists_item_level_stage_advice(self) -> None:
        state_path = self.root / "state" / "pipeline_state.yaml"
        state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        state["current"] = {"module": "M6", "stage": "M6S05", "status": "in_progress"}
        state["modules"]["M4"] = {"status": "completed", "completed_at": None, "last_stage": "M4S04"}
        state["modules"]["M5"] = {"status": "completed", "completed_at": None, "last_stage": "M5S09"}
        state["modules"]["M6"] = {"status": "in_progress", "completed_at": None, "last_stage": "M6S04"}
        state_path.write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")

        action_plan = self.root / "knowledge" / "M6" / "M6S04_action_plan.md"
        action_plan.write_text(
            "# Action Plan\n\n"
            "### PR-A1\n"
            "- **class**: evidence_gap\n"
            "- **severity**: High\n"
            "- **target_stage**: M4S02\n"
            "- **required_fix**: Add ablation design for component X\n"
            "- **success_criteria**: M4S02 includes an executable ablation slice\n"
            "- **evidence_paths**: knowledge/M6/M6S03_review_matrix.md\n"
            "- **rebuild_mode**: incremental_replay\n"
            "- **rerun_scope**: M4S02 -> M4S03 -> M4S04 -> M5S08 -> M5S09\n"
            "- **handoff_updates**: knowledge/handoff_M4_M5.md\n"
            "- **priority**: P0\n\n"
            "### PR-A2\n"
            "- **class**: text_only\n"
            "- **severity**: Medium\n"
            "- **target_stage**: M5S03\n"
            "- **required_fix**: Clarify motivation in introduction\n"
            "- **success_criteria**: M5S03 addresses reviewer confusion\n"
            "- **rebuild_mode**: incremental_replay\n"
            "- **rerun_scope**: M5S03 -> M5S07 -> M5S08 -> M5S09\n"
            "- **priority**: P1\n",
            encoding="utf-8",
        )
        (self.root / "knowledge" / "M6" / "M6S03_review_matrix.md").write_text("# matrix", encoding="utf-8")
        (self.root / "knowledge" / "M6" / "M6S03_review_parsing.md").write_text("# parsing", encoding="utf-8")

        routing = build_revision_routes(self.root)
        result = Conductor(self.root).backtrack_from_revision_routing(routing)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["to"], "M4S02")

        saved = PipelineState(self.root)
        advice_map = saved.get_stage_backtrack_advice_map()
        self.assertIn("M4S02", advice_map)
        self.assertIn("M4S03", advice_map)
        self.assertIn("M5S03", advice_map)
        self.assertIn("M5S09", advice_map)
        self.assertIn("M5S08", advice_map)
        self.assertEqual(advice_map["M4S02"]["direct_item_ids"], ["PR-A1"])
        self.assertEqual(advice_map["M4S03"]["downstream_item_ids"], ["PR-A1"])
        self.assertEqual(advice_map["M5S03"]["direct_item_ids"], ["PR-A2"])
        self.assertEqual(set(advice_map["M5S08"]["downstream_item_ids"]), {"PR-A1", "PR-A2"})
        self.assertEqual(set(advice_map["M5S09"]["downstream_item_ids"]), {"PR-A1", "PR-A2"})

        packet = build_stage_execution_packet(self.root, "M5S08")
        packet_advice = packet["backtrack_advice"]
        self.assertEqual(set(packet_advice["m6_action_item_ids"]), {"PR-A1", "PR-A2"})
        self.assertIn("Downstream revalidation for PR-A1", packet_advice["required_fix"])
        self.assertIn("Downstream revalidation for PR-A2", packet_advice["required_fix"])


if __name__ == "__main__":
    unittest.main()
