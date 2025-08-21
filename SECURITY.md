# Security Policy

## 🛡️ Supported Versions

We actively maintain security updates for the following versions:

| Version | Supported          | Security Updates Until |
| ------- | ------------------ | ---------------------- |
| 1.0.x   | ✅ Yes             | 2026-01-27             |
| < 1.0   | ❌ No              | N/A                    |

## 🚨 Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please follow these steps:

### **1. DO NOT Create a Public Issue**

**Never** report security vulnerabilities through public GitHub issues, discussions, or other public channels.

### **2. Report Privately**

Send a detailed report to our security team at:
- **Email**: security@consiliency.com
- **Subject**: `[SECURITY] Tree-sitter Chunker Vulnerability Report`

### **3. Include in Your Report**

- **Description**: Clear description of the vulnerability
- **Impact**: Potential impact on users and systems
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Proof of Concept**: Code or examples if applicable
- **Affected Versions**: Which versions are affected
- **Suggested Fix**: If you have ideas for fixing the issue

### **4. Response Timeline**

- **Initial Response**: Within 24 hours
- **Assessment**: Within 3 business days
- **Fix Development**: Depends on complexity
- **Public Disclosure**: After fix is available

## 🔒 Security Features

### **Input Validation**

- **File Paths**: Strict validation of file paths to prevent path traversal attacks
- **Language Detection**: Safe language detection without code execution
- **Configuration Files**: Secure parsing of configuration files
- **Grammar Sources**: Validation of grammar repository URLs

### **Sandboxing**

- **Parser Isolation**: Tree-sitter parsers run in isolated environments
- **Memory Limits**: Configurable memory limits for large files
- **Execution Restrictions**: No arbitrary code execution capabilities

### **Data Protection**

- **No Data Collection**: We do not collect or transmit user data
- **Local Processing**: All processing happens locally on your machine
- **Secure Caching**: Local cache with proper file permissions

## 🧪 Security Testing

### **Automated Security Checks**

- **Dependency Scanning**: Regular scanning for vulnerable dependencies
- **Code Analysis**: Static analysis for security issues
- **Fuzzing**: Automated fuzzing of parser inputs
- **Penetration Testing**: Regular security assessments

### **Manual Security Reviews**

- **Code Reviews**: Security-focused code reviews
- **Architecture Reviews**: Security architecture assessments
- **Third-Party Audits**: External security audits

## 🔄 Security Update Process

### **1. Vulnerability Assessment**

- Severity classification (Critical, High, Medium, Low)
- Impact analysis
- Affected version identification

### **2. Fix Development**

- Security patch development
- Testing and validation
- Backward compatibility assessment

### **3. Release Process**

- Security patch release
- Public disclosure (after fix availability)
- CVE assignment if applicable

### **4. Communication**

- Security advisory publication
- User notification through multiple channels
- Documentation updates

## 🚫 Known Security Limitations

### **Current Limitations**

- **File System Access**: Requires read access to source files
- **Network Access**: May download grammar files from GitHub
- **Memory Usage**: Large files may consume significant memory

### **Mitigation Strategies**

- **File Permissions**: Use appropriate file permissions
- **Network Security**: Configure firewall rules for grammar downloads
- **Resource Limits**: Set appropriate memory and CPU limits

## 🔐 Best Practices for Users

### **Installation Security**

```bash
# Use official sources only
pip install treesitter-chunker

# Verify package integrity
pip install --require-hashes treesitter-chunker

# Use virtual environments
python -m venv venv
source venv/bin/activate
pip install treesitter-chunker
```

### **Runtime Security**

```python
# Limit file access to trusted directories
import os
os.chdir('/trusted/source/directory')

# Use appropriate file permissions
# chmod 644 source_files/*.py

# Monitor resource usage
import resource
resource.setrlimit(resource.RLIMIT_AS, (1024*1024*1024, -1))  # 1GB memory limit
```

### **Configuration Security**

```toml
# .chunkerrc
# Restrict grammar sources to trusted repositories
grammar_sources = [
    "https://github.com/tree-sitter/tree-sitter-python",
    "https://github.com/tree-sitter/tree-sitter-javascript"
]

# Set appropriate limits
max_file_size = 100000000  # 100MB
max_memory_usage = 1073741824  # 1GB
```

## 🏆 Security Acknowledgments

We thank security researchers and users who responsibly report vulnerabilities:

- **Responsible Disclosure**: Following responsible disclosure practices
- **Security Research**: Supporting security research and testing
- **Community Collaboration**: Working with the security community

## 📞 Security Contact Information

### **Primary Security Contact**

- **Email**: security@consiliency.com
- **Response Time**: Within 24 hours
- **PGP Key**: Available upon request

### **Alternative Contacts**

- **GitHub Security**: Use GitHub's security advisory system
- **Maintainers**: Direct contact for urgent issues

### **Emergency Response**

For critical security issues requiring immediate attention:
- **Email**: security-emergency@consiliency.com
- **Response Time**: Within 4 hours

## 📚 Security Resources

### **Additional Information**

- **Security Documentation**: [Security Guide](docs/security-guide.md)
- **Best Practices**: [Security Best Practices](docs/security-best-practices.md)
- **Vulnerability Database**: [CVE Database](https://cve.mitre.org/)

### **External Resources**

- [OWASP Security Guidelines](https://owasp.org/)
- [Python Security Best Practices](https://python-security.readthedocs.io/)
- [Tree-sitter Security](https://tree-sitter.github.io/tree-sitter/security)

---

**Security is everyone's responsibility. Thank you for helping keep Tree-sitter Chunker secure!** 🛡️
