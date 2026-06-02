from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.subagent_launch_prompt import load_launch_prompt
from spiral.dispatch import build_stage_execution_packet, write_packets
from tests.test_dispatch import _make_project


class TestSubagentLaunchPrompt(unittest.TestCase):
    def test_extracts_json_launch_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(Path(tmp))
            packet = build_stage_execution_packet(root, "M2S01")
            path = write_packets(root, [packet], fmt="json")[0]

            prompt = load_launch_prompt(path)

            self.assertIn("project:state/dispatch/", prompt)
            self.assertIn("Task: stage_execution / method", prompt)
            self.assertIn("Do not use the parent conversation", prompt)
            self.assertIn("Role spec:", prompt)
            self.assertIn("framework:docs/AGENTS/_specs/method.md", prompt)
            self.assertNotIn(str(root), prompt)

    def test_extracts_markdown_launch_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(Path(tmp))
            packet = build_stage_execution_packet(root, "M2S01")
            path = write_packets(root, [packet], fmt="markdown")[0]

            prompt = load_launch_prompt(path)

            self.assertIn("project:state/dispatch/", prompt)
            self.assertIn("Task: stage_execution / method", prompt)
            self.assertNotIn("## Compact Launch Prompt", prompt)
            self.assertNotIn(str(root), prompt)


if __name__ == "__main__":
    unittest.main()
