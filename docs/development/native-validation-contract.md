# Native validation contract

Status: proposed design for treesitter-chunker#165, treesitter-chunker#151 and
treesitter-chunker#164. Independent design review precedes implementation.
Neither this document nor design approval establishes a repaired implementation.

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

## Snapshot and isolated completion

`probe_native_grammar(path, language, *, provenance, sample=b"", timeout=10.0,
inspect_artifact=None)`
returns an immutable `NativeProbeResult(supported, reason, artifact_sha256)`.
Missing and empty artifacts fail without native execution. Copy bytes from one
open regular file to an exclusively created private temporary snapshot with its
native suffix, verify the completed snapshot with existing `verify_artifact`,
close its writer and load only that absolute snapshot. Candidate replacement,
including same-size/same-mtime changes, cannot substitute the loaded bytes.

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
and no accepted digest, with cleanup in `finally`. Recheck snapshot identity
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
On deadline terminate, allow at most one second of grace, then force termination
and reap the child before removing the snapshot. Never map the candidate in the
parent. Snapshot lifetime extends
through child reaping, including Windows file-handle release.

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
