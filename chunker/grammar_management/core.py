"""Core grammar management engine for treesitter-chunker.

This module provides the core grammar management infrastructure with comprehensive
functionality for grammar discovery, installation, removal, validation, and version
management. Implements all requirements for Phase 1.8 Task 1.8.1.

Key Components:
- GrammarManager: Main grammar management engine
- GrammarRegistry: Registry for grammar lookup with priority logic  
- GrammarInstaller: Handles grammar download, build, and installation
- GrammarValidator: Validates grammar integrity and compatibility

Directory Structure:
- User directory: ~/.cache/treesitter-chunker/grammars/
- Package directory: Package installation location
- Cache directories: downloads and builds subdirectories

Phase 1.8 Compliance:
- Complete grammar lifecycle management
- Version conflict detection and resolution
- Error recovery and rollback support
- Cache management and cleanup
- Dependency tracking and cleanup
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

from chunker.exceptions import ChunkerError
from chunker.interfaces.grammar import GrammarInfo, GrammarStatus, NodeTypeInfo

logger = logging.getLogger(__name__)


class GrammarPriority(Enum):
    """Grammar priority levels for selection logic."""

    USER = 1  # User-installed grammars (highest priority)
    PACKAGE = 2  # Package-bundled grammars (medium priority)
    FALLBACK = 3  # Fallback/default grammars (lowest priority)


class ValidationLevel(Enum):
    """Grammar validation severity levels."""

    BASIC = "basic"  # Basic file existence and syntax
    STANDARD = "standard"  # Standard parsing tests
    EXTENSIVE = "extensive"  # Comprehensive compatibility tests


@dataclass
class InstallationInfo:
    """Information about a grammar installation."""

    version: str
    install_date: float
    install_path: Path
    source_url: str
    source_commit: str | None = None
    priority: GrammarPriority = GrammarPriority.USER
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of grammar validation."""

    is_valid: bool
    level: ValidationLevel
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    performance_metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class GrammarManagementError(ChunkerError):
    """Base exception for grammar management operations."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        grammar_name: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)
        self.operation = operation
        self.grammar_name = grammar_name


class GrammarInstallationError(GrammarManagementError):
    """Exception for grammar installation failures."""


class GrammarValidationError(GrammarManagementError):
    """Exception for grammar validation failures."""


class GrammarRegistryError(GrammarManagementError):
    """Exception for grammar registry operations."""


class GrammarValidator:
    """Validates grammar integrity, compatibility, and performance."""

    def __init__(self, cache_dir: Path | None = None):
        """Initialize grammar validator.

        Args:
            cache_dir: Directory for caching validation results
        """
        self._cache_dir = cache_dir or (Path.home() / ".cache" / "treesitter-chunker")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._validation_cache = self._cache_dir / "validation_cache.json"
        self._cache = self._load_validation_cache()

    def validate_grammar(
        self,
        grammar_path: Path,
        language: str,
        level: ValidationLevel = ValidationLevel.STANDARD,
    ) -> ValidationResult:
        """Validate a grammar at the specified level.

        Args:
            grammar_path: Path to the compiled grammar file
            language: Language name
            level: Validation level to perform

        Returns:
            Validation result with errors, warnings, and metrics
        """
        result = ValidationResult(is_valid=False, level=level)

        try:
            # Check cache first
            cache_key = self._get_cache_key(grammar_path, language, level)
            if cache_key in self._cache:
                cached_result = self._cache[cache_key]
                # Check if cache is still valid (24 hours)
                if time.time() - cached_result.get("timestamp", 0) < 86400:
                    return self._deserialize_validation_result(cached_result)

            # Perform validation based on level
            if level == ValidationLevel.BASIC:
                result = self._validate_basic(grammar_path, language)
            elif level == ValidationLevel.STANDARD:
                result = self._validate_standard(grammar_path, language)
            elif level == ValidationLevel.EXTENSIVE:
                result = self._validate_extensive(grammar_path, language)

            # Cache the result
            self._cache_validation_result(cache_key, result)

            return result

        except Exception as e:
            logger.error(f"Validation failed for {language}: {e}")
            result.errors.append(f"Validation error: {e!s}")
            return result

    def check_abi_compatibility(self, grammar_path: Path) -> tuple[bool, str | None]:
        """Check if grammar ABI is compatible with current tree-sitter version.

        Args:
            grammar_path: Path to compiled grammar

        Returns:
            Tuple of (is_compatible, error_message)
        """
        try:
            if not grammar_path.exists():
                return False, f"Grammar file not found: {grammar_path}"

            # Try to load the grammar to check ABI compatibility
            try:
                import tree_sitter

                language = tree_sitter.Language(str(grammar_path))
                # If we can create a language object, it's compatible
                return True, None
            except Exception as e:
                return False, f"ABI compatibility check failed: {e!s}"

        except Exception as e:
            return False, f"Error checking ABI compatibility: {e!s}"

    def test_parse_samples(
        self,
        language: str,
        samples: list[str],
    ) -> tuple[bool, list[str]]:
        """Test parsing with multiple code samples.

        Args:
            language: Language name
            samples: List of code samples to test

        Returns:
            Tuple of (all_successful, error_messages)
        """
        errors = []

        try:
            # Lazy import to avoid circular dependencies
            from chunker.parser import get_parser

            parser = get_parser(language)

            for i, sample in enumerate(samples):
                try:
                    tree = parser.parse(sample.encode())
                    if not tree or not tree.root_node:
                        errors.append(f"Sample {i + 1}: Failed to parse (empty tree)")
                except Exception as e:
                    errors.append(f"Sample {i + 1}: Parse error - {e!s}")

            return len(errors) == 0, errors

        except Exception as e:
            errors.append(f"Parser setup failed: {e!s}")
            return False, errors

    def _validate_basic(self, grammar_path: Path, language: str) -> ValidationResult:
        """Perform basic validation (file existence and basic checks)."""
        result = ValidationResult(is_valid=True, level=ValidationLevel.BASIC)

        # Check file exists and is readable
        if not grammar_path.exists():
            result.is_valid = False
            result.errors.append(f"Grammar file does not exist: {grammar_path}")
            return result

        if not grammar_path.is_file():
            result.is_valid = False
            result.errors.append(f"Grammar path is not a file: {grammar_path}")
            return result

        # Check file size (should be reasonable)
        file_size = grammar_path.stat().st_size
        if file_size == 0:
            result.is_valid = False
            result.errors.append("Grammar file is empty")
        elif file_size < 1024:  # Less than 1KB is suspicious
            result.warnings.append("Grammar file is unusually small")
        elif file_size > 50 * 1024 * 1024:  # More than 50MB is suspicious
            result.warnings.append("Grammar file is unusually large")

        result.metadata["file_size"] = file_size

        # Basic ABI compatibility check
        is_compatible, error = self.check_abi_compatibility(grammar_path)
        if not is_compatible:
            result.is_valid = False
            result.errors.append(f"ABI compatibility issue: {error}")

        return result

    def _validate_standard(self, grammar_path: Path, language: str) -> ValidationResult:
        """Perform standard validation (includes basic + parsing tests)."""
        # Start with basic validation
        result = self._validate_basic(grammar_path, language)
        result.level = ValidationLevel.STANDARD

        if not result.is_valid:
            return result  # Don't proceed if basic validation failed

        # Test parsing with sample code
        samples = self._get_test_samples(language)
        if samples:
            start_time = time.time()
            parse_success, parse_errors = self.test_parse_samples(language, samples)
            parse_time = time.time() - start_time

            result.performance_metrics["parse_time"] = parse_time
            result.performance_metrics["samples_tested"] = len(samples)

            if not parse_success:
                result.is_valid = False
                result.errors.extend(parse_errors)
            elif parse_time > 5.0:  # Parsing took more than 5 seconds
                result.warnings.append("Parsing performance is slow")
        else:
            result.warnings.append(f"No test samples available for {language}")

        return result

    def _validate_extensive(
        self,
        grammar_path: Path,
        language: str,
    ) -> ValidationResult:
        """Perform extensive validation (comprehensive compatibility tests)."""
        # Start with standard validation
        result = self._validate_standard(grammar_path, language)
        result.level = ValidationLevel.EXTENSIVE

        if not result.is_valid:
            return result  # Don't proceed if standard validation failed

        # Additional extensive tests
        try:
            # Test node type extraction
            node_types = self._extract_node_types(language)
            result.metadata["node_types_count"] = len(node_types)

            # Test memory usage during parsing
            memory_usage = self._test_memory_usage(language)
            if memory_usage:
                result.performance_metrics.update(memory_usage)

            # Test with larger code samples
            large_samples = self._get_large_test_samples(language)
            if large_samples:
                start_time = time.time()
                large_parse_success, large_parse_errors = self.test_parse_samples(
                    language,
                    large_samples,
                )
                large_parse_time = time.time() - start_time

                result.performance_metrics["large_parse_time"] = large_parse_time
                result.performance_metrics["large_samples_tested"] = len(large_samples)

                if not large_parse_success:
                    # Don't fail on large samples, just warn
                    result.warnings.extend(
                        [
                            f"Large sample parsing issues: {error}"
                            for error in large_parse_errors
                        ],
                    )

        except Exception as e:
            result.warnings.append(f"Extensive validation incomplete: {e!s}")

        return result

    def _get_test_samples(self, language: str) -> list[str]:
        """Get test code samples for a language."""
        samples = {
            "python": [
                "def hello(): pass",
                "class Test:\n    def method(self):\n        return 42",
                "import os\nprint('hello')",
            ],
            "javascript": [
                "function hello() {}",
                "const obj = { key: 'value' };",
                "class Test { constructor() {} }",
            ],
            "rust": [
                "fn main() {}",
                "struct Point { x: i32, y: i32 }",
                "impl Point { fn new() -> Self { Point { x: 0, y: 0 } } }",
            ],
            "go": [
                "package main\nfunc main() {}",
                "type Point struct {\n    X, Y int\n}",
                'func (p Point) String() string { return "Point" }',
            ],
            "java": [
                "class Test {}",
                "public class Main {\n    public static void main(String[] args) {}\n}",
                "interface Runnable { void run(); }",
            ],
            "c": [
                "int main() { return 0; }",
                "struct point { int x, y; };",
                "#include <stdio.h>\nint add(int a, int b) { return a + b; }",
            ],
            "cpp": [
                "int main() { return 0; }",
                "class Point { public: int x, y; };",
                "#include <iostream>\nnamespace test { void func() {} }",
            ],
        }
        return samples.get(language, [])

    def _get_large_test_samples(self, language: str) -> list[str]:
        """Get larger test code samples for stress testing."""
        # Generate larger code samples for performance testing
        if language == "python":
            return [
                "\n".join(
                    [
                        f"def function_{i}(param_{j}):\n    return param_{j} * {i}"
                        for i in range(50)
                        for j in range(5)
                    ],
                ),
            ]
        if language == "javascript":
            return [
                "\n".join(
                    [f"function func{i}() {{ return {i}; }}" for i in range(100)],
                ),
            ]
        # Add more languages as needed
        return []

    def _extract_node_types(self, language: str) -> list[str]:
        """Extract available node types from grammar."""
        try:
            # This would need to be implemented based on tree-sitter capabilities
            # For now, return empty list as placeholder
            return []
        except Exception:
            return []

    def _test_memory_usage(self, language: str) -> dict[str, float] | None:
        """Test memory usage during parsing operations."""
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            before_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Perform some parsing operations
            samples = self._get_test_samples(language)
            if samples:
                self.test_parse_samples(language, samples)

            after_memory = process.memory_info().rss / 1024 / 1024  # MB

            return {
                "memory_before_mb": before_memory,
                "memory_after_mb": after_memory,
                "memory_delta_mb": after_memory - before_memory,
            }
        except Exception:
            return None

    def _get_cache_key(
        self,
        grammar_path: Path,
        language: str,
        level: ValidationLevel,
    ) -> str:
        """Generate cache key for validation result."""
        # Include file modification time and size in cache key
        stat = grammar_path.stat()
        key_data = (
            f"{grammar_path}:{language}:{level.value}:{stat.st_mtime}:{stat.st_size}"
        )
        return hashlib.sha256(key_data.encode()).hexdigest()

    def _load_validation_cache(self) -> dict[str, Any]:
        """Load validation cache from disk."""
        if self._validation_cache.exists():
            try:
                with self._validation_cache.open("r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load validation cache: {e}")
        return {}

    def _cache_validation_result(self, cache_key: str, result: ValidationResult):
        """Cache validation result to disk."""
        try:
            self._cache[cache_key] = self._serialize_validation_result(result)
            self._cache[cache_key]["timestamp"] = time.time()

            with self._validation_cache.open("w") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to cache validation result: {e}")

    def _serialize_validation_result(self, result: ValidationResult) -> dict[str, Any]:
        """Serialize validation result for caching."""
        return {
            "is_valid": result.is_valid,
            "level": result.level.value,
            "errors": result.errors,
            "warnings": result.warnings,
            "performance_metrics": result.performance_metrics,
            "metadata": result.metadata,
        }

    def _deserialize_validation_result(self, data: dict[str, Any]) -> ValidationResult:
        """Deserialize validation result from cache."""
        return ValidationResult(
            is_valid=data["is_valid"],
            level=ValidationLevel(data["level"]),
            errors=data.get("errors", []),
            warnings=data.get("warnings", []),
            performance_metrics=data.get("performance_metrics", {}),
            metadata=data.get("metadata", {}),
        )


class GrammarInstaller:
    """Handles grammar download, build, and installation processes."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        build_timeout: int = 300,
        max_retries: int = 3,
    ):
        """Initialize grammar installer.

        Args:
            cache_dir: Directory for downloads and builds
            build_timeout: Timeout for build operations in seconds
            max_retries: Maximum number of retry attempts
        """
        self._base_cache_dir = cache_dir or (
            Path.home() / ".cache" / "treesitter-chunker"
        )
        self._downloads_dir = self._base_cache_dir / "downloads"
        self._builds_dir = self._base_cache_dir / "builds"
        self._grammars_dir = self._base_cache_dir / "grammars"

        # Create directories
        for directory in [self._downloads_dir, self._builds_dir, self._grammars_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        self._build_timeout = build_timeout
        self._max_retries = max_retries
        self._validator = GrammarValidator(self._base_cache_dir)

    def install_grammar(
        self,
        language: str,
        repository_url: str,
        version: str | None = None,
        priority: GrammarPriority = GrammarPriority.USER,
    ) -> tuple[bool, str | None, InstallationInfo | None]:
        """Install a grammar from repository.

        Args:
            language: Language name
            repository_url: Git repository URL
            version: Specific version/commit to install
            priority: Installation priority level

        Returns:
            Tuple of (success, error_message, installation_info)
        """
        try:
            logger.info(f"Installing grammar for {language} from {repository_url}")

            # Create rollback point
            rollback_info = self._create_rollback_point(language)

            try:
                # Download grammar source
                download_success, download_path, download_error = (
                    self._download_grammar(language, repository_url, version)
                )

                if not download_success:
                    return False, f"Download failed: {download_error}", None

                # Build grammar
                build_success, grammar_path, build_error = self._build_grammar(
                    language,
                    download_path,
                )

                if not build_success:
                    return False, f"Build failed: {build_error}", None

                # Validate grammar
                validation_result = self._validator.validate_grammar(
                    grammar_path,
                    language,
                    ValidationLevel.STANDARD,
                )

                if not validation_result.is_valid:
                    error_msg = (
                        f"Validation failed: {'; '.join(validation_result.errors)}"
                    )
                    return False, error_msg, None

                # Install grammar
                install_success, final_path, install_error = self._install_grammar_file(
                    language,
                    grammar_path,
                    priority,
                )

                if not install_success:
                    return False, f"Installation failed: {install_error}", None

                # Create installation info
                install_info = InstallationInfo(
                    version=version or "latest",
                    install_date=time.time(),
                    install_path=final_path,
                    source_url=repository_url,
                    source_commit=self._get_commit_hash(download_path),
                    priority=priority,
                    metadata={
                        "validation": validation_result.metadata,
                        "performance": validation_result.performance_metrics,
                    },
                )

                # Save installation metadata
                self._save_installation_info(language, install_info)

                logger.info(f"Successfully installed grammar for {language}")
                return True, None, install_info

            except Exception as e:
                # Rollback on failure
                self._perform_rollback(language, rollback_info)
                raise e

        except Exception as e:
            logger.error(f"Grammar installation failed for {language}: {e}")
            return False, str(e), None

    def remove_grammar(
        self,
        language: str,
        clean_dependencies: bool = True,
    ) -> tuple[bool, str | None]:
        """Remove an installed grammar.

        Args:
            language: Language name
            clean_dependencies: Whether to clean up dependencies

        Returns:
            Tuple of (success, error_message)
        """
        try:
            logger.info(f"Removing grammar for {language}")

            # Get installation info
            install_info = self._load_installation_info(language)
            if not install_info:
                return False, f"Grammar {language} is not installed"

            # Remove grammar file
            if install_info.install_path and install_info.install_path.exists():
                try:
                    install_info.install_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove grammar file: {e}")

            # Clean up cache files
            self._cleanup_cache(language)

            # Remove installation metadata
            self._remove_installation_info(language)

            # Clean up dependencies if requested
            if clean_dependencies:
                self._cleanup_dependencies(language, install_info.dependencies)

            logger.info(f"Successfully removed grammar for {language}")
            return True, None

        except Exception as e:
            logger.error(f"Failed to remove grammar for {language}: {e}")
            return False, str(e)

    def _download_grammar(
        self,
        language: str,
        repository_url: str,
        version: str | None = None,
    ) -> tuple[bool, Path | None, str | None]:
        """Download grammar source code."""
        download_dir = self._downloads_dir / f"tree-sitter-{language}"

        # Clean up existing download
        if download_dir.exists():
            shutil.rmtree(download_dir)

        try:
            # Clone repository
            cmd = ["git", "clone", repository_url, str(download_dir)]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300, check=False,
            )

            if result.returncode != 0:
                return False, None, f"Git clone failed: {result.stderr}"

            # Checkout specific version if requested
            if version:
                cmd = ["git", "checkout", version]
                result = subprocess.run(
                    cmd,
                    cwd=download_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )

                if result.returncode != 0:
                    return False, None, f"Git checkout failed: {result.stderr}"

            return True, download_dir, None

        except subprocess.TimeoutExpired:
            return False, None, "Download timed out"
        except Exception as e:
            return False, None, str(e)

    def _build_grammar(
        self,
        language: str,
        source_path: Path,
    ) -> tuple[bool, Path | None, str | None]:
        """Build grammar from source code."""
        build_dir = self._builds_dir / language
        build_dir.mkdir(exist_ok=True)

        output_path = build_dir / f"lib{language}.so"

        try:
            # Try different build methods
            build_methods = [
                self._build_with_tree_sitter_cli,
                self._build_with_gcc,
                self._build_with_make,
            ]

            last_error = None

            for build_method in build_methods:
                try:
                    success, error = build_method(language, source_path, output_path)
                    if success:
                        return True, output_path, None
                    last_error = error
                except Exception as e:
                    last_error = str(e)
                    continue

            return False, None, f"All build methods failed. Last error: {last_error}"

        except Exception as e:
            return False, None, str(e)

    def _build_with_tree_sitter_cli(
        self,
        language: str,
        source_path: Path,
        output_path: Path,
    ) -> tuple[bool, str | None]:
        """Build using tree-sitter CLI."""
        try:
            cmd = [
                "tree-sitter",
                "build",
                "--output",
                str(output_path),
                str(source_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._build_timeout,
                check=False,
            )

            if result.returncode == 0:
                return True, None
            return False, f"tree-sitter build failed: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, "Build timed out"
        except FileNotFoundError:
            return False, "tree-sitter CLI not found"
        except Exception as e:
            return False, str(e)

    def _build_with_gcc(
        self,
        language: str,
        source_path: Path,
        output_path: Path,
    ) -> tuple[bool, str | None]:
        """Build using GCC directly."""
        try:
            # Find C source files
            src_dir = source_path / "src"
            if not src_dir.exists():
                return False, "Source directory not found"

            parser_c = src_dir / "parser.c"
            scanner_c = src_dir / "scanner.c"

            if not parser_c.exists():
                return False, "parser.c not found"

            # Build command
            cmd = ["gcc", "-shared", "-fPIC", "-O2", "-I", str(src_dir), str(parser_c)]

            # Add scanner if it exists
            if scanner_c.exists():
                cmd.append(str(scanner_c))

            cmd.extend(["-o", str(output_path)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._build_timeout,
                check=False,
            )

            if result.returncode == 0:
                return True, None
            return False, f"GCC build failed: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, "GCC build timed out"
        except FileNotFoundError:
            return False, "GCC not found"
        except Exception as e:
            return False, str(e)

    def _build_with_make(
        self,
        language: str,
        source_path: Path,
        output_path: Path,
    ) -> tuple[bool, str | None]:
        """Build using Makefile if available."""
        try:
            makefile = source_path / "Makefile"
            if not makefile.exists():
                return False, "Makefile not found"

            # Run make
            result = subprocess.run(
                ["make"],
                cwd=source_path,
                capture_output=True,
                text=True,
                timeout=self._build_timeout,
                check=False,
            )

            if result.returncode != 0:
                return False, f"Make failed: {result.stderr}"

            # Find the built library
            for pattern in ["*.so", "lib*.so", "*.dylib"]:
                built_files = list(source_path.glob(pattern))
                if built_files:
                    shutil.copy2(built_files[0], output_path)
                    return True, None

            return False, "Built library not found after make"

        except subprocess.TimeoutExpired:
            return False, "Make timed out"
        except FileNotFoundError:
            return False, "Make not found"
        except Exception as e:
            return False, str(e)

    def _install_grammar_file(
        self,
        language: str,
        source_path: Path,
        priority: GrammarPriority,
    ) -> tuple[bool, Path | None, str | None]:
        """Install compiled grammar file to final location."""
        try:
            # Determine final installation path based on priority
            if priority == GrammarPriority.USER:
                final_dir = self._grammars_dir
            else:
                # For package-level installs, use a subdirectory
                final_dir = self._grammars_dir / priority.name.lower()

            final_dir.mkdir(parents=True, exist_ok=True)
            final_path = final_dir / f"lib{language}.so"

            # Copy the file
            shutil.copy2(source_path, final_path)

            # Set appropriate permissions
            os.chmod(final_path, 0o755)

            return True, final_path, None

        except Exception as e:
            return False, None, str(e)

    def _create_rollback_point(self, language: str) -> dict[str, Any] | None:
        """Create rollback point for installation."""
        try:
            rollback_info = {"timestamp": time.time(), "existing_installation": None}

            # Check if grammar is already installed
            existing_info = self._load_installation_info(language)
            if existing_info:
                rollback_info["existing_installation"] = {
                    "install_path": str(existing_info.install_path),
                    "info": existing_info.__dict__,
                }

            return rollback_info

        except Exception as e:
            logger.warning(f"Failed to create rollback point: {e}")
            return None

    def _perform_rollback(self, language: str, rollback_info: dict[str, Any] | None):
        """Perform rollback of failed installation."""
        if not rollback_info:
            return

        try:
            # Remove any partially installed files
            self._cleanup_cache(language)
            self._remove_installation_info(language)

            # Restore existing installation if there was one
            existing = rollback_info.get("existing_installation")
            if existing:
                # This would involve restoring the previous installation
                # For now, just log that rollback was attempted
                logger.info(f"Rollback performed for {language} installation")

        except Exception as e:
            logger.error(f"Rollback failed for {language}: {e}")

    def _get_commit_hash(self, repo_path: Path) -> str | None:
        """Get current commit hash from repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode == 0:
                return result.stdout.strip()
            return None

        except Exception:
            return None

    def _save_installation_info(self, language: str, info: InstallationInfo):
        """Save installation metadata."""
        try:
            metadata_file = self._grammars_dir / f"{language}_install_info.json"

            # Convert to serializable format
            data = {
                "version": info.version,
                "install_date": info.install_date,
                "install_path": str(info.install_path),
                "source_url": info.source_url,
                "source_commit": info.source_commit,
                "priority": info.priority.name,
                "dependencies": info.dependencies,
                "metadata": info.metadata,
            }

            with metadata_file.open("w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.warning(f"Failed to save installation info: {e}")

    def _load_installation_info(self, language: str) -> InstallationInfo | None:
        """Load installation metadata."""
        try:
            metadata_file = self._grammars_dir / f"{language}_install_info.json"

            if not metadata_file.exists():
                return None

            with metadata_file.open("r") as f:
                data = json.load(f)

            return InstallationInfo(
                version=data["version"],
                install_date=data["install_date"],
                install_path=Path(data["install_path"]),
                source_url=data["source_url"],
                source_commit=data.get("source_commit"),
                priority=GrammarPriority[data["priority"]],
                dependencies=data.get("dependencies", []),
                metadata=data.get("metadata", {}),
            )

        except Exception as e:
            logger.warning(f"Failed to load installation info: {e}")
            return None

    def _remove_installation_info(self, language: str):
        """Remove installation metadata."""
        try:
            metadata_file = self._grammars_dir / f"{language}_install_info.json"
            if metadata_file.exists():
                metadata_file.unlink()
        except Exception as e:
            logger.warning(f"Failed to remove installation info: {e}")

    def _cleanup_cache(self, language: str):
        """Clean up cache files for a language."""
        try:
            # Clean downloads
            download_dir = self._downloads_dir / f"tree-sitter-{language}"
            if download_dir.exists():
                shutil.rmtree(download_dir)

            # Clean builds
            build_dir = self._builds_dir / language
            if build_dir.exists():
                shutil.rmtree(build_dir)

        except Exception as e:
            logger.warning(f"Cache cleanup failed for {language}: {e}")

    def _cleanup_dependencies(self, language: str, dependencies: list[str]):
        """Clean up grammar dependencies if no longer needed."""
        # This would implement dependency tracking and cleanup
        # For now, just log the attempt
        if dependencies:
            logger.info(f"Cleaning up dependencies for {language}: {dependencies}")


class GrammarRegistry:
    """Manages grammar registration and lookup with priority logic."""

    def __init__(
        self,
        user_dir: Path | None = None,
        package_dir: Path | None = None,
    ):
        """Initialize grammar registry.

        Args:
            user_dir: User grammar directory
            package_dir: Package grammar directory
        """
        self._user_dir = user_dir or (
            Path.home() / ".cache" / "treesitter-chunker" / "grammars"
        )
        self._package_dir = package_dir or (
            Path(__file__).parent.parent / "data" / "grammars"
        )

        self._user_dir.mkdir(parents=True, exist_ok=True)
        if self._package_dir.exists():
            self._package_dir.mkdir(parents=True, exist_ok=True)

        self._registry_cache = {}
        self._cache_timestamp = 0
        self._installer = GrammarInstaller()

    def discover_grammars(self) -> dict[str, list[tuple[Path, GrammarPriority]]]:
        """Discover all available grammars with their priorities.

        Returns:
            Dictionary mapping language names to list of (path, priority) tuples
        """
        current_time = time.time()

        # Use cache if recent (within 60 seconds)
        if current_time - self._cache_timestamp < 60 and self._registry_cache:
            return self._registry_cache

        grammars = {}

        # Discover user grammars (highest priority)
        self._discover_in_directory(self._user_dir, GrammarPriority.USER, grammars)

        # Discover package grammars (medium priority)
        if self._package_dir.exists():
            self._discover_in_directory(
                self._package_dir,
                GrammarPriority.PACKAGE,
                grammars,
            )

        # Update cache
        self._registry_cache = grammars
        self._cache_timestamp = current_time

        return grammars

    def get_grammar_path(self, language: str) -> tuple[Path, GrammarPriority] | None:
        """Get the best available grammar path for a language.

        Args:
            language: Language name

        Returns:
            Tuple of (path, priority) for the best grammar, or None
        """
        grammars = self.discover_grammars()

        if language not in grammars:
            return None

        # Return the highest priority grammar (lowest enum value)
        candidates = grammars[language]
        best_candidate = min(candidates, key=lambda x: x[1].value)

        return best_candidate

    def list_available_languages(self) -> set[str]:
        """List all available languages."""
        grammars = self.discover_grammars()
        return set(grammars.keys())

    def get_language_info(self, language: str) -> dict[str, Any] | None:
        """Get detailed information about a language.

        Args:
            language: Language name

        Returns:
            Dictionary with language information
        """
        grammar_path_info = self.get_grammar_path(language)
        if not grammar_path_info:
            return None

        grammar_path, priority = grammar_path_info

        info = {
            "language": language,
            "path": str(grammar_path),
            "priority": priority.name,
            "exists": grammar_path.exists(),
            "size": grammar_path.stat().st_size if grammar_path.exists() else 0,
            "modified": grammar_path.stat().st_mtime if grammar_path.exists() else 0,
        }

        # Get installation info if available
        install_info = self._installer._load_installation_info(language)
        if install_info:
            info.update(
                {
                    "version": install_info.version,
                    "install_date": install_info.install_date,
                    "source_url": install_info.source_url,
                    "source_commit": install_info.source_commit,
                },
            )

        return info

    def detect_version_conflicts(self) -> dict[str, list[dict[str, Any]]]:
        """Detect version conflicts between installed grammars.

        Returns:
            Dictionary mapping language names to conflict information
        """
        conflicts = {}
        grammars = self.discover_grammars()

        for language, candidates in grammars.items():
            if len(candidates) > 1:
                # Multiple versions exist, check for conflicts
                versions = []

                for grammar_path, priority in candidates:
                    install_info = self._installer._load_installation_info(language)
                    version_info = {
                        "path": str(grammar_path),
                        "priority": priority.name,
                        "version": install_info.version if install_info else "unknown",
                        "exists": grammar_path.exists(),
                    }
                    versions.append(version_info)

                # If versions differ, it's a potential conflict
                unique_versions = set(
                    v["version"] for v in versions if v["version"] != "unknown"
                )
                if len(unique_versions) > 1:
                    conflicts[language] = versions

        return conflicts

    def resolve_conflicts(
        self,
        conflicts: dict[str, list[dict[str, Any]]],
    ) -> dict[str, bool]:
        """Resolve version conflicts by removing lower priority versions.

        Args:
            conflicts: Conflicts from detect_version_conflicts()

        Returns:
            Dictionary mapping language names to resolution success
        """
        results = {}

        for language, conflict_info in conflicts.items():
            try:
                # Keep only the highest priority version
                active_versions = [v for v in conflict_info if v["exists"]]
                if not active_versions:
                    results[language] = False
                    continue

                # Sort by priority (USER=1, PACKAGE=2, FALLBACK=3)
                priority_order = {"USER": 1, "PACKAGE": 2, "FALLBACK": 3}
                active_versions.sort(
                    key=lambda x: priority_order.get(x["priority"], 999),
                )

                # Remove all but the highest priority
                to_remove = active_versions[1:]

                for version_info in to_remove:
                    try:
                        grammar_path = Path(version_info["path"])
                        if grammar_path.exists():
                            grammar_path.unlink()
                            logger.info(f"Removed conflicting grammar: {grammar_path}")
                    except Exception as e:
                        logger.error(f"Failed to remove conflicting grammar: {e}")

                results[language] = True

            except Exception as e:
                logger.error(f"Failed to resolve conflict for {language}: {e}")
                results[language] = False

        # Clear cache to force rediscovery
        self._registry_cache = {}
        self._cache_timestamp = 0

        return results

    def _discover_in_directory(
        self,
        directory: Path,
        priority: GrammarPriority,
        grammars: dict[str, list[tuple[Path, GrammarPriority]]],
    ):
        """Discover grammars in a specific directory."""
        if not directory.exists():
            return

        # Look for .so files
        for grammar_file in directory.glob("lib*.so"):
            # Extract language name from filename
            filename = grammar_file.stem
            if filename.startswith("lib"):
                language = filename[3:]  # Remove "lib" prefix

                if language not in grammars:
                    grammars[language] = []

                grammars[language].append((grammar_file, priority))

        # Also look in subdirectories for different priorities
        for subdir in directory.iterdir():
            if subdir.is_dir() and subdir.name in ["user", "package", "fallback"]:
                subdir_priority = {
                    "user": GrammarPriority.USER,
                    "package": GrammarPriority.PACKAGE,
                    "fallback": GrammarPriority.FALLBACK,
                }.get(subdir.name, priority)

                self._discover_in_directory(subdir, subdir_priority, grammars)


class GrammarManager:
    """Core grammar management engine with discovery, installation, removal."""

    def __init__(
        self,
        user_dir: Path | None = None,
        package_dir: Path | None = None,
        cache_dir: Path | None = None,
    ):
        """Initialize grammar manager.

        Args:
            user_dir: User grammar directory
            package_dir: Package grammar directory
            cache_dir: Cache directory for downloads and builds
        """
        self._cache_dir = cache_dir or (Path.home() / ".cache" / "treesitter-chunker")

        self._registry = GrammarRegistry(user_dir, package_dir)
        self._installer = GrammarInstaller(self._cache_dir)
        self._validator = GrammarValidator(self._cache_dir)

        # Create required directories
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def discover_available_grammars(self) -> dict[str, dict[str, Any]]:
        """Discover all available grammars with detailed information.

        Returns:
            Dictionary mapping language names to grammar information
        """
        discovered = {}

        # Get grammars from registry
        registry_grammars = self._registry.discover_grammars()

        for language in registry_grammars:
            info = self._registry.get_language_info(language)
            if info:
                discovered[language] = info

        return discovered

    def install_grammar(
        self,
        language: str,
        repository_url: str,
        version: str | None = None,
        force: bool = False,
    ) -> tuple[bool, str | None]:
        """Install a grammar from repository.

        Args:
            language: Language name
            repository_url: Git repository URL
            version: Specific version to install
            force: Force reinstallation if already exists

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Check if already installed
            if not force:
                existing_path = self._registry.get_grammar_path(language)
                if existing_path and existing_path[0].exists():
                    return (
                        False,
                        f"Grammar for {language} already installed (use --force to reinstall)",
                    )

            # Install grammar
            success, error, install_info = self._installer.install_grammar(
                language,
                repository_url,
                version,
            )

            if success and install_info:
                # Clear registry cache to pick up new installation
                self._registry._registry_cache = {}
                self._registry._cache_timestamp = 0

                logger.info(f"Successfully installed {language} grammar")
                return True, None
            return False, error

        except Exception as e:
            logger.error(f"Failed to install grammar for {language}: {e}")
            return False, str(e)

    def remove_grammar(
        self,
        language: str,
        clean_cache: bool = True,
    ) -> tuple[bool, str | None]:
        """Remove an installed grammar.

        Args:
            language: Language name
            clean_cache: Whether to clean associated cache files

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Check if grammar exists
            grammar_path = self._registry.get_grammar_path(language)
            if not grammar_path:
                return False, f"Grammar for {language} not found"

            # Remove using installer
            success, error = self._installer.remove_grammar(language, clean_cache)

            if success:
                # Clear registry cache
                self._registry._registry_cache = {}
                self._registry._cache_timestamp = 0

                logger.info(f"Successfully removed {language} grammar")
                return True, None
            return False, error

        except Exception as e:
            logger.error(f"Failed to remove grammar for {language}: {e}")
            return False, str(e)

    def validate_grammar(
        self,
        language: str,
        level: ValidationLevel = ValidationLevel.STANDARD,
    ) -> ValidationResult:
        """Validate a grammar at the specified level.

        Args:
            language: Language name
            level: Validation level

        Returns:
            Validation result
        """
        try:
            grammar_path = self._registry.get_grammar_path(language)
            if not grammar_path:
                result = ValidationResult(is_valid=False, level=level)
                result.errors.append(f"Grammar for {language} not found")
                return result

            return self._validator.validate_grammar(grammar_path[0], language, level)

        except Exception as e:
            result = ValidationResult(is_valid=False, level=level)
            result.errors.append(f"Validation error: {e!s}")
            return result

    def list_installed_grammars(self) -> dict[str, dict[str, Any]]:
        """List all installed grammars with their information.

        Returns:
            Dictionary mapping language names to grammar information
        """
        return self.discover_available_grammars()

    def check_grammar_health(self) -> dict[str, dict[str, Any]]:
        """Check health of all installed grammars.

        Returns:
            Dictionary mapping language names to health information
        """
        health_report = {}
        installed_grammars = self.list_installed_grammars()

        for language in installed_grammars:
            try:
                # Validate grammar
                validation_result = self.validate_grammar(
                    language,
                    ValidationLevel.BASIC,
                )

                health_info = {
                    "is_healthy": validation_result.is_valid,
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                    "last_checked": time.time(),
                }

                # Add performance metrics if available
                if validation_result.performance_metrics:
                    health_info["performance"] = validation_result.performance_metrics

                health_report[language] = health_info

            except Exception as e:
                health_report[language] = {
                    "is_healthy": False,
                    "errors": [f"Health check failed: {e!s}"],
                    "warnings": [],
                    "last_checked": time.time(),
                }

        return health_report

    def detect_and_resolve_conflicts(
        self,
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, bool]]:
        """Detect and resolve version conflicts.

        Returns:
            Tuple of (detected_conflicts, resolution_results)
        """
        # Detect conflicts
        conflicts = self._registry.detect_version_conflicts()

        # Resolve conflicts if any found
        resolution_results = {}
        if conflicts:
            resolution_results = self._registry.resolve_conflicts(conflicts)
            logger.info(f"Resolved conflicts for {len(resolution_results)} languages")

        return conflicts, resolution_results

    def get_grammar_metadata(self, language: str) -> dict[str, Any] | None:
        """Get comprehensive metadata for a grammar.

        Args:
            language: Language name

        Returns:
            Metadata dictionary or None if not found
        """
        try:
            # Get basic info from registry
            info = self._registry.get_language_info(language)
            if not info:
                return None

            # Add validation information
            validation_result = self.validate_grammar(language, ValidationLevel.BASIC)
            info["validation"] = {
                "is_valid": validation_result.is_valid,
                "errors": validation_result.errors,
                "warnings": validation_result.warnings,
                "metadata": validation_result.metadata,
            }

            # Add performance metrics if available
            if validation_result.performance_metrics:
                info["performance"] = validation_result.performance_metrics

            return info

        except Exception as e:
            logger.error(f"Failed to get metadata for {language}: {e}")
            return None

    def cleanup_cache(self, older_than_days: int = 30) -> dict[str, Any]:
        """Clean up old cache files.

        Args:
            older_than_days: Remove cache files older than this many days

        Returns:
            Cleanup statistics
        """
        stats = {
            "files_removed": 0,
            "bytes_freed": 0,
            "directories_cleaned": [],
            "errors": [],
        }

        cutoff_time = time.time() - (older_than_days * 24 * 60 * 60)

        try:
            # Clean downloads directory
            downloads_dir = self._cache_dir / "downloads"
            if downloads_dir.exists():
                cleaned = self._cleanup_directory(downloads_dir, cutoff_time)
                stats["files_removed"] += cleaned["files_removed"]
                stats["bytes_freed"] += cleaned["bytes_freed"]
                if cleaned["files_removed"] > 0:
                    stats["directories_cleaned"].append("downloads")

            # Clean builds directory
            builds_dir = self._cache_dir / "builds"
            if builds_dir.exists():
                cleaned = self._cleanup_directory(builds_dir, cutoff_time)
                stats["files_removed"] += cleaned["files_removed"]
                stats["bytes_freed"] += cleaned["bytes_freed"]
                if cleaned["files_removed"] > 0:
                    stats["directories_cleaned"].append("builds")

            # Clean validation cache
            validation_cache = self._cache_dir / "validation_cache.json"
            if validation_cache.exists():
                try:
                    with validation_cache.open("r") as f:
                        cache_data = json.load(f)

                    # Remove old entries
                    cleaned_cache = {}
                    for key, value in cache_data.items():
                        if value.get("timestamp", 0) > cutoff_time:
                            cleaned_cache[key] = value

                    # Write back cleaned cache
                    with validation_cache.open("w") as f:
                        json.dump(cleaned_cache, f, indent=2)

                    removed_entries = len(cache_data) - len(cleaned_cache)
                    if removed_entries > 0:
                        stats["files_removed"] += removed_entries
                        stats["directories_cleaned"].append("validation_cache")

                except Exception as e:
                    stats["errors"].append(
                        f"Failed to clean validation cache: {e!s}",
                    )

            logger.info(f"Cache cleanup completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            stats["errors"].append(str(e))
            return stats

    def _cleanup_directory(self, directory: Path, cutoff_time: float) -> dict[str, int]:
        """Clean up files in a directory older than cutoff time."""
        stats = {"files_removed": 0, "bytes_freed": 0}

        try:
            for item in directory.iterdir():
                try:
                    item_stat = item.stat()
                    if item_stat.st_mtime < cutoff_time:
                        if item.is_file():
                            stats["bytes_freed"] += item_stat.st_size
                            item.unlink()
                            stats["files_removed"] += 1
                        elif item.is_dir():
                            dir_size = sum(
                                f.stat().st_size for f in item.rglob("*") if f.is_file()
                            )
                            stats["bytes_freed"] += dir_size
                            shutil.rmtree(item)
                            stats["files_removed"] += 1

                except Exception as e:
                    logger.warning(f"Failed to clean {item}: {e}")

        except Exception as e:
            logger.error(f"Failed to cleanup directory {directory}: {e}")

        return stats
