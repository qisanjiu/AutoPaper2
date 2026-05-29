# M5S02 Paper Outline

> Stage: M5S02 | Agent: Writing | Module: M5 Writing

---

## 1. Venue 配置

- **目标 Venue**: ...
- **页数限制**: ... 页（正文）+ 参考文献 + 附录
- **格式要求**: LaTeX / Word / 其他
- **特殊要求**: 如 NeurIPS checklist、ICML impact statement、ACL limitations 等

---

## 2. Style & Layout Profile

**硬性通过条件**:
- 必须声明 3-5 篇高层次参照论文或给出等价 `Reference paper count: N`，N 必须为 3、4 或 5。
- 只允许迁移结构、段落功能、节奏、图表密度、版式约束等高层信号；必须明确不可迁移内容和 anti-copy 边界。
- Figure Style Profile 必须同时给出 venue preset、颜色/布局语法、视觉丰富度，并区分架构/机制图与实验结果图的 backend。

- **风格参照来源**: ...
- **高层次论文样本数**: ...
- **蒸馏范围**: 结构、段落功能、节奏、图表密度、摘要写法、结论写法、版式约束
- **不可迁移内容**: 具体措辞、独特修辞、专有图形、显著叙事顺序
- **排版偏好**: 单栏/双栏、表格密度、图文比、附录分配、caption 长度
- **section 语气**: ...
- **abstract 语气**: ...
- **related work 语气**: ...
- **figure/table 风格**: ...
- **limitation 书写方式**: ...
- **style compliance rule**: 若与目标 venue 的模板冲突，以 venue 模板为准，风格蒸馏只影响可变写作层

| 参照论文 | 可迁移规律 | 应避免模仿的内容 | 本文应用位置 |
|----------|------------|----------------|------------|
| ... | ... | 原文措辞 / 独特图形 / 不适合本文的章节顺序 | Intro / Method / Experiments |

### 2.1 Figure Style Profile

- **venue preset**: ...
- **framework/method style reference**: paper-framework-figure-studio-pro (https://github.com/c-narcissus/paper-framework-figure-studio-pro)
- **experiment plot style reference**: nature-figure skill（仅用于真实数据图的设计/QA，不用于 image2 生成数值结果）
- **distillation mode**: visual / caption-driven / preset-hybrid
- **视觉信号来源**: 可读图像 / caption / figure placement / section 组织
- **颜色语法**: 主色 ... / 辅色 ... / 强调色 ... / 背景色 ... / 边框色 ...
- **布局语法**: 分栏、分组、面板密度、留白、箭头/连线节奏
- **视觉丰富度**: ...
- **允许的轻量装饰**: 浅色面板、弱阴影、层级标记、callout、图例
- **禁止项**: 过度简洁、单色死板、无层次方框、照片化、3D、强渐变
- **fallback 规则**: 若图像不可读，则以 caption / figure placement + venue preset 生成
- **适用图类型**: 架构图 / 机制图 / 概念图 / 流程图

---

## 3. 标题候选

1. **[首选标题]** — ...（理由）
2. **[备选标题 1]** — ...（理由）
3. **[备选标题 2]** — ...（理由）

---

## 4. 核心信息（读者必须在 5 分钟内获取）

- **一句话概括**: ...
- **核心问题**: ...
- **核心方法**: ...
- **核心结果**: ...（具体数值）
- **核心贡献**: ...

---

## 5. Plotting Plan

| Figure/Table | 内容 | 类型 | 数据/代码来源 | 预计位置 | 尺寸 |
|-------------|------|------|-------------|---------|------|
| Fig 1 | 方法架构图 | 架构图 / TikZ | M2S03 | Method 开头 | 单栏/双栏 |
| Fig 2 | 主实验结果 | 柱状图 / 折线图 | experiments/results.tsv | Experiments | ... |
| Tab 1 | 与 baseline 对比 | 表格 | experiments/results.tsv | Experiments | ... |
| Fig 3 | 消融实验 | 分组柱状图 | experiments/analysis_results.tsv | Analysis | ... |
| ... | ... | ... | ... | ... | ... |

### 5.1 Figure Backend Policy

| Figure Type | Preferred Backend | 允许替代 | 禁止 |
|-------------|--------------------|----------|------|
| 架构图 / 机制图 | `image2` / `gpt-image-2` + paper-framework-figure-studio-pro 风格参考 | Draw.io 仅用于可编辑源 | 结果图式的伪装 / 自行发明组件 |
| 实验结果图 | `nature-figure` 原则 + matplotlib / seaborn / plt | 任何真实绘图代码 | `gpt-image-2` / Draw.io |
| 纯排版图示 | Draw.io | TikZ | 结果数值图像化 |

- 每个图都必须记录 backend、prompt 或脚本、输出路径、与正文的对应关系
- 若图为抽象示意图，必须在标题或说明中明确其示意属性，避免被误读为实证结果

---

## 6. Terminology & Symbol Table

| 术语/符号 | 含义 | 首次出现位置 | 备注 |
|----------|------|------------|------|
| ... | ... | ... | ... |

---

## 7. Section Plan（含页数预算）

| Section | 页数预算 | 关键内容 | 依赖上游文档 |
|---------|---------|---------|------------|
| Abstract | 0.3 | 一句话概括、问题、方法、结果、贡献 | M5S07 |
| 1. Introduction & Related Work | 1.5-2.5 | 背景、动机、贡献声明、论文组织、主题分类、对比批判 | M1S02, M1S03 |
| 2. Methodology | 2-3 | 问题定义、方法概述、核心组件、伪代码 | M2S03, M2S04 |
| 3. Experiments, Results and Analysis/Discussion | 3-4 | 设置、主结果、对比、深入解读、消融、Limitations | M3S03, M3S04, M4S03, M4S04 |
| 4. Conclusion | 0.3 | 总结、未来工作 | — |
| References | — | — | M1S02 + 新增 |
| Appendix（如有）| — | 补充实验、证明、实现细节 | M2S04, M4S03 |

**Section 结构灵活性说明**:
- 根据目标 venue 的惯例，Introduction 与 Related Work 可作为两个独立 section（如 "1. Introduction" 和 "2. Related Work"），或合并为单一 section（如 "1. Introduction and Related Work"）
- Experiments 与 Analysis/Discussion 必须在同一 section 内，Analysis/Discussion 作为该 section 的子节（如 3.3 Analysis and Discussion）
- 上述页数预算为推荐值，最终服从 venue 模板和页数限制

**总页数预算**: N 页

---

## 8. 故事线（Story Spine）

用 3-5 句话概括论文的叙事弧线：

1. **背景与问题**: ...
2. **现有方法的不足**: ...
3. **我们的洞察/方法**: ...
4. **关键结果**: ...
5. **意义**: ...

---

## 9. 评审人可能提出的 Top 3 异议

1. **异议**: ... → **预回应**: ...（将在论文中如何 preempt）
2. **异议**: ... → **预回应**: ...
3. **异议**: ... → **预回应**: ...
