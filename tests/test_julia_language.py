"""Comprehensive tests for Julia language support."""
from chunker import chunk_file, get_parser
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.julia import JuliaPlugin


class TestJuliaBasicChunking:
    """Test basic Julia chunking functionality."""

    @staticmethod
    def test_simple_function(tmp_path):
        """Test basic Julia function definition."""
        src = tmp_path / "simple.jl"
        src.write_text(
            """# Simple function
function add(a, b)
    return a + b
end

# One-liner function
multiply(x, y) = x * y

# Function with type annotations
function typed_divide(x::Float64, y::Float64)::Float64
    return x / y
end
""",
            )
        chunks = chunk_file(src, "julia")
        assert len(chunks) >= 3
        func_chunks = [c for c in chunks if "function" in c.node_type]
        assert len(func_chunks) == 3
        assert any("add" in c.content for c in func_chunks)
        assert any("multiply" in c.content for c in func_chunks)
        assert any("typed_divide" in c.content for c in func_chunks)

    @staticmethod
    def test_struct_definitions(tmp_path):
        """Test Julia struct definitions."""
        src = tmp_path / "structs.jl"
        src.write_text(
            """# Immutable struct
struct Point
    x::Float64
    y::Float64
end

# Mutable struct
mutable struct MutablePoint
    x::Float64
    y::Float64
end

# Parametric struct
struct Point3D{T<:Real}
    x::T
    y::T
    z::T
end

# Struct with inner constructor
struct Circle
    radius::Float64

    function Circle(r)
        if r < 0
            error("Radius must be non-negative")
        end
        new(r)
    end
end
""",
            )
        chunks = chunk_file(src, "julia")
        struct_chunks = [c for c in chunks if "struct" in c.node_type]
        assert len(struct_chunks) >= 4
        assert any("Point" in c.content and "mutable" not in c.content for
            c in struct_chunks)
        assert any("MutablePoint" in c.content for c in struct_chunks)
        assert any("Point3D{T<:Real}" in c.content for c in struct_chunks)
        assert any("Circle" in c.content and "inner constructor" in c.
            content for c in struct_chunks)

    @staticmethod
    def test_module_definition(tmp_path):
        """Test Julia module definitions."""
        src = tmp_path / "mymodule.jl"
        src.write_text(
            """module MyModule

export public_function, MyType

# Public function
function public_function(x)
    return x * 2
end

# Private function
function _private_function(x)
    return x + 1
end

# Type definition
struct MyType
    value::Int
end

# Nested module
module SubModule
    function sub_function()
        println("From submodule")
    end
end

end # MyModule
""",
            )
        chunks = chunk_file(src, "julia")
        module_chunks = [c for c in chunks if c.node_type ==
            "module_definition"]
        assert len(module_chunks) >= 2
        assert any("MyModule" in c.content for c in module_chunks)
        assert any("SubModule" in c.content for c in module_chunks)
        func_chunks = [c for c in chunks if "function" in c.node_type]
        assert any("public_function" in c.content for c in func_chunks)
        assert any("_private_function" in c.content for c in func_chunks)

    @staticmethod
    def test_macro_definitions(tmp_path):
        """Test Julia macro definitions."""
        src = tmp_path / "macros.jl"
        src.write_text(
            """# Simple macro
macro sayhello(name)
    return :(println("Hello, ", $name))
end

# Macro with multiple arguments
macro assert_positive(x, msg)
    return quote
        if $x <= 0
            error($msg)
        end
    end
end

# Using macros
@sayhello("World")
@assert_positive(5, "Value must be positive")
""",
            )
        chunks = chunk_file(src, "julia")
        macro_chunks = [c for c in chunks if c.node_type == "macro_definition"]
        assert len(macro_chunks) >= 2
        assert any("sayhello" in c.content for c in macro_chunks)
        assert any("assert_positive" in c.content for c in macro_chunks)

    @staticmethod
    def test_abstract_and_primitive_types(tmp_path):
        """Test Julia abstract and primitive type definitions."""
        src = tmp_path / "types.jl"
        src.write_text(
            """# Abstract type hierarchy
abstract type Animal end
abstract type Mammal <: Animal end
abstract type Bird <: Animal end

# Concrete types
struct Dog <: Mammal
    name::String
    age::Int
end

struct Eagle <: Bird
    wingspan::Float64
end

# Primitive type
primitive type MyInt8 <: Integer 8 end

# Type with type parameters
abstract type AbstractArray{T,N} end
""",
            )
        chunks = chunk_file(src, "julia")
        abstract_chunks = [c for c in chunks if c.node_type ==
            "abstract_type_definition"]
        assert len(abstract_chunks) >= 4
        assert any("Animal" in c.content for c in abstract_chunks)
        assert any("Mammal <: Animal" in c.content for c in abstract_chunks)
        primitive_chunks = [c for c in chunks if c.node_type ==
            "primitive_type_definition"]
        assert len(primitive_chunks) >= 1
        assert any("MyInt8" in c.content for c in primitive_chunks)


class TestJuliaContractCompliance:
    """Test ExtendedLanguagePluginContract compliance."""

    @staticmethod
    def test_implements_contract():
        """Verify JuliaPlugin implements ExtendedLanguagePluginContract."""
        assert issubclass(JuliaPlugin, ExtendedLanguagePluginContract)

    @classmethod
    def test_get_semantic_chunks(cls, tmp_path):
        """Test get_semantic_chunks method."""
        plugin = JuliaPlugin()
        source = b"function square(x)\n    x^2\nend\n"
        parser = get_parser("julia")
        plugin.set_parser(parser)
        tree = parser.parse(source)
        chunks = plugin.get_semantic_chunks(tree.root_node, source)
        assert len(chunks) >= 1
        assert all("type" in chunk for chunk in chunks)
        assert all("start_line" in chunk for chunk in chunks)
        assert all("end_line" in chunk for chunk in chunks)
        assert all("content" in chunk for chunk in chunks)

    @classmethod
    def test_get_chunk_node_types(cls):
        """Test get_chunk_node_types method."""
        plugin = JuliaPlugin()
        node_types = plugin.get_chunk_node_types()
        assert isinstance(node_types, set)
        assert len(node_types) > 0
        assert "function_definition" in node_types
        assert "struct_definition" in node_types
        assert "module_definition" in node_types

    @staticmethod
    def test_should_chunk_node():
        """Test should_chunk_node method."""
        plugin = JuliaPlugin()

        class MockNode:

            def __init__(self, node_type):
                self.type = node_type
        assert plugin.should_chunk_node(MockNode("function_definition"))
        assert plugin.should_chunk_node(MockNode("struct_definition"))
        assert plugin.should_chunk_node(MockNode("module_definition"))
        assert plugin.should_chunk_node(MockNode("macro_definition"))
        assert plugin.should_chunk_node(MockNode("const_statement"))
        assert plugin.should_chunk_node(MockNode("comment"))
        assert not plugin.should_chunk_node(MockNode("identifier"))
        assert not plugin.should_chunk_node(MockNode("number"))
        assert not plugin.should_chunk_node(MockNode("assignment"))

    @staticmethod
    def test_get_node_context():
        """Test get_node_context method."""
        plugin = JuliaPlugin()

        class MockNode:

            def __init__(self, node_type):
                self.type = node_type
                self.children = []
        node = MockNode("function_definition")
        context = plugin.get_node_context(node, b"function test(x)")
        assert context is not None
        assert "function" in context
        node = MockNode("struct_definition")
        context = plugin.get_node_context(node, b"struct Point")
        assert context is not None
        assert "struct" in context


class TestJuliaEdgeCases:
    """Test edge cases in Julia parsing."""

    @staticmethod
    def test_empty_julia_file(tmp_path):
        """Test empty Julia file."""
        src = tmp_path / "empty.jl"
        src.write_text("")
        chunks = chunk_file(src, "julia")
        assert len(chunks) == 0

    @staticmethod
    def test_julia_with_only_comments(tmp_path):
        """Test Julia file with only comments."""
        src = tmp_path / "comments.jl"
        src.write_text(
            """# Single line comment
# Another comment
#= Multi-line
   block comment
   spanning multiple lines =#
""",
            )
        chunks = chunk_file(src, "julia")
        comment_chunks = [c for c in chunks if "comment" in c.node_type]
        assert len(comment_chunks) >= 1

    @staticmethod
    def test_julia_with_unicode_identifiers(tmp_path):
        """Test Julia with Unicode identifiers."""
        src = tmp_path / "unicode.jl"
        src.write_text(
            """# Julia supports Unicode identifiers
function Σ(x::Vector{T}) where T<:Number
    sum(x)
end

# Greek letters in math
α = 0.5
β = 2.0
γ = α * β

# Mathematical operators
∑(arr) = sum(arr)
∏(arr) = prod(arr)

# Emoji identifiers (yes, Julia allows this!)
function 🚀(speed)
    println("Launching at speed $speed!")
end
""",
            )
        chunks = chunk_file(src, "julia")
        func_chunks = [c for c in chunks if "function" in c.node_type]
        assert any("Σ" in c.content for c in func_chunks)
        assert any("🚀" in c.content for c in func_chunks)

    @staticmethod
    def test_julia_with_metaprogramming(tmp_path):
        """Test Julia with metaprogramming constructs."""
        src = tmp_path / "metaprog.jl"
        src.write_text(
            """# Expression manipulation
function make_function(name::Symbol, body)
    return quote
        function $name(x)
            $body
        end
    end
end

# Generated functions
@generated function mysum(T::Tuple)
    n = length(T.parameters)
    ex = :(T[1])
    for i in 2:n
        ex = :($ex + T[$i])
    end
    return ex
end

# Eval at compile time
for op in [:+, :-, :*, :/]
    @eval begin
        function apply_op(a, b, ::Val{$(QuoteNode(op))})
            return $op(a, b)
        end
    end
end
""",
            )
        chunks = chunk_file(src, "julia")
        assert any("make_function" in c.content for c in chunks)
        assert any("@generated" in c.content for c in chunks)

    @staticmethod
    def test_julia_with_multiple_dispatch(tmp_path):
        """Test Julia with multiple dispatch method definitions."""
        src = tmp_path / "dispatch.jl"
        src.write_text(
            """# Base generic function
function process(x)
    println("Generic process for type $(typeof(x))")
end

# Specialized methods
function process(x::Int)
    println("Processing integer: $x")
    return x * 2
end

function process(x::String)
    println("Processing string: $x")
    return uppercase(x)
end

function process(x::Vector{T}) where T<:Number
    println("Processing numeric vector")
    return sum(x)
end

# Method with multiple arguments
function combine(x::Int, y::Int)
    return x + y
end

function combine(x::String, y::String)
    return x * y
end

function combine(x::Vector, y::Vector)
    return vcat(x, y)
end
""",
            )
        chunks = chunk_file(src, "julia")
        func_chunks = [c for c in chunks if "function" in c.node_type]
        process_chunks = [c for c in func_chunks if "process" in c.content]
        assert len(process_chunks) >= 4
        combine_chunks = [c for c in func_chunks if "combine" in c.content]
        assert len(combine_chunks) >= 3
