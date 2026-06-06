# AutoPaper2 Audit and Optimization Notes

Date: 2026-05-23

## User Target

The framework should let a user provide a research topic and configuration, then autonomously orchestrate M1-M6 to produce a complete academic paper. The main agent must only orchestrate, advance, gate, and backtrack; all stage execution and review work must be delegated to subagents. Repetitive or deterministic work should be scripted.

## Repository Map

- `spiral/`: core state, project creation, conductor, dispatch packets, verdict parsing, public literature DB.
- `scripts/`: CLI entry points for state management, dispatch, environment probing, submission/email automation, health checks.
- `docs/AGENTS/`: role prompts for conductor, stage agents, reviewers, critics, and revision routing.
- `skills/`: user-facing workflow descriptions for AutoPaper2 modules and project automation.
- `templates/`: stage templates and venue LaTeX templates.
- `utils/`: file guards, source-log validation, stage quality gates.
- `tests/`: integration and unit tests for M1/M4/M6, public DB, project entry, dispatch.

## Compliance Check

| Requirement | Current status | Evidence / gap |
|---|---|---|
| User can provide topic and config | Mostly satisfied | `scripts/state_manager.py create` accepts topic, display name, venue, keywords, references, execution env; project creation tests pass. |
| M1-M6 pipeline exists | Satisfied structurally | `spiral/project.py` defines 33 stages across M1-M6; canonical outputs and stage templates exist. |
| Main agent only orchestrates | Improved | Dispatch packets define main-agent boundaries. M6S05 routes through Revision Agent plus script-generated routing data; M6S01 internal peer review is delegated to a dedicated critic agent. |
| Subagent dispatch is durable | Satisfied structurally + simulated end-to-end | `spiral/dispatch.py` writes packets under `state/dispatch/`; packets include input paths, output paths, agent docs, and boundaries. `scripts/full_pipeline_simulator.py` now builds/writes dispatch packets while simulating all stages. |
| Backtracking is stateful and delegated | Improved | `Conductor.backtrack()` records advice, stale stages, spiral count, gate re-review; human review uses `Conductor.backtrack()`. The no-LLM simulation now exercises a stage-review REVISE → backtrack → re-execute path. Full real multi-agent execution still depends on the runtime Agent tool. |
| Repetitive work scripted | Improved | Existing scripts cover state, dispatch, health, submission/email, env probe. Added `scripts/m6_action_router.py`, `spiral/revision_router.py`, and `scripts/full_pipeline_simulator.py` for deterministic full-pipeline orchestration checks. |
| User M1-M6 requirements | Improved + traceable | M1 now enforces search provenance/screening evidence, STORM-style perspective coverage, deep-reading fields, and large/middle/small gap-chain gates; M2 now enforces auditable cross-domain search statistics, query ledger, candidate discovery provenance, Gap→solution mapping, M2S05 experiment setup/metric-protocol gates, and independent reviewers; M3 now enforces M3S01 main-experiment design with concrete baseline reference values, concrete local/ssh execution configuration, sandbox/profile matching, long-run permission/patience ledger, and M3S05 result-validation evidence package; M4 now enforces how/where/why analysis-design provenance, baseline-aware M4S02 slices, sandboxed analysis execution, and deep-analysis evidence packaging; M5 now enforces pre-write upstream completeness, fully-supported contribution evidence, data consistency/readiness decisions, style-layout reference distillation, figure policy, and final paper package validation; M6 internal review threshold plus item-level external-review resolution and G1-G6 evidence rubrics are now explicit in templates/docs/gates. `config/user_requirement_trace.yaml` maps each user requirement to evidence paths and tests, and `scripts/requirement_trace_check.py` validates the trace. Actual research quality still depends on project-specific execution evidence. |
| Complete publishable paper guarantee | Not provable from code alone | The framework enforces many quality gates, but publishability requires actual topic-specific research, data access, experiments, reviewer outcomes, and venue compliance. |

## Tests Run

- `python scripts/agent_consistency_check.py`: PASS.
- `python scripts/test_health_check.py`: PASS after converting dispatch tests to `unittest` coverage.
- `python -m py_compile utils/source_log_validator.py utils/stage_gate.py scripts/full_pipeline_simulator.py tests/test_m1_integration.py tests/test_m1_e2e.py tests/test_project_entry.py`: PASS.
- `python -m py_compile utils/source_log_validator.py utils/stage_gate.py scripts/full_pipeline_simulator.py tests/test_m1_integration.py tests/test_dispatch.py`: PASS.
- `python -m py_compile utils/stage_gate.py tests/test_m3_integration.py scripts/full_pipeline_simulator.py`: PASS.
- `python -m py_compile utils/stage_gate.py scripts/full_pipeline_simulator.py tests/test_m4_integration.py`: PASS.
- `python -m py_compile scripts/conductor_helper.py tests/test_dispatch.py`: PASS.
- `python -m py_compile scripts/requirement_trace_check.py tests/test_requirement_trace.py`: PASS.
- `python -m py_compile utils/source_log_validator.py utils/stage_gate.py scripts/full_pipeline_simulator.py tests/test_m1_integration.py`: PASS.
- `python scripts/requirement_trace_check.py`: PASS.
- `python -m unittest tests.test_m1_integration -v`: 23 tests, OK.
- `python -m unittest tests.test_dispatch -v`: 20 tests, OK.
- `python -m unittest tests.test_requirement_trace -v`: 2 tests, OK.
- `python -m unittest tests.test_m4_integration.TestM5StageGate -v`: 8 tests, OK.
- `python -m unittest tests.test_full_pipeline_simulation -v`: 3 tests, OK.
- `python -m unittest tests.test_m4_integration -v`: 28 tests, OK.
- `python -m unittest tests.test_m1_integration tests.test_m1_e2e tests.test_project_entry -v`: 32 tests, OK.
- `python -m unittest tests.test_m1_integration tests.test_m1_e2e tests.test_project_entry tests.test_full_pipeline_simulation -v`: 35 tests, OK.
- `python -m unittest tests.test_m1_integration tests.test_dispatch tests.test_full_pipeline_simulation -v`: 44 tests, OK.
- `python -W error::ResourceWarning -m unittest tests.test_public_db.test_core tests.test_public_db.test_integration_survey_memory -v`: 79 tests, OK.
- `python -m unittest tests.test_m3_integration tests.test_full_pipeline_simulation -v`: 14 tests, OK.
- `python -m unittest tests.test_m4_integration tests.test_full_pipeline_simulation -v`: 26 tests, OK.
- `python -m unittest tests.test_m6_integration tests.test_full_pipeline_simulation -v`: 12 tests, OK.
- `python -m unittest discover -s tests -v`: 191 tests, OK.
- `pytest -q` and `python -m pytest -q`: not available in the current environment (`pytest` is not installed).

The warning-as-error public DB run covers threaded SQLite connections and survey-memory integration without connection leak warnings. Residual issue: `pytest` is not installed; all tracked tests are currently `unittest` compatible.

## Changes Made

- Added deterministic M6 action-plan parsing and routing:
  - `spiral/revision_router.py`
  - `scripts/m6_action_router.py`
- Reassigned M6S05 from `conductor_routed` to a dedicated `revision` subagent in `spiral/project.py`.
- Added `docs/AGENTS/revision/AGENT.md`.
- Updated M6/conductor docs to require script-generated routing before revision execution.
- Converted `tests/test_dispatch.py` from pytest-style functions to `unittest.TestCase`.
- Strengthened `scripts/test_health_check.py` to detect top-level pytest-style tests that `unittest discover` would miss.
- Added mandatory M6S01 internal peer review:
  - `docs/AGENTS/critic/m6_internal_peer_review/AGENT.md`
  - dispatch packet inputs for paper artifacts and M1-M5 evidence
  - stage-gate enforcement of `Internal Review Score >= 8/10` and zero unresolved High issues
- Tightened M5 figure policy:
  - method/framework figures must name image2/gpt-image-2 and `paper-framework-figure-studio-pro`
  - experiment plots must reference `nature-figure` principles and come from data plus plotting code
- Hardened M5S08 final paper package closure:
  - final compilation now blocks placeholder/too-short `paper.tex`, missing required paper sections, missing bibliography, orphan citations, missing figure assets, missing figure/table references, and missing `booktabs` table style
  - `paper.pdf` must exist with a PDF header, and `refs.bib` must be non-empty and match every citation key
  - the final compilation report must record compile commands, PASS verdict, zero fatal errors, zero undefined references/citations, zero orphan cites, Anti-Leakage PASS, page count, style/layout compliance, figure compliance, and final artifact list
  - `handoff_M5_completion.md` is now checked for M6 readiness, paper artifacts, and compilation status
- Hardened M5S01/M5S02 writing-readiness closure:
  - M5S01 now blocks unless critical M1/M2/M3/M4 upstream documents and `handoff_M4_M5.md` exist and are nonempty
  - M5S01 must identify at least one `fully_supported` contribution with M3/M4 evidence paths, cover Evidence/Narrative/Citation gaps, data consistency for metric/baseline/dataset/method, and an explicit positive continue-writing decision
  - unresolved High blocking gaps now stop M5 before outline generation
  - M5S02 must declare 3-5 reference/exemplar papers, transferable structure/layout signals, anti-copy boundaries, Figure Style Profile, image2/gpt-image-2 framework-figure policy, paper-framework-figure-studio-pro reference, and nature-figure-backed experiment plot policy
  - Analysis/Writing agents, M5S01/M5S02 templates, M5 Stage Reviewer, simulator, and regression tests now document the same writing-readiness contract
- Enriched M1/M2 templates:
  - M1 paper cards and source log now include background, contributions, model, method, experiment setup, results, analysis, and conclusion
  - M1 gap report now distinguishes large/mid/small direction gaps
  - M2 experiment design now records related-work protocols and per-experiment report blueprints
- Hardened M1 gap-chain closure:
  - `M1_source_log.yaml` now must classify gaps into large/middle/small direction levels and provide a description/argument for each gap
  - M1S02 stage gate now blocks if the research report omits large/middle/small problems or evidence-chain/argument text
  - M1S03-M1S05 stage gates now block unsupported research questions, hypotheses without measurable predictions/null hypotheses, weak novelty/feasibility assessments, or missing M1→M2 gap/hypothesis handoff
- Hardened M1 search-provenance closure:
  - `M1_source_log.yaml` now must include auditable `search_provenance` / `search_strategy` with database or internet search surfaces, inclusion/exclusion criteria, and three retained-source search rounds
  - each M1 search round must record non-empty queries, positive retrieved/screened counts, and retained source IDs or retained counts; retained IDs must exist in the Source Log
  - blindspot evidence now explicitly covers recent work, negative/opposing results, seminal/classic work, key authors/teams, and Source Log consistency
  - M1S02 Markdown, Survey Agent, Source Log Validator, Coverage Critic, simulator fixtures, and regression tests now use the same provenance contract
- Added STORM-style M1 perspective coverage:
  - `M1_source_log.yaml.search_provenance.perspective_coverage` now must cover scenario/task, model/method, metric/performance, dataset/protocol, failure/limitation, and baseline/comparison perspectives
  - each perspective must record covered/reviewed status, queries, source IDs that exist in the Source Log, and a finding/evidence summary
  - M1S02 Markdown must include a `Perspective Coverage` / 视角覆盖 section before gap synthesis
  - Survey Agent, M1S02 template, Coverage Critic, source-log validator, simulator, and regression tests now share the same perspective-coverage contract
- Hardened M2 cross-domain search-provenance closure:
  - `M2_source_log.yaml` now must include `search_statistics` with total queries or query ledger, Public DB/Web/citation hit counts, shortlisted source IDs, and search dimensions
  - every query-ledger entry must record query, search surface, and positive result counts; M2S01 now blocks if the search surface cannot be traced to Public DB/library, Web/internet, or citation-chain search
  - every M2 candidate source must record search_dimension, target_gap, source_domain, core_mechanism, adaptation_potential, discovery_source, and discovery_query
  - `gap_solution_map` is now blocking rather than advisory, so every M2 search package must map M1 gaps to candidate solutions
  - M2S01 stage gate now invokes `source_log_validator.validate(module="M2")`; Method Agent, M2S01 template, M2 Search Quality Reviewer, simulator, and regression tests use the same contract
- Hardened M2S05/M3S01 experiment-design closure:
  - M2S05 now blocks advancement unless dataset acquisition, baseline fairness, metrics/statistics, related-work protocol, seeds, reproducibility, and per-experiment purpose/hypothesis fields are present
  - M3S01 now blocks advancement unless the main experiment has dataset/scenario/split, metric_protocol_id, baseline reference values with sources, and proposed-method same-condition protocol
  - `m2_experiment_design_review` and `m3_main_experiment_design_review` are mandatory independent stage reviews with canonical dispatch outputs and non-bypass state-manager handling
- Promoted M1 deep-reading fields from guidance to enforced validation for academic sources in `utils/source_log_validator.py`.
- Hardened M3S02 execution evidence:
  - Experiment Agent and M3S02 template now require `experiments/logs/m3s02_longrun_ledger.md`
  - Stage gate blocks M3S02 if the ledger is missing, incomplete, or records invalid size/time-based skips
  - Review dispatch includes the ledger, execution config, and requirements files for independent M3S02 review
- Hardened M3S02 local/ssh execution configuration:
  - M3S02 now fails unless `execution.mode` is explicitly `local` or `ssh`
  - local mode requires `execution.local.env_manager` (`conda` / `venv` / `uv` / `docker`) and `execution.local.python_version`
  - ssh mode requires `execution.ssh.host`, `user`, `workspace_path`, `env_manager`, `python_version`, and `sync.method` (`rsync` / `scp`)
  - sandbox mode must match execution mode: `ssh` requires `ssh_remote`, while `local` cannot use `ssh_remote`
  - M3S02 implementation docs and the long-run ledger must match the configured mode; the ledger now also requires permission/approval evidence in addition to patience/polling and resume commands
  - Experiment Agent, M3S02 template, M3 Dataset/Environment Reviewer, and regression tests now document the same local/ssh contract
- Hardened M3S05 result-validation closure:
  - M3S05 now blocks shallow KEEP reports that omit data-quality checks, statistical validation, hypothesis mapping, root-cause analysis, negative results, limitations, artifact packaging, or downstream M4 handoff content
  - KEEP requires `experiments/artifacts/main_experiment/manifest.yaml`, `metric_contract.yaml`, `comparison_table.csv`, `reproduction.md`, and `knowledge/handoff_M3_M4.md`
  - FIX/BACKTRACK decisions remain non-advancing even when structured repair advice is present, forcing the requested rerun before M4
  - the no-LLM full-pipeline simulator now emits a gate-valid M3S05 evidence package
- Hardened M4S04 deep-analysis closure:
  - M4S04 now blocks analysis integration unless it answers how/where/why, covers ablation, mechanism, robustness, and failure/negative analysis, and records baseline-aware comparisons
  - `experiments/analysis_results.tsv` must include structured slice/type/method/metric/value rows with baseline and ours/proposed comparisons
  - `experiments/artifacts/analysis_experiment/` (or equivalent) must include `manifest.yaml`, `reproduction.md`, and at least one analysis visualization/figure artifact
  - unsupported/deferred/unusable evidence cannot be routed to `main_text`, and `handoff_M4_M5.md` must carry claim/evidence mapping, artifact paths, M5 writing guidance, limitations, and usable/weak status
- Hardened M4S02 deep-analysis design closure:
  - M4S02 now blocks shallow analysis designs that do not explicitly map how/where/why analysis targets
  - claim-carrying slices must include `comparison_target`, `expected_pattern`, `claim_links`, `baseline_inclusion`, `literature_basis`, and `evidence_criteria`
  - the design must cite upstream M2/M3 basis such as M2S05, M3S01, M3S05, or `handoff_M3_M4.md`, plus literature/database analysis basis
  - at least 3 concrete `Ana-*` slice IDs are required before M4S03 can execute
  - Analysis Agent, M4S02 template, M4 Analysis Design Reviewer, simulator, and regression tests now document the same design contract
- Aligned M4/M5 subagent boundaries:
  - Conductor docs now route `M5S01` to Analysis Agent and `M5S02-M5S08/M5S09` to Writing Agent, matching `spiral/project.py`
  - Analysis Agent docs no longer present M4S03 as an Analysis-owned output; they explicitly defer M4S03 execution to Experiment Agent
  - Experiment Agent docs now define M4S03 responsibilities for running `Ana-*` slices, producing `experiments/analysis_results.tsv`, sandbox execution records, artifacts, and execution-side anomaly routing
  - M4S02/M4S03 dispatch input resolution now passes `handoff_M3_M4.md`, M3S01/M3S05 evidence, and analysis-design files to the responsible subagents; dispatch tests cover those paths
- Added M3/M4 sandbox/container execution profile:
  - `config/execution_env.yaml` and `scripts/env_probe.py` now include `execution.sandbox`
  - M3S02 requires `experiments/configs/sandbox_profile.yaml` with network, filesystem, secrets, resource, and reproducibility policies
  - M4S03 requires a sandbox/container execution record for analysis slices
  - Stage gates now block missing/disabled sandbox profiles or M4S03 execution without sandbox evidence
- Added PaperBench-style Gate rubrics:
  - `config/gate_rubrics.yaml` defines G1-G6 rubric items tied to the user's M1-M6 requirements
  - `utils/gate_rubric.py` blocks aggregate gate advancement unless every rubric row is PASS, score 2/2, and cites an existing evidence path
  - Gate dispatch packets now include the applicable rubric block so critics know the required checks before writing reviews
- Added user-requirement traceability:
  - `config/user_requirement_trace.yaml` maps AP2-M1 through AP2-M6, conductor-only orchestration, and external comparison to concrete agent docs, templates, scripts, gates, and tests
  - `scripts/requirement_trace_check.py` validates required trace fields, evidence paths, test paths, module coverage, residual runtime limits, and external-source URLs
  - `tests/test_requirement_trace.py` blocks stale/missing evidence paths in the trace
  - `docs/EXTERNAL_OPEN_SOURCE_COMPARISON.md` records the current comparison against AI Scientist, AI Scientist-v2, Agent Laboratory, STORM, OpenHands, PaperBench, and paper-framework-figure-studio-pro
- Added M6 item-level backtrack advice persistence:
  - `spiral/revision_router.py` now converts each M6 action-plan item into per-stage direct/downstream repair advice
  - `PipelineState.stage_backtrack_advice` preserves item-specific repair instructions across routed target stages and downstream reruns
  - `Conductor.backtrack_from_revision_routing()` applies M6S05 routing through the normal `Conductor.backtrack()` path while keeping all per-stage advice available to dispatch packets
- Hardened M6 external-review closure:
  - M6S02/M6S03/M6S06 stage gates now validate paperreview.ai submission logs, tracking data, raw review-email metadata/body, and atomic PR-* review matrix fields
  - M6S06 self-validation and G6 Resolution Critic prompts now require explicit external-review evidence re-checks before completion
  - added regression coverage blocking M6S06 completion when external-review evidence is incomplete
- Hardened M6 item-level review resolution:
  - every `PR-*` item from `M6S03_review_matrix.md` must appear in `M6S04_action_plan.md` with class, severity, target stage, required fix, success criteria, rebuild mode, rerun scope, and priority
  - M6S05 revision execution must include every PR item with completed/resolved status and evidence/output paths
  - M6S06 validation must cover every PR item, requires High-priority items to be resolved/PASS, and blocks completion if any High item is unresolved/failed/pending
  - templates and M6 Rebuttal/Revision agents now document the same PR-item closure contract
- Fixed pipeline-state isolation:
  - new `PipelineState` instances now deep-copy nested default state instead of sharing module dictionaries between projects/tests
  - added regression coverage so a completed module in one project cannot make another project auto-skip a module
- Fixed public DB connection lifecycle:
  - `DatabaseManager.close_all()` now closes tracked worker-thread SQLite connections, not only the current thread connection
  - `PublicLiteratureDB` and `SurveyMemoryManager` now support explicit close/context-manager cleanup
  - project creation closes the auto-connected public DB after initializing `survey_memory.yaml`
  - registered SQLite JSON helper functions now parse JSON arrays under direct regression coverage
- Added no-LLM full-pipeline simulation:
  - `scripts/full_pipeline_simulator.py` writes minimal valid stage/review/gate artifacts and advances the real state manager through all 33 stages and 6 gates
  - simulation writes dispatch packets and exercises one stage-review-triggered backtrack/re-execution
  - fixed Conductor auto-advance so module completion opens the current next-module stage instead of skipping ahead

## External Comparison

- Full comparison and optimization backlog: `docs/EXTERNAL_OPEN_SOURCE_COMPARISON.md`.
- [The AI Scientist](https://github.com/SakanaAI/AI-Scientist) aims at fully automated scientific discovery and uses templates with runnable experiment scripts, plotting scripts, prompts, and LaTeX templates. Its README also includes a containerization section, which is relevant because AutoPaper2 will execute LLM-produced experiment code.
- [AI Scientist-v2](https://arxiv.org/abs/2504.08066) adds progressive agentic tree search and VLM-assisted figure refinement; this motivates optional future branch/frontier and visual-QA artifacts for AutoPaper2.
- [Agent Laboratory](https://arxiv.org/abs/2501.04227) presents an end-to-end research-assistant workflow with specialized LLM agents across literature review, experimentation, and report writing, while emphasizing human creativity and automation of repetitive coding/documentation.
- [STORM](https://github.com/stanford-oval/storm) informs the remaining M1 optimization: perspective-guided coverage before writing the gap report.
- [OpenHands](https://github.com/OpenHands/OpenHands) and its sandbox model inform M3/M4 local/ssh/sandbox hardening and a future append-only runtime event stream.
- [PaperBench](https://openai.com/index/paperbench/) is a replication benchmark that decomposes paper replication into thousands of gradable tasks and rubrics, which is useful as a model for objective AutoPaper2 gate criteria.
- [paper-framework-figure-studio-pro](https://github.com/c-narcissus/paper-framework-figure-studio-pro) is now treated as the external style reference for M5 architecture/method figures, while numeric experiment plots remain code-generated.

## High-Value Next Optimizations

1. Add optional M2/M3 method frontier tracking inspired by AI Scientist-v2 progressive search.
2. Add append-only M3/M4 runtime event stream inspired by OpenHands/PaperBench execution traces.
3. Add optional VLM figure QA for M5 image2 framework/method figures while preserving allowed-label constraints.
4. Add per-perspective quality scoring for M1 perspective coverage, beyond presence/traceability checks.
5. Install or vendor a dev test environment path for `pytest`, or keep all tests `unittest` compatible and remove pytest assumptions from project metadata.
