"""Scope analyzer for Python (plan section 7.3).

This is the stub the engine ships with (plan section 5.1): every call has the
outcome ``none(stub)``, so the analyzer proves no binding and nothing
resolves. The caller still fails closed on a tree with errors before the
analyzer runs. The real scope chain replaces this stub in a later change.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def analyze(
    root: Any,
    source: bytes,
    language: str,
    call_facts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return partial scope facts: the goal and a ``none(stub)`` per call."""
    del root, source, language  # the stub proves nothing
    bindings = {
        f"{fact['callee_byte_start']}:{fact['callee_byte_end']}": {
            "outcome": "none",
            "reason": "stub",
        }
        for fact in call_facts
    }
    return {"goal": "module", "bindings": bindings}
