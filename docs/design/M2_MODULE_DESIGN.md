# M2 Module Design — Current Topology

M2 is a five-stage method-design module. It ends at `M2S05` and Gate G2.

## Stage Flow

```text
M2S01 Cross-Domain Search
  -> M2S02 Method Inspiration
  -> M2S03 Method Architecture
  -> M2S04 Algorithm & Theory
  -> M2S05 Experiment Setup + Metric Protocol + M2-to-M3 Handoff
  -> G2
  -> M3S01 Main Experiment Design
```

## Boundary

M2 must not produce a full experiment schedule. `M2S05` selects candidate datasets, candidate external baselines, metrics, splits, fairness rules, resource assumptions, and writes `knowledge/M2/M2S05_metric_protocol.yaml`.

`M3S01` is responsible for the concrete main experiment design: dataset/scenario/split, `metric_protocol_id`, external baseline reference values, value sources, and proposed-method same-condition protocol.

M4 is responsible for ablation, mechanism, robustness, boundary, failure, and efficiency analysis design. These analyses must not be planned as M3 baselines.

## Canonical Outputs

| Stage | Output |
|-------|--------|
| M2S01 | `knowledge/M2/M2S01_cross_domain_search.md` |
| M2S02 | `knowledge/M2/M2S02_method_inspiration.md` |
| M2S03 | `knowledge/M2/M2S03_method_architecture.md` |
| M2S04 | `knowledge/M2/M2S04_algorithm_theory.md` |
| M2S05 | `knowledge/M2/M2S05_experiment_setup.md` and `knowledge/M2/M2S05_metric_protocol.yaml` |
| Handoff | `knowledge/handoff_M2_M3.md` |

## Review And Gate

| Stage | Reviewer |
|-------|----------|
| M2S01 | `m2_search_quality` |
| M2S02 | `m2_migration` |
| M2S03 | `m2_design_review` |
| M2S04 | `m2_design_review` |
| M2S05 | `m2_experiment_design_review` |

G2 evaluates method logic, method soundness, novelty, and whether `M2S05` provides enough setup for `M3S01` to design the main experiment without inventing metrics, datasets, or baseline scope.
