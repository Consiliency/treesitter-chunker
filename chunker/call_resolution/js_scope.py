"""Scope analyzer for JavaScript, TypeScript and TSX (plan section 7.2).

This is the stub the engine ships with (plan section 5.1): every call has the
outcome ``none(stub)``, so the analyzer proves no binding and nothing
resolves. The caller still fails closed on a tree with errors before the
analyzer runs. The real scope chain replaces this stub in a later change.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

# Top-level statements that make a program an ES module (section 5.2).
_MODULE_STATEMENTS = frozenset({"import_statement", "export_statement"})


def program_goal(root: Any) -> str:
    """``"module"`` if any top-level statement imports or exports."""
    for child in root.named_children:
        if child.type in _MODULE_STATEMENTS:
            return "module"
    return "script"


def analyze(
    root: Any,
    source: bytes,
    language: str,
    call_facts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return partial scope facts: the goal and a ``none(stub)`` per call."""
    del source, language  # the stub reads only the tree's top level
    bindings = {
        f"{fact['callee_byte_start']}:{fact['callee_byte_end']}": {
            "outcome": "none",
            "reason": "stub",
        }
        for fact in call_facts
    }
    return {"goal": program_goal(root), "bindings": bindings}
