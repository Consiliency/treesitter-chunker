#!/usr/bin/env python3
"""Fix remaining PERF401 - manual list comprehensions."""

import ast
import re
from pathlib import Path


class ListComprehensionFixer(ast.NodeTransformer):
    """AST transformer to fix manual list comprehensions."""
    
    def __init__(self):
        self.changed = False
    
    def visit_For(self, node):
        """Visit For loops to check for manual list comprehensions."""
        # Check if this is a simple list append pattern
        if (
            isinstance(node.body, list) 
            and len(node.body) == 1
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Call)
            and isinstance(node.body[0].value.func, ast.Attribute)
            and node.body[0].value.func.attr == 'append'
        ):
            # This looks like a list append pattern
            # We'll mark it for manual fixing since AST transformation is complex
            self.changed = True
        
        return self.generic_visit(node)


def fix_perf401_patterns(content: str) -> tuple[str, bool]:
    """Fix various PERF401 patterns using regex."""
    original = content
    
    # Pattern 1: Simple for loop with single append
    # result = []
    # for item in items:
    #     result.append(item)
    pattern1 = re.compile(
        r'(\s*)(\w+)\s*=\s*\[\]\s*\n'
        r'(\s*)for\s+(\w+)\s+in\s+([^:]+):\s*\n'
        r'(\s*)\2\.append\(([^)]+)\)\s*(?:\n|$)',
        re.MULTILINE
    )
    
    def replace1(match):
        indent = match.group(1)
        var_name = match.group(2)
        loop_var = match.group(4)
        iterable = match.group(5)
        expr = match.group(7)
        
        # If expression is just the loop variable, simplify
        if expr.strip() == loop_var:
            return f'{indent}{var_name} = list({iterable})'
        else:
            return f'{indent}{var_name} = [{expr} for {loop_var} in {iterable}]'
    
    content = pattern1.sub(replace1, content)
    
    # Pattern 2: For loop with if condition
    # result = []
    # for item in items:
    #     if condition:
    #         result.append(item)
    pattern2 = re.compile(
        r'(\s*)(\w+)\s*=\s*\[\]\s*\n'
        r'(\s*)for\s+(\w+)\s+in\s+([^:]+):\s*\n'
        r'(\s*)if\s+([^:]+):\s*\n'
        r'(\s*)\2\.append\(([^)]+)\)\s*(?:\n|$)',
        re.MULTILINE
    )
    
    def replace2(match):
        indent = match.group(1)
        var_name = match.group(2)
        loop_var = match.group(4)
        iterable = match.group(5)
        condition = match.group(7)
        expr = match.group(9)
        
        return f'{indent}{var_name} = [{expr} for {loop_var} in {iterable} if {condition}]'
    
    content = pattern2.sub(replace2, content)
    
    # Pattern 3: Nested attribute append
    # self.items = []
    # for x in data:
    #     self.items.append(x)
    pattern3 = re.compile(
        r'(\s*)(self\.\w+|[\w\.]+)\s*=\s*\[\]\s*\n'
        r'(\s*)for\s+(\w+)\s+in\s+([^:]+):\s*\n'
        r'(\s*)\2\.append\(([^)]+)\)\s*(?:\n|$)',
        re.MULTILINE
    )
    
    def replace3(match):
        indent = match.group(1)
        var_name = match.group(2)
        loop_var = match.group(4)
        iterable = match.group(5)
        expr = match.group(7)
        
        # If expression is just the loop variable, simplify
        if expr.strip() == loop_var:
            return f'{indent}{var_name} = list({iterable})'
        else:
            return f'{indent}{var_name} = [{expr} for {loop_var} in {iterable}]'
    
    content = pattern3.sub(replace3, content)
    
    # Pattern 4: List extend pattern
    # for item in items:
    #     result.extend([item])
    pattern4 = re.compile(
        r'(\s*)for\s+(\w+)\s+in\s+([^:]+):\s*\n'
        r'(\s*)(\w+)\.extend\(\[([^]]+)\]\)\s*(?:\n|$)',
        re.MULTILINE
    )
    
    def replace4(match):
        indent = match.group(1)
        loop_var = match.group(2)
        iterable = match.group(3)
        list_var = match.group(5)
        expr = match.group(6)
        
        return f'{indent}{list_var}.extend({expr} for {loop_var} in {iterable})'
    
    content = pattern4.sub(replace4, content)
    
    # Pattern 5: += [item] pattern
    # for item in items:
    #     result += [item]
    pattern5 = re.compile(
        r'(\s*)for\s+(\w+)\s+in\s+([^:]+):\s*\n'
        r'(\s*)(\w+)\s*\+=\s*\[([^]]+)\]\s*(?:\n|$)',
        re.MULTILINE
    )
    
    def replace5(match):
        indent = match.group(1)
        loop_var = match.group(2)
        iterable = match.group(3)
        list_var = match.group(5)
        expr = match.group(6)
        
        return f'{indent}{list_var}.extend({expr} for {loop_var} in {iterable})'
    
    content = pattern5.sub(replace5, content)
    
    return content, content != original


def fix_file(file_path: Path) -> bool:
    """Fix PERF401 issues in a single file."""
    try:
        with file_path.open('r', encoding='utf-8') as f:
            content = f.read()
        
        new_content, changed = fix_perf401_patterns(content)
        
        if changed:
            # Verify syntax
            try:
                compile(new_content, str(file_path), 'exec')
                with file_path.open('w', encoding='utf-8') as f:
                    f.write(new_content)
                return True
            except SyntaxError as e:
                print(f"Syntax error in {file_path}: {e}")
                return False
        
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to fix remaining PERF401 issues."""
    # Get files with PERF401 errors from ruff
    import subprocess
    
    result = subprocess.run(
        ['ruff', 'check', '--select', 'PERF401', '--output-format', 'json'],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("No PERF401 errors found")
        return
    
    import json
    try:
        errors = json.loads(result.stdout)
        files_to_fix = {Path(error['filename']) for error in errors}
    except:
        # Fallback to parsing text output
        result = subprocess.run(
            ['ruff', 'check', '--select', 'PERF401'],
            capture_output=True,
            text=True
        )
        files_to_fix = set()
        for line in result.stdout.splitlines():
            if 'PERF401' in line:
                parts = line.split(':')
                if parts:
                    files_to_fix.add(Path(parts[0]))
    
    print(f"Found {len(files_to_fix)} files with PERF401 errors")
    
    fixed_count = 0
    for file_path in sorted(files_to_fix):
        if fix_file(file_path):
            fixed_count += 1
            print(f"Fixed {file_path}")
    
    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()