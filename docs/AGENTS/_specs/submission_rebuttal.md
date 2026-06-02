# Submission / Rebuttal / Revision Compact Spec

## Submission Agent
- `M6S01`: audit M1-M5 completeness, integrity, venue compliance, anonymization, source/figure/bib package, and readiness. Must wait for internal peer review threshold before external submission.
- `M6S02`: perform external paperreview.ai submission through configured script, record tracking/status/log JSON, and next email monitoring step. No simulated success unless explicitly marked blocked.

## Rebuttal Agent
- `M6S03`: parse review email/source, preserve raw evidence, atomicize reviewer items into matrix with id, quote/summary, class, severity, target stage, and evidence need.
- `M6S04`: produce rebuttal strategy and executable action plan. Each action needs `target_stage`, `required_fix`, `success_criteria`, `rebuild_mode`, `rerun_scope`, and priority.
- `M6S06`: validate item resolution, compare against G5 quality, identify regressions, and decide completion or further backtrack.

## Revision Agent
- `M6S05`: use script-generated routes. Confirm routed subagents completed target-stage work before writing revision execution record. Each resolved item needs evidence path; partial/blocked items must stay explicit.

## Rules
- Do not treat evidence/experiment fixes as text-only edits.
- Cannot-fully-address items must be answered honestly with limitation text and evidence.
- Resolution claims must map to reviewer item ids.
