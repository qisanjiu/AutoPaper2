#!/usr/bin/env python3
# ruff: noqa: E402
"""Add, refresh, or verify AutoPaper2 Markdown section anchors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_framework_root = Path(__file__).parent.parent.resolve()
if str(_framework_root) not in sys.path:
    sys.path.insert(0, str(_framework_root))

from utils.markdown_sections import add_or_refresh_heading_anchors, verify_section_anchors


def _default_namespace(path: Path) -> str:
    stem = path.stem
    if "_" in stem:
        return stem.split("_", 1)[0]
    return stem


def _render_checks(path: Path) -> dict[str, object]:
    checks = verify_section_anchors(path.read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "anchor_count": len(checks),
        "ok": bool(checks) and all(check.ok for check in checks),
        "sections": [
            {
                "section_id": check.section_id,
                "expected_sha256": check.expected_sha256,
                "actual_sha256": check.actual_sha256,
                "ok": check.ok,
            }
            for check in checks
        ],
    }


def cmd_refresh(args: argparse.Namespace) -> int:
    path = Path(args.path)
    text = path.read_text(encoding="utf-8")
    namespace = args.namespace or _default_namespace(path)
    path.write_text(add_or_refresh_heading_anchors(text, namespace), encoding="utf-8")
    print(f"[REFRESHED] {path}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    path = Path(args.path)
    report = _render_checks(path)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Markdown Section Anchor Report: {path}")
        print(f"- anchor_count: {report['anchor_count']}")
        print(f"- ok: {report['ok']}")
        for item in report["sections"]:
            status = "OK" if item["ok"] else "STALE"
            print(f"- {status}: {item['section_id']}")
    return 0 if report["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    refresh = sub.add_parser("refresh", help="Insert or refresh section anchors in place")
    refresh.add_argument("path")
    refresh.add_argument("--namespace", default="", help="Section id prefix, defaults to the file stem/stage")
    refresh.set_defaults(func=cmd_refresh)

    verify = sub.add_parser("verify", help="Verify existing section anchors")
    verify.add_argument("path")
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
