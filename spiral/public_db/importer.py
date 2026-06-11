"""Import / export between project-level source logs and the public DB.

Provides bidirectional sync so that:
- Completed project surveys enrich the public database.
- New projects seed their survey memory from the public database.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from .models import (
    Claim,
    DomainTag,
    LimitationEntry,
    LiteratureArtifact,
    LiteratureDiscovery,
    LiteratureExtraction,
    Paper,
    PaperIdentifiers,
    PaperTag,
    Survey,
)

if TYPE_CHECKING:
    from .manager import PublicLiteratureDB

logger = logging.getLogger(__name__)


class ProjectImporter:
    """Imports literature data from an AutoPaper2 project into the public DB."""

    def __init__(self, public_db: PublicLiteratureDB):
        self.db = public_db

    def import_from_source_log(
        self,
        source_log_path: str | Path,
        project_name: str,
        domain_tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Import papers from a project's ``M1_source_log.yaml``.

        Returns a summary dict with counts of imported, merged, and tagged papers.
        """
        path = Path(source_log_path)
        if not path.exists():
            raise FileNotFoundError(f"Source log not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        sources = data.get("sources", [])
        gap_map = data.get("gap_evidence_map", {})

        imported = 0
        merged = 0
        tagged = 0
        artifacts = 0
        extractions = 0
        discoveries = 0

        for src in sources:
            paper = self._source_to_paper(src, project_name)
            existing_id = self.db.check_duplicate(paper)

            if existing_id:
                # Merge into existing
                self.db.update_paper(paper, source_project=project_name)
                merged += 1
            else:
                # New paper
                self.db.insert_paper(paper, source_project=project_name)
                imported += 1
            canonical_id = existing_id or paper.paper_id

            discoveries += self._import_discovery_records(
                src,
                canonical_id,
                data.get("search_provenance") or data.get("search_strategy") or {},
            )
            artifacts += self._import_artifact_records(src, canonical_id)
            extractions += self._import_extraction_record(src, canonical_id)

            # Apply domain tags if provided
            if domain_tags:
                for tag_id in domain_tags:
                    self.db.tag_paper(
                        canonical_id,
                        tag_id,
                        confidence="high",
                        source="manual",
                        added_by_project=project_name,
                    )
                tagged += 1

        logger.info(
            "Imported %d new, merged %d existing, tagged %d from %s",
            imported, merged, tagged, path,
        )

        return {
            "imported": imported,
            "merged": merged,
            "tagged": tagged,
            "total_sources": len(sources),
            "discoveries": discoveries,
            "artifacts": artifacts,
            "extractions": extractions,
        }

    def import_from_survey_memory(
        self,
        survey_memory_path: str | Path,
        project_name: str,
        domain_tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Import from a project's ``survey_memory.yaml``."""
        path = Path(survey_memory_path)
        if not path.exists():
            raise FileNotFoundError(f"Survey memory not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        registry = data.get("source_registry", {})
        imported = 0
        merged = 0
        artifacts = 0
        extractions = 0

        for source_id, src in registry.items():
            paper = self._source_to_paper(src, project_name)
            existing_id = self.db.check_duplicate(paper)

            if existing_id:
                self.db.update_paper(paper, source_project=project_name)
                merged += 1
            else:
                self.db.insert_paper(paper, source_project=project_name)
                imported += 1
            canonical_id = existing_id or paper.paper_id
            artifacts += self._import_artifact_records(src, canonical_id)
            extractions += self._import_extraction_record(src, canonical_id)

            if domain_tags:
                for tag_id in domain_tags:
                    self.db.tag_paper(
                        canonical_id,
                        tag_id,
                        confidence="high",
                        source="manual",
                        added_by_project=project_name,
                    )

        return {
            "imported": imported,
            "merged": merged,
            "artifacts": artifacts,
            "extractions": extractions,
            "total_sources": len(registry),
        }

    def export_to_survey_memory(
        self,
        paper_ids: list[str],
    ) -> dict[str, Any]:
        """Export selected papers from the public DB into survey-memory-compatible format."""
        papers = [self.db.get_paper(pid) for pid in paper_ids]
        papers = [p for p in papers if p is not None]

        source_registry = {}
        for paper in papers:
            source_registry[paper.paper_id] = {
                "id": paper.paper_id,
                "title": paper.title,
                "authors": paper.authors,
                "venue": paper.venue,
                "date": paper.date,
                "url": paper.url,
                "type": paper.type,
                "credibility": paper.credibility_score,
                "verification": paper.verification_status,
                "key_claims": [],
                "limitations_noted": [lim.limitation for lim in paper.limitations_noted],
                "code_availability": paper.code_availability,
                "relevance_to_our_gap": "",
                "pdf_url": paper.pdf_url,
            }
            artifacts = self.db.list_artifacts(paper.paper_id)
            if artifacts:
                source_registry[paper.paper_id]["artifacts"] = [
                    artifact.to_dict() for artifact in artifacts
                ]
            extraction = self.db.get_extraction(paper.paper_id)
            if extraction:
                source_registry[paper.paper_id]["parse_profile"] = extraction.to_dict()

        return {"source_registry": source_registry}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _source_to_paper(src: dict[str, Any], project_name: str) -> Paper:
        """Convert a source-log entry to a Paper model."""
        limitations = src.get("limitations_noted", [])
        if limitations and isinstance(limitations[0], str):
            lim_entries = [
                LimitationEntry(limitation=lim, source_project=project_name)
                for lim in limitations
            ]
        else:
            lim_entries = [
                LimitationEntry(
                    limitation=lim.get("limitation", ""),
                    source_project=lim.get("source_project", project_name),
                    noted_at=lim.get("noted_at", ""),
                )
                for lim in limitations
            ]

        return Paper(
            paper_id=src.get("id", ""),
            title=src.get("title", ""),
            authors=src.get("authors", []),
            venue=src.get("venue", ""),
            year=src.get("year", 0) or 0,
            date=src.get("date", ""),
            url=src.get("url", ""),
            pdf_url=src.get("pdf_url", ""),
            type=src.get("type", "academic"),
            identifiers=PaperIdentifiers.from_dict(src.get("identifiers")),
            credibility_score=src.get("credibility", 3),
            verification_status=src.get("verification", "unverified"),
            code_availability=src.get("code_availability", "closed"),
            code_url=src.get("code_url", ""),
            abstract=src.get("abstract", ""),
            problem_statement=src.get("problem_statement", ""),
            method_summary=src.get("method_summary") or src.get("method", ""),
            key_results=src.get("key_results", []) or _as_list(src.get("results")),
            limitations_noted=lim_entries,
            first_surveyed_at=src.get("first_surveyed_at", ""),
            last_updated_at=src.get("last_updated_at", ""),
            citation_count=src.get("citation_count", 0) or 0,
        )

    def _import_discovery_records(
        self,
        src: dict[str, Any],
        paper_id: str,
        search_provenance: dict[str, Any],
    ) -> int:
        count = 0
        records = _as_list(src.get("discovery_records") or src.get("discovery"))
        if not records and (src.get("discovery_source") or src.get("discovery_query")):
            records = [
                {
                    "search_surface": src.get("discovery_source", ""),
                    "query_text": src.get("discovery_query", ""),
                    "result_url": src.get("url", ""),
                    "screened_status": "retained",
                    "retained_reason": src.get("relevance_to_our_gap", ""),
                }
            ]
        if not records and isinstance(search_provenance, dict):
            for round_data in _as_list(search_provenance.get("rounds") or search_provenance.get("search_rounds")):
                if not isinstance(round_data, dict):
                    continue
                retained_ids = {
                    str(item)
                    for item in _as_list(
                        round_data.get("retained_source_ids")
                        or round_data.get("source_ids")
                        or round_data.get("retained_sources")
                    )
                }
                if paper_id in retained_ids or str(src.get("id", "")) in retained_ids:
                    queries = _as_list(round_data.get("queries"))
                    records.append(
                        {
                            "search_surface": ",".join(_as_list(search_provenance.get("databases"))),
                            "query_text": " | ".join(str(q) for q in queries),
                            "screened_status": "retained",
                            "retained_reason": str(round_data.get("purpose") or round_data.get("goal") or ""),
                        }
                    )
        for raw in records:
            if not isinstance(raw, dict):
                continue
            discovery = LiteratureDiscovery(
                discovery_id=raw.get("discovery_id", ""),
                paper_id=paper_id,
                search_surface=raw.get("search_surface") or raw.get("source") or raw.get("surface") or "",
                query_text=raw.get("query_text") or raw.get("query") or "",
                result_rank=raw.get("result_rank") or raw.get("rank") or 0,
                result_url=raw.get("result_url") or raw.get("url") or src.get("url", ""),
                metadata_source=raw.get("metadata_source", ""),
                discovered_at=raw.get("discovered_at", ""),
                screened_status=raw.get("screened_status", "retained"),
                retained_reason=raw.get("retained_reason", ""),
                notes=raw.get("notes", ""),
            )
            self.db.upsert_discovery(discovery)
            count += 1
        return count

    def _import_artifact_records(self, src: dict[str, Any], paper_id: str) -> int:
        count = 0
        records = _as_list(src.get("artifacts"))
        if src.get("pdf_url") and not any(
            isinstance(record, dict) and record.get("artifact_type") == "pdf"
            for record in records
        ):
            records.append(
                {
                    "artifact_type": "pdf",
                    "uri": src.get("pdf_url", ""),
                    "local_path": src.get("pdf_path", ""),
                    "status": src.get("pdf_status", "available" if src.get("pdf_path") else "unknown"),
                    "failure_reason": src.get("pdf_failure_reason", ""),
                    "recovery_actions": src.get("pdf_recovery_actions", []),
                    "license_note": src.get("license_note", ""),
                }
            )
        for raw in records:
            if not isinstance(raw, dict):
                continue
            artifact = LiteratureArtifact(
                artifact_id=raw.get("artifact_id", ""),
                paper_id=paper_id,
                artifact_type=raw.get("artifact_type", "pdf"),
                uri=raw.get("uri", ""),
                local_path=raw.get("local_path") or raw.get("path") or "",
                status=raw.get("status", "unknown"),
                sha256=raw.get("sha256", ""),
                attempted_at=raw.get("attempted_at", ""),
                updated_at=raw.get("updated_at", ""),
                failure_reason=raw.get("failure_reason", ""),
                recovery_actions=_as_list(raw.get("recovery_actions")),
                license_note=raw.get("license_note", ""),
                notes=raw.get("notes", ""),
            )
            self.db.upsert_artifact(artifact)
            count += 1
        return count

    def _import_extraction_record(self, src: dict[str, Any], paper_id: str) -> int:
        parse_profile = src.get("parse_profile") or src.get("extraction") or {}
        section_summaries = dict(parse_profile.get("section_summaries", {})) if isinstance(parse_profile, dict) else {}
        if not section_summaries:
            section_summaries = {
                "background": src.get("background", ""),
                "contributions": src.get("contributions", []),
                "model": src.get("model", ""),
                "method": src.get("method", ""),
                "experiment_setup": src.get("experiment_setup", ""),
                "results": src.get("results", ""),
                "analysis": src.get("analysis", ""),
                "conclusion": src.get("conclusion", ""),
            }
        downstream_signals = (
            parse_profile.get("downstream_signals", {})
            if isinstance(parse_profile, dict)
            else {}
        )
        if not downstream_signals:
            downstream_signals = {
                "M2": {
                    "method_reference": bool(src.get("method") or src.get("method_summary")),
                    "core_mechanism": src.get("method") or src.get("method_summary", ""),
                },
                "M3": {
                    "experiment_protocol": bool(src.get("experiment_setup")),
                    "datasets_metrics_baselines": src.get("experiment_setup", ""),
                },
                "M4": {
                    "analysis_patterns": bool(src.get("analysis")),
                    "analysis": src.get("analysis", ""),
                },
                "M5": {
                    "citation_ready": bool(src.get("title") and src.get("authors")),
                    "writing_context": src.get("conclusion", ""),
                },
            }

        required = {
            "background": section_summaries.get("background"),
            "contributions": section_summaries.get("contributions"),
            "model": section_summaries.get("model"),
            "method": section_summaries.get("method"),
            "experiment_setup": section_summaries.get("experiment_setup"),
            "results": section_summaries.get("results"),
            "analysis": section_summaries.get("analysis"),
            "conclusion": section_summaries.get("conclusion"),
        }
        missing = [key for key, value in required.items() if not value]
        if isinstance(parse_profile, dict) and parse_profile.get("missing_fields") is not None:
            missing = _as_list(parse_profile.get("missing_fields"))
        parse_status = (
            parse_profile.get("parse_status")
            if isinstance(parse_profile, dict)
            else None
        ) or ("complete" if not missing else "partial")
        metadata_status = (
            parse_profile.get("metadata_status")
            if isinstance(parse_profile, dict)
            else None
        ) or ("complete" if src.get("title") and src.get("authors") else "partial")
        extraction = LiteratureExtraction(
            paper_id=paper_id,
            metadata_status=metadata_status,
            fulltext_status=(
                parse_profile.get("fulltext_status")
                if isinstance(parse_profile, dict)
                else None
            ) or ("parsed" if not missing else "metadata_only"),
            parse_status=parse_status,
            parse_backend=(
                parse_profile.get("parse_backend")
                if isinstance(parse_profile, dict)
                else None
            ) or "source_log_card",
            parsed_at=(
                parse_profile.get("parsed_at")
                if isinstance(parse_profile, dict)
                else None
            ) or "",
            extraction_sources=_as_list(
                parse_profile.get("extraction_sources") if isinstance(parse_profile, dict) else []
            ) or ["source_log"],
            missing_fields=missing,
            section_summaries=section_summaries,
            downstream_signals=downstream_signals,
            confidence=(
                parse_profile.get("confidence")
                if isinstance(parse_profile, dict)
                else None
            ) or ("high" if not missing else "medium"),
            notes=(parse_profile.get("notes", "") if isinstance(parse_profile, dict) else ""),
        )
        self.db.upsert_extraction(extraction)
        return 1


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value in (None, ""):
        return []
    return [value]


class DomainTagImporter:
    """Bulk imports a domain tag taxonomy from YAML/JSON."""

    def __init__(self, public_db: PublicLiteratureDB):
        self.db = public_db

    def import_from_yaml(self, path: str | Path) -> int:
        """Import domain tags from a YAML file. Returns count imported."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Tag file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        tags = data.get("domain_tags", [])
        count = 0
        for tag_data in tags:
            tag = DomainTag.from_dict(tag_data)
            self.db.insert_or_update_tag(tag)
            count += 1

        logger.info("Imported %d domain tags from %s", count, path)
        return count
