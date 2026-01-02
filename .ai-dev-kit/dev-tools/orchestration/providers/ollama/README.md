# Ollama Provider

Execute tasks using locally running Ollama models for offline or privacy-sensitive work.

## Prerequisites

```bash
ollama serve
ollama list
```

## Usage

```bash
./query.sh "your task" [model]
```

## Defaults

- Default model: `llama3.2`
- Override with `OLLAMA_MODEL` or the second argument

## Output Format

```json
{
  "success": true,
  "output": "Ollama response",
  "agent": "ollama",
  "model": "llama3.2",
  "timestamp": "2025-12-10T00:00:00Z"
}
```

## Example

```bash
./query.sh "summarize this repo" "qwen2.5-coder"
```
