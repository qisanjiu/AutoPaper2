# M3S03: Main Experiment Result Review

> **Stage**: M3S03
> **Agent**: Experiment Agent
> **输入**: `knowledge/M3/M3S02_baseline_lock.md`, `knowledge/M2/M2S06_full_experiment_plan.md`（旧项目可用 `M2S05_full_experiment_plan.md`）, `knowledge/M3/M3S01_implementation.md`
> **输出**: `knowledge/M3/M3S03_main_experiment.md` + `experiments/results.tsv` + `experiments/runs/<run_id>/`
>
> **审查重点**: 主实验结果是否超过 baseline、结果表是否完整、统计摘要是否齐全、负面结果是否诚实记录

---

## 1. Run Contract

### 1.1 锁定内容

| 项目 | 内容 |
|------|------|
| 研究问题 | [来自 M1S03] |
| 核心假设 | [来自 M1S04] |
| 方法干预 | [本文方法与 baseline 的关键差异] |
| 比较基准 | [引用 M3S02 锁定的 baseline metric contract] |
| 数据集与划分 | [来自 M2S05] |
| 主指标 | ... (方向: higher/lower_is_better) |
| 次指标 | ... |
| 停止条件 | 预算: X GPU-hours / 迭代: N 轮 / 收敛: 连续 3 轮 < 1% 提升 |
| 放弃条件 | smoke test 级别结果连续 2 轮低于 baseline |

### 1.2 证据层级目标

- **minimum**: [目标，如"代码运行完成，指标可计算"]
- **solid**: [目标，如"主指标显著优于 baseline"]
- **maximum**: [目标，如"多 seed、完整曲线"]

> 本实验当前追求层级: minimum → solid（maximum 留给 M4）

---

## 2. 实验环境

- **执行模式**: local / ssh
- **Python**: ...
- **PyTorch**: ...
- **CUDA**: ...
- **硬件**: ...
- **Git 分支**: `exp/main`
- **随机种子**: [42, 123, 2024, ...]

### 2.1 远程执行配置（如适用）

| 配置项 | 值 |
|--------|-----|
| SSH Host | ... |
| 远程工作路径 | ... |
| 同步策略 | metrics_only / all / selective |

---

## 3. Baseline 结果（本地运行）

| Baseline | 主指标 | 次指标 | Seed | 运行时间 | 备注 |
|----------|--------|--------|------|---------|------|
| Baseline-1 | ... | ... | 42 | ... | 官方代码 |
| Baseline-2 | ... | ... | 42 | ... | 自行实现 |

---

## 4. 迭代循环记录

### Iteration 1

- **Git commit**: `exp(iter1): 初始实现，按 M2S03 设计`
- **修改描述**: ...
- **关键指标**:
  | 方法 | 主指标 | 次指标 | vs Baseline-1 | vs Baseline-2 |
  |------|--------|--------|--------------|--------------|
  | Ours | ... | ... | ... | ... |
- **结论**: [改善/持平/恶化]
- **决策**: [继续 / 调整方向 / 诊断]
- **远程同步**（如适用）: push / pull 状态

### Iteration 2
...

---

## 5. 最终结果

### 5.1 主结果表

| 方法 | Seed | 主指标 | 次指标 | 运行时间 |
|------|------|--------|--------|---------|
| Baseline-1 | 42 | ... | ... | ... |
| Baseline-1 | 123 | ... | ... | ... |
| Baseline-1 | 2024 | ... | ... | ... |
| Baseline-1 | **Mean±Std** | **...** | **...** | — |
| Ours | 42 | ... | ... | ... |
| Ours | 123 | ... | ... | ... |
| Ours | 2024 | ... | ... | ... |
| Ours | **Mean±Std** | **...** | **...** | — |

### 5.2 与 Baseline 的对比

| 对比 | 绝对提升 | 相对提升 | 备注 |
|------|---------|---------|------|
| Ours vs Baseline-1 | ... | ...% | ... |
| Ours vs Baseline-2 | ... | ...% | ... |

---

## 6. Evidence Ladder 自评

- [ ] **minimum** — 可执行、可比较
- [ ] **solid** — 足以支撑主声明
- [ ] **maximum** — 全面抛光

**当前达成层级**: minimum / solid / maximum

**未达成更高层级的原因**（如适用）: ...

---

## 7. 训练曲线与日志

- **曲线路径**: `experiments/runs/<run_id>/curves/`
- **日志路径**: `experiments/runs/<run_id>/logs/`
- **关键观察**: ...

---

## 8. 负面结果与失败记录

| 迭代 | 尝试的修改 | 结果 | 失败类型 | 原因分析 |
|------|-----------|------|---------|---------|
| Iter-X | ... | 未改善 | direction_underperforming | ... |

---

## 9. 远程同步记录（如适用）

| 时间 | 方向 | 内容 | 状态 |
|------|------|------|------|
| ... | push | 代码更新 | 完成 |
| ... | pull | results.tsv + 日志 | 完成 |

---

## 10. 资源消耗

- **总 GPU 时间**: ...
- **总 Wall-clock 时间**: ...
- **存储占用**: ...
- **与预算对比**: 未超支 / 超支 X%

---

## 11. 传递给下游的信息

- **最优结果对应的配置**: ...
- **关键超参数**: ...
- **是否达到停止条件**: ...
- **实验是否按预期收敛**: ...
- **Evidence Artifact 路径**: `experiments/runs/<best_run_id>/`
- **远程结果同步状态**（如适用）: 已同步 / 部分同步 / 未同步
