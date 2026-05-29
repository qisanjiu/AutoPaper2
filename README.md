# AutoPaper2

> **An autonomous research framework that guides a topic from initial scoping all the way through to camera-ready submission and rebuttal.**

AutoPaper2 is a structured, agent-driven pipeline for automated academic research. It breaks the full paper lifecycle into six modules (M1–M6), each with explicit stages, dedicated agents, stage-level reviews, and gate critics. The framework enforces a strict **Conductor–Executor separation**: the main orchestrator schedules work and handles backtracking, while sub-agents execute stage content and reviews.

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [The Six Modules](#the-six-modules)
  - [M1 – Domain Survey](#m1--domain-survey)
  - [M2 – Method Design](#m2--method-design)
  - [M3 – Experiment Implementation & Execution](#m3--experiment-implementation--execution)
  - [M4 – Deep Analysis](#m4--deep-analysis)
  - [M5 – Writing & Finalization](#m5--writing--finalization)
  - [M6 – Submission, Review & Revision](#m6--submission-review--revision)
- [Gate & Review System](#gate--review-system)
- [Spiral Backtracking](#spiral-backtracking)
- [Quick Start](#quick-start)
- [Project Layout](#project-layout)
- [Configuration](#configuration)
- [Skills (Claude Code Integration)](#skills-claude-code-integration)
- [License](#license)

---

## Overview

AutoPaper2 treats paper writing as a **software pipeline**:

1. **State-driven** – every project carries a `pipeline_state.yaml` that records the current module, stage, status, history, and backtrack log.
2. **Agent-specialized** – survey agents, method agents, experiment agents, writing agents, and critic teams each handle their own domain.
3. **Review-gated** – no module can advance to the next until it passes both stage reviews and a final gate review by independent critics.
4. **Self-correcting** – when a review fails, the Conductor initiates a **spiral backtrack** to the appropriate stage, marks downstream work as stale, and re-executes.

---

## System Architecture

```
+------------------+     +------------------+     +------------------+
|   Conductor      |---->|  Sub-Agents      |---->|   Critic Team    |
|  (Orchestrator)  |     | (Stage Execution)|     | (Review & Gate)  |
+------------------+     +------------------+     +------------------+
         |                        |                        |
         v                        v                        v
   pipeline_state.yaml      knowledge/M*             reviews/
   decision_log.md          drafts/                  gate_aggregate.md
   spiral_log.md            experiments/
```

- **Conductor** (`spiral/conductor.py`) – never writes stage outputs directly; only dispatches, schedules, and handles backtracking.
- **State Manager** (`spiral/state.py`) – durable project state with staleness tracking, spiral counters, and gate re-review flags.
- **Project Manager** (`spiral/project.py`) – creates projects, initializes templates, and wires up venue configurations.
- **Dispatch System** (`scripts/state_manager.py`) – generates dispatch packets so sub-agents know exactly what to read and where to write.

---

## The Six Modules

### M1 – Domain Survey

| Stage | Purpose |
|-------|---------|
| **M1S01** | Topic Scoping – define the research question, keywords, and anchor papers. |
| **M1S02** | Literature Deep-Dive – 3-round iterative search with structured source logging. |
| **M1S03** | Gap & Opportunity Analysis – identify unresolved problems. |
| **M1S04** | Pre-Idea Draft – brainstorm solution directions. |
| **M1S05** | Idea Finalization – lock the core claim and approach. |

**Gate G1** – Logic + Coverage Critic reviews completeness of the survey and validity of the gap analysis.

### M2 – Method Design

| Stage | Purpose |
|-------|---------|
| **M2S01** | Cross-Domain Search – find methods from adjacent fields. |
| **M2S02** | Migration Analysis – map external techniques to the target problem. |
| **M2S03** | Method Architecture Design – define the overall pipeline. |
| **M2S04** | Algorithm & Theory Design – formalize objectives, proofs, and complexity. |
| **M2S05** | Experiment Setup Design – datasets, metrics, baselines, and fair-comparison rules. |
| **M2S06** | Full Experiment Plan – consolidate into an executable plan. |

**Gate G2** – Logic + Method + Novelty Critic.

### M3 – Experiment Implementation & Execution

| Stage | Purpose |
|-------|---------|
| **M3S01** | Dataset & Environment Setup – lock dependencies, hardware, and reproducibility config. |
| **M3S02** | Baseline Lock – run baselines and verify fair comparison. |
| **M3S03** | Main Experiment Execution – run the proposed method. |
| **M3S04** | Result Validation & Evidence Packaging – statistical tests, claim-ledgers, and evidence ladders. |

**Gate G3** – Method + Evidence Critic.

### M4 – Deep Analysis

| Stage | Purpose |
|-------|---------|
| **M4S01** | Post-Experiment Audit & Findings Consolidation – summarize all observations. |
| **M4S02** | Deep Analysis Experiment Design – ablations, mechanism studies, robustness tests. |
| **M4S03** | Deep Analysis Execution – run the designed analyses. |
| **M4S04** | Analysis Results Integration – package evidence for the paper. |

**Gate G4** – Logic + Evidence + Novelty Critic.

### M5 – Writing & Finalization

| Stage | Purpose |
|-------|---------|
| **M5S01** | Pre-Write Audit – articulate contributions and pick style-reference papers. |
| **M5S02** | Paper Outline – plotting plan, terminology table, section budget. |
| **M5S04** | Methodology |
| **M5S05** | Experiments & Results |
| **M5S06** | Analysis & Discussion – one-to-one mapping with experiments. |
| **M5S03** | Introduction & Related Work – written after experiments to lock the story. |
| **M5S07** | Abstract & Conclusion |
| **M5S08** | Full Draft Assembly & Compilation – LaTeX build, figure/table checks. |
| **M5S09** | Full-Polish & Narrative Coherence Review – final LaTeX/PDF polish and cross-section consistency. |

**Gate G5** – Logic + Writing + Evidence + Novelty + Ethics Critic. Optional peer-review simulation.

### M6 – Submission, Review & Revision

| Stage | Purpose |
|-------|---------|
| **M6S01** | Pre-Submission Audit & Package Assembly – venue compliance checklist. |
| **M6S02** | External Review Submission – e.g., paperreview.ai. |
| **M6S03** | Review Reception & Parsing – IMAP monitor + atomic review matrix. |
| **M6S04** | Rebuttal Strategy & Action Plan – backtrack planning for each review item. |
| **M6S05** | Revision Execution – routed back to earlier stages as needed. |
| **M6S06** | Revision Validation & Completion Verdict. |

**Gate G6** – Resolution Critic validates that all reviewer concerns are addressed.

---

## Gate & Review System

Every module ends with a **Gate** where independent critics evaluate the work:

| Gate | Critics |
|------|---------|
| G1 | Logic, Coverage |
| G2 | Logic, Method, Novelty |
| G3 | Method, Evidence |
| G4 | Logic, Evidence, Novelty |
| G5 | Logic, Writing, Evidence, Novelty, Ethics |
| G6 | Logic, Evidence, Writing, Resolution |

**Verdicts**: `PASS`, `REVISE`, `REWORK`, `BACKTRACK`, `FIX`, `HALT`.

**Stage Reviews** run *within* a module (e.g., after M2S03 a design-review critic checks consistency with M2S02). This catches errors early rather than letting them accumulate to the gate.

---

## Spiral Backtracking

When a review or gate fails, the Conductor initiates a **backtrack**:

1. Records the reason, required fix, and success criteria in `pipeline_state.yaml`.
2. Marks all downstream stages as **stale**.
3. Increments the **spiral counter** for the target module (default limit = 10).
4. Re-executes the target stage via the appropriate sub-agent with full backtrack advice.

Two rebuild modes:
- **full_regenerate** – treat old files as historical audit only; no copy-paste.
- **incremental_replay** – may reference old files, but all retained content must be re-validated.

---

## Quick Start

### 1. Clone & Install

```bash
git clone git@github.com:qisanjiu/AutoPaper2.git
cd AutoPaper2
pip install -e ".[dev]"
```

### 2. Create a Project

```python
from spiral.project import ProjectManager

proj = ProjectManager.create(
    topic="Semantic Communication for Image Transmission via Reinforcement Learning",
    display_name="SemCom-Image-RL",
    venue="neurips",          # or arxiv, icml, iclr, acl, cvpr, ieee_trans
    keywords=["semantic communication", "reinforcement learning", "image compression"],
)
print(proj)
```

### 3. Check State & Onboarding

```bash
python scripts/state_manager.py status
# Complete config/execution_env.yaml and config/author_info.yaml
python scripts/state_manager.py onboarding-done /path/to/project
```

### 4. Run a Module (via Claude Code Skills)

```
/AutoPaper2_m1_survey   # Start Domain Survey
/AutoPaper2_m2_method_design  # After M1 completes
/AutoPaper2_m3_experiment     # After M2 completes
...
```

Or run manually:

```bash
python scripts/state_manager.py run-module M1
```

---

## Project Layout

Each project is created under `projects/{sanitized_name}-{YYYYMMDD-HHMMSS}/`:

```
my-project-20260115-143022/
├── state/
│   ├── pipeline_state.yaml      # Global state
│   ├── decision_log.md          # Human-readable decisions
│   ├── spiral_log.md            # Backtrack history
│   └── onboarding_checklist.md
├── knowledge/
│   ├── M1/ ... M6/              # Stage outputs
│   └── reviews/                 # Stage & gate reviews
├── drafts/
│   └── M1S01/ ... M6S06/        # Working drafts
├── experiments/
│   ├── results.tsv
│   ├── analysis_results.tsv
│   ├── src/
│   └── configs/
├── artifacts/
│   ├── paper.tex
│   ├── paper.pdf
│   ├── refs.bib
│   └── latex_template/          # Venue-specific LaTeX files
└── config/
    ├── execution_env.yaml       # Hardware, SSH, conda, etc.
    └── author_info.yaml
```

---

## Configuration

### Venue Registry

Supported venues are defined in `config/venue_registry.yaml`:

| Venue | Page Limit | Format |
|-------|-----------|--------|
| arXiv | – | preprint |
| NeurIPS | 9 + refs | conference |
| ICML | 9 + refs | conference |
| ICLR | 9 + refs | conference |
| ACL | 8 + refs | conference |
| CVPR | 8 + refs | conference |
| IEEE Trans | ~10–14 | journal |

### Execution Environment

`config/execution_env.yaml` (auto-generated per project) supports:
- **local** mode – run on the current machine.
- **ssh** mode – dispatch experiments to a remote GPU server.

Environment is auto-probed on project creation (`scripts/env_probe.py` detects CUDA, Python version, GPU count, and framework versions).

---

## Skills (Claude Code Integration)

AutoPaper2 is designed to run as a set of **Claude Code Skills** under `.claude/skills/` and `skills/`:

| Skill | Purpose |
|-------|---------|
| `AutoPaper2_env_probe` | Detect local GPU/Python/CUDA and fill `execution_env.yaml`. |
| `AutoPaper2_m1_survey` | Full M1 pipeline: topic scoping → literature search → ideation → G1. |
| `AutoPaper2_m2_method_design` | Full M2 pipeline: cross-domain search → migration → architecture → G2. |
| `AutoPaper2_m3_experiment` | Full M3 pipeline: env setup → baselines → main experiments → G3. |
| `AutoPaper2_m4_deep_analysis` | Full M4 pipeline: audit → ablation design → execution → G4. |
| `AutoPaper2_m5_writing` | Full M5 pipeline: outline → section drafting → compilation → G5. |
| `AutoPaper2_m6_submission_review` | Full M6 pipeline: submission → review parsing → rebuttal → revision → G6. |
| `AutoPaper2_project_auto_run` | Run all modules end-to-end automatically. |
| `AutoPaper2_project_backtrack` | Handle manual backtrack requests. |
| `AutoPaper2_project_router` | Route to the correct module based on current state. |

---

## License

MIT
