---
name: AutoPaper2_m4_deep_analysis
description: >
  AutoPaper2 Module 4 (Deep Analysis) 全流程执行 Skill。
  当用户需要进入深度分析阶段时触发，包括：
  前置检查 (M3 完成状态) → M4S01 Post-Experiment Audit & Findings Consolidation
  → M4S02 Deep Analysis Experiment Design → M4S03 Deep Analysis Experiment Execution
  → M4S04 Analysis Results Integration & Evidence Packaging
  → Gate G4（Logic + Evidence + Novelty Critic）→ Handoff M4→M5。
  仅在用户明确指定进入 M4 或 M3 完成后建议进入 M4 时触发。
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

# M4 Deep Analysis — 深度分析与证据精炼全流程

执行 AutoPaper2 的 **Module 4: Deep Analysis**，完成从实验后审计到证据打包的完整深度分析流程。

## 触发条件

当用户说以下任意一种表述时触发本 Skill：

- "进入 M4"
- "深度分析"
- "分析实验"
- "消融实验"
- "M4 阶段"
- "deep analysis"
- "继续 M4"

**不触发**的情况：
- 用户明确说 "进入 M1/M2/M3/M5"（应路由到对应 Stage）
- 当前项目 M3 尚未完成（应提示用户先完成 M3）

## 默认行为 vs 显式项目指定

### 默认：复用当前项目

如果用户没有明确指定项目路径，默认复用当前活跃项目（`projects/` 下最新的项目目录）：

```bash
cd {framework_root}
python scripts/state_manager.py status
```

检查 `state/pipeline_state.yaml`：
- 如果 M3 已完成（`M3.status == completed`）→ 正常启动 M4
- 如果 M3 未完成 → 提示用户先完成 M3
- 如果 M4 已在进行中 → 从当前 stage 继续

### 显式：进入指定项目

如果用户明确指定了现有项目，则定位到该项目，检查当前状态：
- 如果项目已完成 M4 → 询问是否回溯重新执行
- 如果项目在 M4 中间 → 从当前 stage 继续
- 如果项目尚未启动 M4 → 检查 M3 是否完成，然后正常启动

## 执行前检查清单

在启动 M4 之前，必须确认：

- [ ] 项目已定位（`projects/{name}-{timestamp}/` 存在）
- [ ] `state/pipeline_state.yaml` 可读
- [ ] M3 状态为 `completed`（或 `module_completed`）
- [ ] `knowledge/handoff_M3_M4.md` 存在且非空
- [ ] `knowledge/M3/M3S04_result_validation.md` 存在且决策为 KEEP
- [ ] 当前 stage 为 M4S01 或用户明确要求重新执行 M4
- [ ] M4 螺旋计数 < 10（`spiral_count.M4 < 10`）

## 控制工作流

```
Phase 0: 进入 M4 前置检查
  → 检查 M3 状态是否为 completed
  → 读取 handoff_M3_M4.md
  → 检查 M3S04 决策是否为 KEEP（非 KEEP 则拒绝启动 M4）
  → 加载 AGENT.md: docs/AGENTS/analysis/AGENT.md
  → 设置 pipeline_state: M4S01 in_progress
  → 标记 M4 模块状态为 in_progress

Phase 1: M4S01 Post-Experiment Audit & Findings Consolidation
  → Analysis Agent 执行
  → 数据质量审计（过拟合、泄漏、稳定性、可复现性）
  → 意外发现、边界条件、负面结果整理
  → Claim 初筛 + 分析战役规划草案 + 论文面向映射初稿
  → 产出: knowledge/M4/M4S01_other_findings.md
  → Stage Review: m4_findings_audit 审查
     → verdict: PASS → M4S02
     → verdict: REVISE → 回到 M4S01 修正
     → verdict: BACKTRACK → 回到 M4S01 重新审计
  → Conductor advance: M4S01 → M4S02

Phase 2: M4S02 Deep Analysis Experiment Design
  → Analysis Agent 执行
  → 消融/机制/鲁棒性/失败分析设计
  → 每个 slice 必须填写 Slice Evidence Contract
  → Comparability Contract + 执行信封审计
  → 产出: knowledge/M4/M4S02_analysis_experiment_design.md
  → Stage Review: m4_analysis_design_review 审查
     → verdict: PASS → M4S03
     → verdict: REVISE → 回到 M4S02 修正
     → verdict: BACKTRACK → 回到 M4S01 重新评估
  → Conductor advance: M4S02 → M4S03

Phase 3: M4S03 Deep Analysis Experiment Execution
  → Experiment Agent 执行（范围限定为 M4S02 已设计的分析实验）
  → 执行所有 feasible slice，记录 completed / partial / failed / blocked
  → 负面结果必须完整记录，禁止隐藏
  → 产出: knowledge/M4/M4S03_analysis_experiment.md
            + experiments/artifacts/analysis_experiment/
            + experiments/analysis_results.tsv
            + sandbox/container execution record referencing experiments/configs/sandbox_profile.yaml
  → Stage Review: m4_analysis_execution_review 审查
     → verdict: PASS → M4S04
     → verdict: REVISE → 回到 M4S03 补执行或修正记录
     → verdict: BACKTRACK → 回到 M4S02 重新设计
  → Conductor advance: M4S03 → M4S04

Phase 4: M4S04 Analysis Results Integration & Evidence Packaging
  → Analysis Agent 执行
  → 统计分析（显著性、效应量、置信区间）
  → Claim Ledger（supported / partially_supported / unsupported / deferred）
  → Insight Articulation + Limitations
  → 产出: knowledge/M4/M4S04_analysis_results.md
  → 产出: knowledge/handoff_M4_M5.md
  → Conductor advance: M4S04 → Gate G4

Phase 5: Gate G4 审查
  → Logic Critic 审查 → G4_logic_review.md
  → Evidence Critic 审查 → G4_evidence_review.md
  → Novelty Critic 审查 → G4_novelty_review.md
  → 综合 verdict:
     → 全部 PASS → 进入 Handoff
     → 任一 REVISE → 回溯到指定 M4 Stage
     → 任一 BACKTRACK → 回溯到 M4 内部 Stage 或跨模块到 M3/M2
     → 任一 HALT → 终止 M4

Phase 6: Handoff & 完成
  → 确认 handoff_M4_M5.md 已产出且完整
  → 标记 M4 模块 completed
  → 报告完成状态，建议下一步（进入 M5）
```

## Agent 调用规范

### Analysis Agent（M4S01, M4S02, M4S04）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/analysis/AGENT.md`
- 当前 stage（M4S01 / M4S02 / M4S04）
- 上游输入文档路径（handoff_M3_M4.md, M3S03-M3S04 产出, M4S01-M4S03 下游产出）
- 产出路径
- 如果是 M4S01，必须显式记录数据质量审计、意外发现、边界条件、负面结果，以及后续分析战役规划草案的文献/数据库依据、组件/Claim 分析矩阵、效率触发/豁免判断
- 如果是 M4S02，必须强调 Slice Evidence Contract 的必填字段
- 如果是 M4S02，必须要求 claim-carrying slice 填写 `analysis_type`、`literature_basis`、`baseline_inclusion`、`efficiency_required`、`paper_protocol_adaptation`、`evidence_criteria`
- 如果是 M4S02，必须包含 Component Claim Analysis Matrix 和 Paper Protocol Adaptation Table；若 `efficiency_required: yes`，必须设计 `analysis_type=efficiency` slice
- 如果是 M4S04，必须强调 Claim Ledger 的完整性和 Insight Articulation 的 "So what?" 要求
- 如果是 M4S04，必须把 unusable / unsupported / deferred 证据从主结论中剥离，并显式标记可用性、效率证据或豁免、论文协议适配摘要

**Analysis Agent subagent 工具集**: ReadFile, WriteFile, Shell, WebSearch

### Experiment Agent（M4S03）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/experiment/AGENT.md`
- 当前 stage（M4S03）
- M4S02 设计文档路径（作为执行蓝图）
- 明确范围限定：只执行 M4S02 已设计的分析实验，不设计新实验
- 产出路径
- 工具集: ReadFile, WriteFile, Shell, WebSearch

**关键约束**：
- M4S03 不得修改方法架构或核心算法
- M4S03 只能在 M4S02 设计的干预范围内执行实验
- 任何偏离 M4S02 设计的行为必须在产出中明确记录并说明原因
- 每个 analysis slice 必须记录 sandbox/container mode、命令、working dir、allowed writes、network policy、resource limits、log path
- `experiments/analysis_results.tsv` 必须包含 dataset/split/seed/config/run/artifact/resource 字段；若执行效率 slice，还必须记录参数量、时间、显存/内存、吞吐或 FLOPs/MACs 中的适用指标
- M4S03 必须沿用 M3S01 的 `experiments/configs/sandbox_profile.yaml` 或说明兼容 profile；不得无隔离运行 LLM 生成的分析脚本
- M4S03 的输出必须包含执行侧的初步异常分流摘要，但不得自判最终 verdict；最终 verdict 由独立 reviewer subagent 写入 review 文件
- 初步异常分流必须区分 `environment / setup / model / data / metric / method / unknown`
- 一旦初步判断需要 stage-out backtrack，必须明确说明 target_stage 候选、缺失证据和建议 rebuild_mode
- M3/M4 stage review 的 `REVISE/BACKTRACK/FIX` 会由 Conductor 自动转成 re-execute/backtrack；同 stage 修订用于受控 stage 内迭代

### Stage-level Reviewers（M4S01-M4S03）

#### m4_findings_audit（M4S01 审查）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/m4_findings_audit/AGENT.md`
- M4S01 产出路径
- M3S04 产出路径（辅助）
- 产出路径：`knowledge/reviews/M4S01_findings_audit_review.md`
- reviewer 需要写出可执行的 backtrack advice：target_stage、blocking_reason、required_fix、success_criteria、evidence_paths、rebuild_mode、rerun_scope、handoff_updates

#### m4_analysis_design_review（M4S02 审查）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/m4_analysis_design_review/AGENT.md`
- M4S02 产出路径
- M4S01 产出路径（辅助，对照 Claim 初筛）
- 产出路径：`knowledge/reviews/M4S02_analysis_design_review.md`
- reviewer 需要检查 baseline_inclusion、literature_basis、evidence_criteria、comparability contract 是否完整，并在需要时输出 stage-out backtrack advice

#### m4_analysis_execution_review（M4S03 审查）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/m4_analysis_execution_review/AGENT.md`
- M4S03 产出路径
- M4S02 设计文档路径（辅助对照）
- experiments/analysis_results.tsv 路径
- 产出路径：`knowledge/reviews/M4S03_analysis_execution_review.md`
- reviewer 需要检查 expected vs actual、异常原因分类、stage-in 修正 / stage-out 回溯建议，并写明 downstream stale stages 的重跑范围

### Gate G4 Critics（Phase 5，并行执行）

#### Logic Critic

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/logic/AGENT.md`
- M4S01-M4S04 全部产出路径
- M3S03-M3S04 产出路径（辅助，验证假设链条）
- 产出路径：`knowledge/reviews/G4_logic_review.md`

#### Evidence Critic

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/evidence/AGENT.md`
- M4S01-M4S04 全部产出路径
- experiments/analysis_results.tsv 路径
- 产出路径：`knowledge/reviews/G4_evidence_review.md`

#### Novelty Critic

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/novelty/AGENT.md`
- M4S01-M4S04 全部产出路径
- M1S02 产出路径（辅助，检查 M1 遗漏）
- 产出路径：`knowledge/reviews/G4_novelty_review.md`

## 状态管理规范

每完成一个 Stage，必须更新 `state/pipeline_state.yaml`。

使用 Python 脚本更新：

```python
from spiral.state import PipelineState
from pathlib import Path

proj = Path("projects/XXX")

state = PipelineState(proj)
state.record_completion("M4S01", "analysis", Path("knowledge/M4/M4S01_other_findings.md"))
state.set_stage("M4S02", "in_progress")

# 螺旋计数（回溯时递增）
spiral_count = state.data.get("spiral_count", {})
spiral_count["M4"] = spiral_count.get("M4", 0) + 1
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
| M4S01 完成后 | 数据质量审计覆盖 4 个维度、Claim 初筛有依据、分析战役规划有明确目标且有文献/数据库依据、组件/Claim 矩阵和效率触发/豁免判断 | REVISE / BACKTRACK → M4S01 |
| M4S02 完成后 | 所有 claim-carrying slice 有完整 Evidence Contract、Comparability Contract 明确、baseline_inclusion / literature_basis / paper_protocol_adaptation 明确，效率 slice 按需设计，执行信封现实 | REVISE / BACKTRACK → M4S02 / M4S01 |
| M4S03 完成后 | 所有设计 slice 有执行记录（含 failed/blocked）、负面结果未被隐藏、初步审查摘要给出异常分流、结果数据完整且包含扩展 schema | REVISE / BACKTRACK → M4S03 / M4S02 |
| M4S04 完成后 | Claim Ledger 完整、Insight Articulation 有 "So what?"、Limitations 诚实、证据可用性/效率证据/论文协议适配标注清楚、Handoff 完整 | BACKTRACK → M4S04 REVISE |
| Gate G4 | Logic ≥ 7.0 AND Evidence ≥ 7.0 AND Novelty ≥ 7.0 | BACKTRACK → 指定 M4 stage |
| Handoff 前 | 所有 M4 产出文件存在、handoff_M4_M5 非空 | 阻止完成 |

## Checkpoint 与用户交互

以下节点默认向用户发送进度更新（非阻塞，继续执行）：

1. **M4S01 完成后**: "实验后审计完成。发现 [N] 个意外模式，[M] 个负面结果，初步筛选出 [K] 个待验证 Claim。"
2. **M4S02 完成后**: "深度分析实验设计完成。共 [N] 个 analysis slice，其中 [M] 个 claim-carrying。"
3. **M4S03 完成后**: "分析实验执行完成。[N] 个 slice 完成，[M] 个失败/阻塞。"
4. **M4S04 完成后**: "证据打包完成。Claim Ledger: [N] supported, [M] partial, [K] unsupported。"
5. **Gate G4 完成后**: "Gate G4 通过（Logic: X/10, Evidence: X/10, Novelty: X/10），准备进入论文写作阶段。"
6. **M4 完成后**: "M4 深度分析完成。核心洞察：[一句话摘要]。建议进入 M5（论文写作）。"

如果用户要求暂停或介入，在下一个 Checkpoint 停止并等待用户指令。

## 输出协议

遵循 AutoPaper2 的输出协议：

1. **Output Versioning**: 首次写入时带时间戳，然后复制到固定名
2. **Output Manifest**: 每个产出记录到项目根目录的 `MANIFEST.md`
3. **Output Language**: 默认中文（与用户一致），用户可覆盖

M4 核心产出清单：
- `knowledge/M4/M4S01_other_findings.md`
- `knowledge/M4/M4S02_analysis_experiment_design.md`
- `knowledge/M4/M4S03_analysis_experiment.md`
- `knowledge/M4/M4S04_analysis_results.md`
- `knowledge/reviews/M4S01_findings_audit_review.md`（如触发审查）
- `knowledge/reviews/M4S02_analysis_design_review.md`（如触发审查）
- `knowledge/reviews/M4S03_analysis_execution_review.md`（如触发审查）
- `knowledge/reviews/G4_logic_review.md`
- `knowledge/reviews/G4_evidence_review.md`
- `knowledge/reviews/G4_novelty_review.md`
- `knowledge/handoff_M4_M5.md`
- `experiments/analysis_results.tsv`
- `experiments/artifacts/analysis_experiment/`

补充规则：
- `experiments/analysis_results.tsv` 记录所有 analysis slice 结果，包括失败的
- `experiments/analysis_results.tsv` 必须包含 `slice`, `analysis_type`, `method`, `dataset`, `split`, `seed`, `config_id`, `run_id`, `metric`, `value`, `baseline_inclusion`, `artifact_path`, `runtime_sec`, `params_m`, `peak_mem_mb`, `notes`
- `experiments/artifacts/analysis_experiment/` 保存原始数据、图表、可视化
- `knowledge/M4/` 保存阶段性结论，`knowledge/reviews/` 保存独立审查结论
- 默认输出语言为中文，除非用户指定英文

## Context Recovery

如果上下文被压缩或 session 中断，恢复流程：

1. 重新读取 `docs/AGENTS/analysis/AGENT.md`
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
python scripts/state_manager.py auto-stage M4S01

# 自动运行当前模块
python scripts/state_manager.py auto-module M4
```

## Key Rules

- **M3 必须先完成且 KEEP**：M4 的入口条件是 M3 已完成且 M3S04 决策为 KEEP。如果 M3S04 为 FIX/BACKTRACK，拒绝启动 M4，提示用户先完成 M3 修复。
- **Analysis Agent 统一负责 M4S01/S02/S04**：深度分析是一个连贯的思维过程，不拆分到不同 Agent。
- **Experiment Agent 只执行不设计**：M4S03 必须严格限定为执行 M4S02 已设计的实验，不得自行设计新 slice。
- **M4S03 必须使用 sandbox/container profile**：所有深度分析脚本都必须在 M3S01 建立的 `experiments/configs/sandbox_profile.yaml` 边界内运行，并记录命令、网络、写入、资源和日志路径。
- **Slice Evidence Contract 是 M4S02 的核心义务**：每个 claim-carrying slice 必须有完整的研究问题、干预、指标、claim_links。
- **M4S02 必须为可比 slice 写明 baseline_inclusion**：只要该 slice 讨论性能、鲁棒性或泛化，就要说明 baseline 是否同跑。
- **M4S02 必须为效率分析写明触发/豁免**：只要方法引入额外组件、额外计算路径、效率 claim 或参考论文惯例，就要设计效率 slice；不做时必须写明 waiver reason。
- **M4S02 必须使用 M1/M2 结构化论文信息**：高水平论文 task/metric/baseline/protocol 的采用或拒绝必须写入 Paper Protocol Adaptation Table。
- **Comparability Contract 必须明确**：防止 analysis slice 与主实验出现 apples-to-oranges 比较。
- **负面结果必须可见**：所有 failed / blocked / null / negative slice 必须完整记录，隐藏负面结果视为学术不端。
- **Stage Review 必须独立**：M4S01-M4S03 的 review 不得由执行 agent 自审。
- **M4S03 的初步审查摘要不是最终 verdict**：它只是执行侧的异常分流，最终判断必须写入独立 review 文件。
- **回溯策略必须区分 incremental_replay 与 full_regenerate**：小修可参考原始 downstream 文件；方向偏差大时只能把旧文件当历史证据，不得继续当新正文模板。
- **Gate G4 必须三 Critic**：Logic + Evidence + Novelty 三个 Critic 都通过才算 Gate 通过。
- **Claim Ledger 必须诚实**：不得将 unsupported 的 Claim 标记为 supported，不得隐瞒证据不足的声明。
- **Handoff 文件必须生成**：M4 完成后必须产出 `knowledge/handoff_M4_M5.md`。
- **跨模型隔离必须遵守**：Analysis Agent 与 Critics 不得由同一模型实例执行（参见 `docs/AGENTS/critic/cross_model_protocol.md`）。
- **螺旋上限为 10**：M4 模块最多允许 10 次回溯，超过则 HALT，需人工介入。
- **M4S03 需要 preliminary review subagent**：异常结果必须先做原因分流，再决定是 stage-in 修补还是 stage-out 回溯。
- **失败时诚实报告**：如果某个 stage 无法通过（如 Gate HALT、螺旋超限），必须明确报告原因，不强行推进。
