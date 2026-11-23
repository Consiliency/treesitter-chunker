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
        "    if entry is not None and (submodule is not None or probe is not None):",
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
        "    reason = run.taint_reason(caller, caller, name)\n    if reason is not None:\n        return reason\n    file = run.files.get(caller)",
        "    file = run.files.get(caller)",
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
        "                if local in self.nodes:\n                    found.add(local)",
        "                if local in self.nodes:\n                    pass",
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
        "            if spellings & _MODULE_OBJECT_NAMES:\n"
        "                facts.shutoff.add(CAUSE_MODULE_OBJECT)\n"
        "            if spellings & _RESOLVER_NAMES:",
        "            if False:\n"
        "                facts.shutoff.add(CAUSE_MODULE_OBJECT)\n"
        "            if spellings & _RESOLVER_NAMES:",
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
        '            if not supported or bindings.get("unparsed") or not bindings:',
        "            if not supported or not bindings:",
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
    # PR 6 fold 2 (#705 E6-1..E6-8).
    (
        "e6-1-own-binding",
        ENG,
        "            py_modules.own_binding_reason(run, file_context.path, head)\n"
        "            if head\n            else None",
        "            None",
    ),
    (
        "e6-1-package-submodule-binding",
        PYM,
        "    if file is not None and file.package:\n        base = caller",
        "    if False:\n        base = caller",
    ),
    (
        "e6-1-tier1-own-binding",
        PYM,
        "            reason = own_binding_reason(run, caller, name)",
        "            reason = run.taint_reason(caller, caller, name)",
    ),
    (
        "e6-2-module-imports-recorded",
        PYM,
        "        if scope.kind == ps._MODULE or name in scope.globals:",
        "        if False:",
    ),
    (
        "e6-2-module-imports-attr",
        PYM,
        "        for binding in file.module_imports.get(name, ()):\n"
        "            # E6-2: any import binding of the name, proven or not.\n"
        '            found |= self.binding_values(binding, path or "", seen)',
        "        pass",
    ),
    (
        "e6-2-module-imports-exposed",
        PYM,
        "            for bindings in file.module_imports.values():\n"
        "                for binding in bindings:\n"
        '                    found |= self.binding_values(binding, path or "", set())',
        "            pass",
    ),
    (
        "e6-3-import-as-attribute",
        PYM,
        "        if isinstance(start, _Module) and len(parts) > 1:",
        "        if False:",
    ),
    (
        "e6-3-own-submodule-allowed",
        PYM,
        "        if submodule is not None and _own_submodule_import(file, entry, name):",
        "        if False:",
    ),
    (
        "e6-3-module-getattr",
        PYM,
        '        if file.package and "__getattr__" in file.exports:',
        "        if False:",
    ),
    (
        "a-3-dynamic-package-submodule",
        PYM,
        '            return submodule if file.missing == "export-not-found" else file.missing',
        "            return submodule",
    ),
    (
        "s-1-skipped-submodule-probe",
        PYM,
        "            # name) may still exist.\n            probe = found",
        "            # name) may still exist.\n            pass",
    ),
    (
        "e6-4-pytest-basedir",
        PYM,
        "    if is_test_path(importer):\n        current = directory",
        "    if False:\n        current = directory",
    ),
    (
        "e6-5-computed-patch",
        PYM,
        "            if first is None or constant is None:\n"
        "                facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)",
        "            if False:\n                facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)",
    ),
    (
        "e6-5-computed-patch-object",
        PYM,
        "            if second is None or ps._constant_string(second, source) is None:",
        "            if False:",
    ),
    (
        "e6-5-computed-monkeypatch",
        PYM,
        "            if string_form and constant is None:",
        "            if False:",
    ),
    (
        "e6-5-whole-module-patch-target",
        PYM,
        "        elif method:\n            if constant is not None:",
        "        elif method:\n            if False:",
    ),
    # Fold 3 (#705 P6-1..P6-4, N-1).
    (
        "p6-1-own-import-full-name",
        PYM,
        '(module == "." or bool(own_ref) and module == own_ref)',
        '(module == "." or module.rpartition(".")[2] == own_ref.rpartition(".")[2])',
    ),
    (
        "p6-2-star-init-has-no-own-submodules",
        PYM,
        "    if not analysis.module_path.package_init or stars:",
        "    if not analysis.module_path.package_init:",
    ),
    (
        "p6-2-star-init-at-assembly",
        PYM,
        "    return file.package and not file.stars and name in file.own_submodules",
        "    return file.package and name in file.own_submodules",
    ),
    (
        "p6-3-w3-patch-aliases",
        PYM,
        "        if node is not None and analysis._sensitive(node, ps._PATCH):",
        "        if False:",
    ),
    (
        "e6-9-mp-receiver",
        PYM,
        '            last in ("setattr", "delattr")\n'
        "            and receiver is not None\n"
        "            and patchers.kind(receiver) == _INSTANCE",
        '            last in ("setattr", "delattr")\n'
        "            and receiver is not None\n"
        "            and False",
    ),
    (
        "p6-3-computed-method-target",
        PYM,
        "                # (and ``patch.dict`` alike) names a target no rule computes.\n"
        "                facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)",
        "                # (and ``patch.dict`` alike) names a target no rule computes.\n"
        "                pass",
    ),
    (
        "p6-4-run-wide-pytest-basedirs",
        PYM,
        "        for basedir in pytest_basedirs(files):",
        "        for basedir in ():",
    ),
    (
        "p6-4-conftest-is-imported",
        PYM,
        "    return name == TEST_CONFTEST or (",
        "    return (",
    ),
    (
        "n-1-code-attribute-write",
        PYM,
        "                # N-1: ``f.__code__ = other.__code__`` (any receiver).\n"
        "                facts.shutoff.add(CAUSE_MODULE_OBJECT)",
        "                pass",
    ),
    (
        "n-1-code-attribute-string",
        PYM,
        "            if value in _CODE_ATTRIBUTES:",
        "            if False:",
    ),
    # Fold 4 (#705 E6-9: P6-5, P6-6, P6-7).
    (
        "e6-9-mp-import-alias",
        PYM,
        "                            self.classes.update(ps._spellings(bound, self.source))",
        "                            pass",
    ),
    (
        "e6-9-mp-alias-fixpoint",
        PYM,
        "                if name not in self.names[kind]:",
        "                if False:",
    ),
    (
        "e6-9-getfixturevalue-instance",
        PYM,
        "            if value == _MP_FIXTURE:\n                return _INSTANCE\n",
        "",
    ),
    (
        "e6-9-getfixturevalue-mocker",
        PYM,
        "    mockers = _MOCKER_NAMES | patchers.names[_FIXTURE_MOCKER]",
        "    mockers = _MOCKER_NAMES",
    ),
    (
        "e6-9-computed-fixture-name",
        PYM,
        "                    self.computed_fixture = True",
        "                    pass",
    ),
    (
        "p6-5-tier1-kind-escapes",
        PYM,
        "            if analysis._sensitive(node, kind) and not analysis._safe_use(node, kind):",
        "            if False:",
    ),
    (
        "p6-5-monkeypatch-escapes",
        PYM,
        "        if patcher is not None and not patchers.safe_use(node, patcher):",
        "        if False:",
    ),
    (
        "e6-9-mp-method-allow-list",
        PYM,
        '            return name in _MP_METHODS if kind == _INSTANCE else name == "context"',
        "            return False",
    ),
    (
        "e6-9-annotation-allowed",
        PYM,
        '        if above is not None and above.type == "type":',
        "        if False:",
    ),
    # Fold 5 (#705 P6-10..P6-15; E6-9a).
    (
        "p6-10-syspath-prepend",
        PYM,
        "            # ``SHADOW.t`` (``f4_mp_syspath_prepend``).\n"
        "            facts.shutoff.add(CAUSE_MODULE_SYSTEM)",
        "            # ``SHADOW.t`` (``f4_mp_syspath_prepend``).\n            pass",
    ),
    (
        "p6-11-unreachable-alias-only",
        PYM,
        'return target.type == "identifier" and not self.analysis._reachable_binding(',
        'return target.type == "identifier" or self.analysis._reachable_binding(',
    ),
    (
        "p6-12-getfixturevalue-attribute",
        PYM,
        '            elif node.type == "attribute" and self._fixture_attribute(node):',
        "            elif False:",
    ),
    (
        "p6-15-getfixturevalue-string",
        PYM,
        '            elif node.type == "string" and (',
        "            elif False and (",
    ),
    (
        "p6-13-every-file",
        PYM,
        "    _scan_patcher_escapes(analysis, facts, patchers)\n    hazard",
        "    if not analysis.dynamic:\n"
        "        _scan_patcher_escapes(analysis, facts, patchers)\n    hazard",
    ),
    (
        "p6-14-annotation-chain",
        PYM,
        "        while above is not None and above.type in _ANNOTATION_PARTS:",
        '        while above is not None and above.type not in ("type", "block", "module"):',
    ),
    (
        "e6-6-first-attribute-write",
        PYM,
        '        if position == "write" and len(chain) > 1:',
        "        if False:",
    ),
    (
        "e6-7-path-read-safe",
        PYM,
        '        "__path__",\n        "__spec__",',
        '        "__spec__",',
    ),
    (
        "e6-8-tier2-only-in-imports",
        CR + "facts.py",
        '                tier2=mode in (None, "imports"),',
        "                tier2=True,",
    ),
    (
        "e6-8-missing-module-facts-fail-closed",
        PYM,
        '            if not supported or bindings.get("unparsed") or not bindings:',
        '            if not supported or bindings.get("unparsed"):',
    ),
    # Panel B's surviving extra mutations (#705 S3), now killed.
    (
        "b-string-module-object-names",
        PYM,
        '            if parts & (_MODULE_OBJECT_NAMES - {"__main__", "__mp_main__"}):',
        "            if False:",
    ),
    (
        "b-string-f-locals",
        PYM,
        "            if _FRAME_LOCALS in parts:",
        "            if False:",
    ),
    (
        "b-main-guard",
        PYM,
        "and not analysis._main_guard(node):",
        "and False:",
    ),
    (
        "b-sys-dunder",
        PYM,
        "        elif ps._dunder(member):\n            facts.shutoff.add(CAUSE_MODULE_SYSTEM)\n",
        "",
    ),
    (
        "b-loader-paths",
        PYM,
        "        or tuple(path[:3]) in _LOADER_PATHS\n        or tuple(path[:2]) in _LOADER_PATHS\n",
        "",
    ),
    (
        "b-resolver-identifier",
        PYM,
        "        if spellings & _RESOLVER_NAMES:\n            facts.shutoff.add(CAUSE_DYNAMIC_LOADER)\n"
        "        if name in _EVALUATORS",
        "        if name in _EVALUATORS",
    ),
    (
        "b-relative-import-module",
        PYM,
        '            facts.taints.add((absolute, "*"))',
        "            pass",
    ),
    (
        "b-dunder-import-head",
        PYM,
        '                facts.taints.add((value.split(".")[0], "*"))',
        "                pass",
    ),
    (
        "b-inert-comparison-ops",
        PYM,
        '            op in ("is", "is not", "not") for op in operators',
        "            True for op in operators",
    ),
    (
        "b-promotion-string-edges",
        PYM,
        '        refs += [str(string) for string in bindings.get("strings", ())]\n',
        "",
    ),
    (
        "b-promotion-taint-edges",
        PYM,
        '        refs += [str(taint[0]) for taint in bindings.get("taints", ())]\n',
        "",
    ),
    (
        "b-coding-second-line",
        PYM,
        "    for line in lines[:2]:",
        "    for line in lines[:1]:",
    ),
    (
        "b-ctrl-z",
        PYM,
        '_HAZARD_BYTES = (b"\\x00", b"\\x0b", b"\\x1a")',
        '_HAZARD_BYTES = (b"\\x00", b"\\x0b")',
    ),
    (
        "b-exec-statement",
        PYM,
        '        if kind == "exec_statement":\n            facts.shutoff.add(CAUSE_EVALUATOR)',
        '        if kind == "exec_statement":\n            pass',
    ),
    (
        "b-missing-reason-fact",
        PYM,
        '        if missing.get("reason") == "unbound"',
        "        if True",
    ),
    # Equivalent (recorded, not run): ``continuation`` (tree-sitter reports
    # every malformed continuation as an error first), ``own-name-acquisition``
    # (``sys.modules[__name__]`` already makes the file dynamic in Tier 1, so
    # its exports fail closed), ``chain-matches-reference`` (the tree's chain
    # and the reference are built from the same tokens), ``setattr-splat``
    # (a splat makes the ``setattr`` argument a value, an escape, which taints
    # more), and ``unresolvable-writer-assembly`` (the unreachable branch is
    # removed; every recorded taint reference is absolute).
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
