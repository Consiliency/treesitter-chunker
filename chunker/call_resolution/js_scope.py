"""Scope analyzer for JavaScript, TypeScript and TSX (plan section 7.2).

One pass over the tree builds every scope and its bindings; then each call
fact's callee is looked up through the scope chain, innermost first:

- block scopes (``statement_block``, ``switch_body``, ``for_statement``,
  ``for_in_statement``, ``catch_clause``);
- ``class_static_block`` bodies, which are var scopes of their own;
- function bodies;
- the **parameter scope** between a function and its parent: the parameters
  and, for non-arrow functions, the implicit ``arguments``. Default values
  and other parameter expressions look up from here outward, skipping the
  body;
- a named function or generator expression's, or a named class
  expression's, **self scope**: its own name, bound as a non-symbol
  (``self-binding``);
- TS namespace bodies (``internal_module``, ``module``, ``declare global``);
- ``program``.

``class_body`` binds no bare names, so method bodies and field initializers
continue in the scope enclosing the class. Lookup does not depend on
position: ``let``, ``const`` and ``class`` bind across their whole block
(TDZ), and function declarations and ``var`` across their whole var scope.

The outcome of a lookup is ``local`` with the declarations the group rule
proves (section 7.4), ``import`` for a value import (it proves nothing in
``structural`` mode), or ``none`` with one reason (section 7.6, with R-1's
precedence):

1. a ``none`` the lookup meets on the way (``dynamic-scope`` for a scope
   that encloses a direct ``eval``, also ``(eval)(s)``, ``eval!(s)`` or
   ``(eval as any)(s)``, or for a ``with`` around the call;
   ``unmapped`` for a scope holding a fail-closed node kind);
2. the binding's own reason: ``type-only``, ``block-function``,
   ``unmapped``, a non-symbol binding's class (``parameter``,
   ``local-variable``, ``expression-bound``, ``self-binding``),
   ``mixed-bindings``, ``reassigned``;
3. the group rule for a set of symbol declarations: non-callable kinds
   (enums, namespaces) are dropped first (``non-callable`` if nothing is
   left, B7), then ``ambient`` (any ambient member), then ``bodyless``; one
   body proves itself (``t1.lexical``); in TS, k >= 1 bodyless signatures
   directly followed by one ``function_declaration`` body, contiguous, prove
   the body (``t1.ts_overload``); signatures with any other body shape prove
   every member, which narrows but never resolves; two or more bodies prove
   the bodies as an ambiguous group;
4. only when the lookup would otherwise prove something, the interim
   deferrals of this head: ``namespace-deferred`` for a lookup through a
   namespace body (also when it ends unbound there), and
   ``script-goal-deferred`` for a lookup that lands on a script-goal
   ``program``. Hoisting (``t1.js_hoist``), script globals, namespace merging
   and inherited ambient status replace them in a later change.

A name with no binding in the file is ``unbound``. For a member callee
(``m.t``) the head identifier is looked up; a head that is not an identifier
(``this``, ``super``, a call) has no binding (``unbound``). Member calls are
never eligible in Tier 1, so their outcome is recorded only.

Every named node the pass visits is classified through the allow-list
(section 7.5). A fail-closed kind, including an unclassified one, marks the
scopes it appears in, and any lookup reaching them gives ``none(unmapped)``.
Writes are collected fail-closed: every identifier under an assignment
``left``, update ``argument`` or bare ``for ... of/in`` target counts, through
parentheses and TS wrappers, except the object of a member access. A
computed method name is visited in the enclosing scope. The pass is
recursive; a tree too deep for it raises ``RecursionError`` (see
:data:`MAX_DEPTH`), which the caller turns into ``supported: false``
(section 5.3).

Proof declarations are the nodes the chunker emits as symbols: the
declaration itself, never an enclosing ``export_statement`` (N-1), and for a
single ``const`` bound to an arrow or function expression, the arrow or
function expression node.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import allowlist

# Deep trees fail closed with RecursionError (section 5.3). This counter
# grows by one or two per tree level, and the pass uses up to three Python
# frames per level, so Python's own recursion limit (1000 by default) can
# stop deeply nested blocks, ``else if`` chains, calls or functions first, at
# roughly 200 to 500 levels depending on the construct. Either way the error
# is the same, and the file keeps its off-mode edges. (The chunker itself
# stops at depth 900.)
MAX_DEPTH = 500

RULE_TS_OVERLOAD = "t1.ts_overload"

# Top-level statements that make a program an ES module (section 5.2).
_MODULE_STATEMENTS = frozenset({"import_statement", "export_statement"})
_TS_LANGUAGES = frozenset({"typescript", "tsx"})

# Function-like nodes: a parameter scope, and a function scope for a block
# body. Only expressions have a self scope; method names are properties.
_FUNCTIONS = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "function_expression",
        "generator_function",
        "arrow_function",
        "method_definition",
    }
)
_FUNCTION_DECLARATIONS = frozenset(
    {"function_declaration", "generator_function_declaration"}
)
_SELF_NAMED_FUNCTIONS = frozenset({"function_expression", "generator_function"})
_CLASSES = frozenset({"class", "class_declaration", "abstract_class_declaration"})
_NAMESPACES = frozenset({"internal_module", "module"})
# Block scopes keyed by their own node.
_BLOCK_SCOPE_NODES = frozenset(
    {"switch_body", "for_statement", "for_in_statement", "catch_clause"}
)
# Wrappers between a declaration and the statement list it belongs to.
_DECLARATION_WRAPPERS = frozenset({"export_statement", "ambient_declaration"})
_FUNCTION_VALUES = frozenset({"arrow_function", "function_expression"})
_EXPRESSION_FUNCTIONS = _FUNCTION_VALUES | {"generator_function"}

# Binding classes. Every class other than SYMBOL, IMPORT and TYPE_ONLY is
# also the ``none`` reason a lookup that meets it reports.
SYMBOL = "symbol"
IMPORT = "import"
TYPE_ONLY = "type-only"
PARAMETER = "parameter"
LOCAL_VARIABLE = "local-variable"
EXPRESSION_BOUND = "expression-bound"
SELF_BINDING = "self-binding"
BLOCK_FUNCTION = "block-function"
UNMAPPED = "unmapped"

# Symbol kinds. Enums and namespaces are value declarations but not callable.
_FUNCTION = "function"
_CLASS = "class"
_SIGNATURE = "signature"
_ENUM = "enum"
_NAMESPACE = "namespace"
_NON_CALLABLE = frozenset({_ENUM, _NAMESPACE})
_BODIES = frozenset({_FUNCTION, _CLASS})

# Scope kinds.
_PROGRAM = "program"
_FUNCTION_SCOPE = "function"
_PARAMS = "params"
_SELF = "self"
_BLOCK = "block"
_NAMESPACE_SCOPE = "namespace"
_STATIC = "static"


def program_goal(root: Any) -> str:
    """``"module"`` if any top-level statement imports or exports."""
    for child in root.named_children:
        if child.type in _MODULE_STATEMENTS:
            return "module"
    return "script"


def _none(reason: str) -> dict[str, Any]:
    return {"outcome": "none", "reason": reason}


@dataclass(frozen=True, eq=False)
class _Binding:
    """One declaration of one name in one scope."""

    cls: str
    decl: Any = None
    kind: str = ""
    statement: Any = None
    ambient: bool = False
    info: Mapping[str, str] | None = None


@dataclass(eq=False)
class _Scope:
    """A scope, its bindings and what makes its lookups fail closed."""

    kind: str
    node: Any
    bindings: dict[str, list[_Binding]] = field(default_factory=dict)
    reassigned: set[str] = field(default_factory=set)
    dynamic: bool = False
    poisoned: bool = False

    def bind(self, name: str, binding: _Binding) -> None:
        self.bindings.setdefault(name, []).append(binding)


def _text(node: Any, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _same(left: Any, right: Any) -> bool:
    return left is not None and right is not None and left.id == right.id


def _has_token(node: Any, token: str) -> bool:
    return any(not child.is_named and child.type == token for child in node.children)


def pattern_names(node: Any) -> list[Any]:
    """The identifier nodes a binding or assignment pattern binds, in order."""
    names: list[Any] = []
    stack = [node]
    while stack:
        current = stack.pop()
        kind = current.type
        if kind in ("identifier", "shorthand_property_identifier_pattern"):
            names.append(current)
        elif kind in (
            "object_pattern",
            "array_pattern",
            "rest_pattern",
            "parenthesized_expression",
        ):
            stack.extend(reversed(current.named_children))
        elif kind == "pair_pattern":
            value = current.child_by_field_name("value")
            if value is not None:
                stack.append(value)
        elif kind in ("assignment_pattern", "object_assignment_pattern"):
            left = current.child_by_field_name("left")
            if left is not None:
                stack.append(left)
        elif kind in ("required_parameter", "optional_parameter"):
            pattern = current.child_by_field_name("pattern")
            if pattern is not None:
                stack.append(pattern)
    return names


# Expressions that wrap a callee or an assignment target without changing
# what it refers to: ``(t)``, ``t!``, ``t as T``, ``t satisfies T``, ``<T>t``.
_TRANSPARENT_WRAPPERS = frozenset(
    {
        "parenthesized_expression",
        "non_null_expression",
        "as_expression",
        "satisfies_expression",
        "type_assertion",
    }
)
# Property names that hold no expression; any other method name (a
# ``computed_property_name``) is evaluated and must be visited.
_PLAIN_NAMES = frozenset(
    {
        "identifier",
        "property_identifier",
        "private_property_identifier",
        "type_identifier",
        "string",
        "number",
    }
)
_MEMBER_ACCESS = frozenset({"member_expression", "subscript_expression"})


def write_targets(node: Any) -> list[Any]:
    """Identifiers an assignment ``left`` or update ``argument`` may write.

    Fail closed: every identifier below the target counts as a write, through
    parentheses, TS wrappers (``as``, ``satisfies``, ``!``, ``<T>``),
    patterns and their defaults, except the object of a member or subscript
    access (``t.x = 1`` writes a property, not ``t``). Over-marking only adds
    ``none(reassigned)``.
    """
    names: list[Any] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type in ("identifier", "shorthand_property_identifier_pattern"):
            names.append(current)
        elif current.type in _MEMBER_ACCESS:
            obj = current.child_by_field_name("object")
            stack.extend(
                child
                for child in reversed(current.named_children)
                if not _same(child, obj)
            )
        else:
            stack.extend(reversed(current.named_children))
    return names


def unwrap(node: Any) -> Any:
    """``node`` without transparent wrappers (``(eval)`` and ``eval!`` -> ``eval``)."""
    current = node
    while current is not None and current.type in _TRANSPARENT_WRAPPERS:
        named = current.named_children
        if not named:
            return current
        # ``<T>x``: the expression follows the type arguments.
        current = named[-1] if current.type == "type_assertion" else named[0]
    return current


class _Analysis:
    """Scopes and bindings of one file, and lookups through them."""

    def __init__(self, root: Any, source: bytes, language: str) -> None:
        self.root = root
        self.source = source
        self.language = language
        self.typescript = language in _TS_LANGUAGES
        self.goal = program_goal(root)
        self.scopes: dict[tuple[int, str], _Scope] = {}
        self.assignment_targets: list[Any] = []
        self.eval_calls: list[Any] = []
        self.handlers: dict[str, Callable[[Any, _Scope, _Scope, int], None]] = {
            "function_declaration": self._function,
            "generator_function_declaration": self._function,
            "function_expression": self._function,
            "generator_function": self._function,
            "arrow_function": self._function,
            "method_definition": self._function,
            "class": self._class,
            "class_declaration": self._class,
            "abstract_class_declaration": self._class,
            "class_static_block": self._static_block,
            "statement_block": self._block,
            "switch_body": self._switch_body,
            "for_statement": self._for,
            "for_in_statement": self._for_in,
            "catch_clause": self._catch,
            "lexical_declaration": self._declaration,
            "variable_declaration": self._declaration,
            "using_declaration": self._declaration,
            "import_statement": self._import,
            "import_alias": self._import_alias,
            "function_signature": self._signature,
            "enum_declaration": self._enum,
            "internal_module": self._namespace,
            "module": self._namespace,
            "ambient_declaration": self._ambient,
            "assignment_expression": self._assignment,
            "augmented_assignment_expression": self._assignment,
            "update_expression": self._assignment,
            "call_expression": self._call,
        }
        program = self._scope(_PROGRAM, root, root, "scope")
        self._statements(root, program, program, 0)
        for target in self.assignment_targets:
            scope = self._binding_scope(target, _text(target, source))
            if scope is not None:
                scope.reassigned.add(_text(target, source))
        for call in self.eval_calls:
            # A direct eval can declare or assign any binding visible from its
            # site, so every scope from there out to ``program`` is dynamic.
            for _, _, scope in self._chain(call):
                if scope is not None:
                    scope.dynamic = True

    # -- building -----------------------------------------------------------

    def _scope(self, kind: str, node: Any, key_node: Any, role: str) -> _Scope:
        scope = _Scope(kind, node)
        self.scopes[(key_node.id, role)] = scope
        return scope

    def visit(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        if depth > MAX_DEPTH:
            msg = "JS/TS scope analysis exceeds safe traversal depth"
            raise RecursionError(msg)
        if not node.is_named:
            return
        entry = allowlist.classify(self.language, node.type)
        if entry.classification == allowlist.FAIL_CLOSED:
            # Unknown binding forms make every lookup through here unmapped.
            var.poisoned = True
            lex.poisoned = True
            return
        handler = self.handlers.get(node.type)
        if handler is not None:
            handler(node, var, lex, depth)
            return
        for child in node.named_children:
            self.visit(child, var, lex, depth + 1)

    def _statements(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        for child in node.named_children:
            self.visit(child, var, lex, depth + 1)

    def _visit_except(
        self, node: Any, skip: Sequence[Any], var: _Scope, lex: _Scope, depth: int
    ) -> None:
        skipped = {item.id for item in skip if item is not None}
        for child in node.named_children:
            if child.id not in skipped:
                self.visit(child, var, lex, depth + 1)

    def _statement_of(self, decl: Any, scope: _Scope) -> tuple[Any, bool]:
        """The statement holding ``decl`` in ``scope``, and its ambient status."""
        current = decl
        ambient = False
        while current.parent is not None and not _same(current.parent, scope.node):
            current = current.parent
            ambient = ambient or current.type == "ambient_declaration"
        return current, ambient

    def _symbol(self, scope: _Scope, name: str, decl: Any, kind: str) -> None:
        statement, ambient = self._statement_of(decl, scope)
        scope.bind(name, _Binding(SYMBOL, decl, kind, statement, ambient))

    def _is_direct(self, decl: Any, var: _Scope, lex: _Scope) -> bool:
        """Whether ``decl`` is a statement directly in its var scope's body."""
        if lex is not var:
            return False
        current = decl
        while current.parent is not None and current.parent.type in (
            _DECLARATION_WRAPPERS
        ):
            current = current.parent
        return _same(current.parent, var.node)

    def _function(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        name = node.child_by_field_name("name")
        if node.type in _FUNCTION_DECLARATIONS and name is not None:
            text = _text(name, self.source)
            if self._is_direct(node, var, lex):
                self._symbol(var, text, node, _FUNCTION)
            else:
                # 2.6(b): a block-level declaration gives none in every
                # lookup, inside its block and (Annex B) in its var scope.
                lex.bind(text, _Binding(BLOCK_FUNCTION))
                if var is not lex:
                    var.bind(text, _Binding(BLOCK_FUNCTION))
        params_scope = self._scope(_PARAMS, node, node, _PARAMS)
        if node.type != "arrow_function":
            params_scope.bind("arguments", _Binding(PARAMETER))
        if node.type in _SELF_NAMED_FUNCTIONS and name is not None:
            self._scope(_SELF, node, node, _SELF).bind(
                _text(name, self.source), _Binding(SELF_BINDING)
            )
        parameters = node.child_by_field_name("parameters") or node.child_by_field_name(
            "parameter"
        )
        if parameters is not None:
            if parameters.type == "identifier":
                params_scope.bind(_text(parameters, self.source), _Binding(PARAMETER))
            else:
                for child in parameters.named_children:
                    for ident in pattern_names(child):
                        params_scope.bind(
                            _text(ident, self.source), _Binding(PARAMETER)
                        )
                self.visit(parameters, params_scope, params_scope, depth + 1)
        body = node.child_by_field_name("body")
        if body is not None:
            if body.type == "statement_block":
                function_scope = self._scope(_FUNCTION_SCOPE, body, body, "scope")
                self._statements(body, function_scope, function_scope, depth + 1)
            else:
                self.visit(body, params_scope, params_scope, depth + 1)
        # A computed method name is evaluated in the enclosing scope.
        plain_name = name if name is not None and name.type in _PLAIN_NAMES else None
        self._visit_except(node, (plain_name, parameters, body), var, lex, depth)

    def _class(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        name = node.child_by_field_name("name")
        if name is not None:
            text = _text(name, self.source)
            if node.type == "class":
                self._scope(_SELF, node, node, _SELF).bind(text, _Binding(SELF_BINDING))
            else:
                self._symbol(lex, text, node, _CLASS)
        for child in node.named_children:
            if _same(child, name):
                continue
            if child.type == "class_body":
                # class_body binds no bare names: members look up outside.
                self._statements(child, var, lex, depth + 1)
            else:
                self.visit(child, var, lex, depth + 1)

    def _static_block(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        body = node.child_by_field_name("body")
        if body is not None:
            scope = self._scope(_STATIC, body, body, "scope")
            self._statements(body, scope, scope, depth + 1)
        self._visit_except(node, (body,), var, lex, depth)

    def _block(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        if node.parent is not None and node.parent.type == "ambient_declaration":
            # ``declare global { ... }``: an ambient namespace-like body.
            scope = self._scope(_NAMESPACE_SCOPE, node, node, "scope")
            self._statements(node, scope, scope, depth + 1)
            return
        block = self._scope(_BLOCK, node, node, "scope")
        self._statements(node, var, block, depth + 1)

    def _switch_body(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        block = self._scope(_BLOCK, node, node, "scope")
        self._statements(node, var, block, depth + 1)

    def _for(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        block = self._scope(_BLOCK, node, node, "scope")
        self._statements(node, var, block, depth + 1)

    def _for_in(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        block = self._scope(_BLOCK, node, node, "scope")
        kind = node.child_by_field_name("kind")
        left = node.child_by_field_name("left")
        if left is not None:
            keyword = kind.type if kind is not None else ""
            names = pattern_names(left)
            if keyword in ("const", "let", "using"):
                for ident in names:
                    block.bind(_text(ident, self.source), _Binding(LOCAL_VARIABLE))
            elif keyword == "var":
                for ident in names:
                    var.bind(_text(ident, self.source), _Binding(LOCAL_VARIABLE))
            elif kind is None:
                self.assignment_targets.extend(write_targets(left))
            else:
                block.poisoned = True
        self._statements(node, var, block, depth + 1)

    def _catch(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        scope = self._scope(_BLOCK, node, node, "scope")
        parameter = node.child_by_field_name("parameter")
        if parameter is not None:
            for ident in pattern_names(parameter):
                scope.bind(_text(ident, self.source), _Binding(LOCAL_VARIABLE))
        self._statements(node, var, scope, depth + 1)

    def _declaration(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        target = var if node.type == "variable_declaration" else lex
        declarators = [
            child
            for child in node.named_children
            if child.type == "variable_declarator"
        ]
        single_const = (
            node.type == "lexical_declaration"
            and _has_token(node, "const")
            and len(declarators) == 1
        )
        for declarator in declarators:
            name = declarator.child_by_field_name("name")
            value = declarator.child_by_field_name("value")
            if name is None:
                continue
            if name.type == "identifier":
                text = _text(name, self.source)
                if (
                    single_const
                    and value is not None
                    and value.type in _FUNCTION_VALUES
                ):
                    # 2.6(c): a single const bound to a function is a symbol.
                    self._symbol(target, text, value, _FUNCTION)
                elif value is not None and value.type in _EXPRESSION_FUNCTIONS:
                    target.bind(text, _Binding(EXPRESSION_BOUND))
                else:
                    target.bind(text, _Binding(LOCAL_VARIABLE))
            else:
                for ident in pattern_names(name):
                    target.bind(_text(ident, self.source), _Binding(LOCAL_VARIABLE))
        self._statements(node, var, lex, depth + 1)

    def _import(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        type_only = _has_token(node, "type")
        source_node = node.child_by_field_name("source")
        source = _text(source_node, self.source)[1:-1] if source_node else ""
        for child in node.named_children:
            if child.type == "import_require_clause":
                # ``import x = require()``: CommonJS is deferred (non-symbol).
                for ident in child.named_children:
                    if ident.type == "identifier":
                        lex.bind(_text(ident, self.source), _Binding(LOCAL_VARIABLE))
                        break
            elif child.type == "import_clause":
                for part in child.named_children:
                    self._import_clause_part(part, lex, source, type_only)
        self._statements(node, var, lex, depth + 1)

    def _import_clause_part(
        self, part: Any, lex: _Scope, source: str, type_only: bool
    ) -> None:
        if part.type == "identifier":
            self._bind_import(lex, part, source, "default", "default", type_only)
        elif part.type == "namespace_import":
            for ident in part.named_children:
                if ident.type == "identifier":
                    self._bind_import(lex, ident, source, "*", "namespace", type_only)
        elif part.type == "named_imports":
            for spec in part.named_children:
                if spec.type != "import_specifier":
                    continue
                imported = spec.child_by_field_name("name")
                local = spec.child_by_field_name("alias") or imported
                if imported is None or local is None:
                    continue
                self._bind_import(
                    lex,
                    local,
                    source,
                    _text(imported, self.source),
                    "named",
                    type_only or _has_token(spec, "type"),
                )

    def _bind_import(
        self,
        lex: _Scope,
        local: Any,
        source: str,
        imported: str,
        form: str,
        type_only: bool,
    ) -> None:
        name = _text(local, self.source)
        if type_only:
            lex.bind(name, _Binding(TYPE_ONLY))
            return
        info = {"source": source, "name": imported, "form": form}
        lex.bind(name, _Binding(IMPORT, info=info))

    def _import_alias(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        # TS ``import t = NS.f``: a value binding treated as non-symbol.
        for child in node.named_children:
            if child.type == "identifier":
                lex.bind(_text(child, self.source), _Binding(LOCAL_VARIABLE))
                break
        self._statements(node, var, lex, depth + 1)

    def _signature(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        name = node.child_by_field_name("name")
        if name is not None:
            scope = var if self._is_direct(node, var, lex) else lex
            self._symbol(scope, _text(name, self.source), node, _SIGNATURE)
        self._visit_except(node, (name,), var, lex, depth)

    def _enum(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        name = node.child_by_field_name("name")
        if name is not None:
            self._symbol(lex, _text(name, self.source), node, _ENUM)
        self._visit_except(node, (name,), var, lex, depth)

    def _namespace(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        name = node.child_by_field_name("name")
        head = name
        while head is not None and head.type == "nested_identifier":
            head = head.child_by_field_name("object") or (
                head.named_children[0] if head.named_children else None
            )
        if head is not None and head.type == "identifier":
            self._symbol(lex, _text(head, self.source), node, _NAMESPACE)
        body = node.child_by_field_name("body")
        if body is not None:
            scope = self._scope(_NAMESPACE_SCOPE, body, body, "scope")
            self._statements(body, scope, scope, depth + 1)
        self._visit_except(node, (name, body), var, lex, depth)

    def _ambient(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        # Bindings below record their ambient status from the wrapper chain.
        self._statements(node, var, lex, depth + 1)

    def _assignment(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        field = "argument" if node.type == "update_expression" else "left"
        target = node.child_by_field_name(field)
        if target is not None:
            names = write_targets(target)
            if _has_token(node, "using"):
                # TS lacks ``using`` declarations and parses them as an
                # assignment: fail closed (7.5).
                for ident in names:
                    lex.bind(_text(ident, self.source), _Binding(UNMAPPED))
            else:
                self.assignment_targets.extend(names)
        self._statements(node, var, lex, depth + 1)

    def _call(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        function = unwrap(node.child_by_field_name("function"))
        if (
            function is not None
            and function.type == "identifier"
            and _text(function, self.source) == "eval"
        ):
            # A direct eval, also ``(eval)(s)``, ``eval!(s)`` or
            # ``(eval as any)(s)``; its scopes are marked after the pass.
            self.eval_calls.append(node)
        self._statements(node, var, lex, depth + 1)

    # -- lookup -------------------------------------------------------------

    def _scopes_at(self, node: Any, child: Any) -> Iterator[_Scope]:
        kind = node.type
        if kind == "program" or kind == "statement_block" or kind in _BLOCK_SCOPE_NODES:
            scope = self.scopes.get((node.id, "scope"))
            if scope is not None:
                yield scope
        elif kind in _FUNCTIONS:
            parameters = node.child_by_field_name(
                "parameters"
            ) or node.child_by_field_name("parameter")
            if _same(child, node.child_by_field_name("body")) or _same(
                child, parameters
            ):
                for role in (_PARAMS, _SELF):
                    scope = self.scopes.get((node.id, role))
                    if scope is not None:
                        yield scope
        elif kind in _CLASSES and not _same(child, node.child_by_field_name("name")):
            scope = self.scopes.get((node.id, _SELF))
            if scope is not None:
                yield scope

    def _chain(self, ident: Any) -> Iterator[tuple[Any, Any, _Scope | None]]:
        """``(node, child, scope)`` from the identifier outward.

        ``scope`` is ``None`` for an ancestor that opens no scope.
        """
        child = ident
        node = ident.parent
        while node is not None:
            opened = False
            for scope in self._scopes_at(node, child):
                opened = True
                yield node, child, scope
            if not opened:
                yield node, child, None
            child, node = node, node.parent

    def _binding_scope(self, ident: Any, name: str) -> _Scope | None:
        for _, _, scope in self._chain(ident):
            if scope is not None and name in scope.bindings:
                return scope
        return None

    def lookup(self, ident: Any) -> dict[str, Any]:
        """The outcome of a value lookup of ``ident``'s name."""
        name = _text(ident, self.source)
        through_namespace = False
        for node, child, scope in self._chain(ident):
            if scope is None:
                if node.type == "with_statement" and _same(
                    child, node.child_by_field_name("body")
                ):
                    return _none("dynamic-scope")
                continue
            if scope.dynamic:
                return _none("dynamic-scope")
            if scope.poisoned:
                return _none(UNMAPPED)
            if scope.kind == _NAMESPACE_SCOPE:
                through_namespace = True
            bindings = scope.bindings.get(name)
            if bindings:
                return self._decide(scope, name, bindings, through_namespace)
        return _none("namespace-deferred" if through_namespace else "unbound")

    def _decide(
        self,
        scope: _Scope,
        name: str,
        bindings: Sequence[_Binding],
        through_namespace: bool,
    ) -> dict[str, Any]:
        value = [binding for binding in bindings if binding.cls != TYPE_ONLY]
        if not value:
            return _none(TYPE_ONLY)
        classes = {binding.cls for binding in value}
        if BLOCK_FUNCTION in classes:
            return _none(BLOCK_FUNCTION)
        if UNMAPPED in classes:
            return _none(UNMAPPED)
        symbols = [binding for binding in value if binding.cls == SYMBOL]
        imports = [binding for binding in value if binding.cls == IMPORT]
        others = [binding for binding in value if binding.cls not in (SYMBOL, IMPORT)]
        if others and not symbols and not imports:
            return _none(others[0].cls)
        if len(imports) > 1 or sum(map(bool, (symbols, imports, others))) > 1:
            return _none("mixed-bindings")
        if name in scope.reassigned:
            return _none("reassigned")
        if imports:
            outcome: dict[str, Any] = {
                "outcome": "import",
                "binding": dict(imports[0].info or {}),
            }
        else:
            outcome = self._group(scope, symbols)
            if outcome["outcome"] != "local":
                return outcome
        if through_namespace:
            return _none("namespace-deferred")
        if scope.kind == _PROGRAM and self.goal == "script":
            return _none("script-goal-deferred")
        return outcome

    def _group(self, scope: _Scope, symbols: Sequence[_Binding]) -> dict[str, Any]:
        """The group rule (section 7.4) for one name's symbol declarations."""
        callable_ = [
            binding for binding in symbols if binding.kind not in _NON_CALLABLE
        ]
        if not callable_:
            return _none("non-callable")
        if any(binding.ambient for binding in callable_):
            # Ambient wins over bodyless (R-1(iii)). A group that mixes
            # ambient and non-ambient members is invalid TS; it fails closed.
            return _none("ambient")
        bodies = [binding for binding in callable_ if binding.kind in _BODIES]
        if not bodies:
            return _none("bodyless")
        signatures = [binding for binding in callable_ if binding.kind == _SIGNATURE]
        rules: list[str] = []
        group: Sequence[_Binding] = bodies
        if len(bodies) == 1 and signatures:
            if self.typescript and self._overload_set(scope, signatures, bodies[0]):
                rules = [RULE_TS_OVERLOAD]
            else:
                # Not an overload set: prove every member, which narrows
                # but can never resolve.
                group = callable_
        proof = sorted(
            [binding.decl.type, binding.decl.start_byte, binding.decl.end_byte]
            for binding in group
        )
        return {"outcome": "local", "proof": proof, "rules": rules}

    def _overload_set(
        self, scope: _Scope, signatures: Sequence[_Binding], body: _Binding
    ) -> bool:
        """k >= 1 signatures then one ``function_declaration``, contiguous."""
        if body.decl.type != "function_declaration":
            return False
        statements = [
            child for child in scope.node.named_children if child.type != "comment"
        ]
        index = {
            statement.id: position for position, statement in enumerate(statements)
        }

        def position(member: _Binding) -> int:
            if member.statement is None:
                return -1
            return index.get(member.statement.id, -1)

        positions = sorted(position(member) for member in signatures)
        last = position(body)
        return positions[0] >= 0 and [*positions, last] == list(
            range(positions[0], positions[0] + len(positions) + 1)
        )


def _callee_head(node: Any) -> Any:
    """The identifier a callee looks up: itself, or a member chain's head."""
    head = node
    while head is not None and head.type in (
        "member_expression",
        "subscript_expression",
    ):
        head = head.child_by_field_name("object")
    return head if head is not None and head.type == "identifier" else None


def analyze(
    root: Any,
    source: bytes,
    language: str,
    call_facts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return partial scope facts: the goal and one outcome per call."""
    analysis = _Analysis(root, source, language)
    bindings: dict[str, Any] = {}
    for fact in call_facts:
        start = int(fact["callee_byte_start"])
        end = int(fact["callee_byte_end"])
        node = root.named_descendant_for_byte_range(start, end)
        if node is None or (node.start_byte, node.end_byte) != (start, end):
            # No node matches the callee span: leave the entry out, which
            # the engine reports as no-binding-fact (5.4).
            continue
        head = _callee_head(node)
        bindings[f"{start}:{end}"] = (
            analysis.lookup(head) if head is not None else _none("unbound")
        )
    return {"goal": analysis.goal, "bindings": bindings}
