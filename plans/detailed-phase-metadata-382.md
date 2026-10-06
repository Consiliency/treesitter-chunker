# Detailed plan: normalize phase manifest metadata

## Task and research

Repair treesitter-chunker#382 independently of product code. On main 2465263f,
the v3-SAFELOAD and v3-CLEANUP phase rows contain detailed-only summary/count
fields. The installed manifest entry validator requires those fields to be null.
Container structural validity alone does not establish entry validity.

## Changes and documentation impact

- Modify only plans/manifest.json using the supported typed append_entry API.
  Preserve the original summary/count in an explicitly historical extension;
  set the two phase-only rows' summary/count fields to null. Preserve every
  lifecycle event, all other rows and all authority/interface metadata.
- Preserve CLEANUP's orphaned state, empty active lane/gate declarations and
  rejected proposal history. Produce no IF and reopen no design review.
- This plan is a control artifact. No public API or release behavior changes,
  so public documentation and CHANGELOG need no update.

## Dependencies, verification and acceptance

1. Capture both failing entry validations and their existing lifecycle hashes.
2. Apply the two typed row replacements; register this detailed plan separately.
3. Validate all manifest entries, not just the container; compare both lifecycle
   hashes and every unrelated row before and after. Check the held state.
4. Publish a draft via the supported adapter, obtain the standing manual panel
   code review with tool-enabled local pointers, merge when accepted, comment
   and close treesitter-chunker#382, then prune the clean merged worktree.

Verification: use the installed Agent Harness Python to call
`validate_manifest(Path("plans/manifest.json"))`; assert structural_valid and
every entry.valid. Compare canonical JSON hashes of the two lifecycle arrays
and each unaffected row against origin/main. Run git diff --check. No product
test, parser pin, golden, consumer lock or protected ledger is changed.

- [ ] Every manifest entry validates; both new phase rows have null summary/count.
- [ ] Original values remain historical metadata; lifecycle and unrelated row
  hashes remain unchanged, apart from this plan's new entry.
- [ ] CLEANUP stays orphaned with no active lanes/gates; no execution IF is claimed.
