"""Module objects returned by functions, Python ``imports`` mode (#706).

A *tracked getter* (a plain module-level ``def`` that returns import-rooted
chains, in a file that passes H1) no longer makes its return a whole-module
escape. Every use of a call that may invoke it is classified through the
same closed allow-list as an imported module object, followed through
member calls and function-local aliases. Plan
``backlog-wave3/plans/706.md`` slice 1 and executive ruling R-706-1.

Each tree runs on the test interpreter, and every test asserts what CPython
printed: an edge whose module function was replaced at run time must never
resolve, except through the named R10/R12 residuals (c02, c05, c06; R-706-1
item 4).
"""

from __future__ import annotations

import copy
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from chunker.boundary import dumps_boundary_ir, extract_boundary_ir
from chunker.call_resolution.facts import valid_py_module_bindings
from chunker.symbol_graph import (
    assemble_symbol_graph,
    collect_source_files,
    extract_symbol_facts_for_file,
    has_directory_symlink,
)
from tests.call_resolution_py_getter_cases import CASES, SHARED

MODE = "imports"
# R-706-1 item 4: accepted widenings of named residuals (a frame of another
# module, an unparsed writer, a computed loader); main gets their plain-import
# twins wrong too. Tracked on treesitter-chunker#699.
RESIDUALS = ("c02-", "c05-", "c06-")
# R-706-2 (S1, S3), named in plan R12 (Python, PR 6): a loader with a constant
# module name held in a binding (g05, the c06 family), a second instance of
# the getter's module loaded by spec (g09; twin t03), the caller's frame
# through a generator or a traceback (i03, j23; the c02 family), and a module
# from a function-local ``import`` held in a closure cell (t01, t02; with an
# unused getter in the tree, i01t, i02t). The twins are wrong on main too.
RESIDUAL_TREES = frozenset(
    f"review2:{name}"
    for name in (
        "g05-import-module-const-name",
        "g09-find-spec-loader",
        "t03-spec-loader-twin",
        "i03-gen-frame-cross-file",
        "j23-exception-traceback-frame",
        "t01-closure-local-import-twin",
        "t02-getclosurevars-local-import-twin",
        "i01t-closure-cell-main-twin",
        "i02t-getclosurevars-main-twin",
    )
)


def _write(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _cpython(root: Path) -> str:
    run = subprocess.run(
        [sys.executable, "-B", "-E", "-s", "main.py"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert run.returncode == 0, run.stderr[-2000:]
    return run.stdout.strip().splitlines()[-1]


def _resolutions(root: Path, probe: str, reference: str = "t") -> list[str]:
    facts = [
        extract_symbol_facts_for_file(path, root, "python", call_resolution=MODE)
        for path in collect_source_files(root, "python")
    ]
    graph = assemble_symbol_graph(
        facts,
        total_files=len(facts),
        call_resolution=MODE,
        language_filter="python",
        directory_symlinks=has_directory_symlink(root),
    )
    return [
        edge["resolution"]
        for edge in graph["relationships"]
        if edge["type"] == "calls"
        and edge["file"] == probe
        and edge["reference"] == reference
    ]


def _replaced(printed: str) -> bool:
    return printed.lower().startswith("other")


@pytest.mark.parametrize("case", sorted(CASES))
def test_review_trees(tmp_path: Path, case: str) -> None:
    """The plan battery (118 trees), the plan reviews' attack trees,
    Sol's slice-1 repros and the R-706-2 trees: CPython prints what was
    recorded, the probe edge resolves exactly as recorded, and no replaced
    function's edge resolves outside the named residuals. The battery
    controls (a01-a24 but a12 and a20) resolve: a rule that always escapes
    fails here."""
    probe, printed, expected, files = CASES[case]
    root = _write(
        tmp_path,
        {
            path: SHARED[body] if isinstance(body, int) else body
            for path, body in files.items()
        },
    )
    assert _cpython(root) == printed, case
    (resolution,) = _resolutions(root, probe)
    assert resolution == expected, case
    name = case.split(":", 1)[1]
    if _replaced(printed) and not name.startswith(RESIDUALS):
        assert case in RESIDUAL_TREES or resolution != "resolved", case


# Battery controls that stay ambiguous although CPython runs ``svc.t``: the
# slice-2 alias (a20, treesitter-chunker#725), and a closure read of a result
# alias, an escape since R-706-2 (B1; the accepted precision loss).
AMBIGUOUS_CONTROLS = ("battery:a12-closure-read", "battery:a20-module-alias-read")


def test_the_battery_controls_recover() -> None:
    """Every battery control but :data:`AMBIGUOUS_CONTROLS` resolves, and
    each printed ``SVC.t``."""
    controls = {
        name: value for name, value in CASES.items() if name.startswith("battery:a")
    }
    assert len(controls) == 25
    for name, (_probe, printed, expected, _files) in controls.items():
        assert printed == "SVC.t", name
        assert expected == ("ambiguous" if name in AMBIGUOUS_CONTROLS else "resolved")


# Sol's two slice-1 wrong edges and the 13 programs of the Opus review's B1,
# by name: each must stay ambiguous while CPython runs the replacement.
NAMED_BLOCKERS = (
    "sol:returned-getter",
    "sol:dunder-alias",
    *(
        f"review:{name}"
        for name in (
            "z01-caller-globals-hands-imported-getter",
            "z02-caller-helper-globals-getter",
            "z03-caller-locals-local-import-getter",
            "z06-caller-globals-module-binding",
            "z07-caller-globals-facade-module",
            "x02-own-f_globals",
            "y03-caller-f_globals",
            "y05-slice2-alias-then-f_globals",
            "x03-own-__globals__",
            "y01-own-getmodule",
            "y02-own-dunder-import-name",
            "x06-string-annotation-own",
            "x07-string-annotation-caller",
        )
    ),
    # R-706-2 B1: a result alias captured by a closure, written through the
    # cell from another module (``__closure__``, ``getclosurevars``, a
    # computed cell name), and the 16 programs of the review's extended
    # generator.
    *(
        f"review2:{name}"
        for name in (
            "i01-closure-cell-cross-file",
            "i02-getclosurevars",
            "i08-closure-no-dunder-cross-file",
            "v01-closure-getter-module-attr",
            "v02-closure-getter-stored",
            "v03-closure-callback-registered",
            "v04-closure-in-file-own-dunder",
        )
    ),
    *sorted(name for name in CASES if name.startswith("review2:gen-")),
)


@pytest.mark.parametrize("case", NAMED_BLOCKERS)
def test_named_blockers_stay_ambiguous(case: str) -> None:
    _probe, printed, expected, _files = CASES[case]
    assert _replaced(printed) and expected == "ambiguous", case


_SVC = 'def t():\n    return "SVC.t"\n\n\ndef u():\n    return t()\n\n\ndef w():\n    return 1\n'
_OTHER = 'def t():\n    return "OTHER.t"\n\n\ndef w():\n    return 2\n'
_MAIN = "import use\nimport svc\n\nuse.go()\nprint(svc.u())\n"


def test_a_write_through_a_result_taints_that_name_only(tmp_path: Path) -> None:
    """``get().t = f`` taints ``svc.t`` (``reassigned``) and leaves another
    name of ``svc`` resolved."""
    root = _write(
        tmp_path,
        {
            "svc.py": _SVC + "\n\ndef v():\n    return w()\n",
            "other.py": _OTHER,
            "get.py": "import svc\n\n\ndef get():\n    return svc\n",
            "use.py": "from get import get\nimport other\n\n\ndef go():\n"
            "    get().t = other.t\n",
            "main.py": _MAIN,
        },
    )
    assert _cpython(root) == "OTHER.t"
    assert _resolutions(root, "svc.py", "t") == ["ambiguous"]
    assert _resolutions(root, "svc.py", "w") == ["resolved"]


def test_a_write_through_a_result_attribute_taints_the_closure(
    tmp_path: Path,
) -> None:
    """``get().dsl.t = f`` writes ``dsl.t`` and the first hop ``svc.dsl``
    (E6-6), exactly as ``svc.dsl.t = f`` does."""
    root = _write(
        tmp_path,
        {
            "dsl.py": _SVC,
            "svc.py": "import dsl\n\n\ndef t():\n    return 1\n\n\ndef u():\n"
            "    return t()\n\n\ndef v():\n    return dsl.u()\n",
            "other.py": _OTHER,
            "get.py": "import svc\n\n\ndef get():\n    return svc\n",
            "use.py": "from get import get\nimport other\n\n\ndef go():\n"
            "    get().dsl.t = other.t\n",
            "main.py": "import use\nimport dsl\n\nuse.go()\nprint(dsl.u())\n",
        },
    )
    assert _cpython(root) == "OTHER.t"
    assert _resolutions(root, "dsl.py", "t") == ["ambiguous"]
    assert _resolutions(root, "svc.py", "t") == ["resolved"]


_O2_BASE = {
    "svc.py": _SVC,
    # A second ``u``, so name mode leaves the callers' ``u()`` ambiguous.
    "other.py": _OTHER + "\n\ndef u():\n    return 0\n",
    "get.py": "import svc\n\n\ndef get():\n    return svc\n",
    "prodcaller.py": "from svc import u\n\n\ndef p():\n    return u()\n",
    "tests/__init__.py": "",
    "tests/test_use.py": "from svc import u\n\n\ndef test_p():\n    return u()\n",
}


@pytest.mark.parametrize(
    ("extra", "production", "test"),
    [
        # A getter result written in a test file taints for test callers only.
        (
            {
                "tests/test_w.py": "from get import get\nimport other\n\n\n"
                "def test_w():\n    get().u = other.t\n"
            },
            "resolved",
            "ambiguous",
        ),
        # The twin: the same write spelled directly.
        (
            {
                "tests/test_w.py": "import svc\nimport other\n\n\n"
                "def test_w():\n    svc.u = other.t\n"
            },
            "resolved",
            "ambiguous",
        ),
        # A production file reaching the test writer promotes it.
        (
            {
                "tests/test_w.py": "from get import get\nimport other\n\n\n"
                "def test_w():\n    get().u = other.t\n",
                "prod2.py": "import tests.test_w\n",
            },
            "ambiguous",
            "ambiguous",
        ),
        # A production caller reaching a test-file getter through an
        # intermediary: the getter file is promoted, so is its write.
        (
            {
                "tests/tget.py": "import svc\nimport other\n\n\ndef tget():\n"
                "    return svc\n\n\ndef poke():\n    tget().u = other.t\n",
                "mid.py": "from tests.tget import poke\n",
            },
            "ambiguous",
            "ambiguous",
        ),
        # No writer.
        ({}, "resolved", "resolved"),
    ],
)
def test_result_records_follow_o2(
    tmp_path: Path, extra: dict[str, str], production: str, test: str
) -> None:
    """Owner decision O-2: a result record taints in the scope of the file
    that holds the use, with promotion through import edges."""
    root = _write(tmp_path, {**_O2_BASE, **extra})
    assert _resolutions(root, "prodcaller.py", "u") == [production]
    assert _resolutions(root, "tests/test_use.py", "u") == [test]


def _bindings(root: Path, name: str) -> dict[str, Any]:
    (item,) = [
        extract_symbol_facts_for_file(path, root, "python", call_resolution=MODE)
        for path in collect_source_files(root, "python")
        if path.name == name
    ]
    bindings = item["scope_facts"]["module_bindings"]
    assert valid_py_module_bindings(bindings)
    return dict(bindings)


def test_facts_record_getters_and_result_records(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            "get.py": "import svc\nimport other\n\n\ndef get():\n    return svc\n\n\n"
            "def pair():\n    return svc, other.sub\n",
            "use.py": "from get import get\n\n\ndef go():\n    m = get()\n"
            "    m.fetch().t = 1\n",
        },
    )
    get = _bindings(root, "get.py")
    assert get["getters"] == {
        "get": [["svc"]],
        "pair": [["other", "sub"], ["svc"]],
    }
    assert ["svc", "ref"] in get["uses"]
    assert ["svc", "value"] not in get["uses"]
    use = _bindings(root, "use.py")
    assert ["get", "result-write", "get", "()", "fetch", "()", "t"] in use["uses"]
    assert use["getters"] == {}


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda b: b.update(getters=[]),
        lambda b: b.update(getters={"g": []}),
        lambda b: b.update(getters={"g": [[""]]}),
        lambda b: b.update(getters={"not a name": [["svc"]]}),
        lambda b: b.pop("getters"),
        lambda b: b["uses"].append(["get", "result-value", "get"]),
        lambda b: b["uses"].append(["get", "result-value", "()", "t"]),
        lambda b: b["uses"].append(["", "result-value", "get", "()"]),
        lambda b: b["uses"].append(["get", "own-value", "get", "()"]),
        lambda b: b["uses"].append(["", "own-value", "a", "b", "()"]),
        lambda b: b["uses"].append(["get", "result-call", "get", "()", "x y"]),
        lambda b: b["uses"].append(["g", "result-value", "g", "()", "()", "()", "()"]),
        lambda b: b["uses"].append(["get", "result-escape", "get", "()"]),
    ],
)
def test_malformed_getter_facts_are_rejected(tmp_path: Path, corrupt: Any) -> None:
    """A tampered ``getters`` table or result record fails validation, so a
    cached record holding it is a safe miss."""
    root = _write(
        tmp_path,
        {
            "use.py": "from get import get\n\n\ndef go():\n    return get().t\n",
            "get.py": "import svc\n\n\ndef get():\n    return svc\n",
        },
    )
    bindings = copy.deepcopy(_bindings(root, "use.py"))
    corrupt(bindings)
    assert not valid_py_module_bindings(bindings)


def test_structural_facts_carry_no_getter_tables(tmp_path: Path) -> None:
    root = _write(tmp_path, {"get.py": "import svc\n\n\ndef get():\n    return svc\n"})
    (item,) = [
        extract_symbol_facts_for_file(
            path, root, "python", call_resolution="structural"
        )
        for path in collect_source_files(root, "python")
    ]
    assert item["scope_facts"]["module_bindings"] == {}


@pytest.mark.parametrize(
    "body",
    [
        "    p = imported()\n    for _ in range(9):\n        p = p.parent\n"
        "    p.t = 1\n",
        "    x = imported()\n    while x:\n        x = x.hop()\n    x.t = 1\n",
        "    a = imported()\n    b = a.k\n    a = b.k\n    b = a.fetch()\n"
        "    a = b.fetch()\n    a.t = 1\n",
    ],
)
def test_self_rebinding_aliases_terminate_and_fail_closed(
    tmp_path: Path, body: str
) -> None:
    """``p = p.parent`` and ``x = x.hop()`` in a loop: the alias fixpoint
    stops at the chain and call caps, and the value escapes."""
    root = _write(
        tmp_path,
        {"use.py": "from lib import imported\n\n\ndef go():\n" + body},
    )
    uses = _bindings(root, "use.py")["uses"]
    assert any(use[1] == "result-value" for use in uses), uses


def _getter_tree(use: str) -> dict[str, str]:
    return {
        "svc.py": _SVC,
        "other.py": _OTHER,
        "get.py": "import svc\n\n\ndef get():\n    return svc\n",
        "use.py": use,
        "main.py": _MAIN,
    }


_SAFE_USE = "from get import get\n\n\ndef go():\n    m = get()\n    return m.w()\n"
_WRITE_USE = "from get import get\nimport other\n\n\ndef go():\n    m = get()\n    m.t = other.t\n"
_REF_USE = "from get import get\n\nG = get\n\n\ndef go():\n    return 1\n"


def test_incremental_runs_equal_cold_runs(tmp_path: Path) -> None:
    """A caller edited from a safe use to a write and back, and a getter
    reference added and removed, on one cache directory across
    ``structural`` and ``imports``: every warm run equals a cold run."""
    root = tmp_path / "tree"
    cache_dir = tmp_path / "cache"
    for use in (_SAFE_USE, _WRITE_USE, _SAFE_USE, _REF_USE, _SAFE_USE):
        _write(root, _getter_tree(use))
        for mode in ("structural", MODE):
            cold = extract_boundary_ir(root, call_resolution=mode)
            warm = extract_boundary_ir(
                root, incremental=True, cache_dir=cache_dir, call_resolution=mode
            )
            assert dumps_boundary_ir(warm) == dumps_boundary_ir(cold), (use, mode)
    assert _resolutions(_write(tmp_path / "w", _getter_tree(_WRITE_USE)), "svc.py") == [
        "ambiguous"
    ]
    assert _resolutions(_write(tmp_path / "s", _getter_tree(_SAFE_USE)), "svc.py") == [
        "resolved"
    ]
    assert _resolutions(_write(tmp_path / "r", _getter_tree(_REF_USE)), "svc.py") == [
        "ambiguous"
    ]


# --------------------------------------------------------------------------
# Generative runtime oracle (R-706-1 item 2). Each program reaches a getter or
# the module it lives in (by import forms, through a facade, as a member of a
# returned module, or through the namespace: ``globals()``, ``locals()``,
# ``vars()``, ``f_globals``, ``__globals__``, ``getmodule``,
# ``__import__(__name__)``, ``sys.modules[__name__]``, a string annotation
# under ``get_type_hints``, a one-argument ``exec``), in the caller or in the
# getter's own file, composes steps around the result (aliases, member calls,
# subscripts, unpacking, rebinding, closures, escapes) and ends in a use (a
# write, ``setattr``, ``__dict__``, a helper that writes, or a harmless read).
# R-706-2 (S4) adds the shapes of the Opus 5.5 review's extended generator:
# reaches through ``import_module``, ``partial``, ``attrgetter``, ``getattr``,
# ``__call__``, a star import, a staticmethod, ``lru_cache``, a getter rebound
# after its definition or repointed by a promoted test helper, a container;
# steps through a class attribute, ``SimpleNamespace``, a dataclass field,
# ``partial``/``map``, ``yield``, ``await`` and starred targets; and writes
# through ``partial(setattr)``, ``operator.setitem(vars())``, a comprehension,
# ``__setattr__``, and another module's write through a closure cell
# (``__closure__``, ``getclosurevars``).
# CPython runs every program; the probe edge ``svc.py`` ``u -> t`` must not
# resolve when ``t`` was replaced. Fixed seeds and a bounded count keep it
# deterministic; set ``CHUNKER_GETTER_ORACLE_COUNT`` for a larger run.

_HUB = """import svc
import other
{imports}

def fetch():
    return svc


def pair():
    return svc, other


def get_hub():
    import hub as me
    return me

{own}
"""
_GET = (
    "import hub\n\n\ndef get():\n    return hub.svc\n\n\ndef get_hub():\n"
    "    return hub\n\n\ndef decoy():\n    return hub.other\n"
)
_FACADE = "from get import get, get_hub\n"
_MAIN_CLOSURE = (
    "import use\nimport svc\nimport other\n{imp}\n\nr = use.go()\n"
    "if callable(r):\n    {poke}\nprint(svc.u())\n"
)
# A test helper (promoted: production imports it) repoints ``decoy``.
_TEST_PATCH = "import get as G\nimport hub\n\nG.decoy = hub.fetch\n"
_HELPERS = (
    "def ident(v):\n    return v\n\n\ndef poke_m(m):\n    m.t = other.t\n\n\n"
    "def gen1(v):\n    yield v\n\n\nasync def aident(v):\n    return v\n"
)


class _Program:
    def __init__(self, rng: random.Random, own: bool, extended: float = 0.0) -> None:
        self.rng = rng
        self.own = own
        # The share of reaches, steps and uses drawn from the R-706-2 shapes.
        self.extended = extended
        self.lines: list[str] = []
        self.imports: set[str] = set()
        self.module_lines: list[str] = []
        self.extra_files: dict[str, str] = {}
        self.get_py = _GET
        self.main = _MAIN
        self.closure_write = False
        self.decoy = False
        self.count = 0

    def ext(self) -> bool:
        """Whether to draw from the extended shapes (no draw when off, so
        the plain oracle's seeds keep their programs)."""
        return bool(self.extended) and self.rng.random() < self.extended

    def fresh(self, stem: str = "x") -> str:
        self.count += 1
        return f"{stem}{self.count}"

    def emit(self, line: str) -> None:
        self.lines.append("    " + line)

    def reach(self) -> tuple[str, str]:
        """An expression and its kind (``svc``, ``hub`` or ``pair``)."""
        fn = "poke" if self.own else "go"
        if self.own:
            options = [
                ("fetch()", "svc"),
                ("pair()", "pair"),
                ("get_hub()", "hub"),
                ('globals()["fetch"]()', "svc"),
                ('sys._getframe(0).f_globals["fetch"]()', "svc"),
                (f'{fn}.__globals__["fetch"]()', "svc"),
                (f"inspect.getmodule({fn}).fetch()", "svc"),
                ("__import__(__name__).fetch()", "svc"),
                ("sys.modules[__name__].fetch()", "svc"),
                ('typing.get_type_hints(_ann)["x"]()', "svc"),
            ]
            getter = "fetch"
        else:
            options = [
                ("get()", "svc"),
                ("G.get()", "svc"),
                ("F.get()", "svc"),
                ("H.fetch()", "svc"),
                ("get_hub()", "hub"),
                ("G.get_hub()", "hub"),
                ("H.pair()", "pair"),
                ('globals()["get"]()', "svc"),
                ('globals()["H"].fetch()', "svc"),
                ('locals()["lg"]()', "svc"),
                ('vars()["lg"]()', "svc"),
                ('sys._getframe(0).f_globals["get"]()', "svc"),
                (f'{fn}.__globals__["get"]()', "svc"),
                (f"inspect.getmodule({fn}).get()", "svc"),
                ("__import__(__name__).get()", "svc"),
                ("sys.modules[__name__].get()", "svc"),
                ('typing.get_type_hints(_ann)["x"]()', "svc"),
            ]
            extended = [
                ("importlib.import_module('get').get()", "svc"),
                ("functools.partial(get)()", "svc"),
                ("functools.partial(G.get)()", "svc"),
                ("operator.attrgetter('get')(G)()", "svc"),
                ("getattr(G, 'get')()", "svc"),
                ("get.__call__()", "svc"),
                ("G.get.__call__()", "svc"),
                ("[get][0]()", "svc"),
                ("next(iter((G.get,)))()", "svc"),
                ("star", "svc"),
                ("Kls.g()", "svc"),
                ("cached()", "svc"),
                ("rebound", "svc"),
                ("patched", "svc"),
                ("G.decoy()", "svc"),
            ]
            if self.ext():
                options = extended
            getter = "get"
        expr, kind = self.rng.choice(options)
        # ``decoy`` returns ``hub.other`` (unless a test helper repoints it).
        self.decoy = expr == "G.decoy()"
        if expr == "star":
            self.imports.add("from hub import *")
            expr = "fetch()"
        elif expr == "Kls.g()":
            self.module_lines.append("class Kls:\n    g = staticmethod(get)\n")
        elif expr == "cached()":
            self.imports.add("import functools")
            self.module_lines.append("cached = functools.lru_cache(get)\n")
        elif expr == "rebound":
            # The getter's file rebinds it after its definition.
            self.get_py = _GET + "\n\nget = decoy\nget = lambda: hub.svc\n"
            expr = "G.get()"
        elif expr == "patched":
            self.extra_files["tests/__init__.py"] = ""
            self.extra_files["tests/helper_patch.py"] = _TEST_PATCH
            self.imports.add("import tests.helper_patch")
            expr = "G.decoy()"
        for module in ("importlib", "functools", "operator"):
            if f"{module}." in expr:
                self.imports.add(f"import {module}")
        if "sys." in expr:
            self.imports.add("import sys")
        if "inspect." in expr:
            self.imports.add("import inspect")
        if "typing." in expr:
            self.imports.add("import typing")
            self.module_lines.append(f'def _ann(x: "{getter}"):\n    pass\n')
        if '"lg"' in expr:
            self.emit("from get import get as lg")
        return expr, kind

    def step(self, expr: str, kind: str) -> tuple[str, str]:
        rng = self.rng
        options = ["alias", "alias", "paren", "loop", "closure", "escape"]
        if self.ext():
            options = ["classattr", "nsattr", "dataclass", "partial", "map"]
            options += ["yield", "await", "star", "starlist"]
        if kind == "hub":
            options += ["svc", "fetch", "fetch", "pair"]
        if kind == "pair":
            options += ["first", "first", "unpack", "starunpack"]
        op = rng.choice(options)
        if op == "classattr":
            cls = self.fresh("C")
            self.emit(f"class {cls}:")
            self.emit(f"    m = {expr}")
            return f"{cls}.m", kind
        if op == "nsattr":
            self.imports.add("import types")
            name = self.fresh("o")
            self.emit(f"{name} = types.SimpleNamespace()")
            self.emit(f"{name}.m = {expr}")
            return f"{name}.m", kind
        if op == "dataclass":
            self.imports.add("import dataclasses")
            if not any("class DC" in line for line in self.module_lines):
                self.module_lines.append(
                    "@dataclasses.dataclass\nclass DC:\n    m: object = None\n"
                )
            return f"DC(m={expr}).m", kind
        if op == "partial":
            self.imports.add("import functools")
            return f"functools.partial(ident, {expr})()", kind
        if op == "map":
            return f"list(map(ident, [{expr}]))[0]", kind
        if op == "yield":
            return f"next(gen1({expr}))", kind
        if op == "await":
            self.imports.add("import asyncio")
            return f"asyncio.run(aident({expr}))", kind
        if op == "star":
            name = self.fresh("s")
            self.emit(f"{name}, *_ = {expr}, 0")
            return name, kind
        if op == "starlist":
            return f"[*[{expr}]][0]", kind
        if op == "starunpack":
            first = self.fresh("a")
            self.emit(f"{first}, *_ = {expr}")
            return first, "svc"
        if op == "alias":
            name = self.fresh()
            self.emit(f"{name} = {expr}")
            return name, kind
        if op == "paren":
            return f"({expr})", kind
        if op == "loop":
            name = self.fresh()
            self.emit(f"{name} = {expr}")
            self.emit("for _ in range(2):")
            self.emit(f"    {name} = {name}")
            return name, kind
        if op == "closure":
            name, inner = self.fresh(), self.fresh("inner")
            self.emit(f"{name} = {expr}")
            self.emit(f"def {inner}():")
            self.emit(f"    return {name}")
            return f"{inner}()", kind
        if op == "escape":
            form = rng.choice(
                [
                    "ident({e})",
                    "[{e}][0]",
                    "({e} if True else None)",
                    "next(iter(({e},)))",
                    "dict(m={e})['m']",
                ]
            )
            if rng.random() < 0.5:
                name = self.fresh("w")
                self.emit(f"if ({name} := {expr}) is None:")
                self.emit("    return")
                return form.format(e=name), kind
            return form.format(e=expr), kind
        if op == "svc":
            return f"{expr}.svc", "svc"
        if op == "fetch":
            return f"{expr}.fetch()", "svc"
        if op == "pair":
            return f"{expr}.pair()", "pair"
        if op == "first":
            return f"{expr}[0]", "svc"
        first, second = self.fresh("a"), self.fresh("b")
        self.emit(f"{first}, {second} = {expr}")
        return first, "svc"

    def finish(self, expr: str, kind: str) -> None:
        if kind == "hub":
            expr = f"{expr}.svc"
        elif kind == "pair":
            expr = f"{expr}[0]"
        uses = [
            "{e}.t = other.t",
            "{e}.t = other.t",
            'setattr({e}, "t", other.t)',
            '{e}.__dict__["t"] = other.t',
            "poke_m({e})",
            "return {e}.u()",
            "return {e}.w()",
            "{e}.zz = 1",
            "{e}",
        ]
        extended = [
            "functools.partial(setattr, {e}, 't')(other.t)",
            "operator.setitem(vars({e}), 't', other.t)",
            "[setattr(m, 't', other.t) for m in [{e}]]",
            "{e}.__setattr__('t', other.t)",
            "hasattr({e}, 't')",
        ]
        if not self.own:
            extended += ["closure-cell", "closure-cell-gcv"] * 2
        use = self.rng.choice(extended if self.ext() else uses)
        if self.decoy and use == "return {e}.u()":
            use = "return {e}.w()"  # ``other`` has no ``u``
        for module in ("functools", "operator"):
            if f"{module}." in use:
                self.imports.add(f"import {module}")
        if use.startswith("closure-cell"):
            # The caller returns a closure over the value; ``main.py`` writes
            # through its cell.
            name, inner = self.fresh("cell"), self.fresh("inner")
            self.emit(f"{name} = {expr}")
            self.emit(f"def {inner}():")
            self.emit(f"    {name}.w()")
            self.emit(f"return {inner}")
            if use == "closure-cell":
                poke, imp = "r.__closure__[0].cell_contents.t = other.t", ""
            else:
                poke = f"inspect.getclosurevars(r).nonlocals['{name}'].t = other.t"
                imp = "import inspect"
            self.main = _MAIN_CLOSURE.format(imp=imp, poke=poke)
            self.closure_write = True
            return
        self.emit(use.format(e=expr))

    def build(self) -> dict[str, str]:
        if self.rng.random() < 0.06:
            # A one-argument ``exec`` reads the file's namespace itself.
            getter = "fetch()" if self.own else "get()"
            self.emit(f'exec("{getter}.t = other.t")')
        else:
            expr, kind = self.reach()
            for _ in range(self.rng.randint(0, 3)):
                expr, kind = self.step(expr, kind)
            self.finish(expr, kind)
        helpers = _HELPERS
        body = "\n".join(self.lines)
        module = "\n".join(self.module_lines)
        if self.own:
            own = f"{helpers}\n{module}\n\ndef poke():\n{body}\n"
            hub = _HUB.format(imports="\n".join(sorted(self.imports)), own=own)
            use = "import hub as H\n\n\ndef go():\n    H.poke()\n"
        else:
            hub = _HUB.format(imports="", own="")
            head = [
                "from get import get, get_hub",
                "import get as G",
                "import facade as F",
                "import hub as H",
                "import other",
                *sorted(self.imports),
            ]
            use = "\n".join(head) + f"\n\n\n{helpers}\n{module}\n\ndef go():\n{body}\n"
        return {
            "svc.py": _SVC,
            "other.py": _OTHER,
            "hub.py": hub,
            "get.py": self.get_py,
            "facade.py": _FACADE,
            "use.py": use,
            "main.py": self.main,
            **self.extra_files,
        }


_ORACLE_COUNT = int(os.environ.get("CHUNKER_GETTER_ORACLE_COUNT", "48"))


def _run_oracle(tmp_path: Path, seed: int, extended: float) -> tuple[int, int]:
    """Run ``_ORACLE_COUNT`` programs: no replaced function's edge resolves.
    ``(harmless programs that resolve, replaced closure-cell writes)``."""
    rng = random.Random(seed)
    resolved_correct = closure_writes = 0
    for index in range(_ORACLE_COUNT):
        generator = _Program(rng, own=rng.random() < 0.35, extended=extended)
        program = generator.build()
        root = _write(tmp_path / f"p{index}", program)
        printed = _cpython(root)
        (resolution,) = _resolutions(root, "svc.py")
        if _replaced(printed):
            assert resolution != "resolved", (seed, index, program["use.py"])
            closure_writes += generator.closure_write
        elif resolution == "resolved":
            resolved_correct += 1
    return resolved_correct, closure_writes


@pytest.mark.parametrize("seed", [3, 17, 2026])
def test_generated_programs_never_resolve_a_replaced_function(
    tmp_path: Path, seed: int
) -> None:
    resolved_correct, _closure_writes = _run_oracle(tmp_path, seed, 0.0)
    # The oracle is not vacuous: some harmless programs keep their proof.
    assert resolved_correct > 0, seed


@pytest.mark.parametrize("seed", [5, 29])
def test_generated_extended_programs_never_resolve_a_replaced_function(
    tmp_path: Path, seed: int
) -> None:
    """The R-706-2 shapes (S4), drawn for 60% of reaches, steps and uses."""
    _resolved, closure_writes = _run_oracle(tmp_path, seed, 0.6)
    # Another module writes through a closure cell (R-706-2 B1).
    assert closure_writes > 0, seed


# Trees that need exactly one G1/H1/return/exposure/alias rule: each is
# caught by nothing else, so a mutation of that rule resolves it wrongly.
# CPython prints ``OTHER.t`` in each; the probe edge stays ambiguous.
_RULE_GET = "import svc\n\n\ndef get():\n    return svc\n"
RULE_TREES: dict[str, dict[str, str]] = {
    # A decorator that keeps the function where no rule sees it (G1).
    "decorated": {
        "get.py": "import svc\n\nREG = []\n\n\ndef deco(f):\n    REG.append(f)\n"
        "    return lambda: None\n\n\n@deco\ndef get():\n    return svc\n",
        "use.py": "import get as G\nimport other\n\n\ndef go():\n"
        "    G.REG[0]().t = other.t\n",
    },
    # A coroutine's value travels on ``StopIteration`` (G1: async).
    "async": {
        "get.py": "import svc\n\n\nasync def get():\n    return svc\n",
        "use.py": "from get import get\nimport other\n\n\ndef go():\n    c = get()\n"
        "    try:\n        c.send(None)\n    except StopIteration as stop:\n"
        "        stop.value.t = other.t\n",
    },
    # So does a generator's (G1: own ``yield``).
    "generator": {
        "get.py": "import svc\n\n\ndef get():\n    if False:\n        yield\n"
        "    return svc\n",
        "use.py": "from get import get\nimport other\n\n\ndef go():\n    g = get()\n"
        "    try:\n        g.send(None)\n    except StopIteration as stop:\n"
        "        stop.value.t = other.t\n",
    },
    # A list is not a tracked return: ``pop()`` hands the module out.
    "list-return": {
        "get.py": "import svc\n\n\ndef get():\n    return [svc]\n",
        "use.py": "from get import get\nimport other\n\n\ndef go():\n"
        "    get().pop().t = other.t\n",
    },
    # A getter with a lazy import, reached through its module by a computed
    # name: only the exposure of what its getters return covers it.
    "exposed-lazy-getter": {
        "get.py": "def get():\n    import svc\n    return svc\n",
        "use.py": "import get as G\nimport other\n\nNAME = 'get'\n\n\ndef go():\n"
        "    getattr(G, NAME)().t = other.t\n",
    },
    # A starred target is no alias: ``rest`` holds the module.
    "starred-unpack": {
        "get.py": "import svc\nimport other\n\n\ndef pair():\n    return svc, other\n",
        "use.py": "from get import pair\nimport other\n\n\ndef go():\n"
        "    *rest, last = pair()\n    rest[0].t = other.t\n",
    },
    # H1 by name: a frame read by the constant key ``"get"`` is no #724
    # reader (no import is named ``get``), but it reaches the getter.
    "h1-frame-key": {
        "get.py": "import sys\nimport svc\nimport other\n\n\ndef get():\n"
        "    return svc\n\n\ndef poke():\n"
        '    sys._getframe(0).f_globals["get"]().t = other.t\n',
        "use.py": "import get as G\n\n\ndef go():\n    G.poke()\n",
    },
}


@pytest.mark.parametrize("case", sorted(RULE_TREES))
def test_rule_trees_stay_ambiguous(tmp_path: Path, case: str) -> None:
    root = _write(
        tmp_path,
        {"svc.py": _SVC, "other.py": _OTHER, "main.py": _MAIN, **RULE_TREES[case]},
    )
    assert _cpython(root) == "OTHER.t", case
    assert _resolutions(root, "svc.py") == ["ambiguous"], case
