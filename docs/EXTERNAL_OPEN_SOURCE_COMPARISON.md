# AutoPaper2 External Open-Source Comparison

Date: 2026-05-23

This note compares AutoPaper2 against open-source or openly documented research-agent systems and turns the comparison into concrete optimization guidance for M1-M6.

## Compared Systems

| System | Relevant capability | AutoPaper2 takeaway |
|---|---|---|
| [The AI Scientist](https://github.com/sakanaai/ai-scientist) / [paper](https://arxiv.org/abs/2408.06292) | End-to-end idea generation, code, experiments, plots, paper writing, and automated review. The repository uses domain templates with `experiment.py`, `plot.py`, prompts, seed ideas, and LaTeX templates, plus an LLM review path. | AutoPaper2 should keep stage outputs as durable artifacts, require plot/code provenance, and make review loops explicit rather than treating review as a final comment. Already adopted in M3/M5/M6 gates. |
| [The AI Scientist-v2](https://arxiv.org/abs/2504.08066) | Removes reliance on human-authored code templates and uses progressive agentic tree search with an experiment manager; also uses VLM feedback for figure refinement. | AutoPaper2's current linear stages are safer and more auditable, but future optimization should add an optional branch/frontier manager for M2/M3 idea variants and M5 figure refinement. |
| [Agent Laboratory](https://arxiv.org/abs/2501.04227) / [project page](https://agentlaboratory.github.io/) | Human-provided idea moves through literature review, experimentation, and report writing, with human feedback at stages. | AutoPaper2 already has richer M1-M6 gates; it should preserve human-review and backtrack hooks as first-class state transitions, not ad hoc comments. |
| [STORM](https://github.com/stanford-oval/storm) | Knowledge curation through internet search, perspective-guided questioning, outline generation, article generation, and citation grounding. | AutoPaper2 M1 should not only search papers; it should force broad perspective coverage and blindspot checks before gap synthesis. Current M1 search provenance and blindspot gates partially adopt this. |
| [OpenHands](https://github.com/OpenHands/OpenHands) / [Docker sandbox docs](https://docs.openhands.dev/openhands/usage/sandboxes/docker) | Generalist software agent with command-line/browser interaction and sandboxed Docker execution for isolation and reproducibility. | AutoPaper2 M3/M4 execution should remain explicit about local/ssh mode, sandbox profile, filesystem/network policies, long-run ledgers, and resume commands. Already adopted in M3S02/M4S03 gates. |
| [PaperBench](https://openai.com/index/paperbench/) / [code](https://github.com/openai/frontier-evals/tree/main/project/paperbench) | Replication benchmark decomposes research replication into hierarchical rubrics and runs rollout, reproduction, and grading in separate containers. | AutoPaper2 gates should stay rubric-driven and evidence-path based. Current G1-G6 rubric enforcement adopts this, but per-project task decomposition can still be strengthened. |
| [paper-framework-figure-studio-pro](https://github.com/c-narcissus/paper-framework-figure-studio-pro) | External style reference for academic method/framework figures. | AutoPaper2 should use it only as high-level style reference for framework/method figures, while numeric experiment plots stay code-generated via real data and Nature-style plotting principles. Current M5 gates enforce this distinction. |

## Module-by-Module Implications

| AutoPaper2 module | Current alignment | Remaining optimization |
|---|---|---|
| M1 Literature and gap synthesis | Stronger than most compared systems on source-log provenance, three-round search evidence, deep-reading fields, perspective coverage, large/middle/small gap chains, and downstream handoff. | Next M1 optimization is project-specific quality scoring for each perspective, not just coverage presence. |
| M2 Method design | Stronger than generic report-writing systems because it requires cross-domain query ledgers, candidate discovery provenance, gap-solution mapping, and experiment-plan contracts. | Add optional branch/frontier tracking inspired by AI Scientist-v2 so multiple method variants can be compared before one architecture is locked. |
| M3 Implementation and experiments | Stronger than AI Scientist-style template execution for project-specific local/ssh configuration, sandbox policies, dependency locks, long-run ledgers, baseline local verification, and runtime watchdog supervision for long-running runs. | Extend runtime lifecycle events beyond M3S04 watchdog checks to all command, retry, artifact, and approval events. |
| M4 Deep analysis | Stronger than most systems on how/where/why analysis and baseline-aware slices; closer to PaperBench-style evidence decomposition. | Add optional per-claim analysis tasks generated from M3S05 claim ledger, with one rubric row per claim. |
| M5 Writing and figures | Stronger than Agent Laboratory-style report writing because it gates pre-write evidence completeness, style distillation, anti-copy boundaries, image2 method figures, code-generated experiment plots, and final LaTeX artifact closure. | Add an optional VLM/visual-QA feedback loop for architecture/method figures, inspired by AI Scientist-v2, while preserving allowed-label constraints. |
| M6 Review and revision | Stronger than AI Scientist's single automated review path because AutoPaper2 separates harsh internal panel review, external paperreview.ai submission, review parsing, item-level revision routing, and final closure validation. | Add reviewer-persona calibration per target venue and maintain a reviewer-memory file across revision loops. |

## Optimization Backlog

| Priority | Item | Source inspiration | Proposed artifact |
|---|---|---|---|
| Done | M1 perspective coverage ledger | STORM | `M1_source_log.yaml.search_provenance.perspective_coverage` plus M1S02 `Perspective Coverage` section |
| P1 | M2/M3 branch frontier manager | AI Scientist-v2 | `state/method_frontier.yaml` with candidate IDs, scores, experiment status, and promotion decision |
| Partial | Append-only runtime event stream | OpenHands / PaperBench | `experiments/logs/runtime_events.jsonl` now records M3S04 watchdog checks; future work can generalize it to all M3S02/M4S03 command, retry, artifact, and approval events |
| P2 | Per-claim rubric expansion | PaperBench | Gate rubric generator that converts claim ledger entries into evidence rows |
| P2 | VLM figure QA loop | AI Scientist-v2 | `artifacts/generated-images/figure_qa/*.json` with label fidelity, readability, and style checks |
| P2 | Venue-calibrated reviewer memory | Agent Laboratory / AI Scientist | `knowledge/reviews/reviewer_memory.yaml` across M6 internal/external loops |

## Current Verdict

AutoPaper2 is already more conservative and auditable than the compared systems in state management, delegated execution boundaries, evidence gating, and revision routing. The main remaining gap is not another broad workflow stage; it is adding optional frontier/search and event-stream artifacts so the system can compare alternatives and preserve execution history at finer granularity.
