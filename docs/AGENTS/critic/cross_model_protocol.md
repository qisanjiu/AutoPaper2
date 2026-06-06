# Cross-Model Review Protocol

## 强制隔离规则

1. Survey Agent (M1S01-02) 与 Survey Review Agent **不得由同一模型实例执行**
2. Ideation Agent (M1S03-05) 与 Logic/Novelty Critic **不得由同一模型实例执行**
3. Method Agent (M2S01-05) 与 Method Critic (G2) **不得由同一模型实例执行**
4. Experiment Agent (M3S01-M3S04) 与 M3 Stage Review Agents **不得由同一模型实例执行**
5. Analysis Agent (M3S05) 与 `m3_result_validation_review` / Gate G3 Critics（Method / Evidence）**不得由同一模型实例执行**

## 信息传递规则

- Critic 的输入**只能是文件路径**，不能是 Executor 提供的摘要、解释或精选片段
- Critic 必须**独立读取**原始产出文件，自行提取证据
- Critic 的 verdict 必须基于**直接阅读**，而非 Executor 的转述

## 回溯建议契约

当 Critic / Reviewer 输出 `REVISE`、`BACKTRACK` 或 `FIX` 时，必须同时写出以下字段：

- `target_stage`: 最小可执行回溯目标，必须是有效 stage
- `blocking_reason`: 触发回溯的直接原因
- `required_fix`: 被回溯 stage 需要实际修改什么
- `success_criteria`: 修改后如何判定修复成功
- `evidence_paths`: 需要重新读取或补充的文件路径
- `rebuild_mode`: `incremental_replay` / `full_regenerate`
- `rerun_scope`: 需要重跑的范围（单 stage / 模块内 / 跨模块）
- `handoff_updates`: 若涉及交接文档重写，列出要更新的 handoff

默认策略：
1. `full_regenerate` 是默认值，适用于不确定、跨层级、语义变化大的回溯。
2. `incremental_replay` 仅适用于局部修补且上下游接口未变的场景，可以复用旧文件中未受影响的部分作为草稿，但必须重新核对它们依赖的上游原始文件。
3. 旧文件永远是历史证据，不是新结论的唯一来源；若方向偏差较大，应丢弃旧正文并按新的上游事实重建。

如果根因在 handoff 或上游设计而不是当前 stage，本契约要求：
1. `target_stage` 仍然写成可执行 stage，不允许只写 handoff 名称
2. `handoff_updates` 必须说明要回写哪个 handoff 文档
3. `required_fix` 必须说明是“重跑当前 stage”还是“重写上游输入后再重跑”，并配合 `rebuild_mode` 说明是增量重跑还是全量重建

## 对抗升级机制

| 级别 | 条件 | 行为 |
|------|------|------|
| L1 (标准) | 首次评审 | 单轮评审，给出 PASS/REWORK/HALT |
| L2 (困难) | Round 2+ 或关键 Gate | 引入 Reviewer Memory（跨轮累积怀疑清单） |
| L3 (噩梦) | 高风险的 Novelty/Method 审查 | Reviewer 独立搜索文献验证 Executor 的声称 |

## 在 AutoPaper2 中的实施点

- M1S02 Round Review: Survey Review Agent 必须独立读取 M1S02_literature_deepdive.md 和 M1_source_log.yaml
- Gate G1: Coverage + Logic + Novelty 三个 Critic 应尽可能分配给不同模型实例
- Gate G2: Method Critic 应独立验证 M2S03 的伪代码与 M2S04 的实验设计
- M3S01-M3S05 Stage Review: Reviewer 必须独立读取对应 M3 产出、配置和结果文件
- Gate G3: Method Critic 与 Evidence Critic 应尽可能分配给不同模型实例
