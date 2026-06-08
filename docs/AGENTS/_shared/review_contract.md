# AutoPaper2 Shared Review Contract

## Verdicts
- `PASS`: output satisfies the role checklist and required evidence exists.
- `REVISE`: same stage can repair a bounded problem without changing upstream assumptions.
- `BACKTRACK`: root cause is upstream or downstream must be regenerated from a target stage.
- `HALT`: cannot proceed without user/external action, unsafe state, missing secret, legal/ethical blocker, or repeated impossible dependency.

## PASS Integrity
- A `PASS` review must not contain unresolved blockers, vague approval, or deferred evidence. Phrases such as pending, failed, missing, unavailable, not verified, unable to download, ineligible, not implemented, not run, proxy only, undertrained, reference only, defer to M4, waiting for user, TODO/TBD, maybe/probably/likely, "基本通过", "先推进", "等待人工", "不合格", "未实现", "未运行", "训练不足", "仅作参考", or "留到M4" make PASS invalid.
- In experiment reviews, unresolved invalid/diagnostic result rows, metric/data/label leakage, shortcut language, protocol mismatch, out-of-range metrics without triage, or incomplete trained-run evidence also make PASS invalid unless the line explicitly says the issue is resolved and cites verification evidence.
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

## Repair Advice Integrity
- Route source/modality/task/baseline eligibility failures to the stage that owns the invalid assumption, usually M3S01 or M3S03.
- Route implementation bugs, metric/data/label leakage, invalid/diagnostic result rows promoted as evidence, or protocol-result mismatches to the stage that owns the broken assumption, usually M3S02, M3S03, or M3S04, and require M3S04-M3S05 rerun when main results change.
- Do not prescribe exact implementation patches as a leakage/shortcut fix unless the reviewer directly inspected the corresponding code/config/log evidence.
- Do not route unresolved M3 experimental blockers to M4 analysis.

## Reviewer Evidence Boundary
- Reviewer findings and `required_fix` must stay within the evidence actually checked.
- If `Evidence Checked` and `evidence_paths` contain only Markdown stage outputs, the reviewer may write task-level advice only: identify the symptom, target owner stage, files/classes to inspect if justified by the Markdown, required verification, and rerun scope.
- Do not invent line-level patches, function calls, signatures, config values, commands, or exact code edits unless the corresponding code/config path was directly checked and is listed in `Evidence Checked` or `evidence_paths`.
- For suspected implementation bugs observed only through result Markdown, write `required_fix` as inspect -> verify root cause -> repair -> add evidence/tests -> rerun downstream, not as an unverified patch.

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
