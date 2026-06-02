# AutoPaper2

> **一个以状态机和多 Agent 分工为核心的自主研究框架，用于把研究主题推进到调研、方法设计、实验、论文写作、投稿、审稿解析、反驳与修改。**

AutoPaper2 将学术研究流程视为一条有门禁的软件流水线。每个项目都会经过六个模块（M1-M6），每个模块由明确 Stage、持久化状态、子 Agent prompt、审查分发包和 Gate Critic 组成。框架的核心规则是严格的**编排者-执行者分离**：主 Agent / Conductor 只负责状态编排、分发、审查路由和回溯；Stage 内容执行和审查必须委托给 `docs/AGENTS/` 下对应的子 Agent。

---

## 目录

- [项目概览](#项目概览)
- [仓库结构](#仓库结构)
- [系统架构](#系统架构)
- [六大模块](#六大模块)
- [Gate 与审查体系](#gate-与审查体系)
- [分发工作流](#分发工作流)
- [螺旋回溯机制](#螺旋回溯机制)
- [快速开始](#快速开始)
- [项目入口与 Anchors](#项目入口与-anchors)
- [项目目录结构](#项目目录结构)
- [配置说明](#配置说明)
- [Skills 与跨 CLI 兼容](#skills-与跨-cli-兼容)
- [质量检查](#质量检查)
- [许可证](#许可证)

---

## 项目概览

AutoPaper2 是一个结构化、Agent 辅助的论文生产框架。它不是把完整研究过程塞进一个长 prompt，而是使用以下机制：

1. **持久化项目状态** - 每个项目都有 `state/pipeline_state.yaml`、决策日志、螺旋日志、分发包和 onboarding 状态。
2. **专业化 Agent** - 调研、创意、方法、实验、分析、写作、投稿、反驳、修改、SSH 运维和 Critic Agent 分别有独立 prompt 契约。
3. **基于路径的委托** - dispatch packet 使用 `project:<relative-path>` 和 `framework:<relative-path>` 引用，子 Agent 必须直接读取源文件。
4. **审查门禁** - Stage 与模块必须经过 Reviewer 和 Gate Critic 检查后才可信地进入下游。
5. **结构化回溯** - 审查失败会转化为明确 backtrack advice，包括目标 Stage、必要修复、成功标准、证据路径、重建模式和重跑范围。
6. **跨 CLI 运行** - Claude Code 可自动发现 `.claude/skills/`；Codex、KimiCode 和其他 CLI 直接从 `skills/` 读取项目内 canonical skill。

---

## 仓库结构

| 路径 | 作用 |
|------|------|
| `spiral/` | 核心状态、项目创建、Conductor、dispatch、公共文献库、SSH registry 和路由逻辑。 |
| `scripts/state_manager.py` | 主 CLI：创建项目、查看状态、分发、推进、回溯、公共文献库操作。 |
| `scripts/orchestrator_guard.py` | 编排者写入边界检查，防止主 Agent 写入执行者/审查者产出。 |
| `scripts/subagent_launch_prompt.py` | 从 dispatch packet 中提取 compact launch prompt。 |
| `docs/AGENTS/` | Stage 执行、审查、Critic、SSH 运维和构建验证的 canonical role prompts。 |
| `skills/` | AutoPaper2 项目内 canonical skills。 |
| `.claude/skills/` | Claude Code 自动发现用的 `skills/` 镜像。 |
| `templates/stage/` | Stage 输出草稿模板。 |
| `templates/venue/` | 会议/期刊 LaTeX 模板。 |
| `config/` | Venue registry、执行环境默认配置、Gate rubrics、公共文献库、图像生成和需求追踪元数据。 |
| `tests/` | Pipeline、dispatch、CLI 兼容、SSH registry、资源规划等测试。 |

---

## 系统架构

```text
+------------------+       +-----------------------+       +------------------+
|   Conductor      | ----> | Durable Dispatch       | ----> |   Subagents      |
|  orchestration   |       | state/dispatch/*.md    |       | stage/review work|
+------------------+       +-----------------------+       +------------------+
        |                              |                              |
        v                              v                              v
 pipeline_state.yaml          project:/framework: refs       knowledge/, drafts/,
 decision_log.md              no parent-context rule         artifacts/, reviews/
 spiral_log.md
        |
        v
+------------------+
|   Gate Critics   |
| review & verdict |
+------------------+
```

核心组件：

- **Conductor** (`spiral/conductor.py`) 生成执行计划、推进状态、安排审查并记录回溯。
- **PipelineState** (`spiral/state.py`) 持久化当前模块/Stage、状态、过期 Stage、Gate 重审标记和 spiral 计数器。
- **ProjectManager** (`spiral/project.py`) 创建带时间戳的项目，初始化模板，写入 `state/research_brief.yaml`，复制 venue 资源，并探测执行环境。
- **Dispatch System** (`spiral/dispatch.py`, `scripts/state_manager.py dispatch`) 为 Stage 执行、Stage Review、Gate Review、SSH Ops 和 Revision Routing 写入持久化分发包。
- **Boundary Guard** (`scripts/orchestrator_guard.py`) 阻止编排者写入 `knowledge/M*/M*S*.md`、审查文件和最终论文 artifact 等子 Agent 拥有的路径。

---

## 六大模块

### M1 - 领域调研

| Stage | 说明 |
|-------|------|
| `M1S01` | 主题界定：研究问题、关键词、边界与 anchor papers。 |
| `M1S02` | 文献深度调研：迭代搜索与结构化 source log。 |
| `M1S03` | 缺口与机会分析。 |
| `M1S04` | 预想法草稿与候选方向。 |
| `M1S05` | 想法最终确定与 M1 到 M2 handoff。 |

**Gate G1** 检查调研逻辑、覆盖度、来源质量和缺口有效性。

### M2 - 方法设计

| Stage | 说明 |
|-------|------|
| `M2S01` | 跨领域搜索可迁移方法。 |
| `M2S02` | 从外部技术到目标问题的迁移分析。 |
| `M2S03` | 方法架构设计。 |
| `M2S04` | 算法与理论设计。 |
| `M2S05` | 实验设置设计：数据集、指标、基线、公平对比规则。 |
| `M2S06` | 完整实验计划与 M2 到 M3 handoff。 |

**Gate G2** 检查逻辑、方法可靠性、新颖性和实验计划可执行性。

### M3 - 实验实现与执行

| Stage | 说明 |
|-------|------|
| `M3S01` | 数据集与环境搭建。 |
| `M3S02` | 基线锁定与 smoke tests。 |
| `M3S03` | 主实验执行。 |
| `M3S04` | 结果验证、证据打包与 M3 到 M4 handoff。 |

**Gate G3** 检查方法实现、基线公平性、结果有效性和证据充分性。

### M4 - 深度分析

| Stage | 说明 |
|-------|------|
| `M4S01` | 实验后审计与发现整合。 |
| `M4S02` | 分析实验设计：消融、机制、鲁棒性检查。 |
| `M4S03` | 深度分析执行。 |
| `M4S04` | 分析结果整合与 M4 到 M5 handoff。 |

**Gate G4** 检查分析是否足以支撑论文主张。

### M5 - 论文写作与定稿

| Stage | 说明 |
|-------|------|
| `M5S01` | 写作前审计与贡献表述。 |
| `M5S02` | 论文大纲、作图计划、术语表和章节预算。 |
| `M5S04` | Methodology。 |
| `M5S05` | Experiments and Results。 |
| `M5S06` | Analysis and Discussion。 |
| `M5S03` | Introduction and Related Work，在证据锁定后撰写。 |
| `M5S07` | Abstract and Conclusion。 |
| `M5S08` | 完整草稿组装与 LaTeX 编译。 |
| `M5S09` | 全文润色与叙事连贯性审查。 |

**Gate G5** 检查逻辑、写作、证据、新颖性、伦理和编译状态。

### M6 - 投稿、审稿与修改

| Stage | 说明 |
|-------|------|
| `M6S01` | 投稿前审计与材料打包。 |
| `M6S02` | 外部审稿提交，例如 `paperreview.ai`。 |
| `M6S03` | 审稿接收与解析为原子化 review matrix。 |
| `M6S04` | 反驳策略与可执行 action plan。 |
| `M6S05` | 修改执行，必要时路由回早期 Stage。 |
| `M6S06` | 修改验证与完成裁决。 |

**Gate G6** 检查所有审稿意见是否已由可追踪证据充分解决。

---

## Gate 与审查体系

每个模块结束时都有 Gate。Gate Critic 与 Stage Executor 相互独立。

| Gate | 主要 Critic |
|------|-------------|
| `G1` | 逻辑、覆盖度、调研/source 质量 |
| `G2` | 逻辑、方法、新颖性 |
| `G3` | 方法、证据 |
| `G4` | 逻辑、证据、新颖性 |
| `G5` | 逻辑、写作、证据、新颖性、伦理 |
| `G6` | 逻辑、证据、写作、解决度 |

支持的 verdict 包括 `PASS`、`REVISE`、`REWORK`、`BACKTRACK`、`FIX` 和 `HALT`。

模块内部可按需运行 Stage Review。Reviewer 必须写入自己的 review 文件；若 verdict 不是 PASS，必须给出结构化 repair advice，供 Conductor 转化为回溯。

---

## 分发工作流

常规运行循环：

```bash
python scripts/state_manager.py status
python scripts/state_manager.py dispatch next --write
python scripts/subagent_launch_prompt.py --packet projects/<project>/state/dispatch/<packet>.md
```

然后把打印出的 compact launch prompt 交给匹配的子 Agent。子 Agent 必须读取 packet 和其中引用的 `docs/AGENTS/**/AGENT.md`，不得依赖父对话上下文。

常用分发命令：

```bash
python scripts/state_manager.py dispatch stage M2S03 --write
python scripts/state_manager.py dispatch reviews M2S03 --write
python scripts/state_manager.py dispatch gate G2 --write
python scripts/state_manager.py dispatch ssh allocation --write
python scripts/agent_dispatch.py --project projects/<project> --write next
```

编排者写项目路径前先检查边界：

```bash
python scripts/orchestrator_guard.py projects/<project> <target_path>
```

退出码为 `1` 表示目标路径属于 Stage Executor 或 Reviewer，必须通过 dispatch 处理。

---

## 螺旋回溯机制

当审查或 Gate 失败时，Conductor 会：

1. 在 `pipeline_state.yaml` 中记录失败原因和修复契约。
2. 将下游 Stage 标记为 stale。
3. 增加目标模块的 spiral 计数器。
4. 为目标 Stage 生成新的 dispatch packet。
5. 委托对应子 Agent 重新生成。

结构化回溯示例：

```bash
python scripts/state_manager.py backtrack M3S04 M3S02 \
  "baseline protocol mismatch" \
  --required-fix "Re-lock baselines using the M2S05 metric contract" \
  --success-criteria "M3S02 reports runnable baselines, seeds, metrics, and artifact paths" \
  --rebuild-mode full_regenerate \
  --evidence-paths knowledge/M2/M2S05_experiment_setup.md,experiments/results.tsv
```

两种重建模式：

- `full_regenerate` - 旧下游文件只能作为历史审计证据。
- `incremental_replay` - 可以参考旧文件，但保留内容必须针对当前上游输入重新验证。

---

## 快速开始

### 1. 克隆与安装

```bash
git clone git@github.com:qisanjiu/AutoPaper2.git
cd AutoPaper2
pip install -e ".[dev]"
```

要求 Python 3.10+。

### 2. 查看支持的 venue

```bash
python scripts/state_manager.py list-venues
```

支持的 venue ID 包括 `arxiv`、`neurips`、`icml`、`iclr`、`acl`、`cvpr` 和 `ieee_trans`。

### 3. 创建项目

```bash
python scripts/state_manager.py create \
  "Semantic Communication for Image Transmission via Reinforcement Learning" \
  "SemCom-Image-RL" \
  neurips \
  --keywords "semantic communication,reinforcement learning,image compression" \
  --reference "doi:10.0000/example-reference" \
  --foundation "arxiv:2401.00000"
```

默认项目目录为 `projects/{sanitized_name}-{YYYYMMDD-HHMMSS}/`。可通过 `SPIRAL_PROJECTS_ROOT` 覆盖项目根目录。

### 4. 选择项目并完成 onboarding

```bash
python scripts/state_manager.py list-projects
python scripts/state_manager.py use projects/SemCom-Image-RL-YYYYMMDD-HHMMSS

# 编辑项目配置：
#   config/execution_env.yaml
#   config/author_info.yaml

python scripts/state_manager.py onboarding-done
```

项目创建时会 best-effort 自动运行 `scripts/env_probe.py`，并生成 `state/onboarding_checklist.md`。

### 5. 生成并委托下一项任务

```bash
python scripts/state_manager.py dispatch next --write
python scripts/subagent_launch_prompt.py --packet projects/<project>/state/dispatch/<packet>.md
```

将输出的 compact launch prompt 交给指定子 Agent。子 Agent 写入目标产出后，再通过 `advance` 或模块 skill 流程继续推进。

高级编排辅助命令：

```bash
python scripts/state_manager.py run-module M1
python scripts/state_manager.py auto-run
python scripts/state_manager.py set-auto-advance on
```

这些辅助命令仍需遵守 Conductor-Executor 边界：Stage 输出和审查文件属于被委托的子 Agent。

---

## 项目入口与 Anchors

项目创建会把灵活输入标准化为 `state/research_brief.yaml`。下游 Stage 通过该文件理解主题、关键词和 anchor 材料。

支持的入口输入：

```bash
--keywords "keyword1,keyword2"
--reference "paper title, DOI, arXiv id, URL, or local PDF path"
--foundation "baseline or lineage paper/code"
--anchor "both:https://github.com/example/repo"
--input-manifest path/to/manifest.yaml
--note "Important project constraint or user preference"
```

本地 PDF anchor 会被复制到项目输入区。Paper 和 code anchor 会被分配 recommended stages，便于调研、方法、实验和写作 Agent 在合适位置使用。

---

## 项目目录结构

```text
projects/<name>-<timestamp>/
├── state/
│   ├── pipeline_state.yaml
│   ├── research_brief.yaml
│   ├── decision_log.md
│   ├── spiral_log.md
│   ├── onboarding_checklist.md
│   └── dispatch/
├── knowledge/
│   ├── M1/ ... M6/
│   ├── reviews/
│   ├── handoff_M1_M2.md
│   ├── handoff_M2_M3.md
│   ├── handoff_M3_M4.md
│   ├── handoff_M4_M5.md
│   ├── handoff_M5_completion.md
│   └── handoff_M6_completion.md
├── drafts/
│   └── M1S01/ ... M6S06/
├── experiments/
│   ├── src/
│   ├── configs/
│   ├── artifacts/
│   ├── logs/
│   ├── results.tsv
│   └── analysis_results.tsv
├── artifacts/
│   ├── paper.tex
│   ├── paper.pdf
│   ├── refs.bib
│   └── latex_template/
└── config/
    ├── execution_env.yaml
    └── author_info.yaml
```

---

## 配置说明

### Venue Registry

Venue 配置位于 `config/venue_registry.yaml`。项目创建时会把所选 venue 的 LaTeX 资源复制到 `artifacts/latex_template/`。

### 执行环境

每个项目都会得到 `config/execution_env.yaml`，支持：

- `local` 模式，在当前机器执行。
- `ssh` 模式，在远程 GPU 服务器执行。
- resource-pool 规划，支持本地/远程混合实验队列。

常用 SSH 命令：

```bash
python scripts/ssh_manager.py server list
python scripts/ssh_manager.py server add <server_id> --host <host> --user <user>
python scripts/ssh_manager.py probe <server_id>
python scripts/ssh_manager.py lease alloc --project projects/<project> --server-id auto --apply
python scripts/ssh_manager.py lease alloc-pool --project projects/<project> --count 2 --apply
```

创建项目时也可直接请求托管 SSH 分配：

```bash
python scripts/state_manager.py create "Topic" "Name" neurips \
  --env-mode ssh --server-id auto --lease-hours 48 --min-gpu-count 1
```

### 公共文献库

`config/public_db.yaml` 控制框架级 SQLite 文献数据库。该数据库首次使用时自动初始化，并在多个项目之间共享。

```bash
python scripts/state_manager.py public-db status
python scripts/state_manager.py public-db stats
python scripts/state_manager.py public-db search "semantic communication"
python scripts/state_manager.py public-db import-project projects/<project>
```

M1 survey memory 会连接该数据库，以便跨项目复用 source log。

### 图像与图表生成

图像/图表默认配置位于：

- `config/image_generation.yaml`
- `config/figure_style_profiles.yaml`

本地 API 凭据应放在被 git 忽略的 local config 或环境变量中，例如 `OPENAI_API_KEY` 与 `OPENAI_BASE_URL`。`scripts/generate_image.py` 支持 M5 作图规划中的图像生成和 Draw.io 风格 diagram 工作流。

---

## Skills 与跨 CLI 兼容

`skills/` 是 AutoPaper2 的 canonical skill source。`.claude/skills/` 是 Claude Code 自动发现用镜像。非 Claude 运行时应先读取 `AGENTS.md`，再直接打开本仓库内的 `skills/<skill_name>/SKILL.md`。

| Skill | 说明 |
|-------|------|
| `AutoPaper2_project_onboarding` | 项目创建后的 onboarding 与检查。 |
| `AutoPaper2_project_router` | 根据当前状态路由到正确模块。 |
| `AutoPaper2_project_auto_run` | 端到端编排辅助。 |
| `AutoPaper2_project_backtrack` | 结构化人工回溯。 |
| `AutoPaper2_manual_import` | 导入文献到公共 DB 或注册共享数据集。 |
| `AutoPaper2_env_probe` | 探测本地 CUDA/Python/GPU 环境。 |
| `AutoPaper2_ssh_ops` | 管理 SSH registry、租约、探测、同步和远程命令证据。 |
| `AutoPaper2_ssh_server_onboarding` | 引导新增 SSH 服务器并验证。 |
| `AutoPaper2_m1_survey` | M1 领域调研到 G1。 |
| `AutoPaper2_m2_method_design` | M2 方法设计到 G2。 |
| `AutoPaper2_m3_experiment` | M3 实现与实验到 G3。 |
| `AutoPaper2_m4_deep_analysis` | M4 深度分析到 G4。 |
| `AutoPaper2_m5_writing` | M5 写作、编译与润色到 G5。 |
| `AutoPaper2_m6_submission_review` | M6 投稿、审稿解析、反驳、修改与 G6。 |

验证本地 skill 和 prompt 兼容性：

```bash
python scripts/cli_compat_check.py
```

---

## 质量检查

修改框架行为前建议运行：

```bash
python scripts/cli_compat_check.py
python scripts/agent_consistency_check.py
python scripts/requirement_trace_check.py
python scripts/test_health_check.py
python -m unittest discover -s tests
```

仓库也在 `pyproject.toml` 中配置了 `pytest`，安装 dev 依赖后可使用 `pytest`。

---

## 许可证

MIT
