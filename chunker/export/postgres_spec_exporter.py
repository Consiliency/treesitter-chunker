from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Tuple

from chunker.core import chunk_file
from chunker.graph.xref import build_xref

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS nodes (
  id TEXT PRIMARY KEY,
  file TEXT,
  lang TEXT,
  symbol TEXT,
  kind TEXT,
  attrs JSONB,
  change_version INT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS edges (
  src TEXT,
  dst TEXT,
  type TEXT,
  weight NUMERIC DEFAULT 1
);

CREATE TABLE IF NOT EXISTS spans (
  file_id TEXT,
  symbol_id TEXT,
  start_byte INT,
  end_byte INT
);
"""


UPSERT_NODE = (
    "INSERT INTO nodes (id, file, lang, symbol, kind, attrs) "
    "VALUES (%s, %s, %s, %s, %s, %s) "
    "ON CONFLICT (id) DO UPDATE SET "
    "change_version = nodes.change_version + 1, "
    "attrs = EXCLUDED.attrs"
)

INSERT_EDGE = (
    "INSERT INTO edges (src, dst, type, weight) VALUES (%s, %s, %s, %s)"
)

INSERT_SPAN = (
    "INSERT INTO spans (file_id, symbol_id, start_byte, end_byte) "
    "VALUES (%s, %s, %s, %s)"
)


def _iter_files(repo_root: str, exts: set[str]) -> Iterable[Path]:
    root = Path(repo_root)
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def _collect_chunks(repo_root: str) -> list:
    # basic language mapping by file extension
    lang_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
    }
    chunks = []
    for path in _iter_files(repo_root, set(lang_map.keys())):
        language = lang_map.get(path.suffix.lower())
        if language:
            try:
                chunks.extend(chunk_file(str(path), language))
            except Exception:
                continue
    return chunks


def _rows_for_nodes_edges_spans(chunks: list) -> tuple[list, list, list]:
    nodes, edges = build_xref(chunks)
    spans = []
    for c in chunks:
        spans.append(
            [
                getattr(c, "file_id", ""),
                getattr(c, "symbol_id", None),
                getattr(c, "byte_start", 0),
                getattr(c, "byte_end", 0),
            ],
        )
    return nodes, edges, spans


def export(repo_root: str, config: dict[str, Any] | None = None) -> int:
    """
    Export nodes, edges, spans from a repository to Postgres.

    If config contains a DSN under key "dsn", use psycopg to connect and
    write directly. Otherwise, write a .sql file next to the repo root and
    return approximate rows written.
    """
    config = config or {}
    chunks = _collect_chunks(repo_root)
    nodes, edges, spans = _rows_for_nodes_edges_spans(chunks)

    dsn = config.get("dsn")
    if dsn:
        try:
            import psycopg
        except Exception as e:  # pragma: no cover - optional dependency
            raise RuntimeError("psycopg not installed for direct DB export") from e

        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                # ensure schema
                cur.execute(SCHEMA_DDL)
                # upsert nodes
                for n in nodes:
                    cur.execute(
                        UPSERT_NODE,
                        (
                            n.get("id"),
                            n.get("file"),
                            n.get("lang"),
                            n.get("symbol"),
                            n.get("kind"),
                            json.dumps(n.get("attrs") or {}),
                        ),
                    )
                # insert edges
                for e in edges:
                    cur.execute(
                        INSERT_EDGE,
                        (
                            e.get("src"),
                            e.get("dst"),
                            e.get("type"),
                            float(e.get("weight", 1.0)),
                        ),
                    )
                # insert spans
                for s in spans:
                    cur.execute(INSERT_SPAN, tuple(s))
            conn.commit()
        return len(nodes) + len(edges) + len(spans)

    # Fallback: generate SQL file
    output_sql = Path(repo_root) / "chunker_export.sql"
    with output_sql.open("w", encoding="utf-8") as f:
        f.write(SCHEMA_DDL)
        for n in nodes:
            attrs_json = json.dumps(n.get("attrs") or {}).replace("'", "''")
            f.write(
                "INSERT INTO nodes (id, file, lang, symbol, kind, attrs) VALUES ("
                f"'{n.get('id')}', '{n.get('file')}', '{n.get('lang')}', "
                f"'{n.get('symbol')}', '{n.get('kind')}', "
                f"'{attrs_json}'::jsonb) ON CONFLICT (id) DO UPDATE SET "
                "change_version = nodes.change_version + 1, "
                "attrs = EXCLUDED.attrs;\n",
            )
        for e in edges:
            f.write(
                "INSERT INTO edges (src, dst, type, weight) VALUES ("
                f"'{e.get('src')}', '{e.get('dst')}', "
                f"'{e.get('type')}', {float(e.get('weight', 1.0))});\n",
            )
        for s in spans:
            file_id, symbol_id, start_b, end_b = s
            sym_val = f"'{symbol_id}'" if symbol_id else "NULL"
            f.write(
                "INSERT INTO spans (file_id, symbol_id, start_byte, end_byte) "
                "VALUES ("
                f"'{file_id}', {sym_val}, {int(start_b)}, {int(end_b)});\n",
            )
    return len(nodes) + len(edges) + len(spans)
