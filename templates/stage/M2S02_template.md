# M2S02: Method Inspiration & Adaptation Analysis

> **Stage**: M2S02
> **Module**: M2 — Method Design
> **Agent**: Method Agent
> **Input**: M2S01_cross_domain_search.md, M1S02_literature_deepdive.md
> **Output**: knowledge/M2/M2S02_method_inspiration.md

---

## 1. 重点分析论文清单

> 对 M2S01 筛选出的重点方案进行深入分析。

### 论文 1: {{paper_1_title}}

#### 1.1 论文基本信息
- **标题**: {{title}}
- **作者**: {{authors}}
- **年份/Venue**: {{year}}/{{venue}}
- **Public DB ID**: {{paper_id}}
- **入口锚点**: {{entry_anchor_id}} / foundation | reference | none
- **来源领域**: {{source_domain}}
- **原问题**: {{original_problem}}
- **核心方法**: {{core_method}}
- **关键创新点**: {{key_innovation}}
- **局限性（原文）**: {{original_limitations}}

#### 1.2 思想迁移分析

##### 问题结构映射
```
原论文问题结构          本问题结构
├─ 输入: {{orig_input}}    ───►   ├─ 输入: {{our_input}}
├─ 输出: {{orig_output}}   ───►   ├─ 输出: {{our_output}}
├─ 约束: {{orig_constraint}} ───► ├─ 约束: {{our_constraint}}
└─ 目标: {{orig_objective}}  ───► └─ 目标: {{our_objective}}
```
- **结构相似度**: 高 / 中 / 低
- **相似性论证**: {{similarity_reasoning}}

##### 核心机制映射
- **原论文机制**: {{original_mechanism}}
- **迁移到本问题后的机制**: {{adapted_mechanism}}
- **映射合理性论证**: {{mapping_reasoning}}

##### 需要适配的关键差异
| 差异维度 | 原论文 | 本问题 | 适配策略 | 适配难度 |
|---------|--------|--------|---------|---------|
| 数据特性 | {{orig_data}} | {{our_data}} | {{adaptation}} | 高/中/低 |
| 优化目标 | {{orig_obj}} | {{our_obj}} | {{adaptation}} | 高/中/低 |
| 约束条件 | {{orig_constraint}} | {{our_constraint}} | {{adaptation}} | 高/中/低 |
| 评价指标 | {{orig_metric}} | {{our_metric}} | {{adaptation}} | 高/中/低 |

#### 1.3 迁移后方法草图
- **核心组件**: {{core_components}}
- **算法流程（初步）**:
  ```
  1. ...
  2. ...
  3. ...
  ```
- **预期优势**: {{expected_advantages}}
- **潜在风险**: {{potential_risks}}

---

### 论文 2: {{paper_2_title}}
（同上格式，支持多篇深入分析）

...

### 论文 N: {{paper_n_title}}
（同上格式）

...

---

## 2. 方案对比与选择

### 2.1 多方案对比矩阵

| 对比维度 | 方案 A (论文X) | 方案 B (论文Y) | 方案 C (论文Z) | 方案 D (领域内改进) |
|---------|---------------|---------------|---------------|-------------------|
| **解决 Gap** | Gap-1, Gap-2 | Gap-1 | Gap-2 | Gap-1 |
| **来源领域** | {{domain_a}} | {{domain_b}} | {{domain_c}} | 本领域 |
| **创新性** | 高/中/低 | 高/中/低 | 高/中/低 | 高/中/低 |
| **适配难度** | 高/中/低 | 高/中/低 | 高/中/低 | 高/中/低 |
| **理论保证** | 有/弱/无 | 有/弱/无 | 有/弱/无 | 有/弱/无 |
| **实现复杂度** | 高/中/低 | 高/中/低 | 高/中/低 | 高/中/低 |
| **预期效果** | 显著提升/中等/小幅 | ... | ... | ... |
| **风险等级** | 高/中/低 | ... | ... | ... |

### 2.2 组合策略分析

> 是否可以将多个方案组合？

| 组合 | 可行性 | 互补性 | 复杂度 | 评估 |
|------|--------|--------|--------|------|
| A + B | ... | ... | ... | ... |
| A + D | ... | ... | ... | ... |

### 2.3 选择决策

**主方案**: {{main_solution}} (基于 {{paper_x}})
- **核心思想来源**: {{source_mechanism}}
- **选择理由**: {{selection_reason}}

**辅助方案/组件**: {{auxiliary_solution}} (基于 {{paper_y}})
- **辅助组件**: {{auxiliary_component}}
- **作用**: {{role}}

**放弃方案**: {{dropped_solution}}
- **放弃理由**: {{drop_reason}}

---

## 3. 方法启发总结

### 3.1 核心思想来源
- **来源论文**: {{source_paper_title}}, {{authors}}, {{year}}
- **来源机制**: {{source_mechanism}}
- **原始问题**: {{original_problem}}
- **引用关系**: 本文方法基于 [论文X] 的 [机制]，并进行了 [改进]

### 3.2 关键改进点

| 改进点 ID | 原方法的局限 | 我们的改进 | 改进必要性 | 技术深度 |
|----------|------------|-----------|-----------|---------|
| IMP-1 | {{original_limitation_1}} | {{our_improvement_1}} | {{necessity_1}} | 机制/架构/参数 |
| IMP-2 | {{original_limitation_2}} | {{our_improvement_2}} | {{necessity_2}} | 机制/架构/参数 |

> **必须说明**: 每个改进为什么是"必要的"而非"装饰性的"

### 3.3 本文方法贡献声明

- **贡献 1**: {{contribution_1}}
  - 类型: 跨领域首次应用 / 关键改进 / 全新设计
  - 证据: ...
- **贡献 2**: {{contribution_2}}
  - 类型: ...
  - 证据: ...

### 3.4 诚实性自检

- [ ] 是否存在已做过类似迁移的工作被遗漏？
- [ ] **候选论文的核心机制是否已在 M1 Source Log（`knowledge/M1/M1_source_log.yaml`）中被覆盖？** 如果覆盖，与 M1 文献的差异是否清晰？
- [ ] 改进是否只是参数调优级别？
- [ ] 是否过度夸大了创新？
- [ ] 如果审稿人问"这和论文X直接应用到本问题有什么区别？"，能否给出有说服力的回答？
- [ ] 如果审稿人问"M1 的文献调研中已经提到了类似方法，为什么 M2 还声称这是跨域新发现？"，能否给出有说服力的回答？

---

## 4. 传递给下游的信息

- **核心思想来源论文**: {{paper_id}}（M2S03 需要深入理解）
- **关键改进点**: IMP-1, IMP-2（M2S03 需要形式化设计）
- **预期方法架构**: {{expected_architecture}}（M2S03 的输入）
- **潜在风险**: {{risks}}（M2S03 需要规避或处理）
- **需要进一步调研的问题**: {{open_questions}}
