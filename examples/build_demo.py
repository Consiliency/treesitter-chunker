#!/usr/bin/env python3
"""
Demonstration of the Build System component
"""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chunker.build import BuildSystem, PlatformSupport


def main():
    """Demonstrate build system functionality"""
    print("=== Tree-sitter Chunker Build System Demo ===\n")

    # Initialize components
    build_sys = BuildSystem()
    platform = PlatformSupport()

    # 1. Platform Detection
    print("1. Detecting Platform...")
    platform_info = platform.detect_platform()

    print(f"   OS: {platform_info['os']}")
    print(f"   Architecture: {platform_info['arch']}")
    print(
        f"   Python: {platform_info['python_version']} ({platform_info['python_impl']})",
    )
    print(f"   Compiler: {platform_info['compiler']}")
    print(f"   Platform Tag: {platform_info['platform_tag']}")
    print(f"   Python Tag: {platform_info['python_tag']}")

    if platform_info["os"] == "linux" and platform_info["libc"]:
        print(f"   libc: {platform_info['libc']}")
    print()

    # 2. Grammar Compilation
    print("2. Compiling Grammars...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "build"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Compile a subset of languages
        languages = ["python", "javascript", "rust"]
        success, build_info = build_sys.compile_grammars(
            languages=languages,
            platform=platform_info["os"],
            output_dir=output_dir,
        )

        if success:
            print("   ✓ Compilation successful!")
            print(f"   Libraries built: {len(build_info['libraries'])}")
            for name, path in build_info["libraries"].items():
                print(f"     - {name}: {Path(path).name}")
        else:
            print("   ✗ Compilation failed!")
            print(f"   Errors: {build_info['errors']}")
        print()

        # 3. Wheel Building
        print("3. Building Wheel...")

        dist_dir = Path(tmpdir) / "dist"
        dist_dir.mkdir(parents=True, exist_ok=True)

        wheel_success, wheel_path = build_sys.build_wheel(
            platform=platform_info["os"],
            python_version=platform_info["python_tag"],
            output_dir=dist_dir,
        )

        if wheel_success:
            print(f"   ✓ Wheel built: {wheel_path.name}")
            print(f"   Size: {wheel_path.stat().st_size / 1024:.1f} KB")

            # 4. Verify Build
            print("\n4. Verifying Wheel...")

            valid, report = build_sys.verify_build(wheel_path, platform_info["os"])

            if valid:
                print("   ✓ Wheel is valid!")
            else:
                print("   ✗ Wheel validation failed!")

            print("   Components:")
            for component, present in report["components"].items():
                status = "✓" if present else "✗"
                print(f"     {status} {component}")

            if report.get("missing"):
                print(f"   Missing: {', '.join(report['missing'])}")

            if report.get("errors"):
                print(f"   Errors: {report['errors']}")
        else:
            print("   ✗ Wheel build failed!")
        print()

        # 5. Conda Package (if available)
        print("5. Building Conda Package...")

        conda_success, conda_path = build_sys.create_conda_package(
            platform=platform_info["os"],
            output_dir=dist_dir,
        )

        if conda_success:
            print(f"   ✓ Conda package built: {conda_path.name}")
        else:
            print("   ✗ Conda build not available (requires conda-build)")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
