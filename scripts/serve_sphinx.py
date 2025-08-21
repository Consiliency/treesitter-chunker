#!/usr/bin/env python3
"""Sphinx server launcher with live-reload."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Launch Sphinx server with live-reload."""
    project_root = Path(__file__).parent.parent
    sphinx_dir = project_root / "docs" / "sphinx"

    # Check if sphinx is installed
    try:
        import sphinx

        print(f"✅ Sphinx {sphinx.__version__} found")
    except ImportError:
        print("❌ Sphinx not found. Installing...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "sphinx[extra]"],
            check=True,
        )

    # Check if sphinx-autobuild is installed
    try:
        import sphinx_autobuild

        print("✅ sphinx-autobuild found")
    except ImportError:
        print("❌ sphinx-autobuild not found. Installing...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "sphinx-autobuild"],
            check=True,
        )

    # Change to sphinx directory
    if not sphinx_dir.exists():
        print(f"❌ Sphinx directory not found: {sphinx_dir}")
        sys.exit(1)

    os.chdir(sphinx_dir)

    print("🚀 Starting Sphinx server...")
    print("�� Documentation will be available at: http://127.0.0.1:8001")
    print("🔄 Live-reload enabled - changes will auto-refresh")
    print("⏹️  Press Ctrl+C to stop the server")
    print()

    # Start Sphinx server with autobuild
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "sphinx_autobuild",
                "source",
                "_build/html",
                "--host",
                "127.0.0.1",
                "--port",
                "8001",
                "--open-browser",
            ],
            check=True,
        )
    except KeyboardInterrupt:
        print("\n🛑 Sphinx server stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting Sphinx server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
