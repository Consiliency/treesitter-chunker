# Cache transaction contract

> Maintainer/internal documentation. This page is intentionally omitted from public navigation.

Status: **proposed interface freeze IF-0-TXNSPEC-1** (roadmap
`specs/phase-plans-v4.md`, Phase 3 TXNSPEC). It has not been accepted yet.
This revision answers the round-1 VB-4 reviews on treesitter-chunker#540.

This document changes no runtime behavior, and no consumer is migrated here.
The helper module `chunker/grammar_management/_transactions.py` does not exist
yet. Its signatures are frozen in [Signatures](#signatures), and TXN lane
SL-cache creates the module in its first PR.

Phase TXN implements the contract for treesitter-chunker#370,
treesitter-chunker#323 and treesitter-chunker#363. It succeeds the rejected
treesitter-chunker#364 CLEANUP design; wherever the two differ, this document
takes precedence. The successor narrows that design rather than proposing it
again.

Forward publication and the restore path use IF-0-HOTFIX-1
(treesitter-chunker#162) unchanged. The signature is cited from
treesitter-chunker#539; see
[IF-0-HOTFIX-1 citation](#if-0-hotfix-1-citation).

## Scope

**Consumers.** The contract covers exactly three consumers, all in
`chunker/grammar_management/core.py`. Every function listed here participates
after TXN. The TXN lane that owns each function is given in
[TXN lane assignment](#txn-lane-assignment).

| Consumer | Issue | Participating functions after TXN |
|---|---|---|
| Validation-record JSON | treesitter-chunker#370 | `GrammarValidator._load_validation_cache`, `GrammarValidator._cache_validation_result`, the validation-cache pruning block of `GrammarManager.cleanup_cache` |
| Cache entry writer and pruner | treesitter-chunker#323 | **Writers:** `GrammarInstaller._download_grammar`, `_build_grammar` and the `_build_with_*` helpers, `_get_commit_hash`, and the staging routing in `install_grammar`. **Removers:** `GrammarInstaller._cleanup_cache`. **Pruner:** `GrammarManager.cleanup_cache` and `GrammarManager._cleanup_directory` |
| Installation commit and rollback | treesitter-chunker#363 | **Commit:** the commit section of `GrammarInstaller.install_grammar`, `_create_rollback_point`, `_perform_rollback`, `_install_grammar_file`, `_save_installation_info`. **Readers:** `_load_installation_info`, which also covers `GrammarRegistry.get_language_info`, `GrammarRegistry.detect_version_conflicts`, `GrammarManager.list_installed_grammars`, `GrammarManager.get_grammar_metadata` and the call in `compatibility.py`. **Removers:** `GrammarInstaller.remove_grammar` and `GrammarManager.remove_grammar`, `_remove_installation_info` |

**Non-participants.** These paths do not follow the protocol. No TXN PR may
claim concurrency safety for them.

| Path | Why it is outside the contract | Consequence |
|---|---|---|
| `ComprehensiveGrammarCLI._cleanup_cache_fallback` (`cli.py`) | Runs only when the core manager is unavailable. It is not one of the three consumers. | Running it concurrently with a participating writer on the same root is unsupported. It keeps its static no-follow behavior from treesitter-chunker#324. It never lists `.txn`. Routing it through the helper is a separately filed follow-up. The helper has no core import, so that routing remains possible. |
| `DirectoryManager.cleanup_empty_directories` (`config.py`), called by `CacheManager` | It walks `DirectoryManager.base_dir`. By default that **is** the core root (`~/.cache/treesitter-chunker`). It runs `rmdir` on every empty directory except those named `grammars`, `cache`, `logs`, `backups` or `tmp` and `base/cache/{downloads,builds}`. It deletes no files. | **Overlap:** it can remove any empty directory under the core root. Roadmap runner decision D-c leaves `config.py` unchanged. Instead, every directory the helper creates under `.txn/` gets the marker file `.txn-keep` immediately after `mkdir` and before any other use, so an in-use control directory is never empty (see [Control area](#control-area)). **Remaining consequences:** (1) A sweep that wins the race between `mkdir` and writing the marker removes the new directory. The helper then fails to write the marker, retries `mkdir` plus marker once, and otherwise raises `CacheTransactionError`. The operation fails before using that directory. (2) An empty directory created by a subprocess inside staging, before the subprocess writes into it, can be removed. That subprocess then fails, and the operation fails before publication. (3) Empty published entries and empty `downloads/` or `builds/` namespaces can be removed. No bytes are lost; the helper re-creates a missing namespace directory, no-follow, under the lock. |
| `CacheManager` age, size and clear (`config.py`) | Uses `directory_manager.get_directory("cache")`, by default `<core root>/cache/`. Its `downloads`/`builds` are not core namespaces. | Not protected. With the default layout it touches no core namespace. If an operator points it at the core root's `downloads/` or `builds/`, it becomes a non-participating deleter on that root, which is unsupported. |
| `chunker/_internal/cache.py` (AST cache), `chunker/boundary/cache.py` | Roadmap non-goals. HOTFIX owns the AST cache. | None |
| `UserGrammarTools` (`chunker/_internal/user_grammar_tools.py`) | It writes `~/.cache/treesitter-chunker/build`, which is not a core namespace. It publishes through IF-0-HOTFIX-1. | None for this contract |
| `GrammarRegistry` artifact discovery (`_discover_in_directory`) | It reads artifact files only, never metadata. | It sees either the previous or the new artifact, because `os.replace` is atomic. It never sees a partial file, and it is not pair-consistent with metadata (see [Remaining windows](#remaining-windows)). |
| Older package versions, external tools, and hostile processes running as the same user | They do not take the lock. | Stop them before using a root with a participating version. The `superseded` outcome of `restore` exists only for these. |

**Concurrency scope.** One host only. Participating threads and processes on
that host share one cache root on a local filesystem. Cross-host sharing and
network filesystems (NFS, SMB/CIFS, sshfs and similar) are unsupported, and the
helper does not try to detect them. This is roadmap Assumption 5. If review
rejects this scope, decision S-TXN applies.

**Supported platforms.**

- Linux and macOS: `fcntl.flock`, `O_NOFOLLOW`, `dir_fd` operations, process
  groups.
- Windows on NTFS: `msvcrt.locking`, reparse-point checks, job objects.

Python 3.12 is the floor. Release checks also cover 3.14.

If a required primitive is unavailable, the operation raises
`CacheTransactionError` and changes nothing; it never passes silently.
Examples are a lock call that fails with `ENOLCK` or `EOPNOTSUPP`, a missing
`DirEntry.is_junction`, and a failure to create a process group or job object.

## Roots, lock file and control area

### Root

The root is the `cache_dir` given to `GrammarValidator`, `GrammarInstaller`
and `GrammarManager` (default `~/.cache/treesitter-chunker`). All three already
share it.

The operator trusts the root path as given, including symlinks in the root
path and its ancestors, so alias layouts such as macOS `/var` work.
`open_cache_root` records the root's identity (`st_dev`, `st_ino`). **Every lock
acquisition re-checks** that the root path still resolves to that identity. A
mismatch raises `CacheTransactionError` with no mutation. On POSIX, an
operation also holds an open directory descriptor and works relative to it.

Everything the helper opens or creates below the root follows the
[containment rules](#containment-rules).

### Lock file

Each root has one lock file, `<root>/.txn.lock`.

- It is a regular file, created on first use with mode `0o600` and one byte of
  content.
- Participants never unlink, truncate or rename it. It carries no state.
- POSIX: an exclusive `fcntl.flock` on the descriptor.
- Windows: `msvcrt.locking` on byte 0, keeping the handle for the whole hold.
- There is no shared mode. Readers of protected files take the same exclusive
  lock, so a Windows reader handle can never make a participant's `os.replace`
  fail.
- **Not inheritable.** The descriptor or handle is opened non-inheritable
  (PEP 446 default), and the helper asserts `os.get_inheritable(fd) is False`
  after opening it. No participant passes it through `pass_fds`,
  `handle_list` or `close_fds=False`. Subprocesses, including the probe
  child, therefore never hold the lock.

### Process semantics

**In-process exclusion.** A process-local reentrant lock, keyed by the lock
file's `(st_dev, st_ino)`, serializes threads before the OS lock is taken. Two
spellings of one root share both locks. Nested acquisition on the same root
reuses the held lock and opens no second descriptor. An operation touches
exactly one root and never holds two roots' locks.

**Crash.** The kernel releases the lock when the holding process dies. Windows
may release a byte-range lock only after process teardown completes; the
bounded acquisition timeout absorbs that delay. No stale-lock breaking exists,
by design.

**Fork.** The helper registers `os.register_at_fork(after_in_child=...)`. In the
child, that handler clears the process-local lock table and closes every
inherited lock descriptor. The parent's lock is unaffected: flock state belongs
to the open file description, and the parent still holds its descriptor. A
forked child must acquire again before using the helper.

**Callbacks.** `mutate` (Primitive 1) and `invalidate` (Primitive 3) run under
the lock. They must not start subprocesses, block on another participant,
acquire another root, or call helper functions on another root.

**Acquisition.** Acquisition is bounded by `timeout`, with default
`DEFAULT_LOCK_TIMEOUT = 60.0` seconds. That exceeds the longest critical
section's bound: two default probe timeouts plus copying. Acquisition uses
non-blocking attempts with a short backoff. Seam point `lock.contended` fires
after the first failed attempt. A timeout raises `CacheLockTimeoutError`, and
the caller reports an actionable error and performs no write, prune, publish,
restore or removal. The timeout bounds waiting; it is not a correctness
deadline, and tests must not assert on its wall-clock behavior.

### Lock scope

The lock is held only for these critical sections:

1. a JSON or installation-metadata read or update;
2. one entry's eligibility walk plus retirement (pruner, `remove_entry`, and
   the retirement inside `publish_entry`);
3. one cache-entry publication;
4. one installation removal;
5. **one installation commit**, as one `cache_lock` section: capture the
   rollback point, publish the metadata, call `publish_native_grammar`, then
   either discard the rollback point (success) or `restore` (failure). See
   [Installation commit](#installation-commit).

**Only one subprocess may run under the lock: the IF-0-HOTFIX-1 probe child.**
`publish_native_grammar` starts it during the commit section, and `restore`
may start it once more. It is bounded by the `timeout` passed to
`publish_native_grammar`, the default 10 seconds, plus the probe's own
documented cleanup. It inherits no lock descriptor or handle. It reads only
its private snapshot, never the root.

The lock is **never** held across `git`, `tree-sitter`, `gcc`, `make` or any
other subprocess. Those run through `run_in_staging` with no lock held.

### Control area

The control area is `<root>/.txn/`, a real directory. It has three fixed
subdirectories:

| Path | Owner | Lifetime |
|---|---|---|
| `.txn/staging/<operation-id>/` | One writer operation | Created at operation start. The owner removes it after the last consumer and after its process group or job is confirmed empty. It is **retained** if the owner dies, or if emptiness cannot be confirmed. No other participant publishes from it or deletes it. |
| `.txn/retired/<operation-id>/<namespace>/<name>` (and `.../grammars/<file>`) | The operation that retired the item | Garbage. The owner deletes it right after retirement. Any later prune may claim and delete it (see [Retired garbage](#retired-garbage)). |
| `.txn/rollback/<operation-id>/` | One installer commit | Created at the start of the commit section and removed after success or a verified restore. It is **retained** after a failed or superseded restore, or a crash. |

**Markers.** The helper creates each of these directories with `os.mkdir`
(no-follow on the final component). It then immediately creates the marker
file `.txn-keep` inside it with `O_CREAT | O_EXCL` and no-follow. This covers
`.txn`, the three subdirectories, every `<operation-id>` directory, and the
helper-created namespace directories inside staging (`<staging>/downloads`,
`<staging>/builds`). Markers are never moved into published entries. This is
decision D-c, against `DirectoryManager.cleanup_empty_directories`.

An `<operation-id>` is `uuid.uuid4().hex`: 32 lowercase hex characters,
portable on every supported filesystem.

## Nested roots

A directory is a *participating root* once `<dir>/.txn.lock` exists as a
regular file. Overlapping participating roots, one inside another's namespace,
are an **unsupported configuration**. The helper detects and refuses them in
the cases below. The remaining risk is stated.

1. **Refusal at open.** `open_cache_root(P)` refuses `P` if an ancestor `A`
   holds a regular `A/.txn.lock` and `P` equals, or lies below, `A/downloads`,
   `A/builds` or `A/.txn`. It compares both the lexical absolute path and the
   resolved path. This covers the outer-first case.
2. **Post-initialization check.** After creating its own lock file and control
   area, `open_cache_root` repeats rule 1 and the root-identity check before
   returning. A root whose directory was moved or claimed during
   initialization fails here, before any operation writes into it.
3. **Reserved names.** `.txn.lock`, `.txn` and any name starting with `.txn`
   are never namespace entries. Enumeration skips and reports them.
   `remove_entry` and `publish_entry` refuse such names with
   `ContainmentError`. Installer names cannot produce them, because
   `_valid_language_name` requires a leading alphanumeric.
4. **Every retirement refuses nested roots.** The pruner, `remove_entry` and
   the retirement of an existing entry inside `publish_entry` all walk the
   entry under the lock before renaming it. If any descendant is a regular
   file named `.txn.lock`, they refuse with `NestedRootError`, which is a
   report, not a deletion. A refused `publish_entry` fails the publication and
   leaves the staged entry in staging. This covers the inner-first case: once
   the outer root is opened, the containing entry can never be retired, and
   cleanup reports it every time.

**Residual risk.** An inner root is initialized for the first time
concurrently with the outer root's retirement of the containing entry, as
follows:

1. The outer root's walk runs before the inner lock file exists.
2. The inner root finishes its post-initialization check before the outer
   root's rename.
3. The outer root renames the entry and deletes the inner root's first data.

This requires two roots, one inside the other's managed namespace, the inner
one initialized for the first time inside the very entry being retired at that
moment. It is not closed. Closing it would require the inner root to take the
outer root's lock, which breaks the one-root rule.

## Containment rules

These apply to every path below the root that the helper opens, creates,
renames or deletes.

1. **Control files are created without following links.**
   - POSIX: `os.open` with `O_NOFOLLOW` relative to the root directory
     descriptor. Unique names also use `O_CREAT | O_EXCL`.
   - Windows: unique names use `O_CREAT | O_EXCL`, which fails if any entry,
     including a reparse point, has the name. For the persistent lock file,
     the helper first `lstat`s the name and refuses a symlink, reparse point
     or non-regular file. After opening, it compares the handle's `fstat`
     identity with that result, or with a fresh `lstat` if it just created the
     file. A mismatch raises `ContainmentError`.
   - Control directories are created with `os.mkdir`. An existing name must
     pass `lstat` as a real, non-reparse directory.
2. **Protected files are never opened through a link.** These are
   `validation_cache.json`, installation metadata and installed artifacts. A
   symlink, junction or other non-regular file at that name raises
   `ContainmentError`, and the target is not read, written or counted.
3. **Namespace directories must be real.** These are `downloads/`, `builds/`,
   `grammars/` (and `grammars/<priority>/`) and `.txn/` with its children. A
   link or junction refuses the whole namespace.
4. **Links inside entries are leaves.** During walks and deletion, every
   symlink, junction or other reparse point inside an entry is a leaf:
   - its age is its own `lstat` time;
   - it is removed with `unlink`, or with `rmdir` for directory symlinks and
     junctions on Windows;
   - its target is never traversed, removed or counted.

   A dangling link is an ordinary leaf.
5. **Anchored deletion.**
   - POSIX walks opened directory descriptors (`os.scandir(fd)`,
     `O_DIRECTORY | O_NOFOLLOW`, `unlink`/`rmdir` with `dir_fd`) and rechecks
     each directory's identity after opening it.
   - Windows walks validated non-reparse directories by path, using
     `DirEntry.is_junction()` and `is_symlink()`.
   - On either platform, `ENOENT` during deletion means "already deleted": it
     is not an error and not counted. No unchecked `shutil.rmtree` is used.
6. **Bounded Windows retry.** On Windows, every `os.replace` and `os.rename`
   that the helper performs is retried at most 10 times, with a short bounded
   wait, after a sharing violation or access-denied error. Persistent failure
   follows the failure rule of the operation in question; the helper never
   deletes a destination to work around a held handle.

## Primitive 1 — locked JSON record update (treesitter-chunker#370)

`update_json_records(root, name, mutate, *, reset_malformed=False, timeout=...)`
runs these steps under the root lock:

1. **Validate the name.** `name` is a single path component directly under the
   root, such as `validation_cache.json`, and is not reserved.
2. **Read fresh state.** Open the file no-follow, check that it is a regular
   file, and decode it as UTF-8 JSON.
   - A missing file is `{}`.
   - A non-object or undecodable document is *malformed*.
     - With `reset_malformed=True`, it is treated as `{}` and logged. This is
       today's writer behavior.
     - Otherwise the call raises `CacheTransactionError` and leaves the file
       unchanged. This is today's pruner behavior.
3. **Merge.** Call `mutate(dict(current))` (seam point `json.after_read` comes
   before it). The helper never writes an instance-local snapshot.
4. **Write a temporary file.** Create `<root>/.<name>.<operation-id>.tmp` with
   `O_CREAT | O_EXCL` and no-follow, mode `0o600`. Write UTF-8 JSON with
   2-space indent as today, then flush, `fsync` and close.
5. **Replace.** Seam point `json.before_replace`, then `os.replace(tmp,
   <root>/<name>)`, with the Windows retry. On POSIX, `fsync` the directory;
   that step is best effort.
6. **Clean up on failure.** Unlink the temporary file and leave the target
   unchanged. A crash can leave a `.<name>.<operation-id>.tmp` file behind
   (see [Crash states](#crash-states-and-operator-recovery)).
7. **Return** the document that was written.

`read_json_records(root, name, *, timeout=...)` performs step 2 under the
lock. A malformed document always raises.

**Consumer rules for TXN:**

- **Construction (`_load_validation_cache`).** Today's behavior is kept: on a
  malformed document, `ContainmentError`, `CacheLockTimeoutError` or any
  `CacheTransactionError`, it logs a warning and uses `{}`. Building a
  validator, and so any manager, never fails because of the record file. A
  containment failure is then reported again by every write.
- **Read cache.** `self._cache` is only a read cache. It is refreshed from the
  document that `update_json_records` returns, and never written back
  wholesale.
- **Writer and pruner.** The writer's `mutate` sets exactly one key, and its
  errors are caught and warned as today. The pruner's `mutate` keeps entries
  whose `timestamp` is greater than the cutoff, so the expiration rule is
  unchanged. Removed-entry counts still go into `files_removed`.
- **Staging-path keys are accepted.** `_get_cache_key` includes the artifact
  path. Validation of a build inside staging therefore writes a record keyed
  by a `.txn/staging/<operation-id>/...` path that is never looked up again.
  Such records expire through the normal age pruning. The alternative,
  validating after publication, would consume a published path outside the
  lock (see [Input routing](#input-routing)).

## Primitive 2 — staging, owned subprocesses and cache-entry publication (treesitter-chunker#323)

The defect in treesitter-chunker#323 is that cleanup checks an entry's age, and
a writer then adds files before `rmtree`. The contract removes the race at
both ends:

- **Writers never mutate a published entry.** They build in private staging,
  and their subprocesses' descendants are confirmed gone before anything is
  published.
- **Every deleter re-checks under the lock and retires before deleting.**

### Entry keys

An entry is one top-level name directly inside `downloads/` or `builds/`.
Installer names are `downloads/tree-sitter-<language>` and `builds/<language>`,
where `<language>` passes `_valid_language_name`. The pruner handles any
non-reserved top-level name by its directory-entry name. It maps no keys and
keeps no publication journal. On case-insensitive filesystems, two language
names that differ only in case are one entry; publishing the second replaces
the first through retirement.

### Owned subprocesses

`run_in_staging(staging, argv, *, cwd, timeout, env=None)` is the only way a
participant starts a subprocess that may write into staging. `cwd` must lie
inside `staging.path`.

1. **Launch.**
   - POSIX: `start_new_session=True`, so the child leads a new process group.
   - Windows: the child is created suspended, assigned to a new job object
     with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and without the breakaway
     limits, then resumed.
2. **Wait.** Wait for the direct child, up to `timeout`.
3. **Kill the group.** Whether the child exited or timed out, kill the whole
   group or job: `os.killpg(pgid, SIGKILL)`, or `TerminateJobObject`.
4. **Confirm empty.** Poll until the group or job is confirmed empty, within a
   bounded deadline:
   - POSIX: `os.killpg(pgid, 0)` raises `ProcessLookupError`.
   - Windows: the job's `ActiveProcesses` is 0.

   Seam points: `run.after_exit` after step 2, `run.after_group_empty` after
   step 4.
5. **Return.** The call returns `StagedRun(returncode, stdout, stderr,
   timed_out, group_empty)`.

**Publishability.**

- A staging area becomes **unpublishable** for the rest of its life if any run
  timed out or ended with `group_empty=False`.
- `publish_entry` refuses unpublishable staging.
- After a timeout, the operation fails. Build-method fallback in
  `_build_grammar` does not continue into the same staging.
- If the group was confirmed empty, `discard_staging` may remove the staging.
  Otherwise the staging is retained and reported.

**Parent death.**

- POSIX: the group survives and can write only inside that staging. That
  staging is never published, because only its owner publishes from it and
  the owner is dead. It is never pruned.
- Windows: closing the job handle kills every descendant.

**Escapes (scoped out).** A POSIX descendant that leaves its process group
(`setsid`, daemonizing) is not tracked. If it outlives confirmation, it could
write into an entry after publication. `git`, `tree-sitter`, the C compilers
and `make` do not daemonize. A build tool that does is unsupported. On Windows,
breakaway is impossible because the job lacks the breakaway limits.

### Input routing

The installer pipeline keeps every input operation-owned through its last use:

1. `create_staging(root)` registers `.txn/staging/<operation-id>/` and its
   staged namespace directories.
2. `git clone` and `git checkout` run through `run_in_staging`. The clone
   lands in `<staging>/downloads/tree-sitter-<language>`. `_get_commit_hash`
   reads it there.
3. The build runs through `run_in_staging` from that staged source into
   `<staging>/builds/<language>/`. This includes `make` in the staged source
   directory, and `_build_with_make`'s copy of the result. Validation reads the
   staged artifact.
4. The installation commit (Primitive 3) passes the **staged** artifact as
   `source` to `publish_native_grammar`. `publish_native_grammar` copies it into
   a sibling temporary file, so nothing published depends on the staging after
   the commit.
5. Only **after** the installation commit, which is the last consumer, does
   the operation call `publish_entry` for the staged download and build. An
   operation that failed publishes no cache entry.
6. `discard_staging` removes what remains of the staging.

No participant reads a published `downloads/` or `builds/` entry outside the
lock. The core code reuses no published entry: it clones afresh every time.
If a future consumer wants to reuse one, it must copy it into its own staging
under the lock first.

### Cache-entry publication

`publish_entry(staging, namespace, name)` runs under the lock:

1. **Check the staged entry.** Refuse unpublishable staging, a reserved name,
   or a missing staged entry `<staging>/<namespace>/<name>`.
2. **Stamp it.** Set the *staged* entry's own mtime to now, without following
   links. A later rename never makes it older. A failure here fails the
   publication before any rename.
3. **Retire the existing entry**, if `namespace/name` exists. Walk it (nested
   root refusal), then rename it to
   `.txn/retired/<operation-id>/<namespace>/<name>`. Seam point
   `publish.after_retire` follows. If retirement fails, the publication fails
   and the existing entry is untouched.
4. **Promote.** Seam point `publish.before_promote`, then rename the staged
   entry to `namespace/name`.
5. **Handle promotion failure.** If promotion fails after the Windows retry,
   rename the retired entry back to `namespace/name`. If that also fails, the
   published name is **absent**, the old generation is garbage in `.txn/retired/`,
   and the new one remains in staging. The call raises
   `CacheTransactionError` naming all three locations.

This is two renames, not one atomic publication. Readers and crashes can see
the old entry, the new entry, or **no entry**. An absent `downloads/` or
`builds/` entry is acceptable because these entries are regenerable caches: the
next install clones and builds afresh, and nothing reads them for reuse.
Copied sources may keep old mtimes (as `copy2` does); the stamp still makes
the entry ineligible for age pruning until its own cutoff passes.

`remove_entry(root, namespace, name)` serves `_cleanup_cache` and the removal
of an existing download. It walks the entry (nested-root refusal), retires it
under the lock, and deletes it outside the lock. There is no age test.

### Pruner

`prune_entries(root, namespace, *, cutoff)`:

1. **Enumerate.** List non-reserved top-level entries with no lock; this is
   only a candidate list. Seam point `prune.after_enumerate`.
2. **Re-check under the lock.** For each candidate, take the lock and repeat
   the no-follow walk. An entry is eligible only if:
   - its own `lstat` mtime is older than `cutoff`;
   - every descendant's `lstat` mtime is older than `cutoff`, with links
     counting as leaves.

   A descendant `.txn.lock` raises `NestedRootError`, which is reported and
   skipped. Seam point `prune.after_recheck`.
3. **Retire.** Still under the lock, rename the eligible entry to
   `.txn/retired/<operation-id>/<namespace>/<name>`, then release the lock. A
   candidate that vanished or became ineligible is skipped and not counted.
4. **Delete** the retired tree with the anchored deleter, outside the lock.
5. **Count truthfully.**
   - `entries_removed` counts entries retired by this call, matching the
     existing top-level `files_removed` counter.
   - `bytes_freed` sums the `lstat` `st_size` of regular files actually
     unlinked by this call. Links count zero, and nothing is counted before a
     successful unlink.
   - Bytes that fail to delete are reported in `errors` and not counted.
6. **Claim old garbage** (see [Retired garbage](#retired-garbage)).
7. **Report staging.** Staging is never deleted. Staging directories older
   than `cutoff` are logged as retained, with their paths.

`GrammarManager.cleanup_cache` keeps its signature and result keys
(`files_removed`, `bytes_freed`, `directories_cleaned`, `errors`).

### Retired garbage

Several deleters can meet in `.txn/retired/`:

- the owner deleting its own retired tree outside the lock;
- a later prune deleting leftover trees.

A prune **claims** another operation's `.txn/retired/<other-id>/` by renaming
it, under the lock, into `.txn/retired/<own-id>/claimed/<other-id>`. It then
deletes the claimed tree. If the original owner is still deleting, `ENOENT` on
either side means "already deleted" (containment rule 5). Each byte is
therefore counted at most once, by the deleter whose `unlink` succeeded.

## Primitive 3 — installation commit and rollback (treesitter-chunker#363)

Today `_create_rollback_point` records metadata only, `_perform_rollback`
deletes the previous metadata while logging that it restored, and
`_install_grammar_file` copies in place. The contract replaces all three.

### Pins (roadmap runner decision D-a)

The installer gets pins through ADMIT SL-core's constructor change,
`GrammarInstaller(cache_dir=None, build_timeout=300, max_retries=3, *,
trusted_artifacts=None)`, which treesitter-chunker#538 fixes in
`docs/development/native-validation-contract.md`. Forwarding follows
`GrammarManager` → `GrammarRegistry` → `GrammarInstaller`. Every installer
publication through `publish_native_grammar` therefore merges only after that
change is on main.

For the language being installed, the installer applies treesitter-chunker#538's
per-probe rule:

- If `trusted_artifacts.get(language)` is a Mapping with a `str` `sha256`, the
  installer builds the one-field record `{"sha256": value}` (the *pin record*).
- Otherwise the install fails with an untrusted result **before the commit
  section**. Nothing is captured or mutated, and no probe runs.

**Production restore limit.** IF-0-ADMITPIN-1 holds one pin per language, so
publishing a new revision means the operator has already moved the pin to it.
In production, `restore` therefore receives the new revision's pin, and the
artifact-republication branch (below) fails closed. That is safe, and this
contract states it plainly. EC-TXN-3's "restores the previous artifact" is met
in production by the [commit order](#installation-commit): a failed update
never replaces the artifact. Republishing the artifact with the previous
revision's pin happens only where a caller holds that pin, such as fixtures.
No previous approval is ever derived from a rollback digest.

### Paths, metadata format and manifest

**Paths.** Both paths must lie under `<root>/grammars/`:

- The **destination** is the path the requested priority selects:
  `grammars/lib<language>.so` for `USER`, otherwise
  `grammars/<priority>/lib<language>.so`.
- The **metadata** path is `grammars/<language>_install_info.json`.

A previous installation at a different priority path is never touched; the
restored metadata points back to it. If recorded metadata points outside
`grammars/`, the install fails before the commit section with
`ContainmentError`.

**Metadata format.** The metadata keeps today's fields and adds
`"artifact_sha256"`, the pin record's `sha256`. That is the digest the artifact
must have once publication succeeds. It is serialized canonically as
`json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"`,
UTF-8. `InstallationInfo` ignores unknown keys, so older readers keep working.

**Detection.** A metadata/artifact mismatch is detectable: `artifact_sha256`
differs from the destination's SHA-256, or from the `artifact_sha256` of a
`NativeProbeResult` that admitted the destination.

**`publish_installation_metadata(root, language, document, *, timeout) -> str`**
writes those canonical bytes to the metadata path under the lock. It uses
Primitive 1's no-follow temporary-file-and-replace mechanics, including the
Windows retry, and returns the SHA-256 of the bytes written. Seam point
`metadata.after_replace` follows the replace. Restoring metadata uses the same
byte replace with the captured bytes.

**`read_installation_metadata(root, language, *, timeout)`** reads the metadata
file no-follow under the lock. It returns the parsed document, or `None` if the
file is absent. `_load_installation_info` calls it. Today's rule is kept: a
malformed document or a `ContainmentError` is warned about and treated as
`None`. `CacheLockTimeoutError` propagates. Callers report it as an error and
never as "not installed".

**Rollback manifest.** The manifest is
`.txn/rollback/<operation-id>/rollback.json`. It is written last, through a
temporary file and replace, and its directory is `fsync`ed. Paths are
root-relative with `/` separators:

```json
{
  "schema": "cache_rollback.v1",
  "operation_id": "<32 lowercase hex>",
  "language": "<language>",
  "created_ns": 0,
  "artifact": {
    "path": "grammars/lib<language>.so",
    "previous_sha256": "<64 hex> | null",
    "previous_copy": "artifact.prev | null",
    "intended_sha256": "<64 hex>"
  },
  "metadata": {
    "path": "grammars/<language>_install_info.json",
    "previous_sha256": "<64 hex> | null",
    "previous_copy": "metadata.prev.json | null",
    "intended_sha256": "<64 hex>",
    "intended_copy": "metadata.next.json"
  }
}
```

`created_ns` is an integer (`time.time_ns()`); the value shown is a
placeholder.

A rollback directory **without** `rollback.json` is an incomplete capture.
Capture precedes every mutation, so such a directory is safe to delete.

### Installation commit

After the build has completed in staging, with its group confirmed empty, and
the pin record has been obtained, the installer runs one `cache_lock` section
with the steps below.

1. **Capture.**
   `create_rollback_point(root, language=..., artifact=<destination>,
   metadata_document=<new document>, artifact_sha256=<pin sha256>)`:
   - copies the current destination artifact, if any, to `artifact.prev`;
   - copies the current metadata, if any, to `metadata.prev.json`;
   - writes the new document's canonical bytes to `metadata.next.json`.

   Sources are opened no-follow, and copies are created with `O_EXCL` and
   `fsync`ed. Each previous copy's SHA-256 is computed while copying with
   `hashlib`. The manifest is written last. Seam point
   `rollback.after_capture`.
2. **Publish metadata** with `publish_installation_metadata`. The returned
   digest must equal `intended_sha256`; if it differs, go to step 4.
3. **Publish the artifact** with
   `publish_native_grammar(<staged artifact>, destination, language,
   provenance=<pin record>)`. This is the last fallible mutation.
   `invalidate(destination)` then runs once, and is **non-fatal** (below).
   - If the result is supported, go to step 5.
   - If it is unsupported, or raised `OSError`, the destination is unchanged
     (an IF-0-HOTFIX-1 guarantee). Go to step 4.
4. **Restore on failure.** Run
   `restore(point, provenance=<pin record>, invalidate=...)`. The install
   returns failure, with the restore outcome in its message. If the restore
   did not verify, the message includes the retained rollback path.
5. **Discard on success.** `discard_rollback_point(point)`. A discard failure
   is a warning naming the retained path; the install still succeeds.

After the section, the operation publishes its cache entries (Primitive 2)
and discards its staging.

**Invalidation is non-fatal.** If `invalidate` raises, the exception is logged
and added as a warning to the result (`RestoreResult.warnings`, or the
install's warnings). It never triggers a restore and never changes the
outcome. Nothing fallible follows step 3 in the forward path, because step 5
cannot fail the install.

**Supersession.** All participants serialize on the lock, so between steps 1
and 4 the pair can change only through a non-participant. `restore` still
checks for that.

### Restore

`restore(point, *, provenance, invalidate, timeout)` runs under the lock and is
reentrant inside the commit section. It decides on the **artifact and
metadata as a pair**, artifact first.

Let `Ap`/`Mp` be the previous digests (or absent) and `Ai`/`Mi` the intended
digests from the manifest. It observes the current digests `Ac`/`Mc`.

| `Ac` | `Mc` | Action |
|---|---|---|
| `Ap` | `Mp` | Nothing to do. The pair is already at the rollback state. |
| `Ap` | `Mi` | Restore the metadata to `Mp` (byte replace, or retire it if `Mp` is absent). |
| `Ai` (≠ `Ap`) | `Mi` | Restore the artifact first, then go to the artifact rules below. |
| `Ai` (≠ `Ap`) | `Mp` | Not producible by participants: metadata is always published before the artifact. Treat as `superseded`. |
| anything else | anything else | `superseded`: touch neither file, report, retain the point. |

**Artifact rules (row 3).**

1. If `Ap` is absent, retire the destination under the lock. It then counts as
   at the rollback state.
2. Otherwise, check the rollback copy against `Ap` with `hashlib`; identity
   checks never pass through an admission API. On mismatch, fail and change
   nothing.
3. Otherwise, seam point `restore.before_artifact`, then call
   `publish_native_grammar(<artifact.prev>, destination, language,
   provenance=provenance)`, then call `invalidate(destination)` (non-fatal).
4. **Only if the artifact ends at `Ap`** (seam point `restore.before_metadata`)
   restore the metadata to `Mp`.
5. If the artifact stays at `Ai`, for example because the probe rejects the
   copy without the previous revision's pin, **leave the metadata at `Mi`**.
   The metadata then describes the artifact that remains. Report failure and
   retain the point.

`RestoreResult` fields:

- `restored` is true only if the pair ends at (`Ap`, `Mp`).
- `artifact_restored` and `metadata_restored` report each file.
- `superseded`, `errors` and `warnings` (which include invalidation failures)
  report the rest.

Restore never falls back to an unadmitted artifact replacement, and never
uses a rollback digest as `provenance`.

**Windows.** IF-0-HOTFIX-1 raises `OSError` when Windows refuses to replace a
library that a process has loaded, and the destination is then unchanged.
Restore does not retry that call, because each attempt re-runs the probe. A
refusal fails the restore and retains the point. The installer process holds
no handle to the destination, because it validates through the probe's
private snapshot. EC-TXN-3 shows this on a real Windows run.

### Installation removal

`remove_installation(root, language, *, timeout)` serves `remove_grammar`. In
one lock section it:

1. reads the metadata no-follow;
2. requires the recorded `install_path` to lie under `grammars/`;
3. retires the artifact, then the metadata, to
   `.txn/retired/<operation-id>/grammars/`;
4. deletes them outside the lock.

`remove_grammar` then calls `remove_entry` for the cache entries. It is a full
participant: it cannot interleave with a commit, so a restore can never bring
back an installation that was removed. A crash between the two retirements
leaves metadata that describes a missing artifact, which today's health check
already reports as `missing`.

On Windows, deleting a retired library that a process still has loaded fails.
It stays in `.txn/retired/`, is reported, and a later prune claims it.

### Remaining windows

**Readers.** Participant readers (`read_installation_metadata`) never observe
the middle of a commit. Two readers are not pair-consistent:

- artifact-only readers (`GrammarRegistry` discovery);
- a reader that reads metadata under the lock and later loads the artifact
  without it.

Either may see the artifact of a later commit. The recorded `artifact_sha256`
makes that detectable.

**Crash windows.**

| Crash point | Resulting pair | Rollback point |
|---|---|---|
| Inside step 1 | Unchanged | Incomplete (no manifest), safe to delete |
| After step 2, before step 3's replace | Metadata `Mi` with artifact `Ap`: the metadata names a digest that the artifact lacks | Retained with manifest |
| After step 3's replace | (`Ai`, `Mi`), consistent | Retained, discardable |

This middle window spans the probe. It is detectable, and it is not repaired
automatically; see the operator procedure below.

## IF-0-HOTFIX-1 citation

**Cited signature.** IF-0-HOTFIX-1 as published in the treesitter-chunker#162
PR (treesitter-chunker#539) body under the heading `IF-0-HOTFIX-1 signature`.
It was first published at head `7710fb7c699db33c244c95bf7d24d8730b91ea5b` and
re-checked unchanged at head `cf1de762020769878f10dd7fdb5e50278016c434`:

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

The contract relies only on these guarantees:

1. A sibling temporary copy of `source` is admitted with `probe_native_grammar`
   and the caller's `provenance`.
2. `os.replace` onto `destination` happens only if the result is supported, and
   never writes or truncates the existing inode.
3. On an unsupported result or an `OSError`, the staged copy is removed and
   `destination` is unchanged.
4. Cache invalidation is the caller's job.

**Staged-file naming is IF-0-HOTFIX-1's choice.** Nothing here depends on the
staged file's name, prefix or suffix. That includes the pending
treesitter-chunker#539 change to a suffix that `*.so` scans do not match. The
staged file lives in `grammars/`, which the pruner never enters. A staged file
left by a crash is outside every primitive here; see the operator procedure.

This contract uses the function unchanged for forward publication and artifact
restoration. It defines no second native publish path and splits out no
admission-free replacement step. The primitives check containment before the
call: a link at the destination or metadata path refuses the install before
the commit section, so IF-0-HOTFIX-1's "replaced, not followed" behavior never
applies to a contained installation.

**Re-review trigger.** treesitter-chunker#539 was still open when this was
cited. If its signature or the guarantees above change before IF-0-TXNSPEC-1
is approved, this section is reviewed again (roadmap TXNSPEC scope notes).

## Crash states and operator recovery

**Possible states after a crash.** No automatic crash recovery exists (gap 2).
A crash can leave:

| Leftover | Meaning | Safe action |
|---|---|---|
| `.txn/staging/<id>/` | A writer died, or its descendants could not be confirmed gone | Delete it once no install is running |
| `.txn/retired/**` | Garbage, which can include the old generation of a cache entry whose republication was interrupted | Always safe to delete; any prune claims it |
| An absent `downloads/` or `builds/` entry | A republication was interrupted between its two renames | None needed; the next install regenerates it |
| `.txn/rollback/<id>/` without `rollback.json` | An incomplete capture, before any mutation | Delete it |
| `.txn/rollback/<id>/rollback.json` | An interrupted or failed commit | Follow the procedure below |
| `<root>/.validation_cache.json.<id>.tmp`, `grammars/.<language>_install_info.json.<id>.tmp` | Primitive 1 temporary files | Delete them once no participant is running |
| An IF-0-HOTFIX-1 staged sibling in `grammars/` | The probe or replacement was interrupted | Delete it once no install is running; the name is IF-0-HOTFIX-1's |

**Procedure for a retained rollback point.**

1. Make sure no `grammar` command or other participating process is running
   on this root.
2. Read `rollback.json`. Compute the SHA-256 of the current
   `artifact.path` and `metadata.path`.
3. If the artifact equals `artifact.previous_sha256` (or both are absent),
   restore the metadata:
   - copy `metadata.prev.json` over `metadata.path`, or delete `metadata.path`
     if `previous_copy` is null;
   - then delete the rollback directory.
4. If the artifact equals `artifact.intended_sha256` and the metadata equals
   `metadata.intended_sha256`, the commit had completed. Keep the new
   installation and delete the rollback directory. To go back to the previous
   revision, install it normally with its pin; do not copy `artifact.prev` by
   hand. A manual copy bypasses publication, although every later load is
   still admitted normally.
5. Any other combination was produced by a non-participant. Leave the files,
   decide manually, and keep the rollback directory until you have.

## Disposition of the treesitter-chunker#364 blocking gaps

The gaps are listed in the final CLEANUP verdict on treesitter-chunker#323, at
the treesitter-chunker#364 head `4465de92`.

| # | Gap | Disposition | Rationale |
|---|---|---|---|
| 1 | Child-writer lifetime across parent death | **addressed**, with one scoped-out escape | Writer subprocesses run only through `run_in_staging`, in their own process group or job, with `cwd` inside private staging. Before anything is published or discarded, the whole group is killed and confirmed empty. A timeout or an unconfirmed group makes the staging unpublishable for good. On parent death, POSIX descendants can write only into staging that is never published (only its dead owner could publish it) and never pruned; on Windows, closing the job kills them. The lock is never inherited. The only subprocess under the lock is the probe child, which is bounded by its timeout, holds no lock handle and reads only its private snapshot; parent death during the probe releases the lock through the kernel. **Scoped out:** a POSIX descendant that leaves its process group (daemonizing). No supported build tool does. |
| 2 | Durable operation and initialization recovery | **addressed** (initialization, state reporting); **scoped out** (automatic crash recovery) | No persistent authority state exists: no journal, no generation counter, no root registration. The lock file carries no state, and creating it idempotently is the whole initialization. A missing `validation_cache.json` means empty. Crash states are enumerated honestly. A cache entry can be old, new or **absent**; absent is acceptable for regenerable caches. An installation can be left with metadata naming a digest its artifact lacks; that is detectable through `artifact_sha256`, and repairable from the self-describing `rollback.json`. Leftover temporary and staged files are listed. An operator procedure exists. Automatic recovery is scoped out: no consumer's acceptance requires it, and a journal was what failed review. |
| 3 | Transactional deletion retirement | **addressed** | Pruning, explicit removal, installation removal and republication all retire whole items by rename under the lock, and delete only from `.txn/retired/`. Republication's two-rename sequence has defined failure handling: rename back, otherwise report all three locations. Garbage is claimed by rename, and `ENOENT` is tolerated, so concurrent deleters never double-count or report spurious errors. |
| 4 | Enforceable nested-root detection | **addressed** for sequential initialization; overlapping roots otherwise **scoped out** (unsupported) | `open_cache_root` refuses roots equal to or below an ancestor root's `downloads`, `builds` or `.txn`, and repeats the check after initialization. Reserved names are never entries. Every retirement path (pruner, `remove_entry`, `publish_entry`) refuses entries that contain a `.txn.lock`. Every lock acquisition re-checks root identity. Residual risk: an inner root initialized for the first time inside the very entry an outer root is retiring at that moment (see [Nested roots](#nested-roots)). |
| 5 | No-follow control-file creation | **addressed** | Containment rule 1 covers the lock file, markers, temporary files, staging, retirement, rollback directories and manifests: POSIX `O_NOFOLLOW` with `dir_fd`; `O_EXCL` unique names; Windows `lstat`/`fstat` identity and reparse checks. |
| 6 | Concrete portable entry keys | **addressed** | The helper keeps no key map. Entries are their top-level directory-entry names; installer names are restricted by `_valid_language_name`; reserved names are excluded. Operation IDs are lowercase `uuid4` hex. Manifest paths are root-relative with `/`. Validation keys stay SHA-256 hex. Behavior on case-insensitive filesystems is stated. |
| 7 | Truthful real-consumer and fixture routing | **addressed** | The Scope tables list every participant, including installation readers and removers, and every non-participant with its real consequence, including the `cleanup_empty_directories` overlap. Input routing keeps inputs owned through the last consumer. Required tests drive real public methods. The only substitution is a `git` shim on `PATH`. Each test asserts that its named seam point was reached. |

**Threats outside every row:**

- hostile processes running as the same user, and other non-participating
  mutators;
- substitution of the root's ancestors between identity checks;
- cross-host and network-filesystem locking;
- the non-participant paths listed in [Scope](#scope).

## Test seam

The helper module has a private seam,
`_BARRIER: Callable[[str, Mapping[str, str]], None] | None`. It is `None` in
production. When set, the helper calls it with a stable point name and a
context mapping:

- `primitive`: the public helper function that hit the point, or `cache_lock`;
- `root`;
- `operation_id`;
- where relevant, `namespace` and `name`.

Tests install the seam inside a subprocess, filter on the context, and block on
a pipe or event file, never on sleeps. The seam only pauses execution (or, in
crash tests, calls `os._exit`); it never replaces behavior.

| Point | Where |
|---|---|
| `lock.before_acquire` | Before the first acquisition attempt |
| `lock.contended` | After the first failed non-blocking attempt |
| `lock.acquired` | After the root lock is taken |
| `root.after_init` | After lock and control-area creation, before the post-initialization check |
| `json.after_read` / `json.before_replace` | Primitive 1 steps 3 and 5 |
| `run.after_exit` / `run.after_group_empty` | `run_in_staging` steps 2 and 4 |
| `publish.after_retire` / `publish.before_promote` | `publish_entry` steps 3 and 4 |
| `prune.after_enumerate` / `prune.after_recheck` | Pruner steps 1 and 2 |
| `rollback.after_capture` | Commit step 1 |
| `metadata.after_replace` | `publish_installation_metadata` |
| `restore.before_artifact` / `restore.before_metadata` | Restore row 3 |

## Required TXN tests and named mutations

Each test passes on the fix and fails under its mutation, and the PR records
both runs (VB-2).

**Ground rules.**

- Scratch data goes under `$TMPDIR` in temporary roots. No operator files are
  used.
- No network is used. The **only permitted substitution** is a `git` shim on
  `PATH` inside the test subprocess. It materializes a local fixture
  repository, as treesitter-chunker#539's VB-1 did, and can copy sources with
  `copystat` to produce old mtimes.
- Builds, probes and helper code stay real. Patching `_download_grammar`,
  `_build_grammar` or the helper is forbidden.
- Restore's post-publication branch is tested by calling `restore` directly
  with a real rollback point whose intent was published.

| Consumer | Deterministic barrier test | Named mutation that must fail it |
|---|---|---|
| treesitter-chunker#370 | **Two writers.** Two real `GrammarValidator` instances are created before either writes. Writer A persists a unique record through `validate_grammar` and pauses at `json.before_replace` while holding the lock. Writer B starts, and the test observes B's `lock.contended`. A resumes. Both records are on disk, checked by exact key or `any(...)` (the treesitter-chunker#401 note). Run in both orders. Use a real rejection record from a non-library fixture if no native fixture exists. | `stale_validation_snapshot`: write the instance snapshot instead of merging. |
| treesitter-chunker#370 | **Writer and pruner.** Writer A pauses at `json.before_replace`. `cleanup_cache` starts, and the test observes its `lock.contended`. A resumes. A's fresh record survives, and expired records are pruned by the existing cutoff rule. | `pruner_stale_rewrite`: the pruner reads before taking the lock and writes that read. |
| treesitter-chunker#370 | **Outside-symlink sentinel.** `validation_cache.json` is a symlink to an outside sentinel. The writer and the pruner each report a containment error, the sentinel's bytes are unchanged, and constructing a validator still succeeds. | `follow_validation_symlink`: open the target following links. |
| treesitter-chunker#323 | **Writer and pruner.** `cleanup_cache` pauses at `prune.after_enumerate` with an expired candidate. A real `install_grammar` (with the shim producing old-mtime sources) republishes the same name. Resume: the new entry survives and is not counted in `bytes_freed`. Separate cases cover entries that are fully expired, exactly at the cutoff, and denied deletion, each with truthful counts. | `prune_without_recheck`: use enumeration-time eligibility. `trust_copied_mtime`: skip the stamp. `overcount_failed_removal`: count bytes before unlink. |
| treesitter-chunker#323 | **Link boundaries.** An old entry holds a file symlink, a directory symlink, a dangling link, and (on Windows) a junction, each pointing to an outside sentinel. The links are removed as leaves; the sentinels are unchanged and count zero bytes. Run on Linux, macOS and Windows. | `follow_cache_link`: traverse link targets. |
| treesitter-chunker#323 | **Descendants.** The shim spawns a grandchild that keeps writing into its cwd. (a) Normal exit: `run.after_group_empty` is reached before `publish_entry`, the grandchild is gone, and the published bytes stay stable. (b) Timeout: the install fails, nothing is published, and the group is killed. (c) Parent death: the installer is killed at `run.after_exit`. On POSIX, a later install and a prune neither publish nor delete that staging, and the staging is retained. On Windows, the grandchild is gone. | `publish_before_group_empty`: skip the kill and confirmation. `fallback_after_timeout`: continue to the next build method in the same staging. |
| treesitter-chunker#323 | **Owned inputs.** Real installer A pauses at its commit section's `lock.before_acquire` (context `primitive=cache_lock`). Installer B completes for the same language, then `remove_entry` removes B's cache entries. A resumes, installs from its own staging, and a fresh subprocess parses A's revision. | `consume_published_input`: A builds or installs from the published `builds/` path. |
| treesitter-chunker#323 | **Republication failures.** (a) A crash (`os._exit`) at `publish.after_retire`: the name is absent, the old generation is in retired, and the staging is retained. The next prune deletes the garbage, and the next install republishes. (b) At `publish.after_retire`, the test removes the staged entry (as a non-participant): promotion fails, the old entry is renamed back, and the error is reported. | `no_rename_back`: skip the rename back. |
| treesitter-chunker#323 | **Nested roots.** (a) Open roots equal to and below `R/downloads`, `R/builds` and `R/.txn` after `R` is initialized: all refused. (b) Initialize the inner root first at `R/downloads/x`, then `R`: the pruner, `remove_entry` and republication each refuse, and the inner lock and data stay intact. (c) At the inner root's `root.after_init`, move the inner directory: the post-initialization check fails. | `nested_root_retire`: skip the descendant check in `remove_entry` and `publish_entry`. |
| treesitter-chunker#363 | **Failed update restores the pair.** Install revision A of a real compiled fixture grammar with A's pin. Update to B with B unpinned: it fails before the commit section, and nothing changes. Update to B with B's pin and a probe that rejects (a corrupted staged B): the metadata is restored, and the pair equals A's (artifact digest and metadata bytes). A fresh subprocess parses A's revision. Also cover a `False`-returning failure. Run on Windows, where the restore succeeds (handle release). | `omit_restore`: skip the restore. `rollback_removes_metadata`: today's behavior. |
| treesitter-chunker#363 | **Restore branches (direct `restore`).** A real rollback point is followed by a real publication of B. (a) With A's pin, both files return to A. (b) Without A's pin, artifact B **and metadata B** remain, `restored=False`, and the point is retained. (c) A non-participant replaces the destination at `restore.before_artifact`: `superseded`, and neither file is touched. (d) A raising `invalidate` gives the same outcomes plus a warning. | `restore_without_admission`: replace without the probe. `restore_metadata_independently`: decide the metadata without the artifact. |
| treesitter-chunker#363 | **Serialization and crash.** (a) Installer A pauses at `metadata.after_replace`. Installer B, and a `read_installation_metadata` reader, each hit `lock.contended`, and the reader never observes metadata B with artifact A. (b) A crash at `metadata.after_replace` leaves `Mi`/`Ap`. The mismatch is detectable through `artifact_sha256`, and following the operator procedure on `rollback.json` restores A's pair. (c) The lock descriptor is not inheritable (`os.get_inheritable` is false) during the probe. (d) `remove_grammar` during a paused commit waits on the lock; afterwards, no removed installation comes back. | `commit_without_lock`: run steps 1–4 as separate lock sections. `inheritable_lock_fd`: open the lock inheritable. |

The TXN PRs keep `tests/test_core_grammar_cache_cleanup.py` and the existing
helper-cache tests passing. They change an existing assertion only where it
pins the lost-update behavior, such as treesitter-chunker#401's `all(...)`
lookup.

## Signatures

These are the public signatures of `chunker/grammar_management/_transactions.py`,
frozen here as text only. This PR adds no stub module: a new package file
would change the pinned wheel payload inventory in
`tests/test_supported_wheel_verification.py`. TXN SL-cache creates the module
and updates that inventory in the same PR. The module imports only the
standard library at module level. It imports IF-0-HOTFIX-1 lazily, inside
`restore`.

```python
DEFAULT_LOCK_TIMEOUT: Final[float] = 60.0
LOCK_FILE_NAME: Final[str] = ".txn.lock"
CONTROL_DIR_NAME: Final[str] = ".txn"
MARKER_NAME: Final[str] = ".txn-keep"
ROLLBACK_MANIFEST_NAME: Final[str] = "rollback.json"
Namespace = Literal["downloads", "builds"]

class CacheTransactionError(Exception): ...
class CacheLockTimeoutError(CacheTransactionError): ...
class ContainmentError(CacheTransactionError): ...
class NestedRootError(ContainmentError): ...

@dataclass(frozen=True)
class StagingArea:
    root: Path
    operation_id: str
    path: Path  # publishability is tracked in-process by the helper

@dataclass(frozen=True)
class StagedRun:
    returncode: int | None  # None: timed out
    stdout: str
    stderr: str
    timed_out: bool
    group_empty: bool

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
    path: Path                       # .txn/rollback/<operation-id>/
    artifact: Path                   # destination chosen by priority
    metadata: Path                   # grammars/<language>_install_info.json
    previous_artifact_sha256: str | None
    previous_metadata_sha256: str | None
    intended_artifact_sha256: str
    intended_metadata_sha256: str

@dataclass(frozen=True)
class RestoreResult:
    restored: bool
    artifact_restored: bool
    metadata_restored: bool
    superseded: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

def open_cache_root(root: Path) -> Path: ...
def cache_lock(root: Path, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> AbstractContextManager[None]: ...
def read_json_records(root: Path, name: str, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> dict[str, Any]: ...
def update_json_records(root: Path, name: str, mutate: Callable[[dict[str, Any]], dict[str, Any]], *, reset_malformed: bool = False, timeout: float = DEFAULT_LOCK_TIMEOUT) -> dict[str, Any]: ...
def create_staging(root: Path, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> StagingArea: ...
def run_in_staging(staging: StagingArea, argv: Sequence[str], *, cwd: Path, timeout: float, env: Mapping[str, str] | None = None) -> StagedRun: ...
def publish_entry(staging: StagingArea, namespace: Namespace, name: str, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> Path: ...
def discard_staging(staging: StagingArea, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> PruneResult: ...
def remove_entry(root: Path, namespace: Namespace, name: str, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> PruneResult: ...
def prune_entries(root: Path, namespace: Namespace, *, cutoff: float, timeout: float = DEFAULT_LOCK_TIMEOUT) -> PruneResult: ...
def read_installation_metadata(root: Path, language: str, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> dict[str, Any] | None: ...
def publish_installation_metadata(root: Path, language: str, document: Mapping[str, Any], *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> str: ...
def remove_installation(root: Path, language: str, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> PruneResult: ...
def create_rollback_point(root: Path, *, language: str, artifact: Path, metadata_document: Mapping[str, Any], artifact_sha256: str, timeout: float = DEFAULT_LOCK_TIMEOUT) -> RollbackPoint: ...
def restore(point: RollbackPoint, *, provenance: Mapping[str, Any] | None, invalidate: Callable[[Path], None], timeout: float = DEFAULT_LOCK_TIMEOUT) -> RestoreResult: ...
def discard_rollback_point(point: RollbackPoint, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> None: ...
```

- **Implicit validation.** `open_cache_root` validates the root, creates the
  lock file and control area (with markers), runs the nested-root checks
  before and after initialization, and returns the root path unchanged. Every
  other function performs the same validation implicitly. Consumers call
  `open_cache_root` at construction so that they fail early.
- **Reentrancy.** `cache_lock` is reentrant on one root within a process, and
  it is how the installation commit holds one section. The other functions
  take the lock themselves, reusing it if it is already held.
- **Language names.** `language` arguments must pass `_valid_language_name`.
- **Rollback-point paths.** `create_rollback_point` requires `artifact` to be
  the priority-selected destination under `grammars/`. It derives the
  metadata path from `language`.

## TXN lane assignment

Roadmap runner decision D-b amends the `core.py` region list in the roadmap's
Execution Notes (`specs/phase-plans-v4.md`):

- **SL-cache, treesitter-chunker#370:** the helper module, plus the
  GrammarValidator cache region.
- **SL-cache, treesitter-chunker#323:** the GrammarInstaller
  download/build/cache-entry functions (`_download_grammar`, `_build_grammar`
  and the `_build_with_*` helpers, `_get_commit_hash`, `_cleanup_cache`), the
  staging routing in `install_grammar`, and
  `GrammarManager.cleanup_cache`/`_cleanup_directory`.
- **SL-rollback, treesitter-chunker#363:** the installation commit section in
  `install_grammar`, `_create_rollback_point`, `_perform_rollback`,
  `_install_grammar_file`, `_save_installation_info`,
  `_load_installation_info`, `_remove_installation_info`, and
  `GrammarInstaller.remove_grammar`/`GrammarManager.remove_grammar`.
  treesitter-chunker#363 merges only after ADMIT SL-core's
  `GrammarInstaller(trusted_artifacts=)` change (decision D-a). It rebases on
  treesitter-chunker#323.
