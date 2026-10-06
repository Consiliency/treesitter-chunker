# Cross-Language Usage Guide

Tree-sitter Chunker can be used from any programming language through multiple integration methods.

## Integration Methods

### 1. Python Package (Native)

For Python projects, use the package directly:

```bash
python -m pip install treesitter-chunker
```

```python
from chunker import chunk_file, chunk_text, chunk_directory

# Chunk a file
chunks = chunk_file("example.py", language="python")

# Chunk text directly
chunks = chunk_text("function hello() { return 1; }", language="javascript")

# Chunk entire directory
if __name__ == "__main__":
    results = chunk_directory("src/", language="python", num_workers=2)
```

### 2. Command-Line Interface (Any Language)

The CLI can be called from any language via subprocess/exec:

```bash
# Output as JSON for easy parsing
treesitter-chunker chunk file.py --lang python --output-format json

# Read from stdin
echo "def hello(): pass" | treesitter-chunker chunk --stdin --lang python --json

# Batch process with quiet mode
treesitter-chunker batch src/ --pattern "*.js" --output-format jsonl --quiet

# Minimal output format for easy parsing
treesitter-chunker chunk file.py --output-format minimal
# Output: file.py:1-3:function_definition
```

**CLI Output Formats:**
- `json` - Pretty-printed JSON
- `jsonl` - JSON Lines (one object per line)
- `minimal` - Simple format: `file:start-end:type`
- `csv` - CSV with headers (`batch` only)
- `table` - Rich table (`chunk` default); `batch` defaults to `summary`

**Example from Node.js:**
```javascript
const { execFile } = require('child_process');
const util = require('util');
const execPromise = util.promisify(execFile);

async function chunkFile(filePath, language) {
    const { stdout } = await execPromise(
        'treesitter-chunker', ['chunk', filePath, '--lang', language, '--quiet', '--json']
    );
    return JSON.parse(stdout);
}
```

**Example from Go:**
```go
import (
    "os/exec"
    "encoding/json"
)

func chunkFile(filePath, language string) ([]Chunk, error) {
    cmd := exec.Command("treesitter-chunker", "chunk", filePath, 
                       "--lang", language, "--json")
    output, err := cmd.Output()
    if err != nil {
        return nil, err
    }
    
    var chunks []Chunk
    err = json.Unmarshal(output, &chunks)
    return chunks, err
}
```

### 3. REST API (HTTP)

The REST server lives in the source checkout; the main PyPI wheel includes
`chunker` and `cli`, but not the `api` package. The `api` extra supplies server
dependencies. Run from a checkout:
```bash
git clone https://github.com/Consiliency/treesitter-chunker.git
cd treesitter-chunker
uv sync --locked --all-extras

# Set a secret token before using filesystem-backed endpoints
# Supply TREE_SITTER_CHUNKER_API_TOKEN through your secret mechanism
export TREE_SITTER_CHUNKER_API_ROOT="$(pwd)"
uv run --locked uvicorn api.server:app --host 127.0.0.1 --port 8000
```

The API provides these endpoints:
- `GET /health` - Health check
- `GET /languages` - List supported languages
- `POST /chunk/text` - Chunk source code text
- `POST /chunk/file` - Chunk a file

**Example requests:**

```bash
# Chunk text
curl -X POST http://localhost:8000/chunk/text \
  -H "Content-Type: application/json" \
  -d '{
    "content": "def hello():\n    print(\"Hello!\")",
    "language": "python"
  }'

# Chunk a file relative to TREE_SITTER_CHUNKER_API_ROOT; token required
curl -X POST http://localhost:8000/chunk/file \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TREE_SITTER_CHUNKER_API_TOKEN" \
  -d '{
    "file_path": "example.js",
    "language": "javascript"
  }'
```

See `/api/examples/` for client examples in Python, JavaScript, and Go.

### 4. Docker Container

Build a CLI image for your deployment using the recipe in the
[deployment guide](development/DEPLOYMENT.md#containers). There is no current
container publication workflow, and the main wheel does not include the REST
server. Do not assume a GHCR `latest` tag provides either.

### 5. Language-Specific Bindings (Future)

Planned native bindings:
- **JavaScript/TypeScript**: npm package using N-API
- **Go**: Module using CGO or exec wrapper
- **Rust**: Crate using PyO3 or native tree-sitter
- **Java**: JAR using JNI or ProcessBuilder

## API Response Format

The REST server returns this wrapper. CLI `chunk --json` returns an array of
chunk objects; Python functions return `CodeChunk` objects (directory helpers
return a mapping). Do not assume these interfaces share a response shape:

```json
{
  "chunks": [
    {
      "node_type": "function_definition",
      "start_line": 1,
      "end_line": 5,
      "content": "def hello(name):\n    ...",
      "parent_context": "ClassName",
      "size": 5
    }
  ],
  "total_chunks": 1,
  "language": "python"
}
```

## Filtering Options

The REST endpoints accept these fields:
- `min_chunk_size` - Minimum lines per chunk
- `max_chunk_size` - Maximum lines per chunk
- `chunk_types` - List of node types to include

CLI equivalents are `--min-size`, `--max-size` and `--types`. Core Python
functions do not accept those filter keywords; filter returned chunks yourself.

## Performance Considerations

1. **CLI**: Has startup overhead, best for batch operations
2. **API**: Keep server running for multiple requests
3. **Docker**: Additional container overhead, but good isolation
4. **Native bindings**: Best performance (when available)

## Error Handling

All methods return appropriate error codes:
- CLI: Non-zero exit code on error
- API: HTTP status codes (400 for bad request, 404 for not found)
- Subprocess: Check return code and stderr

## Examples Repository

See `/api/examples/` for complete working examples:
- `client.py` - Python API client
- `client.js` - Node.js API client
- `client.go` - Go API client
- `curl_examples.sh` - Shell/curl examples

## Supported Languages

Run `treesitter-chunker languages` or `GET /languages` to see all supported languages.

Common languages include:
- Python, JavaScript, TypeScript, Go, Rust
- Java, C, C++, C#, Ruby, PHP
- Swift, Kotlin, Scala, Haskell
- And 30+ more...

## Configuration

`chunk` and `batch` read TOML `.chunkerrc` files. Python plugin configuration
uses `ChunkerConfig`; REST filters come from the request. See
[Configuration](configuration.md) for the separate consumers.

```toml
# .chunkerrc: consumed by CLI chunk/batch
min_chunk_size = 1
max_chunk_size = 100
chunk_types = ["function_definition", "class_definition"]
```
