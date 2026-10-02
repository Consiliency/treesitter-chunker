"""Python source and project version hints stay attributable."""

from pathlib import Path

from chunker import get_parser
from chunker.languages.version_detection.python_detector import (
    PythonVersionDetector,
    PythonVersionInfo,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/python/app/service.py"
)


def test_source_and_setup_hints_preserve_documented_precedence(tmp_path: Path) -> None:
    source = (
        "#!/usr/bin/env python3.12\n"
        "import sys\n"
        + FIXTURE.read_text(encoding="utf-8")
        + "\nif sys.version_info >= (3, 10):\n    pass\n"
    )
    source_path = tmp_path / "service.py"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("python").parse(source.encode("utf-8")).root_node.has_error

    setup_path = tmp_path / "setup.py"
    setup_source = 'from setuptools import setup\nsetup(name="fixture", python_requires=">=3.11")\n'
    setup_path.write_text(setup_source, encoding="utf-8")
    assert (
        not get_parser("python").parse(setup_source.encode("utf-8")).root_node.has_error
    )

    detector = PythonVersionDetector()
    source_hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    setup_hints = detector.detect_version(
        setup_path.read_text(encoding="utf-8"), setup_path
    )
    assert source_hints["file_type"] == "source"
    assert source_hints["shebang"] == "3.12.0"
    assert source_hints["sys_version"] == "3.10.0"
    assert setup_hints["file_type"] == "setup"
    assert setup_hints["requirements"] == ">=3.11"

    combined = {**source_hints, "requirements": setup_hints["requirements"]}
    primary = detector.get_primary_version(combined)
    assert primary == "3.12.0"
    serialized = PythonVersionInfo(primary, "shebang", 1.0).to_dict()
    assert serialized["version"] == primary
    assert serialized["source"] == "shebang"
    assert serialized["confidence"] == 1.0
