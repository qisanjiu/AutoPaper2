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

    return {
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
