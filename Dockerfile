# Multi-stage Dockerfile for treesitter-chunker
# Supports building and running the chunker in a minimal container

# Stage 1: Builder
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    cmake \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy source code
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir build

# Fetch and build grammars
RUN python scripts/fetch_grammars.py && \
    python scripts/build_lib.py

# Build the package
RUN python -m build --wheel --outdir /dist

# Stage 2: Runtime
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 chunker

# Copy wheel from builder
COPY --from=builder /dist/*.whl /tmp/

# Install the package
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm -f /tmp/*.whl

# Switch to non-root user
USER chunker
WORKDIR /home/chunker

# Set entrypoint
ENTRYPOINT ["treesitter-chunker"]
CMD ["--help"]

# Labels
LABEL org.opencontainers.image.title="TreeSitter Chunker"
LABEL org.opencontainers.image.description="Semantic code chunker using Tree-sitter for intelligent code analysis"
LABEL org.opencontainers.image.url="https://github.com/Consiliency/treesitter-chunker"
LABEL org.opencontainers.image.source="https://github.com/Consiliency/treesitter-chunker"
LABEL org.opencontainers.image.vendor="Consiliency"
LABEL org.opencontainers.image.licenses="MIT"