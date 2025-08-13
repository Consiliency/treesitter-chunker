class TreesitterChunker < Formula
  desc "Semantic code chunker using Tree-sitter for intelligent code analysis"
  homepage "https://github.com/aorwall/treesitter-chunker"
  url "https://files.pythonhosted.org/packages/source/t/treesitter-chunker/treesitter-chunker-1.0.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "MIT"

  depends_on "python@3.9"
  depends_on "tree-sitter"

  resource "tree-sitter" do
    url "https://files.pythonhosted.org/packages/source/t/tree-sitter/tree-sitter-0.20.4.tar.gz"
    sha256 "6adb123e2f3e56399bbf2359924633c882cc40ee8344885200bca0922f713be5"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/chunker", "--version"

    # Test basic functionality
    (testpath/"test.py").write <<~EOS
      def hello():
          print("Hello, world!")
    EOS

    output = shell_output("#{bin}/chunker chunk #{testpath}/test.py -l python")
    assert_match "hello", output
  end
end
