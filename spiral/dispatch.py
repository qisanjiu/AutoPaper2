"""Structured dispatch packets for AutoPaper2 subagent delegation.

This module converts Conductor plans into small, durable task packets.  A main
agent should generate a packet, pass the packet path to the matching subagent,
and avoid rewriting stage or review outputs itself.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.file_guard import get_canonical_output_path
from utils.gate_rubric import render_gate_rubric_block

from .conductor import Conductor, GATE_CRITICS
from .project import GATE_STAGES
from .revision_router import build_revision_routes


M1S02_ROUND_REVIEW_OUTPUTS: dict[int, str] = {
    1: "knowledge/reviews/M1S02_round1_review.md",
    2: "knowledge/reviews/M1S02_round2_review.md",
    3: "knowledge/reviews/M1S02_round3_review.md",
}


MAIN_AGENT_BOUNDARIES = [
    "The main agent/conductor must not edit knowledge/ or drafts/ stage outputs.",
    "The main agent/conductor must not write review verdicts on behalf of reviewers.",
    "The main agent/conductor must pass paths only; subagents must read source files directly.",
    "The main agent/conductor must update state only through state_manager.py or Conductor APIs.",
]


EXECUTOR_BOUNDARIES = [
    "Execute only the assigned stage and write the requested stage output.",
    "Do not write stage-review or gate-review verdicts.",
    "Do not advance pipeline state; the conductor will run state_manager.py advance.",
    "Use old downstream files only as historical audit evidence when backtrack_advice is present.",
]


REVIEWER_BOUNDARIES = [
    "Review only; do not modify the stage output under review.",
    "Read the original file paths directly; do not rely on executor summaries.",
    "Write exactly one review file at the requested output path.",
    "For non-PASS verdicts, include target_stage, blocking_reason, required_fix, success_criteria, evidence_paths, rebuild_mode, rerun_scope, and handoff_updates.",
]


DELEGATED_TASK_TYPES = {
    "stage_execution",
    "stage_review",
    "gate_review",
    "revision_routing",
}


REVISION_ROUTING_BOUNDARIES = [
    "Use the script-generated revision routes; do not reinterpret the action plan manually.",
    "Do not edit routed target-stage outputs directly from the main agent/conductor.",
    "Delegate each routed target stage to its responsible subagent before asking the revision agent to write M6S05_revision_execution.md.",
    "If routed work is incomplete, record it as blocked/partial; do not invent completion evidence.",
]


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._-") or "task"


def _as_path_list(values: list[str | Path]) -> list[str]:
    return [str(Path(v)) for v in values if str(v)]


def _existing_or_expected(paths: list[Path]) -> list[str]:
    """Return de-duplicated path strings, keeping expected missing paths too."""
    seen: set[str] = set()
    out: list[str] = []
    for path in paths:
        value = str(path)
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out


def _gate_id_for_stage(stage: str) -> str | None:
    for gate_id, gate_stage in GATE_STAGES.items():
        if gate_stage == stage:
            return gate_id
    return None


def _gate_stage_for_id(gate_id: str) -> str:
    if gate_id not in GATE_STAGES:
        raise ValueError(f"Unknown gate id: {gate_id}")
    return GATE_STAGES[gate_id]


def _review_output_for_gate(root: Path, gate_id: str, critic: str) -> Path:
    return root / "knowledge" / "reviews" / f"{gate_id}_{critic}_review.md"


def _packet(
    *,
    task_type: str,
    task_id: str,
    project_root: Path,
    role: str,
    agent_md: Path,
    output_path: Path | None,
    input_docs: list[str | Path],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "task_id": task_id,
        "task_type": task_type,
        "delegation_required": task_type in DELEGATED_TASK_TYPES,
        "project_root": str(project_root),
        "role": role,
        "agent_md": str(agent_md),
        "input_docs": _as_path_list(input_docs),
        "output_path": str(output_path) if output_path else "",
        "main_agent_boundaries": MAIN_AGENT_BOUNDARIES,
    }
    if extra:
        data.update(extra)
    data["subagent_prompt"] = render_subagent_prompt(data)
    return data


def build_stage_execution_packet(project_root: str | Path, stage: str | None = None) -> dict[str, Any]:
    root = Path(project_root)
    conductor = Conductor(root)
    stage_id = stage or conductor.current_stage()
    if stage_id == "M6S05":
        return build_m6s05_revision_routing_packet(root)
    plan = conductor.run_stage(stage_id)
    role = str(plan.get("agent", conductor.get_agent_for_stage(stage_id)))
    output_path = Path(plan["output_doc"])
    task_id = _slug(f"{stage_id}_{role}_execute")
    extra = {
        "stage": stage_id,
        "phase": plan.get("phase", "stage"),
        "md_protocol": plan.get("md_protocol", ""),
        "stage_checkers": plan.get("stage_checkers", []),
        "stage_review_outputs": plan.get("stage_review_outputs", {}),
        "backtrack_advice": plan.get("backtrack_advice", {}),
        "subagent_boundaries": EXECUTOR_BOUNDARIES,
        "after_completion": [
            f"Ensure output exists: {output_path}",
            "Return changed paths and a concise completion summary to the conductor.",
            "Do not call state_manager.py advance from inside the executor subagent.",
        ],
    }
    return _packet(
        task_type="stage_execution",
        task_id=task_id,
        project_root=root,
        role=role,
        agent_md=Path(plan["agent_md"]),
        output_path=output_path,
        input_docs=[Path(p) for p in plan.get("input_docs", [])],
        extra=extra,
    )


def build_m6s05_revision_routing_packet(project_root: str | Path) -> dict[str, Any]:
    """Build the special M6S05 routing packet.

    M6S05 is not a normal single-agent writing task: the conductor must route
    the M6S04 action-plan items to Method / Experiment / Analysis / Writing
    subagents, then delegate the final execution record to the Revision Agent.
    """
    root = Path(project_root)
    conductor = Conductor(root)
    stage_id = "M6S05"
    plan = conductor.run_stage(stage_id)
    output_path = Path(plan["output_doc"])
    routing = build_revision_routes(root)
    task_id = _slug("M6S05_revision_routing")
    inputs = [Path(p) for p in plan.get("input_docs", [])]

    return _packet(
        task_type="revision_routing",
        task_id=task_id,
        project_root=root,
        role="revision",
        agent_md=Path(plan["agent_md"]),
        output_path=output_path,
        input_docs=inputs,
        extra={
            "stage": stage_id,
            "phase": "revision_routing",
            "md_protocol": plan.get("md_protocol", ""),
            "stage_checkers": plan.get("stage_checkers", []),
            "stage_review_outputs": plan.get("stage_review_outputs", {}),
            "revision_routing": routing,
            "subagent_boundaries": REVISION_ROUTING_BOUNDARIES,
            "after_completion": [
                "Run or delegate the routed target-stage work before final M6S05 reporting.",
                f"Ensure execution record exists only after evidence is available: {output_path}",
                "Return routed item statuses, evidence paths, and the execution-record path to the conductor.",
                "Do not call state_manager.py advance from inside the revision subagent.",
            ],
        },
    )


def build_stage_review_packets(project_root: str | Path, stage: str) -> list[dict[str, Any]]:
    root = Path(project_root)
    conductor = Conductor(root)

    if stage == "M1S02":
        return _build_m1s02_round_review_packets(root, conductor)

    outputs = conductor.get_stage_review_outputs(stage)
    packets: list[dict[str, Any]] = []
    subject_output = get_canonical_output_path(root, stage)
    base_inputs = [subject_output, *conductor.get_stage_input_docs(stage)]
    extra_expected = [
        root / "knowledge" / "M1" / "M1_source_log.yaml",
        root / "knowledge" / "M2" / "M2_source_log.yaml",
        root / "state" / "research_brief.yaml",
    ]
    if stage == "M3S01":
        extra_expected.extend(
            [
                root / "config" / "execution_env.yaml",
                root / "experiments" / "logs" / "m3s01_longrun_ledger.md",
                root / "experiments" / "requirements.lock",
                root / "experiments" / "requirements.txt",
            ]
        )

    for checker in conductor.get_stage_checkers(stage):
        if checker == "source_log_validator":
            continue
        output = outputs.get(checker)
        if output is None:
            output = root / "knowledge" / "reviews" / f"{stage}_{checker}_review.md"
        task_id = _slug(f"{stage}_{checker}_review")
        input_docs = _existing_or_expected([*base_inputs, *extra_expected])
        if checker == "m6_internal_peer_review":
            input_docs = _m6_internal_review_inputs(root, input_docs)
        packets.append(
            _packet(
                task_type="stage_review",
                task_id=task_id,
                project_root=root,
                role=checker,
                agent_md=conductor.get_checker_md_path(checker),
                output_path=output,
                input_docs=input_docs,
                extra={
                    "stage": stage,
                    "subject_output": str(subject_output),
                    "subagent_boundaries": REVIEWER_BOUNDARIES,
                    "after_completion": [
                        f"Ensure review exists: {output}",
                        "Return verdict and the review path to the conductor.",
                    ],
                },
            )
        )
    return packets


def _m6_internal_review_inputs(root: Path, base_inputs: list[str]) -> list[str]:
    """Return the evidence bundle for mandatory M6S01 internal review."""
    expected = [
        root / "artifacts" / "paper.pdf",
        root / "artifacts" / "paper.tex",
        root / "artifacts" / "refs.bib",
        root / "knowledge" / "M1" / "M1S02_literature_deepdive.md",
        root / "knowledge" / "M1" / "M1_source_log.yaml",
        root / "knowledge" / "M2" / "M2S03_method_architecture.md",
        root / "knowledge" / "M2" / "M2S05_experiment_setup.md",
        root / "knowledge" / "M2" / "M2S06_full_experiment_plan.md",
        root / "knowledge" / "M3" / "M3S03_main_experiment.md",
        root / "knowledge" / "M3" / "M3S04_result_validation.md",
        root / "knowledge" / "M4" / "M4S04_analysis_results.md",
        root / "knowledge" / "M5" / "M5S09_full_polish.md",
        root / "knowledge" / "M5" / "M5S08_final_compilation.md",
        root / "knowledge" / "handoff_M5_completion.md",
    ]
    return _existing_or_expected([Path(p) for p in base_inputs] + expected)


def _build_m1s02_round_review_packets(root: Path, conductor: Conductor) -> list[dict[str, Any]]:
    agent_md = conductor.get_checker_md_path("survey_review")
    subject_output = root / "knowledge" / "M1" / "M1S02_literature_deepdive.md"
    source_log = root / "knowledge" / "M1" / "M1_source_log.yaml"
    survey_memory = root / "state" / "survey_memory.yaml"
    packets: list[dict[str, Any]] = []

    for round_num, rel_output in M1S02_ROUND_REVIEW_OUTPUTS.items():
        output = root / rel_output
        task_id = _slug(f"M1S02_round{round_num}_survey_review")
        packets.append(
            _packet(
                task_type="stage_review",
                task_id=task_id,
                project_root=root,
                role="survey_review",
                agent_md=agent_md,
                output_path=output,
                input_docs=[subject_output, source_log, survey_memory],
                extra={
                    "stage": "M1S02",
                    "round": round_num,
                    "subject_output": str(subject_output),
                    "subagent_boundaries": REVIEWER_BOUNDARIES,
                    "after_completion": [
                        f"Ensure round review exists: {output}",
                        "Return verdict and the review path to the conductor.",
                    ],
                },
            )
        )
    return packets


def build_gate_review_packets(
    project_root: str | Path,
    gate_or_stage: str | None = None,
) -> list[dict[str, Any]]:
    root = Path(project_root)
    conductor = Conductor(root)
    target = gate_or_stage or conductor.current_stage()
    gate_id = target if target.startswith("G") else _gate_id_for_stage(target)
    if gate_id is None:
        raise ValueError(f"Cannot infer gate id from {target}")

    gate_stage = _gate_stage_for_id(gate_id)
    input_docs = conductor.get_stage_input_docs(gate_stage)
    aggregate_output = root / "knowledge" / "reviews" / f"{gate_id}_aggregate.md"
    packets: list[dict[str, Any]] = []
    for critic in GATE_CRITICS.get(gate_id, []):
        output = _review_output_for_gate(root, gate_id, critic)
        task_id = _slug(f"{gate_id}_{critic}_gate_review")
        rubric_block = render_gate_rubric_block(gate_id)
        packets.append(
            _packet(
                task_type="gate_review",
                task_id=task_id,
                project_root=root,
                role=critic,
                agent_md=conductor.get_checker_md_path(critic),
                output_path=output,
                input_docs=input_docs,
                extra={
                    "gate_id": gate_id,
                    "gate_stage": gate_stage,
                    "aggregate_output": str(aggregate_output),
                    "gate_rubric": rubric_block,
                    "subagent_boundaries": REVIEWER_BOUNDARIES,
                    "after_completion": [
                        f"Ensure gate critic review exists: {output}",
                        "Return verdict and the review path to the conductor.",
                        f"The conductor aggregates all critic reviews into {aggregate_output}.",
                        "The aggregate review must include the configured Rubric Results table before advancement.",
                    ],
                },
            )
        )
    return packets


def build_next_action_packets(project_root: str | Path) -> list[dict[str, Any]]:
    root = Path(project_root)
    conductor = Conductor(root)
    action = conductor.get_next_action()
    action_name = action.get("action")

    if action_name in {"EXECUTE_STAGE", "RE_EXECUTE"}:
        return [build_stage_execution_packet(root, str(action["stage"]))]
    if action_name == "GATE":
        return build_gate_review_packets(root, str(action["gate_id"]))

    return [
        {
            "task_id": _slug(f"control_{action_name or 'unknown'}"),
            "task_type": "control",
            "delegation_required": False,
            "project_root": str(root),
            "action": action_name,
            "reason": action.get("reason", ""),
            "suggested_cmd": action.get("suggested_cmd", ""),
            "main_agent_boundaries": MAIN_AGENT_BOUNDARIES,
        }
    ]


def build_packets(project_root: str | Path, scope: str, target: str | None = None) -> list[dict[str, Any]]:
    normalized = scope.lower().strip()
    if normalized == "next":
        return build_next_action_packets(project_root)
    if normalized == "stage":
        return [build_stage_execution_packet(project_root, target)]
    if normalized in {"review", "reviews", "stage-review", "stage-reviews"}:
        if not target:
            raise ValueError("stage review dispatch requires a stage target")
        return build_stage_review_packets(project_root, target)
    if normalized == "gate":
        return build_gate_review_packets(project_root, target)
    raise ValueError(f"Unknown dispatch scope: {scope}")


def render_subagent_prompt(packet: dict[str, Any]) -> str:
    lines: list[str] = []
    task_type = packet.get("task_type", "")
    role = packet.get("role", "")
    lines.append(f"You are the AutoPaper2 {role} subagent for task {packet.get('task_id')}.")
    lines.append("")
    lines.append(f"Task type: {task_type}")
    if packet.get("stage"):
        lines.append(f"Stage: {packet['stage']}")
    if packet.get("round"):
        lines.append(f"Round: {packet['round']}")
    if packet.get("gate_id"):
        lines.append(f"Gate: {packet['gate_id']} ({packet.get('gate_stage', '')})")
    lines.append(f"Project root: {packet.get('project_root')}")
    lines.append(f"Role instructions: {packet.get('agent_md')}")
    if packet.get("md_protocol"):
        lines.append(f"Markdown protocol: {packet.get('md_protocol')}")
    lines.append("")
    lines.append("Input paths (read directly; do not rely on summaries):")
    for path in packet.get("input_docs", []):
        lines.append(f"- {path}")
    if packet.get("subject_output"):
        lines.append(f"Subject output under review: {packet['subject_output']}")
    if packet.get("output_path"):
        lines.append("")
        lines.append(f"Required output path: {packet['output_path']}")
    if packet.get("aggregate_output"):
        lines.append(f"Gate aggregate path for conductor: {packet['aggregate_output']}")
    if packet.get("gate_rubric"):
        lines.append("")
        lines.append(packet["gate_rubric"])

    advice = packet.get("backtrack_advice") or {}
    if advice:
        lines.append("")
        lines.append("Backtrack advice:")
        for key in (
            "target_stage",
            "blocking_reason",
            "required_fix",
            "success_criteria",
            "evidence_paths",
            "rebuild_mode",
            "rerun_scope",
            "handoff_updates",
        ):
            lines.append(f"- {key}: {advice.get(key, '')}")

    routing = packet.get("revision_routing") or {}
    if routing:
        lines.append("")
        lines.append("Script-generated M6S05 revision routing:")
        lines.append(f"- action_plan_path: {routing.get('action_plan_path', '')}")
        lines.append(f"- earliest_target_stage: {routing.get('earliest_target_stage', '')}")
        state_update = routing.get("recommended_state_update", {})
        if state_update:
            lines.append("- recommended_state_update:")
            for key in (
                "from_stage",
                "to_stage",
                "reason",
                "required_fix",
                "success_criteria",
                "rebuild_mode",
                "rerun_scope",
            ):
                lines.append(f"  - {key}: {state_update.get(key, '')}")
        routes = routing.get("routes", [])
        if routes:
            lines.append("- routes:")
            for route in routes:
                lines.append(
                    f"  - target_stage={route.get('target_stage', '')}; "
                    f"responsible_agent={route.get('responsible_agent', '')}; "
                    f"items={', '.join(route.get('item_ids', []))}; "
                    f"dispatch={route.get('dispatch_command', '')}"
                )
        stage_advice = routing.get("stage_backtrack_advice", {})
        if stage_advice:
            lines.append("- stage_backtrack_advice:")
            for stage, advice in stage_advice.items():
                item_ids = advice.get("m6_action_item_ids", [])
                rebuild_mode = advice.get("rebuild_mode", "")
                lines.append(
                    f"  - {stage}: items={', '.join(item_ids)}; "
                    f"rebuild_mode={rebuild_mode}; "
                    f"rerun_scope={advice.get('rerun_scope', '')}"
                )
        warnings = routing.get("warnings", [])
        if warnings:
            lines.append("- warnings:")
            for warning in warnings:
                lines.append(f"  - {warning}")

    lines.append("")
    lines.append("Hard boundaries:")
    for rule in packet.get("subagent_boundaries", []):
        lines.append(f"- {rule}")
    for rule in packet.get("main_agent_boundaries", []):
        lines.append(f"- {rule}")

    after = packet.get("after_completion", [])
    if after:
        lines.append("")
        lines.append("After completion:")
        for item in after:
            lines.append(f"- {item}")

    return "\n".join(lines).strip() + "\n"


def packet_to_markdown(packet: dict[str, Any]) -> str:
    lines = [
        f"# AutoPaper2 Dispatch Packet: {packet.get('task_id')}",
        "",
        f"- task_type: {packet.get('task_type', '')}",
        f"- delegation_required: {packet.get('delegation_required', False)}",
        f"- project_root: `{packet.get('project_root', '')}`",
    ]
    if packet.get("role"):
        lines.append(f"- role: `{packet['role']}`")
    if packet.get("stage"):
        lines.append(f"- stage: `{packet['stage']}`")
    if packet.get("gate_id"):
        lines.append(f"- gate_id: `{packet['gate_id']}`")
    if packet.get("output_path"):
        lines.append(f"- output_path: `{packet['output_path']}`")
    lines.extend(["", "## Subagent Prompt", "", "```text", packet.get("subagent_prompt", "").rstrip(), "```", ""])
    return "\n".join(lines)


def packets_to_json(packets: list[dict[str, Any]]) -> str:
    return json.dumps(packets, ensure_ascii=False, indent=2)


def write_packets(
    project_root: str | Path,
    packets: list[dict[str, Any]],
    *,
    fmt: str = "markdown",
    out_dir: str | Path | None = None,
) -> list[Path]:
    root = Path(project_root)
    target_dir = Path(out_dir) if out_dir else root / "state" / "dispatch"
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "json" if fmt == "json" else "md"
    paths: list[Path] = []

    for packet in packets:
        path = target_dir / f"{timestamp}_{_slug(str(packet.get('task_id', 'task')))}.{suffix}"
        if fmt == "json":
            path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            path.write_text(packet_to_markdown(packet), encoding="utf-8")
        paths.append(path)
    return paths
