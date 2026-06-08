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

from utils.file_guard import ALTERNATE_OUTPUT_SUFFIXES, get_canonical_output_path
from utils.gate_rubric import render_gate_rubric_block

from .conductor import Conductor, GATE_CRITICS
from .project import GATE_STAGES
from .revision_router import build_revision_routes


PATH_RESOLUTION = {
    "project": "`project:<relative-path>` resolves from the project root. The packet path normally lives under `<project>/state/dispatch/`, so the project root can be recovered from the packet location.",
    "framework": "`framework:<relative-path>` resolves from SPIRAL_FRAMEWORK_ROOT or the current AutoPaper2 framework root.",
    "legacy": "Absolute paths are not required in dispatch packets; legacy absolute paths may be resolved only for backwards compatibility.",
}


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
    "If the requested output already exists, read it before writing and preserve correct content not targeted by the repair.",
    "Do not truncate and rewrite the whole Markdown file when a section-level edit can satisfy the task.",
]


REVIEWER_BOUNDARIES = [
    "Review only; do not modify the stage output under review.",
    "Read the original file paths directly; do not rely on executor summaries.",
    "Write exactly one review file at the requested output path.",
    "Do not return PASS when evidence is pending, failed, unavailable, ambiguous, or waiting for human/manual action.",
    "For non-PASS verdicts, include target_stage, blocking_reason, required_fix, success_criteria, evidence_paths, rebuild_mode, rerun_scope, and handoff_updates.",
    "Do not prescribe exact code edits, lines, function calls, signatures, config values, or commands unless the code/config/log path was directly checked and listed in Evidence Checked or evidence_paths.",
    "If only Markdown outputs were checked, write task-level advice: inspect the suspected owner files, verify the root cause, repair it, add evidence/tests, and rerun downstream.",
]


DELEGATED_TASK_TYPES = {
    "stage_execution",
    "stage_review",
    "gate_review",
    "revision_routing",
    "ssh_ops",
}


REVISION_ROUTING_BOUNDARIES = [
    "Use the script-generated revision routes; do not reinterpret the action plan manually.",
    "Do not edit routed target-stage outputs directly from the main agent/conductor.",
    "Delegate each routed target stage to its responsible subagent before asking the revision agent to write M6S05_revision_execution.md.",
    "If routed work is incomplete, record it as blocked/partial; do not invent completion evidence.",
]


SSH_OPS_BOUNDARIES = [
    "Manage SSH registry, health checks, leases, remote workspace setup, sync, and remote command evidence only.",
    "Do not write knowledge/ or drafts/ stage outputs.",
    "Do not write stage-review or gate-review verdicts.",
    "Do not store passwords, private keys, API tokens, or unredacted secrets in registry, leases, logs, or project files.",
    "Record allocation and operational evidence under state/ and config/ only unless a stage executor explicitly owns the target path.",
]


LONG_CONTEXT_STAGES = {
    "M3S02",
    "M3S04",
    "M4S03",
    "M5S08",
    "M5S09",
    "M6S01",
    "M6S05",
}


ROLE_SPEC_PATHS = {
    "survey": "docs/AGENTS/_specs/survey.md",
    "ideation": "docs/AGENTS/_specs/survey.md",
    "method": "docs/AGENTS/_specs/method.md",
    "experiment": "docs/AGENTS/_specs/experiment.md",
    "analysis": "docs/AGENTS/_specs/analysis.md",
    "writing": "docs/AGENTS/_specs/writing.md",
    "submission": "docs/AGENTS/_specs/submission_rebuttal.md",
    "rebuttal": "docs/AGENTS/_specs/submission_rebuttal.md",
    "revision": "docs/AGENTS/_specs/submission_rebuttal.md",
    "ssh": "docs/AGENTS/_specs/ops.md",
    "build_verifier": "docs/AGENTS/_specs/ops.md",
    "review": "docs/AGENTS/_specs/critic_reviews.md",
}


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


def _framework_root() -> Path:
    return Path(__file__).parent.parent.resolve()


def _as_posix(path: Path) -> str:
    return path.as_posix()


def _path_ref(value: str | Path, project_root: Path, *, default_scope: str | None = None) -> str:
    """Return a portable dispatch path reference.

    Dispatch packets are durable project artifacts.  They must not bake in the
    local server mount point; subagents resolve these refs at launch time.
    """
    text = str(value).strip()
    if not text:
        return ""
    if text.startswith(("project:", "framework:")):
        return text

    path = Path(text)
    project = Path(project_root).resolve()
    framework = _framework_root()
    if path.is_absolute():
        resolved = path.resolve()
        if default_scope == "framework":
            try:
                return f"framework:{_as_posix(resolved.relative_to(framework))}"
            except ValueError:
                pass
        try:
            return f"project:{_as_posix(resolved.relative_to(project))}"
        except ValueError:
            pass
        try:
            return f"framework:{_as_posix(resolved.relative_to(framework))}"
        except ValueError:
            pass
        return text

    rel = _as_posix(path)
    if default_scope == "framework":
        return f"framework:{rel}"
    if default_scope == "project":
        return f"project:{rel}"
    if rel.startswith(("docs/", "skills/", ".claude/", "templates/", "scripts/")):
        return f"framework:{rel}"
    return f"project:{rel}"


def _packet_path_ref(value: str | Path, project_root: Path) -> str:
    text = str(value).strip()
    if not text:
        return ""
    path = Path(text)
    if not path.is_absolute():
        return _path_ref(path, project_root)
    resolved = path.resolve()
    try:
        return f"framework:{_as_posix(resolved.relative_to(_framework_root()))}"
    except ValueError:
        pass
    try:
        return f"project:{_as_posix(resolved.relative_to(Path(project_root).resolve()))}"
    except ValueError:
        pass
    return path.name


def _path_refs(values: list[str | Path], project_root: Path) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        ref = _path_ref(value, project_root)
        if ref and ref not in seen:
            out.append(ref)
            seen.add(ref)
    return out


def _replace_root_fragments(text: str, project_root: Path) -> str:
    project = str(Path(project_root).resolve())
    framework = str(_framework_root())
    replacements = (
        (project + "/", "project:"),
        (project, "project:."),
        (framework + "/", "framework:"),
        (framework, "framework:."),
    )
    out = text
    for old, new in replacements:
        out = out.replace(old, new)
    return out


_PATH_KEYS = {
    "action_plan_path",
    "agent_md",
    "aggregate_output",
    "framework_root",
    "md_protocol",
    "output_doc",
    "output_path",
    "packet_path",
    "project_root",
    "role_spec",
    "source_action_plan",
    "subject_output",
}

_PATH_LIST_KEYS = {
    "evidence_paths",
    "input_docs",
    "shared_contracts",
}


def _portable_value(value: Any, project_root: Path, *, key: str = "") -> Any:
    if isinstance(value, Path):
        scope = "framework" if key in {"agent_md", "md_protocol", "role_spec", "framework_root"} else None
        return _path_ref(value, project_root, default_scope=scope)
    if isinstance(value, dict):
        return {item_key: _portable_value(item_value, project_root, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        if key in _PATH_LIST_KEYS:
            return [_path_ref(item, project_root) if isinstance(item, (str, Path)) else item for item in value]
        return [_portable_value(item, project_root, key=key) for item in value]
    if isinstance(value, str):
        if key in _PATH_KEYS or key.endswith(("_path", "_paths", "_doc", "_output", "_root")):
            scope = "framework" if key in {"agent_md", "md_protocol", "role_spec", "framework_root"} else None
            return _path_ref(value, project_root, default_scope=scope)
        return _replace_root_fragments(value, project_root)
    return value


def _agent_sections_for(packet: dict[str, Any]) -> list[str]:
    sections = ["identity", "boundaries"]
    task_type = packet.get("task_type", "")
    stage = str(packet.get("stage", "") or "")
    if stage:
        sections.append(stage)
    if task_type in {"stage_review", "gate_review"}:
        sections.extend(["review_protocol", "verdict_schema"])
    if task_type == "revision_routing":
        sections.append("revision_routing")
    if packet.get("backtrack_advice"):
        sections.append("backtrack_advice")
    if packet.get("gate_rubric"):
        sections.append("gate_rubric")
    sections.append("context_recovery")
    return sections


def _task_objective(packet: dict[str, Any]) -> str:
    task_type = packet.get("task_type", "")
    role = packet.get("role", "subagent")
    stage = packet.get("stage", "")
    output = packet.get("output_path", "")
    if task_type == "stage_execution":
        if packet.get("backtrack_advice"):
            return (
                f"Re-execute stage {stage} as the {role} subagent using the packet backtrack_advice/repair_brief, "
                f"then write the assigned stage output at {output}."
            )
        return f"Execute stage {stage} as the {role} subagent and write the assigned stage output at {output}."
    if task_type == "stage_review":
        subject = packet.get("subject_output", "")
        return f"Review {subject} for stage {stage} as {role} and write exactly one review file at {output}."
    if task_type == "gate_review":
        gate = packet.get("gate_id", "")
        return f"Run the {gate} gate review as {role} and write exactly one critic review at {output}."
    if task_type == "revision_routing":
        return f"Route and record M6S05 revision execution using the script-generated routing plan, then write {output}."
    if task_type == "ssh_ops":
        op = packet.get("ssh_operation", "")
        return f"Perform the SSH operation '{op}' within the AutoPaper2 SSH boundaries."
    return f"Handle AutoPaper2 task {packet.get('task_id', '')} as {role}."


def _context_policy(packet: dict[str, Any]) -> dict[str, Any]:
    stage = str(packet.get("stage", "") or "")
    task_type = str(packet.get("task_type", "") or "")
    task_id = _slug(str(packet.get("task_id", "task")))
    return {
        "handoff_mode": "packet_path_only",
        "no_parent_context": True,
        "read_strategy": "read_packet_first_then_role_sections_then_needed_inputs",
        "max_initial_prompt_chars": 1200,
        "max_direct_file_read_chars": 50000,
        "large_input_policy": "For large files or directories, inspect headings, manifests, file stats, indexes, or tails first; do not paste whole logs or papers into the active prompt.",
        "directory_policy": "List/index directories before reading contained files; only open files needed for the assigned task.",
        "resume_required": stage in LONG_CONTEXT_STAGES or task_type in {"revision_routing", "ssh_ops"},
        "worklog_path": f"project:state/agent_runs/{task_id}.yaml",
    }


def _output_write_policy(output_ref: str) -> dict[str, Any]:
    if not output_ref:
        return {}
    return {
        "mode": "canonical_in_place",
        "target_path": output_ref,
        "overwrite_existing": True,
        "read_existing_before_write": True,
        "preserve_unaffected_content": True,
        "edit_granularity": "section_or_smaller",
        "whole_file_replacement": "forbidden unless the entire existing file is invalid; justify every removed major section in the completion summary.",
        "if_target_exists": "Read the existing file first, then update this exact file in place with minimal section-level edits; preserve correct unaffected content and do not create a sibling Markdown file.",
        "forbid_alternate_outputs": True,
        "forbidden_suffixes": list(ALTERNATE_OUTPUT_SUFFIXES),
    }


def _contract_paths(packet: dict[str, Any]) -> list[str]:
    paths = ["framework:docs/AGENTS/_shared/runtime_contract.md"]
    if packet.get("task_type") in {"stage_review", "gate_review"}:
        paths.append("framework:docs/AGENTS/_shared/review_contract.md")
    if packet.get("role") == "conductor":
        paths.append("framework:docs/AGENTS/_shared/orchestrator_contract.md")
    return paths


def _role_spec_path(packet: dict[str, Any]) -> str:
    task_type = str(packet.get("task_type", "") or "")
    role = str(packet.get("role", "") or "")
    if task_type in {"stage_review", "gate_review"}:
        return "framework:docs/AGENTS/_specs/critic_reviews.md"
    rel = ROLE_SPEC_PATHS.get(role, "")
    return f"framework:{rel}" if rel else ""


def _display_path(value: str | Path) -> str:
    path = Path(value)
    framework_root = Path(__file__).parent.parent.resolve()
    try:
        return str(path.relative_to(framework_root))
    except ValueError:
        return str(path)


def render_compact_launch_prompt(packet: dict[str, Any], packet_path: str | Path | None = None) -> str:
    """Return the only text the conductor should pass to a subagent."""
    path = str(packet.get("packet_path") or packet_path or "<dispatch packet path>")
    lines = [
        "Read and execute this AutoPaper2 dispatch packet:",
        path,
        "",
        f"Task: {packet.get('task_type', '')} / {packet.get('role', '')}",
    ]
    if packet.get("stage"):
        lines.append(f"Stage: {packet['stage']}")
    if packet.get("gate_id"):
        lines.append(f"Gate: {packet['gate_id']}")
    if packet.get("output_path"):
        lines.append(f"Required output: {packet['output_path']}")
    if packet.get("role_spec"):
        lines.append(f"Role spec: {packet['role_spec']}")
    if packet.get("backtrack_advice"):
        lines.append("Backtrack: read the packet Backtrack Advice and Repair Brief before opening stage files.")
    lines.extend(
        [
            "",
            "Do not use the parent conversation as task context.",
            "Resolve project: refs from the packet project root; resolve framework: refs from SPIRAL_FRAMEWORK_ROOT or the current AutoPaper2 root.",
            "First read the packet, then read the role instructions and input paths listed inside it.",
            "Read files selectively according to the packet context_policy; do not paste whole large inputs into context.",
            "Write only the requested output path and any explicitly allowed evidence/worklog paths.",
            "If the requested output already exists, read it first, preserve correct unaffected content, and edit only the sections needed for the repair; do not create v2/new/revised/backtrack Markdown copies.",
        ]
    )
    policy = packet.get("context_policy") or {}
    worklog = policy.get("worklog_path", "")
    if policy.get("resume_required") and worklog:
        lines.append(f"If context grows, update the worklog and ask the conductor to resume with the same packet: {worklog}")
    return "\n".join(lines).strip() + "\n"


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
        "project_root": "project:.",
        "path_resolution": PATH_RESOLUTION,
        "role": role,
        "agent_md": _path_ref(agent_md, project_root, default_scope="framework"),
        "input_docs": _path_refs(input_docs, project_root),
        "output_path": _path_ref(output_path, project_root, default_scope="project") if output_path else "",
        "main_agent_boundaries": MAIN_AGENT_BOUNDARIES,
    }
    if data["output_path"]:
        data["output_write_policy"] = _output_write_policy(data["output_path"])
    if extra:
        data.update(_portable_value(extra, project_root))
    data.setdefault("schema_version", "dispatch.v2")
    data.setdefault("task_objective", _task_objective(data))
    data.setdefault("agent_sections", _agent_sections_for(data))
    data.setdefault("context_policy", _context_policy(data))
    data.setdefault("shared_contracts", _contract_paths(data))
    data.setdefault("role_spec", _role_spec_path(data))
    data.setdefault("subagent_launch_prompt", render_compact_launch_prompt(data))
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
    input_docs = [Path(p) for p in plan.get("input_docs", [])]
    if output_path.exists():
        input_docs = [output_path, *[path for path in input_docs if path.resolve() != output_path.resolve()]]
    task_id = _slug(f"{stage_id}_{role}_execute")
    extra = {
        "stage": stage_id,
        "phase": plan.get("phase", "stage"),
        "md_protocol": plan.get("md_protocol", ""),
        "stage_checkers": plan.get("stage_checkers", []),
        "stage_review_outputs": plan.get("stage_review_outputs", {}),
        "backtrack_advice": plan.get("backtrack_advice", {}),
        "existing_output_path": str(output_path) if output_path.exists() else "",
        "subagent_boundaries": EXECUTOR_BOUNDARIES,
        "after_completion": [
            f"Ensure output exists: {output_path}",
            "If this is a re-execution/backtrack and the output already existed, confirm the existing file was read and correct unaffected sections were preserved.",
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
        input_docs=input_docs,
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
    if output_path.exists():
        inputs = [output_path, *[path for path in inputs if path.resolve() != output_path.resolve()]]

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
            "existing_output_path": str(output_path) if output_path.exists() else "",
            "revision_routing": routing,
            "subagent_boundaries": REVISION_ROUTING_BOUNDARIES,
            "after_completion": [
                "Run or delegate the routed target-stage work before final M6S05 reporting.",
                f"Ensure execution record exists only after evidence is available: {output_path}",
                "If the execution record already existed, confirm the existing file was read and correct unaffected sections were preserved.",
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
                root / "knowledge" / "M2" / "M2S05_metric_protocol.yaml",
                root / "knowledge" / "handoff_M2_M3.md",
            ]
        )
    if stage == "M3S02":
        extra_expected.extend(
            [
                root / "config" / "execution_env.yaml",
                root / "state" / "ssh_allocation.yaml",
                root / "experiments" / "logs" / "m3s02_longrun_ledger.md",
                root / "experiments" / "requirements.lock",
                root / "experiments" / "requirements.txt",
            ]
        )
    if stage == "M3S03":
        extra_expected.extend(
            [
                root / "experiments" / "baselines" / "baseline_lock.yaml",
                root / "experiments" / "baselines",
            ]
        )
    if stage == "M3S04":
        extra_expected.extend(
            [
                root / "experiments" / "results.tsv",
                root / "experiments" / "runs",
                root / "experiments" / "configs" / "resource_plan.yaml",
                root / "experiments" / "logs" / "runtime_events.jsonl",
            ]
        )
    if stage in {"M4S02", "M4S03"}:
        extra_expected.extend(
            [
                root / "experiments" / "configs" / "m4_task_queue.yaml",
            ]
        )
    if stage == "M4S03":
        extra_expected.extend(
            [
                root / "experiments" / "analysis_results.tsv",
                root / "experiments" / "configs" / "m4_task_allocation.yaml",
                root / "experiments" / "artifacts" / "analysis_experiment",
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
                        "If this review already existed, confirm the same canonical review file was updated in place.",
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
        root / "knowledge" / "M3" / "M3S01_main_experiment_design.md",
        root / "knowledge" / "M3" / "M3S04_main_experiment.md",
        root / "knowledge" / "M3" / "M3S05_result_validation.md",
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
                        "If this round review already existed, confirm the same canonical review file was updated in place.",
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
    if gate_id == "G3":
        input_docs = _existing_or_expected(
            [
                *[Path(path) for path in input_docs],
                root / "experiments" / "results.tsv",
                root / "experiments" / "runs",
                root / "experiments" / "logs" / "runtime_events.jsonl",
                root / "experiments" / "configs" / "resource_plan.yaml",
            ]
        )
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
                        "If this gate critic review already existed, confirm the same canonical review file was updated in place.",
                        "Return verdict and the review path to the conductor.",
                        f"The conductor aggregates all critic reviews into {aggregate_output}.",
                        "Use only PASS, REVISE, REWORK, BACKTRACK, FIX, or HALT. Do not use CONDITIONAL.",
                        "Aggregate PASS cannot override any individual non-PASS critic review.",
                        "The aggregate review must include the configured Rubric Results table before advancement.",
                    ],
                },
            )
        )
    return packets


def build_ssh_ops_packet(project_root: str | Path, operation: str | None = None) -> dict[str, Any]:
    root = Path(project_root)
    framework_root = Path(__file__).parent.parent
    op = operation or "alloc"
    task_id = _slug(f"ssh_{op}")
    output = root / "state" / "ssh_allocation.yaml" if op in {"alloc", "allocate", "apply"} else None
    input_docs = _existing_or_expected(
        [
            root / "config" / "execution_env.yaml",
            root / "state" / "ssh_allocation.yaml",
            framework_root / "config" / "ssh_servers.yaml",
            framework_root / "state" / "ssh_leases.yaml",
            framework_root / "state" / "ssh_events.jsonl",
        ]
    )
    return _packet(
        task_type="ssh_ops",
        task_id=task_id,
        project_root=root,
        role="ssh",
        agent_md=framework_root / "docs" / "AGENTS" / "ssh" / "AGENT.md",
        output_path=output,
        input_docs=input_docs,
        extra={
            "ssh_operation": op,
            "framework_root": str(framework_root),
            "subagent_boundaries": SSH_OPS_BOUNDARIES,
            "after_completion": [
                "Return server_id, lease_id, changed config/state paths, and concise operation evidence.",
                "If allocation is requested, ensure config/execution_env.yaml references execution.server_id and execution.lease_id.",
                "If a remote command was run, report its command class, return code, and redacted log path or output summary.",
            ],
        },
    )


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
            "project_root": "project:.",
            "path_resolution": PATH_RESOLUTION,
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
    if normalized in {"ssh", "ssh-ops", "infra"}:
        return [build_ssh_ops_packet(project_root, target)]
    raise ValueError(f"Unknown dispatch scope: {scope}")


def render_subagent_prompt(packet: dict[str, Any]) -> str:
    lines: list[str] = []
    task_type = packet.get("task_type", "")
    role = packet.get("role", "")
    lines.append(f"You are the AutoPaper2 {role} subagent for task {packet.get('task_id')}.")
    lines.append("Use this packet as the task source of truth; do not inherit or rely on the parent conversation.")
    lines.append("")
    if packet.get("task_objective"):
        lines.append(f"Objective: {packet['task_objective']}")
    lines.append(f"Task type: {task_type}")
    if packet.get("stage"):
        lines.append(f"Stage: {packet['stage']}")
    if packet.get("round"):
        lines.append(f"Round: {packet['round']}")
    if packet.get("gate_id"):
        lines.append(f"Gate: {packet['gate_id']} ({packet.get('gate_stage', '')})")
    if packet.get("ssh_operation"):
        lines.append(f"SSH operation: {packet['ssh_operation']}")
    lines.append(f"Project root: {packet.get('project_root')}")
    if packet.get("framework_root"):
        lines.append(f"Framework root: {packet.get('framework_root')}")
    lines.append(f"Role instructions: {packet.get('agent_md')}")
    if packet.get("md_protocol"):
        lines.append(f"Markdown protocol: {packet.get('md_protocol')}")
    if packet.get("shared_contracts"):
        lines.append("Shared contracts:")
        for path in packet.get("shared_contracts", []):
            lines.append(f"- {path}")
    if packet.get("role_spec"):
        lines.append(f"Role spec: {packet.get('role_spec')}")
    sections = packet.get("agent_sections", [])
    if sections:
        lines.append(f"Relevant role-instruction sections: {', '.join(sections)}")
    policy = packet.get("context_policy") or {}
    if policy:
        lines.append("")
        lines.append("Context policy:")
        for key in (
            "handoff_mode",
            "read_strategy",
            "max_direct_file_read_chars",
            "large_input_policy",
            "directory_policy",
            "worklog_path",
        ):
            value = policy.get(key, "")
            if value != "":
                lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("Input paths (read directly; do not rely on summaries):")
    for path in packet.get("input_docs", []):
        lines.append(f"- {path}")
    if packet.get("subject_output"):
        lines.append(f"Subject output under review: {packet['subject_output']}")
    if packet.get("output_path"):
        lines.append("")
        lines.append(f"Required output path: {packet['output_path']}")
    write_policy = packet.get("output_write_policy") or {}
    if write_policy:
        lines.append("Output write policy:")
        for key in (
            "mode",
            "target_path",
            "overwrite_existing",
            "read_existing_before_write",
            "preserve_unaffected_content",
            "edit_granularity",
            "whole_file_replacement",
            "if_target_exists",
            "forbid_alternate_outputs",
            "forbidden_suffixes",
        ):
            value = write_policy.get(key, "")
            if value != "":
                lines.append(f"- {key}: {value}")
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
        brief = advice.get("repair_brief") or {}
        if brief:
            lines.append("")
            lines.append("Repair Brief For Executor:")
            for key in (
                "error_summary",
                "required_change",
                "success_criteria",
                "evidence_to_recheck",
                "rebuild_mode",
                "rerun_scope",
                "handoff_updates",
            ):
                lines.append(f"- {key}: {brief.get(key, '')}")

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
        "This file is the durable task contract. The conductor should pass only the compact launch prompt below to the subagent, not the parent conversation or upstream document contents.",
        "",
        f"- task_type: {packet.get('task_type', '')}",
        f"- schema_version: {packet.get('schema_version', '')}",
        f"- delegation_required: {packet.get('delegation_required', False)}",
        f"- project_root: `{packet.get('project_root', '')}`",
        f"- agent_md: `{packet.get('agent_md', '')}`",
    ]
    if packet.get("packet_path"):
        lines.append(f"- packet_path: `{packet['packet_path']}`")
    if packet.get("role"):
        lines.append(f"- role: `{packet['role']}`")
    if packet.get("stage"):
        lines.append(f"- stage: `{packet['stage']}`")
    if packet.get("gate_id"):
        lines.append(f"- gate_id: `{packet['gate_id']}`")
    if packet.get("ssh_operation"):
        lines.append(f"- ssh_operation: `{packet['ssh_operation']}`")
    if packet.get("output_path"):
        lines.append(f"- output_path: `{packet['output_path']}`")
    if packet.get("task_objective"):
        lines.append(f"- task_objective: {packet['task_objective']}")
    if packet.get("output_write_policy"):
        lines.append(f"- output_write_policy: `{json.dumps(packet['output_write_policy'], ensure_ascii=False)}`")
    if packet.get("shared_contracts"):
        lines.append(f"- shared_contracts: `{', '.join(packet['shared_contracts'])}`")
    if packet.get("role_spec"):
        lines.append(f"- role_spec: `{packet['role_spec']}`")
    if packet.get("agent_sections"):
        lines.append(f"- agent_sections: `{', '.join(packet['agent_sections'])}`")
    resolution = packet.get("path_resolution") or PATH_RESOLUTION
    if resolution:
        lines.extend(["", "## Path Resolution", ""])
        for key, value in resolution.items():
            lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Compact Launch Prompt",
            "",
            "Pass only this prompt plus the packet path to the subagent:",
            "",
            "```text",
            packet.get("subagent_launch_prompt", render_compact_launch_prompt(packet)).rstrip(),
            "```",
            "",
            "## Context Policy",
            "",
        ]
    )
    policy = packet.get("context_policy") or {}
    for key, value in policy.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Input Paths", ""])
    for path in packet.get("input_docs", []):
        lines.append(f"- `{path}`")
    if packet.get("subject_output"):
        lines.append(f"- subject_output: `{packet['subject_output']}`")
    if packet.get("md_protocol"):
        lines.append(f"- md_protocol: `{packet['md_protocol']}`")
    if packet.get("gate_rubric"):
        lines.extend(["", "## Gate Rubric", "", packet["gate_rubric"].rstrip()])
    advice = packet.get("backtrack_advice") or {}
    if advice:
        lines.extend(["", "## Backtrack Advice", ""])
        for key, value in advice.items():
            lines.append(f"- {key}: {value}")
        brief = advice.get("repair_brief") or {}
        if brief:
            lines.extend(["", "## Repair Brief For Executor", ""])
            lines.append(f"- error_summary: {brief.get('error_summary', '')}")
            lines.append(f"- required_change: {brief.get('required_change', '')}")
            lines.append(f"- success_criteria: {brief.get('success_criteria', '')}")
            lines.append(f"- evidence_to_recheck: {brief.get('evidence_to_recheck', [])}")
            lines.append(f"- rebuild_mode: {brief.get('rebuild_mode', '')}")
            lines.append(f"- rerun_scope: {brief.get('rerun_scope', '')}")
            lines.append(f"- handoff_updates: {brief.get('handoff_updates', [])}")
            instructions = brief.get("executor_instructions", [])
            if instructions:
                lines.append("- executor_instructions:")
                for item in instructions:
                    lines.append(f"  - {item}")
    routing = packet.get("revision_routing") or {}
    if routing:
        lines.extend(["", "## Revision Routing", "", "```json", json.dumps(routing, ensure_ascii=False, indent=2), "```"])
    lines.extend(["", "## Boundaries", ""])
    for rule in packet.get("subagent_boundaries", []):
        lines.append(f"- {rule}")
    for rule in packet.get("main_agent_boundaries", []):
        lines.append(f"- {rule}")
    after = packet.get("after_completion", [])
    if after:
        lines.extend(["", "## After Completion", ""])
        for item in after:
            lines.append(f"- {item}")
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
        written_packet = dict(packet)
        written_packet["packet_path"] = _packet_path_ref(path, root)
        written_packet["subagent_launch_prompt"] = render_compact_launch_prompt(written_packet, path)
        if fmt == "json":
            path.write_text(json.dumps(written_packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            path.write_text(packet_to_markdown(written_packet), encoding="utf-8")
        paths.append(path)
    return paths
