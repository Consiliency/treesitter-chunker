#!/bin/bash
# Examples of using the Tree-sitter Chunker API with curl

API_URL="http://localhost:8000"

# Disposable scratch under the inherited TMPDIR, removed on exit
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

echo "=== Health Check ==="
curl -s "$API_URL/health" | jq .

echo -e "\n=== List Languages ==="
curl -s "$API_URL/languages" | jq .

echo -e "\n=== Chunk Python Code ==="
# Create a JSON payload with Python code
cat > "$SCRATCH/chunk_request.json" << 'EOF'
{
  "content": "def hello(name):\n    \"\"\"Say hello to someone.\"\"\"\n    print(f'Hello, {name}!')\n\nclass Greeter:\n    def __init__(self, name):\n        self.name = name\n    \n    def greet(self):\n        hello(self.name)",
  "language": "python",
  "min_chunk_size": 3
}
EOF

curl -s -X POST "$API_URL/chunk/text" \
  -H "Content-Type: application/json" \
  -d @"$SCRATCH/chunk_request.json" | jq .

echo -e "\n=== Chunk File ==="
# Create a sample file
cat > "$SCRATCH/example.py" << 'EOF'
def calculate_sum(numbers):
    """Calculate the sum of a list of numbers."""
    total = 0
    for num in numbers:
        total += num
    return total

def calculate_average(numbers):
    """Calculate the average of a list of numbers."""
    if not numbers:
        return 0
    return calculate_sum(numbers) / len(numbers)
EOF

# Request to chunk the file
curl -s -X POST "$API_URL/chunk/file" \
  -H "Content-Type: application/json" \
  -d "{
    \"file_path\": \"$SCRATCH/example.py\",
    \"language\": \"python\"
  }" | jq .
