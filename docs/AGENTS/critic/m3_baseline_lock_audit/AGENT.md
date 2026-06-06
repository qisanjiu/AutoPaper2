# M3 Baseline Lock Audit Reviewer — Compact Review Prompt

## Load Order
1. Read the dispatch packet; it defines role/checker, subject output, input paths, and required review output.
2. Read `docs/AGENTS/_shared/runtime_contract.md`.
3. Read `docs/AGENTS/_shared/review_contract.md`.
4. Read only section `## m3_baseline_lock_audit` from `docs/AGENTS/_specs/critic_reviews.md`.
5. Inspect subject/input paths directly and write exactly packet `output_path`.

## Review Boundary
- Do not edit stage outputs, paper artifacts, experiments, or state.
- Do not rely on executor summaries or parent conversation.
- Treat `knowledge/M3/M3S03_baseline_lock.md`, `experiments/baselines/**/metric_contract.yaml`, and `experiments/baselines/baseline_lock.yaml` as the minimum evidence bundle.
- PASS only when M3S04 can use the locked comparator without changing baseline assumptions, metric definitions, dataset splits, checkpoint state, or comparison scope.
- For non-PASS verdicts, include all repair fields required by the shared review contract.

## Full Historical Prompt
No separate historical prompt exists yet; use the compact spec as source of truth.
