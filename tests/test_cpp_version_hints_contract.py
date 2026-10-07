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
