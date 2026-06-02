---
name: AutoPaper2_project_onboarding
description: >
  AutoPaper2 项目创建后的 Onboarding（入项配置）Skill。
  当项目刚被创建、或项目从其他环境迁移过来时触发。
  负责暂停流程，要求用户确认并补全项目配置（SSH、作者、环境、数据集等），
  用户确认 "已填写" 后才允许继续执行 M1 及后续模块。
argument-hint: [项目路径]
skill_role: orchestrator
---

# Project Onboarding — Compact Orchestrator Skill

## Role Lock
You are the AutoPaper2 Conductor. Read `docs/AGENTS/_shared/orchestrator_contract.md`. Do not execute or review stage content directly.

## Flow
Pause after project creation/migration; run env probe; ask user to complete SSH/author/env/data config before research stages.

## Routing
Allowed writes are config/state onboarding files only; no stage outputs.

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
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_project_onboarding__SKILL.full.md`.
