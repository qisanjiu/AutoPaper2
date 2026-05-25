"""M6 revision action-plan parser and deterministic route builder.

The M6S04 action plan is a repeatable control artifact.  This module extracts
review items and maps each target stage to the responsible execution subagent
so the conductor does not have to spend context manually interpreting a table.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .project import AGENT_FOR_STAGE, MODULE_STAGES


ACTION_PLAN_RELATIVE_PATH = Path("knowledge") / "M6" / "M6S04_action_plan.md"

_ITEM_HEADING_RE = re.compile(
    r"^\s*#{3,}\s*(?:Item\s+)?(?P<id>PR-[A-Za-z0-9_.-]+)\b.*$",
    re.IGNORECASE,
)
_FIELD_RE = re.compile(
    r"^\s*[-*]\s*(?:\*\*)?`?(?P<key>[A-Za-z_][A-Za-z0-9_]*)`?(?:\*\*)?\s*[:：]\s*(?P<value>.*?)\s*$"
)

_ALL_STAGES = [stage for stages in MODULE_STAGES.values() for stage in stages]
_STAGE_RE = re.compile(r"\bM[1-6]S\d{2}\b")


def _stage_index(stage: str) -> int:
    try:
        return _ALL_STAGES.index(stage)
    except ValueError:
        return len(_ALL_STAGES) + 1


def _normalise_key(key: str) -> str:
    return key.strip().lower()


def _split_items(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;|\n]+", value or "") if item.strip()]


def _extract_rerun_stages(scope: str, target_stage: str) -> list[str]:
    stages: list[str] = []
    if target_stage in _ALL_STAGES:
        stages.append(target_stage)
    for stage in _STAGE_RE.findall(scope or ""):
        if stage in _ALL_STAGES and stage not in stages:
            stages.append(stage)
    return stages


def _combined_rebuild_mode(items: list[dict[str, Any]]) -> str:
    if any(str(item.get("rebuild_mode", "")).strip() == "full_regenerate" for item in items):
        return "full_regenerate"
    return "incremental_replay"


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            out.append(value)
            seen.add(value)
    return out


def _finalise_item(raw: dict[str, Any], warnings: list[str]) -> dict[str, Any] | None:
    if not raw:
        return None

    item_id = str(raw.get("id", "")).strip()
    target_stage = str(raw.get("target_stage", "")).strip()
    if not item_id and target_stage:
        item_id = f"UNNAMED-{len(warnings) + 1}"
        warnings.append(f"Action item targeting {target_stage} has no PR-* id; assigned {item_id}.")
    if not item_id:
        return None
    if target_stage and target_stage not in _ALL_STAGES:
        warnings.append(f"{item_id}: unknown target_stage={target_stage}.")

    item = {
        "id": item_id,
        "class": str(raw.get("class", "")).strip(),
        "severity": str(raw.get("severity", "")).strip(),
        "target_stage": target_stage,
        "blocking_reason": str(raw.get("blocking_reason", raw.get("reason", ""))).strip(),
        "required_fix": str(raw.get("required_fix", "")).strip(),
        "success_criteria": str(raw.get("success_criteria", "")).strip(),
        "evidence_paths": _split_items(str(raw.get("evidence_paths", ""))),
        "rebuild_mode": str(raw.get("rebuild_mode", "")).strip() or "full_regenerate",
        "rerun_scope": str(raw.get("rerun_scope", "")).strip(),
        "handoff_updates": _split_items(str(raw.get("handoff_updates", ""))),
        "priority": str(raw.get("priority", "")).strip(),
    }
    for field in ("target_stage", "required_fix", "success_criteria", "rerun_scope"):
        if not item[field]:
            warnings.append(f"{item_id}: missing {field}.")
    if item["rebuild_mode"] not in {"incremental_replay", "full_regenerate"}:
        warnings.append(f"{item_id}: invalid rebuild_mode={item['rebuild_mode']}.")
    return item


def parse_action_plan_text(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse Markdown action-plan items from M6S04.

    The canonical format uses headings such as ``### PR-A1`` followed by field
    lines like ``- **target_stage**: M4S02``.  Text outside item blocks is
    ignored; malformed blocks are retained with warnings where possible.
    """
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    current: dict[str, Any] = {}

    for line in text.splitlines():
        heading = _ITEM_HEADING_RE.match(line)
        if heading:
            item = _finalise_item(current, warnings)
            if item:
                items.append(item)
            current = {"id": heading.group("id")}
            continue

        field = _FIELD_RE.match(line)
        if field and current:
            current[_normalise_key(field.group("key"))] = field.group("value").strip()

    item = _finalise_item(current, warnings)
    if item:
        items.append(item)

    if not items:
        warnings.append("No canonical action items found. Expected headings like '### PR-A1'.")
    return items, warnings


def build_stage_advice_map(items: list[dict[str, Any]], action_plan_path: Path) -> dict[str, dict[str, Any]]:
    """Build per-stage repair advice from parsed M6 action-plan items."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        target_stage = str(item.get("target_stage", "")).strip()
        affected_stages = _extract_rerun_stages(str(item.get("rerun_scope", "")), target_stage)
        for stage in affected_stages:
            relation = "direct" if stage == target_stage else "downstream"
            routed_item = dict(item)
            routed_item["relation_to_stage"] = relation
            buckets.setdefault(stage, []).append(routed_item)

    advice_map: dict[str, dict[str, Any]] = {}
    review_matrix = action_plan_path.parent / "M6S03_review_matrix.md"
    review_parsing = action_plan_path.parent / "M6S03_review_parsing.md"
    base_evidence = [str(action_plan_path), str(review_matrix), str(review_parsing)]

    for stage in sorted(buckets, key=_stage_index):
        stage_items = buckets[stage]
        direct_items = [item for item in stage_items if item.get("relation_to_stage") == "direct"]
        downstream_items = [item for item in stage_items if item.get("relation_to_stage") != "direct"]
        direct_ids = [item["id"] for item in direct_items]
        downstream_ids = [item["id"] for item in downstream_items]
        item_ids = [item["id"] for item in stage_items]

        required_lines: list[str] = []
        success_lines: list[str] = []
        handoff_updates: list[str] = []
        evidence_paths = list(base_evidence)
        rerun_scopes: list[str] = []
        for item in stage_items:
            relation = str(item.get("relation_to_stage", "direct"))
            prefix = "Direct fix" if relation == "direct" else "Downstream revalidation"
            required = item.get("required_fix", "") or "Re-run and verify affected output"
            criteria = item.get("success_criteria", "") or "Reviewer item is resolved with evidence"
            required_lines.append(f"- {prefix} for {item['id']} ({item.get('severity', '')}/{item.get('class', '')}): {required}")
            success_lines.append(f"- {item['id']}: {criteria}")
            evidence_paths.extend(item.get("evidence_paths", []))
            rerun_scopes.append(str(item.get("rerun_scope", "")).strip())
            handoff_updates.extend(item.get("handoff_updates", []))

        if direct_ids and downstream_ids:
            blocking_reason = (
                f"M6S04 action plan assigns direct item(s) {', '.join(direct_ids)} to {stage}; "
                f"also revalidate downstream item(s) {', '.join(downstream_ids)}."
            )
        elif direct_ids:
            blocking_reason = f"M6S04 action plan assigns review item(s) {', '.join(direct_ids)} to {stage}."
        else:
            blocking_reason = (
                f"{stage} is in the rerun scope for M6 review item(s) {', '.join(downstream_ids)} "
                "and must be revalidated after upstream fixes."
            )

        advice_map[stage] = {
            "source_critic": "m6_action_router",
            "source_stage": "M6S04",
            "source_action_plan": str(action_plan_path),
            "target_stage": stage,
            "blocking_reason": blocking_reason,
            "required_fix": "\n".join(required_lines),
            "success_criteria": "\n".join(success_lines),
            "evidence_paths": _unique(evidence_paths),
            "rebuild_mode": _combined_rebuild_mode(stage_items),
            "rerun_scope": "; ".join(_unique(rerun_scopes)) or f"Re-execute {stage}",
            "handoff_updates": _unique(handoff_updates)
            or [f"Update downstream handoffs affected by M6 item(s): {', '.join(item_ids)}"],
            "m6_action_item_ids": item_ids,
            "direct_item_ids": direct_ids,
            "downstream_item_ids": downstream_ids,
            "action_items": stage_items,
        }
    return advice_map


def load_action_plan(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Load and parse an action plan, returning items plus non-fatal warnings."""
    if not path.exists():
        return [], [f"Action plan not found: {path}"]
    return parse_action_plan_text(path.read_text(encoding="utf-8"))


def build_revision_routes(project_root: str | Path) -> dict[str, Any]:
    """Build deterministic M6S05 routes from ``M6S04_action_plan.md``."""
    root = Path(project_root)
    action_plan_path = root / ACTION_PLAN_RELATIVE_PATH
    items, warnings = load_action_plan(action_plan_path)
    stage_advice_map = build_stage_advice_map(items, action_plan_path)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        target_stage = item.get("target_stage", "")
        if not target_stage:
            continue
        grouped.setdefault(target_stage, []).append(item)

    routes: list[dict[str, Any]] = []
    for target_stage in sorted(grouped, key=_stage_index):
        responsible_agent = AGENT_FOR_STAGE.get(target_stage, "conductor")
        routes.append(
            {
                "target_stage": target_stage,
                "responsible_agent": responsible_agent,
                "item_ids": [item["id"] for item in grouped[target_stage]],
                "items": grouped[target_stage],
                "dispatch_command": f"python scripts/state_manager.py dispatch stage {target_stage} --write",
            }
        )

    earliest_target_stage = routes[0]["target_stage"] if routes else ""
    earliest_advice = stage_advice_map.get(earliest_target_stage, {})
    return {
        "action_plan_path": str(action_plan_path),
        "items": items,
        "routes": routes,
        "earliest_target_stage": earliest_target_stage,
        "stage_backtrack_advice": stage_advice_map,
        "recommended_state_update": {
            "from_stage": "M6S05",
            "to_stage": earliest_target_stage,
            "reason": "M6S04 action plan requires routed revision execution",
            "required_fix": earliest_advice.get(
                "required_fix",
                "Execute and verify all items in knowledge/M6/M6S04_action_plan.md",
            ),
            "success_criteria": earliest_advice.get(
                "success_criteria",
                "Every action-plan item is resolved or explicitly recorded as partial/blocked in M6S05_revision_execution.md",
            ),
            "evidence_paths": earliest_advice.get("evidence_paths", [str(action_plan_path)]),
            "rebuild_mode": earliest_advice.get("rebuild_mode", "incremental_replay"),
            "rerun_scope": "Re-run routed target stages and affected downstream stale stages before final M6S05 reporting",
            "handoff_updates": earliest_advice.get("handoff_updates", []),
            "stage_backtrack_advice": stage_advice_map,
            "m6_action_item_ids": [item["id"] for item in items],
        },
        "warnings": warnings,
    }
