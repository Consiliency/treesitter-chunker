"""Core grammar cache cleanup preserves recent files inside stale directories."""

import logging
import os
import time
from pathlib import Path

import pytest

from chunker.grammar_management.core import GrammarManager, InstallationInfo
from chunker.parser import get_parser


FIXTURE = (
    Path(__file__).resolve().parent / "fixtures/boundary_ir/repos/python/app/service.py"
)


@pytest.mark.parametrize(
    ("consumer", "clean_cache"),
    [
        ("manager", False),
        ("manager", True),
        ("installer", False),
        ("installer", True),
        ("installer_positional", True),
    ],
)
def test_remove_grammar_respects_cache_option(tmp_path, consumer, clean_cache):
    import tree_sitter_language_pack as provider

    source = FIXTURE.read_bytes()
    parser = provider.get_parser("python")
    assert not parser.parse(source).root_node.has_error
    libraries = list(Path(provider.cache_dir()).glob("*tree_sitter_python.*"))
    assert len(libraries) == 1
    manager = GrammarManager(
        user_dir=tmp_path / "user",
        package_dir=tmp_path / "package",
        cache_dir=tmp_path / "cache",
    )
    installed = tmp_path / "user" / "libpython.so"
    installed.write_bytes(libraries[0].read_bytes())
    installer = manager._installer
    installer._save_installation_info(
        "python",
        InstallationInfo(
            version="fixture",
            install_date=0,
            install_path=installed,
            source_url="https://github.com/tree-sitter/tree-sitter-python",
        ),
    )
    metadata = installer._grammars_dir / "python_install_info.json"
    assert metadata.is_file()
    assert manager._registry.get_grammar_path("python")[0] == installed
    retained = []
    unrelated = []
    for namespace, language_path in (
        ("downloads", "tree-sitter-python"),
        ("builds", "python"),
    ):
        directory = tmp_path / "cache" / namespace / language_path
        directory.mkdir(parents=True)
        cached = directory / "service.py"
        cached.write_bytes(source)
        retained.append(cached)
        other = directory.parent / "unrelated" / "service.py"
        other.parent.mkdir()
        other.write_bytes(source)
        unrelated.append(other)
    if consumer == "manager":
        result = manager.remove_grammar("python", clean_cache=clean_cache)
    elif consumer == "installer":
        result = installer.remove_grammar("python", clean_cache=clean_cache)
    else:
        with pytest.raises(TypeError):
            installer.remove_grammar("python", True, False)
        result = installer.remove_grammar("python", False)
    assert result == (True, None)
    assert not installed.exists()
    assert not metadata.exists()
    for cached in retained:
        if clean_cache:
            assert not cached.parent.exists()
        else:
            assert cached.read_bytes() == source
            assert not parser.parse(cached.read_bytes()).root_node.has_error
    for other in unrelated:
        assert other.read_bytes() == source


def test_old_cache_directory_keeps_recent_parseable_child(
    tmp_path: Path, caplog
) -> None:
    source = FIXTURE.read_bytes()
    parser = get_parser("python")
    assert not parser.parse(source).root_node.has_error

    cache_dir = tmp_path / "cache"
    old_directory = cache_dir / "downloads" / "old-directory"
    old_directory.mkdir(parents=True)
    stale_source = old_directory / "stale.py"
    recent_source = old_directory / "recent.py"
    stale_source.write_bytes(source)
    recent_source.write_bytes(source)
    old_time = time.time() - 25 * 86400
    recent_time = time.time() - 15 * 86400
    os.utime(stale_source, (old_time, old_time))
    os.utime(recent_source, (recent_time, recent_time))
    os.utime(old_directory, (old_time, old_time))

    manager = GrammarManager(
        user_dir=tmp_path / "user",
        package_dir=tmp_path / "package",
        cache_dir=cache_dir,
    )
    with caplog.at_level(logging.WARNING):
        result = manager.cleanup_cache(older_than_days=20)

    assert result["errors"] == []
    assert result["files_removed"] == 0
    assert result["bytes_freed"] == 0
    assert result["directories_cleaned"] == []
    assert "Skipping mixed-age cache directory" in caplog.text
    assert stale_source.read_bytes() == source
    assert recent_source.read_bytes() == source
    assert not parser.parse(recent_source.read_bytes()).root_node.has_error


def test_entirely_old_cache_directory_is_removed_with_accurate_file_count(
    tmp_path: Path,
) -> None:
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error

    cache_dir = tmp_path / "cache"
    old_directory = cache_dir / "downloads" / "old-directory"
    old_directory.mkdir(parents=True)
    old_time = time.time() - 25 * 86400
    for filename in ("first.py", "second.py"):
        old_source = old_directory / filename
        old_source.write_bytes(source)
        os.utime(old_source, (old_time, old_time))
    os.utime(old_directory, (old_time, old_time))

    manager = GrammarManager(
        user_dir=tmp_path / "user",
        package_dir=tmp_path / "package",
        cache_dir=cache_dir,
    )
    result = manager.cleanup_cache(older_than_days=20)

    assert result["errors"] == []
    assert result["files_removed"] == 1
    assert result["bytes_freed"] == 2 * len(source)
    assert result["directories_cleaned"] == ["downloads"]
    assert not old_directory.exists()


def test_entirely_old_cache_directory_with_dangling_symlink_is_removed(
    tmp_path: Path,
) -> None:
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error

    cache_dir = tmp_path / "cache"
    old_directory = cache_dir / "downloads" / "old-directory"
    old_directory.mkdir(parents=True)
    old_source = old_directory / "service.py"
    old_source.write_bytes(source)
    dangling_link = old_directory / "missing.py"
    try:
        dangling_link.symlink_to(old_directory / "absent.py")
    except OSError as exc:
        pytest.skip(f"Creating symlinks is unavailable: {exc}")
    old_time = time.time() - 25 * 86400
    os.utime(old_source, (old_time, old_time))
    try:
        os.utime(dangling_link, (old_time, old_time), follow_symlinks=False)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Setting symlink timestamps is unavailable: {exc}")
    os.utime(old_directory, (old_time, old_time))

    manager = GrammarManager(
        user_dir=tmp_path / "user",
        package_dir=tmp_path / "package",
        cache_dir=cache_dir,
    )
    result = manager.cleanup_cache(older_than_days=20)

    assert result["errors"] == []
    assert result["files_removed"] == 1
    assert result["bytes_freed"] == len(source)
    assert result["directories_cleaned"] == ["downloads"]
    assert not old_directory.exists()
