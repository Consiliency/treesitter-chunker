"""Grammar Download Manager - Phase 14 Implementation

Handles downloading, extracting, and compiling tree-sitter grammars from GitHub.
"""

import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from chunker.contracts.download_contract import (
    CompilationResult,
    DownloadProgress,
    GrammarDownloadContract,
)


class GrammarDownloadManager(GrammarDownloadContract):
    """Concrete implementation of grammar download and compilation"""

    # Known grammar repositories
    GRAMMAR_REPOS: ClassVar[dict[str, str]] = {
        "python": "tree-sitter/tree-sitter-python",
        "javascript": "tree-sitter/tree-sitter-javascript",
        "typescript": "tree-sitter/tree-sitter-typescript",
        "rust": "tree-sitter/tree-sitter-rust",
        "go": "tree-sitter/tree-sitter-go",
        "java": "tree-sitter/tree-sitter-java",
        "c": "tree-sitter/tree-sitter-c",
        "cpp": "tree-sitter/tree-sitter-cpp",
        "ruby": "tree-sitter/tree-sitter-ruby",
        "php": "tree-sitter/tree-sitter-php",
        "bash": "tree-sitter/tree-sitter-bash",
        "html": "tree-sitter/tree-sitter-html",
        "css": "tree-sitter/tree-sitter-css",
        "json": "tree-sitter/tree-sitter-json",
        "yaml": "ikatyang/tree-sitter-yaml",
        "toml": "ikatyang/tree-sitter-toml",
        "markdown": "ikatyang/tree-sitter-markdown",
        "sql": "DerekStride/tree-sitter-sql",
        "kotlin": "fwcd/tree-sitter-kotlin",
        "swift": "alex-pinkus/tree-sitter-swift",
    }

    def __init__(self, cache_dir: Path | None = None):
        """Initialize download manager with cache directory"""
        self._cache_dir = cache_dir or self._default_cache_dir()
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_file = self._cache_dir / "metadata.json"
        self._load_metadata()

    def _default_cache_dir(self) -> Path:
        """Get default cache directory based on platform"""
        if platform.system() == "Windows":
            base = Path(os.environ.get("LOCALAPPDATA", "~")).expanduser()
        else:
            base = Path("~/.cache").expanduser()
        return base / "treesitter-chunker" / "grammars"

    def _load_metadata(self):
        """Load cache metadata"""
        if self._metadata_file.exists():
            with self._metadata_file.open() as f:
                self._metadata = json.load(f)
        else:
            self._metadata = {"grammars": {}, "version": "1.0"}

    def _save_metadata(self):
        """Save cache metadata"""
        with self._metadata_file.open("w") as f:
            json.dump(self._metadata, f, indent=2)

    def download_grammar(
        self,
        language: str,
        version: str | None = None,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ) -> Path:
        """Download a grammar repository from GitHub"""
        if language not in self.GRAMMAR_REPOS:
            raise ValueError(f"Unknown language: {language}")

        repo = self.GRAMMAR_REPOS[language]
        version = version or "master"

        # Create download directory
        grammar_dir = self._cache_dir / f"{language}-{version}"
        if grammar_dir.exists() and self._is_valid_grammar_dir(grammar_dir):
            return grammar_dir

        # Download URL
        url = f"https://github.com/{repo}/archive/refs/heads/{version}.tar.gz"
        if version.startswith("v"):
            url = f"https://github.com/{repo}/archive/refs/tags/{version}.tar.gz"

        # Download to temporary file
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            try:
                self._download_file(url, tmp.name, language, progress_callback)

                # Extract archive
                grammar_dir.mkdir(parents=True, exist_ok=True)
                self._extract_archive(tmp.name, grammar_dir)

                # Update metadata
                self._metadata["grammars"][language] = {
                    "version": version,
                    "path": str(grammar_dir),
                    "repo": repo,
                }
                self._save_metadata()

                return grammar_dir
            finally:
                Path(tmp.name).unlink(missing_ok=True)

    def _download_file(
        self,
        url: str,
        dest: str,
        language: str,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ):
        """Download file with progress tracking"""
        try:
            # Validate URL scheme
            if not url.startswith(("https://", "http://")):
                raise ValueError(f"Invalid URL scheme: {url}")
            req = Request(url, headers={"User-Agent": "treesitter-chunker/1.0"})
            with urlopen(req) as response:  # noqa: S310
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 8192

                with Path(dest).open("wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback and total_size > 0:
                            progress = DownloadProgress(
                                bytes_downloaded=downloaded,
                                total_bytes=total_size,
                                percent_complete=(downloaded / total_size) * 100,
                                current_file=f"{language}-grammar.tar.gz",
                            )
                            progress_callback(progress)

        except (HTTPError, URLError) as e:
            raise RuntimeError(f"Failed to download grammar: {e}") from e

    def _extract_archive(self, archive_path: str, dest_dir: Path):
        """Extract tar.gz archive"""
        with (
            tarfile.open(archive_path, "r:gz") as tar,
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            # Extract with safety filter (Python 3.12+)
            try:
                tar.extractall(tmpdir, filter="data")
            except TypeError:
                # Fallback for older Python versions
                tar.extractall(tmpdir)  # noqa: S202

            # Find the extracted directory (usually repo-name-version)
            extracted = list(Path(tmpdir).iterdir())
            if len(extracted) == 1 and extracted[0].is_dir():
                # Move contents to destination
                for item in extracted[0].iterdir():
                    dest = dest_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dest)

    def _is_valid_grammar_dir(self, grammar_dir: Path) -> bool:
        """Check if directory contains valid grammar sources"""
        return (grammar_dir / "src" / "parser.c").exists() or (
            grammar_dir / "grammar.js"
        ).exists()

    def compile_grammar(
        self,
        grammar_path: Path,
        output_dir: Path,
    ) -> CompilationResult:
        """Compile a grammar into a shared library"""
        if not grammar_path.exists():
            return CompilationResult(
                success=False,
                output_path=None,
                error_message=f"Grammar path does not exist: {grammar_path}",
                abi_version=None,
            )

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find source files
        src_dir = grammar_path / "src"
        if not src_dir.exists():
            return CompilationResult(
                success=False,
                output_path=None,
                error_message="No src directory found in grammar",
                abi_version=None,
            )

        # Collect source files
        sources = []
        parser_c = src_dir / "parser.c"
        if parser_c.exists():
            sources.append(str(parser_c))

        # Check for scanner files
        for scanner in ["scanner.c", "scanner.cc", "scanner.cpp"]:
            scanner_file = src_dir / scanner
            if scanner_file.exists():
                sources.append(str(scanner_file))
                break

        if not sources:
            return CompilationResult(
                success=False,
                output_path=None,
                error_message="No parser.c found in src directory",
                abi_version=None,
            )

        # Output file
        lang_name = grammar_path.name.split("-")[0]
        output_file = output_dir / f"{lang_name}.so"

        # Compile command
        cc = os.environ.get("CC", "cc")
        if platform.system() == "Darwin":
            # macOS
            cmd = [
                cc,
                "-fPIC",
                "-shared",
                "-dynamiclib",
                "-o",
                str(output_file),
                *sources,
            ]
        else:
            # Linux and others
            cmd = [cc, "-fPIC", "-shared", "-o", str(output_file), *sources]

        # Add C++ support if needed
        if any(s.endswith((".cc", ".cpp")) for s in sources):
            cmd.extend(["-xc++", "-lstdc++"])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(grammar_path),
                check=False,
            )

            if result.returncode != 0:
                return CompilationResult(
                    success=False,
                    output_path=None,
                    error_message=f"Compilation failed: {result.stderr}",
                    abi_version=None,
                )

            # Get ABI version (we'll use tree-sitter version check)
            abi_version = self._get_abi_version()

            return CompilationResult(
                success=True,
                output_path=output_file,
                error_message=None,
                abi_version=abi_version,
            )

        except (FileNotFoundError, OSError) as e:
            return CompilationResult(
                success=False,
                output_path=None,
                error_message=f"Compilation error: {e}",
                abi_version=None,
            )

    def _get_abi_version(self) -> int:
        """Get current tree-sitter ABI version"""
        try:
            import tree_sitter

            # tree-sitter 0.20.0 uses ABI 14, 0.21.0 uses ABI 15
            version = tree_sitter.__version__
            if version.startswith("0.20"):
                return 14
            if version.startswith("0.21"):
                return 15
            # Default to latest
            return 15
        except (ImportError, IndexError, KeyError):
            return 15  # Default

    def download_and_compile(
        self,
        language: str,
        version: str | None = None,
    ) -> tuple[bool, str]:
        """Download and compile a grammar in one step"""
        try:
            # Check if already cached
            if self.is_grammar_cached(language, version):
                cached_path = self._get_cached_grammar_path(language, version)
                return (True, str(cached_path))

            # Download grammar
            grammar_path = self.download_grammar(language, version)

            # Compile to cache directory
            result = self.compile_grammar(grammar_path, self._cache_dir)

            if result.success:
                # Update metadata with compiled info
                if language in self._metadata["grammars"]:
                    self._metadata["grammars"][language]["compiled"] = str(
                        result.output_path,
                    )
                    self._metadata["grammars"][language][
                        "abi_version"
                    ] = result.abi_version
                    self._save_metadata()

                return (True, str(result.output_path))
            return (False, result.error_message or "Compilation failed")

        except (OSError, FileNotFoundError, IndexError) as e:
            return (False, str(e))

    def get_grammar_cache_dir(self) -> Path:
        """Get the directory where grammars are cached"""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        return self._cache_dir

    def is_grammar_cached(self, language: str, version: str | None = None) -> bool:
        """Check if a grammar is already cached and compiled"""
        if language not in self._metadata.get("grammars", {}):
            return False

        grammar_info = self._metadata["grammars"][language]

        # Check version if specified
        if version and grammar_info.get("version") != version:
            return False

        # Check if compiled .so exists
        if "compiled" in grammar_info:
            compiled_path = Path(grammar_info["compiled"])
            return compiled_path.exists()

        # Check default location
        so_file = self._cache_dir / f"{language}.so"
        return so_file.exists()

    def _get_cached_grammar_path(
        self,
        language: str,
        _version: str | None = None,
    ) -> Path:
        """Get path to cached grammar .so file"""
        if language in self._metadata.get("grammars", {}):
            grammar_info = self._metadata["grammars"][language]
            if "compiled" in grammar_info:
                return Path(grammar_info["compiled"])

        # Default location
        return self._cache_dir / f"{language}.so"

    def clean_cache(self, keep_recent: int = 5) -> int:
        """Clean old cached grammars"""
        removed = 0

        # Get all grammar directories and .so files
        grammar_dirs = []
        so_files = []

        for item in self._cache_dir.iterdir():
            if item.is_dir() and "-" in item.name:
                grammar_dirs.append(item)
            elif item.suffix == ".so":
                so_files.append(item)

        # Sort by modification time
        grammar_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        so_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Remove old directories
        for dir_path in grammar_dirs[keep_recent:]:
            shutil.rmtree(dir_path)
            removed += 1

            # Remove from metadata
            lang = dir_path.name.split("-")[0]
            if lang in self._metadata.get("grammars", {}):
                del self._metadata["grammars"][lang]

        # Remove old .so files
        for so_file in so_files[keep_recent:]:
            so_file.unlink()
            removed += 1

        self._save_metadata()
        return removed

    def validate_grammar(self, grammar_path: Path) -> tuple[bool, str | None]:
        """Validate a compiled grammar"""
        if not grammar_path.exists():
            return (False, "Grammar file does not exist")

        if grammar_path.suffix != ".so":
            return (False, "Grammar file must be a .so file")

        # Try to load the grammar to validate it
        try:
            import ctypes

            # Try to load the shared library
            lib = ctypes.CDLL(str(grammar_path))

            # Check for expected symbol (language function)
            lang_name = grammar_path.stem
            expected_symbol = f"tree_sitter_{lang_name}"

            if hasattr(lib, expected_symbol):
                return (True, None)
            return (False, f"Missing expected symbol: {expected_symbol}")

        except (AttributeError, FileNotFoundError, OSError) as e:
            return (False, f"Failed to load grammar: {e}")
