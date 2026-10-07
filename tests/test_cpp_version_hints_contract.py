"""C++ declared standards take precedence over weaker feature hints."""

from pathlib import Path

import pytest

from chunker import get_parser
from chunker.languages.version_detection.cpp_detector import CppVersionDetector


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/cpp/widget.cpp"
)


def test_declared_standard_precedes_feature_and_compiler_hints(tmp_path: Path) -> None:
    source = (
        "// C++20\n// gcc 13.2.0\n"
        + FIXTURE.read_text(encoding="utf-8")
        + "\n#if __cpp_if_constexpr >= 201606L\n"
        + "std::optional<int> optional_count;\n#endif\n"
    )
    source_path = tmp_path / "widget.cpp"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("cpp").parse(source.encode("utf-8")).root_node.has_error

    detector = CppVersionDetector()
    hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    assert hints["language"] == "C++"
    assert hints["file_type"] == "source"
    assert hints["cxx_standard"] == "20"
    assert hints["feature_test_macros"] == ["__cpp_if_constexpr"]
    assert hints["standard_from_features"] == "17"
    assert hints["compiler_version"] == "13.2.0"
    assert detector.get_primary_version(hints) == "C++20"


@pytest.mark.parametrize("newer", ["03", "11", "14", "17", "20", "23", "26"])
@pytest.mark.parametrize("reverse", [False, True])
def test_mixed_standard_comments_use_release_order(
    tmp_path: Path, newer: str, reverse: bool
) -> None:
    standards = ["98", newer]
    if reverse:
        standards.reverse()
    source = "".join(
        f"// C++{standard}\n" for standard in standards
    ) + FIXTURE.read_text(encoding="utf-8")
    source_path = tmp_path / "widget.cpp"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("cpp").parse(source.encode("utf-8")).root_node.has_error
    detector = CppVersionDetector()
    hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    assert hints["cxx_standard"] == newer
    assert detector.get_primary_version(hints) == f"C++{newer}"


def test_cplusplus_98_does_not_override_concepts(tmp_path: Path) -> None:
    source = (
        "#if __cplusplus >= 199711L\n#endif\n"
        + FIXTURE.read_text(encoding="utf-8")
        + "\ntemplate <typename T> concept HasCount = requires(T value) { value.count; };\n"
    )
    source_path = tmp_path / "widget.cpp"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("cpp").parse(source.encode("utf-8")).root_node.has_error
    detector = CppVersionDetector()
    hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    assert hints["cxx_standard"] == "20"
    assert detector.get_primary_version(hints) == "C++20"


@pytest.mark.parametrize(
    ("macro", "value", "expected"),
    [
        ("__cpp_static_assert", 200410, "11"),
        ("__cpp_generic_lambdas", 201304, "14"),
        ("__cpp_structured_bindings", 201606, "17"),
        ("__cpp_concepts", 201907, "20"),
    ],
)
@pytest.mark.parametrize("reverse", [False, True])
def test_feature_macros_use_release_order(
    tmp_path: Path, macro: str, value: int, expected: str, reverse: bool
) -> None:
    macros = [("__cpp_exceptions", 199711), (macro, value)]
    if reverse:
        macros.reverse()
    source = "".join(
        f"#if {name} >= {version}L\n#endif\n" for name, version in macros
    ) + FIXTURE.read_text(encoding="utf-8")
    source_path = tmp_path / "widget.cpp"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("cpp").parse(source.encode("utf-8")).root_node.has_error
    detector = CppVersionDetector()
    hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    assert hints["feature_test_macros"] == [name for name, _ in macros]
    assert hints["cxx_standard"] is None
    assert hints["standard_from_features"] == expected
    assert detector.get_primary_version(hints) == f"C++{expected}"


@pytest.mark.parametrize("standard", ["98", "03", "11", "14", "17", "20", "23", "26"])
def test_single_standard_retains_its_hint(standard: str) -> None:
    source = f"// C++{standard}\n" + FIXTURE.read_text(encoding="utf-8")
    assert not get_parser("cpp").parse(source.encode("utf-8")).root_node.has_error
    assert CppVersionDetector().detect_cxx_standard(source) == standard


def test_unrecognized_features_do_not_invent_a_standard() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    assert not get_parser("cpp").parse(source.encode("utf-8")).root_node.has_error
    detector = CppVersionDetector()
    assert detector.detect_cxx_standard(source) is None
    assert detector.map_features_to_standard([]) is None
    assert detector.map_features_to_standard(["__cpp_unknown"]) is None
    assert detector.map_features_to_standard(["__cpp_exceptions"]) == "98"


@pytest.mark.parametrize(
    ("prefix", "direct", "feature", "primary"),
    [
        ("#if __cpp_if_constexpr >= 201606L\n#endif\n", None, "17", "C++17"),
        ("int custom_constexpr = 1;\n", None, None, None),
        ("int widgetconstexpr = 1;\n", None, None, None),
        ("constexpr int answer = 42;\n", "11", None, "C++11"),
        (
            "int choose() { if constexpr (true) { return 1; } else { return 0; } }\n",
            "17",
            None,
            "C++17",
        ),
    ],
    ids=[
        "feature-macro",
        "underscore-identifier",
        "identifier",
        "keyword",
        "if-keyword",
    ],
)
def test_constexpr_keyword_hints_do_not_match_identifier_suffixes(
    tmp_path: Path,
    prefix: str,
    direct: str | None,
    feature: str | None,
    primary: str | None,
) -> None:
    source = prefix + FIXTURE.read_text(encoding="utf-8")
    source_path = tmp_path / "widget.cpp"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("cpp").parse(source.encode("utf-8")).root_node.has_error
    detector = CppVersionDetector()
    hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    assert hints["cxx_standard"] == direct
    assert hints.get("standard_from_features") == feature
    assert hints.get("feature_test_macros", []) == (
        ["__cpp_if_constexpr"] if feature else []
    )
    assert detector.get_primary_version(hints) == primary


@pytest.mark.parametrize("declared", [False, True])
@pytest.mark.parametrize(
    "snippet",
    [
        "int is_final = 1;\n",
        "int my_override = 1;\n",
        "int my_nullptr = 1;\n",
        "void my_static_assert(int value) {}\nvoid caller() { my_static_assert(1); }\n",
        "int my_co_yield = 1;\n",
        "using my_concept = int; my_concept value = 1;\n",
        "int final_name = 1;\n",
        "int override_name = 1;\n",
        "int nullptr_name = 1;\n",
        "void static_assert_name(int value) {}\nvoid caller() { static_assert_name(1); }\n",
        "int co_yield_name = 1;\n",
        "using concept_name = int; concept_name value = 1;\n",
    ],
    ids=[
        "final-prefix",
        "override-prefix",
        "nullptr-prefix",
        "static_assert-prefix",
        "co_yield-prefix",
        "concept-prefix",
        "final-suffix",
        "override-suffix",
        "nullptr-suffix",
        "static_assert-suffix",
        "co_yield-suffix",
        "concept-suffix",
    ],
)
def test_sibling_keyword_fragments_do_not_manufacture_hints(
    tmp_path: Path, snippet: str, declared: bool
) -> None:
    source = (
        ("// C++98\n" if declared else "")
        + snippet
        + FIXTURE.read_text(encoding="utf-8")
    )
    source_path = tmp_path / "widget.cpp"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("cpp").parse(source.encode("utf-8")).root_node.has_error
    detector = CppVersionDetector()
    hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    expected = "98" if declared else None
    assert detector.detect_cxx_standard(source) == expected
    assert hints["cxx_standard"] == expected
    assert detector.get_primary_version(hints) == ("C++98" if declared else None)


@pytest.mark.parametrize("same_line", [False, True], ids=["newline", "same-line"])
@pytest.mark.parametrize(
    ("before", "after", "standard"),
    [
        ("int *value =", "nullptr;", "11"),
        (
            "struct Base { virtual void f(); }; struct Derived : Base { void f()",
            "override; };",
            "11",
        ),
        ("struct Value", "final {};", "11"),
        ("int preface;", "static_assert(true);", "11"),
        (
            "template <typename T>",
            "concept HasCount = requires(T value) { value.count; };",
            "20",
        ),
        ("void values() {", "co_yield 1; }", "20"),
    ],
    ids=["nullptr", "override", "final", "static_assert", "concept", "co_yield"],
)
def test_genuine_sibling_keyword_hints_survive_both_placements(
    tmp_path: Path, before: str, after: str, standard: str, same_line: bool
) -> None:
    source = (
        before
        + (" " if same_line else "\n")
        + after
        + "\n"
        + FIXTURE.read_text(encoding="utf-8")
    )
    source_path = tmp_path / "widget.cpp"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("cpp").parse(source.encode("utf-8")).root_node.has_error
    detector = CppVersionDetector()
    hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    assert detector.detect_cxx_standard(source) == standard
    assert hints["cxx_standard"] == standard
    assert detector.get_primary_version(hints) == f"C++{standard}"
