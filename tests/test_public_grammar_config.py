"""Contract tests for exported grammar configuration and directories."""

import json
import os
import shutil
import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from chunker import get_parser
from chunker.grammar_management.config import (
    CacheManager,
    DirectoryManager,
    UserConfig,
    config_cli,
)


FIXTURE = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"


def test_config_reloads_nested_cache_and_directory_settings(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    tree = parser.parse(source)
    assert tree.root_node.type == "module"
    assert not tree.root_node.has_error

    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    config_path = tmp_path / "settings" / "config.json"
    grammar_root = tmp_path / "grammar-state"
    config = UserConfig(config_path)
    config.set("directories.base_dir", str(grammar_root))
    config.set("cache.max_size_mb", 256)
    config.set("cache.auto_cleanup", False)

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["directories"]["base_dir"] == str(grammar_root)
    assert saved["cache"]["max_size_mb"] == 256
    assert saved["cache"]["auto_cleanup"] is False

    reloaded = UserConfig(config_path)
    assert reloaded.get("directories.base_dir") == str(grammar_root)
    assert reloaded.get("cache.max_size_mb") == 256
    assert reloaded.get("cache.auto_cleanup") is False

    directories = DirectoryManager(reloaded).create_structure()
    assert directories["grammars"] == grammar_root / "grammars"
    assert directories["cache"] == grammar_root / "cache"
    copied_fixture = directories["grammars"] / "service.py"
    shutil.copyfile(FIXTURE, copied_fixture)
    copied_tree = parser.parse(copied_fixture.read_bytes())
    assert copied_tree.root_node.type == "module"
    assert not copied_tree.root_node.has_error
    assert not isolated_home.exists()


def test_config_has_distinguishes_present_null_and_missing_keys(
    tmp_path: Path, monkeypatch
) -> None:
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error
    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    config_path = tmp_path / "settings" / "config.json"
    config = UserConfig(config_path)
    assert config.has("cache.max_size_mb")
    assert not config.has("cache.not_here")
    assert not config.has("missing.section")

    config.set("cache.note", None)
    assert config.has("cache.note")
    assert UserConfig(config_path).has("cache.note")
    config.delete("cache.note")
    assert not config.has("cache.note")
    assert not UserConfig(config_path).has("cache.note")
    assert not isolated_home.exists()


@pytest.mark.parametrize("invalid_file", [False, True])
def test_config_reset_restores_nested_defaults_after_edits(
    tmp_path: Path, monkeypatch, invalid_file: bool
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error
    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    config_path = tmp_path / "settings" / "config.json"
    if invalid_file:
        config_path.parent.mkdir()
        config_path.write_text("{", encoding="utf-8")
    config = UserConfig(config_path)
    default_size = config.get("cache.max_size_mb")
    default_root = config.get("directories.base_dir")
    grammar_root = tmp_path / "grammar-state"
    config.set("cache.max_size_mb", default_size + 1)
    config.set("cache.note", None)
    config.set("directories.base_dir", str(grammar_root))
    grammar_dir = DirectoryManager(config).create_structure()["grammars"]
    retained = grammar_dir / "service.py"
    retained.write_bytes(source)

    config.reset_to_defaults()
    assert config.get("cache.max_size_mb") == default_size
    assert config.get("directories.base_dir") == default_root
    assert not config.has("cache.note")
    reloaded = UserConfig(config_path)
    assert reloaded.get("cache.max_size_mb") == default_size
    assert reloaded.get("directories.base_dir") == default_root
    assert not reloaded.has("cache.note")
    assert not parser.parse(retained.read_bytes()).root_node.has_error
    assert not isolated_home.exists()


@pytest.mark.parametrize("partial_source", ["load", "import"])
def test_config_partial_merge_does_not_alias_mutable_defaults(
    tmp_path: Path, monkeypatch, partial_source: str
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error
    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    config_path = tmp_path / "settings" / "config.json"
    partial = {
        section: {} for section in ("cache", "directories", "grammar", "logging")
    }
    partial_path = tmp_path / "partial.json"
    partial_path.write_text(json.dumps(partial), encoding="utf-8")
    if partial_source == "load":
        config_path.parent.mkdir()
        config_path.write_text(json.dumps(partial), encoding="utf-8")
    config = UserConfig(config_path)
    if partial_source == "import":
        config.import_config(partial_path, merge=True)

    grammar_root = tmp_path / "grammar-state"
    config.set("directories.base_dir", str(grammar_root))
    retained = DirectoryManager(config).create_structure()["grammars"] / "service.py"
    retained.write_bytes(source)
    default_sources = list(config.get("grammar.preferred_sources"))
    config.get("grammar.preferred_sources").append("https://example.invalid/custom")

    config.reset_to_defaults()
    assert config.get("grammar.preferred_sources") == default_sources
    assert UserConfig(config_path).get("grammar.preferred_sources") == default_sources
    assert (
        json.loads(config_path.read_text(encoding="utf-8"))["grammar"][
            "preferred_sources"
        ]
        == default_sources
    )
    assert not parser.parse(retained.read_bytes()).root_node.has_error
    assert not isolated_home.exists()


def test_config_import_merge_preserves_omitted_settings_and_replace_drops_them(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error
    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    config_path = tmp_path / "settings" / "config.json"
    grammar_root = tmp_path / "grammar-state"
    config = UserConfig(config_path)
    config.set("directories.base_dir", str(grammar_root))
    config.set("cache.max_size_mb", 64)
    config.set("cache.auto_cleanup", False)
    retained = DirectoryManager(config).create_structure()["grammars"] / "service.py"
    retained.write_bytes(source)

    import_path = tmp_path / "partial.json"
    imported = {
        "cache": {"max_age_days": 45},
        "directories": {},
        "grammar": {},
        "logging": {"level": "WARNING"},
    }
    import_path.write_text(json.dumps(imported), encoding="utf-8")
    config.import_config(import_path, merge=True)
    assert config.get("cache.max_size_mb") == 64
    assert config.get("cache.auto_cleanup") is False
    assert config.get("cache.max_age_days") == 45
    assert config.get("logging.level") == "WARNING"
    assert config.get("directories.base_dir") == str(grammar_root)
    reloaded = UserConfig(config_path)
    assert reloaded.get("cache.max_size_mb") == 64
    assert reloaded.get("cache.max_age_days") == 45
    assert reloaded.get("directories.base_dir") == str(grammar_root)

    config.import_config(import_path, merge=False)
    assert not config.has("cache.max_size_mb")
    assert json.loads(config_path.read_text(encoding="utf-8"))["cache"] == {
        "max_age_days": 45
    }
    assert retained.read_bytes() == source
    assert not parser.parse(retained.read_bytes()).root_node.has_error
    assert not isolated_home.exists()


def test_public_config_export_writes_live_settings_to_requested_nested_path(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error
    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    config = UserConfig()
    grammar_root = tmp_path / "grammar-state"
    config.set("directories.base_dir", str(grammar_root))
    config.set("cache.max_size_mb", 64)
    config.set("cache.auto_cleanup", False)
    retained = DirectoryManager(config).create_structure()["grammars"] / "service.py"
    retained.write_bytes(source)
    active_bytes = config.config_path.read_bytes()

    export_path = tmp_path / "reports" / "portable" / "config.json"
    result = CliRunner().invoke(config_cli, ["export", str(export_path)])
    assert result.exit_code == 0, result.output
    assert str(export_path) in result.output
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert exported["directories"]["base_dir"] == str(grammar_root)
    assert exported["cache"]["max_size_mb"] == 64
    assert exported["cache"]["auto_cleanup"] is False
    exported_config = UserConfig(export_path)
    assert exported_config.get("directories.base_dir") == str(grammar_root)
    assert exported_config.get("cache.max_size_mb") == 64

    failed = CliRunner().invoke(config_cli, ["export", str(export_path.parent)])
    assert failed.exit_code == 1
    assert "Failed to export configuration" in failed.output
    assert "Configuration exported to" not in failed.output
    assert json.loads(export_path.read_text(encoding="utf-8")) == exported
    assert config.config_path.read_bytes() == active_bytes
    assert retained.read_bytes() == source
    assert not parser.parse(retained.read_bytes()).root_node.has_error


def test_public_config_import_merges_by_default_and_replaces_on_request(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error
    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    config = UserConfig()
    grammar_root = tmp_path / "grammar-state"
    config.set("directories.base_dir", str(grammar_root))
    config.set("cache.max_size_mb", 64)
    retained = DirectoryManager(config).create_structure()["grammars"] / "service.py"
    retained.write_bytes(source)

    imported = {
        "cache": {"max_age_days": 45},
        "directories": {},
        "grammar": {},
        "logging": {"level": "WARNING"},
    }
    import_path = tmp_path / "partial.json"
    import_path.write_text(json.dumps(imported), encoding="utf-8")
    runner = CliRunner()

    merged = runner.invoke(config_cli, ["import-config", str(import_path)], input="y\n")
    assert merged.exit_code == 0, merged.output
    assert "Configuration imported successfully" in merged.output
    active = UserConfig(config.config_path)
    assert active.get("cache.max_size_mb") == 64
    assert active.get("cache.max_age_days") == 45
    assert active.get("directories.base_dir") == str(grammar_root)
    assert active.get("logging.level") == "WARNING"

    replaced = runner.invoke(
        config_cli, ["import-config", "--replace", str(import_path)], input="y\n"
    )
    assert replaced.exit_code == 0, replaced.output
    assert "Configuration imported successfully" in replaced.output
    saved = json.loads(config.config_path.read_text(encoding="utf-8"))
    assert saved["cache"] == {"max_age_days": 45}
    assert saved["directories"] == {}
    assert saved["logging"]["level"] == "WARNING"
    assert retained.read_bytes() == source
    assert not parser.parse(retained.read_bytes()).root_node.has_error


def test_public_config_set_get_preserves_typed_values_and_grammar_directory(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error
    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    grammar_root = tmp_path / "grammar-state"
    runner = CliRunner()
    for key, value in (
        ("directories.base_dir", str(grammar_root)),
        ("cache.max_size_mb", "64"),
        ("cache.auto_cleanup", "false"),
        ("logging.level", "WARNING"),
    ):
        result = runner.invoke(config_cli, ["set", key, value])
        assert result.exit_code == 0, result.output
        assert f"Configuration updated: {key}" in result.output

    config = UserConfig()
    saved = json.loads(config.config_path.read_text(encoding="utf-8"))
    assert saved["directories"]["base_dir"] == str(grammar_root)
    assert saved["cache"]["max_size_mb"] == 64
    assert saved["cache"]["auto_cleanup"] is False
    assert saved["logging"]["level"] == "WARNING"
    retained = DirectoryManager(config).create_structure()["grammars"] / "service.py"
    assert retained.parent == grammar_root / "grammars"
    retained.write_bytes(source)

    for key, displayed in (
        ("directories.base_dir", str(grammar_root)),
        ("cache.max_size_mb", "64"),
        ("cache.auto_cleanup", "False"),
        ("logging.level", "WARNING"),
    ):
        result = runner.invoke(config_cli, ["get", key])
        assert result.exit_code == 0, result.output
        assert f"{key}: {displayed}" in result.output
    assert retained.read_bytes() == source
    assert not parser.parse(retained.read_bytes()).root_node.has_error


def test_config_backup_restores_saved_settings_and_keeps_pre_restore_copy(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error

    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))
    config_path = tmp_path / "settings" / "config.json"
    grammar_root = tmp_path / "grammar-state"
    changed_root = tmp_path / "changed-state"
    config = UserConfig(config_path)
    config.set("directories.base_dir", str(grammar_root))
    config.set("cache.max_size_mb", 64)
    grammar_dir = DirectoryManager(config).create_structure()["grammars"]
    retained = grammar_dir / "service.py"
    retained.write_bytes(source)

    saved = config.backup("known")
    assert saved == config_path.parent / "backups" / "known.json"
    assert json.loads(saved.read_text(encoding="utf-8"))["cache"]["max_size_mb"] == 64

    config.set("directories.base_dir", str(changed_root))
    config.set("cache.max_size_mb", 128)
    config.restore(saved)
    assert config.get("directories.base_dir") == str(grammar_root)
    assert config.get("cache.max_size_mb") == 64
    reloaded = UserConfig(config_path)
    assert reloaded.get("directories.base_dir") == str(grammar_root)
    assert reloaded.get("cache.max_size_mb") == 64

    pre_restore = json.loads(
        (config_path.parent / "backups" / "pre_restore_backup.json").read_text(
            encoding="utf-8"
        )
    )
    assert pre_restore["directories"]["base_dir"] == str(changed_root)
    assert pre_restore["cache"]["max_size_mb"] == 128
    with pytest.raises(FileNotFoundError):
        config.restore(tmp_path / "missing.json")
    assert UserConfig(config_path).get("cache.max_size_mb") == 64
    assert not parser.parse(retained.read_bytes()).root_node.has_error
    assert not isolated_home.exists()


def test_config_backup_cleanup_keeps_newest_json_backups_and_grammar(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error

    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))
    config_path = tmp_path / "settings" / "config.json"
    grammar_root = tmp_path / "grammar-state"
    config = UserConfig(config_path)
    config.set("directories.base_dir", str(grammar_root))
    grammar_dir = DirectoryManager(config).create_structure()["grammars"]
    retained = grammar_dir / "service.py"
    retained.write_bytes(source)

    backups = []
    for index, size in enumerate((64, 128, 256)):
        config.set("cache.max_size_mb", size)
        backup = config.backup(f"version-{index}")
        os.utime(backup, (1_700_000_000 + index * 100, 1_700_000_000 + index * 100))
        backups.append(backup)
    neighbor = backups[0].parent / "notes.txt"
    neighbor.write_text("keep", encoding="utf-8")
    os.utime(neighbor, (1_700_000_400, 1_700_000_400))

    config.cleanup_old_backups(max_backups=2)
    assert not backups[0].exists()
    assert [
        json.loads(backup.read_text(encoding="utf-8"))["cache"]["max_size_mb"]
        for backup in backups[1:]
    ] == [128, 256]
    assert neighbor.read_text(encoding="utf-8") == "keep"
    assert config.get("cache.max_size_mb") == 256
    assert UserConfig(config_path).get("cache.max_size_mb") == 256
    assert retained.read_bytes() == source
    assert not parser.parse(retained.read_bytes()).root_node.has_error

    config.cleanup_old_backups(max_backups=2)
    assert [backup.name for backup in backups[1:] if backup.exists()] == [
        "version-1.json",
        "version-2.json",
    ]
    assert not isolated_home.exists()


def test_directory_usage_counts_parseable_nested_files_without_creating_missing_dirs(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error

    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))
    config = UserConfig(tmp_path / "settings" / "config.json")
    root = tmp_path / "grammar-state"
    config.set("directories.base_dir", str(root))
    directories = DirectoryManager(config)

    absent = directories.get_disk_usage()
    assert set(absent) == {"base", "grammars", "cache", "logs", "backups", "temp"}
    assert all(
        not entry["exists"] and entry["file_count"] == 0 for entry in absent.values()
    )
    assert not root.exists()

    structure = directories.create_structure()
    grammar = structure["grammars"] / "service.py"
    cached = structure["cache_downloads"] / "nested" / "service.py"
    cached.parent.mkdir()
    for path, size in ((grammar, 128 * 1024), (cached, 256 * 1024)):
        path.write_bytes(source + b"\n" + b" " * (size - len(source) - 1))
        assert not parser.parse(path.read_bytes()).root_node.has_error

    usage = directories.get_disk_usage()
    assert usage["grammars"] == {
        "size_bytes": 128 * 1024,
        "size_mb": 0.12,
        "file_count": 1,
        "path": str(structure["grammars"]),
        "exists": True,
    }
    assert usage["cache"] == {
        "size_bytes": 256 * 1024,
        "size_mb": 0.25,
        "file_count": 1,
        "path": str(structure["cache"]),
        "exists": True,
    }
    assert usage["base"]["size_bytes"] == 384 * 1024
    assert usage["base"]["size_mb"] == 0.38
    assert usage["base"]["file_count"] == 2
    assert all(usage[key]["file_count"] == 0 for key in ("logs", "backups", "temp"))
    assert not isolated_home.exists()


def test_empty_directory_cleanup_keeps_managed_roots_and_parseable_build(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error

    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))
    config = UserConfig(tmp_path / "settings" / "config.json")
    config.set("directories.base_dir", str(tmp_path / "grammar-state"))
    manager = DirectoryManager(config)
    assert manager.cleanup_empty_directories() == 0
    directories = manager.create_structure()

    empty_grammar = directories["grammars"] / "unused"
    empty_download = directories["cache_downloads"] / "unused"
    retained_build = directories["cache_builds"] / "keep" / "service.py"
    for empty in (empty_grammar, empty_download):
        empty.mkdir()
    retained_build.parent.mkdir()
    retained_build.write_bytes(source)

    assert manager.cleanup_empty_directories() == 2
    assert not empty_grammar.exists()
    assert not empty_download.exists()
    assert directories["cache_downloads"].is_dir()
    assert directories["cache_builds"].is_dir()
    assert manager.cleanup_empty_directories() == 0
    assert directories["cache_downloads"].is_dir()
    assert retained_build.exists()
    assert not parser.parse(retained_build.read_bytes()).root_node.has_error
    assert not isolated_home.exists()


def test_cache_cleanup_removes_stale_grammar_files_only(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    tree = parser.parse(source)
    assert tree.root_node.type == "module"
    assert not tree.root_node.has_error

    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    config = UserConfig(tmp_path / "settings" / "config.json")
    config.set("directories.base_dir", str(tmp_path / "grammar-state"))
    directory_manager = DirectoryManager(config)
    directories = directory_manager.create_structure()
    downloads = directories["cache_downloads"]
    builds = directories["cache_builds"]

    old_download = downloads / "old.py"
    new_download = downloads / "new.py"
    old_build = builds / "old.py"
    new_build = builds / "new.py"
    for path in (old_download, new_download, old_build, new_build):
        path.write_bytes(source)

    stale_time = time.time() - 45 * 24 * 60 * 60
    for path in (old_download, old_build):
        os.utime(path, (stale_time, stale_time))

    stats = CacheManager(config, directory_manager).cleanup_old_files(max_age_days=30)
    assert stats == {
        "files_removed": 2,
        "bytes_freed": 2 * len(source),
        "downloads_cleaned": 1,
        "builds_cleaned": 1,
    }
    assert not old_download.exists()
    assert not old_build.exists()
    for path in (new_download, new_build):
        assert path.exists()
        assert not parser.parse(path.read_bytes()).root_node.has_error
    assert not isolated_home.exists()


@pytest.mark.parametrize(
    ("base_subpath", "cache_subpath"),
    [
        ("grammar-state", "cache"),
        ("grammar-state", "nested/../cache"),
        ("alias/../grammar-state", "cache"),
    ],
)
def test_cache_cleanup_keeps_empty_managed_directories(
    tmp_path: Path, monkeypatch, base_subpath: str, cache_subpath: str
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error

    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    config = UserConfig(tmp_path / "settings" / "config.json")
    config.set("directories.base_dir", str(tmp_path / base_subpath))
    config.set("directories.cache_dir", cache_subpath)
    directory_manager = DirectoryManager(config)
    directories = directory_manager.create_structure()
    managed = (directories["cache_downloads"], directories["cache_builds"])
    stale_time = time.time() - 45 * 24 * 60 * 60
    for directory in managed:
        stale = directory / "old.py"
        stale.write_bytes(source)
        os.utime(stale, (stale_time, stale_time))

    stats = CacheManager(config, directory_manager).cleanup_old_files(max_age_days=30)
    assert stats["files_removed"] == 2
    for directory in managed:
        assert directory.is_dir()
        fresh = directory / "new.py"
        fresh.write_bytes(source)
        assert not parser.parse(fresh.read_bytes()).root_node.has_error
    assert not isolated_home.exists()


def test_cache_size_cleanup_evicts_oldest_parseable_file_first(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()

    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    config = UserConfig(tmp_path / "settings" / "config.json")
    config.set("directories.base_dir", str(tmp_path / "grammar-state"))
    directory_manager = DirectoryManager(config)
    directories = directory_manager.create_structure()
    oldest = directories["cache_builds"] / "oldest.py"
    newest = directories["cache_downloads"] / "newest.py"
    for path, size in ((oldest, 512 * 1024), (newest, 768 * 1024)):
        content = source + b"\n" + b" " * (size - len(source) - 1)
        path.write_bytes(content)
        assert not parser.parse(path.read_bytes()).root_node.has_error

    stale_time = time.time() - 45 * 24 * 60 * 60
    os.utime(oldest, (stale_time, stale_time))
    cache_manager = CacheManager(config, directory_manager)
    assert cache_manager.cleanup_by_size(target_size_mb=1) == {
        "files_removed": 1,
        "bytes_freed": 512 * 1024,
        "downloads_cleaned": 0,
        "builds_cleaned": 1,
    }
    assert not oldest.exists()
    assert newest.exists()
    assert not parser.parse(newest.read_bytes()).root_node.has_error
    assert cache_manager.cleanup_by_size(target_size_mb=1) == {
        "files_removed": 0,
        "bytes_freed": 0,
        "downloads_cleaned": 0,
        "builds_cleaned": 0,
    }
    assert not isolated_home.exists()


def test_cache_clear_downloads_recursively_preserves_builds(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error

    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    config = UserConfig(tmp_path / "settings" / "config.json")
    config.set("directories.base_dir", str(tmp_path / "grammar-state"))
    directory_manager = DirectoryManager(config)
    directories = directory_manager.create_structure()
    nested_download = directories["cache_downloads"] / "nested" / "service.py"
    nested_download.parent.mkdir()
    nested_download.write_bytes(source)
    retained_build = directories["cache_builds"] / "service.py"
    retained_build.write_bytes(source)

    cache_manager = CacheManager(config, directory_manager)
    assert cache_manager.clear_cache("downloads") == {
        "files_removed": 1,
        "bytes_freed": len(source),
        "downloads_cleaned": 1,
        "builds_cleaned": 0,
    }
    assert not nested_download.exists()
    assert directories["cache_downloads"].is_dir()
    assert retained_build.exists()
    assert not parser.parse(retained_build.read_bytes()).root_node.has_error
    assert cache_manager.clear_cache("downloads") == {
        "files_removed": 0,
        "bytes_freed": 0,
        "downloads_cleaned": 0,
        "builds_cleaned": 0,
    }
    assert retained_build.exists()
    assert not isolated_home.exists()


def test_cache_info_reports_parseable_sizes_and_cleanup_settings(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error

    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    config = UserConfig(tmp_path / "settings" / "config.json")
    config.set("directories.base_dir", str(tmp_path / "grammar-state"))
    config.set("cache.max_size_mb", 2)
    config.set("cache.cleanup_threshold_mb", 1)
    directory_manager = DirectoryManager(config)
    directories = directory_manager.create_structure()
    download = directories["cache_downloads"] / "nested" / "service.py"
    download.parent.mkdir()
    build = directories["cache_builds"] / "service.py"
    for path, size in ((download, 512 * 1024), (build, 768 * 1024)):
        path.write_bytes(source + b"\n" + b" " * (size - len(source) - 1))
        assert not parser.parse(path.read_bytes()).root_node.has_error

    cache_manager = CacheManager(config, directory_manager)
    info = cache_manager.get_cache_info()
    assert info["size"] == {
        "total_bytes": 1280 * 1024,
        "total_mb": 1.25,
        "downloads_bytes": 512 * 1024,
        "downloads_mb": 0.5,
        "builds_bytes": 768 * 1024,
        "builds_mb": 0.75,
    }
    assert info["limits"]["max_size_mb"] == 2
    assert info["limits"]["cleanup_threshold_mb"] == 1
    assert info["status"] == {"cleanup_needed": True, "usage_percentage": 62.5}

    config.set("cache.auto_cleanup", False)
    assert cache_manager.get_cache_info()["status"] == {
        "cleanup_needed": False,
        "usage_percentage": 62.5,
    }
    config.set("cache.auto_cleanup", True)
    config.set("cache.cleanup_threshold_mb", 2)
    assert cache_manager.get_cache_info()["status"] == {
        "cleanup_needed": False,
        "usage_percentage": 62.5,
    }
    assert not parser.parse(build.read_bytes()).root_node.has_error
    assert not isolated_home.exists()
