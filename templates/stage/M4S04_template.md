# M4S04 Analysis Results Integration & Evidence Packaging

> Stage: M4S04
> Agent: Analysis Agent
> Output: `knowledge/M4/M4S04_analysis_results.md`

---

## 1. 统计分析

| 对比 | 指标 | p-value | 效应量 | 置信区间 | 结论 |
|------|------|---------|--------|---------|------|
|      |      |         |        |         |      |

## 2. Claim Ledger

| Claim ID | Claim Text | Evidence | Status | Caveats | Paper Role |
|----------|-----------|----------|--------|---------|------------|
| C1       |           |          | supported / partially_supported / unsupported / deferred | | main_text / appendix / removed |

### 2.1 Evidence usability rule
- `supported`: 可放入主文主结论，但仍需保留适用条件。
- `partially_supported`: 只能弱化表述，或放入附录；若进主文，必须写 caveat。
- `unsupported`: 不得放入主结论，应移除或改写为限制/负面发现。
- `deferred`: 证据不足，不得当作已验证结果。

### 2.2 不能使用的证据
- 如果 evidence 只能说明探索性现象、样本过少、对照不成立或偏离设计，必须标记为 `unusable` / `removed`。
- `appendix` 只适合可保留但不宜进入主结论的弱证据，不等于可直接支撑 claim。

## 3. 洞察提炼 (Insight Articulation)

- **洞察 1**: ...
  - **So what?**: 对领域的意义是...
  - **So what?**: 对方法设计的启示是...

## 4. 局限性

- **数据限制**: ...
- **指标限制**: ...
- **实现限制**: ...
- **鲁棒性限制**: ...
- **可复现性风险**: ...

## 5. 证据可用性

| Evidence ID | Source | Usability | Reason | Paper Handling |
|-------------|--------|-----------|--------|----------------|
|             |        | usable / weak / unusable |        | main_text / appendix / removed |

## 6. M4→M5 Handoff

### 5.1 核心发现摘要
- ...

### 5.2 完整 Claim-Evidence 映射
| Claim ID | Evidence Files | Paper Role |
|----------|---------------|------------|
|          |               |            |

### 5.3 Artifact 路径清单
- 主实验结果: ...
- 分析实验结果: ...
- 图表/可视化: ...

### 5.4 已知局限与应对建议
- ...

### 5.5 建议的 M5 论文结构要点
- Introduction 可强调: ...
- Method 需补充: ...
- Experiments 应包含: ...
- Analysis 应深入: ...

---

## 7. Deterministic Gate Requirements

M4S04 通过前必须满足：

- `knowledge/M4/M4S04_analysis_results.md` 同时覆盖 ablation/消融、mechanism/机制、robustness/鲁棒、failure/负面或失败分析
- 必须明确回答 how / where / why：方法怎么 work、哪里 work、为什么 work，以及哪里不 work
- 所有 claim-carrying evidence 必须说明 baseline inclusion；性能、鲁棒性、泛化相关 claim 必须有 baseline/基线 对照或降级为 caveat/appendix
- `experiments/analysis_results.tsv` 必须包含 `slice`、`analysis_type`、`method`、`metric`、`value` 等列，并包含 baseline 与 ours/proposed 行
- 必须存在分析 artifact 目录：`experiments/artifacts/analysis_experiment/`（或 `deep_analysis/` / `m4_analysis/`）
- artifact 目录必须包含 `manifest.yaml`、`reproduction.md`、至少一个分析图/可视化文件
- `manifest.yaml` 必须列出至少 3 个 `analysis_slices`，覆盖 ablation、mechanism、robustness，并记录 `baseline_inclusion` 和 `literature_basis`
- Claim Ledger 中 `unsupported`、`deferred`、`unusable` evidence 不得标为 `main_text`
- `knowledge/handoff_M4_M5.md` 必须包含 claim/evidence 映射、artifact 路径、M5 写作指导、局限/caveat、usable/weak evidence status
