"""JavaScript source and package engine hints keep their precedence."""

import json
from pathlib import Path

from chunker import get_parser
from chunker.languages.version_detection.javascript_detector import (
    JavaScriptVersionDetector,
    JavaScriptVersionInfo,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/javascript/service.js"
)


def test_package_engines_precede_source_process_hint(tmp_path: Path) -> None:
    source = (
        "// ES2022\n"
        'const runningNode = process.version === "v20.11.0";\n'
        + FIXTURE.read_text(encoding="utf-8")
    )
    source_path = tmp_path / "service.js"
    source_path.write_text(source, encoding="utf-8")
    assert (
        not get_parser("javascript").parse(source.encode("utf-8")).root_node.has_error
    )

    package_path = tmp_path / "package.json"
    package_path.write_text(
        json.dumps({"name": "fixture", "engines": {"node": ">=20"}}),
        encoding="utf-8",
    )
    assert (
        json.loads(package_path.read_text(encoding="utf-8"))["engines"]["node"]
        == ">=20"
    )

    detector = JavaScriptVersionDetector()
    source_hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    package_hints = detector.detect_version(
        package_path.read_text(encoding="utf-8"), package_path
    )
    assert source_hints["file_type"] == "javascript"
    assert source_hints["process_version"] == "v20.11.0"
    assert source_hints["es_version"] == "2022"
    assert package_hints["file_type"] == "package"
    assert package_hints["node_version"] == ">=20"

    combined = {**source_hints, "node_version": package_hints["node_version"]}
    primary = detector.get_primary_version(combined)
    assert primary == ">=20"
    serialized = JavaScriptVersionInfo(
        node_version=primary,
        es_version=source_hints["es_version"],
        typescript_version=None,
        source="package.json",
    ).to_dict()
    assert serialized["node_version"] == primary
    assert serialized["es_version"] == "2022"
    assert serialized["source"] == "package.json"
