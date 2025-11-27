# V3 Consistency Completion Specification

**Version**: 1.0
**Status**: Draft
**Created**: 2025-11-27
**Purpose**: Address remaining consistency gaps from v2-hardening code review

---

## 1. Overview

This specification addresses three remaining consistency issues identified during code review after implementing v2-hardening-and-agent-integration-spec.md phases 1-6:

1. **JSON Loading Consistency**: Migrate remaining unprotected `json.load()` calls to centralized utilities
2. **Safe Decode Migration**: Replace direct `.decode("utf-8")` calls with centralized `safe_decode()`
3. **Graph Model Rationalization**: Bridge dual graph models (Unified vs legacy) with deprecation path

### 1.1 Design Principles

- **Repurpose over create**: Use existing utilities (`chunker/utils/json.py`, `chunker/utils/text.py`)
- **Minimal changes**: Avoid restructuring; focus on consistency
- **Backward compatibility**: Maintain existing APIs; add deprecation warnings where appropriate
- **Test coverage**: All changes must maintain passing test suite

---

## 2. Phase 1: JSON Loading Consistency

### 2.1 Current State Analysis

**Existing utility** (`chunker/utils/json.py`):
```python
def load_json_file(path: Path | str) -> dict[str, Any]:
    """Load and parse JSON file with clear error reporting.

    Raises:
        ConfigurationError: If file cannot be read or contains invalid JSON
    """

def load_json_string(content: str, source: str = "<string>") -> dict[str, Any]:
    """Parse JSON from string with clear error reporting."""

def safe_json_loads(content: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse JSON with default fallback (non-raising)."""
```

**Files requiring migration** (core library only):

| File | Line | Current Pattern | Migration Strategy |
|------|------|-----------------|-------------------|
| `chunker/grammar/download.py` | 75 | `json.load(f)` | Replace with `load_json_file()` |
| `chunker/grammar/registry.py` | 62 | `json.load(f)` with try/except | Replace with `safe_json_loads()` or `load_json_file()` |
| `chunker/grammar/discovery.py` | 281 | `json.load(f)` with try/except | Replace with `safe_json_loads()` |
| `chunker/grammar/manager.py` | 363 | `json.load(f)` with try/except | Replace with `safe_json_loads()` |

**Out of scope** (acceptable as-is):
- Test files (`tests/*.py`)
- Benchmark files (`benchmarks/*.py`)
- Script files (`scripts/*.py`)
- Example files (`examples/*.py`)

### 2.2 Modifications

#### 2.2.1 `chunker/grammar/download.py`

**Before** (line 72-77):
```python
def _load_cache(self) -> None:
    """Load cache metadata"""
    if self._metadata_file.exists():
        with self._metadata_file.open() as f:
            self._metadata = json.load(f)
    else:
        self._metadata = {"grammars": {}, "version": "1.0"}
```

**After**:
```python
from chunker.utils.json import safe_json_loads

def _load_cache(self) -> None:
    """Load cache metadata"""
    if self._metadata_file.exists():
        try:
            content = self._metadata_file.read_text(encoding="utf-8")
            self._metadata = safe_json_loads(content, {"grammars": {}, "version": "1.0"})
        except OSError:
            self._metadata = {"grammars": {}, "version": "1.0"}
    else:
        self._metadata = {"grammars": {}, "version": "1.0"}
```

#### 2.2.2 `chunker/grammar/registry.py`

**Before** (line 57-65):
```python
def _load_metadata(self) -> dict[str, Any]:
    if self._metadata_path.exists():
        try:
            with self._metadata_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load metadata: %s", e)
    return {"installed": {}, "auto_downloaded": []}
```

**After**:
```python
from chunker.utils.json import safe_json_loads

def _load_metadata(self) -> dict[str, Any]:
    if self._metadata_path.exists():
        try:
            content = self._metadata_path.read_text(encoding="utf-8")
            return safe_json_loads(content, {"installed": {}, "auto_downloaded": []})
        except OSError as e:
            logger.warning("Failed to load metadata: %s", e)
    return {"installed": {}, "auto_downloaded": []}
```

#### 2.2.3 `chunker/grammar/discovery.py`

**Before** (line 276-284):
```python
def _load_cache(self) -> dict | None:
    if not self.cache_file or not self.cache_file.exists():
        return None
    try:
        with self.cache_file.open() as f:
            return json.load(f)
    except (FileNotFoundError, OSError):
        logger.exception("Failed to load cache")
        return None
```

**After**:
```python
from chunker.utils.json import safe_json_loads

def _load_cache(self) -> dict | None:
    if not self.cache_file or not self.cache_file.exists():
        return None
    try:
        content = self.cache_file.read_text(encoding="utf-8")
        return safe_json_loads(content, None)
    except OSError:
        logger.exception("Failed to load cache")
        return None
```

#### 2.2.4 `chunker/grammar/manager.py`

**Before** (line 358-374):
```python
def _load_config(self) -> None:
    if not self._config_file.exists():
        return
    try:
        with Path(self._config_file).open(encoding="utf-8") as f:
            data = json.load(f)
        for name, info in data.items():
            # ... process data
    except (OSError, json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning("Failed to load grammar config: %s", e)
```

**After**:
```python
from chunker.utils.json import safe_json_loads

def _load_config(self) -> None:
    if not self._config_file.exists():
        return
    try:
        content = Path(self._config_file).read_text(encoding="utf-8")
        data = safe_json_loads(content, {})
        for name, info in data.items():
            # ... process data
    except (OSError, TypeError, KeyError) as e:
        logger.warning("Failed to load grammar config: %s", e)
```

---

## 3. Phase 2: Safe Decode Migration

### 3.1 Current State Analysis

**Existing utility** (`chunker/utils/text.py`):
```python
def safe_decode(
    data: bytes | None,
    encoding: str = "utf-8",
    errors: str = "replace",
) -> str:
    """Safely decode bytes to string with fallback handling."""
```

**Files with direct `.decode("utf-8")` calls** (language plugins):

| File | Count | Pattern Type |
|------|-------|--------------|
| `chunker/languages/ruby_plugin.py` | 8 | `node.text.decode("utf-8")` |
| `chunker/languages/typescript.py` | 7 | `source[start:end].decode("utf-8")` |
| `chunker/languages/wasm.py` | 7 | `source[start:end].decode("utf-8")` |
| `chunker/languages/elixir.py` | 7 | `source[start:end].decode("utf-8")` |
| `chunker/languages/svelte.py` | 6 | `source[start:end].decode("utf-8")` |
| `chunker/languages/scala.py` | 4 | `source[start:end].decode("utf-8")` |
| `chunker/languages/php.py` | 3 | `source[start:end].decode("utf-8")` |
| `chunker/languages/javascript.py` | 3 | `source[start:end].decode("utf-8")` |
| `chunker/languages/dockerfile.py` | 2 | `source[start:end].decode("utf-8")` |
| `chunker/languages/yaml.py` | 1 | `source[start:end].decode("utf-8")` |
| `chunker/languages/xml.py` | 1 | `source[start:end].decode("utf-8")` |
| `chunker/languages/ruby.py` | 1 | Has local `_safe_decode` |

**Local implementations to remove**:
- `chunker/languages/ruby.py` lines 27-30: `_safe_decode()` function

### 3.2 Modifications

#### 3.2.1 Update `chunker/utils/text.py`

**Add new function** for byte slice decoding (common pattern):
```python
def safe_decode_bytes(
    data: bytes,
    errors: str = "replace",
) -> str:
    """Decode bytes to string with fallback for source[start:end] patterns.

    This is a simplified version of safe_decode() for the common pattern
    of decoding byte slices from source code. Unlike safe_decode(), this
    function assumes data is always bytes (not None).

    Args:
        data: Bytes to decode.
        errors: Error handling strategy ('replace', 'ignore', 'strict').

    Returns:
        Decoded UTF-8 string.

    Example:
        >>> name = safe_decode_bytes(source[node.start_byte:node.end_byte])
    """
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        logger.warning("Invalid UTF-8 encoding; using '%s' error handling", errors)
        return data.decode("utf-8", errors=errors)
```

**Update `__all__`**:
```python
__all__ = ["safe_decode", "safe_encode", "safe_decode_bytes"]
```

#### 3.2.2 Migration Pattern for Language Plugins

**Before**:
```python
name = source[child.start_byte : child.end_byte].decode("utf-8")
```

**After**:
```python
from chunker.utils.text import safe_decode_bytes

name = safe_decode_bytes(source[child.start_byte : child.end_byte])
```

#### 3.2.3 Remove Local `_safe_decode` from `ruby.py`

**Delete** lines 27-30:
```python
def _safe_decode(data: bytes | None) -> str:
    if data is None:
        return ""
    return data.decode("utf-8")
```

**Replace usage** with import from `chunker.utils.text`:
```python
from chunker.utils.text import safe_decode
```

### 3.3 Files to Modify

| File | Changes |
|------|---------|
| `chunker/utils/text.py` | Add `safe_decode_bytes()` function |
| `chunker/languages/ruby.py` | Remove local `_safe_decode`, import from utils |
| `chunker/languages/typescript.py` | Import and use `safe_decode_bytes` |
| `chunker/languages/wasm.py` | Import and use `safe_decode_bytes` |
| `chunker/languages/elixir.py` | Import and use `safe_decode_bytes` |
| `chunker/languages/svelte.py` | Import and use `safe_decode_bytes` |
| `chunker/languages/scala.py` | Import and use `safe_decode_bytes` |
| `chunker/languages/php.py` | Import and use `safe_decode_bytes` |
| `chunker/languages/javascript.py` | Import and use `safe_decode_bytes` |
| `chunker/languages/dockerfile.py` | Import and use `safe_decode_bytes` |
| `chunker/languages/yaml.py` | Import and use `safe_decode_bytes` |
| `chunker/languages/xml.py` | Import and use `safe_decode_bytes` |
| `chunker/languages/ruby_plugin.py` | Import and use `safe_decode` for `node.text` |

---

## 4. Phase 3: Graph Model Rationalization

### 4.1 Current State Analysis

**Unified model** (`chunker/export/graph_exporter_base.py`):
```python
@dataclass
class UnifiedGraphNode:
    """Unified graph node - matches build_xref output schema."""
    id: str
    file: str
    lang: str
    symbol: str | None
    kind: str
    attrs: dict[str, Any]

    def to_dict() -> dict[str, Any]
    def from_dict(data: dict) -> UnifiedGraphNode
    def from_chunk(chunk: CodeChunk) -> UnifiedGraphNode

@dataclass
class UnifiedGraphEdge:
    """Unified graph edge - matches build_xref output schema."""
    src: str
    dst: str
    type: str
    weight: float = 1.0

    def to_dict() -> dict[str, Any]
    def from_dict(data: dict) -> UnifiedGraphEdge
```

**Legacy model** (`chunker/export/graph_exporter_base.py`):
```python
class GraphNode:
    """Legacy node - used by GraphML/DOT exporters."""
    id: str  # Format: "{file_path}:{start_line}:{end_line}"
    chunk: CodeChunk
    label: str
    properties: dict[str, Any]

class GraphEdge:
    """Legacy edge - different field names from Unified."""
    source_id: str
    target_id: str
    relationship_type: str
    properties: dict[str, Any]
```

**Consumers**:
- `UnifiedGraphNode/Edge`: Used by `build_xref()`, API responses (returns dicts)
- `GraphNode/Edge`: Used by `GraphExporterBase`, `GraphMLExporter`, `DOTExporter`

### 4.2 Modifications

#### 4.2.1 Add Deprecation Warning to Legacy Classes

**Update `GraphNode` docstring**:
```python
class GraphNode:
    """Represents a node in the graph.

    .. deprecated::
        This class is deprecated. For new code, use :class:`UnifiedGraphNode`
        which provides a consistent schema across xref, GraphCut, exporters,
        and APIs. Use :meth:`to_unified` to convert to the new format.
    """
```

**Update `GraphEdge` docstring**:
```python
class GraphEdge:
    """Represents an edge between nodes in the graph.

    .. deprecated::
        This class is deprecated. For new code, use :class:`UnifiedGraphEdge`
        which provides a consistent schema. Use :meth:`to_unified` to convert.
    """
```

#### 4.2.2 Add Bridge Methods

**Add to `GraphNode`**:
```python
def to_unified(self) -> UnifiedGraphNode:
    """Convert to UnifiedGraphNode format.

    Returns:
        UnifiedGraphNode with equivalent data.
    """
    return UnifiedGraphNode(
        id=self.chunk.node_id or self.chunk.chunk_id or self.id,
        file=str(self.chunk.file_path),
        lang=self.chunk.language,
        symbol=self.chunk.symbol_id,
        kind=self.chunk.node_type,
        attrs=self.properties,
    )
```

**Add to `GraphEdge`**:
```python
def to_unified(self) -> UnifiedGraphEdge:
    """Convert to UnifiedGraphEdge format.

    Returns:
        UnifiedGraphEdge with equivalent data.
    """
    return UnifiedGraphEdge(
        src=self.source_id,
        dst=self.target_id,
        type=self.relationship_type,
        weight=float(self.properties.get("weight", 1.0)),
    )
```

### 4.3 Future Work (Out of Scope)

The following changes are deferred to a future specification:
- Migrate `GraphExporterBase.add_chunks()` to use `UnifiedGraphNode`
- Migrate `GraphMLExporter` and `DOTExporter` to use Unified types
- Remove legacy `GraphNode`/`GraphEdge` classes

---

## 5. Testing Requirements

### 5.1 Existing Tests

All existing tests must continue to pass:
```bash
python -m pytest tests/ -v
```

### 5.2 New Test Coverage

#### 5.2.1 `tests/test_json_utils.py` (existing file)

Verify existing tests cover the usage patterns.

#### 5.2.2 `tests/test_text_utils.py` (new tests)

```python
def test_safe_decode_bytes_valid_utf8():
    """Test safe_decode_bytes with valid UTF-8."""
    data = b"hello world"
    assert safe_decode_bytes(data) == "hello world"

def test_safe_decode_bytes_invalid_utf8():
    """Test safe_decode_bytes with invalid UTF-8 uses replacement."""
    data = b"hello \xff world"
    result = safe_decode_bytes(data)
    assert "hello" in result
    assert "world" in result

def test_safe_decode_bytes_empty():
    """Test safe_decode_bytes with empty bytes."""
    assert safe_decode_bytes(b"") == ""
```

#### 5.2.3 `tests/test_graph_exporter_base.py` (new tests)

```python
def test_graph_node_to_unified():
    """Test GraphNode.to_unified() conversion."""
    chunk = CodeChunk(...)
    node = GraphNode(chunk)
    unified = node.to_unified()
    assert isinstance(unified, UnifiedGraphNode)
    assert unified.file == chunk.file_path

def test_graph_edge_to_unified():
    """Test GraphEdge.to_unified() conversion."""
    edge = GraphEdge("src", "dst", "CALLS", {"weight": 2.0})
    unified = edge.to_unified()
    assert isinstance(unified, UnifiedGraphEdge)
    assert unified.src == "src"
    assert unified.dst == "dst"
    assert unified.type == "CALLS"
    assert unified.weight == 2.0
```

---

## 6. Implementation Order

1. **Phase 1**: JSON Loading (low risk, ~30 min)
   - Update 4 grammar module files
   - Run tests to verify

2. **Phase 2**: Safe Decode (medium risk, ~1 hour)
   - Add `safe_decode_bytes()` to `chunker/utils/text.py`
   - Remove local `_safe_decode` from `ruby.py`
   - Migrate 12 language plugin files
   - Run tests to verify

3. **Phase 3**: Graph Model (low risk, ~30 min)
   - Add deprecation docstrings
   - Add `to_unified()` bridge methods
   - Add tests for bridge methods
   - Run tests to verify

---

## 7. Rollback Plan

If issues arise during implementation:

1. **Phase 1 rollback**: Revert to `json.load()` calls - functionally equivalent
2. **Phase 2 rollback**: Revert to `.decode("utf-8")` calls - functionally equivalent
3. **Phase 3 rollback**: Remove bridge methods - no breaking changes

All changes are additive or simple replacements with no API changes.

---

## 8. Success Criteria

- [ ] All 4 JSON loading files migrated to centralized utilities
- [ ] All ~50 decode calls migrated to `safe_decode_bytes()`
- [ ] Local `_safe_decode` removed from `ruby.py`
- [ ] `GraphNode.to_unified()` method added
- [ ] `GraphEdge.to_unified()` method added
- [ ] Deprecation warnings added to legacy graph classes
- [ ] All existing tests pass
- [ ] New tests added for bridge methods
