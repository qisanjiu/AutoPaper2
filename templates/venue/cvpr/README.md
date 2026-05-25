# CVPR LaTeX Template

**Venue**: IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)
**Year**: 2026
**Page Limit**: 8 pages excluding references.

## Files

- `cvpr.sty` — Official style file
- `ieeenat_fullname.bst` — Bibliography style
- `main.tex` — Example/template source
- `sec/*.tex` — Example sections

## Usage

```latex
\documentclass[10pt,twocolumn,letterpaper]{article}
\usepackage[review]{cvpr}   % Anonymous submission with line numbers
% \usepackage{cvpr}          % Camera-ready
% \usepackage[pagenumbers]{cvpr} % arXiv preprint with page numbers
```

## Key Rules

- Two-column IEEE format, US Letter
- Double-blind review
- Supplementary materials allowed (separate file)
- Figures: vector formats (.eps/.pdf) for plots, .png for raster

## Compilation

```bash
pdflatex paper
bibtex paper
pdflatex paper
pdflatex paper
```
