# Universal Language Registry

The Universal Language Registry wraps the base `LanguageRegistry` with explicit install, update and metadata operations. It uses the Grammar Discovery and Download services only when you call those operations.

Nothing is downloaded or built on demand. This automatic download-and-build was retired by a maintainer decision of 2026-11-01, extending M2 of treesitter-chunker#362. `get_parser()` returns parsers only for installed, admitted sources (package-supplied grammars, or local grammars under their own pins, passed as `trusted_artifacts`). For any other language it raises `LanguageNotFoundError` with the cause and guidance. The `auto_download` argument is still accepted but has no effect, and passing it emits a `DeprecationWarning`.

## Features

- **Explicit installs**: `install_language()` downloads and compiles on request; a local result is used only under its pin
- **Version management**: Tracks installed grammar versions and supports updates
- **Metadata persistence**: Stores installation information in `~/.cache/treesitter-chunker/registry_metadata.json`
- **Backward compatibility**: Works with existing parser API seamlessly

## Usage

```python
from chunker.grammar.registry import UniversalLanguageRegistry
from chunker.contracts.discovery_stub import GrammarDiscoveryStub
from chunker.contracts.download_stub import GrammarDownloadStub

# Initialize with services and the approved pins for local grammars
discovery = GrammarDiscoveryStub()
downloader = GrammarDownloadStub()
registry = UniversalLanguageRegistry(
    library_path=Path("build/my-languages.so"),
    discovery_service=discovery,
    download_service=downloader,
    trusted_artifacts={"go": {"sha256": "<reviewed sha256 of the go grammar>"}},
)

# Get a parser from an installed, admitted source (never downloads)
parser = registry.get_parser("go")  # LanguageNotFoundError if unavailable

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

1. **Explicit install/update**: `install_language()` and `update_language()` use the discovery and download services when called; `get_parser()` never does
2. **Metadata tracking**: Maintains a JSON file tracking installed languages and versions (the `auto_downloaded` fields are kept for older files)
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

- Raises `LanguageNotFoundError` when no installed, admitted source provides a language, with the cause and the build-and-pin guidance
- Logs warnings/errors for download failures
- Preserves old versions if updates fail