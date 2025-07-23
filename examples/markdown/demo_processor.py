#!/usr/bin/env python3
"""Demo script for the Markdown processor.

This script demonstrates how to use the MarkdownProcessor to chunk
Markdown files intelligently while preserving structure.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from chunker.processors.markdown import MarkdownProcessor
from chunker.processors import ProcessorConfig


def print_chunk_info(chunk, index):
    """Print information about a chunk."""
    print(f"\n{'='*60}")
    print(f"Chunk {index + 1}:")
    print(f"  Type: {chunk.node_type}")
    print(f"  Lines: {chunk.start_line}-{chunk.end_line}")
    print(f"  Tokens: {chunk.metadata.get('tokens', 'N/A')}")
    
    if chunk.metadata:
        print(f"  Metadata:")
        for key, value in chunk.metadata.items():
            if key != 'segment_types':  # Skip verbose fields
                print(f"    {key}: {value}")
                
    print(f"\nContent preview (first 200 chars):")
    print("-" * 40)
    print(chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content)
    

def process_file(file_path, config=None):
    """Process a Markdown file and display results."""
    print(f"Processing: {file_path}")
    
    # Create processor
    processor = MarkdownProcessor(config)
    
    # Read file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Check if processor can handle file
    if not processor.can_process(file_path, content):
        print(f"Error: {file_path} is not a valid Markdown file")
        return
        
    # Extract structure
    print("\nExtracting structure...")
    structure = processor.extract_structure(content)
    
    print(f"\nStructure summary:")
    print(f"  Headers: {len(structure['headers'])}")
    print(f"  Code blocks: {len(structure['code_blocks'])}")
    print(f"  Tables: {len(structure['tables'])}")
    print(f"  Lists: {len(structure['lists'])}")
    if structure['front_matter']:
        print(f"  Front matter: Present")
        
    # Process into chunks
    print("\nCreating chunks...")
    chunks = processor.process(content, file_path)
    
    print(f"\nCreated {len(chunks)} chunks")
    
    # Display chunk information
    for i, chunk in enumerate(chunks):
        print_chunk_info(chunk, i)
        
    # Summary statistics
    print(f"\n{'='*60}")
    print("Summary Statistics:")
    print(f"  Total chunks: {len(chunks)}")
    print(f"  Average chunk size: {sum(c.metadata.get('tokens', 0) for c in chunks) / len(chunks):.1f} tokens")
    print(f"  Chunk types: {set(c.node_type for c in chunks)}")
    
    # Check for overlap
    overlap_chunks = [c for c in chunks if c.metadata.get('has_overlap')]
    if overlap_chunks:
        print(f"  Chunks with overlap: {len(overlap_chunks)}")
        

def main():
    """Main demo function."""
    # Example configurations
    configs = {
        "default": None,
        "small_chunks": ProcessorConfig(
            max_chunk_size=300,
            min_chunk_size=50,
            overlap_size=50
        ),
        "large_chunks": ProcessorConfig(
            max_chunk_size=2000,
            min_chunk_size=200,
            overlap_size=200
        ),
        "no_overlap": ProcessorConfig(
            max_chunk_size=1000,
            overlap_size=0
        )
    }
    
    # Process example files
    example_files = [
        "technical_documentation.md",
        "mixed_content.md"
    ]
    
    for file_name in example_files:
        file_path = Path(__file__).parent / file_name
        if file_path.exists():
            print(f"\n{'#'*80}")
            print(f"# Processing {file_name} with different configurations")
            print(f"{'#'*80}")
            
            for config_name, config in configs.items():
                print(f"\n\nConfiguration: {config_name}")
                print("-" * 40)
                process_file(file_path, config)
                
                # Only show first config for brevity in demo
                if config_name == "default":
                    break
        else:
            print(f"Warning: {file_path} not found")
            
    print("\n\nDemo complete!")
    

if __name__ == "__main__":
    main()