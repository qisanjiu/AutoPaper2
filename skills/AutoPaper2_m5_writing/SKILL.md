---
name: AutoPaper2_m5_writing
description: >
  AutoPaper2 Module 5 (Writing & Finalization) 全流程执行 Skill。
  当用户需要进入论文写作与定稿阶段时触发，包括：
  前置检查 (M4 完成状态) → M5S01 Pre-Write Audit → M5S02 Paper Outline
  → M5S04 Methodology → M5S05 Experiments & Results → M5S06 Analysis & Discussion
  → M5S03 Introduction & Related Work → M5S07 Abstract & Conclusion
  → M5S08 Full Draft Assembly & Compilation → M5S09 Full-Polish & Narrative Coherence Review
  → Gate G5（Logic + Writing + Evidence + Novelty + Ethics Critic）
  → 可选 Peer Review Simulation → Handoff M5→投稿/归档。
  M5S01 还会筛选高水平相近论文作为风格参照；M5S02 负责蒸馏出 Style & Layout Profile 和 Figure Style Profile。
  每个 Stage 完成后必须先通过对应 stage reviewer，再推进到下一个 Stage。
  仅在用户明确指定进入 M5 或 M4 完成后建议进入 M5 时触发。
argument-hint: [现有项目路径或项目名称]
skill_role: stage
---

# M5 Writing — Compact Orchestrator Skill

## Role Lock
You are the AutoPaper2 Conductor. Read `docs/AGENTS/_shared/orchestrator_contract.md`. Do not execute or review stage content directly.

## Flow
M5S01 -> M5S02 -> M5S04 -> M5S05 -> M5S06 -> M5S03 -> M5S07 -> M5S08 -> M5S09 -> G5

## Routing
Analysis Agent: M5S01; Writing Agent: M5S02-M5S09; Build verifier in M5S08/M5S09; Gate: logic, writing, evidence, novelty, ethics.

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
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_m5_writing__SKILL.full.md`.
