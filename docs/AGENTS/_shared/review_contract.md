# AutoPaper2 Shared Review Contract

## Verdicts
- `PASS`: output satisfies the role checklist and required evidence exists.
- `REVISE`: same stage can repair a bounded problem without changing upstream assumptions.
- `BACKTRACK`: root cause is upstream or downstream must be regenerated from a target stage.
- `HALT`: cannot proceed without user/external action, unsafe state, missing secret, legal/ethical blocker, or repeated impossible dependency.

## PASS Integrity
- A `PASS` review must not contain unresolved blockers, vague approval, or deferred evidence. Phrases such as pending, failed, missing, unavailable, not verified, unable to download, waiting for user, TODO/TBD, maybe/probably/likely, "基本通过", "先推进", or "等待人工" make PASS invalid.
- Dataset, baseline code, baseline weights, checkpoints, model assets, external submissions, and review emails must be either completed with evidence or reviewed as non-PASS. If human action is genuinely required after recorded attempts, use `HALT` with repair fields/evidence, not PASS.
- Reviewers must treat "cannot download" as an objection unless the stage shows multiple concrete acquisition attempts and the review verdict is non-PASS.

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

## Review Output Location
- Write the review only to packet `output_path`.
- If re-reviewing after a backtrack or human revision, overwrite/update the same canonical review file in place.
- Do not create alternate review files such as `_v2`, `_new`, `_revised`, `_revision`, `_backtrack`, `_fixed`, `_updated`, `_draft`, or `_copy`.

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
