#!/usr/bin/env python3
"""Check project-local skill and agent prompt compatibility across CLIs.

AutoPaper2 must not rely on user-global skill installations.  Claude Code can
auto-discover ``.claude/skills``; Codex, KimiCode, and other CLIs can still
load the canonical project-local ``skills`` directory and dispatch packets.
This check verifies that both views are present, synchronized, and that every
stage/review/gate dispatch points at a readable project prompt.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _add_project_root(root: Path) -> None:
    value = str(root.resolve())
    if value not in sys.path:
        sys.path.insert(0, value)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_frontmatter(path: Path) -> dict[str, str]:
    text = _read_text(path)
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    block = text[4:end]
    data: dict[str, str] = {}
    current_key = ""
    for raw in block.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.startswith(" "):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        data[current_key] = value.strip()
    return data


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _check_skill_roots(root: Path, messages: list[str]) -> bool:
    ok = True
    canonical = root / "skills"
    claude = root / ".claude" / "skills"
    for label, path in (("canonical skills", canonical), ("Claude skills mirror", claude)):
        if not path.exists() or not path.is_dir():
            messages.append(f"[FAIL] {label} directory missing: {_relative(path, root)}")
            ok = False
        else:
            messages.append(f"[PASS] {label} directory exists: {_relative(path, root)}")
    if not ok:
        return False

    canonical_skills = {path.parent.name: path for path in canonical.glob("*/SKILL.md")}
    claude_skills = {path.parent.name: path for path in claude.glob("*/SKILL.md")}
    if not canonical_skills:
        messages.append("[FAIL] no project-local skills found under skills/*/SKILL.md")
        return False
    messages.append(f"[PASS] project-local skill count: {len(canonical_skills)}")

    missing_claude = sorted(set(canonical_skills) - set(claude_skills))
    extra_claude = sorted(set(claude_skills) - set(canonical_skills))
    if missing_claude:
        messages.append("[FAIL] .claude/skills missing: " + ", ".join(missing_claude))
        ok = False
    if extra_claude:
        messages.append("[FAIL] .claude/skills has extra skills: " + ", ".join(extra_claude))
        ok = False
    if not missing_claude and not extra_claude:
        messages.append("[PASS] .claude/skills contains the same skill set as skills/")

    required_frontmatter = ("name", "description", "skill_role")
    for name, path in sorted(canonical_skills.items()):
        frontmatter = _parse_frontmatter(path)
        missing = [field for field in required_frontmatter if not frontmatter.get(field)]
        if missing:
            messages.append(f"[FAIL] {name}: SKILL.md missing frontmatter fields: {', '.join(missing)}")
            ok = False
        elif frontmatter.get("name") != name:
            messages.append(f"[FAIL] {name}: frontmatter name={frontmatter.get('name')!r} does not match folder")
            ok = False
        else:
            messages.append(f"[PASS] {name}: frontmatter usable")

        mirror = claude_skills.get(name)
        if mirror and path.read_bytes() != mirror.read_bytes():
            messages.append(f"[FAIL] {name}: skills/ and .claude/skills/ copies differ")
            ok = False

    if ok:
        messages.append("[PASS] skills/ is the canonical source and .claude/skills/ is synchronized")
    return ok


def _check_agent_prompts(root: Path, messages: list[str]) -> bool:
    _add_project_root(root)
    from spiral.conductor import Conductor, GATE_CRITICS, STAGE_CHECKERS
    from spiral.project import MODULE_STAGES

    conductor = Conductor(root)
    ok = True
    stages = [stage for stage_list in MODULE_STAGES.values() for stage in stage_list]
    for stage in stages:
        agent_md = conductor.get_agent_md_path(stage)
        if not agent_md.exists():
            messages.append(f"[FAIL] stage {stage}: agent prompt missing: {_relative(agent_md, root)}")
            ok = False
        elif not _read_text(agent_md).strip():
            messages.append(f"[FAIL] stage {stage}: agent prompt empty: {_relative(agent_md, root)}")
            ok = False
    if ok:
        messages.append(f"[PASS] all {len(stages)} stage agent prompts exist and are readable")

    seen_reviewers: set[str] = set()
    for checkers in STAGE_CHECKERS.values():
        seen_reviewers.update(checkers)
    for critics in GATE_CRITICS.values():
        seen_reviewers.update(critics)
    for reviewer in sorted(seen_reviewers):
        agent_md = conductor.get_checker_md_path(reviewer)
        if not agent_md.exists():
            messages.append(f"[FAIL] reviewer {reviewer}: prompt missing: {_relative(agent_md, root)}")
            ok = False
        elif not _read_text(agent_md).strip():
            messages.append(f"[FAIL] reviewer {reviewer}: prompt empty: {_relative(agent_md, root)}")
            ok = False
    if ok:
        messages.append(f"[PASS] all {len(seen_reviewers)} reviewer/gate prompts exist and are readable")
    return ok


def _check_dispatch_packets(root: Path, messages: list[str]) -> bool:
    _add_project_root(root)
    from spiral.dispatch import build_gate_review_packets, build_stage_execution_packet, build_stage_review_packets
    from spiral.conductor import STAGE_CHECKERS
    from spiral.project import GATE_STAGES, MODULE_STAGES

    ok = True
    execution_packets = 0
    review_packets = 0
    gate_packets = 0

    for stage in [stage for stage_list in MODULE_STAGES.values() for stage in stage_list]:
        packet = build_stage_execution_packet(root, stage)
        execution_packets += 1
        agent_md = Path(packet.get("agent_md", ""))
        prompt = str(packet.get("subagent_prompt", ""))
        if not agent_md.exists():
            messages.append(f"[FAIL] dispatch stage {stage}: agent_md missing: {agent_md}")
            ok = False
        if "Role instructions:" not in prompt or "Project root:" not in prompt:
            messages.append(f"[FAIL] dispatch stage {stage}: subagent_prompt missing role/project path")
            ok = False

        if stage in STAGE_CHECKERS:
            for review_packet in build_stage_review_packets(root, stage):
                review_packets += 1
                review_agent = Path(review_packet.get("agent_md", ""))
                review_prompt = str(review_packet.get("subagent_prompt", ""))
                if not review_agent.exists():
                    messages.append(f"[FAIL] dispatch review {stage}: agent_md missing: {review_agent}")
                    ok = False
                if "Input paths (read directly; do not rely on summaries):" not in review_prompt:
                    messages.append(f"[FAIL] dispatch review {stage}: prompt missing direct-read instruction")
                    ok = False

    for gate_id in sorted(GATE_STAGES):
        for gate_packet in build_gate_review_packets(root, gate_id):
            gate_packets += 1
            gate_agent = Path(gate_packet.get("agent_md", ""))
            gate_prompt = str(gate_packet.get("subagent_prompt", ""))
            if not gate_agent.exists():
                messages.append(f"[FAIL] dispatch gate {gate_id}: agent_md missing: {gate_agent}")
                ok = False
            if "Rubric Results" not in gate_prompt:
                messages.append(f"[FAIL] dispatch gate {gate_id}: gate rubric missing from prompt")
                ok = False

    if ok:
        messages.append(
            f"[PASS] dispatch packets resolve local prompts "
            f"(stage={execution_packets}, reviews={review_packets}, gate={gate_packets})"
        )
    return ok


def _check_cli_instructions(root: Path, messages: list[str]) -> bool:
    ok = True
    agents = root / "AGENTS.md"
    if not agents.exists():
        messages.append("[FAIL] AGENTS.md missing at framework root")
        return False
    text = _read_text(agents)
    required = (
        "Project-Local Skill Loading",
        "skills/",
        ".claude/skills/",
        "scripts/cli_compat_check.py",
        "global",
    )
    for marker in required:
        if marker not in text:
            messages.append(f"[FAIL] AGENTS.md missing CLI-local skill instruction marker: {marker}")
            ok = False
    if ok:
        messages.append("[PASS] AGENTS.md documents project-local skill loading for non-Claude CLIs")
    return ok


def run_checks(root: Path) -> dict[str, Any]:
    root = root.resolve()
    messages: list[str] = []
    checks = {
        "skill_roots": _check_skill_roots(root, messages),
        "agent_prompts": _check_agent_prompts(root, messages),
        "dispatch_packets": _check_dispatch_packets(root, messages),
        "cli_instructions": _check_cli_instructions(root, messages),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "messages": messages,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate AutoPaper2 project-local CLI skill/prompt compatibility")
    parser.add_argument("--root", default=".", help="AutoPaper2 framework root")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of human-readable output")
    args = parser.parse_args(argv)

    result = run_checks(Path(args.root))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for message in result["messages"]:
            print(message)
        print("[PASS] CLI compatibility check passed" if result["ok"] else "[FAIL] CLI compatibility check failed")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
