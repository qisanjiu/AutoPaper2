---
name: AutoPaper2_project_backtrack
description: >
  AutoPaper2 项目级回溯与修订 Skill。
  当用户需要回溯到某个 stage、重新执行某个 stage、修订产出、或根据意见回退时触发。
  主 Agent 只做编排；stage 选择、回溯决策、重新执行均由 subagent 完成。
argument-hint: [项目名/路径] [stage或回溯意见]
skill_role: orchestrator
---

# Project Backtrack — Compact Orchestrator Skill

## Role Lock
You are the AutoPaper2 Conductor. Read `docs/AGENTS/_shared/orchestrator_contract.md`. Do not execute or review stage content directly.

## Flow
Convert user/review feedback into structured backtrack advice, update state via Conductor/state_manager, then dispatch target stage.

## Routing
Required repair fields: target_stage, blocking_reason, required_fix, success_criteria, evidence_paths, rebuild_mode, rerun_scope, handoff_updates.

## Root-Cause Routing Rules
- Source truth, venue, modality, task, dataset/scenario/split, or baseline eligibility mismatch -> route to M3S01 or M3S03. Do not send this to M4.
- Metric definition/protocol mismatch, missing primary metric implementation, proxy-only metric, or not-run metric -> route to M2S05/M3S03/M3S02 as appropriate, then rerun M3S04-M3S05.
- Incomplete training, running/queued jobs, missing history/status, checkpoint-only results, or random/E0 weights -> route to M3S04 after baseline/protocol validity is confirmed.
- Noisy-channel leakage signals such as PPL≈1, accuracy≈1, SNR-invariant PPL, clean memory bypass, target/encoder hidden-state bypass, shortcut, or metric leakage -> route to M3S02 for implementation repair or M3S03 for baseline-lock invalidation, and mark M3S04-M3S05 stale.
- Method failure under a clean, comparable, leak-free protocol -> route to the method/design stage that owns the failed assumption, not to M4 polishing.

## Repair Advice Guardrails
- If review `Evidence Checked`/`evidence_paths` only cite Markdown outputs, preserve advice as task-level inspect/verify/repair work; do not expand it into exact code lines, function calls, config values, or shell commands.
- Never propose clean encoder memory/cross-attention, such as `self.decoder(x, memory)`, as the fix for channel leakage unless the advice explicitly says `memory` is channel-transmitted/noised under the same bottleneck.
- Leakage repair must require removing clean target/encoder paths, adding no-bypass tests, moving suspicious rows to `experiments/tables/results_invalid.tsv`, and rerunning downstream M3 stages.
- Do not write "defer to M4", "rough reference only", or "limitation" as the resolution for M3 blockers.
- If the reviewer advice itself has the wrong target stage or wrong fix direction, correct the advice before generating the dispatch packet.

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
For audit only: `docs/AGENTS/_reference/full_prompts/skills/AutoPaper2_project_backtrack__SKILL.full.md`.
