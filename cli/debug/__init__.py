"""
CLI commands for Tree-sitter debugging tools.
"""

# Import debug commands conditionally to handle missing graphviz
try:
    from . import commands
except ImportError as e:
    if "graphviz" in str(e):
        # Create a stub module when graphviz is missing
        import sys
        from types import ModuleType

        stub = ModuleType("debug_commands")
        stub.app = None  # Will be handled in main.py
        sys.modules[__name__ + ".commands"] = stub
    else:
        raise
