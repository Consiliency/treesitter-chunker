# Documentation notice repair for treesitter-chunker#371

## Changes

Restore the existing release-hygiene policy's required maintainer notice in
docs/development/DEPLOYMENT.md. Owned paths: that document and this plan.
No policy assertions or runtime behavior change.

## Verification

Run the locked release-hygiene tests and strict MkDocs build to a temporary site.
Review the two-file diff; require hosted checks before merging.

## Acceptance criteria

The required notice is present near the top, all nine hygiene tests pass, and
strict documentation build passes. Comment on and close treesitter-chunker#371
only after merge; prune the clean merged worktree.
