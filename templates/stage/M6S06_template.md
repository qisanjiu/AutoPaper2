# M6S06 — 修订验证与完成判定

## Action Plan 验证

| ID | 原始意见 | 修订内容 | 验证结果 | 备注 |
|----|---------|---------|---------|------|
| PR-A1 | ... | ... | ✅/⚠️/❌ | |
| ... | ... | ... | ... | |

> 必须逐条覆盖 `M6S03_review_matrix.md` 和 `M6S04_action_plan.md` 中的所有 `PR-*` ID。High priority item 必须显式 resolved/PASS；任何 unresolved/failed/pending 的 High item 都会阻止 M6 完成。

## 解决度评分

- **High 解决率**: _/100% ([N] / [M])
- **Medium 解决率**: _/100% ([N] / [M])
- **Low 解决率**: _/100% ([N] / [M])
- **综合解决度**: _/100%

## 质量保持度

| 指标 | Gate G5 | 修订后 | 变化 |
|------|---------|--------|------|
| Logic Score | _/10 | _/10 | ±X |
| Evidence Score | _/10 | _/10 | ±X |
| Writing Score | _/10 | _/10 | ±X |
| 页数 | _ | _ | ±X |
| Orphan Cites | _ | _ | ±X |

## 完成判定

- [ ] 综合解决度 ≥ 80%
- [ ] 无 High 优先级未解决项
- [ ] High 解决率为 100%
- [ ] 质量未显著退化（各维度下降 < 2 分）
- [ ] paper.pdf 编译通过

**判定结果**: PASS / NEEDS_MORE_WORK

## 外部审稿证据复核

- [ ] `knowledge/M6/M6S02_submission_log.json` 存在，`status=success`
- [ ] submission log 记录 paperreview.ai platform/url、submitted_at、pdf_path、email、tracking
- [ ] `knowledge/M6/M6S03_review_email.json` 存在，`status=success`
- [ ] review email 保存 subject/from/message_id/date 中至少一项元数据和非空 body
- [ ] `knowledge/M6/M6S03_review_matrix.md` 包含 PR-* 原子意见、original_text、class、severity、route/target
- [ ] 所有 Review Matrix PR-* item 已进入 `M6S04_action_plan.md`
- [ ] 所有 Action Plan PR-* item 已在 `M6S05_revision_execution.md` 中完成或解释阻塞
- [ ] 所有 High PR-* item 在本文件中 resolved/PASS
- 证据复核结论: PASS / FAIL
- 若 FAIL，必须回到 M6S02 或 M6S03，不能结束 M6。

## 可选：再次外部审稿

- [ ] 是否再次提交到 paperreview.ai？
- 理由:

## Handoff

- **knowledge/handoff_M6_completion.md** 已生成
- **最终投稿包目录**: artifacts/submission_package/
- **最终 PDF**: artifacts/submission_package/paper_final.pdf
- **LaTeX 源码包**: artifacts/submission_package/source.zip
- **补充材料包**: artifacts/submission_package/supplementary.zip（如有）
