# Production Deployment Guide

This guide covers deploying Tree-sitter Chunker in production environments, including system requirements, configuration, monitoring, and troubleshooting.

## 🎯 Deployment Overview

Tree-sitter Chunker is designed as a library that can be deployed in various ways:

- **Library Integration**: Direct import into Python applications
- **CLI Application**: Command-line interface for batch processing
- **REST API**: HTTP API for remote access
- **Docker Container**: Containerized deployment
- **System Package**: Native system installation

## 🖥️ System Requirements

### **Minimum Requirements**

- **OS**: Linux (Ubuntu 18.04+), macOS 10.15+, Windows 10+
- **Python**: 3.8 or higher
- **Memory**: 2GB RAM (4GB recommended)
- **Storage**: 1GB free space (5GB recommended)
- **CPU**: 2 cores (4+ cores recommended)

### **Recommended Requirements**

- **OS**: Ubuntu 22.04 LTS, macOS 13+, Windows 11
- **Python**: 3.11 or higher
- **Memory**: 8GB RAM
- **Storage**: 10GB free space (SSD recommended)
- **CPU**: 8+ cores
- **Network**: Stable internet connection for grammar downloads

### **Production Requirements**

- **OS**: Ubuntu 22.04 LTS, RHEL 9+, CentOS Stream 9+
- **Python**: 3.11+ (LTS version)
- **Memory**: 16GB+ RAM
- **Storage**: 50GB+ SSD storage
- **CPU**: 16+ cores
- **Network**: High-bandwidth, low-latency connection

## 📦 Installation Methods

### **Method 1: PyPI Installation (Recommended)**

```bash
# Install latest stable version
pip install treesitter-chunker

# Install with specific extras
pip install "treesitter-chunker[api,viz,profile]"

# Install specific version
pip install treesitter-chunker==1.0.9
```

### **Method 2: System Package Installation**

#### **Ubuntu/Debian**
```bash
# Download .deb package
wget https://github.com/Consiliency/treesitter-chunker/releases/download/v1.0.9/python3-treesitter-chunker_1.0.9-1_all.deb

# Install package
sudo dpkg -i python3-treesitter-chunker_1.0.9-1_all.deb

# Fix dependencies if needed
sudo apt-get install -f
```

#### **RHEL/CentOS/Fedora**
```bash
# Download .rpm package
wget https://github.com/Consiliency/treesitter-chunker/releases/download/v1.0.9/python-treesitter-chunker-1.0.9-1.noarch.rpm

# Install package
sudo rpm -i python-treesitter-chunker-1.0.9-1.noarch.rpm
```

#### **macOS (Homebrew)**
```bash
# Add tap and install
brew tap consiliency/treesitter-chunker
brew install treesitter-chunker
```

### **Method 3: Docker Deployment**

```bash
# Pull latest image
docker pull ghcr.io/consiliency/treesitter-chunker:latest

# Run container
docker run -v $(pwd):/workspace treesitter-chunker chunk /workspace/example.py -l python

# Run with custom configuration
docker run -v $(pwd):/workspace \
  -e CHUNKER_CONFIG_FILE=/workspace/.chunkerrc \
  treesitter-chunker chunk /workspace/ -l python
```

### **Method 4: Source Installation**

```bash
# Clone repository
git clone https://github.com/Consiliency/treesitter-chunker.git
cd treesitter-chunker

# Install in development mode
pip install -e ".[all]"

# Build grammars
python scripts/fetch_grammars.py
python scripts/build_lib.py
```

## ⚙️ Configuration Management

### **Configuration File Setup**

Create `.chunkerrc` in your project directory or home directory:

```toml
# .chunkerrc
# Global configuration for Tree-sitter Chunker

# Performance settings
max_workers = 8
chunk_size = 1000
cache_size = 1000

# Memory limits
max_memory_usage = 1073741824  # 1GB
max_file_size = 100000000      # 100MB

# Grammar settings
auto_download_grammars = true
grammar_cache_dir = "~/.cache/treesitter-chunker/grammars"
grammar_build_dir = "~/.cache/treesitter-chunker/build"

# Export settings
default_export_format = "json"
export_compression = true

# Logging
log_level = "INFO"
log_file = "~/.cache/treesitter-chunker/logs/chunker.log"

# Language-specific settings
[languages.python]
chunk_types = ["function_definition", "class_definition", "async_function_definition"]
min_chunk_size = 5
max_chunk_size = 500

[languages.javascript]
chunk_types = ["function_declaration", "class_declaration", "method_definition"]
min_chunk_size = 3
max_chunk_size = 300
```

### **Environment Variables**

```bash
# Performance
export CHUNKER_MAX_WORKERS=8
export CHUNKER_CACHE_SIZE=1000
export CHUNKER_CHUNK_SIZE=1000

# Memory limits
export CHUNKER_MAX_MEMORY_USAGE=1073741824
export CHUNKER_MAX_FILE_SIZE=100000000

# Grammar management
export CHUNKER_GRAMMARS_DIR="$HOME/.cache/treesitter-chunker/grammars"
export CHUNKER_GRAMMAR_BUILD_DIR="$HOME/.cache/treesitter-chunker/build"
export CHUNKER_AUTO_DOWNLOAD_GRAMMARS=true

# Logging
export CHUNKER_LOG_LEVEL=INFO
export CHUNKER_LOG_FILE="$HOME/.cache/treesitter-chunker/logs/chunker.log"

# Export settings
export CHUNKER_DEFAULT_EXPORT_FORMAT=json
export CHUNKER_EXPORT_COMPRESSION=true
```

## 🚀 Performance Tuning

### **Memory Optimization**

```python
# Configure memory limits
import os
os.environ['CHUNKER_MAX_MEMORY_USAGE'] = '1073741824'  # 1GB
os.environ['CHUNKER_MAX_FILE_SIZE'] = '100000000'      # 100MB

# Use streaming for large files
from chunker import chunk_file_streaming
chunks = chunk_file_streaming("large_file.py", "python", chunk_size=1000)
```

### **CPU Optimization**

```python
# Configure worker count
import os
os.environ['CHUNKER_MAX_WORKERS'] = str(os.cpu_count())

# Use parallel processing
from chunker import chunk_files_parallel
results = chunk_files_parallel(["file1.py", "file2.py", "file3.py"], "python")
```

### **Caching Strategy**

```python
# Configure cache size
import os
os.environ['CHUNKER_CACHE_SIZE'] = '1000'

# Use AST caching
from chunker import ASTCache
cache = ASTCache(max_size=1000)
# Cache is automatically used by chunk_file()
```

## 📊 Monitoring & Observability

### **Health Checks**

```python
# Basic health check
from chunker import list_languages
try:
    languages = list_languages()
    print(f"✅ Service healthy - {len(languages)} languages available")
except Exception as e:
    print(f"❌ Service unhealthy - {e}")
```

### **Performance Metrics**

```python
# Monitor performance
import time
from chunker import chunk_file

def monitor_chunking_performance(file_path, language):
    start_time = time.time()
    start_memory = get_memory_usage()
    
    chunks = chunk_file(file_path, language)
    
    end_time = time.time()
    end_memory = get_memory_usage()
    
    duration = end_time - start_time
    memory_used = end_memory - start_memory
    
    print(f"Performance: {duration:.2f}s, Memory: {memory_used:.2f}MB")
    return chunks

def get_memory_usage():
    import psutil
    return psutil.Process().memory_info().rss / 1024 / 1024  # MB
```

### **Logging Configuration**

```python
# Configure logging
import logging
from pathlib import Path

# Create logs directory
log_dir = Path.home() / ".cache" / "treesitter-chunker" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "chunker.log"),
        logging.StreamHandler()
    ]
)

# Use in your application
logger = logging.getLogger("chunker")
logger.info("Tree-sitter Chunker initialized")
```

## 🔒 Security Configuration

### **File Access Controls**

```bash
# Restrict file access
chmod 644 source_files/*.py
chmod 755 source_directories/

# Use appropriate user permissions
sudo chown -R appuser:appuser /app/source
```

### **Network Security**

```bash
# Configure firewall for grammar downloads
sudo ufw allow out 443/tcp  # HTTPS for GitHub
sudo ufw allow out 80/tcp   # HTTP fallback

# Or restrict to specific domains
sudo ufw allow out to github.com port 443
sudo ufw allow out to raw.githubusercontent.com port 443
```

### **Resource Limits**

```bash
# Set system limits
echo "appuser soft nofile 4096" >> /etc/security/limits.conf
echo "appuser hard nofile 8192" >> /etc/security/limits.conf

# Or use systemd
[Service]
LimitNOFILE=8192
LimitNPROC=1024
```

## 🐳 Docker Deployment

### **Dockerfile Example**

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Tree-sitter Chunker
RUN pip install treesitter-chunker[all]

# Create app directory
WORKDIR /app

# Copy application code
COPY . .

# Create cache directories
RUN mkdir -p /app/.cache/treesitter-chunker/{grammars,build,logs}

# Set environment variables
ENV CHUNKER_GRAMMARS_DIR=/app/.cache/treesitter-chunker/grammars
ENV CHUNKER_GRAMMAR_BUILD_DIR=/app/.cache/treesitter-chunker/build
ENV CHUNKER_LOG_FILE=/app/.cache/treesitter-chunker/logs/chunker.log

# Expose port (if using API)
EXPOSE 8000

# Run application
CMD ["python", "app.py"]
```

### **Docker Compose Example**

```yaml
version: '3.8'

services:
  treesitter-chunker:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./source:/app/source:ro
      - ./output:/app/output
      - chunker-cache:/app/.cache
    environment:
      - CHUNKER_MAX_WORKERS=8
      - CHUNKER_CACHE_SIZE=1000
      - CHUNKER_LOG_LEVEL=INFO
    restart: unless-stopped

volumes:
  chunker-cache:
```

## 🔄 CI/CD Integration

### **GitHub Actions Example**

```yaml
name: Deploy Tree-sitter Chunker

on:
  push:
    tags: ['v*']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install treesitter-chunker[all]
          pip install pytest
      
      - name: Run tests
        run: |
          python -c "from chunker import list_languages; print(list_languages())"
      
      - name: Deploy to production
        run: |
          # Your deployment script here
          echo "Deploying version ${{ github.ref_name }}"
```

### **Jenkins Pipeline Example**

```groovy
pipeline {
    agent any
    
    stages {
        stage('Build') {
            steps {
                sh 'pip install treesitter-chunker[all]'
            }
        }
        
        stage('Test') {
            steps {
                sh 'python -c "from chunker import list_languages; print(list_languages())"'
            }
        }
        
        stage('Deploy') {
            steps {
                sh 'echo "Deploying to production"'
                // Your deployment commands
            }
        }
    }
}
```

## 🚨 Troubleshooting

### **Common Issues**

#### **Memory Issues**
```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head -10

# Increase swap if needed
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

#### **Grammar Build Failures**
```bash
# Check build directory permissions
ls -la ~/.cache/treesitter-chunker/build/

# Rebuild grammars
rm -rf ~/.cache/treesitter-chunker/build/*
python -c "from chunker.grammar.manager import TreeSitterGrammarManager; gm = TreeSitterGrammarManager(); gm.build_grammar('python')"
```

#### **Performance Issues**
```bash
# Check CPU usage
htop
iostat -x 1

# Check disk I/O
iotop
```

### **Debug Mode**

```bash
# Enable debug logging
export CHUNKER_LOG_LEVEL=DEBUG

# Run with verbose output
python -v your_script.py

# Use Python debugger
python -m pdb your_script.py
```

## 📈 Scaling Strategies

### **Horizontal Scaling**

- **Load Balancing**: Use multiple instances behind a load balancer
- **Microservices**: Split functionality into separate services
- **Queue Systems**: Use message queues for batch processing

### **Vertical Scaling**

- **Memory**: Increase RAM for larger file processing
- **CPU**: Use more powerful processors
- **Storage**: Use faster storage (SSD/NVMe)

### **Caching Strategies**

- **Redis**: Cache parsed ASTs and results
- **CDN**: Cache grammar files and documentation
- **Local Cache**: Use local file system caching

## 🔍 Monitoring Tools

### **System Monitoring**

- **Prometheus**: Metrics collection
- **Grafana**: Visualization and dashboards
- **AlertManager**: Alerting and notifications

### **Application Monitoring**

- **Sentry**: Error tracking and performance monitoring
- **DataDog**: Application performance monitoring
- **New Relic**: Full-stack observability

### **Log Aggregation**

- **ELK Stack**: Elasticsearch, Logstash, Kibana
- **Fluentd**: Log collection and forwarding
- **Splunk**: Enterprise log management

---

**For additional support, see [SUPPORT.md](SUPPORT.md) or create an issue on GitHub.**
