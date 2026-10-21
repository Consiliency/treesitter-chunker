"""Real artifacts and independent omission oracles for the public wheel verifier."""

import base64
import csv
import hashlib
import io
import json
import os
import stat
import struct
import subprocess
import sys
import sysconfig
import tomllib
from email.parser import Parser
from pathlib import Path
from zipfile import ZipFile, ZipInfo

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

from chunker.build import BuildSystem, BuildSystemImpl
from chunker.build.builder import _REQUIRED_WHEEL_PAYLOAD, _WHEEL_PAYLOAD_VERSION
from chunker.grammar_management.core import load_compiled_grammar

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = {"chunker/py.typed", "chunker/boundary/boundary_ir.schema.json"}
PARSER_PINS = {
    "tree-sitter": ("tree_sitter_runtime_dependency", ">=0.26,<0.27"),
    "tree-sitter-language-pack": ("grammar_pack_dependency", ">=1.20,<1.21"),
    "tree-sitter-python": ("python_grammar_dependency", "==0.25.0"),
    "tree-sitter-javascript": ("javascript_grammar_dependency", "==0.25.0"),
}


def _run(argv, cwd, *, env=None):
    result = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
        check=False,
    )
    assert result.returncode == 0, (argv, result.stdout, result.stderr)
    return result


def _source_inventory():
    paths = _run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "--", "chunker", "cli"],
        ROOT,
    ).stdout.splitlines()
    return sorted(name for name in paths if name.endswith(".py") or name in RESOURCES)


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory):
    root = tmp_path_factory.mktemp("trusted-wheel")
    source = root / "source"
    source.mkdir()
    tracked = _run(["git", "ls-files", "-z"], ROOT).stdout.split("\0")
    for name in filter(None, tracked):
        original = ROOT / name
        if original.is_file():
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
    direct = root / "direct"
    through_sdist = root / "through-sdist"
    for output, options in ((direct, ["--wheel"]), (through_sdist, [])):
        result = _run(
            [
                sys.executable,
                "-m",
                "build",
                "--no-isolation",
                *options,
                "--outdir",
                str(output),
            ],
            source,
        )
        (root / (output.name + ".log")).write_text(
            result.stdout + result.stderr, encoding="utf-8"
        )
    return {
        "wheel": next(direct.glob("*.whl")),
        "sdist_wheel": next(through_sdist.glob("*.whl")),
        "sdist": next(through_sdist.glob("*.tar.gz")),
        "source": source,
    }


def _mutate_wheel_with_valid_record(
    source,
    target,
    *,
    drop=(),
    replace=None,
    add=(),
    move=None,
):
    """Change controlled fixture members and independently regenerate RECORD."""
    replace = replace or {}
    move = move or {}
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(source) as original:
        record = next(n for n in original.namelist() if n.endswith(".dist-info/RECORD"))
        assert set(drop) <= set(original.namelist())
        assert set(replace) <= set(original.namelist())
        members = [
            (
                move.get(info.filename, info.filename),
                replace.get(info.filename, original.read(info)),
            )
            for info in original.infolist()
            if info.filename not in (*drop, record)
        ]
    members.extend(add)
    record = move.get(record, record)
    rows = []
    with ZipFile(target, "w") as changed:
        for name, data in members:
            member = ZipInfo(name)
            member.filename = name
            changed.writestr(member, data)
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(
                b"="
            )
            rows.append((name, "sha256=" + digest.decode("ascii"), len(data)))
        rows.append((record, "", ""))
        text = io.StringIO(newline="")
        csv.writer(text, lineterminator="\n").writerows(rows)
        changed.writestr(record, text.getvalue())
    return target


def _metadata_paths(wheel):
    with ZipFile(wheel) as archive:
        prefix = next(
            n.split("/")[0]
            for n in archive.namelist()
            if n.endswith(".dist-info/METADATA")
        )
        return prefix, {
            name: archive.read(f"{prefix}/{name}").replace(b"\r\n", b"\n")
            for name in ("METADATA", "WHEEL", "entry_points.txt")
        }


def _check(wheel, *, platform="linux", valid=True, missing=None, error=None):
    for api in (BuildSystem, BuildSystemImpl):
        actual, report = api().verify_build(wheel, platform)
        assert actual is valid and report["valid"] is valid, report
        if missing:
            assert missing in report["missing"], report
        if error:
            assert any(error in item for item in report["errors"]), report
    return report


@pytest.fixture(params=[b"\n", b"\r\n"], ids=["lf", "crlf"])
def header_wheel(artifacts, tmp_path, request):
    source = artifacts["wheel"]
    prefix, contents = _metadata_paths(source)
    headers = {
        f"{prefix}/{name}": content.replace(b"\n", request.param)
        for name, content in contents.items()
    }
    control = _mutate_wheel_with_valid_record(
        source, tmp_path / "header-control" / source.name, replace=headers
    )
    with ZipFile(control) as archive:
        for name, expected in headers.items():
            assert archive.read(name) == expected
    _check(control)
    return control


def _install(wheel, target):
    _run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--no-deps",
            "--target",
            str(target),
            str(wheel),
        ],
        target.parent,
    )


def _installed_python(target, code, *args):
    clean_env = {
        **os.environ,
        "PYTHONPATH": "",
        "PYTHONNOUSERSITE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    bootstrap = (
        "import sys; sys.path[:0] = [sys.argv[1], sys.argv[2]]; "
        "from pathlib import Path; target = Path(sys.argv[1]); "
        "import chunker, chunker.build.builder; "
        "assert Path(chunker.__file__).is_relative_to(target); "
        "assert Path(chunker.build.builder.__file__).is_relative_to(target); "
    )
    return _run(
        [
            sys.executable,
            "-S",
            "-c",
            bootstrap + code,
            str(target),
            sysconfig.get_path("purelib"),
            *map(str, args),
        ],
        target.parent,
        env=clean_env,
    )


def test_payload_inventory_matches_trusted_source():
    expected = _source_inventory()
    assert set(expected) == _REQUIRED_WHEEL_PAYLOAD
    assert len(expected) == 330
    assert hashlib.sha256(
        "".join(name + "\n" for name in expected).encode()
    ).hexdigest() == (
        "225147f6d7e32d1354dde98839e0f0325381d6316072ca572a0779323146f809"
    )
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    assert project["version"] == _WHEEL_PAYLOAD_VERSION == "6.0.0"
    assert SpecifierSet(project["requires-python"]) == SpecifierSet(">=3.12")
    requirements = {
        canonicalize_name(r.name): r
        for value in project["dependencies"]
        if (r := Requirement(value))
    }
    for name, (_, pins) in PARSER_PINS.items():
        assert requirements[name].specifier == SpecifierSet(pins)
    assert requirements["packaging"].specifier == SpecifierSet(">=25.0")


def test_real_wheel_matches_trusted_source(artifacts):
    expected = _source_inventory()
    for key in ("wheel", "sdist_wheel"):
        wheel = artifacts[key]
        assert wheel.name == "treesitter_chunker-6.0.0-py3-none-any.whl"
        with ZipFile(wheel) as archive:
            for name in expected:
                assert name in archive.namelist(), name
                assert (
                    archive.read(name) == (artifacts["source"] / name).read_bytes()
                ), name
            prefix, contents = _metadata_paths(wheel)
            metadata = Parser().parsestr(contents["METADATA"].decode())
            assert metadata["Name"] == "treesitter-chunker"
            assert metadata["Version"] == "6.0.0"
            assert metadata["Requires-Python"] == ">=3.12"
            for name, (_, pins) in PARSER_PINS.items():
                matches = [
                    r
                    for value in metadata.get_all("Requires-Dist", [])
                    if canonicalize_name((r := Requirement(value)).name) == name
                ]
                assert len(matches) == 1
                assert matches[0].specifier == SpecifierSet(pins)
                assert (
                    not matches[0].marker
                    and not matches[0].url
                    and not matches[0].extras
                )
            assert b"Tag: py3-none-any" in contents["WHEEL"]
            assert f"{prefix}/RECORD" in archive.namelist()
        for platform in ("linux", "macos", "windows"):
            _check(wheel, platform=platform)
    assert artifacts["sdist"].stat().st_size > 0


def test_supported_wheel_installs_outside_checkout(artifacts, tmp_path):
    target = tmp_path / "installed"
    _install(artifacts["wheel"], target)
    schema = artifacts["source"] / "chunker/boundary/boundary_ir.schema.json"
    _installed_python(
        target,
        "import json, cli.main, tree_sitter, tree_sitter_python, tree_sitter_javascript; "
        "assert Path(cli.main.__file__).is_relative_to(target); "
        "assert all(not Path(m.__file__).is_relative_to(Path(sys.argv[4]) / package) "
        "for m in (tree_sitter, tree_sitter_python, tree_sitter_javascript) "
        "for package in ('chunker', 'cli')); "
        "from chunker.boundary import load_boundary_ir_schema; "
        "assert load_boundary_ir_schema() == json.loads(Path(sys.argv[3]).read_text()); "
        "samples = [('python', b'def wheel_fixture():\\n    return 42\\n', 'function_definition'), "
        "('javascript', b'function wheelFixture() { return 42; }', 'function_declaration')]; "
        "\nfor language, sample, kind in samples:\n"
        " root = chunker.get_parser(language).parse(sample).root_node\n"
        " assert not root.has_error and any(n.type == kind for n in root.children), root\n",
        schema,
        ROOT,
    )
    fixture = tmp_path / "fixture.py"
    fixture.write_text("def wheel_fixture():\n    return 42\n", encoding="utf-8")
    for command_name in ("treesitter-chunker", "tsc"):
        command = next(
            (
                p
                for directory in ("bin", "Scripts")
                for suffix in ("", ".exe")
                if (p := target / directory / (command_name + suffix)).is_file()
            ),
            None,
        )
        assert command is not None
        for args in (["--help"], ["chunk", str(fixture), "--lang", "python", "--json"]):
            if command.suffix == ".exe":
                result = _run(
                    [str(command), *args],
                    tmp_path,
                    env={
                        **os.environ,
                        "PYTHONPATH": str(target),
                        "PYTHONNOUSERSITE": "1",
                        "PYTHONIOENCODING": "utf-8",
                    },
                )
            else:
                result = _installed_python(
                    target,
                    "import runpy; script = sys.argv[3]; sys.argv = sys.argv[3:]; "
                    "runpy.run_path(script, run_name='__main__')",
                    command,
                    *args,
                )
            if args == ["--help"]:
                assert "Usage" in result.stdout
            else:
                chunks = json.loads(result.stdout)
                assert chunks and any(
                    "def wheel_fixture" in item["content"] for item in chunks
                )


@pytest.mark.parametrize(
    "omitted",
    [
        "cli/setup_command.py",
        "chunker/export/graphml_yed_exporter.py",
        "chunker/boundary/boundary_ir.schema.json",
    ],
)
def test_installed_damaged_verifier_uses_frozen_inventory(artifacts, tmp_path, omitted):
    wheel = _mutate_wheel_with_valid_record(
        artifacts["wheel"],
        tmp_path / "damaged" / artifacts["wheel"].name,
        drop=[omitted],
    )
    report = _check(wheel, valid=False, missing="package")
    assert report["components"]["missing_payload"] == [omitted]
    assert report["components"]["missing_modules"] == (
        [omitted] if omitted.endswith(".py") else []
    )
    target = tmp_path / "installed"
    _install(wheel, target)
    assert not (target / omitted).exists()
    _installed_python(
        target,
        "from chunker.build import BuildSystem, BuildSystemImpl; "
        "omitted = sys.argv[4]; assert not (target / omitted).exists(); "
        "\nfor api in (BuildSystem, BuildSystemImpl):\n"
        " valid, report = api().verify_build(Path(sys.argv[3]), 'linux')\n"
        " assert not valid and report['valid'] is False, report\n"
        " assert report['components']['package'] is False, report\n"
        " assert report['components']['missing_payload'] == [omitted], report\n"
        " assert report['components']['missing_modules'] == ([omitted] if omitted.endswith('.py') else []), report\n",
        wheel,
        omitted,
    )


@pytest.mark.parametrize(
    "schemes", [("direct", "purelib"), ("direct", "platlib"), ("purelib", "platlib")]
)
@pytest.mark.parametrize("equal", [True, False])
def test_installed_destination_collision_rejected(artifacts, tmp_path, schemes, equal):
    source = artifacts["wheel"]
    prefix, _ = _metadata_paths(source)
    data = prefix.removesuffix(".dist-info") + ".data"
    name = "cli/setup_command.py"
    with ZipFile(source) as archive:
        original = archive.read(name)
    paths = [name if s == "direct" else f"{data}/{s}/{name}" for s in schemes]
    wheel = _mutate_wheel_with_valid_record(
        source,
        tmp_path / source.name,
        drop=[name],
        add=[
            (paths[0], original),
            (paths[1], original if equal else b"# other bytes\n"),
        ],
    )
    report = _check(wheel, valid=False, error="destination collision")
    assert report["components"]["destination_collisions"]["library/" + name] == paths


@pytest.mark.parametrize("scheme", ["purelib", "platlib"])
def test_noncolliding_payload_relocation(artifacts, tmp_path, scheme):
    source = artifacts["wheel"]
    prefix, _ = _metadata_paths(source)
    name = "cli/setup_command.py"
    destination = prefix.removesuffix(".dist-info") + f".data/{scheme}/{name}"
    wheel = _mutate_wheel_with_valid_record(
        source,
        tmp_path / "relocated" / source.name,
        move={name: destination},
    )
    _check(wheel)
    target = tmp_path / "installed"
    _install(wheel, target)
    assert (target / name).read_bytes() == (artifacts["source"] / name).read_bytes()
    _installed_python(
        target,
        "import cli.setup_command; assert Path(cli.setup_command.__file__).is_relative_to(target)",
    )
    wrong = _mutate_wheel_with_valid_record(
        source,
        tmp_path / "wrong-data" / source.name,
        move={name: f"wrong-6.0.0.data/{scheme}/{name}"},
    )
    report = _check(wrong, valid=False, missing="package")
    assert report["components"]["missing_payload"] == [name]


@pytest.mark.parametrize(
    "commands",
    [
        "TREESITTER-CHUNKER = cli.main:app\ntsc = cli.main:app\n",
        "Treesitter-Chunker = cli.main:app\ntsc = cli.main:app\n",
        "treesitter-chunker = cli.main:app\nTSC = cli.main:app\n",
        "treesitter-chunker = cli.main:app\nTsc = cli.main:app\n",
        "tsc = cli.main:app\n",
        "treesitter-chunker = cli.main:app\n",
        "treesitter-chunker = wrong:app\ntsc = cli.main:app\n",
        "treesitter-chunker = cli.main:app\ntsc = wrong:app\n",
        "treesitter-chunker = cli.main:app\ntsc = cli.main:app\nextra = cli.main:app\n",
        "treesitter-chunker = cli.main:app\ntsc = cli.main:app\ntsc = cli.main:app\n",
        "[DEFAULT]\ntreesitter-chunker = cli.main:app\ntsc = cli.main:app\n",
    ],
)
def test_console_script_case_is_exact(artifacts, tmp_path, commands):
    source = artifacts["wheel"]
    _check(source)
    prefix, _ = _metadata_paths(source)
    wheel = _mutate_wheel_with_valid_record(
        source,
        tmp_path / source.name,
        replace={
            f"{prefix}/entry_points.txt": ("[console_scripts]\n" + commands).encode()
        },
    )
    if commands.count("tsc =") == 2:
        _check(wheel, valid=False, error="Failed to read wheel")
    else:
        _check(wheel, valid=False, missing="entry_points")


@pytest.mark.parametrize(
    "suffix",
    [
        ".so",
        ".so.1",
        ".so.1.2",
        ".SO.1",
        ".DLL",
        ".DYLIB",
        ".PYD",
        ".dll.1",
        ".dylib.1.2",
        ".pyd.2",
    ],
)
@pytest.mark.parametrize(
    "placement", ["grammar", "purelib", "platlib", "scripts", "libs"]
)
def test_universal_native_name_variants_rejected(
    artifacts, tmp_path, suffix, placement
):
    source = artifacts["wheel"]
    prefix, _ = _metadata_paths(source)
    data = prefix.removesuffix(".dist-info") + ".data"
    directory = {
        "grammar": "chunker/data/grammars/build",
        "purelib": f"{data}/purelib",
        "platlib": f"{data}/platlib",
        "scripts": f"{data}/scripts",
        "libs": "treesitter_chunker.libs",
    }[placement]
    wheel = _mutate_wheel_with_valid_record(
        source,
        tmp_path / source.name,
        add=[(f"{directory}/fixture{suffix}", b"name fixture")],
    )
    for platform in ("linux", "macos", "windows"):
        _check(
            wheel,
            platform=platform,
            valid=False,
            error="Universal wheel contains native files",
        )


@pytest.mark.parametrize(
    "name",
    [
        "/absolute.py",
        "C:/drive.py",
        "C:drive.py",
        "chunker\\evil.py",
        "chunker/../evil.py",
        "chunker/./evil.py",
        "chunker//evil.py",
        "treesitter_chunker-6.0.0.data/purelib/C:/evil.py",
    ],
)
def test_noncanonical_paths_rejected(artifacts, tmp_path, name):
    _check(artifacts["wheel"])
    wheel = _mutate_wheel_with_valid_record(
        artifacts["wheel"],
        tmp_path / artifacts["wheel"].name,
        add=[(name, b"fixture")],
    )
    data = wheel.read_bytes()
    end = data.rfind(b"PK\x05\x06")
    assert end >= 0
    count = struct.unpack_from("<H", data, end + 10)[0]
    cursor = struct.unpack_from("<I", data, end + 16)[0]
    names = []
    for _ in range(count):
        assert data[cursor : cursor + 4] == b"PK\x01\x02"
        length, extra, comment = struct.unpack_from("<HHH", data, cursor + 28)
        raw_name = data[cursor + 46 : cursor + 46 + length]
        offset = struct.unpack_from("<I", data, cursor + 42)[0]
        assert data[offset : offset + 4] == b"PK\x03\x04"
        local_length = struct.unpack_from("<H", data, offset + 26)[0]
        assert data[offset + 30 : offset + 30 + local_length] == raw_name
        names.append(raw_name)
        cursor += 46 + length + extra + comment
    assert name.encode("utf-8") in names
    with ZipFile(wheel) as archive:
        member = next(info for info in archive.infolist() if info.orig_filename == name)
        assert archive.read(member) == b"fixture"
        record = next(n for n in archive.namelist() if n.endswith(".dist-info/RECORD"))
        rows = list(csv.reader(io.StringIO(archive.read(record).decode("utf-8"))))
        digest = base64.urlsafe_b64encode(hashlib.sha256(b"fixture").digest()).rstrip(
            b"="
        )
        assert [name, "sha256=" + digest.decode("ascii"), "7"] in rows
    _check(wheel, valid=False, error=f"Noncanonical wheel member: {name}")


@pytest.mark.parametrize("scheme", ["scripts", "data", "headers", "library"])
def test_other_schemes_do_not_supply_library_payload(artifacts, tmp_path, scheme):
    source = artifacts["wheel"]
    prefix, _ = _metadata_paths(source)
    name = "cli/setup_command.py"
    destination = prefix.removesuffix(".dist-info") + f".data/{scheme}/{name}"
    wheel = _mutate_wheel_with_valid_record(
        source, tmp_path / source.name, move={name: destination}
    )
    report = _check(wheel, valid=False, missing="package")
    assert report["components"]["missing_payload"] == [name]


def test_required_directory_does_not_supply_payload(artifacts, tmp_path):
    source = artifacts["wheel"]
    name = "cli/setup_command.py"
    wheel = _mutate_wheel_with_valid_record(
        source, tmp_path / source.name, drop=[name], add=[(name + "/", b"")]
    )
    report = _check(wheel, valid=False, missing="package")
    assert report["components"]["missing_payload"] == [name]


def test_crc_failure_rejected(artifacts, tmp_path):
    source = artifacts["wheel"]
    name = "crc-fixture.txt"
    wheel = _mutate_wheel_with_valid_record(
        source, tmp_path / source.name, add=[(name, b"unique-crc-fixture-content")]
    )
    _check(wheel)
    content = wheel.read_bytes()
    assert content.count(b"unique-crc-fixture-content") == 1
    wheel.write_bytes(
        content.replace(b"unique-crc-fixture-content", b"broken-crc-fixture-content")
    )
    _check(wheel, valid=False, error=f"Corrupt wheel member: {name}")


@pytest.mark.parametrize("name", ["cli/setup_command.py", *sorted(RESOURCES)])
def test_required_payload_must_be_regular(artifacts, tmp_path, name):
    source = artifacts["wheel"]
    _check(source)
    wheel = tmp_path / source.name
    with ZipFile(source) as original, ZipFile(wheel, "w") as changed:
        for info in original.infolist():
            if info.filename == name:
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            changed.writestr(info, original.read(info))
    report = _check(
        wheel, valid=False, missing="package", error=f"Nonregular wheel member: {name}"
    )
    assert report["components"]["missing_payload"] == [name]


def test_duplicate_members_rejected(artifacts, tmp_path):
    with pytest.warns(UserWarning, match="Duplicate name"):
        wheel = _mutate_wheel_with_valid_record(
            artifacts["wheel"],
            tmp_path / artifacts["wheel"].name,
            add=[("cli/__init__.py", b"duplicate")],
        )
    _check(wheel, valid=False, error="Duplicate wheel members")


@pytest.mark.parametrize("name", list(PARSER_PINS))
@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "conditional", "extra", "url", "loose"]
)
def test_parser_dependency_mutations(header_wheel, tmp_path, name, mutation):
    source = header_wheel
    prefix, contents = _metadata_paths(source)
    text = contents["METADATA"].decode()
    line = next(
        line
        for line in text.splitlines(keepends=True)
        if line.startswith("Requires-Dist: ")
        and canonicalize_name(
            Requirement(line.removeprefix("Requires-Dist: ").strip()).name
        )
        == name
    )
    replacements = {
        "missing": "",
        "duplicate": line + line,
        "conditional": line.rstrip() + '; python_version < "3.0"\n',
        "extra": f"Requires-Dist: {name}[unexpected]{PARSER_PINS[name][1]}\n",
        "url": f"Requires-Dist: {name} @ https://example.invalid/parser.whl\n",
        "loose": f"Requires-Dist: {name}>=0\n",
    }
    changed = text.replace(line, replacements[mutation])
    assert changed != text
    wheel = _mutate_wheel_with_valid_record(
        source,
        tmp_path / source.name,
        replace={f"{prefix}/METADATA": changed.encode()},
    )
    _check(wheel, valid=False, missing=PARSER_PINS[name][0])


@pytest.mark.parametrize(
    ("member", "component"),
    [
        ("METADATA", "metadata"),
        ("WHEEL", "wheel_info"),
        ("RECORD", "record"),
        ("entry_points.txt", "entry_points"),
    ],
)
@pytest.mark.parametrize("nested", [True, False])
def test_required_metadata_is_direct(artifacts, tmp_path, member, component, nested):
    source = artifacts["wheel"]
    prefix, _ = _metadata_paths(source)
    path = f"{prefix}/{member}"
    if nested:
        wheel = _mutate_wheel_with_valid_record(
            source,
            tmp_path / source.name,
            move={path: f"{prefix}/nested/{member}"},
        )
    elif member == "RECORD":
        wheel = tmp_path / source.name
        with ZipFile(source) as original, ZipFile(wheel, "w") as changed:
            for info in original.infolist():
                if info.filename != path:
                    changed.writestr(info, original.read(info))
    else:
        wheel = _mutate_wheel_with_valid_record(
            source, tmp_path / source.name, drop=[path]
        )
    _check(wheel, valid=False, missing=component)


@pytest.mark.parametrize(
    "case",
    [
        "name",
        "version",
        "consistent-name",
        "unknown-version",
        "extra-dist-info",
        "empty-dist-info",
        "python-missing",
        "python-old",
        "tag-mismatch",
        "tag-missing",
        "purelib",
        "wheel-version",
    ],
)
def test_metadata_and_parser_contract_mutations(header_wheel, tmp_path, case):
    source = header_wheel
    prefix, contents = _metadata_paths(source)
    metadata, wheel_info = contents["METADATA"], contents["WHEEL"]
    move, add, filename = {}, [], source.name
    error = "Wheel distribution metadata mismatch"
    if case == "name":
        metadata = metadata.replace(b"Name: treesitter-chunker", b"Name: other-project")
    elif case == "version":
        metadata = metadata.replace(b"Version: 6.0.0", b"Version: 9.0.0")
    elif case in ("consistent-name", "unknown-version"):
        old, new = (
            ("treesitter_chunker", "other_project")
            if case == "consistent-name"
            else ("6.0.0", "9.0.0")
        )
        filename = filename.replace(old, new)
        with ZipFile(source) as archive:
            move = {name: name.replace(old, new) for name in archive.namelist()}
        metadata = metadata.replace(
            old.replace("_", "-").encode(), new.replace("_", "-").encode()
        )
        error = "Unsupported wheel payload contract"
    elif case in ("extra-dist-info", "empty-dist-info"):
        add = (
            [("extra-1.0.dist-info/METADATA", b"Name: extra\n")]
            if case == "extra-dist-info"
            else [("extra-1.0.dist-info/", b"")]
        )
        error = "Wheel metadata directories do not match"
    elif case.startswith("python-"):
        metadata = metadata.replace(
            b"Requires-Python: >=3.12\n",
            b"" if case == "python-missing" else b"Requires-Python: >=3.11\n",
        )
        error = "Unsupported source Requires-Python"
    elif case == "tag-mismatch":
        wheel_info = wheel_info.replace(b"py3-none-any", b"cp312-abi3-win_amd64")
        error = "Platform mismatch"
    elif case == "tag-missing":
        wheel_info = wheel_info.replace(b"Tag: py3-none-any\n", b"")
        error = "Platform mismatch"
    elif case == "purelib":
        wheel_info = wheel_info.replace(
            b"Root-Is-Purelib: true", b"Root-Is-Purelib: false"
        )
        error = "Platform mismatch"
    elif case == "wheel-version":
        wheel_info = wheel_info.replace(b"Wheel-Version: 1.0", b"Wheel-Version: 2.0")
        error = "Missing or unsupported Wheel-Version"
    assert (
        metadata != contents["METADATA"]
        or wheel_info != contents["WHEEL"]
        or move
        or add
    )
    wheel = _mutate_wheel_with_valid_record(
        source,
        tmp_path / filename,
        move=move,
        add=add,
        replace={f"{prefix}/METADATA": metadata, f"{prefix}/WHEEL": wheel_info},
    )
    _check(wheel, valid=False, error=error)


@pytest.fixture(scope="module")
def compiled_grammar(tmp_path_factory):
    if sys.platform != "linux":
        pytest.skip("Controlled ELF compilation executes on Linux")
    root = tmp_path_factory.mktemp("controlled-baml")
    source = ROOT / "packages/baml-grammar/src"
    grammar = root / "baml.so"
    _run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-I",
            str(source),
            str(source / "parser.c"),
            "-o",
            str(grammar),
        ],
        root,
    )
    fixture = ROOT / "packages/baml-grammar/tests/fixtures/release-0201.baml"
    assert (
        not load_compiled_grammar(grammar, "baml")
        .parse(fixture.read_bytes())
        .root_node.has_error
    )
    return grammar, fixture


def test_native_wheel_structure_and_relocation(artifacts, compiled_grammar, tmp_path):
    source = artifacts["wheel"]
    grammar, fixture = compiled_grammar
    prefix, contents = _metadata_paths(source)
    direct = "chunker/data/grammars/build/baml.so"
    data = prefix.removesuffix(".dist-info") + ".data"
    wheel_info = (
        contents["WHEEL"]
        .replace(b"Root-Is-Purelib: true", b"Root-Is-Purelib: false")
        .replace(
            b"Tag: py3-none-any",
            b"Tag: cp312-abi3-manylinux_2_17_x86_64\nTag: cp312-abi3-manylinux2014_x86_64",
        )
    )
    filename = source.name.replace(
        "py3-none-any", "cp312-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64"
    )
    native = _mutate_wheel_with_valid_record(
        source,
        tmp_path / filename,
        replace={f"{prefix}/WHEEL": wheel_info},
        add=[(direct, grammar.read_bytes())],
    )
    _check(native)
    _check(native, platform="windows", valid=False, error="Platform mismatch")
    for placement in (direct, f"{data}/platlib/{direct}"):
        wheel = _mutate_wheel_with_valid_record(
            native,
            tmp_path / ("direct" if placement == direct else "relocated") / filename,
            move={direct: placement},
        )
        _check(wheel)
        target = wheel.parent / "installed"
        _install(wheel, target)
        assert (target / direct).read_bytes() == grammar.read_bytes()
        assert (
            not load_compiled_grammar(target / direct, "baml")
            .parse(fixture.read_bytes())
            .root_node.has_error
        )
    for placement in (
        "chunker/grammars/baml.so",
        "chunker/data/grammars/build/nested/baml.so",
    ):
        wheel = _mutate_wheel_with_valid_record(
            native,
            tmp_path / placement.replace("/", "-") / filename,
            move={direct: placement},
        )
        _check(wheel, valid=False, missing="grammars")
    universal = _mutate_wheel_with_valid_record(
        source,
        tmp_path / "universal" / source.name,
        add=[(direct, grammar.read_bytes())],
    )
    _check(universal, valid=False, error="Universal wheel contains native files")
    mixed_name = source.name.replace("any", "any.manylinux2014_x86_64")
    mixed_info = (
        contents["WHEEL"]
        .replace(b"Root-Is-Purelib: true", b"Root-Is-Purelib: false")
        .replace(
            b"Tag: py3-none-any",
            b"Tag: py3-none-any\nTag: py3-none-manylinux2014_x86_64",
        )
    )
    mixed = _mutate_wheel_with_valid_record(
        source,
        tmp_path / mixed_name,
        replace={f"{prefix}/WHEEL": mixed_info},
        add=[(direct, grammar.read_bytes())],
    )
    _check(mixed, valid=False, error="Universal wheel contains native files")
    mismatch = _mutate_wheel_with_valid_record(
        source,
        tmp_path / "metadata-any" / filename,
        add=[(direct, grammar.read_bytes())],
    )
    _check(mismatch, valid=False, error="Universal wheel contains native files")
