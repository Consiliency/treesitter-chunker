"""C++ declared standards take precedence over weaker feature hints."""

from pathlib import Path

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
