# M3S02: Baseline Result Review

> **Stage**: M3S02
> **Agent**: Experiment Agent
> **输入**: `knowledge/M3/M3S01_implementation.md`, `knowledge/M2/M2S05_experiment_setup.md` 或等价实验计划, `knowledge/M1/M1S02_literature_deepdive.md`
> **输出**: `knowledge/M3/M3S02_baseline_lock.md` + `experiments/baselines/*/metric_contract.yaml`
>
> **审查重点**: baseline 本地实验结果、metric contract、与论文/历史记录的偏差、smoke test 是否通过

---

## 1. Baseline 验证记录

### Baseline 1: [名称]

| 属性 | 内容 |
|------|------|
| 来源 | 官方代码 / pip 包 / 自行实现 |
| 验证路径 | attach / import / verify-local-existing / reproduce / repair |
| Checkpoint 来源 | 官方 Release / README 链接 / HuggingFace / 自动下载 / 无 |
| Checkpoint 本地路径 | `experiments/baselines/{id}/checkpoints/...` |
| Checkpoint 验证状态 | 已验证加载 / 未验证 / 不适用 |
| 官方指标（论文报告） | ... |
| 我们的运行结果 | ... |
| 偏差说明 | ... |
| 验证分级 | verified_match / verified_close / trusted_with_caveats / diverged |

**Checkpoint 获取记录**:
```yaml
checkpoint:
  source_url: "..."
  local_path: "experiments/baselines/{id}/checkpoints/..."
  filename: "..."
  checksum: "sha256:..."
  download_time: "..."
  auto_download: true/false
  verified_loadable: true/false
  search_attempts:
    - GitHub Releases: 是/否
    - README/文档: 是/否
    - 代码自动下载: 是/否
    - HuggingFace Hub: 是/否
    - 第三方托管: 是/否
    - 项目缓存复用: 是/否
```

**Metric Contract**:
```yaml
baseline_id: "..."
source: "..."
dataset: "..."
split: "..."
metrics:
  primary:
    key: "..."
    value: ...
    direction: "higher_is_better"
  secondary:
    - key: "..."
      value: ...
environment:
  python: "..."
  torch: "..."
  cuda: "..."
  hardware: "..."
known_deviations: "..."
verification_verdict: "..."
```

### Baseline 2: [名称]
...

---

## 2. 验证策略选择理由

| Baseline | 选择的路径 | 理由 |
|----------|-----------|------|
| Baseline-1 | reproduce | 官方代码可用，需本地运行验证 |
| Baseline-2 | attach | 之前项目已验证，metric contract 未过期 |

---

## 3. Smoke Test

### 3.1 Smoke Test 设计

- **目的**: 验证完整管道可运行，无基本错误
- **数据**: 使用 1% 训练数据 或 2 个 epoch
- **检查项**:
  - [ ] Loss 下降
  - [ ] 无 NaN/Inf
  - [ ] 指标计算正确
  - [ ] 模型保存/加载正常
  - [ ] 日志记录正常

### 3.2 Smoke Test 结果

| 检查项 | 结果 | 备注 |
|--------|------|------|
| Loss 下降 | 是/否 | ... |
| 无 NaN/Inf | 是/否 | ... |
| 指标计算 | 正确/错误 | ... |
| 保存/加载 | 正常/异常 | ... |

---

## 4. 环境一致性确认

| 维度 | Baseline 运行环境 | 本文方法运行环境 | 是否一致 |
|------|------------------|-----------------|---------|
| Python | ... | ... | 是/否 |
| PyTorch | ... | ... | 是/否 |
| CUDA | ... | ... | 是/否 |
| 硬件 | ... | ... | 是/否 |

---

## 5. 问题与修复记录

| 问题 | Baseline | 根因 | 修复措施 | 修复后状态 |
|------|---------|------|---------|-----------|
| 官方代码有 bug | Baseline-X | ... | ... | 已修复/未修复 |
| 环境依赖冲突 | Baseline-Y | ... | ... | 已解决 |

---

## 6. 传递给下游的信息

- **已验证的 baseline 列表**: ...
- **主要 baseline 的 metric contract 路径**: ...
- **Smoke test 是否通过**: ...
- **已知的环境差异**: ...
- **建议的 M3S03 Run Contract 中的比较基准**: ...
