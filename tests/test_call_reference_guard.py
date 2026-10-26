"""Real-parser proposal regressions; no fixture source is executed."""

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

import chunker.symbol_graph as candidate


def calls(graph, reference=None):
    return [
        r
        for r in graph["relationships"]
        if r["type"] == "calls" and (reference is None or r["reference"] == reference)
    ]


class CallReferenceGuard(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="jev45-parser-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)

    def file(self, text, extension="js"):
        path = self.root / ("audit." + extension)
        path.write_bytes(text.encode("utf-8"))
        return path

    def assert_unresolved_raw(self, row, reference, source):
        # Independent byte oracle: do not trust the producer's reported span.
        start = source.index(reference.encode("utf-8"))
        self.assertEqual(row["callee_byte_start"], start)
        self.assertEqual(row["callee_byte_end"], start + len(reference.encode("utf-8")))
        self.assertEqual(row["line"], source[:start].count(b"\n") + 1)
        self.assertEqual(row["reference"], reference)
        self.assertEqual(row["to"], reference)
        self.assertEqual(row["resolution"], "unresolved")
        self.assertFalse(row["is_internal"])
        self.assertEqual(row["candidates"], [])
        self.assertEqual(
            source[row["callee_byte_start"] : row["callee_byte_end"]].decode(),
            reference,
        )

    def test_comment_text_cannot_bind_local_definition(self):
        for reference in (
            "client /* audit */ .messages.create",
            "client // audit\n .messages.create",
        ):
            with self.subTest(reference=reference):
                path = self.file(
                    "export function audit(x) { return x; }\n"
                    "export function caller(x) { " + reference + "(x); }\n"
                )
                for mode in ("permissive", "strict"):
                    new = candidate.extract_symbol_graph(
                        path, "javascript", resolution_mode=mode, fail_fast=True
                    )
                    actual = calls(new, reference)
                    self.assertEqual(len(actual), 1)
                    self.assert_unresolved_raw(actual[0], reference, path.read_bytes())
                    facts = candidate.extract_symbol_facts_for_file(
                        path, path, "javascript", fail_fast=True
                    )
                    caller = next(
                        key
                        for key, row in facts["symbol_lookup"].items()
                        if row["name"] == "caller"
                    )
                    self.assertEqual(actual[0]["from"], caller)
                    self.assertEqual(actual[0]["file"], "audit.js")
                    self.assertTrue(actual[0]["call_site_id"].startswith("call:"))

    def test_computed_strings_and_non_ascii_fragments_are_not_callees(self):
        for reference in (
            'client["audit"].messages.create',
            "client[`audit`].messages.create",
            "$audit",
            "éaudit",
        ):
            with self.subTest(reference=reference):
                path = self.file(
                    "export function audit(x) { return x; }\n"
                    "export function caller(x) { " + reference + "(x); }\n"
                )
                graph = candidate.extract_symbol_graph(
                    path, "javascript", fail_fast=True
                )
                rows = calls(graph, reference)
                self.assertEqual(len(rows), 1)
                self.assert_unresolved_raw(rows[0], reference, path.read_bytes())

    def test_python_line_continuation_cannot_bind_incidental_member_name(self):
        reference = "client.\\\n        audit.create"
        path = self.file(
            "def audit(x):\n    return x\n\ndef caller(x):\n    return "
            + reference
            + "(x)\n",
            "py",
        )
        new = calls(
            candidate.extract_symbol_graph(path, "python", fail_fast=True), reference
        )
        self.assertEqual(len(new), 1)
        self.assert_unresolved_raw(new[0], reference, path.read_bytes())

    def test_python_higher_order_call_coverage_limit_is_explicit(self):
        reference = "getattr(obj, 'audit')"
        path = self.file(
            "def audit():\n    return 1\n\ndef caller():\n    return "
            + reference
            + "()\n",
            "py",
        )
        graph = candidate.extract_symbol_graph(path, "python", fail_fast=True)
        # An observed pre-existing emission limit, not a repaired outer call.
        self.assertEqual(calls(graph, reference), [])
        self.assertEqual([row["reference"] for row in calls(graph)], ["getattr"])

    def test_simple_qualified_formatted_optional_and_self_calls_are_preserved(self):
        references = ["audit", "ns.audit", "ns . audit", "ns?.audit", "audit"]
        path = self.file(
            "export function audit() { audit(); return 1; }\n"
            "export function caller() { "
            + " ".join(r + "();" for r in references)
            + " }\n"
        )
        for mode in ("strict", "permissive"):
            new = candidate.extract_symbol_graph(
                path, "javascript", resolution_mode=mode, fail_fast=True
            )
            self.assertEqual(
                new,
                candidate.extract_symbol_graph(
                    path, "javascript", resolution_mode=mode, fail_fast=True
                ),
            )
            self.assertEqual(len(calls(new)), 6)
            self.assertEqual(calls(new)[0]["from"], calls(new)[0]["to"])
            self.assertEqual(
                [row["reference"] for row in calls(new)], ["audit"] + references
            )
            for row in calls(new):
                self.assertEqual(row["resolution"], "resolved")
                self.assertEqual(row["to"], calls(new)[0]["to"])

    def test_ambiguous_and_missing_simple_calls_keep_existing_results(self):
        (self.root / "alpha.py").write_text(
            "def helper():\n    return 1\n", encoding="utf-8"
        )
        (self.root / "beta.py").write_text(
            "def helper():\n    return 2\n", encoding="utf-8"
        )
        (self.root / "caller.py").write_text(
            "def caller():\n    helper()\n    missing()\n", encoding="utf-8"
        )
        for mode in ("strict", "permissive"):
            new = candidate.extract_symbol_graph(
                self.root, "python", resolution_mode=mode, fail_fast=True
            )
            self.assertEqual(calls(new, "helper")[0]["resolution"], "ambiguous")
            self.assertEqual(len(calls(new, "helper")[0]["candidates"]), 2)
            self.assertEqual(
                calls(new, "helper")[0]["candidates"],
                sorted(calls(new, "helper")[0]["candidates"]),
            )
            self.assertEqual(calls(new, "missing")[0]["resolution"], "unresolved")

    def test_call_guard_does_not_change_import_dependency_resolver(self):
        path = self.file(
            "export function audit() { return 1; }\n"
            "export function caller() { client /* audit */ .messages.create(); }\n"
        )
        facts = candidate.extract_symbol_facts_for_file(
            path, path, "javascript", fail_fast=True
        )
        caller_id = next(
            key
            for key, row in facts["symbol_lookup"].items()
            if row["name"] == "caller"
        )
        caller = next(
            row for row in facts["chunk_records"] if row["context"]["id"] == caller_id
        )
        target = next(
            key for key, row in facts["symbol_lookup"].items() if row["name"] == "audit"
        )
        # Assembly-only fixture: retains the pre-existing shared import behavior.
        for kind in ("imports", "dependencies"):
            caller[kind] = ["client /* audit */ .messages.create"]
        new = candidate.assemble_symbol_graph(copy.deepcopy([facts]))
        for kind in ("imports", "dependencies"):
            after = [r for r in new["relationships"] if r["type"] == kind]
            self.assertEqual(len(after), 1)
            self.assertEqual(after[0]["to"], target)
            self.assertEqual(after[0]["resolution"], "resolved")
        self.assert_unresolved_raw(
            calls(new)[0], "client /* audit */ .messages.create", path.read_bytes()
        )

    def test_c_and_cpp_pointer_members_keep_simple_resolution(self):
        cases = (
            (
                "c",
                "ops->helper",
                "ops /* helper */ ->run",
                "/* café ☕ */\nvoid helper(void) {}\nvoid caller(void) {\n"
                "ops->helper(); helper(); ops /* helper */ ->run();\n}\n",
            ),
            (
                "cpp",
                "this->helper",
                "p /* helper */ ->run",
                "/* café ☕ */\nclass Worker { public:\nvoid helper() {}\n"
                "void caller() {\nthis->helper(); helper(); "
                "p /* helper */ ->run();\n}\n};\n",
            ),
        )
        for language, pointer, commented, text in cases:
            with self.subTest(language=language):
                path = self.file(text, language)
                source = text.encode("utf-8")
                for mode in ("strict", "permissive"):
                    graph = candidate.extract_symbol_graph(
                        path, language, resolution_mode=mode, fail_fast=True
                    )
                    simple = calls(graph, "helper")
                    indirect = calls(graph, pointer)
                    self.assertEqual(len(simple), 1)
                    self.assertEqual(len(indirect), 1)
                    self.assertEqual(simple[0]["resolution"], "resolved")
                    row = indirect[0]
                    self.assertEqual(row["resolution"], "resolved")
                    self.assertEqual(row["to"], simple[0]["to"])
                    self.assertEqual(row["from"], simple[0]["from"])
                    self.assertEqual(
                        graph["symbol_lookup"][row["to"]]["name"], "helper"
                    )
                    start = source.index(pointer.encode("utf-8"))
                    self.assertEqual(row["callee_byte_start"], start)
                    self.assertEqual(row["callee_byte_end"], start + len(pointer))
                    self.assertEqual(row["line"], source[:start].count(b"\n") + 1)
                    self.assertEqual(
                        source[start : start + len(pointer)].decode(), pointer
                    )
                    unresolved = calls(graph, commented)
                    self.assertEqual(len(unresolved), 1)
                    self.assert_unresolved_raw(unresolved[0], commented, source)
                self.assertEqual(path.read_bytes(), source)

    def test_scope_and_multiline_simple_chains_keep_resolution(self):
        for language, extension, reference, text in (
            (
                "cpp",
                "cpp",
                "external::audit",
                "void audit() {}\nvoid caller() { external::audit(); }\n",
            ),
            (
                "javascript",
                "js",
                "ns\n .audit",
                "export function audit() {}\nexport function caller() { ns\n .audit(); }\n",
            ),
        ):
            with self.subTest(language=language):
                path = self.file(text, extension)
                source = text.encode("utf-8")
                for mode in ("strict", "permissive"):
                    graph = candidate.extract_symbol_graph(
                        path, language, resolution_mode=mode, fail_fast=True
                    )
                    rows = calls(graph, reference)
                    self.assertEqual(len(rows), 1)
                    row = rows[0]
                    self.assertEqual(row["resolution"], "resolved")
                    self.assertEqual(graph["symbol_lookup"][row["to"]]["name"], "audit")
                    start = source.index(reference.encode("utf-8"))
                    self.assertEqual(row["callee_byte_start"], start)
                    self.assertEqual(row["callee_byte_end"], start + len(reference))
                    self.assertEqual(row["line"], source[:start].count(b"\n") + 1)

    def test_utf8_repeated_sites_preserve_independent_spans_and_owner(self):
        reference = "client /* café audit ☕ */ .messages.create"
        text = (
            "// préface ☕\n"
            "export function audit(x) { return x; }\n"
            "export function caller(x) {\n"
            "  " + reference + "(x);\n"
            "  " + reference + "(x);\n"
            "}\n"
        )
        path = self.file(text)
        source = text.encode("utf-8")
        token = reference.encode("utf-8")
        first = source.index(token)
        starts = [first, source.index(token, first + len(token))]
        self.assertNotEqual(first, text.index(reference))
        facts = candidate.extract_symbol_facts_for_file(
            path, path, "javascript", fail_fast=True
        )
        self.assertEqual(len(facts["call_facts"]), 2)
        for mode in ("strict", "permissive"):
            graph = candidate.assemble_symbol_graph(
                copy.deepcopy([facts]), resolution_mode=mode
            )
            rows = calls(graph, reference)
            self.assertEqual(len(rows), 2)
            self.assertEqual(graph["call_facts"], facts["call_facts"])
            self.assertEqual(len({row["call_site_id"] for row in rows}), 2)
            for row, start in zip(rows, starts, strict=True):
                end = start + len(token)
                call_end = end + len(b"(x)")
                line = source[:start].count(b"\n") + 1
                self.assertEqual(row["from"], facts["call_facts"][0]["from"])
                self.assertEqual(graph["symbol_lookup"][row["from"]]["name"], "caller")
                self.assertEqual(graph["symbol_lookup"][row["from"]]["line"], 3)
                self.assertEqual(row["file"], "audit.js")
                self.assertEqual(row["reference"], reference)
                self.assertEqual(row["to"], reference)
                self.assertEqual(row["candidates"], [])
                self.assertEqual(row["resolution"], "unresolved")
                self.assertFalse(row["is_internal"])
                self.assertEqual(row["callee_byte_start"], start)
                self.assertEqual(row["callee_byte_end"], end)
                self.assertEqual(row["line"], line)
                self.assertEqual(
                    row["location"],
                    {
                        "byte_start": start,
                        "byte_end": call_end,
                        "start_line": line,
                        "end_line": line,
                    },
                )
                self.assertEqual(row["call_kind"], "method")
                seed = "|".join(
                    str(value)
                    for value in (
                        row["from"],
                        "audit.js",
                        start,
                        call_end,
                        start,
                        end,
                        reference,
                        "calls",
                    )
                )
                self.assertEqual(
                    row["call_site_id"],
                    "call:" + hashlib.sha1(seed.encode("utf-8")).hexdigest(),
                )
                self.assertEqual(source[start:end], token)
                self.assertEqual(source[start:call_end], token + b"(x)")
            self.assertEqual(path.read_bytes(), source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
