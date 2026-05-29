"""Conductor — Main orchestration entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Any

from .state import PipelineState
from .project import MODULE_STAGES, AGENT_FOR_STAGE, GATE_STAGES
from .verdict_parser import VerdictParser

GATE_CRITICS = {
    "G1": ["logic", "coverage"],
    "G2": ["logic", "method", "novelty"],
    "G3": ["method", "evidence"],
    "G4": ["logic", "evidence", "novelty"],
    "G5": ["logic", "writing", "evidence", "novelty", "ethics"],
    "G6": ["logic", "evidence", "writing", "resolution"],
}

STAGE_CHECKERS = {
    "M1S02": ["source_log_validator", "survey_review"],
    # M2: stage-level reviews (承上启下审查)
    "M2S01": ["m2_search_quality"],
    "M2S02": ["m2_migration"],
    "M2S03": ["m2_design_review"],
    "M2S04": ["m2_design_review"],
    "M2S05": ["m2_experiment_design_review"],
    "M2S06": ["m2_experiment_plan_review"],
    "M3S01": ["m3_dataset_env_review"],
    "M3S02": ["m3_baseline_result_review"],
    "M3S03": ["m3_main_result_review"],
    # M4: stage-level reviews
    "M4S01": ["m4_findings_audit"],
    "M4S02": ["m4_analysis_design_review"],
    "M4S03": ["m4_analysis_execution_review"],
    # M5: content + figure/table stage reviews
    "M5S01": ["m5_prewrite_review"],
    "M5S02": ["m5_outline_style_review"],
    "M5S03": ["m5_intro_relatedwork_review"],
    "M5S04": ["m5_method_figure_review"],
    "M5S05": ["m5_experiments_results_review"],
    "M5S06": ["m5_analysis_discussion_review"],
    "M5S07": ["m5_abstract_conclusion_review"],
    "M5S09": ["m5_full_polish_review"],
    # M5: build verification runs after full draft assembly, not after abstract/conclusion.
    "M5S08": ["build_verifier", "m5_final_compilation_review"],
    # M6: internal review, submission + rebuttal stage reviews
    "M6S01": ["m6_internal_peer_review", "m6_submission_audit"],
    "M6S02": ["m6_external_submission_review"],
    "M6S03": ["m6_review_parsing_review"],
    "M6S04": ["m6_rebuttal_strategy_review"],
    "M6S05": ["m6_revision_execution_review"],
    "M6S06": ["m6_revision_validation_review"],
}

ALL_MODULES = list(MODULE_STAGES.keys())


def _module_of_stage(stage: str) -> str:
    for mod, stages in MODULE_STAGES.items():
        if stage in stages:
            return mod
    return "M6"


def _build_backtrack_advice(
    *,
    critic: str = "",
    target_stage: str,
    reason: str,
    direction: str = "",
    verdict_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build durable repair guidance for a backtrack target stage."""
    payload = verdict_payload or {}
    blocking_reason = (
        payload.get("blocking_reason")
        or payload.get("reason")
        or reason
    )
    required_fix = (
        payload.get("required_fix")
        or payload.get("direction")
        or payload.get("repair_plan")
        or payload.get("recommendation")
        or direction
        or blocking_reason
    )
    success_criteria = (
        payload.get("success_criteria")
        or payload.get("acceptance_criteria")
        or f"{target_stage} passes its stage review and downstream stale stages can be re-run cleanly"
    )
    evidence_paths = payload.get("evidence_paths") or payload.get("evidence") or []
    if isinstance(evidence_paths, str):
        evidence_paths = [evidence_paths]
    rebuild_mode = payload.get("rebuild_mode") or _infer_rebuild_mode(
        blocking_reason,
        str(required_fix),
        str(payload.get("direction", direction)),
    )

    return {
        "source_critic": critic or payload.get("critic", ""),
        "target_stage": target_stage,
        "blocking_reason": blocking_reason,
        "required_fix": required_fix,
        "success_criteria": success_criteria,
        "evidence_paths": evidence_paths,
        "rebuild_mode": rebuild_mode,
        "rerun_scope": payload.get("rerun_scope", f"Re-execute {target_stage} and downstream stale stages"),
        "handoff_updates": payload.get("handoff_updates", []),
    }


def _infer_rebuild_mode(reason: str, required_fix: str = "", direction: str = "") -> str:
    text = f"{reason}\n{required_fix}\n{direction}".lower()
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


class Conductor:
    def __init__(self, project_root: Path):
        self.root = project_root
        self.state = PipelineState(project_root)
        self.framework_docs = Path(__file__).parent.parent / "docs"
        self.agent_docs = Path(__file__).parent.parent / "docs" / "AGENTS"

    def current_stage(self) -> str:
        return self.state.get_current_stage()

    def current_module(self) -> str:
        return self.state.get_current_module()

    def current_status(self) -> str:
        return self.state.get_current_status()

    def next_stage(self) -> Optional[str]:
        all_stages = [s for stages in MODULE_STAGES.values() for s in stages]
        try:
            idx = all_stages.index(self.current_stage())
            return all_stages[idx + 1] if idx + 1 < len(all_stages) else None
        except ValueError:
            return "M1S01"

    def is_gate_stage(self, stage: str) -> tuple[bool, Optional[str]]:
        for gate, st in GATE_STAGES.items():
            if st == stage:
                return True, gate
        return False, None

    def get_agent_for_stage(self, stage: str) -> str:
        return AGENT_FOR_STAGE.get(stage, "conductor")

    def get_stage_checkers(self, stage: str) -> list[str]:
        return STAGE_CHECKERS.get(stage, [])

    def get_stage_review_outputs(self, stage: str) -> dict[str, Path]:
        from scripts.conductor_helper import get_stage_review_outputs

        return get_stage_review_outputs(self.root, stage)

    def get_checker_md_path(self, checker: str) -> Path:
        checker_paths = {
            "source_log_validator": "critic/source_log_validator/AGENT.md",
            "code_review": "critic/code_review/AGENT.md",
            "data_checker": "critic/data_checker/AGENT.md",
            "evidence": "critic/evidence/AGENT.md",
            "build_verifier": "build_verifier/AGENT.md",
            "survey_review": "critic/survey_review/AGENT.md",
            # Gate critics
            "logic": "critic/logic/AGENT.md",
            "method": "critic/method/AGENT.md",
            "novelty": "critic/novelty/AGENT.md",
            "coverage": "critic/coverage/AGENT.md",
            "writing": "critic/writing/AGENT.md",
            "ethics": "critic/ethics/AGENT.md",
            # M2 stage-level reviews
            "m2_search_quality": "critic/m2_search_quality/AGENT.md",
            "m2_migration": "critic/m2_migration/AGENT.md",
            "m2_design_review": "critic/m2_design_review/AGENT.md",
            "m2_experiment_design_review": "critic/m2_experiment_design_review/AGENT.md",
            "m2_experiment_plan_review": "critic/m2_experiment_plan_review/AGENT.md",
            # M3 stage-level reviews
            "m3_dataset_env_review": "critic/m3_dataset_env_review/AGENT.md",
            "m3_baseline_result_review": "critic/m3_baseline_result_review/AGENT.md",
            "m3_main_result_review": "critic/m3_main_result_review/AGENT.md",
            # M4 stage-level reviews
            "m4_findings_audit": "critic/m4_findings_audit/AGENT.md",
            "m4_analysis_design_review": "critic/m4_analysis_design_review/AGENT.md",
            "m4_analysis_execution_review": "critic/m4_analysis_execution_review/AGENT.md",
            # M5 stage-level reviews (same AGENT, stage-specific checker names)
            "m5_prewrite_review": "critic/m5_stage_review/AGENT.md",
            "m5_outline_style_review": "critic/m5_stage_review/AGENT.md",
            "m5_intro_relatedwork_review": "critic/m5_stage_review/AGENT.md",
            "m5_method_figure_review": "critic/m5_stage_review/AGENT.md",
            "m5_experiments_results_review": "critic/m5_stage_review/AGENT.md",
            "m5_analysis_discussion_review": "critic/m5_stage_review/AGENT.md",
            "m5_abstract_conclusion_review": "critic/m5_stage_review/AGENT.md",
            "m5_full_polish_review": "critic/m5_stage_review/AGENT.md",
            "m5_final_compilation_review": "critic/m5_stage_review/AGENT.md",
            # M6 stage-level reviews
            "m6_internal_peer_review": "critic/m6_internal_peer_review/AGENT.md",
            "m6_submission_audit": "critic/m6_stage_review/AGENT.md",
            "m6_external_submission_review": "critic/m6_stage_review/AGENT.md",
            "m6_review_parsing_review": "critic/m6_stage_review/AGENT.md",
            "m6_rebuttal_strategy_review": "critic/m6_stage_review/AGENT.md",
            "m6_revision_execution_review": "critic/m6_stage_review/AGENT.md",
            "m6_revision_validation_review": "critic/m6_stage_review/AGENT.md",
            # G6 critic
            "resolution": "critic/g6_resolution/AGENT.md",
        }
        subpath = checker_paths.get(checker, checker)
        return self.agent_docs / subpath

    def get_agent_md_path(self, stage: str) -> Path:
        agent = self.get_agent_for_stage(stage)
        if agent == "critic_team":
            return self.agent_docs / "critic" / "AGENT.md"
        if agent == "conductor_routed":
            return self.agent_docs / "conductor" / "AGENT.md"
        return self.agent_docs / agent / "AGENT.md"

    def get_stage_input_docs(self, stage: str) -> list[Path]:
        from scripts.conductor_helper import get_input_docs

        return get_input_docs(self.root, stage)

    def check_module_prerequisites(self, module: str) -> tuple[bool, str]:
        if module not in ALL_MODULES:
            return False, f"Unknown module: {module}"
        idx = ALL_MODULES.index(module)
        if idx == 0:
            return True, "M1 has no prerequisites"
        prev_module = ALL_MODULES[idx - 1]
        prev_status = self.state.get_module_status(prev_module).get("status", "pending")
        if prev_status != "completed":
            return False, (
                f"{prev_module} not completed (status: {prev_status}). "
                f"Please run {prev_module} first."
            )
        return True, f"{prev_module} completed. Ready to start {module}."

    def get_module_stages(self, module: str) -> list[str]:
        return MODULE_STAGES.get(module, [])

    def get_first_stage_of_module(self, module: str) -> Optional[str]:
        stages = self.get_module_stages(module)
        return stages[0] if stages else None

    def get_last_stage_of_module(self, module: str) -> Optional[str]:
        stages = self.get_module_stages(module)
        return stages[-1] if stages else None

    def is_module_completed(self, module: str) -> bool:
        return self.state.get_module_status(module).get("status") == "completed"

    def run_module(self, module: str) -> dict[str, Any]:
        ok, msg = self.check_module_prerequisites(module)
        if not ok:
            return {"ok": False, "error": msg, "module": module, "action": "BLOCKED"}

        stages = self.get_module_stages(module)
        if not stages:
            return {"ok": False, "error": f"No stages defined for {module}", "action": "BLOCKED"}

        first = stages[0]
        self.state.set_stage(first, "in_progress")
        self.state.set_module_status(module, "in_progress")

        return {
            "ok": True,
            "module": module,
            "stages": stages,
            "first_stage": first,
            "last_stage": stages[-1],
            "gate": GATE_STAGES.get(f"G{module[1:]}"),
            "prerequisites": msg,
            "action": "START",
        }

    def run_stage(self, stage: str) -> dict[str, Any]:
        agent = self.get_agent_for_stage(stage)
        agent_md = self.get_agent_md_path(stage)
        inputs = self.get_stage_input_docs(stage)
        is_gate, gate_id = self.is_gate_stage(stage)
        current_status = self.current_status()

        from scripts.conductor_helper import get_input_docs
        inputs = get_input_docs(self.root, stage)

        from utils.file_guard import get_canonical_output_path
        output_path = get_canonical_output_path(self.root, stage)
        phase = "gate" if is_gate and current_status == "waiting_gate" else "stage"

        plan = {
            "stage": stage,
            "agent": agent,
            "agent_md": str(agent_md),
            "md_protocol": str(self.framework_docs / "07_MD_PROTOCOL.md"),
            "input_docs": [str(p) for p in inputs],
            "output_doc": str(output_path),
            "stage_checkers": self.get_stage_checkers(stage),
            "stage_checker_docs": [
                str(self.get_checker_md_path(checker))
                for checker in self.get_stage_checkers(stage)
            ],
            "stage_review_outputs": {
                checker: str(path)
                for checker, path in self.get_stage_review_outputs(stage).items()
            },
            "is_gate": is_gate,
            "phase": phase,
            "gate_id": gate_id,
            "current_status": current_status,
            "project_root": str(self.root),
        }
        advice = self.state.get_latest_backtrack_advice(stage)
        if advice:
            plan["backtrack_advice"] = advice
        return plan

    def get_next_action(self) -> dict[str, Any]:
        stage = self.current_stage()
        module = self.current_module()
        status = self.current_status()

        if status == "module_completed":
            # Auto-advance: if enabled and there is a next module, proceed automatically
            if self.state.is_auto_advance_enabled():
                # state_manager.advance records module completion while already
                # positioning current.stage at the first stage of the next
                # module.  In that common state, auto-advance should simply
                # open the current module instead of skipping one module ahead.
                stage_module = _module_of_stage(stage)
                stage_module_status = self.state.get_module_status(stage_module).get("status", "pending")
                if stage_module_status != "completed":
                    self.state.set_stage(stage, "in_progress")
                    self.state.set_module_status(stage_module, "in_progress")
                    return {
                        "action": "EXECUTE_STAGE",
                        "stage": stage,
                        "module": stage_module,
                        "plan": self.run_stage(stage),
                        "note": f"Auto-started {stage_module} at {stage}",
                    }

                next_module = self._get_next_module(module)
                if next_module:
                    first_stage = self.get_first_stage_of_module(next_module)
                    if first_stage:
                        self.state.set_stage(first_stage, "in_progress")
                        self.state.set_module_status(next_module, "in_progress")
                        return {
                            "action": "EXECUTE_STAGE",
                            "stage": first_stage,
                            "module": next_module,
                            "plan": self.run_stage(first_stage),
                            "note": f"Auto-advanced from {module} to {next_module}",
                        }
            return {
                "action": "WAIT_USER",
                "reason": f"{module} previous module completed. User must explicitly request next module.",
                "suggested_cmd": f"python scripts/state_manager.py run-module {module}",
            }

        is_gate, gate_id = self.is_gate_stage(stage)
        if is_gate and gate_id and status == "waiting_gate":
            critics = GATE_CRITICS.get(gate_id, [])
            return {
                "action": "GATE",
                "stage": stage,
                "gate_id": gate_id,
                "critics": critics,
                "input_docs": [str(p) for p in self.get_stage_input_docs(stage)],
            }

        stale = self.state.get_stale_stages()
        if stale and self.state.is_stale(stage):
            return {
                "action": "RE_EXECUTE",
                "stage": stage,
                "reason": f"Stage {stage} is marked stale due to backtrack.",
                "stale_stages": stale,
                "backtrack_advice": self.state.get_latest_backtrack_advice(stage),
                "plan": self.run_stage(stage),
            }

        return {
            "action": "EXECUTE_STAGE",
            "stage": stage,
            "module": module,
            "plan": self.run_stage(stage),
        }

    def _get_next_module(self, module: str) -> str | None:
        """Return the module that follows *module*, or None if *module* is the last."""
        modules = ALL_MODULES
        try:
            idx = modules.index(module)
            return modules[idx + 1] if idx + 1 < len(modules) else None
        except ValueError:
            return None

    def auto_execute_plan(self, from_stage: Optional[str] = None) -> dict[str, Any]:
        all_stages = [s for stages in MODULE_STAGES.values() for s in stages]
        start = from_stage or self.current_stage()
        try:
            start_idx = all_stages.index(start)
        except ValueError:
            start_idx = 0

        remaining = all_stages[start_idx:]
        plans = []
        for st in remaining:
            plan = self.run_stage(st)
            is_gate, gate_id = self.is_gate_stage(st)
            plan["is_gate"] = is_gate
            plan["gate_id"] = gate_id
            plans.append(plan)

        return {
            "ok": True,
            "from_stage": start,
            "total_stages": len(remaining),
            "stages": plans,
            "current_status": self.current_status(),
        }

    # ---- Backtrack ----

    def backtrack(
        self,
        from_stage: str,
        to_stage: str,
        reason: str,
        direction: str = "",
        advice: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        all_stages = [s for stages in MODULE_STAGES.values() for s in stages]
        try:
            from_idx = all_stages.index(from_stage)
            to_idx = all_stages.index(to_stage)
        except ValueError:
            return {"ok": False, "error": f"Invalid stage(s): {from_stage} / {to_stage}"}

        if to_idx > from_idx:
            return {"ok": False, "error": f"Backtrack target {to_stage} must not be after {from_stage}"}

        target_module = _module_of_stage(to_stage)

        if self.state.is_spiral_limit_exceeded(target_module, limit=10):
            return {
                "ok": False,
                "error": f"Spiral limit reached for {target_module} (10 backtracks). Human intervention required.",
                "action": "HALT",
            }

        backtrack_advice = advice or _build_backtrack_advice(
            target_stage=to_stage,
            reason=reason,
            direction=direction,
        )
        direction = direction or backtrack_advice.get("required_fix", "")

        self.state.record_backtrack(from_stage, to_stage, reason, direction, advice=backtrack_advice)
        self.state.set_stage(to_stage, "in_progress")

        from_module = _module_of_stage(from_stage)
        all_modules = list(MODULE_STAGES.keys())
        try:
            for idx in range(all_modules.index(target_module), all_modules.index(from_module) + 1):
                mod = all_modules[idx]
                if self.state.get_module_status(mod).get("status") in ("completed", "module_completed"):
                    self.state.set_module_status(mod, "reopened")
        except (ValueError, IndexError):
            pass

        decision_type = "stage_revise" if from_stage == to_stage else "backtrack"
        summary_label = "Revise" if from_stage == to_stage else "Backtrack"
        self.state.log_decision(
            decision_type, to_stage,
            f"{summary_label} {from_stage} → {to_stage}",
            (
                f"Reason: {reason}\n"
                f"Direction: {direction}\n"
                f"Required fix: {backtrack_advice.get('required_fix', '')}\n"
                f"Success criteria: {backtrack_advice.get('success_criteria', '')}\n"
                f"Rebuild mode: {backtrack_advice.get('rebuild_mode', 'full_regenerate')}\n"
                f"Rerun scope: {backtrack_advice.get('rerun_scope', '')}\n"
                f"Handoff updates: {', '.join(backtrack_advice.get('handoff_updates', []))}"
            )
        )

        return {
            "ok": True,
            "from": from_stage,
            "to": to_stage,
            "target_module": target_module,
            "spiral_count": self.state.get_spiral_count(target_module),
            "stale_stages": self.state.get_stale_stages(),
            "gates_needing_re_review": self.state.get_gates_needing_re_review(),
            "advice": backtrack_advice,
            "action": "RE_EXECUTE",
        }

    def backtrack_from_revision_routing(self, routing: dict[str, Any]) -> dict[str, Any]:
        """Apply an M6S05 routing plan through the normal backtrack path."""
        state_update = routing.get("recommended_state_update", {}) if isinstance(routing, dict) else {}
        target = state_update.get("to_stage") or routing.get("earliest_target_stage", "")
        if not target:
            return {"ok": False, "error": "M6 revision routing has no target stage"}

        advice = {
            "source_critic": "m6_action_router",
            "target_stage": target,
            "blocking_reason": state_update.get("reason", "M6S04 action plan requires routed revision execution"),
            "required_fix": state_update.get("required_fix", ""),
            "success_criteria": state_update.get("success_criteria", ""),
            "evidence_paths": state_update.get("evidence_paths", []),
            "rebuild_mode": state_update.get("rebuild_mode", "incremental_replay"),
            "rerun_scope": state_update.get("rerun_scope", ""),
            "handoff_updates": state_update.get("handoff_updates", []),
            "stage_backtrack_advice": state_update.get("stage_backtrack_advice", routing.get("stage_backtrack_advice", {})),
            "m6_action_item_ids": state_update.get("m6_action_item_ids", []),
            "source_action_plan": routing.get("action_plan_path", ""),
        }
        return self.backtrack(
            from_stage=state_update.get("from_stage", "M6S05"),
            to_stage=target,
            reason=advice["blocking_reason"],
            direction=advice["required_fix"],
            advice=advice,
        )

    def handle_stage_review_verdict(self, stage: str) -> dict[str, Any]:
        """Orchestrate stage-review verdicts: parse, validate, decide.

        Parsing is delegated to ``VerdictParser``; this method focuses solely on
        stateful orchestration decisions (PASS, HALT, RE_EXECUTE via backtrack).
        """
        from scripts.conductor_helper import get_stage_review_outputs

        review_outputs = get_stage_review_outputs(self.root, stage)
        if not review_outputs:
            return {
                "action": "BLOCKED",
                "reason": f"No stage review outputs configured for {stage}",
            }

        # ---- Phase 1: Parse all review files via VerdictParser (pure, side-effect free) ----
        try:
            parsed = VerdictParser.parse_all_stage_reviews(review_outputs)
        except FileNotFoundError as exc:
            return {
                "action": "BLOCKED",
                "reason": f"Stage review missing: {exc}",
            }
        except Exception as exc:
            return {
                "action": "BLOCKED",
                "reason": f"Unreadable stage review: {exc}",
            }

        # ---- Phase 2: Validate structure and handle HALT immediately ----
        for result in parsed:
            ok, err = result.is_valid
            if not ok:
                return {
                    "action": "BLOCKED",
                    "reason": f"Stage review {result.review_path.name} {err}",
                    "checker": result.checker,
                    "missing_fields": result.missing_fields,
                }

            if result.verdict == "HALT":
                reason = f"Stage review {stage} HALT by {result.checker}"
                self.state.log_decision("stage_review_halt", stage, reason, str(result.review_path))
                return {
                    "action": "HALT",
                    "reason": reason,
                    "checker": result.checker,
                    "review_path": str(result.review_path),
                }

        # ---- Phase 3: Orchestration decision ----
        dominant = VerdictParser.select_dominant_non_pass(parsed)
        if dominant is None:
            self.state.log_decision("stage_review_pass", stage, f"Stage {stage} passed all stage reviews")
            return {"action": "PASS", "stage": stage}

        # Non-PASS verdict → backtrack
        target = dominant.target_stage or stage
        reason = (
            f"Stage review {stage} {dominant.verdict} by {dominant.checker}: "
            f"{dominant.blocking_reason}"
        )
        direction = dominant.required_fix
        result = self.backtrack(
            from_stage=stage,
            to_stage=target,
            reason=reason,
            direction=direction,
            advice=dominant.to_dict(),
        )
        if result.get("ok"):
            return {
                "action": "RE_EXECUTE",
                "target_stage": target,
                "reason": reason,
                "stale_stages": result.get("stale_stages", []),
                "spiral_count": result.get("spiral_count", 0),
                "advice": result.get("advice", {}),
            }
        return {
            "action": "HALT",
            "reason": result.get("error", "Stage review backtrack failed"),
        }

    def handle_gate_verdict(self, gate_id: str, verdicts: list[dict[str, Any]]) -> dict[str, Any]:
        for v in verdicts:
            if v.get("verdict") == "HALT":
                self.state.log_decision("gate_halt", gate_id,
                                        f"Gate {gate_id} HALTED by {v['critic']}",
                                        v.get("reason", ""))
                return {"action": "HALT", "reason": v.get("reason", "")}

        for v in verdicts:
            if v.get("verdict") == "BACKTRACK":
                target = v.get("target_stage")
                if not target:
                    gate_num = int(gate_id[1:])
                    mod = f"M{gate_num}"
                    target = self.get_first_stage_of_module(mod) or "M1S01"
                result = self.backtrack(
                    from_stage=GATE_STAGES.get(gate_id, ""),
                    to_stage=target,
                    reason=f"Gate {gate_id} BACKTRACK by {v['critic']}: {v.get('reason', '')}",
                    direction=v.get("direction", v.get("reason", "")),
                    advice=_build_backtrack_advice(
                        critic=v.get("critic", ""),
                        target_stage=target,
                        reason=f"Gate {gate_id} BACKTRACK by {v['critic']}: {v.get('reason', '')}",
                        direction=v.get("direction", ""),
                        verdict_payload=v,
                    ),
                )
                if result.get("ok"):
                    return {
                        "action": "RE_EXECUTE",
                        "target_stage": target,
                        "reason": f"{v['critic']}: {v.get('reason', '')}",
                        "stale_stages": result.get("stale_stages", []),
                        "spiral_count": result.get("spiral_count", 0),
                        "advice": result.get("advice", {}),
                    }
                else:
                    return {
                        "action": "HALT",
                        "reason": result.get("error", "BACKTRACK failed"),
                    }

        for v in verdicts:
            if v.get("verdict") == "FIX":
                target = v.get("target_stage")
                if not target:
                    gate_num = int(gate_id[1:])
                    mod = f"M{gate_num}"
                    if gate_id == "G3":
                        target = "M3S02"
                    else:
                        target = self.get_first_stage_of_module(mod) or "M1S01"
                result = self.backtrack(
                    from_stage=GATE_STAGES.get(gate_id, ""),
                    to_stage=target,
                    reason=f"Gate {gate_id} FIX by {v['critic']}: {v.get('reason', '')}",
                    direction=v.get("direction", v.get("reason", "")),
                    advice=_build_backtrack_advice(
                        critic=v.get("critic", ""),
                        target_stage=target,
                        reason=f"Gate {gate_id} FIX by {v['critic']}: {v.get('reason', '')}",
                        direction=v.get("direction", ""),
                        verdict_payload=v,
                    ),
                )
                if result.get("ok"):
                    return {
                        "action": "RE_EXECUTE",
                        "target_stage": target,
                        "reason": f"{v['critic']}: FIX required — {v.get('reason', '')}",
                        "stale_stages": result.get("stale_stages", []),
                        "spiral_count": result.get("spiral_count", 0),
                        "advice": result.get("advice", {}),
                    }
                else:
                    return {
                        "action": "HALT",
                        "reason": result.get("error", "FIX backtrack failed"),
                    }

        for v in verdicts:
            if v.get("verdict") == "REVISE":
                target = v.get("target_stage")
                if not target:
                    gate_stage = GATE_STAGES.get(gate_id)
                    target = gate_stage
                # REVISE triggers backtrack to the target stage
                result = self.backtrack(
                    from_stage=GATE_STAGES.get(gate_id, ""),
                    to_stage=target,
                    reason=f"Gate {gate_id} REVISE by {v['critic']}: {v.get('reason', '')}",
                    direction=v.get("direction", v.get("reason", "")),
                    advice=_build_backtrack_advice(
                        critic=v.get("critic", ""),
                        target_stage=target,
                        reason=f"Gate {gate_id} REVISE by {v['critic']}: {v.get('reason', '')}",
                        direction=v.get("direction", ""),
                        verdict_payload=v,
                    ),
                )
                if result.get("ok"):
                    return {
                        "action": "RE_EXECUTE",
                        "target_stage": target,
                        "reason": f"{v['critic']}: {v.get('reason', '')}",
                        "stale_stages": result.get("stale_stages", []),
                        "spiral_count": result.get("spiral_count", 0),
                        "advice": result.get("advice", {}),
                    }
                else:
                    return {
                        "action": "HALT",
                        "reason": result.get("error", "REVISE backtrack failed"),
                    }

        self.state.clear_gate_re_review(gate_id)
        self.state.log_decision("gate_pass", gate_id,
                                f"Gate {gate_id} PASSED by all critics")
        return {"action": "PASS"}
