from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.context_budget import build_report, load_packet
from spiral.dispatch import packet_to_markdown


class TestContextBudget(unittest.TestCase):
    def test_json_packet_budget_warns_on_large_input_without_reading_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            large_input = root / "large.md"
            large_input.write_text("x" * 1024, encoding="utf-8")
            packet_path = root / "packet.json"
            packet = {
                "task_id": "budget_test",
                "task_type": "stage_execution",
                "project_root": str(root),
                "role": "experiment",
                "agent_md": str(root / "AGENT.md"),
                "role_spec": str(root / "spec.md"),
                "shared_contracts": [str(root / "runtime.md")],
                "input_docs": [str(large_input)],
                "output_path": str(root / "out.md"),
                "context_policy": {"no_parent_context": True},
            }
            (root / "AGENT.md").write_text("# Agent\n", encoding="utf-8")
            (root / "spec.md").write_text("# Spec\n" + "s" * 128, encoding="utf-8")
            (root / "runtime.md").write_text("# Runtime\n" + "r" * 128, encoding="utf-8")
            packet_path.write_text(json.dumps(packet), encoding="utf-8")

            report = build_report(load_packet(packet_path), warn_chars=500, fail_chars=5000)

            self.assertEqual(report["status"], "WARN")
            self.assertGreaterEqual(report["estimated_direct_read_chars"], 1280)
            self.assertTrue(any("large_text" in warning for warning in report["warnings"]))

    def test_markdown_packet_budget_parses_context_policy_and_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = root / "AGENT.md"
            input_doc = root / "input.md"
            output = root / "out.md"
            agent.write_text("# Agent\n", encoding="utf-8")
            input_doc.write_text("# Input\n", encoding="utf-8")
            packet = {
                "task_id": "budget_md",
                "task_type": "stage_review",
                "schema_version": "dispatch.v2",
                "delegation_required": True,
                "project_root": str(root),
                "role": "review",
                "agent_md": str(agent),
                "input_docs": [str(input_doc)],
                "output_path": str(output),
                "context_policy": {"handoff_mode": "packet_path_only", "no_parent_context": True},
                "subagent_boundaries": [],
                "main_agent_boundaries": [],
            }
            packet["subagent_launch_prompt"] = "Read and execute this AutoPaper2 dispatch packet:\npacket.md\n"
            packet_path = root / "packet.md"
            packet_path.write_text(packet_to_markdown(packet), encoding="utf-8")

            loaded = load_packet(packet_path)
            report = build_report(loaded, warn_chars=5000, fail_chars=10000)

            self.assertEqual(loaded["context_policy"]["no_parent_context"], True)
            self.assertIn(str(input_doc), loaded["input_docs"])
            self.assertEqual(report["status"], "OK")

    def test_portable_project_refs_resolve_from_packet_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dispatch_dir = root / "state" / "dispatch"
            dispatch_dir.mkdir(parents=True)
            (root / "AGENT.md").write_text("# Agent\n", encoding="utf-8")
            (root / "input.md").write_text("# Input\n", encoding="utf-8")
            packet_path = dispatch_dir / "packet.json"
            packet = {
                "task_id": "portable_budget",
                "task_type": "stage_execution",
                "project_root": "project:.",
                "role": "experiment",
                "agent_md": "project:AGENT.md",
                "input_docs": ["project:input.md"],
                "output_path": "project:out.md",
                "context_policy": {"no_parent_context": True},
            }
            packet_path.write_text(json.dumps(packet), encoding="utf-8")

            report = build_report(load_packet(packet_path), warn_chars=5000, fail_chars=10000)

            self.assertEqual(report["status"], "OK")
            self.assertEqual(report["path_count"], 3)


if __name__ == "__main__":
    unittest.main()
