from pathlib import Path

from chunker.semantic_query import SemanticQuery


def test_semantic_query_exact_symbol_lookup(tmp_path: Path):
    source = tmp_path / "auth.py"
    source.write_text(
        "class AuthManager:\n"
        "    def authenticate(self, user, password):\n"
        "        return True\n",
        encoding="utf-8",
    )

    query = SemanticQuery(tmp_path)

    function_result = query.function_exists("auth.py", "authenticate")
    class_result = query.class_exists("auth.py", "AuthManager")

    assert function_result["exists"] is True
    assert function_result["kind"] == "method"
    assert class_result["exists"] is True
    assert class_result["qualified_name"] == "AuthManager"


def test_semantic_query_find_symbols_and_tests(tmp_path: Path):
    source = tmp_path / "auth.py"
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    source.write_text(
        "def authenticate(user, password):\n    return True\n",
        encoding="utf-8",
    )
    (tests_dir / "test_auth.py").write_text(
        "def test_authenticate():\n    assert True\n",
        encoding="utf-8",
    )

    query = SemanticQuery(tmp_path)

    symbols = query.find_symbols("*auth*", kind="function")
    candidate_tests = query.find_tests_for("auth.py")

    assert any(symbol["name"] == "authenticate" for symbol in symbols)
    assert candidate_tests
    assert any("test_auth.py" in candidate["path"] for candidate in candidate_tests)
