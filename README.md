# AutoPaper2 — End-to-End Autonomous Research Paper Generation Framework

> **Version**: 0.1.0  
> **Core Philosophy**: 6-Module spiral progression, deepResearch-inspired memory & iteration, 3-layer critique  
> **Language**: English docs / 中文文档见 [README_CN.md](README_CN.md)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Architecture Overview](#architecture-overview)
3. [Detailed Pipeline](#detailed-pipeline)
   - [M1 Domain Survey](#m1-domain-survey)
   - [M2 Method Design](#m2-method-design)
   - [M3 Experiment](#m3-experiment)
   - [M4 Deep Analysis](#m4-deep-analysis)
   - [M5 Writing & Review](#m5-writing--review)
   - [M6 Submission & Rebuttal](#m6-submission--rebuttal)
4. [Core Mechanisms](#core-mechanisms)
   - [Survey Memory Persistence](#survey-memory-persistence)
   - [Backtrack Mechanism](#backtrack-mechanism)
   - [Gate Review](#gate-review)
   - [Public Literature DB](#public-literature-db)
5. [Quick Start](#quick-start)
6. [CLI Reference](#cli-reference)
7. [Project Structure](#project-structure)
8. [Configuration](#configuration)
9. [Development & Testing](#development--testing)
10. [License](#license)

---

## Introduction

AutoPaper2 is an **end-to-end autonomous research paper generation framework**. It reconstructs the complete research workflow into **6 Modules, 33 Stages, and 6 Gates**, using multi-Agent collaboration and a three-layer Critic review mechanism to automatically complete the entire process from domain survey, method design, experiment execution, deep analysis, to paper writing and submission.

### Improvements over AutoPaper

| Feature | AutoPaper | **AutoPaper2** |
|:---|:---|:---|
| Phase division | 8 Phases × 37 Stages | **6 Modules × 33 Stages** |
| Survey memory | ❌ None | ✅ **Persistent `survey_memory.yaml`** |
| Iterative search | ❌ Single pass | ✅ **3-Round Search→Verify→Iterate loop** |
| Source tracking | ❌ Embedded in Markdown | ✅ **Structured `M1_source_log.yaml`** |
| Coverage review | ❌ Not checked | ✅ **Gate G1 Coverage Critic** |
| Backtrack mechanism | ❌ Simple retry | ✅ **Full Backtrack + Spiral Count** |
| Public literature DB | ❌ None | ✅ **SQLite + FTS cross-project reuse** |
| Submission module | ❌ None | ✅ **M6 external review & revision loop** |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AutoPaper2 Six-Module Pipeline                       │
├─────────┬─────────┬─────────┬─────────┬─────────┬─────────────────────┤
│   M1    │   M2    │   M3    │   M4    │   M5    │        M6           │
│ Domain  │ Method  │  Exp.   │  Deep   │ Writing │  Submission &       │
│ Survey  │ Design  │  Run    │ Analysis│ & Review│  Rebuttal           │
├─────────┼─────────┼─────────┼─────────┼─────────┼─────────────────────┤
│ M1S01   │ M2S01   │ M3S01   │ M4S01   │ M5S01   │ M6S01 Submission    │
│ M1S02   │ M2S02   │ M3S02   │ M4S02   │ M5S02   │      Audit          │
│ M1S03   │ M2S03   │ M3S03   │ M4S03   │ M5S03   │ M6S02 External      │
│ M1S04   │ M2S04   │ M3S04   │ M4S04   │ M5S04   │      Review Submit  │
│ M1S05   │ M2S05   │   ↓     │   ↓     │ M5S05   │ M6S03 Review        │
│   ↓     │ M2S06   │   G3    │   G4    │ M5S06   │      Parsing        │
│   G1    │   ↓     │         │         │ M5S07   │ M6S04 Rebuttal      │
│         │   G2    │         │         │ M5S08   │      Strategy       │
│         │         │         │         │   ↓     │ M6S05 Revision      │
│         │         │         │         │   G5    │      Execution      │
│         │         │         │         │         │ M6S06 Revision      │
│         │         │         │         │         │      Validation     │
│         │         │         │         │         │   ↓                 │
│         │         │         │         │         │   G6                │
└─────────┴─────────┴─────────┴─────────┴─────────┴─────────────────────┘
```

**Core Design Principles**:
- **Conductor only orchestrates, never executes**: The main Agent handles project creation, module routing, stage advancement, backtrack scheduling, gate handling, and **never directly executes stage content or review work**
- **Stage execution delegated to subagents**: Each stage is executed by the corresponding role subagent (Survey / Method / Experiment / Analysis / Writing, etc.)
- **Independent review layer**: Stage-level review + Gate Critic + Human Review, three layers of quality control
- **Traceable backtracking**: All backtracks are persisted to `pipeline_state.yaml`, with Spiral Count limits

---

## Detailed Pipeline

### M1 Domain Survey

> **Goal**: comprehensively survey the research field, identify research gaps, and produce a structured literature review  
> **Agents**: Survey Agent + Ideation Agent  
> **Gate**: G1 (Logic + Novelty + Coverage + Survey Review)

| Stage | Name | Description |
|:---|:---|:---|
| **M1S01** | Topic Scoping | Define research topic, keywords, search strategy, and expected contribution type |
| **M1S02** | Literature Deep Dive | Execute **3-Round iterative search**: Round 1 Breadth scan → Round 2 Depth validation → Round 3 Blindspot filling. Each round requires independent Reviewer verdict = PASS to proceed |
| **M1S03** | Research Question | Transform identified gaps into concrete, testable research questions |
| **M1S04** | Hypothesis Generation | Generate research hypotheses with independent variables, dependent variables, and expected effects |
| **M1S05** | Novelty & Feasibility | Argue novelty and feasibility, complete M1 deliverable integration |

**Key Outputs**:
- `knowledge/M1/M1S01_topic_scoping.md`
- `knowledge/M1/M1S02_literature_deepdive.md`
- `knowledge/M1/M1_source_log.yaml` — structured source log
- `state/survey_memory.yaml` — persistent survey memory (search_batches, round_reviews, findings)
- `knowledge/M1/M1S03_research_question.md`
- `knowledge/M1/M1S04_hypothesis_generation.md`
- `knowledge/M1/M1S05_novelty_feasibility.md`
- `knowledge/handoff_M1_M2.md`

---

### M2 Method Design

> **Goal**: based on gaps identified in M1, design rigorous, reproducible, and hypothesis-testable research methods through cross-domain search, idea migration, and method synthesis  
> **Agent**: Method Agent  
> **Gate**: G2 (Logic + Method + Novelty)

| Stage | Name | Description |
|:---|:---|:---|
| **M2S01** | Cross-Domain Search | Cross-domain literature search to find transferable technical ideas |
| **M2S02** | Method Inspiration | Multi-paper inspiration integration and adaptation, forming preliminary proposals |
| **M2S03** | Method Architecture | Method architecture design: module decomposition, data flow, interface definitions |
| **M2S04** | Algorithm & Theory | Algorithm details and theoretical analysis: convergence, complexity, boundary conditions |
| **M2S05** | Experiment Setup | Experiment setup design: datasets, evaluation metrics, hyperparameters, reproduction environment |
| **M2S06** | Full Experiment Plan | Integrate complete experiment plan, output M2→M3 handoff document |

**Stage Review Mechanism**:
- M2S01 → `m2_search_quality` review
- M2S02 → `m2_migration` review (bridge review, checks cross-domain mapping rationality)
- M2S03 → `m2_design_review` review
- M2S04 → `m2_design_review` review

**Key Outputs**:
- `knowledge/M2/M2S01_cross_domain_search.md`
- `knowledge/M2/M2S02_method_inspiration.md`
- `knowledge/M2/M2S03_method_architecture.md`
- `knowledge/M2/M2S04_algorithm_theory.md`
- `knowledge/M2/M2S05_experiment_setup.md`
- `knowledge/M2/M2S06_full_experiment_plan.md`
- `knowledge/M2/M2_source_log.yaml`
- `knowledge/handoff_M2_M3.md`

---

### M3 Experiment

> **Goal**: correctly and efficiently implement the method designed in M2, run experiment iteration loops, and produce credible empirical evidence  
> **Agent**: Experiment Agent  
> **Gate**: G3 (Method + Evidence)

| Stage | Name | Description |
|:---|:---|:---|
| **M3S01** | Implementation | Code implementation and environment setup: dependency locking, dataset acquisition, data pipeline |
| **M3S02** | Baseline Lock | Baseline reproduction and locking: ensure baselines run, establish metric contract, pass smoke test |
| **M3S03** | Main Experiment | Main experiment execution: full training/evaluation pipeline, multiple random seeds, result logging |
| **M3S04** | Result Validation | Result validation and evidence packaging: statistical significance tests, negative result logging, decision (KEEP / FIX / BACKTRACK) |

**Stage Review Mechanism**:
- M3S01 → `m3_dataset_env_review` review
- M3S02 → `m3_baseline_result_review` review
- M3S03 → `m3_main_result_review` review

**M3S04 Decision Enforcement**:
- If M3S04 output decision is `FIX` or `BACKTRACK`, it **must** include complete `backtrack direction` and repair fields, otherwise `advance` will be blocked
- Decision must be `KEEP` to normally proceed to M4

**Key Outputs**:
- `knowledge/M3/M3S01_implementation.md`
- `knowledge/M3/M3S02_baseline_lock.md`
- `knowledge/M3/M3S03_main_experiment.md`
- `knowledge/M3/M3S04_result_validation.md`
- `knowledge/handoff_M3_M4.md`

---

### M4 Deep Analysis

> **Goal**: extract reliable conclusions from experimental results, identify patterns, and deepen insights through ablation studies, mechanism analysis, and robustness checks  
> **Agents**: Analysis Agent + Experiment Agent (M4S03)  
> **Gate**: G4 (Logic + Evidence + Novelty)

| Stage | Name | Description |
|:---|:---|:---|
| **M4S01** | Other Findings | Post-experiment audit: data quality audit, claim screening, negative result integration |
| **M4S02** | Analysis Experiment Design | Deep analysis experiment design: ablation studies, mechanism visualization, robustness checks, slice evidence contract |
| **M4S03** | Analysis Experiment | Deep analysis experiment execution |
| **M4S04** | Analysis Results | Analysis results integration and evidence packaging |

**Stage Review Mechanism**:
- M4S01 → `m4_findings_audit` review
- M4S02 → `m4_analysis_design_review` review
- M4S03 → `m4_analysis_execution_review` review

**Key Outputs**:
- `knowledge/M4/M4S01_other_findings.md`
- `knowledge/M4/M4S02_analysis_experiment_design.md`
- `knowledge/M4/M4S03_analysis_experiment.md`
- `knowledge/M4/M4S04_analysis_results.md`
- `knowledge/handoff_M4_M5.md`

---

### M5 Writing & Review

> **Goal**: transform research results into a clearly structured, rigorously argued academic paper conforming to venue specifications  
> **Agents**: Analysis Agent (M5S01) + Writing Agent (M5S02-M5S08) + Build Verifier (M5S08)  
> **Gate**: G5 (Logic + Writing + Evidence + Novelty + Ethics)

| Stage | Name | Description |
|:---|:---|:---|
| **M5S01** | Pre-Write Audit | Pre-writing audit: contribution梳理, evidence chain completeness check, terminology unification |
| **M5S02** | Paper Outline | Paper outline: plotting plan, terminology glossary, section budget |
| **M5S03** | Introduction & Related Work | Introduction and related work |
| **M5S04** | Methodology | Methodology section + method figures |
| **M5S05** | Experiments & Results | Experiments and results section |
| **M5S06** | Analysis & Discussion | Analysis and discussion section |
| **M5S07** | Abstract & Conclusion | Abstract and conclusion |
| **M5S08** | Final Compilation | Full draft assembly, LaTeX compilation, PDF generation |

**Stage Review Mechanism**:
- M5S01 → `m5_prewrite_review`
- M5S02 → `m5_outline_style_review`
- M5S03 → `m5_intro_relatedwork_review`
- M5S04 → `m5_method_figure_review`
- M5S05 → `m5_experiments_results_review`
- M5S06 → `m5_analysis_discussion_review`
- M5S07 → `m5_abstract_conclusion_review`
- M5S08 → `build_verifier` + `m5_final_compilation_review`

**Key Outputs**:
- `knowledge/M5/M5S01_pre_write_audit.md` ~ `M5S08_final_compilation.md`
- `artifacts/paper.tex`
- `artifacts/paper.pdf`
- `knowledge/handoff_M5_completion.md`

---

### M6 Submission & Rebuttal

> **Goal**: complete pre-submission audit, external review submission, review parsing, backtrack planning, revision execution and validation  
> **Agents**: Submission Agent (M6S01-M6S02) + Rebuttal Agent (M6S03-M6S06)  
> **Gate**: G6 (Logic + Evidence + Writing + Resolution)

| Stage | Name | Description |
|:---|:---|:---|
| **M6S01** | Submission Audit | Pre-submission audit: submission package completeness, venue format compliance |
| **M6S02** | External Review Submission | External review submission (e.g., paperreview.ai) |
| **M6S03** | Review Parsing | Review reception and parsing + Review Matrix atomization |
| **M6S04** | Rebuttal Strategy | Backtrack planning and rebuttal strategy + executable Action Plan |
| **M6S05** | Revision Execution | Revision execution |
| **M6S06** | Revision Validation | Revision validation and completion verdict |

**Stage Review Mechanism**:
- M6S01 → `m6_submission_audit`
- M6S02 → `m6_external_submission_review`
- M6S03 → `m6_review_parsing_review`
- M6S04 → `m6_rebuttal_strategy_review`
- M6S05 → `m6_revision_execution_review`
- M6S06 → `m6_revision_validation_review`

**Key Outputs**:
- `knowledge/M6/M6S01_submission_audit.md` ~ `M6S06_revision_validation.md`
- `knowledge/M6/M6S03_review_matrix.md`
- `knowledge/M6/M6S04_action_plan.md`
- `knowledge/handoff_M6_completion.md`

---

## Core Mechanisms

### Survey Memory Persistence

Inspired by deepResearch, AutoPaper2 introduces a **SurveyMemory** persistence system in the M1 phase:

```yaml
# state/survey_memory.yaml
topic: "Semantic Communication for Image Transmission"
status: completed
search_batches:
  - batch_id: 1
    round: 1
    status: passed
    queries: ["semantic communication overview", "deep JSCC image"]
    sources_found: 12
round_reviews:
  - round: 1
    verdict: PASS
    score: 0.85
findings:
  key_claims: [...]
  gaps:
    - id: "gap_1"
      description: "Existing methods lack adaptive modulation under varying channels"
      gap_type: enhancement
      target_component: "modulation module"
      baseline_framework: "DeepJSCC"
      bottleneck_description: "Fixed code length cannot adapt to SNR variations"
  contradictions: [...]
source_registry:
  smith2023deepjscc:
    title: "Deep Joint Source-Channel Coding"
    credibility_score: 5
    verification_status: confirmed
    ...
```

**Gap Type System**:
- **VG (Vacancy Gap)**: A sub-field completely unexplored
- **EG (Enhancement Gap)**: A component in existing methods has a bottleneck that needs improvement
- **ValG (Validation Gap)**: A conclusion only holds under specific settings and needs broader validation

### Backtrack Mechanism

When Stage Review or Gate Critic issues a non-PASS verdict (REVISE / REWORK / BACKTRACK / FIX), the Conductor triggers a Backtrack.

**Automated Backtrack** (from Stage Review / Gate):
Stage review markdown files are parsed by **`VerdictParser`** (`spiral/verdict_parser.py`), a standalone, stateless parser. Conductor only makes orchestration decisions based on parsed results--it never parses markdown itself.

**Human Backtrack** now supports the same structured advice protocol as automated reviews:

```bash
# Simple mode (backward compatible, shows WARN)
python scripts/state_manager.py backtrack M2S06 M2S03 \
  "Baseline mismatch" \
  "Switch to transformer-based baseline"

# Structured CLI flags
python scripts/state_manager.py backtrack M2S06 M2S03 \
  "Baseline mismatch" \
  --required-fix "Re-run baseline with official config" \
  --success-criteria "Primary metric within 1% of paper" \
  --rebuild-mode incremental_replay \
  --rerun-scope "M3S01-M3S03" \
  --evidence-paths "experiments/baseline_wrong.log"

# Via structured review file (parsed by VerdictParser)
python scripts/state_manager.py backtrack M2S06 M2S03 "bug found" \
  --review-file knowledge/reviews/human_m3s03_review.md
```

The review file format is identical to automated stage reviews:
```markdown
**Verdict**: BACKTRACK
**blocking_reason**: ...
**required_fix**: ...
**success_criteria**: ...
**rebuild_mode**: full_regenerate
**rerun_scope**: ...
**evidence_paths**: ...
```

**Backtrack Side Effects**:
1. Marks all downstream stages between `to_stage` and `from_stage` as **stale**
2. Resets target module status to `reopened`
3. Records to `backtrack_log`, increments `spiral_count`
4. If `spiral_count >= 10` for the same module, triggers **HALT** (human intervention required)

**Rebuild Mode**:
- `full_regenerate` (default): subagent must treat old downstream files as historical audit only; no copy-paste allowed
- `incremental_replay`: subagent may reference old files to reduce redundancy, but all retained content must be re-validated

### Auto-Advance Mode

When `auto_advance_modules` is enabled (via `--auto-advance` at creation or `set-auto-advance on`), Conductor automatically transitions to the next module's first stage when a module completes--**no `WAIT_USER` interruption**.

```bash
# Enable at project creation
python scripts/state_manager.py create "Topic" "Name" --auto-advance

# Toggle on existing project
python scripts/state_manager.py set-auto-advance on
python scripts/state_manager.py set-auto-advance off
```

**Use cases**: full-auto skill execution, overnight batch runs, spiral iteration loops after backtrack.

**Still requires human intervention even with auto-advance ON**:
- Gate returns HALT
- Spiral limit reached (>=10 backtracks in same module)
- Stage review / file_guard failure (unless `--force`)

### Gate Review

Each module's last stage is a **Gate Stage**, requiring aggregated review by the Critic Team:

| Gate | Stage | Critics |
|:---|:---|:---|
| G1 | M1S05 | Logic, Novelty, Coverage, Survey Review |
| G2 | M2S06 | Logic, Method, Novelty |
| G3 | M3S04 | Method, Evidence |
| G4 | M4S04 | Logic, Evidence, Novelty |
| G5 | M5S08 | Logic, Writing, Evidence, Novelty, Ethics |
| G6 | M6S06 | Logic, Evidence, Writing, Resolution |

**Gate Verdict Types**:
- **PASS**: all passed, proceed to next module
- **REVISE**: minor revision, backtrack to specified stage
- **FIX**: moderate fix, backtrack to module start or specified stage
- **BACKTRACK**: major revision, backtrack to module start
- **HALT**: terminate, human intervention required

Gate reviews produce `knowledge/reviews/{G}_aggregate.md`, used as the Gate Stage output file during `advance`.

### Public Literature DB

AutoPaper2 includes a framework-level **SQLite + FTS5** public literature database supporting cross-project literature reuse:

```bash
# Check database status
python scripts/state_manager.py public-db status

# Search literature
python scripts/state_manager.py public-db search "transformer time series"

# Import project source log into public DB
python scripts/state_manager.py public-db import-project projects/YourProject

# View statistics
python scripts/state_manager.py public-db stats
```

**Manual Import**:

You can also manually import papers or datasets via the `AutoPaper2_manual_import` skill:

```text
Import literature into the public database
```

```text
Register a new dataset CIFAR-100
```

```text
Manually add the paper "Attention Is All You Need" to the public DB
```

For detailed instructions, see `skills/AutoPaper2_manual_import/SKILL.md`.

**Dataset Cache Management**:

```bash
# View registered datasets
cat data/datasets/.dataset_registry.yaml

# Validate registry syntax
python -c "import yaml; yaml.safe_load(open('data/datasets/.dataset_registry.yaml'))"

# Verify dataset checksum (example)
cd data/datasets/cifar-10
md5sum cifar-10-python.tar.gz | grep "c58f30108f718f92721af3b95e74349a"
```

**Core Features**:
- Automatic deduplication (based on DOI / arXiv ID / title similarity)
- Merge strategy (credibility-weighted, limitation deduplication, longest title)
- Query caching (avoid repeated searches)
- Automatic tagging (keyword matching based on title/abstract)
- Full-text search (FTS5)

---

## Quick Start

### Environment Setup

```bash
# Install dependencies after cloning
pip install -e ".[dev]"

# Or install only runtime dependencies
pip install pyyaml pydantic requests
```

### Creating a New Project

#### Method 1: Trigger M1 Skill in Chat

AutoPaper2's new project entry is handled by the `AutoPaper2_m1_survey` skill. You can trigger it with natural language:

```text
Start a new project on "Semantic Communication with Reinforcement Learning for Adaptive Image Transmission", short name SemCom-Image-RL.
```

```text
Start a survey on "adaptive transmission in image semantic communication", keywords include DeepJSCC, semantic communication, reinforcement learning.
```

If the project is based on an existing paper, explicitly use "based on / build upon / foundation":

```text
Start a new project: topic is "adaptive image semantic communication".
I want to build upon the paper "Deep Joint Source-Channel Coding for Wireless Image Transmission".
```

If a paper is only for reference, not inheritance, explicitly use "reference":

```text
Start a new project: topic is "Transformer time-series forecasting".
Reference paper: "Informer: Beyond Efficient Transformer for Long Sequence Time-Series Forecasting".
```

You can also provide both foundation and reference, or PDF, URL, arXiv, DOI, GitHub:

```text
Start a new project, topic is "efficient reranking in multimodal retrieval".
foundation: /home/me/papers/base_method.pdf
reference: https://arxiv.org/abs/2401.00000
code reference: https://github.com/example/repo
```

The skill will create the project and write entry information to `state/research_brief.yaml`. Subsequent M1/M2/M5 stages will treat foundation papers as the method inheritance line and reference papers as near-neighbor comparisons and writing references.

#### Method 2: Minimal CLI

```bash
python scripts/state_manager.py create \
  "Semantic Communication with Reinforcement Learning for Adaptive Image Transmission" \
  "SemCom-Image-RL"
```

#### Method 3: CLI with Keywords, Foundation, Reference, GitHub

```bash
python scripts/state_manager.py create \
  "Semantic Communication with Reinforcement Learning for Adaptive Image Transmission" \
  "SemCom-Image-RL" \
  --keywords "semantic communication, DeepJSCC, reinforcement learning" \
  --foundation "Deep Joint Source-Channel Coding for Wireless Image Transmission" \
  --reference "https://arxiv.org/abs/xxxx.xxxxx" \
  --anchor reference:https://github.com/example/repo
```

Common parameters:

| Parameter | Meaning | Example |
|:---|:---|:---|
| `--keywords` | Entry keywords, comma-separated | `--keywords "DeepJSCC, semantic communication"` |
| `--foundation` / `--base` | Base paper to inherit or extend | `--foundation "Paper Title"` |
| `--reference` / `--ref` | Reference paper, not treated as main baseline by default | `--reference "https://arxiv.org/abs/xxxx.xxxxx"` |
| `--anchor` | Generic anchor, supports `foundation:` / `reference:` / `both:` prefix | `--anchor both:/path/paper.pdf` |
| `--input-manifest` | Read entry info from YAML manifest | `--input-manifest seed.yaml` |
| `--note` | Additional entry note | `--note "focus on low-SNR image transmission"` |
| `--venue` | Specify submission venue | `--venue iclr` |

`--foundation` / `--reference` / `--anchor` values can be paper titles, local PDF paths, URLs, arXiv/DOI, or GitHub addresses. Local PDFs are copied to the project's `artifacts/inputs/`.

#### Method 4: Batch Create with Entry Manifest

When entry information is extensive, create a YAML file, e.g., `seed.yaml`:

```yaml
keywords:
  - semantic communication
  - DeepJSCC
  - adaptive transmission
foundation_papers:
  - value: /home/me/papers/base_method.pdf
    notes: "Primary inheritance target"
reference_papers:
  - value: "A Survey on Semantic Communications"
anchors:
  - role: both
    value: https://arxiv.org/abs/xxxx.xxxxx
  - role: reference
    value: https://github.com/example/repo
notes: "Focus on image transmission and low-SNR robustness."
```

Then create the project:

```bash
python scripts/state_manager.py create \
  "Adaptive Image Semantic Communication" \
  "AISemCom" \
  --input-manifest seed.yaml
```

The project is created at `projects/{sanitized_name}-{YYYYMMDD-HHMMSS}/`, automatically initializing:
- `state/pipeline_state.yaml` — global state
- `state/survey_memory.yaml` — survey memory
- `state/research_brief.yaml` — project entry manifest (keywords, foundation/reference anchors, PDF/URL/GitHub clues)
- `knowledge/M1/` ~ `M6/` — module knowledge directories
- `drafts/M1S01/` ~ `M6S06/` — stage draft directories
- `artifacts/` — final artifacts (LaTeX/PDF)

### Checking Project Status

```bash
# View current stage and status
python scripts/state_manager.py status --project projects/SemCom-Image-RL-20260512-135033

# View module completion status
python scripts/state_manager.py module-status --project projects/SemCom-Image-RL-20260512-135033

# Set current project (subsequent commands can omit --project)
python scripts/state_manager.py use projects/SemCom-Image-RL-20260512-135033
python scripts/state_manager.py status
```

### Running Stages (Subagent Execution)

```bash
# View auto-execution plan for current stage
python scripts/state_manager.py auto-stage M1S01

# Run an entire module
python scripts/state_manager.py run-module M1

# View full run plan from current stage
python scripts/state_manager.py auto-run
```

### Advancing Stages

When a subagent completes stage output, use `advance` to proceed:

```bash
# Normal stage advancement
python scripts/state_manager.py advance M1S01 survey \
  knowledge/M1/M1S01_topic_scoping.md

# Gate stage advancement (submit aggregate review file)
python scripts/state_manager.py advance M1S05 ideation \
  knowledge/reviews/G1_aggregate.md

# Force skip checks (not recommended, debug only)
python scripts/state_manager.py advance M1S01 survey \
  knowledge/M1/M1S01_topic_scoping.md --force
```

### Human Review & Backtracking

```bash
# Submit human review (revise or backtrack)
python scripts/state_manager.py human-review M2S03 \
  "Method architecture lacks comparison with transformer-based baselines" \
  revise

# Manually trigger backtrack
python scripts/state_manager.py backtrack M2S06 M2S03 \
  "Baseline mismatch: selected CNN baseline cannot handle variable input size" \
  "Switch to transformer-based baseline and redesign encoder"

# View backtrack plan (no execution)
python scripts/state_manager.py auto-backtrack M2S06 M2S03 \
  "Need to redesign method" "Redesign attention mechanism"
```

---

## CLI Reference

### Command Overview

```bash
python scripts/state_manager.py <command> [args...]
```

| Command | Description |
|:---|:---|
| `create <topic> <display_name> [venue] [--keywords ...] [--foundation ...] [--reference ...] [--anchor ...] [--input-manifest ...]` | Create new project |
| `status` | View current project status |
| `module-status` | View module completion status |
| `advance <stage> <agent> <output_file>` | Advance stage |
| `human-review <stage> <opinion> [verdict]` | Submit human review |
| `auto-stage <stage>` | View stage auto-execution plan |
| `auto-module <module>` | View module auto-execution plan |
| `auto-backtrack <from> <to> <reason> [direction]` | Preview backtrack plan |
| `auto-run` | View full run plan from current stage |
| `run-module <module>` | Start module execution |
| `list-projects` | List all projects |
| `use <project_dir>` | Set current project |
| `list-venues` | List supported venues |
| `set-venue <venue_id>` | Set project venue |
| `backtrack <from> <to> <reason> [direction]` | Execute backtrack |
| `public-db status/stats/init/import-project/list-papers/search/show-paper/list-tags` | Public literature DB operations |
| `AutoPaper2_manual_import` (Skill) | Manual import of papers or datasets — triggered by natural language |

### Global Options

```bash
# All commands support --project to specify project directory
python scripts/state_manager.py status --project /path/to/project

# advance supports --force (skip file_guard/stage_gate) and --skip-gates
python scripts/state_manager.py advance M1S01 survey output.md --force --skip-gates
```

### Venue Configuration

The framework includes the following venue templates:

| Venue | Page Limit | Type |
|:---|:---|:---|
| arxiv | Unlimited | Preprint |
| NeurIPS | 9 pages + references + appendix | Conference |
| ICML | 9 pages + references + appendix | Conference |
| ICLR | 9 pages + references + appendix | Conference |
| ACL | 8 pages + references + appendix | Conference |
| CVPR | 8 pages + references + appendix | Conference |
| IEEE Trans | 10-14 pages | Journal |

---

## Project Structure

```
AutoPaper2/
├── spiral/                      # Core Python package
│   ├── __init__.py
│   ├── conductor.py             # Orchestration core (Conductor)
│   ├── state.py                 # PipelineState state management
│   ├── project.py               # ProjectManager lifecycle
│   ├── survey_memory.py         # SurveyMemory survey memory system
│   └── public_db/               # Public literature database
│       ├── config.py
│       ├── manager.py
│       ├── models.py
│       ├── db.py
│       ├── identifier.py
│       ├── importer.py
│       ├── merge.py
│       ├── query_cache.py
│       └── tag_engine.py
├── scripts/
│   ├── state_manager.py         # CLI entry
│   ├── conductor_helper.py      # Cross-stage input resolution
│   ├── test_health_check.py     # Test health check
│   └── agent_consistency_check.py  # Agent consistency check
├── utils/
│   ├── file_guard.py            # Naming & location validation
│   ├── stage_gate.py            # Stage quality checks
│   └── source_log_validator.py  # Source log validation
├── docs/
│   ├── AGENTS/                  # Agent identity definitions
│   │   ├── survey/AGENT.md
│   │   ├── method/AGENT.md
│   │   ├── experiment/AGENT.md
│   │   ├── analysis/AGENT.md
│   │   ├── writing/AGENT.md
│   │   ├── submission/AGENT.md
│   │   ├── rebuttal/AGENT.md
│   │   ├── ideation/AGENT.md
│   │   ├── conductor/AGENT.md
│   │   ├── build_verifier/AGENT.md
│   │   └── critic/              # Critic Agent definitions
│   │       ├── logic/AGENT.md
│   │       ├── method/AGENT.md
│   │       ├── novelty/AGENT.md
│   │       ├── coverage/AGENT.md
│   │       ├── writing/AGENT.md
│   │       ├── ethics/AGENT.md
│   │       ├── evidence/AGENT.md
│   │       ├── g6_resolution/AGENT.md
│   │       ├── source_log_validator/AGENT.md
│   │       ├── m2_search_quality/AGENT.md
│   │       ├── m2_migration/AGENT.md
│   │       ├── m2_design_review/AGENT.md
│   │       ├── m3_dataset_env_review/AGENT.md
│   │       ├── m3_baseline_result_review/AGENT.md
│   │       ├── m3_main_result_review/AGENT.md
│   │       ├── m4_findings_audit/AGENT.md
│   │       ├── m4_analysis_design_review/AGENT.md
│   │       ├── m4_analysis_execution_review/AGENT.md
│   │       ├── m5_stage_review/AGENT.md
│   │       └── m6_stage_review/AGENT.md
│   └── design/                  # Design documents
│       ├── M2_MODULE_DESIGN.md
│       ├── M3_MODULE_DESIGN.md
│       └── public_literature_db_design.md
├── config/
│   ├── venue_registry.yaml      # Venue configuration
│   ├── public_db.yaml           # Public DB configuration
│   ├── execution_env.yaml       # Execution environment config
│   ├── figure_style_profiles.yaml
│   └── author_info.yaml
├── templates/
│   ├── stage/                   # Stage Markdown templates (33)
│   │   ├── M1S01_template.md
│   │   ├── M1S02_template.md
│   │   └── ...
│   └── venue/                   # Venue LaTeX templates
│       ├── arxiv/
│       ├── neurips/
│       ├── icml/
│       └── ...
├── skills/                      # Execution skills (M1-M6)
│   ├── AutoPaper2_m1_survey/SKILL.md
│   ├── AutoPaper2_m2_method_design/SKILL.md
│   ├── AutoPaper2_m3_experiment/SKILL.md
│   ├── AutoPaper2_m4_deep_analysis/SKILL.md
│   ├── AutoPaper2_m5_writing/SKILL.md
│   └── AutoPaper2_m6_submission_review/SKILL.md
├── projects/                    # All research projects
│   └── {name}-{YYYYMMDD-HHMMSS}/
│       ├── state/
│       │   ├── pipeline_state.yaml
│       │   ├── survey_memory.yaml
│       │   ├── decision_log.md
│       │   └── spiral_log.md
│       ├── knowledge/
│       │   ├── M1/ ~ M6/
│       │   ├── reviews/
│       │   └── handoff_M*.md
│       ├── drafts/
│       │   └── M1S01/ ~ M6S06/
│       ├── artifacts/
│       │   ├── paper.tex
│       │   └── paper.pdf
│       ├── experiments/
│       └── config/
├── tests/                       # Test suite
│   ├── test_public_db/
│   ├── test_m1_integration.py
│   ├── test_m4_integration.py
│   ├── test_m6_integration.py
│   ├── test_m1_e2e.py
│   └── test_m1_integration.py
├── pyproject.toml
├── README.md
├── README_CN.md                 # Chinese docs
└── AGENTS.md                    # Agent global context
```

---

## Configuration

### Environment Variables

| Variable | Purpose |
|:---|:---|
| `SPIRAL_FRAMEWORK_ROOT` | Override framework root detection |
| `SPIRAL_PROJECTS_ROOT` | Override projects root location |

### Venue Registry

Edit `config/venue_registry.yaml` to add new submission venues:

```yaml
venues:
  my_venue:
    name: "My Conference"
    full_name: "Annual Meeting of ..."
    page_limit: 8
    page_limit_note: "8 pages + references"
    format: "conference"
    style_package: "my_style"
    template_dir: "my_venue"
```

Place `.sty`, `.cls`, `.bst`, `.tex` template files under `templates/venue/my_venue/`.

### Public Database Configuration

Edit `config/public_db.yaml` to adjust public literature DB behavior:

```yaml
enabled: true
db_path: "data/public_literature_db/public_literature.db"
query_cache_ttl_days: 7
min_hit_threshold: 10
```

---

## Development & Testing

### Running Tests

```bash
# Run all tests (114+ tests)
python -m unittest discover -s tests -v

# Run public DB tests
python -m unittest tests.test_public_db.test_core -v

# Run M1 end-to-end tests
python -m unittest tests.test_m1_e2e -v

# Test health check
python scripts/test_health_check.py

# Agent consistency check
python scripts/agent_consistency_check.py
```

### Code Quality

```bash
# Format
ruff format spiral/ scripts/ utils/ tests/

# Lint
ruff check spiral/ scripts/ utils/ tests/

# Type check
mypy spiral/ scripts/ utils/
```

---

## License

MIT License
