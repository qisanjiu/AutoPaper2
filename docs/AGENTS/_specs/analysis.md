# Analysis Agent Compact Spec

## Stages
- `M3S04 Result Validation`: verify result integrity, seed limitations, data quality, stopping reason, evidence level, and final decision `KEEP|FIX|BACKTRACK` with repair fields when needed.
- `M4S01 Findings Audit`: consolidate main results, negative/partial findings, unexpected observations, claim candidates, and analysis campaign draft.
- `M4S02 Deep Analysis Design`: design ablation, mechanism, robustness/boundary, failure, and efficiency slices. Each claim-carrying slice needs baseline inclusion or explicit waiver and literature/database basis.
- `M4S04 Analysis Results`: integrate M4S03 evidence into claim ledger, insight articulation, evidence usability, limitations, and downstream writing guidance.
- `M5S01 Pre-Write Audit`: check M1-M4 completeness, contribution support, evidence/narrative/citation gaps, style/layout references, data consistency, writing risks, and go/no-go.

## Evidence Rules
- Distinguish correlation from causality; do not overstate single-seed or smoke-level evidence.
- Negative, failed, partial, or unusable evidence must be labeled and cannot support main claims.
- Robustness/performance/boundary claims require baseline comparison unless explicitly downgraded.
- Every downstream writing claim must cite M3/M4 evidence paths and evidence status.

## Backtrack Rules
- `FIX`: bounded current-stage repair.
- `BACKTRACK`: upstream design/experiment/data/baseline issue. Include full repair fields and rerun scope.
- Never write KEEP to force progress when evidence contradicts the claim.
