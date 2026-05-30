---
name: AutoPaper2_ssh_ops
description: >
  AutoPaper2 SSH server registry and remote execution infrastructure skill.
  Use when the user wants to add/list/probe SSH servers, allocate a managed
  server lease to a project, prepare remote workspaces, sync project files, or
  route SSH operations to the dedicated SSH Ops subagent.
argument-hint: [server|lease|probe|doctor|sync|project path]
skill_role: orchestrator
---

> **ORCHESTRATOR MANIFEST ⚠️ 绝对不可违反**
>
> **你（当前主 Agent）的身份是 ORCHESTRATOR / CONDUCTOR。**
> SSH 操作可以由专门的 SSH Ops subagent 执行；主 Agent 不得借 SSH
> 基础设施操作直接写任何 stage 内容或 review verdict。
>
> ## 你的唯一合法行为
>
> 1. 读取 `config/ssh_servers.yaml`、`state/ssh_leases.yaml` 和项目 `config/execution_env.yaml`
> 2. 需要人工执行远程操作时，生成 dispatch packet：
>    `python scripts/state_manager.py dispatch ssh <operation> --write`
> 3. 将 packet 路径委派给 `docs/AGENTS/ssh/AGENT.md`
> 4. 等待 SSH Ops Agent 返回 server_id、lease_id、changed paths 和 redacted evidence
> 5. 继续由 Conductor 编排 M3/M4，不直接写实验 stage 输出
>
> ## 违规检测
>
> 如果你准备写入 `knowledge/M*/`、`drafts/`、`knowledge/reviews/` 或
> `artifacts/paper.*`，你正在违规。SSH Ops 只允许管理基础设施文件。
>
> ---

# AutoPaper2 SSH Ops — 服务器库与远程执行基础设施

## 触发条件

- 用户要求“管理 SSH 服务器库”“添加服务器”“分配服务器”“远程执行”“同步到服务器”
- 项目创建时使用 `--server-id` 或 `--server-id auto`
- M3/M4 即将进入 SSH 远程实验，但项目没有有效 lease
- 需要验证远程 GPU/conda/rsync/workspace 是否可用

## Canonical Files

- `config/ssh_servers.yaml`: 框架级服务器库
- `state/ssh_leases.yaml`: 框架级租约状态
- `state/ssh_events.jsonl`: SSH 操作事件流
- `{project}/config/execution_env.yaml`: 项目执行配置
- `{project}/state/ssh_allocation.yaml`: 项目分配摘要
- `docs/AGENTS/ssh/AGENT.md`: SSH Ops subagent prompt

## Common Commands

```bash
python scripts/ssh_manager.py server list
python scripts/ssh_manager.py server add <server_id> --host <host> --user <user>
python scripts/ssh_manager.py bootstrap-key <server_id>
python scripts/ssh_manager.py probe <server_id>
python scripts/ssh_manager.py doctor <server_id>
python scripts/ssh_manager.py lease alloc --project <project> --server-id auto --apply
python scripts/ssh_manager.py lease release <lease_id>
python scripts/state_manager.py dispatch ssh alloc --project <project> --write
```

## Rules

1. SSH server registry must never store passwords, private key contents, tokens, or API keys.
2. One-time SSH passwords may be used only for `bootstrap-key`; never persist them.
3. `probe` should update GPU capabilities and `dataset_cache.datasets` for server selection.
4. Project SSH mode should prefer managed `server_id` + `lease_id` over ad hoc host/user fields.
5. `execution.mode == ssh` must use `execution.sandbox.mode == ssh_remote`.
6. Experiment Agent consumes a valid lease; it should not choose servers itself.
7. SSH Ops Agent may prepare infrastructure and sync files, but it must not write experiment findings or review verdicts.
