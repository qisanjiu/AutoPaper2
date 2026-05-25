# IEEE Transactions LaTeX Template

**Venue**: IEEE Transactions Journals (TNNLS, TIP, TSP, etc.)
**Type**: Journal
**Page Limit**: No fixed limit (varies by journal; typically 10-14 pages for regular papers)

## Files

- `IEEEtran/IEEEtran.cls` — IEEEtran document class
- `IEEEtran/bibtex/IEEEtran.bst` — Bibliography styles
- `IEEEtran/bare_jrnl.tex` — Journal paper template
- `IEEEtran/bare_conf.tex` — Conference paper template
- Various `bare_*.tex` examples for different publication types

## Usage

```latex
\documentclass[journal]{IEEEtran}  % Journal paper
% \documentclass[conference]{IEEEtran}  % Conference paper
% \documentclass[compsoc]{IEEEtran}     % Computer Society

\usepackage{cite}
\usepackage{graphicx}
```

## Key Rules

- Two-column format, US Letter
- NOT anonymous (author info required)
- IEEEtran class is on CTAN and included in most TeX distributions
- Use `\IEEEauthorblockN` and `\IEEEauthorblockA` for authors

## Compilation

```bash
pdflatex paper
bibtex paper
pdflatex paper
pdflatex paper
```

## Journal-Specific Notes

Different IEEE Transactions have slightly different requirements:
- Page limits vary (check target journal CFP)
- Some require special sections (e.g., TNNLS requires no special sections)
- Color figures: check if journal charges for color printing
