"""The installer's path-independent gcc build (treesitter-chunker#621, #607).

``GrammarInstaller`` runs this recipe with the grammar source root (the
directory holding ``src/``) as its working directory, so the compiler only
ever sees the relative paths ``src``, ``src/parser.c`` and ``src/scanner.c``.
Whatever a C source keeps of its own path (``assert``, ``__FILE__``) is then
the same wherever the source was cloned. The per-platform link flags remove
the remaining output-path and link-time inputs:

- Linux: ``-Wl,-z,defs`` refuses undefined symbols, so a grammar the recipe
  cannot build completely fails here instead of producing a partial library.
- macOS: the install name (``LC_ID_DYLIB``) is ``@rpath/lib<language>.so``
  rather than the ``-o`` path.
- Windows (MinGW): no link timestamp, and an ImageBase that is not a hash of
  the ``-o`` path.

This module checks source paths and scanner presence; the
installer runs the argv it returns.
"""

from __future__ import annotations

import re
import stat
import sys
from pathlib import Path
from typing import Any

#: Scanners the controlled route never builds: it compiles C only.
CXX_SCANNERS = ("scanner.cc", "scanner.cpp")

_BANNER_LIMIT = 200
_DOTTED = re.compile(r"\d+(?:\.\d+)+")
_CLANG_VERSION = re.compile(r"version\s+(\d+(?:\.\d+)+)")


def library_name(language: str) -> str:
    """The output file name (Windows records it in the export directory)."""
    return f"lib{language}.so"


def platform_link_flags(language: str, platform: str = sys.platform) -> list[str]:
    """The link flags that keep paths and link time out of the library."""
    return artifact_link_flags(library_name(language), platform)


def cxx_scanner(source_root: Path) -> str | None:
    """The C++ scanner the controlled route will not build, if any (relative name)."""
    for name in CXX_SCANNERS:
        if (source_root / "src" / name).exists():
            return f"src/{name}"
    return None


def symlinked_source(source_root: Path) -> str | None:
    """Find a linked recipe input without traversing linked directories.

    Check the fixed inputs first (including dangling links), then every entry
    beneath src: headers can include other headers outside tree_sitter/.
    This is a preflight, not a sandbox against concurrent source replacement
    or arbitrary preprocessor includes.
    """
    pending = [
        source_root,
        *(
            source_root / name
            for name in ("src", "src/parser.c", "src/scanner.c", "src/tree_sitter")
        ),
    ]
    for path in pending:
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            relative = path.relative_to(source_root).as_posix()
            return "source root" if relative == "." else relative

    pending = [source_root / "src"]
    while pending:
        path = pending.pop()
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            relative = path.relative_to(source_root).as_posix()
            return "source root" if relative == "." else relative
        if stat.S_ISDIR(mode):
            pending.extend(sorted(path.iterdir(), reverse=True))
    return None


def gcc_build_argv(
    compiler: str,
    language: str,
    output: Path | str,
    *,
    has_scanner: bool,
    platform: str = sys.platform,
) -> list[str]:
    """argv to run with cwd = the grammar source root (the directory holding src/).

    ``compiler`` is an absolute path and ``output`` should be absolute too; the
    source paths are fixed relative literals with forward slashes.
    """
    argv = [compiler, "-shared", "-fPIC", "-O2", "-I", "src", "src/parser.c"]
    if has_scanner:
        argv.append("src/scanner.c")
    argv += ["-o", str(output), *platform_link_flags(language, platform)]
    return argv


def compiler_identity(stdout: str | None) -> dict[str, Any] | None:
    """Family, version and banner from ``<compiler> --version`` stdout.

    The banner is the first non-empty line (``\\r`` removed, stripped, at most
    200 characters). ``None`` when there is no such line.
    """
    if not stdout:
        return None
    line = next(
        (
            candidate.strip()
            for candidate in stdout.replace("\r", "").split("\n")
            if candidate.strip()
        ),
        None,
    )
    if line is None:
        return None
    banner = line[:_BANNER_LIMIT]
    family = "clang" if "clang" in banner.lower() else "gcc"
    version: str | None = None
    if family == "clang":
        # Apple's banner ends in a build tag such as ``(clang-1700.0.13.5)``.
        match = _CLANG_VERSION.search(banner)
        if match is not None:
            version = match.group(1)
    if version is None:
        dotted = _DOTTED.findall(banner)
        version = dotted[-1] if dotted else None
    return {"family": family, "version": version, "banner": banner}


def artifact_link_flags(basename: str, platform: str) -> list[str]:
    """Link flags for an actual stable public basename, never a path."""
    if not basename or any(c in basename for c in "/\\,") or basename in {".", ".."}:
        raise ValueError("Expected a library basename")
    if platform.startswith("linux"):
        return ["-Wl,-z,defs"]
    if platform == "darwin":
        return [f"-Wl,-install_name,@rpath/{basename}"]
    if platform == "win32":
        return ["-Wl,--no-insert-timestamp", "-Wl,--disable-auto-image-base"]
    return []


def source_chain_error(root: Path) -> str | None:
    """Inspect every ancestor without resolving away symlink evidence."""
    root = root.absolute()
    for path in reversed((root, *root.parents)):
        try:
            if stat.S_ISLNK(path.lstat().st_mode):
                return f"Symlinked source component: {path}"
        except FileNotFoundError:
            return f"Source directory not found: {path}"
    for pattern in ("*.c", "*.cc", "*.cpp"):
        for path in root.glob(pattern):
            if path.is_symlink():
                return f"Symlinked source: {path}"
    linked = symlinked_source(root)
    return f"Symlinked source: {linked}" if linked else None


def member_sources(root: Path, policy: str) -> tuple[list[Path], str | None]:
    """Preflight a combined member, preserving each builder's C glob policy."""
    error = source_chain_error(root)
    if error:
        return [], error
    if cxx_scanner(root):
        return [], "C++ scanner: controlled combined builds support C only"
    sources = list((root / "src").glob("*.c"))
    if policy == "root":
        sources += list(root.glob("*.c"))
    elif policy == "canonical":
        sources = [p for p in sources if p.name in {"parser.c", "scanner.c"}]
    for path in sources:
        if path.is_symlink() or not path.is_file():
            return [], f"Nonregular C input: {path}"
    if not any(p.name == "parser.c" for p in sources):
        return [], "No parser.c in supported C inputs"
    return sorted(sources), None


def combined_sources(
    common: Path, languages: list[str], policy: str
) -> tuple[list[str], list[str], list[str], dict[str, str]]:
    """Filesystem-only preflight of every member before probes or compilation."""
    common = common.absolute()
    accepted: list[str] = []
    sources: list[str] = []
    includes: set[str] = set()
    errors: dict[str, str] = {}
    for language in sorted(set(languages)):
        root = common / f"tree-sitter-{language}"
        if root.parent != common:
            errors[language] = "Escaping grammar path"
            continue
        files, error = member_sources(root, policy)
        if error:
            errors[language] = error
            continue
        accepted.append(language)
        sources.extend(p.relative_to(common).as_posix() for p in files)
        includes.update(p.parent.relative_to(common).as_posix() for p in files)
    return accepted, sorted(set(sources)), sorted(includes), errors


def controlled_c_argv(
    compiler: str,
    sources: list[str],
    includes: list[str],
    output: Path,
    *,
    standard: str | None = None,
) -> list[str]:
    """Build ordered, relative C inputs with host flags and a stable basename."""
    for name in [*sources, *includes]:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError(f"Not a relative controlled input: {name}")
    argv = [compiler, "-shared", "-fPIC", "-O2"]
    for include in includes:
        argv += ["-I", include]
    argv += sources
    if standard:
        argv.append(f"-std={standard}")
    return argv + [
        "-o",
        str(output.absolute()),
        *artifact_link_flags(output.name, sys.platform),
    ]


def individual_c_argv(
    compiler: str,
    root: Path,
    output: Path,
    *,
    standard: str | None = None,
    scanner_priority: bool = False,
) -> list[str]:
    """Validate canonical C inputs, then build argv; no subprocess or fallback."""
    error = source_chain_error(root)
    if error:
        raise ValueError(error)
    scanner = root / "src" / "scanner.c"
    if cxx_scanner(root) and not (scanner_priority and scanner.is_file()):
        raise ValueError("C++ scanner: controlled route supports C only")
    extras = [
        p
        for directory in (root, root / "src")
        for pattern in ("*.cc", "*.cpp")
        for p in directory.glob(pattern)
    ]
    if scanner_priority and scanner.is_file():
        extras = [
            p
            for p in extras
            if p not in {root / "src" / "scanner.cc", root / "src" / "scanner.cpp"}
        ]
    if extras:
        raise ValueError("Noncanonical C++ inputs on controlled C route")
    files = list(root.glob("*.c")) + list((root / "src").glob("*.c"))
    expected = [root / "src" / "parser.c"]
    if scanner.is_file():
        expected.append(scanner)
    if set(files) != set(expected) or not all(p.is_file() for p in expected):
        raise ValueError(
            "Noncanonical C inputs: require src/parser.c and optional src/scanner.c"
        )
    return controlled_c_argv(
        compiler,
        [p.relative_to(root).as_posix() for p in expected],
        ["src"],
        output,
        standard=standard,
    )
