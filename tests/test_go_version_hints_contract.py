"""Go source constraints and module declarations keep their precedence."""

from pathlib import Path

import pytest

from chunker import get_parser
from chunker.languages.version_detection.go_detector import (
    GoVersionDetector,
    GoVersionInfo,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/go/service.go"
)


@pytest.mark.parametrize("prefix", ["//go:build", "// +build"])
@pytest.mark.parametrize(
    ("versions", "expected"),
    [
        (("1.9", "1.10"), "1.10"),
        (("1.10", "1.9"), "1.10"),
        (("1.99", "2.0"), "2.0"),
        (("2.0", "1.99"), "2.0"),
    ],
)
def test_go_build_constraint_versions_are_numeric(
    tmp_path: Path, prefix: str, versions: tuple[str, str], expected: str
) -> None:
    constraints = "".join(f"{prefix} go{version}\n" for version in versions)
    source = constraints + FIXTURE.read_text(encoding="utf-8")
    source_path = tmp_path / "service.go"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error

    detector = GoVersionDetector()
    hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    assert hints["build_constraints"] == expected
    assert detector.get_primary_version(hints) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "go1.10 && go1.9",
        "go1.9 && go1.10",
        "go1.21 && go1.9 && go1.10",
        "go1.9 && go1.21 && go1.10",
        "go1.9 && go1.10 && go1.21",
        "go1.10 && go1.9 && go1.10",
        "go1.10\t&&\tgo1.9",
    ],
)
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_positive_go_conjunction_retains_all_release_tags(
    tmp_path: Path, expression: str, newline: str
) -> None:
    source = f"//go:build {expression}{newline}{newline}" + FIXTURE.read_text(
        encoding="utf-8"
    )
    source_path = tmp_path / "service.go"
    source_path.write_text(source, encoding="utf-8", newline="")
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error

    detector = GoVersionDetector()
    hints = detector.detect_version(source, source_path)
    expected = "1.21" if "go1.21" in expression else "1.10"
    assert hints["build_constraints"] == expected
    assert detector.get_primary_version(hints) == expected


def test_modern_go_conjunction_precedes_legacy_hint(tmp_path: Path) -> None:
    source = "//go:build go1.10 && go1.9\n// +build go1.22\n\n" + FIXTURE.read_text(
        encoding="utf-8"
    )
    source_path = tmp_path / "service.go"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error
    detector = GoVersionDetector()
    hints = detector.detect_version(source, source_path)
    assert hints["build_constraints"] == "1.10"
    assert detector.get_primary_version(hints) == "1.10"


def test_go_mod_version_precedes_source_build_constraint(tmp_path: Path) -> None:
    source = "//go:build go1.21\n" + FIXTURE.read_text(encoding="utf-8")
    source_path = tmp_path / "service.go"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error

    mod_path = tmp_path / "go.mod"
    mod_path.write_text("module example.com/fixture\ngo 1.22\n", encoding="utf-8")

    detector = GoVersionDetector()
    source_hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    mod_hints = detector.detect_version(mod_path.read_text(encoding="utf-8"), mod_path)
    assert source_hints["file_type"] == "source"
    assert source_hints["build_constraints"] == "1.21"
    assert mod_hints["file_type"] == "module"
    assert mod_hints["go_mod_version"] == "1.22"

    combined = {**source_hints, "go_mod_version": mod_hints["go_mod_version"]}
    primary = detector.get_primary_version(combined)
    assert primary == "1.22"
    serialized = GoVersionInfo(
        go_version=primary,
        build_constraints=[source_hints["build_constraints"]],
        source="go.mod",
    ).to_dict()
    assert serialized["go_version"] == "1.22"
    assert serialized["build_constraints"] == ["1.21"]
    assert serialized["source"] == "go.mod"
