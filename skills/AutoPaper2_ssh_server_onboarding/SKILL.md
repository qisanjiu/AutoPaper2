---
name: AutoPaper2_ssh_server_onboarding
description: >
  Guided AutoPaper2 SSH server creation skill. Use when the user wants to add
  a new remote server/GPU machine to the AutoPaper2 SSH server library, collect
  required host/user/port/password bootstrap/resource metadata, push a
  dedicated SSH key, validate SSH login, probe remote GPU/software capabilities,
  scan stored datasets, and show how to allocate the server to future projects.
argument-hint: [new server id / host / user]
skill_role: orchestrator
---

> **ORCHESTRATOR MANIFEST ⚠️ 绝对不可违反**
>
> You are ORCHESTRATOR / CONDUCTOR. This skill only manages framework-level SSH
> server configuration and validation. It must not write stage outputs,
> review verdicts, paper artifacts, or experiment claims.
>
> Allowed writes:
> - `config/ssh_servers.yaml`
> - `state/ssh_events.jsonl`
> - `state/ssh_leases.yaml` only when the user also requests allocation
> - project `config/execution_env.yaml` only when applying an allocation
>
> Forbidden writes:
> - `knowledge/M*/`
> - `drafts/`
> - `knowledge/reviews/`
> - `artifacts/paper.*`
>
> Never store passwords, private key contents, API keys, or tokens in any file.
> Passwords may be used only once to push a public key, then discarded.

# SSH Server Onboarding

## Goal

Guide the user through adding one new SSH server to AutoPaper2's managed server library.

Canonical command:

```bash
python scripts/ssh_manager.py server add <server_id> \
  --host <host> \
  --user <user> \
  --port 22 \
  --identity-file ~/.ssh/autopaper2_id_ed25519 \
  --remote-framework-root ~/AutoPaper2 \
  --gpu-count <n> \
  --vram-gb <gb> \
  --tags gpu,cuda \
  --priority 10 \
  --max-concurrent-projects 1
```

## Workflow

1. Confirm framework root is the AutoPaper2 root.
2. Collect required fields:
   - `server_id`: stable short alias, e.g. `lab-a4090`
   - `host`: DNS name or IP
   - `user`: SSH username
   - `port`: default `22`
   - `password`: one-time SSH password for key bootstrap; never write it to disk or logs
   - `identity_file`: dedicated private key path; default `~/.ssh/autopaper2_id_ed25519`
3. Collect scheduling metadata:
   - `gpu_count`
   - `vram_gb`
   - `tags`: e.g. `gpu,cuda,a4090`
   - `priority`: higher means preferred by `--server-id auto`
   - `max_concurrent_projects`: default `1`
4. Collect remote layout:
   - `remote_framework_root`: default `~/AutoPaper2`
   - `workspace_template`: default `{framework_root}/projects/{project_name}`
   - `dataset_path`: optional; default is `{framework_root}/data/datasets`
   - `env_manager`: default `conda`
   - `python_version`: default `3.10`
   - `cuda_version`: optional
5. Run `server add` with key auth metadata. Do not store the password:
   ```bash
   python scripts/ssh_manager.py server add <server_id> \
     --host <host> --user <user> --port <port> \
     --identity-file ~/.ssh/autopaper2_id_ed25519 \
     --remote-framework-root ~/AutoPaper2 \
     --dataset-path ~/AutoPaper2/data/datasets \
     --gpu-count <n> --vram-gb <gb> --tags gpu,cuda
   ```
6. Push the dedicated public key with the one-time password:
   ```bash
   python scripts/ssh_manager.py bootstrap-key <server_id> \
     --identity-file ~/.ssh/autopaper2_id_ed25519
   ```
   In automated runs, use `--password-stdin` and pass the password through stdin only.
7. Probe server capabilities and stored datasets:
   ```bash
   python scripts/ssh_manager.py doctor <server_id>
   python scripts/ssh_manager.py probe <server_id>
   python scripts/ssh_manager.py server show <server_id>
   ```
   `probe` must update the server entry with:
   - `capabilities.gpus`
   - `capabilities.gpu_count`
   - `capabilities.max_vram_gb`
   - `dataset_cache.path`
   - `dataset_cache.datasets`
8. Show project allocation examples:
   ```bash
   python scripts/state_manager.py create "Topic" "Project Name" --server-id <server_id>
   python scripts/state_manager.py create "Topic" "Project Name" --server-id auto --server-tags gpu --min-gpu-count 1
   python scripts/state_manager.py create "Topic" "Project Name" --server-ids <server_a>,<server_b>
   python scripts/state_manager.py create "Topic" "Project Name" --server-pool-count 2 --server-tags gpu --min-gpu-count 1
   python scripts/ssh_manager.py lease alloc-pool --project <project> --server-ids <server_a>,<server_b> --apply
   python scripts/ssh_manager.py lease alloc-pool --project <project> --count 2 --tags gpu --min-gpu-count 1 --apply
   ```

## Interaction Rules

- If all required fields are present in the user request, execute the add command and key bootstrap flow directly.
- If required fields are missing, ask only for the missing required fields in one concise question.
- You may ask for a one-time SSH password only for `bootstrap-key`; never echo it back and never persist it.
- If the user gives an SSH config alias, use `--ssh-alias <alias>` and still ask for `server_id`; `host/user/port` may be left blank if the alias works.
- If `doctor`, `bootstrap-key`, or `probe` fails because of network/SSH restrictions, report the exact command that failed and the next manual check.

## Validation Criteria

The server is considered onboarded when:

- `config/ssh_servers.yaml` contains the server.
- `python scripts/ssh_manager.py server show <server_id>` succeeds.
- `bootstrap-key` either succeeds or a manual key setup blocker is explicit.
- `doctor` succeeds after key bootstrap or the failure reason is explicit and actionable.
- `probe` records remote GPU/software capabilities.
- `probe` records `dataset_cache.datasets` or reports why dataset path scanning is blocked.

## Output Summary

Return:

```markdown
## SSH Server Added

- server_id:
- host_or_alias:
- user:
- identity_file:
- tags:
- gpu_count:
- vram_gb:
- registry_path:
- doctor_status:
- probe_status:
- datasets:
- allocation_example:
```
