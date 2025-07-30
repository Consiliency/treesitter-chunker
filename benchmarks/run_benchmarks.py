#!/usr/bin/env python3
"""
Run performance benchmarks for the treesitter-chunker.

Usage:
    python benchmarks/run_benchmarks.py [directory] [language]

Examples:
    python benchmarks/run_benchmarks.py . python
    python benchmarks/run_benchmarks.py ./examples python
    python benchmarks/run_benchmarks.py ./grammars/tree-sitter-rust/examples rust
"""
import argparse
import sys
from pathlib import Path

# Add parent directory to path to import chunker modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.benchmark import BenchmarkSuite, run_benchmarks


def print_results(suite: BenchmarkSuite):
    """Pretty print benchmark results."""
    summary = suite.get_summary()

    print("\n" + "=" * 60)
    print(f"Benchmark Suite: {summary['suite_name']}")
    print(f"Timestamp: {summary['timestamp']}")
    print("=" * 60)
    print(f"Total benchmarks run: {summary['total_benchmarks']}")
    print(f"Total duration: {summary['total_duration']:.3f}s")
    print(f"Total files processed: {summary['total_files']}")
    print(f"Total chunks extracted: {summary['total_chunks']}")
    print("\nIndividual Results:")
    print("-" * 60)

    for result in suite.results:
        print(f"\n{result.name}:")
        print(f"  Duration: {result.duration:.3f}s")
        print(f"  Files: {result.files_processed}")
        print(f"  Chunks: {result.chunks_processed}")

        if result.cache_hits > 0:
            print(f"  Cache hits: {result.cache_hits}")

        if "speedup" in result.metadata:
            print(f"  Cache speedup: {result.metadata['speedup']:.2f}x")

        if "num_workers" in result.metadata:
            print(f"  Workers: {result.metadata['num_workers']}")

    print("\n" + "=" * 60)

    # Find fastest method
    fastest = min(suite.results, key=lambda r: r.duration)
    print(f"\nFastest method: {fastest.name} ({fastest.duration:.3f}s)")

    # Calculate speedups relative to basic chunking
    basic_result = next((r for r in suite.results if r.name == "Basic Chunking"), None)
    if basic_result:
        print("\nSpeedups relative to basic chunking:")
        for result in suite.results:
            if result != basic_result:
                speedup = basic_result.duration / result.duration
                print(f"  {result.name}: {speedup:.2f}x")


def main():
    parser = argparse.ArgumentParser(
        description="Run treesitter-chunker performance benchmarks",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory containing files to benchmark (default: current directory)",
    )
    parser.add_argument(
        "language",
        nargs="?",
        default="python",
        help="Language to benchmark (default: python)",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--save", metavar="FILE", help="Save results to JSON file")

    args = parser.parse_args()

    directory = Path(args.directory)
    if not directory.exists():
        print(f"Error: Directory '{directory}' not found")
        sys.exit(1)

    try:
        suite = run_benchmarks(directory, args.language)

        if args.json:
            print(suite.to_json())
        else:
            print_results(suite)

        if args.save:
            with Path(args.save).open(
                "w",
            ) as f:
                f.write(suite.to_json())
            print(f"\nResults saved to {args.save}")

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except (OSError, ImportError, ModuleNotFoundError) as e:
        print(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
