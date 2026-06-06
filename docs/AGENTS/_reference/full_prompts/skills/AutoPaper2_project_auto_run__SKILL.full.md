---
name: AutoPaper2_project_auto_run
description: >
  AutoPaper2 项目级端到端自动运行 Skill。
  当用户要求从头到尾自动执行、全自动推进项目、或继续自动运行时触发。
  主 Agent 负责循环编排：读取状态 → 委派 subagent 执行 stage → 触发 review → 处理 verdict → 推进或回溯。
argument-hint: [项目名/路径] [可选：起始stage]
skill_role: orchestrator
---

> **ORCHESTRATOR MANIFEST ⚠️ 绝对不可违反**
>
> **你（当前主 Agent）的身份是 ORCHESTRATOR / CONDUCTOR。**
> **无论本 Skill 下文描述了多么详细的执行步骤，你绝对不得亲自执行任何 Stage 内容工作或 Review 工作。**
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

# Project Auto Run — 端到端自动编排执行

## 触发条件

当用户说以下任意一种表述时触发本 Skill：

- "自动运行"
- "从头到尾"
- "auto-run"
- "全自动执行"
- "继续自动运行"
- "帮我自动推进"
- "自动完成剩余部分"

**不触发**的情况：
- 用户明确指定了某个具体 stage 的内容修改（应路由到对应模块 Skill 或 backtrack Skill）
- 用户说 "进入 M3"（这是单模块启动，应路由到 project_router 或 M3 Skill）

## 默认行为 vs 显式项目指定

### 默认：复用当前活跃项目

如果用户没有指定项目，默认复用当前活跃项目：

```bash
cd {framework_root}
python scripts/state_manager.py status
```

### 显式项目指定

如果用户明确提供了项目名称或路径，先定位项目，再执行自动运行。

---

## 项目创建配置清单（Project Creation Checklist）

> **重要原则**：若自动运行前需要创建新项目，必须**一次性**收集并配置以下参数。后续 M2-M6 模块的执行依赖这些初始配置，**不建议在创建后补填**。

### 1. 基础信息（必填）

| 参数 | CLI 标志 | 说明 | 示例 |
|------|---------|------|------|
| topic | 位置参数 1 | 研究主题（一句话描述） | `"Semantic Communication for Images"` |
| display_name | 位置参数 2 | 项目显示名称（用于生成目录名） | `"SemCom-Image-RL"` |
| keywords | `--keywords` | 3-5 个关键词，影响 M1S02 搜索方向 | `"semantic communication, RL, image"` |

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
- **长时间下载/上传/训练前置任务** → M3S02 必须写入 `experiments/logs/m3s02_longrun_ledger.md`，记录命令、日志、轮询/等待、恢复命令和权限状态；不得因文件大或耗时长跳过。

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
  "Semantic Communication for Images" \
  "SemCom-Image-RL"

# 标准创建（含投稿目标和关键词）
python scripts/state_manager.py create \
  "Semantic Communication for Images" \
  "SemCom-Image-RL" \
  neurips \
  --keywords "semantic communication, reinforcement learning, image transmission" \
  --foundation "DeepJSCC: Deep Joint Source-Channel Coding" \
  --reference "ADJSCC, SwinJSCC"

# 完整配置（SSH 远程，已有密钥）
python scripts/state_manager.py create \
  "Semantic Communication for Images" \
  "SemCom-Image-RL" \
  neurips \
  --keywords "semantic communication, reinforcement learning, image transmission" \
  --env-mode ssh \
  --ssh-host 10.10.9.210 \
  --ssh-user zhouzhehao \
  --ssh-port 30011 \
  --ssh-auth-method key \
  --ssh-workspace "~/AutoPaper2/projects/SemCom-Image-RL" \
  --ssh-conda-env "semcom-rl" \
  --python-version 3.10 \
  --cuda-version 12.1

# 完整配置（SSH 远程，只有密码 → M3S02 自动部署密钥）
python scripts/state_manager.py create \
  "Semantic Communication for Images" \
  "SemCom-Image-RL" \
  neurips \
  --keywords "semantic communication, reinforcement learning, image transmission" \
  --env-mode ssh \
  --ssh-host 10.10.9.210 \
  --ssh-user zhouzhehao \
  --ssh-port 30011 \
  --ssh-auth-method password \
  --ssh-password "your_password_here" \
  --ssh-workspace "~/AutoPaper2/projects/SemCom-Image-RL" \
  --python-version 3.10 \
  --cuda-version 12.1
```

---

## 控制工作流

```
Phase 0: 项目定位与状态读取
  → 显式指定项目 或 复用当前活跃项目
  → 读取 state/pipeline_state.yaml
  → 确认 current_stage / status / module
  → 检查 stale_stages（如有则优先处理）
  → 检查 gate_re_review（如有则优先处理）
  → 若用户指定了起始 stage → 从该 stage 开始（需验证前置依赖）

Phase 1: 自动执行循环（WHILE 未到达终点或用户未中断）

  Step 1: 获取下一步计划
    → 调用 conductor.get_next_action()
    → 或直接调用脚本生成委派包:
       python scripts/state_manager.py dispatch next --write
    → 可能的 action：
       - EXECUTE_STAGE → 执行当前 stage
       - RE_EXECUTE → 回溯后重新执行
       - GATE → 执行 Gate 审查
       - WAIT_USER → 模块完成，等待用户确认

  Step 2: 执行 Stage（非 Gate）
    → 先生成 stage dispatch packet:
       python scripts/state_manager.py dispatch stage <stage> --write
    → 从 dispatch packet 中读取 agent 类型、AGENT.md 路径、输入文档、输出路径
    → 创建对应 subagent 执行：
       - M1S01-M1S02 → Survey Agent subagent
       - M1S03-M1S05 → Ideation Agent subagent
       - M2S01-M2S05 → Method Agent subagent
       - M3S02-M3S04 → Experiment Agent subagent
         * M3S02 必须产出 `experiments/logs/m3s02_longrun_ledger.md`
       - M3S05/M4S01/M4S02/M4S04/M5S01 → Analysis Agent subagent
       - M5S02-M5S08/M5S09 → Writing Agent subagent
       - M6S01-M6S02 → Submission Agent subagent
       - M6S01 internal review → `critic/m6_internal_peer_review/AGENT.md` reviewer subagent; must reach ≥8/10 before M6S02
       - M6S03/M6S04/M6S06 → Rebuttal Agent subagent
       - M6S05 → 先用 scripts/m6_action_router.py 生成 routing plan，再按 routing plan 路由到对应 subagent
    → subagent 完成后，验证产出文件存在且非空
    → 若产出缺失 → 重试一次；仍失败 → HALT

  Step 3: Stage Review（如当前 stage 配置了 stage_checkers）
    → 先生成 review dispatch packets:
       python scripts/state_manager.py dispatch reviews <stage> --write
    → 并行创建独立 reviewer subagent（每个 checker 一个 subagent）
    → reviewer 读取对应 AGENT.md 和产出文件
    → reviewer 写入 review 文件到 knowledge/reviews/
    → 主 Agent 读取 review 文件提取 verdict
    → verdict 处理：
       - 全部 PASS → 调用 state_manager.py advance 推进
       - 任一 HALT → 暂停循环，报告原因，等待用户介入
       - 任一 BACKTRACK/REVISE/FIX/REWORK → 调用 Conductor.backtrack()，回到 Step 1（RE_EXECUTE）

  Step 4: Gate 审查（如 status == waiting_gate）
    → 先生成 gate dispatch packets:
       python scripts/state_manager.py dispatch gate <Gx> --write
    → 并行创建 Gate Critics subagent（如 G3: Method Critic + Evidence Critic）
    → Critics 读取对应 AGENT.md 和模块全部产出
    → Critics 写入 review 文件到 knowledge/reviews/
    → 主 Agent 调用 conductor.handle_gate_verdict()
    → verdict 处理：
       - 全部 PASS → 标记模块完成，输出 handoff，进入 WAIT_USER
       - 任一 HALT → 暂停循环，报告原因
       - 任一 BACKTRACK/REVISE/FIX → 调用 Conductor.backtrack()，回到 Step 1

  Step 5: 模块完成检查
    → 若模块最后一个 stage 完成且 Gate PASS：
       → 标记模块 completed
       → 生成 handoff_{from}_{to}.md
       → 输出进度摘要给用户
       → **默认暂停等待用户确认**（除非用户明确说 "继续自动运行到完成"）

Phase 2: 完成或暂停
  → 若全部 6 个模块完成 → 报告项目完成
  → 若用户中断 → 报告当前 stage 和状态，建议下一步
```

## 用户中断点

以下情况自动暂停循环，向用户发送进度报告并等待指令：

1. **Gate HALT**：某个 Gate 的 Critic 返回 HALT
2. **螺旋超限**：任一模块 spiral_count ≥ 10
3. **用户主动暂停**：用户说 "等一下"、"先别继续"、"暂停"
4. **模块完成**：每个模块完成后（默认行为，用户可覆盖）
5. **连续失败**：同一 stage 连续 2 次产出失败或 review 连续 2 次非 PASS
6. **M6S03 审稿等待**：外部审稿提交后等待邮件时（超时 3600 秒）

## Agent 调用规范

**Stage 执行 subagent**：
- 必须优先使用 `python scripts/state_manager.py dispatch stage <stage> --write` 生成任务包
- 每个 stage 由一个独立的执行 subagent 完成
- prompt 必须包含 dispatch packet 路径；packet 中已包含 AGENT.md 路径、输入文档路径（只传路径）、输出路径、backtrack_advice（如有）
- 工具集：ReadFile, WriteFile, Shell, WebSearch（按 Agent 类型）

**Review subagent**：
- 必须优先使用 `python scripts/state_manager.py dispatch reviews <stage> --write` 生成任务包
- 必须与执行 subagent 隔离（跨模型隔离）
- reviewer 只能读取原始文件路径，不能读取 executor 的摘要或转述
- 每个 reviewer 独立输出 verdict

**Gate Critic subagent**：
- 并行创建，各自独立执行
- 全部完成后由主 Agent 统一处理 verdict

## 状态管理规范

每完成一个 Stage 或 Gate，通过 `state_manager.py advance` 或 `Conductor.backtrack()` 更新状态：

```bash
# Stage 完成后推进
python scripts/state_manager.py advance <stage> <agent> <output_file>

# Gate 完成后推进（需 aggregate review 文件）
python scripts/state_manager.py advance <gate_stage> critic knowledge/reviews/<gate_id>_aggregate.md
```

**禁止**：
- 主 Agent 直接修改 `pipeline_state.yaml`
- 跳过 stage review 直接推进
- 在未通过 Gate 的情况下进入下一模块

## Checkpoint 与用户交互

以下节点向用户发送进度更新（非阻塞，继续执行，除非用户主动暂停）：

1. **模块启动时**: "开始自动执行 [模块]，共 [N] 个 stages。"
2. **每完成一个 Stage**: "[stage] 完成，等待 review..."
3. **Stage Review PASS**: "[stage] review 通过，推进到 [next_stage]。"
4. **Gate PASS**: "[gate] 通过，[模块] 完成。"
5. **发生回溯时**: "[stage] review 未通过，回溯到 [target_stage]（螺旋计数: [N]）。"
6. **模块完成**: "[模块] 完成。建议：进入 [下一模块] 或检查 handoff 文件。"
7. **项目完成**: "全部模块完成。最终投稿包位于 artifacts/。"

## Context Recovery

如果上下文被压缩：
1. 读取 `state/pipeline_state.yaml` → 确认 current_stage / status
2. 读取 `state/decision_log.md` 和 `state/spiral_log.md`
3. 检查 stale_stages 和 gate_re_review
4. 从当前 stage 继续执行循环（不重新执行已完成的 stage）

## Key Rules

- **项目定位优先**：自动运行前必须先定位项目
- **Stage 执行必须由 subagent 完成**：主 Agent 只负责读取状态和派发任务
- **Review 必须独立**：执行 Agent 与 Review Agent 不得由同一模型实例执行
- **Gate 必须全部 PASS**：任一 Critic 未通过都不得推进
- **模块完成后默认暂停**：不自动跨模块，除非用户明确授权
- **回溯后自动继续**：backtrack 完成后，自动进入 RE_EXECUTE，无需用户额外指令
- **螺旋上限强制停止**：spiral_count ≥ 10 时立即停止，建议人工介入
- **产出必须落盘**：每个 stage 和 review 都必须写入文件，不能只存在上下文中
- **失败时诚实报告**：stage 连续失败或 Gate HALT 时，明确报告原因，不强行推进
- **跨模型隔离必须遵守**：执行 Agent、Review Agent、Gate Critic 三者之间应尽可能隔离（参见 `docs/AGENTS/critic/cross_model_protocol.md`）
