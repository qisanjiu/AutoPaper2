#!/usr/bin/env python3
"""Runtime watchdog for long-running AutoPaper2 experiments.

The watchdog is intentionally conservative: it observes logs and metric files,
records alerts, and asks for an agent decision. It does not terminate the
training process. The Experiment Agent remains responsible for deciding whether
to continue, fix, or early-stop a run after reading the evidence.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


DEFAULT_INTERVAL_SECONDS = 4 * 60 * 60
DEFAULT_TAIL_BYTES = 1024 * 1024

BAD_LOG_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("nan_or_inf", re.compile(r"\b(?:nan|inf|-inf|\+inf|infinite|non[- ]?finite)\b", re.IGNORECASE)),
    ("oom", re.compile(r"(?:out of memory|cuda.*oom|resourceexhausted)", re.IGNORECASE)),
    ("divergence", re.compile(r"(?:diverg|explod|overflow|gradient.*(?:nan|inf))", re.IGNORECASE)),
    ("exception", re.compile(r"(?:traceback \(most recent call last\)|runtimeerror|valueerror|assertionerror)", re.IGNORECASE)),
)

LOSS_NAME_PATTERNS = ("loss", "train_loss", "val_loss", "valid_loss", "validation_loss")
METRIC_NAME_PATTERNS = ("accuracy", "acc", "f1", "auc", "score", "metric", "reward")


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _append_jsonl(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=False) + "\n")


def _tail_text(path: Path, limit: int = DEFAULT_TAIL_BYTES) -> str:
    if not path.exists() or not path.is_file():
        return ""
    with path.open("rb") as handle:
        try:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - limit), os.SEEK_SET)
        except OSError:
            handle.seek(0)
        return handle.read().decode("utf-8", errors="ignore")


def _is_pid_alive(pid: int | None) -> bool | None:
    if pid is None:
        return None
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else math.nan


def _detect_delimiter(path: Path, sample: str) -> str:
    if path.suffix.lower() == ".tsv":
        return "\t"
    if path.suffix.lower() == ".csv":
        return ","
    try:
        return csv.Sniffer().sniff(sample[:2048], delimiters=",\t").delimiter
    except csv.Error:
        return "\t" if "\t" in sample.splitlines()[0] else ","


def _read_table(path: Path) -> list[dict[str, str]]:
    if not path.exists() or not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return []
    delimiter = _detect_delimiter(path, "\n".join(lines[:5]))
    return list(csv.DictReader(lines, delimiter=delimiter))


def _pick_columns(rows: list[dict[str, str]], preferred: list[str], patterns: tuple[str, ...]) -> list[str]:
    if not rows:
        return []
    columns = [str(column) for column in rows[0].keys()]
    lowered = {column.lower(): column for column in columns}
    picked: list[str] = []
    for name in preferred:
        column = lowered.get(name.lower())
        if column and column not in picked:
            picked.append(column)
    for column in columns:
        lower = column.lower()
        if column in picked:
            continue
        if any(pattern in lower for pattern in patterns):
            picked.append(column)
    return picked


def _numeric_series(rows: list[dict[str, str]], column: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = _coerce_float(row.get(column))
        if value is not None:
            values.append(value)
    return values


def _relative_change(start: float, end: float) -> float:
    denom = max(abs(start), 1e-12)
    return (end - start) / denom


def _inspect_metric_series(
    *,
    label: str,
    values: list[float],
    direction: str,
    min_delta: float,
    patience_points: int,
    target: float | None,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    if not values:
        return signals

    latest = values[-1]
    if not math.isfinite(latest):
        signals.append(
            {
                "kind": "non_finite_metric",
                "severity": "critical",
                "label": label,
                "latest": str(latest),
                "message": f"{label} latest value is non-finite",
            }
        )
        return signals

    window = values[-max(2, patience_points) :]
    finite_window = [value for value in window if math.isfinite(value)]
    if len(finite_window) < 2:
        return signals

    start, end = finite_window[0], finite_window[-1]
    rel = _relative_change(start, end)
    if direction == "lower":
        improved = -rel
        worse = rel > min_delta
    else:
        improved = rel
        worse = -rel > min_delta

    if worse:
        signals.append(
            {
                "kind": "metric_worsening",
                "severity": "warning",
                "label": label,
                "window_start": start,
                "window_end": end,
                "relative_change": rel,
                "message": f"{label} worsened over the latest watchdog window",
            }
        )
    elif abs(improved) < min_delta:
        signals.append(
            {
                "kind": "plateau_or_converged",
                "severity": "early_stop_candidate",
                "label": label,
                "window_start": start,
                "window_end": end,
                "relative_improvement": improved,
                "message": f"{label} improved by less than min_delta over the latest watchdog window",
            }
        )

    if target is not None:
        reached = latest <= target if direction == "lower" else latest >= target
        if reached:
            signals.append(
                {
                    "kind": "target_reached",
                    "severity": "early_stop_candidate",
                    "label": label,
                    "latest": latest,
                    "target": target,
                    "message": f"{label} reached the configured target",
                }
            )
    return signals


def _severity(signals: list[dict[str, Any]], pid_alive: bool | None) -> str:
    severities = {str(signal.get("severity", "")) for signal in signals}
    if "critical" in severities:
        return "critical"
    if "warning" in severities:
        return "warning"
    if "early_stop_candidate" in severities:
        return "early_stop_candidate"
    if pid_alive is False:
        return "completed"
    return "info"


def _default_paths(project: Path, run_id: str) -> tuple[list[Path], list[Path]]:
    run_root = project / "experiments" / "runs" / run_id
    logs: list[Path] = []
    metrics: list[Path] = []
    if run_root.exists():
        for pattern in ("*.log", "*.txt", "logs/*.log", "logs/*.txt"):
            logs.extend(sorted(run_root.glob(pattern)))
        for pattern in ("metrics.csv", "metrics.tsv", "results.csv", "results.tsv", "curves/*.csv", "curves/*.tsv"):
            metrics.extend(sorted(run_root.glob(pattern)))
    return sorted(set(logs)), sorted(set(metrics))


def inspect_run(
    *,
    project: Path,
    run_id: str,
    log_paths: list[Path] | None = None,
    metric_paths: list[Path] | None = None,
    pid: int | None = None,
    metric_col: str | None = None,
    metric_direction: str = "higher",
    min_delta: float = 0.01,
    patience_points: int = 3,
    target: float | None = None,
    events_path: Path | None = None,
    checks_path: Path | None = None,
    alerts_path: Path | None = None,
) -> dict[str, Any]:
    project = project.resolve()
    default_logs, default_metrics = _default_paths(project, run_id)
    logs = log_paths if log_paths is not None and log_paths else default_logs
    metrics = metric_paths if metric_paths is not None and metric_paths else default_metrics
    logs = [path if path.is_absolute() else project / path for path in logs]
    metrics = [path if path.is_absolute() else project / path for path in metrics]

    signals: list[dict[str, Any]] = []
    for log_path in logs:
        tail = _tail_text(log_path)
        for kind, pattern in BAD_LOG_PATTERNS:
            match = pattern.search(tail)
            if match:
                signals.append(
                    {
                        "kind": kind,
                        "severity": "critical",
                        "path": str(log_path.relative_to(project) if log_path.is_relative_to(project) else log_path),
                        "message": f"bad runtime pattern detected: {match.group(0)}",
                    }
                )

    for metric_path in metrics:
        rows = _read_table(metric_path)
        if not rows:
            continue
        loss_columns = _pick_columns(rows, [], LOSS_NAME_PATTERNS)
        for column in loss_columns:
            values = _numeric_series(rows, column)
            signals.extend(
                _inspect_metric_series(
                    label=f"{metric_path.name}:{column}",
                    values=values,
                    direction="lower",
                    min_delta=min_delta,
                    patience_points=patience_points,
                    target=None,
                )
            )

        if metric_col:
            metric_columns = [metric_col]
        else:
            metric_columns = _pick_columns(rows, [], METRIC_NAME_PATTERNS)
        for column in metric_columns:
            if column in loss_columns:
                continue
            if column not in rows[0]:
                continue
            values = _numeric_series(rows, column)
            signals.extend(
                _inspect_metric_series(
                    label=f"{metric_path.name}:{column}",
                    values=values,
                    direction=metric_direction,
                    min_delta=min_delta,
                    patience_points=patience_points,
                    target=target,
                )
            )

    pid_alive = _is_pid_alive(pid)
    severity = _severity(signals, pid_alive)
    decision_required = severity in {"critical", "warning", "early_stop_candidate"}
    event = {
        "timestamp": _now(),
        "stage": "M3S03",
        "event_type": "watchdog_check",
        "run_id": run_id,
        "severity": severity,
        "decision_required": decision_required,
        "agent_action_policy": "record_alert_only_agent_decides_continue_fix_or_stop",
        "pid": pid,
        "pid_alive": pid_alive,
        "log_paths": [str(path.relative_to(project) if path.is_relative_to(project) else path) for path in logs],
        "metric_paths": [str(path.relative_to(project) if path.is_relative_to(project) else path) for path in metrics],
        "signals": signals,
    }

    run_root = project / "experiments" / "runs" / run_id
    events_path = events_path or project / "experiments" / "logs" / "runtime_events.jsonl"
    checks_path = checks_path or run_root / "watchdog_checks.jsonl"
    alerts_path = alerts_path or run_root / "watchdog_alerts.jsonl"
    _append_jsonl(events_path, event)
    _append_jsonl(checks_path, event)
    if decision_required:
        _append_jsonl(alerts_path, event)
    return event


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=".", help="Project root")
    parser.add_argument("--run-id", required=True, help="Run id under experiments/runs/")
    parser.add_argument("--log", action="append", default=[], help="Log file to inspect; repeatable")
    parser.add_argument("--metrics", action="append", default=[], help="CSV/TSV metric file to inspect; repeatable")
    parser.add_argument("--pid", type=int, default=None, help="Optional process id to observe")
    parser.add_argument("--metric-col", default=None, help="Primary metric column name")
    parser.add_argument("--metric-direction", choices=("higher", "lower"), default="higher")
    parser.add_argument("--min-delta", type=float, default=0.01, help="Relative improvement threshold")
    parser.add_argument("--patience-points", type=int, default=3, help="Latest metric points per watchdog decision")
    parser.add_argument("--target", type=float, default=None, help="Optional early-stop target")
    parser.add_argument("--events", default=None, help="runtime_events.jsonl path")
    parser.add_argument("--checks", default=None, help="watchdog_checks.jsonl path")
    parser.add_argument("--alerts", default=None, help="watchdog_alerts.jsonl path")
    parser.add_argument("--quiet", action="store_true", help="Suppress one-line summaries")


def _paths(values: list[str]) -> list[Path]:
    return [Path(value) for value in values if value]


def _print_summary(event: dict[str, Any]) -> None:
    print(
        "[WATCHDOG] "
        f"run={event['run_id']} severity={event['severity']} "
        f"decision_required={str(event['decision_required']).lower()} "
        f"signals={len(event.get('signals', []))}"
    )


def _inspect_from_args(args: argparse.Namespace) -> dict[str, Any]:
    project = Path(args.project)
    event = inspect_run(
        project=project,
        run_id=args.run_id,
        log_paths=_paths(args.log),
        metric_paths=_paths(args.metrics),
        pid=args.pid,
        metric_col=args.metric_col,
        metric_direction=args.metric_direction,
        min_delta=args.min_delta,
        patience_points=args.patience_points,
        target=args.target,
        events_path=Path(args.events) if args.events else None,
        checks_path=Path(args.checks) if args.checks else None,
        alerts_path=Path(args.alerts) if args.alerts else None,
    )
    if not args.quiet:
        _print_summary(event)
    return event


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Observe long-running AutoPaper2 experiment runs without terminating them")
    sub = parser.add_subparsers(dest="cmd", required=True)

    inspect_p = sub.add_parser("inspect", help="Run one watchdog inspection")
    _add_common_args(inspect_p)

    watch_p = sub.add_parser("watch", help="Inspect periodically until max checks or pid exits")
    _add_common_args(watch_p)
    watch_p.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    watch_p.add_argument("--max-checks", type=int, default=0, help="0 means unlimited")

    args = parser.parse_args(argv)
    if args.cmd == "inspect":
        _inspect_from_args(args)
        return 0

    if args.cmd == "watch":
        checks = 0
        while True:
            event = _inspect_from_args(args)
            checks += 1
            if args.max_checks and checks >= args.max_checks:
                break
            if args.pid is not None and event.get("pid_alive") is False:
                break
            time.sleep(max(1, args.interval_seconds))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
