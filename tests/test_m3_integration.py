#!/usr/bin/env python3
"""Integration tests for M3 stage-gate evidence."""

from __future__ import annotations

import sys
import tempfile
import unittest
import hashlib
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

    def _write_m3s02_files(
        self,
        *,
        include_ledger: bool = True,
        include_sandbox: bool = True,
        include_resource_plan: bool = True,
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
            "experiments/configs",
            "experiments/data/demo",
            "experiments/data/demo/splits",
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

        (self.root / "knowledge" / "M3" / "M3S02_implementation.md").write_text(
            "# M3S02 Implementation\n\n"
            "## Dataset Review\n"
            "The real dataset is linked under `experiments/data/demo`.\n\n"
            "## 环境 Review\n"
            f"{env_sentence}"
            "## Long-running execution policy\n"
            "Long-running downloads and smoke runs are recorded in "
            "`experiments/logs/m3s02_longrun_ledger.md` with patience, permission, and resume evidence.\n\n"
            "## Resource utilization plan\n"
            "`experiments/configs/resource_plan.yaml` records local/ssh hardware allocation, "
            "DDP or task_parallel strategy, dataloader workers, launch command, and utilization thresholds.\n",
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
            "      seed_policy: fixed_seed_42\n"
            "  resource_optimization:\n"
            "    enabled: true\n"
            "    target_gpu_count: all_visible\n"
            "    target_cpu_cores: auto\n"
            "    gpu_strategy: auto\n"
            "    cpu_strategy: dataloader_and_task_parallel\n"
            "    dataloader:\n"
            "      auto_num_workers: true\n"
            "      max_workers: 16\n"
            "    monitoring:\n"
            "      enabled: true\n"
            "      interval_seconds: 10\n"
            "      min_gpu_utilization_pct: 70\n"
            "      min_cpu_utilization_pct: 60\n"
            "      plan_path: experiments/configs/resource_plan.yaml\n"
            "      monitor_path_template: experiments/runs/{run_id}/resource_monitor.csv\n"
            "      runtime_watchdog:\n"
            "        enabled: true\n"
            "        default_interval_seconds: 14400\n"
            "        events_path: experiments/logs/runtime_events.jsonl\n"
            "        checks_path_template: experiments/runs/{run_id}/watchdog_checks.jsonl\n"
            "        alerts_path_template: experiments/runs/{run_id}/watchdog_alerts.jsonl\n"
            "        alert_policy: record_alert_only_agent_decides_continue_fix_or_stop\n"
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
                "    seed_policy: fixed_seed_42\n",
                encoding="utf-8",
            )
        if include_resource_plan:
            (self.root / "experiments" / "configs" / "resource_plan.yaml").write_text(
                "schema_version: 1\n"
                "available:\n"
                "  cpu:\n"
                "    cores: 8\n"
                "    memory_total_mb: 32768\n"
                "  gpus: []\n"
                "allocation:\n"
                "  cpu_cores: 4\n"
                "  gpu_count: 0\n"
                "  gpu_ids: []\n"
                "strategy:\n"
                "  device_mode: cpu_parallel\n"
                "  gpu_parallelism: none\n"
                "  config_or_task_parallelism: true\n"
                "  dataloader:\n"
                "    num_workers: 2\n"
                "    pin_memory: false\n"
                "    persistent_workers: true\n"
                "    prefetch_factor: 2\n"
                "launch:\n"
                "  env:\n"
                "    OMP_NUM_THREADS: '4'\n"
                "    MKL_NUM_THREADS: '4'\n"
                "  command_template: python experiments/src/train.py --config experiments/configs/main_exp.yaml --device cpu\n"
                "monitoring:\n"
                "  enabled: true\n"
                "  min_gpu_utilization_pct: 70\n"
                "  min_cpu_utilization_pct: 60\n"
                "  runtime_watchdog:\n"
                "    enabled: true\n"
                "    default_interval_seconds: 14400\n"
                "    events_path: experiments/logs/runtime_events.jsonl\n"
                "    checks_path_template: experiments/runs/{run_id}/watchdog_checks.jsonl\n"
                "    alerts_path_template: experiments/runs/{run_id}/watchdog_alerts.jsonl\n"
                "    alert_policy: record_alert_only_agent_decides_continue_fix_or_stop\n",
                encoding="utf-8",
            )
        (self.root / "experiments" / "requirements.lock").write_text("numpy==1.26.4\n", encoding="utf-8")
        values_path = self.root / "experiments" / "data" / "demo" / "values.txt"
        values_path.write_text("1\n2\n3\n", encoding="utf-8")
        (self.root / "experiments" / "data" / "demo" / "splits" / "train.txt").write_text("1\n2\n", encoding="utf-8")
        (self.root / "experiments" / "data" / "demo" / "splits" / "test.txt").write_text("3\n", encoding="utf-8")
        values_sha = hashlib.sha256(values_path.read_bytes()).hexdigest()
        (self.root / "experiments" / "data" / "dataset_manifest.yaml").write_text(
            "datasets:\n"
            "  - dataset_id: demo\n"
            "    status: complete\n"
            "    path: experiments/data/demo\n"
            "    required_files:\n"
            "      - values.txt\n"
            "      - splits/train.txt\n"
            "      - splits/test.txt\n"
            "    splits:\n"
            "      train:\n"
            "        path: splits/train.txt\n"
            "        expected_count: 2\n"
            "        actual_count: 2\n"
            "      test:\n"
            "        path: splits/test.txt\n"
            "        expected_count: 1\n"
            "        actual_count: 1\n"
            "    checksum:\n"
            "      algorithm: sha256\n"
            "      file: values.txt\n"
            f"      value: {values_sha}\n"
            "    smoke_load:\n"
            "      status: passed\n"
            "      log_path: experiments/logs/import_smoke.log\n",
            encoding="utf-8",
        )
        (self.root / "experiments" / "src" / "train.py").write_text(_code_with_enough_lines(), encoding="utf-8")
        (self.root / "knowledge" / "reviews" / "M3S02_dataset_env_review.md").write_text(
            "# M3S02 Dataset & Environment Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )
        (self.root / "experiments" / "logs" / "import_smoke.log").write_text(
            "dataset smoke load passed\n",
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
            (self.root / "experiments" / "logs" / "m3s02_longrun_ledger.md").write_text(
                "# M3S02 Long-Running Execution Ledger\n\n"
                "| Item | Execution mode | Command | Status | Log path | Patience / polling | Resume command | Permission / approval | Completion criteria |\n"
                "|------|----------------|---------|--------|----------|--------------------|----------------|-----------------------|--------------------|\n"
                f"{ledger_rows}",
                encoding="utf-8",
            )
            if execution_mode == "ssh":
                (self.root / "experiments" / "logs" / "remote_download.log").write_text(
                    "download completed; checksum passed\n",
                    encoding="utf-8",
                )
                (self.root / "experiments" / "logs" / "rsync_push.log").write_text(
                    "rsync completed; remote workspace ready\n",
                    encoding="utf-8",
                )
            else:
                (self.root / "experiments" / "logs" / "demo_download.log").write_text(
                    "download completed; checksum passed\n",
                    encoding="utf-8",
                )
                (self.root / "experiments" / "logs" / "import_smoke.log").write_text(
                    "import smoke passed\n",
                    encoding="utf-8",
                )

    def _write_m3s03_files(
        self,
        *,
        include_lock: bool = True,
        m3s04_eligible: bool = True,
        source: str = "verify-local-existing",
        comparator_type: str = "external_prior_work",
        ablation_of_ours: bool = False,
        implementation_fidelity: str = "official_code",
        fidelity_evidence: str = "",
        verification_verdict: str = "verified_match",
        caveat_waiver_reason: str = "",
        comparison_scope_limit: str = "",
        relative_deviation: float | None = None,
        paper_value: float = 0.75,
        local_value: float = 0.75,
        metric_protocol_id: str = "mp_demo_accuracy",
        scenario: str = "classification",
        direction: str = "higher_is_better",
        include_metric_protocol: bool = True,
        normal_reference_range: tuple[float, float] = (0.5, 0.95),
        metric_validation_status: str = "pass",
        include_metric_validation_evidence: bool = True,
        checkpoint_required: bool = False,
        checkpoint_verified: bool = False,
        checkpoint_file_exists: bool = True,
    ) -> None:
        for rel in (
            "knowledge/M2",
            "knowledge/M3",
            "knowledge/reviews",
            "experiments/baselines/baseline_1",
            "experiments/baselines/baseline_1/logs",
        ):
            (self.root / rel).mkdir(parents=True, exist_ok=True)

        if include_metric_protocol:
            (self.root / "knowledge" / "M2" / "M2S05_metric_protocol.yaml").write_text(
                "schema_version: 1\n"
                "metric_protocols:\n"
                f"  - metric_protocol_id: {metric_protocol_id}\n"
                "    dataset: demo\n"
                f"    scenario: {scenario}\n"
                "    split: test\n"
                "    metric_key: accuracy\n"
                "    definition: fraction of correct labels\n"
                "    calculation: correct / total over the test split\n"
                f"    direction: {direction}\n"
                "    value_range: [0.0, 1.0]\n"
                f"    normal_reference_range: [{normal_reference_range[0]}, {normal_reference_range[1]}]\n"
                "    protocol_source:\n"
                "      source_id: PaperX\n"
                "      table_or_section: Table 1\n"
                "      rationale: standard classification metric for demo\n"
                "    metric_sanity_check:\n"
                "      test_case: two correct out of four examples\n"
                "      expected_value: 0.5\n"
                "      tolerance: 1.0e-6\n",
                encoding="utf-8",
            )

        if include_metric_validation_evidence:
            (self.root / "experiments" / "baselines" / "baseline_1" / "logs" / "metric_sanity.log").write_text(
                "metric sanity passed: 2/4 accuracy = 0.5\n",
                encoding="utf-8",
            )
        checkpoint_rel = "experiments/baselines/baseline_1/checkpoints/model.pth"
        if checkpoint_required and checkpoint_file_exists:
            checkpoint_path = self.root / checkpoint_rel
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpoint_path.write_text("checkpoint-bytes", encoding="utf-8")
        (self.root / "experiments" / "baselines" / "baseline_1" / "logs" / "eval.log").write_text(
            f"local accuracy = {local_value}\n",
            encoding="utf-8",
        )
        deviation_value = (
            relative_deviation
            if relative_deviation is not None
            else (local_value - paper_value) / abs(paper_value if abs(paper_value) > 1e-12 else 1.0)
        )

        (self.root / "knowledge" / "M3" / "M3S03_baseline_lock.md").write_text(
            "# M3S03 Baseline Lock\n\n"
            "### Baseline 1\n"
            f"Verification path: {source}.\n"
            f"verification_verdict: {verification_verdict}.\n"
            f"metric_protocol_id: {metric_protocol_id}; scenario: {scenario}.\n"
            f"Paper value: {paper_value}; local value: {local_value}.\n\n"
            "## Smoke Test\n"
            "Smoke Test passed with correct metric computation and checkpoint loading status.\n\n",
            encoding="utf-8",
        )
        if fidelity_evidence:
            evidence_path = self.root / fidelity_evidence
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text("# Fidelity Report\n\nArchitecture and config match the paper.\n", encoding="utf-8")
        (self.root / "experiments" / "baselines" / "baseline_1" / "metric_contract.yaml").write_text(
            "baseline_id: baseline_1\n"
            f"verification_verdict: {verification_verdict}\n"
            f"metric_protocol_id: {metric_protocol_id}\n"
            "dataset: demo\n"
            f"scenario: {scenario}\n"
            "split: test\n"
            "metrics:\n"
            "  primary:\n"
            "    key: accuracy\n"
            f"    value: {local_value}\n"
            f"    direction: {direction}\n"
            "reference_result:\n"
            f"  value: {paper_value}\n"
            "  source: paper\n"
            "  dataset: demo\n"
            f"  scenario: {scenario}\n"
            "  split: test\n"
            "  metric: accuracy\n"
            "  table_or_section: Table 1\n"
            "local_validation:\n"
            "  command: python eval.py --metric accuracy\n"
            "  raw_log_path: experiments/baselines/baseline_1/logs/eval.log\n"
            f"  local_value: {local_value}\n"
            "deviation:\n"
            f"  relative_delta: {deviation_value}\n"
            "  tolerance: 0.10\n"
            f"  passed: {'true' if abs(deviation_value) <= 0.10 else 'false'}\n"
            "metric_validation:\n"
            f"  status: {metric_validation_status}\n"
            "  evidence_path: experiments/baselines/baseline_1/logs/metric_sanity.log\n",
            encoding="utf-8",
        )
        if include_lock:
            (self.root / "experiments" / "baselines" / "baseline_lock.yaml").write_text(
                "schema_version: 1\n"
                "baseline_code_immutable_after_lock: true\n"
                "baselines:\n"
                "  - baseline_id: baseline_1\n"
                "    name: Demo baseline\n"
                "    comparison_role: primary\n"
                f"    source: {source}\n"
                f"    comparator_type: {comparator_type}\n"
                f"    ablation_of_ours: {'true' if ablation_of_ours else 'false'}\n"
                f"    implementation_fidelity: {implementation_fidelity}\n"
                f"    fidelity_evidence: \"{fidelity_evidence}\"\n"
                "    implementation_path: experiments/baselines/baseline_1/\n"
                "    metric_contract: experiments/baselines/baseline_1/metric_contract.yaml\n"
                f"    metric_protocol_id: {metric_protocol_id}\n"
                "    dataset: demo\n"
                f"    scenario: {scenario}\n"
                "    split: test\n"
                "    metric: accuracy\n"
                f"    direction: {direction}\n"
                f"    paper_value: {paper_value}\n"
                f"    local_value: {local_value}\n"
                f"    relative_deviation: {deviation_value}\n"
                "    reference_result:\n"
                f"      value: {paper_value}\n"
                "      source: paper\n"
                "      dataset: demo\n"
                f"      scenario: {scenario}\n"
                "      split: test\n"
                "      metric: accuracy\n"
                "      table_or_section: Table 1\n"
                "    local_validation:\n"
                "      command: python eval.py --metric accuracy\n"
                "      raw_log_path: experiments/baselines/baseline_1/logs/eval.log\n"
                f"      local_value: {local_value}\n"
                "    deviation:\n"
                f"      relative_delta: {deviation_value}\n"
                "      tolerance: 0.10\n"
                f"      passed: {'true' if abs(deviation_value) <= 0.10 else 'false'}\n"
                "    metric_validation:\n"
                f"      status: {metric_validation_status}\n"
                "      evidence_path: experiments/baselines/baseline_1/logs/metric_sanity.log\n"
                f"    verification_verdict: {verification_verdict}\n"
                f"    m3s04_eligible: {'true' if m3s04_eligible else 'false'}\n"
                f"    caveat_waiver_reason: \"{caveat_waiver_reason}\"\n"
                f"    comparison_scope_limit: \"{comparison_scope_limit}\"\n"
                "    checkpoint:\n"
                f"      required: {'true' if checkpoint_required else 'false'}\n"
                f"      status: {'verified_loadable' if checkpoint_verified else 'not_applicable'}\n"
                f"      verified_loadable: {'true' if checkpoint_verified else 'false'}\n"
                f"      source_url: {'https://example.test/model.pth' if checkpoint_required else ''}\n"
                f"      local_path: {checkpoint_rel if checkpoint_required else ''}\n"
                f"      checksum: {'sha256:demo' if checkpoint_required else ''}\n"
                "      search_attempts:\n"
                f"        - official_release: {'attempted' if checkpoint_required else 'not_applicable'}\n"
                f"        - huggingface: {'attempted' if checkpoint_required else 'not_applicable'}\n"
                "m3s04_contract:\n"
                "  primary_baseline_id: baseline_1\n"
                "  metric_contract: experiments/baselines/baseline_1/metric_contract.yaml\n"
                "  dataset: demo\n"
                f"  scenario: {scenario}\n"
                "  split: test\n"
                "  metric: accuracy\n"
                f"  metric_protocol_id: {metric_protocol_id}\n",
                encoding="utf-8",
            )
        (self.root / "knowledge" / "reviews" / "M3S03_baseline_result_review.md").write_text(
            "# M3S03 Baseline Result Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )
        (self.root / "knowledge" / "reviews" / "M3S03_baseline_lock_audit.md").write_text(
            "# M3S03 Baseline Lock Audit\n\nVerdict: PASS\n",
            encoding="utf-8",
        )

    def _write_m3s05_report(self, *, decision: str = "KEEP", complete: bool = True) -> None:
        (self.root / "knowledge" / "M3").mkdir(parents=True, exist_ok=True)
        if not complete:
            text = f"# M3S05 Result Validation\n\nDecision: {decision}\n"
        else:
            text = (
                "# M3S05 Result Validation\n\n"
                "## 实验停止原因\n"
                "停止条件: budget complete. 当前 best 指标: accuracy=0.803. Evidence Ladder: solid.\n\n"
                "## 数据质量检查\n"
                "过拟合 normal; 数据泄露 none; 训练稳定性 stable; 可复现 with fixed seed=42 config/logs.\n\n"
                "## 固定 Seed 单次结果验证\n"
                "fixed seed=42 single-run validation; no p-value or mean/std claimed; Ours improves accuracy by +0.05 at seed 42.\n\n"
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
                "negative result: no cross-seed stability is claimed because only fixed seed=42 is used.\n\n"
                "## Evidence Artifact 打包\n"
                "Artifact 清单: manifest.yaml, metric_contract.yaml, comparison_table.csv, reproduction.md.\n\n"
                "## 已知限制\n"
                "局限性: single benchmark only.\n\n"
                "## 传递给下游的信息\n"
                "M4 analysis direction: 消融 ablation, 鲁棒 robustness, 机制 mechanism; handoff required.\n"
            )
        (self.root / "knowledge" / "M3" / "M3S05_result_validation.md").write_text(text, encoding="utf-8")

    def _write_m3s05_review(self, *, verdict: str = "PASS") -> None:
        (self.root / "knowledge" / "reviews").mkdir(parents=True, exist_ok=True)
        (self.root / "knowledge" / "reviews" / "M3S05_result_validation_review.md").write_text(
            f"# M3S05 Result Validation Review\n\nVerdict: {verdict}\n",
            encoding="utf-8",
        )

    def _write_m3s04_files(
        self,
        *,
        include_monitor: bool = True,
        include_watchdog: bool = True,
        multi_gpu: bool = False,
    ) -> None:
        for rel in (
            "knowledge/M3",
            "knowledge/reviews",
            "experiments/configs",
            "experiments/logs",
            "experiments/runs/run_001",
            "experiments/runs/run_001/checkpoints",
        ):
            (self.root / rel).mkdir(parents=True, exist_ok=True)

        strategy_text = "DDP torchrun" if multi_gpu else "cpu_parallel task_parallel"
        (self.root / "knowledge" / "M3" / "M3S04_main_experiment.md").write_text(
            "# M3S04 Main Experiment\n\n"
            "## Run Contract\n"
            "Resource Plan: `experiments/configs/resource_plan.yaml`.\n\n"
            "## 实验环境\n"
            f"Resource utilization uses {strategy_text}; dataloader workers and thread env are applied.\n\n"
            "## 资源利用率执行记录\n"
            "| Run ID | Resource monitor | 平均 GPU 利用率 | 平均 CPU 利用率 | 低利用率处理 |\n"
            "|--------|------------------|----------------|----------------|--------------|\n"
            "| run_001 | `experiments/runs/run_001/resource_monitor.csv` | 82% | 74% | optimized |\n\n"
            "## Runtime Watchdog 与告警记录\n"
            "`experiments/logs/runtime_events.jsonl` and "
            "`experiments/runs/run_001/watchdog_checks.jsonl` record periodic 巡检. "
            "Watchdog only records alerts and does not automatically terminate the run. "
            "Agent 决策: continue because no NaN/Inf, OOM, non-convergence, or early_stop alert was observed.\n\n"
            "## Trained-Weight Evidence Contract\n"
            "Final proposed result uses trained checkpoint `experiments/runs/run_001/checkpoints/best.pt`; "
            "runtime_events.jsonl records training_completed for run_001.\n\n"
            "## Baseline 结果\n"
            "baseline rows are included.\n\n"
            "## 迭代循环记录\n"
            "Iteration 1 includes resource_monitor.csv and no low utilization blocker.\n\n"
            "## Evidence Ladder\n"
            "minimum and solid reached.\n\n"
            "## 随机种子\n"
            "Seed: 42.\n",
            encoding="utf-8",
        )
        gpu_block = (
            "  gpus:\n"
            "    - index: 0\n"
            "      name: GPU0\n"
            "      memory_total_mb: 24576\n"
            "    - index: 1\n"
            "      name: GPU1\n"
            "      memory_total_mb: 24576\n"
            if multi_gpu
            else "  gpus: []\n"
        )
        gpu_count = 2 if multi_gpu else 0
        device_mode = "distributed_data_parallel" if multi_gpu else "cpu_parallel"
        command = (
            "torchrun --standalone --nproc_per_node=2 experiments/src/train.py --config experiments/configs/main_exp.yaml"
            if multi_gpu
            else "python experiments/src/train.py --config experiments/configs/main_exp.yaml --device cpu"
        )
        (self.root / "experiments" / "configs" / "resource_plan.yaml").write_text(
            "schema_version: 1\n"
            "available:\n"
            "  cpu:\n"
            "    cores: 8\n"
            f"{gpu_block}"
            "allocation:\n"
            "  cpu_cores: 8\n"
            f"  gpu_count: {gpu_count}\n"
            f"  gpu_ids: {'[0, 1]' if multi_gpu else '[]'}\n"
            "strategy:\n"
            f"  device_mode: {device_mode}\n"
            f"  gpu_parallelism: {'ddp' if multi_gpu else 'none'}\n"
            "  config_or_task_parallelism: true\n"
            "  dataloader:\n"
            "    num_workers: 4\n"
            "    pin_memory: true\n"
            "launch:\n"
            f"  command_template: {command}\n"
            "monitoring:\n"
            "  enabled: true\n"
            "  min_gpu_utilization_pct: 70\n"
            "  min_cpu_utilization_pct: 60\n"
            "  runtime_watchdog:\n"
            "    enabled: true\n"
            "    default_interval_seconds: 14400\n"
            "    events_path: experiments/logs/runtime_events.jsonl\n"
            "    checks_path_template: experiments/runs/{run_id}/watchdog_checks.jsonl\n"
            "    alerts_path_template: experiments/runs/{run_id}/watchdog_alerts.jsonl\n"
            "    alert_policy: record_alert_only_agent_decides_continue_fix_or_stop\n",
            encoding="utf-8",
        )
        (self.root / "experiments" / "results.tsv").write_text(
            "method\trun_id\tseed\tmetric\tvalue\trun_status\tweight_state\tcheckpoint_path\ttraining_steps\tresource_monitor\n"
            "baseline\tbaseline_run\t42\taccuracy\t0.70\tcompleted\tnot_applicable\t\t0\texperiments/runs/run_001/resource_monitor.csv\n"
            "ours\trun_001\t42\taccuracy\t0.80\tcompleted\ttrained_checkpoint\texperiments/runs/run_001/checkpoints/best.pt\t120\texperiments/runs/run_001/resource_monitor.csv\n",
            encoding="utf-8",
        )
        (self.root / "experiments" / "runs" / "run_001" / "checkpoints" / "best.pt").write_text(
            "trained checkpoint placeholder\n",
            encoding="utf-8",
        )
        if include_monitor:
            (self.root / "experiments" / "runs" / "run_001" / "resource_monitor.csv").write_text(
                "timestamp,command_pid,cpu_load_pct,mem_available_mb,gpu_index,gpu_util_pct,gpu_mem_used_mb,gpu_mem_total_mb\n"
                "2026-05-29T12:00:00,123,74,16000,0,82,8000,24576\n",
                encoding="utf-8",
            )
        if include_watchdog:
            watchdog_event = (
                '{"timestamp":"2026-05-29T12:00:00","stage":"M3S04","event_type":"watchdog_check",'
                '"run_id":"run_001","severity":"info","decision_required":false,'
                '"agent_action_policy":"record_alert_only_agent_decides_continue_fix_or_stop","signals":[]}\n'
                '{"timestamp":"2026-05-29T12:30:00","stage":"M3S04","event_type":"training_completed",'
                '"run_id":"run_001","status":"completed","checkpoint_path":"experiments/runs/run_001/checkpoints/best.pt"}\n'
            )
            (self.root / "experiments" / "logs" / "runtime_events.jsonl").write_text(
                watchdog_event,
                encoding="utf-8",
            )
            (self.root / "experiments" / "runs" / "run_001" / "watchdog_checks.jsonl").write_text(
                watchdog_event,
                encoding="utf-8",
            )
        (self.root / "knowledge" / "reviews" / "M3S04_main_result_review.md").write_text(
            "# M3S04 Main Result Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )

    def _write_m3s05_artifacts(self) -> None:
        artifacts = self.root / "experiments" / "artifacts" / "main_experiment"
        artifacts.mkdir(parents=True, exist_ok=True)
        (self.root / "experiments" / "runs" / "run_001" / "checkpoints").mkdir(parents=True, exist_ok=True)
        (self.root / "experiments" / "runs" / "run_001" / "checkpoints" / "best.pt").write_text(
            "trained checkpoint placeholder\n",
            encoding="utf-8",
        )
        (self.root / "experiments" / "logs").mkdir(parents=True, exist_ok=True)
        (self.root / "experiments" / "logs" / "runtime_events.jsonl").write_text(
            '{"timestamp":"2026-05-29T12:30:00","stage":"M3S04","event_type":"training_completed",'
            '"run_id":"run_001","status":"completed","checkpoint_path":"experiments/runs/run_001/checkpoints/best.pt"}\n',
            encoding="utf-8",
        )
        (self.root / "experiments" / "results.tsv").write_text(
            "method\trun_id\tseed\tmetric\tvalue\trun_status\tweight_state\tcheckpoint_path\ttraining_steps\tresource_monitor\n"
            "baseline\tbaseline_run\t42\taccuracy\t0.753\tcompleted\tnot_applicable\t\t0\texperiments/runs/run_001/resource_monitor.csv\n"
            "ours\trun_001\t42\taccuracy\t0.803\tcompleted\ttrained_checkpoint\texperiments/runs/run_001/checkpoints/best.pt\t120\texperiments/runs/run_001/resource_monitor.csv\n",
            encoding="utf-8",
        )
        (artifacts / "manifest.yaml").write_text(
            "experiment_id: main_exp_v1\n"
            "method: ours\n"
            "dataset: demo\n"
            "baseline_refs:\n"
            "  - experiments/baselines/baseline_1/metric_contract.yaml\n"
            "trained_checkpoint: experiments/runs/run_001/checkpoints/best.pt\n"
            "primary_metric:\n"
            "  key: accuracy\n"
            "  value: 0.803\n"
            "seed: 42\n"
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
            "",
            encoding="utf-8",
        )
        (artifacts / "comparison_table.csv").write_text(
            "method,seed,metric,value\n"
            "baseline,42,accuracy,0.753\n"
            "ours,42,accuracy,0.803\n",
            encoding="utf-8",
        )
        (artifacts / "reproduction.md").write_text(
            "# Reproduction\n\nRun the main experiment with seed 42.\n",
            encoding="utf-8",
        )

    def _write_m3s05_handoff(self) -> None:
        (self.root / "knowledge").mkdir(parents=True, exist_ok=True)
        (self.root / "knowledge" / "handoff_M3_M4.md").write_text(
            "# Handoff M3 to M4\n\n"
            "Decision: KEEP; validated by M3S05 result validation.\n\n"
            "## Claims and Evidence\n"
            "claim C1: ours improves accuracy; evidence: experiments/artifacts/main_experiment/manifest.yaml and comparison_table.csv.\n\n"
            "## M4 Analysis\n"
            "M4 analysis should cover 消融, 鲁棒, and 机制 checks using experiments/artifacts/main_experiment/.\n",
            encoding="utf-8",
        )

    def test_m3s02_stage_gate_accepts_longrun_ledger(self) -> None:
        self._write_m3s02_files(include_ledger=True)

        ok, messages = check_stage(self.root, "M3S02")

        self.assertTrue(ok, "\n".join(messages))
        self.assertTrue(any("long-running ledger includes" in message for message in messages))

    def test_m3s02_stage_gate_requires_longrun_ledger(self) -> None:
        self._write_m3s02_files(include_ledger=False)

        ok, messages = check_stage(self.root, "M3S02")

        self.assertFalse(ok)
        self.assertTrue(any("long-running execution ledger missing" in message for message in messages))

    def test_m3s02_stage_gate_requires_sandbox_profile(self) -> None:
        self._write_m3s02_files(include_ledger=True, include_sandbox=False)

        ok, messages = check_stage(self.root, "M3S02")

        self.assertFalse(ok)
        self.assertTrue(any("execution.sandbox profile missing" in message for message in messages))
        self.assertTrue(any("sandbox_profile.yaml not found" in message for message in messages))

    def test_m3s02_stage_gate_requires_resource_plan(self) -> None:
        self._write_m3s02_files(include_ledger=True, include_resource_plan=False)

        ok, messages = check_stage(self.root, "M3S02")

        self.assertFalse(ok)
        self.assertTrue(any("resource_plan.yaml not found" in message for message in messages), messages)

    def test_m3s02_stage_gate_requires_dataset_manifest(self) -> None:
        self._write_m3s02_files(include_ledger=True)
        (self.root / "experiments" / "data" / "dataset_manifest.yaml").unlink()

        ok, messages = check_stage(self.root, "M3S02")

        self.assertFalse(ok)
        self.assertTrue(any("dataset_manifest.yaml not found" in message for message in messages), messages)

    def test_m3s02_stage_gate_rejects_incomplete_dataset_manifest(self) -> None:
        self._write_m3s02_files(include_ledger=True)
        manifest = self.root / "experiments" / "data" / "dataset_manifest.yaml"
        text = manifest.read_text(encoding="utf-8")
        text = text.replace("actual_count: 1", "actual_count: 0", 1)
        manifest.write_text(text, encoding="utf-8")

        ok, messages = check_stage(self.root, "M3S02")

        self.assertFalse(ok)
        self.assertTrue(any("actual_count/count must be > 0" in message for message in messages), messages)

    def test_m3s02_stage_gate_requires_local_or_ssh_mode(self) -> None:
        self._write_m3s02_files(include_ledger=True, execution_mode="cluster")

        ok, messages = check_stage(self.root, "M3S02")

        self.assertFalse(ok)
        self.assertTrue(any("execution.mode must be explicitly local or ssh" in message for message in messages), messages)

    def test_m3s04_stage_gate_accepts_multi_resource_allocation(self) -> None:
        self._write_m3s04_files(include_monitor=True, include_watchdog=True)
        (self.root / "experiments" / "runs" / "run_002").mkdir(parents=True, exist_ok=True)
        (self.root / "experiments" / "runs" / "run_002" / "checkpoints").mkdir(parents=True, exist_ok=True)
        (self.root / "experiments" / "runs" / "run_002" / "checkpoints" / "best.pt").write_text(
            "trained checkpoint placeholder\n",
            encoding="utf-8",
        )
        (self.root / "experiments" / "runs" / "run_002" / "resource_monitor.csv").write_text(
            "timestamp,command_pid,cpu_load_pct,mem_available_mb,gpu_index,gpu_util_pct,gpu_mem_used_mb,gpu_mem_total_mb\n"
            "2026-05-29T12:00:00,124,70,16000,0,80,8000,24576\n",
            encoding="utf-8",
        )
        (self.root / "knowledge" / "M3" / "M3S04_main_experiment.md").write_text(
            "# M3S04 Main Experiment\n\n"
            "## Run Contract\nResource Plan: `experiments/configs/resource_plan.yaml`; "
            "multi-resource allocation: `experiments/configs/m3_task_allocation.yaml`.\n\n"
            "## 实验环境\nresource_id/local and ssh:lab-a server_id lab-a are used with sync push/pull evidence.\n\n"
            "## 资源利用率执行记录\n"
            "| Run ID | resource_id | resource_kind | Resource monitor | 低利用率处理 |\n"
            "|---|---|---|---|---|\n"
            "| run_001 | local | local | `experiments/runs/run_001/resource_monitor.csv` | none |\n"
            "| run_002 | ssh:lab-a | ssh | `experiments/runs/run_002/resource_monitor.csv` | sync completed |\n\n"
            "## Runtime Watchdog 与告警记录\n"
            "`experiments/logs/runtime_events.jsonl` and watchdog checks record periodic 巡检. "
            "Watchdog only records alerts and does not automatically terminate the run. Agent 决策: continue.\n\n"
            "## Trained-Weight Evidence Contract\n"
            "Final proposed result uses trained checkpoint `experiments/runs/run_002/checkpoints/best.pt`; "
            "runtime_events.jsonl records training_completed for run_002.\n\n"
            "## Baseline 结果\nbaseline rows are included.\n\n"
            "## 迭代循环记录\niterations with resource_monitor.csv.\n\n"
            "## Evidence Ladder\nminimum and solid reached.\n\n"
            "## 随机种子\nSeed: 42.\n",
            encoding="utf-8",
        )
        (self.root / "experiments" / "configs" / "resource_plan.yaml").write_text(
            "schema_version: 1\n"
            "available:\n"
            "  cpu: {cores: 8}\n"
            "  gpus: []\n"
            "allocation:\n"
            "  cpu_cores: 8\n"
            "  gpu_count: 0\n"
            "  gpu_ids: []\n"
            "strategy:\n"
            "  device_mode: task_parallel\n"
            "  dataloader: {num_workers: 4}\n"
            "launch:\n"
            "  command_template: python experiments/src/train.py\n"
            "monitoring:\n"
            "  enabled: true\n"
            "  min_gpu_utilization_pct: 70\n"
            "  min_cpu_utilization_pct: 60\n"
            "resource_pool:\n"
            "  enabled: true\n"
            "  task_allocation_policy: dependency_aware_task_parallel\n"
            "  parallelism_contract:\n"
            "    fairness_policy: baseline_and_ours_same_resource_class\n"
            "    result_sync_policy: remote pull logs monitors artifacts\n"
            "  resources:\n"
            "    - resource_id: local\n"
            "      kind: local\n"
            "      cpu_cores: 8\n"
            "      gpu_count: 0\n"
            "      gpu_ids: []\n"
            "    - resource_id: ssh:lab-a\n"
            "      kind: ssh\n"
            "      server_id: lab-a\n"
            "      lease_id: lease-a\n"
            "      workspace_path: ~/AutoPaper2/projects/demo\n"
            "      cpu_cores: 16\n"
            "      gpu_count: 1\n"
            "      gpu_ids: ['0']\n"
            "      sync_required: true\n",
            encoding="utf-8",
        )
        (self.root / "experiments" / "configs" / "m3_task_allocation.yaml").write_text(
            "schema_version: 1\n"
            "assignments:\n"
            "  - task_id: run_001\n"
            "    resource_id: local\n"
            "    resource_kind: local\n"
            "    gpu_ids: []\n"
            "    resource_monitor: experiments/runs/run_001/resource_monitor.csv\n"
            "  - task_id: run_002\n"
            "    resource_id: ssh:lab-a\n"
            "    resource_kind: ssh\n"
            "    server_id: lab-a\n"
            "    gpu_ids: ['0']\n"
            "    resource_monitor: experiments/runs/run_002/resource_monitor.csv\n"
            "waves:\n"
            "  - wave: 0\n"
            "    parallel_assignments: [run_001, run_002]\n"
            "blocked_tasks: []\n",
            encoding="utf-8",
        )
        (self.root / "experiments" / "results.tsv").write_text(
            "method\trun_id\tseed\tmetric\tvalue\trun_status\tweight_state\tcheckpoint_path\ttraining_steps\tresource_id\tresource_kind\tresource_monitor\n"
            "baseline\tbaseline_run\t42\taccuracy\t0.70\tcompleted\tnot_applicable\t\t0\tlocal\tlocal\texperiments/runs/run_001/resource_monitor.csv\n"
            "ours\trun_002\t42\taccuracy\t0.80\tcompleted\ttrained_checkpoint\texperiments/runs/run_002/checkpoints/best.pt\t120\tssh:lab-a\tssh\texperiments/runs/run_002/resource_monitor.csv\n",
            encoding="utf-8",
        )
        (self.root / "experiments" / "logs" / "runtime_events.jsonl").write_text(
            (self.root / "experiments" / "logs" / "runtime_events.jsonl").read_text(encoding="utf-8")
            + '{"timestamp":"2026-05-29T13:00:00","stage":"M3S04","event_type":"training_completed",'
            '"run_id":"run_002","status":"completed","checkpoint_path":"experiments/runs/run_002/checkpoints/best.pt"}\n',
            encoding="utf-8",
        )

        ok, messages = check_stage(self.root, "M3S04")

        self.assertTrue(ok, "\n".join(messages))
        self.assertTrue(any("multi-resource pool enabled" in message for message in messages), messages)

    def test_m3s02_stage_gate_requires_local_env_fields(self) -> None:
        self._write_m3s02_files(include_ledger=True, local_env_manager="")

        ok, messages = check_stage(self.root, "M3S02")

        self.assertFalse(ok)
        self.assertTrue(any("local env_manager must be conda/venv/uv/docker" in message for message in messages), messages)

    def test_m3s02_stage_gate_requires_ssh_connection_fields(self) -> None:
        self._write_m3s02_files(include_ledger=True, execution_mode="ssh")

        ok, messages = check_stage(self.root, "M3S02")

        self.assertFalse(ok)
        self.assertTrue(any("ssh host missing" in message for message in messages), messages)
        self.assertTrue(any("ssh user missing" in message for message in messages), messages)
        self.assertTrue(any("ssh workspace_path missing" in message for message in messages), messages)

    def test_m3s02_stage_gate_accepts_ssh_execution_config(self) -> None:
        self._write_m3s02_files(
            include_ledger=True,
            execution_mode="ssh",
            ssh_host="gpu.example",
            ssh_user="user",
            ssh_workspace_path="~/AutoPaper2/projects/demo",
        )

        ok, messages = check_stage(self.root, "M3S02")

        self.assertTrue(ok, "\n".join(messages))
        self.assertTrue(any("implementation doc records ssh/remote execution mode" in message for message in messages), messages)
        self.assertTrue(any("SSH mode ledger includes remote execution/rsync evidence" in message for message in messages), messages)

    def test_m3s02_stage_gate_blocks_incomplete_dataset_download(self) -> None:
        self._write_m3s02_files()
        ledger = self.root / "experiments" / "logs" / "m3s02_longrun_ledger.md"
        text = ledger.read_text(encoding="utf-8")
        text = text.replace("| completed | `experiments/logs/demo_download.log`", "| blocked_user_action | `experiments/logs/demo_download.log`", 1)
        ledger.write_text(text, encoding="utf-8")

        ok, messages = check_stage(self.root, "M3S02")

        self.assertFalse(ok)
        self.assertTrue(any("acquisition task dataset: demo is not completed" in message for message in messages), messages)

    def test_m3s03_stage_gate_accepts_baseline_lock_manifest(self) -> None:
        self._write_m3s03_files()

        ok, messages = check_stage(self.root, "M3S03")

        self.assertTrue(ok, "\n".join(messages))
        self.assertTrue(any("primary baseline(s) eligible for M3S04" in message for message in messages), messages)
        self.assertTrue(any("stage review m3_baseline_lock_audit PASS" in message for message in messages), messages)

    def test_m3s03_stage_gate_rejects_alternate_review_copy(self) -> None:
        self._write_m3s03_files()
        (self.root / "knowledge" / "reviews" / "M3S03_baseline_result_review_revised.md").write_text(
            "# M3S03 Baseline Result Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )

        ok, messages = check_stage(self.root, "M3S03")

        self.assertFalse(ok)
        self.assertTrue(any("alternate stage review file" in message for message in messages), messages)

    def test_stage_review_pass_cannot_contain_blocking_download_language(self) -> None:
        self._write_m3s03_files()
        (self.root / "knowledge" / "reviews" / "M3S03_baseline_result_review.md").write_text(
            "# M3S03 Baseline Result Review\n\n"
            "Verdict: PASS\n\n"
            "Checkpoint download pending; should be okay to proceed.\n",
            encoding="utf-8",
        )

        ok, messages = check_stage(self.root, "M3S03")

        self.assertFalse(ok)
        self.assertTrue(any("PASS verdict but contains blocking/ambiguous language" in message for message in messages), messages)

    def test_m3s03_stage_gate_requires_baseline_lock_manifest(self) -> None:
        self._write_m3s03_files(include_lock=False)

        ok, messages = check_stage(self.root, "M3S03")

        self.assertFalse(ok)
        self.assertTrue(any("baseline_lock.yaml not found" in message for message in messages), messages)

    def test_m3s03_stage_gate_requires_primary_eligible_baseline(self) -> None:
        self._write_m3s03_files(m3s04_eligible=False)

        ok, messages = check_stage(self.root, "M3S03")

        self.assertFalse(ok)
        self.assertTrue(any("primary baseline must set m3s04_eligible" in message for message in messages), messages)

    def test_m3s03_stage_gate_requires_caveat_waiver_for_trusted_baseline(self) -> None:
        self._write_m3s03_files(verification_verdict="trusted_with_caveats")

        ok, messages = check_stage(self.root, "M3S03")

        self.assertFalse(ok)
        self.assertTrue(any("trusted_with_caveats requires caveat_waiver_reason" in message for message in messages), messages)

    def test_m3s03_stage_gate_requires_m2_metric_protocol(self) -> None:
        self._write_m3s03_files(include_metric_protocol=False)

        ok, messages = check_stage(self.root, "M3S03")

        self.assertFalse(ok)
        self.assertTrue(any("metric protocol registry not found" in message for message in messages), messages)

    def test_m3s03_stage_gate_rejects_metric_protocol_mismatch(self) -> None:
        self._write_m3s03_files()
        for rel in (
            "experiments/baselines/baseline_1/metric_contract.yaml",
            "experiments/baselines/baseline_lock.yaml",
        ):
            path = self.root / rel
            text = path.read_text(encoding="utf-8")
            text = text.replace("scenario: classification", "scenario: regression")
            path.write_text(text, encoding="utf-8")

        ok, messages = check_stage(self.root, "M3S03")

        self.assertFalse(ok)
        self.assertTrue(any("scenario=regression does not match M2 metric protocol classification" in message for message in messages), messages)

    def test_m3s03_stage_gate_rejects_metric_validation_failure(self) -> None:
        self._write_m3s03_files(metric_validation_status="fail")

        ok, messages = check_stage(self.root, "M3S03")

        self.assertFalse(ok)
        self.assertTrue(any("metric_validation status must be pass" in message for message in messages), messages)

    def test_m3s03_stage_gate_requires_checkpoint_file_when_needed(self) -> None:
        self._write_m3s03_files(
            checkpoint_required=True,
            checkpoint_verified=True,
            checkpoint_file_exists=False,
        )

        ok, messages = check_stage(self.root, "M3S03")

        self.assertFalse(ok)
        self.assertTrue(any("required checkpoint local_path missing or does not exist" in message for message in messages), messages)

    def test_m3s03_stage_gate_rejects_weird_metric_value_without_triage(self) -> None:
        self._write_m3s03_files(paper_value=0.99, local_value=0.99)

        ok, messages = check_stage(self.root, "M3S03")

        self.assertFalse(ok)
        self.assertTrue(any("outside normal_reference_range" in message for message in messages), messages)

    def test_m3s03_stage_gate_rejects_ablation_as_baseline(self) -> None:
        self._write_m3s03_files(ablation_of_ours=True, comparator_type="ablation")

        ok, messages = check_stage(self.root, "M3S03")

        self.assertFalse(ok)
        self.assertTrue(any("cannot be an ablation" in message for message in messages), messages)

    def test_m3s03_stage_gate_rejects_simplified_reimplementation(self) -> None:
        self._write_m3s03_files(
            source="reimplementation",
            implementation_fidelity="simplified",
            fidelity_evidence="experiments/baselines/baseline_1/fidelity_report.md",
        )

        ok, messages = check_stage(self.root, "M3S03")

        self.assertFalse(ok)
        joined = "\n".join(messages)
        self.assertIn("simplified/toy/minimal baseline implementations are forbidden", joined)
        self.assertIn("reimplemented baselines must set implementation_fidelity", joined)

    def test_m3s04_stage_gate_accepts_resource_monitor(self) -> None:
        self._write_m3s04_files(include_monitor=True, multi_gpu=True)

        ok, messages = check_stage(self.root, "M3S04")

        self.assertTrue(ok, "\n".join(messages))
        self.assertTrue(any("resource monitor file" in message for message in messages), messages)
        self.assertTrue(any("multi-GPU execution strategy documented" in message for message in messages), messages)
        self.assertTrue(any("runtime_events.jsonl has" in message for message in messages), messages)
        self.assertTrue(any("watchdog check file" in message for message in messages), messages)

    def test_m3s04_stage_gate_requires_resource_monitor(self) -> None:
        self._write_m3s04_files(include_monitor=False)

        ok, messages = check_stage(self.root, "M3S04")

        self.assertFalse(ok)
        self.assertTrue(any("no resource_monitor.csv found" in message for message in messages), messages)

    def test_m3s04_stage_gate_requires_runtime_watchdog(self) -> None:
        self._write_m3s04_files(include_watchdog=False)

        ok, messages = check_stage(self.root, "M3S04")

        self.assertFalse(ok)
        joined = "\n".join(messages)
        self.assertIn("runtime_events.jsonl missing", joined)
        self.assertIn("no watchdog_checks.jsonl found", joined)

    def test_m3s04_stage_gate_rejects_random_or_running_weights(self) -> None:
        self._write_m3s04_files(include_monitor=True, include_watchdog=True)
        (self.root / "experiments" / "results.tsv").write_text(
            "method\trun_id\tseed\tmetric\tvalue\trun_status\tweight_state\tcheckpoint_path\ttraining_steps\tresource_monitor\n"
            "baseline\tbaseline_run\t42\taccuracy\t0.70\tcompleted\tnot_applicable\t\t0\texperiments/runs/run_001/resource_monitor.csv\n"
            "ours\trun_001\t42\taccuracy\t0.80\trunning\trandom_init\texperiments/runs/run_001/checkpoints/best.pt\t0\texperiments/runs/run_001/resource_monitor.csv\n",
            encoding="utf-8",
        )

        ok, messages = check_stage(self.root, "M3S04")

        self.assertFalse(ok)
        joined = "\n".join(messages)
        self.assertIn("run_status/training_status must be completed", joined)
        self.assertIn("no proposed/ours result row is backed by completed trained weights", joined)

    def test_m3s05_stage_gate_accepts_keep_with_evidence_package(self) -> None:
        self._write_m3s05_report()
        self._write_m3s05_artifacts()
        self._write_m3s05_handoff()
        self._write_m3s05_review()

        ok, messages = check_stage(self.root, "M3S05")

        self.assertTrue(ok, "\n".join(messages))
        self.assertTrue(any("manifest.yaml records fixed seed 42" in message for message in messages))
        self.assertTrue(any("handoff_M3_M4.md includes M4 analysis direction" in message for message in messages))

    def test_m3s05_stage_gate_blocks_keep_without_evidence_package(self) -> None:
        self._write_m3s05_report()
        self._write_m3s05_review()

        ok, messages = check_stage(self.root, "M3S05")

        self.assertFalse(ok)
        joined = "\n".join(messages)
        self.assertIn("manifest missing or empty", joined)
        self.assertIn("metric contract missing or empty", joined)
        self.assertIn("comparison table missing or empty", joined)
        self.assertIn("handoff_M3_M4.md missing or empty", joined)

    def test_m3s05_stage_gate_blocks_incomplete_validation_report(self) -> None:
        self._write_m3s05_report(complete=False)
        self._write_m3s05_artifacts()
        self._write_m3s05_handoff()
        self._write_m3s05_review()

        ok, messages = check_stage(self.root, "M3S05")

        self.assertFalse(ok)
        joined = "\n".join(messages)
        self.assertIn("missing single-seed validation", joined)
        self.assertIn("missing hypothesis mapping", joined)
        self.assertIn("missing data quality checks", joined)

    def test_m3s05_stage_gate_blocks_fix_even_with_repair_advice(self) -> None:
        self._write_m3s05_report(decision="FIX")
        self._write_m3s05_review()
        doc = self.root / "knowledge" / "M3" / "M3S05_result_validation.md"
        doc.write_text(
            doc.read_text(encoding="utf-8")
            + "\n## 回溯修改方向\n"
            "- blocking_reason: validation found unstable gains\n"
            "- required_fix: rerun M3S04 with corrected fixed seed=42 configuration\n"
            "- success_criteria: stable fixed seed=42 result with matching config/logs\n"
            "- rebuild_mode: incremental_replay\n"
            "- rerun_scope: M3S04-M3S05\n",
            encoding="utf-8",
        )

        ok, messages = check_stage(self.root, "M3S05")

        self.assertFalse(ok)
        self.assertTrue(any("blocks advancement" in message for message in messages))

    def test_m3s05_stage_gate_requires_result_validation_review(self) -> None:
        self._write_m3s05_report()
        self._write_m3s05_artifacts()
        self._write_m3s05_handoff()

        ok, messages = check_stage(self.root, "M3S05")

        self.assertFalse(ok)
        self.assertTrue(any("M3S05_result_validation_review.md" in message and "missing" in message.lower() for message in messages), messages)


if __name__ == "__main__":
    unittest.main()
