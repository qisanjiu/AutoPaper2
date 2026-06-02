# Writing Agent Compact Spec

## Stages
- `M5S02`: paper outline, claim budget, terminology, section plan, Style & Layout Profile, Figure Style Profile, and figure generation plan.
- `M5S04`: methodology section, problem formulation, method/algorithm, architecture/mechanism figures, allowed labels only from upstream method docs.
- `M5S05`: experiments/results section grounded in M3 evidence, datasets, baselines, metrics, provenance, tables/plots from data and scripts.
- `M5S06`: analysis/discussion, ablations/mechanisms/robustness/failures/limitations from M4 evidence.
- `M5S03`: introduction and related work after method/results/analysis are locked; story must match actual evidence.
- `M5S07`: abstract and conclusion with numeric consistency checks.
- `M5S08`: assemble `artifacts/paper.tex`, refs, figures, and compile `paper.pdf` without inventing new science.
- `M5S09`: full polish from `paper.tex`/`paper.pdf`, narrative coherence, promise-to-evidence consistency, recompile.

## Writing Rules
- Do not invent results, citations, datasets, baselines, metrics, or components.
- Keep claims within evidence level and limitations.
- Architecture/mechanism figures must record backend, prompt/script, output path, caption, and allowed labels. Experimental plots must be code/data generated.
- Never copy exemplar paper wording or distinctive layout; distill high-level style only.
- If evidence is missing, write a repair request/backtrack record rather than filling text.
