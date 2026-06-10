from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from spiral.agent_runtime import append_run_event, ensure_reviewer_memory, write_artifact_manifest
from utils.markdown_sections import add_or_refresh_heading_anchors, verify_section_anchors


class TestAgentRuntime(unittest.TestCase):
    def test_runtime_event_log_redacts_secrets_and_artifact_manifest_records_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifacts" / "result.txt"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("result\n", encoding="utf-8")

            append_run_event(
                root,
                "M3S04_experiment_execute",
                "packet_read",
                {"api_key": "secret-value", "status": "ok"},
            )
            manifest = write_artifact_manifest(root, "M3S04_experiment_execute", [artifact])

            event_path = root / "state" / "agent_runs" / "M3S04_experiment_execute.jsonl"
            event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(event["payload"]["api_key"], "[REDACTED]")
            self.assertEqual(event["payload"]["status"], "ok")

            data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["artifacts"][0]["path"], "artifacts/result.txt")
            self.assertEqual(data["artifacts"][0]["kind"], "file")
            self.assertIn("sha256", data["artifacts"][0])

    def test_runtime_paths_include_code_and_command_ledgers(self) -> None:
        from spiral.agent_runtime import task_runtime_paths

        with tempfile.TemporaryDirectory() as tmp:
            paths = task_runtime_paths(tmp, "M3S04_experiment_execute")

            self.assertTrue(str(paths["command_ledger"]).endswith("M3S04_experiment_execute_commands.yaml"))
            self.assertTrue(str(paths["code_change_ledger"]).endswith("M3S04_experiment_execute_code_changes.yaml"))

    def test_reviewer_memory_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = ensure_reviewer_memory(tmp, "demo")
            data = yaml.safe_load(path.read_text(encoding="utf-8"))

            self.assertEqual(data["project"], "demo")
            self.assertIn("persistent_concerns", data)
            self.assertIn("review_rounds", data)

    def test_markdown_section_anchors_verify_and_detect_stale_content(self) -> None:
        text = "# Title\n\nBody.\n\n## Detail\n\nMore.\n"
        anchored = add_or_refresh_heading_anchors(text, "M1S01")

        checks = verify_section_anchors(anchored)
        self.assertEqual(len(checks), 2)
        self.assertTrue(all(check.ok for check in checks))

        stale = anchored.replace("More.", "Changed.")
        stale_checks = verify_section_anchors(stale)
        self.assertFalse(all(check.ok for check in stale_checks))


if __name__ == "__main__":
    unittest.main()
