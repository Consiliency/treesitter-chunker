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
    "compile": ("def f(s):\n    return compile(s, 'x', 'exec')\n", "evaluator"),
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
