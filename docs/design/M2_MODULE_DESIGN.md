# M2 Module Design — Method Design (方法设计)

> **版本**: v0.1-draft
> **状态**: 构思阶段
> **对应旧版**: AutoPaper Phase 2 (S06-S10)
> **对应DeepScientist**: baseline + idea + experiment skills 的方法设计前段

---

## 1. 设计目标

M2 的核心使命是：**基于 M1 识别的研究缺陷（Gap），通过跨领域/弱相关文献搜索与思想迁移，设计创新性解决方案，并转化为严谨、可执行、可验证的方法论与实验方案。**

**关键认知修正**（⚠️ 重要）：
- M1 的核心产出是"**问题/缺陷**"（Gap），而非"解决方案库"
- M1 搜索的是**领域强相关**文献，但解决思路可以来自**弱相关领域**（跨模态、跨任务思想迁移）
- 例如：图像语义通信问题可以从计算机视觉中的相关思想获得灵感（模态相同/类似）
- M2 必须在 M1 的 Gap 基础上，**主动进行进一步的文献搜索**，寻找解决思路

与 DeepScientist 的区别：
- DeepScientist 的 `idea` skill 同时包含方向选择和方法构思，边界模糊
- AutoPaper2 将方向选择严格放在 M1，M2 负责"**针对已识别的问题，搜索并设计解决方案**"
- M2 的核心是**问题导向的方法探索**，而非假设导向的实验验证

---

## 2. Stage 架构 (5 Stages + 1 Gate)

```
M2S01: Cross-Domain Search         [Method Agent]  → knowledge/M2/M2S01_cross_domain_search.md
M2S02: Migration Analysis          [Method Agent]  → knowledge/M2/M2S02_method_inspiration.md
M2S03: Method Architecture Design  [Method Agent]  → knowledge/M2/M2S03_method_architecture.md
M2S04: Algorithm & Theory Design   [Method Agent]  → knowledge/M2/M2S04_algorithm_theory.md
M2S05: Experiment Setup            [Method Agent]  → knowledge/M2/M2S05_experiment_setup.md
M2S06: Full Experiment Plan        [Method Agent]  → knowledge/M2/M2S06_full_experiment_plan.md
        └── Gate G2 [Logic + Method + Novelty Critic] ──►
Handoff M2→M3                      [Conductor]     → knowledge/handoff_M2_M3.md
```

### 2.1 与旧版 AutoPaper 的映射

> **重要变更**: M2 从 5 Stage 扩展为 6 Stage。原 S06 Methodology Design 拆分为 M2S01(搜索)+M2S02(迁移)+M2S03(架构)+M2S04(算法理论)；原 S07-S09 合并为 M2S05 Experiment Setup。

| AutoPaper2 M2 | 旧版 AutoPaper S-Stage | 核心差异 |
|---------------|------------------------|---------|
| M2S01 | — (新增) | 从原 S06 拆出的跨领域搜索阶段 |
| M2S02 | — (新增) | 从原 S06 拆出的迁移分析阶段 |
| M2S03 | S06 Methodology Design (上半) | 方法架构设计：形式化+架构+组件 |
| M2S04 | S06 Methodology Design (下半) | 算法与理论：算法流程+复杂度+理论证明 |
| M2S05 | S07-S09 合并 | 数据集+baseline+实验协议合并为实验设置 |
| M2S06 | S10 Full Experiment Plan | 明确消融仅做调度预留 |

---

## 3. 各 Stage 详细设计

### M2S01: Cross-Domain Search

**目标**: 基于 M1 识别的 Gap，通过跨领域/弱相关文献搜索，建立候选方案池。

**输入**:
- `knowledge/handoff_M1_M2.md` (M1 所有产出摘要，重点是**Gap 列表**)
- `knowledge/M1/M1S02_literature_deepdive.md` (§4 Gap 分析，了解当前领域强相关工作的局限)
- `knowledge/M1/M1S03_research_question.md` (核心研究问题)
- `knowledge/M1/M1S04_hypothesis_generation.md` (核心假设)
- `knowledge/M1/M1S05_novelty_feasibility.md` (可行性评估)

**关键约束**:
> **M1 的"技术方案库"仅作为强相关参考，不是唯一来源。** Method Agent 应基于 M1 的 Gap，主动进行**跨领域/弱相关文献搜索**，寻找可以解决这些 Gap 的思想、方法或技术。

**输出**: `knowledge/M2/M2S01_cross_domain_search.md`

**质量标准**:
- [ ] **Gap→技术问题拆解清晰**：每个核心 Gap 都拆解为可搜索的技术问题
- [ ] **搜索维度覆盖 ≥3**：同模态不同任务、同任务不同模态、底层原理、相似结构
- [ ] **候选方案池 ≥3**：来自 ≥2 个不同领域，每个方案有适用性评估
- [ ] **M2_source_log.yaml 完整**：记录搜索维度、目标 Gap、来源领域等
- [ ] 与 M1 内容对应（搜索方向必须针对 M1 识别的 Gap）

**可回溯原因**:
- Gap 拆解方向错误 → BACKTRACK → M2S01（重新确认映射；如需刷新交接，在 `handoff_updates` 中标记 `handoff_M1_M2.md`）
- M1 的 Gap 本身不具体 → BACKTRACK → M1S03 或 M1S02
- 搜索全部来自同一领域 → BACKTRACK → M2S01 重新设计搜索策略

---

### M2S02: Migration Analysis

**目标**: 对 M2S01 筛选出的重点方案进行深入分析，完成思想映射、适配分析和方案选择

**输入**:
- `knowledge/M2/M2S01_cross_domain_search.md` (候选方案池)
- `knowledge/M1/M1S02_literature_deepdive.md` (现有工作信息)

**关键约束**:
> 思想映射必须到**算法步骤级别**，不能停留在概念层面。每个改进点必须说明"必要性"（不改会怎样）。

**输出**: `knowledge/M2/M2S02_method_inspiration.md`

**质量标准**:
- [ ] 重点论文有结构化的问题映射（输入/输出/约束对比）
- [ ] 核心机制映射到算法步骤级别
- [ ] 适配差异分析完整（数据特性、优化目标、约束条件、评价指标）
- [ ] 改进点为"必要适配"而非"装饰性修改"
- [ ] 诚实性自检完成（4项检查）

**可回溯原因**:
- 跨域方案完全不适用 → BACKTRACK → M2S01 重新搜索
- 所有跨域方案都无法验证 M1 假设 → BACKTRACK → M1S04 修正假设
- 存在"伪改进" → BACKTRACK → M2S02 重新分析

---

### M2S03: Method Architecture Design

**目标**: 基于 M2S02 的方案选择，设计方法的高层架构、问题形式化和关键组件

**输入**:
- `knowledge/M2/M2S02_method_inspiration.md` (方案选择、改进点)
- `knowledge/M1/M1S03_research_question.md` (核心研究问题)
- `knowledge/M1/M1S04_hypothesis_generation.md` (核心假设)

**输出**: `knowledge/M2/M2S03_method_architecture.md`

**质量标准**:
- [ ] 方法概述包含核心思想来源声明
- [ ] 问题形式化完整（输入、输出、目标函数、约束）
- [ ] 符号定义表完整
- [ ] 总体架构清晰（文字+框图）
- [ ] 关键组件设计含输入/输出规格
- [ ] 与 M2S02 承诺的对应关系明确
- [ ] 设计决策记录完整

**可回溯原因**:
- 组件设计无法支撑算法实现 → BACKTRACK → M2S03 重新设计
- 方案漂移（偏离 M2S02 承诺）→ BACKTRACK → M2S02 重新分析

---

### M2S04: Algorithm & Theory Design

**目标**: 在 M2S03 架构基础上，完成算法流程、复杂度分析、理论证明和设计决策记录

**输入**:
- `knowledge/M2/M2S03_method_architecture.md` (架构设计)
- `knowledge/M2/M2S02_method_inspiration.md` (思想映射)

**输出**: `knowledge/M2/M2S04_algorithm_theory.md`

**质量标准**:
- [ ] 算法流程与 M2S03 组件设计一一对应
- [ ] 伪代码中每个变量在符号定义表中有定义
- [ ] 复杂度分析与伪代码一致
- [ ] 理论分析诚实（证明成立、假设不过度理想化）
- [ ] 与现有工作的对比表完整
- [ ] 设计决策记录完整

**可回溯原因**:
- 伪代码与架构不一致 → REVISE → M2S04
- 理论证明与伪代码矛盾 → BACKTRACK → M2S04 重新设计
- 核心假设无法被实验验证 → BACKTRACK → M1S04 修正假设

---

### M2S05: Experiment Setup

**目标**: 选择数据集、baseline、设计实验协议，确保可复现性

**输入**:
- `knowledge/M2/M2S04_algorithm_theory.md` (方法设计)
- `knowledge/M1/M1S02_literature_deepdive.md` (现有工作、baseline 信息、**代码可用性标注** ★)

**关键约束**:
> - 和消融设计不冲突
> - 参考 M1S02 的代码可用性标注：对未开源或代码不可运行的 baseline 降权
> - Subagent 检查可行性

**输出**: `knowledge/M2/M2S05_experiment_setup.md`

**质量标准**:
- [ ] 数据集领域标准、公开可用、许可证合规
- [ ] 预处理清晰、可复现
- [ ] Baseline 覆盖主要竞争方法、公平性保证
- [ ] 超参数固定且有选择依据
- [ ] 随机种子：至少 3 个不同种子
- [ ] 评估指标明确，含统计检验方法
- [ ] 可复现检查清单完整

**Baseline 代码可用性分级**:
| 级别 | 描述 | 处理策略 |
|------|------|---------|
| A | 开源且有维护 | 优先选择 |
| B | 开源但不可运行 | 降权，需自行修复或复现 |
| C | 未开源 | 最后选择，需根据论文自行实现 |

**可回溯原因**:
- 数据集与任务不匹配 → BACKTRACK → M2S04 或 M1S03
- 无合适公开数据集 → BACKTRACK → M1S03 (调整问题范围)

---

## 4. Gate G2 设计

### 4.1 审查维度

| Critic | 审查重点 | 通过标准 |
|--------|---------|---------|
| **Logic** | 方法逻辑是否自洽、能否回答假设、实验设计是否合理 | 方法→假设→实验的链条完整 |
| **Method** | 跨域迁移是否严谨、算法设计是否正确、baseline 是否公平 | 方法设计无重大缺陷 |
| **Novelty** | 方法是否有实质性创新、与现有工作对比是否清晰 | 有明确创新点，非简单组合 |

### 4.2 审查产出

```
knowledge/reviews/
├── G2_logic_review.md
├── G2_method_review.md
└── G2_novelty_review.md
```

### 4.3  verdict 规则

- **PASS**: 所有 Critic ≥ 7/10，无 BACKTRACK 意见
- **REVISE**: 某 Critic 发现问题但可在当前模块内修复 → 回溯到指定 M2 Stage
- **BACKTRACK**: 根本性问题 → 回溯到 M1 (M1S04 假设/M1S03 问题) 或 M2 上游 Stage
- **HALT**: 无法继续 → 终止，需人工介入

### 4.4 与 G1 的关键差异

| | Gate G1 (M1) | Gate G2 (M2) |
|--|-------------|--------------|
| Critic | Coverage + Logic + Novelty | Logic + Method + Novelty |
| 审查对象 | 调研质量、问题定义 | 跨域迁移质量、方法严谨性、实验可行性 |
| 回溯目标 | M1 内部 Stage | M2 内部 或 M1 |
| 核心问题 | "问题值得研究吗？" | "方法能回答这个问题吗？" |

---

## 5. Handoff 文档

### 5.1 M1→M2 Handoff (输入)

由 M1 产出，M2 读取：

```markdown
# Handoff: M1 → M2

## 已完成的工作摘要
- 主题界定、文献调研 (N篇核心文献)
- 识别 M 个 Gap，选定核心 Gap
- 生成研究问题和可检验假设
- 可行性评估：PROCEED

## 关键决策记录
- 选择 Gap-X 而非 Gap-Y，原因：...
- 核心假设 H0：...

## 传递给 M2 的核心信息
- **核心 Gap 列表**: ...（M2S01 必须针对每个 Gap 拆解技术问题并搜索）
- **核心研究问题**: ...（方法设计必须回答的问题）
- **核心假设**: ...（方法需要验证的假设）
- **当前领域强相关工作局限**: M1S02 中总结的竞争方法局限（供 M2S01 明确"需要超越什么"）
- **Baseline 候选**: M1S02 中提到的竞争方法（供 M2S05 参考）
- **数据集线索**: M1S02 中现有工作使用的数据集（供 M2S05 参考）
- **代码可用性**: 各 baseline 的代码状态（供 M2S05 参考）
- **⚠️ 关键提示**: M1 搜索的是领域强相关文献，M2 应在此基础上进行**跨领域/弱相关搜索**，寻找创新解决思路

## 已知风险与限制
- 风险1：...

## 下游需要特别注意
- 注意1：M1 的"技术方案库"仅作参考，M2 的核心任务是**基于 Gap 进行跨领域搜索**
- 注意2：M2S03 架构设计必须忠实于 M2S02 的思想映射，不能方案漂移
- 注意3：baseline 选择参考代码可用性标注
```

### 5.2 M2→M3 Handoff (输出)

由 M2 产出，M3 读取：

```markdown
# Handoff: M2 → M3

## 已完成的工作摘要
- 完成了跨领域搜索和迁移分析（M2S01-M2S02）
- 设计了方法架构、算法流程和理论分析（M2S03-M2S04）
- 选择了数据集、baseline 和实验协议（M2S05）
- 制定了完整实验计划（M2S06）

## 关键决策记录
- 方法架构选择 A 而非 B，原因：...
- 跨域思想来源：...
- 数据集选择 X，原因：...
- Baseline 选择策略：...

## 传递给 M3 的核心信息
- **核心方法**: ...（1-2 句话概括）
- **方法架构**: M2S03 中的组件设计和接口定义
- **算法流程**: M2S04 中的伪代码和复杂度分析
- **代码实现路径**: 哪些组件需要从头实现，哪些可用现有库
- **实验配置**: 关键超参数、随机种子策略
- **Baseline 实现状态**: 哪些有官方代码，哪些需自行实现
- **成功标准**: 主实验达到什么指标算成功

## 已知风险与限制
- 风险1：某 baseline 无开源代码，需自行实现
- 风险2：某数据集预处理复杂

## 回溯历史
- M2 经历了 N 次回溯（如有）
```

---

## 6. Skill 设计: AutoPaper2_m2_method_design

### 6.1 触发条件

- 用户说 "进入 M2"
- 用户说 "方法设计"
- 用户说 "设计实验"
- M1 完成后自动建议进入 M2

### 6.2 控制工作流

```
Phase 0: 进入 M2 前置检查
  → 检查 M1 状态是否为 completed
  → 读取 handoff_M1_M2.md
  → 检查技术方案库是否存在
  → 加载 AGENT.md: docs/AGENTS/method/AGENT.md
  → 设置 pipeline_state: M2S01 in_progress

Phase 1: M2S01 Cross-Domain Search
  → Method Agent 执行
  → 产出: knowledge/M2/M2S01_cross_domain_search.md
  → Stage Review: m2_search_quality
  → Conductor advance: M2S01 → M2S02

Phase 2: M2S02 Migration Analysis
  → Method Agent 执行
  → 产出: knowledge/M2/M2S02_method_inspiration.md
  → Stage Review: m2_migration
  → Conductor advance: M2S02 → M2S03

Phase 3: M2S03 Method Architecture Design
  → Method Agent 执行
  → 产出: knowledge/M2/M2S03_method_architecture.md
  → Stage Review: m2_design_review
  → Conductor advance: M2S03 → M2S04

Phase 4: M2S04 Algorithm & Theory Design
  → Method Agent 执行
  → 产出: knowledge/M2/M2S04_algorithm_theory.md
  → Stage Review: m2_design_review
  → Conductor advance: M2S04 → M2S05

Phase 5: M2S05 Experiment Setup
  → Method Agent 执行
  → 产出: knowledge/M2/M2S05_experiment_setup.md
  → Stage Review: m2_experiment_design_review
  → Conductor advance: M2S05 → M2S06

Phase 6: M2S06 Full Experiment Plan
  → Method Agent 执行
  → 产出: knowledge/M2/M2S06_full_experiment_plan.md
  → Stage Review: m2_experiment_plan_review
  → Conductor advance: M2S06 → Gate G2

Phase 7: Gate G2 审查
  → Logic Critic 审查 → G2_logic_review.md
  → Method Critic 审查 → G2_method_review.md
  → Novelty Critic 审查 → G2_novelty_review.md
  → 综合 verdict:
     → 全部 PASS → 进入 Handoff
     → 任一 REVISE → 回溯到指定 M2 Stage
     → 任一 BACKTRACK → 回溯到 M1
     → 任一 HALT → 终止 M2

Phase 8: Handoff & 完成
  → 产出: knowledge/handoff_M2_M3.md
  → 标记 M2 模块 completed
  → 报告完成状态，建议下一步（进入 M3）
```

### 6.3 Agent 调用规范

**Method Agent**:
- 使用 subagent 执行
- Prompt 必须包含：
  - 完整读取 `docs/AGENTS/method/AGENT.md`
  - 当前 stage（M2S01-M2S06）
  - 上游输入文档路径
  - 产出路径
- 工具集: ReadFile, WriteFile, Shell, WebSearch

**Stage-level Reviewers**:
- m2_search_quality: M2S01 完成后审查搜索质量
- m2_migration: M2S02 完成后审查迁移分析
- m2_design_review: M2S03 和 M2S04 完成后审查设计质量
- m2_experiment_design_review: M2S05 完成后审查数据集、baseline、公平性、指标、逐实验目标和可复现性
- m2_experiment_plan_review: M2S06 完成后审查执行顺序、分支/回溯逻辑、逐实验报告蓝图和证据保存协议

**Gate G2 Critics** (并行执行):
- Logic Critic: 读取 `docs/AGENTS/critic/logic/AGENT.md`
- Method Critic: 读取 `docs/AGENTS/critic/method/AGENT.md`
- Novelty Critic: 读取 `docs/AGENTS/critic/novelty/AGENT.md`

---

## 7. 状态管理

### 7.1 pipeline_state.yaml 更新

```yaml
current:
  module: M2
  stage: M2S01  # → M2S02 → M2S03 → M2S04 → M2S05 → M2S06 → G2
  status: in_progress

modules:
  M2:
    status: in_progress  # → completed
    completed_at: null
    last_stage: null

history:
  - stage: M2S01
    agent: method
    completed_at: "..."
    output: "knowledge/M2/M2S01_cross_domain_search.md"
```

### 7.2 螺旋计数

```yaml
spiral_count:
  M1: 1
  M2: 1  # 每次回溯到 M2 时 +1，上限 10
```

---

## 8. 质量门控

| 节点 | 检查项 | 失败处理 |
|------|--------|---------|
| M2S01 完成后 | 产出文件非空、有形式化描述、有设计决策记录 | 重试一次，仍失败则 BACKTRACK → M1S04 |
| M2S02 完成后 | 数据集可获取、许可证合规、适配性分析完整 | BACKTRACK → M2S01 |
| M2S04 完成后 | baseline 与消融无冲突、代码可用性评估完整 | 要求补充 |
| M2S05 完成后 | 数据集获取/校验、baseline、公平性、指标/统计检验、相关工作协议、逐实验目的/假设、随机种子、可复现清单、m2_experiment_design_review PASS | BACKTRACK → M2S05 |
| M2S06 完成后 | 执行顺序、分支/回溯逻辑、成功/失败标准、风险/资源预算、逐实验完整报告蓝图、证据保存协议、m2_experiment_plan_review PASS | BACKTRACK → M2S06 |
| Gate G2 | Logic ≥7.0 AND Method ≥7.0 AND Novelty ≥7.0 | BACKTRACK 或 REVISE |
| Handoff 前 | 所有 M2 产出文件存在 | 阻止完成 |

---

## 9. 回溯策略

### 9.1 M2 内部回溯

```
M2S06 发现问题
  ├── 实验计划不完整 → 回溯到 M2S06 重新整合
  ├── baseline 选择有问题 → 回溯到 M2S05
  ├── 实验协议有缺陷 → 回溯到 M2S05
  ├── 算法设计有缺陷 → 回溯到 M2S04
  ├── 架构设计有缺陷 → 回溯到 M2S03
  ├── 迁移分析有缺陷 → 回溯到 M2S02
  └── 搜索不充分 → 回溯到 M2S01
```

### 9.2 跨模块回溯

```
Gate G2 或 M2S01-M2S02 发现根本性问题
  ├── 方法无法验证假设 → 回溯到 M1S04 (假设生成)
  ├── 问题定义不当导致方法设计困难 → 回溯到 M1S03 (研究问题)
  └── 文献调研遗漏关键方法 → 回溯到 M1S02 (文献调研)
```

---

## 10. 与 DeepScientist Skills 的对应关系

| DeepScientist Skill | AutoPaper2 M2 对应 | 说明 |
|---------------------|-------------------|------|
| `baseline` | M2S05 | baseline 选择、代码可用性评估 |
| `idea` (搜索) | M2S01 | 跨领域文献搜索 |
| `idea` (分析) | M2S02 | 思想映射与方案选择 |
| `idea` (设计) | M2S03, M2S04 | 方法架构与算法设计 |
| `experiment` (计划部分) | M2S05, M2S06 | 实验协议和计划 |
| `decision` | Gate G2 | 决策门控 |
| `optimize` | 不涉及 | M2 不做优化搜索，只做方案设计 |

---

## 11. 实现清单

### 11.1 需要创建的文件

```
skills/AutoPaper2_m2_method_design/
└── SKILL.md                          # M2 Skill 定义

templates/stage/
├── M2S01_template.md                 # Cross-Domain Search 模板
├── M2S02_template.md                 # Migration Analysis 模板
├── M2S03_template.md                 # Method Architecture Design 模板
├── M2S04_template.md                 # Algorithm & Theory Design 模板
├── M2S05_template.md                 # Experiment Setup 模板
└── M2S06_template.md                 # Full Experiment Plan 模板

docs/AGENTS/critic/method/
└── AGENT.md                          # Method Critic 定义 (G2)
```

### 11.2 需要更新的文件

```
spiral/project.py                     # MODULE_STAGES 扩展为 6 Stage
spiral/conductor.py                   # STAGE_CHECKERS 更新
docs/AGENTS/method/AGENT.md           # Stage 定义与模板对齐
docs/AGENTS/critic/m2_design_review/AGENT.md  # 审查对象更新
docs/design/M2_MODULE_DESIGN.md       # Stage 架构更新
docs/design/M1_M2_BACKTRACK_DIAGRAM.md # 回溯图更新
```

### 11.3 现有已就绪的文件

```
docs/AGENTS/critic/logic/AGENT.md     # ✅ Logic Critic (复用 G1)
docs/AGENTS/critic/novelty/AGENT.md   # ✅ Novelty Critic (复用 G1)
docs/AGENTS/critic/m2_search_quality/AGENT.md  # ✅ Search Quality Reviewer
docs/AGENTS/critic/m2_migration/AGENT.md       # ✅ Migration Reviewer
```

---

## 12. 关键设计决策

### 决策 1: 为什么 M2 扩展为 6 个 Stage？

原设计为 5 个 Stage，但 M2S01（Methodology Design）承载了过多内容：
- Gap 解构 + 跨领域搜索 + 思想映射 + 方法综合 + 形式化 + 伪代码 + 理论分析

**拆分理由**：
1. **上下文压力**：单 Stage 包含搜索、分析、设计、证明四个认知跨度，Agent 上下文难以承载
2. **审查粒度**：搜索质量、迁移合理性、架构设计、算法正确性需要不同的审查视角
3. **回溯精度**：如果理论证明有问题，不需要重新做跨领域搜索

**新 6-Stage 结构**：
- **跨领域搜索 (S01)** → 迁移分析 (S02) → 架构设计 (S03) → 算法理论 (S04) → 实验设置 (S05) → 整合计划 (S06)
- 每个 Stage 有明确边界，便于独立回溯

### 决策 2: 为什么 Method Agent 负责全部 6 个 Stage？

- 方法设计是一个连贯的思维过程，拆分到不同 Agent 会导致上下文丢失
- M2S01-M2S04 之间存在强依赖关系：搜索结果决定迁移方向，迁移分析决定架构设计，架构设计决定算法流程
- 实验设置（M2S05）和整合计划（M2S06）需要方法论的深度理解
- 与 M3 区分：M3 由 Experiment Agent 负责代码和运行

### 决策 3: Subagent 可行性检查的触发条件

不是每个 Stage 都强制触发，而是：
- **M2S01: 强制触发 Subagent 跨领域搜索验证**
  - Method Agent 完成跨领域搜索后，创建 Subagent 验证：
    - 搜索的弱相关领域是否确实与本问题有机制层面的相通性？
    - 提出的思想迁移是否合理？是否存在未被发现的更优方案？
- **M2S03: 强制触发 Subagent 架构可行性检查**
  - Method Agent 完成架构设计后，创建 Subagent 验证：
    - 组件接口是否明确？算法实现是否可行？
- M2S05: 当数据集需要特殊预处理或不确定是否适配时触发
- M2S05: 当 baseline 实现复杂或代码可用性存疑时触发

由 Method Agent 自行判断非强制 Stage 是否需要 Subagent 检查，并在产出中记录决策理由。

### 决策 4: 消融实验的位置

- M2S06 **不做消融的具体设计**，只做"预留调度"
- 消融的详细设计放在 **M4** (Deep Analysis 模块)
- 原因：消融需要基于主实验结果才能做合理设计，过早设计可能不符合实际

---

> **下一步**: 进入 Plan Mode，制定 M2 的具体实现计划。
