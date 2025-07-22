# Incremental Processing

The incremental processing feature enables efficient processing of large codebases by only re-processing files that have changed. This dramatically reduces processing time for subsequent runs after an initial full scan.

## Overview

The incremental processing system consists of four main components:

1. **IncrementalProcessor** - Computes diffs between old and new chunks, detects moved code
2. **ChunkCache** - Stores and retrieves chunks with file hashing for validation
3. **ChangeDetector** - Efficiently finds changed regions in code
4. **IncrementalIndex** - Updates search indexes incrementally (optional)

## Key Features

- **File Hash Validation**: Uses SHA-256 hashing to detect file changes
- **Efficient Diff Computation**: Only processes changed portions of files
- **Move Detection**: Identifies code that has been moved within or between files
- **Persistent Cache**: Export/import cache for sharing across systems
- **Cache Statistics**: Track hit rates and cache performance
- **Flexible Storage**: File-based cache with configurable location

## Usage

### Basic Incremental Processing

```python
from chunker import (
    DefaultIncrementalProcessor,
    DefaultChunkCache,
    DefaultChangeDetector,
    chunk_file
)

# Initialize components
processor = DefaultIncrementalProcessor()
cache = DefaultChunkCache(".chunker_cache")
detector = DefaultChangeDetector()

# Initial processing
file_path = "example.py"
with open(file_path) as f:
    content = f.read()

# Get initial chunks and hash
initial_chunks = chunk_file(file_path, language="python")
file_hash = detector.compute_file_hash(content)

# Cache the results
cache.store(file_path, initial_chunks, file_hash)

# Later, when file might have changed...
with open(file_path) as f:
    new_content = f.read()

new_hash = detector.compute_file_hash(new_content)

# Check if file changed
if new_hash != file_hash:
    # Retrieve cached chunks
    cache_entry = cache.retrieve(file_path, file_hash)
    if cache_entry:
        # Compute diff
        diff = processor.compute_diff(
            cache_entry.chunks, 
            new_content, 
            "python"
        )
        
        # Update chunks based on diff
        updated_chunks = processor.update_chunks(
            cache_entry.chunks, 
            diff
        )
        
        # Store updated results
        cache.store(file_path, updated_chunks, new_hash)
```

### Change Detection

```python
# Find specific changed regions
old_content = "def hello():\n    print('Hello')\n"
new_content = "def hello():\n    print('Hello, World!')\n"

regions = detector.find_changed_regions(old_content, new_content)
# Returns: [(2, 2)] - line 2 changed

# Classify type of change
changed_lines = {2}
change_type = detector.classify_change(chunk, new_content, changed_lines)
# Returns: ChangeType.MODIFIED
```

### Cache Management

```python
# Get cache statistics
stats = cache.get_statistics()
print(f"Cache entries: {stats['entries']}")
print(f"Hit rate: {stats['hit_rate']:.2%}")
print(f"Size: {stats['total_size_mb']:.2f} MB")

# Invalidate old entries
from datetime import datetime, timedelta
week_ago = datetime.now() - timedelta(days=7)
count = cache.invalidate(older_than=week_ago)
print(f"Removed {count} old entries")

# Export/import cache
cache.export_cache("cache_backup.json")
new_cache = DefaultChunkCache()
new_cache.import_cache("cache_backup.json")
```

### Diff Information

The `ChunkDiff` object provides detailed information about changes:

```python
diff = processor.compute_diff(old_chunks, new_content, "python")

print(f"Summary: {diff.summary}")
# {'added': 2, 'deleted': 1, 'modified': 3, 'moved': 1, 'unchanged': 5}

# Iterate through changes
for change in diff.changes:
    print(f"{change.change_type}: {change.chunk_id}")
    if change.change_type == ChangeType.MODIFIED:
        print(f"  Lines changed: {change.line_changes}")
        print(f"  Confidence: {change.confidence}")
```

### Incremental Index Updates

```python
from chunker import SimpleIncrementalIndex

index = SimpleIncrementalIndex()

# Update index based on diff
index.batch_update(diff)

# Check if full rebuild would be more efficient
cost = index.get_update_cost(diff)
if cost > 0.8:
    print("Consider full rebuild - too many changes")

# Search updated index
results = index.search("function_name")
```

## Change Types

The system recognizes several types of changes:

- **ADDED**: New chunks added to the file
- **DELETED**: Chunks removed from the file
- **MODIFIED**: Chunk content changed but remains in same location
- **MOVED**: Chunk content moved to different location (>85% similarity)
- **RENAMED**: (Future) Chunk renamed but content similar

## Performance Considerations

1. **Initial Scan**: The first run requires full processing
2. **Cache Size**: Monitor cache size and periodically clean old entries
3. **Hash Computation**: File hashing is fast but adds overhead for large files
4. **Move Detection**: Uses similarity matching which can be expensive for many chunks

## Advanced Configuration

### Custom Cache Directory

```python
cache = DefaultChunkCache("/path/to/cache")
```

### Custom Change Detection Threshold

```python
class CustomChangeDetector(DefaultChangeDetector):
    def classify_change(self, old_chunk, new_content, changed_lines):
        # Custom logic for change classification
        overlap_ratio = len(changed_lines & chunk_lines) / len(chunk_lines)
        if overlap_ratio < 0.1:
            return ChangeType.MODIFIED
        return super().classify_change(old_chunk, new_content, changed_lines)
```

### Integration with Repository Processing

```python
from chunker import GitAwareProcessor

# Automatically uses incremental processing for git repositories
processor = GitAwareProcessor(use_incremental=True)
result = processor.process_repository(".", 
    included_extensions=[".py", ".js"],
    use_cache=True
)
```

## Best Practices

1. **Regular Cache Cleanup**: Set up periodic cleanup of old cache entries
2. **Cache Persistence**: Export cache before system migrations
3. **Hash Validation**: Always validate with file hash to ensure cache validity
4. **Batch Processing**: Process multiple files together for better performance
5. **Monitor Hit Rate**: Low hit rates might indicate cache configuration issues