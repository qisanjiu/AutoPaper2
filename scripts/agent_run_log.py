#!/usr/bin/env python3
# ruff: noqa: E402
"""Record delegated AutoPaper2 agent runtime events and artifact metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_framework_root = Path(__file__).parent.parent.resolve()
if str(_framework_root) not in sys.path:
    sys.path.insert(0, str(_framework_root))

from spiral.agent_runtime import append_run_event, task_runtime_paths, write_artifact_manifest


def _load_payload(value: str) -> dict[str, object]:
    if not value:
        return {}
    return json.loads(value)


def cmd_append(args: argparse.Namespace) -> int:
    event = append_run_event(
        args.project,
        args.task_id,
        args.event_type,
        _load_payload(args.payload_json),
        actor=args.actor,
        stage=args.stage,
        packet_path=args.packet,
    )
    paths = task_runtime_paths(args.project, args.task_id)
    print(json.dumps({"event": event, "event_log": str(paths["event_log"])}, ensure_ascii=False, indent=2))
    return 0


def cmd_record_artifact(args: argparse.Namespace) -> int:
    manifest = write_artifact_manifest(args.project, args.task_id, args.paths, append=not args.replace)
    append_run_event(
        args.project,
        args.task_id,
        "artifact_manifest_updated",
        {"manifest": str(manifest), "artifact_count": len(args.paths)},
        actor=args.actor,
        stage=args.stage,
        packet_path=args.packet,
    )
    print(str(manifest))
    return 0


def cmd_paths(args: argparse.Namespace) -> int:
    paths = task_runtime_paths(args.project, args.task_id)
    print(
        json.dumps(
            {key: str(value) for key, value in paths.items()},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Project root")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--actor", default="")
    parser.add_argument("--stage", default="")
    parser.add_argument("--packet", default="")
    sub = parser.add_subparsers(dest="command", required=True)

    append = sub.add_parser("append", help="Append a runtime event")
    append.add_argument("event_type")
    append.add_argument("--payload-json", default="{}")
    append.set_defaults(func=cmd_append)

    artifact = sub.add_parser("record-artifact", help="Update the artifact manifest with paths")
    artifact.add_argument("paths", nargs="+")
    artifact.add_argument("--replace", action="store_true", help="Replace previous artifact records")
    artifact.set_defaults(func=cmd_record_artifact)

    paths = sub.add_parser("paths", help="Print task runtime paths")
    paths.set_defaults(func=cmd_paths)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
