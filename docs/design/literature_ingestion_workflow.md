# Literature Search, Collection, Parsing, and Ingestion Workflow

## External Patterns Checked

This workflow is based on implementation patterns from mature literature tools:

- PaperQA2: indexes local PDFs, fills metadata through Crossref and Semantic Scholar, chunks evidence, and reuses the built index on later queries. Source: https://github.com/future-house/paper-qa
- GROBID: parses scholarly PDFs into structured TEI/XML, including metadata, references, full-text sections, figures/tables, citation contexts, and coordinates. Source: https://github.com/grobidOrg/grobid
- Zotero: retrieves metadata from PDFs when identifiers or extractable metadata exist, but treats failed retrieval as a normal condition that needs manual/alternate metadata handling. Source: https://www.zotero.org/support/retrieve_pdf_metadata
- Findpapers: uses one query over multiple scholarly databases and merges/deduplicates results. Source: https://github.com/jonatasgrosman/findpapers
- Semantic Scholar / Ai2 Paper Finder: emphasizes iterative query decomposition, citation following, and relevance explanations rather than a single keyword pass. Source: https://allenai.org/blog/paper-finder

AutoPaper2 should not simply download PDFs and hope downstream stages can read them. It needs auditable state for every paper: where it was found, how metadata was completed, whether PDF/HTML/BibTeX/source was obtained, how parsing was done, what failed, and which downstream module can safely consume which slice.

## Target Pipeline

1. Search candidates
   - Query public DB first.
   - Query external scholarly surfaces when local hits are insufficient: OpenAlex, Crossref/DOI, Semantic Scholar, arXiv, DBLP, Europe PMC, DOAJ, publisher pages, and citation chains.
   - Attempt direct publisher/database connectors for IEEE Xplore, Elsevier/ScienceDirect/Scopus, Springer Nature, CORE, and Web of Science Starter when credentials are configured.
   - For ACM and Wiley, use Crossref publisher/TDM metadata as the default searchable path, and optionally use `ACM_SEARCH_ENDPOINT` or `WILEY_SEARCH_ENDPOINT` when a local institutional endpoint exists.
   - If a credential-gated connector cannot run, record the failed search round and required environment variable instead of silently treating the database as covered.
   - Record query text, surface, rank, result URL, screened status, and retained reason.

2. Collect metadata and artifacts
   - Canonicalize by DOI, arXiv, Semantic Scholar, DBLP, then title/author/year fallback.
   - Fill title, authors, venue, year/date, abstract, URL, PDF URL, code URL, citation count where available.
   - Store artifact records for PDF, HTML, XML, BibTeX, arXiv source, and supplements.
   - Discover full-text candidates from source metadata, arXiv PDF URLs, OpenAlex OA locations, Crossref publisher/TDM links, Unpaywall OA locations, DOI/publisher HTML, credential-gated publisher records, and publisher APIs such as Elsevier Article Retrieval or Wiley TDM when credentials are available.
   - In batch mode, prefer PDF/OA full-text HTML and keep DOI or credential-gated publisher landing pages as pending unless the user reruns a source with credentials or higher attempt limits.
   - PDF failure is not a blocker by itself, but silent failure is forbidden. Failed/unavailable/skipped artifacts must include `failure_reason` and `recovery_actions`.

3. Parse content
   - Preferred parse order: full PDF via `pdftotext`, `pdfminer.six`, PyMuPDF, or PyPDF-compatible libraries; publisher/OA HTML; publisher/OA XML/JATS/API payloads; arXiv source where available; then metadata/abstract-only card.
   - If arXiv PDF download fails, try ar5iv/arXiv HTML as an alternate full-text route.
   - Short DOI landing pages and blocked publisher pages may populate partial evidence, but must not be marked as complete full text.
   - Store `parse_backend`, `parse_status`, `fulltext_status`, `missing_fields`, `section_summaries`, and `confidence`.
   - Never present missing experiment setup, baselines, metrics, or method details as known facts.

4. Produce downstream signals
   - `M2`: method reference, core mechanism, transferability.
   - `M3`: dataset, metrics, baselines, split/protocol, fairness/resource hints.
   - `M4`: ablation, mechanism, robustness, failure/negative-analysis patterns.
   - `M5`: citation readiness, related-work wording, limitations and claim boundaries.

5. Ingest into public DB
   - `papers`: canonical metadata and reusable summaries.
   - `literature_discovery`: search provenance.
   - `literature_artifacts`: artifact acquisition status and recovery actions.
   - `literature_extractions`: parse profile and downstream signals.

## Source Log Contract

Every academic source in `M1_source_log.yaml` and `M2_source_log.yaml` must include:

- `discovery_records` or legacy `discovery_source` + `discovery_query`.
- `artifacts` with at least one acquisition record.
- `parse_profile` with `metadata_status`, `fulltext_status`, `parse_status`, `parse_backend`, `section_summaries`, `missing_fields`, and `downstream_signals`.
- `downstream_signals.M2`, `.M3`, `.M4`, `.M5`.

Accepted artifact statuses:

- `available`: usable URL or project-local path exists.
- `failed`: attempted but failed; requires reason and recovery actions.
- `unavailable`: known unavailable; requires reason and recovery actions.
- `skipped`: intentionally not collected; requires reason and recovery actions.
- `pending`: queued, not yet usable.
- `unknown`: known record but not checked yet; should not support strong downstream claims and must explain the pending check or fallback path.

Accepted parse statuses:

- `complete`: all required paper-card sections are populated from a parseable artifact.
- `partial`: usable metadata/abstract/sections exist, but some fields are missing.
- `blocked`: parsing cannot support downstream claims until fixed.
- `not_attempted`: no parse has been attempted.

## Operational Commands

```bash
# Search the default scholarly surfaces and emit a source-log fragment. Default
# surfaces include public indexes plus credential-gated publisher/database checks.
python scripts/literature_ingestion.py search "semantic communication robust compression" --limit 10 --output /tmp/source_candidates.yaml

# Normalize an existing M1/M2 source log with discovery, artifact, parse, and downstream fields.
python scripts/literature_ingestion.py prepare-source-log projects/<project>/knowledge/M1/M1_source_log.yaml --project-root projects/<project>

# Optional acquisition/parsing passes. These are explicit because they use network/filesystem tools.
python scripts/literature_ingestion.py prepare-source-log projects/<project>/knowledge/M1/M1_source_log.yaml --project-root projects/<project> --network-check
python scripts/literature_ingestion.py prepare-source-log projects/<project>/knowledge/M1/M1_source_log.yaml --project-root projects/<project> --fetch-fulltext --download-pdfs --parse-local-pdfs
python scripts/literature_ingestion.py prepare-source-log projects/<project>/knowledge/M1/M1_source_log.yaml --project-root projects/<project> --fetch-fulltext --download-pdfs --parse-local-pdfs --max-sources 20
python scripts/literature_ingestion.py prepare-source-log projects/<project>/knowledge/M1/M1_source_log.yaml --project-root projects/<project> --fetch-fulltext --skip-unpaywall --download-pdfs --parse-local-pdfs
python scripts/literature_ingestion.py prepare-source-log projects/<project>/knowledge/M1/M1_source_log.yaml --project-root projects/<project> --fetch-fulltext --skip-unpaywall --skip-crossref-fulltext --download-pdfs --parse-local-pdfs --max-sources 20

# Optional licensed browser-session acquisition. Complete institutional login in
# the opened browser; the script saves local Playwright storage state, not a
# username/password. Keep this JSON out of git.
pip install -e '.[browser]'
playwright install chromium
python scripts/literature_ingestion.py browser-auth \
  --start-url https://ieeexplore.ieee.org/ \
  --user-data-dir config/browser_sessions/literature_profile \
  --output config/browser_sessions/literature_storage_state.json
python scripts/literature_ingestion.py prepare-source-log projects/<project>/knowledge/M1/M1_source_log.yaml --project-root projects/<project> --fetch-fulltext --download-pdfs --browser-downloads --browser-session-state config/browser_sessions/literature_storage_state.json --parse-local-pdfs --max-sources 20

python scripts/state_manager.py public-db status
python scripts/state_manager.py public-db stats
python scripts/state_manager.py public-db ingestion
python scripts/state_manager.py public-db search "semantic communication"
python scripts/state_manager.py public-db import-project projects/<project>
python scripts/state_manager.py public-db show-paper <paper_id>
```

## Review Rules

- M1/M2 cannot pass source-log validation when a retained academic source lacks discovery provenance, artifact status, parse profile, or downstream signals.
- PDF download failure is acceptable only when explicitly recorded with a fallback parse path.
- M3/M4 must treat `parse_status=partial|blocked` and missing experiment/protocol fields as evidence limits, not as support.
- M5 may cite a source with metadata-only parse if citation metadata is complete, but it must not use unavailable full text as evidence for detailed method or experiment claims.

## Credential Configuration

Direct access to commercial indexes and publisher full text requires API or institutional access. Configure whichever credentials are available before running the search/full-text pass:

- `IEEE_API_KEY` or `IEEE_XPLORE_API_KEY`
- `ELSEVIER_API_KEY` or `SCOPUS_API_KEY` for Scopus search and Elsevier Article Retrieval full text when licensed
- `SPRINGER_API_KEY`
- `CORE_API_KEY`
- `WOS_API_KEY` or `WEB_OF_SCIENCE_API_KEY`; optionally `WOS_SEARCH_ENDPOINT` for a local proxy
- `ACM_SEARCH_ENDPOINT` plus optional `ACM_API_KEY` for institutional ACM search; otherwise ACM metadata/full-text links come from Crossref DOI/TDM records
- `WILEY_TDM_TOKEN`; optionally `WILEY_TDM_AUTH_HEADER` and `WILEY_SEARCH_ENDPOINT`
- `UNPAYWALL_EMAIL` for OA discovery attribution
- `AUTOPAPER2_BROWSER_SESSION_STATE` for an already-authorized local Playwright storage-state JSON used by `--browser-downloads`

Browser-session download is explicit and opt-in. AutoPaper2 must not store account passwords in source logs, command lines, repository files, tests, or dispatch packets. Use `browser-auth` to save a local session after the user has completed lawful institutional login in a real browser. Pass the same `--user-data-dir` on later runs to reuse the Playwright browser profile instead of logging in again; use `--check-url <publisher-pdf-or-article-url>` to record whether the current session appears entitled before saving. The resulting storage-state JSON and profile directory are secret local artifacts and should stay under `config/browser_sessions/` or another ignored path.
