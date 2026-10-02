"""
Build System implementation for cross-platform grammar compilation
"""

import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
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
Requires-Python: >=3.8
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
                        """Metadata-Version: 2.1
Name: treesitter-chunker
Version: 0.1.0
Summary: Tree-sitter based code chunking library""",
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
                files = set(zf.namelist())
                source_root = Path(__file__).resolve().parents[2]
                expected_modules = {
                    path.relative_to(source_root).as_posix()
                    for package in ("chunker", "cli")
                    for path in (source_root / package).rglob("*.py")
                }
                missing_modules = sorted(expected_modules - files)
                has_package = bool(expected_modules) and not missing_modules
                dist_info_dirs = {
                    name.split("/", 1)[0]
                    for name in files
                    if name.split("/", 1)[0].endswith(".dist-info")
                }
                dist_info_dir = (
                    next(iter(dist_info_dirs)) if len(dist_info_dirs) == 1 else ""
                )
                metadata_path = f"{dist_info_dir}/METADATA"
                wheel_info_path = f"{dist_info_dir}/WHEEL"
                record_path = f"{dist_info_dir}/RECORD"
                has_metadata = bool(dist_info_dir) and metadata_path in files
                has_wheel_info = bool(dist_info_dir) and wheel_info_path in files
                has_record = bool(dist_info_dir) and record_path in files
                same_dist_info = has_metadata and has_wheel_info and has_record
                native_files = [
                    f
                    for f in files
                    if f.startswith(("chunker/", "cli/"))
                    and f.endswith((".so", ".dll", ".dylib"))
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
                    if PurePosixPath(f).parent == grammar_dir
                    and native_suffix is not None
                    and f.endswith(native_suffix)
                ]
                components = report["components"]
                components.update(
                    package=has_package,
                    missing_modules=missing_modules,
                    metadata=has_metadata,
                    wheel_info=has_wheel_info,
                    record=has_record,
                    grammars=bool(grammar_files),
                    grammar_count=len(grammar_files),
                    platform_match=False,
                    grammar_pack_dependency=False,
                    tree_sitter_runtime_dependency=False,
                )
                if not has_package:
                    report["missing"].append("package")
                if not has_metadata:
                    report["missing"].append("metadata")
                if not has_wheel_info:
                    report["missing"].append("wheel_info")
                if not has_record:
                    report["missing"].append("record")
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
                        not metadata.get("Metadata-Version")
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
                    if wheel_info.get("Wheel-Version") != "1.0":
                        report["errors"].append("Missing or unsupported Wheel-Version")
                    metadata_tags: set[Tag] = set()
                    for tag in wheel_info.get_all("Tag", []):
                        metadata_tags.update(parse_tag(tag))
                    universal = all(tag.platform == "any" for tag in filename_tags)
                    if universal and native_files:
                        report["errors"].append("Universal wheel contains native files")
                    platform_tokens = {
                        "linux": ("linux", "manylinux", "musllinux"),
                        "macos": ("macosx",),
                        "darwin": ("macosx",),
                        "windows": ("win",),
                        "win32": ("win",),
                    }.get(platform.lower(), (platform.lower(),))
                    platform_match = filename_tags == metadata_tags and any(
                        tag.platform == "any"
                        or tag.platform.startswith(platform_tokens)
                        for tag in filename_tags
                    )
                    platform_match = platform_match and wheel_info.get(
                        "Root-Is-Purelib", ""
                    ).lower() == ("true" if universal else "false")
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
                    ):
                        matches = [
                            requirement
                            for requirement in requirements
                            if canonicalize_name(requirement.name) == name
                        ]
                        components[component] = len(matches) == 1 and all(
                            not requirement.marker
                            and not requirement.extras
                            and requirement.specifier == SpecifierSet(pins)
                            for requirement in matches
                        )
                    if not components["grammar_pack_dependency"]:
                        report["missing"].append("grammar_pack_dependency")
                    if not components["tree_sitter_runtime_dependency"]:
                        report["missing"].append("tree_sitter_runtime_dependency")
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
                lib_dir = extract_dir / "lib" / "python" / "site-packages"
                site_packages = extract_dir / "site-packages"

                has_package = (
                    (lib_dir / "chunker").exists()
                    or (lib_dir / "treesitter_chunker").exists()
                    or (site_packages / "chunker").exists()
                    or (site_packages / "treesitter_chunker").exists()
                )

                report["components"]["package"] = has_package

                # Check platform in index.json
                if has_index:
                    with open(info_dir / "index.json") as f:
                        index_data = json.load(f)

                    if "platform" in index_data:
                        report["components"]["platform_match"] = (
                            index_data["platform"] == platform
                        )
                    else:
                        report["components"]["platform_match"] = False

                # Determine if valid
                report["valid"] = has_index and has_files and has_package

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
