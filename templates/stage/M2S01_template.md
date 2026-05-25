# M2S01: Problem-Driven Cross-Domain Literature Search

> **Stage**: M2S01
> **Module**: M2 — Method Design
> **Agent**: Method Agent
> **Input**: handoff_M1_M2.md, M1S02_literature_deepdive.md, M1S03_research_question.md, M1S04_hypothesis_generation.md
> **Output**: knowledge/M2/M2S01_cross_domain_search.md

---

## 0. 项目入口与锚点约定

- **foundation anchors**: 这些是最接近的基线家族，优先用于定义“继承了什么 / 必须改什么”。
- **reference anchors**: 这些是近邻比较对象，优先用于验证机制差异和写作中的 related work 对比。
- **处理方式**: 在候选方案表中标注是否来自入口锚点，以及它对应的是 foundation 还是 reference。

## 1. Gap → 技术问题拆解

基于 M1 识别的核心 Gap，拆解为具体技术问题。

### Gap 列表（来自 M1）
| 优先级 | Gap ID | 原始 Gap 描述 | 关联假设 |
|--------|--------|-------------|---------|
| P0 | Gap-1 | {{gap_1_description}} | H1 |
| P1 | Gap-2 | {{gap_2_description}} | H2 |

### 技术问题拆解
| Gap ID | 技术问题 | 子问题 |
|--------|---------|--------|
| Gap-1 | {{technical_problem_1}} | {{sub_problem_1a}}, {{sub_problem_1b}} |
| Gap-2 | {{technical_problem_2}} | {{sub_problem_2a}}, {{sub_problem_2b}} |

---

## 2. 搜索策略：Public DB + Web 双轨

> **原则**: M1 搜索的是领域强相关文献，M2 搜索的是**弱相关/跨领域**文献。
> **搜索流程**: 先查 Public DB（复用 M1 积累 + 其他项目贡献）→ 补充 Web 搜索 → 引用链扩展
> **搜索策略**: 同模态不同任务 / 同任务不同模态 / 底层原理相通 / 相似结构问题

### 2.0 搜索前准备

```yaml
# M2_source_log.yaml 初始化
search_statistics:
  total_queries: 0
  public_db_hits: 0
  web_search_hits: 0
  citation_chain_hits: 0
  unique_papers_discovered: 0
  papers_shortlisted: 0
  search_dimensions_covered: []
  query_ledger: []
```

### 2.0 M1 Source Log 交叉验证（搜索前必读）

在正式开始 M2 跨域搜索前，必须读取 `knowledge/M1/M1_source_log.yaml`，建立 M1 已覆盖文献的 "黑名单/参考名单"。

```yaml
m1_source_log_summary:
  total_sources_in_m1: {{N_m1}}
  cross_domain_sources_in_m1: {{N_m1_cross}}  # M1 中已存在的跨领域论文
  mechanisms_already_covered:
    - mechanism: "{{mechanism_name}}"
      source_ids: ["{{paper_id_1}}", "{{paper_id_2}}"]
      domain: "{{domain}}"
      gap_it_solves: "{{gap_id}}"
      our_assessment: "M1 已覆盖，M2 应避免重复发现"
```

> **原则**: M2 的跨域搜索不是"重新发现 M1 已经读过的东西"，而是"在 M1 已覆盖范围之外寻找新灵感"。

---

### 2.1 搜索维度 1: 同模态不同任务
- **目标 Gap**: {{target_gap}}
- **搜索思路**: 相同数据模态（{{modality}}），不同任务目标
- **关键词组合**: {{keywords_same_modality}}

#### Step 1: Public DB 查询
```yaml
query_ledger_entry:
  query: "{{keywords_same_modality}}"
  source: public_db
  filters: "domain_tags={{domain_tags}}, year_range={{year_range}}"
  results_count: {{N_db}}
  timestamp: "{{timestamp}}"
```
- **Public DB 命中**: {{N_db}} 篇
- **新发现（未在 M1 中出现）**: {{N_new}} 篇

#### Step 2: Web 搜索补充
```yaml
query_ledger_entry:
  query: "{{web_query}}"
  source: web_search
  results_count: {{N_web}}
  timestamp: "{{timestamp}}"
```
- **Web 补充**: {{N_web}} 篇

#### Step 3: 引用链扩展（对重点论文）
- **前向引用**: 查找引用 [重点论文] 的后续工作 → {{N_cite}} 篇
- **后向引用**: 查找 [重点论文] 引用的基础工作 → {{N_ref}} 篇

#### 发现论文列表
| 论文 | 作者/年份 | 原任务 | 核心思想 | 来源(PublicDB/Web/引用) | 与本 Gap 关联 |
|------|----------|--------|---------|----------------------|-------------|

### 2.2 搜索维度 2: 同任务不同模态
- **目标 Gap**: {{target_gap}}
- **搜索思路**: 相同任务目标（{{task_goal}}），不同数据模态
- **关键词组合**: {{keywords_same_task}}
- **发现论文列表**:
  | 论文 | 作者/年份 | 原模态 | 核心思想 | 与本 Gap 关联 |
  |------|----------|--------|---------|-------------|

### 2.3 搜索维度 3: 底层原理相通
- **目标 Gap**: {{target_gap}}
- **搜索思路**: 数学/信息论/优化/控制原理相通
- **关键词组合**: {{keywords_principle}}
- **发现论文列表**:
  | 论文 | 作者/年份 | 原理领域 | 核心思想 | 与本 Gap 关联 |
  |------|----------|---------|---------|-------------|

### 2.4 搜索维度 4: 相似结构问题
- **目标 Gap**: {{target_gap}}
- **搜索思路**: 问题结构相似（动态、鲁棒、稀疏、自适应等）
- **关键词组合**: {{keywords_structure}}
- **发现论文列表**:
  | 论文 | 作者/年份 | 相似结构 | 核心思想 | 与本 Gap 关联 |
  |------|----------|---------|---------|-------------|

---

## 3. M2_source_log.yaml 核心记录

> **重要**: 以下 YAML 内容是对 `knowledge/M2/M2_source_log.yaml` 核心部分的摘要展示。
> Method Agent 搜索过程中应实时维护此文件。

### Source 记录示例
```yaml
sources:
  - id: "{{paper_id}}"
    title: "{{paper_title}}"
    authors: ["{{author1}}", "{{author2}}"]
    venue: "{{venue}}"
    date: "{{YYYY-MM}}"
    url: "{{url}}"
    type: academic
    credibility: {{1-5}}
    verification: confirmed
    key_claims: ["{{claim_id}}"]
    limitations_noted: ["{{lim1}}", "{{lim2}}"]
    code_availability: open_source / broken / closed
    # M2-specific
    entry_anchor_id: "anchor_01"   # 如果来源于项目入口锚点则填写
    entry_anchor_role: foundation | reference | both | ""
    search_dimension: same_modality_diff_task
    target_gap: "{{gap_id}}"
    source_domain: "{{domain}}"
    core_mechanism: "{{one_sentence}}"
    adaptation_potential: high
    relevance_to_our_gap: "{{gap_id}}"
    discovery_source: public_db   # public_db | web_search | citation_chain
    discovery_query: "{{query}}"
    abstract: "{{abstract}}"
    method_summary: "{{method_summary}}"
    key_results: ["{{result}}"]
```

## 4. 候选方案池 + M1 Source Log 交叉验证

> **每新增一个候选方案，必须立即与 `M1_source_log.yaml` 交叉验证。**

### M1-M2 交叉验证总表

| 候选方案 | 来源论文 | M1 中是否存在？ | 关系类型 | 差异说明（如为重复/变体） |
|---------|---------|----------------|---------|------------------------|
| 方案 1 | {{paper_id}} | 是 / 否 | 新发现 / M1 已覆盖 / 机制重复 / 变体关系 | {{diff_explanation}} |
| 方案 2 | {{paper_id}} | 是 / 否 | 新发现 / M1 已覆盖 / 机制重复 / 变体关系 | {{diff_explanation}} |
| 方案 3 | {{paper_id}} | 是 / 否 | 新发现 / M1 已覆盖 / 机制重复 / 变体关系 | {{diff_explanation}} |

**关系类型定义**:
- **新发现**: M1 Source Log 中完全没有相关文献
- **M1 已覆盖**: M1 已经调研并记录了该论文本身
- **机制重复**: 该论文的核心机制已在 M1 的某篇文献中被实现（即使不是同一篇论文）
- **变体关系**: 该论文是 M1 某篇文献的方法变体/扩展/简化

### 候选方案 1: {{solution_name_1}}
| 属性 | 内容 |
|------|------|
| 来源论文 | {{paper_title}}, {{authors}}, {{year}} |
| 来源领域 | {{source_domain}} |
| 目标 Gap | {{target_gap_id}} |
| 核心思想 | {{core_idea}} |
| 关联理由 | {{relevance_reasoning}} |
| 适配难度 | 高 / 中 / 低 |
| 初步可行性 | 高 / 中 / 低 |
| Public DB ID | {{paper_id}} |
| **M1 交叉验证状态** | 新发现 / M1 已覆盖 / 机制重复 / 变体关系 |
| **与 M1 差异说明** | {{m1_diff}} |

### 候选方案 2: {{solution_name_2}}
...

### 候选方案 3: {{solution_name_3}}
...

### 候选方案 4: 领域内改进方案
> 基于 M1S02 了解的本领域技术，提出改进方向
| 属性 | 内容 |
|------|------|
| 来源 | 本领域现有工作改进 |
| 改进方向 | {{improvement_direction}} |
| 目标 Gap | {{target_gap_id}} |

---

## 5. 候选方案初筛与排序

| 排序 | 方案 | 来源领域 | 目标 Gap | 创新性 | 适配难度 | 可行性 | 后续分析 |
|------|------|---------|---------|--------|---------|--------|---------|
| 1 | ... | ... | ... | ... | ... | ... | ✅ M2S02 深入 |
| 2 | ... | ... | ... | ... | ... | ... | ✅ M2S02 深入 |
| 3 | ... | ... | ... | ... | ... | ... | ⚪ 备选 |
| 4 | ... | ... | ... | ... | ... | ... | ❌ 放弃 |

**放弃理由**: {{drop_reason}}

---

## 6. 搜索统计与质量自检

### 6.1 M2_source_log.yaml 统计汇总
```yaml
search_statistics:
  total_queries: {{N}}
  public_db_hits: {{N_db}}
  web_search_hits: {{N_web}}
  citation_chain_hits: {{N_cite}}
  unique_papers_discovered: {{M}}
  papers_shortlisted: {{K}}
  shortlisted_source_ids: ["{{paper_id_1}}", "{{paper_id_2}}"]
  search_dimensions_covered:
    - same_modality_diff_task
    - same_task_diff_modality
    - shared_principle
    - similar_structure
  query_ledger:
    - query: "..."
      source: public_db
      results_count: {{N}}
      timestamp: "..."
    - query: "..."
      source: web_search
      results_count: {{N}}
      timestamp: "..."
    - query: "..."
      source: citation_chain
      results_count: {{N}}
      timestamp: "..."

gap_solution_map:
  "{{gap_id}}":
    solutions: ["{{paper_id_1}}", "{{paper_id_2}}"]
    selected_solution: "{{paper_id_1}}"
    rationale: "why these candidates can address the technical problem"
```

- **搜索维度覆盖**: 4/4 (同模态/同任务/原理/结构)
- **总搜索查询数**: {{N}}
- **总发现论文数**: {{M}}
- **候选方案数**: {{K}} (≥3)
- **Public DB 命中数**: {{DB_hits}}
- **Web 搜索补充数**: {{Web_hits}}

**硬性要求**:
- `search_statistics.query_ledger` 必须非空，每条记录包含 query、source 和正数 results_count/hits/sources_found。
- 必须能识别 Public DB / 文库、Web / 互联网或 citation-chain 检索面。
- `search_dimensions_covered` 或 `sources[].search_dimension` 至少覆盖 2 个跨域检索维度。
- 每个 `sources[]` 必须包含 search_dimension、target_gap、source_domain、core_mechanism、adaptation_potential、discovery_source、discovery_query。
- `gap_solution_map` 必须非空，每个 Gap 至少有 1 个候选 solution。

---

## 7. 传递给下游的信息

- **M2_source_log.yaml 路径**: `knowledge/M2/M2_source_log.yaml`
- **已导入 Public DB**: 是/否（M2S01 完成后由 Conductor 执行导入）

- **重点分析对象**: 方案 {{N}}、方案 {{M}}（需在 M2S02 深入分析）
- **搜索盲区**: 哪些维度搜索不足？
- **风险提示**: 哪些方案的适配可能存在根本障碍？
- **推荐搜索方向**: 如果 M2S02 发现当前候选不足，建议补充搜索的方向
