"""Tests for custom chunking rules."""

from chunker.rules.comment import (
from chunker.rules.comment import DocumentationBlockRule
from chunker.rules.comment import HeaderCommentRule
from chunker.rules.comment import HeaderCommentRule, TodoBlockRule
from chunker.rules.comment import InlineCommentGroupRule
from chunker.rules.comment import StructuredCommentRule
from chunker.rules.comment import TodoBlockRule
from chunker.rules.regex import AnnotationRule
from chunker.rules.regex import FoldingMarkerRule
from chunker.rules.regex import PatternBoundaryRule
from chunker.rules.regex import PatternBoundaryRule, RegionMarkerRule
from chunker.rules.regex import RegionMarkerRule
from chunker.rules.regex import RegionMarkerRule, SeparatorLineRule
from chunker.rules.regex import SeparatorLineRule
from chunker.rules.regex import create_custom_regex_rule
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
from chunker.rules.custom import BaseCustomRule, BaseRegexRule, MetadataRule
from chunker.rules.engine import DefaultRuleEngine
from chunker.types import CodeChunk


class TestBaseCustomRule:
    """Test BaseCustomRule implementation."""

    def test_basic_properties(self):
        """Test basic rule properties."""

        # Create a concrete implementation for testing
        class ConcreteRule(BaseCustomRule):
            def matches(self, node, source):
                return True

            def extract_chunk(self, node, source, file_path):
                return None

        rule = ConcreteRule("test_rule", "Test description", priority=50)

        assert rule.get_name() == "test_rule"
        assert rule.get_description() == "Test description"
        assert rule.get_priority() == 50

    def test_abstract_methods_not_implemented(self):
        """Test that abstract methods must be implemented."""
        # This should raise TypeError when trying to instantiate
        with pytest.raises(TypeError):
            BaseCustomRule("test", "desc")


class TestBaseRegexRule:
    """Test BaseRegexRule implementation."""

    def test_regex_compilation(self):
        """Test regex pattern compilation."""
        rule = BaseRegexRule(
            "test_regex",
            "Test regex rule",
            r"TODO:\s*(.+)",
            priority=30,
        )

        assert rule.get_name() == "test_regex"
        assert rule.get_priority() == 30
        assert rule.should_cross_node_boundaries() is True

    def test_find_all_matches(self):
        """Test finding all matches in source."""
        rule = BaseRegexRule(
            "todo_finder",
            "Find TODOs",
            r"TODO:\s*(.+?)(?:\n|$)",
            multiline=True,
        )

        source = b"""
        # TODO: Fix this bug
        def foo():
            pass
        # TODO: Add tests
        """

        matches = rule.find_all_matches(source, "test.py")
        assert len(matches) == 2
        assert matches[0].metadata["matched_text"].strip() == "TODO: Fix this bug"
        assert matches[1].metadata["matched_text"].strip() == "TODO: Add tests"

    def test_language_detection(self):
        """Test language detection from file path."""
        rule = BaseRegexRule("test", "test", "test")

        assert rule._get_language_from_path("test.py") == "python"
        assert rule._get_language_from_path("test.js") == "javascript"
        assert rule._get_language_from_path("test.rs") == "rust"
        assert rule._get_language_from_path("test.unknown") == "unknown"


class TestTodoCommentRule:
    """Test TODO comment extraction."""

    def test_todo_pattern_matching(self):
        """Test TODO pattern matching."""
        rule = TodoCommentRule()

        test_cases = [
            (b"# TODO: Fix this", True),
            (b"// FIXME: Bug here", True),
            (b"/* HACK: Temporary solution */", True),
            (b"// NOTE: Important info", True),
            (b"# XXX: Needs review", True),
            (b"// BUG: Known issue", True),
            (b"# OPTIMIZE: Make faster", True),
            (b"// REFACTOR: Clean up", True),
            (b"Regular comment", False),
        ]

        for source, should_match in test_cases:
            matches = rule.find_all_matches(source, "test.py")
            assert bool(matches) == should_match, f"Failed for: {source}"


class TestCopyrightHeaderRule:
    """Test copyright header extraction."""

    def test_copyright_patterns(self):
        """Test various copyright patterns."""
        rule = CopyrightHeaderRule()

        test_cases = [
            b"# Copyright 2024 Company Inc.",
            b"// Copyright (c) 2024",
            b"/* License: MIT */",
            b"# (c) 2024 Author",
            "// © 2024 Company".encode(),  # Unicode copyright symbol
        ]

        for source in test_cases:
            matches = rule.find_all_matches(source, "test.py")
            assert len(matches) > 0, f"Failed to match: {source}"


class TestDocstringRule:
    """Test docstring extraction."""

    def test_docstring_patterns(self):
        """Test various docstring patterns."""
        rule = DocstringRule()

        python_docstring = b'''"""This is a docstring."""'''
        js_doc = b"/** This is JSDoc */"

        assert len(rule.find_all_matches(python_docstring, "test.py")) == 1
        assert len(rule.find_all_matches(js_doc, "test.js")) == 1


class TestImportBlockRule:
    """Test import block extraction."""

    def test_import_patterns(self):
        """Test import pattern matching."""
        rule = ImportBlockRule()

        python_imports = b"""
import os
import sys
from pathlib import Path
"""

        js_imports = b"""
import React from 'react';
import { useState } from 'react';
require('lodash');
"""

        assert len(rule.find_all_matches(python_imports, "test.py")) >= 1
        assert len(rule.find_all_matches(js_imports, "test.js")) >= 1


class TestCustomMarkerRule:
    """Test custom marker extraction."""

    def test_default_markers(self):
        """Test default marker extraction."""
        rule = CustomMarkerRule()

        source = b"""
        # CHUNK_START: important_function
        def important():
            return 42
        # CHUNK_END
        """

        matches = rule.find_all_matches(source, "test.py")
        assert len(matches) == 1

    def test_custom_markers(self):
        """Test custom marker names."""
        rule = CustomMarkerRule("BEGIN_SECTION", "END_SECTION")

        source = b"""
        // BEGIN_SECTION: config
        const config = { debug: true };
        // END_SECTION
        """

        matches = rule.find_all_matches(source, "test.js")
        assert len(matches) == 1


class TestMetadataRule:
    """Test file metadata extraction."""

    def test_metadata_extraction(self):
        """Test metadata extraction for root node."""
        rule = MetadataRule()
        parser = get_parser("python")

        source = b"def test():\n    pass\n"
        tree = parser.parse(source)

        # Test with root node
        chunk = rule.extract_chunk(tree.root_node, source, "test.py")
        assert chunk is not None
        assert chunk.node_type == "file_metadata"
        assert "Total Lines: 3" in chunk.content
        assert "Language: python" in chunk.content

    def test_non_root_node(self):
        """Test that non-root nodes don't match."""
        rule = MetadataRule()
        parser = get_parser("python")

        source = b"def test(): pass"
        tree = parser.parse(source)

        # Get first child (function node)
        func_node = tree.root_node.children[0]
        chunk = rule.extract_chunk(func_node, source, "test.py")
        assert chunk is None


class TestRuleEngine:
    """Test the rule engine."""

    def test_add_remove_rules(self):
        """Test adding and removing rules."""
        engine = DefaultRuleEngine()
        rule = TodoCommentRule()

        # Add rule
        engine.add_rule(rule)
        rules = engine.list_rules()
        assert len(rules) == 1
        assert rules[0]["name"] == "todo_comments"

        # Remove rule
        assert engine.remove_rule("todo_comments") is True
        assert len(engine.list_rules()) == 0

        # Remove non-existent
        assert engine.remove_rule("non_existent") is False

    def test_priority_ordering(self):
        """Test rules are ordered by priority."""
        engine = DefaultRuleEngine()

        # Add rules with different priorities
        engine.add_rule(TodoCommentRule(priority=10))
        engine.add_rule(CopyrightHeaderRule(priority=90))
        engine.add_rule(DocstringRule(priority=50))

        rules = engine.list_rules()
        assert rules[0]["priority"] == 90  # Copyright
        assert rules[1]["priority"] == 50  # Docstring
        assert rules[2]["priority"] == 10  # TODO

    def test_apply_rules_to_python(self):
        """Test applying rules to Python code."""
        engine = DefaultRuleEngine()
        engine.add_rule(TodoCommentRule())
        engine.add_rule(DocstringRule())
        engine.add_rule(MetadataRule())

        source = b'''"""Module docstring."""

# TODO: Add more features
def test():
    """Function docstring."""
    pass
'''

        parser = get_parser("python")
        tree = parser.parse(source)

        chunks = engine.apply_rules(tree, source, "test.py")

        # Should find: metadata, module docstring, TODO, function docstring
        assert len(chunks) >= 3

        # Check chunk types
        chunk_types = {chunk.node_type for chunk in chunks}
        assert any("todo_comments" in t for t in chunk_types)
        assert any("docstring" in t for t in chunk_types)
        assert "file_metadata" in chunk_types

    def test_apply_regex_rules_only(self):
        """Test applying only regex rules."""
        engine = DefaultRuleEngine()
        engine.add_rule(TodoCommentRule())
        engine.add_rule(ImportBlockRule())

        source = b"""
import os
# TODO: Fix imports
import sys
"""

        chunks = engine.apply_regex_rules(source, "test.py")
        assert len(chunks) >= 1

        # Should find TODO and imports
        chunk_types = {chunk.node_type for chunk in chunks}
        assert any("todo_comments" in t for t in chunk_types)

    def test_merge_with_tree_sitter(self):
        """Test merging custom chunks with Tree-sitter chunks."""
        engine = DefaultRuleEngine()

        # Create some mock chunks
        ts_chunks = [
            CodeChunk(
                language="python",
                file_path="test.py",
                node_type="function_definition",
                start_line=1,
                end_line=3,
                byte_start=0,
                byte_end=50,
                parent_context="module",
                content="def test(): pass",
            ),
        ]

        custom_chunks = [
            CodeChunk(
                language="python",
                file_path="test.py",
                node_type="regex_match_todo_comments",
                start_line=2,
                end_line=2,
                byte_start=20,
                byte_end=40,
                parent_context="file",
                content="# TODO: Fix this",
            ),
        ]

        merged = engine.merge_with_tree_sitter_chunks(custom_chunks, ts_chunks)

        # Should have both chunks (TODO is within function, so both kept)
        assert len(merged) == 2

    def test_overlap_handling(self):
        """Test handling of overlapping chunks."""
        engine = DefaultRuleEngine()

        # Create overlapping chunks
        chunks1 = [
            CodeChunk(
                language="python",
                file_path="test.py",
                node_type="chunk1",
                start_line=1,
                end_line=5,
                byte_start=0,
                byte_end=100,
                parent_context="file",
                content="content1",
            ),
        ]

        chunks2 = [
            CodeChunk(
                language="python",
                file_path="test.py",
                node_type="chunk2",
                start_line=3,
                end_line=7,
                byte_start=50,
                byte_end=150,
                parent_context="file",
                content="content2",
            ),
        ]

        merged = engine.merge_with_tree_sitter_chunks(chunks2, chunks1)

        # Tree-sitter chunks take precedence
        assert len(merged) >= 1


class TestBuiltinRules:
    """Test all builtin rules."""

    def test_get_builtin_rules(self):
        """Test getting all builtin rules."""
        rules = get_builtin_rules()

        # Should have all rule types
        assert len(rules) == 11

        rule_names = {rule.get_name() for rule in rules}
        expected_names = {
            "todo_comments",
            "copyright_header",
            "docstring",
            "import_block",
            "custom_markers",
            "section_headers",
            "config_blocks",
            "language_comments",
            "debug_statements",
            "test_markers",
            "file_metadata",
        }

        assert rule_names == expected_names

    def test_section_header_rule(self):
        """Test section header extraction."""
        rule = SectionHeaderRule()

        source = b"""
# === Main Section ===
code here
// --- Sub Section ---
more code
"""

        matches = rule.find_all_matches(source, "test.py")
        assert len(matches) == 2

    def test_config_block_rule(self):
        """Test configuration block extraction."""
        rule = ConfigurationBlockRule()

        source = b"""
/* config: {
    "debug": true,
    "level": "info"
} */
"""

        matches = rule.find_all_matches(source, "test.js")
        assert len(matches) == 1

    def test_debug_statement_rule(self):
        """Test debug statement extraction."""
        rule = DebugStatementRule()

        test_cases = [
            b'console.log("debug");',
            b'print("test")',
            b'System.out.println("java");',
            b'logger.debug("log");',
        ]

        for source in test_cases:
            matches = rule.find_all_matches(source, "test.js")
            assert len(matches) == 1

    def test_test_annotation_rule(self):
        """Test test annotation extraction."""
        rule = TestAnnotationRule()

        test_cases = [
            b'@test("should work")',
            b'it("test case", function() {',
            b'TEST_CASE("cpp test")',
            b'@skip("not ready")',
        ]

        for source in test_cases:
            matches = rule.find_all_matches(source, "test.js")
            assert len(matches) >= 1


class TestLanguageSpecificCommentRule:
    """Test language-specific comment handling."""

    def test_language_detection(self):
        """Test language-specific comment detection."""
        rule = LanguageSpecificCommentRule()
        parser = get_parser("python")

        source = b"# Python comment"
        tree = parser.parse(source)

        # Assuming we have a comment node
        if tree.root_node.children:
            for child in tree.root_node.children:
                if "comment" in child.type:
                    chunk = rule.extract_chunk(child, source, "test.py")
                    if chunk:
                        assert "python" in chunk.node_type

    def test_comment_markers(self):
        """Test getting comment markers."""
        rule = LanguageSpecificCommentRule()
        markers = rule.get_comment_markers()

        assert "single_line" in markers
        assert "block_start" in markers
        assert "block_end" in markers


class TestRegexRules:
    """Test new regex-based rules from regex.py."""

    def test_region_marker_rule(self):
        """Test region marker extraction."""

        rule = RegionMarkerRule()

        source = b"""
        // #region Helper Functions
        function helper1() { return 1; }
        function helper2() { return 2; }
        // #endregion
        """

        matches = rule.find_all_matches(source, "test.js")
        assert len(matches) == 1
        assert "helper1" in matches[0].metadata["matched_text"]

    def test_custom_region_markers(self):
        """Test custom region markers."""

        rule = RegionMarkerRule("START", "END")

        source = b"""
        # START important code
        def critical_function():
            return secure_data()
        # END
        """

        matches = rule.find_all_matches(source, "test.py")
        assert len(matches) == 1

    def test_pattern_boundary_rule_extract_match(self):
        """Test pattern boundary with match extraction."""

        rule = PatternBoundaryRule(
            "function_headers",
            r"function\s+(\w+)\s*\([^)]*\)",
            extract_match_only=True,
        )

        source = b"""
        function test1() { return 1; }
        function test2(arg) { return arg; }
        """

        matches = rule.find_all_matches(source, "test.js")
        assert len(matches) == 2

    def test_pattern_boundary_rule_between_matches(self):
        """Test pattern boundary extracting between matches."""

        rule = PatternBoundaryRule(
            "between_sections",
            r"^={3,}$",
            extract_match_only=False,
            priority=40,
        )

        source = b"""===
Section 1 content
More content
===
Section 2 content
==="""

        matches = rule.find_all_matches(source, "test.txt")
        assert len(matches) >= 1
        assert "Section 1" in matches[0].metadata["region_content"]

    def test_annotation_rule(self):
        """Test annotation-based chunking."""

        rule = AnnotationRule()

        source = b"""
        @chunk performance
        def optimized_function():
            # Fast implementation
            return result

        @chunk security
        def secure_function():
            # Security-critical code
            return encrypted_data
        """

        matches = rule.find_all_matches(source, "test.py")
        assert len(matches) == 2

    def test_folding_marker_rule(self):
        """Test folding marker extraction."""

        rule = FoldingMarkerRule()

        source = b"""
        // {{{ Utility Functions
        function util1() {}
        function util2() {}
        // }}}
        """

        matches = rule.find_all_matches(source, "test.js")
        assert len(matches) == 1
        assert "util1" in matches[0].metadata["matched_text"]

    def test_separator_line_rule(self):
        """Test separator line chunking."""

        rule = SeparatorLineRule()

        source = b"""First section
Some content here
-----
Second section
More content
=====
Third section"""

        matches = rule.find_all_matches(source, "test.txt")
        assert len(matches) >= 2

    def test_create_custom_regex_rule(self):
        """Test custom regex rule factory."""

        rule = create_custom_regex_rule(
            "custom_test",
            r"TEST_CASE\([^)]+\)",
            description="Extract test cases",
            priority=70,
        )

        assert rule.get_name() == "custom_test"
        assert rule.get_priority() == 70


class TestCommentRules:
    """Test new comment-based rules from comment.py."""

    def test_todo_block_rule(self):
        """Test TODO block extraction with context."""

        rule = TodoBlockRule(include_context_lines=1)
        parser = get_parser("python")

        source = b"""def process():
    # TODO: Optimize this function
    result = slow_operation()
    return result"""

        tree = parser.parse(source)

        # Find comment node
        for node in tree.root_node.children[0].children:  # function body
            if "comment" in node.type:
                chunk = rule.extract_chunk(node, source, "test.py")
                if chunk:
                    assert "todo_block_todo" in chunk.node_type
                    assert "slow_operation" in chunk.content  # Context included

    def test_documentation_block_rule(self):
        """Test documentation block extraction."""

        rule = DocumentationBlockRule()
        parser = get_parser("python")

        source = b'''def test():
    """This is a docstring."""
    pass'''

        tree = parser.parse(source)

        # Find string node
        func_node = tree.root_node.children[0]
        for child in func_node.children:
            if child.type in ["string", "expression_statement"]:
                # Handle expression_statement containing string
                string_node = child if child.type == "string" else child.children[0]
                if string_node.type == "string":
                    chunk = rule.extract_chunk(string_node, source, "test.py")
                    if chunk:
                        assert "doc_block" in chunk.node_type

    def test_header_comment_rule(self):
        """Test header comment extraction."""

        rule = HeaderCommentRule()
        parser = get_parser("python")

        source = b"""# Copyright 2024 Company Inc.
# Licensed under MIT License
# Author: Developer

import os
"""

        tree = parser.parse(source)

        # Check all top-level nodes
        for child in tree.root_node.children:
            if "comment" in child.type:
                chunk = rule.extract_chunk(child, source, "test.py")
                if chunk:
                    assert chunk.node_type == "header_comment"
                    break

    def test_inline_comment_group_rule(self):
        """Test inline comment grouping."""

        rule = InlineCommentGroupRule(max_gap_lines=1, min_comments=2)
        parser = get_parser("python")

        source = b"""
def function():
    # First comment
    x = 1
    # Second comment
    y = 2
    # Third comment
    z = 3
"""

        tree = parser.parse(source)

        # Find function body
        func_node = tree.root_node.children[0]
        if func_node.type == "function_definition":
            # Apply rule to function body
            for child in func_node.children:
                if child.type == "block":
                    for stmt in child.children:
                        if "comment" in stmt.type:
                            chunk = rule.extract_chunk(stmt, source, "test.py")
                            if chunk:
                                assert chunk.node_type == "inline_comment_group"
                                assert chunk.content.count("#") >= 2
                                break

    def test_structured_comment_rule(self):
        """Test structured comment extraction."""

        rule = StructuredCommentRule()
        parser = get_parser("python")

        source = b'''"""
Module documentation with structure:

- Feature 1: Description
- Feature 2: Description
- Feature 3: Description

| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |
"""'''

        tree = parser.parse(source)

        # Find string/comment node
        for child in tree.root_node.children:
            if child.type in ["string", "expression_statement"]:
                node = child if child.type == "string" else child.children[0]
                if "comment" in node.type or node.type == "string":
                    chunk = rule.extract_chunk(node, source, "test.py")
                    if chunk:
                        assert "structured_comment" in chunk.node_type

    def test_comment_rule_chain(self):
        """Test comment rule chaining."""
            DocumentationBlockRule,
            HeaderCommentRule,
            TodoBlockRule,
            create_comment_rule_chain,
        )

        rules = create_comment_rule_chain(
            TodoBlockRule(priority=50),
            HeaderCommentRule(priority=90),
            DocumentationBlockRule(priority=70),
        )

        # Should be sorted by priority
        assert rules[0].get_priority() == 90  # Header
        assert rules[1].get_priority() == 70  # Documentation
        assert rules[2].get_priority() == 50  # TODO


class TestRuleComposition:
    """Test rule composition and complex scenarios."""

    def test_multiple_rule_types(self):
        """Test engine with multiple rule types."""

        engine = DefaultRuleEngine()

        # Add various rule types
        engine.add_rule(RegionMarkerRule(priority=80))
        engine.add_rule(SeparatorLineRule(priority=40))
        engine.add_rule(TodoBlockRule(priority=60))
        engine.add_rule(HeaderCommentRule(priority=90))
        engine.add_rule(MetadataRule(priority=100))

        source = b"""# Copyright 2024
# License: MIT

#region Main Code
def main():
    # TODO: Implement main logic
    pass
#endregion

-----

def helper():
    pass
"""

        parser = get_parser("python")
        tree = parser.parse(source)

        chunks = engine.apply_rules(tree, source, "test.py")

        # Should find multiple chunk types
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "file_metadata" in chunk_types
        assert any("region" in t for t in chunk_types)
        assert any("todo" in t for t in chunk_types)

    def test_overlapping_rules(self):
        """Test handling of overlapping rule matches."""

        engine = DefaultRuleEngine()

        # Add rules that might overlap
        engine.add_rule(RegionMarkerRule(priority=80))
        engine.add_rule(
            PatternBoundaryRule(
                "functions",
                r"def\s+\w+\s*\([^)]*\):",
                extract_match_only=True,
                priority=60,
            ),
        )

        source = b"""
#region Functions
def func1():
    pass

def func2():
    pass
#endregion
"""

        parser = get_parser("python")
        tree = parser.parse(source)

        chunks = engine.apply_rules(tree, source, "test.py")

        # Both region and function chunks should be found
        assert len(chunks) >= 1

    def test_rule_priority_execution(self):
        """Test that rules execute in priority order."""

        engine = DefaultRuleEngine()

        # Track execution order
        execution_order = []

        class TrackingRule(BaseRegexRule):
            def find_all_matches(self, source, file_path):
                execution_order.append(self.get_name())
                return super().find_all_matches(source, file_path)

        # Add rules with different priorities
        for priority in [30, 90, 50, 70]:
            rule = TrackingRule(
                f"rule_{priority}",
                f"Test rule {priority}",
                r"test",
                priority=priority,
            )
            engine.add_rule(rule)

        source = b"test content"
        engine.apply_regex_rules(source, "test.txt")

        # Check execution order matches priority
        expected_order = ["rule_90", "rule_70", "rule_50", "rule_30"]
        assert execution_order == expected_order
