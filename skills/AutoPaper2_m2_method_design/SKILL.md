---
name: AutoPaper2_m2_method_design
description: >
  AutoPaper2 Module 2 (Method Design) 全流程执行 Skill。
  当用户需要进入方法设计阶段时触发，包括：
  前置检查 (M1 完成状态) → M2S01 Cross-Domain Search → M2S02 Migration Analysis
  → M2S03 Method Architecture Design → M2S04 Algorithm & Theory Design
  → M2S05 Experiment Setup / Metric Protocol / M2→M3 Handoff
  → Gate G2（Logic + Method + Novelty Critic）。
  仅在用户明确指定进入 M2 或 M1 完成后建议进入 M2 时触发。
argument-hint: [现有项目路径或项目名称]
skill_role: stage
---

# M2 Method Design — Compact Orchestrator Skill

## Role Lock
You are the AutoPaper2 Conductor. Read `docs/AGENTS/_shared/orchestrator_contract.md`. Do not execute or review stage content directly.

## Flow
M2S01 -> M2S02 -> M2S03 -> M2S04 -> M2S05 -> G2

## Routing
Method Agent for all M2 stages; stage reviewers after each stage; Gate: logic, method, novelty.

## Required Loop
1. Locate project: `python scripts/state_manager.py status` or `use` when needed.
2. Generate packet: `python scripts/state_manager.py dispatch next --write` or exact `stage/reviews/gate` command.
3. Pass only compact launch prompt / packet path to the matching subagent.
4. Verify output exists; for reviews parse verdict.
5. PASS -> `state_manager.py advance`; non-PASS -> structured backtrack and regenerate dispatch.

## M2 Metric Protocol Policy
- M2S05 must lock metric correctness before M3 by writing `knowledge/M2/M2S05_metric_protocol.yaml`.
- Each metric protocol must bind metric to dataset, scenario/task, split, definition, calculation, direction, value range, normal reference range, protocol source, and a sanity-check case.
- M2S05 must not write a full M3/M4 experiment plan. Detailed main experiment design is M3S01; ablation/robustness/mechanism design is M4-only.
- M3S01 must reference `metric_protocol_id` for the main experiment. If the correct metric for a dataset/scenario is unclear, revise M2S05 instead of deferring the issue to M3.

## Forbidden Writes
`knowledge/M*/`, `drafts/`, `knowledge/reviews/*_review.md`, `artifacts/paper.*` unless a delegated subagent owns the path.

## Recovery
After pause/compaction: run status, then dispatch next. Do not reconstruct task context from memory.

## Full Historical Prompt
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_m2_method_design__SKILL.full.md`.
