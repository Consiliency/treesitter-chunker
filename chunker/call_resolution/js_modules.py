"""Per-file module facts for Tier 2 JS/TS resolution (plan sections 9.1-9.3).

:func:`module_facts` reads one analyzed file's top-level export statements
and the ways the file can reach another module's exports object. The engine
(:mod:`.modules`) joins these facts across the run.

``exports`` maps each export name (an identifier's spelling or a quoted
name's exact string value) to one entry:

- ``{"kind": "local", "outcome": <outcome>}``: the file's own binding of a
  local name, looked up at the top level with the Tier 1 rules (section
  9.3, step 1). The outcome is ``local`` (a proof), ``import`` (a re-export
  hop through an import of this file) or ``none``;
- ``{"kind": "reexport", "source": <specifier>, "name": <name>}``:
  ``export { a as x } from`` and ``export { x } from`` (step 2);
- ``{"kind": "none", "reason": <reason>}``: ``export * as x from``
  (``namespace-export``), a type-only export (``type-only``), a default
  export of an expression (``expression-bound``), or two different value
  exports of one name (``mixed-bindings``).

Type-space declarations (``export interface``, ``export type T =``) give a
``type-only`` entry only when no value export has the name, because a TS
interface and a function of one name merge.

``module_bindings`` holds:

``has_decorator``
    A decorator anywhere in this module can run code or replace a binding.
``stars``
    The specifiers of ``export * from`` (step 4), in source order.
``commonjs``
    The file's exports object may be written by CommonJS code (step 5):
    ``export =``, any ``exports`` or ``module`` identifier, or a top-level
    ``this`` or ``arguments`` (the CommonJS wrapper's ``exports`` when TS
    emits CommonJS). Every lookup in such a file gives ``none(commonjs)``.
``opaque``
    An export statement outside the closed list this module reads, or a
    specifier or name that does not decode exactly. Every lookup in such a
    file fails closed (``export-not-found``).
``taints``
    Relative specifiers whose module's exports object this file may write.
    When TS or a bundler emits CommonJS, that object is shared and mutable,
    so a namespace import used other than as ``ns.name`` read in an
    allow-listed position, ``require(<string>)``, ``import(<string>)`` and
    ``import x = require(<string>)`` taint the module they name. The engine
    gives every lookup through a tainted module ``none(commonjs)``.
``imports``
    Every static specifier (imports, re-exports): with ``taints`` and
    ``stars``, the import graph the engine uses to promote a test file that
    production code reaches (owner decision O-2).
``ns_uses``
    ``[specifier, member, "read" | "call"]`` for each allow-listed
    ``ns.member`` use; the engine requires a verified export, and for a call
    one whose declarations never mention ``this`` (E5-1).
``symlink``
    The file was collected through a symbolic link (E5-5).
``shutoff``
    Run-wide causes (E5-3): ``evaluator``, ``dynamic-loader``,
    ``module-system``, ``module-object``, ``unparsed-file``,
    ``unresolvable-writer``, and ``dynamic-scope``. Under O-2 a cause in a
    test file applies only to callers in test files unless production reaches it.

Uses of the sensitive values (a namespace import, ``require``, ``module``)
are classified by a closed allow-list after unwrapping parentheses and TS
wrappers, and a namespace import's uses are found by the ordinary lookup at
each use site, so a shadowing binding is never mistaken for it.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from .js_strings import (
    cook_template,
    decode_js_string_sloppy,
    decode_jsx_text,
    decode_string_literal,
    module_export_name,
)

if TYPE_CHECKING:  # pragma: no cover
    from .js_scope import _Analysis

# Export-declaration kinds read as local value bindings (section 9.3).
_LOCAL_DECLARATIONS = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "function_signature",
        "class_declaration",
        "abstract_class_declaration",
        "enum_declaration",
        "internal_module",
        "module",
        "import_alias",
    }
)
_VARIABLE_DECLARATIONS = frozenset({"lexical_declaration", "variable_declaration"})
_TYPE_DECLARATIONS = frozenset({"interface_declaration", "type_alias_declaration"})
_WRAPPERS = frozenset(
    {
        "parenthesized_expression",
        "non_null_expression",
        "as_expression",
        "satisfies_expression",
        "type_assertion",
    }
)
_NON_ARROW_FUNCTIONS = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "function_expression",
        "generator_function",
        "method_definition",
    }
)
# Run-wide causes (E5-3): the ``none(run-tainted:<cause>)`` reasons.
CAUSE_EVALUATOR = "evaluator"
CAUSE_DYNAMIC_LOADER = "dynamic-loader"
CAUSE_MODULE_SYSTEM = "module-system"
CAUSE_MODULE_OBJECT = "module-object"
CAUSE_UNPARSED_FILE = "unparsed-file"
CAUSE_UNRESOLVABLE_WRITER = "unresolvable-writer"
CAUSE_DYNAMIC_SCOPE = "dynamic-scope"
SHUTOFF_CAUSES = (
    CAUSE_EVALUATOR,
    CAUSE_DYNAMIC_LOADER,
    CAUSE_MODULE_SYSTEM,
    CAUSE_MODULE_OBJECT,
    CAUSE_UNPARSED_FILE,
    CAUSE_UNRESOLVABLE_WRITER,
    CAUSE_DYNAMIC_SCOPE,
)
# ``import.meta`` reads that load nothing.
_IMPORT_META_READS = frozenset(
    {"url", "dirname", "filename", "resolve", "env", "main", "hot"}
)
# Vite's ``import.meta.glob``/``globEager`` load every matched module: the
# targets cannot be computed, so every test file is promoted (fold 4).
_IMPORT_META_LOADERS = frozenset({"glob", "globEager"})
# P5-1: ``import.meta`` properties that name the file itself.
_OWN_FILE_META = frozenset({"url", "filename"})
# P5-3: test-framework module mocks (a closed list), by the framework's
# global name and the packages that export it.
MODULE_MOCKS: dict[str, frozenset[str]] = {
    "jest": frozenset({"mock", "doMock", "unstable_mockModule", "setMock"}),
    "vi": frozenset({"mock", "doMock"}),
}
MOCK_PACKAGES = {"jest": "@jest/globals", "vi": "vitest"}
# Names that reach the CommonJS module system from anywhere.
_MODULE_SYSTEM_NAMES = frozenset({"mainModule", "createRequire", "getBuiltinModule"})
_MODULE_SYSTEM_TOKEN_NAMES = frozenset({"caller", "getFunction", "process"})
_MODULE_SYSTEM_NAME_TOKENS = frozenset(
    {
        "identifier",
        "property_identifier",
        "shorthand_property_identifier",
        "shorthand_property_identifier_pattern",
        "statement_identifier",
        "type_identifier",
    }
)
# Pieces of one JSX text run (R-718-3).
_JSX_TEXT_PARTS = frozenset({"jsx_text", "html_character_reference"})
_MODULE_SYSTEM_SPECIFIERS = frozenset({"module", "node:module"})
_PROCESS_SPECIFIERS = frozenset({"process", "node:process"})
_INERT_PROCESS_MEMBERS = frozenset(
    {
        "argv",  # Command-line argument strings.
        "cwd",  # Returns the current directory's path.
        "env",  # Reads and writes environment strings.
        "exit",  # Terminates the process.
        "on",  # Registers a process event listener.
        "once",  # Registers a one-shot process event listener.
        "platform",  # Platform name string.
        "send",  # Sends an IPC message to the parent and reports send status.
    }
)
# R-699-4 item 1: members that return ``process`` (EventEmitter returns
# ``this``) and call each listener with ``this === process``. They are
# exempt only as a discarded statement call with arrow listeners.
_PROCESS_LISTENER_MEMBERS = frozenset({"on", "once"})
# Node types that may spell a use of a binding (``_uses``).
_USE_NAME_TOKENS = frozenset(
    {
        "identifier",
        "shorthand_property_identifier_pattern",
        "shorthand_property_identifier",
    }
)
# R-699-4 item 2: steps from a member access up to the assignment, update,
# ``delete`` or ``for…in/of`` that writes it, through patterns (and their
# expression spellings, which tree-sitter sometimes gives a pattern).
_WRITE_PATTERN_STEPS = frozenset(
    {
        "array_pattern",
        "array",
        "object_pattern",
        "object",
        "rest_pattern",
        "spread_element",
    }
)
# Steps that write only when the access is their ``left`` (a default value
# on the right is a read) or their ``value`` (a key is not written).
_WRITE_FIELD_STEPS = {
    "assignment_pattern": "left",
    "object_assignment_pattern": "left",
    "pair_pattern": "value",
    "pair": "value",
}
_EVALUATOR_SPECIFIERS = frozenset(
    prefix + name
    for prefix in ("", "node:")
    for name in ("vm", "repl", "inspector", "inspector/promises")
)
# Fold 3, item 1: the only names an import from ``module`` may bind without
# a run-wide cause (with ``createRequire`` under item 2). ``builtinModules``
# is an array of names and ``isBuiltin(name)`` returns a boolean: neither
# can load a module, reach a module record or rewrite an exports object
# (Node's ``lib/internal/modules/helpers`` and ``lib/module.js``).
INERT_MODULE_EXPORTS = frozenset({"builtinModules", "isBuiltin"})
_COMMONJS_NAMES = frozenset({"exports", "module"})
_EQUALITY = frozenset({"===", "!==", "==", "!="})
# Ancestors that put an identifier in type space, where it reads nothing.
_TYPE_CONTEXTS = frozenset(
    {
        "type_annotation",
        "type_arguments",
        "type_query",
        "nested_type_identifier",
        "generic_type",
        "type_alias_declaration",
        "interface_declaration",
    }
)
# Read positions for ``ns.name`` (a closed allow-list): ``(parent kind,
# field)``, where ``None`` means any child of that parent.
_READ_POSITIONS = frozenset(
    {
        ("call_expression", "function"),
        ("new_expression", "constructor"),
        ("arguments", None),
        ("member_expression", "object"),
        ("subscript_expression", "object"),
        ("variable_declarator", "value"),
        ("return_statement", None),
        ("expression_statement", None),
        ("await_expression", None),
        ("template_substitution", None),
        ("spread_element", None),
        ("binary_expression", None),
        ("ternary_expression", None),
        ("sequence_expression", None),
        ("arrow_function", "body"),
        ("pair", "value"),
        ("array", None),
        ("assignment_expression", "right"),
        ("augmented_assignment_expression", "right"),
        # Cost reliefs (fold 1): reads under CommonJS emit too.
        ("extends_clause", "value"),
        ("jsx_self_closing_element", "name"),
        ("jsx_opening_element", "name"),
        ("jsx_closing_element", "name"),
    }
)


def _same(left: Any, right: Any) -> bool:
    return left is not None and right is not None and left.id == right.id


def _has_token(node: Any, token: str) -> bool:
    return any(not child.is_named and child.type == token for child in node.children)


def _parent_type(node: Any) -> str | None:
    return node.parent.type if node.parent is not None else None


def _text(node: Any, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _walk(root: Any) -> Iterator[Any]:
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.named_children))


def _field_of(parent: Any, child: Any) -> str | None:
    for index, candidate in enumerate(parent.children):
        if _same(candidate, child):
            name = parent.field_name_for_child(index)
            return str(name) if name is not None else None
    return None


def _climb_wrappers(node: Any) -> Any:
    """``node`` and the parentheses or TS wrappers around it, outermost."""
    current = node
    while current.parent is not None and current.parent.type in _WRAPPERS:
        current = current.parent
    return current


class _ModuleFacts:
    """Collects one file's ``exports`` and ``module_bindings``."""

    def __init__(self, analysis: _Analysis, symlink: bool = False) -> None:
        self.analysis = analysis
        self.source = analysis.source
        self.has_decorator = False
        self.entries: dict[str, list[tuple[Any, ...]]] = {}
        self.stars: list[str] = []
        self.commonjs = False
        self.opaque = False
        self.symlink = symlink
        self.taints: set[str] = set()
        # Every static specifier (imports, re-exports): the import graph
        # that promotes a test file a production file reaches (O-2).
        self.imports: set[str] = set()
        # Edges whose targets cannot be computed (fold 4): a production file
        # with one promotes every test file (O-2).
        self.uncomputable = False
        self._names: dict[str, list[Any]] | None = None
        self._rebound: bool | None = None
        # P5-13: literal targets of ``createRequire(__filename)``.
        self.filename_taints: set[str] = set()
        self.ns_uses: set[tuple[str, str, str]] = set()
        # Run-wide causes (E5-3): routes that may rewrite any module's
        # exports object. The Tier 1 ``*`` wildcard alone is not one.
        self.shutoff: set[str] = set()
        if analysis.evaluator:
            self.shutoff.add(CAUSE_EVALUATOR)

    # -- exports (section 9.3) ----------------------------------------------

    def _add(self, name: str | None, entry: tuple[Any, ...]) -> None:
        if name is None:
            self.opaque = True
            return
        bucket = self.entries.setdefault(name, [])
        if entry not in bucket:
            bucket.append(entry)

    def exports(self) -> None:
        for statement in self.analysis.root.named_children:
            if statement.type == "export_statement":
                self._export_statement(statement)

    def _export_statement(self, statement: Any) -> None:
        source_node = statement.child_by_field_name("source")
        if source_node is not None:
            self._reexport(statement, source_node)
            return
        default = _has_token(statement, "default")
        declaration = statement.child_by_field_name("declaration")
        if declaration is not None:
            self._declaration(declaration, default)
            return
        value = statement.child_by_field_name("value")
        if value is not None:
            inner = value
            while inner is not None and inner.type in _WRAPPERS:
                named = inner.named_children
                if not named:
                    break
                inner = named[-1] if inner.type == "type_assertion" else named[0]
            if inner is not None and inner.type == "identifier":
                self._add("default", ("local", _text(inner, self.source)))
            else:
                self._add("default", ("none", "expression-bound"))
            return
        clause = next(
            (
                child
                for child in statement.named_children
                if child.type == "export_clause"
            ),
            None,
        )
        if clause is not None:
            type_only = _has_token(statement, "type")
            for spec in clause.named_children:
                if spec.type != "export_specifier":
                    continue
                local = spec.child_by_field_name("name")
                alias = spec.child_by_field_name("alias") or local
                if local is None or local.type != "identifier":
                    # ``export { "a" }`` without ``from`` is not valid.
                    self.opaque = True
                    continue
                name = module_export_name(alias, self.source)
                if type_only or _has_token(spec, "type"):
                    self._add(name, ("type",))
                else:
                    self._add(name, ("local", _text(local, self.source)))
            return
        if _has_token(statement, "="):
            # ``export = x``: a CommonJS export assignment.
            self.commonjs = True
            return
        if _has_token(statement, "namespace") and _has_token(statement, "as"):
            # ``export as namespace X`` declares a UMD global for scripts;
            # it changes no export of the module.
            return
        self.opaque = True

    def _declaration(self, declaration: Any, default: bool) -> None:
        node = declaration
        if node.type == "ambient_declaration":
            node = next(iter(node.named_children), None)
            if node is None:
                self.opaque = True
                return
        if node.type in _TYPE_DECLARATIONS:
            name = node.child_by_field_name("name")
            self._add(
                "default" if default else module_export_name(name, self.source),
                ("type",),
            )
            return
        if node.type in _VARIABLE_DECLARATIONS and not default:
            from .js_scope import pattern_names

            for declarator in node.named_children:
                if declarator.type != "variable_declarator":
                    continue
                name = declarator.child_by_field_name("name")
                if name is None:
                    continue
                for ident in pattern_names(name):
                    text = _text(ident, self.source)
                    self._add(text, ("local", text))
            return
        if node.type in _LOCAL_DECLARATIONS:
            if node.type == "import_alias":
                name = next(
                    (c for c in node.named_children if c.type == "identifier"), None
                )
            else:
                name = node.child_by_field_name("name")
            while name is not None and name.type == "nested_identifier":
                # ``export namespace A.B {}`` exports ``A``.
                name = next(iter(name.named_children), None)
            if name is None or name.type not in ("identifier", "type_identifier"):
                self.opaque = True
                return
            local = _text(name, self.source)
            self._add("default" if default else local, ("local", local))
            return
        self.opaque = True

    def _reexport(self, statement: Any, source_node: Any) -> None:
        specifier = decode_string_literal(source_node, self.source)
        type_only = _has_token(statement, "type")
        if not type_only:
            self._mark_node_builtin_load(specifier)
        if specifier is None or any(
            child.type == "import_attribute" for child in statement.named_children
        ):
            self.opaque = True
            if specifier is None:
                self.shutoff.add(CAUSE_MODULE_SYSTEM)
            elif is_relative_specifier(specifier):
                # ``export … from './m' with {…}`` still reads ``./m``.
                self.taints.add(specifier)
            return
        self.imports.add(specifier)
        if specifier in _MODULE_SYSTEM_SPECIFIERS:
            self.shutoff.add(CAUSE_MODULE_SYSTEM)
        for child in statement.named_children:
            if child.type == "namespace_export":
                # ``export * as x from``: a namespace object, never callable.
                # It escapes the namespace, so the module is tainted.
                name_node = next(
                    (
                        c
                        for c in child.named_children
                        if c.type in ("identifier", "string")
                    ),
                    None,
                )
                name = module_export_name(name_node, self.source)
                self._add(
                    name, ("type",) if type_only else ("none", "namespace-export")
                )
                if not type_only:
                    self.taints.add(specifier)
                return
            if child.type == "export_clause":
                for spec in child.named_children:
                    if spec.type != "export_specifier":
                        continue
                    local = spec.child_by_field_name("name")
                    alias = spec.child_by_field_name("alias") or local
                    imported = module_export_name(local, self.source)
                    name = module_export_name(alias, self.source)
                    if imported is None:
                        self.opaque = True
                        continue
                    if type_only or _has_token(spec, "type"):
                        self._add(name, ("type",))
                    else:
                        self._add(name, ("reexport", specifier, imported))
                return
        if _has_token(statement, "*"):
            if not type_only:
                # ``export type * from`` re-exports types only.
                self.stars.append(specifier)
            return
        self.opaque = True

    def export_table(self) -> dict[str, Any]:
        table: dict[str, Any] = {}
        for name, entries in sorted(self.entries.items()):
            values = [entry for entry in entries if entry != ("type",)]
            if len(values) > 1:
                table[name] = {"kind": "none", "reason": "mixed-bindings"}
            elif not values:
                table[name] = {"kind": "none", "reason": "type-only"}
            else:
                table[name] = self._entry(values[0])
        return table

    def _entry(self, entry: tuple[Any, ...]) -> dict[str, Any]:
        kind = entry[0]
        if kind == "local":
            outcome = self.analysis.top_level_outcome(str(entry[1]))
            return {
                "kind": "local",
                "outcome": outcome,
                # E5-1 (A2/B-5): ``ns.f()`` passes the exports object as
                # ``this`` under CommonJS emit, so a proven declaration that
                # mentions ``this`` or ``super`` anywhere is not callable
                # through a namespace.
                "this": self._mentions_this(outcome),
            }
        if kind == "reexport":
            return {"kind": "reexport", "source": entry[1], "name": entry[2]}
        return {"kind": "none", "reason": entry[1]}

    def _mentions_this(self, outcome: dict[str, Any]) -> bool:
        if outcome.get("outcome") != "local":
            return False
        root = self.analysis.root
        for node_type, start, end in outcome.get("proof", ()):
            node = root.descendant_for_byte_range(int(start), int(end))
            while node is not None and node.type != node_type:
                node = node.parent
            if node is None or (node.start_byte, node.end_byte) != (start, end):
                return True
            if any(item.type in ("this", "super") for item in _walk(node)):
                return True
        return False

    # -- CommonJS reach, taints and run-wide causes ------------------------

    def _mark_node_builtin_load(self, specifier: str | None) -> None:
        if specifier in _EVALUATOR_SPECIFIERS:
            self.shutoff.add(CAUSE_EVALUATOR)
        elif specifier in _PROCESS_SPECIFIERS:
            self.shutoff.add(CAUSE_MODULE_SYSTEM)

    def module_system(self) -> None:
        analysis = self.analysis
        handled: set[int] = set()
        for node in _walk(analysis.root):
            kind = node.type
            if kind == "decorator":
                self.has_decorator = True
            elif kind in _MODULE_SYSTEM_NAME_TOKENS:
                self._name(node, handled)
            elif kind == "call_expression":
                self._loader_call(node, handled)
            elif kind == "with_statement":
                # Lookups in this body can reach properties on the with object
                # before consulting lexical bindings.
                self.shutoff.add(CAUSE_DYNAMIC_SCOPE)
            elif kind == "import_require_clause":
                source_node = node.child_by_field_name("source")
                specifier = _literal_value(source_node, self.source)
                if specifier is not None and specifier not in _MODULE_SYSTEM_SPECIFIERS:
                    if not _has_token(node.parent, "type"):
                        # ``import p = require('process')`` is never exempt:
                        # ``--module preserve`` emits a free ``require`` call,
                        # a global lookup in an ES module (R-699-7).
                        self._mark_node_builtin_load(specifier)
                    self.taints.add(specifier)
                else:
                    self.shutoff.add(CAUSE_MODULE_SYSTEM)
            elif kind == "import_statement":
                source_node = node.child_by_field_name("source")
                if source_node is not None:
                    specifier = decode_string_literal(source_node, self.source)
                    if specifier in _PROCESS_SPECIFIERS and not _has_token(
                        node, "type"
                    ):
                        self._mark_process_load(
                            source_node,
                            self._process_import_names(node),
                            handled,
                        )
                    elif not _has_token(node, "type"):
                        self._mark_node_builtin_load(specifier)
                    if specifier is None or (
                        specifier in _MODULE_SYSTEM_SPECIFIERS
                        and not self._inert_module_import(node)
                    ):
                        self.shutoff.add(CAUSE_MODULE_SYSTEM)
                    elif specifier not in _MODULE_SYSTEM_SPECIFIERS:
                        self.imports.add(specifier)
            elif kind in ("jsx_text", "html_character_reference"):
                self._jsx_text(node)
            elif kind == "string" and _parent_type(node) == "jsx_attribute":
                # A JSX attribute string decodes HTML character references,
                # not JS escapes (R-718-3).
                if any(
                    value in _MODULE_SYSTEM_NAMES or value in _MODULE_SYSTEM_TOKEN_NAMES
                    for value in decode_jsx_text(_text(node, self.source)[1:-1])
                ):
                    self.shutoff.add(CAUSE_MODULE_SYSTEM)
            elif kind == "string" and node.id not in handled:
                # Matched on the value sloppy code gives the literal (legacy
                # octal escapes decode); a malformed literal fails closed.
                value = decode_js_string_sloppy(_text(node, self.source))
                if (
                    value is None
                    or value in _MODULE_SYSTEM_NAMES
                    or value in _MODULE_SYSTEM_TOKEN_NAMES
                    or self._stack_trace_hook(node, value)
                ):
                    self.shutoff.add(CAUSE_MODULE_SYSTEM)
            elif kind == "template_string" and node.id not in handled:
                cooked = cook_template(node, self.source)
                if (
                    cooked is None
                    or any(
                        name in part for part in cooked for name in _MODULE_SYSTEM_NAMES
                    )
                    or any(part in _MODULE_SYSTEM_TOKEN_NAMES for part in cooked)
                    or (len(cooked) == 1 and self._stack_trace_hook(node, cooked[0]))
                ):
                    self.shutoff.add(CAUSE_MODULE_SYSTEM)
            elif kind == "regex_pattern":
                pattern = _text(node, self.source)
                if any(name in pattern for name in _MODULE_SYSTEM_TOKEN_NAMES):
                    self.shutoff.add(CAUSE_MODULE_SYSTEM)
            elif kind == "meta_property":
                if not self._inert_import_meta(node):
                    self.shutoff.add(CAUSE_DYNAMIC_LOADER)
            elif kind == "this":
                if module_level(node):
                    self.commonjs = True
        if "arguments" in self.analysis.program.bindings:
            # P5-48: a module-scope declaration of ``arguments`` in any form
            # (``var``, a function, ...) still names the CommonJS wrapper's
            # object in sloppy code, whose ``arguments[1]`` is ``require``.
            self.shutoff.add(CAUSE_DYNAMIC_LOADER)
        for target in self.analysis.assignment_targets:
            # R-699-9: a write to the CommonJS wrapper's ``require`` through a
            # pattern element, a default or a loop head (``[require] = [f]``,
            # ``({ a: require } = o)``, ``for ([require] of xs)``) declares
            # nothing, yet ``f`` then receives every later static import's
            # specifier, ``"process"`` included.
            if _text(target, self.source) == "require" and self._free_or_top(
                target, "require"
            ):
                self.shutoff.add(CAUSE_DYNAMIC_LOADER)
        self._import_writes()
        self._namespace_uses()

    def _jsx_text(self, node: Any) -> None:
        """Substring-match one run of JSX text after entity decoding.

        tree-sitter splits a run at each character reference; the run is
        one string child at runtime. JSX whitespace folding only trims or
        joins lines with a space, so it never makes a new substring."""
        if _parent_type(node) not in ("jsx_element", "jsx_fragment"):
            return
        previous = node.prev_named_sibling
        if previous is not None and previous.type in _JSX_TEXT_PARTS:
            return
        last = node
        while (
            last.next_named_sibling is not None
            and last.next_named_sibling.type in _JSX_TEXT_PARTS
        ):
            last = last.next_named_sibling
        raw = self.source[node.start_byte : last.end_byte].decode(
            "utf-8", errors="replace"
        )
        if any(
            name in value
            for value in decode_jsx_text(raw)
            for name in (*_MODULE_SYSTEM_TOKEN_NAMES, *_MODULE_SYSTEM_NAMES)
        ):
            self.shutoff.add(CAUSE_MODULE_SYSTEM)

    def _stack_trace_hook(self, node: Any, name: str) -> bool:
        """Match a stack-formatting hook only on the global Error receiver."""
        if name != "prepareStackTrace" or _in_type_position(node):
            return False
        outer = _climb_wrappers(node)
        parent = outer.parent
        return (
            parent is not None
            and (parent.type, _field_of(parent, outer))
            in (("member_expression", "property"), ("subscript_expression", "index"))
            and self._global_builtin(parent.child_by_field_name("object"), "Error")
        )

    def _global_builtin(self, node: Any, name: str) -> bool:
        from .js_scope import unwrap

        node = unwrap(node)
        if node is None:
            return False
        if node.type == "identifier":
            return _text(node, self.source) == name and self.analysis._refers_to_global(
                node, name
            )
        return self.analysis._member_key(
            node
        ) == name and self.analysis._is_global_object(
            node.child_by_field_name("object"), receiver=True
        )

    def _inert_import_meta(self, node: Any) -> bool:
        """``import.meta.url`` and other plain reads; Bun's
        ``import.meta.require``, a computed key or a bare use is not."""
        outer = _climb_wrappers(node)
        parent = outer.parent
        if parent is None or parent.type != "member_expression":
            return False
        prop = parent.child_by_field_name("property")
        if (
            not _same(parent.child_by_field_name("object"), outer)
            or prop is None
            or prop.type != "property_identifier"
        ):
            return False
        name = _text(prop, self.source)
        if name in _IMPORT_META_LOADERS:
            self.uncomputable = True
            return True
        return name in _IMPORT_META_READS

    def _free_or_top(self, node: Any, name: str) -> bool:
        """Whether the ordinary lookup at ``node`` finds no binding of
        ``name``, or the program's own (E5-2): only then can the name be
        the CommonJS wrapper's ``module``, ``exports`` or ``require``."""
        scope = self.analysis._binding_scope(node, name)
        return scope is None or scope is self.analysis.program

    def _loader_call(self, node: Any, handled: set[int]) -> None:
        from .js_scope import unwrap

        function = unwrap(node.child_by_field_name("function"))
        if function is None:
            return
        if self._module_mock(node, function):
            return
        is_require = function.type == "identifier" and (
            _text(function, self.source) == "require"
        )
        if not is_require and function.type != "import":
            return
        if function.type == "import" and _in_type_position(node):
            # ``typeof import('./x')`` is erased at emit.
            return
        if is_require:
            handled.add(function.id)
        arguments = node.child_by_field_name("arguments")
        named = (
            [child for child in arguments.named_children if child.type != "comment"]
            if arguments is not None
            else []
        )
        literal = named[0] if len(named) == 1 else None
        specifier = _literal_value(literal, self.source)
        if specifier is None:
            if not is_require or self._free_or_top(function, "require"):
                self.shutoff.add(CAUSE_DYNAMIC_LOADER)
            return
        if specifier in _MODULE_SYSTEM_SPECIFIERS:
            self.shutoff.add(CAUSE_MODULE_SYSTEM)
            return
        # No ``require`` call of ``process`` is exempt (R-699-7): in an ES
        # module a free ``require`` is a global lookup that another file can
        # set (``globalThis.require = f``), and ``f`` then receives the
        # literal. Only a static import is the loader in either goal.
        self._mark_node_builtin_load(specifier)
        # A literal ``require`` taints whatever binds the name: an AMD
        # ``require`` parameter loads modules too.
        self.taints.add(specifier)

    def _module_mock(self, call: Any, function: Any) -> bool:
        """P5-3: ``jest.mock('<x>')`` and the rest of :data:`MODULE_MOCKS`,
        with ``jest``/``vi`` free or imported from ``@jest/globals``/
        ``vitest`` (by the ordinary lookup). The mocked module is replaced
        for the callers in the mocking file's scope: a relative literal
        taints it; a non-literal is an unresolvable writer; a bare
        specifier names a package outside the run."""
        if function.type != "member_expression":
            return False
        from .js_scope import unwrap

        obj = unwrap(function.child_by_field_name("object"))
        prop = function.child_by_field_name("property")
        if obj is None or obj.type != "identifier" or prop is None:
            return False
        framework = self._framework(obj)
        if framework is None or _text(prop, self.source) not in MODULE_MOCKS[framework]:
            return False
        arguments = call.child_by_field_name("arguments")
        named = (
            [child for child in arguments.named_children if child.type != "comment"]
            if arguments is not None
            else []
        )
        specifier = _literal_value(named[0], self.source) if named else None
        if specifier is None:
            self.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
        else:
            self.taints.add(specifier)
        return True

    def _framework(self, node: Any) -> str | None:
        """``jest`` or ``vi`` when ``node`` names the framework object."""
        name = _text(node, self.source)
        scope = self.analysis._binding_scope(node, name)
        if scope is None:
            return name if name in MODULE_MOCKS else None
        for binding in scope.bindings.get(name, ()):
            info = binding.info or {}
            if binding.cls != "import":
                continue
            imported = info.get("name")
            if (
                imported in MOCK_PACKAGES
                and info.get("source") == MOCK_PACKAGES[imported]
            ):
                return str(imported)
        return None

    def _name(self, node: Any, handled: set[int]) -> None:
        from .js_scope import _declaration_name

        text = _text(node, self.source)
        if text in _MODULE_SYSTEM_TOKEN_NAMES:
            # Any role (R-718-3): a variable or parameter name also reaches
            # runtime as a string, through a function's inferred ``.name``
            # or an export key.
            if text == "process":
                if node.type == "identifier" and (
                    self.analysis._binding_scope(node, text) is None
                    and self._inert_process_operand(node)
                ):
                    return
            self.shutoff.add(CAUSE_MODULE_SYSTEM)
            return
        if node.type == "property_identifier":
            # A property cannot be looked up: match the name.
            if text in _MODULE_SYSTEM_NAMES or self._stack_trace_hook(node, text):
                self.shutoff.add(CAUSE_MODULE_SYSTEM)
            return
        if node.type in ("statement_identifier", "type_identifier"):
            return
        if node.type == "identifier" and _declaration_name(node):
            return
        if text in _MODULE_SYSTEM_NAMES:
            scope = self.analysis._binding_scope(node, text)
            bindings = scope.bindings.get(text, ()) if scope is not None else ()
            if any(
                binding.cls == "import"
                and (binding.info or {}).get("source") in _MODULE_SYSTEM_SPECIFIERS
                for binding in bindings
            ):
                # A binding imported from ``module`` itself: the import
                # statement's closed allow-list decides (fold 3).
                return
            if scope is None or any(binding.cls == "import" for binding in bindings):
                self.shutoff.add(CAUSE_MODULE_SYSTEM)
            return
        if text == "require":
            if (
                node.id not in handled
                and self._free_or_top(node, text)
                and not self._inert_require(node)
            ):
                # ``require.cache``, an alias of ``require``, ``require``
                # passed on: any module's exports may be reached.
                self.shutoff.add(CAUSE_DYNAMIC_LOADER)
            return
        if text in _COMMONJS_NAMES:
            if not self._free_or_top(node, text):
                return
            self.commonjs = True
            if (
                text == "module"
                and not self._module_exports(node)
                and not self._inert_operand(node)
            ):
                self.shutoff.add(CAUSE_MODULE_OBJECT)
            return
        if text == "arguments" and module_level(node):
            if self.analysis._binding_scope(node, text) is None:
                self.commonjs = True
                if not self._inert_operand(node):
                    # P5-44: the CommonJS wrapper's ``arguments`` holds
                    # ``require`` (``arguments[1]``). Only ``typeof`` and an
                    # equality operand leave it unused (a closed list).
                    self.shutoff.add(CAUSE_DYNAMIC_LOADER)

    # -- fold 3: closed allow-lists for ``module`` imports and createRequire

    def _mark_process_load(
        self, literal: Any, names: list[Any], handled: set[int]
    ) -> None:
        """Exempt a process load only if every bound name stays in safe uses."""
        if not names or self._require_rebound():
            self.shutoff.add(CAUSE_MODULE_SYSTEM)
            return
        for name in names:
            if name is None or name.type != "identifier":
                self.shutoff.add(CAUSE_MODULE_SYSTEM)
                return
            text = _text(name, self.source)
            scope = self.analysis._binding_scope(name, text)
            uses = self._uses(scope, text) if scope is not None else None
            if not uses or not all(self._inert_process_operand(use) for use in uses):
                self.shutoff.add(CAUSE_MODULE_SYSTEM)
                return
        handled.add(literal.id)

    def _require_rebound(self) -> bool:
        """R-699-7 item 1: whether any scope of the file binds ``require``.

        A CommonJS emit routes the file's static imports through the
        program-scope ``require``, so such a binding receives the literal
        ``"process"`` and no process load in the file is exempt. A
        type-only import and an ambient declaration bind no runtime value.
        """
        if self._rebound is None:
            from .js_scope import TYPE_ONLY

            self._rebound = any(
                binding.cls != TYPE_ONLY and not binding.ambient
                for scope in self.analysis.scopes.values()
                for binding in scope.bindings.get("require", ())
            )
        return self._rebound

    def _process_import_names(self, statement: Any) -> list[Any]:
        if any(child.type == "import_attribute" for child in statement.named_children):
            return []
        names = []
        for clause in statement.named_children:
            if clause.type != "import_clause":
                continue
            for part in clause.named_children:
                if part.type == "identifier":
                    names.append(part)
                elif part.type == "namespace_import":
                    names.extend(
                        c for c in part.named_children if c.type == "identifier"
                    )
                elif part.type == "named_imports":
                    for spec in part.named_children:
                        if spec.type == "import_specifier" and not _has_token(
                            spec, "type"
                        ):
                            names.append(
                                spec.child_by_field_name("alias")
                                or spec.child_by_field_name("name")
                            )
        return names

    def _inert_process_operand(self, node: Any) -> bool:
        outer = _climb_wrappers(node)
        parent = outer.parent
        if parent is None:
            return False
        if parent.type == "unary_expression":
            return self._operator(parent) == "typeof"
        if parent.type == "binary_expression":
            operator = self._operator(parent)
            if operator in ("===", "!=="):
                return True
            if operator in ("==", "!="):
                # R-699-4 item 3: loose equality runs ToPrimitive(process),
                # which calls an inherited valueOf/toString with ``this ===
                # process``, unless the other side is ``null``.
                return self._null_literal(parent, outer)
            return operator == "&&" and _same(parent.child_by_field_name("left"), outer)
        if parent.type != "member_expression" or not _same(
            parent.child_by_field_name("object"), outer
        ):
            return False
        prop = parent.child_by_field_name("property")
        name = _text(prop, self.source) if prop is not None else ""
        if name not in _INERT_PROCESS_MEMBERS:
            return False
        member = _climb_wrappers(parent)
        if self._member_written(member):
            # R-699-4 item 2: an installed method runs with ``this ===
            # process`` when anyone calls the member.
            return False
        if name in _PROCESS_LISTENER_MEMBERS:
            return self._discarded_arrow_listen(member)
        access = member.parent
        # E5-3 already covers constructor and escaped keys. A dynamic key
        # on this receiver has no known spelling for that check.
        return not (
            access is not None
            and access.type == "subscript_expression"
            and _same(access.child_by_field_name("object"), member)
            and self.analysis._member_key(access) is None
        )

    def _operator(self, node: Any) -> str:
        operator = node.child_by_field_name("operator")
        return _text(operator, self.source) if operator is not None else ""

    def _null_literal(self, comparison: Any, operand: Any) -> bool:
        """Whether the other operand of ``comparison`` is ``null``, where
        IsLooselyEqual returns before ToPrimitive. ``undefined`` is not
        taken: it is an identifier a parameter may rebind."""
        from .js_scope import unwrap

        left = comparison.child_by_field_name("left")
        other = unwrap(
            comparison.child_by_field_name("right") if _same(left, operand) else left
        )
        return other is not None and other.type == "null"

    def _member_written(self, member: Any) -> bool:
        """Whether ``member`` is the target of an assignment (plain,
        compound or logical), ``++``/``--``, ``delete`` or a ``for…in/of``
        head, directly or inside a destructuring pattern."""
        current = member
        while True:
            parent = current.parent
            if parent is None:
                return False
            kind = parent.type
            if kind in _WRAPPERS or kind in _WRITE_PATTERN_STEPS:
                current = parent
                continue
            field = _WRITE_FIELD_STEPS.get(kind)
            if field is not None:
                if not _same(parent.child_by_field_name(field), current):
                    return False
                current = parent
                continue
            if kind in (
                "assignment_expression",
                "augmented_assignment_expression",
                "for_in_statement",
            ):
                return _same(parent.child_by_field_name("left"), current)
            if kind == "update_expression":
                return True
            if kind == "unary_expression":
                return self._operator(parent) == "delete"
            return False

    def _discarded_arrow_listen(self, member: Any) -> bool:
        """R-699-4 item 1: ``process.on(event, () => …);`` as a statement.
        The call returns ``process`` (discarded here) and calls each listener
        with ``this === process`` (an arrow keeps its lexical ``this``)."""
        from .js_scope import unwrap

        call = member.parent
        if call is None or call.type != "call_expression":
            return False
        statement = _climb_wrappers(call).parent
        if statement is None or statement.type != "expression_statement":
            return False
        arguments = call.child_by_field_name("arguments")
        named = (
            [child for child in arguments.named_children if child.type != "comment"]
            if arguments is not None and arguments.type == "arguments"
            else []
        )
        return (
            len(named) >= 2
            and named[0].type != "spread_element"
            and all(
                (listener := unwrap(argument)) is not None
                and listener.type == "arrow_function"
                for argument in named[1:]
            )
        )

    def _uses(self, scope: Any, name: str) -> list[Any] | None:
        """Every use of the binding of ``name`` in ``scope``, found by the
        ordinary lookup at each use site; ``None`` when the scope binds the
        name more than once or a use is not a plain identifier."""
        from .js_scope import _declaration_name

        if len(scope.bindings.get(name, ())) != 1:
            return None
        uses: list[Any] = []
        for node in self._name_index().get(name, ()):
            if node.type == "identifier" and _declaration_name(node):
                continue
            if self.analysis._binding_scope(node, name) is not scope:
                continue
            if node.type != "identifier":
                return None
            uses.append(node)
        return uses

    def _name_index(self) -> dict[str, list[Any]]:
        """Identifier-like nodes by spelling, in source order, from one walk
        of the file (R-699-4 item 5: no full scan per bound name)."""
        if self._names is None:
            index: dict[str, list[Any]] = {}
            for node in _walk(self.analysis.root):
                if node.type in _USE_NAME_TOKENS:
                    index.setdefault(_text(node, self.source), []).append(node)
            self._names = index
        return self._names

    def _written(self, node: Any) -> bool:
        return any(_same(node, target) for target in self.analysis.assignment_targets)

    def _inert_module_import(self, statement: Any) -> bool:
        """Fold 3, item 1: an import from ``module``/``node:module`` is inert
        when it is type-only, or when every binding is a named import of
        :data:`INERT_MODULE_EXPORTS` used only by reads and calls, or of
        ``createRequire`` used only as a local require function (item 2).
        A default or namespace import, any other name and import attributes
        stay run-wide."""
        if _has_token(statement, "type"):
            return True
        if any(child.type == "import_attribute" for child in statement.named_children):
            return False
        program = self.analysis.program
        for clause in statement.named_children:
            if clause.type != "import_clause":
                continue
            for part in clause.named_children:
                if part.type != "named_imports":
                    return False
                for spec in part.named_children:
                    if spec.type != "import_specifier":
                        continue
                    if _has_token(spec, "type"):
                        continue
                    imported = module_export_name(
                        spec.child_by_field_name("name"), self.source
                    )
                    local = spec.child_by_field_name(
                        "alias"
                    ) or spec.child_by_field_name("name")
                    if local is None or local.type != "identifier":
                        return False
                    uses = self._uses(program, _text(local, self.source))
                    if uses is None:
                        return False
                    if imported in INERT_MODULE_EXPORTS:
                        if any(self._written(use) for use in uses):
                            return False
                    elif imported == "createRequire":
                        if not all(self._local_require(use) for use in uses):
                            return False
                    else:
                        return False
        return True

    def _local_require(self, use: Any) -> bool:
        """Fold 3, item 2: ``const r = createRequire(<anything>)``, with every
        use of ``r`` (by lookup) a direct call with one literal argument,
        which taints its target like ``require``, or ``r.resolve(<literal>)``."""
        outer = _climb_wrappers(use)
        call = outer.parent
        if (
            call is None
            or call.type != "call_expression"
            or not _same(call.child_by_field_name("function"), outer)
        ):
            return False
        wrapped = _climb_wrappers(call)
        declarator = wrapped.parent
        if (
            declarator is None
            or declarator.type != "variable_declarator"
            or not _same(declarator.child_by_field_name("value"), wrapped)
        ):
            return False
        declaration = declarator.parent
        name = declarator.child_by_field_name("name")
        if (
            declaration is None
            or declaration.type != "lexical_declaration"
            or not _has_token(declaration, "const")
            or name is None
            or name.type != "identifier"
        ):
            return False
        text = _text(name, self.source)
        scope = self.analysis._binding_scope(name, text)
        if scope is None:
            return False
        # P5-1: Node resolves ``r('<lit>')`` from the base given to
        # createRequire, so only the importer's own file is a base whose
        # targets this resolution computes.
        own_base = self._own_file_base(call)
        uses = self._uses(scope, text)
        if uses is None:
            return False
        literals: list[str] = []
        for item in uses:
            outer = _climb_wrappers(item)
            parent = outer.parent
            if parent is None:
                return False
            if parent.type == "call_expression" and _same(
                parent.child_by_field_name("function"), outer
            ):
                arguments = parent
            elif (
                parent.type == "member_expression"
                and _same(parent.child_by_field_name("object"), outer)
                and _text(parent.child_by_field_name("property"), self.source)
                == "resolve"
                and parent.child_by_field_name("property").type == "property_identifier"
            ):
                wrapped_member = _climb_wrappers(parent)
                arguments = wrapped_member.parent
                if (
                    arguments is None
                    or arguments.type != "call_expression"
                    or not _same(
                        arguments.child_by_field_name("function"), wrapped_member
                    )
                ):
                    return False
                arguments = (
                    None if self._single_literal(arguments) is None else arguments
                )
                if arguments is None:
                    return False
                continue
            else:
                return False
            literal = self._single_literal(arguments)
            if literal is None or literal in _MODULE_SYSTEM_SPECIFIERS:
                return False
            self._mark_node_builtin_load(literal)
            literals.append(literal)
        if own_base == "filename":
            # P5-13 (c), P5-20: the engine taints these only if no run file
            # can write a global ``__filename``.
            self.filename_taints.update(literals)
        elif own_base:
            # A literal call loads its target like ``require``: it taints it.
            self.taints.update(literals)
        elif literals:
            # Another base: the targets cannot be computed (P5-1).
            self.uncomputable = True
            self.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
        return True

    def _own_file_base(self, call: Any) -> str | bool:
        """P5-1/P5-13: the closed list of createRequire bases that name the
        importer's own file. ``import.meta.url`` and ``import.meta.filename``
        when the file writes no ``import.meta`` property (``True``);
        ``__filename`` when the lookup finds no binding of it in the file
        and nothing in the file writes it (``"filename"``: the engine also
        requires that no run file can write a global ``__filename`` unless
        the file is CommonJS)."""
        arguments = call.child_by_field_name("arguments")
        named = (
            [child for child in arguments.named_children if child.type != "comment"]
            if arguments is not None
            else []
        )
        if len(named) != 1:
            return False
        from .js_scope import unwrap

        base = unwrap(named[0])
        if base is None:
            return False
        if base.type == "identifier":
            if (
                _text(base, self.source) != "__filename"
                or self.analysis._binding_scope(base, "__filename") is not None
                or any(
                    _text(target, self.source) == "__filename"
                    for target in self.analysis.assignment_targets
                )
            ):
                return False
            return "filename"
        if base.type != "member_expression":
            return False
        obj = unwrap(base.child_by_field_name("object"))
        prop = base.child_by_field_name("property")
        return (
            obj is not None
            and obj.type == "meta_property"
            and prop is not None
            and prop.type == "property_identifier"
            and _text(prop, self.source) in _OWN_FILE_META
            and not self._import_meta_written()
        )

    def _import_meta_written(self) -> bool:
        """P5-13 (b): any ``import.meta.<p>`` in a write position (an
        assignment, compound or destructuring target, an update, a
        ``for … of/in`` head or a ``delete``)."""
        for node in _walk(self.analysis.root):
            if node.type != "meta_property":
                continue
            child, current = node, node.parent
            while current is not None and current.type not in (
                "expression_statement",
                "statement_block",
                "program",
            ):
                field = _field_of(current, child)
                if (
                    current.type
                    in (
                        "assignment_expression",
                        "augmented_assignment_expression",
                        "for_in_statement",
                    )
                    and field == "left"
                ):
                    return True
                if current.type == "update_expression":
                    return True
                if current.type == "unary_expression":
                    operator = current.child_by_field_name("operator")
                    if operator is not None and operator.type == "delete":
                        return True
                child, current = current, current.parent
        return False

    def _single_literal(self, call: Any) -> str | None:
        arguments = call.child_by_field_name("arguments")
        named = (
            [child for child in arguments.named_children if child.type != "comment"]
            if arguments is not None
            else []
        )
        return _literal_value(named[0], self.source) if len(named) == 1 else None

    def _inert_operand(self, node: Any) -> bool:
        """``typeof x`` and an operand of ``===``/``!==``/``==``/``!=``: the
        value is compared, never handed on (a closed allow-list)."""
        outer = _climb_wrappers(node)
        parent = outer.parent
        if parent is None:
            return False
        operator = parent.child_by_field_name("operator")
        text = _text(operator, self.source) if operator is not None else ""
        return (parent.type == "unary_expression" and text == "typeof") or (
            parent.type == "binary_expression" and text in _EQUALITY
        )

    def _inert_require(self, node: Any) -> bool:
        """``typeof require``, ``require.resolve(…)`` (a path string) and
        ``require.main`` compared (``require.main === module``)."""
        if self._inert_operand(node):
            return True
        outer = _climb_wrappers(node)
        member = outer.parent
        if member is None or member.type != "member_expression":
            return False
        prop = member.child_by_field_name("property")
        if not _same(member.child_by_field_name("object"), outer) or prop is None:
            return False
        name = _text(prop, self.source)
        wrapped = _climb_wrappers(member)
        parent = wrapped.parent
        if name == "resolve":
            return (
                parent is not None
                and parent.type == "call_expression"
                and _same(parent.child_by_field_name("function"), wrapped)
            )
        return name == "main" and self._inert_operand(member)

    def _module_exports(self, node: Any) -> bool:
        """Whether ``module`` is the object of ``module.exports``."""
        if node.type != "identifier":
            return False
        outer = _climb_wrappers(node)
        parent = outer.parent
        if parent is None or parent.type != "member_expression":
            return False
        prop = parent.child_by_field_name("property")
        return (
            _same(parent.child_by_field_name("object"), outer)
            and prop is not None
            and prop.type == "property_identifier"
            and _text(prop, self.source) == "exports"
        )

    def _import_binding(self, node: Any, name: str) -> dict[str, Any] | None:
        """The import binding the ordinary lookup at ``node`` finds."""
        from .js_scope import IMPORT

        scope = self.analysis._binding_scope(node, name)
        if scope is not self.analysis.program:
            return None
        for binding in scope.bindings.get(name, ()):
            if binding.cls == IMPORT:
                return dict(binding.info or {})
        return None

    def _import_writes(self) -> None:
        """E5-1 (A1): a write to an import binding (assignment, compound or
        logical assignment, update, destructuring, a ``for … of/in`` head,
        through casts) is ``svc_1.t = …`` under CommonJS emit: it taints
        the binding's module."""
        for target in self.analysis.assignment_targets:
            name = _text(target, self.source)
            info = self._import_binding(target, name)
            if info is not None:
                self.taints.add(str(info.get("source", "")))

    def _namespace_uses(self) -> None:
        """Taint the module of a namespace import used outside the read
        allow-list; record every allow-listed ``ns.name`` for the engine,
        which checks the name is a verified export (E5-1)."""
        from .js_scope import _declaration_name

        program = self.analysis.program
        namespaces: dict[str, str] = {}
        for name, bindings in program.bindings.items():
            for binding in bindings:
                info = binding.info or {}
                if binding.cls == "import" and info.get("form") == "namespace":
                    namespaces[name] = str(info.get("source", ""))
        if not namespaces:
            return
        for node in _walk(self.analysis.root):
            if node.type not in (
                "identifier",
                "shorthand_property_identifier",
                "shorthand_property_identifier_pattern",
            ):
                continue
            name = _text(node, self.source)
            if name not in namespaces:
                continue
            if node.type == "identifier" and _declaration_name(node):
                if node.parent is not None and node.parent.type == "namespace_import":
                    continue
            # The ordinary lookup at the use site decides which binding the
            # name means; a shadowing binding is not the namespace.
            if self.analysis._binding_scope(node, name) is not program:
                continue
            use = self._namespace_use(node)
            if use is None:
                self.taints.add(namespaces[name])
            elif use[0] != "type":
                self.ns_uses.add((namespaces[name], use[1], use[0]))

    def _namespace_use(self, node: Any) -> tuple[str, str] | None:
        """``(kind, member)`` for an allow-listed use: ``("call", f)`` for
        ``ns.f(…)``, ``("read", f)`` for a read of ``ns.f``, ``("type", "")``
        in type space; ``None`` for anything else."""
        if node.type != "identifier":
            return None
        if _in_type_position(node):
            return ("type", "")
        outer = _climb_wrappers(node)
        member = outer.parent
        if member is None or member.type != "member_expression":
            return None
        prop = member.child_by_field_name("property")
        if (
            not _same(member.child_by_field_name("object"), outer)
            or prop is None
            or prop.type != "property_identifier"
        ):
            return None
        name = _text(prop, self.source)
        wrapped = _climb_wrappers(member)
        parent = wrapped.parent
        if parent is None:
            return None
        field = _field_of(parent, wrapped)
        if parent.type == "call_expression" and field == "function":
            # The callee's ``this`` is the namespace (also ``(ns.f)()``).
            return ("call", name)
        if parent.type == "unary_expression":
            operator = parent.child_by_field_name("operator")
            if operator is not None and operator.type != "delete":
                return ("read", name)
            return None
        if (parent.type, field) in _READ_POSITIONS or (
            parent.type,
            None,
        ) in _READ_POSITIONS:
            return ("read", name)
        return None

    def module_bindings(self) -> dict[str, Any]:
        # P5-20: no CommonJS shortcut. A file on this path imports from
        # ``module`` (ESM syntax), so CommonJS hints never prove that
        # ``__filename`` is the wrapper's parameter; the engine's run-wide
        # writer check always decides.
        return {
            "stars": list(self.stars),
            "has_decorator": self.has_decorator,
            "commonjs": self.commonjs or self.analysis.goal == "script",
            "opaque": self.opaque,
            "symlink": self.symlink,
            "taints": sorted(self.taints),
            "imports": sorted(self.imports),
            "uncomputable": self.uncomputable,
            "filename_taints": sorted(self.filename_taints),
            "ns_uses": [list(use) for use in sorted(self.ns_uses)],
            "shutoff": sorted(self.shutoff),
        }


def _in_type_position(node: Any) -> bool:
    """Whether ``node`` sits in type space (erased at emit)."""
    current = node.parent
    while current is not None and current.type not in (
        "expression_statement",
        "program",
        "statement_block",
    ):
        if current.type in _TYPE_CONTEXTS:
            return True
        current = current.parent
    return False


def _literal_value(node: Any, source: bytes) -> str | None:
    """A string literal's value, or a substitution-free template's cooked
    text; ``None`` otherwise."""
    if node is None:
        return None
    if node.type == "string":
        return decode_string_literal(node, source)
    if node.type == "template_string" and not any(
        part.type == "template_substitution" for part in node.named_children
    ):
        cooked = cook_template(node, source)
        return cooked[0] if cooked else None
    return None


def module_level(node: Any) -> bool:
    """Whether ``this`` (or ``arguments``) at ``node`` is the module's own
    value: the CommonJS wrapper's ``exports`` (E5-1, B-4).

    The Tier 1 scope rule, applied exhaustively: arrow functions inherit
    ``this``; a non-arrow function or method rebinds it for its parameters
    and body, but not for a computed name or a decorator; an instance field
    initializer rebinds it (it runs in the constructor), but a computed field
    or method key and the ``extends`` clause do not. P5-49: a **static**
    field initializer and a static block count as module level, because tsc
    below ES2022 hoists them to module scope (``C.r = arguments[1];``). The
    walk is shared by the module-level ``this`` and ``arguments`` checks.
    """
    child, current = node, node.parent
    while current is not None:
        kind = current.type
        if kind in _NON_ARROW_FUNCTIONS:
            if _same(child, current.child_by_field_name("body")) or _same(
                child, current.child_by_field_name("parameters")
            ):
                return False
        elif kind in ("field_definition", "public_field_definition"):
            if _same(child, current.child_by_field_name("value")) and not (
                _has_token(current, "static")
            ):
                return False
        child, current = current, current.parent
    return True


def is_relative_specifier(specifier: str) -> bool:
    return specifier in (".", "..") or specifier.startswith(("./", "../"))


def module_facts(
    analysis: _Analysis, symlink: bool = False
) -> tuple[dict[str, Any], dict[str, Any]]:
    """``(exports, module_bindings)`` for one analyzed JS/TS file."""
    facts = _ModuleFacts(analysis, symlink)
    facts.exports()
    facts.module_system()
    return facts.export_table(), facts.module_bindings()
