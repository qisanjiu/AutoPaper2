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

## Runtime Observability
- If the packet has `runtime_observability`, append progress events to `event_log_path` using `scripts/agent_run_log.py` or the same JSONL schema.
- At minimum record `packet_read`, `inputs_inspected`, `output_written_or_blocked`, and `completed_or_blocked`.
- Record produced or validated artifacts in `artifact_manifest_path` with path, kind, bytes, hash when available, and verification role.
- For substantial code edits, experiment launches, test runs, data-processing commands, or paper-build commands, record command evidence in `command_ledger_path` and patch/diff evidence in `code_change_ledger_path` using `scripts/code_execution_ledger.py` or the same YAML schema.
- These ledgers are audit evidence for later reviewers. They are not subagent permission allowlists and do not restrict which commands or files a delegated subagent may use.
- Redact secrets, credentials, API keys, tokens, private keys, and passwords from all logs and manifests.

## Executor Boundary
- Stage executors write only the packet `output_path` plus explicitly required evidence/worklog artifacts.
- Executors must not write review verdicts and must not call `state_manager.py advance`.
- If a required input is missing or blocked, write a bounded blocked record at the assigned output path with evidence paths and next action.

## Output Write Policy
- The packet `output_path` is the only canonical Markdown output for the assigned task.
- On backtrack, re-execution, revision, or re-review, update the same `output_path` in place.
- If `output_path` already exists, read it before writing. Preserve correct sections, tables, citations, evidence paths, and caveats that are not targeted by `backtrack_advice` or contradicted by current upstream inputs.
- Prefer section-level or smaller edits. Do not truncate and rewrite the whole Markdown file when a targeted edit can satisfy the repair.
- Whole-file replacement is allowed only when the existing file is structurally unusable or every major section is invalid; the completion summary must justify each removed major section.
- Do not create sibling Markdown copies with suffixes such as `_v2`, `_new`, `_revised`, `_revision`, `_backtrack`, `_fixed`, `_updated`, `_draft`, or `_copy`.
- Historical outputs may be read as audit evidence only when the packet allows it; they must not become new canonical outputs.
- If the packet `output_write_policy.section_anchor_policy.enabled` is true and the Markdown file already has `ap2:section` anchors, verify anchors before editing. If a section hash is stale, inspect the current file and record the conflict before refreshing hashes or editing.
- After meaningful Markdown edits, refresh section anchors with `scripts/markdown_section_hash.py refresh <path> --namespace <stage-or-task>` or an equivalent deterministic section-hash update.

## Reviewer Boundary
- Reviewers do not modify subject outputs. They write exactly one review file at packet `output_path`.
- Reviewers read original paths directly and must not rely on executor summaries.
- If `reviewer_memory_path` is provided, reviewers may update only that shared reviewer-memory file to record persistent concerns, resolved concerns, venue pressure points, and repeat failure patterns.

## Common Recovery
If resumed or compacted: reread the dispatch packet, this contract, the role spec, `state/pipeline_state.yaml`, the packet worklog/event log if present, artifact manifest if present, and reviewer memory if relevant; continue from durable files, not memory.
