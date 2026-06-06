---
name: AutoPaper2_m3_experiment
description: >
  AutoPaper2 Module 3 (Experiment Implementation & Execution) 全流程执行 Skill。
  当用户需要进入实验执行阶段时触发，包括：
  前置检查 (M2 完成状态) → M3S02 Dataset & Environment Review / Setup
  → M3S03 Baseline Result Review → M3S04 Main Experiment Result Review
  → M3S05 Result Validation & Evidence Packaging
  → Gate G3（Method + Evidence Critic）→ Handoff M3→M4。
  仅在用户明确指定进入 M3 或 M2 完成后建议进入 M3 时触发。
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

# M3 Experiment Implementation & Execution — 实验实现与执行全流程

执行 AutoPaper2 的 **Module 3: Experiment Implementation & Execution**，完成从代码实现到证据打包的完整实验流程。

## 触发条件

当用户说以下任意一种表述时触发本 Skill：

- "进入 M3"
- "开始实验"
- "运行实验"
- "M3 阶段"
- "实验执行"
- "experiment"
- "继续 M3"

**不触发**的情况：
- 用户明确说 "进入 M1/M2/M4/M5"（应路由到对应 Stage）
- 当前项目 M2 尚未完成（应提示用户先完成 M2）

## 默认行为 vs 显式项目指定

### 默认：复用当前项目

如果用户没有明确指定项目路径，默认复用当前活跃项目（`projects/` 下最新的项目目录）：

```bash
cd {framework_root}
python scripts/state_manager.py status
```

检查 `state/pipeline_state.yaml`：
- 如果 M2 已完成（`M2.status == completed`）→ 正常启动 M3
- 如果 M2 未完成 → 提示用户先完成 M2
- 如果 M3 已在进行中 → 从当前 stage 继续

### 显式：进入指定项目

如果用户明确指定了现有项目，则定位到该项目，检查当前状态：
- 如果项目已完成 M3 → 询问是否回溯重新执行
- 如果项目在 M3 中间 → 从当前 stage 继续
- 如果项目尚未启动 M3 → 检查 M2 是否完成，然后正常启动

## 执行前检查清单

在启动 M3 之前，必须确认：

- [ ] 项目已定位（`projects/{name}-{timestamp}/` 存在）
- [ ] `state/pipeline_state.yaml` 可读
- [ ] M2 状态为 `completed`（或 `module_completed`）
- [ ] `knowledge/handoff_M2_M3.md` 存在且非空
- [ ] 当前 stage 为 M3S02 或用户明确要求重新执行 M3
- [ ] M3 螺旋计数 < 10（`spiral_count.M3 < 10`）

## 控制工作流

```
Phase 0: 进入 M3 前置检查
  → 检查 M2 状态是否为 completed
  → 读取 handoff_M2_M3.md
  → 检查 M2 产出完整性（M2S03-M2S05/M3S01 或项目内等价产物）
  → 加载 AGENT.md: docs/AGENTS/experiment/AGENT.md
  → 设置 pipeline_state: M3S02 in_progress

Phase 1: M3S02 Dataset & Environment Review / Setup
  → Experiment Agent 执行
  → 产出: knowledge/M3/M3S02_implementation.md + experiments/src/ + experiments/configs/ + experiments/requirements.lock + experiments/configs/sandbox_profile.yaml + experiments/configs/resource_plan.yaml + （如多资源）experiments/configs/m3_task_queue.yaml + experiments/configs/m3_task_allocation.yaml + experiments/logs/m3s02_longrun_ledger.md
  → Stage Review: m3_dataset_env_review → knowledge/reviews/M3S02_dataset_env_review.md
  → Review verdict 必须为 PASS；否则 Conductor 调用 backtrack() 后，**必须重新调用 Experiment Agent subagent 修正/重新执行 M3S02；主 agent 禁止直接修改**
  → Conductor advance: M3S02 → M3S03

Phase 2: M3S03 Baseline Result Review
  → Experiment Agent 执行
  → 产出: knowledge/M3/M3S03_baseline_lock.md + experiments/baselines/*/metric_contract.yaml
  → Stage Review: m3_baseline_result_review → knowledge/reviews/M3S03_baseline_result_review.md
  → Review verdict 必须为 PASS；否则 Conductor 调用 backtrack() 后，**必须重新调用 Experiment Agent subagent 修正/重新执行 M3S03；主 agent 禁止直接修改**
  → Conductor advance: M3S03 → M3S04

Phase 3: M3S04 Main Experiment Result Review
  → Experiment Agent 执行
  → 产出: knowledge/M3/M3S04_main_experiment.md + experiments/results.tsv + experiments/runs/ + 每个正式 run 的 resource_monitor.csv + runtime watchdog 记录 + （如多资源）每个 run 的 resource_id/server_id/sync 记录
  → 对预计超过 2 小时的正式 run，Experiment Agent 必须周期巡检（默认每 4 小时，最长不超过 6 小时），读取训练日志、metric 曲线、resource_monitor 和 watchdog 告警；watchdog 只告警不终止，是否继续/修复/早停/回溯由 Experiment Agent 判断并记录
  → Stage Review: m3_main_result_review → knowledge/reviews/M3S04_main_result_review.md
  → Review verdict 必须为 PASS；否则 Conductor 调用 backtrack() 后，**必须重新调用 Experiment Agent subagent 修正/重新执行 M3S04；主 agent 禁止直接修改**
  → Conductor advance: M3S04 → M3S05

Phase 4: M3S05 Result Validation & Evidence Packaging
  → Analysis Agent 执行
  → 产出: knowledge/M3/M3S05_result_validation.md + experiments/artifacts/main_experiment/
  → Stage Review: m3_result_validation_review → knowledge/reviews/M3S05_result_validation_review.md
  → Review verdict 必须为 PASS；否则 Conductor 调用 backtrack() 后，**必须重新调用 Analysis Agent subagent 修正/重新执行 M3S05；主 agent 禁止直接修改**
  → Conductor advance after review PASS: M3S05 → Gate G3

Phase 5: Gate G3 审查
  → Method Critic 审查 → G3_method_review.md
  → Evidence Critic 审查 → G3_evidence_review.md
  → 综合 verdict:
     → 全部 PASS → 进入 Handoff
     → 任一 REVISE / BACKTRACK / FIX → **Conductor 调用 backtrack() 更新状态后，必须调用对应 subagent（Experiment Agent / Analysis Agent / Method Agent）重新执行目标 stage；主 agent 绝对禁止直接修改 stage 文件**
     → 任一 HALT → 终止 M3

Phase 6: Handoff & 完成
  → 产出: knowledge/handoff_M3_M4.md
  → 标记 M3 模块 completed
  → 报告完成状态，建议下一步（进入 M4）
```

## Agent 调用规范

**Experiment Agent**:
- 使用 subagent 执行
- Prompt 必须包含：
  - 完整读取 `docs/AGENTS/experiment/AGENT.md`
  - 当前 stage（M3S02-M3S04）
  - 上游输入文档路径
  - 产出路径
  - 工具集: ReadFile, WriteFile, Shell, WebSearch
  - Stage review 由独立 reviewer 执行，Experiment Agent 不兼任 reviewer
  - **如果是回溯后的重新执行，必须完整传递 `backtrack_advice`（blocking_reason, required_fix, success_criteria, rebuild_mode, evidence_paths 等）**
- **强制规则**：主 agent 不得直接修改 Experiment Agent 的产出文件；所有修正必须通过重新调用 Experiment Agent subagent 完成。

**Analysis Agent** (M3S05):
- 使用 subagent 执行
- Prompt 必须包含：
  - 完整读取 `docs/AGENTS/analysis/AGENT.md`
  - 上游输入文档路径
  - 产出路径
  - 工具集: ReadFile, WriteFile, Shell
  - M3S05 的 Stage Review 必须由独立 `m3_result_validation_review` reviewer 执行，Analysis Agent 不兼任 reviewer
  - **如果是回溯后的重新执行，必须完整传递 `backtrack_advice`**
- **强制规则**：主 agent 不得直接修改 Analysis Agent 的产出文件；所有修正必须通过重新调用 Analysis Agent subagent 完成。

**Gate G3 Critics** (并行执行):
- Method Critic: 读取 `docs/AGENTS/critic/method/AGENT.md`（复用 G2，审查对象更新为 M3 实现）
- Evidence Critic: 读取 `docs/AGENTS/critic/evidence/AGENT.md`（新增）

**Stage Review Agents**:
- M3S01: `docs/AGENTS/critic/m3_main_experiment_design_review/AGENT.md` → `knowledge/reviews/M3S01_main_experiment_design_review.md`
- M3S02: `docs/AGENTS/critic/m3_dataset_env_review/AGENT.md` → `knowledge/reviews/M3S02_dataset_env_review.md`
- M3S03: `docs/AGENTS/critic/m3_baseline_result_review/AGENT.md` → `knowledge/reviews/M3S03_baseline_result_review.md`
- M3S03 audit: `docs/AGENTS/critic/m3_baseline_lock_audit/AGENT.md` → `knowledge/reviews/M3S03_baseline_lock_audit.md`
- M3S04: `docs/AGENTS/critic/m3_main_result_review/AGENT.md` → `knowledge/reviews/M3S04_main_result_review.md`
- M3S05: `docs/AGENTS/critic/m3_result_validation_review/AGENT.md` → `knowledge/reviews/M3S05_result_validation_review.md`

**Stage Review Execution Rule**:
- Stage Review 必须作为独立 subagent 执行，不得由 Experiment Agent / Analysis Agent 兼任
- Reviewer 只能读取 Conductor 提供的文件路径，不能读取 Executor 的摘要或转述
- Reviewer 必须输出到对应 review 文件，并且 verdict 必须是显式 `PASS` 才能推进
- Reviewer 若输出 REVISE / BACKTRACK / FIX，必须写出 `target_stage`、`blocking_reason`、`required_fix`、`success_criteria`、`evidence_paths`、`rebuild_mode`、`rerun_scope`、`handoff_updates`
- Conductor 回溯后必须从 `target_stage` 继续推进，所有被标记为 stale 的 downstream stage 需要按顺序重跑并重新审查；无依赖关系的 stage 可以保留
- `rebuild_mode=incremental_replay` 时可参考旧 downstream 文件减少冗余，但必须重新核对当前上游输入；`rebuild_mode=full_regenerate` 时旧文件只能作为历史证据，不作为新正文模板

## 关键原则

1. **数据集获取铁律（M3S02）**: **真实数据是唯一合法输入**。绝对禁止用仿真/合成/随机数据替代真实数据集。大数据集同样必须尝试下载或传输。无法自动获取时必须生成报告阻塞等待用户，严禁绕过。
2. **长任务等待与权限 Ledger（M3S02）**: 任何长时间下载、上传、远程环境创建、依赖安装、checkpoint 获取或 smoke run 都必须记录到 `experiments/logs/m3s02_longrun_ledger.md`，包含命令、状态、日志路径、等待/轮询策略、恢复命令、权限/批准状态和完成标准；禁止以"太大/太慢/需要等"为由跳过。
3. **Sandbox / Container Profile（M3/M4）**: `execution.sandbox.enabled` 必须为 true，且必须生成 `experiments/configs/sandbox_profile.yaml`，记录网络、文件系统、凭证、资源限制和可复现性边界；禁止无隔离运行 LLM 生成实验代码。
4. **Resource Utilization Contract（M3S02/M3S04）**: 必须生成 `experiments/configs/resource_plan.yaml`，把可见 GPU/CPU 转成 DDP/单卡/CPU 并行/任务并行策略；如果存在多张卡、多个服务器或 local+ssh 混合资源，必须在 `resource_plan.yaml.resource_pool` 中列出资源池，并生成 task queue/allocation，把可并行的独立任务合理分配到资源；M3S04 每个正式 run 必须记录 `resource_monitor.csv`，低利用率必须优化或说明不可优化原因。
5. **Runtime Watchdog（M3S04）**: 预计超过 2 小时的正式 run 必须写入 `experiments/logs/runtime_events.jsonl` 和 `experiments/runs/<run_id>/watchdog_checks.jsonl`；出现 NaN/Inf、不收敛、OOM、异常退出、资源长期低利用率或早停候选时，写入 `watchdog_alerts.jsonl`，由 Experiment Agent 读取证据后决定 `continue` / `fix_and_rerun` / `early_stop` / `backtrack_request`，不得由脚本自动结束。
6. **Comparator-First（M3S03）**: 优先 attach/import/verify-local-existing，非必要不 reproduce。Baseline 若依赖预训练权重，必须主动搜索并获取 checkpoint（GitHub Releases、README、HuggingFace、自动下载等），禁止跳过或用随机初始化替代。
7. **Baseline 只读（M3S04）**: 主实验阶段 baseline 代码只读，确保比较公平
8. **Run Contract 锁定（M3S04）**: 实验开始前明确记录问题、假设、指标、停止条件、watchdog 巡检间隔和告警处置策略
9. **Evidence Ladder（M3S04）**: 明确区分 minimum/solid/maximum，不超前追求
10. **诚实性（M3S05）**: KEEP 是唯一通过决策，结果不支持假设时必须 FIX/BACKTRACK
11. **负面结果记录**: 所有迭代尝试（包括失败的）都必须记录
12. **回溯连续性**: 前序 stage 被修改后，后续依赖它的实验上下文必须重新生成；局部修复可增量复用，方向偏差大时必须全量重建

## Handoff 文档

M3 完成后必须产出 `knowledge/handoff_M3_M4.md`，核心内容：
- 已完成的工作摘要
- 关键决策记录（实现框架、baseline 路径、最终配置、M3S05 决策）
- 传递给 M4 的核心信息（固定 seed=42 主实验结果、假设验证状态、evidence artifact 路径、关键发现、已知限制、建议的 M4 分析方向）
- 回溯历史

## 状态管理规范

每完成一个 Stage，必须更新 `state/pipeline_state.yaml`。

```python
from spiral.state import PipelineState
from pathlib import Path

proj = Path("projects/XXX")

state = PipelineState(proj)
state.record_completion("M3S02", "experiment", Path("knowledge/M3/M3S02_implementation.md"))
state.set_stage("M3S03", "in_progress")
```

回溯后：
- `stale_stages` 代表需要重新跑的 downstream stage
- 被重新完成的 stale stage 必须自动清除 stale 标记
- `gate_re_review` 中的对应 gate 只有在重新通过后才能清除

## 质量门控

| 节点 | 检查项 | 失败处理 |
|------|--------|---------|
| M3S02 完成后 | 数据集、环境、依赖、硬件信息、sandbox profile、resource plan 完整；多资源场景下 task allocation 完整；review PASS | REVISE / BACKTRACK → M3S02 |
| M3S03 完成后 | baseline 本地验证、metric contract、smoke test、review PASS | REVISE / BACKTRACK → M3S03 / M3S02 |
| M3S04 完成后 | `results.tsv` 完整、固定 seed=42、baseline 对比、resource_monitor 完整、runtime watchdog 巡检/告警/Agent 决策记录完整、review PASS | REVISE / BACKTRACK → M3S04 / M3S03 |
| M3S05 完成后 | 统计分析、最终决策、回溯建议完整 | FIX / BACKTRACK → M3S04 / M3S03 / M3S02 |
| Gate G3 | Method Critic + Evidence Critic 双 PASS | BACKTRACK → 指定 M3 stage |

## Checkpoint 与用户交互

以下节点默认向用户发送进度更新（非阻塞，继续执行）：

1. **M3S02 完成后**: "实验环境与数据审查完成。"
2. **M3S03 完成后**: "baseline 已锁定，metric contract 已确认。"
3. **M3S04 完成后**: "主实验已完成，结果表与运行记录已落盘。"
   - 长跑期间如果 watchdog 发现 `critical` / `warning` / `early_stop_candidate`，必须立即发送非阻塞进度反馈，说明 run_id、告警类型、证据路径和当前 Agent 决策；反馈后继续执行或按决策修复，不把告警本身当作 stage 完成。
4. **M3S05 完成后**: "结果验证完成，已生成回溯或交接建议。"
5. **Gate G3 完成后**: "G3 审查完成，准备输出 M3→M4 交接。"
6. **M3 完成后**: "M3 完成，已生成 handoff_M3_M4，建议进入 M4。"

如果用户要求暂停或介入，在下一个 Checkpoint 停止并等待用户指令。

## 输出协议

M3 的标准输出由以下文件构成：
- `knowledge/M3/M3S02_implementation.md`
- `knowledge/M3/M3S03_baseline_lock.md`
- `knowledge/M3/M3S04_main_experiment.md`
- `knowledge/M3/M3S05_result_validation.md`
- `knowledge/reviews/M3S02_dataset_env_review.md`
- `knowledge/reviews/M3S03_baseline_result_review.md`
- `knowledge/reviews/M3S04_main_result_review.md`
- `knowledge/handoff_M3_M4.md`
- `experiments/configs/sandbox_profile.yaml`
- `experiments/logs/m3s02_longrun_ledger.md`
- `experiments/logs/runtime_events.jsonl`
- `experiments/results.tsv`
- `experiments/runs/`
- `experiments/artifacts/main_experiment/`

补充规则：
- `results.tsv` 记录所有尝试，不能只留最优结果
- `experiments/runs/` 保存原始日志、配置、曲线、`resource_monitor.csv`、`watchdog_checks.jsonl` 和失败记录
- Watchdog 告警不得自动终止实验；必须在 M3S04 正文记录 Agent 读取证据后的继续/修复/早停/回溯判断
- `knowledge/M3/` 保存阶段性结论，`knowledge/reviews/` 保存独立审查结论
- 默认输出语言为中文，除非用户指定英文

## Context Recovery

如果上下文被压缩或 session 中断，恢复流程：

1. 重新读取 `docs/AGENTS/experiment/AGENT.md`
2. 重新读取 `docs/07_MD_PROTOCOL.md`
3. 读取 `state/pipeline_state.yaml`
4. 读取 `state/decision_log.md` 和 `state/spiral_log.md`
5. 读取 `knowledge/M3/` 下最近的 stage 文件
6. 读取 `knowledge/reviews/` 下最近的 M3 review
7. 读取 `experiments/results.tsv` 和 `experiments/runs/`
8. 读取 `experiments/logs/runtime_events.jsonl` 和最近 run 的 `watchdog_checks.jsonl` / `watchdog_alerts.jsonl`
9. 从当前 stage 继续执行，不跳过被标记为 stale 的 stage

**CLI 辅助命令**：
```bash
# 查看当前项目状态
python scripts/state_manager.py status

# 查看当前 stage 的自动执行计划
python scripts/state_manager.py auto-stage M3S02

# 自动运行当前模块
python scripts/state_manager.py auto-module M3
```

## Key Rules

- **M3S02 先搭环境再跑实验**：必须明确本地或 SSH 执行模式，并记录依赖锁定
- **长任务不可跳过**：下载、上传、依赖安装、checkpoint 获取和 smoke run 必须记录 ledger，等待/恢复/权限状态必须可审计
- **长跑实验必须巡检**：M3S04 长时间训练必须有 runtime watchdog 或等价机制；发现 NaN/Inf、不收敛、资源低利用率或早停候选时，必须告警并由 Agent 决定下一步
- **M3S03 先锁 baseline 再进入主实验**：baseline 必须本地验证，不能直接引用论文数值
- **M3S04 只做实验与记录**：不做最终分析裁决，不修改 baseline 代码
- **M3S05 由 Analysis Agent 执行**：Experiment Agent 不兼任结果分析
- **Stage Review 必须独立**：M3S02-M3S04 的 review 不得由执行 agent 自审
- **回溯必须连续**：前序 stage 被改动后，所有依赖它的 downstream stage 必须重跑
- **无关 stage 可保留**：没有依赖关系的 stage 不必重写
- **失败必须诚实记录**：包括 baseline 不稳、主实验不优、统计不显著
- **跨模型隔离必须遵守**：Experiment Agent 与 Stage Review Agent / Gate Critic 不得由同一模型实例执行（参见 `docs/AGENTS/critic/cross_model_protocol.md`）
