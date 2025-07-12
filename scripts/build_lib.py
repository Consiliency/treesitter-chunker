# scripts/build_lib.py
#!/usr/bin/env python3
"""
Compile all Tree-sitter grammars into a single shared library.
Usage: python scripts/build_lib.py
"""
import subprocess
from pathlib import Path

def main():
    grammars_dir = Path(__file__).parent.parent / "grammars"
    build_dir = Path(__file__).parent.parent / "build"
    build_dir.mkdir(exist_ok=True)
    lib_path = build_dir / "my-languages.so"

    # Gather all C source files (parser.c and scanner.c) from each grammar
    c_files = []
    for gram in grammars_dir.glob("tree-sitter-*"):
        for src in gram.glob("src/*.c"):
            c_files.append(str(src))

    if not c_files:
        print("⚠️ No C source files found. Did you fetch grammars?")
        return

    cmd = [
        "gcc",
        "-shared",
        "-fPIC",
        "-o",
        str(lib_path),
    ] + c_files

    print("Compiling Tree-sitter grammars into", lib_path)
    subprocess.run(cmd, check=True)
    print("✅ Built", lib_path)

if __name__ == "__main__":
    main()
