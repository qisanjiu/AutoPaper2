# AutoPaper2 -- 全自动科研论文生成框架

> **版本**: 0.1.0  
> **核心理念**: 6 模块螺旋式推进，启发的记忆与迭代系统，三层 Critic 质量把关机制  
> **语言**: 中文主文档 / English docs see [README.md](README.md)

---

## 目录

1. [项目介绍](#项目介绍)
2. [架构总览](#架构总览)
3. [详细流程框架](#详细流程框架)
   - [M1 领域调研](#m1-领域调研-domain-survey)
   - [M2 方法设计](#m2-方法设计-method-design)
   - [M3 实验执行](#m3-实验执行-experiment)
   - [M4 深度分析](#m4-深度分析-deep-analysis)
   - [M5 写作与审稿](#m5-写作与审稿-writing--review)
   - [M6 投稿与修订](#m6-投稿与修订-submission--rebuttal)
4. [核心机制](#核心机制)
   - [Survey Memory 持久化记忆](#survey-memory-持久化记忆)
   - [Backtrack 回溯机制](#backtrack-回溯机制)
   - [Gate 门控评审](#gate-门控评审)
   - [Public Literature DB 公共文献库](#public-literature-db-公共文献库)
5. [使用指南](#使用指南)
   - [环境准备](#环境准备)
   - [项目创建与 Onboarding](#项目创建与-onboarding)
   - [环境探测与自动配置](#环境探测与自动配置)
   - [进入模块 / 推进项目](#进入模块--推进项目)
   - [自动运行](#自动运行)
   - [回溯与修订](#回溯与修订)
   - [人工审查介入](#人工审查介入)
   - [切换项目](#切换项目)
6. [Skill 速查表](#skill-速查表)
7. [项目目录结构](#项目目录结构)
8. [配置说明](#配置说明)
9. [开发者参考](#开发者参考)
10. [开发与测试](#开发与测试)
11. [许可证](#许可证)

---

## 项目介绍

AutoPaper2 是一个**端到端全自动科研论文生成框架**。它将完整的科研流程重构为 **6 个模块、33 个 Stage 和 6 个 Gate**，通过多 Agent 协作与三层 Critic 审查机制，自动完成从领域调研、方法设计、实验执行、深度分析到论文写作与投稿的全过程。

### 与 AutoPaper 的改进对比

| 特性 | AutoPaper | **AutoPaper2** |
|:---|:---|:---|
| 阶段划分 | 8 Phases x 37 Stages | **6 Modules x 33 Stages** |
| 调研记忆 | :x: 无 | :white_check_mark: **持久化 `survey_memory.yaml`** |
| 迭代搜索 | :x: 单次搜索 | :white_check_mark: **3-Round 搜索->验证->迭代循环** |
| 来源追踪 | :x: 内嵌 Markdown | :white_check_mark: **结构化 `M1_source_log.yaml`** |
| 覆盖率审查 | :x: 未检查 | :white_check_mark: **Gate G1 Coverage Critic** |
| 回溯机制 | :x: 简单重试 | :white_check_mark: **完整 Backtrack + Spiral Count** |
| 公共文献库 | :x: 无 | :white_check_mark: **SQLite + FTS 跨项目复用** |
| 投稿模块 | :x: 无 | :white_check_mark: **M6 外部审稿与修订循环** |

---

## 架构总览

```
+-------------------------------------------------------------------------+
|                        AutoPaper2 六模块流水线                           |
+---------+---------+---------+---------+---------+---------------------+
|   M1    |   M2    |   M3    |   M4    |   M5    |        M6           |
| 领域调研 | 方法设计 | 实验执行 | 深度分析 | 写作审稿 |     投稿修订         |
+---------+---------+---------+---------+---------+---------------------+
| M1S01   | M2S01   | M3S01   | M4S01   | M5S01   | M6S01 投稿审计       |
| M1S02   | M2S02   | M3S02   | M4S02   | M5S02   | M6S02 外部审稿提交    |
| M1S03   | M2S03   | M3S03   | M4S03   | M5S03   | M6S03 审稿解析       |
| M1S04   | M2S04   | M3S04   | M4S04   | M5S04   | M6S04 回溯策略       |
| M1S05   | M2S05   |   v     |   v     | M5S05   | M6S05 修订执行       |
|   v     | M2S06   |   G3    |   G4    | M5S06   | M6S06 修订验证       |
|   G1    |   v     |         |         | M5S07   |   v                 |
|         |   G2    |         |         | M5S08   |   G6                |
|         |         |         |         |   v     |                     |
|         |         |         |         |   G5    |                     |
+---------+---------+---------+---------+---------+---------------------+
```

**核心设计原则**：
- **对话驱动**：用户通过自然语言与 Agent 对话，Skill 自动处理流程编排
- **Conductor 只编排，不执行**：主 Agent 负责项目创建、模块路由、Stage 推进、回溯调度、Gate 处理，**绝不直接执行 Stage 内容或审查工作**
- **Stage 执行委托 Subagent**：每个 Stage 由对应角色的 Subagent 执行（Survey / Method / Experiment / Analysis / Writing 等）
- **独立审查层**：Stage-level review + Gate Critic + Human Review 三层把关
- **可追溯的回溯**：所有回溯记录持久化到 `pipeline_state.yaml`，支持 Spiral Count 限制

---

## 详细流程框架

### M1 领域调研 (Domain Survey)

> **目标**: 全面调研研究领域现状，识别研究空白 (Gap)，产出结构化文献综述  
> **Agent**: Survey Agent + Ideation Agent  
> **Gate**: G1 (Logic + Novelty + Coverage + Survey Review)

| Stage | 名称 | 说明 |
|:---|:---|:---|
| **M1S01** | Topic Scoping | 明确研究主题、关键词、检索策略、预期贡献类型 |
| **M1S02** | Literature Deep Dive | 执行 **3-Round 迭代搜索**：Round 1 广度扫描 -> Round 2 深度验证 -> Round 3 盲区补充。每轮需独立 Reviewer verdict = PASS 方可进入下一轮 |
| **M1S03** | Research Question | 将识别的 Gap 转化为具体、可检验的研究问题 |
| **M1S04** | Hypothesis Generation | 生成研究假设，明确自变量/因变量/预期效应 |
| **M1S05** | Novelty & Feasibility | 论证新颖性与可行性，完成 M1 产出整合 |

**关键输出**:
- `knowledge/M1/M1S01_topic_scoping.md`
- `knowledge/M1/M1S02_literature_deepdive.md`
- `knowledge/M1/M1_source_log.yaml` -- 结构化来源日志
- `state/survey_memory.yaml` -- 持久化调研记忆（含 search_batches, round_reviews, findings）
- `knowledge/M1/M1S03_research_question.md`
- `knowledge/M1/M1S04_hypothesis_generation.md`
- `knowledge/M1/M1S05_novelty_feasibility.md`
- `knowledge/handoff_M1_M2.md`

---

### M2 方法设计 (Method Design)

> **目标**: 基于 M1 识别的 Gap，通过跨领域搜索、思想迁移和方法综合，设计严谨、可复现、能验证假设的研究方法  
> **Agent**: Method Agent  
> **Gate**: G2 (Logic + Method + Novelty)

| Stage | 名称 | 说明 |
|:---|:---|:---|
| **M2S01** | Cross-Domain Search | 跨领域文献搜索，寻找可迁移的技术思想 |
| **M2S02** | Method Inspiration | 多论文灵感整合与适配，形成初步方案 |
| **M2S03** | Method Architecture | 方法架构设计：模块划分、数据流、接口定义 |
| **M2S04** | Algorithm & Theory | 算法细节与理论分析：收敛性、复杂度、边界条件 |
| **M2S05** | Experiment Setup | 实验设置设计：数据集、评价指标、超参数、复现环境 |
| **M2S06** | Full Experiment Plan | 整合完整实验计划，输出 M2->M3 交接文档 |

**Stage Review 机制**:
- M2S01 -> `m2_search_quality` 审查
- M2S02 -> `m2_migration` 审查（承上启下，审查跨域映射合理性）
- M2S03 -> `m2_design_review` 审查
- M2S04 -> `m2_design_review` 审查

**关键输出**:
- `knowledge/M2/M2S01_cross_domain_search.md`
- `knowledge/M2/M2S02_method_inspiration.md`
- `knowledge/M2/M2S03_method_architecture.md`
- `knowledge/M2/M2S04_algorithm_theory.md`
- `knowledge/M2/M2S05_experiment_setup.md`
- `knowledge/M2/M2S06_full_experiment_plan.md`
- `knowledge/M2/M2_source_log.yaml`
- `knowledge/handoff_M2_M3.md`

---

### M3 实验执行 (Experiment)

> **目标**: 正确、高效地实现 M2 设计的方法，运行实验迭代循环，产生可信的经验证据  
> **Agent**: Experiment Agent  
> **Gate**: G3 (Method + Evidence)

| Stage | 名称 | 说明 |
|:---|:---|:---|
| **M3S01** | Implementation | 代码实现与环境搭建：依赖锁定、**数据集获取（禁止仿真数据替代）**、数据管道 |
| **M3S02** | Baseline Lock | 基线方法复现与锁定：**含 Checkpoint（预训练权重）搜索与获取**、metric contract 建立、smoke test 通过 |
| **M3S03** | Main Experiment | 主实验执行：完整训练/评估流程、多次随机种子、结果记录 |
| **M3S04** | Result Validation | 结果验证与证据打包：统计显著性检验、负面结果记录、决策（KEEP / FIX / BACKTRACK）|

**Stage Review 机制**:
- M3S01 -> `m3_dataset_env_review` 审查
- M3S02 -> `m3_baseline_result_review` 审查
- M3S03 -> `m3_main_result_review` 审查

**M3S04 决策强制机制**:
- 若 M3S04 输出决策为 `FIX` 或 `BACKTRACK`，则 **必须** 包含完整的 `回溯修改方向` 和修复字段，否则 `advance` 会被阻断
- 决策为 `KEEP` 方可正常推进至 M4

**M3 关键铁律**:
- **数据集获取铁律（M3S01）**：真实数据是唯一合法输入，**绝对禁止**用仿真/合成/随机数据替代。大数据集（>10GB）同样必须尝试下载或传输；无法自动获取时，必须生成阻塞报告等待用户入库。
- **Checkpoint 获取铁律（M3S02）**：Baseline 若依赖预训练权重，必须主动搜索并获取 checkpoint（GitHub Releases、README、HuggingFace Hub 等），禁止跳过或用随机初始化替代。

**关键输出**:
- `knowledge/M3/M3S01_implementation.md`
- `knowledge/M3/M3S02_baseline_lock.md`
- `knowledge/M3/M3S03_main_experiment.md`
- `knowledge/M3/M3S04_result_validation.md`
- `knowledge/handoff_M3_M4.md`

---

### M4 深度分析 (Deep Analysis)

> **目标**: 从实验结果中提取可靠结论，识别模式，通过消融实验、机制分析、鲁棒性检验等深化洞察  
> **Agent**: Analysis Agent + Experiment Agent (M4S03)  
> **Gate**: G4 (Logic + Evidence + Novelty)

| Stage | 名称 | 说明 |
|:---|:---|:---|
| **M4S01** | Other Findings | 实验后审计：数据质量审计、Claim 初筛、负面结果整合 |
| **M4S02** | Analysis Experiment Design | 深度分析实验设计：消融实验、机制可视化、鲁棒性检验、Slice Evidence Contract |
| **M4S03** | Analysis Experiment | 深度分析实验执行 |
| **M4S04** | Analysis Results | 分析结果整合与证据打包 |

**Stage Review 机制**:
- M4S01 -> `m4_findings_audit` 审查
- M4S02 -> `m4_analysis_design_review` 审查
- M4S03 -> `m4_analysis_execution_review` 审查

**关键输出**:
- `knowledge/M4/M4S01_other_findings.md`
- `knowledge/M4/M4S02_analysis_experiment_design.md`
- `knowledge/M4/M4S03_analysis_experiment.md`
- `knowledge/M4/M4S04_analysis_results.md`
- `knowledge/handoff_M4_M5.md`

---

### M5 写作与审稿 (Writing & Review)

> **目标**: 将研究成果转化为结构清晰、论证严谨、符合 venue 规范的学术论文  
> **Agent**: Analysis Agent (M5S01) + Writing Agent (M5S02-M5S08) + Build Verifier (M5S08)  
> **Gate**: G5 (Logic + Writing + Evidence + Novelty + Ethics)

| Stage | 名称 | 说明 |
|:---|:---|:---|
| **M5S01** | Pre-Write Audit | 写作前审计：贡献梳理、证据链完整性检查、术语统一 |
| **M5S02** | Paper Outline | 论文大纲：plotting plan、术语表、section budget |
| **M5S03** | Introduction & Related Work | 引言与相关工作 |
| **M5S04** | Methodology | 方法论章节 + 方法图 |
| **M5S05** | Experiments & Results | 实验与结果章节 |
| **M5S06** | Analysis & Discussion | 分析与讨论章节 |
| **M5S07** | Abstract & Conclusion | 摘要与结论 |
| **M5S08** | Final Compilation | 全文组装、LaTeX 编译、PDF 生成 |

**Stage Review 机制**:
- M5S01 -> `m5_prewrite_review`
- M5S02 -> `m5_outline_style_review`
- M5S03 -> `m5_intro_relatedwork_review`
- M5S04 -> `m5_method_figure_review`
- M5S05 -> `m5_experiments_results_review`
- M5S06 -> `m5_analysis_discussion_review`
- M5S07 -> `m5_abstract_conclusion_review`
- M5S08 -> `build_verifier` + `m5_final_compilation_review`

**关键输出**:
- `knowledge/M5/M5S01_pre_write_audit.md` ~ `M5S08_final_compilation.md`
- `artifacts/paper.tex`
- `artifacts/paper.pdf`
- `knowledge/handoff_M5_completion.md`

---

### M6 投稿与修订 (Submission & Rebuttal)

> **目标**: 完成投稿前审计、外部审稿提交、审稿意见解析、回溯规划、修订执行与验证  
> **Agent**: Submission Agent (M6S01-M6S02) + Rebuttal Agent (M6S03-M6S06)  
> **Gate**: G6 (Logic + Evidence + Writing + Resolution)

| Stage | 名称 | 说明 |
|:---|:---|:---|
| **M6S01** | Submission Audit | 投稿前审计：投稿包完整性、venue 格式合规性 |
| **M6S02** | External Review Submission | 外部审稿提交（如 paperreview.ai）|
| **M6S03** | Review Parsing | 审稿意见接收与解析 + Review Matrix 原子化 |
| **M6S04** | Rebuttal Strategy | 回溯规划与反驳策略 + 可执行 Action Plan |
| **M6S05** | Revision Execution | 修订执行 |
| **M6S06** | Revision Validation | 修订验证与完成判定 |

**Stage Review 机制**:
- M6S01 -> `m6_submission_audit`
- M6S02 -> `m6_external_submission_review`
- M6S03 -> `m6_review_parsing_review`
- M6S04 -> `m6_rebuttal_strategy_review`
- M6S05 -> `m6_revision_execution_review`
- M6S06 -> `m6_revision_validation_review`

**关键输出**:
- `knowledge/M6/M6S01_submission_audit.md` ~ `M6S06_revision_validation.md`
- `knowledge/M6/M6S03_review_matrix.md`
- `knowledge/M6/M6S04_action_plan.md`
- `knowledge/handoff_M6_completion.md`

---

## 核心机制

### Survey Memory 持久化记忆

受 deepResearch 启发，AutoPaper2 在 M1 阶段引入了 **SurveyMemory** 持久化系统：

```yaml
# state/survey_memory.yaml
topic: "Semantic Communication for Image Transmission"
status: completed
search_batches:
  - batch_id: 1
    round: 1
    status: passed
    queries: ["semantic communication overview", "deep JSCC image"]
    sources_found: 12
round_reviews:
  - round: 1
    verdict: PASS
    score: 0.85
findings:
  key_claims: [...]
  gaps:
    - id: "gap_1"
      description: "Existing methods lack adaptive modulation under varying channels"
      gap_type: enhancement
      target_component: "modulation module"
      baseline_framework: "DeepJSCC"
      bottleneck_description: "Fixed code length cannot adapt to SNR variations"
  contradictions: [...]
source_registry:
  smith2023deepjscc:
    title: "Deep Joint Source-Channel Coding"
    credibility_score: 5
    verification_status: confirmed
    ...
```

**Gap 类型系统**:
- **VG (Vacancy Gap)**: 空白型 -- 某子领域完全未被探索
- **EG (Enhancement Gap)**: 改进型 -- 现有方法的某组件存在瓶颈，需改进
- **ValG (Validation Gap)**: 验证型 -- 某结论仅在特定设定下成立，需更广泛的验证

### Backtrack 回溯机制

当 Stage Review 或 Gate Critic 给出非 PASS verdict（REVISE / REWORK / BACKTRACK / FIX）时，Conductor 触发 Backtrack：

**用户触发回溯的方式**（通过对话调用 `AutoPaper2_project_backtrack` Skill）：

```text
回溯到 M2S03，方法架构与基线不兼容，需要重新设计注意力模块。
```

```text
M4S02 的消融实验设计有问题，回到 M4S02 重新设计。
```

```text
重新执行 M3S02，baseline 的 metric contract 不公平。
```

**Backtrack 副作用**:
1. 标记 `to_stage` 与 `from_stage` 之间的所有 downstream Stage 为 **stale**
2. 重置目标 Module 状态为 `reopened`
3. 记录到 `backtrack_log`，递增 `spiral_count`
4. 若同一 Module 的 `spiral_count >= 10`，触发 **HALT**（需人工介入）。Spiral Count 上限为 10，给予实验充分的迭代空间

**Rebuild Mode**:
- `full_regenerate`（默认）: Subagent 必须将旧下游文件视为历史审计，不允许复制粘贴
- `incremental_replay`: Subagent 可参考旧文件减少冗余，但所有保留内容必须重新验证

### Gate 门控评审

每个 Module 最后一个 Stage 是 **Gate Stage**，需通过 Critic Team 的聚合评审：

| Gate | 所在 Stage | Critics |
|:---|:---|:---|
| G1 | M1S05 | Logic, Novelty, Coverage, Survey Review |
| G2 | M2S06 | Logic, Method, Novelty |
| G3 | M3S04 | Method, Evidence |
| G4 | M4S04 | Logic, Evidence, Novelty |
| G5 | M5S08 | Logic, Writing, Evidence, Novelty, Ethics |
| G6 | M6S06 | Logic, Evidence, Writing, Resolution |

**Gate Verdict 类型**:
- **PASS**: 全部通过，进入下一 Module
- **REVISE**: 小修，回溯至指定 Stage
- **FIX**: 中修，回溯至 Module 起始或指定 Stage
- **BACKTRACK**: 大修，回溯至 Module 起始
- **HALT**: 终止，需人工介入

Gate 评审产出 `knowledge/reviews/{G}_aggregate.md`，`advance` 时作为 Gate Stage 的输出文件。

### Public Literature DB 公共文献库

AutoPaper2 内置了框架级的 **SQLite + FTS5** 公共文献数据库，支持跨项目文献复用。Agent 在执行搜索和文献管理时会自动使用公共文献库：

- 自动去重（基于 DOI / arXiv ID / 标题相似度）
- 合并策略（可信度加权、局限性去重、标题取长）
- 查询缓存（避免重复搜索）
- 自动标签（基于标题/摘要的关键词匹配）
- 全文检索（FTS5）

用户可以通过对话查询公共文献库状态，如：

```text
查看公共文献库的状态
```

```text
搜索公共文献库中的 "transformer time series"
```

用户也可以通过对话手动导入文献或数据集，触发 `AutoPaper2_manual_import` Skill：

```text
导入文献到公共库
```

```text
注册新的数据集 CIFAR-100
```

```text
手动添加论文 "Attention Is All You Need" 到公共文献库
```

详见 `skills/AutoPaper2_manual_import/SKILL.md`。

---

## 使用指南

AutoPaper2 的运行方式是**对话驱动**：你在与 Agent 的对话界面中用自然语言发出指令，由 Skill 自动处理项目创建、模块路由、Stage 推进、回溯调度等全部流程。你不需要手动运行 Python 脚本。

### 环境准备

```bash
# 克隆项目后安装依赖
pip install -e ".[dev]"

# 或仅安装运行时依赖
pip install pyyaml pydantic requests
```

### 项目创建与 Onboarding

使用自然语言直接告诉 Agent 你的研究主题：

```text
开始一个新项目，主题是 "Semantic Communication with Reinforcement Learning for Adaptive Image Transmission"，简称 SemCom-Image-RL。
```

```text
开始调研 "图像语义通信中的自适应传输"，关键词包括 DeepJSCC、semantic communication、reinforcement learning。
```

如果项目是基于某篇论文继续做，明确使用 "基于 / 在此基础上拓展 / foundation"：

```text
开始一个新项目：主题是 "自适应图像语义通信"。
我希望从论文 "Deep Joint Source-Channel Coding for Wireless Image Transmission" 的基础上进一步拓展。
```

如果某篇论文只是重点参考，而不是继承对象，明确使用 "重点参考 / reference"：

```text
开始一个新项目：主题是 "Transformer time-series forecasting"。
重点参考论文是 "Informer: Beyond Efficient Transformer for Long Sequence Time-Series Forecasting"。
```

你也可以同时给 foundation 和 reference，或者给 PDF、URL、arXiv、DOI、GitHub：

```text
开始一个新项目，主题是 "多模态检索中的高效重排序"。
foundation: /home/me/papers/base_method.pdf
reference: https://arxiv.org/abs/2401.00000
code reference: https://github.com/example/repo
```

Skill 会创建项目，并把这些入口信息写入 `state/research_brief.yaml`。后续 M1/M2/M5 会把 foundation 论文作为方法继承线，把 reference 论文作为近邻比较和写作参照。

**项目创建后会自动触发 Onboarding（入项配置）**。框架自动探测当前环境（GPU、Python、CUDA 等）并填充 `config/execution_env.yaml`，同时生成 `state/onboarding_checklist.md`。此时项目状态为 `onboarding_pending`，**必须完成配置确认后才能进入 M1**。

Agent 会向你展示 Onboarding Checklist：

```markdown
# Project Onboarding Checklist

## 自动探测结果（请确认）
- 执行模式: ssh / local
- Python 版本: 3.x
- CUDA 版本: 12.x
- GPU: NVIDIA RTX xxx

## 需手动填写
1. SSH 配置（仅当 mode=ssh 时必填）: config/execution_env.yaml
2. 作者信息: config/author_info.yaml
3. 投稿目标确认
```

**执行模式说明**：
- **`local` 模式**：实验在本地运行，SSH 配置**无需填写**
- **`ssh` 模式**：实验在远程服务器运行，必须填写 `ssh.host`、`ssh.user` 等

补全配置后回复 **"已填写"**，Agent 验证通过后解除阻塞，允许进入 M1S01。

```bash
# 也可以通过 CLI 标记 onboarding 完成
python scripts/state_manager.py onboarding-done projects/XXX
```

### 环境探测与自动配置

当项目迁移到新机器或环境发生变化时，可以触发环境探测：

```text
探测环境
更新执行环境配置
重新探测环境
```

Agent 会自动检测并更新以下配置：

| 探测项 | 自动填写 | 需手动确认 |
|--------|---------|-----------|
| Python / CUDA / GPU | ✅ | 确认即可 |
| 环境管理工具（conda/uv/venv） | ✅ | 确认即可 |
| PyTorch / TensorFlow 版本 | ✅ | 确认即可 |
| SSH 主机/用户/密钥 | ❌ | 必须手动填写 |
| 作者信息 | ❌ | 必须手动填写 |

```bash
# 手动探测并更新项目配置
python scripts/env_probe.py --project projects/XXX

# 仅查看不写入
python scripts/env_probe.py --project projects/XXX --dry-run
```

### 进入模块 / 推进项目

Onboarding 完成后，用自然语言告诉 Agent 你想进入哪个模块：

```text
进入 M2
```

```text
开始实验
```

```text
进入 M5，开始写论文
```

如果你不确定当前进度，可以问：

```text
查看项目状态
```

```text
现在到哪个阶段了？
```

### 自动运行

如果你想让 Agent 自动推进当前模块或整个项目：

```text
自动运行
```

```text
从头到尾自动执行
```

```text
继续自动运行
```

```text
帮我自动推进剩余部分
```

### 回溯与修订

当你发现某个 Stage 的产出有问题，需要回退或重做时：

```text
回溯到 M2S03，方法架构与基线不兼容，需要重新设计。
```

```text
重新执行 M3S02，baseline 的结果有问题。
```

```text
回退到 M4S02，消融实验设计需要重新设计。
```

```text
M5S04 的方法描述不够清晰，修订一下。
```

### 人工审查介入

如果你想对某个 Stage 的产出提出意见：

```text
M2S03 的方法架构缺少与 transformer-based baseline 的对比，需要补充。
```

Agent 会自动触发回溯机制，并委托对应的 Subagent 重新执行。

### 切换项目

如果你有多个项目：

```text
切换到 SemCom-Image 项目
```

```text
在 projects/SemCom-Image-RL-20260512-135033 中执行 M3
```

---

## Skill 速查表

AutoPaper2 通过以下 Skill 响应你的指令。你不需要记忆它们的名字，只需用自然语言表达意图即可。

### 模块级执行 Skill（M1-M6）

| Skill | 触发语示例 | 作用 |
|:---|:---|:---|
| `AutoPaper2_m1_survey` | "开始新项目"、"调研 XXX"、"进入 M1"、"领域调研" | 创建新项目，执行 M1 完整流程 |
| `AutoPaper2_m2_method_design` | "进入 M2"、"方法设计"、"设计实验"、"设计方法" | 执行 M2 方法设计完整流程 |
| `AutoPaper2_m3_experiment` | "进入 M3"、"开始实验"、"运行实验"、"实验执行" | 执行 M3 实验执行完整流程 |
| `AutoPaper2_m4_deep_analysis` | "进入 M4"、"深度分析"、"分析实验"、"消融实验" | 执行 M4 深度分析完整流程 |
| `AutoPaper2_m5_writing` | "进入 M5"、"开始写作"、"写论文"、"论文写作" | 执行 M5 论文写作完整流程 |
| `AutoPaper2_m6_submission_review` | "进入 M6"、"最终审稿"、"外部审稿"、"投稿审稿" | 执行 M6 投稿与修订完整流程 |

### 项目级编排 Skill

| Skill | 触发语示例 | 作用 |
|:---|:---|:---|
| `AutoPaper2_project_router` | "运行 [项目] 的 [模块]"、"切换到 [项目]"、"继续 [项目]" | 项目定位、状态诊断、模块路由 |
| `AutoPaper2_project_auto_run` | "自动运行"、"从头到尾"、"全自动执行"、"继续自动运行" | 端到端自动编排执行 |
| `AutoPaper2_project_backtrack` | "回溯到 [stage]"、"重新执行 [stage]"、"修订 [stage]"、"回退到 [stage]" | 回溯到指定 stage 并重新执行 |
| `AutoPaper2_project_onboarding` | "检查项目配置"、"补全项目信息"、"onboarding" | 项目创建后的强制配置检查点 |

### 环境与资源管理 Skill

| Skill | 触发语示例 | 作用 |
|:---|:---|:---|
| `AutoPaper2_env_probe` | "探测环境"、"检查环境"、"配置环境"、"更新执行环境" | 自动探测硬件/软件环境并填充 execution_env.yaml |
| `AutoPaper2_manual_import` | "导入文献"、"导入数据集"、"手动添加论文"、"注册数据集"、"添加数据集" | 手动将外部文献导入公共文献库，或将数据集注册到公共数据集缓存 |

### 使用原则

1. **用自然语言，不用记命令**：Agent 会根据你的表述自动匹配最合适的 Skill
2. **模块有依赖关系**：M2 需要 M1 完成，M3 需要 M2 完成，以此类推。Agent 会自动检查前置依赖，未满足时会提示你先完成前置模块
3. **每个模块完成后默认暂停**：Agent 会报告进度并等待你的确认，除非你明确说 "继续自动运行"
4. **上下文压缩后自动恢复**：如果对话中断或上下文被压缩，Agent 会读取 `state/pipeline_state.yaml` 自动恢复到当前 stage
5. **Onboarding 是强制前置**：项目创建后必须完成 onboarding 才能进入 M1；环境变化时可重新触发 `AutoPaper2_env_probe`

---

## 项目目录结构

```
AutoPaper2/
├── spiral/                      # 核心 Python 包
│   ├── __init__.py
│   ├── conductor.py             # 流程编排核心（Conductor）
│   ├── state.py                 # PipelineState 状态管理
│   ├── project.py               # ProjectManager 项目生命周期
│   ├── survey_memory.py         # SurveyMemory 调研记忆系统
│   └── public_db/               # 公共文献数据库
│       ├── config.py
│       ├── manager.py
│       ├── models.py
│       ├── db.py
│       ├── identifier.py
│       ├── importer.py
│       ├── merge.py
│       ├── query_cache.py
│       └── tag_engine.py
├── scripts/
│   ├── state_manager.py         # CLI 入口（Skill 内部调用）
│   ├── conductor_helper.py      # 跨 Stage 输入解析
│   ├── test_health_check.py     # 测试健康检查
│   └── agent_consistency_check.py  # Agent 一致性检查
├── utils/
│   ├── file_guard.py            # 命名与位置校验
│   ├── stage_gate.py            # Stage 质量检查
│   └── source_log_validator.py  # Source Log 校验
├── docs/
│   ├── AGENTS/                  # Agent 身份定义
│   │   ├── survey/AGENT.md
│   │   ├── method/AGENT.md
│   │   ├── experiment/AGENT.md
│   │   ├── analysis/AGENT.md
│   │   ├── writing/AGENT.md
│   │   ├── submission/AGENT.md
│   │   ├── rebuttal/AGENT.md
│   │   ├── ideation/AGENT.md
│   │   ├── conductor/AGENT.md
│   │   ├── build_verifier/AGENT.md
│   │   └── critic/              # Critic Agent 定义
│   │       ├── logic/AGENT.md
│   │       ├── method/AGENT.md
│   │       ├── novelty/AGENT.md
│   │       ├── coverage/AGENT.md
│   │       ├── writing/AGENT.md
│   │       ├── ethics/AGENT.md
│   │       ├── evidence/AGENT.md
│   │       ├── g6_resolution/AGENT.md
│   │       ├── source_log_validator/AGENT.md
│   │       ├── m2_search_quality/AGENT.md
│   │       ├── m2_migration/AGENT.md
│   │       ├── m2_design_review/AGENT.md
│   │       ├── m3_dataset_env_review/AGENT.md
│   │       ├── m3_baseline_result_review/AGENT.md
│   │       ├── m3_main_result_review/AGENT.md
│   │       ├── m4_findings_audit/AGENT.md
│   │       ├── m4_analysis_design_review/AGENT.md
│   │       ├── m4_analysis_execution_review/AGENT.md
│   │       ├── m5_stage_review/AGENT.md
│   │       └── m6_stage_review/AGENT.md
│   └── design/                  # 设计文档
│       ├── M2_MODULE_DESIGN.md
│       ├── M3_MODULE_DESIGN.md
│       └── public_literature_db_design.md
├── config/
│   ├── venue_registry.yaml      # 投稿 venue 配置
│   ├── public_db.yaml           # 公共数据库配置
│   ├── execution_env.yaml       # 执行环境配置
│   ├── figure_style_profiles.yaml
│   └── author_info.yaml
├── templates/
│   ├── stage/                   # Stage Markdown 模板（33个）
│   │   ├── M1S01_template.md
│   │   ├── M1S02_template.md
│   │   └── ...
│   └── venue/                   # Venue LaTeX 模板
│       ├── arxiv/
│       ├── neurips/
│       ├── icml/
│       └── ...
├── skills/                      # 执行 Skill（M1-M6 + 项目级）
│   ├── AutoPaper2_m1_survey/SKILL.md
│   ├── AutoPaper2_m2_method_design/SKILL.md
│   ├── AutoPaper2_m3_experiment/SKILL.md
│   ├── AutoPaper2_m4_deep_analysis/SKILL.md
│   ├── AutoPaper2_m5_writing/SKILL.md
│   ├── AutoPaper2_m6_submission_review/SKILL.md
│   ├── AutoPaper2_project_router/SKILL.md
│   ├── AutoPaper2_project_auto_run/SKILL.md
│   └── AutoPaper2_project_backtrack/SKILL.md
├── projects/                    # 所有研究项目
│   └── {name}-{YYYYMMDD-HHMMSS}/
│       ├── state/
│       │   ├── pipeline_state.yaml
│       │   ├── survey_memory.yaml
│       │   ├── decision_log.md
│       │   └── spiral_log.md
│       ├── knowledge/
│       │   ├── M1/ ~ M6/
│       │   ├── reviews/
│       │   └── handoff_M*.md
│       ├── drafts/
│       │   └── M1S01/ ~ M6S06/
│       ├── artifacts/
│       │   ├── paper.tex
│       │   └── paper.pdf
│       ├── experiments/
│       └── config/
├── tests/                       # 测试套件
│   ├── test_public_db/
│   ├── test_m1_integration.py
│   ├── test_m4_integration.py
│   ├── test_m6_integration.py
│   ├── test_m1_e2e.py
│   └── test_m1_integration.py
├── pyproject.toml
├── README.md
├── README_CN.md                 # 本文档
└── AGENTS.md                    # Agent 全局上下文
```

---

## 配置说明

### 环境变量

| 变量 | 用途 |
|:---|:---|
| `SPIRAL_FRAMEWORK_ROOT` | 覆盖框架根目录检测 |
| `SPIRAL_PROJECTS_ROOT` | 覆盖项目根目录位置 |

### Venue 注册表

编辑 `config/venue_registry.yaml` 可添加新的投稿 venue：

```yaml
venues:
  my_venue:
    name: "My Conference"
    full_name: "Annual Meeting of ..."
    page_limit: 8
    page_limit_note: "8 pages + references"
    format: "conference"
    style_package: "my_style"
    template_dir: "my_venue"
```

框架预置了以下 venue 模板：

| Venue | 页数限制 | 类型 |
|:---|:---|:---|
| arxiv | 无限制 | 预印本 |
| NeurIPS | 9页 + 参考文献 + 附录 | 会议 |
| ICML | 9页 + 参考文献 + 附录 | 会议 |
| ICLR | 9页 + 参考文献 + 附录 | 会议 |
| ACL | 8页 + 参考文献 + 附录 | 会议 |
| CVPR | 8页 + 参考文献 + 附录 | 会议 |
| IEEE Trans | 10-14页 | 期刊 |

对应在 `templates/venue/my_venue/` 下放置 `.sty`、`.cls`、`.bst`、`.tex` 模板文件。

### 公共数据库配置

编辑 `config/public_db.yaml` 可调整公共文献库行为：

```yaml
enabled: true
db_path: "data/public_literature_db/public_literature.db"
query_cache_ttl_days: 7
min_hit_threshold: 10
```

---

## 开发者参考

> 本节内容面向框架开发者和需要调试的进阶用户。普通用户无需关注。

### 底层 CLI 命令

`scripts/state_manager.py` 是 Skill 内部调用的状态管理工具，普通用户不需要直接使用。以下是开发者调试时可用的命令：

#### 项目操作

```bash
# 创建新项目
python scripts/state_manager.py create \
  "Semantic Communication with Reinforcement Learning for Adaptive Image Transmission" \
  "SemCom-Image-RL"

# 查看当前 Stage 和状态
python scripts/state_manager.py status --project projects/SemCom-Image-RL-20260512-135033

# 查看各 Module 完成状态
python scripts/state_manager.py module-status --project projects/SemCom-Image-RL-20260512-135033

# 设置当前项目（后续命令可省略 --project）
python scripts/state_manager.py use projects/SemCom-Image-RL-20260512-135033

# 标记 onboarding 完成
python scripts/state_manager.py onboarding-done projects/SemCom-Image-RL-20260512-135033
```

#### 环境探测

```bash
# 探测当前环境并更新项目配置
python scripts/env_probe.py --project projects/SemCom-Image-RL-20260512-135033

# 仅查看探测结果，不写入
python scripts/env_probe.py --project projects/SemCom-Image-RL-20260512-135033 --dry-run

# 输出原始探测报告
python scripts/env_probe.py --output /tmp/env_report.yaml
```

#### Stage 推进与回溯（Skill 内部调用）

```bash
# 推进 Stage（由 Skill 自动调用，用户不需要手动执行）
python scripts/state_manager.py advance M1S01 survey \
  knowledge/M1/M1S01_topic_scoping.md

# Gate Stage 推进（由 Skill 自动调用）
python scripts/state_manager.py advance M1S05 ideation \
  knowledge/reviews/G1_aggregate.md

# 执行回溯（由 Skill 自动调用）
python scripts/state_manager.py backtrack M2S06 M2S03 \
  "Baseline mismatch: selected CNN baseline cannot handle variable input size" \
  "Switch to transformer-based baseline and redesign encoder"
```

#### 公共文献库调试

```bash
# 查看数据库状态
python scripts/state_manager.py public-db status

# 搜索文献
python scripts/state_manager.py public-db search "transformer time series"

# 导入项目来源日志到公共库
python scripts/state_manager.py public-db import-project projects/YourProject

# 查看统计
python scripts/state_manager.py public-db stats
```

#### 数据集管理调试

```bash
# 查看已注册的数据集
cat data/datasets/.dataset_registry.yaml

# 校验数据集注册表语法
python -c "import yaml; yaml.safe_load(open('data/datasets/.dataset_registry.yaml'))"

# 手动校验数据集 checksum（示例）
cd data/datasets/cifar-10
md5sum cifar-10-python.tar.gz | grep "c58f30108f718f92721af3b95e74349a"
```

### Python API 参考

框架核心类（供 Skill / Agent 开发参考）：

```python
from spiral.conductor import Conductor
from spiral.state import PipelineState
from spiral.survey_memory import SurveyMemoryManager
from pathlib import Path

proj = Path("projects/XXX")

# Conductor: 流程编排
conductor = Conductor(proj)
result = conductor.backtrack(
    from_stage="M4S02",
    to_stage="M2S03",
    reason="M4S02 的 claim-carrying slice 缺乏 literature basis",
    direction="重新设计消融实验，补充文献依据"
)

# PipelineState: 状态管理
state = PipelineState(proj)
state.record_completion("M1S01", "survey", Path("knowledge/M1/M1S01_topic_scoping.md"))
state.set_stage("M1S02", "in_progress")

# SurveyMemory: 调研记忆
survey_mgr = SurveyMemoryManager(proj)
memory = survey_mgr.load()
memory.add_batch(["query1", "query2"], round_num=1)
survey_mgr.save(memory)
```

---

## 开发与测试

### 运行测试

```bash
# 运行全部测试（114+ tests）
python -m unittest discover -s tests -v

# 运行公共数据库测试
python -m unittest tests.test_public_db.test_core -v

# 运行 M1 端到端测试
python -m unittest tests.test_m1_e2e -v

# 测试健康检查
python scripts/test_health_check.py

# Agent 一致性检查
python scripts/agent_consistency_check.py
```

### 代码质量

```bash
# 格式化
ruff format spiral/ scripts/ utils/ tests/

# Lint
ruff check spiral/ scripts/ utils/ tests/

# 类型检查
mypy spiral/ scripts/ utils/
```

---

## 许可证

MIT License
