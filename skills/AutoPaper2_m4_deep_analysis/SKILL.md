---
name: AutoPaper2_m4_deep_analysis
description: >
  AutoPaper2 Module 4 (Deep Analysis) 全流程执行 Skill。
  当用户需要进入深度分析阶段时触发，包括：
  前置检查 (M3 完成状态) → M4S01 Post-Experiment Audit & Findings Consolidation
  → M4S02 Deep Analysis Experiment Design → M4S03 Deep Analysis Experiment Execution
  → M4S04 Analysis Results Integration & Evidence Packaging
  → Gate G4（Logic + Evidence + Novelty Critic）→ Handoff M4→M5。
  仅在用户明确指定进入 M4 或 M3 完成后建议进入 M4 时触发。
argument-hint: [现有项目路径或项目名称]
skill_role: stage
---

# M4 Deep Analysis — Compact Orchestrator Skill

## Role Lock
You are the AutoPaper2 Conductor. Read `docs/AGENTS/_shared/orchestrator_contract.md`. Do not execute or review stage content directly.

## Flow
M4S01 -> review -> M4S02 -> review -> M4S03 -> review -> M4S04 -> G4

## Routing
Analysis Agent: M4S01/M4S02/M4S04; Experiment Agent: M4S03; Gate: logic, evidence, novelty.

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
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_m4_deep_analysis__SKILL.full.md`.
