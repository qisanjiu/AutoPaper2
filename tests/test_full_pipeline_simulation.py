#!/usr/bin/env python3
"""Tests for the no-LLM full-pipeline simulation harness."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.full_pipeline_simulator import run_simulation
from spiral.conductor import Conductor
from spiral.project import ProjectManager
from spiral.state import PipelineState


class TestFullPipelineSimulation(unittest.TestCase):
    def test_auto_advance_starts_current_next_module_without_skipping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = ProjectManager.create(
                topic="Auto advance simulation",
                display_name="Auto-Advance-Sim",
                projects_root=Path(tmp),
                venue="arxiv",
            )
            state = PipelineState(proj)
            state.set_auto_advance(True)
            state.set_module_status("M1", "completed", "M1S05")
            state.set_stage("M2S01", "module_completed")

            action = Conductor(proj).get_next_action()

            self.assertEqual(action["action"], "EXECUTE_STAGE")
            self.assertEqual(action["stage"], "M2S01")
            self.assertEqual(action["module"], "M2")
            state = PipelineState(proj)
            self.assertEqual(state.get_current_stage(), "M2S01")
            self.assertEqual(state.get_current_status(), "in_progress")
            self.assertEqual(state.get_module_status("M2").get("status"), "in_progress")

    def test_new_pipeline_states_do_not_share_nested_default_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            first.mkdir()
            second.mkdir()

            first_state = PipelineState(first)
            first_state.set_module_status("M5", "completed", "M5S09")

            second_state = PipelineState(second)

            self.assertEqual(second_state.get_module_status("M5").get("status"), "pending")

    def test_gate_verdict_rejects_unsupported_conditional(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = ProjectManager.create(
                topic="Gate verdict simulation",
                display_name="Gate-Verdict-Sim",
                projects_root=Path(tmp),
                venue="arxiv",
            )

            result = Conductor(proj).handle_gate_verdict(
                "G3",
                [{"critic": "evidence", "verdict": "CONDITIONAL", "reason": "trained weights pending"}],
            )

            self.assertEqual(result["action"], "BLOCKED")
            self.assertIn("unsupported verdict=CONDITIONAL", result["reason"])

    def test_no_llm_full_pipeline_simulation_reaches_m6_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_simulation(Path(tmp), keep_project=True)

            self.assertTrue(summary["ok"])
            self.assertEqual(summary["stage_advances"], 34)
            self.assertEqual(summary["gate_advances"], 6)
            self.assertTrue(summary["backtrack_exercised"])
            self.assertEqual(summary["final_stage"], "M6S06")
            self.assertEqual(summary["final_status"], "completed")
            self.assertEqual(summary["auto_starts"], ["M2S01", "M3S01", "M4S01", "M5S01", "M6S01"])
            self.assertGreaterEqual(summary["dispatch_packets"], 34)
            self.assertGreaterEqual(summary["history_entries"], 40)
            self.assertEqual(summary["backtrack_entries"], 1)


if __name__ == "__main__":
    unittest.main()
