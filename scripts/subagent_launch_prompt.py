#!/usr/bin/env python3
"""Print the exact compact prompt to use when launching an AutoPaper2 subagent."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_framework_root = Path(__file__).parent.parent.resolve()
if str(_framework_root) not in sys.path:
    sys.path.insert(0, str(_framework_root))

from spiral.dispatch import render_compact_launch_prompt


def _extract_markdown_launch_prompt(text: str) -> str:
    marker = "## Compact Launch Prompt"
    start = text.find(marker)
    if start < 0:
        return ""
    fenced = re.search(r"```text\n(.*?)\n```", text[start:], re.DOTALL)
    return fenced.group(1).strip() + "\n" if fenced else ""


def load_launch_prompt(packet_path: Path) -> str:
    if not packet_path.exists():
        raise FileNotFoundError(f"Dispatch packet not found: {packet_path}")
    text = packet_path.read_text(encoding="utf-8")
    if packet_path.suffix.lower() == ".json":
        packet = json.loads(text)
        return render_compact_launch_prompt(packet, packet_path)
    prompt = _extract_markdown_launch_prompt(text)
    if prompt:
        return prompt
    raise ValueError(f"Markdown packet has no Compact Launch Prompt block: {packet_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, help="Dispatch packet path (.json or .md)")
    args = parser.parse_args(argv)
    print(load_launch_prompt(Path(args.packet)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
