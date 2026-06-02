---
name: AutoPaper2_env_probe
description: >
  AutoPaper2 环境探测与基础配置 Skill。
  当项目部署到新环境、需要自动检测当前机器的 GPU/Python/CUDA/框架版本，
  并自动填充 config/execution_env.yaml 时触发。
  也用于项目迁移到新机器后重新探测环境。
argument-hint: [项目路径（可选）]
skill_role: utility
---

# Environment Probe — Compact Orchestrator Skill

## Role Lock
You are the AutoPaper2 Conductor. Read `docs/AGENTS/_shared/orchestrator_contract.md`. Do not execute or review stage content directly.

## Flow
Run `scripts/env_probe.py --project <project>` or output report; update execution_env only as requested.

## Routing
Do not write research outputs.

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
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_env_probe__SKILL.full.md`.
