from pathlib import Path

import pytest

from chunker.symbol_graph import extract_symbol_graph


@pytest.mark.parametrize(
    ("filename", "source"),
    [
        ("doc.rst", "Heading\n=======\n\nA paragraph.\n"),
        ("code.asm", "global start\nstart:\n    mov eax, 1\n"),
        ("code.s", ".text\n.globl start\nstart:\n    mov $1, %eax\n"),
    ],
)
def test_extract_symbol_graph_with_pack_mapped_file(
    tmp_path: Path, filename: str, source: str
) -> None:
    (tmp_path / filename).write_text(source, encoding="utf-8")
    (tmp_path / "code.py").write_text("def example():\n    pass\n", encoding="utf-8")

    graph = extract_symbol_graph(tmp_path)

    assert graph["errors"] == []
    assert graph["metadata"]["files_processed"] == 2
    assert [symbol["name"] for symbol in graph["symbols"]["functions"]] == ["example"]


def test_extract_symbol_graph_skips_raku_without_pack_grammar(tmp_path: Path) -> None:
    (tmp_path / "code.raku").write_text('say "hello";\n', encoding="utf-8")
    (tmp_path / "code.py").write_text("def example():\n    pass\n", encoding="utf-8")

    graph = extract_symbol_graph(tmp_path)

    assert graph["errors"] == []
    assert graph["metadata"]["files_processed"] == 1


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
