# M3 Module Design — Experiment Implementation & Execution（实验实现与执行）

> **版本**: v0.1-draft
> **状态**: 蓝图阶段
> **对应旧版**: AutoPaper Phase 3 (S11-S15 实验执行段)
> **对应DeepScientist**: `baseline` + `experiment` + `decision` skills 的执行段
> **设计原则**: M2 产出"蓝图"，M3 负责"按图施工、留痕取证、诚实报告"

---

## 1. 设计目标

M3 的核心使命是：**忠实实现 M2 设计的方法论，在受控的实验环境中产生可信、可比较、可复现的经验证据，并对证据质量进行诚实的初步判定。**

**关键认知修正**（⚠️ 重要）：
- M3 **不重新设计方法**——方法设计的权力属于 M2，M3 只有"忠实实现"和"发现实现偏差后反馈"的权力
- M3 **不做深度解读**——结果深层解释的权力属于 M4 (Analysis)，M3 只负责"验证数据质量、统计显著性、是否达到成功标准"
- M3 **必须诚实**——如果实验结果不支持 M2 的假设，M3 的职责是**明确标记**，而非为了"推进流程"而隐瞒

与 DeepScientist 的区别：
- DeepScientist 的 `experiment` skill 将 baseline 验证、主实验、分析 campaign 混在同一个 skill 中
- AutoPaper2 将 baseline 验证严格放在 **M3S02**，主实验放在 **M3S03**，深度分析放在 **M4**
- M3 的核心是**证据生产与质量门控**，而非"结果解读"

---

## 2. Stage 架构 (4 Stages + 1 Gate)

> **架构变更说明**: 原设计为 3 Stage (M3S01-S03)。现扩展为 **4 Stage**，将 Baseline Lock 从 M3S01 中拆分为独立 Stage M3S02。理由见 §12 决策 1。

```
M3S01: Dataset & Environment Review / Setup [Experiment Agent]  → knowledge/M3/M3S01_implementation.md
M3S02: Baseline Result Review               [Experiment Agent]  → knowledge/M3/M3S02_baseline_lock.md
M3S03: Main Experiment Result Review        [Experiment Agent]  → knowledge/M3/M3S03_main_experiment.md
M3S04: Result Validation & Evidence Pack   [Analysis Agent]    → knowledge/M3/M3S04_result_validation.md
        └── Gate G3 [Method + Evidence Critic] ──►
Handoff M3→M4                              [Conductor]         → knowledge/handoff_M3_M4.md
```

### 2.1 与旧版 AutoPaper 的映射

| AutoPaper2 M3 | 旧版 AutoPaper S-Stage | 核心差异 |
|---------------|------------------------|---------|
| M3S01 | S11 Code Generation | 新增环境搭建、依赖锁定、可复现清单 |
| M3S02 | — (新增) | 从原 S11/S12 拆出的基线验证阶段；汲取 DeepScientist `baseline` skill 的 comparator-first 原则 |
| M3S03 | S12-S14 合并 | 主实验迭代循环；新增 Evidence Ladder 概念 |
| M3S04 | S15 前半 | 结果验证从"简单报告"升级为"统计检验 + 数据质量审查 + 诚实决策" |

### 2.2 各 Stage 一句话定义

| Stage | 一句话定义 | 成功标准 |
|-------|-----------|---------|
| M3S01 | 审查并锁定数据集、执行环境、依赖和运行配置，同时完成方法代码落地 | 数据集与环境可复现，代码可运行 |
| M3S02 | 审查 baseline 本地运行结果，锁定比较基准并运行 smoke test | baseline contract 完整，smoke test 通过 |
| M3S03 | 审查主实验结果是否超过 baseline，并记录迭代证据 | 主结果可比较，达到 minimum/solid |
| M3S04 | 对实验结果进行统计验证、质量审查，并做出 KEEP/FIX/BACKTRACK 决策 | 决策明确、证据链完整、可追溯 |

---

## 3. 各 Stage 详细设计

### M3S01: Dataset & Environment Review / Setup

**目标**: 忠实实现 M2 设计的方法，搭建可复现的实验环境。

**输入**:
- `knowledge/handoff_M2_M3.md` (核心方法概述、架构、算法)
- `knowledge/M2/M2S03_method_architecture.md` (组件设计和接口)
- `knowledge/M2/M2S04_algorithm_theory.md` (伪代码和复杂度分析)
- `knowledge/M2/M2S05_experiment_setup.md` (数据集、预处理、超参数)

**关键约束**:
> - 代码实现必须**忠实于 M2S03/M2S04 的设计**，任何偏差必须在产出中记录并说明理由
> - 环境依赖必须**版本锁定**（requirements.txt / conda-lock / uv.lock）
> - 随机种子策略必须**从本阶段开始执行**（不是等到 M3S03）

**输出**: `knowledge/M3/M3S01_implementation.md` + `experiments/src/*.py` + `experiments/configs/*.yaml` + `experiments/requirements.lock`

**质量标准**:
- [ ] 所有 M2S03 中的组件都有对应代码实现
- [ ] 伪代码与代码实现一一对应（或明确记录偏差及理由）
- [ ] 环境依赖已锁定，可在干净环境中重建
- [ ] 有 README 说明如何运行代码
- [ ] 随机种子已固定且记录
- [ ] 代码通过静态检查（无语法错误，可导入）

**可回溯原因**:
- 发现 M2 的设计在实现层面不可行 → BACKTRACK → M2S03 或 M2S04
- 实现复杂度远超预期 → BACKTRACK → M2S03（简化架构）

---

### M3S02: Baseline Result Review

**目标**: 验证基线可复现，锁定比较基准，确保实验管道无基本错误。

**输入**:
- `knowledge/M3/M3S01_implementation.md` (代码结构)
- `knowledge/M2/M2S05_experiment_setup.md` (baseline 列表、代码可用性)
- `knowledge/M1/M1S02_literature_deepdive.md` (baseline 原始指标)

**关键约束**:
> - **Comparator-first 原则**（汲取 DeepScientist `baseline` skill）：优先 attach/import/verify-local-existing，而非完整从头复现
> - Baseline **必须本地运行验证**，不可直接引用论文报告值
> - Smoke test 必须在主实验前运行，验证"管道通水"

**核心任务**:

**Step 1: Baseline 复现/验证**

对每个 baseline，按以下路径（从轻到重）选择验证策略：

| 路径 | 适用条件 | 验证标准 |
|------|---------|---------|
| `attach` | 官方代码已本地存在且之前验证过 | 读取 metric contract，确认未过期 |
| `import` | 官方 pip/conda 包可用 | 安装并运行官方示例，记录输出 |
| `verify-local-existing` | 项目中已有 baseline 实现 | 运行并验证指标与之前记录一致 |
| `reproduce` | 需从论文/官方 repo 自行实现 | 完整复现，记录偏差 |
| `repair` | 官方代码有 bug 不可运行 | 修复 bounded bug，记录修改 |

**Step 1.5: Checkpoint（预训练权重）获取**

> 绝大多数深度学习 baseline 依赖预训练权重。**Agent 必须主动搜索 checkpoint，禁止跳过。**

Checkpoint 搜索优先级：
1. GitHub Releases / Assets
2. README / 文档中的 Model Zoo / Pretrained Models 链接
3. 代码中的自动下载逻辑（torch.hub、transformers、wget 脚本）
4. 第三方平台：Hugging Face Hub、ModelScope、PyTorch Hub
5. 其他项目缓存复用
6. 以上均失败 → 生成报告阻塞等待用户协助

Metric Contract 必须包含 checkpoint 字段：source_url、local_path、checksum、verified_loadable。

**Step 2: Metric Contract 锁定**

为每个验证通过的 baseline，生成 metric contract：
```yaml
baseline_id: "baseline_x"
source: "论文X / 官方代码 / 自行实现"
dataset: "..."
split: "..."
metrics:
  primary:
    key: "accuracy"
    value: 0.834
    direction: "higher_is_better"
  secondary:
    - key: "f1"
      value: 0.821
environment:
  python: "3.10.12"
  torch: "2.1.0"
  cuda: "12.1"
  hardware: "RTX 4090"
known_deviations: "..."
verification_verdict: "verified_match / verified_close / trusted_with_caveats"
```

**Step 3: Smoke Test**

- 用最小的数据子集（如 1% 数据）或最少的 epoch（如 2 epoch）运行完整管道
- 验证：loss 下降、无 NaN/Inf、指标计算正确、保存/加载正常

**输出**: `knowledge/M3/M3S02_baseline_lock.md` + `experiments/baselines/*/metric_contract.yaml`

**质量标准**:
- [ ] 至少 1 个主要 baseline 已验证并锁定 metric contract
- [ ] 所有 baseline 指标有本地运行证据，非论文复制值
- [ ] **Checkpoint 已获取并验证可加载（如 baseline 依赖预训练权重）**
- [ ] Smoke test 通过，记录通过标准和实际结果
- [ ] 验证分级明确（verified_match / verified_close / trusted_with_caveats / diverged）
- [ ] 环境快照完整（命令、配置、种子、硬件）

**可回溯原因**:
- Baseline 无法复现且无法修复 → BACKTRACK → M2S05（更换 baseline）
- 所有 baseline 指标远低于论文报告 → 检查环境/实现 → 必要时 BACKTRACK → M3S01
- Smoke test 发现方法设计有根本实现障碍 → BACKTRACK → M2S03

---

### M3S03: Main Experiment Result Review

**目标**: 在受控条件下执行主实验，产生可信的主结果。

**输入**:
- `knowledge/M3/M3S02_baseline_lock.md` (已验证的 baseline 和 metric contract)
- `knowledge/M2/M2S06_full_experiment_plan.md` (实验计划；旧项目可使用 `M2S05_full_experiment_plan.md` 作为等价输入)
- `knowledge/M3/M3S01_implementation.md` (代码实现)

**关键约束**:
> - **Run Contract 锁定**（汲取 DeepScientist `experiment` skill）：在开始主实验前，必须明确记录研究问题、基线参考、数据集/划分、指标键、停止条件、放弃条件、预期输出
> - **Baseline 只读原则**：baseline 代码在本次 Stage 中不得修改（如需修复应在 M3S02 完成）
> - **Evidence Ladder**（汲取 DeepScientist）：明确区分 minimum / solid / maximum 证据目标，不在 minimum 达标前追求 maximum

**核心任务**:

**Step 1: Run Contract 锁定**

```markdown
# Run Contract — Main Experiment

## 研究问题
[来自 M1S03]

## 核心假设
[来自 M1S04]

## 方法干预
[本文方法与 baseline 的关键差异，来自 M2S03]

## 比较基准
[引用 M3S02 锁定的 baseline metric contract]

## 数据集与划分
[来自 M2S05]

## 指标键与方向
[primary/secondary 指标]

## 停止条件
- 预算：X GPU-hours
- 迭代：最多 N 轮
- 收敛：连续 3 轮无显著改善（< 1% 相对提升）
- 放弃：如果 smoke test 级别结果连续 2 轮低于 baseline

## 预期输出
- 主实验结果表
- 与 baseline 的对比表
- 训练曲线
- 环境快照
```

**Step 2: 实验迭代循环**

```
Setup Phase:
    1. 创建独立 git 分支 `exp/main`
    2. 初始化 experiments/results.tsv
    3. 记录 M3S02 baseline 结果作为参考

Iteration Loop:
    1. 提出一个实验性修改（基于 M2 设计，或诊断性调整）
    2. git commit -m "exp(iterN): {修改描述}"
    3. 运行完整配置实验
    4. 提取关键指标，与 baseline 和上次最优结果对比
    5. 记录结果到 results.tsv
    6. 如果达到收敛条件或预算上限，退出循环
```

**Step 3: Evidence Ladder 推进**

| 层级 | 目标 | 判定标准 | 后续动作 |
|------|------|---------|---------|
| **minimum** | 可执行、可比较 | 代码运行完成，指标可计算，与 baseline 可比 | 继续推进到 solid |
| **solid** | 足以支撑主声明 | 主指标显著优于 baseline（统计显著 + 实际意义） | 可进入 M3S04 |
| **maximum** | 全面抛光 | 多 seed、多数据集、完整曲线、消融预留 | 留给 M4/M5，不在 M3 追求 |

**输出**: `knowledge/M3/M3S03_main_experiment.md` + `experiments/results.tsv` + `experiments/runs/<run_id>/`

**质量标准**:
- [ ] Run Contract 已锁定并记录
- [ ] 每次迭代都有 git commit 和 results.tsv 记录
- [ ] 主指标与 baseline 的比较基于本地运行结果
- [ ] 随机种子已固定，多 seed 实验已运行（至少 3 个）
- [ ] 训练曲线、日志已保存
- [ ] 环境快照完整
- [ ] 达到 minimum 证据层级；若未达到，明确记录失败原因

**可回溯原因**:
- 方法实现有 bug 导致结果异常 → BACKTRACK → M3S01
- 超参数设置导致训练不稳定 → FIX → M3S03（调整超参）
- 方法在合理实现下仍无法超过 baseline → BACKTRACK → M2S03（重新设计方法）或 M1S04（修正假设）

---

### M3S04: Result Validation & Evidence Packaging

**目标**: 对实验结果进行统计验证、数据质量审查，做出 KEEP/FIX/BACKTRACK 决策，并将证据打包供下游使用。

**输入**:
- `knowledge/M3/M3S03_main_experiment.md` (实验迭代记录)
- `knowledge/M3/M3S02_baseline_lock.md` (baseline metric contract)
- `experiments/results.tsv` (原始结果)
- `knowledge/M1/M1S04_hypothesis_generation.md` (核心假设)

**关键约束**:
> - **KEEP 是唯一的"通过"决策**。如果结果不支持假设，必须选择 FIX 或 BACKTRACK，不得为了推进而隐瞒
> - **统计显著性 ≠ 实际重要性**：必须报告效应量，不能只看 p-value
> - **负面结果也是结果**：如果假设被否定，应诚实记录并分析原因

**核心任务**:

**Step 1: 数据质量检查**
- 过拟合检查：train/val gap，学习曲线分析
- 数据泄露检查：预处理管道隔离性
- 训练稳定性检查：loss 曲线，NaN/Inf，梯度爆炸/消失
- 可复现性检查：同 seed 重新运行一次，验证结果一致

**Step 2: 统计显著性检验**
- 选择适当的检验方法（t-test、Wilcoxon、Bootstrap 等）
- 报告 p-value、置信区间、效应量（Cohen's d 等）
- 如有多重比较，进行校正（Bonferroni、FDR）

**Step 3: 与假设的对应验证**
- 每个核心假设是否得到支持？
- 哪些假设被否定？可能的原因是什么？

**Step 4: 决策**

| 决策 | 条件 | 后续动作 |
|------|------|---------|
| **KEEP** | 结果支持核心假设，统计显著，质量无重大问题 | 进入 Gate G3 |
| **FIX** | 结果有潜力但存在可修复的问题（如超参未调好、某组件有 bug） | 回溯到 M3S03 或 M3S01 |
| **BACKTRACK** | 结果根本不支持假设，或方法有明显缺陷 | 回溯到 M2S03（重新设计）或 M1S04（修正假设） |

**Step 5: Evidence Artifact 打包**

将主实验证据打包为标准化 artifact：
```
experiments/artifacts/main_experiment/
├── manifest.yaml          # 实验元数据
├── metric_contract.yaml   # 本文方法的 metric contract
├── comparison_table.csv   # 与 baseline 的对比
├── training_curves/       # 训练曲线图
├── logs/                  # 运行日志
├── configs/               # 配置文件
└── reproduction.md        # 复现指南
```

**输出**: `knowledge/M3/M3S04_result_validation.md` + `experiments/artifacts/main_experiment/`

**质量标准**:
- [ ] 数据质量检查清单已完成
- [ ] 统计检验方法和结果已记录
- [ ] 效应量已报告
- [ ] 决策明确（KEEP/FIX/BACKTRACK）
- [ ] 若为 FIX/BACKTRACK，已产出「回溯修改方向」章节，并写明 `target_stage` / `blocking_reason` / `required_fix` / `success_criteria` / `evidence_paths` / `rebuild_mode` / `rerun_scope` / `handoff_updates`
- [ ] Evidence Artifact 已打包，包含复现所需全部信息
- [ ] 负面结果（如有）已诚实记录

**可回溯原因**:
- 结果质量有重大问题 → FIX → M3S03 或 M3S01
- 结果不支持核心假设 → BACKTRACK → M2S03 或 M1S04
- 统计不显著但趋势明显 → FIX → M3S03（增加实验规模）

---

## 4. Gate G3 设计

### 4.1 审查维度

| Critic | 审查重点 | 通过标准 |
|--------|---------|---------|
| **Method** | 代码实现是否忠实于 M2 的方法设计？算法实现是否正确？ | 实现与设计文档一致，无重大偏差 |
| **Evidence** | 实验证据是否可信、充分、可比较？统计检验是否恰当？ | 证据达到 solid 层级，统计显著，可复现 |

### 4.2 与 G1/G2 的关键差异

| | Gate G1 (M1) | Gate G2 (M2) | Gate G3 (M3) |
|--|-------------|--------------|--------------|
| Critic | Coverage + Logic + Novelty | Logic + Method + Novelty | Method + Evidence |
| 审查对象 | 调研质量、问题定义 | 方法设计严谨性 | **实现忠实度、证据可信度** |
| 核心问题 | "问题值得研究吗？" | "方法能回答这个问题吗？" | **"证据真的支持这个方法吗？"** |

### 4.3 Evidence Critic 特殊审查项

```markdown
## Evidence Assessment

### 1. 可信性 (Trustworthiness)
- [ ] 所有指标来自本地运行，非论文复制值
- [ ] 随机种子已固定，多 seed 结果一致
- [ ] 无数据泄露迹象
- [ ] 训练曲线正常，无 NaN/Inf/梯度异常

### 2. 可比性 (Comparability)
- [ ] Baseline 与本文方法使用相同数据集/划分
- [ ] 评估指标定义一致
- [ ] 超参数选择策略公平（如都用网格搜索或都用默认值）
- [ ] 环境差异已记录

### 3. 统计严谨性 (Statistical Rigor)
- [ ] 使用了适当的显著性检验
- [ ] 报告了效应量，不只是 p-value
- [ ] 样本量足够（seed 数 ≥ 3 或统计检验力足够）
- [ ] 未进行 p-hacking（多重比较已校正）

### 4. 证据层级 (Evidence Ladder)
- [ ] 至少达到 minimum（可执行、可比较）
- [ ] 是否达到 solid（足以支撑主声明）？
- [ ] 未达到 solid 的原因是否已解释？

### 5. 诚实性检查 (Honesty)
- [ ] 负面结果是否被报告？
- [ ] 结果不显著时是否声称"优于"？
- [ ] 是否过度解读相关性为因果性？
```

### 4.4 verdict 规则

- **PASS**: Method ≥ 7/10 AND Evidence ≥ 7/10，无 BACKTRACK 意见
- **REVISE**: 某 Critic 发现问题但可在当前模块内修复 → 回溯到指定 M3 Stage
- **BACKTRACK**: 根本性问题 → 回溯到 M2（方法设计）或 M1（假设）
- **HALT**: 无法继续 → 终止，需人工介入

---

## 5. Handoff 文档

### 5.1 M2→M3 Handoff (输入)

由 M2 产出，M3 读取。格式见 `docs/design/M2_MODULE_DESIGN.md` §5.2。

### 5.2 M3→M4 Handoff (输出)

由 M3 产出，M4 读取：

```markdown
# Handoff: M3 → M4

## 已完成的工作摘要
- 实现了核心方法代码（M3S01）
- 验证了 baseline 并锁定 metric contract（M3S02）
- 执行了主实验迭代循环（M3S03）
- 完成了结果验证与证据打包（M3S04）
- Gate G3 判决: [PASS / 经过 REVISE 后 PASS]

## 关键决策记录
- 实现框架选择: PyTorch/TensorFlow/JAX，原因: ...
- Baseline 验证路径: attach/import/reproduce/repair，原因: ...
- 最终实验配置: ...
- M3S04 决策: KEEP，理由: ...

## 传递给 M4 的核心信息
- **主实验结果摘要**: ...（1-2 句话）
- **核心假设验证状态**: H1 [支持/部分支持/否定], H2 [...]
- **统计显著性**: 主指标 p-value = ..., 效应量 = ...
- **Evidence Artifact 路径**: `experiments/artifacts/main_experiment/`
- **Baseline Metric Contract 路径**: `experiments/baselines/*/metric_contract.yaml`
- **关键发现**:
  - 预期内的发现: ...
  - 意外发现: ...
  - 负面发现: ...
- **已知限制**:
  - 只在数据集 X 上验证
  - 超参未充分调优
  - ...
- **建议的 M4 分析方向**:
  - 消融实验建议: ...
  - 鲁棒性检查建议: ...
  - 机制验证建议: ...

## 回溯历史
- M3 经历了 N 次回溯（如有）
- 最后一次回溯原因: ...
```

---

## 6. Skill 设计: AutoPaper2_m3_experiment

### 6.1 触发条件

- 用户说 "进入 M3"
- 用户说 "开始实验"
- 用户说 "运行实验"
- M2 完成后自动建议进入 M3

### 6.2 控制工作流

```
Phase 0: 进入 M3 前置检查
  → 检查 M2 状态是否为 completed
  → 读取 handoff_M2_M3.md
  → 检查 M2 产出完整性
  → 加载 AGENT.md: docs/AGENTS/experiment/AGENT.md
  → 设置 pipeline_state: M3S01 in_progress

Phase 1: M3S01 Dataset & Environment Review / Setup
  → Experiment Agent 执行
  → 产出: knowledge/M3/M3S01_implementation.md + 代码文件 + 数据集/环境记录
  → Stage Review: m3_dataset_env_review
  → Review 输出: knowledge/reviews/M3S01_dataset_env_review.md
  → 仅当 Verdict=PASS 时，Conductor 才能推进
  → Conductor advance: M3S01 → M3S02

Phase 2: M3S02 Baseline Result Review
  → Experiment Agent 执行
  → 产出: knowledge/M3/M3S02_baseline_lock.md + baseline metric contracts
  → Stage Review: m3_baseline_result_review
  → Review 输出: knowledge/reviews/M3S02_baseline_result_review.md
  → 仅当 Verdict=PASS 时，Conductor 才能推进
  → Conductor advance: M3S02 → M3S03

Phase 3: M3S03 Main Experiment Result Review
  → Experiment Agent 执行
  → 产出: knowledge/M3/M3S03_main_experiment.md + experiments/results.tsv
  → Stage Review: m3_main_result_review
  → Review 输出: knowledge/reviews/M3S03_main_result_review.md
  → 仅当 Verdict=PASS 时，Conductor 才能推进
  → Conductor advance: M3S03 → M3S04

Phase 4: M3S04 Result Validation & Evidence Packaging
  → Analysis Agent 执行
  → 产出: knowledge/M3/M3S04_result_validation.md
  → Conductor advance: M3S04 → Gate G3

Phase 5: Gate G3 审查
  → Method Critic 审查 → G3_method_review.md
  → Evidence Critic 审查 → G3_evidence_review.md
  → 综合 verdict:
     → 全部 PASS → 进入 Handoff
     → 任一 REVISE → 回溯到指定 M3 Stage
     → 任一 BACKTRACK → 回溯到 M2 或 M1
     → 任一 HALT → 终止 M3

Phase 6: Handoff & 完成
  → 产出: knowledge/handoff_M3_M4.md
  → 标记 M3 模块 completed
  → 报告完成状态，建议下一步（进入 M4）
```

### 6.3 Agent 调用规范

**Experiment Agent**:
- 使用 subagent 执行
- Prompt 必须包含：
  - 完整读取 `docs/AGENTS/experiment/AGENT.md`
  - 当前 stage（M3S01-M3S03）
  - 上游输入文档路径
  - 产出路径
- 工具集: ReadFile, WriteFile, Shell, WebSearch
- Stage Review 由独立 reviewer subagent 执行，Experiment Agent 不兼任 reviewer

**Analysis Agent** (M3S04):
- 使用 subagent 执行
- Prompt 必须包含：
  - 完整读取 `docs/AGENTS/analysis/AGENT.md`
  - 上游输入文档路径
  - 产出路径
- 工具集: ReadFile, WriteFile, Shell
- M3S04 不负责 Stage Review

**Stage Review Agents**:
- M3S01 reviewer: `docs/AGENTS/critic/m3_dataset_env_review/AGENT.md` → `knowledge/reviews/M3S01_dataset_env_review.md`
- M3S02 reviewer: `docs/AGENTS/critic/m3_baseline_result_review/AGENT.md` → `knowledge/reviews/M3S02_baseline_result_review.md`
- M3S03 reviewer: `docs/AGENTS/critic/m3_main_result_review/AGENT.md` → `knowledge/reviews/M3S03_main_result_review.md`

**Stage Review rule**:
- Reviewer 必须独立读取原始文件路径，不得依赖 Executor 摘要
- Reviewer 必须写出显式 `Verdict: PASS`
- 非 PASS verdict 必须触发回溯或重跑，不能直接推进

**Gate G3 Critics** (并行执行):
- Method Critic: 读取 `docs/AGENTS/critic/method/AGENT.md`（复用 G2，审查对象更新为代码实现）
- Evidence Critic: 读取 `docs/AGENTS/critic/evidence/AGENT.md`（新增）

---

## 7. 状态管理

### 7.1 pipeline_state.yaml 更新

```yaml
current:
  module: M3
  stage: M3S01  # → M3S02 → M3S03 → M3S04 → G3
  status: in_progress

modules:
  M3:
    status: in_progress
    completed_at: null
    last_stage: null

history:
  - stage: M3S01
    agent: experiment
    completed_at: "..."
    output: "knowledge/M3/M3S01_implementation.md"
```

### 7.2 螺旋计数

```yaml
spiral_count:
  M1: 1
  M2: 1
  M3: 1  # 每次回溯到 M3 时 +1，上限 10
```

---

## 8. 质量门控

| 节点 | 检查项 | 失败处理 |
|------|--------|---------|
| M3S01 完成后 | **数据集真实可用（绝对禁止仿真/合成数据替代）**、环境配置可审查、代码可运行、环境可重建 | 要求修复，仍失败则 BACKTRACK → M2S03 |
| M3S02 完成后 | baseline 本地结果已审查、至少 1 个 baseline contract 可用、smoke test 通过 | BACKTRACK → M3S01 |
| M3S03 完成后 | results.tsv 完整、主实验结果可比较、达到 minimum 证据 | 要求补充 |
| M3S04 完成后 | 决策明确（KEEP/FIX/BACKTRACK）、统计检验恰当 | 若为 FIX 则回溯，若为 BACKTRACK 则执行 |
| Gate G3 | Method ≥7.0 AND Evidence ≥7.0 | BACKTRACK 或 REVISE |
| Handoff 前 | 所有 M3 产出文件和 artifact 存在 | 阻止完成 |

---

## 9. 回溯策略

### 9.1 M3 模块内回溯

```
M3S04 发现问题
  ├── 统计检验不显著但趋势好 → FIX → M3S03（增加 seed/数据）
  ├── 数据质量问题（泄露、不稳定）→ FIX → M3S03 或 M3S01
  ├── 超参数未调好 → FIX → M3S03
  ├── 实现有 bug → BACKTRACK → M3S01
  ├── 方法实现忠实但效果不达预期 → BACKTRACK → M2S03（重新设计）
  └── 效果不达预期且与假设矛盾 → BACKTRACK → M1S04（修正假设）

M3S03 发现训练异常
  ├── 环境/依赖问题 → FIX → M3S01
  ├── 代码 bug → BACKTRACK → M3S01
  └── 方法设计导致训练不稳定 → BACKTRACK → M2S03

M3S02 发现 baseline 无法复现
  ├── 环境差异 → FIX → M3S01
  ├── 官方代码有 bug → repair baseline
  └── 官方方法本身不可复现 → BACKTRACK → M2S05（更换 baseline）
```

### 9.2 跨模块回溯

```
Gate G3 或 M3S04 发现根本性问题
  ├── 方法实现忠实但设计本身有缺陷 → BACKTRACK → M2S03
  ├── 核心假设被实验否定 → BACKTRACK → M1S04（修正假设）或 M1S03（调整问题）
  └── M2 的实验设计导致无法公平比较 → BACKTRACK → M2S05
```

---

## 10. 实验执行环境管理

> **重要**：M3 的实验可以在**本地**或**远程服务器**上执行。执行位置和环境配置必须在 M3S01 阶段明确并锁定，确保可复现性。

### 10.1 执行位置选择

| 模式 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| **local** | 本地有GPU，或实验规模小（CPU即可） | 低延迟、无需同步、调试方便 | 本地硬件限制 |
| **ssh** | 本地无GPU，需使用远程服务器/集群 | 可利用强大远程硬件 | 需要网络、同步开销、调试不便 |

**默认行为**：
- 如果未配置远程服务器，默认使用 `local` 模式
- 如果配置了 `ssh` 但连接失败，应回退到 `local` 并警告用户
- **禁止**：在没有明确配置的情况下自动猜测远程服务器

### 10.2 环境管理规范

**强制要求**：实验必须在隔离环境中运行，**禁止在系统 Python 中直接安装依赖**。

| 工具 | 推荐度 | 适用场景 | CUDA支持 |
|------|--------|---------|---------|
| **conda** | ⭐⭐⭐ 首选 | 需要管理CUDA和非Python依赖 | ✅ 原生支持 |
| **uv** | ⭐⭐⭐ 现代首选 | 追求极速包管理、现代Python工作流 | ⚠️ 需手动安装CUDA |
| **venv** | ⭐⭐ 可用 | 纯Python项目、轻量需求 | ❌ 不支持 |
| **docker** | ⭐⭐ 可选 | 复杂依赖、多项目并行、需要最高隔离性 | ✅ 需nvidia-docker |

**环境创建流程（M3S01）**：

```
Step 1: 读取 config/execution_env.yaml
Step 2: 根据 env_manager 创建隔离环境
Step 3: 安装项目依赖（requirements.lock）
Step 4: 验证环境（import torch / import tensorflow 等）
Step 5: 记录环境快照到 M3S01 产出
```

### 10.3 远程执行工作流（SSH 模式）

#### 10.3.0 SSH 模式数据集准备规范（M3S01 前置步骤）

> **原则**：SSH 模式下，数据集**不通过项目同步脚本传输**（`sync_remote.sh` 排除大文件）。数据集必须在远程服务器上独立准备，优先远程直接下载，次选本地上传。

**远程数据集准备流程**：

```
Step 1: 检查远程已有缓存
  ├── ssh user@host "ls -la {remote_dataset_path}/{id}/"
  ├── 如存在且完整 → 创建远程项目软链接 → 完成
  └── 如不存在 → Step 2

Step 2: 远程直接下载（优先）
  ├── ssh user@host "mkdir -p {remote_dataset_path}/{id}"
  ├── ssh user@host "cd {remote_dataset_path}/{id} && {download_command}"
  ├── 后台运行（screen/tmux/nohup）
  ├── 定期 check 进度
  └── 下载完成 → 校验 → 创建软链接 → 完成

Step 3: 本地→远程上传（当 Step 2 失败时）
  ├── 检查本地缓存是否存在
  ├── rsync -avzP --partial ./data/datasets/{id}/ user@host:{remote_dataset_path}/{id}/
  ├── 断点续传，网络中断可恢复
  └── 上传完成 → 远程校验 → 创建软链接 → 完成

Step 4: 用户协助（当 Step 2-3 均失败时）
  ├── 生成数据集获取报告（含官方链接、命令、目标路径）
  ├── 阻塞等待用户确认数据集已放入指定路径
  └── 用户确认后 → 从 Step 1 重新验证
```

**大数据集传输策略**：

| 大小 | 推荐方式 | 命令 |
|------|---------|------|
| < 1 GB | rsync 直接上传 | `rsync -avzP ./data/datasets/{id}/ user@host:{path}/{id}/` |
| 1-50 GB | rsync 断点续传 | `rsync -avzP --partial ./data/datasets/{id}/ user@host:{path}/{id}/` |
| > 50 GB 或远程带宽更高 | 远程直接下载 | `ssh user@host "cd {path} && wget/curl ..."` |
| > 100 GB 或权限受限 | 用户协助 | 生成报告，等待用户手动放置 |

**禁止**：以"数据集太大"为由拒绝尝试任何传输/下载方式。

#### 10.3.1 SSH 认证初始化流程（M3S01 前置步骤）

当项目创建时配置了 `auth_method: password`，M3S01 必须先完成"密码→密钥"过渡：

```
M3S01-Pre: SSH 认证初始化
  ├── 检查本地是否存在专用密钥对 (~/.ssh/autopaper2_id_ed25519)
  │     ├─ 存在 → 直接使用
  │     └─ 不存在 → ssh-keygen 生成新密钥对
  ├── 检查 sshpass 是否安装
  │     └─ 未安装 → 输出安装命令并 HALT，等待用户安装
  ├── 使用 sshpass + ssh-copy-id 推送公钥到远程服务器
  ├── 验证密钥登录: ssh -i new_key user@host "echo ok"
  │     ├─ 成功 → 更新 execution_env.yaml: auth_method=key, 清空 password
  │     │          后续使用 sync_remote.sh（密钥版）
  │     └─ 失败 → 保留 password 配置，使用 sync_remote_password.sh（sshpass 回退版）
  │                在 M3S01_implementation.md 中标记风险
```

**安全要求**：
- 密钥部署成功后，`execution_env.yaml` 中的 `password` 字段必须清空
- 禁止在 M3S02/M3S03 阶段仍以明文密码进行常规同步
- 如密钥部署失败需继续使用密码，必须在 M3S01 产出中明确记录原因

#### 10.3.2 标准远程执行工作流

```
M3S01: Dataset & Environment Review / Setup
  ├── 本地: 开发代码、版本控制
  ├── 认证: 完成 SSH 密钥初始化（如需要）
  ├── 数据: 远程数据集准备（下载/上传/校验）← 新增
  ├── 同步: rsync push → 远程服务器（代码、配置，不含数据）
  └── 远程: 创建环境、验证安装

M3S02: Baseline Result Review
  ├── 同步: rsync push（更新后的代码）
  ├── 远程: 运行 baseline 验证
  └── 同步: rsync pull（baseline metric contract）

M3S03: Main Experiment Result Review
  ├── 同步: rsync push（最终代码和配置）
  ├── 远程: 执行主实验迭代
  ├── 定期同步: rsync pull（结果、日志、曲线）
  └── 实验完成后: 全量 pull

M3S04: Result Validation & Evidence Packaging
  └── 本地: 分析已同步回本地的结果
      （Analysis Agent 始终在本地运行，不通过SSH）
```

**同步规则**：
- **Push（本地→远程）**：代码、配置、requirements
- **Pull（远程→本地）**：results.tsv、日志、曲线、metric contract、验证报告
- **排除项**：`__pycache__`、`*.pyc`、`.git`、大模型权重（`.pt`、`.pth`、`.ckpt`）、**数据集**
- **结果同步策略**：
  - `metrics_only`：只同步指标和日志（推荐，节省带宽）
  - `all`：同步所有结果（包括大文件）
  - `selective`：按配置的模式同步

### 10.4 环境配置文件

每个项目在创建时会生成 `config/execution_env.yaml`，Experiment Agent 在 M3S01 读取并按此配置执行。

同时提供辅助脚本模板：
- `config/execution_env_templates/setup_conda.sh.template` — conda 环境创建脚本
- `config/execution_env_templates/Dockerfile.template` — Docker 镜像模板
- `config/execution_env_templates/sync_remote.sh.template` — 远程同步脚本

### 10.5 硬件信息记录

无论本地还是远程，M3S01 必须检测并记录硬件信息：

```yaml
hardware:
  gpu: "NVIDIA RTX 4090"      # nvidia-smi 检测
  gpu_count: 1                 # nvidia-smi 检测
  memory: "24GB"              # nvidia-smi 检测
  cpu_cores: 16               # lscpu / sysctl 检测
```

硬件信息写入：
- `config/execution_env.yaml`（回填）
- `knowledge/M3/M3S01_implementation.md`
- `experiments/artifacts/main_experiment/manifest.yaml`

**目的**：让读者知道实验在什么硬件上运行，便于判断结果的可比性。

---

## 11. 跨模块衔接

### M2 → M3

- M2 传递：方法架构、算法伪代码、实验计划、数据集/baseline 选择
- M3 接收后必须确认：方法设计在实现层面是否可行？baseline 是否可获取？
- **新增**：检查 `config/execution_env.yaml` 是否已配置，确认执行环境可用

### M3 → M4

- M3 传递：主实验结果、验证状态、evidence artifact、已知限制、建议分析方向
- M4 接收后：设计消融/鲁棒性/机制验证实验，深度解读结果

---

## 11. 与 DeepScientist / aris 的对比

| 维度 | DeepScientist `experiment` | aris Experiment Plan/Log | AutoPaper2 M3 (本设计) |
|------|---------------------------|-------------------------|----------------------|
| **Baseline 处理** | 隐式包含在 experiment 中 | 有 Baseline 里程碑 | **M3S02 独立 Baseline Lock 阶段；comparator-first 原则** |
| **Run Contract** | ✅ 显式锁定 | ⚪ 隐含在 Plan 中 | **M3S03 强制 Run Contract 锁定** |
| **Evidence Ladder** | ✅ minimum/solid/maximum | ❌ 无 | **M3S03 强制 Evidence Ladder 评估** |
| **统计验证** | ⚪ 部分提及 | ❌ 无 | **M3S04 强制统计检验 + 效应量** |
| **失败分类** | ✅ 详细分类 | ❌ 无 | **M3S03 记录失败类型，M3S04 判定** |
| **实验日志** | ⚪ results.tsv | ✅ EXPERIMENT_LOG.md | **results.tsv + M3S03 markdown 报告 + Engineering Findings** |
| **Claim Map** | ❌ 无 | ✅ Claim Map | **M3S03 Run Contract 隐含 claim→evidence 映射；M5S01 Pre-Write Audit 显式整理 claim / evidence / contribution 边界** |
| **Findings 记录** | ❌ 无 | ✅ Research + Engineering | **M3S04 负面结果记录；M4S01 Other Findings 深化** |
| **Artifact 打包** | ✅ `artifact.record_main_experiment` | ❌ 无 | **M3S04 Evidence Artifact 标准化打包** |
| **可比性契约** | ✅ metric contract | ⚪ 部分 | **M3S02 Metric Contract 标准化** |
| **环境管理** | ⚪ bash_exec 本地 | ❌ 无 | **M3S01 隔离环境 + 本地/SSH双模式 + 硬件记录** |

---

## 12. 关键设计决策

### 决策 1: 为什么 M3 从 3 Stage 扩展为 4 Stage？

原设计：M3S01(代码) → M3S02(实验迭代) → M3S03(结果验证)

**拆分理由**：
1. **Baseline 验证的独立性**：baseline 验证是一个复杂的、可能耗时的过程（下载代码、修复 bug、调环境），不应与代码实现混在一起
2. **Comparator-first 原则**：DeepScientist 的 baseline skill 证明，一个独立的 baseline 阶段能显著提高下游实验的可信度
3. **质量门控精度**：如果 baseline 有问题，应该能在进入主实验前就拦截，而不是浪费主实验的 GPU 时间
4. **与 M2 对称**：M2 有 6 个 Stage，M3 作为同等重要的执行阶段，4 个 Stage 是合理的粒度

**新 4-Stage 结构**：
- **实现与环境 (S01)** → 基线锁定 (S02) → 主实验执行 (S03) → 结果验证 (S04)
- Baseline Lock 成为独立的 quality gate

### 决策 2: 为什么引入 Run Contract 和 Evidence Ladder？

（汲取 DeepScientist `experiment` skill）

- **Run Contract**：防止实验过程中的"范围蔓延"和"指标替换"——中途换数据集、换指标是科研诚信的大敌
- **Evidence Ladder**：防止"最小可行证据"和"完美证据"之间的混淆——明确告知下游"当前证据足以支撑什么级别的声明"

### 决策 3: 为什么 M3S04 由 Analysis Agent 而非 Experiment Agent 执行？

- 结果验证需要统计推断能力（p-value、效应量、置信区间），这是 Analysis Agent 的核心能力
- Experiment Agent 的职责是"跑实验"，Analysis Agent 的职责是"判断结果意味着什么"
- 但 M3S04 的**范围严格限制**在"验证性分析"（数据质量、统计显著性、诚实决策），不做"深度解读"（那是 M4 的工作）

### 决策 4: Metric Contract 的格式与位置

（汲取 DeepScientist `baseline` skill）

- 位置：`experiments/baselines/<baseline_id>/metric_contract.yaml`
- 格式：YAML，包含 task、dataset、metrics、environment、deviations、verification_verdict
- 目的：让下游（M3S03、M3S04、M4、M5）无需重新运行 baseline 就能知道比较基准
- 原则：baseline 验证一次，处处引用

### 决策 5: 负面结果的处理

（汲取 aris FINDINGS_TEMPLATE 和 DeepScientist 诚实性原则）

- M3S03 的 results.tsv 必须记录**所有**迭代尝试，包括失败的
- M3S04 必须设有「负面结果」专节
- 如果 M3S04 决策为 BACKTRACK 因为假设被否定，这不是"失败"，而是"获得了有价值的负面证据"
- 这种设计防止了"为了推进而隐瞒负面结果"的学术不端倾向

---

## 13. 实现清单

### 13.1 需要创建的文件

```
docs/design/
└── M3_MODULE_DESIGN.md                # ✅ 本文件

docs/AGENTS/experiment/
└── AGENT.md                           # 更新：匹配 4 Stage 新设计

docs/AGENTS/analysis/
└── AGENT.md                           # 更新：明确 M3S04 的范围限制

docs/AGENTS/critic/evidence/
└── AGENT.md                           # 新增：Gate G3 Evidence Critic

docs/AGENTS/critic/
├── m3_dataset_env_review/AGENT.md      # 新增：M3S01 数据集/环境审查
├── m3_baseline_result_review/AGENT.md  # 新增：M3S02 baseline 结果审查
└── m3_main_result_review/AGENT.md      # 新增：M3S03 主实验结果审查

templates/stage/
├── M3S01_template.md                  # 新增：Dataset & Environment Review / Setup
├── M3S02_template.md                  # 新增：Baseline Result Review
├── M3S03_template.md                  # 新增：Main Experiment Result Review
└── M3S04_template.md                  # 新增：Result Validation & Evidence Packaging

skills/AutoPaper2_m3_experiment/
└── SKILL.md                           # 新增：M3 Skill 定义
```

### 13.2 需要更新的文件

```
spiral/project.py                     # MODULE_STAGES["M3"] 扩展为 4 Stage
                                      # GATE_STAGES["G3"] 改为 "M3S04"
                                      # AGENT_FOR_STAGE 添加 M3S04

spiral/conductor.py                   # STAGE_CHECKERS 更新 M3 Stage
                                      # GATE_CRITICS["G3"] 确认 ["method", "evidence"]

docs/design/M1_M2_BACKTRACK_DIAGRAM.md # 扩展为 M1-M3 全链路回溯图

docs/AGENTS/critic/method/AGENT.md     # 更新：添加 Gate G3 的审查对象（代码实现）
```

### 13.3 现有已就绪的文件

```
docs/AGENTS/experiment/AGENT.md        # ⚠️ 存在但需更新（引用旧 M2 文件名）
docs/AGENTS/analysis/AGENT.md          # ⚠️ 存在但需更新（M3S03 相关部分）
docs/AGENTS/critic/method/AGENT.md     # ✅ 存在，需扩展 G3 审查范围
docs/AGENTS/critic/cross_model_protocol.md  # ✅ 复用
```

---

> **下一步**: 确认本蓝图后，进入具体文件实现（模板、Agent 定义、Skill、代码更新）。
