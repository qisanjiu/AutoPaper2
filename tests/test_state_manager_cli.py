from __future__ import annotations

import subprocess
import sys
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


def test_state_manager_help_flag_exits_zero() -> None:
    result = _run_state_manager("--help")

    assert result.returncode == 0
    assert "AutoPaper2 State Manager" in result.stdout
    assert "list/list-projects" in result.stdout
    assert "Unknown command" not in result.stdout


def test_state_manager_list_alias_exits_zero() -> None:
    result = _run_state_manager("list")

    assert result.returncode == 0
    assert "PROJECTS in" in result.stdout or "No projects directory found" in result.stdout
    assert "Unknown command" not in result.stdout
