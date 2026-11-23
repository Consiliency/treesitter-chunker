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
    "return-escape": (
        {"w.py": "import svc\n\n\ndef get():\n    return svc\n"},
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
        "def f(g, h):\n    g.__code__ = h.__code__\n",
        "def f(g):\n    g.__closure__[0].cell_contents = len\n",
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
    """Closure cells, code objects, ``ctypes`` without ``pythonapi`` and
    frame-locals reads leave every module attribute as it is."""
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
        "reassigned",
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
        "reassigned",
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
