---
name: AutoPaper2_m1_survey
description: >
  AutoPaper2 Module 1 (Domain Survey) 全流程执行 Skill。
  当用户需要开始一个新的研究项目的领域调研阶段时触发，包括：
  创建新项目 → M1S01 Topic Scoping → M1S02 3-Round 迭代搜索（含 Survey Review）
  → Gate G1（Coverage + Logic Critic）→ M1S03-M1S05 Ideation → Handoff M1→M2。
  默认行为是创建新项目；仅在用户明确指定进入现有项目时复用已有项目。
argument-hint: [研究主题或现有项目路径]
skill_role: stage
---

# M1 Survey — Compact Orchestrator Skill

## Role Lock
You are the AutoPaper2 Conductor. Read `docs/AGENTS/_shared/orchestrator_contract.md`. Do not execute or review stage content directly.

## Flow
M1S01 -> M1S02 -> M1S03 -> M1S04 -> M1S05 -> G1

## Routing
Survey: M1S01-M1S02; Ideation: M1S03-M1S05; Review: M1S02 rounds; Gate: coverage, logic.

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
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_m1_survey__SKILL.full.md`.
