# AutoPaper2 — Agent Global Context

> **Scope**: All agents working within AutoPaper2 framework.

---

## 1. Directory Structure

### 1.1 Framework Root

Contains `spiral/`, `docs/`, `config/`, `scripts/`, `templates/`, `utils/`.

### 1.2 Projects Root

All projects at `{FrameworkRoot}/projects`.

### 1.3 Project Folder Naming

```
{sanitized_name}-{YYYYMMDD-HHMMSS}/
```

### 1.4 Knowledge Directory Structure

```
knowledge/
├── M1/                        # Module 1 outputs
│   ├── M1S01_topic_scoping.md
│   ├── M1S02_literature_deepdive.md
│   ├── M1_source_log.yaml     # NEW: Structured source log
│   └── ...
├── M2/                        # Module 2 outputs
├── M3/                        # Module 3 outputs
├── M4/                        # Module 4 outputs
├── M5/                        # Module 5 outputs
├── M6/                        # Module 6 outputs (NEW)
│   ├── M6S01_submission_audit.md
│   ├── M6S02_external_review_submission.md
│   ├── M6S03_review_parsing.md
│   ├── M6S03_review_matrix.md
│   ├── M6S04_rebuttal_strategy.md
│   ├── M6S04_action_plan.md
│   ├── M6S05_revision_execution.md
│   ├── M6S06_revision_validation.md
│   ├── M6S02_submission_log.json
│   └── M6S03_review_email.json
├── handoff_M1_M2.md
├── handoff_M2_M3.md
├── handoff_M3_M4.md
├── handoff_M4_M5.md
├── handoff_M5_completion.md
└── reviews/
    └── G1_aggregate.md
```

---

## 2. Key Paths

### 2.0 Project-Local Skill Loading（跨 CLI 强制）

AutoPaper2 的 Skill **只以项目内文件为可信来源**，不得假设 Claude Code、Codex、KimiCode 或其他 CLI 已安装全局 skill。

| CLI / Runtime | 读取方式 |
|---------------|----------|
| Claude Code | 优先读取项目内 `.claude/skills/<skill_name>/SKILL.md` |
| Codex / KimiCode / 其他 CLI | 根据用户意图或路由结果，直接读取项目内 `skills/<skill_name>/SKILL.md` |
| 所有 CLI | Stage/subagent prompt 均通过 dispatch packet 中的 `agent_md` 字段读取 `docs/AGENTS/**/AGENT.md` |

**权威源规则**：

1. `skills/` 是项目内 canonical skill source。
2. `.claude/skills/` 是 Claude Code 自动发现用镜像，必须与 `skills/` 同步。
3. 主 Agent / Conductor 在任何 CLI 中恢复上下文时，若运行时没有自动 skill 发现能力，必须手动打开对应的 `skills/<skill_name>/SKILL.md`。
4. 禁止依赖 `~/.codex/skills`、`~/.claude/skills` 或其他用户全局（global）目录中的 AutoPaper2 skill；全局 skill 只能作为外部工具能力，不是本框架流程真源。
5. 修改任意 `skills/**/SKILL.md` 后，必须同步 `.claude/skills/` 并运行：
   ```bash
   python scripts/cli_compat_check.py
   ```
6. 生成 dispatch packet 后，传给 subagent 的 prompt 必须保留完整且可解析的 `agent_md` 路径引用；subagent 必须直接读取该路径，而不是依赖主 Agent 摘要。
7. Dispatch packet 中的持久化路径不得写入当前机器绝对路径。项目内路径使用 `project:<relative-path>`，框架内路径使用 `framework:<relative-path>`；运行时由 `SPIRAL_FRAMEWORK_ROOT`、当前 AutoPaper2 根目录、或 packet 所在的 `<project>/state/dispatch/` 位置解析。

### 2.1 Main Agent Boundary

The main Agent / Conductor **only orchestrates**: project creation, module routing, stage advancement, review scheduling, gate handling, and backtracking. It **must not** execute Stage work or Stage review work directly. Stage execution and review **must be delegated** to the corresponding subagent prompts under `docs/AGENTS/`.

Before delegating any Stage, Stage Review, or Gate Review, the Conductor must generate a durable dispatch packet and pass the packet path to the subagent:

```bash
python scripts/state_manager.py dispatch next --write
python scripts/state_manager.py dispatch stage <stage> --write
python scripts/state_manager.py dispatch reviews <stage> --write
python scripts/state_manager.py dispatch gate <Gx> --write
```

The main Agent must not write any output path listed inside `state/dispatch/*.md`; those paths belong to the assigned subagent.

Dispatch packets must pass paths, not copied content. The compact launch prompt should contain only the packet reference, task type/role, stage or gate, required output, role spec reference, and the no-parent-context rule.

#### Orchestrator Identity Persistence（编排者身份持久化）

The main Agent's orchestrator identity **must not rely solely on LLM working memory**. When the conversation is paused and resumed (e.g., user says "continue"), the main Agent must re-establish its orchestrator role through the following durable mechanisms:

1. **State File Lock** (`pipeline_state.yaml`):
   - `session.orchestrator_lock`: Always `true` when the main agent is active.
   - `session.last_agent_mode`: Set to `"orchestrator"` at session start.
   - Read via `PipelineState.assert_orchestrator_mode()`.

2. **Runtime Boundary Guard** (`scripts/orchestrator_guard.py`):
   - Before any write operation, the orchestrator must run:
     ```bash
     python scripts/orchestrator_guard.py <project_root> <target_path>
     ```
   - Exit code 1 means **FORBIDDEN** — the path belongs to a subagent.
   - The script is universal and works across Claude Code, KimiCode, Codex, etc.

3. **Skill Manifest Injection**:
   - Every orchestrator and module Skill begins with an `ORCHESTRATOR MANIFEST` block.
   - This block is the first content after frontmatter, ensuring it survives context compression.

4. **Context Recovery Protocol** (mandatory after pause):
   ```bash
   python scripts/state_manager.py status
   python scripts/state_manager.py dispatch next --write
   # Delegate generated packet to subagent — do NOT execute content yourself
   ```

#### Backtrack Delegation Rule（强制）

When a backtrack is triggered (by stage review, gate critic, or human review):

1. **Conductor only updates state**: marks stale stages, records backtrack_log, increments spiral_count, updates current stage.
2. **Conductor must NOT directly modify any stage output file** in `knowledge/` or `drafts/`.
3. **Re-execution must be performed by the corresponding subagent**, not by the main agent. Conductor must construct a complete execution plan (via `run_stage()`) and delegate to the subagent using the `Agent` tool.
4. **The subagent prompt must include**:
   - Portable path reference to the corresponding `docs/AGENTS/{role}/AGENT.md`
   - Current stage and project root reference
   - All upstream input document path references (pass paths only, never summaries)
   - Complete `backtrack_advice` (blocking_reason, required_fix, success_criteria, rebuild_mode, evidence_paths, rerun_scope)
   - Output file path reference
5. **Rebuild mode enforcement**:
   - `full_regenerate` (default): subagent must treat old downstream files as historical audit only; no copy-paste allowed.
   - `incremental_replay`: subagent may reference old files to reduce redundancy, but all retained content must be re-validated against current upstream inputs.
6. **`scripts/state_manager.py` must use `Conductor.backtrack()`** for all human-review revise/backtrack operations. Duplicated backtrack logic in state_manager is prohibited.

| Path | Description |
|------|-------------|
| `{project}/state/pipeline_state.yaml` | Global state |
| `{project}/state/survey_memory.yaml` | M1 survey memory (NEW) |
| `{project}/state/decision_log.md` | Decision log |
| `{project}/state/spiral_log.md` | Spiral log |
| `{project}/knowledge/M1/` | M1 outputs |
| `{project}/knowledge/M1/M1_source_log.yaml` | Structured source log |
| `{project}/knowledge/M2/` | M2 outputs |
| `{project}/knowledge/M2/M2S01_cross_domain_search.md` | Cross-domain literature search |
| `{project}/knowledge/M2/M2S02_method_inspiration.md` | Multi-paper inspiration & adaptation |
| `{project}/knowledge/M2/M2S03_method_architecture.md` | Method architecture design |
| `{project}/knowledge/M2/M2S04_algorithm_theory.md` | Algorithm & theory design |
| `{project}/knowledge/M2/M2S05_experiment_setup.md` | Experiment setup design |
| `{project}/knowledge/M2/M2S06_full_experiment_plan.md` | Full experiment plan |
| `{project}/knowledge/handoff_M2_M3.md` | M2→M3 handoff document |
| `{framework}/skills/AutoPaper2_m2_method_design/SKILL.md` | M2 execution skill |
| `{framework}/templates/stage/M2S01_template.md` | M2S01 stage template |
| `{framework}/docs/AGENTS/critic/method/AGENT.md` | Gate G2 Method Critic |
| `{framework}/docs/AGENTS/conductor/AGENT.md` | Conductor / main orchestration agent |
| `{project}/knowledge/M3/` | M3 outputs |
| `{project}/knowledge/M3/M3S01_implementation.md` | Implementation & environment setup |
| `{project}/knowledge/M3/M3S02_baseline_lock.md` | Baseline lock & smoke test |
| `{project}/knowledge/M3/M3S03_main_experiment.md` | Main experiment execution |
| `{project}/knowledge/M3/M3S04_result_validation.md` | Result validation & evidence packaging |
| `{project}/knowledge/handoff_M3_M4.md` | M3→M4 handoff document |
| `{framework}/skills/AutoPaper2_m3_experiment/SKILL.md` | M3 execution skill |
| `{framework}/templates/stage/M3S01_template.md` | M3S01 stage template |
| `{framework}/docs/AGENTS/critic/evidence/AGENT.md` | Gate G3 Evidence Critic |
| `{project}/knowledge/M4/` | M4 outputs |
| `{project}/knowledge/M4/M4S01_other_findings.md` | Post-experiment audit & findings consolidation |
| `{project}/knowledge/M4/M4S02_analysis_experiment_design.md` | Deep analysis experiment design (ablations, mechanisms, robustness) |
| `{project}/knowledge/M4/M4S03_analysis_experiment.md` | Deep analysis experiment execution |
| `{project}/knowledge/M4/M4S04_analysis_results.md` | Analysis results integration & evidence packaging |
| `{project}/knowledge/handoff_M4_M5.md` | M4→M5 handoff document |
| `{framework}/skills/AutoPaper2_m4_deep_analysis/SKILL.md` | M4 execution skill |
| `{framework}/templates/stage/M4S01_template.md` | M4S01 stage template |
| `{framework}/docs/AGENTS/critic/m4_findings_audit/AGENT.md` | M4S01 Stage Reviewer |
| `{framework}/docs/AGENTS/critic/m4_analysis_design_review/AGENT.md` | M4S02 Stage Reviewer |
| `{framework}/docs/AGENTS/critic/m4_analysis_execution_review/AGENT.md` | M4S03 Stage Reviewer |
| `{project}/knowledge/M5/` | M5 outputs |
| `{project}/knowledge/M5/M5S01_pre_write_audit.md` | Pre-write audit & contribution articulation |
| `{project}/knowledge/M5/M5S02_paper_outline.md` | Paper outline (plotting plan, terminology, section budget) |
| `{project}/knowledge/M5/M5S03_introduction_relatedwork.md` | Introduction & Related Work |
| `{project}/knowledge/M5/M5S04_methodology.md` | Methodology section |
| `{project}/knowledge/M5/M5S05_experiments_results.md` | Experiments & Results section |
| `{project}/knowledge/M5/M5S06_analysis_discussion.md` | Analysis & Discussion section |
| `{project}/knowledge/M5/M5S07_abstract_conclusion.md` | Abstract & Conclusion |
| `{project}/knowledge/M5/M5S08_final_compilation.md` | Full draft assembly & compilation report |
| `{project}/knowledge/M5/M5S09_full_polish.md` | Full-Polish & Narrative Coherence Review |
| `{project}/artifacts/paper.tex` | Final LaTeX source |
| `{project}/artifacts/paper.pdf` | Compiled PDF |
| `{project}/knowledge/handoff_M5_completion.md` | M5 completion handoff |
| `{framework}/skills/AutoPaper2_m5_writing/SKILL.md` | M5 execution skill |
| `{framework}/templates/stage/M5S01_template.md` | M5S01 stage template |
| `{framework}/docs/AGENTS/writing/AGENT.md` | Writing Agent |
| `{framework}/docs/AGENTS/build_verifier/AGENT.md` | Build Verifier (LaTeX compilation) |
| `{framework}/docs/AGENTS/review/AGENT.md` | Peer Review Simulation Agent (optional enhancement) |
| `{framework}/docs/AGENTS/critic/writing/AGENT.md` | Gate G5 Writing Critic |
| `{framework}/docs/AGENTS/critic/ethics/AGENT.md` | Gate G5 Ethics Critic |
| `{project}/knowledge/M6/` | M6 outputs (NEW) |
| `{project}/knowledge/M6/M6S01_submission_audit.md` | Pre-submission audit & package assembly |
| `{project}/knowledge/M6/M6S02_external_review_submission.md` | External review submission (paperreview.ai) |
| `{project}/knowledge/M6/M6S03_review_parsing.md` | Review reception & parsing |
| `{project}/knowledge/M6/M6S03_review_matrix.md` | Atomic reviewer-item matrix |
| `{project}/knowledge/M6/M6S04_rebuttal_strategy.md` | Backtrack planning & rebuttal strategy |
| `{project}/knowledge/M6/M6S04_action_plan.md` | Executable action plan with backtrack advice |
| `{project}/knowledge/M6/M6S05_revision_execution.md` | Revision execution record |
| `{project}/knowledge/M6/M6S06_revision_validation.md` | Revision validation & completion verdict |
| `{project}/knowledge/handoff_M6_completion.md` | M6 completion handoff |
| `{framework}/skills/AutoPaper2_m6_submission_review/SKILL.md` | M6 execution skill |
| `{framework}/templates/stage/M6S01_template.md` | M6S01 stage template |
| `{framework}/docs/AGENTS/submission/AGENT.md` | Submission Agent (M6S01, M6S02) |
| `{framework}/docs/AGENTS/rebuttal/AGENT.md` | Rebuttal Agent (M6S03, M6S04, M6S06) |
| `{framework}/docs/AGENTS/critic/g6_resolution/AGENT.md` | Gate G6 Resolution Critic |
| `{framework}/docs/AGENTS/critic/m6_stage_review/AGENT.md` | M6 Stage Reviewer |
| `{framework}/scripts/paperreview_uploader.py` | paperreview.ai auto-submission script |
| `{framework}/scripts/email_monitor.py` | IMAP email monitor for review reception |
| `{framework}/config/ssh_servers.yaml` | Framework-level SSH server registry |
| `{framework}/state/ssh_leases.yaml` | Framework-level SSH project leases |
| `{framework}/state/ssh_events.jsonl` | Redacted SSH operation event stream |
| `{framework}/scripts/ssh_manager.py` | SSH server, lease, probe, sync, and remote command manager |
| `{framework}/docs/AGENTS/ssh/AGENT.md` | SSH Ops Agent |
| `{framework}/skills/AutoPaper2_ssh_ops/SKILL.md` | SSH Ops orchestration skill |
| `{framework}/skills/AutoPaper2_ssh_server_onboarding/SKILL.md` | Guided SSH server creation skill |

---

## 3. Environment Variable

| Variable | Purpose |
|----------|---------|
| `SPIRAL_FRAMEWORK_ROOT` | Override framework root detection |
| `SPIRAL_PROJECTS_ROOT` | Override projects root location |
