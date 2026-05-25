# M5S04 Methodology

> Stage: M5S04 | Agent: Writing | Module: M5 Writing

---

## 1. 问题定义（Problem Formulation）

- 与 M2S03 的符号定义保持一致
- 输入/输出空间的数学定义
- 优化目标的数学表达

---

## 2. 方法概述

- 一句话概括方法核心思想
- 方法架构图（引用 Fig 1，由 Plotting Plan 定义）
- 关键组件列表及其职责

### 2.1 架构 / 机制图清单

| 图 | 类型 | Backend | 输出路径 | 作用 | 是否已审 |
|----|------|---------|---------|------|---------|
| Fig 1 | 架构图 | gpt-image-2 / Draw.io | generated-images/... | 方法总览 | ☐ |
| Fig 2 | 机制图（如有） | gpt-image-2 / Draw.io | generated-images/... | 解释模块交互 | ☐ |

- 架构图/机制图必须忠实于方法描述，不能新增不存在的组件
- 若使用 `drawio`，必须保留可编辑源文件；若使用 `gpt-image-2`，必须保留 prompt 和输出路径
- 默认使用 `image2` / `gpt-image-2`；Draw.io 仅在明确需要可编辑流程图源时作为替代
- 方法/框架图必须记录 `paper-framework-figure-studio-pro` style reference，并说明只迁移版式语法和层级，不复制具体图形创意
- image2 prompt 必须包含图目的、组件列表、箭头关系、版式、视觉风格和禁止项

**Figure Prompt Record**

```text
Figure ID:
Venue:
Style preset:
Style profile source:
Framework/method style reference: paper-framework-figure-studio-pro
Backend:
Model:
Allowed labels/components:
Forbidden invented labels/components:
Prompt:
Output path:
Caption draft:
Consistency check against M2S03/M2S04:
```

- 架构图/机制图不能只画“空白方框 + 直线箭头”；需要按 M5S02 的 Figure Style Profile 提供受控颜色、分组和层级。
- 图内所有标签必须来自 M2S03/M2S04 或本 stage 明确列出的 Allowed labels/components，不能让 image2 自行补充不存在的模块。

---

## 3. 核心组件详细描述

### 3.1 组件 A

- **功能**: ...
- **数学表达**: ...
- **与现有工作的区别**: ...

### 3.2 组件 B

- **功能**: ...
- **数学表达**: ...

### 3.3 组件 C（如有）

...

---

## 4. 完整算法流程

```
算法 1: [方法名]
输入: ...
输出: ...
1: ...
2: ...
3: ...
...
```

- 算法步骤必须与 M2S04 的伪代码一致
- 复杂度分析（时间/空间）

---

## 5. 理论分析（如有）

- 收敛性 / 最优性 / 近似比等
- 定理陈述 + 证明概述（完整证明放 Appendix）
- 与 M2S04 的理论部分保持一致

---

## 写作检查清单

- [ ] 符号定义与 M2S03 完全一致
- [ ] 包含算法框或伪代码
- [ ] 复杂度分析已给出
- [ ] 理论分析与 M2S04 一致，无矛盾
- [ ] 每个组件的输入/输出规格明确
- [ ] 方法概述段落可被独立理解
- [ ] 无口语化表达
- [ ] 已遵循 M5S02 Style & Layout Profile 的方法呈现与排版约束
- [ ] 架构图 / 机制图已按 backend 记录并与正文一致
- [ ] 所有公式有编号，可引用
