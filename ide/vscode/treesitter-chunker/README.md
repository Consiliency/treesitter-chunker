# TreeSitter Chunker for VS Code

Semantic code chunking extension for Visual Studio Code using Tree-sitter for intelligent code analysis.

## Features

- **Chunk Current File**: Analyze the current file and extract semantic code chunks
- **Chunk Workspace**: Process all supported files in your workspace
- **Visual Chunk Boundaries**: See chunk boundaries highlighted in your editor
- **Export Chunks**: Export chunks to JSON, JSONL, or Parquet formats
- **Context Menu Integration**: Right-click files to chunk them

## Supported Languages

- Python (.py)
- JavaScript (.js)
- TypeScript (.ts)  
- Rust (.rs)
- C (.c)
- C++ (.cpp, .cc, .cxx)

## Requirements

- Python 3.10 or higher
- treesitter-chunker package installed: `pip install treesitter-chunker`

## Extension Settings

This extension contributes the following settings:

* `treesitter-chunker.pythonPath`: Path to Python executable (default: "python")
* `treesitter-chunker.exportFormat`: Default export format (json/jsonl/parquet)
* `treesitter-chunker.showChunkBoundaries`: Show visual chunk boundaries in editor
* `treesitter-chunker.chunkTypes`: Configure chunk types to extract per language

## Usage

1. **Chunk a Single File**:
   - Open a supported file
   - Use Command Palette: `TreeSitter Chunker: Chunk Current File`
   - Or right-click the file and select "Chunk File"

2. **Chunk Entire Workspace**:
   - Use Command Palette: `TreeSitter Chunker: Chunk Workspace`
   - Progress will be shown in notifications

3. **View Chunks**:
   - After chunking, use: `TreeSitter Chunker: Show Chunks`
   - Opens a webview with all chunks displayed

4. **Export Chunks**:
   - After chunking, use: `TreeSitter Chunker: Export Chunks`
   - Choose output location and format

## Configuration Example

```json
{
  "treesitter-chunker.pythonPath": "/usr/bin/python3",
  "treesitter-chunker.exportFormat": "jsonl",
  "treesitter-chunker.showChunkBoundaries": true,
  "treesitter-chunker.chunkTypes": {
    "python": ["function_definition", "class_definition", "method_definition"],
    "javascript": ["function_declaration", "arrow_function", "class_declaration"]
  }
}
```

## Development

To build the extension:

```bash
npm install
npm run compile
```

To package:

```bash
vsce package
```

## License

MIT