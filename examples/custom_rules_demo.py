"""Demo of custom chunking rules."""

from chunker.parser import get_parser
from chunker.rules import (
    DefaultRuleEngine,
    DocumentationBlockRule,
    HeaderCommentRule,
    MetadataRule,
    RegionMarkerRule,
    SeparatorLineRule,
    TodoCommentRule,
)


def demo_custom_rules():
    """Demonstrate custom rule usage."""
    # Sample code with various patterns
    source = b'''# Copyright 2024 Example Corp
# Licensed under MIT License

"""
Module documentation with structure:

Features:
- Custom chunking rules
- Pattern-based extraction
- Comment block analysis
"""

import os
import sys

# ========================================
# Configuration Section
# ========================================

DEBUG = True

#region Helper Functions
def helper1():
    """Helper function 1."""
    # TODO: Optimize this function
    return 42

def helper2():
    """Helper function 2."""
    # FIXME: Handle edge cases
    return "result"
#endregion

# ========================================
# Main Logic
# ========================================

def main():
    """Main entry point."""
    # TODO: Implement main logic
    print("Starting application...")
    
    result = helper1() + len(helper2())
    return result

if __name__ == "__main__":
    main()
'''

    # Create rule engine
    engine = DefaultRuleEngine()

    # Add various rules with different priorities
    engine.add_rule(MetadataRule(priority=100))
    engine.add_rule(HeaderCommentRule(priority=90))
    engine.add_rule(RegionMarkerRule(priority=80))
    engine.add_rule(DocumentationBlockRule(priority=70))
    engine.add_rule(TodoCommentRule(priority=60))
    engine.add_rule(SeparatorLineRule(priority=40))

    # Parse the source
    parser = get_parser("python")
    tree = parser.parse(source)

    # Apply rules
    chunks = engine.apply_rules(tree, source, "demo.py")

    # Display results
    print(f"Found {len(chunks)} chunks:\n")

    for i, chunk in enumerate(chunks, 1):
        print(f"{i}. {chunk.node_type} (lines {chunk.start_line}-{chunk.end_line})")
        print(
            f"   Priority: {engine._priorities.get(chunk.node_type.split('_')[-1], 'N/A')}",
        )
        if len(chunk.content) > 100:
            print(f"   Content: {chunk.content[:100]}...")
        else:
            print(f"   Content: {chunk.content}")
        print()

    # List all registered rules
    print("\nRegistered Rules:")
    for rule_info in engine.list_rules():
        print(
            f"- {rule_info['name']}: {rule_info['description']} (priority: {rule_info['priority']})",
        )


if __name__ == "__main__":
    demo_custom_rules()
