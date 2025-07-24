"""Demonstration of chunk hierarchy features."""

from chunker import ChunkHierarchyBuilder, HierarchyNavigator
from chunker.chunker import chunk_text


def print_hierarchy(hierarchy, navigator, indent_size=2):
    """Print hierarchy in tree format."""

    def print_node(chunk_id, level=0):
        chunk = hierarchy.chunk_map[chunk_id]
        indent = " " * (level * indent_size)
        print(
            f"{indent}├─ {chunk.node_type}: {chunk.content.split()[0][:30]}... (line {chunk.start_line})",
        )

        # Print children
        children = navigator.get_children(chunk_id, hierarchy)
        for child in children:
            print_node(child.chunk_id, level + 1)

    # Print from roots
    for root_id in hierarchy.root_chunks:
        print_node(root_id)


def main():
    # Sample Python code with nested structure
    python_code = '''
class DataProcessor:
    """Process various types of data."""
    
    def __init__(self, config):
        self.config = config
        self.cache = {}
    
    def process_text(self, text):
        """Process text data."""
        # Clean the text
        cleaned = self._clean_text(text)
        
        # Analyze
        results = self._analyze(cleaned)
        
        return results
    
    def _clean_text(self, text):
        """Internal method to clean text."""
        return text.strip().lower()
    
    def _analyze(self, text):
        """Analyze the cleaned text."""
        return {"length": len(text), "words": text.split()}
    
    class NestedProcessor:
        """A nested processor class."""
        
        def nested_method(self):
            """Method in nested class."""
            pass

def helper_function(data):
    """A standalone helper function."""
    processor = DataProcessor({})
    return processor.process_text(data)

async def async_processor(items):
    """Process items asynchronously."""
    results = []
    for item in items:
        result = await process_item(item)
        results.append(result)
    return results
'''

    # Chunk the code
    print("Chunking Python code...")
    chunks = chunk_text(python_code, "python", "demo.py")
    print(f"Found {len(chunks)} chunks\n")

    # Build hierarchy
    builder = ChunkHierarchyBuilder()
    hierarchy = builder.build_hierarchy(chunks)

    # Create navigator
    navigator = HierarchyNavigator()

    print("=== Chunk Hierarchy ===")
    print_hierarchy(hierarchy, navigator)

    print("\n=== Hierarchy Analysis ===")

    # Find all classes
    classes = navigator.find_chunks_by_type("class_definition", hierarchy)
    print(f"\nClasses found: {len(classes)}")
    for cls in classes:
        print(f"  - {cls.content.split()[1]} at line {cls.start_line}")

        # Get methods in this class
        methods = navigator.get_children(cls.chunk_id, hierarchy)
        print(f"    Methods: {len(methods)}")
        for method in methods:
            print(
                f"      - {method.content.split()[1].rstrip('('):} at line {method.start_line}",
            )

    # Depth analysis
    print("\n=== Depth Analysis ===")
    for depth in range(3):
        chunks_at_depth = navigator.filter_by_depth(hierarchy, depth, depth)
        if chunks_at_depth:
            print(f"Depth {depth}: {len(chunks_at_depth)} chunks")
            for chunk in chunks_at_depth:
                print(f"  - {chunk.node_type}: line {chunk.start_line}")

    # Find specific chunk and explore relationships
    print("\n=== Relationship Example ===")
    # Find the process_text method
    process_text = next(
        (
            c
            for c in chunks
            if "process_text" in c.content and c.node_type == "function_definition"
        ),
        None,
    )

    if process_text:
        print(f"Exploring: {process_text.content.split('(')[0]}")

        # Get ancestors
        ancestors = navigator.get_ancestors(process_text.chunk_id, hierarchy)
        print(f"  Ancestors: {[a.node_type for a in ancestors]}")

        # Get siblings
        siblings = navigator.get_siblings(process_text.chunk_id, hierarchy)
        print(f"  Siblings: {len(siblings)}")
        for sibling in siblings:
            print(f"    - {sibling.content.split()[1].rstrip('('):}")

    # Extract subtree
    print("\n=== Subtree Extraction ===")
    if classes:
        main_class = classes[0]
        subtree = navigator.get_subtree(main_class.chunk_id, hierarchy)
        print(
            f"Subtree rooted at '{main_class.content.split()[1]}' contains {len(subtree.chunk_map)} chunks",
        )

        # Common ancestor example
        if len(chunks) >= 2:
            chunk1, chunk2 = chunks[0], chunks[-1]
            common = builder.find_common_ancestor(chunk1, chunk2, hierarchy)
            if common:
                common_chunk = hierarchy.chunk_map[common]
                print(
                    f"\nCommon ancestor of first and last chunk: {common_chunk.node_type} at line {common_chunk.start_line}",
                )
            else:
                print("\nNo common ancestor found between first and last chunk")


if __name__ == "__main__":
    main()
