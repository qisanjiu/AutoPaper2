# Experiment Agent Compact Spec

## Stages
- `M3S01`: dataset and environment setup. Confirm dataset availability before implementation. Implement M2 design, dependency lock, sandbox/container profile, resource plan, hardware probe, optional SSH allocation, longrun ledger, smoke run, and implementation deviations.
- `M3S02`: baseline lock. Verify comparator first, acquire checkpoints when needed, lock metric contract, run smoke test, document local baseline result and deviation from paper/history, and write `experiments/baselines/baseline_lock.yaml`.
- `M3S03`: main experiment. Lock run contract, execute iterations, maintain `experiments/results.tsv`, run/resource logs, watchdog events, negative attempts, best config, and evidence ladder level.
- `M4S03`: execute deep analysis slices from M4S02, produce `experiments/analysis_results.tsv`, resource allocation, artifacts, reproduction notes, and preliminary abnormal-result triage.

## Required Evidence
- M3S01: `experiments/configs/sandbox_profile.yaml`, `experiments/configs/resource_plan.yaml`, dependency lock, dataset path/license/checksum or `M3S01_dataset_pending.md`, `experiments/logs/m3s01_longrun_ledger.md`.
- M3S02: baseline metric contract with checkpoint source/local path/checksum/loadability when applicable, plus `experiments/baselines/baseline_lock.yaml` with at least one primary baseline marked `m3s03_eligible: true`.
- M3S03: `results.tsv`, run directories, config/seed, resource monitor, watchdog checks for long runs, failure/negative records.
- M4S03: `analysis_results.tsv`, slice logs, baseline inclusion, monitor paths, artifacts manifest, sandbox record.

## Resource Rules
- Use visible GPUs/CPUs deliberately. If multiple GPUs/resources exist, generate task queues/allocation or explain why not parallelizable.
- Use DDP for a single multi-GPU training job when applicable; use task parallelism only for independent runs/slices.
- Remote runs must record push/pull sync evidence and redacted logs.

## Stop / Backtrack Rules
- Do not skip dataset/checkpoint/download just because it is slow; record wait/resume commands.
- Watchdog alerts require an agent decision: `continue`, `fix_and_rerun`, `early_stop`, or `backtrack_request` with evidence.
- If design, dataset, metric, or baseline is invalid, request structured backtrack instead of silently changing upstream assumptions.

## M3S02 Baseline Lock Rules
- M3S02 must not use paper-reported numbers alone as the baseline for M3S03; each primary comparator needs a local verified metric or an explicitly bounded waiver.
- If a baseline depends on pretrained weights/checkpoints, actively locate and acquire them from official releases, README-linked storage, framework auto-download, HuggingFace, third-party mirrors, or project cache before declaring it unavailable.
- Baseline code is mutable only during M3S02 repair. After `baseline_code_immutable_after_lock: true`, M3S03 must treat baseline code, checkpoint, dataset split, and metric contract as read-only.
- `trusted_with_caveats` is not enough by itself. It must include `caveat_waiver_reason`, `comparison_scope_limit`, and `m3s03_eligible: true`; otherwise request backtrack or mark the baseline ineligible.
- M3S03 may start only when `experiments/baselines/baseline_lock.yaml` declares a primary comparator with `m3s03_eligible: true` and an existing `metric_contract` path.
