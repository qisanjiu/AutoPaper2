---
name: AutoPaper2_m6_submission_review
description: >
  AutoPaper2 Module 6 (Submission Review & Revision Loop) 全流程执行 Skill。
  当用户需要进入最终审稿与回溯修正阶段时触发，包括：
  前置检查 (M5 完成状态) → M6S01 投稿前审计与包组装
  → M6S01 内部严审（多 reviewer，≥8/10 且 High 未解决项为 0）
  → M6S02 外部审稿提交 (paperreview.ai)
  → M6S03 审稿意见接收与解析 (IMAP 邮箱监控)
  → M6S04 回溯规划与 Rebuttal 策略
  → M6S05 修订执行 (跨模块回溯)
  → M6S06 修订验证与完成判定
  → Gate G6（Logic + Evidence + Writing + Resolution Critic）
  → Handoff M6→归档/投稿。
  仅在用户明确指定进入 M6 或 M5 完成后建议进入 M6 时触发。
argument-hint: [现有项目路径或项目名称]
skill_role: stage
---

# M6 Submission/Review — Compact Orchestrator Skill

## Role Lock
You are the AutoPaper2 Conductor. Read `docs/AGENTS/_shared/orchestrator_contract.md`. Do not execute or review stage content directly.

## Flow
M6S01 internal review -> M6S02 -> M6S03 -> M6S04 -> routed M6S05 -> M6S06 -> G6

## Routing
Submission Agent: M6S01-M6S02; Rebuttal Agent: M6S03/M6S04/M6S06; Revision Agent and routed subagents for M6S05; Gate: logic, evidence, writing, resolution.

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
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_m6_submission_review__SKILL.full.md`.
