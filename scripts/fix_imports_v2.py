"""Fix import organization more carefully."""
import subprocess
from pathlib import Path


def fix_imports_simple(file_path: Path) -> bool:
    """Fix imports with minimal changes - just move misplaced imports."""
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        if any(line.strip() and not line[0].isspace() and not line.
            startswith(("#", "import", "from", '"""', "'''", "def ",
            "class ", "@", "if ", "elif ", "else:", "try:", "except",
            "finally:", "with ", "for ", "while ")) for line in lines[10:]):
            return False
        import_insert_line = 0
        in_docstring = False
        docstring_char = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not in_docstring and stripped.startswith(('"""', "'''")):
                docstring_char = stripped[:3]
                if stripped.endswith(docstring_char) and len(stripped) > 6:
                    import_insert_line = i + 1
                    continue
                in_docstring = True
                continue
            if in_docstring and docstring_char in line:
                in_docstring = False
                import_insert_line = i + 1
                continue
            if (not in_docstring and stripped and not stripped.startswith("#")
                ) and not stripped.startswith(("import ", "from ")):
                break
        misplaced_imports = []
        first_code_line = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith(("#", "import ", "from ")):
                if first_code_line is None:
                    first_code_line = i
            elif first_code_line is not None and stripped.startswith((
                "import ", "from ")):
                misplaced_imports.append((i, line))
        if not misplaced_imports:
            return False
        for i, _ in reversed(misplaced_imports):
            del lines[i]
        for _, import_line in reversed(misplaced_imports):
            lines.insert(import_insert_line, import_line)
        new_content = "".join(lines)
        if new_content != content:
            file_path.write_text(new_content, encoding="utf-8")
            return True
        return False
    except (OSError, FileNotFoundError, ImportError) as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function."""
    repo_root = Path.cwd()
    result = subprocess.run(["git", "ls-files", "*.py"], check=False,
        capture_output=True, text=True, cwd=repo_root)
    if result.returncode != 0:
        print("Error getting file list from git")
        return
    python_files = [(repo_root / f.strip()) for f in result.stdout.
        splitlines() if f.strip() and not f.startswith((".venv", "venv",
        "build"))]
    fixed_count = 0
    print(f"Processing {len(python_files)} Python files...")
    for file_path in python_files:
        if fix_imports_simple(file_path):
            print(f"Fixed: {file_path}")
            fixed_count += 1
    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
