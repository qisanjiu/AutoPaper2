"""SSH server registry and lease management for AutoPaper2.

The registry is framework-level state: projects consume allocated leases, but
the server library itself lives under ``config/`` and ``state/`` at the
framework root.  Secrets are intentionally not modeled here; use SSH agent,
identity files, or one-time onboarding bootstrap outside the registry.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

import yaml


DEFAULT_LEASE_HOURS = 7 * 24


class SSHRegistryError(RuntimeError):
    """Raised when an SSH registry operation cannot be completed."""


def framework_root_from(path: str | Path | None = None) -> Path:
    if path:
        return Path(path).resolve()
    return Path(__file__).parent.parent.resolve()


def registry_path(framework_root: str | Path | None = None) -> Path:
    return framework_root_from(framework_root) / "config" / "ssh_servers.yaml"


def leases_path(framework_root: str | Path | None = None) -> Path:
    return framework_root_from(framework_root) / "state" / "ssh_leases.yaml"


def events_path(framework_root: str | Path | None = None) -> Path:
    return framework_root_from(framework_root) / "state" / "ssh_events.jsonl"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(value: dt.datetime | None = None) -> str:
    return (value or _now()).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-_.") or "item"


def _read_yaml(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else default


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def default_registry() -> dict[str, Any]:
    return {
        "version": 1,
        "defaults": {
            "lease_hours": DEFAULT_LEASE_HOURS,
            "workspace_path_template": "{framework_root}/projects/{project_name}",
            "dataset_path_template": "{framework_root}/data/datasets",
            "sync_method": "rsync",
        },
        "servers": [],
    }


def load_registry(framework_root: str | Path | None = None) -> dict[str, Any]:
    return _read_yaml(registry_path(framework_root), default_registry())


def save_registry(data: dict[str, Any], framework_root: str | Path | None = None) -> None:
    if "version" not in data:
        data["version"] = 1
    if "servers" not in data or not isinstance(data["servers"], list):
        data["servers"] = []
    _write_yaml(registry_path(framework_root), data)


def init_registry(framework_root: str | Path | None = None, *, force: bool = False) -> Path:
    path = registry_path(framework_root)
    if path.exists() and not force:
        return path
    save_registry(default_registry(), framework_root)
    return path


def load_leases(framework_root: str | Path | None = None) -> dict[str, Any]:
    return _read_yaml(leases_path(framework_root), {"version": 1, "leases": []})


def save_leases(data: dict[str, Any], framework_root: str | Path | None = None) -> None:
    if "version" not in data:
        data["version"] = 1
    if "leases" not in data or not isinstance(data["leases"], list):
        data["leases"] = []
    _write_yaml(leases_path(framework_root), data)


def append_event(
    framework_root: str | Path | None,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    path = events_path(framework_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": _iso(), "event_type": event_type, **_redact(payload)}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if any(token in key.lower() for token in ("password", "token", "secret", "private_key")):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _servers(data: dict[str, Any]) -> list[dict[str, Any]]:
    servers = data.get("servers", [])
    return servers if isinstance(servers, list) else []


def list_servers(framework_root: str | Path | None = None) -> list[dict[str, Any]]:
    return list(_servers(load_registry(framework_root)))


def get_server(server_id: str, framework_root: str | Path | None = None) -> dict[str, Any]:
    for server in _servers(load_registry(framework_root)):
        if str(server.get("server_id", "")) == server_id:
            return server
    raise SSHRegistryError(f"Unknown SSH server_id: {server_id}")


def upsert_server(server: dict[str, Any], framework_root: str | Path | None = None) -> dict[str, Any]:
    server_id = str(server.get("server_id", "")).strip()
    if not server_id:
        raise SSHRegistryError("server_id is required")
    data = load_registry(framework_root)
    servers = _servers(data)
    normalized = {
        "server_id": server_id,
        "enabled": bool(server.get("enabled", True)),
        "host": str(server.get("host", "")).strip(),
        "user": str(server.get("user", "")).strip(),
        "port": int(server.get("port", 22) or 22),
        "ssh_alias": str(server.get("ssh_alias", "")).strip(),
        "auth_method": str(server.get("auth_method", "key") or "key"),
        "identity_file": str(server.get("identity_file", "")).strip(),
        "framework_root": str(server.get("framework_root", "~/AutoPaper2") or "~/AutoPaper2"),
        "workspace_path_template": str(
            server.get("workspace_path_template", "{framework_root}/projects/{project_name}")
            or "{framework_root}/projects/{project_name}"
        ),
        "dataset_path": str(server.get("dataset_path", "")).strip(),
        "env_manager": str(server.get("env_manager", "conda") or "conda"),
        "python_version": str(server.get("python_version", "3.10") or "3.10"),
        "cuda_version": str(server.get("cuda_version", "") or ""),
        "tags": server.get("tags", []) or [],
        "priority": int(server.get("priority", 0) or 0),
        "max_concurrent_projects": int(server.get("max_concurrent_projects", 1) or 1),
        "capabilities": server.get("capabilities", {}) or {},
        "health": server.get("health", {}) or {"status": "unknown"},
        "notes": str(server.get("notes", "") or ""),
        "updated_at": _iso(),
    }
    replaced = False
    for idx, existing in enumerate(servers):
        if str(existing.get("server_id", "")) == server_id:
            merged = {**existing, **normalized}
            servers[idx] = merged
            normalized = merged
            replaced = True
            break
    if not replaced:
        normalized.setdefault("created_at", _iso())
        servers.append(normalized)
    data["servers"] = servers
    save_registry(data, framework_root)
    append_event(framework_root, "server_upsert", {"server_id": server_id})
    return normalized


def remove_server(server_id: str, framework_root: str | Path | None = None) -> bool:
    data = load_registry(framework_root)
    servers = _servers(data)
    kept = [server for server in servers if str(server.get("server_id", "")) != server_id]
    if len(kept) == len(servers):
        return False
    data["servers"] = kept
    save_registry(data, framework_root)
    append_event(framework_root, "server_remove", {"server_id": server_id})
    return True


def _parse_iso(value: str) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except Exception:
        return None


def active_leases(framework_root: str | Path | None = None) -> list[dict[str, Any]]:
    data = load_leases(framework_root)
    active: list[dict[str, Any]] = []
    changed = False
    now = _now()
    for lease in data.get("leases", []) or []:
        status = str(lease.get("status", "")).lower()
        if status != "active":
            continue
        expires = _parse_iso(str(lease.get("expires_at", "")))
        if expires and expires <= now:
            lease["status"] = "expired"
            lease["expired_at"] = _iso(now)
            changed = True
            continue
        active.append(lease)
    if changed:
        save_leases(data, framework_root)
    return active


def _server_tags(server: dict[str, Any]) -> set[str]:
    return {str(tag).strip() for tag in server.get("tags", []) if str(tag).strip()}


def _server_gpu_count(server: dict[str, Any]) -> int:
    capabilities = server.get("capabilities", {}) if isinstance(server.get("capabilities"), dict) else {}
    gpu_count = capabilities.get("gpu_count")
    if gpu_count is None:
        gpus = capabilities.get("gpus", [])
        if isinstance(gpus, list):
            return len(gpus)
        return 0
    try:
        return int(gpu_count)
    except (TypeError, ValueError):
        return 0


def _server_max_vram_gb(server: dict[str, Any]) -> float:
    capabilities = server.get("capabilities", {}) if isinstance(server.get("capabilities"), dict) else {}
    values: list[float] = []
    for key in ("vram_gb", "max_vram_gb"):
        try:
            if capabilities.get(key) is not None:
                values.append(float(capabilities[key]))
        except (TypeError, ValueError):
            pass
    for gpu in capabilities.get("gpus", []) or []:
        if not isinstance(gpu, dict):
            continue
        raw = gpu.get("memory_total_mb") or gpu.get("vram_mb")
        try:
            if raw is not None:
                values.append(float(raw) / 1024.0)
        except (TypeError, ValueError):
            pass
    return max(values) if values else 0.0


def _server_is_candidate(
    server: dict[str, Any],
    *,
    required_tags: set[str],
    min_gpu_count: int,
    min_vram_gb: float | None,
    active_count: int,
) -> bool:
    if server.get("enabled") is False:
        return False
    health = server.get("health", {}) if isinstance(server.get("health"), dict) else {}
    if str(health.get("status", "")).lower() in {"down", "disabled", "unreachable"}:
        return False
    if required_tags and not required_tags.issubset(_server_tags(server)):
        return False
    if min_gpu_count and _server_gpu_count(server) < min_gpu_count:
        return False
    if min_vram_gb is not None and _server_max_vram_gb(server) < min_vram_gb:
        return False
    max_projects = int(server.get("max_concurrent_projects", 1) or 1)
    return active_count < max_projects


def select_server(
    framework_root: str | Path | None = None,
    *,
    server_id: str = "auto",
    min_gpu_count: int = 0,
    min_vram_gb: float | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    data = load_registry(framework_root)
    servers = _servers(data)
    if not servers:
        raise SSHRegistryError(f"No SSH servers registered in {registry_path(framework_root)}")

    active = active_leases(framework_root)
    counts: dict[str, int] = {}
    for lease in active:
        sid = str(lease.get("server_id", ""))
        counts[sid] = counts.get(sid, 0) + 1

    required_tags = {tag.strip() for tag in (tags or []) if tag.strip()}
    if server_id and server_id != "auto":
        server = get_server(server_id, framework_root)
        if not _server_is_candidate(
            server,
            required_tags=required_tags,
            min_gpu_count=min_gpu_count,
            min_vram_gb=min_vram_gb,
            active_count=counts.get(server_id, 0),
        ):
            raise SSHRegistryError(f"SSH server {server_id} does not satisfy allocation constraints")
        return server

    candidates = [
        server
        for server in servers
        if _server_is_candidate(
            server,
            required_tags=required_tags,
            min_gpu_count=min_gpu_count,
            min_vram_gb=min_vram_gb,
            active_count=counts.get(str(server.get("server_id", "")), 0),
        )
    ]
    if not candidates:
        raise SSHRegistryError("No SSH server satisfies allocation constraints")
    candidates.sort(
        key=lambda server: (
            int(server.get("priority", 0) or 0),
            -counts.get(str(server.get("server_id", "")), 0),
            _server_gpu_count(server),
            _server_max_vram_gb(server),
        ),
        reverse=True,
    )
    return candidates[0]


def _format_path_template(template: str, *, server: dict[str, Any], project_root: Path) -> str:
    project_name = project_root.name
    framework_root = str(server.get("framework_root", "~/AutoPaper2") or "~/AutoPaper2")
    return template.format(
        framework_root=framework_root.rstrip("/"),
        project_name=project_name,
        server_id=str(server.get("server_id", "")),
    )


def allocate_server(
    framework_root: str | Path | None,
    project_root: str | Path,
    *,
    server_id: str = "auto",
    min_gpu_count: int = 0,
    min_vram_gb: float | None = None,
    tags: list[str] | None = None,
    lease_hours: int | None = None,
    stage_scope: str = "M3-M4",
    reason: str = "project allocation",
) -> dict[str, Any]:
    root = framework_root_from(framework_root)
    project = Path(project_root).resolve()
    server = select_server(
        root,
        server_id=server_id,
        min_gpu_count=min_gpu_count,
        min_vram_gb=min_vram_gb,
        tags=tags,
    )
    registry = load_registry(root)
    defaults = registry.get("defaults", {}) if isinstance(registry.get("defaults"), dict) else {}
    lease_hours = int(lease_hours or defaults.get("lease_hours") or DEFAULT_LEASE_HOURS)
    workspace_template = str(
        server.get("workspace_path_template")
        or defaults.get("workspace_path_template")
        or "{framework_root}/projects/{project_name}"
    )
    dataset_template = str(defaults.get("dataset_path_template") or "{framework_root}/data/datasets")
    workspace_path = _format_path_template(workspace_template, server=server, project_root=project)
    dataset_path = str(server.get("dataset_path") or _format_path_template(dataset_template, server=server, project_root=project))
    now = _now()
    lease_id = f"lease_{now.strftime('%Y%m%d%H%M%S')}_{_slug(str(server['server_id']))}_{_slug(project.name)}"
    lease = {
        "lease_id": lease_id,
        "server_id": server["server_id"],
        "project_root": str(project),
        "project_name": project.name,
        "stage_scope": stage_scope,
        "status": "active",
        "allocated_at": _iso(now),
        "expires_at": _iso(now + dt.timedelta(hours=lease_hours)),
        "lease_hours": lease_hours,
        "workspace_path": workspace_path,
        "dataset_path": dataset_path,
        "gpu_ids": [],
        "cpu_cores": None,
        "reason": reason,
        "last_heartbeat": _iso(now),
    }
    data = load_leases(root)
    data.setdefault("leases", []).append(lease)
    save_leases(data, root)
    append_event(root, "lease_allocate", {"lease": lease})
    return lease


def allocate_server_pool(
    framework_root: str | Path | None,
    project_root: str | Path,
    *,
    server_ids: list[str] | None = None,
    count: int = 1,
    min_gpu_count: int = 0,
    min_vram_gb: float | None = None,
    tags: list[str] | None = None,
    lease_hours: int | None = None,
    stage_scope: str = "M3-M4",
    reason: str = "project resource pool allocation",
) -> list[dict[str, Any]]:
    """Allocate one or more SSH leases for a project resource pool.

    ``server_ids`` may contain explicit server ids and/or ``auto``.  The result
    is a list of normal lease objects that can be written into the project
    resource pool by ``apply_lease_pool_to_project``.
    """
    root = framework_root_from(framework_root)
    requested = [item for item in (server_ids or []) if str(item).strip()]
    if not requested:
        requested = ["auto"] * max(1, count)
    elif len(requested) < count:
        requested.extend(["auto"] * (count - len(requested)))

    leases: list[dict[str, Any]] = []
    for server_id in requested:
        leases.append(
            allocate_server(
                root,
                project_root,
                server_id=str(server_id),
                min_gpu_count=min_gpu_count,
                min_vram_gb=min_vram_gb,
                tags=tags,
                lease_hours=lease_hours,
                stage_scope=stage_scope,
                reason=reason,
            )
        )
    return leases


def get_lease(lease_id: str, framework_root: str | Path | None = None) -> dict[str, Any]:
    for lease in load_leases(framework_root).get("leases", []) or []:
        if str(lease.get("lease_id", "")) == lease_id:
            return lease
    raise SSHRegistryError(f"Unknown SSH lease_id: {lease_id}")


def release_lease(lease_id: str, framework_root: str | Path | None = None, *, reason: str = "manual release") -> dict[str, Any]:
    data = load_leases(framework_root)
    for lease in data.get("leases", []) or []:
        if str(lease.get("lease_id", "")) == lease_id:
            lease["status"] = "released"
            lease["released_at"] = _iso()
            lease["release_reason"] = reason
            save_leases(data, framework_root)
            append_event(framework_root, "lease_release", {"lease_id": lease_id, "reason": reason})
            return lease
    raise SSHRegistryError(f"Unknown SSH lease_id: {lease_id}")


def _set_nested(data: dict[str, Any], dotted: str, value: Any) -> None:
    target = data
    parts = dotted.split(".")
    for part in parts[:-1]:
        if not isinstance(target.get(part), dict):
            target[part] = {}
        target = target[part]
    target[parts[-1]] = value


def build_execution_env_overrides(server: dict[str, Any], lease: dict[str, Any]) -> dict[str, Any]:
    sync_method = "rsync"
    return {
        "execution.mode": "ssh",
        "execution.server_id": server["server_id"],
        "execution.lease_id": lease["lease_id"],
        "execution.sandbox.mode": "ssh_remote",
        "execution.ssh.server_id": server["server_id"],
        "execution.ssh.lease_id": lease["lease_id"],
        "execution.ssh.host": server.get("host", ""),
        "execution.ssh.user": server.get("user", ""),
        "execution.ssh.port": int(server.get("port", 22) or 22),
        "execution.ssh.ssh_alias": server.get("ssh_alias", ""),
        "execution.ssh.auth_method": server.get("auth_method", "key") or "key",
        "execution.ssh.identity_file": server.get("identity_file", ""),
        "execution.ssh.password": "",
        "execution.ssh.framework_root": server.get("framework_root", "~/AutoPaper2"),
        "execution.ssh.workspace_path": lease.get("workspace_path", ""),
        "execution.ssh.dataset_path": lease.get("dataset_path", ""),
        "execution.ssh.env_manager": server.get("env_manager", "conda"),
        "execution.ssh.python_version": server.get("python_version", "3.10"),
        "execution.ssh.cuda_version": server.get("cuda_version", ""),
        "execution.ssh.sync.method": sync_method,
        "execution.ssh.allocation.lease_id": lease["lease_id"],
        "execution.ssh.allocation.expires_at": lease.get("expires_at", ""),
        "execution.ssh.allocation.stage_scope": lease.get("stage_scope", ""),
    }


def _lease_resource_summary(server: dict[str, Any], lease: dict[str, Any]) -> dict[str, Any]:
    capabilities = server.get("capabilities", {}) if isinstance(server.get("capabilities"), dict) else {}
    gpus = capabilities.get("gpus", []) if isinstance(capabilities.get("gpus"), list) else []
    gpu_count = _server_gpu_count(server)
    return {
        "resource_id": f"ssh:{server['server_id']}",
        "kind": "ssh",
        "enabled": True,
        "server_id": server["server_id"],
        "lease_id": lease["lease_id"],
        "host": server.get("host", ""),
        "ssh_alias": server.get("ssh_alias", ""),
        "port": server.get("port", 22),
        "workspace_path": lease.get("workspace_path", ""),
        "dataset_path": lease.get("dataset_path", ""),
        "gpu_count": gpu_count,
        "gpu_ids": lease.get("gpu_ids") or [str(index) for index in range(gpu_count)],
        "cpu_cores": lease.get("cpu_cores") or capabilities.get("cpu_cores") or None,
        "gpus": gpus,
        "tags": server.get("tags", []) if isinstance(server.get("tags"), list) else [],
        "sync_required": True,
        "launcher": "ssh",
    }


def apply_lease_to_project(
    framework_root: str | Path | None,
    project_root: str | Path,
    lease_id: str,
) -> Path:
    root = framework_root_from(framework_root)
    project = Path(project_root).resolve()
    lease = get_lease(lease_id, root)
    server = get_server(str(lease["server_id"]), root)
    config_path = project / "config" / "execution_env.yaml"
    if not config_path.exists():
        raise SSHRegistryError(f"Project execution config not found: {config_path}")
    data = _read_yaml(config_path, {})
    overrides = build_execution_env_overrides(server, lease)
    for key, value in overrides.items():
        _set_nested(data, key, value)
    _write_yaml(config_path, data)
    allocation_path = project / "state" / "ssh_allocation.yaml"
    allocation_path.parent.mkdir(parents=True, exist_ok=True)
    allocation_path.write_text(
        yaml.safe_dump(
            {
                "server": _redact(server),
                "lease": _redact(lease),
                "execution_env": str(config_path),
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    append_event(root, "project_apply_lease", {"project_root": str(project), "lease_id": lease_id})
    return config_path


def apply_lease_pool_to_project(
    framework_root: str | Path | None,
    project_root: str | Path,
    lease_ids: list[str],
    *,
    include_local: bool = True,
) -> Path:
    root = framework_root_from(framework_root)
    project = Path(project_root).resolve()
    config_path = project / "config" / "execution_env.yaml"
    if not config_path.exists():
        raise SSHRegistryError(f"Project execution config not found: {config_path}")

    resources: list[dict[str, Any]] = []
    allocation_entries: list[dict[str, Any]] = []
    for lease_id in lease_ids:
        lease = get_lease(lease_id, root)
        server = get_server(str(lease["server_id"]), root)
        resources.append(_lease_resource_summary(server, lease))
        allocation_entries.append({"server": _redact(server), "lease": _redact(lease)})

    data = _read_yaml(config_path, {})
    _set_nested(data, "execution.resource_optimization.resource_pool.enabled", True)
    _set_nested(data, "execution.resource_optimization.resource_pool.include_local", include_local)
    _set_nested(data, "execution.resource_optimization.resource_pool.allow_local_and_ssh", include_local)
    _set_nested(data, "execution.resource_optimization.resource_pool.resources", resources)
    _write_yaml(config_path, data)

    pool_path = project / "state" / "ssh_resource_pool.yaml"
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    pool_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "include_local": include_local,
                "resources": resources,
                "allocations": allocation_entries,
                "execution_env": str(config_path),
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    append_event(root, "project_apply_lease_pool", {"project_root": str(project), "lease_ids": lease_ids})
    return config_path


def validate_project_lease(framework_root: str | Path | None, project_root: str | Path) -> tuple[bool, str]:
    project = Path(project_root).resolve()
    config_path = project / "config" / "execution_env.yaml"
    if not config_path.exists():
        return False, "config/execution_env.yaml not found"
    data = _read_yaml(config_path, {})
    execution = data.get("execution", {}) if isinstance(data.get("execution"), dict) else {}
    lease_id = execution.get("lease_id") or (execution.get("ssh", {}) or {}).get("lease_id")
    server_id = execution.get("server_id") or (execution.get("ssh", {}) or {}).get("server_id")
    if not lease_id or not server_id:
        return False, "execution.server_id and execution.lease_id are required for managed SSH mode"
    try:
        lease = get_lease(str(lease_id), framework_root)
    except SSHRegistryError as exc:
        return False, str(exc)
    if str(lease.get("server_id", "")) != str(server_id):
        return False, "lease server_id does not match project execution.server_id"
    if str(lease.get("project_root", "")) != str(project):
        return False, "lease project_root does not match this project"
    if str(lease.get("status", "")).lower() != "active":
        return False, f"lease status is {lease.get('status')}"
    expires = _parse_iso(str(lease.get("expires_at", "")))
    if expires and expires <= _now():
        return False, f"lease expired at {lease.get('expires_at')}"
    return True, "managed SSH lease is active"


def ssh_target(server: dict[str, Any]) -> str:
    alias = str(server.get("ssh_alias", "")).strip()
    if alias:
        return alias
    user = str(server.get("user", "")).strip()
    host = str(server.get("host", "")).strip()
    if not host:
        raise SSHRegistryError("server host or ssh_alias is required")
    return f"{user}@{host}" if user else host


def ssh_base_command(server: dict[str, Any], *, batch: bool = True) -> list[str]:
    cmd = ["ssh"]
    port = int(server.get("port", 22) or 22)
    if port:
        cmd.extend(["-p", str(port)])
    identity = str(server.get("identity_file", "")).strip()
    if identity:
        cmd.extend(["-i", identity])
    if batch:
        cmd.extend(["-o", "BatchMode=yes", "-o", "ConnectTimeout=15"])
    cmd.append(ssh_target(server))
    return cmd


def run_remote(
    server: dict[str, Any],
    command: str,
    *,
    timeout: int = 60,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    full_cmd = [*ssh_base_command(server), command]
    result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if check and result.returncode != 0:
        raise SSHRegistryError(result.stderr.strip() or result.stdout.strip() or f"ssh exited {result.returncode}")
    return result


def probe_server(server_id: str, framework_root: str | Path | None = None, *, timeout: int = 60) -> dict[str, Any]:
    root = framework_root_from(framework_root)
    server = get_server(server_id, root)
    remote_framework_root = str(server.get("framework_root", "~/AutoPaper2") or "~/AutoPaper2")
    dataset_path = str(server.get("dataset_path") or f"{remote_framework_root.rstrip('/')}/data/datasets")
    command = (
        "printf '__AP2_HOSTNAME__\\n'; hostname; "
        "printf '__AP2_UNAME__\\n'; uname -srm; "
        "printf '__AP2_PYTHON__\\n'; (python3 --version 2>/dev/null || python --version 2>/dev/null || true); "
        "printf '__AP2_CONDA__\\n'; (conda --version 2>/dev/null || true); "
        "printf '__AP2_UV__\\n'; (uv --version 2>/dev/null || true); "
        "printf '__AP2_DOCKER__\\n'; (docker --version 2>/dev/null || true); "
        "printf '__AP2_GPU__\\n'; "
        "(nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader,nounits 2>/dev/null || true); "
        "printf '__AP2_DATASETS__\\n'; "
        f"DATASET_PATH={shlex.quote(dataset_path)}; "
        "if [ -d \"$DATASET_PATH\" ]; then "
        "find \"$DATASET_PATH\" -mindepth 1 -maxdepth 1 -type d -printf '%f\\n' 2>/dev/null "
        "|| ls -1 \"$DATASET_PATH\" 2>/dev/null || true; "
        "fi"
    )
    result = run_remote(server, command, timeout=timeout)
    parsed = _parse_probe_stdout(result.stdout, dataset_path=dataset_path)
    health = {
        "status": "ok" if result.returncode == 0 else "unreachable",
        "last_probe_at": _iso(),
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    data = load_registry(root)
    for item in _servers(data):
        if str(item.get("server_id", "")) == server_id:
            item["health"] = health
            if result.returncode == 0:
                capabilities = item.get("capabilities", {}) if isinstance(item.get("capabilities"), dict) else {}
                capabilities.update(parsed.get("capabilities", {}))
                item["capabilities"] = capabilities
                item["dataset_cache"] = parsed.get("dataset_cache", {})
            item["updated_at"] = _iso()
            break
    save_registry(data, root)
    append_event(root, "server_probe", {"server_id": server_id, "health": health})
    return {**health, **parsed}


def doctor_server(server_id: str, framework_root: str | Path | None = None, *, timeout: int = 60) -> dict[str, Any]:
    root = framework_root_from(framework_root)
    server = get_server(server_id, root)
    result = run_remote(server, "echo autopaper2-ssh-ok", timeout=timeout)
    report = {
        "server_id": server_id,
        "ok": result.returncode == 0 and "autopaper2-ssh-ok" in result.stdout,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    append_event(root, "server_doctor", report)
    return report


def _parse_probe_stdout(stdout: str, *, dataset_path: str) -> dict[str, Any]:
    sections: dict[str, list[str]] = {}
    current = ""
    marker_prefix = "__AP2_"
    for raw in stdout.splitlines():
        line = raw.strip()
        if line.startswith(marker_prefix) and line.endswith("__"):
            current = line.strip("_").lower().replace("ap2_", "")
            sections.setdefault(current, [])
            continue
        if current:
            sections.setdefault(current, []).append(line)

    gpus: list[dict[str, Any]] = []
    for line in sections.get("gpu", []):
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            index = int(parts[0])
        except ValueError:
            index = len(gpus)
        try:
            memory_total_mb = int(float(parts[2]))
        except ValueError:
            memory_total_mb = None
        gpu = {
            "index": index,
            "name": parts[1],
            "memory_total_mb": memory_total_mb,
        }
        if len(parts) >= 4:
            gpu["driver_version"] = parts[3]
        gpus.append(gpu)

    datasets = [line for line in sections.get("datasets", []) if line]
    max_vram_gb = 0.0
    for gpu in gpus:
        memory = gpu.get("memory_total_mb")
        if isinstance(memory, int):
            max_vram_gb = max(max_vram_gb, round(memory / 1024.0, 2))

    return {
        "remote": {
            "hostname": "\n".join(sections.get("hostname", [])).strip(),
            "uname": "\n".join(sections.get("uname", [])).strip(),
            "python": "\n".join(sections.get("python", [])).strip(),
            "conda": "\n".join(sections.get("conda", [])).strip(),
            "uv": "\n".join(sections.get("uv", [])).strip(),
            "docker": "\n".join(sections.get("docker", [])).strip(),
        },
        "capabilities": {
            "gpu_count": len(gpus),
            "max_vram_gb": max_vram_gb,
            "gpus": gpus,
        },
        "dataset_cache": {
            "path": dataset_path,
            "datasets": datasets,
            "dataset_count": len(datasets),
            "last_scanned_at": _iso(),
        },
    }
