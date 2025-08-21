#!/usr/bin/env python3
"""Launch both MkDocs and Sphinx servers simultaneously."""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path


def run_mkdocs():
    """Run MkDocs server in background."""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

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
    except subprocess.CalledProcessError as e:
        print(f"❌ MkDocs error: {e}")


def run_sphinx():
    """Run Sphinx server in background."""
    project_root = Path(__file__).parent.parent
    sphinx_dir = project_root / "docs" / "sphinx"
    os.chdir(sphinx_dir)

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
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"❌ Sphinx error: {e}")


def main():
    """Launch both servers."""
    print("🚀 Launching both documentation servers...")
    print()
    print("📖 MkDocs (Material theme): http://127.0.0.1:8000")
    print("📚 Sphinx (Read the Docs theme): http://127.0.0.1:8001")
    print()
    print("🔄 Both servers have live-reload enabled")
    print("⏹️  Press Ctrl+C to stop all servers")
    print()

    # Start servers in separate threads
    mkdocs_thread = threading.Thread(target=run_mkdocs, daemon=True)
    sphinx_thread = threading.Thread(target=run_sphinx, daemon=True)

    mkdocs_thread.start()
    time.sleep(2)  # Small delay to avoid port conflicts
    sphinx_thread.start()

    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping all servers...")
        print("✅ Servers stopped")


if __name__ == "__main__":
    main()
