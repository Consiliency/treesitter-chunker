  You are enhancing Tree-sitter Chunker to serve an agentic programming platform.

  Goals:
  1) Add stable, byte-accurate spans and node IDs
     - For each chunk: file_id, symbol_id, start_byte, end_byte, start_line, end_line
     - node_id = sha1(path + language + ast_route + text_hash16)
  2) Expose chunk hierarchy + xref graph
     - Parent route (list of ancestor node_types)
     - Edges: defines, calls, imports, inherits, references (src_id, dst_id, type)
  3) Token awareness and packing hints
     - token_count(model="claude-3.5") per chunk
     - pack_hint: priority score for context packing (size/importance)
  4) Incremental re-index
     - Watch mode; only changed files; update nodes/edges/spans
  5) Postgres exporter
     - Tables: nodes(id, file, lang, symbol, kind, attrs jsonb)
               edges(src, dst, type, weight)
               spans(file_id, symbol_id, start_byte, end_byte)
     - Upsert by (id) with change_version
  6) GraphCut endpoint
     - Input: seeds[], radius, budget, rank weights (distance/publicness/hotspots)
     - Output: node_ids[], edges[] (minimal cut)
  7) Nearest-tests helper
     - For a set of symbols, return candidate test files + rationale

  API contracts (JSON):
  - POST /chunk/file { path, language? } -> { chunks: [CodeChunk] }
  - POST /export/postgres { repo_root, config } -> { rows_written }
  - POST /graph/xref { paths[] } -> { nodes[], edges[] }
  - POST /graph/cut { seeds[], params } -> { nodes[], edges[] }
  - POST /nearest-tests { symbols[] } -> { tests: [{path, score, symbols[]}] }

  Metrics:
  - timings per stage, cache hit rate, files/min, memory high-water

  Tests:
  - Span round-trip tests (apply slice == original text)
  - Deterministic node_id stability across runs
  - Large repo incremental update correctness