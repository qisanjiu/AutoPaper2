"""Pipeline state manager — global project state across all 6 modules."""

from __future__ import annotations

import yaml
from copy import deepcopy
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

DEFAULT_STATE: dict[str, Any] = {
    "project": {
        "name": "",
        "topic": "",
        "created_at": "",
        "venue": {"id": "arxiv", "name": "arXiv"},
    },
    "current": {
        "module": "M1",
        "stage": "M1S01",
        "status": "initialized",
    },
    "modules": {
        "M1": {"status": "pending", "completed_at": None, "last_stage": None},
        "M2": {"status": "pending", "completed_at": None, "last_stage": None},
        "M3": {"status": "pending", "completed_at": None, "last_stage": None},
        "M4": {"status": "pending", "completed_at": None, "last_stage": None},
        "M5": {"status": "pending", "completed_at": None, "last_stage": None},
        "M6": {"status": "pending", "completed_at": None, "last_stage": None},
    },
    "settings": {
        "auto_advance_modules": False,
    },
    "session": {
        "orchestrator_lock": True,
        "lock_set_at": "",
        "last_agent_mode": "orchestrator",
    },
    "history": [],
    "backtrack_log": [],
    "stage_backtrack_advice": {},
    "spiral_count": {},
    "agents": {},
    "gates": {},
    "stale_stages": [],
    "gate_re_review": {},
    "human_reviews": [],
    "decision_log": [],
}


class PipelineState:
    """Manages pipeline_state.yaml for a project."""

    def __init__(self, project_root: Path):
        self.path = project_root / "state" / "pipeline_state.yaml"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                self.data: dict[str, Any] = yaml.safe_load(f) or {}
        else:
            self.data = deepcopy(DEFAULT_STATE)

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.dump(self.data, f, allow_unicode=True, sort_keys=False)

    # ---- Current stage/module/status ----

    def get_current_stage(self) -> str:
        return self.data.get("current", {}).get("stage", "M1S01")

    def get_current_module(self) -> str:
        return self.data.get("current", {}).get("module", "M1")

    def get_current_status(self) -> str:
        return self.data.get("current", {}).get("status", "initialized")

    def set_stage(self, stage: str, status: str = "in_progress") -> None:
        self.data["current"]["stage"] = stage
        self.data["current"]["module"] = _get_module_of(stage)
        self.data["current"]["status"] = status
        self.save()

    def get_module_status(self, module: str) -> dict[str, Any]:
        return self.data.get("modules", {}).get(module, {"status": "unknown"})

    def set_module_status(self, module: str, status: str, last_stage: Optional[str] = None) -> None:
        if "modules" not in self.data:
            self.data["modules"] = dict(DEFAULT_STATE["modules"])
        self.data["modules"][module] = {
            "status": status,
            "completed_at": datetime.now().isoformat() if status == "completed" else None,
            "last_stage": last_stage,
        }
        self.save()

    def mark_module_completed(self, module: str, last_stage: str) -> None:
        self.set_module_status(module, "completed", last_stage)

    # ---- Venue ----

    def get_venue(self) -> dict[str, Any]:
        return self.data.get("project", {}).get("venue", {"id": "arxiv", "name": "arXiv"})

    def set_venue(self, venue_id: str, venue_config: Optional[dict[str, Any]] = None) -> None:
        if "project" not in self.data:
            self.data["project"] = {}
        self.data["project"]["venue"] = {
            "id": venue_id,
            "name": venue_config.get("name", venue_id) if venue_config else venue_id,
            "page_limit": venue_config.get("page_limit") if venue_config else None,
            "page_limit_note": venue_config.get("page_limit_note", "") if venue_config else "",
            "format": venue_config.get("format", "") if venue_config else "",
            "style_package": venue_config.get("style_package", "") if venue_config else "",
            "template_dir": venue_config.get("template_dir", "") if venue_config else "",
            "set_at": datetime.now().isoformat(),
        }
        self.save()

    # ---- History ----

    def record_completion(self, stage: str, agent: str, output: Path) -> None:
        entry = {
            "stage": stage,
            "agent": agent,
            "completed_at": datetime.now().isoformat(),
            "output": str(output),
        }
        self.data.setdefault("history", []).append(entry)
        stale = self.data.get("stale_stages", [])
        if stage in stale:
            stale.remove(stage)
            self.data["stale_stages"] = stale
        self.save()

    # ---- Backtrack ----

    def record_backtrack(
        self,
        from_stage: str,
        to_stage: str,
        reason: str,
        direction: str = "",
        advice: Optional[dict[str, Any]] = None,
    ) -> None:
        target_module = _get_module_of(to_stage)
        entry = {
            "from": from_stage,
            "to": to_stage,
            "reason": reason,
            "direction": direction,
            "target_module": target_module,
            "timestamp": datetime.now().isoformat(),
            "type": "revise" if from_stage == to_stage else "backtrack",
        }
        if advice:
            entry["advice"] = advice
            self.record_stage_backtrack_advice(to_stage, advice, save=False)
            stage_map = advice.get("stage_backtrack_advice")
            if isinstance(stage_map, dict):
                for stage, stage_advice in stage_map.items():
                    if isinstance(stage_advice, dict):
                        self.record_stage_backtrack_advice(str(stage), stage_advice, save=False)
        self.data.setdefault("backtrack_log", []).append(entry)

        count = self.data.setdefault("spiral_count", {}).get(target_module, 0)
        self.data["spiral_count"][target_module] = count + 1

        self._mark_downstream_stale(from_stage, to_stage)
        self._flag_gate_re_review(to_stage)
        self.save()

    def record_stage_backtrack_advice(
        self,
        stage: str,
        advice: dict[str, Any],
        *,
        save: bool = True,
    ) -> None:
        """Persist stage-specific backtrack advice for later dispatch."""
        if not stage:
            return
        all_stages = set(_get_all_stages())
        if stage not in all_stages:
            return
        stored = dict(advice)
        stored["target_stage"] = stage
        stored.setdefault("recorded_at", datetime.now().isoformat())
        self.data.setdefault("stage_backtrack_advice", {})[stage] = stored
        if save:
            self.save()

    def get_stage_backtrack_advice_map(self) -> dict[str, Any]:
        return dict(self.data.get("stage_backtrack_advice", {}))

    def _mark_downstream_stale(self, from_stage: str, to_stage: str) -> None:
        all_stages = _get_all_stages()
        try:
            to_idx = all_stages.index(to_stage)
            from_idx = all_stages.index(from_stage)
        except ValueError:
            return
        stale = all_stages[to_idx + 1 : from_idx + 1]
        existing = set(self.data.get("stale_stages", []))
        existing.update(stale)
        self.data["stale_stages"] = sorted(existing, key=lambda s: all_stages.index(s))

    def _flag_gate_re_review(self, to_stage: str, from_stage: str = "") -> None:
        target_module = _get_module_of(to_stage)
        from_module = _get_module_of(from_stage) if from_stage else self.get_current_module()
        modules = list(_get_module_stages().keys())
        try:
            t_idx = modules.index(target_module)
            f_idx = modules.index(from_module)
            for idx in range(t_idx, f_idx + 1):
                mod = modules[idx]
                gate_id = f"G{mod[1:]}"
                self.data.setdefault("gate_re_review", {})[gate_id] = {
                    "needs_re_review": True,
                    "flagged_at": datetime.now().isoformat(),
                    "reason": f"Backtrack to {to_stage} (Module {target_module})",
                }
        except ValueError:
            gate_id = f"G{target_module[1:]}"
            self.data.setdefault("gate_re_review", {})[gate_id] = {
                "needs_re_review": True,
                "flagged_at": datetime.now().isoformat(),
                "reason": f"Backtrack to {to_stage}",
            }

    def get_spiral_count(self, module: Optional[str] = None) -> int:
        counts = self.data.get("spiral_count", {})
        if module:
            return counts.get(module, 0)
        return max(counts.values()) if counts else 0

    def is_spiral_limit_exceeded(self, module: str, limit: int = 3) -> bool:
        return self.data.get("spiral_count", {}).get(module, 0) >= limit

    # ---- Staleness tracking ----

    def is_stale(self, stage: str) -> bool:
        return stage in self.data.get("stale_stages", [])

    def get_stale_stages(self) -> list[str]:
        return list(self.data.get("stale_stages", []))

    def get_latest_backtrack_advice(self, stage: Optional[str] = None) -> dict[str, Any]:
        """Return the latest backtrack advice relevant to a stage."""
        if stage is not None:
            stage_advice = self.data.get("stage_backtrack_advice", {}).get(stage)
            if isinstance(stage_advice, dict) and stage_advice:
                return stage_advice
        stale = set(self.data.get("stale_stages", []))
        for entry in reversed(self.data.get("backtrack_log", [])):
            advice = entry.get("advice") or {}
            if not advice:
                continue
            if stage is None:
                return advice
            if entry.get("to") == stage or advice.get("target_stage") == stage or stage in stale:
                return advice
        return {}

    def clear_stale(self, stage: str) -> None:
        stale = self.data.get("stale_stages", [])
        if stage in stale:
            stale.remove(stage)
            self.data["stale_stages"] = stale
            self.data.get("stage_backtrack_advice", {}).pop(stage, None)
            self.save()

    def clear_all_stale(self) -> None:
        self.data["stale_stages"] = []
        self.data["stage_backtrack_advice"] = {}
        self.save()

    # ---- Gate re-review ----

    def gate_needs_re_review(self, gate_id: str) -> bool:
        return self.data.get("gate_re_review", {}).get(gate_id, {}).get("needs_re_review", False)

    def get_gates_needing_re_review(self) -> list[str]:
        return [
            g for g, v in self.data.get("gate_re_review", {}).items()
            if v.get("needs_re_review", False)
        ]

    def clear_gate_re_review(self, gate_id: str) -> None:
        if gate_id in self.data.get("gate_re_review", {}):
            self.data["gate_re_review"][gate_id]["needs_re_review"] = False
            self.data["gate_re_review"][gate_id]["reviewed_at"] = datetime.now().isoformat()
            self.save()

    # ---- Decision log ----

    def log_decision(
        self,
        decision_type: str,
        stage: str,
        summary: str,
        details: str = "",
    ) -> None:
        entry = {
            "type": decision_type,
            "stage": stage,
            "summary": summary,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        }
        self.data.setdefault("decision_log", []).append(entry)
        self.save()

    # ---- Settings ----

    def is_auto_advance_enabled(self) -> bool:
        return self.data.get("settings", {}).get("auto_advance_modules", False)

    def set_auto_advance(self, enabled: bool) -> None:
        if "settings" not in self.data:
            self.data["settings"] = {}
        self.data["settings"]["auto_advance_modules"] = enabled
        self.save()

    # ---- Session / Orchestrator lock ----

    def get_session(self) -> dict[str, Any]:
        return self.data.get("session", {
            "orchestrator_lock": True,
            "lock_set_at": "",
            "last_agent_mode": "orchestrator",
        })

    def assert_orchestrator_mode(self) -> dict[str, Any]:
        """Return session lock status for orchestrator enforcement."""
        return self.get_session()

    def set_agent_mode(self, mode: str) -> None:
        """Record the current agent mode in durable state.

        mode should be one of: orchestrator, executor, reviewer.
        """
        if "session" not in self.data:
            self.data["session"] = {
                "orchestrator_lock": True,
                "lock_set_at": "",
                "last_agent_mode": "orchestrator",
            }
        self.data["session"]["last_agent_mode"] = mode
        self.data["session"]["lock_set_at"] = datetime.now().isoformat()
        # When the main agent is active, the lock is always True
        self.data["session"]["orchestrator_lock"] = (mode == "orchestrator")
        self.save()

    def is_orchestrator_locked(self) -> bool:
        return self.get_session().get("orchestrator_lock", True)


# Lazy import helpers to avoid circular imports

def _get_module_stages() -> dict[str, list[str]]:
    from .project import MODULE_STAGES
    return MODULE_STAGES


def _get_module_of(stage: str) -> str:
    for mod, stages in _get_module_stages().items():
        if stage in stages:
            return mod
    return "M1"


def _get_all_stages() -> list[str]:
    return [s for stages in _get_module_stages().values() for s in stages]
