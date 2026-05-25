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
- **claim_update**: 
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

## 4.1 Sandbox / Container Execution Record（必须）

| Slice | sandbox mode | command | working dir | allowed writes | network policy | resource limits | log path |
|-------|--------------|---------|-------------|----------------|----------------|-----------------|----------|
| Ana-1 | docker / conda / venv / uv / ssh_remote | `...` | `...` | `experiments/runs/...` | restricted / disabled / open | timeout / CPU / GPU / memory | `experiments/runs/analysis_*/logs/...` |

- 每个 M4S03 analysis slice 必须说明是否沿用 M3S01 的 `execution.sandbox`。
- 如果某个 slice 需要额外联网下载、远程同步、GPU 时间或凭证，必须写入对应日志和 long-running ledger。
- 禁止让分析脚本写出 `allowed_write_paths` 之外的位置，禁止在日志中打印 SSH key、API key、token 或密码。

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
