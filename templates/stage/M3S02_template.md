# M3S02: Dataset & Environment Review / Setup

> **Stage**: M3S02
> **Agent**: Experiment Agent
> **输入**: `knowledge/M3/M3S01_main_experiment_design.md`, `knowledge/handoff_M2_M3.md`, `knowledge/M2/M2S03_method_architecture.md`, `knowledge/M2/M2S04_algorithm_theory.md`, `knowledge/M2/M2S05_experiment_setup.md`
> **输出**: `knowledge/M3/M3S02_implementation.md` + `experiments/src/*.py` + `experiments/configs/*.yaml` + `experiments/configs/resource_plan.yaml` + `experiments/requirements.lock` + `experiments/logs/m3s02_longrun_ledger.md`
>
> **审查重点**: 数据集可获取性、公共缓存/软链接、执行环境、依赖锁定、硬件回填、运行命令与配置完整性

---

## 0. 数据集准备（M3S02 首要任务）

> **铁律**：数据集获取是 M3S02 的前置条件。在数据集确认可用之前，不得进入代码实现阶段。**绝对禁止**使用仿真数据、合成数据或随机生成数据替代真实数据集。

### 0.1 数据集需求确认

读取 M3S01 主实验设计和 M2S05 中的数据集获取清单，确认主实验所需数据集列表；不得添加 M4 消融或鲁棒性分析才需要的数据集。

| 数据集 | 公共缓存路径 | 缓存是否存在 | 校验结果 | 项目软链接路径 |
|--------|-------------|-------------|---------|---------------|
| {{dataset_1}} | `../../data/datasets/{{id}}/` | 是/否 | 通过/失败/跳过 | `experiments/data/{{id}}/` |
| {{dataset_2}} | ... | ... | ... | ... |

### 0.2 数据集获取策略（严格执行）

#### 策略 A：框架公共缓存复用（优先级最高）

```bash
# 1. 读取注册表
cat data/datasets/.dataset_registry.yaml

# 2. 检查缓存是否存在
ls -la data/datasets/{{id}}/

# 3. 验证完整性（如有 checksum）
{{checksum_verify_cmd}}
```

#### 策略 B：自动下载（所有数据集必须尝试）

**无论数据集大小，必须执行下载尝试**。

```bash
# 方式 1: 通过 torchvision / tensorflow_datasets / huggingface datasets 自动下载
python -c 'import torchvision; torchvision.datasets.{{Dataset}}(root="./data/datasets/{{id}}", download=True)'

# 方式 2: 通过 wget / curl 下载官方链接
wget -P ./data/datasets/{{id}}/ {{official_url}}

# 方式 3: 通过 kaggle API
kaggle datasets download -d {{kaggle_path}} -p ./data/datasets/{{id}}/

# 方式 4: 执行 registry 中记录的 download_command
cd {framework_root} && {{download_command}}
```

**大数据集下载注意事项**：
- > 10 GB 的数据集：使用 `nohup` 或 `screen` 后台运行下载命令
- 下载期间可同时推进环境配置（不依赖数据的工作）
- 记录下载命令、输出日志、预估完成时间
- **禁止**以"太大"为由拒绝执行下载命令

#### 策略 C：SSH 远程模式下的数据集准备

当 `execution.mode == ssh` 时，远程采用与本地一致的框架结构，`framework_root` 默认指向 `~/AutoPaper2`。

> **远程部署精简原则**：远程仅存放**项目代码**和**实验需要用到的数据集**。以下不上传：
> - `data/public_literature_db/`（公共文献数据库仅在本地使用）
> - `skills/`、`docs/`、`templates/`、`tests/`、`*.md`
> - `.git/`、框架级非执行文件
>
> 数据集按需同步：仅当实验需要用到某个数据集时，才将其放入远程公共缓存，不批量上传全部本地数据集。

**Step 1: 检查远程公共数据集缓存是否已有该数据集**
```bash
# 优先检查远程框架公共缓存（~/AutoPaper2/data/datasets/<id>/）
ssh {user}@{host} "ls -la {remote_framework_root}/data/datasets/{{id}}/ 2>/dev/null || echo 'NOT_FOUND'"
```

**Step 2: 如远程公共缓存已存在 → 直接创建项目软链接**
```bash
# 公共缓存命中，直接复用，无需重复下载
ssh {user}@{host} "cd {workspace_path} && mkdir -p experiments/data && ln -s {remote_framework_root}/data/datasets/{{id}} experiments/data/{{id}}"
```

**Step 3: 如远程公共缓存不存在 → 远程服务器直接下载（优先）**
```bash
# 在远程服务器公共缓存目录执行下载（利用服务器带宽和存储，供所有项目复用）
ssh {user}@{host} "mkdir -p {remote_framework_root}/data/datasets/{{id}} && cd {remote_framework_root}/data/datasets/{{id}} && {{download_command}}"

# 下载完成后创建项目软链接
ssh {user}@{host} "cd {workspace_path} && mkdir -p experiments/data && ln -s {remote_framework_root}/data/datasets/{{id}} experiments/data/{{id}}"
```

**Step 4: 本地→远程公共缓存传输（当远程无法直接下载时）**
```bash
# 使用 rsync 断点续传上传到远程公共缓存（本地有缓存的场景）
rsync -avzP --partial \
    ./data/datasets/{{id}}/ \
    {user}@{host}:{remote_framework_root}/data/datasets/{{id}}/

# 验证传输完整性
ssh {user}@{host} "cd {remote_framework_root}/data/datasets/{{id}} && {{checksum_verify_cmd}}"

# 创建项目软链接
ssh {user}@{host} "cd {workspace_path} && mkdir -p experiments/data && ln -s {remote_framework_root}/data/datasets/{{id}} experiments/data/{{id}}"
```

| 数据集大小 | 本地→远程传输方式 | 备注 |
|-----------|-----------------|------|
| < 1 GB | `rsync -avzP` 直接上传 | 快速完成 |
| 1 GB ~ 50 GB | `rsync -avzP --partial` 断点续传 | 网络中断可恢复 |
| > 50 GB | 优先远程直接下载；如必须上传，使用 `rsync --partial --progress` 后台传输 | 可利用 screen/tmux 保持会话 |

**禁止**：以"数据集太大"为由拒绝尝试上传或远程准备。

### 0.3 数据集下载与校验记录

**对于所有尝试过的获取方式**:

| 数据集 | 获取策略 | 尝试状态 | 下载状态 | 校验状态 | 大小匹配 | 错误日志 | 备注 |
|--------|---------|---------|---------|---------|---------|---------|------|
| {{dataset_1}} | A/B/C | 已尝试/未尝试 | 成功/失败/进行中 | 通过/失败 | 是/否 | ... | ... |

```bash
# 校验完整性命令示例
md5sum data/datasets/{{id}}/{{checksum_file}}
sha256sum data/datasets/{{id}}/{{checksum_file}}
```

### 0.4 项目级数据集链接

```bash
# 创建项目级数据目录
mkdir -p experiments/data

# 创建软链接到公共缓存（本地模式）
ln -s ../../../data/datasets/{{id}}/ experiments/data/{{id}}
```

**验证链接可用性**:
```bash
ls -la experiments/data/{{id}}/
# 应能看到数据集文件
```

### 0.5 数据集元数据记录

记录到 `knowledge/M3/M3S02_implementation.md`:
- 每个数据集的实际路径
- 获取方式（缓存复用 / 自动下载 / SSH远程准备 / 用户协助）
- 下载时间
- 校验结果
- 软链接关系
- 对于 SSH 模式：远程数据集路径、传输方式、验证结果

同时必须生成 `experiments/data/dataset_manifest.yaml`，供 M3S02 reviewer 与 stage gate 验证数据集不是残缺目录或占位数据。

最低字段：

```yaml
datasets:
  - dataset_id: "{{id}}"
    status: complete              # complete / verified / ready
    source: official_url | framework_cache | hf | kaggle | ssh_cache | mirror
    path: experiments/data/{{id}}
    required_files:
      - raw/train.jsonl
      - raw/test.jsonl
      - metadata.json
    splits:
      train:
        path: raw/train.jsonl
        expected_count: 10000
        actual_count: 10000
      test:
        path: raw/test.jsonl
        expected_count: 1000
        actual_count: 1000
    checksum:
      algorithm: sha256
      file: metadata.json
      value: "{{sha256}}"
    smoke_load:
      status: passed
      command: "python experiments/src/load_dataset.py --dataset {{id}} --smoke"
      log_path: experiments/logs/dataset_{{id}}_smoke.log
```

要求：
- `datasets` 只能包含 M3S01 主实验需要的数据集，不包含 M4 消融/鲁棒性/机制分析才需要的数据集。
- `status` 必须是 complete/verified/ready 之一；partial/pending/downloaded_only 不得 PASS。
- `required_files`、`splits`、`actual_count` 必须显式记录；split 文件不存在、样本数为 0、低于声明的 `expected_count` 均不得 PASS。
- 如官方提供 checksum，必须记录并验证；未提供 checksum 时仍必须通过 required_files、split count 和 smoke-load 验证。
- smoke-load 必须真实读取数据集并写日志；不能只做 `ls` 或目录非空检查。

### 0.6 数据集获取失败处理（仅限真实外部阻塞）

当策略 A/B/C 均失败后，只有在缺少账号凭证、付费/配额审批、磁盘扩容、受限内网/VPN访问或连续网络失败且无法通过 SSH/镜像/断点续传恢复时，才允许进入阻塞流程。不得因为“太大”“太慢”“训练/下载需要等待”而请求用户介入；这类任务必须进入 longrun ledger 并由 Agent 轮询、恢复、继续执行。

进入阻塞流程时，**必须**执行以下流程，**不得**进入代码实现：

1. **生成阻塞报告** `knowledge/M3/M3S02_dataset_pending.md`：
   ```markdown
   # Dataset Pending Report — M3S02

   ## 所需数据集
   | 数据集 | 官方URL | 预估大小 | 用途 | 状态 |
   |--------|---------|---------|------|------|
   | ... | ... | ... | ... | 待获取 |

   ## 已尝试的获取方式及结果
   - [ ] 框架公共缓存: {{结果}}
   - [ ] 自动下载: {{结果}}（错误: ...）
   - [ ] SSH远程下载: {{结果}}（错误: ...）
   - [ ] 本地→远程上传: {{结果}}（错误: ...）

   ## 推荐的获取方式
   1. 官方下载: {{url}} → 命令: `{{cmd}}`
   2. 镜像下载: {{mirror_url}}
   3. 从其他环境复制: {{source_path}}

   ## 数据入库路径
   - 本地公共缓存: `{framework_root}/data/datasets/<id>/`
   - SSH远程公共缓存: `{remote_framework_root}/data/datasets/<id>/`（所有项目共享，优先复用）

   ## 下一步
   当前仅因凭证/配额/存储/受限网络等不可自动解决条件阻塞。提供缺失条件后，Agent 必须从 Step 1 重新验证并继续执行。
   ```

2. **更新状态**：`state/pipeline_state.yaml` 标记 `status: dataset_pending`

3. **停止并等待用户**：仅在上述真实外部阻塞成立时发送阻塞通知，明确说明：
   - 缺失哪些数据集
   - 已尝试了哪些方式及失败原因
   - 官方下载链接和命令
   - 数据应放入的路径

4. **恢复条件**：收到用户补齐凭证/许可/配额/数据入库确认后：
   - 重新验证数据集可用性
   - 验证通过后删除 `M3S02_dataset_pending.md`
   - 恢复正常 M3S02 流程

---

## 1. 执行环境配置

### 1.1 环境配置读取

读取 `config/execution_env.yaml`：

| 配置项 | 值 | 说明 |
|--------|-----|------|
| 执行模式 | local / ssh | 必须明确为二者之一 |
| 环境管理工具 | conda / venv / uv / docker | local 模式必填 |
| Python 版本 | ... | local 模式必填 |
| CUDA 版本 | ... | ... |
| sandbox.enabled | true / false | 必须为 true |
| sandbox.mode | docker / conda / venv / uv / ssh_remote | local 不得为 ssh_remote；ssh 必须为 ssh_remote |
| sandbox.network_policy | disabled / restricted / open | ... |
| sandbox.resource_limits | timeout / CPU / memory / GPU | ... |
| resource_optimization.enabled | true / false | 必须为 true |
| resource_optimization.gpu_strategy | auto / ddp / task_parallel / single | ... |
| resource_optimization.monitoring | interval / GPU阈值 / CPU阈值 | ... |
| resource_optimization.resource_pool | enabled / resources / include_local / scheduling_policy | 多服务器、多卡或 local+ssh 混合时必填 |

### 1.2 远程配置（如 mode = ssh）

| 配置项 | 值 |
|--------|-----|
| SSH Host | ... |
| SSH User | ... |
| 远程工作路径 | ... |
| 远程 Python 路径 | ... |
| 同步方式 | rsync / scp |

**SSH 硬性要求**: `host`、`user`、`workspace_path`、`env_manager`、`python_version`、`sync.method` 必须非空；`sync.method` 只能是 `rsync` 或 `scp`。`knowledge/M3/M3S02_implementation.md` 与 longrun ledger 必须包含 ssh/remote/rsync 证据。

### 1.2.1 多资源池（可选但一旦提供必须规划）

当用户提供多个服务器、多张卡，或要求本地和远程一起计算时，M3S02 必须把资源池写入 `experiments/configs/resource_plan.yaml.resource_pool`。

| resource_id | kind | server_id / lease_id | workspace | GPU ids/count | CPU cores | tags | sync_required | 用途 |
|-------------|------|----------------------|-----------|---------------|-----------|------|---------------|------|
| local | local | — | `{project}` | 0,1 / 2 | 16 | local,gpu | no | DDP / task slot |
| ssh:lab-a | ssh | lab-a / lease_x | `~/AutoPaper2/projects/...` | 0 / 1 | 32 | gpu,cuda | yes | independent runs |

必须说明：
- 哪些任务可并行，哪些任务有依赖或互斥。
- 多 GPU 单任务优先 DDP；独立 baseline/config/slice 才跨资源 task_parallel。
- 远程资源的 push/pull 同步策略、结果回收路径和失败恢复命令。
- 如果资源池存在但暂不并行，说明约束：数据未同步、显存不足、DDP 不兼容、公平性、配额或依赖。

### 1.3 环境创建记录

```bash
# 执行的命令记录
conda create -n ... python=...
conda activate ...
pip install -r requirements.lock
```

| 检查项 | 结果 | 备注 |
|--------|------|------|
| 环境创建成功 | 是/否 | ... |
| 核心包可导入 | 是/否 | ... |
| GPU 可用 | 是/否 | ... |

### 1.4 实验沙箱 / 容器隔离档案（必须记录）

M3/M4 将运行 LLM 生成或改写的实验代码，因此 M3S02 必须写入 `experiments/configs/sandbox_profile.yaml`，并与 `config/execution_env.yaml` 的 `execution.sandbox` 保持一致。

最低字段：

```yaml
sandbox:
  enabled: true
  mode: docker | conda | venv | uv | ssh_remote
  network_policy: restricted
  filesystem_policy:
    allowed_write_paths:
      - experiments/runs/
      - experiments/logs/
      - experiments/artifacts/
      - artifacts/
    denied_paths:
      - ~/.ssh/
      - /etc/
      - /var/
  secrets_policy:
    allow_env_secrets: false
    allow_ssh_key_read: false
    redact_logs: true
  resource_limits:
    timeout_hours: 24
    max_cpu_cores: 16
    max_memory_gb: 64
    max_gpu_count: all_visible
  reproducibility:
    requirements_lock: experiments/requirements.lock
    image: ""          # docker 模式必须填写
    image_digest: ""   # docker 模式建议填写
    seed_policy: fixed_seed_42
resource_optimization:
  enabled: true
  target_gpu_count: all_visible
  target_cpu_cores: auto
  gpu_strategy: auto
  cpu_strategy: dataloader_and_task_parallel
  dataloader:
    auto_num_workers: true
    max_workers: 16
    pin_memory: auto
    persistent_workers: auto
    prefetch_factor: 2
  monitoring:
    enabled: true
    interval_seconds: 10
    min_gpu_utilization_pct: 70
    min_cpu_utilization_pct: 60
    plan_path: experiments/configs/resource_plan.yaml
    monitor_path_template: experiments/runs/{run_id}/resource_monitor.csv
    runtime_watchdog:
      enabled: true
      default_interval_seconds: 14400
      events_path: experiments/logs/runtime_events.jsonl
      checks_path_template: experiments/runs/{run_id}/watchdog_checks.jsonl
      alerts_path_template: experiments/runs/{run_id}/watchdog_alerts.jsonl
      alert_policy: record_alert_only_agent_decides_continue_fix_or_stop
  resource_pool:
    enabled: false
    include_local: true
    allow_local_and_ssh: true
    scheduling_policy: dependency_aware_pack_by_gpu_then_cpu
    resources: []
    task_queue_paths:
      m3: experiments/configs/m3_task_queue.yaml
      m4: experiments/configs/m4_task_queue.yaml
    allocation_paths:
      m3: experiments/configs/m3_task_allocation.yaml
      m4: experiments/configs/m4_task_allocation.yaml
```

记录到 `knowledge/M3/M3S02_implementation.md`：
- sandbox mode 选择原因
- 网络策略和下载例外（如有，必须与 longrun ledger 对应）
- 文件写入边界和禁止路径
- 凭证/密钥处理策略
- CPU/GPU/内存/timeout 限制
- Docker image / conda env / venv / uv / ssh_remote workspace 的可复现标识

### 1.5 资源规划（必须记录）

M3S02 必须生成 `experiments/configs/resource_plan.yaml`，让 M3S04 有明确的资源执行合同，而不是临时手写命令。

```bash
python scripts/resource_planner.py plan --project . --output experiments/configs/resource_plan.yaml
```

SSH 模式下应在远程 workspace 运行同等命令，并将结果同步回本地。

**Resource Plan 摘要**:

| 项目 | 内容 |
|------|------|
| 可见 GPU | 数量 / 型号 / 显存 |
| 分配 GPU | `gpu_count`, `gpu_ids` |
| 分配 CPU | `cpu_cores` |
| 设备策略 | distributed_data_parallel / single_gpu / cpu_parallel / task_parallel |
| DataLoader | `num_workers`, `pin_memory`, `persistent_workers`, `prefetch_factor` |
| 线程环境变量 | `OMP_NUM_THREADS`, `MKL_NUM_THREADS` |
| 启动命令模板 | `torchrun ...` / `python ...` |
| 监控阈值 | GPU 利用率阈值 / CPU 利用率阈值 |
| Runtime watchdog | 巡检间隔、runtime_events 路径、watchdog checks/alerts 路径、告警不自动终止策略 |
| Resource pool | local/ssh resources、server_id/lease_id、GPU/CPU capacity、sync_required、公平性策略 |

**如未使用全部可见 GPU/CPU，必须说明原因**:

| 未使用资源 | 原因 | 对公平性的影响 | 后续策略 |
|-----------|------|----------------|----------|
| GPU {{id}} / CPU cores | DDP 不兼容 / 显存不足 / 配额限制 / baseline 公平性 | ... | task_parallel / 降级单卡 / 等待用户 |

**多资源产物（当 resource_pool.enabled 或资源数 > 1 时必须生成）**:
- `experiments/configs/m3_task_queue.yaml`: M3S04 候选 run 队列，包含 task_id/run_id、command、dependencies、parallelizable、resource_requirements、fairness_key。
- `experiments/configs/m3_task_allocation.yaml`: 由 `scripts/resource_planner.py allocate --stage M3S04` 生成，包含 assignments、waves、resource_id、slot_id、gpu_ids、cpu_cores、launch_command、resource_monitor、remote push/pull 要求。

### 1.6 长任务、权限与等待策略（必须记录）

M3S02 必须创建并维护 `experiments/logs/m3s02_longrun_ledger.md`。凡是数据下载、远程上传、环境创建、依赖安装、checkpoint 拉取、smoke run 等可能超过 10 分钟的任务，都必须写入 ledger；不得以"太大"、"太慢"、"需要等待"为由跳过。

| 字段 | 要求 |
|------|------|
| execution mode | `local` / `ssh`，与 `config/execution_env.yaml` 一致 |
| command | 实际执行命令；SSH 模式必须包含远程命令或 `rsync` 命令 |
| status | `queued` / `running` / `completed` / `failed` / `blocked_user_action`；进入 PASS 前，数据集/checkpoint/baseline 权重/model asset 获取类条目必须全部为 `completed` |
| log path | 命令 stdout/stderr 保存路径，例如 `experiments/logs/download_dataset_x.log` |
| patience / polling | timeout、轮询间隔、预计等待窗口、最近一次检查时间 |
| resume_command | 可恢复命令，例如 `rsync --partial --progress ...`、`wget -c ...`、`tmux attach -t ...` |
| permission / approval | 是否需要网络、账号、远程主机、磁盘配额、用户凭证或人工批准 |
| completion criteria | 文件存在、checksum 通过、import test 通过、smoke run 完成等 |

`experiments/logs/m3s02_longrun_ledger.md` 模板：

```markdown
# M3S02 Long-Running Execution Ledger

| Item | Execution mode | Command | Status | Log path | Patience / polling | Resume command | Permission / approval | Completion criteria |
|------|----------------|---------|--------|----------|--------------------|----------------|-----------------------|--------------------|
| dataset: {{id}} | local/ssh | `...` | completed/running/failed/blocked_user_action | `experiments/logs/...log` | timeout=..., poll_interval=..., last_checked=... | `...` | none / user credential / remote storage approval | checksum passed / files visible |
| env: {{env_name}} | local/ssh | `...` | ... | `experiments/logs/...log` | ... | `...` | ... | import test passed |
```

如果任务仍在运行或需要用户凭证/配额/存储/受限网络批准，M3S02 必须进入阻塞状态，review 必须给出 `HALT` 或 non-PASS verdict；不得写 `PASS` 后继续推进。阻塞记录必须说明已尝试的获取方式、session/PID/log path、下一次轮询时间、恢复命令和等待用户批准的具体原因。

---

## 2. 代码实现清单

### 2.1 核心组件对应表

| M2S03 组件 | 实现文件 | 行数 | 与设计的对应关系 | 偏差说明（如有） |
|-----------|---------|------|----------------|---------------|
| 组件 A | `src/model_a.py` | ~XXX | 一一对应 / 有偏差 | ... |
| 组件 B | `src/model_b.py` | ~XXX | 一一对应 / 有偏差 | ... |

### 2.2 关键算法实现

| M2S04 伪代码 | 实现位置 | 对应关系 | 偏差说明（如有） |
|-------------|---------|---------|---------------|
| Algorithm 1, Step 1-3 | `src/train.py:45-60` | 一一对应 | — |
| Algorithm 1, Step 4 | `src/model_a.py:88-95` | 有偏差 | 因 XX 原因调整了... |

> **重要**：任何与 M2 设计文档的偏差都必须在此表中明确记录并说明理由。

---

## 3. 代码结构

```
experiments/
├── src/
│   ├── model.py          # 核心方法实现
│   ├── train.py          # 训练脚本
│   ├── evaluate.py       # 评估脚本
│   ├── baseline_wrappers/ # baseline 包装器（如有）
│   └── utils.py          # 工具函数
├── configs/
│   ├── main_exp.yaml     # 主实验配置
│   └── baseline_*.yaml   # baseline 配置
├── requirements.lock     # 锁定依赖（pip/conda/uv）
├── README.md             # 运行指南
└── .gitignore
```

---

## 4. 环境配置

### 4.1 依赖清单

| 包名 | 版本 | 用途 |
|------|------|------|
| torch | 2.x.x | 深度学习框架 |
| ... | ... | ... |

### 4.2 锁定文件
- 锁定工具: pip freeze / conda-lock / uv.lock
- 生成命令: ...
- 文件路径: `experiments/requirements.lock`

### 4.3 硬件环境（自动检测）

```yaml
gpu: "NVIDIA RTX 4090"
gpu_count: 1
memory: "24GB"
cpu_cores: 16
```

---

## 5. 可复现性检查清单

- [ ] 随机种子已固定为 42（`random.seed(42)`, `np.random.seed(42)`, `torch.manual_seed(42)`, `torch.cuda.manual_seed_all(42)`）
- [ ] 所有超参数保存在配置文件中，无硬编码
- [ ] 代码通过语法检查（可导入，无 NameError）
- [ ] README 包含完整的运行命令
- [ ] 环境可在干净机器上重建
- [ ] 远程同步已验证（如使用 SSH 模式）

---

## 6. 静态验证结果

| 检查项 | 结果 | 备注 |
|--------|------|------|
| 语法检查 | 通过/失败 | ... |
| 导入测试 | 通过/失败 | ... |
| 配置加载 | 通过/失败 | ... |
| 远程环境验证 | 通过/失败/不适用 | ... |

---

## 7. 已知实现限制

| 限制 | 原因 | 对实验的影响 | 建议的缓解措施 |
|------|------|------------|--------------|
| ... | ... | ... | ... |

---

## 8. 远程同步状态（如适用）

| 同步方向 | 文件/目录 | 状态 | 备注 |
|---------|----------|------|------|
| Push | src/ | 完成 | ... |
| Push | configs/ | 完成 | ... |
| 远程验证 | 环境+代码 | 通过 | ... |

---

## 9. 传递给下游的信息

- **代码已测试通过的功能**: ...
- **与 M2 设计的主要偏差**: ...
- **可能需要额外关注的实现细节**: ...
- **预估的单次运行时间**: ...
- **远程执行注意事项**（如适用）: ...
