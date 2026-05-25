#!/usr/bin/env python3
"""Test health check — scan test files for unittest compliance.

Usage:
    python scripts/test_health_check.py

Exit code 0 if all test classes inherit unittest.TestCase, non-zero otherwise.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _find_test_classes(filepath: Path) -> list[tuple[str, list[str]]]:
    """Return list of (class_name, base_names) for classes starting with 'Test'."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"), filename=str(filepath))
    except SyntaxError as exc:
        print(f"  [ERROR] Syntax error in {filepath}: {exc}")
        return []

    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(f"{base.attr}")
            result.append((node.name, bases))
    return result


def _find_top_level_test_functions(filepath: Path) -> list[str]:
    """Return module-level pytest-style test functions.

    The project health check is specifically guarding ``python -m unittest
    discover`` coverage.  Top-level pytest functions are invisible to that
    runner when pytest is not installed, so they are treated as health issues.
    """
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"), filename=str(filepath))
    except SyntaxError:
        return []
    return [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]


def main() -> int:
    tests_dir = Path(__file__).parent.parent / "tests"
    if not tests_dir.exists():
        print(f"[ERROR] Tests directory not found: {tests_dir}")
        return 1

    test_files = sorted(tests_dir.glob("test_*.py"))
    if not test_files:
        print(f"[WARN] No test_*.py files found in {tests_dir}")
        return 0

    issues = []
    function_issues: list[tuple[str, str]] = []
    total_classes = 0

    print(f"\n{'='*60}")
    print("  TEST HEALTH CHECK")
    print(f"{'='*60}")
    print(f"  Scanning {len(test_files)} test file(s)...\n")

    for tf in test_files:
        top_level_functions = _find_top_level_test_functions(tf)
        for func_name in top_level_functions:
            function_issues.append((tf.name, func_name))
            print(
                f"  [FAIL] {tf.name}::{func_name} is a top-level pytest-style test; "
                "convert it to unittest.TestCase so unittest discover runs it."
            )

        classes = _find_test_classes(tf)
        if not classes:
            continue
        print(f"  {tf.name}: {len(classes)} test class(es)")
        for name, bases in classes:
            total_classes += 1
            if "TestCase" not in bases:
                issues.append((tf.name, name, bases))
                print(f"    [FAIL] {name} inherits {bases} — should inherit unittest.TestCase")
            else:
                print(f"    [PASS] {name} inherits unittest.TestCase")

    print(f"\n{'='*60}")
    print(f"  Total test classes: {total_classes}")
    total_issues = len(issues) + len(function_issues)
    print(f"  Issues found: {total_issues}")
    print(f"{'='*60}\n")

    if total_issues:
        print("[FAIL] Some tests will NOT be discovered by 'python -m unittest discover'.\n")
        for fname, cname, bases in issues:
            print(f"  - {fname}::{cname}({', '.join(bases)})")
        for fname, func_name in function_issues:
            print(f"  - {fname}::{func_name} (top-level function)")
        print()
        return 1

    print("[PASS] All test classes correctly inherit unittest.TestCase.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
