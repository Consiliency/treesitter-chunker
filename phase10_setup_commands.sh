#!/bin/bash

# Phase 10 Worktree Setup and Claude Agent Launch Commands
# Created: 2025-01-22

echo "Phase 10 Worktree Setup Commands"
echo "================================"
echo ""
echo "Run these commands in separate terminals to set up each worktree:"
echo ""

# Smart Context Worktree
echo "# Terminal 1: Smart Context Selection"
echo "cd /home/jenner/code/treesitter-chunker-worktrees/phase10-smart-context"
echo "uv venv && source .venv/bin/activate"
echo 'uv pip install -e ".[dev]"'
echo "uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git"
echo "python scripts/fetch_grammars.py"
echo "python scripts/build_lib.py"
echo 'claude "Implement the SmartContextProvider interface from chunker/interfaces/smart_context.py. This should provide semantic, dependency, usage, and structural context extraction for code chunks. The implementation should go in chunker/smart_context.py and follow the patterns established in Phase 9 features. Include comprehensive tests in tests/test_smart_context.py. The goal is to provide optimal context for LLM processing by intelligently selecting related code chunks."'
echo ""

# Query Advanced Worktree
echo "# Terminal 2: Advanced Query System"
echo "cd /home/jenner/code/treesitter-chunker-worktrees/phase10-query-advanced"
echo "uv venv && source .venv/bin/activate"
echo 'uv pip install -e ".[dev]"'
echo "uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git"
echo "python scripts/fetch_grammars.py"
echo "python scripts/build_lib.py"
echo 'claude "Implement the ChunkQueryAdvanced interface from chunker/interfaces/query_advanced.py. This should enable natural language queries, semantic search, and similarity matching for code chunks. The implementation should go in chunker/query_advanced.py with a QueryIndexAdvanced implementation for efficient searching. Include tests in tests/test_query_advanced.py. The goal is sophisticated code search and retrieval capabilities."'
echo ""

# Optimization Worktree
echo "# Terminal 3: Chunk Optimization"
echo "cd /home/jenner/code/treesitter-chunker-worktrees/phase10-optimization"
echo "uv venv && source .venv/bin/activate"
echo 'uv pip install -e ".[dev]"'
echo "uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git"
echo "python scripts/fetch_grammars.py"
echo "python scripts/build_lib.py"
echo 'claude "Implement the ChunkOptimizer interface from chunker/interfaces/optimization.py. This should provide LLM-specific optimization including chunk merging, splitting, and rebalancing based on token limits and model constraints. The implementation should go in chunker/optimization.py. Include boundary analysis and optimization strategies. Add tests in tests/test_optimization.py. The goal is to optimize chunks for specific model constraints and use cases."'
echo ""

# Multi-Language Worktree
echo "# Terminal 4: Multi-Language Support"
echo "cd /home/jenner/code/treesitter-chunker-worktrees/phase10-multi-language"
echo "uv venv && source .venv/bin/activate"
echo 'uv pip install -e ".[dev]"'
echo "uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git"
echo "python scripts/fetch_grammars.py"
echo "python scripts/build_lib.py"
echo 'claude "Implement the MultiLanguageProcessor interface from chunker/interfaces/multi_language.py. This should handle mixed-language files, cross-language references, and embedded code extraction. The implementation should go in chunker/multi_language.py with LanguageDetector and ProjectAnalyzer implementations. Include tests in tests/test_multi_language.py. The goal is to handle polyglot codebases and modern web frameworks with embedded languages."'
echo ""

# Incremental Processing Worktree
echo "# Terminal 5: Incremental Processing"
echo "cd /home/jenner/code/treesitter-chunker-worktrees/phase10-incremental"
echo "uv venv && source .venv/bin/activate"
echo 'uv pip install -e ".[dev]"'
echo "uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git"
echo "python scripts/fetch_grammars.py"
echo "python scripts/build_lib.py"
echo 'claude "Implement the IncrementalProcessor interface from chunker/interfaces/incremental.py. This should provide change detection, diff computation, and cache management for efficient updates. The implementation should go in chunker/incremental.py with ChunkCache and ChangeDetector implementations. Include tests in tests/test_incremental.py. The goal is to efficiently process only changed portions of large codebases."'
echo ""

echo "Additional Notes:"
echo "================="
echo "1. Each implementation should follow the patterns from Phase 9 features"
echo "2. Export the main classes in chunker/__init__.py"
echo "3. Update CLI if needed to support new features"
echo "4. Run tests frequently: python -m pytest tests/test_[feature].py -xvs"
echo "5. Check interface compatibility: python -m pytest tests/test_phase10_interface_compatibility.py"
echo "6. When ready to merge, rebase on main first: git fetch origin && git rebase origin/main"