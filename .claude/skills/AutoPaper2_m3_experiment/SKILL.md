---
name: AutoPaper2_m3_experiment
description: >
  AutoPaper2 Module 3 (Experiment Implementation & Execution) 全流程执行 Skill。
  当用户需要进入实验执行阶段时触发，包括：
  前置检查 (M2 完成状态) → M3S01 Dataset & Environment Review / Setup
  → M3S02 Baseline Result Review → M3S03 Main Experiment Result Review
  → M3S04 Result Validation & Evidence Packaging
  → Gate G3（Method + Evidence Critic）→ Handoff M3→M4。
  仅在用户明确指定进入 M3 或 M2 完成后建议进入 M3 时触发。
argument-hint: [现有项目路径或项目名称]
skill_role: stage
---

# M3 Experiment — Compact Orchestrator Skill

## Role Lock
You are the AutoPaper2 Conductor. Read `docs/AGENTS/_shared/orchestrator_contract.md`. Do not execute or review stage content directly.

## Flow
M3S01 -> review -> M3S02 -> review -> M3S03 -> review -> M3S04 -> G3

## Routing
Experiment Agent: M3S01-M3S03; Analysis Agent: M3S04; Gate: method, evidence.

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
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_m3_experiment__SKILL.full.md`.
