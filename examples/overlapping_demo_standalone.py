#!/usr/bin/env python3
"""
Demonstration of overlapping chunks for non-Tree-sitter files - standalone version.

This example shows how to use the OverlappingFallbackChunker for files
that don't have Tree-sitter support, such as text files, markdown, logs, etc.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to sys.path for direct imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Direct imports to avoid the full chunker module initialization
from chunker.fallback.overlapping import OverlappingFallbackChunker, OverlapStrategy, OverlapConfig


def print_chunk_info(chunks, title):
    """Print information about chunks."""
    print(f"\n{title}")
    print("=" * len(title))
    print(f"Total chunks: {len(chunks)}")
    
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i + 1}:")
        print(f"  Lines: {chunk.start_line}-{chunk.end_line}")
        print(f"  Bytes: {chunk.byte_start}-{chunk.byte_end}")
        print(f"  Size: {len(chunk.content)} characters")
        print(f"  Preview: {chunk.content[:50]}..." if len(chunk.content) > 50 else f"  Content: {chunk.content}")


def demo_fixed_overlap():
    """Demonstrate fixed overlap strategy."""
    print("\n" + "="*60)
    print("FIXED OVERLAP STRATEGY DEMO")
    print("="*60)
    
    # Create sample text content
    content = """# Project Documentation

## Introduction

This is a comprehensive guide to our project. The documentation covers all aspects
of the system architecture, implementation details, and usage instructions.

## System Architecture

The system is built using a microservices architecture with the following components:
- API Gateway: Handles all incoming requests and routes them to appropriate services
- Authentication Service: Manages user authentication and authorization
- Data Processing Service: Handles all data transformation and analysis
- Storage Service: Manages data persistence and retrieval

## Implementation Details

### API Gateway

The API Gateway is implemented using Node.js and Express. It provides:
1. Request routing based on URL patterns
2. Load balancing across service instances
3. Request/response transformation
4. Rate limiting and throttling

### Authentication Service

Built with Python and FastAPI, this service handles:
- User registration and login
- JWT token generation and validation
- Role-based access control
- Password reset functionality

## Usage Instructions

To get started with the system:
1. Install all dependencies using the provided scripts
2. Configure environment variables as described in .env.example
3. Run the initialization script to set up the database
4. Start all services using docker-compose

## Troubleshooting

Common issues and their solutions:
- Connection refused: Check if all services are running
- Authentication failed: Verify JWT token is valid
- Data not persisting: Check database connection settings
"""
    
    chunker = OverlappingFallbackChunker()
    
    # Chunk by lines with fixed overlap
    chunks_lines = chunker.chunk_with_overlap(
        content=content,
        file_path="docs/README.md",
        chunk_size=10,  # 10 lines per chunk
        overlap_size=3,  # 3 lines overlap
        strategy=OverlapStrategy.FIXED,
        unit="lines"
    )
    
    print_chunk_info(chunks_lines, "Line-based chunking with 3-line overlap")
    
    # Show overlap between first two chunks
    if len(chunks_lines) >= 2:
        print("\n### Overlap Demonstration ###")
        chunk1_lines = chunks_lines[0].content.splitlines()
        chunk2_lines = chunks_lines[1].content.splitlines()
        
        print(f"\nEnd of Chunk 1 (last 3 lines):")
        for line in chunk1_lines[-3:]:
            print(f"  {line}")
        
        print(f"\nStart of Chunk 2 (first 3 lines):")
        for line in chunk2_lines[:3]:
            print(f"  {line}")
    
    # Chunk by characters with fixed overlap
    chunks_chars = chunker.chunk_with_overlap(
        content=content,
        file_path="docs/README.md",
        chunk_size=300,  # 300 characters per chunk
        overlap_size=50,  # 50 characters overlap
        strategy=OverlapStrategy.FIXED,
        unit="characters"
    )
    
    print_chunk_info(chunks_chars, "\nCharacter-based chunking with 50-char overlap")


def demo_asymmetric_overlap():
    """Demonstrate asymmetric overlap for log files."""
    print("\n" + "="*60)
    print("ASYMMETRIC OVERLAP STRATEGY DEMO")
    print("="*60)
    
    # Create sample log content
    log_content = """2024-01-20 10:15:23 INFO Starting application server
2024-01-20 10:15:24 INFO Loading configuration from config.yaml
2024-01-20 10:15:25 INFO Database connection established
2024-01-20 10:15:26 INFO Starting HTTP server on port 8080
2024-01-20 10:15:27 INFO Server ready to accept connections
2024-01-20 10:16:45 INFO Received GET request for /api/users
2024-01-20 10:16:45 INFO Authenticating user token
2024-01-20 10:16:46 INFO Token validated successfully
2024-01-20 10:16:46 INFO Fetching user data from database
2024-01-20 10:16:47 INFO Returning 25 user records
2024-01-20 10:18:12 WARNING High memory usage detected: 85%
2024-01-20 10:18:13 INFO Running garbage collection
2024-01-20 10:18:15 INFO Memory usage reduced to 62%
2024-01-20 10:20:34 ERROR Failed to connect to external API
2024-01-20 10:20:34 ERROR Timeout after 30 seconds
2024-01-20 10:20:35 INFO Retrying connection attempt 1 of 3
2024-01-20 10:20:45 ERROR Connection failed again
2024-01-20 10:20:46 INFO Retrying connection attempt 2 of 3
2024-01-20 10:20:56 INFO Connection successful
2024-01-20 10:20:57 INFO Resuming normal operation"""
    
    chunker = OverlappingFallbackChunker()
    
    # For logs, we want more forward context than backward
    chunks = chunker.chunk_with_asymmetric_overlap(
        content=log_content,
        file_path="logs/app.log",
        chunk_size=5,  # 5 lines per chunk base
        overlap_before=1,  # Only 1 line before
        overlap_after=3,   # 3 lines after for context
        unit="lines"
    )
    
    print_chunk_info(chunks, "Log file with asymmetric overlap (1 before, 3 after)")
    
    # Show how errors get more context
    for i, chunk in enumerate(chunks):
        if "ERROR" in chunk.content:
            print(f"\n### Error Context in Chunk {i + 1} ###")
            print("This chunk contains an error with forward context:")
            print(chunk.content)


def demo_dynamic_overlap():
    """Demonstrate dynamic overlap based on content structure."""
    print("\n" + "="*60)
    print("DYNAMIC OVERLAP STRATEGY DEMO")
    print("="*60)
    
    # Create structured content with varying density
    structured_content = """# Configuration Guide

## Overview

This document describes the configuration options available in our system.

## Basic Settings

### Server Configuration

```yaml
server:
  host: localhost
  port: 8080
  workers: 4
```

### Database Configuration

```yaml
database:
  host: db.example.com
  port: 5432
  name: myapp
  user: appuser
```

## Advanced Settings

For production deployments, consider these additional settings:

### Performance Tuning

Connection pooling can significantly improve performance:

```yaml
pool:
  min_connections: 10
  max_connections: 100
  idle_timeout: 300
```

### Security Settings

Always enable these in production:

```yaml
security:
  ssl_enabled: true
  cert_path: /etc/ssl/certs/app.crt
  key_path: /etc/ssl/private/app.key
```

## Environment Variables

The following environment variables override config file settings:

- APP_HOST: Override server.host
- APP_PORT: Override server.port
- DB_HOST: Override database.host
- DB_PASSWORD: Database password (never store in config file)

## Troubleshooting

If settings don't take effect:

1. Check environment variables first
2. Verify config file syntax
3. Look for typos in setting names
4. Restart the application

Remember that changes require a full restart.
"""
    
    chunker = OverlappingFallbackChunker()
    
    # Dynamic overlap adjusts based on content structure
    chunks = chunker.chunk_with_dynamic_overlap(
        content=structured_content,
        file_path="docs/config.md",
        chunk_size=400,  # 400 characters per chunk
        min_overlap=30,   # Minimum 30 chars
        max_overlap=100,  # Maximum 100 chars
        unit="characters"
    )
    
    print_chunk_info(chunks, "Dynamic overlap based on content structure")
    
    # Analyze overlap variation
    print("\n### Overlap Analysis ###")
    for i in range(len(chunks) - 1):
        chunk1 = chunks[i].content
        chunk2 = chunks[i + 1].content
        
        # Find actual overlap
        overlap_size = 0
        for size in range(min(len(chunk1), len(chunk2)), 0, -1):
            if chunk1[-size:] == chunk2[:size]:
                overlap_size = size
                break
        
        if overlap_size > 0:
            print(f"\nOverlap between chunks {i + 1} and {i + 2}: {overlap_size} chars")
            overlap_text = chunk1[-overlap_size:]
            # Show what was included in overlap
            if '\n\n' in overlap_text:
                print("  -> Includes paragraph break")
            elif '\n' in overlap_text:
                print("  -> Includes line break")
            elif '```' in overlap_text:
                print("  -> Includes code block boundary")


def demo_natural_boundaries():
    """Demonstrate natural boundary detection."""
    print("\n" + "="*60)
    print("NATURAL BOUNDARY DETECTION DEMO")
    print("="*60)
    
    content = """This is the first sentence. This is the second sentence.

This is a new paragraph with its own content. It continues here.

## New Section

This section has different content altogether."""
    
    chunker = OverlappingFallbackChunker()
    
    # Test boundary detection at different positions
    test_positions = [28, 57, 85, 120]
    
    print("Testing natural boundary detection:")
    for pos in test_positions:
        if pos < len(content):
            boundary = chunker.find_natural_overlap_boundary(content, pos, 20)
            print(f"\nDesired position: {pos}")
            print(f"Natural boundary: {boundary}")
            print(f"Character at boundary: {repr(content[boundary-1:boundary+1])}")


def main():
    """Run all demonstrations."""
    print("Overlapping Fallback Chunker Demonstration")
    print("This demo shows overlapping chunks for non-Tree-sitter files")
    
    # Run demonstrations
    demo_fixed_overlap()
    demo_asymmetric_overlap()
    demo_dynamic_overlap()
    demo_natural_boundaries()
    
    print("\n" + "="*60)
    print("Demo complete!")
    print("\nKey takeaways:")
    print("- Fixed overlap maintains consistent context between chunks")
    print("- Asymmetric overlap is useful for logs and streaming data")
    print("- Dynamic overlap adapts to content structure")
    print("- Natural boundaries improve readability and context preservation")
    print("- This is ONLY for files without Tree-sitter support")


if __name__ == "__main__":
    main()