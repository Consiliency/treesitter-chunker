"""Comprehensive tests for OCaml language support."""

from chunker import chunk_file, get_parser
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.ocaml import OCamlPlugin


class TestOCamlBasicChunking:
    """Test basic OCaml chunking functionality."""

    def test_simple_functions(self, tmp_path):
        """Test basic OCaml function definitions."""
        src = tmp_path / "simple.ml"
        src.write_text(
            """(* Simple function *)
let add x y = x + y

(* Function with type annotation *)
let multiply (x : int) (y : int) : int = x * y

(* Recursive function *)
let rec factorial n =
  if n <= 1 then 1
  else n * factorial (n - 1)

(* Function with pattern matching *)
let rec length lst =
  match lst with
  | [] -> 0
  | _ :: tail -> 1 + length tail
""",
        )
        chunks = chunk_file(src, "ocaml")
        assert len(chunks) >= 4

        # Check for different function types
        let_chunks = [c for c in chunks if "let" in c.content]
        assert len(let_chunks) >= 4
        assert any("add" in c.content for c in let_chunks)
        assert any("multiply" in c.content for c in let_chunks)
        assert any("factorial" in c.content for c in let_chunks)
        assert any("length" in c.content for c in let_chunks)

    def test_type_definitions(self, tmp_path):
        """Test OCaml type definitions."""
        src = tmp_path / "types.ml"
        src.write_text(
            """(* Type alias *)
type number = int

(* Variant type *)
type color =
  | Red
  | Green
  | Blue
  | RGB of int * int * int

(* Record type *)
type person = {
  name : string;
  age : int;
  email : string option;
}

(* Parametric type *)
type 'a tree =
  | Leaf
  | Node of 'a * 'a tree * 'a tree

(* Mutually recursive types *)
type expr =
  | Int of int
  | Add of expr * expr
  | Mul of expr * expr
  | Let of string * expr * expr
and value =
  | VInt of int
  | VClosure of string * expr * env
and env = (string * value) list
""",
        )
        chunks = chunk_file(src, "ocaml")

        # Check for type definitions
        type_chunks = [
            c for c in chunks if c.node_type in ["type_definition", "type_binding"]
        ]
        assert len(type_chunks) >= 5
        assert any("color" in c.content and "RGB" in c.content for c in type_chunks)
        assert any(
            "person" in c.content and "record" in str(c.content) for c in type_chunks
        )
        assert any("'a tree" in c.content for c in type_chunks)

    def test_module_definitions(self, tmp_path):
        """Test OCaml module definitions."""
        src = tmp_path / "modules.ml"
        src.write_text(
            """(* Simple module *)
module Stack = struct
  type 'a t = 'a list

  let empty = []

  let push x s = x :: s

  let pop = function
    | [] -> failwith "Empty stack"
    | h :: t -> (h, t)

  let is_empty s = s = []
end

(* Module with signature *)
module type COMPARABLE = sig
  type t
  val compare : t -> t -> int
end

(* Functor *)
module MakeSet (M : COMPARABLE) = struct
  type element = M.t
  type t = element list

  let empty = []

  let add x s =
    if List.mem x s then s else x :: s
end

(* Nested modules *)
module Outer = struct
  module Inner = struct
    let value = 42
  end

  let get_value () = Inner.value
end
""",
        )
        chunks = chunk_file(src, "ocaml")

        # Check for module definitions
        module_chunks = [c for c in chunks if "module" in c.node_type]
        assert len(module_chunks) >= 4
        assert any("Stack" in c.content for c in module_chunks)
        assert any("COMPARABLE" in c.content for c in module_chunks)
        assert any("MakeSet" in c.content for c in module_chunks)
        assert any("Outer" in c.content for c in module_chunks)

    def test_exception_definitions(self, tmp_path):
        """Test OCaml exception definitions."""
        src = tmp_path / "exceptions.ml"
        src.write_text(
            """(* Simple exception *)
exception Not_found

(* Exception with data *)
exception Invalid_argument of string

(* Exception with multiple arguments *)
exception Parse_error of string * int * int

(* Using exceptions *)
let safe_divide x y =
  if y = 0 then
    raise (Invalid_argument "Division by zero")
  else
    x / y

(* Exception handling *)
let try_divide x y =
  try
    Some (safe_divide x y)
  with
  | Invalid_argument msg ->
    Printf.printf "Error: %s\\n" msg;
    None
""",
        )
        chunks = chunk_file(src, "ocaml")

        # Check for exception definitions
        exception_chunks = [c for c in chunks if c.node_type == "exception_definition"]
        assert len(exception_chunks) >= 3
        assert any("Not_found" in c.content for c in exception_chunks)
        assert any("Invalid_argument" in c.content for c in exception_chunks)
        assert any("Parse_error" in c.content for c in exception_chunks)

    def test_class_definitions(self, tmp_path):
        """Test OCaml class definitions."""
        src = tmp_path / "classes.ml"
        src.write_text(
            """(* Simple class *)
class point x_init y_init =
  object
    val mutable x = x_init
    val mutable y = y_init

    method get_x = x
    method get_y = y

    method move dx dy =
      x <- x + dx;
      y <- y + dy

    method distance (other : point) =
      let dx = x - other#get_x in
      let dy = y - other#get_y in
      sqrt (float_of_int (dx * dx + dy * dy))
  end

(* Class with inheritance *)
class colored_point x y c =
  object
    inherit point x y
    val color = c
    method get_color = color
  end

(* Virtual class *)
class virtual shape =
  object
    method virtual area : float
    method virtual perimeter : float
  end
""",
        )
        chunks = chunk_file(src, "ocaml")

        # Check for class definitions
        class_chunks = [c for c in chunks if "class" in c.node_type]
        assert len(class_chunks) >= 3
        assert any(
            "point" in c.content and "distance" in c.content for c in class_chunks
        )
        assert any(
            "colored_point" in c.content and "inherit" in c.content
            for c in class_chunks
        )
        assert any("virtual shape" in c.content for c in class_chunks)


class TestOCamlContractCompliance:
    """Test ExtendedLanguagePluginContract compliance."""

    def test_implements_contract(self):
        """Verify OCamlPlugin implements ExtendedLanguagePluginContract."""
        assert issubclass(OCamlPlugin, ExtendedLanguagePluginContract)

    def test_get_semantic_chunks(self, tmp_path):
        """Test get_semantic_chunks method."""
        plugin = OCamlPlugin()

        # Create a simple OCaml file
        source = b"""let square x = x * x"""

        # Parse the source (mock tree-sitter node)

        parser = get_parser("ocaml")
        plugin.set_parser(parser)
        tree = parser.parse(source)

        chunks = plugin.get_semantic_chunks(tree.root_node, source)
        assert len(chunks) >= 1
        assert all("type" in chunk for chunk in chunks)
        assert all("start_line" in chunk for chunk in chunks)
        assert all("end_line" in chunk for chunk in chunks)
        assert all("content" in chunk for chunk in chunks)

    def test_get_chunk_node_types(self):
        """Test get_chunk_node_types method."""
        plugin = OCamlPlugin()
        node_types = plugin.get_chunk_node_types()

        assert isinstance(node_types, set)
        assert len(node_types) > 0
        assert "value_definition" in node_types or "let_binding" in node_types
        assert "type_definition" in node_types or "type_binding" in node_types
        assert "module_definition" in node_types or "module_binding" in node_types

    def test_should_chunk_node(self):
        """Test should_chunk_node method."""
        plugin = OCamlPlugin()

        # Mock nodes
        class MockNode:
            def __init__(self, node_type):
                self.type = node_type

        # Test chunk nodes
        assert plugin.should_chunk_node(MockNode("value_definition"))
        assert plugin.should_chunk_node(MockNode("let_binding"))
        assert plugin.should_chunk_node(MockNode("type_definition"))
        assert plugin.should_chunk_node(MockNode("module_definition"))
        assert plugin.should_chunk_node(MockNode("exception_definition"))
        assert plugin.should_chunk_node(MockNode("comment"))

        # Test non-chunk nodes
        assert not plugin.should_chunk_node(MockNode("identifier"))
        assert not plugin.should_chunk_node(MockNode("number"))
        assert not plugin.should_chunk_node(MockNode("constructor"))

    def test_get_node_context(self):
        """Test get_node_context method."""
        plugin = OCamlPlugin()

        # Mock node
        class MockNode:
            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        # Test let binding context
        node = MockNode("let_binding")
        context = plugin.get_node_context(node, b"let add x y = x + y")
        assert context is not None
        assert "let" in context

        # Test type context
        node = MockNode("type_definition")
        context = plugin.get_node_context(node, b"type color = Red | Blue")
        assert context is not None
        assert "type" in context


class TestOCamlEdgeCases:
    """Test edge cases in OCaml parsing."""

    def test_empty_ocaml_file(self, tmp_path):
        """Test empty OCaml file."""
        src = tmp_path / "empty.ml"
        src.write_text("")
        chunks = chunk_file(src, "ocaml")
        assert len(chunks) == 0

    def test_ocaml_with_only_comments(self, tmp_path):
        """Test OCaml file with only comments."""
        src = tmp_path / "comments.ml"
        src.write_text(
            """(* This is a comment *)
(* Another comment
   spanning multiple lines *)
(** Documentation comment *)
(*** Special comment ***)
""",
        )
        chunks = chunk_file(src, "ocaml")
        comment_chunks = [c for c in chunks if c.node_type == "comment"]
        assert len(comment_chunks) >= 1

    def test_ocaml_with_operators(self, tmp_path):
        """Test OCaml with custom operators."""
        src = tmp_path / "operators.ml"
        src.write_text(
            """(* Custom operators *)
let ( +. ) = (+.)
let ( *. ) = ( *. )

(* Prefix operators *)
let ( ~- ) = (~-)
let ( ~+ ) x = x

(* Infix operators *)
let ( |> ) x f = f x
let ( @@ ) f x = f x

(* Monadic operators *)
let ( >>= ) m f =
  match m with
  | None -> None
  | Some x -> f x

let ( >>| ) m f =
  match m with
  | None -> None
  | Some x -> Some (f x)

(* Using custom operators *)
let pipeline_example x =
  x
  |> (+) 1
  |> ( * ) 2
  |> string_of_int
""",
        )
        chunks = chunk_file(src, "ocaml")

        # Should capture operator definitions
        let_chunks = [c for c in chunks if "let" in c.content]
        assert any("|>" in c.content for c in let_chunks)
        assert any(">>=" in c.content for c in let_chunks)

    def test_ocaml_with_gadt(self, tmp_path):
        """Test OCaml with GADTs (Generalized Algebraic Data Types)."""
        src = tmp_path / "gadt.ml"
        src.write_text(
            """(* GADT example *)
type _ expr =
  | Int : int -> int expr
  | Bool : bool -> bool expr
  | Add : int expr * int expr -> int expr
  | Equal : 'a expr * 'a expr -> bool expr

(* Evaluation function using GADT *)
let rec eval : type a. a expr -> a = function
  | Int n -> n
  | Bool b -> b
  | Add (e1, e2) -> eval e1 + eval e2
  | Equal (e1, e2) -> eval e1 = eval e2

(* Type-safe printf using GADT *)
type (_, _) format =
  | Int : ('a, 'b) format -> (int -> 'a, 'b) format
  | String : ('a, 'b) format -> (string -> 'a, 'b) format
  | Lit : string * ('a, 'b) format -> ('a, 'b) format
  | End : ('a, 'a) format
""",
        )
        chunks = chunk_file(src, "ocaml")

        # Should capture GADT type definitions
        type_chunks = [c for c in chunks if "type" in c.node_type]
        assert any("expr" in c.content and "GADT" in c.content for c in chunks)
        assert any("format" in c.content for c in type_chunks)

    def test_ocaml_interface_file(self, tmp_path):
        """Test OCaml interface file (.mli)."""
        src = tmp_path / "stack.mli"
        src.write_text(
            """(* Stack interface *)
type 'a t

val empty : 'a t
val push : 'a -> 'a t -> 'a t
val pop : 'a t -> 'a * 'a t
val is_empty : 'a t -> bool
val size : 'a t -> int

(* Module type for comparable elements *)
module type ELEMENT = sig
  type t
  val compare : t -> t -> int
  val to_string : t -> string
end

(* Functor signature *)
module Make (E : ELEMENT) : sig
  type element = E.t
  type t

  val create : unit -> t
  val push : element -> t -> unit
  val pop : t -> element option
end
""",
        )
        chunks = chunk_file(src, "ocaml")

        # Should capture interface elements
        assert any("'a t" in c.content for c in chunks)
        assert any("ELEMENT" in c.content for c in chunks)
        assert any("Make" in c.content and "Functor" in c.content for c in chunks)
