from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.code_execution_ledger import main


class TestCodeExecutionLedger(unittest.TestCase):
    def test_run_command_records_outputs_and_return_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rc = main(
                [
                    "--project",
                    str(root),
                    "--task-id",
                    "M3S04_experiment_execute",
                    "run",
                    "--purpose",
                    "smoke",
                    "python -c \"print('ok')\"",
                ]
            )

            self.assertEqual(rc, 0)
            ledger = yaml.safe_load(
                (root / "state" / "agent_runs" / "M3S04_experiment_execute_commands.yaml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(ledger["commands"][0]["returncode"], 0)
            self.assertIn("ok", ledger["commands"][0]["stdout_preview"])

    def test_record_change_writes_patch_and_file_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            source = root / "demo.py"
            source.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "demo.py"], cwd=root, check=True, capture_output=True)
            source.write_text("value = 2\n", encoding="utf-8")

            rc = main(
                [
                    "--project",
                    str(root),
                    "--task-id",
                    "M3S02_experiment_execute",
                    "record-change",
                    "--purpose",
                    "implementation edit",
                    "demo.py",
                ]
            )

            self.assertEqual(rc, 0)
            ledger = yaml.safe_load(
                (root / "state" / "agent_runs" / "M3S02_experiment_execute_code_changes.yaml").read_text(
                    encoding="utf-8"
                )
            )
            change = ledger["changes"][0]
            self.assertEqual(change["files"][0]["path"], "demo.py")
            self.assertIn("sha256", change["files"][0])
            self.assertTrue((root / change["patch_path"]).exists())


if __name__ == "__main__":
    unittest.main()
