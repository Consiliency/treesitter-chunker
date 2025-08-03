"""Comprehensive tests for MATLAB language support."""
from chunker import chunk_file, get_parser
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.matlab import MATLABPlugin


class TestMATLABBasicChunking:
    """Test basic MATLAB chunking functionality."""

    @staticmethod
    def test_simple_function(tmp_path):
        """Test basic MATLAB function."""
        src = tmp_path / "simple.m"
        src.write_text(
            """function result = add_numbers(a, b)
    % Add two numbers
    result = a + b;
end
""",
            )
        chunks = chunk_file(src, "matlab")
        assert len(chunks) >= 1
        func_chunks = [c for c in chunks if "function" in c.node_type]
        assert len(func_chunks) == 1
        assert "add_numbers" in func_chunks[0].content
        assert "result = a + b" in func_chunks[0].content

    @staticmethod
    def test_function_with_multiple_outputs(tmp_path):
        """Test function with multiple output arguments."""
        src = tmp_path / "multi_output.m"
        src.write_text(
            """function [x, y, z] = compute_coordinates(r, theta, phi)
    % Convert spherical to Cartesian coordinates
    x = r * sin(phi) * cos(theta);
    y = r * sin(phi) * sin(theta);
    z = r * cos(phi);
end
""",
            )
        chunks = chunk_file(src, "matlab")
        func_chunks = [c for c in chunks if "function" in c.node_type]
        assert len(func_chunks) == 1
        assert "[x, y, z]" in func_chunks[0].content
        assert "compute_coordinates" in func_chunks[0].content

    @staticmethod
    def test_matlab_script(tmp_path):
        """Test MATLAB script (not a function file)."""
        src = tmp_path / "script.m"
        src.write_text(
            """% Data analysis script
data = load('measurements.mat');
x = data(:, 1);
y = data(:, 2);

% Plot the data
figure;
plot(x, y, 'ro');
xlabel('Time (s)');
ylabel('Amplitude');
title('Measurement Results');

% Calculate statistics
mean_val = mean(y);
std_val = std(y);
fprintf('Mean: %.2f, Std: %.2f\\n', mean_val, std_val);
""",
            )
        chunks = chunk_file(src, "matlab")
        assert len(chunks) >= 1
        assert any("Data analysis script" in c.content for c in chunks)

    @staticmethod
    def test_matlab_classdef(tmp_path):
        """Test MATLAB class definition."""
        src = tmp_path / "MyClass.m"
        src.write_text(
            """classdef MyClass < handle
    % MyClass - Example MATLAB class

    properties
        Name
        Value
    end

    properties (Access = private)
        InternalData
    end

    methods
        function obj = MyClass(name, value)
            % Constructor
            obj.Name = name;
            obj.Value = value;
        end

        function display(obj)
            % Display object information
            fprintf('Name: %s, Value: %d\\n', obj.Name, obj.Value);
        end
    end

    methods (Static)
        function result = staticMethod(x)
            result = x * 2;
        end
    end
end
""",
            )
        chunks = chunk_file(src, "matlab")
        chunk_types = {chunk.node_type for chunk in chunks}
        assert any("classdef" in t or "class_definition" in t for t in
            chunk_types)
        assert any("properties" in t for t in chunk_types)
        assert any("methods" in t for t in chunk_types)
        method_chunks = [c for c in chunks if "method" in c.node_type or
            "function" in c.node_type]
        assert any("MyClass" in c.content and "Constructor" in c.content for
            c in method_chunks)
        assert any("display" in c.content for c in method_chunks)
        assert any("staticMethod" in c.content for c in method_chunks)

    @staticmethod
    def test_nested_functions(tmp_path):
        """Test MATLAB file with nested functions."""
        src = tmp_path / "nested.m"
        src.write_text(
            """function result = outer_function(x)
    % Outer function
    y = helper1(x);
    result = helper2(y);

    function a = helper1(b)
        % First nested function
        a = b * 2;
    end

    function c = helper2(d)
        % Second nested function
        c = d + 10;
    end
end

function local_result = local_function(input)
    % Local function (not nested)
    local_result = input^2;
end
""",
            )
        chunks = chunk_file(src, "matlab")
        func_chunks = [c for c in chunks if "function" in c.node_type]
        assert len(func_chunks) >= 4
        assert any("outer_function" in c.content for c in func_chunks)
        assert any("helper1" in c.content for c in func_chunks)
        assert any("helper2" in c.content for c in func_chunks)
        assert any("local_function" in c.content for c in func_chunks)


class TestMATLABContractCompliance:
    """Test ExtendedLanguagePluginContract compliance."""

    @staticmethod
    def test_implements_contract():
        """Verify MATLABPlugin implements ExtendedLanguagePluginContract."""
        assert issubclass(MATLABPlugin, ExtendedLanguagePluginContract)

    @classmethod
    def test_get_semantic_chunks(cls, tmp_path):
        """Test get_semantic_chunks method."""
        plugin = MATLABPlugin()
        source = b"function y = square(x)\n    y = x^2;\nend\n"
        parser = get_parser("matlab")
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
        plugin = MATLABPlugin()
        node_types = plugin.get_chunk_node_types()
        assert isinstance(node_types, set)
        assert len(node_types) > 0
        assert "function_definition" in node_types or "function_declaration" in node_types
        assert any("classdef" in t or "class_definition" in t for t in
            node_types)
        assert any("methods" in t for t in node_types)

    @staticmethod
    def test_should_chunk_node():
        """Test should_chunk_node method."""
        plugin = MATLABPlugin()

        class MockNode:

            def __init__(self, node_type):
                self.type = node_type
        assert plugin.should_chunk_node(MockNode("function_definition"))
        assert plugin.should_chunk_node(MockNode("classdef"))
        assert plugin.should_chunk_node(MockNode("methods"))
        assert plugin.should_chunk_node(MockNode("properties"))
        assert plugin.should_chunk_node(MockNode("comment"))
        assert not plugin.should_chunk_node(MockNode("identifier"))
        assert not plugin.should_chunk_node(MockNode("number"))

    @staticmethod
    def test_get_node_context():
        """Test get_node_context method."""
        plugin = MATLABPlugin()

        class MockNode:

            def __init__(self, node_type):
                self.type = node_type
                self.children = []
        node = MockNode("function_definition")
        context = plugin.get_node_context(node, b"function y = test(x)")
        assert context is not None
        assert "function" in context
        node = MockNode("classdef")
        context = plugin.get_node_context(node, b"classdef MyClass")
        assert context is not None
        assert "classdef" in context


class TestMATLABEdgeCases:
    """Test edge cases in MATLAB parsing."""

    @staticmethod
    def test_empty_matlab_file(tmp_path):
        """Test empty MATLAB file."""
        src = tmp_path / "empty.m"
        src.write_text("")
        chunks = chunk_file(src, "matlab")
        assert len(chunks) == 0

    @staticmethod
    def test_matlab_with_only_comments(tmp_path):
        """Test MATLAB file with only comments."""
        src = tmp_path / "comments.m"
        src.write_text(
            """% This is a comment
% Another comment
%{
Multi-line
block comment
%}
""",
            )
        chunks = chunk_file(src, "matlab")
        comment_chunks = [c for c in chunks if "comment" in c.node_type]
        assert len(comment_chunks) >= 1

    @staticmethod
    def test_matlab_with_anonymous_functions(tmp_path):
        """Test MATLAB with anonymous functions."""
        src = tmp_path / "anonymous.m"
        src.write_text(
            """% Define anonymous functions
square = @(x) x.^2;
add = @(a, b) a + b;

% Use in higher-order function
result = arrayfun(square, 1:10);
combined = @(x, y) add(square(x), y);
""",
            )
        chunks = chunk_file(src, "matlab")
        assert len(chunks) >= 1

    @staticmethod
    def test_matlab_with_events_enumeration(tmp_path):
        """Test MATLAB class with events and enumeration."""
        src = tmp_path / "AdvancedClass.m"
        src.write_text(
            """classdef AdvancedClass < handle

    events
        DataChanged
        StateUpdated
    end

    enumeration
        Active
        Inactive
        Pending
    end

    properties
        State = AdvancedClass.Inactive
    end

    methods
        function notify_change(obj)
            notify(obj, 'DataChanged');
        end
    end
end
""",
            )
        chunks = chunk_file(src, "matlab")
        chunk_types = {chunk.node_type for chunk in chunks}
        assert any("events" in t for t in chunk_types)
        assert any("enumeration" in t for t in chunk_types)

    @staticmethod
    def test_matlab_with_complex_inheritance(tmp_path):
        """Test MATLAB class with complex inheritance."""
        src = tmp_path / "DerivedClass.m"
        src.write_text(
            """classdef DerivedClass < BaseClass & matlab.mixin.Copyable
    % Class with multiple inheritance

    properties (SetAccess = protected, GetAccess = public)
        ProtectedProp
    end

    properties (Constant)
        VERSION = '1.0.0'
    end

    methods (Access = protected)
        function protectedMethod(obj)
            % Protected method implementation
            obj.ProtectedProp = 42;
        end
    end

    methods (Sealed)
        function sealedMethod(obj)
            % Cannot be overridden
            disp('Sealed method');
        end
    end
end
""",
            )
        chunks = chunk_file(src, "matlab")
        assert any("DerivedClass" in c.content and "BaseClass" in c.content for
            c in chunks)
        assert any("SetAccess = protected" in c.content for c in chunks)
        assert any("Constant" in c.content for c in chunks)
        assert any("Sealed" in c.content for c in chunks)
