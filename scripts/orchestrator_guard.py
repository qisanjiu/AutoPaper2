#!/usr/bin/env python3
"""Orchestrator Guard — runtime boundary enforcement for AutoPaper2.

This script is the universal enforcement layer that works across
Claude Code, KimiCode, Codex, and any other LLM deployment.
It does NOT depend on any platform-specific tool or hook.

Usage:
    python scripts/orchestrator_guard.py <project_root> <target_path>

Returns exit code:
    0  — write is allowed for orchestrator
    1  — FORBIDDEN: orchestrator must not write this path
    2  — usage error
"""

from __future__ import annotations

import fnmatch
import sys
from pathlib import Path


# Forbidden write patterns for an orchestrator-mode agent.
# These paths belong to executor / reviewer subagents.
FORBIDDEN_PATTERNS = [
    "knowledge/M*/M*S*.md",
    "knowledge/M*/M*_source_log.yaml",
    "drafts/*/*.md",
    "drafts/*/*_draft.md",
    "knowledge/reviews/*_review.md",
    "knowledge/reviews/*_aggregate.md",
    "artifacts/paper.*",
    "artifacts/*.tex",
    "artifacts/*.pdf",
    "experiments/logs/*.md",
    "experiments/logs/*.yaml",
]

# Allowed paths for an orchestrator (state, config, dispatch, handoff, logs)
ALLOWED_PREFIXES = [
    "state/",
    "config/",
    "MANIFEST.md",
]

# Allowed exact filenames
ALLOWED_EXACT = [
    "knowledge/handoff_M1_M2.md",
    "knowledge/handoff_M2_M3.md",
    "knowledge/handoff_M3_M4.md",
    "knowledge/handoff_M4_M5.md",
    "knowledge/handoff_M5_completion.md",
    "knowledge/handoff_M6_completion.md",
]


def check_orchestrator_write(project_root: str, target_path: str) -> tuple[bool, str]:
    """Check if writing target_path from an orchestrator is allowed."""
    root = Path(project_root).resolve()
    # If target_path is relative, resolve it relative to project_root
    # rather than the current working directory.
    target_raw = Path(target_path)
    if not target_raw.is_absolute():
        target = (root / target_raw).resolve()
    else:
        target = target_raw.resolve()

    # Must be inside project
    try:
        target.relative_to(root)
    except ValueError:
        return True, f"[ALLOWED] Outside project scope — not guarded: {target}"

    rel = target.relative_to(root)
    rel_str = str(rel).replace("\\", "/")

    # Check allowed exact filenames first
    if rel_str in ALLOWED_EXACT:
        return True, f"[ALLOWED] Orchestrator handoff path: {rel_str}"

    # Check allowed prefixes
    for prefix in ALLOWED_PREFIXES:
        if rel_str.startswith(prefix) or rel_str == prefix.rstrip("/"):
            return True, f"[ALLOWED] Orchestrator state/config path: {rel_str}"

    # Check forbidden patterns
    for pattern in FORBIDDEN_PATTERNS:
        if fnmatch.fnmatch(rel_str, pattern):
            return (
                False,
                (
                    f"[FORBIDDEN] Orchestrator attempted to write to {rel_str}\n"
                    f"  This path belongs to a subagent (executor / reviewer).\n"
                    f"  Correct action:\n"
                    f"    python scripts/state_manager.py dispatch stage <STAGE> --write\n"
                    f"  Then delegate the generated packet to the matching subagent."
                ),
            )

    return True, f"[ALLOWED] Unclassified path — allowed by default: {rel_str}"


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2:
        print("Usage: orchestrator_guard.py <project_root> <target_path>")
        print("Returns 0 if allowed, 1 if forbidden (orchestrator violation)")
        return 2

    project_root, target_path = args[0], args[1]
    allowed, msg = check_orchestrator_write(project_root, target_path)

    print(msg)
    return 0 if allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
