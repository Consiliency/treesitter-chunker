"""Regression tests for tar extraction and plugin trust boundaries."""

import io
import tarfile

import pytest

from chunker.build.builder import _safe_extract_tar
from chunker.plugin_manager import PluginManager


def test_safe_extract_blocks_parent_traversal(tmp_path):
    archive = tmp_path / "crafted.tar.bz2"
    with tarfile.open(archive, "w:bz2") as tar:
        member = tarfile.TarInfo("../escaped")
        member.size = 1
        tar.addfile(member, io.BytesIO(b"x"))

    with (
        tarfile.open(archive, "r:bz2") as tar,
        pytest.raises(ValueError, match="Unsafe"),
    ):
        _safe_extract_tar(tar, tmp_path / "extract")


def test_custom_plugin_directory_requires_explicit_trust(tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "example.py").write_text("raise AssertionError('must not execute')")
    manager = PluginManager()

    assert manager.discover_plugins() == []
    assert manager.discover_plugins(plugin_dir) == []
