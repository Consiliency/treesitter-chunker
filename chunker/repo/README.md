# Repository-Level Processing

This module provides scalable, Git-aware processing capabilities for analyzing entire code repositories efficiently.

## Key Features

### 1. **Scalable Processing**
- Parallel processing with configurable worker pools
- Memory-aware processing with limits and monitoring
- Iterator-based processing for massive repositories
- Batch processing for optimal performance

### 2. **Git Integration**
- Incremental processing (only changed files)
- Respects `.gitignore` patterns at all levels
- Tracks file history and changes
- Persistent state for resumable processing

### 3. **Smart File Detection**
- Automatic language detection from extensions
- Configurable file patterns (glob support)
- Exclude patterns for fine-grained control
- Virtual file system support

## Quick Start

```python
from chunker.repo import RepoProcessorImpl

# Basic usage
processor = RepoProcessorImpl()
result = processor.process_repository("/path/to/repo")

print(f"Processed {result.total_files} files")
print(f"Extracted {result.total_chunks} chunks")
```

## Advanced Usage

### Incremental Processing

Process only files that changed since last run:

```python
processor = RepoProcessorImpl()
result = processor.process_repository(
    repo_path,
    incremental=True  # Only process changed files
)
```

### Memory-Efficient Processing

For very large repositories:

```python
processor = RepoProcessorImpl(
    memory_limit_mb=1024  # Limit to 1GB
)

# Use iterator to process one file at a time
for file_result in processor.process_files_iterator(repo_path):
    # Process chunks immediately
    for chunk in file_result.chunks:
        save_to_database(chunk)
```

### Custom File Selection

```python
result = processor.process_repository(
    repo_path,
    file_pattern="src/**/*.py",  # Only Python files in src/
    exclude_patterns=["**/test_*.py", "**/migrations/**"]
)
```

### Git-Aware Features

```python
from chunker.repo import GitAwareProcessorImpl

git_processor = GitAwareProcessorImpl()

# Get changed files
changed = git_processor.get_changed_files(
    repo_path,
    since_commit="HEAD~10"  # Last 10 commits
)

# Check if file should be processed
if git_processor.should_process_file(file_path, repo_path):
    # Process the file
```

## Performance Optimization

### Parallel Processing

```python
# Use multiple workers
processor = RepoProcessorImpl(
    max_workers=8,  # 8 parallel workers
    use_multiprocessing=True  # Use processes for CPU-bound work
)
```

### Batch Processing

```python
processor = RepoProcessorImpl(
    chunk_batch_size=200  # Process 200 files per batch
)
```

## Gitignore Support

The module fully respects `.gitignore` patterns:

```python
from chunker.repo.patterns import load_gitignore_patterns

# Load all .gitignore patterns from repository
matcher = load_gitignore_patterns(repo_path)

# Check if file should be ignored
if not matcher.should_ignore(file_path):
    # Process file
```

## Architecture

### Components

1. **RepoProcessor**: Main interface for repository processing
2. **GitAwareProcessor**: Git integration and incremental processing
3. **GitignoreMatcher**: Efficient gitignore pattern matching
4. **ProcessingStats**: Real-time statistics and monitoring

### Design Principles

- **Scalability**: Handle millions of files efficiently
- **Memory Safety**: Configurable limits and monitoring
- **Fault Tolerance**: Graceful error handling
- **Extensibility**: Easy to add new features

## Configuration

### Environment Variables

- `CHUNKER_MAX_WORKERS`: Default number of workers
- `CHUNKER_MEMORY_LIMIT_MB`: Default memory limit
- `CHUNKER_BATCH_SIZE`: Default batch size

### Processing Options

```python
processor = RepoProcessorImpl(
    max_workers=None,          # Auto-detect CPU count
    use_multiprocessing=False, # Use threads by default
    chunk_batch_size=100,      # Files per batch
    memory_limit_mb=None       # 50% of available RAM
)
```

## Error Handling

The processor handles errors gracefully:

```python
result = processor.process_repository(repo_path)

# Check for errors
if result.errors:
    for file_path, error in result.errors.items():
        print(f"Error in {file_path}: {error}")
```

## Best Practices

1. **Use incremental processing** for repositories under active development
2. **Set memory limits** for large repositories
3. **Use iterators** when processing results immediately
4. **Configure workers** based on your system (I/O vs CPU bound)
5. **Monitor progress** for long-running processes

## Performance Benchmarks

Typical performance on modern hardware:
- Small repos (<1K files): ~50-100 files/second
- Medium repos (10K files): ~30-50 files/second  
- Large repos (100K+ files): ~20-30 files/second

Factors affecting performance:
- File size and complexity
- Number of chunks per file
- Available CPU cores
- Disk I/O speed
- Memory available