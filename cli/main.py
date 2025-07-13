from __future__ import annotations
import json
from pathlib import Path
from typing import Optional, List

import typer
from rich import print

from chunker import chunk_file
from chunker.exporters import ParquetExporter

app = typer.Typer(help="Tree‑sitter‑based code‑chunker CLI")

@app.command()
def chunk(
    file: Path = typer.Argument(..., exists=True, readable=True),
    language: str = typer.Option(..., "--lang", "-l", help="Language name (e.g. python)"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON instead of Rich table"),
    parquet_out: Optional[Path] = typer.Option(None, "--parquet", "-p", help="Output to Parquet file"),
    parquet_columns: Optional[List[str]] = typer.Option(None, "--columns", "-c", help="Columns to include in Parquet output"),
    parquet_partition: Optional[List[str]] = typer.Option(None, "--partition", help="Columns to partition by"),
    parquet_compression: str = typer.Option("snappy", "--compression", help="Parquet compression (snappy, gzip, brotli, lz4, zstd)"),
):
    """Chunk a single source file."""
    chunks = chunk_file(file, language)
    
    if parquet_out:
        exporter = ParquetExporter(
            columns=parquet_columns,
            partition_by=parquet_partition,
            compression=parquet_compression
        )
        exporter.export(chunks, parquet_out)
        print(f"[green]✓[/green] Exported {len(chunks)} chunks to {parquet_out}")
    elif json_out:
        print(json.dumps([c.__dict__ for c in chunks], indent=2))
    else:
        from rich.table import Table
        tbl = Table(title=f"Chunks in {file}")
        tbl.add_column("#", justify="right")
        tbl.add_column("Node")
        tbl.add_column("Lines")
        tbl.add_column("Parent")
        for i, c in enumerate(chunks, 1):
            tbl.add_row(str(i), c.node_type, f"{c.start_line}-{c.end_line}", c.parent_context)
        print(tbl)

if __name__ == "__main__":
    app()
