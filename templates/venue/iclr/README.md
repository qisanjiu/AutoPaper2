# ICLR LaTeX Template

**Venue**: International Conference on Learning Representations (ICLR)
**Year**: 2026
**Page Limit**: 9 pages (main text). References excluded. Rebuttal/camera-ready: 10 pages.

## Files

- `iclr2026_conference.sty` — Official style file
- `iclr2026_conference.bst` — Bibliography style
- `iclr2026_conference.tex` — Example/template source

## Usage

```latex
\documentclass{article}
\usepackage{iclr2026_conference}  % Anonymous submission (default)
% \usepackage[final]{iclr2026_conference}  % Camera-ready
```

Add `\iclrfinalcopy` before `\begin{document}` for camera-ready.

## Key Rules

- Single-column format (variant of NeurIPS format)
- Double-blind review via OpenReview
- Unlimited appendix allowed after references
- Reviewers not required to read appendix

## Compilation

```bash
pdflatex paper
bibtex paper
pdflatex paper
pdflatex paper
```
