#!/usr/bin/env python3
"""Integration tests for M6 module (Submission Review & Revision Loop)."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from spiral.project import ProjectManager, MODULE_STAGES
from spiral.state import PipelineState
from scripts.state_manager import cmd_advance
from utils.file_guard import (
    get_canonical_output_path,
    check_single_file_principle,
    validate_stage_output,
    validate_gate_review,
)
from utils.gate_rubric import gate_critic_review_paths, get_gate_rubric
from utils.stage_gate import check_stage


def _call_advance(
    project_dir: str,
    stage: str,
    agent: str,
    output_file: str,
    force: bool = False,
    skip_gates: bool = False,
) -> tuple[int | None, str]:
    stdout_capture = io.StringIO()
    exit_code = None
    try:
        with patch("sys.stdout", new=stdout_capture):
            cmd_advance(project_dir, stage, agent, output_file, force=force, skip_gates=skip_gates)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
    return exit_code, stdout_capture.getvalue()


class TestM6FileGuard(unittest.TestCase):
    def test_m6_canonical_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            proj.mkdir()
            assert get_canonical_output_path(proj, "M6S01") == proj / "knowledge" / "M6" / "M6S01_submission_audit.md"
            assert get_canonical_output_path(proj, "M6S03") == proj / "knowledge" / "M6" / "M6S03_review_parsing.md"
            assert get_canonical_output_path(proj, "M6S06") == proj / "knowledge" / "M6" / "M6S06_revision_validation.md"

    def test_m6_single_file_principle_allows_companion_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            stage_dir = proj / "knowledge" / "M6"
            stage_dir.mkdir(parents=True)
            (stage_dir / "M6S03_review_parsing.md").write_text("# primary", encoding="utf-8")
            (stage_dir / "M6S03_review_matrix.md").write_text("# companion", encoding="utf-8")
            ok, msg = check_single_file_principle(proj, "M6S03")
            assert ok, msg

    def test_m6_stage_output_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "test_project"
            out = proj / "knowledge" / "M6" / "M6S04_rebuttal_strategy.md"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("# test", encoding="utf-8")
            ok, msg = validate_stage_output(proj, "M6S04", out)
            assert ok, msg


class TestM6StateFlow(unittest.TestCase):
    def _setup_project_at_m6s06(self, tmp_path: Path) -> Path:
        proj = tmp_path / "m6_proj"
        proj.mkdir(parents=True)
        (proj / "state").mkdir(parents=True, exist_ok=True)

        state = PipelineState(proj)
        state.data["project"] = {
            "name": proj.name,
            "topic": "M6 Test",
            "display_name": "M6 Test",
            "created_at": "2024-01-01T00:00:00",
            "venue": {"id": "arxiv", "name": "arXiv"},
        }
        state.set_stage("M6S06", "in_progress")
        state.set_module_status("M5", "completed", "M5S09")
        state.set_module_status("M6", "in_progress", "M6S05")

        (proj / "knowledge" / "M6").mkdir(parents=True, exist_ok=True)
        (proj / "knowledge" / "reviews").mkdir(parents=True, exist_ok=True)
        (proj / "artifacts").mkdir(parents=True, exist_ok=True)
        (proj / "artifacts" / "submission_package").mkdir(parents=True, exist_ok=True)

        (proj / "knowledge" / "M6" / "M6S01_submission_audit.md").write_text("# M6S01\n", encoding="utf-8")
        (proj / "knowledge" / "reviews" / "M6S01_internal_peer_review.md").write_text(
            "# Internal Review\n\n"
            "## Reviewer A\n"
            "## Reviewer B\n"
            "## Reviewer C\n"
            "- **Internal Review Score**: 8.5/10\n"
            "- **Unresolved high-priority issues**: 0\n"
            "- revision loop: completed\n",
            encoding="utf-8",
        )
        (proj / "knowledge" / "M6" / "M6S02_external_review_submission.md").write_text("# M6S02\n", encoding="utf-8")
        (proj / "knowledge" / "M6" / "M6S02_submission_log.json").write_text(
            '{"platform": "paperreview.ai", "url": "https://paperreview.ai/", '
            '"submitted_at": "2026-05-23T00:00:00", "pdf_path": "artifacts/paper.pdf", '
            '"email": "review@example.com", "status": "success", '
            '"tracking": {"confirmation_id": "SIM-1"}}',
            encoding="utf-8",
        )
        (proj / "knowledge" / "M6" / "M6S03_review_parsing.md").write_text("# M6S03\n", encoding="utf-8")
        (proj / "knowledge" / "M6" / "M6S03_review_email.json").write_text(
            '{"status": "success", "found_email": {"subject": "paperreview.ai review", '
            '"from": "noreply@paperreview.ai", "message_id": "<sim-1@example.com>", '
            '"body": "Soundness 8. Reviewer asks for clearer evidence."}}',
            encoding="utf-8",
        )
        (proj / "knowledge" / "M6" / "M6S03_review_matrix.md").write_text(
            "# Matrix\n\n"
            "### PR-A1\n"
            "- **original_text**: Reviewer asks for clearer evidence.\n"
            "- **class**: evidence_gap\n"
            "- **severity**: High\n"
            "- **preliminary_route**: evidence_repackaging\n",
            encoding="utf-8",
        )
        (proj / "knowledge" / "M6" / "M6S04_rebuttal_strategy.md").write_text(
            "# M6S04\n\n"
            "classification summary 意见分类汇总 Action Plan\n"
            "PR-A1 maps to target_stage M5S05 for evidence repackaging.\n"
            "backtrack mapping 回溯目标映射 target_stage\n"
            "honest limitation 诚实限制 cannot_fully_address none.\n",
            encoding="utf-8",
        )
        (proj / "knowledge" / "M6" / "M6S04_action_plan.md").write_text(
            "# Action Plan\n\n"
            "### PR-A1\n"
            "- class: evidence_gap\n"
            "- severity: High\n"
            "- target_stage: M5S05\n"
            "- required_fix: clarify evidence provenance\n"
            "- success_criteria: reviewer evidence confusion is resolved\n"
            "- rebuild_mode: incremental_replay\n"
            "- rerun_scope: M5S05 -> M5S06 -> M5S03 -> M5S07 -> M5S08 -> M5S09\n"
            "- priority: P1\n",
            encoding="utf-8",
        )
        (proj / "knowledge" / "M6" / "M6S05_revision_execution.md").write_text(
            "# M6S05\n\n"
            "revision list 修订清单 Action Plan ID PR-A1 done.\n"
            "## PR-A1\n"
            "- status: completed / resolved\n"
            "- evidence path: knowledge/M5/M5S05_experiments_results.md\n"
            "- output file: artifacts/paper.tex\n"
            "recompile 重新编译 paper.pdf complete.\n"
            "negative results 负面结果 none.\n",
            encoding="utf-8",
        )
        (proj / "knowledge" / "M6" / "M6S06_revision_validation.md").write_text(
            "# M6S06 Revision Validation\n\n"
            "## High 解决率\n"
            "- 100% (1/1)\n\n"
            "## 综合解决度\n"
            "- 100%\n\n"
            "## Action Plan 验证\n"
            "### PR-A1\n"
            "- status: resolved / PASS\n"
            "- M6S05 evidence path: knowledge/M6/M6S05_revision_execution.md\n\n"
            "## 质量保持度\n"
            "- Gate G5\n\n"
            "## 外部审稿证据复核\n"
            "- M6S02_submission_log.json status=success, paperreview.ai tracking present.\n"
            "- M6S03_review_email.json status=success, raw email body and metadata present.\n"
            "- M6S03_review_matrix.md PR-* atomic items present.\n\n"
            "**判定结果**: PASS\n",
            encoding="utf-8",
        )
        (proj / "knowledge" / "handoff_M6_completion.md").write_text("# handoff", encoding="utf-8")
        (proj / "artifacts" / "paper.pdf").write_text("pdf", encoding="utf-8")
        (proj / "artifacts" / "paper.tex").write_text("tex", encoding="utf-8")
        (proj / "artifacts" / "submission_package" / "paper_final.pdf").write_text("pdf", encoding="utf-8")
        (proj / "artifacts" / "submission_package" / "source.zip").write_text("zip", encoding="utf-8")
        (proj / "knowledge" / "reviews" / "M6S06_revision_validation_review.md").write_text(
            "# M6S06 Review\n\nVerdict: PASS\n",
            encoding="utf-8",
        )

        return proj

    def test_m6s06_advances_to_waiting_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._setup_project_at_m6s06(Path(tmp))
            output_file = str(proj / "knowledge" / "M6" / "M6S06_revision_validation.md")
            exit_code, output = _call_advance(str(proj), "M6S06", "rebuttal", output_file)
            assert exit_code is None, output
            assert "waiting_gate" in output, output
            state = PipelineState(proj)
            assert state.get_current_stage() == "M6S06"
            assert state.get_current_status() == "waiting_gate"

    def test_m6s06_blocks_incomplete_external_review_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._setup_project_at_m6s06(Path(tmp))
            (proj / "knowledge" / "M6" / "M6S02_submission_log.json").write_text(
                '{"status": "success"}',
                encoding="utf-8",
            )

            ok, messages = check_stage(proj, "M6S06")

            assert not ok
            joined = "\n".join(messages)
            assert "submission log missing paperreview.ai platform/url" in joined
            assert "submission log missing tracking info" in joined

    def test_m6s04_blocks_action_plan_missing_review_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._setup_project_at_m6s06(Path(tmp))
            (proj / "knowledge" / "M6" / "M6S04_action_plan.md").write_text(
                "# Action Plan\n\n"
                "### PR-Z9\n"
                "- class: text_revision\n"
                "- severity: Low\n"
                "- target_stage: M5S03\n"
                "- required_fix: unrelated edit\n"
                "- success_criteria: unrelated edit complete\n"
                "- rebuild_mode: incremental_replay\n"
                "- rerun_scope: M5S03 -> M5S07 -> M5S08 -> M5S09\n"
                "- priority: P2\n",
                encoding="utf-8",
            )
            (proj / "knowledge" / "reviews" / "M6S04_rebuttal_strategy_review.md").write_text(
                "# M6S04 Review\n\nVerdict: PASS\n",
                encoding="utf-8",
            )

            ok, messages = check_stage(proj, "M6S04")

            assert not ok
            assert any("action plan missing review item ids: PR-A1" in message for message in messages)

    def test_m6s05_blocks_missing_review_item_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._setup_project_at_m6s06(Path(tmp))
            (proj / "knowledge" / "M6" / "M6S05_revision_execution.md").write_text(
                "# M6S05\n\n"
                "revision list 修订清单 Action Plan ID PR-Z9 done.\n"
                "recompile 重新编译 paper.pdf complete.\n"
                "negative results 负面结果 none.\n",
                encoding="utf-8",
            )
            (proj / "knowledge" / "reviews" / "M6S05_revision_execution_review.md").write_text(
                "# M6S05 Review\n\nVerdict: PASS\n",
                encoding="utf-8",
            )

            ok, messages = check_stage(proj, "M6S05")

            assert not ok
            assert any("revision execution missing review item ids: PR-A1" in message for message in messages)

    def test_m6s06_blocks_unresolved_high_review_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._setup_project_at_m6s06(Path(tmp))
            text = (proj / "knowledge" / "M6" / "M6S06_revision_validation.md").read_text(encoding="utf-8")
            (proj / "knowledge" / "M6" / "M6S06_revision_validation.md").write_text(
                text.replace("- status: resolved / PASS", "- status: unresolved"),
                encoding="utf-8",
            )

            ok, messages = check_stage(proj, "M6S06")

            assert not ok
            assert any("PR-A1 validation is unresolved/failed/pending" in message for message in messages)

    def _write_gate_aggregate(self, proj: Path, gate_id: str) -> Path:
        gate_output = proj / "knowledge" / "reviews" / f"{gate_id}_aggregate.md"
        for critic, critic_path in gate_critic_review_paths(proj, gate_id).items():
            critic_path.parent.mkdir(parents=True, exist_ok=True)
            critic_path.write_text(
                f"# {gate_id} {critic} Review\n\nVerdict: PASS\n",
                encoding="utf-8",
            )
        lines = [
            f"# {gate_id} Aggregate Review",
            "",
            "Verdict: PASS",
            "",
            "## Rubric Results",
            "",
            "| Rubric ID | Verdict | Score | Evidence paths | Notes |",
            "|---|---|---|---|---|",
        ]
        for item in get_gate_rubric(gate_id).get("items", []):
            evidence = next(
                (rel for rel in item.get("evidence_examples", []) if (proj / rel).exists()),
                item.get("evidence_examples", ["knowledge/reviews"])[0],
            )
            lines.append(f"| {item.get('id', '')} | PASS | 2/2 | {evidence} | test evidence |")
        gate_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return gate_output

    def test_m6_gate_aggregate_completes_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._setup_project_at_m6s06(Path(tmp))
            stage_output = str(proj / "knowledge" / "M6" / "M6S06_revision_validation.md")
            exit_code, _ = _call_advance(str(proj), "M6S06", "rebuttal", stage_output)
            assert exit_code is None

            gate_output = self._write_gate_aggregate(proj, "G6")
            exit_code, output = _call_advance(str(proj), "M6S06", "critic_team", str(gate_output))
            assert exit_code is None, output
            assert "MODULE COMPLETE" in output or "ALL DONE" in output, output

            state = PipelineState(proj)
            assert state.get_module_status("M6").get("status") == "completed"
            assert validate_gate_review(proj, "G6", gate_output)[0]


if __name__ == "__main__":
    unittest.main()
