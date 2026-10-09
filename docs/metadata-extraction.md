# Metadata Extraction

Core extraction adds metadata by default. Fields depend on the language, node
type and extractor: do not assume every chunk has a signature, docstring,
complexity record or import list. Call spans describe syntax, not resolved
runtime targets or a complete call graph.

## Basic Usage

```python
from chunker import chunk_text

code = 'def hello(name: str):\n    """Say hello."""\n    return print(name)\n'
chunks = chunk_text(code, "python")
for chunk in chunks:
    print(chunk.metadata.get("signature", {}))
    print(chunk.metadata.get("complexity", {}))
    print(chunk.metadata.get("docstring"))
    print(chunk.metadata.get("call_spans", []))
```

Disable optional metadata extraction when the consumer does not need it:

```python
chunks = chunk_text(code, "python", extract_metadata=False)
```

Chunk identity and extraction bookkeeping are separate from these optional
fields. See [chunk identity](chunk-identity.md).

## Signature Metadata

A `signature` record has `name`, `parameters`, `return_type`, `decorators` and
`modifiers`. `parameters` lists what is declared inside the parameter list,
in source order. A method whose grammar declares a receiver also carries
`receiver`: the Go receiver list (`g *Gateway`), which is never repeated in
`parameters`, or the Rust `self` parameter (`&self`), which stays in
`parameters` because it is written there. The key is absent when there is no receiver. Retrieval metadata
formats the record as `signature_text`, `name(parameters) -> return_type`,
with the return type text kept whole, such as Go's `(string, error)`.

## Call Span Contract

`call_spans` records have `name`, `start` and `end` keys, with optional
`function_start`, `function_end`, `arguments_start` and `arguments_end` offsets.
Offsets refer to the UTF-8 bytes **actually parsed**; ends are exclusive.
`chunk_text()` encodes the supplied string directly, so reading UTF-8 bytes and
decoding them explicitly preserves CRLF for byte slicing. Ordinary
`chunk_file()` reads with universal-newline conversion (and can replace invalid
UTF-8), so its offsets may differ from the original on-disk bytes. Slice the
same parsed source bytes, not a Unicode string or a differently normalized file.
There is no universal decoded argument list, call-type field or target binding.
Nested chunks may repeat a call; deduplicate by file and byte span for file
counts. See the [cookbook](cookbook.md#call-span-extraction-and-metadata-analysis).

## Extractors and Complexity Analyzers

The factory has specialized metadata extractors for Python, JavaScript,
TypeScript/JSX/TSX, Rust, Go and C/C++; specialized complexity analyzers cover
Python and JavaScript/TypeScript variants. Core call spans require a registered
extractor; branches for other languages in the abstract base class do not
register them automatically. Parser coverage and metadata completeness are
different questions. Inspect the registrations:

```python
from chunker.metadata import MetadataExtractorFactory

print(MetadataExtractorFactory.supported_languages())
extractor = MetadataExtractorFactory.create_extractor("python")
analyzer = MetadataExtractorFactory.create_analyzer("python")
```

Factory creation can return `None`. Extractor methods such as `extract_calls`
take `(tree_sitter.Node, source_bytes)`, not a `CodeChunk`. The abstract
`BaseMetadataExtractor` cannot be directly instantiated. For consumers, prefer
the metadata already attached to chunks.

Complexity metrics are static heuristics over syntax. They do not prove runtime
cost or behavior; the available measures and node handling vary by language.
Additional application classification should be tested on representative
fixtures and labeled as a heuristic.

## Extending Extraction

Implement the abstract extractor contracts, register the concrete class in
the existing factory, and use real parsing fixtures for signatures, docstrings,
calls and any optional fields you promise. Add a complexity analyzer only when
its separate contract is needed. Follow
[CONTRIBUTING.md](https://github.com/Consiliency/treesitter-chunker/blob/main/CONTRIBUTING.md).
