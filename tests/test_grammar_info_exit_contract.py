"""Public ``grammar info``/``grammar diagnose`` exit status reflects health."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from chunker._internal import grammar_management
from chunker._internal.user_grammar_tools import UserGrammarTools
from chunker.cli import grammar_commands
from chunker.cli.__main__ import main
from tests.test_compiled_grammar_analysis_contract import (
    FIXTURE,
    SOURCE,
    _compile_probe_fixture,
    trusted_artifacts,
)

ROOT = Path(__file__).resolve().parents[1]
LANGUAGE = "issue156lang"
UNAPPROVED_BYTES = b"not a grammar"
EMOJI = {
    "healthy": "✅",
    "corrupted": "❌",
    "missing": "⚠️",
    "incompatible": "⚠️",
}


def require(condition, name):
    if not condition:
        raise AssertionError(name)


def _run_main(monkeypatch, capsys, argv, tools):
    monkeypatch.setattr(grammar_commands, "get_grammar_tools", lambda *_args: tools)
    monkeypatch.setattr(sys, "argv", ["chunker", *argv])
    code = main()
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _isolated_tools(tmp_path, *, trusted=None):
    build_dir = tmp_path / "build"
    sources_dir = tmp_path / "sources"
    build_dir.mkdir(exist_ok=True)
    sources_dir.mkdir(exist_ok=True)
    return UserGrammarTools(build_dir, sources_dir, trusted_artifacts=trusted)


def _mock_tools(status):
    tools = Mock()
    tools.get_grammar_info.return_value = {
        "language": LANGUAGE,
        "health": Mock(status=status, issues=[], recommendations=[]),
        "compatibility": Mock(
            tree_sitter_version="0.26.0",
            system_architecture="x86_64",
            os_platform="Linux",
            compilation_date=None,
            compatibility_score=1.0,
        ),
        "recovery_plan": None,
        "source_info": None,
    }
    return tools


def test_require_is_active_under_current_optimization():
    with pytest.raises(AssertionError, match="^live-oracle$"):
        require(False, "live-oracle")


def _seed_missing(build_dir):
    return None


def _seed_corrupted(build_dir):
    (build_dir / f"{LANGUAGE}.so").write_bytes(b"")


def _seed_unapproved(build_dir):
    (build_dir / f"{LANGUAGE}.so").write_bytes(UNAPPROVED_BYTES)


NONHEALTHY_CASES = {
    "missing": (
        _seed_missing,
        None,
        ["Status: ⚠️ missing", "🛠️ Recovery Plan:"],
    ),
    "corrupted": (
        _seed_corrupted,
        # Rule 3: an unpinned candidate is untrusted before any check.
        {LANGUAGE: {"sha256": "0" * 64}},
        ["Status: ❌ corrupted", "Native admission failed: empty"],
    ),
    "untrusted": (
        _seed_unapproved,
        None,
        [
            "Status: ⚠️ incompatible",
            "Native admission failed: untrusted",
            "Supply an independently approved SHA-256 provenance pin",
        ],
    ),
    "integrity_mismatch": (
        _seed_unapproved,
        {LANGUAGE: {"sha256": "0" * 64}},
        [
            "Status: ⚠️ incompatible",
            "Native admission failed: integrity_mismatch",
        ],
    ),
}


@pytest.mark.parametrize("case", sorted(NONHEALTHY_CASES))
def test_nonhealthy_grammar_info_is_unsuccessful_and_reports(
    tmp_path, monkeypatch, capsys, case
):
    seed, trusted, expected_lines = NONHEALTHY_CASES[case]
    seed(_isolated_tools(tmp_path).build_dir)
    results = {
        command: _run_main(
            monkeypatch,
            capsys,
            ["grammar", command, LANGUAGE],
            _isolated_tools(tmp_path, trusted=trusted),
        )
        for command in ("info", "diagnose")
    }

    info_code, info_out, info_err = results["info"]
    for line in expected_lines:
        require(line in info_out, f"{case}: report line {line!r}")
    require("Error getting grammar info" not in info_err, f"{case}: info stderr")
    diagnose_code, diagnose_out, diagnose_err = results["diagnose"]
    header = f"🔍 Diagnosing grammar for {LANGUAGE}...\n"
    require(diagnose_out.startswith(header), f"{case}: diagnose header")
    require(
        diagnose_out[len(header) :] == info_out,
        f"{case}: diagnose report equals info report",
    )
    require("Error" not in diagnose_err, f"{case}: diagnose stderr")
    require(info_code == 1, f"{case}: info exit {info_code!r}")
    require(diagnose_code == 1, f"{case}: diagnose exit {diagnose_code!r}")


def test_grammar_info_uses_single_diagnosis(tmp_path, monkeypatch, capsys):
    tools = _isolated_tools(tmp_path)
    calls = {"factory": 0, "info": 0, "diagnose": 0, "probe": 0}
    original_info = tools.get_grammar_info
    original_diagnose = tools.manager.diagnose_grammar_issues
    original_probe = grammar_management.probe_native_grammar

    def factory(*_args):
        calls["factory"] += 1
        return tools

    def counted_info(language):
        calls["info"] += 1
        return original_info(language)

    def counted_diagnose(language):
        calls["diagnose"] += 1
        return original_diagnose(language)

    def counted_probe(*args, **kwargs):
        calls["probe"] += 1
        return original_probe(*args, **kwargs)

    monkeypatch.setattr(tools, "get_grammar_info", counted_info)
    monkeypatch.setattr(tools.manager, "diagnose_grammar_issues", counted_diagnose)
    monkeypatch.setattr(grammar_management, "probe_native_grammar", counted_probe)
    monkeypatch.setattr(grammar_commands, "get_grammar_tools", factory)
    monkeypatch.setattr(sys, "argv", ["chunker", "grammar", "info", LANGUAGE])

    code = main()
    out = capsys.readouterr().out

    require("Status: ⚠️ missing" in out, "missing report")
    # Rule 3: a candidate that does not exist is reported missing without
    # calling the probe.
    require(
        calls == {"factory": 1, "info": 1, "diagnose": 1, "probe": 0},
        f"single observation counts {calls!r}",
    )
    require(code == 1, f"exit {code!r}")


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("healthy", 0),
        ("missing", 1),
        ("corrupted", 1),
        ("incompatible", 1),
        ("unknown", 1),
        ("Healthy", 1),
        ("healthy ", 1),
        ("", 1),
    ],
)
def test_exit_mapping_is_exact_on_reported_health(
    monkeypatch, capsys, status, expected
):
    tools = _mock_tools(status)

    code, out, err = _run_main(
        monkeypatch, capsys, ["grammar", "info", LANGUAGE], tools
    )

    tools.get_grammar_info.assert_called_once_with(LANGUAGE)
    status_line = f"Status: {EMOJI.get(status, '❓')} {status}\n"
    require(status_line in out, f"printed status line {status_line!r}")
    require(err == "", f"stderr {err!r}")
    require(code == expected, f"{status!r}: exit {code!r} != {expected!r}")


def test_unexpected_error_returns_one_without_report(monkeypatch, capsys):
    tools = Mock()
    tools.get_grammar_info.side_effect = RuntimeError("boom")

    code, out, err = _run_main(
        monkeypatch, capsys, ["grammar", "info", LANGUAGE], tools
    )

    require(out == "", f"stdout {out!r}")
    require(err == "❌ Error getting grammar info: boom\n", f"stderr {err!r}")
    require(code == 1, f"exit {code!r}")


def test_cli_factory_supplies_no_implicit_pins(tmp_path, monkeypatch, capsys):
    project_root = tmp_path / "project"
    module_file = project_root / "chunker" / "cli" / "grammar_commands.py"
    build_dir = project_root / "chunker" / "data" / "grammars" / "build"
    build_dir.mkdir(parents=True)
    artifact = build_dir / f"{LANGUAGE}.so"
    artifact.write_bytes(UNAPPROVED_BYTES)
    monkeypatch.setattr(grammar_commands, "__file__", str(module_file))

    probes = []
    original_probe = grammar_management.probe_native_grammar

    def recording_probe(path, language, *, provenance, **kwargs):
        probes.append((Path(path), language, provenance))
        return original_probe(path, language, provenance=provenance, **kwargs)

    monkeypatch.setattr(grammar_management, "probe_native_grammar", recording_probe)

    tools = grammar_commands.get_grammar_tools()
    require(isinstance(tools, UserGrammarTools), "actual factory type")
    require(tools.build_dir == build_dir, f"factory build dir {tools.build_dir}")
    require(
        tools.manager.trusted_artifacts == {},
        f"implicit pins {tools.manager.trusted_artifacts!r}",
    )

    monkeypatch.setattr(sys, "argv", ["chunker", "grammar", "info", LANGUAGE])
    code = main()
    out = capsys.readouterr().out

    # Rule 3: with no pin the probe is never called and nothing is opened.
    require(probes == [], f"probe observed {probes!r}")
    require("Status: ⚠️ incompatible" in out, "untrusted status")
    require("Native admission failed: untrusted" in out, "untrusted reason")
    require(artifact.read_bytes() == UNAPPROVED_BYTES, "seeded bytes unchanged")
    require(code == 1, f"exit {code!r}")


@pytest.mark.parametrize("flags", [[], ["-O"]], ids=["normal", "optimized"])
def test_module_entry_exit_status_for_missing_grammar(flags):
    environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    optimize = subprocess.run(
        [sys.executable, *flags, "-c", "import sys; print(sys.flags.optimize)"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    require(optimize.stdout.strip() == ("1" if flags else "0"), "optimize flag")

    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            *flags,
            "-m",
            "chunker.cli",
            "grammar",
            "info",
            "issue156_absent_language",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    require("Status: ⚠️ missing" in result.stdout, f"stdout {result.stdout!r}")
    require("Error getting grammar info" not in result.stderr, "stderr error")
    require("Traceback" not in result.stderr, f"stderr {result.stderr!r}")
    require(result.returncode == 1, f"exit {result.returncode!r}")


def test_pinned_healthy_grammar_info_succeeds(tmp_path, monkeypatch, capsys):
    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    results = {}
    for command in ("info", "diagnose"):
        workspace = tmp_path / command
        workspace.mkdir()
        build_dir = workspace / "build"
        build_dir.mkdir()
        so_file = build_dir / "baml.so"
        so_file.write_bytes(library.read_bytes())
        subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                "import sys; from pathlib import Path; "
                "sys.path.insert(0, sys.argv[1]); "
                "from chunker.grammar_management.core import load_compiled_grammar; "
                "root = load_compiled_grammar(Path(sys.argv[2]), 'baml')"
                ".parse(Path(sys.argv[3]).read_bytes()).root_node; "
                "raise SystemExit(0 if root.type == 'source_file' "
                "and not root.has_error else 3)",
                str(ROOT),
                str(so_file),
                str(FIXTURE),
            ],
            check=True,
            capture_output=True,
            timeout=20,
        )
        tools = UserGrammarTools(
            build_dir,
            workspace / "sources",
            trusted_artifacts=trusted_artifacts(so_file),
        )
        results[command] = _run_main(
            monkeypatch, capsys, ["grammar", command, "baml"], tools
        )
        require(so_file.read_bytes() == library.read_bytes(), "fixture unchanged")

    for command, (code, out, err) in results.items():
        require("Status: ✅ healthy" in out, f"{command}: healthy report")
        require("Recovery Plan" not in out, f"{command}: no recovery plan")
        require("Error" not in err, f"{command}: stderr {err!r}")
        require(code == 0, f"{command}: exit {code!r}")
