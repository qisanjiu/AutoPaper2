# AutoPaper2 Shared Runtime Contract

This contract applies to every delegated subagent.

## Source Of Truth
- The dispatch packet is authoritative for `task_type`, `role`, `stage`, `gate_id`, `agent_md`, `input_docs`, `subject_output`, `output_path`, `backtrack_advice`, and `context_policy`.
- Do not inherit factual context from the parent conversation. Use the parent message only to locate the packet.
- Read in this order: dispatch packet -> this shared contract -> role `AGENT.md` -> role/stage spec -> only needed input paths.

## Context Discipline
- Pass and consume paths, not summaries. Never paste full upstream papers, logs, PDFs, run directories, or prior conversations into active context.
- For large files/directories: inspect filename, size, headings, manifests, tables, tails, or grep hits first; then read only relevant slices.
- If `context_policy.resume_required` is true or context grows, update the packet worklog path and stop with a concise resume note.

## Executor Boundary
- Stage executors write only the packet `output_path` plus explicitly required evidence/worklog artifacts.
- Executors must not write review verdicts and must not call `state_manager.py advance`.
- If a required input is missing or blocked, write a bounded blocked record at the assigned output path with evidence paths and next action.

## Output Write Policy
- The packet `output_path` is the only canonical Markdown output for the assigned task.
- On backtrack, re-execution, revision, or re-review, update or overwrite the same `output_path` in place.
- Do not create sibling Markdown copies with suffixes such as `_v2`, `_new`, `_revised`, `_revision`, `_backtrack`, `_fixed`, `_updated`, `_draft`, or `_copy`.
- Historical outputs may be read as audit evidence only when the packet allows it; they must not become new canonical outputs.

## Reviewer Boundary
- Reviewers do not modify subject outputs. They write exactly one review file at packet `output_path`.
- Reviewers read original paths directly and must not rely on executor summaries.

## Common Recovery
If resumed or compacted: reread the dispatch packet, this contract, the role spec, `state/pipeline_state.yaml`, and the packet worklog if present; continue from durable files, not memory.
