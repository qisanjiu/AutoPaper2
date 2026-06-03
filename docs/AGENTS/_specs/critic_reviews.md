# Critic / Reviewer Compact Spec

Use `docs/AGENTS/_shared/review_contract.md` for verdict schema. Read only the section matching your role/checker.

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
Check empirical support, reproducibility, baseline fairness, metric contract, seeds/statistics, evidence ladder, negative results, resource records, and claim/evidence alignment.

## writing
Check paper clarity, claim discipline, section coherence, citation/terminology consistency, abstract/conclusion numeric consistency, and whether text overclaims evidence.

## ethics
Check human subjects, sensitive data, privacy, bias/fairness, misuse/dual-use, licenses, anonymization, and required disclosures. If not applicable, mark explicitly.

## code_review
Review experiment code quality and reproducibility: runnable entrypoints, configs, hardcoded paths, dependency lock, logging, seeds, outputs, no secret leakage.

## data_checker
Review dataset availability, licenses, checksums/splits, cache/symlink paths, pending dataset report, and no hidden unavailable data dependency.

## m2_search_quality
Check M2S01 search dimensions, source diversity, M1 cross-check, candidate novelty/difference, query ledger, and `M2_source_log.yaml` completeness.

## m2_migration
Check M2S02 mappings: source problem, target problem, transferable mechanism, adaptation changes, why direct reuse is insufficient, no over-combination, M1 overlap handled.

## m2_design_review
Check M2S03/M2S04 architecture/algorithm/theory: notation, components, assumptions, complexity, proof honesty, gap/hypothesis trace, implementation readiness.

## m2_experiment_design_review
Check M2S05 dataset/baseline/metric/split/seed/fairness/resource design, relation to hypotheses, and baseline acquisition/verification plan.

## m2_experiment_plan_review
Check M2S06 execution order, branching/failure logic, success criteria, risk budget, at least main + ablation + robustness/boundary plan, and report blueprint.

## m3_dataset_env_review
Check M3S01 dataset first, env lock, sandbox profile, resource plan, hardware probe, multi-resource queue/allocation where needed, SSH evidence, longrun ledger, smoke run, no secrets.

## m3_baseline_result_review
Check M3S02 baseline verification, checkpoint acquisition/loadability, metric contract, smoke run, fairness, paper/history deviation, and locked comparator immutability.

## m3_baseline_lock_audit
Audit whether M3S02 is safe to unlock M3S03. Require a structured baseline lock manifest, at least one primary comparator with `m3s03_eligible: true`, loadable checkpoints when applicable, acceptable paper/local metric deviation or an explicit waiver, immutable baseline code after lock, and a clearly bounded comparison scope. PASS only if the locked comparator can be used by M3S03 without changing baseline assumptions.

## m3_main_result_review
Check M3S03 run contract, results.tsv, logs/configs/seeds, baseline comparison, resource utilization, watchdog decisions, negative attempts, and evidence ladder.

## m4_findings_audit
Check M4S01 consolidation of main/negative/unexpected findings, claim candidates, efficiency need, source-log/protocol basis, and analysis campaign coverage.

## m4_analysis_design_review
Check M4S02 analysis slices: how/where/why coverage, ablation one-factor discipline, baseline inclusion, literature basis, efficiency need, executable commands/evidence plan.

## m4_execution_readiness_review
Audit whether M4S02 can be executed by M4S03 without redesign. Require `experiments/configs/m4_task_queue.yaml`, concrete `Ana-*` task ids matching the design document, commands or blocked reasons, dependencies, resource requirements, baseline inclusion/fairness keys, expected artifacts, success criteria, and no unresolved design-to-execution gaps.

## m4_analysis_execution_review
Check M4S03 executed planned slices, `analysis_results.tsv`, baseline rows, resource monitor, sandbox/container record, artifacts, abnormal triage, no hidden negative results or secret leakage.

## m5_stage_review
Use checker name/stage to review M5 output. Always check upstream evidence grounding, no invented numbers/citations/components, figure provenance, style-profile use, LaTeX/build impact, and stage-specific completeness.

## m6_internal_peer_review
Simulate multiple strict reviewers for M6S01. Require aggregate score >= 8/10 and unresolved high-priority issues = 0 before external submission. Produce atomic high/medium issues for revision if not pass.

## m6_stage_review
Check M6 stage-specific integrity: submission package readiness, external submission evidence, faithful review parsing, actionable rebuttal plan, routed revision execution, resolution validation.

## resolution
Check every reviewer item is addressed by evidence, text, experiment, or honest limitation; no quality regression against G5; unresolved medium/high items require REVISE/BACKTRACK.
