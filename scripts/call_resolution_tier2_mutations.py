"""Rule mutations for Tier 2 TS/JS call resolution (treesitter-chunker#682 PR 5).

Each mutation disables one rule by a single textual edit. The script copies
the checkout to a temporary directory, checks that the unmutated copy passes,
then applies each mutation alone and runs the Tier 2 tests, the
``imports`` expected-table test and the treesitter-chunker#694 Tier 1
property-writer pins serially. A mutation is *killed* when a test
fails. The script prints one tab-separated line per mutation and exits
non-zero if any mutation survives or does not apply.

Usage (Python 3.14, from the repository root)::

    uv run --locked --all-extras python scripts/call_resolution_tier2_mutations.py

Run it only with headroom: it runs the narrow Tier 2 tests once per mutation,
serially.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CR = "chunker/call_resolution/"
MOD = CR + "modules.py"
JSM = CR + "js_modules.py"
ENG = CR + "engine.py"
JSS = CR + "js_scope.py"
STR = CR + "js_strings.py"
FACTS = CR + "facts.py"
TESTS = (
    "tests/test_call_resolution_tier2_js.py",
    "tests/test_call_resolution_engine.py::test_expected_imports_tables_hold_at_this_head",
    # treesitter-chunker#694 pins for the property-writer mutations below.
    "tests/test_call_resolution_tier1_js.py::test_694_writer_invokers_fail_closed",
    "tests/test_call_resolution_tier1_js.py::test_694_writer_invokers_on_other_targets_are_not_wildcards",
    "tests/test_call_resolution_tier1_js.py::test_717_main_writer_wildcards_are_kept",
)

# (id, file, old text, new text). The old text must occur in the file.
MUTATIONS: tuple[tuple[str, str, str, str], ...] = (
    # Stack introspection (treesitter-chunker#718).
    (
        "718-property-name-token",
        JSM,
        '        "property_identifier",\n        "shorthand_property_identifier",',
        '        "shorthand_property_identifier",',
    ),
    (
        "718-get-function",
        JSM,
        '_STACK_KEYS = frozenset({"caller", "getFunction"})',
        '_STACK_KEYS = frozenset({"caller"})',
    ),
    (
        "718-cooked-keys",
        JSM,
        "                    or any(part in _STACK_KEYS for part in cooked)\n",
        "",
    ),
    (
        "718-constant-stack-keys",
        JSM,
        "                    or value in _STACK_KEYS\n",
        "",
    ),
    (
        "718-with-statement",
        JSM,
        "                self.shutoff.add(CAUSE_DYNAMIC_SCOPE)",
        "                pass",
    ),
    (
        "718-type-position",
        JSM,
        "        if text in _STACK_KEYS:",
        "        if text in _STACK_KEYS and not _in_type_position(node):",
    ),
    (
        "718-pair-pattern",
        JSM,
        "            if not self._lexical_stack_name(node, text):",
        '            if node.parent.type != "pair_pattern" and not self._lexical_stack_name(node, text):',
    ),
    (
        "718-shorthand-pattern",
        JSM,
        '        "shorthand_property_identifier_pattern",\n        "statement_identifier",',
        '        "statement_identifier",',
    ),
    (
        "718-shorthand-expression",
        JSM,
        '        "shorthand_property_identifier",\n        "shorthand_property_identifier_pattern",',
        '        "shorthand_property_identifier_pattern",',
    ),
    (
        "718-regex-substring",
        JSM,
        "                if any(name in pattern for name in _STACK_KEYS):",
        "                if pattern in _STACK_KEYS:",
    ),
    (
        "718-binding-kind",
        JSM,
        "            binding.lexical_name or binding.cls == PARAMETER",
        "            True",
    ),
    (
        "718-variable-exemption",
        JSM,
        "            binding.lexical_name or binding.cls == PARAMETER",
        "            binding.cls == PARAMETER",
    ),
    (
        "718-parameter-exemption",
        JSM,
        "            binding.lexical_name or binding.cls == PARAMETER",
        "            binding.lexical_name",
    ),
    (
        "718-prepare-stack-trace",
        JSM,
        '        if name != "prepareStackTrace" or _in_type_position(node):',
        "        if True:",
    ),
    (
        "718-shadowed-builtin",
        JSM,
        "and self.analysis._refers_to_global(\n                node, name\n            )",
        "",
    ),
    (
        "718-sibling-builtin-shadow",
        JSM,
        "self.analysis._refers_to_global(\n                node, name\n            )",
        "not any(name in scope.bindings for scope in self.analysis.scopes.values())",
    ),
    (
        "718-shadowed-global-object",
        JSS,
        "return name in _GLOBAL_OBJECTS and self._refers_to_global(node, name)",
        "return name in _GLOBAL_OBJECTS",
    ),
    (
        "718-non-global-error-receiver",
        JSM,
        ' and self.analysis._is_global_object(\n            node.child_by_field_name("object"), receiver=True\n        )',
        "",
    ),
    # Module resolution (9.2, E5-5).
    (
        "O1-more-than-one",
        MOD,
        "if len(existing) > 1 or index.suffixed_sibling(candidates):",
        "if index.suffixed_sibling(candidates):",
    ),
    (
        "suffixed-sibling",
        MOD,
        "if len(existing) > 1 or index.suffixed_sibling(candidates):",
        "if len(existing) > 1:",
    ),
    (
        "inert-list-open",
        MOD,
        "if middle is not None and middle not in INERT_SUFFIXES:",
        'if middle in ("ios", "android", "native", "web"):',
    ),
    (
        "uncollected-extension",
        MOD,
        '        if not index.collected(candidate):\n            return None, "unknown-variant"\n',
        "",
    ),
    (
        "skipped-directory",
        MOD,
        '        if any(_skipped(part) for part in candidate.split("/")):\n'
        '            return None, "unknown-variant"\n',
        "",
    ),
    (
        "case-fold",
        MOD,
        "        if any(path != candidate for path in index.folded.get(_fold(candidate), ())):",
        "        if False:",
    ),
    (
        "dts-target",
        MOD,
        '    if target.lower().endswith(".d.ts"):\n        return None, "dts-target"',
        "    pass",
    ),
    (
        "directory-package-json",
        MOD,
        "    if directory == requested and (",
        "    if False and (",
    ),
    (
        "uppercase-extension",
        MOD,
        "        # ``./svc.JS``: toolchains disagree on whether it is an extension.\n"
        '        return (), "unknown-variant"',
        "        pass",
    ),
    (
        "unread-characters",
        MOD,
        "        _UNREAD_CHARACTERS & set(specifier)\n",
        "        False\n",
    ),
    ("trailing-slash", MOD, '        or specifier.endswith("/")\n', ""),
    ("empty-segment", MOD, '        or "//" in specifier\n', ""),
    ("dot-segment", MOD, "        or _dot_segment(specifier)\n", ""),
    (
        "bare-dot",
        MOD,
        '    if specifier in (".", ".."):\n'
        "        # A directory import of the importer's own or parent directory.\n"
        '        return (), "unknown-variant"\n',
        "",
    ),
    (
        "outside-root",
        MOD,
        'if base == ".." or base.startswith(("../", "/")):\n        return (), "outside-root"',
        "if False:\n        pass",
    ),
    (
        "js-importer-exact",
        MOD,
        '    if importer_language == "javascript" and explicit:\n        return (base,), None\n',
        "",
    ),
    (
        "exact-file-other-extension",
        MOD,
        "    if requested in index.run_paths and requested not in candidates:",
        "    if False:",
    ),
    ("symlinked-importer", MOD, "    if importer in index.symlinks:", "    if False:"),
    ("symlinked-target", MOD, "    if target in index.symlinks:", "    if False:"),
    # Export lookup (9.3).
    (
        "hop-limit",
        MOD,
        '    if hops > HOP_LIMIT:\n        return _Unknown("hop-limit")\n',
        "",
    ),
    (
        "cycle",
        MOD,
        '    if (path, name) in seen:\n        return _Unknown("cycle")\n',
        '    if len(seen) > 50:\n        return _Unknown("cycle")\n',
    ),
    (
        "star-conflict",
        MOD,
        '    if len(found) > 1:\n        return _Found(_none("star-conflict"))\n',
        "",
    ),
    (
        "star-source-failure",
        MOD,
        '        if target is None:\n            return _Unknown(failure or "module-not-found")\n'
        "        result",
        "        if target is None:\n            continue\n        result",
    ),
    (
        "star-excludes-default",
        MOD,
        '    if name == "default":\n        return _NOT_FOUND\n',
        "",
    ),
    (
        "explicit-beats-star",
        MOD,
        "    entry = module.exports.get(name)\n    if entry is not None:",
        "    entry = module.exports.get(name)\n    if entry is not None and not module.stars:",
    ),
    (
        "attributes-on-import",
        MOD,
        '    if binding.get("attributes") is not None:\n        return _none("unknown-variant")\n'
        "    form",
        "    form",
    ),
    (
        "attributes-on-hop",
        MOD,
        '            if binding.get("attributes") is not None:\n'
        '                return _none("unknown-variant")\n            if binding.get("form")',
        '            if binding.get("form")',
    ),
    (
        "module-commonjs-flag",
        MOD,
        "    if module.commonjs or path in taints:",
        "    if path in taints:",
    ),
    (
        "module-taints",
        MOD,
        "    if module.commonjs or path in taints:",
        "    if module.commonjs:",
    ),
    (
        "run-wide-shutoff",
        MOD,
        "    shutoff = run_tainted_reason(run, importer)\n    if shutoff is not None:\n        return _none(shutoff)\n",
        "",
    ),
    (
        "opaque-module",
        MOD,
        "    if module is None or not module.supported or module.opaque:",
        "    if module is None or not module.supported:",
    ),
    (
        "rejected-taints-dropped",
        MOD,
        "        targets = None if path in symlinks else lenient_targets(index, specifier, path)\n        if targets is None:\n            # The written",
        '        targets = None if path in symlinks else existing_candidates(index, specifier, path, "typescript")\n        if targets is None:\n            # The written',
    ),
    (
        "unresolvable-writer",
        MOD,
        "            causes.append((CAUSE_UNRESOLVABLE_WRITER, path))\n        else:",
        "            pass\n        else:",
    ),
    (
        "namespace-member-verified",
        MOD,
        "        if not verified:\n            taint(path, specifier)",
        "        if False:\n            taint(path, specifier)",
    ),
    (
        "namespace-call-this",
        MOD,
        '                    outcome.get("outcome") == "local" and outcome.get("this") is False',
        '                    outcome.get("outcome") == "local"',
    ),
    (
        "unparsed-without-text",
        MOD,
        "            causes.append((CAUSE_UNPARSED_FILE, path))\n",
        "            pass\n",
    ),
    # Owner decision O-2 (fold 2): scope by caller, promotion.
    (
        "o2-test-causes-run-wide",
        MOD,
        "    if importer is not None and importer in run.test_scope:",
        "    if True:",
    ),
    (
        "o2-test-causes-ignored",
        MOD,
        "        active.update(run.test_shutoff)",
        "        pass",
    ),
    (
        "o2-test-taints-for-all",
        MOD,
        "        if importer in self.test_scope:\n            return self.tainted | self.test_tainted",
        "        if True:\n            return self.tainted | self.test_tainted",
    ),
    (
        "o2-test-taints-ignored",
        MOD,
        "            return self.tainted | self.test_tainted",
        "            return self.tainted",
    ),
    (
        "o2-taint-origin",
        MOD,
        "            tainted[path in production].update(targets)",
        "            tainted[False].update(targets)",
    ),
    (
        "o2-cause-origin",
        MOD,
        "        shutoff[path in production].setdefault(name, path)",
        "        shutoff[False].setdefault(name, path)",
    ),
    ("o2-promotion", MOD, "    pending = sorted(production)\n", "    pending = []\n"),
    ("o2-promotion-transitive", MOD, "                pending.append(target)\n", ""),
    (
        "o2-promotion-uncomputable",
        MOD,
        "            reached = set(files) if targets is None else set(targets)",
        "            reached = set() if targets is None else set(targets)",
    ),
    (
        "o2-promotion-static-imports",
        MOD,
        '            for key in ("imports", "taints", "stars", "filename_taints")',
        '            for key in ("taints", "stars", "filename_taints")',
    ),
    (
        "o2-classifier-directories",
        MOD,
        "    if any(part in TEST_DIRECTORIES for part in directories):\n        return True\n",
        "",
    ),
    (
        "o2-classifier-names",
        MOD,
        '    return any(part in TEST_NAME_SEGMENTS for part in name.split(".")[1:-1])',
        "    return False",
    ),
    (
        "o2-classifier-case",
        MOD,
        '    return any(part in TEST_NAME_SEGMENTS for part in name.split(".")[1:-1])',
        '    return any(part.lower() in TEST_NAME_SEGMENTS for part in name.split(".")[1:-1])',
    ),
    (
        "o2-imports-fact",
        JSM,
        "                    elif specifier not in _MODULE_SYSTEM_SPECIFIERS:\n                        self.imports.add(specifier)",
        "                    elif specifier not in _MODULE_SYSTEM_SPECIFIERS:\n                        pass",
    ),
    # Fold 3: closed allow-lists for three run-wide causes.
    (
        "f3-inert-module-import",
        JSM,
        "                        and not self._inert_module_import(node)\n",
        "",
    ),
    (
        "f3-inert-names-open",
        JSM,
        "                    if imported in INERT_MODULE_EXPORTS:",
        "                    if imported is not None:",
    ),
    (
        "f3-inert-name-writes",
        JSM,
        "                        if any(self._written(use) for use in uses):\n                            return False",
        "                        pass",
    ),
    (
        "f3-default-or-namespace-import",
        JSM,
        '                if part.type != "named_imports":\n                    return False',
        '                if part.type != "named_imports":\n                    continue',
    ),
    (
        "f3-module-import-attributes",
        JSM,
        '        if any(child.type == "import_attribute" for child in statement.named_children):\n            return False',
        "        pass",
    ),
    (
        "f3-module-binding-defers",
        JSM,
        "                # statement's closed allow-list decides (fold 3).\n                return",
        "                # statement's closed allow-list decides (fold 3).\n                pass",
    ),
    (
        "f3-create-require-const",
        JSM,
        '            or not _has_token(declaration, "const")\n',
        "",
    ),
    # Not listed (f3-create-require-initializer): equivalent, because the declarator's value and its const declaration are checked next, so the kind check is implied.
    (
        "f3-create-require-other-uses",
        JSM,
        "            else:\n                return False\n            literal = self._single_literal(arguments)",
        "            else:\n                continue\n            literal = self._single_literal(arguments)",
    ),
    (
        "f3-create-require-literal-only",
        JSM,
        "            if literal is None or literal in _MODULE_SYSTEM_SPECIFIERS:\n                return False\n            literals.append(literal)",
        "            if literal is not None:\n                literals.append(literal)",
    ),
    (
        "f3-create-require-taints",
        JSM,
        "        self.taints.update(literals)",
        "        pass",
    ),
    (
        "f3-resolve-literal-only",
        JSM,
        "                    None if self._single_literal(arguments) is None else arguments",
        "                    arguments",
    ),
    (
        "f3-uses-single-binding",
        JSM,
        "        if len(scope.bindings.get(name, ())) != 1:\n            return None\n",
        "",
    ),
    (
        "f3-constructor-safe-positions",
        JSS,
        "        if constructor and not self._safe_constructor_read(current, parent):",
        "        if False:",
    ),
    (
        "f3-constructor-name-only",
        JSS,
        '                and _text(prop, self.source) == "name"',
        '                and _text(prop, self.source) != "call"',
    ),
    # Not listed (f3-constructor-non-computed): equivalent, because a subscript has no property field, so the .name check already fails for it.
    (
        "f3-constructor-operators-open",
        JSS,
        "            return text in _SAFE_CONSTRUCTOR_OPERATORS",
        "            return True",
    ),
    (
        "f3-constructor-unary-open",
        JSS,
        '        return parent.type == "unary_expression" and text == "typeof"',
        '        return parent.type == "unary_expression"',
    ),
    # Fold 4 (the president's review, P5-1..P5-3 and item 4).
    (
        "p5-1-base-check",
        JSM,
        "        own_base = self._own_file_base(call)",
        "        own_base = True",
    ),
    # p5-1-filename-lookup: superseded by the p5-13 ``__filename`` checks.
    (
        "p5-1-meta-list",
        JSM,
        "            and _text(prop, self.source) in _OWN_FILE_META",
        '            and _text(prop, self.source) != ""',
    ),
    (
        "p5-1-uncomputable-cause",
        JSM,
        "            self.uncomputable = True\n            self.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)\n        return True",
        "            pass\n        return True",
    ),
    (
        "p5-2-directory-symlinks",
        MOD,
        "    if directory_symlinks is not False:",
        "    if False:",
    ),
    (
        "p5-2-unknown-is-linked",
        MOD,
        "    if directory_symlinks is not False:",
        "    if directory_symlinks:",
    ),
    (
        "p5-3-module-mocks",
        JSM,
        "        if self._module_mock(node, function):\n            return\n",
        "",
    ),
    (
        "p5-3-mock-non-literal",
        JSM,
        "        if specifier is None:\n            self.shutoff.add(CAUSE_UNRESOLVABLE_WRITER)\n        else:\n            self.taints.add(specifier)",
        "        if specifier is not None:\n            self.taints.add(specifier)",
    ),
    (
        "p5-3-framework-lookup",
        JSM,
        "        if scope is None:\n            return name if name in MODULE_MOCKS else None",
        "        if True:\n            return name if name in MODULE_MOCKS else None",
    ),
    (
        "p5-3-framework-imports",
        JSM,
        '                imported in MOCK_PACKAGES\n                and info.get("source") == MOCK_PACKAGES[imported]\n            ):\n                return str(imported)',
        "                False\n            ):\n                return str(imported)",
    ),
    (
        "p5-3-mock-list",
        JSM,
        "        if framework is None or _text(prop, self.source) not in MODULE_MOCKS[framework]:",
        '        if framework is None or _text(prop, self.source) != "mock":',
    ),
    (
        "item4-uncomputable-specifiers",
        MOD,
        "    if _uncomputable_specifier(specifier):",
        "    if False:",
    ),
    (
        "item4-uncomputable-files",
        MOD,
        "        if path in uncomputable:\n            # An edge whose targets cannot be computed (fold 4).\n            return frozenset(files)\n",
        "",
    ),
    (
        "item4-import-meta-glob",
        JSM,
        "        if name in _IMPORT_META_LOADERS:\n            self.uncomputable = True\n            return True",
        "        if name in _IMPORT_META_LOADERS:\n            return True",
    ),
    # Fold 5 (the president's re-check at 3344e9db, P5-13..P5-18).
    (
        "p5-13-filename-unbound",
        JSM,
        '                or self.analysis._binding_scope(base, "__filename") is not None\n',
        "",
    ),
    # Not listed (p5-13-filename-unwritten): equivalent since fold 6 (P5-20).
    # A write to a free ``__filename`` anywhere in the file is an implicit
    # global, so the run-wide writer check (c) already fails it closed; the
    # in-file check (b) stays as a second guard.
    (
        "p5-13-filename-global-writers",
        MOD,
        "        if filename_writers:\n            # ``__filename`` may name another file: uncomputable (P5-13).",
        "        if False:\n            # ``__filename`` may name another file: uncomputable (P5-13).",
    ),
    (
        "p5-13-script-globals-writers",
        MOD,
        '        if not supported or {"__filename", "*"} & set(',
        "        if not supported or set() & set(",
    ),
    # p5-13-commonjs-wrapper: the shortcut it disabled is gone (P5-20).
    (
        "p5-13-meta-unwritten",
        JSM,
        "            and not self._import_meta_written()\n",
        "",
    ),
    (
        "p5-13-meta-destructuring",
        JSM,
        '                    and field == "left"\n                ):\n                    return True',
        '                    and field == "left"\n                    and child.type == "member_expression"\n                ):\n                    return True',
    ),
    (
        "p5-14-skipped-directory",
        MOD,
        '        if any(_skipped(part) for part in base.split("/")):\n            # P5-14',
        "        if False:\n            # P5-14",
    ),
    (
        "p5-18-scheme-case",
        MOD,
        "    return scheme is not None and scheme.group(1).lower() in _UNCOMPUTABLE_SCHEMES",
        "    return scheme is not None and scheme.group(1) in _UNCOMPUTABLE_SCHEMES",
    ),
    (
        "p5-18-data-scheme",
        MOD,
        '_UNCOMPUTABLE_SCHEMES = frozenset({"file", "data"})',
        '_UNCOMPUTABLE_SCHEMES = frozenset({"file"})',
    ),
    (
        "p5-16-junctions",
        "chunker/symbol_graph.py",
        "                if entry.is_symlink() or entry.is_junction():",
        "                if entry.is_symlink():",
    ),
    # Fold 6 (the president's re-check at 9d180a97, P5-20, P5-21).
    (
        "p5-20-commonjs-shortcut",
        JSM,
        "    def module_bindings(self) -> dict[str, Any]:\n",
        "    def module_bindings(self) -> dict[str, Any]:\n"
        '        if self.commonjs or self.analysis.goal == "script":\n'
        "            self.taints.update(self.filename_taints)\n"
        "            self.filename_taints = set()\n",
    ),
    (
        "p5-21-casefold",
        MOD,
        "        base.casefold() in SKIPPED_DIRECTORIES\n        or base.upper().casefold() in SKIPPED_DIRECTORIES\n",
        "        base in SKIPPED_DIRECTORIES\n        or base.upper() in SKIPPED_DIRECTORIES\n",
    ),
    (
        "p5-21-win32-trailing",
        MOD,
        '    base = part.rstrip(". ")\n',
        "    base = part\n",
    ),
    (
        "url-whitespace-strip",
        MOD,
        '    specifier = _URL_NOISE.sub("", specifier.strip(_C0_AND_SPACE))',
        '    specifier = _URL_NOISE.sub("", specifier)',
    ),
    (
        "url-whitespace-noise",
        MOD,
        '    specifier = _URL_NOISE.sub("", specifier.strip(_C0_AND_SPACE))',
        "    specifier = specifier.strip(_C0_AND_SPACE)",
    ),
    # Fold 7 (the president's re-check at ae5f53a5, P5-27, P5-32).
    (
        "p5-27-filename-taints-edges",
        MOD,
        '            for key in ("imports", "taints", "stars", "filename_taints")',
        '            for key in ("imports", "taints", "stars")',
    ),
    (
        "p5-32-upper-casefold",
        MOD,
        "        or base.upper().casefold() in SKIPPED_DIRECTORIES\n",
        "",
    ),
    ("p5-32-streams", MOD, '        or ":" in part\n', ""),
    ("p5-32-short-names", MOD, "        or _SHORT_NAME.match(base) is not None\n", ""),
    # Fold 8's text-scan mutations left with the scan (E5-7, fold 9).
    # substitution never sits alone between ``(`` and ``)``: its substitution's
    # tokens are emitted before it, so a loader call with one is never a
    # complete literal call anyway; the flag only stops a harmless taint.
    # rejects a raw line terminator too, so the file is uncertain either way.
    # Fold 9 (E5-7, P5-44).
    (
        "p5-44-arguments-loader",
        JSM,
        "                if not self._inert_operand(node):\n                    # P5-44",
        "                if False:\n                    # P5-44",
    ),
    (
        "p5-44-arguments-inert-list",
        JSM,
        "                if not self._inert_operand(node):\n                    # P5-44",
        '                if node.parent is not None and node.parent.type == "call_expression":\n                    # P5-44',
    ),
    # Fold 10 (the president's re-check at 9bcd20c1, P5-47..P5-49).
    (
        "p5-47-misread-terminators",
        FACTS,
        '        if family == "js" and _misread_line_terminators(source, root, language):',
        "        if False:",
    ),
    (
        "p5-47-lone-cr",
        FACTS,
        "    if _LONE_CR.search(source) or any(sep in source for sep in _LINE_SEPARATORS):",
        "    if any(sep in source for sep in _LINE_SEPARATORS):",
    ),
    (
        "p5-47-line-separators",
        FACTS,
        "    if _LONE_CR.search(source) or any(sep in source for sep in _LINE_SEPARATORS):",
        "    if _LONE_CR.search(source):",
    ),
    (
        "p5-47-html-comments",
        FACTS,
        '        if node.type == "html_comment":\n            return True',
        "        if False:\n            return True",
    ),
    (
        "p5-50-mid-line-open",
        FACTS,
        "        if code[index]:\n            return True",
        "        if False:\n            return True",
    ),
    (
        "p5-50-close-after-comment",
        FACTS,
        "        if code[index]:\n            line = ",
        "        if False:\n            line = ",
    ),
    (
        "p5-50-close-line-may-start-in-comment",
        FACTS,
        "                comment[at] or source[at]",
        "                source[at]",
    ),
    (
        "p5-50-template-substitution-is-code",
        FACTS,
        '                if child.type == "template_substitution":',
        "                if False:",
    ),
    (
        "p5-48-module-scope-arguments",
        JSM,
        '        if "arguments" in self.analysis.program.bindings:',
        "        if False:",
    ),
    (
        "p5-49-static-fields",
        JSM,
        '            if _same(child, current.child_by_field_name("value")) and not (\n                _has_token(current, "static")\n            ):',
        '            if _same(child, current.child_by_field_name("value")):',
    ),
    (
        "p5-49-static-blocks",
        JSM,
        "        child, current = current, current.parent\n    return True",
        '        elif kind == "class_static_block":\n            return False\n        child, current = current, current.parent\n    return True',
    ),
    # Per-file module facts.
    (
        "type-only-entry",
        JSM,
        '                table[name] = {"kind": "none", "reason": "type-only"}',
        "                continue",
    ),
    (
        "duplicate-export",
        JSM,
        "            if len(values) > 1:",
        "            if False:",
    ),
    (
        "default-expression",
        JSM,
        '                self._add("default", ("none", "expression-bound"))',
        "                pass",
    ),
    (
        "declaration-fallback-opaque",
        JSM,
        '            self._add("default" if default else local, ("local", local))\n'
        "            return\n        self.opaque = True",
        '            self._add("default" if default else local, ("local", local))\n'
        "            return",
    ),
    # Not listed: ``export … from … with {…}`` in ``_reexport``. Both bundled
    # grammars reject it (a parse error), so the file is text-scanned and
    # opaque, and that branch is unreachable today (equivalent mutation).
    (
        "namespace-allow-list",
        JSM,
        "            if use is None:\n                self.taints.add(namespaces[name])",
        "            if False:\n                self.taints.add(namespaces[name])",
    ),
    (
        "namespace-use-lookup",
        JSM,
        "            if self.analysis._binding_scope(node, name) is not program:\n                continue\n",
        "",
    ),
    (
        "namespace-augmented-left",
        JSM,
        '        ("augmented_assignment_expression", "right"),\n',
        '        ("augmented_assignment_expression", None),\n',
    ),
    (
        "this-flag",
        JSM,
        '                "this": self._mentions_this(outcome),',
        '                "this": False,',
    ),
    (
        "import-writes",
        JSM,
        '            if info is not None:\n                self.taints.add(str(info.get("source", "")))',
        "            pass",
    ),
    (
        "module-level-this",
        JSM,
        '            elif kind == "this":\n                if module_level(node):\n'
        "                    self.commonjs = True",
        '            elif kind == "this":\n                pass',
    ),
    (
        "computed-key-this",
        JSM,
        '            if _same(child, current.child_by_field_name("body")) or _same(\n'
        '                child, current.child_by_field_name("parameters")\n            ):',
        "            if True:",
    ),
    (
        "require-taint",
        JSM,
        "        # ``require`` parameter loads modules too.\n        self.taints.add(specifier)",
        "        # ``require`` parameter loads modules too.\n        pass",
    ),
    (
        "require-non-call",
        JSM,
        "                # passed on: any module's exports may be reached.\n"
        "                self.shutoff.add(CAUSE_DYNAMIC_LOADER)",
        "                # passed on: any module's exports may be reached.\n                pass",
    ),
    (
        "require-use-site-lookup",
        JSM,
        '            if not is_require or self._free_or_top(function, "require"):',
        "            if not is_require:",
    ),
    (
        "module-use-site-lookup",
        JSM,
        "            if not self._free_or_top(node, text):\n                return\n            self.commonjs = True",
        "            self.commonjs = True",
    ),
    (
        "module-object",
        JSM,
        "                self.shutoff.add(CAUSE_MODULE_OBJECT)\n            return",
        "                pass\n            return",
    ),
    (
        "module-system-specifier",
        JSM,
        "        if specifier in _MODULE_SYSTEM_SPECIFIERS:\n            self.shutoff.add(CAUSE_MODULE_SYSTEM)\n"
        "            return\n",
        "",
    ),
    (
        "import-from-module",
        JSM,
        "                    if specifier is None or (\n                        specifier in _MODULE_SYSTEM_SPECIFIERS\n                        and not self._inert_module_import(node)\n                    ):\n                        self.shutoff.add(CAUSE_MODULE_SYSTEM)",
        "                    if specifier is None:\n                        self.shutoff.add(CAUSE_MODULE_SYSTEM)",
    ),
    (
        "module-system-identifiers",
        JSM,
        '            if scope is None or any(binding.cls == "import" for binding in bindings):\n                self.shutoff.add(CAUSE_MODULE_SYSTEM)',
        "            if False:\n                pass",
    ),
    (
        "module-system-templates",
        JSM,
        "                    or any(\n"
        "                        name in part for part in cooked for name in _MODULE_SYSTEM_NAMES\n"
        "                    )\n",
        "",
    ),
    (
        "module-system-strings-sloppy",
        JSM,
        "                value = decode_js_string_sloppy(_text(node, self.source))",
        "                value = decode_string_literal(node, self.source) or ''",
    ),
    (
        "import-meta-require",
        JSM,
        "                if not self._inert_import_meta(node):",
        "                if False:",
    ),
    (
        "type-position-import",
        JSM,
        '        if function.type == "import" and _in_type_position(node):\n'
        "            # ``typeof import('./x')`` is erased at emit.\n            return\n",
        "",
    ),
    # Engine eligibility.
    (
        "member-agrees",
        ENG,
        '    if member is not None and binding.get("member") != member:',
        "    if False:",
    ),
    (
        "namespace-form-only",
        ENG,
        '            or binding.get("form") != "namespace"\n',
        "",
    ),
    # Evaluators (E5-3).
    (
        "timer-free-name",
        JSS,
        "            if self._binding_scope(first, _text(first, self.source)) is None:\n"
        "                self.evaluator = True",
        "            pass",
    ),
    (
        "timer-non-function",
        JSS,
        "        else:\n            self.evaluator = True\n        self.global_wildcard = True",
        "        self.global_wildcard = True",
    ),
    # Property writers behind commas and invokers (treesitter-chunker#694).
    (
        "694-comma-callee",
        JSS,
        '    while current is not None and current.type == "sequence_expression":',
        "    while False:",
    ),
    (
        "694-comma-namespace",
        JSS,
        "        node = _callee(node)\n        if node is None:\n            return None\n",
        "        node = unwrap(node)\n        if node is None:\n            return None\n",
    ),
    (
        "694-bind-then-call",
        JSS,
        '            if self._member_key(bound) != "bind":\n                return []',
        "            return []",
    ),
    (
        "694-nested-invoker",
        JSS,
        "            targets.extend(self._writer_targets(obj, arguments[1:]))",
        "            targets.extend(arguments[1:2] if self._is_property_writer(obj) else [])",
    ),
    (
        "694-reflect-apply",
        JSS,
        "                targets.extend(self._writer_targets(arguments[0], listed))",
        "                pass",
    ),
    (
        "694-computed-invoker-chain",
        JSS,
        "        elif invoker in (None, _UNREADABLE_KEY) and self._writer_chain(obj):",
        "        elif invoker in (None, _UNREADABLE_KEY) and self._is_property_writer(obj):",
    ),
    (
        "694-comment-arguments",
        JSS,
        '    return [child for child in node.named_children if child.type != "comment"]\n\n\ndef _array_items',
        "    return list(node.named_children)\n\n\ndef _array_items",
    ),
    (
        "694-target-comma",
        JSS,
        "            or self._is_global_object(_callee(target), receiver=True)",
        "            or self._is_global_object(target, receiver=True)",
    ),
    (
        # The #717 review: main's positional detector is a floor; dropping
        # it loses ``*`` on ``Object.assign.call(/* c */ this, this ?? {}, …)``.
        "717-positional-floor",
        JSS,
        "        if self._positional_writer_call(node):",
        "        if False:",
    ),
    (
        "694-control-target",
        JSS,
        "            targets.extend(arguments[:1])",
        "            targets.extend(arguments[:2])",
    ),
    # Exact decoding.
    (
        "specifier-decoded",
        JSS,
        'source = decode_string_literal(node.child_by_field_name("source"), self.source)',
        "source = (lambda n: n and self.source[n.start_byte + 1 : n.end_byte - 1]"
        '.decode())(node.child_by_field_name("source"))',
    ),
    (
        "names-decoded",
        STR,
        '    if node.type == "string":\n        return decode_string_literal(node, source)',
        '    if node.type == "string":\n        return source[node.start_byte + 1 : node.end_byte - 1].decode()',
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
    with tempfile.TemporaryDirectory(prefix="tier2-mutations-") as tmp:
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
