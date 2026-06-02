---
name: AutoPaper2_m5_writing
description: >
  AutoPaper2 Module 5 (Writing & Finalization) 全流程执行 Skill。
  当用户需要进入论文写作与定稿阶段时触发，包括：
  前置检查 (M4 完成状态) → M5S01 Pre-Write Audit → M5S02 Paper Outline
  → M5S04 Methodology → M5S05 Experiments & Results → M5S06 Analysis & Discussion
  → M5S03 Introduction & Related Work → M5S07 Abstract & Conclusion
  → M5S08 Full Draft Assembly & Compilation → M5S09 Full-Polish & Narrative Coherence Review
  → Gate G5（Logic + Writing + Evidence + Novelty + Ethics Critic）
  → 可选 Peer Review Simulation → Handoff M5→投稿/归档。
  M5S01 还会筛选高水平相近论文作为风格参照；M5S02 负责蒸馏出 Style & Layout Profile 和 Figure Style Profile。
  每个 Stage 完成后必须先通过对应 stage reviewer，再推进到下一个 Stage。
  仅在用户明确指定进入 M5 或 M4 完成后建议进入 M5 时触发。
argument-hint: [现有项目路径或项目名称]
skill_role: stage
---

> **ORCHESTRATOR MANIFEST ⚠️ 绝对不可违反**
>
> **你（当前主 Agent）的身份是 ORCHESTRATOR / CONDUCTOR。**
> **本 Skill 由你阅读并理解，但所有 Stage 执行和 Review 必须委派给对应 subagent。**
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

# M5 Writing & Finalization — 论文写作与定稿全流程

执行 AutoPaper2 的 **Module 5: Writing & Finalization**，完成从写作前审计到最终投稿包生成的完整论文生产流程。

## 触发条件

当用户说以下任意一种表述时触发本 Skill：

- "进入 M5"
- "开始写作"
- "写论文"
- "M5 阶段"
- "论文写作"
- "写作阶段"
- "继续 M5"

**不触发**的情况：
- 用户明确说 "进入 M1/M2/M3/M4"（应路由到对应 Stage）
- 当前项目 M4 尚未完成（应提示用户先完成 M4）

## 默认行为 vs 显式项目指定

### 默认：复用当前项目

如果用户没有明确指定项目路径，默认复用当前活跃项目（`projects/` 下最新的项目目录）：

```bash
cd {framework_root}
python scripts/state_manager.py status
```

检查 `state/pipeline_state.yaml`：
- 如果 M4 已完成（`M4.status == completed`）→ 正常启动 M5
- 如果 M4 未完成 → 提示用户先完成 M4
- 如果 M5 已在进行中 → 从当前 stage 继续

### 显式：进入指定项目

如果用户明确指定了现有项目，则定位到该项目，检查当前状态：
- 如果项目已完成 M5 → 询问是否回溯重新执行
- 如果项目在 M5 中间 → 从当前 stage 继续
- 如果项目尚未启动 M5 → 检查 M4 是否完成，然后正常启动

## 执行前检查清单

在启动 M5 之前，必须确认：

- [ ] 项目已定位（`projects/{name}-{timestamp}/` 存在）
- [ ] `state/pipeline_state.yaml` 可读
- [ ] M4 状态为 `completed`（或 `module_completed`）
- [ ] `knowledge/handoff_M4_M5.md` 存在且非空
- [ ] `knowledge/M4/M4S04_analysis_results.md` 存在且 Claim Ledger 完整
- [ ] 当前 stage 为 M5S01 或用户明确要求重新执行 M5
- [ ] M5 螺旋计数 < 10（`spiral_count.M5 < 10`）
- [ ] Venue 模板已复制到 `artifacts/latex_template/`

## 控制工作流

```
Phase 0: 进入 M5 前置检查
  → 检查 M4 状态是否为 completed
  → 读取 handoff_M4_M5.md
  → 读取 Claim Ledger 和核心证据文件
  → 检查 venue 模板与 LaTeX 环境
  → 加载 AGENT.md: docs/AGENTS/writing/AGENT.md
  → 设置 pipeline_state: M5S01 in_progress
  → 标记 M5 模块状态为 in_progress

Phase 1: M5S01 Pre-Write Audit & Contribution Articulation
  → Analysis Agent 执行
  → 审计 M1-M4 全部产出的完整性与一致性
  → 梳理核心贡献点（最多 3 个），标记证据支撑状态
  → 识别 evidence gap、narrative gap、citation gap
  → 筛选 3-5 篇相近高水平论文，记录可迁移的风格/排版参照
  → 产出: knowledge/M5/M5S01_pre_write_audit.md
  → Stage review: m5_prewrite_review → knowledge/reviews/M5S01_prewrite_review.md
  → Conductor advance: M5S01 → M5S02

Phase 2: M5S02 Paper Outline
  → Writing Agent 执行
  → venue 适配（页数预算、section 结构、特殊要求）
  → 蒸馏 Style & Layout Profile（仅抽取结构、节奏、图表密度、版式规律，不复制原文）
  → 蒸馏 Figure Style Profile（图像可读时抽取视觉语法；不可读时使用 caption / placement + venue preset）
  → Plotting Plan（图表位置、类型、数据映射）
  → Terminology & Symbol Table（全文术语统一）
  → Section-by-section 页数分配与故事线
  → **Section Plan 约束**: Experiments 与 Analysis/Discussion 合并为同一 section（如 "4. Experiments, Results and Analysis"）；Introduction 与 Related Work 根据 venue 惯例可作为独立 section 或合并为 "1. Introduction and Related Work"
  → 产出: knowledge/M5/M5S02_paper_outline.md
  → Stage review: m5_outline_style_review → knowledge/reviews/M5S02_outline_style_review.md
  → Conductor advance: M5S02 → M5S04

Phase 3: M5S04 Methodology
  → Writing Agent 执行
  → 问题形式化（与 M2S03 一致）
  → 方法概述 + 核心组件详细描述
  → 伪代码/算法框（必须引用上游 M2S04）
  → 架构图/机制图使用 scripts/generate_image.py（默认 image2/gpt-image-2；drawio 仅作可编辑替代）生成，并记录 backend + prompt + paper-framework-figure-studio-pro style reference
  → 理论分析（如有，引用 M2S04）
  → 产出: knowledge/M5/M5S04_methodology.md
  → Stage review: m5_method_figure_review → knowledge/reviews/M5S04_method_figure_review.md
  → Conductor advance: M5S04 → M5S05

Phase 4: M5S05 Experiments & Results
  → Writing Agent 执行
  → 实验设置（数据集、baseline、指标、超参数）
  → 主结果表格（数值必须与原始数据一致）
  → 实验结果图必须按 nature-figure 原则由原始数据 + 绘图代码生成（matplotlib / seaborn / plt），不得用 image2 或 drawio
  → 关键发现总结（不分析，只呈现；深层分析留给 M5S06）
  → **结构约束**: 本节内容最终将与 M5S06 合并为同一 section（如 "4. Experiments, Results and Analysis"），因此每个实验结果需为后续分析预留对应子节位置
  → 产出: knowledge/M5/M5S05_experiments_results.md
  → Stage review: m5_experiments_results_review → knowledge/reviews/M5S05_experiments_results_review.md
  → Conductor advance: M5S05 → M5S06

Phase 5: M5S06 Analysis & Discussion
  → Writing Agent 执行
  → **一一对应原则**: 每条分析、每个消融、每个机制解释必须直接对应 M5S05 中的一个具体实验结果
  → 深入解读（"So what?"）
  → 消融/机制/鲁棒性结果整合（引用 M4S03-M4S04）
  → 若使用分析图/机制图，必须注明是否示意图，以及 backend / 来源
  → Limitations 诚实披露
  → 负面结果可见
  → **结构约束**: 本节作为 Experiments section 的子节存在（如 4.3 Analysis and Discussion），不独立成 section
  → 产出: knowledge/M5/M5S06_analysis_discussion.md
  → Stage review: m5_analysis_discussion_review → knowledge/reviews/M5S06_analysis_discussion_review.md
  → Conductor advance: M5S06 → M5S03

Phase 6: M5S03 Introduction & Related Work
  → Writing Agent 执行
  → **写作顺序说明**: Introduction 和 Related Work 在 Method/Experiments/Analysis 之后写，确保故事线基于已锁定的完整内容
  → Introduction: 问题背景 → 现有方法局限 → 本文贡献 → 论文组织
  → Related Work: 主题分类 + 对比批判（必须指出 "与 [X] 不同，我们..."）
  → **结构灵活性**: 根据 venue 惯例和 M5S02 的 Section Plan，Introduction 与 Related Work 可作为两个独立 section，或合并为单一 section（如 "1. Introduction and Related Work"）
  → Anti-Leakage Prompt 强制附加
  → 产出: knowledge/M5/M5S03_introduction_relatedwork.md
  → Stage review: m5_intro_relatedwork_review → knowledge/reviews/M5S03_intro_relatedwork_review.md
  → Conductor advance: M5S03 → M5S07

Phase 7: M5S07 Abstract & Conclusion
  → Writing Agent 执行
  → Abstract: 一句话概括 + 问题 + 方法 + 主要结果（具体数值）+ 贡献
  → Conclusion: 总结核心贡献，不引入新内容
  → 数值一致性交叉验证（Abstract 与正文必须一致）
  → 产出: knowledge/M5/M5S07_abstract_conclusion.md
  → Stage review: m5_abstract_conclusion_review → knowledge/reviews/M5S07_abstract_conclusion_review.md
  → Conductor advance: M5S07 → M5S08

Phase 8: M5S08 Full Draft Assembly & Compilation
  → Writing Agent 执行整合
  → 合并 M5S03-M5S07 为完整 LaTeX 文档
  → **Section 合并**: M5S05（Experiments & Results）与 M5S06（Analysis & Discussion）合并为同一 section（如 "4. Experiments, Results and Analysis"），子节一一对应
  → 插入图表（引用 Plotting Plan）
  → 生成/更新 refs.bib
  → Build Verifier 执行：
     → LaTeX 编译（pdflatex → bibtex → pdflatex × 2）
     → Orphan Cite Gate：验证每个 \cite{KEY} 存在于 refs.bib
     → Anti-Leakage Check：扫描作者信息泄露
     → LaTeX Sanity：检查未定义引用、overfull box、页数超限
  → 产出: artifacts/paper.tex, artifacts/paper.pdf
  → 产出: knowledge/M5/M5S08_final_compilation.md（编译报告）
  → Stage review: m5_final_compilation_review → knowledge/reviews/M5S08_final_compilation_review.md
  → Conductor advance: M5S08 → M5S09

Phase 9: M5S09 Full-Polish & Narrative Coherence Review
  → Writing Agent 执行
  → **输入边界**: 读取 M5S08 生成的 `artifacts/paper.tex` 与 `artifacts/paper.pdf`；`paper.tex` 是唯一可编辑真源，`paper.pdf` 只用于渲染/版面检查
  → **叙事连贯性审阅**: 以读者视角通读最终稿，验证 Intro-Method-Experiments-Analysis 的承诺兑现链
  → 消除重复表述（Abstract/Intro/Conclusion 之间）
  → 句式多样性与阅读节奏优化
  → 段落衔接词与过渡句检查
  → 语态优化（被动/主动）
  → 冗余词删除
  → 跨章节篇幅平衡校验
  → 全文术语一致性最终检查
  → 全文数值一致性最终检查
  → 将修订写回 `artifacts/paper.tex`，重新编译并更新 `artifacts/paper.pdf`
  → 产出: knowledge/M5/M5S09_full_polish.md
  → Stage review: m5_full_polish_review → knowledge/reviews/M5S09_full_polish_review.md
  → Conductor advance: M5S09 → Gate G5

Phase 10: Gate G5 审查
  → Logic Critic 审查 → G5_logic_review.md
  → Writing Critic 审查 → G5_writing_review.md
  → Evidence Critic 审查 → G5_evidence_review.md
  → Novelty Critic 审查 → G5_novelty_review.md
  → Ethics Critic 审查 → G5_ethics_review.md
  → 综合 verdict:
     → 全部 PASS → 进入 Handoff
     → 任一 REVISE → 回溯到指定 M5 Stage
     → 任一 BACKTRACK → 回溯到 M5 内部 Stage 或跨模块到 M4/M3/M2
     → 任一 HALT → 终止 M5

Phase 11: Handoff & 完成
  → 产出: knowledge/handoff_M5_completion.md
  → 标记 M5 模块 completed
  → 生成投稿包（paper.pdf + supplementary.zip + source.zip）
  → 报告完成状态

可选增强（Gate G5 PASS 后）:
  → Peer Review Simulation: Review Agent 执行 3-reviewer 模拟评审
     → 产出: knowledge/reviews/M5_peer_review_simulation.md
     → 根据评审意见进入 Revision Loop（最多 3 轮，Accept/Revert Halt Rules）
```

## Agent 调用规范

### Analysis Agent（M5S01）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/analysis/AGENT.md`
- 当前 stage（M5S01）
- 上游输入文档路径（handoff_M4_M5.md, M3S03-M3S04, M4S03-M4S04）
- 风格参照输入：`knowledge/M1/M1S02_literature_deepdive.md`、`knowledge/M1/M1_source_log.yaml`
- `state/research_brief.yaml`（如存在，用于确认 foundation/reference anchors 的方法线归属）
- 产出路径：`knowledge/M5/M5S01_pre_write_audit.md`
- 强调 evidence gap、narrative gap、citation gap 的识别义务

**Analysis Agent subagent 工具集**: ReadFile, WriteFile, Shell

### Writing Agent（M5S02-M5S09）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/writing/AGENT.md`
- 当前 stage（M5S02-M5S09）
- 上游输入文档路径
- M5S02 需额外读取 `knowledge/M5/M5S01_pre_write_audit.md`、`knowledge/M1/M1S02_literature_deepdive.md`、`knowledge/M1/M1_source_log.yaml`
- `state/research_brief.yaml`（如存在，优先据此确认 related work 与 baseline lineage）
- M5S03-M5S09 需遵循 `knowledge/M5/M5S02_paper_outline.md` 中的 Style & Layout Profile 和 Figure Style Profile
- **写作顺序约束**: M5S04（Method）→ M5S05（Exp）→ M5S06（Analysis）→ M5S03（Intro/RW）→ M5S07（Abstract/Conclusion）→ M5S08（Assembly/Compile）→ M5S09（Final Polish）
- M5S03 写作时可引用 M5S04、M5S05、M5S06 的已完成产出，确保 Intro 的故事线基于完整内容
- M5S06 必须遵循 "一一对应原则"：每条分析直接对应 M5S05 中的一个具体实验结果
- M5S09 必须读取 M5S08 生成的 `artifacts/paper.tex` / `artifacts/paper.pdf`，执行最终润色、PDF 渲染检查和复编译；不得直接编辑 PDF
- 需要架构图/机制图时读取 `config/image_generation.yaml`、`config/figure_style_profiles.yaml` 并调用 `scripts/generate_image.py`（默认 image2；可切换 drawio，优先使用 `drawio.mcp_command` / `DRAWIO_MCP_COMMAND`）
- 架构图/机制图必须引用 `paper-framework-figure-studio-pro` 作为外部风格参考；只迁移层级、分组、箭头和出版风格，不复制具体图形创意
- 实验结果图必须引用 `nature-figure` 原则进行图形设计、导出和 QA；仍必须来自真实数据和绘图脚本
- 调用 image2 时必须传入 `--venue <venue_id>`；M5S02 已生成 Figure Style Profile 后，还必须传入 `--style-profile knowledge/M5/M5S02_paper_outline.md`
- 传入 image2 的 prompt 必须包含图目的、方法名、组件列表、箭头关系、版式、视觉风格和禁止项；默认还要禁止右侧说明栏、重复摘要列或其他多余叙事面板，但不能生成过度极简、单色、死板的方框图；图中标签只能来自上游方法文档或 prompt，不得让模型自行补充不存在的子模块
- 产出路径
- Venue 信息（从 `state/pipeline_state.yaml` 读取）
- Anti-Leakage Prompt 必须附加到所有内容生成调用
- 如果是 M5S08，必须包含 Build Verifier 调用指令；如果是 M5S09 且修改 `paper.tex`，必须执行同等复编译检查

**Writing Agent subagent 工具集**: ReadFile, WriteFile, Shell, WebSearch

### Build Verifier（M5S08 / M5S09 复编译）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/build_verifier/AGENT.md`
- `artifacts/paper.tex` 路径
- `artifacts/paper.pdf` 路径
- `refs.bib` 路径
- Venue 页数限制
- 产出编译报告

**Build Verifier subagent 工具集**: ReadFile, WriteFile, Shell

### M5 Stage Reviewers（每个 Stage 完成后）

使用独立 reviewer subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/m5_stage_review/AGENT.md`
- 当前 stage 与对应输出文档路径
- 当前 stage 产生或引用的图像/图表路径
- 对应 review 输出路径（见下表）

| Stage | Reviewer | Review Output |
|-------|----------|---------------|
| M5S01 | m5_prewrite_review | `knowledge/reviews/M5S01_prewrite_review.md` |
| M5S02 | m5_outline_style_review | `knowledge/reviews/M5S02_outline_style_review.md` |
| M5S04 | m5_method_figure_review | `knowledge/reviews/M5S04_method_figure_review.md` |
| M5S05 | m5_experiments_results_review | `knowledge/reviews/M5S05_experiments_results_review.md` |
| M5S06 | m5_analysis_discussion_review | `knowledge/reviews/M5S06_analysis_discussion_review.md` |
| M5S03 | m5_intro_relatedwork_review | `knowledge/reviews/M5S03_intro_relatedwork_review.md` |
| M5S07 | m5_abstract_conclusion_review | `knowledge/reviews/M5S07_abstract_conclusion_review.md` |
| M5S08 | m5_final_compilation_review | `knowledge/reviews/M5S08_final_compilation_review.md` |
| M5S09 | m5_full_polish_review | `knowledge/reviews/M5S09_full_polish_review.md` |

任何非 PASS verdict 都必须由 Conductor 触发同 stage revise 或跨 stage backtrack。

### Gate G5 Critics（Phase 10，并行执行）

#### Logic Critic

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/logic/AGENT.md`
- M5S01-M5S09 全部产出路径
- M1S03-M1S04, M2S03-M2S04, M3S03-M3S04, M4S04 产出路径（辅助，验证假设到论文的完整链条）
- 产出路径：`knowledge/reviews/G5_logic_review.md`

#### Writing Critic

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/writing/AGENT.md`
- M5S03-M5S09 产出路径
- 产出路径：`knowledge/reviews/G5_writing_review.md`

#### Evidence Critic

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/evidence/AGENT.md`
- M5S05-M5S09 产出路径
- `experiments/results.tsv` 和 `experiments/analysis_results.tsv` 路径
- 产出路径：`knowledge/reviews/G5_evidence_review.md`

#### Novelty Critic

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/novelty/AGENT.md`
- M5S01-M5S09 全部产出路径
- M1S02 产出路径（辅助，检查 M1 遗漏）
- 产出路径：`knowledge/reviews/G5_novelty_review.md`

#### Ethics Critic

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/ethics/AGENT.md`
- M5S01-M5S09 全部产出路径
- M3S01 产出路径（辅助，检查伦理合规）
- 产出路径：`knowledge/reviews/G5_ethics_review.md`

### Peer Review Simulation（可选增强）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/review/AGENT.md`
- `artifacts/paper.tex` 或 `artifacts/paper.pdf`
- M5S02_paper_outline.md
- M5S01_pre_write_audit.md
- M5S01 中列出的风格参照论文（仅用于结构/排版审阅，不用于文本复用）
- 产出路径：`knowledge/reviews/M5_peer_review_simulation.md`

**Review Agent subagent 工具集**: ReadFile, WriteFile, Shell

## 状态管理规范

每完成一个 Stage，必须更新 `state/pipeline_state.yaml`。

使用 Python 脚本更新：

```python
from spiral.state import PipelineState
from pathlib import Path

proj = Path("projects/XXX")

state = PipelineState(proj)
state.record_completion("M5S01", "analysis", Path("knowledge/M5/M5S01_pre_write_audit.md"))
state.set_stage("M5S02", "in_progress")

# 螺旋计数（回溯时递增）
spiral_count = state.data.get("spiral_count", {})
spiral_count["M5"] = spiral_count.get("M5", 0) + 1
state.data["spiral_count"] = spiral_count
state.save()

# 螺旋计数（回溯时递增）
spiral_count = state.data.get("spiral_count", {})
spiral_count["M5"] = spiral_count.get("M5", 0) + 1
state.data["spiral_count"] = spiral_count
state.save()
```

回溯后：
- `stale_stages` 代表需要重新跑的 downstream stage
- 被重新完成的 stale stage 必须自动清除 stale 标记
- `gate_re_review` 中的对应 gate 只有在重新通过后才能清除

## 质量门控

在每个关键节点执行自动检查：

| 节点 | 检查项 | 失败处理 |
|------|--------|---------|
| M5S01 完成后 | 贡献点 ≤3 个且有证据支撑、gap 识别完整、风格/排版参照审计完整 | REVISE → M5S01 |
| M5S02 完成后 | 大纲有页数预算、plotting plan、术语表、Style & Layout Profile、Figure Style Profile、venue 适配；Experiments 与 Analysis 合并为同一 section | REVISE → M5S02 |
| M5S04 完成后 | 有伪代码/算法框、与 M2S03-M2S04 一致、符号统一 | REVISE → M5S04 |
| M5S05 完成后 | 所有数值与原始数据一致、表格用 booktabs、图表有引用；每个实验结果为 M5S06 预留分析位置 | REVISE → M5S05 |
| M5S06 完成后 | 有深入解读（非重复数字）、与 M5S05 一一对应、Limitations 诚实、负面结果可见 | REVISE → M5S06 |
| M5S03 完成后 | Intro 长度 ≤1.5 页、RW 有对比批判、无泄露；Intro 故事线基于已完成的 Method/Exp/Analysis | REVISE → M5S03 |
| M5S07 完成后 | Abstract 有具体数值、Conclusion 无新内容、全文数值一致 | REVISE → M5S07 |
| M5S08 完成后 | LaTeX 编译通过、无 orphan cite、无泄露、页数合规；M5S05 与 M5S06 已合并为同一 section | REVISE → M5S08 |
| M5S09 完成后 | 叙事连贯性四项链条检查通过、无重复表述、句式多样、衔接自然、术语/数值一致；`paper.tex` 已更新并复编译出最终 `paper.pdf` | REVISE → M5S09 |
| Gate G5 | Logic ≥7.0 AND Writing ≥7.0 AND Evidence ≥7.0 AND Novelty ≥7.0 AND Ethics ≥7.0 | BACKTRACK → 指定 M5 stage |
| Handoff 前 | 所有 M5 产出文件存在、paper.pdf 可打开 | 阻止完成 |

## Checkpoint 与用户交互

以下节点默认向用户发送进度更新（非阻塞，继续执行）：

1. **M5S01 完成后**: "写作前审计完成。核心贡献点：[N] 个，证据缺口：[M] 个，叙事缺口：[K] 个。"
2. **M5S02 完成后**: "论文大纲完成。目标 venue：[venue]，页数预算：[N] 页，计划图表：[M] 个。"
3. **M5S04 完成后**: "Methodology 完成。核心组件：[列表]。"
4. **M5S05 完成后**: "Experiments & Results 完成。主结果已交叉验证。"
5. **M5S06 完成后**: "Analysis & Discussion 完成。与 Experiments 一一对应，Limitations 已披露。"
6. **M5S03 完成后**: "Introduction & Related Work 完成。故事线基于已锁定的 Method/Exp/Analysis。"
7. **M5S07 完成后**: "Abstract & Conclusion 完成。数值一致性已验证。"
8. **M5S08 完成后**: "论文初稿编译完成。PDF 页数：[N]， orphan cite：[M] 个。"
9. **M5S09 完成后**: "全文润色完成。叙事连贯性检查通过，最终 PDF 已复编译。"
10. **Gate G5 完成后**: "Gate G5 通过（Logic: X/10, Writing: X/10, Evidence: X/10, Novelty: X/10, Ethics: X/10）。"
11. **M5 完成后**: "M5 论文写作完成。投稿包已生成。"

如果用户要求暂停或介入，在下一个 Checkpoint 停止并等待用户指令。

## 输出协议

遵循 AutoPaper2 的输出协议：

1. **Output Versioning**: 首次写入时带时间戳，然后复制到固定名
2. **Output Manifest**: 每个产出记录到项目根目录的 `MANIFEST.md`
3. **Output Language**: 默认中文（与用户一致），用户可覆盖；论文正文按 venue 要求

M5 核心产出清单：
- `knowledge/M5/M5S01_pre_write_audit.md`
- `knowledge/M5/M5S02_paper_outline.md`
- `knowledge/M5/M5S03_introduction_relatedwork.md`
- `knowledge/M5/M5S04_methodology.md`
- `knowledge/M5/M5S05_experiments_results.md`
- `knowledge/M5/M5S06_analysis_discussion.md`
- `knowledge/M5/M5S07_abstract_conclusion.md`
- `knowledge/M5/M5S08_final_compilation.md`
- `knowledge/M5/M5S09_full_polish.md`
- `artifacts/paper.tex`
- `artifacts/paper.pdf`
- `artifacts/refs.bib`
- `knowledge/reviews/G5_logic_review.md`
- `knowledge/reviews/G5_writing_review.md`
- `knowledge/reviews/G5_evidence_review.md`
- `knowledge/reviews/G5_novelty_review.md`
- `knowledge/reviews/G5_ethics_review.md`
- `knowledge/handoff_M5_completion.md`

补充规则：
- `paper.tex` 使用 venue 模板，保持模板文件只读
- `refs.bib` 由 Writing Agent 在 M5S08 整合生成
- 图表原始文件保存在 `experiments/artifacts/` 下，论文中引用相对路径
- 默认输出语言为中文（stage 文档），论文正文按 venue 要求

## Context Recovery

如果上下文被压缩或 session 中断，恢复流程：

1. 重新读取 `docs/AGENTS/writing/AGENT.md`
2. 读取 `state/pipeline_state.yaml` → 确认当前 stage
3. 读取 `state/decision_log.md` 和 `state/spiral_log.md`
4. 读取当前 stage 的 AGENT.md
5. 读取最近的产出文件，恢复上下文
6. 从当前 stage 继续执行，不跳过被标记为 stale 的 stage

**CLI 辅助命令**：
```bash
# 查看当前项目状态
python scripts/state_manager.py status

# 查看当前 stage 的自动执行计划
python scripts/state_manager.py auto-stage M5S01

# 自动运行当前模块
python scripts/state_manager.py auto-module M5
```

## Key Rules

- **M4 必须先完成**：M5 的入口条件是 M4 已完成。如果 M4 未完成，拒绝启动 M5。
- **Writing Agent 统一负责 M5S02-S09**：论文写作是一个连贯的思维过程，不拆分到不同 Agent（M5S01 除外，由 Analysis Agent 执行审计）。
- **风格蒸馏只做高层抽象**：M5S01/M5S02 可参考相近高水平论文的结构、篇幅、图表和排版规律，但禁止复制原文表达或独特设计。
- **Style & Layout Profile 必须贯穿后续写作**：M5S03-M5S09 必须读取 M5S02 的 Profile，并在与目标 venue 模板冲突时以 venue 模板为准。
- **Figure Style Profile 必须贯穿后续图生成**：架构图/机制图必须按 venue preset 与 M5S02 蒸馏出的图风格生成，避免统一黑白极简方框图。
- **Anti-Leakage Prompt 强制附加**：任何生成论文内容的 LLM 调用前必须附加 Anti-Leakage Instruction。
- **所有数值必须与原始数据一致**：M5S05 和 M5S07 的数值必须与 `experiments/results.tsv` 和 `experiments/analysis_results.tsv` 一致，不得四舍五入导致矛盾。
- **写作顺序遵循学术最佳实践**：M5S04（Method）→ M5S05（Exp）→ M5S06（Analysis）→ M5S03（Intro/RW）→ M5S07（Abstract/Conclusion）→ M5S08（Assembly/Compile）→ M5S09（Final Polish）。Introduction 在 Method/Experiments/Analysis 之后写，最终润色在完整 LaTeX/PDF 生成后执行。
- **Experiments 与 Analysis/Discussion 合并为同一 section**：M5S05 和 M5S06 在最终论文中属于同一 section（如 "4. Experiments, Results and Analysis"），M5S06 作为该 section 的子节存在。
- **M5S06 一一对应原则**：每条分析、每个消融、每个机制解释必须直接对应 M5S05 中的一个具体实验结果；禁止在 Analysis 中讨论未在 Experiments 中呈现的结果。
- **M5S09 叙事连贯性强制审阅**：润色阶段必须读取 `paper.tex` / `paper.pdf`，以读者视角验证 Intro-Method-Experiments-Analysis 的四项承诺兑现链，并完成全文术语/数值一致性最终检查和复编译。
- **论文正文必须引用上游文档**：Method/Exp 部分必须基于 M2/M3/M4 文档忠实改写，不得编造。
- **图表必须在正文中引用并解释**：每个 Figure/Table 至少在正文中被引用一次。
- **Orphan Cite Gate 必须通过**：M5S08 初次编译和 M5S09 复编译时都必须验证所有 `\cite{KEY}` 存在于 `refs.bib`。
- **LaTeX Sanity Check 必须通过**：编译无 fatal error、无未定义引用、页数合规。
- **Limitations 必须诚实**：M5S06 必须披露已知限制，不能敷衍。
- **Gate G5 必须五 Critic**：Logic + Writing + Evidence + Novelty + Ethics 全部通过才算 Gate 通过。
- **Handoff 文件必须生成**：M5 完成后必须产出 `knowledge/handoff_M5_completion.md`。
- **跨模型隔离必须遵守**：Writing Agent 与 Writing Critic 不得由同一模型实例执行（参见 `docs/AGENTS/critic/cross_model_protocol.md`）。
- **螺旋上限为 10**：M5 模块最多允许 10 次回溯，超过则 HALT，需人工介入。
- **失败时诚实报告**：如果某个 stage 无法通过（如 Gate HALT、螺旋超限），必须明确报告原因，不强行推进。
