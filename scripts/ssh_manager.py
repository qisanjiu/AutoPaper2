#!/usr/bin/env python3
"""Manage AutoPaper2 SSH server registry, leases, and basic remote operations."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_framework_root = Path(__file__).parent.parent.resolve()
if str(_framework_root) not in sys.path:
    sys.path.insert(0, str(_framework_root))

import yaml

from spiral.ssh_registry import (
    SSHRegistryError,
    active_leases,
    allocate_server,
    apply_lease_to_project,
    doctor_server,
    get_lease,
    get_server,
    init_registry,
    list_servers,
    load_leases,
    probe_server,
    registry_path,
    release_lease,
    remove_server,
    run_remote,
    upsert_server,
)


def _print_yaml(data: Any) -> None:
    print(yaml.safe_dump(data, allow_unicode=True, sort_keys=False).rstrip())


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _server_from_args(args: argparse.Namespace) -> dict[str, Any]:
    capabilities: dict[str, Any] = {}
    if args.gpu_count is not None:
        capabilities["gpu_count"] = args.gpu_count
    if args.vram_gb is not None:
        capabilities["vram_gb"] = args.vram_gb
    server = {
        "server_id": args.server_id,
        "enabled": not args.disabled,
        "host": args.host or "",
        "user": args.user or "",
        "port": args.port,
        "ssh_alias": args.ssh_alias or "",
        "auth_method": args.auth_method,
        "identity_file": args.identity_file or "",
        "framework_root": args.remote_framework_root,
        "workspace_path_template": args.workspace_template,
        "dataset_path": args.dataset_path or "",
        "env_manager": args.env_manager,
        "python_version": args.python_version,
        "cuda_version": args.cuda_version or "",
        "tags": _split_csv(args.tags),
        "priority": args.priority,
        "max_concurrent_projects": args.max_concurrent_projects,
        "capabilities": capabilities,
        "notes": args.notes or "",
    }
    return server


def _cmd_server(args: argparse.Namespace) -> int:
    if args.server_cmd == "init":
        path = init_registry(args.framework_root, force=args.force)
        print(f"[SSH] Registry ready: {path}")
        return 0
    if args.server_cmd == "list":
        _print_yaml({"registry": str(registry_path(args.framework_root)), "servers": list_servers(args.framework_root)})
        return 0
    if args.server_cmd == "show":
        _print_yaml(get_server(args.server_id, args.framework_root))
        return 0
    if args.server_cmd == "add":
        server = upsert_server(_server_from_args(args), args.framework_root)
        print(f"[SSH] Server saved: {server['server_id']}")
        _print_yaml(server)
        return 0
    if args.server_cmd == "remove":
        removed = remove_server(args.server_id, args.framework_root)
        if removed:
            print(f"[SSH] Server removed: {args.server_id}")
            return 0
        print(f"[SSH] Server not found: {args.server_id}", file=sys.stderr)
        return 1
    raise SSHRegistryError(f"Unknown server command: {args.server_cmd}")


def _cmd_lease(args: argparse.Namespace) -> int:
    if args.lease_cmd == "list":
        leases = active_leases(args.framework_root) if args.active else load_leases(args.framework_root).get("leases", [])
        _print_yaml({"leases": leases})
        return 0
    if args.lease_cmd == "show":
        _print_yaml(get_lease(args.lease_id, args.framework_root))
        return 0
    if args.lease_cmd == "alloc":
        lease = allocate_server(
            args.framework_root,
            args.project,
            server_id=args.server_id,
            min_gpu_count=args.min_gpu_count,
            min_vram_gb=args.min_vram_gb,
            tags=_split_csv(args.tags),
            lease_hours=args.lease_hours,
            stage_scope=args.stage_scope,
            reason=args.reason,
        )
        if args.apply:
            apply_lease_to_project(args.framework_root, args.project, lease["lease_id"])
        print(f"[SSH] Lease allocated: {lease['lease_id']}")
        _print_yaml(lease)
        return 0
    if args.lease_cmd == "release":
        lease = release_lease(args.lease_id, args.framework_root, reason=args.reason)
        print(f"[SSH] Lease released: {lease['lease_id']}")
        return 0
    if args.lease_cmd == "apply":
        path = apply_lease_to_project(args.framework_root, args.project, args.lease_id)
        print(f"[SSH] Applied lease to {path}")
        return 0
    raise SSHRegistryError(f"Unknown lease command: {args.lease_cmd}")


def _cmd_probe(args: argparse.Namespace) -> int:
    report = probe_server(args.server_id, args.framework_root, timeout=args.timeout)
    _print_yaml(report)
    return 0 if report.get("status") == "ok" else 1


def _cmd_bootstrap_key(args: argparse.Namespace) -> int:
    server = get_server(args.server_id, args.framework_root)
    identity = Path(args.identity_file or server.get("identity_file") or "~/.ssh/autopaper2_id_ed25519").expanduser()
    public_key = identity.with_suffix(identity.suffix + ".pub") if identity.suffix else Path(str(identity) + ".pub")
    if not identity.exists():
        identity.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-N",
                "",
                "-C",
                f"autopaper2-{args.server_id}",
                "-f",
                str(identity),
            ],
            check=True,
        )
    if not public_key.exists():
        raise SSHRegistryError(f"public key not found after key generation: {public_key}")

    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("SSH password for one-time key bootstrap: ")
    if not password:
        raise SSHRegistryError("password is required for bootstrap-key")

    if not shutil_which("sshpass"):
        raise SSHRegistryError("sshpass is required for password bootstrap; install sshpass or configure key login manually")
    if not shutil_which("ssh-copy-id"):
        raise SSHRegistryError("ssh-copy-id is required for password bootstrap")

    target_host = server.get("host")
    target_user = server.get("user")
    target = server.get("ssh_alias") or (f"{target_user}@{target_host}" if target_user else str(target_host))
    if not target or target == "None":
        raise SSHRegistryError("server host/user or ssh_alias is required before bootstrap-key")
    port = str(server.get("port", 22) or 22)
    env = os.environ.copy()
    env["SSHPASS"] = password
    result = subprocess.run(
        ["sshpass", "-e", "ssh-copy-id", "-p", port, "-i", str(public_key), target],
        capture_output=True,
        text=True,
        env=env,
        timeout=args.timeout,
        check=False,
    )
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
        return result.returncode

    updated = dict(server)
    updated["auth_method"] = "key"
    updated["identity_file"] = str(identity)
    upsert_server(updated, args.framework_root)
    doctor = doctor_server(args.server_id, args.framework_root, timeout=args.timeout)
    _print_yaml(
        {
            "server_id": args.server_id,
            "identity_file": str(identity),
            "public_key": str(public_key),
            "ssh_copy_id": "ok",
            "doctor": doctor,
        }
    )
    return 0 if doctor.get("ok") else 1


def _cmd_doctor(args: argparse.Namespace) -> int:
    report = doctor_server(args.server_id, args.framework_root, timeout=args.timeout)
    _print_yaml(report)
    return 0 if report.get("ok") else 1


def shutil_which(command: str) -> str | None:
    from shutil import which

    return which(command)


def _cmd_exec(args: argparse.Namespace) -> int:
    server = get_server(args.server_id, args.framework_root)
    command = " ".join(args.command)
    if not command:
        print("[ERROR] exec requires a command after --", file=sys.stderr)
        return 2
    result = run_remote(server, command, timeout=args.timeout)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    return result.returncode


def _cmd_sync(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    config_path = project / "config" / "execution_env.yaml"
    if not config_path.exists():
        raise SSHRegistryError(f"Project execution config not found: {config_path}")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    execution = data.get("execution", {}) if isinstance(data.get("execution"), dict) else {}
    ssh = execution.get("ssh", {}) if isinstance(execution.get("ssh"), dict) else {}
    server_id = ssh.get("server_id") or execution.get("server_id") or args.server_id
    if not server_id:
        raise SSHRegistryError("server_id is required (project execution.server_id missing)")
    server = get_server(str(server_id), args.framework_root)
    target_host = ssh.get("host") or server.get("host")
    target_user = ssh.get("user") or server.get("user")
    target = server.get("ssh_alias") or (f"{target_user}@{target_host}" if target_user else str(target_host))
    if not target or target == "None":
        raise SSHRegistryError("ssh_alias or host is required for sync")
    port = int(ssh.get("port") or server.get("port") or 22)
    identity = ssh.get("identity_file") or server.get("identity_file") or ""
    remote_path = ssh.get("workspace_path")
    if not remote_path:
        raise SSHRegistryError("execution.ssh.workspace_path is required for sync")

    ssh_backend = ["ssh", "-p", str(port)]
    if identity:
        ssh_backend.extend(["-i", str(identity)])
    ssh_backend_value = " ".join(ssh_backend)
    if args.mode == "push":
        source = f"{project}/"
        dest = f"{target}:{remote_path}/"
    else:
        source = f"{target}:{remote_path}/experiments/"
        dest = str(project / "experiments")
        Path(dest).mkdir(parents=True, exist_ok=True)
    command = ["rsync", "-az", "--partial", "-e", ssh_backend_value]
    sync_config = ssh.get("sync", {}) if isinstance(ssh.get("sync"), dict) else {}
    for pattern in sync_config.get("excludes", []) or []:
        command.append(f"--exclude={pattern}")
    command.extend([source, dest])
    print("[SSH] Running:", " ".join(command))
    result = subprocess.run(command, text=True)
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework-root", default=str(_framework_root), help="AutoPaper2 framework root")
    sub = parser.add_subparsers(dest="cmd", required=True)

    server = sub.add_parser("server", help="Manage registered SSH servers")
    server_sub = server.add_subparsers(dest="server_cmd", required=True)
    server_init = server_sub.add_parser("init", help="Create config/ssh_servers.yaml if missing")
    server_init.add_argument("--force", action="store_true", help="Overwrite existing registry")
    server_sub.add_parser("list", help="List servers")
    show = server_sub.add_parser("show", help="Show one server")
    show.add_argument("server_id")
    remove = server_sub.add_parser("remove", help="Remove one server")
    remove.add_argument("server_id")
    add = server_sub.add_parser("add", help="Add or update a server")
    add.add_argument("server_id")
    add.add_argument("--host", default="")
    add.add_argument("--user", default="")
    add.add_argument("--port", type=int, default=22)
    add.add_argument("--ssh-alias", default="")
    add.add_argument("--auth-method", default="key", choices=["key", "password"])
    add.add_argument("--identity-file", default="")
    add.add_argument("--remote-framework-root", default="~/AutoPaper2")
    add.add_argument("--workspace-template", default="{framework_root}/projects/{project_name}")
    add.add_argument("--dataset-path", default="")
    add.add_argument("--env-manager", default="conda")
    add.add_argument("--python-version", default="3.10")
    add.add_argument("--cuda-version", default="")
    add.add_argument("--tags", default="")
    add.add_argument("--priority", type=int, default=0)
    add.add_argument("--max-concurrent-projects", type=int, default=1)
    add.add_argument("--gpu-count", type=int, default=None)
    add.add_argument("--vram-gb", type=float, default=None)
    add.add_argument("--notes", default="")
    add.add_argument("--disabled", action="store_true")

    lease = sub.add_parser("lease", help="Manage SSH project leases")
    lease_sub = lease.add_subparsers(dest="lease_cmd", required=True)
    lease_list = lease_sub.add_parser("list", help="List leases")
    lease_list.add_argument("--active", action="store_true")
    lease_show = lease_sub.add_parser("show", help="Show lease")
    lease_show.add_argument("lease_id")
    alloc = lease_sub.add_parser("alloc", help="Allocate a server to a project")
    alloc.add_argument("--project", required=True)
    alloc.add_argument("--server-id", default="auto")
    alloc.add_argument("--tags", default="")
    alloc.add_argument("--min-gpu-count", type=int, default=0)
    alloc.add_argument("--min-vram-gb", type=float, default=None)
    alloc.add_argument("--lease-hours", type=int, default=None)
    alloc.add_argument("--stage-scope", default="M3-M4")
    alloc.add_argument("--reason", default="project allocation")
    alloc.add_argument("--apply", action="store_true", help="Write lease into project config/execution_env.yaml")
    release = lease_sub.add_parser("release", help="Release lease")
    release.add_argument("lease_id")
    release.add_argument("--reason", default="manual release")
    apply = lease_sub.add_parser("apply", help="Apply an existing lease to a project")
    apply.add_argument("--project", required=True)
    apply.add_argument("--lease-id", required=True)

    probe = sub.add_parser("probe", help="Probe remote server and update health")
    probe.add_argument("server_id")
    probe.add_argument("--timeout", type=int, default=60)

    bootstrap = sub.add_parser("bootstrap-key", help="Use a one-time password to push a dedicated SSH public key")
    bootstrap.add_argument("server_id")
    bootstrap.add_argument("--identity-file", default="~/.ssh/autopaper2_id_ed25519")
    bootstrap.add_argument("--password-stdin", action="store_true", help="Read one-time SSH password from stdin")
    bootstrap.add_argument("--timeout", type=int, default=60)

    doctor = sub.add_parser("doctor", help="Verify SSH login")
    doctor.add_argument("server_id")
    doctor.add_argument("--timeout", type=int, default=60)

    exec_p = sub.add_parser("exec", help="Run a remote command")
    exec_p.add_argument("server_id")
    exec_p.add_argument("--timeout", type=int, default=3600)
    exec_p.add_argument("command", nargs=argparse.REMAINDER)

    sync = sub.add_parser("sync", help="Sync project files with allocated server")
    sync.add_argument("mode", choices=["push", "pull"])
    sync.add_argument("--project", required=True)
    sync.add_argument("--server-id", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.cmd == "server":
            return _cmd_server(args)
        if args.cmd == "lease":
            return _cmd_lease(args)
        if args.cmd == "probe":
            return _cmd_probe(args)
        if args.cmd == "bootstrap-key":
            return _cmd_bootstrap_key(args)
        if args.cmd == "doctor":
            return _cmd_doctor(args)
        if args.cmd == "exec":
            return _cmd_exec(args)
        if args.cmd == "sync":
            return _cmd_sync(args)
    except SSHRegistryError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired as exc:
        print(f"[ERROR] command timed out after {exc.timeout}s", file=sys.stderr)
        return 124
    except KeyboardInterrupt:
        return 130
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
