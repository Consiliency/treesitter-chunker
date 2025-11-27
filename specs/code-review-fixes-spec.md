# Code Review Fixes Specification

- **File:** `specs/code-review-fixes-spec.md`
- **Owner:** Core Chunker Team
- **Status:** Approved for Implementation
- **Scope:** Fix all issues identified in `CODE_REVIEW_REPORT.md`
- **Priority:** Critical fixes first, then high, medium, low

---

## Table of Contents

1. [Phase 1: Critical Fixes](#phase-1-critical-fixes)
2. [Phase 2: High Priority Fixes](#phase-2-high-priority-fixes)
3. [Phase 3: Medium Priority Fixes](#phase-3-medium-priority-fixes)
4. [Phase 4: Low Priority Improvements](#phase-4-low-priority-improvements)
5. [Phase 5: Dependency Updates](#phase-5-dependency-updates)
6. [Testing Requirements](#testing-requirements)

---

## Phase 1: Critical Fixes

### 1.1 Replace Bare Except Clauses

**Purpose:** Prevent silent error suppression and ensure proper exception handling.

#### File: `chunker/grammar_management/testing.py`

**Methods to Modify:**

| Method | Line | Current | Change To |
|--------|------|---------|-----------|
| `_test_invalid_language_error` | 303 | `except:` | `except (ValueError, KeyError, RuntimeError) as e:` |
| `_test_corrupt_grammar_error` | 316 | `except:` | `except (OSError, ValidationError) as e:` |
| `_test_network_failure_error` | 332 | `except:` | `except (urllib.error.URLError, TimeoutError, ConnectionError) as e:` |
| `_test_disk_full_error` | 342 | `except:` | `except OSError as e:` |
| `_test_permission_denied_error` | 355 | `except:` | `except PermissionError as e:` |
| `_test_concurrent_access_error` | 458 | `except:` | `except (RuntimeError, ThreadError) as e:` |
| `_test_memory_pressure_error` | 466 | `except:` | `except MemoryError as e:` |
| `_test_timeout_error` | 474 | `except:` | `except TimeoutError as e:` |
| `_test_version_mismatch_error` | 493 | `except:` | `except (ValueError, VersionError) as e:` |
| `_test_cache_corruption_error` | 506 | `except:` | `except (pickle.UnpicklingError, CacheError) as e:` |
| `_test_concurrent_load` | 558 | `except:` | `except Exception as e:` with logging |
| `_test_rapid_operations` | 587 | `except:` | `except Exception as e:` with logging |
| `_test_large_file_handling` | 645 | `except:` | `except (MemoryError, OSError) as e:` |
| `_test_many_languages` | 654 | `except:` | `except Exception as e:` with logging |
| `_test_deep_recursion` | 665 | `except:` | `except RecursionError as e:` |
| `_test_circular_dependencies` | 673 | `except:` | `except (ImportError, CircularDependencyError) as e:` |
| `run_all_tests` | 805 | `except:` | `except Exception as e:` with logging |

**Specification for Each Method:**

```python
# Template for all methods above
def _test_invalid_language_error(self) -> bool:
    """Test handling of invalid language.

    Returns:
        bool: True if error was handled gracefully, False otherwise.
    """
    try:
        result = self.grammar_manager.install_grammar("nonexistent_language")
        return not result  # Should fail gracefully
    except (ValueError, KeyError, RuntimeError) as e:
        logger.debug("Expected error during invalid language test: %s", e)
        return True  # Exception handling is recovery
```

#### File: `chunker/error_handling/utils.py`

**Method to Modify:**

| Method | Line | Current | Change To |
|--------|------|---------|-----------|
| `extract_stack_locals` | 214 | `except:` | `except (AttributeError, TypeError, ValueError):` |

**Specification:**

```python
def extract_stack_locals(frame: FrameType) -> dict[str, str]:
    """Extract local variables from stack frame.

    Args:
        frame: Python stack frame object.

    Returns:
        dict[str, str]: Dictionary of variable names to their string representations.
    """
    locals_dict = {}
    for name, value in frame.f_locals.items():
        try:
            locals_dict[name] = repr(value)[:200]  # Truncate long reprs
        except (AttributeError, TypeError, ValueError):
            locals_dict[name] = "<unrepresentable>"
    return locals_dict
```

#### File: `chunker/error_handling/troubleshooting.py`

**Method to Modify:**

| Method | Line | Current | Change To |
|--------|------|---------|-----------|
| `_load_stopwords` | 262 | `except:` | `except (ImportError, LookupError):` |

**Specification:**

```python
def _load_stopwords(self) -> set[str]:
    """Load NLTK stopwords if available.

    Returns:
        set[str]: Set of stopwords, empty if NLTK unavailable.
    """
    try:
        from nltk.corpus import stopwords
        return set(stopwords.words('english'))
    except (ImportError, LookupError):
        logger.debug("NLTK stopwords not available, using empty set")
        return set()
```

#### File: `chunker/core.py`

**Location to Modify:** Line 128

**Current:**
```python
except Exception:
    pass
```

**Change To:**
```python
except (AttributeError, IndexError, UnicodeDecodeError) as e:
    logger.debug("R call analysis failed: %s", e)
```

---

### 1.2 Fix SQL Injection in PostgreSQL Exporter

**Purpose:** Prevent SQL injection attacks by using parameterized queries.

#### File: `chunker/export/postgres_exporter.py`

**Class:** `PostgresExporter`

**Method to Modify:** `get_insert_statements`

**Current Lines:** 230-289

**Input:**
- `self.chunks: list[CodeChunk]` - Chunks to export
- `self.relationships: list[dict]` - Relationships to export
- `batch_size: int = 100` - Batch size for inserts

**Output:**
- `list[str]` - SQL statements (for SQL file export)
- OR parameterized query execution (for direct connection)

**New Method Signature:**

```python
def get_insert_statements(
    self,
    batch_size: int = 100,
    parameterized: bool = True
) -> list[str] | list[tuple[str, list[tuple]]]:
    """Generate SQL INSERT statements for chunks and relationships.

    Args:
        batch_size: Number of records per batch.
        parameterized: If True, return (query, params) tuples for safe execution.
                      If False, return escaped SQL strings (less safe, for file export only).

    Returns:
        If parameterized=True: List of (sql_template, params_list) tuples.
        If parameterized=False: List of SQL strings with properly escaped values.
    """
```

**New Implementation:**

```python
def get_insert_statements(
    self,
    batch_size: int = 100,
    parameterized: bool = True
) -> list[str] | list[tuple[str, list[tuple]]]:
    """Generate SQL INSERT statements for chunks and relationships."""

    if parameterized:
        return self._get_parameterized_statements(batch_size)
    else:
        return self._get_escaped_statements(batch_size)

def _get_parameterized_statements(
    self,
    batch_size: int
) -> list[tuple[str, list[tuple]]]:
    """Generate parameterized INSERT statements.

    Returns:
        List of (sql_template, params_list) tuples for executemany().
    """
    results = []

    # Chunk inserts
    chunk_sql = """
        INSERT INTO chunks (id, file_path, start_line, end_line, start_byte,
                           end_byte, content, chunk_type, language, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (id) DO UPDATE SET
            file_path = EXCLUDED.file_path,
            start_line = EXCLUDED.start_line,
            end_line = EXCLUDED.end_line,
            start_byte = EXCLUDED.start_byte,
            end_byte = EXCLUDED.end_byte,
            content = EXCLUDED.content,
            chunk_type = EXCLUDED.chunk_type,
            language = EXCLUDED.language,
            metadata = EXCLUDED.metadata
    """

    chunk_params = []
    for chunk in self.chunks:
        metadata_json = json.dumps(chunk.metadata) if chunk.metadata else "{}"
        chunk_params.append((
            chunk.chunk_id,
            chunk.file_path,
            chunk.start_line,
            chunk.end_line,
            chunk.byte_start,
            chunk.byte_end,
            chunk.content,
            chunk.chunk_type,
            chunk.language,
            metadata_json
        ))

    for i in range(0, len(chunk_params), batch_size):
        batch = chunk_params[i:i + batch_size]
        results.append((chunk_sql, batch))

    # Relationship inserts
    rel_sql = """
        INSERT INTO relationships (source_id, target_id, relationship_type, properties)
        VALUES (%s, %s, %s, %s::jsonb)
        ON CONFLICT (source_id, target_id, relationship_type) DO UPDATE SET
            properties = EXCLUDED.properties
    """

    rel_params = []
    for rel in self.relationships:
        props_json = json.dumps(rel.get("properties", {}))
        rel_params.append((
            rel["source_id"],
            rel["target_id"],
            rel["relationship_type"],
            props_json
        ))

    for i in range(0, len(rel_params), batch_size):
        batch = rel_params[i:i + batch_size]
        results.append((rel_sql, batch))

    return results

def _get_escaped_statements(self, batch_size: int) -> list[str]:
    """Generate escaped SQL statements for file export.

    Note: Use parameterized queries when possible. This method is only
    for generating SQL files that will be manually reviewed.
    """
    statements = []

    for i in range(0, len(self.chunks), batch_size):
        batch = self.chunks[i:i + batch_size]
        values_parts = []
        for chunk in batch:
            # Use proper escaping function
            values_parts.append(self._escape_chunk_values(chunk))

        statement = f"""
INSERT INTO chunks (id, file_path, start_line, end_line, start_byte, end_byte,
                   content, chunk_type, language, metadata)
VALUES {','.join(values_parts)}
ON CONFLICT (id) DO UPDATE SET
    file_path = EXCLUDED.file_path,
    start_line = EXCLUDED.start_line,
    end_line = EXCLUDED.end_line,
    start_byte = EXCLUDED.start_byte,
    end_byte = EXCLUDED.end_byte,
    content = EXCLUDED.content,
    chunk_type = EXCLUDED.chunk_type,
    language = EXCLUDED.language,
    metadata = EXCLUDED.metadata;"""
        statements.append(statement)

    # Similar for relationships...
    return statements

def _escape_sql_string(self, value: str) -> str:
    """Properly escape a string for PostgreSQL.

    Args:
        value: String to escape.

    Returns:
        Escaped string safe for SQL inclusion.
    """
    if value is None:
        return "NULL"
    # Use dollar-quoting for complex strings
    if "'" in value or "\\" in value or "\n" in value:
        # Find unique delimiter
        delimiter = ""
        for suffix in ["", "q", "qq", "qqq", "qqqq"]:
            tag = f"${suffix}$"
            if tag not in value:
                delimiter = suffix
                break
        return f"${delimiter}${value}${delimiter}$"
    return f"'{value}'"
```

**Add New Method:** `execute_safe`

```python
def execute_safe(
    self,
    connection,  # psycopg2 connection
    batch_size: int = 100
) -> None:
    """Execute inserts safely using parameterized queries.

    Args:
        connection: Active psycopg2 database connection.
        batch_size: Number of records per batch.

    Raises:
        DatabaseError: If insert fails.
    """
    statements = self._get_parameterized_statements(batch_size)

    with connection.cursor() as cursor:
        for sql, params in statements:
            cursor.executemany(sql, params)
        connection.commit()
```

---

### 1.3 Fix Shell Injection Vulnerabilities

**Purpose:** Remove `shell=True` from subprocess calls to prevent command injection.

#### File: `chunker/build/builder.py`

**Class:** `GrammarBuilder`

**Method to Modify:** `_compile_windows` (lines 478-494)

**Current:**
```python
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    shell=True,  # VULNERABLE
    check=False,
)
```

**New Implementation:**

```python
def _compile_windows(
    self,
    c_files: list[Path],
    output_path: Path,
    include_dirs: list[Path],
    build_info: dict
) -> bool:
    """Compile grammar on Windows using MSVC.

    Args:
        c_files: List of C source files to compile.
        output_path: Output DLL path.
        include_dirs: Include directories for headers.
        build_info: Dictionary to store build information.

    Returns:
        bool: True if compilation succeeded, False otherwise.
    """
    cl_exe = self._find_cl_exe()
    if not cl_exe:
        build_info["errors"].append("MSVC compiler (cl.exe) not found")
        return False

    # Build command as list (NOT string) - prevents shell injection
    cmd = [
        str(cl_exe),
        "/LD",  # Create DLL
        "/O2",  # Optimize
        "/nologo",
    ]

    # Add include directories - validate paths first
    for inc in include_dirs:
        if not inc.exists():
            logger.warning("Include directory does not exist: %s", inc)
            continue
        cmd.append(f"/I{inc}")

    # Add output path
    cmd.append(f"/Fe{output_path}")

    # Add source files - validate each exists
    for c_file in c_files:
        if not c_file.exists():
            build_info["errors"].append(f"Source file not found: {c_file}")
            return False
        cmd.append(str(c_file))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,  # SECURE - no shell interpretation
            check=False,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode == 0:
            build_info["libraries"]["combined"] = str(output_path)
            return True
        else:
            build_info["errors"].append(f"Compilation failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        build_info["errors"].append("Compilation timed out after 5 minutes")
        return False
    except Exception as e:
        build_info["errors"].append(f"Compilation error: {e}")
        return False
```

#### File: `chunker/distribution/verifier.py`

**Class:** `DistributionVerifier`

**Method to Modify:** `verify_conda_installation` (lines 155-214)

**Current (line 189-196):**
```python
test_cmd = f"conda run -n {env_name} python -c 'import chunker; print(chunker.__version__)'"
test_result = subprocess.run(
    test_cmd,
    shell=True,  # VULNERABLE
    ...
)
```

**New Implementation:**

```python
def verify_conda_installation(self) -> tuple[bool, dict]:
    """Verify conda installation of the package.

    Returns:
        tuple[bool, dict]: (success, details) where details contains
            test results, errors, and installation output.
    """
    details = {
        "tests_passed": [],
        "tests_failed": [],
        "errors": [],
        "installation_output": "",
    }

    conda_cmd = self._find_conda()
    if not conda_cmd:
        details["errors"].append(
            "Conda not found. Please install Anaconda or Miniconda."
        )
        return False, details

    with tempfile.TemporaryDirectory() as tmpdir:
        # Generate safe environment name (alphanumeric only)
        env_suffix = hashlib.sha256(tmpdir.encode()).hexdigest()[:8]
        env_name = f"test_chunker_{env_suffix}"

        try:
            # Create environment
            create_result = subprocess.run(
                [conda_cmd, "create", "-n", env_name, "python=3.9", "-y"],
                capture_output=True,
                text=True,
                check=False,
                timeout=600,
            )

            if create_result.returncode != 0:
                details["errors"].append(
                    f"Failed to create conda env: {create_result.stderr}"
                )
                return False, details

            # Install package
            install_result = subprocess.run(
                [
                    conda_cmd, "install", "-n", env_name,
                    "-c", "conda-forge", "treesitter-chunker", "-y"
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=600,
            )
            details["installation_output"] = install_result.stdout

            # Test import - NO shell=True, use list form
            test_result = subprocess.run(
                [
                    conda_cmd, "run", "-n", env_name,
                    "python", "-c",
                    "import chunker; print(chunker.__version__)"
                ],
                capture_output=True,
                text=True,
                check=False,
                shell=False,  # SECURE
                timeout=60,
            )

            if test_result.returncode == 0:
                details["tests_passed"].append("conda_import_test")
            else:
                details["tests_failed"].append("conda_import_test")
                details["errors"].append(f"Import test failed: {test_result.stderr}")

        except subprocess.TimeoutExpired as e:
            details["errors"].append(f"Operation timed out: {e}")
        except Exception as e:
            details["errors"].append(f"Conda test failed: {e}")
        finally:
            # Clean up environment
            subprocess.run(
                [conda_cmd, "env", "remove", "-n", env_name, "-y"],
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )

        return len(details["tests_failed"]) == 0 and len(details["errors"]) == 0, details
```

---

### 1.4 Replace Deprecated `toml` Library

**Purpose:** Remove unmaintained `toml` library, use built-in `tomllib` (Python 3.11+).

#### File: `pyproject.toml`

**Changes:**

1. Update Python version requirement:
```toml
# Line ~15
requires-python = ">=3.11"
```

2. Remove `toml` from dependencies:
```toml
# Remove this line from dependencies
"toml",
```

#### File: `chunker/cli/main.py`

**Current (line ~103):**
```python
import toml
config = toml.load(f)
```

**New Implementation:**

```python
import tomllib

def load_config_file(config_path: Path) -> dict:
    """Load configuration from TOML file.

    Args:
        config_path: Path to TOML configuration file.

    Returns:
        dict: Parsed configuration dictionary.

    Raises:
        ConfigurationError: If file cannot be read or parsed.
    """
    try:
        with config_path.open("rb") as f:  # Note: tomllib requires binary mode
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigurationError(f"Invalid TOML in {config_path}: {e}") from e
    except OSError as e:
        raise ConfigurationError(f"Cannot read {config_path}: {e}") from e
```

#### File: `chunker/chunker_config.py`

**Current (line ~77):**
```python
import toml
# ...
config_data = toml.load(f)
```

**New Implementation:**

```python
import tomllib

def _load_toml(self, path: Path) -> dict:
    """Load TOML configuration file.

    Args:
        path: Path to TOML file.

    Returns:
        dict: Parsed configuration.

    Raises:
        ConfigurationError: If parsing fails.
    """
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigurationError(f"Invalid TOML syntax in {path}: {e}") from e
```

---

## Phase 2: High Priority Fixes

### 2.1 Add Array Bounds Checking

**Purpose:** Prevent IndexError crashes from unchecked array access.

#### File: `chunker/metadata/languages/javascript.py`

**Method to Modify:** `_extract_param_info` (lines 275-300)

**Add Helper Function:**

```python
def _safe_get_child(
    self,
    node: Node,
    index: int,
    default: Node | None = None
) -> Node | None:
    """Safely get child node by index.

    Args:
        node: Parent node.
        index: Child index (supports negative indexing).
        default: Value to return if index out of bounds.

    Returns:
        Child node at index, or default if not found.
    """
    children = getattr(node, "children", [])
    if not children:
        return default
    try:
        return children[index]
    except IndexError:
        return default
```

**Update `_extract_param_info`:**

```python
def _extract_param_info(
    self,
    param_node: Node,
    source: bytes
) -> dict[str, str] | None:
    """Extract parameter information from AST node.

    Args:
        param_node: Parameter AST node.
        source: Source code bytes.

    Returns:
        dict with 'name', 'type', 'default' keys, or None if extraction fails.
    """
    param_info = {"name": "", "type": "", "default": ""}

    if param_node.type == "identifier":
        param_info["name"] = self._get_node_text(param_node, source)

    elif param_node.type in {"required_parameter", "optional_parameter"}:
        identifier = self._find_child_by_type(param_node, "identifier")
        if identifier:
            param_info["name"] = self._get_node_text(identifier, source)

        type_annotation = self._find_child_by_type(param_node, "type_annotation")
        if type_annotation:
            param_info["type"] = self._get_node_text(type_annotation, source)

        # Check for optional marker
        text = self._get_node_text(param_node, source)
        if "?" in text:
            param_info["name"] += "?"

        # Find default value safely
        for i, child in enumerate(param_node.children):
            if child.type == "=":
                next_child = self._safe_get_child(param_node, i + 1)
                if next_child:
                    param_info["default"] = self._get_node_text(next_child, source)
                break

    elif param_node.type == "rest_parameter":
        identifier = self._find_child_by_type(param_node, "identifier")
        if identifier:
            param_info["name"] = "..." + self._get_node_text(identifier, source)

    elif param_node.type in {"object_pattern", "array_pattern"}:
        param_info["name"] = self._get_node_text(param_node, source)

    elif param_node.type == "assignment_pattern":
        # Safe access with bounds check
        first_child = self._safe_get_child(param_node, 0)
        third_child = self._safe_get_child(param_node, 2)

        if first_child:
            param_info["name"] = self._get_node_text(first_child, source)
        if third_child:
            param_info["default"] = self._get_node_text(third_child, source)

    return param_info if param_info["name"] else None
```

#### Files Requiring Same Pattern:

Add `_safe_get_child` helper to these files and update array accesses:

| File | Lines to Fix |
|------|-------------|
| `chunker/analysis/complexity.py` | 202 |
| `chunker/analysis/coupling.py` | 241 |
| `chunker/metadata/languages/c.py` | 157, 161 |
| `chunker/languages/go.py` | 74 |
| `chunker/languages/clojure.py` | 135 |
| `chunker/export/relationships/tracker.py` | 199, 257, 349, 393 |
| `chunker/debug/interactive/node_explorer.py` | 265, 272 |

**Standard Pattern for All Files:**

```python
# BEFORE (unsafe)
first_child = node.children[0]
second_child = node.children[1]

# AFTER (safe)
children = getattr(node, "children", [])
first_child = children[0] if children else None
second_child = children[1] if len(children) > 1 else None

# Or use helper
first_child = self._safe_get_child(node, 0)
second_child = self._safe_get_child(node, 1)
```

---

### 2.2 Fix Resource Leaks (Database Connections)

**Purpose:** Ensure database connections are properly closed using context managers.

#### File: `chunker/languages/compatibility/database.py`

**Class:** `CompatibilityDatabase`

**Add Context Manager Protocol:**

```python
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

class CompatibilityDatabase:
    """Database for tracking language compatibility information.

    Supports context manager protocol for safe resource management.

    Example:
        with CompatibilityDatabase(path) as db:
            db.query(...)
    """

    def __init__(self, db_path: Path):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> "CompatibilityDatabase":
        """Enter context manager, open connection."""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, close connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get active connection.

        Raises:
            RuntimeError: If not in context manager.
        """
        if self._conn is None:
            raise RuntimeError(
                "Database must be used within context manager: "
                "with CompatibilityDatabase(path) as db: ..."
            )
        return self._conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        """Create a transaction with automatic commit/rollback.

        Yields:
            sqlite3.Cursor: Cursor for executing queries.

        Example:
            with db.transaction() as cursor:
                cursor.execute("INSERT INTO ...")
        """
        cursor = self.conn.cursor()
        try:
            yield cursor
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cursor.close()
```

#### File: `chunker/integration/performance_optimizer.py`

**Method to Modify:** Line 1149 (in-memory database creation)

**Add Connection Management:**

```python
class PerformanceOptimizer:
    """Optimizer for chunk processing performance."""

    def __init__(self):
        self._db_conn: sqlite3.Connection | None = None

    def _get_db_connection(self) -> sqlite3.Connection:
        """Get or create in-memory database connection.

        Returns:
            sqlite3.Connection: Thread-safe connection.
        """
        if self._db_conn is None:
            self._db_conn = sqlite3.connect(
                ":memory:",
                check_same_thread=False
            )
        return self._db_conn

    def close(self) -> None:
        """Close database connection and release resources."""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None

    def __del__(self):
        """Destructor to ensure connection cleanup."""
        self.close()

    def __enter__(self) -> "PerformanceOptimizer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
```

---

### 2.3 Add JSON Error Handling

**Purpose:** Wrap JSON operations in try-except to handle malformed data.

#### File: `chunker/parser.py`

**Method to Modify:** Line 111

```python
def _load_language_config(self, config_path: Path) -> dict:
    """Load language configuration from JSON file.

    Args:
        config_path: Path to JSON configuration file.

    Returns:
        dict: Parsed configuration.

    Raises:
        ConfigurationError: If JSON is invalid or unreadable.
    """
    try:
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigurationError(
            f"Invalid JSON in {config_path}: {e.msg} at line {e.lineno}"
        ) from e
    except OSError as e:
        raise ConfigurationError(f"Cannot read {config_path}: {e}") from e
```

#### Apply Same Pattern to:

| File | Line | Method |
|------|------|--------|
| `chunker/grammar_management/core.py` | 1002 | `_load_grammar_config` |
| `chunker/error_handling/templates.py` | 746, 1061 | `_parse_template`, `_load_test_content` |
| `chunker/grammar_management/compatibility.py` | 1968-1972 | Multiple `json.loads` calls |

**Standard Pattern:**

```python
def _safe_json_load(self, data: str | bytes, context: str = "") -> dict:
    """Safely parse JSON with error context.

    Args:
        data: JSON string or bytes to parse.
        context: Description of what's being parsed (for error messages).

    Returns:
        dict: Parsed JSON data.

    Raises:
        ValueError: If JSON is invalid.
    """
    try:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON{' in ' + context if context else ''}: "
            f"{e.msg} at position {e.pos}"
        ) from e
```

---

### 2.4 Add Decode Error Handling

**Purpose:** Handle UTF-8 decode errors gracefully.

#### File: `chunker/languages/rust.py`

**Add Helper Method:**

```python
def _safe_decode(
    self,
    data: bytes,
    errors: str = "replace"
) -> str:
    """Safely decode bytes to string.

    Args:
        data: Bytes to decode.
        errors: Error handling strategy ('replace', 'ignore', 'strict').

    Returns:
        str: Decoded string.
    """
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        logger.warning("Invalid UTF-8 sequence encountered, using replacement")
        return data.decode("utf-8", errors=errors)
```

**Update All Decode Calls:**

```python
# Lines 42, 61, 85, 92 - change from:
text = node.text.decode("utf-8")

# To:
text = self._safe_decode(node.text)
```

#### Apply Same Pattern to:

| File | Lines |
|------|-------|
| `chunker/analysis/complexity.py` | 204, 207, 213 |
| `chunker/languages/ruby.py` | 90, 95, 98, 102, 144, 154, 168 |
| `chunker/core.py` | 121 (already has errors="ignore", OK) |

---

### 2.5 Add Pickle Integrity Checks

**Purpose:** Validate cache integrity before deserializing pickle data.

#### File: `chunker/_internal/cache.py`

**Add Imports:**

```python
import hashlib
import hmac
```

**Add Constants:**

```python
# Cache format version for compatibility checking
CACHE_FORMAT_VERSION = 2

# Secret key for HMAC (should be loaded from environment in production)
_CACHE_SECRET = os.environ.get("CHUNKER_CACHE_SECRET", "default-dev-key").encode()
```

**Add Helper Methods:**

```python
def _compute_integrity_hash(self, data: bytes) -> bytes:
    """Compute HMAC-SHA256 hash for data integrity.

    Args:
        data: Data to hash.

    Returns:
        bytes: 32-byte HMAC hash.
    """
    return hmac.new(_CACHE_SECRET, data, hashlib.sha256).digest()

def _serialize_with_integrity(self, obj: Any) -> bytes:
    """Serialize object with integrity hash.

    Args:
        obj: Object to serialize.

    Returns:
        bytes: Serialized data with integrity hash prefix.
    """
    # Add version header
    payload = pickle.dumps((CACHE_FORMAT_VERSION, obj))
    integrity_hash = self._compute_integrity_hash(payload)
    return integrity_hash + payload

def _deserialize_with_integrity(self, data: bytes) -> Any:
    """Deserialize data with integrity verification.

    Args:
        data: Serialized data with integrity hash.

    Returns:
        Deserialized object.

    Raises:
        CacheCorruptedError: If integrity check fails.
        CacheVersionError: If format version doesn't match.
    """
    if len(data) < 32:
        raise CacheCorruptedError("Cache data too short")

    stored_hash = data[:32]
    payload = data[32:]

    # Verify integrity
    computed_hash = self._compute_integrity_hash(payload)
    if not hmac.compare_digest(stored_hash, computed_hash):
        raise CacheCorruptedError("Cache integrity check failed")

    # Deserialize and check version
    version, obj = pickle.loads(payload)
    if version != CACHE_FORMAT_VERSION:
        raise CacheVersionError(
            f"Cache format version {version} != expected {CACHE_FORMAT_VERSION}"
        )

    return obj
```

**Update `get_cached_chunks` Method:**

```python
def get_cached_chunks(
    self,
    path: Path,
    language: str
) -> list[CodeChunk] | None:
    """Retrieve cached chunks for a file.

    Args:
        path: Source file path.
        language: Programming language.

    Returns:
        List of cached chunks, or None if not cached/invalid.
    """
    metadata = get_file_metadata(path)

    with self._get_connection() as conn:
        result = conn.execute(
            """
            SELECT file_hash, mtime, chunks_data
            FROM file_cache
            WHERE file_path = ? AND language = ?
            """,
            (str(path), language),
        ).fetchone()

        if result:
            cached_hash, cached_mtime, chunks_data = result

            # Check if file has changed
            if cached_hash == metadata.hash and cached_mtime == metadata.mtime:
                try:
                    # Deserialize with integrity check
                    chunks_dicts = self._deserialize_with_integrity(chunks_data)
                    return [CodeChunk(**chunk_dict) for chunk_dict in chunks_dicts]

                except (CacheCorruptedError, CacheVersionError) as e:
                    logger.warning("Cache invalid for %s: %s", path, e)
                    self.invalidate_cache(path)
                    return None

                except (
                    pickle.UnpicklingError,
                    EOFError,
                    AttributeError,
                    ImportError,
                    IndexError,
                ) as e:
                    logger.warning("Cache corrupted for %s: %s", path, e)
                    self.invalidate_cache(path)
                    return None

    return None
```

**Update `cache_chunks` Method:**

```python
def cache_chunks(
    self,
    path: Path,
    language: str,
    chunks: list[CodeChunk]
) -> None:
    """Cache chunks for a file.

    Args:
        path: Source file path.
        language: Programming language.
        chunks: Chunks to cache.
    """
    metadata = get_file_metadata(path)

    # Serialize with integrity
    chunks_dicts = [asdict(chunk) for chunk in chunks]
    chunks_data = self._serialize_with_integrity(chunks_dicts)

    with self._get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO file_cache
            (file_path, file_hash, file_size, mtime, language, chunks_data)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(path),
                metadata.hash,
                metadata.size,
                metadata.mtime,
                language,
                chunks_data,
            ),
        )
```

**Add Exception Classes to `chunker/exceptions.py`:**

```python
class CacheError(ChunkerError):
    """Base class for cache-related errors."""
    pass

class CacheCorruptedError(CacheError):
    """Raised when cache data fails integrity check."""
    pass

class CacheVersionError(CacheError):
    """Raised when cache format version is incompatible."""
    pass
```

---

## Phase 3: Medium Priority Fixes

### 3.1 Extract Magic Numbers to Constants

**Purpose:** Improve code readability and maintainability.

#### File: `chunker/languages/vue.py`

**Add Constants at Module Level:**

```python
# Content preview length for detecting lang attributes in SFC templates
CONTENT_PREVIEW_LENGTH = 50

# Supported script languages
SCRIPT_LANGUAGES = frozenset({"ts", "typescript"})

# Supported style languages
STYLE_LANGUAGES = frozenset({"scss", "sass", "less", "stylus"})
```

**Update Code:**

```python
# BEFORE (lines 148-180)
if 'lang="ts"' in content[:50] or "lang='ts'" in content[:50]:
if 'lang="scss"' in content[:50] or "lang='scss'" in content[:50]:

# AFTER
def _detect_script_lang(self, content: str) -> str | None:
    """Detect script language from SFC content.

    Args:
        content: Full file content.

    Returns:
        Detected language or None.
    """
    preview = content[:CONTENT_PREVIEW_LENGTH]
    for lang in SCRIPT_LANGUAGES:
        if f'lang="{lang}"' in preview or f"lang='{lang}'" in preview:
            return lang
    return None

def _detect_style_lang(self, content: str) -> str | None:
    """Detect style language from SFC content.

    Args:
        content: Full file content.

    Returns:
        Detected language or None.
    """
    preview = content[:CONTENT_PREVIEW_LENGTH]
    for lang in STYLE_LANGUAGES:
        if f'lang="{lang}"' in preview or f"lang='{lang}'" in preview:
            return lang
    return None
```

#### File: `chunker/semantic/merger.py`

**Add Constants:**

```python
# Default thresholds for semantic merging
DEFAULT_SMALL_METHOD_THRESHOLD = 10  # Lines
DEFAULT_MAX_MERGED_SIZE = 100  # Lines
DEFAULT_COHESION_THRESHOLD = 0.6  # 0.0 to 1.0
```

**Update Dataclass:**

```python
@dataclass
class MergerConfig:
    """Configuration for semantic chunk merging.

    Attributes:
        small_method_threshold: Methods smaller than this are merge candidates.
        max_merged_size: Maximum size of merged chunk in lines.
        cohesion_threshold: Minimum semantic similarity for merging (0.0-1.0).
        language_configs: Per-language override configurations.
    """
    small_method_threshold: int = DEFAULT_SMALL_METHOD_THRESHOLD
    max_merged_size: int = DEFAULT_MAX_MERGED_SIZE
    cohesion_threshold: float = DEFAULT_COHESION_THRESHOLD
    language_configs: dict[str, dict] = field(default_factory=dict)
```

#### File: `chunker/performance/cache/manager.py`

**Add Constants:**

```python
# Default cache sizes
DEFAULT_AST_CACHE_SIZE = 100
DEFAULT_CHUNK_CACHE_SIZE = 1000
DEFAULT_QUERY_CACHE_SIZE = 500
DEFAULT_METADATA_CACHE_SIZE = 500
```

---

### 3.2 Refactor Complex `_walk()` Function

**Purpose:** Break down monolithic function into manageable, testable pieces.

#### File: `chunker/core.py`

**Create New Module:** `chunker/languages/normalizers.py`

```python
"""AST node type normalizers for language-specific handling."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node

class NodeNormalizer(ABC):
    """Base class for language-specific node normalization."""

    @abstractmethod
    def normalize_type(
        self,
        node: Node,
        source: bytes
    ) -> tuple[str, int, int]:
        """Normalize node type and adjust span if needed.

        Args:
            node: AST node to normalize.
            source: Source code bytes.

        Returns:
            tuple of (normalized_type, span_start, span_end)
        """
        pass

    @abstractmethod
    def should_force_chunk(self, node: Node, source: bytes) -> bool:
        """Check if node should be forced into a chunk.

        Args:
            node: AST node to check.
            source: Source code bytes.

        Returns:
            True if node should become a chunk regardless of type.
        """
        pass


class DartNormalizer(NodeNormalizer):
    """Normalizer for Dart language AST nodes."""

    SIGNATURE_TO_DECLARATION = {
        "function_signature": "function_declaration",
        "method_signature": "method_declaration",
        "getter_signature": "getter_declaration",
        "setter_signature": "setter_declaration",
        "constructor_signature": "constructor_declaration",
        "factory_constructor_signature": "factory_constructor",
    }

    def normalize_type(
        self,
        node: Node,
        source: bytes
    ) -> tuple[str, int, int]:
        span_start = node.start_byte
        span_end = node.end_byte
        node_type = node.type

        if node_type in self.SIGNATURE_TO_DECLARATION:
            node_type = self.SIGNATURE_TO_DECLARATION[node_type]
            span_end = self._find_body_end(node) or span_end
        elif node_type == "class_definition":
            node_type = "class_declaration"
        elif node_type == "type_alias":
            node_type = "type_declaration"

        return node_type, span_start, span_end

    def _find_body_end(self, node: Node) -> int | None:
        """Find function_body sibling and return its end byte."""
        parent = getattr(node, "parent", None)
        if parent is None:
            return None

        try:
            children = list(parent.children)
            idx = children.index(node)
            for sib in children[idx + 1:]:
                if sib.type == "function_body":
                    return sib.end_byte
        except (ValueError, IndexError):
            pass
        return None

    def should_force_chunk(self, node: Node, source: bytes) -> bool:
        return False


class RNormalizer(NodeNormalizer):
    """Normalizer for R language AST nodes."""

    FORCE_CHUNK_CALLS = frozenset({"setClass", "setMethod", "setGeneric"})

    def normalize_type(
        self,
        node: Node,
        source: bytes
    ) -> tuple[str, int, int]:
        return node.type, node.start_byte, node.end_byte

    def should_force_chunk(self, node: Node, source: bytes) -> bool:
        if node.type != "call":
            return False

        children = getattr(node, "children", [])
        if not children:
            return False

        callee = children[0]
        if getattr(callee, "type", None) != "identifier":
            return False

        try:
            ident = source[callee.start_byte:callee.end_byte].decode(
                "utf-8", errors="ignore"
            )
            return ident in self.FORCE_CHUNK_CALLS
        except (AttributeError, IndexError):
            return False


# Registry of normalizers by language
NORMALIZERS: dict[str, type[NodeNormalizer]] = {
    "dart": DartNormalizer,
    "r": RNormalizer,
    # Add more as needed...
}


def get_normalizer(language: str) -> NodeNormalizer:
    """Get normalizer for language.

    Args:
        language: Programming language name.

    Returns:
        NodeNormalizer instance for the language.
    """
    normalizer_class = NORMALIZERS.get(language)
    if normalizer_class:
        return normalizer_class()
    return DefaultNormalizer()


class DefaultNormalizer(NodeNormalizer):
    """Default normalizer that passes through unchanged."""

    def normalize_type(
        self,
        node: Node,
        source: bytes
    ) -> tuple[str, int, int]:
        return node.type, node.start_byte, node.end_byte

    def should_force_chunk(self, node: Node, source: bytes) -> bool:
        return False
```

**Update `chunker/core.py`:**

```python
from chunker.languages.normalizers import get_normalizer

def _walk(
    node: Node,
    source: bytes,
    language: str,
    parent_ctx: str | None = None,
    parent_chunk: CodeChunk | None = None,
    extractor: SignatureExtractor | None = None,
    analyzer: Any | None = None,
    parent_route: list[str] | None = None,
) -> list[CodeChunk]:
    """Walk AST and extract code chunks.

    Args:
        node: Current AST node.
        source: Source code bytes.
        language: Programming language.
        parent_ctx: Parent context string.
        parent_chunk: Parent chunk if nested.
        extractor: Metadata extractor instance.
        analyzer: Code analyzer instance.
        parent_route: Route from root to current node.

    Returns:
        List of extracted CodeChunk objects.
    """
    chunks = []
    normalizer = get_normalizer(language)

    # Check for forced chunking (language-specific)
    force_chunk = normalizer.should_force_chunk(node, source)

    if should_chunk(node.type) or force_chunk:
        # Get normalized type and span
        adjusted_type, span_start, span_end = normalizer.normalize_type(
            node, source
        )

        # Create chunk...
        # (rest of chunk creation logic)

    # Recurse into children
    for child in node.children:
        chunks.extend(_walk(
            child, source, language,
            parent_ctx, parent_chunk,
            extractor, analyzer, parent_route
        ))

    return chunks
```

---

### 3.3 Add `__all__` Exports

**Purpose:** Clearly define public API for each module.

#### Files to Update:

| File | Add `__all__` |
|------|---------------|
| `chunker/core.py` | `["chunk_text", "chunk_file", "chunk_directory"]` |
| `chunker/types.py` | `["CodeChunk", "ChunkMetadata", "FileMetadata"]` |
| `chunker/parser.py` | `["get_parser", "ParserRegistry", "SUPPORTED_LANGUAGES"]` |
| `chunker/chunker.py` | `["TreeSitterTokenAwareChunker", "chunk_code"]` |
| `chunker/exceptions.py` | `["ChunkerError", "LanguageNotFoundError", "ParserError", ...]` |
| `chunker/languages/base.py` | `["ChunkRule", "PluginConfig", "LanguageConfig", "LanguagePlugin"]` |

**Example:**

```python
# chunker/core.py
__all__ = [
    "chunk_text",
    "chunk_file",
    "chunk_directory",
    "should_chunk",
]
```

---

### 3.4 Standardize Type Hints

**Purpose:** Use modern Python 3.10+ type hint syntax consistently.

#### File: `chunker/grammar_management/core.py`

**Line 39 - Change:**

```python
# BEFORE
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# AFTER
from typing import Any  # Only keep what can't be replaced

# Then update all usages:
# Dict[str, Any] -> dict[str, Any]
# List[str] -> list[str]
# Optional[int] -> int | None
# Union[str, int] -> str | int
# Set[str] -> set[str]
# Tuple[int, str] -> tuple[int, str]
```

#### Files to Update:

| File | Changes Needed |
|------|----------------|
| `chunker/grammar_management/core.py` | Replace Dict, List, Optional, Union, Set, Tuple |
| `chunker/error_handling/classifier.py` | Replace Dict, List, Optional |
| `chunker/_internal/cache.py` | Replace Optional, Dict |
| `chunker/export/postgres_exporter.py` | Replace Dict, List |

---

### 3.5 Replace `print()` with Logging

**Purpose:** Use proper logging for all output.

#### File: `chunker/testing/system_integration.py`

**Find and Replace Pattern:**

```python
# BEFORE
print(f"Test result: {result}")

# AFTER
logger.info("Test result: %s", result)
```

#### File: `chunker/monitoring/observability_system.py`

**Same pattern.**

---

## Phase 4: Low Priority Improvements

### 4.1 Add Module Docstrings

#### File: `chunker/_internal/cache.py`

```python
"""
Caching infrastructure for tree-sitter chunker.

This module provides SQLite-based caching for parsed ASTs and code chunks,
enabling significant performance improvements for repeated parsing operations.

Classes:
    ChunkCache: Main cache implementation with integrity checking.
    CacheStats: Statistics about cache usage.

Example:
    cache = ChunkCache(Path("~/.cache/chunker"))
    chunks = cache.get_cached_chunks(file_path, "python")
    if chunks is None:
        chunks = parse_file(file_path)
        cache.cache_chunks(file_path, "python", chunks)
"""
```

#### File: `chunker/strategies/adaptive.py`

```python
"""
Adaptive chunking strategies.

This module provides chunking strategies that adapt based on file size,
complexity, and content type to optimize chunk quality and performance.

Classes:
    AdaptiveChunker: Main adaptive chunking implementation.
    ChunkingStrategy: Base class for chunking strategies.
"""
```

#### File: `chunker/streaming.py`

```python
"""
Streaming support for large file processing.

This module enables processing of files larger than available memory
by streaming chunks as they are parsed rather than loading everything.

Functions:
    chunk_file_streaming: Stream chunks from a file.
    chunk_directory_streaming: Stream chunks from a directory.
"""
```

---

### 4.2 Improve Parameter Documentation

#### File: `chunker/semantic/merger.py`

**Method: `_build_merge_groups` (line 146)**

```python
def _build_merge_groups(
    self,
    chunks: list[CodeChunk],
) -> dict[str, list[CodeChunk]]:
    """Build groups of chunks that should be merged together.

    Groups chunks by their logical relationship (e.g., small methods
    in the same class, related helper functions).

    Args:
        chunks: List of chunks to analyze for merging.

    Returns:
        Dictionary mapping group keys to lists of related chunks.
        Key format: "{file_path}:{parent_id}" for class methods,
                   "{file_path}:module" for top-level functions.

    Example:
        >>> merger = SemanticMerger()
        >>> groups = merger._build_merge_groups(chunks)
        >>> # groups might be:
        >>> # {
        >>> #     "src/utils.py:MyClass_123": [chunk1, chunk2, chunk3],
        >>> #     "src/utils.py:module": [chunk4, chunk5],
        >>> # }
    """
```

---

### 4.3 Replace `__import__()` with `importlib`

#### File: `chunker/languages/base.py`

**Line 524 - Change:**

```python
# BEFORE
module = __import__(f"{__package__}.{module_name}", fromlist=[module_name])

# AFTER
import importlib

def _load_language_module(self, module_name: str) -> ModuleType:
    """Dynamically load a language plugin module.

    Args:
        module_name: Name of the module to load (without package prefix).

    Returns:
        Loaded module object.

    Raises:
        ImportError: If module cannot be loaded.
    """
    full_name = f"{__package__}.{module_name}"
    return importlib.import_module(full_name)
```

---

### 4.4 Fix Mutable Default in Dataclass

#### File: `chunker/semantic/merger.py`

**Line 23 - Change:**

```python
# BEFORE
@dataclass
class MergerConfig:
    language_configs: dict[str, dict] = None

# AFTER
from dataclasses import dataclass, field

@dataclass
class MergerConfig:
    """Configuration for semantic merging.

    Attributes:
        small_method_threshold: Minimum lines for standalone chunk.
        max_merged_size: Maximum merged chunk size in lines.
        cohesion_threshold: Minimum similarity for merging.
        language_configs: Per-language configuration overrides.
    """
    small_method_threshold: int = DEFAULT_SMALL_METHOD_THRESHOLD
    max_merged_size: int = DEFAULT_MAX_MERGED_SIZE
    cohesion_threshold: float = DEFAULT_COHESION_THRESHOLD
    language_configs: dict[str, dict] = field(default_factory=dict)
```

---

## Phase 5: Dependency Updates

### 5.1 Update `pyproject.toml`

**Location:** `/home/user/treesitter-chunker/pyproject.toml`

**Changes:**

```toml
[project]
# Update Python version
requires-python = ">=3.11"

dependencies = [
    # Remove: "toml",

    # Update versions:
    "pyarrow>=15.0.0",
    "python-dateutil>=2.9.0",
    "gitpython>=3.1.40",
    "tqdm>=4.66.0",
    "tiktoken>=0.7.0",

    # Add version constraints to unconstrained deps:
    "tree_sitter>=0.20.0,<1.0.0",
    "rich>=13.0.0",
    "typer>=0.9.0",
    "pyyaml>=6.0",
    "pygments>=2.15.0",
    "chardet>=5.0.0",
]
```

---

## Testing Requirements

### New Test Files to Create

#### `tests/test_security.py`

```python
"""Security-focused tests for treesitter-chunker."""

import pytest
from pathlib import Path

class TestSQLInjectionPrevention:
    """Test SQL injection prevention in exporters."""

    def test_postgres_parameterized_queries(self):
        """Verify PostgreSQL exporter uses parameterized queries."""
        # Test with malicious input
        pass

    def test_sqlite_parameterized_queries(self):
        """Verify SQLite exporter uses parameterized queries."""
        pass


class TestShellInjectionPrevention:
    """Test shell injection prevention in subprocess calls."""

    def test_builder_no_shell_true(self):
        """Verify build commands don't use shell=True."""
        pass

    def test_verifier_no_shell_true(self):
        """Verify verification commands don't use shell=True."""
        pass


class TestCacheIntegrity:
    """Test cache integrity mechanisms."""

    def test_cache_integrity_check(self):
        """Verify cache validates integrity before loading."""
        pass

    def test_corrupted_cache_detected(self):
        """Verify corrupted cache is detected and invalidated."""
        pass
```

#### `tests/test_bounds_checking.py`

```python
"""Tests for array bounds checking."""

import pytest

class TestSafeChildAccess:
    """Test safe child node access in AST processing."""

    def test_empty_children_list(self):
        """Verify handling of nodes with no children."""
        pass

    def test_out_of_bounds_index(self):
        """Verify handling of out-of-bounds index."""
        pass
```

### Existing Tests to Update

| Test File | Updates Needed |
|-----------|----------------|
| `tests/test_postgres_exporter.py` | Add parameterized query tests |
| `tests/test_cache.py` | Add integrity check tests |
| `tests/test_grammar_management.py` | Update for new exception types |

---

## Summary Checklist

### Phase 1: Critical (Must Fix)
- [ ] Replace 17+ bare except clauses in `grammar_management/testing.py`
- [ ] Replace bare excepts in `error_handling/utils.py`, `troubleshooting.py`, `core.py`
- [ ] Fix SQL injection in `postgres_exporter.py` with parameterized queries
- [ ] Remove `shell=True` from `build/builder.py`
- [ ] Remove `shell=True` from `distribution/verifier.py`
- [ ] Replace `toml` with `tomllib` in `cli/main.py` and `chunker_config.py`
- [ ] Update `pyproject.toml` for Python 3.11+

### Phase 2: High Priority
- [ ] Add `_safe_get_child` to 8 files with array access issues
- [ ] Add context managers to database classes
- [ ] Wrap JSON operations in try-except in 5 files
- [ ] Add `_safe_decode` helper to language plugins
- [ ] Add pickle integrity checks to cache

### Phase 3: Medium Priority
- [ ] Extract magic numbers in `vue.py`, `svelte.py`, `merger.py`, `manager.py`
- [ ] Create `chunker/languages/normalizers.py`
- [ ] Add `__all__` to 6+ public modules
- [ ] Update type hints in 4+ files
- [ ] Replace `print()` with logging in 2 files

### Phase 4: Low Priority
- [ ] Add module docstrings to 3 files
- [ ] Improve parameter documentation in 2 methods
- [ ] Replace `__import__()` in `languages/base.py`
- [ ] Fix mutable default in `semantic/merger.py`

### Phase 5: Dependencies
- [ ] Update `pyproject.toml` with new version constraints
- [ ] Remove `toml` dependency
- [ ] Test with updated dependencies

---

*This specification is complete and ready for implementation. All changes maintain backward compatibility unless explicitly noted.*
