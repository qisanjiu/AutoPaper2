# M4S01 Post-Experiment Audit & Findings Consolidation

> Stage: M4S01
> Agent: Analysis Agent
> Output: `knowledge/M4/M4S01_other_findings.md`

---

## 1. 数据质量审计

### 1.1 过拟合检查
- train/val gap: ...
- 学习曲线分析: ...

### 1.2 数据泄露检查
- 预处理管道隔离性: ...
- 交叉验证策略: ...

### 1.3 训练稳定性
- loss 曲线: ...
- NaN/inf 出现情况: ...
- 固定 seed=42: ...

### 1.4 可复现性
- seed=42 配置/日志/结果一致性: ...
- 关键超参数稳定性: ...

## 2. 主实验结果摘要

| 指标 | Seed | Ours | Best Baseline | Delta |
|------|------|------|---------------|-------|
|      | 42   |      |               |       |

## 3. 意外发现

- **发现 1**: ...
  - 现象描述: ...
  - 潜在影响: ...
  - 是否需要进一步分析: ...

## 4. 边界条件探索

- **表现好的条件**: ...
- **表现差的条件**: ...
- **临界阈值**: ...

## 5. 负面结果

- **尝试 X**: ...
  - 结果: ...
  - 原因分析: ...
  - 是否报告在论文中: ...

## 6. Claim 初筛

| Claim ID | Claim Text | 当前证据 | 状态初判 | 需补充证据 |
|----------|-----------|----------|---------|-----------|
| C1       |           |          | supported / partial / unsupported | |

## 7. 分析战役规划草案

> 目标: 为 M4S02 生成可执行的分析计划，至少覆盖消融、机制、鲁棒性三类；失败分析必须显式纳入或给出不纳入理由。

| 方向 | 优先级 | 候选 Slice | 目标 Claim | literature_basis | baseline_inclusion | 纸面位置 |
|------|--------|-----------|-----------|------------------|--------------------|----------|
| 消融实验 | High / Medium / Low | | | | required / optional / no | main_text / appendix |
| 机制分析 | High / Medium / Low | | | | required / optional / no | main_text / appendix |
| 鲁棒性检查 | High / Medium / Low | | | | required / optional / no | main_text / appendix |
| 失败分析 | High / Medium / Low | | | | required / optional / no | appendix / removed |

### 7.1 计划备注
- 每个候选 slice 都必须能追溯到 `M1S02` 文献或 `M1_source_log.yaml`/`survey_memory.yaml` 中的相关做法。
- 对于要与 baseline 比较的 slice，必须说明 baseline 是否同跑，以及是否沿用 M3 的 metric/split/seed contract。
- 若某方向只适合边界/负面证据，必须标注为 `appendix` 或 `reference_only`，不能直接写成主结论。

## 8. 论文面向映射初稿

| 发现 | paper_role | 建议位置 |
|------|-----------|---------|
| | main_text / appendix / reference_only | |

## 9. 传递给下游的信息

- 最意外的发现是...
- 最需要进一步分析的是...
- 下一步分析方向: ...

## 10. 下游审查提示
- M4S02 需要优先审查 `claim_links`、`literature_basis` 和 `baseline_inclusion`。
- 任何看起来“结果很好但没有对照”的方向，都必须降级为 exploratory 或重新补 baseline。
- 若主实验结果与预期严重偏离，应把偏离原因写清楚，交给 M4S03 的异常分流和 reviewer。
