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

Incremental diffs and graph/export maps use `chunk_id`/`node_id` (the same
namespace). Boundary symbol indexes use the emitted boundary-node identity,
which prefers the unchanged `definition_id` contract when it is available.
