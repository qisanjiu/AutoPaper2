# M3S05: Result Validation & Evidence Packaging

> **Stage**: M3S05
> **Agent**: Analysis Agent
> **输入**: `knowledge/M3/M3S04_main_experiment.md`, `knowledge/M3/M3S03_baseline_lock.md`, `knowledge/M3/M3S01_main_experiment_design.md`, `experiments/results.tsv`, `knowledge/M1/M1S04_hypothesis_generation.md`
> **输出**: `knowledge/M3/M3S05_result_validation.md` + `experiments/artifacts/main_experiment/`
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
| 固定 seed 配置 | seed=42 已记录 / 未记录 | ... |

---

## 3. 固定 Seed 单次结果验证

### 3.1 验证方法

- **选择的方法**: fixed-seed single-run validation
- **固定 seed**: 42
- **选择理由**: 本框架不再要求多 seed 重复实验，结论基于 seed=42 的单次可复现实验

### 3.2 验证结果

| 对比 | Seed | 主指标差异 | 相对提升 | 结论 |
|------|------|------------|----------|------|
| Ours vs Baseline-1 | 42 | ... | ... | 优于 / 持平 / 低于 |
| Ours vs Baseline-2 | 42 | ... | ... | 优于 / 持平 / 低于 |

### 3.3 统计限制说明

- **统计显著性**: 不声称（未做多 seed 重复实验）
- **不确定性估计**: 不要求 std / CI
- **报告边界**: 只能报告固定 seed=42 下的结果，不得声称跨随机种子稳定

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

- `experiments/artifacts/main_experiment/manifest.yaml`：包含 `experiment_id`, `method`, `dataset`, `baseline_refs`, `primary_metric.key/value`, `seed: 42`, `environment`
- `experiments/artifacts/main_experiment/metric_contract.yaml`：包含本文方法名称与 primary metric 的 `key/value`
- `experiments/artifacts/main_experiment/comparison_table.csv`：包含 baseline 与 ours/proposed 行，并记录 `seed=42`
- `experiments/artifacts/main_experiment/reproduction.md`：记录复现实验命令与关键配置
- M3S04 final proposed/ours 行引用的 trained checkpoint 真实存在，且 `runtime_events.jsonl` 记录训练完成事件；random/E0/untrained 权重不得 KEEP
- `knowledge/handoff_M3_M4.md`：包含 KEEP 决策、claim/evidence 映射、M3S05 来源、artifact 路径、M4 分析方向

### 如果 FIX
- **修复目标**: M3S04 / M3S03 / M3S02
- **修复内容**: ...
- **预期效果**: ...

### 如果 BACKTRACK
- **回溯目标**: M3S02 / M2S03 / M2S05 / M1S04
- **回溯原因**: ...
- **修改方向建议**: ...
- **验证计划**: ...

### 6.4 结构化回溯字段（当决策为 FIX 或 BACKTRACK 时必填）
- `target_stage`: 可执行的回溯目标（如 M3S04 / M3S03 / M3S02 / M2S03 / M2S05 / M1S04）
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
trained_checkpoint: "experiments/runs/run_001/checkpoints/best.pt"
primary_metric:
  key: "..."
  value: ...
seed: 42
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
- **固定 seed 结果边界**: seed=42，主指标差异 = ...，不声称统计显著
- **Evidence Artifact 路径**: `experiments/artifacts/main_experiment/`
- **关键发现（预期内）**: ...
- **意外发现**: ...
- **负面发现**: ...
- **建议的 M4 分析方向**:
  - 消融实验: ...
  - 鲁棒性检查: ...
  - 机制验证: ...
