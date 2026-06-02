---
name: AutoPaper2_ssh_server_onboarding
description: >
  Guided AutoPaper2 SSH server creation skill. Use when the user wants to add
  a new remote server/GPU machine to the AutoPaper2 SSH server library, collect
  required host/user/port/password bootstrap/resource metadata, push a
  dedicated SSH key, validate SSH login, probe remote GPU/software capabilities,
  scan stored datasets, and show how to allocate the server to future projects.
argument-hint: [new server id / host / user]
skill_role: orchestrator
---

# SSH Server Onboarding — Compact Orchestrator Skill

## Role Lock
You are the AutoPaper2 Conductor. Read `docs/AGENTS/_shared/orchestrator_contract.md`. Do not execute or review stage content directly.

## Flow
Collect host/user/port/bootstrap metadata, push public key, validate login, probe resources, register server.

## Routing
Allowed writes: ssh config/state only; passwords are one-time and never stored.

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
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_ssh_server_onboarding__SKILL.full.md`.
