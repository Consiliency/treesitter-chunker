Name:           python-treesitter-chunker
Version:        1.0.0
Release:        1%{?dist}
Summary:        Semantic code chunker using Tree-sitter for intelligent code analysis

License:        MIT
URL:            https://github.com/Consiliency/treesitter-chunker
Source0:        https://pypi.io/packages/source/t/treesitter-chunker/treesitter-chunker-%{version}.tar.gz

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  cmake
BuildRequires:  git

Requires:       python3-tree-sitter
Requires:       python3-rich
Requires:       python3-typer
Requires:       python3-pyarrow >= 11.0.0
Requires:       python3-toml
Requires:       python3-pyyaml
Requires:       python3-pygments
Requires:       python3-chardet
Requires:       python3-GitPython >= 3.1.0
Requires:       python3-pathspec >= 0.11.0
Requires:       python3-tqdm >= 4.65.0

%global _description %{expand:
TreeSitter Chunker is a powerful Python library for semantically chunking
source code using Tree-sitter parsers. It intelligently splits code into
meaningful units like functions, classes, and methods.

Features:
- Semantic understanding of code structure
- Support for Python, JavaScript, Rust, C, and C++
- High performance with parser caching
- Language agnostic design
- Thread safe for concurrent processing
- Multiple export formats (JSON, JSONL, Parquet)
- Plugin architecture for extending language support
- Universal language support with auto-download}

%description %_description

%package -n python3-treesitter-chunker
Summary:        %{summary}
BuildArch:      noarch

%description -n python3-treesitter-chunker %_description

%prep
%autosetup -n treesitter-chunker-%{version}

%build
# Fetch and build grammars
python3 scripts/fetch_grammars.py
python3 scripts/build_lib.py

# Build the Python package
%py3_build

%install
%py3_install

# Install the grammar library
mkdir -p %{buildroot}%{python3_sitelib}/chunker/build
install -m 644 build/my-languages.so %{buildroot}%{python3_sitelib}/chunker/build/

# Install CLI executable
mkdir -p %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/treesitter-chunker << 'EOF'
#!/usr/bin/env python3
from cli.main import app
if __name__ == "__main__":
    app()
EOF
chmod +x %{buildroot}%{_bindir}/treesitter-chunker

# Create tsc symlink
ln -s treesitter-chunker %{buildroot}%{_bindir}/tsc

%check
# Run tests if available
# %%pytest --ignore=grammars/

%files -n python3-treesitter-chunker
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/treesitter-chunker
%{_bindir}/tsc
%{python3_sitelib}/chunker/
%{python3_sitelib}/cli/
%{python3_sitelib}/treesitter_chunker-%{version}-py%{python3_version}.egg-info/

%changelog
* Wed Jul 24 2025 Consiliency <dev@consiliency.com> - 1.0.0-1
- Initial package release
- Full support for Python, JavaScript, Rust, C, and C++
- Plugin architecture for language extensions
- Multiple export formats (JSON, JSONL, Parquet)
- AST caching for improved performance
- Parallel processing capabilities
- Comprehensive CLI with batch processing
- Phase 14: Universal language support with auto-download