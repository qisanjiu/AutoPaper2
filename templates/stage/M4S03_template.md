# M4S03 Deep Analysis Experiment Execution

> Stage: M4S03
> Agent: Experiment Agent
> Output: `knowledge/M4/M4S03_analysis_experiment.md`

---

## 1. 执行摘要

- 总 Slice 数: 
- 完成:  | 部分完成:  | 失败:  | 阻塞: 

## 2. Slice 执行记录

### [Ana-ID] ([名称])
- **status**: completed / partial / failed / blocked
- **results**: 
- **evidence_path**: experiments/artifacts/analysis_experiment/[ana_id]/
- **resource_assignment**: resource_id / resource_kind / server_id / lease_id / gpu_ids / cpu_cores / resource_monitor
- **sync_status**: local / remote push completed / remote pull completed / blocked
- **claim_update**: 
- **efficiency_metrics**: params_m / flops_g / train_time_sec / inference_latency_ms / throughput / peak_mem_mb / not_applicable
- **deviation_from_design**: yes / no
- **notes**: 任何偏离 M4S02 设计的地方必须显式写出

## 3. 负面/失败结果记录

| Slice | 状态 | 原因 | 对 Claim 的影响 |
|-------|------|------|----------------|
|       |      |      |                |

## 4. 原始数据与日志

- 结构化结果表: `experiments/analysis_results.tsv`
- 原始日志: `experiments/runs/analysis_*/`
- 图表/可视化: `experiments/artifacts/analysis_experiment/`
- 沙箱配置: `experiments/configs/sandbox_profile.yaml`
- 资源计划: `experiments/configs/resource_plan.yaml`
- 多资源任务队列: `experiments/configs/m4_task_queue.yaml`（如适用）
- 多资源任务分配: `experiments/configs/m4_task_allocation.yaml`（如适用）

### 4.0 analysis_results.tsv 必填列

`experiments/analysis_results.tsv` 必须至少包含：

`slice`, `analysis_type`, `method`, `dataset`, `split`, `seed`, `config_id`, `run_id`, `metric`, `value`, `baseline_inclusion`, `artifact_path`, `runtime_sec`, `params_m`, `peak_mem_mb`, `resource_id`, `resource_kind`, `server_id`, `gpu_ids`, `resource_monitor`, `notes`

- baseline 与 ours/proposed 必须保留在同一个表中。
- efficiency slice 若适用，还应包含 `flops_g`、`inference_latency_ms`、`throughput`、`train_time_sec` 等列。
- 不适用的效率字段可以为空，但不能省略列名；这样 M4S04 和 M5 能稳定读取证据。

## 4.1 Sandbox / Container Execution Record（必须）

| Slice | sandbox mode | resource_id | command | working dir | allowed writes | network policy | resource limits | log path |
|-------|--------------|-------------|---------|-------------|----------------|----------------|-----------------|----------|
| Ana-1 | docker / conda / venv / uv / ssh_remote | local / ssh:lab-a | `...` | `...` | `experiments/runs/...` | restricted / disabled / open | timeout / CPU / GPU / memory | `experiments/runs/analysis_*/logs/...` |

- 每个 M4S03 analysis slice 必须说明是否沿用 M3S01 的 `execution.sandbox`。
- 如果某个 slice 需要额外联网下载、远程同步、GPU 时间或凭证，必须写入对应日志和 long-running ledger。
- 禁止让分析脚本写出 `allowed_write_paths` 之外的位置，禁止在日志中打印 SSH key、API key、token 或密码。

## 4.2 多资源执行记录（如适用，必须）

当 `resource_plan.yaml.resource_pool.enabled == true` 或资源池中超过 1 个 resource/slot：

```bash
python scripts/resource_planner.py allocate \
  --project . \
  --stage M4S03 \
  --tasks experiments/configs/m4_task_queue.yaml \
  --output experiments/configs/m4_task_allocation.yaml
```

| Wave | Slice / Run ID | resource_id | resource_kind | server_id / lease_id | slot / GPU ids | CPU cores | monitor | sync evidence |
|------|----------------|-------------|---------------|----------------------|----------------|-----------|---------|---------------|
| 0 | Ana-1 / analysis_ana1 | ssh:lab-a | ssh | lab-a / lease_x | gpu:0 | 16 | `experiments/runs/analysis_ana1/resource_monitor.csv` | push/pull logs |

必须说明未并行或未使用资源的原因：slice 依赖、checkpoint 互斥、显存不足、数据未同步、baseline 公平性、配额限制或远程不可达。

## 5. 初步审查摘要

> 这里记录的是执行侧的异常分流，不是最终 verdict。最终审查由 `m4_analysis_execution_review` 独立 subagent 完成。

| Slice | expected_pattern | actual_pattern | meets_expectation | abnormal_cause | proposed_route |
|-------|------------------|----------------|-------------------|----------------|----------------|
|       |                  |                | yes / no / unclear | environment / setup / model / data / metric / method / unknown | stage_in_fix / stage_out_backtrack / continue |

### 5.1 分流规则
- `stage_in_fix`: 记录或参数错误、漏跑、轻微脚本问题，可在 M4S03 内补修。
- `stage_out_backtrack`: 设计假设明显错位、baseline/metric contract 错误、上游 M3 结果不可信，需要回溯到 M4S02 / M4S01 / M3S03 / M3S02。
- `continue`: 结果符合预期，且没有新的结构性问题。

### 5.2 交给 reviewer 的重点
- 哪个 slice 最不稳定
- 哪个 slice 的异常最可能来自环境 / 模型 / 数据 / 指标 / 方法
- 哪些证据路径需要优先复查
