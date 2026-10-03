"""Contract tests for the exported grammar registry and pinned parser."""

import importlib.util
import shutil
from pathlib import Path

import pytest

from chunker import get_parser
from chunker.grammar_management import GrammarPriority, GrammarRegistry


FIXTURE = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"


@pytest.mark.parametrize("library_name", ["libpython.so", "tree_sitter_python.so"])
def test_registry_selects_user_package_then_fallback(
    tmp_path: Path, monkeypatch, library_name: str
) -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    tree = get_parser("python").parse(source.encode("utf-8"))
    assert tree.root_node.type == "module"
    assert not tree.root_node.has_error

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None
    native_library = Path(native_spec.origin)

    user_dir = tmp_path / "user"
    package_dir = tmp_path / "package"
    fallback_dir = package_dir / "fallback"
    for directory in (user_dir, package_dir, fallback_dir):
        directory.mkdir()

    candidates = [
        (user_dir / library_name, GrammarPriority.USER),
        (package_dir / library_name, GrammarPriority.PACKAGE),
        (fallback_dir / library_name, GrammarPriority.FALLBACK),
    ]
    for path, _ in candidates:
        shutil.copyfile(native_library, path)

    for path, priority in candidates:
        registry = GrammarRegistry(user_dir=user_dir, package_dir=package_dir)
        assert registry.get_grammar_path("python") == (path, priority)
        assert registry.list_available_languages() == {"python"}
        assert registry.get_language_info("python") == {
            "language": "python",
            "path": str(path),
            "priority": priority.name,
            "exists": True,
            "size": native_library.stat().st_size,
            "modified": path.stat().st_mtime,
        }
        assert registry.get_grammar_path("missing") is None
        assert registry.get_language_info("missing") is None
        path.unlink()


def test_registry_prefers_lib_when_both_names_exist_in_user_directory(
    tmp_path: Path, monkeypatch
) -> None:
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None
    user_dir = tmp_path / "user"
    package_dir = tmp_path / "package"
    user_dir.mkdir()
    package_dir.mkdir()
    lib = user_dir / "libpython.so"
    alternate = user_dir / "tree_sitter_python.so"
    shutil.copyfile(native_spec.origin, lib)
    shutil.copyfile(native_spec.origin, alternate)

    registry = GrammarRegistry(user_dir=user_dir, package_dir=package_dir)
    assert registry.discover_grammars()["python"] == [
        (lib, GrammarPriority.USER),
        (alternate, GrammarPriority.USER),
    ]
    assert registry.get_grammar_path("python") == (lib, GrammarPriority.USER)
