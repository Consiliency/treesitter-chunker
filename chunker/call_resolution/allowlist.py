"""The binding allow-list (plan section 7.5, ruling A5).

Every named node kind of each pinned grammar (JavaScript, TypeScript, TSX and
Python) gets one classification:

- ``handled``: the analyzer understands the binding it introduces, with its
  binding class;
- ``ignored``: it introduces no value binding the lookup needs, with a reason
  (labels, for example);
- ``fail-closed``: a lookup that meets it gives ``none(unmapped)``;
- ``non-binding``: it cannot introduce a binding.

An analyzer consults :func:`classify` for every declaration-like node it
meets. A kind with no entry is treated as ``fail-closed``, so a grammar bump
can never add an unreviewed binding form that narrows an edge.
``tests/test_call_resolution_allowlist.py`` enumerates the kinds of each loaded
``Language`` and fails on any unclassified kind of a reviewed grammar.

This is the scaffold the engine ships with. The analyzers are stubs at this
head and consult nothing, so no grammar is reviewed yet; each analyzer change
adds its grammars' complete classification and lists them in
:data:`REVIEWED_LANGUAGES`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

HANDLED = "handled"
IGNORED = "ignored"
FAIL_CLOSED = "fail-closed"
NON_BINDING = "non-binding"
CLASSIFICATIONS = (HANDLED, IGNORED, FAIL_CLOSED, NON_BINDING)

PINNED_GRAMMARS = ("javascript", "typescript", "tsx", "python")


@dataclass(frozen=True)
class Entry:
    """One node kind's classification."""

    classification: str
    # The binding class for ``handled`` kinds (for example ``"symbol"``,
    # ``"parameter"`` or ``"local-variable"``), or the reason for ``ignored``
    # and ``fail-closed`` kinds.
    detail: str = ""


# {grammar: {node kind: Entry}}. Empty until an analyzer change reviews a
# grammar.
ALLOWLIST: dict[str, dict[str, Entry]] = {language: {} for language in PINNED_GRAMMARS}

# Grammars whose every named node kind must be classified.
REVIEWED_LANGUAGES: frozenset[str] = frozenset()

_UNCLASSIFIED = Entry(FAIL_CLOSED, "unclassified")


def classify(language: str, kind: str) -> Entry:
    """The entry for ``kind``; an unclassified kind fails closed."""
    return ALLOWLIST.get(language, {}).get(kind, _UNCLASSIFIED)


def named_node_kinds(language: str) -> frozenset[str]:
    """Every visible named node kind of the loaded ``language`` grammar.

    Read from the loaded ``Language``, so no grammar sources are needed.
    """
    from chunker.parser import get_parser

    loaded = get_parser(language).language
    if loaded is None:  # pragma: no cover - get_parser always sets one
        msg = f"no language loaded for {language}"
        raise RuntimeError(msg)
    return frozenset(
        str(loaded.node_kind_for_id(kind_id))
        for kind_id in range(loaded.node_kind_count)
        if loaded.node_kind_is_named(kind_id) and loaded.node_kind_is_visible(kind_id)
    )


def unclassified_kinds(
    kinds: Iterable[str],
    entries: Mapping[str, Entry],
) -> list[str]:
    """Kinds with no entry, sorted."""
    return sorted(kind for kind in set(kinds) if kind not in entries)


def unknown_entries(
    kinds: Iterable[str],
    entries: Mapping[str, Entry],
) -> list[str]:
    """Entries naming no kind of the grammar (typos, removed kinds), sorted."""
    known = set(kinds)
    return sorted(kind for kind in entries if kind not in known)


def invalid_entries(entries: Mapping[str, Entry]) -> list[str]:
    """Entries with an unknown classification or a missing detail, sorted."""
    return sorted(
        kind
        for kind, entry in entries.items()
        if entry.classification not in CLASSIFICATIONS
        or (entry.classification != NON_BINDING and not entry.detail)
    )
