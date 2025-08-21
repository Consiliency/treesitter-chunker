#!/bin/bash
# Quick documentation server launcher

echo "🌐 Tree-sitter Chunker Documentation Servers"
echo "============================================="
echo ""
echo "Choose an option:"
echo "1) MkDocs server (Material theme) - http://127.0.0.1:8000"
echo "2) Sphinx server (Read the Docs theme) - http://127.0.0.1:8001"
echo "3) Both servers simultaneously"
echo "4) Exit"
echo ""
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo "🚀 Starting MkDocs server..."
        python3 scripts/serve_mkdocs.py
        ;;
    2)
        echo "🚀 Starting Sphinx server..."
        python3 scripts/serve_sphinx.py
        ;;
    3)
        echo "🚀 Starting both servers..."
        python3 scripts/serve_all.py
        ;;
    4)
        echo "👋 Goodbye!"
        exit 0
        ;;
    *)
        echo "❌ Invalid choice. Please run the script again."
        exit 1
        ;;
esac
