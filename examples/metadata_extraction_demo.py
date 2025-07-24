#!/usr/bin/env python3
"""
Demonstrate metadata extraction capabilities.
"""

import json

from chunker.metadata.languages import (
    JavaScriptComplexityAnalyzer,
    JavaScriptMetadataExtractor,
    PythonComplexityAnalyzer,
    PythonMetadataExtractor,
)
from chunker.parser import get_parser


def demo_python_metadata():
    """Demonstrate Python metadata extraction."""
    print("=== Python Metadata Extraction Demo ===\n")

    code = b'''
def calculate_fibonacci(n: int, memo: dict = None) -> int:
    """
    Calculate the nth Fibonacci number using memoization.
    
    Args:
        n: The position in the Fibonacci sequence
        memo: Optional memoization dictionary
        
    Returns:
        The nth Fibonacci number
    """
    if memo is None:
        memo = {}
        
    if n in memo:
        return memo[n]
        
    if n <= 1:
        return n
    else:
        result = calculate_fibonacci(n - 1, memo) + calculate_fibonacci(n - 2, memo)
        memo[n] = result
        return result
'''

    parser = get_parser("python")
    tree = parser.parse(code)
    func_node = tree.root_node.children[0]

    # Extract metadata
    extractor = PythonMetadataExtractor("python")
    analyzer = PythonComplexityAnalyzer()

    # Extract signature
    signature = extractor.extract_signature(func_node, code)
    print("Function Signature:")
    print(f"  Name: {signature.name}")
    print(f"  Parameters: {json.dumps(signature.parameters, indent=4)}")
    print(f"  Return Type: {signature.return_type}")

    # Extract docstring
    docstring = extractor.extract_docstring(func_node, code)
    print(f"\nDocstring: {docstring[:60]}...")

    # Extract dependencies
    deps = extractor.extract_dependencies(func_node, code)
    print(f"\nDependencies: {deps}")

    # Analyze complexity
    metrics = analyzer.analyze_complexity(func_node, code)
    print("\nComplexity Metrics:")
    print(f"  Cyclomatic Complexity: {metrics.cyclomatic}")
    print(f"  Cognitive Complexity: {metrics.cognitive}")
    print(f"  Max Nesting Depth: {metrics.nesting_depth}")
    print(f"  Lines of Code: {metrics.lines_of_code}")
    print(f"  Logical Lines: {metrics.logical_lines}")


def demo_javascript_metadata():
    """Demonstrate JavaScript metadata extraction."""
    print("\n\n=== JavaScript Metadata Extraction Demo ===\n")

    code = b"""
/**
 * Merge two sorted arrays into a single sorted array.
 * @param {number[]} arr1 - First sorted array
 * @param {number[]} arr2 - Second sorted array
 * @returns {number[]} Merged sorted array
 */
async function mergeSortedArrays(arr1, arr2 = []) {
    const result = [];
    let i = 0, j = 0;
    
    while (i < arr1.length && j < arr2.length) {
        if (arr1[i] <= arr2[j]) {
            result.push(arr1[i]);
            i++;
        } else {
            result.push(arr2[j]);
            j++;
        }
    }
    
    // Add remaining elements
    while (i < arr1.length) {
        result.push(arr1[i]);
        i++;
    }
    
    while (j < arr2.length) {
        result.push(arr2[j]);
        j++;
    }
    
    return result;
}
"""

    parser = get_parser("javascript")
    tree = parser.parse(code)

    # Find the function (skip the JSDoc comment)
    func_node = None
    for child in tree.root_node.children:
        if child.type == "function_declaration":
            func_node = child
            break

    # Extract metadata
    extractor = JavaScriptMetadataExtractor("javascript")
    analyzer = JavaScriptComplexityAnalyzer()

    # Extract signature
    signature = extractor.extract_signature(func_node, code)
    print("Function Signature:")
    print(f"  Name: {signature.name}")
    print(f"  Parameters: {json.dumps(signature.parameters, indent=4)}")
    print(f"  Modifiers: {signature.modifiers}")

    # Extract JSDoc
    docstring = extractor.extract_docstring(func_node, code)
    if docstring:
        print(f"\nJSDoc: {docstring[:100]}...")

    # Analyze complexity
    metrics = analyzer.analyze_complexity(func_node, code)
    print("\nComplexity Metrics:")
    print(f"  Cyclomatic Complexity: {metrics.cyclomatic}")
    print(f"  Cognitive Complexity: {metrics.cognitive}")
    print(f"  Max Nesting Depth: {metrics.nesting_depth}")
    print(f"  Lines of Code: {metrics.lines_of_code}")
    print(f"  Logical Lines: {metrics.logical_lines}")


if __name__ == "__main__":
    demo_python_metadata()
    demo_javascript_metadata()
