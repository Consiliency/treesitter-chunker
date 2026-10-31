# Cache transaction contract

> Maintainer/internal documentation. This page is intentionally omitted from public navigation.

Status: **proposed interface freeze IF-0-TXNSPEC-1** (roadmap
`specs/phase-plans-v4.md`, Phase 3 TXNSPEC). It has not been accepted yet.
This document changes no runtime behavior, and no consumer is migrated here.
The helper module `chunker/grammar_management/_transactions.py` does not exist
yet. Its signatures are frozen in [Signatures](#signatures), and TXN lane
SL-cache creates the module in its first PR. Phase TXN implements the contract for
treesitter-chunker#370, treesitter-chunker#323 and treesitter-chunker#363.
It succeeds the rejected treesitter-chunker#364 CLEANUP design. Wherever the
two differ, this document takes precedence. The successor deliberately makes
the design narrower rather than proposing that general design again.

Forward publication and the restore path use IF-0-HOTFIX-1
(treesitter-chunker#162) unchanged. The signature is cited at
treesitter-chunker#539 head `7710fb7c`; see
[Restore publication](#restore-publication-if-0-hotfix-1).

## Scope

**Consumers.** The contract covers exactly three consumers, all in
`chunker/grammar_management/core.py`:

| Consumer | Issue | Participating functions after TXN |
|---|---|---|
| Validation-record JSON | treesitter-chunker#370 | `GrammarValidator._load_validation_cache`, `GrammarValidator._cache_validation_result`, the validation-cache pruning block of `GrammarManager.cleanup_cache` |
| Cache entry writer/pruner | treesitter-chunker#323 | Writers: `GrammarInstaller._download_grammar`, `GrammarInstaller._build_grammar`, the build helpers they call. Removers: `GrammarInstaller._cleanup_cache`. Pruner: `GrammarManager.cleanup_cache` / `GrammarManager._cleanup_directory` |
| Installer rollback point | treesitter-chunker#363 | `GrammarInstaller.install_grammar` failure exits, `GrammarInstaller._create_rollback_point`, `GrammarInstaller._perform_rollback`, `GrammarInstaller._install_grammar_file`, `GrammarInstaller._save_installation_info` |

**Non-participants.** These paths do not follow the protocol. No TXN PR may
claim concurrency safety for them:

| Path | Why it is outside the contract | Consequence |
|---|---|---|
| `ComprehensiveGrammarCLI._cleanup_cache_fallback` (`cli.py`) | Runs only when the core manager is unavailable. It is not one of the three consumers. | Running it concurrently with a participating writer on the same root is unsupported. It keeps its static no-follow behavior from treesitter-chunker#324. Routing it through the helper is a separately filed follow-up. The helper has no core import, so it can be routed later. |
| `config.CacheManager` and `DirectoryManager.cleanup_empty_directories` (`config.py`) | They use a different root (`directory_manager.get_directory("cache")`). Size, clear and empty-sweep semantics are not needed by any consumer. | They are not protected. With the default layout, their namespaces do not overlap core namespaces. |
| `chunker/_internal/cache.py` (AST cache), `chunker/boundary/cache.py` | Roadmap non-goals. HOTFIX owns the AST cache. | None |
| `UserGrammarTools` (`chunker/_internal/user_grammar_tools.py`) | It writes `~/.cache/treesitter-chunker/build`, which is not a core namespace. It publishes through IF-0-HOTFIX-1. | None for this contract |
| Older package versions, external tools, and hostile processes running as the same user | They do not take the lock. | Stop them before using a root with a participating version. |

**Concurrency scope.** One host only. Participating threads and processes on
that host share one cache root on a local filesystem. Cross-host sharing and
network filesystems (NFS, SMB/CIFS, sshfs and similar) are unsupported. The
helper does not try to detect them. This is roadmap Assumption 5. If review
rejects this scope, decision S-TXN applies.

**Supported platforms.**

- Linux and macOS: `fcntl.flock`, `O_NOFOLLOW`, and `dir_fd` operations.
- Windows on NTFS: `msvcrt.locking`, with reparse-point checks.

Python 3.12 is the floor. Release checks also cover 3.14.

If a required primitive is unavailable, the operation raises
`CacheTransactionError` and changes nothing. Examples are a lock call that
fails with `ENOLCK` or `EOPNOTSUPP`, and a missing `DirEntry.is_junction`. It is
never a silent pass.

## Roots, lock file and control area

**Root.** The root is the `cache_dir` given to `GrammarValidator`,
`GrammarInstaller` and `GrammarManager` (default `~/.cache/treesitter-chunker`).
All three already share it.

The operator trusts the root path as given, including symlinks in the root
path and in its ancestors. Alias layouts such as macOS `/var` are therefore
allowed. Each operation captures the root's identity once (`st_dev`,
`st_ino`). On POSIX it also holds an open directory descriptor. Every
operation works relative to that identity, so it never switches roots midway.
Everything the helper opens or creates below the root is subject to
no-follow containment (see [Containment rules](#containment-rules)).

**Lock file.** Each root has one lock file, `<root>/.txn.lock`.

- It is a regular file, created on first use with mode `0o600` and one byte of
  content.
- Participants never unlink, truncate or rename it. It carries no state.
- POSIX: an exclusive `fcntl.flock` on the descriptor.
- Windows: `msvcrt.locking` on byte 0, with the handle kept for the whole
  hold.
- No shared mode exists. Readers of protected files take the same exclusive
  lock. This keeps a Windows reader handle from making `os.replace` fail.

**In-process exclusion.** A process-local reentrant lock, keyed by the lock
file's `(st_dev, st_ino)`, serializes threads within one process before the OS
lock is taken. Two spellings of one root therefore share both locks. Nested
acquisition on the same root reuses the held lock and opens no second
descriptor.

An operation touches exactly one root. It never holds two roots' locks.

**Acquisition.** Acquisition is bounded by `timeout` (default
`DEFAULT_LOCK_TIMEOUT = 30.0` seconds). It uses non-blocking attempts with a
short backoff. A timeout raises `CacheLockTimeoutError`. The caller then reports an
actionable error and performs no write, prune or restore.

The timeout bounds waiting; it is not a correctness deadline. Tests must not
assert on its wall-clock behavior.

**Lock scope.** The lock is held only for short critical sections:

- a JSON read or update;
- one prune candidate's re-check and retirement;
- one publication rename;
- creating a rollback point;
- one restore.

It is **never** held across `git`, `tree-sitter`, `gcc`, `make` or any other
subprocess.

**Control area.** The control area is `<root>/.txn/`, a real directory created
no-follow. It has three fixed subdirectories:

| Path | Owner | Lifetime |
|---|---|---|
| `.txn/staging/<operation-id>/` | One writer operation | Created at operation start. The owner removes it after publication or failure. If the process dies, it is **retained**: cleanup never deletes it. |
| `.txn/retired/<operation-id>/` | The pruner or publisher that retired entries into it | Holds garbage. It is deleted after retirement, and any later cleanup can delete it. |
| `.txn/rollback/<operation-id>/` | One installer operation | Created before the update's first mutation. It is removed after success or a verified restore. It is **retained** after any failure. |

An `<operation-id>` is `uuid.uuid4().hex`: 32 lowercase hex characters, which
are portable on every supported filesystem. The pruner never enters `.txn`
except `.txn/retired/`.

## Containment rules

These rules apply to every path below the root that the helper opens, creates,
renames or deletes:

1. **Control files are created without following links.**
   - POSIX: `os.open` with `O_NOFOLLOW` relative to the root directory
     descriptor (`dir_fd`). Temporary and unique names also use
     `O_CREAT | O_EXCL`.
   - Windows has no `O_NOFOLLOW`. Unique names use `O_CREAT | O_EXCL`, which
     fails if any entry, including a reparse point, already has the name. For
     the persistent lock file, the helper first `lstat`s the name and refuses a
     symlink, a reparse point or a non-regular file. After opening, it
     compares the handle's `fstat` identity with that `lstat` result, or with
     a fresh `lstat` if the file was just created. A mismatch raises
     `ContainmentError`.
   - Control directories are created with `os.mkdir`, which does not follow
     the final component. An existing name must pass `lstat` as a real,
     non-reparse directory.
2. **Protected files are never opened through a link.** These are
   `validation_cache.json`, installation metadata and installed artifacts. A
   symlink, a junction or another non-regular file at that name raises
   `ContainmentError`, and the target is not read, written or counted.
3. **Namespace directories must be real.** These are `downloads/`, `builds/`,
   `grammars/` and `.txn/` with its children. If one is a link or junction,
   the whole namespace is refused and reported.
4. **Links inside entries are leaves.** During prune walks and deletion, every
   symlink, Windows junction or other reparse point inside an entry is a leaf:
   - its age is its own `lstat` time;
   - it is removed with `unlink` (or `rmdir` for directory symlinks and
     junctions on Windows);
   - its target is never traversed, removed or counted.

   A dangling link is an ordinary leaf.
5. **Anchored deletion.**
   - POSIX deletion walks opened directory descriptors (`os.scandir(fd)`,
     `O_DIRECTORY | O_NOFOLLOW`, `unlink`/`rmdir` with `dir_fd`). It rechecks
     each directory's identity after opening it.
   - Windows deletion walks validated non-reparse directories by path, using
     `DirEntry.is_junction()` and `is_symlink()`, and removes reparse points
     as leaves.
   - Neither platform uses an unchecked `shutil.rmtree`.

## Primitive 1 — locked JSON record update (treesitter-chunker#370)

`update_json_records(root, name, mutate, *, reset_malformed=False, timeout=...)`
runs these steps, all under the root lock:

1. **Validate the name.** `name` is a single path component directly under the
   root, for example `validation_cache.json`.
2. **Read fresh state from disk.** Open the file for reading with no-follow and
   check that it is a regular file. Decode it as UTF-8 JSON.
   - A missing file is `{}`.
   - A document that is not a JSON object, or that fails to decode, is
     *malformed*. With `reset_malformed=True` it is treated as `{}` and logged.
     This keeps the current behavior of the validation-record writer.
     Otherwise the call raises `CacheTransactionError` and leaves the file
     unchanged. This keeps the current behavior of the pruner.
3. **Merge.** Call `mutate(dict(current))` to get the next document. The helper
   never writes an instance-local snapshot.
4. **Write a temporary file.** Create `<root>/.<name>.<operation-id>.tmp` with
   `O_CREAT | O_EXCL` and no-follow, mode `0o600`. Write UTF-8 JSON (2-space
   indent, as today), flush, `fsync` and close.
5. **Replace.** Call `os.replace(tmp, <root>/<name>)`. On POSIX, also `fsync`
   the root directory; that step is best effort.
6. **Handle Windows sharing violations.** On Windows, a sharing violation from
   a non-participant handle is retried at most 10 times with a short bounded
   wait. Persistent denial raises `CacheTransactionError` and leaves the target
   unchanged.
7. **Clean up on failure.** On any failure, unlink the temporary file. The
   target stays as it was.
8. **Return.** The call returns the document that was written.

`read_json_records(root, name, *, timeout=...)` performs step 2 under the lock
and returns the mapping. A malformed document always raises.

**Consumer rules for TXN:**

- `GrammarValidator` keeps `self._cache` only as a read cache. It is refreshed
  from the document that `update_json_records` returns, or from
  `read_json_records`. It is never written back wholesale.
- The writer's `mutate` sets exactly one key. The pruner's `mutate` keeps
  entries whose `timestamp` is greater than the cutoff, so the expiration rule
  is unchanged. The pruner still adds removed-entry counts to `files_removed`.

## Primitive 2 — staged publication and deletion-time re-check (treesitter-chunker#323)

The defect in treesitter-chunker#323 is that cleanup checks an entry's age, and
then a writer adds files to the entry before `rmtree` runs.

The contract removes the race at both ends:

- **Writers never mutate a published entry.** They build in private staging
  and publish with one rename while holding the lock.
- **The pruner re-checks eligibility under the lock.** It then retires the
  entry with one rename before it deletes anything.

**Entry keys.** An entry is one top-level name directly inside a namespace
(`downloads/` or `builds/`). Installer-produced names are
`downloads/tree-sitter-<language>` and `builds/<language>`, where `<language>`
passes the existing `_valid_language_name`. The pruner handles any top-level
name it finds, including foreign ones, by its directory-entry name. It maps no
keys and keeps no publication journal.

On case-insensitive filesystems, two language names that differ only in case
are one entry. Publication of the second replaces the first through
retirement, as for any republication.

**Writer protocol.**

1. `create_staging(root)` registers `.txn/staging/<operation-id>/` under the
   lock and returns a `StagingArea`.
2. Clone, checkout, build and validation run inside the staging directory with
   no lock held. A staged entry lives at `<staging>/<namespace>/<name>`, so one
   operation can stage both its download and its build. Every subprocess has returned before step 3. A timed-out
   `subprocess.run` has killed and reaped its direct child.
3. `publish_entry(root, staging, namespace, name)` does the following under the
   lock:
   - If `namespace/name` exists, rename it into `.txn/retired/<operation-id>/`.
     The helper never assumes `os.replace` overwrites a non-empty directory.
   - Rename the staged entry into `namespace/name`.
   - Set the published entry's own mtime to the publication time, without
     following links (`os.utime`).

   Copied sources may keep old mtimes, as `copy2` does. The fresh stamp still
   makes the entry ineligible for age pruning until its own cutoff passes.
4. `discard_staging(root, staging)` removes what is left of the operation's own
   staging. It then deletes what this operation retired.

Explicit removal (`GrammarInstaller._cleanup_cache`, the existing-download
removal in `_download_grammar`) uses `remove_entry(root, namespace, name)`.
This is the same retire-then-delete sequence without an age test.

**Pruner protocol** (`prune_entries(root, namespace, *, cutoff)`):

1. **Enumerate.** List the namespace's top-level entries with no lock. The
   enumeration is only a candidate list.
2. **Re-check under the lock.** For each candidate, take the lock and repeat
   the no-follow eligibility walk. An entry is eligible only if all of these
   hold:
   - its own `lstat` mtime is older than `cutoff`;
   - every descendant's `lstat` mtime is older than `cutoff`, with links
     counting as leaves;
   - no descendant is a regular file named `.txn.lock`, which marks a nested
     root (see gap 4).
3. **Retire.** While still holding the lock, rename an eligible entry into
   `.txn/retired/<operation-id>/`, then release the lock. A candidate that
   vanished or became ineligible is skipped and not counted.
4. **Delete.** Delete the retired tree with the anchored deleter, outside the
   lock. Nothing else references `.txn/retired/`, so no participant can be
   writing there.
5. **Count truthfully.**
   - `entries_removed` counts the entries retired by this call. This matches
     the existing top-level `files_removed` counter.
   - `bytes_freed` sums the `lstat` `st_size` of regular files *actually
     unlinked* by this call. Links count zero, and no bytes are counted before
     a successful unlink.
   - A failure to delete retired bytes is reported in `errors`, and those
     bytes are not counted.
6. **Clear old garbage.** Leftover `.txn/retired/*` trees from earlier
   interrupted calls are deleted by the same call, and their freed bytes count.
7. **Report staging.** `.txn/staging/*` is never deleted by the pruner. Staging
   directories older than `cutoff` are logged as retained, with their paths.

`GrammarManager.cleanup_cache` keeps its signature and result keys
(`files_removed`, `bytes_freed`, `directories_cleaned`, `errors`).

## Primitive 3 — rollback point and restore (treesitter-chunker#363)

Today `_create_rollback_point` records metadata only, and `_perform_rollback`
deletes the previous installation metadata while logging that it restored.
The contract replaces both behaviors.

**Containment.** Installed artifacts (`grammars/lib<language>.so` and
`grammars/<priority>/lib<language>.so`) and installation metadata
(`grammars/<language>_install_info.json`) must lie under `<root>/grammars/`.
If recorded metadata points outside it, rollback-point creation raises
`ContainmentError`. The update then aborts before its first mutation.

**`create_rollback_point(root, *, language, artifact, metadata)`** runs under
the lock, before the update mutates anything:

- It copies the current installed artifact (if any) and the metadata file (if
  any) into `.txn/rollback/<operation-id>/`. Sources are opened no-follow, and
  copies are created with `O_EXCL`. Each copy is `fsync`ed.
- It records each copy's SHA-256, computed while copying. The manifest is
  written last.
- An absent previous installation is recorded as absent.

The digests are **rollback identity records**. They only show that a restored
file is byte-identical to what was there before. They are never passed as
`provenance=` to `probe_native_grammar`, written to any pin or approval store,
or compared with `trusted_artifacts`. This satisfies Cross-Cutting Principle 4:
hashing discovered bytes never promotes them to an approval.

**Forward publication and commit order.** `GrammarInstaller._install_grammar_file`
stops writing with `shutil.copy2` in place. It publishes the new artifact with
the IF-0-HOTFIX-1 function `publish_native_grammar` (see
[Restore publication](#restore-publication-if-0-hotfix-1)). The `provenance`
is the caller-supplied pin record for the language, per IF-0-ADMITPIN-1. The
installer commits in this order:

1. Capture the rollback point.
2. Publish the new installation metadata with Primitive 1's
   temporary-file-and-replace mechanics. Record the SHA-256 of the bytes
   written.
3. Call `publish_native_grammar(built, destination, language, provenance=...)`
   as the **last fallible mutation**. Record `NativeProbeResult.artifact_sha256`
   when it is supported.
4. Call the caller's cache invalidation, which IF-0-HOTFIX-1 makes the
   caller's job, then discard the rollback point.

IF-0-HOTFIX-1 guarantees that an unsupported result or an `OSError` leaves the
destination unchanged. So in steps 1 to 3, a failed update never needs the
previous artifact republished: the previous artifact is preserved by never
being replaced. Restoration in that case consists of restoring the metadata
written in step 2. Only a failure after step 3 succeeded can need the
artifact republished. Step 3 is ordered so that nothing fallible follows it;
the artifact branch of `restore` covers this residual case and failures of
non-participating code.

**`restore(point, *, published_artifact_sha256, published_metadata_sha256, provenance, invalidate)`**
runs under the lock. It handles the artifact and the metadata separately:

| Current destination digest | Action | Reported as |
|---|---|---|
| Equals the rollback copy's digest, or both are absent | No change | Already in place |
| Equals what *this* operation published | Restore the rollback copy. If the previous file was absent, retire the destination. | Restored, or failed (see below) |
| Anything else | Touch nothing: another operation has published since | `superseded` |

**Metadata** is restored from its byte copy with Primitive 1's replace
mechanics.

**Artifact restoration** first verifies the rollback copy against its identity
digest using `chunker.grammar.integrity.verify_artifact`. A mismatch fails the
restore and changes nothing. It then calls
`publish_native_grammar(<rollback copy>, destination, language, provenance=provenance)`,
where `provenance` is the caller-supplied pin record for the **previous**
revision. Then `invalidate(destination)` runs after every attempt.

- If the caller has no pin for the previous revision (`provenance=None`, or a
  record whose digest differs), the probe rejects it. The destination keeps
  the admitted new artifact, the restore reports failure, and the rollback
  point is retained.
- Restore never falls back to an unadmitted replacement, and it never uses the
  rollback identity digest as `provenance`.

`RestoreResult` reports `artifact_restored`, `metadata_restored`, `superseded`
and `errors`. `restored` is true only when the destination matches the
rollback point afterwards.

**After a failure:**

- Every failure exit of `install_grammar` that occurs after the rollback point
  exists calls `restore`. That covers both exceptions and `False` returns.
- A failure before anything was published finds the destinations unchanged, so
  restore reports them as already in place.
- After a verified restore, or after success, `discard_rollback_point` removes
  `.txn/rollback/<operation-id>/`.
- After a failed or superseded restore, the rollback point is **retained**. Its
  path is reported in the installer's error message, and the installer never
  logs that the rollback succeeded.

**Windows.** IF-0-HOTFIX-1 raises `OSError` when Windows refuses to replace a
library that a process has loaded, and the destination is then unchanged.
Restore does not retry the artifact replacement, because each attempt would
run the probe again. A refusal fails the restore and keeps the rollback point.
The helper never deletes the destination to work around a held handle. The
installer process must not hold its own handle to the destination: it validates
through the probe's private snapshot, not through a mapping in the parent
process. EC-TXN-3 shows this on a real Windows run.

### Restore publication (IF-0-HOTFIX-1)

**Cited signature.** IF-0-HOTFIX-1 as published in the treesitter-chunker#162
PR (treesitter-chunker#539) body under the heading `IF-0-HOTFIX-1 signature`,
at head `7710fb7c699db33c244c95bf7d24d8730b91ea5b`:

```python
# chunker/_internal/user_grammar_tools.py
def publish_native_grammar(
    source: Path,
    destination: Path,
    language: str,
    *,
    provenance: Mapping[str, Any] | None,
    sample: bytes = b"",
    timeout: float = 10.0,
) -> NativeProbeResult:
```

The function has these steps:

1. Copy `source` into a sibling temporary file next to `destination` and
   `fsync` it.
2. Admit that file with `probe_native_grammar` and the caller's `provenance`.
3. Only if the result is supported, `os.replace` it onto `destination`. The
   existing inode is never written or truncated.
4. On an unsupported result or an `OSError`, remove the staged file and leave
   `destination` unchanged.

Cache invalidation is the caller's job.

This contract uses that function unchanged for both forward publication and
artifact restoration. It defines no second native publish path, and it does
not split out an admission-free replacement step.

The primitives check containment before calling the function. If
`destination` is a link, the rollback point is refused and the update aborts
before its first mutation. IF-0-HOTFIX-1's own "replaced, not followed"
behavior therefore never applies to a contained installation.

**Re-review trigger.** treesitter-chunker#539 was still a draft when this was
cited. If its published signature or the steps above change before
IF-0-TXNSPEC-1 is approved, this section is reviewed again (roadmap TXNSPEC
scope notes).

**Pin dependency for TXN.** The forward publication and the restore need a
caller-supplied pin record. `GrammarInstaller` has no pin source until the
IF-0-ADMITPIN-1 `trusted_artifacts` parameter lands. The TXN plan must do one
of two things:

- sequence the treesitter-chunker#363 PR after ADMIT's `core.py` constructor
  change; or
- take pins only from callers and fixtures, as HOTFIX does, without
  anticipating the CLI pin source.

## Disposition of the treesitter-chunker#364 blocking gaps

The gaps are listed in the final CLEANUP verdict on treesitter-chunker#323, at
the treesitter-chunker#364 head `4465de92`.

| # | Gap | Disposition | Rationale |
|---|---|---|---|
| 1 | Child-writer lifetime across parent death | **addressed** | Subprocesses only ever write inside their operation's private `.txn/staging/<operation-id>/`. They never receive a published path or the lock. Only the parent publishes, under the lock, after every subprocess has returned. If the parent dies, a surviving child or grandchild can write only to staging. The pruner never deletes staging, so no published or live data is lost, and nothing in staging is ever published. The lock lifetime never depends on children, because the lock is not held during subprocesses. |
| 2 | Durable operation and initialization recovery | **addressed** (initialization); **scoped out** (automatic crash recovery) | No persistent authority state exists: no publication journal, no generation counter, no root registration. The lock file carries no state, and its idempotent no-follow creation is the whole initialization. A missing `validation_cache.json` means empty, as today. Every publication is one atomic rename, so a crash leaves either the old or the new entry at the published name, never a partial one. A crash also leaves only retained staging, rollback points or retired garbage. Automatic crash recovery is scoped out, because no consumer's acceptance requires it and a journal was the part that failed review. Operators restore from a retained rollback point, or remove retained staging, as documented here. |
| 3 | Transactional deletion retirement | **addressed** | Pruning, explicit removal and republication all first retire the whole entry with one rename while holding the lock. They delete only from `.txn/retired/`. The published namespace therefore goes from present to absent atomically, and a partial deletion failure leaves bytes only in garbage, uncounted and reported. |
| 4 | Enforceable nested-root detection | **addressed** for participating roots | A root is identified by its `.txn.lock`. `open_cache_root` refuses a root that lies inside an ancestor root's `downloads/`, `builds/` or `.txn/` (an ancestor that holds a regular `.txn.lock`). The pruner's locked eligibility walk skips any entry with a `.txn.lock` among its descendants. An operation never takes two roots' locks. Residual risk: two roots initialized at the same moment are not detected. `config.CacheManager`'s distinct root is a non-participant (see the Scope table). |
| 5 | No-follow control-file creation | **addressed** | Containment rule 1 covers the lock file, temporary files, staging, retirement, rollback directories and manifests: POSIX `O_NOFOLLOW` with `dir_fd`; `O_EXCL` unique names; Windows `lstat`/`fstat` identity and reparse checks. |
| 6 | Concrete portable entry keys | **addressed** | The helper keeps no key map. Entries are their top-level directory-entry names, with installer names restricted by `_valid_language_name`. Operation IDs are lowercase `uuid4` hex. Validation-record keys remain the existing SHA-256 hex. The section on Primitive 2 states what happens on case-insensitive filesystems. |
| 7 | Truthful real-consumer and fixture routing | **addressed** | The Scope tables list every participant function and every non-participant with its consequence. A TXN PR may claim only what its participants implement. Each required test drives the real public method, asserts that the named seam was reached, and uses real fixtures (see below). |

**Threats outside every row of the table.**

- Hostile processes running as the same user, and other non-participating
  mutators.
- Substitution of the root's ancestors after the root is opened.
- Cross-host and network-filesystem locking.
- `config.py` cache operations and the CLI fallback (see Scope).

## Test seam

The helper module has a private seam, `_BARRIER: Callable[[str], None] | None`.
It is `None` in production. When it is set, the helper calls it with a stable
point name.

| Point name | Where it is called |
|---|---|
| `lock.acquired` | After the root lock is taken |
| `json.after_read` | After the fresh read in Primitive 1 |
| `json.before_replace` | Just before the replace in Primitive 1 |
| `prune.after_enumerate` | After the unlocked candidate listing |
| `prune.after_recheck` | After the locked eligibility re-check |
| `publish.before_rename` | Just before the publication rename |
| `rollback.after_capture` | After the rollback point is written |
| `restore.before_replace` | Just before restore calls `publish_native_grammar` |

Tests install the seam inside a subprocess and block on a pipe or event file,
never on sleeps. The seam only pauses execution; it never replaces the
behavior under test.

## Required TXN tests and named mutations

Each test passes on the fix and fails under its mutation. The PR records both
runs (VB-2). All scratch data goes under `$TMPDIR` in temporary roots. Tests
use no network access and no operator files.

| Consumer | Deterministic barrier test | Named mutation that must fail it |
|---|---|---|
| treesitter-chunker#370 | **Two writers.** Construct two real `GrammarValidator` instances before either writes. Each persists a unique record through `validate_grammar`, in either order and also concurrently. Use a real rejection record from a non-library fixture where no native fixture is available. Process A pauses at `json.before_replace` while B blocks on the lock. Both records stay on disk. Use exact-key or `any(...)` lookup, as the treesitter-chunker#401 note asks. **Writer and pruner.** `cleanup_cache` paused at `json.after_read` versus a writer: the fresh record survives, and expired records are still pruned at the existing cutoff rule. | `stale_validation_snapshot`: write the instance snapshot instead of merging with fresh disk state. `pruner_stale_rewrite`: the pruner writes its pre-lock read. |
| treesitter-chunker#370 | **Outside-symlink sentinel.** Make `validation_cache.json` a symlink to an outside sentinel JSON. Writer and pruner both report a containment error. The sentinel's bytes are unchanged. | `follow_validation_symlink`: open the target with link-following. |
| treesitter-chunker#323 | **Writer and pruner.** Pause `cleanup_cache` at `prune.after_enumerate` with an expired candidate entry. A participant republishes the same name through the installer's publication path, using contents copied with old mtimes. Resume: the new entry survives and is not counted in `bytes_freed`. **Counts.** Separate cases cover fully expired entries, entries at the exact cutoff, and denied deletion. Counts are truthful in each. | `prune_without_recheck`: use enumeration-time eligibility. `trust_copied_mtime`: skip the publication stamp. `overcount_failed_removal`: count bytes before unlink. |
| treesitter-chunker#323 | **Link boundaries.** An old entry contains a file symlink, a directory symlink, a dangling link, and (on Windows) a junction, each pointing to an outside sentinel. The links are removed as leaves. Sentinels are unchanged and count zero bytes. Run on Linux, macOS and Windows. | `follow_cache_link`: traverse link targets. |
| treesitter-chunker#363 | **Failed-update restore.** Install revision A of a real compiled fixture grammar locally, with A's pin. Run an update to revision B that fails deterministically at artifact publication (B is unpinned, so the probe rejects it) after the new metadata was written. Check the artifact digest and metadata bytes equal A's. A fresh subprocess parse shows revision A behavior. Also cover a failure before any publication (destinations untouched), a `False`-returning failure, and a superseded case. **Post-publication residual.** The caller's invalidation hook raises after B was published. With A's pin supplied, restore republishes A through `publish_native_grammar`. Without A's pin, restore reports failure, B stays, and the rollback point is retained. Run on Windows, where restore succeeds (handle release). | `omit_restore`: skip the restore. `rollback_removes_metadata`: today's behavior. `restore_without_admission`: replace without the probe, so the no-pin case installs A. |

The TXN PRs keep `tests/test_core_grammar_cache_cleanup.py` and the existing
helper-cache tests passing. They change an existing assertion only where it
pins the lost-update behavior. treesitter-chunker#401's `all(...)` lookup is one
such case.

## Signatures

These are the public signatures of `chunker/grammar_management/_transactions.py`.
They are frozen here as text only. This PR adds no stub module, because a new
package file would change the pinned wheel payload inventory in
`tests/test_supported_wheel_verification.py`. TXN SL-cache creates the module
and updates that inventory in the same PR. The module imports only the
standard library at module level. It imports the integrity and
IF-0-HOTFIX-1 helpers lazily inside `restore`. That way, `cli.py` fallback code
could use it later without importing core.

```python
DEFAULT_LOCK_TIMEOUT: Final[float] = 30.0
LOCK_FILE_NAME: Final[str] = ".txn.lock"
CONTROL_DIR_NAME: Final[str] = ".txn"
Namespace = Literal["downloads", "builds"]

class CacheTransactionError(Exception): ...
class CacheLockTimeoutError(CacheTransactionError): ...
class ContainmentError(CacheTransactionError): ...

@dataclass(frozen=True)
class StagingArea:
    root: Path
    operation_id: str
    path: Path

@dataclass(frozen=True)
class PruneResult:
    entries_removed: int
    bytes_freed: int
    skipped: tuple[str, ...]
    errors: tuple[str, ...]

@dataclass(frozen=True)
class RollbackPoint:
    root: Path
    operation_id: str
    language: str
    path: Path
    artifact: Path
    artifact_sha256: str | None  # None: no previous artifact
    metadata: Path
    metadata_sha256: str | None  # None: no previous metadata

@dataclass(frozen=True)
class RestoreResult:
    restored: bool
    artifact_restored: bool
    metadata_restored: bool
    superseded: bool
    errors: tuple[str, ...]

def open_cache_root(root: Path) -> Path: ...
def cache_lock(root: Path, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> AbstractContextManager[None]: ...
def read_json_records(root: Path, name: str, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> dict[str, Any]: ...
def update_json_records(root: Path, name: str, mutate: Callable[[dict[str, Any]], dict[str, Any]], *, reset_malformed: bool = False, timeout: float = DEFAULT_LOCK_TIMEOUT) -> dict[str, Any]: ...
def create_staging(root: Path, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> StagingArea: ...
def publish_entry(staging: StagingArea, namespace: Namespace, name: str, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> Path: ...
def discard_staging(staging: StagingArea, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> PruneResult: ...
def remove_entry(root: Path, namespace: Namespace, name: str, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> PruneResult: ...
def prune_entries(root: Path, namespace: Namespace, *, cutoff: float, timeout: float = DEFAULT_LOCK_TIMEOUT) -> PruneResult: ...
def create_rollback_point(root: Path, *, language: str, artifact: Path, metadata: Path, timeout: float = DEFAULT_LOCK_TIMEOUT) -> RollbackPoint: ...
def restore(point: RollbackPoint, *, published_artifact_sha256: str | None, published_metadata_sha256: str | None, provenance: Mapping[str, Any] | None, invalidate: Callable[[Path], None], timeout: float = DEFAULT_LOCK_TIMEOUT) -> RestoreResult: ...
def discard_rollback_point(point: RollbackPoint, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> None: ...
```

`open_cache_root` validates the root, creates the lock file and control area,
and returns the root path unchanged. It refuses nested roots (gap 4). Every
other function performs the same validation implicitly. Consumers call
`open_cache_root` at construction so that they fail early.

`cache_lock` is reentrant on one root within a process. It is how composite
consumer steps hold one critical section. The other functions take the lock
themselves, reusing it when it is already held.

## TXN lane notes

- `GrammarInstaller._download_grammar`, `_build_grammar` and `_cleanup_cache`
  are the writer side of treesitter-chunker#323. The roadmap assigns the
  rollback functions of the `GrammarInstaller` region to SL-rollback. The TXN
  plan must give these three writer functions to the treesitter-chunker#323 PR
  (SL-cache), with SL-rollback rebasing. Otherwise, treesitter-chunker#323
  cannot truthfully claim writer coordination.
- Merge order follows the roadmap's `core.py` order.
