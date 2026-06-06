#!/usr/bin/env python3
"""Integration tests for M4 module (Deep Analysis)."""

from __future__ import annotations

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from spiral.project import ProjectManager, MODULE_STAGES
from spiral.state import PipelineState
from spiral.conductor import Conductor
from utils.file_guard import (
    get_canonical_output_path,
    validate_stage_output,
    check_single_file_principle,
)
from utils.stage_gate import check_stage


class TestM4FileGuard(unittest.TestCase):
    """Test file_guard canonical paths for M4 stages."""

    def test_m4s01_canonical_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            proj.mkdir()
            path = get_canonical_output_path(proj, "M4S01")
            expected = proj / "knowledge" / "M4" / "M4S01_other_findings.md"
            assert path == expected, f"Expected {expected}, got {path}"
            print("  [PASS] M4S01 canonical path")

    def test_m4s02_canonical_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            proj.mkdir()
            path = get_canonical_output_path(proj, "M4S02")
            expected = proj / "knowledge" / "M4" / "M4S02_analysis_experiment_design.md"
            assert path == expected, f"Expected {expected}, got {path}"
            print("  [PASS] M4S02 canonical path")

    def test_m4s03_canonical_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            proj.mkdir()
            path = get_canonical_output_path(proj, "M4S03")
            expected = proj / "knowledge" / "M4" / "M4S03_analysis_experiment.md"
            assert path == expected, f"Expected {expected}, got {path}"
            print("  [PASS] M4S03 canonical path")

    def test_m4s04_canonical_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            proj.mkdir()
            path = get_canonical_output_path(proj, "M4S04")
            expected = proj / "knowledge" / "M4" / "M4S04_analysis_results.md"
            assert path == expected, f"Expected {expected}, got {path}"
            print("  [PASS] M4S04 canonical path")

    def test_m4s01_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            (proj / "knowledge" / "M4").mkdir(parents=True)
            out = proj / "knowledge" / "M4" / "M4S01_other_findings.md"
            out.write_text("# test")
            ok, msg = validate_stage_output(proj, "M4S01", out)
            assert ok, f"Expected OK, got: {msg}"
            print("  [PASS] M4S01 file_guard validation")

    def test_m4s02_rejects_alternate_stage_output_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            (proj / "knowledge" / "M4").mkdir(parents=True)
            (proj / "knowledge" / "M4" / "M4S02_analysis_experiment_design.md").write_text("# canonical")
            (proj / "knowledge" / "M4" / "M4S02_analysis_experiment_design_revised.md").write_text("# copy")

            ok, msg = check_single_file_principle(proj, "M4S02")

            assert not ok, "Expected alternate stage output copy to be rejected"
            assert "canonical original file in place" in msg


class TestM4Conductor(unittest.TestCase):
    """Test Conductor M4 stage checker configuration."""

    def test_m4_stage_checkers(self):
        from spiral.conductor import STAGE_CHECKERS
        assert "M4S01" in STAGE_CHECKERS, "M4S01 missing from STAGE_CHECKERS"
        assert "M4S02" in STAGE_CHECKERS, "M4S02 missing from STAGE_CHECKERS"
        assert "M4S03" in STAGE_CHECKERS, "M4S03 missing from STAGE_CHECKERS"
        assert STAGE_CHECKERS["M4S01"] == ["m4_findings_audit"]
        assert STAGE_CHECKERS["M4S02"] == ["m4_analysis_design_review", "m4_execution_readiness_review"]
        assert STAGE_CHECKERS["M4S03"] == ["m4_analysis_execution_review"]
        # Ensure old M3 code_review is not bound to M4
        assert "code_review" not in STAGE_CHECKERS.get("M4S02", [])
        print("  [PASS] M4 stage checkers configured correctly")

    def test_m4_checker_md_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            proj.mkdir()
            cond = Conductor(proj)
            p1 = cond.get_checker_md_path("m4_findings_audit")
            p2 = cond.get_checker_md_path("m4_analysis_design_review")
            p3 = cond.get_checker_md_path("m4_execution_readiness_review")
            p4 = cond.get_checker_md_path("m4_analysis_execution_review")
            assert "m4_findings_audit" in str(p1)
            assert "m4_analysis_design_review" in str(p2)
            assert "m4_execution_readiness_review" in str(p3)
            assert "m4_analysis_execution_review" in str(p4)
            print("  [PASS] M4 checker md paths resolve correctly")

    def test_m4_module_stages(self):
        stages = MODULE_STAGES.get("M4", [])
        assert stages == ["M4S01", "M4S02", "M4S03", "M4S04"], f"Unexpected M4 stages: {stages}"
        print("  [PASS] M4 module stages defined correctly")


class TestM4StageGate(unittest.TestCase):
    def _write_m4s02_project(self, root: Path, *, complete: bool = True, include_task_queue: bool = True) -> None:
        for rel in ("knowledge/M4", "knowledge/reviews", "experiments/configs"):
            (root / rel).mkdir(parents=True, exist_ok=True)
        if complete:
            text = (
                "# M4S02 Deep Analysis Experiment Design\n\n"
                "## 分析目标\n"
                "How: test how the component drives the gain. Where: test scenario boundaries and where it works. "
                "Why: test why the mechanism explains the improvement. Upstream basis: M3S01, M3S05, handoff_M3_M4.\n\n"
                "## Component Claim Analysis Matrix\n"
                "| Component / Claim | Required Evidence | Planned Slice IDs | Missing Evidence / Waiver |\n"
                "|---|---|---|---|\n"
                "| C1 / component | ablation, mechanism, robustness | Ana-1, Ana-2, Ana-3 | efficiency_required: no because no extra compute claim |\n\n"
                "## Paper Protocol Adaptation Table\n"
                "| reference_paper / source_id | task_setup | metric | baseline_protocol | transferable_part | adopted_for_slice | adoption_decision |\n"
                "|---|---|---|---|---|---|---|\n"
                "| PaperX | diagnostic task | accuracy | active baseline same seed | ablation protocol | Ana-1 | adopted |\n\n"
                "## Slice 列表\n"
                "### Slice: Ana-1\n"
                "- analysis_type: ablation 消融\n"
                "- comparison_target: full model and active baseline\n"
                "- baseline_inclusion: required\n"
                "- efficiency_required: no\n"
                "- literature_basis: PaperX / M3S01 main experiment protocol\n"
                "- paper_protocol_adaptation: PaperX task_setup metric baseline_protocol adopted for Ana-1\n"
                "- expected_pattern: full > w/o component\n"
                "- evidence_criteria: 3 seeds, effect size, confidence interval\n"
                "- claim_links: C1\n\n"
                "### Slice: Ana-2\n"
                "- analysis_type: mechanism 机制\n"
                "- comparison_target: baseline probe\n"
                "- baseline_inclusion: required\n"
                "- efficiency_required: no\n"
                "- literature_basis: PaperY visualization protocol\n"
                "- paper_protocol_adaptation: PaperY visualization protocol adopted for Ana-2\n"
                "- expected_pattern: ours alignment score higher\n"
                "- evidence_criteria: quantitative probe plus figure\n"
                "- claim_links: C2\n\n"
                "### Slice: Ana-3\n"
                "- analysis_type: robustness 鲁棒\n"
                "- comparison_target: active baseline under same perturbation\n"
                "- baseline_inclusion: required\n"
                "- efficiency_required: no\n"
                "- literature_basis: PaperZ robustness setup\n"
                "- paper_protocol_adaptation: PaperZ robustness protocol adopted for Ana-3\n"
                "- expected_pattern: ours remains stable under mild noise\n"
                "- evidence_criteria: same split, same seeds, confidence interval\n"
                "- claim_links: C3\n\n"
                "### Slice: Ana-4\n"
                "- analysis_type: failure negative 失败 负面\n"
                "- comparison_target: boundary cases\n"
                "- baseline_inclusion: optional\n"
                "- efficiency_required: no\n"
                "- literature_basis: negative-result audit\n"
                "- paper_protocol_adaptation: negative-result audit adopted for Ana-4\n"
                "- expected_pattern: failures documented honestly\n"
                "- evidence_criteria: taxonomy and examples\n"
                "- claim_links: C4\n\n"
                "## Comparability Contract\n"
                "baseline and ours use the same split, seed, metric, and preprocessing.\n\n"
                "## 执行信封审计\n"
                "Ana-1 to Ana-4 are feasible within the resource budget.\n"
            )
        else:
            text = (
                "# M4S02 Deep Analysis Experiment Design\n\n"
                "## 分析目标\n"
                "Analyze results generally.\n\n"
                "## Slice 列表\n"
                "analysis_type: ablation; baseline_inclusion: optional; literature_basis: PaperX; evidence_criteria: metric.\n\n"
                "## Comparability Contract\n"
                "baseline maybe.\n\n"
                "## 执行信封审计\n"
                "feasible.\n"
            )
        (root / "knowledge" / "M4" / "M4S02_analysis_experiment_design.md").write_text(text, encoding="utf-8")
        (root / "knowledge" / "reviews" / "M4S02_analysis_design_review.md").write_text(
            "# M4S02 Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )
        (root / "knowledge" / "reviews" / "M4S02_execution_readiness_review.md").write_text(
            "# M4S02 Execution Readiness Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )
        if complete and include_task_queue:
            task_block = ""
            for ana_id, analysis_type, baseline_required in (
                ("Ana-1", "ablation", True),
                ("Ana-2", "mechanism", True),
                ("Ana-3", "robustness", True),
                ("Ana-4", "failure", False),
            ):
                task_block += (
                    f"  - task_id: {ana_id}\n"
                    f"    analysis_type: {analysis_type}\n"
                    f"    command: python experiments/src/run_analysis.py --slice {ana_id}\n"
                    "    dependencies: []\n"
                    "    parallelizable: true\n"
                    "    resource_requirements:\n"
                    "      min_gpu_count: 0\n"
                    "      min_cpu_cores: 2\n"
                    "      memory_gb: 8\n"
                    "      expected_minutes: 30\n"
                    f"    baseline_inclusion: {'required' if baseline_required else 'optional'}\n"
                    f"    fairness_key: {ana_id}_same_split_seed_metric_resource_class\n"
                    "    expected_artifacts:\n"
                    f"      - experiments/artifacts/analysis_experiment/{ana_id}/manifest.yaml\n"
                    "    success_criteria:\n"
                    f"      - analysis_results.tsv contains {ana_id} rows\n"
                )
            (root / "experiments" / "configs" / "m4_task_queue.yaml").write_text(
                "schema_version: 1\n"
                "stage: M4S03\n"
                "tasks:\n"
                f"{task_block}",
                encoding="utf-8",
            )

    def _write_m4s03_project(self, root: Path, *, include_sandbox_record: bool = True) -> None:
        for rel in (
            "knowledge/M4",
            "knowledge/reviews",
            "config",
            "experiments/configs",
            "experiments/runs/analysis_1/logs",
            "experiments/artifacts/analysis_experiment",
        ):
            (root / rel).mkdir(parents=True, exist_ok=True)
        (root / "config" / "execution_env.yaml").write_text(
            "execution:\n"
            "  mode: local\n"
            "  sandbox:\n"
            "    enabled: true\n"
            "    mode: venv\n"
            "    network_policy: restricted\n"
            "    filesystem_policy:\n"
            "      allowed_write_paths:\n"
            "        - experiments/runs/\n"
            "        - experiments/logs/\n"
            "        - experiments/artifacts/\n"
            "        - artifacts/\n"
            "      denied_paths:\n"
            "        - ~/.ssh/\n"
            "        - /etc/\n"
            "    secrets_policy:\n"
            "      allow_env_secrets: false\n"
            "      allow_ssh_key_read: false\n"
            "      redact_logs: true\n"
            "    resource_limits:\n"
            "      timeout_hours: 24\n"
            "      max_cpu_cores: 4\n"
            "      max_memory_gb: 16\n"
            "      max_gpu_count: 0\n"
            "    reproducibility:\n"
            "      requirements_lock: experiments/requirements.lock\n"
            "      image: ''\n"
            "      image_digest: ''\n"
            "      seed_policy: fixed_multi_seed\n"
            "  local:\n"
            "    env_manager: venv\n"
            "    python_version: '3.11'\n",
            encoding="utf-8",
        )
        (root / "experiments" / "configs" / "sandbox_profile.yaml").write_text(
            "sandbox:\n"
            "  enabled: true\n"
            "  mode: venv\n"
            "  network_policy: restricted\n"
            "  filesystem_policy:\n"
            "    allowed_write_paths:\n"
            "      - experiments/runs/\n"
            "      - experiments/logs/\n"
            "      - experiments/artifacts/\n"
            "      - artifacts/\n"
            "    denied_paths:\n"
            "      - ~/.ssh/\n"
            "      - /etc/\n"
            "  secrets_policy:\n"
            "    allow_env_secrets: false\n"
            "    allow_ssh_key_read: false\n"
            "    redact_logs: true\n"
            "  resource_limits:\n"
            "    timeout_hours: 24\n"
            "    max_cpu_cores: 4\n"
            "    max_memory_gb: 16\n"
            "    max_gpu_count: 0\n"
            "  reproducibility:\n"
            "    requirements_lock: experiments/requirements.lock\n"
            "    image: ''\n"
            "    image_digest: ''\n"
            "    seed_policy: fixed_multi_seed\n",
            encoding="utf-8",
        )
        sandbox_record = (
            "\n## Sandbox / Container Execution Record\n"
            "Ana-1 sandbox mode venv; command `python analysis.py`; working dir experiments; "
            "allowed writes experiments/runs/; network policy restricted; resource limits timeout=24h cpu=4 gpu=0; "
            "log path experiments/runs/analysis_1/logs/run.log; sandbox_profile experiments/configs/sandbox_profile.yaml.\n"
            if include_sandbox_record else ""
        )
        (root / "knowledge" / "M4" / "M4S03_analysis_experiment.md").write_text(
            "# M4S03\n\n"
            "## 执行摘要\nok\n"
            "## Slice 执行记录\nok\n"
            "## 负面/失败结果记录\nfailed case\n"
            "## 原始数据与日志\nlogs\n"
            f"{sandbox_record}\n"
            "## 初步审查摘要\nstage_in_fix continue; abnormal cause: environment setup model data metric method unknown.\n",
            encoding="utf-8",
        )
        task_block = ""
        for ana_id, analysis_type, baseline_required in (
            ("Ana-1", "ablation", True),
            ("Ana-2", "mechanism", True),
            ("Ana-3", "robustness", True),
            ("Ana-4", "failure", False),
        ):
            task_block += (
                f"  - task_id: {ana_id}\n"
                f"    analysis_type: {analysis_type}\n"
                f"    command: python experiments/src/run_analysis.py --slice {ana_id}\n"
                "    dependencies: []\n"
                "    resource_requirements:\n"
                "      min_gpu_count: 0\n"
                "      min_cpu_cores: 2\n"
                f"    baseline_inclusion: {'required' if baseline_required else 'optional'}\n"
                f"    fairness_key: {ana_id}_same_split_seed_metric_resource_class\n"
                "    expected_artifacts:\n"
                f"      - experiments/artifacts/analysis_experiment/{ana_id}/manifest.yaml\n"
                "    success_criteria:\n"
                f"      - analysis_results.tsv contains {ana_id} rows\n"
            )
        (root / "experiments" / "configs" / "m4_task_queue.yaml").write_text(
            "schema_version: 1\n"
            "stage: M4S03\n"
            "tasks:\n"
            f"{task_block}",
            encoding="utf-8",
        )
        (root / "experiments" / "analysis_results.tsv").write_text(
            "slice\tanalysis_type\tmethod\tdataset\tsplit\tseed\tconfig_id\trun_id\tmetric\tvalue\tbaseline_inclusion\tartifact_path\truntime_sec\tparams_m\tpeak_mem_mb\tresource_id\tresource_kind\tserver_id\tgpu_ids\tresource_monitor\tnotes\n"
            "Ana-1\tablation\tbaseline\tds\ttest\t42\tcfg-b\trun-b\taccuracy_drop\t0.02\trequired\texperiments/artifacts/analysis_experiment/Ana-1\t120\t10.5\t2048\tlocal\tlocal\t\t[]\texperiments/runs/analysis_1/resource_monitor.csv\tbaseline\n"
            "Ana-1\tablation\tours\tds\ttest\t42\tcfg-a\trun-a\taccuracy_drop\t0.05\trequired\texperiments/artifacts/analysis_experiment/Ana-1\t120\t10.5\t2048\tlocal\tlocal\t\t[]\texperiments/runs/analysis_1/resource_monitor.csv\tok\n"
            "Ana-2\tmechanism\tbaseline\tds\ttest\t42\tcfg-b\trun-b\talignment_score\t0.40\trequired\texperiments/artifacts/analysis_experiment/Ana-2\t120\t10.5\t2048\tlocal\tlocal\t\t[]\texperiments/runs/analysis_1/resource_monitor.csv\tbaseline\n"
            "Ana-2\tmechanism\tours\tds\ttest\t42\tcfg-a\trun-a\talignment_score\t0.60\trequired\texperiments/artifacts/analysis_experiment/Ana-2\t120\t10.5\t2048\tlocal\tlocal\t\t[]\texperiments/runs/analysis_1/resource_monitor.csv\tok\n"
            "Ana-3\trobustness\tbaseline\tds\tnoise\t42\tcfg-b\trun-b\taccuracy_noise\t0.70\trequired\texperiments/artifacts/analysis_experiment/Ana-3\t120\t10.5\t2048\tlocal\tlocal\t\t[]\texperiments/runs/analysis_1/resource_monitor.csv\tbaseline\n"
            "Ana-3\trobustness\tours\tds\tnoise\t42\tcfg-a\trun-a\taccuracy_noise\t0.78\trequired\texperiments/artifacts/analysis_experiment/Ana-3\t120\t10.5\t2048\tlocal\tlocal\t\t[]\texperiments/runs/analysis_1/resource_monitor.csv\tok\n"
            "Ana-4\tfailure\tours\tds\tboundary\t42\tcfg-a\trun-a\tfailure_rate\t0.10\toptional\texperiments/artifacts/analysis_experiment/Ana-4\t120\t10.5\t2048\tlocal\tlocal\t\t[]\texperiments/runs/analysis_1/resource_monitor.csv\tok\n",
            encoding="utf-8",
        )
        (root / "knowledge" / "reviews" / "M4S03_analysis_execution_review.md").write_text(
            "# M4S03 Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )

    def test_m4s02_stage_gate_accepts_how_where_why_design(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m4s02_project(proj, complete=True)

            ok, messages = check_stage(proj, "M4S02")

            self.assertTrue(ok, "\n".join(messages))
            self.assertTrue(any("concrete Ana-* slice IDs found" in m for m in messages))
            self.assertTrue(any("includes expected pattern" in m for m in messages))
            self.assertTrue(any("m4_task_queue.yaml covers all design Ana-* ids" in m for m in messages), messages)

    def test_m4s02_stage_gate_requires_task_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m4s02_project(proj, complete=True, include_task_queue=False)

            ok, messages = check_stage(proj, "M4S02")

            self.assertFalse(ok)
            self.assertTrue(any("m4_task_queue.yaml not found" in m for m in messages), messages)

    def test_m4s02_stage_gate_blocks_shallow_design(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m4s02_project(proj, complete=False)

            ok, messages = check_stage(proj, "M4S02")

            self.assertFalse(ok)
            self.assertTrue(any("missing how target" in m for m in messages), messages)
            self.assertTrue(any("fewer than 3 concrete Ana-* slice IDs" in m for m in messages), messages)

    def test_m4s02_stage_gate_blocks_required_efficiency_without_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m4s02_project(proj, complete=True)
            doc = proj / "knowledge" / "M4" / "M4S02_analysis_experiment_design.md"
            text = doc.read_text(encoding="utf-8").replace("efficiency_required: no", "efficiency_required: yes")
            doc.write_text(text, encoding="utf-8")

            ok, messages = check_stage(proj, "M4S02")

            self.assertFalse(ok)
            self.assertTrue(any("efficiency metrics missing" in m for m in messages), messages)

    def test_m4s03_stage_gate_accepts_sandbox_execution_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m4s03_project(proj, include_sandbox_record=True)

            ok, messages = check_stage(proj, "M4S03")

            self.assertTrue(ok, "\n".join(messages))
            self.assertTrue(any("sandbox/container execution record present" in m for m in messages))
            self.assertTrue(any("analysis_results.tsv covers all task_queue slices" in m for m in messages), messages)

    def test_m4s03_stage_gate_requires_sandbox_execution_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m4s03_project(proj, include_sandbox_record=False)

            ok, messages = check_stage(proj, "M4S03")

            self.assertFalse(ok)
            self.assertTrue(any("sandbox/container execution record missing" in m for m in messages))

    def test_m4s03_stage_gate_blocks_missing_task_queue_slice(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m4s03_project(proj, include_sandbox_record=True)
            results = proj / "experiments" / "analysis_results.tsv"
            filtered = "\n".join(
                line
                for line in results.read_text(encoding="utf-8").splitlines()
                if not line.startswith("Ana-3\t")
            ) + "\n"
            results.write_text(filtered, encoding="utf-8")

            ok, messages = check_stage(proj, "M4S03")

            self.assertFalse(ok)
            self.assertTrue(any("missing task_queue slices: Ana-3" in m for m in messages), messages)

    def _write_m4s04_project(
        self,
        root: Path,
        *,
        include_artifacts: bool = True,
        include_handoff: bool = True,
        unsupported_main_text: bool = False,
        include_baseline_rows: bool = True,
    ) -> None:
        for rel in ("knowledge/M4", "experiments/artifacts/analysis_experiment/figures"):
            (root / rel).mkdir(parents=True, exist_ok=True)
        c4_role = "main_text" if unsupported_main_text else "removed"
        (root / "knowledge" / "M4" / "M4S04_analysis_results.md").write_text(
            "# M4S04 Analysis Results\n\n"
            "## 统计分析\n"
            "Ablation, mechanism, robustness, and failure analysis include p-value=0.02, 效应量=0.8, 95% 置信区间, and baseline 基线 对照.\n\n"
            "## Claim Ledger\n"
            "| Claim ID | Claim Text | Evidence | Status | Caveats | Paper Role |\n"
            "|---|---|---|---|---|---|\n"
            "| C1 | component matters | Ana-1 ablation baseline | supported | same split | main_text |\n"
            "| C2 | mechanism explains why/how it works | Ana-2 mechanism visualization | partially_supported | exploratory | appendix |\n"
            "| C3 | works where mild noise appears | Ana-3 robustness baseline | supported | mild noise only | main_text |\n"
            f"| C4 | high-noise always improves | Ana-4 failure negative | unsupported | fails high noise | {c4_role} |\n\n"
            "## 洞察提炼\n"
            "How: ablation identifies the key component. Where: robustness works under mild noise. Why: mechanism visualization/probe shows alignment. So what: claim is bounded.\n\n"
            "## 局限性\n"
            "limitation: mechanism evidence is weak and high-noise failure is reported.\n\n"
            "## 证据可用性\n"
            "| Evidence ID | Source | Usability | Reason | Paper Handling |\n"
            "|---|---|---|---|---|\n"
            "| Ana-1 | experiments/analysis_results.tsv | usable | baseline included | main_text |\n"
            "| Ana-2 | experiments/artifacts/analysis_experiment/figures/mechanism.pdf | weak | visualization exploratory | appendix |\n"
            "| Ana-4 | experiments/analysis_results.tsv | unusable | failure negative | removed |\n\n"
            "## Component Claim Analysis Matrix\n"
            "| Component / Claim | ablation | mechanism | robustness | efficiency | failure | waiver_reason |\n"
            "|---|---|---|---|---|---|---|\n"
            "| C1 / component | Ana-1 | Ana-2 | Ana-3 | efficiency_required: no | Ana-4 | no efficiency claim or extra compute path |\n\n"
            "## Efficiency Evidence / Waiver\n"
            "efficiency_required: no\n"
            "trigger_reason: not_applicable\n"
            "efficiency_metrics_available: params_m runtime_sec peak_mem_mb not_applicable\n"
            "baseline_or_full_model_comparison: waived with reason\n\n"
            "## Paper Protocol Adaptation Summary\n"
            "| reference_paper / source_id | adopted_for_slice | task/metric/protocol adapted | rejected_reason / caveat |\n"
            "|---|---|---|---|\n"
            "| PaperX | Ana-1 | task_setup accuracy baseline_protocol | none |\n\n"
            "## M4→M5 Handoff\n"
            "literature_basis: M2 diagnostic protocol and 文献 analysis design. Visualization figure path recorded for M5.\n",
            encoding="utf-8",
        )
        baseline_rows = (
            "Ana-1\tablation\tbaseline\tds\ttest\t42\tcfg-b\trun-b\taccuracy\t0.753\trequired\texperiments/artifacts/analysis_experiment/Ana-1\t100\t9.8\t1900\tlocal\tlocal\t\t[]\texperiments/runs/run-b/resource_monitor.csv\tbaseline\n"
            "Ana-2\tmechanism\tbaseline\tds\ttest\t42\tcfg-b\trun-b\talignment_score\t0.410\trequired\texperiments/artifacts/analysis_experiment/Ana-2\t80\t9.8\t1900\tlocal\tlocal\t\t[]\texperiments/runs/run-b/resource_monitor.csv\tbaseline\n"
            "Ana-3\trobustness\tbaseline\tds\tnoise\t42\tcfg-b\trun-b\taccuracy_noise\t0.700\trequired\texperiments/artifacts/analysis_experiment/Ana-3\t110\t9.8\t1900\tlocal\tlocal\t\t[]\texperiments/runs/run-b/resource_monitor.csv\tbaseline\n"
            if include_baseline_rows else ""
        )
        (root / "experiments" / "analysis_results.tsv").write_text(
            "slice\tanalysis_type\tmethod\tdataset\tsplit\tseed\tconfig_id\trun_id\tmetric\tvalue\tbaseline_inclusion\tartifact_path\truntime_sec\tparams_m\tpeak_mem_mb\tresource_id\tresource_kind\tserver_id\tgpu_ids\tresource_monitor\tnotes\n"
            f"{baseline_rows}"
            "Ana-1\tablation\tours\tds\ttest\t42\tcfg-o\trun-o\taccuracy\t0.803\trequired\texperiments/artifacts/analysis_experiment/Ana-1\t130\t10.5\t2100\tlocal\tlocal\t\t[]\texperiments/runs/run-o/resource_monitor.csv\tours\n"
            "Ana-2\tmechanism\tours\tds\ttest\t42\tcfg-o\trun-o\talignment_score\t0.560\trequired\texperiments/artifacts/analysis_experiment/Ana-2\t95\t10.5\t2100\tlocal\tlocal\t\t[]\texperiments/runs/run-o/resource_monitor.csv\tours\n"
            "Ana-3\trobustness\tours\tds\tnoise\t42\tcfg-o\trun-o\taccuracy_noise\t0.760\trequired\texperiments/artifacts/analysis_experiment/Ana-3\t140\t10.5\t2100\tlocal\tlocal\t\t[]\texperiments/runs/run-o/resource_monitor.csv\tours\n"
            "Ana-4\tfailure\tours\tds\thigh_noise\t42\tcfg-o\trun-o\taccuracy_high_noise\t0.610\toptional\texperiments/artifacts/analysis_experiment/Ana-4\t120\t10.5\t2100\tlocal\tlocal\t\t[]\texperiments/runs/run-o/resource_monitor.csv\tnegative\n",
            encoding="utf-8",
        )
        if include_artifacts:
            (root / "experiments" / "artifacts" / "analysis_experiment" / "manifest.yaml").write_text(
                "analysis_slices:\n"
                "  - id: Ana-1\n"
                "    analysis_type: ablation\n"
                "    baseline_inclusion: required\n"
                "    literature_basis: PaperX ablation protocol\n"
                "  - id: Ana-2\n"
                "    analysis_type: mechanism\n"
                "    baseline_inclusion: required\n"
                "    literature_basis: PaperY visualization protocol\n"
                "  - id: Ana-3\n"
                "    analysis_type: robustness\n"
                "    baseline_inclusion: required\n"
                "    literature_basis: PaperZ robustness protocol\n"
                "component_claim_analysis_matrix:\n"
                "  - claim: C1\n"
                "    component: component\n"
                "    slices: [Ana-1, Ana-2, Ana-3]\n"
                "paper_protocol_adaptation:\n"
                "  - reference_paper: PaperX\n"
                "    source_id: S1\n"
                "    task_setup: diagnostic task\n"
                "    adoption_decision: adopted\n"
                "figure_paths:\n"
                "  - experiments/artifacts/analysis_experiment/figures/mechanism.pdf\n",
                encoding="utf-8",
            )
            (root / "experiments" / "artifacts" / "analysis_experiment" / "reproduction.md").write_text(
                "# M4 Reproduction\n\nRun Ana-1 through Ana-4 with baseline and ours rows.\n",
                encoding="utf-8",
            )
            (root / "experiments" / "artifacts" / "analysis_experiment" / "figures" / "mechanism.pdf").write_bytes(
                b"%PDF mechanism figure\n"
            )
        if include_handoff:
            (root / "knowledge" / "handoff_M4_M5.md").write_text(
                "# Handoff M4 to M5\n\n"
                "## Claim/Evidence Mapping\n"
                "Claim C1 supported by Evidence Ana-1; Claim C2 partially_supported weak evidence; C3 supported.\n\n"
                "## Artifact Paths\n"
                "- experiments/analysis_results.tsv\n"
                "- experiments/artifacts/analysis_experiment/manifest.yaml\n"
                "- figure: experiments/artifacts/analysis_experiment/figures/mechanism.pdf\n\n"
                "## M5 Writing Guidance\n"
                "M5 Introduction, Method, Experiments, and Analysis should use supported evidence and caveats.\n\n"
                "## Limitations and Caveats\n"
                "weak mechanism evidence goes to appendix; unsupported high-noise evidence is removed.\n",
                encoding="utf-8",
            )

    def test_m4s04_stage_gate_accepts_complete_analysis_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m4s04_project(proj)

            ok, messages = check_stage(proj, "M4S04")

            self.assertTrue(ok, "\n".join(messages))
            self.assertTrue(any("covers ablation/mechanism/robustness/failure" in m for m in messages))
            self.assertTrue(any("analysis visualization/figure artifact" in m for m in messages))

    def test_m4s04_stage_gate_blocks_missing_artifacts_and_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m4s04_project(proj, include_artifacts=False, include_handoff=False)

            ok, messages = check_stage(proj, "M4S04")

            self.assertFalse(ok)
            joined = "\n".join(messages)
            self.assertIn("analysis artifact manifest.yaml missing or empty", joined)
            self.assertIn("analysis artifact reproduction.md missing or empty", joined)
            self.assertIn("no analysis visualization/figure artifact found", joined)
            self.assertIn("handoff_M4_M5.md missing or empty", joined)

    def test_m4s04_stage_gate_blocks_unsupported_main_text_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m4s04_project(proj, unsupported_main_text=True)

            ok, messages = check_stage(proj, "M4S04")

            self.assertFalse(ok)
            self.assertTrue(any("unsupported/deferred/unusable evidence assigned to main_text" in m for m in messages))

    def test_m4s04_stage_gate_blocks_analysis_without_baseline_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m4s04_project(proj, include_baseline_rows=False)

            ok, messages = check_stage(proj, "M4S04")

            self.assertFalse(ok)
            self.assertTrue(any("analysis_results.tsv missing baseline comparison rows" in m for m in messages))


class TestM5StageGate(unittest.TestCase):
    def _write_m5_upstream_docs(self, root: Path) -> None:
        required = {
            "knowledge/M1/M1S02_literature_deepdive.md": "# M1S02\n",
            "knowledge/M1/M1_source_log.yaml": "sources:\n  - id: S1\n",
            "knowledge/M1/M1S03_research_question.md": "# M1S03\n",
            "knowledge/M1/M1S04_hypothesis_generation.md": "# M1S04\n",
            "knowledge/M2/M2S03_method_architecture.md": "# M2S03\n",
            "knowledge/M2/M2S04_algorithm_theory.md": "# M2S04\n",
            "knowledge/M2/M2S05_experiment_setup.md": "# M2S05\n",
            "knowledge/M3/M3S01_main_experiment_design.md": "# M3S01\n",
            "knowledge/M3/M3S04_main_experiment.md": "# M3S04\n",
            "knowledge/M3/M3S05_result_validation.md": "# M3S05\n",
            "knowledge/M4/M4S03_analysis_experiment.md": "# M4S03\n",
            "knowledge/M4/M4S04_analysis_results.md": "# M4S04\n",
            "knowledge/handoff_M4_M5.md": "# handoff\n",
        }
        for rel_path, content in required.items():
            path = root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def _write_m5s01_project(self, root: Path, *, ready: bool = True) -> None:
        self._write_m5_upstream_docs(root)
        for rel in ("knowledge/M5", "knowledge/reviews"):
            (root / rel).mkdir(parents=True, exist_ok=True)
        (root / "knowledge" / "reviews" / "M5S01_prewrite_review.md").write_text(
            "# M5S01 Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )
        if ready:
            readiness = "Writing readiness: yes\n是否建议继续写作: 是\n必须先修复的阻塞问题: 无\n"
            gap = (
                "Evidence Gap 证据缺口: Low | block: no.\n"
                "Narrative Gap 叙事缺口: Low | block: no.\n"
                "Citation Gap 引用缺口: Low | block: no.\n"
            )
        else:
            readiness = "Writing readiness: no\n是否建议继续写作: 否\n必须先修复的阻塞问题: High evidence gap.\n"
            gap = "Evidence Gap 证据缺口: High | block: yes.\nNarrative Gap 叙事缺口.\nCitation Gap 引用缺口.\n"
        (root / "knowledge" / "M5" / "M5S01_pre_write_audit.md").write_text(
            "# M5S01 Pre-Write Audit\n\n"
            "## 上游文档完整性检查\n"
            "upstream completeness complete for M1S02, M1_source_log, M1S03, M1S04, M2S03-M2S05, M3S01, "
            "M3S04-M3S05, M4S03-M4S04, handoff_M4_M5.\n\n"
            "## 核心贡献点\n"
            "Contribution Contrib-1 has 支撑证据 evidence path knowledge/M3/M3S05_result_validation.md "
            "and knowledge/M4/M4S04_analysis_results.md. 证据状态: fully_supported.\n\n"
            "## Gap 识别\n"
            f"{gap}\n"
            "## 风格/排版参照审计\n"
            "Reference papers 3. 风格蒸馏 extracts structure and layout only; do not copy 不复制.\n\n"
            "## 数据一致性检查\n"
            "Main metric 主指标 consistent 一致. Baseline 基线 consistent. Dataset 数据集 consistent. "
            "Method name 方法名称 consistent.\n\n"
            "## 审计结论\n"
            f"{readiness}",
            encoding="utf-8",
        )

    def _write_m5s02_project(self, root: Path, *, with_reference_count: bool = True) -> None:
        for rel in ("knowledge/M5", "knowledge/reviews"):
            (root / rel).mkdir(parents=True, exist_ok=True)
        (root / "knowledge" / "reviews" / "M5S02_outline_style_review.md").write_text(
            "# M5S02 Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )
        reference_line = "Reference paper count: 3 exemplar papers.\n" if with_reference_count else ""
        (root / "knowledge" / "M5" / "M5S02_paper_outline.md").write_text(
            "# M5S02 Paper Outline\n\n"
            "Venue\nPlotting Plan\nTerminology\nSection Plan\n"
            f"{reference_line}"
            "Style & Layout Profile: transferable structure, paragraph function, section rhythm, "
            "figure/table density, and layout constraint signals; do not copy 不得复制 不可迁移 unique wording.\n"
            "Figure Style Profile: venue preset, palette, color grammar, visual richness, layout grammar. "
            "Architecture figure policy uses image2 gpt-image-2 with paper-framework-figure-studio-pro c-narcissus. "
            "Experiment plots use nature-figure with matplotlib seaborn plt.\n",
            encoding="utf-8",
        )

    def test_m5s01_stage_gate_accepts_complete_prewrite_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m5s01_project(proj)

            ok, messages = check_stage(proj, "M5S01")

            self.assertTrue(ok, "\n".join(messages))
            self.assertTrue(any("required upstream documents exist" in m for m in messages))
            self.assertTrue(any("continue-writing decision" in m for m in messages))

    def test_m5s01_stage_gate_blocks_missing_upstream_doc(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m5s01_project(proj)
            (proj / "knowledge" / "M4" / "M4S04_analysis_results.md").unlink()

            ok, messages = check_stage(proj, "M5S01")

            self.assertFalse(ok)
            self.assertTrue(any("M4S04_analysis_results.md" in m for m in messages))

    def test_m5s01_stage_gate_blocks_unresolved_blocking_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m5s01_project(proj, ready=False)

            ok, messages = check_stage(proj, "M5S01")

            self.assertFalse(ok)
            joined = "\n".join(messages)
            self.assertIn("high-severity blocking gap", joined)
            self.assertIn("continue-writing decision", joined)

    def test_m5s02_stage_gate_accepts_complete_style_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m5s02_project(proj)

            ok, messages = check_stage(proj, "M5S02")

            self.assertTrue(ok, "\n".join(messages))
            self.assertTrue(any("declares 3-5 reference" in m for m in messages))
            self.assertTrue(any("transferable structure/layout signals" in m for m in messages))

    def test_m5s02_stage_gate_blocks_missing_reference_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m5s02_project(proj, with_reference_count=False)

            ok, messages = check_stage(proj, "M5S02")

            self.assertFalse(ok)
            self.assertTrue(any("3-5 reference/exemplar paper count" in m for m in messages))

    def _write_m5s08_project(self, root: Path, *, complete: bool = True, orphan_cite: bool = False) -> None:
        for rel in (
            "knowledge/M5",
            "knowledge/reviews",
            "artifacts/figures",
        ):
            (root / rel).mkdir(parents=True, exist_ok=True)
        (root / "artifacts" / "paper.pdf").write_bytes(b"%PDF simulated\n")
        (root / "knowledge" / "reviews" / "M5S08_final_compilation_review.md").write_text(
            "# M5S08 Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )
        if not complete:
            (root / "knowledge" / "M5" / "M5S08_final_compilation.md").write_text(
                "# M5S08\n\nstyle & layout compliance. figure compliance.\n",
                encoding="utf-8",
            )
            (root / "artifacts" / "paper.tex").write_text(
                "\\documentclass{article}\\begin{document}TODO\\end{document}\n",
                encoding="utf-8",
            )
            return

        cite_key = "missing2026" if orphan_cite else "smith2024demo"
        (root / "knowledge" / "M5" / "M5S09_full_polish.md").write_text(
            "# M5S09 Full-Polish\n\n"
            "Narrative coherence 叙事连贯 audit passed.\n"
            "Intro-Method chain, Method-Experiments chain, and Experiments-Analysis mapping are complete.\n"
            "M5S05 findings map one-to-one to M5S06 analysis.\n"
            "terminology consistency 术语一致 passed.\n"
            "numerical consistency 数值一致 passed.\n"
            "language refinement 语言精炼 and 润色 completed.\n"
            "paper.tex LaTeX source edited; paper.pdf PDF rendering checked.\n"
            "recompile 重新编译 compile completed after polish.\n"
            "Anti-Leakage prompt applied.\n",
            encoding="utf-8",
        )
        (root / "artifacts" / "figures" / "architecture.pdf").write_bytes(b"%PDF figure\n")
        (root / "artifacts" / "refs.bib").write_text(
            "@article{smith2024demo,\n"
            "  title={Demo Baseline},\n"
            "  author={Smith, Alex},\n"
            "  journal={Demo Journal},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        (root / "artifacts" / "paper.tex").write_text(
            "\\documentclass{article}\n"
            "\\usepackage{graphicx}\n"
            "\\usepackage{booktabs}\n"
            "\\title{A Complete Simulated Paper}\n"
            "\\begin{document}\n"
            "\\maketitle\n"
            "\\begin{abstract}\n"
            "This paper reports a complete simulated study with bounded claims and reproducible evidence.\n"
            "\\end{abstract}\n"
            "\\section{Introduction}\n"
            f"We motivate the problem using prior evidence~\\cite{{{cite_key}}} and define a bounded contribution.\n"
            "\\section{Related Work}\n"
            "Related work establishes the baseline and metric definitions used throughout the comparison.\n"
            "\\section{Method}\n"
            "The method transforms the validated design into an executable protocol. Figure~\\ref{fig:arch} shows the architecture.\n"
            "\\begin{figure}[t]\n"
            "\\centering\n"
            "\\includegraphics[width=0.7\\linewidth]{figures/architecture}\n"
            "\\caption{Architecture overview.}\n"
            "\\label{fig:arch}\n"
            "\\end{figure}\n"
            "\\section{Experiments and Results}\n"
            "Table~\\ref{tab:main} reports the main metric comparison for seed 42.\n"
            "\\begin{table}[t]\n"
            "\\centering\n"
            "\\caption{Main comparison.}\n"
            "\\label{tab:main}\n"
            "\\begin{tabular}{lccc}\n"
            "\\toprule\n"
            "Method & Metric & Mean & Std \\\\\n"
            "\\midrule\n"
            "Baseline & Accuracy & 0.753 & 0.006 \\\\\n"
            "Ours & Accuracy & 0.803 & 0.006 \\\\\n"
            "\\bottomrule\n"
            "\\end{tabular}\n"
            "\\end{table}\n"
            "\\section{Analysis and Discussion}\n"
            "The analysis discusses robustness, mechanism evidence, negative findings, and limits of the benchmark.\n"
            "\\section{Conclusion}\n"
            "The conclusion restates the evidence-supported claim and its scope for future work.\n"
            "\\bibliographystyle{plain}\n"
            "\\bibliography{refs}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        (root / "knowledge" / "M5" / "M5S08_final_compilation.md").write_text(
            "# M5S08 Final Compilation\n\n"
            "Final verdict: PASS\n\n"
            "Compile commands: pdflatex paper.tex; bibtex paper; pdflatex paper.tex; pdflatex paper.tex.\n"
            "编译状态: PASS\n"
            "PDF page count: 6\n"
            "Fatal Errors: 0\n"
            "Undefined references: 0\n"
            "Undefined citations: 0\n"
            "Orphan cites: 0\n"
            "Anti-Leakage Check: PASS\n"
            "style & layout compliance. Figure compliance: 图像 图表 generated-images 绘图脚本. "
            "figure style profile venue preset palette visual richness.\n"
            "Final artifacts: artifacts/paper.tex, artifacts/paper.pdf, artifacts/refs.bib.\n",
            encoding="utf-8",
        )
        (root / "knowledge" / "handoff_M5_completion.md").write_text(
            "# Handoff M5 Completion\n\n"
            "M6 submission ready. Compilation verdict PASS.\n"
            "Artifacts: artifacts/paper.pdf, artifacts/paper.tex, refs.bib.\n",
            encoding="utf-8",
        )

    def test_m5s08_stage_gate_accepts_complete_compilation_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m5s08_project(proj)

            ok, messages = check_stage(proj, "M5S08")

            self.assertTrue(ok, "\n".join(messages))
            self.assertTrue(any("orphan citation gate passed" in m for m in messages))
            self.assertTrue(any("paper.pdf exists and has PDF header" in m for m in messages))

    def test_m5s08_stage_gate_blocks_placeholder_paper(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m5s08_project(proj, complete=False)

            ok, messages = check_stage(proj, "M5S08")

            self.assertFalse(ok)
            joined = "\n".join(messages)
            self.assertIn("paper.tex is too short", joined)
            self.assertIn("paper.tex contains placeholder text", joined)
            self.assertIn("artifacts/refs.bib missing or empty", joined)

    def test_m5s08_stage_gate_blocks_orphan_citation(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            self._write_m5s08_project(proj, orphan_cite=True)

            ok, messages = check_stage(proj, "M5S08")

            self.assertFalse(ok)
            self.assertTrue(any("orphan citation keys: missing2026" in m for m in messages))

    def test_m5s09_stage_gate_accepts_complete_polish_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            (proj / "knowledge" / "M5").mkdir(parents=True, exist_ok=True)
            (proj / "knowledge" / "reviews").mkdir(parents=True, exist_ok=True)
            (proj / "artifacts").mkdir(parents=True, exist_ok=True)
            (proj / "artifacts" / "paper.tex").write_text("\\documentclass{article}\\begin{document}ok\\end{document}\n", encoding="utf-8")
            (proj / "artifacts" / "paper.pdf").write_bytes(b"%PDF polished\n")
            (proj / "artifacts" / "refs.bib").write_text("@article{x, title={x}, year={2026}}\n", encoding="utf-8")
            (proj / "knowledge" / "handoff_M5_completion.md").write_text(
                "# Handoff\n\nM6 submission ready. Artifacts: artifacts/paper.pdf, artifacts/paper.tex, refs.bib.\n",
                encoding="utf-8",
            )
            (proj / "knowledge" / "M5" / "M5S09_full_polish.md").write_text(
                "# M5S09 Full-Polish & Narrative Coherence Review\n\n"
                "Narrative coherence 叙事连贯 audit passed.\n"
                "Intro-Method chain is complete.\n"
                "Method-Experiments chain is complete.\n"
                "Experiments-Analysis chain maps M5S05 to M5S06 one-to-one.\n"
                "terminology consistency 术语一致 passed.\n"
                "numerical consistency 数值一致 passed.\n"
                "language refinement 语言精炼 and 润色 completed.\n"
                "paper.tex LaTeX source edited; paper.pdf PDF rendering checked.\n"
                "recompile 重新编译 compile completed after polish.\n"
                "Anti-Leakage prompt applied.\n",
                encoding="utf-8",
            )
            (proj / "knowledge" / "reviews" / "M5S09_full_polish_review.md").write_text(
                "# M5S09 Review\n\nVerdict: PASS\n",
                encoding="utf-8",
            )

            ok, messages = check_stage(proj, "M5S09")

            self.assertTrue(ok, "\n".join(messages))
            self.assertTrue(any("includes narrative coherence" in m for m in messages))


class TestM4Templates(unittest.TestCase):
    """Test M4 stage templates exist and are copyable."""

    def test_m4_templates_exist(self):
        tpl_root = _project_root / "templates" / "stage"
        for stage in ["M4S01", "M4S02", "M4S03", "M4S04"]:
            tpl = tpl_root / f"{stage}_template.md"
            assert tpl.exists(), f"Template missing: {tpl}"
        print("  [PASS] All M4 stage templates exist")

    def test_m4_templates_copyable(self):
        tpl_root = _project_root / "templates" / "stage"
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "drafts"
            for stage in ["M4S01", "M4S02", "M4S03", "M4S04"]:
                tpl = tpl_root / f"{stage}_template.md"
                stage_dir = dst / stage
                stage_dir.mkdir(parents=True)
                shutil.copy(tpl, stage_dir / f"{stage}_draft.md")
                assert (stage_dir / f"{stage}_draft.md").exists()
        print("  [PASS] All M4 stage templates copyable")


class TestM4ProjectCreation(unittest.TestCase):
    """Test that ProjectManager creates M4 directories correctly."""

    def test_m4_knowledge_dir_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects_root = Path(tmp) / "projects"
            proj = ProjectManager.create(
                topic="Test M4 Project",
                display_name="Test-M4",
                projects_root=projects_root,
            )
            assert (proj / "knowledge" / "M4").exists(), "M4 knowledge dir not created"
            print("  [PASS] M4 knowledge dir created on project init")

    def test_m4_draft_dirs_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects_root = Path(tmp) / "projects"
            proj = ProjectManager.create(
                topic="Test M4 Project",
                display_name="Test-M4",
                projects_root=projects_root,
            )
            for stage in ["M4S01", "M4S02", "M4S03", "M4S04"]:
                assert (proj / "drafts" / stage).exists(), f"Draft dir not created: {stage}"
            print("  [PASS] M4 draft dirs created on project init")


if __name__ == "__main__":
    unittest.main()
