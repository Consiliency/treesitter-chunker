"""Contracts for the HYGIENE reachability reduction."""

import ast
import importlib
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = (
    "extractors",
    "testing",
    "integration",
    "error_handling",
    "deployment",
    "devenv",
    "distribution",
    "cicd",
    "monitoring",
)


def _imports(path: Path) -> list[ast.ImportFrom]:
    return [
        node
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.ImportFrom)
    ]


def test_false_reachability_edges_are_absent() -> None:
    assert all(
        node.module != "integration" for node in _imports(ROOT / "chunker/__init__.py")
    )
    assert all(
        not (node.module or "").startswith("error_handling")
        for node in _imports(ROOT / "chunker/grammar_management/cli.py")
    )
    assert all(
        not (node.module or "").startswith("chunker.cicd")
        for node in _imports(ROOT / "chunker/contracts/__init__.py")
    )


def test_audit_matches_deleted_packages_and_retained_error_handling() -> None:
    audit = (ROOT / "plans/hygiene-reachability-audit.txt").read_text()
    for candidate in CANDIDATES:
        assert f"{candidate}: deleted" in audit
        tracked = subprocess.run(
            ["git", "ls-files", f"chunker/{candidate}/**"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert not tracked
    assert (ROOT / "chunker/_internal/error_handling.py").is_file()
    importlib.import_module("chunker._internal.error_handling")


def test_surviving_contract_reexports_intact():
    """HYGIENE severed chunker.cicd but must keep surviving contract-layer APIs public."""
    from chunker.contracts import (
        CICDPipelineContract,
        CICDPipelineStub,
        CICDPipelineImpl,
    )

    assert CICDPipelineImpl is CICDPipelineStub
    assert issubclass(CICDPipelineStub, CICDPipelineContract)
