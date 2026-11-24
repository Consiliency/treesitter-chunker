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
  binding can only fail closed. Such a binding, and a type parameter's bound,
  constraints or default, is *phantom*: CPython 3.14 does not make it, so it
  never proves the file's own binding of a builtin or a checked module
  (R-699-5);
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
   (:data:`BUILTINS`, or one the stdlib installs: :data:`INSTALLED_BUILTINS`)
   never proves (``builtin-shadow``): until it runs, the
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
for the own-name rule and the dynamic attribute names. For this rule a
constant string also splits on format and attribute punctuation (``{ } [ ]
! ( ) $ %`` and whitespace), and on the identifier a default
``string.Template`` substitutes, so a stored template (``T = "{:__main__}"``)
counts wherever it is later formatted; the decoded literal parts and format
specs of f-strings and t-strings count the same way, and a string tree-sitter
accepts but this rule cannot decode fails closed (treesitter-chunker#698,
R-698-1). Tier 2 reads the same verdict as its run-wide ``__main__`` cause,
and escapes are decoded without ``ast``, so no warning filter changes the
facts (R-698-2);
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
Python 2 ``exec`` statement. Inside a function, ``locals()`` cannot rebind
a local, so without ``f_locals`` lookups that resolve in a function scope are
unaffected (``locals()`` still reads every local, which makes a sensitive
alias or parameter there reachable, #707); a class body's namespace is a dict
it can write, so class-body lookups fail closed too. Monkeypatching from other modules (plan R10) and
run-time paths no syntactic rule sees (plan R12: frame writes from another
module, computed strings, other ``X.modules`` uses, ``gc`` tricks) are not
tracked.

**Code run from a string, a payload or an annotation fails closed file-wide**
(treesitter-chunker#699 S2: plan PY-1..PY-3 and PY-8, ruling R-699-1 B-2,
B-4, B-5). String code can reach its caller's frame and write a function's
locals with no name spelled outside the string (PEP 667), so each trigger
makes every lookup ``dynamic-scope``, function scopes included:

- the builtins ``exec``, ``eval``, ``execfile``, ``compile`` and
  ``breakpoint``, and the Python 2 ``exec`` statement. A use is the builtin
  unless the ordinary lookup at the use site proves the file's own binding
  and that binding dominates the use (ruling R-699-3): any binding in a
  function scope does (a parameter, a local, a function-local import from
  another module). No module or class binding does, since a call may run
  before it and get the builtin: a module-level ``from re import compile``
  (``builtin-shadow``), ``compile = compile``, ``(compile := compile)``; an
  import from ``builtins`` counts anywhere. As an attribute or a constant
  string they count only in a file that reaches the builtins namespace
  (``builtins.exec``, ``len.__self__.eval``, ``inspect.getmodule(len)``, a
  module acquired by a computed name), so ``model.eval()`` is not one, and
  neither is ``re.compile`` on a proven ``re`` import;
- absolute imports of ``cProfile``, ``profile``, ``bdb``, ``pdb``,
  ``trace``, ``code``, ``codeop``, ``doctest``, ``marshal`` and
  ``multiprocessing.reduction``; the names in :data:`_STRING_CODE_NAMES` in
  any position (``shelve``, the unpicklers, ``sys.breakpointhook``, the
  annotation evaluators and ``singledispatch``/``singledispatchmethod``, a
  loader's ``get_code`` and its kin, with the standard library's re-exports
  such as ``doctest.pdb``); ``marshal``, ``code``, ``trace`` and ``profile``
  as an attribute or a name imported from a stdlib module; ``runpy`` as an
  attribute;
- ``pickle``, ``_pickle``, ``timeit`` and ``runpy`` by member allow-list:
  every use of a name an import of one binds (``from logging.handlers
  import pickle`` binds the module), and an attribute named ``pickle`` on
  any receiver, must read a listed member (``pickle.dumps``,
  ``timeit.default_timer``, ``runpy.run_path(p)`` called directly with one
  positional argument and only ``run_name``/``alter_sys``); anything else
  (``loads``, an alias, an argument, a star import, a class attribute)
  fires;
- a string annotation whose decoded value contains ``(`` or ``:=``, or that
  cannot be folded, and any mention of ``__annotations__`` other than a
  closed list of reads (``get_type_hints`` evaluates what is written there,
  and ``singledispatch.register`` calls it);
- a constant that is a dotted name naming any of the above, a generic
  module name (``"code"``) as the first of two or more dotted components
  when the second is that module's attribute or a dunder
  (``"timeit:timeit"``, not ``"code.py"``), and alone as the literal name of an acquisition
  (``import_module(name="code")``, ``sys.modules["code"]``,
  ``pkgutil.resolve_name("code")``, a ``logging.config`` ``"()"`` value).

The same classifier gives Tier 2 its ``evaluator`` cause (with PR 6's
full-lookup test of ``exec``/``eval``/``execfile`` kept,
:meth:`_Analysis.legacy_evaluator`), and any code-object name
(:data:`_CODE_OBJECT_NAMES`) its ``module-object`` cause. In a file that
imports or aliases the mock module, ``patch`` or a pytest-mock fixture, a
computed attribute read (``getattr`` by lookup, ``attrgetter``,
``methodcaller``, ``getattr_static``, ``__getattribute__`` with a name that
is not a constant, any of them handed on, ``inspect.getmembers``) makes
module-scope lookups dynamic (plan PY-5). The names ``gettext.install()`` and
``sys.displayhook`` put into ``builtins`` (:data:`INSTALLED_BUILTINS`) never
prove at module scope either (plan PY-4).

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

import re
import unicodedata
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from string import Template
from typing import Any

from . import allowlist, py_modules

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
# K-3 components of a ``__main__`` string (R-698-1): format and attribute
# punctuation and whitespace split a constant string, because a format field,
# key, attribute, conversion or spec (``"{0[__main__]}"``, ``"{:__main__}"``,
# ``"%(__main__)s"``, ``"$__main__ "``) reaches user code on its own wherever
# the template is later used. ``-`` and other characters stay inside a
# component; a default ``string.Template`` identifier is matched separately.
_MAIN_COMPONENTS = re.compile(r"[.:{}\[\]!()$%\s]")
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
# treesitter-chunker#699 B-1 (ruling R-699-1, reversing #705 Q2): the names
# above that hand over or rebuild a code object, a closure or a function
# over existing code. ``type(f)(code, globals)()`` runs a code object with
# neither ``exec`` nor ``eval``, so in Tier 2 any mention of one of them,
# reads included, is a run-wide ``module-object`` cause (Tier 1 already
# fails closed file-wide on every one of them).
_CODE_OBJECT_NAMES = frozenset(
    {
        "__closure__",
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
        "dis",
        "codeobj",
        "_get_code_object",
        "monitoring",
        "getstats",
        "_code",
        "code_linenos",
        "call_annotate_function",
        "call_evaluate_function",
        "__annotate__",
        "__annotate_func__",
    }
)
# treesitter-chunker#699 S2 (plan 699-702 PY-1, PY-2, PY-3, PY-8 and ruling
# R-699-1 B-2, B-4, B-5): code run from a string, a payload or an
# annotation. Every such trigger fails closed file-wide (``dynamic`` and
# ``frame_locals``): string code can reach a caller's frame and write its
# locals with no name spelled outside the string (PEP 667). In Tier 2 the
# same classifier gives a run-wide ``evaluator`` cause.
#
# Names that count in every position: an attribute, a keyword argument, a
# definition or import name, or a component of a constant string. They are
# the stdlib helpers that run a string as code (``cProfile``, ``bdb``,
# ``pdb``, ``doctest``, ``codeop``, ``logging.config.fileConfig``) with the
# re-exports a runtime scan of the CPython 3.14 standard library finds
# (``cProfile._pyprofile``, ``pdb.bdb``, ``traceback.codeop``,
# ``doctest.pdb``); the unpicklers (``shelve.Unpickler``, and
# ``multiprocessing``'s ``ForkingPickler.loads``, which is ``pickle.loads``,
# also bound as ``_ForkingPickler``); ``shelve`` and its shelves, which
# unpickle the values handed to them; ``sys.breakpointhook``, which reaches
# ``pdb``; the annotation evaluators; and the routes that load or build a
# code object (a loader's ``get_code``/``source_to_code``/``exec_module``/
# ``load_module``, reachable as ``__spec__.loader`` with no ``importlib``
# spelled, and ``pkgutil.read_code``).
_STRING_CODE_NAMES = frozenset(
    {
        "cProfile",
        "bdb",
        "pdb",
        "_pyprofile",
        "codeop",
        "doctest",
        "fileConfig",
        "Unpickler",
        "_Unpickler",
        "ForkingPickler",
        "_ForkingPickler",
        "shelve",
        "Shelf",
        "DbfilenameShelf",
        "BsdDbShelf",
        "breakpointhook",
        "__breakpointhook__",
        "get_type_hints",
        "eval_str",
        "ForwardRef",
        "evaluate_forward_ref",
        "_eval_type",
        "get_code",
        "source_to_code",
        "exec_module",
        "load_module",
        "read_code",
        # R-699-3 (BLOCKING 4): ``register`` evaluates every ``str``
        # annotation value through ``get_type_hints``, nested in a generic
        # (``List["..."]``) or bound to a name first, so the dispatchers
        # themselves are the unspelled annotation evaluators.
        "singledispatch",
        "singledispatchmethod",
    }
)
# An absolute import whose first component is one of these: the module, not
# a sibling (``from . import code`` never matches), whatever it is later
# called.
_STRING_CODE_MODULES = frozenset(
    {"cProfile", "profile", "bdb", "pdb", "trace", "code", "codeop", "doctest"}
)
# Import paths that reach an unpickler (``from multiprocessing import
# reduction``).
_STRING_CODE_PATHS = frozenset({("multiprocessing", "reduction")})
# ``marshal`` loads code objects. It counts as an absolute import, as an
# attribute on anything (``pstats.marshal``, ``zipimport.marshal``), as a
# constant-string component, and as a name imported from a standard-library
# module (``from pstats import marshal``); a third-party ``marshal`` function
# imported by name (``from flask_restful import marshal``) is not it. The
# generic module names below count the same way as a name imported from a
# standard-library module (R-699-3: ``from pdb import code``); a third-party
# ``trace`` or ``code`` (``from opentelemetry import trace``) is checked by
# :data:`_REEXPORT_CHECKED` instead (R-699-5).
_MARSHAL = "marshal"
# R-699-5 SHOULD 1: a from-import of ``code``, ``trace`` or ``profile`` out of
# a module that is not in the standard library, relative imports included
# (``from compat import code``, ``from .compat import profile``, ``from
# opentelemetry import trace``), may re-export the stdlib module. Its uses are
# checked against a closed allow-list: each must read an attribute absent
# from that module's pinned table (:data:`_GENERIC_MODULE_ATTRIBUTES`) and
# not a dunder (``trace.get_tracer(...)`` stays inert). An attribute read in
# the table, passing the name on, an alias, a computed ``getattr`` or a
# subscript fires (:meth:`_Analysis._safe_module_use`).
_REEXPORT_CHECKED = frozenset({"code", "trace", "profile"})
# The names an absolute import counts as standard library for the S2
# classifier: :data:`py_modules.STDLIB_MODULES` and ``test``, CPython's own
# test package, which ``sys.stdlib_module_names`` leaves out and many builds
# do not ship (R-699-5 NIT: ``from test.test_profile import profile``). Tier 2
# module resolution keeps the shared table, so a project ``test`` package
# still resolves there.
_S2_STDLIB_MODULES = py_modules.STDLIB_MODULES | {"test"}
# Modules whose uses are checked against a member allow-list at the use site
# (plan mechanism 2): every use of a name an import of one binds must read a
# listed member. ``pickle``'s dump side and constants; ``timeit``'s clock;
# ``runpy``'s two runners, called directly with one positional argument and
# only the ``run_name``/``alter_sys`` keywords (the second positional
# parameter is ``init_globals``, which pre-seeds a second instance of the
# module).
_PICKLE_SAFE = frozenset(
    {
        "dumps",
        "dump",
        "Pickler",
        "PickleBuffer",
        "HIGHEST_PROTOCOL",
        "DEFAULT_PROTOCOL",
        "PickleError",
        "PicklingError",
        "UnpicklingError",
    }
)
_RUNPY_RUNNERS = frozenset({"run_path", "run_module"})
_RUNPY_KEYWORDS = frozenset({"run_name", "alter_sys"})
# treesitter-chunker#699 PY-7 (ruling R-699-1 Q2, reversing the #695
# re-check's "no trigger for ``gc``"): ``gc`` walks the heap, so
# ``gc.get_referents(f)`` hands over a function's globals dict, code object
# and closure cells, ``gc.get_referrers(x)`` the dicts and frames that hold
# ``x``, ``gc.get_objects()`` every tracked object and ``gc.garbage`` what
# ``DEBUG_SAVEALL`` keeps alive. Only the collector's controls and counters
# are on the list; ``callbacks`` is off with them. Every member of ``gc`` on
# CPython 3.14 is in exactly one of the two sets (pinned against ``dir(gc)``).
_GC = "gc"
_GC_SAFE = frozenset(
    {
        "collect",
        "enable",
        "disable",
        "isenabled",
        "freeze",
        "unfreeze",
        "get_freeze_count",
        "get_count",
        "get_threshold",
        "set_threshold",
        "get_stats",
        "get_debug",
        "set_debug",
        "is_tracked",
        "is_finalized",
        "DEBUG_COLLECTABLE",
        "DEBUG_LEAK",
        "DEBUG_SAVEALL",
        "DEBUG_STATS",
        "DEBUG_UNCOLLECTABLE",
    }
)
_GC_UNSAFE = frozenset(
    {"get_referents", "get_referrers", "get_objects", "garbage", "callbacks"}
)
# The heap walkers count as tokens in every position (an identifier,
# attribute, import or keyword name, or a constant-string component; the
# R-724-1 token rule): ``from compat import get_referents``,
# ``getattr(g, "get_referrers")``, ``attrgetter("gc.get_objects")``.
_GC_WALKERS = frozenset({"get_referents", "get_referrers", "get_objects"})
_CHECKED_MODULES: Mapping[str, frozenset[str]] = {
    "pickle": _PICKLE_SAFE,
    "_pickle": _PICKLE_SAFE,
    "timeit": frozenset({"default_timer"}),
    "runpy": _RUNPY_RUNNERS,
    _GC: _GC_SAFE,
}
_RUNPY = "runpy"
# An attribute named ``pickle`` on any receiver is the module
# (``trace.pickle``, ``logging.handlers.pickle``,
# ``multiprocessing.reduction.pickle``): its use is checked like the module's.
# An attribute named ``runpy`` (``multiprocessing.spawn.runpy``) fails closed.
# A from-import of a checked module's name out of any other module (R-699-3,
# BLOCKING 2: ``from logging.handlers import pickle as pk``, ``from
# multiprocessing.spawn import runpy``) binds the module itself, and its uses
# are checked like those of ``import pickle as pk``.
_PICKLE_ATTRIBUTES = frozenset({"pickle", "_pickle"})
# Constant strings naming a checked module (``getattr(trace, "pickle")``,
# ``importlib.import_module("runpy")``) fail closed. The generic module names
# are ordinary words (``d["code"]``), so alone they fail closed only as the
# literal module name of an acquisition: any constant among the arguments
# of ``import_module`` or ``__import__``, at any depth (R-699-6: the
# ``package`` argument and the ``globals`` dict name the module when the
# name after the dots is empty), the key of
# ``X.modules[...]`` / ``X.modules.get(...)`` (also ``pop``, ``setdefault``,
# ``__getitem__``), the first argument or ``name=`` keyword of a string
# resolver (``pkgutil.resolve_name``, ``pydoc.locate``/``safeimport``), or
# the value of a ``logging.config`` factory key ``"()"``. As the first
# component of a dotted constant with two or more components
# (``"code.InteractiveInterpreter"``, ``"timeit:timeit"``) they fail closed
# anywhere (R-699-3, BLOCKING 3) when the second component is an attribute of
# that module (:data:`_GENERIC_MODULE_ATTRIBUTES`) or a dunder: none of the
# four is a package, so a resolver, ``import_module``, a factory key or
# ``patch`` given ``"code.py"``, ``"trace.log"`` or ``"code:fixture"``
# reaches no object of the module and runs none of its code. A name stored
# first and passed later is a computed acquisition (plan R12, class (b)).
_MODULE_STRINGS = frozenset({"pickle", "_pickle", "runpy"})
_GENERIC_MODULE_STRINGS = frozenset({"code", "trace", "profile", "timeit"})
# Every non-dunder attribute of the four modules on CPython 3.12, 3.13 and
# 3.14 (``dir()``; pinned against the running interpreter), less
# ``timeit.default_timer``, which is on ``timeit``'s member allow-list.
# CPython 3.15 adds ``profile.warnings`` and ``timeit.default_target_time``
# (R-699-5 SHOULD 2): the first is the ``warnings`` module, the second an
# integer, and reading either runs no code, so leaving them out is
# harmless. The pin test reports them once the project tests on 3.15.
_GENERIC_MODULE_ATTRIBUTES: Mapping[str, frozenset[str]] = {
    "code": frozenset(
        {
            "CommandCompiler",
            "InteractiveConsole",
            "InteractiveInterpreter",
            "Quitter",
            "builtins",
            "compile_command",
            "interact",
            "sys",
            "traceback",
        }
    ),
    "profile": frozenset(
        {
            "Profile",
            "_Utils",
            "importlib",
            "io",
            "main",
            "marshal",
            "run",
            "runctx",
            "sys",
            "time",
        }
    ),
    "timeit": frozenset(
        {
            "Timer",
            "_globals",
            "default_number",
            "default_repeat",
            "dummy_src_name",
            "gc",
            "itertools",
            "main",
            "reindent",
            "repeat",
            "sys",
            "template",
            "time",
            "timeit",
        }
    ),
    "trace": frozenset(
        {
            "CoverageResults",
            "PRAGMA_NOCOVER",
            "Trace",
            "_Ignore",
            "_find_executable_linenos",
            "_find_lines",
            "_find_lines_from_code",
            "_find_strings",
            "_fullmodname",
            "_modname",
            "_time",
            "dis",
            "gc",
            "inspect",
            "io",
            "linecache",
            "main",
            "os",
            "pickle",
            "sys",
            "sysconfig",
            "threading",
            "token",
            "tokenize",
        }
    ),
}
_ACQUIRERS = frozenset({"import_module", "__import__"})
_STRING_RESOLVERS = frozenset({"resolve_name", "locate", "safeimport"})
_FACTORY_KEY = "()"
_NAME_KEYWORD = "name"
# An entry point names its object by a constant ``module:attr [extras]``
# that ``.load()`` imports (R-699-5, BLOCKING 2): ``importlib.metadata``'s
# ``EntryPoint(name, value, group)`` and ``pkg_resources``'
# ``EntryPoint(name, module_name, ...)`` (the second positional argument or
# these keywords), and ``EntryPoint.parse("n = module:attr")``.
_ENTRY_POINT = "EntryPoint"
_ENTRY_POINT_KEYWORDS = frozenset({"value", "module_name"})
_ENTRY_POINT_PARSE = "parse"
_ENTRY_POINT_PARSE_KEYWORDS = frozenset({"src"})
# In an acquisition position a constant is split on every character that
# cannot be part of an identifier (R-699-5, BLOCKING 2): ``.``, ``:``, ``/``,
# whitespace, the ``ext://`` prefix of a ``logging.config`` value and an
# entry point's ``[extras]``. Resolvers drop empty parts (``"timeit..x"``,
# ``".timeit.x"``) and strip whitespace (``"timeit : timeit"``), and
# ``pkgutil.resolve_name``'s pattern accepts a trailing newline, so any
# string-code module name among the parts fires.
# The same word boundaries apply to frame, heap and namespace tokens.
_TOKEN_WORDS = re.compile(r"[^A-Za-z0-9_]+")
_ACQUIRED_MODULES = (
    _GENERIC_MODULE_STRINGS
    | _MODULE_STRINGS
    | _STRING_CODE_MODULES
    | _STRING_CODE_NAMES
    | {_MARSHAL}
)
_DOTTED_SPLIT = re.compile(r"[.:]")
# Components of a constant string for the token rules (R-724-1, R-707-1): a
# dotted, ``:`` or bracket path (``"gc.get_objects"``, ``"d[f_locals]"``).
_TOKEN_PARTS = re.compile(r"[.:\[\]]")
# A constant that is a dotted name (``.`` or ``:`` between identifiers).
_DOTTED_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:[.:][A-Za-z_][A-Za-z0-9_]*)*")
# Builtins that run source, build a code object or reach ``pdb``. A use is
# the builtin unless the ordinary lookup at the use site proves the file's
# own binding and it dominates the use (fold 25, R-699-3 BLOCKING 1): a
# binding in a function scope, including an import from a module other than
# ``builtins``. No module or class binding does, since a use may run before
# it (``compile = compile``, ``(compile := compile)``, ``from re import
# compile``). A phantom binding (:class:`_Binding`) is no proof: one real
# binding of the name in the deciding scope is needed (R-699-5). As
# an attribute or a constant string they count only in a file that reaches
# the builtins namespace (``builtins.exec``, ``len.__self__.eval``,
# ``f.f_builtins["compile"]``, ``inspect.getmodule(len).exec``); no other
# stdlib module exposes them (runtime scan, CPython 3.14), ``model.eval()``
# is not one, and neither is ``re.compile`` on a receiver the ordinary
# lookup proves is an import of ``re``.
_CODE_BUILTINS = frozenset({"exec", "eval", "execfile", "compile", "breakpoint"})
_BUILTIN_MODULES = frozenset({"builtins", "__builtin__"})
_BUILTINS_REACH = frozenset(
    {
        "builtins",
        "__builtins__",
        "__builtin__",
        "bltns",
        "__self__",
        "f_builtins",
        "getmodule",
    }
)
# The builtins whose prior Tier 2 ``evaluator`` cause (PR 6) every later
# classifier must keep: the full lookup with the frame and annotation rules
# (R-699-3, the two cause-preservation regressions).
_LEGACY_EVALUATORS = frozenset({"exec", "eval", "execfile"})
_RE_MODULE = "re"
# A function's annotations dict: a string written into it is evaluated
# against the function's globals by ``typing.get_type_hints``, which
# ``functools.singledispatch.register`` calls internally (B-5). Only a closed
# list of reads is exempt.
_ANNOTATIONS = "__annotations__"
# Plan PY-5 (Z-4): in a file that imports or aliases the mock module,
# ``patch`` or a pytest-mock fixture, a computed attribute read can return
# the file's own ``patch``. These getters fail closed with a name argument
# that is not a constant string, or handed on uncalled; ``getmembers`` hands
# over every attribute.
_COMPUTED_GETTERS = frozenset(
    {"attrgetter", "methodcaller", "getattr_static", "__getattribute__"}
)
_MEMBER_LISTERS = frozenset({"getmembers", "getmembers_static"})
_OWN_BINDING_REASONS = frozenset({PARAMETER, LOCAL, "expression-bound"})
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
# Names the standard library puts into ``builtins`` at run time (plan PY-4):
# ``gettext.install()`` and ``NullTranslations.install()`` accept only these,
# and ``sys.displayhook`` writes ``builtins._``. Kept apart so the
# ``dir(builtins)`` pin stays exact. A module-level definition of one never
# proves either (``builtin-shadow``).
INSTALLED_BUILTINS = frozenset({"_", "gettext", "ngettext", "pgettext", "npgettext"})
SHADOWED_NAMES = BUILTINS | INSTALLED_BUILTINS
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
# treesitter-chunker#699 R-699-12 item 1 (after R-699-10 and R-699-11):
# ``unittest.mock``'s private patchers and the target resolver they share are
# patcher tokens in ANY role, in both tiers: an identifier (a name, an
# attribute on any receiver, an import or alias name, a keyword, a
# class-pattern keyword, a definition), or a word of any constant string
# (``getattr(mk, '_pa' 'tch')``, a mapping-pattern key, an f-string). They
# apply a patch, or hand out the target module (``_get_target`` returns
# ``partial(pkgutil.resolve_name, ...)``), with no public name spelled, and
# they are rare enough that no position needs to be told apart.
_PRIVATE_PATCH_TOKENS = frozenset(
    {"_patch", "_patch_multiple", "_patch_object", "_patch_dict", "_get_target"}
)
# R-699-12 item 2: a constant string exactly ``"patch"`` in any position
# (an argument, a list or tuple element, ``__match_args__``, a mapping-pattern
# key, a comparison operand) names the patcher by string; in the member-naming
# positions (``py_modules._argument_string``) a dotted component counts too.
_PATCH = "patch"
# Builtins that hand over the calling frame's locals as a dict (#707):
# ``locals()``, and ``vars()`` with no argument. Called in a function, they
# make every local of that frame reachable by a computed read, the way
# ``globals()`` reaches every module-scope binding.
_LOCALS_READERS = frozenset({"locals", "vars"})
# The sensitive kinds one alias/readback/escape mechanism tracks (#695 fold
# 22): a namespace dict, the mock module, ``patch`` and a pytest-mock fixture.
_NS, _MOCK, _MOCKER = "namespace", "mock", "mocker"
_KINDS = (_NS, _MOCK, _PATCH, _MOCKER)
# THE CLOSED ALLOW-LIST of safe uses of a sensitive value (#695 fold 23,
# executive ruling E-21 A-1). Every use not listed here fails closed (A-2).
# A namespace dict: pure reads whose result cannot reach the namespace (a
# value by constant key, which the alias sets and the dynamic-attribute
# literals gate), and recognized writes with constant keys or literal
# mappings, used only as expression statements. ``values()`` and ``items()``
# are off the list: they hand over every value, the file's own ``patch`` or
# mock module among them (fold 24, Y-6). So is ``keys()``: a keys view's
# ``.mapping`` is a proxy of the namespace itself (fold 27, Codex
# 4657978945).
_NS_READS = frozenset({"get"})
_NS_WRITES = frozenset({"update", "setdefault", "pop"})
# The mock module's constructors and constants.
_MOCK_SAFE = frozenset(
    {
        "Mock",
        "MagicMock",
        "AsyncMock",
        "NonCallableMock",
        "PropertyMock",
        "call",
        "ANY",
        "sentinel",
        "DEFAULT",
        "create_autospec",
        "mock_open",
        "seal",
    }
)
# A pytest-mock fixture's non-patch public helpers.
_MOCKER_SAFE = frozenset({"spy", "stub", "Mock", "MagicMock", "resetall", "stopall"})
# ``patch``'s methods (called, with W-3 semantics).
_PATCH_SAFE = frozenset(_PATCH_METHODS)
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
    # A binding the scope pass records only to fail closed, which CPython
    # 3.14 does not make (R-699-5, BLOCKING 1): the Python 2 list
    # comprehension leak, the ``B`` of ``except A, B:`` (a second exception
    # class under PEP 758, so a read) and every identifier of a type-parameter
    # list (a bound such as ``T: exec`` reads ``exec``). It shadows like any
    # binding, but never proves that a builtin's or a checked module's name
    # is the file's own: that needs a real binding in the deciding scope.
    phantom: bool = False


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
        # K-3 (#698, R-698-2): a string in the file names the main module and
        # is not the script guard's comparand. Tier 1 makes the file dynamic;
        # Tier 2 reads the same verdict as a run-wide ``module-object`` cause,
        # so both tiers use one classifier (:func:`_main_string`).
        self.main_string = False
        self.star = False
        # Names written as an attribute or constant key of any receiver.
        self.attribute_writes: set[str] = set()
        # Tier 2 (plan 9.4, PR 6): the attribute nodes written as targets
        # (``svc.t = f``, ``del svc.t``), and the scope the last lookup
        # decided in (a group of imports there narrows in ``imports`` mode).
        self.attribute_targets: set[int] = set()
        self.decided: _Scope | None = None
        # Module-scope writes made by submodule imports in ``__init__.py``,
        # counted per name (#705 E6-3: a package's own submodule import).
        self.submodule_writes: dict[str, int] = {}
        # Subscript targets (``x[k] = v``, ``del x[k]``), checked once the
        # namespace aliases are known (#695 fold 18).
        self.subscript_targets: list[Any] = []
        # A ``__dict__`` attribute or constant string appears in the file, and
        # an ``operator`` writer is handed on (fold 18 rule 3).
        self.namespace_seen = False
        self.operator_escape = False
        # Fold 21: a constant ``"patch"`` string, and the mock-module and
        # pytest-mock names found by alias propagation (B-5).
        self.patch_string_seen = False
        self.mock_string_seen = False
        self.mock_imported = False
        # Fold 22: one alias set per sensitive kind; ``namespace_aliases`` is
        # the namespace kind's.
        self.aliases: dict[str, set[str]] = {kind: set() for kind in _KINDS}
        self.namespace_aliases = self.aliases[_NS]
        self.mock_import_names: set[str] = set()
        self.patch_import_names: set[str] = set()
        # Fold 25: every identifier, binding sites by name, and the names an
        # allow-listed callee relies on being the builtin or stdlib object.
        self.identifier_nodes: list[Any] = []
        self.binding_sites: dict[str, list[Any]] | None = None
        self.relied_names: set[str] = set()
        # Fold 28: each verified callee, checked once the scopes are complete
        # by the ordinary lookup at its use site (module ``None`` for a
        # builtin).
        self.verifications: list[tuple[Any, str | None, frozenset[str] | None]] = []
        # treesitter-chunker#699 S2: the string-code and code-object
        # classifier, shared by both tiers. ``string_code`` holds the rule
        # groups that fired (Tier 1 fails closed file-wide; Tier 2 records an
        # ``evaluator`` cause); ``code_objects`` is set by any code-object
        # name (Tier 2 ``module-object``). The use-site checks run once the
        # scopes are complete (:meth:`_verify_string_code`).
        self.string_code: set[str] = set()
        # A fresh-module handout proof checks the exec/exec_module use itself.
        # Every independent file-wide hazard must still block its local lookup.
        self.namespace_receiver_blocked = False
        self.code_objects = False
        # treesitter-chunker#699 PY-7: a use of ``gc`` off its member list or
        # a heap-walker token (Tier 1 fails closed file-wide; Tier 2 records
        # a ``module-object`` cause, B-7).
        self.heap_walk = False
        self.builtins_reach = False
        self.string_checks: list[tuple[str, Any]] = []
        self.checked_bindings: dict[str, list[Mapping[str, str]]] = {}
        # The scope the last :meth:`_use_lookup` decided in.
        self.use_decided: _Scope | None = None
        # Plan PY-5 (module scope only), applied with the S2 flags.
        self.computed_getter = False
        # #707: the spellings that may read a function's locals as a dict
        # (``locals()``, ``vars()``), each with whether only the use-site
        # lookup can tell it from the builtin; the bare-name ones the rules
        # relied on not being the builtin, checked once the scopes are
        # complete; and whether they are.
        self.locals_readers: list[tuple[Any, bool]] | None = None
        self.reader_checks: list[Any] = []
        self.complete = False
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
        self.complete = True
        self._verify_string_code()
        self._verify_callees()

    def _verify_callees(self) -> None:
        """Verify every allow-listed callee by the ordinary lookup at its use
        site (#695 fold 28, Codex 4658232413): a builtin must look up as
        ``none(unbound)`` (bound nowhere on the path, no open class
        namespace, no dynamic scope, no star import, no builtin shadow, no
        recorded write); a stdlib name must look up as its tracked import.
        Anything else makes the use off the list (A-2): fail closed."""
        for node, module, members in self.verifications:
            result = self.lookup(node)
            if module is None:
                verified = result == {"outcome": "none", "reason": "unbound"}
            else:
                binding = (
                    result.get("binding") or {}
                    if result.get("outcome") == "import"
                    else {}
                )
                verified = binding.get("module") == module and (
                    binding.get("form") == "import"
                    if members is None
                    else binding.get("form") == "from"
                    and binding.get("name") in members
                )
            if not verified:
                self.dynamic = True
                return
        for reader in self.reader_checks:
            # #707: a bare ``locals``/``vars`` the rules took for a non-builtin
            # must look up as a proven local definition.
            if self._may_read_locals(reader):
                self.dynamic = True
                return

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
            self.events.append(
                (scope, mangled, _Binding(LOCAL, phantom=binding.phantom))
            )

    def _attribute_write(self, node: Any) -> None:
        if node.type == "attribute":
            self.attribute_targets.add(node.id)
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

    def _targets(
        self,
        node: Any,
        scope: _Scope,
        depth: int,
        cls: str = LOCAL,
        phantom: bool = False,
    ) -> None:
        """Bind every name a target writes; fail closed on unknown forms.
        ``phantom`` marks bindings CPython does not make (:class:`_Binding`)."""
        if depth > MAX_DEPTH:
            msg = "Python scope analysis exceeds safe traversal depth"
            raise RecursionError(msg)
        kind = node.type
        if kind == "identifier":
            self._record(scope, node, _Binding(cls, phantom=phantom))
        elif kind in _TARGET_CONTAINERS:
            for child in node.named_children:
                self._targets(child, scope, depth + 1, cls, phantom)
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
        # binding can only fail closed. Only a parameter's own name is a
        # binding CPython makes; a bound, a constraint or a default is read,
        # so its identifiers are phantom (R-699-5).
        names = {ident.id for ident in _type_parameter_names(params)}
        for ident in _identifiers(params):
            self._record(
                inner, ident, _Binding(PARAMETER, phantom=ident.id not in names)
            )
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
                        # the extra binding can only fail closed. CPython 3
                        # does not make it, so it is phantom (R-699-5).
                        self._targets(part, scope, depth + 1, phantom=True)
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
                # Python 2 ``except E, e:`` binds ``e``. On 3.14 the form is
                # PEP 758's ``except (E, e):``, a read, so it is phantom.
                self._targets(child, scope, depth + 1, phantom=True)
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
                    self.submodule_writes[path[index]] = (
                        self.submodule_writes.get(path[index], 0) + 1
                    )
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
            parts = _dotted_parts(module, self.source) if module else []
            text = ".".join(parts)
            # ``bound``: the module the bound name denotes (Tier 2, 9.4):
            # ``import a.b`` binds ``a`` to module ``a``, ``import a.b as m``
            # binds ``m`` to module ``a.b``.
            denotes = text if child.type == "aliased_import" else ".".join(parts[:1])
            self._import_binding(
                scope,
                node,
                bound,
                {"form": "import", "module": text, "bound": denotes},
            )

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
        self._fire("builtin")  # string code (#699 PY-8)
        self._children(node, scope, depth)

    # -- dynamic binding ----------------------------------------------------

    def _scan_dynamic(self) -> None:
        """Set ``dynamic`` if the file may bind module names at run time, and
        ``frame_locals`` if it may write a function's locals."""
        source = self.source
        sys_names = {_SYS}
        main_names = set(_MAIN_NAMES)
        main_strings: list[tuple[Any, str]] = []
        identifiers: list[Any] = []
        # Fold 18: calls, attributes, ``|=`` statements and namespace aliases,
        # classified once every alias is known.
        calls: list[Any] = []
        attributes: list[Any] = []
        augmented: list[Any] = []
        bindings: list[tuple[Any, Any]] = []
        matches: list[Any] = []
        subscripts: list[Any] = []
        operator_names = set(_OPERATOR_WRITERS)
        # Fold 19 (W-3): names bound to ``unittest.mock``/``mock`` and to
        # ``patch``.
        mock_names: set[str] = set()
        patch_names: set[str] = set()
        # Fold 21 (E-20): names bound to ``pydoc`` and ``logging.config``.
        pydoc_names: set[str] = set()
        logging_config_names: set[str] = set()
        strings: list[Any] = []
        imports: list[Any] = []
        stack = [self.root]
        while stack:
            node = stack.pop()
            kind = node.type
            if kind in ("string", "concatenated_string", "binary_operator"):
                strings.append(node)
            elif kind in ("import_statement", "import_from_statement"):
                imports.append(node)
            if kind == "attribute":
                attributes.append(node)
                attribute = node.child_by_field_name("attribute")
                if attribute is not None and _NAMESPACE_DICT in _spellings(
                    attribute, source
                ):
                    self.namespace_seen = True
            elif kind == "match_statement":
                matches.append(node)
            elif kind in ("for_statement", "for_in_clause"):
                # ``for mm in (mocker,)``: an alias binding (fold 22).
                left = node.child_by_field_name("left")
                right = node.child_by_field_name("right")
                if left is not None and right is not None:
                    bindings.append((_unwrap(left, skip_comments=True), right))
            elif kind == "with_item":
                value = node.child_by_field_name("value")
                if value is not None and value.type == "as_pattern":
                    alias = value.child_by_field_name("alias")
                    inner = value.named_children[0] if value.named_children else None
                    if alias is not None and inner is not None:
                        bindings.append((alias, inner))
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
                    if self._names_own_module(value):
                        # Any constant string naming this module, alone or as
                        # a component of a dotted path (``getattr(pkg, "a")``,
                        # ``pkg.__dict__["a"]``, ``NAME = "a"``; N-3).
                        self.dynamic = True
                main_kind = _main_string(node, source, value)
                if main_kind is not None:
                    # ``"__main__"`` names this module by string when the
                    # file runs as a script (``mock.patch("__main__.f")``,
                    # ``pydoc.locate("__main__")``,
                    # ``pkgutil.resolve_name("__main__:__dict__")``; #695
                    # K-3). Decided after the scan, once every attribute
                    # write is known (see :meth:`_main_guard`).
                    main_strings.append((node, main_kind))
            elif kind in ("subscript", "call"):
                if kind == "subscript":
                    subscripts.append(node)
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
                            self.mock_imported = True
                if not dots and module_parts in (["unittest", "mock"], ["mock"]):
                    # ``from unittest.mock import patch as p``.
                    self.mock_imported = True
                if kind == "import_from_statement":
                    # treesitter-chunker#699 R-699-10 item 2: an import name
                    # spelled ``patch`` is a patcher whatever module it comes
                    # from and whatever alias it takes (``from compat import
                    # patch as pp``, ``@patch(...)`` from a re-exporting
                    # module). Its bound name joins the ``patch`` alias set,
                    # so W-3 and the closed allow-list check every use, in
                    # Tier 1 and, through :meth:`_sensitive`, in Tier 2. The
                    # private patchers are tokens in any role (R-699-12).
                    for last, bound in _from_import_names(node, source):
                        if last == _PATCH:
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
                        if parts in (["mock"], ["unittest", "mock"]):
                            self.mock_imported = True
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
        for node, main_kind in main_strings:
            if main_kind == _MAIN_INTERPOLATED or not self._main_guard(node):
                self.main_string = True
        if self.main_string:
            self.dynamic = True
        self.mock_import_names = mock_names
        self.patch_import_names = patch_names
        self.identifier_nodes = identifiers
        self._sensitive_rules(
            calls,
            attributes,
            identifiers,
            subscripts,
            bindings,
            matches,
        )
        self._namespace_rules(calls, attributes, augmented, operator_names)
        self._resolver_rules(attributes, identifiers, pydoc_names, logging_config_names)
        self._mock_rules(
            calls, attributes, identifiers, bindings, mock_names, patch_names
        )
        if self.relied_names & self.attribute_writes:
            # A recorded write of a name an allow-listed callee relies on
            # (``mod.len = f``, ``ns["dict"] = C``) rebinds it (fold 25).
            self.dynamic = True
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
            if spellings & _PRIVATE_PATCH_TOKENS:
                self.dynamic = True  # R-699-12 item 1, any role
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
        self._string_code_rules(identifiers, strings, imports, attributes)

    # -- string code and code objects (treesitter-chunker#699 S2) -----------

    def _fire(self, group: str, *, namespace_candidate: bool = False) -> None:
        self.string_code.add(group)
        if not namespace_candidate:
            self.namespace_receiver_blocked = True

    def _string_code_rules(
        self,
        identifiers: list[Any],
        strings: list[Any],
        imports: list[Any],
        attributes: list[Any],
    ) -> None:
        """The syntactic half of the string-code and code-object classifier
        (#699 S2): names in any position, imports, constant strings and
        annotation strings fire at once; every use the ordinary lookup must
        decide is queued for :meth:`_verify_string_code`."""
        source = self.source
        checked = self.checked_bindings = self._checked_bindings()
        mock_file = any(
            self._kind_present(kind, attributes, identifiers) or self.aliases[kind]
            for kind in (_MOCK, _PATCH, _MOCKER)
        )
        builtin_mentions: list[str] = []
        getattr_attribute = False
        for ident in identifiers:
            spellings = _spellings(ident, source)
            if spellings & _BUILTINS_REACH or self._computed_acquisition(ident):
                self.builtins_reach = True
            if spellings & _STRING_CODE_NAMES:
                self._fire("name", namespace_candidate=spellings == {"exec_module"})
            if spellings & _CODE_OBJECT_NAMES:
                self.code_objects = True
            if spellings & _GC_WALKERS:
                self.heap_walk = True  # PY-7, token level
            if _ANNOTATIONS in spellings and not self._attribute_read(ident):
                self._fire("annotations")
            name = _text(ident, source)
            parent = ident.parent
            attribute_name = (
                parent is not None
                and parent.type == "attribute"
                and _same(ident, parent.child_by_field_name("attribute"))
            )
            if attribute_name:
                if name == "compile":
                    # ``builtins.compile``, unless ``re.compile`` on a proven
                    # ``re`` import (R-699-3 cost NIT).
                    self.string_checks.append(("attribute:compile", parent))
                elif name in _CODE_BUILTINS:
                    builtin_mentions.append(name)  # ``builtins.exec``
                elif name == _RUNPY:
                    self._fire("runpy")  # ``multiprocessing.spawn.runpy``
                elif name == _MARSHAL:
                    self._fire("marshal")  # ``pstats.marshal``
                elif name in _PICKLE_ATTRIBUTES:
                    if parent.id not in self.attribute_targets:
                        self.string_checks.append(("module:pickle", parent))
                elif name == _GC:
                    # ``timeit.gc``, ``trace.gc``, ``X.gc`` for any ``X``: the
                    # module's member list applies (PY-7).
                    if parent.id not in self.attribute_targets:
                        self.string_checks.append(("module:gc", parent))
                elif mock_file and name == "getattr":
                    getattr_attribute = True  # ``builtins.getattr``
                if mock_file and name in _COMPUTED_GETTERS:
                    self._computed_getter(parent, name)
            elif _name_part(ident) or _binding_position(ident):
                pass
            elif name in _CODE_BUILTINS:
                self.string_checks.append(("builtin", ident))
            elif mock_file and name == "getattr":
                self.string_checks.append(("getattr", ident))
            elif mock_file and name in _COMPUTED_GETTERS:
                self._computed_getter(ident, name)
            elif spellings & checked.keys():
                self.string_checks.append(("checked", ident))
            if mock_file and spellings & _MEMBER_LISTERS:
                self.computed_getter = True  # PY-5: ``inspect.getmembers(m)``
        for node in imports:
            self._string_code_import(node, mock_file)
        for node in strings:
            self._string_code_literal(node, builtin_mentions)
        if builtin_mentions and self.builtins_reach:
            self._fire("builtin")
        if getattr_attribute and self.builtins_reach:
            self.computed_getter = True

    def _computed_acquisition(self, ident: Any) -> bool:
        """Whether ``ident`` acquires a module by a name that is not a
        constant string, so the module may be ``builtins``
        (``importlib.import_module(len.__module__).exec``,
        ``sys.modules[int.__module__].exec``; R-699-3): ``import_module`` or
        ``__import__`` handed on or called with a computed first argument or
        ``name=`` keyword, or ``X.modules`` subscripted or read with a
        getter by a computed key other than ``__name__``."""
        name = _text(ident, self.source)
        parent = ident.parent
        attribute = (
            parent is not None
            and parent.type == "attribute"
            and _same(ident, parent.child_by_field_name("attribute"))
        )
        if name in _ACQUIRERS:
            if _binding_position(ident) or (_name_part(ident) and not attribute):
                return False
            call = _callee_call(parent if attribute else ident)
            if call is None:
                return True  # handed on
            arguments = _call_arguments(call)
            first = next(
                (
                    argument
                    for argument in arguments
                    if argument.type not in ("keyword_argument", "comment")
                ),
                None,
            )
            if first is None:
                first = next(
                    (
                        argument.child_by_field_name("value")
                        for argument in arguments
                        if argument.type == "keyword_argument"
                        and _text(argument.child_by_field_name("name"), self.source)
                        == _NAME_KEYWORD
                    ),
                    None,
                )
            return first is None or _constant_string(first, self.source) is None
        if name != _SYS_MODULES or not attribute:
            return False
        outer = parent
        while (
            outer.parent is not None and outer.parent.type == "parenthesized_expression"
        ):
            outer = outer.parent
        above = outer.parent
        key = None
        if above is not None and above.type == "subscript":
            if _same(above.child_by_field_name("value"), outer):
                key = above.child_by_field_name("subscript")
        elif above is not None and above.type == "attribute":
            method = above.child_by_field_name("attribute")
            call = _callee_call(above)
            if (
                method is not None
                and _text(method, self.source) in _MODULE_GETTERS
                and call is not None
            ):
                arguments = _call_arguments(call)
                key = arguments[0] if arguments else None
        if key is None:
            return False
        key = _unwrap(key, skip_comments=True)
        if key.type == "identifier" and _text(key, self.source) == "__name__":
            return False
        return _constant_string(key, self.source) is None

    def _checked_bindings(self) -> dict[str, list[Mapping[str, str]]]:
        """Every name an import of a checked module (``pickle``, ``timeit``,
        ``runpy``) binds, with its import records. A from-import of a member
        off the module's list, and a binding no use rule sees (a class
        attribute, a ``global`` or ``nonlocal`` redirect), fail closed at
        once."""
        found: dict[str, list[Mapping[str, str]]] = {}
        for scope, name, binding in self.events:
            info = binding.info
            if binding.cls != IMPORT or not info:
                continue
            target = _checked_import(info)
            if target is None:
                continue
            module, member = target
            if member is not None and member not in _CHECKED_MODULES[module]:
                self._fire_checked(module)  # ``from pickle import loads``
                continue
            hidden = (
                scope.kind == _CLASS or name in scope.globals or name in scope.nonlocals
            )
            if hidden and (member is None or module == _RUNPY):
                self._fire_checked(module)  # ``class K: import pickle as pk``
                continue
            found.setdefault(name, []).append(info)
        return found

    def _string_code_import(self, node: Any, mock_file: bool) -> None:
        """Absolute imports of a string-code module (whatever the name is
        later called), of ``multiprocessing.reduction``, of a code builtin
        from ``builtins``, a star import from a checked module, and in a mock
        file an aliased import of a computed getter."""
        source = self.source
        if node.type == "import_statement":
            for child in node.named_children:
                imported = (
                    child.child_by_field_name("name")
                    if child.type == "aliased_import"
                    else child
                )
                parts = _dotted_parts(imported, source) if imported else []
                if parts[:1] and (
                    parts[0] in _STRING_CODE_MODULES | {_MARSHAL}
                    or tuple(parts[:2]) in _STRING_CODE_PATHS
                ):
                    self._fire("import")
            return
        dots, parts = _module_parts(node, source)
        if dots or not parts:
            return
        if parts[0] in _STRING_CODE_MODULES | {_MARSHAL}:
            self._fire("import")
            return
        module = ".".join(parts)
        stdlib = parts[0] in _S2_STDLIB_MODULES
        if module in _CHECKED_MODULES and any(
            child.type == "wildcard_import" for child in node.children
        ):
            self._fire_checked(module)  # ``from pickle import *``
        for last, bound in _from_import_names(node, source):
            if tuple([*parts, *last.split(".")][:2]) in _STRING_CODE_PATHS:
                self._fire("import")
            if stdlib and last == _MARSHAL:
                self._fire("marshal")  # ``from pstats import marshal``
            if stdlib and last in _STRING_CODE_MODULES:
                self._fire("import")  # ``from pdb import code`` (R-699-3)
            if module in _BUILTIN_MODULES and last in _CODE_BUILTINS:
                self._fire("builtin")  # ``from builtins import exec as run``
            if (
                mock_file
                and last in _COMPUTED_GETTERS
                and bound.type == "identifier"
                and _text(bound, source) != last
            ):
                self.computed_getter = True  # ``from operator import attrgetter as g``

    def _string_code_literal(self, node: Any, builtin_mentions: list[str]) -> None:
        """Constant strings: an annotation string that may run code; a
        code-object name as a component (as Tier 1's file-wide names); and,
        in a constant that is a dotted name (``"pdb"``, ``"cProfile.run"``,
        ``"pkg.mod:attr"``: what ``getattr``, ``attrgetter``,
        ``import_module`` and ``patch`` accept), a string-code name, a checked
        module, ``__annotations__`` or a code builtin as a component. Prose
        that mentions a name (``"runpy.run_path or as __mp_main__"``) is no
        route."""
        source = self.source
        top = node.type in ("string", "concatenated_string") and not (
            node.parent is not None and node.parent.type == "concatenated_string"
        )
        value = _constant_string(node, source)
        if (
            top
            and _in_annotation(node)
            and (value is None or "(" in value or ":=" in value)
        ):
            # A string annotation is code another caller evaluates against
            # the function's globals (``get_type_hints``, pydantic,
            # ``singledispatch.register``). Rebinding needs a call or an
            # assignment expression; one that cannot be folded fails closed.
            self._fire("annotation-string")
        if value is None:
            return
        parts = set(_NAME_SEPARATORS.split(value))
        if parts & _CODE_OBJECT_NAMES:
            self.code_objects = True
        if set(_TOKEN_WORDS.split(value)) & _GC_WALKERS:
            # PY-7, token level: ``getattr(g, "get_referents")``,
            # ``attrgetter("gc.get_objects")``.
            self.heap_walk = True
        acquired = self._acquired(node)
        if acquired and _GC in _TOKEN_WORDS.split(value):
            # ``importlib.import_module("gc")``, ``sys.modules["gc"]``.
            self.heap_walk = True
        if acquired and set(_TOKEN_WORDS.split(value)) & _ACQUIRED_MODULES:
            # Before the dotted-name gate (R-699-5, BLOCKING 2):
            # ``pkgutil.resolve_name("timeit:timeit\n")``,
            # ``pydoc.locate(".timeit.timeit")``, ``{"()": "ext://timeit.x"}``,
            # ``EntryPoint(value="timeit : timeit")``.
            self._fire("string")
        if not _DOTTED_NAME.fullmatch(value):
            return
        if parts & (_STRING_CODE_NAMES | _MODULE_STRINGS | {_ANNOTATIONS, _MARSHAL}):
            self._fire("string")
        components = _DOTTED_SPLIT.split(value)
        head = components[0]
        if head in _GENERIC_MODULE_STRINGS and (
            (
                len(components) > 1
                and (
                    _dunder(components[1])
                    or components[1] in _GENERIC_MODULE_ATTRIBUTES[head]
                )
            )
            or acquired
        ):
            # ``"timeit:timeit"``, ``importlib.import_module(name="code")``
            # (R-699-3, BLOCKING 3).
            self._fire("string")
        if parts & _BUILTINS_REACH:
            self.builtins_reach = True
        builtin_mentions.extend(parts & _CODE_BUILTINS)

    def _acquired(self, node: Any) -> bool:
        """Whether a constant string is the literal module name of an
        acquisition: the first argument or ``name=`` keyword of
        ``import_module``/``__import__`` or of a string resolver
        (``resolve_name``, ``locate``, ``safeimport``), the key of a
        ``.modules`` subscript or getter, the value of a ``"()"`` factory
        key (``logging.config.dictConfig``), or an entry point's value
        (:data:`_ENTRY_POINT`; R-699-5). Every constant among the arguments
        of ``import_module``/``__import__``, at any depth, is one too
        (R-699-6): an empty name after the dots resolves to the ``package``
        argument, or to ``__package__``/``__name__`` in ``__import__``'s
        ``globals``, so ``import_module(".", "trace")`` and ``__import__("",
        {"__package__": "trace"}, None, [], 1)`` return the stdlib module."""
        if self._in_acquirer_call(node):
            return True
        outer = node
        while (
            outer.parent is not None and outer.parent.type == "parenthesized_expression"
        ):
            outer = outer.parent
        parent = outer.parent
        if parent is None:
            return False
        if parent.type == "pair":
            key = parent.child_by_field_name("key")
            return (
                _same(parent.child_by_field_name("value"), outer)
                and key is not None
                and _constant_string(key, self.source) == _FACTORY_KEY
            )
        if self._entry_point_value(outer, parent):
            return True
        keyword = False
        if parent.type == "keyword_argument":
            name = parent.child_by_field_name("name")
            if (
                name is None
                or _text(name, self.source) != _NAME_KEYWORD
                or not _same(parent.child_by_field_name("value"), outer)
            ):
                return False
            keyword, outer, parent = True, parent, parent.parent
            if parent is None:
                return False
        if parent.type == "subscript":
            value = parent.child_by_field_name("value")
            return (
                value is not None
                and not _same(value, outer)
                and value.type == "attribute"
                and _text(value.child_by_field_name("attribute"), self.source)
                == _SYS_MODULES
            )
        if parent.type != "argument_list" or parent.parent is None:
            return False
        arguments = [c for c in parent.named_children if c.type != "comment"]
        if not keyword and (not arguments or not _same(arguments[0], outer)):
            return False
        callee = parent.parent.child_by_field_name("function")
        callee = _unwrap(callee, skip_comments=True) if callee is not None else None
        if callee is None:
            return False
        if callee.type == "identifier":
            return _text(callee, self.source) in _ACQUIRERS | _STRING_RESOLVERS
        if callee.type != "attribute":
            return False
        method = _text(callee.child_by_field_name("attribute"), self.source)
        if method in _ACQUIRERS | _STRING_RESOLVERS:
            return True
        if keyword:
            return False
        receiver = _unwrap(callee.child_by_field_name("object"), skip_comments=True)
        return (
            method in _MODULE_GETTERS
            and receiver.type == "attribute"
            and _text(receiver.child_by_field_name("attribute"), self.source)
            == _SYS_MODULES
        )

    def _in_acquirer_call(self, node: Any) -> bool:
        """Whether ``node`` lies anywhere among the arguments of an
        ``import_module`` or ``__import__`` call, by a bare name or an
        attribute (``importlib.import_module``, ``importlib.__import__``):
        the name, the ``package``, the ``globals`` dict and its values, the
        ``fromlist``, positional or keyword (R-699-6). No leading-dot
        exemption: a project module named ``trace`` may re-export the stdlib
        one (R-699-5 SHOULD 1)."""
        child, parent = node, node.parent
        while parent is not None:
            if parent.type == "call" and _same(
                parent.child_by_field_name("arguments"), child
            ):
                callee = parent.child_by_field_name("function")
                callee = (
                    _unwrap(callee, skip_comments=True) if callee is not None else None
                )
                if callee is not None and callee.type == "attribute":
                    callee = callee.child_by_field_name("attribute")
                if (
                    callee is not None
                    and callee.type == "identifier"
                    and _text(callee, self.source) in _ACQUIRERS
                ):
                    return True
            child, parent = parent, parent.parent
        return False

    def _entry_point_value(self, outer: Any, parent: Any) -> bool:
        """Whether ``outer`` is the module path an entry point loads:
        ``EntryPoint(n, "mod:attr", g)`` (any positional argument after the
        first, or ``value=``/``module_name=``) and
        ``EntryPoint.parse("n = mod:attr")`` (the first argument or
        ``src=``), on any receiver (R-699-5, BLOCKING 2)."""
        keyword = None
        if parent.type == "keyword_argument":
            name = parent.child_by_field_name("name")
            if name is None or not _same(parent.child_by_field_name("value"), outer):
                return False
            keyword = _text(name, self.source)
            outer, parent = parent, parent.parent
        if parent is None or parent.type != "argument_list" or parent.parent is None:
            return False
        callee = parent.parent.child_by_field_name("function")
        callee = _unwrap(callee, skip_comments=True) if callee is not None else None
        if callee is None:
            return False
        receiver = None
        if callee.type == "identifier":
            method = _text(callee, self.source)
        elif callee.type == "attribute":
            method = _text(callee.child_by_field_name("attribute"), self.source)
            receiver = _unwrap(callee.child_by_field_name("object"), skip_comments=True)
        else:
            return False
        index: int | None = None
        if keyword is None:
            positional = [
                child
                for child in parent.named_children
                if child.type not in ("comment", "keyword_argument")
            ]
            for position, child in enumerate(positional):
                if _same(child, outer):
                    index = position
                    break
                if child.type in ("list_splat", "parenthesized_list_splat"):
                    index = -1  # after a splat: any position
                    break
        if method == _ENTRY_POINT:
            if keyword is not None:
                return keyword in _ENTRY_POINT_KEYWORDS
            return index is not None and index != 0
        if method != _ENTRY_POINT_PARSE or receiver is None:
            return False
        if receiver.type == "attribute":
            receiver = receiver.child_by_field_name("attribute")
        if receiver is None or receiver.type != "identifier":
            return False
        if _text(receiver, self.source) != _ENTRY_POINT:
            return False
        if keyword is not None:
            return keyword in _ENTRY_POINT_PARSE_KEYWORDS
        return index is not None and index <= 0

    def _computed_getter(self, callee: Any, name: str) -> None:
        """Plan PY-5: ``attrgetter``, ``methodcaller``, ``getattr_static`` or
        ``__getattribute__`` with a name argument that is not a constant
        string, or handed on uncalled, in a mock file."""
        call = _callee_call(callee)
        if call is None or not self._constant_names(call, name):
            self.computed_getter = True

    def _constant_names(self, call: Any, name: str) -> bool:
        """Whether a getter call's attribute-name arguments are all constant
        strings: the second of ``getattr``/``getattr_static``, every one of
        ``attrgetter``, the first of ``methodcaller``, the last of
        ``__getattribute__`` (one or two arguments)."""
        arguments = _call_arguments(call)
        if any(
            argument.type
            in ("list_splat", "dictionary_splat", "keyword_argument", "comment")
            for argument in arguments
        ):
            return False
        if name in ("getattr", "getattr_static"):
            names = arguments[1:2]
        elif name == "attrgetter":
            names = arguments
        elif name == "methodcaller":
            names = arguments[:1]
        else:
            names = arguments[-1:] if len(arguments) in (1, 2) else []
        return bool(names) and all(
            _constant_string(argument, self.source) is not None for argument in names
        )

    def _attribute_read(self, ident: Any) -> bool:
        """Whether ``X.<ident>`` is only read (a closed list): ``.get(...)``
        called on it, a subscript read of it, or the right operand of
        ``in``/``not in``. Anything else (a target, a mutating method, an
        alias, an argument) may write through it."""
        parent = ident.parent
        if (
            parent is None
            or parent.type != "attribute"
            or not _same(ident, parent.child_by_field_name("attribute"))
            or parent.id in self.attribute_targets
        ):
            return False
        outer = parent
        while (
            outer.parent is not None and outer.parent.type == "parenthesized_expression"
        ):
            outer = outer.parent
        above = outer.parent
        if above is None:
            return False
        if above.type == "attribute" and _same(
            outer, above.child_by_field_name("object")
        ):
            method = above.child_by_field_name("attribute")
            return (
                method is not None
                and _text(method, self.source) == "get"
                and _callee_call(above) is not None
            )
        if above.type == "subscript" and _same(
            outer, above.child_by_field_name("value")
        ):
            return not any(above.id == target.id for target in self.subscript_targets)
        if above.type == "comparison_operator":
            operators = [child.type for child in above.children if not child.is_named]
            operands = [c for c in above.named_children if c.type != "comment"]
            return (
                len(operands) == 2
                and operators in (["in"], ["not in"], ["not", "in"])
                and operands[1].id == outer.id
            )
        return False

    def _use_lookup(self, ident: Any) -> dict[str, Any]:
        """The ordinary lookup at a trigger's use site, deciding which
        binding the name denotes: before any S2 flag applies, and ignoring
        the file-wide frame rule and the annotation rule, which say only that
        the binding may be rebound at run time (rebinding a name to a
        string-code helper needs a route that is spelled, and fires, itself).
        Module-scope dynamic binding still counts: ``globals().pop("compile")``
        makes a later ``compile`` the builtin."""
        saved = (self.frame_locals, self.decided)
        self.frame_locals = False
        try:
            outcome = self.lookup(ident, annotations=False)
            self.use_decided = self.decided
            return outcome
        finally:
            self.frame_locals, self.decided = saved

    def _own_binding(self, outcome: Mapping[str, Any]) -> bool:
        return outcome.get("outcome") == "local" or (
            outcome.get("outcome") == "none"
            and outcome.get("reason") in _OWN_BINDING_REASONS
        )

    def _is_builtin(self, ident: Any) -> bool:
        """Whether a builtin's use may be the builtin (R-699-3, BLOCKING 1):
        anything but a binding of the file's own that dominates the use. In
        a function scope every binding does (a use that runs first raises
        ``UnboundLocalError`` or ``NameError``): a ``def`` or ``class``, a
        parameter, a variable, an expression binding, or an import from a
        module other than ``builtins``; a value handed in from this file
        spells the builtin and fires itself. At module or class scope a use
        may run before any binding and get the builtin, so none proves: the
        lookup gives ``builtin-shadow`` for module definitions and imports,
        and a variable or walrus binding (``compile = compile``, a use before
        ``compile = re.compile``) fails closed here."""
        outcome = self._use_lookup(ident)
        scope = self.use_decided
        if outcome.get("outcome") == "import":
            binding = outcome.get("binding") or {}
            return binding.get("module") in _BUILTIN_MODULES
        if not self._own_binding(outcome):
            return True
        return (
            scope is None
            or scope.kind in (_MODULE, _CLASS)
            or not self._real_binding(scope, _text(ident, self.source))
        )

    @staticmethod
    def _real_binding(scope: _Scope | None, name: str) -> bool:
        """Whether ``scope`` binds ``name`` by a binding CPython makes: a
        phantom one alone (:class:`_Binding`) proves nothing (R-699-5)."""
        return scope is not None and any(
            not binding.phantom for binding in scope.bindings.get(name, ())
        )

    def _re_receiver(self, attribute: Any) -> bool:
        """Whether ``X.compile``'s receiver is a name the ordinary lookup
        proves is an import of the ``re`` module (``import re [as r]``)."""
        receiver = attribute.child_by_field_name("object")
        receiver = _unwrap(receiver, skip_comments=True) if receiver else None
        if receiver is None or receiver.type != "identifier":
            return False
        outcome = self._use_lookup(receiver)
        binding = outcome.get("binding") or {}
        return bool(
            outcome.get("outcome") == "import"
            and binding.get("form") == "import"
            and binding.get("bound") == _RE_MODULE
        )

    def legacy_evaluator(self) -> bool:
        """Whether a use of ``exec``, ``eval`` or ``execfile`` may be the
        builtin by the full lookup at the end of the analysis, the frame and
        annotation rules included: PR 6's Tier 2 ``evaluator`` test, which
        the shared classifier must keep (R-699-3). A frame rule or a lazy
        annotation makes the lookup inconclusive, so a local definition or a
        parameter there no longer proves the use is not the builtin. Tier 1
        is unaffected: those lookups already fail closed."""
        for kind, node in self.string_checks:
            if kind != "builtin" or _text(node, self.source) not in (
                _LEGACY_EVALUATORS
            ):
                continue
            outcome = self.lookup(node)
            if outcome.get("outcome") == "none" and outcome.get("reason") not in (
                _OWN_BINDING_REASONS
            ):
                return True
        return False

    def _verify_string_code(self) -> None:
        """The use-site half of the classifier (#699 S2), once the scopes are
        complete. Every decision is made first, then the flags apply, so no
        trigger changes how another use looks up."""
        computed_getter = self.computed_getter
        checked = self.checked_bindings
        for kind, node in self.string_checks:
            if kind == "builtin":
                if self._is_builtin(node):
                    self._fire(
                        "builtin",
                        namespace_candidate=_text(node, self.source) == "exec",
                    )
            elif kind == "attribute:compile":
                if self.builtins_reach and not self._re_receiver(node):
                    self._fire("builtin")
            elif kind == "getattr":
                if self._is_builtin(node):
                    call = _callee_call(node)
                    if call is None or not self._constant_names(call, "getattr"):
                        computed_getter = True
            elif kind == "module:pickle":
                if not self._safe_module_use(node, "pickle"):
                    self._fire("checked")
            elif kind == "module:gc":
                if not self._safe_module_use(node, _GC):
                    self.heap_walk = True
            elif kind == "checked":
                failed = self._checked_violation(node, checked)
                if failed is not None:
                    self._fire_checked(failed)
        if computed_getter:
            self.dynamic = True
        self.namespace_receiver_blocked |= self.frame_locals or self.heap_walk
        if self.string_code:
            self.dynamic = True
            self.frame_locals = True
        if self.heap_walk:
            # PY-7: a heap walk reaches a function's globals dict, code
            # object and closure cells, so function scopes fail closed too.
            self.dynamic = True
            self.frame_locals = True

    def _fire_checked(self, module: str) -> None:
        """A use of a checked module off its member list: string code for
        ``pickle``, ``timeit`` and ``runpy``, a heap walk for ``gc``."""
        if module == _GC:
            self.heap_walk = True
        else:
            self._fire("checked")

    def _checked_violation(
        self, ident: Any, checked: Mapping[str, list[Mapping[str, str]]]
    ) -> str | None:
        """The checked module whose allow-list a use of a name an import of a
        checked module binds is off, for some import binding the ordinary
        lookup leaves possible, or ``None`` when every one allows it."""
        outcome = self._use_lookup(ident)
        if self._own_binding(outcome) and self._real_binding(
            self.use_decided, _text(ident, self.source)
        ):
            return None
        if outcome.get("outcome") == "import":
            binding = outcome.get("binding") or {}
            infos = [binding] if _checked_import(binding) is not None else []
        else:
            infos = [
                info
                for spelling in sorted(_spellings(ident, self.source))
                for info in checked.get(spelling, ())
            ]
        for info in infos:
            found = _checked_import(info)
            assert found is not None
            module, member = found
            if member is not None:
                if module == _RUNPY and not self._plain_runpy_call(ident):
                    return module
                if member not in _CHECKED_MODULES[module]:
                    return module
            elif not self._safe_module_use(ident, module):
                return module
        return None

    def _safe_module_use(self, node: Any, module: str) -> bool:
        """Whether an expression denoting a checked module reads a listed
        member (``pickle.dumps``; ``runpy.run_path`` called plainly)."""
        outer = node
        while (
            outer.parent is not None and outer.parent.type == "parenthesized_expression"
        ):
            outer = outer.parent
        parent = outer.parent
        if (
            parent is None
            or parent.type != "attribute"
            or not _same(outer, parent.child_by_field_name("object"))
        ):
            return False
        member = parent.child_by_field_name("attribute")
        name = _text(member, self.source) if member is not None else ""
        if module in _REEXPORT_CHECKED:
            return bool(name) and not (
                _dunder(name) or name in _GENERIC_MODULE_ATTRIBUTES[module]
            )
        if name not in _CHECKED_MODULES[module]:
            return False
        return module != _RUNPY or self._plain_runpy_call(parent)

    def _plain_runpy_call(self, callee: Any) -> bool:
        """``run_path(p)``/``run_module(m)`` called directly with exactly one
        positional argument and only ``run_name``/``alter_sys`` keywords."""
        call = _callee_call(callee)
        if call is None:
            return False
        arguments = call.child_by_field_name("arguments")
        if arguments is None or arguments.type != "argument_list":
            return False
        positional = 0
        for argument in _call_arguments(call):
            if argument.type == "keyword_argument":
                keyword = argument.child_by_field_name("name")
                if keyword is None or _text(keyword, self.source) not in (
                    _RUNPY_KEYWORDS
                ):
                    return False
            elif argument.type in (
                "list_splat",
                "dictionary_splat",
                "parenthesized_list_splat",
            ):
                return False
            else:
                positional += 1
        return positional == 1

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
        if "mock" in parts:
            self.mock_string_seen = True
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
        literal names are recorded; any other write fails closed. Aliases,
        readbacks and escapes (W-2) are the shared mechanism of
        :meth:`_sensitive_rules` (fold 22).
        """
        for node in calls:
            self._namespace_call(node, operator_names)
        for node in augmented:
            self._namespace_ior(node)

    # -- sensitive kinds: one alias/readback/escape mechanism (fold 22) ------

    def _sensitive_rules(
        self,
        calls: list[Any],
        attributes: list[Any],
        identifiers: list[Any],
        subscripts: list[Any],
        bindings: list[tuple[Any, Any]],
        matches: list[Any],
    ) -> None:
        """One mechanism for every sensitive kind: a namespace dict, the mock
        module, ``patch`` and a pytest-mock fixture (#695 fold 22).

        **Alias binding.** Every binding form makes an alias of the kind its
        value contains: assignment, tuple/list/starred targets, walrus,
        conditional and boolean operands, a ``for`` target, ``with … as``, a
        ``match`` capture, a class-body binding, ``self.X = …``,
        ``global``/``nonlocal``, and ``setattr(T, "name", v)`` with a
        constant name (flow-insensitive, transitive). Every import of the
        mock module or ``patch``, in any spelling and at any scope, is an
        alias too (fold 24, Y-5).

        **Readback.** A name, an ``X.<alias>`` attribute, any call with a
        constant argument naming an alias (``getattr(K, "ns")``,
        ``type.__getattribute__(K, "ns")``, ``attrgetter("ns")(K)``) and a
        subscript with such a constant key (``K.__dict__["ns"]``) read the
        kind back (:meth:`_sensitive`).

        **Uses.** A sensitive value's every use must be on THE CLOSED
        ALLOW-LIST (:meth:`_safe_use`, fold 23); anything else fails closed,
        for example a call argument (other than a namespace dict as the
        receiver of an unbound mutator or ``operator`` writer), a container
        element, a return or yield value, a default, a lambda body, a
        ``with`` item, a ``for`` or comprehension iterable, and a binding a
        computed read can reach (at module or class scope, ``global``, an
        attribute or subscript target, or a local of a function whose locals
        may be read as a dict, :meth:`_locals_reachable`, #707).
        """
        # Import bindings are aliases (fold 24, Y-5): a module- or
        # class-scope import of the mock module or ``patch``, in any spelling,
        # can be read back (``m.mk``, ``getattr(m, "P")``, ``ns["P"]``,
        # ``K.mk``, ``case object(um=x)``).
        self.aliases[_MOCK] |= self.mock_import_names
        self.aliases[_PATCH] |= self.patch_import_names
        present = {
            kind: self._kind_present(kind, attributes, identifiers) for kind in _KINDS
        }
        named: list[tuple[str, Any]] = []
        for node in calls:
            function = node.child_by_field_name("function")
            function = _unwrap(function, skip_comments=True) if function else None
            arguments = _call_arguments(node)
            if (
                function is not None
                and function.type == "identifier"
                and _text(function, self.source) == "setattr"
                and len(arguments) == 3
            ):
                name = _constant_string(arguments[1], self.source)
                if name is not None:
                    named.append((name, arguments[2]))  # ``setattr(T, "mm", mocker)``
        changed = True
        while changed:
            changed = False
            for kind in _KINDS:
                if not present[kind]:
                    continue
                found: set[str] = set()
                for target, value in bindings:
                    if self._contains_kind(value, kind):
                        found |= _binding_names(target, self.source)
                for name, value in named:
                    if self._contains_kind(value, kind):
                        found.add(name)
                if found - self.aliases[kind]:
                    self.aliases[kind] |= found
                    changed = True
        if self.aliases[_NS]:
            self.namespace_seen = True
        # A class-pattern keyword reads an attribute of the subject
        # (``case object(__dict__=x)`` is ``x = subject.__dict__``): a keyword
        # naming a sensitive attribute or an alias is off the allow-list,
        # whatever the subject (fold 23, X-6).
        sensitive_names = {_NAMESPACE_DICT, "mock", "patch"}.union(
            *self.aliases.values()
        )
        for match in matches:
            stack = [match]
            while stack:
                current = stack.pop()
                stack.extend(current.named_children)
                if current.type != "keyword_pattern" or not current.named_children:
                    continue
                keyword = current.named_children[0]
                if _spellings(keyword, self.source) & sensitive_names:
                    self.dynamic = True
                    return
        if not any(present.values()) and not any(self.aliases.values()):
            return
        nodes = identifiers + attributes + calls + subscripts
        for kind in _KINDS:
            if not present[kind] and not self.aliases[kind]:
                continue
            for node in nodes:
                if node.type == "identifier" and _name_part(node):
                    continue  # the ``ns`` of ``K.ns``: part of a larger read
                if self._sensitive(node, kind) and not self._safe_use(node, kind):
                    self.dynamic = True
                    return

    def _kind_present(
        self, kind: str, attributes: list[Any], identifiers: list[Any]
    ) -> bool:
        if kind == _NS:
            return self.namespace_seen or any(
                _text(ident, self.source) == "vars" for ident in identifiers
            )
        if kind == _MOCKER:
            return any(
                _spellings(ident, self.source) & _MOCKER_NAMES for ident in identifiers
            )
        if kind in (_MOCK, _PATCH):
            return bool(
                self.mock_import_names
                or self.patch_import_names
                or self.mock_imported
                or self.mock_string_seen
                or any(
                    _text(ident, self.source) in ("mock",) + tuple(_MOCKER_NAMES)
                    for ident in identifiers
                )
            )
        return False

    def _contains_kind(self, node: Any, kind: str) -> bool:
        """Whether a bound value carries the sensitive ``kind``: the value
        itself, or an element of a tuple, list or set, through parentheses,
        starred forms, walrus values and conditional or boolean operands. A
        call, attribute read or subscript of it does not carry it
        (``ns.get("p")``); a sensitive value passed as an argument
        escapes instead."""
        stack = [node]
        while stack:
            current = stack.pop()
            if self._sensitive(current, kind):
                return True
            if current.type in (
                "tuple",
                "list",
                "set",
                "expression_list",
                "parenthesized_expression",
                "list_splat",
                "pattern_list",
            ):
                stack.extend(current.named_children)
        return False

    def _sensitive(self, node: Any, kind: str) -> bool:
        """Whether ``node`` reads a value of the sensitive ``kind``: its base
        spelling, or a readback of one of its aliases (fold 22)."""
        node = _unwrap(node, skip_comments=True)
        kind_of = node.type
        if kind_of == "named_expression":
            value = node.child_by_field_name("value")
            return value is not None and self._sensitive(value, kind)
        if kind_of == "conditional_expression":
            return any(
                self._sensitive(child, kind)
                for child in node.named_children
                if child.type != "comment"
            )
        if kind_of == "boolean_operator":
            return any(
                self._sensitive(child, kind)
                for child in (
                    node.child_by_field_name("left"),
                    node.child_by_field_name("right"),
                )
                if child is not None
            )
        aliases = self.aliases[kind]
        if kind_of == "identifier":
            names = _spellings(node, self.source)
            if names & aliases:
                return True
            if kind == _MOCK:
                return bool(names & self.mock_import_names)
            if kind == _PATCH:
                return bool(names & self.patch_import_names)
            if kind == _MOCKER:
                return bool(names & _MOCKER_NAMES)
            return False
        if kind_of == "attribute":
            attribute = node.child_by_field_name("attribute")
            receiver = node.child_by_field_name("object")
            if attribute is None:
                return False
            names = _spellings(attribute, self.source)
            if names & aliases:
                return True  # ``m.NS``, ``K.ns``, ``self.mm``
            name = _text(attribute, self.source)
            if kind == _NS:
                return name == _NAMESPACE_DICT
            if kind == _MOCK:
                return name == "mock"  # ``X.mock`` for any ``X`` (W-5)
            if kind == _PATCH:
                return (
                    name == "patch"
                    and receiver is not None
                    and (
                        self._sensitive(receiver, _MOCK)
                        or self._sensitive(receiver, _MOCKER)
                    )
                )
            return False
        if kind_of == "call":
            function = node.child_by_field_name("function")
            function = _unwrap(function, skip_comments=True) if function else None
            constants = _constant_arguments(node, self.source)
            if function is not None and function.type == "call":
                # ``attrgetter("ns")(K)``
                constants |= _constant_arguments(function, self.source)
            if constants & aliases:
                return True  # ``getattr(K, "ns")``, ``type.__getattribute__(K, "ns")``
            if kind == _NS:
                if function is not None and function.type == "identifier":
                    if _text(function, self.source) == "vars":
                        return True
                return _NAMESPACE_DICT in constants
            if kind == _MOCK:
                return "mock" in constants  # ``getattr(unittest, "mock")``
            if kind == _PATCH:
                return "patch" in constants and any(
                    self._sensitive(argument, _MOCK)
                    or self._sensitive(argument, _MOCKER)
                    for argument in _call_arguments(node)
                )
            return False
        if kind_of == "subscript":
            keys = {
                value
                for index, child in enumerate(node.children)
                if node.field_name_for_child(index) == "subscript"
                for value in [_constant_string(child, self.source)]
                if value is not None
            }
            return bool(keys & aliases)  # ``K.__dict__["ns"]``
        return False

    def _safe_use(self, node: Any, kind: str) -> bool:
        """Whether a sensitive value's use is on THE CLOSED ALLOW-LIST
        (#695 fold 23, E-21 A-1); every other use fails closed (A-2).

        The value is followed through parentheses, walrus values and
        conditional or boolean operands. Safe uses:

        - a binding position (a parameter, a target, an import, a pattern);
        - an alias binding: the value assigned (or walrus-bound) to one
          name a computed read cannot reach (a function local whose locals
          nothing may read as a dict, :meth:`_locals_reachable`, #707);
        - a namespace dict: ``ns[c]`` with constant keys (read, target,
          ``del``), ``ns.get(c, …)``,
          ``c in ns``, ``len(ns)``; ``ns.update/setdefault/pop(…)``, the
          unbound ``dict.``/``operator`` writers with ``ns`` first, and
          ``ns |= …``, as expression statements (their constant names are
          recorded; anything else fails closed in the write rules);
        - the mock module: ``mock.<name>`` for a name in ``_MOCK_SAFE``, and
          ``mock.patch``;
        - a fixture: ``mocker.<name>`` for a name in ``_MOCKER_SAFE``, and
          ``mocker.patch``;
        - ``patch``: called, or ``patch.object/dict/multiple`` called (W-3).
        An import binding is safe here because its name is an alias, so every
        readback of it is checked in turn (fold 24, Y-5).
        """
        if node.type == "identifier" and _binding_position(node):
            # #707 (R-707-1): a parameter (a pytest ``mocker``) or other
            # local binding of a function whose locals may be read as a dict
            # is reachable (``locals()["mocker"].patch(...)``).
            return not self._local_binding_readable(node)
        current = node
        parent = current.parent
        while parent is not None:
            if parent.type == "parenthesized_expression":
                named = [c for c in parent.named_children if c.type != "comment"]
                if len(named) != 1:
                    break
            elif parent.type == "named_expression":
                if not _same(current, parent.child_by_field_name("value")):
                    break
                name = parent.child_by_field_name("name")
                if name is None or self._reachable_binding(name):
                    return False
            elif parent.type not in ("conditional_expression", "boolean_operator"):
                break
            current, parent = parent, parent.parent
        if parent is None:
            return False
        kind_of = parent.type
        if kind_of == "assignment":
            left = parent.child_by_field_name("left")
            if left is None or not _same(current, parent.child_by_field_name("right")):
                return False
            left = _unwrap(left, skip_comments=True)
            return left.type == "identifier" and not self._reachable_binding(left)
        if kind_of == "attribute" and _same(
            current, parent.child_by_field_name("object")
        ):
            attribute = parent.child_by_field_name("attribute")
            name = _text(attribute, self.source) if attribute is not None else ""
            call = _callee_call(parent)
            if kind == _NS:
                if name in _NS_WRITES:
                    return call is not None and _statement_call(call)
                if name not in _NS_READS or call is None:
                    return False
                if name == "get":
                    arguments = _call_arguments(call)
                    return bool(arguments) and (
                        _constant_string(arguments[0], self.source) is not None
                    )
                return True
            if kind == _MOCK:
                return name in _MOCK_SAFE or name == "patch"
            if kind == _MOCKER:
                return name in _MOCKER_SAFE or name == "patch"
            return name in _PATCH_SAFE and call is not None
        if kind_of == "call" and _same(current, parent.child_by_field_name("function")):
            return kind == _PATCH
        if kind_of == "decorator":
            return False
        if kind != _NS:
            return False
        if kind_of == "subscript" and _same(
            current, parent.child_by_field_name("value")
        ):
            keys = [
                child
                for index, child in enumerate(parent.children)
                if parent.field_name_for_child(index) == "subscript"
            ]
            return bool(keys) and all(
                _constant_string(key, self.source) is not None for key in keys
            )
        if kind_of == "comparison_operator":
            # ``not in`` is one token, whose text may hold any whitespace
            # (fold 27: the fold-23 check never matched it).
            operators = [
                " ".join(_text(child, self.source).split())
                for child in parent.children
                if not child.is_named
            ]
            operands = [c for c in parent.named_children if c.type != "comment"]
            return (
                len(operands) == 2
                and _same(current, operands[1])
                and operators in (["in"], ["not in"])
            )
        if kind_of == "augmented_assignment":
            operator = parent.child_by_field_name("operator")
            return (
                _same(current, parent.child_by_field_name("left"))
                and operator is not None
                and _text(operator, self.source) == "|="
            )
        if kind_of == "argument_list":
            call = parent.parent
            function = (
                call.child_by_field_name("function") if call is not None else None
            )
            if function is None:
                return False
            function = _unwrap(function, skip_comments=True)
            arguments = [c for c in parent.named_children if c.type != "comment"]
            # Every callee below is verified by binding (fold 25): ``len``
            # and ``dict`` must be the builtins, ``operator`` and its writers
            # must come from a tracked import of ``operator``.
            if len(arguments) == 1 and self._builtin_name(function, "len"):
                return True
            first = arguments[0] if arguments else None
            if first is None or not _same(first, current) or not _statement_call(call):
                return False
            if function.type == "attribute":
                attribute = function.child_by_field_name("attribute")
                receiver = function.child_by_field_name("object")
                if attribute is None or receiver is None:
                    return False
                names = _spellings(attribute, self.source)
                receiver = _unwrap(receiver, skip_comments=True)
                if names & _NAMESPACE_MUTATORS and self._builtin_name(receiver, "dict"):
                    return True  # ``dict.update(ns, …)``
                if names & _OPERATOR_WRITERS and self._stdlib_name(
                    receiver, "operator"
                ):
                    # ``operator.setitem(ns, …)`` relies on the member too: a
                    # recorded write of ``setitem`` (``operator.__dict__
                    # .update(setitem=f)``) rebinds it (fold 26, AA-4).
                    self.relied_names |= names & _OPERATOR_WRITERS
                    return True
                return False
            return self._stdlib_name(function, "operator", _OPERATOR_WRITERS)
        return False

    def _binding_sites_of(self, name: str) -> list[Any]:
        """The identifiers that bind ``name`` anywhere in the file, by
        syntax: where :meth:`_stdlib_name` checks each binding's import."""
        if self.binding_sites is None:
            sites: dict[str, list[Any]] = {}
            for ident in self.identifier_nodes:
                parent = ident.parent
                augmented = (
                    parent is not None
                    and parent.type == "augmented_assignment"
                    and _same(ident, parent.child_by_field_name("left"))
                )
                if augmented or _binding_position(ident):
                    sites.setdefault(_text(ident, self.source), []).append(ident)
            self.binding_sites = sites
        return self.binding_sites.get(name, [])

    def _builtin_name(self, node: Any, name: str) -> bool:
        """Whether ``node`` is the builtin ``name`` (fold 25): spelled so, and
        bound nowhere in the file (no definition, class, assignment,
        import, parameter, ``global``/``nonlocal``, ``for``/``with``/
        ``except`` target, comprehension variable, pattern capture or
        ``del``). A recorded write of the name into a namespace is checked
        once every rule has run (``relied_names``); a star import already
        makes every module-scope lookup ``star-import``."""
        if node.type != "identifier" or _text(node, self.source) != name:
            return False
        # The rules run before the binding events are applied to the scopes,
        # so the events are the scope pass's complete record (every node kind
        # is classified, so no binding form escapes it).
        if any(bound == name for _scope, bound, _binding in self.events):
            return False
        self.relied_names.add(name)
        self.verifications.append((node, None, None))
        return True

    def _stdlib_name(
        self, node: Any, module: str, members: frozenset[str] | None = None
    ) -> bool:
        """Whether ``node`` names ``module`` (``import operator [as op]``) or,
        with ``members``, one of them (``from operator import setitem
        [as s]``), every binding of the name in the file being such an
        import (fold 25)."""
        if node.type != "identifier":
            return False
        name = _text(node, self.source)
        sites = self._binding_sites_of(name)
        imported = [_imports_from(site, self.source, module, members) for site in sites]
        if not sites or not all(imported):
            return False
        if any(
            bound == name and binding.cls != IMPORT
            for _scope, bound, binding in self.events
        ):
            return False
        self.relied_names.add(name)
        self.verifications.append((node, module, members))
        if members is not None:
            # ``from operator import setitem as s`` relies on the module's
            # ``setitem`` member as well as on ``s`` (fold 26, AA-4).
            self.relied_names.update(member for member in imported if member)
        return True

    def _local_binding_readable(self, ident: Any) -> bool:
        """Whether a binding-position identifier is a local of a function
        or lambda whose locals may be read as a dict (#707, R-707-1); a
        module- or class-scope binding is handled by the alias rules."""
        current = ident.parent
        while current is not None and current.type not in (
            "function_definition",
            "lambda",
            "class_definition",
            "module",
        ):
            current = current.parent
        return (
            current is not None
            and current.type in ("function_definition", "lambda")
            and self._locals_reachable(current)
        )

    def _reachable_binding(self, ident: Any) -> bool:
        """Whether a name binding is reachable by a computed read: at module
        or class scope, declared ``global`` in its function, or in a function
        whose locals may be read as a dict (:meth:`_locals_reachable`)."""
        current = ident.parent
        while current is not None and current.type not in (
            "function_definition",
            "lambda",
            "class_definition",
            "module",
        ):
            current = current.parent
        if current is None or current.type in ("module", "class_definition"):
            return True
        scope = self.scopes.get((current.id, "scope"))
        if scope is not None and _text(ident, self.source) in scope.globals:
            return True
        return self._locals_reachable(current)

    def _locals_reachable(self, function: Any) -> bool:
        """Whether a function's (or lambda's) locals may be read as a dict
        (#707), the way ``globals()`` reads every module-scope binding:

        - a ``locals()`` or no-argument ``vars()`` call anywhere inside it,
          a nested function, class body, lambda or comprehension included
          (PEP 709 inlines a comprehension into its function's frame; a
          nested scope's ``locals()`` holds the free variables it reads; an
          enclosing scope counts too, which can only fail closed);
        - ``locals`` or ``vars`` anywhere in the file as a value rather than
          a callee (``L = locals``, ``functools.partial(locals)``), as an
          attribute of anything (``len.__self__.locals()``), as an imported
          name (``from compat import locals as get``) or in any constant
          string, exactly or as a dotted, ``:`` or bracket component
          (``getattr(b, "locals")``, ``attrgetter("__self__.locals")``,
          ``N = "locals"``; token level, as R-724-1): called later, from any
          frame, they read that frame's locals;
        - a frame's locals through the file-wide triggers (``f_locals``, also
          read-only, ``getargvalues``, ...).

        A bare ``locals``/``vars`` name is not the builtin only when the
        ordinary use-site lookup proves a local definition (``def locals():``
        in the function); anything else (an import, an assignment, any
        ``none``) counts as the builtin. Before the scopes are complete the
        name is relied on and checked by :meth:`_verify_callees`."""
        if self.frame_locals:
            return True
        for reader, by_lookup in self._locals_readers():
            if reader is not None and not (
                function.start_byte <= reader.start_byte
                and reader.end_byte <= function.end_byte
            ):
                continue
            if not by_lookup:
                return True
            if not self.complete:
                self.reader_checks.append(reader)
            elif self._may_read_locals(reader):
                return True
        return False

    def _may_read_locals(self, reader: Any) -> bool:
        """Whether a bare ``locals``/``vars`` may be the builtin: its
        use-site lookup is anything but a proven local definition."""
        decided = self.decided
        outcome = self.lookup(reader)
        self.decided = decided
        return outcome.get("outcome") != "local"

    def _locals_readers(self) -> list[tuple[Any, bool]]:
        """Every spelling that may read a frame's locals as a dict (#707),
        computed once: ``(node, by_lookup)``, where ``node`` is the reader
        identifier of a call form (it reads the frame it runs in) or
        ``None`` for a form that reaches any frame, and ``by_lookup`` says
        only the use-site lookup can tell the name from the builtin."""
        if self.locals_readers is not None:
            return self.locals_readers
        readers: list[tuple[Any, bool]] = []
        source = self.source
        for ident in self.identifier_nodes:
            if _text(ident, source) not in _LOCALS_READERS:
                continue
            parent = ident.parent
            if parent is None:
                continue
            if parent.type == "keyword_argument" and _same(
                ident, parent.child_by_field_name("name")
            ):
                continue
            attribute = parent.type == "attribute" and _same(
                ident, parent.child_by_field_name("attribute")
            )
            if not attribute and _binding_position(ident):
                # #707 (R-707-1): an imported name (``from compat import
                # locals as get``) may be the builtin under another name
                # (R-724-1: import names are tokens). A ``def``, parameter or
                # target is left to the use-site lookup of a bare call.
                ancestor = parent
                while ancestor is not None and ancestor.type not in (
                    "import_from_statement",
                    "import_statement",
                    "module",
                    "block",
                ):
                    ancestor = ancestor.parent
                if ancestor is not None and ancestor.type in (
                    "import_from_statement",
                    "import_statement",
                ):
                    readers.append((None, False))
                continue
            node = parent if attribute else ident
            call = _callee_call(node)
            if call is None:
                readers.append((None, False))
                continue
            arguments = _call_arguments(call)
            if (
                _text(ident, source) == "vars"
                and len(arguments) == 1
                and arguments[0].type
                not in ("list_splat", "dictionary_splat", "keyword_argument")
            ):
                continue  # ``vars(obj)`` reads ``obj.__dict__``
            readers.append((ident, not attribute))
        stack = [self.root]
        while stack:
            node = stack.pop()
            stack.extend(node.named_children)
            if node.type not in ("string", "concatenated_string", "binary_operator"):
                continue
            value = _constant_string(node, source)
            if value is None:
                continue
            # #707 (R-707-1, token level as R-724-1): any constant string,
            # anywhere, matched exactly or as a dotted, ``:`` or bracket
            # component (``attrgetter('__self__.locals')``, ``N = 'locals'``).
            if ({value} | set(re.split(r"[.:\[\]]", value))) & _LOCALS_READERS:
                readers.append((None, False))
        self.locals_readers = readers
        return readers

    def _namespace_receiver(self, node: Any) -> bool:
        return self._sensitive(node, _NS)

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

    def _mock_expression(self, node: Any, mock_names: set[str]) -> bool:
        return self._sensitive(node, _MOCK)

    def _mocker_expression(self, node: Any) -> bool:
        return self._sensitive(node, _MOCKER)

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
        ``patch.multiple`` keywords are attribute writes. A constant
        ``patch("a.helper")`` keeps the own-name rule.

        Fold 20 adds receiver-based patchers: any ``X.patch.object``,
        ``X.patch.dict`` or ``X.patch.multiple`` chain, whatever ``X`` is, and
        ``.patch`` on a pytest-mock fixture. A plain ``.patch(url)`` on any
        other receiver is untouched.

        Fold 22: which values are the mock module, ``patch`` or a fixture,
        and where they escape, is the shared mechanism of
        :meth:`_sensitive_rules`; ``X.mock`` counts for any ``X``. A constant
        ``"patch"`` or ``"mock"`` string in a file that imports the mock
        module fails closed (``getattr(mock, "patch")``,
        ``getattr(unittest, "mock")``, ``mock.__dict__["patch"]``).

        treesitter-chunker#699 PY-10 (ruling R-699-1 Q6, in the E6-9b style):
        ``.patch`` is a patcher on ANY receiver, since which value is the
        mock module or a fixture cannot be proven (a parameter, a fixture
        under another name, ``getattr(mocker, "patch")``). A direct call
        ``X.patch(...)`` gets the W-3 semantics, so a computed target fails
        closed and a constant one keeps the own-name rule
        (``@router.patch("/items")`` stays inert); ``X.patch`` read any other
        way (handed on, aliased, ``X.patch.__call__``) and a constant
        ``"patch"`` naming a member by string (a call argument or subscript
        key: ``getattr(X, "patch")``, ``methodcaller("patch", t)``,
        ``vars(type(X))["patch"]``) fail closed, unless the mock rules
        recognise ``X`` (its aliases are then checked use by use). Writing
        ``X.patch = v`` reads no patcher."""
        if self.mock_imported and (self.patch_string_seen or self.mock_string_seen):
            self.dynamic = True
        for node in calls:
            function = node.child_by_field_name("function")
            if function is None:
                continue
            function = _unwrap(function, skip_comments=True)
            kind = None
            if self._is_patch(function, mock_names, patch_names):
                kind = "patch"
            elif _is_patch_attribute(function, self.source):
                kind = "patch"  # ``X.patch(...)`` for any ``X`` (PY-10)
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
        # ``X.patch.object`` for any ``X`` (fold 20): handed on fails closed.
        for node in attributes:
            attribute = node.child_by_field_name("attribute")
            receiver = node.child_by_field_name("object")
            if (
                attribute is not None
                and _text(attribute, self.source) in _PATCH_METHODS
                and receiver is not None
                and (
                    _is_patch_attribute(receiver, self.source)
                    or self._is_patch(receiver, mock_names, patch_names)
                )
                and _callee_call(node) is None
            ):
                self.dynamic = True
            if (
                attribute is not None
                and _text(attribute, self.source) == "patch"
                and node.id not in self.attribute_targets
                and not _patch_applied(node, self.source)
                and not self._sensitive(node, _PATCH)
            ):
                # ``p = X.patch`` for an ``X`` the mock rules do not recognise
                # (PY-10); a recognised one is an alias whose every use the
                # closed allow-list checks.
                self.dynamic = True
        for node in self._patch_name_strings():
            self.dynamic = True  # ``getattr(X, "patch")`` (PY-10)
            break

    def _patch_name_strings(self) -> Iterator[Any]:
        """Every constant string that names a patcher: ``"patch"`` that
        names a member by string (:func:`py_modules._argument_string`: a
        call argument, positional or a keyword value, or a subscript key),
        whole or as a dotted component (``attrgetter("m.patch")``; PY-10),
        and any constant string (:func:`_patch_token_string`) exactly
        ``"patch"`` or with a private patcher token as a word (R-699-12)."""
        stack = [self.root]
        while stack:
            node = stack.pop()
            stack.extend(node.named_children)
            value = py_modules._argument_string(node, self.source)
            if (
                value is not None and _PATCH in _TOKEN_PARTS.split(value)
            ) or _patch_token_string(node, self.source):
                yield node

    def _is_patch(self, node: Any, mock_names: set[str], patch_names: set[str]) -> bool:
        """``patch`` from the mock module or a fixture, or an alias of it."""
        return self._sensitive(node, _PATCH)

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
            binding = _Binding(LOCAL, phantom=binding.phantom)
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

    def lookup(
        self, ident: Any, *, annotations: bool = True, namespace_receiver: bool = False
    ) -> dict[str, Any]:
        """The outcome of a value lookup of ``ident``'s name. With
        ``annotations=False`` a name in an annotation is looked up through
        the ordinary chain (:meth:`_use_lookup`). Namespace receiver lookups
        can prove a local in the presence of candidate exec calls because the
        handout scan must verify every such use. Independent file-wide
        hazards still block the proof."""
        name = _text(ident, self.source)
        self.decided = None
        if self.frame_locals and (
            not namespace_receiver or self.namespace_receiver_blocked
        ):
            # ``frame.f_locals`` writes any function's locals (PEP 667).
            return _none("dynamic-scope")
        if annotations and _in_annotation(ident):
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
        self.decided = scope
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
        if (
            outcome["outcome"] != "none"
            and scope.kind == _MODULE
            and name in SHADOWED_NAMES
        ):
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


def _patch_token_string(node: Any, source: bytes) -> bool:
    """R-699-12 items 1 and 2: whether ``node`` is a whole constant string
    (a literal, adjacent literals, ``+``, an f-string of constants) that is
    exactly ``"patch"`` or has a private patcher token as a word, in any
    position."""
    if node.type not in (
        "string",
        "concatenated_string",
        "binary_operator",
        "parenthesized_expression",
    ):
        return False
    parent = node.parent
    if parent is not None and parent.type == "concatenated_string":
        return False  # judged as part of the whole literal
    if (
        parent is not None
        and parent.type in ("binary_operator", "parenthesized_expression")
        and _constant_string(parent, source) is not None
    ):
        return False  # judged as part of the larger constant (``'pat' + 'ch'``)
    value = _constant_string(node, source)
    if value is None:
        return False
    return value == _PATCH or bool(
        set(_TOKEN_WORDS.split(value)) & _PRIVATE_PATCH_TOKENS
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
    body = text[quote:]
    delimiter = body[:3] if body[:3] in ("'''", '"""') else body[:1]
    if len(body) < 2 * len(delimiter) or not body.endswith(delimiter):
        return None
    return _decode_literal(
        prefix.replace("f", ""), delimiter, body[len(delimiter) : -len(delimiter)]
    )


_MAIN_CONSTANT = "constant"
_MAIN_INTERPOLATED = "interpolated"


def _main_string(node: Any, source: bytes, value: str | None) -> str | None:
    """The K-3 ``__main__`` string classifier, shared by both tiers (#698,
    R-698-1, R-698-2, R-698-3).

    ``node`` is a string expression (a string, adjacent strings or ``+``) and
    ``value`` its :func:`_constant_string`. Returns :data:`_MAIN_INTERPOLATED`
    when the expression has an f-string or t-string and a main name occurs
    anywhere in its source text, decoded (:func:`_interpolated_names_main`,
    R-698-3), or a piece cannot be read; it always counts.
    Returns :data:`_MAIN_CONSTANT` when the constant value names it
    (:func:`_names_main`); only the script guard's comparand is exempt
    (:meth:`_Analysis._main_guard`). Otherwise ``None``. The scan in
    :meth:`_Analysis._scan_dynamic` applies it to every string node and
    records the verdict as ``main_string``, which Tier 1 reads as
    ``dynamic`` and Tier 2 as a run-wide ``module-object`` cause.
    """
    if _interpolated_names_main(node, source):
        return _MAIN_INTERPOLATED
    if value is not None and _names_main(value):
        return _MAIN_CONSTANT
    return None


def _names_main(value: str) -> bool:
    """Whether a decoded string names the main module for K-3 (R-698-1).

    A component counts when it equals a main name after splitting on
    :data:`_MAIN_COMPONENTS`, or when a default ``string.Template`` (``$``
    delimiter, default identifier pattern) would look it up
    (``"$__main__-x"``).
    """
    if "main__" not in value:
        return False
    return any(part in _MAIN_NAMES for part in _MAIN_COMPONENTS.split(value)) or any(
        (match["named"] or match["braced"]) in _MAIN_NAMES
        for match in Template.pattern.finditer(value)
    )


class _UndecodableError(Exception):
    """A string piece tree-sitter accepted that the K-3 decoder cannot read."""


_SIMPLE_ESCAPES = {
    "\n": "",
    "\\": "\\",
    "'": "'",
    '"': '"',
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
}
_HEX_ESCAPE_WIDTHS = {"x": 2, "u": 4, "U": 8}
_OCTAL_DIGITS = frozenset("01234567")
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_SURROGATES = re.compile("[\ud800-\udfff]")


def _decode_literal(prefix: str, quote: str, content: str) -> str | None:
    """The ``str`` CPython reads from the literal ``prefix + quote + content
    + quote``, or ``None`` where CPython rejects it or reads another type.

    ``prefix`` is lower case with any ``f`` already removed; ``quote`` is
    the opening delimiter. This decodes escapes as the compiler does instead
    of calling ``ast.literal_eval`` (#698, R-698-2 S-1): an invalid escape
    (``"\\d"``) is only a ``SyntaxWarning``, which a process warnings filter
    (``-W error::SyntaxWarning``) turns into a ``SyntaxError``, so the facts
    would depend on the filters; a ``catch_warnings`` block would change
    process-global state other threads share. ``\\N{...}`` names come from
    the host ``unicodedata``, as the compiler's do. Newlines are translated
    as the tokenizer does. The text is one literal token from the tree, so a
    delimiter inside ``content`` ends it early and gives ``None``; the main
    protection, though, is that the caller passes the delimiter it read from
    the token's own opening quote.
    """
    if prefix not in ("", "r", "u") or quote not in ("'", '"', "'''", '"""'):
        return None
    if "\0" in content or _SURROGATES.search(content):
        return None
    text = content.replace("\r\n", "\n").replace("\r", "\n") + quote
    end = len(text) - len(quote)
    raw = prefix == "r"
    single = len(quote) == 1
    out: list[str] = []
    index = 0
    while index < len(text):
        if text.startswith(quote, index):
            return "".join(out) if index == end else None
        char = text[index]
        if char == "\n" and single:
            return None
        if char != "\\":
            out.append(char)
            index += 1
            continue
        # ``text`` ends with the delimiter, so a backslash has a successor.
        if raw:
            out.append(char + text[index + 1])
            index += 2
            continue
        decoded = _escape(text, index, end)
        if decoded is None:
            return None
        out.append(decoded[0])
        index = decoded[1]
    return None


def _escape(text: str, index: int, end: int) -> tuple[str, int] | None:
    """The text the escape at ``text[index]`` (a backslash with a successor)
    decodes to in a non-raw literal, and the index after it; ``None`` where
    CPython rejects it. A ``\\N{...}`` name must close before ``end``."""
    char = text[index]
    escaped = text[index + 1]
    if escaped in _SIMPLE_ESCAPES:
        return _SIMPLE_ESCAPES[escaped], index + 2
    if escaped in _OCTAL_DIGITS:
        stop = index + 2
        while stop < index + 4 and stop < len(text) and text[stop] in _OCTAL_DIGITS:
            stop += 1
        return chr(int(text[index + 1 : stop], 8)), stop
    if escaped in _HEX_ESCAPE_WIDTHS:
        digits = text[index + 2 : index + 2 + _HEX_ESCAPE_WIDTHS[escaped]]
        if len(digits) != _HEX_ESCAPE_WIDTHS[escaped] or not set(digits) <= (
            _HEX_DIGITS
        ):
            return None
        point = int(digits, 16)
        if point > 0x10FFFF:
            return None
        return chr(point), index + 2 + len(digits)
    if escaped == "N":
        close = text.find("}", index + 3, end)
        if text[index + 2 : index + 3] != "{" or close <= index + 3:
            return None
        try:
            named = unicodedata.lookup(text[index + 3 : close])
        except KeyError:
            return None
        if len(named) != 1:
            # A named sequence: ``\\N{...}`` accepts single characters.
            return None
        return named, close + 1
    # An invalid escape keeps its backslash (a ``SyntaxWarning``).
    return char, index + 1


# A backslash-newline line continuation, after newline translation.
_CONTINUATION = "\\\n"


def _interpolated_names_main(node: Any, source: bytes) -> bool:
    """Whether an f-string or t-string expression names the main module
    anywhere in its source text (#698, R-698-3).

    CPython splits an f-string or t-string differently from tree-sitter in
    more places than a reader of its pieces can follow (a spec starting with
    ``=`` read as a walrus, ``{{`` after a nested field, comments in debug
    text), so the pieces are not read at all. Every string CPython hands to
    user code from such a node (a literal part, a format spec, debug text, a
    t-string interpolation's expression text) is built from the node's source
    text by decoding escapes, removing backslash-newline continuations,
    turning ``{{`` into ``{`` and dropping comments, and debug text joins the
    literal before it across the ``{``. None of those steps puts a character
    inside a run that was not adjacent to it once escapes, continuations and
    braces are removed, and none removes a newline from inside one; so a
    delivered component equal to a main name occurs as a substring of one of
    the views :func:`_source_names_main` checks. The source text is that of
    every string piece of the expression, joined across adjacent literals and
    ``+`` as CPython joins them; any other operand breaks the text. A piece
    whose quotes or bytes cannot be read fails closed.
    """
    if not _has_interpolated(node, source):
        return False
    parts: list[str] = []
    try:
        _string_sources(node, source, parts)
    except _UndecodableError:
        return True
    return _source_names_main("".join(parts))


def _string_sources(node: Any, source: bytes, parts: list[str]) -> None:
    # The text between the quotes of every string piece of a string
    # expression, in order; a non-string operand appends a break (NUL, which
    # no view removes) so no name is joined across it.
    kind = node.type
    if kind == "parenthesized_expression":
        inner = _unwrap(node, skip_comments=True)
        if inner is not node:
            _string_sources(inner, source, parts)
            return
    elif kind == "concatenated_string":
        for child in node.named_children:
            if child.type != "comment":
                _string_sources(child, source, parts)
        return
    elif kind == "binary_operator":
        operator = node.child_by_field_name("operator")
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if (
            operator is not None
            and operator.type == "+"
            and left is not None
            and right is not None
        ):
            _string_sources(left, source, parts)
            _string_sources(right, source, parts)
            return
    elif kind == "string":
        start = node.children[0] if node.children else None
        opening = _text(start, source) if start is not None else ""
        quote_at = min(
            (index for index in (opening.find("'"), opening.find('"')) if index >= 0),
            default=-1,
        )
        if start is None or start.type != "string_start" or quote_at < 0:
            raise _UndecodableError
        quote = opening[quote_at:]
        if "b" in opening[:quote_at].lower():
            # Bytes do not join a ``str``; their templates are plan risk R12.
            parts.append("\0")
            return
        # The node's end, not the end token: tree-sitter folds a raw
        # string's final ``\"`` into it (``rf"{x}\""``).
        if node.end_byte - len(quote) < start.end_byte:
            raise _UndecodableError
        text = source[start.end_byte : node.end_byte - len(quote)]
        try:
            parts.append(text.decode("utf-8"))
        except UnicodeDecodeError:
            raise _UndecodableError from None
        return
    parts.append("\0")


def _source_names_main(text: str) -> bool:
    """Whether a main name occurs in the source text of an f-string or
    t-string expression under any of its views (R-698-3).

    The views are the text with newlines translated as the tokenizer does,
    with or without backslash-newline continuations removed, each as written
    and with every escape decoded (an escape CPython rejects is kept as
    written), and each of those with ``{`` and ``}`` removed. Decoding as if
    every piece were non-raw only adds views: an escape never consumes a
    character of a name. Raw text needs no other view, since raw pieces keep
    their backslashes and the views as written already contain them.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    views: list[str] = []
    for base in (text, text.replace(_CONTINUATION, "")):
        for view in (base, _decode_escapes(base)):
            views += (view, view.replace("{", "").replace("}", ""))
    return any(name in view for view in views for name in _MAIN_NAMES)


def _decode_escapes(text: str) -> str:
    # Every escape of ``text`` decoded as in a non-raw literal; one CPython
    # rejects is kept as written.
    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char != "\\" or index + 1 == len(text):
            out.append(char)
            index += 1
            continue
        decoded = _escape(text, index, len(text)) or (char, index + 1)
        out.append(decoded[0])
        index = decoded[1]
    return "".join(out)


def _has_interpolated(node: Any, source: bytes) -> bool:
    # Whether :func:`_string_sources` would meet an f-string or t-string.
    kind = node.type
    if kind == "parenthesized_expression":
        inner = _unwrap(node, skip_comments=True)
        return inner is not node and _has_interpolated(inner, source)
    if kind == "concatenated_string":
        return any(_has_interpolated(child, source) for child in node.named_children)
    if kind == "binary_operator":
        operator = node.child_by_field_name("operator")
        return (
            operator is not None
            and operator.type == "+"
            and any(
                side is not None and _has_interpolated(side, source)
                for side in (
                    node.child_by_field_name("left"),
                    node.child_by_field_name("right"),
                )
            )
        )
    if kind != "string" or not node.children:
        return False
    opening = _text(node.children[0], source).lower()
    return node.children[0].type == "string_start" and (
        "f" in opening or "t" in opening
    )


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
        if child.type == "string_start":
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
        raw = _text(child, source)
        if child.type == "string_end":
            # After an interpolation, tree-sitter folds a raw string's final ``\"`` into the end
            # token (``rf"{'x'}\""``), and that text is content.
            if not raw.endswith(quote):
                return None
            raw = raw[: len(raw) - len(quote)]
        value = _decode_literal(plain, quote, raw.replace("{{", "{").replace("}}", "}"))
        if value is None:
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


def _type_parameter_names(params: Any) -> list[Any]:
    """The name of each parameter in a ``type_parameter`` list (``T`` of
    ``T``, ``T: B``, ``*T``, ``**T``), not the identifiers of its bound,
    constraints or default. The grammar parses a default (``U = int``) as an
    error node: a parameter after one, or inside one, gets no name here,
    which only makes its bindings phantom."""
    found: list[Any] = []
    after_separator = False
    for child in params.children:
        if child.type in ("[", ","):
            after_separator = True
            continue
        if child.type == "comment":
            continue
        if child.type == "type" and after_separator:
            inner = child.named_children[0] if child.named_children else None
            if inner is not None and inner.type == "constrained_type":
                head = inner.named_children[0] if inner.named_children else None
                inner = None
                if head is not None and head.type == "type" and head.named_children:
                    inner = head.named_children[0]
            elif inner is not None and inner.type in (
                "splat_type",
                "list_splat",
                "dictionary_splat",
            ):
                inner = next(
                    (c for c in inner.named_children if c.type == "identifier"), None
                )
            if inner is not None and inner.type == "identifier":
                found.append(inner)
        after_separator = False
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


def _checked_import(info: Mapping[str, str]) -> tuple[str, str | None] | None:
    """The checked module (``pickle``, ``_pickle``, ``timeit``, ``runpy``)
    an import record binds and the member it binds (``None`` for the module
    itself): the module (``import pickle [as p]``, or a from-import of the
    module's name out of any other module, R-699-3: ``from logging.handlers
    import pickle``) or a member (``from pickle import dumps``); ``None``
    for any other import. A from-import of ``code``, ``trace`` or
    ``profile`` out of a module outside the standard library binds that
    module's name under the closed allow-list of
    :data:`_REEXPORT_CHECKED` (R-699-5)."""
    if info.get("form") == "import":
        module, member = info.get("bound"), None
    else:
        module, member = info.get("module"), info.get("name")
        if module not in _CHECKED_MODULES and member in _CHECKED_MODULES:
            module, member = member, None
        elif member in _REEXPORT_CHECKED and not _stdlib_path(module or ""):
            return member, None
    if module not in _CHECKED_MODULES:
        return None
    assert module is not None
    return module, member


def _stdlib_path(module: str) -> bool:
    """Whether an import record's module path starts with a standard-library
    name (:data:`_S2_STDLIB_MODULES`). A relative path (``.compat``) starts
    with an empty component, so it never does."""
    return module.split(".", 1)[0] in _S2_STDLIB_MODULES


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


def _patch_applied(node: Any, source: bytes) -> bool:
    """Whether ``X.patch`` (``node``) is applied where it is read: called
    directly, or the receiver of a directly called ``.object``, ``.dict`` or
    ``.multiple`` (through parentheses)."""
    if _callee_call(node) is not None:
        return True
    outer = node
    while outer.parent is not None and outer.parent.type == "parenthesized_expression":
        outer = outer.parent
    parent = outer.parent
    if (
        parent is None
        or parent.type != "attribute"
        or not _same(outer, parent.child_by_field_name("object"))
    ):
        return False
    method = parent.child_by_field_name("attribute")
    return (
        method is not None
        and _text(method, source) in _PATCH_METHODS
        and _callee_call(parent) is not None
    )


def _is_patch_attribute(node: Any, source: bytes) -> bool:
    """Whether ``node`` is ``X.patch`` for any ``X`` (through parentheses)."""
    node = _unwrap(node, skip_comments=True)
    if node.type != "attribute":
        return False
    attribute = node.child_by_field_name("attribute")
    return attribute is not None and _text(attribute, source) == "patch"


def _name_part(ident: Any) -> bool:
    """Whether an identifier is the name of an attribute (``ns`` in
    ``K.ns``) or of a keyword argument: part of a larger node, not a value."""
    parent = ident.parent
    if parent is None:
        return False
    if parent.type == "attribute":
        return _same(ident, parent.child_by_field_name("attribute"))
    if parent.type == "keyword_argument":
        return _same(ident, parent.child_by_field_name("name"))
    return False


def _binding_position(ident: Any) -> bool:
    """Whether an identifier is bound here rather than used: a parameter, a
    ``def``/``class`` name, an import, an assignment, ``for``, ``with`` or
    walrus target, ``global``/``nonlocal``/``del``, or a pattern capture."""
    if _scope_binding_name(ident) or _import_context(ident):
        return True
    current = ident
    parent = ident.parent
    while parent is not None and parent.type in (
        "pattern_list",
        "tuple_pattern",
        "list_pattern",
        "list_splat_pattern",
        "parenthesized_expression",
        "as_pattern_target",
    ):
        current, parent = parent, parent.parent
    if parent is None:
        return False
    if parent.type in ("assignment", "for_statement", "for_in_clause"):
        return _same(current, parent.child_by_field_name("left"))
    if parent.type == "named_expression":
        return _same(current, parent.child_by_field_name("name"))
    if parent.type in ("global_statement", "nonlocal_statement", "delete_statement"):
        return True
    if parent.type == "as_pattern":
        return _same(current, parent.child_by_field_name("alias"))
    node = parent
    while node is not None and node.type not in ("case_clause", "block", "module"):
        if node.type == "case_pattern":
            return True
        node = node.parent
    return False


def _statement_call(call: Any) -> bool:
    """Whether a call's result is discarded: the whole expression of an
    expression statement (through parentheses)."""
    parent = call.parent
    while parent is not None and parent.type == "parenthesized_expression":
        parent = parent.parent
    return parent is not None and parent.type == "expression_statement"


def _imports_from(
    ident: Any, source: bytes, module: str, members: frozenset[str] | None
) -> str | None:
    """The module (``members`` is ``None``) or imported member a binding
    identifier is bound to by ``import <module> [as x]`` or by ``from
    <module> import <member> [as x]`` for a member in ``members``; ``None``
    for any other binding."""
    statement = ident.parent
    while statement is not None and statement.type not in _IMPORT_STATEMENTS:
        statement = statement.parent
    if statement is None:
        return None
    if members is None:
        if statement.type != "import_statement":
            return None
        for child in statement.named_children:
            if child.type == "aliased_import":
                alias = child.child_by_field_name("alias")
                name = child.child_by_field_name("name")
                if (
                    alias is not None
                    and _same(alias, ident)
                    and name is not None
                    and _dotted_parts(name, source) == [module]
                ):
                    return module
            elif child.type == "dotted_name" and child.named_children:
                if _same(child.named_children[0], ident):
                    if _dotted_parts(child, source)[:1] == [module]:
                        return module
                    return None
        return None
    if statement.type != "import_from_statement":
        return None
    dots, parts = _module_parts(statement, source)
    if dots or parts != [module]:
        return None
    for last, bound in _from_import_names(statement, source):
        if bound.type == "dotted_name" and bound.named_children:
            bound = bound.named_children[0]  # ``from operator import setitem``
        if _same(bound, ident) and last in members:
            return last
    return None


def _binding_names(target: Any, source: bytes) -> set[str]:
    """The names a target binds: identifiers through tuple, list, starred and
    parenthesized forms, an attribute target's name (``self.mm``) and a
    subscript target's constant key (``K.__dict__["ns"]``)."""
    found: set[str] = set()
    stack = [target]
    while stack:
        current = stack.pop()
        if current.type == "identifier":
            found |= _spellings(current, source)
        elif current.type == "attribute":
            attribute = current.child_by_field_name("attribute")
            if attribute is not None:
                found |= _spellings(attribute, source)
        elif current.type == "subscript":
            for index, child in enumerate(current.children):
                if current.field_name_for_child(index) == "subscript":
                    value = _constant_string(child, source)
                    if value is not None:
                        found.add(value)
        else:
            stack.extend(current.named_children)
    return found


def _constant_arguments(node: Any, source: bytes) -> set[str]:
    """The constant-string arguments of a call."""
    return {
        value
        for argument in _call_arguments(node)
        for value in [_constant_string(argument, source)]
        if value is not None
    }


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
    tier2: bool = True,
) -> dict[str, Any]:
    """Return partial scope facts: the goal and one outcome per call.

    With ``tier2`` (``imports`` mode), also the Tier 2 module facts of
    :mod:`.py_modules`; other modes never read them (#705 E6-8).

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
    # Tier 2 (plan 9.4, PR 6): a call whose lookup met two or more imports
    # and nothing else (they narrow to the group in ``imports`` mode), and
    # the member chain of a member callee whose head is imported.
    groups: dict[str, Any] = {}
    chains: dict[str, Any] = {}
    for fact in call_facts:
        start = int(fact["callee_byte_start"])
        end = int(fact["callee_byte_end"])
        node = root.named_descendant_for_byte_range(start, end)
        if node is None or (node.start_byte, node.end_byte) != (start, end):
            # No node matches the callee span: leave the entry out, which the
            # engine reports as no-binding-fact (5.4).
            continue
        head = _callee_head(node)
        key = f"{start}:{end}"
        outcome = analysis.lookup(head) if head is not None else _none("unbound")
        bindings[key] = outcome
        if head is None or not tier2:
            continue
        group = py_modules.import_group(analysis, head, outcome)
        if group:
            groups[key] = group
        if group or outcome.get("outcome") == IMPORT:
            chain = py_modules.member_chain(node, head, source)
            if chain is not None:
                chains[key] = chain
    if not tier2:
        return {"goal": "module", "bindings": bindings}
    own = path or ""
    own_ref = py_modules.dotted_name(own)[0] if own.endswith(".py") else ""
    exports, module_bindings = py_modules.module_facts(
        analysis, groups, chains, own_ref
    )
    return {
        "goal": "module",
        "bindings": bindings,
        "exports": exports,
        "module_bindings": module_bindings,
    }
