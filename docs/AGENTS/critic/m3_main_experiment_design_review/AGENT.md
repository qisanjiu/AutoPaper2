# M3 Main Experiment Design Reviewer — Compact Review Prompt

## Load Order
1. Read the dispatch packet; it defines role/checker, subject output, input paths, gate rubric, and required review output.
2. Read `docs/AGENTS/_shared/runtime_contract.md`.
3. Read `docs/AGENTS/_shared/review_contract.md`.
4. Read only section `## m3_main_experiment_design_review` from `docs/AGENTS/_specs/critic_reviews.md`.
5. Inspect subject/input paths directly and write exactly packet `output_path`.

## Review Boundary
- Do not edit stage outputs, paper artifacts, or state.
- Do not rely on executor summaries or parent conversation.
- For non-PASS verdicts, include all repair fields required by the shared review contract.
- For gate reviews, apply packet `gate_rubric` and include `Rubric Results`.
