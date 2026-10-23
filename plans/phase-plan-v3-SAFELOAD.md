---
phase_loop_plan_version: 1
phase: SAFELOAD
roadmap: specs/phase-plans-v3.md
roadmap_sha256: 3c6ee35180b0c9523d57d5c9e8bd668ab09878f62e581e9fccccf8fedcbfdf1b
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_grammar_integrity.py tests/test_compiled_grammar_analysis_contract.py tests/test_grammar_management.py -q"
---

# SAFELOAD: Trusted native grammar validation

## Context

Metadata prerequisites are accepted: treesitter-chunker#366 repaired version and
release metadata, and treesitter-chunker#380 repaired legacy compilation dates.
Neither produces IF-0-SAFELOAD-1. Native implementation acceptance remains pending.

Implement treesitter-chunker#165, treesitter-chunker#151 and treesitter-chunker#164 as one shared native-admission behavior cluster. This plan is execution-ready but is not a ratified design review or a produced IF gate. Retain draft treesitter-chunker#159 until its reviewed successor is accepted; do not spend another review round on that held draft.

Current construction sites: `GrammarAnalyzer.analyze_grammar_file` accepts metadata/date fallbacks without proving loadability; `SmartGrammarManager.diagnose_grammar_issues` maps discovered libraries in the parent and only checks symbol presence; `UserGrammarTools` delegates validation to that manager. Existing `verify_artifact` provides SHA-256 comparison, and `load_compiled_grammar` constructs a Parser with the pinned capsule API and rejects null pointers. Reuse both rather than inventing another loader. The existing compiled BAML test supplies reviewed source and a real sample.

One independently landable implementation PR carries the shared code, tests and documentation together. Its single implementation lane is followed by a documentation/evidence reducer; the reducer is part of that PR, not a separately landed repair. SAFELOAD has no upstream phase or IF gate; acceptance of metadata precursor treesitter-chunker#366 precedes execution. Under the owner's manual acceptance amendment below, GRAMMARS may consume independently recorded SAFELOAD implementation acceptance without a Harness-produced gate. Coordinate exclusive access to the analyzer with GATES and legacy tools with GRAMMARS. Destination publication/reload, native suffix discovery, registry health/CLI semantics and other native-loader consumers remain GRAMMARS work; this phase must not claim repository-wide native-load coverage.

The tracked roadmap hash matches the requested input. The newer canonical `.phase-loop/events.jsonl` run event marks SAFELOAD unplanned after the roadmap amendment, and live git topology confirms a clean starting checkout. Older state and handoff snapshots describe the previous plan against the superseded hash. Refresh this plan from the current roadmap; leave canonical runner state runner-owned and treat legacy `.codex/phase-loop/` files only as compatibility artifacts.

## Owner-directed manual acceptance amendment

The owner explicitly removed Harness review/binding as a blocking requirement
for current treesitter-chunker work. Proceed manually using exact-commit code
review, independent final acceptance, product fixtures and mutations, supported
platform checks and required CI. Those requirements remain mandatory before
publication, normal merge, issue closure or dependent implementation acceptance.
The native successor retains its existing CODE 0/3 and final 0/1 allowance.

Harness integration and `IF-0-SAFELOAD-1` are deferred future automation. Neither
agent-harness#1271 nor production of that formal IF blocks the current manual
path. Do not claim a runner-produced IF, modify runner-owned state, or treat
manual evidence as formal Harness qualification. This owner amendment governs
the current manual path where older roadmap/plan text requires that IF;
preserve the frozen roadmap and historical evidence with their original labels.
It does not accept the implementation or waive treesitter-chunker#389's worker
proof, treesitter-chunker#508's unexplained failure, or any other product finding.

## Owner-approved residual-risk assessment amendment — 2026-10-23

The owner explicitly permits assessment of the documented observations in
treesitter-chunker#508 and treesitter-chunker#509 with their causes unresolved.
This narrowly supersedes the explanation-before-landing requirement for those
two observations; it does not classify either failure as fixed or close either
issue. Their original failed runs, subsequent diagnostic limits and the
diagnostic plugin's nested-wrapper qualification remain review inputs.

Acceptance requires all four CODE seats and the separate independent Astra
president/final to explicitly approve the documented residual risks and current
candidate behavior, followed by passing required CI. Any HOLD blocks landing.
The roster remains two Sol seats, Regenesis Sonnet 5.5 and Astra; CODE 0/3 and
final 0/1 remain unused before the first launch. All earlier exhausted rounds
and HOLDs remain historical.

Provenance, acknowledgment, actual-worker status, confirmed termination before
cleanup, uncertainty retention, immutable snapshots and cache protections remain
mandatory. The controlled treesitter-chunker#389 evidence and single survivor
mutation interpretation still require independent assessment. This amendment
grants no deadline increase, denied-operation retry, policy bypass, source/test
assertion change, or acceptance of any later unexplained failure. Formal Harness
evidence remains deferred and unproduced. The explicit owner decision and its
accepted proposal are retained in the private
`native-owner-risk-assessment-amendment-r1/` packet.

## Owner-approved Windows ready-open polling repair — 2026-10-23

The owner separately approved one narrow implementation for a newly observed
Windows ready-record **open** denial. Only `PermissionError` raised by opening
`.native-probe-worker.json` for binary reading on Windows is treated as pending
and returned to the existing parent poll. It receives no internal retry loop,
new sleep, deadline extension or relaunch. Once open succeeds, stream read and
close exceptions remain errors; non-Windows denial and cancellation retain
their original propagation. Record validation, worker identity, start gating,
native admission and all other lifecycle behavior remain unchanged.

Ready-stream disposal follows the existing first-exception contract rather than
expanding the denied-open policy: after a read failure the stream is closed once
without replacing the original exception or traceback, while a close failure
after a successful read propagates normally. Direct and real public-probe
controls must cover disposal by both an `OSError` and a second cancellation.

Persistent denial consumes the existing shared execution deadline internally,
but the frozen failure precedence maps incomplete startup and unsafe cleanup to
public `child_failed`. The uncertain root is retained, with no digest or start
grant. This actual mapping corrects a prediction in the accepted proposal; it
does not add implementation authority or reorder public reasons. The immutable
owner decision, proposal and parent clarification are retained in
`native-ready-read-repair-proposal-r1/`. This amendment does not change the
historical treesitter-chunker#508/#509 residual-risk amendment, accept code,
waive platform verification, or spend a review round.

## Approved successor execution amendment — 2026-10-22

Fresh integration on `t3/integrate-native-after506` uses accepted main
`b3c43b6c006e944fe01d05e6f59b1e521bb7b4f3` after treesitter-chunker#506.
It replays the frozen native implementation without expanding SL-1/SL-2.
New private evidence belongs to `native-integration-after506-r1/`; the source,
execution attribution and holds of the original amendment below remain intact.
At that integration, Windows actual-worker survivor proof was UNPROVEN; see the
review-candidate amendment below. No acceptance is waived.

Assigned branch `t3/implement-safeload-successor` was clean at old parent
`b9be38a3b8159dd24497963314028a1630608b19` and fast-forwarded, before source
edits, to accepted main `8547f7b7afd90f7e86cf396e52c0b00a70c86dfb`.
Primary, held trees and frozen review packets remain untouched.

Independent design recheck APPROVE (design only): corrected design SHA-256
`f1aab68cdbf5579b1688170e33c2984ee47baee1609d4f5cf136e102b1a99983`, opinion
`9e24ca41b579a446ec44ef3929c25ad6c81be4519549e960fadc960871ad80b5`.
Original design HOLD remains preserved. This successor includes
treesitter-chunker#389; treesitter-chunker#159 and treesitter-chunker#372 retain
their exhausted 3/3 CODE rounds, historical HOLDs and missing full-opinion gaps.
Successor CODE remains 0/3 and separate final acceptance 0/1, parent-owned.
**IF-0-SAFELOAD-1 remains unproduced as deferred Harness automation.** Current
landing uses the manual acceptance amendment above; green tests alone do not
satisfy the independent review or unresolved product correctness requirements.

This coordinator owns this plan and runs SL-1 then SL-2 serially without fanout.
The following approved corrected transcription supersedes conflicting older
lifecycle prose below. Frozen original plans/reviews remain immutable. The two
nonblocking corrections are applied here only: CPython lines 445–460 and
“unarmed candidate handles”. Evidence is new/private only under campaign
`native-implementation-r1/`; no handwritten seals or private binders.

## Review-candidate amendment — 2026-10-23

The integrated implementation was frozen in local commit `6f9f838f` on
`t3/integrate-native-after506`, whose parent is accepted main
`b3c43b6c006e944fe01d05e6f59b1e521bb7b4f3`. A documentation-only owner-amendment
commit follows it; the CODE packet binds the actual reviewed tip and tree.
The original freeze binding remains in
`pr-recovery-20261021/native-review-freeze-r1/`. Production code, the fixture,
the lock and parser pins are unchanged from
the executed frozen tree `64668248b23d2e9ed55780ee5dfce1fe450a07d1`, which
remains historical execution identity.

Controlled Windows diagnostics for treesitter-chunker#389 are ready for
independent evaluation, not acceptance. They cover:
- a timeout baseline;
- a qualified actual-survivor `terminate_launcher_only` mutant;
- a finish-reader successor restoration;
- stdout and stderr overflow positives.

They used explicit debugger/`CREATE_SUSPENDED`/single-monitor-write scheduling
under one known runtime. That gives no ordinary-launch equivalence.

These remain failed and unqualified:
- the original timeout restoration;
- the old stdout baseline;
- the stdout overflow mutant, which failed during setup with P/C true and
  B/X false.

Their unknown helper, worker and root states remain untouched. The evidence
table, bridge evolution and hashes are in
`docs/development/safeload-verification.md`.

The plan requires all three positive fault modes and a retained
`terminate_launcher_only` falsifier. The parent treats the timeout survivor
mutant as that discriminator instead of separate per-output-mode mutants.
Independent reviewers must assess that interpretation. No product criterion is
waived, the acceptance boxes below stay unchecked, and native CODE 0/3 and
final 0/1 remain unused. treesitter-chunker#508 remains independently
unexplained with its acceptance unchanged. `IF-0-SAFELOAD-1` remains deferred
and unproduced.

## Minimal private interfaces and snapshot ownership

Keep public `probe_native_grammar(path, language, *, provenance, sample=b"", timeout=10.0, inspect_artifact=None)` and frozen `NativeProbeResult(supported, reason, artifact_sha256)` unchanged. Keep reasons `ok`, `missing`, `empty`, `untrusted`, `integrity_mismatch`, `load_failed`, `parse_failed`, `timeout`, `child_failed`, `ack_missing`, `ack_invalid`, `inspect_failed`. Only `ok` carries a digest. Keep `native_probe.v1` exactly:

```json
{"schema":"native_probe.v1","nonce":"per-request","language":"requested","sha256":"snapshot","loader_returned":true,"parse_returned":true}
```

Keep `_read_child(command, cwd, timeout)` returning `(launcher_returncode, stdout, stderr, timed_out, overflow)` for raw pipe tests. Add keyword-only `worker_nonce=None, lifecycle=None`. Native admission **always** supplies both; missing native lifecycle is an internal error that cannot yield support. The private lifecycle record lives in `integrity.py`; no general process framework or public type is added. It contains launch intent, discovery state, retained launcher/worker identities, Windows handle where applicable, actual-worker status (integer or unavailable), completion/forced-stop flags, `cleanup_safe=False`, and a bounded containment-failure diagnostic. The tuple's first value is never redefined as worker status.

The snapshot owner creates this record before the launch operation and retains it even if `_read_child` raises before returning. Before any process creation attempt set launch intent and discovery uncertain. A thrown Popen constructor does not imply that no process ever existed: conservatively retain the root if the OS/constructor outcome is ambiguous. Before launch intent, a provenance/copy/verification failure has no process and can safely remove the root.

Replace TemporaryDirectory with mkdtemp and an explicit owner `try/finally`. There is no finalizer, weakref, atexit removal, or deferred cleanup queue for uncertain roots. On every owner exit inspect lifecycle state: remove only if no launch was attempted or `cleanup_safe` has been affirmatively established. A failure in bookkeeping must leave it false. No worker removes the root. Do not wrap Popen in a context manager whose exit can wait without the remaining bound. Close pipes and handles explicitly after bounded stop/wait; handle closure is not proof of termination.

For uncertainty report a bounded application diagnostic with retained absolute root and known `(pid, creation identity)` metadata, and original trigger (timeout/overflow/cancel/read error). It contains no accepted digest or captured unbounded native output. The public ordinary result is `NativeProbeResult(False, "child_failed", None)`; cancellation/KeyboardInterrupt propagates with its original traceback after cleanup/retention. Do not introduce a new public reason or automatically delete a retained root later. A parent diagnostic must remain available even if a diagnostic-file write fails; safety never depends on writing that file.

## Ready gate and the supported launch topology

The process launched is the current trusted `sys.executable -I`, shell=False, fixed approved package bootstrap, private cwd. Preserve current import isolation and no new environment configuration. Before loading, parsing, opening the snapshot in native code, or importing the native loader, the actual interpreter writes one closed/atomically replaced ready record (≤4 KiB) at `.native-probe-worker.json` and blocks reading exactly one start byte. EOF or a byte other than `b"\x01"` exits without native admission. Parent closes the writer after its one grant, and never grants after abort/timeout/cancellation is latched.

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

## Deterministic verification proposal (not run)

Keep controls in existing `tests/test_grammar_integrity.py` and `tests/test_compiled_grammar_analysis_contract.py`; no new fixture package/framework. Use barriers/explicit messages rather than sleep races. All fixture roots, handles and PIDs are captured outside the private root; a supervised driver has independent cleanup authority for its known test processes. Every liveness assertion captures values **inside try before finally emergency cleanup**, including on an unlink exception. No mocks replace real native-open or actual status tests.

| ID / proposed test | Deterministic schedule and expected assertion |
| --- | --- |
| C1 `test_native_cancel_before_worker_ready_retains_snapshot` | Stop real bootstrap before ready publication, cancel controller, leave the delayed interpreter alive until driver inspection. Expect original cancellation propagated, no start/native marker/inspection, root retained with no automatic removal; capture liveness before emergency cleanup. |
| C2 `test_native_launcher_lost_before_registration_retains_snapshot` | Controlled launcher creates worker then exits before publication/parent validation; worker held at external pre-ready barrier. Parent observes launcher exit/empty set. child_failed/no digest, retained root even if output EOF; native never starts. |
| C3 `test_native_creation_crosses_discovery_stop_boundary` | Controller hook completes its first descendant scan (empty); driver releases launcher to create interpreter and waits for external worker-PID marker; only then permit launcher kill/exit and controller cleanup. Verify unknown worker can still be alive at return and root was never removed, including after GC. This proves uncertainty reaches owner; not successful containment. |
| C4 `test_native_lifecycle_faults_retain_unsafe_root` | Inject setup/read OSError, access error, wait timeout and BaseException after launch intent / before registration / after registration. Include second interrupt during cleanup. Unconfirmed paths never remove root; confirmed post-ready deaths may clean. Require finite remaining waits, no finalizer, original exception preserved. |
| C5 `test_native_invalid_registration_never_targets_unrelated_pid` | Live unrelated sentinel interpreter; wrong nonce/schema/types/duplicate keys/oversized record, then plausible pid/ppid with mismatched OS ancestry/creation time. Track production termination calls; no call on sentinel identity and sentinel alive before emergency cleanup. No start granted. |
| C6 `test_native_valid_ack_abnormal_worker_launcher_zero` | On Windows the test harness deliberately substitutes a reviewed single-child fault launcher in its supervised process: actual worker completes gated BAML parse/ack, flushes and then os._exit(7) or crashes at shutdown; launcher really waits then exits zero. Production registration, handle acquisition and status code execute unchanged; no status is mocked. The held handle must report nonzero actual status and parent never inspects or publishes digest. This supplemental fault launcher does not replace genuine-venv native-open acceptance. On POSIX, separately test that indirect topology rejects before start; that early rejection does not count as the ack-then-abnormal path. C8 supplies the direct POSIX ack-then-abnormal control. |
| C7 `test_native_actual_worker_zero_is_required_and_observed` | Real BAML sample, normal bootstrap shutdown and zero actual status on POSIX direct child and genuine Windows redirector with distinct PIDs. Exactly matching ack, admitted digest, snapshot-only metadata, root removed after liveness observation. Include launcher loss after registration and before work completion as a separate failure/cleanup control, never a substitute for natural zero. |
| C8 `test_native_missing_worker_status_rejects` | Force Windows handle query/wait failure after valid ack or inject nonchild POSIX None, while launcher returns zero. All reject/no inspection/no digest. Death-confirmed/status-unavailable may clean only with independently complete quiescence proof; failed death confirmation retains. Include actual worker nonzero on the normal direct POSIX route. |
| C9 `test_native_handle_acquisition_precedes_start` | Hold pre-ready worker; driver exits it before candidate handle validation, or deterministic adapter returns a handle with wrong creation FILETIME. No start, no termination of mismatched object, child_failed/retained uncertainty. Instrument open/validate/transfer/start order; after valid transfer no status-by-PID reopens are allowed. Exercise late registration after cancellation. |

Keep the original **real Windows native-open timeout/stdout-overflow/stderr-overflow** cases in the compiled-contract test. Run the public probe inside a real Windows CPython venv `Scripts/python.exe`; require distinct redirector/actual-worker PIDs, record executable/base executable/runtime/lock/head/compiler. Use the known affected 3.13.15 runtime or demonstrated equivalent in addition to the locked Python 3.12 platform matrix. Missing affected topology is unresolved evidence, not a skip counted as acceptance.

The reviewed pinned DLL constructor obtains its own loaded module pathname, opens **that private snapshot** using a handle without delete sharing, and flushes an external `snapshot_opened` marker with worker PID/path after the successful open. The driver validates private path, separation from candidate, and fixture pin; only then triggers native timeout or >16 KiB stdout / >64 KiB stderr. Keep it blocked. The observer captures actual-worker liveness and launcher reaping immediately before real production unlink/root removal **and** at probe return. For confirmed post-ready failure require no living worker before deletion/return, no digest, correct cause, original candidate rename/unlink and snapshot/root cleanup. For deliberately unconfirmed startup/fault cases require retention instead of unlink. Emergency cleanup always runs later and supplies none of these assertion values. POSIX gets corresponding native-open coverage; unlink success is not a liveness oracle.

Make that liveness oracle independent of production lifecycle flags: on Windows the external driver opens its own query/synchronize handle while the native-open marker proves the real worker is alive, validates the exact creation FILETIME, then samples WaitForSingleObject on that independently retained handle at cleanup/return. Unsignaled means alive; signaled means terminated; query/wait errors fail the observation. Keep observer handles through assertions and release afterward. Do not use PID existence alone, because a terminated process object can persist while a process handle is held; do not call psutil.wait on the production-owned actual-worker status path. On POSIX use the driver's retained creation identity plus OS process/zombie observation and the controller's actual-child reaping record; a bare reused PID is not identity evidence. Retained-startup tests likewise acquire their oracle while the supervised fixture is known alive, before allowing controller return. Record oracle values before any emergency signals.

Retain **all nine** earlier mutations, with path-entered control, baseline, intended failure, restored pass, final head and mutation bytes/hash: `bypass_native_provenance`, `accept_exit_zero_without_ack`, `reload_original_after_verify`, `reuse_language_only_health` (analyzer and manager), `inspect_original_after_probe`, `accept_partial_inspection`, `inherit_candidate_import_path`, `unchanged_update_skips_validation`, **`terminate_launcher_only`**. The last must fail on captured actual-worker liveness in real Windows native-open faults, even if root-retention behavior avoids an unlink error. Add targeted falsifiers `empty_scan_means_quiescent` (C1–C3) and `launcher_zero_means_worker_zero` (C6/C8); neither replaces an old mutation. Missing controls, compilers or supported status evidence keep acceptance unresolved.

Preserve unapproved constructor rejection/deliberate positive control, deliberately pinned exit(0)/_exit(0), corrupt/empty/missing/wrong-symbol/null-language, malformed/mismatched provenance and relative rejection, child digest recheck, immutable snapshot/same-stat replacement, post-child replacement before inspection, raising inspection/no partial metadata, analyzer **and** manager cache revalidation, cwd/PYTHONPATH shadows, disjoint export outcomes, real legacy/tools delegation, unchanged/missing update warnings, repeat unknown version/None dates, nonempty BAML error-free parse and all main downloader handle-lifetime variants.


## Interface Freeze Gates

- [ ] IF-0-SAFELOAD-1 — Deferred future automated interface gate. Review and freeze `docs/development/native-validation-contract.md`, `chunker.grammar.integrity.probe_native_grammar`, its `NativeProbeResult`, constructor provenance inputs and the child acknowledgment below as part of current manual acceptance; this does not produce a formal Harness gate.

### Admission and immutable identity

Extend the existing integrity module with:

`probe_native_grammar(path: Path, language: str, *, provenance: Mapping[str, Any] | None, sample: bytes = b"", timeout: float = 10.0, inspect_artifact: Callable[[Path], None] | None = None) -> NativeProbeResult`.

Freeze `NativeProbeResult` as an immutable record with `supported: bool`, `reason: str`, `artifact_sha256: str | None`. Reasons are `ok`, `missing`, `empty`, `untrusted`, `integrity_mismatch`, `load_failed`, `parse_failed`, `timeout`, `child_failed`, `ack_missing`, `ack_invalid`, `inspect_failed`. Only ok carries an accepted digest; failures return None. Missing/empty bytes are rejected without execution; all other candidates need trusted provenance before any native load.

Use existing `verify_artifact(path, provenance)` semantics: a nonempty SHA-256 pin comes from reviewed application/repository-owned configuration or an explicitly approved local build. A scanned directory, allowed HTTPS host, filename, stat tuple, successful prior probe, or adjacent self-authored manifest cannot confer trust. Never derive the expected pin from an unknown candidate and call that verification. Tests may compute pins only for artifacts they deliberately compile from reviewed repository/C fixture source; malicious fixtures are deliberately admitted only to exercise isolated failure handling.

Add optional keyword-only `trusted_artifacts: Mapping[str, Mapping[str, Any]] | None = None` to `GrammarAnalyzer`, `SmartGrammarManager` and `UserGrammarTools`; records are keyed by requested language and contain the existing `sha256` field. Copy supplied records at construction and forward them through tools to the manager. Absence fails closed for discovered local libraries. Do not silently trust freshly cloned/built outputs or add a trust-all switch. Document how an embedding caller supplies an independently approved pin, and why legacy CLI discoveries without that configuration cannot be healthy. Building arbitrary source is not made safe by this validation contract.

Copy candidate bytes from one open regular file into an exclusively created, private temporary snapshot retaining its native suffix. Verify the completed snapshot against the external pin, close the writer, and load only that absolute snapshot path. The child independently verifies the same digest before loading. Never verify the source path then reopen it for loading; replacements and same-size/same-mtime edits must not substitute bytes. Snapshot lifetime extends through child termination/reaping; source inodes never become mapped in the parent. This protects against candidate replacement, not a hostile process controlling the same account/private directory or malicious explicitly trusted native dependencies.

### Probe and acknowledgment

Parent metadata extraction uses `inspect_artifact(snapshot_path)` only after successful child completion and before removing that same verified snapshot. Analyzer versions, symbols and file size derive from this snapshot, while the public path remains the original candidate and reports carry the admitted digest. Callback failure cannot produce healthy or partial metadata. Add a deterministic replacement specifically between completion and extraction and kill `inspect_original_after_probe`; cache metadata stays digest-bound.
The callback is trusted synchronous application inspection, never parent-side native mapping or snapshot mutation. Recheck identity before invoking it; commit captured metadata only on ok with its matching digest. A raising callback returns inspect_failed with no accepted digest and guaranteed finally cleanup; kill accept_partial_inspection. No source/snapshot mtime produces version or release_date. Missing values remain unknown/None after independently accepted treesitter-chunker#365/treesitter-chunker#368 precursor repair in treesitter-chunker#366.

Use `sys.executable -I` and an argument array, cwd=private snapshot directory, without a shell, to invoke a private child entrypoint in the existing integrity module. Bootstrap from the parent's known installed/approved package path; never import from caller/candidate cwd or PYTHONPATH. Test sentinel shadow modules in both directories and kill inherit_candidate_import_path. Import `load_compiled_grammar` lazily inside the child. The child verifies the snapshot, calls that pinned loader, invokes `Parser.parse(sample)`, observes a returned root, and only then emits one structured completion record:

`{"schema":"native_probe.v1","nonce":"<per-request>","language":"<requested>","sha256":"<snapshot>","loader_returned":true,"parse_returned":true}`.

The parent accepts only zero exit plus exactly one well-formed acknowledgment matching schema, nonce, language and digest with both flags true. Native diagnostic stdout is not itself success; malformed, duplicate, missing or mismatched records fail closed. Acknowledgment proves completion, not a sandbox or authenticity against deliberately trusted malicious code. Empty-parse completion proves basic loadability, not all language semantics; positive BAML coverage must separately parse the checked-in nonempty declaration fixture without errors.

Timeout allows at most one second after termination before forced termination/reaping, all before snapshot cleanup; crashes, nonzero exit and premature `exit(0)`/`_exit(0)` never yield support. Capture at most 64 KiB per diagnostic stream and a 16 KiB acknowledgment; overflow fails closed without unbounded buffering. Distinct child failure records convey load_failed or parse_failed but cannot count as successful completion. Return the stable reason, not fabricated capability metadata. Keep ordinary timeout policy changes for GATES separate.

### Consumer behavior and compatibility

Analyze metadata only after admission and acknowledgment succeed. Failed `analyze_grammar_file` returns `None`; capabilities retain `supported=False` and empty/default fields, with an additive `validation_reason`; reports and exports preserve that reason. Metadata defaults cannot rescue failed validation. Cached analyzer and manager results must revalidate current content/provenance before reuse, including removal and same-stat replacement; do not cache by language alone.

Keep export successes under `grammars` and add `validation_failures` for rejected discoveries with supported=false, cause and path. All positive analyzer results are content/provenance revalidated. Default CLI/database factories without pins expose unsupported discoveries and actionable cause; do not fabricate analysis or new accepted records. Existing database rows remain historical, not admission receipts; default factory pin injection and stale-record reconciliation are owned by treesitter-chunker#362/COMPAT. In scoped tools, both install and update (including unchanged revision) must return warning plus cause when an artifact fails admission, never unconditional success. Do not silently fix unrelated database persistence or downstream publication here.
Derive each export entry from one admitted observation, not separate mutable-path probes. Test complete/disjoint grammars versus validation_failures membership, no inserted default-factory records, inspection exceptions and diagnostic/protocol overflow. Existing tools write changed revisions in place; warnings must describe that actual state, never claim safe staging. Unchanged-revision updates copy nothing but still validate the existing artifact, including missing paths; kill unchanged_update_skips_validation. CLI warning-to-exit-code migration and auxiliary testing.py original-path reload belong to treesitter-chunker#362/GRAMMARS. SAFELOAD guarantees no fabricated analyzer output/no new accepted records; downstream database cause surfacing remains deferred.

Legacy diagnosis maps missing to `missing`, empty/load/parse/null-symbol failures to `corrupted`, untrusted/integrity/child/protocol/inspection/deadline failures to `incompatible`, and only `ok` to `healthy`. Existing issues/recommendations carry the reason and recovery guidance. Tools preserve existing result shapes, propagate these findings, and invalidate old health observations after install/update. No parent `CDLL` or alternate loader may bypass the shared gate in these consumers. The exported low-level loader remains a caller-trusted primitive, never a discovery admission boundary. Registry ambient discovery/fallback loads, central GrammarValidator and CLI validation remain explicitly unsecured until GRAMMARS integrates this contract. Modern installer publication and legacy replacement also remain GRAMMARS work. RUNTIME and GATES repairs do not establish native admission safety.

## Lane Index & Dependencies

SL-1 — Shared admission, probe and consumer repair
  Depends on: (none)
  Blocks: SL-2
  Parallel-safe: no

SL-2 — Documentation and evidence reducer
  Depends on: SL-1
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Shared admission, probe and consumer repair

- **Scope**: Freeze the contract, then implement and falsify one admission/probe mechanism across analyzer and legacy validation.
- **Owned files**: `chunker/grammar/integrity.py`, `chunker/languages/compatibility/grammar_analyzer.py`, `chunker/_internal/grammar_management.py`, `chunker/_internal/user_grammar_tools.py`, `tests/test_grammar_integrity.py`, `tests/test_compiled_grammar_analysis_contract.py`, `tests/test_grammar_management.py`, `docs/development/native-validation-contract.md`, `pyproject.toml`, `uv.lock`
- **Interfaces provided**: `SAFELOAD implementation candidate`, `SAFELOAD contract review evidence`, `SAFELOAD fixture and mutation results`
- **Interfaces consumed**: `verify_artifact`, `load_compiled_grammar`, `GrammarHealth` (pre-existing)
- **Parallel-safe**: no
- **Tasks**:
  - test: Extend existing test files first. Compile BAML from `packages/baml-grammar/src/parser.c`; keep adversarial C snippets in the existing compiled-contract test and outputs under pytest temporary roots. Parameterize analyzer and legacy production entrypoints, including tools delegation. Require an available compiler in native acceptance jobs; do not convert missing compiler support into a passing gate.
  - test: Cover absent/empty/corrupt/wrong-symbol/null-language candidates, missing/malformed/mismatched pins, relative paths, stale cache removal and same-stat replacement, altered source after snapshot creation, malformed/mismatched/duplicate acknowledgment, timeout and crash. An unadmitted constructor writes a temporary sentinel if loaded: assert rejection and no sentinel. Use a separately confined deliberate-load positive control to prove that fixture really writes it.
  - test: Probe a pinned metadata-less real grammar twice through snapshot inspection; both observations retain unknown version and None release_date, preserving the accepted precursor contract.
  - test: Deliberately pin reviewed constructor fixtures calling `exit(0)` and `_exit(0)`; require rejection without acknowledgment while the outer process survives. Instrument the real child loader/parse path for path-entered controls; mocks may test protocol parsing but cannot replace native evidence. Check repeated diagnose/replace/diagnose cycles in an outer subprocess and source rename/removal after probing, including Windows handle release.
  - impl: Review and, where needed, refine the existing proposed `docs/development/native-validation-contract.md` before behavior changes. Obtain independent design review of trust origin, snapshot race handling, child completion and failure mappings; record its evidence before implementing. Resolve blocking disagreement before continuing. Design approval alone produces no IF gate and closes no implementation issue. Then add the shared probe beside the existing integrity verifier and wire all three consumers. Replace mock-CDLL-as-health expectations with observable contract tests.
  - impl: Keep import boundaries lazy and package exports unchanged; promote already locked `psutil>=5.9.0` from dev to runtime, preserving its 7.0.0 resolution and all parser/provider pins. No new environment variable, generated golden or committed native library is needed. Do not modify source fixtures or retrofit unrelated loading paths.
  - verify: Run the focused suite in Verification, then named mutations below with fresh subprocesses and isolated HOME/USERPROFILE. Restore each mutation and rerun the affected tests before handing results to SL-2.

### SL-2 — Documentation and evidence reducer

- **Scope**: Reduce SL-1 behavior, review and verification into accurate user documentation and acceptance evidence.
- **Owned files**: `docs/grammar_management.md`, `CHANGELOG.md`, `docs/development/safeload-verification.md`, `mkdocs.yml`, `tests/test_release_hygiene_policy.py`, `scripts/run_platform_core.py`
- **Interfaces provided**: `SAFELOAD acceptance evidence`, independently recorded manual implementation acceptance; formal `IF-0-SAFELOAD-1` is deferred future automation.
- **Interfaces consumed**: `SAFELOAD implementation candidate`, `SAFELOAD contract review evidence`, `SAFELOAD fixture and mutation results`
- **Parallel-safe**: no
- **Tasks**:
  - test: Check documentation examples against the actual constructor parameters and untrusted/healthy outcomes; inspect every EC/IF claim against SL-1 fixture and review results.
  - impl: Document provenance migration, failure reasons, trust limitations and downstream GRAMMARS responsibilities; add an Unreleased changelog entry. Record per-platform fixture outcomes, positive controls, killed mutations, command/result metadata and independent review references in the evidence document. Distinguish preliminary contract review from final manual implementation acceptance. Require independent implementation review and passing fixture, mutation and platform results for the final reviewed implementation before recording manual acceptance and eligibility to close treesitter-chunker#151, treesitter-chunker#164 and treesitter-chunker#165. Do not emit a formal IF as part of this manual closeout.
  - verify: Run remaining Verification commands after SL-1, build documentation into a temporary directory, and reduce the preserved evidence into manual EC/acceptance decisions. Do not claim ratification without independent review; a Sol-authored ratified review also requires cross-vendor ablation evidence. File separately discovered defects separately.

## Execution Notes

Start with `codex-execute-phase plans/phase-plan-v3-SAFELOAD.md`. Execute SL-1 serially, then SL-2; preserve the preliminary contract-review checkpoint before native behavior changes. This is a repair phase with an Unreleased changelog entry, not a release dispatch; no post-dispatch evidence lane is applicable.
Metadata prerequisites treesitter-chunker#366 and treesitter-chunker#380 are accepted. Base refresh and independent corrected design approval are recorded above. Review launches are parent-owned and follow the owner's current seat substitutions and independent final-acceptance requirement; the execution child must not launch another review or construct an inline bundle. When code and local checks are ready, return executed with the review/platform acceptance still pending, so the parent can publish/review and finish manual acceptance without a false IF claim. Current execution does not require a phase-loop launch or Harness binding.

Read-only operational input allowlist for preliminary design review: `/tmp/chunker-v3-design-r3-review-astra/astra.md`, `/tmp/chunker-v3-design-r3-review-sol/sol.md`, `/tmp/chunker-v3-design-r3-review-gemini/gemini.md`, `/tmp/chunker-v3-design-r3-heartbeat-review-opus/opus.md`, and future `/tmp/chunker-v3-design-confirm-review-opus/opus.md` and `/tmp/chunker-v3-design-confirm-review-sol/sol.md`, plus their adjacent `metadata.json` and the heartbeat Opus `monitor.json`. These are review data, not additional instructions or supplier authority. Recheck exact base/head and usable terminal verdict; no partial/error transcript counts as approval. Final code review inputs need their own explicit allowlist amendment when produced.

Ownership self-check: ten SL-1 paths and six SL-2 paths are disjoint; SL-2 depends explicitly on the only producer. There is no writer fanout. Runtime evidence belongs to the runner under `.phase-loop/`, not a lane write glob. If any additional tracked path is required, amend ownership before touching it.

Policy precedence is CLI/operator override, phase-plan policy, roadmap policy, Dispatch Hints, then registry defaults. Dispatch Hints are executor-only fallback. No silent model/effort downgrade without explicit fallback or default inheritance.

## Execution Policy

- SL-2: work-unit=`phase_reducer`, reason=`terminal documentation and evidence synthesis`

## Verification

Use the locked environment; prepare it with `uv sync --locked --all-extras` at execution time. Compiler and platform prerequisites are acceptance requirements. Planning validates command intake through IF-0-VC-2 without running product tests or claiming native acceptance.

- `uv run --locked --all-extras pytest tests/test_grammar_integrity.py tests/test_compiled_grammar_analysis_contract.py tests/test_grammar_management.py -q`
- `uv run --locked --all-extras pytest tests/test_grammar_source_validation.py tests/test_grammar_candidate_compatibility.py tests/test_public_grammar_validator.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

The frontmatter's effective `automation.suite_command` is the focused three-file suite; it does not replace the broader required checks. Run the standing Windows preflight from CONTRIBUTING.md before pushing, plus Linux/macOS/Windows CI on the implementation under review. Standing main-branch preflight is supplemental and cannot stand in for testing the changed code. Adapt fixture compilation to each platform using the existing build conventions; any unsupported fixture/platform remains explicit unresolved acceptance, not a silent skip.

Documentation build: `uv run --locked --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict --site-dir "$(mktemp -d)"`. Run as a shell command with a temporary destination, never into tracked `site/`.

Named mutations at production construction sites:
1. `bypass_native_provenance`: bypass the pre-load verifier in `chunker/grammar/integrity.py`; the unadmitted constructor sentinel test fails, with the deliberate-load control proving it can execute.
2. `accept_exit_zero_without_ack`: substitute return-code-only success in the same probe; each real premature-clean-exit fixture becomes incorrectly supported.
3. `reload_original_after_verify`: use the original path instead of the verified snapshot; deterministic replacement introduces wrong bytes and fails identity/parse assertions.
4. `reuse_language_only_health`: bypass fresh content verification in analyzer/manager; same-stat replacement and repeated legacy validation tests fail.
5. `inspect_original_after_probe`: read metadata from the replaced original path instead of the retained admitted snapshot; the post-completion replacement fixture fails metadata/digest assertions.
6. `accept_partial_inspection`: publish captured metadata despite a raising callback; partial-output and cleanup assertions fail.
7. `inherit_candidate_import_path`: omit child isolated import protection; caller/candidate shadow-module sentinel assertions fail.
8. `unchanged_update_skips_validation`: return success without validating unchanged installed bytes; stale-pin/missing-artifact warning assertions fail.

For each, record baseline pass, mutation-triggered failure, path-entered control and restored pass. No tight scheduler timing assertions. Keep evidence metadata-only in `docs/development/safeload-verification.md`, pointing to actual preserved command logs, receipts and review opinions. Manual acceptance must identify the actual reviewed commit and each review's scope; an uncommitted prospective tree or previous base commit is not that identity. Harness binding and IF-0-SAFELOAD-1 production are deferred and do not gate current execution, publication, normal merge, issue reconciliation or dependent manual work. Manual evidence does not create runner authority, exemptions, formal IF completion or supplier qualification. Existing failed attempts, checkpoints, ledgers and broker state remain unchanged. treesitter-chunker#389's required actual-worker Windows survivor proof remains an outstanding obligation until independent assessment of its controlled evidence. treesitter-chunker#508's unexplained admission failure remains an independent outstanding obligation. Any change to those product criteria requires a separate concrete owner decision.

## Acceptance Criteria

- [ ] EC-SAFELOAD-1 — proven by `uv run --locked --all-extras pytest tests/test_grammar_integrity.py tests/test_grammar_management.py -q` and independently reviewed `docs/development/native-validation-contract.md` recorded in `docs/development/safeload-verification.md`; falsified by `bypass_native_provenance` at `chunker/grammar/integrity.py:probe_native_grammar`, with a path-entered deliberate-load constructor sentinel control and recorded rejection failure.
- [ ] EC-SAFELOAD-2 — proven by `uv run --locked --all-extras pytest tests/test_compiled_grammar_analysis_contract.py -q`; falsified by `accept_exit_zero_without_ack`, `reload_original_after_verify`, `accept_partial_inspection` and `inherit_candidate_import_path` at `chunker/grammar/integrity.py:probe_native_grammar`, plus `inspect_original_after_probe` at the analyzer callback, `reuse_language_only_health` at analyzer/legacy diagnosis and `unchanged_update_skips_validation` at tools update, with path-entered real BAML parse, premature-clean-exit, callback, shadow-module and replacement controls.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `docs/development/native-validation-contract.md`, `docs/grammar_management.md`
- evidence paths: `docs/development/safeload-verification.md`, `.phase-loop/`
- redaction posture: `metadata_only`
- downstream handling: `none`

Under the owner-directed manual path, GRAMMARS may consume independently recorded SAFELOAD implementation acceptance after all product, review and verification requirements pass. Formal IF-0-SAFELOAD-1 remains deferred and unproduced. This plan amendment does not itself accept native behavior or close the held drafts; normal merge and issue reconciliation continue under the owner's standing authorization after manual acceptance and required CI.
