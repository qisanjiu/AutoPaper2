# NeurIPS LaTeX Template

**Venue**: Conference on Neural Information Processing Systems (NeurIPS)
**Year**: 2025
**Page Limit**: 9 pages (main content). References, checklist, and appendices excluded.

## Files

- `neurips_2025.sty` — Official style file
- `neurips_2025.tex` — Example/template LaTeX source

## Usage

```latex
\documentclass{article}
\usepackage{neurips_2025}  % Anonymous submission (default)
% \usepackage[final]{neurips_2025}   % Camera-ready
% \usepackage[preprint]{neurips_2025} % arXiv preprint
% \usepackage[nonatbib]{neurips_2025} % If natbib clashes
```

## Key Rules

- Do NOT tweak the style file (grounds for rejection)
- Double-blind: omit author names/affiliations in submission
- Mandatory paper checklist included in style file
- Self-cite your own work in third person

## Compilation

```bash
pdflatex paper
bibtex paper
pdflatex paper
pdflatex paper
```
