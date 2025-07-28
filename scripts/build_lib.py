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

    # Gather all C source files and include directories
    c_files = []
    include_dirs = set()
    for gram in grammars_dir.glob("tree-sitter-*"):
        src_dir = gram / "src"
        if src_dir.exists():
            include_dirs.add(str(src_dir))
            for src in src_dir.glob("*.c"):
                c_files.append(str(src))

    if not c_files:
        print("WARNING: No C source files found. Did you fetch grammars?")
        return

    cmd = ["gcc", "-shared", "-fPIC"]
    for inc in include_dirs:
        cmd.extend(["-I", inc])
    cmd += ["-o", str(lib_path)] + c_files

    print("Compiling Tree-sitter grammars into", lib_path)
    subprocess.run(cmd, check=True)
    print("SUCCESS: Built", lib_path)


if __name__ == "__main__":
    main()
