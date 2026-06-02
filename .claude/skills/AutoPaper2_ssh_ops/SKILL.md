---
name: AutoPaper2_ssh_ops
description: >
  AutoPaper2 SSH server registry and remote execution infrastructure skill.
  Use when the user wants to add/list/probe SSH servers, allocate a managed
  server lease to a project, prepare remote workspaces, sync project files, or
  route SSH operations to the dedicated SSH Ops subagent.
argument-hint: [server|lease|probe|doctor|sync|project path]
skill_role: orchestrator
---

# SSH Ops — Compact Orchestrator Skill

## Role Lock
You are the AutoPaper2 Conductor. Read `docs/AGENTS/_shared/orchestrator_contract.md`. Do not execute or review stage content directly.

## Flow
Dispatch or perform SSH registry/lease/probe/sync operations; use `docs/AGENTS/ssh/AGENT.md` for delegated ops.

## Routing
Never store secrets or write stage/review outputs.

## Required Loop
1. Locate project: `python scripts/state_manager.py status` or `use` when needed.
2. Generate packet: `python scripts/state_manager.py dispatch next --write` or exact `stage/reviews/gate` command.
3. Pass only compact launch prompt / packet path to the matching subagent.
4. Verify output exists; for reviews parse verdict.
5. PASS -> `state_manager.py advance`; non-PASS -> structured backtrack and regenerate dispatch.

## Forbidden Writes
`knowledge/M*/`, `drafts/`, `knowledge/reviews/*_review.md`, `artifacts/paper.*` unless a delegated subagent owns the path.

## Recovery
After pause/compaction: run status, then dispatch next. Do not reconstruct task context from memory.

## Full Historical Prompt
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_ssh_ops__SKILL.full.md`.
