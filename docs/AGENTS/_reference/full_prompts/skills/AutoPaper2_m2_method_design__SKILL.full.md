---
name: AutoPaper2_m2_method_design
description: >
  AutoPaper2 Module 2 (Method Design) 全流程执行 Skill。
  当用户需要进入方法设计阶段时触发，包括：
  前置检查 (M1 完成状态) → M2S01 Cross-Domain Search → M2S02 Migration Analysis
  → M2S03 Method Architecture Design → M2S04 Algorithm & Theory Design
  → M2S05 Experiment Setup → M3S01 Main Experiment Design
  → Gate G2（Logic + Method + Novelty Critic）→ Handoff M2→M3。
  仅在用户明确指定进入 M2 或 M1 完成后建议进入 M2 时触发。
argument-hint: [现有项目路径或项目名称]
skill_role: stage
---

> **ORCHESTRATOR MANIFEST ⚠️ 绝对不可违反**
>
> **你（当前主 Agent）的身份是 ORCHESTRATOR / CONDUCTOR。**> **本 Skill 由你阅读并理解，但所有 Stage 执行和 Review 必须委派给对应 subagent。**
>
> ## 你的唯一合法行为
>
> 1. **读取状态** → `state/pipeline_state.yaml`
> 2. **决定下一步** → 调用 `conductor.get_next_action()`
> 3. **生成派发包** → `python scripts/state_manager.py dispatch stage <stage> --write`
> 4. **委派 subagent** → 将 `state/dispatch/*.md` 路径传给对应的 subagent
> 5. **等待结果** → 验证产出文件存在
> 6. **处理 verdict** → PASS 则 advance，非 PASS 则 backtrack 后回到步骤 2
>
> ## 违规检测
>
> 如果你正在准备直接写入以下目录中的任何文件，**你正在违规**：
> - `knowledge/M*/`
> - `drafts/`
> - `knowledge/reviews/*_review.md`
> - `artifacts/paper.*`
>
> **正确做法**：立即停止写入，运行 `python scripts/state_manager.py dispatch stage <stage> --write`，然后将 packet 路径委派给 subagent。
>
> ## 上下文恢复咒语（Context Recovery）
>
> > 如果你刚刚从暂停中恢复，不记得当前进度：
> > 1. 运行 `python scripts/state_manager.py status`
> > 2. 运行 `python scripts/state_manager.py dispatch next --write`
> > 3. 将生成的 packet 交给 subagent
> > 4. **你不得补充、修改、或代替 subagent 完成任何内容**
>
> ---

# M2 Method Design — 方法设计全流程

执行 AutoPaper2 的 **Module 2: Method Design**，完成从跨领域搜索到完整实验计划的完整方法设计流程。

## 触发条件

当用户说以下任意一种表述时触发本 Skill：

- "进入 M2"
- "方法设计"
- "设计实验"
- "M2 阶段"
- "设计方法"
- "method design"
- "继续 M2"

**不触发**的情况：
- 用户明确说 "进入 M1/M3/M4/M5"（应路由到对应 Stage）
- 用户明确说 "开始一个新项目"（应路由到 M1 Skill）
- 当前项目 M1 尚未完成（应提示用户先完成 M1）

## 默认行为 vs 显式项目指定

### 默认：复用当前项目

如果用户没有明确指定项目路径，默认复用当前活跃项目（`projects/` 下最新的项目目录）：

```bash
cd {framework_root}
python scripts/state_manager.py status
```

检查 `state/pipeline_state.yaml`：
- 如果 M1 已完成（`M1.status == completed`）→ 正常启动 M2
- 如果 M1 未完成 → 提示用户先完成 M1
- 如果 M2 已在进行中 → 从当前 stage 继续

同时读取 `state/research_brief.yaml`：
- foundation anchor 会被视为最接近的基线家族
- reference anchor 会被视为近邻比较对象

### 显式：进入指定项目

如果用户明确指定了现有项目，例如：
- "在 SemCom-Image 项目中执行 M2"
- "继续 SemCom-Image 的方法设计"
- 提供了项目路径如 `projects/XXX-YYYYMMDD-HHMMSS`

则定位到该项目，检查当前状态：
- 如果项目已完成 M2 → 询问是否回溯重新执行
- 如果项目在 M2 中间 → 从当前 stage 继续
- 如果项目尚未启动 M2 → 检查 M1 是否完成，然后正常启动

## 执行前检查清单

在启动 M2 之前，必须确认：

- [ ] 项目已定位（`projects/{name}-{timestamp}/` 存在）
- [ ] `state/pipeline_state.yaml` 可读
- [ ] M1 状态为 `completed`（或 `module_completed`）
- [ ] `knowledge/handoff_M1_M2.md` 存在且非空
- [ ] `state/research_brief.yaml` 可读，且 foundation/reference anchors 已被识别
- [ ] 当前 stage 为 M2S01 或用户明确要求重新执行 M2
- [ ] M2 螺旋计数 < 10（`spiral_count.M2 < 10`）

## 控制工作流

```
Phase 0: 进入 M2 前置检查
  → 检查 M1 状态是否为 completed
  → 读取 handoff_M1_M2.md
  → 检查技术方案库是否存在
  → 加载 AGENT.md: docs/AGENTS/method/AGENT.md
  → 设置 pipeline_state: M2S01 in_progress
  → 标记 M2 模块状态为 in_progress

Phase 1: M2S01 Cross-Domain Search
  → Method Agent 执行
  → Step 1: Gap 解构
  → Step 2: 跨领域/弱相关搜索（同模态/同任务/原理/结构）
  → Step 3: 候选方案初筛 + **M1 Source Log 交叉验证**
     → 将候选方案与 `knowledge/M1/M1_source_log.yaml` 中的全部条目比对
     → 标记每个方案：M1 已覆盖 / 机制重复 / 变体关系 / 新发现
     → 产出 M1-M2 交叉验证表作为 M2S01 产出的必要章节
  → Step 4: 搜索质量自检
  → 产出: knowledge/M2/M2S01_cross_domain_search.md
  → Stage-level Review: m2_search_quality 审查
     → verdict: REVISE → **Conductor 调用 backtrack() 后，必须重新调用 Method Agent subagent 修正 M2S01；主 agent 禁止直接修改**
     → verdict: BACKTRACK → **重新调用 Method Agent subagent 重新执行 M2S01**
  → Conductor advance: M2S01 → M2S02

Phase 2: M2S02 Migration Analysis
  → Method Agent 执行
  → 重点论文深入分析（问题结构映射、核心机制映射、适配差异）
  → 多方案对比与选择
  → 关键改进点必要性论证
  → 诚实性自检
  → 产出: knowledge/M2/M2S02_method_inspiration.md
  → Stage-level Review: m2_migration 审查
     → verdict: REVISE → **重新调用 Method Agent subagent 修正 M2S02；主 agent 禁止直接修改**
     → verdict: BACKTRACK → **重新调用 Method Agent subagent 重新执行 M2S01 或 Ideation Agent 重新执行 M1S04**
  → Conductor advance: M2S02 → M2S03

Phase 3: M2S03 Method Architecture Design
  → Method Agent 执行
  → 方法概述、问题形式化（符号定义+目标函数）
  → 总体架构设计
  → 关键组件设计（输入/输出规格、公式）
  → 与 M2S02 承诺的对应关系检查
  → 产出: knowledge/M2/M2S03_method_architecture.md
  → Stage-level Review: m2_design_review 审查（架构一致性+形式化完整性）
     → verdict: REVISE → **重新调用 Method Agent subagent 修正 M2S03；主 agent 禁止直接修改**
     → verdict: BACKTRACK → **重新调用 Method Agent subagent 重新执行 M2S02**
  → Conductor advance: M2S03 → M2S04

Phase 4: M2S04 Algorithm & Theory Design
  → Method Agent 执行
  → 完整算法流程（与 M2S03 组件对应）
  → 复杂度分析
  → 理论分析（收敛性、最优性，如有）
  → 与现有工作关系对比
  → 设计决策记录
  → 产出: knowledge/M2/M2S04_algorithm_theory.md
  → Stage-level Review: m2_design_review 审查（伪代码一致性+可实验化+理论诚实性）
     → verdict: REVISE → **重新调用 Method Agent subagent 修正 M2S04；主 agent 禁止直接修改**
     → verdict: BACKTRACK → **重新调用 Method Agent subagent 重新执行 M2S03 或 M2S02**
  → Conductor advance: M2S04 → M2S05

Phase 5: M2S05 Experiment Setup
  → Method Agent 执行
  → 数据集选择、预处理、伦理与许可证
  → **Baseline 发现（多方法互补）**: 通过直接发现（M1 Source Log）、间接发现（论文对比基线反向追踪）、关键词/数据库搜索、引用链追踪等多种方法发现候选基线
  → Baseline 综合评估（技术相关性、可复现性、对比价值、维度覆盖、资源约束）→ 确定最终 baseline 列表
  → 代码可用性验证（GitHub/论文/社区三重确认）、公平性保证
  → 实验协议（超参数、训练/评估、固定随机种子=42）
  → 可复现性检查清单
  → 产出: knowledge/M2/M2S05_experiment_setup.md
  → 产出: knowledge/M2/M2S05_baseline_discovery_supplement.md（如使用了间接发现，记录候选基线与评估结果）
  → Stage-level Review: m2_experiment_design_review 审查
     → verdict: REVISE/BACKTRACK → **重新调用 Method Agent subagent 修正 M2S05；主 agent 禁止直接修改**
  → Conductor advance: M2S05 → M3S01

Phase 6: M3S01 Main Experiment Design
  → Method Agent 执行
  → 计划总览、执行顺序与分支逻辑
  → 成功/失败判定标准
  → 风险评估与应对
  → 资源预算
  → 消融实验仅做调度预留
  → 产出: knowledge/M2/M3S01_main_experiment_design.md
  → Stage-level Review: m3_main_experiment_design_review 审查
     → verdict: REVISE/BACKTRACK → **重新调用 Method Agent subagent 修正 M3S01；主 agent 禁止直接修改**
  → Conductor advance: M3S01 → Gate G2

Phase 7: Gate G2 审查
  → Logic Critic 审查 → G2_logic_review.md
  → Method Critic 审查 → G2_method_review.md
  → Novelty Critic 审查 → G2_novelty_review.md
  → 综合 verdict:
     → 全部 PASS → 进入 Handoff
     → 任一 REVISE / BACKTRACK / FIX → **Conductor 调用 backtrack() 更新状态后，必须调用对应 subagent（Method Agent 或跨模块的 Survey/Ideation Agent）重新执行目标 stage；主 agent 绝对禁止直接修改 stage 文件**
     → 任一 HALT → 终止 M2

Phase 8: Handoff & 完成
  → 产出: knowledge/handoff_M2_M3.md
  → 标记 M2 模块 completed
  → 报告完成状态，建议下一步（进入 M3）
```

## Agent 调用规范

### Method Agent（Phase 1-6）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/method/AGENT.md`
- 当前 stage（M2S01-M2S05）
- 上游输入文档路径
- 产出路径
- 如果是 M2S01，必须强调跨领域/弱相关搜索义务
- **如果是回溯后的重新执行，必须完整传递 `backtrack_advice`（blocking_reason, required_fix, success_criteria, rebuild_mode, evidence_paths 等）**

**Method Agent subagent 工具集**: ReadFile, WriteFile, Shell, WebSearch

**强制规则**：主 agent（Conductor/Skill）不得直接修改 Method Agent 的产出文件；所有修正必须通过重新调用 Method Agent subagent 完成。

### Stage-level Reviewers（Phase 1-6）

#### m2_search_quality（M2S01 审查）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/m2_search_quality/AGENT.md`
- M2S01 产出路径
- 产出路径：`knowledge/reviews/M2S01_search_quality_review.md`

#### m2_migration（M2S02 审查）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/m2_migration/AGENT.md`
- M2S02 产出路径
- M2S01 产出路径（辅助）
- 产出路径：`knowledge/reviews/M2S02_migration_review.md`

#### m2_design_review（M2S03 审查）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/m2_design_review/AGENT.md`
- M2S03 产出路径
- M2S02 产出路径（辅助，验证架构与思想映射一致性）
- 产出路径：`knowledge/reviews/M2S03_design_review.md`

#### m2_design_review（M2S04 审查）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/m2_design_review/AGENT.md`
- M2S04 产出路径
- M2S03 产出路径（辅助，验证算法与架构一致性）
- M2S02 产出路径（辅助，验证算法与思想映射一致性）
- 产出路径：`knowledge/reviews/M2S04_design_review.md`

#### m2_experiment_design_review（M2S05 审查）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/m2_experiment_design_review/AGENT.md`
- M2S05 产出路径
- M2S03/M2S04 方法设计产出路径（辅助，验证实验能否检验方法主张）
- M1 假设/Gap 相关路径（辅助，验证每个实验目的）
- 产出路径：`knowledge/reviews/M2S05_experiment_design_review.md`

#### m3_main_experiment_design_review（M3S01 审查）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/m3_main_experiment_design_review/AGENT.md`
- M3S01 产出路径
- M2S05 实验设置路径
- M2S03/M2S04 方法设计产出路径（辅助，验证执行计划与方法一致）
- 产出路径：`knowledge/reviews/M3S01_experiment_plan_review.md`

### Gate G2 Critics（Phase 7，并行执行）

#### Logic Critic

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/logic/AGENT.md`
- M2S01-M2S05 全部产出路径
- M1S03-M1S04 产出路径（辅助，验证假设链条）
- 产出路径：`knowledge/reviews/G2_logic_review.md`

#### Method Critic

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/method/AGENT.md`
- M2S01-M2S05 全部产出路径
- 产出路径：`knowledge/reviews/G2_method_review.md`

#### Novelty Critic

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/novelty/AGENT.md`
- M2S01-M2S05 全部产出路径
- M1S02 产出路径（辅助，检查 M1 遗漏）
- 产出路径：`knowledge/reviews/G2_novelty_review.md`

## 状态管理规范

每完成一个 Stage，必须更新 `state/pipeline_state.yaml`。

使用 Python 脚本更新：

```python
from spiral.state import PipelineState
from pathlib import Path

proj = Path("projects/XXX")

# PipelineState
state = PipelineState(proj)
state.record_completion("M2S01", "method", Path("knowledge/M2/M2S01_cross_domain_search.md"))
state.set_stage("M2S02", "in_progress")

# 螺旋计数（回溯时递增）
spiral_count = state.data.get("spiral_count", {})
spiral_count["M2"] = spiral_count.get("M2", 0) + 1
state.data["spiral_count"] = spiral_count
state.save()
```

## 质量门控

在每个关键节点执行自动检查：

| 节点 | 检查项 | 失败处理 |
|------|--------|---------|
| M2S01 完成后 | 搜索维度≥3、候选方案≥3、M2_source_log.yaml 完整 | REVISE → M2S01 |
| M2S02 完成后 | 映射到算法步骤、改进点有必要性论证、诚实性自检完整 | BACKTRACK → M2S02 或 M2S01 |
| M2S03 完成后 | 产出文件非空、有形式化描述、组件接口明确、与 M2S02 对应 | REVISE → M2S03 |
| M2S04 完成后 | 算法流程与架构一致、复杂度与伪代码一致、理论不自相矛盾 | REVISE → M2S04 |
| M2S05 完成后 | 数据集可获取、**外部基线≥5个且覆盖≥4个维度**、**基线发现过程有记录**（使用了哪些发现方法、评估维度、最终选择理由）、**代码可用性经三重验证**、baseline 公平、超参数有依据、固定随机种子=42、逐实验目的/假设/指标完整、m2_experiment_design_review PASS | BACKTRACK → M2S05 |
| M3S01 完成后 | 执行顺序清晰、成功/失败标准明确、风险有应对、完整实验报告蓝图覆盖每个实验、证据保存协议明确、m3_main_experiment_design_review PASS | BACKTRACK → M3S01 |
| Gate G2 | Logic ≥7.0 AND Method ≥7.0 AND Novelty ≥7.0 | BACKTRACK 或 REVISE |
| Handoff 前 | 所有 M2 产出文件存在 | 阻止完成 |

## Checkpoint 与用户交互

以下节点默认向用户发送进度更新（非阻塞，继续执行）：

1. **M2S01 完成后**: "跨领域搜索完成。发现 [N] 个候选方案，来自 [M] 个不同领域。"
2. **M2S02 完成后**: "迁移分析完成。主方案：[方案名称]，关键改进点：[N] 个。"
3. **M2S03 完成后**: "方法架构设计完成。核心组件：[组件列表]。"
4. **M2S04 完成后**: "算法与理论设计完成。算法流程已定义，复杂度已分析。"
5. **M2S05 完成后**: "实验设置完成。数据集：[名称]，baseline：[N] 个。"
6. **Gate G2 完成后**: "Gate G2 通过（Logic: X/10, Method: X/10, Novelty: X/10），进入实验执行阶段。"
7. **M2 完成后**: "M2 方法设计完成。核心方法：[摘要]。建议进入 M3（实验执行）。"

如果用户要求暂停或介入（如 "等一下"、"先别继续"），在下一个 Checkpoint 停止并等待用户指令。

## 输出协议

遵循 AutoPaper2 的输出协议：

1. **Output Versioning**: 首次写入时带时间戳，然后复制到固定名
2. **Output Manifest**: 每个产出记录到项目根目录的 `MANIFEST.md`
3. **Output Language**: 默认中文（与用户一致），用户可覆盖

M2 核心产出清单：
- `knowledge/M2/M2S01_cross_domain_search.md`
- `knowledge/M2/M2S02_method_inspiration.md`
- `knowledge/M2/M2S03_method_architecture.md`
- `knowledge/M2/M2S04_algorithm_theory.md`
- `knowledge/M2/M2S05_experiment_setup.md`
- `knowledge/M2/M3S01_main_experiment_design.md`
- `knowledge/reviews/M2S01_search_quality_review.md`（如触发审查）
- `knowledge/reviews/M2S02_migration_review.md`（如触发审查）
- `knowledge/reviews/M2S03_design_review.md`（如触发审查）
- `knowledge/reviews/M2S04_design_review.md`（如触发审查）
- `knowledge/reviews/M2S05_experiment_design_review.md`
- `knowledge/reviews/M3S01_experiment_plan_review.md`
- `knowledge/reviews/G2_logic_review.md`
- `knowledge/reviews/G2_method_review.md`
- `knowledge/reviews/G2_novelty_review.md`
- `knowledge/handoff_M2_M3.md`

## Context Recovery

如果上下文被压缩或 session 中断，恢复流程：

1. 读取 `state/pipeline_state.yaml` → 确认当前 stage
2. 读取 `state/decision_log.md` → 恢复最近决策
3. 读取当前 stage 的 AGENT.md
4. 读取最近的产出文件，恢复上下文
5. 从当前 stage 继续执行（不重新执行已完成的 stage）

**CLI 辅助命令**：
```bash
# 查看当前项目状态
python scripts/state_manager.py status

# 查看当前 stage 的自动执行计划
python scripts/state_manager.py auto-stage M2S01

# 自动运行当前模块
python scripts/state_manager.py auto-module M2
```

## Key Rules

- **M1 必须先完成**：M2 的入口条件是 M1 已完成。如果 M1 未完成，拒绝启动 M2。
- **Method Agent 统一负责 M2S01-S06**：方法设计是一个连贯的思维过程，不拆分到不同 Agent。
- **跨领域搜索是 M2S01 的核心义务**：必须基于 M1 的 Gap 主动搜索弱相关领域，不能只引用 M1 的方案库。
- **Stage-level Reviewer 必须独立**：每个 Stage 审查由独立的 Reviewer subagent 执行，不得与 Method Agent 同实例。
- **Gate G2 必须三 Critic**：Logic + Method + Novelty 三个 Critic 都通过才算 Gate 通过。
- **消融实验仅做调度预留**：M3S01 不设计消融细节，详细消融设计留给 M4。
- **Handoff 文件必须生成**：M2 完成后必须产出 `knowledge/handoff_M2_M3.md`。
- **跨模型隔离必须遵守**：Method Agent 与 Method Critic 不得由同一模型实例执行（参见 `docs/AGENTS/critic/cross_model_protocol.md`）。
- **螺旋上限为 10**：M2 模块最多允许 10 次回溯，超过则 HALT，需人工介入。
- **失败时诚实报告**：如果某个 stage 无法通过（如 Gate HALT、螺旋超限），必须明确报告原因，不强行推进。
