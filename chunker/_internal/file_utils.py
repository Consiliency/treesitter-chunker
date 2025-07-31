"""File utilities for internal use."""

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileMetadata:
    """Metadata about a file."""
    path: Path
    size: int
    hash: str
    mtime: float


def compute_file_hash(path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256_hash.update(chunk)
    
    return sha256_hash.hexdigest()


def get_file_metadata(path: Path) -> FileMetadata:
    """Get file metadata including size, hash, and modification time."""
    stat = path.stat()
    return FileMetadata(
        path=path,
        size=stat.st_size,
        hash=compute_file_hash(path),
        mtime=stat.st_mtime,
    )