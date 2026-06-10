#!/usr/bin/env python3
"""Build or query the project-local AutoPaper2 skill index."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

import yaml


def _read_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    block = text[4:end]
    try:
        data = yaml.safe_load(block) or {}
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        data: dict[str, str] = {}
        current_key = ""
        for raw in block.splitlines():
            if not raw.strip():
                continue
            if raw.startswith((" ", "\t")) and current_key:
                data[current_key] = (data.get(current_key, "") + " " + raw.strip()).strip()
                continue
            if ":" not in raw:
                continue
            key, value = raw.split(":", 1)
            current_key = key.strip()
            data[current_key] = value.strip().strip('"').strip("'")
        return data


def build_index(root: Path) -> dict[str, Any]:
    root = root.resolve()
    entries: list[dict[str, Any]] = []
    for skill_md in sorted((root / "skills").glob("*/SKILL.md")):
        frontmatter = _read_frontmatter(skill_md)
        name = str(frontmatter.get("name") or skill_md.parent.name)
        rel = skill_md.relative_to(root).as_posix()
        mirror = root / ".claude" / "skills" / skill_md.parent.name / "SKILL.md"
        entry = {
            "name": name,
            "path": rel,
            "mirror_path": mirror.relative_to(root).as_posix() if mirror.exists() else "",
            "skill_role": frontmatter.get("skill_role", ""),
            "argument_hint": frontmatter.get("argument-hint", ""),
            "description": str(frontmatter.get("description", "")).strip(),
        }
        entries.append(entry)

    return {
        "version": 1,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "canonical_root": "skills/",
        "claude_mirror_root": ".claude/skills/",
        "skills": entries,
    }


def _index_path(root: Path) -> Path:
    return root / "skills" / "index.yaml"


def cmd_build(args: argparse.Namespace) -> int:
    root = Path(args.root)
    index = build_index(root)
    if args.write:
        path = Path(args.output) if args.output else _index_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(index, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"[SKILL INDEX] Wrote {path}")
    elif args.json:
        print(json.dumps(index, ensure_ascii=False, indent=2))
    else:
        print(yaml.safe_dump(index, allow_unicode=True, sort_keys=False), end="")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    root = Path(args.root)
    path = _index_path(root)
    if path.exists():
        index = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        index = build_index(root)
    for entry in index.get("skills", []):
        if entry.get("name") == args.name:
            if args.json:
                print(json.dumps(entry, ensure_ascii=False, indent=2))
            else:
                print(f"name: {entry.get('name', '')}")
                print(f"path: {entry.get('path', '')}")
                print(f"skill_role: {entry.get('skill_role', '')}")
                print(f"description: {entry.get('description', '')}")
            return 0
    print(f"[ERROR] Skill not found: {args.name}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="AutoPaper2 framework root")
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build the skill index")
    build.add_argument("--write", action="store_true")
    build.add_argument("--output", default="")
    build.set_defaults(func=cmd_build)

    show = sub.add_parser("show", help="Show one indexed skill")
    show.add_argument("name")
    show.set_defaults(func=cmd_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
