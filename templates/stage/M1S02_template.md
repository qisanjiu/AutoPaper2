# Literature Deep Dive: {{topic}}

## 0. 项目入口与锚点
- **foundation anchors**: ...
- **reference anchors**: ...
- **处理规则**: foundation anchor 必须在 Round 1-3 中被优先验证其身份、来源和可继承性；reference anchor 作为近邻比较对象纳入 Source Log。

## 1. 检索策略与 3-Round 迭代搜索日志

### Round 1: 广泛搜索（Breadth Search）
- **目标**: 覆盖所有子领域，建立全景图
- **数据库**: ...
- **关键词组合**: ...
- **时间范围**: ...
- **检索结果**: retrieved_count=N; screened_count=S; retained_count=M; retained_source_ids=[...]
- **Reviewer 意见**: （ Survey Review Agent 审查后填写 ）
  - Verdict: PASS / REWORK / HALT
  - 评分: X/10
  - 关键问题: ...

### Round 2: 定向搜索（Depth Search）
- **目标**: 针对 Round 1 识别的 Gap 深入搜索
- **补充关键词**: ...
- **关键作者追踪**: ...
- **检索结果**: retrieved_count=N; screened_count=S; retained_count=M; retained_source_ids=[...]
- **Reviewer 意见**: （ Survey Review Agent 审查后填写 ）
  - Verdict: PASS / REWORK / HALT
  - 评分: X/10
  - 关键问题: ...

### Round 3: 盲区填补（Blindspot Search）
- **目标**: 填补 Round 1-2 遗漏的盲区
- **盲区检查项**:
  - [ ] 近 6 个月新工作
  - [ ] 对立观点/负面结果
  - [ ] 奠基性/经典工作
  - [ ] 关键作者其他工作
  - [ ] Source Log 与正文一致性
- **检索结果**: retrieved_count=N; screened_count=S; retained_count=M; retained_source_ids=[...]
- **Reviewer 意见**: （ Survey Review Agent 终审后填写 ）
  - Verdict: PASS / REWORK / HALT
  - 评分: X/10
  - 最终评价: ...

### 搜索统计汇总
- 总搜索轮次: 3
- 总保留文献: N 篇
- 总 Source Log 条目: M 条
- 最终 Review 评分: X/10

### Source Log Search Provenance（必须同步写入 `M1_source_log.yaml`）

```yaml
search_provenance:
  databases:
    - "Semantic Scholar public_db"
    - "arXiv public_db"
    - "Google Scholar internet web search"
  inclusion_criteria:
    - "Matches the project topic, core task, or directly relevant method family"
    - "Contains method, model, experiment setup, results, or limitation evidence"
  exclusion_criteria:
    - "Duplicate, inaccessible, non-technical, or not relevant after abstract/full-text screening"
  rounds:
    - round: 1
      purpose: "breadth"
      queries: ["..."]
      retrieved_count: 30
      screened_count: 30
      retained_source_ids: ["source_id_1"]
    - round: 2
      purpose: "depth"
      queries: ["..."]
      retrieved_count: 20
      screened_count: 20
      retained_source_ids: ["source_id_2"]
    - round: 3
      purpose: "blindspot"
      queries: ["..."]
      retrieved_count: 10
      screened_count: 10
      retained_source_ids: ["source_id_3"]
  blindspot_checks:
    recent_work: "近 6 个月 / latest work checked"
    negative_or_opposing_results: "negative/opposing/contradicting results checked"
    seminal_or_classic_work: "seminal/classic/foundation work checked"
    key_authors: "key authors and teams checked"
    source_log_consistency: "Markdown citations match Source Log IDs"
  perspective_coverage:
    scenario_task:
      status: covered
      queries: ["scenario task application gap"]
      source_ids: ["source_id_1"]
      finding: "场景/任务视角下的主要问题"
    model_method:
      status: covered
      queries: ["model method architecture limitation"]
      source_ids: ["source_id_2"]
      finding: "模型/方法视角下的主要问题"
    metric_performance:
      status: covered
      queries: ["metric accuracy performance efficiency"]
      source_ids: ["source_id_3"]
      finding: "指标/性能视角下的主要问题"
    dataset_protocol:
      status: covered
      queries: ["dataset benchmark experiment protocol"]
      source_ids: ["source_id_4"]
      finding: "数据集/实验协议视角下的主要问题"
    failure_limitation:
      status: covered
      queries: ["failure negative limitation defect"]
      source_ids: ["source_id_5"]
      finding: "失败/局限视角下的主要问题"
    baseline_comparison:
      status: covered
      queries: ["baseline comparison sota comparator"]
      source_ids: ["source_id_6"]
      finding: "baseline/对比视角下的主要问题"
```

**硬性要求**: 三轮 `queries`、`retrieved_count`、`screened_count`、保留来源 ID/数量都必须为可审计记录；`retained_source_ids` 必须对应 `sources[].id`。`perspective_coverage` 必须覆盖 scenario/task、model/method、metric/performance、dataset/protocol、failure/limitation、baseline/comparison 六类视角，每类必须有 status、queries、source_ids 和 finding/evidence_summary。

### Perspective Coverage（必须同步写入 `M1_source_log.yaml`）

| Perspective | Queries | Source IDs | Finding | Gap implication |
|-------------|---------|------------|---------|-----------------|
| scenario/task | ... | ... | ... | large / middle / small |
| model/method | ... | ... | ... | ... |
| metric/performance | ... | ... | ... | ... |
| dataset/protocol | ... | ... | ... | ... |
| failure/limitation | ... | ... | ... | ... |
| baseline/comparison | ... | ... | ... | ... |

---

## 2. 文献分类表
| 类别 | 代表论文 | 核心思想 | 局限性 |
|------|---------|---------|--------|
| 方法A | [作者, 年份] | ... | ... |

---

## 3. 详细文献卡片

### [论文标题]
- **作者**: ...
- **年份/Venue**: ...
- **背景 (Background)**: ...
- **贡献 (Contribution)**: ...
- **模型 / 系统框架 (Model)**: ...
- **方法 (Method)**: ...
- **实验设置 (Experiment Setup)**: 数据集、评价指标、实验方法、baseline、公平性设置、seed/统计检验
- **结果 (Results)**: ...
- **分析 (Analysis)**: 作者解释、消融、失败案例、误差分析或机制分析
- **结论 (Conclusion)**: ...
- **局限性**: ...
- **可迁移信号**: 可迁移的方法模块、实验设置、评价指标或写作结构
- **与我们的相关性**: ...
- **entry_anchor_id**: ...（如果该论文来自项目入口锚点）

---

## 4. 研究空白分析 (Research Gaps)
| Gap ID | 层级 | 类型 | 描述 | 证据 | Confidence | 潜在价值 |
|--------|------|------|------|------|-----------|---------|
| Gap-L-1 | 大方向: 场景/任务/领域缺陷 | vacancy/enhancement/validation | ... | 基于 [论文X,Y] | high | 高 |
| Gap-M-1 | 中方向: 模型/精度/指标/数据集 | vacancy/enhancement/validation | ... | 基于 [论文X,Y] | medium | 中 |
| Gap-S-1 | 小方向: 组件/方法细节/缺陷程度 | enhancement/validation | ... | 基于 [论文X,Y] | high | 高 |

### Gap 论证
- **大方向问题**: ...
- **中方向问题**: ...
- **小方向问题**: ...
- **证据链**: 每个 Gap 至少引用 2 个 Source Log 条目；如证据不足必须降 confidence

---

## 5. 方法论/技术方案库 (Solution Arsenal)

### 5.1 核心技术范式映射
| 问题类型 | 代表性方法/架构 | 代表论文 | 与我们 Gap 的匹配度 |
|---------|----------------|---------|------------------|
| ... | ... | ... | 高/中/低 |

### 5.2 新兴架构/模块速查表
| 架构/模块 | 提出年份 | 核心思想 | 潜在用途 |
|----------|---------|---------|---------|
| ... | ... | ... | ... |

---

## 6. 对比分析

---

## 7. 趋势与机会

---

## 8. 参考文献列表

---

## 9. 传递给下游的信息
- 最重要的 3 篇相关论文：...
- 最关键的 2 个研究空白：...
- 最自然的 baseline 选择：...
- 建议 Ideation Agent 优先考察的 Gap：...
