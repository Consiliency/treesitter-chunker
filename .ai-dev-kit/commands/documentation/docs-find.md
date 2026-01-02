---
name: docs-find
argument-hint: "[search query]"
description: "Search documentation indexes for relevant pages. Returns ranked results with paths for loading."
allowed-tools: Read, Glob
---

# Find Documentation

Search across all documentation indexes to find relevant pages.

## Usage

```
/ai-dev-kit:docs-find retry policy
/ai-dev-kit:docs-find streaming responses baml
/ai-dev-kit:docs-find "error handling" mcp
/ai-dev-kit:docs-find configure provider anthropic
```

## Process

### 1. Parse Query

Extract from the query:
- **Keywords**: Significant terms to match
- **Library filter**: If a known library name is included
- **Quoted phrases**: Exact matches

Example: `/ai-dev-kit:docs-find "retry policy" baml timeout`
```
Keywords: retry, policy, timeout
Library filter: baml
Phrases: "retry policy"
```

### 2. Load Indexes

If library filter specified:
```
@ai-docs/libraries/{library}/_index.toon
@ai-docs/libraries/{library}/*/_index.toon (section indexes)
```

If no filter:
```
@ai-docs/libraries/_index.toon
Then drill into matching libraries
```

### 3. Match Against Index Content

For each index, score matches against:
- `keywords` fields
- `title` fields
- `purpose` / `description` fields
- `common_tasks` entries

Scoring:
- Exact keyword match: 10 points
- Partial keyword match: 5 points
- Phrase match: 15 points
- Title match: 12 points
- Library name match: 8 points

### 4. Rank Results

Sort by:
1. Total relevance score
2. Priority (core > important > supplementary)
3. Library priority (high > medium > low)

### 5. Return Results

```markdown
## Documentation Search Results

**Query**: {original query}
**Matches**: {count}

| Rank | Score | Library | Page | Path |
|------|-------|---------|------|------|
| 1 | 95 | baml | Error Handling | `ai-docs/libraries/baml/guide/pages/error-handling.toon` |
| 2 | 87 | baml | Retry Policy | `ai-docs/libraries/baml/reference/pages/retry-policy.toon` |
| 3 | 45 | mcp | Transport Errors | `ai-docs/libraries/mcp/reference/pages/transports.toon` |

### Top Result Preview

**BAML: Error Handling** (Score: 95)
- Section: guide
- Priority: important
- Keywords: retry, error, fallback, timeout
- Purpose: Configure retry policies and fallback strategies for resilient LLM calls.

### To Load

```
@ai-docs/libraries/baml/guide/pages/error-handling.toon
```

### Related Searches

- "baml fallback client" - for provider chaining
- "baml timeout configuration" - for timeout settings
```

## Examples

### Example 1: Specific library search

```
/ai-dev-kit:docs-find baml streaming
```

Output:
```markdown
## Documentation Search Results

**Query**: baml streaming
**Matches**: 2

| Rank | Score | Library | Page | Path |
|------|-------|---------|------|------|
| 1 | 92 | baml | Streaming | `ai-docs/libraries/baml/guide/pages/streaming.toon` |
| 2 | 34 | baml | Function | `ai-docs/libraries/baml/reference/pages/function.toon` |

To load top result:
@ai-docs/libraries/baml/guide/pages/streaming.toon
```

### Example 2: Cross-library search

```
/ai-dev-kit:docs-find api client configuration
```

Output:
```markdown
## Documentation Search Results

**Query**: api client configuration
**Matches**: 4

| Rank | Score | Library | Page | Path |
|------|-------|---------|------|------|
| 1 | 88 | baml | Client | `ai-docs/libraries/baml/reference/pages/client.toon` |
| 2 | 85 | anthropic-sdk | Client Setup | `ai-docs/libraries/anthropic-sdk/guide/pages/setup.toon` |
| 3 | 72 | mcp | Server Config | `ai-docs/libraries/mcp/reference/pages/server.toon` |
| 4 | 45 | baml | Introduction | `ai-docs/libraries/baml/guide/pages/introduction.toon` |
```

### Example 3: No results

```
/ai-dev-kit:docs-find graphql schema
```

Output:
```markdown
## Documentation Search Results

**Query**: graphql schema
**Matches**: 0

No documentation found matching "graphql schema".

### Suggestions

1. **Check if library is tracked**:
   @ai-docs/libraries/_index.toon

2. **Add documentation source**:
   /ai-dev-kit:docs-add [graphql-library-url] graphql

3. **Try broader search**:
   /ai-dev-kit:docs-find schema
   /ai-dev-kit:docs-find api types
```

## Notes

- This command searches indexes only, doesn't load full page content
- Use results to decide what to `@` load
- For complex multi-library context, use `docs-context-gatherer` agent instead
- Results are ranked by relevance, not alphabetically
