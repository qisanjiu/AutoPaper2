# arXiv LaTeX Template

**Venue**: arXiv Preprint Server
**Type**: Preprint
**Page Limit**: No fixed limit

## Files

- `arxiv.sty` — arXiv style file (based on NeurIPS styling, adapted for preprints)
- `template.tex` — Example/template source

## Usage

```latex
\documentclass{article}
\usepackage{arxiv}

\title{Your Paper Title}
\author{Author Name \\ Institution}

\begin{document}
\maketitle

\begin{abstract}
...
\end{abstract}

\section{Introduction}
...

\bibliographystyle{unsrt}
\bibliography{references}

\end{document}
```

## Key Rules

- **Non-anonymous**: Must include real author names and affiliations
- No page limit
- 10-14pt font, single spaced, minimum 1" margins
- No line numbers, watermarks, or advertisements
- Figures: `.pdf`, `.png`, `.jpg` (PDFLaTeX mode)
- arXiv does NOT run `bibtex` — you must include `.bbl` content inline or use `biblatex` with `biber`

## Compilation

```bash
pdflatex paper
bibtex paper
pdflatex paper
pdflatex paper
```

> **Note for arXiv submission**: arXiv's TeX environment does not run `bibtex`. Before uploading, run `bibtex` locally and copy the content of the generated `.bbl` file into your `.tex` file (replacing `\bibliography{}`).
