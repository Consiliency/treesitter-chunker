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
- TS enum bodies: the members of every declaration of the enum shadow outer
  names in its initializers, and merged declarations make that set
  non-local, so every lookup that reaches an enum body fails closed
  (``enum-scope``);
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
   ``(eval as any)(s)``, or for a ``with`` around the call; ``enum-scope``
   for an enum body;
   ``unmapped`` for a scope holding a fail-closed node kind);
2. the binding's own reason: ``type-only``, ``block-function``,
   ``unmapped``, a non-symbol binding's class (``parameter``,
   ``local-variable``, ``expression-bound``, ``self-binding``),
   ``mixed-bindings``, ``reassigned``;
3. the group rule for a set of symbol declarations: non-callable kinds
   (enums, namespaces) are dropped first (``non-callable`` if nothing is
   left, B7), then ``ambient`` (any ambient member; ambient status is
   inherited from enclosing ``declare`` blocks), then ``bodyless``; one
   body proves itself (``t1.lexical``); in TS, k >= 1 bodyless signatures
   directly followed by one ``function_declaration`` body, contiguous, prove
   the body (``t1.ts_overload``); signatures with any other body shape prove
   every member, which narrows but never resolves; in plain JavaScript, two
   or more function declarations directly in one function body or script
   ``program`` prove the last one (``t1.js_hoist``); any other two or more
   bodies prove the bodies as an ambiguous group;
4. only when the lookup would otherwise prove something:
   ``namespace-merged`` for a lookup through a merged namespace body (also
   when it ends unbound there), one whose namespace has another namespace or
   enum declaration in its scope, is dotted (``namespace A.B``), is a
   ``declare module 'm'`` or ``declare global`` body, or lives in a script;
   and, for a lookup that lands on a script-goal ``program``, the outcome
   carries ``global``: the engine proves it only if no other file of the run
   declares the name in its ``script_globals`` (``script-global``).

Script globals (:meth:`_Analysis.script_globals`) are a script's top-level
names and implicit globals, ``declare global`` names, and names written
through the global object (``window``, ``globalThis``, ``self``, ``global``
and their alias chains, or ``this`` where it may be the global object);
``*`` when a global of unknown name may be written. In a script, such a
write also reassigns the top-level binding of that name. A body binding that
shares a parameter's name is reassigned when the function mentions
``arguments`` (the mapped arguments object aliases it).

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

A file in which any name is spelled with a Unicode escape (``\\u0074``,
``\\u{74}``) is not analyzed: :func:`analyze` raises
:class:`EscapedIdentifierError`, and the caller gives the file
``supported: false``, so its edges stay exactly as off (section 5.3). Names
are compared by their source spelling, so an escaped parameter, write or
``eval`` would otherwise be missed (Codex review of treesitter-chunker#689).

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
from .js_strings import decode_string_literal, module_export_name

# Deep trees fail closed with RecursionError (section 5.3). This counter
# grows by one or two per tree level, and the pass uses up to three Python
# frames per level, so Python's own recursion limit (1000 by default) can
# stop deeply nested blocks, ``else if`` chains, calls or functions first, at
# roughly 200 to 500 levels depending on the construct. Either way the error
# is the same, and the file keeps its off-mode edges. (The chunker itself
# stops at depth 900.)
MAX_DEPTH = 500

RULE_TS_OVERLOAD = "t1.ts_overload"
RULE_JS_HOIST = "t1.js_hoist"

# ``script_globals`` entry for a file that may write a global of any name: a
# global object written through a computed key or escaping into other code,
# or a reference to a code evaluator (section 7.2).
GLOBAL_WILDCARD = "*"
# Identifiers that name the global object when nothing in the file binds
# them, and the properties of the global object that are the global object.
_GLOBAL_OBJECTS = frozenset(
    {"window", "globalThis", "self", "global", "top", "parent", "frames"}
)
_GLOBAL_OBJECT_PROPERTIES = _GLOBAL_OBJECTS
# ``<any>.defaultView`` (``document.defaultView``) is the global object too.
_DEFAULT_VIEW = "defaultView"
# Globals that run source text as code, which can write any global.
_CODE_EVALUATORS = frozenset({"eval", "Function", "execScript"})
_STRING_TIMERS = frozenset({"setTimeout", "setInterval"})
# ``x.constructor`` reaches the function constructors (``[].constructor
# .constructor``, ``(async () => {}).constructor``), so calling it, or handing
# it on, may run source text; and so may ``.call``/``.apply``/``.bind`` of a
# code evaluator or timer.
_CONSTRUCTOR = "constructor"
# Calls that write properties of their first argument by computed name.
_PROPERTY_WRITERS = frozenset(
    {
        ("Object", "assign"),
        ("Object", "defineProperty"),
        ("Object", "defineProperties"),
        ("Reflect", "set"),
        ("Reflect", "defineProperty"),
    }
)
_INVOKERS = frozenset({"call", "apply", "bind"})
# The namespaces whose members are property writers (``_PROPERTY_WRITERS``).
_WRITER_NAMESPACES = frozenset(namespace for namespace, _ in _PROPERTY_WRITERS)
# A static key the analysis cannot read: a string or template key with an
# escape (``o['\x61ssign']``). It may be any name, so it fails closed.
_UNREADABLE_KEY = "\0unreadable"
# A property writer's target when an unreadable invoker may pass any argument.
_ANY_TARGET = object()
# Timer arguments that are certainly functions, never source text.
_FUNCTION_ARGUMENTS = frozenset(
    {"function_expression", "arrow_function", "generator_function"}
)
# Uses of the global object that neither write through it nor hand it on.
_INERT_UNARY = frozenset({"typeof", "void", "!"})
# Tier 2 (fold 3, item 3): binary operators a ``.constructor`` read may be
# an operand of without an evaluator cause.
_SAFE_CONSTRUCTOR_OPERATORS = frozenset({"===", "!==", "==", "!=", "instanceof"})
_COMPARISONS = frozenset({"===", "!==", "==", "!=", "instanceof", "in"})
_NON_ARROW_FUNCTIONS = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "function_expression",
        "generator_function",
        "method_definition",
    }
)
_FIELDS = frozenset({"field_definition", "public_field_definition"})

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
_NESTED_LOOKUP_BARRIERS = _FUNCTIONS | _CLASSES | _NAMESPACES
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
_ENUM_SCOPE = "enum"
ENUM_SCOPE_REASON = "enum-scope"
NAMESPACE_MERGED = "namespace-merged"


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
    # Every declaration in an ambient context (``declare`` and the blocks it
    # opens) is ambient; scopes created there inherit it (section 7.2).
    ambient: bool = False
    # A script top level whose global object is written through a key the
    # analysis cannot read: any name may be reassigned.
    reassigned_all: bool = False
    # TS namespace bodies: the scope and name of the namespace's own
    # declaration, to count its merged declarations, or ``always_merged``.
    merge_scope: _Scope | None = None
    merge_name: str = ""
    always_merged: bool = False
    # Cached by ``_nested_call``: whether any decorator occurs in the body.
    decorated: bool | None = None

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
TRANSPARENT_WRAPPERS = frozenset(
    {
        "parenthesized_expression",
        "non_null_expression",
        "as_expression",
        "satisfies_expression",
        "instantiation_expression",
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


def operand_children(node: Any) -> list[Any]:
    """Named children in operand order, excluding JS and Annex B comments."""
    if node is None:
        return []
    return [c for c in node.named_children if c.type not in ("comment", "html_comment")]


def unwrap(node: Any) -> Any:
    """``node`` without transparent wrappers (``(eval)`` and ``eval!`` -> ``eval``)."""
    current = node
    while current is not None and current.type in TRANSPARENT_WRAPPERS:
        named = operand_children(current)
        if not named:
            return current
        # ``<T>x``: the expression follows the type arguments.
        current = named[-1] if current.type == "type_assertion" else named[0]
    return current


def _callee(node: Any) -> Any:
    """``node`` without transparent wrappers and comma expressions, at every
    level: ``(0, (1, (Object.assign)))`` -> ``Object.assign``. A comma
    expression evaluates to its last operand (treesitter-chunker#694)."""
    current = unwrap(node)
    while current is not None and current.type == "sequence_expression":
        operands = operand_children(current)
        current = unwrap(operands[-1]) if operands else None
    return current


def _array_items(node: Any) -> list[Any] | None:
    """The items of an array literal (through parentheses and commas), or
    ``None`` for any other expression."""
    node = _callee(node)
    if node is None or node.type != "array":
        return None
    return operand_children(node)


class _Analysis:
    """Scopes and bindings of one file, and lookups through them."""

    def __init__(
        self, root: Any, source: bytes, language: str, goal: str | None = None
    ) -> None:
        self.root = root
        self.source = source
        self.language = language
        self.typescript = language in _TS_LANGUAGES
        self.goal = goal or program_goal(root)
        self.scopes: dict[tuple[int, str], _Scope] = {}
        self.assignment_targets: list[Any] = []
        self.eval_calls: list[Any] = []
        self.ambient_depth = 0
        # Bodies of ``declare global``, whose names are globals of any goal.
        self.global_blocks: list[_Scope] = []
        # Names written through the global object, and whether a global of
        # unknown name may be written (section 7.2).
        self.global_writes: set[str] = set()
        self.global_wildcard = False
        # Tier 2 (E5-3): a route that may run source text with access to
        # the module system: a code evaluator, the ``.constructor`` route to
        # ``Function``, or a timer given a string or non-function. It never
        # changes Tier 1 output.
        self.evaluator = False
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
        self.program = program
        self._statements(root, program, program, 0)
        # Assignments to a name no scope of the file declares are implicit
        # globals: in a script they declare it, and in a module (strict) they
        # write a global another script declared (section 7.2).
        self.implicit_globals: set[str] = set()
        for target in self.assignment_targets:
            name = _text(target, source)
            scope = self._binding_scope(target, name)
            if scope is not None:
                scope.reassigned.add(name)
            else:
                self.implicit_globals.add(name)
        for call in self.eval_calls:
            # A direct eval can declare or assign any binding visible from its
            # site, so every scope from there out to ``program`` is dynamic.
            for _, _, scope in self._chain(call):
                if scope is not None:
                    scope.dynamic = True
        self.exported_names = self._exported_names() if self.goal == "module" else set()
        self._global_object_pass()
        if self.goal == "script":
            # A script's top level is the global object: writing a global
            # through it reassigns the top-level binding of that name.
            program.reassigned.update(self.global_writes)
            program.reassigned_all = self.global_wildcard

    # -- building -----------------------------------------------------------

    def _scope(self, kind: str, node: Any, key_node: Any, role: str) -> _Scope:
        scope = _Scope(kind, node, ambient=self.ambient_depth > 0)
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
        # Ambient status is inherited from enclosing ``declare`` blocks.
        ambient = ambient or scope.ambient or self.ambient_depth > 0
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
                if node.type != "arrow_function":
                    self._arguments_aliases(node, params_scope, function_scope)
            else:
                self.visit(body, params_scope, params_scope, depth + 1)
        # A computed method name is evaluated in the enclosing scope.
        plain_name = name if name is not None and name.type in _PLAIN_NAMES else None
        self._visit_except(node, (plain_name, parameters, body), var, lex, depth)

    def _arguments_aliases(
        self, node: Any, params_scope: _Scope, function_scope: _Scope
    ) -> None:
        """A body binding that shares a parameter's name may be written
        through the mapped ``arguments`` object (``arguments[0] = x``), so it
        is reassigned when the function mentions ``arguments`` at all."""
        shared = (set(params_scope.bindings) - {"arguments"}) & set(
            function_scope.bindings
        )
        if shared and _mentions(node, "arguments", self.source):
            function_scope.reassigned.update(shared)

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
            # ``declare global { ... }``: an ambient namespace-like body that
            # merges with the global scope of every script, so it is always
            # merged, and its names are globals.
            scope = self._scope(_NAMESPACE_SCOPE, node, node, "scope")
            scope.always_merged = True
            self.global_blocks.append(scope)
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
                    and not self._namespace_export(node, target)
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

    @staticmethod
    def _namespace_export(node: Any, scope: _Scope) -> bool:
        """An exported variable of a TS namespace: tsc rewrites every use of
        it to a property of the namespace object, which other code can
        reassign, so it is not a symbol binding (``expression-bound``)."""
        return (
            scope.kind == _NAMESPACE_SCOPE
            and node.parent is not None
            and node.parent.type == "export_statement"
        )

    def _import(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        type_only = _has_token(node, "type")
        # The specifier's string value, decoded exactly; ``None`` fails
        # closed (Tier 2, section 9.1).
        source = decode_string_literal(node.child_by_field_name("source"), self.source)
        # Import attributes (``with { type: "json" }``) select a module kind
        # the resolution does not model.
        attributes = any(
            child.type == "import_attribute" for child in node.named_children
        )
        for child in node.named_children:
            if child.type == "import_require_clause":
                # ``import x = require()``: CommonJS is deferred (non-symbol).
                for ident in child.named_children:
                    if ident.type == "identifier":
                        lex.bind(_text(ident, self.source), _Binding(LOCAL_VARIABLE))
                        break
            elif child.type == "import_clause":
                for part in child.named_children:
                    self._import_clause_part(part, lex, source, type_only, attributes)
        self._statements(node, var, lex, depth + 1)

    def _import_clause_part(
        self,
        part: Any,
        lex: _Scope,
        source: str | None,
        type_only: bool,
        attributes: bool,
    ) -> None:
        if part.type == "identifier":
            self._bind_import(
                lex, part, source, "default", "default", type_only, attributes
            )
        elif part.type == "namespace_import":
            for ident in part.named_children:
                if ident.type == "identifier":
                    self._bind_import(
                        lex, ident, source, "*", "namespace", type_only, attributes
                    )
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
                    # ``import {"a-b" as x}``: the string's value, decoded
                    # exactly, never its source text (``None`` fails closed).
                    module_export_name(imported, self.source),
                    "named",
                    type_only or _has_token(spec, "type"),
                    attributes,
                )

    def _bind_import(
        self,
        lex: _Scope,
        local: Any,
        source: str | None,
        imported: str | None,
        form: str,
        type_only: bool,
        attributes: bool,
    ) -> None:
        name = _text(local, self.source)
        if type_only:
            lex.bind(name, _Binding(TYPE_ONLY))
            return
        if source is None or imported is None:
            # A specifier or name that does not decode exactly fails closed.
            lex.bind(name, _Binding(UNMAPPED))
            return
        info = {"source": source, "name": imported, "form": form}
        if attributes:
            info["attributes"] = "with"
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
        body = node.child_by_field_name("body")
        if body is not None:
            # Inside an enum body the members of every declaration of the enum
            # (merged ones too, possibly in other files) are in scope for the
            # initializers and shadow outer names. That member set is not
            # local, so every lookup that reaches the body fails closed.
            scope = self._scope(_ENUM_SCOPE, body, body, "scope")
            self._statements(body, var, scope, depth + 1)
        self._visit_except(node, (name, body), var, lex, depth)

    def _namespace(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        name = node.child_by_field_name("name")
        head = name
        while head is not None and head.type == "nested_identifier":
            head = head.child_by_field_name("object") or (
                next(iter(operand_children(head)), None)
            )
        head_name = ""
        if head is not None and head.type == "identifier":
            head_name = _text(head, self.source)
            self._symbol(lex, head_name, node, _NAMESPACE)
        body = node.child_by_field_name("body")
        if body is not None:
            scope = self._scope(_NAMESPACE_SCOPE, body, body, "scope")
            if name is not None and name.type == "identifier":
                # Merged when the declaring scope holds another namespace (or
                # enum) declaration of the name, counted at lookup time.
                scope.merge_scope = lex
                scope.merge_name = head_name
            else:
                # ``namespace A.B`` (its body also sees the members of every
                # ``A`` and ``A.B``) and ``declare module 'm'`` (which merges
                # with the module it names) are always treated as merged.
                scope.always_merged = True
            self._statements(body, scope, scope, depth + 1)
        self._visit_except(node, (name, body), var, lex, depth)

    def _ambient(self, node: Any, var: _Scope, lex: _Scope, depth: int) -> None:
        # Everything below ``declare`` is ambient, including the bodies of
        # the namespaces and modules it declares (inherited, section 7.2).
        self.ambient_depth += 1
        try:
            self._statements(node, var, lex, depth + 1)
        finally:
            self.ambient_depth -= 1

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

    # -- the global object (section 7.2) ------------------------------------

    def _global_object_pass(self) -> None:
        """Collect writes through the global object and its escapes.

        ``window.x =``, ``globalThis.x =``, ``self.x =``, ``global.x =`` (and
        chains such as ``window.top.x``), with a string-literal key too, write
        the global ``x`` in a file of either goal; in a script, so does
        ``this.x =`` wherever ``this`` may be the global object. Any other way
        the analysis cannot read fails closed with :data:`GLOBAL_WILDCARD`: a
        computed key, the global object used as a value (``f(window)``,
        ``const g = globalThis``), a computed read from it (``window[k]()``
        may call ``eval``), and any reference to a code evaluator (``eval``,
        ``Function``, ``execScript``, or a timer given source text).
        """
        stack = [self.root]
        while stack:
            node = stack.pop()
            kind = node.type
            if kind in ("identifier", "shorthand_property_identifier"):
                name = _text(node, self.source)
                if _declaration_name(node):
                    # A name being declared (a parameter of a bodyless TS
                    # signature or function type binds no scope) is no use.
                    pass
                elif (
                    name in _GLOBAL_OBJECTS or name in _CODE_EVALUATORS
                ) and self._refers_to_global(node, name):
                    if name in _CODE_EVALUATORS:
                        self.global_wildcard = True
                        self.evaluator = True
                    else:
                        self._global_object_use(node)
                elif name in _STRING_TIMERS and self._refers_to_global(node, name):
                    self._timer_use(node)
            elif kind == "this":
                if self._maybe_global_this(node):
                    self._global_object_use(node)
            elif kind in _MEMBER_ACCESS:
                self._member_use(node)
            elif kind == "call_expression":
                self._property_writer_call(node)
            elif kind == "pair_pattern":
                if self._member_key_name(node.child_by_field_name("key")) in (
                    _CONSTRUCTOR,
                    _UNREADABLE_KEY,
                ):
                    # ``const { constructor: F } = f`` reaches the function
                    # constructors like ``f.constructor``.
                    self.global_wildcard = True
                    self.evaluator = True
            elif kind == "shorthand_property_identifier_pattern":
                if _text(node, self.source) == _CONSTRUCTOR:
                    self.global_wildcard = True
                    self.evaluator = True
            elif kind in ("assignment_expression", "augmented_assignment_expression"):
                self._global_write(node.child_by_field_name("left"))
            elif kind == "update_expression":
                self._global_write(node.child_by_field_name("argument"))
            elif kind == "for_in_statement":
                if node.child_by_field_name("kind") is None:
                    self._global_write(node.child_by_field_name("left"))
            elif kind == "unary_expression":
                operator = node.child_by_field_name("operator")
                if operator is not None and operator.type == "delete":
                    self._global_write(node.child_by_field_name("argument"))
            stack.extend(node.named_children)

    def _refers_to_global(self, ident: Any, name: str) -> bool:
        """Whether ``ident`` may read the global ``name``: nothing in the file
        binds it, or only a script's top level does, where ``var window``
        and ``declare var self`` are the global object's own properties."""
        scope = self._binding_scope(ident, name)
        return scope is None or (scope is self.program and self.goal == "script")

    def _is_global_object(self, node: Any, *, receiver: bool = False) -> bool:
        """Whether an expression is (an alias chain of) the global object.

        With ``receiver``, for the object of a write, ``this`` also counts
        wherever a host call may pass the global object as the receiver
        (:meth:`_receiver_this`), in code of either goal.
        """
        node = unwrap(node)
        if node is None:
            return False
        if node.type == "identifier":
            name = _text(node, self.source)
            return name in _GLOBAL_OBJECTS and self._refers_to_global(node, name)
        if node.type == "this":
            return self._maybe_global_this(node) or (
                receiver and self._receiver_this(node)
            )
        if node.type == "super":
            # ``super.x = v`` sets ``x`` on the receiver ``this`` when no
            # setter intervenes (B-4, the president's #691 re-check).
            return receiver and self._receiver_this(node)
        if node.type == "member_expression":
            prop = node.child_by_field_name("property")
            name = _text(prop, self.source) if prop is not None else ""
            return name == _DEFAULT_VIEW or (
                name in _GLOBAL_OBJECT_PROPERTIES
                and self._is_global_object(
                    node.child_by_field_name("object"), receiver=receiver
                )
            )
        if node.type == "subscript_expression":
            key = self._member_key(node)
            if key == _UNREADABLE_KEY:
                key = None
            # In a write chain, a computed key on the global object may name
            # the global object itself (``this[k].x =`` with ``k`` set to
            # ``'globalThis'``), so the chain continues and ``x`` is
            # recorded (B-5, the president's #691 re-check). A computed read
            # outside a write is already ``*`` (:meth:`_global_object_use`).
            return key == _DEFAULT_VIEW or (
                (key in _GLOBAL_OBJECT_PROPERTIES or (receiver and key is None))
                and self._is_global_object(
                    node.child_by_field_name("object"), receiver=receiver
                )
            )
        return False

    def _receiver_this(self, node: Any) -> bool:
        """Whether ``this`` may be the global object passed as a receiver.

        Hosts call functions with the global object as ``this``
        (``setTimeout(K.prototype.m)``, ``window.m()``), strict code
        included. Any ``this`` that comes from a non-arrow function or method
        may be it, except in a class constructor, a field initializer or a
        static block, and at a module top level (A4, #691 panel).
        """
        child, current = node, node.parent
        while current is not None:
            kind = current.type
            if kind in _NON_ARROW_FUNCTIONS:
                parameters = current.child_by_field_name("parameters")
                if _same(child, current.child_by_field_name("body")) or _same(
                    child, parameters
                ):
                    if kind != "method_definition":
                        return True
                    # Only the class constructor is excluded: a non-static
                    # method named ``constructor``. ``static constructor()``
                    # is an ordinary static method (B-2, #691 ruling).
                    name = current.child_by_field_name("name")
                    return not (
                        current.parent is not None
                        and current.parent.type == "class_body"
                        and name is not None
                        and name.type == "property_identifier"
                        and _text(name, self.source) == _CONSTRUCTOR
                        and not _has_token(current, "static")
                    )
            elif kind in _FIELDS:
                if child.type != "computed_property_name":
                    return False
            elif kind == "class_static_block":
                return False
            elif kind == "program":
                return self.goal == "script"
            child, current = current, current.parent
        return False

    def _member_key(self, node: Any) -> str | None:
        """The name a member access reads, matched the same way everywhere.

        ``x.name``, ``x['name']`` and ``x[`name`]`` (a template without
        substitutions) all give ``"name"``: a literal key equals dot access
        for every name the analysis recognizes (Codex 4652498471, #691). A
        string or template key with an escape gives :data:`_UNREADABLE_KEY`,
        and any other computed key gives ``None``.
        """
        if node.type == "member_expression":
            prop = node.child_by_field_name("property")
            return _text(prop, self.source) if prop is not None else None
        if node.type != "subscript_expression":
            return None
        return self._static_key(node.child_by_field_name("index"))

    def _static_key(self, node: Any) -> str | None:
        """A plain string or substitution-free template's text;
        :data:`_UNREADABLE_KEY` when it holds an escape; else ``None``."""
        node = unwrap(node)
        if node is None or node.type not in ("string", "template_string"):
            return None
        parts = node.named_children
        if any(part.type == "template_substitution" for part in parts):
            return None
        if any(part.type != "string_fragment" for part in parts):
            return _UNREADABLE_KEY
        return "".join(_text(part, self.source) for part in parts)

    def _member_use(self, node: Any) -> None:
        """Member accesses that reach the global object or a code evaluator:
        ``document.defaultView`` used as a value, ``G.setTimeout`` and
        ``G['setTimeout']``, and ``x.constructor`` called or handed on."""
        key = self._member_key(node)
        obj = node.child_by_field_name("object")
        if key == _UNREADABLE_KEY:
            # An escaped key may be any name: ``constructor``, a timer or an
            # evaluator (fail closed).
            self._evaluator_use(node)
            if self._is_global_object(obj, receiver=True):
                self.global_wildcard = True
                self.evaluator = True
        elif key == _DEFAULT_VIEW:
            self._global_object_use(node)
        elif key == _CONSTRUCTOR:
            self._evaluator_use(node, constructor=True)
        elif key in _STRING_TIMERS and self._is_global_object(obj, receiver=True):
            self._timer_use(node)
        elif key in _CODE_EVALUATORS and self._is_global_object(obj, receiver=True):
            # ``this.eval(s)``, ``this.Function(s)`` with a receiver ``this``.
            self.global_wildcard = True
            self.evaluator = True

    def _member_key_name(self, key: Any) -> str | None:
        """A pattern or object key's name: an identifier or a plain string."""
        if key is None:
            return None
        if key.type in ("property_identifier", "identifier"):
            return _text(key, self.source)
        if key.type == "computed_property_name":
            named = operand_children(key)
            return self._static_key(named[0]) if named else None
        return self._static_key(key)

    def _writer_namespace(self, node: Any) -> str | None:
        """``"Object"`` or ``"Reflect"`` when an expression is that global
        name, or that property of the global object (``globalThis.Object``,
        ``window['Reflect']``) or of a receiver ``this`` (``this.Object``;
        C-1, the president's #691 re-check), also as the last operand of a
        comma expression (``(0, Object)``, treesitter-chunker#694); else
        ``None``."""
        node = _callee(node)
        if node is None:
            return None
        if node.type == "identifier":
            name = _text(node, self.source)
            if name in _WRITER_NAMESPACES and self._refers_to_global(node, name):
                return name
            return None
        if node.type in _MEMBER_ACCESS:
            key = self._member_key(node)
            if key in _WRITER_NAMESPACES and self._is_global_object(
                node.child_by_field_name("object"), receiver=True
            ):
                return key
        return None

    def _is_property_writer(self, node: Any) -> bool:
        """Whether an expression is a property writer: ``Object.assign``,
        ``Object['defineProperty']``, ``Reflect[`set`]`` and the rest of
        :data:`_PROPERTY_WRITERS`, through parentheses and commas
        (``(0, Object.assign)``). An escaped or computed key on ``Object``
        or ``Reflect`` may name one, so it counts too (fail closed)."""
        node = _callee(node)
        if node is None or node.type not in _MEMBER_ACCESS:
            return False
        namespace = self._writer_namespace(node.child_by_field_name("object"))
        if namespace is None:
            return False
        key = self._member_key(node)
        if key is None or key == _UNREADABLE_KEY:
            return True
        return (namespace, key) in _PROPERTY_WRITERS

    def _property_writer_call(self, node: Any) -> None:
        """``Object.assign(G, …)``, ``Object['defineProperty'](G, …)`` and the
        like, also through ``.call``/``.apply``/``.bind`` (nested, and on a
        comma or parenthesized writer: ``(0, Object.assign).call(null, G,
        …)``, ``Object.assign.bind(null)(G, …)``; treesitter-chunker#694)
        and ``Reflect.apply(Object.assign, null, [G, …])``, where ``G`` is a
        receiver ``this`` (or the global object, which
        :meth:`_global_object_use` already catches), may write any global.

        A call gives ``*`` when either detector flags it: the
        comment-aware one (:meth:`_writer_targets`) or the positional one it
        replaced (:meth:`_positional_writer_call`), so this change only adds
        ``*`` (the #717 review: the positional reading, which counts
        comments as arguments, flagged forms the comment-aware one missed)."""
        if self._positional_writer_call(node):
            self.global_wildcard = True
            return
        targets = self._writer_targets(
            node.child_by_field_name("function"),
            operand_children(node.child_by_field_name("arguments")),
        )
        if any(
            target is _ANY_TARGET
            or self._is_global_object(_callee(target), receiver=True)
            for target in targets
        ):
            self.global_wildcard = True

    def _positional_writer_call(self, node: Any) -> bool:
        """The property-writer detector of js fact version 20, kept verbatim
        apart from returning its verdict: it reads the writer's target from
        the raw ``named_children`` of the arguments (comments included), so
        ``Object.assign.call(/* c */ this, this ?? {}, …)`` reads ``this``.
        Main's verdict is kept as a floor, never replaced:
        :meth:`_is_property_writer` accepts every expression main's did (it
        also looks through commas), so this flags everything main flagged."""
        function = unwrap(node.child_by_field_name("function"))
        while function is not None and function.type == "sequence_expression":
            # ``(0, Object.assign)(this, …)`` calls the last operand.
            operands = function.named_children
            function = unwrap(operands[-1]) if operands else None
        if function is None:
            return False
        arguments = node.child_by_field_name("arguments")
        named = arguments.named_children if arguments is not None else []
        target = None
        if self._is_property_writer(function):
            target = named[0] if named else None
        elif function.type in _MEMBER_ACCESS and self._is_property_writer(
            function.child_by_field_name("object")
        ):
            invoker = self._member_key(function)
            if invoker in ("call", "bind"):
                target = named[1] if len(named) > 1 else None
            elif invoker == "apply":
                listed = unwrap(named[1]) if len(named) > 1 else None
                if listed is not None and listed.type == "array":
                    items = listed.named_children
                    target = items[0] if items else None
            elif invoker is None or invoker == _UNREADABLE_KEY:
                return True
        return target is not None and self._is_global_object(target, receiver=True)

    def _writer_targets(self, function: Any, arguments: list[Any]) -> list[Any]:
        """The expressions a property writer may receive as its first
        argument when ``function`` is called with ``arguments``: empty when
        ``function`` is no writer (or the target is not spelled out), and
        :data:`_ANY_TARGET` when an unreadable invoker may pass any.

        Parentheses and commas are looked through at every level (a comma
        expression evaluates to its last operand). ``F.call(t, a, …)`` and
        ``F.bind(t, a, …)`` pass ``a, …`` to ``F``; ``F.apply(t, [a, …])``
        passes the array's items; ``F.bind(t, a, …)(b, …)`` passes ``a, …,
        b, …``; ``Reflect.apply(F, t, [a, …])`` passes the array's items. A
        computed key on ``Reflect`` may name ``apply`` as well as a writer.
        The receiver argument of a nested invoker is not checked, so
        ``F.call.call(other, …)`` is read as ``F`` (this only adds ``*``)."""
        function = _callee(function)
        if function is None:
            return []
        if function.type == "call_expression":
            # ``F.bind(t, a, …)(b, …)``.
            bound = _callee(function.child_by_field_name("function"))
            if bound is None or bound.type not in _MEMBER_ACCESS:
                return []
            if self._member_key(bound) != "bind":
                return []
            preset = operand_children(function.child_by_field_name("arguments"))
            return self._writer_targets(
                bound.child_by_field_name("object"), preset[1:] + arguments
            )
        if function.type not in _MEMBER_ACCESS:
            return []
        obj = function.child_by_field_name("object")
        invoker = self._member_key(function)
        targets: list[Any] = []
        if self._writer_namespace(obj) == "Reflect" and invoker in (
            "apply",
            None,
            _UNREADABLE_KEY,
        ):
            listed = _array_items(arguments[2]) if len(arguments) > 2 else None
            if listed is not None:
                targets.extend(self._writer_targets(arguments[0], listed))
        if self._is_property_writer(function):
            targets.extend(arguments[:1])
        elif invoker in ("call", "bind"):
            targets.extend(self._writer_targets(obj, arguments[1:]))
        elif invoker == "apply":
            listed = _array_items(arguments[1]) if len(arguments) > 1 else None
            if listed is not None:
                targets.extend(self._writer_targets(obj, listed))
        elif invoker in (None, _UNREADABLE_KEY) and self._writer_chain(obj):
            # ``Object.assign[k](…)``, ``Object.assign.call[k](…)``: the key
            # may name any invoker.
            targets.append(_ANY_TARGET)
        return targets

    def _writer_chain(self, node: Any) -> bool:
        """Whether an expression is a property writer or an invoker of one
        (``Object.assign``, ``(0, Object.assign).call``,
        ``Object.assign.bind(null)``)."""
        node = _callee(node)
        if node is None:
            return False
        if self._is_property_writer(node):
            return True
        if node.type == "call_expression":
            node = _callee(node.child_by_field_name("function"))
            if node is None or node.type not in _MEMBER_ACCESS:
                return False
            if self._member_key(node) != "bind":
                return False
        elif node.type not in _MEMBER_ACCESS or self._member_key(node) not in (
            _INVOKERS
        ):
            return False
        return self._writer_chain(node.child_by_field_name("object"))

    def _use_site(self, node: Any) -> tuple[Any, Any]:
        """``(expression, parent)``: ``node`` with its transparent wrappers,
        and the node that uses it."""
        current = node
        while current.parent is not None and current.parent.type in (
            TRANSPARENT_WRAPPERS
        ):
            current = current.parent
        return current, current.parent

    def _inert_use(self, current: Any, parent: Any) -> bool:
        """``typeof x``, ``!x``, ``x === y`` and the like only read ``x``."""
        if parent is None:
            return False
        if parent.type == "type_query":
            return True
        operator = parent.child_by_field_name("operator")
        operator_text = _text(operator, self.source) if operator is not None else ""
        return (
            parent.type == "unary_expression" and operator_text in _INERT_UNARY
        ) or (parent.type == "binary_expression" and operator_text in _COMPARISONS)

    def _evaluator_use(self, node: Any, constructor: bool = False) -> None:
        """``x.constructor`` may be a function constructor: calling it, or
        using it as a value, may run source text (``*``). Reading a property
        of it (``.name``, ``.prototype``) does not, except ``.call``,
        ``.apply`` and ``.bind``; a nested ``.constructor`` is checked on its
        own."""
        current, parent = self._use_site(node)
        if constructor and not self._safe_constructor_read(current, parent):
            # Tier 2 (fold 3, item 3): only the closed list of positions in
            # :meth:`_safe_constructor_read` leaves no evaluator cause.
            self.evaluator = True
        if (
            parent is not None
            and parent.type in _MEMBER_ACCESS
            and _same(parent.child_by_field_name("object"), current)
        ):
            key = self._member_key(parent)
            if key is None or key in _INVOKERS:
                self.global_wildcard = True
                self.evaluator = self.evaluator or not constructor
            return
        if self._inert_use(current, parent):
            return
        self.global_wildcard = True
        self.evaluator = self.evaluator or not constructor

    def _safe_constructor_read(self, current: Any, parent: Any) -> bool:
        """Fold 3, item 3: the closed list of safe positions for a
        ``.constructor`` read. ``x.constructor.name`` reads a string;
        ``===``/``!==``/``==``/``!=`` compare references and ``instanceof``
        runs ``Function.prototype[Symbol.hasInstance]`` (a prototype-chain
        walk); ``typeof`` returns a string. None calls the constructor, so
        none can reach ``Function`` and run source text."""
        if parent is None:
            return False
        if parent.type == "member_expression" and _same(
            parent.child_by_field_name("object"), current
        ):
            prop = parent.child_by_field_name("property")
            return (
                prop is not None
                and prop.type == "property_identifier"
                and _text(prop, self.source) == "name"
            )
        operator = parent.child_by_field_name("operator")
        text = _text(operator, self.source) if operator is not None else ""
        if parent.type == "binary_expression":
            return text in _SAFE_CONSTRUCTOR_OPERATORS
        return parent.type == "unary_expression" and text == "typeof"

    def _timer_use(self, node: Any) -> None:
        """A timer runs a string first argument as source text. Only a direct
        call whose first argument is certainly a function is safe: a
        function or arrow expression, or a name the file proves to be a
        local function. Any other use (an alias, ``.call``, ``.apply``,
        ``Reflect.apply``) gives ``*``."""
        current, parent = self._use_site(node)
        if self._inert_use(current, parent):
            return
        if (
            parent is None
            or parent.type != "call_expression"
            or not _same(parent.child_by_field_name("function"), current)
        ):
            # Tier 2 (E5-3): only a call runs source text, and Node rejects a
            # string timer; an alias or a saved/restored timer is not an
            # evaluator by itself.
            self.global_wildcard = True
            return
        arguments = parent.child_by_field_name("arguments")
        named = operand_children(arguments)
        first = unwrap(named[0]) if named else None
        if first is None or first.type in _FUNCTION_ARGUMENTS:
            return
        if first.type == "identifier":
            # Tier 2 (E5-3): a name the file binds (a local, a parameter, the
            # sleep idiom's ``resolve``) is not source text; a free name is.
            if self._binding_scope(first, _text(first, self.source)) is None:
                self.evaluator = True
            outcome = self.lookup(first)
            if outcome["outcome"] == "local" and "global" not in outcome:
                return
        else:
            self.evaluator = True
        self.global_wildcard = True

    def _literal_key(self, node: Any) -> str | None:
        """The text of a plain string literal key, or ``None``."""
        node = unwrap(node)
        if node is None or node.type != "string":
            return None
        parts = node.named_children
        if any(part.type != "string_fragment" for part in parts):
            return None
        return "".join(_text(part, self.source) for part in parts)

    def _global_write(self, target: Any) -> None:
        """Record the globals a write target may write through the global
        object; every member access below the target counts (fail closed)."""
        if target is None:
            return
        stack = [target]
        while stack:
            current = stack.pop()
            if current.type in _MEMBER_ACCESS:
                obj = current.child_by_field_name("object")
                if self._is_global_object(obj, receiver=True):
                    if current.type == "member_expression":
                        prop = current.child_by_field_name("property")
                        if prop is not None:
                            self.global_writes.add(_text(prop, self.source))
                    else:
                        key = self._literal_key(current.child_by_field_name("index"))
                        if key is None:
                            self.global_wildcard = True
                        else:
                            self.global_writes.add(key)
                # The object is read, not written (``window.top.x``).
                stack.extend(
                    child for child in current.named_children if not _same(child, obj)
                )
                continue
            stack.extend(current.named_children)

    def _global_object_use(self, node: Any) -> None:
        """Fail closed when the global object is used as a value."""
        current = node
        while True:
            parent = current.parent
            if parent is None:
                self.global_wildcard = True
                return
            kind = parent.type
            if kind in TRANSPARENT_WRAPPERS:
                current = parent
                continue
            if _same(parent.child_by_field_name("object"), current):
                if kind == "member_expression":
                    prop = parent.child_by_field_name("property")
                    name = _text(prop, self.source) if prop is not None else ""
                    if name in _GLOBAL_OBJECT_PROPERTIES:
                        current = parent
                        continue
                    if name in _CODE_EVALUATORS:
                        self.global_wildcard = True
                        self.evaluator = True
                    return
                if kind == "subscript_expression":
                    key = self._member_key(parent)
                    if key in _GLOBAL_OBJECT_PROPERTIES:
                        current = parent
                        continue
                    if key is None or key == _UNREADABLE_KEY or key in _CODE_EVALUATORS:
                        self.global_wildcard = True
                        self.evaluator = True
                    return
            if kind == "type_query":
                return
            operator = parent.child_by_field_name("operator")
            operator_text = _text(operator, self.source) if operator is not None else ""
            if (kind == "unary_expression" and operator_text in _INERT_UNARY) or (
                kind == "binary_expression" and operator_text in _COMPARISONS
            ):
                return
            self.global_wildcard = True
            return

    def _maybe_global_this(self, node: Any) -> bool:
        """Whether ``this`` may be the global object (script goal only):
        at the top level, or in a sloppy function or object-literal method
        that a plain call can reach. Class code is strict, so ``this`` in its
        methods, fields and static blocks is never the global object; a
        computed key or heritage expression sees the enclosing ``this``."""
        if self.goal != "script":
            return False
        child, current = node, node.parent
        while current is not None:
            kind = current.type
            if kind in _NON_ARROW_FUNCTIONS:
                parameters = current.child_by_field_name("parameters")
                if _same(child, current.child_by_field_name("body")) or _same(
                    child, parameters
                ):
                    if _inside_class(current):
                        return False
                    return kind != "method_definition" or (
                        current.parent is not None and current.parent.type == "object"
                    )
            elif kind in _FIELDS:
                if child.type != "computed_property_name":
                    return False
            elif kind == "class_static_block":
                return False
            elif kind == "program":
                return True
            child, current = current, current.parent
        return True

    def script_globals(self) -> list[str]:
        """The globals this file declares or may write (section 7.2)."""
        names = set(self.global_writes)
        if self.global_wildcard:
            names.add(GLOBAL_WILDCARD)
        # Implicit globals count in a file of either goal (A2, #691 panel).
        names.update(self.implicit_globals)
        if self.goal == "script":
            names.update(
                name
                for name, bindings in self.program.bindings.items()
                if any(binding.cls != TYPE_ONLY for binding in bindings)
            )
        for scope in self.global_blocks:
            names.update(scope.bindings)
        return sorted(names)

    # -- lookup -------------------------------------------------------------

    def _scopes_at(self, node: Any, child: Any) -> Iterator[_Scope]:
        kind = node.type
        if (
            kind in ("program", "statement_block", "enum_body")
            or kind in _BLOCK_SCOPE_NODES
        ):
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

    def lookup(self, ident: Any, *, bare_call: bool = False) -> dict[str, Any]:
        """The outcome of a value lookup of ``ident``'s name."""
        name = _text(ident, self.source)
        through_merged = False
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
            if scope.kind == _ENUM_SCOPE:
                return _none(ENUM_SCOPE_REASON)
            if scope.kind == _NAMESPACE_SCOPE and self._merged(scope):
                through_merged = True
            bindings = scope.bindings.get(name)
            if bindings:
                outcome = self._decide(scope, name, bindings, through_merged)
                if (
                    bare_call
                    and scope.kind == _FUNCTION_SCOPE
                    and outcome["outcome"] == "local"
                    and len(bindings) == 1
                    and self._nested_call(ident, scope, bindings[0])
                ):
                    outcome["nested_name"] = name
                return outcome
        # A merged namespace's other declarations may bind the name.
        return _none(NAMESPACE_MERGED if through_merged else "unbound")

    @staticmethod
    def _nested_call(ident: Any, scope: _Scope, binding: _Binding) -> bool:
        """One direct function-body binding, called in that same body.

        A decorator expression anywhere in the body is evaluated in an
        enclosing scope that this analysis does not model exactly (a
        parameter decorator can assign the body's helper), so any decorator
        in the body withholds the nested target.
        """
        if scope.decorated is None:
            scope.decorated = _contains_type(scope.node, "decorator")
        if scope.decorated:
            return False
        statement = binding.statement
        if statement is None or not _same(statement.parent, scope.node):
            return False
        decl = binding.decl
        if decl.type == "function_declaration":
            if not _same(decl, statement):
                return False
        elif (
            decl.type not in _FUNCTION_VALUES
            or statement.type != "lexical_declaration"
            or statement.end_byte > ident.start_byte
        ):
            return False
        # _declaration only promotes direct single-const function values.
        node = ident.parent
        while node is not None and not _same(node, scope.node):
            if node.type in _NESTED_LOOKUP_BARRIERS:
                return False
            node = node.parent
        return node is not None

    def top_level_outcome(self, name: str) -> dict[str, Any]:
        """The outcome of a value lookup of ``name`` at the program scope:
        what an export of the local ``name`` binds (Tier 2, section 9.3)."""
        program = self.program
        if program.dynamic:
            return _none("dynamic-scope")
        if program.poisoned:
            return _none(UNMAPPED)
        bindings = program.bindings.get(name)
        if bindings:
            return self._decide(program, name, bindings, False)
        return _none("unbound")

    def _exported_names(self) -> set[str]:
        """Names a module exports from its top level in a form that module
        augmentation can merge into: an ``export`` modifier, an
        ``export { … }`` clause (either side of ``as``) or ``export =``.
        ``export default`` is left out; any other identifier in an export
        statement without a declaration counts (fail closed)."""
        names: set[str] = set()
        for statement in self.root.named_children:
            if statement.type != "export_statement":
                continue
            declaration = statement.child_by_field_name("declaration")
            if declaration is not None:
                if declaration.type == "ambient_declaration":
                    declaration = next(iter(operand_children(declaration)), None)
                if declaration is not None and declaration.type == "import_alias":
                    # ``export import Q = N``: fail closed on both names.
                    stack = list(declaration.named_children)
                    while stack:
                        current = stack.pop()
                        if current.type == "identifier":
                            names.add(_text(current, self.source))
                        stack.extend(current.named_children)
                elif declaration is not None and declaration.type in _NAMESPACES:
                    name = declaration.child_by_field_name("name")
                    while name is not None and name.type == "nested_identifier":
                        name = next(iter(operand_children(name)), None)
                    if name is not None and name.type == "identifier":
                        names.add(_text(name, self.source))
                continue
            if _has_token(statement, "default") or statement.child_by_field_name(
                "source"
            ):
                continue
            stack = list(statement.named_children)
            while stack:
                current = stack.pop()
                if current.type == "identifier":
                    names.add(_text(current, self.source))
                stack.extend(current.named_children)
        return names

    def _merged(self, scope: _Scope) -> bool:
        """Whether a namespace body is merged (section 7.2): its namespace
        has another declaration, or lives in a script, where namespaces are
        global and merge across files. Enum declarations of the name count
        too (fail closed)."""
        if self.goal == "script" or scope.always_merged:
            return True
        declaring = scope.merge_scope
        if declaring is None:
            return True
        if declaring is self.program and scope.merge_name in self.exported_names:
            # TS module augmentation (``declare module './a' { namespace N
            # {...} }``) merges into an exported namespace from another file
            # (A3, #691 panel).
            return True
        declarations = [
            binding
            for binding in declaring.bindings.get(scope.merge_name, ())
            if binding.cls == SYMBOL and binding.kind in _NON_CALLABLE
        ]
        return len(declarations) > 1

    def _decide(
        self,
        scope: _Scope,
        name: str,
        bindings: Sequence[_Binding],
        through_merged: bool,
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
        if name in scope.reassigned or scope.reassigned_all:
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
        if through_merged:
            return _none(NAMESPACE_MERGED)
        if scope.kind == _PROGRAM and self.goal == "script" and not imports:
            # A script's top level is shared with every other script: the
            # engine narrows only if no other file declares the name in its
            # ``script_globals`` (``script-global``).
            outcome = {**outcome, "global": name}
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
        if self._hoisted(scope, symbols, bodies):
            # t1.js_hoist: every function declaration of the scope is bound
            # before any statement runs, so the last one is the value.
            group = [max(bodies, key=lambda binding: binding.decl.start_byte)]
            rules = [RULE_JS_HOIST]
        elif len(bodies) == 1 and signatures:
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

    def _hoisted(
        self,
        scope: _Scope,
        symbols: Sequence[_Binding],
        bodies: Sequence[_Binding],
    ) -> bool:
        """``t1.js_hoist`` (section 7.4, 8): plain JavaScript, two or more
        function or generator declarations directly in one function body or
        one script ``program``, and nothing else binding the name there.

        Block-level declarations (Annex B), expression bindings and any other
        binding never reach this point: :meth:`_decide` already returned
        ``block-function``, ``mixed-bindings`` or ``reassigned`` (2.6(a)).
        An ES-module top level, where duplicates are an early error, a class
        static block and TypeScript keep the ambiguous group.
        """
        if self.language != "javascript" or len(bodies) < 2:
            return False
        if not (
            scope.kind == _FUNCTION_SCOPE
            or (scope.kind == _PROGRAM and self.goal == "script")
        ):
            return False
        return len(symbols) == len(bodies) and all(
            binding.decl.type in _FUNCTION_DECLARATIONS
            and _same(binding.statement.parent, scope.node)
            for binding in bodies
        )

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


# Parents under which an identifier is a binding pattern, not a reference.
_PATTERN_PARENTS = frozenset({"array_pattern", "object_pattern", "rest_pattern"})
# ``(parent, field)``: the field of the parent that names a declaration.
_DECLARATION_FIELDS = frozenset(
    {
        ("required_parameter", "pattern"),
        ("optional_parameter", "pattern"),
        ("assignment_pattern", "left"),
        ("object_assignment_pattern", "left"),
        ("pair_pattern", "value"),
        ("variable_declarator", "name"),
        ("arrow_function", "parameter"),
        ("catch_clause", "parameter"),
        ("function_declaration", "name"),
        ("generator_function_declaration", "name"),
        ("function_expression", "name"),
        ("generator_function", "name"),
        ("function_signature", "name"),
        ("class_declaration", "name"),
        ("abstract_class_declaration", "name"),
        ("class", "name"),
        ("import_specifier", "name"),
        ("import_specifier", "alias"),
    }
)
_DECLARATION_PARENTS = frozenset(
    {"formal_parameters", "namespace_import", "import_clause", "import_require_clause"}
)


def _declaration_name(node: Any) -> bool:
    """Whether an identifier is a name being declared, not a reference."""
    parent = node.parent
    if parent is None:
        return False
    if parent.type in _PATTERN_PARENTS or parent.type in _DECLARATION_PARENTS:
        return True
    return any(
        _same(parent.child_by_field_name(field_name), node)
        for kind, field_name in _DECLARATION_FIELDS
        if kind == parent.type
    )


def _inside_class(node: Any) -> bool:
    """Whether ``node`` is class code, which is always strict."""
    current = node.parent
    while current is not None:
        if current.type in _CLASSES:
            return True
        current = current.parent
    return False


def _contains_type(node: Any, kind: str) -> bool:
    """Whether a node of type ``kind`` occurs anywhere below ``node``."""
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type == kind:
            return True
        stack.extend(current.named_children)
    return False


_READ_IDENTIFIERS = frozenset({"identifier", "shorthand_property_identifier"})


def _mentions(node: Any, name: str, source: bytes) -> bool:
    """Whether a read of ``name`` occurs anywhere below ``node``.

    An object shorthand (``{ arguments }``) reads the binding too, so it
    counts as well as a plain identifier.
    """
    encoded = name.encode()
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type in _READ_IDENTIFIERS and (
            source[current.start_byte : current.end_byte] == encoded
        ):
            return True
        stack.extend(current.named_children)
    return False


def _callee_head(node: Any) -> Any:
    """The identifier a callee looks up: itself, or a member chain's head."""
    head = node
    while head is not None and head.type in (
        "member_expression",
        "subscript_expression",
    ):
        head = head.child_by_field_name("object")
    return head if head is not None and head.type == "identifier" else None


class EscapedIdentifierError(ValueError):
    """A name in the file uses a Unicode escape; the file fails closed."""


# Leaf kinds whose text is content, not a name: a backslash in them is an
# ordinary escape. Every other named leaf holding a backslash is a name
# spelled with a Unicode escape.
_TEXT_LEAVES = frozenset(
    {
        "string_fragment",
        "escape_sequence",
        "regex_pattern",
        "regex_flags",
        "comment",
        "html_comment",
        "hash_bang_line",
        "jsx_text",
        "html_character_reference",
    }
)


def escaped_name(root: Any, source: bytes) -> Any:
    """The first named leaf that spells a name with an escape, or ``None``."""
    if b"\\" not in source:
        return None
    stack = [root]
    while stack:
        node = stack.pop()
        if node.child_count:
            stack.extend(reversed(node.children))
        elif (
            node.is_named
            and node.type not in _TEXT_LEAVES
            and b"\\" in source[node.start_byte : node.end_byte]
        ):
            return node
    return None


class MisparsedBlockError(ValueError):
    """A statement-level object literal: a misparsed block; fail closed."""


def misparsed_block(root: Any) -> Any:
    """The first ``expression_statement`` whose first token is ``{``, or
    ``None``.

    Valid JavaScript and TypeScript never have one (an expression statement
    cannot start with ``{``), but tree-sitter parses a block such as
    ``{ L: function d() {} }`` as an object literal without an error, alone
    or glued to what follows on the line (``[0]``, ``(0)``, ``+0``, a
    template, a regex). That would hide a block-level declaration (A1, #691
    panel; B-1, the president's #691 ruling).
    """
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "expression_statement":
            first = node
            while first.child_count:
                first = first.children[0]
            if first.type == "{":
                return node
        stack.extend(node.named_children)
    return None


def analyze(
    root: Any,
    source: bytes,
    language: str,
    call_facts: Sequence[Mapping[str, Any]],
    goal: str | None = None,
    symlink: bool = False,
) -> dict[str, Any]:
    """Return partial scope facts: the goal and one outcome per call.

    ``goal`` overrides the goal the file's syntax implies, for an extension
    that fixes it (``.mjs``/``.mts`` are always modules).
    """
    escaped = escaped_name(root, source)
    if escaped is not None:
        msg = f"escaped name in a {escaped.type} at byte {escaped.start_byte}"
        raise EscapedIdentifierError(msg)
    misparsed = misparsed_block(root)
    if misparsed is not None:
        msg = f"statement-level object literal at byte {misparsed.start_byte}"
        raise MisparsedBlockError(msg)
    analysis = _Analysis(root, source, language, goal)
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
        outcome = (
            analysis.lookup(head, bare_call=node.type == "identifier")
            if head is not None
            else _none("unbound")
        )
        member = _namespace_member(node, head, source)
        if member is not None and outcome.get("outcome") == "import":
            # ``ns.f()`` (Tier 2, section 9.1): the property a two-segment
            # member callee names, read from the tree.
            outcome = {
                **outcome,
                "binding": {**outcome["binding"], "member": member},
            }
        bindings[f"{start}:{end}"] = outcome
    from .js_modules import module_facts

    exports, module_bindings = module_facts(analysis, symlink)
    return {
        "goal": analysis.goal,
        "bindings": bindings,
        "script_globals": analysis.script_globals(),
        "exports": exports,
        "module_bindings": module_bindings,
    }


def _namespace_member(node: Any, head: Any, source: bytes) -> str | None:
    """The property of a callee spelled exactly ``head.name``, else ``None``.

    Parentheses, computed keys, private names, optional chains and longer
    chains give ``None``: only ``ns.f()`` is a namespace member call.
    """
    if node.type != "member_expression" or head is None:
        return None
    obj = node.child_by_field_name("object")
    prop = node.child_by_field_name("property")
    if (
        not _same(obj, head)
        or prop is None
        or prop.type != "property_identifier"
        or any(child.type == "optional_chain" for child in node.children)
    ):
        return None
    return _text(prop, source)
