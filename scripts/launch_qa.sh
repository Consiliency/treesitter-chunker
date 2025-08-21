#!/bin/bash
# Quality Assurance and Final Review Launcher

echo "🧪 Tree-sitter Chunker - Quality Assurance Suite"
echo "================================================"
echo ""
echo "Choose an option:"
echo "1) Quality Check (comprehensive analysis)"
echo "2) Example Validation (documentation examples)"
echo "3) Final Review (deployment readiness)"
echo "4) Run All (complete QA suite)"
echo "5) Exit"
echo ""
read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo "🔍 Running quality check..."
        python3 scripts/quality_check.py
        ;;
    2)
        echo "📚 Running example validation..."
        python3 scripts/validate_examples.py
        ;;
    3)
        echo "🚀 Running final review..."
        python3 scripts/final_review.py
        ;;
    4)
        echo "🚀 Running complete QA suite..."
        echo ""
        echo "Step 1: Quality Check"
        python3 scripts/quality_check.py
        echo ""
        echo "Step 2: Example Validation"
        python3 scripts/validate_examples.py
        echo ""
        echo "Step 3: Final Review"
        python3 scripts/final_review.py
        ;;
    5)
        echo "👋 Goodbye!"
        exit 0
        ;;
    *)
        echo "❌ Invalid choice. Please run the script again."
        exit 1
        ;;
esac
