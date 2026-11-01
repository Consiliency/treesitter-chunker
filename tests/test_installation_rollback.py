"""Installation commit and rollback (treesitter-chunker#363).

Cache transaction contract, Primitive 3. Artifacts are real compiled BAML
revisions (0.1.0 and 0.2.0); every admission is a real
``probe_native_grammar`` run through IF-0-HOTFIX-1 ``publish_native_grammar``.
Pins come from the test, as the caller (runner decision D-a; production pins
arrive with ADMIT SL-core-2).

Terms used below:

- A *False-returning failure* is ``publish_native_grammar`` returning an
  unsupported ``NativeProbeResult`` (for example, the staged bytes do not match
  the pin), as opposed to raising ``OSError``.
- *Handle release* means the installing process holds no handle on the
  destination library (it validates through the probe's private snapshot), so
  Windows lets ``os.replace`` swap it during restore.
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

from chunker._internal.user_grammar_tools import publish_native_grammar
from chunker.grammar_management import _transactions
from tests.test_cache_entry_transactions import (
    SHIM,
    _age,
    _env,
    _install,
    _installer,
)
from tests.test_compiled_grammar_analysis_contract import SOURCE, _compile_probe_fixture
from tests.test_user_grammar_publication import LOAD
from tests.txn_barrier import (
    ROOT,
    SAFETY_TIMEOUT,
    Child,
    exit_at,
    pause_at,
    participants,
    run_mounting,
)

FIXTURE = ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"
POSIX_INSTALL = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("make") is None,
    reason="the installer path uses the POSIX git shim and make",
)


@pytest.fixture
def shim(tmp_path: Path) -> Path:
    directory = tmp_path / "shim"
    directory.mkdir()
    git = directory / "git"
    git.write_text(SHIM.format(python=sys.executable), encoding="utf-8")
    git.chmod(0o755)
    return directory


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


def _prebuilt_repo(base: Path, library: Path) -> Path:
    """A fixture repository whose ``make`` build yields exactly ``library``."""
    base.mkdir(parents=True)
    (base / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
    shutil.copy2(library, base / "libbaml.so")
    _age(base)
    return base


def _pair(cache: Path) -> tuple[str | None, bytes | None]:
    metadata = cache / "grammars" / "baml_install_info.json"
    return (
        _sha(cache / "grammars" / "libbaml.so"),
        metadata.read_bytes() if metadata.is_file() else None,
    )


def _parse_version(library: Path) -> list[int]:
    loaded = subprocess.run(
        [sys.executable, "-I", "-c", LOAD, str(ROOT), str(library), str(FIXTURE)],
        capture_output=True,
        text=True,
        timeout=SAFETY_TIMEOUT,
        check=True,
    )
    report = json.loads(loaded.stdout)
    assert report["ok"]
    return report["version"]


def _rollback_points(cache: Path) -> list[str]:
    area = cache / ".txn" / "rollback"
    return sorted(p.name for p in area.iterdir() if p.name != ".txn-keep")


# --- failed update restores the pair -------------------------------------------


@POSIX_INSTALL
@pytest.mark.parametrize("failure", ["not_admitted", "raises"])
def test_failed_update_restores_previous_pair(tmp_path, shim, revisions, failure):
    """A real install of A, then a deterministic failed update to B.

    The fault is injected at the commit section's ``lock.before_acquire``:
    a non-participant corrupts (``not_admitted``: a False-returning failure)
    or removes (``raises``: ``OSError``) the staged artifact. The metadata
    already published is restored, the pair equals A's, and a fresh process
    parses A's revision. Mutations ``omit_restore`` and
    ``rollback_removes_metadata`` (today's behavior) leave a different pair.
    """
    rev_a, rev_b = revisions
    cache = tmp_path / "cache"
    repo_a = _prebuilt_repo(tmp_path / "repo-a", rev_a)
    repo_b = _prebuilt_repo(tmp_path / "repo-b", rev_b)
    assert _install(cache, _env(shim, repo_a))["success"]
    pair_a = _pair(cache)
    assert pair_a[0] == _sha(rev_a)
    assert json.loads(pair_a[1])["artifact_sha256"] == _sha(rev_a)

    # B unpinned: refused before the commit section; nothing changes.
    unpinned = Child(
        "from pathlib import Path\n"
        "from chunker.grammar_management.core import GrammarInstaller\n"
        "installer = GrammarInstaller(cache_dir=Path(ARGS[0]), trusted_artifacts={})\n"
        "emit('ready'); wait()\n"
        "ok, error, _ = installer.install_grammar('baml', "
        "'https://github.com/example/tree-sitter-baml')\n"
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
        child = _installer(
            cache,
            _env(shim, repo_b),
            pauses=[
                pause_at(
                    "lock.before_acquire", primitive="cache_lock", section="commit"
                )
            ],
        )
        children.append(child)
        child.expect("ready")
        child.release()
        child.expect("lock.before_acquire", primitive="cache_lock", section="commit")
        (staged,) = (cache / "builds" / ".txn-staging").glob("*/baml/libbaml.so")
        if failure == "not_admitted":
            # A new inode: the installer's validator still maps the old one.
            damaged = staged.with_name("damaged")
            damaged.write_bytes(staged.read_bytes()[:4096])
            damaged.replace(staged)
        else:
            staged.unlink()
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
    assert _parse_version(cache / "grammars" / "libbaml.so") == [0, 1, 0]


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
            "source_url": "https://github.com/example/tree-sitter-baml",
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
    assert _parse_version(point.artifact) == [0, 1, 0]


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


# --- serialization and crash ----------------------------------------------------

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
from chunker.grammar_management.core import GrammarInstaller
installer = GrammarInstaller(cache_dir=Path(ARGS[0]))
emit("ready")
wait()
emit("done", result=list(installer.remove_grammar("baml")))
"""


def _update_paused_at_metadata(cache, shim, repo_b):
    child = _installer(
        cache,
        _env(shim, repo_b),
        pauses=[pause_at("commit.after_metadata", section="commit")],
    )
    child.expect("ready")
    child.release()
    child.expect("commit.after_metadata", section="commit")
    return child


@POSIX_INSTALL
def test_reader_waits_for_the_whole_commit(tmp_path, shim, revisions):
    """(a) Paused after the metadata publication, the commit still holds the lock.

    The pause point ``commit.after_metadata`` (Claude N1) fires after the
    metadata's own nested hold is released. A reader contends and then sees
    a consistent pair. Mutation ``commit_without_lock`` lets it read B's
    metadata beside A's artifact.
    """
    rev_a, rev_b = revisions
    cache = tmp_path / "cache"
    assert _install(cache, _env(shim, _prebuilt_repo(tmp_path / "a", rev_a)))["success"]
    with participants() as children:
        reader = Child(READER, [cache])
        children.append(reader)
        reader.expect("ready")
        installer = _update_paused_at_metadata(
            cache, shim, _prebuilt_repo(tmp_path / "b", rev_b)
        )
        children.append(installer)
        reader.release()
        first = reader.expect_any("lock.contended", "lock.acquired")
        assert (first["event"], first["primitive"]) == ("lock.contended", "cache_lock")
        installer.release()
        assert installer.finish()["success"]
        read = reader.finish()
    assert read["recorded"] == read["actual"] == _sha(rev_b)


@POSIX_INSTALL
def test_crash_after_metadata_is_detectable_and_recoverable(
    tmp_path, shim, revisions, caplog
):
    """(b) A crash after the metadata replace leaves ``Mi`` beside ``Ap``.

    The mismatch is reported before the next capture (Claude N9), and the
    operator procedure on ``rollback.json`` restores A's pair.
    """
    rev_a, rev_b = revisions
    cache = tmp_path / "cache"
    assert _install(cache, _env(shim, _prebuilt_repo(tmp_path / "a", rev_a)))["success"]
    pair_a = _pair(cache)
    child = _installer(
        cache,
        _env(shim, _prebuilt_repo(tmp_path / "b", rev_b)),
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
    assert json.loads(metadata)["artifact_sha256"] == _sha(rev_b) != artifact
    (point,) = _rollback_points(cache)
    manifest_path = cache / ".txn" / "rollback" / point / "rollback.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    with caplog.at_level(logging.WARNING):
        probe = _transactions.create_rollback_point(
            cache,
            language="baml",
            artifact=cache / "grammars" / "libbaml.so",
            metadata_document={"install_path": str(cache / "grammars" / "libbaml.so")},
            artifact_sha256=_sha(rev_b),
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


@POSIX_INSTALL
def test_removal_during_a_paused_commit_waits_and_stays_removed(
    tmp_path, shim, revisions
):
    """(d) ``remove_grammar`` contends with the commit; nothing comes back."""
    rev_a, rev_b = revisions
    cache = tmp_path / "cache"
    assert _install(cache, _env(shim, _prebuilt_repo(tmp_path / "a", rev_a)))["success"]
    with participants() as children:
        remover = Child(REMOVER, [cache])
        children.append(remover)
        remover.expect("ready")
        installer = _update_paused_at_metadata(
            cache, shim, _prebuilt_repo(tmp_path / "b", rev_b)
        )
        children.append(installer)
        remover.release()
        remover.expect("lock.contended")
        installer.release()
        assert installer.finish()["success"]
        assert remover.finish()["result"] == [True, None]
    assert _pair(cache) == (None, None)
    assert _rollback_points(cache) == []


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
