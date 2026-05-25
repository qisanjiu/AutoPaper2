# AutoPaper2 Agent 模板改进建议报告

> **分析范围**: M1 (Domain Survey) + M2 (Method Design) 涉及的全部 Agent 模板
> **对比对象**: DeepScientist (system.md + skills)、ARIS (AGENT_GUIDE + skills)、PaperOrchestra (arXiv:2604.05018)、Autoresearch (ai-research-skills)、ResearchClaw
> **报告日期**: 2026-05-11

---

## 执行摘要

通过对 5 个外部项目的深度对标，AutoPaper2 的 Agent 模板在 **阶段划分清晰度**、**Critic 评分维度**、**回溯机制设计** 上已有良好基础，但在以下 6 个维度存在系统性差距：

| 差距维度 | 当前状态 | 对标水平 | 改进优先级 |
|---------|---------|---------|-----------|
| 1. 三层规划控制面 | 仅 pipeline_state.yaml | plan.md / PLAN.md / CHECKLIST.md | **P0** |
| 2. 跨模型对抗审查 | 单模型内 Critic | Executor-Reviewer 必须不同模型 | **P0** |
| 3. 实验执行纪律 | 建议性规范 | 强制性 bash_exec + 生命周期协议 | **P0** |
| 4. 文献引用验证 | Source Log 手工维护 | S2 API 验证 + Levenshtein + cutoff | **P1** |
| 5. Venue 分层检索 | 泛泛建议 | Tier A/B/C 硬性优先序 | **P1** |
| 6. Agent 交互协议 | 无统一规范 | artifact.interact 四类消息契约 | **P2** |

---

## 一、P0 改进（立即实施）

### 1.1 引入「三层规划控制面」协议

**现状问题**:
- AutoPaper2 仅依赖 `pipeline_state.yaml` 追踪当前 stage，缺乏项目级、节点级、执行级三层规划
- Agent 在上下文压缩后只能通过 Context Recovery 被动恢复，没有主动的规划锚点
- M1S02 的 3-Round 协议虽精细，但与其他 stage 的规划深度不一致

**对标**: DeepScientist `system.md:7.2A` 的三层控制栈

```
plan.md          → quest 级 Research Map（整个研究循环的全局状态）
PLAN.md          → node 级当前 stage 契约（目标、产出、成功/放弃条件）
CHECKLIST.md     → 执行级前沿（当前 In Progress、Next 3-5 项、阻塞项）
```

**改进方案**:

在每个项目的 `state/` 目录下新增三层规划文件，并在 **每个 Agent 的 AGENT.md 中强制要求**:

1. **进入 stage 前**: 读取/刷新最小相关规划层
   - 若整体路线改变 → 更新 `plan.md`
   - 若当前节点目标/成功条件改变 → 更新 `PLAN.md`
   - 若仅执行前沿改变 → 更新 `CHECKLIST.md`

2. **离开 stage 前**: 至少一层必须显式推进
   - 节点移动、被阻塞、或循环前进
   - 节点目标或契约被细化
   - 检查清单项完成、阻塞或取代

3. **M1 各 Stage 的三层映射示例**:

| Stage | plan.md 更新点 | PLAN.md 内容 | CHECKLIST.md 内容 |
|-------|---------------|-------------|------------------|
| M1S01 | 确认 M1 已启动 | 主题界定目标、范围边界、成功标准 | 关键词提取→子领域映射→里程碑确认 |
| M1S02 | Round 1→2→3 节点推进 | 当前 Round 目标、Reviewer 反馈、通过条件 | 搜索策略→文献筛选→Gap 提炼→Review 提交 |
| M1S03 | M1 进入 Ideation 阶段 | Pre-Idea Draft 目标、反对意见阈值、通过条件 | 最强反对意见收集→证伪路径设计→方向选择 |
| Gate G1 | M1 完成/回溯决策 | Critic 评审目标、通过阈值、回溯条件 | Coverage→Logic→Novelty 独立评审→综合 verdict |

**具体修改文件**:
- `docs/AGENTS/survey/AGENT.md` — 在 "3-Round 迭代搜索协议" 前插入三层规划要求
- `docs/AGENTS/ideation/AGENT.md` — 在 "Pre-Idea Draft 强制流程" 前插入节点契约要求
- `docs/AGENTS/critic/*/AGENT.md` — 审查前读取被审 stage 的 PLAN.md，审查后更新 CHECKLIST.md

---

### 1.2 建立「跨模型对抗审查」协议

**现状问题**:
- AutoPaper2 的 Critic（Coverage/Logic/Novelty/Method）由同一模型家族执行，缺乏真正的对抗性
- Survey Review Agent 与 Survey Agent 虽要求"独立"，但无强制模型隔离机制
- Gate 评审的 verdict 可信度完全依赖 prompt 设计，无外部验证

**对标**: ARIS `AGENT_GUIDE.md` 的 Cross-Model Protocol

```
Executor (Claude/Codex) : 写代码、跑实验、起草论文
Reviewer (GPT-5.4/Gemini/GLM) : 批判、评分、要求修改
Rule: executor 和 reviewer 必须是不同模型家族
Reviewer independence: 只传文件路径，从不传摘要或解释
Experiment integrity: executor 不得评判自己的 eval 代码
```

**改进方案**:

在 `docs/AGENTS/critic/` 下新增 `cross_model_protocol.md`:

```markdown
# Cross-Model Review Protocol

## 强制隔离规则
1. Survey Agent (M1S01-02) 与 Survey Review Agent **不得由同一模型实例执行**
2. Ideation Agent (M1S03-05) 与 Logic/Novelty Critic **不得由同一模型实例执行**
3. Method Agent (M2S01-05) 与 Method Critic (G2) **不得由同一模型实例执行**

## 信息传递规则
- Critic 的输入**只能是文件路径**，不能是 Executor 提供的摘要、解释或精选片段
- Critic 必须**独立读取**原始产出文件，自行提取证据
- Critic 的 verdict 必须基于**直接阅读**，而非 Executor 的转述

## 对抗升级机制
| 级别 | 条件 | 行为 |
|------|------|------|
| L1 (标准) | 首次评审 | 单轮评审，给出 PASS/REWORK/HALT |
| L2 (困难) | Round 2+ 或关键 Gate | 引入 Reviewer Memory（跨轮累积怀疑清单） |
| L3 (噩梦) | 高风险的 Novelty/Method 审查 | Reviewer 独立搜索文献验证 Executor 的声称 |

## 在 AutoPaper2 中的实施点
- M1S02 Round Review: Survey Review Agent 必须独立读取 M1S02_literature_deepdive.md 和 M1_source_log.yaml
- Gate G1: Coverage + Logic + Novelty 三个 Critic 应尽可能分配给不同模型实例
- Gate G2: Method Critic 应独立验证 M2S03 的伪代码与 M2S04 的实验设计
```

**具体修改文件**:
- 新增 `docs/AGENTS/critic/cross_model_protocol.md`
- 修改 `docs/AGENTS/critic/survey_review/AGENT.md` — 在 "5. Verdict 规则" 前插入跨模型隔离要求
- 修改 `docs/AGENTS/critic/novelty/AGENT.md` — 在 "5.1 主动搜索" 中强调 Reviewer 的独立搜索义务

---

### 1.3 强化「实验执行纪律」与工具强制规范

**现状问题**:
- Experiment Agent 的 AGENT.md 建议使用 git commit 保存实验，但**非强制**
- 未规定 shell 执行必须通过统一接口（如 bash_exec），Agent 可能直接调用本地 shell
- 长运行实验缺乏 detach/monitor/await 生命周期管理
- M3S02 的 "不做保留/回退决策" 是好的，但缺乏具体的证据记录格式

**对标**: DeepScientist `system.md:11.3` 的 bash_exec 纪律 + autoresearch 的 git 协议

**改进方案**:

在 `docs/AGENTS/experiment/AGENT.md` 中新增 "Hard Execution Redlines" 章节：

```markdown
## 0. 硬执行红线

- **所有终端类操作必须通过统一 shell 接口执行**。禁止直接调用 `ls`、`cat`、`python`、`git` 等本地 shell 命令。
- **每个实验尝试必须对应一个独立的 git commit**，格式：`experiment(iter{N}): {修改描述}`
- **Protocol commit 必须在 Result commit 之前**，证明计划先于结果存在
- **长运行实验必须使用 detach + monitor 模式**：
  ```
  1. detach 启动实验
  2. 通过 list/read 监控进度
  3. 通过 await 等待完成
  4. 超时或卡死时通过 kill 终止
  ```
- **禁止在 smoke test / pilot 成功后就停止**。smoke 只是路径验证，不是主证据。
```

同时，在 M1/M2 相关的 Method Agent 中也引入方法设计的版本控制要求：

```markdown
## 新增：方法设计版本控制

Method Agent 对 M2S01-M2S05 的每次重大修改必须：
1. 创建独立 git 分支 `method-design/{attempt-N}`
2. Commit 信息格式：`method(design): M2S0X — {决策摘要}`
3. 设计决策记录表中的每项决策必须能追溯到具体 commit
```

---

## 二、P1 改进（近期实施）

### 2.1 引入「文献引用验证」自动化流程

**现状问题**:
- AutoPaper2 的 Source Log (`M1_source_log.yaml`) 完全由 Survey Agent 手工维护
- 无自动验证机制检查：标题是否真实存在、作者是否匹配、venue 是否正确
- Gate G1 的 Coverage Critic 依赖人工判断 Source Log 与 Markdown 一致性
- 无引用截止时间（cutoff date）概念，可能导致引用投稿后发表的工作

**对标**: PaperOrchestra `literature-review-agent/SKILL.md` 的两阶段验证管道

```
Phase 1: Parallel Candidate Discovery (web search)
Phase 2: Sequential Citation Verification (Semantic Scholar API)
  - Levenshtein title ratio > 70
  - Year/venue alignment bonus
  - Abstract 非空检查
  - 严格早于 cutoff_date
  - Dedup by paperId
```

**改进方案**:

在 `docs/AGENTS/survey/AGENT.md` 的 "5. Source Log 规范" 后新增：

```markdown
## 5.1 Source Log 验证协议（新增）

每轮搜索完成后，必须对新增文献执行自动化验证：

### 验证流程
1. **标题验证**: 通过 Semantic Scholar API 搜索标题，Levenshtein ratio ≥ 70
2. **元数据对齐**: 验证作者、年份、venue 与搜索结果一致
3. **时效性检查**: 文献日期必须早于项目启动日期（或明确设定的 cutoff_date）
4. **去重**: 按 paperId 去重，避免同一文献多次记录

### 验证失败处理
| 失败类型 | 处理方式 |
|---------|---------|
| 标题匹配失败 | 标记为 `[UNVERIFIED]`，要求提供 DOI 或 arXiv ID |
| 元数据不一致 | 以 S2/DBLP 为准更新 Source Log |
| 晚于 cutoff | 标记为 `concurrent_work`，不纳入 Gap 证据链 |
| 重复条目 | 合并条目，保留最完整的元数据 |

### 工具集成
```python
# 伪代码：验证脚本（建议实现为 utils/source_verifier.py）
from spiral.public_db.query_cache import QueryCache

def verify_source(source_entry: dict) -> dict:
    result = s2_search(source_entry["title"])
    if levenshtein(source_entry["title"], result.title) < 0.7:
        return {"status": "FAILED", "reason": "title_mismatch"}
    if result.year > cutoff_year:
        return {"status": "CONCURRENT", "reason": "post_cutoff"}
    return {"status": "VERIFIED", "s2_id": result.paperId}
```
```

**同时修改**:
- `utils/source_log_validator.py` — 增加 S2 API 验证调用
- `spiral/public_db/query_cache.py` — 增加 Semantic Scholar 查询后端

---

### 2.2 引入「Venue 分层检索」策略

**现状问题**:
- Survey Agent 的 AGENT.md 建议 "覆盖 ≥3 个数据库"，但无 venue 优先级指导
- 无明确的 "top venue first" 策略，可能导致低质量文献混入 Source Log
- 通信领域特有的 venue（JSAC/TWC/ToN/SIGCOMM 等）未被明确标注

**对标**: ARIS `comm-lit-review/SKILL.md` 的 Tier A/B/C venue 分层

**改进方案**:

在 `docs/AGENTS/survey/AGENT.md` 的 "4. 3-Round 迭代搜索协议" 中新增：

```markdown
### 4.3 Venue 分层检索策略

#### Tier A（顶级）
- IEEE Journal on Selected Areas in Communications (JSAC)
- IEEE/ACM Transactions on Networking (ToN)
- IEEE Transactions on Wireless Communications (TWC)
- IEEE Transactions on Communications (TCOM)
- ACM SIGCOMM, USENIX NSDI, ACM MobiCom, IEEE INFOCOM

#### Tier B（高质量）
- IEEE Transactions on Vehicular Technology (TVT)
- IEEE Wireless Communications Letters (WCL)
- IEEE ICC, IEEE GLOBECOM, IEEE WCNC, ACM MobiHoc

#### Tier C（领域相关）
- 其他 IEEE Transactions
- Elsevier Computer Networks / Computer Communications
- 领域特化 venue（卫星、光通信、车载、IoT 等）

#### 检索规则
1. Round 1 广泛搜索时，优先覆盖 Tier A，再扩展至 Tier B
2. Round 2 定向搜索时，必须在 Tier A 中确认是否有相关工作
3. Round 3 盲区填补时，检查是否遗漏了 Tier A 的经典/奠基性工作
4. Source Log 中必须标注每篇文献的 venue tier
5. Tier A 文献占比低于 30% 时，Survey Review Agent 应标记为 Coverage 问题
```

---

### 2.3 增强「回溯机制」的 Agent 级处理指令

**现状问题**:
- AutoPaper2 的 `conductor.py` 实现了框架级回溯（stale 标记、spiral limit）
- 但各 Agent 的 AGENT.md 中**缺乏面对回溯时的具体操作指令**
- M1S02 的 3-Round REWORK 有详细处理，但跨 stage 回溯（如 M1S05→M1S02）无 Agent 级指导

**对标**: DeepScientist `system.md:7.5` 的 Downgrade and Abandonment Discipline

**改进方案**:

在每个 Agent 的 AGENT.md 中新增 "Backtrack Handling" 章节。

**Survey Agent 示例**:
```markdown
## 9. 回溯处理

### 从下游回溯到 M1S01/M1S02
当收到回溯指令时：
1. 读取 `state/backtrack_log` 确认回溯原因和方向
2. 若回溯到 M1S01：
   - 完全重新执行主题界定
   - 清空 survey_memory.yaml 中的 search_batches（或标记为 stale）
   - 保留 source_registry 但重新评估相关性
3. 若回溯到 M1S02：
   - 读取已通过审查的 Round 内容，选择性保留
   - 根据回溯原因确定从哪个 Round 重新开始
   - 若原因是 "Gap 证据不足" → 从 Round 2 重新开始定向搜索
   - 若原因是 "主题范围变更" → 从 Round 1 重新开始
4. 更新 `PLAN.md` 和 `CHECKLIST.md` 反映新的搜索计划
```

**Ideation Agent 示例**:
```markdown
## 10. 回溯处理

### 从 Gate G1 回溯到 M1S03/M1S04/M1S05
1. 读取 Gate 评审文件 (`knowledge/reviews/G1_*_review.md`)，提取具体修改要求
2. 若回溯到 M1S03：
   - 重新评估 Pre-Idea Draft 中的反对意见
   - 如果反对意见中有 ≥1 项为"高"，回到 M1S02 补充调研
3. 若回溯到 M1S04：
   - 保留 Gap-Question 映射，修正假设和零假设设计
4. 若回溯到 M1S05：
   - 重新评估新颖性声明和可行性判断
5. **Major Revision 判定**：
   - 修改核心 Gap/假设/方法方向 → 通知 Conductor 触发下游 M2+ 回溯
   - 仅修正措辞/补充文献 → 不触发下游回溯
```

---

## 三、P2 改进（中期实施）

### 3.1 引入「Agent 交互协议」

**现状问题**:
- AutoPaper2 无统一的 Agent 间通信协议
- Agent 通过文件系统隐式通信（写入 knowledge/，读取上一 stage 产出）
- 无显式的 "milestone"、"progress"、"decision_request" 消息分类

**对标**: DeepScientist `system.md:7.6` 的 artifact.interact 协议

**改进方案**:

在 `docs/07_MD_PROTOCOL.md`（或新建 `docs/AGENT_INTERACTION_PROTOCOL.md`）中定义：

```markdown
# AutoPaper2 Agent 交互协议

## 消息类型

### milestone
- 触发条件：材料性状态变化（如 Round 3 通过、Gate 通过、Handoff 完成）
- 行为：非阻塞，但应被 Conductor 记录到 spiral_log.md

### progress
- 触发条件：执行中的检查点、活跃工作摘要、恢复说明
- 行为：可去重抑制，避免重复更新

### decision_request
- 触发条件：真正阻塞的用户决策（如 Gate HALT、Spiral Limit 达到、ABANDON 判断）
- 行为：阻塞式，等待用户回复后才能继续

### answer
- 触发条件：直接回答用户问题
- 行为：默认使用，不隐藏在 progress 消息中

## 更新节奏
- 活跃工作期间：约 10 个有意义工具调用后发送 progress
- 硬上限：不超过约 20 个工具调用或 15 分钟无更新
- 长运行任务：不超过 1800 秒无状态检查
```

---

### 3.2 引入「Pre-Idea Draft」的自动化审查清单

**现状问题**:
- Ideation Agent 的 Pre-Idea Draft 有内容要求，但无自动化的通过/失败检查
- Survey Review Agent 对 Round 有明确的 PASS/REWORK/HALT verdict，但 Pre-Idea Draft 无等价机制

**对标**: DeepScientist `idea/SKILL.md` 的 "Pre-idea draft SOP" 和 "Selection Gate"

**改进方案**:

在 `docs/AGENTS/ideation/AGENT.md` 的 "4.3 Pre-Idea Draft 的审查规则" 中细化：

```markdown
### 4.3 Pre-Idea Draft 自动化审查清单

每个 Pre-Idea Draft 必须回答以下问题，任何一项为"否"则禁止进入正式 Research Question：

| 检查项 | 通过标准 | 失败处理 |
|--------|---------|---------|
| 反对意见充分性 | ≥2 条有意义的反对意见，其中 ≥1 条严重程度为"高" | 补充反对意见或调整方向 |
| 最接近工作差异 | 与最接近工作的差异必须实质性（非表面差异） | 明确声明 novelty type |
| 架构改进型瓶颈 | 如果是架构改进型，必须清晰说明"解决了什么具体瓶颈" | 回到 M1S02 深挖组件局限性 |
| 证伪路径可执行 | 必须设计至少 1 个可执行的证伪实验 | 补充证伪路径 |
| Plan B 存在性 | 必须有至少 1 个明确的 Plan B | 补充备选方案 |
| 非装饰性改动 | 必须明确区分本研究不属于"参数调优/简单组合/场景应用" | 重新定位创新类型 |

### Pre-Idea Draft 审查 Agent（新增角色）
- 在 M1S03 正式产出前，Conductor 可调用独立的 Pre-Idea Review Agent
- Review Agent 读取 `drafts/M1S03/pre_idea_draft.md`，逐项检查上述清单
- Verdict: PASS → 进入 M1S03 正式产出；REWORK → Ideation Agent 修正；HALT → 回到 M1S02
```

---

### 3.3 统一「Context Recovery」为「状态重建协议」

**现状问题**:
- 每个 Agent 的 AGENT.md 都有独立的 Context Recovery 章节，内容高度重复
- 缺乏项目级别的统一恢复入口
- 未明确区分 "上下文压缩后的被动恢复" 和 "session 中断后的主动重建"

**对标**: DeepScientist `system.md:10` 的 Truth Sources 层级

**改进方案**:

新建 `docs/CONTEXT_RECOVERY_PROTOCOL.md`，替换各 Agent 中的独立章节：

```markdown
# AutoPaper2 状态重建协议

## 触发条件
- 上下文压缩（context compaction）
- Session 中断后恢复
- Agent 切换（如从 Survey 切换到 Ideation）

## 重建顺序（严格按优先级）

### Layer 1: 运行时状态（最高优先级）
1. `state/pipeline_state.yaml` — 当前 stage、status、stale_stages
2. `state/survey_memory.yaml` — M1S02 的搜索状态（仅限 M1）
3. `state/decision_log.md` — 最近的决策记录

### Layer 2: 当前节点契约
4. 当前 stage 的 `PLAN.md`（如存在）
5. 当前 stage 的 `CHECKLIST.md`（如存在）
6. 当前 stage 的 `AGENT.md` — 恢复角色定义和工作规范

### Layer 3: 上游输入
7. 上一 stage 的产出文件（按 conductor.py 的 get_stage_input_docs 规则）
8. Handoff 文件（如 handoff_M1_M2.md）

### Layer 4: 历史记录
9. `state/spiral_log.md` — 螺旋日志
10. `knowledge/reviews/` — 最近的评审文件

## 重建验证
重建完成后，Agent 必须输出一句确认：
"状态重建完成。当前在 [stage]，状态为 [status]，正在执行 [CHECKLIST.md 中的当前项]。"

若无法完成重建，必须显式声明缺失的 layer 和 blocker。
```

然后各 Agent 的 AGENT.md 简化为：
```markdown
## Context Recovery
遵循 `docs/CONTEXT_RECOVERY_PROTOCOL.md`，重建后确认当前 stage 和 CHECKLIST 状态。
```

---

## 四、具体文件修改清单

### 新增文件
| 文件路径 | 说明 |
|---------|------|
| `docs/AGENTS/critic/cross_model_protocol.md` | 跨模型对抗审查协议 |
| `docs/CONTEXT_RECOVERY_PROTOCOL.md` | 统一状态重建协议 |
| `docs/AGENT_INTERACTION_PROTOCOL.md` | Agent 交互消息类型与节奏（P2） |
| `utils/source_verifier.py` | S2 API 文献验证工具（P1） |

### 修改文件（P0）
| 文件路径 | 修改内容 |
|---------|---------|
| `docs/AGENTS/survey/AGENT.md` | 插入三层规划要求、venue 分层、回溯处理 |
| `docs/AGENTS/ideation/AGENT.md` | 插入三层规划、Pre-Idea 自动审查、回溯处理 |
| `docs/AGENTS/experiment/AGENT.md` | 插入硬执行红线、git 协议、detach 生命周期 |
| `docs/AGENTS/method/AGENT.md` | 插入方法设计版本控制、三层规划 |
| `docs/AGENTS/critic/survey_review/AGENT.md` | 插入跨模型隔离要求 |
| `docs/AGENTS/critic/novelty/AGENT.md` | 插入独立搜索义务、Reviewer Memory |
| `docs/AGENTS/critic/method/AGENT.md` | 插入跨模型隔离、独立代码验证 |

### 修改文件（P1）
| 文件路径 | 修改内容 |
|---------|---------|
| `utils/source_log_validator.py` | 集成 S2 API 验证 |
| `spiral/public_db/query_cache.py` | 增加 S2 后端 |
| `skills/AutoPaper2_m1_survey/SKILL.md` | 同步 Survey Agent 改进 |
| `skills/AutoPaper2_m2_method_design/SKILL.md` | 同步 Method Agent 改进 |

---

## 五、实施路线图

```
Week 1 (P0 核心)
  ├── 新增 cross_model_protocol.md
  ├── 新增 CONTEXT_RECOVERY_PROTOCOL.md
  ├── 修改 survey/AGENT.md (三层规划 + venue 分层 + 回溯)
  ├── 修改 ideation/AGENT.md (三层规划 + Pre-Idea 审查 + 回溯)
  ├── 修改 experiment/AGENT.md (硬执行红线)
  └── 修改 critic/*/AGENT.md (跨模型隔离)

Week 2 (P0 扩展 + P1 启动)
  ├── 修改 method/AGENT.md (方法版本控制)
  ├── 实现 utils/source_verifier.py
  ├── 修改 source_log_validator.py (集成验证)
  └── 修改 public_db/query_cache.py (S2 后端)

Week 3 (P1 完成 + P2 启动)
  ├── 修改 SKILL.md 文件同步改进
  ├── 新增 AGENT_INTERACTION_PROTOCOL.md
  ├── 实现 Pre-Idea Review Agent 模板
  └── 端到端测试 M1 回溯场景

Week 4 (验证)
  ├── 运行 test_m1_e2e.py 验证改进
  ├── 运行 test_m2_integration.py 验证改进
  └── 输出回归测试报告
```

---

## 附录：对标项目关键设计亮点速查

### DeepScientist
- **system.md**: 1290 行的紧凑全局内核，硬红线、三层规划、artifact 交互协议、bash_exec 纪律
- **idea/SKILL.md**: 1499 行的深度 ideation 指南，Pre-Idea Draft SOP、创意发散协议、16 种 ideation lens
- **experiment/SKILL.md**: 268 行，证据阶梯（minimum/solid/maximum）、失败分类、接受门

### ARIS
- **AGENT_GUIDE.md**: 136 行路由索引，参数化 skill 调用（effort/difficulty/venue）
- **auto-review-loop/SKILL.md**: 457 行，三级对抗难度（medium/hard/nightmare）、Reviewer Memory + Debate Protocol
- **comm-lit-review/SKILL.md**: 297 行，venue Tier A/B/C、Zotero→Obsidian→local→IEEE 分层检索

### PaperOrchestra
- **literature-review-agent/SKILL.md**: 356 行，两阶段验证管道、Levenshtein >70、cutoff date、≥90% citation coverage gate
- **paper-orchestra/SKILL.md**: 240 行，五步并行管道、Anti-Leakage Prompt、确定性 gates

### Autoresearch
- **SKILL.md**: 411 行，双循环架构（Inner/Outer Loop）、Agent Continuity（/loop 20m）、Git 预注册协议
