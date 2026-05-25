# M6S03 — 审稿意见接收与解析

## 邮件接收

- **监控邮箱**: [从 `config/email_config.yaml` 读取]
- **发件人过滤**: noreply@paperreview.ai
- **等待结果**: received / timeout / manual
- **原始邮件保存**: knowledge/M6/M6S03_review_email.json

## 解析内容提取

### 总体评分
| 维度 | 分数 | 权重 |
|------|------|------|
| Soundness | _/10 | 0.25 |
| Presentation | _/10 | 0.20 |
| Contribution | _/10 | 0.30 |
| Relevance | _/10 | 0.15 |
| Clarity | _/10 | 0.10 |
| **Overall** | **_/10** | 1.00 |

### Strengths
1. ...

### Weaknesses
1. ...

## Review Matrix（原子化）

### PR-A1
- **original_text**: "..."
- **class**: [editorial/text_only/evidence_gap/experiment_gap/claim_scope/cannot_fully_address]
- **severity**: [High/Medium/Low]
- **target_aspect**: [method/experiment/writing/novelty/related_work]
- **preliminary_route**: [text_revision/evidence_repackaging/supplementary_experiment/claim_downgrade/explicit_limitation]
- **affects_acceptance**: true/false

## 分类汇总

| 分类 | High | Medium | Low | 合计 |
|------|------|--------|-----|------|
| editorial | 0 | 0 | 0 | 0 |
| text_only | 0 | 0 | 0 | 0 |
| evidence_gap | 0 | 0 | 0 | 0 |
| experiment_gap | 0 | 0 | 0 | 0 |
| claim_scope | 0 | 0 | 0 | 0 |
| cannot_fully_address | 0 | 0 | 0 | 0 |
