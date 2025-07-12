#!/bin/bash
# Launch Claude Code sessions for parallel development

echo "=== Tree-sitter Chunker Parallel Development ==="
echo ""
echo "Git worktrees have been created. You can now launch Claude Code sessions in parallel."
echo ""
echo "CRITICAL PATH - Start this first:"
echo "  cd ../treesitter-chunker-worktrees/lang-config"
echo '  claude "Implement Phase 2.1 Language Configuration Framework from ROADMAP.md"'
echo ""
echo "IMMEDIATE STARTS - Can work in parallel:"
echo "  1. Plugin Architecture:"
echo "     cd ../treesitter-chunker-worktrees/plugin-arch"
echo '     claude "Implement Phase 1.2 Plugin Architecture from ROADMAP.md"'
echo ""
echo "  2. CLI Enhancements:"
echo "     cd ../treesitter-chunker-worktrees/cli-enhance"
echo '     claude "Implement Phase 5.1 Advanced CLI Features and 5.3 User Experience from ROADMAP.md"'
echo ""
echo "  3. JSON Export:"
echo "     cd ../treesitter-chunker-worktrees/export-json"
echo '     claude "Implement JSON/JSONL export format from Phase 5.2 in ROADMAP.md"'
echo ""
echo "  4. Performance:"
echo "     cd ../treesitter-chunker-worktrees/performance"
echo '     claude "Implement Phase 4.1 Efficient Processing and 4.2 Caching from ROADMAP.md"'
echo ""
echo "  5. Documentation:"
echo "     cd ../treesitter-chunker-worktrees/docs"
echo '     claude "Create comprehensive documentation per Phase 6.2 in ROADMAP.md"'
echo ""
echo "AFTER LANG-CONFIG MERGES - Language modules:"
echo "  - Python: cd ../treesitter-chunker-worktrees/lang-python"
echo "  - Rust: cd ../treesitter-chunker-worktrees/lang-rust"
echo "  - JavaScript: cd ../treesitter-chunker-worktrees/lang-javascript"
echo "  - C: cd ../treesitter-chunker-worktrees/lang-c"
echo "  - C++: cd ../treesitter-chunker-worktrees/lang-cpp"
echo ""
echo "ADDITIONAL EXPORT FORMATS - Can start anytime:"
echo "  - Parquet: cd ../treesitter-chunker-worktrees/export-parquet"
echo "  - Graph: cd ../treesitter-chunker-worktrees/export-graph"
echo "  - Database: cd ../treesitter-chunker-worktrees/export-db"
echo ""
echo "Remember to run environment setup in each worktree before starting development!"