"""Per-file scope facts for opt-in call resolution (plan sections 4.6 and 5).

When ``call_resolution`` is not ``"name"``, symbol-fact extraction re-parses
each file with the bytes it already read and stores ``facts["scope_facts"]``.
Scope facts are never emitted. They are stored only in on-mode Boundary cache
records, whose keys carry the file family's fact version.

Schema (fact version ``"23"`` for the ``js`` family and ``"44"`` for
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
    name, "default" or "*">, "form": "named" | "default" | "namespace"}``,
    with the specifier and a quoted name decoded exactly (a literal that
    does not decode binds ``none(unmapped)``), plus ``"attributes": "with"``
    for an import with attributes and ``"member": <name>`` on the outcome of
    a two-segment member callee ``ns.f()``.
    The Python import binding is ``{"form": "import", "module": <dotted
    name>, "bound": <the module the bound name denotes>}`` for ``import m
    [as y]`` (``import a.b`` binds ``a``, ``import a.b as y`` binds
    ``a.b``), or ``{"form": "from", "module": <module, with any leading
    dots>, "name": <imported name>}``.
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
    JavaScript and TypeScript: the Tier 2 module facts of
    :mod:`.js_modules` (the export table; star exports, CommonJS reach,
    ``opaque`` and the modules the file may write). Python: the Tier 2
    module facts of :mod:`.py_modules` (every module-scope name's Tier 1
    module lookup; imports, module-object uses, acquisitions, stars, dotted
    strings, run-wide causes, parse hazards, import groups and member
    chains). Empty for an unsupported file.
``symbols``
    ``[[node_type, byte_start, byte_end, symbol_id], ...]``, one entry per
    symbol chunk of the file, in chunk order. The engine joins proof
    declarations to symbol IDs through this table (section 5.4).
"""

from __future__ import annotations

import logging
import re
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
# js "10": Tier 2 module facts (plan PR 5): the export table, star exports,
# CommonJS reach and taints; import specifiers and quoted names decoded
# exactly; the member of a namespace member call.
# js "11": PR 5 fold 1 (import-binding writes taint, ``this`` in exports and
# at module level, verified namespace members, use-site lookups for
# module-system names, run-wide causes, text scans of unparsed files,
# symlinked files, cooked templates).
# js "12": PR 5 fold 2 (O-2): every static specifier of a file
# (``module_bindings["imports"]``) for the promotion fixpoint.
# js "13": PR 5 fold 3: closed allow-lists for ``module`` imports
# (``builtinModules``, ``isBuiltin``), ``createRequire`` local require
# functions (literal calls taint) and ``.constructor`` positions.
# js "14": PR 5 fold 4 (createRequire bases, test-framework module mocks,
# ``import.meta.glob`` and ``uncomputable`` edges).
# js "15": PR 5 fold 5 (P5-13: ``__filename`` and ``import.meta`` bases
# unwritten and unbound; ``filename_taints``).
# js "16": PR 5 fold 6 (P5-20: ``filename_taints`` always go to the
# engine's writer check, with no CommonJS shortcut).
# js "17": PR 5 fold 8 (the lexer-level text scan of unparsed files).
# js "18": PR 5 fold 9 (E5-7: no text scan, an unparsed JS/TS file has
# empty ``module_bindings``; P5-44: module-level ``arguments`` uses).
# js "19": PR 5 fold 10 (P5-47 unparsed on lone CR, LS/PS or HTML-like
# comments; P5-48 module-scope ``arguments`` declarations; P5-49 static
# class members are module level).
# js "20": PR 5 fold 11 (P5-50: in JavaScript, a ``<!--`` in code, or a
# ``-->`` in code with only whitespace and comments before it on its line,
# makes the file unparsed).
# js "21": treesitter-chunker#694: property-writer calls look through
# parentheses and commas at every level (``(0, Object.assign).call(null,
# this, …)``, ``(0, Object).assign``), nested ``.call``/``.apply``/``.bind``
# and a bound writer called later (``Object.assign.bind(null)(this, …)``),
# ``Reflect.apply(Object.assign, null, [this, …])`` and comments between
# arguments; each such call on a receiver ``this`` now gives ``*``. The
# positional reading of "20" still runs and is never overridden, so this
# version flags every call "20" flagged (the #717 review).
# js "22": stack-introspection tokens, including binding names and decoded
# JSX, can expose the CommonJS wrapper. ``with`` can shadow lexical lookup
# (treesitter-chunker#718).
# js "23": Node evaluator modules and process tokens or imports can expose
# run-wide writes. Bare process has closed member and operand exemptions;
# writes to those members, ``on``/``once`` outside a discarded call with
# arrow listeners, and loose equality except against ``null`` are causes
# (treesitter-chunker#702, R-699-4). Only a static import of process can be
# exempt, and none in a file where any scope binds ``require`` (R-699-7;
# same version, unreleased). A destructuring or loop-head write to the
# wrapper's ``require`` is a dynamic-loader cause (R-699-9; same version).
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
# python "24": fold 22 (one alias/readback/escape mechanism for a namespace
# dict, the mock module, ``patch`` and a pytest-mock fixture).
# python "25": fold 23 (E-21: the uses of a sensitive value are a closed
# allow-list; every other use fails closed).
# python "26": fold 24 (Y-5: imports of the mock module or ``patch`` are
# aliases; Y-6: ``values()``/``items()`` on a namespace fail closed).
# python "27": fold 25 (Codex 4657695001: allow-listed callees are verified
# by binding: builtin ``len``/``dict``, a tracked ``operator`` import).
# python "28": fold 26 (AA-4: a writer relied on through a module attribute
# or a from-import is relied on by name; a recorded write of it fails closed).
# python "29": fold 27 (Codex 4657978945: an allow-listed read's result must
# not reach the namespace; ``keys()`` leaves ``_NS_READS``).
# python "30": fold 28 (Codex 4658232413: allow-listed callees verified by the
# ordinary lookup at the use site, so open class namespaces fail closed).
# python "31": Tier 2 Python (plan PR 6): the module-scope export table,
# what ``import m`` binds (``bound``), import groups and member chains of
# calls, every use of an imported module object (writes and escapes, #697),
# literal module acquisitions, star imports, dotted constant strings,
# run-wide causes and parse hazards (``module_bindings``).
# python "32": PR 6 fold 1 (#705 Q2): ``compile`` alone is no evaluator
# cause; the fixtures' digests are unchanged, but a file that only compiles
# source loses its ``evaluator`` shutoff.
# python "33": PR 6 fold 2 (#705 E6-1..E6-8): ``module_imports`` (every
# import binding in the module namespace), patcher targets (computed ones a
# cause, constant ones a whole-module taint), write chains taint their first
# attribute, ``__path__``/``__spec__`` reads are safe, and the Tier 2 module
# facts are computed only in ``imports`` mode (empty otherwise).
# python "34": PR 6 fold 3 (#705 P6-1..P6-4, N-1): own-submodule imports
# are ``from . import x`` or the package's full dotted name only, and none in
# an ``__init__.py`` with a star import; patchers follow the Tier 1 W-3
# aliases and ``MonkeyPatch`` aliases, and a computed ``patch.multiple`` /
# ``patch.dict`` target is a cause; a write of a function's ``__code__``,
# ``__closure__``, ``__defaults__`` or ``__kwdefaults__`` is a
# ``module-object`` cause.
# python "35": PR 6 fold 4 (#705 E6-9): pytest's ``MonkeyPatch`` is a patcher
# kind (imports of it under any alias, ``MonkeyPatch()``/``.context()``,
# ``getfixturevalue``; no substring rule), and in a test file a patcher value
# off the E-21 allow-list, or a computed ``getfixturevalue``, is an
# ``unresolvable-writer`` cause. The fixtures' digests change only by the
# version.
# python "36": PR 6 fold 5 (#705 P6-10..P6-15, E6-9a): the patcher-escape
# scan runs in every file (causes O-2-scoped by the file's own
# classification); ``syspath_prepend`` on a MonkeyPatch is ``module-system``;
# MonkeyPatch aliases must be unreachable bindings; ``getfixturevalue``
# reached by alias or by ``getattr`` is a computed fixture; an annotation is
# safe only with no call in between.
# python "37": PR 6 fold 6 (#705 E6-9b): ``setattr``/``delattr``/
# ``syspath_prepend`` (and ``setitem``/``delitem``) are MonkeyPatch methods
# on any receiver except the ``operator`` module, also by name as a call
# argument or as a method reference; the MonkeyPatch instance and class kinds
# are gone.
# python "38": PR 6 fold 7 (#705 P6-21, P6-22): a constant name (patcher
# method or ``getfixturevalue``) counts in any spelling ``_constant_string``
# decodes, as a positional argument, a keyword value or a subscript key.
# python "39": K-3 classifies a ``__main__`` string by components split on
# format and attribute punctuation and whitespace, and by a default
# ``string.Template`` identifier, so stored templates count; f-string and
# t-string literal parts and format specs are decoded from the tree, and an
# undecodable one fails closed (treesitter-chunker#698, R-698-1). Before the
# merge, R-698-3 replaced the f-/t-string piece reader: such a string counts
# when a main name occurs anywhere in its decoded source text (same version,
# unreleased; the fixtures' digests are unchanged).
# python "40": treesitter-chunker#699 S2 (plan 699-702 PY-1..PY-5, PY-8;
# ruling R-699-1 B-1, B-2, B-4, B-5): code run from a string, a payload or
# an annotation (stdlib string-code helpers, ``pickle``/``timeit``/``runpy``
# by member allow-list, ``shelve``, unpicklers, ``breakpoint``, annotation
# evaluators, string annotations, ``__annotations__`` writes, ``compile``,
# ``marshal``, loader methods, and ``exec``/``eval``) fails closed file-wide
# in Tier 1 and is a run-wide ``evaluator`` cause in Tier 2; every
# code-object name, reads included, is a ``module-object`` cause (reversing
# #705 Q2); the names ``gettext.install()`` puts into ``builtins`` are
# ``builtin-shadow``; computed attribute reads in mock files fail closed.
# With the R-699-3, R-699-5 and R-699-6 folds (every constant among the
# arguments of ``import_module``/``__import__`` is an acquisition position).
# Unreleased as "39" on the #727 branch; renumbered after #714 took "39".
# python "41": treesitter-chunker#707: a function-scope sensitive alias (E-21)
# is reachable when its function's locals may be read as a dict: a
# ``locals()`` or no-argument ``vars()`` call inside it, ``locals``/``vars``
# as a value, an attribute, an imported name or in any constant string
# (exactly or as a dotted, ``:`` or bracket component; R-707-1) anywhere in
# the file, or a file-wide frame trigger (``f_locals`` reads included); a
# parameter or other binding of such a function is reachable too (R-707-1).
# Unreleased as "39" on the #721 branch; renumbered after #714 and #727.
# python "42": treesitter-chunker#699 S4 (plan 699-702 PY-6, PY-7, PY-9,
# PY-10; ruling R-699-1 Q2, Q5, Q6, B-6, B-7): ``gc`` by member allow-list
# plus the heap walkers as tokens fails closed file-wide in Tier 1 and is a
# run-wide ``module-object`` cause in Tier 2; ``.patch`` on any receiver is a
# patcher (W-3 semantics; handed on or named by string it fails closed in
# Tier 1 and is an ``unresolvable-writer`` in Tier 2); in Tier 2 every
# frame-locals spelling (``f_locals`` reads included, ``getargvalues``,
# ``getgeneratorlocals``, ``getcoroutinelocals``, ``getasyncgenlocals``,
# ``curframe_locals``), ``locals``/``vars`` as a value, import name or
# constant-string token, and ``cell_contents`` other than a plain read are
# ``module-object`` causes. Provisional: renumbered at merge if #726 or #729
# lands first.
# python "43": treesitter-chunker#724, R-724-1: a file in which any token
# spells a namespace-reaching name (``globals``, ``f_globals``,
# ``__import__``, ``builtins``, ``__spec__``, ...; any role, any constant
# spelling), uses a bare ``eval``/``exec`` or imports ``__main__`` records
# a ``value`` use of every import binding in it; a package ``__init__.py``
# also taints itself wholly (its submodules), and a handed-out ``sys``,
# ``importlib`` or ``builtins`` adds ``module-system``. R-724-2 exempts
# ``exec(code, X.__dict__)`` and ``<name>.loader.exec_module(X)`` on a fresh
# module local and ``__import__`` of a constant foreign module. R-724-4
# (same version, unreleased): format-field separators, more tokens, the
# own-name resolvers and ``request.module``, and the exemption voided by a
# constant word or a ``__class__`` write. Only ``imports``-mode facts change;
# the fixtures' digests change only by the version. R-724-7 limits freshness
# to types.ModuleType because a loader may return an existing module.
# python "44": record private import aliases and member reads at every scope (#684).
CALL_RESOLUTION_FACT_VERSIONS: dict[str, str] = {"js": "23", "python": "44"}

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
    # The run-wide shutoff (E5-3), one reason per cause.
    "run-tainted:evaluator",
    "run-tainted:dynamic-loader",
    "run-tainted:module-system",
    "run-tainted:module-object",
    "run-tainted:unparsed-file",
    "run-tainted:unresolvable-writer",
    "run-tainted:dynamic-scope",
    # Tier 2 Python (PR 6): a module another file may write wholly (#697),
    # and a package whose module ``__getattr__`` answers a submodule name
    # (#705 E6-3).
    "module-escape",
    "module-getattr",
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
    symlink: bool = False,
    mode: str | None = None,
) -> dict[str, Any]:
    """Re-parse ``source`` and return the file's scope facts.

    ``mode`` is the run's ``call_resolution``. A Python file's Tier 2 module
    facts (``exports``, ``module_bindings``) are computed only for
    ``"imports"`` (or when no mode is given); other modes never read them
    (#705 E6-8).

    ``symlink`` says the file was collected through a symbolic link; Tier 2
    never resolves an import from or into such a file (E5-5). A JS/TS file
    that cannot be analyzed has no ``module_bindings``; the engine counts it
    as a run-wide ``unparsed-file`` cause, scoped by O-2 (E5-7).

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
        if family == "js" and _misread_line_terminators(source, root, language):
            # P5-47: tree-sitter runs a ``#!`` line, a ``//`` comment or an
            # HTML-like comment past a JS line terminator it does not honour,
            # with no error; the file counts as unparsed (E5-7).
            logger.debug("call resolution: %s tree may hide code", language)
            return fallback
        if family == "js" and suffix in _MODULE_SUFFIXES:
            partial = js_scope.analyze(
                root, source, language, call_facts, goal="module", symlink=symlink
            )
        elif family == "js" and analyzer is js_scope.analyze:
            partial = js_scope.analyze(
                root, source, language, call_facts, symlink=symlink
            )
        elif family == "python" and analyzer is py_scope.analyze:
            partial = py_scope.analyze(
                root,
                source,
                language,
                call_facts,
                path=path,
                tier2=mode in (None, "imports"),
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


_LONE_CR = re.compile(rb"\r(?!\n)")
_LINE_SEPARATORS = (b"\xe2\x80\xa8", b"\xe2\x80\xa9")


def _misread_line_terminators(source: bytes, root: Any, language: str) -> bool:
    """P5-47: a lone CR, a U+2028 or U+2029 anywhere in the text, or any
    ``html_comment`` node (TypeScript has no HTML-like comments, and
    tree-sitter's runs past a lone CR). P5-50: in JavaScript, an HTML-like
    comment tree-sitter reads as code (:func:`_hidden_html_comment`)."""
    if _LONE_CR.search(source) or any(sep in source for sep in _LINE_SEPARATORS):
        return True
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "html_comment":
            return True
        stack.extend(node.children)
    return language.lower() == "javascript" and _hidden_html_comment(source, root)


# Leaves whose bytes are not code (P5-50). A ``template_substitution`` inside
# a ``template_string`` is code again.
_COMMENT_LEAVES = frozenset({"comment", "html_comment", "hash_bang_line"})
_TEXT_LEAVES = frozenset({"string", "template_string", "regex", "jsx_text"})
_SPACE_BYTES = frozenset(b" \t\v\f")


def _hidden_html_comment(source: bytes, root: Any) -> bool:
    """P5-50: an Annex B HTML-like comment that tree-sitter reads as code.

    V8 (Script goal) makes the rest of the line a comment at (a) a ``<!--``
    anywhere in code, and (b) a ``-->`` in code with only whitespace and
    comments before it on its line, where the line may begin inside a
    multi-line comment. tree-sitter reads ``x <!--y`` or ``*/ -->`` as
    operators, and what follows can open a template or comment that hides
    the next lines. Only code bytes count, so HTML text in strings,
    templates, regexes and JSX text is ignored. A non-ASCII byte counts as
    whitespace before ``-->`` (fail closed)."""
    if b"<!--" not in source and b"-->" not in source:
        return False
    code = bytearray(b"\x01") * len(source)
    comment = bytearray(len(source))
    stack = [root]
    while stack:
        node = stack.pop()
        start, end = node.start_byte, node.end_byte
        if node.type in _COMMENT_LEAVES:
            code[start:end] = bytes(end - start)
            comment[start:end] = b"\x01" * (end - start)
            continue
        if node.type in _TEXT_LEAVES:
            # Parents are marked before their children, so a substitution
            # pushed below is re-marked as code after its template.
            code[start:end] = bytes(end - start)
            if node.type != "template_string":
                continue
            for child in node.children:
                if child.type == "template_substitution":
                    code[child.start_byte : child.end_byte] = b"\x01" * (
                        child.end_byte - child.start_byte
                    )
                    stack.append(child)
            continue
        stack.extend(node.children)
    index = source.find(b"<!--")
    while index >= 0:
        if code[index]:
            return True
        index = source.find(b"<!--", index + 1)
    index = source.find(b"-->")
    while index >= 0:
        if code[index]:
            line = max(source.rfind(b"\n", 0, index), source.rfind(b"\r", 0, index))
            if all(
                comment[at] or source[at] in _SPACE_BYTES or source[at] >= 0x80
                for at in range(line + 1, index)
            ):
                return True
        index = source.find(b"-->", index + 1)
    return False


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


_MODULE_BINDING_KEYS = frozenset(
    {
        "stars",
        "commonjs",
        "opaque",
        "symlink",
        "taints",
        "imports",
        "uncomputable",
        "filename_taints",
        "ns_uses",
        "shutoff",
    }
)
_NS_USE_KINDS = frozenset({"read", "call"})


def _valid_export_entry(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    kind = value.get("kind")
    if kind == "local":
        return (
            set(value) == {"kind", "outcome", "this"}
            and type(value["this"]) is bool
            and valid_outcome(value["outcome"])
        )
    if kind == "reexport":
        return (
            set(value) == {"kind", "source", "name"}
            and isinstance(value["source"], str)
            and isinstance(value["name"], str)
        )
    if kind == "none":
        return (
            set(value) == {"kind", "reason"}
            and isinstance(value["reason"], str)
            and value["reason"] in KNOWN_NONE_REASONS
        )
    return False


def valid_export_table(value: object) -> bool:
    """Whether ``value`` is a well-formed JS/TS ``exports`` table."""
    return isinstance(value, dict) and all(
        isinstance(name, str) and _valid_export_entry(entry)
        for name, entry in value.items()
    )


def valid_module_bindings(value: object) -> bool:
    """Whether ``value`` is well-formed JS/TS ``module_bindings``."""
    if not isinstance(value, dict) or set(value) != _MODULE_BINDING_KEYS:
        return False
    from .js_modules import SHUTOFF_CAUSES

    return (
        all(
            isinstance(value[key], list)
            and all(isinstance(item, str) for item in value[key])
            for key in ("stars", "taints", "imports", "filename_taints", "shutoff")
        )
        and set(value["shutoff"]) <= set(SHUTOFF_CAUSES)
        and isinstance(value["ns_uses"], list)
        and all(
            isinstance(use, list)
            and len(use) == 3
            and all(isinstance(item, str) for item in use)
            and use[2] in _NS_USE_KINDS
            for use in value["ns_uses"]
        )
        and all(
            type(value[key]) is bool
            for key in ("commonjs", "opaque", "symlink", "uncomputable")
        )
    )


_PY_MODULE_BINDING_KEYS = frozenset(
    {
        "imports",
        "uses",
        "taints",
        "stars",
        "strings",
        "shutoff",
        "unparsed",
        "missing",
        "groups",
        "chains",
        "module_imports",
        "own_submodules",
        "private_import_alias",
        "alias_member_reads",
    }
)
_PY_USE_POSITIONS = frozenset({"write", "call", "value"})


def _strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def valid_py_exports(value: object) -> bool:
    """Whether ``value`` is a well-formed Python ``exports`` table."""
    return isinstance(value, dict) and all(
        isinstance(name, str) and valid_outcome(outcome)
        for name, outcome in value.items()
    )


def valid_py_module_bindings(value: object) -> bool:
    """Whether ``value`` is well-formed Python ``module_bindings``."""
    if not isinstance(value, dict) or set(value) != _PY_MODULE_BINDING_KEYS:
        return False
    from .py_modules import SHUTOFF_CAUSES

    groups = value["groups"]
    chains = value["chains"]
    return (
        all(_strings(value[key]) for key in ("imports", "stars", "strings", "shutoff"))
        and set(value["shutoff"]) <= set(SHUTOFF_CAUSES)
        and isinstance(value["uses"], list)
        and all(
            _strings(use) and len(use) >= 2 and use[1] in _PY_USE_POSITIONS
            for use in value["uses"]
        )
        and isinstance(value["taints"], list)
        and all(_strings(taint) and len(taint) == 2 for taint in value["taints"])
        and type(value["unparsed"]) is bool
        and isinstance(value["missing"], str)
        and value["missing"] in KNOWN_NONE_REASONS
        and isinstance(groups, dict)
        and all(
            _is_span_key(key)
            and isinstance(items, list)
            and len(items) >= 2
            and all(
                isinstance(item, dict)
                and all(isinstance(v, str) for v in item.values())
                for item in items
            )
            for key, items in groups.items()
        )
        and isinstance(chains, dict)
        and all(
            _is_span_key(key) and _strings(items) and bool(items)
            for key, items in chains.items()
        )
        and isinstance(value["alias_member_reads"], list)
        and all(
            _strings(read) and len(read) >= 2 for read in value["alias_member_reads"]
        )
        and type(value["private_import_alias"]) is bool
        and _strings(value["own_submodules"])
        and isinstance(value["module_imports"], dict)
        and all(
            isinstance(name, str)
            and isinstance(items, list)
            and bool(items)
            and all(
                isinstance(item, dict)
                and all(isinstance(v, str) for v in item.values())
                for item in items
            )
            for name, items in value["module_imports"].items()
        )
    )


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
    if language_family(language) == "js" and (
        (supported and not valid_export_table(value["exports"]))
        or (not supported and value["exports"])
        or (
            (supported or value["module_bindings"])
            and not valid_module_bindings(value["module_bindings"])
        )
    ):
        return False
    # A Python file's module facts exist only in ``imports``-mode records
    # (#705 E6-8): both tables are empty, or both are well formed.
    tier2_tables = bool(value["exports"]) or bool(value["module_bindings"])
    if language_family(language) == "python" and (
        (supported and tier2_tables and not valid_py_exports(value["exports"]))
        or (
            supported
            and tier2_tables
            and not valid_py_module_bindings(value["module_bindings"])
        )
        or (not supported and tier2_tables)
    ):
        return False
    symbols = value["symbols"]
    return isinstance(symbols, list) and all(
        valid_symbol_entry(entry) for entry in symbols
    )
