#!/usr/bin/env python3
"""Resource planning and monitoring helpers for AutoPaper2 experiments.

The script is intentionally dependency-light so it can run before the project
environment is fully installed.  M3S01 uses ``plan`` to create a durable
resource plan; M3S03 can use ``run`` or ``monitor`` to record utilization
evidence for each experiment run.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml


def _run(cmd: list[str], timeout: int = 20) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _memory_total_mb() -> int | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2:
                return int(parts[1]) // 1024
    return None


def _memory_available_mb() -> int | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("MemAvailable:"):
            parts = line.split()
            if len(parts) >= 2:
                return int(parts[1]) // 1024
    return None


def detect_cpu() -> dict[str, Any]:
    cpu_count = os.cpu_count() or 1
    model = ""
    rc, out, _ = _run(["lscpu"])
    if rc == 0:
        for line in out.splitlines():
            if line.startswith("Model name:"):
                model = line.split(":", 1)[1].strip()
                break
    return {
        "cores": cpu_count,
        "model": model or "unknown",
        "memory_total_mb": _memory_total_mb(),
    }


def detect_gpus() -> list[dict[str, Any]]:
    query = "index,name,memory.total"
    rc, out, _ = _run(
        ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
        timeout=10,
    )
    if rc != 0 or not out:
        return []
    devices: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        devices.append(
            {
                "index": _int_or_none(parts[0]) if _int_or_none(parts[0]) is not None else len(devices),
                "name": parts[1],
                "memory_total_mb": _int_or_none(parts[2]),
            }
        )
    return devices


def _resource_limits(config: dict[str, Any]) -> dict[str, Any]:
    execution = config.get("execution", {}) if isinstance(config, dict) else {}
    sandbox = execution.get("sandbox", {}) if isinstance(execution, dict) else {}
    limits = sandbox.get("resource_limits", {}) if isinstance(sandbox, dict) else {}
    return limits if isinstance(limits, dict) else {}


def _resource_optimization(config: dict[str, Any]) -> dict[str, Any]:
    execution = config.get("execution", {}) if isinstance(config, dict) else {}
    opt = execution.get("resource_optimization", {}) if isinstance(execution, dict) else {}
    return opt if isinstance(opt, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _gpu_ids_from_count(gpu_count: int, raw_ids: Any = None) -> list[str]:
    if raw_ids is None:
        return [str(index) for index in range(max(0, gpu_count))]
    raw_text = str(raw_ids).strip().lower() if not isinstance(raw_ids, list) else ""
    if not isinstance(raw_ids, list) and raw_text in {"", "auto", "all", "all_visible"}:
        return [str(index) for index in range(max(0, gpu_count))]
    return [str(item) for item in _as_list(raw_ids) if str(item).strip()]


def _resource_pool_config(config: dict[str, Any]) -> dict[str, Any]:
    opt = _resource_optimization(config)
    pool = opt.get("resource_pool", {}) if isinstance(opt.get("resource_pool"), dict) else {}
    return pool if isinstance(pool, dict) else {}


def _state_resource_pool(project: Path) -> list[dict[str, Any]]:
    path = project / "state" / "ssh_resource_pool.yaml"
    data = _read_yaml(path)
    resources = data.get("resources", [])
    return resources if isinstance(resources, list) else []


def _single_ssh_resource(project: Path, execution: dict[str, Any]) -> dict[str, Any] | None:
    ssh = execution.get("ssh", {}) if isinstance(execution.get("ssh"), dict) else {}
    allocation = _read_yaml(project / "state" / "ssh_allocation.yaml")
    server = allocation.get("server", {}) if isinstance(allocation.get("server"), dict) else {}
    lease = allocation.get("lease", {}) if isinstance(allocation.get("lease"), dict) else {}

    server_id = (
        ssh.get("server_id")
        or execution.get("server_id")
        or server.get("server_id")
        or lease.get("server_id")
    )
    lease_id = ssh.get("lease_id") or execution.get("lease_id") or lease.get("lease_id")
    host = ssh.get("host") or server.get("host")
    workspace_path = ssh.get("workspace_path") or lease.get("workspace_path")
    if not any(str(value or "").strip() for value in (server_id, lease_id, host, workspace_path)):
        return None

    capabilities = server.get("capabilities", {}) if isinstance(server.get("capabilities"), dict) else {}
    hardware = ssh.get("hardware", {}) if isinstance(ssh.get("hardware"), dict) else {}
    gpus = capabilities.get("gpus", [])
    gpu_count = _safe_positive_int(
        capabilities.get("gpu_count"),
        default=len(gpus) if isinstance(gpus, list) else _safe_positive_int(hardware.get("gpu_count"), default=0),
    )
    cpu_cores = _safe_positive_int(capabilities.get("cpu_cores"), default=_safe_positive_int(hardware.get("cpu_cores"), default=0))
    return {
        "resource_id": f"ssh:{server_id or host}",
        "kind": "ssh",
        "enabled": True,
        "server_id": server_id or "",
        "lease_id": lease_id or "",
        "host": host or "",
        "workspace_path": workspace_path or "",
        "dataset_path": ssh.get("dataset_path") or lease.get("dataset_path") or "",
        "cpu_cores": cpu_cores,
        "gpu_count": gpu_count,
        "gpu_ids": _gpu_ids_from_count(gpu_count, lease.get("gpu_ids")),
        "gpus": gpus if isinstance(gpus, list) else [],
        "tags": server.get("tags", []) if isinstance(server.get("tags"), list) else [],
        "sync_required": True,
        "launcher": "ssh",
    }


def _safe_positive_int(value: Any, *, default: int = 0) -> int:
    parsed = _int_or_none(value)
    if parsed is None:
        return default
    return max(0, parsed)


def _normalize_pool_resource(raw: dict[str, Any]) -> dict[str, Any]:
    resource_id = str(raw.get("resource_id") or raw.get("server_id") or raw.get("name") or raw.get("kind") or "resource")
    kind = str(raw.get("kind") or ("ssh" if raw.get("server_id") or raw.get("host") else "local")).lower()
    gpu_count = _safe_positive_int(raw.get("gpu_count"), default=len(raw.get("gpus", []) or []))
    cpu_cores = _safe_positive_int(raw.get("cpu_cores"), default=0)
    normalized = {
        "resource_id": resource_id,
        "kind": kind,
        "enabled": raw.get("enabled", True) is not False,
        "server_id": raw.get("server_id", ""),
        "lease_id": raw.get("lease_id", ""),
        "host": raw.get("host", ""),
        "ssh_alias": raw.get("ssh_alias", ""),
        "port": raw.get("port", 22),
        "workspace_path": raw.get("workspace_path", ""),
        "dataset_path": raw.get("dataset_path", ""),
        "cpu_cores": cpu_cores,
        "gpu_count": gpu_count,
        "gpu_ids": _gpu_ids_from_count(gpu_count, raw.get("gpu_ids")),
        "gpus": raw.get("gpus", []) if isinstance(raw.get("gpus"), list) else [],
        "tags": raw.get("tags", []) if isinstance(raw.get("tags"), list) else [],
        "sync_required": bool(raw.get("sync_required", kind == "ssh")),
        "launcher": raw.get("launcher") or ("ssh" if kind == "ssh" else "local"),
        "notes": raw.get("notes", ""),
    }
    return normalized


def _dedupe_resources(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in resources:
        resource = _normalize_pool_resource(raw)
        if not resource.get("enabled", True):
            continue
        key = str(resource.get("resource_id") or resource.get("server_id") or len(deduped))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(resource)
    return deduped


def build_resource_pool(
    project: Path,
    config: dict[str, Any],
    *,
    local_cpu: dict[str, Any],
    local_gpus: list[dict[str, Any]],
    allocated_cpu: int,
    allocated_gpu_ids: list[str],
) -> dict[str, Any]:
    execution = config.get("execution", {}) if isinstance(config, dict) else {}
    pool_cfg = _resource_pool_config(config)
    include_local = pool_cfg.get("include_local", True) is not False
    manual_resources = pool_cfg.get("resources") or pool_cfg.get("manual_resources") or []
    managed_leases = pool_cfg.get("managed_ssh_leases") or []

    resources: list[dict[str, Any]] = []
    if include_local:
        resources.append(
            {
                "resource_id": "local",
                "kind": "local",
                "enabled": True,
                "cpu_cores": allocated_cpu,
                "gpu_count": len(allocated_gpu_ids),
                "gpu_ids": allocated_gpu_ids,
                "gpus": [
                    device
                    for device in local_gpus
                    if str(device.get("index")) in {str(gpu_id) for gpu_id in allocated_gpu_ids}
                ],
                "memory_total_mb": local_cpu.get("memory_total_mb"),
                "workspace_path": str(project),
                "sync_required": False,
                "launcher": "local",
                "tags": ["local"] + (["gpu"] if allocated_gpu_ids else ["cpu"]),
            }
        )

    if isinstance(managed_leases, list):
        for lease in managed_leases:
            if not isinstance(lease, dict):
                continue
            resources.append(
                {
                    "resource_id": f"ssh:{lease.get('server_id') or lease.get('lease_id')}",
                    "kind": "ssh",
                    "enabled": lease.get("enabled", True) is not False,
                    "server_id": lease.get("server_id", ""),
                    "lease_id": lease.get("lease_id", ""),
                    "workspace_path": lease.get("workspace_path", ""),
                    "dataset_path": lease.get("dataset_path", ""),
                    "cpu_cores": lease.get("cpu_cores", 0),
                    "gpu_count": lease.get("gpu_count", len(lease.get("gpu_ids", []) or [])),
                    "gpu_ids": lease.get("gpu_ids", "all_visible"),
                    "tags": lease.get("tags", ["ssh", "gpu"]),
                    "sync_required": True,
                    "launcher": "ssh",
                }
            )

    single_ssh = _single_ssh_resource(project, execution)
    if single_ssh:
        resources.append(single_ssh)

    for raw in _as_list(manual_resources):
        if isinstance(raw, dict):
            resources.append(raw)

    resources.extend(_state_resource_pool(project))
    resources = _dedupe_resources(resources)
    explicit_enabled = pool_cfg.get("enabled") is True
    enabled = explicit_enabled or len(resources) > 1
    return {
        "enabled": enabled,
        "policy": str(pool_cfg.get("scheduling_policy") or "dependency_aware_pack_by_gpu_then_cpu"),
        "include_local": include_local,
        "allow_local_and_ssh": pool_cfg.get("allow_local_and_ssh", True) is not False,
        "resources": resources,
        "parallelism_contract": {
            "parallelize_only_independent_tasks": True,
            "do_not_parallelize_replicate_seeds_as_resource_filler": True,
            "prefer_ddp_within_single_multi_gpu_training_task": True,
            "prefer_task_parallel_for_independent_configs_baselines_or_analysis_slices": True,
            "fairness_policy": "baseline_and_ours_use_same_resource_class_or_record_resource_id",
            "result_sync_policy": "each_remote_assignment_must_pull_metrics_logs_monitors_and_artifacts",
        },
        "artifacts": {
            "m3_task_queue": "experiments/configs/m3_task_queue.yaml",
            "m3_task_allocation": "experiments/configs/m3_task_allocation.yaml",
            "m4_task_queue": "experiments/configs/m4_task_queue.yaml",
            "m4_task_allocation": "experiments/configs/m4_task_allocation.yaml",
        },
    }


def _resolve_gpu_count(total_gpus: int, limits: dict[str, Any], opt: dict[str, Any]) -> int:
    if total_gpus <= 0:
        return 0
    raw_limit = limits.get("max_gpu_count")
    limit_text = str(raw_limit).strip().lower() if raw_limit is not None else "all_visible"
    if limit_text in {"", "none", "null", "auto", "all", "all_visible", "-1"}:
        limit = total_gpus
    else:
        parsed = _int_or_none(raw_limit)
        limit = total_gpus if parsed is None else max(0, parsed)

    raw_target = opt.get("target_gpu_count", "auto")
    target_text = str(raw_target).strip().lower()
    if target_text in {"", "auto", "all", "all_visible"}:
        target = limit
    else:
        parsed_target = _int_or_none(raw_target)
        target = limit if parsed_target is None else max(0, parsed_target)
    return min(total_gpus, limit, target)


def _resolve_cpu_count(total_cpu: int, limits: dict[str, Any], opt: dict[str, Any]) -> int:
    raw_limit = limits.get("max_cpu_cores")
    parsed = _int_or_none(raw_limit)
    limit = total_cpu if parsed is None or parsed <= 0 else min(total_cpu, parsed)
    raw_target = opt.get("target_cpu_cores", "auto")
    parsed_target = _int_or_none(raw_target)
    target = limit if parsed_target is None or parsed_target <= 0 else min(limit, parsed_target)
    return max(1, target)


def _default_resource_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    allocation = plan.get("allocation", {}) if isinstance(plan.get("allocation"), dict) else {}
    available = plan.get("available", {}) if isinstance(plan.get("available"), dict) else {}
    cpu = available.get("cpu", {}) if isinstance(available.get("cpu"), dict) else {}
    gpus = available.get("gpus", []) if isinstance(available.get("gpus"), list) else []
    return {
        "resource_id": "local",
        "kind": "local",
        "enabled": True,
        "cpu_cores": _safe_positive_int(allocation.get("cpu_cores"), default=_safe_positive_int(cpu.get("cores"), default=1)),
        "gpu_count": _safe_positive_int(allocation.get("gpu_count"), default=0),
        "gpu_ids": _gpu_ids_from_count(_safe_positive_int(allocation.get("gpu_count"), default=0), allocation.get("gpu_ids")),
        "gpus": gpus,
        "workspace_path": plan.get("project_root", "."),
        "sync_required": False,
        "launcher": "local",
        "tags": ["local"],
    }


def _plan_resources(plan: dict[str, Any]) -> list[dict[str, Any]]:
    pool = plan.get("resource_pool", {}) if isinstance(plan.get("resource_pool"), dict) else {}
    resources = pool.get("resources", []) if isinstance(pool.get("resources"), list) else []
    if resources:
        return _dedupe_resources([item for item in resources if isinstance(item, dict)])
    return [_normalize_pool_resource(_default_resource_from_plan(plan))]


def _load_task_queue(path: Path) -> list[dict[str, Any]]:
    data = _read_yaml(path)
    tasks = data.get("tasks") or data.get("runs") or data.get("slices") or []
    if not isinstance(tasks, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(tasks, start=1):
        if not isinstance(raw, dict):
            continue
        task_id = str(raw.get("task_id") or raw.get("run_id") or raw.get("slice") or raw.get("id") or f"task_{index:03d}")
        requirements = raw.get("resource_requirements", {}) if isinstance(raw.get("resource_requirements"), dict) else {}
        normalized.append(
            {
                **raw,
                "task_id": task_id,
                "stage": raw.get("stage", ""),
                "command": raw.get("command") or raw.get("resolved_command") or raw.get("launch_command") or "",
                "estimated_minutes": _safe_positive_int(raw.get("estimated_minutes") or raw.get("duration_minutes"), default=60),
                "dependencies": [str(item) for item in _as_list(raw.get("dependencies") or raw.get("depends_on")) if str(item).strip()],
                "parallelizable": raw.get("parallelizable", True) is not False,
                "resource_requirements": requirements,
            }
        )
    return normalized


def _task_min_gpu(task: dict[str, Any]) -> int:
    req = task.get("resource_requirements", {}) if isinstance(task.get("resource_requirements"), dict) else {}
    return _safe_positive_int(
        req.get("min_gpu_count") or req.get("gpu_count") or task.get("min_gpu_count") or task.get("gpu_count"),
        default=0,
    )


def _task_min_cpu(task: dict[str, Any]) -> int:
    req = task.get("resource_requirements", {}) if isinstance(task.get("resource_requirements"), dict) else {}
    return _safe_positive_int(
        req.get("min_cpu_cores") or req.get("cpu_cores") or task.get("min_cpu_cores") or task.get("cpu_cores"),
        default=1,
    )


def _task_tags(task: dict[str, Any]) -> set[str]:
    req = task.get("resource_requirements", {}) if isinstance(task.get("resource_requirements"), dict) else {}
    return {str(tag).strip() for tag in _as_list(req.get("tags") or task.get("tags")) if str(tag).strip()}


def _task_allows_resource(task: dict[str, Any], resource: dict[str, Any]) -> bool:
    req = task.get("resource_requirements", {}) if isinstance(task.get("resource_requirements"), dict) else {}
    kind = str(resource.get("kind", "")).lower()
    if req.get("local_only") is True and kind != "local":
        return False
    if req.get("remote_ok") is False and kind == "ssh":
        return False
    preferred_kind = str(req.get("kind") or req.get("resource_kind") or "").strip().lower()
    if preferred_kind and preferred_kind != kind:
        return False
    min_gpu = _task_min_gpu(task)
    min_cpu = _task_min_cpu(task)
    if _safe_positive_int(resource.get("gpu_count"), default=0) < min_gpu:
        return False
    if _safe_positive_int(resource.get("cpu_cores"), default=0) < min_cpu:
        return False
    required_tags = _task_tags(task)
    resource_tags = {str(tag).strip() for tag in _as_list(resource.get("tags")) if str(tag).strip()}
    return not required_tags or required_tags.issubset(resource_tags)


def _resource_slots(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for resource in resources:
        gpu_ids = [str(item) for item in _as_list(resource.get("gpu_ids")) if str(item).strip()]
        if gpu_ids:
            for gpu_id in gpu_ids:
                slots.append({**resource, "slot_id": f"{resource['resource_id']}:gpu:{gpu_id}", "slot_gpu_ids": [gpu_id]})
        else:
            slots.append({**resource, "slot_id": f"{resource['resource_id']}:cpu", "slot_gpu_ids": []})
    return slots


def _task_wave(task: dict[str, Any], task_to_wave: dict[str, int]) -> int:
    if task.get("parallelizable") is False:
        return max(task_to_wave.values(), default=-1) + 1
    deps = [dep for dep in task.get("dependencies", []) if dep in task_to_wave]
    return (max((task_to_wave[dep] for dep in deps), default=-1) + 1) if deps else 0


def _assignment_command(task: dict[str, Any], resource: dict[str, Any], gpu_ids: list[str]) -> str:
    command = str(task.get("command") or "").strip()
    if not command:
        command = "# command must be filled by Experiment Agent"
    env_parts: list[str] = []
    if gpu_ids:
        env_parts.append("CUDA_VISIBLE_DEVICES=" + ",".join(gpu_ids))
    cpu_cores = _task_min_cpu(task)
    if cpu_cores:
        env_parts.append(f"OMP_NUM_THREADS={cpu_cores}")
        env_parts.append(f"MKL_NUM_THREADS={cpu_cores}")
    local_command = " ".join([*env_parts, command]).strip()
    if str(resource.get("kind", "")).lower() != "ssh":
        return local_command
    workspace = str(resource.get("workspace_path") or ".")
    server = str(resource.get("ssh_alias") or resource.get("host") or resource.get("server_id") or resource.get("resource_id"))
    return f"ssh {shlex.quote(server)} {shlex.quote(f'cd {workspace} && {local_command}')}"


def allocate_tasks(project: Path, plan: dict[str, Any], task_queue: Path, *, stage: str = "") -> dict[str, Any]:
    tasks = _load_task_queue(task_queue)
    if stage:
        tasks = [task for task in tasks if not task.get("stage") or str(task.get("stage")) == stage]
    resources = _plan_resources(plan)
    slots = _resource_slots(resources)
    if not slots:
        slots = [_normalize_pool_resource(_default_resource_from_plan(plan))]

    slot_load: dict[str, int] = {str(slot["slot_id"]): 0 for slot in slots}
    slot_next_wave: dict[str, int] = {str(slot["slot_id"]): 0 for slot in slots}
    task_to_wave: dict[str, int] = {}
    assignments: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for task in tasks:
        candidates = [slot for slot in slots if _task_allows_resource(task, slot)]
        min_gpu = _task_min_gpu(task)
        if min_gpu >= 2:
            candidates = [
                resource
                for resource in resources
                if _task_allows_resource(task, resource)
                and _safe_positive_int(resource.get("gpu_count"), default=0) >= min_gpu
            ]
        if not candidates:
            blocked.append(
                {
                    "task_id": task["task_id"],
                    "reason": "no resource satisfies task resource_requirements",
                    "resource_requirements": task.get("resource_requirements", {}),
                }
            )
            continue

        def score(resource: dict[str, Any]) -> tuple[int, int, int]:
            resource_id = str(resource.get("slot_id") or resource.get("resource_id"))
            return (
                -slot_load.get(resource_id, 0),
                _safe_positive_int(resource.get("gpu_count"), default=0),
                _safe_positive_int(resource.get("cpu_cores"), default=0),
            )

        chosen = sorted(candidates, key=score, reverse=True)[0]
        chosen_id = str(chosen.get("slot_id") or chosen.get("resource_id"))
        duration = _safe_positive_int(task.get("estimated_minutes"), default=60)
        slot_load[chosen_id] = slot_load.get(chosen_id, 0) + duration
        if min_gpu >= 2:
            gpu_ids = _gpu_ids_from_count(min_gpu, chosen.get("gpu_ids"))[:min_gpu]
        else:
            gpu_ids = [str(item) for item in _as_list(chosen.get("slot_gpu_ids")) if str(item).strip()]
        dependency_wave = _task_wave(task, task_to_wave)
        wave = max(dependency_wave, slot_next_wave.get(chosen_id, 0))
        slot_next_wave[chosen_id] = wave + 1
        task_to_wave[str(task["task_id"])] = wave
        run_id = str(task.get("run_id") or task.get("task_id"))
        monitor_path = f"experiments/runs/{run_id}/resource_monitor.csv"
        assignments.append(
            {
                "task_id": task["task_id"],
                "stage": task.get("stage") or stage,
                "wave": wave,
                "parallelizable": bool(task.get("parallelizable", True)) and not task.get("dependencies"),
                "dependencies": task.get("dependencies", []),
                "resource_id": chosen.get("resource_id"),
                "resource_kind": chosen.get("kind"),
                "server_id": chosen.get("server_id", ""),
                "lease_id": chosen.get("lease_id", ""),
                "slot_id": chosen.get("slot_id", chosen.get("resource_id")),
                "gpu_ids": gpu_ids,
                "cpu_cores": min(_task_min_cpu(task), _safe_positive_int(chosen.get("cpu_cores"), default=_task_min_cpu(task))),
                "estimated_minutes": duration,
                "command": task.get("command", ""),
                "launch_command": _assignment_command(task, chosen, gpu_ids),
                "resource_monitor": monitor_path,
                "sync": {
                    "push_before": bool(chosen.get("sync_required", False)),
                    "pull_after": bool(chosen.get("sync_required", False)),
                    "required_artifacts": [
                        monitor_path,
                        "metrics/results rows",
                        "logs",
                        "artifacts referenced by task output",
                    ],
                },
                "fairness_key": task.get("fairness_key") or task.get("comparison_group") or "",
            }
        )

    waves: list[dict[str, Any]] = []
    for wave in sorted({int(item["wave"]) for item in assignments}):
        wave_items = [item for item in assignments if int(item["wave"]) == wave]
        waves.append(
            {
                "wave": wave,
                "parallel_assignments": [item["task_id"] for item in wave_items],
                "resource_ids": sorted({str(item["resource_id"]) for item in wave_items}),
            }
        )

    return {
        "schema_version": 1,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "project_root": str(project),
        "stage": stage or "mixed",
        "source_resource_plan": "experiments/configs/resource_plan.yaml",
        "source_task_queue": str(task_queue.relative_to(project) if task_queue.is_relative_to(project) else task_queue),
        "scheduling_policy": "dependency_aware_least_loaded_resource_slot",
        "resources_considered": resources,
        "assignments": assignments,
        "blocked_tasks": blocked,
        "waves": waves,
        "execution_contract": {
            "parallelize_assignments_in_same_wave": True,
            "respect_dependencies_between_waves": True,
            "each_assignment_requires_resource_monitor": True,
            "remote_assignments_require_push_before_and_pull_after": True,
            "results_tables_must_record_resource_id_and_monitor_path": True,
            "baseline_and_ours_fairness": "same fairness_key should use the same resource class or document the override",
        },
    }


def build_plan(project: Path) -> dict[str, Any]:
    config_path = project / "config" / "execution_env.yaml"
    config = _read_yaml(config_path)
    execution = config.get("execution", {}) if isinstance(config, dict) else {}
    limits = _resource_limits(config)
    opt = _resource_optimization(config)

    cpu = detect_cpu()
    gpus = detect_gpus()
    allocated_cpu = _resolve_cpu_count(int(cpu["cores"]), limits, opt)
    allocated_gpu_count = _resolve_gpu_count(len(gpus), limits, opt)
    allocated_gpu_ids = [str(device["index"]) for device in gpus[:allocated_gpu_count]]

    max_loader_workers = _int_or_none(opt.get("max_dataloader_workers")) or 16
    if allocated_cpu <= 2:
        loader_workers = max(0, allocated_cpu - 1)
    else:
        loader_workers = min(max_loader_workers, max(2, allocated_cpu // 2))
    per_process_threads = max(1, allocated_cpu // max(allocated_gpu_count, 1))

    if allocated_gpu_count >= 2:
        device_mode = "distributed_data_parallel"
        command_template = (
            "torchrun --standalone --nproc_per_node={gpu_count} "
            "experiments/src/train.py --config experiments/configs/main_exp.yaml"
        )
    elif allocated_gpu_count == 1:
        device_mode = "single_gpu"
        command_template = "python experiments/src/train.py --config experiments/configs/main_exp.yaml"
    else:
        device_mode = "cpu_parallel"
        command_template = "python experiments/src/train.py --config experiments/configs/main_exp.yaml --device cpu"

    monitoring = opt.get("monitoring", {}) if isinstance(opt.get("monitoring"), dict) else {}
    interval = _int_or_none(monitoring.get("interval_seconds")) or 10
    min_gpu = _int_or_none(monitoring.get("min_gpu_utilization_pct")) or 70
    min_cpu = _int_or_none(monitoring.get("min_cpu_utilization_pct")) or 60
    plan = {
        "schema_version": 1,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "project_root": str(project),
        "execution_mode": str(execution.get("mode", "local")),
        "available": {
            "cpu": cpu,
            "gpus": gpus,
        },
        "limits": {
            "max_cpu_cores": limits.get("max_cpu_cores", "auto"),
            "max_memory_gb": limits.get("max_memory_gb", "auto"),
            "max_gpu_count": limits.get("max_gpu_count", "all_visible"),
        },
        "allocation": {
            "cpu_cores": allocated_cpu,
            "gpu_count": allocated_gpu_count,
            "gpu_ids": allocated_gpu_ids,
        },
        "strategy": {
            "device_mode": device_mode,
            "gpu_parallelism": "ddp" if allocated_gpu_count >= 2 else ("single_process" if allocated_gpu_count == 1 else "none"),
            "config_or_task_parallelism": allocated_gpu_count <= 1 and allocated_cpu >= 4,
            "dataloader": {
                "num_workers": loader_workers,
                "pin_memory": allocated_gpu_count > 0,
                "persistent_workers": loader_workers > 0,
                "prefetch_factor": 2 if loader_workers > 0 else None,
            },
            "mixed_precision": "prefer_amp_when_supported" if allocated_gpu_count > 0 else "not_applicable",
        },
        "launch": {
            "env": {
                "CUDA_VISIBLE_DEVICES": ",".join(allocated_gpu_ids),
                "OMP_NUM_THREADS": str(per_process_threads),
                "MKL_NUM_THREADS": str(per_process_threads),
                "TOKENIZERS_PARALLELISM": "false",
            },
            "command_template": command_template,
            "resolved_command_hint": command_template.format(gpu_count=allocated_gpu_count),
        },
        "monitoring": {
            "enabled": True,
            "interval_seconds": interval,
            "output_path_template": "experiments/runs/{run_id}/resource_monitor.csv",
            "min_gpu_utilization_pct": min_gpu,
            "min_cpu_utilization_pct": min_cpu,
            "low_utilization_policy": "optimize_or_document_blocker",
            "runtime_watchdog": {
                "enabled": True,
                "default_interval_seconds": 4 * 60 * 60,
                "events_path": "experiments/logs/runtime_events.jsonl",
                "checks_path_template": "experiments/runs/{run_id}/watchdog_checks.jsonl",
                "alerts_path_template": "experiments/runs/{run_id}/watchdog_alerts.jsonl",
                "alert_policy": "record_alert_only_agent_decides_continue_fix_or_stop",
                "default_command": (
                    "python scripts/experiment_watchdog.py watch "
                    "--run-id {run_id} --interval-seconds 14400"
                ),
            },
        },
    }
    plan["resource_pool"] = build_resource_pool(
        project,
        config,
        local_cpu=cpu,
        local_gpus=gpus,
        allocated_cpu=allocated_cpu,
        allocated_gpu_ids=allocated_gpu_ids,
    )
    return plan


def _gpu_samples() -> list[dict[str, Any]]:
    query = "index,utilization.gpu,memory.used,memory.total"
    rc, out, _ = _run(
        ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
        timeout=10,
    )
    if rc != 0 or not out:
        return []
    samples: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 4:
            continue
        samples.append(
            {
                "gpu_index": parts[0],
                "gpu_util_pct": parts[1],
                "gpu_mem_used_mb": parts[2],
                "gpu_mem_total_mb": parts[3],
            }
        )
    return samples


def _cpu_load_pct() -> float | None:
    try:
        load_1m = os.getloadavg()[0]
    except (AttributeError, OSError):
        return None
    cores = os.cpu_count() or 1
    return round(min(100.0, (load_1m / cores) * 100.0), 2)


def _write_monitor_sample(writer: csv.DictWriter[str], command_pid: int | None = None) -> None:
    timestamp = dt.datetime.now().isoformat(timespec="seconds")
    base = {
        "timestamp": timestamp,
        "command_pid": command_pid or "",
        "cpu_load_pct": _cpu_load_pct(),
        "mem_available_mb": _memory_available_mb(),
    }
    gpus = _gpu_samples()
    if not gpus:
        writer.writerow({**base, "gpu_index": "", "gpu_util_pct": "", "gpu_mem_used_mb": "", "gpu_mem_total_mb": ""})
        return
    for gpu in gpus:
        writer.writerow({**base, **gpu})


def monitor(output: Path, interval: int, duration: int | None = None, pid: int | None = None) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp",
        "command_pid",
        "cpu_load_pct",
        "mem_available_mb",
        "gpu_index",
        "gpu_util_pct",
        "gpu_mem_used_mb",
        "gpu_mem_total_mb",
    ]
    started = time.time()
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer: csv.DictWriter[str] = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        while True:
            _write_monitor_sample(writer, command_pid=pid)
            handle.flush()
            if duration is not None and time.time() - started >= duration:
                break
            if pid is not None:
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
            time.sleep(max(1, interval))
    return 0


def run_with_monitor(output: Path, interval: int, command: list[str]) -> int:
    if not command:
        print("[ERROR] run requires a command after --", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(command)
    fieldnames = [
        "timestamp",
        "command_pid",
        "cpu_load_pct",
        "mem_available_mb",
        "gpu_index",
        "gpu_util_pct",
        "gpu_mem_used_mb",
        "gpu_mem_total_mb",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer: csv.DictWriter[str] = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        while proc.poll() is None:
            _write_monitor_sample(writer, command_pid=proc.pid)
            handle.flush()
            time.sleep(max(1, interval))
        _write_monitor_sample(writer, command_pid=proc.pid)
    return proc.returncode or 0


def summarize(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    cpu_values: list[float] = []
    gpu_values: dict[str, list[float]] = {}
    for row in rows:
        try:
            if row.get("cpu_load_pct") not in {"", None}:
                cpu_values.append(float(row["cpu_load_pct"]))
            if row.get("gpu_index") not in {"", None} and row.get("gpu_util_pct") not in {"", None}:
                gpu_values.setdefault(str(row["gpu_index"]), []).append(float(row["gpu_util_pct"]))
        except ValueError:
            continue
    return {
        "samples": len(rows),
        "avg_cpu_load_pct": round(sum(cpu_values) / len(cpu_values), 2) if cpu_values else None,
        "avg_gpu_util_pct": {
            gpu: round(sum(values) / len(values), 2) for gpu, values in sorted(gpu_values.items())
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan and monitor AutoPaper2 experiment resources")
    sub = parser.add_subparsers(dest="cmd", required=True)

    plan_p = sub.add_parser("plan", help="Generate experiments/configs/resource_plan.yaml")
    plan_p.add_argument("--project", default=".", help="Project root")
    plan_p.add_argument("--output", default="experiments/configs/resource_plan.yaml", help="Output YAML path")

    alloc_p = sub.add_parser("allocate", help="Allocate an experiment task queue across resource_pool resources")
    alloc_p.add_argument("--project", default=".", help="Project root")
    alloc_p.add_argument("--plan", default="experiments/configs/resource_plan.yaml", help="Input resource plan YAML")
    alloc_p.add_argument("--tasks", required=True, help="Task queue YAML with tasks/runs/slices")
    alloc_p.add_argument("--stage", default="", help="Optional stage filter, e.g. M3S03 or M4S03")
    alloc_p.add_argument("--output", default="", help="Output allocation YAML path")

    mon_p = sub.add_parser("monitor", help="Record CPU/GPU utilization samples")
    mon_p.add_argument("--output", required=True, help="CSV output path")
    mon_p.add_argument("--interval", type=int, default=10, help="Sampling interval in seconds")
    mon_p.add_argument("--duration", type=int, default=None, help="Optional duration in seconds")
    mon_p.add_argument("--pid", type=int, default=None, help="Optional process id to follow")

    run_p = sub.add_parser("run", help="Run a command while recording resource samples")
    run_p.add_argument("--output", required=True, help="CSV output path")
    run_p.add_argument("--interval", type=int, default=10, help="Sampling interval in seconds")
    run_p.add_argument("command", nargs=argparse.REMAINDER, help="Command after --")

    sum_p = sub.add_parser("summarize", help="Summarize a resource_monitor.csv")
    sum_p.add_argument("--input", required=True, help="CSV input path")

    args = parser.parse_args(argv)
    if args.cmd == "plan":
        project = Path(args.project).resolve()
        output = Path(args.output)
        if not output.is_absolute():
            output = project / output
        data = build_plan(project)
        _write_yaml(output, data)
        print(f"[RESOURCE_PLAN] Wrote {output}")
        return 0
    if args.cmd == "allocate":
        project = Path(args.project).resolve()
        plan_path = Path(args.plan)
        task_path = Path(args.tasks)
        if not plan_path.is_absolute():
            plan_path = project / plan_path
        if not task_path.is_absolute():
            task_path = project / task_path
        plan = _read_yaml(plan_path)
        output = Path(args.output) if args.output else Path(
            "experiments/configs/m4_task_allocation.yaml"
            if args.stage == "M4S03"
            else "experiments/configs/m3_task_allocation.yaml"
        )
        if not output.is_absolute():
            output = project / output
        data = allocate_tasks(project, plan, task_path, stage=args.stage)
        _write_yaml(output, data)
        print(f"[RESOURCE_ALLOC] Wrote {output}")
        if data.get("blocked_tasks"):
            print(f"[RESOURCE_ALLOC][WARN] blocked tasks: {len(data['blocked_tasks'])}", file=sys.stderr)
            return 1
        return 0
    if args.cmd == "monitor":
        return monitor(Path(args.output), args.interval, duration=args.duration, pid=args.pid)
    if args.cmd == "run":
        command = args.command[1:] if args.command and args.command[0] == "--" else args.command
        return run_with_monitor(Path(args.output), args.interval, command)
    if args.cmd == "summarize":
        print(yaml.safe_dump(summarize(Path(args.input)), sort_keys=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
