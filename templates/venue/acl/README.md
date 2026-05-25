# ACL LaTeX Template

**Venue**: Association for Computational Linguistics (ACL) and sister conferences (EMNLP, NAACL, EACL, etc.)
**Year**: 2023 (applies to all *ACL venues)
**Page Limit**: 8 pages content (long paper). References excluded. Camera-ready: 9 pages. Short papers: 4 pages.

## Files

- `acl2023.sty` — Official style file (generic `acl.sty`)
- `acl_natbib.bst` — Bibliography style
- `acl2023.tex` — Example/template source

## Usage

```latex
\documentclass[11pt]{article}
\usepackage[review]{acl}   % Anonymous submission with line numbers
% \usepackage{acl}          % Camera-ready (final)
% \usepackage[preprint]{acl} % Non-anonymous preprint
\usepackage{times}
```

## Key Rules

- Two-column format, A4 paper, 11pt
- Abstract: ~200 words
- Must include Limitations section
- Chicago Author-Date citation style (natbib)
- No hyperref clashes: use `[nohyperref]` if needed

## Compilation

```bash
pdflatex paper
bibtex paper
pdflatex paper
pdflatex paper
```
