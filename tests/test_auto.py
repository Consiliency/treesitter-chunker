"""Unit tests for the ZeroConfigAPI implementation."""

import tempfile
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from tree_sitter_language_pack import manifest_languages

from chunker import auto, core, parser
from chunker.chunker import chunk_file_with_token_limit
from chunker.grammar.registry import UniversalLanguageRegistry
from chunker.languages import language_config_registry
from chunker.languages.base import LanguageConfig
from chunker.auto import ZeroConfigAPI
from chunker.contracts.auto_contract import AutoChunkResult
from chunker.exceptions import ChunkerError, ParserInitError
from chunker.fallback import FallbackWarning
from chunker.types import CodeChunk


@pytest.fixture(scope="module")
def pack_manifest() -> set[str]:
    return set(manifest_languages())


@pytest.mark.parametrize(
    ("extension", "language"), sorted(ZeroConfigAPI.EXTENSION_MAP.items())
)
def test_extension_map_uses_pack_manifest_names(
    extension: str, language: str, pack_manifest: set[str]
) -> None:
    # BAML has a separate, optional grammar provider.
    assert (extension, language) == (".baml", "baml") or language in pack_manifest


@pytest.mark.parametrize(
    "language", sorted(set(ZeroConfigAPI.SHEBANG_PATTERNS.values()))
)
def test_shebang_patterns_use_pack_manifest_names(
    language: str, pack_manifest: set[str]
) -> None:
    assert language in pack_manifest


class MockRegistry:
    """Mock implementation of UniversalRegistryContract for testing."""

    def __init__(self):
        self.installed_languages = {"python", "javascript", "go"}
        self.available_languages = [
            "python",
            "javascript",
            "go",
            "java",
            "rust",
            "ruby",
        ]
        self.language_versions = {
            "python": "0.20.0",
            "javascript": "0.20.0",
            "go": "0.20.0",
        }
        self.parsers = {}

    def is_language_installed(self, language: str) -> bool:
        return language in self.installed_languages

    def list_installed_languages(self) -> list[str]:
        return sorted(self.installed_languages)

    def list_available_languages(self) -> list[str]:
        return sorted(self.available_languages)

    def install_language(
        self,
        language: str,
        version: str | None = None,
    ) -> bool:
        if language in self.available_languages:
            self.installed_languages.add(language)
            self.language_versions[language] = version or "0.20.0"
            return True
        return False

    def get_language_version(self, language: str) -> str | None:
        return self.language_versions.get(language)

    def update_language(self, language: str) -> tuple[bool, str]:
        if language in self.installed_languages:
            return True, f"Updated {language} to latest version"
        return False, f"Language {language} not installed"

    def get_parser(self, language: str, auto_download: bool | None = None):
        if language in self.installed_languages:
            return MagicMock()
        return None

    def uninstall_language(self, language: str) -> bool:
        if language in self.installed_languages:
            self.installed_languages.remove(language)
            del self.language_versions[language]
            return True
        return False

    def get_language_metadata(self, language: str) -> dict:
        if language in self.installed_languages:
            return {
                "version": self.language_versions[language],
                "extensions": [f".{language[:2]}"],
            }
        return {}


class TestZeroConfigAPI:
    """Test cases for ZeroConfigAPI."""

    @pytest.fixture
    def api(self):
        """Create a ZeroConfigAPI instance with mock registry."""
        registry = MockRegistry()
        return ZeroConfigAPI(registry)

    def test_ensure_language_already_installed(self, api):
        """Test ensuring a language that's already installed."""
        assert api.ensure_language("python") is True
        assert api.registry.is_language_installed("python") is True

    def test_ensure_language_never_installs(self, api):
        """A known but uninstalled language stays unavailable: nothing is
        downloaded or built (M2 of treesitter-chunker#362, extended by the
        2026-11-01 maintainer decision)."""
        with (
            patch.object(api.registry, "install_language") as install,
            patch.object(api.registry, "update_language") as update,
        ):
            assert api.ensure_language("rust") is False
        install.assert_not_called()
        update.assert_not_called()
        assert api.registry.is_language_installed("rust") is False

    def test_failing_pinned_grammar_is_unavailable_not_an_error(self, api):
        """A grammar whose parser fails to initialize (for example a pinned
        library that fails to load) reports unavailable; preloading continues
        with the remaining languages."""
        real = api.registry.get_parser

        def get_parser(language, auto_download=None):
            if language == "go":
                raise ParserInitError("go", "pinned grammar failed to load")
            return real(language)

        with patch.object(api.registry, "get_parser", side_effect=get_parser):
            assert api.ensure_language("go") is False
            assert api.preload_languages(["go", "python"]) == {
                "go": False,
                "python": True,
            }

    def test_ensure_language_not_available(self, api):
        """Test ensuring a language that's not available."""
        assert api.ensure_language("not-a-language") is False

    def test_ensure_language_with_version(self, api):
        """A version mismatch is reported, never updated in place."""
        assert api.ensure_language("python", "0.20.0") is True
        with patch.object(api.registry, "update_language") as update:
            assert api.ensure_language("python", "0.21.0") is False
        update.assert_not_called()

    def test_detect_language_by_extension(self, api):
        """Test language detection by file extension."""
        assert api.detect_language(Path("test.py")) == "python"
        assert api.detect_language(Path("test.js")) == "javascript"
        assert api.detect_language(Path("test.rs")) == "rust"
        assert api.detect_language(Path("test.go")) == "go"
        assert api.detect_language(Path("test.unknown")) is None

    def test_detect_language_by_shebang(self, api):
        """Test language detection by shebang."""
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", delete=False) as f:
            f.write("#!/usr/bin/env python3\n")
            f.write("print('hello')")
            f.flush()
            temp_path = Path(f.name)

        try:
            assert api.detect_language(temp_path) == "python"
        finally:
            temp_path.unlink(missing_ok=True)

    def test_detect_language_special_files(self, api):
        """Test language detection for special file names."""
        assert api.detect_language(Path("Makefile")) == "makefile"
        assert api.detect_language(Path("Dockerfile")) == "dockerfile"
        assert api.detect_language(Path("package.json")) == "json"
        assert api.detect_language(Path("Cargo.toml")) == "toml"

    def test_list_supported_extensions(self, api):
        """Test listing supported file extensions."""
        extensions = api.list_supported_extensions()
        assert isinstance(extensions, dict)
        assert "python" in extensions
        assert ".py" in extensions["python"]
        assert "javascript" in extensions
        assert ".js" in extensions["javascript"]

    def test_auto_chunk_file_with_tree_sitter(self, api):
        """Test auto chunking a file with tree-sitter available."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            suffix=".py",
            mode="w",
            delete=False,
        ) as f:
            f.write("def hello():\n    print('world')")
            f.flush()
            temp_path = Path(f.name)
            mock_chunks = [
                CodeChunk(
                    language="python",
                    file_path=f.name,
                    node_type="function_definition",
                    start_line=1,
                    end_line=2,
                    byte_start=0,
                    byte_end=30,
                    parent_context="",
                    content="""def hello():
    print('world')""",
                    metadata={"name": "hello"},
                ),
            ]

        try:
            with patch("chunker.auto.chunk_file", return_value=mock_chunks):
                result = api.auto_chunk_file(str(temp_path))
            assert isinstance(result, AutoChunkResult)
            assert result.language == "python"
            assert result.fallback_used is False
            assert len(result.chunks) == 1
            assert result.chunks[0]["type"] == "function_definition"
        finally:
            temp_path.unlink(missing_ok=True)

    def test_auto_chunk_file_fallback(self, api):
        """Test auto chunking falls back when tree-sitter fails."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            suffix=".txt",
            mode="w",
            delete=False,
        ) as f:
            f.write("This is some text content\nthat should be chunked")
            f.flush()
            temp_path = Path(f.name)

        try:
            with pytest.warns(FallbackWarning, match="Using fallback chunking"):
                result = api.auto_chunk_file(str(temp_path))
            assert isinstance(result, AutoChunkResult)
            assert result.language == "unknown"
            assert result.fallback_used is True
            assert len(result.chunks) > 0
        finally:
            temp_path.unlink(missing_ok=True)

    def test_auto_chunk_file_with_language_override(self, api):
        """Test auto chunking with explicit language."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            suffix=".txt",
            mode="w",
            delete=False,
        ) as f:
            f.write("def hello():\n    print('world')")
            f.flush()
            temp_path = Path(f.name)
            mock_chunks = [
                CodeChunk(
                    language="python",
                    file_path=f.name,
                    node_type="function_definition",
                    start_line=1,
                    end_line=2,
                    byte_start=0,
                    byte_end=30,
                    parent_context="",
                    content="""def hello():
    print('world')""",
                ),
            ]

        try:
            with patch("chunker.auto.chunk_file", return_value=mock_chunks):
                result = api.auto_chunk_file(str(temp_path), language="python")
            assert result.language == "python"
            assert result.fallback_used is False
        finally:
            temp_path.unlink(missing_ok=True)

    def test_chunk_text_success(self, api):
        """Test chunking text content successfully."""
        text = "def hello():\n    print('world')"
        mock_chunks = [
            CodeChunk(
                language="python",
                file_path="",
                node_type="function_definition",
                start_line=1,
                end_line=2,
                byte_start=0,
                byte_end=len(text.encode()),
                parent_context="",
                content=text,
            ),
        ]
        with patch("chunker.auto.chunk_text", return_value=mock_chunks):
            result = api.chunk_text(text, "python")
        assert isinstance(result, AutoChunkResult)
        assert result.language == "python"
        assert result.fallback_used is False
        assert len(result.chunks) == 1

    def test_chunk_text_empty(self, api):
        """Test chunking empty text raises error."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            api.chunk_text("", "python")

    def test_auto_chunk_never_installs_or_updates(self, api, tmp_path):
        """``auto_chunk_file`` and ``chunk_text`` on the real API never install
        or update a missing grammar, and report ``grammar_downloaded=False``."""
        source = tmp_path / "script.rb"
        source.write_text("def hello\n  puts 'hi'\nend\n", encoding="utf-8")
        refuse = MagicMock(side_effect=AssertionError("install or update attempted"))
        with (
            patch.object(api.registry, "install_language", refuse),
            patch.object(api.registry, "update_language", refuse),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", FallbackWarning)
            from_file = api.auto_chunk_file(source)
            # The text fallback's own file-type detection opens its pseudo-path
            # "<text>", which Windows rejects (treesitter-chunker#585); the
            # fallback itself is not under test here.
            with patch.object(api._fallback_chunker, "chunk_text", return_value=[]):
                from_text = api.chunk_text("def hello\nend\n", "ruby")
        assert not api.registry.is_language_installed("ruby")
        for result in (from_file, from_text):
            assert result.language == "ruby"
            assert result.grammar_downloaded is False
        refuse.assert_not_called()

    def test_chunk_text_no_language(self, api):
        """Test chunking text without language raises error."""
        with pytest.raises(ValueError, match="Language must be specified"):
            api.chunk_text("some text", "")

    def test_get_chunker_for_language(self, api):
        """Test getting a chunker for a specific language."""
        chunker = api.get_chunker_for_language("python")
        assert hasattr(chunker, "chunk_file")
        assert hasattr(chunker, "chunk_text")
        with pytest.raises(ChunkerError):
            api.get_chunker_for_language("rust")
        assert not api.registry.is_language_installed("rust")

    @pytest.mark.parametrize("flag", [True, False])
    def test_get_chunker_auto_download_is_inert(self, api, flag):
        """``auto_download`` is accepted but deprecated and has no effect."""
        with patch.object(api.registry, "install_language") as install:
            with pytest.warns(DeprecationWarning, match="no effect"):
                chunker = api.get_chunker_for_language("python", auto_download=flag)
            assert hasattr(chunker, "chunk_text")
            with (
                pytest.warns(DeprecationWarning, match="no effect"),
                pytest.raises(ChunkerError),
            ):
                api.get_chunker_for_language("rust", auto_download=flag)
        install.assert_not_called()
        assert not api.registry.is_language_installed("rust")

    def test_preload_languages(self, api):
        """Preloading reports availability and installs nothing."""
        with patch.object(api.registry, "install_language") as install:
            results = api.preload_languages(["python", "rust", "not-a-language"])
        assert results == {"python": True, "rust": False, "not-a-language": False}
        install.assert_not_called()
        assert not api.registry.is_language_installed("rust")


@pytest.fixture
def real_api(tmp_path):
    return ZeroConfigAPI(
        UniversalLanguageRegistry(tmp_path, None, None, tmp_path / "cache")
    )


def assert_line_fallback(result, language, expected, path=None):
    reason = {"fallback_reason": "no_chunk_rules"}
    assert result.language == language
    assert result.fallback_used is True
    assert result.grammar_downloaded is False
    assert result.metadata == (reason | {"file_path": str(path)} if path else reason)
    assert result.chunks == [
        {
            "type": "fallback_lines",
            "content": content,
            "start_line": start,
            "end_line": end,
            "metadata": reason,
        }
        for start, end, content in expected
    ]


@pytest.mark.parametrize(
    ("name", "language", "source"),
    [
        ("valid.asm", "asm", "main:\n    nop\n"),
        ("valid.css", "css", "p { color: red; }\n"),
        ("valid.erl", "erlang", "-module(sample).\n"),
        ("valid.f90", "fortran", "program hello\nend program hello\n"),
        ("valid.fs", "fsharp", "module Sample\nlet x = 1\n"),
        ("valid.html", "html", "<p>Hello</p>\n"),
        ("valid.json", "json", '{"value":1}\n'),
        ("valid.tex", "latex", "Hello world.\n"),
        ("valid.md", "markdown", "# Title\n"),
        ("valid.nim", "nim", "let x = 1\n"),
        ("valid.pas", "pascal", "program sample;\nbegin\nend.\n"),
        ("valid.pl", "perl", "my $x = 1;\n"),
        ("valid.ps1", "powershell", "$x = 1\n"),
        ("valid.rst", "rst", "Title\n=====\n"),
        ("valid.v", "verilog", "module sample; endmodule\n"),
        ("valid.vhdl", "vhdl", "entity sample is\nend sample;\n"),
        ("CMakeLists.txt", "cmake", 'message("hello")\n'),
        ("valid.s", "asm", "main:\n    nop\n"),
        ("override.other", "ini", "[group]\nkey=value\n"),
    ],
)
def test_unruled_grammar(real_api, tmp_path, name, language, source):
    path = tmp_path / name
    path.write_bytes(source.encode())
    override = language if name == "override.other" else None
    assert real_api.detect_language(path) == (None if override else language)
    assert not parser.get_parser(language).parse(source.encode()).root_node.has_error
    expected = [(1, source.count("\n"), source)]
    assert_line_fallback(
        real_api.auto_chunk_file(path, language=override), language, expected, path
    )
    assert_line_fallback(real_api.chunk_text(source, language), language, expected)


@pytest.mark.parametrize(
    ("language", "source", "contents"),
    [
        ("python", "# comment\nx = 1\n", []),
        ("python", "def f():\n    pass\n", ["def f():\n    pass"]),
        ("lua", "local x = 1\n", []),
        ("lua", "function f() return 2 end\n", []),
        ("lua", "local f = function() return 1 end\n", ["function() return 1 end"]),
        (
            "lua",
            "function f() return 2 end\nlocal g = function() return 1 end\n",
            ["function() return 1 end"],
        ),
    ],
)
def test_ruled_extraction(real_api, tmp_path, language, source, contents):
    assert not parser.get_parser(language).parse(source.encode()).root_node.has_error
    path = tmp_path / ("example.py" if language == "python" else "example.lua")
    path.write_bytes(source.encode())
    for result in (
        real_api.auto_chunk_file(path),
        real_api.chunk_text(source, language),
    ):
        assert not result.fallback_used
        assert "fallback_reason" not in result.metadata
        assert [(c["type"], c["content"]) for c in result.chunks] == [
            ("function_definition", content) for content in contents
        ]


@pytest.mark.parametrize("source", ["", " \t\r\n", "\u2003", '{"x":"\0"}'])
def test_unruled_empty_binary_policy(real_api, tmp_path, source):
    path = tmp_path / "data.json"
    path.write_bytes(source.encode())
    results = [real_api.auto_chunk_file(path)]
    if source:
        results.append(real_api.chunk_text(source, "json"))
    else:
        with pytest.raises(ValueError, match="Text cannot be empty"):
            real_api.chunk_text(source, "json")
    for result in results:
        assert not result.fallback_used
        assert result.chunks == []


def test_imperfect_utf8(real_api, tmp_path):
    path = tmp_path / "data.json"
    path.write_bytes(b'"a\xffb"\r\n')
    assert_line_fallback(
        real_api.auto_chunk_file(path), "json", [(1, 1, '"a\ufffdb"\r\n')], path
    )


@pytest.mark.parametrize(
    ("language", "source", "fallback"),
    [
        ("json", '{"x":\n', True),
        ("lua", "local x =\n", False),
    ],
)
def test_unruled_error_tree(real_api, tmp_path, language, source, fallback):
    path = tmp_path / f"data.{language}"
    path.write_bytes(source.encode())
    assert parser.get_parser(language).parse(source.encode()).root_node.has_error
    for result, expected_path in (
        (real_api.auto_chunk_file(path), path),
        (real_api.chunk_text(source, language), None),
    ):
        if fallback:
            assert_line_fallback(result, language, [(1, 1, source)], expected_path)
        else:
            assert not result.fallback_used
            assert result.chunks == []
            assert "fallback_reason" not in result.metadata


@pytest.mark.parametrize(
    "source", ['"' + "x\u2028y\u2029" * 55 + '"', '"' + "long word " * 500 + '"']
)
def test_unruled_physical_line(real_api, tmp_path, source):
    path = tmp_path / "data.json"
    path.write_bytes(source.encode())
    assert not parser.get_parser("json").parse(source.encode()).root_node.has_error
    expected = [(1, 1, source)]
    assert_line_fallback(
        real_api.auto_chunk_file(path, token_limit=8), "json", expected, path
    )
    assert_line_fallback(
        real_api.chunk_text(
            source, "json", token_limit=8, include_retrieval_metadata=True
        ),
        "json",
        expected,
    )


def test_unruled_windows(real_api, tmp_path):
    lines = [f"line {i}" + ("\r", "\r\n", "\n")[i % 3] for i in range(120)] + ["last"]
    source = "".join(lines)
    expected = [
        (1, 50, "".join(lines[:50])),
        (51, 100, "".join(lines[50:100])),
        (101, 121, "".join(lines[100:])),
    ]
    path = tmp_path / "notes.md"
    path.write_bytes(source.encode())
    assert_line_fallback(real_api.auto_chunk_file(path), "markdown", expected, path)
    assert_line_fallback(real_api.chunk_text(source, "markdown"), "markdown", expected)


@pytest.mark.parametrize(
    ("token_limit", "extractor"),
    [(None, "chunk_text"), (16, "chunk_text_with_token_limit")],
)
def test_unruled_file_snapshot(real_api, tmp_path, token_limit, extractor):
    path = tmp_path / "notes.md"
    original = "original paragraph\r\n"
    path.write_bytes(original.encode())
    extract = getattr(auto, extractor)

    def replace_after_extraction(*args, **kwargs):
        chunks = extract(*args, **kwargs)
        assert chunks == []
        path.write_bytes(b"new paragraph\r\n")
        return chunks

    with patch.object(auto, extractor, side_effect=replace_after_extraction) as called:
        result = real_api.auto_chunk_file(path, token_limit=token_limit)
    called.assert_called_once()
    assert_line_fallback(result, "markdown", [(1, 1, original)], path)


@pytest.mark.parametrize("limit", [None, 4096])
def test_nested_json_preserves_existing_extraction(real_api, tmp_path, limit):
    path = tmp_path / "deep.json"
    source = "[" * 901 + "\r\n0\r" + "]" * 901
    path.write_bytes(source.encode())
    assert not parser.get_parser("json").parse(source.encode()).root_node.has_error
    expected = (
        chunk_file_with_token_limit(path, "json", limit)
        if limit
        else core.chunk_file(path, "json")
    )
    assert expected
    result = real_api.auto_chunk_file(path, token_limit=limit)
    assert not result.fallback_used
    assert result.chunks == [
        {
            "content": c.content,
            "type": c.node_type,
            "start_line": c.start_line,
            "end_line": c.end_line,
            **({"metadata": c.metadata} if c.metadata else {}),
        }
        for c in expected
    ]


def test_unruled_active_provider(real_api, tmp_path):
    source = "a = 1\n"
    path = tmp_path / "example.md"
    path.write_bytes(source.encode())
    for provider, fallback in [("markdown", True), ("lua", False), ("markdown", True)]:
        active = parser.get_parser(provider)
        assert not active.parse(source.encode()).root_node.has_error
        with patch.object(parser._state.factory, "get_parser", return_value=active):
            for result in (
                real_api.auto_chunk_file(path),
                real_api.chunk_text(source, "markdown"),
            ):
                assert result.fallback_used is fallback
                assert bool(result.chunks) is fallback


def test_configured_markdown_owns_empty_results(real_api, tmp_path, monkeypatch):
    class Paragraphs(LanguageConfig):
        language_id = "markdown"
        chunk_types = {"paragraph"}

    config = Paragraphs()
    assert real_api.chunk_text("paragraph\n", "markdown").fallback_used
    monkeypatch.setattr(
        language_config_registry, "_configs", language_config_registry._configs.copy()
    )
    language_config_registry.register(config)
    path = tmp_path / "example.md"
    for source, types in [
        ("paragraph\n", ["paragraph"]),
        ("# Title\n", []),
        ("paragraph\n", []),
    ]:
        if source.startswith("paragraph") and not types:
            config.chunk_types.clear()
        path.write_bytes(source.encode())
        for result in (
            real_api.auto_chunk_file(path),
            real_api.chunk_text(source, "markdown"),
        ):
            assert not result.fallback_used
            assert [c["type"] for c in result.chunks] == types


def test_unruled_extraction_failure(real_api, tmp_path, monkeypatch):
    source = '{"key":1}\n'
    path = tmp_path / "data.json"
    path.write_bytes(source.encode())
    # The legacy fallback classifies a path. Use a real path even for <text>.
    fallback = real_api._fallback_chunker.chunk_text
    monkeypatch.setattr(
        real_api._fallback_chunker,
        "chunk_text",
        lambda text, _: fallback(text, str(path)),
    )
    with patch.object(
        auto, "chunk_text", side_effect=ParserInitError("json", "injected")
    ) as extract:
        for result, metadata in [
            (real_api.auto_chunk_file(path), {"file_path": str(path)}),
            (real_api.chunk_text(source, "json"), {}),
        ]:
            assert result.fallback_used and result.chunks
            assert result.metadata == metadata | {
                "fallback_reason": "tree_sitter_failed"
            }
            assert all(
                c.get("metadata", {}).get("fallback_reason") != "no_chunk_rules"
                for c in result.chunks
            )
    assert extract.call_count == 2


def test_mixed_directory_wrappers(real_api, tmp_path):
    sources = {
        "notes.md": "plain paragraph\n",
        "code.py": "def f(): pass\n",
        "data.unknown": "some text\n",
    }
    for name, source in sources.items():
        (tmp_path / name).write_bytes(source.encode())
    results = {
        p.name: real_api.auto_chunk_file(p)
        for p in tmp_path.iterdir()
        if p.is_file() and p.name in sources
    }
    assert results["notes.md"].metadata["fallback_reason"] == "no_chunk_rules"
    assert not results["code.py"].fallback_used
    assert results["data.unknown"].fallback_used
    assert results["data.unknown"].metadata == {
        "file_path": str(tmp_path / "data.unknown")
    }
    assert core.chunk_file(tmp_path / "notes.md", "markdown") == []
