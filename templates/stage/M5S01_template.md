# M5S01 Pre-Write Audit & Contribution Articulation

> Stage: M5S01 | Agent: Analysis | Module: M5 Writing

---

## 审计范围

对 M1-M4 全部产出进行系统性审计，确保写作前的证据基础完整、一致、可叙事。

**硬性通过条件**:
- 下表列出的上游文件必须真实存在且非空；不能只在报告中勾选 complete。
- 至少 1 个核心贡献必须标记为 `fully_supported`，并给出 `knowledge/M3/...` 或 `knowledge/M4/...` 证据路径。
- Evidence/Narrative/Citation Gap 中不得存在未解决的 High blocking gap。
- 数据一致性检查必须覆盖主指标、baseline、数据集、方法名称。
- 审计结论必须明确写出 `是否建议继续写作: 是` 或 `Writing readiness: yes`；否则不得进入 M5S02。

---

## 1. 上游文档完整性检查

| 模块 | 必需文档 | 状态 | 问题说明 |
|------|---------|------|---------|
| M1 | M1S02_literature_deepdive.md | ☐ | |
| M1 | M1_source_log.yaml | ☐ | |
| M1 | M1S03_research_question.md | ☐ | |
| M1 | M1S04_hypothesis_generation.md | ☐ | |
| M2 | M2S03_method_architecture.md | ☐ | |
| M2 | M2S04_algorithm_theory.md | ☐ | |
| M2 | M2S05_experiment_setup.md | ☐ | |
| M3 | M3S01_main_experiment_design.md | ☐ | |
| M3 | M3S04_main_experiment.md | ☐ | |
| M3 | M3S05_result_validation.md | ☐ | |
| M4 | M4S03_analysis_experiment.md | ☐ | |
| M4 | M4S04_analysis_results.md | ☐ | |
| Handoff | handoff_M4_M5.md | ☐ | |

---

## 2. 核心贡献点梳理（最多 3 个）

### Contribution 1
- **声明**: ...
- **支撑证据**: 引用 M?S?? 的具体段落/数据
- **证据状态**: ☐ fully_supported ☐ partially_supported ☐ unsupported
- **对应论文 section**: Introduction / Method / Experiments

### Contribution 2
- **声明**: ...
- **支撑证据**: ...
- **证据状态**: ...

### Contribution 3
- **声明**: ...
- **支撑证据**: ...
- **证据状态**: ...

---

## 3. Gap 识别

### Evidence Gap（证据缺口）
| 缺口描述 | 严重程度 | 是否阻塞写作 | 建议处理 |
|---------|---------|------------|---------|
| ... | High/Medium/Low | 是/否 | ... |

### Narrative Gap（叙事缺口）
| 缺口描述 | 严重程度 | 是否阻塞写作 | 建议处理 |
|---------|---------|------------|---------|
| ... | High/Medium/Low | 是/否 | ... |

### Citation Gap（引用缺口）
| 需要补充的引用类型 | 数量估计 | 是否阻塞写作 | 建议处理 |
|-------------------|---------|------------|---------|
| ... | N | 是/否 | ... |

---

## 4. 风格/排版参照审计

| 参照论文 | Venue / Journal | 相关性 | 可获取内容 | 用途 | 是否纳入风格蒸馏 |
|----------|-----------------|--------|-----------|------|----------------|
| ... | ... | 高/中/低 | full text / abstract / notes | 结构 / 叙事 / 图表 / 排版 | 是/否 |

- 风格蒸馏只抽取结构、段落功能、图表密度、版式约束、标题/摘要/结论写法，不复制原文句子
- 若参照论文与目标 venue 不一致，必须说明可迁移部分与不可迁移部分
- 建议保留 3-5 篇可读的参照论文供 M5S02 生成 Style & Layout Profile；不足 3 篇时必须说明原因和补救计划。

---

## 5. 数据一致性检查

| 检查项 | 来源 A | 来源 B | 是否一致 | 备注 |
|--------|--------|--------|---------|------|
| 主指标数值 | M3S04 | M3S05 | 是/否 | |
| 基线名称 | M2S05 | M3S03 | 是/否 | |
| 数据集名称 | M2S05 | M3S02 | 是/否 | |
| 方法名称 | M2S03 | M2S04 | 是/否 | |

---

## 6. 写作风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| ... | 高/中/低 | 高/中/低 | ... |

---

## 7. 审计结论

- **是否建议继续写作**: 是 / 否（需先修复以下问题）
- **必须先修复的阻塞问题**: ...
- **可在写作中并行修复的问题**: ...
- **建议的 M5S02 重点关注**: ...
