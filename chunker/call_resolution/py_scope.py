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

**Annotations prove nothing** (#695 re-check at 14e8f044, Q-2). A name looked
up inside any annotation (a parameter's, a return annotation, or a variable
annotation at module, class or function level) gives ``dynamic-scope``. On
3.14 annotations are evaluated lazily (PEP 649/749), and ``annotationlib``
runs an annotation scope again under substitute globals for the
``FORWARDREF`` and ``STRING`` formats, which ``dataclasses``,
``typing.get_type_hints``, ``inspect.signature`` and
``functools.singledispatch`` use: a call there may reach a stand-in
(``annotationlib._Stringifier``), not the binding the lookup would prove.
The value of a ``type`` statement is evaluated lazily as well (PEP 695), and
in a class body it reads the live class namespace through ``__classdict__``,
so a later write to the class whose attribute name is not a literal at the
write site rebinds it: it proves nothing either (#695 re-check at a6734480).

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
So does every other route that rebinds a binding a lookup depends on without
spelling an assignment to that name (:data:`_FILE_WIDE_NAMES`; Codex
4655078224): a closure cell (``__closure__``, ``cell_contents``,
``types.CellType``), a function rebuilt over existing code
(``FunctionType``/``LambdaType``), code-object surgery (``__code__``,
``CodeType``, ``gi_code``/``cr_code``/``ag_code``/``f_code``, the ``co_*``
fields ``code.replace`` rewrites, and the code objects ``dis`` and
``sys.monitoring`` hand over: ``dis``, ``codeobj``, ``_get_code_object``,
``monitoring``, and the profiler's ``getstats``), a frame's live locals
through ``inspect`` (``getgeneratorlocals``, ``getcoroutinelocals``,
``getasyncgenlocals``, ``getargvalues``; PEP 667), raw C-level access
(``ctypes``, ``pythonapi``, ``PyFrame_LocalsToFast``), and a ``closure=``
keyword argument
(``exec(code, g, closure=cells)``). The function type itself is reachable
without naming it (``type(f)``), so a rebuilt function is caught through the
code object it needs (#695 re-check at 606c689f).

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
other than in an import, any name a ``from __main__`` import binds (``from
__main__ import __dict__ as g`` hands over the namespace), and any import of
``sys`` or ``__main__`` in a class body (a class attribute, read as ``K.m``,
``self.m`` or ``getattr(K, "m")``), and a constant string with a ``__main__``
component (``mock.patch("__main__.helper")``, ``pydoc.locate("__main__")``),
except on a positive allow-list: exactly ``__name__ == "__main__"`` or
``!=``, either order, optionally parenthesized, as the whole test of an
``if`` or ``elif`` at module top level, in a file that never rebinds
``__name__`` (#695 M-2). There ``__name__`` is a module-global ``str``, so no
user ``__eq__`` runs and no class namespace or ``__prepare__`` is involved;
every other comparison, ``in``, chain, ``match`` form, or guard in a function,
method or class fails closed; ``__mp_main__``, the name a multiprocessing
spawn child imports the script under, counts as ``__main__``, and constant
strings split on ``.`` and ``:`` (``pkgutil.resolve_name("pkg.mod:attr")``)
for this rule, the own-name rule and the dynamic attribute names;
``X.modules[__name__]`` or
``X.modules.get(__name__)`` (also ``__getitem__``, ``setdefault``, ``pop``)
through any receiver ``X``; an import of the file's own module (``import a``
or ``from . import a`` in ``a.py``); a function's ``__globals__``, a frame's
``f_globals``/``f_builtins`` and ``inspect.getmodule``; the builtins
namespace reached as an attribute, ``f.__builtins__``, ``os.__builtins__`` or
``len.__self__`` (the ``builtins`` module; #695 re-check at 606c689f), and
the ``builtins`` module as an attribute (``inspect.builtins``,
``enum.bltns``) or a constant string (``mock.patch("builtins.helper")``,
``pydoc.locate("builtins")``; #695 re-check at 8fd7c1a2); a constant
string
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

**Indentation tree-sitter may read differently is not analyzed.** tree-sitter
counts a tab as eight more columns, while CPython advances to the next
multiple of eight, so a line whose leading whitespace has a space before a
tab can land in a different block without a parse error. And when a line's
first non-blank character is a backslash continuation, CPython takes the
logical line's indentation from that line while tree-sitter takes it from
the next. Such a file, or one with a form feed in a line's leading
whitespace, raises :class:`AmbiguousIndentationError` and is
``supported: false``.

**Private names.** Inside a class (its body and every function, lambda and
comprehension in it), CPython rewrites ``__x`` (not ending in ``__``) to
``_<Class>__x``. A lookup of such a name there gives ``none(unmapped)``, and
every binding, ``global`` or ``nonlocal`` of one there also binds each
mangled spelling an enclosing class may give it (a non-definition binding),
so ``_C__x`` spelled out elsewhere never proves past a mangled write. The
same holds wherever the analysis records a name from an identifier in class
code (Codex 4654363963): an attribute write (``mod.__helper = f`` in class
``K`` writes ``_K__helper``; also ``del`` and augmented assignment), the
own-name and dynamic-name scans, submodule imports, and the ``sys`` and
``__main__`` alias sets with the uses tested against them (#695 I-3:
``import __main__ as __m`` in class ``K`` binds ``_K__m``) all take every
runtime spelling. CPython 3.14 mangles attribute names, imported module names and
``as`` aliases, but not keyword-argument names, class-pattern keywords or
strings; the scans take the mangled spelling everywhere anyway, which can
only fail closed, and string keys keep their literal spelling.

**The file's own module: one general fail-closed rule** (the president's
re-checks of #695, replacing per-shape fixes). The names the import system
derives from the path can denote this file's module: every suffix of its
dotted module path relative to the run root and to every ancestor directory,
because the root and any ancestor may be packages, regular or PEP 420
namespace packages. Each of those, and any longer path ending in one, ends
with the file's own name: its raw stem, or the package directory's raw name
for ``__init__.py`` (:class:`ModulePath`; no identifier filter, since
``my-mod`` is importable by ``importlib``). A loader may choose any other name
(``spec_from_file_location``, ``runpy``); writes through such a module in
the spellings the attribute-write rule below lists fail closed, and every
other spelling is plan risk R12. A file whose own name cannot be computed
(no path: ``None`` or ``""``) fails closed. Names, dotted paths and relative
levels are read from identifier and ``.`` tokens, never raw node text:
whitespace, comments and backslash continuations may sit between them
(``from . helper import M``, ``from . . import R``). So:

- **Self-reference.** Module-scope lookups give ``dynamic-scope`` when the own
  name is a component of any import's path or imported names (absolute or
  relative, after any dots, in any scope), of any identifier that is not a
  parameter or ``def``/``class`` name (an attribute, a keyword argument, a
  class pattern's keyword ``case object(a=m)``, a dotted name: whatever node
  spells it), or of any constant string, alone or dotted. A root-level
  ``__init__.py``, which includes any ``__init__.py`` run as a single file,
  has no own name in the run: every absolute import, and every relative
  import whose dots leave the run (``from .. import R``), may name it; only a
  single-dot relative import cannot. This over-triggers by design. Losing a
  proof is fine; a wrong edge is not.
- **Attribute writes through any receiver.** The receiver may be this module,
  handed over by a sibling's re-export, a function's return value, a
  parameter or a loader. So writing attribute ``name`` of anything (``x.name
  = v``, ``del x.name``, ``x["name"] = v`` with a constant key,
  ``setattr``/``delattr``/``__setattr__``/``__setitem__`` with a constant
  string, ``x.__dict__.update(name=v)``/``.update({"name": v})``/
  ``.setdefault``/``.pop``) gives ``name`` a non-definition binding at module
  scope, so a definition of ``name`` there never proves. Only those listed
  spellings are caught: ``operator.setitem(mod.__dict__, "helper", len)``,
  ``d = mod.__dict__; d |= {...}`` and ``update()`` with a non-literal mapping
  are plan risk R12.
- **Submodule rebinding.** In any ``__init__.py``, every import is resolved to
  a full dotted path (relative dots joined to this file's module path). Where
  the own name is followed by a component ``X`` (``import pkg.sub.X``,
  ``from ..sub.X import y``, ``from . import X``), loading the submodule sets
  this package's global ``X``: a non-definition binding at module scope,
  also from a function.

Dynamic attribute names (``__globals__``, ``f_globals``, ``f_locals``,
``f_builtins``, ``getmodule``, ``__builtins__``, ``__self__``, ``builtins``,
``bltns``) also count whatever node spells them, and
``X[__name__]`` or ``X.get(__name__)`` (also ``__getitem__``, ``setdefault``,
``pop``) on any receiver is dynamic. What is left to reach the module without
spelling its name or writing through it by name is other dynamic triggers
(``__import__``, ``importlib``, ``sys.modules``, ``globals()``, frames) or
plan risks R10/R12 (another module, iteration over a package's namespace,
``gc``, by-name submodule loading with a computed name).

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
# object (``inspect.getmodule``), including the builtins namespace a lookup
# falls back to before a module-level definition has run: ``f.__builtins__``,
# ``os.__builtins__``, and ``len.__self__``, which is the ``builtins`` module
# (#695 re-check at 606c689f, O-3b); and the ``builtins`` module as another
# module's attribute or in a constant string (``inspect.builtins``,
# ``site.builtins``, ``mock.patch("builtins.helper", ...)``,
# ``pydoc.locate("builtins")``), including ``enum.bltns``, the one other
# name the stdlib binds it to (#695 re-check at 8fd7c1a2, P-2).
_DYNAMIC_ATTRIBUTES = frozenset(
    {
        "__globals__",
        "f_globals",
        "f_locals",
        "f_builtins",
        "getmodule",
        "__builtins__",
        "__self__",
        "builtins",
        "bltns",
    }
)
_SYS = "sys"
_SYS_MODULES = "modules"
# ``import __main__`` reaches the namespace of the module run as a script,
# which may be this one: any use other than importing it is dynamic.
_MAIN = "__main__"
# The names the module run as a script answers to: ``__main__``, and
# ``__mp_main__`` in a multiprocessing spawn child, which imports the main
# script under that name.
_MAIN_NAMES = frozenset({_MAIN, "__mp_main__"})
# Separators of a module path in a string resolvers accept: ``.`` and the
# ``:`` of ``pkgutil.resolve_name("pkg.mod:attr")``. No resolver maps ``/``
# to this module's namespace (``runpy.run_path`` and
# ``spec_from_file_location`` build a new module object).
_NAME_SEPARATORS = re.compile(r"[.:]")
# ``frame.f_locals`` writes through to a function's locals (PEP 667, Python
# 3.13+): every lookup of a file that mentions it fails closed.
_FRAME_LOCALS = "f_locals"
# Names whose mention may rebind a binding a lookup depends on in any scope,
# function scopes included, without spelling an assignment to that name: a
# closure cell (``f.__closure__[0].cell_contents = g``; Codex 4655078224), a
# function rebuilt over existing code with a new closure or globals
# (``types.FunctionType``/``LambdaType``, ``types.CellType``), code-object
# surgery (``f.__code__ = f.__code__.replace(co_names=...)``, ``CodeType``,
# the code of a generator, coroutine or frame) and raw C-level access
# (``ctypes``). Like ``f_locals``, any mention makes every lookup of the file
# dynamic, and so does a ``closure=`` keyword argument (``exec(code, g,
# closure=cells)``, ``FunctionType(..., closure=...)``).
#
# The function type is reachable without naming it (``type(f)``,
# ``f.__class__``, ``type(lambda: 0)``), so a rebuilt function is caught on
# the code-object side: rebinding a proven name for existing code takes that
# code object, and every way to reach it by a spelled name is listed here,
# including ``dis`` (``Bytecode(f).codeobj``, ``get_instructions`` constants,
# ``_get_code_object``) and ``sys.monitoring`` callbacks (#695 re-check at
# 606c689f, O-3a), and the profiler's ``getstats()`` entries (#695 re-check
# at 8fd7c1a2, P-3a). ``inspect.getgeneratorlocals``, ``getcoroutinelocals``,
# ``getasyncgenlocals`` and ``getargvalues(frame).locals`` return a frame's
# live, write-through ``f_locals`` proxy (PEP 667), so they count like
# ``f_locals`` (P-3b). Also (#695 re-check at 14e8f044, Q-3): the code
# object of a ``traceback.FrameSummary`` (``_code``) and the code objects
# ``bdb.Bdb`` caches (``code_linenos``); ``pdb.Pdb().curframe_locals``, the
# live ``f_locals`` proxy; and ``annotationlib.call_annotate_function``,
# ``call_evaluate_function`` and ``__annotate__``, which rebuild a user
# function from its ``__code__`` under substitute globals, and
# ``__annotate_func__``, the class-dict key behind ``type.__annotate__``
# (#695 re-check at a6734480, S-3). Objects reached by introspection rather than by a spelled
# name stay in plan risk R12: heap walking (``gc`` referents, for example a
# found globals dict written with ``update(D)``, or found code or cells run
# under ``type(f)(...)``) and computed member names (``inspect.getmembers``,
# ``dir`` plus ``getattr``).
_FILE_WIDE_NAMES = frozenset(
    {
        _FRAME_LOCALS,
        "__closure__",
        "cell_contents",
        "CellType",
        "FunctionType",
        "LambdaType",
        "CodeType",
        "__code__",
        "gi_code",
        "cr_code",
        "ag_code",
        "f_code",
        "co_code",
        "co_names",
        "co_consts",
        "co_varnames",
        "co_freevars",
        "co_cellvars",
        "ctypes",
        "pythonapi",
        "PyFrame_LocalsToFast",
        "dis",
        "codeobj",
        "_get_code_object",
        "monitoring",
        "getstats",
        "getgeneratorlocals",
        "getcoroutinelocals",
        "getasyncgenlocals",
        "getargvalues",
        "_code",
        "code_linenos",
        "curframe_locals",
        "call_annotate_function",
        "call_evaluate_function",
        "__annotate__",
        "__annotate_func__",
    }
)
# A keyword argument that hands a function or code object a new closure.
_CLOSURE_KEYWORD = "closure"
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
# Builtins only some platforms have (``WindowsError`` on Windows).
PLATFORM_BUILTINS = frozenset(["WindowsError"])
BUILTINS = BUILTINS_314 | PY2_BUILTINS | PLATFORM_BUILTINS
# The package an import in a root-level ``__init__.py`` names with ``.``: its
# own name is outside the run, so it stands for "this package".
_SELF = "<this package>"
# Calls that write an attribute or namespace key named by a string argument,
# a keyword argument or a constant dict key (``X.__dict__.update(helper=f)``).
_ATTRIBUTE_WRITERS = frozenset(
    {
        "setattr",
        "delattr",
        "__setattr__",
        "__delattr__",
        "__setitem__",
        "__delitem__",
        "update",
        "setdefault",
        "pop",
        "__ior__",
    }
)
# Writers whose mention anywhere but as the callee of a direct call hands
# them on (``w = setattr``, ``partial(setattr, mod)``, ``(w := setattr)``):
# the write they make is no longer visible, so module-scope lookups fail
# closed (#695 fold 18).
_WRITER_NAMES = frozenset({"setattr", "delattr", "__setattr__", "__delattr__"})
# Mutators of a namespace dict (``mod.__dict__``, ``vars(mod)``,
# ``getattr(mod, "__dict__")``): taken off the receiver without a call
# (``u = mod.__dict__.update``) they fail closed; the writing ones, called
# with anything but literal names, fail closed too.
_NAMESPACE_MUTATORS = frozenset(
    {
        "update",
        "setdefault",
        "pop",
        "popitem",
        "clear",
        "__setitem__",
        "__delitem__",
        "__ior__",
    }
)
_NAMESPACE_WRITES = frozenset({"update", "setdefault", "__setitem__", "__ior__"})
# ``operator`` functions that write a mapping given as their first argument.
_OPERATOR_WRITERS = frozenset(
    {
        "setitem",
        "delitem",
        "__setitem__",
        "__delitem__",
        "ior",
        "iadd",
        "__ior__",
        "__iadd__",
    }
)
_NAMESPACE_DICT = "__dict__"
# pytest-mock's fixtures, whose ``.patch`` is ``unittest.mock.patch`` (#695
# fold 20).
_MOCKER_NAMES = frozenset(
    {"mocker", "module_mocker", "class_mocker", "package_mocker", "session_mocker"}
)
_PATCH_METHODS = ("object", "dict", "multiple")
# Stdlib string-to-module resolvers (#695 fold 21, E-20): a mention in any
# position fails closed, like ``importlib``. These names are rare enough to
# count in every spelling; ``locate`` counts on ``pydoc`` and ``_resolve``/
# ``_importer`` on ``logging.config`` only.
_RESOLVER_NAMES = frozenset({"resolve_name", "safeimport", "find_class"})
_PYDOC_RESOLVERS = frozenset({"locate", "safeimport"})
_LOGGING_RESOLVERS = frozenset({"_resolve", "_importer"})
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
        self,
        root: Any,
        source: bytes,
        own_names: frozenset[str] = frozenset(),
        module_path: ModulePath | None = None,
    ) -> None:
        self.root = root
        self.source = source
        path = module_path or ModulePath(own_names=own_names)
        # The file's own module name (its stem, or its package for
        # ``__init__.py``): importing it is a self-import.
        self.own_names = path.own_names
        self.module_path = path
        self.scopes: dict[tuple[int, str], _Scope] = {}
        self.events: list[tuple[_Scope, str, _Binding]] = []
        self.dynamic = False
        self.frame_locals = False
        self.star = False
        # Names written as an attribute or constant key of any receiver.
        self.attribute_writes: set[str] = set()
        # Subscript targets (``x[k] = v``, ``del x[k]``), checked once the
        # namespace aliases are known (#695 fold 18).
        self.subscript_targets: list[Any] = []
        # A ``__dict__`` attribute or constant string appears in the file, and
        # an ``operator`` writer is handed on (fold 18 rule 3).
        self.namespace_seen = False
        self.operator_escape = False
        # Names assigned a namespace receiver (``d = mod.__dict__``).
        self.namespace_aliases: set[str] = set()
        # Fold 21: a constant ``"patch"`` string, and the mock-module and
        # pytest-mock names found by alias propagation (B-5).
        self.patch_string_seen = False
        self.mock_aliases: set[str] = set()
        self.mocker_names: set[str] = set(_MOCKER_NAMES)
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
        for name in sorted(self.attribute_writes):
            # Any receiver may be this module: a non-definition binding of
            # the written name at module scope (#695 re-check R-5 family).
            self._module_write(name)
        if self.module_path.unknown:
            # Without a path the own name is unknown: fail closed.
            self.dynamic = True
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
        for mangled in _mangled_names(name_node, name, self.source):
            # CPython binds ``_C__x`` for ``__x`` inside class ``C`` (B-1): the
            # mangled spelling gets a non-definition binding too.
            scope.assigned.add(mangled)
            self.events.append((scope, mangled, _Binding(LOCAL)))

    def _attribute_write(self, node: Any) -> None:
        if node.type == "attribute":
            attribute = node.child_by_field_name("attribute")
            if attribute is not None:
                # Inside a class, CPython mangles the attribute name too:
                # ``mod.__helper = f`` in class ``K`` writes ``_K__helper``
                # (Codex 4654363963). Record every runtime spelling.
                self.attribute_writes.update(_spellings(attribute, self.source))
            return
        self.subscript_targets.append(node)
        for index, child in enumerate(node.children):
            if node.field_name_for_child(index) == "subscript":
                value = _constant_string(child, self.source)
                if value is not None:
                    self.attribute_writes.add(value)

    def _module_write(self, name: str) -> None:
        """A non-definition binding of ``name`` at module scope."""
        self.module.assigned.add(name)
        self.events.append((self.module, name, _Binding(LOCAL)))

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
            # But the receiver may be this module, handed over by any means
            # (a sibling's re-export, a function's return value, a loader's
            # name): the written attribute, or a constant key, is a possible
            # write of this module's global of that name.
            self._attribute_write(node)
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

    def _import_paths(self, node: Any, *, resolve: bool) -> list[list[str]]:
        """The dotted paths an import statement names, one per imported name.

        ``import a.b`` gives ``[a, b]``; ``from m.x import y`` gives
        ``[m, x, y]``. With ``resolve``, a relative module is joined to the
        package its dots name, from this file's module path (``[_SELF]`` for
        a root-level ``__init__.py``; nothing when the dots leave the run);
        without it, only the components after the dots count.
        """
        source = self.source
        names: list[list[str]] = []
        star = False
        for index, child in enumerate(node.children):
            if child.type == "wildcard_import":
                star = True
            if node.field_name_for_child(index) != "name":
                continue
            imported = (
                child.child_by_field_name("name")
                if child.type == "aliased_import"
                else child
            )
            if imported is not None:
                names.append(_dotted_parts(imported, source))
        if node.type == "import_statement":
            return names
        dots, rest = _module_parts(node, source)
        base: list[str] = []
        if dots and resolve:
            info = self.module_path
            package = list(info.components)
            if not info.package_init:
                package = package[:-1]
            if info.root_init:
                package = [_SELF]
            up = dots - 1
            if up < len(package) or (up == len(package) and not info.root_init):
                base = package[: len(package) - up]
        prefix = base + rest
        paths = [prefix + name for name in names]
        if star or not paths:
            paths.append(prefix)
        return paths

    def _submodule_writes(self, node: Any) -> None:
        """In any ``__init__.py``, an import whose resolved path passes
        through this package and names a next component ``X`` (``import
        pkg.sub.X``, ``from ..sub.X import y``, ``from . import X``) sets the
        package's global ``X`` when the submodule loads (B-3, N-1): a
        non-definition binding at module scope, also from a function."""
        if not self.module_path.package_init:
            return
        own = self.own_names | {_SELF}
        for path in self._import_paths(node, resolve=True):
            for index in range(1, len(path)):
                if path[index - 1] in own:
                    self._module_write(path[index])
                    # In class code an import name may also be mangled.
                    for mangled in _mangled_names(node, path[index], self.source):
                        self._module_write(mangled)

    def _import(self, node: Any, scope: _Scope, depth: int) -> None:
        self._submodule_writes(node)
        for name, child in self._fields(node):
            if name != "name":
                self.visit(child, scope, depth + 1)
                continue
            if child.type == "aliased_import":
                module = child.child_by_field_name("name")
                bound = child.child_by_field_name("alias")
            else:
                module = child
                # ``import a.b`` binds ``a``: the first identifier token.
                bound = next(iter(_identifier_children(child)), None)
            text = ".".join(_dotted_parts(module, self.source)) if module else ""
            self._import_binding(scope, node, bound, {"form": "import", "module": text})

    def _import_from(self, node: Any, scope: _Scope, depth: int) -> None:
        self._submodule_writes(node)
        dots, parts = _module_parts(node, self.source)
        module = "." * dots + ".".join(parts)
        for name, child in self._fields(node):
            if name != "name":
                self.visit(child, scope, depth + 1)
                continue
            if child.type == "aliased_import":
                imported = child.child_by_field_name("name")
                bound = child.child_by_field_name("alias")
            else:
                imported = child
                tokens = _identifier_children(child)
                bound = tokens[0] if len(tokens) == 1 else None
            text = ".".join(_dotted_parts(imported, self.source)) if imported else ""
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
                tokens = _identifier_children(child)
                bound = tokens[0] if len(tokens) == 1 else None
            text = ".".join(_dotted_parts(imported, self.source)) if imported else ""
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
        scope.globals.update(self._declared(node))

    def _nonlocal(self, node: Any, scope: _Scope, depth: int) -> None:
        del depth
        scope.nonlocals.update(self._declared(node))

    def _declared(self, node: Any) -> set[str]:
        """The names a ``global``/``nonlocal`` declares, with every mangled
        spelling a class around it may give them (B-1)."""
        names: set[str] = set()
        for ident in _identifiers(node):
            name = _text(ident, self.source)
            names.add(name)
            names.update(_mangled_names(ident, name, self.source))
        return names

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
        main_names = set(_MAIN_NAMES)
        main_strings: list[Any] = []
        identifiers: list[Any] = []
        # Fold 18: calls, attributes, ``|=`` statements and namespace aliases,
        # classified once every alias is known.
        calls: list[Any] = []
        attributes: list[Any] = []
        augmented: list[Any] = []
        bindings: list[tuple[Any, Any]] = []
        matches: list[Any] = []
        operator_names = set(_OPERATOR_WRITERS)
        # Fold 19 (W-3): names bound to ``unittest.mock``/``mock`` and to
        # ``patch``.
        mock_names: set[str] = set()
        patch_names: set[str] = set()
        # Fold 21 (E-20): names bound to ``pydoc`` and ``logging.config``.
        pydoc_names: set[str] = set()
        logging_config_names: set[str] = set()
        stack = [self.root]
        while stack:
            node = stack.pop()
            kind = node.type
            if kind == "attribute":
                attributes.append(node)
                attribute = node.child_by_field_name("attribute")
                if attribute is not None and _NAMESPACE_DICT in _spellings(
                    attribute, source
                ):
                    self.namespace_seen = True
            elif kind == "match_statement":
                matches.append(node)
            elif kind == "augmented_assignment":
                augmented.append(node)
            elif kind in ("assignment", "named_expression"):
                target = node.child_by_field_name(
                    "left" if kind == "assignment" else "name"
                )
                value = node.child_by_field_name(
                    "right" if kind == "assignment" else "value"
                )
                while value is not None and value.type == "assignment":
                    value = value.child_by_field_name("right")
                if target is not None and value is not None:
                    bindings.append((_unwrap(target, skip_comments=True), value))
            if kind == "identifier":
                identifiers.append(node)
            elif kind == "aliased_import":
                imported = node.child_by_field_name("name")
                alias = node.child_by_field_name("alias")
                parts = _dotted_parts(imported, source) if imported is not None else []
                last = parts[-1] if parts else ""
                # In class code an alias binds its mangled spelling too
                # (``import __main__ as __m`` binds ``_K__m``; #695 I-3).
                if alias is not None and last == _SYS:
                    sys_names.update(_spellings(alias, source))
                if alias is not None and last in _MAIN_NAMES:
                    main_names.update(_spellings(alias, source))
            elif kind in ("string", "concatenated_string", "binary_operator"):
                value = _constant_string(node, source)
                if value is not None:
                    self._literal_use(value)
                    if set(_NAME_SEPARATORS.split(value)) & _MAIN_NAMES:
                        # ``"__main__"`` names this module by string when the
                        # file runs as a script (``mock.patch("__main__.f")``,
                        # ``pydoc.locate("__main__")``,
                        # ``pkgutil.resolve_name("__main__:__dict__")``; #695
                        # K-3). Decided after the scan, once every attribute
                        # write is known (see :meth:`_main_guard`).
                        main_strings.append(node)
                    if self._names_own_module(value):
                        # Any constant string naming this module, alone or as
                        # a component of a dotted path (``getattr(pkg, "a")``,
                        # ``pkg.__dict__["a"]``, ``NAME = "a"``; N-3).
                        self.dynamic = True
            elif kind in ("subscript", "call"):
                if kind == "subscript" and any(
                    _constant_string(child, source) == _NAMESPACE_DICT
                    for index, child in enumerate(node.children)
                    if node.field_name_for_child(index) == "subscript"
                ):
                    # ``type.__dict__["__dict__"].__get__(m)`` (fold 21, V-7).
                    self.dynamic = True
                self._module_by_name(node)
                if kind == "call":
                    self._setattr_call(node)
                    calls.append(node)
            if kind in ("import_statement", "import_from_statement"):
                self._import_use(node)
                self._class_body_module_import(node)
                dots, module_parts = (
                    _module_parts(node, source)
                    if kind == "import_from_statement"
                    else (0, [])
                )
                if not dots and module_parts == ["operator"]:
                    # ``from operator import setitem as s`` (fold 18 rule 3).
                    for last, bound in _from_import_names(node, source):
                        if last in _OPERATOR_WRITERS:
                            operator_names.update(_spellings(bound, source))
                if not dots and module_parts == ["pydoc"]:
                    for last, _bound in _from_import_names(node, source):
                        if last in _PYDOC_RESOLVERS:
                            self.dynamic = True  # ``from pydoc import locate``
                if not dots and module_parts == ["logging"]:
                    for last, bound in _from_import_names(node, source):
                        if last == "config":
                            logging_config_names.update(_spellings(bound, source))
                if not dots and module_parts == ["logging", "config"]:
                    for last, _bound in _from_import_names(node, source):
                        if last in _LOGGING_RESOLVERS:
                            self.dynamic = True
                if not dots and module_parts == ["unittest"]:
                    # ``from unittest import mock as m`` (fold 19 W-3).
                    for last, bound in _from_import_names(node, source):
                        if last == "mock":
                            mock_names.update(_spellings(bound, source))
                if not dots and module_parts in (["unittest", "mock"], ["mock"]):
                    # ``from unittest.mock import patch as p``.
                    for last, bound in _from_import_names(node, source):
                        if last == "patch":
                            patch_names.update(_spellings(bound, source))
                if kind == "import_statement":
                    for child in node.named_children:
                        name_node = (
                            child.child_by_field_name("name")
                            if child.type == "aliased_import"
                            else child
                        )
                        parts = (
                            _dotted_parts(name_node, source)
                            if name_node is not None
                            else []
                        )
                        alias = (
                            child.child_by_field_name("alias")
                            if child.type == "aliased_import"
                            else None
                        )
                        if parts in (["mock"], ["unittest", "mock"]) and alias:
                            mock_names.update(_spellings(alias, source))
                        elif parts == ["mock"]:
                            mock_names.add("mock")
                        if parts == ["pydoc"]:
                            pydoc_names.update(
                                _spellings(alias, source) if alias else {"pydoc"}
                            )
                        if parts == ["logging", "config"] and alias:
                            logging_config_names.update(_spellings(alias, source))
                if (
                    not dots
                    and len(module_parts) == 1
                    and module_parts[0] in (_MAIN_NAMES)
                ):
                    # ``from __main__ import __dict__ as g`` hands over a
                    # piece of ``__main__``'s namespace: every name it binds
                    # is an alias, so any later use is dynamic (#695 J-3b).
                    # An unused one still resolves.
                    for bound in _from_import_bound_names(node):
                        main_names.update(_spellings(bound, source))
            stack.extend(node.named_children)
        for node in main_strings:
            if not self._main_guard(node):
                self.dynamic = True
        self._namespace_rules(
            calls, attributes, augmented, bindings, matches, identifiers, operator_names
        )
        self._resolver_rules(attributes, identifiers, pydoc_names, logging_config_names)
        self._mock_rules(
            calls, attributes, identifiers, bindings, mock_names, patch_names
        )
        for ident in identifiers:
            name = _text(ident, source)
            parent = ident.parent
            if parent is None:
                continue
            # Attribute-like names count wherever an identifier spells them
            # (#695 re-check N-4): an attribute, a keyword argument, a class
            # pattern's keyword (``case object(__globals__=g)``), an import or
            # dotted name, a definition's name. Over-triggering only fails
            # closed. Inside a class every runtime spelling counts: the
            # source one and each mangled ``_Class__x`` one (Codex
            # 4654363963), whether or not CPython mangles that position.
            spellings = _spellings(ident, source)
            if spellings & (_WRITER_NAMES | operator_names | _OPERATOR_WRITERS):
                self._writer_mention(ident, spellings, operator_names)
            if spellings & _DYNAMIC_ATTRIBUTES:
                self.dynamic = True
            if spellings & _FILE_WIDE_NAMES:
                self.dynamic = True
                self.frame_locals = True
            if not _scope_binding_name(ident) and any(
                self._names_own_module(spelling) for spelling in spellings
            ):
                # ``pkg.a.helper = …``, ``case object(a=m)``: a path through a
                # parent package, which may be the run root itself.
                self.dynamic = True
            if parent.type == "attribute" and _same(
                ident, parent.child_by_field_name("attribute")
            ):
                if name == _SYS:
                    self._sys_use(parent)
                continue
            if parent.type == "keyword_argument" and _same(
                ident, parent.child_by_field_name("name")
            ):
                if name == _CLOSURE_KEYWORD:
                    # ``exec(code, g, closure=cells)`` runs existing code
                    # against new cells: every lookup is dynamic.
                    self.dynamic = True
                    self.frame_locals = True
                continue
            if parent.type in ("function_definition", "class_definition") and _same(
                ident, parent.child_by_field_name("name")
            ):
                continue
            if name in _DYNAMIC_NAMES:
                self.dynamic = True
            elif spellings & sys_names:
                # Both sides use every runtime spelling: ``__m`` in class
                # ``K`` reads ``_K__m``, and ``_K__m`` outside reads it too.
                self._sys_use(ident)
            elif spellings & main_names and not _import_context(ident):
                # ``__main__.helper = len``, ``setattr(m, ...)``.
                self.dynamic = True
        if self.operator_escape and self.namespace_seen:
            # An ``operator`` writer handed on in a file that names a
            # namespace dict (fold 18 rule 3).
            self.dynamic = True

    def _main_guard(self, node: Any) -> bool:
        """Whether a ``__main__`` constant is exempt: a positive allow-list
        (#695 L-2/M-2, executive decision).

        Only the script guard at module top level: the constant is exactly
        ``"__main__"`` (a plain string, optionally in parentheses) and one
        operand of a single ``==`` or ``!=`` comparison whose other operand is
        the bare ``__name__``; that comparison (optionally in parentheses) is
        the whole test of an ``if`` statement directly in the module, or of
        an ``elif`` of one; and the file never rebinds ``__name__``. There,
        ``__name__`` is read from the module globals, so the comparison is
        between a module-global ``str`` and a literal: no user ``__eq__`` runs
        and no class namespace or ``__prepare__`` is involved. Everything
        else with a ``__main__`` component fails closed: guards in functions,
        methods or classes, ``in``, chains, ``and``/``or``/``not``, and every
        ``match`` form.
        """
        if self._name_rebound() or node.type != "string":
            return False
        if _constant_string(node, self.source) != _MAIN:
            return False
        operand = node
        while (
            operand.parent is not None
            and operand.parent.type == "parenthesized_expression"
        ):
            operand = operand.parent
        comparison = operand.parent
        if comparison is None:
            return False
        # A single ``==``/``!=`` token between exactly two operands only occurs
        # in a ``comparison_operator``.
        operands = [
            child for child in comparison.named_children if child.type != "comment"
        ]
        operators = [child.type for child in comparison.children if not child.is_named]
        if len(operands) != 2 or operators not in (["=="], ["!="]):
            return False
        other = _unwrap(operands[1] if _same(operands[0], operand) else operands[0])
        if not any(_same(item, operand) for item in operands) or not (
            other.type == "identifier" and _text(other, self.source) == "__name__"
        ):
            return False
        test = comparison
        while (
            test.parent is not None and test.parent.type == "parenthesized_expression"
        ):
            test = test.parent
        # A comparison sits directly under an ``if`` or ``elif`` only as its
        # whole condition.
        statement = test.parent
        if statement is None:
            return False
        if statement.type == "elif_clause":
            statement = statement.parent
        return (
            statement is not None
            and statement.type == "if_statement"
            and statement.parent is not None
            and statement.parent.type == "module"
        )

    def _name_rebound(self) -> bool:
        """Whether any scope binds, declares or deletes ``__name__``, or any
        receiver's attribute ``__name__`` is written."""
        return "__name__" in self.attribute_writes or any(
            "__name__" in scope.assigned
            or "__name__" in scope.globals
            or "__name__" in scope.nonlocals
            for scope in self.scopes.values()
        )

    def _names_own_module(self, text: str) -> bool:
        """Whether a name, or a dotted constant string, may denote this
        file's module: one of its components, or the whole text, is an own
        name."""
        if not self.own_names:
            return False
        return bool(set(_NAME_SEPARATORS.split(text)) & self.own_names) or any(
            "." in own and own in text for own in self.own_names
        )

    def _class_body_module_import(self, node: Any) -> None:
        """An import in a class body that names ``sys`` or ``__main__`` stores
        it as a class attribute (``K.m``, ``self.m``, ``getattr(K, "m")``),
        which no identifier rule sees: dynamic (#695 J-3a)."""
        if not _in_class_body(node):
            return
        # The paths include a from-import's module components.
        for path in self._import_paths(node, resolve=False):
            if ({_SYS} | _MAIN_NAMES) & set(path):
                self.dynamic = True

    def _literal_use(self, value: str) -> None:
        """A constant string naming a dynamic attribute counts as a mention
        of it (the analogue of PR 3's literal-key rule)."""
        parts = set(_NAME_SEPARATORS.split(value))
        if parts & _LITERAL_DYNAMIC:
            self.dynamic = True
        if parts & _WRITER_NAMES:
            # ``getattr(mod, "__setattr__")``: a writer reached by name (fold
            # 18 rule 1).
            self.dynamic = True
        if _NAMESPACE_DICT in parts:
            self.namespace_seen = True
        if parts & _OPERATOR_WRITERS:
            self.operator_escape = True
        if parts & _RESOLVER_NAMES:
            # ``getattr(pkgutil, "resolve_name")`` (fold 21, E-20).
            self.dynamic = True
        if "patch" in parts:
            self.patch_string_seen = True
        if parts & _FILE_WIDE_NAMES:
            self.dynamic = True
            self.frame_locals = True

    def _import_use(self, node: Any) -> None:
        """``from sys import modules`` and every import that may name this
        file's module are dynamic.

        An import may name it when its own name is a component of the
        import's path or of an imported name (raw, after any leading dots):
        ``import a``, ``import pkg.a.x``, ``from . import a``, ``from ..sub
        import x`` in ``pkg/sub/__init__.py``. A root-level ``__init__.py``
        has no own name in the run, so any absolute import may name it.
        """
        source = self.source
        dots, module_parts = (
            _module_parts(node, source)
            if node.type == "import_from_statement"
            else (0, [])
        )
        if node.type == "import_from_statement":
            for path in self._import_paths(node, resolve=False):
                if (
                    module_parts[-1:] == [_SYS]
                    and len(path) > 1
                    and path[-1] == _SYS_MODULES
                ):
                    self.dynamic = True
        for path in self._import_paths(node, resolve=False):
            if set(path) & self.own_names:
                self.dynamic = True
        if self.module_path.root_init and (
            node.type == "import_statement" or dots == 0 or dots >= 2
        ):
            # B-4(c): a root-level ``__init__.py`` (also any ``__init__.py``
            # run as a single file) has no own name in the run. An absolute
            # import may name it, and so may a relative import whose dots
            # leave the run (``from .. import R``; #695 re-check N-6): the
            # root's parent may be a package. Only a single-dot relative
            # import cannot reach it.
            self.dynamic = True

    def _module_by_name(self, node: Any) -> None:
        """``X[__name__]`` and ``X.get(__name__)`` (also ``__getitem__``,
        ``setdefault``, ``pop``) on any receiver may reach this module through
        a modules mapping, however it was obtained (``sys.modules``,
        ``collections._sys.modules``, a ``case object(modules=m)`` capture):
        a key or first argument that mentions ``__name__`` is dynamic."""
        if node.type == "subscript":
            keys = [
                child
                for index, child in enumerate(node.children)
                if node.field_name_for_child(index) == "subscript"
            ]
            if any(self._mentions_module_name(key) for key in keys):
                self.dynamic = True
            return
        function = node.child_by_field_name("function")
        # Callees are classified after unwrapping parentheses:
        # ``(x.modules.get)(__name__)`` (#695 Codex 4656123247).
        function = (
            _unwrap(function, skip_comments=True) if function is not None else None
        )
        if function is None or function.type != "attribute":
            return
        method = function.child_by_field_name("attribute")
        if method is None or _text(method, self.source) not in _MODULE_GETTERS:
            return
        arguments = node.child_by_field_name("arguments")
        first = (
            arguments.named_children[0]
            if arguments is not None and arguments.named_children
            else None
        )
        if first is not None and self._mentions_module_name(first):
            self.dynamic = True

    def _setattr_call(self, node: Any) -> None:
        """``setattr(x, "name", v)``, ``delattr``, ``x.__setattr__("name", v)``,
        ``object.__setattr__(x, "name", v)`` and namespace mutators
        (``x.__dict__.update(name=v)``, ``.update({"name": v})``,
        ``.setdefault("name", v)``, ``.pop("name")``, ``__setitem__``) write
        ``name`` of a receiver that may be this module.

        The callee and each argument are classified after unwrapping
        parentheses: ``(setattr)(mod, "helper", f)``, ``((setattr))(...)``,
        ``(mod.__setattr__)("helper", f)``, ``(mod.__dict__.update)(...)``,
        ``.update(({"helper": f}))`` (#695 Codex 4656123247).
        """
        function = node.child_by_field_name("function")
        function = (
            _unwrap(function, skip_comments=True) if function is not None else None
        )
        if function is not None and function.type == "attribute":
            function = function.child_by_field_name("attribute")
        if function is None or _text(function, self.source) not in _ATTRIBUTE_WRITERS:
            return
        if _text(function, self.source) in _WRITER_NAMES:
            self._writer_name_check(node, _text(function, self.source))
        arguments = node.child_by_field_name("arguments")
        for argument in arguments.named_children if arguments is not None else ():
            argument = _unwrap(argument, skip_comments=True)
            if argument.type == "keyword_argument":
                keyword = argument.child_by_field_name("name")
                if keyword is not None:
                    self.attribute_writes.add(_text(keyword, self.source))
                continue
            if argument.type == "list_splat":
                # ``setattr(mod, *("helper", f))``: the constants of a literal
                # sequence (#695 fold 18).
                inner = argument.named_children[0] if argument.named_children else None
                inner = (
                    _unwrap(inner, skip_comments=True) if inner is not None else None
                )
                if inner is not None and inner.type in ("tuple", "list"):
                    for element in inner.named_children:
                        value = _constant_string(element, self.source)
                        if value is not None:
                            self.attribute_writes.add(value)
                continue
            if argument.type == "dictionary_splat":
                argument = _unwrap(
                    argument.named_children[0] if argument.named_children else argument,
                    skip_comments=True,
                )
            if argument.type == "dictionary":
                for pair in argument.named_children:
                    key = (
                        pair.child_by_field_name("key") if pair.type == "pair" else None
                    )
                    value = (
                        _constant_string(key, self.source) if key is not None else None
                    )
                    if value is not None:
                        self.attribute_writes.add(value)
                continue
            value = _constant_string(argument, self.source)
            if value is not None:
                self.attribute_writes.add(value)

    # -- namespace writes (#695 fold 18) ------------------------------------

    def _namespace_rules(
        self,
        calls: list[Any],
        attributes: list[Any],
        augmented: list[Any],
        bindings: list[tuple[Any, Any]],
        matches: list[Any],
        identifiers: list[Any],
        operator_names: set[str],
    ) -> None:
        """Writes through a namespace dict that the attribute-write rule does
        not read: a mutator taken off the receiver, a write with a computed
        key or mapping, ``|=``, the ``operator`` writers, and a namespace
        dict that escapes (#695 folds 18–19).

        A **namespace receiver** is ``x.__dict__``, ``vars(x)``, a call with
        a ``"__dict__"`` constant argument (``getattr(x, "__dict__")``), any
        of these in parentheses or as an operand of a conditional or boolean
        expression (``ns if c else {}``, ``ns or {}``), or a name bound from
        one anywhere in the file: every target name of an assignment or
        walrus whose value contains one (``d, e = ns, 0``) and every capture
        of a ``match`` on one (flow-insensitive, transitive). Its writes with
        literal names are recorded; any other write fails closed, and so does
        the receiver escaping into a call argument, a container, a return or
        yield value, a default, a lambda body, a ``with`` item, a ``for`` or
        comprehension iterable or an attribute or subscript target (W-2).
        """
        changed = self.namespace_seen
        while changed:
            changed = False
            for target, value in bindings:
                if not self._contains_namespace(value):
                    continue
                for ident in _target_names(target):
                    names = _spellings(ident, self.source) - self.namespace_aliases
                    if names:
                        self.namespace_aliases |= names
                        changed = True
            for match in matches:
                subject = match.child_by_field_name("subject")
                if subject is None or not self._contains_namespace(subject):
                    continue
                for ident in _match_captures(match):
                    names = _spellings(ident, self.source) - self.namespace_aliases
                    if names:
                        self.namespace_aliases |= names
                        changed = True
        if self.namespace_aliases:
            self.namespace_seen = True
        if self.namespace_seen:
            # W-2: every namespace receiver that escapes.
            candidates = [
                node
                for node in attributes
                if self._namespace_receiver(node) and node.type == "attribute"
            ]
            candidates += [node for node in calls if self._namespace_receiver(node)]
            candidates += [
                ident
                for ident in identifiers
                if _spellings(ident, self.source) & self.namespace_aliases
            ]
            for node in candidates:
                if self._namespace_escape(node, operator_names):
                    self.dynamic = True
        for node in attributes:
            attribute = node.child_by_field_name("attribute")
            if attribute is None:
                continue
            names = _spellings(attribute, self.source)
            receiver = node.child_by_field_name("object")
            if (
                names & _NAMESPACE_MUTATORS
                and receiver is not None
                and self._namespace_receiver(receiver)
                and _callee_call(node) is None
            ):
                # ``u = mod.__dict__.update``, ``map(vars(m).__setitem__, …)``.
                self.dynamic = True
        for node in calls:
            self._namespace_call(node, operator_names)
        for node in augmented:
            self._namespace_ior(node)
        for node in self.subscript_targets:
            receiver = node.child_by_field_name("value")
            if receiver is None or not self._namespace_receiver(receiver):
                continue
            keys = [
                child
                for index, child in enumerate(node.children)
                if node.field_name_for_child(index) == "subscript"
            ]
            if any(_constant_string(key, self.source) is None for key in keys):
                # ``mod.__dict__[k] = f``: a computed key of a namespace.
                self.dynamic = True

    def _contains_namespace(self, node: Any) -> bool:
        stack = [node]
        while stack:
            current = stack.pop()
            if self._namespace_receiver(current):
                return True
            stack.extend(current.named_children)
        return False

    def _namespace_escape(self, node: Any, operator_names: set[str]) -> bool:
        """Whether a namespace receiver escapes (W-2): the position it
        reaches through parentheses and conditional or boolean operands."""
        current = node
        parent = current.parent
        while parent is not None:
            if parent.type == "parenthesized_expression":
                named = [c for c in parent.named_children if c.type != "comment"]
                if len(named) != 1:
                    break
            elif parent.type == "named_expression":
                # ``f(d := mod.__dict__)``: the walrus passes its value on.
                if not _same(current, parent.child_by_field_name("value")):
                    break
            elif parent.type not in ("conditional_expression", "boolean_operator"):
                break
            current, parent = parent, parent.parent
        if parent is None:
            return False
        kind = parent.type
        if kind == "argument_list":
            return not self._mutator_receiver(parent, current, operator_names)
        if kind == "keyword_argument":
            return (
                parent.parent is not None
                and parent.parent.type == "argument_list"
                and _same(current, parent.child_by_field_name("value"))
            )
        if kind in ("list_splat", "dictionary_splat"):
            return parent.parent is not None and parent.parent.type == "argument_list"
        if kind in (
            "list",
            "tuple",
            "set",
            "expression_list",
            "pair",
            "return_statement",
            "yield",
            "with_item",
        ):
            return True
        if kind in ("default_parameter", "typed_default_parameter"):
            return _same(current, parent.child_by_field_name("value"))
        if kind == "lambda":
            return _same(current, parent.child_by_field_name("body"))
        if kind == "as_pattern":
            return parent.parent is not None and parent.parent.type == "with_item"
        if kind in ("for_statement", "for_in_clause"):
            return _same(current, parent.child_by_field_name("right"))
        if kind in _COMPREHENSIONS:
            return _same(current, parent.child_by_field_name("body"))
        if kind == "assignment":
            left = parent.child_by_field_name("left")
            return (
                _same(current, parent.child_by_field_name("right"))
                and left is not None
                and _has_attribute_target(left)
            )
        return False

    def _mutator_receiver(
        self, arguments: Any, node: Any, operator_names: set[str]
    ) -> bool:
        """Whether ``node`` is the receiver (first positional argument) of an
        unbound namespace mutator or an ``operator`` writer, which the write
        rules read (``dict.update(ns, D)``, ``operator.setitem(ns, k, f)``)."""
        first = next(
            (child for child in arguments.named_children if child.type != "comment"),
            None,
        )
        if first is None or not _same(first, node):
            return False
        call = arguments.parent
        function = call.child_by_field_name("function") if call is not None else None
        if function is None:
            return False
        function = _unwrap(function, skip_comments=True)
        if function.type == "attribute":
            attribute = function.child_by_field_name("attribute")
            names = (
                _spellings(attribute, self.source) if attribute is not None else set()
            )
            return bool(names & (_NAMESPACE_MUTATORS | _OPERATOR_WRITERS))
        if function.type == "identifier":
            return bool(_spellings(function, self.source) & operator_names)
        return False

    def _namespace_receiver(self, node: Any) -> bool:
        node = _unwrap(node, skip_comments=True)
        if node.type == "named_expression":
            # ``(d := mod.__dict__).update(D)``
            value = node.child_by_field_name("value")
            return value is not None and self._namespace_receiver(value)
        if node.type == "conditional_expression":
            return any(
                self._namespace_receiver(child)
                for child in node.named_children
                if child.type != "comment"
            )
        if node.type == "boolean_operator":
            return any(
                self._namespace_receiver(child)
                for child in (
                    node.child_by_field_name("left"),
                    node.child_by_field_name("right"),
                )
                if child is not None
            )
        if node.type == "identifier":
            return bool(_spellings(node, self.source) & self.namespace_aliases)
        if node.type == "attribute":
            attribute = node.child_by_field_name("attribute")
            if attribute is None:
                return False
            # ``x.__dict__``, and a namespace alias read back as an attribute:
            # a module-level ``NS`` as ``m.NS``, a class-body ``ns`` as
            # ``K.ns`` or ``self.ns`` (fold 21, B-4).
            return _text(attribute, self.source) == _NAMESPACE_DICT or bool(
                _spellings(attribute, self.source) & self.namespace_aliases
            )
        if node.type == "call":
            function = node.child_by_field_name("function")
            function = (
                _unwrap(function, skip_comments=True) if function is not None else None
            )
            if function is not None and function.type == "identifier":
                if _text(function, self.source) == "vars":
                    return True
                arguments = _call_arguments(node)
                if (
                    _text(function, self.source) == "getattr"
                    and len(arguments) > 1
                    and _constant_string(arguments[1], self.source)
                    in self.namespace_aliases
                ):
                    return True  # ``getattr(m, "NS")`` (B-4)
            return any(
                _constant_string(argument, self.source) == _NAMESPACE_DICT
                for argument in _call_arguments(node)
            )
        return False

    def _namespace_call(self, node: Any, operator_names: set[str]) -> None:
        function = node.child_by_field_name("function")
        if function is None:
            return
        function = _unwrap(function, skip_comments=True)
        arguments = _call_arguments(node)
        callee = ""
        if function.type == "attribute":
            attribute = function.child_by_field_name("attribute")
            receiver = function.child_by_field_name("object")
            name = _text(attribute, self.source) if attribute is not None else ""
            callee = name
            if name in _NAMESPACE_MUTATORS:
                if receiver is not None and self._namespace_receiver(receiver):
                    # ``mod.__dict__.update(D)``, ``vars(m).pop(k)``.
                    if not self._literal_namespace_write(name, arguments):
                        self.dynamic = True
                elif arguments and self._namespace_receiver(arguments[0]):
                    # Unbound: ``dict.update(ns, D)``, ``type(ns).pop(ns, k)``
                    # (fold 19 B-2b).
                    if not self._literal_namespace_write(name, arguments[1:]):
                        self.dynamic = True
            if name in _OPERATOR_WRITERS:
                self._operator_write(arguments)
        elif function.type == "identifier":
            callee = _text(function, self.source)
            if _spellings(function, self.source) & operator_names:
                self._operator_write(arguments)
        if callee == "attrgetter" and any(
            _NAMESPACE_DICT in _NAME_SEPARATORS.split(value)
            for value in (
                _constant_string(argument, self.source) for argument in arguments
            )
            if value is not None
        ):
            # ``attrgetter("__dict__.update")(mod)``: any path through a
            # namespace dict (fold 19 B-2c).
            self.dynamic = True
        if callee == "methodcaller" and self.namespace_seen and arguments:
            value = _constant_string(arguments[0], self.source)
            if value in _NAMESPACE_MUTATORS:
                # ``methodcaller("update", D)(ns)`` (B-2c).
                self.dynamic = True

    def _literal_namespace_write(self, name: str, arguments: list[Any]) -> bool:
        """Whether a namespace mutator call names every key it writes as a
        constant (the attribute-write rule then records them)."""
        if name == "update":
            return all(self._literal_mapping(argument) for argument in arguments)
        if name == "__ior__":
            return len(arguments) == 1 and self._literal_mapping(arguments[0])
        if name in ("clear", "popitem"):
            # Every name may go (fold 19: anything not literal fails closed).
            return False
        return bool(arguments) and (
            _constant_string(arguments[0], self.source) is not None
        )

    def _literal_mapping(self, node: Any) -> bool:
        node = _unwrap(node, skip_comments=True)
        if node.type == "keyword_argument":
            return True
        if node.type == "dictionary_splat":
            inner = node.named_children[0] if node.named_children else node
            return self._literal_mapping(inner)
        if node.type != "dictionary":
            return False
        for pair in node.named_children:
            if pair.type == "comment":
                continue
            key = pair.child_by_field_name("key") if pair.type == "pair" else None
            if key is None or _constant_string(key, self.source) is None:
                return False
        return True

    def _operator_write(self, arguments: list[Any]) -> None:
        """``operator.setitem(x, "name", f)`` and the other ``operator``
        writers: a constant key (or a literal mapping for ``ior``/``iadd``)
        is a write of that name on any receiver, like ``x["name"] = f``; on a
        namespace receiver anything else fails closed."""
        if not arguments:
            return
        namespace = self._namespace_receiver(arguments[0])
        key = _unwrap(arguments[1], skip_comments=True) if len(arguments) > 1 else None
        if key is None:
            if namespace:
                self.dynamic = True
            return
        value = _constant_string(key, self.source)
        if value is not None:
            self.attribute_writes.add(value)
            return
        if key.type == "dictionary" and self._literal_mapping(key):
            for pair in key.named_children:
                pair_key = (
                    pair.child_by_field_name("key") if pair.type == "pair" else None
                )
                text = (
                    _constant_string(pair_key, self.source)
                    if pair_key is not None
                    else None
                )
                if text is not None:
                    self.attribute_writes.add(text)
            return
        if namespace:
            self.dynamic = True

    def _namespace_ior(self, node: Any) -> None:
        """``x |= {"name": f}`` writes ``name`` of any receiver, like
        ``x.update({"name": f})``; on a namespace receiver any other right
        side fails closed."""
        operator = node.child_by_field_name("operator")
        if operator is None or _text(operator, self.source) != "|=":
            return
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None:
            return
        right = _unwrap(right, skip_comments=True)
        literal = right.type == "dictionary" and self._literal_mapping(right)
        if literal:
            for pair in right.named_children:
                key = pair.child_by_field_name("key") if pair.type == "pair" else None
                text = _constant_string(key, self.source) if key is not None else None
                if text is not None:
                    self.attribute_writes.add(text)
        elif self._namespace_receiver(left):
            self.dynamic = True

    def _writer_mention(
        self, ident: Any, spellings: set[str], operator_names: set[str]
    ) -> None:
        """A writer named anywhere but as the callee of a direct call is
        handed on: ``w = setattr``, ``partial(setattr, mod)``,
        ``f = object.__setattr__`` (rule 1, fail closed); an ``operator``
        writer handed on fails closed when the file names a namespace dict
        (rule 3)."""
        parent = ident.parent
        if parent is None or _scope_binding_name(ident) or _import_context(ident):
            return
        if parent.type == "keyword_argument" and _same(
            ident, parent.child_by_field_name("name")
        ):
            return
        is_attribute = parent.type == "attribute" and _same(
            ident, parent.child_by_field_name("attribute")
        )
        callee = parent if is_attribute else ident
        if _callee_call(callee) is not None:
            return
        if spellings & _WRITER_NAMES:
            self.dynamic = True
        operator = (spellings & _OPERATOR_WRITERS) if is_attribute else set()
        if operator or (not is_attribute and spellings & operator_names):
            self.operator_escape = True

    def _writer_name_check(self, node: Any, name: str) -> None:
        """W-1: a writer call whose name argument is not a constant string,
        on any receiver, makes module-scope lookups dynamic. The name is the
        second argument of ``setattr``/``delattr`` and of an unbound
        ``X.__setattr__(obj, name, v)``/``X.__delattr__(obj, name)``, the first
        of a bound ``obj.__setattr__(name, v)``; a literal ``*`` splat is
        read element by element, any other splat is computed."""
        flat: list[Any] = []
        for argument in _call_arguments(node):
            if argument.type == "keyword_argument":
                continue
            if argument.type == "list_splat":
                inner = argument.named_children[0] if argument.named_children else None
                inner = (
                    _unwrap(inner, skip_comments=True) if inner is not None else None
                )
                if inner is None or inner.type not in ("tuple", "list"):
                    self.dynamic = True
                    return
                flat.extend(
                    _unwrap(c, skip_comments=True)
                    for c in inner.named_children
                    if c.type != "comment"
                )
                continue
            if argument.type == "dictionary_splat":
                self.dynamic = True
                return
            flat.append(argument)
        if name in ("setattr", "delattr"):
            index = 1
        elif name == "__setattr__":
            index = 1 if len(flat) >= 3 else 0
        else:
            index = 1 if len(flat) >= 2 else 0
        if len(flat) <= index or _constant_string(flat[index], self.source) is None:
            self.dynamic = True

    # -- unittest.mock (#695 fold 19, W-3) ----------------------------------

    def _resolver_rules(
        self,
        attributes: list[Any],
        identifiers: list[Any],
        pydoc_names: set[str],
        logging_config_names: set[str],
    ) -> None:
        """A stdlib string-to-module resolver mentioned in any position fails
        closed, like ``importlib`` (fold 21, E-20): ``resolve_name``,
        ``safeimport`` and ``find_class`` in every spelling, ``locate`` on
        ``pydoc``, ``_resolve``/``_importer`` on ``logging.config`` (their
        from-imports are handled with the import)."""
        for ident in identifiers:
            if _spellings(ident, self.source) & _RESOLVER_NAMES:
                self.dynamic = True
                return
        for node in attributes:
            attribute = node.child_by_field_name("attribute")
            receiver = node.child_by_field_name("object")
            if attribute is None or receiver is None:
                continue
            name = _text(attribute, self.source)
            receiver = _unwrap(receiver, skip_comments=True)
            if name == _SYS_MODULES and (
                (
                    receiver.type == "identifier"
                    and _text(receiver, self.source) == "_sys"
                )
                or (
                    receiver.type == "attribute"
                    and receiver.child_by_field_name("attribute") is not None
                    and _text(receiver.child_by_field_name("attribute"), self.source)
                    == "_sys"
                )
            ):
                # ``collections._sys.modules[X.__module__]``: another module's
                # private ``sys`` (fold 21, E-20; 0 extra stdlib files).
                self.dynamic = True
            if name in _PYDOC_RESOLVERS and receiver.type == "identifier":
                if _spellings(receiver, self.source) & pydoc_names:
                    self.dynamic = True
            if name in _LOGGING_RESOLVERS:
                if receiver.type == "identifier" and (
                    _spellings(receiver, self.source) & logging_config_names
                ):
                    self.dynamic = True
                elif receiver.type == "attribute":
                    inner = receiver.child_by_field_name("attribute")
                    head = receiver.child_by_field_name("object")
                    if (
                        inner is not None
                        and _text(inner, self.source) == "config"
                        and head is not None
                        and _text(_unwrap(head, skip_comments=True), self.source)
                        == "logging"
                    ):
                        self.dynamic = True

    def _mock_aliases(
        self,
        bindings: list[tuple[Any, Any]],
        mock_names: set[str],
    ) -> None:
        """Mock-module and pytest-mock names bound by assignment, walrus,
        tuple targets, class bodies or ``self.X = …`` (fold 21, B-5),
        flow-insensitively."""
        changed = True
        while changed:
            changed = False
            for target, value in bindings:
                value = _unwrap(value, skip_comments=True)
                if self._mock_expression(value, mock_names):
                    sink = self.mock_aliases
                elif self._mocker_expression(value):
                    sink = self.mocker_names
                else:
                    continue
                names: set[str] = set()
                if target.type == "attribute":
                    attribute = target.child_by_field_name("attribute")
                    if attribute is not None:
                        names = _spellings(attribute, self.source)
                else:
                    for ident in _target_names(target):
                        names |= _spellings(ident, self.source)
                if names - sink:
                    sink |= names
                    changed = True

    def _mock_expression(self, node: Any, mock_names: set[str]) -> bool:
        """``mock`` (an import), one of its aliases, an attribute holding one
        (``K.mk``, ``self.mk``) or ``unittest.mock``."""
        node = _unwrap(node, skip_comments=True)
        if node.type == "named_expression":
            value = node.child_by_field_name("value")
            return value is not None and self._mock_expression(value, mock_names)
        if node.type == "identifier":
            return bool(
                _spellings(node, self.source) & (mock_names | self.mock_aliases)
            )
        if node.type != "attribute":
            return False
        attribute = node.child_by_field_name("attribute")
        head = node.child_by_field_name("object")
        if attribute is None:
            return False
        if _spellings(attribute, self.source) & self.mock_aliases:
            return True
        return (
            _text(attribute, self.source) == "mock"
            and head is not None
            and _text(_unwrap(head, skip_comments=True), self.source) == "unittest"
        )

    def _mocker_expression(self, node: Any) -> bool:
        node = _unwrap(node, skip_comments=True)
        if node.type == "identifier":
            return bool(_spellings(node, self.source) & self.mocker_names)
        if node.type == "attribute":
            attribute = node.child_by_field_name("attribute")
            return attribute is not None and bool(
                _spellings(attribute, self.source) & self.mocker_names
            )
        return False

    def _mock_rules(
        self,
        calls: list[Any],
        attributes: list[Any],
        identifiers: list[Any],
        bindings: list[tuple[Any, Any]],
        mock_names: set[str],
        patch_names: set[str],
    ) -> None:
        """``patch``, ``patch.object``, ``patch.dict`` and ``patch.multiple``
        from ``unittest.mock`` (or ``mock``) write by dotted path or attribute
        name: a non-constant target or attribute name makes module-scope
        lookups dynamic, a constant ``patch.object`` attribute and the
        ``patch.multiple`` keywords are attribute writes, and ``patch`` handed
        on fails closed. A constant ``patch("a.helper")`` keeps the own-name
        rule.

        Fold 20 adds receiver-based patchers: any ``X.patch.object``,
        ``X.patch.dict`` or ``X.patch.multiple`` chain, whatever ``X`` is, and
        ``.patch`` on a pytest-mock fixture (``mocker``, ``module_mocker``,
        ``class_mocker``, ``package_mocker``, ``session_mocker``). A plain
        ``.patch(url)`` on any other receiver is untouched.

        Fold 21 (B-5): mock-module and pytest-mock aliases are tracked; a
        mock-module name used anywhere but as the receiver of an attribute
        access, a direct callee or the value of an alias binding fails closed
        (``getattr(mock, "patch")``, ``attrgetter("patch")(mock)``), and so
        does a constant ``"patch"`` string in a file that imports the mock
        module."""
        self._mock_aliases(bindings, mock_names)
        mock_imported = bool(mock_names or patch_names) or any(
            self._mock_expression(node, set()) for node in attributes
        )
        if mock_imported and self.patch_string_seen:
            self.dynamic = True
        mock_uses = [
            ident
            for ident in identifiers
            if _spellings(ident, self.source) & (mock_names | self.mock_aliases)
            and not _import_context(ident)
            and not _scope_binding_name(ident)
        ]
        mock_uses += [node for node in attributes if self._mock_expression(node, set())]
        for node in mock_uses:
            if not self._mock_receiver_use(node):
                self.dynamic = True
        for node in calls:
            function = node.child_by_field_name("function")
            if function is None:
                continue
            function = _unwrap(function, skip_comments=True)
            kind = None
            if self._is_patch(function, mock_names, patch_names):
                kind = "patch"
            elif function.type == "attribute":
                attribute = function.child_by_field_name("attribute")
                method = _text(attribute, self.source) if attribute is not None else ""
                receiver = function.child_by_field_name("object")
                if (
                    method in _PATCH_METHODS
                    and receiver is not None
                    and (
                        self._is_patch(receiver, mock_names, patch_names)
                        or _is_patch_attribute(receiver, self.source)
                    )
                ):
                    kind = method
            if kind is not None:
                self._patch_call(node, kind)
        candidates = [
            ident
            for ident in identifiers
            if _spellings(ident, self.source) & patch_names
            and not _import_context(ident)
            and not _scope_binding_name(ident)
        ]
        candidates += [
            node for node in attributes if self._is_patch(node, mock_names, patch_names)
        ]
        # ``X.patch.object`` for any ``X`` (fold 20): handed on fails closed.
        for node in attributes:
            attribute = node.child_by_field_name("attribute")
            receiver = node.child_by_field_name("object")
            if (
                attribute is not None
                and _text(attribute, self.source) in _PATCH_METHODS
                and receiver is not None
                and _is_patch_attribute(receiver, self.source)
                and _callee_call(node) is None
            ):
                self.dynamic = True
        for node in candidates:
            if _callee_call(node) is not None:
                continue
            parent = node.parent
            if parent is not None and parent.type == "attribute":
                attribute = parent.child_by_field_name("attribute")
                method = _text(attribute, self.source) if attribute is not None else ""
                if method not in ("object", "dict", "multiple"):
                    continue  # ``patch.stopall()``, ``patch.TEST_PREFIX``
                if _callee_call(parent) is not None:
                    continue
            if (
                parent is not None
                and parent.type in ("assignment",)
                and _same(node, parent.child_by_field_name("left"))
            ):
                continue
            # ``p = mock.patch``, ``partial(patch.object, K)``: handed on.
            self.dynamic = True

    def _is_patch(self, node: Any, mock_names: set[str], patch_names: set[str]) -> bool:
        node = _unwrap(node, skip_comments=True)
        if node.type == "identifier":
            return bool(_spellings(node, self.source) & patch_names)
        if node.type != "attribute":
            return False
        attribute = node.child_by_field_name("attribute")
        if attribute is None or _text(attribute, self.source) != "patch":
            return False
        receiver = node.child_by_field_name("object")
        receiver = _unwrap(receiver, skip_comments=True) if receiver else None
        if receiver is None:
            return False
        # ``mock.patch`` (an import or an alias, also ``K.mk.patch``),
        # ``unittest.mock.patch``, and a pytest-mock fixture's ``.patch``
        # (``mocker``, ``mm = mocker``, ``self.mocker``).
        return self._mock_expression(receiver, mock_names) or self._mocker_expression(
            receiver
        )

    def _mock_receiver_use(self, node: Any) -> bool:
        """Whether a mock-module name is used as an attribute receiver, a
        direct callee, an alias binding's value or its own binding."""
        current = node
        parent = current.parent
        while parent is not None and parent.type == "parenthesized_expression":
            current, parent = parent, parent.parent
        if parent is None:
            return True
        if parent.type == "attribute":
            # The receiver (``mock.patch``), or the attribute name itself.
            return True
        if _callee_call(current) is not None:
            return True
        if parent.type in ("assignment", "named_expression"):
            left = parent.child_by_field_name(
                "left" if parent.type == "assignment" else "name"
            )
            right = parent.child_by_field_name(
                "right" if parent.type == "assignment" else "value"
            )
            if right is not None and _same(current, right):
                return True  # ``mk = mock`` (tracked)
            if left is not None and _same(current, _unwrap(left)):
                return True  # rebinding the name
        if parent.type in ("pattern_list", "tuple_pattern", "list_pattern"):
            return True
        return False

    def _patch_call(self, node: Any, kind: str) -> None:
        arguments = _call_arguments(node)
        positional = [a for a in arguments if a.type != "keyword_argument"]
        keywords = {
            _text(a.child_by_field_name("name"), self.source): a.child_by_field_name(
                "value"
            )
            for a in arguments
            if a.type == "keyword_argument" and a.child_by_field_name("name")
        }
        if any(a.type in ("list_splat", "dictionary_splat") for a in positional):
            self.dynamic = True
            return
        if kind == "patch" or kind == "dict":
            field = "target" if kind == "patch" else "in_dict"
            target = positional[0] if positional else keywords.get(field)
            if target is None or _constant_string(target, self.source) is None:
                self.dynamic = True
            return
        if kind == "object":
            attribute = (
                positional[1] if len(positional) > 1 else keywords.get("attribute")
            )
            value = (
                _constant_string(attribute, self.source)
                if attribute is not None
                else None
            )
            if value is None:
                self.dynamic = True
            else:
                self.attribute_writes.add(value)
            return
        # multiple: every keyword other than its own options names an
        # attribute.
        options = {"target", "spec", "create", "spec_set", "autospec", "new_callable"}
        for keyword in keywords:
            if keyword not in options:
                self.attribute_writes.add(keyword)

    def _mentions_module_name(self, node: Any) -> bool:
        return any(
            _text(ident, self.source) == "__name__" for ident in _identifiers(node)
        )

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
        if _in_annotation(ident):
            # Annotations are evaluated lazily (PEP 649/749): ``annotationlib``
            # runs an annotation scope again under substitute globals for the
            # ``FORWARDREF`` and ``STRING`` formats, which ``dataclasses``,
            # ``typing.get_type_hints``, ``inspect.signature`` and
            # ``functools.singledispatch`` use, so a call there may reach a
            # stand-in, not the binding (#695 re-check at 14e8f044, Q-2).
            return _none("dynamic-scope")
        if _mangled_names(ident, name, self.source):
            # CPython looks up ``_C__x`` for ``__x`` inside class ``C``; the
            # source spelling proves nothing (B-1).
            return _none(UNMAPPED)
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


def _mangle_eligible(name: str) -> bool:
    return name.startswith("__") and not name.endswith("__")


def _mangled_names(node: Any, name: str, source: bytes) -> list[str]:
    """Every mangled spelling a class around ``node`` may give ``name``.

    CPython rewrites ``__x`` (not ending in ``__``) inside a class to
    ``_<Class>__x``, the class name's leading underscores stripped, unless
    the class name is all underscores. Every enclosing class counts, not
    only the innermost, and a class's bases and decorators count too: an
    extra spelling can only fail closed.
    """
    if not _mangle_eligible(name):
        return []
    found: list[str] = []
    child, current = node, node.parent
    while current is not None:
        if current.type == "class_definition":
            class_name = current.child_by_field_name("name")
            if class_name is not None and not _same(child, class_name):
                stripped = _text(class_name, source).lstrip("_")
                if stripped:
                    found.append(f"_{stripped}{name}")
        child, current = current, current.parent
    return found


def _spellings(ident: Any, source: bytes) -> set[str]:
    """Every name an identifier may have at run time: its source spelling and
    each mangled ``_Class__x`` spelling a class around it may give it (the
    rules of :func:`_mangled_names`)."""
    name = _text(ident, source)
    return {name, *_mangled_names(ident, name, source)}


def _in_annotation(ident: Any) -> bool:
    """Whether ``ident`` lies in an annotation: the ``type`` of a typed
    parameter, a typed default parameter or an annotated assignment, a
    function's return annotation, or the value of a ``type`` statement."""
    child = ident
    node = ident.parent
    while node is not None:
        kind = node.type
        if kind in ("typed_parameter", "typed_default_parameter", "assignment"):
            if _same(child, node.child_by_field_name("type")):
                return True
        elif kind == "function_definition":
            if _same(child, node.child_by_field_name("return_type")):
                return True
        elif kind == "type_alias_statement":
            # A ``type`` value is evaluated lazily too (PEP 695); in a class
            # body it reads the live class namespace through
            # ``__classdict__`` (#695 re-check at a6734480, S-2).
            if _same(child, node.child_by_field_name("right")):
                return True
        child, node = node, node.parent
    return False


def _in_class_body(node: Any) -> bool:
    """Whether a statement runs directly in a class body: the nearest
    enclosing ``class_definition`` comes before any function or lambda."""
    current = node.parent
    while current is not None:
        if current.type == "class_definition":
            return True
        if current.type in ("function_definition", "lambda"):
            return False
        current = current.parent
    return False


def _from_import_bound_names(node: Any) -> list[Any]:
    """The identifiers a ``from … import`` binds (each alias, or the imported
    name)."""
    bound: list[Any] = []
    for index, child in enumerate(node.children):
        if node.field_name_for_child(index) != "name":
            continue
        if child.type == "aliased_import":
            alias = child.child_by_field_name("alias")
            if alias is not None:
                bound.append(alias)
            continue
        tokens = _identifier_children(child) if child.type != "identifier" else [child]
        if len(tokens) == 1:
            bound.append(tokens[0])
    return bound


def _unwrap(node: Any, skip_comments: bool = False) -> Any:
    """``node`` without enclosing parentheses: ``((x))`` is ``x``. A tuple,
    ``(x,)``, is not a parenthesized expression and stays as it is.

    With ``skip_comments``, a comment inside the parentheses does not count
    (``(setattr  # note\n)(...)``); callee and receiver classification uses
    that form (#695 Codex 4656123247). The ``__main__`` guard's allow-list
    keeps the strict form.
    """
    while node.type == "parenthesized_expression":
        children = [
            child
            for child in node.named_children
            if not (skip_comments and child.type == "comment")
        ]
        if len(children) != 1:
            break
        node = children[0]
    return node


_PARAMETER_PARENTS = frozenset(
    {
        "parameters",
        "lambda_parameters",
        "typed_parameter",
        "list_splat_pattern",
        "dictionary_splat_pattern",
    }
)


def _scope_binding_name(ident: Any) -> bool:
    """Whether an identifier is a parameter or ``def``/``class`` name: a pure
    scope binding, which can never look up an attribute by name. Every other
    position, including any node type the grammar may add, counts for the
    own-name rule."""
    parent = ident.parent
    if parent is None:
        return False
    if parent.type in _PARAMETER_PARENTS:
        return True
    if parent.type in (
        "default_parameter",
        "typed_default_parameter",
        "function_definition",
        "class_definition",
    ):
        return _same(ident, parent.child_by_field_name("name"))
    return False


def _identifier_children(node: Any) -> list[Any]:
    """A node's identifier children, skipping comments and line
    continuations between the tokens."""
    return [child for child in node.named_children if child.type == "identifier"]


def _dotted_parts(node: Any, source: bytes) -> list[str]:
    """The identifier tokens of a dotted name (or of a lone identifier),
    never its raw text: whitespace, comments and backslash continuations may
    sit between the tokens (#695 re-check N-7)."""
    if node.type == "identifier":
        return [_text(node, source)]
    return [_text(child, source) for child in _identifier_children(node)]


def _module_parts(node: Any, source: bytes) -> tuple[int, list[str]]:
    """A ``from`` import's relative level and module components.

    The level counts the ``.`` tokens of ``import_prefix`` (``from . .
    import x`` is level 2, ``from ...x`` level 3); the components come from
    the ``dotted_name``'s identifiers, so ``from . helper import M`` is
    ``(1, ["helper"])`` and not ``" helper"``.
    """
    module = node.child_by_field_name("module_name")
    if module is None:
        return 0, []
    if module.type != "relative_import":
        return 0, _dotted_parts(module, source)
    level = 0
    parts: list[str] = []
    for child in module.children:
        if child.type == "import_prefix":
            level += sum(
                _text(token, source).count(".")
                for token in child.children
                if not token.is_named
            )
        elif child.type == "dotted_name":
            parts = _dotted_parts(child, source)
    return level, parts


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
    """The value of a constant string expression: a literal, an f-string
    whose interpolations are all constant strings (``f"__glo{'bals'}__"``),
    adjacent literals, or literals joined by ``+``, through parentheses and
    with comments between the parts (#695 B-1, W-4).

    Anything computed (a name, a call, a conversion or format spec) gives
    ``None``; such strings are plan risk R12.
    """
    kind = node.type
    if kind == "parenthesized_expression":
        inner = _unwrap(node, skip_comments=True)
        return None if inner is node else _constant_string(inner, source)
    if kind == "concatenated_string":
        parts = [
            _constant_string(child, source)
            for child in node.named_children
            if child.type != "comment"
        ]
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
    if kind != "string":
        return None
    if any(child.type == "interpolation" for child in node.named_children):
        return _constant_fstring(node, source)
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


def _constant_fstring(node: Any, source: bytes) -> str | None:
    """An f-string whose interpolations are all constant strings, with no
    conversion, format spec or ``=`` (#695 W-4); otherwise ``None``."""
    start = next((c for c in node.children if c.type == "string_start"), None)
    if start is None:
        return None
    opening = _text(start, source)
    quote_at = min(
        (index for index in (opening.find("'"), opening.find('"')) if index >= 0),
        default=-1,
    )
    if quote_at < 0:
        return None
    prefix = opening[:quote_at].lower()
    quote = opening[quote_at:]
    if "b" in prefix or "f" not in prefix:
        return None
    plain = prefix.replace("f", "")
    pieces: list[str] = []
    for child in node.children:
        if child.type in ("string_start", "string_end"):
            continue
        if child.type == "interpolation":
            inner = [c for c in child.children if c.type not in ("{", "}")]
            if len(inner) != 1:
                return None
            value = _constant_string(inner[0], source)
            if value is None:
                return None
            pieces.append(value)
            continue
        raw = _text(child, source).replace("{{", "{").replace("}}", "}")
        try:
            value = ast.literal_eval(plain + quote + raw + quote)
        except (SyntaxError, ValueError):
            return None
        if not isinstance(value, str):
            return None
        pieces.append(value)
    return "".join(pieces)


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
        if kind == "dotted_name" and len(_identifier_children(current)) > 1:
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


def _from_import_names(node: Any, source: bytes) -> list[tuple[str, Any]]:
    """``(imported last name, bound name node)`` for each name a
    ``from … import`` binds."""
    found: list[tuple[str, Any]] = []
    for child in node.named_children:
        if child.type not in ("dotted_name", "aliased_import"):
            continue
        if _same(child, node.child_by_field_name("module_name")):
            continue
        name_node = (
            child.child_by_field_name("name")
            if child.type == "aliased_import"
            else child
        )
        parts = _dotted_parts(name_node, source) if name_node is not None else []
        bound = (
            child.child_by_field_name("alias")
            if child.type == "aliased_import"
            else name_node
        )
        if parts and bound is not None:
            found.append((parts[-1], bound))
    return found


def _target_names(target: Any) -> list[Any]:
    """The names a target binds: identifiers through tuple, list, starred
    and parenthesized forms, not the parts of an attribute or subscript."""
    found: list[Any] = []
    stack = [target]
    while stack:
        current = stack.pop()
        if current.type == "identifier":
            found.append(current)
        elif current.type not in ("attribute", "subscript"):
            stack.extend(current.named_children)
    return found


def _has_attribute_target(target: Any) -> bool:
    """Whether a target stores into an attribute or subscript."""
    stack = [target]
    while stack:
        current = stack.pop()
        if current.type in ("attribute", "subscript"):
            return True
        stack.extend(current.named_children)
    return False


def _match_captures(match: Any) -> list[Any]:
    found: list[Any] = []
    stack = [match]
    while stack:
        current = stack.pop()
        if current.type == "case_pattern":
            found.extend(_pattern_captures(current))
            continue
        stack.extend(current.named_children)
    return found


def _is_patch_attribute(node: Any, source: bytes) -> bool:
    """Whether ``node`` is ``X.patch`` for any ``X`` (through parentheses)."""
    node = _unwrap(node, skip_comments=True)
    if node.type != "attribute":
        return False
    attribute = node.child_by_field_name("attribute")
    return attribute is not None and _text(attribute, source) == "patch"


def _callee_call(node: Any) -> Any:
    """The call whose callee ``node`` is, through any parentheses, or
    ``None``."""
    current = node
    parent = current.parent
    while parent is not None and parent.type == "parenthesized_expression":
        named = [c for c in parent.named_children if c.type != "comment"]
        if len(named) != 1:
            return None
        current, parent = parent, parent.parent
    if parent is not None and parent.type == "call":
        if _same(current, parent.child_by_field_name("function")):
            return parent
    return None


def _call_arguments(node: Any) -> list[Any]:
    """A call's arguments, unwrapped, without comments."""
    arguments = node.child_by_field_name("arguments")
    if arguments is None:
        return []
    return [
        _unwrap(child, skip_comments=True)
        for child in arguments.named_children
        if child.type != "comment"
    ]


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
        stripped = line.lstrip(b" \t\f")
        leading = line[: len(line) - len(stripped)]
        if b"\f" in leading or stripped.startswith(b"\\"):
            # A backslash continuation as a line's first non-blank character:
            # CPython takes the indentation from this line, tree-sitter from
            # the next (B-2).
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


@dataclass(frozen=True)
class ModulePath:
    """What a Python file's display path says about its own module."""

    own_names: frozenset[str] = frozenset()
    # ``__init__.py``: importing a submodule sets the package's global.
    package_init: bool = False
    # A root-level ``__init__.py``, whose package name is outside the run.
    root_init: bool = False
    # The dotted module path relative to the run root (``("pkg", "sub",
    # "mod")``; ``("pkg", "sub")`` for ``pkg/sub/__init__.py``). The root and
    # any ancestor directory may be packages too, so every suffix of it, and
    # any longer path ending in one, may name the module: each ends with the
    # own name.
    components: tuple[str, ...] = ()
    # No path at all: the own name cannot be computed, so module-scope
    # lookups fail closed.
    unknown: bool = False


def module_path(path: str) -> ModulePath:
    """The :class:`ModulePath` of a root-relative display path."""
    parts = [part for part in path.replace("\\", "/").split("/") if part]
    if not parts:
        return ModulePath(unknown=True)
    init = parts[-1] == "__init__.py"
    components = [*parts[:-1]]
    if parts and not init:
        components.append(parts[-1].rsplit(".", 1)[0])
    return ModulePath(
        own_names=own_module_names(path),
        package_init=init,
        root_init=init and len(parts) == 1,
        components=tuple(components),
    )


def own_module_names(path: str) -> frozenset[str]:
    """The names a file's own module is imported by: its raw stem, or its
    package directory's raw name for ``__init__.py``.

    No identifier filter (#695 re-check N-5): ``my-mod`` is importable by
    ``importlib`` and loaders, and ``setattr(parent, "my-mod", module)``
    still happens. A dotted stem also contributes its components.
    """
    parts = path.replace("\\", "/").rstrip("/").split("/")
    stem = parts[-1].rsplit(".", 1)[0] if parts and parts[-1] else ""
    if stem == "__init__":
        stem = parts[-2] if len(parts) > 1 else ""
    if not stem:
        return frozenset()
    return frozenset({stem, *(part for part in stem.split(".") if part)})


def analyze(
    root: Any,
    source: bytes,
    language: str,
    call_facts: Sequence[Mapping[str, Any]],
    path: str | None = None,
) -> dict[str, Any]:
    """Return partial scope facts: the goal and one outcome per call.

    ``path`` is the file's root-relative display path (:func:`module_path`).
    Without one (``None`` or ``""``) the own name is unknown, and module-scope
    lookups fail closed.
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
    analysis = _Analysis(root, source, module_path=module_path(path or ""))
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
