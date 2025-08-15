# Grammar Discovery Service

The Grammar Discovery Service is a core component that provides automatic discovery of tree-sitter grammars from GitHub and manages metadata about available grammars.

## Overview

The service implements the `GrammarDiscoveryContract` and provides:

- **GitHub API Integration**: Automatically discovers grammars from the tree-sitter organization
- **Caching**: Results are cached locally to avoid rate limiting and improve performance
- **Search**: Find grammars by name or description
- **Version Tracking**: Check for updates to installed grammars
- **Compatibility Info**: Get compatibility requirements for specific grammar versions

## Architecture

```
GrammarDiscoveryService
├── GitHub API Client (requests)
├── Cache Manager (JSON file-based)
├── Version Comparator
└── Metadata Extractor
```

## Usage

```python
from chunker.grammar.discovery import GrammarDiscoveryService

# Create service instance
discovery = GrammarDiscoveryService()

# List all official grammars
grammars = discovery.list_available_grammars()

# Include community grammars
all_grammars = discovery.list_available_grammars(include_community=True)

# Get info for a specific language
python_info = discovery.get_grammar_info("python")
if python_info:
    print(f"Python grammar: {python_info.url}")
    print(f"Version: {python_info.version}")
    print(f"Stars: {python_info.stars}")

# Search for grammars
rust_grammars = discovery.search_grammars("rust")

# Check for updates
installed = {"python": "0.19.0", "rust": "0.20.0"}
updates = discovery.check_grammar_updates(installed)
for lang, (current, latest) in updates.items():
    print(f"{lang}: {current} -> {latest}")

# Get compatibility info
compat = discovery.get_grammar_compatibility("python", "0.20.0")
print(f"ABI Version: {compat.abi_version}")
print(f"Tested Python versions: {compat.tested_python_versions}")

# Refresh cache manually
success = discovery.refresh_cache()
```

## Caching

The service implements intelligent caching to minimize API calls:

- **Location**: `~/.cache/treesitter-chunker/discovery_cache.json`
- **Duration**: 24 hours by default
- **Format**: JSON with timestamp and grammar metadata
- **Automatic refresh**: When cache expires or on manual refresh

## Rate Limiting

The service respects GitHub API rate limits:

- **Unauthenticated**: 60 requests/hour
- **Graceful handling**: Stops fetching when limit reached
- **Cache fallback**: Uses cached data when API unavailable

## Grammar Metadata

Each grammar includes:

- **name**: Language identifier (e.g., "python", "rust")
- **url**: GitHub repository URL
- **version**: Current version (semantic versioning)
- **last_updated**: Last modification timestamp
- **stars**: GitHub star count
- **description**: Grammar description
- **supported_extensions**: File extensions (e.g., [".py", ".pyw"])
- **official**: Whether from tree-sitter organization

## Implementation Details

### Language Name Resolution

The service handles multiple naming conventions:
- Exact match: `get_grammar_info("python")`
- With prefix: `get_grammar_info("rust")` finds "tree-sitter-rust"

### Version Comparison

Simple semantic versioning comparison:
- Major.Minor.Patch format
- Handles missing patch versions
- Falls back safely on parse errors

### File Extension Mapping

Common languages have predefined extension mappings:
- Python: [".py", ".pyw"]
- JavaScript: [".js", ".mjs", ".cjs"]
- TypeScript: [".ts", ".tsx"]
- And many more...

## Error Handling

The service handles errors gracefully:

- **Network errors**: Falls back to cache
- **Rate limiting**: Stops fetching, returns partial results
- **Invalid responses**: Logs errors, continues with valid data
- **Cache corruption**: Recreates cache on next successful fetch

## Future Enhancements

Planned improvements:

1. **Authentication**: Support GitHub tokens for higher rate limits
2. **Community grammars**: Discover grammars outside tree-sitter org
3. **Release tracking**: Fetch actual release versions instead of defaults
4. **Parallel fetching**: Speed up discovery with concurrent requests
5. **Grammar quality metrics**: Include test coverage, commit activity

## Testing

The service includes comprehensive tests:

- **Unit tests**: Mock GitHub API responses
- **Integration tests**: Work with other Phase 14 components
- **Cache tests**: Verify caching behavior
- **Error tests**: Ensure graceful failure handling

Run tests:
```bash
python -m pytest tests/test_grammar_discovery.py -xvs
```