---
automation:
  suite_command: 'uv run --with toml --all-extras pytest -q tests/test_canon_vectors.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_golden_snapshots.py && uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site && uv run --all-extras black --check chunker/ cli/ tests/ scripts/ && uv run --with toml --all-extras python scripts/run_ci_smoke.py'
---

# Detailed plan: Python 3.14 wheel-only Unicode 16 dependency closure

## Task

Implement Consiliency/treesitter-chunker#102 in a subsequent authorized execution.
Publish a compatible patch whose runtime dependency closure installs from wheels on
CPython 3.14/Linux x86_64 and whose canonicalization retains exact Unicode 16.0.0
behavior. This change is planned only: implementation, publication, and consumer
lock changes have not occurred.

Plan Mode was not active. The requested deliverable is this plan; no verification
commands were run. Research base: fb3cd7da242120cafcb730d9c2a158a87c61892a.

## Research summary

The unconditional unicodedata2==16.0.0 dependency appears in pyproject.toml and
uv.lock. The lock contains CPython wheels through 3.13 and an sdist.
chunker/boundary/_canon.py imports only that backport and checks major/minor.
tests/test_canon_vectors.py exercises frozen canonical bytes and digests.
The release workflow validates source on Python 3.11–3.13 but its fresh wheel
installation runs only on 3.12 and does not prohibit source builds.

Python 3.14 documents Unicode 16.0.0, but runtime table versions must be checked:
https://docs.python.org/3.14/library/unicodedata.html .
Distribution metadata: https://pypi.org/pypi/unicodedata2/16.0.0/json .

The local vendored module identifies canon v1 and an upstream source SHA-256.
Current Consiliency/spec main has canon v2, removes NFC from canonicalization,
and changes the digest domain. Do not refresh from upstream main for this fix.
The bounded implementation explicitly documents a local backend-selection patch
while preserving the original provenance and all v1 encoding behavior.

## Changes

### chunker/boundary/_canon.py (modify)

- Backend loading: prefer stdlib unicodedata only when its actual
  unidata_version equals exactly "16.0.0"; otherwise load unicodedata2 and
  require its full version to equal exactly "16.0.0".
- Missing or mismatched fallback must fail closed with actionable diagnostics.
  Do not infer table versions from sys.version_info.
- Preserve _ACTUAL_UNICODE major/minor compatibility if needed, but compute it
  only after the exact-version assertion.
- Document the narrow downstream loading adaptation; remove inaccurate verbatim
  and unconditional-backport claims. Retain the original upstream source hash
  labeled as provenance, not a checksum of the adapted file.
- Leave all serialization algorithms and existing vectors untouched.

Frozen vocabulary inspected in the current source:

```python
PROFILES = ("semantic-content", "run", "artifact-byte", "certificate")
_DOMAIN_PREFIX = "spec-canon:v1:"
```

No new vocabulary, digest domain, Boundary IR schema, or normalization behavior
is introduced. Preserve key NFC normalization and collision rejection.

### pyproject.toml (modify)

- Set the runtime requirement to:

```toml
"unicodedata2==16.0.0; python_version != '3.14' or platform_python_implementation != 'CPython'",
```

- Explain the stdlib exact-version gate in the dependency comment.
- Add the Python 3.14 classifier after verification.
- Retain fallback metadata for older, future, and alternate interpreters.
  Python 3.15 wheel availability is outside this issue's promise.
- Preserve unrelated dependency ranges and the ABI-paired grammar/runtime pins.

### uv.lock (modify through uv lock)

Regenerate without broad upgrades, retaining backport entries for other
interpreters. Review the project requirement marker and reject unrelated churn.
At release time synchronize the project version normally.

### tests/test_canon_vectors.py (modify)

- Update provenance wording and assert full backend version "16.0.0".
- Load the module in isolated namespaces with controlled imports, avoiding
  global reloads or sys.modules contamination.
- Test exact stdlib success without any backport import; mismatching older/newer
  stdlib plus exact backport success; missing backport failure; and 15.x, 17.x,
  and 16.0.1 backport rejection.
- Test dependency marker evaluation for CPython 3.11–3.15 and an alternate
  interpreter. Inspect built metadata separately during package acceptance.
- Keep existing canonical byte/digest vectors unchanged.

### .github/workflows/release.yml (modify)

Extend installed-wheel acceptance to CPython 3.14, retaining existing 3.12
acceptance and the full 3.11–3.13 source matrix. Install the complete runtime
closure with hash checking and --only-binary=:all: into a fresh environment.
Run outside the checkout; assert the imported package is in site-packages,
the chosen Unicode tables are exactly 16.0.0, and unicodedata2 is absent on
CPython 3.14. Retain existing parser checks.

Run the actual installed treesitter-chunker chunk CLI against a Python fixture.
Parse JSON and assert a nonempty Python function_definition chunk containing
the expected function. process_file catches ChunkerError and returns [], so
exit status alone is insufficient. Language-pack may fetch grammar artifacts;
prefetch Python or allow that normal fetch independently of dependency install.

### specs/active/release-process-spec.md and CHANGELOG.md (modify)

Document the focused Python 3.14 wheel-only release gate and unchanged Unicode
16 canonicalization contract. Record the fix under the next patch release.

### Release bookkeeping (subsequent execution)

Use the next available patch version, nominally 5.1.1, after checking release
state. Synchronize pyproject.toml, generated chunker/_version.py, and lock project
version according to existing packaging conventions. Publish only through
.github/workflows/release.yml with a matching version tag.

## Documentation impact

The release spec and changelog describe the packaging guarantee. No public
Boundary IR schema or serialization API change is intended. Do not adopt canon
v2, change fixture expectations, or regenerate Boundary IR goldens.

## Dependencies and order

1. Implement backend selection, metadata, regression tests, and documentation.
2. Regenerate the lock and inspect every changed dependency.
3. Run focused tests on Python 3.11, 3.12, 3.13, and 3.14, then local CI checks.
4. Build and inspect the wheel; demonstrate its full wheel-only dependency closure.
5. Complete required local/platform release preflights.
6. Publish through the established release workflow.
7. Repeat acceptance against the published artifact.
8. Perform consumer lock acceptance in separately authorized Consiliency/dotfiles
   work. Do not treat package acceptance as permission to deploy a shared host.

## Verification

The automation.suite_command above is the local implementation gate. Also run
each interpreter's focused gate, replacing VERSION with 3.11, 3.12, 3.13, and 3.14:

```sh
uv run --python VERSION --with toml --all-extras pytest -q tests/test_canon_vectors.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_golden_snapshots.py
uv run --all-extras python -m build
uv run --all-extras python -m twine check dist/*
```

Inspect the built wheel METADATA and evaluate its Requires-Dist marker for the
same interpreter cases. On real CPython 3.14/Linux x86_64, resolve all dependencies:

```sh
python -m pip download --only-binary=:all: --dest WHEELHOUSE PATH_TO_BUILT_WHEEL
```

Export hashed runtime requirements with
uv export --locked --no-dev --no-emit-project --format requirements-txt, append
the built wheel with its computed SHA-256, and download that exact set:

```sh
python -m pip download --only-binary=:all: --require-hashes -r HASHED_REQUIREMENTS --dest WHEELHOUSE
python -m pip install --no-index --find-links WHEELHOUSE --only-binary=:all: --require-hashes -r HASHED_REQUIREMENTS
python -m pip check
treesitter-chunker chunk FIXTURE.py --lang python --json
```

Use a second clean environment for installation, remove compiler executables
from PATH, and capture logs. Assert there are only wheels in the downloaded
closure and no build/backend execution. Parse CLI JSON and verify the expected
function chunk. PATH_TO_BUILT_WHEEL, WHEELHOUSE, HASHED_REQUIREMENTS, and FIXTURE.py
are executor-created absolute artifact paths, not repository additions.

Run the standing Windows preflight from AGENTS.md before pushing configuration
changes, plus required leno/macmini and full release validation. Record the
commit under test: the standing Windows main-branch command alone does not prove
the candidate's new code. Do not run tests during this planning-only change.

Repeat wheel-only download, hash-install, Unicode assertion, and CLI acceptance
for treesitter-chunker==RELEASE_VERSION from PyPI. Consumer acceptance must use
the complete regenerated Consiliency/dotfiles reviewed lock on fresh CPython
3.14/Linux x86_64 with no compiler in PATH. Preserve its tsc alias handling.
The issue reference Consiliency/dotfiles#7 is a maintenance context; inspect the
actual consumer branch/PR rather than assuming main already contains chunker.

## Acceptance criteria

- [ ] Exact Unicode 16.0.0 backend selection and fail-closed rejection pass on
  older and newer simulated databases: tests/test_canon_vectors.py.
- [ ] Frozen vectors and Boundary IR goldens remain identical on Python
  3.11–3.14: the focused per-interpreter pytest commands above.
- [ ] Published metadata resolves the complete CPython 3.14/Linux x86_64 closure
  without sdists: pip download --only-binary=:all: against RELEASE_VERSION.
- [ ] Fresh complete consumer hash-lock installation works without compiler or
  build backend: offline wheel-only pip install --require-hashes plus pip check.
- [ ] Installed CLI emits the expected nonempty Python function chunk:
  treesitter-chunker chunk FIXTURE.py --lang python --json plus JSON assertion.
- [ ] Local CI, platform gates, and the existing release matrix pass: suite command
  and recorded release workflow results.

## Evidence and closeout

The executor must write artifacts/issue-102-acceptance.json containing commit,
release version, wheel SHA-256, parsed dependency metadata, interpreter/platform,
actual backend/table version, command exit codes, wheel-only and hash-install
logs, and CLI JSON assertion results. Record separately the consumer lock commit
and acceptance result. An executor closeout may mark an operational item accepted
only after a runner-stamped amendment references that artifact and its SHA-256;
proxy evidence requires a plan amendment before downstream reliance.

Main risks are a hidden second CPython 3.14 wheel gap and inadvertent canon v2
adoption. A second dependency gap requires explicit evidence and a bounded plan
amendment, not an unreviewed global dependency upgrade. No goldens, digest domains,
grammar pins, shared-host deployment, or consumer locks change in this plan PR.

