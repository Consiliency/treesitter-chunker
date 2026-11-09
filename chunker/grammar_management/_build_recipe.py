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
    if platform.startswith("linux"):
        return ["-Wl,-z,defs"]  # Linux only: refuse undefined symbols
    if platform == "darwin":
        return [f"-Wl,-install_name,@rpath/{library_name(language)}"]
    if platform == "win32":
        return ["-Wl,--no-insert-timestamp", "-Wl,--disable-auto-image-base"]
    return []


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
