#!/usr/bin/env python3
"""Tests for gate-level rubric enforcement."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.state_manager import cmd_advance
from spiral.state import PipelineState
from utils.gate_rubric import gate_critic_review_paths, get_gate_rubric, validate_gate_critic_reviews, validate_gate_rubric


def _call_advance(
    project_dir: str,
    stage: str,
    agent: str,
    output_file: str,
    force: bool = False,
    skip_gates: bool = False,
) -> tuple[int | None, str]:
    stdout_capture = io.StringIO()
    exit_code = None
    try:
        with patch("sys.stdout", new=stdout_capture):
            cmd_advance(project_dir, stage, agent, output_file, force=force, skip_gates=skip_gates)
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    return exit_code, stdout_capture.getvalue()


def _setup_g1_project(root: Path) -> None:
    for rel in ("state", "knowledge/M1", "knowledge/reviews"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    state = PipelineState(root)
    state.data["project"] = {
        "name": root.name,
        "topic": "rubric test",
        "display_name": "rubric test",
        "created_at": "2026-05-23T00:00:00",
        "venue": {"id": "arxiv", "name": "arXiv"},
    }
    state.set_stage("M1S05", "waiting_gate")
    state.set_module_status("M1", "in_progress", "M1S05")
    for name in (
        "M1S02_literature_deepdive.md",
        "M1S03_research_question.md",
        "M1S04_hypothesis_generation.md",
        "M1S05_novelty_feasibility.md",
    ):
        (root / "knowledge" / "M1" / name).write_text(f"# {name}\n", encoding="utf-8")
    (root / "knowledge" / "M1" / "M1_source_log.yaml").write_text("sources: []\n", encoding="utf-8")
    _write_gate_critic_reviews(root, "G1")


def _setup_g3_project(root: Path) -> Path:
    for rel in ("state", "knowledge/M2", "knowledge/M3", "knowledge/reviews", "config", "experiments/configs", "experiments/logs", "experiments/baselines/baseline_1", "experiments/runs"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    for item in get_gate_rubric("G3").get("items", []):
        for rel in item.get("evidence_examples", []):
            path = root / rel
            if path.suffix:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# evidence\n", encoding="utf-8")
            else:
                path.mkdir(parents=True, exist_ok=True)
    _write_gate_critic_reviews(root, "G3")
    aggregate = root / "knowledge" / "reviews" / "G3_aggregate.md"
    aggregate.write_text(_rubric_aggregate(root, "G3"), encoding="utf-8")
    return aggregate


def _write_gate_critic_reviews(root: Path, gate_id: str) -> None:
    for critic, path in gate_critic_review_paths(root, gate_id).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# {gate_id} {critic} Review\n\n"
            "## Verdict\n"
            "Verdict: PASS\n\n"
            "## Rubric Results\n"
            "| Rubric ID | Verdict | Score | Evidence paths | Notes |\n"
            "|---|---|---|---|---|\n"
            f"| {gate_id}-R1 | PASS | 2/2 | knowledge/reviews | checked |\n",
            encoding="utf-8",
        )


def _rubric_aggregate(root: Path, gate_id: str, *, missing_last: bool = False) -> str:
    lines = [
        f"# {gate_id} Aggregate Review",
        "",
        "Verdict: PASS",
        "",
        "## Rubric Results",
        "",
        "| Rubric ID | Verdict | Score | Evidence paths | Notes |",
        "|---|---|---|---|---|",
    ]
    items = get_gate_rubric(gate_id).get("items", [])
    if missing_last:
        items = items[:-1]
    for item in items:
        evidence = next(
            (rel for rel in item.get("evidence_examples", []) if (root / rel).exists()),
            item.get("evidence_examples", ["knowledge/reviews"])[0],
        )
        lines.append(f"| {item.get('id', '')} | PASS | 2/2 | {evidence} | checked |")
    return "\n".join(lines) + "\n"


class TestGateRubricValidation(unittest.TestCase):
    def test_gate_rubric_rejects_bare_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            _setup_g1_project(root)
            aggregate = root / "knowledge" / "reviews" / "G1_aggregate.md"
            aggregate.write_text("# G1 Aggregate Review\n\nPASS\n", encoding="utf-8")

            ok, messages = validate_gate_rubric(root, "G1", aggregate)

            self.assertFalse(ok)
            self.assertTrue(any("missing Rubric Results" in message for message in messages))
            self.assertTrue(any("missing rubric row G1-R1" in message for message in messages))

    def test_gate_rubric_accepts_complete_evidence_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            _setup_g1_project(root)
            aggregate = root / "knowledge" / "reviews" / "G1_aggregate.md"
            aggregate.write_text(_rubric_aggregate(root, "G1"), encoding="utf-8")

            ok, messages = validate_gate_rubric(root, "G1", aggregate)

            self.assertTrue(ok, "\n".join(messages))
            self.assertTrue(any("rubric G1-R1 evidence path exists" in message for message in messages))

    def test_gate_critic_pass_cannot_hide_pending_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            _setup_g1_project(root)
            critic_path = gate_critic_review_paths(root, "G1")["logic"]
            critic_path.write_text(
                "# G1 logic Review\n\n"
                "Verdict: PASS\n\n"
                "Dataset download pending; maybe okay to proceed.\n",
                encoding="utf-8",
            )

            ok, messages = validate_gate_critic_reviews(root, "G1")

            self.assertFalse(ok)
            self.assertTrue(any("PASS verdict but contains blocking/ambiguous language" in message for message in messages), messages)

    def test_gate_aggregate_pass_cannot_hide_pending_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            _setup_g1_project(root)
            aggregate = root / "knowledge" / "reviews" / "G1_aggregate.md"
            aggregate.write_text(
                _rubric_aggregate(root, "G1") + "\nCheckpoint download pending but probably acceptable.\n",
                encoding="utf-8",
            )

            ok, messages = validate_gate_rubric(root, "G1", aggregate)

            self.assertFalse(ok)
            self.assertTrue(any("aggregate verdict PASS but review contains blocking/ambiguous language" in message for message in messages), messages)

    def test_gate_advance_blocks_missing_rubric_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            _setup_g1_project(root)
            aggregate = root / "knowledge" / "reviews" / "G1_aggregate.md"
            aggregate.write_text(_rubric_aggregate(root, "G1", missing_last=True), encoding="utf-8")

            exit_code, output = _call_advance(str(root), "M1S05", "critic_team", str(aggregate))

            self.assertEqual(exit_code, 1, output)
            self.assertIn("Gate rubric validation failed", output)
            self.assertIn("missing rubric row G1-R3", output)

    def test_gate_advance_blocks_individual_revise_even_if_aggregate_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            _setup_g1_project(root)
            aggregate = root / "knowledge" / "reviews" / "G1_aggregate.md"
            aggregate.write_text(_rubric_aggregate(root, "G1"), encoding="utf-8")
            critic_review = root / "knowledge" / "reviews" / "G1_logic_review.md"
            critic_review.write_text(
                "# G1 Logic Review\n\n"
                "Verdict: REVISE\n\n"
                "- target_stage: M1S05\n"
                "- blocking_reason: missing evidence\n"
                "- required_fix: add evidence\n"
                "- success_criteria: review can pass\n"
                "- rebuild_mode: incremental_replay\n"
                "- rerun_scope: M1S05\n",
                encoding="utf-8",
            )

            critic_ok, critic_messages = validate_gate_critic_reviews(root, "G1")
            exit_code, output = _call_advance(str(root), "M1S05", "critic_team", str(aggregate))

            self.assertFalse(critic_ok, "\n".join(critic_messages))
            joined = "\n".join(critic_messages)
            self.assertIn("evidence_paths", joined)
            self.assertIn("handoff_updates", joined)
            self.assertEqual(exit_code, 1, output)
            self.assertIn("aggregate PASS cannot override individual critic verdicts", output)

    def test_gate_critic_rejects_code_patch_advice_without_code_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            _setup_g1_project(root)
            critic_review = root / "knowledge" / "reviews" / "G1_logic_review.md"
            critic_review.write_text(
                "# G1 Logic Review\n\n"
                "## Verdict\n"
                "Verdict: REVISE\n\n"
                "## Evidence Checked\n"
                "- knowledge/M1/M1S05_novelty_feasibility.md: observed unresolved implementation claim only\n\n"
                "## Repair Fields\n"
                "- target_stage: M1S05\n"
                "- blocking_reason: Markdown claim implies implementation evidence is missing, but code was not inspected.\n"
                "- required_fix: Change experiments/eval.py line 42 to call `evaluate_fixed()`.\n"
                "- success_criteria: implementation evidence is inspected, repaired if needed, and re-reviewed.\n"
                "- evidence_paths: knowledge/M1/M1S05_novelty_feasibility.md\n"
                "- rebuild_mode: full_regenerate\n"
                "- rerun_scope: M1S05 -> G1\n"
                "- handoff_updates: refresh knowledge/handoff_M1_M2.md\n",
                encoding="utf-8",
            )

            ok, messages = validate_gate_critic_reviews(root, "G1")

            self.assertFalse(ok)
            self.assertIn("code-level repair advice lacks direct code/config/log evidence", "\n".join(messages))

    def test_gate_advance_blocks_unsupported_conditional_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            _setup_g1_project(root)
            aggregate = root / "knowledge" / "reviews" / "G1_aggregate.md"
            aggregate.write_text(_rubric_aggregate(root, "G1"), encoding="utf-8")
            (root / "knowledge" / "reviews" / "G1_coverage_review.md").write_text(
                "# G1 Coverage Review\n\nVerdict: CONDITIONAL\n",
                encoding="utf-8",
            )

            exit_code, output = _call_advance(str(root), "M1S05", "critic_team", str(aggregate))

            self.assertEqual(exit_code, 1, output)
            self.assertIn("unsupported verdict=CONDITIONAL", output)

    def test_gate_advance_accepts_complete_rubric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            _setup_g1_project(root)
            aggregate = root / "knowledge" / "reviews" / "G1_aggregate.md"
            aggregate.write_text(_rubric_aggregate(root, "G1"), encoding="utf-8")

            exit_code, output = _call_advance(str(root), "M1S05", "critic_team", str(aggregate))

            self.assertIsNone(exit_code, output)
            self.assertIn("MODULE COMPLETE", output)

    def test_g3_rubric_requires_m3s05_validation_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            aggregate = _setup_g3_project(root)

            def fake_check_stage(_root: Path, stage: str) -> tuple[bool, list[str]]:
                if stage == "M3S04":
                    return True, ["[PASS] M3S04: evidence gate pass"]
                if stage == "M3S05":
                    return False, ["[FAIL] M3S05: result-validation review missing"]
                raise AssertionError(stage)

            with patch("utils.stage_gate.check_stage", side_effect=fake_check_stage):
                ok, messages = validate_gate_rubric(root, "G3", aggregate)

            self.assertFalse(ok, "\n".join(messages))
            self.assertTrue(any("M3S05 validation gate is not currently PASS" in message for message in messages), messages)

    def test_force_quality_bypass_disabled_without_debug_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            _setup_g1_project(root)
            aggregate = root / "knowledge" / "reviews" / "G1_aggregate.md"
            aggregate.write_text(_rubric_aggregate(root, "G1"), encoding="utf-8")

            with patch.dict("os.environ", {"AUTOPAPER2_ALLOW_QUALITY_BYPASS": ""}, clear=False):
                exit_code, output = _call_advance(str(root), "M1S05", "critic_team", str(aggregate), force=True)

            self.assertEqual(exit_code, 1, output)
            self.assertIn("--force quality bypass is disabled", output)

    def test_skip_gates_bypass_disabled_for_stage_outputs_without_debug_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            _setup_g1_project(root)
            output = root / "knowledge" / "M1" / "M1S05_novelty_feasibility.md"

            with patch.dict("os.environ", {"AUTOPAPER2_ALLOW_QUALITY_BYPASS": ""}, clear=False):
                exit_code, output_text = _call_advance(str(root), "M1S05", "ideation", str(output), skip_gates=True)

            self.assertEqual(exit_code, 1, output_text)
            self.assertIn("--skip-gates is disabled", output_text)


if __name__ == "__main__":
    unittest.main()
