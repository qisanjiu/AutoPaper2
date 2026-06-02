---
name: AutoPaper2_project_backtrack
description: >
  AutoPaper2 项目级回溯与修订 Skill。
  当用户需要回溯到某个 stage、重新执行某个 stage、修订产出、或根据意见回退时触发。
  主 Agent 只做编排；stage 选择、回溯决策、重新执行均由 subagent 完成。
argument-hint: [项目名/路径] [stage或回溯意见]
skill_role: orchestrator
---

# Project Backtrack — 项目级回溯与修订

## 触发条件

当用户说以下任意一种表述时触发本 Skill：

- "回溯到 [stage]"
- "重新执行 [stage]"
- "修订 [stage]"
- "回退到 [stage]"
- "revise [stage]"
- "[stage] 需要重做"
- "方法有问题，回退"
- "结果不对，回到 [stage]"
- "重新跑 [stage]"

**不触发**的情况：
- 用户说 "进入 M2"（这是正常模块切换，应路由到 project_router 或对应模块 Skill）
- 用户说 "开始一个新项目"（路由到 M1 Skill）

## 默认行为 vs 显式项目指定

### 默认：复用当前活跃项目

如果用户没有指定项目，默认复用当前活跃项目：

```bash
cd {framework_root}
python scripts/state_manager.py status
```

### 显式项目指定

如果用户明确提供了项目名称或路径，先定位项目，再执行回溯。

## 控制工作流

```
Phase 0: 项目定位
  → 显式指定项目 或 复用当前活跃项目
  → 读取 state/pipeline_state.yaml 确认当前 stage / status / spiral_count / stale_stages

Phase 1: 意图解析
  → 用户明确指定了 target_stage？→ 进入 Phase 3
  → 用户只给出意见/问题（如 "方法设计有问题"、"baseline 不公平"）？→ 进入 Phase 2
  → 用户说 "重新执行当前 stage"？→ target_stage = current_stage，进入 Phase 3

Phase 2: Backtrack Planner subagent 分析（当用户未指定 stage 时）
  → 使用 subagent 执行，prompt 必须包含：
     - 完整读取 docs/AGENTS/conductor/AGENT.md
     - 完整读取 docs/07_MD_PROTOCOL.md
     - 当前项目路径、当前 stage、current_status
     - spiral_count 各模块计数
     - stale_stages 列表
     - 最近的 stage 产出文件路径（从 pipeline_state history 读取）
     - 最近的 review / gate 产出路径（从 knowledge/reviews/ 读取）
     - 用户给出的回溯意见/问题描述
  → Backtrack Planner subagent 产出（保存到 state/backtrack_planner_latest.md）：
     - recommended_target_stage（必须具体到 stage，如 M2S03）
     - blocking_reason
     - required_fix
     - success_criteria
     - rebuild_mode（incremental_replay / full_regenerate）
     - evidence_paths
     - rerun_scope
     - handoff_updates
  → **主 Agent 不得自行选择 stage，必须采纳 subagent 的推荐**
  → 若 subagent 推荐跨模块回溯（如从 M4 回到 M2），需额外提示用户确认

Phase 3: 状态回溯（Conductor 编排）
  → 确定 from_stage = current_stage（从 pipeline_state 读取）
  → 确定 to_stage = 用户指定 或 Backtrack Planner 推荐
  → 确定 reason = 用户描述 或 Backtrack Planner 的 blocking_reason
  → 组装 backtrack_advice：
     ```python
     from spiral.conductor import Conductor
     conductor = Conductor(project_root)
     result = conductor.backtrack(
         from_stage=from_stage,
         to_stage=to_stage,
         reason=reason,
         direction=backtrack_planner_output.get("required_fix", ""),
         advice=backtrack_planner_output,
     )
     ```
  → 检查 result["ok"]：
     → False（如螺旋超限）→ 报告错误，停止回溯，建议人工介入
     → True → 继续
  → **主 Agent 不得直接修改任何 knowledge/ 或 drafts/ 下的 stage 产出文件**
  → 回溯后先生成修订 dispatch packet:
     python scripts/state_manager.py dispatch stage <target_stage> --write

Phase 4: 重新执行（与正常回溯完全一致）
  → 调用 conductor.get_next_action() 获取下一步计划
  → 若 action == "RE_EXECUTE"：
     → 先读取/生成 dispatch packet，再读取其中的 agent 类型、AGENT.md 路径、输入文档、输出路径、backtrack_advice
     → 创建对应 subagent 重新执行 target_stage（Survey/Method/Experiment/Analysis/Writing Agent）
     → subagent prompt 必须包含 backtrack_advice 全部字段
     → **主 Agent 不得代替 subagent 修改内容**
  → 若用户未要求立即执行：
     → 报告回溯完成，告知用户可从 target_stage 继续（使用 auto-stage 或手动推进）

Checkpoint 与用户交互
  1. Phase 2 完成后（如调用了 Planner）:
     "Backtrack Planner 分析完成，建议回溯到 [target_stage]，原因：[摘要]。"
  2. Phase 3 完成后:
     "已回溯 [from] → [to]。Spiral count: [N]。Stale stages: [列表]。Rebuild mode: [mode]。"
  3. 如进入 Phase 4:
     "开始重新执行 [target_stage]。"
```

## Backtrack Planner subagent 规范

**subagent 类型**: `explore`（先读取分析）或 `coder`（如需运行脚本验证）

**强制规则**：
- Planner 只能读取文件，不能修改任何 stage 产出
- Planner 的推荐必须基于实际文件内容，不能基于假设
- 如果用户意见指向的问题在当前 stage 之前就已存在，Planner 必须推荐回溯到最早出现该问题的 stage
- Planner 必须考虑 spiral_count：若目标模块已达 10 次回溯，应建议 HALT 而非继续回溯

## 状态回溯规范

使用 Python 脚本统一调用 Conductor：

```python
from spiral.conductor import Conductor
from pathlib import Path

proj = Path("projects/XXX")
conductor = Conductor(proj)

result = conductor.backtrack(
    from_stage="M4S02",
    to_stage="M2S03",
    reason="M4S02 的 claim-carrying slice 缺乏 literature basis",
    direction="重新设计消融实验，补充文献依据",
    advice={
        "target_stage": "M2S03",
        "blocking_reason": "...",
        "required_fix": "...",
        "success_criteria": "...",
        "rebuild_mode": "full_regenerate",
        "rerun_scope": "重新执行 M2S03-M2S06 及 M4S01-M4S04",
        "evidence_paths": ["knowledge/M4/M4S02_analysis_experiment_design.md"],
        "handoff_updates": ["更新 handoff_M2_M3 中的消融设计摘要"],
    }
)
```

**禁止**：
- 直接修改 `pipeline_state.yaml`（必须通过 Conductor API）
- 直接删除或修改 `knowledge/`、`drafts/`、`experiments/` 下的任何文件
- 在未清除 stale 标记的情况下跳过 stage 执行

## Context Recovery

如果上下文被压缩：
1. 读取 `state/pipeline_state.yaml` → 确认当前 stage
2. 读取 `state/backtrack_planner_latest.md` → 恢复最近一次 Planner 产出
3. 读取 `state/decision_log.md` 和 `state/spiral_log.md`
4. 确认 stale_stages 和 backtrack_log
5. 从当前 stage 继续执行（如果是 RE_EXECUTE 状态）

## Key Rules

- **项目定位优先**：任何回溯指令必须先完成项目定位
- **Backtrack Planner 必须独立**：stage 选择不得由主 Agent 自行决定
- **Conductor 统一入口**：所有状态变更必须通过 `Conductor.backtrack()`，禁止绕过
- **主 Agent 不修改内容**：回溯后的文件修正必须由对应 subagent 完成
- **必须先生成 dispatch packet**：回溯 re-execute 不能只靠口头 prompt，必须落盘到 `state/dispatch/`
- **rebuild_mode 必须传递**：subagent 必须按 full_regenerate 或 incremental_replay 规则执行
- **螺旋上限预警**：目标模块 spiral_count ≥ 10 时，必须停止并建议人工介入
- **Stale stages 不可跳过**：被标记为 stale 的 downstream stage 必须重新执行并重新审查
- **跨模型隔离必须遵守**：Backtrack Planner 与后续重新执行的 Agent 不得由同一模型实例执行（参见 `docs/AGENTS/critic/cross_model_protocol.md`）
