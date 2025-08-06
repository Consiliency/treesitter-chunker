"""Comprehensive tests for Dockerfile language support."""

from chunker import chunk_file, get_parser
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.dockerfile import DockerfilePlugin


class TestDockerfileBasicChunking:
    """Test basic Dockerfile chunking functionality."""

    @staticmethod
    def test_simple_dockerfile(tmp_path):
        """Test basic Dockerfile with common instructions."""
        src = tmp_path / "Dockerfile"
        src.write_text(
            """FROM ubuntu:20.04

RUN apt-get update && apt-get install -y python3

COPY . /app
WORKDIR /app

CMD ["python3", "app.py"]
""",
        )
        chunks = chunk_file(src, "dockerfile")
        assert len(chunks) >= 5
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "from_instruction" in chunk_types
        assert "run_instruction" in chunk_types
        assert "copy_instruction" in chunk_types
        assert "workdir_instruction" in chunk_types
        assert "cmd_instruction" in chunk_types

    @staticmethod
    def test_multi_line_run_instruction(tmp_path):
        """Test multi-line RUN instruction."""
        src = tmp_path / "Dockerfile"
        src.write_text(
            """FROM alpine:latest

RUN apk add --no-cache \\
    python3 \\
    py3-pip \\
    git \\
    && pip3 install --upgrade pip
""",
        )
        chunks = chunk_file(src, "dockerfile")
        run_chunks = [c for c in chunks if c.node_type == "run_instruction"]
        assert len(run_chunks) == 1
        assert "apk add" in run_chunks[0].content
        assert "pip3 install" in run_chunks[0].content

    @staticmethod
    def test_dockerfile_with_comments(tmp_path):
        """Test Dockerfile with comments."""
        src = tmp_path / "Dockerfile"
        src.write_text(
            """# Base image
FROM node:14

# Install dependencies
RUN npm install

# Set working directory
WORKDIR /usr/src/app

# Copy application files
COPY package*.json ./
COPY . .

# Expose port
EXPOSE 3000

# Start application
CMD ["npm", "start"]
""",
        )
        chunks = chunk_file(src, "dockerfile")
        comment_chunks = [c for c in chunks if c.node_type == "comment"]
        assert len(comment_chunks) >= 5
        assert any("Base image" in c.content for c in comment_chunks)
        assert any("Install dependencies" in c.content for c in comment_chunks)

    @staticmethod
    def test_dockerfile_with_args_and_env(tmp_path):
        """Test Dockerfile with ARG and ENV instructions."""
        src = tmp_path / "Dockerfile"
        src.write_text(
            """ARG NODE_VERSION=14

FROM node:${NODE_VERSION}

ENV APP_HOME=/app
ENV NODE_ENV=production

WORKDIR ${APP_HOME}
""",
        )
        chunks = chunk_file(src, "dockerfile")
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "arg_instruction" in chunk_types
        assert "env_instruction" in chunk_types
        env_chunks = [c for c in chunks if c.node_type == "env_instruction"]
        assert len(env_chunks) == 2

    @staticmethod
    def test_dockerfile_with_healthcheck(tmp_path):
        """Test Dockerfile with HEALTHCHECK instruction."""
        src = tmp_path / "Dockerfile"
        src.write_text(
            """FROM nginx:alpine

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost/ || exit 1

EXPOSE 80
""",
        )
        chunks = chunk_file(src, "dockerfile")
        healthcheck_chunks = [
            c for c in chunks if c.node_type == "healthcheck_instruction"
        ]
        assert len(healthcheck_chunks) == 1
        assert "curl -f http://localhost/" in healthcheck_chunks[0].content


class TestDockerfileContractCompliance:
    """Test ExtendedLanguagePluginContract compliance."""

    @staticmethod
    def test_implements_contract():
        """Verify DockerfilePlugin implements ExtendedLanguagePluginContract."""
        assert issubclass(DockerfilePlugin, ExtendedLanguagePluginContract)

    @classmethod
    def test_get_semantic_chunks(cls, tmp_path):
        """Test get_semantic_chunks method."""
        plugin = DockerfilePlugin()
        source = b'FROM python:3.9\nRUN pip install flask\nCMD ["python", "app.py"]\n'
        parser = get_parser("dockerfile")
        plugin.set_parser(parser)
        tree = parser.parse(source)
        chunks = plugin.get_semantic_chunks(tree.root_node, source)
        assert len(chunks) >= 3
        assert all("type" in chunk for chunk in chunks)
        assert all("start_line" in chunk for chunk in chunks)
        assert all("end_line" in chunk for chunk in chunks)
        assert all("content" in chunk for chunk in chunks)

    @classmethod
    def test_get_chunk_node_types(cls):
        """Test get_chunk_node_types method."""
        plugin = DockerfilePlugin()
        node_types = plugin.get_chunk_node_types()
        assert isinstance(node_types, set)
        assert len(node_types) > 0
        assert "from_instruction" in node_types
        assert "run_instruction" in node_types
        assert "cmd_instruction" in node_types

    @staticmethod
    def test_should_chunk_node():
        """Test should_chunk_node method."""
        plugin = DockerfilePlugin()

        class MockNode:

            def __init__(self, node_type):
                self.type = node_type

        assert plugin.should_chunk_node(MockNode("from_instruction"))
        assert plugin.should_chunk_node(MockNode("run_instruction"))
        assert plugin.should_chunk_node(MockNode("comment"))
        assert not plugin.should_chunk_node(MockNode("source_file"))
        assert not plugin.should_chunk_node(MockNode("line_continuation"))

    @staticmethod
    def test_get_node_context():
        """Test get_node_context method."""
        plugin = DockerfilePlugin()

        class MockNode:

            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        node = MockNode("run_instruction")
        context = plugin.get_node_context(node, b"RUN apt-get update")
        assert context is not None
        node = MockNode("cmd_instruction")
        context = plugin.get_node_context(node, b'CMD ["python", "app.py"]')
        assert context is not None


class TestDockerfileEdgeCases:
    """Test edge cases in Dockerfile parsing."""

    @staticmethod
    def test_empty_dockerfile(tmp_path):
        """Test empty Dockerfile."""
        src = tmp_path / "Dockerfile"
        src.write_text("")
        chunks = chunk_file(src, "dockerfile")
        assert len(chunks) == 0

    @staticmethod
    def test_dockerfile_with_only_comments(tmp_path):
        """Test Dockerfile with only comments."""
        src = tmp_path / "Dockerfile"
        src.write_text(
            "# This is a comment\n# Another comment\n# Yet another comment\n",
        )
        chunks = chunk_file(src, "dockerfile")
        assert all(c.node_type == "comment" for c in chunks)

    @staticmethod
    def test_dockerfile_with_escape_characters(tmp_path):
        """Test Dockerfile with escape characters."""
        src = tmp_path / "Dockerfile"
        src.write_text(
            """FROM alpine

RUN echo "Hello \\"World\\"" && \\
    echo "Line continuation\"
""",
        )
        chunks = chunk_file(src, "dockerfile")
        assert len(chunks) >= 2

    @staticmethod
    def test_multistage_dockerfile(tmp_path):
        """Test multi-stage Dockerfile."""
        src = tmp_path / "Dockerfile"
        src.write_text(
            """# Build stage
FROM golang:1.16 AS builder
WORKDIR /app
COPY . .
RUN go build -o main .

# Runtime stage
FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/main .
CMD ["./main"]
""",
        )
        chunks = chunk_file(src, "dockerfile")
        from_chunks = [c for c in chunks if c.node_type == "from_instruction"]
        assert len(from_chunks) == 2
        copy_chunks = [c for c in chunks if c.node_type == "copy_instruction"]
        assert any("--from=builder" in c.content for c in copy_chunks)
