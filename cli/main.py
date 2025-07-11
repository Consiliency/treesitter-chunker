from __future__ import annotations
import json
from pathlib import Path

import typer
from rich import print

from chunker import chunk_file

app = typer.Typer(help="Tree‑sitter‑based code‑chunker CLI")

@app.command()
def chunk(
    file: Path = typer.Argument(..., exists=True, readable=True),
    language: str = typer.Option(..., "--lang", "-l", help="Language name (e.g. python)"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON instead of Rich table"),
):
    """Chunk a single source file."""
    chunks = chunk_file(file, language)
    if json_out:
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
