class TreesitterChunker < Formula
  include Language::Python::Virtualenv

  desc "Semantic code chunker using Tree-sitter for intelligent code analysis"
  homepage "https://github.com/Consiliency/treesitter-chunker"
  url "https://files.pythonhosted.org/packages/source/t/treesitter-chunker/treesitter-chunker-0.1.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256"  # Will be updated when package is published
  license "MIT"
  head "https://github.com/Consiliency/treesitter-chunker.git", branch: "main"

  depends_on "python@3.11"
  depends_on "tree-sitter"
  depends_on "cmake" => :build
  depends_on "pkg-config" => :build

  # Python dependencies
  resource "tree-sitter" do
    url "https://files.pythonhosted.org/packages/source/t/tree-sitter/tree_sitter-0.20.4.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.7.0.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  resource "typer" do
    url "https://files.pythonhosted.org/packages/source/t/typer/typer-0.9.0.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  resource "pyarrow" do
    url "https://files.pythonhosted.org/packages/source/p/pyarrow/pyarrow-14.0.1.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  resource "toml" do
    url "https://files.pythonhosted.org/packages/source/t/toml/toml-0.10.2.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/source/P/PyYAML/PyYAML-6.0.1.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  resource "pygments" do
    url "https://files.pythonhosted.org/packages/source/p/pygments/pygments-2.17.2.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  resource "chardet" do
    url "https://files.pythonhosted.org/packages/source/c/chardet/chardet-5.2.0.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  def install
    virtualenv_install_with_resources

    # Build grammars after installation
    system libexec/"bin/python", "-c", "import subprocess; subprocess.run(['python', 'scripts/fetch_grammars.py'], cwd='#{libexec}/lib/python3.11/site-packages')"
    system libexec/"bin/python", "-c", "import subprocess; subprocess.run(['python', 'scripts/build_lib.py'], cwd='#{libexec}/lib/python3.11/site-packages')"

    # Create command shortcuts
    bin.install_symlink libexec/"bin/treesitter-chunker"
    bin.install_symlink libexec/"bin/tsc"
  end

  test do
    # Test basic functionality
    system "#{bin}/treesitter-chunker", "--version"
    
    # Test with a simple Python file
    (testpath/"test.py").write <<~EOS
      def hello():
          print("Hello, world!")
      
      class Greeter:
          def greet(self, name):
              return f"Hello, {name}!"
    EOS
    
    output = shell_output("#{bin}/treesitter-chunker chunk #{testpath}/test.py -l python")
    assert_match "hello", output
    assert_match "Greeter", output
  end
end