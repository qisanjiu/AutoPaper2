# M5S05 Experiments & Results

> Stage: M5S05 | Agent: Writing | Module: M5 Writing

---

## 结构说明

本 Stage 的内容最终将与 M5S06（Analysis & Discussion）**合并为同一 section**（如 "4. Experiments, Results and Analysis"）。因此：
- 本节只呈现实验设置和主结果，不做深入解读（解读留给 M5S06）
- 每个实验结果需为 M5S06 预留对应的分析子节位置
- M5S06 将作为该 section 的子节（如 4.3 Analysis and Discussion）存在

---

## 1. 实验设置

### 1.1 数据集

| 数据集 | 规模 | 划分 | 预处理 | 来源 |
|--------|------|------|--------|------|
| ... | ... | ... | ... | ... |

### 1.2 Baseline 方法

| Baseline | 来源 | 本地验证状态 | 关键超参数 |
|---------|------|------------|----------|
| ... | ... | ... | ... |

### 1.3 评估指标

- 指标定义（与 M2S05 一致）
- 固定 seed=42 的单次结果验证方式

### 1.4 实现细节

- 框架版本（PyTorch/TensorFlow/JAX 等）
- 硬件信息
- 超参数选择策略
- 随机种子（固定为 42）

### 1.5 实验结果图 Provenance

| 图 | nature-figure 结论 | 数据源 | 绘图脚本 | 输出路径 | 一致性检查 |
|----|----------------------|--------|---------|---------|------------|
| Fig 2 | ... | experiments/results.tsv | scripts/plot_results.py / notebook | experiments/figures/... | ☐ |
| Fig 3 | ... | experiments/analysis_results.tsv | scripts/plot_analysis.py / notebook | experiments/figures/... | ☐ |

- 实验结果图必须由原始数据和绘图代码生成；禁止使用 `gpt-image-2` 或 Draw.io 生成数值图
- 实验结果图必须遵循 `nature-figure` skill 的结论先行、证据逻辑、导出与 QA 原则；这里记录的是绘图规范，不是使用 image2 画结果

---

## 2. 主实验结果

### 2.1 总体对比（Table 1）

使用 `booktabs` 格式（无竖线）：

| Method | Dataset-1 | Dataset-2 | ... | Avg |
|--------|-----------|-----------|-----|-----|
| Baseline-1 | ... | ... | ... | ... |
| Baseline-2 | ... | ... | ... | ... |
| **Ours** | **...** | **...** | **...** | **...** |

- **所有数值必须与 `experiments/results.tsv` 完全一致**
- 最佳结果加粗
- 单次结果格式：报告 seed=42 的指标值
- 不标注统计显著性；未做多 seed 重复实验时不得写 p-value / mean±std

### 2.2 关键发现（为 M5S06 预留分析入口）

每个发现应简洁陈述事实，不展开解释；解释和深层原因分析留给 M5S06。

1. **发现 1**: ...（对应具体数值）→ *M5S06 对应分析子节: 4.X ...*
2. **发现 2**: ... → *M5S06 对应分析子节: 4.X ...*
3. **发现 3**: ... → *M5S06 对应分析子节: 4.X ...*

---

## 3. 效率/复杂度对比（如适用）

| Method | 参数量 | FLOPs | 推理时间 | 训练时间 |
|--------|--------|-------|---------|---------|
| ... | ... | ... | ... | ... |

---

## 写作检查清单

- [ ] 所有数值与原始数据交叉验证，无矛盾
- [ ] 表格使用 booktabs（\toprule, \midrule, \bottomrule），无竖线
- [ ] 图表有 \label 和 \ref 引用
- [ ] 使用了 Figure~\ref{} 和 Table~\ref{}（含 ~ 防断行）
- [ ] 实验结果图来自真实数据和绘图代码，不来自 image2 / Draw.io
- [ ] 实验结果图已按 nature-figure 原则记录结论、证据逻辑、导出格式与 QA
- [ ] 随机种子固定为 42 且已报告
- [ ] baseline 与本文方法使用相同评估协议
- [ ] 已遵循 M5S02 Style & Layout Profile 的表格/图密度与版式约束
- [ ] 无口语化表达
