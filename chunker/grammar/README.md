# Universal Language Registry

The Universal Language Registry extends the base `LanguageRegistry` with automatic grammar download capabilities. It integrates with the Grammar Discovery and Download services to provide seamless language support.

## Features

- **Auto-download**: Automatically downloads and compiles grammars when requested
- **Version management**: Tracks installed grammar versions and supports updates
- **Metadata persistence**: Stores installation information in `~/.cache/treesitter-chunker/registry_metadata.json`
- **Backward compatibility**: Works with existing parser API seamlessly

## Usage

```python
from chunker.grammar.registry import UniversalLanguageRegistry
from chunker.contracts.discovery_stub import GrammarDiscoveryStub
from chunker.contracts.download_stub import GrammarDownloadStub

# Initialize with services
discovery = GrammarDiscoveryStub()
downloader = GrammarDownloadStub()
registry = UniversalLanguageRegistry(
    library_path=Path("build/my-languages.so"),
    discovery_service=discovery,
    download_service=downloader
)

# Get parser with auto-download
parser = registry.get_parser("go")  # Downloads if not available

# List languages
installed = registry.list_installed_languages()
available = registry.list_available_languages()

# Install/update/uninstall
registry.install_language("java", "0.20.0")
registry.update_language("python")
registry.uninstall_language("ruby")

# Get metadata
metadata = registry.get_language_metadata("python")
# Returns: {
#     "version": "0.20.0",
#     "abi_version": "14",
#     "file_extensions": [".py", ".pyw"],
#     "auto_downloaded": False,
#     "installed_path": "/path/to/python.so"
# }
```

## Architecture

The `UniversalLanguageRegistry` wraps the existing `LanguageRegistry` and adds:

1. **Auto-download logic**: When a language isn't found, it queries the discovery service and downloads via the download service
2. **Metadata tracking**: Maintains a JSON file tracking installed languages, versions, and whether they were auto-downloaded
3. **Version management**: Supports checking for updates and upgrading grammars

## Metadata Format

The registry stores metadata in `~/.cache/treesitter-chunker/registry_metadata.json`:

```json
{
  "installed": {
    "python": {
      "version": "0.20.0",
      "path": "/path/to/python.so",
      "auto_downloaded": false
    },
    "go": {
      "version": "0.20.0", 
      "path": "/path/to/go.so",
      "auto_downloaded": true
    }
  },
  "auto_downloaded": ["go"]
}
```

## Integration Points

- **Discovery Service**: Used to find available grammars and check compatibility
- **Download Service**: Used to download and compile grammars
- **Base Registry**: Delegates language loading to the existing `LanguageRegistry`

## Error Handling

- Returns `LanguageNotFoundError` when a language isn't available and auto-download is disabled
- Logs warnings/errors for download failures
- Preserves old versions if updates fail