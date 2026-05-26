#!/usr/bin/env python3
"""Integration tests for M3 stage-gate evidence."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from utils.stage_gate import check_stage


def _code_with_enough_lines() -> str:
    lines = [
        "def normalize(value):",
        "    return float(value)",
        "",
        "def load_dataset(path):",
        "    rows = []",
        "    with open(path, 'r', encoding='utf-8') as handle:",
        "        for raw in handle:",
        "            rows.append(normalize(raw.strip() or 0))",
        "    return rows",
        "",
        "def train_one_epoch(rows):",
        "    total = 0.0",
        "    for value in rows:",
        "        total += value",
        "    return total / max(len(rows), 1)",
        "",
        "def evaluate(rows):",
        "    score = train_one_epoch(rows)",
        "    return {'primary': score}",
        "",
        "if __name__ == '__main__':",
        "    print(evaluate([1, 2, 3]))",
    ]
    return "\n".join(lines) + "\n"


class TestM3StageGate(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_m3s01_files(
        self,
        *,
        include_ledger: bool = True,
        include_sandbox: bool = True,
        execution_mode: str = "local",
        local_env_manager: str = "venv",
        local_python_version: str = "3.11",
        ssh_host: str = "",
        ssh_user: str = "",
        ssh_workspace_path: str = "",
    ) -> None:
        for rel in (
            "knowledge/M3",
            "knowledge/reviews",
            "config",
            "experiments/src",
            "experiments/data/demo",
            "experiments/logs",
        ):
            (self.root / rel).mkdir(parents=True, exist_ok=True)

        if execution_mode == "ssh":
            env_sentence = (
                "`config/execution_env.yaml` uses ssh remote mode with rsync sync, "
                "remote workspace, and ssh execution evidence.\n\n"
            )
            sandbox_mode = "ssh_remote"
        else:
            env_sentence = "`config/execution_env.yaml` uses local mode with an isolated venv.\n\n"
            sandbox_mode = "venv"

        (self.root / "knowledge" / "M3" / "M3S01_implementation.md").write_text(
            "# M3S01 Implementation\n\n"
            "## Dataset Review\n"
            "The real dataset is linked under `experiments/data/demo`.\n\n"
            "## 环境 Review\n"
            f"{env_sentence}"
            "## Long-running execution policy\n"
            "Long-running downloads and smoke runs are recorded in "
            "`experiments/logs/m3s01_longrun_ledger.md` with patience, permission, and resume evidence.\n",
            encoding="utf-8",
        )
        sandbox_yaml = (
            "  sandbox:\n"
            "    enabled: true\n"
            f"    mode: {sandbox_mode}\n"
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
        )
        (self.root / "config" / "execution_env.yaml").write_text(
            "execution:\n"
            f"  mode: {execution_mode}\n"
            + (sandbox_yaml if include_sandbox else "")
            + "  local:\n"
            f"    env_manager: {local_env_manager}\n"
            f"    python_version: '{local_python_version}'\n"
            "  ssh:\n"
            f"    host: '{ssh_host}'\n"
            f"    user: '{ssh_user}'\n"
            "    port: 22\n"
            "    auth_method: key\n"
            "    framework_root: '~/AutoPaper2'\n"
            f"    workspace_path: '{ssh_workspace_path}'\n"
            "    dataset_path: '~/AutoPaper2/data/datasets'\n"
            "    env_manager: conda\n"
            "    python_version: '3.11'\n"
            "    sync:\n"
            "      method: rsync\n"
            "      auto_sync: true\n",
            encoding="utf-8",
        )
        if include_sandbox:
            (self.root / "experiments" / "configs").mkdir(parents=True, exist_ok=True)
            (self.root / "experiments" / "configs" / "sandbox_profile.yaml").write_text(
                "sandbox:\n"
                "  enabled: true\n"
                f"  mode: {sandbox_mode}\n"
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
        (self.root / "experiments" / "requirements.lock").write_text("numpy==1.26.4\n", encoding="utf-8")
        (self.root / "experiments" / "data" / "demo" / "values.txt").write_text("1\n2\n3\n", encoding="utf-8")
        (self.root / "experiments" / "src" / "train.py").write_text(_code_with_enough_lines(), encoding="utf-8")
        (self.root / "knowledge" / "reviews" / "M3S01_dataset_env_review.md").write_text(
            "# M3S01 Dataset & Environment Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )
        if include_ledger:
            if execution_mode == "ssh":
                ledger_rows = (
                    "| dataset: demo | ssh remote | `ssh user@gpu.example 'wget -c https://example.test/demo.zip'` | completed | `experiments/logs/remote_download.log` | timeout=12h; poll_interval=30m; last_checked=2026-05-23T10:00:00 | `ssh user@gpu.example 'wget -c https://example.test/demo.zip'` | approved remote download | checksum passed |\n"
                    "| sync: code | ssh remote | `rsync -avzP ./ user@gpu.example:~/AutoPaper2/projects/demo/` | completed | `experiments/logs/rsync_push.log` | timeout=2h; poll_interval=10m | `rsync -avzP ./ user@gpu.example:~/AutoPaper2/projects/demo/` | approved rsync upload | remote workspace ready |\n"
                )
            else:
                ledger_rows = (
                    "| dataset: demo | local | `wget -c https://example.test/demo.zip` | completed | `experiments/logs/demo_download.log` | timeout=12h; poll_interval=30m; last_checked=2026-05-23T10:00:00 | `wget -c https://example.test/demo.zip` | none | checksum passed |\n"
                    "| smoke: import | local | `python experiments/src/train.py` | completed | `experiments/logs/import_smoke.log` | timeout=30m; poll_interval=5m | `python experiments/src/train.py` | none | import test passed |\n"
                )
            (self.root / "experiments" / "logs" / "m3s01_longrun_ledger.md").write_text(
                "# M3S01 Long-Running Execution Ledger\n\n"
                "| Item | Execution mode | Command | Status | Log path | Patience / polling | Resume command | Permission / approval | Completion criteria |\n"
                "|------|----------------|---------|--------|----------|--------------------|----------------|-----------------------|--------------------|\n"
                f"{ledger_rows}",
                encoding="utf-8",
            )

    def _write_m3s04_report(self, *, decision: str = "KEEP", complete: bool = True) -> None:
        (self.root / "knowledge" / "M3").mkdir(parents=True, exist_ok=True)
        if not complete:
            text = f"# M3S04 Result Validation\n\nDecision: {decision}\n"
        else:
            text = (
                "# M3S04 Result Validation\n\n"
                "## 实验停止原因\n"
                "停止条件: budget complete. 当前 best 指标: accuracy=0.803. Evidence Ladder: solid.\n\n"
                "## 数据质量检查\n"
                "过拟合 normal; 数据泄露 none; 训练稳定性 stable; 可复现 with three seeds.\n\n"
                "## 统计显著性检验\n"
                "Wilcoxon test p-value=0.018; effect size=0.82; 效应量 strong; 95% 置信区间=[0.038,0.061]; 多重比较 none.\n\n"
                "## 与假设的对应验证\n"
                "| 假设 | 预期结果 | 实际结果 | 支持程度 |\n"
                "|------|---------|---------|---------|\n"
                "| H1 | Ours improves accuracy | +0.05 accuracy | 完全支持 |\n\n"
                "## 潜在问题与根因分析\n"
                "| 问题 | 严重程度 (critical/major/minor) | 根因 | 影响 |\n"
                "|------|-------------------------------|------|------|\n"
                "| small dataset | minor | benchmark scope | M4 robustness check |\n\n"
                "## 最终决策\n"
                f"Decision: {decision}\n\n"
                "## 负面结果\n"
                "negative result: one seed had smaller gain and is preserved for failure analysis.\n\n"
                "## Evidence Artifact 打包\n"
                "Artifact 清单: manifest.yaml, metric_contract.yaml, comparison_table.csv, reproduction.md.\n\n"
                "## 已知限制\n"
                "局限性: single benchmark only.\n\n"
                "## 传递给下游的信息\n"
                "M4 analysis direction: 消融 ablation, 鲁棒 robustness, 机制 mechanism; handoff required.\n"
            )
        (self.root / "knowledge" / "M3" / "M3S04_result_validation.md").write_text(text, encoding="utf-8")

    def _write_m3s04_artifacts(self) -> None:
        artifacts = self.root / "experiments" / "artifacts" / "main_experiment"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "manifest.yaml").write_text(
            "experiment_id: main_exp_v1\n"
            "method: ours\n"
            "dataset: demo\n"
            "baseline_refs:\n"
            "  - experiments/baselines/baseline_1/metric_contract.yaml\n"
            "primary_metric:\n"
            "  key: accuracy\n"
            "  value: 0.803\n"
            "  std: 0.006\n"
            "seeds: [1, 2, 3]\n"
            "environment:\n"
            "  python: '3.11'\n"
            "  hardware: cpu\n",
            encoding="utf-8",
        )
        (artifacts / "metric_contract.yaml").write_text(
            "method: ours\n"
            "metrics:\n"
            "  primary:\n"
            "    key: accuracy\n"
            "    value: 0.803\n"
            "    std: 0.006\n",
            encoding="utf-8",
        )
        (artifacts / "comparison_table.csv").write_text(
            "method,metric,mean,std,seed_count\n"
            "baseline,accuracy,0.753,0.006,3\n"
            "ours,accuracy,0.803,0.006,3\n",
            encoding="utf-8",
        )
        (artifacts / "reproduction.md").write_text(
            "# Reproduction\n\nRun the main experiment with seeds 1, 2, and 3.\n",
            encoding="utf-8",
        )

    def _write_m3s04_handoff(self) -> None:
        (self.root / "knowledge").mkdir(parents=True, exist_ok=True)
        (self.root / "knowledge" / "handoff_M3_M4.md").write_text(
            "# Handoff M3 to M4\n\n"
            "Decision: KEEP; validated by M3S04 result validation.\n\n"
            "## Claims and Evidence\n"
            "claim C1: ours improves accuracy; evidence: experiments/artifacts/main_experiment/manifest.yaml and comparison_table.csv.\n\n"
            "## M4 Analysis\n"
            "M4 analysis should cover 消融, 鲁棒, and 机制 checks using experiments/artifacts/main_experiment/.\n",
            encoding="utf-8",
        )

    def test_m3s01_stage_gate_accepts_longrun_ledger(self) -> None:
        self._write_m3s01_files(include_ledger=True)

        ok, messages = check_stage(self.root, "M3S01")

        self.assertTrue(ok, "\n".join(messages))
        self.assertTrue(any("long-running ledger includes" in message for message in messages))

    def test_m3s01_stage_gate_requires_longrun_ledger(self) -> None:
        self._write_m3s01_files(include_ledger=False)

        ok, messages = check_stage(self.root, "M3S01")

        self.assertFalse(ok)
        self.assertTrue(any("long-running execution ledger missing" in message for message in messages))

    def test_m3s01_stage_gate_requires_sandbox_profile(self) -> None:
        self._write_m3s01_files(include_ledger=True, include_sandbox=False)

        ok, messages = check_stage(self.root, "M3S01")

        self.assertFalse(ok)
        self.assertTrue(any("execution.sandbox profile missing" in message for message in messages))
        self.assertTrue(any("sandbox_profile.yaml not found" in message for message in messages))

    def test_m3s01_stage_gate_requires_local_or_ssh_mode(self) -> None:
        self._write_m3s01_files(include_ledger=True, execution_mode="cluster")

        ok, messages = check_stage(self.root, "M3S01")

        self.assertFalse(ok)
        self.assertTrue(any("execution.mode must be explicitly local or ssh" in message for message in messages), messages)

    def test_m3s01_stage_gate_requires_local_env_fields(self) -> None:
        self._write_m3s01_files(include_ledger=True, local_env_manager="")

        ok, messages = check_stage(self.root, "M3S01")

        self.assertFalse(ok)
        self.assertTrue(any("local env_manager must be conda/venv/uv/docker" in message for message in messages), messages)

    def test_m3s01_stage_gate_requires_ssh_connection_fields(self) -> None:
        self._write_m3s01_files(include_ledger=True, execution_mode="ssh")

        ok, messages = check_stage(self.root, "M3S01")

        self.assertFalse(ok)
        self.assertTrue(any("ssh host missing" in message for message in messages), messages)
        self.assertTrue(any("ssh user missing" in message for message in messages), messages)
        self.assertTrue(any("ssh workspace_path missing" in message for message in messages), messages)

    def test_m3s01_stage_gate_accepts_ssh_execution_config(self) -> None:
        self._write_m3s01_files(
            include_ledger=True,
            execution_mode="ssh",
            ssh_host="gpu.example",
            ssh_user="user",
            ssh_workspace_path="~/AutoPaper2/projects/demo",
        )

        ok, messages = check_stage(self.root, "M3S01")

        self.assertTrue(ok, "\n".join(messages))
        self.assertTrue(any("implementation doc records ssh/remote execution mode" in message for message in messages), messages)
        self.assertTrue(any("SSH mode ledger includes remote execution/rsync evidence" in message for message in messages), messages)

    def test_m3s04_stage_gate_accepts_keep_with_evidence_package(self) -> None:
        self._write_m3s04_report()
        self._write_m3s04_artifacts()
        self._write_m3s04_handoff()

        ok, messages = check_stage(self.root, "M3S04")

        self.assertTrue(ok, "\n".join(messages))
        self.assertTrue(any("manifest.yaml records at least 3 seeds" in message for message in messages))
        self.assertTrue(any("handoff_M3_M4.md includes M4 analysis direction" in message for message in messages))

    def test_m3s04_stage_gate_blocks_keep_without_evidence_package(self) -> None:
        self._write_m3s04_report()

        ok, messages = check_stage(self.root, "M3S04")

        self.assertFalse(ok)
        joined = "\n".join(messages)
        self.assertIn("manifest missing or empty", joined)
        self.assertIn("metric contract missing or empty", joined)
        self.assertIn("comparison table missing or empty", joined)
        self.assertIn("handoff_M3_M4.md missing or empty", joined)

    def test_m3s04_stage_gate_blocks_incomplete_validation_report(self) -> None:
        self._write_m3s04_report(complete=False)
        self._write_m3s04_artifacts()
        self._write_m3s04_handoff()

        ok, messages = check_stage(self.root, "M3S04")

        self.assertFalse(ok)
        joined = "\n".join(messages)
        self.assertIn("missing statistical validation", joined)
        self.assertIn("missing hypothesis mapping", joined)
        self.assertIn("missing data quality checks", joined)

    def test_m3s04_stage_gate_blocks_fix_even_with_repair_advice(self) -> None:
        self._write_m3s04_report(decision="FIX")
        doc = self.root / "knowledge" / "M3" / "M3S04_result_validation.md"
        doc.write_text(
            doc.read_text(encoding="utf-8")
            + "\n## 回溯修改方向\n"
            "- blocking_reason: validation found unstable gains\n"
            "- required_fix: rerun M3S03 with corrected seeds\n"
            "- success_criteria: stable significant improvement across three seeds\n"
            "- rebuild_mode: incremental_replay\n"
            "- rerun_scope: M3S03-M3S04\n",
            encoding="utf-8",
        )

        ok, messages = check_stage(self.root, "M3S04")

        self.assertFalse(ok)
        self.assertTrue(any("blocks advancement" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
