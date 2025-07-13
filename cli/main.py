from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

import typer
from rich import print

from chunker import chunk_file
from chunker.export import JSONExporter, JSONLExporter, SchemaType

app = typer.Typer(help="Tree‑sitter‑based code‑chunker CLI")

@app.command()
def chunk(
    file: Path = typer.Argument(..., exists=True, readable=True),
    language: str = typer.Option(..., "--lang", "-l", help="Language name (e.g. python)"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON instead of Rich table"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, jsonl"),
    schema: str = typer.Option("flat", "--schema", "-s", help="JSON schema type: flat, nested, minimal, full"),
    compress: bool = typer.Option(False, "--compress", "-c", help="Compress output with gzip"),
):
    """Chunk a single source file."""
    chunks = chunk_file(file, language)
    
    # Handle different output formats
    if format == "table" and not json_out:
        from rich.table import Table
        tbl = Table(title=f"Chunks in {file}")
        tbl.add_column("#", justify="right")
        tbl.add_column("ID")
        tbl.add_column("Node")
        tbl.add_column("Lines")
        tbl.add_column("Parent")
        for i, c in enumerate(chunks, 1):
            tbl.add_row(
                str(i), 
                c.chunk_id[:8] + "...", 
                c.node_type, 
                f"{c.start_line}-{c.end_line}", 
                c.parent_context
            )
        print(tbl)
    elif format == "json" or json_out:
        schema_type = SchemaType[schema.upper()]
        exporter = JSONExporter(schema_type)
        
        if output:
            exporter.export(chunks, output, compress=compress)
            print(f"[green]✓[/green] Exported {len(chunks)} chunks to {output}")
        else:
            print(exporter.export_to_string(chunks))
    elif format == "jsonl":
        schema_type = SchemaType[schema.upper()]
        exporter = JSONLExporter(schema_type)
        
        if output:
            exporter.export(chunks, output, compress=compress)
            print(f"[green]✓[/green] Exported {len(chunks)} chunks to {output}")
        else:
            # For stdout, write directly
            import sys
            exporter.export(chunks, sys.stdout)
    else:
        print(f"[red]Error:[/red] Unknown format: {format}")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
