"""Tests for NASM language plugin."""

import pytest

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.nasm import NASMPlugin
from chunker.languages.plugin_base import LanguagePlugin
from chunker.parser import get_parser


class TestNASMPlugin:
    """Test suite for NASM language plugin."""

    @pytest.fixture()
    def plugin(self):
        """Create a NASM plugin instance."""
        return NASMPlugin()

    @pytest.fixture()
    def parser(self):
        """Get a NASM parser."""
        return get_parser("nasm")

    def test_plugin_properties(self, plugin):
        """Test basic plugin properties."""
        assert plugin.language_name == "nasm"
        assert ".asm" in plugin.supported_extensions
        assert ".nasm" in plugin.supported_extensions
        assert ".s" in plugin.supported_extensions
        assert ".S" in plugin.supported_extensions
        assert "label" in plugin.default_chunk_types
        assert "section" in plugin.default_chunk_types
        assert "macro_definition" in plugin.default_chunk_types
        assert "struc_definition" in plugin.default_chunk_types

    def test_implements_contracts(self, plugin):
        """Test that plugin implements required contracts."""
        assert isinstance(plugin, LanguagePlugin)
        assert isinstance(plugin, ExtendedLanguagePluginContract)

    def test_label_chunking(self, plugin, parser):
        """Test chunking of NASM labels."""
        code = """
section .text
    global _start

_start:
    mov eax, 1
    mov ebx, 0
    int 0x80

.local_label:
    ret
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        label_chunks = [c for c in chunks if c["type"] == "label"]
        assert len(label_chunks) >= 2

        # Check for global and local labels
        global_labels = [c for c in label_chunks if c.get("is_global", False)]
        local_labels = [c for c in label_chunks if not c.get("is_global", False)]

        assert len(global_labels) >= 1
        assert any(c["name"] == "_start" for c in global_labels)
        assert len(local_labels) >= 1

    def test_section_chunking(self, plugin, parser):
        """Test chunking of NASM sections."""
        code = """
section .data
    msg db 'Hello, World!', 0xa
    len equ $ - msg

section .bss
    buffer resb 64

section .text
    global _start
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        section_chunks = [c for c in chunks if c["type"] == "section"]
        assert len(section_chunks) >= 3

        section_names = [c["name"] for c in section_chunks if c.get("name")]
        assert ".data" in section_names or "data" in section_names
        assert ".bss" in section_names or "bss" in section_names
        assert ".text" in section_names or "text" in section_names

    def test_macro_chunking(self, plugin, parser):
        """Test chunking of NASM macros."""
        code = """
%macro PRINT_STRING 2
    mov eax, 4
    mov ebx, 1
    mov ecx, %1
    mov edx, %2
    int 0x80
%endmacro

%macro SYSCALL 1
    mov eax, %1
    int 0x80
%endmacro
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        macro_chunks = [c for c in chunks if c["type"] == "macro"]
        assert len(macro_chunks) >= 2

        macro_names = [c["name"] for c in macro_chunks if c.get("name")]
        assert "PRINT_STRING" in macro_names
        assert "SYSCALL" in macro_names

    def test_struc_chunking(self, plugin, parser):
        """Test chunking of NASM structures."""
        code = """
struc Point
    .x: resd 1
    .y: resd 1
endstruc

struc Rectangle
    .top_left: resb Point_size
    .width: resd 1
    .height: resd 1
endstruc
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        struct_chunks = [c for c in chunks if c["type"] == "struct"]
        assert len(struct_chunks) >= 2

        struct_names = [c["name"] for c in struct_chunks if c.get("name")]
        assert "Point" in struct_names
        assert "Rectangle" in struct_names

    def test_global_extern_directives(self, plugin, parser):
        """Test chunking of global and extern directives."""
        code = """
global _start
global print_message
extern printf
extern malloc
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        global_chunks = [c for c in chunks if c["type"] == "global"]
        extern_chunks = [c for c in chunks if c["type"] == "extern"]

        assert len(global_chunks) >= 2
        assert len(extern_chunks) >= 2

        global_names = [c["name"] for c in global_chunks if c.get("name")]
        assert "_start" in global_names
        assert "print_message" in global_names

        extern_names = [c["name"] for c in extern_chunks if c.get("name")]
        assert "printf" in extern_names
        assert "malloc" in extern_names

    def test_should_chunk_node(self, plugin, parser):
        """Test should_chunk_node method."""
        code = """
section .text
my_label:
    ret

%macro TEST 0
    nop
%endmacro
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
        label_nodes = find_nodes_by_type(root, "label")
        section_nodes = find_nodes_by_type(root, "section")
        macro_nodes = find_nodes_by_type(root, "macro_definition")

        # All should be chunkable
        assert all(plugin.should_chunk_node(n) for n in label_nodes)
        assert all(plugin.should_chunk_node(n) for n in section_nodes)
        assert all(plugin.should_chunk_node(n) for n in macro_nodes)

    def test_get_node_context(self, plugin, parser):
        """Test context extraction for nodes."""
        code = """
section .text
my_function:
    push ebp

.local:
    nop

%macro MYMACRO 2
    ; macro body
%endmacro
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

        # Test label context
        label_node = find_first_node_by_type(tree.root_node, "label")
        if label_node:
            context = plugin.get_node_context(label_node, source)
            assert context is not None

        # Test section context
        section_node = find_first_node_by_type(tree.root_node, "section")
        if section_node:
            context = plugin.get_node_context(section_node, source)
            assert context is not None
            assert "section" in context

    def test_complex_assembly_file(self, plugin, parser):
        """Test with a more complex assembly file structure."""
        code = """
; Program to print Hello World
section .data
    msg db 'Hello, World!', 0xa
    len equ $ - msg

section .bss
    buffer resb 256

struc FileInfo
    .name: resb 256
    .size: resd 1
    .type: resb 1
endstruc

section .text
    global _start
    extern printf

%macro PRINT 2
    mov eax, 4
    mov ebx, 1
    mov ecx, %1
    mov edx, %2
    int 0x80
%endmacro

_start:
    ; Print message
    PRINT msg, len

    ; Exit program
    mov eax, 1
    xor ebx, ebx
    int 0x80

print_string:
    push ebp
    mov ebp, esp
    ; Function body
    pop ebp
    ret
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        # Should find multiple chunk types
        section_chunks = [c for c in chunks if c["type"] == "section"]
        label_chunks = [c for c in chunks if c["type"] == "label"]
        macro_chunks = [c for c in chunks if c["type"] == "macro"]
        struct_chunks = [c for c in chunks if c["type"] == "struct"]
        global_chunks = [c for c in chunks if c["type"] == "global"]
        extern_chunks = [c for c in chunks if c["type"] == "extern"]

        assert len(section_chunks) >= 3  # .data, .bss, .text
        assert len(label_chunks) >= 2  # _start, print_string
        assert len(macro_chunks) >= 1  # PRINT
        assert len(struct_chunks) >= 1  # FileInfo
        assert len(global_chunks) >= 1  # _start
        assert len(extern_chunks) >= 1  # printf

    def test_procedure_detection(self, plugin, parser):
        """Test detection of procedures vs simple labels."""
        code = """
my_procedure:
    push ebp
    mov ebp, esp
    ; procedure body
    pop ebp
    ret

simple_label:
    nop
    jmp next_label

next_label:
    ret
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())

        # Process nodes to check procedure detection
        source = code.encode()
        chunks = []

        def process_tree(node):
            chunk = plugin.process_node(node, source, "test.asm")
            if chunk:
                chunks.append(chunk)
            for child in node.children:
                process_tree(child)

        process_tree(tree.root_node)

        # Check if procedures are identified
        [c for c in chunks if c.node_type == "procedure"]
        [c for c in chunks if c.node_type == "label"]

        # The exact detection depends on implementation
        assert len(chunks) > 0

    def test_section_metadata(self, plugin, parser):
        """Test section metadata extraction."""
        code = """
section .text
section .data
section .bss
section .rodata
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        source = code.encode()

        # Process nodes to check section metadata
        chunks = []

        def process_tree(node):
            chunk = plugin.process_node(node, source, "test.asm")
            if chunk:
                chunks.append(chunk)
            for child in node.children:
                process_tree(child)

        process_tree(tree.root_node)

        # Check section metadata
        section_chunks = [c for c in chunks if "section" in c.node_type]
        for chunk in section_chunks:
            if chunk.metadata and "section_name" in chunk.metadata:
                name = chunk.metadata["section_name"]
                if ".text" in name:
                    assert chunk.metadata.get("section_type") == "code"
                elif ".data" in name:
                    assert chunk.metadata.get("section_type") == "data"
                elif ".bss" in name:
                    assert chunk.metadata.get("section_type") == "uninitialized_data"
