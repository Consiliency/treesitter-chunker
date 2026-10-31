# Native validation contract

> Maintainer/internal documentation. This page is intentionally omitted from public navigation.

Status: corrected design independently APPROVED for the bounded successor to
treesitter-chunker#372 / treesitter-chunker#159, including treesitter-chunker#389.
The implementation is a review candidate. Its controlled Windows diagnostic
evidence is recorded in `safeload-verification.md` for independent evaluation.
Implementation review, platform verification and final acceptance remain pending.
Under the owner's manual acceptance amendment, formal IF-0-SAFELOAD-1 is deferred
and unproduced. Harness is not a current product prerequisite, and no formal
approval is claimed. Original design and historical HOLDs remain. Neither this
document nor design approval establishes a repaired or accepted implementation.
treesitter-chunker#508 and treesitter-chunker#509 remain independently
unexplained. The owner's 2026-10-23 amendment permits acceptance despite those
two missing cause explanations only if all four CODE seats and separate
independent Astra explicitly approve the documented residual risks and required
CI passes. Any HOLD still blocks landing. Original failed runs, diagnostic
limitations and open issues remain; no other provenance, containment or
correctness requirement changes. See the owner-approved amendment in
`plans/phase-plan-v3-SAFELOAD.md`.

## Scope and trust

GrammarAnalyzer, SmartGrammarManager and UserGrammarTools use one shared
admission and isolated probe in `chunker.grammar.integrity`. Registry discovery,
central GrammarValidator, CLI validation and installer publication remain
explicitly outside this first implementation; GRAMMARS integrates those paths.
The low-level compiled loader remains a caller-trusted primitive. Existing
ambient discovery paths are not presumed safe merely because they predate this
contract.

treesitter-chunker#362 tracks remaining registry, central and CLI validation,
`grammar/validator.py`, `grammar/download.py`, `grammar_manager.py`, cached
verdict reuse and analyzer dependency inspection. GRAMMARS integrates or retires
each discovery path. The public dependency inspector must not be treated as
secured merely because the analyzer uses this probe. Pack-managed artifacts
have a separate pinned supplier trust boundary.

Each candidate requires an independently approved SHA-256 pin in caller-owned
configuration. Constructors accept optional keyword-only `trusted_artifacts`,
keyed by language with the existing `sha256` field. Copy records at construction
and forward them through tools to the manager. Missing configuration fails
closed. An allowed URL, filename, directory, previous probe, stat tuple or
self-authored neighboring manifest confers no trust. Never hash discovered
bytes and promote that hash into an approval. Reviewed fixture builds may
deliberately supply their hashes; arbitrary downloaded source is not made safe
to build by this contract.

Existing unpinned discoveries become unsupported. Embedding callers migrate by
supplying pins from independently approved builds/configuration. No trust-all
switch or automatic trust of freshly cloned output is introduced.

The production pin sources (the CLI option and the user-config pin file), the
package-supplier boundary, the inventory of every native load site and the verdict-reuse key are frozen in
[Production pin source and native-load inventory](#production-pin-source-and-native-load-inventory-admitpin)
below.

## Snapshot and isolated completion

`probe_native_grammar(path, language, *, provenance, sample=b"", timeout=10.0,
inspect_artifact=None)`
returns an immutable `NativeProbeResult(supported, reason, artifact_sha256)`.
Missing and empty artifacts fail without native execution. Copy bytes from one
open regular file to an exclusively created private temporary snapshot with its
native suffix, verify the completed snapshot with existing `verify_artifact`,
close its writer and load only that absolute snapshot. Candidate replacement,
including same-size/same-mtime changes, cannot substitute the loaded bytes.
Each parent-owned snapshot stream or descriptor is disposed exactly once.
When copy, flush, fsync, verification, or final hash reading fails, later
disposal failures cannot replace that first exception object or its operation
traceback, and disposal of the remaining independently owned resources is
still attempted. If the operation succeeds, its ordinary disposal failure is
not suppressed and follows the existing public failure mapping. Acquisition
failures retain and dispose every descriptor whose ownership was not
successfully transferred.

The optional parent-side `inspect_artifact(snapshot_path)` callback runs only
after successful child completion, while the same verified private snapshot
still exists. Analyzer size, symbols and version metadata come from that
snapshot, never a fresh read of the original candidate. Public reports retain
the original candidate pathname for identification and carry the admitted
digest; cached metadata is bound to that digest. Callback failure cannot yield
healthy or partially accepted metadata. A deterministic replacement between
probe completion and metadata extraction must still report the admitted bytes.
The callback is trusted synchronous application code: it may inspect but must
not mutate or native-load the snapshot. Commit its captured metadata only after
`ok`; a raising callback returns `supported=False`, `reason="inspect_failed"`
and no accepted digest, with conditional cleanup in the owner’s `finally`. Recheck snapshot identity
before inspection. Artifact version/date fields never derive from source or
snapshot timestamps: missing version is `unknown` and release_date is None
without authentic release metadata. The separately reviewed precursor
treesitter-chunker#366 addresses treesitter-chunker#365 and its numeric-rule
consumer blocker treesitter-chunker#368 before this metadata migration lands.

Launch a child with `sys.executable -I`, an argument array and cwd set to the
private snapshot directory, without a shell. Bootstrap the package from the
parent's known installed/approved package location; never add the caller or
candidate directory or inherit PYTHONPATH to find it. Caller/candidate shadow
modules cannot execute before verification. The child independently verifies
the snapshot hash, lazily invokes the existing
pinned capsule loader, parses the supplied sample and observes a returned root.
Only afterwards may it emit exactly one completion record:

```json
{"schema":"native_probe.v1","nonce":"per-request","language":"requested","sha256":"snapshot","loader_returned":true,"parse_returned":true}
```

Accept only zero exit and one well-formed record matching schema, nonce,
language and digest with both booleans true. Diagnostic output is not completion;
missing, duplicate, malformed and mismatched acknowledgments fail closed.
Constructor `exit(0)` or `_exit(0)` therefore cannot establish support. Capture
at most 64 KiB per stdout/stderr diagnostic stream and a 16 KiB acknowledgment;
output overflow fails closed without unbounded buffering. Distinct child load
and parse failure records carry the stable reason but never count as completion.
On deadline use the bounded shared worker/launcher shutdown below. Never map
the candidate in the parent. Snapshot lifetime extends through confirmed worker
and launcher termination, including Windows file-handle release. Uncertain
startup retains the root; it cannot establish containment qualification.

Isolation protects the parent against native crashes and premature exits. It is
not a security sandbox for explicitly approved malicious native code, its
dependencies, or another process controlling the operator's private directory.
Acknowledgment demonstrates completion, not authentication against such code.
An empty sample demonstrates basic loadability; a real nonempty BAML fixture
must separately parse without errors to demonstrate its language contract.

## Results and consumer compatibility

Reasons: `ok`, `missing`, `empty`, `untrusted`, `integrity_mismatch`,
`load_failed`, `parse_failed`, `timeout`, `child_failed`, `ack_missing`,
`ack_invalid`, `inspect_failed`. Only `ok` permits `supported=True`, an accepted
artifact digest and capability metadata; failures return no accepted digest.
Analyzer failure returns `None`; capability/report/export results retain
`supported=False` and an additive `validation_reason`. Metadata fallbacks cannot
rescue failed admission. Revalidate content and provenance before returning
cached health, including removal and same-stat replacement.

Exports keep successful analyses under the existing `grammars` key and include
discovered rejected languages under additive `validation_failures`, each with
`supported=False`, `validation_reason` and the candidate path. Revalidate every
positive analyzer result, not merely legacy health. Default CLI/database
factories have no pin configuration, so their discoveries are unsupported:
report that cause, never fabricate metadata or insert a new accepted grammar
record. Existing database records are historical data, not admission receipts;
caller pin injection and stale-record migration belong to treesitter-chunker#362
and COMPAT and must preserve existing data until explicitly reconciled.

Legacy health maps missing to `missing`; empty/load/parse/null-symbol failures to
`corrupted`; trust, integrity, child, acknowledgment, inspection and deadline failures to
`incompatible`; only successful completion to `healthy`. Existing findings and
recommendations carry the cause. Tools forward these outcomes and invalidate
observations after install/update. No alternate parent loader may bypass this
gate in the scoped consumers.
Both install and update report `warning` with the validation cause when an
artifact fails admission, including unchanged revisions and missing artifacts.
Existing changed-revision operations write in place before checking: a warning
does not imply safe staging or restored old bytes. The existing argparse CLI
still exits zero on these warnings; correcting that exit status belongs to
treesitter-chunker#362 in GRAMMARS.
Neither reports `success` for an unapproved artifact. The following GRAMMARS phase
adds approved staging/publication and CLI migration; this first repair does not
grant trust to downloaded source or promise rollback.

## Acceptance

Use real compiled repository BAML and reviewed adversarial C fixtures. Prove
the constructor sentinel fixture executes in a deliberate confined positive
control, then prove unapproved entrypoints reject it without a sentinel. Pin
exit-zero fixtures deliberately to test missing completion. Cover corrupt,
wrong-symbol, null, relative paths, source substitution, cache removal,
same-stat replacement, timeout/crash and acknowledgment variants. Require native
fixture execution on acceptance platforms; missing compilers do not pass gates.
Also replace the original candidate between successful child completion and
metadata extraction, and verify that every reported artifact-derived field and
digest still describe the admitted snapshot.
Probe a pinned artifact without embedded metadata twice and require `unknown`
version and None release_date on both admitted snapshot observations.
Cover a raising inspection callback without partial metadata publication and
shadow modules planted in both caller cwd and the candidate directory. Derive
each report/export entry from one admitted record, so replacement between
separate observations cannot create internally contradictory nested fields.

Kill `bypass_native_provenance`, `accept_exit_zero_without_ack`,
`reload_original_after_verify`, `inspect_original_after_probe` and
`reuse_language_only_health`, restore each,
and rerun affected tests. The final accepted interface gate requires scoped
implementation, fixtures, mutations, exact-head independent review and required
platform verification. Discovery integration and immutable publication in
GRAMMARS receive their own review and acceptance.
Also kill `accept_partial_inspection`, `inherit_candidate_import_path` and
`unchanged_update_skips_validation`, with restored passes and path controls.


## Corrected lifecycle contract

This approved transcription supersedes conflicting lifecycle wording above.
Design SHA-256: `f1aab68cdbf5579b1688170e33c2984ee47baee1609d4f5cf136e102b1a99983`;
independent opinion: `9e24ca41b579a446ec44ef3929c25ad6c81be4519549e960fadc960871ad80b5`.
Only new transcriptions correct the CPython reference to 445–460 and use
“unarmed candidate handles”; frozen review bytes remain unchanged.

## Minimal private interfaces and snapshot ownership

Keep public `probe_native_grammar(path, language, *, provenance, sample=b"", timeout=10.0, inspect_artifact=None)` and frozen `NativeProbeResult(supported, reason, artifact_sha256)` unchanged. Keep reasons `ok`, `missing`, `empty`, `untrusted`, `integrity_mismatch`, `load_failed`, `parse_failed`, `timeout`, `child_failed`, `ack_missing`, `ack_invalid`, `inspect_failed`. Only `ok` carries a digest. Keep `native_probe.v1` exactly:

```json
{"schema":"native_probe.v1","nonce":"per-request","language":"requested","sha256":"snapshot","loader_returned":true,"parse_returned":true}
```

Keep `_read_child(command, cwd, timeout)` returning `(launcher_returncode, stdout, stderr, timed_out, overflow)` for raw pipe tests. Add keyword-only `worker_nonce=None, lifecycle=None`. Native admission **always** supplies both; missing native lifecycle is an internal error that cannot yield support. The private lifecycle record lives in `integrity.py`; no general process framework or public type is added. It contains launch intent, discovery state, retained launcher/worker identities, Windows handle where applicable, actual-worker status (integer or unavailable), completion/forced-stop flags, `cleanup_safe=False`, and a bounded containment-failure diagnostic. The tuple's first value is never redefined as worker status.

The snapshot owner creates this record before the launch operation and retains it even if `_read_child` raises before returning. Before any process creation attempt set launch intent and discovery uncertain. A thrown Popen constructor does not imply that no process ever existed: conservatively retain the root if the OS/constructor outcome is ambiguous. Before launch intent, a provenance/copy/verification failure has no process and can safely remove the root.

Replace TemporaryDirectory with mkdtemp and an explicit owner `try/finally`. There is no finalizer, weakref, atexit removal, or deferred cleanup queue for uncertain roots. On every owner exit inspect lifecycle state: remove only if no launch was attempted or `cleanup_safe` has been affirmatively established. A failure in bookkeeping must leave it false. No worker removes the root. Do not wrap Popen in a context manager whose exit can wait without the remaining bound. Close pipes and handles explicitly after bounded stop/wait; handle closure is not proof of termination.

For uncertainty report a bounded application diagnostic with retained absolute root and known `(pid, creation identity)` metadata, and original trigger (timeout/overflow/cancel/read error). It contains no accepted digest or captured unbounded native output. The public ordinary result is `NativeProbeResult(False, "child_failed", None)`; cancellation/KeyboardInterrupt propagates with its original traceback after cleanup/retention. Do not introduce a new public reason or automatically delete a retained root later. A parent diagnostic must remain available even if a diagnostic-file write fails; safety never depends on writing that file.

### Opt-in failure observation

Enabling DEBUG for `chunker.grammar.integrity` attaches a structured
`native_probe_diagnostic` dictionary to each rejection or propagating-exception
log record, with the same JSON in the log message for plain formatters.
Its diagnostic schema is `native_probe.diagnostic.v1`; this is not
the worker acknowledgment schema. Successful probes emit no such record.
The public result fields, reasons and `native_probe.v1` acknowledgment remain
unchanged.

The record contains the probe phase, last monitored operation, first exception
class/errno/winerror and at most six function/line locations, the recorded
launcher/worker identities and statuses, startup-write attempts/completion,
and the final cleanup proof state. It performs no extra process-status query.
It omits exception messages, filenames, source samples and native output.
Completing the start write is not evidence of native entry or successful parsing.

The first exception reserves its operation before metadata observation. If that
observation fails, its class/error-code fields remain null and its frames empty;
a secondary cleanup exception cannot take its place. Some inherited status and
cleanup handlers consume exceptions into internal failure state, so a rejection
can also have no exception metadata. `cleanup_safe` reports the worker-lifetime
proof before snapshot removal, not proof that filesystem removal succeeded.

Observation visits at most 64 traceback links and retains the last six visited
locations, with class/function names limited to 64 characters. A deeper origin
need not be included. Field/frame counts and names are bounded, but no universal
serialized-byte cap is promised for arbitrary integer attributes supplied by
trusted application callbacks; normal OS error-code metadata is the intended
case.

The private ready reader optionally receives its caller-owned lifecycle solely
to count Windows OPEN denials and retain the first denial's bounded metadata.
It does not mark those recovered denials as lifecycle errors, extend deadlines
or emit per-poll logs. A later rejection can therefore report a persistent
sharing denial even when the original public result remains `child_failed`.
Ordinary observer failures cannot replace the result; an original propagating
exception remains primary, and a new cancellation with no earlier exception
still propagates. These records support future investigations; they cannot
recover the missing original causes in treesitter-chunker#508/#509.

## Ready gate and the supported launch topology

The process launched is the current trusted `sys.executable -I`, shell=False, fixed approved package bootstrap, private cwd. Preserve current import isolation and no new environment configuration. Before loading, parsing, opening the snapshot in native code, or importing the native loader, the actual interpreter writes one closed/atomically replaced ready record (≤4 KiB) at `.native-probe-worker.json` and blocks reading exactly one start byte. EOF or a byte other than `b"\x01"` exits without native admission. Parent closes the writer after its one grant, and never grants after abort/timeout/cancellation is latched.

On Windows only, `PermissionError` from opening that ready-record path for
binary reading is a pending observation, like a record that is not present yet.
The parent returns to its ordinary polling path under the same execution
deadline; this adds no inner retry, sleep, deadline, or relaunch. The exception
scope ends as soon as the stream is opened: read and close failures still take
the existing error/containment path. If reading fails, the stream is closed once
without replacing the original read exception, its identity, or its traceback;
if reading succeeds, a close failure propagates. Non-Windows open denials and
cancellation also retain their existing propagation. Strict record validation
and all identity checks remain unchanged, and no start byte, native entry,
digest, or inspection can precede a fully read and validated registration.

If the Windows open denial persists, `_read_child` reaches its existing shared
deadline with `timed_out=True` and a timeout trigger. The frozen safety-first
precedence still maps incomplete startup and unsafe cleanup to public
`child_failed`, not `timeout`: no digest or start grant is produced, and the
uncertain root is retained. This distinction follows the frozen safety-first
precedence and was recorded by the parent implementation clarification; the
owner-approved repair itself remains limited to Windows ready-record open
polling and does not change other failure mappings.

**New private schema replacing the proposed v1 registration, for fresh acceptance:**

```json
{"schema":"native_probe.worker.v2","nonce":"per-request","pid":1234,"ppid":1200,"windows_creation_filetime":"0123456789abcdef"}
```

The exact key set is fixed; `pid` and `ppid` are positive integers with booleans rejected; nonce/schema are exact strings. `windows_creation_filetime` is exactly 16 lower-case hex digits on Windows, null on POSIX. The Windows worker obtains it from `GetProcessTimes(GetCurrentProcess())` on its own process object, not a timestamp or status file supplied by native code. This is a pre-entry identity record, never a report of successful exit. Strict duplicate-key/size/type/nonce validation precedes use. An invalid record is not a source of kill targets.

Startup completeness is conditional on the trusted, fixed interpreter topology already inside the admission trust boundary: POSIX directly execs the actual interpreter in the Popen child; Windows is either that direct interpreter or a genuine trusted CPython venv redirector creating **one** interpreter child. No caller-supplied arbitrary launcher, nested generic wrapper or process-creating bootstrap is supported as a success route. The approved bootstrap creates no children before the gate. CPython v3.13.15 `PC/venvlauncher.c:445–460` creates one interpreter, waits and queries its status; it does not provide an atomic process-tree snapshot, and its job assignment is not used as this plan's proof. Source evidence: [official CPython source](https://github.com/python/cpython/blob/v3.13.15/PC/venvlauncher.c#L445-L460). The actual executable/runtime must be recorded in platform evidence; matching a filename or a Python version alone does not validate a custom wrapper.

To enter `registered` the controller must, while start remains withheld and the original launcher is observed live, establish:

1. A strictly valid ready record from the trusted bootstrap in the exclusive private root.
2. POSIX: worker PID equals the direct Popen child PID. Windows: worker is either direct launcher or its independently observed **direct** interpreter child; compare recorded ppid with OS-observed ancestry, and retained psutil creation identities with the live original launcher. Do not trust record ppid alone. Final launcher `poll()` must still observe the original Popen child live after ancestry validation.
3. Windows: a handle to the exact recorded worker incarnation has been acquired/validated as below. POSIX: retain the direct Popen object as the sole wait-status owner and a psutil identity for liveness/descendant observation.
4. No abort/cancellation, discovery access error, unexpected topology/descendant, or timeout has occurred. Snapshot/control state is still intact.

Only then mark startup discovery complete and grant start. If launcher loss, abort, invalid record or an identity acquisition error occurs earlier, latch uncertainty; late registration does not retroactively clear it. An empty retained set, EOF, launcher zero, a later empty scan, or an apparently successful unlink never clears it. A registered worker remains independently retained after later launcher loss. If the topology is unexpected, reject/retain rather than silently treating a recursively found nonchild as status-capable.

This explicitly closes the ordinary missed-startup-worker case by conservative retention, not by claiming discovery is atomic. Native admission is still not a sandbox for deliberately trusted hostile code or private-directory compromise. Observed extra descendants are retained, stopped where identities are validated, and cause rejection. Lost ancestry/access/creation uncertainty around them prevents cleanup. No claim of complete containment of arbitrary invisible process escape is made. If a reviewer considers arbitrary post-start process creation part of the required support contract, this design needs a separately reviewed creation-atomic containment mechanism; recursive psutil polling cannot supply it. Do not broaden that claim during implementation.

## Actual-worker status: supported APIs and acquisition ordering

### Windows, including the real venv redirector

Use stdlib ctypes with declared Windows ABI argument/return types and `use_last_error=True`; this is a substantive OS-specific mechanism addition. Do not use psutil internals, Popen `_handle`, or third-party private process handles.

While the real worker is at the pre-start gate, call public `OpenProcess` once with `SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE`, `bInheritHandle=False`. Hold this candidate handle locally, unarmed. Read its creation FILETIME through `GetProcessTimes` and compare the exact 64-bit value with the ready record; validate ancestry independently as above. On any mismatch/query error/access denial/missing process, close this unarmed handle **without signaling it**, reject, and retain uncertainty. After all checks, transfer ownership to the lifecycle record and only then allow start. Cancellation between open and transfer closes the unarmed handle and preserves uncertain-root policy. Cancellation after transfer uses that same validated handle.

If the worker dies/reuses its PID before open, failure or differing FILETIME rejects. If it dies after successful open, the held handle remains attached to that process object through exit; it is never replaced by a later PID query. This prevents a PID-reuse status/termination substitution without assuming the worker can never exit while gated. There is no post-ack handle-acquisition window.

Poll `WaitForSingleObject(handle, 0)` alongside bounded output draining; waits use finite remaining-time slices, never INFINITE. Only `WAIT_OBJECT_0` establishes this worker's exit. `WAIT_TIMEOUT` is still live, `WAIT_FAILED`/unexpected codes are unavailable evidence. **After** signaled termination, `GetExitCodeProcess` on this exact handle supplies a DWORD: only integer zero can support success. Failure, missing status, nonzero values (including 259), and exception exit codes reject. A successful API call returning a plausible code while the process is unsignaled is not terminal status. Forced termination is recorded separately and can never count as normal success, regardless of a queried code.

Cancellation terminates the validated worker using `TerminateProcess(handle, nonzero_code)` and waits on that handle. The call alone is asynchronous evidence and cannot set cleanup_safe. Close exactly once after wait/status bookkeeping (or bounded failure/retention); do not close while a wait is pending. Reap the direct launcher separately with finite `Popen.wait()` remaining time; launcher zero is an additional condition, never a replacement for worker zero. Later launcher loss cannot erase the retained worker handle/status. Windows psutil remains useful for discovery and identity checks; its `wait()` result is not the actual-worker success authority here.

Public API evidence: [OpenProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocess) documents requested access, inheritance, failure and handle ownership; [GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes) documents creation FILETIME; [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject) documents finite waits and result codes. [GetExitCodeProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getexitcodeprocess) provides actual termination status. [TerminateProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess) requires a subsequent wait to confirm asynchronous termination. [Process termination semantics](https://learn.microsoft.com/en-us/windows/win32/procthread/terminating-a-process) preserve an object while another process holds its handle and warn that children are not automatically terminated. Read 2026-10-21; these are source/API evidence, not Windows execution evidence.

### POSIX

For the supported direct interpreter, the retained `subprocess.Popen` object refers to the actual worker child. It alone polls/waits/reaps that child; use its finite `wait(timeout=remaining)` status. No second psutil or os.waitpid consumer races to reap it. On POSIX a negative status is a signal failure; only known integer zero supports success. This is identity-bound direct-child OS status, not status forwarded by a launcher or a file. See [public Python Popen status/wait contract](https://docs.python.org/3.12/library/subprocess.html#subprocess.Popen.wait).

An injected POSIX launcher with a different actual worker PID is unsupported for success: psutil may confirm its death but cannot establish a nonchild's successful status. Mark actual status unavailable and reject even if launcher zero and valid ack are present. This intentional fail-closed behavior must be tested; there is no proposed cross-platform supervisor/status-relay protocol. Preserve known identities for bounded cleanup, and retain the root if startup discovery never completed or descendant quiescence is uncertain. A future requirement for successful indirect POSIX workers needs a separately reviewed direct-parent status relay; it is not silently included here.

### What the installed psutil source actually establishes

Read-only local installed source is `.venv/lib/python3.12/site-packages/psutil/` version **7.0.0** (`__init__.py:210`). `Process.wait` (`__init__.py:1328–1354`) documents nonchild POSIX status unavailability. `_psposix.py:62–145` uses waitpid, and returns None after polling nonchildren. `_pswindows.py:867–909` can return None after a process is already gone or a wait failure fallback. It reacquires status by PID inside the extension rather than exposing a public retained-handle ownership API. `children` (`__init__.py:939–1008`) explicitly documents lost descendant ancestry; enumeration is not atomic. `wait_procs` can report gone without a zero exit code. None of these APIs justify converting death or None to success.

**Dependency delta:** no upgrade from already locked psutil **7.0.0**, no new third-party dependency, no pywin32. Retain original proposed promotion of `psutil>=5.9.0` from dev to runtime with lock metadata regenerated by the supported tool, preserving resolution and parser/provider pins. Windows handle work uses Python's ctypes and public OS APIs, so it requires code/contract acceptance, not a dependency bump. It expressly supersedes the first proposal's psutil-only containment/status implication. Do not assume a newer psutil version would remove the lifecycle proof obligation.

## Lifecycle table and bounded cancellation

`uncertain` is a proof state, not a statement that a live worker definitely exists. `cleanup_safe` requires complete startup discovery, independently confirmed termination of the worker/launcher and every retained in-scope descendant, and no unresolved discovery/lifecycle error. Quiescence and exit success are separate facts: known abnormal exit can permit cleanup while prohibiting support.

| State / event | Retained identities and discovery proof | Snapshot owner action | Outcome / next transition |
| --- | --- | --- | --- |
| Before any launch intent | No process; source/snapshot owner only | Explicit cleanup permitted on failure | Existing trust/integrity reason, no digest |
| Popen construction entered; setup interrupted or raises | Uncertain, even if no Popen object returned | Retain root; bounded stop only for safely acquired identities | child_failed or propagate original cancellation |
| Launched, waiting for ready | Launcher plus any independently observed identities; startup uncertain | No native start, no inspection/removal | Continue only within original deadline |
| Cancel/timeout/EOF/launcher loss before registration | Sticky uncertain, including empty retained set | Close start writer, bounded stop/wait known targets, retain root even if they die | child_failed with original trigger in diagnostics; cancellation propagates |
| Invalid record / unrelated PID / identity mismatch | Do not arm record PID or unverified handle; startup uncertain | Reject; stop independently known targets; retain | child_failed; unrelated interpreter untouched |
| Valid live ready gate + supported topology + acquired worker status identity | Startup complete; worker retained independently of launcher | Start only if no abort latched; keep root | Work and bounded drains under same deadline |
| Registered worker native timeout / overflow / read failure / cancellation | Complete startup; actual worker/launcher known | Shared stop/wait path; cleanup only if all required deaths confirmed, otherwise retain | timeout / ack_invalid / child_failed as applicable; propagate original cancel |
| Launcher exits after worker registration | Retained worker handle/direct child remains; no ancestry rediscovery needed for that worker | Wait/stop worker under original bounds | Nonzero/unavailable launcher/worker status rejects; zero launcher alone insufficient |
| Unexpected descendant / ancestry lost / access failure | Retain identities, mark relevant discovery uncertain; never infer completeness from remaining scans | Bounded stop safe targets, retain root | child_failed; no digest even if known workers subsequently die |
| Natural worker and launcher exit, status known, all required deaths confirmed | Quiescent; each worker status bound to its identity | Inspection only after complete success predicate, then explicit cleanup | ack failure/nonzero rejects; ok requires all checks below |
| Worker dead but actual status unavailable | Death may be confirmed independently; no successful-status proof | Cleanup only if separate quiescence proof is complete; otherwise retain | child_failed, never ok |
| Stop/kill attempted; confirmation deadline expires or second cancellation interrupts cleanup | cleanup_safe remains false; uncertainty preserved | Close resources without another unbounded wait; retain root | child_failed or original cancellation; no finalizer |

Use one monotonic execution deadline computed before launch intent; registration, startup, native work, pipe draining and natural exit share it. Closing one/both pipes cannot cancel the deadline. When stopping, latch abort, close start permission first, collect safely observed descendants before signaling, stop registered worker/descendants before launcher, and use **one shared ≤1 s grace** then **one shared ≤5 s hard-stop confirmation**. Each wait receives only the remaining shared time; there is no five seconds per process, no fresh native deadline after registration, and no unbounded Popen.wait in finally. Windows terminate has no graceful SIGTERM distinction; an immediate forced stop may consume less than the grace bound. Keep polling output bounded while needed and close readers on failure; never block on pipe EOF from an unknown process.

For pre-ready cancellation the discovery/termination boundary itself is uncertain. Do not promote a before-kill snapshot of children into an exhaustive set; kill/wait known targets only and retain regardless of whether the launcher subsequently reports zero. C3 deliberately leaves the newly created unknown worker alive temporarily to prove that public failure/retention does not falsely attest its death. Test cleanup later owns the fixture; production has no background reaper guarantee for unknown PIDs.

All exits, including OSError/setup/read errors and BaseException, enter the same bounded containment path and then owner finally. Preserve the first cancellation/read exception; cleanup diagnostics cannot replace its traceback or make cleanup_safe true. If another interruption prevents confirmation, immediately leave the record unsafe and propagate with retention. The design does not promise immunity to parent process kill or machine failure. Python documents that initial OS process creation cannot always be interrupted or bounded by the subprocess timeout; the stated bound applies once control returns from those OS calls. Do not claim a strict end-to-end wall-clock SLA or a bounded trusted inspection callback.

## Success predicate and frozen failure precedence

Support requires **all**: validated registration/start; complete supported discovery; natural actual-worker exit with identity-bound integer zero; launcher reaped with integer zero; no forced termination or remaining in-scope worker; bounded output with exactly the unchanged matching ack; snapshot hash still matching the independent pin; trusted snapshot-only inspection returned successfully. Then and only then publish digest/metadata and remove the root. A pre-exit worker status JSON, a valid ack, EOF, worker absence, launcher zero, psutil None or successful deletion cannot substitute for any conjunct.

Precedence when there is no propagating caller exception:

1. Incomplete discovery/unconfirmed quiescence/setup or identity/status evidence failure => child_failed, no digest, retain if cleanup is unsafe. This overrides timeout/overflow; retain the initiating cause in bounded diagnostics.
2. With confirmed containment, execution timeout => timeout; stdout/stderr overflow => ack_invalid. If both are observed, preserve the first latched cause rather than resetting deadlines during cleanup.
3. With normal completed containment and no earlier fault, abnormal/nonzero success-record worker exit or nonzero launcher => child_failed. A request-matching failure envelope for load_failed/parse_failed with the expected ordinary worker failure exit remains that stable failure reason; it never admits. Missing/unavailable actual status always child_failed.
4. Then apply existing ack_missing/ack_invalid validation, snapshot integrity_mismatch, inspect_failed, and finally ok rules. Existing malformed ack tests remain meaningful and cannot bypass lifecycle evidence by monkeypatching tuple status.

## Production pin source and native-load inventory (ADMITPIN)

Status: proposed interface freeze for IF-0-ADMITPIN-1 and IF-0-ADMITPIN-2 of
`specs/phase-plans-v4.md`, pending two independent approvals. When ADMITPIN
closes, this line changes to "accepted", with the merge commit and the review
record. It changes no product code. treesitter-chunker#362 (phase ADMIT)
implements it. It includes three maintainer decisions from 2026-10-31: the
user-config pin file, the package-supplier boundary for our own wheels, and the
retirement of the on-demand fetch-and-build. Line numbers below refer to main
`7440971a`. ADMIT keeps the inventory's site IDs and updates its status column
as each site lands.

This section extends the contract above. `probe_native_grammar` and
`NativeProbeResult` stay unchanged and remain the only admission mechanism.
Nothing here changes `chunker/grammar/integrity.py`, `_read_child` or launcher
reaping (treesitter-chunker#389).

### IF-0-ADMITPIN-1 — pin mapping

Each of these constructors takes the same keyword-only argument:

```python
trusted_artifacts: Mapping[str, Mapping[str, str]] | None = None
```

- `chunker.grammar_management.core.GrammarValidator(cache_dir=None, *, trusted_artifacts=None)`
- `chunker.grammar_management.core.GrammarInstaller(cache_dir=None, build_timeout=300, max_retries=3, *, trusted_artifacts=None)`.
  The roadmap list omits it, but it builds its own `GrammarValidator`
  (`core.py:587`), so it needs the pins to validate installs.
- `chunker.grammar_management.core.GrammarRegistry(user_dir=None, package_dir=None, cache_dir=None, *, trusted_artifacts=None)`.
  It loads nothing itself; it passes the pins to the `GrammarInstaller` it builds.
- `chunker.grammar_management.core.GrammarManager(user_dir=None, package_dir=None, cache_dir=None, *, trusted_artifacts=None)`
- `chunker.grammar_management.cli.ComprehensiveGrammarCLI(cache_dir=None, verbose=False, *, trusted_artifacts=None)`
- `chunker._internal.registry.LanguageRegistry(library_path, *, trusted_artifacts=None)`
- `chunker.grammar.registry.UniversalLanguageRegistry(..., *, trusted_artifacts=None)`.
  It forwards the pins to the `LanguageRegistry` it builds (`registry.py:42`).
- `chunker.grammar_manager.GrammarManager(root_dir=None, config_file=None, max_workers=4, *, trusted_artifacts=None)`.
  This is the legacy combined-library manager (site M1 below). Nothing in the
  repository imports it. It is not the `TreeSitterGrammarManager` that
  `chunker.parser` uses. That class comes from `chunker.grammar.manager`,
  validates through `get_parser`, does no native load of its own, and reaches
  native loads only through the registry (R1–R4).

`GrammarAnalyzer`, `SmartGrammarManager` and `UserGrammarTools` already accept
the argument (SAFELOAD). Their wider `Mapping[str, Mapping[str, Any]]`
annotation stays compatible.

Rules:

1. The mapping is keyed by the *requested language*: the name the admitting
   component receives after its own existing alias normalization. For example,
   `chunker.parser` maps `c_sharp` to `csharp` before it calls the registry, so
   the parse-path key is `csharp`. Other file-name variants that a component
   tries while searching (such as `c-sharp`) are never keys. When a component
   derives the language from a file name, as
   `GrammarValidator.check_abi_compatibility(path, language=None)` does from
   the stem, the derived name is only the lookup key; admission still needs a
   pin under exactly that key. Each value is a record whose only meaningful
   field is `sha256`. `None` means no pins.
2. Each constructor copies the records it receives (`dict(record)` for each
   Mapping value, dropping non-Mapping values). Later changes to the caller's
   mapping have no effect. A constructor may pass the mapping to the components
   it owns (CLI → `GrammarManager` → `GrammarRegistry`/`GrammarInstaller`/
   `GrammarValidator`), and each of them copies it again. The whole mapping is
   never passed to the probe.
3. For each probe, the caller may first check whether the candidate exists
   with `os.path.lexists`, which neither opens nor loads it. If it does not
   exist, the caller reports `NativeProbeResult(False, "missing", None)`, so a
   grammar that was never installed still reads as missing. Otherwise the
   caller looks up `trusted_artifacts.get(language)`. If the lookup returns a
   record with a `str` `sha256` value, the caller passes the new one-field
   record `{"sha256": value}` as `provenance=`. If there is no entry, the
   record is not a Mapping, or it has no `str` `sha256`, the caller does not
   call the probe. It reports `NativeProbeResult(False, "untrusted", None)`
   without opening or loading the candidate. It never passes the whole
   mapping, `None` or an empty record. The probe still checks the 64-hex
   format; a malformed value becomes `untrusted` before native work.
4. A missing pin means unsupported. Freshly built or downloaded output, a
   directory location, a file name, an earlier probe, a stat tuple or a hash
   that the tool computed from discovered bytes never creates a pin. Pins come
   only from the sources in "Pin sources" below. No trust-all switch exists.
   The one exception to pinning is the package-supplied grammars of our own
   distribution (below), whose expected digest comes from the installed
   distribution's RECORD.
5. One combined library may serve several languages. Each language is
   admitted separately against its own record, so the same digest may appear
   under several keys. Mapping a library for one language admits no other
   language. Language L may be built from a mapped library only if L has its
   own record, that record's `sha256` equals the digest of the admitted copy,
   and L's own probe returned `ok` in this process (or a verdict was reused
   under L's own key, below). Otherwise L is `untrusted`, even though the
   library is already mapped. Discovery from a combined library tries only
   the languages that have pins. It never reads the symbol table of a library
   that has not been admitted. A package-supplied library of our own wheel
   (see "Package-supplied grammars in our own wheels") is the only exception:
   its supplier vouches for the whole file.

### IF-0-ADMITPIN-1 — pin sources

There are two pin sources. Both use the same file format, and only one is
active at a time (see "Precedence" below):

- the CLI option `--trusted-artifacts PATH`, for the grammar commands;
- the user-config pin file, for ordinary parsing and for grammar commands run
  without the option.

(Maintainer decision, 2026-10-31: the user-config pin file was added, and the
roadmap's IF-0-ADMITPIN-1 was updated to match.)

#### CLI option `--trusted-artifacts PATH`

Both grammar command groups accept the option before the subcommand:

- the argparse group in `chunker/cli/grammar_commands.py`:
  `python -m chunker.cli grammar --trusted-artifacts pins.json info python`.
  It forwards the parsed mapping through `get_grammar_tools` to
  `UserGrammarTools`.
- the click group `chunker.grammar_management.cli.grammar_cli`:
  `grammar --trusted-artifacts pins.json validate python`. It forwards the
  mapping to `ComprehensiveGrammarCLI`.

#### User-config pin file

The file is named `trusted-artifacts.json`. It lives in the
`treesitter-chunker` directory under the user configuration directory, which is
resolved with the standard library alone:

| `sys.platform` | Path |
|---|---|
| `win32` | `%APPDATA%\treesitter-chunker\trusted-artifacts.json`. If `APPDATA` is unset or not an absolute path, there is no config file. |
| `darwin` | `~/Library/Application Support/treesitter-chunker/trusted-artifacts.json` |
| any other | `$XDG_CONFIG_HOME/treesitter-chunker/trusted-artifacts.json` when `XDG_CONFIG_HOME` is set to an absolute path (relative values are ignored, as the XDG specification requires); otherwise `~/.config/treesitter-chunker/trusted-artifacts.json` |

Here `~` is `Path.home()`. `APPDATA` and `XDG_CONFIG_HOME` are the platforms'
standard base-directory variables. They only say where the operator's own file
is; they never make anything trusted, so this is not a trust switch.

- **Who reads it.** Only two entrypoints read the file. The first is
  `chunker.parser`'s module state, once, when it builds its `LanguageRegistry`;
  this covers `get_parser`, `acquire_parser`, `list_languages`, `chunk_file` and
  every API that resolves parsers through `chunker.parser`. The second is the
  two grammar command groups, when `--trusted-artifacts` is absent.
  Constructors never read it: `trusted_artifacts=None` on a constructor means
  no pins. A change to the file takes effect in the next process.
- **Pin-holding components stay off the parse path.** Every component in the
  IF-0-ADMITPIN-1 constructor list, whatever its `trusted_artifacts` value,
  never resolves grammars through `chunker.parser`'s module state
  (`get_parser`, `acquire_parser`, or anything else that reads the config
  file). Otherwise a narrower option file, an explicit empty mapping, or a
  defective config file could be bypassed or leak into a command run with a
  valid option. Today the `grammar_path=None` branch of
  `GrammarValidator.test_parse_samples` (`core.py:257-263`, reached from
  `compatibility.py:1061` and from other `compatibility.py` calls whose
  `grammar_path` may be `None`) calls `chunker.parser.get_parser`. ADMIT
  changes that branch to do one of two things:
  - resolve through a `LanguageRegistry` built from the validator's own
    mapping, where package-supplied grammars (our wheels, P1, P2, R5) still
    apply;
  - or report `untrusted` for a language that would need a pin.

  The named mutation `parse_samples_via_global_parser` (EC-ADMIT-6) restores
  the `get_parser` call, and a test with `GrammarValidator(trusted_artifacts={})`
  plus a config file that pins the language must then fail.
- **Never a `ChunkerConfig` file.** `ChunkerConfig` files are never pin sources,
  and ADMIT does not merge them with the pin file. That covers `chunker.config.*`
  found by the upward search from the current directory and
  `~/.chunker/config.*`. The upward search reads files the repository being
  chunked controls.
- **Never a tool-written directory.** The file must not be inside any of
  these directories, checked after symbolic links are resolved:
  - the treesitter-chunker cache root (`~/.cache/treesitter-chunker`, or the
    `--cache-dir` in effect);
  - the package grammar directory `chunker/data/grammars/build`;
  - `CHUNKER_GRAMMAR_BUILD_DIR` when it is set;
  - the configured combined library's directory (`Path(library_path).parent`,
    the R2/R4 scan directory).

  A file inside any of them is treated as defective. The tool never creates,
  updates or deletes the pin file.
- **A missing file** is not an error; it supplies no pins.
- **A present file that is defective fails closed.** That covers a file that
  is malformed, unreadable, not a regular file after symbolic links are
  resolved, larger than the limit, or inside a forbidden directory.
  (Maintainer clarification, 2026-10-31: fail closed means a defective pin file
  grants no local trust. It does not stop parsing altogether.)
  - Nothing in the file is used; entries are never partially applied, and a
    defective file can never cause anything to be trusted.
  - The shared reader raises `chunker.exceptions.TrustedArtifactsError` (a new
    `ChunkerError` subclass that ADMIT adds), with the file path and the
    defect. Each entrypoint handles it as follows.
  - **`chunker.parser`** catches it at initialization and continues with no
    pins. It logs one warning per process naming the file and the defect.
    Package-supplied grammars keep working: our own wheel's RECORD-verified
    files, the official tree-sitter wheels (P1), the language-pack (P2) and
    the BAML companion (R5). Every grammar that would need a pin is reported
    untrusted. When such a language cannot be resolved, the error it raises
    (`LanguageNotFoundError`, or `ParserInitError` for a rejected local
    candidate) names the pin file and its defect, so the cause is actionable.
    Parser initialization does not fail for every language.
  - **A grammar command run without the option** treats it as a usage error:
    exit status 2, naming the file and the defect, before discovery, any probe
    or any native load. Those commands exist to report on pinned grammars, so
    continuing would misreport them.
- **Test isolation.** ADMIT's tests set `HOME`, `USERPROFILE`, `APPDATA` and
  `XDG_CONFIG_HOME` to private temporary directories, so a developer's real
  pin file never affects a test.

#### File format (both sources)

The file is a regular file of at most 1 MiB, read as UTF-8 JSON. Duplicate
object keys are rejected. The exact shape is:

```json
{"schema": "chunker.trusted_artifacts.v1",
 "artifacts": {"python": {"sha256": "<64 hex digits>"}}}
```

The top level has exactly the keys `schema` and `artifacts`. `schema` is
exactly `chunker.trusted_artifacts.v1`. `artifacts` is an object whose keys
match `^[A-Za-z0-9][A-Za-z0-9_-]*$`; each key is a requested language as
defined in rule 1. Each value is an object with exactly the key `sha256`, whose
value is 64 hex digits; upper case is accepted and normalized to lower case. An
empty `artifacts` object is valid and supplies no pins. Entries are never
partially applied. A defective `--trusted-artifacts` file, or a missing or
unreadable one, is a usage error: the command exits with status 2 and a message
naming the file and the defect, before discovery, any probe or any native load.

The parsed file becomes the `trusted_artifacts` mapping, and the per-language
rules above apply unchanged. Each probe gets only `trusted_artifacts[language]`
as a fresh one-field record. A language with no entry is `untrusted`, and the
whole mapping is never passed on.

#### Precedence

Exactly one source is active, chosen in this order. The first source present
wins, and sources are **never merged**:

1. an explicit `trusted_artifacts` argument to a constructor (embedding code);
2. `--trusted-artifacts PATH` on a grammar command;
3. the user-config pin file;
4. no pins.

The active source is fixed where the component is built. The rule above that
pin-holding components stay off the parse path keeps a second source from
being reached later through `chunker.parser`.

The rule is conservative. The active pin set is always exactly one mapping the
operator can name and inspect. A second source can never widen an approval
without the operator noticing, and two sources can never disagree about a
language, so no conflict rule is needed. Naming a file with the option is how
an operator checks a narrower or different set without editing their config.
An option file with an empty `artifacts` object shuts off every local grammar
for that command. No cache-directory file, default pin location in the cache, or
trust-all switch exists.

### Using an admitted grammar in-process

A success from `probe_native_grammar` describes the probe's private snapshot.
It does not make the candidate path safe to map. A site that needs the grammar
in its own process (registry resolution, sample parsing, AST display) uses this
pattern and no other:

1. Copy the candidate from one open regular file into an exclusively created
   file in a new private directory, keeping its native suffix.
2. Verify the copy against the same one-field record with `verify_artifact`.
3. Pass that copy's absolute path to `probe_native_grammar` with the same
   record. Reusing a verdict under the key below is also allowed.
4. Only after `ok`, load that same copy, never the candidate path. Use
   `load_compiled_grammar`, or for a library already opened under this rule,
   the registry's capsule constructor.

Nothing writes to the copy after it is loaded, and the copy outlives every
`Language` or `Parser` built from it. Copies are created with `tempfile` in its
default directory, under a private directory whose name starts with
`chunker-admitted-`. Each process creates at most one copy per admitted
(language, digest) pair. On POSIX, the process removes its own copy directories
when the interpreter exits, because a mapped file can be unlinked there. On
Windows a loaded file cannot be deleted. Copies left there after exit are a
documented residual risk: they hold approved bytes, are named with that prefix,
and an operator can remove them once no chunker process is running. These
copies are separate from the probe's own snapshot roots, whose retention rules
above (no finalizer or `atexit` removal for uncertain roots) are unchanged.
Dependency lookup in the candidate's own directory is not supported for
admitted copies, which matches the probe child. Any helper for this pattern
lives outside the lifecycle code in `chunker/grammar/integrity.py`, and nothing
in the probe changes.

### Package-supplied grammars in our own wheels

(Maintainer decision, 2026-10-31.) Compiled grammars shipped inside our own
installed `treesitter-chunker` distribution are package-supplied. They are
trusted on the same footing as the official tree-sitter wheels and the
language-pack (P1, P2), with no user pin. The boundary is exact:

1. **The distribution.** It is the one returned by
   `importlib.metadata.distribution("treesitter-chunker")`, and only if its
   `locate_file("chunker/__init__.py")` is the same file as the imported
   `chunker.__file__` (compared resolved, or with `os.path.samefile`). A different or shadowing distribution
   supplies nothing.
2. **Which files count.** A candidate counts only when all of these hold:
   - It is a regular file, not a symbolic link.
   - It is the same file as `locate_file(entry)` for one entry in that
     distribution's `RECORD`. Both paths are compared after `Path.resolve()`,
     or with `os.path.samefile`, never as text. `locate_file()` returns an
     unresolved path, so a symbolic link in the site-packages path (a venv
     `lib64`, or `/var` → `/private/var` on macOS) or a difference in case on
     a case-insensitive file system does not demote our own files.
   - The entry is a relative POSIX path. It is not absolute, has no drive or
     root, no backslash and no empty, `.` or `..` component, and its parent is
     exactly `chunker/data/grammars/build`. Any other entry is ignored, so a
     textual prefix match can never be spoofed.
   - The entry ends in `.so`, `.dylib` or `.dll`. That covers the combined
     `languages<ext>` that `chunker.parser` prefers, and the per-language
     libraries.

   Nothing else counts, in particular other directories, the user cache,
   `CHUNKER_GRAMMAR_BUILD_DIR`, or a source checkout.
3. **Verification against RECORD.** The entry must carry a `sha256=` hash
   (URL-safe base64 without padding, as the wheel format specifies). The
   candidate's bytes are hashed from one open regular file, and the hash must
   equal the RECORD hash. The outcome depends on the case:
   - The hashes match: package-supplied.
   - The hashes differ: `integrity_mismatch`. The file is never loaded, and no
     user pin can admit it, because an installed file that differs from its
     RECORD is a tampering or corruption signal.
   - There is no `RECORD`, no entry for the file, the entry has no hash, or the
     hash uses another algorithm: the file is not package-supplied. This
     covers a file placed in that directory after installation, an editable
     install, a source checkout, and `grammar build` output written there.
     Such a file is an ordinary local candidate: it needs a user pin under
     the rules above, and without one it is `untrusted`.
4. **Loading.** A package-supplied file is loaded in place, as P1 and P2 are,
   only after the RECORD check passes in the current process. Every symbol in
   it is available, because the supplier vouches for the whole file. The
   check tells our package's files apart from files added later. It is not a
   defence against someone who can rewrite the installed package, because
   that person could also rewrite our Python code; that is the same supplier
   boundary as P1 and P2.
5. **Not an approval from discovered bytes.** The expected digest comes from
   `RECORD`, which the wheel ships and the installer writes. The tool only
   hashes the candidate to compare it with that supplied value. It never
   creates, stores or widens an approval from what it finds. `RECORD` is
   installer metadata, not a manifest the tool writes beside artifacts.

### Verdict-reuse key

A digest match shows that the bytes are the approved bytes. It does not show
that they still load in the current interpreter, platform or dependency set.
So an admission verdict is reused only inside the process that produced it,
and only under this key. That covers the `GrammarValidator` validation cache
and the in-memory health and analysis caches.

```text
sha256(canonical JSON of {
  "schema": "chunker.native_verdict.v1",
  "language": <requested language, as in rule 1>,
  "pin_sha256": <the record's sha256 value, lower-cased>,
  "content_sha256": <lower-case SHA-256 of the candidate bytes read for this lookup>,
  "level": <validation level value, or "probe">,
  "probe_schema": "native_probe.v1",
  "probe_profile": "default-v1",
  "inspector": <stable identifier of the inspect_artifact callback, or "none">,
  "validator_schema": <integer constant that ADMIT bumps whenever validation semantics change>,
  "chunker": <installed treesitter-chunker distribution version>,
  "tree_sitter": <installed tree-sitter distribution version>,
  "python": <sys.implementation.cache_tag>,
  "abi": <sysconfig.get_config_var("SOABI") or "">,
  "platform": <sys.platform>,
  "machine": <platform.machine()>
})
```

Canonical JSON means sorted keys, no insignificant whitespace and UTF-8. The
probe profile `default-v1` means `probe_native_grammar` called with
`sample=b""` and `timeout=10.0`. A probe with a different sample or deadline is
never answered from the cache, and its result is not stored.

`inspector` is a stable identifier for the `inspect_artifact` callback; `none`
means no callback. ADMIT fixes one constant per inspecting site, for example
`grammar_analyzer.v1` for `GrammarAnalyzer` and
`smart_grammar_manager.v1` for `SmartGrammarManager`. Captured metadata is
stored with the verdict under that key. A request with an inspector is answered
only by an entry stored by the same inspector, so a probe-only `ok` from the
registry or validator never answers `GrammarAnalyzer` with missing or foreign
metadata. An entry stored with metadata answers a probe-only request only
through its own key, which never matches `none`.

1. **Lookup order.** First check that the candidate exists, as in rule 3; if
   it does not, report `missing` with no reuse. Next resolve the pin as in
   rule 3, and with no pin report `untrusted` without reading or writing the
   cache. Then hash the candidate from one open regular file. If the content
   digest differs from the pin, report `integrity_mismatch` without reuse or
   probing. Only then compute the key and reuse a hit.
2. **What is stored.** Only results whose admission verdict was `ok` are
   stored, and only when the probe's `artifact_sha256` equals the key's
   `content_sha256`. A failed admission is recomputed every time.
3. **Process boundary.** A positive admission is reusable only in the process
   that ran the fresh probe, so every new process probes again before its
   first use of an artifact. A validation result written to disk is never an
   admission receipt on its own. A persisted `ValidationResult` may be returned
   only when the current process already holds a fresh `ok` admission under
   the same key. Otherwise the site probes, and the persisted entry is ignored.
4. **Load failure.** A reused verdict never hides a load failure. If loading
   an admitted copy fails, for example because a dynamic dependency was removed
   after the probe, the site drops the verdict for that key and reports
   `load_failed`.
5. **What is never in the key.** Path, mtime, size, inode, ctime and
   wall-clock timestamps are never part of the key or of its validity check.
   An expiry such as the current 24-hour TTL may only shorten reuse; it never
   establishes it. Same-stat byte replacement changes `content_sha256`, a pin
   change changes `pin_sha256`, and an interpreter, platform, chunker or
   tree-sitter change changes the environment fields. Each one misses.
6. **The lookup hash.** It is compared with the independent pin. It is never
   stored as a pin or treated as an approval.
7. **Old entries.** Entries under the old path/mtime/size key
   (`GrammarValidator._get_cache_key`) are never consulted and need no
   migration. TXN owns the protocol for writing the cache file; this key is
   independent of it.

ADMIT names cache mutations for EC-ADMIT-3, each with a regression that fails
under it:

- `reuse_stat_keyed_verdict`: same-stat byte replacement.
- `reuse_verdict_across_pin_change`: a changed pin record.
- `persist_admission_across_processes`: a fresh process given only a persisted
  `ok` entry must probe again.
- `reuse_verdict_across_environment`: a key that differs only in an
  environment field (`python`, `abi`, `platform`, `machine`, `chunker`,
  `tree_sitter` or `validator_schema`) misses.
- `reuse_verdict_across_inspector`: a request with one inspector is not
  answered by an entry stored without metadata or by another inspector.
- `reuse_verdict_across_probe_profile`: a non-default sample or deadline is
  not answered from the cache.

### treesitter-chunker#400 disposition: retire

The legacy `chunker.grammar.validator.TreeSitterGrammarValidator` is
**retired**, not repaired. Its constructor has raised `TypeError` on every
call (it omits `LanguageRegistry.library_path`), so it has no working
consumers. A repair would add a second public validator, with its own registry
wiring and its own timeout feature probe, next to `GrammarValidator`. ADMIT
SL-legacy:

- makes the constructor raise the module's existing
  `chunker.grammar.validator.ValidationError`, with a message that names the
  replacement;
- makes the static `check_abi_compatibility(grammar_path)`, which can be
  called without construction and loads in-process today, return
  `(False, <retirement message>)` without any native load;
- keeps the name importable from `chunker.grammar` until the next major
  version, records the migration in `CHANGELOG.md`, and updates
  `examples/manage_grammars.py`.

The replacement is
`chunker.grammar_management.core.GrammarValidator(cache_dir, trusted_artifacts=...)`
and its `check_abi_compatibility(path, language)` / `validate_grammar(...)`, or
`probe_native_grammar` directly. The unsupported `set_timeout_micros` feature
probe goes with the class. Retirement satisfies EC-ADMIT-4.

### IF-0-ADMITPIN-2 — native-load inventory

The dispositions are **integrated** (the site goes through
`probe_native_grammar` with an IF-0-ADMITPIN-1 pin, plus the in-process
pattern if it maps the grammar), **caller-trusted primitive** (it loads only
bytes its caller has already admitted), and **retired** (no native load
remains). **Package supplier, out of scope** marks loads of installed Python
distributions, which are a separate supplier trust boundary that this contract
does not cover.

| ID | Site (main `7440971a`) | What it loads | Disposition | ADMIT lane | Status |
|---|---|---|---|---|---|
| N1 | `chunker/grammar_management/core.py:129` `load_compiled_grammar` (`ctypes.CDLL`); its capsule `Language(` at `chunker/grammar_management/core.py:138` | the path it is given | caller-trusted primitive. Allowed callers pass the probe child's verified snapshot (I1) or an admitted private copy | SL-core | open |
| N2 | `chunker/grammar_management/core.py:229` `GrammarValidator.check_abi_compatibility` → N1 | discovered/validated candidate | integrated (probe only; no in-process load) | SL-core | open |
| N3 | `chunker/grammar_management/core.py:260` `GrammarValidator.test_parse_samples(grammar_path=...)` → N1 | local candidate, parsed in-process | integrated (in-process pattern). The `grammar_path=None` branch (`core.py:262`, today `chunker.parser.get_parser`) stops using `chunker.parser`. It resolves through a `LanguageRegistry` built from the validator's own pins, or reports `untrusted` ("Pin-holding components stay off the parse path"; mutation `parse_samples_via_global_parser`) | SL-core | open |
| N4 | `chunker/grammar_management/cli.py:1552` `build_grammar` post-build load check | fresh build output | integrated. With no pin, it skips the load and exits 0 with `built, not admitted: add a pin via --trusted-artifacts`. With a pin, it probes the output and exits 1 on any result other than `ok`. The build itself is unchanged | SL-core | open |
| N5 | `chunker/grammar_management/cli.py:2272` `_validate_compiled_grammar` | installed candidate | integrated, keeping today's output and exit codes; the treesitter-chunker#128 behaviour stays with ADMITFIX | SL-core | open |
| N6 | `chunker/grammar_management/cli.py:1945` `_test_compiled_grammar` (grammar test command) → N1 | local candidate, parsed in-process | integrated (in-process pattern) | SL-core | open |
| R1 | `chunker/_internal/registry.py:93` `LanguageRegistry._load_library` (combined library, including the `hasattr` symbol checks in `_discover_symbols`) | configured combined library | package-supplied when the file passes the RECORD check for our wheels (below); otherwise integrated (in-process pattern, one admission per language under rule 5). Discovery tries only the pinned language keys. It never uses `hasattr` or any other symbol inspection on a library that has not been admitted | SL-reg | open |
| R2 | `chunker/_internal/registry.py:234` `_validate_language_library` | per-language libraries found by scanning the combined library's own directory (`Path(library_path).parent`), the package build directory, `~/.cache/treesitter-chunker/build` and `CHUNKER_GRAMMAR_BUILD_DIR` | package-supplied for files that pass the RECORD check; otherwise integrated (in-process pattern). Scan directories confer no trust | SL-reg | open |
| R3 | `chunker/_internal/registry.py:293` `_language_from_ctypes_symbol` capsule `Language(` | nothing new; it wraps a library opened by R1/R2/R4 | integrated under rule 5. It may build language L only if L has its own record, that record's `sha256` equals the admitted copy's digest, and L's own probe (or a verdict reused under L's key) returned `ok`. Otherwise L is `untrusted`, even though the library is mapped. The `custom:sha256:` source label must use the admitted digest, not a re-read of the path | SL-reg | open |
| R4 | `chunker/_internal/registry.py:517` `_try_load_from_individual_library` | candidates in the combined library's own directory (`Path(library_path).parent`), the package build directory, `CHUNKER_GRAMMAR_BUILD_DIR` and `~/.cache/treesitter-chunker/build` | package-supplied for files that pass the RECORD check; otherwise integrated (in-process pattern). Search directories confer no trust | SL-reg | open |
| R5 | `chunker/_internal/registry.py:589` BAML companion `Language(baml_language())` | installed `treesitter_chunker_baml_grammar` distribution | package supplier, out of scope | — | n/a |
| V1 | `chunker/grammar/validator.py:41` and `chunker/grammar/validator.py:43` `TreeSitterGrammarValidator.check_abi_compatibility` | caller path | retired (treesitter-chunker#400, above) | SL-legacy | open |
| D1 | `chunker/grammar/download.py:412` `GrammarDownloadManager.validate_grammar` | downloaded/compiled output | retired. The static method has no way to receive pins: it keeps its existing non-native checks and returns `(False, <retirement message naming probe_native_grammar>)`. It has no in-repository callers | SL-legacy | open |
| M1 | `chunker/grammar_manager.py:256` `GrammarManager.get_available_languages` (legacy combined `my-languages.so`) | combined library | integrated (probe only, rule 5). It tries only the pinned language keys and returns only those whose combined-library bytes are admitted against their own pin. With no pins it returns the empty set. It never maps the library in the parent or reads its symbols | SL-legacy | open |
| T1 | `chunker/grammar_management/testing.py:153` reload of the original path after validation → N1 | original candidate | retired. The duplicate reload goes; `test_parse_samples` (N3) already checks parse errors on admitted bytes | SL-ins | open |
| T2 | `chunker/grammar_management/testing.py:381` `ctypes.CDLL` of a self-written corrupt file, used to compute an expected message | bytes the self-test just wrote | retired. The self-test compares against the admission reason instead | SL-ins | open |
| A1 | `GrammarMetadataExtractor.extract_from_dependencies` (`chunker/languages/compatibility/grammar_analyzer.py:591`, `ldd`) | caller-supplied path, through the dynamic loader | retired. It returns `{"dependencies": [], "dependencies_status": "retired"}` without running any tool, so a caller can tell retirement from a library with no dependencies. It has no in-repository callers | SL-ins | open |
| I1 | `chunker/grammar/integrity.py:131` probe child → N1 | verified private snapshot | integrated (this is the admission mechanism) | — | landed |
| P1 | `chunker/_internal/language_pack.py:109` `Language(module.language())` | pinned `tree_sitter_python` / `tree_sitter_javascript` wheels | package supplier, out of scope | — | n/a |
| P2 | `chunker/_internal/language_pack.py:130` `tree_sitter_language_pack.get_language` | pinned language-pack | package supplier, out of scope | — | n/a |
| F1 | `chunker/parser.py:164` (`get_parser`) and `chunker/parser.py:228` (`acquire_parser`) on-demand fetch-and-build through `chunker.grammar.manager.TreeSitterGrammarManager` | no load of its own: it clones and compiles a grammar on a miss, then retries the registry (R4) | retired in ADMIT (maintainer decision, 2026-10-31). A miss raises `LanguageNotFoundError` without cloning or compiling. Deliberate builds remain available through the grammar commands. ADMIT records it as a behaviour change in `CHANGELOG.md` and the grammar docs | SL-reg | open |

These grep hits are not load sites:

| Hit | What it is |
|---|---|
| `chunker/_internal/registry.py:67` | `ctypes.CDLL` type annotation on `_library` (R1) |
| `chunker/_internal/registry.py:81` | `_load_library` return annotation (R1) |
| `chunker/_internal/registry.py:227` | comment above R2 |
| `chunker/_internal/registry.py:271` | `_language_from_ctypes_symbol` parameter annotation (R3) |

`chunker/grammar/integrity.py:164` and `chunker/grammar/integrity.py:590` load
the Windows `kernel32` system library for process control, not a grammar. The
`nm`, `strings` and header readers in `GrammarMetadataExtractor` read files
without loading them, and `GrammarAnalyzer` runs them only on the admitted
snapshot inside `inspect_artifact`.

Every hit of
`grep -rn 'ctypes.CDLL\|cdll.LoadLibrary\|Language(' chunker/` at `7440971a`
appears as a `path:line` reference in the two tables above (EC-ADMITPIN-1).
After ADMIT, a new direct load anywhere in `chunker/` needs its own inventory
row and disposition.

File ownership notes for the ADMIT plan:

- SL-core owns several more files, as the roadmap's Phase 8 scope notes now
  say:
  - the shared pin-file reader, a new module `chunker/_internal/trusted_artifacts.py`,
    which handles per-OS path resolution, the forbidden-directory check, the
    `chunker.trusted_artifacts.v1` parser and `TrustedArtifactsError`;
  - `chunker/exceptions.py`, for `TrustedArtifactsError`;
  - `chunker/cli/grammar_commands.py`, the argparse option and the config
    fallback;
  - `chunker/_internal/grammar_management.py`, the rule-3 lookup in
    `SmartGrammarManager`.

  SL-core publishes the reader's signatures on day 1, alongside IF-0-ADMIT-1,
  and SL-reg consumes them for `chunker/parser.py` instead of writing its own.
- `chunker/grammar_management/compatibility.py` is already owned by SMALLFIX
  SL-sel (the treesitter-chunker#133 → treesitter-chunker#134 →
  treesitter-chunker#344 chain), so it is shared. ADMIT SL-core's edit is
  limited to the two `GrammarValidator(...)` constructor lines (148 and 770)
  that build validators without pins. ADMIT and SMALLFIX PRs on that file
  merge one at a time; the roadmap's cross-phase single-writer list records
  this.
- In `chunker/languages/compatibility/grammar_analyzer.py`, SL-ins's region is
  `GrammarAnalyzer.__init__` and `GrammarAnalyzer.analyze_grammar_file` (the
  rule-3 lookup) plus `GrammarMetadataExtractor.extract_from_dependencies`
  (A1). That is disjoint from CIFAST SL-deadline's `analyze_grammar_symbols`.

### Caller migration

These changes take effect when ADMIT lands, and ADMIT records them in
`CHANGELOG.md`.

- **Embedding callers** pass `trusted_artifacts={"<language>": {"sha256":
  "<hex>"}}` to the constructor they already use. The digest comes from an
  independently reviewed build or release record, never from hashing a
  discovered file at run time.
- **CLI users** either put their pins in the user-config pin file, or name a
  `chunker.trusted_artifacts.v1` file with `--trusted-artifacts PATH` before
  the subcommand. The option replaces the config file for that command; the
  two are never merged. With no pins from either source, an installed local
  compiled grammar reports `incompatible` with an `untrusted` cause, and
  `grammar info` exits 1. A grammar that was never installed still reports
  `missing` (rule 3).
- **Ordinary parsing** (`get_parser`, `acquire_parser`, `chunk_file` and
  everything else that resolves through `chunker.parser`) reads the user-config
  pin file. Local compiled grammars are used for parsing only when that file
  pins them, or when they are package-supplied files of our own wheel. All
  other local libraries are ignored, and resolution continues to the official
  wheels, the language-pack and the BAML companion. A defective config file
  grants no local trust. Package-supplied grammars keep working, and one
  warning names the file and its defect. Errors for languages that would
  have needed a pin repeat that cause.
- **`treesitter-chunker setup grammars`** (`cli/setup_command.py`) still builds
  into `~/.cache/treesitter-chunker/build`. Parsing uses that output only after
  the operator pins it in the user-config file.
- **`UniversalLanguageRegistry`** accepts `trusted_artifacts` and forwards it.
  It does not read the config file itself.
- **On-demand fetch-and-build is retired** (F1). A language that is missing
  from every source raises `LanguageNotFoundError` instead of cloning and
  compiling in the background. Build deliberately with the grammar commands,
  review the result, and pin it.
- **`grammar build`** with no pin does not load the new output. It exits 0 and
  prints `built, not admitted: add a pin via --trusted-artifacts`. An operator
  who has reviewed the build adds its digest to the pin file and validates
  again. With a pin, the build probes the output and exits 1 on any result
  other than `ok`.
- **Retired APIs** (`TreeSitterGrammarValidator`,
  `GrammarDownloadManager.validate_grammar`,
  `GrammarMetadataExtractor.extract_from_dependencies`) keep their names and
  return types until the next major version, but perform no native load or
  dependency inspection.
