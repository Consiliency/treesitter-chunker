"""Regression tests for tar extraction and plugin trust boundaries."""

import io
import tarfile
from pathlib import Path

import pytest

from chunker import get_parser
from chunker.build.builder import _safe_extract_tar
from chunker.plugin_manager import PluginManager

FIXTURE = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"


def test_safe_extract_keeps_parseable_source_in_nested_directory(tmp_path):
    source = FIXTURE.read_bytes()
    parser = get_parser("python")
    assert not parser.parse(source).root_node.has_error

    archive = tmp_path / "source.tar.bz2"
    with tarfile.open(archive, "w:bz2") as tar:
        directory = tarfile.TarInfo("package")
        directory.type = tarfile.DIRTYPE
        tar.addfile(directory)
        member = tarfile.TarInfo("package/service.py")
        member.size = len(source)
        tar.addfile(member, io.BytesIO(source))

    destination = tmp_path / "extract"
    with tarfile.open(archive, "r:bz2") as tar:
        _safe_extract_tar(tar, destination)

    extracted = destination / "package" / "service.py"
    assert extracted.read_bytes() == source
    assert not parser.parse(extracted.read_bytes()).root_node.has_error


@pytest.mark.parametrize("unsafe_name", ["/escaped.py", "C:/escaped.py"])
def test_safe_extract_rejects_absolute_members_before_writing(tmp_path, unsafe_name):
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error

    archive = tmp_path / "mixed.tar.bz2"
    with tarfile.open(archive, "w:bz2") as tar:
        valid = tarfile.TarInfo("package/service.py")
        valid.size = len(source)
        tar.addfile(valid, io.BytesIO(source))
        unsafe = tarfile.TarInfo(unsafe_name)
        unsafe.size = len(source)
        tar.addfile(unsafe, io.BytesIO(source))

    destination = tmp_path / "extract"
    with (
        tarfile.open(archive, "r:bz2") as tar,
        pytest.raises(ValueError, match="Unsafe tar member"),
    ):
        _safe_extract_tar(tar, destination)
    assert not destination.exists()


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
