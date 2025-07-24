"""
Build System implementation for cross-platform grammar compilation
"""

import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from chunker.contracts.build_contract import BuildSystemContract

from .platform import PlatformSupport


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
            "errors": []
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
            shutil.copytree(src_dir, package_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            
            # Copy metadata files
            for file in ["setup.py", "pyproject.toml", "README.md", "LICENSE"]:
                src_file = Path(__file__).parent.parent.parent / file
                if src_file.exists():
                    shutil.copy2(src_file, build_dir / file)
                    
            # Compile grammars for this platform
            grammar_dir = package_dir / "grammars" / platform
            grammar_dir.mkdir(parents=True, exist_ok=True)
            
            languages = self._get_available_languages()
            success, build_info = self.compile_grammars(languages, platform, grammar_dir)
            
            if not success:
                return False, Path()
                
            # Build wheel manually using wheel package
            try:
                from wheel.wheelfile import WheelFile
                from wheel.metadata import pkginfo_to_metadata
                
                # Create wheel filename
                pkg_name = "treesitter_chunker"
                version = "0.1.0"  # Should get from package
                wheel_name = f"{pkg_name}-{version}-{python_version}-none-{platform_tag}.whl"
                wheel_path = output_dir / wheel_name
                
                # Create wheel
                with WheelFile(wheel_path, 'w') as whl:
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
                    whl.writestr(f"{metadata_dir}/top_level.txt", "treesitter_chunker\nchunker")
                    
                return True, wheel_path
                    
            except ImportError:
                # Fallback to simple zip creation
                import zipfile
                
                wheel_name = f"treesitter_chunker-0.1.0-{python_version}-none-{platform_tag}.whl"
                wheel_path = output_dir / wheel_name
                
                with zipfile.ZipFile(wheel_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    # Add package files
                    for file in package_dir.rglob("*"):
                        if file.is_file() and "__pycache__" not in str(file):
                            arcname = str(file.relative_to(build_dir))
                            zf.write(str(file), arcname)
                            
                    # Add basic metadata
                    metadata_dir = "treesitter_chunker-0.1.0.dist-info"
                    
                    zf.writestr(f"{metadata_dir}/WHEEL", f"""Wheel-Version: 1.0
Generator: treesitter-chunker-build 1.0
Root-Is-Purelib: false
Tag: {python_version}-none-{platform_tag}""")
                    
                    zf.writestr(f"{metadata_dir}/METADATA", f"""Metadata-Version: 2.1
Name: treesitter-chunker
Version: 0.1.0
Summary: Tree-sitter based code chunking library""")
                    
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
                timeout=5
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
                ["conda", "build", str(meta_path.parent), "--output-folder", str(output_dir)],
                capture_output=True,
                text=True
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
            "errors": []
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
            
    def _compile_unix(self, languages: list[str], output_dir: Path, build_info: dict, platform: str) -> bool:
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
                
            src_dir = grammar_dir / "src"
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
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                build_info["libraries"]["combined"] = str(lib_path)
                return True
            else:
                build_info["errors"].append(f"Compilation failed: {result.stderr}")
                return False
        except Exception as e:
            build_info["errors"].append(f"Compilation error: {e}")
            return False
            
    def _compile_windows(self, languages: list[str], output_dir: Path, build_info: dict) -> bool:
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
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
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
        
    def _fix_wheel_name(self, wheel_path: Path, python_version: str, platform_tag: str) -> Path:
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
        
    def _verify_wheel(self, wheel_path: Path, platform: str, report: dict) -> tuple[bool, dict]:
        """Verify wheel contents"""
        try:
            with zipfile.ZipFile(wheel_path, 'r') as zf:
                files = zf.namelist()
                
                # Check for required components
                has_package = any("chunker/" in f or "treesitter_chunker/" in f for f in files)
                has_metadata = any("METADATA" in f for f in files)
                has_wheel_info = any("WHEEL" in f for f in files)
                
                report["components"]["package"] = has_package
                report["components"]["metadata"] = has_metadata
                report["components"]["wheel_info"] = has_wheel_info
                
                # Check for grammars
                grammar_files = [f for f in files if "grammars/" in f or ".so" in f or ".dll" in f or ".dylib" in f]
                report["components"]["grammars"] = len(grammar_files) > 0
                report["components"]["grammar_count"] = len(grammar_files)
                
                # Check platform tag in WHEEL file
                if has_wheel_info:
                    wheel_info_file = next(f for f in files if "WHEEL" in f)
                    wheel_content = zf.read(wheel_info_file).decode('utf-8')
                    
                    if platform in wheel_content.lower():
                        report["components"]["platform_match"] = True
                    else:
                        report["components"]["platform_match"] = False
                        report["errors"].append(f"Platform mismatch in wheel metadata")
                        
                # Determine if valid
                report["valid"] = (
                    has_package and 
                    has_metadata and 
                    has_wheel_info and 
                    len(grammar_files) > 0
                )
                
                if not has_package:
                    report["missing"].append("package")
                if not has_metadata:
                    report["missing"].append("metadata")
                if not has_wheel_info:
                    report["missing"].append("wheel_info")
                if len(grammar_files) == 0:
                    report["missing"].append("grammars")
                    
        except Exception as e:
            report["errors"].append(f"Failed to read wheel: {e}")
            report["valid"] = False
            
        return report["valid"], report
        
    def _verify_conda(self, package_path: Path, platform: str, report: dict) -> tuple[bool, dict]:
        """Verify conda package contents"""
        try:
            # Extract to temp directory
            with tempfile.TemporaryDirectory() as tmpdir:
                extract_dir = Path(tmpdir)
                
                # Extract tar.bz2
                import tarfile
                with tarfile.open(package_path, 'r:bz2') as tar:
                    tar.extractall(extract_dir)
                    
                # Check for required components
                info_dir = extract_dir / "info"
                has_index = (info_dir / "index.json").exists()
                has_files = (info_dir / "files").exists()
                has_recipe = (info_dir / "recipe.json").exists() or (info_dir / "recipe" / "meta.yaml").exists()
                
                report["components"]["index"] = has_index
                report["components"]["files"] = has_files
                report["components"]["recipe"] = has_recipe
                
                # Check for package files
                lib_dir = extract_dir / "lib" / "python" / "site-packages"
                site_packages = extract_dir / "site-packages"
                
                has_package = (
                    (lib_dir / "chunker").exists() or 
                    (lib_dir / "treesitter_chunker").exists() or
                    (site_packages / "chunker").exists() or
                    (site_packages / "treesitter_chunker").exists()
                )
                
                report["components"]["package"] = has_package
                
                # Check platform in index.json
                if has_index:
                    with open(info_dir / "index.json") as f:
                        index_data = json.load(f)
                        
                    if "platform" in index_data:
                        report["components"]["platform_match"] = index_data["platform"] == platform
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


import sys  # Add this import at the top of the file