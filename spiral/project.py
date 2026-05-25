"""Project lifecycle: create, initialize, archive."""

from __future__ import annotations

import re
import shutil
import sys
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional, Any

from .state import PipelineState
from .survey_memory import SurveyMemoryManager
from .project_entry import ENTRY_BRIEF_FILENAME, build_project_entry

# Module -> Stage mapping (6 modules)
MODULE_STAGES = {
    "M1": ["M1S01", "M1S02", "M1S03", "M1S04", "M1S05"],
    "M2": ["M2S01", "M2S02", "M2S03", "M2S04", "M2S05", "M2S06"],
    "M3": ["M3S01", "M3S02", "M3S03", "M3S04"],
    "M4": ["M4S01", "M4S02", "M4S03", "M4S04"],
    "M5": ["M5S01", "M5S02", "M5S03", "M5S04", "M5S05", "M5S06", "M5S07", "M5S08"],
    "M6": ["M6S01", "M6S02", "M6S03", "M6S04", "M6S05", "M6S06"],
}

GATE_STAGES = {
    "G1": "M1S05",
    "G2": "M2S06",
    "G3": "M3S04",
    "G4": "M4S04",
    "G5": "M5S08",
    "G6": "M6S06",
}

# Survey Agent for M1S01-S02, Ideation Agent for M1S03-S05, dedicated agents for M2-M5
AGENT_FOR_STAGE = {
    # M1: Domain Survey
    "M1S01": "survey",
    "M1S02": "survey",
    "M1S03": "ideation",
    "M1S04": "ideation",
    "M1S05": "ideation",
    # M2: Method Design
    "M2S01": "method",
    "M2S02": "method",
    "M2S03": "method",
    "M2S04": "method",
    "M2S05": "method",
    "M2S06": "method",
    # M3: Experiment Implementation & Execution
    "M3S01": "experiment",
    "M3S02": "experiment",
    "M3S03": "experiment",
    "M3S04": "analysis",
    # M4: Deep Analysis
    "M4S01": "analysis",
    "M4S02": "analysis",
    "M4S03": "experiment",
    "M4S04": "analysis",
    # M5: Writing & Finalization
    "M5S01": "analysis",
    "M5S02": "writing",
    "M5S03": "writing",
    "M5S04": "writing",
    "M5S05": "writing",
    "M5S06": "writing",
    "M5S07": "writing",
    "M5S08": "writing",
    # M6: Submission Review & Revision Loop
    "M6S01": "submission",
    "M6S02": "submission",
    "M6S03": "rebuttal",
    "M6S04": "rebuttal",
    # M6S05 is routed by the conductor, but the stage output itself is written
    # by a dedicated subagent so the main agent never writes stage content.
    "M6S05": "revision",
    "M6S06": "rebuttal",
}

_WIN_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def sanitize_folder_name(name: str) -> str:
    name = name.strip()
    name = name.replace(" ", "-")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = name.rstrip(" .")
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    if name.upper() in _WIN_RESERVED:
        name = name + "_"
    return name or "untitled"


def _load_venue_registry() -> dict[str, Any]:
    registry_path = Path(__file__).parent.parent / "config" / "venue_registry.yaml"
    if registry_path.exists():
        with open(registry_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _get_venue_config(venue_id: str) -> Optional[dict[str, Any]]:
    registry = _load_venue_registry()
    venues = registry.get("venues", {})
    return venues.get(venue_id)


def _apply_env_overrides(text: str, overrides: dict[str, Any]) -> str:
    """Apply user-supplied execution environment overrides to the YAML template.

    Supports dotted keys for nested access, e.g. ``ssh.host``.
    """
    import yaml

    try:
        data = yaml.safe_load(text)
    except Exception:
        return text

    if not isinstance(data, dict):
        return text

    for key, value in overrides.items():
        if value is None:
            continue
        parts = key.split(".")
        target = data
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value

    return yaml.dump(data, allow_unicode=True, sort_keys=False)


class ProjectManager:
    """High-level project creation and management."""

    @staticmethod
    def create(
        topic: str,
        display_name: Optional[str] = None,
        projects_root: Optional[Path] = None,
        venue: Optional[str] = None,
        keywords: Optional[list[str]] = None,
        reference_papers: Optional[list[str]] = None,
        foundation_papers: Optional[list[str]] = None,
        input_manifest: Optional[str | Path] = None,
        notes: str = "",
        execution_env: Optional[dict[str, Any]] = None,
    ) -> Path:
        framework_root = Path(__file__).parent.parent.resolve()
        if projects_root is None:
            projects_root = framework_root / "projects"

        projects_root.mkdir(parents=True, exist_ok=True)

        registry = _load_venue_registry()
        default_venue = registry.get("default_venue", "arxiv")
        venue_id = venue if venue else default_venue
        venue_config = _get_venue_config(venue_id)
        if venue_config is None:
            available = list(registry.get("venues", {}).keys())
            raise ValueError(f"Unknown venue '{venue_id}'. Available: {available}")

        folder_base = display_name if display_name else topic
        folder_name = sanitize_folder_name(folder_base)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        proj_dir = projects_root / f"{folder_name}-{ts}"
        proj_dir.mkdir(parents=True, exist_ok=False)

        # Stage draft folders
        drafts_dir = proj_dir / "drafts"
        drafts_dir.mkdir(exist_ok=True)
        for module, stages in MODULE_STAGES.items():
            for stage in stages:
                (drafts_dir / stage).mkdir(parents=True, exist_ok=True)

        # Supporting directories
        for sub in ["state", "knowledge", "knowledge/reviews", "artifacts", "experiments", "config"]:
            (proj_dir / sub).mkdir(parents=True, exist_ok=True)

        # Module knowledge directories
        for mod in MODULE_STAGES.keys():
            (proj_dir / "knowledge" / mod).mkdir(exist_ok=True)

        # Normalize the flexible project entry into one durable manifest.
        display_str = display_name if display_name else topic
        entry_brief = build_project_entry(
            project_root=proj_dir,
            topic=topic,
            display_name=display_str,
            keywords=keywords,
            reference_inputs=reference_papers,
            foundation_inputs=foundation_papers,
            input_manifest=input_manifest,
            notes=notes,
        )
        entry_brief_path = proj_dir / "state" / ENTRY_BRIEF_FILENAME
        entry_brief_path.write_text(
            yaml.safe_dump(entry_brief, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        # Copy venue template
        template_dir = framework_root / "templates" / "venue" / venue_config.get("template_dir", venue_id)
        latex_template_dir = proj_dir / "artifacts" / "latex_template"
        if template_dir.exists():
            for pattern in ["*.sty", "*.bst", "*.cls", "*.tex", "README.md"]:
                for src in template_dir.rglob(pattern):
                    if src.is_file():
                        rel = src.relative_to(template_dir)
                        dst = latex_template_dir / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)

        # Initialize pipeline state
        state = PipelineState(proj_dir)
        state.data["project"]["name"] = folder_name
        state.data["project"]["display_name"] = display_name if display_name else topic
        state.data["project"]["topic"] = topic
        state.data["project"]["keywords"] = entry_brief.get("project", {}).get("keywords", [])
        state.data["project"]["entry_brief"] = f"state/{ENTRY_BRIEF_FILENAME}"
        state.data["project"]["entry_mode"] = entry_brief.get("project", {}).get("entry_mode", "topic_only")
        state.data["project"]["anchor_count"] = entry_brief.get("project", {}).get("anchor_count", 0)
        state.data["project"]["notes"] = entry_brief.get("notes", "")
        state.data["project"]["created_at"] = datetime.now().isoformat()
        state.set_venue(venue_id, venue_config)
        state.save()

        # Initialize Survey Memory for M1 (auto-connects to public literature DB)
        survey_mgr = SurveyMemoryManager(proj_dir, auto_connect=True)
        try:
            survey_mgr.init(topic)
        finally:
            survey_mgr.close()

        # Initialize logs
        anchor_lines = []
        for anchor in entry_brief.get("anchors", []):
            value = anchor.get("title_hint") or anchor.get("url") or anchor.get("canonical_value") or anchor.get("raw_value", "")
            anchor_lines.append(
                f">   - {anchor.get('id')}: {anchor.get('role')} / {anchor.get('kind')} / "
                f"{anchor.get('input_type')} / {value}"
            )
        anchors_block = "\n".join(anchor_lines) if anchor_lines else ">   - none"
        keywords_str = ", ".join(entry_brief.get("keywords", [])) or "none"
        (proj_dir / "state" / "decision_log.md").write_text(
            f"# Decision Log — {display_str}\n\n"
            f"> Project: `{folder_name}`\n"
            f"> Display Name: {display_str}\n"
            f"> Topic: {topic}\n"
            f"> Keywords: {keywords_str}\n"
            f"> Entry Brief: `state/{ENTRY_BRIEF_FILENAME}`\n"
            f"> Anchors:\n{anchors_block}\n"
            f"> Created: {ts}\n\n",
            encoding="utf-8",
        )
        (proj_dir / "state" / "spiral_log.md").write_text(
            f"# Spiral Log — {display_str}\n\n",
            encoding="utf-8",
        )

        # Copy stage templates
        tpl_root = framework_root / "templates" / "stage"
        if tpl_root.exists():
            for stage in [s for stages in MODULE_STAGES.values() for s in stages]:
                tpl = tpl_root / f"{stage}_template.md"
                if tpl.exists():
                    shutil.copy(tpl, drafts_dir / stage / f"{stage}_draft.md")
            # Copy auxiliary templates (e.g., pre-idea draft)
            for aux_tpl in tpl_root.glob("*_pre_*.md"):
                # e.g., M1S03_pre_idea_draft_template.md -> drafts/M1S03/pre_idea_draft.md
                parts = aux_tpl.stem.split("_")
                if len(parts) >= 2 and parts[0].startswith("M"):
                    stage_id = parts[0]
                    target_dir = drafts_dir / stage_id
                    if target_dir.exists():
                        # Strip the leading stage_id and _template suffix
                        # M1S03_pre_idea_draft_template.md -> pre_idea_draft.md
                        raw_name = aux_tpl.name.replace("_template", "")
                        if raw_name.startswith(stage_id + "_"):
                            raw_name = raw_name[len(stage_id)+1:]
                        shutil.copy(aux_tpl, target_dir / raw_name)

        # Copy execution environment configuration template
        env_config_tpl = framework_root / "config" / "execution_env.yaml"
        if env_config_tpl.exists():
            env_config_dst = proj_dir / "config" / "execution_env.yaml"
            env_config_text = env_config_tpl.read_text(encoding="utf-8")
            # Replace placeholders with project-specific values
            env_config_text = env_config_text.replace("{project_name}", folder_name)

            # Apply user-provided execution environment overrides
            env_overrides = execution_env or {}
            env_config_text = _apply_env_overrides(env_config_text, env_overrides)

            env_config_dst.write_text(env_config_text, encoding="utf-8")

        # Copy execution environment helper templates
        env_helper_dir = framework_root / "config" / "execution_env_templates"
        if env_helper_dir.exists():
            for helper_tpl in env_helper_dir.iterdir():
                if helper_tpl.is_file():
                    dst = proj_dir / helper_tpl.name.replace(".template", "")
                    helper_text = helper_tpl.read_text(encoding="utf-8")
                    helper_text = helper_text.replace("{project_name}", folder_name)
                    dst.write_text(helper_text, encoding="utf-8")

        # Copy author info template
        author_info_tpl = framework_root / "config" / "author_info.yaml"
        if author_info_tpl.exists():
            shutil.copy2(author_info_tpl, proj_dir / "config" / "author_info.yaml")

        # Auto-run environment probe to fill execution_env.yaml
        env_probe_script = framework_root / "scripts" / "env_probe.py"
        if env_probe_script.exists():
            import subprocess as _sub
            try:
                _sub.run(
                    [sys.executable, str(env_probe_script), "--project", str(proj_dir)],
                    capture_output=True, timeout=60, check=False,
                )
            except Exception:
                pass  # env_probe is best-effort; don't fail project creation

        # Mark onboarding pending in pipeline state
        state.data["current"]["status"] = "onboarding_pending"
        state.data["current"]["stage"] = "onboarding"
        state.data["current"]["module"] = "onboarding"
        state.save()

        # Determine execution mode from the generated execution_env.yaml
        env_config_path = proj_dir / "config" / "execution_env.yaml"
        exec_mode = "local"
        try:
            if env_config_path.exists():
                env_data = yaml.safe_load(env_config_path.read_text(encoding="utf-8")) or {}
                exec_mode = env_data.get("execution", {}).get("mode", "local")
        except Exception:
            exec_mode = "local"

        # Generate onboarding checklist (conditional on execution mode)
        ssh_section = (
            f"1. **SSH 配置**（`execution.mode = ssh`，必须填写）:\n"
            f"   - [ ] `ssh.host`: 远程服务器地址\n"
            f"   - [ ] `ssh.user`: SSH 用户名\n"
            f"   - [ ] `ssh.port`: SSH 端口（默认 22）\n"
            f"   - [ ] `ssh.auth_method`: key 或 password\n"
            f"   - [ ] `ssh.identity_file`: 私钥路径（如使用 key 认证）\n"
            f"   - [ ] `ssh.conda_env_name`: 远程 conda 环境名（如有）\n"
            f"   - [ ] `ssh.workspace_path`: 远程工作路径\n\n"
            f"2. **作者信息**: `config/author_info.yaml` 中的 authors, affiliation, email\n\n"
        ) if exec_mode == "ssh" else (
            f"1. **本地环境确认**（`execution.mode = local`，SSH 配置无需填写）:\n"
            f"   - [ ] `local.env_name`: 本地环境名（默认: autopaper2-{folder_name}）\n"
            f"   - [ ] `local.cuda_version`: CUDA 版本是否正确\n"
            f"   - [ ] `local.env_manager`: 环境管理工具（conda/uv/venv）\n\n"
            f"2. **作者信息**: `config/author_info.yaml` 中的 authors, affiliation, email\n\n"
        )

        onboarding_path = proj_dir / "state" / "onboarding_checklist.md"
        onboarding_path.write_text(
            f"# Project Onboarding Checklist — {display_str}\n\n"
            f"> 项目已创建。在正式开始研究前，请确认以下配置。\n\n"
            f"## 自动探测结果（请确认）\n\n"
            f"- 执行模式: `{exec_mode}`\n"
            f"- 执行环境配置已自动生成: `config/execution_env.yaml`\n"
            f"- 作者信息模板已复制: `config/author_info.yaml`\n"
            f"- LaTeX 模板已复制: `artifacts/latex_template/`\n\n"
            f"## 需手动填写\n\n"
            f"{ssh_section}"
            f"3. **投稿目标确认**: Venue={venue_config.get('name', venue_id)}, Page Limit={venue_config.get('page_limit', 'N/A')}\n\n"
            f"## 下一步\n\n"
            f"请补全上述配置后，回复 **'已填写'**，或运行 `python scripts/state_manager.py onboarding-done {proj_dir}` 继续。\n",
            encoding="utf-8",
        )

        print(f"[PROJECT] Created {proj_dir}")
        print(f"          Display Name: {display_str}")
        print(f"          Topic: {topic}")
        if entry_brief.get("keywords"):
            print(f"          Keywords: {', '.join(entry_brief.get('keywords', []))}")
        print(f"          Entry Brief: state/{ENTRY_BRIEF_FILENAME}")
        print(f"          Anchors: {entry_brief.get('project', {}).get('anchor_count', 0)}")
        print(f"          Venue: {venue_config.get('name', venue_id)}")
        print(f"          Page Limit: {venue_config.get('page_limit', 'N/A')}")
        print(f"[ONBOARDING] Status: PENDING — Please complete config/execution_env.yaml and config/author_info.yaml")
        print(f"             Checklist: state/onboarding_checklist.md")
        return proj_dir
