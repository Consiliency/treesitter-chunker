"""Tree-sitter grammar builder implementation."""

import logging
import platform
import shutil
import subprocess
from pathlib import Path

from chunker.grammar_management import _build_recipe, _build_tools

from chunker.exceptions import ChunkerError
from chunker.interfaces.grammar import GrammarBuilder

logger = logging.getLogger(__name__)


class BuildError(ChunkerError):
    """Error during grammar building."""


class TreeSitterGrammarBuilder(GrammarBuilder):
    """Builds Tree-sitter grammars from source."""

    def __init__(self):
        """Initialize grammar builder."""
        self._build_dir = Path("build")
        self._source_dir = Path("grammars")
        self._build_logs: dict[str, str] = {}
        self._platform = platform.system()
        self._lib_extension = {
            "Linux": ".so",
            "Darwin": ".dylib",
            "Windows": ".dll",
        }.get(self._platform, ".so")

    def set_build_directory(self, path: Path) -> None:
        """Set directory for build output.

        Args:
            path: Build output directory
        """
        self._build_dir = path
        self._build_dir.mkdir(exist_ok=True)

    def set_source_directory(self, path: Path) -> None:
        """Set directory containing grammar sources.

        Args:
            path: Source directory
        """
        self._source_dir = path

    def build(self, languages: list[str]) -> dict[str, bool]:
        """Build specified languages.

        Args:
            languages: List of language names

        Returns:
            Dictionary mapping language to build success
        """
        accepted, sources, includes, errors = _build_recipe.combined_sources(
            self._source_dir, languages, "canonical"
        )
        results = dict.fromkeys(languages, False)
        self._build_logs.update(errors)
        if not accepted:
            return results
        compiler = _build_tools.c_compiler()
        if not compiler:
            for lang in accepted:
                self._build_logs[lang] = "No gcc or cc found"
            return results
        lib_path = (self._build_dir / f"languages{self._lib_extension}").absolute()
        cmd = _build_recipe.controlled_c_argv(compiler, sources, includes, lib_path)
        logger.info("Controlled C build using %s", compiler)
        try:
            result = subprocess.run(
                cmd,
                cwd=self._source_dir.absolute(),
                check=False,
                capture_output=True,
                text=True,
            )
            success = result.returncode == 0 and lib_path.is_file()
            for lang in accepted:
                results[lang] = success
                self._build_logs[lang] = (
                    f"Controlled C using {compiler}: build successful"
                    if success
                    else f"Controlled C using {compiler}: link failed: {result.stderr}"
                )
        except Exception as error:
            for lang in accepted:
                self._build_logs[lang] = (
                    f"Controlled C using {compiler}: link failed: {error}"
                )
        return results

    def build_individual(self, language: str) -> bool:
        """Build a single language as a separate library.

        Args:
            language: Language name

        Returns:
            True if successful
        """
        lang_path = self._source_dir / f"tree-sitter-{language}"
        if not lang_path.exists():
            logger.error("Source directory for '%s' not found", language)
            self._build_logs[language] = "Source directory not found"
            return False
        lib_path = self._build_dir / f"{language}{self._lib_extension}"
        try:
            logger.info("Building %s...", language)
            # Multi-language repo subdir mapping (build from subdir when required)
            subdir_map: dict[str, str] = {
                # typescript repo provides typescript/ and tsx/
                "typescript": "typescript",
                "tsx": "tsx",
                # wasm repo provides wat/ subdirectory
                "wat": "wat",
                # ocaml repo provides grammars/ocaml/ and grammars/interface/
                # For now build ocaml core when requested
                "ocaml": "grammars/ocaml",
                # php repo provides php/ and php_only/ subdirectories
                "php": "php",
            }
            lang_root = lang_path
            if language in subdir_map:
                lang_root = lang_path / subdir_map[language]
                if not lang_root.exists():
                    logger.error("Subdir for %s not found: %s", language, lang_root)
                    self._build_logs[language] = f"Subdir not found: {lang_root}"
                    return False
            error = _build_recipe.source_chain_error(lang_root)
            if error:
                self._build_logs[language] = error
                return False
            # Check if this grammar needs generation first
            grammar_js = lang_root / "grammar.js"
            parser_c = lang_root / "src" / "parser.c"
            if grammar_js.exists() and not parser_c.exists():
                logger.info("Grammar needs generation, running tree-sitter generate...")
                generator = _build_tools.resolve_tool("tree-sitter")
                if not generator:
                    self._build_logs[language] = (
                        "Parser missing: install tree-sitter on PATH or supply src/parser.c"
                    )
                    return False
                result = subprocess.run(
                    [generator, "generate"],
                    cwd=lang_root,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    logger.warning(f"tree-sitter generate failed: {result.stderr}")
                    # Continue anyway - maybe we can still find source files

            canonical = not list(lang_root.glob("*.c")) and not list(
                lang_root.glob("*.cc")
            )
            canonical = canonical and not list(lang_root.glob("*.cpp"))
            canonical = canonical and not list((lang_root / "src").glob("*.cc"))
            canonical = canonical and not list((lang_root / "src").glob("*.cpp"))
            canonical = canonical and all(
                p.name in {"parser.c", "scanner.c"}
                for p in (lang_root / "src").glob("*.c")
            )
            if canonical:
                compiler = _build_tools.c_compiler()
                if not compiler:
                    self._build_logs[language] = "No gcc or cc found"
                    return False
                try:
                    cmd = _build_recipe.individual_c_argv(
                        compiler, lang_root, lib_path, standard="c11"
                    )
                    logger.info("Controlled C build using %s", compiler)
                    result = subprocess.run(
                        cmd,
                        cwd=lang_root.absolute(),
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    success = result.returncode == 0 and lib_path.is_file()
                    self._build_logs[language] = (
                        f"Controlled C using {compiler}: build successful"
                        if success
                        else f"Controlled C using {compiler}: compilation failed: {result.stderr}"
                    )
                    return success
                except Exception as error:
                    self._build_logs[language] = (
                        f"Controlled C using {compiler}: {error}"
                    )
                    return False
            logger.info("Uncontrolled compatibility build for %s", language)
            # Collect C/C++ sources including external scanners from root and src/
            c_files: list[str] = []
            cc_files: list[str] = []
            src_dir = lang_root / "src"
            # Root-level sources
            c_files.extend(str(p) for p in lang_root.glob("*.c"))
            cc_files.extend(str(p) for p in lang_root.glob("*.cc"))
            # src/ directory sources
            if src_dir.exists():
                c_files.extend(str(p) for p in src_dir.glob("*.c"))
                cc_files.extend(str(p) for p in src_dir.glob("*.cc"))

            if not c_files and not cc_files:
                # No C/C++ source files found, this grammar might need different handling
                logger.error(f"No C/C++ source files found in {lang_root}")
                self._build_logs[language] = (
                    f"No C/C++ source files found in {lang_root}"
                )
                return False

            # Filter out binding.cc and other problematic files
            cc_files = [f for f in cc_files if not f.endswith("binding.cc")]

            # For some problematic grammars, use only parser.c and scanner.c
            problematic_grammars = {"wat"}
            if language in problematic_grammars:
                # Only include essential files for problematic grammars
                c_files = [f for f in c_files if f.endswith(("parser.c", "scanner.c"))]
                cc_files = []

            # Choose compiler - prefer clang for better C99 support
            use_cxx = len(cc_files) > 0
            if use_cxx:
                compiler = "clang++" if shutil.which("clang++") else "g++"
            else:
                compiler = "clang" if shutil.which("clang") else "gcc"

            sources = c_files + cc_files
            cmd = [compiler, "-shared", "-O2", "-o", str(lib_path), *sources]

            # Add -fPIC for position-independent code on Unix-like systems
            # Windows/MSVC doesn't support this flag
            if self._platform != "Windows":
                cmd.insert(2, "-fPIC")

            # Language standards to support generated parsers
            if use_cxx:
                cmd.extend(["-std=c++17"])  # scanners often use modern C++
            else:
                # Use C11 for better support of static_assert and other features
                # Some grammars (like C++) have scanner.c files that use C11 features
                cmd.extend(["-std=c11"])

            # Link stdc++ if using C++
            if use_cxx:
                cmd.extend(["-lstdc++"])  # usually implied by g++, but explicit is fine

            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                raise BuildError(f"Compilation failed: {result.stderr}")
            if lib_path.exists():
                logger.info("Successfully built %s at %s", language, lib_path)
                self._build_logs[language] = "Build successful"
                return True
            raise BuildError(f"Library file_path not created at {lib_path}")
        except (FileNotFoundError, IndexError, KeyError) as e:
            logger.error("Failed to build %s: %s", language, e)
            self._build_logs[language] = str(e)
            return False

    def clean(self, language: str | None = None) -> None:
        """Clean build artifacts.

        Args:
            language: Specific language (None for all)
        """
        if language:
            patterns = [
                f"{language}{self._lib_extension}",
                f"{language}.*{self._lib_extension}",
            ]
        else:
            patterns = [f"*{self._lib_extension}", "*.o", "*.obj", "*.exp", "*.lib"]
        cleaned = 0
        for pattern in patterns:
            for file_path in self._build_dir.glob(pattern):
                # Use LBYL pattern to avoid try-except in loop
                if file_path.exists():
                    try:
                        file_path.unlink()
                        cleaned += 1
                        logger.debug("Removed %s", file_path)
                    except OSError as e:
                        logger.error("Failed to remove %s: %s", file_path, e)
        if cleaned > 0:
            logger.info("Cleaned %s build artifacts", cleaned)

    def get_build_log(self, language: str) -> str | None:
        """Get build log for a language.

        Args:
            language: Language name

        Returns:
            Build log or None
        """
        return self._build_logs.get(language)

    def compile_queries(self, language: str) -> bool:
        """Compile query files for a language.

        Args:
            language: Language name

        Returns:
            True if successful
        """
        lang_path = self._source_dir / f"tree-sitter-{language}"
        queries_dir = lang_path / "queries"
        if not queries_dir.exists():
            logger.debug("No queries directory for %s", language)
            return True
        target_dir = self._build_dir / "queries" / language
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            for query_file in queries_dir.glob("*.scm"):
                target_file = target_dir / query_file.name
                shutil.copy2(query_file, target_file)
                logger.debug("Copied %s for %s", query_file.name, language)
            return True
        except (FileNotFoundError, ImportError, ModuleNotFoundError) as e:
            logger.error("Failed to copy queries for %s: %s", language, e)
            return False


def build_language(name: str, source_path: str, build_path: str) -> bool:
    """Build a single language (helper function).

    Args:
        name: Language name
        source_path: Path to grammar source
        build_path: Path to build directory

    Returns:
        True if successful
    """
    builder = TreeSitterGrammarBuilder()
    builder.set_source_directory(Path(source_path).parent)
    builder.set_build_directory(Path(build_path))
    return builder.build_individual(name)
