"""Rule mutations for Tier 2 Python call resolution (treesitter-chunker#682 PR 6).

Each mutation disables one rule by a single textual edit. The script copies
the checkout to a temporary directory, checks that the unmutated copy passes,
then applies each mutation alone and runs the Tier 2 Python tests, the
``imports`` expected-table test, the shared K-3 main-string regressions
and the Tier 1 half of the shared S2 string-code classifier serially. A mutation is *killed* when a test fails. The script prints one
tab-separated line per mutation and exits non-zero if any mutation survives
or does not apply.

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
PYS = CR + "py_scope.py"
ENG = CR + "engine.py"
T1 = "tests/test_call_resolution_tier1_py.py::"
TESTS = (
    "tests/test_call_resolution_tier2_py.py",
    "tests/test_call_resolution_engine.py::test_expected_imports_tables_hold_at_this_head",
    # treesitter-chunker#699 S2: the shared string-code classifier's Tier 1
    # half (the list pins are left out, so behaviour must kill each one).
    T1 + "test_string_code_fails_closed_file_wide",
    T1 + "test_string_code_controls_still_resolve",
    T1 + "test_own_bindings_of_code_builtins_leave_function_proofs_alone",
    T1 + "test_module_level_binding_of_a_code_builtin_is_builtin_shadow",
    T1 + "test_string_code_local_controls_still_resolve",
    T1 + "test_stdlib_reexports_hold_and_fail_closed",
    T1 + "test_string_code_inside_the_function_defeats_its_own_proof",
    T1 + "test_mock_scoped_computed_getters_fail_closed",
    T1 + "test_computed_getters_outside_mock_files_or_constant_still_resolve",
    T1 + "test_installed_builtins_never_prove_at_module_level",
    T1 + "test_each_string_code_name_counts_in_every_position",
    T1 + "test_s2_traced_routes_keep_their_off_mode_edge",
    T1 + "test_s2_installed_builtin_route_keeps_its_off_mode_edge",
    # treesitter-chunker#698 (#714): the main-string classifier's Tier 1 pins.
    T1 + "test_main_format_strings_fail_closed",
    T1 + "test_main_string_components_fail_closed",
    T1 + "test_scope_facts_ignore_the_warnings_filters",
    T1 + "test_decode_literal_matches_cpython",
    T1 + "test_constant_fstrings_match_cpython_through_the_tree",
    T1 + "test_main_substring_rule_is_sound_against_cpython",
    T1 + "test_main_anywhere_in_an_fstring_fails_closed",
    T1 + "test_fstring_without_main_resolves",
    T1 + "test_unreadable_fstring_bytes_fail_closed",
    T1 + "test_main_needs_a_whole_component",
    T1 + "test_main_guard_resolves_the_call_in_its_body",
    # treesitter-chunker#699 S4: the Tier 1 halves of PY-7 and PY-10.
    T1 + "test_gc_off_its_member_list_fails_closed_file_wide",
    T1 + "test_gc_member_list_controls_still_resolve",
    T1 + "test_gc_traced_routes_fail_closed",
    T1 + "test_patch_on_any_receiver_fails_closed",
    T1 + "test_patch_on_any_receiver_controls_still_resolve",
    # Ruling R-699-10: imported patchers from any module, in Tier 1.
    T1 + "test_r10_imported_patchers_fail_closed",
    T1 + "test_r10_imported_patch_multiple_fails_closed",
    T1 + "test_r10_imported_patcher_controls_still_resolve",
    T1 + "test_r11_private_patchers_on_any_receiver_fail_closed",
    T1 + "test_r12_patch_tokens_fail_closed",
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
    # #699 S2: Tier 2 reads the shared classifier (one classifier per side,
    # the fold-8 precedent); ``compile`` is an evaluator since B-1.
    (
        "evaluator",
        PYM,
        "    if analysis.string_code or analysis.legacy_evaluator():\n"
        "        facts.shutoff.add(CAUSE_EVALUATOR)",
        "    if False:\n        facts.shutoff.add(CAUSE_EVALUATOR)",
    ),
    (
        "b1-code-objects-cause",
        PYM,
        "    if analysis.code_objects:\n        facts.shutoff.add(CAUSE_MODULE_OBJECT)",
        "    if False:\n        facts.shutoff.add(CAUSE_MODULE_OBJECT)",
    ),
    (
        "b1-code-reads",
        PYS,
        '        "__code__",\n        "gi_code",\n        "cr_code",\n        "ag_code",\n'
        '        "f_code",\n        "co_code",\n        "co_names",\n        "co_consts",\n'
        '        "co_varnames",\n        "co_freevars",\n        "co_cellvars",\n'
        '        "dis",\n        "codeobj",',
        '        "gi_code",\n        "cr_code",\n        "ag_code",\n'
        '        "f_code",\n        "co_code",\n        "co_names",\n        "co_consts",\n'
        '        "co_varnames",\n        "co_freevars",\n        "co_cellvars",\n'
        '        "dis",\n        "codeobj",',
    ),
    (
        "b1-compile-is-an-evaluator",
        PYS,
        '_CODE_BUILTINS = frozenset({"exec", "eval", "execfile", "compile", "breakpoint"})',
        '_CODE_BUILTINS = frozenset({"exec", "eval", "execfile", "breakpoint"})',
    ),
    (
        "b4-breakpoint",
        PYS,
        '_CODE_BUILTINS = frozenset({"exec", "eval", "execfile", "compile", "breakpoint"})',
        '_CODE_BUILTINS = frozenset({"exec", "eval", "execfile", "compile"})',
    ),
    (
        "py1-drop-name",
        PYS,
        '        "doctest",\n        "fileConfig",\n',
        '        "doctest",\n',
    ),
    (
        "py1-drop-module",
        PYS,
        '    {"cProfile", "profile", "bdb", "pdb", "trace", "code", "codeop", "doctest"}',
        '    {"cProfile", "profile", "bdb", "pdb", "code", "codeop", "doctest"}',
    ),
    (
        "py1-pickle-loads-safe",
        PYS,
        '        "dumps",\n        "dump",\n        "Pickler",',
        '        "dumps",\n        "loads",\n        "dump",\n        "Pickler",',
    ),
    (
        "py1-timeit-safe",
        PYS,
        '    "timeit": frozenset({"default_timer"}),',
        '    "timeit": frozenset({"default_timer", "timeit"}),',
    ),
    (
        "py1-skip-use-site-lookup",
        PYS,
        '        return outcome.get("outcome") == "local" or (\n'
        '            outcome.get("outcome") == "none"\n'
        '            and outcome.get("reason") in _OWN_BINDING_REASONS\n        )',
        "        return False",
    ),
    (
        "py1-pickle-any-receiver",
        PYS,
        "                    if parent.id not in self.attribute_targets:\n"
        '                        self.string_checks.append(("module:pickle", parent))',
        "                    pass",
    ),
    (
        "b4-forkingpickler",
        PYS,
        '        "ForkingPickler",\n        "_ForkingPickler",\n',
        '        "_ForkingPickler",\n',
    ),
    (
        "py3-runpy-two-positional",
        PYS,
        "        return positional == 1\n",
        "        return positional in (1, 2)\n",
    ),
    (
        "py2-annotation-raw-text",
        PYS,
        '            and (value is None or "(" in value or ":=" in value)\n',
        '            and ("(" in _text(node, source) or ":=" in _text(node, source))\n',
    ),
    (
        "b5-annotations-write",
        PYS,
        "            if _ANNOTATIONS in spellings and not self._attribute_read(ident):",
        "            if False:",
    ),
    (
        "py8-file-wide",
        PYS,
        "        if self.string_code:\n            self.dynamic = True\n            self.frame_locals = True",
        "        if self.string_code:\n            self.dynamic = True",
    ),
    (
        "b2-marshal-attribute-module-only",
        PYS,
        '                    self._fire("marshal")  # ``pstats.marshal``',
        "                    self.dynamic = True  # ``pstats.marshal``",
    ),
    (
        "py8-exec-from-builtins",
        PYS,
        "            if module in _BUILTIN_MODULES and last in _CODE_BUILTINS:",
        "            if False:",
    ),
    (
        "builtins-reach-gate",
        PYS,
        "        if builtin_mentions and self.builtins_reach:",
        "        if builtin_mentions:",
    ),
    (
        "dotted-name-gate",
        PYS,
        "        if not _DOTTED_NAME.fullmatch(value):\n            return\n",
        "",
    ),
    (
        "generic-module-acquisition",
        PYS,
        "        if head in _GENERIC_MODULE_STRINGS and (",
        "        if False and (",
    ),
    # R-699-3 (the #727 fold).
    (
        "r3-legacy-evaluator",
        PYM,
        "    if analysis.string_code or analysis.legacy_evaluator():",
        "    if analysis.string_code:",
    ),
    (
        "r3-legacy-evaluator-lookup",
        PYS,
        "            outcome = self.lookup(node)\n"
        '            if outcome.get("outcome") == "none" and outcome.get("reason") not in (\n'
        "                _OWN_BINDING_REASONS\n            ):\n                return True",
        "            outcome = self._use_lookup(node)\n"
        '            if outcome.get("outcome") == "none" and outcome.get("reason") not in (\n'
        "                _OWN_BINDING_REASONS\n            ):\n                return True",
    ),
    (
        "r3-b1-module-binding-dominance",
        PYS,
        "            or scope.kind in (_MODULE, _CLASS)\n",
        "",
    ),
    (
        "r3-b2-from-import-reexport",
        PYS,
        "        if module not in _CHECKED_MODULES and member in _CHECKED_MODULES:",
        "        if False:",
    ),
    (
        "r3-b2-generic-from-stdlib",
        PYS,
        "            if stdlib and last in _STRING_CODE_MODULES:",
        "            if False:",
    ),
    (
        "r3-b3-dotted-generic",
        PYS,
        "                    _dunder(components[1])\n"
        "                    or components[1] in _GENERIC_MODULE_ATTRIBUTES[head]",
        "                    False",
    ),
    (
        "r3-b3-name-keyword",
        PYS,
        '        if parent.type == "keyword_argument":\n'
        '            name = parent.child_by_field_name("name")\n            if (\n',
        '        if False:\n            name = parent.child_by_field_name("name")\n'
        "            if (\n",
    ),
    (
        "r3-b3-resolver-attribute",
        PYS,
        "        if method in _ACQUIRERS | _STRING_RESOLVERS:",
        "        if method in _ACQUIRERS:",
    ),
    (
        "r3-b3-resolver-name",
        PYS,
        "            return _text(callee, self.source) in _ACQUIRERS | _STRING_RESOLVERS",
        "            return _text(callee, self.source) in _ACQUIRERS",
    ),
    (
        "r3-b3-factory-key",
        PYS,
        '        if parent.type == "pair":',
        "        if False:",
    ),
    (
        "r3-b4-singledispatch",
        PYS,
        '        "singledispatch",\n        "singledispatchmethod",\n',
        '        "singledispatchmethod",\n',
    ),
    (
        "r3-getmodule",
        PYS,
        '        "f_builtins",\n        "getmodule",\n    }\n)',
        '        "f_builtins",\n    }\n)',
    ),
    (
        "r3-computed-acquisition",
        PYS,
        "            if spellings & _BUILTINS_REACH or self._computed_acquisition(ident):",
        "            if spellings & _BUILTINS_REACH:",
    ),
    (
        "r3-computed-acquisition-own-name",
        PYS,
        '        if key.type == "identifier" and _text(key, self.source) == "__name__":\n'
        "            return False\n",
        "",
    ),
    (
        "r3-re-receiver-exempt",
        PYS,
        "                if self.builtins_reach and not self._re_receiver(node):",
        "                if self.builtins_reach:",
    ),
    (
        "r3-re-receiver-any",
        PYS,
        "        return bool(\n"
        '            outcome.get("outcome") == "import"\n'
        '            and binding.get("form") == "import"\n'
        '            and binding.get("bound") == _RE_MODULE\n        )',
        "        return True",
    ),
    # R-699-5 (the second #727 fold).
    (
        "r5-b1-phantom-listcomp-leak",
        PYS,
        "                        self._targets(part, scope, depth + 1, phantom=True)",
        "                        self._targets(part, scope, depth + 1)",
    ),
    (
        "r5-b1-phantom-except-comma",
        PYS,
        "                self._targets(child, scope, depth + 1, phantom=True)",
        "                self._targets(child, scope, depth + 1)",
    ),
    (
        "r5-b1-phantom-type-parameter-bound",
        PYS,
        "                inner, ident, _Binding(PARAMETER, phantom=ident.id not in names)",
        "                inner, ident, _Binding(PARAMETER)",
    ),
    (
        "r5-b1-type-parameter-name-is-real",
        PYS,
        "                inner, ident, _Binding(PARAMETER, phantom=ident.id not in names)",
        "                inner, ident, _Binding(PARAMETER, phantom=True)",
    ),
    (
        "r5-b1-type-parameter-splat-name",
        PYS,
        '                "splat_type",\n                "list_splat",\n',
        '                "splat_type",\n',
    ),
    (
        "r5-b1-real-binding-builtin",
        PYS,
        "            or not self._real_binding(scope, _text(ident, self.source))\n",
        "",
    ),
    (
        "r5-b1-real-binding-checked",
        PYS,
        "        if self._own_binding(outcome) and self._real_binding(\n"
        "            self.use_decided, _text(ident, self.source)\n        ):",
        "        if self._own_binding(outcome):",
    ),
    (
        "r5-b2-acquired-before-gate",
        PYS,
        "        if acquired and set(_ACQUIRED_PARTS.split(value)) & _ACQUIRED_MODULES:",
        "        if False:",
    ),
    (
        "r5-b2-split-every-separator",
        PYS,
        '_ACQUIRED_PARTS = re.compile(r"[^A-Za-z0-9_]+")',
        '_ACQUIRED_PARTS = re.compile(r"[.:]")',
    ),
    (
        "r5-b2-entry-point",
        PYS,
        "        if self._entry_point_value(outer, parent):",
        "        if False:",
    ),
    (
        "r5-b2-entry-point-positional",
        PYS,
        "            return index is not None and index != 0",
        "            return False",
    ),
    (
        "r5-b2-entry-point-keyword",
        PYS,
        "                return keyword in _ENTRY_POINT_KEYWORDS",
        "                return False",
    ),
    (
        "r5-b2-entry-point-parse",
        PYS,
        "        if method != _ENTRY_POINT_PARSE or receiver is None:",
        "        if True:",
    ),
    (
        "r5-s1-reexport-checked",
        PYS,
        '        elif member in _REEXPORT_CHECKED and not _stdlib_path(module or ""):',
        "        elif False:",
    ),
    (
        "r5-s1-reexport-attribute-table",
        PYS,
        "                _dunder(name) or name in _GENERIC_MODULE_ATTRIBUTES[module]",
        "                _dunder(name)",
    ),
    (
        "r5-s1-reexport-dunder",
        PYS,
        "                _dunder(name) or name in _GENERIC_MODULE_ATTRIBUTES[module]",
        "                name in _GENERIC_MODULE_ATTRIBUTES[module]",
    ),
    (
        "r5-nit-test-package",
        PYS,
        '_S2_STDLIB_MODULES = py_modules.STDLIB_MODULES | {"test"}',
        "_S2_STDLIB_MODULES = py_modules.STDLIB_MODULES",
    ),
    # R-699-6 (the third #727 fold).
    (
        "r6-acquirer-any-argument",
        PYS,
        "        if self._in_acquirer_call(node):\n            return True\n",
        "",
    ),
    (
        "r6-acquirer-attribute-callee",
        PYS,
        '                if callee is not None and callee.type == "attribute":\n'
        '                    callee = callee.child_by_field_name("attribute")\n',
        "",
    ),
    (
        "r6-acquirer-any-depth",
        PYS,
        "        while parent is not None:\n"
        '            if parent.type == "call" and _same(\n'
        '                parent.child_by_field_name("arguments"), child\n',
        "        while parent is not None:\n"
        '            if parent.type == "dictionary":\n'
        "                return False\n"
        '            if parent.type == "call" and _same(\n'
        '                parent.child_by_field_name("arguments"), child\n',
    ),
    (
        "py5-mock-getattr",
        PYS,
        '            elif mock_file and name == "getattr":\n'
        '                self.string_checks.append(("getattr", ident))',
        '            elif mock_file and name == "getattr":\n                pass',
    ),
    (
        "py4-installed-builtins",
        PYS,
        "SHADOWED_NAMES = BUILTINS | INSTALLED_BUILTINS",
        "SHADOWED_NAMES = BUILTINS",
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
    # ("frame-locals-reads" is retired: treesitter-chunker#699 S4, PY-9,
    # removed the Tier 2 read allow-list it disabled; every ``f_locals``
    # spelling is a cause, killed by "s4-frame-readers-identifier".)
    (
        "runpy-loader",
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
    # ("e6-9-getfixturevalue-mocker" is retired: treesitter-chunker#699 S4,
    # PY-10, makes ``X.patch`` a patcher on any receiver, so the fixture-name
    # check in ``_scan_patchers`` it disabled is gone; the fixture's escapes
    # stay, killed by "e6-9-mp-alias-fixpoint" and "p6-5-...".)
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
        # Re-anchored by treesitter-chunker#699 S4: every frame-locals word of
        # a constant string (PY-9), ``f_locals`` included.
        "b-string-f-locals",
        PYM,
        "            if words & _FRAME_READERS:",
        "            if False:",
    ),
    (
        # The guard exemption now lives in the shared K-3 verdict (R-698-2).
        "b-main-guard",
        PYS,
        "if main_kind == _MAIN_INTERPOLATED or not self._main_guard(node):",
        "if main_kind == _MAIN_INTERPOLATED:",
    ),
    # K-3 main-string classifier (treesitter-chunker#698, R-698-1).
    (
        "main-component-split",
        PYS,
        '_MAIN_COMPONENTS = re.compile(r"[.:{}\\[\\]!()$%\\s]")',
        '_MAIN_COMPONENTS = re.compile(r"[.:]")',
    ),
    (
        "main-percent-fields",
        PYS,
        '_MAIN_COMPONENTS = re.compile(r"[.:{}\\[\\]!()$%\\s]")',
        '_MAIN_COMPONENTS = re.compile(r"[.:{}\\[\\]!$%\\s]")',
    ),
    (
        "main-template-identifier",
        PYS,
        '(match["named"] or match["braced"]) in _MAIN_NAMES',
        "False",
    ),
    (
        "main-fstring-tstring-parts",
        PYS,
        "    if _interpolated_names_main(node, source):\n        return _MAIN_INTERPOLATED",
        "    if False:\n        return _MAIN_INTERPOLATED",
    ),
    # One K-3 classifier for both tiers (treesitter-chunker#698, R-698-2 B-1).
    (
        "imports-main-string-shared",
        PYM,
        "    if analysis.main_string:",
        "    if False:",
    ),
    (
        "main-string-scan",
        PYS,
        "                main_kind = _main_string(node, source, value)",
        "                main_kind = None",
    ),
    (
        "main-string-constant",
        PYS,
        "    if value is not None and _names_main(value):\n        return _MAIN_CONSTANT",
        "    if False:\n        return _MAIN_CONSTANT",
    ),
    (
        "main-string-tier1-dynamic",
        PYS,
        "        if self.main_string:\n            self.dynamic = True",
        "        if False:\n            self.dynamic = True",
    ),
    # S-1 decoder (R-698-2): no ``ast`` and no warnings state.
    (
        "s1-invalid-escape-keeps-backslash",
        PYS,
        "    # An invalid escape keeps its backslash (a ``SyntaxWarning``).\n"
        "    return char, index + 1",
        "    # An invalid escape keeps its backslash (a ``SyntaxWarning``).\n"
        '    return "", index + 1',
    ),
    (
        "s1-named-sequence",
        PYS,
        "        if len(named) != 1:\n            # A named sequence",
        "        if False:\n            # A named sequence",
    ),
    # R-698-3: the f-string and t-string substring rule (it replaces the
    # piece reader, and with it the re-check 2 spec-gap mutation).
    (
        "r698-3-brace-view",
        PYS,
        '            views += (view, view.replace("{", "").replace("}", ""))',
        "            views += (view,)",
    ),
    (
        "r698-3-decode-view",
        PYS,
        "        for view in (base, _decode_escapes(base)):",
        "        for view in (base,):",
    ),
    (
        "r698-3-mp-main",
        PYS,
        "    return any(name in view for view in views for name in _MAIN_NAMES)",
        "    return any(_MAIN in view for view in views)",
    ),
    (
        "r698-3-adjacent-join",
        PYS,
        "                _string_sources(child, source, parts)\n        return",
        "                _string_sources(child, source, parts)\n"
        '                parts.append("\\0")\n        return',
    ),
    (
        "r698-3-plus-join",
        PYS,
        "            _string_sources(left, source, parts)\n"
        "            _string_sources(right, source, parts)",
        "            _string_sources(left, source, parts)\n"
        '            parts.append("\\0")\n'
        "            _string_sources(right, source, parts)",
    ),
    (
        "r698-3-plain-strings-keep-classifier",
        PYS,
        "    if not _has_interpolated(node, source):\n        return False\n    parts",
        "    if False:\n        return False\n    parts",
    ),
    (
        # A raw string's final ``\"`` folded into the end token is content
        # in the constant-interpolation f-string reader too.
        "b2-constant-fstring-folded-end",
        PYS,
        "            if not raw.endswith(quote):\n"
        "                return None\n"
        "            raw = raw[: len(raw) - len(quote)]\n",
        "            continue\n",
    ),
    (
        "main-undecodable-fails-closed",
        PYS,
        "    except _UndecodableError:\n        return True",
        "    except _UndecodableError:\n        return False",
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
        '        if name == "__import__"',
        '        if name == "__import__"',
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
        PYS,
        '        self._fire("builtin")  # string code (#699 PY-8)',
        "        pass",
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
    # treesitter-chunker#707: a function's locals read as a dict make its
    # sensitive aliases reachable.
    # R-707-1: a local alias's own binding passes ``_safe_use`` too, so the
    # binding-position rule (``707-parameter-readable``) covers the alias
    # path in ``_reachable_binding``; this mutation disables both at once.
    (
        "707-locals-reachable",
        PYS,
        '        name is relied on and checked by :meth:`_verify_callees`."""\n',
        '        name is relied on and checked by :meth:`_verify_callees`."""\n'
        "        return False\n",
    ),
    (
        "707-frame-locals",
        PYS,
        "        if self.frame_locals:\n            return True\n        for reader, by_lookup",
        "        for reader, by_lookup",
    ),
    (
        "707-value-readers",
        PYS,
        "            if call is None:\n                readers.append((None, False))\n",
        "            if call is None:\n",
    ),
    (
        "707-constant-readers",
        PYS,
        '            if ({value} | set(re.split(r"[.:\\[\\]]", value))) & _LOCALS_READERS:\n',
        "            if False:\n",
    ),
    (
        "707-use-site-lookup",
        PYS,
        '        return outcome.get("outcome") != "local"\n',
        "        return False\n",
    ),
    (
        "707-lookup-ignored",
        PYS,
        '        return outcome.get("outcome") != "local"\n',
        "        return True\n",
    ),
    (
        "707-vars-argument",
        PYS,
        "                continue  # ``vars(obj)`` reads ``obj.__dict__``\n",
        "                pass\n",
    ),
    # R-707-1 (#721 review): constant strings are tokens (any position, any
    # dotted, ``:`` or bracket component), import names count, and a local
    # parameter is reachable like an alias. Sonnet SHOULD-1..3: containment,
    # the splat guard and the keyword-name skip.
    (
        "707-constant-components",
        PYS,
        '            if ({value} | set(re.split(r"[.:\\[\\]]", value))) & _LOCALS_READERS:\n',
        "            if {value} & _LOCALS_READERS:\n",
    ),
    (
        "707-constant-positions",
        PYS,
        '            if node.type not in ("string", "concatenated_string", "binary_operator"):\n',
        '            if node.type not in ("string", "concatenated_string", "binary_operator")'
        ' or node.parent.type not in ("argument_list", "subscript"):\n',
    ),
    (
        "707-import-names",
        PYS,
        "                ):\n                    readers.append((None, False))\n"
        "                continue\n",
        "                ):\n                    pass\n                continue\n",
    ),
    (
        "707-parameter-readable",
        PYS,
        "            return not self._local_binding_readable(node)\n",
        "            return True\n",
    ),
    (
        "707-reader-containment",
        PYS,
        "            ):\n                continue\n            if not by_lookup:",
        "            ):\n                pass\n            if not by_lookup:",
    ),
    (
        "707-vars-splat",
        PYS,
        'not in ("list_splat", "dictionary_splat", "keyword_argument")',
        'not in ("keyword_argument",)',
    ),
    (
        "707-keyword-name",
        PYS,
        "            ):\n                continue\n"
        '            attribute = parent.type == "attribute" and _same(\n',
        "            ):\n                pass\n"
        '            attribute = parent.type == "attribute" and _same(\n',
    ),
    # treesitter-chunker#699 S4 (PY-6, PY-7 with B-7, PY-9 with B-6, PY-10).
    (
        "s4-gc-checked-module",
        PYS,
        "    _GC: _GC_SAFE,\n}",
        "}",
    ),
    (
        "s4-gc-unsafe-member-on-list",
        PYS,
        '        "is_finalized",\n        "DEBUG_COLLECTABLE",',
        '        "is_finalized",\n        "garbage",\n        "DEBUG_COLLECTABLE",',
    ),
    (
        "s4-gc-walker-token",
        PYS,
        "            if spellings & _GC_WALKERS:",
        "            if False:",
    ),
    (
        "s4-gc-walker-string",
        PYS,
        "        if set(_TOKEN_WORDS.split(value)) & _GC_WALKERS:",
        "        if False:",
    ),
    (
        "s4-gc-attribute",
        PYS,
        "                elif name == _GC:",
        "                elif False:",
    ),
    (
        "s4-gc-acquired",
        PYS,
        "        if acquired and _GC in _ACQUIRED_PARTS.split(value):",
        "        if False:",
    ),
    (
        "s4-gc-fires-as-string-code",
        PYS,
        "        if module == _GC:\n            self.heap_walk = True\n        else:",
        "        if False:\n            pass\n        else:",
    ),
    (
        "s4-gc-tier1-file-wide",
        PYS,
        "        if self.heap_walk:\n            # PY-7: a heap walk",
        "        if False:\n            # PY-7: a heap walk",
    ),
    (
        "s4-gc-tier2-cause",
        PYM,
        "    if analysis.heap_walk:",
        "    if False:",
    ),
    (
        "s4-patch-any-receiver-call",
        PYS,
        "            elif _is_patch_attribute(function, self.source):\n"
        '                kind = "patch"  # ``X.patch(...)`` for any ``X`` (PY-10)\n',
        "",
    ),
    (
        "s4-patch-handed-on",
        PYS,
        "                and not _patch_applied(node, self.source)\n"
        "                and not self._sensitive(node, _PATCH)\n",
        "                and False\n",
    ),
    (
        "s4-patch-recognised-alias-exempt",
        PYS,
        "                and not self._sensitive(node, _PATCH)\n",
        "",
    ),
    (
        "s4-patch-attribute-target",
        PYS,
        "                and node.id not in self.attribute_targets\n"
        "                and not _patch_applied(node, self.source)\n",
        "                and not _patch_applied(node, self.source)\n",
    ),
    (
        "s4-patch-applied-methods",
        PYS,
        "        and _text(method, source) in _PATCH_METHODS\n"
        "        and _callee_call(parent) is not None\n",
        "        and False\n",
    ),
    (
        "s4-patch-name-string",
        PYS,
        "        for node in self._patch_name_strings():",
        "        for node in ():",
    ),
    (
        "s4-patch-tier2-any-receiver",
        PYM,
        "        if node is not None and ps._is_patch_attribute(node, source):\n"
        "            # PY-10: ``X.patch`` on any receiver",
        "        if False:\n            # PY-10: ``X.patch`` on any receiver",
    ),
    (
        "s4-patch-tier2-call-receiver",
        PYM,
        "        if not names and receiver is not None and function is not None:",
        "        if False:",
    ),
    (
        "s4-patch-tier2-reads",
        PYM,
        "    _scan_patch_reads(analysis, facts)\n",
        "",
    ),
    (
        "s4-patch-tier2-name-string",
        PYM,
        '        if value is not None and "patch" in ps._TOKEN_PARTS.split(value):',
        "        if False:",
    ),
    (
        "s4-patch-tier2-recognised-alias-exempt",
        PYM,
        "            and not analysis._sensitive(node, ps._PATCH)\n",
        "",
    ),
    (
        "s4-patch-tier2-attribute-target",
        PYM,
        "            and node.id not in analysis.attribute_targets\n"
        "            and not ps._patch_applied(node, source)\n",
        "            and not ps._patch_applied(node, source)\n",
    ),
    (
        "s4-frame-readers-identifier",
        PYM,
        "        if spellings & _FRAME_READERS:",
        "        if False:",
    ),
    (
        "s4-frame-readers-drop-getargvalues",
        PYM,
        '        _FRAME_LOCALS,\n        "getargvalues",\n',
        "        _FRAME_LOCALS,\n",
    ),
    (
        "s4-frame-readers-drop-curframe-locals",
        PYM,
        '        "getasyncgenlocals",\n        "curframe_locals",\n',
        '        "getasyncgenlocals",\n',
    ),
    (
        "s4-frame-readers-words",
        PYS,
        '_TOKEN_WORDS = re.compile(r"[^A-Za-z0-9_]+")',
        '_TOKEN_WORDS = re.compile(r"[.:]")',
    ),
    (
        "s4-locals-value-cause",
        PYM,
        "    if any(node is None for node, _by_lookup in analysis._locals_readers()):",
        "    if False:",
    ),
    (
        "s4-cell-identifier",
        PYM,
        "        if _CELL_CONTENTS in spellings and not _cell_read(analysis, ident):",
        "        if False:",
    ),
    (
        "s4-cell-read-is-write",
        PYM,
        "        if _CELL_CONTENTS in spellings and not _cell_read(analysis, ident):",
        "        if _CELL_CONTENTS in spellings:",
    ),
    (
        "s4-cell-string",
        PYM,
        "            if _CELL_CONTENTS in words:",
        "            if False:",
    ),
    (
        "s4-cell-target",
        PYM,
        "        or parent.id in analysis.attribute_targets\n    ):\n        return False\n"
        "    outer = parent",
        "    ):\n        return False\n    outer = parent",
    ),
    (
        "s4-cell-descriptor",
        PYM,
        "        return method is not None and not ps._dunder(ps._text(method, analysis.source))",
        "        return True",
    ),
    # Ruling R-699-10 (the Fable review of #733).
    (
        "r10-getclosurevars-reader",
        PYM,
        '        "getclosurevars",\n',
        "",
    ),
    (
        "r10-imported-patch-any-module",
        PYS,
        '                if kind == "import_from_statement":\n'
        "                    # treesitter-chunker#699 R-699-10 item 2",
        '                if kind == "import_from_statement" and module_parts in (\n'
        '                    ["unittest", "mock"],\n'
        '                    ["mock"],\n'
        "                ):\n"
        "                    # treesitter-chunker#699 R-699-10 item 2",
    ),
    (
        "r10-class-pattern-keyword",
        PYM,
        "            if ps._spellings(keyword, source) & _CLASS_PATTERN_PATCHERS:",
        "            if False:",
    ),
    (
        "r10-class-pattern-patch",
        PYM,
        '_CLASS_PATTERN_PATCHERS = _PATCH_METHOD_NAMES | {"patch"}',
        "_CLASS_PATTERN_PATCHERS = _PATCH_METHOD_NAMES",
    ),
    (
        "r10-class-pattern-methods",
        PYM,
        '_CLASS_PATTERN_PATCHERS = _PATCH_METHOD_NAMES | {"patch"}',
        '_CLASS_PATTERN_PATCHERS = frozenset({"patch"})',
    ),
    (
        "r10-star-patcher",
        PYM,
        "                if builder.exposes_patcher(node, None):",
        "                if False:",
    ),
    # Ruling R-699-12.
    (
        "r12-private-identifier-tier1",
        PYS,
        "            if spellings & _PRIVATE_PATCH_TOKENS:\n                self.dynamic = True",
        "            if False:\n                self.dynamic = True",
    ),
    (
        "r12-private-identifier-tier2",
        PYM,
        "            ps._spellings(node, source) & ps._PRIVATE_PATCH_TOKENS",
        "            False",
    ),
    (
        "r12-token-string-tier1",
        PYS,
        "            ) or _patch_token_string(node, self.source):",
        "            ):",
    ),
    (
        "r12-token-string-tier2",
        PYM,
        "        if ps._patch_token_string(node, source):",
        "        if False:",
    ),
    (
        "r12-patch-exact-string",
        PYS,
        "    return value == _PATCH or bool(",
        "    return bool(",
    ),
    (
        "r12-private-string-words",
        PYS,
        "        set(_TOKEN_WORDS.split(value)) & _PRIVATE_PATCH_TOKENS",
        "        set()",
    ),
    (
        "r12-get-target-token",
        PYS,
        '"_patch_dict", "_get_target"}',
        '"_patch_dict"}',
    ),
    (
        "r12-whole-literal",
        PYS,
        "        return False  # judged as part of the whole literal",
        "        pass",
    ),
    (
        "r12-larger-constant",
        PYS,
        "        return False  # judged as part of the larger constant (``'pat' + 'ch'``)",
        "        pass",
    ),
    (
        "r12-reexport-any-scope",
        PYM,
        "            if any(\n                builder.exposes_patcher(start, name)\n"
        "                for start in builder.targets(module, path)\n            ):",
        "            if False:",
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
