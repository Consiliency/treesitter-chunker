# Parser concurrency

Tree-sitter parser instances are mutable and must not be used by more than one
thread at a time. Tree-sitter Chunker enforces that boundary in two ways.

- `get_parser(language)` returns a parser owned by the calling thread. Repeated
  calls from that thread reuse its parser, while another thread receives a
  different instance.
- `acquire_parser(language)` returns a context-manager lease. The parser is
  removed from the shared idle cache and pool until the lease exits.

Use a lease for short-lived parsing work:

```python
from chunker.parser import acquire_parser

with acquire_parser("python") as parser:
    tree = parser.parse(source.encode())
```

Existing callers of `return_parser()` remain valid, but it is intentionally a
no-op for thread-owned parser instances. Use a lease when a parser must be
returned to the shared idle pool.
