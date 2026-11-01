"""No tracked script, tool or test hardcodes the system temp root (treesitter-chunker#481).

Verification scratch belongs under the inherited disk ``TMPDIR``, created with
``tempfile`` or ``mktemp`` and removed when done. On the shared host the system
temp root is RAM-backed, and retained scratch there exhausted memory.

The scan covers tracked script, tool and test sources. It skips ``archive/``
(historical helpers kept as evidence), generated ``site/`` output, data under
``tests/fixtures/`` and the product package ``chunker/``. A line naming the
root fails unless it is a synthetic path label listed below that is never
created on disk.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = Path(__file__).resolve().relative_to(ROOT).as_posix()

SCRIPT_SUFFIXES = (".py", ".sh", ".bash", ".ps1", ".js", ".mjs", ".cjs", ".ts")
EXCLUDED_PREFIXES = ("archive/", "site/", "tests/fixtures/", "chunker/")

# Built from parts so this file never names the root itself.
SYSTEM_TMP = "/" + "tmp"
ROOT_PATTERN = re.compile(r"(?<![\w$.~])" + re.escape(SYSTEM_TMP) + r"(?![\w-])")

# (path, stripped line) -> occurrences. Each is a string label that nothing
# creates: chunk metadata, a cache-key field, a config value or a path
# asserted not to exist.
SYNTHETIC_LABELS = Counter(
    {
        (
            "spec_tests/test_codechunk_ids_backcompat.py",
            f'file_path="{SYSTEM_TMP}/x.py",',
        ): 2,
        ("spec_tests/test_xref_graph.py", f'file_path="{SYSTEM_TMP}/x.py",'): 1,
        (
            "tests/test_boundary_ir_incremental_cache.py",
            f'cache_dir="{SYSTEM_TMP}/cache",',
        ): 1,
        (
            "tests/test_cache.py",
            f'non_existent = Path("{SYSTEM_TMP}/non_existent_file.py")',
        ): 1,
        (
            "tests/test_codechunk_ids_backcompat.py",
            f'file_path="{SYSTEM_TMP}/x.py",',
        ): 1,
        (
            "tests/test_cross_module_errors.py",
            f'cache_context["context_data"]["cache_path"] = "{SYSTEM_TMP}/chunker_cache.db"',
        ): 1,
        (
            "tests/test_cross_module_errors.py",
            f'assert root_cause["context_data"]["cache_path"] == "{SYSTEM_TMP}/chunker_cache.db"',
        ): 1,
        (
            "tests/test_iface_public_chunk_text.py",
            f"# In-memory: default file_path is empty, not a {SYSTEM_TMP}/... temp name.",
        ): 1,
        ("tests/test_packing_hint.py", f'file_path="{SYSTEM_TMP}/x.py",'): 1,
        (
            "tests/test_parallel.py",
            f'non_existent = Path("{SYSTEM_TMP}/does_not_exist_12345.py")',
        ): 1,
        (
            "tests/test_plugin_system.py",
            f'config.plugin_dirs = [Path("{SYSTEM_TMP}/plugins")]',
        ): 1,
        ("tests/test_scale_graph_determinism.py", f'file_path="{SYSTEM_TMP}/x.py",'): 1,
        ("tests/test_xref_graph.py", f'file_path="{SYSTEM_TMP}/x.py",'): 1,
    }
)


def _tracked_sources() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        capture_output=True,
        check=True,
        cwd=ROOT,
        timeout=60,
    )
    return sorted(
        path
        for path in result.stdout.decode("utf-8").split("\0")
        if path.endswith(SCRIPT_SUFFIXES)
        and not path.startswith(EXCLUDED_PREFIXES)
        and path != THIS_FILE
    )


def _root_references(paths: list[str]) -> Counter[tuple[str, str]]:
    found: Counter[tuple[str, str]] = Counter()
    for path in paths:
        text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if ROOT_PATTERN.search(line):
                found[(path, line.strip())] += 1
    return found


def test_pattern_matches_root_references_only() -> None:
    for line in (
        f'Path("{SYSTEM_TMP}")',
        f"cat > {SYSTEM_TMP}/x.json",
        f'f"{SYSTEM_TMP}/fork-{{id}}.txt"',
        f'TMP="${{TMPDIR:-{SYSTEM_TMP}}}"',
        f"--user-data-dir={SYSTEM_TMP}/profile",
    ):
        assert ROOT_PATTERN.search(line), line
    for line in (
        '"$TMPDIR/run.jsonl"',
        "tempfile.gettempdir()",
        f"{SYSTEM_TMP}fs quota",
        f"/var{SYSTEM_TMP}/cache",
        f"$TMPDIR{SYSTEM_TMP}",
    ):
        assert not ROOT_PATTERN.search(line), line


def test_scan_covers_scripts_tools_and_tests() -> None:
    sources = _tracked_sources()
    for expected in (
        "scripts/run_ci_smoke.py",
        "tools/governed_scope.py",
        "tests/conftest.py",
        "api/examples/curl_examples.sh",
        ".claude/hooks/test_multi_instance.py",
        ".ai-dev-kit/skills/spawn/agent/fork_terminal.py",
    ):
        assert expected in sources


def test_no_tracked_script_tool_or_test_hardcodes_system_temp_root() -> None:
    found = _root_references(_tracked_sources())
    unexpected = sorted((found - SYNTHETIC_LABELS).elements())
    assert unexpected == [], (
        "Create scratch under the inherited TMPDIR with tempfile or mktemp and "
        "remove it when done (CONTRIBUTING.md)"
    )
    # A stale allowance would hide a future scratch use on the same line.
    assert sorted((SYNTHETIC_LABELS - found).elements()) == []
