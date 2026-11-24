"""Tier 2 call resolution for Python (plan sections 9.4-9.8, PR 6).

Two halves, like :mod:`.js_modules` and :mod:`.modules` for JS/TS:

* :func:`module_facts` runs inside the per-file analyzer, after the Tier 1
  scope pass (:class:`.py_scope._Analysis`), and records what other files
  need: the module-scope **exports** (each name's Tier 1 module lookup), and
  ``module_bindings``: the modules the file imports, every use of an
  imported module object, literal module acquisitions, star imports, dotted
  constant strings, run-wide causes and parse hazards.
* :func:`build_py_module_run` and :func:`resolve_import` run at assembly,
  with no filesystem access: they index the run's Python files by dotted
  module name, compute which module globals other files may write (the
  taints, closing treesitter-chunker#697), scope causes and taints by the
  caller (owner decision O-2) and resolve import bindings.

**Binding proof (6.3).** An import binding proves a target only when module
resolution (9.5) finds exactly one run file and the name lookup in it (9.6)
ends, through at most three re-export hops, at definitions the target's own
Tier 1 lookup proves. Every other case is ``none(reason)``.

**Module paths (9.5).** Dotted names are resolved one component at a time
from the run root (the ``sys.path`` entry): at every component a regular
package (``D/__init__.py``) comes before a module (``D.py``), which comes
before a namespace directory; a module before the last component gives
``module-not-found``. An absolute import whose first component exists in the
importer's own directory (not the root) gives ``script-dir-shadow``; one whose
first component is a standard-library module name (:data:`STDLIB_MODULES`,
pinned) gives ``external-module``, because builtin and frozen modules win
over any file. A component that names a directory the run never collects
(``build``, ``dist``, ...) gives ``unknown-variant``. Relative imports start
at the importer's package; leaving the root gives ``outside-root``.

**Name lookup (9.6).** For name ``x`` in module M: M binding ``x`` and a
submodule ``x`` give ``attr-submodule-conflict``; a submodule only is a
module (calling it is ``non-callable``; it may head a member chain); M's
module-scope binding gives its Tier 1 module lookup (an import is a hop,
which covers ``__init__`` re-exports); anything else is
``export-not-found`` (or M's own reason: ``dynamic-scope``,
``star-import``, ``unmapped``). More than three hops give ``hop-limit``,
revisiting a pair gives ``cycle``.

**Writes from other files (#697).** An imported module object may appear
only in a CLOSED allow-list of uses (:func:`_use_position`): an attribute
read (a member chain), a call of one, an attribute write (``svc.t = f``,
``del svc.t``, ``svc.t += 1``, a ``for``/``with`` target, and ``setattr`` /
``delattr`` with a constant name, the builtin verified by the ordinary
lookup at the use site), which taints exactly that name, and an operand of
``is``/``is not``/``not`` or a bare ``if``/``while`` test. Every other use
(an argument such as ``monkeypatch.setattr(svc, 't', f)``, a return, an
assignment value, a container, a dunder attribute such as ``__dict__``)
taints the whole module, and through it every module it exposes as an
attribute (its submodules and the modules it imports). A file that reads its
own namespace (any token spelling ``globals``, ``locals``, ``vars``,
``f_globals``, ``__globals__``, ``__import__``, ``getmodule``, ``builtins``
and the rest of :data:`_NAMESPACE_TOKENS`, a bare ``eval``/``exec``, an
import of ``__main__``; :func:`_namespace_handout`) hands every import
binding in it to code no use rule sees, so each is such a use, and a
package ``__init__.py`` hands out its submodules too
(treesitter-chunker#724, R-724-1). A closed allow-list exempts a token use
whose object is provably not the file's namespace (R-724-2:
``exec(code, mod.__dict__)`` and ``spec.loader.exec_module(mod)`` on a
fresh ``types.ModuleType`` local, ``__import__`` of a constant foreign module; see
:func:`_not_own_namespace`). R-724-4 voids those exemptions in a file whose
constants spell a token or a factory name as a word. A write to ``__class__``
voids the receiver proof. R-724-4 also adds resolvers given the file's own name and pytest's
``request.module`` (:func:`_own_module_route`). A read of a function-local import binding from
a nested scope is an escape too: a closure cell is reachable from another
module (R-706-3, :func:`_nested_import_read`). A module returned by a
*tracked getter* (a plain module-level ``def`` in a
file that passes H1, :func:`_introspects`) is no escape: its uses are
followed through the call result, member calls and function-local aliases
(a read from a nested scope is an escape: a closure cell is reachable from
another module) by the same allow-list, and anything else taints what the
getter may return (treesitter-chunker#706, :func:`_scan_results`,
:meth:`_Builder.walk_result`). Literal acquisitions
(``importlib.import_module('svc')``, ``__import__('svc')``,
``sys.modules['svc']``) taint their target wholly; dotted constant strings
(``mock.patch('svc.t')``, ``monkeypatch.setattr('svc.t', f)``) taint the
name they spell. A written module name denotes the run module of that dotted
name and, for an absolute name written from a file below the root, the one
in the writer's own directory (a script or pytest's ``rootdir`` insertion
puts it first on ``sys.path``). No other module can be meant: within one
process a dotted name is one module object, and the same file imported under
another name (another root) is a separate object a write does not reach. A
taint makes every proof of that name in that module fail closed, the
module's own Tier 1 module-scope proofs included (``imports`` mode only:
``structural`` stays as it was).

**Run-wide causes (E5-3 analog).** Routes that can obtain or write any
module: ``evaluator`` (code run from a string, a payload or an annotation,
as Tier 1's shared classifier decides it: ``exec``, ``eval``, ``execfile``,
``compile`` and ``breakpoint`` by use-site lookup, the stdlib string-code
helpers, ``pickle`` loads, annotation evaluators, ``marshal`` and loader
methods; treesitter-chunker#699 S2), ``dynamic-loader`` (a non-literal ``import_module`` or
``__import__``, any other ``importlib`` use off a closed list, ``runpy``,
``imp``, ``zipimport``, string-to-module resolvers), ``module-system``
(``sys.modules`` off its closed list, writes of ``sys.path``,
``sys.meta_path``, ``sys.path_hooks``, ``sys.path_importer_cache``, the
``sys`` module handed on, ``__path__``, ``site.addsitedir``),
``module-object`` (another module's namespace: ``__globals__``,
``f_globals``, ``f_builtins``, a frame's ``f_locals`` other than a read,
``getmodule``, ``pythonapi``, the ``builtins`` module, ``__main__``; a
``__main__`` string is classified by the one rule Tier 1 uses, #698),
``unparsed-file`` and ``unresolvable-writer``. As for TS/JS (PR 5), a cause
shuts off Tier 2 for the callers it applies to; Tier 1 proofs keep their
``structural`` result except where a taint names their module global.
A write of a function's ``__code__``, ``__closure__``, ``__defaults__`` or
``__kwdefaults__`` in any file makes a proven definition run other code: a
``module-object`` cause (#705 N-1). Since treesitter-chunker#699 B-1
(ruling R-699-1, reversing #705 Q2) any mention of a code-object source is
one too, reads included: ``type(f)(f.__code__, {"t": len})()`` runs a
function's code under substitute globals with neither ``exec`` nor
``eval``.

**Owner decision O-2.** Causes and taints that originate in test files
(:func:`is_test_path`) apply only to callers in test files, unless a
production file reaches the test file through an import edge (it is then
production).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence, Set as AbstractSet
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

HOP_LIMIT = 3

# Run-wide causes (each reason is ``run-tainted:<cause>``), in report order.
CAUSE_EVALUATOR = "evaluator"
CAUSE_DYNAMIC_LOADER = "dynamic-loader"
CAUSE_MODULE_SYSTEM = "module-system"
CAUSE_MODULE_OBJECT = "module-object"
CAUSE_UNPARSED_FILE = "unparsed-file"
CAUSE_UNRESOLVABLE_WRITER = "unresolvable-writer"
SHUTOFF_CAUSES = (
    CAUSE_EVALUATOR,
    CAUSE_DYNAMIC_LOADER,
    CAUSE_MODULE_SYSTEM,
    CAUSE_MODULE_OBJECT,
    CAUSE_UNPARSED_FILE,
    CAUSE_UNRESOLVABLE_WRITER,
)
# Reasons of a tainted name or module.
REASON_NAME_TAINT = "reassigned"
REASON_MODULE_TAINT = "module-escape"
# A package with a module-level ``__getattr__`` (PEP 562): ``from pkg import
# sub``, ``import pkg.sub as m`` and ``pkg.sub`` call it before the
# submodule is imported, so the attribute may be anything (#705 E6-3).
REASON_MODULE_GETATTR = "module-getattr"

# Owner decision O-2, the Python test classifier: closed, case-sensitive and
# path-based. A basename ``test_*.py``, ``*_test.py`` or ``conftest.py``
# (pytest loads it only), or any directory segment exactly ``tests`` or
# ``test``. A test file a production file reaches is production.
TEST_DIRECTORIES = frozenset({"tests", "test"})
TEST_PREFIX = "test_"
TEST_SUFFIX = "_test.py"
TEST_CONFTEST = "conftest.py"

# ``chunker.symbol_graph.SKIP_PARTS`` (a test pins the copy): a package of
# one of these names is never collected.
SKIPPED_DIRECTORIES = frozenset(
    {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".tox",
        ".pytest_cache",
        "build",
        "dist",
        ".eggs",
        "archive",
    }
)

# The CPython 3.14 ``sys.stdlib_module_names``, plus the modules 3.12 still
# had and 3.13 removed (a test pins it against the running interpreter).
# An absolute import whose first component is one of them gives
# ``external-module``: builtin and frozen modules win over any file, and
# whether the root precedes the standard library on ``sys.path`` depends on
# how the program starts.
STDLIB_MODULES = frozenset(
    {
        "__future__", "_abc", "_aix_support", "_android_support", "_apple_support",
        "_ast", "_ast_unparse", "_asyncio", "_bisect", "_blake2", "_bz2",
        "_codecs", "_codecs_cn", "_codecs_hk", "_codecs_iso2022", "_codecs_jp",
        "_codecs_kr", "_codecs_tw", "_collections", "_collections_abc",
        "_colorize", "_compat_pickle", "_compression", "_contextvars", "_csv",
        "_ctypes", "_curses", "_curses_panel", "_datetime", "_dbm", "_decimal",
        "_elementtree", "_frozen_importlib", "_frozen_importlib_external",
        "_functools", "_gdbm", "_hashlib", "_heapq", "_hmac", "_imp", "_interpchannels",
        "_interpqueues", "_interpreters", "_io", "_ios_support", "_json", "_locale",
        "_lsprof", "_lzma", "_markupbase", "_md5", "_multibytecodec",
        "_multiprocessing", "_opcode", "_opcode_metadata", "_operator", "_osx_support",
        "_overlapped", "_pickle", "_posixshmem", "_posixsubprocess", "_py_abc",
        "_py_warnings", "_pydatetime", "_pydecimal", "_pyio", "_pylong", "_pyrepl",
        "_queue", "_random", "_remote_debugging", "_scproxy", "_sha1", "_sha2", "_sha3",
        "_signal", "_sitebuiltins", "_socket", "_sqlite3", "_sre", "_ssl", "_stat",
        "_statistics", "_string", "_strptime", "_struct", "_suggestions", "_symtable",
        "_sysconfig", "_thread", "_threading_local", "_tkinter", "_tokenize",
        "_tracemalloc", "_types", "_typing", "_uuid", "_warnings", "_weakref",
        "_weakrefset", "_winapi", "_wmi", "_zoneinfo", "_zstd", "abc", "aifc",
        "annotationlib", "antigravity", "argparse", "array", "ast", "asynchat",
        "asyncio", "asyncore", "atexit", "audioop", "base64", "bdb", "binascii",
        "bisect", "builtins", "bz2", "cProfile", "calendar", "cgi", "cgitb", "chunk",
        "cmath", "cmd", "code", "codecs", "codeop", "collections", "colorsys",
        "compileall", "compression", "concurrent", "configparser", "contextlib",
        "contextvars", "copy", "copyreg", "crypt", "csv", "ctypes", "curses",
        "dataclasses", "datetime", "dbm", "decimal", "difflib", "dis", "distutils",
        "doctest", "email", "encodings", "ensurepip", "enum", "errno", "faulthandler",
        "fcntl", "filecmp", "fileinput", "fnmatch", "fractions", "ftplib", "functools",
        "gc", "genericpath", "getopt", "getpass", "gettext", "glob", "graphlib", "grp",
        "gzip", "hashlib", "heapq", "hmac", "html", "http", "idlelib", "imaplib",
        "imghdr", "imp", "importlib", "inspect", "io", "ipaddress", "itertools", "json",
        "keyword", "lib2to3", "linecache", "locale", "logging", "lzma", "mailbox",
        "mailcap", "marshal", "math", "mimetypes", "mmap", "modulefinder", "msilib",
        "msvcrt", "multiprocessing", "netrc", "nis", "nntplib", "nt", "ntpath",
        "nturl2path", "numbers", "opcode", "operator", "optparse", "os",
        "ossaudiodev", "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil",
        "platform", "plistlib", "poplib", "posix", "posixpath", "pprint", "profile",
        "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc", "pydoc_data",
        "pyexpat", "queue", "quopri", "random", "re", "readline", "reprlib",
        "resource", "rlcompleter", "runpy", "sched", "secrets", "select", "selectors",
        "shelve", "shlex", "shutil", "signal", "site", "smtpd", "smtplib", "sndhdr",
        "socket", "socketserver", "spwd", "sqlite3", "sre_compile", "sre_constants",
        "sre_parse", "ssl", "stat", "statistics", "string", "stringprep", "struct",
        "subprocess", "sunau", "symtable", "sys", "sysconfig", "syslog", "tabnanny",
        "tarfile", "telnetlib", "tempfile", "termios", "textwrap", "this",
        "threading", "time", "timeit", "tkinter", "token", "tokenize", "tomllib",
        "trace", "traceback", "tracemalloc", "tty", "turtle", "turtledemo", "types",
        "typing", "unicodedata", "unittest", "urllib", "uu", "uuid", "venv",
        "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref",
        "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
        "zoneinfo",
    }
)  # fmt: skip

# Standard-library modules this rule set classifies. A module object of one
# of them obtained without an import the rules can follow
# (``importlib.import_module('sys')``, ``sys.modules['importlib']``) is a
# run-wide ``dynamic-loader`` cause.
_CLASSIFIED_MODULES = frozenset(
    {
        "importlib",
        "builtins",
        "__builtin__",
        "sys",
        "runpy",
        "imp",
        "zipimport",
        "__main__",
        "__mp_main__",
        "pkgutil",
        "pydoc",
        "site",
        "gc",
        "inspect",
        "ctypes",
        "logging",
    }
)
# ``importlib`` uses that load or write nothing by name (a closed list). A
# use matches when the dotted path from ``importlib`` starts with one entry.
_INERT_IMPORTLIB = (
    ("importlib", "metadata"),
    ("importlib", "resources"),
    ("importlib", "abc"),
    ("importlib", "invalidate_caches"),
    ("importlib", "util", "find_spec"),
)
_LOADER_MODULES = frozenset({"runpy", "imp", "zipimport"})
_LOADER_PATHS = frozenset(
    {
        ("pkgutil", "resolve_name"),
        ("pkgutil", "get_loader"),
        ("pkgutil", "find_loader"),
        ("pydoc", "locate"),
        ("pydoc", "safeimport"),
        ("pydoc", "importfile"),
        ("logging", "config", "_resolve"),
        ("logging", "config", "_importer"),
    }
)
_SITE_PATHS = frozenset({("site", "addsitedir"), ("site", "main")})
_SYS_MODULE_GETTERS = frozenset({"get", "pop", "setdefault", "__getitem__"})
_SYS_PATH_NAMES = frozenset({"path", "meta_path", "path_hooks", "path_importer_cache"})
# Names that reach another module's namespace in any identifier position
# (an attribute, a keyword argument) or as a component of a constant string.
_MODULE_OBJECT_NAMES = frozenset(
    {
        "__globals__",
        "f_globals",
        "f_builtins",
        "getmodule",
        "__builtins__",
        "builtins",
        "__builtin__",
        "bltns",
        "__main__",
        "__mp_main__",
        # C-level access to any object (``PyImport_AddModule``,
        # ``PyObject_SetAttr``) and the frame-locals writer.
        "pythonapi",
        "PyFrame_LocalsToFast",
    }
)
# A frame's ``f_locals``: for a module-level frame it is the module's
# globals, and for a function frame a write-through proxy of its locals (PEP
# 667). treesitter-chunker#699 PY-9 (ruling R-699-1 Q5 and B-6): any
# spelling is a ``module-object`` cause, reads included, and so are the
# other frame-locals proxies Tier 1 lists (``inspect.getargvalues(fr)
# .locals``, ``getgeneratorlocals``, ``getcoroutinelocals``,
# ``getasyncgenlocals``, ``pdb``'s ``curframe_locals``). A file that reads a
# frame another file hands it (``gi_frame``, ``cr_frame``, ``ag_frame``,
# ``tb_frame``, ``inspect.trace()``, ``sys._getframe(1)``) can take a patcher
# or module object out of that frame's locals and apply it out of sight, and
# every way to read them spells one of these names. Token level (R-724-1): an
# identifier in any role, or a word of a constant string.
_FRAME_LOCALS = "f_locals"
_FRAME_READERS = frozenset(
    {
        _FRAME_LOCALS,
        "getargvalues",
        "getgeneratorlocals",
        "getcoroutinelocals",
        "getasyncgenlocals",
        "curframe_locals",
        # R-699-10 item 1: ``inspect.getclosurevars(f)`` hands out the
        # contents of ``f``'s closure cells (``.nonlocals``) and the globals
        # it names (``.globals``), another file's imported module among
        # them, with no cell or frame name spelled.
        "getclosurevars",
    }
)
# treesitter-chunker#699 PY-6: a closure cell's ``cell_contents`` other than
# a plain read (an attribute target, ``del``, the descriptor used as a
# receiver: ``type(c).cell_contents.__set__(c, v)``; any other identifier
# role; a word of a constant string: ``setattr(c, "cell_contents", v)``)
# rewrites a cell another file's function closes over: a ``module-object``
# cause. ``__closure__`` needs no rule of its own: every mention is a cause
# since B-1.
_CELL_CONTENTS = "cell_contents"
_RESOLVER_NAMES = frozenset({"resolve_name", "safeimport", "find_class"})
# Dunder attributes of a module object that read a plain value. Any other
# dunder (``__dict__``, ``__setattr__``, ``__class__``, ``__spec__``,
# ``__loader__``, ``__path__``) taints the module wholly.
_SAFE_DUNDERS = frozenset(
    {
        "__name__",
        "__qualname__",
        "__doc__",
        "__file__",
        "__module__",
        "__version__",
        # #705 E6-7: a read of a package's search path or spec hands out a
        # list of directories or a spec, not the module namespace. Changing
        # ``__path__`` redirects later imports, which the ``module-system``
        # cause on any ``__path__`` spelling already covers.
        "__path__",
        "__spec__",
    }
)
# #705 N-1: function attributes whose write makes a function run other code
# (or with other defaults) while every edge still names its definition:
# ``f = svc.t; f.__code__ = other.t.__code__`` in any file made CPython run
# ``OTHER.t``'s body for ``use.py``'s ``from svc import t`` (the president's
# ``h5_code_alias``). A write of one in any file is a run-wide
# ``module-object`` cause, scoped by O-2.
_CODE_ATTRIBUTES = frozenset(
    {"__code__", "__closure__", "__defaults__", "__kwdefaults__"}
)
# Outcomes of a use-site lookup that prove the name is the file's own
# binding, not the builtin or an import.
_OWN_BINDINGS = frozenset({"parameter", "local-variable", "expression-bound"})
_DOTTED_STRING = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:[.:][A-Za-z_][A-Za-z0-9_]*)+")
_LONE_CR = re.compile(rb"\r(?!\n)")
_CODING = re.compile(rb"^[ \t\f]*#.*?coding[:=][ \t]*([-\w.]+)")
# Bytes CPython and tree-sitter may read differently with no tree error.
_HAZARD_BYTES = (b"\x00", b"\x0b", b"\x1a")
_SAFE_CODINGS = frozenset({"utf-8", "ascii", "us-ascii"})


def _none(reason: str) -> dict[str, Any]:
    return {"outcome": "none", "reason": reason}


def is_test_path(path: str) -> bool:
    """Whether a display path names Python test code by the O-2 classifier."""
    *directories, name = path.split("/")
    if any(part in TEST_DIRECTORIES for part in directories):
        return True
    return (
        name == TEST_CONFTEST
        or (name.startswith(TEST_PREFIX) and name.endswith(".py"))
        or name.endswith(TEST_SUFFIX)
    )


# ---------------------------------------------------------------------------
# The analyzer half


def _normal_coding(name: bytes) -> str:
    """CPython's ``get_normal_name`` for a coding declaration."""
    text = name.decode("ascii", errors="replace").lower().replace("_", "-")
    if text == "utf-8" or text.startswith("utf-8-") or text == "utf8":
        return "utf-8"
    return text


def parse_hazard(source: bytes, root: Any) -> str | None:
    """Why CPython and tree-sitter may read this file differently with no
    tree error (E5-7 analog), or ``None``. Simple, broad byte rules: a lone
    CR, a NUL, vertical tab or Ctrl-Z byte, a PEP 263 coding declaration
    other than UTF-8 or ASCII (or any with a BOM), both tab- and
    space-indented lines (CPython's ``TabError`` rules), and a backslash
    continuation that is not exactly a backslash before the line break. The
    Tier 1 rules (5.3) already reject a space before a tab and a form feed
    in indentation, and a line starting with a backslash."""
    if _LONE_CR.search(source):
        return "lone-cr"
    if any(byte in source for byte in _HAZARD_BYTES):
        return "control-byte"
    lines = source.split(b"\n")
    for line in lines[:2]:
        match = _CODING.match(line.lstrip(b"\xef\xbb\xbf"))
        if match is not None:
            if source.startswith(b"\xef\xbb\xbf"):
                return "bom-and-coding"
            if _normal_coding(match.group(1)) not in _SAFE_CODINGS:
                return "coding"
    tabbed = spaced = False
    for line in lines:
        stripped = line.lstrip(b" \t\f")
        if not stripped.strip():
            continue
        leading = line[: len(line) - len(stripped)]
        tabbed = tabbed or b"\t" in leading
        spaced = spaced or b" " in leading
    if tabbed and spaced:
        return "tab-space-mix"
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "line_continuation":
            text = source[node.start_byte : node.end_byte]
            if text not in (b"\\\n", b"\\\r\n", b"\\"):
                return "continuation"
            if text == b"\\" and source[node.end_byte : node.end_byte + 1] not in (
                b"\n",
                b"\r",
            ):
                return "continuation"
        stack.extend(node.children)
    return None


def _join(base: str, name: str) -> str:
    """``base`` (a module reference, possibly only dots) joined with ``name``."""
    if not base or base.endswith("."):
        return base + name
    return f"{base}.{name}"


@dataclass
class _Facts:
    """What one Python file contributes to Tier 2, built by
    :func:`module_facts`."""

    imports: set[str] = field(default_factory=set)
    uses: set[tuple[str, ...]] = field(default_factory=set)
    taints: set[tuple[str, str]] = field(default_factory=set)
    stars: set[str] = field(default_factory=set)
    strings: set[str] = field(default_factory=set)
    shutoff: set[str] = field(default_factory=set)
    getters: dict[str, set[tuple[str, ...]]] = field(default_factory=dict)


def module_facts(
    analysis: Any,
    groups: Mapping[str, Sequence[Mapping[str, str]]],
    chains: Mapping[str, Sequence[str]],
    own_ref: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """``(exports, module_bindings)`` for one analyzed Python file.

    ``analysis`` is the finished :class:`.py_scope._Analysis`; ``groups``
    and ``chains`` are the per-call import groups and member chains, keyed
    by callee span; ``own_ref`` is the file's own dotted module name (for
    ``sys.modules[__name__]``).
    """
    from . import py_scope as ps

    source = analysis.source
    facts = _Facts()
    exports = {
        name: analysis._module_lookup(name)
        for name in sorted(analysis.module.bindings)
        if name.isidentifier()
    }
    missing = analysis._module_lookup("0")
    missing_reason = (
        "export-not-found"
        if missing.get("reason") == "unbound"
        else str(missing.get("reason") or "export-not-found")
    )
    import_infos: dict[str, list[Mapping[str, str]]] = {}
    # #705 E6-2: every import binding that lands in the module namespace,
    # whatever the Tier 1 lookup of the name says (conditional, repeated, in
    # a dynamic file): another file may reach the module it holds as an
    # attribute of this one.
    module_imports: dict[str, list[dict[str, str]]] = {}
    for scope, name, binding in analysis.events:
        if binding.cls != ps.IMPORT or not binding.info:
            continue
        info = binding.info
        if info.get("module") == "__future__":
            continue
        import_infos.setdefault(name, []).append(info)
        if scope.kind == ps._MODULE or name in scope.globals:
            entry = dict(info)
            if entry not in module_imports.setdefault(name, []):
                module_imports[name].append(entry)
        if scope.kind == ps._CLASS or name in scope.globals or name in scope.nonlocals:
            # A class attribute (``K.svc``) or a binding redirected to another
            # scope holds the module where no use rule sees it.
            facts.uses.add(_record(info, "value", ()))
    _scan_imports(analysis, facts)
    own_submodules = _own_submodules(analysis, own_ref, facts.stars)
    routes_seen: list[bool] = []
    handout = _namespace_handout(analysis, frozenset(import_infos), routes_seen)
    # H1 (#706): a file that reaches its namespace without spelling a name
    # has no tracked getters and no result aliases.
    gate = _introspects(analysis, handout, routes_seen)
    _scan_uses(
        analysis, facts, import_infos, {} if gate else _tracked_getters(analysis)
    )
    _scan_results(analysis, facts, import_infos, gate)
    if handout is None or handout:
        # #724: the file hands its namespace, and the import bindings in it,
        # to code the use rules do not follow.
        handed = [
            info
            for name, infos in import_infos.items()
            if handout is None or name in handout
            for info in infos
        ]
        facts.uses.update(_record(info, "value", ()) for info in handed)
        if any((_dotted(info) or [""])[0] in _MODULE_SYSTEM_MODULES for info in handed):
            # R-724-1 item 4: a handed-out ``sys``, ``importlib`` or
            # ``builtins`` reaches every module (``d["sys"].modules["svc"]``),
            # as passing it on does.
            facts.shutoff.add(CAUSE_MODULE_SYSTEM)
        if handout is None and analysis.module_path.package_init and own_ref:
            # R-724-1 item 2: a package's namespace holds its submodules,
            # which are not import bindings (``globals()["svc"]`` in
            # ``pkg/__init__.py`` is ``pkg.svc``). As for
            # ``sys.modules[__name__]``, the package is tainted wholly, and
            # through it every submodule.
            facts.taints.add((own_ref, "*"))
    _scan_causes(analysis, facts, import_infos, own_ref)
    patchers = _Patchers(analysis)
    _scan_patchers(analysis, facts, patchers)
    _scan_patch_methods(analysis, facts)
    _scan_patch_reads(analysis, facts)
    _scan_patcher_escapes(analysis, facts, patchers)
    hazard = parse_hazard(source, analysis.root)
    module_bindings = {
        "imports": sorted(facts.imports),
        "uses": [list(use) for use in sorted(facts.uses)],
        "taints": [list(taint) for taint in sorted(facts.taints)],
        "stars": sorted(facts.stars),
        "strings": sorted(facts.strings),
        "shutoff": [cause for cause in SHUTOFF_CAUSES if cause in facts.shutoff],
        "unparsed": hazard is not None,
        "missing": missing_reason,
        "groups": {
            key: [dict(info) for info in value] for key, value in groups.items()
        },
        "chains": {key: list(value) for key, value in chains.items()},
        "module_imports": {
            name: module_imports[name] for name in sorted(module_imports)
        },
        "own_submodules": own_submodules,
        "getters": {
            name: [list(record) for record in sorted(facts.getters[name])]
            for name in sorted(facts.getters)
        },
    }
    return exports, module_bindings


def _own_submodules(
    analysis: Any, own_ref: str, stars: AbstractSet[str] = frozenset()
) -> list[str]:
    """In a package ``__init__.py``, the names whose only module-scope
    bindings are unconditional imports of the package's own submodule of that
    name and the writes those imports make: the name then holds that
    submodule (#705 E6-3). Any other binding (a definition, an assignment, an
    attribute write by any receiver, a conditional or other import) leaves it
    out.

    An own-submodule import is ``from . import b`` or the absolute
    self-import ``from <the package's full dotted name> import b``, nothing
    else (#705 P6-1). CPython runs ``from vendor.utils import timezone`` in
    ``myapp/utils/__init__.py`` as an import of ``vendor.utils.timezone``:
    ``myapp.utils.timezone`` then holds the vendor module, and a later
    ``from myapp.utils import timezone`` finds that attribute, so
    ``_handle_fromlist`` never loads ``myapp/utils/timezone.py`` (the
    president's ``h10_django_like`` printed ``VENDOR timezone.now``). A
    match on the last component alone took it for the package's own.

    A star import anywhere in the file leaves no name out of reach: ``from
    .c import *`` runs after ``from . import b`` and rebinds ``b`` to
    whatever ``c`` exports under that name, and the submodule already in
    ``sys.modules`` is never set again (#705 P6-2; ``h9_star_rebind`` printed
    ``C.Impl.t (class)``). Such a file has no own-submodule names."""
    from . import py_scope as ps

    if not analysis.module_path.package_init or stars:
        return []
    found: list[str] = []
    for name, bindings in sorted(analysis.module.bindings.items()):
        imports = [binding for binding in bindings if binding.cls == ps.IMPORT]
        others = [binding for binding in bindings if binding.cls != ps.IMPORT]
        if not imports or any(binding.conditional for binding in imports):
            continue
        if any(binding.cls != ps.LOCAL for binding in others):
            continue
        if len(others) != analysis.submodule_writes.get(name, 0):
            continue

        def own_import(info: Mapping[str, str]) -> bool:
            module = str(info.get("module") or "")
            return (
                info.get("form") == "from"
                and info.get("name") == name
                and (module == "." or bool(own_ref) and module == own_ref)
            )

        if all(own_import(binding.info or {}) for binding in imports):
            found.append(name)
    return found


def _record(
    info: Mapping[str, str], position: str, chain: Sequence[str]
) -> tuple[str, ...]:
    """A use record ``(base, position, *chain)`` for an import binding."""
    if info.get("form") == "import":
        return (str(info.get("bound") or ""), position, *chain)
    return (
        str(info.get("module") or ""),
        position,
        str(info.get("name") or ""),
        *chain,
    )


def _scan_imports(analysis: Any, facts: _Facts) -> None:
    """Every module an import statement names (promotion edges), and star
    imports."""
    from . import py_scope as ps

    source = analysis.source
    stack = [analysis.root]
    while stack:
        node = stack.pop()
        stack.extend(node.named_children)
        if node.type == "import_statement":
            for child in node.named_children:
                imported = (
                    child.child_by_field_name("name")
                    if child.type == "aliased_import"
                    else child
                )
                if imported is not None and imported.type in (
                    "dotted_name",
                    "identifier",
                ):
                    facts.imports.add(".".join(ps._dotted_parts(imported, source)))
        elif node.type == "import_from_statement":
            dots, parts = ps._module_parts(node, source)
            base = "." * dots + ".".join(parts)
            if not dots and parts == ["__future__"]:
                continue
            facts.imports.add(base)
            for index, child in enumerate(node.children):
                if child.type == "wildcard_import":
                    facts.stars.add(base)
                if node.field_name_for_child(index) != "name":
                    continue
                imported = (
                    child.child_by_field_name("name")
                    if child.type == "aliased_import"
                    else child
                )
                if imported is not None:
                    name = ".".join(ps._dotted_parts(imported, source))
                    if name:
                        facts.imports.add(_join(base, name))


_IMPORT_NODES = frozenset(
    {
        "import_statement",
        "import_from_statement",
        "future_import_statement",
        "global_statement",
        "nonlocal_statement",
    }
)
_IMPORT_PARTS = frozenset(
    {
        "dotted_name",
        "aliased_import",
        "relative_import",
        "import_prefix",
        "wildcard_import",
    }
)


def _in_import(ident: Any) -> bool:
    """Whether an identifier is part of an import (its module path, relative
    or not, an imported name or an alias) or of a ``global``/``nonlocal``
    statement: a name, never a use of a value."""
    node = ident.parent
    while node is not None and node.type in _IMPORT_PARTS:
        node = node.parent
    return node is not None and node.type in _IMPORT_NODES


def _candidates(
    analysis: Any,
    ident: Any,
    import_infos: Mapping[str, list[Mapping[str, str]]],
) -> list[Mapping[str, str]]:
    """The import bindings an identifier may denote, by the ordinary lookup
    at the use: the one it proves, none when it proves the file's own
    binding, and every import of the name when the lookup cannot tell."""
    from . import py_scope as ps

    spellings = ps._spellings(ident, analysis.source)
    infos = [info for name in sorted(spellings) for info in import_infos.get(name, ())]
    if not infos:
        return []
    outcome = analysis.lookup(ident)
    kind = outcome.get("outcome")
    if kind == "import":
        return [outcome.get("binding") or {}]
    if analysis.decided is not None and analysis.real_deciding_scope(ident) is None:
        # A phantom binding (e.g. a name in a type parameter's bound)
        # cannot shadow an outer import at runtime.
        return infos
    if kind == "local" or outcome.get("reason") in _OWN_BINDINGS:
        return []
    return infos


def _walk(ident: Any, source: bytes) -> tuple[list[str], list[Any], Any]:
    """``(chain, attribute nodes, outer)``: the attribute names read off an
    identifier, through parentheses, the attribute node after each, and the
    outermost node (parentheses included)."""
    from . import py_scope as ps

    node = ident
    chain: list[str] = []
    nodes: list[Any] = [ident]
    while True:
        parent = node.parent
        if parent is None:
            break
        if (
            parent.type == "parenthesized_expression"
            and len([c for c in parent.named_children if c.type != "comment"]) == 1
        ):
            node = parent
            continue
        if parent.type == "attribute" and ps._same(
            node, parent.child_by_field_name("object")
        ):
            attribute = parent.child_by_field_name("attribute")
            if attribute is None:
                break
            chain.append(ps._text(attribute, source))
            nodes.append(parent)
            node = parent
            continue
        break
    return chain, nodes, node


def _inert_context(outer: Any) -> bool:
    """An operand of ``is``/``is not``, of ``not``, or a bare ``if``/``elif``
    /``while`` test: no method of the value runs and it goes nowhere."""
    parent = outer.parent
    if parent is None:
        return False
    if parent.type == "comparison_operator":
        operators = [child.type for child in parent.children if not child.is_named]
        return bool(operators) and all(
            op in ("is", "is not", "not") for op in operators
        )
    if parent.type == "not_operator":
        return True
    if parent.type in ("if_statement", "elif_clause", "while_statement"):
        condition = parent.child_by_field_name("condition")
        return condition is not None and condition.id == outer.id
    return False


def _builtin_at(analysis: Any, ident: Any) -> bool:
    """Whether an identifier may be the builtin of its name: the ordinary
    lookup at the use finds no binding of the file's own (fail closed)."""
    outcome = analysis.lookup(ident)
    return (
        outcome.get("outcome") == "none" and outcome.get("reason") not in _OWN_BINDINGS
    )


def _setattr_write(analysis: Any, outer: Any) -> str | None:
    """``setattr(<outer>, 'name', v)`` or ``delattr(<outer>, 'name')`` with
    the builtin (by the ordinary lookup) and a constant name: the name."""
    from . import py_scope as ps

    source = analysis.source
    arguments = outer.parent
    if arguments is None or arguments.type != "argument_list":
        return None
    call = arguments.parent
    if call is None or call.type != "call":
        return None
    callee = call.child_by_field_name("function")
    callee = ps._unwrap(callee, skip_comments=True) if callee is not None else None
    if callee is None or callee.type != "identifier":
        return None
    if ps._text(callee, source) not in ("setattr", "delattr"):
        return None
    items = [child for child in arguments.named_children if child.type != "comment"]
    if any(
        item.type in ("keyword_argument", "list_splat", "dictionary_splat")
        for item in items
    ):
        return None
    if len(items) < 2 or items[0].id != outer.id:
        return None
    if not _builtin_at(analysis, callee):
        return None
    return ps._constant_string(ps._unwrap(items[1], skip_comments=True), source)


def _use_position(analysis: Any, ident: Any) -> tuple[str, list[str]] | None:
    """The closed allow-list of uses of an imported module object, or
    ``None`` for an inert use: ``("write", chain)`` for an attribute write
    (the last name is the one written), ``("call", chain)`` for a call of a
    member, ``("value", chain)`` for anything else (an escape of whatever the
    chain reads)."""
    found = _classify_use(analysis, ident)
    return None if found is None else (found[0], found[1])


def _classify_use(analysis: Any, node: Any) -> tuple[str, list[str], Any] | None:
    """:func:`_use_position` of the value at ``node`` (an identifier or any
    expression), with the outermost node of the chain read off it
    (parentheses included): ``(position, chain, outer)``."""
    chain, nodes, outer = _walk(node, analysis.source)
    top = nodes[-1]
    if chain and top.id in analysis.attribute_targets:
        return "write", chain, outer
    from . import py_scope as ps

    if ps._callee_call(top) is not None:
        return "call", chain, outer
    name = _setattr_write(analysis, outer)
    if name is not None:
        return "write", [*chain, name], outer
    if _inert_context(outer):
        return None
    return "value", chain, outer


def _holder_read(ident: Any) -> bool:
    """Include implicit closure references and the base of a value pattern."""
    from . import py_scope as ps

    parent = ident.parent
    if parent is not None and parent.type == "nonlocal_statement":
        # The declaration alone captures the enclosing cell.
        return True
    if parent is not None and parent.type == "dotted_name" and not _in_import(ident):
        parts = ps._identifier_children(parent)
        return bool(
            parts
            and parts[0].id == ident.id
            and (
                len(parts) > 1
                or (parent.parent is not None and parent.parent.type == "class_pattern")
            )
        )
    return not (
        ps._name_part(ident) or _in_import(ident) or ps._binding_position(ident)
    )


def _scan_uses(
    analysis: Any,
    facts: _Facts,
    import_infos: Mapping[str, list[Mapping[str, str]]],
    getters: Mapping[int, str] | None = None,
) -> None:
    """Record every use of an imported name (#697): writes, and the reads
    that may escape a module object or reach a dunder. A tracked getter's
    own return of an import-rooted chain (#706) is recorded in
    ``facts.getters`` and as a ``ref`` record instead of a ``value`` use. A
    read of a function-local import binding from a nested scope is a
    ``value`` use (:func:`_nested_import_read`)."""
    from . import py_scope as ps

    local_imports: dict[str, list[Any]] = {}
    for scope, name, binding in analysis.events:
        if binding.cls == ps.IMPORT and scope.kind == ps._FUNCTION:
            local_imports.setdefault(name, []).append(scope)
    for ident in analysis.identifier_nodes:
        if not _holder_read(ident):
            continue
        infos = _candidates(analysis, ident, import_infos)
        if not infos:
            continue
        if local_imports and _nested_import_read(analysis, ident, local_imports):
            for info in infos:
                facts.uses.add(_record(info, "value", ()))
            continue
        position = _classify_use(analysis, ident)
        if position is None:
            continue
        kind, chain, outer = position
        dunder = any(ps._dunder(part) and part not in _SAFE_DUNDERS for part in chain)
        if kind == "call" and not dunder:
            # A call of a member reads a name and hands nothing on; only a
            # dunder on the way matters.
            continue
        getter = (
            _tracked_return(outer, getters)
            if getters and kind == "value" and not dunder
            else None
        )
        if getter is not None:
            # #706: the getter may return what the chain holds. The ``ref``
            # record keeps the chain's reference to any getter it reaches
            # (``return getter.get`` hands that function to the caller).
            for info in infos:
                record = _record(info, REF_POSITION, chain)
                facts.getters.setdefault(getter, set()).add((record[0], *record[2:]))
                facts.uses.add(record)
            continue
        for info in infos:
            facts.uses.add(_record(info, kind, chain))


def _nested_import_read(
    analysis: Any, ident: Any, local_imports: Mapping[str, Sequence[Any]]
) -> bool:
    """Executive ruling R-706-3: whether ``ident`` may read a function-local
    import binding from a scope nested in that function (a closure, lambda,
    comprehension or class body, a method in one, or an annotation scope).
    The capture puts the module in a cell another module can read and write
    (``fn.__closure__[i].cell_contents``,
    ``inspect.getclosurevars(fn).nonlocals``,
    ``fn.__annotate__.__closure__``), so the read hands the module out, as
    for a getter-result alias (R-706-2 B1).

    ``local_imports`` maps each name to the function scopes that import it.
    An annotation (PEP 649/695: evaluated later in its own annotation scope)
    counts when any such function encloses it. Otherwise, when the lookup
    decides in a scope (the one Python's static scoping binds the name in,
    whatever the outcome), that scope must be an importing function other
    than the read's innermost scope. When it decides nowhere (a mangled
    name, a poisoned or dynamic scope), any importing function that encloses
    the read, other than the innermost scope, counts."""
    from . import py_scope as ps

    holders = [
        scope
        for name in ps._spellings(ident, analysis.source)
        for scope in local_imports.get(name, ())
    ]
    if not holders:
        return False
    chain = list(analysis._chain(ident))
    if not chain:
        return False
    if ps._in_annotation(ident):
        return any(scope in chain for scope in holders)
    decided = analysis.lookup_scope(ident)
    if decided is not None:
        return decided is not chain[0] and any(scope is decided for scope in holders)
    return any(scope is not chain[0] and scope in chain for scope in holders)


def _dotted(info: Mapping[str, str]) -> list[str] | None:
    """The absolute dotted path an import binding denotes, or ``None`` for a
    relative one."""
    if info.get("form") == "import":
        return str(info.get("bound") or "").split(".")
    module = str(info.get("module") or "")
    if module.startswith(".") or not module:
        return None
    return [*module.split("."), str(info.get("name") or "")]


def _first_argument(call: Any) -> Any:
    from . import py_scope as ps

    arguments = ps._call_arguments(call)
    return arguments[0] if arguments else None


def _literal_module(analysis: Any, node: Any, facts: _Facts, own_ref: str) -> bool:
    """Record a literal module name (a constant string, or ``__name__``) as a
    whole-module taint; ``False`` when it is not literal."""
    from . import py_scope as ps

    if node is None:
        return False
    node = ps._unwrap(node, skip_comments=True)
    if node.type == "identifier" and ps._text(node, analysis.source) == "__name__":
        if own_ref:
            facts.taints.add((own_ref, "*"))
        return True
    value = ps._constant_string(node, analysis.source)
    if value is None or not value or value.startswith("."):
        return False
    if value.split(".")[0] in _CLASSIFIED_MODULES:
        facts.shutoff.add(CAUSE_DYNAMIC_LOADER)
    facts.taints.add((value, "*"))
    facts.imports.add(value)
    return True


def _operand_of_in(node: Any) -> bool:
    """Whether ``node`` (after parentheses) is the right operand of ``in`` or
    ``not in``."""
    outer = node
    while outer.parent is not None and outer.parent.type == "parenthesized_expression":
        outer = outer.parent
    parent = outer.parent
    if parent is None or parent.type != "comparison_operator":
        return False
    operators = [child.type for child in parent.children if not child.is_named]
    operands = [child for child in parent.named_children if child.type != "comment"]
    return (
        len(operands) == 2
        and operators in (["in"], ["not in"], ["not", "in"])
        and operands[1].id == outer.id
    )


def _sys_modules(analysis: Any, node: Any, facts: _Facts, own_ref: str) -> None:
    """``sys.modules`` (``node``): a closed list of uses. A constant key read
    or written, or a getter with a constant first argument, taints that
    module; ``'x' in sys.modules`` is inert; anything else is a run-wide
    ``module-system`` cause."""
    from . import py_scope as ps

    outer = node
    while outer.parent is not None and outer.parent.type == "parenthesized_expression":
        outer = outer.parent
    parent = outer.parent
    if (
        parent is not None
        and parent.type == "subscript"
        and ps._same(outer, parent.child_by_field_name("value"))
    ):
        keys = [
            child
            for index, child in enumerate(parent.children)
            if parent.field_name_for_child(index) == "subscript"
        ]
        if len(keys) == 1 and _literal_module(analysis, keys[0], facts, own_ref):
            return
    elif (
        parent is not None
        and parent.type == "attribute"
        and ps._same(outer, parent.child_by_field_name("object"))
    ):
        method = parent.child_by_field_name("attribute")
        call = ps._callee_call(parent)
        name = ps._text(method, analysis.source) if method is not None else ""
        if name == "__contains__" and call is not None:
            return
        if (
            name in _SYS_MODULE_GETTERS
            and call is not None
            and _literal_module(analysis, _first_argument(call), facts, own_ref)
        ):
            return
    elif _operand_of_in(node):
        return
    facts.shutoff.add(CAUSE_MODULE_SYSTEM)


def _classify_path(
    analysis: Any,
    path: list[str],
    nodes: list[Any],
    offset: int,
    facts: _Facts,
    own_ref: str,
) -> None:
    """Classify a reference to a classified standard-library module.

    ``path`` is the full dotted path the use reads (``["importlib",
    "import_module"]``); the node for ``path[k]`` is ``nodes[k - offset]``
    (the identifier stands for the first ``offset + 1`` components).
    """
    from . import py_scope as ps

    def node_at(index: int) -> Any:
        return nodes[max(index - offset, 0)]

    def inert_value(index: int) -> bool:
        node = node_at(index)
        if index < len(path) - 1:
            return True  # an attribute is read off it
        outer = node
        while (
            outer.parent is not None and outer.parent.type == "parenthesized_expression"
        ):
            outer = outer.parent
        return _inert_context(outer)

    head = path[0]
    if head in ("builtins", "__builtin__", "__main__", "__mp_main__"):
        facts.shutoff.add(CAUSE_MODULE_OBJECT)
        return
    if (
        head in _LOADER_MODULES
        or tuple(path[:3]) in _LOADER_PATHS
        or tuple(path[:2]) in _LOADER_PATHS
    ):
        facts.shutoff.add(CAUSE_DYNAMIC_LOADER)
        return
    if tuple(path[:2]) in _SITE_PATHS:
        facts.shutoff.add(CAUSE_MODULE_SYSTEM)
        return
    if head == "sys":
        if len(path) == 1:
            if not inert_value(0):
                facts.shutoff.add(CAUSE_MODULE_SYSTEM)
            return
        member = path[1]
        if member == "modules":
            if len(path) == 2 or path[2] in _SYS_MODULE_GETTERS | {"__contains__"}:
                _sys_modules(analysis, node_at(1), facts, own_ref)
            else:
                facts.shutoff.add(CAUSE_MODULE_SYSTEM)
        elif member in _SYS_PATH_NAMES:
            if not (len(path) == 2 and _operand_of_in(node_at(1))):
                facts.shutoff.add(CAUSE_MODULE_SYSTEM)
        elif ps._dunder(member):
            facts.shutoff.add(CAUSE_MODULE_SYSTEM)
        return
    if head != "importlib":
        return
    if any(tuple(path[: len(entry)]) == entry for entry in _INERT_IMPORTLIB):
        return
    if len(path) >= 2 and path[1] == "import_module" and len(path) == 2:
        call = ps._callee_call(node_at(1))
        if call is None:
            facts.shutoff.add(CAUSE_DYNAMIC_LOADER)
            return
        arguments = ps._call_arguments(call)
        first = arguments[0] if arguments else None
        value = (
            ps._constant_string(first, analysis.source) if first is not None else None
        )
        if value is not None and value.startswith("."):
            package = None
            for argument in arguments[1:]:
                if argument.type == "keyword_argument":
                    name = argument.child_by_field_name("name")
                    if name is None or ps._text(name, analysis.source) != "package":
                        continue
                    argument = argument.child_by_field_name("value")
                package = (
                    ps._constant_string(argument, analysis.source)
                    if argument is not None
                    else None
                )
                break
            if package is None:
                facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
                return
            dots = len(value) - len(value.lstrip("."))
            parts = package.split(".")
            if dots - 1 >= len(parts):
                facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
                return
            rest = value[dots:]
            absolute = ".".join(
                parts[: len(parts) - (dots - 1)] + ([rest] if rest else [])
            )
            facts.taints.add((absolute, "*"))
            facts.imports.add(absolute)
            return
        if not _literal_module(analysis, first, facts, own_ref):
            facts.shutoff.add(CAUSE_DYNAMIC_LOADER)
        return
    if len(path) == 2 and path[1] == "reload":
        call = ps._callee_call(node_at(1))
        arguments = ps._call_arguments(call) if call is not None else []
        if len(arguments) == 1 and arguments[0].type in ("identifier", "attribute"):
            # The module object handed over is itself a use the escape rule
            # records; reloading re-runs its own source.
            return
    facts.shutoff.add(CAUSE_DYNAMIC_LOADER)


def _scan_causes(
    analysis: Any,
    facts: _Facts,
    import_infos: Mapping[str, list[Mapping[str, str]]],
    own_ref: str,
) -> None:
    """Run-wide causes, literal acquisitions and dotted strings."""
    from . import py_scope as ps

    source = analysis.source
    # treesitter-chunker#699 S2: one classifier serves both tiers (the
    # fold-8 precedent). Code run from a string, a payload or an annotation
    # (Tier 1 file-wide) is a run-wide ``evaluator`` cause (Q8: a production
    # ``pickle.loads`` included); a code-object source, reads included, is a
    # ``module-object`` cause (B-1, reversing #705 Q2: ``type(f)(code, g)()``
    # runs a code object with neither ``exec`` nor ``eval``).
    # The full-lookup test PR 6 used for ``exec``/``eval``/``execfile`` is
    # kept too (R-699-3): a frame rule or a lazy annotation leaves the use
    # possibly the builtin even where the use-site proof excludes it.
    if analysis.string_code or analysis.legacy_evaluator():
        facts.shutoff.add(CAUSE_EVALUATOR)
    if analysis.code_objects:
        facts.shutoff.add(CAUSE_MODULE_OBJECT)
    if analysis.heap_walk:
        # treesitter-chunker#699 PY-7 with B-7: Tier 1's ``gc`` verdict (a use
        # off the member list, a heap-walker token) is a run-wide cause too:
        # ``gc.get_referents(use.run)`` hands over another module's globals.
        facts.shutoff.add(CAUSE_MODULE_OBJECT)
    if any(node is None for node, _by_lookup in analysis._locals_readers()):
        # treesitter-chunker#699 PY-9: ``locals``/``vars`` as a value, an
        # import name or a constant-string word (Tier 1's R-707-1 token
        # rule): another file may call it (``get_locals = locals``) and hand
        # the dict of its frame's locals on.
        facts.shutoff.add(CAUSE_MODULE_OBJECT)
    if analysis.main_string:
        # K-3 (#698, R-698-2): a string naming the main module, by the one
        # classifier Tier 1 uses (``py_scope._main_string``): a component
        # after the format and attribute punctuation split, a default
        # ``string.Template`` identifier, or a main name anywhere in an
        # f-string's or t-string's decoded source text (``T = "%(__main__)s"``,
        # ``f"{P():__main__}"``; R-698-3). Only the script guard's comparand
        # is exempt.
        facts.shutoff.add(CAUSE_MODULE_OBJECT)
    stack = [analysis.root]
    while stack:
        node = stack.pop()
        stack.extend(node.named_children)
        kind = node.type
        if kind in ("string", "concatenated_string", "binary_operator"):
            if (
                kind == "string"
                and node.parent is not None
                and node.parent.type == ("concatenated_string")
            ):
                continue
            value = ps._constant_string(node, source)
            if value is None:
                continue
            parts = set(ps._NAME_SEPARATORS.split(value))
            words = set(ps._TOKEN_WORDS.split(value))
            if parts & (_MODULE_OBJECT_NAMES - {"__main__", "__mp_main__"}):
                facts.shutoff.add(CAUSE_MODULE_OBJECT)
            if words & _FRAME_READERS:
                facts.shutoff.add(CAUSE_MODULE_OBJECT)
            if _CELL_CONTENTS in words:
                facts.shutoff.add(CAUSE_MODULE_OBJECT)
            if parts & _RESOLVER_NAMES:
                facts.shutoff.add(CAUSE_DYNAMIC_LOADER)
            if {"sys", "modules"} <= parts or "__path__" in parts:
                facts.shutoff.add(CAUSE_MODULE_SYSTEM)
            if _DOTTED_STRING.fullmatch(value):
                facts.strings.add(value.replace(":", "."))
            if value in _CODE_ATTRIBUTES:
                # N-1: ``setattr(f, "__code__", c)`` and every other spelling
                # that names the attribute by string.
                facts.shutoff.add(CAUSE_MODULE_OBJECT)
    for ident in analysis.identifier_nodes:
        name = ps._text(ident, source)
        spellings = ps._spellings(ident, source)
        if spellings & _FRAME_READERS:
            facts.shutoff.add(CAUSE_MODULE_OBJECT)
        if _CELL_CONTENTS in spellings and not _cell_read(analysis, ident):
            facts.shutoff.add(CAUSE_MODULE_OBJECT)
        if ps._name_part(ident):
            parent = ident.parent
            if (
                name in _CODE_ATTRIBUTES
                and parent is not None
                and parent.id in analysis.attribute_targets
            ):
                # N-1: ``f.__code__ = other.__code__`` (any receiver).
                facts.shutoff.add(CAUSE_MODULE_OBJECT)
            if spellings & _MODULE_OBJECT_NAMES:
                facts.shutoff.add(CAUSE_MODULE_OBJECT)
            if spellings & _RESOLVER_NAMES:
                facts.shutoff.add(CAUSE_DYNAMIC_LOADER)
            if "__path__" in spellings:
                facts.shutoff.add(CAUSE_MODULE_SYSTEM)
            parent = ident.parent
            if parent is not None and parent.type == "keyword_argument":
                continue
            if parent is not None and name in ("sys", "_sys"):
                # ``os.sys``, ``collections._sys``: another module's ``sys``.
                chain, nodes, _outer = _walk(parent, source)
                _classify_path(
                    analysis, ["sys", *chain], [parent, *nodes[1:]], 0, facts, own_ref
                )
            continue
        if _in_import(ident) or ps._scope_binding_name(ident):
            continue
        if name == "__path__":
            facts.shutoff.add(CAUSE_MODULE_SYSTEM)
            continue
        if ps._binding_position(ident):
            continue
        if spellings & _MODULE_OBJECT_NAMES and name not in ("builtins", "__builtin__"):
            facts.shutoff.add(CAUSE_MODULE_OBJECT)
        if spellings & _RESOLVER_NAMES:
            facts.shutoff.add(CAUSE_DYNAMIC_LOADER)
        if name == "__import__" and _builtin_at(analysis, ident):
            call = ps._callee_call(ident)
            first = _first_argument(call) if call is not None else None
            value = ps._constant_string(first, source) if first is not None else None
            if value and _literal_module(analysis, first, facts, own_ref):
                # ``__import__('a.b')`` returns ``a``.
                facts.taints.add((value.split(".")[0], "*"))
            else:
                facts.shutoff.add(CAUSE_DYNAMIC_LOADER)
        infos = _candidates(analysis, ident, import_infos)
        for info in infos:
            dotted = _dotted(info)
            if dotted is None or dotted[0] not in _CLASSIFIED_MODULES:
                continue
            chain, nodes, _outer = _walk(ident, source)
            _classify_path(
                analysis, [*dotted, *chain], nodes, len(dotted) - 1, facts, own_ref
            )
        if not infos and name in (
            "builtins",
            "__builtin__",
            "importlib",
            "sys",
            "runpy",
        ):
            # A module name used without an import the rules can follow (a
            # star import, a global another file set).
            outcome = analysis.lookup(ident)
            if outcome.get("outcome") != "local" and outcome.get("reason") not in (
                _OWN_BINDINGS
            ):
                facts.shutoff.add(
                    CAUSE_MODULE_OBJECT
                    if name in ("builtins", "__builtin__")
                    else CAUSE_DYNAMIC_LOADER if name != "sys" else CAUSE_MODULE_SYSTEM
                )


# treesitter-chunker#724, executive ruling R-724-1: a file hands out its
# namespace, every import binding in it, when ANY token in it spells a name
# that reaches a namespace (:data:`_NAMESPACE_TOKENS`), in any role: an
# identifier, an attribute, an import name, a keyword argument or a constant
# string (decoded and joined across adjacent literals and ``+``, matched
# exactly or as a dotted or bracket component). ``helper(globals())`` after
# ``import svc`` lets ``helper`` run ``d["svc"].t = f``, which CPython 3.14
# honours while ``svc.py``'s own ``t()`` call was proven. Shadowing is
# ignored: any spelling counts, so a token list closes the spelling and
# position variants a trigger list leaves open (the 726 Fable review, B-1 to
# B-7). Each handed-out binding is a ``value`` use, as if the module were
# passed as an argument.
_NAMESPACE_TOKENS = frozenset(
    {
        # The builtins that return the calling frame's namespace.
        "globals",
        "locals",
        "vars",
        # A frame's or a function's namespace dicts, and the builtins dict
        # (``f_builtins["globals"]()``).
        "f_globals",
        "f_locals",
        "f_builtins",
        "__globals__",
        # A module object from a name, a frame or a function
        # (``__import__(__name__)``, ``inspect.getmodule(fn)``), and the
        # globals a closure reads (``inspect.getclosurevars(fn).globals``).
        "__import__",
        "getmodule",
        "getclosurevars",
        # The module's own loader (``__spec__.loader.load_module(__name__)``).
        "__loader__",
        "__spec__",
        "load_module",
        "exec_module",
        # ``string.Formatter().get_field("0.__globals__[svc]", (fn,), {})``.
        "get_field",
        # The builtins module, which holds every builtin above.
        "builtins",
        # The frame-locals readers of ``inspect`` and ``pdb``.
        "getargvalues",
        "getgeneratorlocals",
        "getcoroutinelocals",
        "getasyncgenlocals",
        "curframe_locals",
        # The annotation evaluators, which run a string annotation
        # (``def h(x: "svc")``) against the defining file's globals
        # (``typing.get_type_hints(h)["x"]`` is the module ``svc``).
        "get_type_hints",
        "get_annotations",
        "eval_str",
        "ForwardRef",
        "evaluate_forward_ref",
        "_eval_type",
        "call_annotate_function",
        "call_evaluate_function",
        # R-724-4 (S-3): routes that spell no other listed name, each kept
        # at a measured production cost of 0 edges.
        # ``inspect.getmembers(frame)`` lists ``f_globals`` by content;
        # ``doctest.DocTestFinder().find(fn)[0].globs`` holds the module's
        # bindings; ``rlcompleter.Completer()`` reads ``__main__``'s;
        # ``[v for k, v in __builtins__.items() if k.startswith("glob")]``
        # picks a builtin by content; ``ctypes.pythonapi.PyEval_GetGlobals``
        # returns the calling frame's globals.
        "getmembers",
        "getmembers_static",
        "DocTestFinder",
        "globs",
        "rlcompleter",
        "__builtins__",
        "PyEval_GetGlobals",
    }
)
# The components a constant string is matched by: dotted, ``:``-separated,
# bracketed, quoted and format-field parts (``"0.__globals__[svc]"``,
# ``"builtins.open"``, ``"{0.__globals__!r}"``: ``string.Formatter``
# resolves the field without its caller spelling ``get_field``).
_TOKEN_SEPARATORS = re.compile(r"[.:\[\]'\"{}!]")
# A frame's namespace dicts, read by a constant key (:func:`_frame_read_keys`).
_FRAME_DICTS = frozenset({"f_locals", "f_globals"})
# The evaluators run code in the calling frame's namespace. They count in any
# bare spelling, called with any arguments or handed on (``exec(code, d)``
# included: ``d`` may be the namespace). Another object's ``.eval()``
# (``model.eval()``) and ``compile``'s mode string ``"exec"`` count only in a
# file that spells a route to the builtins (:data:`_BUILTINS_ROUTES`), where
# ``__builtins__.exec(...)`` or ``getattr(bltns, "eval")`` is the builtin.
_NAMESPACE_EVALUATORS = frozenset({"eval", "exec", "execfile"})
_BUILTINS_ROUTES = frozenset({"__builtins__", "__builtin__", "bltns", "__self__"})
# The modules whose handed-out binding is itself a route to every module
# (``d["sys"].modules["svc"]``, ``d["importlib"].import_module("svc")``):
# a ``module-system`` cause (R-724-1 item 4).
_MODULE_SYSTEM_MODULES = frozenset({"sys", "importlib", "builtins"})
_MAIN = "__main__"


def _token_match(value: str, names: AbstractSet[str]) -> bool:
    """Whether a decoded constant string is one of ``names``, exactly or as
    a component (:data:`_TOKEN_SEPARATORS`)."""
    return value in names or bool(set(_TOKEN_SEPARATORS.split(value)) & names)


def _namespace_handout(
    analysis: Any,
    import_names: AbstractSet[str] = frozenset(),
    routes_seen: list[bool] | None = None,
) -> frozenset[str] | None:
    """The import binding names the file hands out by reaching its own
    namespace (#724, R-724-1): ``None`` for every one, else the names a frame
    namespace read by a constant key reaches. When it returns a set and
    ``routes_seen`` is given, it appends whether the file spells a route to
    the builtins (:data:`_BUILTINS_ROUTES`), which H1 reads
    (:func:`_introspects`).

    Every binding is handed out when any token of the file spells one of
    :data:`_NAMESPACE_TOKENS` (an identifier in any role, an attribute, an
    import name, a keyword argument name, or a component of a constant
    string), whatever binding the name has; when the file imports
    ``__main__`` (an import statement, or ``"__main__"`` as a call argument
    or subscript key); when a bare ``eval``,
    ``exec`` or ``execfile`` is used other than as a binding, or the
    statement ``exec``; and, in a file that spells a route to the builtins
    (:data:`_BUILTINS_ROUTES`), when ``X.eval``/``X.exec`` or the string
    ``"eval"``/``"exec"`` appears.

    One narrowing: a frame's ``f_locals`` or ``f_globals`` read by a constant
    key (``.get(K)``, ``[K]``) hands out only the binding named ``K``, and
    only when ``K`` is a non-dunder name that is an import binding of the
    file (``import_names``). Any other key hands out every binding: a dunder
    (``__builtins__``, ``__loader__``, ``__spec__``, ``__name__``) reaches
    the whole namespace, and a function or class (``f_globals["go"]``)
    reaches it through ``__globals__`` or ``__module__``. ``K in`` reads
    no value and hands out none."""
    from . import py_scope as ps

    source = analysis.source
    routes = False
    members = False
    exempted = False
    worded = False
    keys: set[str] = set()
    for ident in analysis.identifier_nodes:
        spellings = ps._spellings(ident, source)
        if spellings & _NAMESPACE_TOKENS:
            if _not_own_namespace(analysis, ident):
                # R-724-2: the token applies to an object the use-site
                # lookup proves is not this file's namespace.
                exempted = True
                continue
            read = _frame_read_keys(analysis, ident)
            if read is None or any(
                ps._dunder(key) or key not in import_names for key in read
            ):
                return None
            keys |= read
            continue
        if spellings & _BUILTINS_ROUTES:
            routes = True
        name = ps._text(ident, source)
        if name == _MAIN and _import_target(ident):
            return None
        if _own_module_route(analysis, ident, name):
            return None
        if name not in _NAMESPACE_EVALUATORS:
            continue
        if ps._name_part(ident):
            # ``X.eval`` (a builtin on a route to the builtins); a keyword
            # argument name (``f(eval=True)``) is neither.
            parent = ident.parent
            if parent is not None and parent.type == "attribute":
                members = True
            continue
        if _in_import(ident):
            return None
        if not ps._binding_position(ident):
            if not _exec_into_fresh_module(analysis, ident):
                return None
            exempted = True
    evaluator_strings = False
    stack = [analysis.root]
    while stack:
        node = stack.pop()
        stack.extend(node.named_children)
        kind = node.type
        if kind == "exec_statement":
            return None
        if kind not in ("string", "concatenated_string", "binary_operator"):
            continue
        if (
            kind == "string"
            and node.parent is not None
            and (node.parent.type == "concatenated_string")
        ):
            continue
        value = ps._constant_string(node, source)
        if value is None:
            continue
        if _token_match(value, _NAMESPACE_TOKENS):
            return None
        if set(ps._TOKEN_WORDS.split(value)) & _EXEMPT_VOIDING_WORDS or _token_match(
            value, _FACTORY_PARTS
        ):
            worded = True
        if _token_match(value, _BUILTINS_ROUTES):
            routes = True
        if value in _NAMESPACE_EVALUATORS:
            evaluator_strings = True
        if value == _MAIN and _argument_string(node, source) is not None:
            # ``importlib.import_module("__main__")``,
            # ``sys.modules["__main__"]`` (the script guard compares the
            # constant, which is neither).
            return None
    if routes and (members or evaluator_strings):
        return None
    if exempted and worded:
        # R-724-4: the code an exempt ``exec`` runs may spell a token with
        # any delimiter (``"import sys; d = sys._getframe(1).f_globals"``),
        # and a patch target may name a factory or its module
        # (``mock.patch("types.ModuleType", fake)``).
        return None
    if routes_seen is not None:
        routes_seen.append(routes)
    return frozenset(keys)


# R-724-4 (S-3): resolvers that return the module a name denotes. Applied to
# ``__name__``, or to a constant whose first component is a component of the
# file's own module path (``pkgutil.resolve_name("use:svc")``), one returns
# the file's own module or a package holding it, as
# ``importlib.import_module(__name__)`` does
# (``logging.config.BaseConfigurator({}).resolve(__name__)``).
_OWN_NAME_RESOLVERS = frozenset({"resolve_name", "locate", "resolve"})
# R-724-4 (S-3): attribute reads that are a test module itself (pytest's
# ``request.module``).
_OWN_MODULE_ATTRIBUTES = frozenset({("request", "module")})


def _own_module_route(analysis: Any, ident: Any, name: str) -> bool:
    """Whether ``ident`` is a route to the file's own module that spells no
    listed token: a callee named in :data:`_OWN_NAME_RESOLVERS` whose first
    argument is ``__name__`` or a constant naming the file's own module or a
    package holding it, or the attribute of
    :data:`_OWN_MODULE_ATTRIBUTES`."""
    from . import py_scope as ps

    source = analysis.source
    parent = ident.parent
    if parent is not None and parent.type == "attribute":
        holder = parent.child_by_field_name("object")
        holder = ps._unwrap(holder, skip_comments=True) if holder is not None else None
        if (
            holder is not None
            and holder.type == "identifier"
            and ps._same(ident, parent.child_by_field_name("attribute"))
            and (ps._text(holder, source), name) in _OWN_MODULE_ATTRIBUTES
        ):
            return True
    if name not in _OWN_NAME_RESOLVERS:
        return False
    callee = parent if parent is not None and parent.type == "attribute" else ident
    if callee is not ident and not ps._same(
        ident, callee.child_by_field_name("attribute")
    ):
        return False
    call = ps._callee_call(callee)
    arguments = ps._call_arguments(call) if call is not None else []
    if not arguments:
        return False
    first = ps._unwrap(arguments[0], skip_comments=True)
    if first.type == "identifier" and ps._text(first, source) == "__name__":
        return True
    value = ps._constant_string(first, source)
    if not value:
        return False
    head = re.split(r"[.:]", value.strip())[0]
    return head in {*analysis.module_path.components, *analysis.own_names}


# R-724-2: the closed allow-list of token uses whose object the use-site
# lookup proves is not the file's own namespace. This covers a constant
# foreign import and exec or loader execution into a fresh module local.
# The receiver's one binding in the function must call types.ModuleType,
# with the constructor identified through its import (R-724-7).
# module_from_spec delegates creation to the loader, which can return the
# importing module itself. Its historical names remain voiding tokens.
# R-724-4: a constant that spells a token or a factory's own name as a word
# (:data:`py_scope._TOKEN_WORDS`), or any name of a factory path as a component
# (:data:`_TOKEN_SEPARATORS`), voids every exempt use of the file. A patch
# target or a module key may name the factory or its module
# (``mock.patch("types.ModuleType", F)``, ``mock.patch("importlib.util",
# U)``, ``mock.patch.dict(sys.modules, {"types": T})``).
_EXEMPT_VOIDING_WORDS = _NAMESPACE_TOKENS | {"ModuleType", "module_from_spec"}
_FACTORY_PARTS = frozenset(
    {"types", "ModuleType", "importlib", "util", "module_from_spec"}
)


def _not_own_namespace(analysis: Any, ident: Any) -> bool:
    """Whether a token identifier is one of R-724-2's exempt uses:
    ``<name>.loader.exec_module(X)`` on a fresh module ``X``
    (:func:`_fresh_module_local`), or ``__import__(K)`` of a constant
    absolute module name ``K`` that is not the file's own module, its
    package or a classified module (:func:`_foreign_import_constant`)."""
    from . import py_scope as ps

    name = ps._text(ident, analysis.source)
    if name == "exec_module":
        return _loader_exec_into_fresh_module(analysis, ident)
    if name == "__import__":
        return _foreign_import_constant(analysis, ident)
    return False


def _unshadowed_builtin(analysis: Any, name: str) -> bool:
    """Whether ``name`` is bound nowhere in the file, which has no star
    import: every use of it is the builtin."""
    return not analysis.star and not any(
        bound == name for _scope, bound, _binding in analysis.events
    )


def _positional_arguments(call: Any) -> list[Any] | None:
    """A call's arguments when every one is positional (no keyword, no
    ``*``/``**`` splat, no generator argument), else ``None``."""
    from . import py_scope as ps

    arguments = call.child_by_field_name("arguments")
    if arguments is None or arguments.type != "argument_list":
        return None
    values = ps._call_arguments(call)
    if any(
        value.type in ("keyword_argument", "list_splat", "dictionary_splat")
        for value in values
    ):
        return None
    return values


def _exec_into_fresh_module(analysis: Any, ident: Any) -> bool:
    """``exec(code, X.__dict__)``: the builtin ``exec`` called with exactly
    two positional arguments, the globals being a fresh module's
    ``__dict__`` (spec ``ingest.py``). The code runs in ``X``'s namespace;
    ``globals()`` there is ``X.__dict__``."""
    from . import py_scope as ps

    source = analysis.source
    if ps._text(ident, source) != "exec" or not _unshadowed_builtin(analysis, "exec"):
        return False
    call = ps._callee_call(ident)
    arguments = _positional_arguments(call) if call is not None else None
    if arguments is None or len(arguments) != 2:
        return False
    namespace = arguments[1]
    if namespace.type != "attribute":
        return False
    attribute = namespace.child_by_field_name("attribute")
    receiver = namespace.child_by_field_name("object")
    return (
        attribute is not None
        and ps._text(attribute, source) == "__dict__"
        and receiver is not None
        and _fresh_module_local(analysis, ps._unwrap(receiver, skip_comments=True))
    )


def _loader_exec_into_fresh_module(analysis: Any, ident: Any) -> bool:
    """``<name>.loader.exec_module(X)``: the attribute ``exec_module`` of a
    name's ``loader``, called with exactly one positional argument, a fresh
    module (Code-Index-MCP ``safety_runtime_smoke.py``). The loader runs the
    module's code in ``X``'s namespace."""
    from . import py_scope as ps

    source = analysis.source
    attribute = ident.parent
    if (
        attribute is None
        or attribute.type != "attribute"
        or not ps._same(ident, attribute.child_by_field_name("attribute"))
    ):
        return False
    loader = attribute.child_by_field_name("object")
    loader = ps._unwrap(loader, skip_comments=True) if loader is not None else None
    if loader is None or loader.type != "attribute":
        return False
    loader_name = loader.child_by_field_name("attribute")
    holder = loader.child_by_field_name("object")
    holder = ps._unwrap(holder, skip_comments=True) if holder is not None else None
    if (
        loader_name is None
        or ps._text(loader_name, source) != "loader"
        or holder is None
        or holder.type != "identifier"
    ):
        return False
    call = ps._callee_call(attribute)
    arguments = _positional_arguments(call) if call is not None else None
    return (
        arguments is not None
        and len(arguments) == 1
        and _fresh_module_local(analysis, arguments[0])
    )


def _foreign_import_constant(analysis: Any, ident: Any) -> bool:
    """``__import__(K)``: the builtin called with exactly one positional
    argument, a constant absolute module name (Code-Index-MCP
    ``stdio_runner.py``'s ``__import__("hashlib")``). It returns ``K``'s
    top-level package, which :func:`_scan_causes` already taints wholly
    (``import K; f(K)``). Not exempt: a relative or empty name, a name
    whose top-level package is a classified module (``sys``,
    ``importlib``, ``builtins``, ``__main__``, ``inspect``, ``gc``, ...:
    ``__import__("sys").modules[__name__]``), or a name whose top-level
    package is any component of the file's own module path (it may be the
    file's own package, and so reach the file). A constant spelling a token
    (``__import__("builtins")``) is a string token itself. A shadowing
    binding of ``__import__`` is a token too; a star import is checked."""
    from . import py_scope as ps

    if not _unshadowed_builtin(analysis, "__import__"):
        return False
    call = ps._callee_call(ident)
    arguments = _positional_arguments(call) if call is not None else None
    if arguments is None or len(arguments) != 1:
        return False
    value = ps._constant_string(arguments[0], analysis.source)
    if not value:
        return False
    parts = value.split(".")
    if not all(part.isidentifier() for part in parts):
        return False
    own = set(analysis.module_path.components) | set(analysis.own_names)
    return (
        not analysis.module_path.unknown
        and parts[0] not in _CLASSIFIED_MODULES
        and parts[0] not in own
    )


def _fresh_module_local(analysis: Any, ident: Any) -> bool:
    """Whether ``ident`` is a function local whose ONE binding in its
    function is ``ident = F(...)``, ``F`` proven by its import to be
    ``types.ModuleType``. Such a value is a new module object,
    never the file's own module: a rebinding (another assignment, a ``for``
    or ``with`` target, ``del``, a walrus, a ``nonlocal`` write from an inner
    function), a ``global`` declaration or a parameter of the name makes it
    no fresh module."""
    from . import py_scope as ps

    if ident is None or ident.type != "identifier":
        return False
    name = ps._text(ident, analysis.source)
    scope = next(iter(analysis._chain(ident)), None)
    if scope is None or scope.kind != ps._FUNCTION:
        return False
    if "__class__" in analysis.attribute_writes:
        # R-724-4: ``mod.__class__ = M`` on any receiver may give the module
        # a ``__dict__`` property that returns another namespace.
        return False
    # The lookup decides in this function (a ``global`` or ``nonlocal``
    # name, a mangled name, a poisoned scope and a file that may write a
    # function's locals, ``f_locals`` or a closure cell, decide nowhere or
    # elsewhere).
    analysis.lookup(ident, namespace_receiver=True)
    if analysis.decided is not scope or len(scope.bindings.get(name, ())) != 1:
        return False
    sites = [
        site
        for site in analysis._binding_sites_of(name)
        if next(iter(analysis._chain(site)), None) is scope
    ]
    if len(sites) != 1:
        return False
    (site,) = sites
    assignment = site.parent
    if assignment is None or assignment.type != "assignment":
        return False
    value = assignment.child_by_field_name("right")
    value = ps._unwrap(value, skip_comments=True) if value is not None else None
    if value is None or value.type != "call":
        return False
    callee = value.child_by_field_name("function")
    callee = ps._unwrap(callee, skip_comments=True) if callee is not None else None
    return callee is not None and _fresh_module_factory(analysis, callee)


def _fresh_module_factory(analysis: Any, callee: Any) -> bool:
    """Whether a callee is the stdlib module constructor: an
    identifier or attribute chain whose head is bound ONLY by imports in the
    file, all denoting one absolute path, which joined with the chain is the
    factory (``types.ModuleType``). Fold 25's proof of a
    standard-library callee (``py_scope._stdlib_name``), which holds in a
    file whose module lookups fail closed (any ``importlib`` mention makes
    them ``dynamic-scope``): no other binding of the head anywhere (an
    assignment, a parameter, ``del``, a class or def, a write of its name on
    any receiver such as ``x.types = F``), no star import, and no recorded
    write of a chain name on any receiver (``importlib.util = F``,
    ``ns["ModuleType"] = F``)."""
    from . import py_scope as ps

    source = analysis.source
    chain: list[str] = []
    node = callee
    while node is not None and node.type == "attribute":
        attribute = node.child_by_field_name("attribute")
        if attribute is None:
            return False
        chain.append(ps._text(attribute, source))
        node = node.child_by_field_name("object")
        node = ps._unwrap(node, skip_comments=True) if node is not None else None
    if node is None or node.type != "identifier" or analysis.star:
        return False
    head = ps._text(node, source)
    if ps._mangled_names(node, head, source):
        return False
    if set(chain) & analysis.attribute_writes:
        # ``importlib.util = U``, ``ns["ModuleType"] = F``. A write of the
        # head's own name on any receiver (``x.types = F``) is already a
        # module-scope binding event of it, which the loop below refuses.
        return False
    paths = set()
    for _scope, bound, binding in analysis.events:
        if bound != head:
            continue
        dotted = _dotted(binding.info or {}) if binding.cls == ps.IMPORT else None
        if dotted is None:
            return False
        paths.add(tuple(dotted))
    if len(paths) != 1:
        return False
    (path,) = paths
    return (*path, *reversed(chain)) == ("types", "ModuleType")


def _import_target(ident: Any) -> bool:
    """Whether an identifier is the first component of the module an import
    statement imports (``import __main__``, ``import __main__ as me``,
    ``from __main__ import x``)."""
    node = ident.parent
    if node is None or node.type != "dotted_name":
        return False
    first = node.named_children[0] if node.named_children else None
    if first is None or first.id != ident.id:
        return False
    above = node.parent
    if above is not None and above.type == "aliased_import":
        above = above.parent
    if above is None:
        return False
    if above.type == "import_statement":
        return True
    if above.type == "import_from_statement":
        module = above.child_by_field_name("module_name")
        return module is not None and module.id == node.id
    return False


def _frame_read_keys(analysis: Any, ident: Any) -> frozenset[str] | None:
    """For an identifier spelled like one of :data:`_NAMESPACE_TOKENS`: the
    keys it reads when it is a frame's ``f_locals`` or ``f_globals`` read by
    a constant key (closed list: ``.get(K)``,
    ``[K]``, ``K in``, the last reading none), else ``None`` (every
    binding)."""
    from . import py_scope as ps

    source = analysis.source
    if not ps._spellings(ident, source) & _FRAME_DICTS:
        return None
    if not analysis._attribute_read(ident):
        return None
    outer = ident.parent
    while outer.parent is not None and outer.parent.type == "parenthesized_expression":
        outer = outer.parent
    above = outer.parent
    key: Any = None
    if above.type == "attribute":
        key = _first_argument(ps._callee_call(above))
    elif above.type == "subscript":
        keys = [
            child
            for index, child in enumerate(above.children)
            if above.field_name_for_child(index) == "subscript"
        ]
        key = keys[0] if len(keys) == 1 else None
    else:
        return frozenset()
    value = ps._constant_string(key, source) if key is not None else None
    return None if value is None else frozenset({value})


# treesitter-chunker#706: module objects returned by functions. A *tracked
# getter* returns import-rooted chains (``return svc``, ``return a, b``);
# its file records what it may return (``getters``) instead of a ``value``
# escape, and every use of a call that may invoke a getter is recorded
# through the same closed allow-list as an imported module object
# (:func:`_scan_results`). Assembly resolves the callee leniently to a set of
# getters and walks the uses from the modules they return.
#
# The marker of a call step in a result record's chain.
CALL_MARK = "()"
# Call steps followed in one value: ``get()`` is one, ``get().fetch()`` two.
# Past the cap the value escapes.
CALL_STEPS = 3
# The longest chain (names and call steps) a function-local alias of a
# result may stand for: ``p = p.parent`` in a loop would grow it without end.
# Past the cap the value escapes.
MAX_ALIAS_CHAIN = 6
# The positions of a result record: ``result-<p>`` for a call whose callee
# is reached through an import binding, ``own-<p>`` for a call of this
# file's own getter by name.
RESULT_POSITIONS = frozenset(
    f"{prefix}-{position}"
    for prefix in ("result", "own")
    for position in ("write", "call", "value")
)
# A record that hands on every getter its chain reaches (a tracked return of
# a chain that may hold a function, ``return getter.get``) and taints nothing
# else.
REF_POSITION = "ref"
# The nodes that open a scope a ``return`` or an alias belongs to.
_SCOPE_NODES = frozenset(
    {
        "function_definition",
        "lambda",
        "class_definition",
        "module",
        "list_comprehension",
        "set_comprehension",
        "dictionary_comprehension",
        "generator_expression",
        "type_alias_statement",
    }
)


def _introspects(
    analysis: Any, handout: frozenset[str] | None, routes_seen: Sequence[bool]
) -> bool:
    """H1 (#706, extended per the plan review's B1): whether the file may
    hand out a namespace holding a getter or a result alias, or reach the
    module object a getter lives in, without spelling the getter's name. Such
    a file has no tracked getters and no result aliases (the old escape holds
    there). ``handout`` is :func:`_namespace_handout`'s result and
    ``routes_seen`` what it appended, so H1 is
    #724's token rule with its R-724-2 allow-list, plus three cases that rule
    narrows for import bindings alone:

    - a frame's ``f_locals``/``f_globals`` read by a constant key
      (``handout`` not empty): the key may name a getter or a result alias;
    - any mention of ``f_locals`` or another name that may write a
      function's locals (``analysis.frame_locals``);
    - a spelling of a route to the builtins (:data:`_BUILTINS_ROUTES`:
      ``__builtins__``, ``__self__``, ``bltns``, the rest of
      ``_DYNAMIC_ATTRIBUTES`` with the tokens), on which a computed member
      may be ``globals``."""
    return bool(handout is None or handout or analysis.frame_locals or any(routes_seen))


def _scope_node(node: Any) -> Any:
    """The nearest scope-opening ancestor of ``node``."""
    node = node.parent
    while node is not None and node.type not in _SCOPE_NODES:
        node = node.parent
    return node


def _own_yield(function: Any) -> bool:
    """Whether a function's own body (not a nested scope) has a ``yield``."""
    stack = list(function.named_children)
    while stack:
        node = stack.pop()
        if node.type in ("function_definition", "lambda", "class_definition"):
            continue
        if node.type == "yield":
            return True
        stack.extend(node.named_children)
    return False


def _tracked_getters(analysis: Any) -> dict[int, str]:
    """G1 (#706): every ``def`` directly at module scope (not under ``if``,
    ``try`` or a class, not nested), undecorated, not ``async``, with no
    ``yield`` of its own and a name that is not a dunder (the runtime calls a
    module's ``__getattr__`` and ``__dir__`` itself), by node id. Several
    definitions of one name are one getter (their returns are joined)."""
    from . import py_scope as ps

    found: dict[int, str] = {}
    for child in analysis.root.named_children:
        if child.type != "function_definition":
            continue
        if any(token.type == "async" for token in child.children):
            continue
        name = child.child_by_field_name("name")
        if name is None or _own_yield(child):
            continue
        text = ps._text(name, analysis.source)
        if not ps._dunder(text):
            found[child.id] = text
    return found


def _tracked_return(outer: Any, getters: Mapping[int, str]) -> str | None:
    """The tracked getter whose own ``return`` the value ``outer`` is:
    ``return X``, or one tuple level, ``return X, Y`` / ``return (X, Y)``."""
    node = outer
    parent = node.parent
    if parent is not None and parent.type in ("expression_list", "tuple"):
        node, parent = parent, parent.parent
        while parent is not None and parent.type == "parenthesized_expression":
            node, parent = parent, parent.parent
    if parent is None or parent.type != "return_statement":
        return None
    scope = _scope_node(parent)
    return getters.get(scope.id) if scope is not None else None


def _unsafe_dunder(chain: Sequence[str]) -> bool:
    from . import py_scope as ps

    return any(ps._dunder(part) and part not in _SAFE_DUNDERS for part in chain)


def _result_steps(node: Any, source: bytes) -> tuple[list[str], Any]:
    """Walk up from a value: parentheses, then subscripts that each have one
    integer literal key, any number of them before the first attribute
    (``pair()[1]``, ``pair()[0][1]``; a nested tuple return is an escape,
    so only one level can hold a module), then attribute reads.
    ``(chain, outermost node)``."""
    from . import py_scope as ps

    chain: list[str] = []
    while True:
        parent = node.parent
        if parent is None:
            break
        if (
            parent.type == "parenthesized_expression"
            and len([c for c in parent.named_children if c.type != "comment"]) == 1
        ):
            node = parent
            continue
        if (
            parent.type == "subscript"
            and not chain
            and ps._same(node, parent.child_by_field_name("value"))
        ):
            keys = [
                child
                for index, child in enumerate(parent.children)
                if parent.field_name_for_child(index) == "subscript"
            ]
            if len(keys) == 1 and keys[0].type == "integer":
                node = parent
                continue
            break
        if parent.type == "attribute" and ps._same(
            node, parent.child_by_field_name("object")
        ):
            attribute = parent.child_by_field_name("attribute")
            if attribute is None:
                break
            chain.append(ps._text(attribute, source))
            node = parent
            continue
        break
    return chain, node


def _alias_targets(analysis: Any, outer: Any) -> tuple[Any, list[str], bool] | None:
    """``(scope, names, unpack)`` when ``outer`` is the whole value of a plain
    assignment statement ``x = V`` or ``a, b = V`` whose targets are bare
    identifiers, in a ``def`` scope the pass analyzed (not a lambda,
    comprehension, generator expression or class body), none declared
    ``global`` or ``nonlocal`` and none mangled; else ``None``."""
    from . import py_scope as ps

    parent = outer.parent
    if parent is None or parent.type != "assignment":
        return None
    left = parent.child_by_field_name("left")
    right = parent.child_by_field_name("right")
    if left is None or right is None or right.id != outer.id:
        return None
    if parent.child_by_field_name("type") is not None:
        return None
    statement = parent.parent
    if statement is None or statement.type != "expression_statement":
        return None
    if left.type == "identifier":
        targets, unpack = [left], False
    elif left.type in ("pattern_list", "tuple_pattern"):
        targets = [c for c in left.named_children if c.type != "comment"]
        if not targets or any(c.type != "identifier" for c in targets):
            return None
        unpack = True
    else:
        return None
    scope_node = _scope_node(parent)
    if scope_node is None or scope_node.type != "function_definition":
        return None
    scope = analysis.scopes.get((scope_node.id, "scope"))
    if scope is None or scope.poisoned:
        return None
    names = [ps._text(target, analysis.source) for target in targets]
    if any(name in scope.globals or name in scope.nonlocals for name in names):
        return None
    source = analysis.source
    if any(ps._mangled_names(t, n, source) for t, n in zip(targets, names)):
        return None
    return scope, names, unpack


def _classify_result(analysis: Any, node: Any, aliases: bool) -> tuple[Any, ...] | None:
    """The use of a tracked value at ``node`` (a call, or a read of a result
    alias): ``None`` (inert), ``("alias", scope, names, chain)``,
    ``("call", chain, call)`` for a member call, or ``(position, chain)``
    with position ``write`` or ``value``. The allow-list is
    :func:`_classify_use`'s, plus a discarded expression statement (inert)
    and, outside H1 files, an alias binding."""
    from . import py_scope as ps

    chain, top = _result_steps(node, analysis.source)
    if chain and top.id in analysis.attribute_targets:
        return "write", chain
    if top.type == "subscript" and (
        top.id in analysis.attribute_targets
        or any(top.id == target.id for target in analysis.subscript_targets)
    ):
        return "value", chain
    call = ps._callee_call(top)
    if call is not None:
        # Calling the value itself is off the list; a member call reads a
        # name, and its result is a value to follow (the member may be a
        # getter of the module).
        return ("call", chain, call) if chain else ("value", chain)
    name = _setattr_write(analysis, top)
    if name is not None:
        return "write", [*chain, name]
    if _inert_context(top):
        return None
    parent = top.parent
    if (
        parent is not None
        and parent.type == "expression_statement"
        and len([c for c in parent.named_children if c.type != "comment"]) == 1
    ):
        return None
    targets = _alias_targets(analysis, top) if aliases else None
    if targets is not None:
        scope, names, unpack = targets
        if not unpack or not chain:
            return "alias", scope, names, chain
    return "value", chain


def _callee_refs(
    analysis: Any,
    call: Any,
    import_infos: Mapping[str, list[Mapping[str, str]]],
    own_getters: AbstractSet[str],
) -> list[tuple[str, tuple[str, ...]]]:
    """``[(base, callee path)]`` a call's callee may denote: base ``""`` for
    this file's own getter by spelling, else an import binding's record
    base with the names read off it."""
    from . import py_scope as ps

    source = analysis.source
    node = call.child_by_field_name("function")
    names: list[str] = []
    while node is not None:
        node = ps._unwrap(node, skip_comments=True)
        if node.type != "attribute":
            break
        attribute = node.child_by_field_name("attribute")
        if attribute is None:
            return []
        names.append(ps._text(attribute, source))
        node = node.child_by_field_name("object")
    if node is None or node.type != "identifier":
        return []
    names.reverse()
    refs: list[tuple[str, tuple[str, ...]]] = []
    if not names:
        for spelling in sorted(ps._spellings(node, source) & own_getters):
            refs.append(("", (spelling,)))
    for info in _candidates(analysis, node, import_infos):
        record = _record(info, CALL_MARK, names)
        if record[2:]:
            refs.append((record[0], tuple(record[2:])))
    return refs


def _scan_results(
    analysis: Any,
    facts: _Facts,
    import_infos: Mapping[str, list[Mapping[str, str]]],
    gate: bool,
) -> None:
    """#706: record every use of a call that may invoke a tracked getter
    (``get()``, ``G.get()``, ``x.fetch()`` on a tracked value), followed
    through member calls and function-local aliases, as result records
    ``(base, "result-<p>" | "own-<p>", *callee, "()", *chain)``; and every
    reference to this file's own getter that is not a direct callee as an
    escape of whatever it returns (``("", "own-value", name, "()")``)."""
    from . import py_scope as ps

    source = analysis.source
    own = frozenset(facts.getters)
    records = facts.uses
    # (scope id, name) -> {(base, callee, prefix)}: what a result alias may
    # hold, the prefix being the chain read off the call result.
    aliases: dict[tuple[int, str], set[tuple[str, tuple[str, ...], tuple[str, ...]]]]
    aliases = {}
    # scope id -> the ``def`` node of that alias scope.
    alias_defs: dict[int, Any] = {}
    Source = tuple[tuple[str, tuple[str, ...]], tuple[str, ...]]

    def emit(
        ref: tuple[str, tuple[str, ...]],
        prefix: Sequence[str],
        position: str,
        chain: Sequence[str],
    ) -> None:
        base, callee = ref
        kind = ("own-" if base == "" else "result-") + position
        records.add((base, kind, *callee, CALL_MARK, *prefix, *chain))

    def handle(sources: list[Source], node: Any) -> bool:
        """Classify one use for every source; whether an alias grew."""
        found = _classify_result(analysis, node, not gate)
        if found is None:
            return False
        if found[0] == "alias":
            _kind, scope, names, chain = found
            grew = False
            for ref, prefix in sources:
                full = (*prefix, *chain)
                if _unsafe_dunder(full) or len(full) > MAX_ALIAS_CHAIN:
                    # ``ns = get().__dict__`` hands out the namespace; a chain
                    # past the cap is not followed: both escape.
                    emit(ref, prefix, "value", chain)
                    continue
                alias_defs[id(scope)] = scope.node
                for name in names:
                    bucket = aliases.setdefault((id(scope), name), set())
                    item = (ref[0], ref[1], full)
                    if item not in bucket:
                        bucket.add(item)
                        grew = True
            return grew
        position, chain = found[0], found[1]
        if position == "call" and not _unsafe_dunder(chain):
            following: list[Source] = []
            for ref, prefix in sources:
                if prefix.count(CALL_MARK) + 1 >= CALL_STEPS:
                    emit(ref, prefix, "value", [])
                else:
                    following.append((ref, (*prefix, *chain, CALL_MARK)))
            return bool(following) and handle(following, found[2])
        for ref, prefix in sources:
            emit(ref, prefix, position, chain)
        return False

    stack = [analysis.root]
    calls: list[Any] = []
    while stack:
        node = stack.pop()
        stack.extend(node.named_children)
        if node.type == "call":
            calls.append(node)
    for call in calls:
        refs = _callee_refs(analysis, call, import_infos, own)
        if refs:
            handle([(ref, ()) for ref in refs], call)

    reads = [ident for ident in analysis.identifier_nodes if _holder_read(ident)]
    for ident in reads:
        for spelling in sorted(ps._spellings(ident, source) & own):
            if ps._callee_call(ident) is None:
                # The getter handed on as a value: whatever it returns escapes.
                records.add(("", "own-value", spelling, CALL_MARK))
    if not aliases:
        return
    # A read of an alias is any identifier of its spelling whose lookup
    # decides in the alias's scope (closures included) or cannot say where.
    # A read from a nested scope (a closure, lambda, comprehension or class
    # body) is an escape of the alias: the capture puts it in a cell another
    # module may read and write (``fn.__closure__[i].cell_contents``,
    # ``inspect.getclosurevars(fn).nonlocals``). An alias read may bind a new
    # alias, so the reads are found again each round; every (read, source)
    # pair is handled once.
    deciding: dict[int, Any] = {}
    done: dict[int, set[tuple[str, tuple[str, ...], tuple[str, ...]]]] = {}
    changed = True
    while changed:
        changed = False
        alias_names = {name for _scope, name in aliases}
        for ident in reads:
            spellings = ps._spellings(ident, source)
            if not spellings & alias_names:
                continue
            if ident.id not in deciding:
                deciding[ident.id] = analysis.lookup_scope(ident)
            decided = deciding[ident.id]
            seen = done.setdefault(ident.id, set())
            sources: list[Source] = []
            read_scope = _scope_node(ident)
            for (scope_id, name), items in list(aliases.items()):
                if name not in spellings:
                    continue
                if decided is not None and id(decided) != scope_id:
                    continue
                own_def = alias_defs[scope_id]
                nested = (
                    own_def is None or read_scope is None or read_scope.id != own_def.id
                )
                for item in sorted(items - seen):
                    seen.add(item)
                    if nested:
                        emit((item[0], item[1]), item[2], "value", [])
                    else:
                        sources.append(((item[0], item[1]), item[2]))
            if sources and handle(sources, ident):
                changed = True


def _cell_read(analysis: Any, ident: Any) -> bool:
    """``X.cell_contents`` only read (PY-6): an attribute that is not a
    target (assignment, augmented assignment, ``del``) and not the receiver
    of a dunder (``type(c).cell_contents.__set__``)."""
    from . import py_scope as ps

    parent = ident.parent
    if (
        parent is None
        or parent.type != "attribute"
        or not ps._same(ident, parent.child_by_field_name("attribute"))
        or parent.id in analysis.attribute_targets
    ):
        return False
    outer = parent
    while outer.parent is not None and outer.parent.type == "parenthesized_expression":
        outer = outer.parent
    above = outer.parent
    if (
        above is not None
        and above.type == "attribute"
        and ps._same(outer, above.child_by_field_name("object"))
    ):
        method = above.child_by_field_name("attribute")
        return method is not None and not ps._dunder(ps._text(method, analysis.source))
    return True


# pytest-mock fixture names whose ``.patch`` is ``unittest.mock.patch``.
_MOCKER_NAMES = frozenset(
    {"mocker", "module_mocker", "class_mocker", "package_mocker", "session_mocker"}
)


def _callee_names(call: Any, source: bytes) -> list[str] | None:
    """The dotted names of a call's callee (``mock.patch.object`` gives
    ``["mock", "patch", "object"]``), through parentheses; ``None`` unless
    it is an identifier or a plain attribute chain."""
    from . import py_scope as ps

    node = call.child_by_field_name("function")
    node = ps._unwrap(node, skip_comments=True) if node is not None else None
    names: list[str] = []
    while node is not None and node.type == "attribute":
        attribute = node.child_by_field_name("attribute")
        if attribute is None:
            return None
        names.append(ps._text(attribute, source))
        node = node.child_by_field_name("object")
        node = ps._unwrap(node, skip_comments=True) if node is not None else None
    if node is None or node.type != "identifier":
        return None
    names.append(ps._text(node, source))
    return list(reversed(names))


# #705 E6-9b: the methods of pytest's ``MonkeyPatch`` that can redirect a
# name or an import, matched by name on ANY receiver. Proving which receiver
# is a MonkeyPatch cannot be done (pytest hands it out through
# ``request.node.funcargs``, autouse fixtures, ``pytest_fixture_setup`` hooks,
# closure cells, frames and ``locals()``; P6-17), but every route ends in a
# spelled method call or a spelled method name.
_WRITE_METHODS = frozenset({"setattr", "delattr"})
_SYSPATH_METHOD = "syspath_prepend"
# ``setitem``/``delitem`` take the mapping as a value, which the #697 use
# rules already classify (``vars(svc)``, ``svc.__dict__``, ``sys.modules``,
# ``f_globals``), so their name adds nothing.
_PATCH_METHOD_NAMES = _WRITE_METHODS | {"setitem", "delitem", _SYSPATH_METHOD}
_CLASS_PATTERN_PATCHERS = _PATCH_METHOD_NAMES | {"patch"}
_MP_FIXTURE_ARGUMENTS = frozenset({"target", "name"})
_GETFIXTUREVALUE = "getfixturevalue"
_FIXTURE_MOCKER = "mocker"


class _Patchers:
    """The pytest-mock fixtures one file obtains by name (#705 P6-7, P6-12,
    P6-15): ``request.getfixturevalue('<pytest-mock fixture>')`` yields a
    fixture whose ``.patch`` is ``patch``; it and every name bound from it by
    assignment, walrus or ``with ... as`` is a *mocker* value, whose uses
    Tier 1's ``_MOCKER`` allow-list decides. A ``getfixturevalue`` call with a
    computed name, an ``X.getfixturevalue`` attribute that is not called
    directly and the constant ``"getfixturevalue"`` as a call argument may
    fetch any fixture (``computed_fixture``).

    Fold 6 (E6-9b) removed the ``MonkeyPatch`` instance and class kinds of
    folds 3-5 (the ``monkeypatch`` parameter seed, ``MonkeyPatch`` imports,
    ``MonkeyPatch()``/``.context()``, their alias fixpoint, the
    ``MonkeyPatch`` allow-list with its unreachable-alias and annotation
    rules): :func:`_scan_patch_methods` matches the methods themselves."""

    def __init__(self, analysis: Any) -> None:
        from . import py_scope as ps

        self.analysis = analysis
        self.source = analysis.source
        self.mockers: set[str] = set()
        self.computed_fixture = False
        pairs: list[tuple[Any, Any]] = []
        stack = [analysis.root]
        while stack:
            node = stack.pop()
            stack.extend(node.named_children)
            if node.type == "assignment":
                pairs.append(
                    (
                        node.child_by_field_name("left"),
                        node.child_by_field_name("right"),
                    )
                )
            elif node.type == "named_expression":
                pairs.append(
                    (
                        node.child_by_field_name("name"),
                        node.child_by_field_name("value"),
                    )
                )
            elif node.type == "as_pattern":
                value = node.named_children[0] if node.named_children else None
                pairs.append((node.child_by_field_name("alias"), value))
            elif node.type == "call" and self._fixture_call(node):
                first = _first_argument(node)
                if first is None or ps._constant_string(first, self.source) is None:
                    self.computed_fixture = True
            elif node.type == "attribute" and self._fixture_attribute(node):
                # P6-12: ``g = request.getfixturevalue; g("mocker")``.
                self.computed_fixture = True
            elif _argument_string(node, self.source) == _GETFIXTUREVALUE:
                # P6-15: ``getattr(request, "getfixturevalue")("mocker")``
                # (any call taking the name: ``getattr``, ``attrgetter``,
                # ``methodcaller``); a plain constant names nothing.
                self.computed_fixture = True
        changed = True
        while changed:
            changed = False
            for target, value in pairs:
                if target is None or value is None or self.kind(value) is None:
                    continue
                target = ps._unwrap(target, skip_comments=True)
                if target.type == "as_pattern_target" and target.named_children:
                    target = target.named_children[0]
                if target.type != "identifier":
                    continue
                name = ps._text(target, self.source)
                if name not in self.mockers:
                    self.mockers.add(name)
                    changed = True

    def _fixture_attribute(self, node: Any) -> bool:
        """An ``X.getfixturevalue`` attribute that is not the callee of a
        direct call."""
        from . import py_scope as ps

        attribute = node.child_by_field_name("attribute")
        return (
            attribute is not None
            and ps._text(attribute, self.source) == _GETFIXTUREVALUE
            and ps._callee_call(node) is None
        )

    def _fixture_call(self, node: Any) -> bool:
        from . import py_scope as ps

        function = node.child_by_field_name("function")
        function = ps._unwrap(function, skip_comments=True) if function else None
        if function is None or function.type != "attribute":
            return False
        attribute = function.child_by_field_name("attribute")
        return (
            attribute is not None
            and ps._text(attribute, self.source) == _GETFIXTUREVALUE
        )

    def kind(self, node: Any) -> str | None:
        """``_FIXTURE_MOCKER`` for a pytest-mock fixture value, else
        ``None``."""
        from . import py_scope as ps

        node = ps._unwrap(node, skip_comments=True)
        if node.type == "identifier":
            return (
                _FIXTURE_MOCKER if ps._text(node, self.source) in self.mockers else None
            )
        if node.type == "call" and self._fixture_call(node):
            first = _first_argument(node)
            value = ps._constant_string(first, self.source) if first else None
            if value in _MOCKER_NAMES:
                return _FIXTURE_MOCKER
        return None


# P6-21: the expressions a constant name may be spelled with (``"set"
# "attr"``, ``"set" + "attr"``, ``("setattr")``), decoded by Tier 1's
# ``_constant_string``.
_NAME_STRING_NODES = frozenset(
    {"string", "concatenated_string", "binary_operator", "parenthesized_expression"}
)


def _argument_string(node: Any, source: bytes) -> str | None:
    """A constant string that names something by string: a call argument,
    positional or a keyword value (``getattr(mp, "setattr")``,
    ``inspect.getattr_static(mp, attr="setattr")``; #705 P6-21), or a
    subscript key (``MonkeyPatch.__dict__["setattr"]``, ``vars(type(mp))
    ["setattr"]``; P6-22). Any spelling ``_constant_string`` decodes counts:
    adjacent literals (with comments between them), ``+`` and parentheses.
    ``None`` otherwise; a name computed at run time (``M = "setattr";
    getattr(mp, M)``) is §15 R12."""
    from . import py_scope as ps

    if node.type not in _NAME_STRING_NODES or node.parent is None:
        return None
    parent = node.parent
    if parent.type == "keyword_argument" and ps._same(
        node, parent.child_by_field_name("value")
    ):
        parent = parent.parent
    if parent is None:
        return None
    if parent.type == "subscript":
        if ps._same(node, parent.child_by_field_name("value")):
            return None
    elif parent.type != "argument_list":
        return None
    return ps._constant_string(node, source)


def _operator_module(analysis: Any, receiver: Any) -> bool:
    """Whether the ordinary Tier 1 lookup resolves a receiver to the
    ``operator`` module (``operator.setitem`` is a namespace writer Tier 1
    already handles; E6-9b)."""
    from . import py_scope as ps

    receiver = ps._unwrap(receiver, skip_comments=True)
    if receiver.type != "identifier":
        return False
    outcome = analysis.lookup(receiver)
    binding = outcome.get("binding") or {}
    return (
        outcome.get("outcome") == "import"
        and binding.get("form") == "import"
        and binding.get("module") == "operator"
    )


def _scan_patch_methods(analysis: Any, facts: _Facts) -> None:
    """#705 E6-9b: in every Python file (causes O-2-scoped by the file's own
    classification), ``X.setattr``, ``X.delattr``, ``X.setitem``,
    ``X.delitem`` and ``X.syspath_prepend`` are handled as calls on a pytest
    ``MonkeyPatch``, whatever ``X`` is (a name, subscript, call or
    attribute), unless Tier 1 resolves ``X`` to the ``operator`` module.

    - ``setattr``/``delattr``: the string form (``setattr("m.t", v)``, two
      positional arguments; ``delattr("m.t")``, one) with a constant target
      taints the module it names wholly; with any other target it is an
      ``unresolvable-writer``. With more positional arguments (the object
      form ``setattr(obj, "name", v)``, or an unbound
      ``MonkeyPatch.setattr(mp, "m.t", v)``), the second one must be a
      constant: a computed name is an ``unresolvable-writer``, a constant
      one is the dotted-string rule's or the object's escape (``svc`` as an
      argument is a whole-module escape). A ``target=``/``name=`` keyword
      must be constant, and a ``*``/``**`` splat is an
      ``unresolvable-writer``.
    - ``syspath_prepend`` is ``sys.path.insert(0, p)`` plus
      ``importlib.invalidate_caches()``: a ``module-system`` cause (P6-10).
    - ``setitem``/``delitem``: no cause of their own (see
      ``_PATCH_METHOD_NAMES``).
    - The same names reached without a direct call (``s = mp.setattr``) or as
      a constant call argument (``getattr(mp, "setattr")``,
      ``operator.methodcaller("setattr", ...)``) are an
      ``unresolvable-writer``, or ``module-system`` for ``syspath_prepend``.

    pytest ran ``OTHER.t`` for each of the president's P6-17 trees (the
    MonkeyPatch obtained through ``request.node.funcargs`` with
    ``usefixtures`` or an autouse fixture, a ``pytest_fixture_setup`` hook, a
    closure cell, a frame's ``f_locals``, a caller's frame, ``locals()`` and
    ``get_type_hints(localns=locals())``), and for the P6-18 string spellings
    of ``getfixturevalue``: each ends in a spelled ``.setattr(...)``."""
    from . import py_scope as ps

    source = analysis.source
    stack = [analysis.root]
    while stack:
        node = stack.pop()
        stack.extend(node.named_children)
        name = _argument_string(node, source)
        if name in _WRITE_METHODS:
            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
        elif name == _SYSPATH_METHOD:
            facts.shutoff.add(CAUSE_MODULE_SYSTEM)
        if node.type != "attribute":
            continue
        attribute = node.child_by_field_name("attribute")
        receiver = node.child_by_field_name("object")
        method = ps._text(attribute, source) if attribute is not None else ""
        if method not in _PATCH_METHOD_NAMES or receiver is None:
            continue
        if _operator_module(analysis, receiver):
            continue
        call = ps._callee_call(node)
        if method == _SYSPATH_METHOD:
            facts.shutoff.add(CAUSE_MODULE_SYSTEM)
            continue
        if method not in _WRITE_METHODS:
            continue
        if call is None:
            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
            continue
        _patch_method_call(call, method, facts, source)


def _patch_method_call(call: Any, method: str, facts: _Facts, source: bytes) -> None:
    """One ``X.setattr(...)``/``X.delattr(...)`` call (:func:`_scan_patch_methods`)."""
    from . import py_scope as ps

    arguments = ps._call_arguments(call)
    positional: list[Any] = []
    for argument in arguments:
        if argument.type in ("list_splat", "dictionary_splat"):
            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
            return
        if argument.type == "keyword_argument":
            key = argument.child_by_field_name("name")
            value = argument.child_by_field_name("value")
            if (
                key is not None
                and ps._text(key, source) in _MP_FIXTURE_ARGUMENTS
                and (value is None or ps._constant_string(value, source) is None)
            ):
                facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
                return
            continue
        if argument.type != "comment":
            positional.append(argument)
    string_form = 2 if method == "setattr" else 1
    if len(positional) == string_form:
        constant = ps._constant_string(positional[0], source)
        if constant is None:
            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
        else:
            facts.taints.add((constant.replace(":", "."), "*"))
    elif len(positional) > string_form:
        if ps._constant_string(positional[1], source) is None:
            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)


def _scan_patcher_escapes(analysis: Any, facts: _Facts, patchers: _Patchers) -> None:
    """#705 E6-9 (P6-5), amended by E6-9a (P6-13): in every Python file, a
    patcher value (Tier 1's mock module, ``patch`` and ``mocker`` kinds,
    decided by Tier 1's alias sets and its E-21 closed allow-list
    :meth:`.py_scope._Analysis._safe_use`, and a pytest-mock fixture obtained
    by name, :class:`_Patchers`) used anywhere off its allow-list is an
    ``unresolvable-writer`` cause, scoped by O-2: the call that applies it is
    out of sight. pytest ran ``OTHER.t`` for each of the president's trees:
    ``run(patch)`` (``f3_patch_as_arg``), ``@deco(mock.patch)``
    (``f3_patch_decorator_arg``), ``[mock.patch]`` (``f3_patch_list_escape``)
    and ``functools.partial(patch, ...)`` (``f3_patch_partial``). So is any
    computed fixture lookup (:class:`_Patchers`).

    E6-9a (P6-13): production files are scanned too. Tier 1's E-21 makes the
    hand-off file dynamic for its own lookups, but the hidden write still
    reaches another module (``f4_prod_patch_param``). The cause is scoped by
    O-2 through the file's own classification. MonkeyPatch values need no
    escape rule since fold 6: :func:`_scan_patch_methods` sees their
    methods."""
    from . import py_scope as ps

    if patchers.computed_fixture:
        facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
        return
    stack = [analysis.root]
    while stack:
        node = stack.pop()
        stack.extend(node.named_children)
        if node.type not in ("identifier", "attribute", "call", "subscript"):
            continue
        if node.type == "identifier" and (ps._name_part(node) or _in_import(node)):
            continue
        for kind in (ps._MOCK, ps._PATCH, ps._MOCKER):
            if analysis._sensitive(node, kind) and not analysis._safe_use(node, kind):
                facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
                return
        if node.type == "subscript":
            continue
        if patchers.kind(node) is not None and not analysis._safe_use(node, ps._MOCKER):
            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
            return


def _scan_patchers(
    analysis: Any, facts: _Facts, patchers: _Patchers | None = None
) -> None:
    """Patcher targets (#705 E6-5), a closed list of callees:
    ``unittest.mock``/``mock`` ``patch`` (``mock.patch``, a pytest-mock
    fixture's ``.patch``, a bare ``patch``), ``X.patch.object``,
    ``X.patch.dict`` and ``X.patch.multiple`` (``MonkeyPatch`` methods are
    :func:`_scan_patch_methods`, since fold 6 on any receiver). A string target that is not a constant names a
    module the rules cannot compute: an ``unresolvable-writer`` cause (scoped
    by O-2 like any cause). So is a ``patch.object`` attribute that is not a
    constant, and a first argument of ``patch.multiple``/``patch.dict`` that
    is not a constant string. A constant string target taints the module it
    names wholly (``patch.multiple('svc', ...)`` rebinds several of its
    globals), besides the dotted-string rule.

    **Spellings (#705 P6-3).** Which callee is ``patch`` is decided at the
    use site by the Tier 1 W-3 alias sets (:meth:`.py_scope._Analysis.\
    _sensitive`): the mock-module names (``from unittest import mock as m``
    gives ``m.patch``), the ``patch`` names (``from unittest.mock import
    patch as p``), and every local alias of the mock module, ``patch`` or a
    pytest-mock fixture, besides the literal spellings above; a
    ``getfixturevalue`` of a pytest-mock fixture name holds a fixture whose
    ``.patch`` is ``patch`` (:class:`_Patchers`). The president's trees
    ``h3a``/``h3b`` ran ``OTHER.t`` under pytest through these spellings, and ``h3c``
    through ``patch.multiple(MOD, t=...)`` with a computed ``MOD``.

    treesitter-chunker#699 PY-10 (ruling R-699-1 Q6, in the E6-9b style):
    ``X.patch(...)``, ``X.patch.object(...)``, ``.dict`` and ``.multiple``
    are patcher calls on ANY receiver (a parameter, ``S().patch(...)``,
    ``requests.patch(url)``): a computed target is an
    ``unresolvable-writer``, a constant one taints the module it names. The
    same names reached without a direct call (``p = mk.patch``) or by a
    constant name (``getattr(mk, "patch")``) are an ``unresolvable-writer``
    (:func:`_scan_patch_reads`)."""
    from . import py_scope as ps

    source = analysis.source
    patchers = patchers if patchers is not None else _Patchers(analysis)

    def is_patch(node: Any, names: Sequence[str]) -> bool:
        if node is not None and analysis._sensitive(node, ps._PATCH):
            return True
        if node is not None and ps._is_patch_attribute(node, source):
            # PY-10: ``X.patch`` on any receiver, which subsumes the former
            # name checks (``mock.patch``, a fixture's or a fixture alias's
            # ``.patch``).
            return True
        return list(names) == ["patch"]  # a bare ``patch``

    stack = [analysis.root]
    while stack:
        node = stack.pop()
        stack.extend(node.named_children)
        if node.type != "call":
            continue
        function = node.child_by_field_name("function")
        function = (
            ps._unwrap(function, skip_comments=True) if function is not None else None
        )
        receiver = (
            function.child_by_field_name("object")
            if function is not None and function.type == "attribute"
            else None
        )
        names = _callee_names(node, source)
        if not names and receiver is not None and function is not None:
            # PY-10: ``S().patch(u)``, ``ms[0].patch.object(...)``.
            names = [ps._text(function.child_by_field_name("attribute"), source)]
        if not names:
            continue
        arguments = [
            argument
            for argument in ps._call_arguments(node)
            if argument.type not in ("keyword_argument", "comment")
        ]
        first = arguments[0] if arguments else None
        constant = ps._constant_string(first, source) if first is not None else None
        last = names[-1]
        patch = is_patch(function, names)
        method = (
            receiver is not None
            and last in ("object", "dict", "multiple")
            and is_patch(receiver, names[:-1])
        )
        if patch:
            if first is None or constant is None:
                facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
            else:
                facts.taints.add((constant.replace(":", "."), "*"))
        elif method and last == "object":
            second = arguments[1] if len(arguments) > 1 else None
            if second is None or ps._constant_string(second, source) is None:
                facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
        elif method:
            if constant is not None:
                facts.taints.add((constant.replace(":", "."), "*"))
            else:
                # P6-3: ``patch.multiple(MOD, t=f)`` with a computed ``MOD``
                # (and ``patch.dict`` alike) names a target no rule computes.
                facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)


def _scan_patch_reads(analysis: Any, facts: _Facts) -> None:
    """treesitter-chunker#699 PY-10, the E6-9b form of the hand-off rule:
    ``X.patch`` for any ``X`` read other than applied where it is read
    (called, or ``.object``/``.dict``/``.multiple`` called on it), and a
    constant ``"patch"`` that names a member by string (a call argument or
    subscript key, whole or as a dotted component: ``getattr(mk, "patch")``,
    ``operator.methodcaller("patch", t)``), are an ``unresolvable-writer``:
    the call that applies the patcher is out of sight. A ``.patch`` the mock
    rules recognise (``p = mock.patch``) is an alias whose uses
    :func:`_scan_patcher_escapes` checks instead. Writing ``X.patch = v``
    reads no patcher."""
    from . import py_scope as ps

    source = analysis.source
    stack = [analysis.root]
    while stack:
        node = stack.pop()
        stack.extend(node.named_children)
        value = _argument_string(node, source)
        if value is not None and "patch" in ps._TOKEN_PARTS.split(value):
            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
            return
        if ps._patch_token_string(node, source):
            # R-699-12 items 1 and 2: ``"patch"`` exactly in any position
            # (``__match_args__ = ("patch",)``, ``case {"patch": p}``), or a
            # private patcher as a word of any constant string
            # (``getattr(mk, "_pa" "tch")``).
            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
            return
        if node.type == "identifier" and (
            ps._spellings(node, source) & ps._PRIVATE_PATCH_TOKENS
        ):
            # R-699-12 item 1: a private patcher (or ``_get_target``) in any
            # identifier role: a name, an attribute on any receiver (R-699-11),
            # an import or alias name, a keyword, a class-pattern keyword.
            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
            return
        if node.type == "keyword_pattern" and node.named_children:
            # R-699-10 item 3: a class-pattern keyword reads the subject's
            # attribute (``case object(patch=p)`` is ``p = subject.patch``),
            # so ``patch`` and the E6-9b ``MonkeyPatch`` methods spelled
            # there are patchers read out of sight, whatever the subject.
            keyword = node.named_children[0]
            if ps._spellings(keyword, source) & _CLASS_PATTERN_PATCHERS:
                facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
                return
        if (
            node.type == "attribute"
            and ps._is_patch_attribute(node, source)
            and node.id not in analysis.attribute_targets
            and not ps._patch_applied(node, source)
            and not analysis._sensitive(node, ps._PATCH)
        ):
            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)
            return


def import_group(
    analysis: Any, head: Any, outcome: Mapping[str, Any]
) -> list[dict[str, str]]:
    """The import bindings of a lookup that met two or more imports and
    nothing else (9.4: they narrow to the group in ``imports`` mode), or
    ``[]``."""
    from . import py_scope as ps

    scope = analysis.decided
    if outcome != {"outcome": "none", "reason": "mixed-bindings"} or scope is None:
        return []
    name = ps._text(head, analysis.source)
    bindings = list(scope.bindings.get(name, ()))
    if (
        len(bindings) < 2
        or any(binding.cls != ps.IMPORT or not binding.info for binding in bindings)
        or (scope.kind in (ps._MODULE, ps._CLASS) and ps._dunder(name))
        or (scope.kind == ps._MODULE and name in ps.SHADOWED_NAMES)
    ):
        return []
    return [dict(binding.info) for binding in bindings]


def member_chain(node: Any, head: Any, source: bytes) -> list[str] | None:
    """The attribute names of a member callee after its head identifier
    (``pkg.util.helper`` gives ``["util", "helper"]``), read from the tree;
    ``None`` unless the callee is a plain attribute chain."""
    from . import py_scope as ps

    names: list[str] = []
    current = node
    while current is not None and current.type == "attribute":
        attribute = current.child_by_field_name("attribute")
        if attribute is None:
            return None
        names.append(ps._text(attribute, source))
        current = current.child_by_field_name("object")
    if current is None or not ps._same(current, head) or not names:
        return None
    return list(reversed(names))


# ---------------------------------------------------------------------------
# The assembly half


@dataclass(frozen=True)
class PyFile:
    """What Tier 2 reads from one Python file's scope facts."""

    path: str
    dotted: str
    package: bool
    supported: bool
    exports: Mapping[str, Any] = field(default_factory=dict)
    missing: str = "export-not-found"
    stars: tuple[str, ...] = ()
    groups: Mapping[str, Any] = field(default_factory=dict)
    chains: Mapping[str, Any] = field(default_factory=dict)
    # Every import binding landing in the module namespace, by name (E6-2).
    module_imports: Mapping[str, Any] = field(default_factory=dict)
    # Names a package's ``__init__.py`` binds only to its own submodule.
    own_submodules: frozenset[str] = frozenset()
    # Proof declaration -> the module-scope name it is exported under.
    exported: Mapping[tuple[str, int, int], frozenset[str]] = field(
        default_factory=dict
    )


def dotted_name(path: str) -> tuple[str, bool]:
    """``(dotted module name, is a package)`` of a root-relative ``.py``
    path; ``("", True)`` for a root-level ``__init__.py``."""
    parts = path.split("/")
    if parts[-1] == "__init__.py":
        return ".".join(parts[:-1]), True
    return ".".join([*parts[:-1], parts[-1][: -len(".py")]]), False


@dataclass(frozen=True)
class PyModuleRun:
    """The run's Python module graph, taints and causes (O-2 scoped)."""

    files: Mapping[str, PyFile]
    # Dotted name -> the file defining it (package ``__init__`` or module).
    modules: Mapping[str, str]
    # Directories holding any run file, by root-relative path ("" is the root).
    directories: frozenset[str]
    # Every dotted name a chain may pass through (modules and directories).
    nodes: frozenset[str]
    name_taints: Mapping[str, frozenset[str]] = field(default_factory=dict)
    whole_taints: frozenset[str] = frozenset()
    shutoff: Mapping[str, str] = field(default_factory=dict)
    test_name_taints: Mapping[str, frozenset[str]] = field(default_factory=dict)
    test_whole_taints: frozenset[str] = frozenset()
    test_shutoff: Mapping[str, str] = field(default_factory=dict)
    test_scope: frozenset[str] = frozenset()

    @property
    def file_set(self) -> frozenset[str]:
        """The run's Python file paths (one hashable set, for the pytest
        basedirs computed once per run)."""
        found = self.__dict__.get("_file_set")
        if found is None:
            found = frozenset(self.files)
            object.__setattr__(self, "_file_set", found)
        return found

    def caller_shutoff(self, caller: str) -> str | None:
        active = dict(self.shutoff)
        if caller in self.test_scope:
            active.update(self.test_shutoff)
        for name in SHUTOFF_CAUSES:
            if name in active:
                return f"run-tainted:{name}"
        return None

    def taint_reason(self, caller: str, path: str, name: str | None) -> str | None:
        """Why name ``name`` of module ``path`` (or any name, ``None``) may
        have been written by another file, for a call from ``caller``."""
        test = caller in self.test_scope
        if path in self.whole_taints or (test and path in self.test_whole_taints):
            return REASON_MODULE_TAINT
        if name is None:
            return None
        if name in self.name_taints.get(path, ()) or (
            test and name in self.test_name_taints.get(path, ())
        ):
            return REASON_NAME_TAINT
        return None


class _Builder:
    """Builds a :class:`PyModuleRun` from the run's facts."""

    def __init__(self, facts: Sequence[Mapping[str, Any]]) -> None:
        self.files: dict[str, PyFile] = {}
        self.bindings: dict[str, Mapping[str, Any]] = {}
        self.unsupported: set[str] = set()
        directories: set[str] = {""}
        for item in facts:
            path = str(item.get("path") or "")
            parts = path.split("/")
            for index in range(1, len(parts)):
                directories.add("/".join(parts[:index]))
        self.directories = frozenset(directories)
        modules: dict[str, str] = {}
        for item in sorted(facts, key=lambda fact: str(fact.get("path") or "")):
            scope = item.get("scope_facts") or {}
            if scope.get("language") != "python":
                continue
            path = str(item.get("path") or "")
            if not path.endswith(".py"):
                continue
            dotted, package = dotted_name(path)
            supported = bool(scope.get("supported"))
            bindings = scope.get("module_bindings") or {} if supported else {}
            exports = scope.get("exports") or {} if supported else {}
            exported: dict[tuple[str, int, int], set[str]] = {}
            for name, outcome in exports.items():
                if isinstance(outcome, Mapping) and outcome.get("outcome") == "local":
                    for declaration in outcome.get("proof") or ():
                        key = (
                            str(declaration[0]),
                            int(declaration[1]),
                            int(declaration[2]),
                        )
                        exported.setdefault(key, set()).add(str(name))
            if not supported or bindings.get("unparsed") or not bindings:
                # No module facts (a record of another mode) is unknown too.
                self.unsupported.add(path)
            self.bindings[path] = bindings
            self.files[path] = PyFile(
                path=path,
                dotted=dotted,
                package=package,
                supported=supported and bool(bindings) and not bindings.get("unparsed"),
                exports=exports,
                missing=str(bindings.get("missing") or "export-not-found"),
                stars=tuple(str(star) for star in bindings.get("stars", ())),
                groups=bindings.get("groups") or {},
                chains=bindings.get("chains") or {},
                module_imports=bindings.get("module_imports") or {},
                own_submodules=frozenset(bindings.get("own_submodules") or ()),
                exported={key: frozenset(names) for key, names in exported.items()},
            )
            if dotted:
                modules.setdefault(dotted, path)
                if package:
                    modules[dotted] = path
        self.modules = modules
        self.file_set = frozenset(self.files)
        nodes = set(modules)
        for directory in directories:
            if directory:
                nodes.add(directory.replace("/", "."))
        self.nodes = frozenset(nodes)
        self._getter_names: frozenset[str] | None = None
        self._returned: dict[tuple[str, str], set[str]] = {}

    # -- names ------------------------------------------------------------

    def absolute(self, ref: str, importer: str) -> str | None:
        """A module reference made absolute from ``importer``; ``None`` when
        its dots leave the root."""
        if not ref.startswith("."):
            return ref
        dots = len(ref) - len(ref.lstrip("."))
        rest = ref[dots:]
        package = importer.split("/")[:-1]
        if dots - 1 >= len(package):
            return None
        base = package[: len(package) - (dots - 1)]
        return ".".join(base + ([rest] if rest else []))

    def submodule(self, node: str, name: str) -> str | None:
        child = f"{node}.{name}" if node else name
        return child if child in self.nodes else None

    def attr_values(self, node: str, name: str, seen: set[tuple[str, str]]) -> set[str]:
        """Every module a ``node.name`` attribute may hold: a submodule, a
        module the node's file imports under that name, or one a star
        source provides (followed precisely and leniently)."""
        if (node, name) in seen:
            return set()
        seen.add((node, name))
        found: set[str] = set()
        child = self.submodule(node, name)
        if child is not None:
            found.add(child)
        path = self.modules.get(node)
        file = self.files.get(path) if path is not None else None
        if file is None:
            return found
        entry = file.exports.get(name)
        if isinstance(entry, Mapping) and entry.get("outcome") == "import":
            found |= self.binding_values(entry.get("binding") or {}, path or "", seen)
        for binding in file.module_imports.get(name, ()):
            # E6-2: any import binding of the name, proven or not.
            found |= self.binding_values(binding, path or "", seen)
        for star in file.stars:
            for start in self.targets(star, path or ""):
                found |= self.attr_values(start, name, seen)
        return found

    def binding_values(
        self, binding: Mapping[str, Any], importer: str, seen: set[tuple[str, str]]
    ) -> set[str]:
        """The modules an import binding may denote."""
        if binding.get("form") == "import":
            bound = str(binding.get("bound") or binding.get("module") or "")
            return self.module_values(bound, importer)
        module = str(binding.get("module") or "")
        name = str(binding.get("name") or "")
        found: set[str] = set()
        for start in self.targets(module, importer):
            found |= self.attr_values(start, name, seen)
        return found

    def targets(self, ref: str, writer: str) -> set[str]:
        """The run nodes a module reference written in ``writer`` may denote
        (relative references made absolute; ``""`` for the root)."""
        absolute = self.absolute(ref, writer)
        if absolute is None:
            return set()
        if not absolute:
            return {""}
        if ref.startswith("."):
            return {absolute} if absolute in self.nodes else set()
        return self.starts(absolute, writer)

    def module_values(self, ref: str, writer: str) -> set[str]:
        """THE writer-side reading of a module reference (#705 fold 8), the
        over-approximating twin of :func:`_resolve_binding`: every run node
        ``ref`` may denote, the module path (:meth:`targets`) and, for a dotted
        absolute name, the attribute walk ``getattr(getattr(a, "b"), "c")``
        that ``import a.b.c as m`` binds (E6-3), through every value an
        attribute may hold (:meth:`attr_values`: submodules, every import
        binding of the name, E6-2, and star sources). A use of ``m`` (``m.t =
        f``, ``m`` handed on) and a re-export of it write what CPython bound,
        not only ``a/b/c.py``."""
        found = set(self.targets(ref, writer))
        parts = ref.split(".")
        if ref and not ref.startswith(".") and len(parts) > 1:
            current = self.targets(parts[0], writer)
            for part in parts[1:]:
                following: set[str] = set()
                for node in current:
                    following |= self.attr_values(node, part, set())
                current = following
            found |= current
        return found

    def starts(self, dotted: str, writer: str = "") -> set[str]:
        """The run nodes an absolute dotted name may denote: the root-relative
        module, and the one in each directory a script or pytest puts first
        on ``sys.path`` for the writer (:func:`shadow_directories`)."""
        found = {dotted} if dotted in self.nodes else set()
        if dotted:
            for directory in shadow_directories(self.file_set, writer):
                local = ".".join([*directory, dotted])
                if local in self.nodes:
                    found.add(local)
        return found

    def exposed(self, node: str, seen: set[str] | None = None) -> set[str]:
        """Every module reachable as an attribute of ``node``'s module."""
        seen = set() if seen is None else seen
        if node in seen:
            return set()
        seen.add(node)
        found: set[str] = set()
        prefix = f"{node}."
        for other in self.nodes:
            if other.startswith(prefix) and "." not in other[len(prefix) :]:
                found.add(other)
        path = self.modules.get(node)
        file = self.files.get(path) if path is not None else None
        if file is not None:
            for entry in file.exports.values():
                if isinstance(entry, Mapping) and entry.get("outcome") == "import":
                    found |= self.binding_values(
                        entry.get("binding") or {}, path or "", set()
                    )
            for bindings in file.module_imports.values():
                for binding in bindings:
                    found |= self.binding_values(binding, path or "", set())
            for star in file.stars:
                for start in self.targets(star, path or ""):
                    found |= self.exposed(start, seen)
            # #706: a module reached wholly hands out its getters (its own,
            # and those its namespace imports by name), so what they return.
            for name in self.getters_of(path or ""):
                found |= self.returned((path or "", name))
            reachable = self.getter_names()
            for name in file.module_imports:
                if name in reachable:
                    for getter in self.getter_values(node, name):
                        found |= self.returned(getter)
        return found

    def exposes_patcher(self, node: str, name: str | None) -> bool:
        """R-699-10 item 2, R-699-12 item 3: whether module ``node`` binds
        ``patch`` by a module-scope from-import under ``name`` (``from
        unittest.mock import patch as pp``, read back by ``from node import
        pp`` at any scope), or under any name (``None``: what ``from node
        import *`` may hand over; underscore names and ``__all__`` are not
        narrowed, which only fails closed). A private patcher needs no
        following: it is a token of the file that binds it (R-699-12).

        One hop is enough. Every run file in a longer chain (``compat``
        re-exporting ``compat2``'s ``pp``, or star-importing it) records the
        same cause for its own hop, and O-2 promotion makes that file
        production whenever a production file imports it. Reading the
        re-export as a module attribute (``compat.pp``,
        ``import_module("compat").pp``) is not followed (R12)."""
        from . import py_scope as ps

        path = self.modules.get(node)
        file = self.files.get(path) if path is not None else None
        if file is None:
            return False
        return any(
            binding.get("form") == "from"
            and str(binding.get("name") or "").split(".")[-1] == ps._PATCH
            for bound, bindings in file.module_imports.items()
            if name is None or bound == name
            for binding in bindings
        )

    # -- taints -----------------------------------------------------------

    def walk_use(
        self,
        writer: str,
        base_ref: str,
        position: str,
        chain: Sequence[str],
        names: dict[str, set[str]],
        whole: set[str],
    ) -> None:
        """Taint what one module-object use may write or escape."""
        if position in RESULT_POSITIONS:
            self.walk_result(writer, base_ref, position, chain, names, whole)
            return
        self.walk_from(
            self.module_values(base_ref, writer), position, chain, names, whole
        )

    # -- getters (#706) ---------------------------------------------------

    def getters_of(self, path: str) -> Mapping[str, Any]:
        """The tracked getters of a run file: name -> ``[[base, *chain]]``."""
        found = (self.bindings.get(path) or {}).get("getters")
        return found if isinstance(found, Mapping) else {}

    def getter_names(self) -> frozenset[str]:
        """Every attribute name a tracked getter may be reached under: its
        own name and, to a fixpoint, every name a module-namespace ``from M
        import <one of them> [as X]`` binds. A name outside this set never
        needs a getter walk."""
        if self._getter_names is None:
            found: set[str] = set()
            for path in self.files:
                found.update(self.getters_of(path))
            changed = bool(found)
            while changed:
                changed = False
                for file in self.files.values():
                    for name, bindings in file.module_imports.items():
                        if name not in found and any(
                            binding.get("form") == "from"
                            and binding.get("name") in found
                            for binding in bindings
                        ):
                            found.add(name)
                            changed = True
            self._getter_names = frozenset(found)
        return self._getter_names

    def getter_values(
        self, node: str, name: str, seen: set[tuple[str, str]] | None = None
    ) -> set[tuple[str, str]]:
        """Every tracked getter ``(path, name)`` a ``node.name`` attribute may
        hold: the module's own getter of that name, and leniently every
        ``from M import name`` re-export (proven or not, like
        :meth:`attr_values`) and star source."""
        if name not in self.getter_names():
            return set()
        seen = set() if seen is None else seen
        if (node, name) in seen:
            return set()
        seen.add((node, name))
        found: set[tuple[str, str]] = set()
        path = self.modules.get(node)
        file = self.files.get(path) if path is not None else None
        if path is None or file is None:
            return found
        if name in self.getters_of(path):
            found.add((path, name))
        entries = list(file.module_imports.get(name, ()))
        entry = file.exports.get(name)
        if isinstance(entry, Mapping) and entry.get("outcome") == "import":
            entries.append(entry.get("binding") or {})
        for binding in entries:
            if binding.get("form") != "from":
                continue
            for start in self.targets(str(binding.get("module") or ""), path):
                found |= self.getter_values(start, str(binding.get("name") or ""), seen)
        for star in file.stars:
            for start in self.targets(star, path):
                found |= self.getter_values(start, name, seen)
        return found

    def returned(self, getter: tuple[str, str]) -> set[str]:
        """Every module a tracked getter may return (cached)."""
        cached = self._returned.get(getter)
        if cached is not None:
            return cached
        self._returned[getter] = set()  # a cycle adds nothing new
        path, name = getter
        found: set[str] = set()
        records = self.getters_of(path).get(name) or ()
        for record in records:
            current = self.module_values(str(record[0]), path)
            for part in record[1:]:
                following: set[str] = set()
                for node in current:
                    following |= self.attr_values(node, str(part), set())
                current = following
            found.update(current)
        self._returned[getter] = found
        return found

    def hand_on(self, current: AbstractSet[str], name: str, whole: set[str]) -> None:
        """``name`` read off a value that may be one of ``current`` anywhere
        but as a direct callee hands the getters it may hold to code no rule
        follows: whatever they return escapes."""
        if name not in self.getter_names():
            return
        for node in current:
            for getter in self.getter_values(node, name):
                whole.update(self.returned(getter))

    def walk_result(
        self,
        writer: str,
        base_ref: str,
        position: str,
        chain: Sequence[str],
        names: dict[str, set[str]],
        whole: set[str],
    ) -> None:
        """A result record (#706): resolve the callee leniently to a set of
        getters, then walk the uses from the modules they return, following
        each call step through the getters the called member may be."""
        if CALL_MARK not in chain:
            return
        split = list(chain).index(CALL_MARK)
        callee, rest = list(chain[:split]), list(chain[split + 1 :])
        kind = position.split("-", 1)[1]
        if not callee:
            return
        getters: set[tuple[str, str]] = set()
        if position.startswith("own-"):
            if callee[0] in self.getters_of(writer):
                getters.add((writer, callee[0]))
        elif callee[-1] in self.getter_names():
            current = self.module_values(base_ref, writer)
            for name in callee[:-1]:
                following: set[str] = set()
                for node in current:
                    following |= self.attr_values(node, name, set())
                current = following
            for node in current:
                getters |= self.getter_values(node, callee[-1])
        for getter in sorted(getters):
            current = set(self.returned(getter))
            segment: list[str] = []
            for part in rest:
                if part != CALL_MARK:
                    segment.append(part)
                    continue
                # A call step: the member called may be a getter of any module
                # the value may be; follow what those return.
                nodes = current
                for name in segment[:-1]:
                    self.hand_on(nodes, name, whole)
                    following = set()
                    for node in nodes:
                        following |= self.attr_values(node, name, set())
                    nodes = following
                current = set()
                if segment:
                    for node in nodes:
                        for inner in self.getter_values(node, segment[-1]):
                            current |= self.returned(inner)
                segment = []
            self.walk_from(current, kind, segment, names, whole)

    def walk_from(
        self,
        current: set[str],
        position: str,
        chain: Sequence[str],
        names: dict[str, set[str]],
        whole: set[str],
    ) -> None:
        """The steps of :meth:`walk_use` from a set of modules: what a use
        with this position and chain may write or escape."""
        current = set(current)
        if position == "write" and len(chain) > 1:
            # E6-6: a write through an attribute chain rooted at the module
            # (``svc.t.__code__ = ...``) changes what ``svc.t`` holds or runs.
            for node in current:
                names.setdefault(node, set()).add(chain[0])
        for index, name in enumerate(chain):
            if (
                name.startswith("__")
                and name.endswith("__")
                and name not in _SAFE_DUNDERS
            ):
                whole.update(current)
                return
            if index == len(chain) - 1 and position == "write":
                # A write of ``M.get`` replaces the function and hands it to
                # nobody (a name taint).
                for node in current:
                    names.setdefault(node, set()).add(name)
                return
            # #706: a getter read off the value anywhere but as a direct callee
            # (``x = A.get``, ``A.get.__call__()``, ``return getter.get``).
            self.hand_on(current, name, whole)
            following: set[str] = set()
            for node in current:
                following |= self.attr_values(node, name, set())
            current = following
        if position == "value":
            whole.update(current)


def _private_patch_tokens() -> frozenset[str]:
    from . import py_scope as ps

    return ps._PRIVATE_PATCH_TOKENS


def _split_import_ref(ref: str) -> tuple[str, str]:
    """``(module reference, last name)`` of an import reference
    (:func:`_scan_imports`: ``compat.pp``, ``.pp``, ``..pkg.compat.pp``)."""
    dots = len(ref) - len(ref.lstrip("."))
    rest = ref[dots:]
    if "." not in rest:
        return "." * dots, rest
    module, name = rest.rsplit(".", 1)
    return "." * dots + module, name


def _production(
    builder: _Builder,
    edges: Mapping[str, Sequence[str]],
    directory_symlinks: bool | None,
) -> frozenset[str]:
    """O-2 promotion: the fixpoint of production files over every edge a
    file may load another through (imports, uses, acquisitions, stars,
    strings), each resolved leniently."""
    files = builder.files
    if directory_symlinks is not False:
        return frozenset(files)
    production = {path for path in files if not is_test_path(path)}
    pending = sorted(production)
    while pending:
        path = pending.pop()
        for ref in edges.get(path, ()):
            absolute = builder.absolute(ref, path)
            if absolute is None:
                continue
            reached: set[str] = set()
            parts = absolute.split(".") if absolute else []
            for index in range(1, len(parts) + 1):
                prefix = ".".join(parts[:index])
                nodes = (
                    {prefix} & builder.nodes
                    if ref.startswith(".")
                    else builder.starts(prefix, path)
                )
                for node in nodes:
                    target = builder.modules.get(node)
                    if target is not None:
                        reached.add(target)
            for target in sorted(reached - production):
                production.add(target)
                pending.append(target)
    return frozenset(production)


def build_py_module_run(
    facts: Sequence[Mapping[str, Any]],
    directory_symlinks: bool | None = None,
) -> PyModuleRun:
    """Index the run's Python files and compute the taints and run-wide
    causes, scoped by the caller (O-2)."""
    builder = _Builder(facts)
    edges: dict[str, list[str]] = {}
    for path, bindings in builder.bindings.items():
        refs = [str(ref) for ref in bindings.get("imports", ())]
        refs += [str(ref) for ref in bindings.get("stars", ())]
        refs += [str(taint[0]) for taint in bindings.get("taints", ())]
        refs += [str(string) for string in bindings.get("strings", ())]
        for use in bindings.get("uses", ()):
            if str(use[1]).startswith("own-"):
                continue  # a call of the file's own getter loads nothing
            ref = str(use[0])
            for part in use[2:]:
                if part == CALL_MARK:
                    # #706: a result record loads its callee's module only.
                    break
                ref = _join(ref, str(part))
            refs.append(ref)
        edges[path] = refs
    production = _production(builder, edges, directory_symlinks)
    names: dict[bool, dict[str, set[str]]] = {True: {}, False: {}}
    whole: dict[bool, set[str]] = {True: set(), False: set()}
    causes: list[tuple[str, str]] = []
    for path in sorted(builder.files):
        bindings = builder.bindings.get(path) or {}
        scope = path in production
        if path in builder.unsupported:
            causes.append((CAUSE_UNPARSED_FILE, path))
        for cause in bindings.get("shutoff", ()):
            causes.append((str(cause), path))
        for use in bindings.get("uses", ()):
            builder.walk_use(
                path,
                str(use[0]),
                str(use[1]),
                [str(p) for p in use[2:]],
                names[scope],
                whole[scope],
            )
        for ref, name in bindings.get("taints", ()):
            # Every recorded taint reference is absolute (the analyzer makes a
            # relative ``import_module`` absolute or records a cause).
            for node in builder.targets(str(ref), path):
                if name == "*":
                    whole[scope].add(node)
                else:
                    names[scope].setdefault(node, set()).add(str(name))
        for string in bindings.get("strings", ()):
            parts = str(string).split(".")
            builder.walk_use(
                path, parts[0], "write", parts[1:], names[scope], whole[scope]
            )
        for star in bindings.get("stars", ()):
            for node in builder.targets(str(star), path):
                whole[scope].update(builder.exposed(node))
                if builder.exposes_patcher(node, None):
                    # R-699-10 item 2: ``from compat import *`` hands over
                    # a patcher under a name this file never spells as one
                    # (``pp(f"svc.{NAME}", f)``): an ``unresolvable-writer``
                    # of the importing file, scoped by O-2.
                    causes.append((CAUSE_UNRESOLVABLE_WRITER, path))
        for ref in bindings.get("imports", ()):
            # R-699-12 item 3: ``from compat import pp`` at any scope (module,
            # function, class body; relative too), where ``compat`` binds
            # ``patch`` as ``pp``. A name spelled ``patch`` is the file's own
            # W-3 rules, a private patcher its own token.
            module, name = _split_import_ref(str(ref))
            if name == "patch" or name in _private_patch_tokens():
                continue
            if any(
                builder.exposes_patcher(start, name)
                for start in builder.targets(module, path)
            ):
                causes.append((CAUSE_UNRESOLVABLE_WRITER, path))
    for scope in (True, False):
        pending = sorted(whole[scope])
        while pending:
            node = pending.pop()
            for other in sorted(builder.exposed(node) - whole[scope]):
                whole[scope].add(other)
                pending.append(other)

    def by_path(dotted_names: dict[str, set[str]]) -> dict[str, frozenset[str]]:
        result: dict[str, set[str]] = {}
        for node, written in dotted_names.items():
            target = builder.modules.get(node)
            if target is not None:
                result.setdefault(target, set()).update(written)
        return {key: frozenset(value) for key, value in result.items()}

    def whole_paths(dotted_names: set[str]) -> frozenset[str]:
        return frozenset(
            builder.modules[node] for node in dotted_names if node in builder.modules
        )

    shutoff: dict[bool, dict[str, str]] = {True: {}, False: {}}
    for name, path in causes:
        shutoff[path in production].setdefault(name, path)
    for in_production, found in shutoff.items():
        for name, path in sorted(found.items()):
            logger.info(
                "call resolution: Python Tier 2 is off for %s (%s in %s, %s)",
                "this run" if in_production else "callers in test files",
                name,
                path,
                "production" if in_production else "test-scoped",
            )
    return PyModuleRun(
        files=builder.files,
        modules=builder.modules,
        directories=builder.directories,
        nodes=builder.nodes,
        name_taints=by_path(names[True]),
        whole_taints=whole_paths(whole[True]),
        shutoff=dict(shutoff[True]),
        test_name_taints=by_path(names[False]),
        test_whole_taints=whole_paths(whole[False]),
        test_shutoff=dict(shutoff[False]),
        test_scope=frozenset(builder.files) - production,
    )


# ---------------------------------------------------------------------------
# Resolution (9.5, 9.6)


@dataclass(frozen=True)
class _Module:
    """A module value: its dotted name and file (``None`` for a namespace
    directory)."""

    dotted: str
    path: str | None


def _resolve_parts(
    run: PyModuleRun, base: list[str], parts: Sequence[str]
) -> _Module | str:
    """Resolve components one at a time from directory ``base`` (9.5)."""
    directory = list(base)
    found: _Module | None = None
    for index, component in enumerate(parts):
        if component in SKIPPED_DIRECTORIES:
            return "unknown-variant"
        stem = "/".join([*directory, component])
        init = f"{stem}/__init__.py"
        module = f"{stem}.py"
        dotted = ".".join([*directory, component])
        if init in run.files:
            found = _Module(dotted, init)
            directory.append(component)
        elif module in run.files:
            if index < len(parts) - 1:
                return "module-not-found"
            found = _Module(dotted, module)
        elif stem in run.directories:
            found = _Module(dotted, None)
            directory.append(component)
        else:
            return "module-not-found"
    return found if found is not None else "module-not-found"


def _pytest_basedir(files: AbstractSet[str], path: str) -> list[str]:
    """The directory pytest's ``prepend`` import mode puts first on
    ``sys.path`` for a module it imports: the first ancestor of ``path``
    (its own directory included) without ``__init__.py``."""
    current = path.split("/")[:-1]
    while current and "/".join(current) + "/__init__.py" in files:
        current = current[:-1]
    return current


def _pytest_imported(path: str) -> bool:
    """Whether pytest imports ``path`` itself while collecting (its default
    ``python_files`` and conftest names), inserting its basedir."""
    name = path.rsplit("/", 1)[-1]
    return name == TEST_CONFTEST or (
        name.endswith(".py")
        and (name.startswith(TEST_PREFIX) or name.endswith(TEST_SUFFIX))
    )


_BASEDIR_CACHE: dict[frozenset[str], tuple[tuple[str, ...], ...]] = {}


def pytest_basedirs(files: AbstractSet[str]) -> tuple[tuple[str, ...], ...]:
    """The basedir of every file pytest imports while collecting the run
    (test modules and every ``conftest.py``), below the root (#705 P6-4).

    In ``prepend`` mode pytest inserts each one's basedir at ``sys.path[0]``
    and never removes it, so a test module sees the basedirs of every
    conftest and test module imported before it: the president's
    ``h4_conftest_basedir`` (``tests/conftest.py`` beside ``tests/helpers.py``,
    the test in ``tests/unit/``) printed ``TESTS helpers.h`` for ``from
    helpers import h``, and its control without the conftest printed ``ROOT
    helpers.h``. Computed once per file set."""
    key = files if isinstance(files, frozenset) else frozenset(files)
    found = _BASEDIR_CACHE.get(key)
    if found is None:
        basedirs = {
            tuple(_pytest_basedir(key, path))
            for path in key
            if path.endswith(".py") and _pytest_imported(path)
        }
        found = tuple(sorted(basedir for basedir in basedirs if basedir))
        if len(_BASEDIR_CACHE) > 8:
            _BASEDIR_CACHE.clear()
        _BASEDIR_CACHE[key] = found
    return found


def shadow_directories(files: AbstractSet[str], importer: str) -> list[list[str]]:
    """The directories below the root that may come first on ``sys.path`` for
    ``importer``: its own (a script run directly), and for a test file
    (:func:`is_test_path`) every directory up to and including the first
    ancestor without ``__init__.py``, pytest's ``rootdir`` insertion in
    ``prepend`` mode (#705 E6-4), and the basedir of every test module and
    conftest pytest imports in the run (#705 P6-4, :func:`pytest_basedirs`).
    The root itself is never one."""
    directory = importer.split("/")[:-1]
    found: list[list[str]] = [directory] if directory else []
    if is_test_path(importer):
        current = directory
        while current and "/".join(current) + "/__init__.py" in files:
            current = current[:-1]
            if current:
                found.append(current)
        for basedir in pytest_basedirs(files):
            if list(basedir) not in found:
                found.append(list(basedir))
    return found


def resolve_module(run: PyModuleRun, ref: str, importer: str) -> _Module | str:
    """The module an import names from ``importer`` (9.5), or a reason."""
    if ref.startswith("."):
        dots = len(ref) - len(ref.lstrip("."))
        rest = [part for part in ref[dots:].split(".") if part]
        package = importer.split("/")[:-1]
        if dots - 1 >= len(package):
            # The root is the ``sys.path`` entry, not a package.
            return "outside-root"
        base = package[: len(package) - (dots - 1)]
        if not rest:
            path = "/".join(base) + "/__init__.py"
            return _Module(
                ".".join(base),
                path if path in run.files else None,
            )
        return _resolve_parts(run, base, rest)
    parts = [part for part in ref.split(".") if part]
    if not parts:
        return "module-not-found"
    for directory in shadow_directories(run.file_set, importer):
        stem = "/".join([*directory, parts[0]])
        if (
            f"{stem}.py" in run.files
            or f"{stem}/__init__.py" in run.files
            or stem in run.directories
        ):
            return "script-dir-shadow"
    if parts[0] in STDLIB_MODULES:
        return "external-module"
    return _resolve_parts(run, [], parts)


@dataclass(frozen=True)
class _Local:
    path: str
    local: Mapping[str, Any]


def _attribute(
    run: PyModuleRun,
    caller: str,
    value: _Module,
    name: str,
    hops: int,
    seen: tuple[tuple[str, str], ...],
) -> _Module | _Local | str:
    """Attribute ``name`` of module ``value`` (9.6): a module, a proof, or a
    reason."""
    key = (value.dotted, name)
    if key in seen:
        return "cycle"
    if hops > HOP_LIMIT:
        return "hop-limit"
    seen = (*seen, key)
    submodule: _Module | None = None
    probe: str | None = None
    directory = value.dotted.replace(".", "/") if value.dotted else ""
    if value.path is None or value.path.endswith("__init__.py"):
        found = _resolve_parts(run, directory.split("/") if directory else [], [name])
        if isinstance(found, _Module):
            submodule = found
        elif found != "module-not-found":
            # S-1: a submodule the resolver cannot read (a skipped-directory
            # name) may still exist.
            probe = found
    if value.path is None:
        if submodule is not None:
            return submodule
        return probe or "export-not-found"
    reason = run.taint_reason(caller, value.path, name)
    if reason is not None:
        return reason
    file = run.files.get(value.path)
    if file is None or not file.supported:
        return "export-not-found"
    entry = file.exports.get(name)
    if entry is not None and (submodule is not None or probe is not None):
        if submodule is not None and _own_submodule_import(file, entry, name):
            # ``from . import b`` in ``a/__init__.py`` binds its own submodule.
            return submodule
        return "attr-submodule-conflict"
    if entry is None:
        if file.package and "__getattr__" in file.exports:
            # E6-3: PEP 562 ``__getattr__`` answers before the submodule loads.
            return REASON_MODULE_GETATTR
        if submodule is not None:
            # A-3: a module that may bind names at run time may bind this one.
            return submodule if file.missing == "export-not-found" else file.missing
        return probe or file.missing
    kind = entry.get("outcome")
    if kind == "local":
        return _Local(value.path, entry)
    if kind == "import":
        # Fold 8: a re-export hop goes through the one binding resolver, with
        # every check a direct import gets (Codex r4661935648).
        return _resolve_binding(
            run, caller, entry.get("binding") or {}, value.path, hops + 1, seen
        )
    return str(entry.get("reason") or "export-not-found")


def _resolve_binding(
    run: PyModuleRun,
    caller: str,
    binding: Mapping[str, Any],
    importer: str,
    hops: int,
    seen: tuple[tuple[str, str], ...],
) -> _Module | _Local | str:
    """THE resolver of one import binding written in ``importer`` (#705 fold
    8): the value the name holds, a module, a proof or a reason. Every proof
    path uses it: a direct import in the caller (:func:`resolve_import`) and
    every re-export hop through an intermediary (:func:`_attribute`), up to
    the hop limit.

    - ``import a`` / ``import a.b`` (which binds ``a``): the module
      :func:`resolve_module` finds from ``importer`` (script-directory and
      pytest shadowing, standard-library names, skipped directories).
    - ``import a.b as m``: CPython 3.7+ ``IMPORT_FROM`` binds
      ``getattr(a, "b")`` (E6-3), so after the dotted path resolves, every
      component after the first is an attribute of its package, read by
      :func:`_attribute` with every check (``attr-submodule-conflict``,
      ``module-getattr``, own-submodule imports by full name, P6-1, and not
      under a star import, P6-2, and each module's taints, E6-1/E6-2); the
      result must be a module, else ``attr-submodule-conflict``.
    - ``from M import n`` (relative or absolute): attribute ``n`` of module
      ``M``, read the same way.

    Fold 7 and earlier resolved a re-exported ``import a.b as m`` as the path
    ``a.b``: with ``a/__init__.py`` doing ``from . import b`` and then ``from
    vendor import impl as b``, ``from facade import m; m.t()`` proved
    ``a/b.py:t`` while CPython ran ``vendor.impl.t``."""
    if binding.get("form") == "import":
        bound = str(binding.get("bound") or "")
        start = resolve_module(run, bound, importer)
        parts = [part for part in bound.split(".") if part]
        if not isinstance(start, _Module) or len(parts) < 2:
            return start
        value: _Module | _Local | str = resolve_module(run, parts[0], importer)
        for part in parts[1:]:
            if not isinstance(value, _Module):
                break
            value = _attribute(run, caller, value, part, hops, seen)
        if isinstance(value, str):
            return value
        if not isinstance(value, _Module):
            return "attr-submodule-conflict"
        return value
    target = resolve_module(run, str(binding.get("module") or ""), importer)
    if not isinstance(target, _Module):
        return target
    return _attribute(run, caller, target, str(binding.get("name") or ""), hops, seen)


def _own_submodule_import(file: PyFile, entry: Mapping[str, Any], name: str) -> bool:
    """Whether a package binds ``name`` only to its own submodule of that
    name (the analyzer's ``own_submodules``; #705 E6-3)."""
    del entry
    # P6-2: a star import may rebind any name (the analyzer leaves such a
    # file no own-submodule names; this holds for facts that predate it).
    return file.package and not file.stars and name in file.own_submodules


def own_binding_reason(run: PyModuleRun, caller: str, name: str) -> str | None:
    """Why a module-scope name of the caller's own module may not hold what
    its binding says (#705 E6-1): another file's write of it, or, in a
    package ``__init__.py``, a submodule of that name, which importing it sets
    as the package's global (A-4)."""
    reason = run.taint_reason(caller, caller, name)
    if reason is not None:
        return reason
    file = run.files.get(caller)
    if file is not None and file.package:
        base = caller.split("/")[:-1]
        found = _resolve_parts(run, base, [name])
        if isinstance(found, _Module) or found != "module-not-found":
            entry = file.exports.get(name)
            if not (
                isinstance(found, _Module)
                and isinstance(entry, Mapping)
                and _own_submodule_import(file, entry, name)
            ):
                return "attr-submodule-conflict"
    return None


def resolve_import(
    run: PyModuleRun,
    importer: str,
    binding: Mapping[str, Any],
    chain: Sequence[str],
) -> Mapping[str, Any]:
    """Resolve one import binding, followed by the member chain of the call
    (``u.helper()``, ``pkg.util.helper()``), to a proof in its target module.

    Returns ``{"outcome": "local", "path": <target>, "local": <the target's
    local outcome>}`` or a ``none`` outcome.
    """
    shutoff = run.caller_shutoff(importer)
    if shutoff is not None:
        return _none(shutoff)
    value = _resolve_binding(run, importer, binding, importer, 0, ())
    if isinstance(value, str):
        return _none(value)
    for name in chain:
        if not isinstance(value, _Module):
            return _none("export-not-found")
        value = _attribute(run, importer, value, name, 0, ())
        if isinstance(value, str):
            return _none(value)
    if isinstance(value, _Module):
        return _none("non-callable")
    return {"outcome": "local", "path": value.path, "local": value.local}


def tier1_reason(
    run: PyModuleRun, caller: str, proof: Sequence[Sequence[Any]]
) -> str | None:
    """Why a Tier 1 proof in ``caller`` fails closed in ``imports`` mode:
    another file's write of the module global the proof names (#697). Run-wide
    causes shut off Tier 2 only, as for TS/JS (PR 5); a write they may make
    is the same plan risk R10/R12 as in ``structural`` mode."""
    file = run.files.get(caller)
    if file is None:
        return None
    for declaration in proof:
        key = (str(declaration[0]), int(declaration[1]), int(declaration[2]))
        for name in sorted(file.exported.get(key, ())):
            reason = own_binding_reason(run, caller, name)
            if reason is not None:
                return reason
    return None
