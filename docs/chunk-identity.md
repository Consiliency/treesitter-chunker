# Chunk identity

Each extracted chunk has four related identifiers with separate roles:

| Field | Role | Seed or linkage |
| --- | --- | --- |
| `definition_id` | Content-insensitive structural identity for a named definition. | `sha1("def:" + file_path + "|" + language + "|" + qualified_route)` |
| `node_id` | Content-addressed occurrence identity used by graph nodes and id-keyed chunk maps. | `sha1(file_path + "|" + language + "|" + qualified_route + "|" + byte_start + "|" + content_hash)` |
| `chunk_id` | Back-compatible chunk-map key. | Always aliases `node_id`; both are 40-character SHA-1 values. |
| `parent_chunk_id` | Parent-child linkage. | The parent chunk's `chunk_id`. |

`qualified_route` includes definition names, such as
`class_definition:First/function_definition:__init__`. The byte offset keeps
otherwise identical anonymous siblings distinct. Changing content, moving a
chunk, or inserting text before it produces a new occurrence ID; a repeated
chunking run of unchanged source produces the same ID.

Incremental diffs match named definitions by `definition_id`, so a body-only
edit is a `MODIFIED` change rather than a delete-and-add pair. Graph/export
maps use `chunk_id`/`node_id` (the same namespace). Boundary symbol indexes
also prefer the emitted `definition_id` contract when it is available.

## Raw file newlines and the 6.0.0 migration

For valid UTF-8 files, regular `chunk_file` parsing preserves LF and CRLF bytes
instead of translating CRLF to LF. Byte spans and chunk content refer to that
source byte sequence. The existing identity algorithms are unchanged; LF chunk
identities remain unchanged. Previously normalized CRLF content and offsets
produce corrected occurrence IDs in 6.0.0. R Markdown snippet pseudo paths also
include source string offsets: CRLF preservation can change those paths and
their path-based structural IDs, including `definition_id`. Rechunk CRLF sources
and rebuild ID-based joins and parent links (treesitter-chunker#464).

Lone CR bytes are also preserved. CR-only Python parsing and line recovery are
not covered by the LF/CRLF contract: the raw parser reports errors and both
functions in the recorded CR-only fixture report line 1. Convert CR-only source
to LF when accurate line recovery is required until treesitter-chunker#471 is
resolved. Raw spans can end between CR and LF when the parser includes CR in a
token, such as a Python comment; source slicing still retains those exact bytes.

An explicit `identity_path` still determines regular chunk identities independently
of the physical read path. Invalid UTF-8 outside BAML retains replacement
decoding, which is lossy and does not promise raw-byte roundtrips. BAML decoding
remains strict. Language-specific transformations, such as R Markdown extraction,
and regular/streaming selection differences are separate contracts; this change
does not establish global API parity. CLI stdin retains text-stream newline
handling and is not certified as raw-byte-equivalent to file input.

Cached parallel processing has a separate cache-identity defect
(treesitter-chunker#358). Use `use_cache=False` until that repair is accepted;
newline preservation does not invalidate or repair existing cached payloads.

## Python selection migration for 6.0.0

Regular and streaming extraction select complete named Python lambda expressions
and exclude unnamed keyword leaves. Earlier versions also emitted keyword-only
`lambda` records. Regenerate Python chunk collections and remove those records
from downstream indexes when adopting 6.0.0 (treesitter-chunker#446). The identity
algorithm and IDs of retained chunks for the same source and file path are
unchanged. Regular extraction keeps its existing ignored-subtree rules.
Streaming honors those configured ignored-subtree boundaries too
(treesitter-chunker#466).

The two APIs preserve spans, contents, occurrence IDs, parents and routes for
the same-path Python lambda fixture. This does not certify all languages or
metadata fields; streaming language-specific transformation exceptions remain
documented in `chunker.streaming.StreamingChunker`.

## Streaming ignored-subtree migration for 6.0.0

Streaming traversal stops at the language configuration's ignored nodes, as
regular extraction does. In particular, Python strings and JavaScript/TypeScript
template strings do not contribute nested lambda or arrow-expression chunks.
Their enclosing function or variable chunks still retain the full source text,
including the ignored string. Visible expressions outside ignored subtrees keep
their contents, spans, parents, routes and occurrence IDs for unchanged source
at the same path (treesitter-chunker#466).

Earlier streaming output included those nested expressions. Regenerate affected
streaming and VFS collections and remove their extra records from downstream
indexes when adopting 6.0.0. Real fixture contracts compare the declared tuples
in both metadata modes for Python, JavaScript and TypeScript; they do not certify
every grammar, all metadata fields or language-specific span transformations.
Existing cached payloads are not invalidated: keep `use_cache=False` with
parallel helpers until treesitter-chunker#358 is resolved.
