"""Verify the wheel produced by the supported build path."""

import subprocess
from pathlib import Path
from zipfile import ZipFile

from chunker import get_parser
from chunker.build.builder import BuildSystem


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"


def _rewrite_wheel(source: Path, target: Path, suffix: str, replacement: str) -> None:
    with ZipFile(source) as original, ZipFile(target, "w") as changed:
        for member in original.infolist():
            data = original.read(member.filename)
            if member.filename.endswith(suffix):
                decoded = data.decode("utf-8").replace("\r\n", "\n")
                assert replacement in decoded
                data = decoded.replace(replacement, "").encode("utf-8")
            changed.writestr(member, data)


def _drop_wheel_member(source: Path, target: Path, member_to_drop: str) -> None:
    with ZipFile(source) as original, ZipFile(target, "w") as changed:
        assert member_to_drop in original.namelist()
        for member in original.infolist():
            if member.filename != member_to_drop:
                changed.writestr(member, original.read(member.filename))


def test_supported_wheel_and_invalid_variants(tmp_path: Path) -> None:
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error
    output = tmp_path / "dist"
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    wheel = next(output.glob("*.whl"))
    assert wheel.name.endswith("-py3-none-any.whl")
    verifier = BuildSystem()
    for platform in ("linux", "macos", "windows"):
        valid, report = verifier.verify_build(wheel, platform)
        assert valid, report
        assert report["components"]["platform_match"] is True
        assert not report["errors"]

    missing, report = verifier.verify_build(tmp_path / "missing.whl", "linux")
    assert missing is False
    assert "Artifact does not exist" in report["errors"]

    no_pack_dir = tmp_path / "no-pack"
    no_pack_dir.mkdir()
    no_pack = no_pack_dir / wheel.name
    _rewrite_wheel(
        wheel,
        no_pack,
        ".dist-info/METADATA",
        "Requires-Dist: tree-sitter-language-pack<1.21,>=1.20\n",
    )
    valid, report = verifier.verify_build(no_pack, "linux")
    assert valid is False, report
    assert report["components"]["grammar_pack_dependency"] is False

    wrong_tag_dir = tmp_path / "wrong-tag"
    wrong_tag_dir.mkdir()
    wrong_tag = wrong_tag_dir / wheel.name
    _rewrite_wheel(
        wheel,
        wrong_tag,
        ".dist-info/WHEEL",
        "Tag: py3-none-any\n",
    )
    valid, report = verifier.verify_build(wrong_tag, "linux")
    assert valid is False, report
    assert report["components"]["platform_match"] is False

    no_parser_dir = tmp_path / "no-parser"
    no_parser_dir.mkdir()
    no_parser = no_parser_dir / wheel.name
    _drop_wheel_member(wheel, no_parser, "chunker/parser.py")
    valid, report = verifier.verify_build(no_parser, "linux")
    assert valid is False, report
    assert "package" in report["missing"]
