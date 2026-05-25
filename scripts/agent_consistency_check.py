#!/usr/bin/env python3
"""Agent consistency check — verify all referenced AGENT.md files exist.

Usage:
    python scripts/agent_consistency_check.py

Checks:
1. Every stage in AGENT_FOR_STAGE has a corresponding AGENT.md
2. Every checker in STAGE_CHECKERS has a corresponding AGENT.md
3. Every gate critic in GATE_CRITICS has a corresponding AGENT.md

Exit code 0 if all consistent, non-zero otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    # Add project root to path
    project_root = Path(__file__).parent.parent.resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from spiral.project import AGENT_FOR_STAGE, MODULE_STAGES
    from spiral.conductor import STAGE_CHECKERS, GATE_CRITICS

    # Need a dummy project to instantiate Conductor for path resolution
    dummy_proj = project_root / "projects"
    from spiral.conductor import Conductor

    if dummy_proj.exists():
        # Use first existing project or create a temp path (Conductor only needs path for root)
        existing = [p for p in dummy_proj.iterdir() if p.is_dir() and (p / "state" / "pipeline_state.yaml").exists()]
        if existing:
            conductor = Conductor(existing[0])
        else:
            conductor = Conductor(dummy_proj)
    else:
        conductor = Conductor(project_root)

    issues = []

    print(f"\n{'='*60}")
    print("  AGENT CONSISTENCY CHECK")
    print(f"{'='*60}\n")

    # Check 1: AGENT_FOR_STAGE
    print("  [1] Checking AGENT_FOR_STAGE...")
    all_stages = [s for stages in MODULE_STAGES.values() for s in stages]
    for stage in all_stages:
        agent_md = conductor.get_agent_md_path(stage)
        if not agent_md.exists():
            issues.append(("AGENT_FOR_STAGE", stage, str(agent_md)))
            print(f"    [FAIL] {stage}: agent md missing -> {agent_md}")
    print(f"  {'[PASS]' if not any(i[0] == 'AGENT_FOR_STAGE' for i in issues) else '[FAIL]'} AGENT_FOR_STAGE check done\n")

    # Check 2: STAGE_CHECKERS
    print("  [2] Checking STAGE_CHECKERS...")
    for stage, checkers in STAGE_CHECKERS.items():
        for checker in checkers:
            checker_md = conductor.get_checker_md_path(checker)
            if not checker_md.exists():
                issues.append(("STAGE_CHECKERS", f"{stage}/{checker}", str(checker_md)))
                print(f"    [FAIL] {stage} checker '{checker}' md missing -> {checker_md}")
    print(f"  {'[PASS]' if not any(i[0] == 'STAGE_CHECKERS' for i in issues) else '[FAIL]'} STAGE_CHECKERS check done\n")

    # Check 3: GATE_CRITICS
    print("  [3] Checking GATE_CRITICS...")
    for gate, critics in GATE_CRITICS.items():
        for critic in critics:
            critic_md = conductor.get_checker_md_path(critic)
            if not critic_md.exists():
                issues.append(("GATE_CRITICS", f"{gate}/{critic}", str(critic_md)))
                print(f"    [FAIL] Gate {gate} critic '{critic}' md missing -> {critic_md}")
    print(f"  {'[PASS]' if not any(i[0] == 'GATE_CRITICS' for i in issues) else '[FAIL]'} GATE_CRITICS check done\n")

    print(f"{'='*60}")
    print(f"  Total issues: {len(issues)}")
    print(f"{'='*60}\n")

    if issues:
        print("[FAIL] Some referenced AGENT.md files are missing.\n")
        return 1

    print("[PASS] All referenced AGENT.md files exist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
