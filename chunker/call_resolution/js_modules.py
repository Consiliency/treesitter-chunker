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
``taint_all``
    The file may write any module's exports: ``require`` or ``import()``
    used other than with one string argument, ``module`` used other than as
    ``module.exports``, the names ``mainModule``, ``createRequire`` and
    ``getBuiltinModule``, an import of ``module`` or ``node:module``, a
    specifier that does not decode, or a code evaluator or other global-object
    escape (the analysis's ``*`` script global, section 7.2).

Uses of the sensitive values (a namespace import, ``require``, ``module``)
are classified by a closed allow-list after unwrapping parentheses and TS
wrappers, and a namespace import's uses are found by the ordinary lookup at
each use site, so a shadowing binding is never mistaken for it.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from .js_strings import decode_string_literal, module_export_name

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
# Names that reach the CommonJS module system from anywhere.
_MODULE_SYSTEM_NAMES = frozenset({"mainModule", "createRequire", "getBuiltinModule"})
_MODULE_SYSTEM_SPECIFIERS = frozenset({"module", "node:module"})
_COMMONJS_NAMES = frozenset({"exports", "module"})
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
    }
)


def _same(left: Any, right: Any) -> bool:
    return left is not None and right is not None and left.id == right.id


def _has_token(node: Any, token: str) -> bool:
    return any(not child.is_named and child.type == token for child in node.children)


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

    def __init__(self, analysis: _Analysis) -> None:
        self.analysis = analysis
        self.source = analysis.source
        self.entries: dict[str, list[tuple[Any, ...]]] = {}
        self.stars: list[str] = []
        self.commonjs = False
        self.opaque = False
        self.taints: set[str] = set()
        self.taint_all = bool(analysis.global_wildcard)

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
        if specifier is None or any(
            child.type == "import_attribute" for child in statement.named_children
        ):
            self.opaque = True
            if specifier is None:
                self.taint_all = True
            return
        if specifier in _MODULE_SYSTEM_SPECIFIERS:
            self.taint_all = True
        type_only = _has_token(statement, "type")
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
            return {"kind": "local", "outcome": outcome}
        if kind == "reexport":
            return {"kind": "reexport", "source": entry[1], "name": entry[2]}
        return {"kind": "none", "reason": entry[1]}

    # -- CommonJS reach and taints ------------------------------------------

    def module_system(self) -> None:
        analysis = self.analysis
        handled: set[int] = set()
        for node in _walk(analysis.root):
            kind = node.type
            if kind == "call_expression":
                self._loader_call(node, handled)
            elif kind == "import_require_clause":
                self._taint_specifier(node.child_by_field_name("source"))
            elif kind == "import_statement":
                source_node = node.child_by_field_name("source")
                if source_node is not None:
                    specifier = decode_string_literal(source_node, self.source)
                    if specifier is None or specifier in _MODULE_SYSTEM_SPECIFIERS:
                        self.taint_all = True
            elif kind in (
                "identifier",
                "property_identifier",
                "shorthand_property_identifier",
                "shorthand_property_identifier_pattern",
            ):
                self._name(node, handled)
            elif kind == "string":
                if decode_string_literal(node, self.source) in _MODULE_SYSTEM_NAMES:
                    self.taint_all = True
            elif kind == "template_string":
                text = _text(node, self.source)
                if any(name in text for name in _MODULE_SYSTEM_NAMES):
                    self.taint_all = True
            elif kind == "this":
                if self._top_level(node):
                    self.commonjs = True
        self._namespace_uses()

    def _loader_call(self, node: Any, handled: set[int]) -> None:
        from .js_scope import unwrap

        function = unwrap(node.child_by_field_name("function"))
        if function is None:
            return
        is_require = function.type == "identifier" and (
            _text(function, self.source) == "require"
        )
        if not is_require and function.type != "import":
            return
        if is_require:
            handled.add(function.id)
        arguments = node.child_by_field_name("arguments")
        named = (
            [child for child in arguments.named_children if child.type != "comment"]
            if arguments is not None
            else []
        )
        if len(named) != 1 or named[0].type != "string":
            self.taint_all = True
            return
        self._taint_specifier(named[0])

    def _taint_specifier(self, node: Any) -> None:
        specifier = decode_string_literal(node, self.source)
        if specifier is None or specifier in _MODULE_SYSTEM_SPECIFIERS:
            self.taint_all = True
            return
        self.taints.add(specifier)

    def _name(self, node: Any, handled: set[int]) -> None:
        text = _text(node, self.source)
        if text in _MODULE_SYSTEM_NAMES:
            self.taint_all = True
            return
        if node.type == "property_identifier":
            return
        if text == "require" and node.id not in handled:
            from .js_scope import _declaration_name

            if not _declaration_name(node):
                # ``require.cache``, an alias of ``require``, ``require`` passed
                # on: any module's exports may be reached.
                self.taint_all = True
            return
        if text in _COMMONJS_NAMES:
            self.commonjs = True
            if text == "module" and not self._module_exports(node):
                self.taint_all = True
            return
        if text == "arguments" and self._top_level(node):
            self.commonjs = True

    def _module_exports(self, node: Any) -> bool:
        """Whether ``module`` is the object of ``module.exports``."""
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

    @staticmethod
    def _top_level(node: Any) -> bool:
        """Whether ``this`` or ``arguments`` belongs to no non-arrow function
        or class member: the module's own (the CommonJS wrapper's) value."""
        current = node.parent
        while current is not None:
            if current.type in _NON_ARROW_FUNCTIONS or current.type in (
                "class_body",
                "class_static_block",
            ):
                return False
            current = current.parent
        return True

    def _namespace_uses(self) -> None:
        """Taint the module of a namespace import used outside the allow-list."""
        from .js_scope import IMPORT, _declaration_name

        analysis = self.analysis
        program = analysis.program
        namespaces: dict[str, str] = {}
        for name, bindings in program.bindings.items():
            for binding in bindings:
                info = binding.info or {}
                if binding.cls == IMPORT and info.get("form") == "namespace":
                    namespaces[name] = str(info.get("source", ""))
        if not namespaces:
            return
        for node in _walk(analysis.root):
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
            if analysis._binding_scope(node, name) is not program:
                continue
            if not self._safe_namespace_use(node):
                self.taints.add(namespaces[name])

    def _safe_namespace_use(self, node: Any) -> bool:
        if node.type != "identifier":
            return False
        current = node.parent
        while current is not None and current.type not in (
            "expression_statement",
            "program",
            "statement_block",
        ):
            if current.type in _TYPE_CONTEXTS:
                return True
            current = current.parent
        outer = _climb_wrappers(node)
        member = outer.parent
        if member is None or member.type != "member_expression":
            return False
        prop = member.child_by_field_name("property")
        if (
            not _same(member.child_by_field_name("object"), outer)
            or prop is None
            or prop.type != "property_identifier"
        ):
            return False
        wrapped = _climb_wrappers(member)
        parent = wrapped.parent
        if parent is None:
            return False
        if parent.type == "unary_expression":
            operator = parent.child_by_field_name("operator")
            return operator is not None and operator.type != "delete"
        field = _field_of(parent, wrapped)
        return (parent.type, field) in _READ_POSITIONS or (
            parent.type,
            None,
        ) in _READ_POSITIONS

    def module_bindings(self) -> dict[str, Any]:
        return {
            "stars": list(self.stars),
            "commonjs": self.commonjs or self.analysis.goal == "script",
            "opaque": self.opaque,
            "taints": sorted(self.taints),
            "taint_all": self.taint_all,
        }


def module_facts(analysis: _Analysis) -> tuple[dict[str, Any], dict[str, Any]]:
    """``(exports, module_bindings)`` for one analyzed JS/TS file."""
    facts = _ModuleFacts(analysis)
    facts.exports()
    facts.module_system()
    return facts.export_table(), facts.module_bindings()
