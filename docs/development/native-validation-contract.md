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

`probe_native_grammar(path, language, *, provenance, sample=b"", timeout=10.0)`
returns an immutable `NativeProbeResult(supported, reason, artifact_sha256)`.
Missing and empty artifacts fail without native execution. Copy bytes from one
open regular file to an exclusively created private temporary snapshot with its
native suffix, verify the completed snapshot with existing `verify_artifact`,
close its writer and load only that absolute snapshot. Candidate replacement,
including same-size/same-mtime changes, cannot substitute the loaded bytes.

Launch a child with `sys.executable` and an argument array, without a shell. The
child independently verifies the snapshot hash, lazily invokes the existing
pinned capsule loader, parses the supplied sample and observes a returned root.
Only afterwards may it emit exactly one completion record:

```json
{"schema":"native_probe.v1","nonce":"per-request","language":"requested","sha256":"snapshot","loader_returned":true,"parse_returned":true}
```

Accept only zero exit and one well-formed record matching schema, nonce,
language and digest with both booleans true. Diagnostic output is not completion;
missing, duplicate, malformed and mismatched acknowledgments fail closed.
Constructor `exit(0)` or `_exit(0)` therefore cannot establish support. Capture
bounded diagnostics; on deadline terminate and reap the child before removing
the snapshot. Never map the candidate in the parent. Snapshot lifetime extends
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
`ack_invalid`. Only `ok` permits `supported=True` and capability metadata.
Analyzer failure returns `None`; capability/report/export results retain
`supported=False` and an additive `validation_reason`. Metadata fallbacks cannot
rescue failed admission. Revalidate content and provenance before returning
cached health, including removal and same-stat replacement.

Legacy health maps missing to `missing`; empty/load/parse/null-symbol failures to
`corrupted`; trust, integrity, child, acknowledgment and deadline failures to
`incompatible`; only successful completion to `healthy`. Existing findings and
recommendations carry the cause. Tools forward these outcomes and invalidate
observations after install/update. No alternate parent loader may bypass this
gate in the scoped consumers.

## Acceptance

Use real compiled repository BAML and reviewed adversarial C fixtures. Prove
the constructor sentinel fixture executes in a deliberate confined positive
control, then prove unapproved entrypoints reject it without a sentinel. Pin
exit-zero fixtures deliberately to test missing completion. Cover corrupt,
wrong-symbol, null, relative paths, source substitution, cache removal,
same-stat replacement, timeout/crash and acknowledgment variants. Require native
fixture execution on acceptance platforms; missing compilers do not pass gates.

Kill `bypass_native_provenance`, `accept_exit_zero_without_ack`,
`reload_original_after_verify` and `reuse_language_only_health`, restore each,
and rerun affected tests. The final accepted interface gate requires scoped
implementation, fixtures, mutations, exact-head independent review and required
platform verification. Discovery integration and immutable publication in
GRAMMARS receive their own review and acceptance.
