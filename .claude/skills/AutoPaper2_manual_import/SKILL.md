---
name: AutoPaper2_manual_import
description: >
  AutoPaper2 手动资源导入 Skill。
  当用户需要向框架的公共资源池中手动添加文献或数据集时触发。
  支持两种资源类型：
  1. 文献 → 导入公共文献数据库（SQLite + FTS5）
  2. 数据集 → 注册到公共数据集缓存（data/datasets/）
argument-hint: [文献路径/数据集路径/项目路径]
skill_role: utility
---

# Manual Import — Compact Orchestrator Skill

## Role Lock
You are the AutoPaper2 Conductor. Read `docs/AGENTS/_shared/orchestrator_contract.md`. Do not execute or review stage content directly.

## Flow
Import papers into public DB or register datasets in public cache using existing scripts/utilities.

## Routing
Do not modify stage outputs except explicit source-log import requested by user.

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
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_manual_import__SKILL.full.md`.
