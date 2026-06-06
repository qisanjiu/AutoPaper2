# AutoPaper2

> **A state-driven autonomous research framework for taking a topic from scoping to experiments, paper writing, submission, review parsing, rebuttal, and revision.**

AutoPaper2 treats academic research as a guarded software pipeline. A project moves through six modules (M1-M6), each made of explicit stages, durable state, subagent prompts, review packets, and gate critics. The central rule is strict **Conductor-Executor separation**: the main agent orchestrates state, dispatch, review routing, and backtracking; stage execution and review work must be delegated to the matching subagent prompt under `docs/AGENTS/`.

---

## Table of Contents

- [Overview](#overview)
- [Repository Map](#repository-map)
- [System Architecture](#system-architecture)
- [The Six Modules](#the-six-modules)
- [Gate & Review System](#gate--review-system)
- [Dispatch Workflow](#dispatch-workflow)
- [Spiral Backtracking](#spiral-backtracking)
- [Quick Start](#quick-start)
- [Project Entry & Anchors](#project-entry--anchors)
- [Project Layout](#project-layout)
- [Configuration](#configuration)
- [Skills & CLI Compatibility](#skills--cli-compatibility)
- [Quality Checks](#quality-checks)
- [License](#license)

---

## Overview

AutoPaper2 is a framework for structured, agent-assisted paper production. It does not collapse the research process into one long prompt. Instead it uses:

1. **Durable project state** - each project has `state/pipeline_state.yaml`, decision logs, spiral logs, dispatch packets, and onboarding state.
2. **Specialized agents** - survey, ideation, method, experiment, analysis, writing, submission, rebuttal, revision, SSH ops, and critic agents have separate prompt contracts.
3. **Path-based delegation** - dispatch packets pass `project:<relative-path>` and `framework:<relative-path>` references. Subagents read source files directly.
4. **Review-gated advancement** - stages and modules are checked by reviewers and gate critics before downstream work is trusted.
5. **Structured backtracking** - failed reviews become explicit backtrack advice with target stage, required fix, success criteria, evidence paths, rebuild mode, and rerun scope.
6. **Cross-CLI operation** - Claude Code can discover `.claude/skills/`; Codex, KimiCode, and other CLIs load canonical skills directly from `skills/`.

---

## Repository Map

| Path | Purpose |
|------|---------|
| `spiral/` | Core state, project, conductor, dispatch, public DB, SSH registry, and routing logic. |
| `scripts/state_manager.py` | Main CLI for project creation, status, dispatch, advancement, backtracking, and public DB operations. |
| `scripts/orchestrator_guard.py` | Runtime write-boundary guard for orchestrator-mode agents. |
| `scripts/subagent_launch_prompt.py` | Extracts the compact launch prompt from a dispatch packet. |
| `docs/AGENTS/` | Canonical role prompts for stage executors, reviewers, critics, SSH ops, and build verification. |
| `skills/` | Canonical project-local AutoPaper2 skills. |
| `.claude/skills/` | Claude Code mirror of `skills/` for auto-discovery. |
| `templates/stage/` | Draft templates for stage outputs. |
| `templates/venue/` | Venue-specific LaTeX templates. |
| `config/` | Venue registry, execution environment defaults, gate rubrics, public DB config, image generation config, and requirement trace metadata. |
| `tests/` | Integration and guard tests for pipeline behavior, dispatch packets, CLI compatibility, SSH registry, and resource planning. |

---

## System Architecture

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

Core components:

- **Conductor** (`spiral/conductor.py`) builds execution plans, advances state, schedules reviews, and records backtracks.
- **PipelineState** (`spiral/state.py`) persists current module/stage, statuses, stale stages, gate re-review flags, and spiral counters.
- **ProjectManager** (`spiral/project.py`) creates timestamped projects, initializes templates, writes `state/research_brief.yaml`, copies venue assets, and probes the execution environment.
- **Dispatch System** (`spiral/dispatch.py`, `scripts/state_manager.py dispatch`) writes durable packets for stage execution, stage review, gate review, SSH ops, and revision routing.
- **Boundary Guard** (`scripts/orchestrator_guard.py`) prevents the orchestrator from writing executor/reviewer-owned outputs such as `knowledge/M*/M*S*.md`, review files, and final paper artifacts.

---

## The Six Modules

### M1 - Domain Survey

| Stage | Purpose |
|-------|---------|
| `M1S01` | Topic scoping: research question, keywords, boundaries, and anchor papers. |
| `M1S02` | Literature deep dive: iterative search plus structured source logging. |
| `M1S03` | Gap and opportunity analysis. |
| `M1S04` | Pre-idea draft and candidate solution directions. |
| `M1S05` | Idea finalization and M1-to-M2 handoff. |

**Gate G1** checks survey logic, coverage, source quality, and gap validity.

### M2 - Method Design

| Stage | Purpose |
|-------|---------|
| `M2S01` | Cross-domain search for transferable methods. |
| `M2S02` | Migration analysis from external techniques to the target problem. |
| `M2S03` | Method architecture design. |
| `M2S04` | Algorithm and theory design. |
| `M2S05` | Experiment setup design: datasets, metrics, baselines, fairness rules. |

**Gate G2** checks logic, method soundness, novelty, and experiment-setup readiness.

### M3 - Experiment Implementation & Execution

| Stage | Purpose |
|-------|---------|
| `M3S01` | Main experiment design: dataset, metrics, baseline reference values, and same-condition protocol. |
| `M3S02` | Dataset and environment setup. |
| `M3S03` | Baseline lock and smoke tests. |
| `M3S04` | Main experiment execution. |
| `M3S05` | Result validation, evidence packaging, and M3-to-M4 handoff. |

Each M3 stage has its own targeted stage reviewer: `m3_main_experiment_design_review`, `m3_dataset_env_review`, `m3_baseline_result_review` plus `m3_baseline_lock_audit`, `m3_main_result_review`, and `m3_result_validation_review`. M3 cannot rely on a generic reviewer to advance.

**Gate G3** checks method implementation, baseline fairness, result validity, and evidence sufficiency.

### M4 - Deep Analysis

| Stage | Purpose |
|-------|---------|
| `M4S01` | Post-experiment audit and findings consolidation. |
| `M4S02` | Analysis experiment design: ablations, mechanisms, robustness checks. |
| `M4S03` | Deep analysis execution. |
| `M4S04` | Analysis result integration and M4-to-M5 handoff. |

**Gate G4** checks whether the analysis supports the paper's intended claims.

### M5 - Writing & Finalization

| Stage | Purpose |
|-------|---------|
| `M5S01` | Pre-write audit and contribution articulation. |
| `M5S02` | Paper outline, plotting plan, terminology table, and section budget. |
| `M5S04` | Methodology section. |
| `M5S05` | Experiments and results section. |
| `M5S06` | Analysis and discussion section. |
| `M5S03` | Introduction and related work, written after evidence is locked. |
| `M5S07` | Abstract and conclusion. |
| `M5S08` | Full draft assembly and LaTeX compilation. |
| `M5S09` | Full polish and narrative coherence review. |

**Gate G5** checks logic, writing quality, evidence, novelty, ethics, and compilation readiness.

### M6 - Submission, Review & Revision

| Stage | Purpose |
|-------|---------|
| `M6S01` | Pre-submission audit and package assembly. |
| `M6S02` | External review submission, for example through `paperreview.ai`. |
| `M6S03` | Review reception and parsing into an atomic review matrix. |
| `M6S04` | Rebuttal strategy and executable action plan. |
| `M6S05` | Revision execution, routed back to earlier stages when needed. |
| `M6S06` | Revision validation and completion verdict. |

**Gate G6** checks whether reviewer concerns have been resolved with traceable evidence.

---

## Gate & Review System

Every module ends with a gate. Gate critics are independent from stage executors.

| Gate | Main Critics |
|------|--------------|
| `G1` | Logic, coverage, survey/source quality |
| `G2` | Logic, method, novelty |
| `G3` | Method, evidence |
| `G4` | Logic, evidence, novelty |
| `G5` | Logic, writing, evidence, novelty, ethics |
| `G6` | Logic, evidence, writing, resolution |

Supported verdicts include `PASS`, `REVISE`, `REWORK`, `BACKTRACK`, `FIX`, and `HALT`.

Stage reviews run inside modules where needed. Reviewers must write their own review file and, for non-PASS verdicts, include structured repair advice that the Conductor can convert into a backtrack.

---

## Dispatch Workflow

The normal runtime loop is:

```bash
python scripts/state_manager.py status
python scripts/state_manager.py dispatch next --write
python scripts/subagent_launch_prompt.py --packet projects/<project>/state/dispatch/<packet>.md
```

Then launch the matching subagent with the compact prompt. The subagent must read the packet and the referenced `docs/AGENTS/**/AGENT.md` file directly. It must not rely on the parent conversation.

Useful dispatch commands:

```bash
python scripts/state_manager.py dispatch stage M2S03 --write
python scripts/state_manager.py dispatch reviews M2S03 --write
python scripts/state_manager.py dispatch gate G2 --write
python scripts/state_manager.py dispatch ssh allocation --write
python scripts/agent_dispatch.py --project projects/<project> --write next
```

Before an orchestrator writes to a project path, check the boundary:

```bash
python scripts/orchestrator_guard.py projects/<project> <target_path>
```

Exit code `1` means the target belongs to a stage executor or reviewer and must be handled through dispatch.

---

## Spiral Backtracking

When a review or gate fails, the Conductor:

1. Records the failure reason and repair contract in `pipeline_state.yaml`.
2. Marks downstream stages as stale.
3. Increments the target module's spiral counter.
4. Generates a new dispatch packet for the target stage.
5. Delegates regeneration to the matching subagent.

Structured backtrack example:

```bash
python scripts/state_manager.py backtrack M3S05 M3S03 \
  "baseline protocol mismatch" \
  --required-fix "Re-lock baselines using the M2S05 metric contract" \
  --success-criteria "M3S03 reports runnable baselines, seeds, metrics, and artifact paths" \
  --rebuild-mode full_regenerate \
  --evidence-paths knowledge/M2/M2S05_experiment_setup.md,experiments/results.tsv
```

Rebuild modes:

- `full_regenerate` - old downstream files are historical audit evidence only.
- `incremental_replay` - old files may be referenced, but retained content must be re-validated against current upstream inputs.

---

## Quick Start

### 1. Clone and install

```bash
git clone git@github.com:qisanjiu/AutoPaper2.git
cd AutoPaper2
pip install -e ".[dev]"
```

Python 3.10+ is required.

### 2. Inspect supported venues

```bash
python scripts/state_manager.py list-venues
```

Supported venue IDs include `arxiv`, `neurips`, `icml`, `iclr`, `acl`, `cvpr`, and `ieee_trans`.

### 3. Create a project

```bash
python scripts/state_manager.py create \
  "Semantic Communication for Image Transmission via Reinforcement Learning" \
  "SemCom-Image-RL" \
  neurips \
  --keywords "semantic communication,reinforcement learning,image compression" \
  --reference "doi:10.0000/example-reference" \
  --foundation "arxiv:2401.00000"
```

Project folders are created under `projects/{sanitized_name}-{YYYYMMDD-HHMMSS}/` unless `SPIRAL_PROJECTS_ROOT` is set.

### 4. Select the project and finish onboarding

```bash
python scripts/state_manager.py list-projects
python scripts/state_manager.py use projects/SemCom-Image-RL-YYYYMMDD-HHMMSS

# Edit project config files:
#   config/execution_env.yaml
#   config/author_info.yaml

python scripts/state_manager.py onboarding-done
```

Project creation auto-runs `scripts/env_probe.py` on a best-effort basis and creates `state/onboarding_checklist.md`.

### 5. Generate and delegate the next task

```bash
python scripts/state_manager.py dispatch next --write
python scripts/subagent_launch_prompt.py --packet projects/<project>/state/dispatch/<packet>.md
```

Pass the printed compact launch prompt to the assigned subagent. After the subagent writes the requested output, use `advance` or the module skill flow to continue.

For high-level orchestration helpers:

```bash
python scripts/state_manager.py run-module M1
python scripts/state_manager.py auto-run
python scripts/state_manager.py set-auto-advance on
```

These helpers still preserve the Conductor-Executor boundary: stage outputs and reviews belong to delegated subagents.

---

## Project Entry & Anchors

Project creation normalizes flexible input into `state/research_brief.yaml`. Downstream stages read that file to understand the topic, keywords, and anchor material.

Supported entry inputs:

```bash
--keywords "keyword1,keyword2"
--reference "paper title, DOI, arXiv id, URL, or local PDF path"
--foundation "baseline or lineage paper/code"
--anchor "both:https://github.com/example/repo"
--input-manifest path/to/manifest.yaml
--note "Important project constraint or user preference"
```

Local PDF anchors are copied into the project input area. Paper and code anchors are assigned recommended stages so survey, method, experiment, and writing agents know where they are relevant.

---

## Project Layout

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

## Configuration

### Venue Registry

Venue settings live in `config/venue_registry.yaml`. Project creation copies the selected venue's LaTeX assets into `artifacts/latex_template/`.

### Execution Environment

Each project receives `config/execution_env.yaml`. It supports:

- `local` mode for current-machine execution.
- `ssh` mode for remote GPU execution.
- Resource-pool planning for mixed local/remote experiment queues.

Common SSH commands:

```bash
python scripts/ssh_manager.py server list
python scripts/ssh_manager.py server add <server_id> --host <host> --user <user>
python scripts/ssh_manager.py probe <server_id>
python scripts/ssh_manager.py lease alloc --project projects/<project> --server-id auto --apply
python scripts/ssh_manager.py lease alloc-pool --project projects/<project> --count 2 --apply
```

Project creation can also request managed SSH allocation:

```bash
python scripts/state_manager.py create "Topic" "Name" neurips \
  --env-mode ssh --server-id auto --lease-hours 48 --min-gpu-count 1
```

### Public Literature Database

`config/public_db.yaml` controls the framework-wide SQLite literature database. It is initialized on first use and shared across projects.

```bash
python scripts/state_manager.py public-db status
python scripts/state_manager.py public-db stats
python scripts/state_manager.py public-db search "semantic communication"
python scripts/state_manager.py public-db import-project projects/<project>
```

M1 survey memory connects to this database so source logs can be reused across projects.

### Figure and Diagram Generation

Figure defaults live in:

- `config/image_generation.yaml`
- `config/figure_style_profiles.yaml`

Local API credentials should go in ignored local config files or environment variables, for example `OPENAI_API_KEY` and `OPENAI_BASE_URL`. `scripts/generate_image.py` supports image-generation and Draw.io-style diagram workflows for M5 figure planning.

---

## Skills & CLI Compatibility

`skills/` is the canonical AutoPaper2 skill source. `.claude/skills/` is a mirror for Claude Code auto-discovery. Non-Claude runtimes should read `AGENTS.md` and then load the relevant `skills/<skill_name>/SKILL.md` directly from this repository.

| Skill | Purpose |
|-------|---------|
| `AutoPaper2_project_onboarding` | Project setup and onboarding checks. |
| `AutoPaper2_project_router` | Route to the correct module based on current state. |
| `AutoPaper2_project_auto_run` | End-to-end orchestration helper. |
| `AutoPaper2_project_backtrack` | Structured manual backtracking. |
| `AutoPaper2_manual_import` | Import literature into the public DB or register shared datasets. |
| `AutoPaper2_env_probe` | Probe local CUDA/Python/GPU environment. |
| `AutoPaper2_ssh_ops` | Manage SSH registry, leases, probes, sync, and remote command evidence. |
| `AutoPaper2_ssh_server_onboarding` | Guided SSH server creation and validation. |
| `AutoPaper2_m1_survey` | Domain survey through G1. |
| `AutoPaper2_m2_method_design` | Method design through G2. |
| `AutoPaper2_m3_experiment` | Implementation and experiments through G3. |
| `AutoPaper2_m4_deep_analysis` | Deep analysis through G4. |
| `AutoPaper2_m5_writing` | Paper writing, compilation, and polish through G5. |
| `AutoPaper2_m6_submission_review` | Submission, review parsing, rebuttal, revision, and G6. |

Validate local skill and prompt compatibility with:

```bash
python scripts/cli_compat_check.py
```

---

## Quality Checks

Recommended checks before changing framework behavior:

```bash
python scripts/cli_compat_check.py
python scripts/agent_consistency_check.py
python scripts/requirement_trace_check.py
python scripts/test_health_check.py
python -m unittest discover -s tests
```

The repository also defines `pytest` configuration in `pyproject.toml`, so `pytest` can be used when the development dependency is installed.

---

## License

MIT
