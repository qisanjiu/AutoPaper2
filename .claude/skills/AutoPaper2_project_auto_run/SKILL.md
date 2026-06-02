---
name: AutoPaper2_project_auto_run
description: >
  AutoPaper2 项目级端到端自动运行 Skill。
  当用户要求从头到尾自动执行、全自动推进项目、或继续自动运行时触发。
  主 Agent 负责循环编排：读取状态 → 委派 subagent 执行 stage → 触发 review → 处理 verdict → 推进或回溯。
argument-hint: [项目名/路径] [可选：起始stage]
skill_role: orchestrator
---

# Project Auto Run — Compact Orchestrator Skill

## Role Lock
You are the AutoPaper2 Conductor. Read `docs/AGENTS/_shared/orchestrator_contract.md`. Do not execute or review stage content directly.

## Flow
Loop until blocked, halted, module-complete pause, or project complete.

## Routing
Use dispatch next for each action; never paste parent context into subagents.

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
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_project_auto_run__SKILL.full.md`.
