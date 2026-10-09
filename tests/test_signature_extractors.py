"""Signature metadata for methods and member declarations across languages.

Each case parses real source with the locked grammar and checks the public
chunk metadata (``signature`` and the formatted ``signature_text``) plus, where
noted, the Boundary IR ``signature`` field. The named faults guard specific
regressions:

* Go (treesitter-chunker#352): identifier-only name lookup, the receiver list
  read as arguments, and an omitted or truncated result list.
* Rust (treesitter-chunker#367): an omitted ``&self`` receiver and an omitted
  ``-> return`` type.
* C++ (treesitter-chunker#353): an in-class member declaration (a
  ``field_declaration`` with a ``function_declarator``) left unsigned, and a
  return type that absorbs ``virtual``/``static`` specifiers.
* Java, C#, Kotlin, Swift, PHP and Ruby (treesitter-chunker#354): no
  registered extractor, so every method and function had ``signature: null``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import chunker
from chunker.core import chunk_text
from chunker.metadata import MetadataExtractorFactory
from chunker.parser import get_parser


def _signed(code: str, language: str) -> dict[str, dict]:
    """Map signature name -> chunk metadata for every signed chunk."""
    chunks = chunk_text(
        code,
        language,
        extract_metadata=True,
        include_retrieval_metadata=True,
    )
    out: dict[str, dict] = {}
    for chunk in chunks:
        signature = chunk.metadata.get("signature")
        if signature:
            out[signature["name"]] = chunk.metadata
    return out


def _boundary_signatures(tmp_path: Path, filename: str, code: str) -> dict:
    path = tmp_path / filename
    path.write_text(code, encoding="utf-8")
    ir = chunker.extract_boundary_ir(
        str(tmp_path), canonical=True, include_timings=False
    )
    return {
        node["qualified_name"]: node["signature"]
        for node in ir["nodes"]
        if node.get("signature")
    }


# --------------------------------------------------------------------------- #
# Go (treesitter-chunker#352)
# --------------------------------------------------------------------------- #

GO_ISSUE_352 = """package gateway

type Gateway struct{}
func (g *Gateway) Dispatch(id string) (string, error) { return "", nil }
"""


def test_go_method_signature_issue_352_repro():
    signed = _signed(GO_ISSUE_352, "go")
    metadata = signed["Dispatch"]
    signature = metadata["signature"]
    # Fault: identifier-only name lookup returned None for field_identifier.
    assert signature["name"] == "Dispatch"
    # Fault: the receiver list was read as the argument list.
    assert signature["parameters"] == ["id string"]
    assert signature["receiver"] == "g *Gateway"
    assert "method" in signature["modifiers"]
    # Fault: the result list was omitted (or had its parentheses stripped).
    assert signature["return_type"] == "(string, error)"
    assert metadata["signature_text"] == "Dispatch(id string) -> (string, error)"


def test_go_method_value_receiver_single_result():
    code = """package handler

type Handler struct{ Name string }

func (h Handler) Dispatch(toolId string) string {
\treturn toolId
}
"""
    metadata = _signed(code, "go")["Dispatch"]
    assert metadata["signature"]["receiver"] == "h Handler"
    assert metadata["signature_text"] == "Dispatch(toolId string) -> string"


def test_go_function_signature_keeps_result_and_has_no_receiver():
    code = """package handler

func Label(value string) string { return value }
func Pair(a, b int, s ...string) (n int, err error) { return 0, nil }
func Nothing() {}
"""
    signed = _signed(code, "go")
    assert signed["Label"]["signature_text"] == "Label(value string) -> string"
    assert "receiver" not in signed["Label"]["signature"]
    assert signed["Label"]["signature"]["modifiers"] == []
    assert signed["Pair"]["signature"]["parameters"] == ["a, b int", "s ...string"]
    assert signed["Pair"]["signature"]["return_type"] == "(n int, err error)"
    assert signed["Nothing"]["signature_text"] == "Nothing()"


def test_go_method_signature_in_boundary_ir(tmp_path):
    signatures = _boundary_signatures(tmp_path, "gateway.go", GO_ISSUE_352)
    assert signatures["Dispatch"] == "Dispatch(id string) -> (string, error)"


# --------------------------------------------------------------------------- #
# Rust (treesitter-chunker#367)
# --------------------------------------------------------------------------- #

RUST_ISSUE_367 = """struct Gateway;

impl Gateway {
    pub fn dispatch(&self, id: &str) -> String { String::new() }
}
"""


def test_rust_impl_method_issue_367_repro():
    metadata = _signed(RUST_ISSUE_367, "rust")["dispatch"]
    signature = metadata["signature"]
    # Fault: the receiver is omitted from the parameter list.
    assert signature["parameters"] == ["&self", "id: &str"]
    assert signature["receiver"] == "&self"
    # Fault: the return type is omitted.
    assert signature["return_type"] == "String"
    assert signature["modifiers"] == ["pub"]
    assert metadata["signature_text"] == "dispatch(&self, id: &str) -> String"


def test_rust_receiver_forms_and_free_functions():
    code = """struct S;

impl S {
    fn len(&self) -> usize { 0 }
    fn push(&mut self, v: u32) {}
    fn take(self) -> Result<(), std::io::Error> { Ok(()) }
    fn new() -> Self { S }
}

pub fn label(value: &str) -> String { value.to_string() }
"""
    signed = _signed(code, "rust")
    assert signed["len"]["signature_text"] == "len(&self) -> usize"
    assert signed["push"]["signature"]["receiver"] == "&mut self"
    assert signed["push"]["signature_text"] == "push(&mut self, v: u32)"
    assert signed["take"]["signature"]["return_type"] == "Result<(), std::io::Error>"
    assert signed["take"]["signature"]["receiver"] == "self"
    assert signed["new"]["signature_text"] == "new() -> Self"
    assert "receiver" not in signed["new"]["signature"]
    assert signed["label"]["signature_text"] == "label(value: &str) -> String"
    assert "receiver" not in signed["label"]["signature"]


# --------------------------------------------------------------------------- #
# C++ (treesitter-chunker#353)
# --------------------------------------------------------------------------- #

CPP_ISSUE_353 = """#include <string>

class Gateway {
 public:
  std::string dispatch(const std::string& id);
};
"""


def test_cpp_member_declaration_issue_353_repro():
    metadata = _signed(CPP_ISSUE_353, "cpp")["dispatch"]
    signature = metadata["signature"]
    assert signature["parameters"] == ["const std::string& id"]
    assert signature["return_type"] == "std::string"
    assert signature["modifiers"] == []
    assert "receiver" not in signature
    assert (
        metadata["signature_text"] == "dispatch(const std::string& id) -> std::string"
    )


def test_cpp_member_declaration_qualifiers():
    code = """class Base {
 public:
  virtual std::string invoke(const std::string& id) = 0;
  virtual int size() const override;
  static Base* make(int n) noexcept;
  const char* name() const;
  bool operator==(const Base& other) const;
};
"""
    signed = _signed(code, "cpp")
    invoke = signed["invoke"]["signature"]
    assert invoke["return_type"] == "std::string"
    assert invoke["modifiers"] == ["virtual", "pure"]
    size = signed["size"]["signature"]
    assert size["return_type"] == "int"
    assert size["modifiers"] == ["virtual", "const", "override"]
    make = signed["make"]["signature"]
    assert make["return_type"] == "Base*"
    assert make["parameters"] == ["int n"]
    assert make["modifiers"] == ["static", "noexcept"]
    assert signed["name"]["signature"]["return_type"] == "const char*"
    assert signed["name"]["signature"]["modifiers"] == ["const"]
    assert signed["operator=="]["signature_text"] == (
        "operator==(const Base& other) -> bool"
    )


def test_cpp_data_members_stay_unsigned():
    code = """class Holder {
 public:
  std::string field;
  int (*callback)(int);
};
"""
    assert _signed(code, "cpp") == {}


def test_c_function_pointer_field_stays_unsigned():
    code = """struct Ops {
    int (*cb)(int);
    int count;
};
"""
    assert _signed(code, "c") == {}


def test_cpp_definitions_unchanged_by_member_declarations():
    code = """std::string label(int value) {
    return std::to_string(value);
}
"""
    metadata = _signed(code, "cpp")["label"]
    assert metadata["signature_text"] == "label(int value) -> std::string"


# --------------------------------------------------------------------------- #
# Java, C#, Kotlin, Swift, PHP and Ruby (treesitter-chunker#354)
# --------------------------------------------------------------------------- #

SIGNATURE_CASES = {
    "java": (
        """package tool;

class Gateway {
    public Gateway(int x, String... rest) {}

    @Override
    public static <T> java.util.List<T> collect(final String id, int[] xs)
            throws Exception { return null; }

    public String dispatch(String id) { return id; }

    void run() {}
}
""",
        {
            "Gateway": ("Gateway(int x, String... rest)", ["public"], [], None),
            "collect": (
                "collect(final String id, int[] xs) -> java.util.List<T>",
                ["public", "static"],
                ["@Override"],
                None,
            ),
            "dispatch": ("dispatch(String id) -> String", ["public"], [], None),
            "run": ("run() -> void", [], [], None),
        },
    ),
    "csharp": (
        """namespace Tool;

class Gateway {
    public string Dispatch(string id) { return id; }

    [Obsolete]
    public static async Task<List<int>> Go(ref int a, string s = "x", params int[] r)
    { return null; }

    void Run() {}
}
""",
        {
            "Dispatch": ("Dispatch(string id) -> string", ["public"], [], None),
            "Go": (
                'Go(ref int a, string s = "x", params int[] r) -> Task<List<int>>',
                ["public", "static", "async"],
                ["[Obsolete]"],
                None,
            ),
            "Run": ("Run() -> void", [], [], None),
        },
    ),
    "kotlin": (
        """package tool

class Gateway {
    fun dispatch(id: String): String {
        return id
    }

    @JvmStatic
    suspend fun <T> String.go(a: Int = 1, vararg xs: T) {}

    fun twice(x: Int) = x * 2
}
""",
        {
            "dispatch": ("dispatch(id: String) -> String", [], [], None),
            "go": (
                "go(a: Int = 1, vararg xs: T)",
                ["suspend"],
                ["@JvmStatic"],
                "String",
            ),
            "twice": ("twice(x: Int)", [], [], None),
        },
    ),
    "swift": (
        """class Gateway {
    func dispatch(id: String) -> String {
        return id
    }

    @discardableResult
    static func go(_ a: Int, with b: inout [String: Int], c: Int = 3) async throws -> (Int, String) {
        return (a, "")
    }

    func run() {}
}
""",
        {
            "dispatch": ("dispatch(id: String) -> String", [], [], None),
            "go": (
                "go(_ a: Int, with b: inout [String: Int], c: Int = 3) -> (Int, String)",
                ["static", "async", "throws"],
                ["@discardableResult"],
                None,
            ),
            "run": ("run()", [], [], None),
        },
    ),
    "php": (
        """<?php
namespace Tool;

class Gateway {
    public function dispatch(string $id): string {
        return $id;
    }

    #[Pure]
    public static function go(?string $id, array &$opts = ['a' => 1], int ...$rest): ?string {
        return $id;
    }
}

function helper($a, $b = 2) { return $a; }
""",
        {
            "dispatch": ("dispatch(string $id) -> string", ["public"], [], None),
            "go": (
                "go(?string $id, array &$opts = ['a' => 1], int ...$rest) -> ?string",
                ["public", "static"],
                ["#[Pure]"],
                None,
            ),
            "helper": ("helper($a, $b = 2)", [], [], None),
        },
    ),
    "ruby": (
        """module Tool
  class Gateway
    def dispatch(id)
      id
    end

    def self.make(a, b = 1, *rest, c:, d: 2, **opts, &blk)
    end

    def run
    end

    def bare a, b
    end
  end
end
""",
        {
            "dispatch": ("dispatch(id)", [], [], None),
            "make": (
                "make(a, b = 1, *rest, c:, d: 2, **opts, &blk)",
                [],
                [],
                "self",
            ),
            "run": ("run()", [], [], None),
            "bare": ("bare(a, b)", [], [], None),
        },
    ),
}


@pytest.mark.parametrize("language", sorted(SIGNATURE_CASES))
def test_issue_354_language_signatures(language):
    code, expected = SIGNATURE_CASES[language]
    signed = _signed(code, language)
    # Fault: no registered extractor, so no chunk carried a signature.
    assert set(signed) == set(expected)
    for name, (text, modifiers, decorators, receiver) in expected.items():
        metadata = signed[name]
        signature = metadata["signature"]
        assert metadata["signature_text"] == text, name
        assert signature["modifiers"] == modifiers, name
        assert signature["decorators"] == decorators, name
        assert signature.get("receiver") == receiver, name


@pytest.mark.parametrize("language", sorted(SIGNATURE_CASES))
def test_issue_354_extractors_add_only_signatures(language):
    code, _expected = SIGNATURE_CASES[language]
    chunks = chunk_text(code, language, extract_metadata=True)
    for chunk in chunks:
        assert "calls" not in chunk.metadata
        assert "call_spans" not in chunk.metadata
        assert "imports" not in chunk.metadata
        assert "exports" not in chunk.metadata
        assert "docstring" not in chunk.metadata
        assert chunk.metadata["dependencies"] == []
    assert MetadataExtractorFactory.is_supported(language)


def test_csharp_alias_uses_csharp_extractor():
    extractor = MetadataExtractorFactory.create_extractor("c_sharp")
    assert type(extractor).__name__ == "CSharpMetadataExtractor"


def test_swift_protocol_function_declaration_signature():
    source = b"protocol ToolPort {\n    func invoke(id: String) -> String\n}\n"
    tree = get_parser("swift").parse(source)
    extractor = MetadataExtractorFactory.create_extractor("swift")
    assert extractor is not None

    def find(node):
        if node.type == "protocol_function_declaration":
            return node
        for child in node.children:
            found = find(child)
            if found is not None:
                return found
        return None

    requirement = find(tree.root_node)
    assert requirement is not None
    signature = extractor.extract_signature(requirement, source)
    assert signature is not None
    assert signature.name == "invoke"
    assert signature.parameters == ["id: String"]
    assert signature.return_type == "String"


@pytest.mark.parametrize(
    ("filename", "code", "expected"),
    [
        (
            "Gateway.java",
            SIGNATURE_CASES["java"][0],
            {"Gateway.dispatch": "dispatch(String id) -> String"},
        ),
        (
            "gateway.rb",
            SIGNATURE_CASES["ruby"][0],
            {"Tool.Gateway.dispatch": "dispatch(id)"},
        ),
    ],
)
def test_issue_354_boundary_ir_signatures(tmp_path, filename, code, expected):
    signatures = _boundary_signatures(tmp_path, filename, code)
    for qualified_name, text in expected.items():
        assert signatures[qualified_name] == text
