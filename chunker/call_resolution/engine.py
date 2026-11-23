"""The call-resolution rule engine (plan sections 6 and 7.1).

Pure functions over per-file facts and the assembled symbol lookup; no
filesystem access. The engine narrows call relationships in place:

1. **Eligibility (6.1).** The mode is not ``"name"``; the caller's file is
   Python, JavaScript, TypeScript or TSX and its scope facts are supported;
   today's candidate set C0 has two or more members; and the reference is a
   bare identifier.
2. **Binding proof (6.3, ruling 2.1).** ``P`` is the set of symbols the
   lookup outcome proves. A ``local`` outcome proves its group-rule result,
   joined to symbol IDs by ``(node_type, byte_start, byte_end)``; a
   declaration that maps to no symbol, or to more than one, fails closed as
   ``none(unmapped)`` (5.4). A call with no binding entry is
   ``none(no-binding-fact)``. In ``structural`` mode an ``import`` outcome
   proves nothing. A ``local`` outcome that lands on a script-goal top level
   (it carries ``global``) proves its group only if no other file of the run
   declares that name in its ``script_globals``, none may write a global of
   any name, no other JavaScript/TypeScript file is unsupported (its globals
   are unknown) and no file of a language that can carry inline scripts is
   in the run; otherwise it is ``none(script-global)`` (7.2).
3. **Filters (7.1).** ``t1.family`` then ``t1.kind`` remove candidates of
   another language family or of a non-callable kind. They apply only when two
   or more candidates remain, or when the single survivor is proven by ``P``.
   A filter alone therefore never resolves an edge.

Every step only removes candidates and a step that would empty the set is
skipped. An edge is ``resolved`` only when its one remaining candidate is in
``P``. If a result ever broke these invariants the edge is left unchanged.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import py_modules
from .modules import ModuleRun, build_module_run, resolve_import

RULE_LEXICAL = "t1.lexical"
RULE_KIND = "t1.kind"
RULE_FAMILY = "t1.family"
RULE_TS_OVERLOAD = "t1.ts_overload"
RULE_JS_HOIST = "t1.js_hoist"
RULE_IMPORT = "t2.import"
RULE_NAMESPACE = "t2.namespace"
KNOWN_RULE_IDS = (
    RULE_LEXICAL,
    RULE_KIND,
    RULE_FAMILY,
    RULE_TS_OVERLOAD,
    RULE_JS_HOIST,
    RULE_IMPORT,
    RULE_NAMESPACE,
)
# Rules that prove a binding; every resolved edge names one of them.
BINDING_RULE_IDS = frozenset({RULE_LEXICAL, RULE_IMPORT, RULE_NAMESPACE})
# A ``script_globals`` entry for a file that may write a global of any name.
GLOBAL_WILDCARD = "*"
# Collected languages whose files can carry inline scripts (``<script>``,
# event-handler attributes) the analysis never reads: each such file in the
# run counts as declaring every global (B5, #691 panel).
# Markdown and reStructuredText run nothing themselves: their raw HTML runs
# only in a page a site generator renders, outside the run (plan R9).
INLINE_SCRIPT_LANGUAGES = frozenset({"html", "xml", "php"})
# Group rules (7.4) refine a binding's group; they never apply alone.
GROUP_RULE_IDS = frozenset({RULE_TS_OVERLOAD, RULE_JS_HOIST})
FILTER_RULE_IDS = frozenset({RULE_KIND, RULE_FAMILY})
# t1.kind removes these symbol kinds (7.1).
NON_CALLABLE_KINDS = frozenset(
    {"interface", "type", "enum", "module", "struct", "trait"}
)
_JS_FAMILY_LANGUAGES = frozenset({"javascript", "typescript", "tsx"})
_ANALYZED_LANGUAGES = _JS_FAMILY_LANGUAGES | {"python"}
_BARE_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# ``ns.f``: a namespace-import member call (Tier 2, section 9.1).
_NAMESPACE_MEMBER = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)")
# ``m.f``, ``a.b.f``: a Python module member chain (Tier 2, section 9.4).
_MEMBER_CHAIN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
MODE_IMPORTS = "imports"

Declaration = tuple[str, int, int]


def language_family(language: str | None) -> str | None:
    """``"js"`` for JavaScript, TypeScript and TSX; otherwise the language."""
    if not language:
        return None
    normalized = language.lower()
    return "js" if normalized in _JS_FAMILY_LANGUAGES else normalized


def is_bare_identifier(reference: str) -> bool:
    """Whether a call reference is a plain identifier (Tier 1 eligible)."""
    return _BARE_IDENTIFIER.fullmatch(reference) is not None


def namespace_member(reference: str) -> str | None:
    """The member of a two-segment reference ``ns.f``, else ``None``."""
    match = _NAMESPACE_MEMBER.fullmatch(reference)
    return match.group(2) if match else None


def _none(reason: str) -> dict[str, Any]:
    return {"outcome": "none", "reason": reason}


@dataclass(frozen=True)
class FileContext:
    """One file's scope facts, indexed for the join."""

    language: str | None
    supported: bool
    bindings: Mapping[str, Any]
    declarations: Mapping[Declaration, tuple[str, ...]]
    path: str = ""
    script_globals: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RunContext:
    """Everything the engine reads for one run."""

    mode: str
    files: Mapping[str, FileContext]
    symbol_lookup: Mapping[str, Mapping[str, Any]]
    # Tier 2 input (plan 4.2): the run's language filter. The run's file set
    # is ``files``; assembly never touches the filesystem.
    language_filter: str | None = None
    # Script globals (7.2): the files declaring each name, and the files
    # whose globals are unknown (a wildcard, an unsupported JS/TS file, or a
    # file that can carry inline scripts).
    global_declarers: Mapping[str, frozenset[str]] = field(default_factory=dict)
    unknown_globals: frozenset[str] = frozenset()
    # Tier 2 (section 9): the run's module graph, in ``imports`` mode only.
    modules: ModuleRun | None = None
    # Tier 2 Python (9.4-9.6, PR 6), in ``imports`` mode only.
    py_modules: py_modules.PyModuleRun | None = None


@dataclass(frozen=True)
class Decision:
    """The engine's decision for one call relationship."""

    call_site_id: str
    eligible: bool
    outcome: Mapping[str, Any] | None
    before: tuple[str, ...]
    after: tuple[str, ...]
    proven: frozenset[str] = field(default_factory=frozenset)
    rules: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return self.after != self.before

    @property
    def resolution(self) -> str:
        if len(self.after) == 1:
            return "resolved"
        return "ambiguous" if self.after else "unresolved"


def build_run_context(
    facts: Iterable[Mapping[str, Any]],
    symbol_lookup: Mapping[str, Mapping[str, Any]],
    mode: str,
    *,
    language_filter: str | None = None,
    directory_symlinks: bool | None = None,
) -> RunContext:
    """Index every file's scope facts by its display path."""
    facts = list(facts)
    files: dict[str, FileContext] = {}
    for file_facts in facts:
        scope_facts = file_facts["scope_facts"]
        declarations: defaultdict[Declaration, list[str]] = defaultdict(list)
        for node_type, byte_start, byte_end, symbol_id in scope_facts["symbols"]:
            declarations[(str(node_type), int(byte_start), int(byte_end))].append(
                str(symbol_id)
            )
        path = str(file_facts.get("path") or "")
        files[path] = FileContext(
            path=path,
            language=scope_facts.get("language"),
            supported=bool(scope_facts.get("supported")),
            bindings=scope_facts.get("bindings") or {},
            declarations={key: tuple(ids) for key, ids in declarations.items()},
            script_globals=frozenset(
                str(name) for name in scope_facts.get("script_globals") or ()
            ),
        )
    declarers: defaultdict[str, set[str]] = defaultdict(set)
    unknown: set[str] = set()
    for path, file_context in files.items():
        if file_context.language in INLINE_SCRIPT_LANGUAGES:
            unknown.add(path)
            continue
        if language_family(file_context.language) != "js":
            continue
        if not file_context.supported or GLOBAL_WILDCARD in file_context.script_globals:
            unknown.add(path)
        for name in file_context.script_globals:
            declarers[name].add(path)
    return RunContext(
        mode=mode,
        files=files,
        symbol_lookup=symbol_lookup,
        language_filter=language_filter,
        global_declarers={name: frozenset(paths) for name, paths in declarers.items()},
        unknown_globals=frozenset(unknown),
        modules=(
            build_module_run(facts, language_filter, directory_symlinks)
            if mode == MODE_IMPORTS
            else None
        ),
        py_modules=(
            py_modules.build_py_module_run(facts, directory_symlinks)
            if mode == MODE_IMPORTS
            else None
        ),
    )


def script_global_outcome(
    context: RunContext,
    file_context: FileContext,
    outcome: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    """Apply the cross-file script-global check to a lookup outcome (7.2).

    Only a ``local`` outcome that landed on a script-goal top level carries
    ``global``; it becomes ``none(script-global)`` when another file of the
    run declares that name as a script global, may write a global of any
    name, is an unsupported JavaScript/TypeScript file, or is a file of a
    language that can carry inline scripts (HTML, XML, PHP). This holds
    within the run only (plan R9, R11).
    """
    if outcome is None or outcome.get("outcome") != "local" or "global" not in outcome:
        return outcome
    name = str(outcome["global"])
    path = file_context.path
    declared = context.global_declarers.get(name, frozenset())
    unknown = context.unknown_globals
    conflict = (
        len(declared) > 1
        or bool(declared and path not in declared)
        or len(unknown) > 1
        or bool(unknown and path not in unknown)
    )
    return _none("script-global") if conflict else outcome


def _join(
    outcome: Mapping[str, Any],
    file_context: FileContext,
    symbol_lookup: Mapping[str, Mapping[str, Any]],
) -> tuple[frozenset[str], Mapping[str, Any], tuple[str, ...]]:
    """Map a ``local`` outcome's proof to symbol IDs; fail closed (5.4).

    Each declaration must map to exactly one symbol record, and that record
    must belong to the caller's file.
    """
    proven: set[str] = set()
    for node_type, byte_start, byte_end in outcome["proof"]:
        ids = file_context.declarations.get(
            (str(node_type), int(byte_start), int(byte_end)), ()
        )
        symbol = symbol_lookup.get(ids[0]) if len(ids) == 1 else None
        if symbol is None or symbol.get("file") != file_context.path:
            return frozenset(), _none("unmapped"), ()
        proven.add(ids[0])
    return frozenset(proven), outcome, tuple(str(rule) for rule in outcome["rules"])


def _checked_proof(
    outcome: Mapping[str, Any],
    file_context: FileContext,
    caller_family: str | None,
    symbol_lookup: Mapping[str, Mapping[str, Any]],
    binding_rule: str,
) -> tuple[frozenset[str], Mapping[str, Any], tuple[str, ...]]:
    """Join a ``local`` outcome in ``file_context`` and check its symbols."""
    proven, joined, group_rules = _join(outcome, file_context, symbol_lookup)
    if not proven:
        return proven, joined, ()
    # The engine enforces what the group rules promise (7.4): a proof
    # names only callable symbols of the caller's family. Anything else
    # fails closed, so a filter can never turn it into a resolution.
    if any(
        not _symbol_callable(symbol_lookup.get(symbol_id))
        or _symbol_family(symbol_lookup.get(symbol_id)) != caller_family
        for symbol_id in proven
    ):
        return frozenset(), _none("non-callable"), ()
    extra = tuple(rule for rule in group_rules if rule in GROUP_RULE_IDS)
    return proven, joined, (binding_rule, *extra)


def proof(
    outcome: Mapping[str, Any] | None,
    mode: str,
    file_context: FileContext,
    symbol_lookup: Mapping[str, Mapping[str, Any]],
    *,
    context: RunContext | None = None,
    member: str | None = None,
    span_key: str | None = None,
    head: str | None = None,
) -> tuple[frozenset[str], Mapping[str, Any], tuple[str, ...]]:
    """``(P, final outcome, binding rule IDs)`` for one call (6.3).

    ``member`` is the property of a namespace member call (``ns.f()``);
    ``span_key`` the call's callee span key (Python import groups and member
    chains are keyed by it); ``head`` the reference's first name, the
    caller's own binding a Python Tier 2 proof starts from.
    """
    if outcome is None:
        return frozenset(), _none("no-binding-fact"), ()
    kind = outcome.get("outcome")
    family = language_family(file_context.language)
    python_run = (
        family == "python"
        and mode == MODE_IMPORTS
        and context is not None
        and context.py_modules is not None
    )
    if kind == "local":
        if member is not None:
            # Only a namespace import's member is eligible (9.1).
            return frozenset(), outcome, ()
        if python_run:
            assert context is not None and context.py_modules is not None
            # ``imports`` mode: another file may write the module global the
            # proof names (#697), or a run-wide cause applies (PR 6).
            reason = py_modules.tier1_reason(
                context.py_modules, file_context.path, outcome.get("proof") or ()
            )
            if reason is not None:
                return frozenset(), _none(reason), ()
        return _checked_proof(
            outcome, file_context, family, symbol_lookup, RULE_LEXICAL
        )
    if python_run:
        assert context is not None and context.py_modules is not None
        return _python_proof(
            outcome,
            file_context,
            symbol_lookup,
            context,
            context.py_modules,
            span_key if span_key is not None else _span_key(file_context, outcome),
            head,
        )
    if (
        kind != "import"
        or mode != MODE_IMPORTS
        or family != "js"
        or context is None
        or context.modules is None
    ):
        # An import outcome proves nothing in structural mode (6.3); Python
        # import bindings are Tier 2 of a later change (section 9.4).
        return frozenset(), outcome, ()
    binding = outcome.get("binding") or {}
    if member is not None and binding.get("member") != member:
        # The reference and the tree must agree on the member (fail closed).
        return frozenset(), _none("export-not-found"), ()
    resolved = resolve_import(
        context.modules,
        file_context.path,
        file_context.language,
        binding,
        member,
    )
    if resolved.get("outcome") != "local":
        return frozenset(), resolved, ()
    target = context.files.get(str(resolved.get("path")))
    if target is None or not target.supported:
        return frozenset(), _none("export-not-found"), ()
    rule = RULE_NAMESPACE if member is not None else RULE_IMPORT
    proven, joined, rules = _checked_proof(
        resolved["local"], target, family, symbol_lookup, rule
    )
    if not proven:
        return proven, joined, ()
    return proven, outcome, rules


def _python_proof(
    outcome: Mapping[str, Any],
    file_context: FileContext,
    symbol_lookup: Mapping[str, Mapping[str, Any]],
    context: RunContext,
    run: py_modules.PyModuleRun,
    key: str | None,
    head: str | None = None,
) -> tuple[frozenset[str], Mapping[str, Any], tuple[str, ...]]:
    """Tier 2 Python (9.4-9.6): an import binding, or a group of two or more
    imports (which narrows but resolves only when every member proves the
    same definitions), followed by the call's member chain. The caller's own
    binding of ``head`` must hold what the import put there (#705 E6-1):
    another file may write it, and a package's submodule import sets it.
    Both reach only the module namespace, so a binding the lookup decided in
    a function scope skips the check (#709); an unknown key keeps it."""
    py_file = run.files.get(file_context.path)
    if py_file is None:
        return frozenset(), outcome, ()
    if outcome.get("outcome") == "import" or (key and key in py_file.groups):
        reason = (
            py_modules.own_binding_reason(run, file_context.path, head)
            if head and not (key and key in py_file.local_imports)
            else None
        )
        if reason is not None:
            return frozenset(), _none(reason), ()
    chain = list(py_file.chains.get(key, ())) if key else []
    if outcome.get("outcome") == "import":
        bindings = [outcome.get("binding") or {}]
    else:
        bindings = list(py_file.groups.get(key, ())) if key else []
        if not bindings:
            return frozenset(), outcome, ()
    rule = RULE_NAMESPACE if chain else RULE_IMPORT
    proven: set[str] = set()
    for binding in bindings:
        resolved = py_modules.resolve_import(run, file_context.path, binding, chain)
        if resolved.get("outcome") != "local":
            return frozenset(), resolved, ()
        target = context.files.get(str(resolved.get("path")))
        if target is None or not target.supported:
            return frozenset(), _none("export-not-found"), ()
        found, joined, _rules = _checked_proof(
            resolved["local"], target, "python", symbol_lookup, rule
        )
        if not found:
            return frozenset(), joined, ()
        proven |= found
    shown = outcome if outcome.get("outcome") == "import" else {"outcome": "import"}
    return frozenset(proven), shown, (rule,)


def _span_key(file_context: FileContext, outcome: Mapping[str, Any]) -> str | None:
    """The callee span key of a binding outcome in its file."""
    for key, value in file_context.bindings.items():
        if value is outcome:
            return str(key)
    return None


def _symbol_family(symbol: Mapping[str, Any] | None) -> str | None:
    return language_family(symbol.get("language")) if symbol else None


def _symbol_callable(symbol: Mapping[str, Any] | None) -> bool:
    return symbol is not None and str(symbol.get("kind")) not in NON_CALLABLE_KINDS


def narrow(
    candidates: Sequence[str],
    proven: frozenset[str],
    binding_rules: Sequence[str],
    caller_family: str | None,
    symbol_lookup: Mapping[str, Mapping[str, Any]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The binding-proof algorithm over C0 (6.3): ``(C, rule IDs)``."""
    before = tuple(candidates)
    if any(candidate not in symbol_lookup for candidate in before):
        # A candidate without a symbol record cannot be classified.
        return before, ()
    current = before
    rules: list[str] = []
    # 1. Binding: intersect with the proof when that removes something.
    if proven:
        kept = tuple(candidate for candidate in current if candidate in proven)
        if kept and kept != current:
            current = kept
            rules.extend(binding_rules)
    # 2. Filters: same family, then callable kinds. Applied together, and only
    # when two or more remain or the single survivor is proven.
    same_family = tuple(
        candidate
        for candidate in current
        if _symbol_family(symbol_lookup.get(candidate)) == caller_family
    )
    callable_ = tuple(
        candidate
        for candidate in same_family
        if _symbol_callable(symbol_lookup.get(candidate))
    )
    if callable_ != current and (
        len(callable_) >= 2 or (len(callable_) == 1 and callable_[0] in proven)
    ):
        if same_family != current:
            rules.append(RULE_FAMILY)
        if callable_ != same_family:
            rules.append(RULE_KIND)
        current = callable_
    # 3. Invariants: a subset of C0, never empty, resolved only when proven
    # and only through a binding rule.
    if (
        not current
        or not set(current) <= set(before)
        or (len(current) == 1 and current[0] not in proven)
        or (len(current) == 1 and not BINDING_RULE_IDS & set(rules))
        or (current != before and not rules)
    ):
        return before, ()
    return current, tuple(rules)


def decide(context: RunContext, relationship: Mapping[str, Any]) -> Decision:
    """The decision for one ``calls`` relationship in its off-mode form."""
    call_site_id = str(relationship.get("call_site_id") or "")
    before = tuple(str(candidate) for candidate in relationship.get("candidates", []))
    not_eligible = Decision(call_site_id, False, None, before, before)
    if context.mode == "name" or relationship.get("type") != "calls":
        return not_eligible
    file_context = context.files.get(str(relationship.get("file") or ""))
    if (
        file_context is None
        or file_context.language not in _ANALYZED_LANGUAGES
        or not file_context.supported
    ):
        return not_eligible
    if relationship.get("resolution") != "ambiguous" or len(before) < 2:
        return not_eligible
    reference = str(relationship.get("reference") or "")
    raw = file_context.bindings.get(
        f"{relationship.get('callee_byte_start')}:{relationship.get('callee_byte_end')}"
    )
    member: str | None = None
    family = language_family(file_context.language)
    if family == "python" and not is_bare_identifier(reference):
        # Tier 2 Python: a member chain whose head the lookup binds to an
        # import (or a group of imports), with the chain read from the tree
        # matching the reference exactly (9.4). Every other member call is
        # untouched.
        key = (
            f"{relationship.get('callee_byte_start')}:"
            f"{relationship.get('callee_byte_end')}"
        )
        run = context.py_modules
        py_file = run.files.get(file_context.path) if run is not None else None
        chain = py_file.chains.get(key) if py_file is not None else None
        if (
            context.mode != MODE_IMPORTS
            or py_file is None
            or not chain
            or _MEMBER_CHAIN.fullmatch(reference) is None
            or reference.split(".")[1:] != list(chain)
            or ((raw or {}).get("outcome") != "import" and key not in py_file.groups)
        ):
            return not_eligible
    elif not is_bare_identifier(reference):
        # Tier 2: a two-segment member call whose head the lookup binds to a
        # namespace import (9.1). Every other member call is untouched.
        member = namespace_member(reference)
        binding = (raw or {}).get("binding") or {}
        if (
            context.mode != MODE_IMPORTS
            or member is None
            or language_family(file_context.language) != "js"
            or (raw or {}).get("outcome") != "import"
            or binding.get("form") != "namespace"
        ):
            return not_eligible
    raw = script_global_outcome(context, file_context, raw)
    proven, outcome, binding_rules = proof(
        raw,
        context.mode,
        file_context,
        context.symbol_lookup,
        context=context,
        member=member,
        span_key=(
            f"{relationship.get('callee_byte_start')}:"
            f"{relationship.get('callee_byte_end')}"
        ),
        head=reference.partition(".")[0] or None,
    )
    after, rules = narrow(
        before,
        proven,
        binding_rules,
        language_family(file_context.language),
        context.symbol_lookup,
    )
    return Decision(call_site_id, True, outcome, before, after, proven, rules)


def apply_decision(relationship: dict[str, Any], decision: Decision, mode: str) -> None:
    """Rewrite a changed relationship (4.3); an unchanged one is untouched."""
    if not decision.changed:
        return
    resolved = decision.resolution == "resolved"
    relationship["to"] = (
        decision.after[0] if resolved else str(relationship.get("reference"))
    )
    relationship["resolution"] = decision.resolution
    relationship["candidates"] = list(decision.after)
    relationship["is_internal"] = resolved
    relationship["provenance"] = {
        **relationship.get("provenance", {}),
        "call_resolution": mode,
        "call_rules": list(decision.rules),
    }


def narrow_relationships(
    relationships: Sequence[dict[str, Any]],
    context: RunContext,
) -> dict[str, Decision]:
    """Narrow every eligible call relationship in place; return the decisions."""
    decisions: dict[str, Decision] = {}
    if context.mode == "name":
        return decisions
    for relationship in relationships:
        if relationship.get("type") != "calls":
            continue
        decision = decide(context, relationship)
        decisions[decision.call_site_id] = decision
        apply_decision(relationship, decision, context.mode)
    return decisions
