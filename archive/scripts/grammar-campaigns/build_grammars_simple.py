#!/usr/bin/env python3
"""Simple sequential build of all tree-sitter grammars."""

import json
import subprocess
import sys
from pathlib import Path


def main():
    # Load grammar sources
    sources_path = Path(__file__).parent.parent / "config" / "grammar_sources.json"
    with sources_path.open("r", encoding="utf-8") as f:
        sources = json.load(f)

    # Ensure output directories exist
    output_dir = (
        Path(__file__).parent.parent / "chunker" / "data" / "grammars" / "build"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    build_dir = Path(__file__).parent.parent / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    # Track results
    successful = []
    failed = []
    already_built = []

    for language in sorted(sources.keys()):
        # Check if already built
        output_file = output_dir / f"{language}.so"
        build_file = build_dir / f"{language}.so"

        if output_file.exists() or build_file.exists():
            already_built.append(language)
            print(f"✓ {language}: Already built")
            continue

        print(f"Building {language}...", end=" ")

        # Use the grammar manager CLI
        cmd = [sys.executable, "-m", "chunker.grammar.manager", "build", language]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

            # Check if file was created
            if output_file.exists() or build_file.exists():
                successful.append(language)
                print("✓")

                # Move from build to package dir if needed
                if build_file.exists() and not output_file.exists():
                    build_file.rename(output_file)
            else:
                failed.append(language)
                print("✗ (no output file)")
                if result.stderr:
                    print(f"  Error: {result.stderr[:200]}")

        except subprocess.TimeoutExpired:
            failed.append(language)
            print("✗ (timeout)")
        except Exception as e:
            failed.append(language)
            print(f"✗ ({e})")

    # Summary
    print("\n" + "=" * 60)
    print("Build Summary:")
    print(f"  Already built: {len(already_built)}")
    print(f"  Successful: {len(successful)}")
    print(f"  Failed: {len(failed)}")

    total_built = len(already_built) + len(successful)
    print(f"\nTotal grammars available: {total_built}/{len(sources)}")

    if failed:
        print(f"\nFailed languages: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
