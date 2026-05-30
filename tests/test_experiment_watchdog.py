#!/usr/bin/env python3
"""Tests for M3 runtime watchdog alerts."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.experiment_watchdog import inspect_run


class TestExperimentWatchdog(unittest.TestCase):
    def test_watchdog_records_alert_without_terminating_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            run_root = root / "experiments" / "runs" / "run_nan"
            logs = run_root / "logs"
            logs.mkdir(parents=True)
            train_log = logs / "train.log"
            metrics = run_root / "metrics.csv"
            train_log.write_text("epoch=3 loss=nan gradient overflow\n", encoding="utf-8")
            metrics.write_text("epoch,loss,accuracy\n1,1.0,0.4\n2,nan,0.3\n", encoding="utf-8")

            event = inspect_run(
                project=root,
                run_id="run_nan",
                log_paths=[train_log],
                metric_paths=[metrics],
            )

            self.assertEqual(event["severity"], "critical")
            self.assertTrue(event["decision_required"])
            self.assertEqual(event["agent_action_policy"], "record_alert_only_agent_decides_continue_fix_or_stop")
            self.assertTrue((root / "experiments" / "logs" / "runtime_events.jsonl").exists())
            self.assertTrue((run_root / "watchdog_checks.jsonl").exists())
            self.assertTrue((run_root / "watchdog_alerts.jsonl").exists())

            alert = json.loads((run_root / "watchdog_alerts.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(alert["run_id"], "run_nan")
            self.assertTrue(any(signal["kind"] in {"nan_or_inf", "non_finite_metric"} for signal in alert["signals"]))


if __name__ == "__main__":
    unittest.main()
