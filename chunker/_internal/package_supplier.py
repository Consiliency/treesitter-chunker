"""Package-supplied grammars of our own wheel (RECORD-verified).

This is the one shared implementation of the native validation contract's
"Package-supplied grammars in our own wheels" boundary (maintainer decision M3,
2026-10-31). Every trust decision uses it: registry resolution, the parse path
and, through ``chunker._internal.native_admission``, the grammar commands
(maintainer decision, 2026-11-01: one trust rule everywhere).

A native file directly in the installed package's ``chunker/data/grammars/build``
is package-supplied only when it is a regular, non-symlink file that is one of
the installed ``treesitter-chunker`` distribution's ``RECORD`` entries and its
bytes match that entry's ``sha256``. The expected digest comes from ``RECORD``,
which the installer writes; nothing here creates or widens an approval.

This module imports nothing from ``chunker.grammar`` and loads no native code.
"""

from __future__ import annotations

import base64
import csv
import functools
import hashlib
import hmac
import importlib.metadata
import os
import stat
from importlib.metadata import PackageNotFoundError
from pathlib import Path, PurePosixPath

_PACKAGE_GRAMMAR_ENTRY_PARENT = PurePosixPath("chunker/data/grammars/build")
_NATIVE_SUFFIXES = frozenset({".so", ".dylib", ".dll"})
_READ_FLAGS = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)

SUPPLIED = "supplied"
MISMATCH = "mismatch"
LOCAL = "local"


def package_grammar_build_dir() -> Path:
    """Return the package grammar directory ``chunker/data/grammars/build``."""
    return Path(__file__).resolve().parent.parent / "data" / "grammars" / "build"


def same_file(first: Path | str, second: Path | str) -> bool:
    """File identity: ``os.path.samefile`` first; resolved paths only if it raises."""
    try:
        return Path(first).samefile(second)
    except (OSError, ValueError):
        try:
            return Path(first).resolve() == Path(second).resolve()
        except (OSError, RuntimeError):
            return False


def _package_distribution() -> importlib.metadata.Distribution | None:
    """Return the installed ``treesitter-chunker`` distribution, if any."""
    try:
        return importlib.metadata.distribution("treesitter-chunker")
    except PackageNotFoundError:
        return None


def _package_init_file() -> Path:
    """Return the imported ``chunker/__init__.py``."""
    import chunker

    return Path(chunker.__file__)


def _valid_package_grammar_entry(raw: str) -> bool:
    if "\\" in raw or raw.startswith("/") or ":" in raw:
        return False
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    return (
        PurePosixPath(*parts[:-1]) == _PACKAGE_GRAMMAR_ENTRY_PARENT
        and PurePosixPath(parts[-1]).suffix in _NATIVE_SUFFIXES
    )


@functools.lru_cache(maxsize=1)
def _package_grammar_records() -> tuple[tuple[Path, str | None], ...]:
    """Return ``(located file, expected urlsafe-b64 sha256 or None)`` entries.

    Only entries of the installed distribution whose ``chunker/__init__.py`` is
    the imported package count, and only relative POSIX entries directly under
    ``chunker/data/grammars/build`` with a native suffix. ``None`` marks an entry
    without a ``sha256`` hash (not package-supplied).
    """
    distribution = _package_distribution()
    if distribution is None:
        return ()
    try:
        located_init = distribution.locate_file("chunker/__init__.py")
        if not same_file(Path(str(located_init)), _package_init_file()):
            return ()
        # Parse RECORD itself: Distribution.files drops entries whose files no
        # longer exist (Python 3.12+), and a deleted shipped grammar must still
        # be recognised as a RECORD entry.
        record_text = distribution.read_text("RECORD")
    except (OSError, ValueError):
        return ()
    if not record_text:
        return ()
    records = []
    for row in csv.reader(record_text.splitlines()):
        if not row:
            continue
        raw = row[0]
        if not _valid_package_grammar_entry(raw):
            continue
        hash_field = row[1] if len(row) > 1 else ""
        algorithm, _, value = hash_field.partition("=")
        expected = value if algorithm == "sha256" and value else None
        records.append((Path(str(distribution.locate_file(raw))), expected))
    return tuple(records)


def package_supplied_digest(candidate: Path) -> tuple[str, str | None]:
    """Classify ``candidate`` against our own wheel's ``RECORD``.

    Returns ``("supplied", hex_digest)`` when the candidate is a regular,
    non-symlink file that is one of our distribution's package grammar files and
    matches its ``RECORD`` ``sha256``; ``("mismatch", None)`` when it is such a
    file but its bytes differ (never loaded, and no user pin can admit it); and
    ``("local", None)`` otherwise (an ordinary local candidate that needs a pin).
    """
    try:
        status = os.lstat(candidate)
    except OSError:
        return LOCAL, None
    if not stat.S_ISREG(status.st_mode):
        return LOCAL, None
    for located, expected in _package_grammar_records():
        if not same_file(candidate, located):
            continue
        if expected is None:
            return LOCAL, None
        try:
            descriptor = os.open(candidate, _READ_FLAGS)
        except OSError:
            return LOCAL, None
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                return LOCAL, None
            digest = hashlib.sha256()
            while True:
                block = os.read(descriptor, 1024 * 1024)
                if not block:
                    break
                digest.update(block)
        finally:
            os.close(descriptor)
        actual = base64.urlsafe_b64encode(digest.digest()).rstrip(b"=").decode("ascii")
        if hmac.compare_digest(actual, expected.rstrip("=")):
            return SUPPLIED, digest.hexdigest()
        return MISMATCH, None
    return LOCAL, None


def is_record_entry(path: Path) -> bool:
    """Whether the directory entry ``path`` is one of our RECORD grammar entries.

    The comparison is by directory entry: the same file name (case-normalized)
    in the same directory (compared with ``same_file``), never by the inode the
    entry points to. So a local symlink or hard link elsewhere that aliases a
    shipped grammar is not a RECORD entry, while the shipped entry itself still
    counts after its file has been deleted. Used to refuse replacing a shipped
    grammar in place: the replacement would differ from RECORD and stay
    ``integrity_mismatch`` permanently.
    """
    path = Path(path)
    name = os.path.normcase(path.name)
    return any(
        os.path.normcase(located.name) == name
        and same_file(path.parent, located.parent)
        for located, _ in _package_grammar_records()
    )
