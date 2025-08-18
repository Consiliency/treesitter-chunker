# Grammar Management Guide

This guide covers the smart grammar management system for tree-sitter-chunker, which provides intelligent error handling, user guidance, and tools for managing tree-sitter grammar libraries.

## Overview

The grammar management system consists of several components:

- **Smart Grammar Manager**: Core management with intelligent error handling
- **User Grammar Tools**: User-friendly tools for grammar operations
- **CLI Commands**: Command-line interface for grammar management
- **Enhanced Error Handling**: Comprehensive user guidance and troubleshooting

## Features

### 🧠 Smart Error Handling
- **Automatic diagnosis** of grammar issues
- **Context-aware recommendations** based on error type
- **Recovery plans** with step-by-step solutions
- **Compatibility checking** for system requirements

### 🛠️ User Grammar Management
- **Install** grammars from Git repositories
- **Update** existing grammars to latest versions
- **Remove** grammars and clean up sources
- **Validate** grammar health and integrity

### 📊 Health Monitoring
- **Real-time status** of all installed grammars
- **Compatibility scoring** for system requirements
- **Issue tracking** with actionable recommendations
- **System health reports** for troubleshooting

## Quick Start

### Check Current Grammar Status

```bash
# List all installed grammars
python -m chunker.cli grammar list

# Get detailed info about a specific grammar
python -m chunker.cli grammar info python

# Check system health
python -m chunker.cli grammar health
```

### Install a New Grammar

```bash
# Install Python grammar
python -m chunker.cli grammar install python https://github.com/tree-sitter/tree-sitter-python.git

# Install with specific branch
python -m chunker.cli grammar install rust https://github.com/tree-sitter/tree-sitter-rust.git --branch main
```

### Manage Existing Grammars

```bash
# Update a grammar to latest version
python -m chunker.cli grammar update python

# Remove a grammar
python -m chunker.cli grammar remove python

# Diagnose issues with a grammar
python -m chunker.cli grammar diagnose python
```

## CLI Commands Reference

### `grammar list`
Lists all installed grammars with their health status.

**Output:**
```
📋 Grammar Status Summary:
   Total grammars: 6
   Healthy: 5
   Problematic: 1

🔍 Individual Grammar Status:
   ✅ python: healthy
   ✅ rust: healthy
   ✅ go: healthy
   ✅ c: healthy
   ✅ cpp: healthy
   ⚠️ java: missing
      - Grammar library /path/to/java.so not found
      💡 Check if grammar source exists in grammars/ directory
```

### `grammar info <language>`
Provides detailed information about a specific grammar.

**Output:**
```
📊 Grammar Information: python
==================================================
Status: ✅ healthy

🔧 Compatibility:
   Tree-sitter version: 0.20.8
   System architecture: x86_64
   OS platform: Linux
   Compilation date: 2024-01-15T10:30:00
   Compatibility score: 100.0%

📁 Source Repository:
   URL: https://github.com/tree-sitter/tree-sitter-python.git
   Latest commit: abc1234 Update Python 3.12 support
   Directory: /path/to/grammars/tree-sitter-python
   Has package.json: True
   Has grammar.js: True
```

### `grammar install <language> <repo_url> [--branch <branch>]`
Installs a grammar from a Git repository.

**Example:**
```bash
python -m chunker.cli grammar install typescript https://github.com/tree-sitter/tree-sitter-typescript.git
```

**Output:**
```
🚀 Installing grammar for typescript...
   Repository: https://github.com/tree-sitter/tree-sitter-typescript.git
   Branch: main

📋 Installation Result:
   Status: success

✅ Steps completed:
   - Cloned repository
   - Installed npm dependencies
   - Generated grammar
   - Copied typescript.so to build directory
   - Validated grammar installation

🎉 Successfully installed typescript grammar!
```

### `grammar update <language>`
Updates an existing grammar to the latest version.

**Example:**
```bash
python -m chunker.cli grammar update python
```

**Output:**
```
🔄 Updating grammar for python...

📋 Update Result:
   Status: success

✅ Steps completed:
   - Fetched latest changes
   - Updated to latest version
   - Updated dependencies
   - Regenerated grammar
   - Updated compiled grammar library

🎉 Successfully updated python grammar!
```

### `grammar remove <language>`
Removes a grammar and its source code.

**Example:**
```bash
python -m chunker.cli grammar remove python
```

**Output:**
```
🗑️ Removing grammar for python...
Are you sure you want to remove python? (y/N): y

📋 Removal Result:
   Status: success

✅ Steps completed:
   - Removed compiled grammar library
   - Removed grammar source directory

🎉 Successfully removed python grammar!
```

### `grammar diagnose <language>`
Diagnoses issues with a specific grammar.

**Example:**
```bash
python -m chunker.cli grammar diagnose java
```

**Output:**
```
🔍 Diagnosing grammar for java...

📊 Grammar Information: java
==================================================
Status: ⚠️ missing

❌ Issues:
   - Grammar library /path/to/java.so not found
   - Grammar source repository not found: /path/to/grammars/tree-sitter-java

💡 Recommendations:
   - Check if grammar source exists in grammars/ directory
   - Compile the grammar using the appropriate build script
   - Verify the grammar repository was cloned correctly
   - Clone the grammar repository to grammars/ directory

🛠️ Recovery Plan:
   Difficulty: easy
   Estimated time: 5-15 minutes
   Steps:
      1. Clone grammar repository: git clone <repo_url> grammars/tree-sitter-java
      2. Navigate to grammar directory: cd grammars/tree-sitter-java
      3. Install dependencies: npm install (if package.json exists)
      4. Generate grammar: tree-sitter generate
      5. Copy .so file to build directory: cp *.so ../../chunker/data/grammars/build/
```

### `grammar health`
Checks overall system health for grammar management.

**Output:**
```
🏥 Checking system health for grammar management...

📋 System Health Report:
==================================================

🔧 System Requirements:
   ✅ Tree Sitter Cli: Available
   ✅ Node Npm: Available
   ✅ Git: Available
   ✅ Compiler: Available
   ✅ Python Deps: Available

📁 Directory Permissions:
   ✅ build directory: readable, writable, executable
   ✅ grammars directory: readable, writable, executable

📊 Overall Health Score: 100.0%
🎉 System is fully ready for grammar management!
```

### `grammar validate`
Validates all installed grammars.

**Output:**
```
🔍 Validating all installed grammars...

📋 Validation Results:
   Total grammars: 6
   Healthy: 5
   Problematic: 1

⚠️ Problematic Grammars:
   - java: missing
     Issue: Grammar library /path/to/java.so not found
     Recommendation: Check if grammar source exists in grammars/ directory
     Recommendation: Compile the grammar using the appropriate build script
     Recommendation: Verify the grammar repository was cloned correctly
```

## Error Handling

### Common Issues and Solutions

#### Missing Grammar Library
**Symptoms:** `LanguageNotFoundError` with "missing" status

**Solutions:**
1. Check if grammar source exists in `grammars/` directory
2. Clone the grammar repository: `git clone <repo_url> grammars/tree-sitter-<language>`
3. Install dependencies: `npm install` (if package.json exists)
4. Generate grammar: `tree-sitter generate`
5. Copy .so file to build directory

#### Corrupted Grammar Library
**Symptoms:** `LanguageLoadError` with "corrupted" status

**Solutions:**
1. Remove corrupted .so file
2. Clean grammar source: `git clean -fd`
3. Pull latest changes: `git pull origin main`
4. Regenerate grammar: `tree-sitter generate`
5. Copy new .so file to build directory

#### Incompatible Grammar
**Symptoms:** `LanguageLoadError` with "incompatible" status

**Solutions:**
1. Check system compatibility requirements
2. Verify tree-sitter version compatibility
3. Recompile grammar on current system
4. Check for architecture-specific issues
5. Consider using a different grammar version

### Recovery Plans

The system automatically generates recovery plans for problematic grammars:

```
🛠️ Recovery Plan:
   Difficulty: easy
   Estimated time: 5-15 minutes
   Steps:
      1. Clone grammar repository: git clone <repo_url> grammars/tree-sitter-<language>
      2. Navigate to grammar directory: cd grammars/tree-sitter-<language>
      3. Install dependencies: npm install (if package.json exists)
      4. Generate grammar: tree-sitter generate
      5. Copy .so file to build directory: cp *.so ../../chunker/data/grammars/build/
```

## System Requirements

### Required Tools
- **tree-sitter CLI**: `npm install -g tree-sitter-cli`
- **Node.js and npm**: For grammar compilation
- **Git**: For managing grammar repositories
- **C Compiler**: gcc or clang for building grammars
- **Python tree-sitter**: `pip install tree-sitter`

### Directory Structure
```
project_root/
├── chunker/
│   └── data/
│       └── grammars/
│           └── build/          # Compiled .so files
└── grammars/                   # Grammar source repositories
    ├── tree-sitter-python/
    ├── tree-sitter-rust/
    └── ...
```

## Best Practices

### Grammar Installation
1. **Use official repositories** when possible
2. **Check compatibility** with your system
3. **Keep grammars updated** for latest language support
4. **Validate installations** after completion

### Troubleshooting
1. **Start with system health check**: `grammar health`
2. **Diagnose specific issues**: `grammar diagnose <language>`
3. **Follow recovery plans** step by step
4. **Check system requirements** if issues persist

### Maintenance
1. **Regular updates** of installed grammars
2. **Monitor grammar health** with `grammar list`
3. **Clean up unused grammars** to save space
4. **Backup important grammars** before major changes

## Advanced Usage

### Programmatic Access

```python
from chunker._internal.user_grammar_tools import UserGrammarTools
from pathlib import Path

# Initialize tools
tools = UserGrammarTools(
    build_dir=Path("chunker/data/grammars/build"),
    grammars_dir=Path("grammars")
)

# Install a grammar
result = tools.install_grammar(
    "kotlin",
    "https://github.com/fwcd/tree-sitter-kotlin.git"
)

# Check grammar health
health = tools.manager.diagnose_grammar_issues("kotlin")
print(f"Status: {health.status}")
```

### Custom Grammar Sources

```python
# Install from custom repository
result = tools.install_grammar(
    "custom-lang",
    "https://github.com/username/tree-sitter-custom-lang.git",
    branch="develop"
)
```

### Batch Operations

```python
# Validate all grammars
all_health = tools.manager.validate_all_grammars()

# Check system health
system_health = tools.check_system_health()

# Generate recovery plans for all problematic grammars
for language, health in all_health.items():
    if health.status != "healthy":
        plan = tools.manager.generate_recovery_plan(language)
        print(f"Recovery plan for {language}: {plan['difficulty']}")
```

## Troubleshooting Guide

### Installation Failures

**Problem:** `npm install` fails
**Solution:** Check Node.js version and npm permissions

**Problem:** `tree-sitter generate` fails
**Solution:** Verify grammar.js file exists and syntax is correct

**Problem:** Permission denied errors
**Solution:** Check directory permissions and user access

### Runtime Issues

**Problem:** Grammar loads but parsing fails
**Solution:** Check grammar version compatibility with your code

**Problem:** Symbol not found errors
**Solution:** Recompile grammar on current system architecture

**Problem:** Memory errors during parsing
**Solution:** Check grammar complexity and system resources

### System Compatibility

**Problem:** Architecture mismatch
**Solution:** Recompile grammar on target architecture

**Problem:** OS compatibility issues
**Solution:** Use grammar versions compatible with your OS

**Problem:** Tree-sitter version mismatch
**Solution:** Update tree-sitter or use compatible grammar version

## Support and Resources

### Getting Help
1. **Check system health**: `grammar health`
2. **Review error messages** for specific guidance
3. **Follow recovery plans** provided by the system
4. **Check grammar repository** for known issues

### Useful Commands
- `grammar list` - Quick status overview
- `grammar health` - System requirements check
- `grammar diagnose <language>` - Detailed issue analysis
- `grammar validate` - Comprehensive validation

### Additional Resources
- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [Grammar Development Guide](https://tree-sitter.github.io/tree-sitter/creating-parsers)
- [Community Grammars](https://github.com/topics/tree-sitter-grammar)

## Conclusion

The smart grammar management system provides comprehensive tools for managing tree-sitter grammars with intelligent error handling and user guidance. By following the best practices and using the provided tools, you can maintain a healthy and up-to-date grammar ecosystem for optimal code parsing performance.

For additional support or feature requests, please refer to the project documentation or create an issue in the project repository.
