# M5S03 Introduction & Related Work

> Stage: M5S03 | Agent: Writing | Module: M5 Writing

---

## 写作顺序说明

本 Stage 在 Methodology（M5S04）、Experiments（M5S05）和 Analysis（M5S06）**之后**执行。这是学术写作的最佳实践：只有在完整呈现方法、实验和分析后，才能准确提炼出论文的故事线，并写出与后文严格对应的 Introduction。

## 结构灵活性

根据目标 venue 的惯例和 M5S02 的 Section Plan，Introduction 与 Related Work 可采用以下两种组织方式之一：
- **分离式**: Section 1 — Introduction；Section 2 — Related Work（适用于多数 ML/CV 顶会）
- **合并式**: Section 1 — Introduction and Related Work（适用于某些期刊或特定 venue）

无论采用哪种方式，Related Work 必须在 Introduction 的贡献声明之前或之后完整呈现，且必须包含对比与批判。

---

## 1. Introduction

### 1.1 背景（1-2 段）

- 研究领域的重要性
- 核心问题的定义
- 避免过度铺陈，快速进入问题

### 1.2 现有方法的局限（1-2 段）

- 概括现有工作的主要思路
- 明确指出其不足（必须与本文方法形成对比）
- 引用关键文献（使用 \cite{} 占位符）

### 1.3 本文贡献（1 段， bullet 列表）

我们提出 [方法名]，其核心贡献如下：
- **贡献 1**: ...（具体，可验证）
- **贡献 2**: ...
- **贡献 3**: ...

### 1.4 论文组织（1 段）

本文其余部分组织如下：第 2 节回顾相关工作；第 3 节介绍方法；第 4 节描述实验；第 5 节进行分析与讨论；第 6 节总结。

---

## 2. Related Work

### 2.1 主题 A（与本文最相关的方向）

- 关键工作概述
- **对比**: 与 [X] 不同，我们 ...
- **批判**: [Y] 的局限在于 ...，而我们解决了 ...

### 2.2 主题 B（次要相关方向）

- 关键工作概述
- **对比**: ...

### 2.3 主题 C（交叉/弱相关但重要的方向）

- 关键工作概述
- **对比**: ...

---

## 写作检查清单

- [ ] Introduction 总长度 ≤ 1.5 页
- [ ] 第一段直接切入问题，无过多背景铺陈
- [ ] Related Work 有对比和批判，不仅是罗列
- [ ] 所有引用都有对应的 \cite{} 占位符
- [ ] 贡献声明具体、可验证、不超过 3 条
- [ ] 论文组织段落简洁
- [ ] 无口语化表达（参照 Writing Agent 风格指南）
- [ ] 已遵循 M5S02 Style & Layout Profile，且未复制参照论文原文
- [ ] 如包含概念示意图，已记录图像来源、backend 和 caption，且图意与正文一致
- [ ] Anti-Leakage Prompt 已应用（无作者信息泄露）
