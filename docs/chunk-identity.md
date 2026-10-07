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
produce corrected occurrence IDs in 6.0.0. Rechunk CRLF sources and rebuild
ID-based joins and parent links (treesitter-chunker#464).

An explicit `identity_path` still determines regular chunk identities independently
of the physical read path. Invalid UTF-8 outside BAML retains replacement
decoding, which is lossy and does not promise raw-byte roundtrips. BAML decoding
remains strict. Language-specific transformations, such as R Markdown extraction,
and regular/streaming selection differences are separate contracts; this change
does not establish global API parity.

Cached parallel processing has a separate cache-identity defect
(treesitter-chunker#358). Use `use_cache=False` until that repair is accepted;
newline preservation does not invalidate or repair existing cached payloads.
