"""Boundary IR public API.

This module is the single supported import surface for Boundary IR consumers
(``spec``, greenfield, Code-Index-MCP, codegraph-de). Import from
``chunker.boundary`` only -- never from the submodules (``adapter``,
``serialization``, ``identity``, ...), whose internal layout is not part of the
contract and may change without a major bump.

Frozen public surface (the interface P3 freezes; changing it requires a MAJOR
release):

Extraction
    - ``extract_boundary_ir`` -- emit a Boundary IR document.
    - ``dumps_boundary_ir`` -- canonical JSON text of a Boundary IR document.

Canonicalization
    - ``canonicalize_boundary_ir`` -- canonicalize a Boundary IR dict (the
      full emitted document, volatile fields retained).

Parity hashing (added in P1; the surface ``spec`` hashes against)
    - ``canonicalize_for_parity`` -- parity-hashable view (volatile fields
      stripped, floats pre-stringified).
    - ``canonicalize_for_parity_bytes`` -- canon canonical UTF-8 bytes of the
      parity view (cross-tool byte-identity).
    - ``parity_digest`` -- SHA-256 canon digest (hex) of the parity view.

Identity
    - ``select_node_identity`` -- Tier-2 node-identity precedence selection.

Schema + versions
    - ``BOUNDARY_IR_SCHEMA_VERSION`` (document schema_version, "2.0").
    - ``BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION`` ("2.1").
    - ``BOUNDARY_IR_SCHEMA_PATH`` / ``load_boundary_ir_schema`` -- the published
      machine-readable JSON Schema (``boundary_ir.schema.json``, packaged in the
      wheel) so consumers can validate documents and detect drift.

The remaining exported constants/types (cache keys, resolution/diagnostic
vocabularies, semantic resolver types) are stable supporting symbols.

The public surface is versioned by ``BOUNDARY_PUBLIC_API_VERSION`` below. It is
bumped only when this surface changes (P3's MAJOR release); it is independent of
the package version and of ``BOUNDARY_IR_SCHEMA_VERSION``.
"""

from importlib import resources

from .adapter import extract_boundary_ir
from .identity import select_node_identity
from .serialization import (
    canonicalize_boundary_ir,
    canonicalize_for_parity,
    canonicalize_for_parity_bytes,
    dumps_boundary_ir,
    parity_digest,
)
from .semantic import SemanticEdge, SemanticResolver, SemanticResolverContext
from .types import (
    BOUNDARY_CACHE_EXCLUDED_OPTION_FIELDS,
    BOUNDARY_CACHE_KEY_FIELDS,
    BOUNDARY_CACHE_KEY_PREFIX,
    BOUNDARY_CACHE_VERSION,
    BOUNDARY_IR_SCHEMA_VERSION,
    BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION,
    DIAGNOSTIC_SEVERITIES,
    DIAGNOSTIC_STAGES,
    FILE_STATUSES,
    METRIC_KEYS,
    RESOLUTION_MODES,
    RESOLUTION_STATUSES,
    SEMANTIC_EDGE_SOURCES,
    SEMANTIC_RESOLVER_API_VERSION,
    TIMING_KEYS,
    ResolutionMode,
    ResolutionStatus,
    SemanticEdgeSource,
)

# Version of the pinned public surface (the set of names exported below and
# documented in the module docstring). Independent of the package version and of
# BOUNDARY_IR_SCHEMA_VERSION; bumped only when this surface changes (P3 MAJOR).
BOUNDARY_PUBLIC_API_VERSION = "1.0"

# Packaged machine-readable JSON Schema for the emitted Boundary IR document.
BOUNDARY_IR_SCHEMA_FILENAME = "boundary_ir.schema.json"
BOUNDARY_IR_SCHEMA_PATH = resources.files(__name__) / BOUNDARY_IR_SCHEMA_FILENAME


def load_boundary_ir_schema() -> dict:
    """Return the published Boundary IR JSON Schema as a dict.

    Consumers can validate emitted documents against this to detect drift. The
    schema ships in the wheel (see ``[tool.setuptools.package-data]``).
    """
    import json

    return json.loads(
        BOUNDARY_IR_SCHEMA_PATH.read_text(encoding="utf-8"),
    )


__all__ = [
    "BOUNDARY_IR_SCHEMA_VERSION",
    "BOUNDARY_IR_SCHEMA_FILENAME",
    "BOUNDARY_IR_SCHEMA_PATH",
    "BOUNDARY_PUBLIC_API_VERSION",
    "load_boundary_ir_schema",
    "BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION",
    "BOUNDARY_CACHE_EXCLUDED_OPTION_FIELDS",
    "BOUNDARY_CACHE_KEY_FIELDS",
    "BOUNDARY_CACHE_KEY_PREFIX",
    "BOUNDARY_CACHE_VERSION",
    "DIAGNOSTIC_SEVERITIES",
    "DIAGNOSTIC_STAGES",
    "FILE_STATUSES",
    "METRIC_KEYS",
    "RESOLUTION_MODES",
    "RESOLUTION_STATUSES",
    "ResolutionMode",
    "ResolutionStatus",
    "SEMANTIC_EDGE_SOURCES",
    "SEMANTIC_RESOLVER_API_VERSION",
    "SemanticEdge",
    "SemanticEdgeSource",
    "SemanticResolver",
    "SemanticResolverContext",
    "TIMING_KEYS",
    "canonicalize_boundary_ir",
    "canonicalize_for_parity",
    "canonicalize_for_parity_bytes",
    "dumps_boundary_ir",
    "extract_boundary_ir",
    "parity_digest",
    "select_node_identity",
]
