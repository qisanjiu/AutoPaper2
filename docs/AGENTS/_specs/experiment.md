# Experiment Agent Compact Spec

## Stages
- `M3S01`: main experiment design only. Define dataset/scenario/split, M2S05 metric_protocol_id, external/prior-work baselines with concrete same-dataset same-metric reference values and source truth from `knowledge/M1/M1_source_log.yaml`, proposed-method same-condition protocol, seed=42, fairness/resource constraints, and open blockers. Do not design ablations, robustness, mechanism, failure slices, or M4 analysis work.
- `M3S02`: dataset and environment setup. Confirm complete dataset availability before implementation. Actively download/sync datasets and model assets through public cache, official URLs, framework auto-download, HuggingFace/Kaggle/ModelScope/PyTorch Hub, mirrors, project cache, or SSH; only block for missing credentials, paid/quota approval, storage expansion, restricted network/VPN access, or repeated network failure after recorded resumable attempts. Implement M2 design, dependency lock, sandbox/container profile, resource plan, hardware probe, optional SSH allocation, longrun ledger, smoke run, dataset completeness manifest, and implementation deviations.
- `M3S03`: baseline lock. Verify comparator first, acquire checkpoints when needed, lock metric contract, run smoke test, document local baseline result and deviation from paper/history, verify metric implementation against M2S05 `metric_protocol_id`, and write `experiments/baselines/baseline_lock.yaml`.
- `M3S04`: main experiment. Lock run contract, execute iterations to completed trained checkpoints, maintain `experiments/tables/results_main.tsv`, `experiments/tables/results_all.tsv`, `experiments/run_registry.yaml`, run/resource logs, watchdog events, negative attempts, best config, and evidence ladder level. `experiments/results.tsv` may exist only as a compatibility mirror.
- `M4S03`: execute deep analysis slices from M4S02, produce `experiments/analysis_results.tsv`, resource allocation, artifacts, reproduction notes, and preliminary abnormal-result triage.

## Required Evidence
- M3S01: `knowledge/M3/M3S01_main_experiment_design.md` with baseline/dataset/metric/reference_value/source rows, M2S05 metric_protocol_id references, baseline `source_id/title/venue/year/modality/task/table_or_section` rows matching `M1_source_log.yaml`, proposed same-condition protocol, seed=42, and no M4 analysis plan.
- M3S02: `experiments/configs/sandbox_profile.yaml`, `experiments/configs/resource_plan.yaml`, dependency lock, `experiments/data/dataset_manifest.yaml` with dataset path, required files, explicit splits/counts, checksum evidence when available, smoke-load evidence, or `M3S02_dataset_pending.md`, plus `experiments/logs/m3s02_longrun_ledger.md`.
- M3S03: baseline metric contract with checkpoint source/local path/checksum/loadability when applicable, source truth fields matching `M1_source_log.yaml`, metric_protocol_id alignment, metric sanity-check evidence, plus `experiments/baselines/baseline_lock.yaml` with at least one primary baseline marked `m3s04_eligible: true`.
- M3S04: `experiments/tables/results_main.tsv`, `experiments/tables/results_all.tsv`, `experiments/run_registry.yaml`, run directories, config/seed, resource monitor, watchdog checks for long runs, failure/negative records, and a completed trained-checkpoint path for each proposed/ours result row.
- M4S03: `analysis_results.tsv`, slice logs, baseline inclusion, monitor paths, artifacts manifest, sandbox record.

## Resource Rules
- Use visible GPUs/CPUs deliberately. If multiple GPUs/resources exist, generate task queues/allocation or explain why not parallelizable.
- Use DDP for a single multi-GPU training job when applicable; use task parallelism only for independent runs/slices.
- Remote runs must record push/pull sync evidence and redacted logs.

## Stop / Backtrack Rules
- Do not skip dataset/checkpoint/download just because it is slow; record wait/resume commands.
- Download/acquisition blockers are not PASS conditions. If datasets, baseline code, baseline weights, checkpoints, or model assets are still `failed`, `running`, `queued`, `blocked_user_action`, unavailable, or not verified, the stage/review must be non-PASS until the artifact is completed with evidence or a HALT is raised for human action after recorded attempts.
- M3S01 cannot PASS with vague baseline placeholders. Each baseline must have a concrete reference metric value for the corresponding dataset/scenario/split/metric and source truth (`source_id`, exact title, venue, year, modality, task, table/section) that can be checked against `M1_source_log.yaml`.
- Watchdog alerts require an agent decision: `continue`, `fix_and_rerun`, `early_stop`, or `backtrack_request` with evidence.
- If design, dataset, metric, or baseline is invalid, request structured backtrack instead of silently changing upstream assumptions.
- Do not mark M3S04 complete while a required training stage is still running. E0/random/untrained weights are diagnostic only and must never populate the final proposed/ours result row.
- If a run is under target, first use autonomous repair within scope: fix data/config/code, resume training, download missing weights, retrain a baseline, adjust resources, or backtrack to M3S03/M3S02/M2 as needed. Do not stop at hyperparameter tuning if the root cause is elsewhere.
- Treat any implementation shortcut, metric/data/label leakage, invalid diagnostic row, or protocol-mismatched result as non-claim evidence until verified. Route to the owning M3 stage, invalidate downstream rows, and rerun M3S04; do not defer this to M4.
- Do not prescribe exact code patches for suspected implementation shortcuts unless code/config/log evidence was directly inspected; otherwise write task-level inspect/verify/repair advice.

## M3S03 Baseline Lock Rules
- M3S03 must not use paper-reported numbers alone as the baseline for M3S04; each primary comparator needs a local verified metric or an explicitly bounded waiver.
- M3S03 must not invent or mutate source metadata. Every eligible baseline must bind to `M1_source_log.yaml` through `source_id` and match exact title, venue, year, modality, and task; modality/task mismatch makes the baseline ineligible for M3S04.
- M3S03 must not define or silently replace metrics. Each primary comparator must cite an M2S05 `metric_protocol_id` and match that protocol's dataset, scenario, split, metric key, direction, value range, and normal reference range.
- If a baseline local value is outside the M2 normal reference range or has a large paper/local deviation, M3S03 must write structured anomaly/deviation triage with evidence paths and request REVISE/BACKTRACK as needed; it must not mark that result as `verified_match` or `verified_close`.
- If a baseline depends on pretrained weights/checkpoints, actively locate and acquire them from official releases, README-linked storage, framework auto-download, HuggingFace, third-party mirrors, or project cache before declaring it unavailable.
- Required checkpoints must record source URL, local path, checksum, loadability verification, and acquisition/search attempts. A required checkpoint without a real local file cannot enter M3S04.
- M3 baselines must be external comparators from prior work, official packages, or full faithful reproductions. They must not be ablations, variants, or disabled-component versions of the proposed method; ablations are M4-only.
- A self-implemented/reimplemented baseline must be a full reproduction of the paper/model. Simplified, toy, minimal, proxy, or partial implementations are forbidden as M3 baselines; if full fidelity cannot be reached, request backtrack or mark the comparator ineligible.
- Baseline code is mutable only during M3S03 repair. After `baseline_code_immutable_after_lock: true`, M3S04 must treat baseline code, checkpoint, dataset split, and metric contract as read-only.
- For any task where side information or target-derived state could create a shortcut, M3S03 must audit the implementation contract stated by M2S05/M3S01 and mark the comparator ineligible until the shortcut is removed or explicitly justified by the protocol.
- `trusted_with_caveats` is not enough by itself. It must include `caveat_waiver_reason`, `comparison_scope_limit`, and `m3s04_eligible: true`; otherwise request backtrack or mark the baseline ineligible.
- M3S04 may start only when `experiments/baselines/baseline_lock.yaml` declares a primary comparator with `m3s04_eligible: true` and an existing `metric_contract` path.

## M3S04 Run Registry Rules
- Formal M3S04 rows live in `experiments/tables/results_main.tsv`; all attempts live in `experiments/tables/results_all.tsv`; invalid or historical diagnostic rows live in `experiments/tables/results_invalid.tsv`.
- Every proposed/ours row in `results_main.tsv` must have a matching `experiments/run_registry.yaml` entry with `status: completed` and `validity: valid_main` or `valid_reference`.
- Each formal run registry entry must point to existing `run_manifest.yaml`, `config.yaml`, `training_history.json`, `metrics.tsv`, checkpoint, `checkpoint_manifest.yaml`, `status.json`, `resource_monitor.csv`, and watchdog evidence.
- Checkpoint-only, interrupted, legacy, invalid, metric-bug, C-mismatch, missing-history, or proxy-only runs must be labeled invalid/interrupted/checkpoint-only and cannot appear in `results_main.tsv`.
- Leakage/shortcut/protocol-invalid rows must be labeled diagnostic or invalid, excluded from `experiments/tables/results_main.tsv`, and recorded with `invalid_reason`, evidence path, and `backtrack_target` in `experiments/tables/results_invalid.tsv`.
- Use stable run ids: `<stage>_<role>_<config_id>_<dataset>_<keyparams>_seed42_<YYYYMMDD-HHMMSS>`. Do not mix baseline, main, analysis, invalid, and legacy runs in one undifferentiated directory.
