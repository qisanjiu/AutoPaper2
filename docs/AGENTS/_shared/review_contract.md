# AutoPaper2 Shared Review Contract

## Verdicts
- `PASS`: output satisfies the role checklist and required evidence exists.
- `REVISE`: same stage can repair a bounded problem without changing upstream assumptions.
- `BACKTRACK`: root cause is upstream or downstream must be regenerated from a target stage.
- `HALT`: cannot proceed without user/external action, unsafe state, missing secret, legal/ethical blocker, or repeated impossible dependency.

## Required Non-PASS Fields
Every `REVISE`, `BACKTRACK`, `FIX`, or `REWORK` review must include:
- `target_stage`
- `blocking_reason`
- `required_fix`
- `success_criteria`
- `evidence_paths` (project-local paths; at least one real path when possible)
- `rebuild_mode`: `full_regenerate` or `incremental_replay`
- `rerun_scope`
- `handoff_updates`

## Review Output Skeleton
```markdown
# Review: <task>

## Verdict
Verdict: PASS|REVISE|BACKTRACK|HALT

## Evidence Checked
- <path>: <what was checked>

## Findings
| severity | issue | evidence_path | required_fix |
|---|---|---|---|

## Scores / Rubric
<use packet gate_rubric or role checklist>

## Repair Fields
- target_stage:
- blocking_reason:
- required_fix:
- success_criteria:
- evidence_paths:
- rebuild_mode:
- rerun_scope:
- handoff_updates:
```

## Gate Reviews
Gate critics must apply packet `gate_rubric` and include a `Rubric Results` table. The conductor creates the aggregate; individual critics do not advance state.
