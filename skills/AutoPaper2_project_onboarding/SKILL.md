---
name: AutoPaper2_project_onboarding
description: >
  AutoPaper2 项目创建后的 Onboarding（入项配置）Skill。
  当项目刚被创建、或项目从其他环境迁移过来时触发。
  负责暂停流程，要求用户确认并补全项目配置（SSH、作者、环境、数据集等），
  用户确认 "已填写" 后才允许继续执行 M1 及后续模块。
argument-hint: [项目路径]
skill_role: orchestrator
---

# Project Onboarding — 项目入项配置

项目创建或迁移后的**强制配置检查点**。在用户可以开始任何研究工作（M1-M6）之前，必须完成本流程。

## 触发条件

以下情况**必须**触发本 Skill：

1. **新项目创建完成后**（`scripts/state_manager.py create` 之后）
2. **项目从其他机器/环境迁移过来后**首次启动
3. **用户显式要求**："检查项目配置"、"补全项目信息"、"onboarding"
4. **M1 启动前检测到 onboarding 未完成**（`state/pipeline_state.yaml` 中 `status: onboarding_pending`）

## 控制工作流

```
Phase 0: 项目定位
  → 确认目标项目路径
  → 读取 state/pipeline_state.yaml
  → 确认当前 status 是否为 onboarding_pending（或用户显式触发）

Phase 1: 自动环境探测（如未执行过）
  → 调用 scripts/env_probe.py --project {proj_dir}
  → 自动填充 config/execution_env.yaml 中的可探测字段
  → 生成 state/env_probe_report.yaml

Phase 2: 配置完整性检查
  → 检查以下配置文件是否已填写：
    1. config/execution_env.yaml    — 执行环境
    2. config/author_info.yaml      — 作者信息
    3. state/project_brief.yaml     — 项目基础信息（已自动填充）

Phase 3: 向用户展示 Onboarding Checklist（阻塞等待）
  → 生成 state/onboarding_checklist.md
  → 发送给用户，要求逐项确认或补全
  → **暂停执行，等待用户回复**

Phase 4: 用户确认后验证
  → 收到用户 "已填写" / "确认无误" 回复
  → 重新读取各配置文件，验证必填字段非空
  → 验证通过后：
     - 删除 state/onboarding_checklist.md
     - 更新 pipeline_state.yaml: status → pending / ready
     - 允许进入 M1S01
  → 验证不通过：
     - 指出缺失字段
     - 回到 Phase 3 重新等待
```

## Onboarding Checklist（发送给用户的模板）

```markdown
# Project Onboarding Checklist — {project_name}

> 项目已创建 / 已迁移。在正式开始研究前，请确认以下配置：

## ✅ 已自动探测（无需修改，但请确认）

- [ ] **执行模式**: {local/ssh} — 当前设置为: {mode}
- [ ] **Python 版本**: {python_version}
- [ ] **CUDA 版本**: {cuda_version}
- [ ] **GPU**: {gpu_name} x{gpu_count} ({memory})
- [ ] **CPU**: {cpu_model} / {cpu_cores} cores
- [ ] **环境管理工具**: {conda/uv/venv}

## ⚠️ 需手动填写（请补全后回复"已填写"）

### 1. 执行环境配置 (`config/execution_env.yaml`)

**当前执行模式: `{mode}`**

{{#if mode == "ssh"}}
如使用 **SSH 远程执行**，**必须**填写以下字段：
- [ ] `ssh.host`: 远程服务器地址（如: gpu-server.lab 或 192.168.1.100）
- [ ] `ssh.user`: SSH 用户名
- [ ] `ssh.port`: SSH 端口（默认 22）
- [ ] `ssh.auth_method`: key 或 password
- [ ] `ssh.identity_file`: 私钥路径（如使用 key 认证）
- [ ] `ssh.conda_env_name`: 远程 conda 环境名（如有）
- [ ] `ssh.framework_root`: 远程框架根目录（默认: ~/AutoPaper2）
- [ ] `ssh.workspace_path`: 远程工作路径（默认: ~/AutoPaper2/projects/{project_name}）
- [ ] `ssh.dataset_path`: 远程公共数据集缓存路径（默认: ~/AutoPaper2/data/datasets）
{{else}}
当前为 **本地执行模式**，SSH 配置**无需填写**。请确认以下字段：
- [ ] `local.env_name`: 本地环境名（默认: autopaper2-{project_name}）
- [ ] `local.cuda_version`: CUDA 版本是否正确
- [ ] `local.env_manager`: 环境管理工具（conda/uv/venv）

> 如需切换到 SSH 远程执行，请将 `execution.mode` 改为 `ssh`，并填写 SSH 相关字段。
{{/if}}

### 2. 作者信息 (`config/author_info.yaml`)

- [ ] `authors[0].name`: 作者姓名
- [ ] `authors[0].affiliation`: 单位/学校
- [ ] `authors[0].email`: 邮箱
- [ ] `authors[0].orcid`: ORCID（可选）
- [ ] `acknowledgments`: 致谢（可选）
- [ ] `funding`: 基金信息（可选）

### 3. 投稿目标确认

- [ ] Venue: {venue_name} ({venue_id})
- [ ] Page Limit: {page_limit} 页
- [ ] LaTeX 模板: 已复制到 `artifacts/latex_template/`

### 4. 数据集需求确认

- [ ] 实验所需数据集已确认（来自 M2S05，如尚未到 M2 则跳过）
- [ ] 大型数据集（>10GB）是否已在本地/远程准备就绪

---

**请检查以上清单，在文件中补全所需信息后，回复 "已填写"，我将继续。**
```

## 验证规则

用户回复 "已填写" 后，Agent 必须执行以下验证：

```python
# 伪代码
validation_passed = True
missing_fields = []

# 1. 检查 execution_env.yaml
exec_mode = execution_env.get("execution", {}).get("mode", "local")
if exec_mode == "ssh":
    ssh = execution_env.get("execution", {}).get("ssh", {})
    if not ssh.get("host"):
        missing_fields.append("ssh.host")
    if not ssh.get("user"):
        missing_fields.append("ssh.user")
# 若 mode == local，SSH 字段不检查

# 2. 检查 author_info.yaml
authors = author_info.get("authors", [])
if not authors or not authors[0].get("name"):
    missing_fields.append("authors[0].name")

if missing_fields:
    print(f"[ONBOARDING] 以下字段仍为空，请补全: {missing_fields}")
    validation_passed = False
```

## 状态管理

- **Onboarding 进行中**: `state/pipeline_state.yaml` 中 `current.status = "onboarding_pending"`
- **Onboarding 完成**: `current.status = "pending"`，删除 `state/onboarding_checklist.md`
- **阻止条件**: 任何模块 Skill（M1-M6）在启动前必须检查 onboarding 状态，如为 `onboarding_pending` 则必须先触发本 Skill

## Key Rules

- **强制阻塞**：Onboarding 未完成前，**绝对禁止**进入 M1S01 或任何其他 stage
- **一次性收集**：尽量在项目创建时一次性收集所有必要配置，避免后续反复询问
- **环境变化可重新触发**：如果机器换了、GPU 变了、SSH 配置改了，用户可以说 "重新探测环境" 或 "更新配置"，本 Skill 重新执行
- **不阻塞已进行中项目**：如果项目已经进展到 M1S02 或更后，不应强制回到 onboarding，除非用户显式要求
