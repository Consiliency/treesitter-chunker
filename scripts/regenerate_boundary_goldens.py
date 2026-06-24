#!/usr/bin/env python3
"""Regenerate the canonical Boundary IR golden snapshots.

This is the ONE sanctioned way the committed goldens under
``tests/fixtures/boundary_ir/golden/`` change. Any intentional Boundary IR
change must be made here and reviewed as a golden diff in the PR; the
determinism gate (``tests/test_boundary_ir_golden_snapshots.py`` +
``tests/test_boundary_ir_determinism.py``) makes *unintended* changes fail
loudly in CI.

It MUST be run on the pinned, ABI-paired stack (tree_sitter 0.25 /
tree-sitter-language-pack 0.9). Running it twice produces no git diff: output is
byte-stable (``sort_keys`` + fixed indent), the volatile ``run.tool_version`` is
normalized to a placeholder, and the IR's other volatile fields (timestamps,
absolute roots) are already canonicalized by ``extract_boundary_ir`` /
``normalize_ir_for_golden`` -- so goldens never embed an absolute path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Run from the repository root so the repo-relative FIXTURE_ROOT / GOLDEN_ROOT
# paths in tests.boundary_ir_conformance resolve, and import that module as the
# single source of truth for the language list + normalization.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tests.boundary_ir_conformance import (  # noqa: E402
    GOLDEN_ROOT,
    SUPPORTED_BOUNDARY_LANGUAGES,
    assert_grammar_runtime_pins,
    extract_fixture_ir,
    normalize_ir_for_golden,
)


def _golden_text(language: str) -> str:
    """Return the byte-stable on-disk golden representation for a language."""
    normalized = normalize_ir_for_golden(extract_fixture_ir(language))
    # Mirror the committed goldens exactly: 2-space indent, sorted keys, trailing
    # newline. sort_keys + fixed indent make the bytes deterministic across runs.
    return json.dumps(normalized, indent=2, sort_keys=True) + "\n"


def main() -> int:
    # Fail closed before writing anything if the stack drifted off-pin -- we must
    # never bake goldens on an unpinned grammar/runtime.
    assert_grammar_runtime_pins()

    golden_root = REPO_ROOT / GOLDEN_ROOT
    golden_root.mkdir(parents=True, exist_ok=True)

    print("Regenerating Boundary IR goldens (pinned stack):")
    for language in SUPPORTED_BOUNDARY_LANGUAGES:
        text = _golden_text(language)
        path = golden_root / f"{language}.json"
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        path.write_text(text, encoding="utf-8")
        node_count = json.loads(text)["metrics"]["nodes_total"]
        status = "unchanged" if existing == text else "updated"
        print(f"- {language:<11} nodes={node_count:<3} {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
