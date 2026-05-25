# AutoPaper2 公共文献数据库设计方案

> **状态**: 设计文档（未实现）  
> **目标**: 打通项目间文献数据孤岛，实现跨项目文献复用与去重  
> **范围**: Schema 设计、标签体系、查询复用流程、集成方案

---

## 1. 现状分析

### 1.1 现有文献字段清单（可复用基础）

AutoPaper2 当前在 `survey_memory.py` 中已定义 `Source` dataclass，字段如下：

| 字段 | 类型 | 说明 | 可复用性 |
|------|------|------|---------|
| `id` | str | AuthorYearKeyword 格式 | ✅ 直接复用，作为主键候选 |
| `title` | str | 论文标题 | ✅ 核心字段 |
| `authors` | list[str] | 作者列表 | ✅ 核心字段 |
| `venue` | str | 会议/期刊名 | ✅ 核心字段 |
| `date` | str | YYYY-MM 格式 | ✅ 核心字段 |
| `url` | str | 论文链接 | ✅ 核心字段 |
| `type` | enum | academic/news/official/expert/blog | ✅ 直接复用 |
| `credibility_score` | int | 1-5 可信度评分 | ✅ 跨项目可复用 |
| `verification_status` | enum | confirmed/partial/unverified/contradicted | ✅ 可复用 |
| `key_claims` | list[str] | 该文献支持的关键声明 ID 列表 | ⚠️ 需抽象为领域无关声明 |
| `limitations_noted` | list[str] | 已记录的局限性 | ✅ 可复用 |
| `code_availability` | enum | open_source/broken/closed | ✅ 可复用 |
| `relevance_to_our_gap` | str | 指向具体 gap_id | ❌ 项目特定，需改为领域标签 |

### 1.2 现有存储结构

```
projects/
  ├── project-a-20260101-120000/
  │     ├── state/survey_memory.yaml      # 项目级调研记忆
  │     └── knowledge/M1/M1_source_log.yaml  # 结构化来源日志
  └── project-b-20260102-090000/
        ├── state/survey_memory.yaml
        └── knowledge/M1/M1_source_log.yaml
```

**痛点**：
- 项目 A 已深度调研的论文，项目 B 需从零开始搜索
- 同一篇论文的 `credibility_score`、`limitations_noted` 等评估无法继承
- 多次调研中重复的网络搜索浪费 API 调用与时间

---

## 2. 总体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    公共文献数据库 (Public Literature DB)            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  papers     │  │  surveys    │  │  domain_tags            │  │
│  │  文献实体表  │  │  调研会话表  │  │  领域标签体系            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  claims     │  │  paper_tags │  │  query_cache            │  │
│  │  声明知识表  │  │  文献标签关联│  │  查询缓存               │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↑
                              │ YAML/JSON 存储（第一阶段）
                              │ SQLite（第二阶段，可选）
┌─────────────────────────────────────────────────────────────────┐
│                         集成层 (Integration Layer)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ DB Manager   │  │ Query Engine │  │ Import/Export        │   │
│  │ 数据库管理器  │  │ 查询引擎     │  │ 导入导出（项目↔公共） │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↑
              ┌───────────────┼───────────────┐
              ↓               ↓               ↓
        ┌─────────┐    ┌─────────┐    ┌─────────┐
        │ Project │    │ Project │    │ Project │
        │    A    │    │    B    │    │    C    │
        └─────────┘    └─────────┘    └─────────┘
```

---

## 3. Schema 设计

### 3.1 核心原则

1. **项目无关性**：公共库中不存储任何项目特定的 gap_id、research_question
2. **领域标签化**：用可扩展的领域标签（domain tags）替代项目级的 `relevance_to_our_gap`
3. **评估继承性**：一篇论文的 `credibility_score`、`limitations_noted` 可被后续项目继承并追加
4. **增量累加**：同一篇论文被多个项目调研时，字段内容应合并而非覆盖

### 3.2 表/集合设计

#### `papers` — 文献实体表

```yaml
papers:
  - paper_id: "vaswani2017attention"           # 主键，规范化的唯一标识
    identifiers:
      arxiv_id: "1706.03762"
      doi: "10.5555/3295222.3295349"
      semantic_scholar_id: "..."
      dblp_id: "..."
    title: "Attention Is All You Need"
    authors: ["Ashish Vaswani", "Noam Shazeer", ...]
    venue: "NeurIPS"
    year: 2017
    date: "2017-12"
    url: "https://arxiv.org/abs/1706.03762"
    pdf_url: "https://arxiv.org/pdf/1706.03762.pdf"
    type: "academic"
    
    # --- 评估字段（可继承/累加）---
    credibility_score: 5                        # 跨项目共识评分（可加权平均）
    verification_status: "confirmed"
    code_availability: "open_source"
    code_url: "https://github.com/..."
    
    # --- 内容摘要（领域无关）---
    abstract: "..."
    problem_statement: "..."                    # 该论文解决的核心问题
    method_summary: "..."                       # 方法核心（150字内）
    key_results: ["...", "..."]                 # 关键实验结果
    
    # --- 局限性（多来源累加）---
    limitations_noted:
      - source_project: "tsf-transformer-20260101-120000"
        limitation: "计算复杂度随序列长度平方增长"
        noted_at: "2026-01-15T10:00:00"
      - source_project: "llm-efficiency-20260201-090000"
        limitation: "内存占用大，长文本场景受限"
        noted_at: "2026-02-03T14:30:00"
    
    # --- 元数据 ---
    first_surveyed_at: "2026-01-15T10:00:00"
    last_updated_at: "2026-02-03T14:30:00"
    survey_count: 2                             # 被多少个调研项目引用过
    citation_count: 120000                      # 外部引用数（可缓存 Semantic Scholar）
```

#### `claims` — 声明知识表（领域无关化改造）

原 `key_claims` 是项目特定的声明 ID。公共库中应存储**领域无关的声明实体**：

```yaml
claims:
  - claim_id: "c_transformer_better_than_rnn_seq2seq"
    statement: "Transformer 在机器翻译任务上显著优于 RNN-based Seq2Seq"
    confidence: "high"
    supporting_papers: ["vaswani2017attention", "..."]
    contradicting_papers: []
    domains: ["nlp", "machine_translation", "sequence_modeling"]
    first_stated_at: "2026-01-15T10:00:00"
    
  - claim_id: "c_self_attention_o_n2_memory"
    statement: "Self-Attention 的计算和内存复杂度均为 O(n²)"
    confidence: "high"
    supporting_papers: ["vaswani2017attention", "..."]
    domains: ["deep_learning", "efficiency"]
```

#### `domain_tags` — 领域标签体系

```yaml
domain_tags:
  - tag_id: "computer_vision"
    name: "Computer Vision"
    aliases: ["CV", "视觉", "图像处理"]
    parent: null
    level: 1
    
  - tag_id: "nlp"
    name: "Natural Language Processing"
    aliases: ["NLP", "自然语言处理"]
    parent: null
    level: 1
    
  - tag_id: "transformer"
    name: "Transformer"
    aliases: ["Transformer", "注意力机制"]
    parent: "deep_learning_architectures"
    level: 3
    
  - tag_id: "time_series_forecasting"
    name: "Time Series Forecasting"
    aliases: ["TSF", "时间序列预测", "时序预测"]
    parent: "sequence_modeling"
    level: 3
```

#### `paper_tags` — 文献-标签关联表

```yaml
paper_tags:
  - paper_id: "vaswani2017attention"
    tag_id: "transformer"
    confidence: "high"                          # 标签匹配的置信度
    source: "manual"                            # manual | auto_keyword | auto_abstract
    added_by_project: "tsf-transformer-20260101-120000"
    added_at: "2026-01-15T10:00:00"
    
  - paper_id: "vaswani2017attention"
    tag_id: "nlp"
    confidence: "high"
    source: "manual"
    added_by_project: "tsf-transformer-20260101-120000"
    added_at: "2026-01-15T10:00:00"
```

#### `surveys` — 调研会话表

记录每次领域调研的上下文，用于追溯和审计：

```yaml
surveys:
  - survey_id: "survey-tsf-transformer-20260115"
    project_name: "tsf-transformer-20260101-120000"
    topic: "Transformer-based Time Series Forecasting"
    status: "completed"
    start_at: "2026-01-15T09:00:00"
    end_at: "2026-01-15T18:00:00"
    search_queries:
      - "Transformer time series forecasting"
      - "attention mechanism forecasting"
    papers_discovered: ["zhou2021informer", "wu2021autoformer", ...]
    papers_from_db: 5                            # 从公共库中命中复用的数量
    papers_from_web: 15                          # 通过网络搜索新发现的数量
```

#### `query_cache` — 查询缓存表

避免对相同/相似查询重复调用搜索引擎：

```yaml
query_cache:
  - query_hash: "sha256:..."
    query_text: "Transformer time series forecasting"
    cached_at: "2026-01-15T09:30:00"
    expires_at: "2026-07-15T09:30:00"           # 半年过期
    results:
      - paper_id: "zhou2021informer"
        rank: 1
      - paper_id: "wu2021autoformer"
        rank: 2
    total_hits: 47
```

---

## 4. 去重与标识机制

### 4.1 唯一标识策略

一篇论文可能有多个来源 ID（arXiv、DOI、Semantic Scholar、DBLP）。公共库采用**多标识符联合去重**：

```python
class PaperIdentifier:
    """论文唯一标识解析器"""
    
    # 优先级：DOI > arXiv ID > Semantic Scholar ID > 标题+第一作者+年份
    
    @staticmethod
    def canonical_id(paper: dict) -> str:
        if paper.get("doi"):
            return f"doi:{paper['doi']}"
        if paper.get("arxiv_id"):
            return f"arxiv:{paper['arxiv_id']}"
        if paper.get("semantic_scholar_id"):
            return f"s2:{paper['semantic_scholar_id']}"
        # fallback: 规范化标题 + 第一作者姓 + 年份
        first_author_last = extract_last_name(paper["authors"][0])
        title_hash = hash_title(paper["title"])
        return f"{first_author_last}{paper['year']}{title_hash[:8]}"
```

### 4.2 增量合并规则

当新项目的文献导入公共库时，若论文已存在，按以下规则合并：

| 字段 | 合并策略 | 说明 |
|------|---------|------|
| `title`, `authors`, `venue` | 取最长/最完整版本 | 补全元数据 |
| `abstract`, `method_summary` | 取最长版本 | 摘要通常有长短版本 |
| `credibility_score` | 加权平均 | 按 `survey_count` 加权 |
| `limitations_noted` | 追加去重 | 相同的 limitation 不重复添加 |
| `code_url` | 优先取非空值 | 首次发现代码链接即持久化 |
| `survey_count` | +1 | 累加调研引用次数 |
| `domains` / `tags` | 并集 | 合并所有项目的标签标注 |

---

## 5. 查询与复用流程

### 5.1 新项目调研时的标准流程

```
┌─────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│  输入查询    │────→│  1. 查询公共文献库   │────→│ 命中论文列表     │
│ (关键词/主题)│     │    (向量/标签/全文)  │     │ (含完整元数据)   │
└─────────────┘     └─────────────────────┘     └─────────────────┘
                                                        │
                              ┌─────────────────────────┘
                              ↓
                    ┌─────────────────────┐
                    │ 2. 命中论文预筛选    │
                    │   - 按标签相关性排序  │
                    │   - 按 credibility 过滤│
                    │   - 按时效性过滤      │
                    └─────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ↓                               ↓
    ┌─────────────────┐             ┌─────────────────┐
    │ 高置信度命中 ≥N  │             │ 命中不足或置信低  │
    │ (N=10, 可调)     │             │                 │
    └─────────────────┘             └─────────────────┘
              │                               │
              ↓                               ↓
    ┌─────────────────┐             ┌─────────────────┐
    │ 3a. 直接注入调研  │             │ 3b. 触发网络搜索  │
    │    记忆 (survey   │             │    补充新文献     │
    │    memory)       │             │                 │
    └─────────────────┘             └─────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              ↓
                    ┌─────────────────────┐
                    │ 4. 新文献导入公共库  │
                    │   - 去重、合并、打标签 │
                    └─────────────────────┘
                              │
                              ↓
                    ┌─────────────────────┐
                    │ 5. 更新查询缓存      │
                    └─────────────────────┘
```

### 5.2 查询接口设计

```python
class PublicLiteratureDB:
    """公共文献数据库查询接口"""
    
    def query(
        self,
        keywords: list[str],
        domain_tags: list[str] | None = None,
        year_range: tuple[int, int] | None = None,
        venue_filter: list[str] | None = None,
        min_credibility: int = 3,
        min_citation_count: int = 0,
        require_code: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> QueryResult:
        """
        多维度查询公共文献库。
        
        返回的论文已按以下规则排序：
        1. 标签匹配度（标签重叠越多越靠前）
        2. 可信度评分（credibility_score 降序）
        3. 引用次数（citation_count 降序）
        4. 调研引用次数（survey_count 降序，代表被多次验证）
        """
        ...
    
    def find_similar(
        self,
        paper_id: str,
        by: Literal["tag", "citation", "embedding"] = "tag",
        limit: int = 10,
    ) -> list[Paper]:
        """查找相似论文"""
        ...
    
    def check_duplicate(
        self,
        title: str,
        authors: list[str],
        year: int,
        arxiv_id: str | None = None,
        doi: str | None = None,
    ) -> str | None:
        """
        检查论文是否已在公共库中。
        返回已有的 paper_id，或 None（表示新论文）。
        """
        ...
```

### 5.3 与 Survey Memory 的集成点

在现有 `SurveyMemoryManager` 之上增加一个适配层：

```python
class SurveyMemoryWithPublicDB(SurveyMemoryManager):
    """增强版 SurveyMemory，优先查询公共库再触网搜索。"""
    
    def __init__(self, project_root: Path, public_db: PublicLiteratureDB):
        super().__init__(project_root)
        self.public_db = public_db
    
    def search(self, queries: list[str], domain_tags: list[str]) -> list[Source]:
        # 1. 先去重检查查询缓存
        cached = self.public_db.query_cache.get(queries)
        if cached and not cached.expired:
            return self._load_from_db(cached.paper_ids)
        
        # 2. 查询公共文献库
        db_results = []
        for q in queries:
            db_results.extend(self.public_db.query(
                keywords=q.split(),
                domain_tags=domain_tags,
            ).papers)
        
        # 3. 若命中不足，触网搜索补充
        if len(db_results) < self.min_hit_threshold:
            web_results = self.web_search(queries)
            # 去重：web_results 中已在 db_results 的跳过
            new_papers = [p for p in web_results if not self.public_db.check_duplicate(...)]
            # 新论文导入公共库
            self.public_db.import_papers(new_papers, source_project=self.project_id)
            db_results.extend(new_papers)
        
        # 4. 更新查询缓存
        self.public_db.query_cache.set(queries, db_results)
        
        return db_results
```

---

## 6. 领域标签体系设计

### 6.1 标签层级

```
Level 1 (大类):        ai / systems / theory / application
                         ↓
Level 2 (方向):         deep_learning / classical_ml / cv / nlp / robotics
                         ↓
Level 3 (技术/任务):    transformer / cnn / gnn / time_series_forecasting / object_detection
                         ↓
Level 4 (细分):         long_sequence_transformer / efficient_attention / vision_transformer
```

### 6.2 标签自动推导

```python
def auto_tag_paper(paper: Paper) -> list[PaperTag]:
    """基于标题、摘要、关键词自动推导领域标签。"""
    tags = []
    text = f"{paper.title} {paper.abstract}".lower()
    
    # 规则匹配（可维护的关键词映射表）
    for rule in TAG_RULES:
        if rule.matches(text):
            tags.append(PaperTag(
                tag_id=rule.tag_id,
                confidence="medium" if rule.is_weak_match else "high",
                source="auto_keyword",
            ))
    
    # 可选：接入轻量级分类模型（如 sentence-transformer + 标签向量匹配）
    # tags.extend(model_based_tagging(paper))
    
    return tags
```

### 6.3 标签冲突解决

- 人工标签（`source: manual`）优先级高于自动标签
- 多个项目对同一 paper 标注不同标签 → 全部保留，按 `confidence` 排序展示

---

## 7. 存储与部署方案

### 7.1 第一阶段：YAML 文件存储（推荐起步）

与现有 AutoPaper2 的 `survey_memory.yaml` 风格保持一致，降低实现成本：

```
AutoPaper2/
├── spiral/
│   └── public_db/                    # 新增模块
│       ├── __init__.py
│       ├── models.py                 # Paper, Claim, Tag 等 dataclass
│       ├── manager.py                # PublicLiteratureDB 主类
│       └── tag_rules.py              # 自动标签规则
├── data/
│   └── public_literature_db/         # 公共数据库目录（gitignore 可选）
│       ├── papers/                   # 每篇论文一个 YAML（或按年份分片）
│       │   ├── v/
│       │   │   └── vaswani2017attention.yaml
│       │   └── z/
│       │       └── zhou2021informer.yaml
│       ├── claims.yaml
│       ├── domain_tags.yaml
│       ├── paper_tags.yaml
│       ├── surveys.yaml
│       └── query_cache.yaml
```

**优点**：
- 与现有架构风格一致
- 人类可读、可手动编辑、可 git 版本控制
- 无需数据库依赖

**缺点**：
- 论文数量 >1000 时查询性能下降
- 全文检索需额外实现

### 7.2 第二阶段：SQLite 升级（可选）

当论文量 >5000 或查询延迟成为瓶颈时，可透明迁移到 SQLite：

```python
# manager.py 中预留接口
class StorageBackend(ABC):
    def query_papers(self, filters: QueryFilters) -> list[Paper]: ...
    def save_paper(self, paper: Paper) -> None: ...

class YAMLBackend(StorageBackend): ...
class SQLiteBackend(StorageBackend): ...
```

---

## 8. 与现有 AutoPaper2 的集成方案

### 8.1 最小侵入式改造

仅需修改以下文件：

| 文件 | 改动 | 说明 |
|------|------|------|
| `spiral/survey_memory.py` | +30 行 | `SurveyMemoryManager` 增加 `public_db` 可选参数 |
| `docs/AGENTS/survey/AGENT.md` | +10 行 | 更新 Survey Agent 规范，加入公共库查询步骤 |
| `utils/source_log_validator.py` | +5 行 | 验证时支持公共库来源标记 |
| 新增 `spiral/public_db/` | ~400 行 | 公共数据库完整模块 |

### 8.2 配置化开关

在 `config/venue_registry.yaml` 同级新增 `config/public_db.yaml`：

```yaml
public_literature_db:
  enabled: true
  path: "${SPIRAL_FRAMEWORK_ROOT}/../data/public_literature_db"
  min_hit_threshold: 10          # 公共库最少命中数，不足则触网搜索
  query_cache_ttl_days: 180      # 查询缓存半年过期
  auto_tagging: true             # 是否启用自动标签推导
  
  # 跨项目复用策略
  import_policy:
    merge_limitations: true      # 合并局限性记录
    inherit_credibility: true    # 继承可信度评分
    inherit_tags: true           # 继承领域标签
```

---

## 9. 使用示例

### 9.1 场景 1：新项目直接复用

```bash
# 创建项目：基于 Transformer 的时间序列预测
python scripts/state_manager.py create "Transformer-based Time Series Forecasting" "TSF-Transformer"

# 运行 M1S02 时，Survey Agent 行为变化：
# 1. 公共库查询关键词 "Transformer", "time series forecasting"
# 2. 命中 8 篇已有完整元数据的论文（Informer, Autoformer, FEDformer, PatchTST...）
# 3. 命中数 < 10，触网搜索补充 12 篇新论文
# 4. 新论文经去重后导入公共库
# 5. 最终 20 篇论文注入 survey_memory.yaml，其中 8 篇继承已有评估
```

### 9.2 场景 2：跨领域迁移

```bash
# 项目 A 已完成 "Vision Transformer" 调研
# 项目 B 创建 "Efficient Attention for Long Sequences"

# 公共库查询：
# - 直接命中项目 A 中标注了 "transformer" + "efficiency" 标签的论文
# - Swin Transformer, Linear Attention, Performer, FlashAttention...
# - 这些论文的 limitations（如 "quadratic complexity"）已被项目 A 记录
# - 项目 B 直接继承，无需重复阅读
```

### 9.3 场景 3：渐进式知识积累

```
项目 A 调研 → 50 篇论文入库 → 公共库规模 50
项目 B 调研 → 复用 15 篇 + 新增 35 篇 → 公共库规模 85
项目 C 调研 → 复用 30 篇 + 新增 20 篇 → 公共库规模 105
...
第 N 个项目 → 复用 80% + 新增 20% → 调研效率指数级提升
```

---

## 10. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| 标签体系膨胀 | 查询噪声增加 | 限制层级深度（max 4 级），定期 review 低频标签合并 |
| 元数据质量参差不齐 | 继承错误评估 | 显示评估来源项目 + 时间，支持覆盖而非强制继承 |
| 存储体积膨胀 | YAML 加载变慢 | 论文 YAML 按首字母分片；达到阈值后透明迁移 SQLite |
| 隐私/敏感内容泄露 | 公共库含未发表想法 | 公共库仅存储公开论文元数据，不含项目 specific 的分析 |
| 并发写入冲突 | 多项目同时修改 | YAML 阶段用文件锁；SQLite 阶段用事务 |

---

## 11. 实现路径建议（非当前任务）

若后续决定实现，建议按以下优先级：

1. **P0 — 核心骨架**（1-2 天）
   - `spiral/public_db/models.py`：定义 Paper, Tag, Claim dataclass
   - `spiral/public_db/manager.py`：YAML 存储后端 + 基本 CRUD
   - `spiral/public_db/importer.py`：从项目 `M1_source_log.yaml` 导入公共库

2. **P1 — 查询复用**（1-2 天）
   - 实现 `query()` 多维度查询
   - 改造 `SurveyMemoryManager` 增加公共库查询步骤
   - 更新 Survey Agent 规范文档

3. **P2 — 标签体系**（1 天）
   - `domain_tags.yaml` 初始定义（50-100 个常用标签）
   - `auto_tag_paper()` 规则引擎
   - 标签冲突解决逻辑

4. **P3 — 查询缓存**（0.5 天）
   - `query_cache.yaml` 实现
   - TTL 过期机制

5. **P4 — 质量与优化**（持续）
   - 数据校验与清理脚本
   - SQLite 后端迁移（按需）
   - 向量检索（sentence-transformer 标签匹配）

---

## 附录：现有字段 → 公共库字段映射表

| 现有字段 (`Source`) | 公共库字段 | 变更说明 |
|---------------------|-----------|---------|
| `id` | `paper_id` | 名称变更，格式规范化 |
| `title` | `title` | 无变更 |
| `authors` | `authors` | 无变更 |
| `venue` | `venue` | 无变更 |
| `date` | `date` | 无变更 |
| `url` | `url` | 无变更 |
| `type` | `type` | 无变更 |
| `credibility_score` | `credibility_score` | 合并策略：加权平均 |
| `verification_status` | `verification_status` | 取最高置信度 |
| `key_claims` | `claims` 表 + `paper_claims` 关联 | 领域无关化改造 |
| `limitations_noted` | `limitations_noted` | 改为带来源的列表，支持累加 |
| `code_availability` | `code_availability` + `code_url` | 新增 `code_url` |
| `relevance_to_our_gap` | `paper_tags` 关联表 | 项目特定 → 领域标签 |
| — | `identifiers` | 新增：多来源 ID 聚合 |
| — | `abstract` | 新增：支持全文检索 |
| — | `problem_statement` | 新增：领域无关问题描述 |
| — | `method_summary` | 新增：方法摘要 |
| — | `key_results` | 新增：关键结果 |
| — | `survey_count` | 新增：被引用次数 |
| — | `citation_count` | 新增：外部引用数 |
