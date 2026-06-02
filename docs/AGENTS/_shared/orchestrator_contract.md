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

## Forbidden Actions
- Do not write `knowledge/M*/`, `drafts/`, `knowledge/reviews/*_review.md`, `artifacts/paper.*`, or stage evidence on behalf of subagents.
- Do not paste parent conversation, upstream file contents, or executor summaries into subagent prompts.
- Do not manually compose subagent prompts from memory. Use the dispatch-generated compact launch prompt.
- Do not skip required stage reviews or gate reviews.

## Backtrack
Use structured repair advice. After backtrack, regenerate dispatch from target stage; old downstream files are historical unless `incremental_replay` is explicitly allowed.
