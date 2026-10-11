"""Test suite for Phase 1.5: Extended language support for call span extraction."""

from typing import Any

import pytest
from tree_sitter import Node

from chunker.metadata import MetadataExtractorFactory
from chunker.metadata.extractor import BaseMetadataExtractor
from chunker.metadata.languages.signature_only import SignatureOnlyMetadataExtractor
from chunker.parser import get_parser


class SimpleMetadataExtractor(BaseMetadataExtractor):
    """Simple concrete implementation for testing."""

    def extract_imports(self, node: Node, source: bytes) -> list[str]:
        """Extract imports (not needed for call testing)."""
        return []

    def extract_exports(self, node: Node, source: bytes) -> list[str]:
        """Extract exports (not needed for call testing)."""
        return []

    def extract_dependencies(self, node: Node, source: bytes) -> list[str]:
        """Extract dependencies (not needed for call testing)."""
        return []

    def extract_signature(self, node: Node, source: bytes) -> dict[str, Any] | None:
        """Extract signature (not needed for call testing)."""
        return None

    def extract_docstring(self, node: Node, source: bytes) -> str | None:
        """Extract docstring (not needed for call testing)."""
        return None


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("(dangerous)", ["dangerous"]),
        ("(quote (dangerous))", []),
        ("'(dangerous)", []),
        ("'(outer (dangerous))", []),
        ("(quote ; comment\n (dangerous))", []),
        ("(; comment\n quote (dangerous))", []),
        ("`(data ~(actual))", ["actual"]),
        ("`(data ~@(actual))", ["actual"]),
        ("`(data `(nested ~(still-data)))", []),
        ("`(data `(nested ~~(actual)))", ["actual"]),
        ("`(data ~(quote (still-data)))", []),
        ("`(quote ~(actual))", ["actual"]),
        ("`(data '~(actual))", ["actual"]),
        ("'`(actual)", []),
        ("(quote `(actual))", []),
        ("`'(quote ~(actual))", ["actual"]),
        ("`(data (clojure.core/unquote (actual)))", ["actual"]),
        ("`(data (clojure.core/unquote-splicing (actual)))", ["actual"]),
        ("`(data (unquote (actual)))", []),
        ("`(data (unquote-splicing (actual)))", []),
        ("'`(data (clojure.core/unquote (actual)))", []),
        ("`(data (clojure.core/unquote (quote (actual))))", []),
        (
            "`(data `(nested (clojure.core/unquote (clojure.core/unquote (actual)))))",
            ["actual"],
        ),
        ("`(data (clojure.core/unquote (actual) (actual)))", ["actual"]),
        ("`(data (clojure.core/unquote-splicing (actual) (actual)))", ["actual"]),
        ("`(data (clojure.core/unquote-splicing [1] (actual)))", []),
        ("`(data `(nested (clojure.core/unquote (actual))))", []),
        ("`(quote (clojure.core/unquote (actual)))", ["actual"]),
        ("`(data '(clojure.core/unquote (actual)))", ["actual"]),
        ("`(data (; comment\n clojure.core/unquote (actual)))", ["actual"]),
        ("(^:x quote (actual))", []),
        ("`(data (^:x clojure.core/unquote (actual)))", ["actual"]),
        ("(^{:x (actual)} identity 1)", ["identity"]),
        ("(^{:x (actual)} actual)", ["actual"]),
        ("^{:x (actual)} identity", []),
        ("(identity ^{:x (actual)} identity)", ["identity"]),
        ("[^{:x (actual)} identity]", []),
        ("^{:x (actual)} [1]", ["actual"]),
        ("^{:x (actual)} {:a 1}", ["actual"]),
        ("^{:x (actual)} #{1}", ["actual"]),
        ("^{:x (actual)} (identity 1)", ["identity"]),
        ("(def ^{:x (actual)} subject 1)", ["actual"]),
        ("(defn ^{:x (actual)} subject [] 1)", ["defn", "actual"]),
        ("(defonce ^{:x (actual)} unique-subject 1)", ["defonce", "actual"]),
        ("(let [^{:x (actual)} x 1] x)", []),
        ("(fn ^{:x (actual)} f [] 1)", []),
        ("(fn [^{:x (actual)} x] x)", []),
        ("(quote ^{:x (actual)} identity)", []),
        ("`^{:x (actual)} identity", []),
        ("`^{:x ~(actual)} identity", ["actual"]),
        ("`(^{:x ~(actual)} identity 1)", ["actual"]),
        ("`(data ~^{:x (actual)} identity)", []),
        ("(def ^{:x (actual)} subject)", ["actual"]),
        ("(declare ^{:x (actual)} declared-subject)", ["declare", "actual"]),
        ("(defn- ^{:x (actual)} private-subject [] 1)", ["defn-", "actual"]),
        ("(defmacro ^{:x (actual)} macro-subject [] 1)", ["defmacro", "actual"]),
        ("((fn ^{:x (actual)} [] 1))", []),
        ("(defn parameter-annotation ^{:x (actual)} [] 1)", ["defn"]),
        ("((fn (^{:x (actual)} [] 1)))", []),
        ("(defn parameter-arity (^{:x (actual)} [] 1))", ["defn"]),
        ("(let ^{:x (actual)} [v 1] v)", []),
        ("(let [^{:x (actual)} [v] [1]] v)", []),
        ("((fn [^{:x (actual)} [v]] v) [1])", []),
        ("(let [v ^{:x (actual)} [1]] v)", ["actual"]),
        ("((fn [] ^{:x (actual)} [1]))", ["actual"]),
        ("(let [^{:x (actual)} {:keys [v]} {:v 1}] v)", []),
        ("(let [{:keys [v] :or {v ^{:x (actual)} [1]}} {}] v)", ["actual"]),
        ("^{:x (actual)} ()", ["actual"]),
        ("^{:x (actual)} (#_ (ignored))", ["actual"]),
        ("(let* ^{:x (actual)} [v 1] (identity v))", ["identity"]),
        ("((fn* ^{:x (actual)} [v] (identity v)) 1)", ["identity"]),
        ("((fn [] (^{:x (actual)} [1] 0)))", ["actual"]),
        ("`^{:line ~(actual)} identity", []),
        ("`^{:column ~(actual)} identity", []),
        ("`^{:line ~(actual) :column ~(actual)} identity", []),
        ("`^{:line ~(actual) :x true} identity", ["actual"]),
        ("`^{:column ~(actual) :x true} identity", ["actual"]),
        ("`^{:line ~(actual)} [1]", []),
        ("`^{:line ~(actual)} ()", []),
        ("`^{:line ~(actual)} (identity 1)", []),
        ("`^{:line ~(actual) :x true} (identity 1)", ["actual"]),
        ("`^:private ^{:line ~(actual)} identity", ["actual"]),
        ("`^{:line ~(actual)} ^:private identity", ["actual"]),
        ("^{:x true} ^{:x (actual)} [1]", []),
        ("^{:x (actual)} ^{:x true} [1]", ["actual"]),
        ("`^{:x true} ^{:x ~(actual)} [1]", []),
        ("`^{:x ~(actual)} ^{:x true} [1]", ["actual"]),
        ("`^:private ^{:private ~(actual)} identity", []),
        ("`^String ^{:tag ~(actual)} identity", []),
        ("`^{:tag ~(actual)} ^String identity", ["actual"]),
        ("`^{:x ~(actual)} ~(identity 1)", ["identity"]),
        ("`(data ^{:x ~(actual)} ~@(identity [1]))", ["identity"]),
        ("((fn ^{:pre [(actual)]} [] 1))", ["actual"]),
        ("((fn ^{:post [(actual)]} [] 1))", ["actual"]),
        ("((fn ^{:pre [(actual)]} [] {} 1))", []),
        ("((fn ^{:post [(actual)]} [] {:pre [true]} 1))", []),
        ("((fn ^{:pre [(actual)]} [] {}))", ["actual"]),
        ("((fn* ^{:pre [(actual)]} [] 1))", []),
        ("((fn (^{:pre [(actual)]} [] 1)))", ["actual"]),
        ("((clojure.core/fn ^{:post [(actual)]} [] 1))", ["fn", "actual"]),
        ("((fn ^{:pre [(actual)] :x (actual)} [] 1))", ["actual"]),
        ("((fn ^{:pre []} ^{:pre [(actual)]} [] 1))", []),
        ("((fn ^{:pre [(actual)]} [^{:pre [(actual)]} x] x) 1)", ["actual"]),
        (
            "(do (defn pre-subject ^{:pre [(actual)]} [] 1) (pre-subject))",
            ["defn", "actual", "pre-subject"],
        ),
        (
            "(do (defn post-subject (^{:post [(actual)]} [] 1)) (post-subject))",
            ["defn", "actual", "post-subject"],
        ),
        ("((fn ^{:pre (actual)} [] 1))", []),
        ("((fn ^{:pre ((actual))} [] 1))", ["actual"]),
        ("((fn ^{:pre (actual (actual))} [] 1))", ["actual"]),
        ("((fn ^{:pre ^{:x (actual)} [true]} [] 1))", []),
        ("((fn ^{:pre ^{:x (actual)} [(actual)]} [] 1))", ["actual"]),
        ("((fn ^{:pre [^{:x (actual)} [true]]} [] 1))", ["actual"]),
        ("((fn ^{:pre ^{:x (actual)} ((actual))} [] 1))", ["actual"]),
        ("((fn ^{:pre #{(actual)}} [] 1))", ["actual"]),
        ("((fn ^{:pre ^{:x (actual)} #{true}} [] 1))", []),
        ("((fn ^{:pre {(actual) true}} [] 1))", ["actual"]),
        ("((fn ^{:pre ^{:x (actual)} {true true}} [] 1))", []),
        ("((fn ^{:pre [(actual) (actual)]} [] 1))", ["actual", "actual"]),
        ("((fn ^{:post (actual)} [] 1))", []),
        ("((fn ^{:post ((actual))} [] 1))", ["actual"]),
        ("((fn ^{:post (actual (actual))} [] 1))", ["actual"]),
        ("((fn ^{:post ^{:x (actual)} [true]} [] 1))", []),
        ("((fn ^{:post ^{:x (actual)} [(actual)]} [] 1))", ["actual"]),
        ("((fn ^{:post [^{:x (actual)} [true]]} [] 1))", ["actual"]),
        ("((fn ^{:post ^{:x (actual)} ((actual))} [] 1))", ["actual"]),
        ("((fn ^{:post #{(actual)}} [] 1))", ["actual"]),
        ("((fn ^{:post ^{:x (actual)} #{true}} [] 1))", []),
        ("((fn ^{:post {(actual) true}} [] 1))", ["actual"]),
        ("((fn ^{:post ^{:x (actual)} {true true}} [] 1))", []),
        ("((fn ^{:post [(actual) (actual)]} [] 1))", ["actual", "actual"]),
        ("((fn [] {:pre (actual)} 1))", []),
        ("((fn [] {:pre ((actual))} 1))", ["actual"]),
        ("((fn [] {:pre (actual (actual))} 1))", ["actual"]),
        ("((fn [] {:pre ^{:x (actual)} [true]} 1))", []),
        ("((fn [] {:pre ^{:x (actual)} [(actual)]} 1))", ["actual"]),
        ("((fn [] {:pre [^{:x (actual)} [true]]} 1))", ["actual"]),
        ("((fn [] {:pre ^{:x (actual)} ((actual))} 1))", ["actual"]),
        ("((fn [] {:pre #{(actual)}} 1))", ["actual"]),
        ("((fn [] {:pre ^{:x (actual)} #{true}} 1))", []),
        ("((fn [] {:pre {(actual) true}} 1))", ["actual"]),
        ("((fn [] {:pre ^{:x (actual)} {true true}} 1))", []),
        ("((fn [] {:pre [(actual) (actual)]} 1))", ["actual", "actual"]),
        ("((fn [] {:post (actual)} 1))", []),
        ("((fn [] {:post ((actual))} 1))", ["actual"]),
        ("((fn [] {:post (actual (actual))} 1))", ["actual"]),
        ("((fn [] {:post ^{:x (actual)} [true]} 1))", []),
        ("((fn [] {:post ^{:x (actual)} [(actual)]} 1))", ["actual"]),
        ("((fn [] {:post [^{:x (actual)} [true]]} 1))", ["actual"]),
        ("((fn [] {:post ^{:x (actual)} ((actual))} 1))", ["actual"]),
        ("((fn [] {:post #{(actual)}} 1))", ["actual"]),
        ("((fn [] {:post ^{:x (actual)} #{true}} 1))", []),
        ("((fn [] {:post {(actual) true}} 1))", ["actual"]),
        ("((fn [] {:post ^{:x (actual)} {true true}} 1))", []),
        ("((fn [] {:post [(actual) (actual)]} 1))", ["actual", "actual"]),
        ("((fn [] {:pre [true] :x (actual)} 1))", []),
        ("((fn [] ^{:x (actual)} {:pre [(actual)]} 1))", ["actual"]),
        ("((fn [] {:pre [(actual)]}))", ["actual"]),
        ("((fn ^{:pre [(actual)]} [] {:pre [(actual)]}))", ["actual", "actual"]),
        ("((fn* [] {:pre [(actual)]} 1))", ["actual"]),
        ("((fn ([] {:pre (actual)} 1)))", []),
        ("#_(discarded) (actual)", ["actual"]),
        ("(if true 1 2)", []),
        ("(if (condition) (f) (g))", ["condition", "f", "g"]),
        ("(let [x (init)] (do (use x)))", ["init", "use"]),
        ("(fn [x] (if x (f) (g)))", ["f", "g"]),
        ("(try (f) (catch Exception e (g)) (finally (h)))", ["f", "g", "h"]),
        ("(qualified/if (actual))", ["if", "actual"]),
        ("(letfn* [f (fn* [] 1)] (f))", ["f"]),
        ("(letfn* ^{:x (actual)} [f (fn* [] 1)] (f))", ["f"]),
        ("(letfn* [^{:x (actual)} f (fn* [] 1)] (f))", ["f"]),
        ("'(letfn* [f (fn* [] 1)] (f))", []),
        ("`(letfn* [f (fn* [] 1)] ~(actual))", ["actual"]),
        ("(qualified/letfn* (actual))", ["letfn*", "actual"]),
    ],
)
def test_clojure_call_evaluation_context(code, expected):
    source = code.encode()
    root = get_parser("clojure").parse(source).root_node
    extractor = SimpleMetadataExtractor("clojure")
    calls = extractor.extract_calls(root, source)
    assert [call["name"] for call in calls] == expected
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "list_lit":
            assert extractor.extract_calls(node, source) == [
                call
                for call in calls
                if node.start_byte <= call["start"] < node.end_byte
            ]
        stack.extend(node.named_children)


class TestPhase15Languages:
    """Test call span extraction for 15+ languages."""

    @staticmethod
    def _test_language_calls(
        language: str,
        code: str,
        expected_calls: list[str],
        excluded_calls: tuple[str, ...] = (),
    ):
        """Helper to test call extraction for a language."""
        # Use base extractor for languages without specific extractors. The
        # signature-only extractors (treesitter-chunker#354) extract no calls,
        # so their languages also exercise the base call branches.
        extractor = MetadataExtractorFactory.create_extractor(language)
        if extractor is None or isinstance(extractor, SignatureOnlyMetadataExtractor):
            extractor = SimpleMetadataExtractor(language)

        parser = get_parser(language)
        tree = parser.parse(code.encode())

        calls = extractor.extract_calls(tree.root_node, code.encode())
        extracted_names = [call["name"] for call in calls]

        # Check that all expected calls are found
        for expected in expected_calls:
            assert (
                expected in extracted_names
            ), f"Expected call '{expected}' not found in {extracted_names}"

        assert not set(excluded_calls).intersection(extracted_names)

        # Verify span information is present
        for call in calls:
            assert "start" in call
            assert "end" in call
            assert "function_start" in call
            assert "function_end" in call
            assert call["start"] <= call["function_start"]
            assert call["function_end"] <= call["end"]

    def test_java_method_calls(self):
        """Test Java method call extraction."""
        code = """
        public class Test {
            public void test() {
                System.out.println("hello");    // Should detect "println"
                String result = "test".length(); // Should detect "length"
                obj.method();                    // Should detect "method"
                Math.max(1, 2);                  // Should detect "max"
            }
        }
        """
        expected_calls = ["println", "length", "method", "max"]
        self._test_language_calls("java", code, expected_calls)

    def test_ruby_method_calls(self):
        """Test Ruby method call extraction."""
        code = """
        def test
            puts "hello"                    # Should detect "puts"
            result = "test".length          # Should detect "length"
            obj.method                      # Should detect "method"
            [1, 2, 3].map { |x| x * 2 }    # Should detect "map"
        end
        """
        expected_calls = ["puts", "length", "method", "map"]
        self._test_language_calls("ruby", code, expected_calls)

    def test_php_method_calls(self):
        """Test PHP method call extraction."""
        code = """
        <?php
        function test() {
            echo "hello";                 // Language statement, not a function call
            $result = strlen("test");     // Should detect "strlen"
            $obj->method();               // Should detect "method"
            array_map($fn, $array);       // Should detect "array_map"
        }
        ?>
        """
        expected_calls = ["strlen", "method", "array_map"]
        self._test_language_calls("php", code, expected_calls, ("echo",))

    def test_kotlin_method_calls(self):
        """Test Kotlin method call extraction."""
        code = """
        fun test() {
            println("hello")              // Should detect "println"
            val result = "test".length   // Property read, not an explicit call
            obj.method()                  // Should detect "method"
            listOf(1, 2, 3).map { it * 2 } // Should detect "map"
        }
        """
        expected_calls = ["println", "method", "map"]
        self._test_language_calls("kotlin", code, expected_calls, ("length",))

    def test_swift_method_calls(self):
        """Test Swift method call extraction."""
        code = """
        func test() {
            print("hello")                // Should detect "print"
            let result = "test".count     // Property read, not an explicit call
            obj.method()                  // Should detect "method"
            [1, 2, 3].map { $0 * 2 }     // Should detect "map"
        }
        """
        expected_calls = ["print", "method", "map"]
        self._test_language_calls("swift", code, expected_calls, ("count",))

    def test_csharp_method_calls(self):
        """Test C# method call extraction."""
        code = """
        public class Test {
            public void test() {
                Console.WriteLine("hello");     // Should detect "WriteLine"
                string result = "test".Length;  // Property read, not an explicit call
                obj.Method();                    // Should detect "Method"
                Math.Max(1, 2);                  // Should detect "Max"
            }
        }
        """
        expected_calls = ["WriteLine", "Method", "Max"]
        self._test_language_calls("csharp", code, expected_calls, ("Length",))

    def test_dart_method_calls(self):
        """Test Dart method call extraction."""
        code = """
        void test() {
            print("hello");                 // Should detect "print"
            var result = "test".length;     // Property read, not an explicit call
            obj.method();                   // Should detect "method"
            [1, 2, 3].map((x) => x * 2);   // Should detect "map"
        }
        """
        expected_calls = ["print", "method", "map"]
        self._test_language_calls("dart", code, expected_calls, ("length",))

    def test_haskell_function_calls(self):
        """Test Haskell function application extraction."""
        code = """
        test :: IO ()
        test = do
            putStrLn "hello"               -- Should detect "putStrLn"
            let result = length "test"      -- Should detect "length"
            let mapped = map id [1,2,3]    -- Should detect "map"
            return ()
        """
        expected_calls = ["putStrLn", "length", "map"]
        self._test_language_calls("haskell", code, expected_calls)

    def test_ocaml_method_calls(self):
        """Test OCaml method call extraction."""
        code = """
        let test () =
            print_endline "hello";         (* Should detect "print_endline" *)
            let result = String.length "test" in (* Should detect "length" *)
            List.map (fun x -> x * 2) [1; 2; 3] (* Should detect "map" *)
        """
        expected_calls = ["print_endline", "length", "map"]
        self._test_language_calls("ocaml", code, expected_calls)

    def test_scala_method_calls(self):
        """Test Scala method call extraction."""
        code = """
        def test(): Unit = {
            println("hello")                // Should detect "println"
            val result = "test".length      // Property read, not an explicit call
            obj.method()                    // Should detect "method"
            List(1, 2, 3).map(_ * 2)       // Should detect "map"
        }
        """
        expected_calls = ["println", "method", "map"]
        self._test_language_calls("scala", code, expected_calls, ("length",))

    def test_elixir_function_calls(self):
        """Test Elixir function call extraction."""
        code = """
        def test do
            IO.puts("hello")                # Should detect "puts"
            result = String.length("test")  # Should detect "length"
            Enum.map([1, 2, 3], &(&1 * 2)) # Should detect "map"
        end
        """
        expected_calls = ["puts", "length", "map"]
        self._test_language_calls("elixir", code, expected_calls)

    def test_clojure_function_calls(self):
        """Test Clojure function call extraction."""
        code = """
        (defn test []
            (println "hello")               ; Should detect "println"
            (let [result (count "test")]    ; Should detect "count"
                (map #(* % 2) [1 2 3])))    ; Should detect "map"
        """
        expected_calls = ["println", "count", "map"]
        self._test_language_calls("clojure", code, expected_calls)

    def test_julia_function_calls(self):
        """Test Julia function call extraction."""
        code = """
        function test()
            println("hello")                # Should detect "println"
            result = length("test")         # Should detect "length"
            map(x -> x * 2, [1, 2, 3])     # Should detect "map"
        end
        """
        expected_calls = ["println", "length", "map"]
        self._test_language_calls("julia", code, expected_calls)

    def test_r_function_calls(self):
        """Test R function call extraction."""
        code = """
        test <- function() {
            print("hello")                  # Should detect "print"
            result <- length("test")        # Should detect "length"
            sapply(c(1, 2, 3), function(x) x * 2) # Should detect "sapply"
        }
        """
        expected_calls = ["print", "length", "sapply"]
        self._test_language_calls("r", code, expected_calls)

    def test_matlab_function_calls(self):
        """Test MATLAB function call extraction."""
        code = """
        function test()
            disp('hello');                  % Should detect "disp"
            result = length('test');        % Should detect "length"
            arrayfun(@(x) x * 2, [1, 2, 3]); % Should detect "arrayfun"
        end
        """
        expected_calls = ["disp", "length", "arrayfun"]
        self._test_language_calls("matlab", code, expected_calls)


class TestPhase15EdgeCases:
    """Test edge cases for extended language support."""

    @staticmethod
    def _test_no_false_positives(language: str, code: str, not_expected: list[str]):
        """Helper to test that certain patterns are NOT detected as calls."""
        extractor = MetadataExtractorFactory.create_extractor(language)
        if extractor is None:
            extractor = SimpleMetadataExtractor(language)

        parser = get_parser(language)
        tree = parser.parse(code.encode())

        calls = extractor.extract_calls(tree.root_node, code.encode())
        extracted_names = [call["name"] for call in calls]

        # Check that none of the not_expected items are detected
        for item in not_expected:
            assert (
                item not in extracted_names
            ), f"False positive: '{item}' should not be detected as a call"

    def test_java_property_access(self):
        """Test that Java property access is not detected as method calls."""
        code = """
        public class Test {
            public void test() {
                int x = obj.field;          // Should NOT detect "field"
                obj.publicField = 5;        // Should NOT detect "publicField"
            }
        }
        """
        not_expected = ["field", "publicField"]
        self._test_no_false_positives("java", code, not_expected)

    def test_kotlin_property_access(self):
        """Test that Kotlin property access is not detected as method calls."""
        code = """
        fun test() {
            val x = obj.property         // Should NOT detect "property"
            obj.field = 5                // Should NOT detect "field"
        }
        """
        not_expected = ["property", "field"]
        self._test_no_false_positives("kotlin", code, not_expected)

    def test_csharp_property_access(self):
        """Test that C# property access is not detected as method calls."""
        code = """
        public class Test {
            public void test() {
                var x = obj.Property;    // Should NOT detect "Property"
                obj.Field = 5;           // Should NOT detect "Field"
            }
        }
        """
        not_expected = ["Property", "Field"]
        self._test_no_false_positives("csharp", code, not_expected)


class TestPhase15Performance:
    """Test performance of the enhanced base implementation."""

    def test_large_file_performance(self):
        """Test that the enhanced implementation handles large files efficiently."""
        # Generate a large code file with many function calls
        code_lines = []
        for i in range(1000):
            code_lines.append(f"    func{i}();")
            code_lines.append(f"    obj.method{i}();")
            code_lines.append(f"    Module.function{i}();")

        code = "def test():\n" + "\n".join(code_lines)

        extractor = SimpleMetadataExtractor("python")
        parser = get_parser("python")
        tree = parser.parse(code.encode())

        import time

        start = time.time()
        calls = extractor.extract_calls(tree.root_node, code.encode())
        elapsed = time.time() - start

        # Should process 3000 calls in under 1 second
        assert len(calls) >= 3000
        assert (
            elapsed < 1.0
        ), f"Performance issue: took {elapsed:.2f}s to process 3000 calls"

    def test_nested_calls_performance(self):
        """Test performance with deeply nested function calls."""
        # Generate deeply nested calls
        nested = "func("
        for i in range(50):
            nested += f"inner{i}("
        nested += "value"
        nested += ")" * 51

        code = f"def test():\n    {nested}"

        extractor = SimpleMetadataExtractor("python")
        parser = get_parser("python")
        tree = parser.parse(code.encode())

        import time

        start = time.time()
        calls = extractor.extract_calls(tree.root_node, code.encode())
        elapsed = time.time() - start

        # Should handle nested calls efficiently
        assert len(calls) >= 50
        assert (
            elapsed < 0.5
        ), f"Performance issue with nested calls: took {elapsed:.2f}s"
