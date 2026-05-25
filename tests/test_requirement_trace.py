#!/usr/bin/env python3
"""Tests for user requirement traceability metadata."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.requirement_trace_check import load_trace, validate_trace


class TestRequirementTrace(unittest.TestCase):
    def test_user_requirement_trace_passes(self) -> None:
        trace_path = _project_root / "config" / "user_requirement_trace.yaml"
        data = load_trace(trace_path)

        ok, messages = validate_trace(data, _project_root)

        self.assertTrue(ok, "\n".join(messages))
        self.assertTrue(any("trace covers M1-M6" in message for message in messages))

    def test_requirement_trace_blocks_missing_evidence_path(self) -> None:
        trace_path = _project_root / "config" / "user_requirement_trace.yaml"
        data = load_trace(trace_path)
        data["requirements"][0]["evidence_paths"].append("missing/evidence.md")

        ok, messages = validate_trace(data, _project_root)

        self.assertFalse(ok)
        self.assertTrue(any("missing/evidence.md" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
