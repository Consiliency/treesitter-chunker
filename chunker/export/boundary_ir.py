"""Boundary IR export helpers."""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any

from chunker.boundary import dumps_boundary_ir


def write_boundary_ir(
    ir: dict[str, Any],
    output: str | Path | IO[str],
    *,
    pretty: bool = False,
) -> None:
    """Write Boundary IR JSON to a path or text stream."""
    text = dumps_boundary_ir(ir, pretty=pretty)
    if isinstance(output, str | Path):
        Path(output).write_text(text, encoding="utf-8")
    else:
        output.write(text)


class BoundaryIRExporter:
    """Small exporter wrapper for Boundary IR dictionaries."""

    def export(
        self,
        ir: dict[str, Any],
        output: str | Path | IO[str],
        *,
        pretty: bool = False,
    ) -> None:
        write_boundary_ir(ir, output, pretty=pretty)

    def export_to_string(self, ir: dict[str, Any], *, pretty: bool = False) -> str:
        return dumps_boundary_ir(ir, pretty=pretty)
