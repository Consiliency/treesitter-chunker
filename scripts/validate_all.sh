#!/bin/bash
# Comprehensive validation launcher

echo "🧪 Tree-sitter Chunker Validation Suite"
echo "======================================="
echo ""
echo "Choose validation level:"
echo "1) Quick validation (basic functionality)"
echo "2) Example validation (documentation examples)"
echo "3) Full test suite (all tests + validation)"
echo "4) Exit"
echo ""
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo "⚡ Running quick validation..."
        python3 scripts/quick_validate.py
        ;;
    2)
        echo "📚 Running example validation..."
        python3 scripts/validate_examples.py
        ;;
    3)
        echo "🚀 Running full test suite..."
        python3 scripts/run_all_tests.py
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
