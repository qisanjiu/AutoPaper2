# Critic / Reviewer Compact Spec

Use `docs/AGENTS/_shared/review_contract.md` for verdict schema. Read only the section matching your role/checker.

## evidence_boundary
Reviewer advice must be grounded in files actually checked. If you only inspected Markdown reports, write task-level repair advice: route to the owning stage, name the suspected symptom, require the executor to inspect/verify/repair the implementation or protocol, specify success criteria/evidence, and rerun downstream. Do not prescribe exact code lines, function calls, signatures, config values, or shell commands unless the relevant code/config/log path was directly read and listed in `Evidence Checked` or `evidence_paths`.

## source_log_validator
Validate M1/M2 source logs: required top-level keys, stable ids, credibility, discovery source/query, gap/solution maps, search statistics, query ledger, and no uncited literature claims. Prefer existing validator scripts when available.

## survey_review
Review M1S02 round outputs: search breadth/depth/blindspots, source credibility, gap taxonomy, solution arsenal, source log consistency, survey memory updates, and whether another round/backtrack is needed.

## coverage
Check M1 coverage and final idea readiness: topic scope, literature classes, gap evidence, novelty space, feasibility, downstream handoff. Block if major subfield or closest-work class is missing.

## logic
Check argument chain: topic -> gaps -> questions -> hypotheses -> method -> experiments -> claims. Verify FINER-like feasibility, ethical note when relevant, no unsupported jumps, and correct backtrack target.

## novelty
Check whether the core idea is substantively new relative to closest work, not just renamed/combined/decorative. Require bottleneck/component rationale for architecture improvements and honest novelty type.

## method
Check method soundness, migration validity, assumptions, formalization, component necessity, relation to existing work, and whether M2/M1 backtrack is needed.

## evidence
Check empirical support, reproducibility, baseline fairness, metric contract, seeds/statistics, evidence ladder, negative results, resource records, trained-checkpoint completion evidence, and claim/evidence alignment. For G3, PASS is forbidden if proposed/ours results rely on random, E0, untrained, still-running weights, PPL≈1/accuracy≈1 noisy-channel leakage, clean memory bypass, or SNR-invariant PPL.

## writing
Check paper clarity, claim discipline, section coherence, citation/terminology consistency, abstract/conclusion numeric consistency, and whether text overclaims evidence.

## ethics
Check human subjects, sensitive data, privacy, bias/fairness, misuse/dual-use, licenses, anonymization, and required disclosures. If not applicable, mark explicitly.

## code_review
Review experiment code quality and reproducibility: runnable entrypoints, configs, hardcoded paths, dependency lock, logging, seeds, outputs, no secret leakage.

## data_checker
Review dataset availability, completeness, checksums/splits/counts, cache/symlink paths, longrun ledger acquisition status, and no hidden unavailable data dependency. PASS is forbidden if `M3S02_dataset_pending.md` exists, `experiments/data/dataset_manifest.yaml` is missing/incomplete, any required split/file is absent or zero-count, smoke-load evidence is missing, or any dataset/model-asset acquisition ledger row is failed, running, queued, blocked_user_action, missing log evidence, or waiting for human action.

## m2_search_quality
Check M2S01 search dimensions, source diversity, M1 cross-check, candidate novelty/difference, query ledger, and `M2_source_log.yaml` completeness.

## m2_migration
Check M2S02 mappings: source problem, target problem, transferable mechanism, adaptation changes, why direct reuse is insufficient, no over-combination, M1 overlap handled.

## m2_design_review
Check M2S03/M2S04 architecture/algorithm/theory: notation, components, assumptions, complexity, proof honesty, gap/hypothesis trace, implementation readiness.

## m2_experiment_design_review
Check M2S05 dataset/baseline/metric/split/seed/fairness/resource design, relation to hypotheses, baseline acquisition/verification plan, and `knowledge/M2/M2S05_metric_protocol.yaml`. Baselines must be external comparators or full reproductions, not ablations or disabled-component variants of the proposed method. Every metric protocol must bind metric to dataset, scenario/task, split, definition, calculation, direction, value range, normal reference range, protocol source, and sanity-check case.

## m3_main_experiment_design_review
Check M3S01 main-experiment-only design: dataset/scenario/split, metric_protocol_id references from M2S05, external/prior-work baseline list, concrete baseline reference values on the same dataset/scenario/split/metric, source_id/title/venue/year/modality/task/table-or-section matching `knowledge/M1/M1_source_log.yaml`, proposed-method same-condition protocol, seed=42, fairness/resource constraints, and explicit blockers. PASS is forbidden if baseline values are TBD/missing/not source-located, if source metadata appears invented or mismatched, if a paper's modality/task is not comparable to the project task, if baselines are ablations of the proposed method, if metric protocol IDs are missing or inconsistent with M2S05, or if the document designs ablation/robustness/mechanism/M4 analysis work instead of only the main experiment.

## m3_dataset_env_review
Check M3S02 dataset first, env lock, sandbox profile, resource plan, hardware probe, multi-resource queue/allocation where needed, SSH evidence, longrun ledger, smoke run, no secrets. Dataset review must validate `experiments/data/dataset_manifest.yaml`: every required main-experiment dataset has a complete/verified status, project-local path, required files, explicit splits, positive actual counts, expected-count match when declared, checksum verification when declared, and smoke-load log. PASS is forbidden for partial datasets, residual placeholder files, pending downloads, hidden data dependencies, or any dataset/baseline/model-asset acquisition still failed/running/queued/blocked.

## m3_baseline_result_review
Check M3S03 baseline verification, checkpoint acquisition/loadability, source_id/title/venue/year/modality/task consistency with `M1_source_log.yaml`, metric contract, smoke run, fairness, paper/history deviation, metric_protocol_id alignment with M2S05, metric implementation sanity-check evidence, full reproduction fidelity for self-implemented comparators, no simplified/toy baselines, no ablation-as-baseline misuse, and locked comparator immutability. For noisy-channel/text semantic communication baselines, audit that decoder inputs cannot see clean encoder memory, target tokens, teacher-forced target state, clean embeddings, or any hidden state that bypasses the channel. REVISE/BACKTRACK if source metadata is hallucinated/mismatched, if a metric is wrong for the dataset/scenario, if the value is outside the M2 normal reference range without triage, if a large deviation is hidden behind `verified_match`/`verified_close`, if PPL≈1/accuracy≈1/SNR-invariant PPL suggests leakage, or if required baseline code/weights/checkpoints are not downloaded, checksumed, and verified loadable.

## m3_baseline_lock_audit
Audit whether M3S03 is safe to unlock M3S04. Require a structured baseline lock manifest, at least one primary external/prior-work comparator with `m3s04_eligible: true`, source truth matching `M1_source_log.yaml`, loadable checkpoints when applicable, M2S05 metric_protocol_id alignment, metric sanity-check evidence, acceptable paper/local metric deviation or an explicit waiver, immutable baseline code after lock, no ablation/proposed-method variant in the baseline list, full reproduction fidelity for self-implemented comparators, no clean-memory/target bypass in noisy-channel implementations, and a clearly bounded comparison scope. PASS only if the locked comparator can be used by M3S04 without changing baseline assumptions, source metadata, metric definitions, dataset/scenario/split, checkpoint acquisition state, leakage status, or comparison scope.

## m3_main_result_review
Check M3S04 run contract, `experiments/tables/results_main.tsv`, `experiments/tables/results_all.tsv`, `experiments/run_registry.yaml`, logs/configs/seeds, baseline comparison, completed trained-checkpoint paths for proposed/ours rows, training completion events, resource utilization, watchdog decisions, negative attempts, PPL/channel leakage sanity, and evidence ladder. REVISE/BACKTRACK if Stage 1 or any required training is still running, if only E0/random/checkpoint-only/no-history weights are evaluated, if no trained checkpoint can be loaded, if formal result rows lack a registry entry with completed status and existing manifest/config/history/metrics/status evidence, or if formal noisy-channel rows show PPL<=1.05 with near-perfect accuracy or SNR-invariant PPL. Leakage/code bugs route to M3S02 or M3S03 and require M3S04 rerun; do not defer to M4.

## m3_result_validation_review
Check M3S05 result validation, evidence packaging, KEEP/FIX/BACKTRACK honesty, claim boundaries, M3S04-to-M3S05 metric consistency, baseline fairness carry-through, data-quality checks, single-seed limitations, negative/failed results, root-cause analysis, artifact manifest, metric contract, comparison table, reproduction notes, and M3-to-M4 handoff. PASS is forbidden if M3S05 claims KEEP while evidence artifacts are missing, if any primary baseline is ineligible/non-comparable, if external baseline match fails, if metrics are not implemented/proxy-only/not-run, if results are undertrained/checkpoint-only, if it ignores anomalous or weak results, if PPL≈1/accuracy≈1/SNR-invariant PPL or clean memory bypass remains unresolved, if it broadens claims beyond fixed seed=42 evidence, if it fails to route needed repair to M3S04/M3S03/M3S02/M2, or if it uses vague language to advance despite unresolved blockers. A repair suggestion that fixes leakage by passing clean encoder memory into the decoder is invalid unless the memory itself is channel-transmitted/noised.

## m4_findings_audit
Check M4S01 consolidation of main/negative/unexpected findings, claim candidates, efficiency need, source-log/protocol basis, and analysis campaign coverage.

## m4_analysis_design_review
Check M4S02 analysis slices: how/where/why coverage, ablation one-factor discipline, baseline inclusion, literature basis, efficiency need, executable commands/evidence plan.

## m4_execution_readiness_review
Audit whether M4S02 can be executed by M4S03 without redesign. Require `experiments/configs/m4_task_queue.yaml`, concrete `Ana-*` task ids matching the design document, commands or blocked reasons, dependencies, resource requirements, baseline inclusion/fairness keys, expected artifacts, success criteria, and no unresolved design-to-execution gaps.

## m4_analysis_execution_review
Check M4S03 executed planned slices, `analysis_results.tsv`, baseline rows, resource monitor, sandbox/container record, artifacts, abnormal triage, no hidden negative results or secret leakage.

## m5_stage_review
Use checker name/stage to review M5 output. Always check upstream evidence grounding, no invented numbers/citations/components, figure provenance, style-profile use, LaTeX/build impact, and stage-specific completeness. Generic PASS is forbidden; choose the checklist matching packet `role`/checker:
- `m5_prewrite_review`: verify M5S01 maps final claims to G3/G4 evidence, flags weak/negative results, preserves limitations, and blocks unsupported contribution inflation.
- `m5_outline_style_review`: verify M5S02 section plan, figure/table plan, terminology, citation slots, claim budget, and paper style profile before drafting.
- `m5_intro_relatedwork_review`: verify M5S03 motivation, gap framing, related-work positioning, citation grounding, and no novelty overclaim beyond M1/M2.
- `m5_method_figure_review`: verify M5S04 method description matches M2/M3 implementation, equations/algorithms are consistent, and figures have traceable source/provenance.
- `m5_experiments_results_review`: verify M5S05 numbers exactly match validated M3/M4 artifacts, baseline fairness is preserved, tables cite artifact paths, and no unresolved anomaly is hidden.
- `m5_analysis_discussion_review`: verify M5S06 analysis/discussion uses only M4-supported explanations, includes failures/limitations, and does not turn speculation into evidence.
- `m5_abstract_conclusion_review`: verify M5S07 headline claims and numeric summaries match the body and evidence, with no broader task/dataset/generalization claims than supported.
- `m5_final_compilation_review`: verify M5S08 assembled draft includes all required sections, references/figures/tables compile consistently, and build verifier issues are addressed.
- `m5_full_polish_review`: verify M5S09 improves coherence without changing claims, numbers, citations, method details, or limitations unsupported by evidence.

## m6_internal_peer_review
Simulate multiple strict reviewers for M6S01. Require aggregate score >= 8/10 and unresolved high-priority issues = 0 before external submission. Produce atomic high/medium issues for revision if not pass.

## m6_stage_review
Check M6 stage-specific integrity. Generic PASS is forbidden; choose the checklist matching packet `role`/checker:
- `m6_submission_audit`: verify M6S01 package readiness, final PDF/source/figures/supplement links, anonymization/ethics/data statements when relevant, and internal peer-review blockers resolved.
- `m6_external_submission_review`: verify M6S02 external submission evidence is real, with submission log/status/receipt or a non-PASS blocker if the external service/account/network is unavailable.
- `m6_review_parsing_review`: verify M6S03 faithfully parses all reviewer items into an atomic matrix without merging, dropping, softening, or inventing issues.
- `m6_rebuttal_strategy_review`: verify M6S04 action plan routes each reviewer item to text, experiment, analysis, limitation, or backtrack with concrete owner/stage/evidence criteria.
- `m6_revision_execution_review`: verify M6S05 executes routed revisions, records artifact/text deltas, reruns needed checks, and leaves unresolved external blockers as non-PASS.
- `m6_revision_validation_review`: verify M6S06 closes every high/medium reviewer item with evidence, no G5 quality regression, and honest unresolved-item accounting before completion.

## resolution
Check every reviewer item is addressed by evidence, text, experiment, or honest limitation; no quality regression against G5; unresolved medium/high items require REVISE/BACKTRACK.
