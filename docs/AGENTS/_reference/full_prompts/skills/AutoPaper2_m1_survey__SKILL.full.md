---
name: AutoPaper2_m1_survey
description: >
  AutoPaper2 Module 1 (Domain Survey) 全流程执行 Skill。
  当用户需要开始一个新的研究项目的领域调研阶段时触发，包括：
  创建新项目 → M1S01 Topic Scoping → M1S02 3-Round 迭代搜索（含 Survey Review）
  → Gate G1（Coverage + Logic Critic）→ M1S03-M1S05 Ideation → Handoff M1→M2。
  默认行为是创建新项目；仅在用户明确指定进入现有项目时复用已有项目。
argument-hint: [研究主题或现有项目路径]
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

# M1 Domain Survey — 领域调研全流程

执行 AutoPaper2 的 **Module 1: Domain Survey**，完成从主题界定到研究假设生成的完整流程。

## 触发条件

当用户说以下任意一种表述时触发本 Skill：

- "进入 M1"
- "开始调研"
- "调研 [主题]"
- "M1 阶段"
- "领域调研"
- "survey [topic]"
- "开始一个新项目"
- "研究 [方向]"

**不触发**的情况：
- 用户明确说 "进入 M2/M3/M4/M5"（应路由到对应 Stage）
- 用户明确说 "继续当前项目" 且当前不在 M1（应路由到当前 stage 的 skill）

## 默认行为 vs 显式项目指定

### 默认：创建新项目

如果用户没有明确指定现有项目路径或项目名称，**必须创建新项目**：

```bash
cd {framework_root}
python scripts/state_manager.py create \
  "{用户提供的主题}" \
  "{自动生成的简称}" \
  --keywords "keyword1, keyword2" \
  --reference "paper title / url / pdf" \
  --foundation "base paper title / url / pdf"
```

项目名称生成规则：
- 取主题前 2-4 个关键词的首字母组合
- 例如 "自适应时间序列预测" → "ATSF"
- 例如 "Transformer Time Series Forecasting" → "TSF-Transformer"

### 显式：进入现有项目

如果用户明确指定了现有项目，例如：
- "在 SemCom-Image 项目中执行 M1"
- "继续 SemCom-Image 的调研"
- 提供了项目路径如 `projects/XXX-YYYYMMDD-HHMMSS`

则定位到该项目，检查当前状态：
- 如果项目已完成 M1 → 询问是否回溯重新执行
- 如果项目在 M1 中间 → 从当前 stage 继续
- 如果项目尚未启动 M1 → 正常启动

---

## 项目创建配置清单（Project Creation Checklist）

> **重要原则**：创建新项目时，必须**一次性**收集并配置以下参数。后续 M2-M6 模块的执行依赖这些初始配置，**不建议在创建后补填**。

### 1. 基础信息（必填）

| 参数 | CLI 标志 | 说明 | 示例 |
|------|---------|------|------|
| topic | 位置参数 1 | 研究主题（一句话描述） | `"Adaptive Time Series Forecasting"` |
| display_name | 位置参数 2 | 项目显示名称（用于生成目录名） | `"ATSF-Transformer"` |
| keywords | `--keywords` | 3-5 个关键词，影响 M1S02 搜索方向 | `"time series forecasting, calibration, robustness"` |

### 2. 投稿目标（必填，默认 arxiv）

| 参数 | CLI 标志 | 可选值 | 影响 |
|------|---------|--------|------|
| venue | 位置参数 3 或 `--venue` | `arxiv`, `neurips`, `icml`, `iclr`, `acl`, `cvpr`, `ieee_trans` | LaTeX 模板、页数限制、格式要求 |

### 3. 入口锚点（强烈建议）

| 参数 | CLI 标志 | 说明 |
|------|---------|------|
| foundation_papers | `--foundation` | 基线/基础论文（本文方法建立在其上） |
| reference_papers | `--reference`, `--ref` | 参考论文（相关但非基础） |
| input_manifest | `--manifest` | 预定义的文献清单文件路径 |

### 4. 执行环境配置（强烈建议提前配置，M3 实验阶段依赖）

| 参数 | CLI 标志 | 可选值 | 默认值 | 说明 |
|------|---------|--------|--------|------|
| env_mode | `--env-mode` | `local` / `ssh` | `local` | 实验执行位置 |
| ssh_host | `--ssh-host` | — | — | 远程服务器地址 |
| ssh_user | `--ssh-user` | — | — | SSH 用户名 |
| ssh_port | `--ssh-port` | — | `22` | SSH 端口 |
| ssh_auth_method | `--ssh-auth-method` | `key` / `password` | `key` | 认证方式 |
| ssh_password | `--ssh-password` | — | — | 密码（仅 `password` 模式，临时存储） |
| ssh_workspace | `--ssh-workspace` | — | `~/AutoPaper2/projects/{name}` | 远程工作空间路径（位于远程框架根目录下的 projects/） |
| ssh_conda_env | `--ssh-conda-env` | — | — | 远程 conda 环境名 |
| python_version | `--python-version` | — | `3.10` | Python 版本 |
| cuda_version | `--cuda-version` | — | `12.1` | CUDA 版本 |
| env_manager | `--env-manager` | `conda` / `venv` / `uv` / `docker` | `conda` | 环境管理工具 |

**环境配置决策指南**：
- **本地有 GPU** → `--env-mode local`
- **本地无 GPU，需远程服务器** → `--env-mode ssh`
- **已有 SSH 密钥** → `--ssh-auth-method key`（无需密码）
- **只有密码，无密钥** → `--ssh-auth-method password --ssh-password "xxx"`（M3S02 自动部署密钥后切换为 key）

### 5. 其他选项

| 参数 | CLI 标志 | 说明 |
|------|---------|------|
| auto_advance | `--auto-advance` | 是否自动推进模块（默认 false） |
| notes | `--note` | 项目备注 |

### CLI 创建示例

```bash
# 最简创建（仅基础信息）
cd {framework_root}
python scripts/state_manager.py create \
  "Adaptive Time Series Forecasting" \
  "ATSF-Transformer"

# 标准创建（含投稿目标和关键词）
python scripts/state_manager.py create \
  "Adaptive Time Series Forecasting" \
  "ATSF-Transformer" \
  neurips \
  --keywords "time series forecasting, calibration, robustness" \
  --foundation "Informer: Beyond Efficient Transformer for Long Sequence Time-Series Forecasting" \
  --reference "Autoformer, FEDformer"

# 完整配置（SSH 远程，已有密钥）
python scripts/state_manager.py create \
  "Adaptive Time Series Forecasting" \
  "ATSF-Transformer" \
  neurips \
  --keywords "time series forecasting, calibration, robustness" \
  --env-mode ssh \
  --ssh-host 10.10.9.210 \
  --ssh-user zhouzhehao \
  --ssh-port 30011 \
  --ssh-auth-method key \
  --ssh-workspace "~/AutoPaper2/projects/ATSF-Transformer" \
  --ssh-conda-env "atsf" \
  --python-version 3.10 \
  --cuda-version 12.1

# 完整配置（SSH 远程，只有密码 → M3S02 自动部署密钥）
python scripts/state_manager.py create \
  "Adaptive Time Series Forecasting" \
  "ATSF-Transformer" \
  neurips \
  --keywords "time series forecasting, calibration, robustness" \
  --env-mode ssh \
  --ssh-host 10.10.9.210 \
  --ssh-user zhouzhehao \
  --ssh-port 30011 \
  --ssh-auth-method password \
  --ssh-password "your_password_here" \
  --ssh-workspace "~/AutoPaper2/projects/ATSF-Transformer" \
  --python-version 3.10 \
  --cuda-version 12.1
```

---

## 执行前检查清单

在启动 M1 之前，必须确认：

- [ ] 项目已创建或已定位（`projects/{name}-{timestamp}/` 存在）
- [ ] `state/pipeline_state.yaml` 可读
- [ ] **Onboarding 已完成**（`current.status != onboarding_pending`）
  - 如为 `onboarding_pending` → **必须暂停**，触发 `AutoPaper2_project_onboarding` Skill
  - 等待用户补全 `config/execution_env.yaml` 和 `config/author_info.yaml` 后回复 "已填写"
  - **注意**：若 `execution.mode == local`，SSH 配置无需填写；仅当 `mode == ssh` 时才需检查 ssh.host, ssh.user
- [ ] `state/survey_memory.yaml` 已初始化
- [ ] `state/research_brief.yaml` 已写入（如有 foundation/reference anchors）
- [ ] 当前 stage 为 M1S01 或用户明确要求重新执行 M1
- [ ] 用户提供的主题足够具体（如果太宽泛，先执行 topic clarification）

## 控制工作流

```
Phase 0: 项目初始化
  → 创建/定位项目
  → **检查 Onboarding 状态**：
     → 读取 state/pipeline_state.yaml
     → 若 status == onboarding_pending：
        → 读取 state/onboarding_checklist.md
        → 向用户展示待填写清单
        → **阻塞等待用户回复 "已填写"**
        → 用户确认后验证 config/execution_env.yaml 和 config/author_info.yaml
        → 验证通过 → 更新 status = pending，删除 onboarding_checklist.md
        → 验证不通过 → 指出缺失字段，继续阻塞
     → 若 onboarding 已完成 → 继续
  → 确认 venue（默认 arxiv，用户可覆盖）
  → 加载 AGENT.md: docs/AGENTS/survey/AGENT.md

Phase 1: M1S01 Topic Scoping
  → Survey Agent 执行
  → 产出: knowledge/M1/M1S01_topic_scoping.md
  → Conductor advance: M1S01 → M1S02

Phase 2: M1S02 Literature Deep Dive (3-Round)
  → Round 1: Survey Agent 广泛搜索
     → 更新 survey_memory (batch round=1, status=awaiting_review)
     → Survey Review Agent 审查
     → verdict: PASS → Round 2
     → verdict: REWORK → **主 agent 不得修改，必须重新调用 Survey Agent subagent 修正**
  → Round 2: Survey Agent 定向搜索
     → 更新 survey_memory (batch round=2, status=awaiting_review)
     → Survey Review Agent 审查
     → verdict: PASS → Round 3
     → verdict: REWORK → **重新调用 Survey Agent subagent 修正**
  → Round 3: Survey Agent 盲区填补
     → 产出 M1_source_log.yaml
     → 每篇核心论文必须完成深读字段：背景、贡献、模型、方法、实验设置、结果、分析、结论、局限性
     → Gap 报告必须按大方向/中方向/小方向分层，并给出至少 2 个来源的证据链
     → 更新 survey_memory (batch round=3, status=awaiting_review)
     → Survey Review Agent 终审
     → verdict: PASS → M1S02 完成
     → verdict: REWORK → **重新调用 Survey Agent subagent 修正**
  → Conductor advance: M1S02 → Gate G1

Phase 3: Gate G1 审查
  → Coverage Critic 审查
     → 产出: knowledge/reviews/G1_coverage_review.md
  → Logic Critic 审查
     → 产出: knowledge/reviews/G1_logic_review.md
  → 综合 verdict:
     → 全部 PASS → 进入 M1S03
     → 任一 BACKTRACK / REVISE / FIX → **Conductor 调用 backtrack() 更新状态后，必须调用对应 subagent（Survey Agent 或 Ideation Agent）重新执行目标 stage；主 agent 绝对禁止直接修改 stage 文件**
     → 任一 HALT → 终止 M1，报告原因

Phase 4: M1S03-M1S05 Ideation
  → M1S03 Pre-Idea Draft
     → 产出: drafts/M1S03/pre_idea_draft.md
  → M1S03 Research Question
     → 产出: knowledge/M1/M1S03_research_question.md
  → M1S04 Hypothesis Generation
     → 产出: knowledge/M1/M1S04_hypothesis_generation.md
  → M1S05 Novelty & Feasibility
     → 产出: knowledge/M1/M1S05_novelty_feasibility.md

Phase 5: Handoff & 完成
  → 产出: knowledge/handoff_M1_M2.md
  → 标记 M1 模块 completed
  → 报告完成状态，建议下一步（进入 M2）
```

## Agent 调用规范

### Survey Agent（Phase 1-2）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/survey/AGENT.md`
- 当前项目路径
- 当前 stage（M1S01 或 M1S02 Round X）
- Survey Memory 当前状态（从 `state/survey_memory.yaml` 读取）
- 如果是 M1S02，必须明确指定当前 Round（1/2/3）和上一轮 Reviewer 反馈
- **如果是回溯后的重新执行，必须完整传递 `backtrack_advice`（blocking_reason, required_fix, success_criteria, rebuild_mode, evidence_paths 等）**

**Survey Agent subagent 工具集**: ReadFile, WriteFile, Shell, WebSearch, WebFetch

**强制规则**：主 agent（Conductor/Skill）不得直接修改 Survey Agent 的产出文件；所有修正必须通过重新调用 Survey Agent subagent 完成。

### Survey Review Agent（Phase 2）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/survey_review/AGENT.md`
- 当前审查的 Round（1/2/3）
- Survey Agent 的产出文件路径
- Source Log 路径
- 产出路径：`knowledge/reviews/M1S02_round{N}_review.md`

**Survey Review Agent subagent 工具集**: ReadFile, WriteFile, Shell

### Coverage Critic（Phase 3）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/coverage/AGENT.md`
- M1S02 产出路径
- Source Log 路径
- 产出路径：`knowledge/reviews/G1_coverage_review.md`

### Logic Critic（Phase 3）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/logic/AGENT.md`
- M1S03-M1S05 产出路径
- M1S02 产出路径（辅助）
- 产出路径：`knowledge/reviews/G1_logic_review.md`

### Ideation Agent（Phase 4）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/ideation/AGENT.md`
- 当前 stage（M1S03 Pre-Idea / M1S03 / M1S04 / M1S05）
- M1S02 产出路径（输入）
- Source Log 路径（输入）
- 产出路径
- **如果是回溯后的重新执行（如 Gate G1 REVISE 回到 M1S03-M1S05），必须完整传递 `backtrack_advice`**

**Ideation Agent subagent 工具集**: ReadFile, WriteFile, Shell, WebSearch

**强制规则**：主 agent 不得直接修改 Ideation Agent 的产出文件；所有修正必须通过重新调用 Ideation Agent subagent 完成。

## 状态管理规范

每完成一个 Stage 或一个 Round，必须更新 `state/pipeline_state.yaml` 和 `state/survey_memory.yaml`。

使用 Python 脚本更新：

```python
from spiral.state import PipelineState
from spiral.survey_memory import SurveyMemoryManager
from pathlib import Path

proj = Path("projects/XXX")

# PipelineState
state = PipelineState(proj)
state.record_completion("M1S01", "survey", Path("knowledge/M1/M1S01_topic_scoping.md"))
state.set_stage("M1S02", "in_progress")

# SurveyMemory (for M1S02 rounds)
survey_mgr = SurveyMemoryManager(proj)
memory = survey_mgr.load()
memory.add_batch(["query1", "query2"], round_num=1)
survey_mgr.save(memory)
```

## 质量门控

在每个关键节点执行自动检查：

| 节点 | 检查项 | 失败处理 |
|------|--------|---------|
| M1S01 完成后 | 产出文件是否存在且非空 | 重试一次，仍失败则 HALT |
| M1S02 每轮 Review | verdict 是否为 PASS | REWORK 则让 Survey Agent 修正，最多 2 次 |
| M1S02 Round 3 完成后 | Gap 类型分布：至少 1 个 EG 或 ValG | 若全为 VG，要求 Survey Agent 补充架构改进型 Gap 挖掘 |
| M1S02 Round 3 完成后 | 核心论文深读字段完整；Gap 分为大/中/小方向并有证据链 | 缺失时要求 Survey Agent 补全 Source Log 与正文 |
| Gate G1 | Coverage ≥7.0/10 AND Logic ≥7.0/10 | BACKTRACK 到指定 stage |
| M1S03 Pre-Idea | 是否包含反对意见和证伪路径；架构改进型是否指明具体瓶颈 | 要求 Ideation Agent 补充 |
| M1S05 完成后 | 最终判断是否为 PROCEED | 若为 ABANDON，终止 M1 |

## Checkpoint 与用户交互

以下节点默认向用户发送进度更新（非阻塞，继续执行）：

1. **M1S01 完成后**: "Topic Scoping 完成，已界定 [主题] 的研究范围。"
2. **M1S02 Round 1 完成后**: "Round 1 广泛搜索完成，发现 [N] 篇候选文献，[M] 个初步 Gap。"
3. **M1S02 Round 3 完成后**: "文献调研完成，共 [N] 篇核心文献，[M] 个明确 Gap。"
4. **Gate G1 完成后**: "Gate G1 通过（Coverage: X/10, Logic: X/10），进入方向选择阶段。"
5. **M1 完成后**: "M1 领域调研完成。研究问题：[问题摘要]。建议进入 M2（方法设计）。"

如果用户要求暂停或介入（如 "等一下"、"先别继续"），在下一个 Checkpoint 停止并等待用户指令。

## 输出协议

遵循 AutoPaper2 的输出协议：

1. **Output Versioning**: 首次写入时带时间戳，然后复制到固定名
2. **Output Manifest**: 每个产出记录到项目根目录的 `MANIFEST.md`
3. **Output Language**: 默认中文（与用户一致），用户可覆盖

## Context Recovery

如果上下文被压缩或 session 中断，恢复流程：

1. 读取 `state/pipeline_state.yaml` → 确认当前 stage
2. 读取 `state/survey_memory.yaml` → 恢复调研状态
3. 读取当前 stage 的 AGENT.md
4. 读取最近的产出文件，恢复上下文
5. 从当前 stage 继续执行（不重新执行已完成的 stage）

**CLI 辅助命令**：
```bash
# 查看当前项目状态
python scripts/state_manager.py status

# 查看当前 stage 的自动执行计划
python scripts/state_manager.py auto-stage M1S01

# 自动运行当前模块
python scripts/state_manager.py auto-module M1
```

## Key Rules

- **默认创建新项目**：除非用户明确指定现有项目，否则一律创建新项目
- **不要跳过 3-Round**：M1S02 必须完整执行 3 轮搜索 + Reviewer 审查
- **Reviewer 必须独立**：Survey Agent 和 Survey Review Agent 必须作为不同 subagent 调用，不得由同一个 agent 同时扮演
- **Gate G1 必须双 Critic**：Coverage 和 Logic 两个 Critic 都通过才算 Gate 通过
- **Pre-Idea Draft 必须完成**：M1S03 正式产出前，必须先完成 Pre-Idea Draft
- **Handoff 文件必须生成**：M1 完成后必须产出 `knowledge/handoff_M1_M2.md`
- **入口锚点必须落地**：如果用户提供 foundation/reference 论文、PDF、URL 或 GitHub，必须写入 `state/research_brief.yaml`，并在 M1S02 的 Source Log 中为 foundation anchor 回填 `entry_anchor_id`
- **Source Log 必须一致**：Markdown 中引用的文献数量必须与 Source Log 条目数一致
- **失败时诚实报告**：如果某个 stage 无法通过（如连续 REWORK 超过 2 次、Gate HALT），必须明确报告原因，不强行推进
