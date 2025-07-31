# Cross-Language Usage Guide

Tree-sitter Chunker can be used from any programming language through multiple integration methods.

## Integration Methods

### 1. Python Package (Native)

For Python projects, use the package directly:

```python
pip install treesitter-chunker

from chunker import chunk_file, chunk_text, chunk_directory

# Chunk a file
chunks = chunk_file("example.py", language="python")

# Chunk text directly
chunks = chunk_text(code_string, language="javascript")

# Chunk entire directory
results = chunk_directory("src/", language="python")
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
- `csv` - CSV with headers
- `table` - Rich table (default, human-readable)

**Example from Node.js:**
```javascript
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

async function chunkFile(filePath, language) {
    const { stdout } = await execPromise(
        `treesitter-chunker chunk "${filePath}" --lang ${language} --json`
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

Run the API server:
```bash
# Install with API dependencies
pip install "treesitter-chunker[api]"

# Start the server
python -m api.server
# Or: uvicorn api.server:app --reload
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

# Chunk file
curl -X POST http://localhost:8000/chunk/file \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/file.js",
    "language": "javascript"
  }'
```

See `/api/examples/` for client examples in Python, JavaScript, and Go.

### 4. Docker Container

Use the Docker image for isolated execution:

```bash
# Pull the image
docker pull ghcr.io/consiliency/treesitter-chunker:latest

# Run as CLI
docker run --rm -v $(pwd):/workspace \
  treesitter-chunker chunk /workspace/file.py -l python --json

# Run as API server
docker run -p 8000:8000 \
  treesitter-chunker python -m api.server
```

### 5. Language-Specific Bindings (Future)

Planned native bindings:
- **JavaScript/TypeScript**: npm package using N-API
- **Go**: Module using CGO or exec wrapper
- **Rust**: Crate using PyO3 or native tree-sitter
- **Java**: JAR using JNI or ProcessBuilder

## API Response Format

All methods return chunks with this structure:

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

All methods support these filters:
- `min_chunk_size` - Minimum lines per chunk
- `max_chunk_size` - Maximum lines per chunk
- `chunk_types` - List of node types to include

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

Run `treesitter-chunker list-languages` or `GET /languages` to see all supported languages.

Common languages include:
- Python, JavaScript, TypeScript, Go, Rust
- Java, C, C++, C#, Ruby, PHP
- Swift, Kotlin, Scala, Haskell
- And 30+ more...

## Configuration

All methods respect `.chunkerrc` configuration files in TOML/YAML/JSON format:

```toml
# .chunkerrc
min_chunk_size = 5
max_chunk_size = 100

[languages.python]
chunk_types = ["function_definition", "class_definition"]
```