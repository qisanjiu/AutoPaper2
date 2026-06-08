"""Tests for scripts/orchestrator_guard.py — runtime boundary enforcement."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD_SCRIPT = Path(__file__).parent.parent / "scripts" / "orchestrator_guard.py"


def _make_fake_project(tmp_path: Path) -> Path:
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


class OrchestratorGuardFixture:
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.fake_project = _make_fake_project(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()


class TestOrchestratorGuardAllowed(OrchestratorGuardFixture, unittest.TestCase):
    """Paths that an orchestrator is allowed to write."""

    def test_state_file(self) -> None:
        code, out = _run_guard(self.fake_project, "state/pipeline_state.yaml")
        self.assertEqual(code, 0, out)
        self.assertIn("ALLOWED", out)

    def test_state_dispatch(self) -> None:
        code, out = _run_guard(self.fake_project, "state/dispatch/20260101-120000_task.md")
        self.assertEqual(code, 0, out)
        self.assertIn("ALLOWED", out)

    def test_config_file(self) -> None:
        code, out = _run_guard(self.fake_project, "config/execution_env.yaml")
        self.assertEqual(code, 0, out)
        self.assertIn("ALLOWED", out)

    def test_manifest(self) -> None:
        code, out = _run_guard(self.fake_project, "MANIFEST.md")
        self.assertEqual(code, 0, out)
        self.assertIn("ALLOWED", out)

    def test_handoff_m1_m2(self) -> None:
        code, out = _run_guard(self.fake_project, "knowledge/handoff_M1_M2.md")
        self.assertEqual(code, 0, out)
        self.assertIn("ALLOWED", out)

    def test_handoff_m5_completion(self) -> None:
        code, out = _run_guard(self.fake_project, "knowledge/handoff_M5_completion.md")
        self.assertEqual(code, 0, out)
        self.assertIn("ALLOWED", out)


class TestOrchestratorGuardForbidden(OrchestratorGuardFixture, unittest.TestCase):
    """Paths that an orchestrator must NOT write."""

    def test_stage_output_m1(self) -> None:
        code, out = _run_guard(self.fake_project, "knowledge/M1/M1S01_topic_scoping.md")
        self.assertEqual(code, 1, out)
        self.assertIn("FORBIDDEN", out)
        self.assertIn("dispatch stage", out)

    def test_stage_output_m2(self) -> None:
        code, out = _run_guard(self.fake_project, "knowledge/M2/M2S03_method_architecture.md")
        self.assertEqual(code, 1, out)
        self.assertIn("FORBIDDEN", out)

    def test_source_log(self) -> None:
        code, out = _run_guard(self.fake_project, "knowledge/M1/M1_source_log.yaml")
        self.assertEqual(code, 1, out)
        self.assertIn("FORBIDDEN", out)

    def test_review_file(self) -> None:
        code, out = _run_guard(self.fake_project, "knowledge/reviews/G2_logic_review.md")
        self.assertEqual(code, 1, out)
        self.assertIn("FORBIDDEN", out)

    def test_aggregate_review(self) -> None:
        code, out = _run_guard(self.fake_project, "knowledge/reviews/G1_aggregate.md")
        self.assertEqual(code, 1, out)
        self.assertIn("FORBIDDEN", out)

    def test_artifact_tex(self) -> None:
        code, out = _run_guard(self.fake_project, "artifacts/paper.tex")
        self.assertEqual(code, 1, out)
        self.assertIn("FORBIDDEN", out)

    def test_artifact_pdf(self) -> None:
        code, out = _run_guard(self.fake_project, "artifacts/paper.pdf")
        self.assertEqual(code, 1, out)
        self.assertIn("FORBIDDEN", out)

    def test_experiment_log(self) -> None:
        code, out = _run_guard(self.fake_project, "experiments/logs/m3s02_longrun_ledger.md")
        self.assertEqual(code, 1, out)
        self.assertIn("FORBIDDEN", out)

    def test_draft_file(self) -> None:
        code, out = _run_guard(self.fake_project, "drafts/M1S01/M1S01_draft.md")
        self.assertEqual(code, 1, out)
        self.assertIn("FORBIDDEN", out)


class TestOrchestratorGuardOutsideProject(OrchestratorGuardFixture, unittest.TestCase):
    """Paths outside the project root are not guarded."""

    def test_outside_project(self) -> None:
        code, out = _run_guard(self.fake_project, "/etc/passwd")
        self.assertEqual(code, 0, out)
        self.assertIn("Outside project scope", out)


class TestOrchestratorGuardUsage(unittest.TestCase):
    def test_no_args(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GUARD_SCRIPT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage", result.stdout)
