# BAML grammar companion for treesitter-chunker

This optional package provides a pinned Tree-sitter BAML grammar through a Python
`language()` capsule. It is separate from the universal `treesitter-chunker`
wheel so projects that do not use BAML do not install a native extension.

The grammar comes from BoundaryML's read-only `baml-treesitter` mirror at the
commit recorded in `pin.json`. `overlay.patch` makes one source change:
`prompt_field` accepts the grammar's existing `backtick_string` production as
well as `raw_string`. This preserves the original source bytes, including
interpolation and line endings. The overlay is temporary until the upstream
BAML grammar accepts this prompt form. The package still needs a separate
distribution until `treesitter-chunker` deliberately adopts an upstream BAML
grammar in its pinned language pack.

```python
from tree_sitter import Language, Parser
from treesitter_chunker_baml_grammar import language

parser = Parser(Language(language()))
tree = parser.parse(b"function greet() -> string { prompt: `Hello` }")
assert not tree.root_node.has_error
```

The source distribution needs a C compiler at installation time. The wheel
workflow builds `cp311-abi3` wheels for Linux glibc x86_64/aarch64, macOS
x86_64/arm64, and Windows x86_64 and tests them on Python 3.11–3.13. Other
platforms use the source distribution until a wheel is tested there. Run
`python scripts/check_baml_grammar.py` to verify vendored hashes offline;
explicit regeneration requires the pinned `tree-sitter-cli` executable.

## Feasibility evidence

At the pinned mirror commit, the unmodified grammar rejected the BAML 0.20.1
backtick `prompt:` form. The one-rule overlay generated an ABI-15 parser with
Tree-sitter CLI 0.25.10 without a conflict or warning. All 65 upstream corpus
cases passed. The focused fixtures cover the release example, old raw prompts,
multiline and block interpolation, adjacent declarations, bigints, generics,
Unicode, CRLF, and every initial declaration kind. They parse without `ERROR`
or `MISSING` nodes. Tests check original byte spans for prompt delimiters,
interpolations, and CRLF declarations. `pin.json` records the upstream source,
overlay, generator executable, and generated output SHA-256 values.

`implements_for_declaration` exposes `interface` and `target` fields but no
`name` field. The chunker integration must derive its stable symbol from those
fields; the grammar package preserves both spans.
