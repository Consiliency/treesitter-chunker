"""Unit tests for release manager"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from chunker.distribution.release_manager import ReleaseManager


class TestReleaseManager:
    """Test release management functionality"""

    @classmethod
    def test_prepare_release_version_validation(cls):
        """Test version validation during release preparation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReleaseManager(Path(tmpdir))
            with patch.object(manager, "_get_current_version", return_value="1.0.0"):
                success, info = manager.prepare_release("0.9.0", "changelog")
                assert not success
                assert "Invalid version bump" in info["errors"][0]
                with patch.object(manager, "_run_tests", return_value=True):
                    with patch.object(
                        manager,
                        "_update_version_in_file",
                        return_value=True,
                    ):
                        with patch.object(
                            manager,
                            "_update_changelog",
                            return_value=True,
                        ):
                            with patch.object(
                                manager,
                                "_create_git_tag",
                                return_value=True,
                            ):
                                success, info = manager.prepare_release(
                                    "1.1.0",
                                    "changelog",
                                )
                                assert success

    @classmethod
    def test_version_file_updates(cls):
        """Test version updates in multiple files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            manager = ReleaseManager(project_root)
            pyproject = project_root / "pyproject.toml"
            pyproject.write_text('version = "1.0.0"')
            init_file = project_root / "chunker" / "__init__.py"
            init_file.parent.mkdir()
            init_file.write_text('__version__ = "1.0.0"')
            setup_file = project_root / "setup.py"
            setup_file.write_text('version="1.0.0"')
            assert manager._update_version_in_file(pyproject, "1.1.0")
            assert manager._update_version_in_file(init_file, "1.1.0")
            assert manager._update_version_in_file(setup_file, "1.1.0")
            assert 'version = "1.1.0"' in pyproject.read_text()
            assert '__version__ = "1.1.0"' in init_file.read_text()
            assert 'version="1.1.0"' in setup_file.read_text()

    @classmethod
    def test_changelog_update(cls):
        """Test CHANGELOG.md updates"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReleaseManager(Path(tmpdir))
            changelog_path = Path(tmpdir) / "CHANGELOG.md"
            assert manager._update_changelog(changelog_path, "1.0.0", "Initial release")
            content = changelog_path.read_text()
            assert "# Changelog" in content
            assert "[1.0.0]" in content
            assert "Initial release" in content
            assert manager._update_changelog(changelog_path, "1.1.0", "New features")
            content = changelog_path.read_text()
            assert "[1.1.0]" in content
            assert "[1.0.0]" in content

    @classmethod
    def test_validate_version_bump(cls):
        """Test version bump validation"""
        manager = ReleaseManager()
        assert manager._validate_version_bump("1.0.0", "1.0.1")
        assert manager._validate_version_bump("1.0.0", "1.1.0")
        assert manager._validate_version_bump("1.0.0", "2.0.0")
        assert not manager._validate_version_bump("1.0.0", "1.0.0")
        assert not manager._validate_version_bump("1.0.0", "0.9.0")
        assert not manager._validate_version_bump("1.0.0", "invalid")

    @classmethod
    @patch("subprocess.run")
    def test_create_git_tag(cls, mock_run):
        """Test git tag creation"""
        manager = ReleaseManager()
        mock_run.side_effect = [Mock(returncode=0, stdout=""), Mock(returncode=0)]
        assert manager._create_git_tag("v1.0.0", "Release 1.0.0")
        mock_run.side_effect = [Mock(returncode=0, stdout="v1.0.0\n")]
        assert not manager._create_git_tag("v1.0.0", "Release 1.0.0")

    @classmethod
    @patch("subprocess.run")
    def test_run_tests(cls, mock_run):
        """Test running test suite"""
        manager = ReleaseManager()
        mock_run.return_value = Mock(returncode=0)
        assert manager._run_tests()
        mock_run.return_value = Mock(returncode=1)
        assert not manager._run_tests()

    @classmethod
    @patch("subprocess.run")
    def test_build_artifacts(cls, mock_run):
        """Test building release artifacts"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            output_dir = project_root / "dist"
            manager = ReleaseManager(project_root)
            mock_run.return_value = Mock(returncode=0)

            def create_files(*args, **kwargs):
                output_dir.mkdir(exist_ok=True)
                if "--sdist" in args[0]:
                    (output_dir / "package-1.0.0.tar.gz").touch()
                elif "--wheel" in args[0]:
                    (output_dir / "package-1.0.0-py3-none-any.whl").touch()
                return Mock(returncode=0)

            mock_run.side_effect = create_files
            artifacts = manager.create_release_artifacts("1.0.0", output_dir)
            assert len(artifacts) >= 2
            assert any(str(a).endswith(".tar.gz") for a in artifacts)
            assert any(str(a).endswith(".whl") for a in artifacts)

    @classmethod
    def test_generate_checksums(cls):
        """Test checksum generation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manager = ReleaseManager()
            file1 = output_dir / "test1.txt"
            file1.write_text("content1")
            file2 = output_dir / "test2.txt"
            file2.write_text("content2")
            checksum_path = manager._generate_checksums([file1, file2], output_dir)
            assert checksum_path.exists()
            content = checksum_path.read_text()
            assert "test1.txt" in content
            assert "test2.txt" in content
            lines = content.strip().split("\n")
            for line in lines:
                hash_part = line.split()[0]
                assert len(hash_part) == 64
                assert all(c in "0123456789abcdef" for c in hash_part)

    @classmethod
    def test_create_release_notes(cls):
        """Test release notes creation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            manager = ReleaseManager(project_root)
            changelog = project_root / "CHANGELOG.md"
            changelog.write_text(
                """# Changelog

## [1.0.0] - 2023-01-01

### Added
- Initial release
- Basic functionality

## [0.9.0] - 2022-12-01

### Added
- Beta features
""",
            )
            notes_path = project_root / "RELEASE_NOTES.md"
            assert manager._create_release_notes("1.0.0", notes_path)
            content = notes_path.read_text()
            assert "[1.0.0]" in content
            assert "Initial release" in content
            assert "[0.9.0]" not in content

    @classmethod
    def test_get_current_version(cls):
        """Test getting current version from pyproject.toml"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            manager = ReleaseManager(project_root)
            assert manager._get_current_version() == "0.0.0"
            pyproject = project_root / "pyproject.toml"
            pyproject.write_text('\n[project]\nname = "test"\nversion = "1.2.3"\n')
            assert manager._get_current_version() == "1.2.3"
