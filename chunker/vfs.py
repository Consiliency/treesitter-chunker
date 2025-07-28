"""Virtual File System support for Tree-sitter Chunker.

This module provides abstractions for working with various file systems,
including local files, in-memory files, zip archives, and remote repositories.
"""

from __future__ import annotations

import io
import os
import urllib.parse
import urllib.request
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass
class VirtualFile:
    """Represents a file in a virtual file system."""

    path: str
    size: int
    is_dir: bool
    mtime: float | None = None


class VirtualFileSystem(ABC):
    """Abstract base class for virtual file systems."""

    @abstractmethod
    def open(self, path: str, mode: str = "r") -> io.IOBase:
        """Open a file in the virtual file system."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if a path exists in the virtual file system."""

    @abstractmethod
    def is_file(self, path: str) -> bool:
        """Check if a path is a file."""

    @abstractmethod
    def is_dir(self, path: str) -> bool:
        """Check if a path is a directory."""

    @abstractmethod
    def list_dir(self, path: str = "/") -> Iterator[VirtualFile]:
        """List contents of a directory."""

    @abstractmethod
    def get_size(self, path: str) -> int:
        """Get the size of a file."""

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """Read text content of a file."""
        with self.open(path, "r") as f:
            if hasattr(f, "read"):
                content = f.read()
                if isinstance(content, bytes):
                    return content.decode(encoding)
                return content
            # Handle binary mode
            return f.read().decode(encoding)

    def read_bytes(self, path: str) -> bytes:
        """Read binary content of a file."""
        with self.open(path, "rb") as f:
            return f.read()


class LocalFileSystem(VirtualFileSystem):
    """Virtual file system for local files."""

    def __init__(self, root_path: Path | None = None):
        """Initialize with optional root path for sandboxing."""
        self.root = Path(root_path) if root_path else Path("/")

    def _resolve_path(self, path: str) -> Path:
        """Resolve a virtual path to actual path."""
        if os.path.isabs(path):
            return Path(path)
        return self.root / path

    def open(self, path: str, mode: str = "r") -> io.IOBase:
        """Open a local file."""
        resolved = self._resolve_path(path)
        return open(resolved, mode)

    def exists(self, path: str) -> bool:
        """Check if a local path exists."""
        return self._resolve_path(path).exists()

    def is_file(self, path: str) -> bool:
        """Check if a local path is a file."""
        return self._resolve_path(path).is_file()

    def is_dir(self, path: str) -> bool:
        """Check if a local path is a directory."""
        return self._resolve_path(path).is_dir()

    def list_dir(self, path: str = "/") -> Iterator[VirtualFile]:
        """List contents of a local directory."""
        resolved = self._resolve_path(path)
        if not resolved.is_dir():
            return

        for item in resolved.iterdir():
            stat = item.stat()
            yield VirtualFile(
                path=str(
                    item.relative_to(self.root) if self.root != Path("/") else item,
                ),
                size=stat.st_size if item.is_file() else 0,
                is_dir=item.is_dir(),
                mtime=stat.st_mtime,
            )

    def get_size(self, path: str) -> int:
        """Get the size of a local file."""
        return self._resolve_path(path).stat().st_size


class InMemoryFileSystem(VirtualFileSystem):
    """Virtual file system that stores files in memory."""

    def __init__(self):
        """Initialize empty in-memory file system."""
        self.files: dict[str, bytes | str] = {}
        self.metadata: dict[str, VirtualFile] = {}

    def add_file(self, path: str, content: str | bytes, is_text: bool = True):
        """Add a file to the in-memory file system."""
        self.files[path] = content
        size = len(content) if isinstance(content, bytes) else len(content.encode())
        self.metadata[path] = VirtualFile(
            path=path,
            size=size,
            is_dir=False,
        )

    def open(self, path: str, mode: str = "r") -> io.IOBase:
        """Open an in-memory file."""
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")

        content = self.files[path]

        if "b" in mode:
            if isinstance(content, str):
                content = content.encode()
            return io.BytesIO(content)
        if isinstance(content, bytes):
            content = content.decode()
        return io.StringIO(content)

    def exists(self, path: str) -> bool:
        """Check if a path exists in memory."""
        return path in self.files

    def is_file(self, path: str) -> bool:
        """Check if a path is a file."""
        return path in self.files

    def is_dir(self, path: str) -> bool:
        """Check if a path is a directory."""
        # Root is always a directory
        if path in {"/", ""}:
            return True
        # Simple implementation - check if any file has this as prefix
        if path in self.files:
            return False
        path_prefix = path.rstrip("/") + "/"
        return any(f.startswith(path_prefix) for f in self.files)

    def list_dir(self, path: str = "/") -> Iterator[VirtualFile]:
        """List contents of a directory."""
        # Normalize path
        path = path.rstrip("/")
        if path == "":
            path = "/"

        if path == "/":
            path_prefix = ""
        else:
            path_prefix = path + "/"

        seen_dirs = set()

        for file_path in sorted(self.files.keys()):
            # Remove leading slash for comparison
            normalized_file_path = file_path.lstrip("/")

            if path == "/" or normalized_file_path.startswith(path_prefix.lstrip("/")):
                # Calculate relative path
                if path == "/":
                    relative = normalized_file_path
                else:
                    relative = normalized_file_path[len(path_prefix.lstrip("/")) :]

                if "/" in relative:
                    # It's in a subdirectory
                    dir_name = relative.split("/")[0]
                    if dir_name not in seen_dirs:
                        seen_dirs.add(dir_name)
                        dir_path = (path_prefix + dir_name).lstrip("/")
                        yield VirtualFile(
                            path=dir_path,
                            size=0,
                            is_dir=True,
                        )
                else:
                    # Direct file
                    yield self.metadata[file_path]

    def get_size(self, path: str) -> int:
        """Get the size of a file."""
        if path in self.metadata:
            return self.metadata[path].size
        raise FileNotFoundError(f"File not found: {path}")


class ZipFileSystem(VirtualFileSystem):
    """Virtual file system for ZIP archives."""

    def __init__(self, zip_path: str | Path):
        """Initialize with path to ZIP file."""
        self.zip_path = Path(zip_path)
        self.zip_file = zipfile.ZipFile(self.zip_path, "r")
        self._build_index()

    def _build_index(self):
        """Build an index of files in the ZIP."""
        self.files = {}
        self.dirs = set()

        for info in self.zip_file.infolist():
            self.files[info.filename] = info
            # Track directories
            parts = info.filename.split("/")
            for i in range(1, len(parts)):
                self.dirs.add("/".join(parts[:i]))

    def open(self, path: str, mode: str = "r") -> io.IOBase:
        """Open a file in the ZIP archive."""
        if mode not in {"r", "rb"}:
            raise ValueError("ZIP file system is read-only")

        if path not in self.files:
            raise FileNotFoundError(f"File not found in ZIP: {path}")

        file_data = self.zip_file.read(path)

        if "b" in mode:
            return io.BytesIO(file_data)
        return io.StringIO(file_data.decode("utf-8"))

    def exists(self, path: str) -> bool:
        """Check if a path exists in the ZIP."""
        return path in self.files or path in self.dirs

    def is_file(self, path: str) -> bool:
        """Check if a path is a file."""
        return path in self.files

    def is_dir(self, path: str) -> bool:
        """Check if a path is a directory."""
        return path in self.dirs

    def list_dir(self, path: str = "/") -> Iterator[VirtualFile]:
        """List contents of a directory in the ZIP."""
        path = path.rstrip("/")
        if path == "":
            path_prefix = ""
        else:
            path_prefix = path + "/"

        seen = set()

        for file_path, info in self.files.items():
            if file_path.startswith(path_prefix):
                relative = file_path[len(path_prefix) :]
                if "/" in relative:
                    # It's in a subdirectory
                    dir_name = relative.split("/")[0]
                    if dir_name not in seen:
                        seen.add(dir_name)
                        yield VirtualFile(
                            path=path_prefix + dir_name,
                            size=0,
                            is_dir=True,
                        )
                else:
                    # Direct file
                    yield VirtualFile(
                        path=file_path,
                        size=info.file_size,
                        is_dir=False,
                        mtime=None,  # ZIP doesn't preserve mtime reliably
                    )

    def get_size(self, path: str) -> int:
        """Get the size of a file in the ZIP."""
        if path in self.files:
            return self.files[path].file_size
        raise FileNotFoundError(f"File not found in ZIP: {path}")

    def close(self):
        """Close the ZIP file."""
        self.zip_file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class HTTPFileSystem(VirtualFileSystem):
    """Virtual file system for HTTP/HTTPS resources (read-only)."""

    def __init__(self, base_url: str):
        """Initialize with base URL."""
        self.base_url = base_url.rstrip("/")
        self._cache = {}

    def _make_url(self, path: str) -> str:
        """Construct full URL from path."""
        if path.startswith(("http://", "https://")):
            return path
        path = path.lstrip("/")
        return f"{self.base_url}/{path}"

    def open(self, path: str, mode: str = "r") -> io.IOBase:
        """Open a file from HTTP."""
        if "w" in mode:
            raise ValueError("HTTP file system is read-only")

        url = self._make_url(path)

        # Check cache first
        if url in self._cache:
            content = self._cache[url]
        else:
            # Fetch from network
            with urllib.request.urlopen(url) as response:
                content = response.read()
                self._cache[url] = content

        if "b" in mode:
            return io.BytesIO(content)
        return io.StringIO(content.decode("utf-8"))

    def exists(self, path: str) -> bool:
        """Check if a URL is accessible."""
        url = self._make_url(path)
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req) as response:
                return response.status == 200
        except:
            return False

    def is_file(self, path: str) -> bool:
        """Assume all accessible paths are files in HTTP."""
        return self.exists(path)

    def is_dir(self, path: str) -> bool:
        """HTTP doesn't have directories in the traditional sense."""
        return False

    def list_dir(self, path: str = "/") -> Iterator[VirtualFile]:
        """HTTP doesn't support directory listing."""
        return iter([])

    def get_size(self, path: str) -> int:
        """Get the size of a file from HTTP headers."""
        url = self._make_url(path)
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req) as response:
            content_length = response.headers.get("Content-Length")
            if content_length:
                return int(content_length)
        return 0


class CompositeFileSystem(VirtualFileSystem):
    """Composite file system that can overlay multiple file systems."""

    def __init__(self):
        """Initialize empty composite file system."""
        self.filesystems: list[tuple[str, VirtualFileSystem]] = []

    def mount(self, prefix: str, filesystem: VirtualFileSystem):
        """Mount a file system at a given prefix."""
        prefix = prefix.rstrip("/")
        self.filesystems.append((prefix, filesystem))
        # Sort by prefix length (longest first) for proper matching
        self.filesystems.sort(key=lambda x: len(x[0]), reverse=True)

    def _find_filesystem(self, path: str) -> tuple[VirtualFileSystem, str]:
        """Find the file system responsible for a path."""
        for prefix, fs in self.filesystems:
            if path.startswith(prefix):
                relative_path = path[len(prefix) :].lstrip("/")
                return fs, relative_path
        raise FileNotFoundError(f"No filesystem mounted for path: {path}")

    def open(self, path: str, mode: str = "r") -> io.IOBase:
        """Open a file from the appropriate file system."""
        fs, relative_path = self._find_filesystem(path)
        return fs.open(relative_path, mode)

    def exists(self, path: str) -> bool:
        """Check if a path exists in any mounted file system."""
        try:
            fs, relative_path = self._find_filesystem(path)
            return fs.exists(relative_path)
        except FileNotFoundError:
            return False

    def is_file(self, path: str) -> bool:
        """Check if a path is a file."""
        fs, relative_path = self._find_filesystem(path)
        return fs.is_file(relative_path)

    def is_dir(self, path: str) -> bool:
        """Check if a path is a directory."""
        fs, relative_path = self._find_filesystem(path)
        return fs.is_dir(relative_path)

    def list_dir(self, path: str = "/") -> Iterator[VirtualFile]:
        """List contents from all applicable file systems."""
        yielded_paths = set()

        # Normalize path
        path = path.rstrip("/") or "/"

        for prefix, fs in self.filesystems:
            # Check if this filesystem could contain items under the requested path
            if path == "/" or path.startswith(prefix) or prefix.startswith(path):
                if path == "/":
                    # List items at root - check if prefix is at root level
                    if prefix.count("/") == 1:  # e.g., /memory, /local
                        # Add the mount point as a directory
                        if prefix not in yielded_paths:
                            yielded_paths.add(prefix)
                            yield VirtualFile(
                                path=prefix,
                                size=0,
                                is_dir=True,
                                mtime=None,
                            )
                elif path.startswith(prefix):
                    # Path is within this mount point
                    relative_path = path[len(prefix) :].lstrip("/")
                    for vf in fs.list_dir(relative_path if relative_path else "/"):
                        # Adjust path to include prefix
                        if vf.path.startswith("/"):
                            full_path = f"{prefix}{vf.path}"
                        else:
                            full_path = f"{prefix}/{vf.path}"
                        full_path = full_path.replace("//", "/")

                        if full_path not in yielded_paths:
                            yielded_paths.add(full_path)
                            yield VirtualFile(
                                path=full_path,
                                size=vf.size,
                                is_dir=vf.is_dir,
                                mtime=vf.mtime,
                            )

    def get_size(self, path: str) -> int:
        """Get the size of a file."""
        fs, relative_path = self._find_filesystem(path)
        return fs.get_size(relative_path)


# Factory function for creating file systems
def create_vfs(path_or_url: str) -> VirtualFileSystem:
    """Create appropriate VFS based on path/URL."""
    if path_or_url.startswith(("http://", "https://")):
        return HTTPFileSystem(path_or_url)
    if path_or_url.endswith(".zip"):
        return ZipFileSystem(path_or_url)
    return LocalFileSystem(path_or_url)
