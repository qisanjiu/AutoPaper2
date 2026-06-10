#!/usr/bin/env python3
# ruff: noqa: E402
"""Run commands or record code changes with AutoPaper2 task-level ledgers.

This is an audit helper, not a permission system. Subagents remain responsible
for choosing commands and edits, but experiment/code tasks should leave durable
evidence that reviewers can inspect.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

_framework_root = Path(__file__).parent.parent.resolve()
if str(_framework_root) not in sys.path:
    sys.path.insert(0, str(_framework_root))

from spiral.agent_runtime import append_run_event, task_runtime_paths


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_ledger(path: Path, key: str, record: dict[str, Any]) -> None:
    data = _read_yaml(path)
    entries = data.get(key, [])
    if not isinstance(entries, list):
        entries = []
    entries.append(record)
    data.update({"version": 1, "updated_at": _now(), key: entries})
    _write_yaml(path, data)


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n...[truncated]...\n", True


def cmd_run(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    paths = task_runtime_paths(project, args.task_id)
    command = args.command
    if not command:
        print("[ERROR] command is empty", file=sys.stderr)
        return 2

    run_id = args.run_id or f"cmd_{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    output_dir = project / "state" / "agent_runs" / "command_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = output_dir / f"{run_id}.stdout.txt"
    stderr_path = output_dir / f"{run_id}.stderr.txt"

    started = _now()
    proc = subprocess.run(
        command,
        cwd=str(project / args.cwd) if args.cwd else str(project),
        shell=True,
        text=True,
        capture_output=True,
        timeout=args.timeout if args.timeout > 0 else None,
        check=False,
    )
    ended = _now()
    stdout_preview, stdout_truncated = _truncate(proc.stdout or "", args.preview_chars)
    stderr_preview, stderr_truncated = _truncate(proc.stderr or "", args.preview_chars)
    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")

    record = {
        "run_id": run_id,
        "stage": args.stage,
        "purpose": args.purpose,
        "command": command,
        "command_argv": shlex.split(command),
        "cwd": args.cwd or ".",
        "started_at": started,
        "ended_at": ended,
        "returncode": proc.returncode,
        "stdout_path": _relative(stdout_path, project),
        "stderr_path": _relative(stderr_path, project),
        "stdout_preview": stdout_preview,
        "stderr_preview": stderr_preview,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
    }
    _append_ledger(paths["command_ledger"], "commands", record)
    append_run_event(
        project,
        args.task_id,
        "command_completed",
        {
            "run_id": run_id,
            "purpose": args.purpose,
            "returncode": proc.returncode,
            "stdout_path": record["stdout_path"],
            "stderr_path": record["stderr_path"],
        },
        actor=args.actor,
        stage=args.stage,
        packet_path=args.packet,
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return proc.returncode


def _git_diff(project: Path, paths: list[str]) -> str:
    cmd = ["git", "diff", "--"]
    cmd.extend(paths or ["."])
    proc = subprocess.run(cmd, cwd=project, text=True, capture_output=True, check=False)
    return proc.stdout


def _file_record(project: Path, value: str) -> dict[str, Any]:
    path = Path(value)
    if not path.is_absolute():
        path = project / path
    record: dict[str, Any] = {
        "path": _relative(path, project),
        "exists": path.exists(),
    }
    if path.exists() and path.is_file():
        record.update({"bytes": path.stat().st_size, "sha256": _sha256_file(path)})
    elif path.exists() and path.is_dir():
        record.update({"kind": "directory"})
    return record


def cmd_record_change(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    paths = task_runtime_paths(project, args.task_id)
    change_id = args.change_id or f"change_{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    patch_dir = project / "state" / "agent_runs" / "patches"
    patch_dir.mkdir(parents=True, exist_ok=True)
    patch_path = patch_dir / f"{change_id}.diff"
    diff_text = _git_diff(project, args.paths)
    patch_path.write_text(diff_text, encoding="utf-8")

    record = {
        "change_id": change_id,
        "stage": args.stage,
        "purpose": args.purpose,
        "recorded_at": _now(),
        "patch_path": _relative(patch_path, project),
        "patch_bytes": patch_path.stat().st_size,
        "files": [_file_record(project, path) for path in args.paths],
        "validation": args.validation,
    }
    _append_ledger(paths["code_change_ledger"], "changes", record)
    append_run_event(
        project,
        args.task_id,
        "code_change_recorded",
        {
            "change_id": change_id,
            "patch_path": record["patch_path"],
            "file_count": len(args.paths),
            "validation": args.validation,
        },
        actor=args.actor,
        stage=args.stage,
        packet_path=args.packet,
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def cmd_paths(args: argparse.Namespace) -> int:
    paths = task_runtime_paths(args.project, args.task_id)
    print(json.dumps({key: str(value) for key, value in paths.items()}, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--stage", default="")
    parser.add_argument("--actor", default="")
    parser.add_argument("--packet", default="")
    sub = parser.add_subparsers(dest="command_name", required=True)

    run = sub.add_parser("run", help="Run a command and append a command ledger record")
    run.add_argument("--purpose", default="")
    run.add_argument("--cwd", default="")
    run.add_argument("--timeout", type=int, default=0)
    run.add_argument("--preview-chars", type=int, default=4000)
    run.add_argument("--run-id", default="")
    run.add_argument("command")
    run.set_defaults(func=cmd_run)

    change = sub.add_parser("record-change", help="Record a git diff and changed-file metadata")
    change.add_argument("--purpose", default="")
    change.add_argument("--change-id", default="")
    change.add_argument("--validation", default="")
    change.add_argument("paths", nargs="+")
    change.set_defaults(func=cmd_record_change)

    paths = sub.add_parser("paths", help="Print task ledger paths")
    paths.set_defaults(func=cmd_paths)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
