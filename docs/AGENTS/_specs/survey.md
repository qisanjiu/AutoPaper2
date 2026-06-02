# Survey / Ideation Compact Spec

## Survey Agent Stages
- `M1S01`: define topic, entry anchors, related domains, keywords/synonyms, timeline, teams, venues, and downstream handoff notes.
- `M1S02`: run 3-round literature deep dive. Round 1 breadth, Round 2 targeted gap depth, Round 3 blindspot filling. Maintain `state/survey_memory.yaml` and `knowledge/M1/M1_source_log.yaml`.

## M1S02 Required Content
- Search strategy: databases/web queries, inclusion/exclusion criteria, iteration notes.
- Literature cards: problem, method, datasets, metrics, claims, limitations, credibility.
- Gap analysis: vacancy gaps, enhancement gaps, micro-gaps, evidence strength, affected task/data/metric.
- Solution arsenal: transferable mechanisms for vacancy gaps and component-improvement options for enhancement gaps.
- Source log schema: `search_statistics`, `sources`, `gap_evidence_map`, stable source ids, query ledger, discovery source, credibility.

## Ideation Agent Stages
- `M1S03`: turn gaps into concrete research questions; state novelty type, target bottleneck, closest work, and falsifiable scope.
- `M1S04`: generate hypotheses with expected direction, mechanism, measurable outcomes, and falsification path.
- `M1S05`: assess novelty, feasibility, risk, Plan B, downstream handoff, and whether M2 can design a method.

## Hard Rules
- Do not invent citations. Every claim about literature must map to source ids.
- Enhancement-gap ideas must name the bottleneck/component being improved; decorative changes are not enough.
- If M1S02 is incomplete, reviewers may require repeating a specific search round.
