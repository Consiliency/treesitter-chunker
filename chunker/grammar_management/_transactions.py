"""Single-host cache transaction helpers (IF-0-TXNSPEC-1 signatures only).

The contract lives in ``docs/development/cache-transaction-contract.md``.
This module is a signature-only stub: every callable raises
``NotImplementedError`` until phase TXN implements it. No production code
imports it yet. Module-level imports are restricted to the standard library so
core-unavailable fallbacks can use it later.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

DEFAULT_LOCK_TIMEOUT: Final[float] = 30.0
LOCK_FILE_NAME: Final[str] = ".txn.lock"
CONTROL_DIR_NAME: Final[str] = ".txn"

Namespace = Literal["downloads", "builds"]

_NOT_IMPLEMENTED: Final[str] = "IF-0-TXNSPEC-1 stub; implemented in phase TXN"

# Private test seam (contract "Test seam"). ``None`` in production.
_BARRIER: Callable[[str], None] | None = None


class CacheTransactionError(Exception):
    """A transaction step could not complete; nothing was changed by it."""


class CacheLockTimeoutError(CacheTransactionError):
    """The root lock was not acquired within the bounded timeout."""


class ContainmentError(CacheTransactionError):
    """A path below the root is a link, junction, non-regular or outside it."""


@dataclass(frozen=True)
class StagingArea:
    """One writer operation's private ``.txn/staging/<operation-id>/``."""

    root: Path
    operation_id: str
    path: Path


@dataclass(frozen=True)
class PruneResult:
    """Truthful outcome of a retire-then-delete call."""

    entries_removed: int
    bytes_freed: int
    skipped: tuple[str, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class RollbackPoint:
    """Restorable copies of an installation captured before an update."""

    root: Path
    operation_id: str
    language: str
    path: Path
    artifact: Path
    artifact_sha256: str | None
    metadata: Path
    metadata_sha256: str | None


@dataclass(frozen=True)
class RestoreResult:
    """Outcome of restoring a rollback point."""

    restored: bool
    artifact_restored: bool
    metadata_restored: bool
    superseded: bool
    errors: tuple[str, ...]


def open_cache_root(root: Path) -> Path:
    """Validate ``root``, create its lock file and control area no-follow."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def cache_lock(
    root: Path, *, timeout: float = DEFAULT_LOCK_TIMEOUT
) -> AbstractContextManager[None]:
    """Hold the root's exclusive, process-reentrant transaction lock."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def read_json_records(
    root: Path, name: str, *, timeout: float = DEFAULT_LOCK_TIMEOUT
) -> dict[str, Any]:
    """Read one root-level JSON object under the lock, no-follow."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def update_json_records(
    root: Path,
    name: str,
    mutate: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    reset_malformed: bool = False,
    timeout: float = DEFAULT_LOCK_TIMEOUT,
) -> dict[str, Any]:
    """Fresh-read, merge and atomically replace one root-level JSON object."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def create_staging(root: Path, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> StagingArea:
    """Register a new operation-private staging directory."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def publish_entry(
    staging: StagingArea,
    namespace: Namespace,
    name: str,
    *,
    timeout: float = DEFAULT_LOCK_TIMEOUT,
) -> Path:
    """Retire any existing entry and rename the staged entry into place."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def discard_staging(
    staging: StagingArea, *, timeout: float = DEFAULT_LOCK_TIMEOUT
) -> PruneResult:
    """Remove this operation's own staging and retired bytes."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def remove_entry(
    root: Path,
    namespace: Namespace,
    name: str,
    *,
    timeout: float = DEFAULT_LOCK_TIMEOUT,
) -> PruneResult:
    """Explicitly retire then delete one published entry."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def prune_entries(
    root: Path,
    namespace: Namespace,
    *,
    cutoff: float,
    timeout: float = DEFAULT_LOCK_TIMEOUT,
) -> PruneResult:
    """Age-prune entries with a locked deletion-time re-check."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def create_rollback_point(
    root: Path,
    *,
    language: str,
    artifact: Path,
    metadata: Path,
    timeout: float = DEFAULT_LOCK_TIMEOUT,
) -> RollbackPoint:
    """Copy the current artifact and metadata into a rollback point."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def restore(
    point: RollbackPoint,
    *,
    published_artifact_sha256: str | None,
    published_metadata_sha256: str | None,
    provenance: Mapping[str, Any] | None,
    invalidate: Callable[[Path], None],
    timeout: float = DEFAULT_LOCK_TIMEOUT,
) -> RestoreResult:
    """Restore the rollback point through IF-0-HOTFIX-1 ``publish_native_grammar``."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def discard_rollback_point(
    point: RollbackPoint, *, timeout: float = DEFAULT_LOCK_TIMEOUT
) -> None:
    """Remove a rollback point after success or a verified restore."""
    raise NotImplementedError(_NOT_IMPLEMENTED)
