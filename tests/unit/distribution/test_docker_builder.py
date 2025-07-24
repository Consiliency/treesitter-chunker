"""Unit tests for Docker builder"""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from chunker.distribution.docker_builder import DockerBuilder


class TestDockerBuilder:
    """Test Docker image building functionality"""

    @patch("shutil.which")
    def test_docker_required(self, mock_which):
        """Test that Docker is required for building"""
        mock_which.return_value = None
        builder = DockerBuilder()

        success, message = builder.build_image("test:latest")
        assert not success
        assert "Docker not found" in message

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_docker_daemon_check(self, mock_which, mock_run):
        """Test Docker daemon is checked before building"""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.side_effect = subprocess.CalledProcessError(1, "docker info")

        builder = DockerBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            dockerfile = Path(tmpdir) / "Dockerfile"
            dockerfile.write_text("FROM python:3.9")

            success, message = builder.build_image(
                "test:latest",
                dockerfile_path=dockerfile,
            )
            assert not success
            assert "Docker daemon is not running" in message

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_single_platform_build(self, mock_which, mock_run):
        """Test single platform Docker build"""
        mock_which.return_value = "/usr/bin/docker"
        # Set up side effects for all subprocess calls
        mock_run.side_effect = [
            # docker buildx version (for buildx check)
            Mock(returncode=1),  # buildx not available
            # docker info
            Mock(returncode=0),
            # docker build
            Mock(returncode=0, stdout="Successfully built abcd1234", stderr=""),
            # docker inspect
            Mock(returncode=0, stdout="sha256:abcd1234567890", stderr=""),
        ]

        builder = DockerBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            dockerfile = Path(tmpdir) / "Dockerfile"
            dockerfile.write_text("FROM python:3.9\nRUN pip install treesitter-chunker")

            success, image_id = builder.build_image(
                "test:latest",
                platforms=["linux/amd64"],
                dockerfile_path=dockerfile,
            )

            assert success
            assert image_id == "sha256:abcd1234567890"

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_multi_platform_build(self, mock_which, mock_run):
        """Test multi-platform Docker build with buildx"""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.side_effect = [
            # docker info
            Mock(returncode=0),
            # docker buildx version
            Mock(returncode=0),
            # docker buildx inspect
            Mock(returncode=1),  # Builder doesn't exist
            # docker buildx create
            Mock(returncode=0),
            # docker buildx use
            Mock(returncode=0),
            # docker buildx build
            Mock(returncode=0, stdout="writing image sha256:multi123 done", stderr=""),
        ]

        builder = DockerBuilder()
        builder.buildx_available = True  # Force buildx available

        with tempfile.TemporaryDirectory() as tmpdir:
            dockerfile = Path(tmpdir) / "Dockerfile"
            dockerfile.write_text("FROM python:3.9")

            success, image_id = builder.build_image(
                "test:latest",
                platforms=["linux/amd64", "linux/arm64"],
                dockerfile_path=dockerfile,
            )

            assert success
            assert "sha256:multi123" in image_id

    def test_dockerfile_not_found(self):
        """Test handling of missing Dockerfile"""
        builder = DockerBuilder()

        success, message = builder.build_image(
            "test:latest",
            dockerfile_path=Path("/nonexistent/Dockerfile"),
        )

        assert not success
        assert "Dockerfile not found" in message

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_verify_image(self, mock_which, mock_run):
        """Test Docker image verification"""
        mock_which.return_value = "/usr/bin/docker"

        image_data = {
            "Id": "sha256:abcd1234",
            "Created": "2023-01-01T00:00:00Z",
            "Size": 1234567,
            "Architecture": "amd64",
            "Os": "linux",
            "RootFS": {"Layers": ["layer1", "layer2"]},
        }

        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([image_data]),
            stderr="",
        )

        builder = DockerBuilder()
        success, info = builder.verify_image("test:latest")

        assert success
        assert info["id"] == "sha256:abcd1234"
        assert info["architecture"] == "amd64"
        assert info["layers"] == 2

    def test_extract_image_id(self):
        """Test image ID extraction from build output"""
        builder = DockerBuilder()

        # Test various output formats
        output1 = "writing image sha256:abc123def456 done"
        assert builder._extract_image_id(output1) == "sha256:abc123def456"

        output2 = 'Step 5/5 : CMD ["python"]\n ---> abc123\nSuccessfully built abc123'
        assert builder._extract_image_id(output2) is None  # No sha256 format

    @patch("shutil.which")
    def test_buildx_detection(self, mock_which):
        """Test Docker buildx detection"""
        mock_which.return_value = "/usr/bin/docker"

        # Test buildx available
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            builder = DockerBuilder()
            assert builder._check_buildx()

        # Test buildx not available
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "docker buildx")
            builder = DockerBuilder()
            assert not builder._check_buildx()
