from pathlib import Path

from chunker.symbol_graph import extract_symbol_graph


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
