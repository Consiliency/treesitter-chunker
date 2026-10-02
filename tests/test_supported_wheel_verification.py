"""Verify the wheel produced by the supported build path."""

import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from chunker import get_parser
from chunker.build.builder import BuildSystem


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"


def _rewrite_wheel(
    source: Path, target: Path, suffix: str, replacement: str, new_text: str = ""
) -> None:
    with ZipFile(source) as original, ZipFile(target, "w") as changed:
        for member in original.infolist():
            data = original.read(member.filename)
            if member.filename.endswith(suffix):
                decoded = data.decode("utf-8").replace("\r\n", "\n")
                assert replacement in decoded
                data = decoded.replace(replacement, new_text).encode("utf-8")
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

    for name, replacement in (
        ("loose-pin", "Requires-Dist: tree-sitter-language-pack<1.210,>=1.20\n"),
        (
            "inactive-marker",
            'Requires-Dist: tree-sitter-language-pack<1.21,>=1.20; python_version < "3.0"\n',
        ),
    ):
        changed_dir = tmp_path / name
        changed_dir.mkdir()
        changed = changed_dir / wheel.name
        _rewrite_wheel(
            wheel,
            changed,
            ".dist-info/METADATA",
            "Requires-Dist: tree-sitter-language-pack<1.21,>=1.20\n",
            replacement,
        )
        valid, report = verifier.verify_build(changed, "linux")
        assert valid is False, report
        assert report["components"]["grammar_pack_dependency"] is False

    no_version_dir = tmp_path / "no-version"
    no_version_dir.mkdir()
    no_version = no_version_dir / wheel.name
    _rewrite_wheel(
        wheel,
        no_version,
        ".dist-info/METADATA",
        f"Version: {wheel.stem.split('-')[1]}\n",
    )
    valid, report = verifier.verify_build(no_version, "linux")
    assert valid is False, report
    assert "Wheel distribution metadata mismatch" in report["errors"]

    no_wheel_version_dir = tmp_path / "no-wheel-version"
    no_wheel_version_dir.mkdir()
    no_wheel_version = no_wheel_version_dir / wheel.name
    _rewrite_wheel(
        wheel,
        no_wheel_version,
        ".dist-info/WHEEL",
        "Wheel-Version: 1.0\n",
    )
    valid, report = verifier.verify_build(no_wheel_version, "linux")
    assert valid is False, report
    assert "Missing or unsupported Wheel-Version" in report["errors"]

    fake_native_dir = tmp_path / "fake-native"
    fake_native_dir.mkdir()
    fake_native = fake_native_dir / wheel.name
    with ZipFile(no_pack) as original, ZipFile(fake_native, "w") as changed:
        for member in original.infolist():
            changed.writestr(member, original.read(member.filename))
        changed.writestr("chunker/grammars/fake.so", b"not a grammar")
    valid, report = verifier.verify_build(fake_native, "linux")
    assert valid is False, report
    assert "grammar_pack_dependency" in report["missing"]

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


@pytest.mark.skipif(sys.platform != "linux", reason="Compiles an ELF grammar")
def test_native_wheel_with_compressed_platform_tags(tmp_path: Path) -> None:
    source_dir = ROOT / "packages/baml-grammar/src"
    grammar = tmp_path / "baml.so"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-I",
            str(source_dir),
            str(source_dir / "parser.c"),
            "-o",
            str(grammar),
        ],
        check=True,
        capture_output=True,
    )
    output = tmp_path / "dist"
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    pure_wheel = next(output.glob("*.whl"))
    native_wheel = tmp_path / pure_wheel.name.replace(
        "py3-none-any", "cp311-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64"
    )
    with ZipFile(pure_wheel) as original, ZipFile(native_wheel, "w") as changed:
        for member in original.infolist():
            data = original.read(member.filename)
            if member.filename.endswith(".dist-info/WHEEL"):
                wheel_info = data.decode("utf-8").replace("\r\n", "\n")
                wheel_info = wheel_info.replace(
                    "Root-Is-Purelib: true", "Root-Is-Purelib: false"
                ).replace(
                    "Tag: py3-none-any",
                    "Tag: cp311-abi3-manylinux_2_17_x86_64\n"
                    "Tag: cp311-abi3-manylinux2014_x86_64",
                )
                data = wheel_info.encode("utf-8")
            changed.writestr(member, data)
        changed.writestr("chunker/grammars/baml.so", grammar.read_bytes())
    valid, report = BuildSystem().verify_build(native_wheel, "linux")
    assert valid, report
    assert report["components"]["platform_match"] is True
    assert report["components"]["grammars"] is True

    no_runtime = tmp_path / "no-runtime"
    no_runtime.mkdir()
    missing_runtime_wheel = no_runtime / native_wheel.name
    _rewrite_wheel(
        native_wheel,
        missing_runtime_wheel,
        ".dist-info/METADATA",
        "Requires-Dist: tree_sitter<0.27,>=0.26\n",
    )
    valid, report = BuildSystem().verify_build(missing_runtime_wheel, "linux")
    assert valid is False, report
    assert "tree_sitter_runtime_dependency" in report["missing"]
