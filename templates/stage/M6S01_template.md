# M6S01 — 投稿前审计与包组装

## 审计范围
- [ ] M1-M5 产出完整性
- [ ] Venue 合规性（页数、格式、匿名性）
- [ ] 投稿包组装
- [ ] 邮件配置检查

## 完整性审计表格

| 模块 | 文件路径 | 状态 | 备注 |
|------|----------|------|------|
| M1 | knowledge/M1/M1S02_literature_deepdive.md | ⬜ | |
| M2 | knowledge/M2/M2S03_method_architecture.md | ⬜ | |
| M2 | knowledge/M2/M2S04_algorithm_theory.md | ⬜ | |
| M3 | knowledge/M3/M3S03_main_experiment.md | ⬜ | |
| M3 | knowledge/M3/M3S04_result_validation.md | ⬜ | |
| M4 | knowledge/M4/M4S04_analysis_results.md | ⬜ | |
| M5 | artifacts/paper.pdf | ⬜ | |
| M5 | artifacts/paper.tex | ⬜ | |
| M5 | artifacts/refs.bib | ⬜ | |
| Handoff | knowledge/handoff_M5_completion.md | ⬜ | |

## Venue 合规检查

- **目标 Venue**: [从 pipeline_state 读取]
- **页数限制**: [页数] / [限制]
- **当前页数**: ⬜ 合规 / ❌ 超限
- **格式检查**: ⬜ PASS / ❌ FAIL
- **匿名性检查**: ⬜ PASS / ❌ FAIL
- **Orphan Cite 数量**: [N]

## 邮件配置

- `config/email_config.yaml`: ⬜ 存在 / ❌ 缺失
- 如果缺失，需要提示用户配置 QQ 邮箱 IMAP 授权码

## 内部审查门槛

- **内部审查文件**: knowledge/reviews/M6S01_internal_peer_review.md
- **内部审查状态**: WAITING_INTERNAL_REVIEW / INTERNAL_PASS / INTERNAL_REVISE
- **要求评分**: Internal Review Score ≥ 8/10
- **High 未解决项**: 必须为 0
- **若未达标**: 不得进入 M6S02；按内部审查中的 `target_stage`、`required_fix`、`rebuild_mode` 回溯

## 审计结论

- **总体状态**: READY / NOT_READY
- **内部审查门槛**: WAITING_INTERNAL_REVIEW / INTERNAL_PASS / INTERNAL_REVISE
- **Blockers**: [列表，如有]
- **Warnings**: [列表，如有]
- **下一步**: [进入 M6S02 或修复 Blockers]
