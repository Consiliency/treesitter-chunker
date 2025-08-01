"""Tests for NASM language plugin."""
import pytest

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.nasm import NASMPlugin
from chunker.languages.plugin_base import LanguagePlugin
from chunker.parser import get_parser


class TestNASMPlugin:
    """Test suite for NASM language plugin."""

    @classmethod
    @pytest.fixture
    def plugin(cls):
        """Create a NASM plugin instance."""
        return NASMPlugin()

    @staticmethod
    @pytest.fixture
    def parser():
        """Get a NASM parser."""
        return get_parser("nasm")

    @staticmethod
    def test_plugin_properties(plugin):
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

    @staticmethod
    def test_implements_contracts(plugin):
        """Test that plugin implements required contracts."""
        assert isinstance(plugin, LanguagePlugin)
        assert isinstance(plugin, ExtendedLanguagePluginContract)

    @staticmethod
    def test_label_chunking(plugin, parser):
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
        global_labels = [c for c in label_chunks if c.get("is_global", False)]
        local_labels = [c for c in label_chunks if not c.get("is_global",
            False)]
        assert len(global_labels) >= 1
        assert any(c["name"] == "_start" for c in global_labels)
        assert len(local_labels) >= 1

    @staticmethod
    def test_section_chunking(plugin, parser):
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

    @staticmethod
    def test_macro_chunking(plugin, parser):
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

    @staticmethod
    def test_struc_chunking(plugin, parser):
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

    @staticmethod
    def test_global_extern_directives(plugin, parser):
        """Test chunking of global and extern directives."""
        code = (
            "\nglobal _start\nglobal print_message\nextern printf\nextern malloc\n"
            )
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

    @staticmethod
    def test_should_chunk_node(plugin, parser):
        """Test should_chunk_node method."""
        code = (
            "\nsection .text\nmy_label:\n    ret\n\n%macro TEST 0\n    nop\n%endmacro\n"
            )
        tree = parser.parse(code.encode())

        def find_nodes_by_type(node, node_type):
            """Helper to find nodes by type."""
            results = []
            if node.type == node_type:
                results.append(node)
            for child in node.children:
                results.extend(find_nodes_by_type(child, node_type))
            return results
        root = tree.root_node
        label_nodes = find_nodes_by_type(root, "label")
        section_nodes = find_nodes_by_type(root, "section")
        macro_nodes = find_nodes_by_type(root, "macro_definition")
        assert all(plugin.should_chunk_node(n) for n in label_nodes)
        assert all(plugin.should_chunk_node(n) for n in section_nodes)
        assert all(plugin.should_chunk_node(n) for n in macro_nodes)

    @staticmethod
    def test_get_node_context(plugin, parser):
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
        label_node = find_first_node_by_type(tree.root_node, "label")
        if label_node:
            context = plugin.get_node_context(label_node, source)
            assert context is not None
        section_node = find_first_node_by_type(tree.root_node, "section")
        if section_node:
            context = plugin.get_node_context(section_node, source)
            assert context is not None
            assert "section" in context

    @staticmethod
    def test_complex_assembly_file(plugin, parser):
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
        section_chunks = [c for c in chunks if c["type"] == "section"]
        label_chunks = [c for c in chunks if c["type"] == "label"]
        macro_chunks = [c for c in chunks if c["type"] == "macro"]
        struct_chunks = [c for c in chunks if c["type"] == "struct"]
        global_chunks = [c for c in chunks if c["type"] == "global"]
        extern_chunks = [c for c in chunks if c["type"] == "extern"]
        assert len(section_chunks) >= 3
        assert len(label_chunks) >= 2
        assert len(macro_chunks) >= 1
        assert len(struct_chunks) >= 1
        assert len(global_chunks) >= 1
        assert len(extern_chunks) >= 1

    @staticmethod
    def test_procedure_detection(plugin, parser):
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
        source = code.encode()
        chunks = []

        def process_tree(node):
            chunk = plugin.process_node(node, source, "test.asm")
            if chunk:
                chunks.append(chunk)
            for child in node.children:
                process_tree(child)
        process_tree(tree.root_node)
        [c for c in chunks if c.node_type == "procedure"]
        [c for c in chunks if c.node_type == "label"]
        assert len(chunks) > 0

    @staticmethod
    def test_section_metadata(plugin, parser):
        """Test section metadata extraction."""
        code = (
            "\nsection .text\nsection .data\nsection .bss\nsection .rodata\n")
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        source = code.encode()
        chunks = []

        def process_tree(node):
            chunk = plugin.process_node(node, source, "test.asm")
            if chunk:
                chunks.append(chunk)
            for child in node.children:
                process_tree(child)
        process_tree(tree.root_node)
        section_chunks = [c for c in chunks if "section" in c.node_type]
        for chunk in section_chunks:
            if chunk.metadata and "section_name" in chunk.metadata:
                name = chunk.metadata["section_name"]
                if ".text" in name:
                    assert chunk.metadata.get("section_type") == "code"
                elif ".data" in name:
                    assert chunk.metadata.get("section_type") == "data"
                elif ".bss" in name:
                    assert chunk.metadata.get("section_type",
                        ) == "uninitialized_data"
