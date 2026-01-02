# Gemini Provider

Execute tasks using Gemini CLI with Google AI Ultra subscription.

## Authentication

Uses Google account OAuth by default:

```bash
gemini  # Select "Login with Google" → use AI Ultra account
gemini auth status  # Verify
```

For headless/CI: `export GEMINI_API_KEY="..."`

## Available Models (December 2025)

| Model | Use Case | Model ID |
|-------|----------|----------|
| Gemini 3 Pro | Flagship, complex tasks | `gemini-3-pro` |
| Gemini 3 Deep Think | Extended reasoning | `gemini-3-deep-think` |
| Gemini 3 Flash-Lite | Fast, cost-efficient | `gemini-3-flash-lite` |

## Unique Capabilities

- **2M token context**: Can load entire codebases
- **Multimodal native**: Images, video, audio
- **Web search**: Grounded in current information
- **Highest rate limits**: AI Ultra provides priority access

## Usage

### Standard Query

```bash
./query.sh "your question"
```

### With Files (multimodal)

```bash
./multimodal.py "analyze this image" image.png
```

### Web Search with Grounding

```bash
./search.sh "latest developments in X"
```

## Output Format

JSON object:

```json
{
  "success": true,
  "output": "Gemini response",
  "agent": "gemini",
  "timestamp": "2025-12-10T00:00:00Z"
}
```

## Rate Limits

- AI Ultra: Highest limits, 5-hour refresh cycle
- Priority access over free tier users

## Example

```bash
# Simple query
./query.sh "explain this architecture diagram"

# With image
./multimodal.py "what does this screenshot show?" screenshot.png

# Web search
./search.sh "latest React 19 features"
```
