#!/usr/bin/env python3
"""Generate AutoPaper2 subagent dispatch packets.

Examples:
    python scripts/agent_dispatch.py --project projects/XXX next --write
    python scripts/agent_dispatch.py --project projects/XXX stage M3S01 --format json
    python scripts/agent_dispatch.py --project projects/XXX reviews M2S01 --write
    python scripts/agent_dispatch.py --project projects/XXX gate G3 --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_framework_root = Path(__file__).parent.parent.resolve()
if str(_framework_root) not in sys.path:
    sys.path.insert(0, str(_framework_root))

from spiral.dispatch import build_packets, packet_to_markdown, packets_to_json, write_packets


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Project root directory")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format",
    )
    parser.add_argument("--write", action="store_true", help="Write packet files under state/dispatch")
    parser.add_argument("--out-dir", default="", help="Optional output directory for --write")

    sub = parser.add_subparsers(dest="scope", required=True)

    def add_common(subparser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        subparser.add_argument(
            "--format",
            choices=("markdown", "json"),
            default=argparse.SUPPRESS,
            help="Output format",
        )
        subparser.add_argument(
            "--write",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Write packet files under state/dispatch",
        )
        subparser.add_argument(
            "--out-dir",
            default=argparse.SUPPRESS,
            help="Optional output directory for --write",
        )
        return subparser

    add_common(sub.add_parser("next", help="Build packets for Conductor.get_next_action()"))

    stage = add_common(sub.add_parser("stage", help="Build one stage execution packet"))
    stage.add_argument("target", nargs="?", help="Stage id, defaults to current stage")

    reviews = add_common(sub.add_parser("reviews", help="Build stage-review packets"))
    reviews.add_argument("target", help="Stage id")

    gate = add_common(sub.add_parser("gate", help="Build gate critic packets"))
    gate.add_argument("target", nargs="?", help="Gate id or gate stage, defaults to current stage")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        packets = build_packets(args.project, args.scope, getattr(args, "target", None))
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if args.write:
        paths = write_packets(
            args.project,
            packets,
            fmt=args.format,
            out_dir=args.out_dir or None,
        )
        for path in paths:
            print(path)
        return 0

    if args.format == "json":
        print(packets_to_json(packets))
    else:
        for idx, packet in enumerate(packets):
            if idx:
                print("\n---\n")
            print(packet_to_markdown(packet))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
