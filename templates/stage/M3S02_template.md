# M3S02: Baseline Result Review

> **Stage**: M3S02
> **Agent**: Experiment Agent
> **输入**: `knowledge/M3/M3S01_implementation.md`, `knowledge/M2/M2S05_experiment_setup.md` 或等价实验计划, `knowledge/M1/M1S02_literature_deepdive.md`
> **输出**: `knowledge/M3/M3S02_baseline_lock.md` + `experiments/baselines/*/metric_contract.yaml` + `experiments/baselines/baseline_lock.yaml`
>
> **审查重点**: baseline 本地实验结果、metric contract、与论文/历史记录的偏差、smoke test 是否通过

---

## 1. Baseline 验证记录

> **硬性边界**: M3S02 只锁定外部 comparator 或完整忠实复现的 prior-work baseline。本文方法的消融、组件移除、轻量变体、调参版本、proxy/simple/toy/minimal 实现均不得进入 `baseline_lock.yaml`；消融只能在 M4 设计和执行。

### Baseline 1: [名称]

| 属性 | 内容 |
|------|------|
| 来源 | 官方代码 / pip 包 / 自行实现 |
| comparator_type | external_prior_work / official_baseline / reproduced_prior_work |
| ablation_of_ours | false |
| implementation_fidelity | official_code / official_package / full_reproduction / paper_faithful_reproduction |
| fidelity_evidence | `experiments/baselines/{id}/fidelity_report.md` 或官方 repo/config 证据 |
| 验证路径 | attach / import / verify-local-existing / reproduce / repair |
| Checkpoint 来源 | 官方 Release / README 链接 / HuggingFace / 自动下载 / 无 |
| Checkpoint 本地路径 | `experiments/baselines/{id}/checkpoints/...` |
| Checkpoint 验证状态 | 已验证加载 / 未验证 / 不适用 |
| metric_protocol_id | 来自 `knowledge/M2/M2S05_metric_protocol.yaml` |
| 场景 / Scenario | 必须与 M2 指标协议一致 |
| 官方指标（论文报告） | ... |
| 我们的运行结果 | ... |
| 偏差说明 | ... |
| 指标实现验证 | `metric_validation` 通过，证据路径存在 |
| 验证分级 | verified_match / verified_close / trusted_with_caveats / diverged |

**Checkpoint 获取记录**:
```yaml
checkpoint:
  source_url: "..."
  local_path: "experiments/baselines/{id}/checkpoints/..."
  filename: "..."
  checksum: "sha256:..."
  download_time: "..."
  auto_download: true/false
  verified_loadable: true/false
  search_attempts:
    - GitHub Releases: 是/否
    - README/文档: 是/否
    - 代码自动下载: 是/否
    - HuggingFace Hub: 是/否
    - 第三方托管: 是/否
    - 项目缓存复用: 是/否
```

**Metric Contract**:
```yaml
baseline_id: "..."
source: "..."
comparator_type: external_prior_work
ablation_of_ours: false
implementation_fidelity: official_code / full_reproduction / paper_faithful_reproduction
fidelity_evidence: "experiments/baselines/{id}/fidelity_report.md"
metric_protocol_id: "mp_..."
dataset: "..."
scenario: "..."
split: "..."
metrics:
  primary:
    key: "..."
    value: ...
    direction: "higher_is_better"
  secondary:
    - key: "..."
      value: ...
reference_result:
  source: paper / official_repo / official_checkpoint / leaderboard
  value: ...
  dataset: "..."
  scenario: "..."
  split: "..."
  metric: "..."
  table_or_section: "..."
local_validation:
  command: "..."
  config_path: "..."
  raw_log_path: "experiments/baselines/{id}/logs/eval.log"
  local_value: ...
deviation:
  relative_delta: ...
  tolerance: ...
  passed: true/false
metric_validation:
  status: pass
  evidence_path: "experiments/baselines/{id}/logs/metric_sanity.log"
  checked_against_protocol: "knowledge/M2/M2S05_metric_protocol.yaml#mp_..."
environment:
  python: "..."
  torch: "..."
  cuda: "..."
  hardware: "..."
known_deviations: "..."
verification_verdict: "..."
```

### Baseline 2: [名称]
...

---

## 2. 验证策略选择理由

| Baseline | 选择的路径 | 理由 |
|----------|-----------|------|
| Baseline-1 | reproduce | 官方代码可用，需本地运行验证 |
| Baseline-2 | attach | 之前项目已验证，metric contract 未过期 |

---

## 3. Smoke Test

### 3.1 Smoke Test 设计

- **目的**: 验证完整管道可运行，无基本错误
- **数据**: 使用 1% 训练数据 或 2 个 epoch
- **检查项**:
  - [ ] Loss 下降
  - [ ] 无 NaN/Inf
  - [ ] 指标计算正确
  - [ ] 模型保存/加载正常
  - [ ] 日志记录正常

### 3.2 Smoke Test 结果

| 检查项 | 结果 | 备注 |
|--------|------|------|
| Loss 下降 | 是/否 | ... |
| 无 NaN/Inf | 是/否 | ... |
| 指标计算 | 正确/错误 | ... |
| 保存/加载 | 正常/异常 | ... |

---

## 4. 环境一致性确认

| 维度 | Baseline 运行环境 | 本文方法运行环境 | 是否一致 |
|------|------------------|-----------------|---------|
| Python | ... | ... | 是/否 |
| PyTorch | ... | ... | 是/否 |
| CUDA | ... | ... | 是/否 |
| 硬件 | ... | ... | 是/否 |

---

## 5. 问题与修复记录

| 问题 | Baseline | 根因 | 修复措施 | 修复后状态 |
|------|---------|------|---------|-----------|
| 官方代码有 bug | Baseline-X | ... | ... | 已修复/未修复 |
| 环境依赖冲突 | Baseline-Y | ... | ... | 已解决 |

---

## 6. 传递给下游的信息

- **已验证的 baseline 列表**: ...
- **主要 baseline 的 metric contract 路径**: ...
- **Smoke test 是否通过**: ...
- **已知的环境差异**: ...
- **建议的 M3S03 Run Contract 中的比较基准**: ...

---

## 7. Baseline Lock Manifest（必须）

必须同步写入 `experiments/baselines/baseline_lock.yaml`。该文件是 M3S03 的准入契约；没有 primary 且 `m3s03_eligible: true` 的 baseline，不得进入 M3S03。

```yaml
schema_version: 1
baseline_code_immutable_after_lock: true
baselines:
  - baseline_id: baseline_1
    name: "..."
    comparison_role: primary
    source: official_code / pip_package / reimplementation / imported_project
    comparator_type: external_prior_work / official_baseline / reproduced_prior_work
    ablation_of_ours: false
    implementation_fidelity: official_code / official_package / full_reproduction / paper_faithful_reproduction
    fidelity_evidence: experiments/baselines/baseline_1/fidelity_report.md
    implementation_path: experiments/baselines/baseline_1/
    metric_contract: experiments/baselines/baseline_1/metric_contract.yaml
    metric_protocol_id: mp_...
    dataset: "..."
    scenario: "..."
    split: "..."
    metric: "accuracy"
    direction: higher_is_better
    paper_value: 0.0
    local_value: 0.0
    relative_deviation: 0.0
    reference_result:
      source: paper / official_repo / official_checkpoint / leaderboard
      value: 0.0
      dataset: "..."
      scenario: "..."
      split: "..."
      metric: "accuracy"
      table_or_section: "..."
    local_validation:
      command: "..."
      raw_log_path: experiments/baselines/baseline_1/logs/eval.log
      local_value: 0.0
    deviation:
      relative_delta: 0.0
      tolerance: 0.10
      passed: true
    metric_validation:
      status: pass
      evidence_path: experiments/baselines/baseline_1/logs/metric_sanity.log
      checked_against_protocol: knowledge/M2/M2S05_metric_protocol.yaml#mp_...
    verification_verdict: verified_match / verified_close / trusted_with_caveats
    m3s03_eligible: true
    caveat_waiver_reason: ""
    comparison_scope_limit: ""
    checkpoint:
      required: true
      source_url: "..."
      local_path: experiments/baselines/baseline_1/checkpoints/model.pth
      checksum: "sha256:..."
      verified_loadable: true
    smoke_test:
      command: "..."
      status: pass
      log_path: experiments/baselines/baseline_1/logs/smoke_test.log
m3s03_contract:
  primary_baseline_id: baseline_1
  metric_contract: experiments/baselines/baseline_1/metric_contract.yaml
  dataset: "..."
  scenario: "..."
  split: "..."
  metric: "accuracy"
  metric_protocol_id: mp_...
  run_contract_note: "M3S03 must compare against this locked baseline without changing baseline code, split, metric, or checkpoint."
```

`trusted_with_caveats` 只有在 `caveat_waiver_reason` 和 `comparison_scope_limit` 都明确时才可进入 M3S03。若 baseline 依赖 checkpoint，`checkpoint.verified_loadable` 必须为 `true`。

如果 `source: reimplementation` 或自行实现，`implementation_fidelity` 必须是 `full_reproduction`、`paper_faithful_reproduction` 或 `official_equivalent`，并且 `fidelity_evidence` 必须指向已存在的复现一致性报告。不得使用 simplified / toy / minimal / proxy baseline。

M3S02 不得重新定义指标。所有 primary baseline 必须引用 M2S05 的 `metric_protocol_id`，并与其 dataset、scenario、split、metric、direction、value_range、normal_reference_range 一致。若本地结果超出正常参考范围，必须写入 `anomaly_triage`，提供真实日志/证据路径，并根据根因 REVISE 或 BACKTRACK；不得把异常结果标成 `verified_match` 或 `verified_close` 后继续推进。
