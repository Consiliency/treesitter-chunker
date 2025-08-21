#!/usr/bin/env python3
"""MkDocs server launcher with live-reload."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Launch MkDocs server with live-reload."""
    project_root = Path(__file__).parent.parent

    # Check if mkdocs is installed
    try:
        import mkdocs

        print(f"✅ MkDocs {mkdocs.__version__} found")
    except ImportError:
        print("❌ MkDocs not found. Installing...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "mkdocs[extra]"],
            check=True,
        )

    # Change to project root
    os.chdir(project_root)

    print("🚀 Starting MkDocs server...")
    print("�� Documentation will be available at: http://127.0.0.1:8000")
    print("🔄 Live-reload enabled - changes will auto-refresh")
    print("⏹️  Press Ctrl+C to stop the server")
    print()

    # Start MkDocs server
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "mkdocs",
                "serve",
                "--dev-addr",
                "127.0.0.1:8000",
                "--livereload",
            ],
            check=True,
        )
    except KeyboardInterrupt:
        print("\n🛑 MkDocs server stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting MkDocs server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
