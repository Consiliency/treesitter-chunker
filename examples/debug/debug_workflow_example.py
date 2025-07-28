"""
Example demonstrating Tree-sitter debug workflows.
"""

from chunker.debug import (
    ASTVisualizer,
    ChunkDebugger,
    QueryDebugger,
    highlight_chunk_boundaries,
)


def example_ast_visualization():
    """Example: Visualize AST for Python code."""
    print("=== AST Visualization Example ===")

    # Create visualizer
    visualizer = ASTVisualizer("python")

    # Sample code
    code = '''
def calculate_sum(numbers):
    """Calculate sum of numbers."""
    total = 0
    for num in numbers:
        total += num
    return total

class Calculator:
    def __init__(self):
        self.result = 0

    def add(self, x, y):
        self.result = x + y
        return self.result
'''

    # Save to temp file
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        temp_file = f.name

    # Visualize as tree
    print("\n1. Tree visualization:")
    visualizer.visualize_file(
        temp_file,
        output_format="tree",
        max_depth=3,
        highlight_nodes={"function_definition", "class_definition"},
    )

    # Clean up
    import os

    os.unlink(temp_file)


def example_query_debugging():
    """Example: Debug Tree-sitter queries."""
    print("\n=== Query Debugging Example ===")

    # Sample Python code
    code = """
def process_data(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result

async def fetch_data(url):
    response = await http.get(url)
    return response.json()
"""

    # Create debugger
    debugger = QueryDebugger("python")

    # Example 1: Find all function definitions
    print("\n1. Finding function definitions:")
    query1 = """
    (function_definition
      name: (identifier) @func_name
    )
    """
    debugger.debug_query(query1, code)

    # Example 2: Find async functions
    print("\n2. Finding async functions:")
    query2 = """
    (function_definition
      "async"
      name: (identifier) @async_func
    )
    """
    debugger.debug_query(query2, code)

    # Example 3: Find conditional statements
    print("\n3. Finding if statements:")
    query3 = """
    (if_statement
      condition: (_) @condition
      consequence: (block) @then_block
    )
    """
    debugger.debug_query(query3, code)


def example_chunk_analysis():
    """Example: Analyze chunking decisions."""
    print("\n=== Chunk Analysis Example ===")

    # Sample code with various structures
    code = '''
def small_function():
    return 42

def medium_function(x, y):
    """A medium-sized function."""
    result = x + y
    if result > 100:
        print("Large result")
    return result

class DataProcessor:
    """Process data with multiple methods."""

    def __init__(self, config):
        self.config = config
        self.data = []

    def load_data(self, path):
        """Load data from file."""
        with open(path) as f:
            self.data = json.load(f)

    def process(self):
        """Process loaded data."""
        results = []
        for item in self.data:
            if self.validate(item):
                results.append(self.transform(item))
        return results

    def validate(self, item):
        """Validate a single item."""
        return item.get('valid', False)

    def transform(self, item):
        """Transform a single item."""
        return {
            'id': item['id'],
            'value': item['value'] * 2
        }
'''

    # Save to temp file
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        temp_file = f.name

    # Create chunk debugger
    debugger = ChunkDebugger("python")

    # Analyze chunking
    print("\nAnalyzing chunking decisions...")
    debugger.analyze_file(
        temp_file,
        show_decisions=True,
        show_overlap=True,
        show_gaps=True,
        min_chunk_size=3,
        max_chunk_size=20,
    )

    # Also show visual boundaries
    print("\n\nVisualizing chunk boundaries...")
    highlight_chunk_boundaries(
        temp_file,
        "python",
        show_stats=True,
        show_side_by_side=False,
    )

    # Clean up
    import os

    os.unlink(temp_file)


def example_interactive_exploration():
    """Example: Interactive AST exploration."""
    print("\n=== Interactive AST Exploration ===")

    # Sample code

    print("Starting interactive AST explorer...")
    print("Try commands like: info, tree, child 0, find if_statement, help")

    # This would start the interactive explorer
    # explore_ast(code, "python")
    print("(Interactive explorer would start here)")


def example_query_patterns():
    """Example: Common query patterns."""
    print("\n=== Common Query Patterns ===")

    queries = {
        "Function calls": "(call expression: (identifier) @func_call)",
        "Class methods": """
        (class_definition
          body: (block
            (function_definition
              name: (identifier) @method
            )
          )
        )
        """,
        "Imports": """
        [
          (import_statement)
          (import_from_statement)
        ] @import
        """,
        "String literals": "(string) @string",
        "Comments": "(comment) @comment",
        "Decorators": """
        (decorated_definition
          (decorator
            (identifier) @decorator_name
          )
        )
        """,
    }

    # Sample code to test queries
    code = '''
import os
from typing import List

@dataclass
class Point:
    x: int
    y: int

    def distance(self, other):
        """Calculate distance to another point."""
        # Use Pythagorean theorem
        return ((self.x - other.x)**2 + (self.y - other.y)**2)**0.5

print("Hello, world!")
'''

    debugger = QueryDebugger("python")

    for name, query in queries.items():
        print(f"\n{name}:")
        print(f"Query: {query.strip()}")
        try:
            matches = debugger.debug_query(
                query,
                code,
                show_ast=False,
                show_captures=True,
                highlight_matches=False,
            )
            print(f"Found {len(matches)} matches")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    # Run examples
    example_ast_visualization()
    example_query_debugging()
    example_chunk_analysis()
    example_query_patterns()
    example_interactive_exploration()

    print("\n\nFor more interactive debugging, try:")
    print("  python -m cli.main debug repl")
    print("  python -m cli.main debug ast examples/example.py")
    print("  python -m cli.main debug chunks examples/example.py --visualize")
