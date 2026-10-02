"""Java source features and Gradle target declarations keep their precedence."""

from pathlib import Path

from chunker import get_parser
from chunker.languages.version_detection.java_detector import JavaVersionDetector


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/java/Widget.java"
)


def test_gradle_target_precedes_source_feature_hint(tmp_path: Path) -> None:
    source = FIXTURE.read_text(encoding="utf-8") + "\nrecord Point(int x, int y) {}\n"
    source_path = tmp_path / "Widget.java"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("java").parse(source.encode("utf-8")).root_node.has_error

    gradle_path = tmp_path / "build.gradle"
    gradle_path.write_text(
        "sourceCompatibility = '17'\ntargetCompatibility = '21'\n",
        encoding="utf-8",
    )

    detector = JavaVersionDetector()
    source_hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    gradle_hints = detector.detect_version(
        gradle_path.read_text(encoding="utf-8"), gradle_path
    )
    assert source_hints["file_type"] == "source"
    assert source_hints["min_version_from_features"] == "14"
    assert gradle_hints["file_type"] == "gradle"
    assert gradle_hints["gradle_version"] == "21"

    combined = {**source_hints, "gradle_version": gradle_hints["gradle_version"]}
    assert detector.get_primary_version(combined) == "21"
