# M3S04: Main Experiment Result Review

> **Stage**: M3S04
> **Agent**: Experiment Agent
> **输入**: `knowledge/M3/M3S03_baseline_lock.md`, `knowledge/M3/M3S01_main_experiment_design.md`, `knowledge/M3/M3S02_implementation.md`
> **输出**: `knowledge/M3/M3S04_main_experiment.md` + `experiments/tables/results_main.tsv` + `experiments/tables/results_all.tsv` + `experiments/run_registry.yaml` + `experiments/runs/<stage>/<run_id>/` + `experiments/logs/runtime_events.jsonl`
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
| 比较基准 | [引用 M3S03 锁定的 baseline metric contract] |
| 数据集与划分 | [来自 M3S01 主实验设计，必须与 M2S05 指标协议一致] |
| 主指标 | ... (方向: higher/lower_is_better) |
| 次指标 | ... |
| 停止条件 | 预算: X GPU-hours / 迭代: N 轮 / 收敛: 连续 3 轮 < 1% 提升 |
| 放弃条件 | smoke test 级别结果连续 2 轮低于 baseline |
| 资源执行合同 | `experiments/configs/resource_plan.yaml` |
| 多资源任务分配 | `experiments/configs/m3_task_queue.yaml` / `experiments/configs/m3_task_allocation.yaml`（如适用） |
| Runtime watchdog | 巡检间隔: 默认 4h / 最长 6h；告警只记录，不自动结束；Agent 决策: continue / fix_and_rerun / early_stop / backtrack_request |

### 1.2 Experiments Directory Contract

M3S04 正式产物必须使用如下结构；旧的 `experiments/results.tsv` 可作为兼容镜像，但不得作为唯一真源：

```text
experiments/
├── code/                         # 训练/评估代码
├── configs/                      # resource_plan、task queue、run configs
├── data/                         # dataset_manifest.yaml 与项目内数据引用
├── assets/                       # tokenizer、schedule、固定外部资产
├── baselines/                    # M3S03 locked baseline contracts
├── tables/
│   ├── results_main.tsv          # 仅有效 M3S04 主结果
│   ├── results_all.tsv           # 全部有效/诊断/失败尝试
│   └── results_invalid.tsv       # 明确无效的历史/异常结果
├── runs/
│   ├── M3S03_baseline/<run_id>/
│   ├── M3S04_main/<run_id>/
│   ├── M4_analysis/<run_id>/
│   └── archive/
├── logs/
└── run_registry.yaml
```

每个进入 `results_main.tsv` 的 run 必须在 `run_registry.yaml` 中登记，并且 run 目录至少包含：

```text
run_manifest.yaml
config.yaml
command.sh
stdout.log / stderr.log
training_history.json
metrics.tsv
best_model.pt 或 checkpoint 路径
checkpoint_manifest.yaml
status.json
resource_monitor.csv
watchdog_checks.jsonl
```

没有 `training_history.json` 或 `status.json` 的 checkpoint-only run 只能标为 `validity: checkpoint_only_unverified`，不得进入 `results_main.tsv`。

### 1.3 证据层级目标

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
- **Task Queue / Allocation**: `experiments/configs/m3_task_queue.yaml`, `experiments/configs/m3_task_allocation.yaml`（如启用多资源）
- **设备策略**: distributed_data_parallel / single_gpu / cpu_parallel / task_parallel
- **资源池**: local / ssh resources, resource_id, server_id/lease_id, GPU/CPU capacity, sync_required
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

## 2.2 多资源任务分配（如适用，必须）

当 `resource_plan.yaml.resource_pool.enabled == true` 或资源池中超过 1 个 resource/slot：

```bash
python scripts/resource_planner.py allocate \
  --project . \
  --stage M3S04 \
  --tasks experiments/configs/m3_task_queue.yaml \
  --output experiments/configs/m3_task_allocation.yaml
```

| Wave | Task / Run ID | parallelizable | resource_id | resource_kind | server_id / lease_id | slot / GPU ids | CPU cores | launch command | sync |
|------|---------------|----------------|-------------|---------------|----------------------|----------------|-----------|----------------|------|
| 0 | run_001 | yes | local | local | — | gpu:0 | 8 | `...` | no |
| 0 | run_002 | yes | ssh:lab-a | ssh | lab-a / lease_x | gpu:0 | 16 | `ssh ...` | push/pull |

必须说明未并行或未使用资源的原因：依赖、共用 checkpoint 写入、显存不足、数据未同步、DDP 不兼容、baseline 公平性、服务器配额或远程不可达。

## 2.3 资源利用率执行记录（必须）

| Run ID | resource_id | server_id | 启动命令 | Resource monitor | 平均 GPU 利用率 | 平均 CPU 利用率 | 低利用率处理 |
|--------|-------------|-----------|----------|------------------|----------------|----------------|--------------|
| run_001 | local / ssh:lab-a | lab-a / — | `python scripts/resource_planner.py run --output experiments/runs/run_001/resource_monitor.csv --interval 10 -- ...` | `experiments/runs/run_001/resource_monitor.csv` | ...% | ...% | optimized / documented blocker |

如 `resource_plan.yaml` 分配多 GPU，则默认命令必须使用 `torchrun --nproc_per_node=<gpu_count>` 或等价 DDP。若未使用 DDP，必须写明替代资源策略和原因；不得通过多 seed 重复实验来填满资源。

## 2.4 Runtime Watchdog 与告警记录（必须）

| Run ID | Watchdog command / session | 巡检间隔 | Check log | Alert log | 最近状态 | Agent 决策 |
|--------|----------------------------|----------|-----------|-----------|----------|------------|
| run_001 | `python scripts/experiment_watchdog.py watch --project . --run-id run_001 --interval-seconds 14400 --log experiments/runs/run_001/logs/train.log --metrics experiments/runs/run_001/metrics.csv` | 4h | `experiments/runs/run_001/watchdog_checks.jsonl` | `experiments/runs/run_001/watchdog_alerts.jsonl` / 无告警 | info / warning / critical / early_stop_candidate | continue / fix_and_rerun / early_stop / backtrack_request |

- **Runtime events**: `experiments/logs/runtime_events.jsonl`
- **告警不自动终止**: Watchdog 仅写告警；是否结束、继续、修复或回溯由 Experiment Agent 读取日志、metric 曲线、checkpoint 和资源监控后判断。
- **若出现告警，必须记录证据链**: `run_id`、告警类型、原始日志路径、metric/curve 路径、checkpoint 路径、Agent 决策、决策理由、后续命令。

## 2.5 Trained-Weight Evidence Contract（必须）

M3S04 不得在训练未完成时推进。随机初始化、E0、未训练 checkpoint、仍在 running/queued 的训练结果只能作为负面/诊断记录，不能填入最终 proposed/ours 主结果。

`experiments/tables/results_main.tsv` 的 proposed/ours 行必须至少包含：

| method | run_id | seed | metric | value | run_status | weight_state | checkpoint_path | training_steps | resource_monitor |
|--------|--------|------|--------|-------|------------|--------------|-----------------|----------------|------------------|
| ours | run_001 | 42 | ... | ... | completed | trained / trained_checkpoint / verified_loadable | `experiments/runs/run_001/checkpoints/best.pt` | >0 | `experiments/runs/run_001/resource_monitor.csv` |

同时必须满足：
- `checkpoint_path` 指向项目内真实存在的文件；
- `run_status` / `training_status` 为 completed / succeeded / finished / done；
- `weight_state` 证明是训练完成的权重，不得为 random / random_init / untrained / E0；
- `experiments/logs/runtime_events.jsonl` 至少包含对应 run 的 `training_completed`、`run_completed`、`experiment_completed` 或 `checkpoint_saved` 事件。
- `experiments/run_registry.yaml` 中同一 `run_id` 的 `status` 为 completed，`validity` 为 `valid_main` 或 `valid_reference`，并列出真实存在的 manifest/config/history/metrics/checkpoint/status 文件。

### 2.6 Metric Protocol / Result Validity Contract（必须）

进入 `results_main.tsv` 的 formal row 必须满足：

- 每行包含 `metric_protocol_id`，并能在 `knowledge/M2/M2S05_metric_protocol.yaml` 找到；
- `metric`、`direction`、dataset/scenario/split（如列出）与对应 metric protocol 一致；
- `value` 落在 protocol `value_range` 内；
- 若 `value` 超出 `normal_reference_range`，必须包含 anomaly_triage / evidence path / 保留或排除该行的理由；
- implementation shortcut、metric/data/label leakage、protocol mismatch、interrupted run、checkpoint-only run 等只能进入 diagnostic/invalid 记录，不能作为 formal main evidence。

`results_invalid.tsv` 应写明 `invalid_reason`、`evidence_path`、`affected_run_id` 和 `backtrack_target`。

---

## 3. Baseline 结果（本地运行）

| Baseline | 主指标 | 次指标 | Seed | run_status | weight_state | checkpoint_path | 运行时间 | resource_id | Monitor | 备注 |
|----------|--------|--------|------|------------|--------------|-----------------|---------|-------------|---------|------|
| Baseline-1 | ... | ... | 42 | completed | trained / verified_loadable / not_applicable | `...` | ... | local / ssh:lab-a | `experiments/runs/.../resource_monitor.csv` | 官方代码 |
| Baseline-2 | ... | ... | 42 | completed | trained / verified_loadable / not_applicable | `...` | ... | ... | `experiments/runs/.../resource_monitor.csv` | 完整复现 |

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

| 方法 | Run ID | Seed | 主指标 | 次指标 | run_status | weight_state | checkpoint_path | training_steps | resource_id | server_id | Monitor |
|------|--------|------|--------|--------|------------|--------------|-----------------|----------------|-------------|-----------|---------|
| Baseline-1 | baseline_1_run | 42 | ... | ... | completed | trained / verified_loadable / not_applicable | `...` | ... | ... | ... | `experiments/runs/.../resource_monitor.csv` |
| Ours | run_001 | 42 | ... | ... | completed | trained_checkpoint | `experiments/runs/run_001/checkpoints/best.pt` | ... | ... | ... | `experiments/runs/.../resource_monitor.csv` |

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
- **Trained checkpoint**: `experiments/runs/<best_run_id>/checkpoints/best.pt`，runtime event 已记录 completed
- **远程结果同步状态**（如适用）: 已同步 / 部分同步 / 未同步

## 12. Run Registry Snapshot

`experiments/run_registry.yaml` 必须至少包含以下字段：

```yaml
schema_version: 1
runs:
  - run_id: M3S04_main_ours_demo_seed42_YYYYMMDD-HHMMSS
    stage: M3S04
    role: ours
    status: completed
    validity: valid_main
    config_id: ...
    seed: 42
    dataset: ...
    metric_protocol_id: mp_...
    checkpoint_path: experiments/runs/M3S04_main/.../best_model.pt
    history_path: training_history.json
    metrics_path: metrics.tsv
    run_manifest: run_manifest.yaml
    checkpoint_manifest: checkpoint_manifest.yaml
    status_path: status.json
```
