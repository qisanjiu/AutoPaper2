# M6S04 — 回溯规划与 Rebuttal 策略

## 意见分类分析

[基于 Review Matrix 的分类汇总]

## 回溯目标映射

| 意见 ID | 类别 | 目标 Stage | 负责 Agent | rebuild_mode |
|---------|------|-----------|-----------|-------------|
| PR-A1 | evidence_gap | M4S02 | Analysis | incremental_replay |
| ... | ... | ... | ... | ... |

## Action Plan

### 执行顺序（按优先级排序）
1. [P0] PR-AX → [target_stage]
2. [P1] PR-AY → [target_stage]
3. ...

### 详细条目

#### PR-A1
- **class**:
- **severity**: High / Medium / Low
- **target_stage**: 
- **required_fix**: 
- **success_criteria**: 
- **rebuild_mode**: incremental_replay / full_regenerate
- **rerun_scope**: 
- **priority**: P0

> 每个 `knowledge/M6/M6S03_review_matrix.md` 中的 `PR-*` item 都必须在 Rebuttal Strategy 和 Action Plan 中出现一次。不得合并到无法追踪的笼统条目。

## 诚实限制声明

- [ ] 存在无法完全解决的意见？
- [ ] 如有，说明原因和 fallback 策略

## 预计工作量

- 涉及模块: [列表]
- 预计回溯轮数: [N]
- 关键路径: [从哪个 stage 到哪个 stage]

## Deterministic Gate Requirements

- Rebuttal Strategy 必须覆盖所有 Review Matrix 中的 `PR-*` ID
- `M6S04_action_plan.md` 必须覆盖所有 Review Matrix 中的 `PR-*` ID
- 每个 `PR-*` 条目必须包含 `class`、`severity`、`target_stage`、`required_fix`、`success_criteria`、`rebuild_mode`、`rerun_scope`、`priority`
- High priority item 不允许只做 text-only 修复，除非明确说明原意见本身仅为文字问题
