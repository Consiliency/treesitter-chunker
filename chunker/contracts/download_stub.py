"""Concrete stub implementation for testing - Grammar Download"""

import tempfile
from collections.abc import Callable
from pathlib import Path

from .download_contract import (
    CompilationResult,
    DownloadProgress,
    GrammarDownloadContract,
)


class GrammarDownloadStub(GrammarDownloadContract):
    """Stub implementation that can be instantiated and tested"""

    @staticmethod
    def download_grammar(
        language: str,
        version: str | None = None,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ) -> Path:
        """Stub that simulates download"""
        if progress_callback:
            for i in range(0, 101, 20):
                progress = DownloadProgress(
                    bytes_downloaded=i * 1000,
                    total_bytes=100000,
                    percent_complete=float(i),
                    current_file=f"{language}-grammar.tar.gz",
                )
                progress_callback(progress)
        cache_dir = GrammarDownloadStub.get_grammar_cache_dir()
        download_path = cache_dir / f"{language}-{version or 'latest'}"
        download_path.mkdir(exist_ok=True)
        (download_path / "grammar.js").touch()
        return download_path

    @staticmethod
    def compile_grammar(
        grammar_path: Path,
        output_dir: Path,
    ) -> CompilationResult:
        """Stub that simulates compilation"""
        if not grammar_path.exists():
            return CompilationResult(
                success=False,
                output_path=None,
                error_message="Grammar path does not exist",
                abi_version=None,
            )
        output_file = output_dir / f"{grammar_path.name}.so"
        output_file.touch()
        return CompilationResult(
            success=True,
            output_path=output_file,
            error_message=None,
            abi_version=14,
        )

    @staticmethod
    def download_and_compile(
        language: str,
        version: str | None = None,
    ) -> tuple[bool, str]:
        """Stub that simulates download and compile"""
        try:
            grammar_path = GrammarDownloadStub.download_grammar(language, version)
            cache_dir = GrammarDownloadStub.get_grammar_cache_dir()
            result = GrammarDownloadStub.compile_grammar(grammar_path, cache_dir)
            if result.success:
                return True, str(result.output_path)
            return False, result.error_message or "Compilation failed"
        except (FileNotFoundError, IndexError, KeyError) as e:
            return False, str(e)

    @staticmethod
    def get_grammar_cache_dir() -> Path:
        """Stub that returns test cache directory"""
        cache_dir = Path(tempfile.gettempdir()) / "grammar_cache_stub"
        cache_dir.mkdir(exist_ok=True)
        return cache_dir

    @staticmethod
    def is_grammar_cached(
        language: str,
        version: str | None = None,
    ) -> bool:
        """Stub that checks for cached grammar"""
        cache_dir = GrammarDownloadStub.get_grammar_cache_dir()
        cached_file = cache_dir / f"{language}-{version or 'latest'}.so"
        return cached_file.exists()

    @staticmethod
    def clean_cache(keep_recent: int = 5) -> int:
        """Stub that simulates cache cleaning"""
        removed = 0
        cache_dir = GrammarDownloadStub.get_grammar_cache_dir()
        for file_path in cache_dir.glob("*.so"):
            if removed >= 2:
                break
            file_path.unlink()
            removed += 1
        return removed

    @staticmethod
    def validate_grammar(grammar_path: Path) -> tuple[bool, str | None]:
        """Stub that validates grammar"""
        if not grammar_path.exists():
            return False, "Grammar file_path does not exist"
        if grammar_path.suffix != ".so":
            return False, "Grammar file_path must be a .so file_path"
        return True, None
