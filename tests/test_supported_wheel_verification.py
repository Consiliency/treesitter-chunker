"""Verify the wheel produced by the supported build path."""

import base64
import csv
import hashlib
import io
import os
import subprocess
import sys
import sysconfig
from pathlib import Path
from zipfile import ZipFile

import pytest

from chunker import get_parser
from chunker.build.builder import BuildSystem
from chunker.grammar_management.core import load_compiled_grammar


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


def _mutate_wheel_with_valid_record(
    source: Path,
    target: Path,
    *,
    drop: str | None = None,
    add: tuple[str, bytes] | None = None,
) -> None:
    with ZipFile(source) as original, ZipFile(target, "w") as changed:
        if drop is not None:
            assert drop in original.namelist()
        if add is not None:
            assert add[0] not in original.namelist()
        record_path = next(
            name for name in original.namelist() if name.endswith(".dist-info/RECORD")
        )
        rows = []
        for member in original.infolist():
            if member.filename in (drop, record_path):
                continue
            data = original.read(member.filename)
            changed.writestr(member, data)
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(
                b"="
            )
            rows.append(
                (member.filename, f"sha256={digest.decode('ascii')}", len(data))
            )
        if add is not None:
            name, data = add
            changed.writestr(name, data)
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(
                b"="
            )
            rows.append((name, f"sha256={digest.decode('ascii')}", len(data)))
        rows.append((record_path, "", ""))
        text = io.StringIO(newline="")
        writer = csv.writer(text, lineterminator="\n")
        writer.writerows(rows)
        changed.writestr(record_path, text.getvalue())


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
        assert report["components"]["missing_modules"] == []
        assert not report["errors"]

    installed = tmp_path / "installed"
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--no-deps",
            "--target",
            str(installed),
            str(wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    import_check = (
        "import sys; sys.path[:0] = [sys.argv[1], sys.argv[2]]; "
        "from pathlib import Path; import chunker, cli.main; "
        "assert Path(chunker.__file__).is_relative_to(Path(sys.argv[1])); "
        "assert Path(cli.main.__file__).is_relative_to(Path(sys.argv[1])); "
        "assert not chunker.get_parser('python').parse(Path(sys.argv[3]).read_bytes()).root_node.has_error"
    )
    clean_env = {**os.environ, "PYTHONPATH": "", "PYTHONNOUSERSITE": "1"}
    site_packages = sysconfig.get_path("purelib")
    subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            import_check,
            str(installed),
            site_packages,
            str(FIXTURE),
        ],
        cwd=tmp_path,
        env=clean_env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    command = next(
        (
            path
            for directory in ("bin", "Scripts")
            for name in ("tsc", "tsc.exe")
            if (path := installed / directory / name).is_file()
        ),
        None,
    )
    assert command is not None
    command_args = (
        [str(command), "--help"]
        if command.suffix == ".exe"
        else [
            sys.executable,
            "-S",
            "-c",
            "import runpy, sys; sys.path[:0] = [sys.argv[1], sys.argv[2]]; "
            "script = sys.argv[3]; sys.argv = [script, '--help']; "
            "runpy.run_path(script, run_name='__main__')",
            str(installed),
            site_packages,
            str(command),
        ]
    )
    command_result = subprocess.run(
        command_args,
        cwd=tmp_path,
        env={
            **clean_env,
            "PYTHONPATH": str(installed),
            "PYTHONIOENCODING": "utf-8",
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert command_result.returncode == 0, command_result.stderr
    assert "Usage" in command_result.stdout

    no_entry_points_dir = tmp_path / "no-entry-points"
    no_entry_points_dir.mkdir()
    no_entry_points = no_entry_points_dir / wheel.name
    with ZipFile(wheel) as built:
        entry_points_path = next(
            name
            for name in built.namelist()
            if name.endswith(".dist-info/entry_points.txt")
        )
    _mutate_wheel_with_valid_record(wheel, no_entry_points, drop=entry_points_path)
    valid, report = verifier.verify_build(no_entry_points, "linux")
    assert valid is False, report
    assert "entry_points" in report["missing"]
    no_commands = tmp_path / "no-commands"
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--no-deps",
            "--target",
            str(no_commands),
            str(no_entry_points),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert not any(
        (no_commands / directory / name).exists()
        for directory in ("bin", "Scripts")
        for name in ("tsc", "tsc.exe", "treesitter-chunker", "treesitter-chunker.exe")
    )

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
    assert "chunker/parser.py" in report["components"]["missing_modules"]

    no_record_dir = tmp_path / "no-record"
    no_record_dir.mkdir()
    no_record = no_record_dir / wheel.name
    with ZipFile(wheel) as source_wheel:
        record_path = next(
            name
            for name in source_wheel.namelist()
            if name.endswith(".dist-info/RECORD")
        )
    _drop_wheel_member(wheel, no_record, record_path)
    valid, report = verifier.verify_build(no_record, "linux")
    assert valid is False, report
    assert "record" in report["missing"]

    for name in ("METADATA", "WHEEL"):
        nested_dir = tmp_path / f"nested-{name.lower()}"
        nested_dir.mkdir()
        nested = nested_dir / wheel.name
        with ZipFile(wheel) as original, ZipFile(nested, "w") as changed:
            metadata_path = next(
                path
                for path in original.namelist()
                if path.endswith(f".dist-info/{name}")
            )
            for member in original.infolist():
                path = member.filename
                if path == metadata_path:
                    path = f"nested/{path}"
                changed.writestr(path, original.read(member.filename))
        valid, report = verifier.verify_build(nested, "linux")
        assert valid is False, report
        assert ("metadata" if name == "METADATA" else "wheel_info") in report["missing"]

    no_cache_dir = tmp_path / "no-cache"
    no_cache_dir.mkdir()
    no_cache = no_cache_dir / wheel.name
    _mutate_wheel_with_valid_record(wheel, no_cache, drop="chunker/_internal/cache.py")
    valid, report = verifier.verify_build(no_cache, "linux")
    assert valid is False, report
    assert "package" in report["missing"]
    assert "chunker/_internal/cache.py" in report["components"]["missing_modules"]
    broken_install = tmp_path / "broken-install"
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--no-deps",
            "--target",
            str(broken_install),
            str(no_cache),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    failed_import = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            "import sys; sys.path[:0] = [sys.argv[1], sys.argv[2]]; import chunker",
            str(broken_install),
            site_packages,
        ],
        cwd=tmp_path,
        env=clean_env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert failed_import.returncode != 0
    assert "ASTCache" in failed_import.stderr
    assert "broken-install" in failed_import.stderr

    no_cli_dir = tmp_path / "no-cli"
    no_cli_dir.mkdir()
    no_cli = no_cli_dir / wheel.name
    _mutate_wheel_with_valid_record(wheel, no_cli, drop="cli/main.py")
    valid, report = verifier.verify_build(no_cli, "linux")
    assert valid is False, report
    assert "package" in report["missing"]
    assert "cli/main.py" in report["components"]["missing_modules"]
    broken_cli_install = tmp_path / "broken-cli-install"
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--no-deps",
            "--target",
            str(broken_cli_install),
            str(no_cli),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    failed_cli = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            "import sys; sys.path[:0] = [sys.argv[1], sys.argv[2]]; import cli.main",
            str(broken_cli_install),
            site_packages,
        ],
        cwd=tmp_path,
        env=clean_env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert failed_cli.returncode != 0
    assert "cli.main" in failed_cli.stderr
    subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            "import sys; sys.path[:0] = [sys.argv[1], sys.argv[2]]; "
            "from pathlib import Path; from chunker.build.builder import BuildSystem; "
            "valid, report = BuildSystem().verify_build(Path(sys.argv[3]), 'linux'); "
            "assert not valid and 'cli/main.py' in report['components']['missing_modules'], report",
            str(broken_cli_install),
            site_packages,
            str(no_cli),
        ],
        cwd=tmp_path,
        env=clean_env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


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
    baml_source = ROOT / "packages/baml-grammar/tests/fixtures/release-0201.baml"
    assert (
        not load_compiled_grammar(grammar, "baml")
        .parse(baml_source.read_bytes())
        .root_node.has_error
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
    with ZipFile(pure_wheel) as built:
        dist_info_dir = next(
            name.split("/", 1)[0]
            for name in built.namelist()
            if name.endswith(".dist-info/RECORD")
        )
    data_dir = dist_info_dir.removesuffix(".dist-info") + ".data"
    for case, member in (
        ("package", "chunker/data/grammars/build/baml.so"),
        ("relocated", f"{data_dir}/purelib/chunker/data/grammars/build/baml.so"),
        ("libs", "treesitter_chunker.libs/baml.so"),
    ):
        universal_dir = tmp_path / f"universal-{case}"
        universal_dir.mkdir()
        universal_native = universal_dir / pure_wheel.name
        _mutate_wheel_with_valid_record(
            pure_wheel,
            universal_native,
            add=(member, grammar.read_bytes()),
        )
        for platform in ("linux", "macos", "windows"):
            valid, report = BuildSystem().verify_build(universal_native, platform)
            assert valid is False, report
            assert "Universal wheel contains native files" in report["errors"]

    mixed = tmp_path / pure_wheel.name.replace(
        "py3-none-any", "py3-none-any.manylinux2014_x86_64"
    )
    with ZipFile(pure_wheel) as original, ZipFile(mixed, "w") as changed:
        for member in original.infolist():
            data = original.read(member.filename)
            if member.filename.endswith(".dist-info/WHEEL"):
                info = data.decode("utf-8").replace("\r\n", "\n")
                info = info.replace("Root-Is-Purelib: true", "Root-Is-Purelib: false")
                info = info.replace(
                    "Tag: py3-none-any",
                    "Tag: py3-none-any\nTag: py3-none-manylinux2014_x86_64",
                )
                data = info.encode("utf-8")
            changed.writestr(member, data)
        changed.writestr("chunker/data/grammars/build/baml.so", grammar.read_bytes())
    valid, report = BuildSystem().verify_build(mixed, "linux")
    assert valid is False, report
    assert "Universal wheel contains native files" in report["errors"]

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
        changed.writestr("chunker/data/grammars/build/baml.so", grammar.read_bytes())
    valid, report = BuildSystem().verify_build(native_wheel, "linux")
    assert valid, report
    assert report["components"]["platform_match"] is True
    assert report["components"]["grammars"] is True
    packaged_root = tmp_path / "packaged-grammar"
    with ZipFile(native_wheel) as packaged:
        packaged.extract("chunker/data/grammars/build/baml.so", packaged_root)
    packaged_grammar = packaged_root / "chunker/data/grammars/build/baml.so"
    assert (
        not load_compiled_grammar(packaged_grammar, "baml")
        .parse(baml_source.read_bytes())
        .root_node.has_error
    )

    relocated_dir = tmp_path / "relocated-native"
    relocated_dir.mkdir()
    relocated = relocated_dir / native_wheel.name
    _mutate_wheel_with_valid_record(
        native_wheel,
        relocated,
        drop="chunker/data/grammars/build/baml.so",
        add=(
            f"{data_dir}/platlib/chunker/data/grammars/build/baml.so",
            grammar.read_bytes(),
        ),
    )
    valid, report = BuildSystem().verify_build(relocated, "linux")
    assert valid, report
    relocated_install = tmp_path / "relocated-install"
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--no-deps",
            "--target",
            str(relocated_install),
            str(relocated),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    installed_grammar = relocated_install / "chunker/data/grammars/build/baml.so"
    assert installed_grammar.exists()
    assert (
        not load_compiled_grammar(installed_grammar, "baml")
        .parse(baml_source.read_bytes())
        .root_node.has_error
    )

    misplaced_dir = tmp_path / "misplaced-grammar"
    misplaced_dir.mkdir()
    misplaced = misplaced_dir / native_wheel.name
    with ZipFile(native_wheel) as original, ZipFile(misplaced, "w") as changed:
        for member in original.infolist():
            path = member.filename
            if path == "chunker/data/grammars/build/baml.so":
                path = "chunker/grammars/baml.so"
            changed.writestr(path, original.read(member.filename))
    valid, report = BuildSystem().verify_build(misplaced, "linux")
    assert valid is False, report
    assert "grammars" in report["missing"]

    nested_dir = tmp_path / "nested-grammar"
    nested_dir.mkdir()
    nested = nested_dir / native_wheel.name
    with ZipFile(native_wheel) as original, ZipFile(nested, "w") as changed:
        for member in original.infolist():
            path = member.filename
            if path == "chunker/data/grammars/build/baml.so":
                path = "chunker/data/grammars/build/linux/baml.so"
            changed.writestr(path, original.read(member.filename))
    valid, report = BuildSystem().verify_build(nested, "linux")
    assert valid is False, report
    assert "grammars" in report["missing"]

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
