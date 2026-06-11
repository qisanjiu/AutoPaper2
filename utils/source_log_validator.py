"""Source Log validator — checks M1_source_log.yaml and M2_source_log.yaml integrity and coverage."""

from __future__ import annotations

import re
import yaml
from pathlib import Path
from typing import Any


M1_DEEP_READING_FIELDS = [
    "background",
    "contributions",
    "model",
    "method",
    "experiment_setup",
    "results",
    "analysis",
    "conclusion",
]

LITERATURE_ARTIFACT_TERMS = ("pdf", "html", "abstract", "bibtex", "source_tex", "supplement")
LITERATURE_ARTIFACT_STATUSES = {
    "available",
    "unavailable",
    "failed",
    "pending",
    "skipped",
    "unknown",
}
LITERATURE_PARSE_STATUSES = {"complete", "partial", "blocked", "not_attempted"}
LITERATURE_DOWNSTREAM_MODULES = ("M2", "M3", "M4", "M5")

M1_GAP_LEVELS = {
    "large": ("large", "big", "大方向", "场景", "领域", "domain", "scenario", "task-level"),
    "middle": ("middle", "mid", "中方向", "模型", "精度", "指标", "数据集", "model", "metric", "accuracy", "dataset"),
    "small": ("small", "micro", "小方向", "组件", "方法细节", "缺陷程度", "component", "module", "method limitation"),
}

M1_PERSPECTIVE_REQUIREMENTS = {
    "scenario/task perspective": ("scenario", "task", "application", "场景", "任务", "应用"),
    "model/method perspective": ("model", "method", "architecture", "algorithm", "模型", "方法", "架构", "算法"),
    "metric/performance perspective": ("metric", "accuracy", "performance", "efficiency", "指标", "精度", "性能", "效率"),
    "dataset/protocol perspective": ("dataset", "benchmark", "protocol", "experiment", "数据集", "基准", "实验设置", "协议"),
    "failure/limitation perspective": ("failure", "negative", "limitation", "defect", "失败", "负面", "局限", "缺陷"),
    "baseline/comparison perspective": ("baseline", "comparison", "sota", "comparator", "基线", "对比", "比较"),
}


def _infer_m1_gap_level(gap_id: str, gap_data: dict[str, Any]) -> str:
    """Infer large/middle/small gap level from explicit metadata or labels."""
    parts = [
        gap_id,
        str(gap_data.get("level", "")),
        str(gap_data.get("layer", "")),
        str(gap_data.get("gap_level", "")),
        str(gap_data.get("direction_level", "")),
        str(gap_data.get("scope", "")),
        str(gap_data.get("description", "")),
    ]
    signal = " ".join(parts).lower()
    for level, terms in M1_GAP_LEVELS.items():
        if any(term.lower() in signal for term in terms):
            return level
    return ""


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value in (None, ""):
        return []
    return [value]


def _is_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and value > 0


def _check_literature_ingestion_contract(
    sources: list[dict[str, Any]],
    *,
    module: str,
) -> tuple[bool, list[str]]:
    """Validate collection/artifact/parse metadata for retained papers.

    The contract does not require every PDF to be downloadable. It requires a
    durable status record, a failure reason when acquisition failed, and enough
    structured extraction metadata for downstream modules to know what is ready.
    """
    messages: list[str] = []
    ok = True
    for src in sources:
        if src.get("type") != "academic":
            continue
        source_id = src.get("id", "?")

        discovery_records = _as_list(src.get("discovery_records") or src.get("discovery"))
        legacy_discovery = bool(src.get("discovery_source") or src.get("discovery_query"))
        if discovery_records or legacy_discovery:
            messages.append(f"[PASS] Source '{source_id}': discovery provenance recorded")
        else:
            messages.append(f"[FAIL] Source '{source_id}': missing discovery_records or discovery_source/discovery_query")
            ok = False

        artifacts = _as_list(src.get("artifacts"))
        if not artifacts and src.get("pdf_url"):
            artifacts = [
                {
                    "artifact_type": "pdf",
                    "status": src.get("pdf_status", "unknown"),
                    "uri": src.get("pdf_url"),
                    "local_path": src.get("pdf_path", ""),
                    "failure_reason": src.get("pdf_failure_reason", ""),
                    "recovery_actions": src.get("pdf_recovery_actions", []),
                }
            ]
        if not artifacts:
            messages.append(f"[FAIL] Source '{source_id}': missing artifacts acquisition record")
            ok = False
        else:
            source_has_parseable_artifact = False
            for idx, artifact in enumerate(artifacts, start=1):
                if not isinstance(artifact, dict):
                    messages.append(f"[FAIL] Source '{source_id}': artifact {idx} must be a mapping")
                    ok = False
                    continue
                artifact_type = str(artifact.get("artifact_type") or artifact.get("type") or "").strip()
                status = str(artifact.get("status") or "").strip()
                if artifact_type not in LITERATURE_ARTIFACT_TERMS:
                    messages.append(f"[FAIL] Source '{source_id}': artifact {idx} has unknown artifact_type='{artifact_type}'")
                    ok = False
                if status not in LITERATURE_ARTIFACT_STATUSES:
                    messages.append(f"[FAIL] Source '{source_id}': artifact {idx} has unknown status='{status}'")
                    ok = False
                if status in {"available", "pending", "unknown"} and not (
                    artifact.get("uri") or artifact.get("local_path") or artifact.get("path")
                ):
                    messages.append(f"[FAIL] Source '{source_id}': artifact {idx} status={status} missing uri/local_path")
                    ok = False
                if status in {"failed", "unavailable", "skipped"}:
                    if not artifact.get("failure_reason"):
                        messages.append(f"[FAIL] Source '{source_id}': artifact {idx} status={status} missing failure_reason")
                        ok = False
                    if not _as_list(artifact.get("recovery_actions")):
                        messages.append(f"[FAIL] Source '{source_id}': artifact {idx} status={status} missing recovery_actions")
                        ok = False
                if artifact_type in {"pdf", "html", "source_tex"} and status == "available":
                    source_has_parseable_artifact = True
            if source_has_parseable_artifact:
                messages.append(f"[PASS] Source '{source_id}': parseable artifact available")
            else:
                messages.append(f"[PASS] Source '{source_id}': artifact failure/unavailability is explicitly recorded")

        parse_profile = src.get("parse_profile") or src.get("extraction")
        if not isinstance(parse_profile, dict) or not parse_profile:
            messages.append(f"[FAIL] Source '{source_id}': missing parse_profile")
            ok = False
            continue

        parse_status = str(parse_profile.get("parse_status") or "").strip()
        if parse_status not in LITERATURE_PARSE_STATUSES:
            messages.append(f"[FAIL] Source '{source_id}': parse_profile.parse_status invalid or missing")
            ok = False
        elif parse_status == "blocked":
            if not _as_list(parse_profile.get("missing_fields")):
                messages.append(f"[FAIL] Source '{source_id}': blocked parse_profile missing missing_fields")
                ok = False
            else:
                messages.append(f"[PASS] Source '{source_id}': blocked parse records missing fields")
        else:
            messages.append(f"[PASS] Source '{source_id}': parse_status={parse_status}")

        backend = str(parse_profile.get("parse_backend") or "").strip()
        if not backend:
            messages.append(f"[FAIL] Source '{source_id}': parse_profile missing parse_backend")
            ok = False

        section_summaries = parse_profile.get("section_summaries", {})
        if not isinstance(section_summaries, dict) or not section_summaries:
            messages.append(f"[FAIL] Source '{source_id}': parse_profile missing section_summaries")
            ok = False

        downstream = parse_profile.get("downstream_signals", {})
        if not isinstance(downstream, dict) or not downstream:
            messages.append(f"[FAIL] Source '{source_id}': parse_profile missing downstream_signals")
            ok = False
        else:
            missing_modules = [mod for mod in LITERATURE_DOWNSTREAM_MODULES if mod not in downstream]
            if missing_modules:
                messages.append(f"[FAIL] Source '{source_id}': downstream_signals missing {missing_modules}")
                ok = False
            else:
                messages.append(f"[PASS] Source '{source_id}': downstream_signals cover M2/M3/M4/M5")

        if module == "M1":
            required_signal_checks = {
                "M2": ("method_reference", "core_mechanism"),
                "M3": ("experiment_protocol", "datasets_metrics_baselines"),
                "M4": ("analysis_patterns", "analysis"),
                "M5": ("citation_ready", "writing_context"),
            }
            for mod, fields in required_signal_checks.items():
                signal = downstream.get(mod, {}) if isinstance(downstream, dict) else {}
                if not isinstance(signal, dict) or not any(signal.get(field) for field in fields):
                    messages.append(f"[FAIL] Source '{source_id}': downstream_signals.{mod} lacks {fields}")
                    ok = False

    return ok, messages


def _check_m1_search_provenance(data: dict[str, Any], sources: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Validate that M1 records an auditable search and screening strategy."""
    messages: list[str] = []
    ok = True
    provenance = data.get("search_provenance") or data.get("search_strategy") or {}
    source_ids = {str(src.get("id")) for src in sources if src.get("id")}

    if not isinstance(provenance, dict) or not provenance:
        return False, ["[FAIL] M1 search_provenance missing; expected databases, rounds, screening, and blindspot checks"]

    databases = _as_list(provenance.get("databases") or provenance.get("sources") or provenance.get("search_surfaces"))
    if not databases:
        messages.append("[FAIL] M1 search_provenance missing databases/search_surfaces")
        ok = False
    else:
        messages.append(f"[PASS] M1 search_provenance lists {len(databases)} database/search surface(s)")
        joined = " ".join(str(db).lower() for db in databases)
        library_terms = ("public_db", "library", "local", "semantic scholar", "openalex", "arxiv", "pubmed", "crossref", "dblp", "数据库", "文库")
        internet_terms = ("web", "internet", "google scholar", "scholar", "browser", "网页", "互联网")
        if not any(term in joined for term in library_terms + internet_terms):
            messages.append("[FAIL] M1 search_provenance databases do not identify a library/public DB or internet source")
            ok = False
        else:
            messages.append("[PASS] M1 search_provenance identifies library/public DB or internet search")

    inclusion = _as_list(provenance.get("inclusion_criteria") or provenance.get("include"))
    exclusion = _as_list(provenance.get("exclusion_criteria") or provenance.get("exclude"))
    if not inclusion:
        messages.append("[FAIL] M1 search_provenance missing inclusion_criteria")
        ok = False
    else:
        messages.append("[PASS] M1 search_provenance includes inclusion_criteria")
    if not exclusion:
        messages.append("[FAIL] M1 search_provenance missing exclusion_criteria")
        ok = False
    else:
        messages.append("[PASS] M1 search_provenance includes exclusion_criteria")

    rounds = provenance.get("rounds") or provenance.get("search_rounds") or []
    if not isinstance(rounds, list):
        messages.append("[FAIL] M1 search_provenance.rounds must be a list")
        return False, messages
    round_by_id: dict[int, dict[str, Any]] = {}
    for item in rounds:
        if not isinstance(item, dict):
            continue
        try:
            round_num = int(item.get("round"))
        except (TypeError, ValueError):
            continue
        round_by_id[round_num] = item

    retained_across_rounds: set[str] = set()
    for round_num, expected_label in ((1, "breadth"), (2, "depth"), (3, "blindspot")):
        round_data = round_by_id.get(round_num)
        if not round_data:
            messages.append(f"[FAIL] M1 search_provenance missing round {round_num} ({expected_label})")
            ok = False
            continue
        queries = [q for q in _as_list(round_data.get("queries")) if str(q).strip()]
        if not queries:
            messages.append(f"[FAIL] M1 search_provenance round {round_num} missing queries")
            ok = False
        else:
            messages.append(f"[PASS] M1 search_provenance round {round_num} records {len(queries)} query/queries")
        retrieved = round_data.get("retrieved_count", round_data.get("sources_found", 0))
        screened = round_data.get("screened_count", round_data.get("screened", 0))
        retained = round_data.get("retained_count", 0)
        retained_ids = {
            str(src_id)
            for src_id in _as_list(
                round_data.get("retained_source_ids")
                or round_data.get("source_ids")
                or round_data.get("retained_sources")
            )
            if str(src_id).strip()
        }
        retained_across_rounds.update(retained_ids)
        if not isinstance(retrieved, (int, float)) or retrieved <= 0:
            messages.append(f"[FAIL] M1 search_provenance round {round_num} missing positive retrieved_count/sources_found")
            ok = False
        else:
            messages.append(f"[PASS] M1 search_provenance round {round_num} has retrieved_count={retrieved}")
        if not isinstance(screened, (int, float)) or screened <= 0:
            messages.append(f"[FAIL] M1 search_provenance round {round_num} missing positive screened_count")
            ok = False
        else:
            messages.append(f"[PASS] M1 search_provenance round {round_num} has screened_count={screened}")
        if retained_ids:
            messages.append(f"[PASS] M1 search_provenance round {round_num} lists retained source IDs")
        elif not isinstance(retained, (int, float)) or retained <= 0:
            messages.append(f"[FAIL] M1 search_provenance round {round_num} missing retained sources/count")
            ok = False
        else:
            messages.append(f"[PASS] M1 search_provenance round {round_num} has retained_count={retained}")

    unknown_retained = sorted(retained_across_rounds - source_ids)
    if unknown_retained:
        messages.append(f"[FAIL] M1 search_provenance retained unknown source IDs: {', '.join(unknown_retained)}")
        ok = False
    elif retained_across_rounds:
        messages.append("[PASS] M1 search_provenance retained source IDs exist in Source Log")

    blindspot = provenance.get("blindspot_checks") or {}
    blindspot_text = ""
    if isinstance(blindspot, dict):
        blindspot_text = " ".join(f"{k} {v}" for k, v in blindspot.items()).lower()
    elif isinstance(blindspot, list):
        blindspot_text = " ".join(str(item) for item in blindspot).lower()
    required_blindspots = {
        "recent work": ("recent", "last 6 months", "近 6", "最新", "202", "new work"),
        "negative/opposing results": ("negative", "opposing", "contradict", "负面", "相反", "对立"),
        "seminal/classic work": ("seminal", "classic", "foundation", "奠基", "经典"),
        "key authors": ("key author", "author", "团队", "作者"),
        "source-log consistency": ("source log", "source_log", "一致性", "consistency"),
    }
    for label, terms in required_blindspots.items():
        if not any(term in blindspot_text for term in terms):
            messages.append(f"[FAIL] M1 search_provenance blindspot_checks missing {label}")
            ok = False
        else:
            messages.append(f"[PASS] M1 search_provenance blindspot_checks include {label}")

    return ok, messages


def _iter_perspective_entries(coverage: Any) -> list[tuple[str, dict[str, Any], str]]:
    entries: list[tuple[str, dict[str, Any], str]] = []
    if isinstance(coverage, dict):
        for key, value in coverage.items():
            if isinstance(value, dict):
                entry = dict(value)
            else:
                entry = {"value": value}
            entry.setdefault("perspective", key)
            entries.append((str(key), entry, yaml.safe_dump(entry, allow_unicode=True)))
    elif isinstance(coverage, list):
        for idx, value in enumerate(coverage, start=1):
            if not isinstance(value, dict):
                entry = {"value": value}
            else:
                entry = dict(value)
            key = str(entry.get("perspective") or entry.get("name") or f"entry_{idx}")
            entries.append((key, entry, yaml.safe_dump(entry, allow_unicode=True)))
    return entries


def _check_m1_perspective_coverage(data: dict[str, Any], sources: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Validate STORM-style perspective coverage before M1 gap synthesis."""
    messages: list[str] = []
    ok = True
    provenance = data.get("search_provenance") or data.get("search_strategy") or {}
    coverage = (
        data.get("perspective_coverage")
        or data.get("coverage_ledger")
        or (provenance.get("perspective_coverage") if isinstance(provenance, dict) else None)
        or (provenance.get("coverage_ledger") if isinstance(provenance, dict) else None)
    )
    source_ids = {str(src.get("id")) for src in sources if src.get("id")}

    entries = _iter_perspective_entries(coverage)
    if not entries:
        return False, ["[FAIL] M1 perspective_coverage missing; expected scenario/task, model/method, metric/performance, dataset/protocol, failure/limitation, and baseline/comparison coverage"]

    messages.append(f"[PASS] M1 perspective_coverage records {len(entries)} perspective entries")
    matched_indices: set[int] = set()
    for label, terms in M1_PERSPECTIVE_REQUIREMENTS.items():
        matching = [
            (idx, key, entry, text)
            for idx, (key, entry, text) in enumerate(entries)
            if any(term.lower() in f"{key}\n{text}".lower() for term in terms)
        ]
        if not matching:
            messages.append(f"[FAIL] M1 perspective_coverage missing {label}")
            ok = False
            continue
        matched_indices.update(idx for idx, *_ in matching)
        messages.append(f"[PASS] M1 perspective_coverage includes {label}")

    for idx, (key, entry, _text) in enumerate(entries):
        if idx not in matched_indices:
            continue
        status = str(entry.get("status") or "").strip().lower()
        if status not in {"covered", "reviewed", "included", "pass", "complete", "completed"}:
            messages.append(f"[FAIL] M1 perspective_coverage '{key}' missing covered/reviewed status")
            ok = False
        else:
            messages.append(f"[PASS] M1 perspective_coverage '{key}' status={status}")

        queries = [q for q in _as_list(entry.get("queries") or entry.get("search_queries")) if str(q).strip()]
        if not queries:
            messages.append(f"[FAIL] M1 perspective_coverage '{key}' missing search queries")
            ok = False
        else:
            messages.append(f"[PASS] M1 perspective_coverage '{key}' records {len(queries)} query/queries")

        covered_ids = {
            str(source_id)
            for source_id in _as_list(
                entry.get("source_ids")
                or entry.get("covered_source_ids")
                or entry.get("evidence_source_ids")
                or entry.get("sources")
            )
            if str(source_id).strip()
        }
        if not covered_ids:
            messages.append(f"[FAIL] M1 perspective_coverage '{key}' missing source IDs")
            ok = False
        else:
            unknown = sorted(covered_ids - source_ids)
            if unknown:
                messages.append(f"[FAIL] M1 perspective_coverage '{key}' references unknown source IDs: {', '.join(unknown)}")
                ok = False
            else:
                messages.append(f"[PASS] M1 perspective_coverage '{key}' source IDs exist")

        finding = (
            entry.get("finding")
            or entry.get("findings")
            or entry.get("evidence_summary")
            or entry.get("summary")
            or entry.get("argument")
        )
        if not str(finding or "").strip():
            messages.append(f"[FAIL] M1 perspective_coverage '{key}' missing finding/evidence_summary")
            ok = False
        else:
            messages.append(f"[PASS] M1 perspective_coverage '{key}' includes finding/evidence_summary")

    return ok, messages


def _check_m2_search_provenance(data: dict[str, Any], sources: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Validate that M2 records auditable cross-domain search provenance."""
    messages: list[str] = []
    ok = True
    stats = data.get("search_statistics") or data.get("search_provenance") or {}
    source_ids = {str(src.get("id")) for src in sources if src.get("id")}

    if not isinstance(stats, dict) or not stats:
        return False, ["[FAIL] M2 search_statistics missing; expected query ledger, hit counts, dimensions, and shortlisted papers"]

    total_queries = stats.get("total_queries", 0)
    query_ledger = _as_list(stats.get("query_ledger") or stats.get("queries"))
    if _is_positive_number(total_queries):
        messages.append(f"[PASS] M2 search_statistics records total_queries={total_queries}")
    elif query_ledger:
        messages.append(f"[PASS] M2 search_statistics infers total_queries from {len(query_ledger)} query ledger entries")
    else:
        messages.append("[FAIL] M2 search_statistics missing positive total_queries or query_ledger")
        ok = False

    if not query_ledger:
        messages.append("[FAIL] M2 search_statistics.query_ledger is empty")
        ok = False
    else:
        messages.append(f"[PASS] M2 search_statistics records {len(query_ledger)} query ledger entries")

    surface_terms = (
        "public_db",
        "public db",
        "library",
        "local",
        "semantic scholar",
        "openalex",
        "arxiv",
        "pubmed",
        "crossref",
        "dblp",
        "web",
        "internet",
        "google scholar",
        "scholar",
        "citation",
        "文库",
        "数据库",
        "互联网",
    )
    ledger_surfaces: set[str] = set()
    positive_result_seen = False
    for idx, entry in enumerate(query_ledger, start=1):
        if not isinstance(entry, dict):
            messages.append(f"[FAIL] M2 query_ledger entry {idx} must be a mapping with query/source/results_count")
            ok = False
            continue
        query = str(entry.get("query") or "").strip()
        source = str(entry.get("source") or entry.get("surface") or "").strip()
        results_count = entry.get("results_count", entry.get("hits", entry.get("sources_found", 0)))
        if not query:
            messages.append(f"[FAIL] M2 query_ledger entry {idx} missing query")
            ok = False
        if not source:
            messages.append(f"[FAIL] M2 query_ledger entry {idx} missing source/search surface")
            ok = False
        else:
            ledger_surfaces.add(source.lower())
        if _is_positive_number(results_count):
            positive_result_seen = True
    if positive_result_seen:
        messages.append("[PASS] M2 query_ledger includes positive result counts")
    elif query_ledger:
        messages.append("[FAIL] M2 query_ledger has no positive results_count/hits/sources_found")
        ok = False

    hit_counts = {
        "public_db_hits": stats.get("public_db_hits", 0),
        "web_search_hits": stats.get("web_search_hits", 0),
        "citation_chain_hits": stats.get("citation_chain_hits", 0),
    }
    hit_text = " ".join(str(surface) for surface in ledger_surfaces)
    if not any(term in hit_text for term in surface_terms) and not any(_is_positive_number(v) for v in hit_counts.values()):
        messages.append("[FAIL] M2 search_statistics does not identify a public DB/library, web, or citation search surface")
        ok = False
    else:
        messages.append("[PASS] M2 search_statistics identifies public DB/library, web, or citation search")

    dimensions = {
        str(dim).strip()
        for dim in _as_list(stats.get("search_dimensions_covered"))
        if str(dim).strip()
    }
    if not dimensions:
        dimensions = {
            str(src.get("search_dimension")).strip()
            for src in sources
            if str(src.get("search_dimension") or "").strip()
        }
    if len(dimensions) < 2:
        messages.append(f"[FAIL] M2 search provenance covers only {len(dimensions)} search dimension(s); expected >=2")
        ok = False
    else:
        messages.append(f"[PASS] M2 search provenance covers {len(dimensions)} search dimension(s)")

    shortlisted = stats.get("papers_shortlisted", stats.get("shortlisted_count", len(sources)))
    if not _is_positive_number(shortlisted):
        messages.append("[FAIL] M2 search_statistics missing positive papers_shortlisted/shortlisted_count")
        ok = False
    else:
        messages.append(f"[PASS] M2 search_statistics records papers_shortlisted={shortlisted}")

    retained_ids = {
        str(src_id)
        for src_id in _as_list(stats.get("shortlisted_source_ids") or stats.get("retained_source_ids"))
        if str(src_id).strip()
    }
    unknown_retained = sorted(retained_ids - source_ids)
    if unknown_retained:
        messages.append(f"[FAIL] M2 search_statistics references unknown shortlisted source IDs: {', '.join(unknown_retained)}")
        ok = False
    elif retained_ids:
        messages.append("[PASS] M2 shortlisted source IDs exist in Source Log")

    critical_source_fields = [
        "search_dimension",
        "target_gap",
        "source_domain",
        "core_mechanism",
        "adaptation_potential",
        "discovery_source",
        "discovery_query",
    ]
    for src in sources:
        missing = [field for field in critical_source_fields if not src.get(field)]
        if missing:
            messages.append(f"[FAIL] Source '{src.get('id', '?')}': missing M2 search/adaptation fields {missing}")
            ok = False
        else:
            messages.append(f"[PASS] Source '{src.get('id', '?')}': M2 search/adaptation fields complete")

    return ok, messages


def validate(project_root: str | Path, module: str = "M1") -> tuple[bool, list[str]]:
    """Validate source_log.yaml for a given module (M1 or M2).

    Args:
        project_root: Path to the project directory.
        module: Module identifier, "M1" or "M2".

    Returns:
        (ok, messages) tuple.
    """
    root = Path(project_root)
    log_path = root / "knowledge" / module / f"{module}_source_log.yaml"
    messages: list[str] = []
    ok = True

    if not log_path.exists():
        messages.append(f"[FAIL] {module}_source_log.yaml not found")
        return False, messages

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        messages.append(f"[FAIL] Failed to parse M1_source_log.yaml: {e}")
        return False, messages

    sources = data.get("sources", [])
    gap_map = data.get("gap_evidence_map", {})

    # Check source count (M2 allows fewer sources since it's cross-domain focused)
    min_sources = 5 if module == "M1" else 3
    if len(sources) < min_sources:
        messages.append(f"[FAIL] Only {len(sources)} sources found (minimum {min_sources})")
        ok = False
    else:
        messages.append(f"[PASS] {len(sources)} sources logged")

    # Check required fields per source
    required_fields = ["id", "title", "type", "credibility"]
    for src in sources:
        missing = [f for f in required_fields if f not in src or not src[f]]
        if missing:
            messages.append(f"[WARN] Source '{src.get('id', '?')}': missing fields {missing}")

    if module == "M1":
        search_ok, search_messages = _check_m1_search_provenance(data, sources)
        messages.extend(search_messages)
        if not search_ok:
            ok = False

        perspective_ok, perspective_messages = _check_m1_perspective_coverage(data, sources)
        messages.extend(perspective_messages)
        if not perspective_ok:
            ok = False

        for src in sources:
            if src.get("type") != "academic":
                continue
            missing_rich = [f for f in M1_DEEP_READING_FIELDS if not src.get(f)]
            if missing_rich:
                messages.append(
                    f"[FAIL] Source '{src.get('id', '?')}': missing deep-reading fields {missing_rich}. "
                    "M1 should extract background, contribution, model, method, experiments, results, analysis, and conclusion."
                )
                ok = False
            else:
                messages.append(f"[PASS] Source '{src.get('id', '?')}': deep-reading fields complete")

        ingestion_ok, ingestion_messages = _check_literature_ingestion_contract(sources, module=module)
        messages.extend(ingestion_messages)
        if not ingestion_ok:
            ok = False

    if module == "M1":
        anchors_ok, anchor_messages = _check_entry_anchor_coverage(root, sources)
        messages.extend(anchor_messages)
        if not anchors_ok:
            ok = False

    # Check academic source ratio
    academic_count = sum(1 for s in sources if s.get("type") == "academic")
    ratio = academic_count / len(sources) if sources else 0
    min_ratio = 0.5 if module == "M1" else 0.3  # M2 cross-domain may include more diverse sources
    if ratio < min_ratio:
        messages.append(f"[WARN] Academic sources ratio {ratio:.0%} < {min_ratio:.0%}")
    else:
        messages.append(f"[PASS] Academic sources ratio {ratio:.0%}")

    # M2-specific checks
    if module == "M2":
        search_ok, search_messages = _check_m2_search_provenance(data, sources)
        messages.extend(search_messages)
        if not search_ok:
            ok = False

        ingestion_ok, ingestion_messages = _check_literature_ingestion_contract(sources, module=module)
        messages.extend(ingestion_messages)
        if not ingestion_ok:
            ok = False

        # Check M2-specific fields
        m2_fields = ["search_dimension", "target_gap", "source_domain", "core_mechanism", "adaptation_potential"]
        for src in sources:
            missing_m2 = [f for f in m2_fields if f not in src or not src[f]]
            if missing_m2:
                messages.append(f"[WARN] Source '{src.get('id', '?')}': missing M2 fields {missing_m2}")

        # Check search dimension diversity
        dimensions = set(s.get("search_dimension", "") for s in sources)
        if len(dimensions) < 2:
            messages.append(f"[WARN] Only {len(dimensions)} search dimension(s) used (expected ≥2)")
        else:
            messages.append(f"[PASS] Search dimensions: {', '.join(dimensions)}")

        # Check gap_solution_map existence
        gap_solution_map = data.get("gap_solution_map", {})
        if not gap_solution_map:
            messages.append("[FAIL] M2 gap_solution_map is empty")
            ok = False
        else:
            messages.append(f"[PASS] gap_solution_map covers {len(gap_solution_map)} gap(s)")

        # Check search statistics
        search_stats = data.get("search_statistics", {})
        if search_stats:
            db_hits = search_stats.get("public_db_hits", 0)
            web_hits = search_stats.get("web_search_hits", 0)
            messages.append(f"[INFO] Public DB hits: {db_hits}, Web hits: {web_hits}")

    # Check gap evidence (M1 uses gap_evidence_map, M2 uses gap_solution_map)
    if module == "M1":
        if not gap_map:
            messages.append("[FAIL] M1 gap_evidence_map is empty; expected large/middle/small research gaps")
            ok = False

        gap_types = {}
        gap_levels: dict[str, list[str]] = {"large": [], "middle": [], "small": []}
        for gap_id, gap_data in gap_map.items():
            supporting = gap_data.get("supporting_sources", [])
            gap_type = gap_data.get("gap_type", "vacancy")
            gap_types[gap_id] = gap_type
            level = _infer_m1_gap_level(gap_id, gap_data)
            if not level:
                messages.append(
                    f"[FAIL] Gap '{gap_id}': missing large/middle/small direction level metadata"
                )
                ok = False
            else:
                gap_levels[level].append(gap_id)
                messages.append(f"[PASS] Gap '{gap_id}': direction level={level}")
            if not any(gap_data.get(field) for field in ("description", "claim", "argument", "evidence_summary")):
                messages.append(f"[FAIL] Gap '{gap_id}': missing description/argument for research report")
                ok = False
            if len(supporting) < 2:
                messages.append(f"[WARN] Gap '{gap_id}': only {len(supporting)} supporting source(s) (expected ≥2)")
                ok = False
            else:
                messages.append(f"[PASS] Gap '{gap_id}': {len(supporting)} supporting sources")

        if gap_map:
            for level, label in (("large", "large direction"), ("middle", "middle direction"), ("small", "small direction")):
                if not gap_levels[level]:
                    messages.append(f"[FAIL] M1 gap_evidence_map missing {label} gap")
                    ok = False
                else:
                    messages.append(f"[PASS] M1 gap_evidence_map covers {label}: {', '.join(gap_levels[level])}")

        # Check gap type distribution: at least 1 enhancement or validation gap
        enhancement_count = sum(1 for t in gap_types.values() if t in ("enhancement", "validation"))
        if enhancement_count == 0 and len(gap_types) >= 3:
            messages.append(
                f"[WARN] All {len(gap_types)} gaps are vacancy-type (VG). "
                f"Expected at least 1 enhancement (EG) or validation (ValG) gap. "
                f"Survey may have missed method-enhancement opportunities."
            )
        else:
            messages.append(
                f"[PASS] Gap type distribution: {enhancement_count} EG/ValG gap(s) found"
            )
    elif module == "M2":
        # M2 uses gap_solution_map
        for gap_id, gap_data in gap_solution_map.items():
            solutions = gap_data.get("solutions", [])
            if len(solutions) < 1:
                messages.append(f"[WARN] Gap '{gap_id}': no solutions found")
                ok = False
            else:
                messages.append(f"[PASS] Gap '{gap_id}': {len(solutions)} candidate solution(s)")
            selected = gap_data.get("selected_solution", "")
            if not selected:
                messages.append(f"[WARN] Gap '{gap_id}': no selected_solution")
            else:
                messages.append(f"[PASS] Gap '{gap_id}': selected_solution = {selected}")

    # --- Bidirectional consistency: Source Log ↔ Survey Memory (M1 only) ---
    if module == "M1":
        survey_mem_path = root / "state" / "survey_memory.yaml"
        if survey_mem_path.exists():
            try:
                with open(survey_mem_path, "r", encoding="utf-8") as f:
                    sm = yaml.safe_load(f) or {}
                sm_gaps = sm.get("findings", {}).get("gaps", [])
                sm_gap_ids = {g.get("id") for g in sm_gaps if g.get("id")}
                sl_gap_ids = set(gap_map.keys())

                missing_in_sl = sm_gap_ids - sl_gap_ids
                missing_in_sm = sl_gap_ids - sm_gap_ids
                if missing_in_sl:
                    messages.append(
                        f"[WARN] Gaps in survey_memory but not in Source Log: {', '.join(missing_in_sl)}. "
                        f"Source Log may be outdated."
                    )
                if missing_in_sm:
                    messages.append(
                        f"[WARN] Gaps in Source Log but not in survey_memory: {', '.join(missing_in_sm)}. "
                        f"Survey Memory may not have been synced."
                    )
                if not missing_in_sl and not missing_in_sm:
                    messages.append("[PASS] Source Log and Survey Memory gap sets are consistent")

                sm_sources = sm.get("source_registry", {})
                sl_source_ids = {s.get("id") for s in sources if s.get("id")}
                sm_source_ids = set(sm_sources.keys())
                missing_sources_in_sm = sl_source_ids - sm_source_ids
                if missing_sources_in_sm:
                    messages.append(
                        f"[WARN] {len(missing_sources_in_sm)} source(s) in Source Log not found in Survey Memory: "
                        f"{', '.join(list(missing_sources_in_sm)[:5])}{'...' if len(missing_sources_in_sm) > 5 else ''}"
                    )
                else:
                    messages.append("[PASS] All Source Log entries present in Survey Memory")
            except Exception as exc:
                messages.append(f"[WARN] Could not verify Source Log ↔ Survey Memory consistency: {exc}")

    # Check author diversity (single team ≤30%)
    author_diversity_ok, author_msg = check_author_diversity(sources)
    messages.extend(author_msg)
    if not author_diversity_ok:
        ok = False

    return ok, messages


def _check_entry_anchor_coverage(root: Path, sources: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Check that entry paper anchors were resolved into the M1 source log."""
    brief_path = root / "state" / "research_brief.yaml"
    if not brief_path.exists():
        return True, []

    messages: list[str] = []
    try:
        with open(brief_path, "r", encoding="utf-8") as f:
            brief = yaml.safe_load(f) or {}
    except Exception as exc:
        return True, [f"[WARN] Could not read research_brief.yaml for entry-anchor checks: {exc}"]

    anchors = [
        anchor
        for anchor in brief.get("anchors", [])
        if anchor.get("kind") == "paper" and _anchor_has_paper_role(anchor)
    ]
    if not anchors:
        return True, []

    ok = True
    for anchor in anchors:
        matched = any(_source_matches_anchor(src, anchor) for src in sources)
        label = _anchor_label(anchor)
        if matched:
            messages.append(f"[PASS] Entry paper anchor covered in M1 source log: {anchor.get('id')} ({label})")
            continue
        if _is_foundation_anchor(anchor):
            messages.append(
                f"[FAIL] Foundation paper anchor missing from M1 source log: "
                f"{anchor.get('id')} ({label}). Add a source with entry_anchor_id={anchor.get('id')} "
                f"or a matching title/url."
            )
            ok = False
        else:
            messages.append(
                f"[WARN] Reference paper anchor not found in M1 source log: "
                f"{anchor.get('id')} ({label}). If unreachable, document why in M1S02."
            )

    return ok, messages


def _anchor_has_paper_role(anchor: dict[str, Any]) -> bool:
    role = str(anchor.get("role", "reference")).lower()
    return role in {"foundation", "reference", "both"}


def _is_foundation_anchor(anchor: dict[str, Any]) -> bool:
    role = str(anchor.get("role", "reference")).lower()
    return role in {"foundation", "both"}


def _anchor_label(anchor: dict[str, Any]) -> str:
    return (
        anchor.get("title_hint")
        or anchor.get("url")
        or anchor.get("canonical_value")
        or anchor.get("raw_value")
        or "untitled"
    )


def _normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _normalize_url(text: str) -> str:
    return text.strip().lower().removeprefix("https://").removeprefix("http://").removesuffix("/")


def _source_matches_anchor(src: dict[str, Any], anchor: dict[str, Any]) -> bool:
    anchor_id = anchor.get("id", "")
    if src.get("entry_anchor_id") == anchor_id:
        return True
    entry_ids = src.get("entry_anchor_ids", [])
    if isinstance(entry_ids, str):
        entry_ids = [entry_ids]
    if anchor_id and anchor_id in entry_ids:
        return True

    anchor_url = str(anchor.get("url") or "").strip()
    if anchor_url:
        norm_anchor_url = _normalize_url(anchor_url)
        for field in ("url", "pdf_url", "code_url"):
            source_url = str(src.get(field) or "").strip()
            if not source_url:
                continue
            norm_source_url = _normalize_url(source_url)
            if norm_anchor_url == norm_source_url or norm_anchor_url in norm_source_url or norm_source_url in norm_anchor_url:
                return True

    title_hint = str(anchor.get("title_hint") or "").strip()
    source_title = str(src.get("title") or "").strip()
    if title_hint and source_title:
        a_title = _normalize_title(title_hint)
        s_title = _normalize_title(source_title)
        if a_title and s_title and (a_title == s_title or a_title in s_title or s_title in a_title):
            return True

    local_asset = str(anchor.get("local_asset") or "").strip()
    if local_asset:
        for field in ("local_asset", "source_path", "file_path", "pdf_path"):
            source_path = str(src.get(field) or "").strip()
            if source_path and (local_asset == source_path or local_asset in source_path):
                return True

    return False


def check_author_diversity(sources: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Check that no single team/institution dominates (>30%).

    Uses first author as team proxy. If author affiliation data is not available,
    falls back to first-author name frequency.
    """
    messages: list[str] = []
    if not sources:
        return True, messages

    # Count by first author (as proxy for team/institution)
    from collections import Counter

    first_authors: list[str] = []
    for src in sources:
        authors = src.get("authors", [])
        if authors and len(authors) > 0:
            first_authors.append(str(authors[0]).strip())

    if not first_authors:
        messages.append("[WARN] No author information available for diversity check")
        return True, messages

    counter = Counter(first_authors)
    total = len(first_authors)
    max_count = counter.most_common(1)[0][1] if counter else 0
    max_author = counter.most_common(1)[0][0] if counter else ""
    max_ratio = max_count / total if total > 0 else 0

    if max_ratio > 0.3:
        messages.append(
            f"[FAIL] Author diversity check failed: "
            f"'{max_author}' appears in {max_count}/{total} sources ({max_ratio:.0%}), "
            f"exceeds 30% threshold. Need broader author/institution coverage."
        )
        return False, messages
    else:
        messages.append(
            f"[PASS] Author diversity check passed: "
            f"most frequent author '{max_author}' in {max_count}/{total} sources ({max_ratio:.0%})"
        )
        return True, messages
