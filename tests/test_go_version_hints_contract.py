"""Go source constraints and module declarations keep their precedence."""

from pathlib import Path

from chunker import get_parser
from chunker.languages.version_detection.go_detector import (
    GoVersionDetector,
    GoVersionInfo,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/go/service.go"
)


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
