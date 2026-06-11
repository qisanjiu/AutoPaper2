#!/usr/bin/env python3
"""CLI wrapper for AutoPaper2 literature ingestion helpers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spiral.literature_ingestion import main


if __name__ == "__main__":
    raise SystemExit(main())
