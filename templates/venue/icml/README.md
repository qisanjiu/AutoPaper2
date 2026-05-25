# ICML LaTeX Template

**Venue**: International Conference on Machine Learning (ICML)
**Year**: 2025
**Page Limit**: 8 pages (main body). References and appendices excluded. Camera-ready: 9 pages.

## Files

- `icml2025.sty` — Official style file
- `icml2025.bst` — Bibliography style
- `example_paper.tex` — Example/template source
- `algorithm.sty`, `algorithmic.sty` — Algorithm environments

## Usage

```latex
\documentclass{article}
\usepackage{icml2025}  % Anonymous submission (default)
% \usepackage[accepted]{icml2025}   % Camera-ready
% \usepackage[nohyperref]{icml2025} % If hyperref clashes
```

## Key Rules

- Two-column format, 10pt Times
- Abstract: 4-6 sentences, single paragraph
- Do not alter style template
- Camera-ready requires Impact Statement (unnumbered section before bibliography)

## Compilation

```bash
pdflatex paper
bibtex paper
pdflatex paper
pdflatex paper
```
