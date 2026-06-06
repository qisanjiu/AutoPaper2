# M2S05: Experiment Setup Design

> **Stage**: M2S05
> **Module**: M2 — Method Design
> **Agent**: Method Agent
> **Input**: M2S04_algorithm_theory.md, M1S02_literature_deepdive.md
> **Output**: knowledge/M2/M2S05_experiment_setup.md + knowledge/M2/M2S05_metric_protocol.yaml

---

## 1. Benchmark & Dataset Selection

### 1.1 数据集

| 数据集 | 规模 | 任务类型 | 选择理由 | 获取方式 | 许可证 |
|--------|------|---------|---------|---------|--------|
| {{dataset_1}} | {{size}} | {{task}} | {{reason}} | {{url}} | {{license}} |
| {{dataset_2}} | {{size}} | {{task}} | {{reason}} | {{url}} | {{license}} |

### 1.2 数据集获取清单（供 M3S02 执行）

> **原则**: M2 阶段只定义"需要哪些数据"，不实际下载。下载由 M3S02 通过统一命令执行。
> **公共缓存**: 优先使用 `data/datasets/` 全局缓存。如缓存已存在，项目通过软链接引用；如不存在，按以下清单下载。

| 数据集 | 下载方式 | 具体命令 | 目标路径 | 校验方式 | 预估大小 | 是否已在公共缓存 |
|--------|---------|---------|---------|---------|---------|---------------|
| {{dataset_1}} | torchvision / wget / manual | `{{download_cmd}}` | `data/datasets/{{id}}/` | MD5: {{md5}} / SHA256: {{sha256}} | {{size}} | 是/否 |
| {{dataset_2}} | ... | ... | ... | ... | ... | ... |

**公共数据集库规范**:
- 全局缓存位置: `AutoPaper2/data/datasets/`
- 注册表: `AutoPaper2/data/datasets/.dataset_registry.yaml`
- 项目引用方式: `ln -s ../../../data/datasets/<id>/ ./experiments/data/<id>`
- 校验: 下载完成后必须验证 checksum，与注册表比对

### 1.3 数据预处理

- **训练/验证/测试划分**: {{split_ratio}}
- **数据清洗步骤**: ...
- **数据增强策略**: ...
- **预处理代码参考**: ...

### 1.4 伦理与许可证

- **数据使用许可**: ...
- **隐私考虑**: ...
- **使用限制**: ...

---

## 2. Baseline Selection

> **硬性边界**: M3 baseline 只能是外部相关工作、官方实现、官方包或完整忠实复现的 comparator。本文方法的消融、禁用组件、轻量变体、替代超参版本、proxy/simple/toy 实现都不能作为 M3 baseline；这些只能在 M4 的 ablation / mechanism / robustness 分析中出现。

### 2.1 Baseline 列表

| 方法 | 来源论文 | comparator_type | 选择理由 | 代码可用性 | 实现来源 | ablation_of_ours | 备注 |
|------|---------|-----------------|---------|-----------|---------|------------------|------|
| {{baseline_1}} | {{paper}} | external_prior_work / official_baseline / reproduced_prior_work | {{reason}} | A(开源维护)/B(开源不可运行)/C(未开源) | 官方/完整复现/官方包 | false | ... |
| {{baseline_2}} | {{paper}} | ... | {{reason}} | ... | ... | false | ... |

### 2.2 代码可用性评估

| Baseline | 代码可用性 | 评估依据 | 实现策略 | implementation_fidelity | fidelity_evidence |
|----------|-----------|---------|---------|-------------------------|-------------------|
| {{baseline_1}} | {{grade}} | {{evidence}} | 直接使用/修复后使用/完整忠实复现 | official_code / full_reproduction / paper_faithful_reproduction | source id / official repo / config match |

自行实现只允许作为“完整忠实复现”。如果无法达到论文结构、关键模块、训练/评估协议和 checkpoint/配置的一致性，必须标记为不可作为 M3 baseline，并在 M4 或局限性中处理；不得退化为简单实现。

### 2.3 公平性保证

- [ ] 所有方法使用**相同的数据划分**
- [ ] 所有方法使用**相同的评估指标**
- [ ] 所有方法使用**相同的训练预算**（epochs/time）
- [ ] 超参数调优策略**一致**（grid search / random search / fixed）
- [ ] baseline 列表中没有本文方法的消融/变体/禁用组件版本

### 2.4 与消融设计的协调

> 确认 baseline 中的组件不会与后续消融实验产生冲突；若某个对照是“去掉本文组件”的变体，它不是 baseline，必须移到 M4。

| Baseline 组件 | 消融实验中是否验证 | 冲突说明 |
|--------------|-----------------|---------|
| ... | 是/否 | ... |

---

## 3. Experiment Protocol

### 3.0 相关工作实验设置参考

| 参考论文 | 数据集 | 指标 | Baselines | 实验方法/协议 | 可迁移到本文的部分 | 不可迁移原因 |
|----------|--------|------|-----------|---------------|--------------------|--------------|
| ... | ... | ... | ... | ... | ... | ... |

### 3.1 实验目标列表

| 实验 ID | 目的 | 目标假设 | 验证内容 | 对照组/Baselines | 指标 | 必需/可选 |
|---------|------|---------|---------|------------------|------|----------|
| Exp-1 | 验证核心方法是否优于相关工作 | H1 | 主实验：方法 vs Baseline | ... | ... | 必需 |
| Exp-2 | 证明组件 A 如何起作用 | H2 | 消融实验：组件 A 的有效性 | ... | ... | 必需 |
| Exp-3 | 验证边界条件或鲁棒性 | — | 鲁棒性实验 | ... | ... | 可选 |

### 3.2 超参数设置

| 超参数 | 值 | 选择依据 | 搜索范围（如适用） |
|--------|-----|---------|-----------------|
| Learning rate | {{value}} | {{reason}} | {{range}} |
| Batch size | {{value}} | {{reason}} | {{range}} |
| Epochs | {{value}} | {{reason}} | — |
| Optimizer | {{value}} | {{reason}} | — |
| ... | ... | ... | ... |

### 3.3 训练协议

- **优化器**: {{optimizer}}
- **学习率调度**: {{lr_schedule}}
- **早停条件**: {{early_stop}}
- **正则化**: {{regularization}}
- **随机种子**: 42（固定单次实验；不做多 seed 重复实验）
- **硬件环境**: {{hardware}}

### 3.4 评估协议

- **评估指标**:
  | metric_protocol_id | 数据集 | 场景/任务 | Split | 指标 | 定义 | 计算方式 | 方向 | 取值范围 | 正常参考范围 | 协议来源 |
  |--------------------|--------|-----------|-------|------|------|----------|------|----------|--------------|----------|
  | mp_{{dataset}}_{{metric}} | {{dataset}} | {{scenario}} | test | {{metric_1}} | ... | ... | higher_is_better / lower_is_better | [0, 1] | [{{normal_low}}, {{normal_high}}] | paper/official benchmark/leaderboard |

- **指标协议锁定原则**:
  - M2S05 必须为每个会进入 M3/M4 的 dataset + scenario + split + metric 组合分配唯一 `metric_protocol_id`。
  - 指标必须说明它对哪个数据集、哪个场景/任务、哪个 split 是正常指标；不得只写 "accuracy"、"F1" 等裸指标名。
  - 必须给出 `value_range` 与 `normal_reference_range`。超出 `value_range` 是实现错误；超出 `normal_reference_range` 是异常结果，M3 必须报告并做 triage，不能静默推进。
  - 必须给出 `metric_sanity_check`，用一个可手算小样例证明指标方向、公式、平均方式、类别/样本权重处理正确。

同步写入 `knowledge/M2/M2S05_metric_protocol.yaml`：

```yaml
schema_version: 1
metric_protocols:
  - metric_protocol_id: mp_{{dataset}}_{{metric}}
    dataset: "{{dataset}}"
    scenario: "{{scenario_or_task}}"
    split: "test"
    metric_key: "{{metric_1}}"
    definition: "..."
    calculation: "..."
    direction: higher_is_better
    value_range: [0.0, 1.0]
    normal_reference_range: [{{normal_low}}, {{normal_high}}]
    protocol_source:
      source_id: "{{paper_or_benchmark_id}}"
      table_or_section: "..."
      rationale: "why this metric is standard for this dataset/scenario"
    metric_sanity_check:
      test_case: "..."
      expected_value: 0.0
      tolerance: 1.0e-6
```

- **统计检验**:
  - 检验方法: 不适用（固定 seed=42 的单次实验）
  - 显著性水平: 不适用
  - 报告方式: single run result with seed=42

---

## 4. 可复现性检查清单

- [ ] 随机种子已固定并记录
- [ ] 所有超参数已记录（含选择依据）
- [ ] 环境依赖已列出（requirements.txt）
- [ ] 代码版本已记录（git commit hash）
- [ ] 数据预处理流程已文档化
- [ ] 训练/评估脚本已准备
- [ ] 结果记录格式已定义

---

## 5. 传递给下游的信息

- **主要数据集的大小和格式**: ...
- **数据加载时需要注意**: ...
- **需要复现的 baseline 数量**: ...
- **官方代码可直接使用的**: ...
- **需要自行实现的**: ...
