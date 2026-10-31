# Backlog Decisions — Roadmap v4

Owner decisions for the decision points in `specs/phase-plans-v4.md`
(roadmap treesitter-chunker#533). Each record repeats the owner's choice as
posted in the linked issue comment. No decision here was inferred by an agent.

Produced by phase OWNERDEC (IF-0-OWNERDEC-1 to IF-0-OWNERDEC-4). D5 is listed
for reference only; SETTINGS consumes it.

| ID | Issue | Chosen option | Owner attribution | Date |
|---|---|---|---|---|
| D1 | treesitter-chunker#357 | (c) both | [issuecomment-6549421019](https://github.com/Consiliency/treesitter-chunker/issues/357#issuecomment-6549421019) (ViperJuice) | 2026-10-31 |
| D2 | treesitter-chunker#453 | (b) namespaced caller key | [issuecomment-6549421303](https://github.com/Consiliency/treesitter-chunker/issues/453#issuecomment-6549421303) (ViperJuice) | 2026-10-31 |
| D3 | treesitter-chunker#471 | (a) CR→LF with byte-offset map | [issuecomment-6549421467](https://github.com/Consiliency/treesitter-chunker/issues/471#issuecomment-6549421467) (ViperJuice) | 2026-10-31 |
| D4 | treesitter-chunker#516 | (a) implement | [issuecomment-6549421600](https://github.com/Consiliency/treesitter-chunker/issues/516#issuecomment-6549421600) (ViperJuice) | 2026-10-31 |
| D5 | treesitter-chunker#507 | Audit first, then the owner flips the setting | [issuecomment-6549421775](https://github.com/Consiliency/treesitter-chunker/issues/507#issuecomment-6549421775) (ViperJuice) | 2026-10-31 |

## D1 — First-use download policy (treesitter-chunker#357) — IF-0-OWNERDEC-1

Decision: do both. Add a bounded, verified prewarm route: a command or API
that downloads the grammar bundle ahead of time and checks its SHA-256 against
the official manifest. Also propagate a configurable download deadline, with
an actionable error and recovery guidance when the deadline is hit. Keep the
parser execution deadline separate from the download deadline.

Consumer: FOLLOWUP lane SL-dl.

## D2 — GraphML caller-label interop (treesitter-chunker#453) — IF-0-OWNERDEC-2

Decision: use a namespaced key. Export the caller label under a distinct
GraphML `attr.name` (for example `caller_label`, following the existing naming
conventions), and keep `label` for the structural label, so a NetworkX import
exposes both. Record the change in the changelog and the GraphML docs, and test
it with a real NetworkX import.

Consumer: FOLLOWUP lane SL-gml (after GRAPHML).

## D3 — CR-only Python input (treesitter-chunker#471) — IF-0-OWNERDEC-3

Decision: convert CR to LF with a byte map. Normalize CR-only line endings to
LF for parsing, and keep an exact mapping back to the original raw byte
offsets, so reported rows and lines are correct and byte spans still point at
the physical bytes. Verify it with real fixtures and independent raw-byte and
row oracles, for both the regular and streaming paths.

Consumer: FOLLOWUP lane SL-cr.

## D4 — Outer call sites for callable-return expressions (treesitter-chunker#516) — IF-0-OWNERDEC-4

Decision: implement it. Emit the outer call site for callable-return
expressions as its own unresolved site, with truthful raw callee bytes, span,
owner and identity, and keep the inner site. Intentional Boundary IR and golden
changes go in the same reviewed PR. They are regenerated with the project
tooling, never hand-edited, and bound to the locked parser stack.

Consumer: FOLLOWUP lane SL-call.

## D5 — Repository default Actions permissions (treesitter-chunker#507)

Decision: audit first, then flip. Add explicit least-privilege `permissions:`
to every workflow and job, granting write scopes only where publishing or
another write is required (CIFAST lane SL-perm). After that PR merges, the
owner switches the repository default to read-only. Agents do not change the
repository setting.

Consumer: CIFAST SL-perm (source audit), then SETTINGS (the owner's action).
