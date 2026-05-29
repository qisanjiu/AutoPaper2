# M5S09 Full-Polish & Narrative Coherence Review

> Stage: M5S09 | Agent: Writing | Module: M5 Writing

---

## 0. 输入边界（LaTeX/PDF Final Polish）

M5S09 在 M5S08 之后执行。此阶段必须读取 M5S08 生成的完整稿：
- `artifacts/paper.tex` — **主输入与唯一可编辑真源**
- `artifacts/paper.pdf` — **渲染/版面检查输入**，只用于检查排版、分页、图表位置和可读性，不直接编辑 PDF
- `artifacts/refs.bib` — 引用一致性检查
- `knowledge/M5/M5S08_final_compilation.md` — 编译报告与已知 LaTeX 问题

必要时可回读 M5S03-M5S07 的章节源稿用于定位问题来源：
- `knowledge/M5/M5S03_introduction_relatedwork.md`
- `knowledge/M5/M5S04_methodology.md`
- `knowledge/M5/M5S05_experiments_results.md`
- `knowledge/M5/M5S06_analysis_discussion.md`
- `knowledge/M5/M5S07_abstract_conclusion.md`

所有文字、结构、引用和图表位置修订必须落到 `artifacts/paper.tex`。修订后必须重新编译并更新 `artifacts/paper.pdf`，同时输出 `knowledge/M5/M5S09_full_polish.md` 记录修改清单、PDF 检查结果和复编译状态，并更新 `knowledge/handoff_M5_completion.md` 作为最终 M5→M6 交接。

---

## 1. 全文叙事连贯性审阅（Narrative Coherence Audit）

以**读者视角**通读 `artifacts/paper.tex` 与渲染后的 `artifacts/paper.pdf`，验证论文的叙事弧线是否完整、一致、有说服力。

### 1.1 Intro-Method 承诺兑现链

| Intro 中的承诺 | Method 中的实现 | 是否兑现 | 备注 |
|---------------|----------------|---------|------|
| ... | ... | 是/否 | |

- Introduction 中提出的每个核心贡献/技术洞察，必须在 Method 中找到对应实现
- Method 中描述的每个关键组件，必须在 Intro 中被预告或动机化

### 1.2 Method-Experiments 验证链

| Method 组件/假设 | Experiments 中的验证方式 | 结果 | 是否对应 |
|-----------------|------------------------|------|---------|
| ... | ... | ... | 是/否 |

- 每个方法设计决策（如损失函数、网络结构）是否被实验验证？
- 实验中报告的每个主结果是否能在 Method 中找到来源？

### 1.3 Experiments-Analysis 解读链

| 实验结果（M5S05） | Analysis 中的解读（M5S06） | 是否一一对应 | 深度评价 |
|------------------|--------------------------|------------|---------|
| ... | ... | 是/否 | |

- **核心要求**：M5S06 中的每条分析、每个消融、每个机制解释，必须直接对应 M5S05 中的一个具体实验结果
- 禁止在 Analysis 中讨论未在 Experiments 中呈现的结果
- 禁止在 Experiments 中呈现未在 Analysis 中解释的重要现象

### 1.4 全文术语一致性最终校验

| 术语 | Intro | Method | Exp | Analysis | Conclusion | 是否一致 |
|------|-------|--------|-----|----------|------------|---------|
| ... | ... | ... | ... | ... | ... | 是/否 |

### 1.5 数值一致性最终校验

| 数值 | Abstract | Intro | Exp | Analysis | Conclusion | 是否一致 |
|------|----------|-------|-----|----------|------------|---------|
| ... | ... | ... | ... | ... | ... | 是/否 |

---

## 2. 语言精炼（Language Refinement）

### 2.1 消除重复表述

- [ ] Abstract 与 Conclusion 无整句重复（可意思一致，但措辞不同）
- [ ] Intro 与 Abstract 无过度重复
- [ ] Method 中的组件描述与 Analysis 中的回顾描述不机械重复
- [ ] 同一概念在全文各处使用不同表达（避免单调）

### 2.2 句式多样性

- [ ] 段落开头句式不重复（避免连续使用 "We propose...", "The results show..."）
- [ ] 长短句交替，避免过长从句堆叠
- [ ] 适当使用强调结构（如倒装、分词短语开头）

### 2.3 段落衔接与过渡

- [ ] 各 section 末尾有向下一节的自然过渡句
- [ ] 各 section 开头有承上启下的回顾句
- [ ] 段落之间使用逻辑连接词（However, Furthermore, Consequently, In contrast 等）
- [ ] 无突兀跳跃（如从方法细节突然跳到实验结果，缺少 "To validate..." 等过渡）

### 2.4 语态优化

- [ ] Method 中技术描述以被动语态为主（"is formulated as", "is optimized via"）
- [ ] 贡献声明以主动语态为主（"We propose", "We demonstrate"）
- [ ] 避免 "We use ... to ..." 的连续单调句式

### 2.5 冗余词删除

- [ ] 删除无意义的填充词（"It is worth noting that", "It should be mentioned that"）
- [ ] 删除重复修饰（如 "significantly improves the performance significantly"）
- [ ] 精简 "in order to" → "to", "due to the fact that" → "because"
- [ ] 检查 "very", "quite", "rather", "fairly" 等弱化副词是否必要

---

## 3. 跨章节节奏与篇幅平衡

| Section | 当前页数 | 预算页数 | 偏差 | 调整建议 |
|---------|---------|---------|------|---------|
| Abstract | ... | 0.3 | ... | ... |
| Introduction & Related Work | ... | 1.5-2.5 | ... | ... |
| Methodology | ... | 2-3 | ... | ... |
| Experiments, Results and Analysis | ... | 3-4 | ... | ... |
| Conclusion | ... | 0.3 | ... | ... |

- 若某 section 超出预算，优先压缩冗余描述而非删除关键内容
- 确保 Method 和 Experiments 的篇幅比例合理（通常 Method:Exp ≈ 1:1 到 2:3）

---

## 4. 写作检查清单

- [ ] Narrative Coherence Audit 四项链条全部检查通过
- [ ] 全文术语一致性检查通过
- [ ] 全文数值一致性检查通过
- [ ] 无重复表述
- [ ] 句式有变化，阅读节奏良好
- [ ] 段落衔接自然，无突兀跳跃
- [ ] 语态使用符合学术惯例
- [ ] 冗余词已清理
- [ ] 篇幅与 M5S02 预算基本一致
- [ ] 已遵循 M5S02 Style & Layout Profile 的语气与长度约束
- [ ] 无口语化表达
- [ ] Anti-Leakage Prompt 已应用
