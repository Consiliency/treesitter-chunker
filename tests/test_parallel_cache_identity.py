"""Parallel chunk-cache entry identity (treesitter-chunker#358).

Real parsers and process workers extract a checked-in fixture. Each cached
result must equal uncached extraction for the requested mode, whichever mode
warmed the cache first. Entries from a different runtime/grammar pairing or
language configuration must not be returned, a grammar or configuration
without a reliable identity must bypass the cache, and a caller-supplied cache
directory must confine writes.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import pickle
import shutil
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import pytest

import chunker._internal.cache as cache_module
import chunker.parser as parser_module
from chunker._internal.cache import ASTCache, chunk_cache_identity
from chunker._internal.file_utils import get_file_metadata
from chunker.core import chunk_file
from chunker.languages import language_config_registry
from chunker.languages.base import ChunkRule
from chunker.metadata import MetadataExtractorFactory
from chunker.parallel import ParallelChunker, chunk_files_parallel

pytestmark = pytest.mark.integration

FIXTURE = (
    Path(__file__).resolve().parent / "fixtures/boundary_ir/repos/python/app/service.py"
)
GO_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures/boundary_ir/repos/go/service.go"
)
MODES = {"core": False, "streaming": True}


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Point the default cache location at a disposable home."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


@pytest.fixture
def source_file(tmp_path):
    path = tmp_path / "src" / "service.py"
    path.parent.mkdir()
    shutil.copyfile(FIXTURE, path)
    return path


def _extract(path: Path, mode: str, **options) -> list[dict]:
    chunker = ParallelChunker(
        "python", num_workers=1, use_streaming=MODES[mode], **options
    )
    results = chunker.chunk_files_parallel([path])
    assert set(results) == {path}
    return [asdict(chunk) for chunk in results[path]]


@pytest.mark.parametrize(
    ("warm_mode", "requested_mode"),
    [("core", "streaming"), ("streaming", "core")],
)
def test_cached_result_matches_uncached_requested_mode(
    isolated_home, source_file, warm_mode, requested_mode
):
    uncached = {mode: _extract(source_file, mode, use_cache=False) for mode in MODES}
    # The fixture must make the modes distinguishable, or the test proves nothing.
    assert uncached["core"] and uncached["streaming"]
    assert uncached["core"] != uncached["streaming"]

    warmed = _extract(source_file, warm_mode)
    assert warmed == uncached[warm_mode]
    assert (isolated_home / ".cache/treesitter-chunker/ast_cache.db").is_file()

    assert _extract(source_file, requested_mode) == uncached[requested_mode]
    # Both entries remain valid for their own mode.
    assert _extract(source_file, warm_mode) == uncached[warm_mode]


def test_warm_entry_is_reused_for_its_own_mode(tmp_path, isolated_home, source_file):
    cache_dir = tmp_path / "cache"
    for mode in MODES:
        _extract(source_file, mode, cache_dir=cache_dir)
    cache = ASTCache(cache_dir=cache_dir)
    annotated = {}
    for mode in MODES:
        stored = cache.get_cached_chunks(source_file, "python", extraction=mode)
        assert stored is not None
        annotated[mode] = [
            replace(chunk, metadata={**chunk.metadata, "reused_entry": mode})
            for chunk in stored
        ]
        cache.cache_chunks(source_file, "python", annotated[mode], extraction=mode)

    for mode in MODES:
        assert _extract(source_file, mode, cache_dir=cache_dir) == [
            asdict(chunk) for chunk in annotated[mode]
        ]


@pytest.mark.parametrize(
    "distribution", ["treesitter-chunker", "tree-sitter", "tree-sitter-language-pack"]
)
def test_entry_from_other_runtime_pairing_is_not_returned(
    tmp_path, isolated_home, source_file, monkeypatch, distribution
):
    cache_dir = tmp_path / "cache"
    expected = _extract(source_file, "core", use_cache=False)
    real_version = cache_module._distribution_version
    with monkeypatch.context() as patched:
        patched.setattr(
            cache_module,
            "_distribution_version",
            lambda name: (
                "0.0.0+other-pairing" if name == distribution else real_version(name)
            ),
        )
        foreign = ASTCache(cache_dir=cache_dir)
        foreign.cache_chunks(
            source_file,
            "python",
            [
                replace(chunk, content="stale")
                for chunk in ParallelChunker(
                    "python", use_cache=False
                )._process_single_file(source_file)[1]
            ],
        )
        assert foreign.get_cached_chunks(source_file, "python") is not None

    assert (
        ASTCache(cache_dir=cache_dir).get_cached_chunks(source_file, "python") is None
    )
    assert _extract(source_file, "core", cache_dir=cache_dir) == expected


def test_entry_from_other_grammar_provenance_is_not_returned(
    tmp_path, isolated_home, source_file, monkeypatch
):
    cache_dir = tmp_path / "cache"
    expected = _extract(source_file, "core", use_cache=False)
    real_info = parser_module.get_language_info

    def custom_grammar_info(language):
        metadata = real_info(language)
        return replace(
            metadata,
            capabilities={
                **metadata.capabilities,
                "grammar_source": "custom:sha256:" + "0" * 64,
            },
        )

    with monkeypatch.context() as patched:
        patched.setattr(parser_module, "get_language_info", custom_grammar_info)
        custom_identity = chunk_cache_identity("python")
        ASTCache(cache_dir=cache_dir).cache_chunks(
            source_file,
            "python",
            [
                replace(chunk, content="stale")
                for chunk in ParallelChunker(
                    "python", use_cache=False
                )._process_single_file(source_file)[1]
            ],
        )

    assert custom_identity != chunk_cache_identity("python")
    assert (
        ASTCache(cache_dir=cache_dir).get_cached_chunks(source_file, "python") is None
    )
    assert _extract(source_file, "core", cache_dir=cache_dir) == expected


def test_caller_cache_dir_confines_writes(tmp_path, isolated_home, source_file):
    cache_dir = tmp_path / "private-cache"
    for streaming in MODES.values():
        results = chunk_files_parallel(
            [source_file],
            "python",
            num_workers=1,
            use_streaming=streaming,
            cache_dir=cache_dir,
        )
        assert results[source_file]

    assert (cache_dir / "ast_cache.db").is_file()
    assert sorted(path.name for path in cache_dir.iterdir()) == ["ast_cache.db"]
    assert list(isolated_home.rglob("*")) == []
    with closing(sqlite3.connect(cache_dir / "ast_cache.db")) as conn:
        rows = conn.execute(
            "SELECT file_path, COUNT(DISTINCT extraction_identity) FROM chunk_cache_v3 "
            "GROUP BY file_path"
        ).fetchall()
    assert rows == [(str(source_file), 2)]


def test_legacy_entries_are_ignored_and_left_intact(
    tmp_path, isolated_home, source_file
):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    metadata = get_file_metadata(source_file)
    with closing(sqlite3.connect(cache_dir / "ast_cache.db")) as conn:
        conn.execute(
            """CREATE TABLE file_cache (
                file_path TEXT NOT NULL, file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL, mtime REAL NOT NULL,
                language TEXT NOT NULL, chunks_data BLOB NOT NULL,
                data_checksum TEXT, cache_version TEXT DEFAULT '1.0',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (file_path, language)
            )"""
        )
        conn.execute(
            "INSERT INTO file_cache (file_path, file_hash, file_size, mtime, "
            "language, chunks_data, cache_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(source_file),
                metadata.hash,
                metadata.size,
                metadata.mtime,
                "python",
                pickle.dumps([]),
                "2.0",
            ),
        )
        conn.commit()

    expected = _extract(source_file, "core", use_cache=False)
    assert expected
    assert (
        ASTCache(cache_dir=cache_dir).get_cached_chunks(source_file, "python") is None
    )
    assert _extract(source_file, "core", cache_dir=cache_dir) == expected
    with closing(sqlite3.connect(cache_dir / "ast_cache.db")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM file_cache").fetchone() == (1,)


def test_unknown_extraction_mode_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unknown extraction mode"):
        chunk_cache_identity("python", "fast")
    cache = ASTCache(cache_dir=tmp_path / "cache")
    with pytest.raises(ValueError, match="Unknown extraction mode"):
        cache.cache_chunks(tmp_path / "missing.py", "python", [], extraction="fast")


@pytest.fixture
def python_ignores_functions():
    """Ignore Python function definitions in the shared registry, then restore."""
    config = language_config_registry.get("python")
    assert "function_definition" not in config.ignore_types

    def apply():
        config.add_ignore_type("function_definition")

    try:
        yield apply
    finally:
        config._ignore_types.discard("function_definition")


def test_changed_language_configuration_is_not_served_stale_chunks(
    tmp_path, source_file, python_ignores_functions
):
    cache = ASTCache(cache_dir=tmp_path / "cache")
    warm = chunk_file(source_file, "python")
    assert cache.cache_chunks(source_file, "python", warm)

    python_ignores_functions()
    fresh = chunk_file(source_file, "python")
    assert len(fresh) < len(warm)
    assert cache.get_cached_chunks(source_file, "python") is None
    assert cache.cache_chunks(source_file, "python", fresh)
    stored = cache.get_cached_chunks(source_file, "python")
    assert [asdict(chunk) for chunk in stored] == [asdict(chunk) for chunk in fresh]
    # The write replaced this file's core entry under the superseded identity.
    assert cache.get_cache_stats()["total_files"] == 1


@pytest.mark.skipif(
    mp.get_start_method() != "fork",
    reason="workers see a parent registry change only when forked",
)
def test_parallel_workers_key_on_changed_configuration(
    tmp_path, source_file, python_ignores_functions
):
    cache_dir = tmp_path / "cache"
    warmed = _extract(source_file, "core", cache_dir=cache_dir)
    python_ignores_functions()
    fresh = _extract(source_file, "core", use_cache=False)
    assert len(fresh) < len(warmed)
    assert _extract(source_file, "core", cache_dir=cache_dir) == fresh


class _OutsideExtractor(MetadataExtractorFactory._extractors["python"]):
    """An extractor class defined outside the chunker package."""


@pytest.mark.parametrize("unidentified", ["function_state", "outside_extractor"])
def test_unfingerprintable_configuration_bypasses_cache(
    tmp_path, source_file, monkeypatch, unidentified
):
    if unidentified == "function_state":
        config = language_config_registry.get("python")
        monkeypatch.setattr(config, "_custom_hook", lambda node: False, raising=False)
    else:
        monkeypatch.setitem(
            MetadataExtractorFactory._extractors, "python", _OutsideExtractor
        )
    assert chunk_cache_identity("python") is None

    cache = ASTCache(cache_dir=tmp_path / "cache")
    chunks = chunk_file(source_file, "python")
    assert cache.cache_chunks(source_file, "python", chunks) is False
    assert cache.get_cached_chunks(source_file, "python") is None
    assert cache.get_cache_stats()["total_files"] == 0


def test_grammar_without_identity_is_never_served_from_cache(tmp_path):
    # The language pack resolves its grammar cache from the real home, so this
    # test confines only the chunk cache (cache_dir) to tmp_path.
    path = tmp_path / "src" / "service.go"
    path.parent.mkdir()
    shutil.copyfile(GO_FIXTURE, path)
    # The registry records no provenance for Go, so it has no identity.
    assert chunk_cache_identity("go") is None

    fresh = ParallelChunker("go", num_workers=1, use_cache=False).chunk_files_parallel(
        [path]
    )[path]
    assert fresh
    cache_dir = tmp_path / "cache"
    cache = ASTCache(cache_dir=cache_dir)
    stale = [replace(chunk, content="stale") for chunk in fresh]
    assert cache.cache_chunks(path, "go", stale) is False
    for _ in range(2):
        served = ParallelChunker(
            "go", num_workers=1, cache_dir=cache_dir
        ).chunk_files_parallel([path])[path]
        assert [asdict(chunk) for chunk in served] == [asdict(chunk) for chunk in fresh]
    assert cache.get_cached_chunks(path, "go") is None
    assert cache.get_cache_stats()["total_files"] == 0
    # A grammar that cannot be loaded is also bypassed rather than raising.
    assert cache.cache_chunks(path, "no_such_language", fresh) is False


@dataclass(slots=True)
class _SlottedState:
    """Rule metadata whose attributes ``vars()`` cannot read."""

    value: int = 1


def _nested(depth: int) -> list:
    value: list = []
    for _ in range(depth):
        value = [value]
    return value


@pytest.mark.parametrize("state", ["cycle", "slotted", "deep"])
def test_unreadable_configuration_state_bypasses_cache_without_crashing(
    tmp_path, source_file, caplog, state
):
    config = language_config_registry.get("python")
    # The rule's node type never occurs, so chunk output is unchanged.
    rule = ChunkRule(node_types={"no_such_node_type"})
    if state == "cycle":
        rule.metadata["owner"] = config
    elif state == "slotted":
        rule.metadata["state"] = _SlottedState()
    else:
        rule.metadata["state"] = _nested(5000)
    uncached = [asdict(chunk) for chunk in chunk_file(source_file, "python")]
    config.add_chunk_rule(rule)
    try:
        with caplog.at_level(logging.DEBUG, logger="chunker._internal.cache"):
            assert chunk_cache_identity("python") is None
        if state == "cycle":
            assert "cyclic configuration state" in caplog.text
        cache_dir = tmp_path / "cache"
        chunker = ParallelChunker("python", num_workers=1, cache_dir=cache_dir)
        for _ in range(2):
            _, served = chunker._process_single_file(source_file)
            assert [asdict(chunk) for chunk in served] == uncached
        cache = ASTCache(cache_dir=cache_dir)
        assert cache.get_cached_chunks(source_file, "python") is None
        assert cache.get_cache_stats()["total_files"] == 0
    finally:
        config._chunk_rules.remove(rule)
    assert chunk_cache_identity("python") is not None


_PRE_RELEASE_TABLE_SQL = """CREATE TABLE chunk_cache (
    file_path TEXT NOT NULL, language TEXT NOT NULL,
    extraction_identity TEXT NOT NULL, file_hash TEXT NOT NULL,
    file_size INTEGER NOT NULL, mtime REAL NOT NULL,
    chunks_data BLOB NOT NULL, data_checksum TEXT NOT NULL,
    cache_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (file_path, language, extraction_identity)
)"""


def _seed_pre_release_table(cache_dir: Path) -> None:
    """Write the chunk_cache layout of an unreleased build, with one row."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(cache_dir / "ast_cache.db")) as conn:
        conn.execute(_PRE_RELEASE_TABLE_SQL)
        conn.execute("CREATE INDEX idx_chunk_cache_hash ON chunk_cache(file_hash)")
        conn.execute(
            "INSERT INTO chunk_cache VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "CURRENT_TIMESTAMP)",
            ("old.py", "python", "0" * 64, "0" * 64, 1, 0.0, b"x", "0" * 64, "3.0"),
        )
        conn.commit()


def _pre_release_rows(cache_dir: Path) -> int:
    with closing(sqlite3.connect(cache_dir / "ast_cache.db")) as conn:
        return conn.execute("SELECT COUNT(*) FROM chunk_cache").fetchone()[0]


def test_pre_release_table_is_ignored_and_left_intact(tmp_path, source_file):
    cache_dir = tmp_path / "cache"
    _seed_pre_release_table(cache_dir)

    expected = _extract(source_file, "core", use_cache=False)
    assert _extract(source_file, "core", cache_dir=cache_dir) == expected
    assert _extract(source_file, "core", cache_dir=cache_dir) == expected
    assert ASTCache(cache_dir=cache_dir).get_cache_stats()["total_files"] == 1
    assert _pre_release_rows(cache_dir) == 1


def _concurrent_cache_user(cache_dir, source, barrier, results, rounds):
    """Open, write and re-read the shared cache in a separate process."""
    from chunker._internal.cache import ASTCache as ChildCache
    from chunker.core import chunk_file as child_chunk_file

    path = Path(source)
    expected = [asdict(chunk) for chunk in child_chunk_file(path, "python")]
    report = {"source": source, "stored": False, "served": 0, "errors": []}
    barrier.wait(timeout=120)
    try:
        report["stored"] = ChildCache(cache_dir=Path(cache_dir)).cache_chunks(
            path, "python", child_chunk_file(path, "python")
        )
        for _ in range(rounds):
            # Each round opens the database again, racing other openers.
            served = ChildCache(cache_dir=Path(cache_dir)).get_cached_chunks(
                path, "python"
            )
            if served is not None and [asdict(c) for c in served] == expected:
                report["served"] += 1
    except Exception as error:  # reported to the parent, which asserts on it
        report["errors"].append(repr(error))
    results.put(report)


def test_opening_the_cache_only_creates_and_never_drops(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    _seed_pre_release_table(cache_dir)
    with closing(sqlite3.connect(cache_dir / "ast_cache.db")) as conn:
        conn.execute(
            "CREATE TABLE file_cache (file_path TEXT NOT NULL, "
            "language TEXT NOT NULL, chunks_data BLOB NOT NULL, "
            "PRIMARY KEY (file_path, language))"
        )
        conn.execute("INSERT INTO file_cache VALUES ('old.py', 'python', x'00')")
        conn.commit()

    statements: list[str] = []
    real_connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        # Spy only: the real SQLite connection executes every statement.
        connection = real_connect(*args, **kwargs)
        connection.set_trace_callback(
            lambda sql: statements.append(" ".join(sql.split()))
        )
        return connection

    monkeypatch.setattr(sqlite3, "connect", traced_connect)
    for _ in range(2):  # a fresh database, then one that already has the table
        statements.clear()
        ASTCache(cache_dir=cache_dir)
        assert len(statements) == 2, statements
        assert statements[0].startswith("CREATE TABLE IF NOT EXISTS chunk_cache_v3 (")
        assert statements[1] == (
            "CREATE INDEX IF NOT EXISTS idx_chunk_cache_v3_hash "
            "ON chunk_cache_v3(file_hash)"
        )
        for statement in statements:
            assert not statement.upper().startswith(("DROP", "ALTER", "DELETE"))
    monkeypatch.undo()

    with closing(sqlite3.connect(cache_dir / "ast_cache.db")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM chunk_cache").fetchone() == (1,)
        assert conn.execute("SELECT COUNT(*) FROM file_cache").fetchone() == (1,)
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
    assert {"idx_chunk_cache_hash", "idx_chunk_cache_v3_hash"} <= indexes


def test_concurrent_processes_share_the_cache_without_losing_entries(tmp_path):
    """Smoke test: real spawned processes open, write and re-read together."""
    workers, rounds = 4, 15
    cache_dir = tmp_path / "cache"
    _seed_pre_release_table(cache_dir)
    sources = []
    for index in range(workers):
        path = tmp_path / f"src{index}" / "service.py"
        path.parent.mkdir()
        shutil.copyfile(FIXTURE, path)
        sources.append(str(path))

    context = mp.get_context("spawn")
    barrier = context.Barrier(workers)
    results = context.Queue()
    processes = [
        context.Process(
            target=_concurrent_cache_user,
            args=(str(cache_dir), source, barrier, results, rounds),
        )
        for source in sources
    ]
    for process in processes:
        process.start()
    try:
        reports = [results.get(timeout=300) for _ in processes]
    finally:
        for process in processes:
            process.join(timeout=60)
            if process.is_alive():
                process.terminate()
                process.join()
    assert [process.exitcode for process in processes] == [0] * workers

    for report in reports:
        assert report["errors"] == [], report
        assert report["stored"] is True, report
        assert report["served"] == rounds, report
    # A later open (here, in this process) must not discard what they wrote.
    cache = ASTCache(cache_dir=cache_dir)
    assert cache.get_cache_stats()["total_files"] == workers
    for source in sources:
        assert cache.get_cached_chunks(Path(source), "python") is not None
    assert _pre_release_rows(cache_dir) == 1
