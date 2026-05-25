"""Tests for scripts/orchestrator_guard.py — runtime boundary enforcement."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

GUARD_SCRIPT = Path(__file__).parent.parent / "scripts" / "orchestrator_guard.py"


@pytest.fixture
def fake_project(tmp_path: Path) -> Path:
    """Create a minimal project structure for guard testing."""
    proj = tmp_path / "fake-project"
    (proj / "state").mkdir(parents=True)
    (proj / "state" / "dispatch").mkdir(parents=True)
    (proj / "knowledge" / "M1").mkdir(parents=True)
    (proj / "knowledge" / "M2").mkdir(parents=True)
    (proj / "knowledge" / "reviews").mkdir(parents=True)
    (proj / "drafts" / "M1S01").mkdir(parents=True)
    (proj / "artifacts").mkdir(parents=True)
    (proj / "config").mkdir(parents=True)
    (proj / "experiments" / "logs").mkdir(parents=True)
    return proj


def _run_guard(project_root: Path, target_path: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(GUARD_SCRIPT), str(project_root), target_path],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


class TestOrchestratorGuardAllowed:
    """Paths that an orchestrator is allowed to write."""

    def test_state_file(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "state/pipeline_state.yaml")
        assert code == 0, out
        assert "ALLOWED" in out

    def test_state_dispatch(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "state/dispatch/20260101-120000_task.md")
        assert code == 0, out
        assert "ALLOWED" in out

    def test_config_file(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "config/execution_env.yaml")
        assert code == 0, out
        assert "ALLOWED" in out

    def test_manifest(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "MANIFEST.md")
        assert code == 0, out
        assert "ALLOWED" in out

    def test_handoff_m1_m2(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "knowledge/handoff_M1_M2.md")
        assert code == 0, out
        assert "ALLOWED" in out

    def test_handoff_m5_completion(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "knowledge/handoff_M5_completion.md")
        assert code == 0, out
        assert "ALLOWED" in out


class TestOrchestratorGuardForbidden:
    """Paths that an orchestrator must NOT write."""

    def test_stage_output_m1(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "knowledge/M1/M1S01_topic_scoping.md")
        assert code == 1, out
        assert "FORBIDDEN" in out
        assert "dispatch stage" in out

    def test_stage_output_m2(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "knowledge/M2/M2S03_method_architecture.md")
        assert code == 1, out
        assert "FORBIDDEN" in out

    def test_source_log(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "knowledge/M1/M1_source_log.yaml")
        assert code == 1, out
        assert "FORBIDDEN" in out

    def test_review_file(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "knowledge/reviews/G2_logic_review.md")
        assert code == 1, out
        assert "FORBIDDEN" in out

    def test_aggregate_review(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "knowledge/reviews/G1_aggregate.md")
        assert code == 1, out
        assert "FORBIDDEN" in out

    def test_artifact_tex(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "artifacts/paper.tex")
        assert code == 1, out
        assert "FORBIDDEN" in out

    def test_artifact_pdf(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "artifacts/paper.pdf")
        assert code == 1, out
        assert "FORBIDDEN" in out

    def test_experiment_log(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "experiments/logs/m3s01_longrun_ledger.md")
        assert code == 1, out
        assert "FORBIDDEN" in out

    def test_draft_file(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "drafts/M1S01/M1S01_draft.md")
        assert code == 1, out
        assert "FORBIDDEN" in out


class TestOrchestratorGuardOutsideProject:
    """Paths outside the project root are not guarded."""

    def test_outside_project(self, fake_project: Path) -> None:
        code, out = _run_guard(fake_project, "/etc/passwd")
        assert code == 0, out
        assert "Outside project scope" in out


class TestOrchestratorGuardUsage:
    def test_no_args(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GUARD_SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "Usage" in result.stdout
