"""Tier 2 call resolution for Python, ``call_resolution="imports"`` (#682 PR 6).

Plan ``plans/detailed-scoped-call-resolution-682.md`` sections 9.4-9.8. The
committed fixtures' expected tables are asserted in
``test_call_resolution_engine.py``; this module covers each rule on trees the
tests write, because a committed tree would change the off-mode baseline
(11.2):

- import bindings, module paths (package before module before namespace
  directory, at every component; the script directory; relative imports),
  name lookup (re-export hops, attribute/submodule conflicts, the hop
  limit) and member chains;
- other files' writes to a module's globals (treesitter-chunker#697): an
  imported module object may appear only in a closed list of uses; every
  other use taints it, and a taint makes every proof of the written name
  fail closed, the module's own Tier 1 proofs included;
- run-wide causes (routes that can load or write any module), the
  unparsed-file classification, and owner decision O-2 (scope by caller).

Each positive is unchanged in ``structural`` mode, where an import proves
nothing (6.3). Each near-miss keeps its off-mode edge exactly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from chunker.call_resolution import engine, py_modules
from chunker.call_resolution.facts import (
    KNOWN_NONE_REASONS,
    valid_py_module_bindings,
    valid_scope_facts,
)
from chunker.symbol_graph import (
    SKIP_PARTS,
    assemble_symbol_graph,
    collect_source_files,
    extract_symbol_facts_for_file,
    extract_symbol_graph,
    has_directory_symlink,
)

MODE = "imports"
SVC = "def t():\n    return 1\n\n\ndef run():\n    return t()\n"
USE = "from svc import t\n\n\ndef u():\n    return t()\n"
# Another definition of ``t``, so today's candidate set has two members.
OTHER = {"other.py": "def t():\n    return 2\n"}


def _write(root: Path, files: dict[str, str | bytes]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="utf-8")
    return root


def _label(outcome: Any) -> str | None:
    if outcome is None:
        return None
    if outcome["outcome"] == "none":
        return f"none({outcome['reason']})"
    return str(outcome["outcome"])


def _context(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any], Any]:
    facts = [
        extract_symbol_facts_for_file(path, root, None, call_resolution=MODE)
        for path in collect_source_files(root, None)
    ]
    for item in facts:
        assert valid_scope_facts(item["scope_facts"], item["language"])
    links = has_directory_symlink(root)
    graph = assemble_symbol_graph(
        facts,
        total_files=len(facts),
        call_resolution=MODE,
        directory_symlinks=links,
    )
    context = engine.build_run_context(
        facts, graph["symbol_lookup"], MODE, directory_symlinks=links
    )
    return facts, graph, context


def _run(
    root: Path, file: str, reference: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str | None]:
    """``(off edge, structural edge, imports edge, imports outcome label)``."""
    _facts, graph, context = _context(root)
    off = extract_symbol_graph(root)
    structural = extract_symbol_graph(root, call_resolution="structural")
    on = extract_symbol_graph(root, call_resolution=MODE)
    assert on == graph

    def pick(document: dict[str, Any]) -> dict[str, Any]:
        (edge,) = [
            edge
            for edge in document["relationships"]
            if edge["type"] == "calls"
            and edge["file"] == file
            and edge["reference"] == reference
        ]
        return edge

    off_edge = pick(off)
    decision = engine.decide(context, off_edge)
    label = _label(decision.outcome) if decision.eligible else None
    return off_edge, pick(structural), pick(on), label


def _target(graph_edge: dict[str, Any], root: Path) -> str:
    graph = extract_symbol_graph(root, call_resolution=MODE)
    return str(graph["symbol_lookup"][graph_edge["to"]]["file"])


# ---------------------------------------------------------------------------
# Positives: each resolves in ``imports`` mode and is unchanged in
# ``structural`` mode. ``(files, (file, reference), target file, rules)``.

POSITIVES: dict[str, tuple[dict[str, str], tuple[str, str], str, list[str]]] = {
    "from-import": (
        {"svc.py": SVC, "use.py": USE},
        ("use.py", "t"),
        "svc.py",
        ["t2.import"],
    ),
    "relative": (
        {
            "pkg/__init__.py": "",
            "pkg/svc.py": SVC,
            "pkg/sub/__init__.py": "",
            "pkg/sub/use.py": "from ..svc import t\n\n\ndef u():\n    return t()\n",
        },
        ("pkg/sub/use.py", "t"),
        "pkg/svc.py",
        ["t2.import"],
    ),
    "relative-dot": (
        {
            "pkg/__init__.py": "",
            "pkg/svc.py": SVC,
            "pkg/use.py": "from . import svc\n\n\ndef u():\n    return svc.t()\n",
        },
        ("pkg/use.py", "svc.t"),
        "pkg/svc.py",
        ["t2.namespace"],
    ),
    "import-module": (
        {"svc.py": SVC, "use.py": "import svc\n\n\ndef u():\n    return svc.t()\n"},
        ("use.py", "svc.t"),
        "svc.py",
        ["t2.namespace"],
    ),
    "import-dotted-chain": (
        {
            "pkg/__init__.py": "",
            "pkg/svc.py": SVC,
            "use.py": "import pkg.svc\n\n\ndef u():\n    return pkg.svc.t()\n",
        },
        ("use.py", "pkg.svc.t"),
        "pkg/svc.py",
        ["t2.namespace"],
    ),
    "import-as": (
        {
            "pkg/__init__.py": "",
            "pkg/svc.py": SVC,
            "use.py": "import pkg.svc as s\n\n\ndef u():\n    return s.t()\n",
        },
        ("use.py", "s.t"),
        "pkg/svc.py",
        ["t2.namespace"],
    ),
    "namespace-package": (
        {
            "ns/svc.py": SVC,
            "use.py": "from ns.svc import t\n\n\ndef u():\n    return t()\n",
        },
        ("use.py", "t"),
        "ns/svc.py",
        ["t2.import"],
    ),
    "package-before-module": (
        {
            "svc/__init__.py": SVC,
            "svc.py": "def t():\n    return 3\n",
            "use.py": USE,
        },
        ("use.py", "t"),
        "svc/__init__.py",
        ["t2.import"],
    ),
    "init-reexport": (
        {
            "pkg/__init__.py": "from .impl import t\n",
            "pkg/impl.py": SVC,
            "use.py": "from pkg import t\n\n\ndef u():\n    return t()\n",
        },
        ("use.py", "t"),
        "pkg/impl.py",
        ["t2.import"],
    ),
    "local-import": (
        {"svc.py": SVC, "use.py": "def u():\n    from svc import t\n    return t()\n"},
        ("use.py", "t"),
        "svc.py",
        ["t2.import"],
    ),
    "group-same-target": (
        {
            "svc.py": SVC,
            "use.py": (
                "try:\n    from svc import t\nexcept ImportError:\n"
                "    from svc import t\n\n\ndef u():\n    return t()\n"
            ),
        },
        ("use.py", "t"),
        "svc.py",
        ["t2.import"],
    ),
    # The module path of a relative import is a name, not a use of the
    # module object bound under the same name.
    "relative-import-path-is-not-a-use": (
        {
            "pkg/__init__.py": "",
            "pkg/svc.py": SVC,
            "pkg/use.py": "from .svc import t\n\n\ndef u():\n    return t()\n",
            "pkg/w.py": "from . import svc\nfrom .svc import run as svc_run\n",
        },
        ("pkg/use.py", "t"),
        "pkg/svc.py",
        ["t2.import"],
    ),
    # Inert uses of the module system leave Tier 2 on.
    "main-guard": (
        {
            "svc.py": SVC,
            "use.py": USE + "\n\nif __name__ == '__main__':\n    u()\n",
        },
        ("use.py", "t"),
        "svc.py",
        ["t2.import"],
    ),
    "inert-sys": (
        {
            "svc.py": SVC,
            "use.py": USE,
            "w.py": (
                "import sys\nimport importlib.metadata\n\n\ndef f(p):\n"
                "    print(sys.argv, 'svc' in sys.modules, p in sys.path)\n"
                "    return importlib.metadata.version('x')\n"
            ),
        },
        ("use.py", "t"),
        "svc.py",
        ["t2.import"],
    ),
    "module-read-is-inert": (
        {
            "svc.py": SVC,
            "use.py": USE,
            "w.py": (
                "import svc\n\n\ndef f():\n    if svc is None or not svc:\n"
                "        return svc.__name__\n    return svc.run()\n"
            ),
        },
        ("use.py", "t"),
        "svc.py",
        ["t2.import"],
    ),
    "external-literal-import": (
        {
            "svc.py": SVC,
            "use.py": USE,
            "w.py": "import importlib\n\nyaml = importlib.import_module('yaml')\n",
        },
        ("use.py", "t"),
        "svc.py",
        ["t2.import"],
    ),
    "own-eval-is-not-the-builtin": (
        {
            "svc.py": SVC,
            "use.py": USE,
            "w.py": "def f(eval):\n    return eval(1)\n",
        },
        ("use.py", "t"),
        "svc.py",
        ["t2.import"],
    ),
}


@pytest.mark.parametrize("case", sorted(POSITIVES))
def test_tier2_positives_resolve_end_to_end(tmp_path: Path, case: str) -> None:
    files, (file, reference), target, rules = POSITIVES[case]
    root = _write(tmp_path, {**files, **OTHER})
    off, structural, on, label = _run(root, file, reference)
    assert off["resolution"] == "ambiguous"
    assert structural == off
    assert on["resolution"] == "resolved", label
    assert _target(on, root) == target
    assert on["provenance"]["call_rules"] == rules
    assert on["provenance"]["call_resolution"] == MODE
    assert label == "import"


def test_import_groups_narrow_to_the_group(tmp_path: Path) -> None:
    """9.4: two or more imports narrow to the group and do not resolve."""
    root = _write(
        tmp_path,
        {
            "a.py": "def t():\n    return 1\n",
            "b.py": "def t():\n    return 2\n",
            "c.py": "def t():\n    return 3\n",
            "use.py": (
                "try:\n    from a import t\nexcept ImportError:\n"
                "    from b import t\n\n\ndef u():\n    return t()\n"
            ),
        },
    )
    off, structural, on, label = _run(root, "use.py", "t")
    assert structural == off
    assert on["resolution"] == "ambiguous"
    assert len(on["candidates"]) == 2 and len(off["candidates"]) == 3
    assert on["provenance"]["call_rules"] == ["t2.import"]
    assert label == "import"


# ---------------------------------------------------------------------------
# Near-misses: each keeps its off-mode edge exactly in both modes.

NEAR_MISSES: dict[str, tuple[dict[str, str], tuple[str, str], str]] = {
    "module-not-found": (
        {"use.py": USE, "svc2.py": SVC},
        ("use.py", "t"),
        "module-not-found",
    ),
    "intermediate-module": (
        {
            "a.py": "",
            "a/svc.py": SVC,
            # A root ``svc.py`` a component-wise walk must not fall into.
            "svc.py": "def t():\n    return 4\n",
            "use.py": "from a.svc import t\n\n\ndef u():\n    return t()\n",
        },
        ("use.py", "t"),
        "module-not-found",
    ),
    "module-before-namespace-dir": (
        {
            "D.py": "",
            "D/svc.py": SVC,
            "use.py": "from D.svc import t\n\n\ndef u():\n    return t()\n",
        },
        ("use.py", "t"),
        "module-not-found",
    ),
    "outside-root": (
        {"svc.py": SVC, "use.py": "from .svc import t\n\n\ndef u():\n    return t()\n"},
        ("use.py", "t"),
        "outside-root",
    ),
    "script-dir": (
        {"svc.py": SVC, "tools/svc.py": SVC, "tools/use.py": USE},
        ("tools/use.py", "t"),
        "script-dir-shadow",
    ),
    "stdlib-name": (
        {
            "json.py": SVC,
            "use.py": "from json import t\n\n\ndef u():\n    return t()\n",
        },
        ("use.py", "t"),
        "external-module",
    ),
    "attr-submodule-conflict": (
        {
            "pkg/__init__.py": "from .impl import t\n",
            "pkg/impl.py": SVC,
            "pkg/t.py": "",
            "use.py": "from pkg import t\n\n\ndef u():\n    return t()\n",
        },
        ("use.py", "t"),
        "attr-submodule-conflict",
    ),
    "submodule-called": (
        {
            "pkg/__init__.py": "",
            "pkg/t.py": SVC,
            "use.py": "from pkg import t\n\n\ndef u():\n    return t()\n",
        },
        ("use.py", "t"),
        "non-callable",
    ),
    "star-import-in-target": (
        {
            "svc.py": "from os import *\n\n\ndef t():\n    return 1\n",
            "use.py": USE,
        },
        ("use.py", "t"),
        "star-import",
    ),
    "module-getattr": (
        {
            "svc.py": "def __getattr__(name):\n    return len\n",
            "use.py": USE,
            "x.py": SVC,
        },
        ("use.py", "t"),
        "export-not-found",
    ),
    "conditional-target": (
        {
            "svc.py": "import os\n\nif os.sep:\n    def t():\n        return 1\n",
            "use.py": USE,
        },
        ("use.py", "t"),
        "conditional",
    ),
    "assigned-target": (
        {"svc.py": "def _t():\n    return 1\n\n\nt = _t\n", "use.py": USE, "x.py": SVC},
        ("use.py", "t"),
        "local-variable",
    ),
    "single-conditional-import": (
        {
            "svc.py": SVC,
            "use.py": (
                "import os\n\nif os.sep:\n    from svc import t\n\n\n"
                "def u():\n    return t()\n"
            ),
        },
        ("use.py", "t"),
        "conditional",
    ),
    "cycle": (
        {
            "a.py": "from b import t\n",
            "b.py": "from a import t\n",
            "use.py": "from a import t\n\n\ndef u():\n    return t()\n",
            "x.py": SVC,
        },
        ("use.py", "t"),
        "cycle",
    ),
    "hop-limit": (
        {
            "p1/__init__.py": "from p2 import t\n",
            "p2/__init__.py": "from p3 import t\n",
            "p3/__init__.py": "from p4 import t\n",
            "p4/__init__.py": "from svc import t\n",
            "svc.py": SVC,
            "use.py": "from p1 import t\n\n\ndef u():\n    return t()\n",
        },
        ("use.py", "t"),
        "hop-limit",
    ),
    "chain-through-a-function": (
        {"svc.py": SVC, "use.py": "import svc\n\n\ndef u():\n    return svc.t.t()\n"},
        ("use.py", "svc.t.t"),
        "export-not-found",
    ),
    "skipped-directory-component": (
        {
            "svc.py": SVC,
            "use.py": "from archive.svc import t\n\n\ndef u():\n    return t()\n",
        },
        ("use.py", "t"),
        "unknown-variant",
    ),
    "group-with-a-failing-member": (
        {
            "svc.py": SVC,
            "use.py": (
                "try:\n    from svc import t\nexcept ImportError:\n"
                "    from missing import t\n\n\ndef u():\n    return t()\n"
            ),
        },
        ("use.py", "t"),
        "module-not-found",
    ),
}


@pytest.mark.parametrize("case", sorted(NEAR_MISSES))
def test_tier2_near_misses_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    files, (file, reference), reason = NEAR_MISSES[case]
    root = _write(tmp_path, {**files, **OTHER})
    off, structural, on, label = _run(root, file, reference)
    assert off["resolution"] == "ambiguous"
    assert structural == off
    assert on == off
    assert label == f"none({reason})"
    assert reason in KNOWN_NONE_REASONS


def test_member_calls_other_than_module_chains_are_not_eligible(tmp_path: Path) -> None:
    """A parenthesized head, a call in the chain or a local object is not a
    module member chain: not eligible, so unchanged."""
    root = _write(
        tmp_path,
        {
            "svc.py": SVC,
            **OTHER,
            "use.py": (
                "import svc\n\n\ndef u(o):\n    (svc).t()\n    o.t()\n"
                "    return svc.run().t()\n"
            ),
        },
    )
    _facts, graph, context = _context(root)
    off = extract_symbol_graph(root)
    for edge, on_edge in zip(off["relationships"], graph["relationships"], strict=True):
        if (
            edge["type"] == "calls"
            and edge["file"] == "use.py"
            and edge["reference"] != "svc.t"
        ):
            assert on_edge == edge


# ---------------------------------------------------------------------------
# treesitter-chunker#697: another run file writing a module's globals. Each
# route is written in ``w.py`` (production). ``use.py``'s Tier 2 edge and
# ``svc.py``'s own Tier 1 edge (``run`` -> ``t``) keep their off-mode form in
# ``imports`` mode; ``structural`` still resolves ``svc.py``'s edge, as on
# main.

ROUTES_697: dict[str, tuple[dict[str, str], str]] = {
    "attribute-write": ({"w.py": "import svc\n\nsvc.t = len\n"}, "reassigned"),
    "setattr": ({"w.py": "import svc\n\nsetattr(svc, 't', len)\n"}, "reassigned"),
    "delattr": ({"w.py": "import svc\n\ndelattr(svc, 't')\n"}, "reassigned"),
    "del": ({"w.py": "import svc\n\ndel svc.t\n"}, "reassigned"),
    "augmented": ({"w.py": "import svc\n\nsvc.t += 1\n"}, "reassigned"),
    "for-target": (
        {"w.py": "import svc\n\nfor svc.t in [len]:\n    pass\n"},
        "reassigned",
    ),
    "parenthesized-target": ({"w.py": "import svc\n\n(svc).t = len\n"}, "reassigned"),
    "import-as": ({"w.py": "import svc as s\n\ns.t = len\n"}, "reassigned"),
    "function-local-import": (
        {"w.py": "def f():\n    import svc\n    svc.t = len\n"},
        "reassigned",
    ),
    "from-package-import": (
        {
            "pkg/__init__.py": "",
            "pkg/svc.py": SVC,
            "svc.py": "",
            "use.py": "from pkg.svc import t\n\n\ndef u():\n    return t()\n",
            "w.py": "from pkg import svc as m\n\nm.t = len\n",
        },
        "reassigned",
    ),
    "dict-write": (
        {"w.py": "import svc\n\nsvc.__dict__['t'] = len\n"},
        "module-escape",
    ),
    "vars-update": (
        {"w.py": "import svc\n\nvars(svc).update(t=len)\n"},
        "module-escape",
    ),
    "shadowed-setattr": (
        {"w.py": "import svc\n\n\ndef f(setattr):\n    setattr(svc, 't', len)\n"},
        "module-escape",
    ),
    "setattr-computed": (
        {"w.py": "import svc\n\n\ndef f(n):\n    setattr(svc, n, len)\n"},
        "module-escape",
    ),
    "alias-escape": ({"w.py": "import svc\n\nx = svc\nx.t = len\n"}, "module-escape"),
    "argument-escape": (
        {"w.py": "import svc\n\n\ndef f(mp):\n    mp.setattr(svc, 't', len)\n"},
        "module-escape",
    ),
    # #706: a returned module is followed through the call result, so the
    # escape is the result's use (a container element), not the return.
    "return-escape": (
        {"w.py": "import svc\n\n\ndef get():\n    return svc\n\n\nKEEP = [get()]\n"},
        "module-escape",
    ),
    "class-attribute": ({"w.py": "class K:\n    import svc\n"}, "module-escape"),
    "global-redirect": (
        {"w.py": "def f():\n    global svc\n    import svc\n"},
        "module-escape",
    ),
    "dunder-method": (
        {"w.py": "import svc\n\nsvc.__setattr__('t', len)\n"},
        "module-escape",
    ),
    "patch-object": (
        {
            "w.py": "from unittest import mock\nimport svc\n\nmock.patch.object(svc, 't')\n"
        },
        "module-escape",
    ),
    "sys-modules-literal": (
        {"w.py": "import sys\n\nsys.modules['svc'].t = len\n"},
        "module-escape",
    ),
    "sys-modules-get": (
        {"w.py": "import sys\n\nsys.modules.get('svc').t = len\n"},
        "module-escape",
    ),
    "import-module-literal": (
        {"w.py": "import importlib\n\nimportlib.import_module('svc').t = len\n"},
        "module-escape",
    ),
    "dunder-import-literal": ({"w.py": "__import__('svc').t = len\n"}, "module-escape"),
    "patch-string": (
        {"w.py": "from unittest import mock\n\nmock.patch('svc.t', len).start()\n"},
        "reassigned",
    ),
    "monkeypatch-string": (
        {"w.py": "def f(monkeypatch):\n    monkeypatch.setattr('svc.t', len)\n"},
        "reassigned",
    ),
    "resolve-name-colon": (
        {"w.py": "def f(p):\n    p.setattr('svc:t', len)\n"},
        "reassigned",
    ),
    "dotted-import-chain": (
        {
            "pkg/__init__.py": "",
            "pkg/svc.py": SVC,
            "svc.py": "",
            "use.py": "from pkg.svc import t\n\n\ndef u():\n    return t()\n",
            "w.py": "import pkg.svc\n\npkg.svc.t = len\n",
        },
        "reassigned",
    ),
    "star-exposes-modules": (
        {"pkg/__init__.py": "import svc\n", "w.py": "from pkg import *\n"},
        "module-escape",
    ),
    "reexported-module-object": (
        {
            "pkg/__init__.py": "import svc as alias\n",
            "w.py": "import pkg\n\npkg.alias.t = len\n",
        },
        "reassigned",
    ),
    "package-escape-exposes-imports": (
        {"pkg/__init__.py": "import svc\n", "w.py": "import pkg\n\nvars(pkg)\n"},
        "module-escape",
    ),
    "script-directory-writer": (
        {"tools/svc.py": "", "tools/w.py": "import svc\n\nsvc.t = len\n"},
        "reassigned",
    ),
    "mixed-binding-head": (
        {
            "w.py": (
                "try:\n    import svc\nexcept ImportError:\n    svc = None\n\n"
                "svc.t = len\n"
            )
        },
        "reassigned",
    ),
}


@pytest.mark.parametrize("route", sorted(ROUTES_697))
def test_other_files_writes_fail_closed(tmp_path: Path, route: str) -> None:
    extra, reason = ROUTES_697[route]
    root = _write(tmp_path, {"svc.py": SVC, "use.py": USE, **OTHER, **extra})
    off, structural, on, label = _run(root, "use.py", "t")
    assert on == off, route
    assert label == f"none({reason})", route
    # The written module's own Tier 1 proof: resolved by ``structural`` (as on
    # main), failed closed by ``imports`` (#697).
    written = "pkg/svc.py" if extra.get("svc.py") == "" else "svc.py"
    own_off, own_structural, own_on, own_label = _run(root, written, "t")
    assert own_structural["resolution"] == "resolved", route
    assert own_on == own_off, route
    assert own_label == f"none({reason})", route


def test_a_write_through_another_dotted_name_is_another_module(tmp_path: Path) -> None:
    """Within one process a dotted name is one module object: ``svc.py``
    imported as ``proj.svc`` (another root) is a separate object, so the write
    does not reach the ``svc`` the proof names."""
    root = _write(
        tmp_path,
        {
            "svc.py": SVC,
            "use.py": USE,
            **OTHER,
            "w.py": "import proj.svc\n\nproj.svc.t = len\n",
        },
    )
    _off, _structural, on, label = _run(root, "use.py", "t")
    assert on["resolution"] == "resolved"
    assert label == "import"


def test_a_writer_below_the_root_also_writes_its_script_directory(
    tmp_path: Path,
) -> None:
    """``tools/w.py`` run as a script (or under pytest's rootdir insertion)
    imports ``tools/svc.py`` as ``svc``: that module is written too."""
    root = _write(
        tmp_path,
        {
            "tools/__init__.py": "",
            "tools/svc.py": SVC,
            "tools/w.py": "import svc\n\nsvc.t = len\n",
            "use.py": "from tools.svc import t\n\n\ndef u():\n    return t()\n",
            **OTHER,
        },
    )
    off, _structural, on, label = _run(root, "use.py", "t")
    assert on == off
    assert label == "none(reassigned)"


def test_a_write_of_another_name_leaves_the_proof(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            "svc.py": SVC,
            "use.py": USE,
            **OTHER,
            "w.py": "import svc\n\nsvc.other = len\n",
        },
    )
    _off, _structural, on, label = _run(root, "use.py", "t")
    assert on["resolution"] == "resolved"
    assert label == "import"


def test_a_tainted_hop_fails_the_proof(tmp_path: Path) -> None:
    """A write of the name in a re-exporting module also fails the lookup."""
    root = _write(
        tmp_path,
        {
            "pkg/__init__.py": "from .impl import t\n",
            "pkg/impl.py": SVC,
            "use.py": "from pkg import t\n\n\ndef u():\n    return t()\n",
            "w.py": "import pkg.impl\n\npkg.impl.t = len\n",
            **OTHER,
        },
    )
    off, _structural, on, label = _run(root, "use.py", "t")
    assert on == off
    assert label == "none(reassigned)"


# ---------------------------------------------------------------------------
# Run-wide causes (E5-3 analog): written in production ``w.py``, each fails
# every Python proof closed, Tier 1 included.

CAUSES: dict[str, tuple[str, str]] = {
    "exec": ("def f(s):\n    exec(s)\n", "evaluator"),
    "eval-handed-on": ("e = eval\n", "evaluator"),
    "exec-compile": (
        "def f(s):\n    exec(compile(s, 'x', 'exec'))\n",
        "evaluator",
    ),
    "import-module-computed": (
        "import importlib\n\n\ndef f(n):\n    return importlib.import_module(n)\n",
        "dynamic-loader",
    ),
    "import-module-from": (
        "from importlib import import_module as im\n\n\ndef f(n):\n    return im(n)\n",
        "dynamic-loader",
    ),
    "import-module-classified-literal": (
        "import importlib\n\nb = importlib.import_module('builtins')\n",
        "dynamic-loader",
    ),
    "dunder-import-computed": (
        "def f(n):\n    return __import__(n)\n",
        "dynamic-loader",
    ),
    "importlib-util": (
        "import importlib.util\n\n\ndef f(p):\n"
        "    return importlib.util.spec_from_file_location('svc', p)\n",
        "dynamic-loader",
    ),
    "importlib-value": ("import importlib\n\nx = importlib\n", "dynamic-loader"),
    "reload-computed": (
        "import importlib\n\n\ndef f(g):\n    importlib.reload(g())\n",
        "dynamic-loader",
    ),
    "runpy": ("import runpy\n\nrunpy.run_module('svc')\n", "dynamic-loader"),
    "resolve-name": (
        "import pkgutil\n\n\ndef f(n):\n    return pkgutil.resolve_name(n)\n",
        "dynamic-loader",
    ),
    "relative-import-module-computed-package": (
        "import importlib\n\n\ndef f(p):\n    return importlib.import_module('.svc', p)\n",
        "unresolvable-writer",
    ),
    "sys-modules-computed": (
        "import sys\n\n\ndef f(k, m):\n    sys.modules[k] = m\n",
        "module-system",
    ),
    "sys-modules-items": (
        "import sys\n\nx = list(sys.modules.items())\n",
        "module-system",
    ),
    "sys-path-insert": ("import sys\n\nsys.path.insert(0, 'x')\n", "module-system"),
    "sys-meta-path": (
        "import sys\n\nsys.meta_path.append(object())\n",
        "module-system",
    ),
    "sys-handed-on": ("import sys\n\n\ndef f(g):\n    g(sys)\n", "module-system"),
    "from-sys-modules": (
        "from sys import modules\n\nmodules.clear()\n",
        "module-system",
    ),
    "os-sys-modules": (
        "import os\n\n\ndef f(k):\n    return os.sys.modules[k]\n",
        "module-system",
    ),
    "patch-dict-sys-modules": (
        "from unittest import mock\n\nmock.patch.dict('sys.modules', {})\n",
        "module-system",
    ),
    "package-path": ("__path__ = []\n", "module-system"),
    "site": ("import site\n\nsite.addsitedir('x')\n", "module-system"),
    "globals-of-a-function": (
        "def f(g):\n    g.__globals__['t'] = len\n",
        "module-object",
    ),
    "frame-globals": (
        "import sys\n\n\ndef f():\n    sys._getframe(1).f_globals['t'] = len\n",
        "module-object",
    ),
    "builtins": ("import builtins\n\nbuiltins.t = len\n", "module-object"),
    "main-module": ("import __main__\n\n__main__.t = len\n", "module-object"),
    "frame-locals-write": (
        "import sys\n\n\ndef f():\n    sys._getframe(1).f_locals['t'] = len\n",
        "module-object",
    ),
    "pythonapi": (
        "import ctypes\n\n\ndef f(o):\n    ctypes.pythonapi.PyObject_SetAttr(o)\n",
        "module-object",
    ),
}


@pytest.mark.parametrize("case", sorted(CAUSES))
def test_run_wide_causes_fail_closed(tmp_path: Path, case: str) -> None:
    """A cause shuts off Tier 2 (as for TS/JS, PR 5); Tier 1 proofs keep
    their ``structural`` result."""
    writer, cause = CAUSES[case]
    root = _write(tmp_path, {"svc.py": SVC, "use.py": USE, **OTHER, "w.py": writer})
    off, structural, on, label = _run(root, "use.py", "t")
    assert structural == off
    assert on == off, case
    assert label == f"none(run-tainted:{cause})", case
    _own_off, own_structural, own_on, _own_label = _run(root, "svc.py", "t")
    assert own_structural["resolution"] == "resolved"
    for key in ("resolution", "candidates", "to"):
        assert own_on[key] == own_structural[key]


@pytest.mark.parametrize(
    "writer",
    [
        "def f(g):\n    g.__closure__[0].cell_contents = len\n",
        "def f(g):\n    return g.__code__, g.__defaults__\n",
        "import ctypes\n\n\ndef f():\n    return ctypes.windll\n",
        # A syntax check: ``compile`` alone runs nothing (#705 Q2).
        "def check(src):\n    compile(src, 'x', 'exec')\n    return True\n",
        "def f(tb):\n    return tb.tb_frame.f_locals.get('x'), tb.tb_frame.f_code\n",
        "def f(fr):\n    return 'x' in fr.f_locals and fr.f_locals['x']\n",
    ],
)
def test_routes_that_cannot_change_a_module_attribute_are_no_cause(
    tmp_path: Path, writer: str
) -> None:
    """Closure cells, reads of code objects and defaults, ``ctypes``
    without ``pythonapi`` and frame-locals reads leave every module attribute
    as it is (a write of ``__code__`` and its kin is a cause since fold 3,
    #705 N-1)."""
    root = _write(tmp_path, {"svc.py": SVC, "use.py": USE, **OTHER, "w.py": writer})
    _off, _structural, on, label = _run(root, "use.py", "t")
    assert on["resolution"] == "resolved"
    assert label == "import"


UNPARSED: dict[str, bytes] = {
    "syntax-error": b"def f(:\n    pass\n",
    "non-ascii-name": "def f():\n    \u00e9 = 1\n".encode(),
    "space-before-tab": b"def f():\n    \tpass\n",
    "lone-cr": b"def f():\r    pass\n",
    "nul": b"x = 1\n# \x00\n",
    "vertical-tab": b"x = 1\n# \x0b\n",
    "latin-1-coding": b"# -*- coding: latin-1 -*-\nx = 1\n",
    "bom-and-coding": b"\xef\xbb\xbf# coding: utf-8\nx = 1\n",
    "tab-space-mix": b"def f():\n\tif 1:\n\t\tpass\n\ndef g():\n    pass\n",
}


@pytest.mark.parametrize("case", sorted(UNPARSED))
def test_unparsed_files_are_a_run_wide_cause(tmp_path: Path, case: str) -> None:
    """E5-7 analog: a Python file tree-sitter cannot parse cleanly, or one
    CPython may read differently with no tree error, may load or write any
    module."""
    root = _write(
        tmp_path, {"svc.py": SVC, "use.py": USE, **OTHER, "w.py": UNPARSED[case]}
    )
    off, _structural, on, label = _run(root, "use.py", "t")
    assert on == off
    assert label == "none(run-tainted:unparsed-file)"


@pytest.mark.parametrize(
    "text",
    [
        b"# coding: utf-8\nx = 1\n",
        b"# -*- coding: ascii -*-\nx = 1\n",
        b"\xef\xbb\xbfx = 1\n",
        b"x = 1\r\ny = 2\r\n",
        b"def f():\n\tpass\n\ndef g():\n\tpass\n",
        b"x = [1, \\\n     2]\n",
    ],
)
def test_parse_hazard_controls(text: bytes) -> None:
    from chunker.parser import get_parser

    root = get_parser("python").parse(text).root_node
    assert not root.has_error
    assert py_modules.parse_hazard(text, root) is None


# ---------------------------------------------------------------------------
# Owner decision O-2: scope by caller.


@pytest.mark.parametrize(
    ("path", "test"),
    [
        ("test_svc.py", True),
        ("svc_test.py", True),
        ("conftest.py", True),
        ("pkg/conftest.py", True),
        ("tests/helper.py", True),
        ("test/helper.py", True),
        ("a/tests/b/c.py", True),
        ("testing/helper.py", False),
        ("contest.py", False),
        ("Tests/helper.py", False),
        ("my_tests.py", False),
        ("test.py", False),
        ("tests.py", False),
        ("attest_svc.py", False),
        ("svc_test_util.py", False),
    ],
)
def test_test_classifier_is_closed_and_case_sensitive(path: str, test: bool) -> None:
    assert py_modules.is_test_path(path) is test


def test_test_file_causes_reach_only_test_callers(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            "svc.py": SVC,
            "use.py": USE,
            **OTHER,
            "tests/test_use.py": "from svc import t\n\n\ndef test_u():\n    return t()\n",
            "tests/conftest.py": "def f(s):\n    exec(s)\n",
        },
    )
    _off, _structural, on, label = _run(root, "use.py", "t")
    assert on["resolution"] == "resolved" and label == "import"
    off, _structural, on, label = _run(root, "tests/test_use.py", "t")
    assert on == off
    assert label == "none(run-tainted:evaluator)"


def test_test_file_taints_reach_only_test_callers(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            "svc.py": SVC,
            "use.py": USE,
            **OTHER,
            "tests/test_use.py": "from svc import t\n\n\ndef test_u():\n    return t()\n",
            "tests/test_patch.py": (
                "import svc\n\n\ndef test_p(monkeypatch):\n"
                "    monkeypatch.setattr(svc, 't', len)\n"
            ),
        },
    )
    _off, _structural, on, label = _run(root, "use.py", "t")
    assert on["resolution"] == "resolved" and label == "import"
    off, _structural, on, label = _run(root, "tests/test_use.py", "t")
    assert on == off
    assert label == "none(module-escape)"


def test_a_test_file_production_reaches_is_production(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            "svc.py": SVC,
            "use.py": USE,
            **OTHER,
            "app.py": "from tests import helpers\n",
            "tests/__init__.py": "",
            "tests/helpers.py": "def f(s):\n    exec(s)\n",
        },
    )
    off, _structural, on, label = _run(root, "use.py", "t")
    assert on == off
    assert label == "none(run-tainted:evaluator)"


def test_unknown_directory_symlinks_make_every_file_production(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {"svc.py": SVC, "use.py": USE, **OTHER, "tests/conftest.py": "exec('x')\n"},
    )
    facts = [
        extract_symbol_facts_for_file(path, root, None, call_resolution=MODE)
        for path in collect_source_files(root, None)
    ]
    for links in (None, True):
        run = py_modules.build_py_module_run(facts, links)
        assert not run.test_scope
        assert run.shutoff == {"evaluator": "tests/conftest.py"}
    run = py_modules.build_py_module_run(facts, False)
    assert run.test_scope == {"tests/conftest.py"}
    assert run.test_shutoff == {"evaluator": "tests/conftest.py"}


# ---------------------------------------------------------------------------
# Facts and pins.


def test_module_bindings_are_well_formed(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            "svc.py": SVC,
            "use.py": (
                USE + "import svc\nimport sys\nsvc.x = 1\nsys.modules['svc']\n"
                "from os import *\nP = 'svc.t'\n"
            ),
        },
    )
    facts = {
        item["path"]: item["scope_facts"]
        for item in (
            extract_symbol_facts_for_file(path, root, None, call_resolution=MODE)
            for path in collect_source_files(root, None)
        )
    }
    bindings = facts["use.py"]["module_bindings"]
    assert valid_py_module_bindings(bindings)
    assert ["svc", "write", "x"] in bindings["uses"]
    assert ["svc", "*"] in bindings["taints"]
    assert bindings["stars"] == ["os"]
    assert bindings["strings"] == ["svc.t"]
    assert {"svc", "sys", "os"} <= set(bindings["imports"])
    assert facts["svc.py"]["exports"]["t"]["outcome"] == "local"
    broken = {**bindings, "shutoff": ["nope"]}
    assert not valid_py_module_bindings(broken)


def test_copies_are_pinned() -> None:
    import sys

    assert set(SKIP_PARTS) == py_modules.SKIPPED_DIRECTORIES
    assert set(sys.stdlib_module_names) <= py_modules.STDLIB_MODULES
    assert set(py_modules.SHUTOFF_CAUSES) == {
        "evaluator",
        "dynamic-loader",
        "module-system",
        "module-object",
        "unparsed-file",
        "unresolvable-writer",
    }
    for cause in py_modules.SHUTOFF_CAUSES:
        assert f"run-tainted:{cause}" in KNOWN_NONE_REASONS
    assert {py_modules.REASON_NAME_TAINT, py_modules.REASON_MODULE_TAINT} <= (
        KNOWN_NONE_REASONS
    )


def test_structural_mode_ignores_tier2_facts(tmp_path: Path) -> None:
    """``structural`` output never depends on another file's writes or on a
    run-wide cause (it stays byte-identical to main)."""
    root = _write(
        tmp_path,
        {
            "svc.py": SVC,
            "use.py": USE,
            **OTHER,
            "w.py": "import svc, sys\n\nsvc.t = len\nsys.path.insert(0, 'x')\n",
        },
    )
    structural = extract_symbol_graph(root, call_resolution="structural")
    (edge,) = [
        edge
        for edge in structural["relationships"]
        if edge["type"] == "calls" and edge["file"] == "svc.py"
    ]
    assert edge["resolution"] == "resolved"
    assert edge["provenance"]["call_rules"] == ["t1.lexical"]


# ---------------------------------------------------------------------------
# PR 6 fold 2 (#705 president rulings E6-1..E6-8). Each blocking case is a
# panel repro: ``(files, (file, reference), expected label, driver, runtime)``.
# ``driver`` is the program the panel ran; ``runtime`` is what CPython 3.14
# printed (checked with ``python -I -B -c <driver>`` in the tree): the
# function the edge would have named does NOT run, so the edge must keep its
# off-mode form. ``svc.t`` returns 1 and ``other.t`` returns 2.

PATCHER = "from other import t as o\n"
FOLD2_BLOCKING: dict[str, tuple[dict[str, str], tuple[str, str], str, str, str]] = {
    # E6-1 (A-1, B1): another file writes the importer's own global.
    "e6-1-name-write": (
        {"patch.py": "import use\n" + PATCHER + "use.t = o\n"},
        ("use.py", "t"),
        "reassigned",
        "import patch, use; print(use.u())",
        "2 (other.t runs)",
    ),
    "e6-1-setattr": (
        {"patch.py": "import use\n" + PATCHER + "setattr(use, 't', o)\n"},
        ("use.py", "t"),
        "reassigned",
        "import patch, use; print(use.u())",
        "2 (other.t runs)",
    ),
    "e6-1-patch-string": (
        {
            "patch.py": "from unittest import mock\n"
            + PATCHER
            + "mock.patch('use.t', o).start()\n"
        },
        ("use.py", "t"),
        "reassigned",
        "import patch, use; print(use.u())",
        "2 (other.t runs)",
    ),
    "e6-1-escape": (
        {
            "patch.py": "import use\n"
            + PATCHER
            + "def fix(m):\n    m.t = o\n\n\nfix(use)\n"
        },
        ("use.py", "t"),
        "module-escape",
        "import patch, use; print(use.u())",
        "2 (other.t runs)",
    ),
    "e6-1-module-rebind": (
        {
            "use.py": "import svc\n\n\ndef u():\n    return svc.t()\n",
            "patch.py": "import use\nimport other\nuse.svc = other\n",
        },
        ("use.py", "svc.t"),
        "reassigned",
        "import patch, use; print(use.u())",
        "2 (other.t runs)",
    ),
    # E6-1 (A-4): importing ``pkg.tool`` sets ``pkg/__init__.py``'s ``tool``.
    "e6-1-init-submodule": (
        {
            "util.py": "def t():\n    return 1\n",
            "pkg/__init__.py": "import util as tool\n\n\ndef run():\n    return tool.t()\n",
            "pkg/tool.py": "def t():\n    return 2\n",
            "main.py": "import pkg.tool\nimport pkg\n",
        },
        ("pkg/__init__.py", "tool.t"),
        "attr-submodule-conflict",
        "import pkg.tool, pkg; print(pkg.run())",
        "2 (pkg/tool.py's t runs)",
    ),
    # E6-2 (B2): the intermediary's import is not proven by its own lookup.
    "e6-2-try-except": (
        {
            "mid.py": "try:\n    import svc\nexcept ImportError:\n    svc = None\n",
            "patch.py": "import mid\n" + PATCHER + "mid.svc.t = o\n",
        },
        ("use.py", "t"),
        "reassigned",
        "import patch, use; print(use.u())",
        "2 (other.t runs)",
    ),
    "e6-2-if": (
        {
            "mid.py": "import os\n\nif os.sep:\n    import svc\n",
            "patch.py": "import mid\n" + PATCHER + "mid.svc.t = o\n",
        },
        ("use.py", "t"),
        "reassigned",
        "import patch, use; print(use.u())",
        "2 (other.t runs)",
    ),
    "e6-2-twice": (
        {
            "mid.py": "import svc\nimport svc\n",
            "patch.py": "import mid\n" + PATCHER + "mid.svc.t = o\n",
        },
        ("use.py", "t"),
        "reassigned",
        "import patch, use; print(use.u())",
        "2 (other.t runs)",
    ),
    "e6-2-globals": (
        {
            "mid.py": "import svc\n\nG = globals()\n",
            "patch.py": "import mid\n" + PATCHER + "mid.svc.t = o\n",
        },
        ("use.py", "t"),
        # #724: ``mid.py`` reads its own namespace, so its ``import svc``
        # is handed out and ``svc`` is tainted wholly, not only ``svc.t``.
        "module-escape",
        "import patch, use; print(use.u())",
        "2 (other.t runs)",
    ),
    "e6-2-whole-escape": (
        {
            "mid.py": "import os\n\nif os.sep:\n    import svc\n",
            "patch.py": "import mid\n"
            + PATCHER
            + "def fix(m):\n    m.svc.t = o\n\n\nfix(mid)\n",
        },
        ("use.py", "t"),
        "module-escape",
        "import patch, use; print(use.u())",
        "2 (other.t runs)",
    ),
    "e6-2-star": (
        {
            "mid.py": "import os\n\nif os.sep:\n    import svc\n",
            "patch.py": "from mid import *\n" + PATCHER + "svc.t = o\n",
        },
        ("use.py", "t"),
        "module-escape",
        "import patch, use; print(use.u())",
        "2 (other.t runs)",
    ),
    "e6-2-alias": (
        {
            "mid.py": "import os\n\nif os.sep:\n    import svc\n",
            "patch.py": "from mid import svc as s\n" + PATCHER + "s.t = o\n",
        },
        ("use.py", "t"),
        "reassigned",
        "import patch, use; print(use.u())",
        "2 (other.t runs)",
    ),
    # E6-3 (A-2, B4): ``import a.b as m`` binds ``getattr(a, "b")``.
    "e6-3-import-as-class": (
        {
            "a/__init__.py": "from . import b\nfrom .impl import Cfg as b\n",
            "a/b.py": "def t():\n    return 1\n",
            "a/impl.py": "class Cfg:\n    @staticmethod\n    def t():\n        return 3\n",
            "use.py": "import a.b as m\n\n\ndef u():\n    return m.t()\n",
        },
        ("use.py", "m.t"),
        "attr-submodule-conflict",
        "import use; print(use.u())",
        "3 (Cfg.t runs)",
    ),
    "e6-3-from-b-import-b": (
        {
            "a/__init__.py": "from .b import b\n",
            "a/b.py": (
                "def t():\n    return 1\n\n\nclass b:\n    @staticmethod\n"
                "    def t():\n        return 3\n"
            ),
            "use.py": "import a.b as m\n\n\ndef u():\n    return m.t()\n",
        },
        ("use.py", "m.t"),
        "attr-submodule-conflict",
        "import use; print(use.u())",
        "3 (class b's t runs)",
    ),
    "e6-3-rebound-to-another-module": (
        {
            "a/__init__.py": "from . import b\nimport other as b\n",
            "a/b.py": "def t():\n    return 1\n",
            "use.py": "import a.b as m\n\n\ndef u():\n    return m.t()\n",
        },
        ("use.py", "m.t"),
        "attr-submodule-conflict",
        "import use; print(use.u())",
        "2 (other.t runs)",
    ),
    # E6-3 (A-3, B3): PEP 562 ``__getattr__`` answers before the submodule.
    "e6-3-getattr-from-import": (
        {
            "pkg/__init__.py": (
                "class _Fake:\n    @staticmethod\n    def t():\n        return 3\n\n\n"
                "def __getattr__(name):\n    if name == 'sub':\n        return _Fake\n"
                "    raise AttributeError(name)\n"
            ),
            "pkg/sub.py": "def t():\n    return 1\n",
            "use.py": "from pkg import sub\n\n\ndef u():\n    return sub.t()\n",
        },
        ("use.py", "sub.t"),
        "module-getattr",
        "import use; print(use.u())",
        "3 (_Fake.t runs)",
    ),
    "e6-3-getattr-chain": (
        {
            "pkg/__init__.py": (
                "def __getattr__(name):\n    if name == 'sub':\n"
                "        from . import _fast as mod\n        return mod\n"
                "    raise AttributeError(name)\n"
            ),
            "pkg/sub.py": "def t():\n    return 1\n",
            "pkg/_fast.py": "def t():\n    return 3\n",
            "use.py": "import pkg\n\n\ndef u():\n    return pkg.sub.t()\n",
        },
        ("use.py", "pkg.sub.t"),
        "module-getattr",
        "import use; print(use.u())",
        "3 (pkg/_fast.py's t runs)",
    ),
    "e6-3-getattr-import-as": (
        {
            "pkg/__init__.py": (
                "def __getattr__(name):\n    if name == 'sub':\n"
                "        from . import _fast as mod\n        return mod\n"
                "    raise AttributeError(name)\n"
            ),
            "pkg/sub.py": "def t():\n    return 1\n",
            "pkg/_fast.py": "def t():\n    return 3\n",
            "use.py": "import pkg.sub as m\n\n\ndef u():\n    return m.t()\n",
        },
        ("use.py", "m.t"),
        "module-getattr",
        "import use; print(use.u())",
        # Here ``IMPORT_NAME`` loads ``pkg.sub`` first, so CPython runs
        # ``pkg/sub.py``'s ``t`` (prints 1); ruling E6-3 still fails every
        # submodule access through a ``__getattr__`` package closed.
        "1 (pkg/sub.py's t runs; closed by ruling E6-3, not a wrong edge)",
    ),
    # E6-4 (A-5): pytest's ``rootdir`` insertion of an ancestor directory.
    "e6-4-pytest-basedir": (
        {
            "svc.py": SVC,
            "tests/svc.py": "def t():\n    return 2\n",
            "tests/unit/__init__.py": "",
            "tests/unit/test_x.py": (
                "from svc import t\n\n\ndef test_which():\n    return t()\n"
            ),
        },
        ("tests/unit/test_x.py", "t"),
        "script-dir-shadow",
        "pytest -q tests/unit/test_x.py (prepend mode)",
        "tests/svc.py's t runs (pytest inserts tests/)",
    ),
    # E6-6 (B-S2): a write through a chain rooted at the module.
    "e6-6-code-write": (
        {"patch.py": "import svc\n" + PATCHER + "svc.t.__code__ = o.__code__\n"},
        ("use.py", "t"),
        # Fold 3 (N-1): a ``__code__`` write is a run-wide cause first; the
        # E6-6 chain taint still fails ``svc.py``'s own Tier 1 proof.
        "run-tainted:module-object",
        "import patch, use; print(use.u())",
        "2 (other.t's code runs)",
    ),
    # E6-5 (B-S1): a constant patch target naming a whole module.
    "e6-5-patch-multiple": (
        {
            "patch.py": "from unittest import mock\n"
            + PATCHER
            + "mock.patch.multiple('svc', t=o).start()\n"
        },
        ("use.py", "t"),
        "module-escape",
        "import patch, use; print(use.u())",
        "2 (other.t runs)",
    ),
    # S-1: a submodule whose name the collector skips for directories.
    "s-1-skipped-name-submodule": (
        {
            "pkg/__init__.py": "def build():\n    return 1\n",
            "pkg/build.py": "",
            "loader.py": "import pkg.build\n",
            "other.py": "def build():\n    return 2\n",
            "use.py": "from pkg import build\n\n\ndef u():\n    return build()\n",
        },
        ("use.py", "build"),
        "attr-submodule-conflict",
        "import loader, use; print(use.u())",
        "TypeError: 'module' object is not callable (pkg.build is the module)",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD2_BLOCKING))
def test_fold2_blocking_cases_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    """#705 E6-1..E6-6 and S-1: each panel repro, whose CPython 3.14 run is
    recorded in its ``runtime`` field (a function other than the one the
    edge would name runs), keeps its off-mode edge in ``imports`` mode."""
    extra, (file, reference), reason, _driver, _runtime = FOLD2_BLOCKING[case]
    root = _write(tmp_path, {"svc.py": SVC, "use.py": USE, **OTHER, **extra})
    off, structural, on, label = _run(root, file, reference)
    assert off["resolution"] == "ambiguous", case
    assert on == off, case
    assert label == f"none({reason})", case


@pytest.mark.parametrize(
    "case",
    [
        "e6-1-name-write",
        "e6-2-try-except",
        "e6-2-whole-escape",
        "e6-2-star",
        "e6-6-code-write",
        "e6-5-patch-multiple",
    ],
)
def test_fold2_written_module_loses_its_own_tier1_proof(
    tmp_path: Path, case: str
) -> None:
    """The written module's own module-scope proof (``svc.py`` ``run`` ->
    ``t``) fails closed too where ``svc.t`` is written (E6-2, E6-6); for
    E6-1 the written module is ``use.py``, whose ``u`` -> ``t`` is a Tier 2
    proof, so ``svc.py`` stays resolved."""
    extra = FOLD2_BLOCKING[case][0]
    root = _write(tmp_path, {"svc.py": SVC, "use.py": USE, **OTHER, **extra})
    _off, structural, on, _label = _run(root, "svc.py", "t")
    assert structural["resolution"] == "resolved"
    if case == "e6-1-name-write":
        assert on["resolution"] == "resolved"
    else:
        assert on["resolution"] == "ambiguous", case


FOLD2_CONTROLS: dict[str, tuple[dict[str, str], tuple[str, str], str]] = {
    # E6-3: a package binding its own submodule still resolves.
    "own-submodule-import": (
        {
            "a/__init__.py": "from . import b\n",
            "a/b.py": "def t():\n    return 1\n",
            "use.py": "import a.b as m\n\n\ndef u():\n    return m.t()\n",
        },
        ("use.py", "m.t"),
        "a/b.py",
    ),
    # E6-4: a production importer below the root only shadows its own dir.
    "production-importer-below-root": (
        {
            "src/__init__.py": "",
            "src/app/__init__.py": "",
            "src/app/main.py": "from svc import t\n\n\ndef u():\n    return t()\n",
            "src/svc.py": "def t():\n    return 2\n",
        },
        ("src/app/main.py", "t"),
        "svc.py",
    ),
    # E6-7: plain reads of safe dunders are no escape.
    "safe-dunder-reads": (
        {
            "w.py": (
                "import svc\n\nINFO = (svc.__file__, svc.__name__, svc.__spec__, "
                "svc.__doc__)\n"
            )
        },
        ("use.py", "t"),
        "svc.py",
    ),
    # E6-5: an HTTP client's ``.patch(url)`` is no patcher.
    "http-patch-is-no-patcher": (
        {"w.py": "import requests\n\n\ndef f(url):\n    return requests.patch(url)\n"},
        ("use.py", "t"),
        "svc.py",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD2_CONTROLS))
def test_fold2_controls_still_resolve(tmp_path: Path, case: str) -> None:
    extra, (file, reference), target = FOLD2_CONTROLS[case]
    root = _write(tmp_path, {"svc.py": SVC, "use.py": USE, **OTHER, **extra})
    _off, _structural, on, label = _run(root, file, reference)
    assert on["resolution"] == "resolved", (case, label)
    assert _target(on, root) == target


def test_fold2_package_path_read_keeps_the_packages_own_proofs(
    tmp_path: Path,
) -> None:
    """E6-7: a read of ``pkg.__path__`` is a ``module-system`` cause (Tier 2
    off) but no escape: ``pkg/__init__.py``'s own Tier 1 proof stays."""
    root = _write(
        tmp_path,
        {
            "pkg/__init__.py": SVC,
            **OTHER,
            "w.py": "import pkg\n\nWHERE = list(pkg.__path__)\n",
        },
    )
    _off, structural, on, _label = _run(root, "pkg/__init__.py", "t")
    assert structural["resolution"] == "resolved"
    assert on["resolution"] == "resolved"


FOLD2_CAUSES: dict[str, tuple[dict[str, str], str, str]] = {
    # E6-5 (A-6): computed patcher targets, scoped to test callers by O-2.
    "computed-patch": (
        {
            "tests/test_b.py": (
                "from unittest import mock\n\nNAME = 't'\n\n\ndef test_go():\n"
                "    with mock.patch(f'svc.{NAME}', len):\n        pass\n"
            )
        },
        "tests/calls.py",
        "unresolvable-writer",
    ),
    "computed-monkeypatch": (
        {
            "tests/test_m.py": "def test_m(monkeypatch, n):\n    monkeypatch.setattr(n, len)\n"
        },
        "tests/calls.py",
        "unresolvable-writer",
    ),
    "computed-patch-object": (
        {
            "tests/test_o.py": (
                "from unittest import mock\nimport svc\n\n\ndef test_o(n):\n"
                "    mock.patch.object(svc, n)\n"
            )
        },
        "tests/calls.py",
        "unresolvable-writer",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD2_CAUSES))
def test_fold2_computed_patcher_targets_are_test_scoped_causes(
    tmp_path: Path, case: str
) -> None:
    """E6-5 (A-6, CPython 3.14 under pytest: ``tests/calls.py`` ``go`` runs
    ``other.t`` while patched): a computed target is an
    ``unresolvable-writer`` for test callers; production callers keep their
    proof (O-2)."""
    extra, test_caller, cause = FOLD2_CAUSES[case]
    root = _write(
        tmp_path,
        {
            "svc.py": SVC,
            "use.py": USE,
            **OTHER,
            test_caller: "import svc\n\n\ndef go():\n    return svc.t()\n",
            **extra,
        },
    )
    off, _structural, on, label = _run(root, test_caller, "svc.t")
    assert on == off
    assert label == f"none(run-tainted:{cause})"
    _off, _structural, on, label = _run(root, "use.py", "t")
    assert on["resolution"] == "resolved" and label == "import"


def test_fold2_structural_facts_carry_no_tier2_tables(tmp_path: Path) -> None:
    """E6-8: the Python module facts are computed only in ``imports`` mode;
    ``structural`` facts carry empty tables (as on main), and an ``imports``
    assembly fed facts without them fails closed (``unparsed-file``)."""
    root = _write(tmp_path, {"svc.py": SVC, "use.py": USE, **OTHER})
    files = collect_source_files(root, None)
    structural = [
        extract_symbol_facts_for_file(path, root, None, call_resolution="structural")
        for path in files
    ]
    imports = [
        extract_symbol_facts_for_file(path, root, None, call_resolution=MODE)
        for path in files
    ]
    for item in structural:
        assert item["scope_facts"]["exports"] == {}
        assert item["scope_facts"]["module_bindings"] == {}
        assert valid_scope_facts(item["scope_facts"], item["language"])
    assert all(item["scope_facts"]["module_bindings"] for item in imports)
    for left, right in zip(structural, imports, strict=True):
        assert left["scope_facts"]["bindings"] == right["scope_facts"]["bindings"]
    run = py_modules.build_py_module_run(structural, False)
    assert run.shutoff.get("unparsed-file")


FOLD2_MUTATION_GAPS: dict[str, tuple[dict[str, str | bytes], str, str]] = {
    # Panel B's surviving extra mutations (S3), each pinned here.
    "string-module-object-names": (
        {"w.py": "def f(o):\n    return getattr(o, '__globals__')\n"},
        "t",
        "run-tainted:module-object",
    ),
    "string-f-locals": (
        {"w.py": "def f(fr):\n    return getattr(fr, 'f_locals')\n"},
        "t",
        "run-tainted:module-object",
    ),
    "main-string": ({"w.py": "WHO = '__main__'\n"}, "t", "run-tainted:module-object"),
    "sys-dunder": (
        {"w.py": "import sys\n\nD = sys.__dict__\n"},
        "t",
        "run-tainted:module-system",
    ),
    "pydoc-locate": (
        {"w.py": "import pydoc\n\n\ndef f(n):\n    return pydoc.locate(n)\n"},
        "t",
        "run-tainted:dynamic-loader",
    ),
    "pydoc-importfile": (
        {"w.py": "import pydoc\n\n\ndef f(p):\n    return pydoc.importfile(p)\n"},
        "t",
        "run-tainted:dynamic-loader",
    ),
    "pkgutil-get-loader": (
        {"w.py": "import pkgutil\n\n\ndef f(n):\n    return pkgutil.get_loader(n)\n"},
        "t",
        "run-tainted:dynamic-loader",
    ),
    "logging-config-importer": (
        {
            "w.py": (
                "import logging.config\n\n\ndef f(n):\n"
                "    return logging.config._importer(n)\n"
            )
        },
        "t",
        "run-tainted:dynamic-loader",
    ),
    "resolver-identifier": (
        {"w.py": "def f(g, x):\n    resolve_name = g\n    return resolve_name(x)\n"},
        "t",
        "run-tainted:dynamic-loader",
    ),
    "relative-import-module": (
        {
            "pkg/__init__.py": "",
            "pkg/x.py": SVC,
            "use.py": "from pkg.x import t\n\n\ndef u():\n    return t()\n",
            "w.py": "import importlib\n\nM = importlib.import_module('.x', 'pkg')\n",
        },
        "t",
        "module-escape",
    ),
    "dunder-import-head": (
        {
            "a/__init__.py": SVC,
            "a/b.py": "",
            "use.py": "from a import t\n\n\ndef u():\n    return t()\n",
            "w.py": "A = __import__('a.b')\n",
        },
        "t",
        "module-escape",
    ),
    "comparison-escape": (
        {"w.py": "import svc\n\nSAME = svc == 1\n"},
        "t",
        "module-escape",
    ),
    "promotion-through-a-string": (
        {
            "app.py": "TARGET = 'tests.helpers.f'\n",
            "tests/__init__.py": "",
            "tests/helpers.py": "def f(s):\n    exec(s)\n",
        },
        "t",
        "run-tainted:evaluator",
    ),
    "promotion-through-an-acquisition": (
        {
            "app.py": "import importlib\n\nH = importlib.import_module('tests.helpers')\n",
            "tests/__init__.py": "",
            "tests/helpers.py": "def f(s):\n    exec(s)\n",
        },
        "t",
        "run-tainted:evaluator",
    ),
    "promotion-through-a-patch-target": (
        {
            # A one-component constant patcher target is a taint only (no
            # import edge, no dotted string): ``patch.multiple`` imports
            # ``test_helpers`` in production, so it is production.
            "app.py": (
                "from unittest import mock\n\n"
                "P = mock.patch.multiple('test_helpers', f=len)\n"
            ),
            "test_helpers.py": "def f(s):\n    exec(s)\n",
        },
        "t",
        "run-tainted:evaluator",
    ),
    "coding-second-line": (
        {"w.py": b"#!/usr/bin/env python\n# coding: latin-1\nx = 1\n"},
        "t",
        "run-tainted:unparsed-file",
    ),
    "ctrl-z": ({"w.py": b"x = 1\n# \x1a\n"}, "t", "run-tainted:unparsed-file"),
    "missing-name-of-a-dynamic-module": (
        {
            "svc.py": "G = globals()\n",
            "a.py": SVC,
            "b.py": "def t():\n    return 3\n",
        },
        "t",
        "dynamic-scope",
    ),
    "submodule-of-a-dynamic-package": (
        {
            "pkg/__init__.py": "G = globals()\n",
            "pkg/sub.py": SVC,
            "use.py": "from pkg import sub\n\n\ndef u():\n    return sub.t()\n",
        },
        "sub.t",
        "dynamic-scope",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD2_MUTATION_GAPS))
def test_fold2_rules_each_have_a_failing_case(tmp_path: Path, case: str) -> None:
    """Panel B's 20 surviving mutations (#705 S3): every rule they disabled
    now has a case that changes when the rule is removed."""
    extra, reference, label_reason = FOLD2_MUTATION_GAPS[case]
    root = _write(tmp_path, {"svc.py": SVC, "use.py": USE, **OTHER, **extra})
    off, _structural, on, label = _run(root, "use.py", reference)
    assert on == off, case
    assert label == f"none({label_reason})", case


def test_fold2_python2_exec_statement_is_an_evaluator(tmp_path: Path) -> None:
    """The Python 2 ``exec`` statement the grammar accepts is an evaluator,
    or the file does not parse; either way Tier 2 is off."""
    root = _write(
        tmp_path, {"svc.py": SVC, "use.py": USE, **OTHER, "w.py": 'exec "x = 1"\n'}
    )
    off, _structural, on, label = _run(root, "use.py", "t")
    assert on == off
    assert label in (
        "none(run-tainted:evaluator)",
        "none(run-tainted:unparsed-file)",
    )


def test_fold2_init_definition_shadowed_by_a_submodule(tmp_path: Path) -> None:
    """E6-1 (A-4), Tier 1 side: in ``imports`` mode a package ``__init__``'s
    own proof of ``tool`` fails closed when ``pkg/tool.py`` exists, because
    importing ``pkg.tool`` anywhere sets the package global ``tool`` to the
    submodule (CPython 3.14: after ``import pkg.tool``, ``pkg.tool`` is the
    module and ``pkg.run()`` raises ``TypeError``)."""
    root = _write(
        tmp_path,
        {
            "pkg/__init__.py": "def tool():\n    return 1\n\n\ndef run():\n    return tool()\n",
            "pkg/tool.py": "",
            "other.py": "def tool():\n    return 2\n",
        },
    )
    off, structural, on, label = _run(root, "pkg/__init__.py", "tool")
    assert structural["resolution"] == "resolved"
    assert on == off
    assert label == "none(attr-submodule-conflict)"


# ---------------------------------------------------------------------------
# Fold 3 (#705 P6-1..P6-4, N-1): the president's trees at fold 2, verbatim
# (``pr6-705-review/president/cases/<id>/tree``). ``runtime`` is what CPython
# 3.14.10 printed for ``python -B -E -s main.py`` in the tree, or, for a test
# tree, ``python -B -E -s -m pytest -q -s -p no:cacheprovider --rootdir=.
# tests``: in every row a function other than the one the ``imports`` edge
# named at fold 2 runs. ``(files, (file, reference), reason, runtime)``.

_CALLS = "import svc\ndef go(): return svc.t()\n"
_SVC_OTHER = {
    "svc.py": 'def t(): return "SVC.t"\n',
    "other.py": 'def t(): return "OTHER.t"\n',
    "tests/calls.py": _CALLS,
}
FOLD3_BLOCKING: dict[str, tuple[dict[str, str], tuple[str, str], str, str]] = {
    # P6-1: an absolute import from another package whose last component has
    # the package's own name is no own-submodule import.
    "h1_own_sub_lastpart": (
        {
            "a/__init__.py": "from x.a import b\n",
            "a/b.py": 'def t(): return "A.B.t (own submodule)"\n',
            "x/__init__.py": "",
            "x/a/__init__.py": "",
            "x/a/b.py": 'def t(): return "X.A.B.t"\n',
            "main.py": 'from a import b\ndef go(): return b.t()\nprint("RAN", go())\n',
        },
        ("main.py", "b.t"),
        "attr-submodule-conflict",
        "RAN X.A.B.t",
    ),
    "h10_django_like": (
        {
            "vendor/__init__.py": "",
            "vendor/utils/__init__.py": "",
            "vendor/utils/timezone.py": 'def now(): return "VENDOR timezone.now"\n',
            "myapp/__init__.py": "",
            "myapp/utils/__init__.py": "from vendor.utils import timezone\n",
            "myapp/utils/timezone.py": 'def now(): return "MYAPP timezone.now"\n',
            "main.py": (
                "from myapp.utils import timezone\n"
                "def go(): return timezone.now()\n"
                'print("RAN", go())\n'
            ),
        },
        ("main.py", "timezone.now"),
        "attr-submodule-conflict",
        "RAN VENDOR timezone.now",
    ),
    # P6-2: a star import after ``from . import b`` rebinds ``b``.
    "h9_star_rebind": (
        {
            "a/__init__.py": "from . import b\nfrom .c import *\n",
            "a/b.py": 'def t(): return "A.B.t (submodule)"\n',
            "a/c.py": (
                "class Impl:\n    @staticmethod\n"
                '    def t(): return "C.Impl.t (class)"\nb = Impl\n'
            ),
            "decoy.py": 'def t(): return "DECOY"\n',
            "main.py": 'from a import b\ndef go(): return b.t()\nprint("RAN", go())\n',
        },
        ("main.py", "b.t"),
        "attr-submodule-conflict",
        "RAN C.Impl.t (class)",
    ),
    # P6-3: the W-3 spellings of ``patch`` and ``monkeypatch``.
    "h3a_mock_alias": (
        {
            **_SVC_OTHER,
            "tests/test_b.py": (
                "from unittest import mock as m\nimport calls\n"
                'from other import t as _evil\nNAME = "t"\ndef test_go():\n'
                '    with m.patch(f"svc.{NAME}", _evil):\n'
                '        print("RAN", calls.go())\n'
            ),
        },
        ("tests/calls.py", "svc.t"),
        "run-tainted:unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    "h3b_patch_alias": (
        {
            **_SVC_OTHER,
            "tests/test_b.py": (
                "from unittest.mock import patch as p\nimport calls\n"
                'from other import t as _evil\nNAME = "t"\ndef test_go():\n'
                '    with p(f"svc.{NAME}", _evil):\n'
                '        print("RAN", calls.go())\n'
            ),
        },
        ("tests/calls.py", "svc.t"),
        "run-tainted:unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    "h3c_multiple_computed": (
        {
            **_SVC_OTHER,
            "tests/test_b.py": (
                "from unittest import mock\nimport calls\n"
                'from other import t as _evil\nMOD = "s" + "vc"\ndef test_go():\n'
                "    with mock.patch.multiple(MOD, t=_evil):\n"
                '        print("RAN", calls.go())\n'
            ),
        },
        ("tests/calls.py", "svc.t"),
        "run-tainted:unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    "h6_mp_alias": (
        {
            **_SVC_OTHER,
            "tests/test_b.py": (
                'import calls\nfrom other import t as _evil\nNAME = "t"\n'
                "def test_go(monkeypatch):\n    mp = monkeypatch\n"
                '    mp.setattr(f"svc.{NAME}", _evil)\n'
                '    print("RAN", calls.go())\n'
            ),
        },
        ("tests/calls.py", "svc.t"),
        "run-tainted:unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    # P6-4: ``tests/conftest.py``'s basedir ``tests/`` is on ``sys.path``
    # before the test module in ``tests/unit/`` imports ``helpers``.
    "h4_conftest_basedir": (
        {
            "helpers.py": 'def h(): return "ROOT helpers.h"\n',
            "tests/conftest.py": "",
            "tests/helpers.py": 'def h(): return "TESTS helpers.h"\n',
            "tests/unit/test_x.py": (
                'from helpers import h\ndef test_which(): print("RAN", h())\n'
            ),
        },
        ("tests/unit/test_x.py", "h"),
        "script-dir-shadow",
        "RAN TESTS helpers.h / 1 passed",
    ),
    # N-1: code-object surgery through a local alias in another file.
    "h5_code_alias": (
        {
            "svc.py": 'def t(): return "SVC.t"\n',
            "other.py": 'def t(): return "OTHER.t"\n',
            "patch.py": "import svc, other\nf = svc.t\nf.__code__ = other.t.__code__\n",
            "use.py": "from svc import t\ndef u(): return t()\n",
            "main.py": 'import patch, use\nprint("RAN", use.u())\n',
        },
        ("use.py", "t"),
        "run-tainted:module-object",
        "RAN OTHER.t",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD3_BLOCKING))
def test_fold3_president_cases_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    """#705 P6-1..P6-4 and N-1: each president's tree, whose CPython 3.14 or
    pytest run is recorded in its ``runtime`` field, keeps its off-mode edge
    in ``imports`` mode with the recorded reason.

    - P6-1 (``h1``, ``h10``): ``from vendor.utils import timezone`` in
      ``myapp/utils/__init__.py`` binds the vendor module; the later ``from
      myapp.utils import timezone`` finds that attribute and
      ``_handle_fromlist`` never loads ``myapp/utils/timezone.py``.
    - P6-2 (``h9``): ``from .c import *`` after ``from . import b`` rebinds
      ``b`` to ``c.Impl``; ``a.b`` already in ``sys.modules`` is never set
      again.
    - P6-3 (``h3a``, ``h3b``, ``h3c``, ``h6``): ``m.patch``, ``p(...)``,
      ``patch.multiple(MOD, ...)`` and ``mp.setattr`` replace ``svc.t`` for
      the duration of the test, so ``calls.go`` runs ``other.t``.
    - P6-4 (``h4``): pytest's ``prepend`` mode inserted ``tests/`` (the
      conftest's basedir) and then ``tests/unit/``; ``helpers`` is found in
      ``tests/``.
    - N-1 (``h5``): the assigned ``__code__`` runs ``other.t``'s body under
      ``svc.t``'s name.
    """
    files, (file, reference), reason, _runtime = FOLD3_BLOCKING[case]
    root = _write(tmp_path, files)
    off, _structural, on, label = _run(root, file, reference)
    assert off["resolution"] in ("ambiguous", "resolved"), case
    assert on == off, case
    assert label == f"none({reason})", case


FOLD3_CONTROLS: dict[str, tuple[dict[str, str], tuple[str, str], str]] = {
    # P6-4 control (pytest: ``RAN ROOT helpers.h``): no conftest, so only the
    # test's own basedir ``tests/unit/`` is inserted; ``helpers`` resolves to
    # the root's, as before fold 3.
    "h4b_no_conftest_control": (
        {
            "helpers.py": 'def h(): return "ROOT helpers.h"\n',
            "tests/helpers.py": 'def h(): return "TESTS helpers.h"\n',
            "tests/unit/test_x.py": (
                'from helpers import h\ndef test_which(): print("RAN", h())\n'
            ),
        },
        ("tests/unit/test_x.py", "h"),
        "helpers.py",
    ),
    # P6-3 control: ``requests.patch(url)`` is an HTTP call, no patcher, even
    # with a computed argument.
    "requests-patch-control": (
        {
            **_SVC_OTHER,
            "tests/test_b.py": (
                'import requests\nimport calls\nNAME = "t"\ndef test_go():\n'
                '    requests.patch(f"http://h/{NAME}")\n'
                '    print("RAN", calls.go())\n'
            ),
        },
        ("tests/calls.py", "svc.t"),
        "svc.py",
    ),
    # P6-1 control: the absolute self-import is the package's own submodule.
    "absolute-self-import": (
        {
            "myapp/__init__.py": "",
            "myapp/utils/__init__.py": "from myapp.utils import timezone\n",
            "myapp/utils/timezone.py": "def now():\n    return 1\n",
            "other.py": "def now():\n    return 2\n",
            "main.py": "from myapp.utils import timezone\n\n\ndef go():\n    return timezone.now()\n",
        },
        ("main.py", "timezone.now"),
        "myapp/utils/timezone.py",
    ),
    # P6-1 control: the relative form, as before.
    "relative-own-import": (
        {
            "a/__init__.py": "from . import b\n",
            "a/b.py": "def t():\n    return 1\n",
            "other.py": "def t():\n    return 2\n",
            "main.py": "from a import b\n\n\ndef go():\n    return b.t()\n",
        },
        ("main.py", "b.t"),
        "a/b.py",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD3_CONTROLS))
def test_fold3_controls_still_resolve(tmp_path: Path, case: str) -> None:
    files, (file, reference), target = FOLD3_CONTROLS[case]
    root = _write(tmp_path, files)
    _off, _structural, on, label = _run(root, file, reference)
    assert on["resolution"] == "resolved", (case, label)
    assert label == "import", case
    assert _target(on, root) == target


def test_fold3_patcher_causes_stay_test_scoped(tmp_path: Path) -> None:
    """P6-3 under O-2: the aliased patchers are causes for test callers only;
    a production caller of ``svc.t`` keeps its proof."""
    files = dict(FOLD3_BLOCKING["h3a_mock_alias"][0])
    files["use.py"] = "from svc import t\n\n\ndef u():\n    return t()\n"
    root = _write(tmp_path, files)
    _off, _structural, on, label = _run(root, "use.py", "t")
    assert on["resolution"] == "resolved" and label == "import"


def test_fold3_star_init_has_no_own_submodules(tmp_path: Path) -> None:
    """P6-2 at the fact level: an ``__init__.py`` with a star import records
    no own-submodule names, and one without records its relative import."""
    root = _write(
        tmp_path,
        {
            "a/__init__.py": "from . import b\nfrom .c import *\n",
            "a/b.py": "",
            "a/c.py": "",
            "k/__init__.py": "from . import b\n",
            "k/b.py": "",
        },
    )
    facts, _graph, _context_ = _context(root)
    own = {
        item["path"]: item["scope_facts"]["module_bindings"]["own_submodules"]
        for item in facts
        if item["path"].endswith("__init__.py")
    }
    assert own == {"a/__init__.py": [], "k/__init__.py": ["b"]}


@pytest.mark.parametrize(
    "writer",
    [
        "def f(g, h):\n    g.__code__ = h.__code__\n",
        "def f(g, h):\n    setattr(g, '__code__', h.__code__)\n",
        "def f(g):\n    g.__defaults__ = (2,)\n",
        "def f(g):\n    g.__kwdefaults__ = {}\n",
        "def f(g):\n    del g.__closure__\n",
    ],
)
def test_fold3_function_code_writes_are_a_cause(tmp_path: Path, writer: str) -> None:
    """#705 N-1: a write of a function's ``__code__``, ``__closure__``,
    ``__defaults__`` or ``__kwdefaults__`` in any file, through any receiver
    (a parameter, a local alias as in ``h5_code_alias``) or by constant name,
    is a run-wide ``module-object`` cause: the proven definition may run other
    code (CPython 3.14 ran ``OTHER.t`` for ``h5``)."""
    root = _write(tmp_path, {"svc.py": SVC, "use.py": USE, **OTHER, "w.py": writer})
    off, _structural, on, label = _run(root, "use.py", "t")
    assert on == off
    assert label == "none(run-tainted:module-object)"


def test_fold3_star_init_rejects_recorded_own_submodules(tmp_path: Path) -> None:
    """#705 P6-2, assembly side: even a fact record that lists ``b`` as an
    own submodule of a package whose ``__init__.py`` has a star import is not
    trusted (``h9_star_rebind`` ran ``C.Impl.t``)."""
    root = _write(tmp_path, FOLD3_BLOCKING["h9_star_rebind"][0])
    facts, _graph, _context_ = _context(root)
    for item in facts:
        if item["path"] == "a/__init__.py":
            item["scope_facts"]["module_bindings"]["own_submodules"] = ["b"]
    run = py_modules.build_py_module_run(facts)
    binding = {"form": "from", "module": "a", "name": "b", "bound": "b"}
    outcome = py_modules.resolve_import(run, "main.py", binding, ["t"])
    assert outcome == {"outcome": "none", "reason": "attr-submodule-conflict"}


def test_fold3_conftest_basedir_reaches_the_writer_side(tmp_path: Path) -> None:
    """#705 P6-4, writer side: ``import helpers; helpers.h = o`` in
    ``tests/unit/test_w.py`` writes ``tests/helpers.py`` when
    ``tests/conftest.py`` exists (pytest on CPython 3.14: ``tests/`` is on
    ``sys.path`` first, ``helpers.run()`` returns 2), so that file's own
    Tier 1 proof of ``h`` fails closed for test callers."""
    root = _write(
        tmp_path,
        {
            "helpers.py": "def h():\n    return 0\n",
            "tests/conftest.py": "",
            "tests/helpers.py": "def h():\n    return 1\n\n\ndef run():\n    return h()\n",
            "tests/unit/test_w.py": (
                "import helpers\nfrom other import t as o\n\n\n"
                "def test_w():\n    helpers.h = o\n    assert helpers.run() == 2\n"
            ),
            **OTHER,
        },
    )
    _off, structural, on, label = _run(root, "tests/helpers.py", "h")
    assert structural["resolution"] == "resolved"
    assert on["resolution"] != "resolved"
    assert label == "none(reassigned)"


# ---------------------------------------------------------------------------
# Fold 4 (#705 E6-9: P6-5, P6-6, P6-7): the president's ``f3_*`` trees,
# verbatim (``tests/test_b.py``; ``svc.py``, ``other.py`` and
# ``tests/calls.py`` as in ``_SVC_OTHER``). ``runtime`` is what pytest
# printed on CPython 3.14.10 (``python -B -E -s -m pytest -q -s -p
# no:cacheprovider --rootdir=. tests``): ``tests/calls.py``'s ``go`` ran
# ``other.t`` in every tree, while fold 3 resolved ``svc.t`` to ``svc.py``.

_F3_HEAD = 'import calls\nfrom other import t as _evil\nNAME = "t"\n'
FOLD4_BLOCKING: dict[str, tuple[str, str]] = {
    # P6-5: a patcher handed on as a value.
    "f3_patch_as_arg": (
        "from unittest.mock import patch\n" + _F3_HEAD + "def run(p):\n"
        '    with p(f"svc.{NAME}", _evil):\n'
        "        return calls.go()\n"
        "def test_go():\n"
        '    print("RAN", run(patch))\n',
        "RAN OTHER.t / 1 passed",
    ),
    "f3_patch_decorator_arg": (
        "from unittest import mock\n" + _F3_HEAD + "def deco(patcher):\n"
        "    def wrap(fn):\n"
        "        def inner():\n"
        '            with patcher(f"svc.{NAME}", _evil):\n'
        "                return fn()\n"
        "        return inner\n"
        "    return wrap\n"
        "@deco(mock.patch)\n"
        "def test_go():\n"
        '    print("RAN", calls.go())\n',
        "RAN OTHER.t / 1 passed",
    ),
    "f3_patch_list_escape": (
        "from unittest import mock\n" + _F3_HEAD + "PATCHERS = [mock.patch]\n"
        "def test_go():\n"
        '    with PATCHERS[0](f"svc.{NAME}", _evil):\n'
        '        print("RAN", calls.go())\n',
        "RAN OTHER.t / 1 passed",
    ),
    "f3_patch_partial": (
        "import functools\nfrom unittest.mock import patch\n"
        + _F3_HEAD
        + 'pp = functools.partial(patch, f"svc.{NAME}")\n'
        "def test_go():\n"
        "    with pp(_evil):\n"
        '        print("RAN", calls.go())\n',
        "RAN OTHER.t / 1 passed",
    ),
    "f3_mp_param": (
        _F3_HEAD + "def helper(mp):\n"
        '    mp.setattr(f"svc.{NAME}", _evil)\n'
        "def test_go(monkeypatch):\n"
        "    helper(monkeypatch)\n"
        '    print("RAN", calls.go())\n',
        "RAN OTHER.t / 1 passed",
    ),
    # P6-6: ``MonkeyPatch`` imported under an alias.
    "f3_mp_from_import": (
        "from pytest import MonkeyPatch as MP\n" + _F3_HEAD + "def test_go():\n"
        "    m = MP()\n"
        '    m.setattr(f"svc.{NAME}", _evil)\n'
        '    print("RAN", calls.go())\n'
        "    m.undo()\n",
        "RAN OTHER.t / 1 passed",
    ),
    # P6-7: a patcher fixture fetched by constant name.
    "f3_mp_getfixture": (
        _F3_HEAD + "def test_go(request):\n"
        '    mp = request.getfixturevalue("monkeypatch")\n'
        '    mp.setattr(f"svc.{NAME}", _evil)\n'
        '    print("RAN", calls.go())\n',
        "RAN OTHER.t / 1 passed",
    ),
    # P6-7: a pytest-mock fixture fetched by name; its ``.patch`` is
    # ``unittest.mock.patch`` (pytest-mock is not installed in the measuring
    # venv, so this row records the rule, not a pytest run).
    "getfixturevalue-mocker": (
        _F3_HEAD + "def test_go(request):\n"
        '    m = request.getfixturevalue("mocker")\n'
        '    m.patch(f"svc.{NAME}", _evil)\n'
        '    print("RAN", calls.go())\n',
        "(pytest-mock: mocker.patch is unittest.mock.patch)",
    ),
    # P6-7: a computed fixture name may fetch any patcher.
    "computed-getfixturevalue": (
        _F3_HEAD + 'FIX = "monkey" + "patch"\n'
        "def test_go(request):\n"
        "    request.getfixturevalue(FIX).setenv('X', '1')\n"
        '    print("RAN", calls.go())\n',
        "(no patch; the cause is the computed fixture name)",
    ),
}


def _fold4_root(tmp_path: Path, test_file: str) -> Path:
    return _write(
        tmp_path,
        {
            **_SVC_OTHER,
            "use.py": "from svc import t\n\n\ndef u():\n    return t()\n",
            "tests/test_b.py": test_file,
        },
    )


@pytest.mark.parametrize("case", sorted(FOLD4_BLOCKING))
def test_fold4_patcher_values_are_test_scoped_causes(tmp_path: Path, case: str) -> None:
    """#705 E6-9. P6-5 (``f3_patch_as_arg``, ``f3_patch_decorator_arg``,
    ``f3_patch_list_escape``, ``f3_patch_partial``, ``f3_mp_param``): a
    patcher used off the E-21 closed allow-list (an argument, a decorator
    argument, a container element, ``functools.partial``) is applied by a
    call the rules cannot see. P6-6 (``f3_mp_from_import``): ``MP()`` for
    ``from pytest import MonkeyPatch as MP`` is a ``MonkeyPatch``. P6-7:
    ``request.getfixturevalue("monkeypatch")`` is one, and a computed fixture
    name may be any patcher. In every president's tree pytest printed ``RAN
    OTHER.t``. Test callers get ``unresolvable-writer``; the production
    caller ``use.py`` keeps its proof (O-2)."""
    test_file, _runtime = FOLD4_BLOCKING[case]
    root = _fold4_root(tmp_path, test_file)
    off, _structural, on, label = _run(root, "tests/calls.py", "svc.t")
    assert on == off, case
    assert label == "none(run-tainted:unresolvable-writer)", case
    _off, _structural, on, label = _run(root, "use.py", "t")
    assert on["resolution"] == "resolved" and label == "import", case


FOLD4_CONTROLS: dict[str, tuple[str, str]] = {
    # The object form takes the module as an argument: today's whole-module
    # escape of ``svc`` for test callers, no cause.
    "monkeypatch-setattr-object": (
        "import svc\nfrom other import t as _evil\n"
        "def test_go(monkeypatch):\n    monkeypatch.setattr(svc, 't', _evil)\n",
        "module-escape",
    ),
    # A constant target: today's taint of ``svc.t`` (the dotted string).
    "mock-patch-constant": (
        "from unittest import mock\nfrom other import t as _evil\n"
        "def test_go():\n    with mock.patch('svc.t', _evil):\n        pass\n",
        "reassigned",
    ),
    # Every allow-listed use at once, with a constant target.
    "allow-listed-uses": (
        "import pytest\nfrom unittest import mock\nfrom pytest import MonkeyPatch\n"
        "from other import t as _evil\n"
        "def test_go(monkeypatch: pytest.MonkeyPatch, mocker):\n"
        "    monkeypatch.setenv('X', '1')\n"
        "    with monkeypatch.context() as m:\n"
        "        m.setattr('svc.t', _evil)\n"
        "    mp = MonkeyPatch()\n    mp.undo()\n"
        "    mocker.patch('svc.t', _evil)\n"
        "    mock.MagicMock()\n",
        "reassigned",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD4_CONTROLS))
def test_fold4_allow_listed_patcher_uses_keep_their_exact_taints(
    tmp_path: Path, case: str
) -> None:
    """E6-9 controls: allowed patcher uses with constant targets (or the
    module as an object) keep today's exact taint, and no cause."""
    test_file, reason = FOLD4_CONTROLS[case]
    root = _fold4_root(tmp_path, test_file)
    facts, _graph, _context_ = _context(root)
    (item,) = [item for item in facts if item["path"] == "tests/test_b.py"]
    assert item["scope_facts"]["module_bindings"]["shutoff"] == [], case
    _off, _structural, on, label = _run(root, "tests/calls.py", "svc.t")
    assert label == f"none({reason})", case
    _off, _structural, on, label = _run(root, "use.py", "t")
    assert on["resolution"] == "resolved" and label == "import", case


# ---------------------------------------------------------------------------
# Fold 5 (#705 P6-10..P6-15; executive ruling E6-9a): the president's ``f4_*``
# trees, verbatim apart from ``svc.py``/``other.py``/``tests/calls.py`` (as in
# ``_SVC_OTHER``). ``runtime`` is what CPython 3.14.10 printed: ``python -B -E
# -s -m pytest -q -s -p no:cacheprovider --rootdir=. tests`` for a test tree,
# ``python -B -E -s main.py`` for a production one. In every row a function
# other than the one fold 4's ``imports`` edge named ran.
# ``(extra files, (file, reference), reason, runtime)``.

_F4_HEAD = 'import calls\nfrom other import t as _evil\nNAME = "t"\n'
_F4_MAIN = 'import app\nimport svc\ndef go(): return svc.t()\nprint("RAN", go())\n'
FOLD5_BLOCKING: dict[str, tuple[dict[str, str], tuple[str, str], str, str]] = {
    # P6-10: ``syspath_prepend`` writes ``sys.path``.
    "f4_mp_syspath_prepend": (
        {
            "shadow/svc.py": 'def t(): return "SHADOW.t"\n',
            "tests/test_b.py": (
                "import os\ndef test_go(monkeypatch):\n"
                '    monkeypatch.syspath_prepend(os.path.join(os.path.dirname(__file__), "..", "shadow"))\n'
                '    import calls\n    print("RAN", calls.go())\n'
            ),
        },
        ("tests/calls.py", "svc.t"),
        "run-tainted:module-system",
        "RAN SHADOW.t / 1 passed",
    ),
    # P6-11: a module-level MonkeyPatch another file imports.
    "f4_mp_global_cross": (
        {
            "tests/helpers_mp.py": "import pytest\nMP = pytest.MonkeyPatch()\n",
            "tests/test_b.py": (
                "import calls\nfrom helpers_mp import MP\nfrom other import t as _evil\n"
                'NAME = "t"\ndef test_go():\n    MP.setattr(f"svc.{NAME}", _evil)\n'
                '    print("RAN", calls.go())\n    MP.undo()\n'
            ),
        },
        ("tests/calls.py", "svc.t"),
        "run-tainted:unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    "f4_mp_global_attr": (
        {
            "tests/helpers_mp.py": "import pytest\nMP = pytest.MonkeyPatch()\n",
            "tests/test_b.py": (
                "import calls\nimport helpers_mp\nfrom other import t as _evil\n"
                'NAME = "t"\ndef test_go():\n'
                '    helpers_mp.MP.setattr(f"svc.{NAME}", _evil)\n'
                '    print("RAN", calls.go())\n    helpers_mp.MP.undo()\n'
            ),
        },
        ("tests/calls.py", "svc.t"),
        "run-tainted:unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    # P6-12 and P6-15: ``getfixturevalue`` reached without a direct call.
    "f4_mp_getfixture_alias": (
        {
            "tests/test_b.py": _F4_HEAD
            + "def test_go(request):\n    g = request.getfixturevalue\n"
            '    mp = g("monkeypatch")\n    mp.setattr(f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n'
        },
        ("tests/calls.py", "svc.t"),
        "run-tainted:unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    "f4_mp_getattr_method": (
        {
            "tests/test_b.py": _F4_HEAD + "def test_go(request):\n"
            '    mp = getattr(request, "getfixturevalue")("monkeypatch")\n'
            '    mp.setattr(f"svc.{NAME}", _evil)\n    print("RAN", calls.go())\n'
        },
        ("tests/calls.py", "svc.t"),
        "run-tainted:unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    # P6-13 (E6-9a): production hand-offs reach production callers.
    "f4_prod_patch_param": (
        {
            "app.py": (
                "from unittest.mock import patch\nfrom other import t as _evil\n"
                'NAME = "t"\ndef run(p):\n    p(f"svc.{NAME}", _evil).start()\n'
                "run(patch)\n"
            ),
            "main.py": _F4_MAIN,
        },
        ("main.py", "svc.t"),
        "run-tainted:unresolvable-writer",
        "RAN OTHER.t",
    ),
    "f4_prod_mp_param": (
        {
            "app.py": (
                "import pytest\nfrom other import t as _evil\n"
                'NAME = "t"\ndef helper(mp):\n    mp.setattr(f"svc.{NAME}", _evil)\n'
                "helper(pytest.MonkeyPatch())\n"
            ),
            "main.py": _F4_MAIN,
        },
        ("main.py", "svc.t"),
        "run-tainted:unresolvable-writer",
        "RAN OTHER.t",
    ),
    "f4_prod_mp_list": (
        {
            "app.py": (
                "import pytest\nfrom other import t as _evil\n"
                'NAME = "t"\nL = [pytest.MonkeyPatch()]\n'
                'L[0].setattr(f"svc.{NAME}", _evil)\n'
            ),
            "main.py": _F4_MAIN,
        },
        ("main.py", "svc.t"),
        "run-tainted:unresolvable-writer",
        "RAN OTHER.t",
    ),
    # P6-14: a call inside an annotation hands the fixture on.
    "f4_mp_annot_eval": (
        {
            "tests/test_b.py": _F4_HEAD + "def helper(mp):\n"
            '    mp.setattr(f"svc.{NAME}", _evil)\n    return int\n'
            "def test_go(monkeypatch):\n"
            "    def inner(a: helper(monkeypatch)): pass\n"
            "    inner.__annotations__\n"
            '    print("RAN", calls.go())\n'
        },
        ("tests/calls.py", "svc.t"),
        "run-tainted:unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD5_BLOCKING))
def test_fold5_president_cases_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    """#705 P6-10..P6-15 and E6-9a, each president's tree with what CPython
    3.14 or pytest printed in its ``runtime`` field:

    - P6-10 (``f4_mp_syspath_prepend``): ``monkeypatch.syspath_prepend(p)``
      is ``sys.path.insert(0, p)``; ``import calls`` then found
      ``shadow/svc.py`` and printed ``SHADOW.t``, so it is ``module-system``.
    - P6-11 (``f4_mp_global_cross``, ``f4_mp_global_attr``): a module-level
      ``MP = pytest.MonkeyPatch()`` is imported by the test, which patches
      ``svc.t`` through it.
    - P6-12, P6-15 (``f4_mp_getfixture_alias``, ``f4_mp_getattr_method``):
      ``getfixturevalue`` reached through an alias or ``getattr`` returned the
      ``monkeypatch`` fixture.
    - P6-13 (``f4_prod_*``): production ``app.py`` hands a patcher on, and
      production ``main.py`` then ran ``OTHER.t``; the cause now applies to
      production callers too.
    - P6-14 (``f4_mp_annot_eval``): evaluating ``inner.__annotations__``
      called ``helper(monkeypatch)``.
    """
    files, (file, reference), reason, _runtime = FOLD5_BLOCKING[case]
    root = _write(tmp_path, {**_SVC_OTHER, **files})
    off, _structural, on, label = _run(root, file, reference)
    assert on == off, case
    assert label == f"none({reason})", case


def test_fold5_syspath_insert_control(tmp_path: Path) -> None:
    """P6-10 control (``f4_ctl_syspath_insert``, pytest: ``RAN SHADOW.t``):
    the plain ``sys.path.insert`` that ``syspath_prepend`` equals was
    already a ``module-system`` cause."""
    root = _write(
        tmp_path,
        {
            **_SVC_OTHER,
            "shadow/svc.py": 'def t(): return "SHADOW.t"\n',
            "tests/test_b.py": (
                "import os, sys\ndef test_go():\n"
                '    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shadow"))\n'
                '    import calls\n    print("RAN", calls.go())\n'
            ),
        },
    )
    off, _structural, on, label = _run(root, "tests/calls.py", "svc.t")
    assert on == off
    assert label == "none(run-tainted:module-system)"


def test_fold5_production_patcher_causes_stay_production_scoped(
    tmp_path: Path,
) -> None:
    """E6-9a under O-2: a test file's patcher escape still reaches only test
    callers, while a production file's reaches every caller (above)."""
    files = dict(FOLD5_BLOCKING["f4_prod_mp_param"][0])
    files["tests/test_app.py"] = files.pop("app.py")
    files["main.py"] = "import svc\ndef go(): return svc.t()\n"
    root = _write(tmp_path, {**_SVC_OTHER, **files})
    _off, _structural, on, label = _run(root, "main.py", "svc.t")
    assert on["resolution"] == "resolved" and label == "import"
    _off, _structural, on, label = _run(root, "tests/calls.py", "svc.t")
    assert label == "none(run-tainted:unresolvable-writer)"


def test_fold5_local_aliases_and_plain_annotations_stay_safe(
    tmp_path: Path,
) -> None:
    """Controls for P6-11 and P6-14: a function-local alias, a ``with ... as``
    local and plain annotations (``pytest.MonkeyPatch``, ``list[...]``,
    ``... | None``) record no cause."""
    root = _write(
        tmp_path,
        {
            **_SVC_OTHER,
            "tests/test_b.py": (
                "import pytest\nfrom pytest import MonkeyPatch\n"
                "def test_go(monkeypatch: pytest.MonkeyPatch,"
                " other: list[MonkeyPatch] | None = None):\n"
                "    mp = monkeypatch\n    mp.setenv('X', '1')\n"
                "    with monkeypatch.context() as m:\n        m.delenv('X')\n"
                "    local = MonkeyPatch()\n    local.undo()\n"
            ),
        },
    )
    facts, _graph, _context_ = _context(root)
    (item,) = [item for item in facts if item["path"] == "tests/test_b.py"]
    assert item["scope_facts"]["module_bindings"]["shutoff"] == []


def test_fold5_plain_getfixturevalue_constant_is_no_cause(tmp_path: Path) -> None:
    """P6-15 control: the constant ``"getfixturevalue"`` names a fixture
    lookup only as a call argument (``getattr(request, "getfixturevalue")``);
    a plain constant (this tool's own ``_GETFIXTUREVALUE``) records no
    cause."""
    root = _write(
        tmp_path,
        {**_SVC_OTHER, "names.py": 'GET = "getfixturevalue"\n'},
    )
    facts, _graph, _context_ = _context(root)
    (item,) = [item for item in facts if item["path"] == "names.py"]
    assert item["scope_facts"]["module_bindings"]["shutoff"] == []


def test_fold5_a_local_named_monkeypatch_is_no_fixture(tmp_path: Path) -> None:
    """An ordinary local spelled ``monkeypatch`` (this tool's own
    ``monkeypatch = ...`` flag, read in an ``elif``) records no cause: fold 5
    seeded the fixture from a parameter only, and since fold 6 (E6-9b) only
    the MonkeyPatch methods themselves are matched."""
    root = _write(
        tmp_path,
        {
            **_SVC_OTHER,
            "flags.py": (
                "def f(names):\n    monkeypatch = 'setattr' in names\n"
                "    if monkeypatch:\n        return [monkeypatch]\n    return []\n"
            ),
        },
    )
    facts, _graph, _context_ = _context(root)
    (item,) = [item for item in facts if item["path"] == "flags.py"]
    assert item["scope_facts"]["module_bindings"]["shutoff"] == []


# ---------------------------------------------------------------------------
# Fold 6 (#705 P6-17, P6-18; executive ruling E6-9b): the president's ``f5_*``
# trees, verbatim apart from ``svc.py``/``other.py``/``tests/calls.py`` (as in
# ``_SVC_OTHER``), and five spellings of the method name itself. ``runtime``
# is what pytest 8.4.1 printed on CPython 3.14.10 (``python -B -E -s -m
# pytest -q -s -p no:cacheprovider --rootdir=. tests``); in every tree fold 5
# resolved ``tests/calls.py``'s ``svc.t`` to ``svc.py`` while ``other.t`` ran.

_F5_HEAD = 'import calls\nfrom other import t as _evil\nNAME = "t"\n'
FOLD6_BLOCKING: dict[str, tuple[dict[str, str], str]] = {
    # P6-17: pytest delivery routes.
    "f5_usefix_funcargs": (
        {
            "tests/test_b.py": "import calls\nimport pytest\nfrom other import t as _evil\n"
            'NAME = "t"\n@pytest.mark.usefixtures("monkeypatch")\n'
            "def test_go(request):\n"
            '    mp = request.node.funcargs["monkeypatch"]\n'
            '    mp.setattr(f"svc.{NAME}", _evil)\n    print("RAN", calls.go())\n'
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f5_autouse_funcargs": (
        {
            "tests/conftest.py": "import pytest\n@pytest.fixture(autouse=True)\n"
            "def _iso(monkeypatch):\n    pass\n",
            "tests/test_b.py": _F5_HEAD + "def test_go(request):\n"
            '    request.node.funcargs["monkeypatch"].setattr(f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n',
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f5_hook_fixture_setup": (
        {
            "tests/conftest.py": "import pytest\nfrom other import t as _evil\n"
            'NAME = "t"\n@pytest.hookimpl(wrapper=True)\n'
            "def pytest_fixture_setup(fixturedef, request):\n    value = yield\n"
            '    if fixturedef.argname == "monkeypatch":\n'
            '        value.setattr(f"svc.{NAME}", _evil)\n    return value\n',
            "tests/test_b.py": "import calls\nimport pytest\n"
            '@pytest.mark.usefixtures("monkeypatch")\n'
            'def test_go():\n    print("RAN", calls.go())\n',
        },
        "RAN OTHER.t / 1 passed",
    ),
    # P6-17: introspection.
    "f5_closure_cell": (
        {
            "tests/helpers_mp.py": "import pytest\ndef make():\n    mp = None\n"
            "    def init():\n        nonlocal mp\n        mp = pytest.MonkeyPatch()\n"
            "    init()\n    return init\n",
            "tests/test_b.py": "import calls\nfrom helpers_mp import make\n"
            'from other import t as _evil\nNAME = "t"\ndef test_go():\n'
            '    make().__closure__[0].cell_contents.setattr(f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n',
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f5_frame_locals": (
        {
            "tests/helpers_mp.py": "import pytest, sys\ndef make():\n"
            "    mp = pytest.MonkeyPatch()\n    return sys._getframe()\n",
            "tests/test_b.py": "import calls\nfrom helpers_mp import make\n"
            'from other import t as _evil\nNAME = "t"\ndef test_go():\n'
            '    make().f_locals["mp"].setattr(f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n',
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f5_frame_walk": (
        {
            "tests/helpers_x.py": "import sys\nfrom other import t as _evil\n"
            'NAME = "t"\ndef poke():\n'
            '    sys._getframe(1).f_locals["monkeypatch"].setattr(f"svc.{NAME}", _evil)\n',
            "tests/test_b.py": "import calls\nfrom helpers_x import poke\n"
            'def test_go(monkeypatch):\n    poke()\n    print("RAN", calls.go())\n',
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f5_locals_dict": (
        {
            "tests/test_b.py": _F5_HEAD + "def helper(d):\n"
            '    d["monkeypatch"].setattr(f"svc.{NAME}", _evil)\n'
            "def test_go(monkeypatch):\n    helper(locals())\n"
            '    print("RAN", calls.go())\n'
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f5_hints_locals": (
        {
            "tests/test_b.py": "import calls, typing\nfrom other import t as _evil\n"
            'NAME = "t"\ndef helper(mp):\n    mp.setattr(f"svc.{NAME}", _evil)\n'
            "    return int\ndef test_go(monkeypatch):\n"
            '    def inner(a: "helper(monkeypatch)"): pass\n'
            "    typing.get_type_hints(inner, localns=locals())\n"
            '    print("RAN", calls.go())\n'
        },
        "RAN OTHER.t / 1 passed",
    ),
    # P6-18: string spellings of ``getfixturevalue``; each ends in a
    # spelled ``mp.setattr(...)``.
    "f5_str_var": (
        {
            "tests/test_b.py": _F5_HEAD + 'FN = "getfixturevalue"\n'
            "def test_go(request):\n"
            '    mp = getattr(request, FN)("monkeypatch")\n'
            '    mp.setattr(f"svc.{NAME}", _evil)\n    print("RAN", calls.go())\n'
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f5_str_tuple": (
        {
            "tests/test_b.py": _F5_HEAD + "def test_go(request):\n"
            '    for n in ("getfixturevalue",):\n'
            '        mp = getattr(request, n)("monkeypatch")\n'
            '    mp.setattr(f"svc.{NAME}", _evil)\n    print("RAN", calls.go())\n'
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f5_str_concat": (
        {
            "tests/test_b.py": _F5_HEAD + "def test_go(request):\n"
            '    mp = getattr(request, "getfixture" + "value")("monkeypatch")\n'
            '    mp.setattr(f"svc.{NAME}", _evil)\n    print("RAN", calls.go())\n'
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f5_str_subscript2": (
        {
            "tests/test_b.py": _F5_HEAD + "def test_go(request):\n"
            '    mp = type(request).__mro__[1].__dict__["getfixturevalue"](request, "monkeypatch")\n'
            '    mp.setattr(f"svc.{NAME}", _evil)\n    print("RAN", calls.go())\n'
        },
        "RAN OTHER.t / 1 passed",
    ),
    # E6-9b: the method name without a direct call on a receiver.
    "f6_getattr_setattr": (
        {
            "tests/test_b.py": _F5_HEAD + "def test_go(monkeypatch):\n"
            '    getattr(monkeypatch, "setattr")(f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n'
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f6_methodcaller": (
        {
            "tests/test_b.py": "import operator\n"
            + _F5_HEAD
            + "def test_go(monkeypatch):\n"
            '    operator.methodcaller("setattr", f"svc.{NAME}", _evil)(monkeypatch)\n'
            '    print("RAN", calls.go())\n'
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f6_method_reference": (
        {
            "tests/test_b.py": _F5_HEAD + "def test_go(monkeypatch):\n"
            "    s = monkeypatch.setattr\n"
            '    s(f"svc.{NAME}", _evil)\n    print("RAN", calls.go())\n'
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f6_unbound_class": (
        {
            "tests/test_b.py": "import pytest\n"
            + _F5_HEAD
            + "def test_go(monkeypatch):\n"
            '    pytest.MonkeyPatch.setattr(monkeypatch, f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n'
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f6_keyword_target": (
        {
            "tests/test_b.py": _F5_HEAD + "def test_go(monkeypatch):\n"
            '    monkeypatch.setattr(target=f"svc.{NAME}", name=_evil)\n'
            '    print("RAN", calls.go())\n'
        },
        "RAN OTHER.t / 1 passed",
    ),
    "f6_splat": (
        {
            "tests/test_b.py": _F5_HEAD + "def test_go(monkeypatch):\n"
            '    ARGS = (f"svc.{NAME}", _evil)\n'
            "    monkeypatch.setattr(*ARGS)\n"
            '    print("RAN", calls.go())\n'
        },
        "RAN OTHER.t / 1 passed",
    ),
    # A pytest-mock fixture fetched by name and handed on: its ``.patch`` runs
    # where no rule sees it (pytest-mock is not installed in the measuring
    # venv; this row records the rule).
    "getfixturevalue-mocker-escape": (
        {
            "tests/test_b.py": _F5_HEAD + "def helper(m):\n"
            '    m.patch(f"svc.{NAME}", _evil)\n'
            "def test_go(request):\n"
            '    helper(request.getfixturevalue("mocker"))\n'
            '    print("RAN", calls.go())\n'
        },
        "(pytest-mock: mocker.patch is unittest.mock.patch)",
    ),
    # P6-12 and P6-15 for pytest-mock: ``getfixturevalue`` through an alias
    # or ``getattr`` fetching ``mocker``, whose ``.patch`` is ``patch``
    # (rule rows: pytest-mock is not installed in the measuring venv). The
    # MonkeyPatch forms of these trees close by E6-9b alone.
    "getfixturevalue-alias-mocker": (
        {
            "tests/test_b.py": _F5_HEAD + "def test_go(request):\n"
            "    g = request.getfixturevalue\n"
            '    m = g("mocker")\n'
            '    m.patch(f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n'
        },
        "(pytest-mock: mocker.patch is unittest.mock.patch)",
    ),
    "getfixturevalue-getattr-mocker": (
        {
            "tests/test_b.py": _F5_HEAD + "def test_go(request):\n"
            '    m = getattr(request, "getfixturevalue")("mocker")\n'
            '    m.patch(f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n'
        },
        "(pytest-mock: mocker.patch is unittest.mock.patch)",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD6_BLOCKING))
def test_fold6_monkeypatch_methods_on_any_receiver(tmp_path: Path, case: str) -> None:
    """#705 E6-9b. A ``MonkeyPatch`` reaches a write with no seed spelled:
    ``request.node.funcargs["monkeypatch"]`` (with ``usefixtures`` or an
    autouse fixture), a ``pytest_fixture_setup`` hook's ``value``, a closure
    cell, a frame's ``f_locals`` (its own or a caller's), ``locals()`` and
    ``get_type_hints(localns=locals())`` evaluating a string annotation
    (P6-17); and ``getfixturevalue`` through a variable, a loop, a
    concatenation or the class ``__dict__`` (P6-18). Every route ends in a
    spelled ``.setattr(...)``, or in the method name as a string
    (``getattr(mp, "setattr")``, ``methodcaller("setattr", ...)``), a method
    reference, the unbound ``MonkeyPatch.setattr(mp, ...)`` or a ``target=``
    keyword. pytest printed ``RAN OTHER.t`` in every tree. The method is now
    matched on any receiver: test callers get ``unresolvable-writer``."""
    files, _runtime = FOLD6_BLOCKING[case]
    root = _write(tmp_path, {**_SVC_OTHER, **files})
    off, _structural, on, label = _run(root, "tests/calls.py", "svc.t")
    assert on == off, case
    if case in _FOLD6_NAMESPACE_READERS:
        # #724: the test file reads its own namespace (``locals()``), so
        # its ``import calls`` is handed out and ``calls``
        # is tainted wholly, which decides first.
        assert label == "none(module-escape)", case
    else:
        assert label == "none(run-tainted:unresolvable-writer)", case


_FOLD6_NAMESPACE_READERS = frozenset({"f5_locals_dict", "f5_hints_locals"})


FOLD6_CONTROLS: dict[str, tuple[str, str | None]] = {
    # ``operator.setitem`` keeps its treatment: the namespace dict is a
    # whole-module escape of ``svc`` (no cause).
    "operator-setitem": (
        "import operator\nimport svc\nfrom other import t as _evil\n"
        "def f():\n    operator.setitem(svc.__dict__, 't', _evil)\n",
        "module-escape",
    ),
    # The builtin ``setattr`` is a bare call: a named write of ``svc.t``.
    "builtin-setattr": (
        "import svc\nfrom other import t as _evil\n"
        "def f():\n    setattr(svc, 't', _evil)\n",
        "reassigned",
    ),
    # Constant string and object forms on any receiver keep exact taints.
    "constant-string-form": (
        "from other import t as _evil\n"
        "def f(anything):\n    anything.setattr('svc.t', _evil)\n",
        "reassigned",
    ),
    "object-form-constant-name": (
        "import svc\nfrom other import t as _evil\n"
        "def f(anything):\n    anything.setattr(svc, 't', _evil)\n",
        "module-escape",
    ),
    # ``setitem``/``delitem`` on a plain dict add nothing.
    "setitem-on-a-dict": (
        "def f(anything, d):\n    anything.setitem(d, 'k', 1)\n    anything.delitem(d, 'k')\n",
        None,
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD6_CONTROLS))
def test_fold6_controls_keep_their_treatment(tmp_path: Path, case: str) -> None:
    """E6-9b controls: ``operator.setitem`` (excluded by the Tier 1 lookup),
    the builtin ``setattr`` and constant targets keep their exact taints and
    record no cause; ``setitem`` on a plain mapping records nothing."""
    writer, reason = FOLD6_CONTROLS[case]
    root = _write(tmp_path, {**_SVC_OTHER, "use.py": USE, "w.py": writer})
    facts, _graph, _context_ = _context(root)
    (item,) = [item for item in facts if item["path"] == "w.py"]
    assert item["scope_facts"]["module_bindings"]["shutoff"] == [], case
    _off, _structural, on, label = _run(root, "use.py", "t")
    if reason is None:
        assert on["resolution"] == "resolved" and label == "import", case
    else:
        assert label == f"none({reason})", case


@pytest.mark.parametrize(
    "line",
    [
        "    request.node.funcargs['monkeypatch'].syspath_prepend('shadow')\n",
        "    getattr(request.node.funcargs['monkeypatch'], 'syspath_prepend')('shadow')\n",
    ],
)
def test_fold6_syspath_prepend_on_any_receiver(tmp_path: Path, line: str) -> None:
    """E6-9b, P6-10 on any receiver: ``request.node.funcargs["monkeypatch"]
    .syspath_prepend(p)``, also by name through ``getattr``, is a
    ``module-system`` cause, scoped by O-2."""
    root = _write(
        tmp_path,
        {
            **_SVC_OTHER,
            "use.py": USE,
            "tests/test_b.py": "def test_go(request):\n" + line,
        },
    )
    _off, _structural, _on, label = _run(root, "tests/calls.py", "svc.t")
    assert label == "none(run-tainted:module-system)"
    _off, _structural, on, label = _run(root, "use.py", "t")
    assert on["resolution"] == "resolved" and label == "import"


# ---------------------------------------------------------------------------
# Fold 7 (#705 P6-21, P6-22): a constant method name spelled as more than one
# literal, as a keyword value or as a subscript key. The president's
# ``cases6/f6p_*`` trees import ``pytest``, ``sys``, ``svc``, ``other``,
# ``importlib``, ``operator`` and ``functools`` at the top of
# ``tests/test_b.py``; the rows keep only the lines that matter. ``runtime``
# is what pytest 8.4.1 printed on CPython 3.14.10.

_F7_HEAD = 'import calls\nimport pytest\nfrom other import t as _evil\nNAME = "t"\n'
FOLD7_BLOCKING: dict[str, tuple[dict[str, str], str, str]] = {
    # P6-21: the method name passed as a call argument.
    "f6p_a19_getattr_concat": (
        {
            "tests/test_b.py": _F7_HEAD + "def test_go(monkeypatch):\n"
            '    getattr(monkeypatch, "set" "attr")(f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n'
        },
        "unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    "f6p_a20_getattr_plus": (
        {
            "tests/test_b.py": _F7_HEAD + "def test_go(monkeypatch):\n"
            '    getattr(monkeypatch, "set" + "attr")(f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n'
        },
        "unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    "f6p_a21_getattr_paren": (
        {
            "tests/test_b.py": _F7_HEAD + "def test_go(monkeypatch):\n"
            '    getattr(monkeypatch, ("setattr"))(f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n'
        },
        "unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    "f6p_e01_getattr_static_kw": (
        {
            "tests/test_b.py": _F7_HEAD + "def test_go(monkeypatch):\n"
            "    import inspect\n"
            '    inspect.getattr_static(monkeypatch, attr="setattr")(monkeypatch, f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n'
        },
        "unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    "f6p_e03_concat_comment": (
        {
            "tests/test_b.py": _F7_HEAD + "def test_go(monkeypatch):\n"
            '    getattr(monkeypatch, "set"  # x\n'
            '        "attr")(f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n'
        },
        "unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    "f7_syspath_concat": (
        {
            "shadow/svc.py": 'def t(): return "SHADOW.t"\n',
            "tests/test_b.py": "import os\ndef test_go(monkeypatch):\n"
            '    getattr(monkeypatch, "syspath" "_prepend")(os.path.join(os.path.dirname(__file__), "..", "shadow"))\n'
            '    import calls\n    print("RAN", calls.go())\n',
        },
        "module-system",
        "RAN SHADOW.t / 1 passed",
    ),
    # P6-21 for pytest-mock: ``getfixturevalue`` named by ``+`` (rule row:
    # pytest-mock is not installed in the measuring venv).
    "getfixturevalue-plus-mocker": (
        {
            "tests/test_b.py": _F7_HEAD + "def test_go(request):\n"
            '    m = getattr(request, "getfixture" + "value")("mocker")\n'
            '    m.patch(f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n'
        },
        "unresolvable-writer",
        "(pytest-mock: mocker.patch is unittest.mock.patch)",
    ),
    # P6-22: the method name as a subscript key.
    "f6p_c08_class_dict": (
        {
            "tests/test_b.py": _F7_HEAD + "def test_go(monkeypatch):\n"
            '    pytest.MonkeyPatch.__dict__["setattr"](monkeypatch, f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n'
        },
        "unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
    "f6p_c09_vars_class": (
        {
            "tests/test_b.py": _F7_HEAD + "def test_go(monkeypatch):\n"
            '    vars(type(monkeypatch))["setattr"](monkeypatch, f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n'
        },
        "unresolvable-writer",
        "RAN OTHER.t / 1 passed",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD7_BLOCKING))
def test_fold7_method_names_by_constant_expression(tmp_path: Path, case: str) -> None:
    """#705 P6-21: a constant method name is any expression Tier 1's
    ``_constant_string`` decodes (adjacent literals, also with a comment
    between them; ``+``; parentheses), passed positionally or as a keyword
    value (``inspect.getattr_static(mp, attr="setattr")``). P6-22: or used as
    a subscript key (``MonkeyPatch.__dict__["setattr"]``,
    ``vars(type(mp))["setattr"]``). pytest printed ``RAN OTHER.t`` (``RAN
    SHADOW.t`` for ``syspath_prepend``) in every tree, which fold 6 resolved
    to ``svc.py``."""
    files, reason, _runtime = FOLD7_BLOCKING[case]
    root = _write(tmp_path, {**_SVC_OTHER, **files})
    off, _structural, on, label = _run(root, "tests/calls.py", "svc.t")
    assert on == off, case
    assert label == f"none(run-tainted:{reason})", case


def test_fold7_computed_method_name_is_r12(tmp_path: Path) -> None:
    """The president's ``f6p_r1_name_var`` (``M = "setattr"; getattr(mp,
    M)(...)``; pytest printed ``RAN OTHER.t``) stays the §15 R12
    computed-string residual: a name built at run time is not followed. This
    row pins that it is not silently claimed closed."""
    root = _write(
        tmp_path,
        {
            **_SVC_OTHER,
            "tests/test_b.py": _F7_HEAD + "def test_go(monkeypatch):\n"
            '    M = "setattr"\n'
            '    getattr(monkeypatch, M)(f"svc.{NAME}", _evil)\n'
            '    print("RAN", calls.go())\n',
        },
    )
    _off, _structural, on, label = _run(root, "tests/calls.py", "svc.t")
    assert on["resolution"] == "resolved" and label == "import"


def test_fold7_other_constant_names_record_nothing(tmp_path: Path) -> None:
    """Controls: a constant string that is no patcher name, in an argument,
    a keyword value or a subscript key, and a ``setattr`` constant that is
    neither (an assignment value), record no cause."""
    root = _write(
        tmp_path,
        {
            **_SVC_OTHER,
            "w.py": "def f(d, o):\n"
            '    x = getattr(o, "set" "default")\n'
            '    y = d["get" + "item"]\n'
            '    z = dict(key="value")\n'
            '    name = "setattr"\n'
            "    return x, y, z, name\n",
        },
    )
    facts, _graph, _context_ = _context(root)
    (item,) = [item for item in facts if item["path"] == "w.py"]
    assert item["scope_facts"]["module_bindings"]["shutoff"] == []


# ---------------------------------------------------------------------------
# Fold 8 (#705, Codex review r4661935648): a re-exported ``import a.b as m``
# binding went around the E6-3 package-attribute check. Every tree has
# ``a/__init__.py`` doing ``from . import b`` and then ``from vendor import
# impl as b`` (so ``a.b`` is ``vendor.impl`` once the package is imported),
# ``a/b.py: def t(): return "A.B.t"`` and ``vendor/impl.py: def t(): return
# "VENDOR.impl.t"``. ``runtime`` is what ``python -B -E -s main.py`` printed
# on CPython 3.14.10.

_F8_BASE = {
    "a/b.py": 'def t(): return "A.B.t"\n',
    "vendor/__init__.py": "",
    "vendor/impl.py": 'def t(): return "VENDOR.impl.t"\n',
}
_F8_SHADOW = {"a/__init__.py": "from . import b\nfrom vendor import impl as b\n"}
FOLD8_BLOCKING: dict[str, tuple[dict[str, str], tuple[str, str], str, str]] = {
    "codex_reexport_import_as": (
        {
            "facade.py": "import a.b as m\n",
            "main.py": 'from facade import m\ndef go(): return m.t()\nprint("RAN", go())\n',
        },
        ("main.py", "m.t"),
        "attr-submodule-conflict",
        "RAN VENDOR.impl.t",
    ),
    "reexport_attribute_chain": (
        {
            "facade.py": "import a.b as m\n",
            "main.py": 'import facade\ndef go(): return facade.m.t()\nprint("RAN", go())\n',
        },
        ("main.py", "facade.m.t"),
        "attr-submodule-conflict",
        "RAN VENDOR.impl.t",
    ),
    "reexport_two_hops": (
        {
            "facade.py": "import a.b as m\n",
            "facade2.py": "from facade import m\n",
            "main.py": 'from facade2 import m\ndef go(): return m.t()\nprint("RAN", go())\n',
        },
        ("main.py", "m.t"),
        "attr-submodule-conflict",
        "RAN VENDOR.impl.t",
    ),
    "reexport_alias": (
        {
            "facade.py": "import a.b as m\n",
            "main.py": 'from facade import m as n\ndef go(): return n.t()\nprint("RAN", go())\n',
        },
        ("main.py", "n.t"),
        "attr-submodule-conflict",
        "RAN VENDOR.impl.t",
    ),
    "reexport_from_binding": (
        {
            "facade.py": "from a import b\n",
            "main.py": 'from facade import b\ndef go(): return b.t()\nprint("RAN", go())\n',
        },
        ("main.py", "b.t"),
        "attr-submodule-conflict",
        "RAN VENDOR.impl.t",
    ),
    # The writer side: ``m`` is ``vendor.impl``, so ``m.t = o`` (directly or
    # through ``facade.m``) writes ``vendor.impl.t``.
    "writer_import_as": (
        {
            "other.py": 'def t(): return "OTHER.t"\n',
            "w.py": "import a.b as m\nfrom other import t as o\nm.t = o\n",
            "use.py": "from vendor.impl import t\ndef u(): return t()\n",
            "main.py": 'import w, use\nprint("RAN", use.u())\n',
        },
        ("use.py", "t"),
        "reassigned",
        "RAN OTHER.t",
    ),
    "writer_through_facade": (
        {
            "other.py": 'def t(): return "OTHER.t"\n',
            "facade.py": "import a.b as m\n",
            "w.py": "import facade\nfrom other import t as o\nfacade.m.t = o\n",
            "use.py": "from vendor.impl import t\ndef u(): return t()\n",
            "main.py": 'import w, use\nprint("RAN", use.u())\n',
        },
        ("use.py", "t"),
        "reassigned",
        "RAN OTHER.t",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD8_BLOCKING))
def test_fold8_reexported_bindings_use_the_one_resolver(
    tmp_path: Path, case: str
) -> None:
    """#705 fold 8 (Codex r4661935648). ``import a.b as m`` binds
    ``getattr(a, "b")``, which ``a/__init__.py`` rebound to ``vendor.impl``
    after ``from . import b``; ``a.b`` is already in ``sys.modules``, so the
    later import never resets it. CPython 3.14 printed ``RAN VENDOR.impl.t``
    for ``from facade import m; m.t()``, ``facade.m.t()``, a two-hop
    re-export, ``from facade import m as n`` and a re-exported ``from a
    import b``, and ``RAN OTHER.t`` where ``m.t = o`` or ``facade.m.t = o``
    wrote ``vendor.impl.t``. Fold 7 proved ``a/b.py:t`` for the re-exports and
    left ``use.py``'s ``from vendor.impl import t`` resolved. Every binding
    now goes through one resolver (``_resolve_binding``; on the writer side
    ``_Builder.module_values``)."""
    files, (file, reference), reason, _runtime = FOLD8_BLOCKING[case]
    root = _write(tmp_path, {**_F8_BASE, **_F8_SHADOW, **files})
    off, _structural, on, label = _run(root, file, reference)
    assert off["resolution"] == "ambiguous", case
    assert on == off, case
    assert label == f"none({reason})", case


FOLD8_CONTROLS: dict[str, tuple[dict[str, str], tuple[str, str]]] = {
    # CPython: ``RAN A.B.t``. The package binds ``b`` only by ``from . import
    # b``, so the re-exported ``import a.b as m`` is the submodule.
    "clean_reexport": (
        {
            "a/__init__.py": "from . import b\n",
            "facade.py": "import a.b as m\n",
            "main.py": 'from facade import m\ndef go(): return m.t()\nprint("RAN", go())\n',
        },
        ("main.py", "m.t"),
    ),
    # CPython: ``RAN A.B.t``. An empty ``__init__.py``, two hops.
    "clean_two_hops": (
        {
            "a/__init__.py": "",
            "facade.py": "import a.b as m\n",
            "facade2.py": "from facade import m\n",
            "main.py": 'from facade2 import m\ndef go(): return m.t()\nprint("RAN", go())\n',
        },
        ("main.py", "m.t"),
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD8_CONTROLS))
def test_fold8_clean_reexports_still_resolve(tmp_path: Path, case: str) -> None:
    files, (file, reference) = FOLD8_CONTROLS[case]
    root = _write(tmp_path, {**_F8_BASE, **files})
    _off, _structural, on, label = _run(root, file, reference)
    assert on["resolution"] == "resolved" and label == "import", case
    assert _target(on, root) == "a/b.py", case


# treesitter-chunker#724: a file that reads its own namespace hands out every
# import binding in it. Each tree's ``main.py`` imports ``use`` (the reader,
# or the file that reaches it), runs it and prints which ``t`` body
# ``svc.u()`` ran. ``svc.py``'s ``u -> t`` is a Tier 1 proof; ``other.py``
# defines another ``t``, so name mode is ambiguous.
_NS_SVC = 'def t():\n    return "SVC.t"\n\n\ndef u():\n    return t()\n'
_NS_BASE = {
    "svc.py": _NS_SVC,
    "other.py": 'def t():\n    return "OTHER.t"\n',
    "main.py": "import use\nimport svc\n\nuse.go()\nprint(svc.u())\n",
}
_NS_POKE = "import get as G\n\n\ndef go():\n    G.poke()\n"
_NS_HELPER = {
    "helper.py": 'import other\n\n\ndef patch(d):\n    d["svc"].t = other.t\n'
}

# Name -> (files, what CPython 3.14 prints). Every pinned case printed
# ``OTHER.t`` (the replacement ran); main 64bae100 resolved ``svc.py``'s
# ``t`` in all but c01 and c04, whose getter return or module alias was
# already an escape.
NAMESPACE_HANDOUT: dict[str, dict[str, str]] = {
    # The #706 plan battery (706/battery-final4).
    "c01-locals-leak-alias": {
        "get.py": "import svc\n\n\ndef get():\n    return svc\n",
        "helper.py": 'import other\n\n\ndef patch(d):\n    d["m"].t = other.t\n',
        "use.py": (
            "from get import get\nimport helper\n\n\ndef go():\n    m = get()\n"
            "    helper.patch(locals())\n"
        ),
    },
    "c01-twin-locals-leak-import": {
        **_NS_HELPER,
        "use.py": "import helper\n\n\ndef go():\n    import svc\n    helper.patch(locals())\n",
    },
    "c04-globals-leak-module-alias": {
        "holder.py": "import svc\n",
        "helper.py": 'import other\n\n\ndef patch(d):\n    d["SV"].t = other.t\n',
        "use.py": (
            "import holder as H\nimport helper\nSV = H.svc\n\n\ndef go():\n"
            "    helper.patch(globals())\n"
        ),
    },
    "c04-twin-globals-leak-import": {
        **_NS_HELPER,
        "use.py": "import svc\nimport helper\n\n\ndef go():\n    helper.patch(globals())\n",
    },
    "c03-twin-exec-import": {
        "use.py": 'import svc\nimport other\n\n\ndef go():\n    exec("svc.t = other.t")\n',
    },
    # The plan review's twins (706-opus, plain imports).
    "x02t-own-f_globals": {
        "get.py": (
            "import sys\nimport svc\nimport other\n\n\ndef poke():\n"
            '    sys._getframe(0).f_globals["svc"].t = other.t\n'
        ),
        "use.py": _NS_POKE,
    },
    "x03t-own-__globals__": {
        "get.py": (
            "import svc\nimport other\n\n\ndef poke():\n"
            '    poke.__globals__["svc"].t = other.t\n'
        ),
        "use.py": _NS_POKE,
    },
    "y01t-own-getmodule": {
        "get.py": (
            "import inspect\nimport svc\nimport other\n\n\ndef poke():\n"
            "    inspect.getmodule(poke).svc.t = other.t\n"
        ),
        "use.py": _NS_POKE,
    },
    "y02t-own-dunder-import": {
        "get.py": (
            "import svc\nimport other\n\n\ndef poke():\n"
            "    __import__(__name__).svc.t = other.t\n"
        ),
        "use.py": _NS_POKE,
    },
    "y05t-caller-f_globals": {
        "use.py": (
            "import sys\nimport svc\nimport other\n\n\ndef go():\n"
            '    sys._getframe(0).f_globals["svc"].t = other.t\n'
        ),
    },
    "z01t-caller-globals": {
        "use.py": (
            "import svc\nimport other\n\n\ndef go():\n"
            '    globals()["svc"].t = other.t\n'
        ),
    },
    "x06t-string-annotation": {
        "get.py": (
            'import typing\nimport svc\nimport other\n\n\ndef h(x: "svc"):\n'
            '    pass\n\n\ndef poke():\n    typing.get_type_hints(h)["x"].t = other.t\n'
        ),
        "use.py": _NS_POKE,
    },
    # More spellings of the same rule.
    "vars-no-argument": {
        "use.py": (
            "import other\n\n\ndef go():\n    import svc\n"
            '    vars()["svc"].t = other.t\n'
        ),
    },
    "eval-one-argument": {
        "use.py": 'import svc\nimport other\n\n\ndef go():\n    eval("svc").t = other.t\n',
    },
    "exec-none-globals": {
        "use.py": (
            "import svc\nimport other\n\n\ndef go():\n"
            '    exec("svc.t = other.t", None)\n'
        ),
    },
    "globals-handed-on": {
        "use.py": (
            "import svc\nimport other\n\nns = globals\n\n\ndef go():\n"
            '    ns()["svc"].t = other.t\n'
        ),
    },
    "builtins-globals-attribute": {
        "use.py": (
            "import builtins\nimport svc\nimport other\n\n\ndef go():\n"
            '    builtins.globals()["svc"].t = other.t\n'
        ),
    },
    "globals-imported-under-another-name": {
        "use.py": (
            "from builtins import globals as g\nimport svc\nimport other\n\n\n"
            'def go():\n    g()["svc"].t = other.t\n'
        ),
    },
    "builtins-globals-by-string": {
        "use.py": (
            "import builtins\nimport svc\nimport other\n\n\ndef go():\n"
            '    getattr(builtins, "globals")()["svc"].t = other.t\n'
        ),
    },
    "f_globals-computed-key": {
        "use.py": (
            "import sys\nimport svc\nimport other\n\n\ndef go():\n"
            '    k = "s" + "vc"\n    sys._getframe(0).f_globals[k].t = other.t\n'
        ),
    },
    "f_locals-written": {
        "use.py": (
            "import sys\nimport other\n\n\ndef go():\n    import svc\n"
            "    f = sys._getframe(0)\n    m = f.f_locals\n"
            '    m["svc"].t = other.t\n'
        ),
    },
    "f_builtins-globals": {
        "use.py": (
            "import sys\nimport svc\nimport other\n\n\ndef go():\n"
            '    sys._getframe(0).f_builtins["globals"]()["svc"].t = other.t\n'
        ),
    },
    "f_globals-by-string": {
        "use.py": (
            "import sys\nimport svc\nimport other\n\n\ndef go():\n"
            '    getattr(sys._getframe(0), "f_globals")["svc"].t = other.t\n'
        ),
    },
    "from-import-of-a-submodule": {
        "pkg/__init__.py": "",
        "pkg/svc.py": _NS_SVC,
        "main.py": "import use\nimport pkg.svc\n\nuse.go()\nprint(pkg.svc.u())\n",
        "use.py": (
            "from pkg import svc\nimport other\n\n\ndef go():\n"
            '    globals()["svc"].t = other.t\n'
        ),
    },
}

# Name -> files. A file that keeps its namespace to itself: CPython printed
# ``SVC.t`` for each, and ``svc.py``'s proof stays.
NAMESPACE_CONTROLS: dict[str, dict[str, str]] = {
    "no-reader": {"use.py": "import svc\n\n\ndef go():\n    return svc.t\n"},
    # ``vars(obj)`` reads ``obj.__dict__``.
    "vars-with-argument": {
        "use.py": (
            "import svc\n\n\nclass K:\n    pass\n\n\ndef go():\n"
            "    return vars(K())\n"
        ),
    },
    # spec's ``ingest.py``: ``exec(code, mod.__dict__)`` runs in ``mod``.
    "exec-explicit-globals": {
        "use.py": (
            "import types\nimport svc\n\n\ndef go():\n"
            '    mod = types.ModuleType("m")\n    exec("x = 1", mod.__dict__)\n'
            '    eval("1", {})\n'
        ),
    },
    "exec-keyword-globals": {
        "use.py": 'import svc\n\n\ndef go():\n    exec("x = 1", globals={})\n',
    },
    # A model's ``.eval()`` and a template environment's ``.globals``.
    "eval-and-globals-methods": {
        "use.py": (
            "import svc\n\n\nclass M:\n    globals = {}\n\n    def eval(self):\n"
            "        return self\n\n\ndef go():\n    M().eval()\n"
            '    M.globals["x"] = 1\n'
        ),
    },
    # The ordinary lookup at the use proves the file's own binding.
    "own-binding-named-locals": {
        "use.py": ("import svc\n\n\ndef go(locals=dict):\n    return locals()\n"),
    },
    # A frame read by a constant key reaches only the binding of that name
    # (pmcp's ``tb.tb_frame.f_locals.get("code")``), and ``in`` none.
    "frame-read-of-another-name": {
        "use.py": (
            "import sys\nimport svc\n\n\ndef go():\n    f = sys._getframe(0)\n"
            '    code = f.f_locals.get("code")\n    seen = "svc" in f.f_globals\n'
            '    return code, seen, f.f_globals["sys"]\n'
        ),
    },
    # ``compile``'s mode string names no builtin to call.
    "exec-mode-string": {
        "use.py": 'import svc\n\n\ndef go():\n    return compile("1", "f", "exec")\n',
    },
    "dunder-import-of-a-constant": {
        "use.py": 'import svc\n\n\ndef go():\n    return __import__("json")\n',
    },
}


def _cpython(root: Path) -> str:
    import subprocess
    import sys

    run = subprocess.run(
        [sys.executable, "-B", "-E", "-s", "main.py"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return run.stdout.strip().splitlines()[-1]


@pytest.mark.parametrize("case", sorted(NAMESPACE_HANDOUT))
def test_namespace_reader_hands_out_its_import_bindings(
    tmp_path: Path, case: str
) -> None:
    """#724: ``globals()``, ``locals()``, ``vars()``, one-argument
    ``exec``/``eval``, ``f_globals``, ``__globals__``, ``getmodule``,
    ``__import__(__name__)`` and string annotations evaluated by
    ``get_type_hints`` hand out every import binding of the file that spells
    them, so the imported module is tainted wholly. CPython 3.14 runs the
    replacement in each tree; ``svc.py``'s ``t`` keeps its off-mode edge."""
    root = _write(tmp_path, {**_NS_BASE, **NAMESPACE_HANDOUT[case]})
    assert _cpython(root) == "OTHER.t", case
    probe = "pkg/svc.py" if (root / "pkg/svc.py").exists() else "svc.py"
    off, structural, on, label = _run(root, probe, "t")
    assert structural["resolution"] == "resolved", case
    assert on == off and on["resolution"] == "ambiguous", case
    assert label == "none(module-escape)", case


@pytest.mark.parametrize("case", sorted(NAMESPACE_CONTROLS))
def test_namespace_controls_keep_their_proof(tmp_path: Path, case: str) -> None:
    """#724 controls: ``vars(obj)``, ``exec``/``eval`` with explicit
    globals, another object's ``.eval()`` or ``.globals``, a binding of the
    file's own named ``locals`` and ``__import__`` of a constant read no
    namespace of the file: ``svc.py``'s ``t`` stays resolved."""
    root = _write(tmp_path, {**_NS_BASE, **NAMESPACE_CONTROLS[case]})
    assert _cpython(root) == "SVC.t", case
    _off, _structural, on, label = _run(root, "svc.py", "t")
    assert on["resolution"] == "resolved", (case, label)
    assert _target(on, root) == "svc.py"


def test_namespace_reader_records_value_uses_of_every_binding(
    tmp_path: Path,
) -> None:
    """The reader rule records a ``value`` use of each import binding,
    function-local and ``from`` imports included, and nothing in a file that
    reads no namespace."""
    root = _write(
        tmp_path,
        {
            "r.py": (
                "import a.b\nfrom c import d as e\n\n\ndef f():\n    import g\n"
                "    return locals()\n"
            ),
            "n.py": "import a.b\nfrom c import d as e\n",
        },
    )
    facts = {
        item["path"]: item["scope_facts"]["module_bindings"]
        for item in (
            extract_symbol_facts_for_file(path, root, None, call_resolution=MODE)
            for path in collect_source_files(root, None)
        )
    }
    assert ["a", "value"] in facts["r.py"]["uses"]
    assert ["c", "value", "d"] in facts["r.py"]["uses"]
    assert ["g", "value"] in facts["r.py"]["uses"]
    assert facts["n.py"]["uses"] == []


def test_frame_read_by_constant_key_hands_out_that_binding(tmp_path: Path) -> None:
    """#724: ``frame.f_globals["svc"]`` hands out the binding named ``svc``
    only; another import of the file stays unrecorded."""
    root = _write(
        tmp_path,
        {
            "r.py": (
                "import sys\nimport svc\nimport json\n\n\ndef f():\n"
                '    return sys._getframe(0).f_globals["svc"]\n'
            ),
        },
    )
    (item,) = [
        extract_symbol_facts_for_file(path, root, None, call_resolution=MODE)
        for path in collect_source_files(root, None)
    ]
    uses = item["scope_facts"]["module_bindings"]["uses"]
    assert ["svc", "value"] in uses
    assert ["json", "value"] not in uses and ["sys", "value"] not in uses
