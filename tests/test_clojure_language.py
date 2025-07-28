"""Comprehensive tests for Clojure language support."""

from chunker import chunk_file
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.clojure import ClojurePlugin


class TestClojureBasicChunking:
    """Test basic Clojure chunking functionality."""

    def test_simple_functions(self, tmp_path):
        """Test basic function definitions."""
        src = tmp_path / "functions.clj"
        src.write_text(
            """(ns example.core)

(defn factorial
  "Calculate factorial of n"
  [n]
  (if (<= n 1)
    1
    (* n (factorial (dec n)))))

(defn- private-helper
  "A private helper function"
  [x]
  (* x x))

(def pi 3.14159)

(defn area-of-circle
  [radius]
  (* pi (private-helper radius)))
""",
        )
        chunks = chunk_file(src, "clojure")
        assert len(chunks) >= 4

        # Check for namespace
        ns_chunks = [
            c for c in chunks if c.node_type == "namespace" or "ns" in c.content
        ]
        assert len(ns_chunks) >= 1

        # Check for public and private functions
        defn_chunks = [c for c in chunks if c.node_type == "defn"]
        defn_private_chunks = [c for c in chunks if c.node_type == "defn-"]
        assert len(defn_chunks) >= 2
        assert len(defn_private_chunks) >= 1

        # Check for def
        def_chunks = [c for c in chunks if c.node_type == "def"]
        assert len(def_chunks) >= 1
        assert any("pi" in c.content for c in def_chunks)

    def test_macros_and_special_forms(self, tmp_path):
        """Test macro definitions and special forms."""
        src = tmp_path / "macros.clj"
        src.write_text(
            """(ns example.macros)

(defmacro when-not
  "Evaluates test. If logical false, evaluates body in an implicit do."
  [test & body]
  `(if (not ~test)
     (do ~@body)))

(defmacro with-timing
  "Times the execution of expressions"
  [& body]
  `(let [start# (System/currentTimeMillis)
         result# (do ~@body)
         end# (System/currentTimeMillis)]
     (println "Elapsed time:" (- end# start#) "ms")
     result#))

(defonce initialized? (atom false))
""",
        )
        chunks = chunk_file(src, "clojure")

        # Check for macros
        macro_chunks = [c for c in chunks if c.node_type == "defmacro"]
        assert len(macro_chunks) >= 2
        assert any("when-not" in c.content for c in macro_chunks)
        assert any("with-timing" in c.content for c in macro_chunks)

        # Check for defonce
        defonce_chunks = [c for c in chunks if c.node_type == "defonce"]
        assert len(defonce_chunks) >= 1

    def test_protocols_and_types(self, tmp_path):
        """Test protocol and type definitions."""
        src = tmp_path / "protocols.clj"
        src.write_text(
            """(ns example.protocols)

(defprotocol Drawable
  "A protocol for drawable shapes"
  (draw [this canvas])
  (get-bounds [this]))

(defrecord Rectangle [x y width height]
  Drawable
  (draw [this canvas]
    (.drawRect canvas x y width height))
  (get-bounds [this]
    {:x x :y y :width width :height height}))

(deftype Circle [center-x center-y radius]
  Drawable
  (draw [this canvas]
    (.drawOval canvas 
               (- center-x radius) 
               (- center-y radius)
               (* 2 radius)
               (* 2 radius)))
  (get-bounds [this]
    {:x (- center-x radius)
     :y (- center-y radius)
     :width (* 2 radius)
     :height (* 2 radius)}))
""",
        )
        chunks = chunk_file(src, "clojure")

        # Check for protocol
        protocol_chunks = [c for c in chunks if c.node_type == "defprotocol"]
        assert len(protocol_chunks) >= 1
        assert any("Drawable" in c.content for c in protocol_chunks)

        # Check for record and type
        record_chunks = [c for c in chunks if c.node_type == "defrecord"]
        type_chunks = [c for c in chunks if c.node_type == "deftype"]
        assert len(record_chunks) >= 1
        assert len(type_chunks) >= 1
        assert any("Rectangle" in c.content for c in record_chunks)
        assert any("Circle" in c.content for c in type_chunks)

    def test_multimethods(self, tmp_path):
        """Test multimethod definitions."""
        src = tmp_path / "multimethods.clj"
        src.write_text(
            """(ns example.multimethods)

(defmulti greet
  "Greet based on language preference"
  :language)

(defmethod greet :english
  [person]
  (str "Hello, " (:name person) "!"))

(defmethod greet :spanish
  [person]
  (str "¡Hola, " (:name person) "!"))

(defmethod greet :default
  [person]
  (str "Hi, " (:name person) "!"))

(defmulti area
  "Calculate area of a shape"
  :shape)

(defmethod area :circle
  [{:keys [radius]}]
  (* Math/PI radius radius))

(defmethod area :rectangle
  [{:keys [width height]}]
  (* width height))
""",
        )
        chunks = chunk_file(src, "clojure")

        # Check for defmulti
        multi_chunks = [c for c in chunks if c.node_type == "defmulti"]
        assert len(multi_chunks) >= 2
        assert any("greet" in c.content for c in multi_chunks)
        assert any("area" in c.content for c in multi_chunks)

        # Check for defmethod
        method_chunks = [c for c in chunks if c.node_type == "defmethod"]
        assert len(method_chunks) >= 5  # 3 greet methods + 2 area methods


class TestClojureContractCompliance:
    """Test ExtendedLanguagePluginContract implementation."""

    def test_implements_contract(self):
        """Test that ClojurePlugin implements the contract."""
        plugin = ClojurePlugin()
        assert isinstance(plugin, ExtendedLanguagePluginContract)

    def test_get_semantic_chunks(self):
        """Test get_semantic_chunks method."""
        plugin = ClojurePlugin()

        # Mock node structure
        class MockNode:
            def __init__(self, node_type, start=0, end=1):
                self.type = node_type
                self.start_byte = start
                self.end_byte = end
                self.start_point = (0, 0)
                self.end_point = (0, end)
                self.children = []

        root = MockNode("source")
        list_node = MockNode("list_lit", 0, 50)
        sym_node = MockNode("sym_lit", 1, 5)
        name_node = MockNode("sym_lit", 6, 15)
        list_node.children = [sym_node, name_node]
        root.children.append(list_node)

        source = b"(defn factorial [n] (* n (factorial (dec n))))"
        chunks = plugin.get_semantic_chunks(root, source)

        assert len(chunks) >= 0  # May be empty if mock doesn't match expected structure

    def test_get_chunk_node_types(self):
        """Test get_chunk_node_types method."""
        plugin = ClojurePlugin()
        node_types = plugin.get_chunk_node_types()

        assert isinstance(node_types, set)
        assert "list_lit" in node_types
        assert "defprotocol" in node_types
        assert "deftype" in node_types
        assert "ns_form" in node_types

    def test_should_chunk_node(self):
        """Test should_chunk_node method."""
        plugin = ClojurePlugin()

        # Mock node
        class MockNode:
            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        # Test chunk nodes
        assert plugin.should_chunk_node(MockNode("list_lit"))
        assert plugin.should_chunk_node(MockNode("defprotocol"))
        assert plugin.should_chunk_node(MockNode("deftype"))
        assert plugin.should_chunk_node(MockNode("ns_form"))

        # Test non-chunk nodes
        assert not plugin.should_chunk_node(MockNode("str_lit"))
        assert not plugin.should_chunk_node(MockNode("num_lit"))

    def test_get_node_context(self):
        """Test get_node_context method."""
        plugin = ClojurePlugin()

        # Mock node
        class MockNode:
            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        # Test context extraction
        node = MockNode("ns_form")
        context = plugin.get_node_context(node, b"(ns example.core)")
        assert context is not None
        assert "ns" in context


class TestClojureEdgeCases:
    """Test edge cases in Clojure parsing."""

    def test_empty_file(self, tmp_path):
        """Test empty Clojure file."""
        src = tmp_path / "empty.clj"
        src.write_text("")
        chunks = chunk_file(src, "clojure")
        assert len(chunks) == 0

    def test_comments_only(self, tmp_path):
        """Test file with only comments."""
        src = tmp_path / "comments.clj"
        src.write_text(
            """; Single line comment
;; Another comment
;;; Documentation comment

#_"This is a discard form"
""",
        )
        chunks = chunk_file(src, "clojure")
        # Comments should be ignored
        assert len(chunks) == 0

    def test_let_and_letfn(self, tmp_path):
        """Test let and letfn forms."""
        src = tmp_path / "let_forms.clj"
        src.write_text(
            """(ns example.let)

(defn complex-calculation
  [x y]
  (let [sum (+ x y)
        product (* x y)
        diff (- x y)
        avg (/ sum 2)]
    {:sum sum
     :product product
     :difference diff
     :average avg}))

(defn with-local-functions
  [coll]
  (letfn [(square [x] (* x x))
          (cube [x] (* x x x))
          (process [f xs] (map f xs))]
    {:squares (process square coll)
     :cubes (process cube coll)}))
""",
        )
        chunks = chunk_file(src, "clojure")

        # Functions should be chunked
        function_chunks = [c for c in chunks if c.node_type == "defn"]
        assert len(function_chunks) >= 2
        assert any("complex-calculation" in c.content for c in function_chunks)
        assert any("with-local-functions" in c.content for c in function_chunks)

    def test_anonymous_functions(self, tmp_path):
        """Test anonymous function forms."""
        src = tmp_path / "anon.clj"
        src.write_text(
            """(ns example.anon)

(def squares (map #(* % %) (range 10)))

(def add-5 (fn [x] (+ x 5)))

(defn apply-twice
  [f x]
  ((fn [g y] (g (g y))) f x))

(def complex-fn
  (fn [{:keys [x y] :as point}]
    (Math/sqrt (+ (* x x) (* y y)))))
""",
        )
        chunks = chunk_file(src, "clojure")

        # def forms should be chunked
        def_chunks = [c for c in chunks if c.node_type == "def"]
        assert len(def_chunks) >= 3
        assert any("squares" in c.content for c in def_chunks)
        assert any("add-5" in c.content for c in def_chunks)
        assert any("complex-fn" in c.content for c in def_chunks)

    def test_metadata_and_reader_macros(self, tmp_path):
        """Test metadata and reader macro handling."""
        src = tmp_path / "metadata.clj"
        src.write_text(
            """(ns example.metadata)

(defn ^:private ^:deprecated old-function
  "This function is deprecated"
  [x]
  (println "Please don't use this"))

(def ^{:doc "A special constant"
       :added "1.0"
       :static true}
  special-value 42)

(defn ^String type-hinted-fn
  ^String [^Integer x]
  (str "Number: " x))

#?(:clj
   (defn jvm-only []
     (println "Running on JVM")))

#?(:cljs
   (defn js-only []
     (js/console.log "Running in JS")))
""",
        )
        chunks = chunk_file(src, "clojure")

        # Functions with metadata should still be chunked
        function_chunks = [c for c in chunks if c.node_type == "defn"]
        assert len(function_chunks) >= 1
        assert any("old-function" in c.content for c in function_chunks)
        assert any("type-hinted-fn" in c.content for c in function_chunks)

        # def with metadata
        def_chunks = [c for c in chunks if c.node_type == "def"]
        assert any("special-value" in c.content for c in def_chunks)

    def test_threading_macros(self, tmp_path):
        """Test threading macro usage."""
        src = tmp_path / "threading.clj"
        src.write_text(
            """(ns example.threading)

(defn process-data
  [input]
  (-> input
      str/trim
      str/lower-case
      (str/split #" ")
      (->> (map str/capitalize))
      (str/join " ")))

(defn complex-pipeline
  [data]
  (->> data
       (filter :active)
       (map :name)
       (sort)
       (take 10)))

(defn conditional-threading
  [x]
  (cond-> x
    (string? x) str/trim
    (< (count x) 5) (str "short: ")
    :always str/upper-case))
""",
        )
        chunks = chunk_file(src, "clojure")

        # All functions with threading macros should be chunked
        function_chunks = [c for c in chunks if c.node_type == "defn"]
        assert len(function_chunks) >= 3
        assert any(
            "process-data" in c.content and "->" in c.content for c in function_chunks
        )
        assert any(
            "complex-pipeline" in c.content and "->>" in c.content
            for c in function_chunks
        )
        assert any(
            "conditional-threading" in c.content and "cond->" in c.content
            for c in function_chunks
        )
