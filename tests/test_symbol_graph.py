from pathlib import Path, PureWindowsPath
from unittest.mock import Mock

import pytest

from chunker import symbol_graph
from chunker.symbol_graph import extract_symbol_graph


def test_collect_source_files_uses_case_sensitive_path_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class WindowsSourceFile(PureWindowsPath):
        def is_file(self) -> bool:
            return True

    root = Mock(spec=Path)
    root.exists.return_value = True
    root.is_file.return_value = False
    root.rglob.return_value = [
        WindowsSourceFile("project/app.py"),
        WindowsSourceFile("project/D.py"),
        WindowsSourceFile("project/D/sub.py"),
        WindowsSourceFile("project/other.py"),
    ]
    monkeypatch.setattr(symbol_graph, "Path", lambda _: root)

    files = symbol_graph.collect_source_files("project", "python")

    assert [path.parts[1:] for path in files] == [
        ("D", "sub.py"),
        ("D.py",),
        ("app.py",),
        ("other.py",),
    ]


def test_extract_symbol_graph_python_project(tmp_path: Path):
    (tmp_path / "auth").mkdir()
    (tmp_path / "auth" / "user.py").write_text(
        "class User:\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "auth" / "login.py").write_text(
        "from .user import User\n\ndef login(name):\n    return User()\n",
        encoding="utf-8",
    )

    result = extract_symbol_graph(tmp_path, "python")

    assert result["metadata"]["files_processed"] == 2
    assert result["metadata"]["total_classes"] == 1
    assert result["metadata"]["total_functions"] == 1
    assert any(symbol["name"] == "User" for symbol in result["symbols"]["classes"])
    assert any(symbol["name"] == "login" for symbol in result["symbols"]["functions"])
    assert any(rel["is_internal"] for rel in result["relationships"])


def test_extract_symbol_graph_javascript_file(tmp_path: Path):
    js_file = tmp_path / "service.js"
    js_file.write_text(
        "import { helper } from './helper.js';\n"
        "export function greet(name) {\n"
        "  return helper(name);\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "helper.js").write_text(
        "export function helper(name) { return name; }\n",
        encoding="utf-8",
    )

    result = extract_symbol_graph(tmp_path, "javascript")

    assert result["metadata"]["files_processed"] == 2
    assert any(symbol["name"] == "greet" for symbol in result["symbols"]["functions"])
    assert any(symbol["name"] == "helper" for symbol in result["symbols"]["functions"])
    assert any(
        rel["type"] == "calls" and rel["is_internal"] for rel in result["relationships"]
    )
