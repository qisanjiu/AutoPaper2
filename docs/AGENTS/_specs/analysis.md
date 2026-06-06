# Analysis Agent Compact Spec

## Stages
- `M3S05 Result Validation`: verify result integrity, seed limitations, data quality, stopping reason, evidence level, and final decision `KEEP|FIX|BACKTRACK` with repair fields when needed.
- `M4S01 Findings Audit`: consolidate main results, negative/partial findings, unexpected observations, claim candidates, and analysis campaign draft.
- `M4S02 Deep Analysis Design`: design ablation, mechanism, robustness/boundary, failure, and efficiency slices. Each claim-carrying slice needs baseline inclusion or explicit waiver and literature/database basis. Also write `experiments/configs/m4_task_queue.yaml` so M4S03 can execute the plan without redesign.
- `M4S04 Analysis Results`: integrate M4S03 evidence into claim ledger, insight articulation, evidence usability, limitations, and downstream writing guidance.
- `M5S01 Pre-Write Audit`: check M1-M4 completeness, contribution support, evidence/narrative/citation gaps, style/layout references, data consistency, writing risks, and go/no-go.

## Evidence Rules
- Distinguish correlation from causality; do not overstate single-seed or smoke-level evidence.
- Negative, failed, partial, or unusable evidence must be labeled and cannot support main claims.
- Robustness/performance/boundary claims require baseline comparison unless explicitly downgraded.
- Every downstream writing claim must cite M3/M4 evidence paths and evidence status.
- M4S02 must translate every `Ana-*` slice into an executable task with command, dependencies, resource requirements, baseline policy, expected artifacts, and success criteria.
- Ablations live in M4 only. Treat disabled-component, variant, removal, sensitivity, and partial-method experiments as `analysis_type=ablation` slices, never as M3 baselines.

## Backtrack Rules
- `FIX`: bounded current-stage repair.
- `BACKTRACK`: upstream design/experiment/data/baseline issue. Include full repair fields and rerun scope.
- Never write KEEP to force progress when evidence contradicts the claim.

## M4S02 Task Queue Rules
- `experiments/configs/m4_task_queue.yaml` must contain a nonempty `tasks` list.
- Every task id must correspond to an `Ana-*` slice in `knowledge/M4/M4S02_analysis_experiment_design.md`.
- Every task needs `command`, `analysis_type`, `dependencies`, `resource_requirements`, `baseline_inclusion` or `baseline_required`, `expected_artifacts`, and `success_criteria`.
- Baseline-required tasks need a `fairness_key` tying baseline and proposed-method rows to the same split, seed, metric, and resource class.
- If a slice cannot be executed, state the blocker in M4S02 and do not mark it as a runnable queue task.
- M4 may compare ablation variants against the locked M3 active baseline or full proposed method, but those variants do not become baseline_lock entries and must not rewrite M3 baseline contracts.
