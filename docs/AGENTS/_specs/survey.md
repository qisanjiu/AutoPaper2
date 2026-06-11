# Survey / Ideation Compact Spec

## Survey Agent Stages
- `M1S01`: define topic, entry anchors, related domains, keywords/synonyms, timeline, teams, venues, and downstream handoff notes.
- `M1S02`: run 3-round literature deep dive. Round 1 breadth, Round 2 targeted gap depth, Round 3 blindspot filling. Maintain `state/survey_memory.yaml` and `knowledge/M1/M1_source_log.yaml`.

## M1S02 Required Content
- Search strategy: databases/web queries, inclusion/exclusion criteria, iteration notes.
- Literature cards: problem, method, datasets, metrics, claims, limitations, credibility.
- Collection ledger: for every retained academic source, record discovery provenance, metadata source, artifact acquisition state, and PDF/HTML/BibTeX/source availability.
- Failure handling: if PDF download/read/parse fails, record `status=failed|unavailable|skipped`, `failure_reason`, and `recovery_actions` such as Crossref/OpenAlex/Semantic Scholar metadata, publisher HTML, arXiv source, or manual abstract-only card.
- Parse profile: write section summaries and parser/backend (`grobid`, `pdftotext`, `pdfminer`, `pymupdf`, `publisher_html`, `html_text`, `xml_text`, `arxiv_source`, `abstract_only`, `source_log_card`), plus `missing_fields`.
- Downstream signals: each source must state what is ready for M2 method reference, M3 experiment setup, M4 analysis design, and M5 citation/writing.
- Gap analysis: vacancy gaps, enhancement gaps, micro-gaps, evidence strength, affected task/data/metric.
- Solution arsenal: transferable mechanisms for vacancy gaps and component-improvement options for enhancement gaps.
- Source log schema: `search_statistics`, `sources`, `gap_evidence_map`, stable source ids, query ledger, discovery records, artifacts, parse profile, downstream signals, credibility.
- Helper tooling: use `python scripts/literature_ingestion.py search ...` for default public and credential-gated database candidate search when useful, including Crossref publisher/TDM metadata for ACM/Wiley and Web of Science when configured. Use `python scripts/literature_ingestion.py prepare-source-log <source_log> --project-root <project>` to normalize discovery/artifact/parse fields before review. Use `--fetch-fulltext --download-pdfs --parse-local-pdfs` when file/network access is intentionally part of the stage work and record credential-gated failures explicitly.

## Ideation Agent Stages
- `M1S03`: turn gaps into concrete research questions; state novelty type, target bottleneck, closest work, and falsifiable scope.
- `M1S04`: generate hypotheses with expected direction, mechanism, measurable outcomes, and falsification path.
- `M1S05`: assess novelty, feasibility, risk, Plan B, downstream handoff, and whether M2 can design a method.

## Hard Rules
- Do not invent citations. Every claim about literature must map to source ids.
- Missing PDFs are allowed only when the source log preserves the acquisition failure and a bounded fallback parse path.
- Enhancement-gap ideas must name the bottleneck/component being improved; decorative changes are not enough.
- If M1S02 is incomplete, reviewers may require repeating a specific search round.
