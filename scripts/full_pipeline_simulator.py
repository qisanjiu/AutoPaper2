#!/usr/bin/env python3
"""No-LLM full-pipeline simulator for AutoPaper2.

The simulator writes minimal but gate-valid stage/review artifacts, generates
dispatch packets, and advances the real pipeline state through M1-M6.  It is a
deterministic harness for orchestration mechanics; it does not claim to produce
scientific content.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

_framework_root = Path(__file__).parent.parent.resolve()
if str(_framework_root) not in sys.path:
    sys.path.insert(0, str(_framework_root))

from spiral.conductor import Conductor
from spiral.dispatch import (
    build_gate_review_packets,
    build_stage_execution_packet,
    build_stage_review_packets,
    write_packets,
)
from spiral.project import AGENT_FOR_STAGE, GATE_STAGES, MODULE_STAGES, ProjectManager
from spiral.state import PipelineState
from utils.file_guard import get_canonical_output_path
from utils.gate_rubric import get_gate_rubric
from scripts.context_budget import resolve_packet_path
from scripts.state_manager import cmd_advance


FLAT_STAGES = [stage for stages in MODULE_STAGES.values() for stage in stages]
GATE_BY_STAGE = {stage: gate for gate, stage in GATE_STAGES.items()}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    _write(path, json.dumps(data, ensure_ascii=False, indent=2))


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    _write(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def _passing_review(title: str = "Stage Review") -> str:
    return f"# {title}\n\nVerdict: PASS\n"


def _repair_review(stage: str) -> str:
    return (
        f"# Simulated Repair Review — {stage}\n\n"
        "Verdict: REVISE\n"
        f"- target_stage: {stage}\n"
        "- blocking_reason: simulator injected a stage-level revision request\n"
        "- required_fix: rewrite the simulated output and rerun the stage review\n"
        "- success_criteria: stage advances after the reviewer returns PASS\n"
        f"- evidence_paths: knowledge/{stage[:2]}/{get_canonical_output_path('.', stage).name}\n"
        "- rebuild_mode: incremental_replay\n"
        f"- rerun_scope: {stage}\n"
        "- handoff_updates: none\n"
    )


def _internal_peer_review() -> str:
    return (
        "# M6S01 Internal Peer Review\n\n"
        "## Reviewer A\n"
        "### Overall Score: 8/10\n"
        "## Reviewer B\n"
        "### Overall Score: 8/10\n"
        "## Reviewer C\n"
        "### Overall Score: 9/10\n\n"
        "## Aggregate Score\n"
        "- **Internal Review Score**: 8.4/10\n"
        "- **Unresolved high-priority issues**: 0\n\n"
        "## Revision Loop Decision\n"
        "- revision loop: completed\n"
        "- backtrack: no remaining blocking issues\n"
        "- Accept/Revert note: accept current version\n\n"
        "## Verdict\n"
        "Verdict: PASS\n"
    )


def _code_with_enough_lines() -> str:
    return "\n".join(
        [
            "def normalize(value):",
            "    return float(value)",
            "",
            "def load_rows(path):",
            "    rows = []",
            "    with open(path, 'r', encoding='utf-8') as handle:",
            "        for raw in handle:",
            "            rows.append(normalize(raw.strip() or 0))",
            "    return rows",
            "",
            "def train(rows):",
            "    total = 0.0",
            "    for value in rows:",
            "        total += value",
            "    return total / max(len(rows), 1)",
            "",
            "def evaluate(rows):",
            "    baseline = train(rows)",
            "    ours = baseline + 0.1",
            "    return {'baseline': baseline, 'ours': ours}",
            "",
            "if __name__ == '__main__':",
            "    print(evaluate([1, 2, 3]))",
        ]
    ) + "\n"


def _source(idx: int) -> dict[str, Any]:
    return {
        "id": f"src{idx}",
        "title": f"Representative Paper {idx}",
        "type": "academic",
        "credibility": 0.9,
        "authors": [f"Author{idx}", f"Coauthor{idx}"],
        "venue": "DemoConf",
        "year": 2024,
        "modality": "text",
        "task": "classification",
        "background": "Defines the problem background and scenario.",
        "contributions": "Contributes a relevant model and evaluation protocol.",
        "model": "Uses a neural model with a comparable baseline.",
        "method": "Describes the method components and training objective.",
        "experiment_setup": "Reports datasets, metrics, baselines, seeds, and protocol.",
        "results": "Reports quantitative results and statistical summary.",
        "analysis": "Includes ablation, failure analysis, and mechanism discussion.",
        "conclusion": "Concludes with limitations and future work.",
        "discovery_records": [
            {
                "search_surface": "Semantic Scholar",
                "query_text": f"representative paper {idx} method experiment",
                "result_rank": idx,
                "result_url": f"https://example.org/src{idx}",
                "screened_status": "retained",
                "retained_reason": "simulated literature evidence",
            }
        ],
        "artifacts": [
            {
                "artifact_type": "pdf",
                "uri": f"https://example.org/src{idx}.pdf",
                "local_path": f"literature/pdfs/src{idx}.pdf",
                "status": "available",
                "sha256": "",
                "license_note": "simulated open-access source",
            }
        ],
        "parse_profile": {
            "metadata_status": "complete",
            "fulltext_status": "parsed",
            "parse_status": "complete",
            "parse_backend": "source_log_card",
            "extraction_sources": ["pdf"],
            "missing_fields": [],
            "section_summaries": {
                "background": "Defines the problem background and scenario.",
                "contributions": "Contributes a relevant model and evaluation protocol.",
                "model": "Uses a neural model with a comparable baseline.",
                "method": "Describes the method components and training objective.",
                "experiment_setup": "Reports datasets, metrics, baselines, seeds, and protocol.",
                "results": "Reports quantitative results and statistical summary.",
                "analysis": "Includes ablation, failure analysis, and mechanism discussion.",
                "conclusion": "Concludes with limitations and future work.",
            },
            "downstream_signals": {
                "M2": {"method_reference": True, "core_mechanism": "method components and training objective"},
                "M3": {"experiment_protocol": True, "datasets_metrics_baselines": "datasets, metrics, baselines, seeds, and protocol"},
                "M4": {"analysis_patterns": True, "analysis": "ablation, failure analysis, and mechanism discussion"},
                "M5": {"citation_ready": True, "writing_context": "limitations and future work"},
            },
            "confidence": "high",
        },
    }


def _m2_source(idx: int, dimension: str, target_gap: str, domain: str, discovery_source: str) -> dict[str, Any]:
    source = _source(idx)
    source.update(
        {
            "search_dimension": dimension,
            "target_gap": target_gap,
            "source_domain": domain,
            "core_mechanism": f"Transferable mechanism from {domain}.",
            "adaptation_potential": "high",
            "relevance_to_our_gap": target_gap,
            "discovery_source": discovery_source,
            "discovery_query": f"{domain} {dimension} transferable mechanism",
            "abstract": "Summarizes the transferable method idea.",
            "method_summary": "Provides an algorithmic component that can be adapted.",
            "key_results": ["Improves a related metric under comparable constraints."],
        }
    )
    return source


def _prepare_m1_memory(root: Path) -> None:
    sources = [_source(i) for i in range(1, 6)]
    search_provenance = {
        "databases": ["public_db", "Semantic Scholar", "arXiv", "internet web search"],
        "inclusion_criteria": ["academic or authoritative", "contains method and experiment evidence"],
        "exclusion_criteria": ["off-topic", "no usable evidence"],
        "rounds": [
            {
                "round": 1,
                "goal": "breadth",
                "queries": ["simulated topic survey baseline", "dataset metric benchmark"],
                "retrieved_count": 40,
                "screened_count": 18,
                "retained_source_ids": ["src1", "src2"],
            },
            {
                "round": 2,
                "goal": "depth",
                "queries": ["GAP-MID target method", "failure analysis"],
                "retrieved_count": 25,
                "screened_count": 12,
                "retained_source_ids": ["src3", "src4"],
            },
            {
                "round": 3,
                "goal": "blindspot",
                "queries": ["recent negative result", "classic key author"],
                "retrieved_count": 18,
                "screened_count": 10,
                "retained_source_ids": ["src2", "src5"],
            },
        ],
        "blindspot_checks": {
            "recent_work": "checked latest and recent 6 months 2026 work",
            "negative_results": "checked negative/opposing/contradictory results",
            "seminal_work": "checked seminal classic foundation work",
            "key_authors": "checked key author and team follow-up work",
            "source_log_consistency": "checked Source Log consistency",
        },
        "perspective_coverage": {
            "scenario_task": {
                "status": "covered",
                "queries": ["scenario task application gap"],
                "source_ids": ["src1", "src2"],
                "finding": "Scenario/task perspective identifies deployment and task-level gaps.",
            },
            "model_method": {
                "status": "covered",
                "queries": ["model method architecture limitation"],
                "source_ids": ["src2", "src3"],
                "finding": "Model/method perspective identifies architecture and algorithm limits.",
            },
            "metric_performance": {
                "status": "covered",
                "queries": ["metric accuracy performance efficiency"],
                "source_ids": ["src3", "src4"],
                "finding": "Metric/performance perspective identifies accuracy and efficiency gaps.",
            },
            "dataset_protocol": {
                "status": "covered",
                "queries": ["dataset benchmark experiment protocol"],
                "source_ids": ["src4", "src5"],
                "finding": "Dataset/protocol perspective identifies benchmark and setup gaps.",
            },
            "failure_limitation": {
                "status": "covered",
                "queries": ["failure negative limitation defect"],
                "source_ids": ["src2", "src5"],
                "finding": "Failure/limitation perspective identifies negative results and defects.",
            },
            "baseline_comparison": {
                "status": "covered",
                "queries": ["baseline comparison sota comparator"],
                "source_ids": ["src1", "src5"],
                "finding": "Baseline/comparison perspective identifies comparator gaps.",
            },
        },
    }
    gaps = {
        "GAP-BIG": {
            "gap_type": "enhancement",
            "level": "large",
            "supporting_sources": ["src1", "src2"],
            "description": "Large scenario-level gap.",
        },
        "GAP-MID": {
            "gap_type": "validation",
            "level": "middle",
            "supporting_sources": ["src3", "src4"],
            "description": "Middle model/metric-level gap.",
        },
        "GAP-SMALL": {
            "gap_type": "vacancy",
            "level": "small",
            "supporting_sources": ["src2", "src5"],
            "description": "Small method limitation.",
        },
    }
    _write_yaml(
        root / "knowledge" / "M1" / "M1_source_log.yaml",
        {"sources": sources, "gap_evidence_map": gaps, "search_provenance": search_provenance},
    )

    source_registry = {src["id"]: src for src in sources}
    survey_memory = {
        "topic": "simulated topic",
        "search_batches": [
            {"batch_id": 1, "round": 1, "status": "passed", "queries": ["q1"], "sources_found": 5},
            {"batch_id": 2, "round": 2, "status": "passed", "queries": ["q2"], "sources_found": 5},
            {"batch_id": 3, "round": 3, "status": "passed", "queries": ["q3"], "sources_found": 5},
        ],
        "round_reviews": [
            {"round": 1, "verdict": "PASS"},
            {"round": 2, "verdict": "PASS"},
            {"round": 3, "verdict": "PASS"},
        ],
        "source_registry": source_registry,
        "findings": {
            "gaps": [
                {"id": gap_id, "gap_type": data["gap_type"], "description": data["description"]}
                for gap_id, data in gaps.items()
            ]
        },
    }
    _write_yaml(root / "state" / "survey_memory.yaml", survey_memory)


def _write_stage_reviews(root: Path, stage: str, *, repair: bool = False) -> int:
    packets = build_stage_review_packets(root, stage)
    if packets:
        write_packets(root, packets, fmt="markdown")
    for packet in packets:
        out = resolve_packet_path(packet["output_path"], packet, project_root=root, framework_root=_framework_root)
        if stage == "M6S01" and out.name == "M6S01_internal_peer_review.md":
            _write(out, _internal_peer_review())
        elif repair:
            _write(out, _repair_review(stage))
        else:
            _write(out, _passing_review(packet.get("role", "Stage Review")))

    if stage == "M1S02":
        for round_num in (1, 2, 3):
            _write(root / "knowledge" / "reviews" / f"M1S02_round{round_num}_review.md", _passing_review(f"M1S02 Round {round_num} Review"))
    return len(packets)


def _write_gate_reviews(root: Path, gate_id: str) -> int:
    packets = build_gate_review_packets(root, gate_id)
    write_packets(root, packets, fmt="markdown")
    for packet in packets:
        out = resolve_packet_path(packet["output_path"], packet, project_root=root, framework_root=_framework_root)
        _write(out, _passing_review(packet.get("role", "Gate Review")))
    _write(root / "knowledge" / "reviews" / f"{gate_id}_aggregate.md", _gate_aggregate_review(root, gate_id))
    return len(packets)


def _gate_aggregate_review(root: Path, gate_id: str) -> str:
    rubric = get_gate_rubric(gate_id)
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
    for item in rubric.get("items", []):
        evidence = _first_existing_evidence(root, item.get("evidence_examples", []))
        lines.append(f"| {item.get('id', '')} | PASS | 2/2 | {evidence} | simulated evidence satisfies rubric |")
    return "\n".join(lines) + "\n"


def _first_existing_evidence(root: Path, candidates: list[str]) -> str:
    for rel in candidates:
        if (root / rel).exists():
            return rel
    return candidates[0] if candidates else "knowledge/reviews"


def _write_stage_output(root: Path, stage: str) -> Path:
    out = get_canonical_output_path(root, stage)
    if stage == "M1S01":
        _write(out, "# M1S01 Topic Scoping\n\nScenario and research scope.\n")
    elif stage == "M1S02":
        _prepare_m1_memory(root)
        _write(
            out,
            "# M1S02 Literature Deep Dive\n\n"
            "## Round 1\nInitial database and web search.\n"
            "## Round 2\nExpanded related-work understanding.\n"
            "## Round 3\nFinal coverage pass.\n"
            "## 检索策略 search strategy\n"
            "数据库 public_db and internet web search; screening inclusion/exclusion criteria recorded.\n"
            "## Perspective Coverage\n"
            "Perspective coverage covers scenario/task, model/method, metric/performance, dataset/protocol, "
            "failure/limitation, and baseline/comparison views before gap synthesis.\n"
            "## Detailed Research Report\nBig direction, middle direction, and small direction gaps are justified.\n"
            "## Gap 论证\n证据链 evidence chain cites Source Log supporting sources for GAP-BIG, GAP-MID, and GAP-SMALL.\n",
        )
    elif stage == "M1S03":
        _write(
            out,
            "# M1S03 Research Question\n\n"
            "## 1. 从 Gap 到问题\n"
            "大方向 large direction scenario gap GAP-BIG, 中方向 middle direction model/metric gap GAP-MID, "
            "小方向 small direction component limitation GAP-SMALL are mapped into one focused question.\n\n"
            "## 2. 研究问题\n"
            "**主问题**: Can the proposed method address GAP-BIG while improving GAP-MID and GAP-SMALL?\n\n"
            "### FINER 标准验证\n"
            "- **F**easible: yes.\n"
            "- **I**nteresting: yes.\n"
            "- **N**ovel: source-backed by GAP-BIG/GAP-MID/GAP-SMALL.\n"
            "- **E**thical: low risk.\n"
            "- **R**elevant: aligned with topic.\n\n"
            "## 3. 问题分解\n"
            "| 子问题 | 依赖 | 验证方式 |\n|---|---|---|\n| Q1 | GAP-BIG | experiment |\n\n"
            "## 4. 创新类型声明\n"
            "架构改进型 with validation-deepening aspects.\n\n"
            "## 5. 范围界定\n"
            "- **包含**: GAP-BIG, GAP-MID, GAP-SMALL.\n"
            "- **排除**: unrelated settings.\n",
        )
    elif stage == "M1S04":
        _write(
            out,
            "# M1S04 Hypothesis Generation\n\n"
            "## 1. 核心假设\n"
            "| 假设 ID | 假设陈述 | 来源 |\n|---|---|---|\n| H1 | The method improves the target scenario. | GAP-BIG, GAP-MID, GAP-SMALL |\n\n"
            "## 2. 可测量预测\n"
            "| 假设 | 预测 | 测量指标 | 实验设计 |\n|---|---|---|---|\n| H1 | improvement over baseline | accuracy metric | main experiment |\n\n"
            "## 3. 零假设\n"
            "| 假设 | 零假设 H0 |\n|---|---|\n| H1 | no improvement over baseline |\n\n"
            "## 4. 假设-问题映射\n"
            "GAP-BIG -> 问题 Q1 -> 假设 H1 -> 预测 P1; GAP-MID and GAP-SMALL define secondary predictions.\n",
        )
    elif stage == "M1S05":
        _write(
            out,
            "# M1S05 Novelty Feasibility\n\n"
            "## 1. 新颖性评估\n"
            "问题新颖性 and 方法新颖性 are supported by evidence from Source src1-src5 and GAP-BIG/GAP-MID/GAP-SMALL.\n"
            "大方向 large direction GAP-BIG, 中方向 middle direction GAP-MID, 小方向 small direction GAP-SMALL remain explicit.\n\n"
            "## 2. 文献对比\n"
            "| 对比维度 | 已有工作 | 本研究 | 差异 |\n|---|---|---|---|\n| scenario | src1/src2 | GAP-BIG | source-backed difference |\n\n"
            "## 3. 可行性分析\n"
            "- **技术可行性**: feasible.\n"
            "- **数据可行性**: dataset exists.\n"
            "- **时间可行性**: within budget.\n"
            "- **计算资源**: local/ssh budget.\n\n"
            "## 4. 风险评估\n"
            "| 风险 | 概率 | 影响 | 缓解措施 |\n|---|---|---|---|\n| baseline risk | 中 | 中 | mitigation |\n\n"
            "## 5. 最终判断\n"
            "**建议**: PROCEED\n\n"
            "**理由**: Source-backed and feasible.\n",
        )
        _write(
            root / "knowledge" / "handoff_M1_M2.md",
            "# Handoff M1 to M2\n\nResearch question and hypothesis from GAP-BIG, GAP-MID, GAP-SMALL.\n",
        )
    elif stage == "M2S01":
        _write(out, "# M2S01\n\n同模态不同任务\n不同模态同任务\n底层原理\n优化目标\n\n## 候选方案\ncandidate solution pool.\n")
        m2_sources = [
            _m2_source(6, "same_modality_diff_task", "GAP-BIG", "vision", "public_db"),
            _m2_source(7, "same_task_diff_modality", "GAP-MID", "speech", "web_search"),
            _m2_source(8, "shared_principle", "GAP-SMALL", "optimization", "citation_chain"),
            _m2_source(9, "similar_structure", "GAP-BIG", "control", "public_db"),
        ]
        _write_yaml(
            root / "knowledge" / "M2" / "M2_source_log.yaml",
            {
                "search_statistics": {
                    "total_queries": 4,
                    "public_db_hits": 12,
                    "web_search_hits": 8,
                    "citation_chain_hits": 6,
                    "unique_papers_discovered": 18,
                    "papers_shortlisted": 4,
                    "shortlisted_source_ids": [src["id"] for src in m2_sources],
                    "search_dimensions_covered": [
                        "same_modality_diff_task",
                        "same_task_diff_modality",
                        "shared_principle",
                        "similar_structure",
                    ],
                    "query_ledger": [
                        {"query": "vision same modality transferable mechanism", "source": "public_db", "results_count": 12},
                        {"query": "speech same task different modality", "source": "web_search", "results_count": 8},
                        {"query": "optimization shared principle robust adaptation", "source": "citation_chain", "results_count": 6},
                        {"query": "control similar structure adaptive method", "source": "public_db", "results_count": 5},
                    ],
                },
                "sources": m2_sources,
                "gap_solution_map": {
                    "GAP-BIG": {"solutions": ["src6", "src9"], "selected_solution": "src6"},
                    "GAP-MID": {"solutions": ["src7"], "selected_solution": "src7"},
                    "GAP-SMALL": {"solutions": ["src8"], "selected_solution": "src8"},
                },
            },
        )
    elif stage == "M2S02":
        _write(out, "# M2S02\n\n### 论文 A\n问题结构映射\n核心机制映射\nIMP-1\n\n### Paper B\nstructure mapping\nmechanism mapping\nIMP-2\n\n## 诚实性自检\nhonesty.\n")
    elif stage == "M2S03":
        _write(out, "# M2S03\n\n## 符号定义\nx, y.\n\n## 组件\ncomponent A.\n\n## M2S02 对应关系\nmapping.\n\n## 设计决策\ndecision.\n")
    elif stage == "M2S04":
        _write(out, "# M2S04\n\n## Algorithm\n算法 steps.\n\n## 复杂度\ncomplexity.\n\n## 定理\nproof sketch.\n\n## 现有工作对比\nrelated work.\n\n## 诚实性声明\nhonesty.\n")
    elif stage == "M2S05":
        _write(
            out,
            "# M2S05\n\n"
            "## 1. Benchmark & Dataset Selection\n\n"
            "| 数据集 | 规模 | 任务类型 | 选择理由 | 获取方式 | 许可证 |\n"
            "|---|---|---|---|---|---|\n"
            "| DemoSet | 1GB | classification | matches M1 gap | wget download with checksum 校验 | CC-BY |\n\n"
            "## 2. Baseline 基线\n"
            "Baseline fairness: 相同的数据划分, 相同的评估指标, same split, same training budget.\n\n"
            "## 3. Experiment Protocol\n"
            "### 3.0 相关工作实验设置\n"
            "reference protocol from PaperX: dataset metric baseline protocol.\n\n"
            "| 实验 ID | 目的 | 目标假设 | 验证内容 | 对照组/Baselines | 指标 | 必需/可选 |\n"
            "|---|---|---|---|---|---|---|\n"
            "| Exp-1 | 实验目标 main purpose | H1 | main comparison | baseline | accuracy metric | 必需 |\n"
            "随机种子 seed: 42. 单次固定 seed 实验，不要求多 seed 统计检验。可复现 reproducibility requirements git commit.\n",
        )
        _write_yaml(
            root / "knowledge" / "M2" / "M2S05_metric_protocol.yaml",
            {
                "schema_version": 1,
                "metric_protocols": [
                    {
                        "metric_protocol_id": "mp_demo_accuracy",
                        "dataset": "demo",
                        "scenario": "classification",
                        "split": "test",
                        "metric_key": "accuracy",
                        "definition": "fraction of correct labels",
                        "calculation": "correct / total over the test split",
                        "direction": "higher_is_better",
                        "value_range": [0.0, 1.0],
                        "normal_reference_range": [0.5, 0.95],
                        "protocol_source": {
                            "source_id": "src1",
                            "table_or_section": "Table 1",
                            "rationale": "standard classification metric for demo",
                        },
                        "metric_sanity_check": {
                            "test_case": "two correct out of four examples",
                            "expected_value": 0.5,
                            "tolerance": 1.0e-6,
                        },
                    }
                ],
            },
        )
        _write(root / "knowledge" / "handoff_M2_M3.md", "# Handoff M2 to M3\n\nM3S01 should design the main experiment from M2S05 metric protocols.\n")
    elif stage == "M3S01":
        _write(
            out,
            "# M3S01 Main Experiment Design\n\n"
            "## Scope Boundary\n"
            "Main experiment only. Not include ablation, robustness, mechanism, or M4 analysis design; those are M4-only.\n\n"
            "## Dataset And Metric Protocol\n\n"
            "| experiment_id | dataset | scenario/task | split | metric_protocol_id | primary_metric | direction | normal_reference_range | source |\n"
            "|---|---|---|---|---|---|---|---|---|\n"
            "| Exp-1 | demo | classification | test | mp_demo_accuracy | accuracy | higher_is_better | 0.5-0.95 | M2S05_metric_protocol.yaml |\n\n"
            "## Baseline Reference Values\n\n"
            "| baseline | comparator_type | source_id | title | venue | year | modality | task | dataset | scenario | split | metric_protocol_id | metric | reference_value | value_source | table_or_section | expected_tolerance | acquisition_plan |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
            "| baseline_1 | external_prior_work | src1 | Representative Paper 1 | DemoConf | 2024 | text | classification | demo | classification | test | mp_demo_accuracy | accuracy | 0.75 | paper | Table 1 | 0.02 | verify-local-existing |\n\n"
            "## Proposed Method Same-Condition Protocol\n\n"
            "| 条件 | Baseline | Proposed method | 是否一致 | 差异说明 |\n"
            "|---|---|---|---|---|\n"
            "| dataset | demo | demo | yes | same condition |\n"
            "| split | test | test | yes | same split |\n"
            "| primary metric | accuracy | accuracy | yes | same metric |\n"
            "| seed | 42 | 42 | yes | fixed seed single run |\n\n"
            "Fairness 公平 constraints use same split and same metric. Ours/proposed 所提方法 runs under same condition.\n",
        )
    elif stage == "M3S02":
        _write(
            out,
            "# M3S02 Implementation\n\n"
            "## Dataset Review\nReal dataset under experiments/data/demo.\n\n"
            "## 环境 Review\nconfig/execution_env.yaml uses local mode.\n\n"
            "## Long-running execution policy\n"
            "Long-running jobs are recorded in experiments/logs/m3s02_longrun_ledger.md with 权限, patience, and resume evidence.\n\n"
            "## Resource utilization plan\n"
            "experiments/configs/resource_plan.yaml records CPU allocation, cpu_parallel strategy, dataloader workers, launch command, and utilization thresholds.\n",
        )
        sandbox_profile = {
            "sandbox": {
                "enabled": True,
                "mode": "venv",
                "network_policy": "restricted",
                "filesystem_policy": {
                    "allowed_write_paths": ["experiments/runs/", "experiments/logs/", "experiments/artifacts/", "artifacts/"],
                    "denied_paths": ["~/.ssh/", "/etc/", "/var/"],
                },
                "secrets_policy": {
                    "allow_env_secrets": False,
                    "allow_ssh_key_read": False,
                    "redact_logs": True,
                },
                "resource_limits": {
                    "timeout_hours": 24,
                    "max_cpu_cores": 4,
                    "max_memory_gb": 16,
                    "max_gpu_count": 0,
                },
                "reproducibility": {
                    "requirements_lock": "experiments/requirements.lock",
                    "image": "",
                    "image_digest": "",
                    "seed_policy": "fixed_seed_42",
                },
            }
        }
        resource_optimization = {
            "enabled": True,
            "target_gpu_count": "all_visible",
            "target_cpu_cores": "auto",
            "gpu_strategy": "auto",
            "cpu_strategy": "dataloader_and_task_parallel",
            "dataloader": {"auto_num_workers": True, "max_workers": 16},
            "monitoring": {
                "enabled": True,
                "interval_seconds": 10,
                "min_gpu_utilization_pct": 70,
                "min_cpu_utilization_pct": 60,
                "plan_path": "experiments/configs/resource_plan.yaml",
                "monitor_path_template": "experiments/runs/{run_id}/resource_monitor.csv",
                "runtime_watchdog": {
                    "enabled": True,
                    "default_interval_seconds": 14400,
                    "events_path": "experiments/logs/runtime_events.jsonl",
                    "checks_path_template": "experiments/runs/{run_id}/watchdog_checks.jsonl",
                    "alerts_path_template": "experiments/runs/{run_id}/watchdog_alerts.jsonl",
                    "alert_policy": "record_alert_only_agent_decides_continue_fix_or_stop",
                },
            },
        }
        _write_yaml(
            root / "config" / "execution_env.yaml",
            {
                "execution": {
                    "mode": "local",
                    "local": {"env_manager": "venv", "python_version": "3.11"},
                    **sandbox_profile,
                    "resource_optimization": resource_optimization,
                }
            },
        )
        _write_yaml(root / "experiments" / "configs" / "sandbox_profile.yaml", sandbox_profile)
        _write_yaml(
            root / "experiments" / "configs" / "resource_plan.yaml",
            {
                "schema_version": 1,
                "available": {"cpu": {"cores": 4, "memory_total_mb": 16384}, "gpus": []},
                "allocation": {"cpu_cores": 4, "gpu_count": 0, "gpu_ids": []},
                "strategy": {
                    "device_mode": "cpu_parallel",
                    "gpu_parallelism": "none",
                    "config_or_task_parallelism": True,
                    "dataloader": {"num_workers": 2, "pin_memory": False, "persistent_workers": True},
                },
                "launch": {
                    "env": {"OMP_NUM_THREADS": "4", "MKL_NUM_THREADS": "4"},
                    "command_template": "python experiments/src/train.py --config experiments/configs/main_exp.yaml --device cpu",
                },
                "monitoring": {
                    "enabled": True,
                    "min_gpu_utilization_pct": 70,
                    "min_cpu_utilization_pct": 60,
                    "runtime_watchdog": {
                        "enabled": True,
                        "default_interval_seconds": 14400,
                        "events_path": "experiments/logs/runtime_events.jsonl",
                        "checks_path_template": "experiments/runs/{run_id}/watchdog_checks.jsonl",
                        "alerts_path_template": "experiments/runs/{run_id}/watchdog_alerts.jsonl",
                        "alert_policy": "record_alert_only_agent_decides_continue_fix_or_stop",
                    },
                },
            },
        )
        _write(root / "experiments" / "requirements.lock", "numpy==1.26.4\n")
        values_path = root / "experiments" / "data" / "demo" / "values.txt"
        _write(values_path, "1\n2\n3\n")
        _write(root / "experiments" / "data" / "demo" / "splits" / "train.txt", "1\n2\n")
        _write(root / "experiments" / "data" / "demo" / "splits" / "test.txt", "3\n")
        _write_yaml(
            root / "experiments" / "data" / "dataset_manifest.yaml",
            {
                "datasets": [
                    {
                        "dataset_id": "demo",
                        "status": "complete",
                        "path": "experiments/data/demo",
                        "required_files": ["values.txt", "splits/train.txt", "splits/test.txt"],
                        "splits": {
                            "train": {"path": "splits/train.txt", "expected_count": 2, "actual_count": 2},
                            "test": {"path": "splits/test.txt", "expected_count": 1, "actual_count": 1},
                        },
                        "checksum": {
                            "algorithm": "sha256",
                            "file": "values.txt",
                            "value": hashlib.sha256(values_path.read_bytes()).hexdigest(),
                        },
                        "smoke_load": {
                            "status": "passed",
                            "log_path": "experiments/logs/import_smoke.log",
                        },
                    }
                ]
            },
        )
        _write(root / "experiments" / "src" / "train.py", _code_with_enough_lines())
        _write(
            root / "experiments" / "logs" / "m3s02_longrun_ledger.md",
            "# M3S02 Long-Running Execution Ledger\n\n"
            "| Item | Execution mode | Command | Status | Log path | Patience / polling | Resume command | Permission / approval | Completion criteria |\n"
            "|---|---|---|---|---|---|---|---|---|\n"
            "| dataset | local | `wget -c https://example.test/demo.zip` | completed | `experiments/logs/download.log` | timeout=12h; poll_interval=30m | `wget -c https://example.test/demo.zip` | none | checksum passed |\n",
        )
        _write(root / "experiments" / "logs" / "download.log", "download completed; checksum passed\n")
        _write(root / "experiments" / "logs" / "import_smoke.log", "dataset smoke load passed\n")
    elif stage == "M3S03":
        _write(
            out,
            "# M3S03 Baseline Lock\n\n"
            "### Baseline 1\n"
            "Verification path: verify-local-existing.\n"
            "Checkpoint verified loadable: not_applicable.\n"
            "source_id: src1; title: Representative Paper 1; venue: DemoConf; year: 2024; modality: text; task: classification.\n"
            "metric_protocol_id: mp_demo_accuracy; scenario: classification.\n"
            "Paper value: 0.75; local value: 0.75; relative_deviation: 0.0.\n"
            "verification_verdict: verified_match.\n\n"
            "## Smoke Test\nsmoke passed.\n\n"
            "## Baseline Lock Manifest\n"
            "`experiments/baselines/baseline_lock.yaml` declares baseline_1 as primary and m3s04_eligible.\n",
        )
        _write(
            root / "experiments" / "baselines" / "baseline_1" / "logs" / "metric_sanity.log",
            "metric sanity passed: 2/4 accuracy = 0.5\n",
        )
        _write(
            root / "experiments" / "baselines" / "baseline_1" / "logs" / "eval.log",
            "local accuracy = 0.75\n",
        )
        _write_yaml(
            root / "experiments" / "baselines" / "baseline_1" / "metric_contract.yaml",
            {
                "baseline_id": "baseline_1",
                "verification_verdict": "verified_match",
                "metric_protocol_id": "mp_demo_accuracy",
                "dataset": "demo",
                "scenario": "classification",
                "split": "test",
                "metrics": {"primary": {"key": "accuracy", "value": 0.75, "direction": "higher_is_better"}},
                "reference_result": {
                    "source": "paper",
                    "value": 0.75,
                    "dataset": "demo",
                    "scenario": "classification",
                    "split": "test",
                    "metric": "accuracy",
                    "table_or_section": "Table 1",
                },
                "local_validation": {
                    "command": "python eval.py --metric accuracy",
                    "raw_log_path": "experiments/baselines/baseline_1/logs/eval.log",
                    "local_value": 0.75,
                },
                "deviation": {"relative_delta": 0.0, "tolerance": 0.10, "passed": True},
                "metric_validation": {
                    "status": "pass",
                    "evidence_path": "experiments/baselines/baseline_1/logs/metric_sanity.log",
                },
            },
        )
        _write_yaml(
            root / "experiments" / "baselines" / "baseline_lock.yaml",
            {
                "schema_version": 1,
                "baseline_code_immutable_after_lock": True,
                "baselines": [
                    {
                        "baseline_id": "baseline_1",
                        "name": "Simulated baseline",
                        "comparison_role": "primary",
                        "source": "verify-local-existing",
                        "comparator_type": "external_prior_work",
                        "source_id": "src1",
                        "title": "Representative Paper 1",
                        "venue": "DemoConf",
                        "year": 2024,
                        "modality": "text",
                        "task": "classification",
                        "ablation_of_ours": False,
                        "implementation_fidelity": "official_code",
                        "implementation_path": "experiments/baselines/baseline_1/",
                        "metric_contract": "experiments/baselines/baseline_1/metric_contract.yaml",
                        "metric_protocol_id": "mp_demo_accuracy",
                        "dataset": "demo",
                        "scenario": "classification",
                        "split": "test",
                        "metric": "accuracy",
                        "direction": "higher_is_better",
                        "paper_value": 0.75,
                        "local_value": 0.75,
                        "relative_deviation": 0.0,
                        "reference_result": {
                            "source": "paper",
                            "value": 0.75,
                            "dataset": "demo",
                            "scenario": "classification",
                            "split": "test",
                            "metric": "accuracy",
                            "table_or_section": "Table 1",
                        },
                        "local_validation": {
                            "command": "python eval.py --metric accuracy",
                            "raw_log_path": "experiments/baselines/baseline_1/logs/eval.log",
                            "local_value": 0.75,
                        },
                        "deviation": {"relative_delta": 0.0, "tolerance": 0.10, "passed": True},
                        "metric_validation": {
                            "status": "pass",
                            "evidence_path": "experiments/baselines/baseline_1/logs/metric_sanity.log",
                        },
                        "verification_verdict": "verified_match",
                        "m3s04_eligible": True,
                        "checkpoint": {
                            "required": False,
                            "status": "not_applicable",
                            "verified_loadable": False,
                        },
                    }
                ],
                "m3s04_contract": {
                    "primary_baseline_id": "baseline_1",
                    "metric_contract": "experiments/baselines/baseline_1/metric_contract.yaml",
                    "dataset": "demo",
                    "scenario": "classification",
                    "split": "test",
                    "metric": "accuracy",
                    "metric_protocol_id": "mp_demo_accuracy",
                },
            },
        )
    elif stage == "M3S04":
        run_dir = root / "experiments" / "runs" / "M3S04_main" / "run1"
        _write(
            out,
            "# M3S04 Main Experiment\n\n"
            "## Run Contract\ncontract. Resource Plan: experiments/configs/resource_plan.yaml.\n\n"
            "## Experiments Directory Contract\n"
            "Formal results are in experiments/tables/results_main.tsv and run_registry.yaml.\n\n"
            "## 资源利用率执行记录\n"
            "Run run1 uses cpu_parallel task_parallel and records experiments/runs/M3S04_main/run1/resource_monitor.csv; average CPU utilization 72%; low utilization none.\n\n"
            "## Runtime Watchdog 与告警记录\n"
            "experiments/logs/runtime_events.jsonl and experiments/runs/M3S04_main/run1/watchdog_checks.jsonl record watchdog 巡检. "
            "Watchdog only records alerts and does not automatically terminate the run. Agent 决策: continue; no alert observed.\n\n"
            "## Trained-Weight Evidence Contract\n"
            "Final proposed result uses trained checkpoint experiments/runs/M3S04_main/run1/checkpoints/best.pt and runtime_events records training_completed.\n\n"
            "## 迭代循环记录\niterations with resource_monitor.csv.\n\n"
            "## Evidence Ladder\nsolid.\n\n"
            "## 随机种子\n42.\n",
        )
        _write(run_dir / "log.txt", "ok\n")
        _write(run_dir / "checkpoints" / "best.pt", "trained checkpoint placeholder\n")
        _write(run_dir / "run_manifest.yaml", "run_id: run1\nstage: M3S04\nrole: ours\n")
        _write(run_dir / "config.yaml", "seed: 42\n")
        _write(run_dir / "command.sh", "python experiments/code/train.py --seed 42\n")
        _write(run_dir / "stdout.log", "training completed\n")
        _write(run_dir / "stderr.log", "")
        _write(run_dir / "training_history.json", "[{\"epoch\": 1, \"metric\": 0.8}]\n")
        _write(run_dir / "metrics.tsv", "metric\tvalue\naccuracy\t0.80\n")
        _write(run_dir / "checkpoint_manifest.yaml", "checkpoint_path: experiments/runs/M3S04_main/run1/checkpoints/best.pt\nverified_loadable: true\n")
        _write(run_dir / "status.json", "{\"status\":\"completed\"}\n")
        _write(
            run_dir / "resource_monitor.csv",
            "timestamp,command_pid,cpu_load_pct,mem_available_mb,gpu_index,gpu_util_pct,gpu_mem_used_mb,gpu_mem_total_mb\n"
            "2026-05-29T12:00:00,123,72,8000,,,,\n",
        )
        watchdog_event = (
            '{"timestamp":"2026-05-29T12:00:00","stage":"M3S04","event_type":"watchdog_check",'
            '"run_id":"run1","severity":"info","decision_required":false,'
            '"agent_action_policy":"record_alert_only_agent_decides_continue_fix_or_stop","signals":[]}\n'
            '{"timestamp":"2026-05-29T12:30:00","stage":"M3S04","event_type":"training_completed",'
            '"run_id":"run1","status":"completed","checkpoint_path":"experiments/runs/M3S04_main/run1/checkpoints/best.pt"}\n'
        )
        _write(root / "experiments" / "logs" / "runtime_events.jsonl", watchdog_event)
        _write(run_dir / "watchdog_checks.jsonl", watchdog_event)
        _write(
            root / "experiments" / "tables" / "results_main.tsv",
            "method\trun_id\tseed\tmetric_protocol_id\tmetric\tdirection\tvalue\trun_status\tweight_state\tcheckpoint_path\ttraining_steps\tresource_monitor\n"
            "baseline\tbaseline_run\t42\tmp_demo_accuracy\taccuracy\thigher_is_better\t0.75\tcompleted\tnot_applicable\t\t0\texperiments/runs/M3S04_main/run1/resource_monitor.csv\n"
            "ours\trun1\t42\tmp_demo_accuracy\taccuracy\thigher_is_better\t0.80\tcompleted\ttrained_checkpoint\texperiments/runs/M3S04_main/run1/checkpoints/best.pt\t120\texperiments/runs/M3S04_main/run1/resource_monitor.csv\n",
        )
        _write(
            root / "experiments" / "tables" / "results_all.tsv",
            (root / "experiments" / "tables" / "results_main.tsv").read_text(encoding="utf-8"),
        )
        _write(
            root / "experiments" / "results.tsv",
            (root / "experiments" / "tables" / "results_main.tsv").read_text(encoding="utf-8"),
        )
        _write_yaml(
            root / "experiments" / "run_registry.yaml",
            {
                "schema_version": 1,
                "runs": [
                    {
                        "run_id": "run1",
                        "stage": "M3S04",
                        "role": "ours",
                        "status": "completed",
                        "validity": "valid_main",
                        "run_dir": "experiments/runs/M3S04_main/run1",
                        "run_manifest": "run_manifest.yaml",
                        "config_path": "config.yaml",
                        "command_path": "command.sh",
                        "stdout_path": "stdout.log",
                        "stderr_path": "stderr.log",
                        "history_path": "training_history.json",
                        "metrics_path": "metrics.tsv",
                        "checkpoint_path": "experiments/runs/M3S04_main/run1/checkpoints/best.pt",
                        "checkpoint_manifest": "checkpoint_manifest.yaml",
                        "status_path": "status.json",
                    }
                ],
            },
        )
    elif stage == "M3S05":
        _write(
            out,
            "# M3S05 Result Validation\n\n"
            "## 实验停止原因\n"
            "停止条件: budget complete. 当前 best 指标: accuracy=0.803 vs baseline=0.753. Evidence Ladder: solid.\n\n"
            "## 数据质量检查\n"
            "过拟合: normal. 数据泄露: none. 训练稳定性: stable. 可复现: fixed seed=42 command/config/logs are recorded.\n\n"
            "## 固定 Seed 单次结果验证\n"
            "fixed seed=42 single-run validation; no p-value, std, or CI is claimed. Ours improves accuracy by 0.05 at seed 42.\n\n"
            "## 与假设的对应验证\n"
            "| 假设 | 预期结果 | 实际结果 | 支持程度 |\n"
            "|---|---|---|---|\n"
            "| H1 | Ours improves accuracy | accuracy improves by 0.05 | 完全支持 |\n\n"
            "## 潜在问题与根因分析\n"
            "| 问题 | 严重程度 (critical/major/minor) | 根因 | 影响 |\n"
            "|---|---|---|---|\n"
            "| small dataset | minor | benchmark scale | M4 robustness required |\n\n"
            "## 最终决策\n"
            "Decision: KEEP\n\n"
            "## 负面结果\n"
            "negative result: cross-seed stability is not claimed because only fixed seed=42 is used.\n\n"
            "## Evidence Artifact 打包\n"
            "Artifact 清单 includes manifest.yaml, metric_contract.yaml, comparison_table.csv, and reproduction.md under "
            "`experiments/artifacts/main_experiment/`.\n\n"
            "## 已知限制\n"
            "局限性: single simulated dataset, M4 will test robustness.\n\n"
            "## 传递给下游的信息\n"
            "M4 analysis direction: ablation 消融, robustness 鲁棒, mechanism 机制. handoff required.\n",
        )
        _write_yaml(
            root / "experiments" / "artifacts" / "main_experiment" / "manifest.yaml",
            {
                "experiment_id": "main_exp_v1",
                "method": "ours",
                "dataset": "demo",
                "baseline_refs": ["experiments/baselines/baseline_1/metric_contract.yaml"],
                "trained_checkpoint": "experiments/runs/M3S04_main/run1/checkpoints/best.pt",
                "primary_metric": {"key": "accuracy", "value": 0.803},
                "seed": 42,
                "environment": {"python": "3.11", "hardware": "cpu"},
                "run_date": "2026-05-23",
            },
        )
        _write_yaml(
            root / "experiments" / "artifacts" / "main_experiment" / "metric_contract.yaml",
            {
                "method": "ours",
                "metrics": {"primary": {"key": "accuracy", "value": 0.803}},
            },
        )
        _write(
            root / "experiments" / "artifacts" / "main_experiment" / "comparison_table.csv",
            "method,seed,metric,value\nbaseline,42,accuracy,0.753\nours,42,accuracy,0.803\n",
        )
        _write(
            root / "experiments" / "artifacts" / "main_experiment" / "reproduction.md",
            "# Reproduction\n\nRun `python experiments/src/train.py --seed 42`.\n",
        )
        _write(
            root / "knowledge" / "handoff_M3_M4.md",
            "# Handoff M3 to M4\n\n"
            "Decision: KEEP, validation passed in M3S05 result validation.\n\n"
            "## Claims and Evidence\n"
            "claim C1: ours improves accuracy; evidence: experiments/artifacts/main_experiment/manifest.yaml and comparison_table.csv.\n\n"
            "## Artifact Path\n"
            "experiments/artifacts/main_experiment/ contains manifest.yaml, metric_contract.yaml, comparison_table.csv.\n\n"
            "## M4 Analysis Directions\n"
            "M4 should run analysis, ablation 消融, robustness 鲁棒, and mechanism 机制 checks.\n",
        )
    elif stage == "M4S01":
        _write(
            out,
            "# M4S01\n\n"
            "## 数据质量审计\nok\n## 主实验结果摘要\nok\n## 意外发现\nok\n"
            "## 边界条件探索\nok\n## 负面结果\nok\n## Claim 初筛\nok\n"
            "## 分析战役规划草案\n"
            "消融 ablation, 机制 mechanism, 鲁棒 robustness. literature_basis 文献 数据库. "
            "efficiency_required: no; 效率豁免: no extra compute claim in this simulation.\n\n"
            "### Component Claim Analysis Matrix\n"
            "| Component / Claim | ablation | mechanism | robustness | efficiency | failure | waiver_reason |\n"
            "|---|---|---|---|---|---|---|\n"
            "| C1 / component A | planned | planned | planned | waived | planned | no efficiency claim |\n\n"
            "### Paper Protocol Adaptation Table\n"
            "| reference_paper / source_id | task_setup | metric | baseline_protocol | transferable_part | adopted_for_slice | adoption_decision |\n"
            "|---|---|---|---|---|---|---|\n"
            "| src1 | diagnostic setup | accuracy | active baseline same seed | ablation protocol | Ana-1 | adopted |\n\n"
            "## 论文面向映射初稿\nok\n",
        )
    elif stage == "M4S02":
        _write(
            out,
            "# M4S02\n\n"
            "## 分析目标\n"
            "How: test the contribution mechanism. Where: test mild-noise and boundary scenarios. "
            "Why: probe the mechanism behind the gain. Upstream basis: M3S01 main experiment design, M3S05 KEEP validation, and handoff_M3_M4.\n\n"
            "## Component Claim Analysis Matrix\n"
            "| Component / Claim | Required Evidence | Planned Slice IDs | Missing Evidence / Waiver |\n"
            "|---|---|---|---|\n"
            "| C1 / component A | ablation, mechanism, robustness | Ana-1, Ana-2, Ana-3 | efficiency_required: no because no efficiency claim |\n\n"
            "## Paper Protocol Adaptation Table\n"
            "| reference_paper / source_id | task_setup | metric | baseline_protocol | transferable_part | adopted_for_slice | adoption_decision |\n"
            "|---|---|---|---|---|---|---|\n"
            "| src1 | diagnostic setup | accuracy | active baseline same seed | ablation protocol | Ana-1 | adopted |\n\n"
            "## Slice 列表\n"
            "### Slice: Ana-1\nanalysis_type=ablation; baseline_inclusion=required; literature_basis=src1; "
            "efficiency_required: no; paper_protocol_adaptation=src1 task_setup metric baseline_protocol adopted; "
            "comparison_target=full model and active baseline; expected_pattern=full > w/o component; evidence_criteria=metric effect size; claim_links=C1.\n"
            "### Slice: Ana-2\nanalysis_type=mechanism; baseline_inclusion=required; literature_basis=src2; "
            "efficiency_required: no; paper_protocol_adaptation=src2 visualization protocol adopted; "
            "comparison_target=baseline probe; expected_pattern=ours alignment higher; evidence_criteria=visualization plus metric; claim_links=C2.\n"
            "### Slice: Ana-3\nanalysis_type=robustness; baseline_inclusion=required; literature_basis=src3; "
            "efficiency_required: no; paper_protocol_adaptation=src3 robustness protocol adopted; "
            "comparison_target=active baseline under same perturbation; expected_pattern=ours stable under mild noise; evidence_criteria=metric and CI; claim_links=C3.\n"
            "### Slice: Ana-4\nanalysis_type=failure negative; baseline_inclusion=optional; literature_basis=negative-result audit; "
            "efficiency_required: no; paper_protocol_adaptation=negative-result audit adopted; "
            "comparison_target=boundary cases; expected_pattern=failures documented; evidence_criteria=case taxonomy; claim_links=C4.\n\n"
            "## Comparability Contract\nbaseline same split.\n## 执行信封审计\nrealistic.\n",
        )
        _write_yaml(
            root / "experiments" / "configs" / "m4_task_queue.yaml",
            {
                "schema_version": 1,
                "stage": "M4S03",
                "tasks": [
                    {
                        "task_id": "Ana-1",
                        "analysis_type": "ablation",
                        "command": "python experiments/src/run_analysis.py --slice Ana-1",
                        "dependencies": [],
                        "parallelizable": True,
                        "resource_requirements": {"min_gpu_count": 0, "min_cpu_cores": 2, "expected_minutes": 30},
                        "baseline_inclusion": "required",
                        "fairness_key": "Ana-1_same_split_seed_metric_resource_class",
                        "expected_artifacts": ["experiments/artifacts/analysis_experiment/Ana-1/manifest.yaml"],
                        "success_criteria": ["analysis_results.tsv contains Ana-1 baseline and ours rows"],
                    },
                    {
                        "task_id": "Ana-2",
                        "analysis_type": "mechanism",
                        "command": "python experiments/src/run_analysis.py --slice Ana-2",
                        "dependencies": [],
                        "parallelizable": True,
                        "resource_requirements": {"min_gpu_count": 0, "min_cpu_cores": 2, "expected_minutes": 30},
                        "baseline_inclusion": "required",
                        "fairness_key": "Ana-2_same_split_seed_metric_resource_class",
                        "expected_artifacts": ["experiments/artifacts/analysis_experiment/Ana-2/manifest.yaml"],
                        "success_criteria": ["analysis_results.tsv contains Ana-2 baseline and ours rows"],
                    },
                    {
                        "task_id": "Ana-3",
                        "analysis_type": "robustness",
                        "command": "python experiments/src/run_analysis.py --slice Ana-3",
                        "dependencies": [],
                        "parallelizable": True,
                        "resource_requirements": {"min_gpu_count": 0, "min_cpu_cores": 2, "expected_minutes": 30},
                        "baseline_inclusion": "required",
                        "fairness_key": "Ana-3_same_split_seed_metric_resource_class",
                        "expected_artifacts": ["experiments/artifacts/analysis_experiment/Ana-3/manifest.yaml"],
                        "success_criteria": ["analysis_results.tsv contains Ana-3 baseline and ours rows"],
                    },
                    {
                        "task_id": "Ana-4",
                        "analysis_type": "failure",
                        "command": "python experiments/src/run_analysis.py --slice Ana-4",
                        "dependencies": [],
                        "parallelizable": True,
                        "resource_requirements": {"min_gpu_count": 0, "min_cpu_cores": 2, "expected_minutes": 30},
                        "baseline_inclusion": "optional",
                        "fairness_key": "Ana-4_boundary_documentation",
                        "expected_artifacts": ["experiments/artifacts/analysis_experiment/Ana-4/manifest.yaml"],
                        "success_criteria": ["analysis_results.tsv contains Ana-4 rows"],
                    },
                ],
            },
        )
    elif stage == "M4S03":
        _write(out, "# M4S03\n\n## 执行摘要\nok\n## Slice 执行记录\nok; resource_id=local resource_kind=local server_id=none resource_monitor=experiments/runs/analysis_1/resource_monitor.csv.\n## 负面/失败结果记录\nfailed case.\n## 原始数据与日志\nlogs. sandbox_profile: experiments/configs/sandbox_profile.yaml.\n\n## Sandbox / Container Execution Record\nAna-1 sandbox mode venv; resource_id local; command `python analysis.py`; working dir experiments; allowed writes experiments/runs/; network policy restricted; resource limits timeout=24h cpu=4 gpu=0; log path experiments/runs/analysis_1/logs/run.log.\n\n## 初步审查摘要\nstage_in_fix continue; abnormal class: data metric method model environment.\n")
        _write(
            root / "experiments" / "analysis_results.tsv",
            "slice\tanalysis_type\tmethod\tdataset\tsplit\tseed\tconfig_id\trun_id\tmetric\tvalue\tbaseline_inclusion\tartifact_path\truntime_sec\tparams_m\tpeak_mem_mb\tresource_id\tresource_kind\tserver_id\tgpu_ids\tresource_monitor\tnotes\n"
            "Ana-1\tablation\tbaseline\tds\ttest\t42\tcfg-b\trun-b\taccuracy\t0.753\trequired\texperiments/artifacts/analysis_experiment/Ana-1\t100\t9.8\t1900\tlocal\tlocal\t\t[]\texperiments/runs/run-b/resource_monitor.csv\tbaseline\n"
            "Ana-1\tablation\tours\tds\ttest\t42\tcfg-o\trun-o\taccuracy\t0.803\trequired\texperiments/artifacts/analysis_experiment/Ana-1\t130\t10.5\t2100\tlocal\tlocal\t\t[]\texperiments/runs/run-o/resource_monitor.csv\tours\n"
            "Ana-2\tmechanism\tbaseline\tds\ttest\t42\tcfg-b\trun-b\talignment_score\t0.410\trequired\texperiments/artifacts/analysis_experiment/Ana-2\t80\t9.8\t1900\tlocal\tlocal\t\t[]\texperiments/runs/run-b/resource_monitor.csv\tbaseline\n"
            "Ana-2\tmechanism\tours\tds\ttest\t42\tcfg-o\trun-o\talignment_score\t0.560\trequired\texperiments/artifacts/analysis_experiment/Ana-2\t95\t10.5\t2100\tlocal\tlocal\t\t[]\texperiments/runs/run-o/resource_monitor.csv\tours\n"
            "Ana-3\trobustness\tbaseline\tds\tnoise\t42\tcfg-b\trun-b\taccuracy_noise\t0.700\trequired\texperiments/artifacts/analysis_experiment/Ana-3\t110\t9.8\t1900\tlocal\tlocal\t\t[]\texperiments/runs/run-b/resource_monitor.csv\tbaseline\n"
            "Ana-3\trobustness\tours\tds\tnoise\t42\tcfg-o\trun-o\taccuracy_noise\t0.760\trequired\texperiments/artifacts/analysis_experiment/Ana-3\t140\t10.5\t2100\tlocal\tlocal\t\t[]\texperiments/runs/run-o/resource_monitor.csv\tours\n"
            "Ana-4\tfailure\tours\tds\thigh_noise\t42\tcfg-o\trun-o\taccuracy_high_noise\t0.610\toptional\texperiments/artifacts/analysis_experiment/Ana-4\t120\t10.5\t2100\tlocal\tlocal\t\t[]\texperiments/runs/run-o/resource_monitor.csv\tnegative\n",
        )
    elif stage == "M4S04":
        _write(
            out,
            "# M4S04 Analysis Results\n\n"
            "## 统计分析\n"
            "Ablation, mechanism, and robustness analyses include p-value, 效应量, 95% 置信区间, and baseline 对照.\n\n"
            "## Claim Ledger\n"
            "| Claim ID | Claim Text | Evidence | Status | Caveats | Paper Role |\n"
            "|---|---|---|---|---|---|\n"
            "| C1 | Component A explains the gain | Ana-1 ablation baseline comparison | supported | same split only | main_text |\n"
            "| C2 | Mechanism visualization explains why/how the method works | Ana-2 mechanism visualization | partially_supported | exploratory probe | appendix |\n"
            "| C3 | Robustness holds under mild noise | Ana-3 robustness baseline comparison | supported | not high noise | main_text |\n"
            "| C4 | All high-noise cases improve | Ana-4 failure negative result | unsupported | high noise fails | removed |\n\n"
            "## 洞察提炼\n"
            "How: ablation shows the component drives the gain. Where: robustness works under mild noise and fails under high noise. "
            "Why: mechanism visualization/probe shows better alignment. So what: the method claim should be bounded.\n\n"
            "## 局限性\n"
            "鲁棒性 limitation and weak mechanism caveat are retained.\n\n"
            "## 证据可用性\n"
            "| Evidence ID | Source | Usability | Reason | Paper Handling |\n"
            "|---|---|---|---|---|\n"
            "| Ana-1 | experiments/analysis_results.tsv | usable | baseline included | main_text |\n"
            "| Ana-2 | experiments/artifacts/analysis_experiment/figures/mechanism.pdf | weak | visualization exploratory | appendix |\n"
            "| Ana-4 | experiments/analysis_results.tsv | unusable | negative high-noise result | removed |\n\n"
            "## Component Claim Analysis Matrix\n"
            "| Component / Claim | ablation | mechanism | robustness | efficiency | failure | waiver_reason |\n"
            "|---|---|---|---|---|---|---|\n"
            "| C1 / component A | Ana-1 | Ana-2 | Ana-3 | efficiency_required: no | Ana-4 | no efficiency claim or extra compute path |\n\n"
            "## Efficiency Evidence / Waiver\n"
            "efficiency_required: no\n"
            "trigger_reason: not_applicable\n"
            "efficiency_metrics_available: params_m runtime_sec peak_mem_mb not_applicable\n"
            "baseline_or_full_model_comparison: waived with reason\n\n"
            "## Paper Protocol Adaptation Summary\n"
            "| reference_paper / source_id | adopted_for_slice | task/metric/protocol adapted | rejected_reason / caveat |\n"
            "|---|---|---|---|\n"
            "| src1 | Ana-1 | task_setup accuracy baseline_protocol | none |\n\n"
            "## M4→M5 Handoff\n"
            "literature_basis: M2 reference protocol and 文献 diagnostic setup. Visualization figure path recorded. "
            "M5 should write Analysis with ablation, mechanism, robustness, and failure evidence.\n",
        )
        _write_yaml(
            root / "experiments" / "artifacts" / "analysis_experiment" / "manifest.yaml",
            {
                "analysis_slices": [
                    {"id": "Ana-1", "analysis_type": "ablation", "baseline_inclusion": "required", "literature_basis": "PaperX ablation protocol"},
                    {"id": "Ana-2", "analysis_type": "mechanism", "baseline_inclusion": "required", "literature_basis": "PaperY probe visualization"},
                    {"id": "Ana-3", "analysis_type": "robustness", "baseline_inclusion": "required", "literature_basis": "PaperZ robustness setup"},
                    {"id": "Ana-4", "analysis_type": "failure", "baseline_inclusion": "optional", "literature_basis": "negative-result audit"},
                ],
                "component_claim_analysis_matrix": [
                    {"claim": "C1", "component": "component A", "slices": ["Ana-1", "Ana-2", "Ana-3"]},
                ],
                "paper_protocol_adaptation": [
                    {
                        "reference_paper": "src1",
                        "task_setup": "diagnostic setup",
                        "adoption_decision": "adopted",
                    },
                ],
                "result_table": "experiments/analysis_results.tsv",
                "figure_paths": ["experiments/artifacts/analysis_experiment/figures/mechanism.pdf"],
            },
        )
        _write(
            root / "experiments" / "artifacts" / "analysis_experiment" / "reproduction.md",
            "# M4 Reproduction\n\nRun analysis slices Ana-1 through Ana-4 with baseline and ours rows.\n",
        )
        _write(
            root / "experiments" / "artifacts" / "analysis_experiment" / "figures" / "mechanism.pdf",
            "%PDF simulated mechanism figure\n",
        )
        _write(
            root / "knowledge" / "handoff_M4_M5.md",
            "# Handoff M4 to M5\n\n"
            "## Claim/Evidence Mapping\n"
            "Claim C1 supported by Evidence Ana-1; Claim C2 partially_supported weak evidence; Claim C3 supported; C4 removed.\n\n"
            "## Artifact Paths\n"
            "- experiments/analysis_results.tsv\n"
            "- experiments/artifacts/analysis_experiment/manifest.yaml\n"
            "- experiments/artifacts/analysis_experiment/figures/mechanism.pdf\n\n"
            "## M5 Writing Guidance\n"
            "Introduction should keep claims bounded. Method should mention component rationale. Experiments should include ablation and robustness. Analysis should explain how/where/why with caveat.\n\n"
            "## Limitations and Caveats\n"
            "weak mechanism evidence goes to appendix; high-noise unsupported result is removed from main claims.\n",
        )
    elif stage == "M5S01":
        _write(
            out,
            "# M5S01 Pre-Write Audit\n\n"
            "## 上游文档完整性检查\n"
            "All required upstream documents are complete: M1S02_literature_deepdive.md, "
            "M1_source_log.yaml, M1S03_research_question.md, M1S04_hypothesis_generation.md, "
            "M2S03_method_architecture.md, M2S04_algorithm_theory.md, M2S05_experiment_setup.md, "
            "M3S01_main_experiment_design.md, M3S04_main_experiment.md, M3S05_result_validation.md, "
            "M4S03_analysis_experiment.md, M4S04_analysis_results.md, handoff_M4_M5.md.\n\n"
            "## 核心贡献点\n"
            "Contribution Contrib-1: bounded method improvement. 支撑证据 paths: "
            "knowledge/M3/M3S05_result_validation.md and knowledge/M4/M4S04_analysis_results.md. "
            "证据状态: fully_supported. Paper section: Introduction / Experiments.\n\n"
            "## Gap 识别\n"
            "Evidence Gap 证据缺口: Low | block: no | handled in limitations.\n"
            "Narrative Gap 叙事缺口: Low | block: no | handled in M5S02 story spine.\n"
            "Citation Gap 引用缺口: Low | block: no | handled by M1_source_log.\n\n"
            "## 风格/排版参照审计\n"
            "Reference papers 3: Paper A, Paper B, Paper C. 风格蒸馏 extracts structure, "
            "paragraph function, figure/table density, and layout constraints only; do not copy 不复制 "
            "source sentences or unique figure designs.\n\n"
            "## 数据一致性检查\n"
            "Main metric 主指标 is consistent 一致 between M3S04 and M3S05. Baseline 基线 is consistent "
            "between M2S05/M3S01 and M3S03. Dataset 数据集 is consistent between M3S01 and M3S02. "
            "Method name 方法名称 is consistent between M2S03 and M2S04.\n\n"
            "## 审计结论\n"
            "Writing readiness: yes\n"
            "是否建议继续写作: 是\n"
            "必须先修复的阻塞问题: 无\n",
        )
    elif stage == "M5S02":
        _write(
            out,
            "# M5S02\n\n"
            "Venue\nPlotting Plan\nTerminology\nSection Plan\n"
            "Reference paper count: 3 exemplar papers selected from M1/M2 evidence.\n"
            "Style & Layout Profile: transferable structure, paragraph function, figure/table density, "
            "section rhythm, and layout constraint signals only; do not copy, 不得复制, 不可迁移 unique wording or figures.\n"
            "Figure Style Profile: venue preset, palette, color grammar, visual richness, layout grammar. "
            "Architecture uses image2 gpt-image-2 with paper-framework-figure-studio-pro c-narcissus. "
            "Experiment plots use matplotlib seaborn plt and nature-figure.\n",
        )
    elif stage == "M5S03":
        _write(out, "# M5S03\n\n## Introduction\ncontribution based on locked M5S04 Method, M5S05 Experiments, and M5S06 Analysis.\n\n## Related Work\nrelated work.\n")
    elif stage == "M5S04":
        _write(out, "# M5S04\n\nproblem formulation 问题定义\nmethod 方法\nalgorithm 算法\narchitecture figure generated-images via image2 gpt-image-2. figure style profile venue palette visual richness. paper-framework-figure-studio-pro c-narcissus. allowed labels and forbidden invented labels; no invented components.\n")
    elif stage == "M5S05":
        _write(out, "# M5S05\n\ndataset 数据集\nbaseline 基线\nresults 结果\nprovenance 绘图脚本 数据源\nnature-figure plotting rules.\n")
    elif stage == "M5S06":
        _write(out, "# M5S06\n\nanalysis 分析\ndiscussion 讨论\nlimitations 局限\nnegative failure 边界\n图来源 backend matplotlib plt no analysis figure.\n")
    elif stage == "M5S07":
        _write(out, "# M5S07\n\nabstract 摘要\nconclusion 结论\n数值一致 consistency check.\n")
    elif stage == "M5S09":
        _write(
            out,
            "# M5S09 Full-Polish & Narrative Coherence Review\n\n"
            "## LaTeX/PDF Inputs\n"
            "Read artifacts/paper.tex as the editable LaTeX source and artifacts/paper.pdf as the rendered PDF check. "
            "Do not edit PDF directly; all edits are applied to paper.tex.\n\n"
            "## Narrative Coherence Audit\n"
            "Intro-Method promise chain: Introduction promises are implemented in Method.\n"
            "Method-Experiments validation chain: Method components are validated in Experiments.\n"
            "Experiments-Analysis interpretation chain: M5S05 findings map one-to-one to M5S06 analysis.\n\n"
            "## Terminology Consistency\n"
            "terminology consistency 术语一致 check passed across Introduction, Method, Exp, Analysis, and Conclusion.\n\n"
            "## Numerical Consistency\n"
            "numerical consistency 数值一致 check passed for Abstract, Exp, Analysis, and Conclusion.\n\n"
            "## Language Refinement\n"
            "language refinement 语言精炼 and 润色 completed; transitions improved; no new claims added.\n\n"
            "## Recompile\n"
            "recompile 重新编译 compile completed after polishing paper.tex; final paper.pdf updated.\n\n"
            "## Anti-Leakage\n"
            "Anti-Leakage prompt applied; no author identity or copied exemplar text.\n",
        )
        _write(root / "artifacts" / "paper.pdf", "%PDF simulated final polished\n")
        _write(
            root / "knowledge" / "handoff_M5_completion.md",
            "# Handoff M5 Completion\n\n"
            "M6 submission ready: M5S09 final polish and recompile verdict PASS.\n\n"
            "## Paper Artifacts\n"
            "- artifacts/paper.pdf\n"
            "- artifacts/paper.tex\n"
            "- artifacts/refs.bib\n\n"
            "The final polished package is compiled and ready for submission audit.\n",
        )
    elif stage == "M5S08":
        _write(
            out,
            "# M5S08 Final Compilation\n\n"
            "Final verdict: PASS\n\n"
            "## Compile Command Record\n"
            "`pdflatex paper.tex`; `bibtex paper`; `pdflatex paper.tex`; `pdflatex paper.tex`.\n\n"
            "## Compile Result\n"
            "编译状态: PASS\n"
            "PDF page count: 6\n"
            "Fatal Errors: 0\n"
            "Undefined references: 0\n"
            "Undefined citations: 0\n"
            "Orphan cites: 0\n"
            "Anti-Leakage Check: PASS\n\n"
            "## Compliance\n"
            "style & layout compliance documented. Figure compliance: 图像 图表 backend generated-images 绘图脚本.\n"
            "figure style profile uses venue preset, palette, and visual richness.\n\n"
            "## Final Artifacts\n"
            "`artifacts/paper.tex`, `artifacts/paper.pdf`, `artifacts/refs.bib`.\n",
        )
        _write(root / "artifacts" / "paper.pdf", "%PDF simulated\n")
        _write(root / "artifacts" / "figures" / "architecture.pdf", "%PDF simulated figure\n")
        _write(
            root / "artifacts" / "refs.bib",
            "@article{smith2024demo,\n"
            "  title={Demo Baseline},\n"
            "  author={Smith, Alex},\n"
            "  journal={Transactions on Simulated Research},\n"
            "  year={2024}\n"
            "}\n"
            "@inproceedings{lee2025method,\n"
            "  title={Method Inspiration},\n"
            "  author={Lee, Bo},\n"
            "  booktitle={Proceedings of DemoConf},\n"
            "  year={2025}\n"
            "}\n",
        )
        _write(
            root / "artifacts" / "paper.tex",
            "\\documentclass{article}\n"
            "\\usepackage{graphicx}\n"
            "\\usepackage{booktabs}\n"
            "\\title{Simulated AutoPaper2 Study}\n"
            "\\begin{document}\n"
            "\\maketitle\n"
            "\\begin{abstract}\n"
            "We study a simulated research question with a controlled baseline and a proposed method. "
            "The abstract reports the validated main result and states the evidence boundary.\n"
            "\\end{abstract}\n"
            "\\section{Introduction}\n"
            "The problem follows a literature gap identified by prior work~\\cite{smith2024demo}. "
            "Our contribution is a method and evaluation protocol that improves the primary metric while preserving reproducibility.\n"
            "\\section{Related Work}\n"
            "Existing systems define the baseline protocol and motivate the method adaptation~\\cite{lee2025method}. "
            "We compare against the same baseline, metric, split, and seed policy to keep the claim bounded.\n"
            "\\section{Method}\n"
            "The proposed method combines the selected architecture with a reproducible training protocol. "
            "Figure~\\ref{fig:arch} summarizes the framework and its information flow.\n"
            "\\begin{figure}[t]\n"
            "\\centering\n"
            "\\includegraphics[width=0.75\\linewidth]{figures/architecture}\n"
            "\\caption{Method architecture generated from the approved figure profile.}\n"
            "\\label{fig:arch}\n"
            "\\end{figure}\n"
            "\\section{Experiments and Results}\n"
            "Table~\\ref{tab:main} reports the main comparison with fixed seed 42. "
            "The proposed method improves accuracy over the baseline with matched data and metric definitions.\n"
            "\\begin{table}[t]\n"
            "\\centering\n"
            "\\caption{Main result comparison.}\n"
            "\\label{tab:main}\n"
            "\\begin{tabular}{lccc}\n"
            "\\toprule\n"
            "Method & Metric & Mean & Std \\\\\n"
            "\\midrule\n"
            "Baseline & Accuracy & 0.753 & 0.006 \\\\\n"
            "Ours & Accuracy & 0.803 & 0.006 \\\\\n"
            "\\bottomrule\n"
            "\\end{tabular}\n"
            "\\end{table}\n"
            "\\section{Analysis and Discussion}\n"
            "The analysis identifies robustness checks, ablation needs, and one negative seed-level finding. "
            "These limitations prevent broader claims beyond the tested benchmark.\n"
            "\\section{Conclusion}\n"
            "The evidence supports a bounded improvement claim and a clear follow-up analysis plan for future work.\n"
            "\\bibliographystyle{plain}\n"
            "\\bibliography{refs}\n"
            "\\end{document}\n",
        )
        _write(
            root / "knowledge" / "handoff_M5_completion.md",
            "# Handoff M5 Completion\n\n"
            "M6 submission ready: compiled verdict PASS.\n\n"
            "## Paper Artifacts\n"
            "- artifacts/paper.pdf\n"
            "- artifacts/paper.tex\n"
            "- artifacts/refs.bib\n\n"
            "The package is compiled and ready for submission audit.\n",
        )
    elif stage == "M6S01":
        _write(out, "# M6S01\n\n## Integrity Audit 完整性审计 投稿包\nok\n## Venue Compliance\nVenue, 页数, 匿名.\n## Audit Conclusion 审计结论\nREADY\nBlockers: []\nWarnings: []\n")
    elif stage == "M6S02":
        _write(out, "# M6S02\n\n## Submission Info 提交信息 paperreview.ai\nok\n## Submission Status 提交状态 tracking\nsuccess\n## Next Step 下一步 review邮件 审稿邮件\nmonitor.\n")
        _write_json(
            root / "knowledge" / "M6" / "M6S02_submission_log.json",
            {
                "platform": "paperreview.ai",
                "url": "https://paperreview.ai/",
                "submitted_at": "2026-05-23T00:00:00",
                "pdf_path": "artifacts/paper.pdf",
                "email": "review@example.com",
                "venue": "arxiv",
                "status": "success",
                "tracking": {"confirmation_id": "SIM-1"},
            },
        )
    elif stage == "M6S03":
        _write(out, "# M6S03\n\noverall score 总体评分 Soundness: 8\nreview matrix Review Matrix PR-A1\natomicization 原子化 class severity.\n")
        _write_json(
            root / "knowledge" / "M6" / "M6S03_review_email.json",
            {
                "status": "success",
                "found_email": {
                    "subject": "paperreview.ai review",
                    "from": "noreply@paperreview.ai",
                    "message_id": "<sim-1@example.com>",
                    "body": "Review body: Soundness 8. Please clarify evidence.",
                },
            },
        )
        _write(
            root / "knowledge" / "M6" / "M6S03_review_matrix.md",
            "# Matrix\n\n"
            "### PR-A1\n"
            "- **original_text**: Please clarify evidence.\n"
            "- **class**: evidence_gap\n"
            "- **severity**: High\n"
            "- **preliminary_route**: evidence_repackaging\n",
        )
    elif stage == "M6S04":
        _write(
            out,
            "# M6S04\n\n"
            "classification summary 意见分类汇总 Action Plan\n"
            "PR-A1: evidence_gap High routed to target_stage M5S05 for evidence repackaging.\n"
            "backtrack mapping 回溯目标映射 target_stage\n"
            "honest limitation 诚实限制 cannot_fully_address none.\n",
        )
        _write(
            root / "knowledge" / "M6" / "M6S04_action_plan.md",
            "# Action Plan\n\n"
            "### PR-A1\n"
            "- class: evidence_gap\n"
            "- severity: High\n"
            "- target_stage: M5S05\n"
            "- required_fix: clarify evidence provenance and comparison table\n"
            "- success_criteria: M5S05 cites the evidence artifact and reviewer confusion is resolved\n"
            "- rebuild_mode: incremental_replay\n"
            "- rerun_scope: M5S05 -> M5S06 -> M5S03 -> M5S07 -> M5S08 -> M5S09\n"
            "- priority: P1\n",
        )
    elif stage == "M6S05":
        _write(
            out,
            "# M6S05\n\n"
            "revision list 修订清单 Action Plan ID PR-A1 done.\n"
            "## PR-A1\n"
            "- status: completed / resolved\n"
            "- evidence path: knowledge/M5/M5S05_experiments_results.md; artifacts/paper.pdf\n"
            "- output file: artifacts/paper.tex\n"
            "recompile 重新编译 paper.pdf complete.\n"
            "negative results 负面结果 none.\n",
        )
        _write(root / "artifacts" / "paper.pdf", "%PDF revised simulated\n")
    elif stage == "M6S06":
        _write(
            out,
            "# M6S06\n\n"
            "resolution rate 综合解决度 High 解决率: 100%.\n"
            "## Action Plan 验证\n"
            "### PR-A1\n"
            "- status: resolved / PASS\n"
            "- M6S05 evidence path: knowledge/M6/M6S05_revision_execution.md\n"
            "quality preservation 质量保持度 Gate G5 preserved.\n"
            "external review evidence 外部审稿证据: M6S02_submission_log.json success; "
            "M6S03_review_email.json success; M6S03_review_matrix.md PR-* atomic items present.\n"
            "completion verdict 判定结果 PASS.\n\n"
            "判定结果: PASS\n",
        )
        _write(root / "knowledge" / "handoff_M6_completion.md", "# Handoff M6 Completion\n\nDone.\n")
        _write(root / "artifacts" / "submission_package" / "paper_final.pdf", "%PDF final simulated\n")
        _write(root / "artifacts" / "submission_package" / "source.zip", "simulated zip\n")
    else:
        _write(out, f"# {stage}\n\nSimulated output.\n")
    return out


def _advance(root: Path, stage: str, output: Path, *, agent: str | None = None) -> str:
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        try:
            cmd_advance(str(root), stage, agent or AGENT_FOR_STAGE.get(stage, "conductor"), str(output))
        except SystemExit as exc:
            raise RuntimeError(f"advance failed for {stage} with exit {exc.code}:\n{stdout.getvalue()}") from exc
    return stdout.getvalue()


def _module_auto_start_if_needed(root: Path) -> dict[str, Any] | None:
    state = PipelineState(root)
    if state.get_current_status() != "module_completed":
        return None
    action = Conductor(root).get_next_action()
    if action.get("action") != "EXECUTE_STAGE":
        raise RuntimeError(f"auto-advance did not produce EXECUTE_STAGE: {action}")
    return action


def run_simulation(
    projects_root: str | Path | None = None,
    *,
    keep_project: bool = False,
    exercise_backtrack: bool = True,
    write_dispatch: bool = True,
) -> dict[str, Any]:
    """Run the deterministic M1-M6 simulation and return a summary."""
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if projects_root is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="autopaper2-sim-")
        projects_root = Path(temp_dir.name)
    else:
        projects_root = Path(projects_root)

    root = ProjectManager.create(
        topic="AutoPaper2 full pipeline simulation",
        display_name="Full-Pipeline-Sim",
        projects_root=Path(projects_root),
        venue="arxiv",
    )
    state = PipelineState(root)
    state.set_stage("M1S01", "in_progress")
    state.set_module_status("M1", "in_progress")
    state.set_auto_advance(True)

    dispatch_packets = 0
    stage_advances = 0
    gate_advances = 0
    backtrack_exercised = False
    auto_starts: list[str] = []

    try:
        for stage in FLAT_STAGES:
            state = PipelineState(root)
            if state.get_current_stage() != stage:
                raise RuntimeError(f"expected current stage {stage}, got {state.get_current_stage()}")

            packet = build_stage_execution_packet(root, stage)
            if write_dispatch:
                write_packets(root, [packet], fmt="markdown")
            dispatch_packets += 1

            output = _write_stage_output(root, stage)

            if stage == "M2S01" and exercise_backtrack and not backtrack_exercised:
                dispatch_packets += _write_stage_reviews(root, stage, repair=True)
                text = _advance(root, stage, output)
                if "RE_EXECUTE" not in text:
                    raise RuntimeError(f"simulated stage review did not trigger RE_EXECUTE:\n{text}")
                backtrack_exercised = True
                if PipelineState(root).get_current_stage() != stage:
                    raise RuntimeError("backtrack did not keep current stage at the repair target")

            dispatch_packets += _write_stage_reviews(root, stage)
            _advance(root, stage, output)
            stage_advances += 1

            gate_id = GATE_BY_STAGE.get(stage)
            if gate_id:
                state = PipelineState(root)
                if state.get_current_status() != "waiting_gate":
                    raise RuntimeError(f"{stage} did not enter waiting_gate before {gate_id}")
                dispatch_packets += _write_gate_reviews(root, gate_id)
                _advance(root, stage, root / "knowledge" / "reviews" / f"{gate_id}_aggregate.md", agent="critic_team")
                gate_advances += 1
                action = _module_auto_start_if_needed(root)
                if action:
                    auto_starts.append(str(action.get("stage")))

        final_state = PipelineState(root)
        modules = final_state.data.get("modules", {})
        if final_state.get_current_status() != "completed":
            raise RuntimeError(f"final status is not completed: {final_state.get_current_status()}")
        if modules.get("M6", {}).get("status") != "completed":
            raise RuntimeError(f"M6 status is not completed: {modules.get('M6')}")

        summary = {
            "ok": True,
            "project_root": str(root),
            "stage_advances": stage_advances,
            "gate_advances": gate_advances,
            "dispatch_packets": dispatch_packets,
            "backtrack_exercised": backtrack_exercised,
            "auto_starts": auto_starts,
            "final_stage": final_state.get_current_stage(),
            "final_status": final_state.get_current_status(),
            "history_entries": len(final_state.data.get("history", [])),
            "backtrack_entries": len(final_state.data.get("backtrack_log", [])),
        }
        return summary
    finally:
        if temp_dir is not None and not keep_project:
            temp_dir.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic AutoPaper2 M1-M6 pipeline simulation.")
    parser.add_argument("--projects-root", default="", help="Directory where the simulated project should be created.")
    parser.add_argument("--keep-project", action="store_true", help="Keep the temporary simulated project after completion.")
    parser.add_argument("--no-backtrack", action="store_true", help="Do not inject the stage-review backtrack exercise.")
    parser.add_argument("--no-dispatch-write", action="store_true", help="Build but do not write dispatch packet markdown files.")
    args = parser.parse_args()

    summary = run_simulation(
        args.projects_root or None,
        keep_project=args.keep_project,
        exercise_backtrack=not args.no_backtrack,
        write_dispatch=not args.no_dispatch_write,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
