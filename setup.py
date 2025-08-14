"""
Setup script for treesitter-chunker.

This handles PyPI packaging with proper grammar compilation and platform-specific wheels.
"""

import platform
import subprocess
import sys
from pathlib import Path

from setuptools import find_packages, setup
from setuptools.command.develop import develop
from setuptools.command.egg_info import egg_info
from setuptools.command.install import install


class BuildGrammars:
    """Mixin for commands that need to build grammars."""

    @classmethod
    def build_grammars(cls):
        """Build tree-sitter grammars into shared library."""
        root_dir = Path(__file__).parent
        scripts_dir = root_dir / "scripts"
        grammars_dir = root_dir / "grammars"
        if not grammars_dir.exists() or not any(grammars_dir.iterdir()):
            print("Fetching grammars...")
            subprocess.run(
                [sys.executable, str(scripts_dir / "fetch_grammars.py")],
                check=True,
            )
        print("Building tree-sitter grammars...")
        subprocess.run([sys.executable, str(scripts_dir / "build_lib.py")], check=True)


class CustomInstallCommand(install, BuildGrammars):
    """Custom install command that ensures grammars are built."""

    def run(self):
        self.build_grammars()
        install.run(self)


class CustomDevelopCommand(develop, BuildGrammars):
    """Custom develop command that ensures grammars are built."""

    def run(self):
        self.build_grammars()
        develop.run(self)


class CustomEggInfoCommand(egg_info):
    """Custom egg_info command that ensures build directory exists."""

    def run(self):
        build_dir = Path(__file__).parent / "build"
        build_dir.mkdir(exist_ok=True)
        egg_info.run(self)


def get_long_description():
    """Get long description from README."""
    readme_path = Path(__file__).parent / "README.md"
    if readme_path.exists():
        return readme_path.read_text(encoding="utf-8")
    return ""


def get_requirements():
    """Parse requirements from pyproject.toml dependencies."""
    return [
        "tree_sitter",
        "rich",
        "typer",
        "pyarrow>=11.0.0",
        "toml",
        "pyyaml",
        "pygments",
        "chardet",
    ]


def get_platform_tag():
    """Get platform-specific wheel tag."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        if machine in {"x86_64", "amd64"}:
            return "macosx_10_9_x86_64"
        if machine == "arm64":
            return "macosx_11_0_arm64"
        return "macosx_10_9_universal2"
    if system == "linux":
        if machine in {"x86_64", "amd64"}:
            return "manylinux2014_x86_64"
        if machine == "aarch64":
            return "manylinux2014_aarch64"
        return "linux_" + machine
    if system == "windows":
        if machine in {"x86_64", "amd64"}:
            return "win_amd64"
        return "win32"
    return None


setup(
    name="treesitter-chunker",
    version="1.0.1",
    author="Consiliency",
    author_email="dev@consiliency.com",
    description="Semantic code chunker using Tree-sitter for intelligent code analysis",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/Consiliency/treesitter-chunker",
    project_urls={
        "Bug Tracker": "https://github.com/Consiliency/treesitter-chunker/issues",
        "Documentation": "https://github.com/Consiliency/treesitter-chunker/wiki",
        "Source Code": "https://github.com/Consiliency/treesitter-chunker",
    },
    packages=find_packages(
        exclude=["tests*", "benchmarks*", "examples*", "docs*", "scripts*"],
    ),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=get_requirements(),
    extras_require={
        "dev": ["pytest", "psutil", "build", "wheel", "twine"],
        "viz": ["graphviz"],
        "all": ["pytest", "psutil", "graphviz", "build", "wheel", "twine"],
    },
    entry_points={
        "console_scripts": ["treesitter-chunker=cli.main:app", "tsc=cli.main:app"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Text Processing :: Linguistic",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
    ],
    keywords="tree-sitter, code-analysis, chunking, parsing, ast, semantic-analysis",
    cmdclass={
        "install": CustomInstallCommand,
        "develop": CustomDevelopCommand,
        "egg_info": CustomEggInfoCommand,
    },
    zip_safe=False,
)
