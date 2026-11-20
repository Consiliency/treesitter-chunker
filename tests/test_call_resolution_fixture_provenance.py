"""Provenance of the call-resolution fixture trees (treesitter-chunker#682, PR 0).

Every copied or authored file under ``tests/fixtures/call_resolution`` is listed
in ``provenance.json`` with its sha256 (plan section 10.1):

- Greenfield's round-1 trees, byte-for-byte, checked against the lines of
  Greenfield's evidence manifest (sha256 ``40575a9b...a1e46``);
- the executive's probe tree, checked against the hashes in plan section 10.1;
- the plan author's authored trees, plus the two PR 0 trees from the final
  plan revision.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "call_resolution"
PROVENANCE = json.loads((FIXTURES / "provenance.json").read_text(encoding="utf-8"))
TREE_ROOTS = ("greenfield-r1", "probe-r9", "authored")

GREENFIELD_MANIFEST_SHA256 = (
    "40575a9bd9612fd1d307dda1e8e94f0ca7af5dff19659ca45cbb7fad649a1e46"
)
PROBE_EVIDENCE_SHA256SUMS_SHA256 = (
    "e1e0b01cba9771440c3b9b462c276838b3f6a6f9b1769962adf553d9f6aa250e"
)
# Plan section 10.1: the probe files' hashes, computed for the plan.
PROBE_SHA256 = {
    "pkg/over.ts": "251c363f322d24c867a41c94def6dce86cf2fe2468eda7422d388623928c9446",
    "pkg/svc.ts": "a373e3684282efc21a9005b1f9a543f3b78811bb0366159559e2667a274f58eb",
    "pkg/svc.tsx": "2906c06b6c7bdc8388a58b6718a1f0533c3afa37768ef8dc0af5b30e9b5dbf8f",
    "pkg/use.ts": "c7af3463aeef0a153d9638a251bc6a0e0b7147ec554c1ea03d6f4802658a354c",
    "py/a.py": "b6631639de17fb869c43278f858c465cc5b71c8ec51c8c25d803905361f8a544",
    "py/b.py": "80db5c431a8c630a959c421fba66ac80327fae4b813ada82ba2deae5c8d4532c",
    "py/c.py": "bd7c3914703ec6fa39ca98113d2534841181032b80820ebc7c9d66cb8bcdb382",
    "py/pkg/__init__.py": (
        "11a2d0ad935bd347586d68821e82c9dc8bbd0f324f9ed572ea7c732490b9241b"
    ),
    "py/pkg.py": "76adf090c7316f6da950398ec0da093577f5fce1e621fdc21c29fd41a307fccd",
    "py/redef.py": "98a171ca61216a4f8d23b864733e4ce8f169744319cc37b11715ebe60d44ae66",
}
GREENFIELD_TREES = {
    "clo-go",
    "clo-kotlin",
    "clo-rust",
    "py-sameline",
    "r9-py",
    "r9-ts",
    "r9b-py",
    "rt-cpp",
    "rt-go",
    "rt-java",
    "rt-js",
    "rt-kotlin",
    "rt-pycond",
    "rt-pyrec",
    "rt-rust",
    "rt-tsclass",
}
# The two trees the final plan revision added (Codex review of #683).
PR0_AUTHORED_TREES = {"py-ancestor-module-shadow", "py-nonlocal-rebind"}
AUTHORED_TREE_COUNT = 106 + len(PR0_AUTHORED_TREES)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture_files() -> dict[str, Path]:
    return {
        path.relative_to(FIXTURES).as_posix(): path
        for top in TREE_ROOTS
        for path in sorted((FIXTURES / top).rglob("*"))
        if path.is_file()
    }


def test_every_fixture_file_matches_its_recorded_sha256() -> None:
    files = _fixture_files()
    recorded = PROVENANCE["files"]
    assert sorted(files) == sorted(recorded)
    mismatched = sorted(
        name
        for name, path in files.items()
        if _sha256(path) != recorded[name]["sha256"]
    )
    assert mismatched == []


def test_every_file_names_a_known_source() -> None:
    sources = set(PROVENANCE["sources"])
    assert sources == {"greenfield-r1", "probe-r9", "authored", "authored-pr0"}
    for name, entry in PROVENANCE["files"].items():
        assert entry["source"] in sources, name


def test_greenfield_trees_match_the_greenfield_manifest() -> None:
    source = PROVENANCE["sources"]["greenfield-r1"]
    assert source["source_manifest_sha256"] == GREENFIELD_MANIFEST_SHA256
    manifest_lines = source["manifest_lines"]
    copied = {
        name: entry
        for name, entry in PROVENANCE["files"].items()
        if entry["source"] == "greenfield-r1"
    }
    assert len(manifest_lines) == len(copied) == 18
    for name, entry in copied.items():
        tree_path = name.removeprefix("greenfield-r1/")
        assert entry["source_path"] == f"r1/trees/{tree_path}"
        assert manifest_lines[entry["source_path"]] == entry["sha256"], name
    trees = {path.name for path in (FIXTURES / "greenfield-r1").iterdir()}
    assert trees == GREENFIELD_TREES


def test_probe_tree_matches_the_plan_hashes() -> None:
    source = PROVENANCE["sources"]["probe-r9"]
    assert source["evidence_sha256sums_sha256"] == PROBE_EVIDENCE_SHA256SUMS_SHA256
    files = {
        name.removeprefix("probe-r9/"): _sha256(path)
        for name, path in _fixture_files().items()
        if name.startswith("probe-r9/")
    }
    assert files == PROBE_SHA256


def test_authored_trees() -> None:
    trees = {path.name for path in (FIXTURES / "authored").iterdir() if path.is_dir()}
    assert len(trees) == AUTHORED_TREE_COUNT
    assert trees >= PR0_AUTHORED_TREES
    for name, entry in PROVENANCE["files"].items():
        if not name.startswith("authored/"):
            continue
        tree = name.split("/")[1]
        expected = "authored-pr0" if tree in PR0_AUTHORED_TREES else "authored"
        assert entry["source"] == expected, name


def test_no_generated_files_inside_fixture_trees() -> None:
    stray = sorted(
        name
        for name in _fixture_files()
        if "__pycache__" in name or name.endswith((".pyc", ".pyo"))
    )
    assert stray == []


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_no_fixture_file_is_git_ignored() -> None:
    """``ts-skipped-dir/dist/`` must not fall under the repository's ``dist/`` rule."""
    if not (ROOT / ".git").exists():
        pytest.skip("not a Git checkout")
    names = [f"tests/fixtures/call_resolution/{name}" for name in _fixture_files()]
    assert "tests/fixtures/call_resolution/authored/ts-skipped-dir/dist/t.ts" in names
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        input="\n".join(names) + "\n",
        capture_output=True,
        check=False,
        cwd=ROOT,
        text=True,
        timeout=60,
    )
    # Exit code 1 means no path is ignored.
    assert result.returncode == 1, result.stdout + result.stderr
