#!/usr/bin/env python3
"""State Manager — CLI for AutoPaper2 pipeline state management."""

from __future__ import annotations

import os
import re
import sys
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional

_framework_root = Path(__file__).parent.parent.resolve()
if str(_framework_root) not in sys.path:
    sys.path.insert(0, str(_framework_root))

from utils.file_guard import (
    validate_stage_output,
    check_single_file_principle,
    validate_gate_review,
    get_canonical_output_path,
)
from utils.stage_gate import check_stage, _check_m1s02_rounds
from utils.gate_rubric import validate_gate_rubric
from utils.source_log_validator import validate as validate_source_log
from spiral.project_entry import normalize_keywords as _normalize_keywords, parse_anchor_input
from spiral.verdict_parser import (
    VerdictParser,
    missing_m3_repair_fields,
    extract_m3s04_decision,
    is_valid_rebuild_mode,
)


# ---------------------------------------------------------------------------
# Multi-project helpers
# ---------------------------------------------------------------------------

def _get_default_projects_root() -> Path:
    framework_root = Path(__file__).parent.parent.resolve()
    return framework_root / "projects"


PROJECTS_ROOT = _get_default_projects_root()
_CURRENT_PROJECT_FILE = Path.home() / ".spiral" / "current_project"


def _ensure_current_project_dir() -> None:
    _CURRENT_PROJECT_FILE.parent.mkdir(parents=True, exist_ok=True)


def _get_current_project() -> Optional[Path]:
    if _CURRENT_PROJECT_FILE.exists():
        path = Path(_CURRENT_PROJECT_FILE.read_text(encoding="utf-8").strip())
        if path.exists():
            return path
    return None


def _set_current_project(project_dir: str) -> None:
    _ensure_current_project_dir()
    path = Path(project_dir).resolve()
    _CURRENT_PROJECT_FILE.write_text(str(path), encoding="utf-8")
    print(f"[USE] Current project set to: {path}")


def _resolve_project_dir(args: list[str]) -> str:
    for i, arg in enumerate(args):
        if arg == "--project" and i + 1 < len(args):
            project_dir = str(Path(args[i + 1]).resolve())
            del args[i : i + 2]
            return project_dir
    current = _get_current_project()
    if current:
        return str(current)
    raise SystemExit(
        "[ERROR] No project specified.\n"
        "  Use: --project /path/to/project  or  python state_manager.py use /path/to/project\n"
        "  See: python state_manager.py list-projects"
    )


def _clear_stale_stage(data: dict[str, Any], stage: str) -> bool:
    stale = data.get("stale_stages", [])
    if stage in stale:
        stale.remove(stage)
        data["stale_stages"] = stale
        stage_advice = data.get("stage_backtrack_advice", {})
        if isinstance(stage_advice, dict):
            stage_advice.pop(stage, None)
            data["stage_backtrack_advice"] = stage_advice
        return True
    return False


def _is_gate_aggregate_output(project_dir: str, stage: str, output_file: str) -> bool:
    """Return True if output_file is the gate aggregate for a final stage."""
    gate_map = _GATE_STAGES_MAP
    if stage not in gate_map.values():
        return False
    gate_id = next((gid for gid, st in gate_map.items() if st == stage), None)
    if not gate_id:
        return False
    expected = Path(project_dir) / "knowledge" / "reviews" / f"{gate_id}_aggregate.md"
    try:
        return Path(output_file).resolve() == expected.resolve()
    except Exception:
        return False


def _infer_rebuild_mode(reason: str, direction: str = "", required_fix: str = "") -> str:
    text = f"{reason}\n{direction}\n{required_fix}".lower()
    full_regen_markers = [
        "method",
        "architecture",
        "baseline",
        "design",
        "hypothesis",
        "dataset",
        "metric",
        "comparison",
        "claim",
        "theory",
        "pipeline",
        "错位",
        "重做",
        "重新设计",
        "方向偏差",
        "core",
    ]
    incremental_markers = [
        "log",
        "artifact",
        "path",
        "filename",
        "format",
        "metadata",
        "record",
        "typo",
        "minor",
        "seed",
        "parameter",
        "config",
        "environment",
        "setup",
        "missing output",
    ]
    if any(marker in text for marker in full_regen_markers):
        return "full_regenerate"
    if any(marker in text for marker in incremental_markers):
        return "incremental_replay"
    return "full_regenerate"


# Import from spiral package
from spiral.project import MODULE_STAGES, GATE_STAGES as _GATE_STAGES_MAP, AGENT_FOR_STAGE

MODULE_OF = {}
for mod, stages in MODULE_STAGES.items():
    for s in stages:
        MODULE_OF[s] = mod

GATE_STAGES = set(_GATE_STAGES_MAP.values())
ALL_MODULES = list(MODULE_STAGES.keys())


def _load_venue_registry() -> dict:
    registry_path = Path(__file__).parent.parent / "config" / "venue_registry.yaml"
    if registry_path.exists():
        with open(registry_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _get_venue_config(venue_id: str) -> dict:
    registry = _load_venue_registry()
    return registry.get("venues", {}).get(venue_id, {})


def _load(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)


def _split_value_items(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;|\n]+", value) if item.strip()]


def _parse_create_args(args: list[str]) -> dict[str, Any]:
    positional: list[str] = []
    keywords: list[str] = []
    references: list[str] = []
    foundations: list[str] = []
    notes: list[str] = []
    manifest: Optional[str] = None
    venue: Optional[str] = None
    auto_advance: bool = False
    execution_env: dict[str, Any] = {}
    ssh_server_id: Optional[str] = None
    ssh_server_ids: list[str] = []
    ssh_pool_count: Optional[int] = None
    ssh_lease_hours: Optional[int] = None
    ssh_min_gpu_count: int = 0
    ssh_min_vram_gb: Optional[float] = None
    ssh_server_tags: list[str] = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--auto-advance":
            auto_advance = True
            i += 1
            continue
        if arg == "--env-mode":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --env-mode requires a value (local|ssh)")
            execution_env["execution.mode"] = args[i + 1]
            i += 2
            continue
        if arg == "--server-id":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --server-id requires a value (server id or auto)")
            ssh_server_id = args[i + 1]
            execution_env["execution.mode"] = "ssh"
            execution_env["execution.server_id"] = ssh_server_id
            execution_env["execution.ssh.server_id"] = ssh_server_id
            i += 2
            continue
        if arg == "--server-ids":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --server-ids requires a comma-separated value")
            ssh_server_ids = _split_value_items(args[i + 1])
            execution_env["execution.resource_optimization.resource_pool.enabled"] = True
            execution_env["execution.resource_optimization.resource_pool.include_local"] = True
            i += 2
            continue
        if arg == "--server-pool-count":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --server-pool-count requires a value")
            ssh_pool_count = int(args[i + 1])
            execution_env["execution.resource_optimization.resource_pool.enabled"] = True
            execution_env["execution.resource_optimization.resource_pool.include_local"] = True
            i += 2
            continue
        if arg == "--lease-hours":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --lease-hours requires a value")
            ssh_lease_hours = int(args[i + 1])
            i += 2
            continue
        if arg == "--min-gpu-count":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --min-gpu-count requires a value")
            ssh_min_gpu_count = int(args[i + 1])
            i += 2
            continue
        if arg == "--min-vram-gb":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --min-vram-gb requires a value")
            ssh_min_vram_gb = float(args[i + 1])
            i += 2
            continue
        if arg == "--server-tags":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --server-tags requires a comma-separated value")
            ssh_server_tags = _split_value_items(args[i + 1])
            i += 2
            continue
        if arg == "--ssh-host":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --ssh-host requires a value")
            execution_env["execution.ssh.host"] = args[i + 1]
            i += 2
            continue
        if arg == "--ssh-user":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --ssh-user requires a value")
            execution_env["execution.ssh.user"] = args[i + 1]
            i += 2
            continue
        if arg == "--ssh-port":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --ssh-port requires a value")
            execution_env["execution.ssh.port"] = int(args[i + 1])
            i += 2
            continue
        if arg == "--ssh-auth-method":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --ssh-auth-method requires a value (key|password)")
            method = args[i + 1]
            if method not in ("key", "password"):
                raise SystemExit("[ERROR] --ssh-auth-method must be 'key' or 'password'")
            execution_env["execution.ssh.auth_method"] = method
            i += 2
            continue
        if arg == "--ssh-password":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --ssh-password requires a value")
            execution_env["execution.ssh.password"] = args[i + 1]
            i += 2
            continue
        if arg == "--ssh-workspace":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --ssh-workspace requires a value")
            execution_env["execution.ssh.workspace_path"] = args[i + 1]
            i += 2
            continue
        if arg == "--ssh-conda-env":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --ssh-conda-env requires a value")
            execution_env["execution.ssh.conda_env_name"] = args[i + 1]
            i += 2
            continue
        if arg == "--python-version":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --python-version requires a value")
            execution_env["execution.local.python_version"] = args[i + 1]
            execution_env["execution.ssh.python_version"] = args[i + 1]
            i += 2
            continue
        if arg == "--cuda-version":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --cuda-version requires a value")
            execution_env["execution.local.cuda_version"] = args[i + 1]
            execution_env["execution.ssh.cuda_version"] = args[i + 1]
            i += 2
            continue
        if arg == "--env-manager":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --env-manager requires a value (conda|venv|uv|docker)")
            execution_env["execution.local.env_manager"] = args[i + 1]
            execution_env["execution.ssh.env_manager"] = args[i + 1]
            i += 2
            continue
        if arg in {"--keywords", "--keyword"}:
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --keywords requires a value")
            keywords.extend(_split_value_items(args[i + 1]))
            i += 2
            continue
        if arg in {"--reference", "--ref"}:
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --reference requires a value")
            references.extend(_split_value_items(args[i + 1]))
            i += 2
            continue
        if arg in {"--foundation", "--base"}:
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --foundation requires a value")
            foundations.extend(_split_value_items(args[i + 1]))
            i += 2
            continue
        if arg == "--anchor":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --anchor requires a value")
            role, value = parse_anchor_input(args[i + 1], "reference")
            if role == "foundation":
                foundations.extend(_split_value_items(value))
            elif role == "both":
                references.extend(_split_value_items(value))
                foundations.extend(_split_value_items(value))
            else:
                references.extend(_split_value_items(value))
            i += 2
            continue
        if arg in {"--input-manifest", "--manifest"}:
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --input-manifest requires a value")
            manifest = args[i + 1]
            i += 2
            continue
        if arg in {"--note", "--notes"}:
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --note requires a value")
            notes.append(args[i + 1])
            i += 2
            continue
        if arg == "--venue":
            if i + 1 >= len(args):
                raise SystemExit("[ERROR] --venue requires a value")
            venue = args[i + 1]
            i += 2
            continue
        if arg.startswith("--"):
            raise SystemExit(f"[ERROR] Unknown flag for create: {arg}")
        positional.append(arg)
        i += 1

    if len(positional) < 2:
        raise SystemExit("Usage: create <topic> <display_name> [venue] [options]")

    return {
        "topic": positional[0],
        "display_name": positional[1],
        "positional_venue": positional[2] if len(positional) > 2 else None,
        "venue": venue,
        "keywords": _normalize_keywords(keywords),
        "reference_papers": references,
        "foundation_papers": foundations,
        "input_manifest": manifest,
        "notes": " ".join(part for part in notes if part).strip(),
        "auto_advance": auto_advance,
        "execution_env": execution_env,
        "ssh_server_id": ssh_server_id,
        "ssh_server_ids": ssh_server_ids,
        "ssh_pool_count": ssh_pool_count,
        "ssh_lease_hours": ssh_lease_hours,
        "ssh_min_gpu_count": ssh_min_gpu_count,
        "ssh_min_vram_gb": ssh_min_vram_gb,
        "ssh_server_tags": ssh_server_tags,
    }


def _build_backtrack_advice(
    target_stage: str,
    reason: str,
    direction: str = "",
    source: str = "human",
    required_fix: str = "",
    success_criteria: str = "",
) -> dict:
    repair_hint = required_fix or direction or reason
    rebuild_mode = _infer_rebuild_mode(reason, direction, repair_hint)
    return {
        "source": source,
        "target_stage": target_stage,
        "blocking_reason": reason,
        "required_fix": repair_hint,
        "success_criteria": success_criteria or f"Stage {target_stage} can be re-run and PASS stage/review gates",
        "evidence_paths": [],
        "rebuild_mode": rebuild_mode,
        "rerun_scope": f"Re-execute {target_stage} and any stale downstream stages",
        "handoff_updates": [],
    }


def _sync_source_log_to_survey_memory(project_dir: str) -> None:
    """Import sources from M1_source_log.yaml into survey_memory.yaml.

    This ensures the project's SurveyMemory accurately reflects all literature
    discovered during M1S02, closing the gap between the structured source log
    and the in-memory survey registry.
    """
    from spiral.survey_memory import SurveyMemoryManager, Source, SurveyStatus

    root = Path(project_dir)
    source_log_path = root / "knowledge" / "M1" / "M1_source_log.yaml"
    if not source_log_path.exists():
        print("  [WARN] M1_source_log.yaml not found; skipping survey memory sync.")
        return

    try:
        data = _load(source_log_path)
    except Exception as exc:
        print(f"  [WARN] Failed to read M1_source_log.yaml: {exc}")
        return

    sources = data.get("sources", [])
    if not sources:
        print("  [INFO] M1_source_log.yaml has no sources; survey memory unchanged.")
        return

    mgr = SurveyMemoryManager(root, auto_connect=False)
    memory = mgr.load()

    added = 0
    for src in sources:
        try:
            source = Source(
                id=src.get("id", ""),
                title=src.get("title", ""),
                authors=src.get("authors", []),
                venue=src.get("venue", ""),
                date=src.get("date", ""),
                url=src.get("url", ""),
                type=src.get("type", "academic"),
                credibility_score=src.get("credibility", 3),
                verification_status=src.get("verification", "unverified"),
                key_claims=src.get("key_claims", []),
                limitations_noted=src.get("limitations_noted", []),
                code_availability=src.get("code_availability", "closed"),
                relevance_to_our_gap=src.get("relevance_to_our_gap", ""),
                background=src.get("background", ""),
                contributions=src.get("contributions", []),
                model=src.get("model", ""),
                method=src.get("method", ""),
                experiment_setup=src.get("experiment_setup", ""),
                results=src.get("results", ""),
                analysis=src.get("analysis", ""),
                conclusion=src.get("conclusion", ""),
            )
            memory.add_source(source)
            added += 1
        except Exception as exc:
            print(f"  [WARN] Failed to import source {src.get('id', '?')}: {exc}")

    # Also import gap evidence map if present
    gap_map = data.get("gap_evidence_map", {})
    for gap_id, gap_data in gap_map.items():
        from spiral.survey_memory import Gap
        gap = Gap(
            id=gap_id,
            description=gap_id,
            evidence_sources=gap_data.get("supporting_sources", []),
            confidence=gap_data.get("confidence", "medium"),
        )
        memory.add_gap(gap)

    memory.status = SurveyStatus.COMPLETED
    mgr.save(memory)
    print(f"  [SYNC] Survey memory updated: {added} sources, {len(gap_map)} gaps.")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_create(
    topic: str,
    display_name: str,
    venue: Optional[str] = None,
    *,
    keywords: Optional[list[str]] = None,
    reference_papers: Optional[list[str]] = None,
    foundation_papers: Optional[list[str]] = None,
    input_manifest: Optional[str] = None,
    notes: str = "",
    auto_advance: bool = False,
    execution_env: Optional[dict[str, Any]] = None,
    ssh_server_id: Optional[str] = None,
    ssh_server_ids: Optional[list[str]] = None,
    ssh_pool_count: Optional[int] = None,
    ssh_lease_hours: Optional[int] = None,
    ssh_min_gpu_count: int = 0,
    ssh_min_vram_gb: Optional[float] = None,
    ssh_server_tags: Optional[list[str]] = None,
) -> str:
    from spiral.project import ProjectManager, validate_project_name

    env_override = os.environ.get("SPIRAL_PROJECTS_ROOT")
    projects_root = Path(env_override) if env_override else PROJECTS_ROOT
    try:
        validate_project_name(display_name)
    except ValueError as exc:
        raise SystemExit(f"[ERROR] Invalid project display_name: {exc}") from exc
    projects_root.mkdir(parents=True, exist_ok=True)

    proj = ProjectManager.create(
        topic=topic,
        display_name=display_name,
        projects_root=projects_root,
        venue=venue,
        keywords=keywords,
        reference_papers=reference_papers,
        foundation_papers=foundation_papers,
        input_manifest=input_manifest,
        notes=notes,
        execution_env=execution_env,
    )

    if auto_advance:
        from spiral.state import PipelineState
        state = PipelineState(proj)
        state.set_auto_advance(True)
        print(f"[SETTINGS] Auto-advance modules: enabled")

    if ssh_server_ids or ssh_pool_count:
        from spiral.ssh_registry import SSHRegistryError, allocate_server_pool, apply_lease_pool_to_project

        try:
            leases = allocate_server_pool(
                Path(__file__).parent.parent.resolve(),
                proj,
                server_ids=ssh_server_ids or [],
                count=ssh_pool_count or len(ssh_server_ids or []) or 1,
                min_gpu_count=ssh_min_gpu_count,
                min_vram_gb=ssh_min_vram_gb,
                tags=ssh_server_tags or [],
                lease_hours=ssh_lease_hours,
                stage_scope="project",
                reason="project creation resource pool",
            )
            apply_lease_pool_to_project(
                Path(__file__).parent.parent.resolve(),
                proj,
                [lease["lease_id"] for lease in leases],
                include_local=True,
            )
            checklist = proj / "state" / "onboarding_checklist.md"
            if checklist.exists():
                with checklist.open("a", encoding="utf-8") as handle:
                    handle.write("\n## Managed SSH Resource Pool\n\n")
                    for lease in leases:
                        handle.write(
                            f"- server_id: `{lease['server_id']}`; "
                            f"lease_id: `{lease['lease_id']}`; "
                            f"workspace_path: `{lease['workspace_path']}`; "
                            f"expires_at: `{lease['expires_at']}`\n"
                        )
            print(f"[SSH] Allocated resource pool with {len(leases)} lease(s)")
            print("      Applied to: config/execution_env.yaml and state/ssh_resource_pool.yaml")
        except SSHRegistryError as exc:
            print(f"[SSH][ERROR] Failed to allocate managed SSH resource pool: {exc}")
            print(f"            Project remains created at: {proj}")
            raise SystemExit(1)

    if ssh_server_id and not (ssh_server_ids or ssh_pool_count):
        from spiral.ssh_registry import SSHRegistryError, allocate_server, apply_lease_to_project

        try:
            lease = allocate_server(
                Path(__file__).parent.parent.resolve(),
                proj,
                server_id=ssh_server_id,
                min_gpu_count=ssh_min_gpu_count,
                min_vram_gb=ssh_min_vram_gb,
                tags=ssh_server_tags or [],
                lease_hours=ssh_lease_hours,
                stage_scope="project",
                reason="project creation",
            )
            apply_lease_to_project(Path(__file__).parent.parent.resolve(), proj, lease["lease_id"])
            checklist = proj / "state" / "onboarding_checklist.md"
            if checklist.exists():
                with checklist.open("a", encoding="utf-8") as handle:
                    handle.write(
                        "\n## Managed SSH Allocation\n\n"
                        f"- server_id: `{lease['server_id']}`\n"
                        f"- lease_id: `{lease['lease_id']}`\n"
                        f"- workspace_path: `{lease['workspace_path']}`\n"
                        f"- expires_at: `{lease['expires_at']}`\n"
                    )
            print(f"[SSH] Allocated server {lease['server_id']} with lease {lease['lease_id']}")
            print(f"      Applied to: config/execution_env.yaml")
        except SSHRegistryError as exc:
            print(f"[SSH][ERROR] Failed to allocate managed SSH server: {exc}")
            print(f"            Project remains created at: {proj}")
            raise SystemExit(1)

    if execution_env:
        print(f"[SETTINGS] Execution environment overrides applied:")
        for k, v in execution_env.items():
            print(f"  {k} = {v}")

    return str(proj)


def cmd_onboarding_done(project_dir: str) -> None:
    """Mark project onboarding as complete and advance to M1S01."""
    proj = Path(project_dir)
    state_file = proj / "state" / "pipeline_state.yaml"
    if not state_file.exists():
        print(f"[ERROR] State file not found: {state_file}")
        sys.exit(1)

    data = _load(state_file)
    current = data.get("current", {})
    if current.get("status") != "onboarding_pending":
        print(f"[WARN] Project status is '{current.get('status')}', not onboarding_pending. Nothing to do.")
        return

    # Basic validation: check execution_env.yaml exists
    env_file = proj / "config" / "execution_env.yaml"
    if not env_file.exists():
        print(f"[WARN] config/execution_env.yaml not found. Please ensure it exists.")

    # Determine execution mode
    exec_mode = "local"
    try:
        env_data = _load(env_file)
        exec_mode = env_data.get("execution", {}).get("mode", "local")
    except Exception:
        pass

    # Validation: SSH config only required when mode == ssh
    missing_fields = []
    if exec_mode == "ssh":
        try:
            env_data = _load(env_file)
            execution = env_data.get("execution", {})
            ssh = env_data.get("execution", {}).get("ssh", {})
            managed = bool(
                execution.get("server_id")
                or execution.get("lease_id")
                or ssh.get("server_id")
                or ssh.get("lease_id")
            )
            if managed:
                from spiral.ssh_registry import validate_project_lease

                ok, message = validate_project_lease(Path(__file__).parent.parent.resolve(), proj)
                if not ok:
                    missing_fields.append(f"managed_ssh_lease ({message})")
            else:
                if not ssh.get("host"):
                    missing_fields.append("ssh.host")
                if not ssh.get("user"):
                    missing_fields.append("ssh.user")
        except Exception:
            pass

    if missing_fields:
        print(f"[ONBOARDING] 以下 SSH 字段为空，请补全后再执行 onboarding-done:")
        for f in missing_fields:
            print(f"  - {f}")
        print(f"  如不使用 SSH，可将 execution_env.yaml 中的 mode 改为 local。")
        sys.exit(1)

    # Update state
    current["status"] = "pending"
    current["stage"] = "M1S01"
    current["module"] = "M1"
    data["current"] = current
    _save(state_file, data)

    # Remove onboarding checklist
    checklist = proj / "state" / "onboarding_checklist.md"
    if checklist.exists():
        checklist.unlink()

    print(f"[ONBOARDING] Project onboarding marked as DONE.")
    print(f"             Mode: {exec_mode}")
    print(f"             Status: pending → M1S01")
    print(f"             You can now start M1 with: python scripts/state_manager.py run-module M1")


def cmd_status(project_dir: str) -> None:
    state_file = Path(project_dir) / "state" / "pipeline_state.yaml"
    if not state_file.exists():
        print(f"[ERROR] State file not found: {state_file}")
        sys.exit(1)
    data = _load(state_file)
    proj = data.get("project", {})
    cur = data.get("current", {})
    venue = proj.get("venue", {})
    print(f"PROJECT: {proj.get('display_name', proj.get('name'))}")
    print(f"TOPIC:   {proj.get('topic')}")
    if proj.get("keywords"):
        print(f"KEYWORDS: {', '.join(proj.get('keywords', []))}")
    if proj.get("entry_mode"):
        print(f"ENTRY:   {proj.get('entry_mode')} ({proj.get('anchor_count', 0)} anchors)")
    if proj.get("entry_brief"):
        print(f"BRIEF:   {proj.get('entry_brief')}")
    print(f"VENUE:   {venue.get('name', 'N/A')} (page limit: {venue.get('page_limit', 'N/A')})")
    print(f"CURRENT: {cur.get('stage')} (Module {cur.get('module')})")
    print(f"STATUS:  {cur.get('status')}")
    print(f"HISTORY: {len(data.get('history', []))} stages")
    print(f"BACKTRACKS: {len(data.get('backtrack_log', []))}")


def cmd_module_status(project_dir: str) -> None:
    state_file = Path(project_dir) / "state" / "pipeline_state.yaml"
    if not state_file.exists():
        print(f"[ERROR] State file not found: {state_file}")
        sys.exit(1)
    data = _load(state_file)
    modules = data.get("modules", {})
    print("\n" + "=" * 50)
    print("  MODULE STATUS")
    print("=" * 50)
    for mod in ALL_MODULES:
        info = modules.get(mod, {})
        status = info.get("status", "unknown")
        last = info.get("last_stage", "-")
        completed = info.get("completed_at", "-")
        if completed and completed != "-":
            completed = completed[:16]
        icon = "✅" if status == "completed" else "⏳" if status == "in_progress" else "⬜"
        print(f"  {icon} {mod}: {status:12s} | last={last} | {completed}")
    print("=" * 50)


def _module_of_stage(stage: str) -> str:
    return MODULE_OF.get(stage, "M1")


def _is_last_stage_of_module(stage: str) -> bool:
    mod = _module_of_stage(stage)
    stages = MODULE_STAGES.get(mod, [])
    return len(stages) > 0 and stages[-1] == stage


def _get_first_stage_of_module(module: str) -> str:
    stages = MODULE_STAGES.get(module, [])
    return stages[0] if stages else "M1S01"


def _check_module_prerequisites(data: dict, target_module: str) -> tuple[bool, str]:
    if target_module not in ALL_MODULES:
        return False, f"Unknown module: {target_module}"
    idx = ALL_MODULES.index(target_module)
    if idx == 0:
        return True, "M1 has no prerequisites"
    prev_module = ALL_MODULES[idx - 1]
    prev_status = data.get("modules", {}).get(prev_module, {}).get("status", "pending")
    if prev_status != "completed":
        return False, (
            f"{prev_module} is not completed (status: {prev_status}). "
            f"Please run {prev_module} first."
        )
    return True, f"{prev_module} completed. Ready to start {target_module}."


def cmd_advance(
    project_dir: str,
    stage: str,
    agent: str,
    output_file: str,
    force: bool = False,
    skip_gates: bool = False,
) -> None:
    state_file = Path(project_dir) / "state" / "pipeline_state.yaml"
    data = _load(state_file)

    current_stage = data.get("current", {}).get("stage")
    if stage != current_stage:
        print(
            f"[ERROR] Cannot advance {stage}: current stage is {current_stage}. "
            f"Use 'backtrack' or 'run-module' to navigate."
        )
        sys.exit(1)

    is_gate = stage in GATE_STAGES
    gate_num = [k for k, v in _GATE_STAGES_MAP.items() if v == stage][0] if is_gate else None
    is_gate_aggregate = _is_gate_aggregate_output(project_dir, stage, output_file)

    if is_gate_aggregate:
        fg_ok, fg_msg = validate_gate_review(project_dir, gate_num, output_file)
    else:
        fg_ok, fg_msg = validate_stage_output(project_dir, stage, output_file)
        if fg_ok:
            fg_ok2, fg_msg2 = check_single_file_principle(project_dir, stage)
            if not fg_ok2:
                fg_ok = False
                fg_msg = fg_msg2

    if not fg_ok:
        print(fg_msg)
        if force:
            print("  [WARN] --force used: bypassing file_guard checks.")
        else:
            print("  [BLOCKED] Fix the issue or use --force.")
            sys.exit(1)
    else:
        print(fg_msg)

    if is_gate_aggregate:
        rubric_ok, rubric_msgs = validate_gate_rubric(project_dir, gate_num, output_file)
        for m in rubric_msgs:
            print(m)
        if not rubric_ok:
            if force:
                print("  [WARN] --force used: bypassing gate rubric checks.")
            else:
                print("  [BLOCKED] Gate rubric validation failed.")
                sys.exit(1)

    # M1S02: survey memory state consistency check + source log validation + sync
    if stage == "M1S02":
        # --- Pre-check: survey memory round status must match expected stage ---
        rounds_ok, round_msgs = _check_m1s02_rounds(Path(project_dir))
        for m in round_msgs:
            print(m)
        if not rounds_ok:
            if force:
                print("  [WARN] --force used: bypassing M1S02 3-Round checks.")
            else:
                print("  [BLOCKED] M1S02 round/review validation failed.")
                sys.exit(1)

        sl_ok, sl_msgs = validate_source_log(project_dir)
        for m in sl_msgs:
            print(m)
        if not sl_ok:
            if force:
                print("  [WARN] --force used: bypassing source_log checks.")
            else:
                print("  [BLOCKED] Source log validation failed.")
                sys.exit(1)
        # Sync source log into survey memory (ensures project-level tracking)
        _sync_source_log_to_survey_memory(project_dir)

    # M3S04 decision enforcement
    if stage == "M3S04":
        s34_path = Path(project_dir) / "knowledge" / "M3" / "M3S04_result_validation.md"
        if s34_path.exists():
            text = s34_path.read_text(encoding="utf-8")
            decision = extract_m3s04_decision(text)
            if decision in {"FIX", "BACKTRACK"}:
                missing_fields = missing_m3_repair_fields(text)
                has_guidance = "回溯修改方向" in text
                if missing_fields or not has_guidance:
                    print("[BLOCKED] M3S04 decision is FIX or BACKTRACK, and repair guidance is incomplete.")
                    if not has_guidance:
                        print("  Missing section: 回溯修改方向")
                    if missing_fields:
                        print(f"  Missing fields: {', '.join(missing_fields)}")
                else:
                    print("[BLOCKED] M3S04 decision is FIX or BACKTRACK.")
                    print("  Repair guidance is present; execute the requested backtrack before advancing.")
                sys.exit(1)
            if decision != "KEEP":
                print("[BLOCKED] M3S04 missing explicit KEEP decision.")
                sys.exit(1)

    if not skip_gates and not is_gate_aggregate:
        sg_ok, sg_msgs = check_stage(project_dir, stage)
        for m in sg_msgs:
            print(m)
        if not sg_ok:
            stage_review_block = stage in {
                "M2S01", "M2S02", "M2S03", "M2S04",
                "M2S05", "M2S06",
                "M3S01", "M3S02", "M3S03",
                "M4S01", "M4S02", "M4S03",
                "M5S01", "M5S02", "M5S03", "M5S04",
                "M5S05", "M5S06", "M5S07", "M5S08", "M5S09",
                "M6S01", "M6S02", "M6S03", "M6S04",
                "M6S05", "M6S06",
            } and any(
                m.lower().startswith("[fail]")
                and ("stage review" in m.lower() or "verdict" in m.lower())
                for m in sg_msgs
            )
            if stage_review_block:
                from spiral.conductor import Conductor

                conductor = Conductor(Path(project_dir))
                review_result = conductor.handle_stage_review_verdict(stage)
                action = review_result.get("action")
                if action == "RE_EXECUTE":
                    print(f"[STAGE REVIEW] {stage}: non-PASS verdict processed.")
                    print(f"  Action:       RE_EXECUTE")
                    print(f"  Target stage: {review_result.get('target_stage', stage)}")
                    print(f"  Reason:       {review_result.get('reason', '')}")
                    advice = review_result.get("advice", {})
                    if advice:
                        print(f"  Required fix: {advice.get('required_fix', '')}")
                        print(f"  Success:      {advice.get('success_criteria', '')}")
                        print(f"  Rebuild mode: {advice.get('rebuild_mode', '')}")
                        print(f"  Rerun scope:  {advice.get('rerun_scope', '')}")
                    stale = review_result.get("stale_stages") or []
                    print(f"  Stale stages: {', '.join(stale) or 'none'}")
                    target_stage = review_result.get("target_stage", stage)
                    print(f"  Dispatch:     python scripts/state_manager.py dispatch stage {target_stage} --write")
                    return
                if action == "HALT":
                    print(f"  [BLOCKED] Stage review requested HALT: {review_result.get('reason', '')}")
                    sys.exit(1)
                print(f"  [BLOCKED] Stage review cannot be processed: {review_result.get('reason', '')}")
                print(f"  Dispatch reviews with: python scripts/state_manager.py dispatch reviews {stage} --write")
                if force:
                    print("  [BLOCKED] M2/M3/M4/M5/M6 stage review cannot be bypassed with --force.")
                sys.exit(1)
            if force:
                print("  [WARN] --force used: bypassing stage_gate checks.")
            else:
                print("  [BLOCKED] Stage quality checks failed.")
                sys.exit(1)

    history_entry = {
        "stage": stage,
        "agent": agent,
        "completed_at": datetime.now().isoformat(),
        "output": output_file,
    }
    data["history"].append(history_entry)

    if _clear_stale_stage(data, stage):
        print(f"[INFO] Cleared stale marker for {stage} after successful re-execution.")

    if is_gate and not is_gate_aggregate:
        data["current"]["stage"] = stage
        data["current"]["module"] = MODULE_OF.get(stage, data.get("current", {}).get("module", "M1"))
        data["current"]["status"] = "waiting_gate"
        _save(state_file, data)
        print(f"[STAGE COMPLETE] {stage} → waiting_gate ({gate_num})")
        print(f"[NEXT] Run Gate {gate_num} reviewers and advance with knowledge/reviews/{gate_num}_aggregate.md")
        return

    ALL_STAGES = [s for stages in MODULE_STAGES.values() for s in stages]
    idx = ALL_STAGES.index(stage)
    next_stage = ALL_STAGES[idx + 1] if idx + 1 < len(ALL_STAGES) else None

    if next_stage:
        data["current"]["stage"] = next_stage
        data["current"]["module"] = MODULE_OF.get(next_stage, "M5")

        if stage in GATE_STAGES:
            completed_module = MODULE_OF.get(stage, "M1")
            if "modules" not in data:
                data["modules"] = {}
            data["modules"][completed_module] = {
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "last_stage": stage,
            }
            data["current"]["status"] = "module_completed"
            _save(state_file, data)
            print(f"[ADVANCED] {stage} → {next_stage}")
            print(f"[MODULE COMPLETE] {completed_module} finished at {stage}.")
        else:
            data["current"]["status"] = "in_progress"
            _save(state_file, data)
            print(f"[ADVANCED] {stage} → {next_stage}")
    else:
        completed_module = MODULE_OF.get(stage, "M1")
        data["current"]["status"] = "completed"
        data.setdefault("modules", {})
        data["modules"][completed_module] = {
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "last_stage": stage,
        }
        _save(state_file, data)
        print(f"[COMPLETED] {stage} → ALL DONE")
        print(f"[MODULE COMPLETE] {completed_module} finished at {stage}.")


def cmd_human_review(
    project_dir: str,
    stage: str,
    opinion: str,
    verdict: str = "revise",
) -> None:
    state_file = Path(project_dir) / "state" / "pipeline_state.yaml"
    if not state_file.exists():
        print(f"[ERROR] State file not found: {state_file}")
        sys.exit(1)

    data = _load(state_file)
    proj_name = data.get("project", {}).get("display_name", "Project")

    review_entry = {
        "stage": stage,
        "opinion": opinion,
        "verdict": verdict,
        "reviewer": "human",
        "timestamp": datetime.now().isoformat(),
    }
    data.setdefault("human_reviews", []).append(review_entry)

    review_dir = Path(project_dir) / "knowledge" / "reviews"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_file = review_dir / f"human_{stage}_review.md"
    review_file.write_text(
        f"# Human Review — {stage}\n\n"
        f"**Project**: {proj_name}\n"
        f"**Stage**: {stage}\n"
        f"**Verdict**: {verdict.upper()}\n"
        f"**Time**: {review_entry['timestamp']}\n\n"
        f"## Opinion\n\n{opinion}\n\n"
        f"---\n"
        f"*This review was submitted by the user.*\n",
        encoding="utf-8",
    )

    if verdict == "pass":
        data["current"]["status"] = "in_progress"
        _save(state_file, data)
        print(f"[HUMAN REVIEW] {stage}: PASS")

    elif verdict in ("revise", "backtrack"):
        # 统一通过 Conductor.backtrack() 处理状态变更，
        # 禁止在 state_manager 中直接重复实现 backtrack 逻辑。
        current_stage = data["current"]["stage"]
        target_module = MODULE_OF.get(stage, "M1")
        label = verdict.upper()

        # 先保存 human review 记录
        _save(state_file, data)

        from spiral.conductor import Conductor

        conductor = Conductor(Path(project_dir))
        result = conductor.backtrack(
            from_stage=current_stage,
            to_stage=stage,
            reason=f"Human review {label}: {opinion[:100]}",
            direction=opinion[:200],
        )
        if result.get("ok"):
            print(f"[HUMAN REVIEW] {stage}: {label}")
            print(f"  Backtracked from {current_stage} to {stage} ({target_module}).")
            print(f"  Spiral count: {result['spiral_count']}")
            stale = result.get("stale_stages", [])
            if stale:
                print(f"  Stale stages: {', '.join(stale)}")
            advice = result.get("advice", {})
            if advice:
                print(f"  Required fix: {advice.get('required_fix', '')}")
                print(f"  Rebuild mode: {advice.get('rebuild_mode', 'full_regenerate')}")
                print(f"  Success criteria: {advice.get('success_criteria', '')}")
            print(
                f"\n  [NEXT] Conductor 必须调用对应 subagent 重新执行 {stage}，"
                f"主 agent 不得直接修改 stage 内容。"
            )
            print(f"  [DISPATCH] python scripts/state_manager.py dispatch stage {stage} --write")
        else:
            print(f"[ERROR] {label} failed: {result.get('error')}")
            sys.exit(1)

    else:
        print(f"[ERROR] Unknown verdict: {verdict}. Use: pass | revise | backtrack")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Auto-run commands
# ---------------------------------------------------------------------------

def cmd_auto_stage(project_dir: str, stage: str) -> None:
    state_file = Path(project_dir) / "state" / "pipeline_state.yaml"
    if not state_file.exists():
        print(f"[ERROR] State file not found: {state_file}")
        sys.exit(1)

    data = _load(state_file)
    cur_stage = data.get("current", {}).get("stage", "M1S01")
    cur_status = data.get("current", {}).get("status", "initialized")

    if stage != cur_stage:
        print(f"[WARN] Requested stage {stage} but current stage is {cur_stage}.")

    agent = AGENT_FOR_STAGE.get(stage, "conductor")
    canonical_md = get_canonical_output_path(project_dir, stage)
    is_gate = stage in GATE_STAGES
    gate_num = [k for k, v in _GATE_STAGES_MAP.items() if v == stage][0] if is_gate else None
    try:
        from spiral.conductor import Conductor
        conductor = Conductor(Path(project_dir))
        stage_plan = conductor.run_stage(stage)
        stage_checkers = conductor.get_stage_checkers(stage)
        stage_checker_docs = [
            str(conductor.get_checker_md_path(checker)) for checker in stage_checkers
        ]
        stage_review_outputs = conductor.get_stage_review_outputs(stage)
    except Exception:
        stage_plan = {}
        stage_checkers = []
        stage_checker_docs = []
        stage_review_outputs = {}
    phase = stage_plan.get("phase") or ("gate" if is_gate and cur_status == "waiting_gate" else "stage")
    output_display = (
        Path(project_dir) / "knowledge" / "reviews" / f"{gate_num}_aggregate.md"
        if phase == "gate" and gate_num
        else canonical_md
    )

    print(f"\n{'='*60}")
    print(f"  AUTO-STAGE PLAN: {stage}")
    print(f"{'='*60}")
    print(f"  Project:     {project_dir}")
    print(f"  Stage:       {stage}")
    print(f"  Agent:       {agent}")
    print(f"  Is Gate:     {is_gate}")
    print(f"  Phase:       {phase}")
    print(f"  Output:      {output_display}")
    if stage_checkers:
        print(f"  Stage Review: {', '.join(stage_checkers)}")
        for checker, checker_doc in zip(stage_checkers, stage_checker_docs):
            review_out = stage_review_outputs.get(checker)
            if review_out:
                print(f"    - {checker}: {checker_doc} -> {review_out}")
            else:
                print(f"    - {checker}: {checker_doc}")
    backtrack_advice = stage_plan.get("backtrack_advice", {})
    if backtrack_advice:
        print(f"  Backtrack mode: {backtrack_advice.get('rebuild_mode', 'full_regenerate')}")
        rerun_scope = backtrack_advice.get("rerun_scope")
        if rerun_scope:
            print(f"  Backtrack scope: {rerun_scope}")
    print(f"\n  Conductor Action:")
    if phase == "gate":
        print(f"    1. Collect all Module outputs")
        print(f"    2. Call Critic Team for {gate_num}")
        print(f"    3. Aggregate reviews into knowledge/reviews/{gate_num}_aggregate.md")
        print(f"    4. Process verdict: PASS / REVISE / BACKTRACK / HALT")
        print(f"    Dispatch packets: python scripts/state_manager.py dispatch gate {gate_num} --write")
    else:
        print(f"    1. Read AGENT.md for role='{agent}'")
        print(f"    2. Read MD Protocol")
        print(f"    3. Gather input documents")
        print(f"    4. CREATE sub-Agent (role={agent}, stage={stage})")
        print(f"       Dispatch packet: python scripts/state_manager.py dispatch stage {stage} --write")
        print(f"    5. WAIT for completion")
        print(f"    6. VERIFY output: {canonical_md}")
        if stage_checkers:
            print(f"    7. CALL stage review agent(s): {', '.join(stage_checkers)}")
            print(f"       Dispatch packets: python scripts/state_manager.py dispatch reviews {stage} --write")
            print(f"       - Each reviewer must read its AGENT.md and write the required review file")
            print(f"       - Advance only after all stage review files exist and verdict=PASS")
            print(f"    8. ADVANCE: python scripts/state_manager.py advance {stage} {agent} {canonical_md}")
            if is_gate and gate_num:
                print(f"    9. On success, status becomes waiting_gate; then run Gate {gate_num}")
        else:
            print(f"    7. ADVANCE: python scripts/state_manager.py advance {stage} {agent} {canonical_md}")
            if is_gate and gate_num:
                print(f"    8. On success, status becomes waiting_gate; then run Gate {gate_num}")
    print(f"{'='*60}\n")


def cmd_auto_module(project_dir: str, module: str) -> None:
    state_file = Path(project_dir) / "state" / "pipeline_state.yaml"
    if not state_file.exists():
        print(f"[ERROR] State file not found: {state_file}")
        sys.exit(1)

    data = _load(state_file)
    stages = MODULE_STAGES.get(module, [])
    if not stages:
        print(f"[ERROR] Unknown module: {module}")
        sys.exit(1)

    ok, msg = _check_module_prerequisites(data, module)
    if not ok:
        print(f"[BLOCKED] {msg}")
        sys.exit(1)
    try:
        from spiral.conductor import Conductor
        conductor = Conductor(Path(project_dir))
    except Exception:
        conductor = None

    print(f"\n{'='*60}")
    print(f"  AUTO-MODULE PLAN: {module}")
    print(f"{'='*60}")
    print(f"  Project:     {project_dir}")
    print(f"  Stages:      {' → '.join(stages)}")
    print(f"  Gate:        G{module[1:]}")
    print(f"\n  Execution Order:")
    for st in stages:
        agent = AGENT_FOR_STAGE.get(st, "conductor")
        out = get_canonical_output_path(project_dir, st)
        checkers = conductor.get_stage_checkers(st) if conductor else []
        if conductor and checkers:
            checker_docs = [conductor.get_checker_md_path(checker) for checker in checkers]
            review_outputs = conductor.get_stage_review_outputs(st)
            review_items = []
            for checker, checker_doc in zip(checkers, checker_docs):
                rev_out = review_outputs.get(checker)
                review_items.append(
                    f"{checker}@{checker_doc}:{rev_out if rev_out else 'n/a'}"
                )
            review = f" | review: {', '.join(review_items)}"
        else:
            review = f" | review: {', '.join(checkers)}" if checkers else ""
        print(f"    {st} [{agent}] → {out.name}{review}")
    print(f"{'='*60}\n")


def cmd_auto_backtrack(
    project_dir: str,
    from_stage: str,
    to_stage: str,
    reason: str,
    direction: str = "",
) -> None:
    state_file = Path(project_dir) / "state" / "pipeline_state.yaml"
    if not state_file.exists():
        print(f"[ERROR] State file not found: {state_file}")
        sys.exit(1)

    data = _load(state_file)
    ALL_STAGES_FLAT = [s for stages in MODULE_STAGES.values() for s in stages]

    try:
        to_idx = ALL_STAGES_FLAT.index(to_stage)
        from_idx = ALL_STAGES_FLAT.index(from_stage)
    except ValueError:
        print(f"[ERROR] Invalid stage(s): {from_stage} / {to_stage}")
        sys.exit(1)

    if to_idx > from_idx:
        print(f"[ERROR] Backtrack target {to_stage} must not be after {from_stage}")
        sys.exit(1)

    re_exec = [to_stage] + ALL_STAGES_FLAT[to_idx + 1 : from_idx + 1]
    target_module = MODULE_OF.get(to_stage, "M1")
    from_module = MODULE_OF.get(from_stage, target_module)
    gates = []
    try:
        for idx in range(ALL_MODULES.index(target_module), ALL_MODULES.index(from_module) + 1):
            gates.append(f"G{ALL_MODULES[idx][1:]}")
    except ValueError:
        pass

    action_label = "AUTO-REVISE PLAN" if from_stage == to_stage else "AUTO-BACKTRACK PLAN"
    print(f"\n{'='*60}")
    print(f"  {action_label}: {from_stage} → {to_stage}")
    print(f"{'='*60}")
    print(f"  Reason:      {reason}")
    print(f"  Direction:   {direction or '(not specified)'}")
    if direction:
        print(f"  Repair hint: {direction}")
    print(f"  Re-execute:  {' → '.join(re_exec)}")
    rebuild_mode = _infer_rebuild_mode(reason, direction, direction or reason)
    print(f"  Rebuild mode: {rebuild_mode}")
    print(f"                 incremental_replay for local fixes; full_regenerate when the direction shifts")
    print(f"  Rerun scope: start at {to_stage}, then continue through downstream stale stages")
    print(f"  Gates:       {', '.join(gates) if gates else 'none'}")
    print(f"  Note:        unrelated stages stay untouched unless they become downstream stale")
    print(f"{'='*60}\n")


def cmd_auto_run(project_dir: str) -> None:
    state_file = Path(project_dir) / "state" / "pipeline_state.yaml"
    if not state_file.exists():
        print(f"[ERROR] State file not found: {state_file}")
        sys.exit(1)

    data = _load(state_file)
    cur_stage = data.get("current", {}).get("stage", "M1S01")
    cur_status = data.get("current", {}).get("status", "initialized")
    auto_advance = data.get("settings", {}).get("auto_advance_modules", False)
    ALL_STAGES_FLAT = [s for stages in MODULE_STAGES.values() for s in stages]

    try:
        start_idx = ALL_STAGES_FLAT.index(cur_stage)
    except ValueError:
        start_idx = 0

    remaining = ALL_STAGES_FLAT[start_idx:]

    print(f"\n{'='*60}")
    print(f"  AUTO-RUN PLAN")
    print(f"{'='*60}")
    print(f"  Project:     {project_dir}")
    print(f"  Current:     {cur_stage} (status: {cur_status})")
    print(f"  Remaining:   {len(remaining)} stage(s)")
    print(f"  Stages:      {' → '.join(remaining[:10])}{'...' if len(remaining) > 10 else ''}")
    stale = data.get("stale_stages", [])
    if stale:
        print(f"  Stale:       {' → '.join(stale[:10])}{'...' if len(stale) > 10 else ''}")
    print(f"  Auto-advance: {'ON' if auto_advance else 'OFF'}")
    print(f"\n  Conductor Action:")
    print(f"    WHILE current_stage != completed:")
    print(f"        IF status == waiting_gate:")
    print(f"            TRIGGER Gate (Critic Team)")
    print(f"            PROCESS verdict")
    print(f"        ELIF status == module_completed AND auto_advance:")
    print(f"            AUTO-ADVANCE to next module first stage")
    print(f"        ELSE:")
    print(f"            CALL auto-stage current_stage")
    print(f"            WAIT completion + ADVANCE")
    print(f"        END")
    print(f"    END")
    print(f"\n  User Intervention Points:")
    if auto_advance:
        print(f"    [Auto-advance ON] Module transitions are automatic.")
        print(f"    - Gate HALT")
        print(f"    - Spiral limit reached (≥10 backtracks in same module)")
        print(f"    - stage_gate / file_guard failure (unless --force)")
    else:
        print(f"    - Module completion (requires explicit 'run-module' or enable auto-advance)")
        print(f"    - Gate HALT")
        print(f"    - Spiral limit reached (≥10 backtracks in same module)")
        print(f"    - stage_gate / file_guard failure (unless --force)")
    print(f"{'='*60}\n")


def cmd_run_module(project_dir: str, module: str) -> None:
    state_file = Path(project_dir) / "state" / "pipeline_state.yaml"
    if not state_file.exists():
        print(f"[ERROR] State file not found: {state_file}")
        sys.exit(1)
    data = _load(state_file)

    ok, msg = _check_module_prerequisites(data, module)
    if not ok:
        print(f"[BLOCKED] Cannot start {module}: {msg}")
        sys.exit(1)

    first_stage = _get_first_stage_of_module(module)
    data["current"]["module"] = module
    data["current"]["stage"] = first_stage
    data["current"]["status"] = "in_progress"

    if "modules" not in data:
        data["modules"] = {}
    data["modules"][module] = {
        "status": "in_progress",
        "completed_at": None,
        "last_stage": None,
    }
    _save(state_file, data)
    print(f"[RUN MODULE] {module} starting at {first_stage}")


def cmd_list_projects() -> None:
    projects_root = PROJECTS_ROOT
    if not projects_root.exists():
        print(f"[INFO] No projects directory found at {projects_root}")
        return

    projects = []
    for p in sorted(projects_root.iterdir()):
        if p.is_dir() and (p / "state" / "pipeline_state.yaml").exists():
            try:
                data = _load(p / "state" / "pipeline_state.yaml")
                cur = data.get("current", {})
                projects.append({
                    "path": p,
                    "name": data.get("project", {}).get("display_name", p.name),
                    "stage": cur.get("stage", "?"),
                    "module": cur.get("module", "?"),
                    "status": cur.get("status", "?"),
                })
            except Exception:
                continue

    current = _get_current_project()
    print(f"\n{'='*70}")
    print(f"  PROJECTS in {projects_root}")
    print(f"{'='*70}")
    if not projects:
        print("  No projects found.")
    else:
        for p in projects:
            marker = " 👈" if current and p["path"] == current else ""
            print(f"  {p['name']}{marker}")
            print(f"    {p['stage']} ({p['module']}) — {p['status']}")
            print(f"    {p['path']}")
    print(f"{'='*70}\n")


def cmd_use(project_dir: str) -> None:
    path = Path(project_dir)
    if not (path / "state" / "pipeline_state.yaml").exists():
        print(f"[ERROR] Not a valid project: {path}")
        sys.exit(1)
    _set_current_project(str(path))


def cmd_list_venues() -> None:
    registry = _load_venue_registry()
    venues = registry.get("venues", {})
    default_venue = registry.get("default_venue", "arxiv")
    print(f"\n{'='*60}")
    print("  VENUES")
    print(f"{'='*60}")
    for vid, vinfo in venues.items():
        marker = " [default]" if vid == default_venue else ""
        print(f"  {vid}{marker}")
        print(f"    Name: {vinfo.get('name', vid)}")
        print(f"    Page Limit: {vinfo.get('page_limit', 'N/A')}")
        print(f"    Full Name: {vinfo.get('full_name', '')}")
    print(f"{'='*60}\n")


def _get_public_db():
    """Return the framework-wide PublicLiteratureDB instance (initialized)."""
    from spiral.public_db.config import DBConfig
    from spiral.public_db.manager import PublicLiteratureDB

    cfg = DBConfig.default()
    db = PublicLiteratureDB(cfg)
    db.init_if_needed()
    return db


def cmd_public_db_status() -> None:
    from spiral.public_db.config import DBConfig

    cfg = DBConfig.default()
    db_path = Path(cfg.db_path)

    print(f"\n{'='*60}")
    print("  PUBLIC LITERATURE DATABASE")
    print(f"{'='*60}")
    print(f"  Enabled:     {cfg.enabled}")
    print(f"  DB Path:     {db_path}")
    print(f"  Exists:      {db_path.exists()}")

    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        print(f"  Size:        {size_mb:.2f} MB")
        try:
            db = _get_public_db()
            count = db.count_papers()
            tags = len(db.list_tags())
            print(f"  Papers:      {count}")
            print(f"  Tags:        {tags}")
        except Exception as exc:
            print(f"  [WARN] Could not read stats: {exc}")
    else:
        print("  Status:      Not initialized (will auto-create on first use)")
    print(f"{'='*60}\n")


def cmd_public_db_init() -> None:
    db = _get_public_db()
    print(f"[PUBLIC DB] Initialized at {db.config.db_path}")
    print(f"            Papers: {db.count_papers()}")


def cmd_public_db_stats() -> None:
    db = _get_public_db()
    print(f"\n{'='*60}")
    print("  PUBLIC DB STATISTICS")
    print(f"{'='*60}")
    print(f"  Total papers:    {db.count_papers()}")

    tag_stats = db.get_tag_statistics()
    if tag_stats:
        print(f"\n  Top tags by paper count:")
        for stat in tag_stats[:10]:
            print(f"    {stat['tag_id']:30s}  {stat['paper_count']:4d} papers  (avg cred: {stat['avg_credibility']})")
    else:
        print("  No tags defined yet.")

    top = db.get_top_papers(limit=5)
    if top:
        print(f"\n  Top papers (credibility × survey_count):")
        for p in top:
            print(f"    {p.paper_id:40s}  score={p.credibility_score * p.survey_count}")
    print(f"{'='*60}\n")


def cmd_public_db_import_project(project_dir: str) -> None:
    source_log = Path(project_dir) / "knowledge" / "M1" / "M1_source_log.yaml"
    if not source_log.exists():
        print(f"[ERROR] Source log not found: {source_log}")
        sys.exit(1)

    db = _get_public_db()
    from spiral.public_db.importer import ProjectImporter

    importer = ProjectImporter(db)
    project_name = Path(project_dir).name
    result = importer.import_from_source_log(source_log, project_name)
    print(f"[PUBLIC DB] Imported from {project_name}")
    print(f"            New: {result['imported']}  Merged: {result['merged']}  Total sources: {result['total_sources']}")


def cmd_public_db_list_papers(tag: str | None = None, limit: int = 20) -> None:
    db = _get_public_db()
    if tag:
        result = db.query(domain_tags=[tag], limit=limit)
        print(f"\n  Papers tagged with '{tag}' ({result.total_count} total):")
    else:
        result = db.query(limit=limit)
        print(f"\n  All papers ({result.total_count} total, showing top {limit}):")

    if not result.papers:
        print("  (none)")
        return

    print(f"\n  {'ID':<22s} {'Year':<6s} {'Cred':<5s} {'Title'}")
    print(f"  {'-'*70}")
    for p in result.papers:
        year = str(p.year) if p.year else "N/A"
        print(f"  {p.paper_id:<22s} {year:<6s} {p.credibility_score:<5d} {p.title[:45]}")
    print()


def cmd_public_db_search(query: str, limit: int = 10) -> None:
    db = _get_public_db()
    keywords = query.split()
    result = db.query(keywords=keywords, limit=limit)
    print(f"\n  Search: '{query}' — {result.total_count} hits ({'cached' if result.from_cache else 'live'}):")
    if not result.papers:
        print("  (none)")
        return

    print(f"\n  {'ID':<22s} {'Year':<6s} {'Title'}")
    print(f"  {'-'*60}")
    for p in result.papers:
        year = str(p.year) if p.year else "N/A"
        print(f"  {p.paper_id:<22s} {year:<6s} {p.title[:50]}")
    print(f"  Query time: {result.query_time_ms:.1f}ms")
    print()


def cmd_public_db_show_paper(paper_id: str) -> None:
    db = _get_public_db()
    p = db.get_paper(paper_id)
    if not p:
        print(f"[ERROR] Paper not found: {paper_id}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  {p.title}")
    print(f"{'='*60}")
    print(f"  ID:          {p.paper_id}")
    print(f"  Authors:     {', '.join(p.authors) if p.authors else 'N/A'}")
    print(f"  Venue:       {p.venue or 'N/A'}")
    print(f"  Year:        {p.year or 'N/A'}")
    print(f"  URL:         {p.url or 'N/A'}")
    print(f"  Type:        {p.type}")
    print(f"  Credibility: {p.credibility_score}/5")
    print(f"  Verification:{p.verification_status}")
    print(f"  Code:        {p.code_availability} {f'({p.code_url})' if p.code_url else ''}")
    if p.abstract:
        print(f"\n  Abstract:\n    {p.abstract[:300]}{'...' if len(p.abstract)>300 else ''}")
    if p.limitations_noted:
        print(f"\n  Limitations:")
        for lim in p.limitations_noted:
            print(f"    • {lim.limitation}")
    tags = db.get_paper_tags(p.paper_id)
    if tags:
        print(f"\n  Tags: {', '.join(t.tag_id for t in tags)}")
    print(f"{'='*60}\n")


def cmd_public_db_list_tags() -> None:
    db = _get_public_db()
    tags = db.list_tags()
    stats = {s["tag_id"]: s for s in db.get_tag_statistics()}

    print(f"\n  {'Tag ID':<30s} {'Name':<25s} {'Papers':<8s} {'Avg Cred'}")
    print(f"  {'-'*70}")
    for t in tags:
        stat = stats.get(t.tag_id, {})
        avg_cred = stat.get('avg_credibility', '-')
        avg_cred_str = f"{avg_cred:.2f}" if isinstance(avg_cred, (int, float)) else str(avg_cred)
        print(f"  {t.tag_id:<30s} {t.name[:24]:<25s} {stat.get('paper_count', 0):<8d} {avg_cred_str:<8s}")
    print()


def cmd_set_venue(project_dir: str, venue_id: str) -> None:
    state_file = Path(project_dir) / "state" / "pipeline_state.yaml"
    if not state_file.exists():
        print(f"[ERROR] State file not found: {state_file}")
        sys.exit(1)

    venue_config = _get_venue_config(venue_id)
    if not venue_config:
        print(f"[ERROR] Unknown venue: {venue_id}")
        sys.exit(1)

    from spiral.state import PipelineState
    state = PipelineState(Path(project_dir))
    state.set_venue(venue_id, venue_config)
    print(f"[VENUE] Set to: {venue_config.get('name', venue_id)}")


def cmd_set_auto_advance(project_dir: str, enabled: bool) -> None:
    state_file = Path(project_dir) / "state" / "pipeline_state.yaml"
    if not state_file.exists():
        print(f"[ERROR] State file not found: {state_file}")
        sys.exit(1)

    from spiral.state import PipelineState
    state = PipelineState(Path(project_dir))
    state.set_auto_advance(enabled)
    status = "enabled" if enabled else "disabled"
    print(f"[SETTINGS] Auto-advance modules: {status}")
    if enabled:
        print("  When a module completes, Conductor will automatically start the next module.")
    else:
        print("  When a module completes, Conductor will wait for explicit user instruction.")


def cmd_dispatch(
    project_dir: str,
    scope: str = "next",
    target: str = "",
    *,
    fmt: str = "markdown",
    write: bool = False,
    out_dir: str = "",
) -> None:
    """Generate structured subagent dispatch packets.

    Dispatch packets are the script-level bridge between Conductor planning and
    actual subagent delegation.  They make the required agent role, input paths,
    output path, and main-agent boundaries explicit.
    """
    from spiral.dispatch import (
        build_packets,
        packet_to_markdown,
        packets_to_json,
        render_compact_launch_prompt,
        write_packets,
    )

    packets = build_packets(project_dir, scope, target or None)
    if write:
        paths = write_packets(project_dir, packets, fmt=fmt, out_dir=out_dir or None)
        print("[DISPATCH] Wrote subagent packet(s):")
        for packet, path in zip(packets, paths):
            try:
                display_path = path.resolve().relative_to(Path.cwd().resolve())
            except ValueError:
                display_path = Path(os.path.relpath(path.resolve(), Path.cwd().resolve()))
            print(f"  {display_path}")
            print(f"  Context preflight: python scripts/context_budget.py --packet {display_path}")
            print(f"  Launch prompt extractor: python scripts/subagent_launch_prompt.py --packet {display_path}")
            print("  Compact subagent launch prompt:")
            for line in render_compact_launch_prompt(packet, display_path).rstrip().splitlines():
                print(f"    {line}")
        print("  Pass only the compact launch prompt/packet path to the matching subagent.")
        print("  Do not paste the parent conversation or upstream document contents into the subagent prompt.")
        print("  Main agent must not write stage/review content directly.")
        return

    if fmt == "json":
        print(packets_to_json(packets))
    else:
        for idx, packet in enumerate(packets):
            if idx:
                print("\n---\n")
            print(packet_to_markdown(packet))


def cmd_backtrack(
    project_dir: str,
    from_stage: str,
    to_stage: str,
    reason: str,
    direction: str = "",
    *,
    required_fix: str = "",
    success_criteria: str = "",
    rebuild_mode: str = "",
    rerun_scope: str = "",
    evidence_paths: Optional[list[str]] = None,
    handoff_updates: Optional[list[str]] = None,
    review_file: Optional[str] = None,
) -> None:
    from spiral.conductor import Conductor
    from spiral.verdict_parser import VerdictParser

    conductor = Conductor(Path(project_dir))

    # If a structured review file is provided, parse it via VerdictParser
    # to ensure human backtracks follow the same structured advice protocol
    # as automated stage reviews.
    advice: Optional[dict] = None
    if review_file:
        review_path = Path(review_file)
        if not review_path.exists():
            print(f"[ERROR] Review file not found: {review_path}")
            sys.exit(1)
        parsed = VerdictParser.parse_stage_review("human", review_path)
        ok, err = parsed.is_valid
        if not ok and parsed.verdict not in ("HALT", None):
            print(f"[ERROR] Review file invalid: {err}")
            print(f"  Missing fields: {', '.join(parsed.missing_fields)}")
            sys.exit(1)
        # Merge parsed fields with explicit CLI overrides (CLI takes precedence)
        advice = {
            "target_stage": to_stage,
            "blocking_reason": reason,
            "required_fix": required_fix or parsed.required_fix or direction or reason,
            "success_criteria": success_criteria or parsed.success_criteria or f"{to_stage} passes its stage review and downstream stale stages can be re-run cleanly",
            "rebuild_mode": rebuild_mode or parsed.rebuild_mode or "full_regenerate",
            "rerun_scope": rerun_scope or parsed.rerun_scope or f"Re-execute {to_stage} and downstream stale stages",
            "evidence_paths": evidence_paths if evidence_paths is not None else parsed.evidence_paths,
            "handoff_updates": handoff_updates if handoff_updates is not None else parsed.handoff_updates,
        }
    elif any([required_fix, success_criteria, rebuild_mode, rerun_scope, evidence_paths, handoff_updates]):
        # Structured advice provided via CLI flags
        advice = {
            "target_stage": to_stage,
            "blocking_reason": reason,
            "required_fix": required_fix or direction or reason,
            "success_criteria": success_criteria or f"{to_stage} passes its stage review and downstream stale stages can be re-run cleanly",
            "rebuild_mode": rebuild_mode or "full_regenerate",
            "rerun_scope": rerun_scope or f"Re-execute {to_stage} and downstream stale stages",
            "evidence_paths": evidence_paths or [],
            "handoff_updates": handoff_updates or [],
        }

    if advice is None:
        print("  [WARN] Human backtrack without structured repair advice. "
              "Consider using --review-file or --required-fix / --success-criteria / --rebuild-mode flags.")

    result = conductor.backtrack(from_stage, to_stage, reason, direction, advice=advice)
    if result["ok"]:
        label = "REVISE" if from_stage == to_stage else "BACKTRACK"
        print(f"[{label}] {from_stage} → {to_stage}")
        print(f"  Reason: {reason}")
        advice = result.get("advice", {})
        if advice:
            print(f"  Target stage: {advice.get('target_stage', to_stage)}")
            print(f"  Blocking reason: {advice.get('blocking_reason', reason)}")
            print(f"  Required fix: {advice.get('required_fix', direction or reason)}")
            print(f"  Success criteria: {advice.get('success_criteria', '')}")
            print(f"  Rebuild mode: {advice.get('rebuild_mode', 'full_regenerate')}")
            evidence_paths = advice.get("evidence_paths") or []
            if evidence_paths:
                print(f"  Evidence paths: {', '.join(evidence_paths)}")
            rerun_scope = advice.get("rerun_scope")
            if rerun_scope:
                print(f"  Rerun scope: {rerun_scope}")
            handoff_updates = advice.get("handoff_updates") or []
            if handoff_updates:
                print(f"  Handoff updates: {', '.join(handoff_updates)}")
        print(f"  Spiral count: {result['spiral_count']}")
        print(f"  Stale stages: {', '.join(result['stale_stages']) or 'none'}")
        print(f"  Dispatch: python scripts/state_manager.py dispatch stage {to_stage} --write")
    else:
        print(f"[ERROR] {result['error']}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _print_help() -> None:
    print("AutoPaper2 State Manager")
    print("Commands: create, status, module-status, advance, human-review,")
    print("          auto-stage, auto-module, auto-backtrack, auto-run,")
    print("          run-module, list/list-projects, use, list-venues, set-venue,")
    print("          set-auto-advance, dispatch, backtrack, public-db")
    print("Create usage: create <topic> <display_name> [venue]")
    print("  [--auto-advance] [--env-mode local|ssh]")
    print("  [--ssh-host HOST] [--ssh-user USER] [--ssh-port PORT]")
    print("  [--ssh-workspace PATH] [--ssh-conda-env NAME]")
    print("  [--server-id ID|auto] [--lease-hours N] [--min-gpu-count N]")
    print("  [--min-vram-gb GB] [--server-tags tag1,tag2]")
    print("  [--python-version VER] [--cuda-version VER] [--env-manager TOOL]")
    print("  [--keywords ...] [--reference ...] [--foundation ...] [--anchor ...]")
    print("")
    print("Backtrack (structured advice):")
    print("  backtrack <from> <to> <reason> [direction]")
    print("  backtrack <from> <to> <reason> --review-file <review.md>")
    print("  backtrack <from> <to> <reason> [--required-fix ...] [--success-criteria ...]")
    print("    [--rebuild-mode MODE] [--rerun-scope ...] [--evidence-paths p1,p2]")
    print("")
    print("Auto-run:")
    print("  set-auto-advance <on|off>     Enable/disable automatic module transition")
    print("  dispatch next|stage|reviews|gate|ssh [target] [--write] [--format json|markdown]")
    print("")
    print("Public DB subcommands:")
    print("  public-db status              Show database location and size")
    print("  public-db stats               Show tag statistics and top papers")
    print("  public-db list-papers [tag]   List papers (optionally filter by tag)")
    print("  public-db search <keywords>   Full-text search across titles/abstracts")
    print("  public-db show-paper <id>     Show full details of a paper")
    print("  public-db list-tags           List all domain tags")
    print("  public-db import-project <dir> Import a project's source log")


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        _print_help()
        sys.exit(0)

    # Handle --project flag before command parsing
    # If first arg is --project, extract it and shift
    if args[0] == "--project" and len(args) >= 3:
        # Reorder: --project /path cmd ... -> cmd --project /path ...
        args = [args[2], args[0], args[1]] + args[3:]

    cmd = args[0]
    remaining = args[1:]
    if cmd in {"--help", "-h", "help"}:
        _print_help()
        sys.exit(0)

    if cmd == "create":
        try:
            parsed = _parse_create_args(remaining)
        except SystemExit as exc:
            print(str(exc))
            sys.exit(1)
        create_venue = parsed["venue"] or parsed["positional_venue"]
        cmd_create(
            parsed["topic"],
            parsed["display_name"],
            create_venue,
            keywords=parsed["keywords"],
            reference_papers=parsed["reference_papers"],
            foundation_papers=parsed["foundation_papers"],
            input_manifest=parsed["input_manifest"],
            notes=parsed["notes"],
            auto_advance=parsed.get("auto_advance", False),
            execution_env=parsed.get("execution_env"),
            ssh_server_id=parsed.get("ssh_server_id"),
            ssh_server_ids=parsed.get("ssh_server_ids"),
            ssh_pool_count=parsed.get("ssh_pool_count"),
            ssh_lease_hours=parsed.get("ssh_lease_hours"),
            ssh_min_gpu_count=parsed.get("ssh_min_gpu_count", 0),
            ssh_min_vram_gb=parsed.get("ssh_min_vram_gb"),
            ssh_server_tags=parsed.get("ssh_server_tags"),
        )

    elif cmd == "status":
        proj = _resolve_project_dir(remaining)
        cmd_status(proj)

    elif cmd == "module-status":
        proj = _resolve_project_dir(remaining)
        cmd_module_status(proj)

    elif cmd == "advance":
        proj = _resolve_project_dir(remaining)
        if len(remaining) < 3:
            print("Usage: advance <stage> <agent> <output_file> [--force] [--skip-gates]")
            sys.exit(1)
        force = "--force" in remaining
        skip = "--skip-gates" in remaining
        for flag in ("--force", "--skip-gates"):
            while flag in remaining:
                remaining.remove(flag)
        cmd_advance(proj, remaining[0], remaining[1], remaining[2], force=force, skip_gates=skip)

    elif cmd == "human-review":
        proj = _resolve_project_dir(remaining)
        if len(remaining) < 2:
            print("Usage: human-review <stage> <opinion> [verdict]")
            sys.exit(1)
        verdict = remaining[2] if len(remaining) > 2 else "revise"
        cmd_human_review(proj, remaining[0], remaining[1], verdict)

    elif cmd == "auto-stage":
        proj = _resolve_project_dir(remaining)
        if not remaining:
            print("Usage: auto-stage <stage>")
            sys.exit(1)
        cmd_auto_stage(proj, remaining[0])

    elif cmd == "auto-module":
        proj = _resolve_project_dir(remaining)
        if not remaining:
            print("Usage: auto-module <module>")
            sys.exit(1)
        cmd_auto_module(proj, remaining[0])

    elif cmd == "auto-backtrack":
        proj = _resolve_project_dir(remaining)
        if len(remaining) < 3:
            print("Usage: auto-backtrack <from> <to> <reason> [direction]")
            sys.exit(1)
        cmd_auto_backtrack(proj, remaining[0], remaining[1], remaining[2], remaining[3] if len(remaining) > 3 else "")

    elif cmd == "auto-run":
        proj = _resolve_project_dir(remaining)
        cmd_auto_run(proj)

    elif cmd == "run-module":
        proj = _resolve_project_dir(remaining)
        if not remaining:
            print("Usage: run-module <module>")
            sys.exit(1)
        cmd_run_module(proj, remaining[0])

    elif cmd in {"list", "list-projects"}:
        cmd_list_projects()

    elif cmd == "use":
        if not remaining:
            print("Usage: use <project_dir>")
            sys.exit(1)
        cmd_use(remaining[0])

    elif cmd == "list-venues":
        cmd_list_venues()

    elif cmd == "set-venue":
        proj = _resolve_project_dir(remaining)
        if not remaining:
            print("Usage: set-venue <venue_id>")
            sys.exit(1)
        cmd_set_venue(proj, remaining[0])

    elif cmd == "set-auto-advance":
        proj = _resolve_project_dir(remaining)
        if not remaining:
            print("Usage: set-auto-advance <on|off>")
            sys.exit(1)
        enabled = remaining[0].lower() in {"on", "true", "1", "yes", "enable"}
        cmd_set_auto_advance(proj, enabled)

    elif cmd == "dispatch":
        proj = _resolve_project_dir(remaining)
        write = "--write" in remaining
        while "--write" in remaining:
            remaining.remove("--write")

        fmt = "markdown"
        out_dir = ""
        for flag in ("--format", "--out-dir"):
            while flag in remaining:
                i = remaining.index(flag)
                if i + 1 >= len(remaining):
                    print(f"Usage: dispatch next|stage|reviews|gate|ssh [target] [{flag} VALUE]")
                    sys.exit(1)
                value = remaining[i + 1]
                del remaining[i:i + 2]
                if flag == "--format":
                    fmt = value
                else:
                    out_dir = value
        if "--json" in remaining:
            fmt = "json"
            while "--json" in remaining:
                remaining.remove("--json")

        if fmt not in {"markdown", "json"}:
            print("[ERROR] --format must be markdown or json")
            sys.exit(1)

        scope = remaining[0] if remaining else "next"
        target = remaining[1] if len(remaining) > 1 else ""
        if len(remaining) > 2:
            print("Usage: dispatch next|stage|reviews|gate|ssh [target] [--write] [--format json|markdown]")
            sys.exit(1)
        cmd_dispatch(proj, scope, target, fmt=fmt, write=write, out_dir=out_dir)

    elif cmd == "backtrack":
        proj = _resolve_project_dir(remaining)
        # Parse optional structured advice flags
        def _pop_flag(args: list[str], flag: str) -> str:
            for i, a in enumerate(args):
                if a == flag and i + 1 < len(args):
                    val = args[i + 1]
                    del args[i:i + 2]
                    return val
            return ""
        def _pop_flag_list(args: list[str], flag: str) -> list[str] | None:
            for i, a in enumerate(args):
                if a == flag and i + 1 < len(args):
                    val = [v.strip() for v in args[i + 1].split(",") if v.strip()]
                    del args[i:i + 2]
                    return val
            return None

        review_file = _pop_flag(remaining, "--review-file")
        required_fix = _pop_flag(remaining, "--required-fix")
        success_criteria = _pop_flag(remaining, "--success-criteria")
        rebuild_mode = _pop_flag(remaining, "--rebuild-mode")
        rerun_scope = _pop_flag(remaining, "--rerun-scope")
        evidence_paths = _pop_flag_list(remaining, "--evidence-paths")
        handoff_updates = _pop_flag_list(remaining, "--handoff-updates")

        if len(remaining) < 3:
            print("Usage: backtrack <from> <to> <reason> [direction]")
            print("       backtrack <from> <to> <reason> --review-file <path>")
            print("       backtrack <from> <to> <reason> [--required-fix ...] [--success-criteria ...]")
            print("         [--rebuild-mode full_regenerate|incremental_replay] [--rerun-scope ...]")
            print("         [--evidence-paths p1,p2] [--handoff-updates u1,u2]")
            sys.exit(1)
        cmd_backtrack(
            proj, remaining[0], remaining[1], remaining[2],
            remaining[3] if len(remaining) > 3 else "",
            review_file=review_file or None,
            required_fix=required_fix,
            success_criteria=success_criteria,
            rebuild_mode=rebuild_mode,
            rerun_scope=rerun_scope,
            evidence_paths=evidence_paths,
            handoff_updates=handoff_updates,
        )

    elif cmd == "onboarding-done":
        if remaining:
            proj = str(Path(remaining[0]).resolve())
        else:
            proj = _resolve_project_dir(remaining)
        cmd_onboarding_done(proj)

    elif cmd == "public-db":
        if not remaining:
            print("Usage: public-db <status|init|stats|import-project> [args...]")
            sys.exit(1)
        sub = remaining[0]
        if sub == "status":
            cmd_public_db_status()
        elif sub == "init":
            cmd_public_db_init()
        elif sub == "stats":
            cmd_public_db_stats()
        elif sub == "import-project":
            if len(remaining) < 2:
                print("Usage: public-db import-project <project_dir>")
                sys.exit(1)
            cmd_public_db_import_project(remaining[1])

        elif sub == "list-papers":
            tag = remaining[1] if len(remaining) > 1 else None
            cmd_public_db_list_papers(tag=tag)

        elif sub == "search":
            if len(remaining) < 2:
                print("Usage: public-db search <keywords>")
                sys.exit(1)
            cmd_public_db_search(remaining[1])

        elif sub == "show-paper":
            if len(remaining) < 2:
                print("Usage: public-db show-paper <paper_id>")
                sys.exit(1)
            cmd_public_db_show_paper(remaining[1])

        elif sub == "list-tags":
            cmd_public_db_list_tags()

        else:
            print(f"[ERROR] Unknown public-db subcommand: {sub}")
            sys.exit(1)

    else:
        print(f"[ERROR] Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
