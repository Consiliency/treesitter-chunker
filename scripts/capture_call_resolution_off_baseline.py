#!/usr/bin/env python3
"""Check or capture the off-mode call-resolution baseline (treesitter-chunker#682).

The baseline pins today's output for every fixture tree under
``tests/fixtures/call_resolution`` before any call-resolution code exists
(plan ``plans/detailed-scoped-call-resolution-682.md`` section 11.2):

- the symbol graph, as canonical JSON, for both ``resolution_mode`` values;
- the Boundary IR parity view, for both ``resolution_mode`` values, captured
  cold and reproduced by a cold-then-warm incremental run;
- the off-mode Boundary cache-key payloads and keys, recorded from that
  incremental run;
- ``parity_digests.json`` and ``MANIFEST.sha256``, which lists every document.

By default the script only checks: it re-extracts everything in memory and
compares it with the committed documents. It writes only with ``--write``.
Regeneration after a lock change is its own pull request with no product
change; a cross-OS mismatch is a portability bug, never a reason to regenerate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "call_resolution"
BASELINE = FIXTURES / "off_mode_baseline"
MANIFEST = BASELINE / "MANIFEST.sha256"
DIGESTS = BASELINE / "parity_digests.json"
TREE_SOURCES = ("greenfield-r1", "probe-r9", "authored")
RESOLUTION_MODES = ("permissive", "strict")
# Cache-key payload fields that follow installed versions (package, runtime and
# grammar pins). They are recorded but compared only when they are unchanged,
# so a version bump does not invalidate the baseline by itself.
VOLATILE_PAYLOAD_FIELDS = ("grammar_version", "runtime_version", "tool_version")


@dataclass(frozen=True)
class Run:
    """One extraction root: a fixture tree, optionally a subroot or language."""

    tree: str
    source: str
    label: str
    root: str
    language: str | None

    @property
    def path(self) -> Path:
        return FIXTURES / self.root

    @property
    def run_id(self) -> str:
        return f"{self.tree}/{self.label}"


# Extra roots named by plan section 10.1: the probe's Python root and the
# filtered ts-language-filter run. Every tree also has a "default" run (its own
# directory, no language filter).
EXTRA_RUNS = {
    "probe-r9": (("py", "probe-r9/py", None),),
    "ts-language-filter": (
        ("typescript", "authored/ts-language-filter", "typescript"),
    ),
}


def discover_runs() -> list[Run]:
    """Every baseline run, in a stable order."""
    runs: list[Run] = []
    trees: dict[str, str] = {}
    for source in TREE_SOURCES:
        base = FIXTURES / source
        if source == "probe-r9":
            entries = [("probe-r9", "probe-r9")]
        else:
            entries = sorted(
                (child.name, f"{source}/{child.name}")
                for child in base.iterdir()
                if child.is_dir()
            )
        for tree, root in entries:
            if tree in trees:
                msg = f"tree name {tree!r} is used by {trees[tree]} and {source}"
                raise ValueError(msg)
            trees[tree] = source
            runs.append(Run(tree, source, "default", root, None))
            for label, extra_root, language in EXTRA_RUNS.get(tree, ()):
                runs.append(Run(tree, source, label, extra_root, language))
    return runs


def canonical_json(value: Any) -> bytes:
    """Byte-stable JSON: sorted keys, LF line endings, trailing newline."""
    text = json.dumps(value, sort_keys=True, indent=1, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def _symbol_graph(run: Run, mode: str) -> dict[str, Any]:
    from chunker.symbol_graph import extract_symbol_graph

    return extract_symbol_graph(run.path, run.language, resolution_mode=mode)


def _boundary(run: Run, mode: str, **kwargs: Any) -> dict[str, Any]:
    from chunker.boundary import extract_boundary_ir

    return extract_boundary_ir(run.path, run.language, resolution_mode=mode, **kwargs)


def _record_snapshot(directory: Path) -> dict[str, tuple[int, int]]:
    """Size and mtime of every cache record (the index is rewritten each run)."""
    snapshot: dict[str, tuple[int, int]] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "index.json":
            stat = path.stat()
            snapshot[path.relative_to(directory).as_posix()] = (
                stat.st_size,
                stat.st_mtime_ns,
            )
    return snapshot


def _incremental(run: Run, mode: str) -> tuple[bytes, bytes, dict[str, Any]]:
    """Cold then warm incremental parity views, plus the recorded cache keys."""
    from chunker.boundary import canonicalize_for_parity
    from chunker.boundary.cache import load_cache_index, load_cache_record

    with tempfile.TemporaryDirectory(prefix="call-resolution-baseline-") as tmp:
        cache_dir = Path(tmp) / "cache"
        first = _boundary(run, mode, incremental=True, cache_dir=cache_dir)
        before = _record_snapshot(cache_dir)
        second = _boundary(run, mode, incremental=True, cache_dir=cache_dir)
        after = _record_snapshot(cache_dir)
        if before != after:
            msg = f"{run.run_id} {mode}: the warm incremental run rewrote cache records"
            raise AssertionError(msg)
        index = load_cache_index(cache_dir)
        files: dict[str, Any] = {}
        for display_path, cache_key in sorted(index.records.items()):
            record = load_cache_record(cache_dir, cache_key)
            if record is None:
                msg = f"{run.run_id} {mode}: no cache record for {display_path}"
                raise AssertionError(msg)
            files[display_path] = {
                "cache_key": cache_key,
                "key_payload": record.key_payload,
            }
    cache_keys = {"volatile_fields": list(VOLATILE_PAYLOAD_FIELDS), "files": files}
    return (
        canonical_json(canonicalize_for_parity(first)),
        canonical_json(canonicalize_for_parity(second)),
        cache_keys,
    )


def capture_run(run: Run) -> tuple[dict[str, bytes], dict[str, str]]:
    """Return ``{document name: bytes}`` and ``{mode: parity digest}`` for a run."""
    from chunker.boundary import canonicalize_for_parity, parity_digest

    documents: dict[str, bytes] = {}
    digests: dict[str, str] = {}
    for mode in RESOLUTION_MODES:
        documents[f"symbol_graph.{mode}.json"] = canonical_json(
            _symbol_graph(run, mode)
        )
        cold = _boundary(run, mode)
        parity = canonical_json(canonicalize_for_parity(cold))
        incremental_cold, warm, cache_keys = _incremental(run, mode)
        for name, value in (("incremental cold", incremental_cold), ("warm", warm)):
            if value != parity:
                msg = f"{run.run_id} {mode}: the {name} parity view differs from cold"
                raise AssertionError(msg)
        documents[f"boundary_ir.{mode}.parity.json"] = parity
        documents[f"cache_keys.{mode}.json"] = canonical_json(cache_keys)
        digests[mode] = parity_digest(cold)
    return documents, digests


def _manifest_lines(entries: Iterable[tuple[str, bytes]]) -> bytes:
    lines = [
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in sorted(entries)
    ]
    return "".join(lines).encode("utf-8")


def read_manifest() -> dict[str, str]:
    """``{relative path: sha256}`` from the committed manifest."""
    entries: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        digest, _, name = line.partition("  ")
        entries[name] = digest
    return entries


def check_manifest() -> list[str]:
    """Problems with the committed documents against ``MANIFEST.sha256``."""
    problems: list[str] = []
    if not MANIFEST.is_file():
        return [f"missing {MANIFEST.relative_to(ROOT).as_posix()}"]
    listed = read_manifest()
    on_disk = {
        path.relative_to(BASELINE).as_posix()
        for path in BASELINE.rglob("*")
        if path.is_file() and path != MANIFEST
    }
    for name in sorted(on_disk - set(listed)):
        problems.append(f"not in manifest: {name}")
    for name in sorted(set(listed) - on_disk):
        problems.append(f"listed but missing: {name}")
    for name in sorted(on_disk & set(listed)):
        actual = hashlib.sha256((BASELINE / name).read_bytes()).hexdigest()
        if actual != listed[name]:
            problems.append(f"sha256 mismatch: {name}")
    return problems


def compare_cache_keys(recorded: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Compare cache-key documents, ignoring volatile fields when they changed."""
    from chunker.boundary.cache import build_boundary_cache_key

    problems: list[str] = []
    if recorded.get("volatile_fields") != list(VOLATILE_PAYLOAD_FIELDS):
        problems.append("volatile_fields changed")
    old, new = recorded.get("files", {}), current.get("files", {})
    if sorted(old) != sorted(new):
        problems.append(f"file set differs: {sorted(old)} != {sorted(new)}")
    for path in sorted(set(old) & set(new)):
        old_payload = old[path]["key_payload"]
        new_payload = new[path]["key_payload"]
        stable = sorted(set(old_payload) | set(new_payload))
        for field in stable:
            if field in VOLATILE_PAYLOAD_FIELDS:
                continue
            if old_payload.get(field) != new_payload.get(field):
                problems.append(f"{path}: payload field {field} differs")
        if build_boundary_cache_key(old_payload) != old[path]["cache_key"]:
            problems.append(f"{path}: recorded key does not derive from its payload")
        versions_same = all(
            old_payload.get(field) == new_payload.get(field)
            for field in VOLATILE_PAYLOAD_FIELDS
        )
        if versions_same and old[path]["cache_key"] != new[path]["cache_key"]:
            problems.append(f"{path}: cache key differs at unchanged versions")
    return problems


def check_run(run: Run) -> list[str]:
    """Problems for one run: regenerated documents against the committed ones."""
    problems: list[str] = []
    documents, digests = capture_run(run)
    directory = BASELINE / run.run_id
    for name, data in documents.items():
        path = directory / name
        label = f"{run.run_id}/{name}"
        if not path.is_file():
            problems.append(f"missing {label}")
            continue
        committed = path.read_bytes()
        if name.startswith("cache_keys."):
            problems.extend(
                f"{label}: {problem}"
                for problem in compare_cache_keys(
                    json.loads(committed), json.loads(data)
                )
            )
        elif committed != data:
            problems.append(f"differs: {label}")
    if DIGESTS.is_file():
        recorded = json.loads(DIGESTS.read_text(encoding="utf-8")).get(run.run_id)
        if recorded != digests:
            problems.append(f"parity digests differ: {run.run_id}")
    return problems


def _write(runs: list[Run]) -> str:
    entries: list[tuple[str, bytes]] = []
    digests: dict[str, dict[str, str]] = {}
    for run in runs:
        documents, run_digests = capture_run(run)
        digests[run.run_id] = run_digests
        for name, data in documents.items():
            entries.append((f"{run.run_id}/{name}", data))
        print(f"captured {run.run_id}", flush=True)
    expected = {name for name, _ in entries}
    for path in sorted(BASELINE.rglob("*"), reverse=True):
        relative = path.relative_to(BASELINE).as_posix()
        if (
            path.is_file()
            and relative not in expected
            and path not in {MANIFEST, DIGESTS}
        ):
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    for name, data in entries:
        target = BASELINE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    digest_bytes = canonical_json(digests)
    DIGESTS.write_bytes(digest_bytes)
    entries.append((DIGESTS.name, digest_bytes))
    manifest = _manifest_lines(entries)
    MANIFEST.write_bytes(manifest)
    return hashlib.sha256(manifest).hexdigest()


def _select(runs: list[Run], wanted: list[str] | None) -> Iterator[Run]:
    if not wanted:
        yield from runs
        return
    known = {run.run_id: run for run in runs}
    for run_id in wanted:
        if run_id not in known:
            msg = f"unknown run {run_id!r}; use --list"
            raise SystemExit(msg)
        yield known[run_id]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write",
        action="store_true",
        help="regenerate every document and the manifest (default: check only)",
    )
    parser.add_argument(
        "--run",
        action="append",
        metavar="TREE/LABEL",
        help="check only this run (repeatable); not allowed with --write",
    )
    parser.add_argument("--list", action="store_true", help="list runs and exit")
    args = parser.parse_args(argv)
    runs = discover_runs()
    if args.list:
        for run in runs:
            print(f"{run.run_id}\t{run.root}\t{run.language or '-'}")
        return 0
    if args.write:
        if args.run:
            parser.error("--write regenerates every run; drop --run")
        digest = _write(runs)
        print(f"wrote {len(runs)} runs; MANIFEST.sha256 sha256 {digest}")
        return 0
    problems = check_manifest()
    for run in _select(runs, args.run):
        problems.extend(check_run(run))
    for problem in problems:
        print(problem)
    if problems:
        print(f"FAILED: {len(problems)} problem(s)")
        return 1
    manifest_digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    print(f"OK: baseline matches; MANIFEST.sha256 sha256 {manifest_digest}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
