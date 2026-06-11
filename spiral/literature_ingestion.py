"""Helpers for literature search, artifact triage, parsing, and source-log repair."""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import importlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


USER_AGENT = "AutoPaper2 literature ingestion (https://github.com/)"
DEFAULT_SURFACES = (
    "openalex",
    "crossref",
    "semantic_scholar",
    "arxiv",
    "dblp",
    "europe_pmc",
    "doaj",
    "ieee",
    "elsevier",
    "springer",
    "core",
    "wos",
    "acm",
    "wiley",
)
MAX_PDF_BYTES = 50 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("AUTOPAPER2_REQUEST_TIMEOUT_SECONDS", "20"))
DOWNLOAD_TIMEOUT_SECONDS = int(os.environ.get("AUTOPAPER2_DOWNLOAD_TIMEOUT_SECONDS", "12"))
MIN_FULLTEXT_CHARS = 4000
MAX_PDF_DOWNLOAD_ATTEMPTS_PER_SOURCE = int(os.environ.get("AUTOPAPER2_MAX_PDF_ATTEMPTS_PER_SOURCE", "1"))
MAX_HTML_DOWNLOAD_ATTEMPTS_PER_SOURCE = int(os.environ.get("AUTOPAPER2_MAX_HTML_ATTEMPTS_PER_SOURCE", "1"))
MAX_UNPAYWALL_LOCATIONS = int(os.environ.get("AUTOPAPER2_MAX_UNPAYWALL_LOCATIONS", "4"))
SKIP_UNPAYWALL = os.environ.get("AUTOPAPER2_SKIP_UNPAYWALL", "").lower() in {"1", "true", "yes"}
SKIP_CROSSREF_FULLTEXT = os.environ.get("AUTOPAPER2_SKIP_CROSSREF_FULLTEXT", "").lower() in {"1", "true", "yes"}
BROWSER_SESSION_STATE_ENV = "AUTOPAPER2_BROWSER_SESSION_STATE"
DEFAULT_BROWSER_AUTH_URL = "https://ieeexplore.ieee.org/"
DEFAULT_BROWSER_SESSION_STATE = "config/browser_sessions/literature_storage_state.json"
DEFAULT_BROWSER_PROFILE_DIR = "config/browser_sessions/literature_profile"


class CredentialRequired(RuntimeError):
    """Raised when a database connector needs a user-provided credential."""


@dataclass
class LiteratureIngestionReport:
    sources_seen: int = 0
    discovery_added: int = 0
    artifacts_added: int = 0
    parse_profiles_added: int = 0
    artifact_checked: int = 0
    pdf_checked: int = 0
    pdf_download_attempted: int = 0
    pdf_downloaded: int = 0
    pdf_parse_attempted: int = 0
    pdf_parsed: int = 0
    html_download_attempted: int = 0
    html_downloaded: int = 0
    html_parsed: int = 0
    xml_download_attempted: int = 0
    xml_downloaded: int = 0
    xml_parsed: int = 0
    browser_download_attempted: int = 0
    browser_downloaded: int = 0
    browser_download_failed: int = 0
    browser_xml_downloaded: int = 0
    fulltext_artifacts_added: int = 0
    credential_blocked: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources_seen": self.sources_seen,
            "discovery_added": self.discovery_added,
            "artifacts_added": self.artifacts_added,
            "parse_profiles_added": self.parse_profiles_added,
            "artifact_checked": self.artifact_checked,
            "pdf_checked": self.pdf_checked,
            "pdf_download_attempted": self.pdf_download_attempted,
            "pdf_downloaded": self.pdf_downloaded,
            "pdf_parse_attempted": self.pdf_parse_attempted,
            "pdf_parsed": self.pdf_parsed,
            "html_download_attempted": self.html_download_attempted,
            "html_downloaded": self.html_downloaded,
            "html_parsed": self.html_parsed,
            "xml_download_attempted": self.xml_download_attempted,
            "xml_downloaded": self.xml_downloaded,
            "xml_parsed": self.xml_parsed,
            "browser_download_attempted": self.browser_download_attempted,
            "browser_downloaded": self.browser_downloaded,
            "browser_download_failed": self.browser_download_failed,
            "browser_xml_downloaded": self.browser_xml_downloaded,
            "fulltext_artifacts_added": self.fulltext_artifacts_added,
            "credential_blocked": self.credential_blocked,
            "warnings": self.warnings,
        }


def search_literature(
    query: str,
    *,
    limit: int = 10,
    surfaces: list[str] | tuple[str, ...] = DEFAULT_SURFACES,
) -> dict[str, Any]:
    """Search public scholarly surfaces and return a source-log-like payload."""
    sources: list[dict[str, Any]] = []
    search_rounds: list[dict[str, Any]] = []
    queries = _query_variants(query)
    for surface in surfaces:
        surface = surface.lower().strip()
        found: list[dict[str, Any]] = []
        surface_failures: list[str] = []
        per_query_limit = max(1, min(limit, max(1, (limit + len(queries) - 1) // len(queries))))
        retrieved_total = 0
        retained_for_surface: list[str] = []
        query_texts: list[str] = []
        try:
            for expanded_query in queries:
                query_texts.append(expanded_query)
                per_query_limit = max(1, min(limit, 50))
                if surface == "openalex":
                    batch = _search_openalex(expanded_query, per_query_limit)
                elif surface == "crossref":
                    batch = _search_crossref(expanded_query, per_query_limit)
                elif surface in {"semantic_scholar", "semanticscholar"}:
                    batch = _search_semantic_scholar(expanded_query, per_query_limit)
                elif surface == "arxiv":
                    batch = _search_arxiv(expanded_query, per_query_limit)
                elif surface == "dblp":
                    batch = _search_dblp(expanded_query, per_query_limit)
                elif surface == "europe_pmc":
                    batch = _search_europe_pmc(expanded_query, per_query_limit)
                elif surface == "doaj":
                    batch = _search_doaj(expanded_query, per_query_limit)
                elif surface == "ieee":
                    batch = _search_ieee(expanded_query, per_query_limit)
                elif surface == "elsevier":
                    batch = _search_elsevier(expanded_query, per_query_limit)
                elif surface == "springer":
                    batch = _search_springer(expanded_query, per_query_limit)
                elif surface == "core":
                    batch = _search_core(expanded_query, per_query_limit)
                elif surface == "wos":
                    batch = _search_wos(expanded_query, per_query_limit)
                elif surface == "acm":
                    batch = _search_acm(expanded_query, per_query_limit)
                elif surface == "wiley":
                    batch = _search_wiley(expanded_query, per_query_limit)
                else:
                    continue
                found.extend(batch)
                retrieved_total += len(batch)
                retained_for_surface.extend(src["id"] for src in batch if src.get("id"))
                if found:
                    break
        except Exception as exc:
            surface_failures.append(str(exc))
            search_rounds.append(
                {
                    "round": len(search_rounds) + 1,
                    "goal": f"{surface} search failed",
                    "queries": query_texts or [query],
                    "retrieved_count": retrieved_total,
                    "screened_count": retrieved_total,
                    "retained_source_ids": [],
                    "failure_reason": "; ".join(surface_failures),
                }
            )
            continue
        sources.extend(found)
        search_rounds.append(
            {
                "round": len(search_rounds) + 1,
                "goal": f"{surface} keyword search",
                "queries": query_texts,
                "retrieved_count": retrieved_total,
                "screened_count": retrieved_total,
                "retained_source_ids": retained_for_surface,
            }
        )

    merged_sources = _dedupe_sources(sources)
    screened_sources, screening_exclusions = _screen_sources_for_query(merged_sources, query)
    retained_ids = {str(src.get("id")) for src in screened_sources if src.get("id")}
    for search_round in search_rounds:
        search_round["retained_source_ids"] = [
            source_id
            for source_id in _as_list(search_round.get("retained_source_ids"))
            if str(source_id) in retained_ids
        ]
    return {
        "search_provenance": {
            "databases": list(surfaces),
            "inclusion_criteria": ["keyword match", "academic metadata record"],
            "exclusion_criteria": [
                "duplicate metadata record",
                "empty title",
                "low query-specific term coverage",
            ],
            "rounds": search_rounds,
            "screening_exclusions": screening_exclusions,
            "publisher_coverage": _publisher_coverage(screened_sources),
            "database_limitations": [
                "IEEE Xplore, Elsevier/ScienceDirect/Scopus, Springer Nature, CORE, Web of Science, ACM, and Wiley direct connectors require API keys or institutional/TDM access.",
                "When credentials are unavailable, publisher coverage is inferred from DOI prefixes, venues, publisher fields, and indexed metadata from OpenAlex/Crossref/Semantic Scholar/DBLP.",
            ],
            "blindspot_checks": {
                "recent_work": "pending manual review",
                "negative_results": "pending manual review",
                "seminal_work": "pending manual review",
                "key_authors": "pending manual review",
                "source_log_consistency": "generated source ids are stable and deduplicated",
            },
        },
        "sources": screened_sources,
        "gap_evidence_map": {},
    }


def prepare_source_log(
    source_log_path: str | Path,
    *,
    output_path: str | Path | None = None,
    project_root: str | Path | None = None,
    module: str = "M1",
    network_check: bool = False,
    download_pdfs: bool = False,
    fetch_fulltext: bool = False,
    parse_local_pdfs: bool = False,
    max_sources: int | None = None,
    skip_unpaywall: bool = False,
    skip_crossref_fulltext: bool = False,
    browser_downloads: bool = False,
    browser_session_state: str | Path | None = None,
) -> LiteratureIngestionReport:
    """Normalize an existing M1/M2 source log in-place or to another path."""
    path = Path(source_log_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    report = normalize_source_log_data(
        data,
        module=module,
        project_root=project_root or path.parent.parent.parent,
        network_check=network_check,
        download_pdfs=download_pdfs,
        fetch_fulltext=fetch_fulltext,
        parse_local_pdfs=parse_local_pdfs,
        max_sources=max_sources,
        skip_unpaywall=skip_unpaywall,
        skip_crossref_fulltext=skip_crossref_fulltext,
        browser_downloads=browser_downloads,
        browser_session_state=browser_session_state,
    )
    target = Path(output_path) if output_path else path
    target.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report


def normalize_source_log_data(
    data: dict[str, Any],
    *,
    module: str = "M1",
    project_root: str | Path | None = None,
    network_check: bool = False,
    download_pdfs: bool = False,
    fetch_fulltext: bool = False,
    parse_local_pdfs: bool = False,
    max_sources: int | None = None,
    skip_unpaywall: bool = False,
    skip_crossref_fulltext: bool = False,
    browser_downloads: bool = False,
    browser_session_state: str | Path | None = None,
) -> LiteratureIngestionReport:
    """Add missing discovery/artifact/parse records without inventing claims."""
    report = LiteratureIngestionReport()
    project_root_path = Path(project_root).resolve() if project_root else None
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        report.warnings.append("source log has no list-valued sources field")
        return report

    provenance = data.get("search_provenance") or data.get("search_strategy") or {}
    processed_sources = 0
    for idx, src in enumerate(sources, start=1):
        if not isinstance(src, dict) or src.get("type", "academic") != "academic":
            continue
        if max_sources is not None and processed_sources >= max_sources:
            report.warnings.append(f"Stopped after max_sources={max_sources}; rerun in batches for remaining sources.")
            break
        processed_sources += 1
        report.sources_seen += 1
        source_id = _source_id(src, idx)
        if not src.get("id"):
            src["id"] = source_id

        if _ensure_discovery_record(src, source_id, provenance):
            report.discovery_added += 1

        artifact_added = _ensure_artifact_records(
            src,
            source_id,
            project_root=project_root_path,
            network_check=network_check,
            download_pdfs=download_pdfs,
            fetch_fulltext=fetch_fulltext,
            skip_unpaywall=skip_unpaywall,
            skip_crossref_fulltext=skip_crossref_fulltext,
            browser_downloads=browser_downloads,
            browser_session_state=browser_session_state,
            report=report,
        )
        report.artifacts_added += artifact_added

        if _ensure_parse_profile(
            src,
            source_id,
            module=module,
            project_root=project_root_path,
            parse_local_pdfs=parse_local_pdfs,
            parse_local_fulltext=fetch_fulltext,
            report=report,
        ):
            report.parse_profiles_added += 1

    return report


def _search_openalex(query: str, limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"search": query, "per-page": max(1, min(limit, 50))})
    payload = _http_json(f"https://api.openalex.org/works?{params}")
    results = payload.get("results", [])
    sources: list[dict[str, Any]] = []
    for rank, item in enumerate(results, start=1):
        title = item.get("title") or ""
        if not title:
            continue
        doi = _normalize_doi(item.get("doi", ""))
        openalex_id = item.get("id", "")
        paper_id = doi or openalex_id.rsplit("/", 1)[-1] or _slug(title)
        authors = [
            auth.get("author", {}).get("display_name", "")
            for auth in item.get("authorships", [])
            if auth.get("author", {}).get("display_name")
        ]
        venue = (
            (item.get("primary_location") or {}).get("source") or {}
        ).get("display_name", "")
        best_location = item.get("best_oa_location") or item.get("primary_location") or {}
        pdf_url = best_location.get("pdf_url") or ""
        url = best_location.get("landing_page_url") or item.get("doi") or openalex_id
        source = {
            "id": _stable_source_id("openalex", paper_id),
            "title": title,
            "authors": authors,
            "venue": venue,
            "year": item.get("publication_year") or 0,
            "date": item.get("publication_date") or "",
            "url": url,
            "pdf_url": pdf_url,
            "type": "academic",
            "credibility": 4,
            "verification": "unverified",
            "identifiers": {"doi": doi or None, "semantic_scholar_id": None},
            "citation_count": item.get("cited_by_count") or 0,
            "abstract": _openalex_abstract(item.get("abstract_inverted_index")),
            "discovery_records": [_discovery("openalex", query, rank, url)],
        }
        _ensure_artifact_records(source, source["id"], project_root=None, network_check=False, download_pdfs=False)
        _ensure_parse_profile(source, source["id"], module="M1", project_root=None, parse_local_pdfs=False)
        sources.append(source)
    return sources


def _search_crossref(query: str, limit: int) -> list[dict[str, Any]]:
    return _search_crossref_filtered(query, limit, surface="crossref")


def _search_crossref_filtered(
    query: str,
    limit: int,
    *,
    surface: str,
    filters: list[str] | tuple[str, ...] = (),
    publisher_override: str = "",
) -> list[dict[str, Any]]:
    query_params: dict[str, str | int] = {
        "query.bibliographic": query,
        "rows": max(1, min(limit, 50)),
    }
    if filters:
        query_params["filter"] = ",".join(filters)
    params = urllib.parse.urlencode(
        query_params
    )
    payload = _http_json(f"https://api.crossref.org/works?{params}")
    items = payload.get("message", {}).get("items", [])
    sources: list[dict[str, Any]] = []
    for rank, item in enumerate(items, start=1):
        title = " ".join(item.get("title") or []).strip()
        if not title:
            continue
        doi = _normalize_doi(item.get("DOI", ""))
        authors = [
            " ".join(part for part in (a.get("given", ""), a.get("family", "")) if part).strip()
            for a in item.get("author", [])
        ]
        authors = [a for a in authors if a]
        issued = item.get("issued", {}).get("date-parts", [[]])[0]
        year = issued[0] if issued else 0
        venue = " ".join(item.get("container-title") or []).strip()
        url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")
        abstract = _clean_crossref_abstract(item.get("abstract", ""))
        source = {
            "id": _stable_source_id("crossref", doi or title),
            "title": title,
            "authors": authors,
            "venue": venue,
            "publisher": publisher_override or item.get("publisher", ""),
            "year": year,
            "date": "-".join(str(x) for x in issued) if issued else "",
            "url": url,
            "type": "academic",
            "credibility": 4,
            "verification": "unverified",
            "identifiers": {"doi": doi or None},
            "abstract": abstract,
            "artifacts": _crossref_link_artifacts(item),
            "discovery_records": [_discovery(surface, query, rank, url)],
        }
        _enrich_source_from_openalex_doi(source)
        _ensure_artifact_records(source, source["id"], project_root=None, network_check=False, download_pdfs=False)
        _ensure_parse_profile(source, source["id"], module="M1", project_root=None, parse_local_pdfs=False)
        sources.append(source)
    return sources


def _search_semantic_scholar(query: str, limit: int) -> list[dict[str, Any]]:
    fields = ",".join(
        [
            "title",
            "authors",
            "year",
            "venue",
            "url",
            "abstract",
            "citationCount",
            "externalIds",
            "openAccessPdf",
            "isOpenAccess",
            "publicationDate",
        ]
    )
    params = urllib.parse.urlencode(
        {
            "query": query,
            "limit": max(1, min(limit, 50)),
            "fields": fields,
        }
    )
    payload = _http_json(f"https://api.semanticscholar.org/graph/v1/paper/search?{params}")
    sources: list[dict[str, Any]] = []
    for rank, item in enumerate(payload.get("data", []), start=1):
        title = item.get("title") or ""
        if not title:
            continue
        external_ids = item.get("externalIds") or {}
        doi = _normalize_doi(external_ids.get("DOI", ""))
        arxiv_id = external_ids.get("ArXiv") or external_ids.get("ArXivId") or ""
        paper_id = item.get("paperId") or doi or arxiv_id or title
        open_access_pdf = item.get("openAccessPdf") or {}
        pdf_url = open_access_pdf.get("url") or _derive_pdf_url(
            f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
        )
        url = item.get("url") or (f"https://doi.org/{doi}" if doi else "")
        identifiers = {
            "doi": doi or None,
            "semantic_scholar_id": item.get("paperId") or None,
        }
        if arxiv_id:
            identifiers["arxiv_id"] = arxiv_id
        source = {
            "id": _stable_source_id("semantic_scholar", paper_id),
            "title": title,
            "authors": [
                author.get("name", "")
                for author in item.get("authors", [])
                if author.get("name")
            ],
            "venue": item.get("venue", ""),
            "year": item.get("year") or 0,
            "date": item.get("publicationDate") or "",
            "url": url,
            "pdf_url": pdf_url,
            "type": "academic",
            "credibility": 4,
            "verification": "unverified",
            "identifiers": identifiers,
            "citation_count": item.get("citationCount") or 0,
            "abstract": item.get("abstract") or "",
            "discovery_records": [_discovery("semantic_scholar", query, rank, url)],
        }
        _ensure_artifact_records(source, source["id"], project_root=None, network_check=False, download_pdfs=False)
        _ensure_parse_profile(source, source["id"], module="M1", project_root=None, parse_local_pdfs=False)
        sources.append(source)
    return sources


def _search_arxiv(query: str, limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max(1, min(limit, 50)),
        }
    )
    raw = _http_bytes(f"https://export.arxiv.org/api/query?{params}")
    root = ET.fromstring(raw)
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    sources: list[dict[str, Any]] = []
    for rank, entry in enumerate(root.findall("atom:entry", ns), start=1):
        title = " ".join((entry.findtext("atom:title", default="", namespaces=ns) or "").split())
        if not title:
            continue
        abs_url = entry.findtext("atom:id", default="", namespaces=ns)
        arxiv_id = abs_url.rsplit("/", 1)[-1]
        pdf_url = ""
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href", "")
        authors = [
            node.findtext("atom:name", default="", namespaces=ns)
            for node in entry.findall("atom:author", ns)
        ]
        published = entry.findtext("atom:published", default="", namespaces=ns)
        year_match = re.match(r"(\d{4})", published or "")
        source = {
            "id": _stable_source_id("arxiv", arxiv_id),
            "title": title,
            "authors": [a for a in authors if a],
            "venue": "arXiv",
            "year": int(year_match.group(1)) if year_match else 0,
            "date": published[:10] if published else "",
            "url": abs_url,
            "pdf_url": pdf_url,
            "type": "academic",
            "credibility": 4,
            "verification": "unverified",
            "identifiers": {"arxiv_id": arxiv_id},
            "abstract": " ".join((entry.findtext("atom:summary", default="", namespaces=ns) or "").split()),
            "discovery_records": [_discovery("arxiv", query, rank, abs_url)],
        }
        _ensure_artifact_records(source, source["id"], project_root=None, network_check=False, download_pdfs=False)
        _ensure_parse_profile(source, source["id"], module="M1", project_root=None, parse_local_pdfs=False)
        sources.append(source)
    return sources


def _search_dblp(query: str, limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"q": query, "format": "json", "h": max(1, min(limit, 50))})
    payload = _http_json(f"https://dblp.org/search/publ/api?{params}")
    hits = payload.get("result", {}).get("hits", {}).get("hit", [])
    sources: list[dict[str, Any]] = []
    for rank, hit in enumerate(_as_list(hits), start=1):
        info = hit.get("info", {}) if isinstance(hit, dict) else {}
        title = _strip_trailing_period(info.get("title", ""))
        if not title:
            continue
        authors_raw = info.get("authors", {}).get("author", [])
        authors = [
            str(author.get("text", author) if isinstance(author, dict) else author)
            for author in _as_list(authors_raw)
        ]
        url = info.get("ee") or info.get("url") or ""
        doi = _normalize_doi(info.get("doi", ""))
        source = {
            "id": _stable_source_id("dblp", doi or url or title),
            "title": title,
            "authors": [a for a in authors if a],
            "venue": info.get("venue", ""),
            "year": int(info.get("year") or 0),
            "date": str(info.get("year") or ""),
            "url": url,
            "pdf_url": _derive_pdf_url(url),
            "type": "academic",
            "credibility": 4,
            "verification": "unverified",
            "identifiers": {"doi": doi or None, "dblp_id": info.get("key")},
            "discovery_records": [_discovery("dblp", query, rank, url)],
        }
        _ensure_artifact_records(source, source["id"], project_root=None, network_check=False, download_pdfs=False)
        _ensure_parse_profile(source, source["id"], module="M1", project_root=None, parse_local_pdfs=False)
        sources.append(source)
    return sources


def _search_europe_pmc(query: str, limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"query": query, "format": "json", "pageSize": max(1, min(limit, 25))})
    payload = _http_json(f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?{params}")
    results = payload.get("resultList", {}).get("result", [])
    sources: list[dict[str, Any]] = []
    for rank, item in enumerate(results, start=1):
        title = item.get("title") or ""
        if not title:
            continue
        doi = _normalize_doi(item.get("doi", ""))
        pmcid = item.get("pmcid", "")
        url = (
            f"https://europepmc.org/article/{item.get('source', 'MED')}/{item.get('id')}"
            if item.get("id")
            else (f"https://doi.org/{doi}" if doi else "")
        )
        pdf_url = f"https://europepmc.org/articles/{pmcid}?pdf=render" if pmcid else ""
        source = {
            "id": _stable_source_id("europe_pmc", doi or pmcid or title),
            "title": title,
            "authors": [a.strip() for a in str(item.get("authorString", "")).split(",") if a.strip()],
            "venue": item.get("journalTitle", ""),
            "year": int(item.get("pubYear") or 0),
            "date": item.get("firstPublicationDate") or item.get("pubYear", ""),
            "url": url,
            "pdf_url": pdf_url,
            "type": "academic",
            "credibility": 4,
            "verification": "unverified",
            "identifiers": {"doi": doi or None, "pmcid": pmcid or None, "pmid": item.get("pmid") or None},
            "abstract": item.get("abstractText", ""),
            "discovery_records": [_discovery("europe_pmc", query, rank, url)],
        }
        _ensure_artifact_records(source, source["id"], project_root=None, network_check=False, download_pdfs=False)
        _ensure_parse_profile(source, source["id"], module="M1", project_root=None, parse_local_pdfs=False)
        sources.append(source)
    return sources


def _search_doaj(query: str, limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"pageSize": max(1, min(limit, 100))})
    payload = _http_json(f"https://doaj.org/api/search/articles/{urllib.parse.quote(query)}?{params}")
    results = payload.get("results", [])
    sources: list[dict[str, Any]] = []
    for rank, item in enumerate(results, start=1):
        bibjson = item.get("bibjson", {})
        title = bibjson.get("title", "")
        if not title:
            continue
        identifiers = {i.get("type", "").lower(): i.get("id", "") for i in _as_list(bibjson.get("identifier")) if isinstance(i, dict)}
        doi = _normalize_doi(identifiers.get("doi", ""))
        links = _as_list(bibjson.get("link"))
        pdf_url = ""
        landing = ""
        for link in links:
            if not isinstance(link, dict):
                continue
            link_url = link.get("url", "")
            if link.get("type") == "fulltext" and link_url.lower().endswith(".pdf"):
                pdf_url = link_url
            landing = landing or link_url
        source = {
            "id": _stable_source_id("doaj", doi or item.get("id", "") or title),
            "title": title,
            "authors": [a.get("name", "") for a in _as_list(bibjson.get("author")) if isinstance(a, dict) and a.get("name")],
            "venue": (bibjson.get("journal") or {}).get("title", ""),
            "year": int(str(bibjson.get("year") or 0)[:4] or 0),
            "date": str(bibjson.get("year") or ""),
            "url": landing or (f"https://doi.org/{doi}" if doi else ""),
            "pdf_url": pdf_url,
            "type": "academic",
            "credibility": 4,
            "verification": "unverified",
            "identifiers": {"doi": doi or None},
            "abstract": " ".join(_as_list(bibjson.get("abstract"))),
            "discovery_records": [_discovery("doaj", query, rank, landing)],
        }
        _ensure_artifact_records(source, source["id"], project_root=None, network_check=False, download_pdfs=False)
        _ensure_parse_profile(source, source["id"], module="M1", project_root=None, parse_local_pdfs=False)
        sources.append(source)
    return sources


def _search_ieee(query: str, limit: int) -> list[dict[str, Any]]:
    api_key = os.environ.get("IEEE_API_KEY") or os.environ.get("IEEE_XPLORE_API_KEY")
    if not api_key:
        raise CredentialRequired("IEEE Xplore connector requires IEEE_API_KEY or IEEE_XPLORE_API_KEY")
    params = urllib.parse.urlencode(
        {"apikey": api_key, "format": "json", "max_records": max(1, min(limit, 200)), "querytext": query}
    )
    payload = _http_json(f"https://ieeexploreapi.ieee.org/api/v1/search/articles?{params}")
    sources: list[dict[str, Any]] = []
    for rank, item in enumerate(payload.get("articles", []), start=1):
        title = item.get("title", "")
        if not title:
            continue
        doi = _normalize_doi(item.get("doi", ""))
        url = item.get("html_url") or item.get("abstract_url") or (f"https://doi.org/{doi}" if doi else "")
        pdf_url = item.get("pdf_url", "")
        source = {
            "id": _stable_source_id("ieee", doi or item.get("article_number", "") or title),
            "title": title,
            "authors": [a.get("full_name", "") for a in _as_list((item.get("authors") or {}).get("authors")) if isinstance(a, dict)],
            "venue": item.get("publication_title", ""),
            "publisher": "IEEE",
            "year": int(item.get("publication_year") or 0),
            "date": item.get("publication_date", ""),
            "url": url,
            "pdf_url": pdf_url,
            "type": "academic",
            "credibility": 5,
            "verification": "unverified",
            "identifiers": {"doi": doi or None, "ieee_article_number": item.get("article_number")},
            "abstract": item.get("abstract", ""),
            "discovery_records": [_discovery("ieee", query, rank, url)],
        }
        _ensure_artifact_records(source, source["id"], project_root=None, network_check=False, download_pdfs=False)
        _ensure_parse_profile(source, source["id"], module="M1", project_root=None, parse_local_pdfs=False)
        sources.append(source)
    return sources


def _search_elsevier(query: str, limit: int) -> list[dict[str, Any]]:
    api_key = os.environ.get("ELSEVIER_API_KEY") or os.environ.get("SCOPUS_API_KEY")
    if not api_key:
        raise CredentialRequired("Elsevier/Scopus connector requires ELSEVIER_API_KEY or SCOPUS_API_KEY")
    params = urllib.parse.urlencode({"query": query, "count": max(1, min(limit, 25)), "apiKey": api_key})
    payload = _http_json(f"https://api.elsevier.com/content/search/scopus?{params}")
    entries = payload.get("search-results", {}).get("entry", [])
    sources: list[dict[str, Any]] = []
    for rank, item in enumerate(entries, start=1):
        title = item.get("dc:title", "")
        if not title:
            continue
        doi = _normalize_doi(item.get("prism:doi", ""))
        url = next((link.get("@href") for link in _as_list(item.get("link")) if isinstance(link, dict) and link.get("@href")), "")
        source = {
            "id": _stable_source_id("elsevier", doi or item.get("dc:identifier", "") or title),
            "title": title,
            "authors": [item.get("dc:creator", "")] if item.get("dc:creator") else [],
            "venue": item.get("prism:publicationName", ""),
            "publisher": "Elsevier",
            "year": int(str(item.get("prism:coverDate", "0"))[:4] or 0),
            "date": item.get("prism:coverDate", ""),
            "url": url or (f"https://doi.org/{doi}" if doi else ""),
            "type": "academic",
            "credibility": 5,
            "verification": "unverified",
            "identifiers": {"doi": doi or None, "scopus_id": item.get("dc:identifier")},
            "discovery_records": [_discovery("elsevier", query, rank, url)],
        }
        _ensure_artifact_records(source, source["id"], project_root=None, network_check=False, download_pdfs=False)
        _ensure_parse_profile(source, source["id"], module="M1", project_root=None, parse_local_pdfs=False)
        sources.append(source)
    return sources


def _search_springer(query: str, limit: int) -> list[dict[str, Any]]:
    api_key = os.environ.get("SPRINGER_API_KEY")
    if not api_key:
        raise CredentialRequired("Springer connector requires SPRINGER_API_KEY")
    params = urllib.parse.urlencode({"q": query, "p": max(1, min(limit, 100)), "api_key": api_key})
    payload = _http_json(f"https://api.springernature.com/meta/v2/json?{params}")
    return [_source_from_springer(item, query, rank) for rank, item in enumerate(payload.get("records", []), start=1) if item.get("title")]


def _source_from_springer(item: dict[str, Any], query: str, rank: int) -> dict[str, Any]:
    doi = _normalize_doi(item.get("doi", ""))
    url = next((u.get("value") for u in _as_list(item.get("url")) if isinstance(u, dict) and u.get("value")), "")
    source = {
        "id": _stable_source_id("springer", doi or url or item.get("title", "")),
        "title": item.get("title", ""),
        "authors": [a.get("creator", "") for a in _as_list(item.get("creators")) if isinstance(a, dict)],
        "venue": item.get("publicationName", ""),
        "publisher": "Springer Nature",
        "year": int(str(item.get("publicationDate", "0"))[:4] or 0),
        "date": item.get("publicationDate", ""),
        "url": url or (f"https://doi.org/{doi}" if doi else ""),
        "type": "academic",
        "credibility": 4,
        "verification": "unverified",
        "identifiers": {"doi": doi or None},
        "abstract": item.get("abstract", ""),
        "discovery_records": [_discovery("springer", query, rank, url)],
    }
    _ensure_artifact_records(source, source["id"], project_root=None, network_check=False, download_pdfs=False)
    _ensure_parse_profile(source, source["id"], module="M1", project_root=None, parse_local_pdfs=False)
    return source


def _search_core(query: str, limit: int) -> list[dict[str, Any]]:
    api_key = os.environ.get("CORE_API_KEY")
    if not api_key:
        raise CredentialRequired("CORE connector requires CORE_API_KEY")
    req = urllib.request.Request(
        "https://api.core.ac.uk/v3/search/works",
        data=json.dumps({"q": query, "limit": max(1, min(limit, 100))}).encode("utf-8"),
        headers={"User-Agent": USER_AGENT, "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    sources: list[dict[str, Any]] = []
    for rank, item in enumerate(payload.get("results", []), start=1):
        title = item.get("title", "")
        if not title:
            continue
        doi = _normalize_doi(item.get("doi", ""))
        pdf_url = item.get("downloadUrl") or ""
        source = {
            "id": _stable_source_id("core", doi or item.get("id", "") or title),
            "title": title,
            "authors": [a.get("name", "") for a in _as_list(item.get("authors")) if isinstance(a, dict) and a.get("name")],
            "venue": item.get("publisher", ""),
            "publisher": item.get("publisher", ""),
            "year": int(item.get("yearPublished") or 0),
            "date": str(item.get("yearPublished") or ""),
            "url": item.get("sourceFulltextUrls", [""])[0] if item.get("sourceFulltextUrls") else item.get("urls", [""])[0] if item.get("urls") else "",
            "pdf_url": pdf_url,
            "type": "academic",
            "credibility": 4,
            "verification": "unverified",
            "identifiers": {"doi": doi or None, "core_id": item.get("id")},
            "abstract": item.get("abstract", ""),
            "discovery_records": [_discovery("core", query, rank, pdf_url)],
        }
        _ensure_artifact_records(source, source["id"], project_root=None, network_check=False, download_pdfs=False)
        _ensure_parse_profile(source, source["id"], module="M1", project_root=None, parse_local_pdfs=False)
        sources.append(source)
    return sources


def _search_wos(query: str, limit: int) -> list[dict[str, Any]]:
    api_key = os.environ.get("WOS_API_KEY") or os.environ.get("WEB_OF_SCIENCE_API_KEY")
    if not api_key:
        raise CredentialRequired("Web of Science connector requires WOS_API_KEY or WEB_OF_SCIENCE_API_KEY")
    base_url = os.environ.get("WOS_SEARCH_ENDPOINT") or "https://api.clarivate.com/apis/wos-starter/v1/documents"
    params = urllib.parse.urlencode(
        {
            "q": f"TS=({_wos_escape_query(query)})",
            "db": os.environ.get("WOS_DATABASE", "WOS"),
            "limit": max(1, min(limit, 50)),
            "page": 1,
        }
    )
    payload = _http_json(f"{base_url}?{params}", headers={"X-ApiKey": api_key})
    hits = _as_list(payload.get("hits") or payload.get("data") or payload.get("documents"))
    sources: list[dict[str, Any]] = []
    for rank, item in enumerate(hits, start=1):
        if not isinstance(item, dict):
            continue
        source = _source_from_wos(item, query, rank)
        if source:
            sources.append(source)
    return sources


def _search_acm(query: str, limit: int) -> list[dict[str, Any]]:
    endpoint = os.environ.get("ACM_SEARCH_ENDPOINT")
    if endpoint:
        return _search_configured_json_endpoint(
            "acm",
            endpoint,
            query,
            limit,
            publisher="ACM",
            api_key_envs=("ACM_API_KEY",),
            default_header="Authorization",
        )
    # ACM does not expose a stable public search API comparable to Crossref.
    # Crossref carries ACM DOI metadata and publisher-deposited full-text/TDM
    # links, so this path gives a runnable default without bypassing access
    # control on dl.acm.org.
    return _search_crossref_filtered(
        query,
        limit,
        surface="acm_crossref_tdm",
        filters=("prefix:10.1145",),
        publisher_override="ACM",
    )


def _search_wiley(query: str, limit: int) -> list[dict[str, Any]]:
    endpoint = os.environ.get("WILEY_SEARCH_ENDPOINT")
    if endpoint:
        return _search_configured_json_endpoint(
            "wiley",
            endpoint,
            query,
            limit,
            publisher="Wiley",
            api_key_envs=("WILEY_TDM_TOKEN", "WILEY_API_KEY"),
            default_header=os.environ.get("WILEY_TDM_AUTH_HEADER", "Wiley-TDM-Client-Token"),
        )
    sources: list[dict[str, Any]] = []
    for prefix in ("10.1002", "10.1111"):
        try:
            sources.extend(
                _search_crossref_filtered(
                    query,
                    max(1, limit),
                    surface="wiley_crossref_tdm",
                    filters=(f"prefix:{prefix}",),
                    publisher_override="Wiley",
                )
            )
        except Exception:
            continue
    return _dedupe_sources(sources)[:limit]


def _source_from_wos(item: dict[str, Any], query: str, rank: int) -> dict[str, Any]:
    source_data = item.get("source") if isinstance(item.get("source"), dict) else {}
    identifiers = item.get("identifiers") if isinstance(item.get("identifiers"), dict) else {}
    names = item.get("names") if isinstance(item.get("names"), dict) else {}
    links = item.get("links") if isinstance(item.get("links"), dict) else {}
    doi = _normalize_doi(_first_present(identifiers, ("doi", "DOI")))
    title = str(item.get("title") or item.get("documentTitle") or "").strip()
    if not title:
        return {}
    authors = [
        _author_display_name(author)
        for author in _as_list(names.get("authors"))
        if isinstance(author, dict)
    ]
    authors = [author for author in authors if author]
    url = links.get("record") or links.get("url") or (f"https://doi.org/{doi}" if doi else "")
    citations = 0
    for citation in _as_list(item.get("citations")):
        if isinstance(citation, dict):
            citations += int(citation.get("count") or 0)
    source = {
        "id": _stable_source_id("wos", doi or item.get("uid", "") or title),
        "title": title,
        "authors": authors,
        "venue": _first_present(source_data, ("sourceTitle", "source_title", "title")),
        "publisher": "Web of Science indexed",
        "year": int(source_data.get("publishYear") or source_data.get("publish_year") or 0),
        "date": str(source_data.get("publishDate") or source_data.get("publish_year") or source_data.get("publishYear") or ""),
        "url": url,
        "type": "academic",
        "credibility": 5,
        "verification": "unverified",
        "identifiers": {"doi": doi or None, "wos_uid": item.get("uid")},
        "citation_count": citations,
        "abstract": item.get("abstract", ""),
        "discovery_records": [_discovery("wos", query, rank, url)],
    }
    _ensure_artifact_records(source, source["id"], project_root=None, network_check=False, download_pdfs=False)
    _ensure_parse_profile(source, source["id"], module="M1", project_root=None, parse_local_pdfs=False)
    return source


def _wos_escape_query(query: str) -> str:
    text = re.sub(r"[()=]", " ", str(query or ""))
    terms = [term for term in re.findall(r"[A-Za-z0-9_-]+", text) if len(term) > 1]
    return " ".join(terms[:16]) or query


def _first_present(data: dict[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = data.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def _author_display_name(author: dict[str, Any]) -> str:
    for key in ("display_name", "displayName", "full_name", "fullName", "name"):
        if author.get(key):
            return str(author[key])
    parts = [
        str(author.get("firstName") or author.get("given") or "").strip(),
        str(author.get("lastName") or author.get("family") or "").strip(),
    ]
    return " ".join(part for part in parts if part)


def _configured_authors(item: dict[str, Any]) -> list[str]:
    authors = item.get("authors") or item.get("author") or []
    if isinstance(authors, str):
        return [authors]
    result: list[str] = []
    for author in _as_list(authors):
        if isinstance(author, dict):
            name = _author_display_name(author)
        else:
            name = str(author or "")
        if name:
            result.append(name)
    return result


def _configured_artifacts(item: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for key in ("pdf_url", "pdfUrl", "downloadUrl", "fullTextPdf"):
        if item.get(key):
            artifacts.append(_artifact("pdf", str(item[key]), notes=f"{key} from configured endpoint"))
    for key in ("html_url", "htmlUrl", "fullTextHtml"):
        if item.get(key):
            artifacts.append(_artifact("html", str(item[key]), notes=f"{key} from configured endpoint"))
    for key in ("xml_url", "xmlUrl", "fullTextXml"):
        if item.get(key):
            artifacts.append(_artifact("xml", str(item[key]), notes=f"{key} from configured endpoint"))
    return artifacts


def _crossref_link_artifacts(item: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for link in _as_list(item.get("link")):
        if not isinstance(link, dict):
            continue
        url = link.get("URL") or link.get("url") or ""
        if not _is_http_url(url):
            continue
        content_type = str(link.get("content-type") or "").lower()
        intended = str(link.get("intended-application") or "").lower()
        version = str(link.get("content-version") or "").lower()
        artifact_type = "html"
        if "pdf" in content_type or re.search(r"/doi/pdf/|\.pdf(\?|$)", url, flags=re.I):
            artifact_type = "pdf"
        elif "xml" in content_type or "jats" in content_type or "nlm" in content_type:
            artifact_type = "xml"
        notes = "Crossref publisher full-text link"
        if intended:
            notes += f"; intended={intended}"
        if version:
            notes += f"; version={version}"
        artifact = _artifact(artifact_type, url, notes=notes)
        if "wiley.com/onlinelibrary/tdm/" in url:
            artifact["auth_env"] = "WILEY_TDM_TOKEN"
            artifact["auth_header"] = os.environ.get("WILEY_TDM_AUTH_HEADER", "Wiley-TDM-Client-Token")
            artifact["recovery_actions"] = [
                "provide WILEY_TDM_TOKEN from Wiley TDM access",
                "ensure the request runs from an entitled institutional IP",
            ]
        artifacts.append(artifact)
    return artifacts


def _search_configured_json_endpoint(
    surface: str,
    endpoint: str,
    query: str,
    limit: int,
    *,
    publisher: str,
    api_key_envs: tuple[str, ...],
    default_header: str,
) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"q": query, "query": query, "limit": max(1, min(limit, 100))})
    separator = "&" if "?" in endpoint else "?"
    headers: dict[str, str] = {}
    api_key = next((os.environ.get(env) for env in api_key_envs if os.environ.get(env)), "")
    if api_key:
        header_name = os.environ.get(f"{surface.upper()}_API_KEY_HEADER") or default_header
        scheme = os.environ.get(f"{surface.upper()}_API_KEY_SCHEME", "Bearer")
        headers[header_name] = api_key if not scheme else f"{scheme} {api_key}"
    payload = _http_json(f"{endpoint}{separator}{params}", headers=headers or None)
    items = _as_list(payload.get("items") or payload.get("results") or payload.get("data") or payload.get("records"))
    sources: list[dict[str, Any]] = []
    for rank, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        if not title:
            continue
        doi = _normalize_doi(item.get("doi") or item.get("DOI") or "")
        url = item.get("url") or item.get("URL") or item.get("link") or (f"https://doi.org/{doi}" if doi else "")
        source = {
            "id": _stable_source_id(surface, doi or url or title),
            "title": title,
            "authors": _configured_authors(item),
            "venue": item.get("venue") or item.get("publicationName") or item.get("containerTitle") or "",
            "publisher": publisher,
            "year": int(str(item.get("year") or item.get("publicationYear") or item.get("published") or 0)[:4] or 0),
            "date": str(item.get("date") or item.get("publicationDate") or item.get("published") or ""),
            "url": url,
            "type": "academic",
            "credibility": 4,
            "verification": "unverified",
            "identifiers": {"doi": doi or None},
            "abstract": item.get("abstract", ""),
            "discovery_records": [_discovery(surface, query, rank, url)],
        }
        source["artifacts"] = _configured_artifacts(item)
        _ensure_artifact_records(source, source["id"], project_root=None, network_check=False, download_pdfs=False)
        _ensure_parse_profile(source, source["id"], module="M1", project_root=None, parse_local_pdfs=False)
        sources.append(source)
    return sources


def _ensure_discovery_record(
    src: dict[str, Any],
    source_id: str,
    provenance: dict[str, Any],
) -> bool:
    if _as_list(src.get("discovery_records") or src.get("discovery")):
        return False
    records: list[dict[str, Any]] = []
    if src.get("discovery_source") or src.get("discovery_query"):
        records.append(
            _discovery(
                src.get("discovery_source") or "legacy_source_log",
                src.get("discovery_query") or src.get("title", ""),
                int(src.get("result_rank") or 0),
                src.get("url", ""),
                reason=src.get("relevance_to_our_gap", ""),
            )
        )
    elif isinstance(provenance, dict):
        for round_data in _as_list(provenance.get("rounds") or provenance.get("search_rounds")):
            if not isinstance(round_data, dict):
                continue
            retained = {
                str(item)
                for item in _as_list(
                    round_data.get("retained_source_ids")
                    or round_data.get("source_ids")
                    or round_data.get("retained_sources")
                )
            }
            if source_id in retained:
                records.append(
                    _discovery(
                        ",".join(str(x) for x in _as_list(provenance.get("databases"))),
                        " | ".join(str(q) for q in _as_list(round_data.get("queries"))),
                        0,
                        src.get("url", ""),
                        reason=str(round_data.get("goal") or round_data.get("purpose") or ""),
                    )
                )
    if not records:
        records.append(
            _discovery(
                "manual_or_unknown",
                src.get("title", ""),
                0,
                src.get("url", ""),
                reason="Inserted by literature_ingestion prepare-source-log; needs human search audit.",
            )
        )
    src["discovery_records"] = records
    return True


def _ensure_artifact_records(
    src: dict[str, Any],
    source_id: str,
    *,
    project_root: Path | None,
    network_check: bool,
    download_pdfs: bool,
    fetch_fulltext: bool = False,
    skip_unpaywall: bool = False,
    skip_crossref_fulltext: bool = False,
    browser_downloads: bool = False,
    browser_session_state: str | Path | None = None,
    report: LiteratureIngestionReport | None = None,
) -> int:
    artifacts = _as_list(src.get("artifacts"))
    before = len(artifacts)
    if fetch_fulltext:
        for artifact in _discover_fulltext_artifacts(
            src,
            source_id,
            report,
            skip_unpaywall=skip_unpaywall,
            skip_crossref_fulltext=skip_crossref_fulltext,
        ):
            if not _has_artifact(artifacts, artifact.get("artifact_type", ""), artifact.get("uri", "")):
                artifacts.append(artifact)
                if report:
                    report.fulltext_artifacts_added += 1
    pdf_url = src.get("pdf_url") or _derive_pdf_url(src.get("url", ""))
    if pdf_url and not _has_artifact(artifacts, "pdf", pdf_url):
        artifacts.append(
            {
                "artifact_type": "pdf",
                "uri": pdf_url,
                "local_path": src.get("pdf_path", ""),
                "status": "available" if src.get("pdf_path") else "unknown",
                "recovery_actions": [],
            }
        )
        src["pdf_url"] = pdf_url
    if src.get("pdf_path") and not any(a.get("local_path") == src.get("pdf_path") for a in artifacts if isinstance(a, dict)):
        artifacts.append(
            {
                "artifact_type": "pdf",
                "uri": pdf_url,
                "local_path": src.get("pdf_path"),
                "status": "available",
                "recovery_actions": [],
            }
        )
    if not artifacts:
        url = src.get("url", "")
        if url:
            artifacts.append(
                {
                    "artifact_type": "html" if not url.lower().endswith(".pdf") else "pdf",
                    "uri": url,
                    "local_path": "",
                    "status": "unknown",
                    "recovery_actions": ["check publisher page", "fallback to metadata/abstract-only parse"],
                }
            )
        else:
            artifacts.append(
                {
                    "artifact_type": "abstract",
                    "uri": f"metadata:{source_id}",
                    "local_path": "",
                    "status": "available",
                    "notes": "No URL/PDF recorded; metadata-only fallback.",
                    "recovery_actions": ["search DOI/arXiv/Semantic Scholar/OpenAlex by title"],
                }
            )
    artifacts = sorted(artifacts, key=_artifact_priority)
    pdf_download_attempts = 0
    html_download_attempts = 0
    xml_download_attempts = 0
    fulltext_available = any(
        isinstance(artifact, dict)
        and artifact.get("artifact_type") in {"pdf", "html", "xml"}
        and artifact.get("local_path")
        for artifact in artifacts
    )
    browser_state_path = _resolve_browser_session_state(browser_session_state)
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        artifact.setdefault("artifact_type", "pdf")
        artifact.setdefault("uri", "")
        artifact.setdefault("local_path", "")
        artifact.setdefault("status", "unknown")
        artifact.setdefault("recovery_actions", [])
        artifact.setdefault("failure_reason", "")
        artifact.setdefault("notes", "")
        _fill_artifact_hash(artifact, project_root)
        if (
            network_check
            and artifact.get("uri")
            and artifact["artifact_type"] in {"pdf", "html", "xml"}
            and _is_http_url(artifact.get("uri", ""))
        ):
            _check_artifact_uri(artifact, report)
        if (
            download_pdfs
            and artifact.get("artifact_type") == "pdf"
            and artifact.get("uri")
            and _is_http_url(artifact.get("uri", ""))
        ):
            if fulltext_available and not artifact.get("local_path"):
                _defer_artifact_attempt(artifact, "A full-text artifact is already available for this source")
            elif browser_downloads and _should_browser_download(artifact):
                _download_artifact_with_browser(
                    artifact,
                    source_id,
                    project_root,
                    browser_state_path,
                    report,
                )
                fulltext_available = fulltext_available or bool(artifact.get("local_path"))
                if artifact.get("local_path"):
                    continue
            elif _artifact_auth_envs(artifact) and not _artifact_credentials_available(artifact):
                _mark_credential_blocked(artifact, report)
            elif not _should_bulk_download_pdf(artifact):
                _defer_artifact_attempt(artifact, "PDF URI is a credential-gated publisher full-text link; not bulk-downloaded")
            elif pdf_download_attempts < MAX_PDF_DOWNLOAD_ATTEMPTS_PER_SOURCE:
                pdf_download_attempts += 1
                _download_pdf_artifact(artifact, source_id, project_root, report)
                fulltext_available = fulltext_available or bool(artifact.get("local_path"))
            else:
                _defer_artifact_attempt(artifact, "PDF download attempt cap reached for this source")
        if (
            fetch_fulltext
            and artifact.get("artifact_type") == "html"
            and artifact.get("uri")
            and _is_http_url(artifact.get("uri", ""))
        ):
            if fulltext_available and not artifact.get("local_path"):
                _defer_artifact_attempt(artifact, "A full-text artifact is already available for this source")
            elif browser_downloads and _should_browser_download(artifact):
                _download_artifact_with_browser(
                    artifact,
                    source_id,
                    project_root,
                    browser_state_path,
                    report,
                )
                fulltext_available = fulltext_available or bool(artifact.get("local_path"))
                if artifact.get("local_path"):
                    continue
            elif not _should_bulk_download_html(artifact):
                _defer_artifact_attempt(artifact, "HTML URI is a DOI or credential-gated publisher landing page; not bulk-downloaded")
            elif html_download_attempts < MAX_HTML_DOWNLOAD_ATTEMPTS_PER_SOURCE:
                html_download_attempts += 1
                _download_html_artifact(artifact, source_id, project_root, report)
                fulltext_available = fulltext_available or bool(artifact.get("local_path"))
            else:
                _defer_artifact_attempt(artifact, "HTML download attempt cap reached for this source")
        if (
            fetch_fulltext
            and artifact.get("artifact_type") == "xml"
            and artifact.get("uri")
            and _is_http_url(artifact.get("uri", ""))
        ):
            if fulltext_available and not artifact.get("local_path"):
                _defer_artifact_attempt(artifact, "A full-text artifact is already available for this source")
            elif browser_downloads and _should_browser_download(artifact):
                _download_artifact_with_browser(
                    artifact,
                    source_id,
                    project_root,
                    browser_state_path,
                    report,
                )
                fulltext_available = fulltext_available or bool(artifact.get("local_path"))
                if artifact.get("local_path"):
                    continue
            elif xml_download_attempts < MAX_HTML_DOWNLOAD_ATTEMPTS_PER_SOURCE:
                xml_download_attempts += 1
                _download_xml_artifact(artifact, source_id, project_root, report)
                fulltext_available = fulltext_available or bool(artifact.get("local_path"))
            else:
                _defer_artifact_attempt(artifact, "XML download attempt cap reached for this source")
        if artifact.get("status") in {"failed", "unavailable", "skipped"}:
            if not artifact.get("failure_reason"):
                artifact["failure_reason"] = "artifact acquisition did not produce a usable file"
            if not _as_list(artifact.get("recovery_actions")):
                artifact["recovery_actions"] = [
                    "retry DOI/Crossref/OpenAlex/Semantic Scholar metadata",
                    "use publisher HTML or abstract-only parse",
                ]
        elif artifact.get("status") in {"unknown", "pending"}:
            if not artifact.get("failure_reason"):
                artifact["failure_reason"] = "artifact availability not checked or not yet resolved"
            if not _as_list(artifact.get("recovery_actions")):
                artifact["recovery_actions"] = [
                    "run prepare-source-log with --network-check",
                    "try publisher HTML or open-access repository",
                    "fallback to metadata/abstract-only parse",
                ]
    src["artifacts"] = artifacts
    return max(0, len(artifacts) - before)


def _ensure_parse_profile(
    src: dict[str, Any],
    source_id: str,
    *,
    module: str,
    project_root: Path | None,
    parse_local_pdfs: bool,
    parse_local_fulltext: bool = False,
    report: LiteratureIngestionReport | None = None,
) -> bool:
    existing = src.get("parse_profile") if isinstance(src.get("parse_profile"), dict) else {}
    section_summaries = dict(existing.get("section_summaries") or {})
    if not section_summaries:
        section_summaries = _section_summaries_from_source(src)

    parsed_text = ""
    parse_errors = _as_list(existing.get("parse_errors"))
    parse_backend = existing.get("parse_backend") or "source_log_card"
    fulltext_status = existing.get("fulltext_status") or "metadata_only"
    parsed_fulltext = False
    if parse_local_pdfs:
        pdf_path = _first_local_pdf(src, project_root)
        if pdf_path:
            if report:
                report.pdf_parse_attempted += 1
            text, parse_error, backend = _extract_pdf_text(pdf_path)
            if text:
                parsed_text = text
                section_summaries.update(_sections_from_text(text))
                parse_backend = backend
                fulltext_status = "parsed_fulltext"
                parsed_fulltext = True
                _mark_local_artifact_parse(src, pdf_path, project_root, "parsed", backend=backend)
                if report:
                    report.pdf_parsed += 1
            else:
                fulltext_status = "parse_failed"
                _mark_local_artifact_parse(src, pdf_path, project_root, "failed", parse_error=parse_error)
                if parse_error:
                    parse_errors.append(parse_error)
                if report:
                    report.warnings.append(f"{source_id}: PDF parse failed: {parse_error}")
    if parse_local_fulltext and not parsed_fulltext:
        html_path = _first_local_html(src, project_root)
        if html_path:
            text, parse_error, backend = _extract_html_text(html_path)
            if text:
                parsed_text = text
                section_summaries.update(_sections_from_text(text))
                parse_backend = backend
                fulltext_status = "parsed_fulltext" if backend == "html_text" else "partial_fulltext"
                parsed_fulltext = backend == "html_text"
                _mark_local_artifact_parse(
                    src,
                    html_path,
                    project_root,
                    "parsed" if backend == "html_text" else "partial",
                    backend=backend,
                    parse_error=parse_error,
                )
                if parse_error:
                    parse_errors.append(parse_error)
                if report:
                    report.html_parsed += 1
            else:
                fulltext_status = "parse_failed"
                _mark_local_artifact_parse(src, html_path, project_root, "failed", parse_error=parse_error)
                if parse_error:
                    parse_errors.append(parse_error)
                if report:
                    report.warnings.append(f"{source_id}: HTML parse failed: {parse_error}")
    if parse_local_fulltext and not parsed_fulltext:
        xml_path = _first_local_xml(src, project_root)
        if xml_path:
            text, parse_error, backend = _extract_xml_text(xml_path)
            if text:
                parsed_text = text
                section_summaries.update(_sections_from_text(text))
                parse_backend = backend
                fulltext_status = "parsed_fulltext" if backend == "xml_text" else "partial_fulltext"
                parsed_fulltext = backend == "xml_text"
                _mark_local_artifact_parse(
                    src,
                    xml_path,
                    project_root,
                    "parsed" if backend == "xml_text" else "partial",
                    backend=backend,
                    parse_error=parse_error,
                )
                if parse_error:
                    parse_errors.append(parse_error)
                if report:
                    report.xml_parsed += 1
            else:
                fulltext_status = "parse_failed"
                _mark_local_artifact_parse(src, xml_path, project_root, "failed", parse_error=parse_error)
                if parse_error:
                    parse_errors.append(parse_error)
                if report:
                    report.warnings.append(f"{source_id}: XML parse failed: {parse_error}")

    missing_fields = _missing_parse_fields(section_summaries)
    if existing.get("missing_fields") is not None and not parsed_fulltext:
        missing_fields = _as_list(existing.get("missing_fields"))

    parse_status = existing.get("parse_status")
    if parsed_fulltext or not parse_status:
        if parsed_fulltext and not missing_fields:
            parse_status = "complete"
        elif section_summaries:
            parse_status = "partial"
        else:
            parse_status = "blocked"
    metadata_status = existing.get("metadata_status") or (
        "complete" if src.get("title") and src.get("authors") else "partial"
    )
    downstream_signals = existing.get("downstream_signals")
    if parsed_fulltext or not isinstance(downstream_signals, dict) or not downstream_signals:
        downstream_signals = _downstream_signals(src, section_summaries)

    extraction_sources = _as_list(existing.get("extraction_sources")) or ["source_log"]
    if parsed_text and parse_backend not in extraction_sources:
        extraction_sources.append(parse_backend)

    profile = {
        "metadata_status": metadata_status,
        "fulltext_status": fulltext_status,
        "parse_status": parse_status,
        "parse_backend": parse_backend,
        "extraction_sources": extraction_sources,
        "missing_fields": missing_fields,
        "section_summaries": section_summaries,
        "downstream_signals": downstream_signals,
        "confidence": "high" if parse_status == "complete" else existing.get("confidence") or "medium",
        "notes": existing.get("notes", ""),
    }
    if parse_errors:
        profile["parse_errors"] = parse_errors
        if not profile["notes"]:
            profile["notes"] = "; ".join(str(error) for error in parse_errors[:3])
    changed = not src.get("parse_profile")
    src["parse_profile"] = profile
    return changed


def _section_summaries_from_source(src: dict[str, Any]) -> dict[str, Any]:
    summaries = {
        key: value
        for key, value in {
            "abstract": src.get("abstract", ""),
            "background": src.get("background", ""),
            "contributions": src.get("contributions", []),
            "model": src.get("model", ""),
            "method": src.get("method") or src.get("method_summary", ""),
            "experiment_setup": src.get("experiment_setup", ""),
            "results": src.get("results") or src.get("key_results", []),
            "analysis": src.get("analysis", ""),
            "conclusion": src.get("conclusion", ""),
            "limitations": src.get("limitations_noted", []),
        }.items()
        if value not in ("", [], None)
    }
    abstract_sections = _sections_from_abstract(src.get("abstract", ""))
    for key, value in abstract_sections.items():
        summaries.setdefault(key, value)
    return summaries


def _sections_from_abstract(abstract: str) -> dict[str, str]:
    abstract = str(abstract or "")
    if not abstract:
        return {}
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", abstract)
        if sentence.strip()
    ]
    patterns = {
        "method": (
            "propose",
            "present",
            "design",
            "framework",
            "method",
            "model",
            "approach",
            "using",
            "via",
            "based",
        ),
        "experiment_setup": (
            "experiment",
            "validate",
            "evaluation",
            "dataset",
            "channel",
            "snr",
            "rate",
            "modulation",
            "transmission",
        ),
        "results": (
            "outperform",
            "superior",
            "improve",
            "demonstrate",
            "achieve",
            "performance",
            "result",
        ),
        "analysis": (
            "robust",
            "gap",
            "ablation",
            "analysis",
            "reduces",
            "trade-off",
            "tradeoff",
        ),
    }
    extracted: dict[str, str] = {}
    for section, keywords in patterns.items():
        matches = [
            sentence
            for sentence in sentences
            if any(keyword in sentence.lower() for keyword in keywords)
        ]
        if matches:
            extracted[section] = _clip(" ".join(matches[:3]), 1200)
    return extracted


def _downstream_signals(src: dict[str, Any], section_summaries: dict[str, Any]) -> dict[str, Any]:
    method = section_summaries.get("method", "")
    experiment = section_summaries.get("experiment_setup", "")
    analysis = section_summaries.get("analysis", "")
    results = section_summaries.get("results", "")
    writing_context = (
        section_summaries.get("conclusion")
        or section_summaries.get("abstract")
        or src.get("title", "")
    )
    return {
        "M2": {"method_reference": bool(method), "core_mechanism": method},
        "M3": {"experiment_protocol": bool(experiment), "datasets_metrics_baselines": experiment},
        "M4": {"analysis_patterns": bool(analysis or results), "analysis": analysis or results},
        "M5": {
            "citation_ready": bool(src.get("title") and src.get("authors")),
            "writing_context": writing_context,
        },
    }


def _missing_parse_fields(section_summaries: dict[str, Any]) -> list[str]:
    required = ("method", "experiment_setup", "results", "analysis")
    return [field for field in required if not section_summaries.get(field)]


def _sections_from_text(text: str) -> dict[str, str]:
    headings = {
        "abstract": ("abstract",),
        "background": ("introduction", "background", "related work"),
        "model": ("system model", "problem formulation", "channel model", "signal model"),
        "method": ("method", "methodology", "approach", "proposed", "framework", "algorithm", "model"),
        "experiment_setup": ("experiment", "experimental setup", "evaluation", "simulation setup", "implementation details"),
        "results": ("results", "findings", "performance evaluation", "simulation results"),
        "analysis": ("analysis", "discussion", "ablation", "robustness", "complexity"),
        "conclusion": ("conclusion",),
    }
    lines = text.splitlines()
    current = ""
    buckets: dict[str, list[str]] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lowered = _normalize_heading(stripped)
        matched = _match_heading(lowered, headings)
        if matched:
            current = matched
            buckets.setdefault(current, [])
            continue
        if current:
            buckets.setdefault(current, []).append(stripped)
    return {key: _clip(" ".join(value), 1200) for key, value in buckets.items() if value}


def _normalize_heading(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"^\s*(section\s+)?([ivxlcdm]+|\d+)([.\)]|\s)+", "", lowered)
    lowered = re.sub(r"^\d+(\.\d+)*\s+", "", lowered)
    lowered = re.sub(r"[^a-z0-9 /_-]+", " ", lowered)
    return " ".join(lowered.split())


def _match_heading(lowered: str, headings: dict[str, tuple[str, ...]]) -> str:
    if not lowered or len(lowered) > 90:
        return ""
    for name, variants in headings.items():
        if any(lowered == variant or lowered.startswith(variant + " ") for variant in variants):
            return name
    return ""


def _extract_pdf_text(path: Path) -> tuple[str, str, str]:
    binary = shutil.which("pdftotext")
    if binary:
        with tempfile.TemporaryDirectory() as tmp:
            txt_path = Path(tmp) / "paper.txt"
            proc = subprocess.run(
                [binary, "-enc", "UTF-8", str(path), str(txt_path)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if proc.returncode == 0:
                text = txt_path.read_text(encoding="utf-8", errors="replace")
                if text.strip():
                    return text, "", "pdftotext"
            cli_error = (proc.stderr or proc.stdout or f"pdftotext exited {proc.returncode}").strip()
    else:
        cli_error = "pdftotext is not installed"

    text, pdfminer_error, backend = _pdfminer_text(path)
    if text:
        return text, "", backend

    text, fitz_error, backend = _fitz_pdf_text(path)
    if text:
        return text, "", backend

    text, py_error, backend = _python_pdf_text(path)
    if text:
        return text, "", backend
    return "", f"{cli_error}; {pdfminer_error}; {fitz_error}; {py_error}", "source_log_card"


def _pdfminer_text(path: Path) -> tuple[str, str, str]:
    try:
        module = importlib.import_module("pdfminer.high_level")
        text = module.extract_text(str(path)) or ""
        if text.strip():
            return text, "", "pdfminer"
        return "", "pdfminer returned no extractable text", "source_log_card"
    except Exception as exc:
        return "", f"pdfminer failed: {exc}", "source_log_card"


def _fitz_pdf_text(path: Path) -> tuple[str, str, str]:
    try:
        fitz = importlib.import_module("fitz")
        doc = fitz.open(str(path))
        pages = []
        for idx in range(min(len(doc), 80)):
            page = doc.load_page(idx)
            pages.append(page.get_text("text") or "")
        text = "\n".join(pages).strip()
        if text:
            return text, "", "pymupdf"
        return "", "PyMuPDF returned no extractable text", "source_log_card"
    except Exception as exc:
        return "", f"PyMuPDF failed: {exc}", "source_log_card"


def _python_pdf_text(path: Path) -> tuple[str, str, str]:
    errors: list[str] = []
    for module_name in ("pypdf", "PyPDF2"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            errors.append(f"{module_name} is not installed")
            continue
        try:
            reader = module.PdfReader(str(path))
            pages = []
            for page in reader.pages[:80]:
                pages.append(page.extract_text() or "")
            text = "\n".join(pages).strip()
            if text:
                return text, "", module_name
            errors.append(f"{module_name} returned no extractable text")
        except Exception as exc:
            errors.append(f"{module_name} failed: {exc}")
    return "", "; ".join(errors), "source_log_card"


def _extract_html_text(path: Path) -> tuple[str, str, str]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        title = _html_title(raw)
        text = _html_to_text(raw)
        if len(text) >= MIN_FULLTEXT_CHARS:
            return f"{title}\n\n{text}" if title else text, "", "html_text"
        if text.strip():
            return text, "HTML text appears shorter than full-text threshold", "html_text_partial"
        return "", "HTML parser produced no text", "source_log_card"
    except Exception as exc:
        return "", f"HTML parse failed: {exc}", "source_log_card"


def _extract_xml_text(path: Path) -> tuple[str, str, str]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        if raw.lstrip().startswith("{"):
            payload = json.loads(raw)
            text = _json_text(payload)
        else:
            text = _xml_to_text(raw)
        if len(text) >= MIN_FULLTEXT_CHARS:
            return text, "", "xml_text"
        if text.strip():
            return text, "XML text appears shorter than full-text threshold", "xml_text_partial"
        return "", "XML parser produced no text", "source_log_card"
    except Exception as exc:
        return "", f"XML parse failed: {exc}", "source_log_card"


def _html_title(raw: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
    if not match:
        return ""
    return _clip(_clean_html_text(match.group(1)), 300)


def _html_to_text(raw: str) -> str:
    # Remove noisy blocks before stripping tags. This intentionally avoids a
    # heavy dependency while still making publisher/PMC/arXiv HTML usable.
    raw = re.sub(r"(?is)<(script|style|noscript|svg|math|form|nav|footer|header)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<(br|p|div|section|article|h[1-6]|li|tr|table|figcaption)[^>]*>", "\n", raw)
    raw = re.sub(r"(?is)<[^>]+>", " ", raw)
    return _clean_html_text(raw)


def _xml_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<!\[CDATA\[(.*?)\]\]>", r"\1", raw)
    raw = re.sub(r"(?is)<(title|article-title|section-title|sec-title|abstract|p|para|caption|fig|table-wrap|sec|body|h[1-6])[^>]*>", "\n", raw)
    raw = re.sub(r"(?is)</(title|article-title|section-title|sec-title|abstract|p|para|caption|fig|table-wrap|sec|body|h[1-6])>", "\n", raw)
    raw = re.sub(r"(?is)<(script|style|math|mml:math)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<[^>]+>", " ", raw)
    return _clean_html_text(raw)


def _json_text(value: Any) -> str:
    chunks: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if key.lower() in {"abstract", "title", "description", "text", "body", "section", "paragraph"}:
                    visit(child)
                elif isinstance(child, (dict, list)):
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
        elif isinstance(node, str):
            if len(node.split()) >= 4:
                chunks.append(node)

    visit(value)
    return _clean_html_text("\n".join(chunks))


def _clean_html_text(value: str) -> str:
    value = html_lib.unescape(value)
    lines = [" ".join(line.split()) for line in value.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _check_artifact_uri(artifact: dict[str, Any], report: LiteratureIngestionReport | None) -> None:
    if report:
        report.artifact_checked += 1
        if artifact.get("artifact_type") == "pdf":
            report.pdf_checked += 1
    uri = artifact["uri"]
    if not _artifact_credentials_available(artifact):
        _mark_credential_blocked(artifact, report)
        return
    try:
        req = urllib.request.Request(uri, method="HEAD", headers=_artifact_request_headers(artifact))
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            if 200 <= resp.status < 400:
                artifact["status"] = "available"
                artifact["failure_reason"] = ""
            else:
                artifact["status"] = "failed"
                artifact["failure_reason"] = f"HTTP {resp.status}"
    except Exception as exc:
        artifact["status"] = "failed"
        artifact["failure_reason"] = str(exc)
        artifact["recovery_actions"] = [
            "try publisher HTML",
            "query Crossref/OpenAlex/Semantic Scholar metadata",
            "fallback to abstract-only parse",
        ]


def _download_pdf_artifact(
    artifact: dict[str, Any],
    source_id: str,
    project_root: Path | None,
    report: LiteratureIngestionReport | None,
) -> None:
    if not project_root or not artifact.get("uri"):
        return
    if report:
        report.pdf_download_attempted += 1
    if not _artifact_credentials_available(artifact):
        _mark_credential_blocked(artifact, report)
        return
    pdf_dir = project_root / "literature" / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    target = pdf_dir / f"{_artifact_file_stem(source_id, artifact.get('uri', ''))}.pdf"
    try:
        data, headers, final_url = _fetch_limited(
            artifact["uri"],
            MAX_PDF_BYTES + 1,
            request_headers=_artifact_request_headers(artifact, accept=artifact.get("accept", "application/pdf,*/*")),
        )
        if len(data) > MAX_PDF_BYTES:
            raise ValueError("PDF exceeds 50 MB download cap")
        if not data.startswith(b"%PDF"):
            resolved = _extract_pdf_link(data, final_url, headers)
            if resolved and resolved != artifact["uri"]:
                landing_url = final_url
                data, headers, final_url = _fetch_limited(
                    resolved,
                    MAX_PDF_BYTES + 1,
                    request_headers=_artifact_request_headers(artifact, accept=artifact.get("accept", "application/pdf,*/*")),
                )
                artifact["uri"] = resolved
                artifact["notes"] = _append_note(
                    artifact.get("notes", ""),
                    f"Resolved PDF link from landing page {landing_url}",
                )
        if len(data) > MAX_PDF_BYTES:
            raise ValueError("PDF exceeds 50 MB download cap")
        if not data.startswith(b"%PDF"):
            raise ValueError("downloaded file does not have a PDF header")
        target.write_bytes(data)
        artifact["local_path"] = str(target.relative_to(project_root))
        artifact["status"] = "available"
        artifact["sha256"] = hashlib.sha256(data).hexdigest()
        artifact["failure_reason"] = ""
        if report:
            report.pdf_downloaded += 1
    except Exception as exc:
        artifact["status"] = "failed"
        artifact["failure_reason"] = str(exc)
        artifact["recovery_actions"] = [
            "retry download later",
            "try publisher HTML",
            "fallback to abstract-only parse",
        ]


def _download_html_artifact(
    artifact: dict[str, Any],
    source_id: str,
    project_root: Path | None,
    report: LiteratureIngestionReport | None,
) -> None:
    if not project_root or not artifact.get("uri") or not _is_http_url(artifact.get("uri", "")):
        return
    if artifact.get("local_path"):
        return
    if report:
        report.html_download_attempted += 1
    html_dir = project_root / "literature" / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    try:
        data, headers, final_url = _fetch_limited(
            artifact["uri"],
            8 * 1024 * 1024,
            request_headers=_artifact_request_headers(artifact, accept=artifact.get("accept", "text/html,*/*")),
        )
        content_type = headers.get("content-type", "").lower()
        if data.startswith(b"%PDF"):
            pdf_dir = project_root / "literature" / "pdfs"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            target = pdf_dir / f"{_artifact_file_stem(source_id, artifact.get('uri', ''))}_html_redirect.pdf"
            target.write_bytes(data)
            artifact["artifact_type"] = "pdf"
            artifact["local_path"] = str(target.relative_to(project_root))
            artifact["status"] = "available"
            artifact["sha256"] = hashlib.sha256(data).hexdigest()
            artifact["failure_reason"] = ""
            artifact["notes"] = _append_note(artifact.get("notes", ""), f"HTML URI redirected to PDF {final_url}")
            if report:
                report.pdf_downloaded += 1
            return
        if "html" not in content_type and b"<html" not in data[:5000].lower():
            raise ValueError(f"HTML artifact returned unsupported content-type '{content_type}'")
        target = html_dir / f"{_artifact_file_stem(source_id, artifact.get('uri', ''))}.html"
        target.write_bytes(data)
        artifact["local_path"] = str(target.relative_to(project_root))
        artifact["status"] = "available"
        artifact["sha256"] = hashlib.sha256(data).hexdigest()
        artifact["failure_reason"] = ""
        if report:
            report.html_downloaded += 1
    except Exception as exc:
        artifact["status"] = "failed"
        artifact["failure_reason"] = str(exc)
        artifact["recovery_actions"] = [
            "retry publisher HTML later",
            "try open-access repository PDF via Unpaywall/OpenAlex",
            "request institutional/API access for publisher full text",
        ]


def _download_xml_artifact(
    artifact: dict[str, Any],
    source_id: str,
    project_root: Path | None,
    report: LiteratureIngestionReport | None,
) -> None:
    if not project_root or not artifact.get("uri") or not _is_http_url(artifact.get("uri", "")):
        return
    if artifact.get("local_path"):
        return
    if report:
        report.xml_download_attempted += 1
    if not _artifact_credentials_available(artifact):
        _mark_credential_blocked(artifact, report)
        return
    xml_dir = project_root / "literature" / "xml"
    xml_dir.mkdir(parents=True, exist_ok=True)
    try:
        data, headers, final_url = _fetch_limited(
            artifact["uri"],
            16 * 1024 * 1024,
            request_headers=_artifact_request_headers(
                artifact,
                accept=artifact.get("accept", "application/xml,text/xml,application/json,*/*"),
            ),
        )
        if data.startswith(b"%PDF"):
            pdf_dir = project_root / "literature" / "pdfs"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            target = pdf_dir / f"{_artifact_file_stem(source_id, artifact.get('uri', ''))}_xml_redirect.pdf"
            target.write_bytes(data)
            artifact["artifact_type"] = "pdf"
            artifact["local_path"] = str(target.relative_to(project_root))
            artifact["status"] = "available"
            artifact["sha256"] = hashlib.sha256(data).hexdigest()
            artifact["failure_reason"] = ""
            artifact["notes"] = _append_note(artifact.get("notes", ""), f"XML URI returned PDF {final_url}")
            if report:
                report.pdf_downloaded += 1
            return
        content_type = headers.get("content-type", "").lower()
        sample = data[:5000].lower()
        if not any(token in content_type for token in ("xml", "json", "text")) and b"<" not in sample:
            raise ValueError(f"XML artifact returned unsupported content-type '{content_type}'")
        target = xml_dir / f"{_artifact_file_stem(source_id, artifact.get('uri', ''))}.xml"
        target.write_bytes(data)
        artifact["local_path"] = str(target.relative_to(project_root))
        artifact["status"] = "available"
        artifact["sha256"] = hashlib.sha256(data).hexdigest()
        artifact["failure_reason"] = ""
        if report:
            report.xml_downloaded += 1
    except Exception as exc:
        artifact["status"] = "failed"
        artifact["failure_reason"] = str(exc)
        artifact["recovery_actions"] = [
            "retry publisher XML/API full text later",
            "try open-access repository PDF/HTML via Unpaywall/OpenAlex",
            "request institutional/API access for publisher full text",
        ]


def _download_artifact_with_browser(
    artifact: dict[str, Any],
    source_id: str,
    project_root: Path | None,
    browser_session_state: Path | None,
    report: LiteratureIngestionReport | None,
) -> None:
    if artifact.get("local_path") or artifact.get("status") == "available":
        return
    if report:
        report.browser_download_attempted += 1
    if not project_root:
        _mark_browser_download_pending(
            artifact,
            "Browser-session download requires --project-root so acquired files can be stored.",
            report,
        )
        return
    if not browser_session_state or not browser_session_state.exists():
        _mark_browser_download_pending(
            artifact,
            "Browser session state is not configured or does not exist.",
            report,
        )
        return
    try:
        data, resolved_type, final_url = _fetch_with_browser_session(
            str(artifact["uri"]),
            browser_session_state,
            expected_type=str(artifact.get("artifact_type") or "pdf"),
        )
        artifact_type = resolved_type or str(artifact.get("artifact_type") or "pdf")
        if artifact_type == "pdf":
            if len(data) > MAX_PDF_BYTES:
                raise ValueError("browser-downloaded PDF exceeds 50 MB download cap")
            if not data.startswith(b"%PDF"):
                raise ValueError("browser-downloaded file does not have a PDF header")
            target_dir = project_root / "literature" / "pdfs"
            suffix = ".pdf"
            report_field = "pdf"
        elif artifact_type == "html":
            if len(data) > 8 * 1024 * 1024:
                raise ValueError("browser-downloaded HTML exceeds 8 MB download cap")
            if b"<html" not in data[:5000].lower() and b"<!doctype html" not in data[:5000].lower():
                raise ValueError("browser-downloaded file does not look like HTML")
            if _looks_like_access_blocked_html(data):
                raise ValueError("browser-downloaded HTML appears to be a login or access-denied page")
            if not _looks_like_fulltext_html(data):
                raise ValueError("browser-downloaded HTML does not appear to contain complete full-text HTML")
            target_dir = project_root / "literature" / "html"
            suffix = ".html"
            report_field = "html"
        elif artifact_type == "xml":
            if len(data) > 16 * 1024 * 1024:
                raise ValueError("browser-downloaded XML exceeds 16 MB download cap")
            sample = data[:5000].lstrip().lower()
            if not (sample.startswith(b"<") or sample.startswith(b"{")):
                raise ValueError("browser-downloaded file does not look like XML/JSON")
            if _looks_like_access_blocked_html(data):
                raise ValueError("browser-downloaded XML appears to be a login or access-denied page")
            target_dir = project_root / "literature" / "xml"
            suffix = ".xml"
            report_field = "xml"
        else:
            raise ValueError(f"unsupported browser-downloaded artifact type '{artifact_type}'")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{_artifact_file_stem(source_id, artifact.get('uri', ''))}_browser{suffix}"
        target.write_bytes(data)
        artifact["artifact_type"] = artifact_type
        artifact["local_path"] = str(target.relative_to(project_root))
        artifact["status"] = "available"
        artifact["sha256"] = hashlib.sha256(data).hexdigest()
        artifact["failure_reason"] = ""
        artifact["notes"] = _append_note(
            artifact.get("notes", ""),
            f"Downloaded with authorized browser session from {final_url or artifact.get('uri', '')}",
        )
        if report:
            report.browser_downloaded += 1
            if report_field == "xml":
                report.browser_xml_downloaded += 1
    except Exception as exc:
        artifact["status"] = "failed"
        artifact["failure_reason"] = f"browser session download failed: {exc}"
        artifact["recovery_actions"] = [
            "refresh the browser session with literature_ingestion.py browser-auth",
            "verify institutional access in the same network/browser session",
            "retry open-access routes via Unpaywall/OpenAlex/Semantic Scholar",
            "use a manually exported licensed PDF/HTML if available",
        ]
        if report:
            report.browser_download_failed += 1


def _fetch_with_browser_session(
    url: str,
    browser_session_state: Path,
    *,
    expected_type: str = "pdf",
) -> tuple[bytes, str, str]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RuntimeError(
            "Playwright is required for browser-session downloads; install with "
            "`pip install playwright` and `playwright install chromium`"
        ) from exc

    if expected_type not in {"pdf", "html", "xml"}:
        expected_type = "pdf"
    if expected_type == "xml":
        accept = "application/xml,text/xml,application/json,text/html,*/*"
    elif expected_type == "html":
        accept = "text/html,*/*"
    else:
        accept = "application/pdf,text/html,*/*"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                storage_state=str(browser_session_state),
                accept_downloads=True,
                user_agent=USER_AGENT,
            )
            try:
                response = context.request.get(
                    url,
                    headers={"Accept": accept, "User-Agent": USER_AGENT},
                    timeout=DOWNLOAD_TIMEOUT_SECONDS * 1000,
                )
            except Exception as exc:
                if "timeout" in str(exc).lower():
                    return _fetch_with_browser_page(context, url, expected_type=expected_type)
                raise
            if not response.ok:
                if response.status in {401, 403, 429}:
                    return _fetch_with_browser_page(context, url, expected_type=expected_type)
                raise RuntimeError(f"HTTP {response.status} from browser request")
            data = response.body()
            final_url = response.url
            content_type = str(response.headers.get("content-type", "")).lower()
            if data.startswith(b"%PDF"):
                return data, "pdf", final_url
            if expected_type == "xml" and _looks_like_xml_or_json(data, content_type):
                return data, "xml", final_url
            if expected_type == "html" and ("html" in content_type or b"<html" in data[:5000].lower()):
                if not _looks_like_fulltext_html(data):
                    return _fetch_with_browser_page(context, url, expected_type=expected_type)
                return data, "html", final_url
            resolved = _extract_pdf_link(data, final_url, {"content-type": content_type})
            if resolved:
                pdf_response = context.request.get(
                    resolved,
                    headers={"Accept": "application/pdf,*/*", "User-Agent": USER_AGENT},
                    timeout=DOWNLOAD_TIMEOUT_SECONDS * 1000,
                )
                if not pdf_response.ok:
                    raise RuntimeError(f"HTTP {pdf_response.status} from resolved PDF request")
                pdf_data = pdf_response.body()
                if pdf_data.startswith(b"%PDF"):
                    return pdf_data, "pdf", pdf_response.url
            if "html" in content_type or b"<html" in data[:5000].lower():
                if not _looks_like_fulltext_html(data):
                    return _fetch_with_browser_page(context, url, expected_type="html")
                return data, "html", final_url
            raise RuntimeError(f"browser request returned unsupported content-type '{content_type}'")
        finally:
            browser.close()


def _fetch_with_browser_page(context: Any, url: str, *, expected_type: str) -> tuple[bytes, str, str]:
    page = context.new_page()
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT_SECONDS * 1000)
        final_url = page.url
        content_type = ""
        response_status = 0
        response_ok = False
        response_body = b""
        if response is not None:
            response_status = int(response.status)
            response_ok = bool(response.ok)
            content_type = str(response.headers.get("content-type", "")).lower()
            try:
                response_body = response.body()
            except Exception:
                response_body = b""
            final_url = response.url or final_url
        if response_body.startswith(b"%PDF"):
            return response_body, "pdf", final_url
        if expected_type == "xml" and response_body and _looks_like_xml_or_json(response_body, content_type):
            return response_body, "xml", final_url
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        html = (page.content() or "").encode("utf-8", errors="replace")
        if expected_type == "xml" and _looks_like_xml_or_json(html, "text/html"):
            return html, "xml", final_url
        if "html" in content_type or b"<html" in html[:5000].lower() or b"<!doctype html" in html[:5000].lower():
            if _looks_like_access_blocked_html(html) and not response_ok:
                raise RuntimeError(f"HTTP {response_status} from browser page navigation")
            if not _looks_like_fulltext_html(html):
                raise RuntimeError("browser page did not expose complete full-text HTML")
            return html, "html", final_url
        if response_body:
            raise RuntimeError(f"browser page returned unsupported content-type '{content_type}'")
        raise RuntimeError(f"HTTP {response_status} from browser page navigation")
    finally:
        page.close()


def _looks_like_access_blocked_html(data: bytes) -> bool:
    text = data[:200_000].decode("utf-8", errors="ignore").lower()
    if not text:
        return False
    indicators = (
        "access denied",
        "institutional login",
        "sign in",
        "log in",
        "shibboleth",
        "saml",
        "single sign-on",
        "please login",
        "please log in",
        "not subscribed",
        "purchase access",
    )
    return any(indicator in text for indicator in indicators) and not any(
        marker in text for marker in ("<article", "abstract", "references", "doi:")
    )


def _looks_like_fulltext_html(data: bytes) -> bool:
    text = data[:1_500_000].decode("utf-8", errors="ignore").lower()
    if len(text) < MIN_FULLTEXT_CHARS:
        return False
    positive_markers = (
        "<article",
        "article__body",
        "c-article-body",
        "section",
        "abstract",
        "references",
        "bibliography",
        "methods",
        "results",
        "discussion",
        "fig.",
        "figure",
        "table",
    )
    marker_count = sum(1 for marker in positive_markers if marker in text)
    if marker_count >= 3:
        return True
    if marker_count >= 2 and len(text) >= MIN_FULLTEXT_CHARS * 2:
        return True
    return False


def _looks_like_xml_or_json(data: bytes, content_type: str = "") -> bool:
    lowered_type = str(content_type or "").lower()
    if any(token in lowered_type for token in ("xml", "json")):
        return True
    sample = data[:5000].lstrip().lower()
    return sample.startswith((b"<?xml", b"<article", b"<full-text", b"<component", b"{"))


def save_browser_session_state(
    *,
    start_url: str = DEFAULT_BROWSER_AUTH_URL,
    output: str | Path = DEFAULT_BROWSER_SESSION_STATE,
    headless: bool = False,
    wait_seconds: int = 0,
    user_data_dir: str | Path | None = None,
    check_url: str = "",
) -> dict[str, Any]:
    """Open a browser for licensed institutional login and save storage state.

    This intentionally does not accept username/password arguments. The user
    completes SSO/proxy login in the browser, and only the resulting local
    browser storage state is saved.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RuntimeError(
            "Playwright is required for browser-auth; install with "
            "`pip install playwright` and `playwright install chromium`"
        ) from exc

    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    user_data_path = Path(user_data_dir).expanduser() if user_data_dir else None
    if user_data_path:
        user_data_path.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = None
        context = None
        try:
            if user_data_path:
                context = p.chromium.launch_persistent_context(
                    str(user_data_path),
                    headless=headless,
                    accept_downloads=True,
                    user_agent=USER_AGENT,
                )
            else:
                browser = p.chromium.launch(headless=headless)
                context = browser.new_context(accept_downloads=True, user_agent=USER_AGENT)
            page = context.new_page()
            page.goto(start_url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT_SECONDS * 1000)
            if wait_seconds > 0:
                page.wait_for_timeout(wait_seconds * 1000)
            elif not headless:
                input(
                    "Complete institutional login in the opened browser, verify access, "
                    "then press Enter here to save the session state: "
                )
            access_check = _check_browser_context_access(context, check_url or start_url)
            context.storage_state(path=str(output_path))
        finally:
            if context is not None:
                context.close()
            if browser is not None:
                browser.close()
    return {
        "status": "saved",
        "storage_state": str(output_path),
        "user_data_dir": str(user_data_path) if user_data_path else "",
        "access_check": access_check,
    }


def _check_browser_context_access(context: Any, url: str) -> dict[str, Any]:
    if not url:
        return {"status": "not_requested"}
    try:
        response = context.request.get(
            url,
            headers={"Accept": "application/pdf,text/html,*/*", "User-Agent": USER_AGENT},
            timeout=DOWNLOAD_TIMEOUT_SECONDS * 1000,
        )
        data = response.body()
        content_type = str(response.headers.get("content-type", "")).lower()
        blocked = _looks_like_access_blocked_html(data) if b"<html" in data[:5000].lower() else False
        return {
            "status": "ok" if response.ok and not blocked else "blocked_or_login",
            "url": response.url,
            "http_status": response.status,
            "content_type": content_type,
            "looks_like_pdf": data.startswith(b"%PDF"),
            "looks_like_access_blocked": blocked,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "url": url,
            "failure_reason": str(exc),
        }


def _mark_browser_download_pending(
    artifact: dict[str, Any],
    reason: str,
    report: LiteratureIngestionReport | None,
) -> None:
    artifact["status"] = "pending"
    artifact["failure_reason"] = reason
    artifact["recovery_actions"] = [
        "run literature_ingestion.py browser-auth after logging in through the licensed institutional network",
        f"set {BROWSER_SESSION_STATE_ENV} or pass --browser-session-state",
        "retry prepare-source-log with --fetch-fulltext --download-pdfs --browser-downloads --parse-local-pdfs",
    ]
    if report:
        report.credential_blocked += 1


def _discover_fulltext_artifacts(
    src: dict[str, Any],
    source_id: str,
    report: LiteratureIngestionReport | None,
    *,
    skip_unpaywall: bool = False,
    skip_crossref_fulltext: bool = False,
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    identifiers = src.get("identifiers") or {}
    doi = identifiers.get("doi") or ""
    arxiv_id = (
        identifiers.get("arxiv_id")
        or _arxiv_id_from_url(src.get("url", ""))
        or _arxiv_id_from_url(src.get("pdf_url", ""))
        or ""
    )

    if src.get("pdf_url"):
        artifacts.append(_artifact("pdf", src["pdf_url"], notes="PDF URL from source metadata"))
    if arxiv_id:
        artifacts.append(_artifact("pdf", f"https://arxiv.org/pdf/{arxiv_id}.pdf", notes="arXiv PDF"))
        artifacts.append(_artifact("html", f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}", notes="ar5iv HTML full-text fallback"))
    if doi and not (SKIP_CROSSREF_FULLTEXT or skip_crossref_fulltext):
        artifacts.extend(_crossref_doi_artifacts(doi, report))
    if doi:
        artifacts.extend(_publisher_api_artifacts(src, doi))
    if doi and not (SKIP_UNPAYWALL or skip_unpaywall):
        artifacts.extend(_unpaywall_artifacts(doi, report))
    if _is_http_url(src.get("url", "")):
        artifacts.append(_artifact("html", src["url"], notes="publisher or DOI landing page"))
    artifacts.extend(_credential_required_artifacts(src, report))
    return artifacts


def _unpaywall_artifacts(doi: str, report: LiteratureIngestionReport | None) -> list[dict[str, Any]]:
    email = os.environ.get("UNPAYWALL_EMAIL") or "autopaper2@example.com"
    try:
        encoded = urllib.parse.quote(str(doi), safe="")
        payload = _http_json(f"https://api.unpaywall.org/v2/{encoded}?{urllib.parse.urlencode({'email': email})}")
    except Exception as exc:
        if report:
            report.warnings.append(f"Unpaywall lookup failed for {doi}: {exc}")
        return []
    artifacts: list[dict[str, Any]] = []
    locations = _as_list(payload.get("best_oa_location")) + _as_list(payload.get("oa_locations"))
    seen_urls: set[str] = set()
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        if len(artifacts) >= MAX_UNPAYWALL_LOCATIONS:
            break
        pdf_url = loc.get("url_for_pdf") or ""
        html_url = loc.get("url") or loc.get("url_for_landing_page") or ""
        if pdf_url and pdf_url not in seen_urls:
            seen_urls.add(pdf_url)
            artifacts.append(_artifact("pdf", pdf_url, notes=f"Unpaywall OA location: {loc.get('host_type', '')}"))
        if html_url and html_url not in seen_urls and len(artifacts) < MAX_UNPAYWALL_LOCATIONS:
            seen_urls.add(html_url)
            artifacts.append(_artifact("html", html_url, notes=f"Unpaywall landing page: {loc.get('host_type', '')}"))
    return artifacts


def _crossref_doi_artifacts(doi: str, report: LiteratureIngestionReport | None) -> list[dict[str, Any]]:
    try:
        encoded = urllib.parse.quote(str(doi), safe="")
        payload = _http_json(f"https://api.crossref.org/works/{encoded}")
        item = payload.get("message") or {}
        if isinstance(item, dict):
            return _crossref_link_artifacts(item)
    except Exception as exc:
        if report:
            report.warnings.append(f"Crossref full-text link lookup failed for {doi}: {exc}")
    return []


def _publisher_api_artifacts(src: dict[str, Any], doi: str) -> list[dict[str, Any]]:
    haystack = " ".join(
        str(part or "")
        for part in (
            src.get("publisher"),
            src.get("venue"),
            src.get("url"),
            doi,
        )
    ).lower()
    encoded_doi = urllib.parse.quote(str(doi), safe="")
    artifacts: list[dict[str, Any]] = []
    if "elsevier" in haystack or "sciencedirect" in haystack or doi.startswith("10.1016/"):
        artifacts.append(
            {
                **_artifact(
                    "xml",
                    f"https://api.elsevier.com/content/article/doi/{encoded_doi}",
                    notes="Elsevier Article Retrieval API full text; requires entitlement.",
                ),
                "auth_envs": ["ELSEVIER_API_KEY", "SCOPUS_API_KEY"],
                "auth_header": "X-ELS-APIKey",
                "accept": "application/xml,text/xml,application/json,*/*",
                "recovery_actions": [
                    "provide ELSEVIER_API_KEY or SCOPUS_API_KEY with Article Retrieval entitlement",
                    "retry from an entitled institutional network if required",
                    "use Unpaywall/OpenAlex OA copy when available",
                ],
            }
        )
    if "wiley" in haystack or doi.startswith("10.1002/") or doi.startswith("10.1111/"):
        artifacts.append(
            {
                **_artifact(
                    "pdf",
                    f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{encoded_doi}",
                    notes="Wiley TDM full text; requires token and entitlement.",
                ),
                "auth_env": "WILEY_TDM_TOKEN",
                "auth_header": os.environ.get("WILEY_TDM_AUTH_HEADER", "Wiley-TDM-Client-Token"),
                "recovery_actions": [
                    "provide WILEY_TDM_TOKEN from Wiley TDM access",
                    "ensure the request runs from an entitled institutional IP",
                    "use Crossref/Unpaywall OA links when available",
                ],
            }
        )
    return artifacts


def _credential_required_artifacts(
    src: dict[str, Any],
    report: LiteratureIngestionReport | None,
) -> list[dict[str, Any]]:
    identifiers = src.get("identifiers") or {}
    haystack = " ".join(
        str(part or "")
        for part in (
            src.get("title"),
            src.get("venue"),
            src.get("publisher"),
            src.get("url"),
            identifiers.get("doi"),
        )
    ).lower()
    requirements = [
        ("IEEE", ("ieee", "10.1109"), ("IEEE_API_KEY", "IEEE_XPLORE_API_KEY")),
        ("Elsevier/ScienceDirect", ("elsevier", "sciencedirect", "10.1016"), ("ELSEVIER_API_KEY", "SCOPUS_API_KEY")),
        ("Springer Nature", ("springer", "10.1007"), ("SPRINGER_API_KEY",)),
        ("ACM Digital Library", ("acm", "10.1145"), ("ACM_API_KEY",)),
        ("Wiley", ("wiley", "10.1002"), ("WILEY_TDM_TOKEN",)),
    ]
    artifacts: list[dict[str, Any]] = []
    for publisher, tokens, env_names in requirements:
        if not any(token in haystack for token in tokens):
            continue
        if any(os.environ.get(name) for name in env_names):
            continue
        if report:
            report.credential_blocked += 1
        artifacts.append(
            {
                "artifact_type": "html",
                "uri": f"credential:{publisher}",
                "local_path": "",
                "status": "skipped",
                "failure_reason": f"Direct {publisher} full-text access requires one of {', '.join(env_names)} or institutional access.",
                "recovery_actions": [
                    f"provide {env_names[0]} or institutional access",
                    "retry open-access routes via Unpaywall/OpenAlex/Semantic Scholar",
                    "use manually exported publisher PDF/HTML if licensed",
                ],
                "notes": "Credential-gated publisher connector.",
            }
        )
    return artifacts


def _artifact(artifact_type: str, uri: str, *, notes: str = "") -> dict[str, Any]:
    return {
        "artifact_type": artifact_type,
        "uri": uri,
        "local_path": "",
        "status": "unknown",
        "failure_reason": "",
        "recovery_actions": [],
        "notes": notes,
    }


def _artifact_priority(artifact: Any) -> tuple[int, str]:
    if not isinstance(artifact, dict):
        return (99, "")
    artifact_type = str(artifact.get("artifact_type") or "")
    uri = str(artifact.get("uri") or "").lower()
    notes = str(artifact.get("notes") or "").lower()
    if artifact.get("local_path"):
        return (0, uri)
    if artifact_type == "xml":
        if any(token in uri or token in notes for token in ("full-xml", "jats", "article retrieval", "text-mining", "tdm")):
            return (1, uri)
        if artifact.get("auth_env") or artifact.get("auth_envs"):
            return (2, uri)
        return (2, uri)
    if artifact_type == "html" and "ar5iv.labs.arxiv.org" in uri:
        return (1, uri)
    if artifact_type == "html":
        if uri.startswith("credential:"):
            return (90, uri)
        if any(token in uri or token in notes for token in ("full", "article", "text-mining", "pmc", "arxiv.org", "unpaywall")):
            return (3, uri)
        if "doi.org/" in uri:
            return (8, uri)
        if "sciencedirect.com" in uri or "ieeexplore.ieee.org" in uri or "onlinelibrary.wiley.com" in uri:
            return (4, uri)
        return (4, uri)
    if artifact_type == "pdf":
        if "arxiv.org/pdf" in uri or "arxiv pdf" in notes:
            return (5, uri)
        if "unpaywall" in notes or "openalex" in notes or "repository" in uri:
            return (5, uri)
        return (6, uri)
    return (50, uri)


def _defer_artifact_attempt(artifact: dict[str, Any], reason: str) -> None:
    if artifact.get("local_path") or artifact.get("status") in {"available", "failed", "unavailable", "skipped"}:
        return
    if artifact.get("status") in ("", "unknown", None):
        artifact["status"] = "pending"
    artifact["failure_reason"] = artifact.get("failure_reason") or reason
    artifact["recovery_actions"] = _as_list(artifact.get("recovery_actions")) or [
        "increase AUTOPAPER2_MAX_PDF_ATTEMPTS_PER_SOURCE or AUTOPAPER2_MAX_HTML_ATTEMPTS_PER_SOURCE",
        "retry this source individually",
        "use manually exported licensed PDF/HTML if available",
    ]


def _resolve_browser_session_state(browser_session_state: str | Path | None) -> Path | None:
    value = str(browser_session_state or os.environ.get(BROWSER_SESSION_STATE_ENV) or "").strip()
    if not value:
        return None
    return Path(value).expanduser()


def _should_browser_download(artifact: dict[str, Any]) -> bool:
    uri = str(artifact.get("uri") or "").lower()
    if not uri.startswith(("http://", "https://")):
        return False
    notes = str(artifact.get("notes") or "").lower()
    commercial_hosts = (
        "ieeexplore.ieee.org",
        "xplorestaging.ieee.org",
        "sciencedirect.com",
        "onlinelibrary.wiley.com",
        "api.wiley.com",
        "dl.acm.org",
        "link.springer.com",
    )
    if any(host in uri for host in commercial_hosts):
        return True
    commercial_notes = ("publisher", "tdm", "requires entitlement", "credential")
    return any(token in notes for token in commercial_notes) and (
        "/doi/" in uri or "doi.org/" in uri or artifact.get("auth_env") or artifact.get("auth_envs")
    )


def _should_bulk_download_html(artifact: dict[str, Any]) -> bool:
    uri = str(artifact.get("uri") or "").lower()
    notes = str(artifact.get("notes") or "").lower()
    blocked_hosts = (
        "doi.org/",
        "dx.doi.org/",
        "ieeexplore.ieee.org",
        "sciencedirect.com",
        "onlinelibrary.wiley.com",
        "link.springer.com",
        "dl.acm.org",
    )
    if any(host in uri for host in blocked_hosts):
        return False
    oa_signals = (
        "unpaywall",
        "pmc",
        "europepmc",
        "ar5iv.labs.arxiv.org",
        "arxiv.org/abs",
        "arxiv.org/html",
        "mdpi.com",
        "frontiersin.org",
        "nature.com/articles",
        "springeropen",
        "biomedcentral",
        "peerj.com",
    )
    return any(signal in uri or signal in notes for signal in oa_signals)


def _should_bulk_download_pdf(artifact: dict[str, Any]) -> bool:
    if artifact.get("auth_env") or artifact.get("auth_envs"):
        return _artifact_credentials_available(artifact)
    uri = str(artifact.get("uri") or "").lower()
    notes = str(artifact.get("notes") or "").lower()
    blocked_hosts = (
        "ieeexplore.ieee.org",
        "xplorestaging.ieee.org",
        "sciencedirect.com",
        "onlinelibrary.wiley.com",
        "api.wiley.com",
        "dl.acm.org",
        "link.springer.com",
    )
    if any(host in uri for host in blocked_hosts):
        return False
    oa_signals = (
        "arxiv.org/pdf",
        "europepmc.org",
        "pmc.ncbi.nlm.nih.gov",
        "ncbi.nlm.nih.gov/pmc",
        "unpaywall",
        "repository",
        "core.ac.uk",
        "mdpi.com",
        "frontiersin.org",
        "springeropen",
        "biomedcentral",
        "peerj.com",
    )
    return any(signal in uri or signal in notes for signal in oa_signals)


def _fetch_limited(
    url: str,
    limit_bytes: int,
    *,
    request_headers: dict[str, str] | None = None,
) -> tuple[bytes, dict[str, str], str]:
    headers = {"User-Agent": USER_AGENT}
    if request_headers:
        headers.update(request_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT_SECONDS) as resp:
        started = time.monotonic()
        chunks: list[bytes] = []
        total = 0
        while total < limit_bytes:
            if time.monotonic() - started > DOWNLOAD_TIMEOUT_SECONDS:
                raise TimeoutError(f"download exceeded {DOWNLOAD_TIMEOUT_SECONDS}s")
            chunk = resp.read(min(64 * 1024, limit_bytes - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        data = b"".join(chunks)
        headers = {key.lower(): value for key, value in resp.headers.items()}
        return data, headers, resp.geturl()


def _artifact_request_headers(artifact: dict[str, Any], *, accept: str = "") -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    elif artifact.get("accept"):
        headers["Accept"] = str(artifact["accept"])
    auth_value = _artifact_auth_value(artifact)
    if auth_value:
        header_name = str(artifact.get("auth_header") or "Authorization")
        scheme = str(artifact.get("auth_scheme") or "").strip()
        headers[header_name] = f"{scheme} {auth_value}" if scheme else auth_value
    return headers


def _artifact_credentials_available(artifact: dict[str, Any]) -> bool:
    env_names = _artifact_auth_envs(artifact)
    return not env_names or any(os.environ.get(env_name) for env_name in env_names)


def _artifact_auth_value(artifact: dict[str, Any]) -> str:
    for env_name in _artifact_auth_envs(artifact):
        value = os.environ.get(env_name)
        if value:
            return value
    return ""


def _artifact_auth_envs(artifact: dict[str, Any]) -> list[str]:
    names = _as_list(artifact.get("auth_envs"))
    if artifact.get("auth_env"):
        names.append(artifact["auth_env"])
    return [str(name) for name in names if name]


def _mark_credential_blocked(artifact: dict[str, Any], report: LiteratureIngestionReport | None) -> None:
    env_names = _artifact_auth_envs(artifact)
    artifact["status"] = "skipped"
    artifact["failure_reason"] = (
        f"Credential required for this full-text artifact: {', '.join(env_names)}"
        if env_names
        else "Credential required for this full-text artifact"
    )
    artifact["recovery_actions"] = _as_list(artifact.get("recovery_actions")) or [
        f"set {env_names[0]}" if env_names else "configure publisher/API credentials",
        "retry prepare-source-log with --fetch-fulltext --download-pdfs --parse-local-pdfs",
        "use a licensed PDF/HTML/XML export if available",
    ]
    if report:
        report.credential_blocked += 1


def _extract_pdf_link(data: bytes, base_url: str, headers: dict[str, str]) -> str:
    content_type = headers.get("content-type", "").lower()
    sample = data[:1_000_000]
    if "html" not in content_type and b"<html" not in sample.lower():
        return ""
    text = sample.decode("utf-8", errors="replace")
    patterns = [
        r'href=["\']([^"\']+?\.pdf(?:\?[^"\']*)?)["\']',
        r'(https?://[^\s"\'<>]+?\.pdf(?:\?[^\s"\'<>]*)?)',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            candidate = html_lib.unescape(match.group(1))
            if candidate.lower().startswith(("javascript:", "mailto:")):
                continue
            return urllib.parse.urljoin(base_url, candidate)
    return ""


def _append_note(existing: str, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing}; {note}"


def _artifact_file_stem(source_id: str, uri: str) -> str:
    source_part = _slug(source_id) or "paper"
    uri_hash = hashlib.sha1(str(uri or source_id).encode("utf-8")).hexdigest()[:8]
    return f"{source_part}_{uri_hash}"


def _fill_artifact_hash(artifact: dict[str, Any], project_root: Path | None) -> None:
    local = artifact.get("local_path") or artifact.get("path") or ""
    if not local or artifact.get("sha256"):
        return
    path = Path(local)
    if not path.is_absolute() and project_root:
        path = project_root / path
    if path.exists() and path.is_file():
        artifact["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        artifact["status"] = "available"


def _first_local_pdf(src: dict[str, Any], project_root: Path | None) -> Path | None:
    for artifact in _as_list(src.get("artifacts")):
        if not isinstance(artifact, dict) or artifact.get("artifact_type") != "pdf":
            continue
        local = artifact.get("local_path") or artifact.get("path")
        if not local:
            continue
        path = Path(local)
        if not path.is_absolute() and project_root:
            path = project_root / path
        if path.exists():
            return path
    return None


def _first_local_html(src: dict[str, Any], project_root: Path | None) -> Path | None:
    for artifact in _as_list(src.get("artifacts")):
        if not isinstance(artifact, dict) or artifact.get("artifact_type") != "html":
            continue
        local = artifact.get("local_path") or artifact.get("path")
        if not local:
            continue
        path = Path(local)
        if not path.is_absolute() and project_root:
            path = project_root / path
        if path.exists():
            return path
    return None


def _first_local_xml(src: dict[str, Any], project_root: Path | None) -> Path | None:
    for artifact in _as_list(src.get("artifacts")):
        if not isinstance(artifact, dict) or artifact.get("artifact_type") != "xml":
            continue
        local = artifact.get("local_path") or artifact.get("path")
        if not local:
            continue
        path = Path(local)
        if not path.is_absolute() and project_root:
            path = project_root / path
        if path.exists():
            return path
    return None


def _mark_local_artifact_parse(
    src: dict[str, Any],
    parsed_path: Path,
    project_root: Path | None,
    parse_status: str,
    *,
    backend: str = "",
    parse_error: str = "",
) -> None:
    try:
        target = parsed_path.resolve()
    except Exception:
        target = parsed_path
    for artifact in _as_list(src.get("artifacts")):
        if not isinstance(artifact, dict):
            continue
        local = artifact.get("local_path") or artifact.get("path")
        if not local:
            continue
        path = Path(local)
        if not path.is_absolute() and project_root:
            path = project_root / path
        try:
            same_path = path.resolve() == target
        except Exception:
            same_path = path == target
        if not same_path:
            continue
        artifact["parse_status"] = parse_status
        if backend:
            artifact["parse_backend"] = backend
        if parse_error:
            artifact["parse_failure_reason"] = parse_error
            artifact["recovery_actions"] = _as_list(artifact.get("recovery_actions")) or [
                "retry with another parser backend",
                "try publisher/OA HTML full text",
                "use OCR or manually supplied licensed PDF/HTML",
            ]


def _http_json(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    return json.loads(_http_bytes(url, headers=headers).decode("utf-8"))


def _http_bytes(url: str, *, headers: dict[str, str] | None = None) -> bytes:
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        return resp.read()


def _dedupe_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for src in sources:
        key = _dedupe_key(src)
        if key in seen:
            continue
        seen.add(key)
        merged.append(src)
    return merged


def _dedupe_key(src: dict[str, Any]) -> str:
    identifiers = src.get("identifiers") or {}
    for field in ("doi", "arxiv_id", "semantic_scholar_id"):
        value = identifiers.get(field)
        if value:
            return f"{field}:{str(value).lower()}"
    return "title:" + _slug(src.get("title", ""))


def _screen_sources_for_query(
    sources: list[dict[str, Any]],
    query: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tokens = _query_tokens(query)
    specific_tokens = [
        token
        for token in tokens
        if token not in {"semantic", "communication", "communications", "digital"}
    ]
    if not specific_tokens:
        return sources, []

    kept: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for src in sources:
        text = " ".join(
            str(part or "")
            for part in (
                src.get("title"),
                src.get("abstract"),
                src.get("venue"),
                src.get("publisher"),
            )
        ).lower()
        matched = [token for token in tokens if token in text]
        specific_matched = [token for token in specific_tokens if token in text]
        if len(matched) >= 2 and specific_matched:
            kept.append(src)
        else:
            excluded.append(
                {
                    "source_id": str(src.get("id", "")),
                    "title": str(src.get("title", "")),
                    "reason": "missing query-specific terms",
                    "matched_terms": matched,
                    "required_any": specific_tokens,
                }
            )

    return (kept, excluded) if kept else (sources, [])


def _query_variants(query: str) -> list[str]:
    """Expand one topic into a small set of database-friendly query forms."""
    base = " ".join(str(query or "").split())
    if not base:
        return [""]

    lowered = base.lower()
    contains_cjk = bool(re.search(r"[\u4e00-\u9fff]", base))
    variants = [] if contains_cjk else [base]
    has_semantic_comm = ("semantic" in lowered and "communication" in lowered) or "语义通信" in base
    has_modulation = "modulation" in lowered or "调制" in base
    has_image = "image" in lowered or "图像" in base
    if has_semantic_comm:
        variants.extend(
            [
                "image semantic communication digital modulation",
                "digital semantic communication image transmission",
                "semantic image communication modulation",
                "joint coding modulation semantic communication",
                "semantic coding modulation image wireless",
                "deep joint source channel coding image wireless",
            ]
        )
    if has_modulation:
        variants.extend(
            [
                "joint source channel coding modulation image",
                "coded modulation semantic communications",
            ]
        )
    if has_image:
        variants.extend(
            [
                "semantic image transmission wireless",
                "image transmission semantic communication channel",
            ]
        )
    if contains_cjk:
        variants.insert(1 if variants else 0, base)

    deduped: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        normalized = " ".join(variant.split())
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped[:8]


def _query_tokens(query: str) -> list[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "for",
        "from",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "via",
        "with",
    }
    tokens = []
    for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", query.lower()):
        if token not in stopwords and token not in tokens:
            tokens.append(token)
    chinese_expansions = {
        "图像": ("image",),
        "数字图像": ("image",),
        "语义通信": ("semantic", "communication"),
        "数字调制": ("modulation",),
        "调制": ("modulation",),
    }
    for phrase, mapped_tokens in chinese_expansions.items():
        if phrase in query:
            for token in mapped_tokens:
                if token not in tokens:
                    tokens.append(token)
    return tokens


def _publisher_coverage(sources: list[dict[str, Any]]) -> dict[str, Any]:
    patterns = {
        "IEEE": ("ieee", "10.1109", "ieeexplore"),
        "Elsevier/ScienceDirect": ("elsevier", "sciencedirect", "10.1016"),
        "ACM": ("acm", "10.1145", "dl.acm.org"),
        "Springer": ("springer", "10.1007", "link.springer"),
        "Wiley": ("wiley", "10.1002", "onlinelibrary.wiley"),
        "arXiv": ("arxiv", "arxiv.org"),
    }
    coverage: dict[str, Any] = {}
    for publisher, tokens in patterns.items():
        matches: list[dict[str, str]] = []
        for src in sources:
            identifiers = src.get("identifiers") or {}
            haystack = " ".join(
                str(part or "")
                for part in (
                    src.get("title"),
                    src.get("venue"),
                    src.get("publisher"),
                    src.get("url"),
                    src.get("pdf_url"),
                    identifiers.get("doi"),
                    identifiers.get("arxiv_id"),
                )
            ).lower()
            if any(token in haystack for token in tokens):
                matches.append(
                    {
                        "source_id": str(src.get("id", "")),
                        "title": str(src.get("title", "")),
                        "venue": str(src.get("venue", "")),
                    }
                )
        coverage[publisher] = {
            "covered": bool(matches),
            "match_count": len(matches),
            "examples": matches[:5],
        }
    return coverage


def _discovery(
    surface: str,
    query: str,
    rank: int,
    result_url: str,
    *,
    reason: str = "",
) -> dict[str, Any]:
    return {
        "search_surface": surface,
        "query_text": query,
        "result_rank": rank,
        "result_url": result_url,
        "screened_status": "retained",
        "retained_reason": reason or "keyword search candidate",
    }


def _has_artifact(artifacts: list[Any], artifact_type: str, uri: str) -> bool:
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        if artifact.get("artifact_type") == artifact_type and artifact.get("uri") == uri:
            return True
    return False


def _derive_pdf_url(url: str) -> str:
    if not url:
        return ""
    if url.lower().endswith(".pdf"):
        return url
    match = re.search(r"arxiv\.org/abs/([^?#]+)", url)
    if match:
        return f"https://arxiv.org/pdf/{match.group(1)}.pdf"
    return ""


def _arxiv_id_from_url(url: str) -> str:
    match = re.search(r"arxiv\.org/(?:abs|pdf|html)/([^?#]+)", str(url or ""), flags=re.I)
    if not match:
        return ""
    arxiv_id = match.group(1).strip("/")
    arxiv_id = re.sub(r"\.pdf$", "", arxiv_id, flags=re.I)
    return arxiv_id


def _is_http_url(url: str) -> bool:
    return str(url or "").lower().startswith(("http://", "https://"))


def _enrich_source_from_openalex_doi(source: dict[str, Any]) -> None:
    identifiers = source.get("identifiers") or {}
    doi = identifiers.get("doi") or ""
    if not doi or (source.get("abstract") and source.get("pdf_url")):
        return
    try:
        encoded = urllib.parse.quote(str(doi), safe="")
        payload = _http_json(f"https://api.openalex.org/works/https://doi.org/{encoded}")
    except Exception:
        return
    if not source.get("abstract"):
        source["abstract"] = _openalex_abstract(payload.get("abstract_inverted_index"))
    if not source.get("pdf_url"):
        best_location = payload.get("best_oa_location") or payload.get("primary_location") or {}
        source["pdf_url"] = best_location.get("pdf_url") or ""
    if not source.get("venue"):
        source["venue"] = (
            (payload.get("primary_location") or {}).get("source") or {}
        ).get("display_name", "")
    if not source.get("citation_count"):
        source["citation_count"] = payload.get("cited_by_count") or 0


def _source_id(src: dict[str, Any], idx: int) -> str:
    if src.get("id"):
        return str(src["id"])
    identifiers = src.get("identifiers") or {}
    for field in ("doi", "arxiv_id", "semantic_scholar_id"):
        if identifiers.get(field):
            return _stable_source_id(field, identifiers[field])
    return _stable_source_id("source", src.get("title") or f"source-{idx}")


def _stable_source_id(prefix: str, raw: str) -> str:
    return f"{_slug(prefix)}_{hashlib.sha1(str(raw).encode('utf-8')).hexdigest()[:10]}"


def _slug(value: str) -> str:
    value = str(value or "").lower()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value[:80]


def _normalize_doi(value: str) -> str:
    value = str(value or "").strip()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.I)
    return value.lower()


def _strip_trailing_period(value: str) -> str:
    return re.sub(r"\s*\.$", "", str(value or "").strip())


def _clean_crossref_abstract(value: str) -> str:
    value = str(value or "")
    value = re.sub(r"</?jats:[^>]+>", " ", value)
    value = re.sub(r"<[^>]+>", " ", value)
    return _clip(html_lib.unescape(value), 3000)


def _openalex_abstract(inverted_index: Any) -> str:
    if not isinstance(inverted_index, dict):
        return ""
    positions: dict[int, str] = {}
    for word, indexes in inverted_index.items():
        for idx in indexes:
            positions[int(idx)] = word
    return " ".join(positions[idx] for idx in sorted(positions))


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value in (None, ""):
        return []
    return [value]


def _clip(text: str, max_chars: int) -> str:
    text = " ".join(str(text).split())
    return text[:max_chars]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AutoPaper2 literature ingestion helper")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search scholarly APIs and emit a source-log fragment")
    search.add_argument("query", help="Keyword query")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--surface", action="append", choices=DEFAULT_SURFACES)
    search.add_argument("--output", help="YAML output path; stdout if omitted")

    auth = sub.add_parser("browser-auth", help="Open a browser, let the user log in, and save local storage state")
    auth.add_argument(
        "--start-url",
        default=DEFAULT_BROWSER_AUTH_URL,
        help="Publisher/library URL to open for institutional login",
    )
    auth.add_argument(
        "--output",
        default=DEFAULT_BROWSER_SESSION_STATE,
        help="Storage-state JSON path; keep this file local and out of git",
    )
    auth.add_argument(
        "--user-data-dir",
        default=DEFAULT_BROWSER_PROFILE_DIR,
        help=(
            "Optional persistent Playwright profile directory. Reuse this path "
            "to keep institutional login state across browser-auth runs."
        ),
    )
    auth.add_argument(
        "--check-url",
        default="",
        help="Optional publisher article/PDF URL to probe before saving the session state",
    )
    auth.add_argument("--headless", action="store_true", help="Run browser headless")
    auth.add_argument(
        "--wait-seconds",
        type=int,
        default=0,
        help="Wait this many seconds before saving state; default waits for Enter in headed mode",
    )

    prep = sub.add_parser("prepare-source-log", help="Normalize discovery/artifact/parse fields")
    prep.add_argument("source_log", help="Path to M1_source_log.yaml or M2_source_log.yaml")
    prep.add_argument("--output", help="Write to this path instead of editing in-place")
    prep.add_argument("--project-root", help="Project root for relative artifacts")
    prep.add_argument("--module", default="M1", choices=("M1", "M2"))
    prep.add_argument("--network-check", action="store_true", help="HEAD-check PDF/HTML URLs")
    prep.add_argument("--download-pdfs", action="store_true", help="Download verified PDF artifacts")
    prep.add_argument(
        "--fetch-fulltext",
        action="store_true",
        help="Discover/download OA full text via Unpaywall/OpenAlex/arXiv/publisher HTML and record credential-gated blockers",
    )
    prep.add_argument("--skip-unpaywall", action="store_true", help="Skip per-DOI Unpaywall lookups for faster batch verification")
    prep.add_argument("--skip-crossref-fulltext", action="store_true", help="Skip per-DOI Crossref full-text link lookups for faster batch verification")
    prep.add_argument(
        "--browser-downloads",
        action="store_true",
        help="Use an authorized Playwright storage state to download credential-gated publisher PDF/HTML artifacts",
    )
    prep.add_argument(
        "--browser-session-state",
        help=f"Playwright storage-state JSON path; defaults to ${BROWSER_SESSION_STATE_ENV} when set",
    )
    prep.add_argument(
        "--parse-local-pdfs",
        action="store_true",
        help="Parse local PDF artifacts with pdftotext/pdfminer/PyMuPDF when available",
    )
    prep.add_argument("--max-sources", type=int, help="Process only the first N academic sources for batch verification")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.command == "search":
        data = search_literature(
            args.query,
            limit=args.limit,
            surfaces=args.surface or DEFAULT_SURFACES,
        )
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0
    if args.command == "browser-auth":
        auth_result = save_browser_session_state(
            start_url=args.start_url,
            output=args.output,
            headless=args.headless,
            wait_seconds=args.wait_seconds,
            user_data_dir=args.user_data_dir or None,
            check_url=args.check_url,
        )
        auth_result["next"] = (
            "Set AUTOPAPER2_BROWSER_SESSION_STATE to storage_state or pass "
            "--browser-session-state when running prepare-source-log."
        )
        print(
            yaml.safe_dump(
                auth_result,
                allow_unicode=True,
                sort_keys=False,
            ),
            end="",
        )
        return 0
    if args.command == "prepare-source-log":
        report = prepare_source_log(
            args.source_log,
            output_path=args.output,
            project_root=args.project_root,
            module=args.module,
            network_check=args.network_check,
            download_pdfs=args.download_pdfs,
            fetch_fulltext=args.fetch_fulltext,
            parse_local_pdfs=args.parse_local_pdfs,
            max_sources=args.max_sources,
            skip_unpaywall=args.skip_unpaywall,
            skip_crossref_fulltext=args.skip_crossref_fulltext,
            browser_downloads=args.browser_downloads,
            browser_session_state=args.browser_session_state,
        )
        print(yaml.safe_dump(report.to_dict(), allow_unicode=True, sort_keys=False), end="")
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
