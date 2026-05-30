#!/usr/bin/env python3
"""Environment Probe — Auto-detect local execution environment for AutoPaper2.

Usage:
    python scripts/env_probe.py                          # detect current environment
    python scripts/env_probe.py --project /path/to/proj  # detect + write to project config
    python scripts/env_probe.py --output env_report.yaml # detect + write to file
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import yaml


def _run(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run a command, return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"


def detect_python() -> dict[str, Any]:
    return {
        "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "executable": sys.executable,
        "implementation": platform.python_implementation(),
    }


def detect_os() -> dict[str, Any]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
    }


def detect_env_managers() -> dict[str, Any]:
    managers: dict[str, Any] = {}
    for name, cmd in [
        ("conda", ["conda", "--version"]),
        ("uv", ["uv", "--version"]),
        ("docker", ["docker", "--version"]),
    ]:
        rc, out, _ = _run(cmd)
        managers[name] = {
            "available": rc == 0,
            "version": out.strip() if rc == 0 else None,
        }
    # venv is always available (stdlib), but check if we're in one
    managers["venv"] = {
        "available": True,
        "active": sys.prefix != sys.base_prefix,
        "prefix": sys.prefix,
    }
    return managers


def detect_gpu() -> dict[str, Any]:
    gpu_info: dict[str, Any] = {"available": False, "cuda_version": None, "devices": []}

    # Try nvidia-smi
    rc, out, _ = _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    if rc == 0:
        gpu_info["available"] = True
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                gpu_info["devices"].append({
                    "name": parts[0],
                    "memory": parts[1],
                    "driver": parts[2],
                })

    # Try nvcc for CUDA version
    rc, out, _ = _run(["nvcc", "--version"])
    if rc == 0:
        m = re.search(r"release (\d+\.\d+)", out)
        if m:
            gpu_info["cuda_version"] = m.group(1)
    else:
        # Fallback: parse nvidia-smi header for CUDA version
        rc2, out2, _ = _run(["nvidia-smi"])
        if rc2 == 0:
            m = re.search(r"CUDA Version:\s*(\d+\.\d+)", out2)
            if m:
                gpu_info["cuda_version"] = m.group(1)

    return gpu_info


def detect_ml_frameworks() -> dict[str, Any]:
    frameworks: dict[str, Any] = {}

    # PyTorch
    try:
        import torch
        frameworks["torch"] = {
            "available": True,
            "version": str(torch.__version__),
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_version": str(torch.version.cuda) if (hasattr(torch.version, "cuda") and torch.version.cuda) else None,
        }
    except Exception as e:
        frameworks["torch"] = {"available": False, "error": str(e)}

    # TensorFlow
    try:
        import tensorflow as tf
        frameworks["tensorflow"] = {
            "available": True,
            "version": str(tf.__version__),
        }
    except Exception:
        frameworks["tensorflow"] = {"available": False}

    # JAX
    try:
        import jax
        frameworks["jax"] = {
            "available": True,
            "version": str(jax.__version__),
        }
    except Exception:
        frameworks["jax"] = {"available": False}

    return frameworks


def detect_ssh() -> dict[str, Any]:
    rc, _, _ = _run(["ssh", "-V"])
    ssh_available = rc == 0 or rc == 255  # ssh -V exits 255 but prints version
    return {
        "available": ssh_available,
        "key_files": [
            str(p) for p in [Path.home() / ".ssh" / "id_rsa", Path.home() / ".ssh" / "id_ed25519"]
            if p.exists()
        ],
    }


def detect_git() -> dict[str, Any]:
    rc, out, _ = _run(["git", "--version"])
    return {
        "available": rc == 0,
        "version": out.strip() if rc == 0 else None,
    }


def detect_cpu() -> dict[str, Any]:
    cpu_count = os.cpu_count() or 0
    # Try to get more detailed info on Linux
    cpu_info = {"cores": cpu_count}
    if platform.system() == "Linux":
        rc, out, _ = _run(["lscpu"])
        if rc == 0:
            for line in out.splitlines():
                if line.startswith("Model name:"):
                    cpu_info["model"] = line.split(":", 1)[1].strip()
                elif line.startswith("CPU(s):"):
                    cpu_info["cores"] = line.split(":", 1)[1].strip()
    elif platform.system() == "Darwin":
        rc, out, _ = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        if rc == 0:
            cpu_info["model"] = out.strip()
    return cpu_info


def probe() -> dict[str, Any]:
    """Run full environment probe and return structured report."""
    import datetime as _dt
    return {
        "probe_time": _dt.datetime.now().isoformat(),
        "python": detect_python(),
        "os": detect_os(),
        "cpu": detect_cpu(),
        "gpu": detect_gpu(),
        "env_managers": detect_env_managers(),
        "ml_frameworks": detect_ml_frameworks(),
        "ssh": detect_ssh(),
        "git": detect_git(),
    }


def generate_execution_env_yaml(report: dict[str, Any], project_name: str = "project") -> str:
    """Generate an execution_env.yaml snippet from probe report."""
    python_ver = report["python"]["version"]
    python_short = ".".join(python_ver.split(".")[:2])

    gpu = report["gpu"]
    has_gpu = gpu["available"]
    cuda_ver = gpu.get("cuda_version") or "12.1"
    cuda_short = cuda_ver.split(".")[0] + "." + cuda_ver.split(".")[1] if "." in cuda_ver else cuda_ver

    env_mgr = report["env_managers"]
    preferred_mgr = "conda"
    if env_mgr.get("conda", {}).get("available"):
        preferred_mgr = "conda"
    elif env_mgr.get("uv", {}).get("available"):
        preferred_mgr = "uv"
    elif env_mgr.get("venv", {}).get("available"):
        preferred_mgr = "venv"

    gpu_names = [d["name"] for d in gpu.get("devices", [])]
    gpu_mems = [d["memory"] for d in gpu.get("devices", [])]
    gpu_count = len(gpu_names)

    hw_gpu = gpu_names[0] if gpu_names else "N/A"
    hw_mem = gpu_mems[0] if gpu_mems else "N/A"

    lines = [
        "# AutoPaper2 — 实验执行环境配置（由 env_probe.py 自动生成）",
        "# 默认使用 local；只有显式选择服务器或填写 SSH 配置后才切换到 ssh。",
        "",
        "execution:",
        "  mode: local",
        "",
        "  sandbox:",
        "    enabled: true",
        f"    mode: {'docker' if env_mgr.get('docker', {}).get('available') else preferred_mgr}",
        "    network_policy: restricted",
        "    filesystem_policy:",
        "      project_root_read_only: false",
        "      allowed_write_paths:",
        "        - experiments/runs/",
        "        - experiments/logs/",
        "        - experiments/artifacts/",
        "        - artifacts/",
        "      denied_paths:",
        "        - ~/.ssh/",
        "        - /etc/",
        "        - /var/",
        "    secrets_policy:",
        "      allow_env_secrets: false",
        "      allow_ssh_key_read: false",
        "      redact_logs: true",
        "    resource_limits:",
        "      timeout_hours: 24",
        f"      max_cpu_cores: {report['cpu'].get('cores', 0)}",
        "      max_memory_gb: 64",
        f"      max_gpu_count: {gpu_count}",
        "    reproducibility:",
        "      requirements_lock: experiments/requirements.lock",
        '      image: ""',
        '      image_digest: ""',
        "      seed_policy: fixed_seed_42",
        "",
        "  resource_optimization:",
        "    enabled: true",
        "    target_gpu_count: all_visible",
        "    target_cpu_cores: auto",
        "    gpu_strategy: auto",
        "    cpu_strategy: dataloader_and_task_parallel",
        "    dataloader:",
        "      auto_num_workers: true",
        "      max_workers: 16",
        "      pin_memory: auto",
        "      persistent_workers: auto",
        "      prefetch_factor: 2",
        "    autotune:",
        "      enabled: true",
        "      warmup_steps: 50",
        "      batch_size_search: true",
        "      mixed_precision: auto",
        "      compile_or_jit: auto",
        "    monitoring:",
        "      enabled: true",
        "      interval_seconds: 10",
        "      min_gpu_utilization_pct: 70",
        "      min_cpu_utilization_pct: 60",
        "      low_utilization_window_minutes: 10",
        "      low_utilization_policy: optimize_or_document_blocker",
        "      plan_path: experiments/configs/resource_plan.yaml",
        "      monitor_path_template: experiments/runs/{run_id}/resource_monitor.csv",
        "      runtime_watchdog:",
        "        enabled: true",
        "        default_interval_seconds: 14400",
        "        events_path: experiments/logs/runtime_events.jsonl",
        "        checks_path_template: experiments/runs/{run_id}/watchdog_checks.jsonl",
        "        alerts_path_template: experiments/runs/{run_id}/watchdog_alerts.jsonl",
        "        alert_policy: record_alert_only_agent_decides_continue_fix_or_stop",
        "",
        "  local:",
        f"    env_manager: {preferred_mgr}",
        f"    env_name: autopaper2-{project_name}",
        f"    python_version: \"{python_short}\"",
        f"    cuda_version: \"{cuda_short}\"",
        "    hardware:",
        f"      gpu: \"{hw_gpu}\"",
        f"      gpu_count: {gpu_count}",
        f"      memory: \"{hw_mem}\"",
        f"      cpu_cores: {report['cpu'].get('cores', 0)}",
        "",
        "  ssh:",
        '    server_id: ""',
        '    lease_id: ""',
        '    host: ""',
        '    user: ""',
        '    port: 22',
        '    auth_method: "key"',
        '    identity_file: ""',
        '    password: ""',
        f'    framework_root: "~/AutoPaper2"',
        f'    workspace_path: "~/AutoPaper2/projects/{project_name}"',
        f'    dataset_path: "~/AutoPaper2/data/datasets"',
        '    python_path: ""',
        '    conda_env_name: ""',
        f'    env_manager: {preferred_mgr}',
        f'    python_version: "{python_short}"',
        f'    cuda_version: "{cuda_short}"',
        "    hardware:",
        f"      gpu: \"{hw_gpu}\"",
        f"      gpu_count: {gpu_count}",
        f"      memory: \"{hw_mem}\"",
        f"      cpu_cores: {report['cpu'].get('cores', 0)}",
        "    sync:",
        '      method: rsync',
        "      excludes:",
        '        - "__pycache__"',
        '        - "*.pyc"',
        '        - ".git"',
        '        - "*.log"',
        '        - "runs/*/logs/*.txt"',
        '        - "*.pt"',
        '        - "*.pth"',
        '        - "*.ckpt"',
        "      auto_sync: true",
        '      result_sync_strategy: "metrics_only"',
        "      selective_patterns:",
        '        - "results.tsv"',
        '        - "results.yaml"',
        '        - "results.json"',
        '        - "*.csv"',
        '        - "configs/*.yaml"',
        '        - "curves/*.png"',
        '        - "logs/*.log"',
        "",
        "# =============================================================================",
        "# 环境探测摘要（只读参考）",
        "# =============================================================================",
        f"# Python: {python_ver} ({report['python']['executable']})",
        f"# OS: {report['os']['system']} {report['os']['release']} ({report['os']['machine']})",
        f"# CPU: {report['cpu'].get('model', 'unknown')} / {report['cpu'].get('cores', '?')} cores",
        f"# GPU: {hw_gpu} x{gpu_count} ({hw_mem})",
        f"# CUDA: {cuda_ver or 'N/A'}",
        f"# PyTorch: {report['ml_frameworks'].get('torch', {}).get('version', 'not installed')}",
        f"# TensorFlow: {report['ml_frameworks'].get('tensorflow', {}).get('version', 'not installed')}",
        f"# Conda: {env_mgr.get('conda', {}).get('version', 'not available')}",
        f"# UV: {env_mgr.get('uv', {}).get('version', 'not available')}",
        f"# Docker: {env_mgr.get('docker', {}).get('version', 'not available')}",
        f"# SSH keys: {', '.join(report['ssh']['key_files']) or 'none found'}",
    ]
    return "\n".join(lines)


def _has_configured_ssh(data: dict[str, Any]) -> bool:
    execution = data.get("execution", {}) if isinstance(data.get("execution"), dict) else {}
    ssh = execution.get("ssh", {}) if isinstance(execution.get("ssh"), dict) else {}
    return bool(
        execution.get("mode") == "ssh"
        and (
            execution.get("server_id")
            or execution.get("lease_id")
            or ssh.get("server_id")
            or ssh.get("lease_id")
            or (ssh.get("host") and ssh.get("user"))
        )
    )


def _merge_non_empty(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    for key, value in overrides.items():
        if isinstance(value, dict):
            target = base.setdefault(key, {})
            if isinstance(target, dict):
                _merge_non_empty(target, value)
            continue
        if value not in ("", None, [], {}):
            base[key] = value
    return base


def _merge_existing_manual_config(generated: str, existing: dict[str, Any]) -> str:
    """Preserve explicit user SSH/project fields across local environment probe.

    The probe should refresh local machine facts, not erase a server selected by
    onboarding or ``state_manager.py create --server-id``.
    """
    if not existing:
        return generated
    try:
        generated_data = yaml.safe_load(generated) or {}
    except Exception:
        return generated
    if not isinstance(generated_data, dict):
        return generated

    existing_execution = existing.get("execution", {}) if isinstance(existing.get("execution"), dict) else {}
    generated_execution = generated_data.setdefault("execution", {})
    if not isinstance(generated_execution, dict):
        return generated

    # Preserve stable project/allocation identifiers even for local mode.
    for key in ("server_id", "lease_id"):
        if existing_execution.get(key):
            generated_execution[key] = existing_execution[key]

    if _has_configured_ssh(existing):
        generated_execution["mode"] = "ssh"
        sandbox = generated_execution.setdefault("sandbox", {})
        if isinstance(sandbox, dict):
            sandbox["mode"] = "ssh_remote"
        existing_ssh = existing_execution.get("ssh", {}) if isinstance(existing_execution.get("ssh"), dict) else {}
        generated_ssh = generated_execution.setdefault("ssh", {})
        if isinstance(generated_ssh, dict):
            _merge_non_empty(generated_ssh, existing_ssh)

    return yaml.safe_dump(generated_data, allow_unicode=True, sort_keys=False)


def apply_to_project(project_dir: str | Path, dry_run: bool = False) -> Path:
    """Detect environment and overwrite project's execution_env.yaml."""
    project_dir = Path(project_dir).resolve()
    config_path = project_dir / "config" / "execution_env.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Project config not found: {config_path}")

    try:
        existing = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        existing = {}
    report = probe()
    project_name = project_dir.name.split("-")[0] if "-" in project_dir.name else project_dir.name
    generated = _merge_existing_manual_config(generate_execution_env_yaml(report, project_name), existing)

    if not dry_run:
        config_path.write_text(generated, encoding="utf-8")
        print(f"[ENV_PROBE] Updated {config_path}")
    else:
        print("[ENV_PROBE] Dry-run. Would write:")
        print(generated)

    return config_path


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="AutoPaper2 Environment Probe")
    parser.add_argument("--project", help="Project directory to update config/execution_env.yaml")
    parser.add_argument("--output", help="Output file for raw probe report (YAML)")
    parser.add_argument("--dry-run", action="store_true", help="Print without writing")
    args = parser.parse_args()

    report = probe()

    if args.output:
        Path(args.output).write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"[ENV_PROBE] Raw report saved to {args.output}")

    if args.project:
        apply_to_project(args.project, dry_run=args.dry_run)
    elif not args.output:
        # Just print JSON to stdout
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
