"""Comprehensive tests for Dart language support."""

from chunker import chunk_file
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.dart import DartPlugin


class TestDartBasicChunking:
    """Test basic Dart chunking functionality."""

    def test_simple_functions(self, tmp_path):
        """Test basic function declarations."""
        src = tmp_path / "functions.dart"
        src.write_text(
            """import 'dart:math';

int factorial(int n) {
  if (n <= 1) return 1;
  return n * factorial(n - 1);
}

void printMessage(String message) {
  print('Message: $message');
}

Future<String> fetchData() async {
  await Future.delayed(Duration(seconds: 1));
  return 'Data loaded';
}

Stream<int> countStream(int max) async* {
  for (int i = 0; i < max; i++) {
    yield i;
  }
}
""",
        )
        chunks = chunk_file(src, "dart")
        assert len(chunks) >= 4

        # Check for function declarations
        function_chunks = [c for c in chunks if c.node_type == "function_declaration"]
        assert len(function_chunks) >= 4
        assert any("factorial" in c.content for c in function_chunks)
        assert any("printMessage" in c.content for c in function_chunks)
        assert any(
            "fetchData" in c.content and "async" in c.content for c in function_chunks
        )
        assert any(
            "countStream" in c.content and "async*" in c.content
            for c in function_chunks
        )

    def test_classes_and_methods(self, tmp_path):
        """Test class and method declarations."""
        src = tmp_path / "classes.dart"
        src.write_text(
            """class Person {
  final String name;
  int _age;

  Person(this.name, this._age);

  Person.withName(String name) : this(name, 0);

  factory Person.fromJson(Map<String, dynamic> json) {
    return Person(json['name'], json['age']);
  }

  int get age => _age;

  set age(int value) {
    if (value >= 0) _age = value;
  }

  void greet() {
    print('Hello, I am $name');
  }

  static Person createAnonymous() {
    return Person('Anonymous', 0);
  }
}

abstract class Shape {
  double get area;
  void draw();
}

mixin Colorable {
  String color = 'black';

  void setColor(String newColor) {
    color = newColor;
  }
}

class Circle extends Shape with Colorable {
  final double radius;

  Circle(this.radius);

  @override
  double get area => 3.14159 * radius * radius;

  @override
  void draw() {
    print('Drawing a $color circle');
  }
}
""",
        )
        chunks = chunk_file(src, "dart")

        # Check for class declarations
        class_chunks = [
            c for c in chunks if c.node_type in {"class_declaration", "widget_class"}
        ]
        assert len(class_chunks) >= 3
        assert any("Person" in c.content for c in class_chunks)
        assert any(
            "Shape" in c.content and "abstract" in c.content for c in class_chunks
        )
        assert any("Circle" in c.content for c in class_chunks)

        # Check for mixin
        mixin_chunks = [c for c in chunks if c.node_type == "mixin_declaration"]
        assert len(mixin_chunks) >= 1
        assert any("Colorable" in c.content for c in mixin_chunks)

        # Check for constructors
        constructor_chunks = [c for c in chunks if "constructor" in c.node_type]
        assert len(constructor_chunks) >= 3  # Regular, named, and factory constructors

        # Check for getters and setters
        getter_chunks = [c for c in chunks if c.node_type == "getter_declaration"]
        setter_chunks = [c for c in chunks if c.node_type == "setter_declaration"]
        assert len(getter_chunks) >= 2  # age and area getters
        assert len(setter_chunks) >= 1  # age setter

    def test_flutter_widgets(self, tmp_path):
        """Test Flutter widget classes."""
        src = tmp_path / "widgets.dart"
        src.write_text(
            """import 'package:flutter/material.dart';

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Flutter Demo',
      home: HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  final String title;

  const HomePage({Key? key, this.title = 'Home'}) : super(key: key);

  @override
  _HomePageState createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int _counter = 0;

  void _incrementCounter() {
    setState(() {
      _counter++;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: Center(
        child: Text('Counter: $_counter'),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _incrementCounter,
        child: Icon(Icons.add),
      ),
    );
  }
}
""",
        )
        chunks = chunk_file(src, "dart")

        # Check for widget classes
        widget_chunks = [
            c
            for c in chunks
            if "widget_class" in c.node_type
            or (
                "class" in c.node_type
                and ("StatelessWidget" in c.content or "StatefulWidget" in c.content)
            )
        ]
        assert len(widget_chunks) >= 3
        assert any(
            "MyApp" in c.content and "StatelessWidget" in c.content for c in chunks
        )
        assert any(
            "HomePage" in c.content and "StatefulWidget" in c.content for c in chunks
        )

        # Check for build methods
        build_methods = [
            c
            for c in chunks
            if c.node_type == "method_declaration" and "build" in c.content
        ]
        assert len(build_methods) >= 2

    def test_extensions_and_enums(self, tmp_path):
        """Test extension declarations and enums."""
        src = tmp_path / "extensions.dart"
        src.write_text(
            """enum Color { red, green, blue, alpha }

enum Status {
  pending('Pending'),
  approved('Approved'),
  rejected('Rejected');

  final String displayName;
  const Status(this.displayName);
}

extension StringExtensions on String {
  String get reversed => split('').reversed.join();

  bool get isEmail => contains('@') && contains('.');

  String capitalize() {
    if (isEmpty) return this;
    return '${this[0].toUpperCase()}${substring(1)}';
  }
}

extension IterableExtensions<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;

  Iterable<T> whereNotNull() {
    return where((e) => e != null);
  }
}
""",
        )
        chunks = chunk_file(src, "dart")

        # Check for enums
        enum_chunks = [c for c in chunks if c.node_type == "enum_declaration"]
        assert len(enum_chunks) >= 2
        assert any("Color" in c.content for c in enum_chunks)
        assert any("Status" in c.content for c in enum_chunks)

        # Check for extensions
        extension_chunks = [c for c in chunks if c.node_type == "extension_declaration"]
        assert len(extension_chunks) >= 2
        assert any("StringExtensions" in c.content for c in extension_chunks)
        assert any("IterableExtensions" in c.content for c in extension_chunks)


class TestDartContractCompliance:
    """Test ExtendedLanguagePluginContract implementation."""

    def test_implements_contract(self):
        """Test that DartPlugin implements the contract."""
        plugin = DartPlugin()
        assert isinstance(plugin, ExtendedLanguagePluginContract)

    def test_get_semantic_chunks(self):
        """Test get_semantic_chunks method."""
        plugin = DartPlugin()

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
        func_node = MockNode("function_declaration", 0, 50)
        root.children.append(func_node)

        source = b"void main() { print('Hello'); }"
        chunks = plugin.get_semantic_chunks(root, source)

        assert len(chunks) >= 1
        assert any(chunk["type"] == "function_declaration" for chunk in chunks)

    def test_get_chunk_node_types(self):
        """Test get_chunk_node_types method."""
        plugin = DartPlugin()
        node_types = plugin.get_chunk_node_types()

        assert isinstance(node_types, set)
        assert "function_declaration" in node_types
        assert "class_declaration" in node_types
        assert "method_declaration" in node_types
        assert "mixin_declaration" in node_types

    def test_should_chunk_node(self):
        """Test should_chunk_node method."""
        plugin = DartPlugin()

        # Mock node
        class MockNode:
            def __init__(self, node_type):
                self.type = node_type

        # Test chunk nodes
        assert plugin.should_chunk_node(MockNode("function_declaration"))
        assert plugin.should_chunk_node(MockNode("class_declaration"))
        assert plugin.should_chunk_node(MockNode("method_declaration"))
        assert plugin.should_chunk_node(MockNode("mixin_declaration"))

        # Test non-chunk nodes
        assert not plugin.should_chunk_node(MockNode("identifier"))
        assert not plugin.should_chunk_node(MockNode("comment"))

    def test_get_node_context(self):
        """Test get_node_context method."""
        plugin = DartPlugin()

        # Mock node
        class MockNode:
            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        # Test context extraction
        node = MockNode("function_declaration")
        context = plugin.get_node_context(node, b"void main() {}")
        assert context is not None
        assert "function" in context


class TestDartEdgeCases:
    """Test edge cases in Dart parsing."""

    def test_empty_file(self, tmp_path):
        """Test empty Dart file."""
        src = tmp_path / "empty.dart"
        src.write_text("")
        chunks = chunk_file(src, "dart")
        assert len(chunks) == 0

    def test_comments_only(self, tmp_path):
        """Test file with only comments."""
        src = tmp_path / "comments.dart"
        src.write_text(
            """// Single line comment
/* Multi-line
   comment */
/// Documentation comment
/// with multiple lines
""",
        )
        chunks = chunk_file(src, "dart")
        # Comments should be ignored
        assert len(chunks) == 0

    def test_async_patterns(self, tmp_path):
        """Test various async patterns."""
        src = tmp_path / "async.dart"
        src.write_text(
            """import 'dart:async';

Future<void> asyncFunction() async {
  await Future.delayed(Duration(seconds: 1));
  print('Done');
}

Future<int> asyncWithReturn() async {
  final result = await computeValue();
  return result * 2;
}

Stream<String> asyncGenerator() async* {
  for (int i = 0; i < 5; i++) {
    await Future.delayed(Duration(milliseconds: 100));
    yield 'Item $i';
  }
}

Iterable<int> syncGenerator() sync* {
  for (int i = 0; i < 10; i++) {
    yield i * i;
  }
}

Future<int> computeValue() async => 42;
""",
        )
        chunks = chunk_file(src, "dart")

        # All async functions should be chunked
        async_chunks = [c for c in chunks if "async" in c.content]
        assert len(async_chunks) >= 4
        assert any("asyncFunction" in c.content for c in async_chunks)
        assert any("asyncWithReturn" in c.content for c in async_chunks)
        assert any(
            "asyncGenerator" in c.content and "async*" in c.content
            for c in async_chunks
        )

        # Sync generator
        sync_gen_chunks = [
            c for c in chunks if "syncGenerator" in c.content and "sync*" in c.content
        ]
        assert len(sync_gen_chunks) >= 1

    def test_null_safety(self, tmp_path):
        """Test null safety features."""
        src = tmp_path / "null_safety.dart"
        src.write_text(
            """class User {
  final String name;
  final String? email;
  late final int id;

  User({required this.name, this.email}) {
    id = _generateId();
  }

  int _generateId() => DateTime.now().millisecondsSinceEpoch;

  void sendEmail(String message) {
    if (email != null) {
      print('Sending to $email: $message');
    }
  }

  String getDisplayName() {
    return email ?? name;
  }
}

void processNullable(String? value) {
  final length = value?.length ?? 0;
  print('Length: $length');
}

T requireNotNull<T>(T? value, String message) {
  if (value == null) {
    throw ArgumentError(message);
  }
  return value;
}
""",
        )
        chunks = chunk_file(src, "dart")

        # Check class with nullable fields
        [c for c in chunks if c.node_type == "class_declaration"]
        assert any("User" in c.content and "String?" in c.content for c in chunks)

        # Check functions handling nullable types
        function_chunks = [c for c in chunks if "function" in c.node_type]
        assert any("processNullable" in c.content for c in function_chunks)
        assert any(
            "requireNotNull" in c.content and "<T>" in c.content
            for c in function_chunks
        )

    def test_typedef_and_generics(self, tmp_path):
        """Test typedef declarations and generic types."""
        src = tmp_path / "typedefs.dart"
        src.write_text(
            """typedef IntMapper = int Function(int);
typedef StringProcessor = Future<String> Function(String input, {bool reverse});
typedef GenericTransform<T, R> = R Function(T value);

class Container<T> {
  final T value;

  Container(this.value);

  R map<R>(R Function(T) transform) {
    return transform(value);
  }
}

class Pair<T, U> {
  final T first;
  final U second;

  const Pair(this.first, this.second);

  Pair<U, T> swap() => Pair(second, first);
}

T identity<T>(T value) => value;

List<R> mapList<T, R>(List<T> items, R Function(T) transform) {
  return items.map(transform).toList();
}
""",
        )
        chunks = chunk_file(src, "dart")

        # Check typedef declarations
        typedef_chunks = [c for c in chunks if c.node_type == "typedef_declaration"]
        assert len(typedef_chunks) >= 3
        assert any("IntMapper" in c.content for c in typedef_chunks)
        assert any("StringProcessor" in c.content for c in typedef_chunks)
        assert any("GenericTransform" in c.content for c in typedef_chunks)

        # Check generic classes
        [c for c in chunks if c.node_type == "class_declaration"]
        assert any("Container<T>" in c.content for c in chunks)
        assert any("Pair<T, U>" in c.content for c in chunks)

        # Check generic functions
        [c for c in chunks if "function" in c.node_type]
        assert any("identity<T>" in c.content for c in chunks)
        assert any("mapList<T, R>" in c.content for c in chunks)
