"""Read approved native-grammar pins (``chunker.trusted_artifacts.v1``).

This is the shared pin-file reader of the native validation contract
(``docs/development/native-validation-contract.md``, "IF-0-ADMITPIN-1 — pin
sources"). It only reads and validates pins. It never creates, updates or
deletes a pin file, never hashes a discovered artifact, and never loads native
code. Admission itself stays in :func:`chunker.grammar.integrity.probe_native_grammar`.

Two sources use this format, and exactly one is active (never merged):

1. an explicit ``trusted_artifacts`` constructor argument (embedding code);
2. the ``--trusted-artifacts PATH`` option of the grammar command groups;
3. the user-config pin file, :func:`user_config_pin_path`;
4. no pins.
"""

from __future__ import annotations

import json
import os
import re
import stat
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from chunker.exceptions import TrustedArtifactsError

TRUSTED_ARTIFACTS_SCHEMA = "chunker.trusted_artifacts.v1"
PIN_FILE_NAME = "trusted-artifacts.json"
PIN_FILE_LIMIT = 1024 * 1024
_APP_DIRECTORY = "treesitter-chunker"
_LANGUAGE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*", re.ASCII)
#: Binary read-only open; ``O_BINARY`` keeps Windows from translating bytes.
_READ_FLAGS = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
_SHA256 = re.compile(r"[0-9a-fA-F]{64}", re.ASCII)

TrustedArtifacts = dict[str, dict[str, str]]


def user_config_pin_path() -> Path | None:
    """Return the user-config pin file path, or ``None`` if there is none.

    ``win32``: ``%APPDATA%\\treesitter-chunker\\trusted-artifacts.json``, only
    when ``APPDATA`` is an absolute path. ``darwin``:
    ``~/Library/Application Support/treesitter-chunker/trusted-artifacts.json``.
    Elsewhere: ``$XDG_CONFIG_HOME/treesitter-chunker/trusted-artifacts.json``
    when ``XDG_CONFIG_HOME`` is absolute, otherwise
    ``~/.config/treesitter-chunker/trusted-artifacts.json``.
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if not appdata or not Path(appdata).is_absolute():
            return None
        return Path(appdata) / _APP_DIRECTORY / PIN_FILE_NAME
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".config"
    return base / _APP_DIRECTORY / PIN_FILE_NAME


def forbidden_pin_directories(
    *, cache_dir: Path | None = None, library_path: Path | None = None
) -> tuple[Path, ...]:
    """Return the tool-written directories that must not contain the pin file.

    These are the cache root (``cache_dir`` or ``~/.cache/treesitter-chunker``),
    the package grammar directory ``chunker/data/grammars/build``,
    ``CHUNKER_GRAMMAR_BUILD_DIR`` when set, and the configured combined
    library's directory. With no ``library_path``, both possible default
    library directories are included (the package grammar directory and the
    checkout's ``build`` directory).
    """
    package_root = Path(__file__).resolve().parents[1]
    directories = [
        Path(cache_dir) if cache_dir is not None else _default_cache_root(),
        package_root / "data" / "grammars" / "build",
    ]
    override = os.environ.get("CHUNKER_GRAMMAR_BUILD_DIR")
    if override:
        directories.append(Path(override))
    if library_path is not None:
        directories.append(Path(library_path).parent)
    else:
        directories.append(package_root.parent / "build")
    return tuple(directories)


def _default_cache_root() -> Path:
    return Path.home() / ".cache" / "treesitter-chunker"


def _inside(path: Path, directory: Path) -> bool:
    """Whether resolved ``path`` lies in ``directory``.

    Each ancestor of ``path`` is compared with ``directory`` by file identity
    (``os.path.samefile``), so case-insensitive file systems that ``resolve()``
    does not fold (macOS APFS) are handled. A string comparison of resolved,
    case-normalized paths is the fallback when the identity check raises (for
    example a forbidden directory that does not exist).
    """
    for ancestor in path.parents:
        try:
            if Path(ancestor).samefile(directory):
                return True
        except (OSError, ValueError):
            continue
    try:
        resolved = os.path.normcase(str(directory.resolve()))
    except (OSError, RuntimeError):
        return False
    candidate = os.path.normcase(str(path))
    return candidate.startswith(resolved.rstrip(os.sep) + os.sep)


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def _reject_constant(name: str) -> Any:
    raise ValueError(f"invalid JSON constant {name}")


def parse_trusted_artifacts(data: bytes, *, source: Path) -> TrustedArtifacts:
    """Validate ``data`` as one ``chunker.trusted_artifacts.v1`` document.

    The whole file is validated before anything is returned; entries are never
    partially applied.

    Raises:
        TrustedArtifactsError: naming ``source`` and the first defect found.
    """

    def defect(message: str) -> TrustedArtifactsError:
        return TrustedArtifactsError(source, message)

    if len(data) > PIN_FILE_LIMIT:
        raise defect(f"larger than {PIN_FILE_LIMIT} bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise defect(f"not valid UTF-8 ({error.reason})") from None
    try:
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except (ValueError, RecursionError) as error:
        raise defect(f"not valid JSON ({error})") from None
    if not isinstance(document, dict) or set(document) != {"schema", "artifacts"}:
        raise defect(
            'top level must be an object with exactly "schema" and "artifacts"'
        )
    if document["schema"] != TRUSTED_ARTIFACTS_SCHEMA:
        raise defect(f'"schema" must be exactly "{TRUSTED_ARTIFACTS_SCHEMA}"')
    artifacts = document["artifacts"]
    if not isinstance(artifacts, dict):
        raise defect('"artifacts" must be an object')
    pins: TrustedArtifacts = {}
    for language, record in artifacts.items():
        if not _LANGUAGE_KEY.fullmatch(language):
            raise defect(f"invalid language key {language!r}")
        if not isinstance(record, dict) or set(record) != {"sha256"}:
            raise defect(f'entry {language!r} must be an object with exactly "sha256"')
        digest = record["sha256"]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise defect(f"entry {language!r} sha256 must be 64 hex digits")
        pins[language] = {"sha256": digest.lower()}
    return pins


def read_trusted_artifacts(
    path: Path, *, forbidden: Iterable[Path] = ()
) -> TrustedArtifacts:
    """Read and validate one pin file.

    The file must exist, be a regular file after symbolic links are resolved,
    be at most :data:`PIN_FILE_LIMIT` bytes, and lie outside every directory in
    ``forbidden`` (compared after resolving symbolic links).

    Raises:
        TrustedArtifactsError: for a missing, unreadable or defective file.
    """
    path = Path(path)
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        raise TrustedArtifactsError(path, "file not found") from None
    except (OSError, RuntimeError) as error:
        raise TrustedArtifactsError(path, f"cannot resolve path ({error})") from None
    for directory in forbidden:
        if _inside(resolved, Path(directory)):
            raise TrustedArtifactsError(
                path,
                f"inside the tool-written directory {directory}; pin files must "
                "live outside the cache and grammar build directories",
            )
    try:
        descriptor = os.open(resolved, _READ_FLAGS)
    except OSError as error:
        raise TrustedArtifactsError(
            path, f"cannot be opened ({error.strerror or error})"
        ) from None
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):
            raise TrustedArtifactsError(path, "not a regular file")
        if status.st_size > PIN_FILE_LIMIT:
            raise TrustedArtifactsError(path, f"larger than {PIN_FILE_LIMIT} bytes")
        chunks = []
        remaining = PIN_FILE_LIMIT + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(remaining, 65536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    except OSError as error:
        raise TrustedArtifactsError(
            path, f"cannot be read ({error.strerror or error})"
        ) from None
    finally:
        os.close(descriptor)
    return parse_trusted_artifacts(b"".join(chunks), source=path)


def load_user_config_pins(
    *, cache_dir: Path | None = None, library_path: Path | None = None
) -> TrustedArtifacts | None:
    """Read the user-config pin file.

    Returns ``None`` when the file does not exist (no pins and no error).

    Raises:
        TrustedArtifactsError: for a present but defective file. Callers decide
            how to fail closed: the parse path continues with no pins; grammar
            commands exit 2.
    """
    path = user_config_pin_path()
    if path is None:
        return None
    try:
        os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as error:
        # Present but inaccessible (for example a parent directory without
        # search permission) is a defect, never "absent".
        raise TrustedArtifactsError(
            path, f"cannot be accessed ({error.strerror or error})"
        ) from None
    return read_trusted_artifacts(
        path,
        forbidden=forbidden_pin_directories(
            cache_dir=cache_dir, library_path=library_path
        ),
    )


def resolve_command_pins(
    option_path: Path | None, *, cache_dir: Path | None = None
) -> TrustedArtifacts | None:
    """Return the active pins of a grammar command.

    ``--trusted-artifacts PATH`` wins when given; otherwise the user-config pin
    file applies. The two are never merged.

    Raises:
        TrustedArtifactsError: for a missing or defective option file, or a
            present but defective config file. Grammar commands treat it as a
            usage error (exit status 2).
    """
    if option_path is not None:
        return read_trusted_artifacts(Path(option_path))
    return load_user_config_pins(cache_dir=cache_dir)


def copy_trusted_artifacts(mapping: object) -> dict[str, dict[str, Any]]:
    """Copy a caller's pin mapping (IF-0-ADMITPIN-1 rule 2).

    Each Mapping record is copied with ``dict(record)``; other values, and a
    non-Mapping argument, are dropped. Later changes to the caller's mapping
    have no effect.
    """
    if not isinstance(mapping, Mapping):
        return {}
    return {
        language: dict(record)
        for language, record in mapping.items()
        if isinstance(language, str) and isinstance(record, Mapping)
    }


def pin_provenance(
    mapping: Mapping[str, Any] | None, language: str
) -> dict[str, str] | None:
    """Return the one-field probe record for ``language`` (rule 3), or ``None``.

    Only ``{"sha256": value}`` with a ``str`` value is returned, as a new dict.
    A missing entry, a non-Mapping record or a non-``str`` value gives ``None``:
    the caller must then report ``untrusted`` without calling the probe. The
    whole mapping, or the stored record, is never returned.
    """
    if not isinstance(mapping, Mapping):
        return None
    record = mapping.get(language)
    if not isinstance(record, Mapping):
        return None
    digest = record.get("sha256")
    if not isinstance(digest, str):
        return None
    return {"sha256": digest}
