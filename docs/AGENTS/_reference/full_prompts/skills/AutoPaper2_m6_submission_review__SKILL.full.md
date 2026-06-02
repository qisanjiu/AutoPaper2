---
name: AutoPaper2_m6_submission_review
description: >
  AutoPaper2 Module 6 (Submission Review & Revision Loop) 全流程执行 Skill。
  当用户需要进入最终审稿与回溯修正阶段时触发，包括：
  前置检查 (M5 完成状态) → M6S01 投稿前审计与包组装
  → M6S01 内部严审（多 reviewer，≥8/10 且 High 未解决项为 0）
  → M6S02 外部审稿提交 (paperreview.ai)
  → M6S03 审稿意见接收与解析 (IMAP 邮箱监控)
  → M6S04 回溯规划与 Rebuttal 策略
  → M6S05 修订执行 (跨模块回溯)
  → M6S06 修订验证与完成判定
  → Gate G6（Logic + Evidence + Writing + Resolution Critic）
  → Handoff M6→归档/投稿。
  仅在用户明确指定进入 M6 或 M5 完成后建议进入 M6 时触发。
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

# M6 Submission Review & Revision Loop — 投稿审稿与回溯修正全流程

执行 AutoPaper2 的 **Module 6: Submission Review & Revision Loop**，完成从投稿前审计到外部审稿闭环的完整最终验证流程。

## 触发条件

当用户说以下任意一种表述时触发本 Skill：

- "进入 M6"
- "最终审稿"
- "外部审稿"
- "提交 review"
- "M6 阶段"
- "投稿审稿"
- "继续 M6"

**不触发**的情况：
- 用户明确说 "进入 M1/M2/M3/M4/M5"（应路由到对应 Stage）
- 当前项目 M5 尚未完成（应提示用户先完成 M5）

## 默认行为 vs 显式项目指定

### 默认：复用当前项目

如果用户没有明确指定项目路径，默认复用当前活跃项目（`projects/` 下最新的项目目录）：

```bash
cd {framework_root}
python scripts/state_manager.py status
```

检查 `state/pipeline_state.yaml`：
- 如果 M5 已完成（`M5.status == completed`）→ 正常启动 M6
- 如果 M5 未完成 → 提示用户先完成 M5
- 如果 M6 已在进行中 → 从当前 stage 继续

### 显式：进入指定项目

如果用户明确指定了现有项目，则定位到该项目，检查当前状态：
- 如果项目已完成 M6 → 询问是否回溯重新执行
- 如果项目在 M6 中间 → 从当前 stage 继续
- 如果项目尚未启动 M6 → 检查 M5 是否完成，然后正常启动

## 执行前检查清单

在启动 M6 之前，必须确认：

- [ ] 项目已定位（`projects/{name}-{timestamp}/` 存在）
- [ ] `state/pipeline_state.yaml` 可读
- [ ] M5 状态为 `completed`（或 `module_completed`）
- [ ] `knowledge/handoff_M5_completion.md` 存在且非空
- [ ] `artifacts/paper.pdf` 存在且可打开
- [ ] `artifacts/paper.tex` 存在
- [ ] 当前 stage 为 M6S01 或用户明确要求重新执行 M6
- [ ] M6 螺旋计数 < 10（`spiral_count.M6 < 10`）
- [ ] 邮件配置已就绪（`config/email_config.yaml` 存在或用户已提供邮箱凭证）

## 控制工作流

```
Phase 0: 进入 M6 前置检查
  → 检查 M5 状态是否为 completed
  → 读取 handoff_M5_completion.md
  → 检查 paper.pdf / paper.tex 完整性
  → 加载 AGENT.md: docs/AGENTS/submission/AGENT.md
  → 设置 pipeline_state: M6S01 in_progress
  → 标记 M6 模块状态为 in_progress

Phase 1: M6S01 投稿前审计与包组装
  → Submission Agent 执行
  → 审计 M1-M5 全部产出的完整性与一致性
  → 组装投稿包（paper.pdf + supplementary.zip + source.zip）
  → Venue 合规性最终检查（页数、格式、匿名性）
  → 产出: knowledge/M6/M6S01_submission_audit.md
  → Mandatory internal review: m6_internal_peer_review → knowledge/reviews/M6S01_internal_peer_review.md
  → 内部审查要求: Internal Review Score ≥ 8/10 且 Unresolved high-priority issues = 0
  → 若未达标: 按 reviewer 给出的 target_stage / required_fix / rebuild_mode 回溯，重跑受影响 stage 后重新内部审查
  → Stage review: m6_submission_audit → knowledge/reviews/M6S01_submission_audit_review.md
  → Conductor advance: M6S01 → M6S02

Phase 2: M6S02 外部审稿提交 (paperreview.ai)
  → 先确认 M6S01_internal_peer_review.md 已 PASS
  → Submission Agent 执行
  → 调用 scripts/paperreview_uploader.py 自动提交论文
  → 上传 paper.pdf 到 https://paperreview.ai
  → 邮箱从 `config/email_config.yaml` 读取，支持 CLI 覆盖
  → 可选 target venue（从 pipeline_state 读取）
  → 记录 submission tracking info
  → 产出: knowledge/M6/M6S02_external_review_submission.md
  → Stage review: m6_external_submission_review → knowledge/reviews/M6S02_external_submission_review.md
  → Conductor advance: M6S02 → M6S03

Phase 3: M6S03 审稿意见接收与解析
  → Rebuttal Agent 执行
  → 调用 scripts/email_monitor.py 监控 `config/email_config.yaml` 中的邮箱配置
  → 等待并接收 paperreview.ai 的审稿邮件
  → 解析邮件内容，提取结构化 review（scores, strengths, weaknesses, suggestions）
  → 归一化为 Review Matrix（原子化 reviewer items）
  → 产出: knowledge/M6/M6S03_review_parsing.md
  → 产出: knowledge/M6/M6S03_review_matrix.md
  → Stage review: m6_review_parsing_review → knowledge/reviews/M6S03_review_parsing_review.md
  → Conductor advance: M6S03 → M6S04

Phase 4: M6S04 回溯规划与 Rebuttal 策略
  → Rebuttal Agent 执行
  → 对每条审稿意见分类：editorial / text_only / evidence_gap / experiment_gap / claim_scope / cannot_fully_address
  → 映射到具体回溯目标 stage/module
  → 制定 Action Plan（含优先级、执行顺序、成功标准）
  → 产出: knowledge/M6/M6S04_rebuttal_strategy.md
  → 产出: knowledge/M6/M6S04_action_plan.md
  → Stage review: m6_rebuttal_strategy_review → knowledge/reviews/M6S04_rebuttal_strategy_review.md
  → Conductor advance: M6S04 → M6S05

Phase 5: M6S05 修订执行
  → 先调用 scripts/m6_action_router.py 将 action_plan 解析为确定性路由计划
  → Conductor 使用 Conductor.backtrack_from_revision_routing() 持久化 stage_backtrack_advice，保留每条审稿 item 到对应 stage 的 direct/downstream 修复说明
  → 根据 routing plan 路由到对应 Agent 执行
  → editorial/text_only → Writing Agent（M5 内部回溯）
  → evidence_gap/experiment_gap → Analysis Agent + Experiment Agent（M3/M4 回溯）
  → claim_scope/method_issue → Method Agent + Writing Agent（M2/M5 回溯）
  → 产出: knowledge/M6/M6S05_revision_execution.md
  → 更新 artifacts/paper.pdf（重新编译）
  → Stage review: m6_revision_execution_review → knowledge/reviews/M6S05_revision_execution_review.md
  → Conductor advance: M6S05 → M6S06

Phase 6: M6S06 修订验证与完成判定
  → Rebuttal Agent 执行
  → 对照 action_plan 验证每条审稿意见的解决度
  → 检查论文质量未因修订而退化（与 M5 Gate G5 评分对比）
  → 可选：再次提交到 paperreview.ai 验证（仅当 major revision 时）
  → 产出: knowledge/M6/M6S06_revision_validation.md
  → 产出: knowledge/handoff_M6_completion.md
  → Stage review: m6_revision_validation_review → knowledge/reviews/M6S06_revision_validation_review.md
  → Conductor advance: M6S06 → Gate G6

Phase 7: Gate G6 审查
  → Logic Critic 审查 → G6_logic_review.md
  → Evidence Critic 审查 → G6_evidence_review.md
  → Writing Critic 审查 → G6_writing_review.md
  → Resolution Critic 审查 → G6_resolution_review.md（M6 特有：审稿意见解决度）
  → 综合 verdict:
     → 全部 PASS → 进入 Handoff
     → 任一 REVISE → 回溯到指定 M6 Stage
     → 任一 BACKTRACK → 回溯到 M6 内部 Stage 或跨模块到 M5/M4/M3/M2
     → 任一 HALT → 终止 M6

Phase 8: Handoff & 完成
  → 产出: knowledge/handoff_M6_completion.md
  → 标记 M6 模块 completed
  → 生成最终投稿包（最终版 paper.pdf + supplementary.zip + source.zip + review_report.pdf）
  → 报告完成状态
```

## Agent 调用规范

### Submission Agent（M6S01, M6S02）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/submission/AGENT.md`
- 当前 stage（M6S01 / M6S02）
- 上游输入文档路径（handoff_M5_completion.md, paper.pdf, paper.tex）
- M6S01 产出路径：`knowledge/M6/M6S01_submission_audit.md`
- M6S02 产出路径：`knowledge/M6/M6S02_external_review_submission.md`
- 强调投稿包完整性和 venue 合规性检查义务
- M6S02 需包含调用 `scripts/paperreview_uploader.py` 的指令
- M6S02 前必须检查 `knowledge/reviews/M6S01_internal_peer_review.md` 已满足 8/10 门槛

**Submission Agent subagent 工具集**: ReadFile, WriteFile, Shell, WebSearch

### M6 Internal Peer Review Agent（M6S01 mandatory）

使用独立 reviewer subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/m6_internal_peer_review/AGENT.md`
- 当前论文 `artifacts/paper.pdf` / `artifacts/paper.tex`
- M1-M5 关键证据路径
- 输出路径：`knowledge/reviews/M6S01_internal_peer_review.md`
- 必须模拟至少 3 个严厉领域审稿专家
- PASS 条件：`Internal Review Score` ≥ 8/10 且 `Unresolved high-priority issues` 为 0
- 非 PASS 时必须给出完整回溯字段，Conductor 必须回溯而不是进入 M6S02

### Rebuttal Agent（M6S03, M6S04, M6S06）

使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/rebuttal/AGENT.md`
- 当前 stage（M6S03 / M6S04 / M6S06）
- 上游输入文档路径
- M6S03 需包含调用 `scripts/email_monitor.py` 的指令
- 审稿意见必须原子化，每条有 stable id（如 R1-C1, R1-C2）
- Action Plan 必须包含可执行的 backtrack advice（target_stage, blocking_reason, required_fix 等）
- 产出路径

**Rebuttal Agent subagent 工具集**: ReadFile, WriteFile, Shell, WebSearch

### Writing Agent（M6S05 中 text/editorial 修订）

当 action_plan 中的修订项主要为 text/editorial 时，使用 Writing Agent：
- 完整读取 `docs/AGENTS/writing/AGENT.md`
- 产出路径
- 工具集: ReadFile, WriteFile, Shell, WebSearch

### Analysis/Experiment Agent（M6S05 中 evidence/experiment 修订）

当 action_plan 需要补充实验或分析时，使用对应 Agent：
- Analysis Agent: `docs/AGENTS/analysis/AGENT.md`
- Experiment Agent: `docs/AGENTS/experiment/AGENT.md`
- 工具集: ReadFile, WriteFile, Shell, WebSearch

### Revision Agent（M6S05 执行记录）

在所有路由修订完成后，使用 Revision Agent 写入 `knowledge/M6/M6S05_revision_execution.md`：
- 完整读取 `docs/AGENTS/revision/AGENT.md`
- 读取 `knowledge/M6/M6S04_action_plan.md` 和 `state/dispatch/M6S05_revision_routes.*`（如已写出）
- 逐条核验每个 Action Plan item 的执行状态、证据路径和阻塞项
- 不得直接修改 Method / Experiment / Analysis / Writing Agent 的 stage 产物

### M6 Stage Reviewers（每个 Stage 完成后）

使用独立 reviewer subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/m6_stage_review/AGENT.md`
- 当前 stage 与对应输出文档路径
- 对应 review 输出路径（见下表）

| Stage | Reviewer | Review Output |
|-------|----------|---------------|
| M6S01 | m6_internal_peer_review | `knowledge/reviews/M6S01_internal_peer_review.md` |
| M6S01 | m6_submission_audit | `knowledge/reviews/M6S01_submission_audit_review.md` |
| M6S02 | m6_external_submission_review | `knowledge/reviews/M6S02_external_submission_review.md` |
| M6S03 | m6_review_parsing_review | `knowledge/reviews/M6S03_review_parsing_review.md` |
| M6S04 | m6_rebuttal_strategy_review | `knowledge/reviews/M6S04_rebuttal_strategy_review.md` |
| M6S05 | m6_revision_execution_review | `knowledge/reviews/M6S05_revision_execution_review.md` |
| M6S06 | m6_revision_validation_review | `knowledge/reviews/M6S06_revision_validation_review.md` |

任何非 PASS verdict 都必须由 Conductor 触发同 stage revise 或跨 stage backtrack。

### Gate G6 Critics（Phase 7，并行执行）

#### Logic Critic
使用 subagent 执行，prompt 包含：
- 完整读取 `docs/AGENTS/critic/logic/AGENT.md`
- M6S01-M6S06 全部产出路径
- 产出路径：`knowledge/reviews/G6_logic_review.md`

#### Evidence Critic
使用 subagent 执行，prompt 包含：
- 完整读取 `docs/AGENTS/critic/evidence/AGENT.md`
- M6S05-M6S06 产出路径 + 修订后的 experiments/results.tsv
- 产出路径：`knowledge/reviews/G6_evidence_review.md`

#### Writing Critic
使用 subagent 执行，prompt 包含：
- 完整读取 `docs/AGENTS/critic/writing/AGENT.md`
- 修订后的 paper.tex / paper.pdf
- 产出路径：`knowledge/reviews/G6_writing_review.md`

#### Resolution Critic（M6 特有）
使用 subagent 执行，prompt 必须包含：
- 完整读取 `docs/AGENTS/critic/g6_resolution/AGENT.md`
- M6S03 review_matrix.md
- M6S04 action_plan.md
- M6S06 revision_validation.md
- 产出路径：`knowledge/reviews/G6_resolution_review.md`

## 自动化工具使用规范

### paperreview.ai 提交 (`scripts/paperreview_uploader.py`)

在 M6S02 中，Submission Agent 必须调用：

```bash
python scripts/paperreview_uploader.py \
  --pdf artifacts/paper.pdf \
  --config config/email_config.yaml \
  --email "<review_email>" \
  --venue "<venue_id>" \
  --output knowledge/M6/M6S02_submission_log.json
```

参数说明：
- `--pdf`: 论文 PDF 路径（必需）
- `--config`: 可选邮箱配置文件，默认读取 `config/email_config.yaml`
- `--email`: 接收审稿意见的邮箱（默认从配置读取）
- `--venue`: 目标会议/期刊（可选，从 pipeline_state 读取）
- `--output`: 提交日志输出路径（JSON 格式）
- `--headless`: 无头模式（默认 true，CI 环境使用）

如果环境中未安装 playwright，脚本会输出安装指令：
```bash
pip install playwright
playwright install chromium
```

### 邮箱监控 (`scripts/email_monitor.py`)

在 M6S03 中，Rebuttal Agent 必须调用：

```bash
python scripts/email_monitor.py \
  --config config/email_config.yaml \
  --email "<review_email>" \
  --password "<IMAP_AUTH_CODE>" \
  --sender-filter "noreply@paperreview.ai" \
  --output knowledge/M6/M6S03_review_email.json \
  --wait-timeout 3600
```

参数说明：
- `--config`: 可选邮箱配置文件，默认读取 `config/email_config.yaml`
- `--email`: 邮箱地址（默认从配置读取）
- `--password`: IMAP/SMTP 授权码（非 QQ 密码，需用户提前在 QQ 邮箱设置中开启 IMAP 并获取授权码）
- `--sender-filter`: 发件人过滤（paperreview.ai 的默认发件人）
- `--output`: 解析结果输出路径（JSON 格式）
- `--wait-timeout`: 等待邮件的最大秒数（默认 3600 = 1 小时）
- `--poll-interval`: 轮询间隔秒数（默认 60）

**重要**: QQ 邮箱授权码需要用户手动获取。Agent 在 M6S01 前应检查 `config/email_config.yaml` 是否存在，若不存在应提示用户配置。

## 状态管理规范

每完成一个 Stage，必须更新 `state/pipeline_state.yaml`。

```python
from spiral.state import PipelineState
from pathlib import Path

proj = Path("projects/XXX")

state = PipelineState(proj)
state.record_completion("M6S01", "submission", Path("knowledge/M6/M6S01_submission_audit.md"))
state.set_stage("M6S02", "in_progress")

# 螺旋计数（回溯时递增）
spiral_count = state.data.get("spiral_count", {})
spiral_count["M6"] = spiral_count.get("M6", 0) + 1
state.data["spiral_count"] = spiral_count
state.save()
```

回溯后：
- `stale_stages` 代表需要重新跑的 downstream stage
- 被重新完成的 stale stage 必须自动清除 stale 标记
- `gate_re_review` 中的对应 gate 只有在重新通过后才能清除

## 质量门控

| 节点 | 检查项 | 失败处理 |
|------|--------|---------|
| M6S01 完成后 | 投稿包完整、venue 合规、匿名性通过；内部审查 ≥8/10 且 High 未解决项为 0 | REVISE → M6S01 或 BACKTRACK 到 reviewer 指定 stage |
| M6S02 完成后 | 内部审查已 PASS；paperreview.ai 提交成功、有 tracking info | REVISE → M6S02 |
| M6S03 完成后 | 审稿邮件成功接收、Review Matrix 原子化完整 | REVISE → M6S03 |
| M6S04 完成后 | Action Plan 有可执行 backtrack advice、优先级明确 | REVISE → M6S04 |
| M6S05 完成后 | 修订已执行、paper.pdf 已重新编译 | REVISE → M6S05 |
| M6S06 完成后 | 审稿意见解决度 ≥ 80%、无 High 优先级未解决项、质量未退化 | REVISE → M6S06 |
| Gate G6 | Logic ≥7.0 AND Evidence ≥7.0 AND Writing ≥7.0 AND Resolution ≥7.0 | BACKTRACK → 指定 stage |
| Handoff 前 | 所有 M6 产出文件存在、最终 paper.pdf 可打开 | 阻止完成 |

## Checkpoint 与用户交互

以下节点默认向用户发送进度更新（非阻塞，继续执行）：

1. **M6S01 完成后**: "投稿前审计完成。投稿包已组装，内部审查评分：[X/10]，High 未解决项：[N]。"
2. **M6S02 完成后**: "内部审查已通过，论文已提交到 paperreview.ai。追踪信息已记录。"
3. **M6S03 完成后**: "审稿意见已接收并解析。共 [N] 条原子化意见，High 优先级 [M] 条。"
4. **M6S04 完成后**: "回溯规划完成。需回溯到 [target_stage]，涉及 [N] 个模块。"
5. **M6S05 完成后**: "修订执行完成。已更新 paper.pdf。"
6. **M6S06 完成后**: "修订验证完成。审稿意见解决度：[X]%，质量保持度：[Y]/10。"
7. **Gate G6 完成后**: "Gate G6 通过（Logic: X/10, Evidence: X/10, Writing: X/10, Resolution: X/10）。"
8. **M6 完成后**: "M6 最终审稿完成。最终投稿包已生成。"

如果用户要求暂停或介入，在下一个 Checkpoint 停止并等待用户指令。

## 输出协议

遵循 AutoPaper2 的输出协议：

1. **Output Versioning**: 首次写入时带时间戳，然后复制到固定名
2. **Output Manifest**: 每个产出记录到项目根目录的 `MANIFEST.md`
3. **Output Language**: 默认中文（与用户一致）

M6 核心产出清单：
- `knowledge/M6/M6S01_submission_audit.md`
- `knowledge/reviews/M6S01_internal_peer_review.md`
- `knowledge/M6/M6S02_external_review_submission.md`
- `knowledge/M6/M6S03_review_parsing.md`
- `knowledge/M6/M6S03_review_matrix.md`
- `knowledge/M6/M6S04_rebuttal_strategy.md`
- `knowledge/M6/M6S04_action_plan.md`
- `knowledge/M6/M6S05_revision_execution.md`
- `knowledge/M6/M6S06_revision_validation.md`
- `knowledge/reviews/G6_logic_review.md`
- `knowledge/reviews/G6_evidence_review.md`
- `knowledge/reviews/G6_writing_review.md`
- `knowledge/reviews/G6_resolution_review.md`
- `knowledge/handoff_M6_completion.md`
- `knowledge/M6/M6S02_submission_log.json`（自动工具生成）
- `knowledge/M6/M6S03_review_email.json`（自动工具生成）

补充规则：
- 最终 `paper.pdf` 必须保存在 `artifacts/paper.pdf`
- 所有审稿相关文件保存在 `knowledge/M6/` 下
- Review Matrix 必须保持原子化，每条意见有 stable id
- Action Plan 的 backtrack advice 必须符合 conductor 的格式要求
- 默认输出语言为中文，论文正文按 venue 要求

## Context Recovery

如果上下文被压缩或 session 中断，恢复流程：

1. 重新读取 `docs/AGENTS/submission/AGENT.md` 或 `docs/AGENTS/rebuttal/AGENT.md`
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
python scripts/state_manager.py auto-stage M6S01

# 自动运行当前模块
python scripts/state_manager.py auto-module M6
```

## Key Rules

- **M5 必须先完成**：M6 的入口条件是 M5 已完成。如果 M5 未完成，拒绝启动 M6。
- **内部审稿是强制环节**：M6S01 后必须通过多 reviewer 严审，达到 8/10 且 High 未解决项为 0，不能跳过。
- **外部审稿是强制环节**：M6S02 必须在内部审稿通过后实际提交到 paperreview.ai，不能跳过。
- **邮箱监控需要用户配置**：QQ 邮箱授权码需用户手动获取，Agent 不能假设已配置。
- **Review Matrix 必须原子化**：每条审稿意见必须有 stable id、分类、优先级、映射到的回溯目标。
- **Action Plan 必须有可执行 advice**：每条修订项必须包含 target_stage、required_fix、success_criteria。
- **修订必须验证**：M6S06 必须对照 action_plan 逐条验证，不能假设修订已充分。
- **质量不能退化**：修订后的论文质量不得低于 Gate G5 水平。
- **Gate G6 必须四 Critic**：Logic + Evidence + Writing + Resolution 全部通过才算 Gate 通过。
- **Resolution Critic 是 M6 特有**：专门审查审稿意见的解决度和回应质量。
- **Handoff 文件必须生成**：M6 完成后必须产出 `knowledge/handoff_M6_completion.md`。
- **跨模型隔离必须遵守**：Rebuttal Agent 与 Resolution Critic 不得由同一模型实例执行（参见 `docs/AGENTS/critic/cross_model_protocol.md`）。
- **螺旋上限为 10**：M6 模块最多允许 10 次回溯，超过则 HALT，需人工介入。
- **失败时诚实报告**：如果某个 stage 无法通过（如 Gate HALT、螺旋超限），必须明确报告原因，不强行推进。
