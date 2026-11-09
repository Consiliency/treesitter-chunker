"""Installation commit and rollback (treesitter-chunker#363).

Cache transaction contract, Primitive 3. Artifacts are real compiled BAML
revisions (0.1.0 and 0.2.0); every admission is a real
``probe_native_grammar`` run through IF-0-HOTFIX-1 ``publish_native_grammar``.

Installer cases use the integrated ADMIT setup of
``tests/test_cache_entry_transactions.py``: the ``git`` shim and a failing
``tree-sitter`` stub, so the installer's real ``gcc`` builder compiles each
fixture's sources with its path-independent recipe (treesitter-chunker#621).
Each install child gets its pin through ADMIT's
``GrammarInstaller(*, trusted_artifacts=)`` from ``TXN_PIN_SHA256``: the
digest of the parent's own build of that fixture with the same documented
recipe, computed independently of what the installer builds. The Windows
variant builds the same way with MinGW ``gcc`` and executable shims (see
:func:`_windows_shim`).

A restored revision is parsed in a fresh process through an admitted private
copy under that revision's independently supplied pin, never by loading the
installed path directly.

Terms used below:

- A *False-returning failure* is ``publish_native_grammar`` returning an
  unsupported ``NativeProbeResult`` (for example, the staged bytes do not match
  the pin), as opposed to raising ``OSError``.
- *Handle release* means the installing process holds no handle on the
  destination library (ADMIT loads only private copies), so Windows lets
  ``os.replace`` swap it during restore.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from chunker._internal import user_grammar_tools
from chunker._internal.user_grammar_tools import publish_native_grammar
from chunker.grammar import integrity
from chunker.grammar_management import _build_recipe, _transactions
from chunker.grammar_management.core import (
    GrammarInstaller,
    GrammarManager,
    GrammarPriority,
    GrammarValidator,
    InstallationInfo,
)
from tests.native_policy import policy_aware_native_driver, skip_policy_subprocess
from tests.test_cache_entry_transactions import (
    INSTALL,
    PINS,
    POSIX_SHIM,
    SHIM,
    URL,
    _env,
    _fixture_digest,
    _install,
    _installer,
    _make_shim,
    _repo,
)
from tests.test_compiled_grammar_analysis_contract import SOURCE, _compile_probe_fixture
from tests.test_reproducible_grammar_build import _installer_compiler
from tests.txn_barrier import (
    ROOT,
    SAFETY_TIMEOUT,
    Child,
    exit_at,
    pause_at,
    participants,
    run_mounting,
)

pytestmark = pytest.mark.usefixtures("native_policy_environment")

FIXTURE = ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"
COMMIT_PAUSE = pause_at("lock.before_acquire", primitive="cache_lock", section="commit")


@pytest.fixture
def shim(tmp_path: Path) -> Path:
    """The integrated shim directory (``git`` and a ``tree-sitter`` stub)."""
    return _make_shim(tmp_path)


def _sha(path: Path) -> str | None:
    return sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _pin(path: Path) -> dict[str, str]:
    return {"sha256": sha256(path.read_bytes()).hexdigest()}


@pytest.fixture(scope="module")
def revisions(tmp_path_factory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("baml-rollback-revisions")
    (root / "a").mkdir()
    rev_a = _compile_probe_fixture(root / "a", [SOURCE / "parser.c"])
    text = (SOURCE / "parser.c").read_text(encoding="utf-8")
    (root / "b").mkdir()
    revised = root / "b" / "parser.c"
    revised.write_text(
        text.replace(".minor_version = 1,", ".minor_version = 2,"), encoding="utf-8"
    )
    rev_b = _compile_probe_fixture(root / "b", [revised])
    assert _sha(rev_a) != _sha(rev_b)
    return rev_a, rev_b


def _pair(cache: Path) -> tuple[str | None, bytes | None]:
    metadata = cache / "grammars" / "baml_install_info.json"
    return (
        _sha(cache / "grammars" / "libbaml.so"),
        metadata.read_bytes() if metadata.is_file() else None,
    )


ADMITTED_PARSE = r"""
import json, sys
from pathlib import Path
from chunker._internal.native_admission import admitted_private_copy
from chunker.grammar_management.core import load_compiled_grammar
library, fixture, pin = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
result, copy = admitted_private_copy(library, "baml", {"baml": {"sha256": pin}})
if result.reason == "policy_blocked":
    print(json.dumps({"schema": "native_test.policy_result.v1",
                      "reason": "policy_blocked"}), flush=True)
    raise SystemExit(77)
if copy is None:
    print(json.dumps({"admitted": False, "reason": result.reason}), flush=True)
    raise SystemExit(0)
parser = load_compiled_grammar(copy, "baml")
root = parser.parse(fixture.read_bytes()).root_node
print(json.dumps({"admitted": True, "reason": result.reason,
                  "version": list(parser.language.semantic_version),
                  "ok": root.type == "source_file" and not root.has_error}), flush=True)
"""


def _admitted_parse(library: Path, digest: str) -> dict:
    """Parse the fixture in a fresh process via an admitted copy under ``digest``."""
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            policy_aware_native_driver(ADMITTED_PARSE),
            str(ROOT),
            str(library),
            str(FIXTURE),
            digest,
        ],
        capture_output=True,
        text=True,
        timeout=SAFETY_TIMEOUT,
        check=False,
    )
    skip_policy_subprocess(completed)
    assert completed.returncode == 0, completed.stderr[-4000:]
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _parse_version(library: Path, digest: str) -> list[int]:
    report = _admitted_parse(library, digest)
    assert report["admitted"] and report["ok"], report
    return report["version"]


def _health(cache: Path, digest: str) -> dict:
    """ADMIT's single health accessor under a one-language pin for ``digest``."""
    manager = GrammarManager(
        user_dir=cache / "grammars",
        package_dir=cache.parent / "package",
        cache_dir=cache,
        trusted_artifacts={"baml": {"sha256": digest}},
    )
    return manager.get_admitted_health("baml")


def _require_restored_a(cache: Path, digest_a: str, digest_b: str) -> None:
    """A's pair parses only under A's pin; with B still pinned, A fails closed."""
    library = cache / "grammars" / "libbaml.so"
    assert _parse_version(library, digest_a) == [0, 1, 0]
    under_b = _admitted_parse(library, digest_b)
    assert under_b == {"admitted": False, "reason": "integrity_mismatch"}
    health = _health(cache, digest_b)
    assert (health["status"], health["validation_reason"]) == (
        "incompatible",
        "integrity_mismatch",
    )
    health = _health(cache, digest_a)
    assert (health["status"], health["validation_reason"]) == ("healthy", "ok")


def _tree(cache: Path) -> list[str]:
    return sorted(p.relative_to(cache).as_posix() for p in cache.rglob("*"))


def _rollback_points(cache: Path) -> list[str]:
    area = cache / ".txn" / "rollback"
    return sorted(p.name for p in area.iterdir() if p.name != ".txn-keep")


def _damage_staged(cache: Path, failure: str) -> None:
    """A non-participant corrupts or removes the staged, validated build."""
    (staged,) = (cache / "builds" / ".txn-staging").glob("*/baml/libbaml.so")
    if failure == "not_admitted":
        # A new inode: the staged file is replaced, never written in place.
        damaged = staged.with_name("damaged")
        damaged.write_bytes(staged.read_bytes()[:4096])
        damaged.replace(staged)
    else:
        staged.unlink()


# --- failed update restores the pair -------------------------------------------


@POSIX_SHIM
@pytest.mark.parametrize("failure", ["not_admitted", "raises"])
def test_failed_update_restores_previous_pair(tmp_path, shim, failure):
    """A real install of A, then a deterministic failed update to B.

    The fault is injected at the commit section's ``lock.before_acquire``,
    after validation: a non-participant corrupts (``not_admitted``: a
    False-returning failure) or removes (``raises``: ``OSError``) the staged
    artifact. The metadata already published is restored, the pair equals A's,
    and a fresh process parses A's revision through an admitted copy under
    A's pin. With B still pinned, A fails closed (``integrity_mismatch``,
    health ``incompatible``). Mutations ``omit_restore`` and
    ``rollback_removes_metadata`` (the old behavior) leave a different pair.
    """
    cache = tmp_path / "cache"
    repo_a = _repo(tmp_path / "repo-a", minor=1)
    repo_b = _repo(tmp_path / "repo-b", minor=2)
    digest_a, digest_b = _fixture_digest(repo_a), _fixture_digest(repo_b)
    assert digest_a and digest_b and digest_a != digest_b
    assert _install(cache, _env(shim, repo_a))["success"]
    pair_a = _pair(cache)
    assert pair_a[0] == digest_a
    assert json.loads(pair_a[1])["artifact_sha256"] == digest_a

    # B unpinned: refused before the commit section; nothing changes.
    unpinned = Child(
        "from pathlib import Path\n"
        "from chunker.grammar_management.core import GrammarInstaller\n"
        "installer = GrammarInstaller(cache_dir=Path(ARGS[0]), trusted_artifacts={})\n"
        "emit('ready'); wait()\n"
        f"ok, error, _ = installer.install_grammar('baml', {URL!r})\n"
        "emit('done', success=ok, error=error)\n",
        [cache],
        env=_env(shim, repo_b),
    )
    try:
        unpinned.expect("ready")
        unpinned.release()
        refused = unpinned.finish()
    finally:
        unpinned.close()
    assert not refused["success"] and "untrusted" in refused["error"]
    assert not any(e["event"] == "rollback.after_capture" for e in unpinned.seen)
    assert _pair(cache) == pair_a and _rollback_points(cache) == []

    # B pinned, with the staged artifact damaged just before the commit.
    with participants() as children:
        child = _installer(cache, _env(shim, repo_b), pauses=[COMMIT_PAUSE])
        children.append(child)
        child.expect("ready")
        child.release()
        child.expect("lock.before_acquire", primitive="cache_lock", section="commit")
        _damage_staged(cache, failure)
        child.release()
        done = child.finish()
    events = [e["event"] for e in child.seen]
    assert (
        "metadata.after_replace" in events
    )  # the metadata was published, then restored
    assert not done["success"]
    assert "The previous installation was restored." in done["error"]
    assert _pair(cache) == pair_a
    assert _rollback_points(cache) == []
    _require_restored_a(cache, digest_a, digest_b)


# --- admission before any work --------------------------------------------------


@pytest.mark.parametrize(
    "pins",
    [{}, {"baml": {"sha256": 1}}, {"baml": "0" * 64}, {"python": {"sha256": "0" * 64}}],
    ids=["none", "non_str", "non_mapping", "other_language"],
)
def test_missing_pin_refuses_before_staging_or_probe(tmp_path, monkeypatch, pins):
    """No pin: untrusted before staging, clone, build, validation, probe or capture."""
    calls: list[str] = []

    def record(name, _real):
        def refuse(*args, **kwargs):
            # Recorded and refused, so a regression never clones or builds.
            calls.append(name)
            raise AssertionError(f"{name} ran for an unpinned install")

        return refuse

    for owner, name in (
        (_transactions, "create_staging"),
        (_transactions, "run_in_staging"),
        (_transactions, "create_rollback_point"),
        (_transactions, "publish_installation_metadata"),
        (GrammarInstaller, "_download_grammar"),
        (GrammarInstaller, "_build_grammar"),
        (GrammarValidator, "validate_grammar"),
        (integrity, "probe_native_grammar"),
        (user_grammar_tools, "probe_native_grammar"),
        (user_grammar_tools, "publish_native_grammar"),
    ):
        monkeypatch.setattr(owner, name, record(name, getattr(owner, name)))
    cache = tmp_path / "cache"
    installer = GrammarInstaller(cache_dir=cache, trusted_artifacts=pins)
    before = _tree(cache)
    ok, error, info = installer.install_grammar("baml", URL)
    assert (ok, info) == (False, None)
    assert error == (
        "Grammar baml is untrusted: no pinned sha256 was supplied for it, "
        "so nothing was installed"
    )
    assert calls == []
    assert _tree(cache) == before  # no staging, capture or metadata


@pytest.mark.parametrize(
    ("language", "source", "version", "expected"),
    [
        ("../baml", URL, None, "Invalid grammar language"),
        ("baml", "file:///etc", None, "Download failed: Invalid grammar source: "),
        ("baml", URL, "--upload-pack=x", "Download failed: Invalid grammar version"),
    ],
    ids=["language", "source", "version"],
)
def test_unsafe_inputs_are_rejected_before_the_pin_check(
    tmp_path, language, source, version, expected
):
    """Unsafe language, source and version keep their own messages, unpinned."""
    cache = tmp_path / "cache"
    installer = GrammarInstaller(cache_dir=cache, trusted_artifacts={})
    before = _tree(cache)
    ok, error, _ = installer.install_grammar(language, source, version)
    assert not ok and error.startswith(expected), error
    assert "untrusted" not in error
    assert _tree(cache) == before


# --- metadata digest and post-publication failures ------------------------------

WRONG_DIGEST = (
    PINS
    + r"""
from pathlib import Path
from chunker.grammar_management.core import GrammarInstaller
real_publish = _transactions.publish_installation_metadata


def publish(*args, **kwargs):
    real_publish(*args, **kwargs)
    return "0" * 64  # the returned digest disagrees with the intended one


_transactions.publish_installation_metadata = publish
installer = GrammarInstaller(cache_dir=Path(ARGS[0]), trusted_artifacts=pins)
emit("ready")
wait()
ok, error, _ = installer.install_grammar("baml", "https://github.com/example/tree-sitter-baml")
emit("done", success=ok, error=error)
"""
)


@POSIX_SHIM
def test_metadata_digest_mismatch_restores_the_pair(tmp_path, shim):
    """Commit step 2: a returned digest other than ``intended_sha256`` restores.

    The bytes on disk are the intended ones, so the restore table's
    (``Ap``, ``Mi``) row returns A's metadata; the participant never reports
    its own metadata as ``superseded`` (N7). The artifact is never published.
    Mutation ``skip_metadata_digest_check`` installs B.
    """
    cache = tmp_path / "cache"
    repo_a = _repo(tmp_path / "repo-a", minor=1)
    repo_b = _repo(tmp_path / "repo-b", minor=2)
    assert _install(cache, _env(shim, repo_a))["success"]
    pair_a = _pair(cache)
    child = Child(WRONG_DIGEST, [cache], env=_env(shim, repo_b))
    try:
        child.expect("ready")
        child.release()
        done = child.finish()
    finally:
        child.close()
    assert not done["success"]
    assert "published metadata digest" in done["error"], done["error"]
    assert "The previous installation was restored." in done["error"]
    assert "non-participant" not in done["error"]
    assert "commit.after_metadata" not in [e["event"] for e in child.seen]
    assert _pair(cache) == pair_a
    assert _rollback_points(cache) == []


FAIL_AFTER_PUBLICATION = (
    PINS
    + r"""
from pathlib import Path
from chunker._internal import user_grammar_tools
from chunker.grammar_management.core import GrammarInstaller
real_publish = user_grammar_tools.publish_native_grammar
calls = []


def publish(*args, **kwargs):
    calls.append(kwargs.get("provenance"))
    result = real_publish(*args, **kwargs)
    if len(calls) == 1:  # the commit's own publication
        raise OSError(f"injected after publication ({result.reason})")
    return result


user_grammar_tools.publish_native_grammar = publish
installer = GrammarInstaller(cache_dir=Path(ARGS[0]), trusted_artifacts=pins)
emit("ready")
wait()
ok, error, _ = installer.install_grammar("baml", "https://github.com/example/tree-sitter-baml")
emit("done", success=ok, error=error, provenance=calls)
"""
)


def _point_from_manifest(cache: Path, operation_id: str) -> _transactions.RollbackPoint:
    manifest = json.loads(
        (cache / ".txn" / "rollback" / operation_id / "rollback.json").read_text(
            encoding="utf-8"
        )
    )
    return _transactions.RollbackPoint(
        root=cache,
        operation_id=operation_id,
        language=manifest["language"],
        path=cache.absolute() / ".txn" / "rollback" / operation_id,
        artifact=cache.absolute() / manifest["artifact"]["path"],
        metadata=cache.absolute() / manifest["metadata"]["path"],
        previous_artifact_sha256=manifest["artifact"]["previous_sha256"],
        previous_metadata_sha256=manifest["metadata"]["previous_sha256"],
        intended_artifact_sha256=manifest["artifact"]["intended_sha256"],
        intended_metadata_sha256=manifest["metadata"]["intended_sha256"],
    )


@POSIX_SHIM
def test_installer_restore_never_uses_rollback_digest_as_provenance(tmp_path, shim):
    """Production restore limit: only B's pin is configured.

    A failure after B's artifact was published makes the installer restore
    with B's pin record, the only one it has. The probe rejects A's copy, so
    the pair stays (B, B), consistent and admitted, and the point is
    retained. Republishing A needs independently supplied A provenance.
    Mutation ``installer_rollback_provenance`` (pass the rollback point's
    previous digest as provenance) republishes A.
    """
    cache = tmp_path / "cache"
    repo_a = _repo(tmp_path / "repo-a", minor=1)
    repo_b = _repo(tmp_path / "repo-b", minor=2)
    digest_a, digest_b = _fixture_digest(repo_a), _fixture_digest(repo_b)
    assert digest_a and digest_b
    assert _install(cache, _env(shim, repo_a))["success"]
    pair_a = _pair(cache)
    child = Child(FAIL_AFTER_PUBLICATION, [cache], env=_env(shim, repo_b))
    try:
        child.expect("ready")
        child.release()
        done = child.finish()
    finally:
        child.close()
    assert not done["success"]
    assert "injected after publication (ok)" in done["error"]
    assert "Restore incomplete" in done["error"]
    assert "not admitted (integrity_mismatch)" in done["error"]
    assert done["provenance"] == [{"sha256": digest_b}] * 2
    artifact, metadata = _pair(cache)
    assert artifact == digest_b
    assert json.loads(metadata)["artifact_sha256"] == digest_b
    health = _health(cache, digest_b)
    assert (health["status"], health["validation_reason"]) == ("healthy", "ok")

    (operation_id,) = _rollback_points(cache)
    point = _point_from_manifest(cache, operation_id)
    assert point.previous_artifact_sha256 == digest_a
    result = _transactions.restore(
        point, provenance={"sha256": digest_a}, invalidate=lambda _: None
    )
    assert result.restored, result.errors
    assert _pair(cache) == pair_a
    assert _rollback_points(cache) == []
    _require_restored_a(cache, digest_a, digest_b)


RESTORE_RAISES = (
    PINS
    + r"""
from pathlib import Path
from chunker._internal import user_grammar_tools
from chunker.grammar_management.core import GrammarInstaller
fault = ARGS[1]


def publish(*args, **kwargs):
    if fault == "interrupt":
        raise KeyboardInterrupt
    raise OSError("injected publication failure")


def restore(*args, **kwargs):
    raise OSError("injected restore failure")


user_grammar_tools.publish_native_grammar = publish
_transactions.restore = restore
installer = GrammarInstaller(cache_dir=Path(ARGS[0]), trusted_artifacts=pins)
emit("ready")
wait()
try:
    ok, error, _ = installer.install_grammar("baml", "https://github.com/example/tree-sitter-baml")
except KeyboardInterrupt:
    emit("done", interrupted=True, success=False, error=None)
else:
    emit("done", interrupted=False, success=ok, error=error)
"""
)


@POSIX_SHIM
@pytest.mark.parametrize("fault", ["oserror", "interrupt"])
def test_raising_restore_keeps_the_original_failure(tmp_path, shim, fault):
    """A restore that raises is reported with the commit's own failure.

    The point is retained for the operator, and a ``KeyboardInterrupt`` from
    the commit is still re-raised. Mutation ``unguarded_restore`` lets the
    restore's exception replace both.
    """
    cache = tmp_path / "cache"
    child = Child(
        RESTORE_RAISES, [cache, fault], env=_env(shim, _repo(tmp_path / "repo"))
    )
    try:
        child.expect("ready")
        child.release()
        done = child.finish()
    finally:
        child.close()
    if fault == "interrupt":
        assert done["interrupted"], done
    else:
        assert not done["interrupted"] and not done["success"]
        assert "OSError: injected publication failure" in done["error"], done
        assert "restore raised OSError: injected restore failure" in done["error"]
        assert "Restore incomplete" in done["error"]
    assert len(_rollback_points(cache)) == 1


@POSIX_SHIM
def test_unreadable_previous_metadata_does_not_block_install(tmp_path, shim):
    """Truncated metadata (the old writer was not atomic) is replaced on install.

    Mutation ``strict_previous_metadata`` fails every install of the language.
    """
    cache = tmp_path / "cache"
    (cache / "grammars").mkdir(parents=True)
    (cache / "grammars" / "baml_install_info.json").write_bytes(b'{"version": ')
    repo = _repo(tmp_path / "repo")
    done = _install(cache, _env(shim, repo))
    assert done["success"], done
    assert json.loads(_pair(cache)[1])["artifact_sha256"] == _fixture_digest(repo)
    assert _pair(cache)[0] == _fixture_digest(repo)
    assert _rollback_points(cache) == []


@POSIX_SHIM
def test_install_over_a_record_outside_grammars_is_refused(tmp_path, shim):
    """Recorded metadata outside ``grammars/`` refuses the install, unchanged.

    The record is read under the commit's hold, before capture. Mutation
    ``skip_previous_check`` captures and installs over it.
    """
    cache = tmp_path / "cache"
    outside = tmp_path / "user" / "libbaml.so"
    outside.parent.mkdir()
    outside.write_bytes(b"user library")
    GrammarInstaller(cache_dir=cache, trusted_artifacts={})._save_installation_info(
        "baml",
        InstallationInfo(
            version="user", install_date=0, install_path=outside, source_url=URL
        ),
    )
    before = _pair(cache)
    assert before[0] is None and before[1] is not None
    done = _install(cache, _env(shim, _repo(tmp_path / "repo")))
    assert not done["success"]
    assert "is not under" in done["error"], done
    assert _pair(cache) == before
    assert _rollback_points(cache) == []
    assert outside.read_bytes() == b"user library"


@POSIX_SHIM
def test_upper_case_pin_records_lower_case_digest(tmp_path, shim, caplog):
    """An upper-case pin is admitted; metadata and capture use hashlib's form.

    Otherwise the next capture would report a false mismatch (N9), and a
    restore could not recognise the artifact it published. Mutation
    ``record_pin_case`` records the pin as given.
    """
    cache = tmp_path / "cache"
    repo_a = _repo(tmp_path / "repo-a", minor=1)
    repo_b = _repo(tmp_path / "repo-b", minor=2)
    digest_a, digest_b = _fixture_digest(repo_a), _fixture_digest(repo_b)
    assert digest_a and digest_b
    first = _install(cache, _env(shim, repo_a, TXN_PIN_SHA256=digest_a.upper()))
    assert first["success"], first
    assert json.loads(_pair(cache)[1])["artifact_sha256"] == digest_a
    second = _install(cache, _env(shim, repo_b, TXN_PIN_SHA256=digest_b.upper()))
    assert second["success"], second
    assert not [w for w in second["warnings"] if "names artifact" in w]
    assert _pair(cache)[0] == digest_b
    assert json.loads(_pair(cache)[1])["artifact_sha256"] == digest_b


# --- restore branches (direct) --------------------------------------------------


def _published_pair(root: Path, rev_a: Path, rev_b: Path):
    """A published at A, a real rollback point, then B really published."""
    root.mkdir()
    _transactions.open_cache_root(root)
    destination = root / "grammars" / "libbaml.so"
    destination.parent.mkdir()
    assert publish_native_grammar(
        rev_a, destination, "baml", provenance=_pin(rev_a)
    ).supported

    def document(revision: str, path: Path) -> dict:
        return {
            "version": revision,
            "install_date": 0,
            "install_path": str(destination),
            "source_url": URL,
            "source_commit": None,
            "priority": "USER",
            "dependencies": [],
            "metadata": {},
            "artifact_sha256": _sha(path),
        }

    _transactions.publish_installation_metadata(root, "baml", document("a", rev_a))
    pair_a = _pair(root)
    point = _transactions.create_rollback_point(
        root,
        language="baml",
        artifact=destination,
        metadata_document=document("b", rev_b),
        artifact_sha256=_sha(rev_b),
    )
    _transactions.publish_installation_metadata(root, "baml", document("b", rev_b))
    assert publish_native_grammar(
        rev_b, destination, "baml", provenance=_pin(rev_b)
    ).supported
    pair_b = _pair(root)
    assert pair_b[0] == _sha(rev_b) != pair_a[0]
    return point, pair_a, pair_b


@pytest.fixture
def held_fds(monkeypatch):
    """Record, at ``restore.before_artifact``, whether the lock fd is inheritable."""
    seen: list[bool] = []

    def barrier(point, context):
        if point == "restore.before_artifact":
            holds = [h for h in _transactions._HOLDS.values() if h.owner is not None]
            seen.extend(os.get_inheritable(h.lock_fd) for h in holds)

    monkeypatch.setattr(_transactions, "_BARRIER", barrier)
    return seen


def test_restore_with_previous_pin_returns_both_files(tmp_path, revisions, held_fds):
    """(a) Both files return to A; the lock is not inheritable during the probe.

    On Windows this shows handle release: the replaced library is not held.
    """
    rev_a, rev_b = revisions
    point, pair_a, _ = _published_pair(tmp_path / "cache", rev_a, rev_b)
    invalidated: list[Path] = []
    result = _transactions.restore(
        point, provenance=_pin(rev_a), invalidate=invalidated.append
    )
    assert (result.restored, result.artifact_restored, result.metadata_restored) == (
        True,
    ) * 3
    assert not result.superseded and result.errors == ()
    assert _pair(tmp_path / "cache") == pair_a
    assert invalidated == [point.artifact]
    assert held_fds == [False]
    assert not point.path.exists()
    assert _parse_version(point.artifact, _sha(rev_a)) == [0, 1, 0]


def test_restore_without_previous_pin_keeps_artifact_and_metadata_b(
    tmp_path, revisions
):
    """(b) The probe rejects A's copy under B's pin: the pair stays B.

    Mutations ``restore_without_admission`` and
    ``restore_metadata_independently`` change the pair.
    """
    rev_a, rev_b = revisions
    point, _, pair_b = _published_pair(tmp_path / "cache", rev_a, rev_b)
    result = _transactions.restore(
        point, provenance=_pin(rev_b), invalidate=lambda _: None
    )
    assert not result.restored and not result.artifact_restored
    assert not result.metadata_restored and not result.superseded
    assert any("not admitted" in e for e in result.errors)
    assert _pair(tmp_path / "cache") == pair_b
    assert (point.path / "rollback.json").is_file()


@pytest.mark.parametrize("when", ["before_call", "at_barrier"])
def test_restore_is_superseded_by_non_participant_replacement(
    tmp_path, revisions, monkeypatch, when
):
    """(c) A non-participant replaced the artifact: neither file is touched.

    ``before_call`` replaces it before ``restore`` (Claude N2); ``at_barrier``
    replaces it at ``restore.before_artifact``, which ``restore`` re-observes
    (Codex finding 3).
    """
    rev_a, rev_b = revisions
    point, _, pair_b = _published_pair(tmp_path / "cache", rev_a, rev_b)
    foreign = tmp_path / "foreign.so"
    foreign.write_bytes(b"not a grammar")

    def replace() -> None:
        shutil.copyfile(foreign, tmp_path / "staged")
        (tmp_path / "staged").replace(point.artifact)

    if when == "before_call":
        replace()
    else:
        monkeypatch.setattr(
            _transactions,
            "_BARRIER",
            lambda p, _c: replace() if p == "restore.before_artifact" else None,
        )
    result = _transactions.restore(
        point, provenance=_pin(rev_a), invalidate=lambda _: None
    )
    assert result.superseded and not result.restored
    assert _pair(tmp_path / "cache") == (_sha(foreign), pair_b[1])
    assert (point.path / "rollback.json").is_file()


def test_restore_with_raising_invalidation_still_restores(tmp_path, revisions, caplog):
    """(d) Invalidation is non-fatal: same outcome plus a warning."""
    rev_a, rev_b = revisions
    point, pair_a, _ = _published_pair(tmp_path / "cache", rev_a, rev_b)

    def invalidate(_path: Path) -> None:
        raise RuntimeError("cache refresh failed")

    with caplog.at_level(logging.WARNING):
        result = _transactions.restore(
            point, provenance=_pin(rev_a), invalidate=invalidate
        )
    assert result.restored
    assert result.warnings == ("Cache invalidation failed: cache refresh failed",)
    assert _pair(tmp_path / "cache") == pair_a


HOLD_LOADED = r"""
from pathlib import Path
from chunker.grammar_management.core import load_compiled_grammar
parser = load_compiled_grammar(Path(ARGS[0]), "baml")
emit("ready")
wait()
emit("done")
"""


@pytest.mark.skipif(sys.platform != "win32", reason="Windows loaded-library refusal")
def test_restore_refused_while_another_process_has_the_library_loaded(
    tmp_path, revisions
):
    """Windows refuses to replace a loaded library: restore fails, keeps the point."""
    rev_a, rev_b = revisions
    point, _, pair_b = _published_pair(tmp_path / "cache", rev_a, rev_b)
    with participants() as children:
        holder = Child(HOLD_LOADED, [point.artifact])
        children.append(holder)
        holder.expect("ready")
        result = _transactions.restore(
            point, provenance=_pin(rev_a), invalidate=lambda _: None
        )
        holder.release()
        holder.finish()
    assert not result.restored and not result.artifact_restored
    assert _pair(tmp_path / "cache") == pair_b
    assert (point.path / "rollback.json").is_file()
    retried = _transactions.restore(
        point, provenance=_pin(rev_a), invalidate=lambda _: None
    )
    assert retried.restored  # once the handle is released


# --- serialization, crash and removal -------------------------------------------

READER = r"""
import json
from hashlib import sha256
from pathlib import Path
root = Path(ARGS[0])
_transactions.open_cache_root(root)
emit("ready")
wait()
with _transactions.cache_lock(root):
    metadata = _transactions.read_installation_metadata(root, "baml")
    library = root / "grammars" / "libbaml.so"
    digest = sha256(library.read_bytes()).hexdigest()
emit("done", recorded=metadata["artifact_sha256"], actual=digest)
"""

REMOVER = r"""
from pathlib import Path
from chunker.grammar_management.core import GrammarInstaller, GrammarManager
cache = Path(ARGS[0])
if ARGS[1] == "manager":
    consumer = GrammarManager(
        user_dir=cache / "grammars", package_dir=Path(ARGS[2]), cache_dir=cache
    )
else:
    consumer = GrammarInstaller(cache_dir=cache)
emit("ready")
wait()
emit("done", result=list(consumer.remove_grammar("baml")))
"""


def _update_paused_at_metadata(cache, shim, repo):
    child = _installer(
        cache,
        _env(shim, repo),
        pauses=[pause_at("commit.after_metadata", section="commit")],
    )
    child.expect("ready")
    child.release()
    child.expect("commit.after_metadata", section="commit")
    return child


@POSIX_SHIM
def test_reader_waits_for_the_whole_commit(tmp_path, shim):
    """(a) Paused after the metadata publication, the commit still holds the lock.

    The pause point ``commit.after_metadata`` (Claude N1) fires after the
    metadata's own nested hold is released. A reader contends and then sees
    a consistent pair. Mutation ``commit_without_lock`` lets it read B's
    metadata beside A's artifact.
    """
    cache = tmp_path / "cache"
    assert _install(cache, _env(shim, _repo(tmp_path / "a", minor=1)))["success"]
    repo_b = _repo(tmp_path / "b", minor=2)
    with participants() as children:
        reader = Child(READER, [cache])
        children.append(reader)
        reader.expect("ready")
        installer = _update_paused_at_metadata(cache, shim, repo_b)
        children.append(installer)
        reader.release()
        first = reader.expect_any("lock.contended", "lock.acquired")
        assert (first["event"], first["primitive"]) == ("lock.contended", "cache_lock")
        installer.release()
        assert installer.finish()["success"]
        read = reader.finish()
    assert read["recorded"] == read["actual"] == _fixture_digest(repo_b)


@POSIX_SHIM
def test_crash_after_metadata_is_detectable_and_recoverable(tmp_path, shim, caplog):
    """(b) A crash after the metadata replace leaves ``Mi`` beside ``Ap``.

    The mismatch is reported before the next capture (Claude N9), and the
    operator procedure on ``rollback.json`` restores A's pair.
    """
    cache = tmp_path / "cache"
    assert _install(cache, _env(shim, _repo(tmp_path / "a", minor=1)))["success"]
    pair_a = _pair(cache)
    repo_b = _repo(tmp_path / "b", minor=2)
    child = _installer(
        cache,
        _env(shim, repo_b),
        pauses=[
            exit_at("metadata.after_replace", primitive="publish_installation_metadata")
        ],
    )
    try:
        child.expect("ready")
        child.release()
        child.expect("metadata.after_replace")
        assert child.exit_code() == 17
    finally:
        child.close()
    artifact, metadata = _pair(cache)
    assert artifact == pair_a[0]
    assert json.loads(metadata)["artifact_sha256"] == _fixture_digest(repo_b)
    assert _fixture_digest(repo_b) != artifact
    (point,) = _rollback_points(cache)
    manifest_path = cache / ".txn" / "rollback" / point / "rollback.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    with caplog.at_level(logging.WARNING):
        probe = _transactions.create_rollback_point(
            cache,
            language="baml",
            artifact=cache / "grammars" / "libbaml.so",
            metadata_document={"install_path": str(cache / "grammars" / "libbaml.so")},
            artifact_sha256=_fixture_digest(repo_b),
        )
    assert any(str(manifest_path) in r.getMessage() for r in caplog.records)
    _transactions.discard_rollback_point(probe)

    # Operator procedure, step 3: the artifact is at its previous digest.
    assert (
        _sha(cache / manifest["artifact"]["path"])
        == manifest["artifact"]["previous_sha256"]
    )
    previous = (
        cache / ".txn" / "rollback" / point / manifest["metadata"]["previous_copy"]
    )
    assert (
        sha256(previous.read_bytes()).hexdigest()
        == manifest["metadata"]["previous_sha256"]
    )
    shutil.copyfile(previous, cache / manifest["metadata"]["path"])
    shutil.rmtree(cache / ".txn" / "rollback" / point)
    assert _pair(cache) == pair_a


@POSIX_SHIM
@pytest.mark.parametrize("state", ["update", "fresh"])
@pytest.mark.parametrize("consumer", ["installer", "manager"])
def test_removal_during_a_paused_commit_waits_and_stays_removed(
    tmp_path, shim, consumer, state
):
    """(d) Removal contends with a paused commit; nothing comes back.

    ``fresh`` pauses the first install of the language, when only its metadata
    exists. Mutation ``manager_unlocked_lookup`` (the manager's old registry
    check before the installer's locked section) reports the fresh install
    as not found without waiting.
    """
    cache = tmp_path / "cache"
    if state == "update":
        assert _install(cache, _env(shim, _repo(tmp_path / "a", minor=1)))["success"]
    repo_b = _repo(tmp_path / "b", minor=2)
    with participants() as children:
        remover = Child(REMOVER, [cache, consumer, tmp_path / "package"])
        children.append(remover)
        remover.expect("ready")
        installer = _update_paused_at_metadata(cache, shim, repo_b)
        children.append(installer)
        remover.release()
        remover.expect("lock.contended")
        installer.release()
        assert installer.finish()["success"]
        assert remover.finish()["result"] == [True, None]
    assert _pair(cache) == (None, None)
    assert _rollback_points(cache) == []


@pytest.mark.parametrize("consumer", ["installer", "manager"])
def test_metadata_without_artifact_is_removed(tmp_path, consumer):
    """Metadata whose artifact is gone (a crash between commit steps) is removable.

    Mutation ``manager_unlocked_lookup`` reports it as not found, leaving the
    metadata in place.
    """
    cache = tmp_path / "cache"
    manager = GrammarManager(
        user_dir=cache / "grammars", package_dir=tmp_path / "package", cache_dir=cache
    )
    _transactions.publish_installation_metadata(
        cache,
        "baml",
        {
            "version": "latest",
            "install_date": 0,
            "install_path": str(cache / "grammars" / "libbaml.so"),
            "source_url": URL,
            "source_commit": None,
            "priority": "USER",
            "dependencies": [],
            "metadata": {},
            "artifact_sha256": "0" * 64,
        },
    )
    assert _pair(cache)[0] is None and _pair(cache)[1] is not None
    target = manager if consumer == "manager" else manager._installer
    assert target.remove_grammar("baml") == (True, None)
    assert _pair(cache) == (None, None)


@pytest.mark.parametrize("kind", ["directory", "symlink"])
def test_removal_refuses_a_non_regular_artifact(tmp_path, kind):
    """Containment rule 2: only a regular file is removed at the artifact name.

    A directory (or a link) at ``grammars/libbaml.so`` makes removal fail with
    nothing moved: the directory's files, the link's target and the metadata
    are all kept. Mutation ``retire_any_artifact`` (retire whatever is there)
    deletes the directory tree and the metadata.
    """
    cache = tmp_path / "cache"
    installer = GrammarInstaller(cache_dir=cache, trusted_artifacts={})
    artifact = cache / "grammars" / "libbaml.so"
    outside = tmp_path / "outside.so"
    outside.write_bytes(b"keep")
    if kind == "directory":
        artifact.mkdir()
        (artifact / "kept.txt").write_bytes(b"keep")
    else:
        try:
            artifact.symlink_to(outside)
        except OSError as error:
            pytest.skip(f"symlinks unavailable: {error}")
    _transactions.publish_installation_metadata(
        cache,
        "baml",
        {
            "version": "latest",
            "install_date": 0,
            "install_path": str(artifact),
            "source_url": URL,
            "source_commit": None,
            "priority": "USER",
            "dependencies": [],
            "metadata": {},
        },
    )
    metadata = _pair(cache)[1]
    ok, error = installer.remove_grammar("baml")
    assert not ok and "is not a regular file; nothing was removed" in error, error
    assert _pair(cache)[1] == metadata
    if kind == "directory":
        assert (artifact / "kept.txt").read_bytes() == b"keep"
    else:
        assert artifact.is_symlink() and outside.read_bytes() == b"keep"
    with pytest.raises(_transactions.ContainmentError):
        _transactions.remove_installation(cache, "baml")
    assert _pair(cache)[1] == metadata


SPLIT_GRAMMARS = r"""
import json, sys
from hashlib import sha256
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from chunker._internal.user_grammar_tools import publish_native_grammar
from chunker.grammar_management import _transactions as t

root, rev_a, rev_b = Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
pin = lambda p: {"sha256": sha256(p.read_bytes()).hexdigest()}
destination = root / "grammars" / "libbaml.so"
doc = lambda tag, p: {"version": tag, "install_path": str(destination),
                      "artifact_sha256": pin(p)["sha256"]}
outcomes = {}
try:
    t.open_cache_root(root)
    mount_tmpfs(root / "grammars")  # grammars/ is its own filesystem
    outcomes["split"] = destination.parent.stat().st_dev != root.stat().st_dev
    # A fresh install that fails after publishing: restore retires both files.
    fresh = t.create_rollback_point(root, language="baml", artifact=destination,
                                    metadata_document=doc("a", rev_a),
                                    artifact_sha256=pin(rev_a)["sha256"])
    t.publish_installation_metadata(root, "baml", doc("a", rev_a))
    outcomes["publish_a"] = publish_native_grammar(rev_a, destination, "baml", provenance=pin(rev_a)).supported
    result = t.restore(fresh, provenance=pin(rev_a), invalidate=lambda _: None)
    outcomes["fresh_restore"] = [result.restored, list(result.errors)]
    outcomes["fresh_gone"] = not destination.exists() and t.read_installation_metadata(root, "baml") is None
    # A to B, then restore to A.
    t.publish_installation_metadata(root, "baml", doc("a", rev_a))
    publish_native_grammar(rev_a, destination, "baml", provenance=pin(rev_a))
    point = t.create_rollback_point(root, language="baml", artifact=destination,
                                    metadata_document=doc("b", rev_b),
                                    artifact_sha256=pin(rev_b)["sha256"])
    t.publish_installation_metadata(root, "baml", doc("b", rev_b))
    publish_native_grammar(rev_b, destination, "baml", provenance=pin(rev_b))
    result = t.restore(point, provenance=pin(rev_a), invalidate=lambda _: None)
    outcomes["restore"] = [result.restored, pin(destination) == pin(rev_a)]
    removed = t.remove_installation(root, "baml")
    outcomes["remove"] = [removed.entries_removed, list(removed.errors)]
    outcomes["left"] = sorted(p.name for p in (root / "grammars").iterdir())
finally:
    unmount_all()
print(json.dumps(outcomes))
"""


def test_split_mount_grammars_restore_and_remove(tmp_path, revisions):
    """Amendment A1 for Primitive 3: a separate filesystem at ``grammars/``.

    Restore (including retiring a fresh install's files) and removal retire
    into ``grammars/.txn-retired/`` on the same filesystem and succeed.
    Mutation ``retire_outside_namespace`` fails with ``EXDEV``.
    """
    rev_a, rev_b = revisions
    root = tmp_path / "cache"
    root.mkdir()
    result = run_mounting(SPLIT_GRAMMARS, [root, rev_a, rev_b])
    assert result.returncode == 0, result.stderr[-3000:]
    outcomes = json.loads(result.stdout.strip().splitlines()[-1])
    assert outcomes == {
        "split": True,
        "publish_a": True,
        "fresh_restore": [True, []],
        "fresh_gone": True,
        "restore": [True, True],
        "remove": [1, []],
        "left": [".txn-retired"],
    }


def test_download_cache_cleanup_keeps_retired_grammars_folder(tmp_path):
    """Runner decision (treesitter-chunker#564 round 2): a non-participant.

    ``GrammarDownloadManager.clean_cache`` defaults to the core ``grammars/``
    folder and removes ``-``-named directories beyond the newest few. It must
    never remove ``grammars/.txn-retired``. Mutation ``download_cleanup_sees_txn``
    deletes it.
    """
    from chunker.grammar.download import GrammarDownloadManager

    grammars = tmp_path / "grammars"
    retired = grammars / ".txn-retired" / ("0" * 32)
    retired.mkdir(parents=True)
    (retired / "libold.so").write_bytes(b"r")
    os.utime(grammars / ".txn-retired", (1, 1))  # the oldest "-" directory
    for index in range(3):
        directory = grammars / f"lang{index}-1.0"
        directory.mkdir()
        os.utime(directory, (100 + index, 100 + index))
    removed = GrammarDownloadManager(cache_dir=grammars).clean_cache(keep_recent=2)
    assert removed == 1
    assert not (grammars / "lang0-1.0").exists()
    assert (retired / "libold.so").read_bytes() == b"r"


# --- follow-ups: treesitter-chunker#618, #619, #620 -----------------------------

SAVE_INFO = r"""
from pathlib import Path
from chunker.grammar_management.core import GrammarInstaller, InstallationInfo
cache = Path(ARGS[0])
library = cache / "grammars" / "libbaml.so"
installer = GrammarInstaller(cache_dir=cache, trusted_artifacts={})
emit("ready")
wait()
# Pause at the save's first lock attempt, after construction's own sections.
PAUSES.append({"point": "lock.before_acquire", "match": {}})
installer._save_installation_info(
    "baml",
    InstallationInfo(version="a", install_date=0, install_path=library,
                     source_url="https://github.com/example/tree-sitter-baml"),
)
emit("done")
"""


def test_saved_metadata_digest_is_hashed_under_the_lock(tmp_path):
    """treesitter-chunker#618: the recorded digest describes the published library.

    ``_save_installation_info`` pauses at its first lock attempt; a
    participant then replaces the library under the lock. The digest is taken
    inside the section that writes the metadata, so it names the library on
    disk when the metadata is published. Mutation ``hash_outside_lock``
    (hash before taking the lock) records the replaced bytes' digest.
    """
    cache = tmp_path / "cache"
    library = cache / "grammars" / "libbaml.so"
    library.parent.mkdir(parents=True)
    library.write_bytes(b"revision a")
    child = Child(SAVE_INFO, [cache])
    try:
        child.expect("ready")
        child.release()
        child.expect("lock.before_acquire")
        with _transactions.cache_lock(cache):
            staged = library.with_name("libbaml.so.replacement")
            staged.write_bytes(b"revision b")
            staged.replace(library)
        child.release()
        child.finish()
    finally:
        child.close()
    metadata = json.loads(_pair(cache)[1])
    assert metadata["artifact_sha256"] == sha256(b"revision b").hexdigest()
    assert _sha(library) == metadata["artifact_sha256"]


CAPTURE_EFBIG = r"""
import errno, json, resource, signal, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from chunker.grammar_management import _transactions as t

root = Path(sys.argv[2])
destination = root / "grammars" / "libbaml.so"
t.open_cache_root(root)
destination.parent.mkdir(exist_ok=True)
destination.write_bytes(b"\x7fELF" * (1 << 16))  # 256 KiB, beyond the limit
t.publish_installation_metadata(root, "baml", {"version": "a",
                                               "install_path": str(destination)})
# A real write error: the artifact copy fails with EFBIG part-way through.
signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024, hard))
outcome = {}
try:
    t.create_rollback_point(root, language="baml", artifact=destination,
                            metadata_document={"version": "b"},
                            artifact_sha256="0" * 64)
except OSError as error:
    outcome["errno"] = errno.errorcode.get(error.errno)
finally:
    resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))
print(json.dumps(outcome))
"""


@pytest.mark.skipif(
    sys.platform == "win32", reason="RLIMIT_FSIZE is a POSIX write limit"
)
def test_capture_io_error_leaves_no_partial_rollback_folder(tmp_path):
    """treesitter-chunker#619: a failed capture removes its own folder.

    A real ``EFBIG`` (``RLIMIT_FSIZE``) interrupts the copy of the previous
    library. Capture precedes every mutation, so the incomplete
    ``.txn/rollback/<op>/`` is retired and deleted; the installation is
    unchanged and no garbage is left in ``.txn/``. Mutation
    ``keep_partial_capture`` (skip the cleanup) leaves the folder with a
    truncated ``artifact.prev``.
    """
    cache = tmp_path / "cache"
    cache.mkdir()
    completed = subprocess.run(
        [sys.executable, "-I", "-c", CAPTURE_EFBIG, str(ROOT), str(cache)],
        capture_output=True,
        text=True,
        timeout=SAFETY_TIMEOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-4000:]
    outcome = json.loads(completed.stdout.strip().splitlines()[-1])
    assert outcome == {"errno": "EFBIG"}
    assert _rollback_points(cache) == []
    retired = cache / ".txn" / "retired"
    assert sorted(p.name for p in retired.iterdir() if p.name != ".txn-keep") == []
    assert _pair(cache)[0] == sha256(b"\x7fELF" * (1 << 16)).hexdigest()
    assert json.loads(_pair(cache)[1])["version"] == "a"


def _metadata_link(cache: Path, tmp_path: Path) -> tuple[Path, Path]:
    """A non-participant swaps the metadata for a link to an outside sentinel."""
    sentinel = tmp_path / "outside.json"
    sentinel.write_bytes(b"sentinel")
    metadata = cache / "grammars" / "baml_install_info.json"
    metadata.unlink()
    try:
        metadata.symlink_to(sentinel)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")
    return metadata, sentinel


@pytest.mark.parametrize("when", ["before_call", "at_barrier"])
def test_restore_refuses_linked_metadata_with_recovery_steps(
    tmp_path, revisions, monkeypatch, when
):
    """treesitter-chunker#620: a linked metadata file is refused, actionably.

    Containment rule 2 keeps the refusal: restore never follows or replaces
    the link, and neither file is touched. The error names the link to
    delete, the retained ``rollback.json`` to finish from, and says the
    link's target is left alone. ``before_call`` swaps the metadata before
    ``restore``; ``at_barrier`` swaps it at ``restore.before_artifact``, which
    ``restore`` checks again. Mutation ``bare_link_refusal`` (drop both checks)
    fails both; mutation ``M4`` (drop only the check after
    ``restore.before_artifact``) fails ``at_barrier``. Each raises only
    "Refusing to follow link".
    """
    rev_a, rev_b = revisions
    cache = tmp_path / "cache"
    point, _, pair_b = _published_pair(cache, rev_a, rev_b)
    linked: list[tuple[Path, Path]] = []
    if when == "before_call":
        linked.append(_metadata_link(cache, tmp_path))
    else:
        monkeypatch.setattr(
            _transactions,
            "_BARRIER",
            lambda p, _c: (
                linked.append(_metadata_link(cache, tmp_path))
                if p == "restore.before_artifact"
                else None
            ),
        )
    with pytest.raises(_transactions.ContainmentError) as raised:
        _transactions.restore(point, provenance=_pin(rev_a), invalidate=lambda _: None)
    ((metadata, sentinel),) = linked
    message = str(raised.value)
    assert f"delete {point.metadata}" in message, message
    assert str(point.path / "rollback.json") in message
    assert "neither installation file was touched" in message
    assert metadata.is_symlink() and sentinel.read_bytes() == b"sentinel"
    assert _sha(point.artifact) == pair_b[0]
    assert (point.path / "rollback.json").is_file()


LINK_DURING_COMMIT = (
    PINS
    + r"""
import os
from pathlib import Path
from chunker._internal import user_grammar_tools
from chunker.grammar_management.core import GrammarInstaller
cache, sentinel, target = Path(ARGS[0]), Path(ARGS[1]), ARGS[2]


def publish(*args, **kwargs):
    # A non-participant swaps an installation path for a link mid-commit.
    grammars = cache / "grammars"
    if target == "metadata":
        (grammars / "baml_install_info.json").unlink()
        os.symlink(sentinel, grammars / "baml_install_info.json")
    else:  # the grammars/ root becomes a link to a real directory
        os.rename(grammars, sentinel)
        os.symlink(sentinel, grammars, target_is_directory=True)
    raise OSError("injected publication failure")


user_grammar_tools.publish_native_grammar = publish
installer = GrammarInstaller(cache_dir=cache, trusted_artifacts=pins)
emit("ready")
wait()
ok, error, _ = installer.install_grammar(
    "baml", "https://github.com/example/tree-sitter-baml", "v2"
)
emit("done", success=ok, error=error)
"""
)


@POSIX_SHIM
def test_installer_names_the_recovery_for_linked_metadata(tmp_path, shim):
    """treesitter-chunker#620: the failed install says what to delete and re-run.

    Mutation ``bare_link_refusal`` reports only "Refusing to follow link".
    """
    cache = tmp_path / "cache"
    assert _install(cache, _env(shim, _repo(tmp_path / "a", minor=1)))["success"]
    artifact_a = _pair(cache)[0]
    sentinel = tmp_path / "outside.json"
    sentinel.write_bytes(b"sentinel")
    done = _install_with_link(tmp_path, shim, cache, sentinel, "metadata")
    metadata = cache.absolute() / "grammars" / "baml_install_info.json"
    (operation_id,) = _rollback_points(cache)
    manifest = cache.absolute() / ".txn" / "rollback" / operation_id / "rollback.json"
    assert not done["success"]
    error = done["error"]
    assert "OSError: injected publication failure" in error, error
    assert "Restore incomplete" in error
    assert "restore raised ContainmentError" in error
    assert f"delete {metadata}" in error
    assert str(manifest) in error
    assert (
        "After finishing that procedure, re-run install_grammar('baml', "
        "'https://github.com/example/tree-sitter-baml', 'v2')"
    ) in error
    assert metadata.is_symlink() and sentinel.read_bytes() == b"sentinel"
    assert _pair(cache)[0] == artifact_a


def _install_with_link(
    tmp_path: Path, shim: Path, cache: Path, sentinel: Path, target: str
) -> dict:
    child = Child(
        LINK_DURING_COMMIT,
        [cache, sentinel, target],
        env=_env(shim, _repo(tmp_path / "b", minor=2)),
    )
    try:
        child.expect("ready")
        child.release()
        return child.finish()
    finally:
        child.close()


@POSIX_SHIM
def test_installer_omits_rerun_for_a_linked_grammars_root(tmp_path, shim):
    """treesitter-chunker#620 RF1: only the up-front link refusal adds re-run.

    A ``grammars/`` root swapped for a link to a real directory is refused by
    a plain ``ContainmentError``, whose recovery is not the documented
    procedure. The error names the retained point and offers no re-run.
    Mutation ``rerun_for_any_containment`` (match any ``ContainmentError``)
    adds the re-run sentence.
    """
    cache = tmp_path / "cache"
    assert _install(cache, _env(shim, _repo(tmp_path / "a", minor=1)))["success"]
    real = tmp_path / "grammars-real"
    done = _install_with_link(tmp_path, shim, cache, real, "grammars_root")
    (operation_id,) = _rollback_points(cache)
    point = cache.absolute() / ".txn" / "rollback" / operation_id
    assert not done["success"]
    error = done["error"]
    assert "OSError: injected publication failure" in error, error
    assert "restore raised ContainmentError" in error
    assert f"rollback point retained: {point}" in error
    assert "re-run" not in error
    assert (cache / "grammars").is_symlink() and real.is_dir()


@pytest.mark.parametrize(
    ("priority", "expected"),
    [
        (GrammarPriority.USER, "install_grammar('baml', '{url}', 'v2')"),
        (
            GrammarPriority.PACKAGE,
            "install_grammar('baml', '{url}', 'v2', "
            "priority=GrammarPriority.PACKAGE)",
        ),
    ],
)
def test_install_call_names_a_non_user_priority(priority, expected):
    """treesitter-chunker#620 RF1: the re-run call repeats a non-USER priority.

    Mutation ``rerun_without_priority`` drops ``priority=``.
    """
    info = InstallationInfo(
        version="v2",
        install_date=0,
        install_path=Path("libbaml.so"),
        source_url=URL,
        priority=priority,
    )
    assert GrammarInstaller._install_call("baml", info) == expected.format(url=URL)


# --- Windows: a real installer failed update ------------------------------------

WINDOWS_TOOLCHAIN = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows installer fixture"
)

#: A console launcher: runs ``<its name>.cmdline`` (UTF-16-LE) followed by its
#: own arguments, verbatim, with inherited standard handles, and returns the
#: exit code. ``subprocess`` on Windows launches only real executables by name,
#: so the shims cannot be scripts.
LAUNCHER_C = r"""
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

static wchar_t self[MAX_PATH + 16];
static wchar_t prefix[16384];
static wchar_t line[32768];

int wmain(void) {
    DWORD n = GetModuleFileNameW(NULL, self, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return 120;
    wchar_t *dot = wcsrchr(self, L'.');
    if (dot == NULL) return 121;
    wcscpy(dot, L".cmdline");
    FILE *file = _wfopen(self, L"rb");
    if (file == NULL) return 122;
    size_t got = fread(prefix, sizeof(wchar_t), 16383, file);
    fclose(file);
    prefix[got] = 0;
    wchar_t *rest = GetCommandLineW();
    if (*rest == L'"') {
        rest++;
        while (*rest && *rest != L'"') rest++;
        if (*rest) rest++;
    } else {
        while (*rest && *rest != L' ' && *rest != L'\t') rest++;
    }
    if (wcslen(prefix) + wcslen(rest) >= 32767) return 123;
    wcscpy(line, prefix);
    wcscat(line, rest);
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof si);
    si.cb = sizeof si;
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    if (!CreateProcessW(NULL, line, NULL, NULL, TRUE, 0, NULL, NULL, &si, &pi))
        return 124;
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 125;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return (int)code;
}
"""

#: Each probe's reason, as a seam-style event (a typed policy channel).
PROBE_EVENTS = r"""
from chunker._internal import user_grammar_tools as _tools
from chunker.grammar import integrity as _integrity


def _reporting(real):
    def probe(*args, **kwargs):
        result = real(*args, **kwargs)
        emit("probe", reason=result.reason)
        return result

    return probe


_integrity.probe_native_grammar = _reporting(_integrity.probe_native_grammar)
_tools.probe_native_grammar = _reporting(_tools.probe_native_grammar)
"""


def _quote(path: Path | str) -> str:
    return f'"{path}"'


def _windows_shim(tmp_path: Path) -> tuple[Path, str]:
    """Executable ``git`` and ``tree-sitter`` shims; the installer's gcc path.

    The installer runs the MinGW ``gcc`` first on ``PATH`` itself, with its
    PE link flags (treesitter-chunker#621); no ``gcc`` shim is needed. A
    missing gcc fails on CI and is a typed skip elsewhere.
    """
    from tests.native_policy import skip_policy_error

    real_gcc = _installer_compiler()
    directory = tmp_path / "shim"
    directory.mkdir()
    source = tmp_path / "launcher.c"
    source.write_text(LAUNCHER_C, encoding="utf-8")
    launcher = tmp_path / "launcher.exe"
    built = subprocess.run(
        [real_gcc, "-O2", "-municode", str(source), "-o", str(launcher)],
        capture_output=True,
        text=True,
        timeout=SAFETY_TIMEOUT,
        check=False,
    )
    assert built.returncode == 0, built.stderr[-4000:]
    git_script = directory / "git-shim.py"
    git_script.write_text(SHIM.format(python=sys.executable), encoding="utf-8")
    commands = {
        "git": f"{_quote(sys.executable)} {_quote(git_script)}",
        "tree-sitter": f'{_quote(sys.executable)} -c "raise SystemExit(1)"',
    }
    for name, command in commands.items():
        shutil.copyfile(launcher, directory / f"{name}.exe")
        (directory / f"{name}.cmdline").write_bytes(command.encode("utf-16-le"))
    try:  # an Application Control refusal of the new launcher is a typed skip
        probe = subprocess.run(
            [str(directory / "tree-sitter.exe")],
            capture_output=True,
            timeout=SAFETY_TIMEOUT,
            check=False,
        )
    except OSError as error:
        skip_policy_error(error)
        raise
    assert probe.returncode == 1, probe
    return directory, real_gcc


def _windows_pin(real_gcc: str, repo: Path, work: Path) -> str:
    """Build ``repo`` with the installer's documented recipe (cwd = ``repo``)
    and output basename; return the digest."""
    work.mkdir()
    output = work / "libbaml.so"  # the PE export name is the output basename
    completed = subprocess.run(
        _build_recipe.gcc_build_argv(
            real_gcc,
            "baml",
            output,
            has_scanner=(repo / "src" / "scanner.c").exists(),
        ),
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=SAFETY_TIMEOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-4000:]
    return sha256(output.read_bytes()).hexdigest()


def _windows_env(shim_dir: Path, repo: Path, digest: str) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "TXN_GIT_FIXTURE": str(repo),
        "TXN_PIN_SHA256": digest,
    }


def _skip_on_policy_probe(child: Child) -> None:
    from chunker.grammar._native_policy import APPLICATION_CONTROL_MESSAGE

    if any(
        e["event"] == "probe" and e.get("reason") == "policy_blocked"
        for e in child.seen
    ):
        pytest.skip(APPLICATION_CONTROL_MESSAGE)


@WINDOWS_TOOLCHAIN
@pytest.mark.parametrize("failure", ["not_admitted", "raises"])
def test_windows_installer_failed_update_restores_previous_pair(tmp_path, failure):
    """EC-TXN-3 on Windows with the real installer; nothing in it is patched.

    Builds run through the installer's own gcc builder (MinGW, with the
    recipe's deterministic PE flags), and the pins are independent builds with
    the same documented recipe and output basename. Before the fault, the staged
    build must equal B's pin. The failed update then restores A's pair. The
    destination library is never displaced here (the restore returns only the
    metadata); handle release for the library is shown by
    ``test_restore_with_previous_pin_returns_both_files`` and
    ``test_restore_refused_while_another_process_has_the_library_loaded``.
    """
    shim_dir, real_gcc = _windows_shim(tmp_path)
    cache = tmp_path / "cache"
    repo_a = _repo(tmp_path / "repo-a", minor=1)
    repo_b = _repo(tmp_path / "repo-b", minor=2)
    digest_a = _windows_pin(real_gcc, repo_a, tmp_path / "pin-a")
    digest_b = _windows_pin(real_gcc, repo_b, tmp_path / "pin-b")
    assert digest_a != digest_b
    body = PROBE_EVENTS + INSTALL

    first = Child(body, [cache, 120.0], env=_windows_env(shim_dir, repo_a, digest_a))
    try:
        first.expect("ready")
        first.release()
        installed = first.finish()
    finally:
        first.close()
    _skip_on_policy_probe(first)
    assert installed["success"], installed
    assert installed["build"]["method"] == "gcc", installed
    assert installed["build"]["compiler"]["family"] == "gcc", installed
    pair_a = _pair(cache)
    assert pair_a[0] == digest_a

    with participants() as children:
        child = Child(
            body,
            [cache, 120.0],
            pauses=[COMMIT_PAUSE],
            env=_windows_env(shim_dir, repo_b, digest_b),
        )
        children.append(child)
        child.expect("ready")
        child.release()
        # A policy-blocked validation probe ends the install before the commit.
        # Earlier lock sections (staging) also report lock.before_acquire, so
        # wait for the commit section itself or for the end of the install.
        while True:
            reached = child.expect_any("lock.before_acquire", "done")
            if reached["event"] == "done" or (
                reached.get("primitive") == "cache_lock"
                and reached.get("section") == "commit"
            ):
                break
        _skip_on_policy_probe(child)
        assert reached["event"] == "lock.before_acquire", reached
        (staged,) = (cache / "builds" / ".txn-staging").glob("*/baml/libbaml.so")
        assert _sha(staged) == digest_b, "the Windows build is not reproducible"
        _damage_staged(cache, failure)
        child.release()
        done = child.finish()
    _skip_on_policy_probe(child)
    assert "metadata.after_replace" in [e["event"] for e in child.seen]
    assert not done["success"]
    assert "The previous installation was restored." in done["error"], done
    assert _pair(cache) == pair_a
    assert _rollback_points(cache) == []
    _require_restored_a(cache, digest_a, digest_b)
