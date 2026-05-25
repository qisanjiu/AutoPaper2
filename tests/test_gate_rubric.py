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
from utils.gate_rubric import get_gate_rubric, validate_gate_rubric


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


if __name__ == "__main__":
    unittest.main()
