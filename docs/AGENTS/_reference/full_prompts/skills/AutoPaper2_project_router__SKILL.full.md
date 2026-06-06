---
name: AutoPaper2_project_router
description: >
  AutoPaper2 项目级通用路由 Skill。
  当用户需要在指定项目中运行指定模块、切换项目、或定位到某个项目的某个 stage 时触发。
  负责项目定位、前置依赖检查、模块入口设置，然后将执行权交给对应模块级 Skill。
argument-hint: [项目名/路径] [模块名或stage]
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

# Project Router — 项目定位与模块路由

## 触发条件

当用户说以下任意一种表述时触发本 Skill：

- "运行 [项目] 的 [模块]"
- "进入 [项目] [模块]"
- "在 [项目] 中执行 [stage]"
- "切换到 [项目]"
- "继续 [项目] 的 [模块]"
- "打开 [项目]"
- "项目 [项目名]"

**不触发**的情况：
- 用户只说 "进入 M1/M2/M3" 且没有指定项目 → 复用当前活跃项目，应路由到对应模块 Skill（如 `AutoPaper2_m1_survey`）
- 用户只说 "开始一个新项目" → 路由到 `AutoPaper2_m1_survey`

## 默认行为 vs 显式项目指定

### 显式项目指定

如果用户明确提供了项目名称或路径：
- 名称模糊匹配：`projects/` 下查找包含该名称的目录
- 完整路径：直接使用
- 当前活跃项目：读取 `~/.spiral/current_project`

> **若用户要求创建新项目而非进入现有项目**：路由到 `AutoPaper2_m1_survey` Skill，并确保一次性收集完整的项目创建配置（参见该 Skill 中的「项目创建配置清单」）。必须提前配置投稿目标（venue）、执行环境（local/ssh、认证方式、GPU 需求）等参数，避免后续模块执行时缺失关键配置。
>
> **项目创建后会自动触发 Onboarding**：`spiral/project.py` 的 `create()` 方法会自动运行 `env_probe.py` 探测环境，并生成 `state/onboarding_checklist.md`。此时项目状态为 `onboarding_pending`，**必须等待用户补完配置后才能进入 M1**。

### 默认：复用当前活跃项目

如果用户没有指定项目，默认复用当前活跃项目：

```bash
cd {framework_root}
python scripts/state_manager.py status
```

## 控制工作流

```
Phase 0: 项目定位
  → 解析用户输入，提取项目标识和模块/stage
  → 若用户未指定项目 → 读取当前活跃项目
  → 若活跃项目不存在 → 列出 projects/ 下所有项目供用户选择
  → 验证项目目录存在且包含 state/pipeline_state.yaml

Phase 1: 状态诊断
  → 读取 state/pipeline_state.yaml
  → 确认当前 module / stage / status
  → 检查 spiral_count（如过高则预警）
  → 检查 stale_stages（如有则提示需要先处理）

Phase 2: 目标解析与依赖检查
  → 若用户指定了具体 stage（如 M3S03）：
     → 检查该 stage 是否在当前模块流程中可达
     → 若 target_stage < current_stage → 提示用户是否需要先回溯
  → 若用户指定了模块（如 M3）：
     → 调用 check_module_prerequisites(M3)
     → M2 未完成 → 提示先完成 M2
     → M2 已完成 → 获取模块首 stage（M3S02）
  → 若用户未指定模块/stage：
     → 返回项目当前状态摘要，等待用户下一步指令

Phase 3: 模块入口设置
  → 调用 python scripts/state_manager.py run-module <module>
  → 设置 current.stage = 模块首 stage
  → 标记模块状态为 in_progress

Phase 4: 路由到模块 Skill
  → M1 → 触发 AutoPaper2_m1_survey
  → M2 → 触发 AutoPaper2_m2_method_design
  → M3 → 触发 AutoPaper2_m3_experiment
  → M4 → 触发 AutoPaper2_m4_deep_analysis
  → M5 → 触发 AutoPaper2_m5_writing
  → M6 → 触发 AutoPaper2_m6_submission_review
  → 将项目路径作为参数传递给模块 Skill
  → 对每个即将执行的 stage，先生成 dispatch packet:
     python scripts/state_manager.py dispatch stage <stage> --write
```

## 状态诊断规范

项目定位后，必须向用户输出状态摘要：

```
项目: [名称]
当前: [stage] ([module]) — [status]
已完成模块: [列表]
螺旋计数: M1:[N] M2:[N] M3:[N] M4:[N] M5:[N] M6:[N]
Stale stages: [列表或 "无"]
建议下一步: [根据当前状态自动生成]
```

## Agent 调用规范

**本 Skill 为主 Agent 编排层**：
- 不允许创建 Survey/Method/Experiment 等内容执行 subagent
- 只允许使用 Shell/ReadFile 读取状态和项目信息
- 路由决策由本 Skill 直接完成，无需 subagent
- 路由后必须先生成 dispatch packet，再把 packet path 交给对应模块 Skill 或 subagent

## Context Recovery

如果上下文被压缩：
1. 读取 `~/.spiral/current_project` 确认活跃项目
2. 读取 `state/pipeline_state.yaml` 恢复当前 stage
3. 重新执行 Phase 1 状态诊断

## Key Rules

- **项目定位优先**：任何涉及项目的指令必须先完成项目定位
- **前置依赖强制检查**：不允许跳过未完成的模块
- **Stale stages 需预警**：如果项目有 stale stages，必须在路由前提示用户
- **状态只读**：本 Skill 只读取状态，不直接修改 stage 产出文件
- **路由后移交控制权**：设置入口后，立即将后续执行交给对应模块 Skill
