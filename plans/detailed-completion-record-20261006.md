---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_release_hygiene_policy.py -q"
---

# Reconcile accepted cleanup records

## Task

Reconcile completed treesitter-chunker#373, treesitter-chunker#381 and
treesitter-chunker#383 into the manifest and current inventory. This is metadata
work; native acceptance and the rejected CLEANUP transaction interface stay held.

## Changes

Own this plan, plans/manifest.json and
docs/development/backlog-inventory-20261006.md. Use the typed manifest lifecycle
API; append reconciliation events without rewriting historical lifecycle rows.
Mark accepted static/cache-option/phase-metadata detailed plans completed.
The phase-metadata plan's missing execution event is reconciled explicitly now,
not represented as a historical event. Preserve all unrelated entries, phase
fields, retired proposal metadata and orphaned transaction status.

Update the inventory against a fresh GitHub open-issue snapshot: remove closed
treesitter-chunker#324, treesitter-chunker#369 and treesitter-chunker#375 from the
open map; add separate treesitter-chunker#384 and treesitter-chunker#386 once.
Record the accepted PR/evidence links and publishing hold under agent-harness#910.
Historical snapshots remain historical; the newer checkpoint supersedes them.

## Verification

- Validate every manifest entry, not just structural validity.
- Compare untouched lifecycle histories to the starting Git version.
- Compare the open-map set with the captured GitHub issue snapshot; no duplicates.
- uv run --locked --all-extras pytest tests/test_release_hygiene_policy.py -q
- Strict MkDocs build into a temporary site directory.

No product behavior changes: the accepted original product runners and mutation
evidence remain linked to their actual heads. No new percentage gate or IF claim.

## Acceptance criteria

- [ ] Three accepted detailed entries are completed with preserved history;
  unrelated entries and the held CLEANUP phase remain unchanged.
- [ ] Open-map rows match the current GitHub issue set exactly once; accepted
  closures and newly discovered defects have qualified evidence references.
- [ ] Hygiene and strict docs pass; publication waits for supported recovery.
