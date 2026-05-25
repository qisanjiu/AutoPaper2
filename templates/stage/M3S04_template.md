# M3S04: Result Validation & Evidence Packaging

> **Stage**: M3S04
> **Agent**: Analysis Agent
> **输入**: `knowledge/M3/M3S03_main_experiment.md`, `knowledge/M3/M3S02_baseline_lock.md`, `experiments/results.tsv`, `knowledge/M1/M1S04_hypothesis_generation.md`
> **输出**: `knowledge/M3/M3S04_result_validation.md` + `experiments/artifacts/main_experiment/`
>
> **审查重点**: 统计验证、数据质量、诚实决策、证据打包

---

## 1. 实验停止原因

- **停止条件触发**: [指标收敛 / 预算耗尽 / 方向验证 / 外部中断]
- **总迭代次数**: N
- **当前 best 指标**: ...（vs baseline: ...）
- **Evidence Ladder 达成层级**: minimum / solid / maximum

---

## 2. 数据质量检查

### 2.1 过拟合检查

| 检查项 | 结果 | 严重程度 | 备注 |
|--------|------|---------|------|
| Train/Val gap | ... | 正常/警告/严重 | ... |
| 学习曲线分析 | ... | 正常/警告/严重 | ... |

### 2.2 数据泄露检查

| 检查项 | 结果 | 严重程度 | 备注 |
|--------|------|---------|------|
| 预处理管道隔离性 | ... | 正常/警告/严重 | ... |
| 验证集信息是否间接用于训练 | ... | 否/是 | ... |

### 2.3 训练稳定性检查

| 检查项 | 结果 | 严重程度 | 备注 |
|--------|------|---------|------|
| Loss 曲线异常 | ... | 正常/警告/严重 | ... |
| NaN/Inf 出现 | ... | 正常/警告/严重 | ... |
| 梯度爆炸/消失 | ... | 正常/警告/严重 | ... |

### 2.4 可复现性检查

| 检查项 | 结果 | 备注 |
|--------|------|------|
| 同 seed 重复运行一致性 | ... | ... |

---

## 3. 统计显著性检验

### 3.1 检验方法选择

- **选择的方法**: [t-test / Wilcoxon signed-rank / Bootstrap / 其他]
- **选择理由**: [数据分布、样本量、对比类型]

### 3.2 检验结果

| 对比 | 检验方法 | p-value | 效应量 | 95% 置信区间 | 结论 |
|------|---------|---------|--------|------------|------|
| Ours vs Baseline-1 | ... | ... | Cohen's d = ... | [...] | 显著优于 / 不显著 |
| Ours vs Baseline-2 | ... | ... | Cohen's d = ... | [...] | 显著优于 / 不显著 |

### 3.3 多重比较校正

- **比较次数**: ...
- **校正方法**: [Bonferroni / FDR / Holm / 无]
- **校正后显著性**: ...

---

## 4. 与假设的对应验证

| 假设 | 预期结果 | 实际结果 | 支持程度 | 备注 |
|------|---------|---------|---------|------|
| H1 | ... | ... | 完全支持 / 部分支持 / 不支持 | ... |
| H2 | ... | ... | 完全支持 / 部分支持 / 不支持 | ... |

---

## 5. 潜在问题与根因分析

| 问题 | 严重程度 (critical/major/minor) | 根因 | 影响 |
|------|-------------------------------|------|------|
| ... | ... | ... | ... |

---

## 6. 最终决策

### 决策: [KEEP / FIX / BACKTRACK]

### 理由
...

### KEEP 完成条件（决策为 KEEP 时必填）

KEEP 只能在以下材料同时完成时使用：

- `experiments/artifacts/main_experiment/manifest.yaml`：包含 `experiment_id`, `method`, `dataset`, `baseline_refs`, `primary_metric.key/value/std`, 至少 3 个 `seeds`, `environment`
- `experiments/artifacts/main_experiment/metric_contract.yaml`：包含本文方法名称与 primary metric 的 `key/value/std`
- `experiments/artifacts/main_experiment/comparison_table.csv`：包含 baseline 与 ours/proposed 行，并给出不确定性列（如 `std` / `ci`）
- `experiments/artifacts/main_experiment/reproduction.md`：记录复现实验命令与关键配置
- `knowledge/handoff_M3_M4.md`：包含 KEEP 决策、claim/evidence 映射、M3S04 来源、artifact 路径、M4 分析方向

### 如果 FIX
- **修复目标**: M3S03 / M3S02 / M3S01
- **修复内容**: ...
- **预期效果**: ...

### 如果 BACKTRACK
- **回溯目标**: M3S01 / M2S03 / M2S05 / M1S04
- **回溯原因**: ...
- **修改方向建议**: ...
- **验证计划**: ...

### 6.4 结构化回溯字段（当决策为 FIX 或 BACKTRACK 时必填）
- `target_stage`: 可执行的回溯目标（如 M3S03 / M3S02 / M3S01 / M2S03 / M2S05 / M1S04）
- `blocking_reason`: 触发回溯的直接原因
- `required_fix`: 被回溯 stage 需要实际修改什么
- `success_criteria`: 修改后如何判定修复成功
- `evidence_paths`: 需要重新读取或补充的文件路径
- `rebuild_mode`: `incremental_replay` / `full_regenerate`
- `rerun_scope`: 从 `target_stage` 起需要重跑的范围，必须说明是否包含 downstream stale stages
- `handoff_updates`: 如需要刷新交接文档时填写

---

## 7. 负面结果

（诚实报告实验中的负面发现）

- **负面发现 1**: ...
- **负面发现 2**: ...

---

## 8. Evidence Artifact 打包

### 8.1 Artifact 清单

```
experiments/artifacts/main_experiment/
├── manifest.yaml          # 实验元数据
├── metric_contract.yaml   # 本文方法的 metric contract
├── comparison_table.csv   # 与 baseline 的对比
├── training_curves/       # 训练曲线图
├── logs/                  # 运行日志
├── configs/               # 配置文件
└── reproduction.md        # 复现指南
```

### 8.2 Manifest 内容

```yaml
experiment_id: "main_exp_v1"
method: "..."
dataset: "..."
baseline_refs:
  - "experiments/baselines/baseline_1/metric_contract.yaml"
primary_metric:
  key: "..."
  value: ...
  std: ...
seeds: [42, 123, 2024]
environment:
  python: "..."
  torch: "..."
  cuda: "..."
  hardware: "..."
run_date: "YYYY-MM-DD"
```

---

## 9. 已知限制

| 限制 | 影响 | 建议的后续工作 |
|------|------|--------------|
| 只在数据集 X 上验证 | 外部效度有限 | M4 增加跨数据集验证 |
| 超参未充分调优 | 可能非最优性能 | M4 做敏感性分析 |
| ... | ... | ... |

---

## 10. 传递给下游的信息

- **核心假设验证状态**: ...
- **统计显著性**: p-value = ..., 效应量 = ...
- **Evidence Artifact 路径**: `experiments/artifacts/main_experiment/`
- **关键发现（预期内）**: ...
- **意外发现**: ...
- **负面发现**: ...
- **建议的 M4 分析方向**:
  - 消融实验: ...
  - 鲁棒性检查: ...
  - 机制验证: ...
