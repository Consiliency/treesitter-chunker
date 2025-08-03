"""Tests for custom chunking rules."""
import pytest

from chunker.parser import get_parser
from chunker.rules.builtin import (
    ConfigurationBlockRule,
    CopyrightHeaderRule,
    CustomMarkerRule,
    DebugStatementRule,
    DocstringRule,
    ImportBlockRule,
    LanguageSpecificCommentRule,
    SectionHeaderRule,
    TestAnnotationRule,
    TodoCommentRule,
    get_builtin_rules,
)
from chunker.rules.comment import (
    DocumentationBlockRule,
    HeaderCommentRule,
    InlineCommentGroupRule,
    StructuredCommentRule,
    TodoBlockRule,
)
from chunker.rules.custom import BaseCustomRule, BaseRegexRule, MetadataRule
from chunker.rules.engine import DefaultRuleEngine
from chunker.rules.regex import (
    AnnotationRule,
    FoldingMarkerRule,
    PatternBoundaryRule,
    RegionMarkerRule,
    SeparatorLineRule,
    create_custom_regex_rule,
)
from chunker.types import CodeChunk


class TestBaseCustomRule:
    """Test BaseCustomRule implementation."""

    @classmethod
    def test_basic_properties(cls):
        """Test basic rule properties."""

        class ConcreteRule(BaseCustomRule):

            @staticmethod
            def matches(node, source):
                return True

            @staticmethod
            def extract_chunk(node, source, file_path):
                return None
        rule = ConcreteRule("test_rule", "Test description", priority=50)
        assert rule.get_name() == "test_rule"
        assert rule.get_description() == "Test description"
        assert rule.get_priority() == 50

    @classmethod
    def test_abstract_methods_not_implemented(cls):
        """Test that abstract methods must be implemented."""
        with pytest.raises(TypeError):
            BaseCustomRule("test", "desc")


class TestBaseRegexRule:
    """Test BaseRegexRule implementation."""

    @classmethod
    def test_regex_compilation(cls):
        """Test regex pattern compilation."""
        rule = BaseRegexRule("test_regex", "Test regex rule",
            "TODO:\\s*(.+)", priority=30)
        assert rule.get_name() == "test_regex"
        assert rule.get_priority() == 30
        assert rule.should_cross_node_boundaries() is True

    @classmethod
    def test_find_all_matches(cls):
        """Test finding all matches in source."""
        rule = BaseRegexRule("todo_finder", "Find TODOs",
            "TODO:\\s*(.+?)(?:\\n|$)", multiline=True)
        source = (
            b"\n        # TODO: Fix this bug\n        def foo():\n            pass\n        # TODO: Add tests\n        "
            )
        matches = rule.find_all_matches(source, "test.py")
        assert len(matches) == 2
        assert matches[0].metadata["matched_text"].strip(
            ) == "TODO: Fix this bug"
        assert matches[1].metadata["matched_text"].strip() == "TODO: Add tests"

    @classmethod
    def test_language_detection(cls):
        """Test language detection from file path."""
        rule = BaseRegexRule("test", "test", "test")
        assert rule._get_language_from_path("test.py") == "python"
        assert rule._get_language_from_path("test.js") == "javascript"
        assert rule._get_language_from_path("test.rs") == "rust"
        assert rule._get_language_from_path("test.unknown") == "unknown"


class TestTodoCommentRule:
    """Test TODO comment extraction."""

    @classmethod
    def test_todo_pattern_matching(cls):
        """Test TODO pattern matching."""
        rule = TodoCommentRule()
        test_cases = [(b"# TODO: Fix this", True), (b"// FIXME: Bug here",
            True), (b"/* HACK: Temporary solution */", True), (
            b"// NOTE: Important info", True), (b"# XXX: Needs review",
            True), (b"// BUG: Known issue", True), (
            b"# OPTIMIZE: Make faster", True), (b"// REFACTOR: Clean up",
            True), (b"Regular comment", False)]
        for source, should_match in test_cases:
            matches = rule.find_all_matches(source, "test.py")
            assert bool(matches) == should_match, f"Failed for: {source}"


class TestCopyrightHeaderRule:
    """Test copyright header extraction."""

    @classmethod
    def test_copyright_patterns(cls):
        """Test various copyright patterns."""
        rule = CopyrightHeaderRule()
        test_cases = [b"# Copyright 2024 Company Inc.",
            b"// Copyright (c) 2024", b"/* License: MIT */",
            b"# (c) 2024 Author", "// © 2024 Company".encode()]
        for source in test_cases:
            matches = rule.find_all_matches(source, "test.py")
            assert len(matches) > 0, f"Failed to match: {source}"


class TestDocstringRule:
    """Test docstring extraction."""

    @classmethod
    def test_docstring_patterns(cls):
        """Test various docstring patterns."""
        rule = DocstringRule()
        python_docstring = b'"""This is a docstring."""'
        js_doc = b"/** This is JSDoc */"
        assert len(rule.find_all_matches(python_docstring, "test.py")) == 1
        assert len(rule.find_all_matches(js_doc, "test.js")) == 1


class TestImportBlockRule:
    """Test import block extraction."""

    @classmethod
    def test_import_patterns(cls):
        """Test import pattern matching."""
        rule = ImportBlockRule()
        python_imports = b"\nimport os\nimport sys\nfrom pathlib import Path\n"
        js_imports = (
            b"\nimport React from 'react';\nimport { useState } from 'react';\nrequire('lodash');\n"
            )
        assert len(rule.find_all_matches(python_imports, "test.py")) >= 1
        assert len(rule.find_all_matches(js_imports, "test.js")) >= 1


class TestCustomMarkerRule:
    """Test custom marker extraction."""

    @classmethod
    def test_default_markers(cls):
        """Test default marker extraction."""
        rule = CustomMarkerRule()
        source = (
            b"\n        # CHUNK_START: important_function\n        def important():\n            return 42\n        # CHUNK_END\n        "
            )
        matches = rule.find_all_matches(source, "test.py")
        assert len(matches) == 1

    @classmethod
    def test_custom_markers(cls):
        """Test custom marker names."""
        rule = CustomMarkerRule("BEGIN_SECTION", "END_SECTION")
        source = (
            b"\n        // BEGIN_SECTION: config\n        const config = { debug: true };\n        // END_SECTION\n        "
            )
        matches = rule.find_all_matches(source, "test.js")
        assert len(matches) == 1


class TestMetadataRule:
    """Test file metadata extraction."""

    @classmethod
    def test_metadata_extraction(cls):
        """Test metadata extraction for root node."""
        rule = MetadataRule()
        parser = get_parser("python")
        source = b"def test():\n    pass\n"
        tree = parser.parse(source)
        chunk = rule.extract_chunk(tree.root_node, source, "test.py")
        assert chunk is not None
        assert chunk.node_type == "file_metadata"
        assert "Total Lines: 3" in chunk.content
        assert "Language: python" in chunk.content

    @classmethod
    def test_non_root_node(cls):
        """Test that non-root nodes don't match."""
        rule = MetadataRule()
        parser = get_parser("python")
        source = b"def test(): pass"
        tree = parser.parse(source)
        func_node = tree.root_node.children[0]
        chunk = rule.extract_chunk(func_node, source, "test.py")
        assert chunk is None


class TestRuleEngine:
    """Test the rule engine."""

    @classmethod
    def test_add_remove_rules(cls):
        """Test adding and removing rules."""
        engine = DefaultRuleEngine()
        rule = TodoCommentRule()
        engine.add_rule(rule)
        rules = engine.list_rules()
        assert len(rules) == 1
        assert rules[0]["name"] == "todo_comments"
        assert engine.remove_rule("todo_comments") is True
        assert len(engine.list_rules()) == 0
        assert engine.remove_rule("non_existent") is False

    @classmethod
    def test_priority_ordering(cls):
        """Test rules are ordered by priority."""
        engine = DefaultRuleEngine()
        engine.add_rule(TodoCommentRule(priority=10))
        engine.add_rule(CopyrightHeaderRule(priority=90))
        engine.add_rule(DocstringRule(priority=50))
        rules = engine.list_rules()
        assert rules[0]["priority"] == 90
        assert rules[1]["priority"] == 50
        assert rules[2]["priority"] == 10

    @classmethod
    def test_apply_rules_to_python(cls):
        """Test applying rules to Python code."""
        engine = DefaultRuleEngine()
        engine.add_rule(TodoCommentRule())
        engine.add_rule(DocstringRule())
        engine.add_rule(MetadataRule())
        source = (
            b'"""Module docstring."""\n\n# TODO: Add more features\ndef test():\n    """Function docstring."""\n    pass\n'
            )
        parser = get_parser("python")
        tree = parser.parse(source)
        chunks = engine.apply_rules(tree, source, "test.py")
        assert len(chunks) >= 3
        chunk_types = {chunk.node_type for chunk in chunks}
        assert any("todo_comments" in t for t in chunk_types)
        assert any("docstring" in t for t in chunk_types)
        assert "file_metadata" in chunk_types

    @classmethod
    def test_apply_regex_rules_only(cls):
        """Test applying only regex rules."""
        engine = DefaultRuleEngine()
        engine.add_rule(TodoCommentRule())
        engine.add_rule(ImportBlockRule())
        source = b"\nimport os\n# TODO: Fix imports\nimport sys\n"
        chunks = engine.apply_regex_rules(source, "test.py")
        assert len(chunks) >= 1
        chunk_types = {chunk.node_type for chunk in chunks}
        assert any("todo_comments" in t for t in chunk_types)

    @classmethod
    def test_merge_with_tree_sitter(cls):
        """Test merging custom chunks with Tree-sitter chunks."""
        engine = DefaultRuleEngine()
        ts_chunks = [CodeChunk(language="python", file_path="test.py",
            node_type="function_definition", start_line=1, end_line=3,
            byte_start=0, byte_end=50, parent_context="module", content="def test(): pass")]
        custom_chunks = [CodeChunk(language="python", file_path="test.py",
            node_type="regex_match_todo_comments", start_line=2, end_line=2,
            byte_start=20, byte_end=40, parent_context="file", content="# TODO: Fix this")]
        merged = engine.merge_with_tree_sitter_chunks(custom_chunks, ts_chunks)
        assert len(merged) == 2

    @classmethod
    def test_overlap_handling(cls):
        """Test handling of overlapping chunks."""
        engine = DefaultRuleEngine()
        chunks1 = [CodeChunk(language="python", file_path="test.py",
            node_type="chunk1", start_line=1, end_line=5, byte_start=0,
            byte_end=100, parent_context="file", content="content1")]
        chunks2 = [CodeChunk(language="python", file_path="test.py",
            node_type="chunk2", start_line=3, end_line=7, byte_start=50,
            byte_end=150, parent_context="file", content="content2")]
        merged = engine.merge_with_tree_sitter_chunks(chunks2, chunks1)
        assert len(merged) >= 1


class TestBuiltinRules:
    """Test all builtin rules."""

    @staticmethod
    def test_get_builtin_rules():
        """Test getting all builtin rules."""
        rules = get_builtin_rules()
        assert len(rules) == 11
        rule_names = {rule.get_name() for rule in rules}
        expected_names = {"todo_comments", "copyright_header", "docstring",
            "import_block", "custom_markers", "section_headers",
            "config_blocks", "language_comments", "debug_statements",
            "test_markers", "file_metadata"}
        assert rule_names == expected_names

    @classmethod
    def test_section_header_rule(cls):
        """Test section header extraction."""
        rule = SectionHeaderRule()
        source = (
            b"\n# === Main Section ===\ncode here\n// --- Sub Section ---\nmore code\n"
            )
        matches = rule.find_all_matches(source, "test.py")
        assert len(matches) == 2

    @classmethod
    def test_config_block_rule(cls):
        """Test configuration block extraction."""
        rule = ConfigurationBlockRule()
        source = (
            b'\n/* config: {\n    "debug": true,\n    "level": "info"\n} */\n')
        matches = rule.find_all_matches(source, "test.js")
        assert len(matches) == 1

    @classmethod
    def test_debug_statement_rule(cls):
        """Test debug statement extraction."""
        rule = DebugStatementRule()
        test_cases = [b'console.log("debug");', b'print("test")',
            b'System.out.println("java");', b'logger.debug("log");']
        for source in test_cases:
            matches = rule.find_all_matches(source, "test.js")
            assert len(matches) == 1

    @classmethod
    def test_test_annotation_rule(cls):
        """Test test annotation extraction."""
        rule = TestAnnotationRule()
        test_cases = [b'@test("should work")',
            b'it("test case", function() {', b'TEST_CASE("cpp test")',
            b'@skip("not ready")']
        for source in test_cases:
            matches = rule.find_all_matches(source, "test.js")
            assert len(matches) >= 1


class TestLanguageSpecificCommentRule:
    """Test language-specific comment handling."""

    @classmethod
    def test_language_detection(cls):
        """Test language-specific comment detection."""
        rule = LanguageSpecificCommentRule()
        parser = get_parser("python")
        source = b"# Python comment"
        tree = parser.parse(source)
        if tree.root_node.children:
            for child in tree.root_node.children:
                if "comment" in child.type:
                    chunk = rule.extract_chunk(child, source, "test.py")
                    if chunk:
                        assert "python" in chunk.node_type

    @classmethod
    def test_comment_markers(cls):
        """Test getting comment markers."""
        rule = LanguageSpecificCommentRule()
        markers = rule.get_comment_markers()
        assert "single_line" in markers
        assert "block_start" in markers
        assert "block_end" in markers


class TestRegexRules:
    """Test new regex-based rules from regex.py."""

    @classmethod
    def test_region_marker_rule(cls):
        """Test region marker extraction."""
        rule = RegionMarkerRule()
        source = (
            b"\n        // #region Helper Functions\n        function helper1() { return 1; }\n        function helper2() { return 2; }\n        // #endregion\n        "
            )
        matches = rule.find_all_matches(source, "test.js")
        assert len(matches) == 1
        assert "helper1" in matches[0].metadata["matched_text"]

    @classmethod
    def test_custom_region_markers(cls):
        """Test custom region markers."""
        rule = RegionMarkerRule("START", "END")
        source = (
            b"\n        # START important code\n        def critical_function():\n            return secure_data()\n        # END\n        "
            )
        matches = rule.find_all_matches(source, "test.py")
        assert len(matches) == 1

    @classmethod
    def test_pattern_boundary_rule_extract_match(cls):
        """Test pattern boundary with match extraction."""
        rule = PatternBoundaryRule("function_headers",
            "function\\s+(\\w+)\\s*\\([^)]*\\)", extract_match_only=True)
        source = (
            b"\n        function test1() { return 1; }\n        function test2(arg) { return arg; }\n        "
            )
        matches = rule.find_all_matches(source, "test.js")
        assert len(matches) == 2

    @classmethod
    def test_pattern_boundary_rule_between_matches(cls):
        """Test pattern boundary extracting between matches."""
        rule = PatternBoundaryRule("between_sections", "^={3,}$",
            extract_match_only=False, priority=40)
        source = (
            b"===\nSection 1 content\nMore content\n===\nSection 2 content\n==="
            )
        matches = rule.find_all_matches(source, "test.txt")
        assert len(matches) >= 1
        assert "Section 1" in matches[0].metadata["region_content"]

    @classmethod
    def test_annotation_rule(cls):
        """Test annotation-based chunking."""
        rule = AnnotationRule()
        source = (
            b"\n        @chunk performance\n        def optimized_function():\n            # Fast implementation\n            return result\n\n        @chunk security\n        def secure_function():\n            # Security-critical code\n            return encrypted_data\n        "
            )
        matches = rule.find_all_matches(source, "test.py")
        assert len(matches) == 2

    @classmethod
    def test_folding_marker_rule(cls):
        """Test folding marker extraction."""
        rule = FoldingMarkerRule()
        source = (
            b"\n        // {{{ Utility Functions\n        function util1() {}\n        function util2() {}\n        // }}}\n        "
            )
        matches = rule.find_all_matches(source, "test.js")
        assert len(matches) == 1
        assert "util1" in matches[0].metadata["matched_text"]

    @classmethod
    def test_separator_line_rule(cls):
        """Test separator line chunking."""
        rule = SeparatorLineRule()
        source = (
            b"First section\nSome content here\n-----\nSecond section\nMore content\n=====\nThird section"
            )
        matches = rule.find_all_matches(source, "test.txt")
        assert len(matches) >= 2

    @staticmethod
    def test_create_custom_regex_rule():
        """Test custom regex rule factory."""
        rule = create_custom_regex_rule("custom_test",
            "TEST_CASE\\([^)]+\\)", description="Extract test cases",
            priority=70)
        assert rule.get_name() == "custom_test"
        assert rule.get_priority() == 70


class TestCommentRules:
    """Test new comment-based rules from comment.py."""

    @classmethod
    def test_todo_block_rule(cls):
        """Test TODO block extraction with context."""
        rule = TodoBlockRule(include_context_lines=1)
        parser = get_parser("python")
        source = (
            b"def process():\n    # TODO: Optimize this function\n    result = slow_operation()\n    return result"
            )
        tree = parser.parse(source)
        for node in tree.root_node.children[0].children:
            if "comment" in node.type:
                chunk = rule.extract_chunk(node, source, "test.py")
                if chunk:
                    assert "todo_block_todo" in chunk.node_type
                    assert "slow_operation" in chunk.content

    @classmethod
    def test_documentation_block_rule(cls):
        """Test documentation block extraction."""
        rule = DocumentationBlockRule()
        parser = get_parser("python")
        source = b'def test():\n    """This is a docstring."""\n    pass'
        tree = parser.parse(source)
        func_node = tree.root_node.children[0]
        for child in func_node.children:
            if child.type in {"string", "expression_statement"}:
                string_node = (child if child.type == "string" else child.
                    children[0])
                if string_node.type == "string":
                    chunk = rule.extract_chunk(string_node, source, "test.py")
                    if chunk:
                        assert "doc_block" in chunk.node_type

    @classmethod
    def test_header_comment_rule(cls):
        """Test header comment extraction."""
        rule = HeaderCommentRule()
        parser = get_parser("python")
        source = (
            b"# Copyright 2024 Company Inc.\n# Licensed under MIT License\n# Author: Developer\n\nimport os\n"
            )
        tree = parser.parse(source)
        for child in tree.root_node.children:
            if "comment" in child.type:
                chunk = rule.extract_chunk(child, source, "test.py")
                if chunk:
                    assert chunk.node_type == "header_comment"
                    break

    @classmethod
    def test_inline_comment_group_rule(cls):
        """Test inline comment grouping."""
        rule = InlineCommentGroupRule(max_gap_lines=1, min_comments=2)
        parser = get_parser("python")
        source = (
            b"\ndef function():\n    # First comment\n    x = 1\n    # Second comment\n    y = 2\n    # Third comment\n    z = 3\n"
            )
        tree = parser.parse(source)
        func_node = tree.root_node.children[0]
        if func_node.type == "function_definition":
            for child in func_node.children:
                if child.type == "block":
                    for stmt in child.children:
                        if "comment" in stmt.type:
                            chunk = rule.extract_chunk(stmt, source, "test.py")
                            if chunk:
                                assert chunk.node_type == "inline_comment_group"
                                assert chunk.content.count("#") >= 2
                                break

    @classmethod
    def test_structured_comment_rule(cls):
        """Test structured comment extraction."""
        rule = StructuredCommentRule()
        parser = get_parser("python")
        source = (
            b'"""\nModule documentation with structure:\n\n- Feature 1: Description\n- Feature 2: Description\n- Feature 3: Description\n\n| Column 1 | Column 2 |\n|----------|----------|\n| Data 1   | Data 2   |\n"""'
            )
        tree = parser.parse(source)
        for child in tree.root_node.children:
            if child.type in {"string", "expression_statement"}:
                node = child if child.type == "string" else child.children[0]
                if "comment" in node.type or node.type == "string":
                    chunk = rule.extract_chunk(node, source, "test.py")
                    if chunk:
                        assert "structured_comment" in chunk.node_type

    @classmethod
    def test_comment_rule_chain(cls):
        """Test comment rule chaining."""
        from chunker.rules.comment import (
            DocumentationBlockRule,
            HeaderCommentRule,
            TodoBlockRule,
            create_comment_rule_chain,
        )
        rules = create_comment_rule_chain(TodoBlockRule(priority=50),
            HeaderCommentRule(priority=90), DocumentationBlockRule(priority=70),
            )
        assert rules[0].get_priority() == 90
        assert rules[1].get_priority() == 70
        assert rules[2].get_priority() == 50


class TestRuleComposition:
    """Test rule composition and complex scenarios."""

    @classmethod
    def test_multiple_rule_types(cls):
        """Test engine with multiple rule types."""
        engine = DefaultRuleEngine()
        engine.add_rule(RegionMarkerRule(priority=80))
        engine.add_rule(SeparatorLineRule(priority=40))
        engine.add_rule(TodoBlockRule(priority=60))
        engine.add_rule(HeaderCommentRule(priority=90))
        engine.add_rule(MetadataRule(priority=100))
        source = (
            b"# Copyright 2024\n# License: MIT\n\n#region Main Code\ndef main():\n    # TODO: Implement main logic\n    pass\n#endregion\n\n-----\n\ndef helper():\n    pass\n"
            )
        parser = get_parser("python")
        tree = parser.parse(source)
        chunks = engine.apply_rules(tree, source, "test.py")
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "file_metadata" in chunk_types
        assert any("region" in t for t in chunk_types)
        assert any("todo" in t for t in chunk_types)

    @classmethod
    def test_overlapping_rules(cls):
        """Test handling of overlapping rule matches."""
        engine = DefaultRuleEngine()
        engine.add_rule(RegionMarkerRule(priority=80))
        engine.add_rule(PatternBoundaryRule("functions",
            "def\\s+\\w+\\s*\\([^)]*\\):", extract_match_only=True,
            priority=60))
        source = (
            b"\n#region Functions\ndef func1():\n    pass\n\ndef func2():\n    pass\n#endregion\n"
            )
        parser = get_parser("python")
        tree = parser.parse(source)
        chunks = engine.apply_rules(tree, source, "test.py")
        assert len(chunks) >= 1

    @staticmethod
    def test_rule_priority_execution():
        """Test that rules execute in priority order."""
        engine = DefaultRuleEngine()
        execution_order = []

        class TrackingRule(BaseRegexRule):

            def find_all_matches(self, source, file_path):
                execution_order.append(self.get_name())
                return super().find_all_matches(source, file_path)
        for priority in [30, 90, 50, 70]:
            rule = TrackingRule(f"rule_{priority}", f"Test rule {priority}",
                "test", priority=priority)
            engine.add_rule(rule)
        source = b"test content"
        engine.apply_regex_rules(source, "test.txt")
        expected_order = ["rule_90", "rule_70", "rule_50", "rule_30"]
        assert execution_order == expected_order
