# Code Sandbox MCP Server

A simple MCP server that executes code with timeout and output limits.

> **Note**: This provides **minimal sandboxing** (timeout + output limits only). Code runs directly on your machine with your user permissions. See [Security](#security-warning) below.

## What This Provides

| Feature | Provided? | Details |
|---------|-----------|---------|
| Timeout limits | Yes | Configurable (default 10s) |
| Output truncation | Yes | Prevents token bloat |
| Temp directory execution | Yes | Basic cleanup |
| Filesystem isolation | **No** | Full access to your files |
| Network isolation | **No** | Can make network requests |
| Resource limits (CPU/RAM) | **No** | No limits enforced |
| Process isolation | **No** | Runs as your user |

## Features

- **run_code**: Execute code in Python, JavaScript, or Bash
- Configurable timeout (default: 10 seconds)
- Output truncation to prevent token bloat
- Basic process isolation via temp directory

## Security Warning

This is a **basic example** suitable for development and trusted environments.

**Code runs directly on your machine** - not in a container or VM. For production use with untrusted code, you should add:

- Docker/container isolation
- Resource limits (CPU, memory, disk)
- Network isolation
- Filesystem sandboxing
- User namespace isolation

See [Security Best Practices](https://github.com/modelcontextprotocol/servers#security) for guidance.

## Configuration

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "code-sandbox": {
      "command": "python3",
      "args": ["dev-tools/mcp/examples/code-sandbox/server.py"],
      "env": {
        "TIMEOUT_SECONDS": "10",
        "MAX_OUTPUT_BYTES": "10000"
      }
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TIMEOUT_SECONDS` | Max execution time per request | `10` |
| `MAX_OUTPUT_BYTES` | Max output size before truncation | `10000` |

## Supported Languages

| Language | Runtime Required |
|----------|-----------------|
| `python` | Python 3 (uses current interpreter) |
| `javascript` | Node.js (`node` command) |
| `bash` | Bash shell |

## Usage Examples

Once configured, Claude Code can use this tool:

```
"Run this Python code: print(sum(range(100)))"
"Execute: console.log(Array.from({length: 10}, (_, i) => i * i))"
"Run bash: ls -la && echo 'Hello World'"
```

## Dependencies

```bash
uv pip install mcp
```

## Extending

To add more languages, modify the `runners` dict in `call_tool()`:

```python
def run_ruby(code: str, timeout: int) -> tuple[str, str, int]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".rb", delete=False) as f:
        f.write(code)
        f.flush()
        try:
            result = subprocess.run(
                ["ruby", f.name],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.stdout, result.stderr, result.returncode
        finally:
            Path(f.name).unlink(missing_ok=True)

# Add to ALLOWED_LANGUAGES and runners dict
```

## Docker Isolation (Recommended)

For better isolation, wrap execution in Docker:

```python
def run_python_docker(code: str, timeout: int) -> tuple[str, str, int]:
    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--network=none",
            "--memory=100m",
            "--cpus=0.5",
            "-i", "python:3.11-slim",
            "python", "-c", code
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout, result.stderr, result.returncode
```
