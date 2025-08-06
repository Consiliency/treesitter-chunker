"""Comprehensive tests for Elixir language support."""

from chunker import chunk_file
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.elixir import ElixirPlugin


class TestElixirBasicChunking:
    """Test basic Elixir chunking functionality."""

    @staticmethod
    def test_simple_functions(tmp_path):
        """Test basic function definitions."""
        src = tmp_path / "functions.ex"
        src.write_text(
            """defmodule Math do
  def factorial(0), do: 1
  def factorial(n) when n > 0 do
    n * factorial(n - 1)
  end

  defp fibonacci(0), do: 0
  defp fibonacci(1), do: 1
  defp fibonacci(n), do: fibonacci(n - 1) + fibonacci(n - 2)

  @doc ""\"
  Calculates the sum of a list.
  ""\"
  def sum(list), do: Enum.reduce(list, 0, &+/2)
end
""",
        )
        chunks = chunk_file(src, "elixir")
        assert len(chunks) >= 5
        module_chunks = [c for c in chunks if c.node_type == "module_definition"]
        assert len(module_chunks) >= 1
        assert any("Math" in c.content for c in module_chunks)
        function_chunks = [c for c in chunks if "function" in c.node_type]
        assert len(function_chunks) >= 4
        assert any("factorial" in c.content for c in function_chunks)
        assert any("fibonacci" in c.content for c in function_chunks)
        assert any("sum" in c.content for c in function_chunks)

    @staticmethod
    def test_macros_and_specs(tmp_path):
        """Test macro definitions and type specs."""
        src = tmp_path / "macros.ex"
        src.write_text(
            """defmodule MyMacros do
  defmacro unless(condition, do: clause) do
    quote do
      if !unquote(condition), do: unquote(clause)
    end
  end

  defmacrop debug(msg) do
    quote do
      IO.puts("[DEBUG] #{unquote(msg)}")
    end
  end

  @spec add(number, number) :: number
  def add(a, b), do: a + b

  @type color :: :red | :green | :blue

  @callback process(binary) :: {:ok, term} | {:error, String.t}
end
""",
        )
        chunks = chunk_file(src, "elixir")
        macro_chunks = [
            c
            for c in chunks
            if "macro" in c.content
            or any(kw in c.content for kw in ["defmacro", "defmacrop"])
        ]
        assert len(macro_chunks) >= 2
        assert any("unless" in c.content for c in chunks)
        assert any("debug" in c.content for c in chunks)
        spec_chunks = [
            c
            for c in chunks
            if c.node_type == "spec_definition" or "@spec" in c.content
        ]
        assert len(spec_chunks) >= 1

    @staticmethod
    def test_genserver_implementation(tmp_path):
        """Test GenServer implementation."""
        src = tmp_path / "counter.ex"
        src.write_text(
            """defmodule Counter do
  use GenServer

  # Client API
  def start_link(initial \\\\ 0) do
    GenServer.start_link(__MODULE__, initial, name: __MODULE__)
  end

  def increment do
    GenServer.call(__MODULE__, :increment)
  end

  def get_value do
    GenServer.call(__MODULE__, :get_value)
  end

  # Server callbacks
  @impl true
  def init(initial) do
    {:ok, initial}
  end

  @impl true
  def handle_call(:increment, _from, state) do
    {:reply, state + 1, state + 1}
  end

  @impl true
  def handle_call(:get_value, _from, state) do
    {:reply, state, state}
  end
end
""",
        )
        chunks = chunk_file(src, "elixir")
        assert any("Counter" in c.content and "module" in c.node_type for c in chunks)
        api_functions = ["start_link", "increment", "get_value"]
        for func_name in api_functions:
            assert any(
                func_name in c.content and "function" in c.node_type for c in chunks
            )
        callback_functions = ["init", "handle_call"]
        for func_name in callback_functions:
            assert any(func_name in c.content for c in chunks)

    @staticmethod
    def test_pattern_matching(tmp_path):
        """Test pattern matching constructs."""
        src = tmp_path / "patterns.ex"
        src.write_text(
            """defmodule Patterns do
  def process_message({:ok, data}), do: {:success, data}
  def process_message({:error, reason}), do: {:failure, reason}
  def process_message(_), do: {:unknown}

  def describe_list([]), do: "empty"
  def describe_list([_]), do: "single element"
  def describe_list([_, _]), do: "two elements"
  def describe_list(list), do: "#{length(list)} elements"

  def handle_user(%{name: name, age: age}) when age >= 18 do
    "Adult: #{name}"
  end
  def handle_user(%{name: name}), do: "Minor: #{name}"
end
""",
        )
        chunks = chunk_file(src, "elixir")
        function_chunks = [c for c in chunks if "function" in c.node_type]
        assert len(function_chunks) >= 9
        assert any("process_message" in c.content for c in function_chunks)
        assert any("describe_list" in c.content for c in function_chunks)
        assert any("handle_user" in c.content for c in function_chunks)


class TestElixirContractCompliance:
    """Test ExtendedLanguagePluginContract implementation."""

    @classmethod
    def test_implements_contract(cls):
        """Test that ElixirPlugin implements the contract."""
        plugin = ElixirPlugin()
        assert isinstance(plugin, ExtendedLanguagePluginContract)

    @staticmethod
    def test_get_semantic_chunks():
        """Test get_semantic_chunks method."""
        plugin = ElixirPlugin()

        class MockNode:

            def __init__(self, node_type, start=0, end=1):
                self.type = node_type
                self.start_byte = start
                self.end_byte = end
                self.start_point = 0, 0
                self.end_point = 0, end
                self.children = []

        root = MockNode("source")
        module_node = MockNode("module_definition", 0, 100)
        func_node = MockNode("call", 10, 50)
        id_node = MockNode("identifier", 10, 13)
        id_node.text = b"def"
        func_node.children.append(id_node)
        module_node.children.append(func_node)
        root.children.append(module_node)
        source = b"defmodule Test do\n  def hello, do: :world\nend"
        chunks = plugin.get_semantic_chunks(root, source)
        assert len(chunks) >= 1
        assert any(chunk["type"] == "module_definition" for chunk in chunks)

    @classmethod
    def test_get_chunk_node_types(cls):
        """Test get_chunk_node_types method."""
        plugin = ElixirPlugin()
        node_types = plugin.get_chunk_node_types()
        assert isinstance(node_types, set)
        assert "function_definition" in node_types
        assert "module_definition" in node_types
        assert "macro_definition" in node_types
        assert "call" in node_types

    @staticmethod
    def test_should_chunk_node():
        """Test should_chunk_node method."""
        plugin = ElixirPlugin()

        class MockNode:

            def __init__(self, node_type):
                self.type = node_type
                self.children = []
                self.text = b""

        assert plugin.should_chunk_node(MockNode("module_definition"))
        assert plugin.should_chunk_node(MockNode("macro_definition"))
        assert plugin.should_chunk_node(MockNode("spec_definition"))
        assert not plugin.should_chunk_node(MockNode("identifier"))
        assert not plugin.should_chunk_node(MockNode("comment"))

    @staticmethod
    def test_get_node_context():
        """Test get_node_context method."""
        plugin = ElixirPlugin()

        class MockNode:

            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        node = MockNode("module_definition")
        context = plugin.get_node_context(node, b"defmodule Test do")
        assert context is not None
        assert "module" in context


class TestElixirEdgeCases:
    """Test edge cases in Elixir parsing."""

    @staticmethod
    def test_empty_file(tmp_path):
        """Test empty Elixir file."""
        src = tmp_path / "empty.ex"
        src.write_text("")
        chunks = chunk_file(src, "elixir")
        assert len(chunks) == 0

    @staticmethod
    def test_comments_only(tmp_path):
        """Test file with only comments."""
        src = tmp_path / "comments.ex"
        src.write_text(
            """# Single line comment
# Another comment

# Module comment
# More details
""",
        )
        chunks = chunk_file(src, "elixir")
        assert len(chunks) == 0

    @staticmethod
    def test_anonymous_functions(tmp_path):
        """Test anonymous functions and captures."""
        src = tmp_path / "anon.ex"
        src.write_text(
            """defmodule Anon do
  def map_example do
    list = [1, 2, 3, 4, 5]

    # Anonymous function
    Enum.map(list, fn x -> x * 2 end)

    # Capture syntax
    Enum.map(list, &(&1 * 2))

    # Function capture
    Enum.reduce(list, 0, &+/2)
  end

  def complex_anon do
    process = fn
      {:ok, data} -> data
      {:error, _} -> nil
    end

    process.({:ok, "hello"})
  end
end
""",
        )
        chunks = chunk_file(src, "elixir")
        assert any("Anon" in c.content and "module" in c.node_type for c in chunks)
        assert any("map_example" in c.content for c in chunks)
        assert any("complex_anon" in c.content for c in chunks)

    @staticmethod
    def test_protocols_and_implementations(tmp_path):
        """Test protocol definitions and implementations."""
        src = tmp_path / "protocols.ex"
        src.write_text(
            """defprotocol Stringify do
  @doc "Converts data to string representation"
  def to_string(data)
end

defimpl Stringify, for: Integer do
  def to_string(num), do: Integer.to_string(num)
end

defimpl Stringify, for: List do
  def to_string(list) do
    list
    |> Enum.map(&Stringify.to_string/1)
    |> Enum.join(", ")
  end
end
""",
        )
        chunks = chunk_file(src, "elixir")
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "protocol_definition" in chunk_types
        assert "implementation_definition" in chunk_types
        assert any(
            "Stringify" in c.content and "protocol" in c.node_type for c in chunks
        )
        assert any(
            "Integer" in c.content and "implementation" in c.node_type for c in chunks
        )

    @staticmethod
    def test_pipe_operators(tmp_path):
        """Test pipe operator chains."""
        src = tmp_path / "pipes.ex"
        src.write_text(
            """defmodule Pipeline do
  def process_data(input) do
    input
    |> String.trim()
    |> String.downcase()
    |> String.split(" ")
    |> Enum.map(&String.capitalize/1)
    |> Enum.join(" ")
  end

  def complex_pipeline(data) do
    data
    |> validate()
    |> transform()
    |> case do
      {:ok, result} -> persist(result)
      {:error, reason} -> log_error(reason)
    end
  end

  defp validate(data), do: {:ok, data}
  defp transform(data), do: {:ok, data}
  defp persist(data), do: data
  defp log_error(reason), do: IO.puts("Error: #{reason}")
end
""",
        )
        chunks = chunk_file(src, "elixir")
        function_names = [
            "process_data",
            "complex_pipeline",
            "validate",
            "transform",
            "persist",
            "log_error",
        ]
        for name in function_names:
            assert any(name in c.content for c in chunks)

    @staticmethod
    def test_structs_and_behaviours(tmp_path):
        """Test struct definitions and behaviours."""
        src = tmp_path / "structs.ex"
        src.write_text(
            """defmodule User do
  @behaviour Access

  defstruct [:name, :email, age: 0, active: true]

  @impl Access
  def fetch(%User{} = user, key) do
    Map.fetch(user, key)
  end

  @impl Access
  def get_and_update(%User{} = user, key, fun) do
    Map.get_and_update(user, key, fun)
  end

  @impl Access
  def pop(%User{} = user, key) do
    Map.pop(user, key)
  end
end
""",
        )
        chunks = chunk_file(src, "elixir")
        assert any("defstruct" in c.content for c in chunks)
        assert any(
            "@behaviour" in c.content or "behaviour_definition" in c.node_type
            for c in chunks
        )
        impl_functions = ["fetch", "get_and_update", "pop"]
        for func in impl_functions:
            assert any(func in c.content for c in chunks)
