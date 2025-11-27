## v4 Pre‑Production Finalization and Consistency Spec

- **File**: `specs/v4-preprod-finalization-spec.md`
- **Owner**: Core Chunker Team
- **Status**: Draft
- **Scope**:
  - Finish remaining consistency work from v2/v3 specs before first production deployment.
  - Tighten failure semantics for configs and data paths.
  - Clean up remaining direct `.decode("utf-8")` and `json.load(...)` in core library code.
  - Clarify and, where reasonable, narrow the “public” API surface before committing to backward compatibility.
  - Prefer **modifying existing code** (utilities, language plugins, grammar/config modules, exporters, APIs) over adding new modules.

---

## 0. Design Principles

- **Reuse over duplication**: Prefer `chunker/utils/text.py` and `chunker/utils/json.py` rather than local helpers.
- **Fail fast while pre‑prod**: Surface invalid configs/data as explicit exceptions; only use silent fallbacks where strongly justified.
- **Backwards compatible by default**: Do not change signatures of exported functions/classes in `chunker/__init__.py` or HTTP endpoints unless necessary; add deprecations instead of silent removals.
- **Security first**: Preserve guarantees from `tests/test_security.py` (no `shell=True`, no bare `except:`, presence of escape/parameterization helpers).

---

## 1. Phase 1 – Complete Safe Decode Migration

**Goal**: Replace remaining direct `.decode("utf-8")` calls in library modules with centralized helpers from `chunker/utils/text.py`, ensuring consistent behavior and logging for encoding issues.

### 1.1 Existing Utility (no interface changes)

- **File**: `chunker/utils/text.py`
- **Functions** (already present; **no changes to signatures**):

```python
def safe_decode(
    data: bytes | None,
    encoding: str = "utf-8",
    errors: str = "replace",
) -> str: ...

def safe_encode(
    text: str | None,
    encoding: str = "utf-8",
    errors: str = "replace",
) -> bytes: ...

def safe_decode_bytes(
    data: bytes,
    errors: str = "replace",
) -> str: ...
```

- **Purpose**:
  - Use `safe_decode_bytes` for the common `source[start:end].decode("utf-8")` pattern.
  - Use `safe_decode` when decoding `node.text`, or when the value may already be `str`.

### 1.2 Language Plugins – Required Modifications

> **Note**: All changes below are internal and must not alter public APIs exported from `chunker/__init__.py`. We are only modifying implementations.

#### 1.2.1 `chunker/languages/clojure.py`

- **Imports**:
  - **Add**: `from chunker.utils.text import safe_decode_bytes`
- **Functions to change** (all internal helpers that currently call `.decode("utf-8")`):
  - Any code in this file resembling:

    ```python
    source[child.start_byte : child.end_byte].decode("utf-8")
    ```

  - **Change pattern**:

    ```python
    # Before
    name = source[child.start_byte : child.end_byte].decode("utf-8")

    # After
    name = safe_decode_bytes(source[child.start_byte : child.end_byte])
    ```

- **Interfaces**:
  - No public function/class signatures or return types change.
  - Only internal decoding behavior is made robust.

#### 1.2.2 `chunker/languages/go.py`

- **Imports**:
  - **Add**: `from chunker.utils.text import safe_decode_bytes`
- **Affected logic**:
  - Helper methods that extract names and package names, currently using:

    ```python
    name_node.text.decode("utf-8")
    ```

  - **Change pattern**:

    ```python
    # Before
    info["function_name"] = name_node.text.decode("utf-8")

    # After
    info["function_name"] = safe_decode_bytes(name_node.text)
    ```

    Apply the same for `receiver_type`, `type_name`, `package_name`.

- **Interfaces**: unchanged.

#### 1.2.3 `chunker/languages/vue.py`

- **Imports**:
  - **Add**: `from chunker.utils.text import safe_decode_bytes`
- **Affected logic**:
  - Node content and attribute extraction that currently do:

    ```python
    content = source[node.start_byte : node.end_byte].decode("utf-8")
    attr in child.text.decode("utf-8") ...
    ```

  - **Change pattern**:

    ```python
    content = safe_decode_bytes(source[node.start_byte : node.end_byte])

    attr in safe_decode_bytes(child.text) if hasattr(child, "text") else ""
    ```

- **Interfaces**: unchanged.

#### 1.2.4 `chunker/languages/zig.py`

- **Imports**:
  - **Add**: `from chunker.utils.text import safe_decode_bytes`
- **Affected logic**:
  - Any helper that returns `source[child.start_byte : child.end_byte].decode("utf-8")`.
- **Change pattern**:

```python
return safe_decode_bytes(source[child.start_byte : child.end_byte])
```

- **Interfaces**: unchanged.

#### 1.2.5 `chunker/languages/haskell.py`

- **Imports**:
  - **Add**: `from chunker.utils.text import safe_decode_bytes`
- **Affected logic**:
  - Helper functions in this file that directly decode byte slices.
- **Change pattern**: same as previous sections.

#### 1.2.6 `chunker/languages/sql.py`

- **Imports**:
  - **Add**: `from chunker.utils.text import safe_decode_bytes`
- **Affected logic**:
  - Any `source[child.start_byte : child.end_byte].decode("utf-8")` or similar.
- **Change pattern**: same as above.

#### 1.2.7 `chunker/languages/python.py`

- **Imports**:
  - **Add**: `from chunker.utils.text import safe_decode_bytes`
- **Affected logic**:
  - Helper that currently does:

    ```python
    return source[child.start_byte : child.end_byte].decode("utf-8")
    ```

  - **Change**:

    ```python
    return safe_decode_bytes(source[child.start_byte : child.end_byte])
    ```

#### 1.2.8 `chunker/languages/cs_plugin.py`

- **Imports**:
  - **Add**: `from chunker.utils.text import safe_decode_bytes`
- **Affected logic**:
  - Same pattern for extracting identifiers.
- **Change**: wrap with `safe_decode_bytes` as above.

#### 1.2.9 `chunker/languages/scala.py`

- **Imports**:
  - **Add**: `from chunker.utils.text import safe_decode_bytes`
- **Affected logic**:
  - All `source[child.start_byte : child.end_byte].decode("utf-8")` and node content decodes.

#### 1.2.10 `chunker/languages/java_plugin.py`

- **Imports**:
  - **Add**: `from chunker.utils.text import safe_decode_bytes`
- **Affected logic**:
  - Name extraction from `name_node.text.decode("utf-8")`.
  - Type and field name decodes.
- **Change pattern**:

```python
name = safe_decode_bytes(name_node.text)
type_str = safe_decode_bytes(type_node.text) if type_node else "?"
field_names.append(safe_decode_bytes(name.text))
```

#### 1.2.11 `chunker/languages/elixir.py` (remaining decode)

- Already partially migrated to `safe_decode_bytes`.
- **Method**: `_process_module_attribute(...)`
  - **Current**:

    ```python
    content = source[node.start_byte : node.end_byte].decode("utf-8")
    ```

  - **Change**:

    ```python
    content = safe_decode_bytes(source[node.start_byte : node.end_byte])
    ```

---

## 2. Phase 2 – JSON Loading Consistency (Remaining Sites)

**Goal**: Finish migrating user-facing and cache/config JSON reads to `load_json_file` / `safe_json_loads` where it improves clarity and robustness, while leaving internal or test-only uses untouched.

### 2.1 Existing Utility (no changes)

- **File**: `chunker/utils/json.py`
- **Functions**:

```python
def load_json_file(path: Path | str) -> dict[str, Any]: ...
def load_json_string(content: str, source: str = "<string>") -> dict[str, Any]: ...
def safe_json_loads(content: str, default: dict[str, Any] | None = None) -> dict[str, Any]: ...
```

### 2.2 `chunker/grammar/repository.py::_load_custom_repos`

- **File**: `chunker/grammar/repository.py`
- **Class**: `TreeSitterGrammarRepository(GrammarRepository)`
- **Current method**:

```python
def _load_custom_repos(self, repo_file: Path) -> None:
    """Load custom repository definitions."""
    try:
        with Path(repo_file).open("r", encoding="utf-8") as f:
            custom_repos = json.load(f)

        self._grammars.update(custom_repos)
        self._build_extension_map()
        logger.info("Loaded %s custom grammar repositories", len(custom_repos))
    except (ValueError, json.JSONDecodeError) as e:
        logger.error("Failed to load custom repositories: %s", e)
```

- **Change**:
  - **Imports**:
    - **Add**: `from chunker.utils.json import load_json_file`
  - **New implementation**:

```python
def _load_custom_repos(self, repo_file: Path) -> None:
    """Load custom repository definitions.

    Args:
        repo_file: Path to JSON file with custom repos.
    """
    try:
        custom_repos = load_json_file(repo_file)
        self._grammars.update(custom_repos)
        self._build_extension_map()
        logger.info(
            "Loaded %s custom grammar repositories",
            len(custom_repos),
        )
    except ConfigurationError as e:
        logger.error("Failed to load custom repositories from %s: %s", repo_file, e)
```

- **Interfaces**:
  - Method signature and return type remain `None`.
  - Behavior on invalid JSON becomes:
    - Clear error log via `ConfigurationError` raised by `load_json_file`.

### 2.3 `chunker/chunker_config.py::ChunkerConfig.load`

- **File**: `chunker/chunker_config.py`
- **Class**: `ChunkerConfig`
- **Method**: `load(self, config_path: Path) -> None`
  - Currently:
    - Uses `tomllib` for TOML, `yaml.safe_load` for YAML, and `json.load` for JSON.
    - Catches `FileNotFoundError`, `OSError`, `SyntaxError`, logs and re-raises.

- **Change (optional, but recommended pre‑prod)**:
  - Leave TOML/YAML logic as-is.
  - For JSON, switch to `load_json_file` for consistent error messaging:

```python
elif ext == ".json":
    self.data = load_json_file(config_path)
```

- **Interfaces**:
  - Signature unchanged.
  - Error messages become more specific when JSON is invalid.

### 2.4 `chunker/config/strategy_config.py::load_strategy_config`

- **File**: `chunker/config/strategy_config.py`
- **Function**: `load_strategy_config(path: str | Path) -> StrategyConfig`
- **Current**:

```python
if path.suffix == ".json":
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
elif path.suffix in {".yaml", ".yml"}:
    ...
else:
    raise ValueError(...)
return StrategyConfig.from_dict(data)
```

- **Change**:
  - **Imports**:
    - **Add**: `from chunker.utils.json import load_json_file`
  - **New JSON branch**:

```python
if path.suffix == ".json":
    data = load_json_file(path)
elif path.suffix in {".yaml", ".yml"}:
    ...
```

- **Interfaces**:
  - Input and output unchanged.
  - On invalid JSON, a `ConfigurationError` from `load_json_file` surfaces, which is appropriate pre‑prod.

---

## 3. Phase 3 – API & Public Surface Check (No Breaking Changes)

**Goal**: Confirm and codify which surfaces are “public” before production, and ensure our consistency changes do not alter them.

### 3.1 Python API

- **File**: `chunker/__init__.py`
  - **Public functions/types** of interest:
    - `chunk_file(...) -> list[CodeChunk]`
    - `chunk_text(...) -> list[CodeChunk]`
    - `chunk_directory(...)`, `chunk_files_parallel(...)` (if exported)
    - `CodeChunk` dataclass (from `chunker.types`)
    - Repo and incremental processors: `RepoProcessorImpl`, `GitAwareProcessorImpl`, `DefaultIncrementalProcessor`, etc.
  - **Plan**:
    - **Do not change function signatures** or return types as part of this spec.
    - Ensure docstrings and type hints still match `docs/api-reference.md`.

### 3.2 HTTP API

- **File**: `api/server.py`
  - Endpoints and models:
    - `POST /chunk/text` → `ChunkResult`
    - `POST /chunk/file` → `ChunkResult`
    - `POST /export/postgres` → `ExportPostgresResponse`
    - `POST /graph/xref` → `GraphResponse`
    - `POST /graph/cut` → `GraphCutResponse`
    - `POST /nearest-tests` → `NearestTestsResponse`
  - **Plan**:
    - No changes to Pydantic model fields or endpoint paths.
    - Only internal behavior (e.g., reliance on `compute_pack_hint`, `build_xref`, `graph_cut`) may evolve.

---

## 4. Phase 4 – End‑to‑End Validation (Pre‑Prod Checklist)

**Goal**: Validate the full pipeline on representative real‑world repositories now that decoding and JSON behaviors are consistent.

### 4.1 Repositories for Manual/Automated Runs

- At least one each of:
  - Python + JavaScript/TypeScript monorepo.
  - Mixed-language repo including Rust, Go, Java, and one functional language (Haskell or Elixir).

### 4.2 Flows to Exercise

1. **Core chunking**:
   - `chunk_file` and `chunk_text` across languages.
   - Confirm stable `node_id`/`file_id` and consistent spans.
2. **Streaming**:
   - `chunker/streaming.chunk_file_streaming(...)` vs `chunk_file(...)` ID/spans equivalence on large files.
3. **Repo processing**:
   - `RepoProcessor.process_repository(...)` (full and incremental).
   - `GitAwareRepoProcessor.get_changed_files(...)` correctness across branches.
   - `RepoProcessor.watch_repository(...)` deltas under edits/renames.
4. **Graph & APIs**:
   - `/graph/xref` + `/graph/cut` + `/nearest-tests` hit on a real repo.
   - `build_xref` → `PostgresExporter` / `postgres_spec_exporter.export(...)` round‑trip into a test Postgres instance.

### 4.3 Testing Requirements

- All existing tests:
  - `pytest -q -k "not integration"` (unit + fast integration).
  - Integration tests as configured (`-m integration`), especially:
    - `tests/test_phase12_integration.py`
    - `tests/test_performance_features.py`
    - `tests/test_intelligent_fallback.py`
    - `tests/test_security.py`
- New or extended tests (if needed) to:
  - Cover any newly migrated decode/json paths if not already indirectly covered.

---

## 5. Rollback Strategy

- Because changes are mostly internal (implementation details, not APIs), rollback risk is low:
  - For decode changes, reverting a file simply restores direct `.decode("utf-8")` semantics.
  - For JSON loader changes, reverting a file restores previous `json.load` + try/except behavior.
- If a regression is observed in a particular language plugin or config reader:
  - Revert that file only.
  - Re‑run targeted tests for that module plus `tests/test_security.py` to ensure no regressions on hardening guarantees.


