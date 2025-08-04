"""Internal implementation details for treesitter-chunker.

This module contains internal implementation details that are not part of the public API.
Users should not import from this module directly as the internal structure may change
without notice between versions.
"""

# Internal modules - not part of the public API
from . import cache, factory, gc_tuning, registry, vfs

__all__ = []  # No public exports from internal modules
