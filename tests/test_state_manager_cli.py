from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parent.parent


def _run_state_manager(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/state_manager.py", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class TestStateManagerCli(unittest.TestCase):
    def test_state_manager_help_flag_exits_zero(self) -> None:
        result = _run_state_manager("--help")

        self.assertEqual(result.returncode, 0)
        self.assertIn("AutoPaper2 State Manager", result.stdout)
        self.assertIn("list/list-projects", result.stdout)
        self.assertNotIn("Unknown command", result.stdout)

    def test_state_manager_list_alias_exits_zero(self) -> None:
        result = _run_state_manager("list")

        self.assertEqual(result.returncode, 0)
        self.assertTrue("PROJECTS in" in result.stdout or "No projects directory found" in result.stdout)
        self.assertNotIn("Unknown command", result.stdout)
