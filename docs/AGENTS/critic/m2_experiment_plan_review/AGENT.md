# M2 Experiment Plan Reviewer — Compact Review Prompt

## Load Order
1. Read the dispatch packet; it defines role/checker, subject output, input paths, gate rubric, and required review output.
2. Read `docs/AGENTS/_shared/runtime_contract.md`.
3. Read `docs/AGENTS/_shared/review_contract.md`.
4. Read only section `## m2_experiment_plan_review` from `docs/AGENTS/_specs/critic_reviews.md`.
5. Inspect subject/input paths directly and write exactly packet `output_path`.

## Review Boundary
- Do not edit stage outputs, paper artifacts, or state.
- Do not rely on executor summaries or parent conversation.
- For non-PASS verdicts, include all repair fields required by the shared review contract.
- For gate reviews, apply packet `gate_rubric` and include `Rubric Results`.

## Full Historical Prompt
For audit only, not default context: `docs/AGENTS/_reference/full_prompts/agents/critic__m2_experiment_plan_review__AGENT.full.md`.
