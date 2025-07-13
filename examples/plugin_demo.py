#!/usr/bin/env python3
"""
Demonstration of the plugin architecture for treesitter-chunker.
"""
from pathlib import Path
from chunker import get_plugin_manager, ChunkerConfig, PluginConfig

def main():
    # Initialize plugin manager
    plugin_manager = get_plugin_manager()
    
    # List available languages
    print("Available languages:")
    for lang in plugin_manager.registry.list_languages():
        print(f"  - {lang}")
    
    # List supported file extensions
    print("\nSupported file extensions:")
    extensions = plugin_manager.registry.list_extensions()
    for ext, lang in sorted(extensions.items()):
        print(f"  {ext} -> {lang}")
    
    # Example: Create a configuration
    config = ChunkerConfig()
    config.enabled_languages = {"python", "rust", "javascript"}
    config.default_plugin_config = PluginConfig(
        min_chunk_size=3,
        max_chunk_size=100
    )
    
    # Language-specific configuration
    config.set_plugin_config("python", PluginConfig(
        enabled=True,
        chunk_types={"function_definition", "class_definition"},
        custom_options={"include_docstrings": True}
    ))
    
    # Save example configuration
    example_config_path = Path("generated_config.yaml")
    config.save(example_config_path)
    print(f"\nExample configuration saved to: {example_config_path}")
    
    # Example: Chunk a Python file
    python_file = Path("example.py")
    if python_file.exists():
        print(f"\nChunking {python_file}...")
        chunks = plugin_manager.chunk_file(python_file)
        for chunk in chunks:
            print(f"  - {chunk.node_type} at lines {chunk.start_line}-{chunk.end_line}")
            if chunk.parent_context:
                print(f"    Context: {chunk.parent_context}")
    
    # Example: Load plugins from a custom directory
    custom_plugin_dir = Path("custom_plugins")
    if custom_plugin_dir.exists():
        loaded = plugin_manager.load_plugins_from_directory(custom_plugin_dir)
        print(f"\nLoaded {loaded} plugins from {custom_plugin_dir}")

if __name__ == "__main__":
    main()