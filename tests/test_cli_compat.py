#!/usr/bin/env python3
"""Tests for project-local CLI skill compatibility."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.cli_compat_check import run_checks


class TestCliCompatibility(unittest.TestCase):
    def test_project_local_skills_and_prompts_are_compatible(self) -> None:
        result = run_checks(_project_root)

        self.assertTrue(result["ok"], "\n".join(result["messages"]))
        self.assertTrue(result["checks"]["skill_roots"])
        self.assertTrue(result["checks"]["agent_prompts"])
        self.assertTrue(result["checks"]["dispatch_packets"])
        self.assertTrue(result["checks"]["cli_instructions"])


if __name__ == "__main__":
    unittest.main()
