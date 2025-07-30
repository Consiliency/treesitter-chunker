"""Example of repository processing with the chunker."""

import time

from chunker.repo.processor import GitAwareRepoProcessor, RepoProcessor


def basic_repo_processing():
    """Basic repository processing example."""
    print("=== Basic Repository Processing ===")

    # Create a basic processor
    processor = RepoProcessor(show_progress=True)

    # Process the current directory
    result = processor.process_repository(".", incremental=False)

    print(f"\nProcessed {result.total_files} files")
    print(f"Generated {result.total_chunks} chunks")
    print(f"Processing took {result.processing_time:.2f} seconds")

    # Show some chunk details
    if result.file_results:
        print("\nSample chunks from first file_path:")
        first_file = result.file_results[0]
        print(f"  File: {first_file.file_path}")
        for i, chunk in enumerate(first_file.chunks[:3]):
            print(
                f"  Chunk {i+1}: {chunk.chunk_type} '{chunk.name}' (lines {chunk.start_line}-{chunk.end_line})",
            )


def git_aware_processing():
    """Git-aware repository processing example."""
    print("\n=== Git-Aware Repository Processing ===")

    # Create a Git-aware processor
    processor = GitAwareRepoProcessor(show_progress=False)

    # Check for changed files
    try:
        changed_files = processor.get_changed_files(".", since_commit="HEAD~1")
        print(f"Changed files since last commit: {len(changed_files)}")
        for file_path in changed_files[:5]:
            print(f"  - {file_path}")
    except (FileNotFoundError, IndexError, KeyError) as e:
        print(f"Not a git repository or no commits: {e}")

    # Process with incremental mode
    result = processor.process_repository(".", incremental=True)
    print("\nIncremental processing completed:")
    print(f"  Processed files: {len(result.file_results)}")
    print(f"  Total chunks: {result.total_chunks}")


def filtered_processing():
    """Example with file_path filtering."""
    print("\n=== Filtered Repository Processing ===")

    processor = RepoProcessor(show_progress=False)

    # Process only Python files, excluding tests
    result = processor.process_repository(
        ".",
        incremental=False,
        file_pattern="*.py",
        exclude_patterns=["tests/*", "*/test_*.py"],
    )

    print(f"Processed {len(result.file_results)} Python files (excluding tests)")
    print(f"Total chunks: {result.total_chunks}")

    # Show language distribution
    lang_counts = {}
    for file_result in result.file_results:
        for chunk in file_result.chunks:
            lang = chunk.metadata.get("language", "unknown")
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

    print("\nChunks by language:")
    for lang, count in sorted(lang_counts.items()):
        print(f"  {lang}: {count}")


def memory_efficient_processing():
    """Example using iterator for memory efficiency."""
    print("\n=== Memory-Efficient Processing ===")

    processor = RepoProcessor(show_progress=False)

    # Process files one at a time
    total_chunks = 0
    file_count = 0

    for file_result in processor.process_files_iterator("."):
        file_count += 1
        total_chunks += len(file_result.chunks)

        # Process each file_path as it comes
        if file_count <= 3:
            print(
                f"Processing: {file_result.file_path} ({len(file_result.chunks)} chunks)",
            )

    print(f"\nProcessed {file_count} files with {total_chunks} total chunks")


def parallel_processing():
    """Example with different parallelization settings."""
    print("\n=== Parallel Processing Comparison ===")

    # Single-threaded processing
    processor_single = RepoProcessor(show_progress=False, max_workers=1)
    start = time.time()
    result_single = processor_single.process_repository(".", incremental=False)
    time_single = time.time() - start

    # Multi-threaded processing
    processor_multi = RepoProcessor(show_progress=False, max_workers=4)
    start = time.time()
    result_multi = processor_multi.process_repository(".", incremental=False)
    time_multi = time.time() - start

    print(
        f"Single-threaded: {time_single:.2f}s for {result_single.total_chunks} chunks",
    )
    print(
        f"Multi-threaded (4 workers): {time_multi:.2f}s for {result_multi.total_chunks} chunks",
    )
    print(f"Speedup: {time_single/time_multi:.2f}x")


if __name__ == "__main__":
    # Run examples
    basic_repo_processing()
    git_aware_processing()
    filtered_processing()
    memory_efficient_processing()
    parallel_processing()
