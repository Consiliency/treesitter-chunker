"""Tests for Zig language plugin."""

import pytest

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.plugin_base import LanguagePlugin
from chunker.languages.zig import ZigPlugin
from chunker.parser import get_parser


class TestZigPlugin:
    """Test suite for Zig language plugin."""

    @pytest.fixture
    def plugin(self):
        """Create a Zig plugin instance."""
        return ZigPlugin()

    @pytest.fixture
    def parser(self):
        """Get a Zig parser."""
        return get_parser("zig")

    def test_plugin_properties(self, plugin):
        """Test basic plugin properties."""
        assert plugin.language_name == "zig"
        assert ".zig" in plugin.supported_extensions
        assert "function_declaration" in plugin.default_chunk_types
        assert "struct_declaration" in plugin.default_chunk_types
        assert "enum_declaration" in plugin.default_chunk_types
        assert "test_declaration" in plugin.default_chunk_types

    def test_implements_contracts(self, plugin):
        """Test that plugin implements required contracts."""
        assert isinstance(plugin, LanguagePlugin)
        assert isinstance(plugin, ExtendedLanguagePluginContract)

    def test_basic_function_chunking(self, plugin, parser):
        """Test chunking of basic Zig functions."""
        code = """
pub fn main() void {
    std.debug.print("Hello, World!\\n", .{});
}

fn add(a: i32, b: i32) i32 {
    return a + b;
}
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        assert len(chunks) == 2
        assert chunks[0]["type"] == "function"
        assert chunks[0]["name"] == "main"
        assert chunks[0]["visibility"] == "public"
        assert chunks[1]["type"] == "function"
        assert chunks[1]["name"] == "add"
        assert chunks[1]["visibility"] == "private"

    def test_struct_chunking(self, plugin, parser):
        """Test chunking of Zig structs."""
        code = """
const Point = struct {
    x: f32,
    y: f32,

    pub fn distance(self: Point, other: Point) f32 {
        const dx = self.x - other.x;
        const dy = self.y - other.y;
        return @sqrt(dx * dx + dy * dy);
    }
};
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        # Should find struct and nested function
        struct_chunks = [c for c in chunks if c["type"] == "struct"]
        func_chunks = [c for c in chunks if c["type"] == "function"]

        assert len(struct_chunks) == 1
        assert struct_chunks[0]["name"] == "Point"

        assert len(func_chunks) == 1
        assert func_chunks[0]["name"] == "distance"
        assert func_chunks[0]["container"] == "Point"

    def test_enum_chunking(self, plugin, parser):
        """Test chunking of Zig enums."""
        code = """
const Color = enum {
    red,
    green,
    blue,

    pub fn toRgb(self: Color) [3]u8 {
        return switch (self) {
            .red => [3]u8{ 255, 0, 0 },
            .green => [3]u8{ 0, 255, 0 },
            .blue => [3]u8{ 0, 0, 255 },
        };
    }
};
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        enum_chunks = [c for c in chunks if c["type"] == "enum"]
        assert len(enum_chunks) == 1
        assert enum_chunks[0]["name"] == "Color"

    def test_test_declaration_chunking(self, plugin, parser):
        """Test chunking of Zig test declarations."""
        code = """
test "basic arithmetic" {
    try std.testing.expectEqual(@as(i32, 1 + 1), 2);
}

test "string operations" {
    const hello = "Hello";
    try std.testing.expectEqualStrings(hello, "Hello");
}
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        assert len(chunks) == 2
        assert all(c["type"] == "test" for c in chunks)
        assert chunks[0]["name"] == "basic arithmetic"
        assert chunks[1]["name"] == "string operations"

    def test_union_chunking(self, plugin, parser):
        """Test chunking of Zig unions."""
        code = """
const Value = union(enum) {
    int: i32,
    float: f32,
    string: []const u8,

    pub fn isNumeric(self: Value) bool {
        return switch (self) {
            .int, .float => true,
            .string => false,
        };
    }
};
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        union_chunks = [c for c in chunks if c["type"] == "union"]
        assert len(union_chunks) == 1
        assert union_chunks[0]["name"] == "Value"

    def test_error_set_chunking(self, plugin, parser):
        """Test chunking of Zig error sets."""
        code = """
const FileError = error{
    NotFound,
    PermissionDenied,
    Corrupted,
};
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        error_chunks = [c for c in chunks if c["type"] == "error_set"]
        assert len(error_chunks) == 1
        assert error_chunks[0]["name"] == "FileError"

    def test_comptime_chunking(self, plugin, parser):
        """Test chunking of comptime declarations."""
        code = """
comptime {
    const pi = 3.14159;
    const tau = pi * 2;
}
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        comptime_chunks = [c for c in chunks if c["type"] == "comptime"]
        assert len(comptime_chunks) == 1

    def test_should_chunk_node(self, plugin, parser):
        """Test should_chunk_node method."""
        code = """
pub fn main() void {}
const Point = struct { x: f32, y: f32 };
test "example" {}
"""
        tree = parser.parse(code.encode())

        def find_nodes_by_type(node, node_type):
            """Helper to find nodes by type."""
            results = []
            if node.type == node_type:
                results.append(node)
            for child in node.children:
                results.extend(find_nodes_by_type(child, node_type))
            return results

        # Find different node types
        root = tree.root_node
        func_nodes = find_nodes_by_type(root, "function_declaration")
        struct_nodes = find_nodes_by_type(root, "struct_declaration")
        test_nodes = find_nodes_by_type(root, "test_declaration")

        # All should be chunkable
        assert all(plugin.should_chunk_node(n) for n in func_nodes)
        assert all(plugin.should_chunk_node(n) for n in struct_nodes)
        assert all(plugin.should_chunk_node(n) for n in test_nodes)

    def test_get_node_context(self, plugin, parser):
        """Test context extraction for nodes."""
        code = """
pub fn publicFunc() void {}
fn privateFunc() void {}
const MyStruct = struct {};
test "my test" {}
"""
        tree = parser.parse(code.encode())
        source = code.encode()

        def find_first_node_by_type(node, node_type):
            """Helper to find first node by type."""
            if node.type == node_type:
                return node
            for child in node.children:
                result = find_first_node_by_type(child, node_type)
                if result:
                    return result
            return None

        # Test function contexts
        func_node = find_first_node_by_type(tree.root_node, "function_declaration")
        if func_node:
            context = plugin.get_node_context(func_node, source)
            assert context is not None
            # Should indicate public visibility
            assert "pub" in context or "public" in context.lower()

    def test_complex_zig_file(self, plugin, parser):
        """Test with a more complex Zig file structure."""
        code = """
const std = @import("std");

pub const Config = struct {
    name: []const u8,
    value: i32,

    pub fn init(name: []const u8, value: i32) Config {
        return Config{ .name = name, .value = value };
    }
};

const Operation = enum {
    add,
    subtract,
    multiply,
    divide,
};

pub fn calculate(op: Operation, a: f32, b: f32) !f32 {
    return switch (op) {
        .add => a + b,
        .subtract => a - b,
        .multiply => a * b,
        .divide => if (b != 0) a / b else error.DivisionByZero,
    };
}

test "calculate operations" {
    try std.testing.expectEqual(calculate(.add, 2, 3), 5);
}
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        # Should find multiple chunk types
        struct_chunks = [c for c in chunks if c["type"] == "struct"]
        enum_chunks = [c for c in chunks if c["type"] == "enum"]
        func_chunks = [c for c in chunks if c["type"] == "function"]
        test_chunks = [c for c in chunks if c["type"] == "test"]

        assert len(struct_chunks) >= 1
        assert len(enum_chunks) >= 1
        assert len(func_chunks) >= 2  # init and calculate
        assert len(test_chunks) >= 1

        # Verify specific chunks
        assert any(c["name"] == "Config" for c in struct_chunks)
        assert any(c["name"] == "Operation" for c in enum_chunks)
        assert any(c["name"] == "calculate" for c in func_chunks)

    def test_inline_assembly_detection(self, plugin, parser):
        """Test detection of inline assembly blocks."""
        code = """
pub fn syscall(number: usize, arg1: usize) usize {
    return asm volatile ("syscall"
        : [ret] "={rax}" (-> usize)
        : [number] "{rax}" (number),
          [arg1] "{rdi}" (arg1)
        : "rcx", "r11", "memory"
    );
}
"""
        tree = parser.parse(code.encode())

        # Check if asm_expression nodes are detected as chunkable
        def find_asm_nodes(node):
            results = []
            if node.type == "asm_expression":
                results.append(node)
            for child in node.children:
                results.extend(find_asm_nodes(child))
            return results

        asm_nodes = find_asm_nodes(tree.root_node)
        if asm_nodes:
            assert all(plugin.should_chunk_node(n) for n in asm_nodes)
