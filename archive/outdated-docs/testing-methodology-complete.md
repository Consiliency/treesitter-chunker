# 🧪 Treesitter-Chunker Testing Methodology

## Overview
This document outlines the comprehensive testing methodology used to validate the treesitter-chunker's production readiness across multiple programming languages and features.

## Testing Environment Setup

### Prerequisites
- Python 3.8-3.12
- UV package manager
- Docker (for containerized testing)
- 8GB+ RAM for performance tests
- All language grammars compiled

### CLI Access
```bash
python -m cli.main --help
```

### Testing Framework
```bash
python -m pytest -xvs
python -m pytest --cov=chunker --cov-report=html
```

## 1. Language Coverage Testing

Test each supported programming language with real-world repositories:

| Language | Repository | Test File | Expected Chunks |
|----------|------------|-----------|-----------------|
| Python | pallets/click | src/click/core.py | 176+ chunks |
| JavaScript | lodash/lodash | lodash.js | 1,865+ chunks |
| Go | gin-gonic/gin | gin.go | 67+ chunks |
| Rust | serde-rs/serde | src/de/size_hint.rs | 3+ chunks |
| C++ | google/googletest | src/gtest_main.cc | 2+ chunks |
| Java | google/guava | TraverserRewrite.java | 19+ chunks |
| Ruby | ruby/ruby | array.rb | 12+ chunks |
| C | git/git | apply.c | 45+ chunks |
| TypeScript | microsoft/TypeScript | src/compiler/parser.ts | 230+ chunks |
| TSX | facebook/react | packages/react/src/React.tsx | 15+ chunks |
| PHP | laravel/framework | src/Illuminate/Foundation/Application.php | 89+ chunks |
| Kotlin | JetBrains/kotlin | compiler/frontend/src/org/jetbrains/kotlin/resolve/BindingContext.kt | 34+ chunks |
| C# | dotnet/roslyn | src/Compilers/CSharp/Portable/Parser/LanguageParser.cs | 156+ chunks |
| Swift | apple/swift | stdlib/public/core/Array.swift | 78+ chunks |

## 2. Feature Testing Matrix

### A. Single File Chunking
```bash
python -m cli.main chunk <file> --lang <language>
```

### B. AST Visualization
```bash
python -m cli.main debug ast <file> --lang <language> --format tree
python -m cli.main debug ast <file> --lang <language> --format dot --output ast.svg
```

### C. Chunk Analysis
```bash
# Test chunking decisions and coverage
python -m cli.main debug chunks <file> --lang <language>

# Expected: Detailed analysis with chunked vs non-chunked nodes
```

### D. Query Debugging
```bash
python -m cli.main debug query <file> --lang <language> --query "(function_definition) @func"
```

### E. Batch Processing
```bash
# Test multiple files
python -m cli.main chunk *.py --lang python --output results.jsonl --format jsonl
```

### F. Repository Processing
```bash
# Test full repository analysis
python -m cli.main repo process <repo> --file-pattern "src/**/*.py" --output results.jsonl

# Expected: Comprehensive repository analysis
```

## 3. Security Testing

### A. Input Validation
```bash
# Test malicious file paths
python -m cli.main chunk "../../../../../etc/passwd" --lang python  # Should fail safely
python -m cli.main chunk "file://malicious.py" --lang python  # Should fail safely
python -m cli.main chunk "; rm -rf /" --lang python  # Should fail safely
```

### B. Resource Limits
```python
# Test memory limits
python -c "
from chunker import chunk_file
import resource
# Set 1GB memory limit
resource.setrlimit(resource.RLIMIT_AS, (1024*1024*1024, 1024*1024*1024))
try:
    chunks = chunk_file('massive_file.py', 'python')
except MemoryError:
    print('Memory limit enforced correctly')
"
```

### C. Configuration Injection
```bash
# Test config file security
echo 'malicious_config = "__import__(\"os\").system(\"echo pwned\")"' > bad_config.py
python -m cli.main chunk test.py --config bad_config.py  # Should not execute
```

### D. Dependency Scanning
```bash
# Check for known vulnerabilities
pip-audit
safety check
```

## 4. Performance & Scalability Testing

### A. Large File Handling
```python
# Test with progressively larger files
for size in [1, 10, 100, 1000]:  # MB
    create_test_file(f"test_{size}mb.py", size)
    start = time.time()
    chunks = chunk_file(f"test_{size}mb.py", "python")
    print(f"{size}MB: {time.time()-start:.2f}s, {len(chunks)} chunks")
```

### B. Concurrent Processing
```bash
# Test parallel processing limits
python -m cli.main chunk **/*.py --lang python --workers 1 --output single.jsonl
python -m cli.main chunk **/*.py --lang python --workers 4 --output parallel4.jsonl
python -m cli.main chunk **/*.py --lang python --workers 16 --output parallel16.jsonl

# Compare performance and correctness
```

### C. Memory Usage Profiling
```bash
# Profile memory usage
mprof run python -m cli.main repo process large_repo/
mprof plot
```

### D. Cache Efficiency
```python
# Test cache hit rates
from chunker.cache import get_cache_stats
chunk_file("test.py", "python")  # First run
stats1 = get_cache_stats()
chunk_file("test.py", "python")  # Cached run
stats2 = get_cache_stats()
assert stats2.hits > stats1.hits
```

## 5. Reliability & Stability Testing

### A. Long-Running Tests
```bash
# 24-hour stability test
python scripts/stability_test.py --duration 86400 --interval 60
```

### B. Error Recovery
```python
# Test graceful degradation
def test_error_recovery():
    # Corrupt AST scenario
    with mock.patch('tree_sitter.Parser.parse', side_effect=Exception):
        chunks = chunk_file("test.py", "python", fallback=True)
        assert len(chunks) > 0  # Should use fallback chunker
```

### C. Thread Safety
```python
# Test concurrent access
import threading
def worker(file_path, results):
    chunks = chunk_file(file_path, "python")
    results.append(len(chunks))

results = []
threads = [threading.Thread(target=worker, args=("test.py", results)) 
           for _ in range(100)]
for t in threads: t.start()
for t in threads: t.join()
assert all(r == results[0] for r in results)  # All results should be identical
```

### D. Memory Leak Detection
```bash
# Run with memory leak detection
valgrind --leak-check=full python -m cli.main chunk large_file.py --lang python
```

## 6. Data Integrity Testing

### A. Chunk Boundary Validation
```python
def test_chunk_boundaries():
    chunks = chunk_file("test.py", "python")
    source = open("test.py").read()
    
    # Verify no overlaps
    for i in range(len(chunks)-1):
        assert chunks[i].end_line < chunks[i+1].start_line
    
    # Verify complete coverage
    reconstructed = "".join(chunk.content for chunk in chunks)
    assert reconstructed == source
```

### B. Unicode Handling
```python
# Test various encodings
test_files = [
    ("utf8_emoji.py", "utf-8", "🚀 def rocket(): pass"),
    ("utf16.py", "utf-16", "def test(): return '测试'"),
    ("latin1.py", "latin-1", "def café(): pass"),
]

for filename, encoding, content in test_files:
    with open(filename, "w", encoding=encoding) as f:
        f.write(content)
    chunks = chunk_file(filename, "python")
    assert len(chunks) > 0
```

### C. Cross-Language Consistency
```bash
# Test mixed-language files
echo '<?php echo "<script>console.log(\"test\")</script>"; ?>' > mixed.php
python -m cli.main chunk mixed.php --lang php
# Should handle embedded JavaScript correctly
```

## 7. Integration Testing

### A. CI/CD Pipeline Integration
```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python: ['3.8', '3.9', '3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python }}
      - run: |
          pip install uv
          uv pip install -e ".[dev]"
          python -m pytest
```

### B. Docker Testing
```dockerfile
# Test in containerized environment
FROM python:3.11-slim
COPY . /app
WORKDIR /app
RUN pip install uv && uv pip install -e .
RUN python -m pytest
```

### C. IDE Plugin Testing
```python
# Test VS Code integration
def test_vscode_integration():
    # Test MCP protocol compatibility
    from chunker.contracts.debug_contract import DebugContract
    debug = DebugContract()
    diagnostics = debug.get_diagnostics("test.py")
    assert isinstance(diagnostics, list)
```

## 8. Operational Testing

### A. Installation Testing
```bash
# Test various installation methods
pip install treesitter-chunker
conda install -c conda-forge treesitter-chunker
brew install treesitter-chunker
docker pull treesitter/chunker:latest
```

### B. Upgrade Testing
```bash
# Test upgrade paths
pip install treesitter-chunker==0.1.0
python -m cli.main chunk test.py --lang python > v1_output.json
pip install --upgrade treesitter-chunker
python -m cli.main chunk test.py --lang python > v2_output.json
# Verify compatibility
```

### C. Configuration Migration
```python
# Test config format migrations
def test_config_migration():
    old_config = {"chunk_size": 100}
    new_config = migrate_config(old_config)
    assert "max_chunk_size" in new_config
```

### D. Monitoring & Telemetry
```python
# Test OpenTelemetry integration
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("chunk_file"):
    chunks = chunk_file("test.py", "python")
    
# Verify span was recorded
```

## Success Criteria

### Functional Requirements
- ✅ All 14 languages produce valid chunks
- ✅ AST parsing succeeds for all languages
- ✅ Chunks are meaningful code units
- ✅ Coverage >90% for typical files
- ✅ Process 1000+ files without errors

### Performance Requirements
- ✅ Process 100 files/second (average size)
- ✅ Handle files up to 10MB
- ✅ Memory usage <2GB for typical workload
- ✅ Cache hit rate >80% for repeated files

### Quality Requirements
- ✅ Chunk size: 3-200 lines (configurable)
- ✅ No data loss or corruption
- ✅ Graceful error handling
- ✅ Clear error messages

### Security Requirements
- ✅ No arbitrary code execution
- ✅ Path traversal protection
- ✅ Resource limit enforcement
- ✅ Safe configuration parsing

## Debugging Methodology

### When Tests Fail
1. Check language grammar installation
2. Verify file encoding
3. Review chunk configuration
4. Enable debug logging
5. Use visualization tools

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| No chunks produced | Verify language grammar, check AST parsing |
| Language not recognized | Run `scripts/fetch_grammars.py` and rebuild |
| Memory errors | Increase limits or use streaming mode |
| Performance degradation | Check cache configuration, use parallel mode |

## Test Automation

### Continuous Testing
```bash
# Run all tests continuously
while true; do
    python -m pytest
    python benchmarks/run_benchmarks.py
    sleep 300  # 5 minutes
done
```

### Regression Testing
```bash
# Compare against baseline
python benchmarks/regression_tracker.py --baseline v1.0.0
```

## Reporting

### Test Coverage Report
```bash
python -m pytest --cov=chunker --cov-report=html
open htmlcov/index.html
```

### Performance Report
```bash
python benchmarks/comprehensive_suite.py --output perf_report.html
```

### Security Report
```bash
bandit -r chunker/
safety check --json > security_report.json
```

## Conclusion

This comprehensive testing methodology ensures the treesitter-chunker is production-ready by validating:

1. **Functionality** across all 14 supported languages
2. **Performance** at scale with real-world codebases
3. **Security** against common vulnerabilities
4. **Reliability** under various conditions
5. **Compatibility** across platforms and integrations

Regular execution of these tests provides confidence in the system's stability and readiness for production deployment.