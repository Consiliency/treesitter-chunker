#!/usr/bin/env python3
"""Example usage of repository-level processing.

This example shows how to use the repository processing features
for large-scale code analysis.
"""

from pathlib import Path
from chunker.repo import RepoProcessorImpl, GitAwareProcessorImpl
from chunker.repo.patterns import load_gitignore_patterns

def process_repository_example():
    """Example: Process an entire repository with Git awareness."""
    
    # Initialize processor with optimized settings for large repos
    processor = RepoProcessorImpl(
        max_workers=8,              # Use 8 parallel workers
        use_multiprocessing=False,  # Use threads (faster for I/O)
        chunk_batch_size=100,       # Process 100 files per batch
        memory_limit_mb=2048        # Limit memory to 2GB
    )
    
    # Process a repository (incremental mode)
    repo_path = "/path/to/your/repository"
    
    # This would process only changed files since last run
    result = processor.process_repository(
        repo_path,
        incremental=True,           # Only process changed files
        file_pattern="**/*.py",     # Only Python files
        exclude_patterns=["**/test_*.py", "**/migrations/**"]
    )
    
    # Display results
    print(f"Repository: {result.repo_path}")
    print(f"Total files: {result.total_files}")
    print(f"Total chunks: {result.total_chunks}")
    print(f"Processing time: {result.processing_time:.2f}s")
    print(f"Files/second: {result.metadata['stats']['files_per_second']:.1f}")
    
    # Check for errors
    if result.errors:
        print(f"\nErrors in {len(result.errors)} files:")
        for file, error in list(result.errors.items())[:5]:
            print(f"  - {file}: {error}")


def process_with_iterator_example():
    """Example: Process repository using iterator for memory efficiency."""
    
    processor = RepoProcessorImpl(max_workers=4)
    repo_path = "/path/to/large/repository"
    
    # Process files one at a time to minimize memory usage
    total_chunks = 0
    total_files = 0
    
    for file_result in processor.process_files_iterator(repo_path):
        total_files += 1
        total_chunks += len(file_result.chunks)
        
        # Process chunks immediately (e.g., save to database)
        for chunk in file_result.chunks:
            # Your processing logic here
            pass
            
        # Free memory after processing each file
        if total_files % 100 == 0:
            print(f"Processed {total_files} files, {total_chunks} chunks...")


def git_aware_processing_example():
    """Example: Use Git awareness for smart processing."""
    
    git_processor = GitAwareProcessorImpl()
    repo_path = "/path/to/git/repository"
    
    # Get files changed in last 10 commits
    changed_files = git_processor.get_changed_files(
        repo_path, 
        since_commit="HEAD~10"
    )
    
    print(f"Files changed in last 10 commits: {len(changed_files)}")
    
    # Get file history
    for file in changed_files[:3]:
        history = git_processor.get_file_history(
            file, 
            repo_path, 
            limit=5
        )
        print(f"\nHistory for {file}:")
        for commit in history:
            print(f"  - {commit['date']}: {commit['message']} ({commit['author']})")
    
    # Save state for incremental processing
    state = {
        'processed_files': changed_files,
        'processing_config': {
            'chunk_size_threshold': 100,
            'languages': ['python', 'javascript']
        }
    }
    git_processor.save_incremental_state(repo_path, state)


def gitignore_pattern_example():
    """Example: Work with gitignore patterns."""
    
    repo_path = Path("/path/to/repository")
    
    # Load all gitignore patterns from repository
    matcher = load_gitignore_patterns(repo_path)
    
    # Check specific files
    files_to_check = [
        "src/main.py",
        "build/output.exe",
        "node_modules/package.json",
        ".env.local",
        "docs/api.md"
    ]
    
    for file in files_to_check:
        if matcher.should_ignore(Path(file)):
            print(f"IGNORE: {file}")
        else:
            print(f"PROCESS: {file}")
    
    # Filter a list of files
    all_files = list(repo_path.rglob("*"))
    processable_files = matcher.filter_paths(all_files)
    
    print(f"\nTotal files: {len(all_files)}")
    print(f"Processable files: {len(processable_files)}")
    print(f"Ignored files: {len(all_files) - len(processable_files)}")


if __name__ == "__main__":
    print("Repository Processing Examples")
    print("=" * 50)
    print("\nThese are code examples. Replace paths with actual repositories.")
    print("\nKey features demonstrated:")
    print("- Parallel processing with memory limits")
    print("- Git-aware incremental processing")
    print("- Iterator-based processing for large repos")
    print("- Gitignore pattern matching")
    print("\nSee the code for implementation details.")