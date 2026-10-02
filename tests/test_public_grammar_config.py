"""Contract tests for exported grammar configuration and directories."""

import json
import os
import shutil
import time
from pathlib import Path

import pytest
from chunker import get_parser
from chunker.grammar_management.config import CacheManager, DirectoryManager, UserConfig


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
    oldest = directories["cache_downloads"] / "oldest.py"
    newest = directories["cache_builds"] / "newest.py"
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
        "downloads_cleaned": 1,
        "builds_cleaned": 0,
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
