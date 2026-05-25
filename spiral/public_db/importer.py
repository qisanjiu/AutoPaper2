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

from .models import Claim, DomainTag, LimitationEntry, Paper, PaperIdentifiers, PaperTag, Survey

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

            # Apply domain tags if provided
            if domain_tags:
                for tag_id in domain_tags:
                    self.db.tag_paper(
                        paper.paper_id,
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

        for source_id, src in registry.items():
            paper = self._source_to_paper(src, project_name)
            existing_id = self.db.check_duplicate(paper)

            if existing_id:
                self.db.update_paper(paper, source_project=project_name)
                merged += 1
            else:
                self.db.insert_paper(paper, source_project=project_name)
                imported += 1

            if domain_tags:
                for tag_id in domain_tags:
                    self.db.tag_paper(
                        paper.paper_id,
                        tag_id,
                        confidence="high",
                        source="manual",
                        added_by_project=project_name,
                    )

        return {
            "imported": imported,
            "merged": merged,
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
            }

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
            date=src.get("date", ""),
            url=src.get("url", ""),
            type=src.get("type", "academic"),
            credibility_score=src.get("credibility", 3),
            verification_status=src.get("verification", "unverified"),
            code_availability=src.get("code_availability", "closed"),
            limitations_noted=lim_entries,
            first_surveyed_at=src.get("first_surveyed_at", ""),
            last_updated_at=src.get("last_updated_at", ""),
        )


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
