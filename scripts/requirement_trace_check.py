#!/usr/bin/env python3
"""Validate AutoPaper2 user-requirement traceability metadata.

The trace file is not evidence that a project has completed M1-M6.  It is a
framework-level guard: every user requirement must stay mapped to concrete
agent docs, templates, gates, scripts, and tests.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


TRACE_PATH = Path("config") / "user_requirement_trace.yaml"
REQUIRED_MODULES = {
    "M1",
    "M2",
    "M3",
    "M4",
    "M5",
    "M6",
    "CONDUCTOR",
    "EXTERNAL_COMPARISON",
}
ALLOWED_STATUSES = {"framework_enforced", "framework_partial", "external_required"}
REQUIRED_FIELDS = {
    "id",
    "module",
    "status",
    "user_requirement",
    "enforced_by",
    "evidence_paths",
    "tests",
    "residual_gaps",
}


def load_trace(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError("trace root must be a mapping")
    return data


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def validate_trace(data: dict[str, Any], repo_root: Path) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True

    requirements = data.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        return False, ["[FAIL] trace has no requirements list"]

    seen_ids: set[str] = set()
    modules: set[str] = set()
    for idx, requirement in enumerate(requirements, start=1):
        label = f"requirement[{idx}]"
        if not isinstance(requirement, dict):
            messages.append(f"[FAIL] {label}: entry must be a mapping")
            ok = False
            continue

        missing = sorted(REQUIRED_FIELDS - set(requirement))
        req_id = str(requirement.get("id", label))
        if missing:
            messages.append(f"[FAIL] {req_id}: missing fields: {', '.join(missing)}")
            ok = False

        if req_id in seen_ids:
            messages.append(f"[FAIL] {req_id}: duplicate requirement id")
            ok = False
        seen_ids.add(req_id)

        module = str(requirement.get("module", "")).strip()
        if module:
            modules.add(module)
        if module not in REQUIRED_MODULES:
            messages.append(f"[FAIL] {req_id}: unknown module {module or '<empty>'}")
            ok = False

        status = str(requirement.get("status", "")).strip()
        if status not in ALLOWED_STATUSES:
            messages.append(f"[FAIL] {req_id}: invalid status {status or '<empty>'}")
            ok = False

        enforced_by = requirement.get("enforced_by")
        if not isinstance(enforced_by, dict) or not any(_as_list(v) for v in enforced_by.values()):
            messages.append(f"[FAIL] {req_id}: enforced_by must contain at least one nonempty list")
            ok = False

        evidence_paths = _as_list(requirement.get("evidence_paths"))
        if not evidence_paths:
            messages.append(f"[FAIL] {req_id}: evidence_paths must be nonempty")
            ok = False
        for rel_path in evidence_paths:
            path = repo_root / str(rel_path)
            if not path.exists():
                messages.append(f"[FAIL] {req_id}: evidence path missing: {rel_path}")
                ok = False
            else:
                messages.append(f"[PASS] {req_id}: evidence path exists: {rel_path}")

        tests = _as_list(requirement.get("tests"))
        if not tests:
            messages.append(f"[FAIL] {req_id}: tests must be nonempty")
            ok = False
        for rel_path in tests:
            path = repo_root / str(rel_path)
            if not path.exists():
                messages.append(f"[FAIL] {req_id}: test path missing: {rel_path}")
                ok = False
            else:
                messages.append(f"[PASS] {req_id}: test path exists: {rel_path}")

        residual_gaps = _as_list(requirement.get("residual_gaps"))
        if not residual_gaps:
            messages.append(f"[FAIL] {req_id}: residual_gaps must state remaining runtime/external limits")
            ok = False

        if module == "EXTERNAL_COMPARISON":
            sources = _as_list(requirement.get("external_sources"))
            if len(sources) < 5:
                messages.append(f"[FAIL] {req_id}: external_sources must list at least 5 sources")
                ok = False
            for source in sources:
                if not str(source).startswith(("http://", "https://")):
                    messages.append(f"[FAIL] {req_id}: invalid external source URL: {source}")
                    ok = False
            if sources:
                messages.append(f"[PASS] {req_id}: external source URLs listed: {len(sources)}")

    missing_modules = sorted(REQUIRED_MODULES - modules)
    if missing_modules:
        messages.append("[FAIL] trace missing modules: " + ", ".join(missing_modules))
        ok = False
    else:
        messages.append("[PASS] trace covers M1-M6, conductor, and external comparison")

    return ok, messages


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    trace_path = repo_root / TRACE_PATH
    if not trace_path.exists():
        print(f"[FAIL] requirement trace missing: {trace_path}")
        return 1

    try:
        data = load_trace(trace_path)
    except Exception as exc:
        print(f"[FAIL] could not read requirement trace: {exc}")
        return 1

    ok, messages = validate_trace(data, repo_root)
    for message in messages:
        print(message)
    if not ok:
        print("[FAIL] requirement trace validation failed")
        return 1
    print("[PASS] requirement trace validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
