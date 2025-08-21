# Support & Community

Welcome to the Tree-sitter Chunker community! This document provides information on how to get help, connect with other users, and contribute to the project.

## 🆘 Getting Help

### **Quick Help Options**

1. **📚 Documentation**: Start with our [comprehensive documentation](https://treesitter-chunker.readthedocs.io/)
2. **🔍 Search**: Search existing [issues](https://github.com/Consiliency/treesitter-chunker/issues) and [discussions](https://github.com/Consiliency/treesitter-chunker/discussions)
3. **💬 Discussions**: Ask questions in [GitHub Discussions](https://github.com/Consiliency/treesitter-chunker/discussions)
4. **🐛 Issues**: Report bugs in [GitHub Issues](https://github.com/Consiliency/treesitter-chunker/issues)

### **Before Asking for Help**

To get the best help quickly, please:

- ✅ **Check the documentation** first
- ✅ **Search existing issues** for similar problems
- ✅ **Provide a minimal example** that reproduces the issue
- ✅ **Include your environment** (OS, Python version, package version)
- ✅ **Show error messages** and stack traces

## 🐛 Reporting Issues

### **Bug Report Template**

```markdown
**Bug Description**
Clear description of what's not working

**Steps to Reproduce**
1. Step 1
2. Step 2
3. Step 3

**Expected Behavior**
What you expected to happen

**Actual Behavior**
What actually happened

**Environment**
- OS: [e.g., Ubuntu 22.04, macOS 14.0, Windows 11]
- Python Version: [e.g., 3.11.5]
- Tree-sitter Chunker Version: [e.g., 1.0.9]
- Installation Method: [e.g., pip, uv, development]

**Additional Information**
Any other relevant details
```

### **Feature Request Template**

```markdown
**Feature Description**
Clear description of what you want

**Use Case**
Why this feature would be useful

**Proposed Solution**
How you think it could be implemented

**Alternatives Considered**
Other approaches you've considered

**Additional Context**
Any other relevant information
```

## 💬 Community Channels

### **GitHub Discussions**

- **General Questions**: [Q&A](https://github.com/Consiliency/treesitter-chunker/discussions/categories/q-a)
- **Show & Tell**: [Show & Tell](https://github.com/Consiliency/treesitter-chunker/discussions/categories/show-and-tell)
- **Ideas**: [Ideas](https://github.com/Consiliency/treesitter-chunker/discussions/categories/ideas)
- **Announcements**: [Announcements](https://github.com/Consiliency/treesitter-chunker/discussions/categories/announcements)

### **GitHub Issues**

- **Bug Reports**: [Bug Reports](https://github.com/Consiliency/treesitter-chunker/issues?q=is%3Aissue+is%3Aopen+label%3Abug)
- **Feature Requests**: [Feature Requests](https://github.com/Consiliency/treesitter-chunker/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement)
- **Documentation**: [Documentation Issues](https://github.com/Consiliency/treesitter-chunker/issues?q=is%3Aissue+is%3Aopen+label%3Adocumentation)

## 🔧 Common Issues & Solutions

### **Installation Issues**

#### **Grammar Build Failures**
```bash
# Solution: Use prebuilt wheels (recommended)
pip install treesitter-chunker

# Alternative: Set custom build directory
export CHUNKER_GRAMMAR_BUILD_DIR="$HOME/.cache/treesitter-chunker/build"
pip install treesitter-chunker
```

#### **Missing Dependencies**
```bash
# Install with all dependencies
pip install "treesitter-chunker[all]"

# Install specific extras
pip install "treesitter-chunker[viz]"  # Visualization tools
pip install "treesitter-chunker[api]"  # REST API support
```

### **Runtime Issues**

#### **Memory Issues with Large Files**
```python
# Use streaming for large files
from chunker import chunk_file_streaming
chunks = chunk_file_streaming("large_file.py", "python", chunk_size=1000)
```

#### **Language Detection Problems**
```python
# Force specific language
from chunker import chunk_file
chunks = chunk_file("file.xyz", language="python", force_language=True)
```

#### **Performance Issues**
```python
# Enable AST caching
from chunker import ASTCache
cache = ASTCache(max_size=1000)
# Cache is automatically used by chunk_file()
```

### **Configuration Issues**

#### **Configuration File Not Found**
```bash
# Create configuration file
mkdir -p ~/.config
touch ~/.config/.chunkerrc

# Or use environment variables
export CHUNKER_CONFIG_FILE="$HOME/.chunkerrc"
```

#### **Grammar Download Issues**
```bash
# Set custom grammar directory
export CHUNKER_GRAMMARS_DIR="$HOME/.cache/treesitter-chunker/grammars"

# Or disable auto-download
export CHUNKER_AUTO_DOWNLOAD_GRAMMARS=false
```

## 📚 Learning Resources

### **Documentation**

- **[Getting Started](docs/getting-started.md)**: Quick start guide
- **[User Guide](docs/user-guide.md)**: Comprehensive usage guide
- **[API Reference](docs/api-reference.md)**: Complete API documentation
- **[Cookbook](docs/cookbook.md)**: Practical examples and recipes
- **[Performance Guide](docs/performance-guide.md)**: Optimization strategies

### **Examples**

- **[Basic Examples](examples/)**: Simple usage examples
- **[Advanced Examples](examples/advanced/)**: Complex use cases
- **[Integration Examples](examples/integrations/)**: Third-party integrations

### **Tutorials**

- **[Language Plugin Development](docs/plugin-development.md)**: Create custom language support
- **[Performance Optimization](docs/performance-guide.md)**: Speed up your chunking
- **[Export Formats](docs/export-formats.md)**: Output data in various formats

## 🤝 Contributing

### **Ways to Contribute**

- **Code**: Submit pull requests with improvements
- **Documentation**: Improve or expand documentation
- **Examples**: Add examples to the cookbook
- **Testing**: Help test on different platforms
- **Bug Reports**: Report issues you encounter
- **Feature Ideas**: Suggest new features

### **Getting Started with Contributions**

1. **Fork the repository**
2. **Create a feature branch**
3. **Make your changes**
4. **Add tests**
5. **Submit a pull request**

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## 🏆 Community Guidelines

### **Code of Conduct**

- **Be Respectful**: Treat everyone with respect
- **Be Helpful**: Help others learn and grow
- **Be Constructive**: Provide constructive feedback
- **Be Inclusive**: Welcome people from all backgrounds

### **Communication Guidelines**

- **Use Clear Language**: Write clearly and concisely
- **Be Patient**: Remember that everyone is learning
- **Ask Questions**: Don't hesitate to ask for clarification
- **Share Knowledge**: Help others by sharing what you know

## 📊 Project Status

### **Current Status**

- **Version**: 1.0.9 (Production Ready)
- **Status**: Active Development
- **Languages Supported**: 36+ built-in, 100+ auto-download
- **Test Coverage**: 95%+
- **Documentation**: Comprehensive

### **Roadmap**

- **Phase 3**: Performance optimization and validation
- **Future**: Additional language support and features
- **Long-term**: Advanced AI/ML integration

## 📞 Contact Information

### **Maintainers**

- **Primary Contact**: [GitHub Issues](https://github.com/Consiliency/treesitter-chunker/issues)
- **Security Issues**: security@consiliency.com
- **General Inquiries**: dev@consiliency.com

### **Response Times**

- **Bug Reports**: Within 24 hours
- **Feature Requests**: Within 3 business days
- **Security Issues**: Within 4 hours
- **General Questions**: Within 48 hours

## 🌟 Recognition

### **Contributors**

We recognize contributors in:
- **GitHub Contributors**: [Contributors page](https://github.com/Consiliency/treesitter-chunker/graphs/contributors)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)
- **Release Notes**: Each version release
- **Documentation**: For major features

### **Community Highlights**

- **Active Contributors**: 50+ contributors
- **Languages Supported**: 36+ programming languages
- **Test Coverage**: 95%+ maintained
- **Documentation**: Comprehensive guides and examples

---

**Thank you for being part of the Tree-sitter Chunker community!** 🚀

Together, we're building the best semantic code chunking library for developers worldwide.
