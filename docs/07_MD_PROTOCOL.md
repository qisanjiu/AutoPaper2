# AutoPaper2 Markdown Output Protocol (07_MD_PROTOCOL)

> **版本**: 1.0
> **适用范围**: 所有 Agent 产出的 Markdown 文件（`knowledge/`、`drafts/`、`reviews/` 下的 `.md` 文件）
> **目的**: 统一 Markdown 结构、命名、引用与一致性规范，确保下游 Agent 和 Critic 能可靠解析。

---

## 1. 文件结构与标题层级

### 1.1 必要章节（每个 Stage 产出必须包含）

```markdown
# {Stage ID} — {中文/英文标题}

> **Stage**: {stage_id}
> **Agent**: {agent_role}
> **Version**: {timestamp}
> **Status**: draft | review | final

## 1. 执行摘要（Executive Summary）
## 2. 正文内容（按 Stage 要求展开）
## 3. 关键决策记录（Decision Log）
## 4. 下游输入说明（Downstream Inputs）
## 5. 局限性 / 待办（Limitations & TODO）
```

- 一级标题 `#` 只能有一个，即文档主标题。
- 二级标题 `##` 用于主要章节，必须按顺序编号（`## 1.`, `## 2.` …）。
- 三级标题 `###` 用于子章节，不强制编号。
- 禁止跳级（如 `##` 后直接 `####`）。

### 1.2 特殊章节规范

| Stage 类型 | 必须包含的特殊章节 |
|-----------|------------------|
| Survey (M1S01-M1S02) | Source Log 引用对照表、Gap 列表（含类型标注） |
| Ideation (M1S03-M1S05) | Pre-Idea Draft 摘要、反对意见与证伪路径 |
| Method (M2S01-M2S05) | 问题形式化（符号+目标函数）、伪代码/算法框、复杂度分析 |
| Experiment (M3S02-M3S04) | 环境配置锁定、Run Contract、Baseline 公平性声明 |
| Analysis (M3S05/M4S01-M4S04/M5S01) | Claim Ledger、Evidence Ladder、统计显著性 |
| Writing (M5S02-M5S08/M5S09) | Style & Layout Profile 引用、Figure/Table 清单、Anti-Leakage 自检、Full-Polish 叙事连贯性审阅 |
| Submission (M6S01-M6S02) | Venue 合规性检查表、投稿包清单 |
| Rebuttal (M6S03-M6S06) | Review Matrix 引用、Action Plan、逐条解决度验证 |

---

## 2. Output Versioning

### 2.1 时间戳版本
首次写入文件时，文件名必须包含 ISO 时间戳：
```
knowledge/M2/M2S03_method_architecture_2026-01-15T143022.md
```

### 2.2 固定名复制
时间戳文件确认稳定后，复制到固定名（不带时间戳）：
```
knowledge/M2/M2S03_method_architecture.md
```
- 固定名文件是下游 Agent 读取的标准路径。
- 时间戳文件保留作为历史审计记录。

### 2.3 文件头元数据
每个 Markdown 文件头必须包含：
```markdown
> **Stage**: M2S03
> **Agent**: method
> **Version**: 2026-01-15T14:30:22
> **Status**: draft
> **Rebuild Mode**: full_regenerate | incremental_replay  (仅回溯后重新执行时填写)
```

---

## 3. Source Log ↔ Markdown 正文一致性规则

### 3.1 引用格式
- **Stage 文档内引用文献**：使用 `[@source_id]` 或 `Source: [@id]`。
- **LaTeX 论文内引用**：使用 `\cite{key}`，key 必须与 `refs.bib` 中的 BibTeX key 一致。
- **禁止**使用未经 Source Log 登记的 "幽灵文献"。

### 3.2 一致性检查清单
- [ ] Markdown 中声明的 "共保留 N 篇核心文献" 与 Source Log 条目数一致。
- [ ] 每个 `[@id]` 都存在于 Source Log 中。
- [ ] Source Log 中的每篇文献至少有一个 `[@id]` 在 Markdown 中被引用（未被引用的需说明原因，如 "备选/待审"）。
- [ ] 数值、实验结果、超参数必须与原始数据文件（`results.tsv`、`analysis_results.tsv`）一致，不得四舍五入导致矛盾。

---

## 4. 术语表与符号统一

### 4.1 术语表（Terminology Table）
在涉及符号定义的 Stage（M2S03、M5S04 等）中，必须提供术语表：

```markdown
| 符号 | 含义 | 首次出现 |
|------|------|---------|
| $X$ | 输入特征矩阵 | M2S03 |
| $y$ | 目标标签向量 | M2S03 |
| $\mathcal{L}$ | 损失函数 | M2S04 |
```

### 4.2 禁止行为
- 同一符号在不同 Stage 中表示不同含义（除非显式重定义）。
- 论文正文中出现术语表以外的缩写而不给出全称。

---

## 5. 文件命名与落盘规范

### 5.1 目录结构
```
{project}/
├── knowledge/
│   ├── M1/
│   ├── M2/
│   ├── M3/
│   ├── M4/
│   ├── M5/
│   ├── M6/
│   └── reviews/
├── drafts/
│   └── {stage_id}/
│       └── {stage_id}_draft.md
├── experiments/
│   ├── results.tsv
│   ├── analysis_results.tsv
│   ├── artifacts/
│   │   ├── main_experiment/
│   │   └── analysis_experiment/
│   ├── src/
│   ├── configs/
│   └── runs/
└── artifacts/
    ├── paper.tex
    ├── paper.pdf
    └── refs.bib
```

### 5.2 命名规则
- **Stage 产出**：`knowledge/{模块}/{stage_id}_{snake_case_title}.md`
- **Review 文件**：`knowledge/reviews/{stage_or_gate_id}_{reviewer_name}_review.md`
- **Handoff 文件**：`knowledge/handoff_{from}_{to}.md`
- **Gate Aggregate**：`knowledge/reviews/{gate_id}_aggregate.md`

---

## 6. Context Recovery 文件读取顺序

当 Agent 上下文被压缩或 session 中断时，按以下顺序恢复：

1. `docs/AGENTS/{role}/AGENT.md` — 当前 Agent 的身份与职责
2. `docs/07_MD_PROTOCOL.md` — 本文件（输出规范）
3. `state/pipeline_state.yaml` — 当前 stage / status / stale_stages
4. `state/decision_log.md` — 最近决策
5. `state/spiral_log.md` — 螺旋历史
6. `knowledge/handoff_{prev}_{curr}.md` — 上游交接文档
7. 当前 stage 的上一次产出文件（时间戳版本或固定名）
8. 最近的 review / gate 产出（如当前处于回溯后重新执行状态）

**禁止**在恢复上下文时跳过 Source Log 或数据文件直接假设数值。

---

## 7. Review / Gate 产出格式

### 7.1 Verdict 必须显式
所有 review 文件必须在末尾包含独立的 verdict 行：
```markdown
## Verdict

PASS
```
或
```markdown
**Verdict**: REVISE
```

允许的 verdict 值（必须大写）：`PASS`, `REVISE`, `REWORK`, `BACKTRACK`, `FIX`, `HALT`。

### 7.2 非 PASS 时必须包含 Repair Advice
当 verdict 不为 PASS 时，必须包含以下字段：
```markdown
- **target_stage**: M2S03
- **blocking_reason**: 架构设计与迁移分析不一致
- **required_fix**: 重新设计注意力模块的输入输出规格
- **success_criteria**: 新架构能通过 m2_design_review 且与 M2S02 的映射表一致
- **evidence_paths**: knowledge/M2/M2S02_method_inspiration.md
- **rebuild_mode**: full_regenerate
- **rerun_scope**: 重新执行 M2S03 及下游 M2S04-M2S05/M3S01
- **handoff_updates**: 更新 handoff_M2_M3 中的架构摘要
```

---

## 8. 跨模块引用规范

- 引用上游产出时，必须给出**文件路径**，不能只给 stage ID。
- 示例：✅ "参见 `knowledge/M2/M2S03_method_architecture.md` 中的公式 (3)"
- 示例：❌ "参见 M2S03"

---

## 9. 语言规范

- **Stage 文档**（`knowledge/`、`drafts/`、`reviews/`）：默认中文，用户可覆盖。
- **论文正文**（`artifacts/paper.tex`）：按 venue 要求。
- **代码注释**：英文。
- **配置/日志**：英文。
