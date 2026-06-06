# M3S01: Main Experiment Design

> **Stage**: M3S01
> **Agent**: Experiment Agent
> **输入**: `knowledge/handoff_M2_M3.md`, `knowledge/M2/M2S03_method_architecture.md`, `knowledge/M2/M2S04_algorithm_theory.md`, `knowledge/M2/M2S05_experiment_setup.md`, `knowledge/M2/M2S05_metric_protocol.yaml`
> **输出**: `knowledge/M3/M3S01_main_experiment_design.md`
>
> **审查重点**: 只设计主实验，不设计消融、机制、鲁棒性或 M4 分析实验。

---

## 0. Scope Boundary

M3S01 只允许定义主实验计划：

- 在什么数据集、场景和 split 上评估；
- 使用哪些 M2S05 `metric_protocol_id`；
- 选择哪些外部 prior-work baselines；
- 每个 baseline 在对应 dataset/scenario/split/metric 上的具体参考数值和来源；
- 所提方法如何在同数据、同 split、同指标、同 seed、公平资源约束下运行。

禁止内容：

- 不设计 ablation / 消融；
- 不设计 robustness / 鲁棒性分析；
- 不设计 mechanism / failure slice / M4 `Ana-*`；
- 不把本文方法的组件移除、轻量变体、调参版本作为 baseline。

这些分析只能进入 M4S02/M4S03。

---

## 1. Main Experiment Target

| 字段 | 内容 |
|------|------|
| Research question | 来自 M1S03 |
| Core hypothesis | 来自 M1S04 |
| Proposed method | 来自 M2S03/M2S04 |
| Main claim candidate | 只写主实验要验证的 claim |
| Evidence level target | minimum / solid |

---

## 2. Dataset And Metric Protocol

| experiment_id | dataset | scenario/task | split | metric_protocol_id | primary_metric | direction | normal_reference_range | source |
|---------------|---------|---------------|-------|--------------------|----------------|-----------|------------------------|--------|
| Main-1 | ... | ... | ... | mp_... | ... | higher_is_better / lower_is_better | ... | M2S05_metric_protocol.yaml |

要求：

- `metric_protocol_id` 必须来自 `knowledge/M2/M2S05_metric_protocol.yaml`；
- dataset/scenario/split/metric/direction 必须与 M2S05 指标协议一致；
- 若指标正常范围不明确，必须回溯 M2S05，不得留到 M3S03/M3S04 再猜。

---

## 3. Baseline Reference Values

每个 baseline 必须是外部 prior work、官方 baseline 或忠实完整复现的 prior work。这里记录的是后续 M3S03 本地复现/验证的参考值，不等于最终比较结果。

| baseline | comparator_type | dataset | scenario | split | metric_protocol_id | metric | reference_value | value_source | table_or_section | expected_tolerance | acquisition_plan |
|----------|-----------------|---------|----------|-------|--------------------|--------|-----------------|--------------|------------------|--------------------|------------------|
| Baseline-1 | external_prior_work / official_baseline / reproduced_prior_work | ... | ... | ... | mp_... | ... | 0.000 | paper / official repo / leaderboard | ... | ... | official code/checkpoint URL or training plan |
| Baseline-2 | ... | ... | ... | ... | mp_... | ... | 0.000 | ... | ... | ... | ... |

硬性要求：

- `reference_value` 必须是具体数值，不能写 TBD、unknown、见论文、待复现；
- `value_source` 必须能定位到论文表格、官方 repo、leaderboard 或已验证历史 artifact；
- baseline 不得是本方法消融变体；
- 如果找不到同 dataset/split/metric 的参考值，M3S01 必须 HALT/REVISE，而不是让 M3S03 继续。

---

## 4. Proposed Method Same-Condition Protocol

| 条件 | Baseline | Proposed method | 是否一致 | 差异说明 |
|------|----------|-----------------|----------|----------|
| dataset | ... | ... | yes/no | ... |
| split | ... | ... | yes/no | ... |
| primary metric | ... | ... | yes/no | ... |
| seed | 42 | 42 | yes | fixed seed single run |
| preprocessing | ... | ... | yes/no | ... |
| training budget | ... | ... | yes/no | ... |
| hardware/resource class | ... | ... | yes/no | ... |
| checkpoint policy | ... | ... | yes/no | ... |

不一致项必须说明公平性影响；若无法公平比较，必须回溯 M2S05 或重选 baseline。

---

## 5. Execution Handoff To M3S02-M3S04

| 下游阶段 | 必须执行的主实验工作 | 禁止事项 |
|----------|----------------------|----------|
| M3S02 | 获取主实验数据集、搭环境、实现方法、生成 resource plan 和 longrun ledger | 不获取只服务于 M4 消融的数据 |
| M3S03 | 获取/训练/验证 baselines，写 baseline_lock.yaml | 不把消融变体写入 baseline |
| M3S04 | 按本设计执行主实验，写 results.tsv 和 trained checkpoint evidence | 不把 E0/random/still-running 结果当最终结果 |
| M3S05 | 验证结果、打包证据、决定 KEEP/FIX/BACKTRACK | 不伪造 PASS 或忽略异常指标 |

---

## 6. Open Blockers

| blocker_id | 类型 | 影响 | 已尝试动作 | 下一步 | 是否阻塞推进 |
|------------|------|------|------------|--------|----------------|
| B-1 | metric / dataset / baseline value / checkpoint / license | ... | ... | ... | yes/no |

所有阻塞项必须在 M3S01 review 前解决或明确触发 REVISE/HALT。不得用模糊表述通过。
