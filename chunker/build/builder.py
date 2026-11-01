"""
Build System implementation for cross-platform grammar compilation
"""

import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from configparser import ConfigParser
from email.parser import Parser
from pathlib import Path, PurePosixPath
from typing import Any

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import Tag, parse_tag
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

from chunker.contracts.build_contract import BuildSystemContract

from .platform import PlatformSupport


_WHEEL_PAYLOAD_VERSION = "6.0.0"
# Shared by both wheel-building paths; keep in step with pyproject requires-python.
_WHEEL_REQUIRES_PYTHON = ">=3.12"
_REQUIRED_WHEEL_PAYLOAD = frozenset(
    {
        "chunker/__init__.py",
        "chunker/_internal/__init__.py",
        "chunker/_internal/cache.py",
        "chunker/_internal/error_handling.py",
        "chunker/_internal/factory.py",
        "chunker/_internal/file_utils.py",
        "chunker/_internal/gc_tuning.py",
        "chunker/_internal/grammar_management.py",
        "chunker/_internal/language_pack.py",
        "chunker/_internal/native_admission.py",
        "chunker/_internal/pack_pin.py",
        "chunker/_internal/package_supplier.py",
        "chunker/_internal/path_confinement.py",
        "chunker/_internal/registry.py",
        "chunker/_internal/trusted_artifacts.py",
        "chunker/_internal/user_grammar_tools.py",
        "chunker/_internal/vfs.py",
        "chunker/_version.py",
        "chunker/analysis/__init__.py",
        "chunker/analysis/complexity.py",
        "chunker/analysis/coupling.py",
        "chunker/analysis/semantics.py",
        "chunker/auto.py",
        "chunker/boundary/__init__.py",
        "chunker/boundary/_canon.py",
        "chunker/boundary/adapter.py",
        "chunker/boundary/boundary_ir.schema.json",
        "chunker/boundary/cache.py",
        "chunker/boundary/identity.py",
        "chunker/boundary/impact.py",
        "chunker/boundary/semantic.py",
        "chunker/boundary/serialization.py",
        "chunker/boundary/types.py",
        "chunker/build/__init__.py",
        "chunker/build/builder.py",
        "chunker/build/platform.py",
        "chunker/build/system.py",
        "chunker/chunker.py",
        "chunker/chunker_config.py",
        "chunker/cli/__init__.py",
        "chunker/cli/__main__.py",
        "chunker/cli/cluster_commands.py",
        "chunker/cli/grammar_commands.py",
        "chunker/cli/symbol_commands.py",
        "chunker/clustering/__init__.py",
        "chunker/clustering/engine.py",
        "chunker/clustering/hierarchy.py",
        "chunker/clustering/metrics.py",
        "chunker/clustering/weights.py",
        "chunker/config/__init__.py",
        "chunker/config/profiles.py",
        "chunker/config/strategy_config.py",
        "chunker/context/__init__.py",
        "chunker/context/extractor.py",
        "chunker/context/factory.py",
        "chunker/context/filter.py",
        "chunker/context/languages/__init__.py",
        "chunker/context/languages/javascript.py",
        "chunker/context/languages/python.py",
        "chunker/context/scope_analyzer.py",
        "chunker/context/symbol_resolver.py",
        "chunker/contracts/__init__.py",
        "chunker/contracts/auto_contract.py",
        "chunker/contracts/auto_stub.py",
        "chunker/contracts/build_contract.py",
        "chunker/contracts/build_stub.py",
        "chunker/contracts/cicd_contract.py",
        "chunker/contracts/cicd_stub.py",
        "chunker/contracts/debug_contract.py",
        "chunker/contracts/debug_stub.py",
        "chunker/contracts/devenv_contract.py",
        "chunker/contracts/discovery_contract.py",
        "chunker/contracts/discovery_stub.py",
        "chunker/contracts/distribution_contract.py",
        "chunker/contracts/distribution_stub.py",
        "chunker/contracts/download_contract.py",
        "chunker/contracts/download_stub.py",
        "chunker/contracts/grammar_manager_contract.py",
        "chunker/contracts/grammar_manager_stub.py",
        "chunker/contracts/language_plugin_contract.py",
        "chunker/contracts/language_plugin_stub.py",
        "chunker/contracts/registry_contract.py",
        "chunker/contracts/registry_stub.py",
        "chunker/contracts/template_generator_contract.py",
        "chunker/contracts/template_generator_stub.py",
        "chunker/contracts/tooling_contract.py",
        "chunker/contracts/tooling_stub.py",
        "chunker/core.py",
        "chunker/debug/__init__.py",
        "chunker/debug/comparison.py",
        "chunker/debug/interactive/__init__.py",
        "chunker/debug/interactive/chunk_debugger.py",
        "chunker/debug/interactive/node_explorer.py",
        "chunker/debug/interactive/query_debugger.py",
        "chunker/debug/interactive/repl.py",
        "chunker/debug/tools/__init__.py",
        "chunker/debug/tools/comparison.py",
        "chunker/debug/tools/visualization.py",
        "chunker/debug/visualization/__init__.py",
        "chunker/debug/visualization/ast_visualizer.py",
        "chunker/debug/visualization/chunk_visualizer.py",
        "chunker/debug/visualization_impl.py",
        "chunker/exceptions.py",
        "chunker/export/__init__.py",
        "chunker/export/boundary_ir.py",
        "chunker/export/database_exporter_base.py",
        "chunker/export/dot_exporter.py",
        "chunker/export/formats/__init__.py",
        "chunker/export/formats/database.py",
        "chunker/export/formats/graph.py",
        "chunker/export/formats/json.py",
        "chunker/export/formats/neo4j.py",
        "chunker/export/formats/parquet.py",
        "chunker/export/formats/semantic_lens.py",
        "chunker/export/formatters.py",
        "chunker/export/graph_exporter_base.py",
        "chunker/export/graphml_exporter.py",
        "chunker/export/graphml_yed_exporter.py",
        "chunker/export/json_export.py",
        "chunker/export/neo4j_exporter.py",
        "chunker/export/postgres_exporter.py",
        "chunker/export/postgres_spec_exporter.py",
        "chunker/export/relationships/__init__.py",
        "chunker/export/relationships/tracker.py",
        "chunker/export/sqlite_exporter.py",
        "chunker/export/structured_exporter.py",
        "chunker/exporters/__init__.py",
        "chunker/exporters/parquet.py",
        "chunker/fallback/__init__.py",
        "chunker/fallback/base.py",
        "chunker/fallback/detection/__init__.py",
        "chunker/fallback/detection/file_type.py",
        "chunker/fallback/fallback_manager.py",
        "chunker/fallback/intelligent_fallback.py",
        "chunker/fallback/offsets.py",
        "chunker/fallback/overlapping.py",
        "chunker/fallback/sliding_window_fallback.py",
        "chunker/fallback/strategies/__init__.py",
        "chunker/fallback/strategies/line_based.py",
        "chunker/fallback/strategies/log_chunker.py",
        "chunker/fallback/strategies/markdown.py",
        "chunker/fallback_overlap/__init__.py",
        "chunker/fallback_overlap/chunker.py",
        "chunker/grammar/__init__.py",
        "chunker/grammar/builder.py",
        "chunker/grammar/discovery.py",
        "chunker/grammar/download.py",
        "chunker/grammar/integrity.py",
        "chunker/grammar/manager.py",
        "chunker/grammar/registry.py",
        "chunker/grammar/repository.py",
        "chunker/grammar/source_validation.py",
        "chunker/grammar/validator.py",
        "chunker/grammar_management/__init__.py",
        "chunker/grammar_management/_transactions.py",
        "chunker/grammar_management/cli.py",
        "chunker/grammar_management/compatibility.py",
        "chunker/grammar_management/config.py",
        "chunker/grammar_management/core.py",
        "chunker/grammar_management/testing.py",
        "chunker/grammar_manager.py",
        "chunker/graph/cut.py",
        "chunker/graph/xref.py",
        "chunker/helpers/nearest_tests.py",
        "chunker/hierarchy/__init__.py",
        "chunker/hierarchy/builder.py",
        "chunker/hierarchy/navigator.py",
        "chunker/incremental.py",
        "chunker/interfaces/__init__.py",
        "chunker/interfaces/base.py",
        "chunker/interfaces/context.py",
        "chunker/interfaces/debug.py",
        "chunker/interfaces/export.py",
        "chunker/interfaces/fallback.py",
        "chunker/interfaces/fallback_overlap.py",
        "chunker/interfaces/grammar.py",
        "chunker/interfaces/hierarchy.py",
        "chunker/interfaces/incremental.py",
        "chunker/interfaces/metadata.py",
        "chunker/interfaces/multi_language.py",
        "chunker/interfaces/optimization.py",
        "chunker/interfaces/performance.py",
        "chunker/interfaces/query.py",
        "chunker/interfaces/query_advanced.py",
        "chunker/interfaces/repo.py",
        "chunker/interfaces/rules.py",
        "chunker/interfaces/semantic.py",
        "chunker/interfaces/smart_context.py",
        "chunker/interfaces/stubs.py",
        "chunker/interfaces/token.py",
        "chunker/languages/__init__.py",
        "chunker/languages/baml.py",
        "chunker/languages/base.py",
        "chunker/languages/c.py",
        "chunker/languages/clojure.py",
        "chunker/languages/compatibility/__init__.py",
        "chunker/languages/compatibility/database.py",
        "chunker/languages/compatibility/grammar_analyzer.py",
        "chunker/languages/compatibility/schema.py",
        "chunker/languages/cpp.py",
        "chunker/languages/cs.py",
        "chunker/languages/cs_plugin.py",
        "chunker/languages/dart.py",
        "chunker/languages/dockerfile.py",
        "chunker/languages/elixir.py",
        "chunker/languages/go.py",
        "chunker/languages/go_plugin.py",
        "chunker/languages/haskell.py",
        "chunker/languages/java.py",
        "chunker/languages/java_plugin.py",
        "chunker/languages/javascript.py",
        "chunker/languages/julia.py",
        "chunker/languages/kotlin.py",
        "chunker/languages/matlab.py",
        "chunker/languages/nasm.py",
        "chunker/languages/normalizers.py",
        "chunker/languages/ocaml.py",
        "chunker/languages/php.py",
        "chunker/languages/plugin_base.py",
        "chunker/languages/python.py",
        "chunker/languages/r.py",
        "chunker/languages/ruby.py",
        "chunker/languages/ruby_plugin.py",
        "chunker/languages/rust.py",
        "chunker/languages/rust_config.py",
        "chunker/languages/scala.py",
        "chunker/languages/sql.py",
        "chunker/languages/svelte.py",
        "chunker/languages/swift.py",
        "chunker/languages/toml.py",
        "chunker/languages/typescript.py",
        "chunker/languages/version_detection/__init__.py",
        "chunker/languages/version_detection/cpp_detector.py",
        "chunker/languages/version_detection/go_detector.py",
        "chunker/languages/version_detection/java_detector.py",
        "chunker/languages/version_detection/javascript_detector.py",
        "chunker/languages/version_detection/python_detector.py",
        "chunker/languages/version_detection/rust_detector.py",
        "chunker/languages/vue.py",
        "chunker/languages/wasm.py",
        "chunker/languages/xml.py",
        "chunker/languages/yaml.py",
        "chunker/languages/zig.py",
        "chunker/metadata/__init__.py",
        "chunker/metadata/extractor.py",
        "chunker/metadata/factory.py",
        "chunker/metadata/languages/__init__.py",
        "chunker/metadata/languages/c.py",
        "chunker/metadata/languages/csharp.py",
        "chunker/metadata/languages/go.py",
        "chunker/metadata/languages/java.py",
        "chunker/metadata/languages/javascript.py",
        "chunker/metadata/languages/kotlin.py",
        "chunker/metadata/languages/php.py",
        "chunker/metadata/languages/python.py",
        "chunker/metadata/languages/ruby.py",
        "chunker/metadata/languages/rust.py",
        "chunker/metadata/languages/signature_only.py",
        "chunker/metadata/languages/swift.py",
        "chunker/metadata/languages/typescript.py",
        "chunker/metadata/metrics.py",
        "chunker/multi_language.py",
        "chunker/optimization.py",
        "chunker/packing.py",
        "chunker/parallel.py",
        "chunker/parser.py",
        "chunker/performance/__init__.py",
        "chunker/performance/cache/__init__.py",
        "chunker/performance/cache/lru.py",
        "chunker/performance/cache/manager.py",
        "chunker/performance/cache/multi_level.py",
        "chunker/performance/core/__init__.py",
        "chunker/performance/core/performance_framework.py",
        "chunker/performance/enhanced_chunker.py",
        "chunker/performance/optimization/__init__.py",
        "chunker/performance/optimization/batch.py",
        "chunker/performance/optimization/incremental.py",
        "chunker/performance/optimization/memory_pool.py",
        "chunker/performance/optimization/monitor.py",
        "chunker/performance/optimization/system_optimizer.py",
        "chunker/plugin_manager.py",
        "chunker/processors/__init__.py",
        "chunker/processors/base.py",
        "chunker/processors/config.py",
        "chunker/processors/logs.py",
        "chunker/processors/markdown.py",
        "chunker/py.typed",
        "chunker/query_advanced.py",
        "chunker/repo/__init__.py",
        "chunker/repo/chunker_adapter.py",
        "chunker/repo/git_aware.py",
        "chunker/repo/patterns.py",
        "chunker/repo/processor.py",
        "chunker/rules/__init__.py",
        "chunker/rules/builtin.py",
        "chunker/rules/comment.py",
        "chunker/rules/custom.py",
        "chunker/rules/engine.py",
        "chunker/rules/regex.py",
        "chunker/semantic/__init__.py",
        "chunker/semantic/analyzer.py",
        "chunker/semantic/merger.py",
        "chunker/semantic_query.py",
        "chunker/sliding_window/__init__.py",
        "chunker/sliding_window/error_safe_adapter.py",
        "chunker/smart_context.py",
        "chunker/strategies/__init__.py",
        "chunker/strategies/adaptive.py",
        "chunker/strategies/composite.py",
        "chunker/strategies/hierarchical.py",
        "chunker/strategies/semantic.py",
        "chunker/streaming.py",
        "chunker/symbol_graph.py",
        "chunker/template_generator.py",
        "chunker/token/__init__.py",
        "chunker/token/chunker.py",
        "chunker/token/counter.py",
        "chunker/tooling/__init__.py",
        "chunker/tooling/developer.py",
        "chunker/types.py",
        "chunker/utils/__init__.py",
        "chunker/utils/ast.py",
        "chunker/utils/json.py",
        "chunker/utils/text.py",
        "chunker/validation/__init__.py",
        "chunker/validation/validation_framework.py",
        "chunker/vfs.py",
        "chunker/vfs_chunker.py",
        "cli/__init__.py",
        "cli/debug/__init__.py",
        "cli/debug/commands.py",
        "cli/main.py",
        "cli/repo_command.py",
        "cli/setup_command.py",
    }
)


def _safe_extract_tar(tar: tarfile.TarFile, destination: Path) -> None:
    """Extract only ordinary files and directories contained by destination.

    Containment is enforced by resolving each member against the destination and
    requiring the result to stay under it. This catches POSIX ``..`` traversal,
    absolute paths, AND Windows drive-qualified members (e.g. ``C:/escaped``) that
    a ``PurePosixPath``-only check would miss — important because the ``filter=``
    fallback below (pre-3.11.4) performs no containment of its own.
    """
    dest_root = destination.resolve()
    members = tar.getmembers()
    for member in members:
        name = member.name.replace("\\", "/")
        member_path = PurePosixPath(name)
        # Reject Windows drive letters (e.g. "C:/x") — not absolute under posix parsing.
        has_drive = len(name) >= 2 and name[1] == ":" and name[0].isalpha()
        if (
            member_path.is_absolute()
            or has_drive
            or ".." in member_path.parts
            or not (member.isfile() or member.isdir())
        ):
            raise ValueError(f"Unsafe tar member: {member.name}")
        # Authoritative guard: the resolved target must stay under destination.
        resolved = (dest_root / member_path).resolve()
        if resolved != dest_root and dest_root not in resolved.parents:
            raise ValueError(f"Tar member escapes destination: {member.name}")
    try:
        tar.extractall(destination, members=members, filter="data")
    except TypeError:
        tar.extractall(destination, members=members)


class BuildSystem(BuildSystemContract):
    """Implementation of cross-platform build system"""

    def __init__(self):
        self.platform_support = PlatformSupport()
        # Find project root by looking for grammars directory
        current = Path(__file__).parent
        while current.parent != current:
            if (current / "grammars").exists():
                self._grammars_dir = current / "grammars"
                self._build_dir = current / "build"
                break
            current = current.parent
        else:
            # Fallback to relative path
            self._grammars_dir = Path(__file__).parent.parent.parent / "grammars"
            self._build_dir = Path(__file__).parent.parent.parent / "build"

    def compile_grammars(
        self,
        languages: list[str],
        platform: str,
        output_dir: Path,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Compile tree-sitter grammars for specified platform

        Args:
            languages: List of languages to compile
            platform: Target platform (windows, macos, linux)
            output_dir: Directory for compiled outputs

        Returns:
            Tuple of (success, build_info) with paths and metadata
        """
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Detect compiler
        platform_info = self.platform_support.detect_platform()
        compiler = platform_info["compiler"]

        if compiler == "unknown":
            return False, {"error": "No suitable C compiler found"}

        # Prepare build info
        build_info = {
            "platform": platform,
            "compiler": compiler,
            "languages": languages,
            "libraries": {},
            "errors": [],
        }

        # Compile based on platform
        if platform == "windows":
            success = self._compile_windows(languages, output_dir, build_info)
        else:
            success = self._compile_unix(languages, output_dir, build_info, platform)

        return success, build_info

    def build_wheel(
        self,
        platform: str,
        python_version: str,
        output_dir: Path,
    ) -> tuple[bool, Path]:
        """
        Build platform-specific wheel for distribution

        Args:
            platform: Target platform identifier
            python_version: Python version (e.g., "cp39")
            output_dir: Directory for wheel output

        Returns:
            Tuple of (success, wheel_path)
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get platform tag
        platform_info = self.platform_support.detect_platform()
        platform_tag = platform_info["platform_tag"]

        # Create temporary build directory
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = Path(tmpdir)

            # Copy package files
            package_dir = build_dir / "treesitter_chunker"
            src_dir = Path(__file__).parent.parent.parent / "chunker"
            shutil.copytree(
                src_dir,
                package_dir,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )

            # Copy metadata files
            for file in ["setup.py", "pyproject.toml", "README.md", "LICENSE"]:
                src_file = Path(__file__).parent.parent.parent / file
                if src_file.exists():
                    shutil.copy2(src_file, build_dir / file)

            # Compile grammars for this platform
            grammar_dir = package_dir / "grammars" / platform
            grammar_dir.mkdir(parents=True, exist_ok=True)

            # Determine languages to include in wheel; allow env override
            env_langs = os.environ.get("CHUNKER_WHEEL_LANGS")
            if env_langs:
                requested = [l.strip() for l in env_langs.split(",") if l.strip()]
                available = set(self._get_available_languages())
                languages = [l for l in requested if l in available]
            else:
                preferred = ["python", "javascript", "rust"]
                available = set(self._get_available_languages())
                languages = [l for l in preferred if l in available] or list(available)[
                    :3
                ]

            if os.environ.get("CHUNKER_BUILD_VERBOSE"):
                print(f"Building wheel grammars for languages: {languages}")
            success, build_info = self.compile_grammars(
                languages,
                platform,
                grammar_dir,
            )

            if not success:
                if os.environ.get("CHUNKER_BUILD_VERBOSE"):
                    print(f"Grammar compilation failed: {build_info.get('errors')}")
                return False, Path()

            # Build wheel manually using wheel package
            try:
                from wheel.wheelfile import WheelFile

                # Create wheel filename
                pkg_name = "treesitter_chunker"
                version = "0.1.0"  # Should get from package
                wheel_name = (
                    f"{pkg_name}-{version}-{python_version}-none-{platform_tag}.whl"
                )
                wheel_path = output_dir / wheel_name

                # Create wheel
                with WheelFile(wheel_path, "w") as whl:
                    # Add package files
                    for file in package_dir.rglob("*"):
                        if file.is_file() and "__pycache__" not in str(file):
                            arcname = str(file.relative_to(build_dir))
                            whl.write(str(file), arcname)

                    # Add metadata
                    metadata_dir = f"{pkg_name}-{version}.dist-info"

                    # Write WHEEL file
                    wheel_metadata = f"""Wheel-Version: 1.0
Generator: treesitter-chunker-build 1.0
Root-Is-Purelib: false
Tag: {python_version}-none-{platform_tag}"""
                    whl.writestr(f"{metadata_dir}/WHEEL", wheel_metadata)

                    # Write METADATA file
                    metadata = f"""Metadata-Version: 2.1
Name: {pkg_name}
Version: {version}
Summary: Tree-sitter based code chunking library
Author: Your Name
License: MIT
Platform: {platform}
Classifier: Programming Language :: Python :: 3
Classifier: License :: OSI Approved :: MIT License
Requires-Python: {_WHEEL_REQUIRES_PYTHON}
"""
                    whl.writestr(f"{metadata_dir}/METADATA", metadata)

                    # Write top_level.txt
                    whl.writestr(
                        f"{metadata_dir}/top_level.txt",
                        "treesitter_chunker\nchunker",
                    )

                return True, wheel_path

            except ImportError:
                # Fallback to simple zip creation
                import zipfile

                wheel_name = (
                    f"treesitter_chunker-0.1.0-{python_version}-none-{platform_tag}.whl"
                )
                wheel_path = output_dir / wheel_name

                with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    # Add package files
                    for file in package_dir.rglob("*"):
                        if file.is_file() and "__pycache__" not in str(file):
                            arcname = str(file.relative_to(build_dir))
                            zf.write(str(file), arcname)

                    # Add basic metadata
                    metadata_dir = "treesitter_chunker-0.1.0.dist-info"

                    zf.writestr(
                        f"{metadata_dir}/WHEEL",
                        f"""Wheel-Version: 1.0
Generator: treesitter-chunker-build 1.0
Root-Is-Purelib: false
Tag: {python_version}-none-{platform_tag}""",
                    )

                    zf.writestr(
                        f"{metadata_dir}/METADATA",
                        f"""Metadata-Version: 2.1
Name: treesitter-chunker
Version: 0.1.0
Summary: Tree-sitter based code chunking library
Requires-Python: {_WHEEL_REQUIRES_PYTHON}
""",
                    )

                    zf.writestr(f"{metadata_dir}/top_level.txt", "treesitter_chunker")

                return True, wheel_path

            except Exception as e:
                print(f"Wheel build error: {e}")
                return False, Path()

        return False, Path()

    def create_conda_package(
        self,
        platform: str,
        output_dir: Path,
    ) -> tuple[bool, Path]:
        """
        Create conda package for distribution

        Args:
            platform: Target platform
            output_dir: Directory for package output

        Returns:
            Tuple of (success, package_path)
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Check for conda-build
        try:
            result = subprocess.run(
                ["conda", "build", "--version"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            if result.returncode != 0:
                return False, Path()
        except (subprocess.SubprocessError, FileNotFoundError):
            print("conda-build not found. Install with: conda install conda-build")
            return False, Path()

        # Find meta.yaml
        meta_path = Path(__file__).parent.parent.parent / "conda" / "meta.yaml"
        if not meta_path.exists():
            print(f"meta.yaml not found at {meta_path}")
            return False, Path()

        # Build conda package
        try:
            result = subprocess.run(
                [
                    "conda",
                    "build",
                    str(meta_path.parent),
                    "--output-folder",
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                # Find generated package
                packages = list(output_dir.rglob("*.tar.bz2"))
                if packages:
                    return True, packages[0]

        except Exception as e:
            print(f"Conda build error: {e}")

        return False, Path()

    def verify_build(
        self,
        artifact_path: Path,
        platform: str,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Verify build artifact is correctly constructed

        Args:
            artifact_path: Path to built artifact
            platform: Expected platform

        Returns:
            Tuple of (valid, verification_report)
        """
        report = {
            "artifact": str(artifact_path),
            "platform": platform,
            "valid": False,
            "components": {},
            "missing": [],
            "errors": [],
        }

        if not artifact_path.exists():
            report["errors"].append("Artifact does not exist")
            return False, report

        # Check based on file type
        if artifact_path.suffix == ".whl":
            return self._verify_wheel(artifact_path, platform, report)
        elif artifact_path.suffix == ".bz2" and "tar" in artifact_path.name:
            return self._verify_conda(artifact_path, platform, report)
        else:
            report["errors"].append(f"Unknown artifact type: {artifact_path.suffix}")
            return False, report

    def _compile_unix(
        self,
        languages: list[str],
        output_dir: Path,
        build_info: dict,
        platform: str,
    ) -> bool:
        """Compile grammars on Unix-like systems"""
        compiler = build_info["compiler"]

        # Collect source files
        all_c_files = []
        include_dirs = set()

        for lang in languages:
            grammar_dir = self._grammars_dir / f"tree-sitter-{lang}"
            if not grammar_dir.exists():
                build_info["errors"].append(f"Grammar not found: {lang}")
                continue

            # Include both root-level and src/ C sources (to pick up scanners)
            src_dir = grammar_dir / "src"
            root_c = list(grammar_dir.glob("*.c"))
            if root_c:
                include_dirs.add(str(grammar_dir))
                all_c_files.extend(str(f) for f in root_c)
            if src_dir.exists():
                include_dirs.add(str(src_dir))
                c_files = list(src_dir.glob("*.c"))
                if c_files:
                    all_c_files.extend(str(f) for f in c_files)

        if not all_c_files:
            build_info["errors"].append("No C source files found")
            return False

        # Compile shared library
        lib_name = "my-languages.so" if platform == "linux" else "my-languages.dylib"
        lib_path = output_dir / lib_name

        cmd = [compiler, "-shared", "-fPIC"]

        # Platform-specific flags
        if platform == "macos":
            cmd.extend(["-dynamiclib", "-undefined", "dynamic_lookup"])

        # Add include directories
        for inc in include_dirs:
            cmd.extend(["-I", inc])

        # Add output and source files
        cmd.extend(["-o", str(lib_path)] + all_c_files)

        try:
            timeout_s = None
            try:
                timeout_env = os.environ.get("CHUNKER_BUILD_TIMEOUT")
                if timeout_env:
                    timeout_s = int(timeout_env)
            except Exception:
                timeout_s = None
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_s,
            )
            if result.returncode == 0:
                build_info["libraries"]["combined"] = str(lib_path)
                return True
            else:
                build_info["errors"].append(f"Compilation failed: {result.stderr}")
                return False
        except subprocess.TimeoutExpired as e:
            build_info["errors"].append(f"Compilation timed out after {e.timeout}s")
            return False
        except Exception as e:
            build_info["errors"].append(f"Compilation error: {e}")
            return False

    def _compile_windows(
        self,
        languages: list[str],
        output_dir: Path,
        build_info: dict,
    ) -> bool:
        """Compile grammars on Windows"""
        # Find cl.exe
        cl_path = self._find_cl_exe()
        if not cl_path:
            build_info["errors"].append("Visual Studio cl.exe not found")
            return False

        # Collect source files
        all_c_files = []
        include_dirs = set()

        for lang in languages:
            grammar_dir = self._grammars_dir / f"tree-sitter-{lang}"
            if not grammar_dir.exists():
                build_info["errors"].append(f"Grammar not found: {lang}")
                continue

            src_dir = grammar_dir / "src"
            if src_dir.exists():
                include_dirs.add(str(src_dir))
                c_files = list(src_dir.glob("*.c"))
                if c_files:
                    all_c_files.extend(str(f) for f in c_files)

        if not all_c_files:
            build_info["errors"].append("No C source files found")
            return False

        # Compile DLL
        dll_path = output_dir / "my-languages.dll"

        cmd = [str(cl_path), "/LD"]  # /LD for DLL

        # Add include directories
        for inc in include_dirs:
            cmd.append(f"/I{inc}")

        # Add output and source files
        cmd.extend([f"/Fe{dll_path}"] + all_c_files)

        try:
            # Use shell=False for security - command is already a list
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                build_info["libraries"]["combined"] = str(dll_path)
                return True
            else:
                build_info["errors"].append(f"Compilation failed: {result.stderr}")
                return False
        except Exception as e:
            build_info["errors"].append(f"Compilation error: {e}")
            return False

    def _find_cl_exe(self) -> Path | None:
        """Find Visual Studio cl.exe compiler"""
        vs_paths = [
            r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC",
            r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC",
            r"C:\Program Files\Microsoft Visual Studio\2019\Community\VC\Tools\MSVC",
        ]

        for vs_base in vs_paths:
            vs_path = Path(vs_base)
            if vs_path.exists():
                # Find version directory
                for version_dir in vs_path.iterdir():
                    if version_dir.is_dir():
                        cl_path = version_dir / "bin" / "Hostx64" / "x64" / "cl.exe"
                        if cl_path.exists():
                            return cl_path

        return None

    def _get_available_languages(self) -> list[str]:
        """Get list of available language grammars"""
        languages = []

        if self._grammars_dir.exists():
            for grammar_dir in self._grammars_dir.glob("tree-sitter-*"):
                if grammar_dir.is_dir():
                    lang = grammar_dir.name.replace("tree-sitter-", "")
                    languages.append(lang)

        return languages

    def _fix_wheel_name(
        self,
        wheel_path: Path,
        python_version: str,
        platform_tag: str,
    ) -> Path:
        """Fix wheel filename with correct tags"""
        # Parse wheel filename
        name_parts = wheel_path.stem.split("-")
        if len(name_parts) >= 5:
            # Update python and platform tags
            name_parts[-3] = python_version
            name_parts[-1] = platform_tag
            new_name = "-".join(name_parts) + ".whl"
            return wheel_path.parent / new_name
        return wheel_path

    def _verify_wheel(
        self,
        wheel_path: Path,
        platform: str,
        report: dict,
    ) -> tuple[bool, dict]:
        """Verify wheel contents"""
        try:
            with zipfile.ZipFile(wheel_path, "r") as zf:
                members = [member.orig_filename for member in zf.infolist()]
                if len(members) != len(set(members)):
                    report["errors"].append("Duplicate wheel members")
                files = []
                for member in zf.infolist():
                    # Windows normalizes separators in filename, but not orig_filename.
                    name = member.orig_filename
                    path_parts = name.removesuffix("/").split("/")
                    if (
                        name.startswith("/")
                        or any(re.match(r"^[A-Za-z]:", part) for part in path_parts)
                        or "\\" in name
                        or "\x00" in name
                        or any(part in ("", ".", "..") for part in path_parts)
                    ):
                        report["errors"].append(f"Noncanonical wheel member: {name}")
                        continue
                    if member.is_dir():
                        if stat.S_IFMT(member.external_attr >> 16) not in (
                            0,
                            stat.S_IFDIR,
                        ):
                            report["errors"].append(f"Nonregular wheel member: {name}")
                        continue
                    if stat.S_IFMT(member.external_attr >> 16) not in (0, stat.S_IFREG):
                        report["errors"].append(f"Nonregular wheel member: {name}")
                        continue
                    files.append(name)
                dist_info_dirs = {
                    name.split("/", 1)[0]
                    for name in members
                    if name.split("/", 1)[0].endswith(".dist-info")
                }
                dist_info_dir = (
                    next(iter(dist_info_dirs)) if len(dist_info_dirs) == 1 else ""
                )
                data_dir = f"{dist_info_dir.removesuffix('.dist-info')}.data"

                def installed_path(name: str) -> tuple[str, str]:
                    parts = name.split("/")
                    if parts[0].endswith(".data"):
                        if len(parts) >= 3 and parts[0] == data_dir:
                            scheme = parts[1]
                            path = "/".join(parts[2:])
                            if scheme in ("purelib", "platlib"):
                                return "library", path
                            return f"data-{scheme}", path
                        return "unmatched-data", name
                    return "library", name

                destinations: dict[tuple[str, str], list[str]] = {}
                for name in files:
                    destinations.setdefault(installed_path(name), []).append(name)
                collisions = {
                    f"{scheme}/{path}": names
                    for (scheme, path), names in destinations.items()
                    if len(names) > 1
                }
                if collisions:
                    report["errors"].append("Wheel installation destination collision")
                installed_files = {
                    path for scheme, path in destinations if scheme == "library"
                }
                missing_payload = sorted(_REQUIRED_WHEEL_PAYLOAD - installed_files)
                missing_modules = [
                    name for name in missing_payload if name.endswith(".py")
                ]
                has_package = not missing_payload
                metadata_path = f"{dist_info_dir}/METADATA"
                wheel_info_path = f"{dist_info_dir}/WHEEL"
                record_path = f"{dist_info_dir}/RECORD"
                entry_points_path = f"{dist_info_dir}/entry_points.txt"
                has_metadata = bool(dist_info_dir) and metadata_path in files
                has_wheel_info = bool(dist_info_dir) and wheel_info_path in files
                has_record = bool(dist_info_dir) and record_path in files
                same_dist_info = has_metadata and has_wheel_info and has_record
                has_entry_points = bool(dist_info_dir) and entry_points_path in files
                if has_entry_points:
                    entry_points = ConfigParser(interpolation=None)
                    entry_points.optionxform = str  # type: ignore[method-assign, assignment]
                    entry_points.read_string(zf.read(entry_points_path).decode("utf-8"))
                    has_entry_points = (
                        not entry_points.defaults()
                        and entry_points.has_section("console_scripts")
                        and (
                            dict(entry_points.items("console_scripts"))
                            == {
                                "treesitter-chunker": "cli.main:app",
                                "tsc": "cli.main:app",
                            }
                        )
                    )
                native_files = [
                    name
                    for name in files
                    if re.search(
                        r"(?:\.so(?:\..+)?|\.(?:dll|dylib|pyd)(?:\.\d+(?:\.\d+)*)?)$",
                        PurePosixPath(name).name.casefold(),
                    )
                ]
                grammar_dir = PurePosixPath("chunker/data/grammars/build")
                native_suffix = {
                    "linux": ".so",
                    "macos": ".dylib",
                    "darwin": ".dylib",
                    "windows": ".dll",
                    "win32": ".dll",
                }.get(platform.lower())
                grammar_files = [
                    f
                    for f in native_files
                    if installed_path(f)[0] == "library"
                    and PurePosixPath(installed_path(f)[1]).parent == grammar_dir
                    and native_suffix is not None
                    and f.endswith(native_suffix)
                ]
                components = report["components"]
                components.update(
                    package=has_package,
                    missing_payload=missing_payload,
                    missing_modules=missing_modules,
                    destination_collisions=collisions,
                    metadata=has_metadata,
                    wheel_info=has_wheel_info,
                    record=has_record,
                    entry_points=has_entry_points,
                    grammars=bool(grammar_files),
                    grammar_count=len(grammar_files),
                    platform_match=False,
                    grammar_pack_dependency=False,
                    tree_sitter_runtime_dependency=False,
                    python_grammar_dependency=False,
                    javascript_grammar_dependency=False,
                    python_requirement=False,
                    payload_contract=False,
                )
                if not has_package:
                    report["missing"].append("package")
                if not has_metadata:
                    report["missing"].append("metadata")
                if not has_wheel_info:
                    report["missing"].append("wheel_info")
                if not has_record:
                    report["missing"].append("record")
                if not has_entry_points:
                    report["missing"].append("entry_points")
                if not same_dist_info:
                    report["errors"].append("Wheel metadata directories do not match")

                if same_dist_info:
                    metadata = Parser().parsestr(zf.read(metadata_path).decode("utf-8"))
                    wheel_info = Parser().parsestr(
                        zf.read(wheel_info_path).decode("utf-8")
                    )
                    wheel_name, wheel_version, _, filename_tags = parse_wheel_filename(
                        wheel_path.name
                    )
                    metadata_name = metadata.get("Name")
                    metadata_version = metadata.get("Version")
                    dist_info_name = dist_info_dir.removesuffix(".dist-info")
                    dist_name, _, dist_version = dist_info_name.rpartition("-")
                    if (
                        any(
                            len(metadata.get_all(field, [])) != 1
                            for field in ("Metadata-Version", "Name", "Version")
                        )
                        or not metadata.get("Metadata-Version")
                        or not metadata_name
                        or not metadata_version
                        or not dist_name
                        or not dist_version
                        or canonicalize_name(metadata_name) != wheel_name
                        or canonicalize_name(dist_name) != wheel_name
                        or Version(metadata_version) != wheel_version
                        or Version(dist_version) != wheel_version
                    ):
                        report["errors"].append("Wheel distribution metadata mismatch")
                    components["payload_contract"] = (
                        wheel_name == "treesitter-chunker"
                        and wheel_version == Version(_WHEEL_PAYLOAD_VERSION)
                    )
                    if not components["payload_contract"]:
                        report["errors"].append("Unsupported wheel payload contract")
                    components["python_requirement"] = len(
                        metadata.get_all("Requires-Python", [])
                    ) == 1 and SpecifierSet(
                        metadata["Requires-Python"]
                    ) == SpecifierSet(
                        ">=3.12"
                    )
                    if not components["python_requirement"]:
                        report["errors"].append("Unsupported source Requires-Python")
                    if (
                        len(wheel_info.get_all("Wheel-Version", [])) != 1
                        or wheel_info.get("Wheel-Version") != "1.0"
                    ):
                        report["errors"].append("Missing or unsupported Wheel-Version")
                    metadata_tags: set[Tag] = set()
                    for tag in wheel_info.get_all("Tag", []):
                        metadata_tags.update(parse_tag(tag))
                    universal = all(tag.platform == "any" for tag in filename_tags)
                    if (
                        any(
                            tag.platform == "any"
                            for tag in filename_tags | metadata_tags
                        )
                        and native_files
                    ):
                        report["errors"].append("Universal wheel contains native files")
                    platform_patterns = {
                        "linux": (
                            r"(?:linux|manylinux(?:1|2010|2014)|manylinux_[0-9]+_[0-9]+|musllinux_[0-9]+_[0-9]+)"
                            r"_[a-z0-9]+(?:_[a-z0-9]+)*"
                        ),
                        "macos": r"macosx_[0-9]+_[0-9]+_[a-z0-9]+(?:_[a-z0-9]+)*",
                        "windows": r"win(?:32|_(?:amd64|arm32|arm64|ia64))",
                    }
                    platform_family = {"darwin": "macos", "win32": "windows"}.get(
                        platform.lower(), platform.lower()
                    )
                    platform_pattern = platform_patterns.get(
                        platform_family, re.escape(platform_family) + ".*"
                    )
                    platform_match = (
                        filename_tags == metadata_tags
                        and all(
                            not tag.platform.startswith(
                                ("linux", "manylinux", "musllinux", "macosx", "win")
                            )
                            or any(
                                re.fullmatch(pattern, tag.platform)
                                for pattern in platform_patterns.values()
                            )
                            for tag in filename_tags
                        )
                        and any(
                            tag.platform == "any"
                            or re.fullmatch(platform_pattern, tag.platform)
                            for tag in filename_tags
                        )
                    )
                    platform_match = (
                        platform_match
                        and len(wheel_info.get_all("Root-Is-Purelib", [])) == 1
                        and wheel_info.get("Root-Is-Purelib", "").lower()
                        == ("true" if universal else "false")
                    )
                    components["platform_match"] = platform_match
                    if not platform_match:
                        report["errors"].append("Platform mismatch in wheel metadata")

                    requirements = [
                        Requirement(value)
                        for value in metadata.get_all("Requires-Dist", [])
                    ]
                    for component, name, pins in (
                        (
                            "grammar_pack_dependency",
                            "tree-sitter-language-pack",
                            ">=1.20,<1.21",
                        ),
                        (
                            "tree_sitter_runtime_dependency",
                            "tree-sitter",
                            ">=0.26,<0.27",
                        ),
                        ("python_grammar_dependency", "tree-sitter-python", "==0.25.0"),
                        (
                            "javascript_grammar_dependency",
                            "tree-sitter-javascript",
                            "==0.25.0",
                        ),
                    ):
                        matches = [
                            requirement
                            for requirement in requirements
                            if canonicalize_name(requirement.name) == name
                        ]
                        components[component] = len(matches) == 1 and all(
                            not requirement.url
                            and not requirement.marker
                            and not requirement.extras
                            and requirement.specifier == SpecifierSet(pins)
                            for requirement in matches
                        )
                        if not components[component]:
                            report["missing"].append(component)
                    if not universal and not grammar_files:
                        report["missing"].append("grammars")

                corrupt_member = zf.testzip()
                if corrupt_member:
                    report["errors"].append(f"Corrupt wheel member: {corrupt_member}")
                report["valid"] = not report["missing"] and not report["errors"]

        except Exception as e:
            report["errors"].append(f"Failed to read wheel: {e}")
            report["valid"] = False

        return report["valid"], report

    def _verify_conda(
        self,
        package_path: Path,
        platform: str,
        report: dict,
    ) -> tuple[bool, dict]:
        """Verify conda package contents"""
        try:
            # Extract to temp directory
            with tempfile.TemporaryDirectory() as tmpdir:
                extract_dir = Path(tmpdir)

                # Extract tar.bz2
                with tarfile.open(package_path, "r:bz2") as tar:
                    _safe_extract_tar(tar, extract_dir)

                # Check for required components
                info_dir = extract_dir / "info"
                has_index = (info_dir / "index.json").exists()
                has_files = (info_dir / "files").exists()
                has_recipe = (info_dir / "recipe.json").exists() or (
                    info_dir / "recipe" / "meta.yaml"
                ).exists()

                report["components"]["index"] = has_index
                report["components"]["files"] = has_files
                report["components"]["recipe"] = has_recipe

                # Check for package files
                site_packages_dirs = [
                    extract_dir / "site-packages",
                    extract_dir / "lib" / "python" / "site-packages",
                ]
                site_packages_dirs.extend(
                    python_dir / "site-packages"
                    for python_dir in (extract_dir / "lib").glob("python*")
                    if re.fullmatch(r"python\d+\.\d+", python_dir.name)
                )

                has_package = any(
                    (site_packages / package).exists()
                    for site_packages in site_packages_dirs
                    for package in ("chunker", "treesitter_chunker")
                )

                report["components"]["package"] = has_package

                # Check platform in index.json
                platform_mismatch = False
                if has_index:
                    with open(info_dir / "index.json") as f:
                        index_data = json.load(f)

                    declared_platform = index_data.get("platform")
                    if declared_platform is not None:
                        expected_platform = {
                            "windows": "win",
                            "macos": "osx",
                        }.get(platform, platform)
                        platform_mismatch = declared_platform != expected_platform
                        report["components"]["platform_match"] = not platform_mismatch
                        if platform_mismatch:
                            report["errors"].append(
                                f"Conda platform mismatch: expected {platform}, "
                                f"found {declared_platform}"
                            )
                    else:
                        report["components"]["platform_match"] = None

                # Determine if valid
                report["valid"] = (
                    has_index and has_files and has_package and not platform_mismatch
                )

                if not has_index:
                    report["missing"].append("index.json")
                if not has_files:
                    report["missing"].append("files")
                if not has_package:
                    report["missing"].append("package")

        except Exception as e:
            report["errors"].append(f"Failed to verify conda package: {e}")
            report["valid"] = False

        return report["valid"], report

    def detect_platform(self) -> dict[str, str]:
        """
        Detect current platform details

        Returns:
            Platform info including OS, arch, python version
        """
        return self.platform_support.detect_platform()
