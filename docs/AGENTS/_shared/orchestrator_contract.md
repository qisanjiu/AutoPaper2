# AutoPaper2 Orchestrator Contract

The main agent is conductor only.

## Allowed Actions
1. Read `state/pipeline_state.yaml` and status files.
2. Decide next action with `Conductor.get_next_action()` or `state_manager.py status`.
3. Generate dispatch packets:
   - `python scripts/state_manager.py dispatch next --write`
   - `python scripts/state_manager.py dispatch stage <stage> --write`
   - `python scripts/state_manager.py dispatch reviews <stage> --write`
   - `python scripts/state_manager.py dispatch gate <Gx> --write`
4. Create the matching subagent with exactly the compact launch prompt printed by dispatch, or extract it with:
   `python scripts/subagent_launch_prompt.py --packet <packet_path>`
5. Verify output file existence and parse review verdicts.
6. Advance through `state_manager.py advance` or backtrack through Conductor/state_manager APIs.

## Auto-Run Autonomy
- When project auto-run is active, enable `auto_advance_modules` and do not pause at module boundaries.
- `REVISE`, `REWORK`, `FIX`, and `BACKTRACK` are normal loop states, not user questions. Apply structured backtrack advice, regenerate dispatch for the target stage, and continue.
- Backtracking may target any responsible upstream stage, including dataset acquisition, baseline lock, implementation, training, experiment design, method design, or hypothesis stages. Do not reduce repair to hyperparameter tuning when evidence points elsewhere.
- Ask the user only for Gate HALT, spiral limit, explicit pause/stop, secrets, paid/quota approvals, unavailable storage/network access, or unsafe/destructive actions.

## Forbidden Actions
- Do not write `knowledge/M*/`, `drafts/`, `knowledge/reviews/*_review.md`, `artifacts/paper.*`, or stage evidence on behalf of subagents.
- Do not paste parent conversation, upstream file contents, or executor summaries into subagent prompts.
- Do not manually compose subagent prompts from memory. Use the dispatch-generated compact launch prompt.
- Do not skip required stage reviews or gate reviews.
- Do not convert a non-PASS critic review into aggregate PASS. Individual critic verdicts are authoritative for gate advancement.
- Do not advance on PASS reviews/gates that contain unresolved blockers or vague/deferred evidence such as pending, failed, unavailable, not verified, cannot download, waiting for user, TODO/TBD, maybe/probably, "基本通过", or "先推进".
- Do not treat dataset, baseline code, baseline weight, checkpoint, model asset, external submission, or review-email acquisition blockers as PASS; continue attempts or require non-PASS/HALT.

## Backtrack
Use structured repair advice. After backtrack, regenerate dispatch from target stage; old downstream files are historical unless `incremental_replay` is explicitly allowed.
