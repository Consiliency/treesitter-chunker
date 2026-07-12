"""Integrity checks for grammar download artifacts."""

import hashlib
import hmac
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class ArtifactIntegrityError(ValueError):
    """Raised when an artifact is not covered by trusted provenance."""


def verify_artifact(path: Path, provenance: Mapping[str, Any]) -> None:
    """Verify ``path`` against its repo-owned SHA-256 provenance entry."""
    expected = provenance.get("sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        raise ArtifactIntegrityError("Artifact provenance requires a SHA-256 checksum")
    if not path.is_file():
        raise ArtifactIntegrityError(f"Artifact does not exist: {path}")

    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for block in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(block)
    if not hmac.compare_digest(digest.hexdigest(), expected.lower()):
        raise ArtifactIntegrityError(
            "Artifact checksum does not match trusted provenance"
        )
