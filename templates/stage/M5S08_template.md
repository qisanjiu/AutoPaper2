# M5S08 Full Draft Assembly & Compilation

> Stage: M5S08 | Agent: Writing + Build Verifier | Module: M5 Writing

---

## 1. 整合清单

### 1.1 Section 合并状态

| Section | 源文件 | 已合并 | 状态 |
|---------|--------|--------|------|
| Abstract | M5S07 | ☐ | |
| Introduction | M5S03 | ☐ | |
| Related Work | M5S03 | ☐ | |
| Methodology | M5S04 | ☐ | |
| Experiments | M5S05 | ☐ | |
| Analysis & Discussion | M5S06 | ☐ | |
| Conclusion | M5S07 | ☐ | |

### 1.2 Style/Layout Compliance

- [ ] M5S02 Style & Layout Profile 已应用到全文
- [ ] 版式与图表密度与目标 venue 一致
- [ ] 无对参照论文原文的直接复用

### 1.3 图表插入状态

| 图表 | 源文件 | LaTeX 标签 | 正文引用 | 已插入 |
|------|--------|-----------|---------|--------|
| Fig 1 | ... | \label{fig:arch} | Figure~\ref{fig:arch} | ☐ |
| Tab 1 | ... | \label{tab:main} | Table~\ref{tab:main} | ☐ |
| ... | ... | ... | ... | ... |

### 1.4 参考文献状态

- [ ] `refs.bib` 已生成/更新
- [ ] 所有 `\cite{}` 有对应条目
- [ ] 无未使用条目（或已清理）

### 1.5 Figure Compliance

- [ ] 架构图 / 机制图的 backend、prompt、输出路径已记录
- [ ] 架构图 / 机制图已应用 M5S02 Figure Style Profile 或 venue preset
- [ ] 图像风格不过度简洁、单色、死板，且不模仿参照论文的独特图形设计
- [ ] 实验结果图的脚本与数据源已记录
- [ ] 没有把 image2 图用作结果图
- [ ] 所有图像资产在 `generated-images/` 或 `experiments/figures/` 中可追溯

---

## 2. LaTeX 编译报告

### 编译命令

```bash
cd artifacts/
pdflatex paper.tex
bibtex paper
pdflatex paper.tex
pdflatex paper.tex
```

### 编译结果

- **编译状态**: ☐ 成功 ☐ 失败
- **PDF 页数**: N / 限制 M
- **Fatal Errors**: N 个
- **Warnings**: N 个
- **Overfull/Underfull Hboxes**: N 个
- **未定义引用**: N 个
- **未定义 citations**: N 个

### Orphan Cite Gate

- **Total citations in text**: N
- **Matched in refs.bib**: N
- **Orphan cites**: [列表，如有]
- **Unused bib entries**: [列表，如有]

### Anti-Leakage Check

- **扫描结果**: ☐ 通过 ☐ 发现泄露
- **泄露项**: [如有，列出]

### LaTeX Sanity Check

- [ ] 无 fatal error
- [ ] 无未定义 \ref / \cite
- [ ] 页数在限制内
- [ ] 图表在可见页面内（不跨页太远）

---

## 3. 最终产出

- [ ] `artifacts/paper.tex` — 完整 LaTeX 源文件
- [ ] `artifacts/paper.pdf` — 编译后的 PDF
- [ ] `artifacts/refs.bib` — 参考文献数据库
- [ ] `knowledge/M5/M5S08_final_compilation.md` — 本编译报告
- [ ] `knowledge/handoff_M5_completion.md` — M5→M6 完成交接

### 3.1 Deterministic Gate Requirements

M5S08 通过前必须满足：

- `paper.tex` 不是占位文件，包含 abstract、Introduction、Related Work、Method、Experiments/Results、Analysis/Discussion、Conclusion、bibliography
- `paper.tex` 不包含 `TODO`, `TBD`, `[INSERT ...]`, `placeholder`, `待补充`, `占位` 等占位文本
- 所有 `\includegraphics{}` 路径在 `artifacts/` 下真实存在
- 至少有一个 figure 引用、一个 table 引用，表格使用 `booktabs`
- `refs.bib` 非空，所有 `\cite{}` key 都能在 `refs.bib` 中找到
- `paper.pdf` 存在且是 PDF 文件
- 编译报告必须记录 `pdflatex` 与 `bibtex`/`biber` 命令、Final verdict: PASS、Fatal Errors: 0、Undefined references: 0、Undefined citations: 0、Orphan cites: 0、Anti-Leakage: PASS、页数、style/layout 和 figure compliance
- `handoff_M5_completion.md` 必须说明 M6 submission readiness、paper artifacts、compilation status

---

## 4. 投稿包生成（如适用）

- [ ] Source ZIP（paper.tex + refs.bib + 图表 + sty/cls 文件）
- [ ] Supplementary ZIP（附录、额外实验、代码说明）
- [ ] 检查 venue 特殊要求（如 NeurIPS checklist、reproducibility checklist）
