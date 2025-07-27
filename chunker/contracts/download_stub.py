"""Concrete stub implementation for testing - Grammar Download"""

import tempfile
from pathlib import Path
from typing import Callable, Optional

from .download_contract import (
    CompilationResult,
    DownloadProgress,
    GrammarDownloadContract,
)


class GrammarDownloadStub(GrammarDownloadContract):
    """Stub implementation that can be instantiated and tested"""

    def __init__(self):
        self._cache_dir = Path(tempfile.gettempdir()) / "grammar_cache_stub"
        self._cache_dir.mkdir(exist_ok=True)

    def download_grammar(
        self,
        language: str,
        version: str | None = None,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
    ) -> Path:
        """Stub that simulates download"""
        # Simulate progress callbacks
        if progress_callback:
            for i in range(0, 101, 20):
                progress = DownloadProgress(
                    bytes_downloaded=i * 1000,
                    total_bytes=100000,
                    percent_complete=float(i),
                    current_file=f"{language}-grammar.tar.gz",
                )
                progress_callback(progress)

        # Return a fake download path
        download_path = self._cache_dir / f"{language}-{version or 'latest'}"
        download_path.mkdir(exist_ok=True)
        (download_path / "grammar.js").touch()
        return download_path

    def compile_grammar(
        self,
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

        # Simulate successful compilation
        output_file = output_dir / f"{grammar_path.name}.so"
        output_file.touch()

        return CompilationResult(
            success=True,
            output_path=output_file,
            error_message=None,
            abi_version=14,
        )

    def download_and_compile(
        self,
        language: str,
        version: str | None = None,
    ) -> tuple[bool, str]:
        """Stub that simulates download and compile"""
        try:
            # Simulate the process
            grammar_path = self.download_grammar(language, version)
            result = self.compile_grammar(grammar_path, self._cache_dir)

            if result.success:
                return (True, str(result.output_path))
            return (False, result.error_message or "Compilation failed")
        except Exception as e:
            return (False, str(e))

    def get_grammar_cache_dir(self) -> Path:
        """Stub that returns test cache directory"""
        return self._cache_dir

    def is_grammar_cached(self, language: str, version: str | None = None) -> bool:
        """Stub that checks for cached grammar"""
        cached_file = self._cache_dir / f"{language}-{version or 'latest'}.so"
        return cached_file.exists()

    def clean_cache(self, keep_recent: int = 5) -> int:
        """Stub that simulates cache cleaning"""
        # Simulate removing some files
        removed = 0
        for file in self._cache_dir.glob("*.so"):
            if removed >= 2:  # Simulate keeping recent files
                break
            file.unlink()
            removed += 1
        return removed

    def validate_grammar(self, grammar_path: Path) -> tuple[bool, str | None]:
        """Stub that validates grammar"""
        if not grammar_path.exists():
            return (False, "Grammar file does not exist")
        if grammar_path.suffix != ".so":
            return (False, "Grammar file must be a .so file")
        return (True, None)
