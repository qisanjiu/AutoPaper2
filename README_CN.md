# AutoPaper2

> **一个将研究主题从初始界定到最终投稿、审稿与修改的完整自主研究框架。**

AutoPaper2 是一个结构化、Agent 驱动的学术论文自动化流水线框架。它将完整的论文生命周期划分为六个模块（M1–M6），每个模块包含明确的 Stage、专属 Agent、Stage 级审查以及 Gate 评审。框架严格执行**编排者–执行者分离**：主编排器（Conductor）只负责调度与回溯，具体 Stage 内容和审查工作必须由子 Agent 完成。

---

## 目录

- [项目概览](#项目概览)
- [系统架构](#系统架构)
- [六大模块](#六大模块)
  - [M1 – 领域调研](#m1--领域调研)
  - [M2 – 方法设计](#m2--方法设计)
  - [M3 – 实验执行](#m3--实验执行)
  - [M4 – 深度分析](#m4--深度分析)
  - [M5 – 论文写作](#m5--论文写作)
  - [M6 – 投稿、审稿与修改](#m6--投稿审稿与修改)
- [Gate 与审查体系](#gate-与审查体系)
- [螺旋回溯机制](#螺旋回溯机制)
- [快速开始](#快速开始)
- [项目目录结构](#项目目录结构)
- [配置说明](#配置说明)
- [Claude Code Skill 集成](#claude-code-skill-集成)
- [许可证](#许可证)

---

## 项目概览

AutoPaper2 将论文写作视为**软件流水线**：

1. **状态驱动** – 每个项目携带 `pipeline_state.yaml`，记录当前模块、Stage、状态、历史与回溯日志。
2. **Agent 专业化** – 调研 Agent、方法 Agent、实验 Agent、写作 Agent、评审 Critic 团队各司其职。
3. **审查门禁** – 任何模块在未通过 Stage 审查和最终 Gate 评审前，不得进入下一模块。
4. **自我修正** – 当审查失败时，Conductor 发起**螺旋回溯**，将下游 Stage 标记为过期，并重新执行。

---

## 系统架构

```
+------------------+     +------------------+     +------------------+
|   Conductor      |---->|  子 Agent        |---->|   Critic 团队    |
|   (主编排器)     |     | (Stage 执行)     |     | (审查 & Gate)    |
+------------------+     +------------------+     +------------------+
         |                        |                        |
         v                        v                        v
   pipeline_state.yaml      knowledge/M*             reviews/
   decision_log.md          drafts/                  gate_aggregate.md
   spiral_log.md            experiments/
```

- **Conductor** (`spiral/conductor.py`) – 绝不直接写入 Stage 产出；只负责调度、分发与回溯。
- **State Manager** (`spiral/state.py`) – 持久化项目状态，包括过期追踪、螺旋计数器、Gate 重审标志。
- **Project Manager** (`spiral/project.py`) – 创建项目、初始化模板、绑定会议配置。
- **Dispatch System** (`scripts/state_manager.py`) – 生成分发包，子 Agent 据此读取输入、写入输出。

---

## 六大模块

### M1 – 领域调研

| Stage | 说明 |
|-------|------|
| **M1S01** | 主题界定 – 明确研究问题、关键词与锚定论文。 |
| **M1S02** | 文献深度调研 – 三轮迭代搜索，生成结构化 Source Log。 |
| **M1S03** | 缺口与机会分析 – 识别尚未解决的问题。 |
| **M1S04** | 预想法草稿 – 头脑风暴解决方向。 |
| **M1S05** | 想法最终确定 – 锁定核心主张与方法。 |

**Gate G1** – 逻辑 + 覆盖度 Critic 评审调研完整性与缺口分析有效性。

### M2 – 方法设计

| Stage | 说明 |
|-------|------|
| **M2S01** | 跨领域搜索 – 从相邻领域寻找可迁移方法。 |
| **M2S02** | 迁移分析 – 将外部技术映射到目标问题。 |
| **M2S03** | 方法架构设计 – 定义整体流程。 |
| **M2S04** | 算法与理论设计 – 形式化目标函数、证明与复杂度分析。 |
| **M2S05** | 实验设置设计 – 数据集、指标、基线与公平对比规则。 |
| **M2S06** | 完整实验计划 – 整合为可执行计划。 |

**Gate G2** – 逻辑 + 方法 + 新颖性 Critic。

### M3 – 实验执行

| Stage | 说明 |
|-------|------|
| **M3S01** | 数据集与环境搭建 – 锁定依赖、硬件与可复现配置。 |
| **M3S02** | 基线锁定 – 运行基线并验证公平对比。 |
| **M3S03** | 主实验执行 – 运行所提方法。 |
| **M3S04** | 结果验证与证据打包 – 统计检验、Claim Ledger、Evidence Ladder。 |

**Gate G3** – 方法 + 证据 Critic。

### M4 – 深度分析

| Stage | 说明 |
|-------|------|
| **M4S01** | 实验后审计与发现整合 – 汇总所有观察。 |
| **M4S02** | 深度分析实验设计 – 消融实验、机制研究、鲁棒性测试。 |
| **M4S03** | 深度分析执行 – 运行设计的分析实验。 |
| **M4S04** | 分析结果整合 – 为论文打包证据。 |

**Gate G4** – 逻辑 + 证据 + 新颖性 Critic。

### M5 – 论文写作

| Stage | 说明 |
|-------|------|
| **M5S01** | 写作前审计 – 明确贡献并挑选风格参照论文。 |
| **M5S02** | 论文大纲 – 情节规划、术语表、章节预算。 |
| **M5S04** | 方法 |
| **M5S05** | 实验与结果 |
| **M5S06** | 分析与讨论 – 与实验结果一一对应。 |
| **M5S03** | 引言与相关工作 – 在实验完成后撰写以锁定故事线。 |
| **M5S07** | 摘要与结论 |
| **M5S08** | 完整草稿组装与编译 – LaTeX 构建、图表检查。 |
| **M5S09** | 全文润色与叙事连贯性审阅 – 最终 LaTeX/PDF 润色与跨章节一致性检查。 |

**Gate G5** – 逻辑 + 写作 + 证据 + 新颖性 + 伦理 Critic。可选同行评审模拟。

### M6 – 投稿、审稿与修改

| Stage | 说明 |
|-------|------|
| **M6S01** | 投稿前审计与打包 – 会议合规性检查表。 |
| **M6S02** | 外部审稿提交 – 如 paperreview.ai。 |
| **M6S03** | 审稿接收与解析 – IMAP 监控 + 原子化审稿矩阵。 |
| **M6S04** | 反驳策略与行动计划 – 针对每条审稿意见规划回溯。 |
| **M6S05** | 修改执行 – 根据需要路由回早期 Stage。 |
| **M6S06** | 修改验证与完成裁决。 |

**Gate G6** – 解决度 Critic 验证所有审稿意见是否已被充分回应。

---

## Gate 与审查体系

每个模块结束时有 **Gate**，由独立 Critic 评估：

| Gate | Critic 组合 |
|------|------------|
| G1 | 逻辑、覆盖度 |
| G2 | 逻辑、方法、新颖性 |
| G3 | 方法、证据 |
| G4 | 逻辑、证据、新颖性 |
| G5 | 逻辑、写作、证据、新颖性、伦理 |
| G6 | 逻辑、证据、写作、解决度 |

**裁决类型**：`PASS`、`REVISE`、`REWORK`、`BACKTRACK`、`FIX`、`HALT`。

**Stage 审查**在模块内部运行（例如 M2S03 完成后由设计审查 Critic 检查与 M2S02 的一致性）。这种早期拦截防止错误累积到 Gate。

---

## 螺旋回溯机制

当审查或 Gate 失败时，Conductor 发起**回溯**：

1. 在 `pipeline_state.yaml` 中记录原因、必要修复与成功标准。
2. 将所有下游 Stage 标记为**过期（stale）**。
3. 为目标模块增加**螺旋计数器**（默认上限 10 次）。
4. 通过对应子 Agent 重新执行目标 Stage，并附带完整回溯建议。

两种重建模式：
- **full_regenerate** – 将旧文件仅视为历史审计，禁止复制粘贴。
- **incremental_replay** – 可参考旧文件，但所有保留内容必须针对当前上游输入重新验证。

---

## 快速开始

### 1. 克隆与安装

```bash
git clone git@github.com:qisanjiu/AutoPaper2.git
cd AutoPaper2
pip install -e ".[dev]"
```

### 2. 创建项目

```python
from spiral.project import ProjectManager

proj = ProjectManager.create(
    topic="基于强化学习的图像语义通信",
    display_name="SemCom-Image-RL",
    venue="neurips",          # 可选 arxiv, icml, iclr, acl, cvpr, ieee_trans
    keywords=["semantic communication", "reinforcement learning", "image compression"],
)
print(proj)
```

### 3. 查看状态并完成初始化

```bash
python scripts/state_manager.py status
# 填写 config/execution_env.yaml 和 config/author_info.yaml
python scripts/state_manager.py onboarding-done /path/to/project
```

### 4. 运行模块（通过 Claude Code Skills）

```
/AutoPaper2_m1_survey   # 开始领域调研
/AutoPaper2_m2_method_design  # M1 完成后进入方法设计
/AutoPaper2_m3_experiment     # M2 完成后进入实验执行
...
```

或手动运行：

```bash
python scripts/state_manager.py run-module M1
```

---

## 项目目录结构

每个项目创建于 `projects/{ sanitized_name }-{YYYYMMDD-HHMMSS}/`：

```
my-project-20260115-143022/
├── state/
│   ├── pipeline_state.yaml      # 全局状态
│   ├── decision_log.md          # 可读决策日志
│   ├── spiral_log.md            # 回溯历史
│   └── onboarding_checklist.md  # 初始化检查清单
├── knowledge/
│   ├── M1/ ... M6/              # Stage 产出
│   └── reviews/                 # Stage & Gate 评审文件
├── drafts/
│   └── M1S01/ ... M6S06/        # 工作草稿
├── experiments/
│   ├── results.tsv
│   ├── analysis_results.tsv
│   ├── src/                     # 实验代码
│   └── configs/                 # 实验配置
├── artifacts/
│   ├── paper.tex
│   ├── paper.pdf
│   ├── refs.bib
│   └── latex_template/          # 会议专用 LaTeX 模板
└── config/
    ├── execution_env.yaml       # 硬件、SSH、conda 等环境配置
    └── author_info.yaml         # 作者信息
```

---

## 配置说明

### 会议注册表

支持的会议/期刊定义在 `config/venue_registry.yaml`：

| 会议/期刊 | 页数限制 | 格式 |
|----------|---------|------|
| arXiv | – | 预印本 |
| NeurIPS | 9 + 参考文献 | 会议 |
| ICML | 9 + 参考文献 | 会议 |
| ICLR | 9 + 参考文献 | 会议 |
| ACL | 8 + 参考文献 | 会议 |
| CVPR | 8 + 参考文献 | 会议 |
| IEEE Trans | ~10–14 | 期刊 |

### 执行环境

`config/execution_env.yaml`（每个项目自动生成）支持：
- **local** 模式 – 在当前机器运行。
- **ssh** 模式 – 将实验分发到远程 GPU 服务器。

项目创建时自动运行环境探测（`scripts/env_probe.py` 检测 CUDA、Python 版本、GPU 数量与框架版本）。

---

## Claude Code Skill 集成

AutoPaper2 设计为一组 **Claude Code Skills**，位于 `.claude/skills/` 和 `skills/`：

`skills/` 是项目内 canonical skill source。`.claude/skills/` 是给 Claude Code 自动发现用的镜像。Codex、KimiCode 和其他 CLI 应先读取 `AGENTS.md`，再从本仓库直接打开对应的 `skills/<skill_name>/SKILL.md`；不得依赖用户全局 skill 目录。

| Skill | 说明 |
|-------|------|
| `AutoPaper2_env_probe` | 检测本地 GPU/Python/CUDA 并填充 `execution_env.yaml`。 |
| `AutoPaper2_m1_survey` | M1 完整流程：主题界定 → 文献搜索 → 创意生成 → G1。 |
| `AutoPaper2_m2_method_design` | M2 完整流程：跨领域搜索 → 迁移分析 → 架构设计 → G2。 |
| `AutoPaper2_m3_experiment` | M3 完整流程：环境搭建 → 基线 → 主实验 → G3。 |
| `AutoPaper2_m4_deep_analysis` | M4 完整流程：审计 → 消融设计 → 执行 → G4。 |
| `AutoPaper2_m5_writing` | M5 完整流程：大纲 → 分节写作 → 编译 → G5。 |
| `AutoPaper2_m6_submission_review` | M6 完整流程：投稿 → 审稿解析 → 反驳 → 修改 → G6。 |
| `AutoPaper2_project_auto_run` | 端到端自动运行所有模块。 |
| `AutoPaper2_project_backtrack` | 处理手动回溯请求。 |
| `AutoPaper2_project_router` | 根据当前状态路由到正确模块。 |

使用以下命令验证跨 CLI 的本地 skill 与 prompt 兼容性：

```bash
python scripts/cli_compat_check.py
```

---

## 许可证

MIT
