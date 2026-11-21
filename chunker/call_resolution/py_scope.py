"""Scope analyzer for Python (plan section 7.3).

One pass over the tree builds every scope and its bindings; then each call
fact's callee is looked up through the scope chain (LEGB), innermost first.

**Scopes.** ``module``, ``function_definition``, ``lambda``,
``class_definition`` and the comprehensions (``list_comprehension``,
``set_comprehension``, ``dictionary_comprehension``,
``generator_expression``), plus a **type-parameter scope** for a PEP 695
generic ``def``, ``class`` or ``type`` statement. Where code runs:

- a function's decorators, default values, parameter annotations and return
  annotation run in the enclosing scope (a decorator is a sibling of the
  definition, so it never enters it). A generic definition's type parameters
  are visible to its annotations, bases and body; lookups from its default
  values also pass through them, which can only fail closed;
- a class's bases and keywords run in the enclosing scope (or its
  type-parameter scope);
- a lambda's defaults run in the enclosing scope;
- a comprehension's first iterable runs in the enclosing scope; its targets,
  conditions, later iterables and body run in the comprehension's scope.

**Class scope (ruling A10 as modified).** Code that runs directly in a class
body (class-level statements, method decorators, defaults and annotations,
nested class bases, a comprehension's first iterable) starts its lookup at
the class scope, and so does an annotation scope immediately inside a class.
A name the class body binds anywhere gives ``none(class-scope-bound)``; there
is no positional variant. When the class statement has any base or keyword
argument, every lookup from class-body code gives ``class-scope-bound``: a
metaclass's ``__prepare__`` (possibly inherited from a base defined in
another file) or a ``__missing__`` namespace may supply any name. Otherwise a
free name continues through the enclosing function scopes, then the module. Code in methods, nested functions, lambdas
and comprehension bodies skips every class scope. A method's bare
``__class__`` is the implicit class cell (``none(local-variable)``), and every
dunder name is implicitly bound in a module or class namespace.

**Bindings.** A name bound anywhere in a scope is local to the whole scope,
so lookups never depend on position. Every write form binds:

- ``def`` and ``class`` (symbols). A **decorated** definition binds the
  decorator's result, so a single one is not a proof: ``none(expression-
  bound)``. It still counts as a member of a redefinition group, which never
  resolves (section 8);
- parameters, including ``*args``, ``**kwargs``, lambda parameters and PEP 695
  type parameters (``parameter``);
- assignment, annotated and augmented assignment, ``for``/``with``/
  ``except``/comprehension targets, walrus (bound in the nearest scope that
  is not a comprehension), ``match`` captures, ``del`` and ``type`` statements
  (``local-variable``). Targets are read fail-closed: every identifier under a
  target counts, through tuples, lists, starred targets and parentheses,
  except the object of an attribute or subscript (``x.y = v``); any other
  target form poisons the scope (``unmapped``); a backslash continuation
  inside a target is only a token. The grammar also accepts
  Python 2, so ``except E, e`` binds ``e`` and a list comprehension's
  targets also bind in the enclosing scope (Python 2 leaked them); the extra
  binding can only fail closed;
- ``import`` and ``from … import`` (including ``as`` and ``__future__``): an
  ``import`` outcome, which proves nothing in ``structural`` mode.

**Redirects.** ``global name`` sends lookups, and bindings, to the module
scope; ``nonlocal name`` to the nearest enclosing function scope that binds
the name. A binding made through either is a non-definition binding of its
target scope, so a definition there gives ``none(mixed-bindings)`` (the
``nonlocal``-rebind rule of the Codex review of treesitter-chunker#683).

**Outcomes** (section 7.6 with R-1's precedence): a lookup meets, in order,

1. ``dynamic-scope`` for a module-scope or class-body lookup in a file that
   may bind names at run time (below), then ``star-import`` for a
   module-scope lookup in a file with ``from m import *``, then ``unmapped``
   for a scope holding a fail-closed node kind;
2. ``class-scope-bound`` for class-body code and a name the class binds;
3. the binding's own reason: a non-symbol binding's class (``parameter``,
   ``local-variable``), ``mixed-bindings`` for definitions mixed with other
   bindings or two or more imports, ``conditional`` for a single import under
   a conditional statement;
4. the group rule (section 7.4): one unconditional, undecorated definition
   proves itself (``t1.lexical``); a single decorated one gives
   ``expression-bound`` and a single conditional one ``conditional``; two or
   more definitions prove the whole group, which narrows but never resolves
   (section 8). A module-level definition or import whose name is a builtin
   (:data:`BUILTINS`) never proves (``builtin-shadow``): until it runs, the
   name is the builtin, not a ``NameError``. A definition is conditional when an ``if``, ``elif``,
   ``else``, ``try``, ``except``, ``finally``, ``while``, ``for``, ``with``,
   ``match`` or ``case`` lies between it and its scope's body;
   ``decorated_definition`` is transparent.

A name bound nowhere in the file is ``unbound`` (a builtin or a
``NameError``).

A file that mentions ``f_locals`` anywhere (an attribute or a constant string)
gives ``dynamic-scope`` for every lookup, function scopes included: a frame's
``f_locals`` writes through to a function's locals (PEP 667, Python 3.13+).

**Dynamic binding fails closed** (``dynamic-scope``). A file may bind module
names at run time when it mentions ``exec``, ``eval``, ``globals``,
``vars``, ``locals``, ``__import__``, ``__builtins__``, ``builtins``,
``importlib`` or ``execfile`` anywhere outside an attribute name, a keyword
argument name or a ``def``/``class`` name (so ``import builtins as b`` and
``from importlib import import_module`` count); writes through
``sys.modules`` (``sys`` reached by name, through an ``as`` alias, or as an
attribute ``os.sys``), a dunder attribute of ``sys`` (``sys.__dict__``), the
``sys`` module handed on as a value (``getattr(sys, "modules")``,
``f(sys)``), ``from sys import modules``; ``__main__`` or an alias of it used
other than in an import; ``X.modules[__name__]`` or
``X.modules.get(__name__)`` (also ``__getitem__``, ``setdefault``, ``pop``)
through any receiver ``X``; an import of the file's own module (``import a``
or ``from . import a`` in ``a.py``); a function's ``__globals__``, a frame's
``f_globals``/``f_builtins`` and ``inspect.getmodule``; a constant string
(a literal, adjacent literals or literals joined by ``+``) that is one of
those attribute names or ``modules``, alone or as a part of a dotted path
(``getattr(f, "__globals__")``, ``attrgetter("sys.modules")``); and the
Python 2 ``exec`` statement. Inside a function, ``exec`` and ``locals()``
cannot rebind a local, so without ``f_locals`` lookups that resolve in a
function scope are unaffected; a class body's namespace is a dict they can
write, so class-body lookups fail closed too. Monkeypatching from other
modules (plan R10) and run-time paths no syntactic rule sees (plan R12:
frame writes from another module, computed strings, other ``X.modules``
uses, ``gc``/``ctypes`` tricks) are not tracked.

**Indentation that depends on the tab width is not analyzed.** tree-sitter
counts a tab as eight more columns, while CPython advances to the next
multiple of eight, so a line whose leading whitespace has a space before a
tab can land in a different block without a parse error. Such a file, or one
with a form feed in a line's leading whitespace, raises
:class:`AmbiguousIndentationError` and is ``supported: false``.

**Identifiers are compared by their source spelling, so a file with a
non-ASCII identifier is not analyzed.** Python normalizes identifiers to
NFKC (``ﬁle`` and ``file`` are one name), and the chunker's symbol names keep
the source spelling, so a normalized lookup could join a binding the engine
cannot see. :func:`analyze` raises :class:`NonAsciiNameError` for any
non-ASCII identifier, or any non-ASCII character outside string literals and
comments, and the caller gives the file ``supported: false``: its edges stay
exactly as off (section 5.3). ASCII names are NFKC-invariant.

Every named node the pass visits is classified through the allow-list
(section 7.5). A fail-closed kind, including an unclassified one, poisons the
scope it appears in, and any lookup reaching that scope gives
``none(unmapped)``. The pass is recursive; a tree too deep for it raises
``RecursionError`` (see :data:`MAX_DEPTH`), which the caller turns into
``supported: false``.

For a member callee (``m.f``) the head identifier is looked up; a head that is
not an identifier (``C().f``) has no binding (``unbound``). Member calls are
never eligible in Tier 1, so their outcome is recorded only. Proof
declarations are the ``function_definition`` and ``class_definition`` nodes
the chunker emits as symbols, never the enclosing ``decorated_definition``.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import allowlist

LANGUAGE = "python"
# Deep trees fail closed with RecursionError (section 5.3). The counter grows
# by one per tree level and the pass uses one or two Python frames per level,
# so Python's own recursion limit can stop it first; either way the error is
# the same and the file keeps its off-mode edges. (The chunker itself stops
# at depth 900.)
MAX_DEPTH = 500

# Binding classes. ``parameter`` and ``local-variable`` are also the ``none``
# reasons of a lookup that ends on them.
SYMBOL = "symbol"
IMPORT = "import"
PARAMETER = "parameter"
LOCAL = "local-variable"
UNMAPPED = "unmapped"

_MODULE = "module"
_FUNCTION = "function"
_LAMBDA = "lambda"
_CLASS = "class"
_COMPREHENSION = "comprehension"
_TYPE_PARAMS = "type-parameters"
_POISONED = "poisoned"

_COMPREHENSIONS = frozenset(
    {
        "list_comprehension",
        "set_comprehension",
        "dictionary_comprehension",
        "generator_expression",
    }
)
# Statements that make a definition or import between them and its scope's
# body conditional (section 7.3).
_CONDITIONAL_NODES = frozenset(
    {
        "if_statement",
        "elif_clause",
        "else_clause",
        "try_statement",
        "except_clause",
        "finally_clause",
        "while_statement",
        "for_statement",
        "with_statement",
        "match_statement",
        "case_clause",
    }
)
# Names whose mention may bind module names at run time (dynamic-scope).
_DYNAMIC_NAMES = frozenset(
    {
        "exec",
        "eval",
        "globals",
        "vars",
        "locals",
        "__import__",
        "__builtins__",
        "builtins",
        "importlib",
        "execfile",
    }
)
# Attributes that reach a namespace dict of a module or frame, or a module
# object (``inspect.getmodule``).
_DYNAMIC_ATTRIBUTES = frozenset(
    {"__globals__", "f_globals", "f_locals", "f_builtins", "getmodule"}
)
_SYS = "sys"
_SYS_MODULES = "modules"
# ``import __main__`` reaches the namespace of the module run as a script,
# which may be this one: any use other than importing it is dynamic.
_MAIN = "__main__"
# ``frame.f_locals`` writes through to a function's locals (PEP 667, Python
# 3.13+): every lookup of a file that mentions it fails closed.
_FRAME_LOCALS = "f_locals"
# ``X.modules[__name__]`` and these methods with ``__name__`` reach this
# module's object through any receiver (``collections._sys.modules``).
_MODULE_GETTERS = frozenset({"get", "__getitem__", "setdefault", "pop"})
# A string literal naming one of these, alone or as a part of a dotted path
# (``getattr(f, "__globals__")``, ``attrgetter("sys.modules")``), counts as a
# mention of the attribute.
_LITERAL_DYNAMIC = _DYNAMIC_ATTRIBUTES | {_SYS_MODULES}
# ``dir(builtins)`` on CPython 3.14 (``python -I``), pinned by a test, plus
# the Python 2 builtins the grammar's Python 2 forms imply. A module-level
# definition of one of these names never proves: until the definition runs,
# the name falls back to the builtin (``builtin-shadow``).
BUILTINS_314 = frozenset(
    [
        "ArithmeticError",
        "AssertionError",
        "AttributeError",
        "BaseException",
        "BaseExceptionGroup",
        "BlockingIOError",
        "BrokenPipeError",
        "BufferError",
        "BytesWarning",
        "ChildProcessError",
        "ConnectionAbortedError",
        "ConnectionError",
        "ConnectionRefusedError",
        "ConnectionResetError",
        "DeprecationWarning",
        "EOFError",
        "Ellipsis",
        "EncodingWarning",
        "EnvironmentError",
        "Exception",
        "ExceptionGroup",
        "False",
        "FileExistsError",
        "FileNotFoundError",
        "FloatingPointError",
        "FutureWarning",
        "GeneratorExit",
        "IOError",
        "ImportError",
        "ImportWarning",
        "IndentationError",
        "IndexError",
        "InterruptedError",
        "IsADirectoryError",
        "KeyError",
        "KeyboardInterrupt",
        "LookupError",
        "MemoryError",
        "ModuleNotFoundError",
        "NameError",
        "None",
        "NotADirectoryError",
        "NotImplemented",
        "NotImplementedError",
        "OSError",
        "OverflowError",
        "PendingDeprecationWarning",
        "PermissionError",
        "ProcessLookupError",
        "PythonFinalizationError",
        "RecursionError",
        "ReferenceError",
        "ResourceWarning",
        "RuntimeError",
        "RuntimeWarning",
        "StopAsyncIteration",
        "StopIteration",
        "SyntaxError",
        "SyntaxWarning",
        "SystemError",
        "SystemExit",
        "TabError",
        "TimeoutError",
        "True",
        "TypeError",
        "UnboundLocalError",
        "UnicodeDecodeError",
        "UnicodeEncodeError",
        "UnicodeError",
        "UnicodeTranslateError",
        "UnicodeWarning",
        "UserWarning",
        "ValueError",
        "Warning",
        "ZeroDivisionError",
        "_IncompleteInputError",
        "__build_class__",
        "__debug__",
        "__doc__",
        "__import__",
        "__loader__",
        "__name__",
        "__package__",
        "__spec__",
        "abs",
        "aiter",
        "all",
        "anext",
        "any",
        "ascii",
        "bin",
        "bool",
        "breakpoint",
        "bytearray",
        "bytes",
        "callable",
        "chr",
        "classmethod",
        "compile",
        "complex",
        "copyright",
        "credits",
        "delattr",
        "dict",
        "dir",
        "divmod",
        "enumerate",
        "eval",
        "exec",
        "exit",
        "filter",
        "float",
        "format",
        "frozenset",
        "getattr",
        "globals",
        "hasattr",
        "hash",
        "help",
        "hex",
        "id",
        "input",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "license",
        "list",
        "locals",
        "map",
        "max",
        "memoryview",
        "min",
        "next",
        "object",
        "oct",
        "open",
        "ord",
        "pow",
        "print",
        "property",
        "quit",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "setattr",
        "slice",
        "sorted",
        "staticmethod",
        "str",
        "sum",
        "super",
        "tuple",
        "type",
        "vars",
        "zip",
    ]
)
PY2_BUILTINS = frozenset(
    [
        "StandardError",
        "apply",
        "basestring",
        "buffer",
        "cmp",
        "coerce",
        "execfile",
        "file",
        "intern",
        "long",
        "raw_input",
        "reduce",
        "reload",
        "unichr",
        "unicode",
        "xrange",
    ]
)
BUILTINS = BUILTINS_314 | PY2_BUILTINS
_IMPORT_STATEMENTS = frozenset(
    {"import_statement", "import_from_statement", "future_import_statement"}
)
# Target forms whose identifiers all bind (a tuple, list or starred target).
_TARGET_CONTAINERS = frozenset(
    {
        "tuple_pattern",
        "list_pattern",
        "pattern_list",
        "tuple",
        "list",
        "expression_list",
        "parenthesized_expression",
        "list_splat_pattern",
        "list_splat",
        "parenthesized_list_splat",
        "as_pattern_target",
    }
)
# Subtrees whose leaves are text, not code (identifiers in an f-string's
# interpolations are still checked).
_STRING_NODES = frozenset({"string", "comment"})


def _none(reason: str) -> dict[str, Any]:
    return {"outcome": "none", "reason": reason}


def _text(node: Any, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _same(left: Any, right: Any) -> bool:
    return left is not None and right is not None and bool(left.id == right.id)


def _dunder(name: str) -> bool:
    return len(name) > 4 and name.startswith("__") and name.endswith("__")


@dataclass(frozen=True, eq=False)
class _Binding:
    """One binding of one name in one scope."""

    cls: str
    decl: Any = None
    kind: str = ""
    conditional: bool = False
    decorated: bool = False
    info: Mapping[str, str] | None = None


_IMPLICIT = _Binding(LOCAL)


@dataclass(eq=False)
class _Scope:
    """A scope, its bindings and what makes its lookups fail closed."""

    kind: str
    node: Any
    parent: _Scope | None = None
    bindings: dict[str, list[_Binding]] = field(default_factory=dict)
    # Names written in this scope before redirects, for ``nonlocal`` targets.
    assigned: set[str] = field(default_factory=set)
    globals: set[str] = field(default_factory=set)
    nonlocals: set[str] = field(default_factory=set)
    poisoned: bool = False
    # A class with any base or keyword: its metaclass's ``__prepare__``, or a
    # ``__missing__`` namespace, may supply any name to the class body.
    open_namespace: bool = False

    def bind(self, name: str, binding: _Binding) -> None:
        self.bindings.setdefault(name, []).append(binding)


# A scope-opening node the pass never reached (it sits under a fail-closed
# kind): every lookup through it fails closed.
_UNVISITED = _Scope(_POISONED, None, poisoned=True)


class _Analysis:
    """Scopes and bindings of one Python file, and lookups through them."""

    def __init__(
        self, root: Any, source: bytes, own_names: frozenset[str] = frozenset()
    ) -> None:
        self.root = root
        self.source = source
        # The file's own module name (its stem, or its package for
        # ``__init__.py``): importing it is a self-import.
        self.own_names = own_names
        self.scopes: dict[tuple[int, str], _Scope] = {}
        self.events: list[tuple[_Scope, str, _Binding]] = []
        self.dynamic = False
        self.frame_locals = False
        self.star = False
        self.handlers: dict[str, Callable[[Any, _Scope, int], None]] = {
            "function_definition": self._function,
            "class_definition": self._class,
            "decorated_definition": self._decorated,
            "lambda": self._lambda,
            "list_comprehension": self._comprehension,
            "set_comprehension": self._comprehension,
            "dictionary_comprehension": self._comprehension,
            "generator_expression": self._comprehension,
            "assignment": self._assignment,
            "augmented_assignment": self._assignment,
            "named_expression": self._walrus,
            "for_statement": self._for,
            "as_pattern": self._as_pattern,
            "except_clause": self._except,
            "delete_statement": self._delete,
            "import_statement": self._import,
            "import_from_statement": self._import_from,
            "future_import_statement": self._future_import,
            "global_statement": self._global,
            "nonlocal_statement": self._nonlocal,
            "case_pattern": self._case_pattern,
            "type_alias_statement": self._type_alias,
            "exec_statement": self._exec_statement,
            "wildcard_import": self._wildcard,
        }
        self.module = self._scope(_MODULE, root, None, "scope")
        self._children(root, self.module, 0)
        self._scan_dynamic()
        for scope, name, binding in self.events:
            self._bind(scope, name, binding)

    # -- building -----------------------------------------------------------

    def _scope(self, kind: str, node: Any, parent: _Scope | None, role: str) -> _Scope:
        scope = _Scope(kind, node, parent)
        self.scopes[(node.id, role)] = scope
        return scope

    def visit(self, node: Any, scope: _Scope, depth: int) -> None:
        if depth > MAX_DEPTH:
            msg = "Python scope analysis exceeds safe traversal depth"
            raise RecursionError(msg)
        if not node.is_named:
            return
        entry = allowlist.classify(LANGUAGE, node.type)
        if entry.classification == allowlist.FAIL_CLOSED:
            # Unknown binding forms make every lookup through here unmapped.
            scope.poisoned = True
            return
        handler = self.handlers.get(node.type)
        if handler is not None:
            handler(node, scope, depth)
            return
        self._children(node, scope, depth)

    def _children(self, node: Any, scope: _Scope, depth: int) -> None:
        for child in node.named_children:
            self.visit(child, scope, depth + 1)

    def _fields(self, node: Any) -> Iterator[tuple[str | None, Any]]:
        for index, child in enumerate(node.children):
            if child.is_named:
                yield node.field_name_for_child(index), child

    def _record(self, scope: _Scope, name_node: Any, binding: _Binding) -> None:
        if name_node is None or name_node.type != "identifier":
            # A name position holding anything else is not understood.
            scope.poisoned = True
            return
        name = _text(name_node, self.source)
        scope.assigned.add(name)
        self.events.append((scope, name, binding))

    def _conditional(self, node: Any, scope: _Scope) -> bool:
        current = node.parent
        while current is not None and not _same(current, scope.node):
            if current.type in _CONDITIONAL_NODES:
                return True
            current = current.parent
        return False

    def _targets(self, node: Any, scope: _Scope, depth: int, cls: str = LOCAL) -> None:
        """Bind every name a target writes; fail closed on unknown forms."""
        if depth > MAX_DEPTH:
            msg = "Python scope analysis exceeds safe traversal depth"
            raise RecursionError(msg)
        kind = node.type
        if kind == "identifier":
            self._record(scope, node, _Binding(cls))
        elif kind in _TARGET_CONTAINERS:
            for child in node.named_children:
                self._targets(child, scope, depth + 1, cls)
        elif kind in ("attribute", "subscript"):
            # ``x.y = v`` and ``x[i] = v`` write no name; their parts are read.
            self.visit(node, scope, depth + 1)
        elif kind not in ("comment", "line_continuation"):
            scope.poisoned = True

    def _type_params(self, node: Any, scope: _Scope, depth: int) -> _Scope:
        """The type-parameter scope of a generic definition, or ``scope``."""
        params = node.child_by_field_name("type_parameters")
        if params is None:
            return scope
        return self._type_param_scope(node, params, scope, depth)

    def _type_param_scope(
        self, node: Any, params: Any, scope: _Scope, depth: int
    ) -> _Scope:
        inner = self._scope(_TYPE_PARAMS, node, scope, "tparams")
        # Every identifier in the list binds, bounds included: an extra
        # binding can only fail closed.
        for ident in _identifiers(params):
            self._record(inner, ident, _Binding(PARAMETER))
        self.visit(params, inner, depth + 1)
        return inner

    def _parameters(
        self, params: Any, inner: _Scope, outer: _Scope, depth: int
    ) -> None:
        """Bind parameter names in ``inner``; defaults and annotations run in
        ``outer``."""
        for parameter in params.named_children:
            if parameter.type in ("positional_separator", "keyword_separator"):
                continue
            if parameter.type == "comment":
                continue
            parts: list[tuple[str | None, Any]] = (
                list(self._fields(parameter))
                if parameter.named_children
                else [(None, parameter)]
            )
            for name, child in parts:
                if name in ("type", "value"):
                    self.visit(child, outer, depth + 1)
                    continue
                # Every other identifier is a parameter name (``x``, ``*a``,
                # ``**kw``, a Python 2 tuple parameter).
                for ident in _identifiers(child):
                    self._record(inner, ident, _Binding(PARAMETER))

    # -- handlers -----------------------------------------------------------

    def _function(
        self, node: Any, scope: _Scope, depth: int, decorated: bool = False
    ) -> None:
        self._record(
            scope,
            node.child_by_field_name("name"),
            _Binding(
                SYMBOL,
                decl=node,
                kind="function",
                conditional=self._conditional(node, scope),
                decorated=decorated,
            ),
        )
        header = self._type_params(node, scope, depth)
        body_scope = self._scope(_FUNCTION, node, header, "scope")
        for name, child in self._fields(node):
            if name in ("name", "type_parameters"):
                continue
            if name == "parameters":
                self._parameters(child, body_scope, header, depth)
            elif name == "body":
                self.visit(child, body_scope, depth + 1)
            else:
                self.visit(child, header, depth + 1)

    def _class(
        self, node: Any, scope: _Scope, depth: int, decorated: bool = False
    ) -> None:
        self._record(
            scope,
            node.child_by_field_name("name"),
            _Binding(
                SYMBOL,
                decl=node,
                kind="class",
                conditional=self._conditional(node, scope),
                decorated=decorated,
            ),
        )
        header = self._type_params(node, scope, depth)
        class_scope = self._scope(_CLASS, node, header, "scope")
        bases = node.child_by_field_name("superclasses")
        class_scope.open_namespace = bases is not None and any(
            child.type not in ("comment", "line_continuation")
            for child in bases.named_children
        )
        for name, child in self._fields(node):
            if name in ("name", "type_parameters"):
                continue
            if name == "body":
                self.visit(child, class_scope, depth + 1)
            else:
                self.visit(child, header, depth + 1)

    def _decorated(self, node: Any, scope: _Scope, depth: int) -> None:
        definition = node.child_by_field_name("definition")
        for child in node.named_children:
            if _same(child, definition) and child.type == "function_definition":
                self._function(child, scope, depth + 1, decorated=True)
            elif _same(child, definition) and child.type == "class_definition":
                self._class(child, scope, depth + 1, decorated=True)
            else:
                self.visit(child, scope, depth + 1)

    def _lambda(self, node: Any, scope: _Scope, depth: int) -> None:
        inner = self._scope(_LAMBDA, node, scope, "scope")
        for name, child in self._fields(node):
            if name == "parameters":
                self._parameters(child, inner, scope, depth)
            elif name == "body":
                self.visit(child, inner, depth + 1)
            else:
                self.visit(child, scope, depth + 1)

    def _comprehension(self, node: Any, scope: _Scope, depth: int) -> None:
        inner = self._scope(_COMPREHENSION, node, scope, "scope")
        first = True
        for child in node.named_children:
            if child.type != "for_in_clause":
                self.visit(child, inner, depth + 1)
                continue
            # The first iterable runs in the enclosing scope.
            iterable_scope = scope if first else inner
            first = False
            for name, part in self._fields(child):
                if name == "left":
                    self._targets(part, inner, depth + 1)
                    if node.type == "list_comprehension":
                        # Python 2 leaks list-comprehension targets into the
                        # enclosing scope; the grammar accepts Python 2, and
                        # the extra binding can only fail closed.
                        self._targets(part, scope, depth + 1)
                else:
                    self.visit(part, iterable_scope, depth + 1)

    def _assignment(self, node: Any, scope: _Scope, depth: int) -> None:
        for name, child in self._fields(node):
            if name == "left":
                self._targets(child, scope, depth + 1)
            else:
                self.visit(child, scope, depth + 1)

    def _walrus(self, node: Any, scope: _Scope, depth: int) -> None:
        target = scope
        while target.kind in (_COMPREHENSION, _TYPE_PARAMS) and target.parent:
            target = target.parent
        for name, child in self._fields(node):
            if name == "name":
                self._record(target, child, _Binding(LOCAL))
            else:
                self.visit(child, scope, depth + 1)

    def _for(self, node: Any, scope: _Scope, depth: int) -> None:
        for name, child in self._fields(node):
            if name == "left":
                self._targets(child, scope, depth + 1)
            else:
                self.visit(child, scope, depth + 1)

    def _as_pattern(self, node: Any, scope: _Scope, depth: int) -> None:
        """``with x as y`` and ``except E as e``; a ``case`` capture is bound
        by :meth:`_case_pattern`."""
        for name, child in self._fields(node):
            if name == "alias":
                self._targets(child, scope, depth + 1)
            else:
                self.visit(child, scope, depth + 1)

    def _except(self, node: Any, scope: _Scope, depth: int) -> None:
        seen_value = False
        for name, child in self._fields(node):
            if name == "value" and seen_value:
                # Python 2 ``except E, e:`` binds ``e``.
                self._targets(child, scope, depth + 1)
                continue
            seen_value = seen_value or name == "value"
            self.visit(child, scope, depth + 1)

    def _delete(self, node: Any, scope: _Scope, depth: int) -> None:
        for child in node.named_children:
            self._targets(child, scope, depth + 1)

    def _import_binding(
        self, scope: _Scope, statement: Any, name_node: Any, info: dict[str, str]
    ) -> None:
        self._record(
            scope,
            name_node,
            _Binding(
                IMPORT, conditional=self._conditional(statement, scope), info=info
            ),
        )

    def _import(self, node: Any, scope: _Scope, depth: int) -> None:
        for name, child in self._fields(node):
            if name != "name":
                self.visit(child, scope, depth + 1)
                continue
            if child.type == "aliased_import":
                module = child.child_by_field_name("name")
                bound = child.child_by_field_name("alias")
            else:
                module = child
                bound = child.named_children[0] if child.named_children else None
            text = _text(module, self.source) if module is not None else ""
            self._import_binding(scope, node, bound, {"form": "import", "module": text})

    def _import_from(self, node: Any, scope: _Scope, depth: int) -> None:
        module_node = node.child_by_field_name("module_name")
        module = _text(module_node, self.source) if module_node is not None else ""
        for name, child in self._fields(node):
            if name != "name":
                self.visit(child, scope, depth + 1)
                continue
            if child.type == "aliased_import":
                imported = child.child_by_field_name("name")
                bound = child.child_by_field_name("alias")
            else:
                imported = child
                parts = child.named_children
                bound = parts[0] if len(parts) == 1 else None
            text = _text(imported, self.source) if imported is not None else ""
            self._import_binding(
                scope, node, bound, {"form": "from", "module": module, "name": text}
            )

    def _future_import(self, node: Any, scope: _Scope, depth: int) -> None:
        for name, child in self._fields(node):
            if name != "name":
                self.visit(child, scope, depth + 1)
                continue
            if child.type == "aliased_import":
                imported = child.child_by_field_name("name")
                bound = child.child_by_field_name("alias")
            else:
                imported = child
                parts = child.named_children
                bound = parts[0] if len(parts) == 1 else None
            text = _text(imported, self.source) if imported is not None else ""
            self._import_binding(
                scope,
                node,
                bound,
                {"form": "from", "module": "__future__", "name": text},
            )

    def _wildcard(self, node: Any, scope: _Scope, depth: int) -> None:
        del node, scope, depth
        self.star = True

    def _global(self, node: Any, scope: _Scope, depth: int) -> None:
        del depth
        if scope.kind == _MODULE:
            return  # a no-op at module level
        scope.globals.update(_text(ident, self.source) for ident in _identifiers(node))

    def _nonlocal(self, node: Any, scope: _Scope, depth: int) -> None:
        del depth
        scope.nonlocals.update(
            _text(ident, self.source) for ident in _identifiers(node)
        )

    def _case_pattern(self, node: Any, scope: _Scope, depth: int) -> None:
        """Bind the names a ``case`` pattern captures.

        Every identifier binds except a dotted value pattern (``Color.RED``),
        a class pattern's class name and a keyword pattern's keyword. An
        extra binding can only fail closed.
        """
        del depth
        for ident in _pattern_captures(node):
            self._record(scope, ident, _Binding(LOCAL))

    def _type_alias(self, node: Any, scope: _Scope, depth: int) -> None:
        name_node, params = _alias_parts(node)
        self._record(scope, name_node, _Binding(LOCAL))
        inner = (
            self._type_param_scope(node, params, scope, depth)
            if params is not None
            else scope
        )
        for name, child in self._fields(node):
            if name != "left":
                self.visit(child, inner, depth + 1)

    def _exec_statement(self, node: Any, scope: _Scope, depth: int) -> None:
        self.dynamic = True
        self._children(node, scope, depth)

    # -- dynamic binding ----------------------------------------------------

    def _scan_dynamic(self) -> None:
        """Set ``dynamic`` if the file may bind module names at run time, and
        ``frame_locals`` if it may write a function's locals."""
        source = self.source
        sys_names = {_SYS}
        main_names = {_MAIN}
        identifiers: list[Any] = []
        stack = [self.root]
        while stack:
            node = stack.pop()
            kind = node.type
            if kind == "identifier":
                identifiers.append(node)
            elif kind == "aliased_import":
                imported = node.child_by_field_name("name")
                alias = node.child_by_field_name("alias")
                last = (
                    _text(imported.named_children[-1], source)
                    if imported is not None and imported.named_children
                    else ""
                )
                if alias is not None and last == _SYS:
                    sys_names.add(_text(alias, source))
                if alias is not None and last == _MAIN:
                    main_names.add(_text(alias, source))
            elif kind in ("string", "concatenated_string", "binary_operator"):
                value = _constant_string(node, source)
                if value is not None:
                    self._literal_use(value)
            if kind in ("import_statement", "import_from_statement"):
                self._import_use(node)
            stack.extend(node.named_children)
        for ident in identifiers:
            name = _text(ident, source)
            parent = ident.parent
            if parent is None:
                continue
            if parent.type == "attribute" and _same(
                ident, parent.child_by_field_name("attribute")
            ):
                if name in _DYNAMIC_ATTRIBUTES:
                    self.dynamic = True
                    self.frame_locals = self.frame_locals or name == _FRAME_LOCALS
                elif name == _SYS:
                    self._sys_use(parent)
                elif name == _SYS_MODULES:
                    self._modules_use(parent)
                continue
            if parent.type == "keyword_argument" and _same(
                ident, parent.child_by_field_name("name")
            ):
                continue
            if parent.type in ("function_definition", "class_definition") and _same(
                ident, parent.child_by_field_name("name")
            ):
                continue
            if name in _DYNAMIC_NAMES:
                self.dynamic = True
            elif name in sys_names:
                self._sys_use(ident)
            elif name in main_names and not _import_context(ident):
                # ``__main__.helper = len``, ``setattr(m, ...)``.
                self.dynamic = True

    def _literal_use(self, value: str) -> None:
        """A constant string naming a dynamic attribute counts as a mention
        of it (the analogue of PR 3's literal-key rule)."""
        parts = set(value.split("."))
        if parts & _LITERAL_DYNAMIC:
            self.dynamic = True
        if _FRAME_LOCALS in parts:
            self.frame_locals = True

    def _import_use(self, node: Any) -> None:
        """``from sys import modules`` and imports of the file's own module
        (``import a`` in ``a.py``, ``from . import a``) are dynamic."""
        source = self.source
        module = node.child_by_field_name("module_name")
        for index, child in enumerate(node.children):
            if node.field_name_for_child(index) != "name":
                continue
            imported = (
                child.child_by_field_name("name")
                if child.type == "aliased_import"
                else child
            )
            if imported is None:
                continue
            text = _text(imported, source)
            if node.type == "import_from_statement":
                if (
                    module is not None
                    and text == _SYS_MODULES
                    and _text(module, source).rsplit(".", 1)[-1] == _SYS
                ):
                    self.dynamic = True
                if text in self.own_names:
                    self.dynamic = True
            elif text.rsplit(".", 1)[-1] in self.own_names:
                self.dynamic = True

    def _modules_use(self, node: Any) -> None:
        """``X.modules[__name__]``, ``X.modules.get(__name__)`` and the like
        reach this module through any receiver ``X``; other ``X.modules`` uses
        are left to plan risk R12."""
        parent = node.parent
        if parent is None:
            return
        if parent.type == "subscript" and _same(
            node, parent.child_by_field_name("value")
        ):
            keys = [
                child
                for index, child in enumerate(parent.children)
                if parent.field_name_for_child(index) == "subscript"
            ]
            if any(_text(key, self.source) == "__name__" for key in keys):
                self.dynamic = True
            return
        if parent.type == "attribute" and _same(
            node, parent.child_by_field_name("object")
        ):
            method = parent.child_by_field_name("attribute")
            call = parent.parent
            if (
                method is not None
                and _text(method, self.source) in _MODULE_GETTERS
                and call is not None
                and call.type == "call"
                and _same(parent, call.child_by_field_name("function"))
            ):
                arguments = call.child_by_field_name("arguments")
                first = (
                    arguments.named_children[0]
                    if arguments is not None and arguments.named_children
                    else None
                )
                if first is not None and _text(first, self.source) == "__name__":
                    self.dynamic = True

    def _sys_use(self, node: Any) -> None:
        """A use of the ``sys`` module: ``sys.modules``, a dunder attribute
        (``sys.__dict__["modules"]``) or handing it on is dynamic; reading
        another attribute is not."""
        parent = node.parent
        if parent is None:
            return
        if parent.type == "attribute" and _same(
            node, parent.child_by_field_name("object")
        ):
            attribute = parent.child_by_field_name("attribute")
            text = _text(attribute, self.source) if attribute is not None else ""
            if text == _SYS_MODULES or _dunder(text):
                self.dynamic = True
            return
        if not _import_context(node):
            self.dynamic = True

    # -- redirects ----------------------------------------------------------

    def _nonlocal_target(self, scope: _Scope, name: str) -> _Scope | None:
        """The enclosing function scope that owns ``name`` for a
        ``nonlocal`` in ``scope``, or ``None``."""
        outer = scope.parent
        while outer is not None and outer.kind != _MODULE:
            if outer.kind != _CLASS and name not in outer.nonlocals:
                if name in outer.globals:
                    return None
                if name in outer.assigned:
                    return outer
            outer = outer.parent
        return None

    def _bind(self, scope: _Scope, name: str, binding: _Binding) -> None:
        target: _Scope | None = scope
        if name in scope.globals:
            target = self.module
        elif name in scope.nonlocals:
            target = self._nonlocal_target(scope, name) or self.module
        if target is not scope:
            # A write through ``global`` or ``nonlocal`` is a non-definition
            # binding of the scope it lands in (section 7.3).
            binding = _Binding(LOCAL)
        assert target is not None
        target.bind(name, binding)

    # -- lookup -------------------------------------------------------------

    def _scopes_at(self, node: Any, child: Any, ident: Any) -> Iterator[_Scope]:
        kind = node.type
        if kind == "module":
            yield self.module
        elif kind in ("function_definition", "class_definition"):
            # The body runs in the definition's own scope; everything but the
            # name (parameters, annotations, bases, the body) also sees a
            # generic definition's type parameters.
            if _same(child, node.child_by_field_name("body")):
                yield self.scopes.get((node.id, "scope"), _UNVISITED)
            if not _same(child, node.child_by_field_name("name")):
                params = self.scopes.get((node.id, "tparams"))
                if params is not None:
                    yield params
                elif node.child_by_field_name("type_parameters") is not None:
                    yield _UNVISITED
        elif kind == "lambda":
            if _same(child, node.child_by_field_name("body")):
                yield self.scopes.get((node.id, "scope"), _UNVISITED)
        elif kind in _COMPREHENSIONS:
            if not _in_first_iterable(node, ident):
                yield self.scopes.get((node.id, "scope"), _UNVISITED)
        elif kind == "type_alias_statement":
            params = self.scopes.get((node.id, "tparams"))
            if params is not None:
                yield params
            elif _alias_parts(node)[1] is not None:
                yield _UNVISITED

    def _chain(self, ident: Any) -> Iterator[_Scope]:
        child = ident
        node = ident.parent
        while node is not None:
            yield from self._scopes_at(node, child, ident)
            child, node = node, node.parent

    def lookup(self, ident: Any) -> dict[str, Any]:
        """The outcome of a value lookup of ``ident``'s name."""
        name = _text(ident, self.source)
        if self.frame_locals:
            # ``frame.f_locals`` writes any function's locals (PEP 667).
            return _none("dynamic-scope")
        crossed = False  # a function-like scope lies between ``ident`` and here
        for scope in self._chain(ident):
            if scope.kind == _CLASS:
                if crossed:
                    if name in ("__class__", "__classdict__"):
                        # The implicit class cell of a method.
                        return _none(LOCAL)
                    continue
                if self.dynamic:
                    # exec/locals() in a class body write its namespace.
                    return _none("dynamic-scope")
                if scope.open_namespace:
                    # A metaclass's ``__prepare__`` (possibly inherited from a
                    # base in another file) may supply any name.
                    return _none("class-scope-bound")
            if scope.kind == _MODULE:
                return self._module_lookup(name)
            if scope.kind != _TYPE_PARAMS:
                crossed = True
            if scope.poisoned:
                return _none(UNMAPPED)
            if name in scope.globals:
                return self._module_lookup(name)
            if name in scope.nonlocals:
                target = self._nonlocal_target(scope, name)
                if target is None:
                    return _none(UNMAPPED)
                if target.poisoned:
                    return _none(UNMAPPED)
                return self._decide(target, name)
            if name in scope.bindings or (scope.kind == _CLASS and _dunder(name)):
                if scope.kind == _CLASS:
                    return _none("class-scope-bound")
                return self._decide(scope, name)
        return self._module_lookup(name)  # pragma: no cover - module ends the chain

    def _module_lookup(self, name: str) -> dict[str, Any]:
        if self.dynamic:
            return _none("dynamic-scope")
        if self.star:
            return _none("star-import")
        if self.module.poisoned:
            return _none(UNMAPPED)
        if name not in self.module.bindings and not _dunder(name):
            return _none("unbound")
        return self._decide(self.module, name)

    def _decide(self, scope: _Scope, name: str) -> dict[str, Any]:
        bindings = list(scope.bindings.get(name, ()))
        if scope.kind in (_MODULE, _CLASS) and _dunder(name):
            # Module and class namespaces bind dunder names implicitly.
            bindings.insert(0, _IMPLICIT)
        symbols = [binding for binding in bindings if binding.cls == SYMBOL]
        imports = [binding for binding in bindings if binding.cls == IMPORT]
        others = [
            binding for binding in bindings if binding.cls not in (SYMBOL, IMPORT)
        ]
        if others and not symbols and not imports:
            return _none(others[0].cls)
        if len(imports) > 1 or sum(map(bool, (symbols, imports, others))) > 1:
            return _none("mixed-bindings")
        if imports:
            if imports[0].conditional:
                return _none("conditional")
            outcome: dict[str, Any] = {
                "outcome": "import",
                "binding": dict(imports[0].info or {}),
            }
        else:
            outcome = _group(symbols)
        if outcome["outcome"] != "none" and scope.kind == _MODULE and name in BUILTINS:
            # Until the definition or import runs, the name is the builtin.
            return _none("builtin-shadow")
        return outcome


def _group(symbols: Sequence[_Binding]) -> dict[str, Any]:
    """The group rule (section 7.4) for one name's definitions."""
    if len(symbols) == 1:
        (only,) = symbols
        if only.decorated:
            # The name is bound to the decorator's result, not the def.
            return _none("expression-bound")
        if only.conditional:
            return _none("conditional")
    # Two or more definitions prove the whole group: Python redefinitions
    # narrow to the group and never resolve (section 8).
    proof = sorted(
        [binding.decl.type, binding.decl.start_byte, binding.decl.end_byte]
        for binding in symbols
    )
    return {"outcome": "local", "proof": proof, "rules": []}


def _import_context(node: Any) -> bool:
    """Whether a name sits in an import, ``global`` or ``nonlocal``
    statement (a binding position, not a use)."""
    context = node.parent
    while context is not None and context.type in ("dotted_name", "aliased_import"):
        context = context.parent
    return context is not None and (
        context.type in _IMPORT_STATEMENTS
        or context.type in ("global_statement", "nonlocal_statement")
    )


def _constant_string(node: Any, source: bytes) -> str | None:
    """The value of a constant string expression: a literal without
    interpolations, adjacent literals, or literals joined by ``+``.

    Anything computed (a name, a call, an interpolation) gives ``None``; such
    strings are plan risk R12.
    """
    kind = node.type
    if kind == "parenthesized_expression" and len(node.named_children) == 1:
        return _constant_string(node.named_children[0], source)
    if kind == "concatenated_string":
        parts = [_constant_string(child, source) for child in node.named_children]
        if not parts or any(part is None for part in parts):
            return None
        return "".join(part for part in parts if part is not None)
    if kind == "binary_operator":
        operator = node.child_by_field_name("operator")
        if operator is None or operator.type != "+":
            return None
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None:
            return None
        first = _constant_string(left, source)
        second = _constant_string(right, source)
        if first is None or second is None:
            return None
        return first + second
    if kind != "string" or any(
        child.type == "interpolation" for child in node.named_children
    ):
        return None
    text = _text(node, source)
    quote = min(
        (index for index in (text.find("'"), text.find('"')) if index >= 0),
        default=-1,
    )
    if quote < 0:
        return None
    prefix = text[:quote].lower()
    if "b" in prefix:
        return None
    try:
        value = ast.literal_eval(prefix.replace("f", "") + text[quote:])
    except (SyntaxError, ValueError):
        return None
    return value if isinstance(value, str) else None


def _alias_parts(node: Any) -> tuple[Any, Any]:
    """A ``type`` statement's name node and type-parameter list (or ``None``)."""
    name_node = node.child_by_field_name("left")
    params = None
    while name_node is not None and name_node.type in ("type", "generic_type"):
        if name_node.type == "generic_type":
            params = next(
                (
                    child
                    for child in name_node.named_children
                    if child.type == "type_parameter"
                ),
                None,
            )
        name_node = name_node.named_children[0] if name_node.named_children else None
    return name_node, params


def _identifiers(node: Any) -> list[Any]:
    """Every identifier in ``node``'s subtree, ``node`` included."""
    found: list[Any] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type == "identifier":
            found.append(current)
        stack.extend(reversed(current.named_children))
    return found


def _pattern_captures(node: Any) -> list[Any]:
    found: list[Any] = []
    stack = [node]
    while stack:
        current = stack.pop()
        kind = current.type
        if kind == "identifier":
            found.append(current)
            continue
        if kind == "dotted_name" and len(current.named_children) > 1:
            continue  # a value pattern: ``Color.RED``
        children = list(current.named_children)
        if kind == "class_pattern" and children and children[0].type == "dotted_name":
            children = children[1:]  # the class name is read
        if kind == "keyword_pattern" and children and children[0].type == "identifier":
            children = children[1:]  # the keyword names an attribute
        stack.extend(reversed(children))
    return found


def _in_first_iterable(node: Any, ident: Any) -> bool:
    """Whether ``ident`` is in a comprehension's first iterable."""
    clause = next(
        (child for child in node.named_children if child.type == "for_in_clause"), None
    )
    if clause is None:
        return False
    left = clause.child_by_field_name("left")
    start = left.end_byte if left is not None else clause.start_byte
    return bool(start <= ident.start_byte and ident.end_byte <= clause.end_byte)


def _callee_head(node: Any) -> Any:
    while node is not None and node.type == "attribute":
        node = node.child_by_field_name("object")
    return node if node is not None and node.type == "identifier" else None


class NonAsciiNameError(ValueError):
    """The file has a non-ASCII identifier, so it is not analyzed (5.3)."""


class AmbiguousIndentationError(ValueError):
    """A line's indentation depends on the width of a tab (5.3)."""


_LINES = re.compile(rb"\r\n|\r|\n")


def ambiguous_indentation(source: bytes) -> int | None:
    """The 1-based number of the first line whose leading whitespace has a
    space before a tab, or a form feed, or ``None``.

    tree-sitter counts a tab as eight more columns, while CPython advances to
    the next multiple of eight, so "seven spaces and a tab" can put a ``def``
    in a different block without a parse error. Lines inside strings count
    too, which can only fail closed.
    """
    for number, line in enumerate(_LINES.split(source), start=1):
        leading = line[: len(line) - len(line.lstrip(b" \t\f"))]
        if b"\f" in leading:
            return number
        first_space = leading.find(b" ")
        if first_space >= 0 and leading.rfind(b"\t") > first_space:
            return number
    return None


def non_ascii_name(root: Any, source: bytes) -> Any:
    """The first non-ASCII identifier, or non-ASCII leaf outside strings and
    comments, or ``None``.

    Python compares identifiers after NFKC normalization while the analysis
    and the chunker's symbol names use the source spelling; an ASCII name is
    its own normal form.
    """
    stack: list[tuple[Any, bool]] = [(root, False)]
    while stack:
        node, in_string = stack.pop()
        if node.type == "comment":
            continue
        is_leaf = node.child_count == 0
        if (node.type == "identifier" or (is_leaf and not in_string)) and not source[
            node.start_byte : node.end_byte
        ].isascii():
            return node
        nested = in_string or node.type in _STRING_NODES
        stack.extend((child, nested) for child in node.children)
    return None


def own_module_names(path: str) -> frozenset[str]:
    """The names a file's own module is imported by: its stem, or its
    package's name for ``__init__.py``."""
    parts = path.replace("\\", "/").rstrip("/").split("/")
    stem = parts[-1].rsplit(".", 1)[0] if parts and parts[-1] else ""
    if stem == "__init__":
        stem = parts[-2] if len(parts) > 1 else ""
    return frozenset({stem}) if stem.isidentifier() else frozenset()


def analyze(
    root: Any,
    source: bytes,
    language: str,
    call_facts: Sequence[Mapping[str, Any]],
    own_names: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Return partial scope facts: the goal and one outcome per call.

    ``own_names`` are the names the file's own module is imported by
    (:func:`own_module_names`); importing one is a self-import.
    """
    del language  # always python
    bad = non_ascii_name(root, source)
    if bad is not None:
        msg = f"non-ASCII name in a {bad.type} at byte {bad.start_byte}"
        raise NonAsciiNameError(msg)
    line = ambiguous_indentation(source)
    if line is not None:
        msg = f"indentation depends on the tab width on line {line}"
        raise AmbiguousIndentationError(msg)
    analysis = _Analysis(root, source, own_names)
    bindings: dict[str, Any] = {}
    for fact in call_facts:
        start = int(fact["callee_byte_start"])
        end = int(fact["callee_byte_end"])
        node = root.named_descendant_for_byte_range(start, end)
        if node is None or (node.start_byte, node.end_byte) != (start, end):
            # No node matches the callee span: leave the entry out, which the
            # engine reports as no-binding-fact (5.4).
            continue
        head = _callee_head(node)
        bindings[f"{start}:{end}"] = (
            analysis.lookup(head) if head is not None else _none("unbound")
        )
    return {"goal": "module", "bindings": bindings}
