"""Rust source hints and Cargo declarations keep their precedence."""

import tomllib
from pathlib import Path

from chunker import get_parser
from chunker.languages.version_detection.rust_detector import (
    RustVersionDetector,
    RustVersionInfo,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/language_smoke/samples/sample.rs"
)


def test_cargo_rust_version_precedes_source_rustc_hint(tmp_path: Path) -> None:
    source = "// rustc 1.70.0\n" + FIXTURE.read_text(encoding="utf-8")
    source_path = tmp_path / "sample.rs"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("rust").parse(source.encode("utf-8")).root_node.has_error

    cargo_path = tmp_path / "Cargo.toml"
    cargo_path.write_text(
        '[package]\nname = "fixture"\nversion = "0.1.0"\nedition = "2021"\n'
        'rust-version = "1.74.0"\n',
        encoding="utf-8",
    )
    assert (
        tomllib.loads(cargo_path.read_text(encoding="utf-8"))["package"]["edition"]
        == "2021"
    )

    detector = RustVersionDetector()
    source_hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    cargo_hints = detector.detect_version(
        cargo_path.read_text(encoding="utf-8"), cargo_path
    )
    assert source_hints["file_type"] == "source"
    assert source_hints["rustc_version"] == "1.70.0"
    assert cargo_hints["file_type"] == "cargo"
    assert cargo_hints["edition"] == "2021"
    assert cargo_hints["rust_version"] == "1.74.0"

    combined = {
        **source_hints,
        "edition": cargo_hints["edition"],
        "rust_version": cargo_hints["rust_version"],
    }
    assert detector.get_primary_version(combined) == "1.74.0"
    serialized = RustVersionInfo(
        edition=cargo_hints["edition"],
        rustc_version=source_hints["rustc_version"],
        features=[],
        source="Cargo.toml",
    ).to_dict()
    assert serialized["edition"] == "2021"
    assert serialized["source"] == "Cargo.toml"
