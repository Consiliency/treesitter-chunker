"""Structural query helpers over enriched chunk metadata."""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from .auto import ZeroConfigAPI
from .core import chunk_file
from .helpers.nearest_tests import nearest_tests
from .symbol_graph import collect_source_files


class SemanticQuery:
    """Query chunk-derived structure without performing retrieval or verification."""

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path)

    def function_exists(self, file_path: str | Path, name: str) -> dict[str, Any]:
        """Check whether a function or method exists in a file."""
        match = self._find_exact_symbol(
            file_path, name, {"function", "method", "constructor"}
        )
        if match is None:
            return {"exists": False, "name": name, "file": str(file_path)}
        return {"exists": True, **match}

    def class_exists(self, file_path: str | Path, name: str) -> dict[str, Any]:
        """Check whether a class-like symbol exists in a file."""
        match = self._find_exact_symbol(
            file_path,
            name,
            {"class", "interface", "struct", "enum", "trait", "type"},
        )
        if match is None:
            return {"exists": False, "name": name, "file": str(file_path)}
        return {"exists": True, **match}

    def find_symbols(
        self,
        pattern: str,
        kind: str | None = None,
        file_path: str | Path | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Find symbols matching a glob-style pattern across the repo or file."""
        matches: list[dict[str, Any]] = []
        for chunk in self._iter_symbol_chunks(file_path=file_path):
            metadata = chunk.metadata
            symbol = str(metadata.get("symbol") or "")
            qualified_name = str(metadata.get("qualified_name") or "")
            symbol_kind = str(metadata.get("kind") or "")
            if kind and symbol_kind != kind:
                continue
            if not (
                fnmatchcase(symbol, pattern)
                or (qualified_name and fnmatchcase(qualified_name, pattern))
            ):
                continue
            matches.append(self._chunk_result(chunk))
        matches.sort(key=lambda item: (item["file"], item["line"], item["name"]))
        return matches[:limit]

    def find_candidate_tests(
        self, file_path: str | Path, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Find likely related tests for a source file."""
        source_file = self._resolve_file(file_path)
        symbols = [
            chunk.metadata.get("symbol")
            for chunk in self._iter_symbol_chunks(file_path=source_file)
        ]
        symbol_names = [str(symbol) for symbol in symbols if symbol]
        if not symbol_names:
            symbol_names = [source_file.stem]
        results = nearest_tests(symbol_names, str(self.repo_path))
        return results[:limit]

    def find_tests_for(
        self, file_path: str | Path, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Alias for candidate-test discovery."""
        return self.find_candidate_tests(file_path, limit=limit)

    def _find_exact_symbol(
        self,
        file_path: str | Path,
        name: str,
        allowed_kinds: set[str],
    ) -> dict[str, Any] | None:
        for chunk in self._iter_symbol_chunks(file_path=file_path):
            metadata = chunk.metadata
            symbol = str(metadata.get("symbol") or "")
            qualified_name = str(metadata.get("qualified_name") or "")
            kind = str(metadata.get("kind") or "")
            if kind not in allowed_kinds:
                continue
            if (
                symbol == name
                or qualified_name == name
                or qualified_name.endswith(f".{name}")
            ):
                return self._chunk_result(chunk)
        return None

    def _iter_symbol_chunks(self, file_path: str | Path | None = None):
        if file_path is not None:
            files = [self._resolve_file(file_path)]
        else:
            files = collect_source_files(self.repo_path)
        for path in files:
            language = ZeroConfigAPI.EXTENSION_MAP.get(path.suffix.lower())
            if not language:
                continue
            try:
                chunks = chunk_file(
                    path,
                    language,
                    extract_metadata=True,
                    include_retrieval_metadata=True,
                )
            except (
                Exception
            ):  # pragma: no cover - parser availability varies by environment
                continue
            for chunk in chunks:
                if chunk.metadata.get("symbol") and chunk.metadata.get("kind"):
                    yield chunk

    def _resolve_file(self, file_path: str | Path) -> Path:
        candidate = Path(file_path)
        if candidate.is_absolute() and candidate.exists():
            return candidate
        repo_candidate = self.repo_path / candidate
        if repo_candidate.exists():
            return repo_candidate
        return candidate

    @staticmethod
    def _chunk_result(chunk) -> dict[str, Any]:
        metadata = chunk.metadata
        return {
            "name": metadata.get("symbol"),
            "kind": metadata.get("kind"),
            "file": chunk.file_path,
            "line": chunk.start_line,
            "end_line": chunk.end_line,
            "qualified_name": metadata.get("qualified_name"),
            "signature": metadata.get("signature_text"),
            "semantic_path": metadata.get("semantic_path"),
        }
