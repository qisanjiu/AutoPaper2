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
Loop until project complete, Gate HALT, spiral limit, explicit user pause, or a real external blocker that cannot be resolved automatically after recorded attempts.

## Routing
Use dispatch next for each action; never paste parent context into subagents.

## Required Loop
1. Locate project: `python scripts/state_manager.py status` or `use` when needed.
2. Enable module auto-advance before the loop: `python scripts/state_manager.py set-auto-advance on`.
3. Generate packet: `python scripts/state_manager.py dispatch next --write` or exact `stage/reviews/gate` command.
4. Pass only compact launch prompt / packet path to the matching subagent.
5. Verify output exists; for reviews parse verdict.
6. PASS -> `state_manager.py advance`; non-PASS -> use Conductor/state_manager backtrack handling, regenerate dispatch for the target stage, and continue automatically.

## Autonomy Policy
- Do not ask at module boundaries. `module_completed` means immediately continue to the next module when auto-run is active.
- Do not ask for ordinary REVISE/BACKTRACK/FIX work. Apply structured backtrack advice and re-dispatch the responsible subagent.
- Backtracking is not limited to hyperparameters. It may target dataset acquisition, baseline lock, implementation, main training, M2 experiment design, or earlier hypothesis/design stages when the evidence points there.
- M3/M4 must keep working until the configured evidence target is reached or a hard blocker occurs. Slow training, long downloads, waiting for checkpoints, or poor first results are not hard blockers.
- Agents should actively download datasets, checkpoints, baseline weights, and official code; train or resume when needed; and use SSH/resource planning when configured.
- Ask the user only for secrets, licenses, paid/quota approvals, unavailable storage/network access, unsafe/destructive actions, spiral limit, or explicit pause/stop instructions.

## Forbidden Writes
`knowledge/M*/`, `drafts/`, `knowledge/reviews/*_review.md`, `artifacts/paper.*` unless a delegated subagent owns the path.

## Recovery
After pause/compaction: run status, then dispatch next. Do not reconstruct task context from memory.

## Full Historical Prompt
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_project_auto_run__SKILL.full.md`.
