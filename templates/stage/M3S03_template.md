# M3S03: Main Experiment Result Review

> **Stage**: M3S03
> **Agent**: Experiment Agent
> **输入**: `knowledge/M3/M3S02_baseline_lock.md`, `knowledge/M2/M2S06_full_experiment_plan.md`（旧项目可用 `M2S05_full_experiment_plan.md`）, `knowledge/M3/M3S01_implementation.md`
> **输出**: `knowledge/M3/M3S03_main_experiment.md` + `experiments/results.tsv` + `experiments/runs/<run_id>/` + `experiments/logs/runtime_events.jsonl`
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
| 资源执行合同 | `experiments/configs/resource_plan.yaml` |
| Runtime watchdog | 巡检间隔: 默认 4h / 最长 6h；告警只记录，不自动结束；Agent 决策: continue / fix_and_rerun / early_stop / backtrack_request |

### 1.2 证据层级目标

- **minimum**: [目标，如"代码运行完成，指标可计算"]
- **solid**: [目标，如"主指标显著优于 baseline"]
- **maximum**: [目标，如"完整曲线、更多数据集或更完整日志"]

> 本实验当前追求层级: minimum → solid（maximum 留给 M4）

---

## 2. 实验环境

- **执行模式**: local / ssh
- **Python**: ...
- **PyTorch**: ...
- **CUDA**: ...
- **硬件**: ...
- **Resource Plan**: `experiments/configs/resource_plan.yaml`
- **设备策略**: distributed_data_parallel / single_gpu / cpu_parallel / task_parallel
- **分配 GPU**: `gpu_ids=[...]`, `gpu_count=...`
- **分配 CPU**: `cpu_cores=...`
- **DataLoader**: `num_workers=...`, `pin_memory=...`, `persistent_workers=...`, `prefetch_factor=...`
- **线程环境变量**: `OMP_NUM_THREADS=...`, `MKL_NUM_THREADS=...`
- **Git 分支**: `exp/main`
- **随机种子**: 42（固定单次实验；不做多 seed 重复实验）

### 2.1 远程执行配置（如适用）

| 配置项 | 值 |
|--------|-----|
| SSH Host | ... |
| 远程工作路径 | ... |
| 同步策略 | metrics_only / all / selective |

---

## 2.2 资源利用率执行记录（必须）

| Run ID | 启动命令 | Resource monitor | 平均 GPU 利用率 | 平均 CPU 利用率 | 低利用率处理 |
|--------|----------|------------------|----------------|----------------|--------------|
| run_001 | `python scripts/resource_planner.py run --output experiments/runs/run_001/resource_monitor.csv --interval 10 -- ...` | `experiments/runs/run_001/resource_monitor.csv` | ...% | ...% | optimized / documented blocker |

如 `resource_plan.yaml` 分配多 GPU，则默认命令必须使用 `torchrun --nproc_per_node=<gpu_count>` 或等价 DDP。若未使用 DDP，必须写明替代资源策略和原因；不得通过多 seed 重复实验来填满资源。

## 2.3 Runtime Watchdog 与告警记录（必须）

| Run ID | Watchdog command / session | 巡检间隔 | Check log | Alert log | 最近状态 | Agent 决策 |
|--------|----------------------------|----------|-----------|-----------|----------|------------|
| run_001 | `python scripts/experiment_watchdog.py watch --project . --run-id run_001 --interval-seconds 14400 --log experiments/runs/run_001/logs/train.log --metrics experiments/runs/run_001/metrics.csv` | 4h | `experiments/runs/run_001/watchdog_checks.jsonl` | `experiments/runs/run_001/watchdog_alerts.jsonl` / 无告警 | info / warning / critical / early_stop_candidate | continue / fix_and_rerun / early_stop / backtrack_request |

- **Runtime events**: `experiments/logs/runtime_events.jsonl`
- **告警不自动终止**: Watchdog 仅写告警；是否结束、继续、修复或回溯由 Experiment Agent 读取日志、metric 曲线、checkpoint 和资源监控后判断。
- **若出现告警，必须记录证据链**: `run_id`、告警类型、原始日志路径、metric/curve 路径、checkpoint 路径、Agent 决策、决策理由、后续命令。

---

## 3. Baseline 结果（本地运行）

| Baseline | 主指标 | 次指标 | Seed | 运行时间 | 资源策略 | Monitor | 备注 |
|----------|--------|--------|------|---------|----------|---------|------|
| Baseline-1 | ... | ... | 42 | ... | resource_plan / fair override | `experiments/runs/.../resource_monitor.csv` | 官方代码 |
| Baseline-2 | ... | ... | 42 | ... | resource_plan / fair override | `experiments/runs/.../resource_monitor.csv` | 自行实现 |

---

## 4. 迭代循环记录

### Iteration 1

- **Git commit**: `exp(iter1): 初始实现，按 M2S03 设计`
- **修改描述**: ...
- **关键指标**:
  | 方法 | 主指标 | 次指标 | vs Baseline-1 | vs Baseline-2 |
  |------|--------|--------|--------------|--------------|
  | Ours | ... | ... | ... | ... |
- **资源监控**: `experiments/runs/<run_id>/resource_monitor.csv`；平均 GPU 利用率 ...%；平均 CPU 利用率 ...%
- **低利用率处置**: 无 / 已调 batch size / 已调 num_workers / 已切换 DDP / 已改 task_parallel / 不可优化原因 ...
- **Watchdog 巡检**: `experiments/runs/<run_id>/watchdog_checks.jsonl`；最近状态 info / warning / critical / early_stop_candidate
- **告警与 Agent 决策**: 无 / NaN / non_convergence / OOM / early_stop_candidate → continue / fix_and_rerun / early_stop / backtrack_request；理由: ...
- **结论**: [改善/持平/恶化]
- **决策**: [继续 / 调整方向 / 诊断]
- **远程同步**（如适用）: push / pull 状态

### Iteration 2
...

---

## 5. 最终结果

### 5.1 主结果表

| 方法 | Seed | 主指标 | 次指标 | 运行时间 | 资源策略 | Monitor |
|------|------|--------|--------|---------|----------|---------|
| Baseline-1 | 42 | ... | ... | ... | ... | `experiments/runs/.../resource_monitor.csv` |
| Ours | 42 | ... | ... | ... | ... | `experiments/runs/.../resource_monitor.csv` |

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
- **Watchdog checks**: `experiments/runs/<run_id>/watchdog_checks.jsonl`
- **Watchdog alerts**: `experiments/runs/<run_id>/watchdog_alerts.jsonl` / 无告警
- **Runtime event stream**: `experiments/logs/runtime_events.jsonl`
- **关键观察**: ...

### 7.1 Agent 决策日志（针对告警或早停候选）

| 时间 | Run ID | Watchdog severity | 证据路径 | Agent 决策 | 理由 | 后续动作 |
|------|--------|-------------------|----------|------------|------|----------|
| ... | run_001 | critical / warning / early_stop_candidate | `experiments/runs/run_001/watchdog_alerts.jsonl`; `experiments/runs/run_001/logs/train.log`; `experiments/runs/run_001/metrics.csv` | continue / fix_and_rerun / early_stop / backtrack_request | ... | ... |

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
- **平均 GPU 利用率**: ...%
- **平均 CPU 利用率**: ...%
- **低利用率原因/优化记录**: ...
- **存储占用**: ...
- **与预算对比**: 未超支 / 超支 X%

---

## 11. 传递给下游的信息

- **最优结果对应的配置**: ...
- **关键超参数**: ...
- **是否达到停止条件**: ...
- **实验是否按预期收敛**: ...
- **Watchdog 最终状态**: info / warning_resolved / critical_resolved / early_stopped / backtrack_requested
- **Evidence Artifact 路径**: `experiments/runs/<best_run_id>/`
- **远程结果同步状态**（如适用）: 已同步 / 部分同步 / 未同步
