#!/bin/bash

# Phase 12: Graph & Database Export - Worktree Setup
# This script creates worktrees for parallel development of Phase 12 components

echo "=== Phase 12: Graph & Database Export - Worktree Setup ==="
echo "Creating worktrees for parallel development..."

# Ensure we're in the main branch with clean status
git checkout main
git status

# Create worktrees directory if it doesn't exist
mkdir -p worktrees

# Create worktrees for each Phase 12 component
echo -e "\n--- Creating GraphML Export worktree ---"
git worktree add ./worktrees/graphml-export -b phase12-graphml-export

echo -e "\n--- Creating Neo4j Export worktree ---"
git worktree add ./worktrees/neo4j-export -b phase12-neo4j-export

echo -e "\n--- Creating DOT Export worktree ---"
git worktree add ./worktrees/dot-export -b phase12-dot-export

echo -e "\n--- Creating SQLite Export worktree ---"
git worktree add ./worktrees/sqlite-export -b phase12-sqlite-export

echo -e "\n--- Creating PostgreSQL Export worktree ---"
git worktree add ./worktrees/postgres-export -b phase12-postgres-export

echo -e "\n=== Worktree Setup Complete ==="
echo "Listing all worktrees:"
git worktree list

echo -e "\n=== Next Steps ==="
echo "1. Each worktree has the interface contracts from main branch"
echo "2. Integration tests are in tests/test_phase12_integration.py"
echo "3. Launch sub-agents using the Task tool for each worktree"
echo "4. Each team should implement their specific exporter"
echo "5. All integration tests should pass when implementations are complete"