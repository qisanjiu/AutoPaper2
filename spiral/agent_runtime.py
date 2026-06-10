"""Lightweight runtime observability helpers for delegated AutoPaper2 agents."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

AGENT_RUNS_DIR = "state/agent_runs"
REVIEWER_MEMORY_REL = "knowledge/reviews/reviewer_memory.yaml"


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("password", "token", "secret", "private_key", "api_key")):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def slug_task_id(task_id: str) -> str:
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in task_id.strip())
    return safe.strip("._-") or "task"


def task_runtime_paths(project_root: str | Path, task_id: str) -> dict[str, Path]:
    root = Path(project_root)
    safe = slug_task_id(task_id)
    run_dir = root / AGENT_RUNS_DIR
    return {
        "event_log": run_dir / f"{safe}.jsonl",
        "artifact_manifest": run_dir / f"{safe}_artifacts.yaml",
        "command_ledger": run_dir / f"{safe}_commands.yaml",
        "code_change_ledger": run_dir / f"{safe}_code_changes.yaml",
    }


def append_run_event(
    project_root: str | Path,
    task_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    actor: str = "",
    stage: str = "",
    packet_path: str = "",
) -> dict[str, Any]:
    """Append one redacted runtime event for a delegated task."""
    paths = task_runtime_paths(project_root, task_id)
    event = {
        "ts": _now(),
        "task_id": slug_task_id(task_id),
        "event_type": event_type,
    }
    if actor:
        event["actor"] = actor
    if stage:
        event["stage"] = stage
    if packet_path:
        event["packet_path"] = packet_path
    if payload:
        event["payload"] = _redact(payload)

    path = paths["event_log"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def build_artifact_record(path: str | Path, project_root: str | Path) -> dict[str, Any]:
    """Return stable metadata for a file or directory artifact."""
    root = Path(project_root)
    artifact = Path(path)
    if not artifact.is_absolute():
        artifact = root / artifact

    record: dict[str, Any] = {
        "path": _relative(artifact, root),
        "exists": artifact.exists(),
        "recorded_at": _now(),
    }
    if not artifact.exists():
        record["kind"] = "missing"
        return record
    if artifact.is_dir():
        files = [item for item in artifact.rglob("*") if item.is_file()]
        record.update(
            {
                "kind": "directory",
                "file_count": len(files),
                "bytes": sum(item.stat().st_size for item in files),
            }
        )
        return record

    stat = artifact.stat()
    record.update(
        {
            "kind": "file",
            "bytes": stat.st_size,
            "sha256": _sha256_file(artifact),
            "modified_at": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        }
    )
    return record


def write_artifact_manifest(
    project_root: str | Path,
    task_id: str,
    artifact_paths: list[str | Path],
    *,
    append: bool = True,
) -> Path:
    """Write or update the per-task artifact manifest."""
    paths = task_runtime_paths(project_root, task_id)
    manifest_path = paths["artifact_manifest"]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if append and manifest_path.exists():
        existing = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}

    records = existing.get("artifacts", []) if isinstance(existing.get("artifacts"), list) else []
    records.extend(build_artifact_record(path, project_root) for path in artifact_paths)
    manifest = {
        "version": 1,
        "task_id": slug_task_id(task_id),
        "updated_at": _now(),
        "artifacts": records,
    }
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return manifest_path


def reviewer_memory_path(project_root: str | Path) -> Path:
    return Path(project_root) / REVIEWER_MEMORY_REL


def initial_reviewer_memory(project_name: str = "") -> dict[str, Any]:
    return {
        "version": 1,
        "project": project_name,
        "updated_at": _now(),
        "persistent_concerns": [],
        "resolved_concerns": [],
        "venue_pressure_points": [],
        "repeat_failure_patterns": [],
        "review_rounds": [],
    }


def ensure_reviewer_memory(project_root: str | Path, project_name: str = "") -> Path:
    path = reviewer_memory_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            yaml.safe_dump(initial_reviewer_memory(project_name), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    return path
