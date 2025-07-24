"""
Platform detection and support implementation
"""

import platform
import subprocess
import sys
from pathlib import Path

from chunker.contracts.build_contract import PlatformSupportContract


class PlatformSupport(PlatformSupportContract):
    """Implementation of platform-specific support"""

    def detect_platform(self) -> dict[str, str]:
        """
        Detect current platform details
        
        Returns:
            Platform info including OS, arch, python version
        """
        # Get basic platform info
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        # Normalize platform names
        if system == "darwin":
            system = "macos"
        elif system == "windows":
            system = "windows"
        else:
            system = "linux"
            
        # Normalize architecture
        if machine in ("x86_64", "amd64"):
            arch = "x86_64"
        elif machine in ("arm64", "aarch64"):
            arch = "arm64" 
        elif machine == "i386":
            arch = "i386"
        else:
            arch = machine
            
        # Get Python info
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        python_impl = platform.python_implementation().lower()
        
        # Get compiler info
        compiler = self._detect_compiler()
        
        return {
            "os": system,
            "arch": arch,
            "python_version": python_version,
            "python_impl": python_impl,
            "python_tag": f"cp{sys.version_info.major}{sys.version_info.minor}",
            "platform_tag": self._get_platform_tag(system, arch),
            "compiler": compiler,
            "libc": self._detect_libc() if system == "linux" else None,
        }
        
    def install_build_dependencies(self, platform: str) -> bool:
        """
        Install platform-specific build dependencies
        
        Args:
            platform: Target platform
            
        Returns:
            True if all dependencies installed successfully
        """
        if platform == "windows":
            return self._install_windows_deps()
        elif platform == "macos":
            return self._install_macos_deps()
        else:  # linux
            return self._install_linux_deps()
            
    def _detect_compiler(self) -> str:
        """Detect available C compiler"""
        compilers = ["gcc", "clang", "cl", "cc"]
        
        for compiler in compilers:
            try:
                result = subprocess.run(
                    [compiler, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return compiler
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
                
        return "unknown"
        
    def _detect_libc(self) -> str:
        """Detect libc version on Linux"""
        try:
            # Try ldd first
            result = subprocess.run(
                ["ldd", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stdout.lower()
            
            if "glibc" in output or "gnu" in output:
                # Extract version
                import re
                match = re.search(r'(\d+\.\d+)', output)
                if match:
                    return f"glibc{match.group(1)}"
                return "glibc"
            elif "musl" in output:
                return "musl"
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
            
        # Check for musl
        if Path("/lib/ld-musl-x86_64.so.1").exists():
            return "musl"
            
        return "glibc"  # Default assumption
        
    def _get_platform_tag(self, system: str, arch: str) -> str:
        """Generate platform tag for wheel naming"""
        if system == "windows":
            if arch == "x86_64":
                return "win_amd64"
            elif arch == "i386":
                return "win32"
            else:
                return f"win_{arch}"
        elif system == "macos":
            # macOS uses universal2 for M1 compatibility
            if arch == "arm64":
                return "macosx_11_0_arm64"
            else:
                return "macosx_10_9_x86_64"
        else:  # linux
            if arch == "x86_64":
                return "linux_x86_64"
            elif arch == "i386":
                return "linux_i686"
            else:
                return f"linux_{arch}"
                
    def _install_windows_deps(self) -> bool:
        """Install Windows build dependencies"""
        # Check for Visual Studio Build Tools
        vs_paths = [
            r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools",
            r"C:\Program Files\Microsoft Visual Studio\2019\Community",
            r"C:\Program Files\Microsoft Visual Studio\2022\Community",
        ]
        
        for path in vs_paths:
            if Path(path).exists():
                return True
                
        print("Warning: Visual Studio Build Tools not found")
        print("Please install from: https://visualstudio.microsoft.com/downloads/")
        return False
        
    def _install_macos_deps(self) -> bool:
        """Install macOS build dependencies"""
        # Check for Xcode Command Line Tools
        try:
            result = subprocess.run(
                ["xcode-select", "-p"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return True
                
            # Try to install
            print("Installing Xcode Command Line Tools...")
            subprocess.run(["xcode-select", "--install"])
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
            
    def _install_linux_deps(self) -> bool:
        """Install Linux build dependencies"""
        # Check for gcc/g++
        try:
            result = subprocess.run(
                ["gcc", "--version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return True
                
            # Try to install based on distro
            if Path("/etc/apt/sources.list").exists():
                print("Installing build-essential...")
                subprocess.run(["sudo", "apt-get", "update"])
                subprocess.run(["sudo", "apt-get", "install", "-y", "build-essential"])
                return True
            elif Path("/etc/yum.conf").exists():
                print("Installing development tools...")
                subprocess.run(["sudo", "yum", "groupinstall", "-y", "Development Tools"])
                return True
                
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
            
        return False