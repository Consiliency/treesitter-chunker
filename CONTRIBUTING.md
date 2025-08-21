# Contributing to Tree-sitter Chunker

Thank you for your interest in contributing to Tree-sitter Chunker! This document provides guidelines and information for contributors.

## 🎯 How to Contribute

We welcome contributions from the community! Here are the main ways you can help:

### **Types of Contributions**

- **Bug Reports**: Report bugs and issues you encounter
- **Feature Requests**: Suggest new features or improvements
- **Code Contributions**: Submit pull requests with code changes
- **Documentation**: Improve or expand documentation
- **Testing**: Help test the library on different platforms
- **Examples**: Add new examples to the cookbook
- **Language Support**: Add support for new programming languages

## 🚀 Getting Started

### **Prerequisites**

- Python 3.8 or higher
- Git
- Basic familiarity with Python development

### **Development Setup**

1. **Fork the repository**
   ```bash
   # Fork on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/treesitter-chunker.git
   cd treesitter-chunker
   ```

2. **Set up development environment**
   ```bash
   # Create virtual environment
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   
   # Install in development mode
   uv pip install -e ".[dev]"
   
   # Install py-tree-sitter with ABI 15 support
   uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git
   ```

3. **Build language grammars (development only)**
   ```bash
   python scripts/fetch_grammars.py
   python scripts/build_lib.py
   ```

4. **Verify setup**
   ```bash
   # Run tests to ensure everything works
   pytest
   
   # Check code quality
   ruff check .
   black --check .
   mypy chunker/
   ```

## 📝 Development Workflow

### **1. Create a Feature Branch**

```bash
# Create and switch to a new branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-description
```

### **2. Make Your Changes**

- Write clear, readable code
- Follow the coding standards below
- Add tests for new functionality
- Update documentation as needed

### **3. Test Your Changes**

```bash
# Run the full test suite
pytest

# Run specific test files
pytest tests/test_your_feature.py

# Run with coverage
pytest --cov=chunker

# Run linting and type checking
ruff check .
black --check .
mypy chunker/
```

### **4. Commit Your Changes**

```bash
# Stage your changes
git add .

# Commit with a clear message
git commit -m "feat: add new language support for Kotlin

- Add Kotlin language plugin
- Include comprehensive test coverage
- Update documentation with examples"
```

### **5. Push and Create Pull Request**

```bash
# Push your branch
git push origin feature/your-feature-name

# Create pull request on GitHub
```

## 🏗️ Coding Standards

### **Python Code Style**

- **Formatting**: Use [Black](https://black.readthedocs.io/) for code formatting
- **Linting**: Use [Ruff](https://ruff.rs/) for linting
- **Type Hints**: Use type hints for all function parameters and return values
- **Docstrings**: Use Google-style docstrings for all public functions

### **Code Example**

```python
from typing import List, Optional, Dict, Any
from pathlib import Path

def process_files(
    file_paths: List[Path],
    language: str,
    config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Process multiple files and return chunked results.
    
    Args:
        file_paths: List of file paths to process
        language: Programming language for parsing
        config: Optional configuration dictionary
        
    Returns:
        List of chunk dictionaries with metadata
        
    Raises:
        ValueError: If no valid files are provided
        LanguageNotSupportedError: If language is not supported
    """
    if not file_paths:
        raise ValueError("No file paths provided")
    
    # Your implementation here
    pass
```

### **Testing Standards**

- **Coverage**: Maintain 95%+ test coverage
- **Test Types**: Include unit, integration, and edge case tests
- **Test Names**: Use descriptive test names that explain the scenario
- **Fixtures**: Use pytest fixtures for common test data

### **Test Example**

```python
import pytest
from pathlib import Path
from chunker.core import chunk_file

def test_chunk_file_with_python_function():
    """Test chunking a Python file with function definitions."""
    # Arrange
    test_file = Path("test_data/simple_function.py")
    expected_chunk_types = ["function_definition"]
    
    # Act
    chunks = chunk_file(test_file, "python")
    
    # Assert
    assert len(chunks) > 0
    assert all(chunk.node_type in expected_chunk_types for chunk in chunks)
```

## 🔧 Language Plugin Development

### **Adding New Language Support**

1. **Create the plugin file**
   ```python
   # chunker/languages/your_language.py
   from chunker.languages.base import BaseLanguagePlugin
   
   class YourLanguagePlugin(BaseLanguagePlugin):
       name = "your_language"
       extensions = [".ext"]
       
       def get_chunk_types(self) -> List[str]:
           return ["function_definition", "class_definition"]
   ```

2. **Add tests**
   ```python
   # tests/test_languages/test_your_language.py
   def test_your_language_plugin():
       # Test your plugin implementation
       pass
   ```

3. **Update language registry**
   ```python
   # chunker/languages/__init__.py
   from .your_language import YourLanguagePlugin
   
   __all__ = [
       # ... existing plugins
       "YourLanguagePlugin",
   ]
   ```

## 📚 Documentation Standards

### **When to Update Documentation**

- New features or APIs
- Breaking changes
- Bug fixes that affect behavior
- New examples or use cases

### **Documentation Types**

- **API Documentation**: Update docstrings for all public APIs
- **User Guides**: Update relevant user documentation
- **Examples**: Add examples to the cookbook
- **README**: Update if adding major features

## 🐛 Bug Reports

### **Before Reporting a Bug**

1. Check if the issue is already reported
2. Try to reproduce the issue with the latest version
3. Check if it's a configuration or environment issue

### **Bug Report Template**

```markdown
**Bug Description**
Brief description of the issue

**Steps to Reproduce**
1. Step 1
2. Step 2
3. Step 3

**Expected Behavior**
What you expected to happen

**Actual Behavior**
What actually happened

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python Version: [e.g., 3.11]
- Tree-sitter Chunker Version: [e.g., 1.0.9]

**Additional Information**
Any other relevant information
```

## 💡 Feature Requests

### **Feature Request Guidelines**

- **Clear Description**: Explain what you want to achieve
- **Use Case**: Describe the problem it solves
- **Implementation Ideas**: Suggest how it might be implemented
- **Priority**: Indicate how important this is to you

## 🔄 Pull Request Process

### **Before Submitting**

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Documentation is updated
- [ ] No breaking changes (or clearly documented)

### **Pull Request Template**

```markdown
**Description**
Brief description of changes

**Type of Change**
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

**Testing**
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

**Additional Notes**
Any additional information
```

## 🏷️ Release Process

### **Version Bumping**

- **Patch**: Bug fixes and minor improvements
- **Minor**: New features, backward compatible
- **Major**: Breaking changes

### **Release Checklist**

- [ ] All tests pass
- [ ] Documentation is updated
- [ ] Changelog is updated
- [ ] Version is bumped
- [ ] Release notes are prepared

## 🤝 Community Guidelines

### **Code of Conduct**

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Follow the project's coding standards

### **Getting Help**

- **Issues**: [GitHub Issues](https://github.com/Consiliency/treesitter-chunker/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Consiliency/treesitter-chunker/discussions)
- **Documentation**: [Full Documentation](https://treesitter-chunker.readthedocs.io/)

## 🙏 Recognition

Contributors are recognized in:
- **Contributors list** on GitHub
- **Changelog** for significant contributions
- **Documentation** for major features
- **Release notes** for each version

---

**Thank you for contributing to Tree-sitter Chunker!** 🚀

Your contributions help make this library better for everyone in the community.
