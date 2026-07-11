from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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

INSERT_EDGE = "INSERT INTO edges (src, dst, type, weight) VALUES (%s, %s, %s, %s)"

INSERT_SPAN = (
    "INSERT INTO spans (file_id, symbol_id, start_byte, end_byte) "
    "VALUES (%s, %s, %s, %s)"
)


def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def _allowed_dsn_hosts() -> set[str]:
    configured_hosts = os.environ.get(
        "TREE_SITTER_CHUNKER_POSTGRES_HOSTS",
        "localhost,127.0.0.1,::1",
    )
    return {
        host.strip().lower() for host in configured_hosts.split(",") if host.strip()
    }


def _validate_dsn(dsn: str) -> None:
    parsed = urlparse(dsn)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("Postgres DSN must use postgres or postgresql")
    if not parsed.hostname or parsed.hostname.lower() not in _allowed_dsn_hosts():
        raise ValueError("Postgres DSN host is not approved")
    # libpq honours host=/hostaddr= (and port) query parameters as the EFFECTIVE
    # destination, overriding the URI authority. Reject them so the allowlist on
    # the authority above cannot be bypassed (e.g. ...localhost/db?host=evil).
    from urllib.parse import parse_qs

    overriding = {"host", "hostaddr"}
    for key in parse_qs(parsed.query):
        if key.lower() in overriding:
            raise ValueError(
                f"Postgres DSN may not override the destination host via '{key}'"
            )


def _iter_files(repo_root: str, exts: set[str]) -> Iterable[Path]:
    root = Path(repo_root).resolve()
    for p in root.rglob("*"):
        # Skip anything reached via a symlink and anything that resolves outside
        # the export root, so a symlink planted inside repo_root cannot exfiltrate
        # files from elsewhere on disk (APISAFE follow-up).
        if p.is_symlink():
            continue
        resolved = p.resolve()
        if root != resolved and root not in resolved.parents:
            continue
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
        _validate_dsn(dsn)
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
    # Never follow a pre-existing symlink at the output path — it could redirect
    # the write to an arbitrary location outside repo_root (APISAFE follow-up).
    if output_sql.is_symlink():
        raise ValueError("Refusing to write export through a symlink")
    with output_sql.open("w", encoding="utf-8") as f:
        f.write(SCHEMA_DDL)
        for n in nodes:
            attrs_json = json.dumps(n.get("attrs") or {})
            f.write(
                "INSERT INTO nodes (id, file, lang, symbol, kind, attrs) VALUES ("
                f"{_sql_literal(n.get('id'))}, {_sql_literal(n.get('file'))}, "
                f"{_sql_literal(n.get('lang'))}, {_sql_literal(n.get('symbol'))}, "
                f"{_sql_literal(n.get('kind'))}, {_sql_literal(attrs_json)}::jsonb) "
                "ON CONFLICT (id) DO UPDATE SET "
                "change_version = nodes.change_version + 1, "
                "attrs = EXCLUDED.attrs;\n",
            )
        for e in edges:
            f.write(
                "INSERT INTO edges (src, dst, type, weight) VALUES ("
                f"{_sql_literal(e.get('src'))}, {_sql_literal(e.get('dst'))}, "
                f"{_sql_literal(e.get('type'))}, {float(e.get('weight', 1.0))});\n",
            )
        for s in spans:
            file_id, symbol_id, start_b, end_b = s
            f.write(
                "INSERT INTO spans (file_id, symbol_id, start_byte, end_byte) "
                "VALUES ("
                f"{_sql_literal(file_id)}, {_sql_literal(symbol_id)}, "
                f"{int(start_b)}, {int(end_b)});\n",
            )
    return len(nodes) + len(edges) + len(spans)
