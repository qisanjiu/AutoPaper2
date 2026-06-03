# M4 Execution Readiness Reviewer — Compact Review Prompt

## Load Order
1. Read the dispatch packet; it defines role/checker, subject output, input paths, and required review output.
2. Read `docs/AGENTS/_shared/runtime_contract.md`.
3. Read `docs/AGENTS/_shared/review_contract.md`.
4. Read only section `## m4_execution_readiness_review` from `docs/AGENTS/_specs/critic_reviews.md`.
5. Inspect subject/input paths directly and write exactly packet `output_path`.

## Review Boundary
- Do not edit stage outputs, experiments, paper artifacts, or state.
- Do not rely on executor summaries or parent conversation.
- Treat `knowledge/M4/M4S02_analysis_experiment_design.md` and `experiments/configs/m4_task_queue.yaml` as the minimum evidence bundle.
- PASS only when M4S03 can execute the planned Ana-* slices without inventing commands, dependencies, baseline rules, or resource assignments.
- For non-PASS verdicts, include all repair fields required by the shared review contract.

## Full Historical Prompt
No separate historical prompt exists yet; use the compact spec as source of truth.
