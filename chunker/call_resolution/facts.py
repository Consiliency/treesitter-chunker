"""Per-file scope facts for opt-in call resolution (plan sections 4.6 and 5).

When ``call_resolution`` is not ``"name"``, symbol-fact extraction re-parses
each file with the bytes it already read and stores ``facts["scope_facts"]``.
Scope facts are never emitted. They are stored only in on-mode Boundary cache
records, whose keys carry the file family's fact version.

Schema (fact version ``"9"`` for the ``js`` family and ``"23"`` for
``python``; both analyzers are real):

``version``
    :data:`CALL_RESOLUTION_FACT_VERSIONS` for the file's language family, or
    ``None`` for a language no analyzer covers.
``language``
    The file's language, or ``None``.
``supported``
    ``False`` for a language no analyzer covers, an analyzer exception,
    ``RecursionError``, a parser initialization failure, a tree with
    errors, a JS/TS file that spells a name with a Unicode escape, or a
    Python file with a non-ASCII identifier or with indentation that depends
    on the width of a tab (section 5.3). An unsupported file never narrows, has no
    ``bindings`` and contributes nothing to other files.
``goal``
    JavaScript and TypeScript: ``"module"`` if the program has any top-level
    ``import`` or ``export`` statement, otherwise ``"script"``. Python:
    ``"module"``. ``None`` when unsupported.
``bindings``
    ``{"<callee_byte_start>:<callee_byte_end>": outcome}`` for every call fact
    of the file, keyed by its callee byte span (section 5.4). An outcome is
    ``{"outcome": "none", "reason": <reason>}``,
    ``{"outcome": "local", "proof": [[node_type, byte_start, byte_end], ...],
    "rules": [<group rule id>, ...]}`` (the declarations the group rule
    proves, section 7.4), or ``{"outcome": "import", "binding": {...}}``.
    A ``local`` outcome that lands on a script-goal top level also has
    ``"global": <name>``: the engine proves it only if no other file of the
    run declares that name as a script global (section 7.2).
    The JS/TS import binding is ``{"source": <specifier>, "name": <imported
    name, "default" or "*">, "form": "named" | "default" | "namespace"}``.
    The Python import binding is ``{"form": "import", "module": <dotted
    name>}`` for ``import m [as y]``, or ``{"form": "from", "module":
    <module, with any leading dots>, "name": <imported name>}``.
    A call whose callee span matches no node has no entry
    (``no-binding-fact``).
``script_globals``
    JavaScript and TypeScript: the sorted globals the file declares or may
    write (section 7.2). In a script, every name its top level binds, and
    every name it assigns with no declaration in scope (implicit globals).
    In a file of either goal, the names declared in ``declare global`` and
    the names written through the global object (``window.x =``,
    ``globalThis["x"] =``, ``self.x =``, ``global.x =``; ``this.x =`` where
    ``this`` may be the global object in a script). ``"*"`` when the file
    may write a global of any name: a computed key, the global object used
    as a value, or a code evaluator (``eval``, ``Function``, ``execScript``,
    a timer given source text). Empty for Python.
``exports``, ``module_bindings``
    Cross-file facts for later tiers; empty until an analyzer fills them.
``symbols``
    ``[[node_type, byte_start, byte_end, symbol_id], ...]``, one entry per
    symbol chunk of the file, in chunk order. The engine joins proof
    declarations to symbol IDs through this table (section 5.4).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from . import js_scope, py_scope
from .engine import language_family

logger = logging.getLogger(__name__)

# Per-language-family fact versions (section 4.6). A change to one family's
# per-file facts bumps only that family's version;
# tests/fixtures/call_resolution/scope_facts_digests.json pins a digest of the
# fixtures' facts per family, so a change without a bump fails.
# js "2": the JS/TS scope analyzer replaces the stub (plan PR 2).
# js "3": script globals, script-goal lookups, namespace merging and
# inherited ambient status (plan PR 3).
# js "4": t1.js_hoist, in its own change so it can be reverted alone (PR 3).
# js "5": the #691 panel fold (misparsed blocks, implicit globals in modules,
# exported namespaces merged, receiver ``this`` writes, more global-object
# names and code evaluators).
# A version number is never reused: reverting a change that altered the
# facts takes a new, higher version, so no cache record written under one
# set of facts is read under another. The digest test rejects a decrease.
# js "6": the president's #691 ruling (blocks glued to a following
# expression, ``static constructor()``, receiver ``this`` alias chains).
# js "7": the president's #691 re-check (``super`` writes, computed links
# in a receiver ``this`` chain).
# js "8": literal-key access equals dot access at every name-matching site
# (Codex 4652498471 on #691).
# js "9": ``Object``/``Reflect`` reached through a receiver ``this`` (C-1).
# python "2": the Python scope analyzer replaces the stub (plan PR 4).
# python "3": the #695 panel fold (metaclass namespaces, ``f_locals``,
# builtin shadowing, tab-width indentation, ``__main__``, literal attribute
# names, self-imports, ``X.modules[__name__]``, line continuations).
# python "4": the president's #695 ruling (private-name mangling, backslash
# continuations in indentation, submodule rebinding in ``__init__.py``,
# self-import gaps, parenthesized ``__name__``, ``WindowsError``). Any change
# to analyzer output bumps the version, whether or not digests move.
# python "5": the president's #695 re-check (one general fail-closed rule for
# self-reference and submodule rebinding at any depth).
# python "6": the re-check at f7f0b0bd (names matched whatever node spells
# them, raw non-identifier own names, ``..`` from a root ``__init__.py``,
# ``X[__name__]`` on any receiver, an unknown path fails closed).
# python "7": the re-check at 06f5dc32 (names, dotted paths and relative
# levels from tokens, not raw node text).
# python "8": Codex 4654363963 (every runtime spelling of a name recorded
# from class code, mangled ``_Class__x`` included).
# python "9": the re-check at 13c38360 (I-3: ``sys``/``__main__`` alias sets
# and their uses compare every runtime spelling).
# python "10": the re-check at eae66582 (J-3: class-body imports of sys or
# __main__, names a ``from __main__`` import binds).
# python "11": the re-check at f2b38014 (K-3: ``"__main__"`` constant
# strings; ``__mp_main__``; ``:`` separates string module paths).
# python "12": the re-check at 3b2d8fae (L-2: the ``__main__`` guard
# exemption narrowed).
# python "13": the re-check at 8006c72c (M-2: a positive allow-list for the
# module-level ``if __name__ == "__main__":`` guard).
# python "14": Codex 4655078224 (closure cells, code objects, ``ctypes`` and
# ``closure=`` make every lookup dynamic).
# python "15": the re-check at 606c689f (O-3: ``__builtins__`` and
# ``__self__`` as dynamic attributes; ``dis``, ``codeobj``,
# ``_get_code_object`` and ``monitoring`` make every lookup dynamic).
# python "16": the re-check at 8fd7c1a2 (P-2/P-3: ``builtins`` and ``bltns``
# as dynamic attributes; ``getstats`` and the ``inspect`` frame-locals
# helpers make every lookup dynamic).
# python "17": the re-check at 14e8f044 (Q-2: a name in an annotation proves
# nothing; Q-3: ``_code``, ``code_linenos``, ``curframe_locals``,
# ``call_annotate_function``, ``call_evaluate_function`` and
# ``__annotate__`` make every lookup dynamic).
# python "18": the re-check at a6734480 (S-2: a ``type`` statement's value
# proves nothing; S-3: ``__annotate_func__`` makes every lookup dynamic).
# python "19": Codex 4656123247 (callees, attribute callees and arguments
# classified after unwrapping parentheses).
# python "20": fold 18 (writer aliases, namespace mutators taken off their
# receiver, computed namespace writes, ``operator`` writers, ``|=``).
# python "21": fold 19 (E-19: computed writes closed at the write site;
# constant strings through comments and constant f-strings; unbound and
# by-name namespace mutators; more namespace aliases; unittest.mock patches).
# python "22": fold 20 (receiver-based patchers: any ``X.patch.object``/
# ``dict``/``multiple`` chain and pytest-mock fixtures' ``.patch``).
# python "23": fold 21 (E-20: namespace aliases read back as attributes,
# mock-module/pytest-mock aliases, stdlib resolver mentions, ``'__dict__'``
# subscript keys, ``X._sys.modules``).
CALL_RESOLUTION_FACT_VERSIONS: dict[str, str] = {"js": "9", "python": "23"}

ANALYZED_LANGUAGES = frozenset({"python", "javascript", "typescript", "tsx"})
# Extensions that make a JavaScript/TypeScript file an ES module.
_MODULE_SUFFIXES = frozenset({".mjs", ".mts"})

TIER1_NONE_REASONS = (
    "unbound",
    "parameter",
    "local-variable",
    "expression-bound",
    "self-binding",
    "reassigned",
    "block-function",
    "conditional",
    "builtin-shadow",
    "mixed-bindings",
    "class-scope-bound",
    "star-import",
    "dynamic-scope",
    "ambient",
    "bodyless",
    "non-callable",
    "namespace-merged",
    "script-global",
    "type-only",
    "enum-scope",
    "unmapped",
    "no-binding-fact",
)
TIER2_NONE_REASONS = (
    "external-module",
    "outside-root",
    "module-not-found",
    "unknown-variant",
    "ambiguous-extension",
    "dts-target",
    "export-not-found",
    "star-conflict",
    "namespace-export",
    "commonjs",
    "hop-limit",
    "cycle",
    "script-dir-shadow",
    "attr-submodule-conflict",
)
# Reasons that exist only at interim heads (section 7.6).
# ``script-goal-deferred`` and ``namespace-deferred`` existed only at the PR 2
# head; PR 3 replaced them. ``stub`` existed until both analyzers were real;
# PR 4 replaced the Python stub. None is a valid outcome any more.
INTERIM_NONE_REASONS: tuple[str, ...] = ()
KNOWN_NONE_REASONS = frozenset(
    TIER1_NONE_REASONS + TIER2_NONE_REASONS + INTERIM_NONE_REASONS
)
OUTCOME_KINDS = ("local", "import", "none")
SCOPE_FACT_KEYS = (
    "bindings",
    "exports",
    "goal",
    "language",
    "module_bindings",
    "script_globals",
    "supported",
    "symbols",
    "version",
)

Analyzer = Callable[[Any, bytes, str, Sequence[Mapping[str, Any]]], dict[str, Any]]
_ANALYZERS: dict[str, Analyzer] = {
    "js": js_scope.analyze,
    "python": py_scope.analyze,
}


def fact_version(language: str | None) -> str | None:
    """The scope-fact version for ``language``'s family, or ``None``."""
    if language not in ANALYZED_LANGUAGES:
        return None
    family = language_family(language)
    return CALL_RESOLUTION_FACT_VERSIONS.get(family) if family else None


def binding_key(byte_start: int, byte_end: int) -> str:
    """The ``bindings`` key for a callee byte span."""
    return f"{byte_start}:{byte_end}"


def unsupported_scope_facts(
    language: str | None,
    symbols: Sequence[Sequence[Any]] = (),
) -> dict[str, Any]:
    """Scope facts for a file that never narrows (section 5.3)."""
    return {
        "version": fact_version(language),
        "language": language,
        "supported": False,
        "goal": None,
        "bindings": {},
        "script_globals": [],
        "exports": {},
        "module_bindings": {},
        "symbols": [list(entry) for entry in symbols],
    }


def compute_scope_facts(
    *,
    language: str | None,
    source: bytes,
    call_facts: Sequence[Mapping[str, Any]],
    symbols: Sequence[Sequence[Any]],
    suffix: str = "",
    path: str = "",
) -> dict[str, Any]:
    """Re-parse ``source`` and return the file's scope facts.

    ``suffix`` is the file's lower-case extension: ``.mjs`` and ``.mts``
    files are always ES modules, whatever their syntax. ``path`` is the
    file's display path relative to the root (part of every cache key): a
    Python file that imports its own module is dynamic.

    ``source`` is the buffer symbol-fact extraction already read, so callee
    spans match the call facts. Python source with a lone CR is parsed through
    core's CR->LF copy, which keeps every byte offset. Every failure gives
    ``supported: false``; none is raised or recorded as an error, even with
    ``fail_fast`` (section 5.3).
    """
    fallback = unsupported_scope_facts(language, symbols)
    if language not in ANALYZED_LANGUAGES:
        return fallback
    family = language_family(language)
    analyzer = _ANALYZERS.get(family or "")
    if analyzer is None:  # pragma: no cover - every analyzed family has one
        return fallback
    try:
        from chunker.core import _lone_cr_parse_copy
        from chunker.parser import get_parser

        parser = get_parser(language)
        parse_copy = _lone_cr_parse_copy(source, language)
        tree = parser.parse(source if parse_copy is None else parse_copy)
        root = tree.root_node
        if root.has_error:
            logger.debug("call resolution: %s tree has errors", language)
            return fallback
        if family == "js" and suffix in _MODULE_SUFFIXES:
            partial = js_scope.analyze(
                root, source, language, call_facts, goal="module"
            )
        elif family == "python" and analyzer is py_scope.analyze:
            partial = py_scope.analyze(
                root,
                source,
                language,
                call_facts,
                path=path,
            )
        else:
            partial = analyzer(root, source, language, call_facts)
        # Normalizing and validating the analyzer's output is inside the
        # guard too: malformed output fails closed instead of raising.
        facts = {
            **fallback,
            "supported": True,
            "goal": partial.get("goal"),
            "bindings": dict(partial.get("bindings", {})),
            "script_globals": sorted(set(partial.get("script_globals", ()))),
            "exports": dict(partial.get("exports", {})),
            "module_bindings": dict(partial.get("module_bindings", {})),
        }
        if not valid_scope_facts(facts, language):
            logger.debug(
                "call resolution: %s analyzer returned malformed facts", language
            )
            return fallback
    except RecursionError:
        logger.debug("call resolution: %s analyzer hit RecursionError", language)
        return fallback
    except Exception as exc:  # noqa: BLE001 - fail closed (section 5.3)
        logger.debug("call resolution: %s analyzer failed: %r", language, exc)
        return fallback
    return facts


def _is_span_key(value: object) -> bool:
    if not isinstance(value, str):
        return False
    start, sep, end = value.partition(":")
    return bool(sep) and start.isdigit() and end.isdigit() and int(start) < int(end)


def _valid_declaration(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and isinstance(value[0], str)
        and bool(value[0])
        and type(value[1]) is int
        and type(value[2]) is int
        and 0 <= value[1] < value[2]
    )


def valid_outcome(value: object) -> bool:
    """Whether ``value`` is a well-formed ``bindings`` outcome."""
    if not isinstance(value, dict):
        return False
    kind = value.get("outcome")
    if not isinstance(kind, str):
        return False
    if kind == "none":
        reason = value.get("reason")
        return (
            set(value) == {"outcome", "reason"}
            and isinstance(reason, str)
            and reason in KNOWN_NONE_REASONS
        )
    if kind == "local":
        proof = value.get("proof")
        rules = value.get("rules")
        return (
            set(value) - {"global"} == {"outcome", "proof", "rules"}
            and isinstance(value.get("global", ""), str)
            and isinstance(proof, list)
            and bool(proof)
            and all(_valid_declaration(item) for item in proof)
            and isinstance(rules, list)
            and all(isinstance(rule, str) for rule in rules)
        )
    if kind == "import":
        return set(value) == {"outcome", "binding"} and isinstance(
            value.get("binding"), dict
        )
    return False


def valid_symbol_entry(value: object) -> bool:
    """Whether ``value`` is a well-formed ``symbols`` table entry."""
    return (
        isinstance(value, list)
        and len(value) == 4
        and _valid_declaration(value[:3])
        and isinstance(value[3], str)
        and bool(value[3])
    )


def valid_scope_facts(value: object, language: str | None) -> bool:
    """Whether ``value`` is well-formed scope facts for a ``language`` file.

    An on-mode cache record whose scope facts fail this check is a safe miss
    (section 4.4).
    """
    if not isinstance(value, dict) or set(value) != set(SCOPE_FACT_KEYS):
        return False
    if value["version"] != fact_version(language) or value["language"] != language:
        return False
    supported = value["supported"]
    if type(supported) is not bool:
        return False
    if supported and language not in ANALYZED_LANGUAGES:
        return False
    goals: tuple[str | None, ...] = ("module", "script") if supported else (None,)
    if value["goal"] not in goals:
        return False
    bindings = value["bindings"]
    if not isinstance(bindings, dict) or (bindings and not supported):
        return False
    if not all(
        _is_span_key(key) and valid_outcome(outcome)
        for key, outcome in bindings.items()
    ):
        return False
    script_globals = value["script_globals"]
    if not isinstance(script_globals, list) or not all(
        isinstance(name, str) for name in script_globals
    ):
        return False
    if not isinstance(value["exports"], dict) or not isinstance(
        value["module_bindings"], dict
    ):
        return False
    symbols = value["symbols"]
    return isinstance(symbols, list) and all(
        valid_symbol_entry(entry) for entry in symbols
    )
