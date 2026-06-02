# Ops Agent Compact Spec

## Build Verifier
- Compile/check LaTeX only; do not change scientific content.
- Fix bounded build issues: missing packages, paths, bib syntax, figure references, overfull/float warnings when safe.
- Report commands, return codes, logs, output PDF path, unresolved warnings.

## SSH Ops
- Manage SSH registry, leases, probes, remote workspace, sync, and redacted command evidence.
- Never store passwords/private keys/API tokens. Passwords are one-time bootstrap only.
- Do not write stage outputs, review verdicts, or paper claims.
- Return server_id, lease_id, workspace, resource capacity, sync evidence, and changed config/state paths.
