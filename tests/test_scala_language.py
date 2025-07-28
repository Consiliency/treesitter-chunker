"""Comprehensive tests for Scala language support."""

from chunker import chunk_file
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.scala import ScalaPlugin


class TestScalaBasicChunking:
    """Test basic Scala chunking functionality."""

    def test_simple_functions(self, tmp_path):
        """Test basic function definitions."""
        src = tmp_path / "Functions.scala"
        src.write_text(
            """package example

def factorial(n: Int): Int =
  if (n <= 1) 1 else n * factorial(n - 1)

def fibonacci(n: Int): Int = {
  @annotation.tailrec
  def fib(n: Int, a: Int, b: Int): Int = n match {
    case 0 => a
    case _ => fib(n - 1, b, a + b)
  }
  fib(n, 0, 1)
}

val double: Int => Int = _ * 2
""",
        )
        chunks = chunk_file(src, "scala")
        assert len(chunks) >= 3

        # Check for function definitions
        function_chunks = [
            c for c in chunks if "function" in c.node_type or "method" in c.node_type
        ]
        assert len(function_chunks) >= 2
        assert any("factorial" in c.content for c in chunks)
        assert any("fibonacci" in c.content for c in chunks)

        # Check for val definition (function value)
        val_chunks = [c for c in chunks if c.node_type == "val_definition"]
        assert len(val_chunks) >= 1
        assert any("double" in c.content for c in val_chunks)

    def test_classes_and_objects(self, tmp_path):
        """Test class and object definitions."""
        src = tmp_path / "Classes.scala"
        src.write_text(
            """package example

class Person(val name: String, var age: Int) {
  def greet(): String = s"Hello, I'm $name"

  private def secretMethod(): Unit = {
    println("This is private")
  }
}

object Person {
  def apply(name: String): Person = new Person(name, 0)

  val DefaultAge = 18
}

case class User(id: Long, email: String, active: Boolean = true)

trait Greeting {
  def sayHello(): String
}
""",
        )
        chunks = chunk_file(src, "scala")

        # Check for different definition types
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "class_definition" in chunk_types
        assert "object_definition" in chunk_types or "companion_object" in chunk_types
        assert "case_class_definition" in chunk_types
        assert "trait_definition" in chunk_types

        # Check for methods within class
        method_chunks = [c for c in chunks if "method" in c.node_type]
        assert any("greet" in c.content for c in method_chunks)

    def test_pattern_matching(self, tmp_path):
        """Test pattern matching constructs."""
        src = tmp_path / "PatternMatching.scala"
        src.write_text(
            """sealed trait Color
case object Red extends Color
case object Green extends Color
case object Blue extends Color

def describe(color: Color): String = color match {
  case Red => "The color is red"
  case Green => "The color is green"
  case Blue => "The color is blue"
}

def processOption(opt: Option[Int]): String = opt match {
  case Some(n) if n > 0 => s"Positive: $n"
  case Some(n) => s"Non-positive: $n"
  case None => "No value"
}
""",
        )
        chunks = chunk_file(src, "scala")

        # Check for trait and case objects
        assert any("Color" in c.content and "trait" in c.node_type for c in chunks)
        assert any("Red" in c.content and "object" in c.node_type for c in chunks)

        # Check for functions with pattern matching
        function_chunks = [
            c for c in chunks if "function" in c.node_type or "method" in c.node_type
        ]
        assert any(
            "describe" in c.content and "match" in c.content for c in function_chunks
        )
        assert any("processOption" in c.content for c in function_chunks)

    def test_implicit_definitions(self, tmp_path):
        """Test implicit values and conversions."""
        src = tmp_path / "Implicits.scala"
        src.write_text(
            """package example

implicit val defaultTimeout: Int = 5000

implicit def stringToInt(s: String): Int = s.toInt

implicit class RichString(s: String) {
  def toSnakeCase: String = s.replaceAll("([A-Z])", "_$1").toLowerCase
}

def processWithTimeout(data: String)(implicit timeout: Int): Unit = {
  println(s"Processing with timeout: $timeout")
}
""",
        )
        chunks = chunk_file(src, "scala")

        # Check for implicit definitions
        implicit_chunks = [
            c
            for c in chunks
            if "implicit" in c.node_type or "implicit" in c.content[:50]
        ]
        assert len(implicit_chunks) >= 3

        # Verify different implicit types
        assert any("defaultTimeout" in c.content for c in chunks)
        assert any("stringToInt" in c.content for c in chunks)
        assert any("RichString" in c.content for c in chunks)


class TestScalaContractCompliance:
    """Test ExtendedLanguagePluginContract implementation."""

    def test_implements_contract(self):
        """Test that ScalaPlugin implements the contract."""
        plugin = ScalaPlugin()
        assert isinstance(plugin, ExtendedLanguagePluginContract)

    def test_get_semantic_chunks(self):
        """Test get_semantic_chunks method."""
        plugin = ScalaPlugin()

        # Mock node structure
        class MockNode:
            def __init__(self, node_type, start=0, end=1):
                self.type = node_type
                self.start_byte = start
                self.end_byte = end
                self.start_point = (0, 0)
                self.end_point = (0, end)
                self.children = []

        root = MockNode("compilation_unit")
        func_node = MockNode("function_definition", 0, 50)
        root.children.append(func_node)

        source = b"def factorial(n: Int): Int = n * factorial(n - 1)"
        chunks = plugin.get_semantic_chunks(root, source)

        assert len(chunks) >= 1
        assert any(chunk["type"] == "function_definition" for chunk in chunks)

    def test_get_chunk_node_types(self):
        """Test get_chunk_node_types method."""
        plugin = ScalaPlugin()
        node_types = plugin.get_chunk_node_types()

        assert isinstance(node_types, set)
        assert "function_definition" in node_types
        assert "class_definition" in node_types
        assert "object_definition" in node_types
        assert "trait_definition" in node_types

    def test_should_chunk_node(self):
        """Test should_chunk_node method."""
        plugin = ScalaPlugin()

        # Mock node
        class MockNode:
            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        # Test chunk nodes
        assert plugin.should_chunk_node(MockNode("function_definition"))
        assert plugin.should_chunk_node(MockNode("class_definition"))
        assert plugin.should_chunk_node(MockNode("object_definition"))
        assert plugin.should_chunk_node(MockNode("trait_definition"))

        # Test non-chunk nodes
        assert not plugin.should_chunk_node(MockNode("identifier"))
        assert not plugin.should_chunk_node(MockNode("comment"))

    def test_get_node_context(self):
        """Test get_node_context method."""
        plugin = ScalaPlugin()

        # Mock node
        class MockNode:
            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        # Test context extraction
        node = MockNode("function_definition")
        context = plugin.get_node_context(node, b"def factorial(n: Int)")
        assert context is not None
        assert "def" in context or "method" in context


class TestScalaEdgeCases:
    """Test edge cases in Scala parsing."""

    def test_empty_file(self, tmp_path):
        """Test empty Scala file."""
        src = tmp_path / "Empty.scala"
        src.write_text("")
        chunks = chunk_file(src, "scala")
        assert len(chunks) == 0

    def test_comments_only(self, tmp_path):
        """Test file with only comments."""
        src = tmp_path / "Comments.scala"
        src.write_text(
            """// Single line comment
/* Multi-line
   comment */
/** ScalaDoc comment
  * @param x the parameter
  */
""",
        )
        chunks = chunk_file(src, "scala")
        # Comments should be ignored
        assert len(chunks) == 0

    def test_for_comprehensions(self, tmp_path):
        """Test for comprehensions."""
        src = tmp_path / "ForComprehensions.scala"
        src.write_text(
            """def cartesianProduct(xs: List[Int], ys: List[Int]): List[(Int, Int)] =
  for {
    x <- xs
    y <- ys
  } yield (x, y)

def complexFor(): List[Int] = {
  for {
    i <- 1 to 10
    j <- 1 to i
    if i + j > 10
  } yield i * j
}
""",
        )
        chunks = chunk_file(src, "scala")

        # Functions with for comprehensions should be chunked
        function_chunks = [
            c for c in chunks if "function" in c.node_type or "method" in c.node_type
        ]
        assert len(function_chunks) >= 2
        assert any(
            "cartesianProduct" in c.content and "for" in c.content
            for c in function_chunks
        )
        assert any("complexFor" in c.content for c in function_chunks)

    def test_type_parameters(self, tmp_path):
        """Test generic types and type parameters."""
        src = tmp_path / "Generics.scala"
        src.write_text(
            """class Box[T](val value: T) {
  def map[U](f: T => U): Box[U] = new Box(f(value))
}

trait Container[+A] {
  def get: A
}

def identity[T](x: T): T = x

type StringMap[V] = Map[String, V]
""",
        )
        chunks = chunk_file(src, "scala")

        # Check for generic definitions
        assert any("Box" in c.content and "[T]" in c.content for c in chunks)
        assert any("Container" in c.content and "[+A]" in c.content for c in chunks)
        assert any("identity" in c.content and "[T]" in c.content for c in chunks)

        # Check for type alias
        type_chunks = [c for c in chunks if c.node_type == "type_definition"]
        assert any("StringMap" in c.content for c in type_chunks)

    def test_nested_definitions(self, tmp_path):
        """Test nested classes and methods."""
        src = tmp_path / "Nested.scala"
        src.write_text(
            """class Outer(val name: String) {
  class Inner(val id: Int) {
    def innerMethod(): String = s"$name-$id"
  }

  def createInner(id: Int): Inner = new Inner(id)

  object InnerCompanion {
    val DefaultId = 0
  }
}

object Utils {
  def process(): Unit = {
    def helper(x: Int): Int = x * 2

    val result = helper(42)
    println(result)
  }
}
""",
        )
        chunks = chunk_file(src, "scala")

        # Check for outer and nested definitions
        assert any("Outer" in c.content and "class" in c.node_type for c in chunks)
        assert any("Inner" in c.content and "class" in c.node_type for c in chunks)
        assert any(
            "InnerCompanion" in c.content and "object" in c.node_type for c in chunks
        )
        assert any("Utils" in c.content and "object" in c.node_type for c in chunks)
