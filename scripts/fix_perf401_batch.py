#!/usr/bin/env python3
"""Fix PERF401 errors in batch using ruff's auto-fix capability."""

import subprocess


def main():
    """Run ruff to fix PERF401 errors."""
    # Get all Python files with PERF401 errors
    result = subprocess.run(
        ["ruff", "check", "--select", "PERF401", "--no-fix"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        print("No PERF401 errors found!")
        return

    # Extract file paths from output
    files_with_errors = set()
    for line in result.stdout.splitlines():
        if "PERF401" in line:
            # Line format: "path/to/file.py:line:col: PERF401 ..."
            parts = line.split(":")
            if len(parts) >= 3:
                files_with_errors.add(parts[0])

    print(f"Found PERF401 errors in {len(files_with_errors)} files")

    # Fix files in batches to avoid overwhelming the system
    files_list = list(files_with_errors)
    batch_size = 10

    for i in range(0, len(files_list), batch_size):
        batch = files_list[i : i + batch_size]
        print(
            f"\nFixing batch {i//batch_size + 1}/{(len(files_list) + batch_size - 1)//batch_size}",
        )

        # Run ruff fix on this batch
        cmd = ["ruff", "check", "--select", "PERF401", "--fix"] + batch
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode == 0:
            print(f"  Fixed {len(batch)} files successfully")
        else:
            print("  Some fixes may have failed:")
            if result.stderr:
                print(f"  {result.stderr}")

    # Final check
    result = subprocess.run(
        ["ruff", "check", "--select", "PERF401", "--no-fix"],
        capture_output=True,
        text=True,
        check=False,
    )

    remaining_errors = len(
        [line for line in result.stdout.splitlines() if "PERF401" in line],
    )
    print(f"\nRemaining PERF401 errors: {remaining_errors}")


if __name__ == "__main__":
    main()
