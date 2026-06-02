# Method Agent Compact Spec

## Stages
- `M2S01 Cross-Domain Search`: search same-modality/different-task, same-task/different-modality, shared-principle, and similar-structure sources. Write candidate pool and `M2_source_log.yaml` with search statistics, query ledger, dimensions, target gaps, mechanisms, adaptation potential.
- `M2S02 Method Inspiration`: map multiple papers into transferable mechanisms; state source problem, target problem, what transfers, what must change, and why unmodified transfer is insufficient.
- `M2S03 Method Architecture`: define notation, problem, components, data/control flow, M2S02 mapping, design decisions, downstream implementation notes.
- `M2S04 Algorithm & Theory`: write algorithm steps/pseudocode, complexity, assumptions, proof sketches if claimed, comparison to existing work, and honesty statement.
- `M2S05 Experiment Setup`: select datasets, baselines, metrics, splits, seeds, fairness rules, resource needs, and experiment targets tied to M1 hypotheses.
- `M2S06 Full Experiment Plan`: sequence experiments, branch/failure logic, success/failure criteria, risk plan, resource budget, and report blueprint.

## Non-Negotiable Checks
- Baselines must be runnable or have a documented acquisition/verification path; no unsupported paper-value-only baseline.
- Each method component must trace to a gap/hypothesis and have a planned validation or ablation.
- Migration must be honest: no novelty claim from a mechanism already covered in M1 unless the difference is explicit.
- Experiment plan must include at least main comparison, component/ablation, and robustness or boundary analysis unless explicitly justified.
- If required evidence is missing, request backtrack rather than inventing method/theory/experiment claims.
