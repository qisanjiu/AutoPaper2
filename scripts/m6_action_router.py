#!/usr/bin/env python3
"""Parse M6S04 action plans into deterministic M6S05 revision routes.

Examples:
    python scripts/m6_action_router.py --project projects/XXX
    python scripts/m6_action_router.py --project projects/XXX --format markdown
    python scripts/m6_action_router.py --project projects/XXX --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_framework_root = Path(__file__).parent.parent.resolve()
if str(_framework_root) not in sys.path:
    sys.path.insert(0, str(_framework_root))

from spiral.revision_router import build_revision_routes


def _to_markdown(plan: dict) -> str:
    lines = [
        "# M6S05 Revision Routing Plan",
        "",
        f"- action_plan_path: `{plan.get('action_plan_path', '')}`",
        f"- earliest_target_stage: `{plan.get('earliest_target_stage', '')}`",
        "",
        "## Routes",
        "",
    ]
    routes = plan.get("routes", [])
    if not routes:
        lines.append("(none)")
    for route in routes:
        lines.extend(
            [
                f"### {route.get('target_stage', '')}",
                f"- responsible_agent: `{route.get('responsible_agent', '')}`",
                f"- item_ids: {', '.join(route.get('item_ids', []))}",
                f"- dispatch_command: `{route.get('dispatch_command', '')}`",
                "",
            ]
        )
    stage_advice = plan.get("stage_backtrack_advice", {})
    if stage_advice:
        lines.extend(["## Stage Backtrack Advice", ""])
        for stage, advice in stage_advice.items():
            lines.extend(
                [
                    f"### {stage}",
                    f"- item_ids: {', '.join(advice.get('m6_action_item_ids', []))}",
                    f"- direct_item_ids: {', '.join(advice.get('direct_item_ids', []))}",
                    f"- downstream_item_ids: {', '.join(advice.get('downstream_item_ids', []))}",
                    f"- rebuild_mode: `{advice.get('rebuild_mode', '')}`",
                    f"- rerun_scope: {advice.get('rerun_scope', '')}",
                    f"- required_fix: {str(advice.get('required_fix', '')).replace(chr(10), ' ')}",
                    "",
                ]
            )
    warnings = plan.get("warnings", [])
    if warnings:
        lines.extend(["## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project", required=True, help="Project root directory")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--write", action="store_true", help="Write route plan under state/dispatch")
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    plan = build_revision_routes(project_root)
    output = (
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
        if args.format == "json"
        else _to_markdown(plan)
    )

    if args.write:
        suffix = "json" if args.format == "json" else "md"
        out_dir = project_root / "state" / "dispatch"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"M6S05_revision_routes.{suffix}"
        out_path.write_text(output, encoding="utf-8")
        print(out_path)
        return 0

    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
