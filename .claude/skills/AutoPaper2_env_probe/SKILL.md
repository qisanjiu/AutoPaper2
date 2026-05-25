---
name: AutoPaper2_env_probe
description: >
  AutoPaper2 环境探测与基础配置 Skill。
  当项目部署到新环境、需要自动检测当前机器的 GPU/Python/CUDA/框架版本，
  并自动填充 config/execution_env.yaml 时触发。
  也用于项目迁移到新机器后重新探测环境。
argument-hint: [项目路径（可选）]
skill_role: utility
---

# AutoPaper2 Environment Probe — 环境探测与基础配置

自动探测当前机器的硬件和软件环境，并生成/更新 `config/execution_env.yaml`。

## 触发条件

当用户说以下任意一种表述时触发本 Skill：

- "探测环境"
- "检查环境"
- "配置环境"
- "更新执行环境"
- "env probe"
- "环境配置"
- "项目迁移到新机器"
- "重新探测环境"
- "自动填写配置"

**默认触发**（无需用户显式说出）：
- 项目创建完成后，Conductor 自动调用本 Skill 探测环境
- 项目从一台机器复制到另一台机器后首次启动时

## 探测内容

本 Skill 调用 `scripts/env_probe.py` 自动探测以下信息：

| 探测项 | 自动填写 | 说明 |
|--------|---------|------|
| Python 版本 | ✅ 是 | 自动检测主版本号 |
| 操作系统 | ✅ 是 | Linux/macOS/Windows |
| CPU 型号与核心数 | ✅ 是 | 自动检测 |
| GPU 型号与数量 | ✅ 是 | nvidia-smi |
| GPU 显存 | ✅ 是 | nvidia-smi |
| CUDA 版本 | ✅ 是 | nvcc 或 nvidia-smi |
| 环境管理工具 | ✅ 是 | conda / uv / venv / docker 可用性 |
| PyTorch/TensorFlow/JAX | ✅ 是 | 已安装则记录版本 |
| SSH 可用性 | ✅ 是 | 检测 ssh 命令和密钥文件 |
| Git 可用性 | ✅ 是 | 检测 git 版本 |
| **SSH 主机地址** | ❌ 否 | 需用户手动填写 |
| **SSH 用户名** | ❌ 否 | 需用户手动填写 |
| **SSH 密码/密钥** | ❌ 否 | 需用户手动填写 |
| **作者信息** | ❌ 否 | 需用户手动填写 |
| **远程 conda 环境名** | ❌ 否 | 需用户手动填写 |

## 执行流程

```
Step 1: 定位目标项目
  → 显式指定项目路径，或复用当前活跃项目

Step 2: 运行环境探测
  → python scripts/env_probe.py --project {proj_dir}
  → 自动生成/覆盖 config/execution_env.yaml

Step 3: 向用户报告探测结果
  → 列出已自动填写的字段
  → 标红需手动补全的字段（SSH 配置、作者信息等）

Step 4: 提示用户补全
  → "以下字段无法自动探测，请手动填写："
  → execution_env.yaml 中的 ssh.host, ssh.user, ssh.identity_file
  → config/author_info.yaml 中的作者信息
```

## 输出

- 更新 `{project}/config/execution_env.yaml`（自动探测的字段已填写）
- 生成 `{project}/state/env_probe_report.yaml`（完整探测报告，供参考）

## 使用示例

```bash
# 探测当前环境并更新指定项目
cd {framework_root}
python scripts/env_probe.py --project projects/SemCom-Image-RL-20260512-135033

# 仅探测并查看结果，不写入
python scripts/env_probe.py --project projects/XXX --dry-run

# 输出原始探测报告到文件
python scripts/env_probe.py --output /tmp/my_env.yaml
```

## Key Rules

- **只覆盖自动可探测的字段**：不会覆盖用户已手动填写的 SSH 配置、作者信息等
- **执行前备份**：如 execution_env.yaml 已存在且包含用户手动填写的内容，先备份为 `execution_env.yaml.bak`
- **GPU 检测容错**：如 nvidia-smi 失败，hardware.gpu 标记为 "N/A"，不报错
- **框架检测容错**：如 PyTorch/TensorFlow 未安装，标记为 "not installed"，不报错
