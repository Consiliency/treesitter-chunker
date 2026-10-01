"""Contract tests for exported grammar configuration and directories."""

import json
import shutil
from pathlib import Path

from chunker import get_parser
from chunker.grammar_management.config import DirectoryManager, UserConfig


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
