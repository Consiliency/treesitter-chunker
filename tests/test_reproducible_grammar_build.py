"""Path-independent installer grammar builds (treesitter-chunker#621, #607).

``GrammarInstaller``'s controlled gcc route runs the ``gcc`` first on ``PATH``
(resolved once, to an absolute path) with cwd = the grammar source root, the
relative paths ``src``, ``src/parser.c`` and ``src/scanner.c``, and per-platform
link flags (``_build_recipe``). The same grammar source then builds to the same
bytes wherever it is cloned and built, on Linux, macOS and Windows (MinGW).
The route declines C++ scanners before compiling, and on Linux refuses
undefined symbols (``-Wl,-z,defs``), so it never reports success for a partial
library. Methods run gcc, then ``make``, then the ``tree-sitter`` CLI.

The fixture (``tests/fixtures/reproducible_grammar``) keeps its source path
through glibc and MinGW ``assert`` and through direct ``__FILE__`` uses in a
``.c`` file and a ``src/tree_sitter`` header; it is compiled only, never loaded.

Tests that need the installer's compiler use :func:`_installer_compiler`: a
missing ``gcc`` and ``cc`` fails on CI (or with ``CHUNKER_REQUIRE_INSTALLER_COMPILER``)
and is a typed skip elsewhere.

Named mutations (plan §4.3), each a temporary patch that must fail here:

- ``follow_symlinked_src``: remove the source symlink preflight. Killed by
  the symlink decline test, before any process can start.
- ``cc_not_tried``: resolve gcc only. Killed by the cc-only resolution case.
- ``cc_before_gcc``: prefer cc. Killed by the both-present resolution case.
- ``absolute_sources``: the recipe emits absolute ``-I``/source paths.
  Killed by the two-path test and the golden argv.
- ``cwd_output_dir``: relative argv, but cwd = the output directory. Killed by
  the two-path test (the build fails).
- ``drop_install_name``: no darwin flag. Golden ``[darwin]``; real effect in the
  two-path test on macOS.
- ``drop_no_insert_timestamp``: golden ``[win32]``; real effect
  ``TimeDateStamp == 0`` on Windows.
- ``drop_disable_auto_image_base``: golden ``[win32]``; real effect the
  two-path digest on Windows.
- ``drop_z_defs``: golden ``[linux]``; real effect
  ``test_gcc_route_refuses_undefined_symbols`` on Linux.
- ``gcc_ignores_cxx_scanner``: no C++ decline. Killed by
  ``test_gcc_route_declines_cxx_scanner_without_compiling`` on any host.
- ``bare_gcc_name``: ``argv[0] = "gcc"``. Killed by
  ``test_gcc_is_resolved_once_to_an_absolute_path``.
- ``probe_failure_fails_install``: a failed probe fails ``_build_grammar``.
  Killed by ``test_compiler_probe_failure_still_builds`` and the install-level
  test in ``tests/test_cache_entry_transactions.py``.
- ``banner_from_stderr``: the probe parses stderr too. Killed by
  ``test_compiler_probe_failure_still_builds[stderr_only]``.
- ``tree_sitter_first``: the old method order. Killed by the order test.
- ``fallback_after_timeout``: continue after an abort. Killed by the order
  test (and ``test_build_timeout_fails_without_fallback_or_publication``).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from chunker.grammar_management import _build_recipe, _transactions
from chunker.grammar_management import core as core_module
from chunker.grammar_management.core import GrammarInstaller, _StagedRunAbortedError

FIXTURE = Path(__file__).parent / "fixtures" / "reproducible_grammar"
NO_INSTALLER_COMPILER = (
    "no gcc or cc on PATH: the installer's controlled build route is unavailable"
)
BUILD_TIMEOUT = 300


def _policy_required() -> bool:
    return bool(
        os.environ.get("CI") or os.environ.get("CHUNKER_REQUIRE_INSTALLER_COMPILER")
    )


def _installer_compiler() -> str:
    """The absolute ``gcc`` or ``cc`` the installer resolves; fail on CI, skip elsewhere."""
    found = shutil.which("gcc") or shutil.which("cc")
    if found is None:
        if _policy_required():
            pytest.fail(
                f"{sys.platform} CI must provide gcc or cc for the installer's "
                "reproducible-build test (treesitter-chunker#621)"
            )
        pytest.skip(NO_INSTALLER_COMPILER)
    return os.path.abspath(found)  # noqa: PTH100 - as the installer resolves it


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _staged_fixture(
    root: Path,
) -> tuple[GrammarInstaller, _transactions.StagingArea, Path]:
    """An installer on ``root``, a real staging area and the fixture copied in."""
    installer = GrammarInstaller(cache_dir=root, build_timeout=BUILD_TIMEOUT)
    staging = _transactions.create_staging(root)
    source = staging.path("downloads") / "tree-sitter-repro"
    shutil.copytree(FIXTURE, source)
    return installer, staging, source


def _write_grammar(source: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return source


def _pe_time_date_stamp(data: bytes) -> int:
    e_lfanew = int.from_bytes(data[0x3C:0x40], "little")
    assert data[e_lfanew : e_lfanew + 4] == b"PE\0\0"
    return int.from_bytes(data[e_lfanew + 8 : e_lfanew + 12], "little")


ROOTS = (Path("a"), Path("bb") / "c")  # differ in name and length; short for MAX_PATH


# --- the controlled route, built for real --------------------------------------


@pytest.mark.parametrize("compiler_choice", ["default", "cc", "clang-as-cc"])
def test_installer_builds_are_identical_at_two_paths(
    tmp_path, monkeypatch, compiler_choice
):
    """The fixture builds to one SHA-256 at two roots of different name and length."""
    _installer_compiler()
    if compiler_choice != "default":
        if compiler_choice == "clang-as-cc" and sys.platform not in ("linux", "darwin"):
            pytest.skip("clang-as-cc link-flag contract covers Linux and macOS")
        found = shutil.which("cc" if compiler_choice == "cc" else "clang")
        if found is None:
            if _policy_required():
                pytest.fail(f"CI must provide {compiler_choice}")
            pytest.skip(f"{compiler_choice} is unavailable on PATH")
        compiler = Path(os.path.abspath(found))  # noqa: PTH100
        if compiler_choice == "clang-as-cc":
            # Invoke clang under the actual name cc, exercising the same driver
            # and linker flags as the installer's cc fallback on each OS.
            compiler_dir = tmp_path / "compiler"
            compiler_dir.mkdir()
            (compiler_dir / "cc").symlink_to(compiler)
            compiler = compiler_dir / "cc"
        real_which = shutil.which
        monkeypatch.setattr(
            core_module.shutil,
            "which",
            lambda name, *a, **k: (
                None
                if name == "gcc"
                else str(compiler) if name == "cc" else real_which(name, *a, **k)
            ),
        )
    built: list[tuple[Path, _transactions.StagingArea]] = []
    stagings: list[_transactions.StagingArea] = []
    try:
        for relative in ROOTS:
            root = tmp_path / relative
            installer, staging, source = _staged_fixture(root)
            stagings.append(staging)
            ok, path, error, record = installer._build_grammar(
                "repro", source, staging=staging
            )
            assert ok, error
            assert record is not None and record["method"] == "gcc", record
            assert path is not None and path.name == "librepro.so"
            if compiler_choice == "clang-as-cc":
                assert record["compiler"]["family"] == "clang"
                print(f"clang-as-cc flags accepted: {record['compiler']}")
            print(f"{compiler_choice}: {_sha(path)}")
            built.append((path, staging))

        (library_a, staging_a), (library_b, _staging_b) = built
        assert str(library_a) != str(library_b)
        assert len(str(library_a)) != len(str(library_b))
        assert _sha(library_a) == _sha(library_b), "the build is path-dependent"

        data = library_a.read_bytes()
        assert b"src/scanner.c" in data
        assert b"src/tree_sitter/parser.h" in data
        for namespace in ("downloads", "builds"):
            assert os.fsencode(str(staging_a.path(namespace))) not in data, namespace
        if sys.platform == "darwin":
            assert b"@rpath/librepro.so" in data
            assert os.fsencode(str(library_a.parent)) not in data
        if sys.platform == "win32":
            assert _pe_time_date_stamp(data) == 0
    finally:
        for staging in stagings:
            _transactions.discard_staging(staging)


def test_legacy_command_differs_at_two_paths(tmp_path):
    """Negative control: the old absolute-path command is path-dependent."""
    gcc = _installer_compiler()
    digests = []
    scanner_a = None
    library_a = None
    stagings: list[_transactions.StagingArea] = []
    try:
        for relative in ROOTS:
            root = tmp_path / relative
            _installer, staging, source = _staged_fixture(root)
            stagings.append(staging)
            out_dir = staging.path("builds") / "repro"
            out_dir.mkdir()
            out = out_dir / "librepro.so"
            src = source / "src"
            scanner = str(src / "scanner.c")
            if not scanner.isascii():
                message = f"the legacy scanner argument is not ASCII: {scanner!r}"
                if _policy_required():
                    pytest.fail(message)
                pytest.skip(message)
            legacy_argv = [
                gcc,
                "-shared",
                "-fPIC",
                "-O2",
                "-I",
                str(src),
                str(src / "parser.c"),
                scanner,
                "-o",
                str(out),
            ]
            completed = subprocess.run(
                legacy_argv,
                cwd=out_dir,
                capture_output=True,
                text=True,
                timeout=BUILD_TIMEOUT,
                check=False,
            )
            assert completed.returncode == 0, completed.stderr[-4000:]
            digests.append(_sha(out))
            if scanner_a is None:
                scanner_a, library_a = scanner, out
        assert digests[0] != digests[1]
        assert library_a is not None and scanner_a is not None
        assert os.fsencode(scanner_a) in library_a.read_bytes()
    finally:
        for staging in stagings:
            _transactions.discard_staging(staging)


def test_gcc_route_refuses_undefined_symbols(tmp_path):
    """An undefined symbol fails the gcc route (Linux through ``-z defs``)."""
    gcc = _installer_compiler()
    installer = GrammarInstaller(
        cache_dir=tmp_path / "cache", build_timeout=BUILD_TIMEOUT
    )
    staging = _transactions.create_staging(tmp_path / "cache")
    try:
        source = _write_grammar(
            staging.path("downloads") / "tree-sitter-undef",
            {
                "src/parser.c": (
                    "int tree_sitter_undef_missing(int);\n"
                    "int tree_sitter_undef(int v) "
                    "{ return tree_sitter_undef_missing(v); }\n"
                )
            },
        )
        out_dir = staging.path("builds") / "undef"
        out_dir.mkdir()
        success, error = installer._build_with_gcc(
            "undef", source, out_dir / "libundef.so", staging=staging, compiler=gcc
        )
        assert success is False, error
        assert error is not None and error.startswith("GCC build failed"), error
    finally:
        _transactions.discard_staging(staging)


def test_cxx_scanner_grammar_is_not_built_by_gcc(tmp_path, monkeypatch):
    """End to end: a ``scanner.cc``-only grammar never becomes a gcc build."""
    _installer_compiler()
    installer = GrammarInstaller(
        cache_dir=tmp_path / "cache", build_timeout=BUILD_TIMEOUT
    )
    staging = _transactions.create_staging(tmp_path / "cache")
    calls: list[str] = []

    def fail(name):
        def method(*args, **kwargs):
            calls.append(name)
            return False, f"{name} patched to fail"

        return method

    monkeypatch.setattr(installer, "_build_with_make", fail("make"))
    monkeypatch.setattr(
        installer, "_build_with_tree_sitter_cli", fail("tree-sitter-cli")
    )
    try:
        source = _write_grammar(
            staging.path("downloads") / "tree-sitter-cxx",
            {
                "src/parser.c": (
                    "void *tree_sitter_cxx_external_scanner_create(void);\n"
                    "void tree_sitter_cxx_external_scanner_destroy(void *);\n"
                    "void *tree_sitter_cxx(void) {\n"
                    "  void *s = tree_sitter_cxx_external_scanner_create();\n"
                    "  tree_sitter_cxx_external_scanner_destroy(s);\n"
                    "  return s;\n"
                    "}\n"
                ),
                "src/scanner.cc": (
                    'extern "C" void *tree_sitter_cxx_external_scanner_create() '
                    "{ return 0; }\n"
                    'extern "C" void tree_sitter_cxx_external_scanner_destroy(void *) {}\n'
                ),
            },
        )
        ok, path, error, record = installer._build_grammar(
            "cxx", source, staging=staging
        )
        assert (ok, path, record) == (False, None, None), (error, record)
        assert error == (
            "All build methods failed. Last error: tree-sitter-cli patched to fail"
        )
        assert calls == ["make", "tree-sitter-cli"]
        assert not (staging.path("builds") / "cxx" / "libcxx.so").exists()
    finally:
        _transactions.discard_staging(staging)


@pytest.mark.parametrize("fault", ["nonzero", "missing", "stderr_only"])
def test_compiler_probe_failure_still_builds(tmp_path, fault):
    """A failed ``--version`` probe records ``compiler: None`` and still builds."""
    _installer_compiler()
    installer, staging, source = _staged_fixture(tmp_path / "cache")
    real = installer._run_staged
    probes: list[list[str]] = []

    def run_staged(staging_area, argv, *, what, **kwargs):
        if what != "Compiler version":
            return real(staging_area, argv, what=what, **kwargs)
        probes.append(argv)
        banner = "gcc (Probe 15.2.0) 15.2.0\n"
        if fault == "missing":
            raise FileNotFoundError(argv[0])
        if fault == "nonzero":
            return _transactions.StagedRun(1, banner, "", False, True)
        return _transactions.StagedRun(0, "", banner, False, True)

    installer._run_staged = run_staged  # type: ignore[method-assign]
    try:
        ok, path, error, record = installer._build_grammar(
            "repro", source, staging=staging
        )
        assert ok, error
        assert path is not None and path.is_file()
        assert record is not None
        assert record["method"] == "gcc"
        assert record["compiler"] is None
        assert len(probes) == 1
    finally:
        _transactions.discard_staging(staging)


# --- no compiler needed --------------------------------------------------------


GOLDEN_TAILS = {
    "linux": ["-Wl,-z,defs"],
    "darwin": ["-Wl,-install_name,@rpath/librepro.so"],
    "win32": ["-Wl,--no-insert-timestamp", "-Wl,--disable-auto-image-base"],
    "freebsd": [],
}


@pytest.mark.parametrize("platform", sorted(GOLDEN_TAILS))
def test_build_argv_matches_the_documented_recipe(platform):
    """The golden copies of the recipe in docs/grammar_management.md."""
    head = ["/abs/gcc", "-shared", "-fPIC", "-O2", "-I", "src", "src/parser.c"]
    tail = ["-o", "/o/librepro.so", *GOLDEN_TAILS[platform]]
    with_scanner = _build_recipe.gcc_build_argv(
        "/abs/gcc", "repro", "/o/librepro.so", has_scanner=True, platform=platform
    )
    without = _build_recipe.gcc_build_argv(
        "/abs/gcc", "repro", "/o/librepro.so", has_scanner=False, platform=platform
    )
    assert with_scanner == [*head, "src/scanner.c", *tail]
    assert without == [*head, *tail]


@pytest.mark.parametrize("scanner", ["scanner.cc", "scanner.cpp"])
def test_gcc_route_declines_cxx_scanner_without_compiling(tmp_path, scanner):
    """A C++ scanner is declined before any process starts."""
    files = {"src/parser.c": "int x;\n", f"src/{scanner}": "// C++\n"}
    if scanner == "scanner.cc":
        files["src/scanner.c"] = "int y;\n"  # a C scanner beside it changes nothing
    source = _write_grammar(tmp_path / "tree-sitter-cxx", files)
    installer = GrammarInstaller(cache_dir=tmp_path / "cache")
    calls: list[list[str]] = []

    def run_staged(staging, argv, **kwargs):
        calls.append(argv)
        raise AssertionError("the gcc route started a process for a C++ scanner")

    installer._run_staged = run_staged  # type: ignore[method-assign]
    result = installer._build_with_gcc(
        "cxx",
        source,
        tmp_path / "libcxx.so",
        staging=object(),  # type: ignore[arg-type]
        compiler="/abs/gcc",
    )
    assert result == (
        False,
        f"C++ scanner (src/{scanner}): not built by the controlled route",
    )
    assert calls == []


@pytest.mark.parametrize("gcc_present", [True, False])
@pytest.mark.parametrize("family", ["gcc", "clang"])
def test_gcc_is_resolved_once_to_an_absolute_path(
    tmp_path, monkeypatch, gcc_present, family
):
    """One ``which``; its absolute path is argv[0] of the build and the probe."""
    root = tmp_path / "cache"
    installer, staging, source = _staged_fixture(root)
    which_calls: list[str] = []

    def which(name, *args, **kwargs):
        which_calls.append(name)
        return f"bin/{name}" if name == "cc" or gcc_present else None

    runs: list[tuple[str, list[str]]] = []

    def run_staged(staging_area, argv, *, what, **kwargs):
        runs.append((what, list(argv)))
        if what == "GCC build":
            Path(argv[argv.index("-o") + 1]).write_bytes(b"dummy library")
            return _transactions.StagedRun(0, "", "", False, True)
        return _transactions.StagedRun(0, f"{family} version 15.2.0\n", "", False, True)

    monkeypatch.setattr(core_module.shutil, "which", which)
    installer._run_staged = run_staged  # type: ignore[method-assign]
    try:
        ok, _path, error, record = installer._build_grammar(
            "repro", source, staging=staging
        )
    finally:
        monkeypatch.undo()
        _transactions.discard_staging(staging)
    assert ok, error
    expected = os.path.abspath(  # noqa: PTH100 - the installer's rule
        "bin/gcc" if gcc_present else "bin/cc"
    )
    assert [what for what, _ in runs] == ["GCC build", "Compiler version"]
    assert [argv[0] for _, argv in runs] == [expected, expected]
    assert runs[1][1] == [expected, "--version"]
    assert which_calls == (["gcc"] if gcc_present else ["gcc", "cc"]) + [
        "make",
        "tree-sitter",
    ]
    assert record is not None
    assert record["compiler"] == {
        "family": family,
        "version": "15.2.0",
        "banner": f"{family} version 15.2.0",
    }


def test_build_methods_run_gcc_then_make_then_tree_sitter(tmp_path, monkeypatch):
    """Order gcc, make, CLI; a success or an abort stops the loop."""
    identity = {"family": "gcc", "version": "1.2.3", "banner": "gcc (Fixed) 1.2.3"}
    monkeypatch.setattr(core_module.shutil, "which", lambda name, *a, **k: "/abs/gcc")
    abort = _StagedRunAbortedError(
        _transactions.StagedRun(None, "", "", True, True), "GCC build"
    )

    def probe_identity(*args, **kwargs):
        return dict(identity)

    def run(gcc_outcome, probe=probe_identity, label=None):
        root = tmp_path / f"cache-{label or gcc_outcome}"
        installer = GrammarInstaller(cache_dir=root)
        staging = _transactions.create_staging(root)
        calls: list[str] = []

        def method(name, outcome):
            def build(language, source_path, output_path, *, staging, **kwargs):
                calls.append(name)
                if outcome == "abort":
                    raise abort
                return (outcome == "ok"), (
                    None if outcome == "ok" else f"{name} failed"
                )

            return build

        monkeypatch.setattr(installer, "_build_with_gcc", method("gcc", gcc_outcome))
        monkeypatch.setattr(installer, "_build_with_make", method("make", "fail"))
        monkeypatch.setattr(
            installer, "_build_with_tree_sitter_cli", method("tree-sitter-cli", "fail")
        )
        monkeypatch.setattr(installer, "_probe_compiler", probe)
        try:
            source = staging.path("downloads") / "tree-sitter-order"
            source.mkdir()
            result = installer._build_grammar("order", source, staging=staging)
        finally:
            _transactions.discard_staging(staging)
        return calls, result

    calls, (ok, _path, error, record) = run("fail")
    assert calls == ["gcc", "make", "tree-sitter-cli"]
    assert (ok, record) == (False, None)
    assert error == "All build methods failed. Last error: tree-sitter-cli failed"

    calls, (ok, _path, error, record) = run("ok")
    assert calls == ["gcc"]
    assert ok, error
    assert record is not None
    assert record["method"] == "gcc"
    assert record["compiler"] == identity
    assert record["platform"].startswith(sys.platform + "-")

    calls, (ok, _path, error, record) = run("abort")
    assert calls == ["gcc"]
    assert (ok, record) == (False, None)
    assert error == "Build aborted: GCC build timed out"

    # gcc succeeds, then its probe aborts: the build aborts, no fallback runs.
    def probe_aborts(*args, **kwargs):
        raise _StagedRunAbortedError(
            _transactions.StagedRun(None, "", "", True, True), "Compiler version"
        )

    calls, (ok, _path, error, record) = run("ok", probe_aborts, "probe-abort")
    assert calls == ["gcc"]
    assert (ok, record) == (False, None)
    assert error is not None and error.startswith("Build aborted: "), error

    # gcc succeeds, then its probe raises anything else: still the gcc build,
    # with no compiler identity, and no fallback overwrites the library.
    def probe_raises(*args, **kwargs):
        raise RuntimeError("probe broke")

    calls, (ok, _path, error, record) = run("ok", probe_raises, "probe-raises")
    assert calls == ["gcc"]
    assert ok, error
    assert record is not None
    assert record["method"] == "gcc"
    assert record["compiler"] is None


@pytest.mark.parametrize(
    ("stdout", "family", "version"),
    [
        ("gcc (Ubuntu 15.2.0-16ubuntu1) 15.2.0\n", "gcc", "15.2.0"),
        ("gcc (Debian 12.2.0-14) 12.2.0 20220819\n", "gcc", "12.2.0"),
        (
            "gcc.exe (Rev2, Built by MSYS2 project) 15.2.0\r\nCopyright\r\n",
            "gcc",
            "15.2.0",
        ),
        (
            "gcc.exe (MinGW-W64 x86_64-ucrt-posix-seh, built by Brecht Sanders, r1) 16.2.0\n",
            "gcc",
            "16.2.0",
        ),
        ("gcc-14 (Homebrew GCC 14.2.0) 14.2.0\n", "gcc", "14.2.0"),
        (
            "Apple clang version 17.0.0 (clang-1700.0.13.5)\nTarget: arm64\n",
            "clang",
            "17.0.0",
        ),
        ("x86_64-w64-mingw32-gcc (GCC) 13-win32\n", "gcc", None),
    ],
)
def test_compiler_identity_parses_known_banners(stdout, family, version):
    identity = _build_recipe.compiler_identity(stdout)
    assert identity is not None
    banner = stdout.replace("\r", "").split("\n")[0].strip()
    assert identity == {"family": family, "version": version, "banner": banner}


@pytest.mark.parametrize("stdout", ["", None, "\r\n  \n"])
def test_compiler_identity_of_no_banner_is_none(stdout):
    assert _build_recipe.compiler_identity(stdout) is None


@pytest.mark.parametrize(
    "linked",
    [
        "source root",
        "src",
        "src/parser.c",
        "src/scanner.c",
        "src/tree_sitter",
        "src/tree_sitter/parser.h",
        "src/headers",
        "src/headers/extra.h",
    ],
)
@pytest.mark.parametrize("dangling", [False, True])
def test_gcc_route_declines_symlinked_source_before_process(tmp_path, linked, dangling):
    """Real links, including dangling links and nested headers, never compile."""
    source = tmp_path / "source"
    shutil.copytree(FIXTURE, source)
    _write_grammar(source, {"src/headers/extra.h": "/* header */\n"})
    path = source if linked == "source root" else source / linked
    target = tmp_path / "outside"
    directory = path.is_dir()
    path.rename(target)
    if dangling:
        if directory:
            shutil.rmtree(target)
        else:
            target.unlink()
    try:
        path.symlink_to(target, target_is_directory=directory)
    except OSError as error:
        if sys.platform == "win32" and error.winerror == 1314:
            if _policy_required():
                pytest.fail("Windows CI must permit symlink creation (WinError 1314)")
            pytest.skip("Windows symlink creation requires privilege (WinError 1314)")
        raise
    installer = GrammarInstaller(cache_dir=tmp_path / "cache")
    calls = []

    def run_staged(staging, argv, **kwargs):
        calls.append(argv)
        raise AssertionError("symlinked source started a process")

    installer._run_staged = run_staged  # type: ignore[method-assign]
    result = installer._build_with_gcc(
        "repro",
        source,
        tmp_path / "librepro.so",
        staging=object(),
        compiler="/abs/gcc",  # type: ignore[arg-type]
    )
    assert result == (
        False,
        f"Symlinked source ({linked}): not built by the controlled route",
    )
    assert calls == []


def test_symlink_decline_allows_fallback(tmp_path, monkeypatch):
    """The decline is defence in depth; admission still binds fallback bytes."""
    installer, staging, source = _staged_fixture(tmp_path / "cache")
    calls = []
    monkeypatch.setattr(_build_recipe, "symlinked_source", lambda root: "src")
    monkeypatch.setattr(core_module.shutil, "which", lambda name: "/abs/gcc")

    def make(*args, **kwargs):
        calls.append("make")
        return True, None

    def unexpected(*args, **kwargs):
        pytest.fail("declined compiler must not run or probe")

    monkeypatch.setattr(installer, "_run_staged", unexpected)
    monkeypatch.setattr(installer, "_build_with_make", make)
    try:
        ok, _, error, record = installer._build_grammar(
            "repro", source, staging=staging
        )
        assert ok, error
        assert calls == ["make"]
        assert record["method"] == "make"
        assert record["compiler"] is None
    finally:
        _transactions.discard_staging(staging)


_ADAPTERS = [
    "cli",
    "individual",
    "individual-mapped",
    "download",
    "download-cc",
    "manager",
    "combined",
]
if sys.platform in ("linux", "darwin"):
    _ADAPTERS.append("platform")


def _public_adapter(kind, root, monkeypatch):
    from chunker.build.builder import BuildSystem
    from chunker.grammar.builder import TreeSitterGrammarBuilder
    from chunker.grammar.download import GrammarDownloadManager
    from chunker.grammar_management.cli import ComprehensiveGrammarCLI
    from chunker.grammar_manager import GrammarManager

    common = root / "g"
    source = common / "tree-sitter-repro"
    shutil.copytree(FIXTURE, source)
    output = root / "o"
    output.mkdir()
    if kind in {"manager", "combined", "platform"}:
        zeta = common / "tree-sitter-zeta"
        shutil.copytree(FIXTURE, zeta)
        for path in zeta.rglob("*"):
            if path.is_file():
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        "tree_sitter_repro_", "tree_sitter_zeta_"
                    ),
                    encoding="utf-8",
                )
    if kind == "cli":
        tool = ComprehensiveGrammarCLI(root / "cache")
        tool.build_dir = output
        monkeypatch.setattr(
            tool, "_get_grammar_priority_order", lambda: [(common, None, None)]
        )
        # The discovery name is intentionally independent of the output name.
        monkeypatch.setattr(tool, "_handle_error", lambda *a, **kw: {})
        from click.testing import CliRunner

        with CliRunner().isolation():
            assert tool.build_grammar("tree-sitter-repro", force=True) == 0
        path = output / "tree_sitter_tree-sitter-repro.so"
    elif kind in {"individual", "individual-mapped", "combined"}:
        tool = TreeSitterGrammarBuilder()
        tool.set_source_directory(common)
        tool.set_build_directory(output)
        if kind in {"individual", "individual-mapped"}:
            language = "ocaml" if kind == "individual-mapped" else "repro"
            if kind == "individual-mapped":
                shutil.copytree(
                    source, common / "tree-sitter-ocaml" / "grammars" / "ocaml"
                )
            assert tool.build_individual(language), tool.get_build_log(language)
            path = output / f"{language}{tool._lib_extension}"
        else:
            assert tool.build(["zeta", "repro"]) == {"repro": True, "zeta": True}
            path = output / f"languages{tool._lib_extension}"
    elif kind.startswith("download"):
        (source / "src" / "scanner.cc").write_text("ignored sibling", encoding="utf-8")
        if kind == "download-cc":
            monkeypatch.setenv("CC", _installer_compiler())
        else:
            monkeypatch.delenv("CC", raising=False)
        from chunker.grammar_management import _build_tools

        compiler = (
            _build_tools.resolve_tool(os.environ["CC"])
            if "CC" in os.environ
            else _build_tools.resolve_tool("cc") or _build_tools.resolve_tool("gcc")
        )
        assert compiler is not None
        print(f"downloader selected compiler={compiler}")
        print(
            subprocess.run(
                [compiler, "--version"], capture_output=True, text=True, check=True
            ).stdout
        )
        if sys.platform == "win32":
            target = subprocess.run(
                [compiler, "-dumpmachine"], capture_output=True, text=True, check=True
            ).stdout.strip()
            print(f"downloader {compiler} -dumpmachine: {target}")
            assert "w64-mingw32" in target
        result = GrammarDownloadManager(root / "cache").compile_grammar(source, output)
        assert result.success, result.error_message
        path = result.output_path
    elif kind == "manager":
        tool = GrammarManager(root)
        tool._grammars_dir = common
        tool._lib_path = output / "my-languages.so"
        assert tool.compile_grammars(["zeta", "repro"]) == {"repro": True, "zeta": True}
        path = tool._lib_path
    else:
        tool = BuildSystem()
        tool._grammars_dir = common
        ok, info = tool.compile_grammars(
            ["zeta", "repro"],
            "linux" if sys.platform.startswith("linux") else "macos",
            output,
        )
        assert ok, info
        path = Path(info["libraries"]["combined"])
    assert path.is_file()
    return path


@pytest.mark.parametrize("adapter", _ADAPTERS)
def test_remaining_public_adapters_two_paths(tmp_path, monkeypatch, adapter):
    """Real public builds retain source strings without absolute source/output roots."""
    compiler = _installer_compiler()
    print(
        subprocess.run(
            [compiler, "--version"], capture_output=True, text=True, check=True
        ).stdout
    )
    paths = [
        _public_adapter(adapter, tmp_path / relative, monkeypatch) for relative in ROOTS
    ]
    blobs = [path.read_bytes() for path in paths]
    print(
        f"{adapter} compiler={compiler} raw_sha256={[sha256(blob).hexdigest() for blob in blobs]}"
    )
    prefix = (
        b"tree-sitter-repro/" if adapter in {"manager", "combined", "platform"} else b""
    )
    for path, blob in zip(paths, blobs):
        if sys.platform == "darwin":
            assert f"@rpath/{path.name}".encode() in blob, "missing stable install name"
        if sys.platform == "win32":
            assert _pe_time_date_stamp(blob) == 0, "PE TimeDateStamp must be zero"
        assert os.fsencode(tmp_path) not in blob, "absolute source/output root leaked"
        assert prefix + b"src/scanner.c" in blob
        assert prefix + b"src/tree_sitter/parser.h" in blob

    assert (
        sha256(blobs[0]).digest() == sha256(blobs[1]).digest()
    ), "public build is path-dependent"


if sys.platform in ("linux", "darwin"):

    def test_wheel_embedded_library_two_paths(tmp_path, monkeypatch):
        import zipfile
        from chunker.build.builder import BuildSystem

        _installer_compiler()
        monkeypatch.setenv("CHUNKER_WHEEL_LANGS", "repro")
        blobs = []
        for relative in ROOTS:
            root = tmp_path / relative
            common = root / "g"
            shutil.copytree(FIXTURE, common / "tree-sitter-repro")
            tool = BuildSystem()
            tool._grammars_dir = common
            ok, wheel = tool.build_wheel(
                "macos" if sys.platform == "darwin" else "linux", "cp314", root / "o"
            )
            assert ok
            with zipfile.ZipFile(wheel) as archive:
                names = [
                    n
                    for n in archive.namelist()
                    if n.endswith(("my-languages.so", "my-languages.dylib"))
                ]
                assert len(names) == 1
                blobs.append(archive.read(names[0]))
        assert sha256(blobs[0]).digest() == sha256(blobs[1]).digest()
        assert b"tree-sitter-repro/src/scanner.c" in blobs[0]
        assert os.fsencode(tmp_path) not in blobs[0]


@pytest.mark.parametrize(
    "adapter", [a for a in _ADAPTERS if a in {"manager", "combined", "platform"}]
)
def test_combined_duplicate_symbols_fail_all(tmp_path, adapter):
    from chunker.build.builder import BuildSystem
    from chunker.grammar.builder import TreeSitterGrammarBuilder
    from chunker.grammar_manager import GrammarManager

    _installer_compiler()
    common = tmp_path / "g"
    for language in ("repro", "duplicate"):
        shutil.copytree(FIXTURE, common / f"tree-sitter-{language}")
    languages = ["repro", "duplicate"]
    output = tmp_path / "o"
    output.mkdir()
    if adapter == "manager":
        tool = GrammarManager(tmp_path)
        tool._grammars_dir = common
        tool._lib_path = output / "my-languages.so"
        assert tool.compile_grammars(languages) == dict.fromkeys(languages, False)
    elif adapter == "combined":
        tool = TreeSitterGrammarBuilder()
        tool.set_source_directory(common)
        tool.set_build_directory(output)
        assert tool.build(languages) == dict.fromkeys(languages, False)
    else:
        tool = BuildSystem()
        tool._grammars_dir = common
        ok, info = tool.compile_grammars(
            languages, "macos" if sys.platform == "darwin" else "linux", output
        )
        assert not ok
        assert info["libraries"] == {}
        assert any("every requested member" in error for error in info["errors"])
