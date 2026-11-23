"""Rule mutations for Tier 2 Python call resolution (treesitter-chunker#682 PR 6).

Each mutation disables one rule by a single textual edit. The script copies
the checkout to a temporary directory, checks that the unmutated copy passes,
then applies each mutation alone and runs the Tier 2 Python tests and the
``imports`` expected-table test serially. A mutation is *killed* when a test
fails. The script prints one tab-separated line per mutation and exits
non-zero if any mutation survives or does not apply.

Usage (Python 3.14, from the repository root)::

    uv run --locked --all-extras python scripts/call_resolution_tier2_py_mutations.py [ID ...]

With mutation ids as arguments, only those run.

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
    "tests/test_call_resolution_py_getters.py",
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
        '    if chain and top.id in analysis.attribute_targets:\n        return "write", chain, outer',
        '    if False:\n        return "write", chain, outer',
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
        "        return _none(shutoff)\n    value = _resolve_binding(",
        "    value = _resolve_binding(",
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
        "        if not isinstance(start, _Module) or len(parts) < 2:",
        "        if True:",
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
        "        if constant is None:\n            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)\n        else:\n            facts.taints.add",
        "        if False:\n            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)\n        else:\n            facts.taints.add",
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
        "e6-9-mp-alias-fixpoint",
        PYM,
        "                if name not in self.mockers:",
        "                if False:",
    ),
    (
        "e6-9-getfixturevalue-mocker",
        PYM,
        "    mockers = _MOCKER_NAMES | patchers.mockers",
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
        "p6-5-fixture-mocker-escapes",
        PYM,
        "        if patchers.kind(node) is not None and not analysis._safe_use(node, ps._MOCKER):",
        "        if False:",
    ),
    # Fold 5 (#705 P6-10..P6-15; E6-9a).
    (
        "p6-10-syspath-prepend",
        PYM,
        "        if method == _SYSPATH_METHOD:\n            facts.shutoff.add(CAUSE_MODULE_SYSTEM)\n            continue",
        "        if method == _SYSPATH_METHOD:\n            continue",
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
        "            elif _argument_string(node, self.source) == _GETFIXTUREVALUE:",
        "            elif False:",
    ),
    (
        "p6-13-every-file",
        PYM,
        "    _scan_patcher_escapes(analysis, facts, patchers)\n    hazard",
        "    if not analysis.dynamic:\n"
        "        _scan_patcher_escapes(analysis, facts, patchers)\n    hazard",
    ),
    # Fold 6 (#705 E6-9b: MonkeyPatch methods on any receiver).
    (
        "e6-9b-receiver-kind",
        PYM,
        "        if _operator_module(analysis, receiver):\n            continue",
        '        if ps._text(receiver, source) != "monkeypatch":\n            continue',
    ),
    (
        "e6-9b-method-name-string",
        PYM,
        "        if name in _WRITE_METHODS:\n            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)",
        "        if False:\n            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)",
    ),
    (
        "e6-9b-syspath-name-string",
        PYM,
        "        elif name == _SYSPATH_METHOD:",
        "        elif False:",
    ),
    (
        "e6-9b-method-reference",
        PYM,
        "        if call is None:\n            facts.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)",
        "        if call is None:\n            pass",
    ),
    (
        "e6-9b-second-argument",
        PYM,
        "        if ps._constant_string(positional[1], source) is None:",
        "        if False:",
    ),
    (
        "e6-9b-keyword-target",
        PYM,
        "                and ps._text(key, source) in _MP_FIXTURE_ARGUMENTS",
        "                and False",
    ),
    (
        "e6-9b-splat",
        PYM,
        '        if argument.type in ("list_splat", "dictionary_splat"):',
        "        if False:",
    ),
    # Fold 7 (#705 P6-21, P6-22).
    (
        "p6-21-literal-only",
        PYM,
        "    if node.type not in _NAME_STRING_NODES or node.parent is None:",
        '    if node.type != "string" or node.parent is None:',
    ),
    (
        "p6-21-keyword-value",
        PYM,
        '    if parent.type == "keyword_argument" and ps._same(',
        "    if False and ps._same(",
    ),
    (
        "p6-22-subscript-key",
        PYM,
        '    if parent.type == "subscript":',
        '    if parent.type == "subscript" and False:',
    ),
    # Fold 8 (#705, Codex r4661935648): one binding resolver.
    (
        "f8-reexport-bypasses-resolver",
        PYM,
        "        return _resolve_binding(\n"
        '            run, caller, entry.get("binding") or {}, value.path, hops + 1, seen\n'
        "        )",
        '        binding = entry.get("binding") or {}\n'
        '        if binding.get("form") == "import":\n'
        '            return resolve_module(run, str(binding.get("bound") or ""), value.path)\n'
        "        return _resolve_binding(\n"
        "            run, caller, binding, value.path, hops + 1, seen\n"
        "        )",
    ),
    (
        "f8-writer-attribute-walk",
        PYM,
        "            found |= current\n",
        "            pass\n",
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
    # treesitter-chunker#724: a namespace reader hands out its import
    # bindings.
    (
        "ns-reader-hands-out-imports",
        PYM,
        "    if handout is None or handout:\n        # #724",
        "    if False:\n        # #724",
    ),
    (
        "ns-names",
        PYM,
        "            read = _frame_read_keys(analysis, ident)\n            if read is None:\n"
        "                return None\n            keys |= read\n            continue\n",
        "            pass\n",
    ),
    ("ns-frame-key", PYM, "            keys |= read\n", "            pass\n"),
    (
        "ns-frame-computed-key",
        PYM,
        "    return None if value is None else frozenset({value})",
        "    return frozenset() if value is None else frozenset({value})",
    ),
    (
        "ns-frame-read-only",
        PYM,
        "    if not _frame_locals_read(analysis, ident):\n        return None\n    outer",
        "    outer",
    ),
    (
        "ns-getmodule",
        PYM,
        '        "getmodule",\n        "getargvalues",',
        '        "getargvalues",',
    ),
    (
        "ns-annotation-evaluator",
        PYM,
        '        "get_type_hints",\n        "get_annotations",',
        '        "get_annotations",',
    ),
    (
        "ns-builtin-lookup",
        PYM,
        "    outcome = analysis.lookup(ident)\n"
        '    if outcome.get("outcome") == "local" or outcome.get("reason") in _OWN_BINDINGS:\n'
        "        return False\n    call = ps._callee_call(ident)\n    if call is None:\n"
        "        # Handed on",
        "    call = ps._callee_call(ident)\n    if call is None:\n        # Handed on",
    ),
    (
        "ns-handed-on",
        PYM,
        "        # Handed on (``g = globals``; ``run(vars)``): it may be called here.\n"
        "        return True\n",
        "        return False\n",
    ),
    (
        "ns-vars-argument",
        PYM,
        "        return not (len(positional) == 1 and len(arguments) == 1)",
        "        return True",
    ),
    (
        "ns-explicit-globals",
        PYM,
        '        return bool(namespace.type == "none")',
        "        return True",
    ),
    (
        "ns-none-globals",
        PYM,
        '        return bool(namespace.type == "none")',
        "        return False",
    ),
    (
        "ns-keyword-globals",
        PYM,
        '                if key is not None and ps._text(key, analysis.source) == "globals":',
        "                if False:",
    ),
    (
        "ns-import-form",
        PYM,
        "            # spelled at its uses.\n            return None",
        "            # spelled at its uses.\n            continue",
    ),
    (
        "ns-builtins-members",
        PYM,
        "    if routes and (members or builtin_strings):",
        "    if routes and builtin_strings:",
    ),
    (
        "ns-members-receiver",
        PYM,
        "    if routes and (members or builtin_strings):",
        "    if members or builtin_strings:",
    ),
    (
        "ns-strings",
        PYM,
        "        if set(ps._NAME_SEPARATORS.split(value)) & _NAMESPACE_NAMES:\n            return None",
        "        if False:\n            return None",
    ),
    (
        "ns-f_builtins-route",
        PYM,
        '"__self__", "f_builtins"}',
        '"__self__"}',
    ),
    (
        "ns-builtin-strings",
        PYM,
        "            builtin_strings = True",
        "            pass",
    ),
    (
        "ns-dunder-import",
        PYM,
        "            if _own_import(analysis, ident):\n                return None",
        "            if False:\n                return None",
    ),
    (
        "ns-dunder-import-constant",
        PYM,
        "    return first is None or ps._constant_string(first, analysis.source) is None",
        "    return True",
    ),
    # treesitter-chunker#706 slice 1: tracked getters and call results.
    (
        "getter-decorated",
        PYM,
        '        if child.type != "function_definition":\n            continue\n'
        '        if any(token.type == "async"',
        '        if child.type == "decorated_definition":\n'
        '            child = child.child_by_field_name("definition")\n'
        '        if child is None or child.type != "function_definition":\n'
        "            continue\n"
        '        if any(token.type == "async"',
    ),
    (
        "getter-async",
        PYM,
        '        if any(token.type == "async" for token in child.children):\n'
        "            continue\n",
        "",
    ),
    (
        "getter-generator",
        PYM,
        "        if name is None or _own_yield(child):",
        "        if name is None:",
    ),
    ("getter-dunder", PYM, "        if not ps._dunder(text):", "        if True:"),
    (
        "getter-nested-return",
        PYM,
        "    scope = _scope_node(parent)\n"
        "    return getters.get(scope.id) if scope is not None else None",
        "    scope = parent.parent\n"
        "    while scope is not None and scope.id not in getters:\n"
        "        scope = scope.parent\n"
        "    return getters.get(scope.id) if scope is not None else None",
    ),
    (
        "getter-conditional-def",
        PYM,
        "    found: dict[int, str] = {}\n"
        "    for child in analysis.root.named_children:\n",
        "    found: dict[int, str] = {}\n"
        "    stack, nodes = [analysis.root], []\n"
        "    while stack:\n"
        "        node = stack.pop()\n"
        "        stack.extend(node.named_children)\n"
        '        if node.type == "function_definition" and (\n'
        '            _scope_node(node).type == "module"\n'
        "        ):\n"
        "            nodes.append(node)\n"
        "    for child in nodes:\n",
    ),
    (
        "getter-introspection-gate",
        PYM,
        "    gate = handout is None or _introspects(analysis, reader=False)",
        "    gate = handout is None",
    ),
    (
        "h1-namespace-names",
        PYM,
        "    if any(\n        ps._spellings(ident, source) & _INTROSPECTION_NAMES\n",
        "    if False and any(\n        ps._spellings(ident, source) & _INTROSPECTION_NAMES\n",
    ),
    (
        "return-shape",
        PYM,
        '    if parent is not None and parent.type in ("expression_list", "tuple"):',
        '    if parent is not None and parent.type in ("expression_list", "tuple", "list"):',
    ),
    (
        "return-ref",
        PYM,
        "                facts.uses.add(record)\n            continue\n",
        "            continue\n",
    ),
    (
        "own-reference",
        PYM,
        '                records.add(("", "own-value", spelling, CALL_MARK))',
        "                pass",
    ),
    (
        "cross-file-reference",
        PYM,
        "            self.hand_on(current, name, whole)\n            following",
        "            following",
    ),
    (
        "exposed-getters",
        PYM,
        '            for name in self.getters_of(path or ""):\n'
        '                found |= self.returned((path or "", name))\n',
        "",
    ),
    (
        "reexport-walk",
        PYM,
        '            if binding.get("form") != "from":\n                continue\n'
        '            for start in self.targets(str(binding.get("module") or ""), path):\n'
        "                found |= self.getter_values(",
        "            continue\n"
        '            for start in self.targets(str(binding.get("module") or ""), path):\n'
        "                found |= self.getter_values(",
    ),
    (
        "result-value",
        PYM,
        "        for ref, prefix in sources:\n            emit(ref, prefix, position, chain)\n"
        "        return False\n",
        '        for ref, prefix in sources:\n            if position == "write":\n'
        "                emit(ref, prefix, position, chain)\n        return False\n",
    ),
    (
        "result-write",
        PYM,
        '        kind = position.split("-", 1)[1]\n        if not callee:',
        '        kind = position.split("-", 1)[1].replace("write", "call")\n'
        "        if not callee:",
    ),
    (
        "result-dunder",
        PYM,
        '        if position == "call" and not _unsafe_dunder(chain):',
        '        if position == "call":',
    ),
    (
        "alias-dunder",
        PYM,
        "                if _unsafe_dunder(full) or len(full) > MAX_ALIAS_CHAIN:",
        "                if len(full) > MAX_ALIAS_CHAIN:",
    ),
    (
        "call-step-cap",
        PYM,
        "                if prefix.count(CALL_MARK) + 1 >= CALL_STEPS:",
        "                if False:",
    ),
    (
        "result-member-call",
        PYM,
        "            return bool(following) and handle(following, found[2])",
        "            return False",
    ),
    (
        "result-call-step",
        PYM,
        "                        for inner in self.getter_values(node, segment[-1]):\n"
        "                            current |= self.returned(inner)",
        "                        pass",
    ),
    (
        "alias-scope",
        PYM,
        "    if any(name in scope.globals or name in scope.nonlocals for name in names):\n"
        "        return None\n",
        "",
    ),
    (
        "alias-target-shape",
        PYM,
        '        if not targets or any(c.type != "identifier" for c in targets):',
        "        if not targets:",
    ),
    (
        "alias-unplaced-read",
        PYM,
        "                if decided is not None and id(decided) != scope_id:",
        "                if id(decided) != scope_id:",
    ),
    (
        "alias-other-scope",
        PYM,
        "                if decided is not None and id(decided) != scope_id:\n"
        "                    continue\n",
        "",
    ),
    (
        "alias-new-reads",
        PYM,
        "        alias_names = {name for _scope, name in aliases}\n        for ident in reads:",
        "        alias_names = alias_names if 'alias_names' in dir() else "
        "{name for _scope, name in aliases}\n        for ident in reads:",
    ),
    (
        "result-scope",
        PYM,
        '        for use in bindings.get("uses", ()):\n            builder.walk_use(\n',
        '        for use in bindings.get("uses", ()):\n'
        "            scope = scope or str(use[1]) in RESULT_POSITIONS\n"
        "            builder.walk_use(\n",
    ),
    # Equivalent (recorded, not run) for #706: ``subscript-literal`` (a
    # getter returns modules or one tuple level of them; any other key
    # raises or yields an element the over-approximation already covers).
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


def main(argv: list[str] | None = None) -> int:
    """Run every mutation, or only the ids given as arguments."""
    only = set(sys.argv[1:] if argv is None else argv)
    unknown = only - {m[0] for m in MUTATIONS}
    if unknown:
        print(f"unknown mutation ids: {sorted(unknown)}", file=sys.stderr)
        return 2
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
        selected = [m for m in MUTATIONS if not only or m[0] in only]
        for ident, relative, old, new in selected:
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
        total = len(selected)
        print(f"{total - bad}/{total} killed")
        return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
