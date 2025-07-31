"""Virtual File System support for tree-sitter chunker.

This module provides a public interface to the VFS functionality,
allowing users to work with different file sources (local, HTTP, ZIP, etc.).
"""

# Re-export the VFS classes from internal module
from ._internal.vfs import (
    VirtualFileSystem,
    LocalFileSystem,
    HTTPFileSystem,
    ZipFileSystem,
    InMemoryFileSystem,
    CompositeFileSystem,
    create_vfs,
)

__all__ = [
    "VirtualFileSystem",
    "LocalFileSystem", 
    "HTTPFileSystem",
    "ZipFileSystem",
    "InMemoryFileSystem",
    "CompositeFileSystem",
    "create_vfs",
]