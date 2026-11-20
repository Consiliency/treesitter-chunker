# Call-resolution fixtures: provenance

These fixtures back the opt-in scope-aware call resolution work
(treesitter-chunker#682, `plans/detailed-scoped-call-resolution-682.md`).
PR 0 adds them with no product change. `provenance.json` records the sha256
of every copied or authored file, and
`tests/test_call_resolution_fixture_provenance.py` checks each file against it.

| Directory | Source | How it was verified |
| --- | --- | --- |
| `greenfield-r1/<tree>/` | Greenfield's 16 round-1 probe trees (`gf48-probes/r1/trees`, ViperJuice/greenfield#48) | Copied byte-for-byte, then checked against the 18 `r1/trees/` lines of `gf48-probes/evidence-manifest.sha256` (sha256 `40575a9bd9612fd1d307dda1e8e94f0ca7af5dff19659ca45cbb7fad649a1e46`). Those lines are kept in `provenance.json`. Greenfield confirmed the trees are synthetic and safe to commit publicly. |
| `probe-r9/` | The executive's probe tree (`evidence/treesitter-chunker/ambiguity-scope-20261119/r9probe`), original layout | All ten files match the hashes in plan section 10.1. The evidence `SHA256SUMS` (sha256 `e1e0b01cba9771440c3b9b462c276838b3f6a6f9b1769962adf553d9f6aa250e`) covers only the outputs and `r9probe_run.py`, so the plan computed the file hashes itself. |
| `authored/<case>/` (106 trees) | The plan author's scratch directory | Copied byte-for-byte. The president's re-check ran main on this same set of trees and confirmed every Today cell. |
| `authored/py-nonlocal-rebind/`, `authored/py-ancestor-module-shadow/` | Written in PR 0 from the plan's section 10.4 descriptions (the Codex review of #683 added them) | No earlier copy existed. Their Today cells were derived on main and match the plan. |

Other files:

- `expected/<tree>.json`: oracle tables, one per tree. In PR 0 each call
  records only its `today` edge: the off-mode resolution, the candidates as
  `file:line:qualified_name`, and the candidate IDs. All of these were derived
  by running main. Later PRs add the expected outcome for each mode by hand,
  and the `pr` field.
- `off_mode_baseline/`: canonical off-mode documents for every run (plan
  section 11.2). `scripts/capture_call_resolution_off_baseline.py` checks
  them by default and rewrites them only with `--write`. The sha256 of
  `MANIFEST.sha256` is pinned in `tests/test_call_resolution_today.py`.

Extraction roots: each tree is its own root. The probe also has a Python run
rooted at `probe-r9/py/`. `ts-language-filter` also has a run with
`language="typescript"`.

**Byte stability.** `.gitattributes` marks this directory `-text`, so Git
never rewrites line endings. The tool exclusions are pytest `--ignore`, the
Black and Ruff excludes and `MANIFEST.in`. Together they keep these files out
of test collection and linting, but in the sdist.
