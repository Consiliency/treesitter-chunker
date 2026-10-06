# Performance Guide

Correctness tests compare repeated streaming output with eager fixture parsing.
They do not enforce wall-clock variance on shared hosts. The existing streaming
benchmark records per-file timing samples and variance in seconds squared as
informational metadata; its duration is the sum of per-file means for one logical
pass. Run performance
comparisons under controlled host load, and keep those observations separate
from content, ordering and line-bound correctness.

Performance depends on source size, language, grammar availability, storage and
worker count. Measure your workload; this guide makes no fixed speedup or memory
multiplier claim.

## Large-file quality check

The large-file test parses 5,000 generated Python functions in an isolated
process and checks their actual JSON export: complete ordered contents,
distinct IDs, kinds and file attribution. It keeps the existing 500 MiB
post-chunk RSS limit. RSS is sampled after chunking; it is not peak memory.
These checks run before timing is considered. Default correctness runs report
chunk/export times without classifying slow covered execution as wrong output.

For an explicit controlled check, prefetch Python, use a quiet host, disable
coverage and run:

```bash
CHUNKER_CONTROLLED_PERFORMANCE=1 uv run --locked --all-extras pytest tests/test_performance_advanced.py::TestScalabilityLimits::test_very_large_file_handling --no-cov -q -s
```

This retains the existing targets: chunking below ten seconds, JSON export
below five seconds, and post-chunk RSS below 500 MiB. The command reports both
timing failures together and rejects active coverage for controlled timing.
Measurements include host CPU use before the workload; retain them with the
source/environment snapshot. Passing this workload is not a throughput
guarantee for other inputs or machines.

## Parser reuse

`get_parser(language)` reuses a parser owned by the calling thread. It does not
cache a file's extracted chunks. For exclusive temporary parsing, use
`acquire_parser(language)` as a context manager. See [parser concurrency](performance-guide/parser-concurrency.md).

Prefetch the grammars you need before measuring so network downloads do not
obscure parsing costs:

```bash
python -c "import tree_sitter_language_pack as p; p.prefetch(['python', 'javascript'])"
```

## AST Caching

The publicly exported `ASTCache` stores **chunk lists in SQLite**, rather than
live Tree-sitter AST objects. `chunk_file()` does not consult this cache
automatically. The parallel APIs enable caching by default (`use_cache=True`)
at `~/.cache/treesitter-chunker/ast_cache.db`. Their helpers do not accept a
custom cache directory. Use `use_cache=False` unless you manage invalidation.

```python
from pathlib import Path
from chunker import ASTCache, chunk_file

path = Path("example.py").resolve()
cache = ASTCache(cache_dir=Path(".cache/chunks"))
chunks = cache.get_cached_chunks(path, "python")
if chunks is None:
    chunks = chunk_file(path, "python")
    cache.cache_chunks(path, "python", chunks)
print(cache.get_cache_stats())
# Invalidate a file, or omit the argument to invalidate all cached entries.
cache.invalidate_cache(path)
```

Statistics contain `total_files`, `total_size_bytes` and `cache_db_size`; there
are no hit-rate counters, `max_size` constructor argument, TTL or LRU eviction.
Cache validation checks the file's hash and modification time. This cache does
not key entries by grammar/runtime version or extraction options; invalidate
it when those change, including when switching core/streaming extraction.
The private-directory example above applies to explicit `ASTCache` use; it
does not redirect the parallel helpers' shared default cache.
The extraction-mode/pin cache gap is tracked in
[treesitter-chunker#358](https://github.com/Consiliency/treesitter-chunker/issues/358).

## Incremental Boundary IR

Boundary IR has a separate persistent cache:

```bash
treesitter-chunker boundary src/ --lang python --incremental --cache-dir .cache/boundary > boundary.json
treesitter-chunker boundary src/ --lang python --incremental --cache-dir .cache/boundary > boundary.json
treesitter-chunker boundary src/ --lang python --incremental --cache-dir .cache/boundary --force-rebuild
```

Cold runs populate records. Warm runs reuse valid records and recompute changed
files and impacted neighbors. Keys include content, language, grammar/runtime
fingerprint, tool/schema versions and extraction options. Malformed records
are recomputed. Without `--include-timings`, output for an unchanged snapshot
remains canonical and identical between cold and warm runs. Cache statistics
are excluded from stdout JSON.

## Parallel Processing

The Python parallel APIs use a process pool. Use `num_workers`, not
`max_workers`, and `extensions`, not a glob `pattern`. Results map `Path`
objects to lists of chunks. Put calls behind a main guard for platforms that
start workers by importing the script.

Save this as `parallel_example.py` and run it with files under `src/`:

```python
from chunker.parallel import chunk_directory_parallel, chunk_files_parallel

if __name__ == "__main__":
    results = chunk_files_parallel(
        ["example.py"], "python", num_workers=2, use_cache=False
    )
    directory_results = chunk_directory_parallel(
        "src/", "python", extensions=[".py"], num_workers=2, use_cache=False
    )
    for path, chunks in directory_results.items():
        print(path, len(chunks))
```

`chunker.chunk_directory` aliases `chunk_directory_parallel`. Default extensions
come from language mappings. Worker failures can appear as empty chunk lists;
inspect reported errors before treating results as complete. Parallelism has
startup and serialization costs and may be slower for small workloads.

The CLI `batch --parallel N` uses threads; it is a different interface from the
Python process-pool helpers. See [CLI Reference](cli-reference.md).

## Streaming Large Files

```python
from chunker import chunk_file_streaming

for chunk in chunk_file_streaming("example.py", "python"):
    print(chunk.node_type, chunk.start_line, chunk.end_line)
```

Streaming yields chunks lazily and memory-maps the source, but still parses a
whole syntax tree. It does not provide bounded-memory parsing, a read-buffer
`chunk_size` option, or arbitrary stream input. Turning its result into a list
retains all chunks in memory.

Streaming uses the core node-selection predicate, but does not repeat core's
per-language type/span rewrites, merged or synthesized chunks, or optional
metadata and file/definition/symbol identities. Types, spans and IDs can differ
(including C++ methods); CRLF handling can also differ. Treat the two outputs
as different extraction modes and compare real fixtures before switching.
Invalidate cached chunks when changing modes; do not mix their output in one
index assuming equivalence.

## Benchmarking

`benchmarks.benchmark.PerformanceBenchmark.run_all_benchmarks()` uses current
sequential and parallel APIs. Its cached benchmark explicitly reads and writes
SQLite chunk records: the cold pass includes lookup, parsing and population;
the warm pass counts a hit only when lookup returns cached chunks. It retains
one logical file/chunk count per pass. Durations and the observed cold/warm ratio
are informational, with no promised speedup. Cache identity limitations described
above still apply.

The default benchmark cache uses the shared home SQLite database. Running the
cached benchmark invalidates and rewrites records for its input paths, so it can
affect later cached parallel calls. Invalidate those records before switching
between core and streaming extraction; their modes are not distinguished by the
current cache identity (treesitter-chunker#358).

Run this from a directory containing `example.py`. It measures repeated direct
parsing, not SQLite cache hits:

```python
from importlib.metadata import version
from pathlib import Path
from statistics import median
from time import perf_counter
import platform
from chunker import chunk_file

path = Path("example.py")
chunk_file(path, "python")  # Warm grammar loading and parser initialization.
times = []
for _ in range(10):
    start = perf_counter()
    chunks = chunk_file(path, "python")
    times.append(perf_counter() - start)
print({
    "python": platform.python_version(),
    "platform": platform.platform(),
    "chunker": version("treesitter-chunker"),
    "tree_sitter": version("tree-sitter"),
    "grammar_pack": version("tree-sitter-language-pack"),
    "source_bytes": path.stat().st_size,
    "chunks": len(chunks),
    "median_seconds": median(times),
})
```

For comparisons, record the source snapshot, hardware, worker count, cache
state and output equivalence. Compare uncached sequential and parallel runs
with the parallel API's `use_cache=False`; sequential `chunk_file` does not accept
that option. Measure explicit caching separately. Record multiple runs
and peak resident memory; do not infer a speedup from a single warm run.
