# M4S02 Deep Analysis Experiment Design

> Stage: M4S02
> Agent: Analysis Agent
> Output: `knowledge/M4/M4S02_analysis_experiment_design.md`

---

## 1. 分析目标

（要验证的深层问题，如"为什么方法有效？""组件 A 的作用机制是什么？"）

> 设计约束: 分析目标必须明确对应 ablation / mechanism / robustness / failure 至少一类；若 slice 涉及性能优劣比较，必须说明是否纳入 baseline。
> 必须显式覆盖 How / Where / Why：怎么 work、在哪里 work / 不 work、为什么 work。每个目标应连接到 M2S05/M2S06 实验设计、M3S04 KEEP 证据或 `handoff_M3_M4.md` 中的 claim。

## 2. Slice 列表

### Slice: [Ana-ID] ([类型])
- **analysis_type**: ablation / mechanism / robustness / failure / other
- **research_question**: 
- **hypothesis**: 
- **intervention**: 
- **controls**: 
- **metric**: 
- **comparison_target**: 
- **baseline_inclusion**: required / optional / no
- **literature_basis**: 参考了哪些文献、数据库条目或相关领域做法
- **expected_pattern**: 预期结果模式，例如 Full > w/o A、ours 在 mild noise 下优于 baseline、机制指标与目标区域对齐
- **evidence_criteria**: 判断该 slice 是否提供了可写入论文的证据
- **stop_condition**: 
- **paper_role**: main_text / appendix / reference_only
- **claim_links**: 

### Slice 设计原则
- 同一条 claim 下的多个 slice 必须写清楚彼此关系，避免一次改动多个变量。
- 消融 slice 只能改一个组件或一个机制开关，不能混合多个因素。
- 机制 slice 需要说明为何该可视化/探针能回答机制问题，并列出替代解释。
- 鲁棒性 slice 必须说明扰动类型、扰动强度和是否与 baseline 同跑。
- 失败 slice 需要写明它失败的原因是模型、环境、数据、指标还是方法本身。

## 3. Comparability Contract

- 与 M3 主实验的比较基准: ...
- 保持不变的条件: ...
- 允许变化的条件: ...
- 防止 apples-to-oranges 的措施: ...
- baseline 是否同跑: ...
- 如果不同比较对象不能直接对齐，必须写明这是边界/泛化/探索性证据，而不是主结论。

## 4. 执行信封审计

| Slice | 预估时间 | 预估资源 | 可行性 | 备注 |
|-------|---------|---------|--------|------|
|       |         |         | feasible / blocked | |

## 5. 与主实验的区别

（分析实验通常不同于主实验的评估指标或设置）

## 6. 文献/数据库依据
- 对照的论文/领域做法: ...
- 数据库条目或 source id: ...
- 上游 M2/M3 依据: `knowledge/M2/M2S06_full_experiment_plan.md`, `knowledge/M3/M3S04_result_validation.md`, `knowledge/handoff_M3_M4.md`
- 为什么该分析方式适合当前 claim: ...
