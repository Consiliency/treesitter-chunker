"""Rule mutations for Tier 2 Python call resolution (treesitter-chunker#682 PR 6).

Each mutation disables one rule by a single textual edit. The script copies
the checkout to a temporary directory, checks that the unmutated copy passes,
then applies each mutation alone and runs the Tier 2 Python tests and the
``imports`` expected-table test serially. A mutation is *killed* when a test
fails. The script prints one tab-separated line per mutation and exits
non-zero if any mutation survives or does not apply.

Usage (Python 3.14, from the repository root)::

    uv run --locked --all-extras python scripts/call_resolution_tier2_py_mutations.py

Run it only with headroom: it runs the narrow Tier 2 Python tests once per
mutation, serially.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CR = "chunker/call_resolution/"
PYM = CR + "py_modules.py"
ENG = CR + "engine.py"
TESTS = (
    "tests/test_call_resolution_tier2_py.py",
    "tests/test_call_resolution_engine.py::test_expected_imports_tables_hold_at_this_head",
)

# (id, file, old text, new text). The old text must occur in the file once.
MUTATIONS: tuple[tuple[str, str, str, str], ...] = (
    # Module paths (9.5).
    (
        "script-dir-shadow",
        PYM,
        '            return "script-dir-shadow"\n',
        "            pass\n",
    ),
    ("stdlib-name", PYM, "    if parts[0] in STDLIB_MODULES:", "    if False:"),
    (
        "intermediate-module",
        PYM,
        '            if index < len(parts) - 1:\n                return "module-not-found"\n',
        "",
    ),
    (
        "package-before-module",
        PYM,
        "        if init in run.files:\n            found = _Module(dotted, init)",
        "        if init in run.files and module not in run.files:\n"
        "            found = _Module(dotted, init)",
    ),
    (
        "skipped-component",
        PYM,
        '        if component in SKIPPED_DIRECTORIES:\n            return "unknown-variant"\n',
        "",
    ),
    (
        "outside-root",
        PYM,
        "        if dots - 1 >= len(package):\n            # The root is the",
        "        if dots - 1 > len(package):\n            # The root is the",
    ),
    # Name lookup (9.6).
    (
        "attr-submodule-conflict",
        PYM,
        "    if entry is not None and submodule is not None:",
        "    if False:",
    ),
    ("hop-limit", PYM, "    if hops > HOP_LIMIT:", "    if False:"),
    ("cycle", PYM, "    if key in seen:", "    if False:"),
    (
        "submodule-not-callable",
        PYM,
        '    if isinstance(value, _Module):\n        return _none("non-callable")',
        '    if isinstance(value, _Module):\n        return _none("export-not-found")',
    ),
    # Taints (#697).
    (
        "taint-in-lookup",
        PYM,
        "    reason = run.taint_reason(caller, value.path, name)",
        "    reason = None",
    ),
    (
        "taint-in-tier1",
        PYM,
        "            reason = run.taint_reason(caller, caller, name)",
        "            reason = None",
    ),
    (
        "write-position",
        PYM,
        "    if chain and top.id in analysis.attribute_targets:",
        "    if False:",
    ),
    (
        "uses-recorded",
        PYM,
        "        for info in infos:\n            facts.uses.add(_record(info, kind, chain))",
        "        for info in infos:\n            pass",
    ),
    (
        "setattr-write",
        PYM,
        "    name = _setattr_write(analysis, outer)",
        "    name = None",
    ),
    (
        "setattr-builtin-verified",
        PYM,
        "    if not _builtin_at(analysis, callee):\n        return None\n",
        "",
    ),
    (
        "inert-context",
        PYM,
        "    if _inert_context(outer):\n        return None\n",
        "",
    ),
    (
        "dunder-escape",
        PYM,
        "                and name not in _SAFE_DUNDERS\n            ):",
        "                and name not in _SAFE_DUNDERS\n                and False\n            ):",
    ),
    (
        "exposure-closure",
        PYM,
        "                whole[scope].add(other)\n                pending.append(other)",
        "                pass",
    ),
    (
        "star-exposure",
        PYM,
        "                whole[scope].update(builder.exposed(node))",
        "                pass",
    ),
    (
        "dotted-strings",
        PYM,
        '                facts.strings.add(value.replace(":", "."))',
        "                pass",
    ),
    (
        "literal-acquisition",
        PYM,
        '    facts.taints.add((value, "*"))\n    facts.imports.add(value)\n    return True',
        "    return True",
    ),
    (
        "writer-script-directory",
        PYM,
        "            if local in self.nodes:\n                found.add(local)",
        "            if local in self.nodes:\n                pass",
    ),
    (
        "class-scope-exposure",
        PYM,
        '            facts.uses.add(_record(info, "value", ()))',
        "            pass",
    ),
    (
        "inconclusive-lookup",
        PYM,
        '    if kind == "local" or outcome.get("reason") in _OWN_BINDINGS:\n'
        "        return []\n    return infos",
        '    if kind == "local" or outcome.get("reason") in _OWN_BINDINGS:\n'
        "        return []\n    return []",
    ),
    # Run-wide causes.
    (
        "evaluator",
        PYM,
        "        if name in _EVALUATORS and _builtin_at(analysis, ident):",
        "        if False:",
    ),
    (
        "compile-is-no-evaluator",
        PYM,
        '_EVALUATORS = frozenset({"exec", "eval", "execfile"})',
        '_EVALUATORS = frozenset({"exec", "eval", "compile", "execfile"})',
    ),
    (
        "computed-import-module",
        PYM,
        "        if not _literal_module(analysis, first, facts, own_ref):\n"
        "            facts.shutoff.add(CAUSE_DYNAMIC_LOADER)\n        return\n"
        '    if len(path) == 2 and path[1] == "reload":',
        "        _literal_module(analysis, first, facts, own_ref)\n        return\n"
        '    if len(path) == 2 and path[1] == "reload":',
    ),
    (
        "classified-literal",
        PYM,
        '    if value.split(".")[0] in _CLASSIFIED_MODULES:',
        "    if False:",
    ),
    (
        "importlib-closed-list",
        PYM,
        "            return\n    facts.shutoff.add(CAUSE_DYNAMIC_LOADER)\n\n\ndef _scan_causes(",
        "            return\n\n\ndef _scan_causes(",
    ),
    (
        "sys-modules-closed-list",
        PYM,
        "    elif _operand_of_in(node):\n        return\n    facts.shutoff.add(CAUSE_MODULE_SYSTEM)",
        "    elif _operand_of_in(node):\n        return",
    ),
    (
        "sys-path-writes",
        PYM,
        "            if not (len(path) == 2 and _operand_of_in(node_at(1))):",
        "            if False:",
    ),
    (
        "sys-handed-on",
        PYM,
        "            if not inert_value(0):",
        "            if False:",
    ),
    (
        "module-object-attribute-names",
        PYM,
        "        if ps._name_part(ident):\n            if spellings & _MODULE_OBJECT_NAMES:",
        "        if ps._name_part(ident):\n            if False:",
    ),
    (
        "frame-locals-reads",
        PYM,
        '    """``X.f_locals`` used only as a read (a closed list): ``.get(...)``\n'
        '    called, a subscript read, or the right operand of ``in``/``not in``."""\n',
        '    """``X.f_locals`` used only as a read (a closed list): ``.get(...)``\n'
        '    called, a subscript read, or the right operand of ``in``/``not in``."""\n'
        "    return True\n",
    ),
    (
        "runpy",
        PYM,
        "        head in _LOADER_MODULES\n",
        "        False\n",
    ),
    # Parse classification (E5-7 analog).
    (
        "unparsed-cause",
        PYM,
        '            if not supported or bindings.get("unparsed"):',
        "            if not supported:",
    ),
    ("lone-cr", PYM, '    if _LONE_CR.search(source):\n        return "lone-cr"\n', ""),
    (
        "coding",
        PYM,
        "            if _normal_coding(match.group(1)) not in _SAFE_CODINGS:",
        "            if False:",
    ),
    ("tab-space-mix", PYM, "    if tabbed and spaced:", "    if False:"),
    # O-2.
    (
        "test-scope-causes",
        PYM,
        "        if caller in self.test_scope:\n            active.update(self.test_shutoff)",
        "        if True:\n            active.update(self.test_shutoff)",
    ),
    (
        "test-scope-taints",
        PYM,
        "        test = caller in self.test_scope\n",
        "        test = True\n",
    ),
    (
        "promotion",
        PYM,
        "            for target in sorted(reached - production):\n"
        "                production.add(target)\n                pending.append(target)",
        "            for target in sorted(reached - production):\n                pass",
    ),
    (
        "classifier-conftest",
        PYM,
        "        name == TEST_CONFTEST\n",
        "        False\n",
    ),
    (
        "directory-symlinks",
        PYM,
        "    if directory_symlinks is not False:\n        return frozenset(files)\n",
        "",
    ),
    # Engine.
    (
        "caller-shutoff",
        PYM,
        "    shutoff = run.caller_shutoff(importer)\n    if shutoff is not None:\n"
        "        return _none(shutoff)\n    if binding.get",
        "    if binding.get",
    ),
    (
        "import-groups",
        ENG,
        "        bindings = list(py_file.groups.get(key, ())) if key else []",
        "        bindings = []",
    ),
)


def _pytest(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-q",
            "-x",
            "-rf",
            "-o",
            "addopts=--tb=no",
            *TESTS,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tier2-py-mutations-") as tmp:
        copy = Path(tmp) / "repo"
        copy.mkdir()
        for name in ("chunker", "tests", "scripts"):
            shutil.copytree(ROOT / name, copy / name)
        shutil.copy2(ROOT / "pyproject.toml", copy / "pyproject.toml")
        baseline = _pytest(copy)
        if baseline.returncode != 0:
            print(baseline.stdout[-2000:])
            print("baseline fails; no mutation is meaningful", file=sys.stderr)
            return 2
        bad = 0
        for ident, relative, old, new in MUTATIONS:
            path = copy / relative
            original = path.read_text(encoding="utf-8")
            if original.count(old) != 1:
                print(f"NOT-APPLIED\t{ident}\t{relative}")
                bad += 1
                continue
            path.write_text(original.replace(old, new, 1), encoding="utf-8")
            try:
                result = _pytest(copy)
            except subprocess.TimeoutExpired:
                # A hang (for example a lexer that stops advancing) is a
                # failing test run: the mutation is killed.
                print(f"KILLED\t{ident}\ttimeout (hang)")
                continue
            finally:
                path.write_text(original, encoding="utf-8")
            failed = next(
                (
                    line.removeprefix("FAILED ")
                    for line in result.stdout.splitlines()
                    if line.startswith("FAILED ")
                ),
                "",
            )
            if result.returncode not in (0, 1):
                # A collection or import error is not a kill: the edit broke
                # the copy instead of disabling a rule.
                print(f"BROKEN\t{ident}\texit {result.returncode}")
                bad += 1
                continue
            killed = result.returncode == 1
            bad += not killed
            print(f"{'KILLED' if killed else 'SURVIVED'}\t{ident}\t{failed}")
        total = len(MUTATIONS)
        print(f"{total - bad}/{total} killed")
        return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
