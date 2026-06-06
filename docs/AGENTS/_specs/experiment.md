# Experiment Agent Compact Spec

## Stages
- `M3S01`: main experiment design only. Define dataset/scenario/split, M2S05 metric_protocol_id, external/prior-work baselines with concrete same-dataset same-metric reference values and sources, proposed-method same-condition protocol, seed=42, fairness/resource constraints, and open blockers. Do not design ablations, robustness, mechanism, failure slices, or M4 analysis work.
- `M3S02`: dataset and environment setup. Confirm dataset availability before implementation. Actively download/sync datasets and model assets through public cache, official URLs, framework auto-download, HuggingFace/Kaggle, or SSH; only block for missing credentials, license approval, quota/storage, or repeated network failure after recorded attempts. Implement M2 design, dependency lock, sandbox/container profile, resource plan, hardware probe, optional SSH allocation, longrun ledger, smoke run, and implementation deviations.
- `M3S03`: baseline lock. Verify comparator first, acquire checkpoints when needed, lock metric contract, run smoke test, document local baseline result and deviation from paper/history, verify metric implementation against M2S05 `metric_protocol_id`, and write `experiments/baselines/baseline_lock.yaml`.
- `M3S04`: main experiment. Lock run contract, execute iterations to completed trained checkpoints, maintain `experiments/results.tsv`, run/resource logs, watchdog events, negative attempts, best config, and evidence ladder level.
- `M4S03`: execute deep analysis slices from M4S02, produce `experiments/analysis_results.tsv`, resource allocation, artifacts, reproduction notes, and preliminary abnormal-result triage.

## Required Evidence
- M3S01: `knowledge/M3/M3S01_main_experiment_design.md` with baseline/dataset/metric/reference_value/source rows, M2S05 metric_protocol_id references, proposed same-condition protocol, seed=42, and no M4 analysis plan.
- M3S02: `experiments/configs/sandbox_profile.yaml`, `experiments/configs/resource_plan.yaml`, dependency lock, dataset path/license/checksum or `M3S02_dataset_pending.md`, `experiments/logs/m3s02_longrun_ledger.md`.
- M3S03: baseline metric contract with checkpoint source/local path/checksum/loadability when applicable, metric_protocol_id alignment, metric sanity-check evidence, plus `experiments/baselines/baseline_lock.yaml` with at least one primary baseline marked `m3s04_eligible: true`.
- M3S04: `results.tsv`, run directories, config/seed, resource monitor, watchdog checks for long runs, failure/negative records, and a completed trained-checkpoint path for each proposed/ours result row.
- M4S03: `analysis_results.tsv`, slice logs, baseline inclusion, monitor paths, artifacts manifest, sandbox record.

## Resource Rules
- Use visible GPUs/CPUs deliberately. If multiple GPUs/resources exist, generate task queues/allocation or explain why not parallelizable.
- Use DDP for a single multi-GPU training job when applicable; use task parallelism only for independent runs/slices.
- Remote runs must record push/pull sync evidence and redacted logs.

## Stop / Backtrack Rules
- Do not skip dataset/checkpoint/download just because it is slow; record wait/resume commands.
- Download/acquisition blockers are not PASS conditions. If datasets, baseline code, baseline weights, checkpoints, or model assets are still `failed`, `running`, `queued`, `blocked_user_action`, unavailable, or not verified, the stage/review must be non-PASS until the artifact is completed with evidence or a HALT is raised for human action after recorded attempts.
- M3S01 cannot PASS with vague baseline placeholders. Each baseline must have a concrete reference metric value for the corresponding dataset/scenario/split/metric and a source that can be checked later.
- Watchdog alerts require an agent decision: `continue`, `fix_and_rerun`, `early_stop`, or `backtrack_request` with evidence.
- If design, dataset, metric, or baseline is invalid, request structured backtrack instead of silently changing upstream assumptions.
- Do not mark M3S04 complete while a required training stage is still running. E0/random/untrained weights are diagnostic only and must never populate the final proposed/ours result row.
- If a run is under target, first use autonomous repair within scope: fix data/config/code, resume training, download missing weights, retrain a baseline, adjust resources, or backtrack to M3S03/M3S02/M2 as needed. Do not stop at hyperparameter tuning if the root cause is elsewhere.

## M3S03 Baseline Lock Rules
- M3S03 must not use paper-reported numbers alone as the baseline for M3S04; each primary comparator needs a local verified metric or an explicitly bounded waiver.
- M3S03 must not define or silently replace metrics. Each primary comparator must cite an M2S05 `metric_protocol_id` and match that protocol's dataset, scenario, split, metric key, direction, value range, and normal reference range.
- If a baseline local value is outside the M2 normal reference range or has a large paper/local deviation, M3S03 must write structured anomaly/deviation triage with evidence paths and request REVISE/BACKTRACK as needed; it must not mark that result as `verified_match` or `verified_close`.
- If a baseline depends on pretrained weights/checkpoints, actively locate and acquire them from official releases, README-linked storage, framework auto-download, HuggingFace, third-party mirrors, or project cache before declaring it unavailable.
- Required checkpoints must record source URL, local path, checksum, loadability verification, and acquisition/search attempts. A required checkpoint without a real local file cannot enter M3S04.
- M3 baselines must be external comparators from prior work, official packages, or full faithful reproductions. They must not be ablations, variants, or disabled-component versions of the proposed method; ablations are M4-only.
- A self-implemented/reimplemented baseline must be a full reproduction of the paper/model. Simplified, toy, minimal, proxy, or partial implementations are forbidden as M3 baselines; if full fidelity cannot be reached, request backtrack or mark the comparator ineligible.
- Baseline code is mutable only during M3S03 repair. After `baseline_code_immutable_after_lock: true`, M3S04 must treat baseline code, checkpoint, dataset split, and metric contract as read-only.
- `trusted_with_caveats` is not enough by itself. It must include `caveat_waiver_reason`, `comparison_scope_limit`, and `m3s04_eligible: true`; otherwise request backtrack or mark the baseline ineligible.
- M3S04 may start only when `experiments/baselines/baseline_lock.yaml` declares a primary comparator with `m3s04_eligible: true` and an existing `metric_contract` path.
