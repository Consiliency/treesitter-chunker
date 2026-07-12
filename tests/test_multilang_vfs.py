"""Regression tests for SCALE lane SL-3.

Covers two bugs that made mixed-language and large-file chunking unusable:

* BUG-1 (``chunker.multi_language.process_mixed_file``) called a non-existent
  ``chunk_file(file_path=..., content=..., language=...)`` signature and raised
  ``TypeError`` on every mixed-language file. The fix routes the in-memory
  region content through ``chunk_text(text, language, file_path)``.
* BUG-2 (``chunker.vfs_chunker._chunk_file_streaming``) reached for a
  ``self.vfs.Path`` helper that Zip/HTTP backends do not expose (AttributeError)
  and used a sliding, overlapping re-parse that duplicated boundary chunks and
  emitted buffer-relative offsets. The fix reads full bytes through the confined
  VFS handle and parses once, yielding file-relative, non-duplicated offsets.

Every test here is designed to FAIL on the pre-fix code and pass after it.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from chunker.multi_language import MultiLanguageProcessorImpl
from chunker.vfs import LocalFileSystem
from chunker.vfs_chunker import VFSChunker, chunk_from_zip


def _make_large_python_source(num_functions: int = 40000) -> str:
    """Build a >2 MiB Python source with uniquely named top-level functions.

    Unique names let us assert that no function is emitted twice (the pre-fix
    sliding buffer re-parsed overlapping regions and duplicated boundary
    chunks).
    """
    parts = []
    for i in range(num_functions):
        parts.append(
            f"def func_{i}(a, b):\n"
            f"    # unique body marker {i}\n"
            f"    return a + b + {i}\n\n",
        )
    return "".join(parts)


# ---------------------------------------------------------------------------
# BUG-1: process_mixed_file must not raise TypeError and must return chunks.
# ---------------------------------------------------------------------------


class TestProcessMixedFile:
    """process_mixed_file should chunk embedded regions via chunk_text."""

    def test_markdown_with_python_block_returns_chunks(self) -> None:
        """A Markdown file with an embedded Python block yields real chunks.

        On the pre-fix code the chunk_file(file_path=..., content=...,
        language=...) call raised TypeError, which is NOT caught by the
        method's ``(FileNotFoundError, IndexError, KeyError)`` handler, so it
        propagated out of process_mixed_file.
        """
        content = (
            "# Title\n"
            "\n"
            "Some prose describing the code.\n"
            "\n"
            "```python\n"
            "def greet(name):\n"
            "    return f'hello {name}'\n"
            "\n"
            "\n"
            "def add(a, b):\n"
            "    return a + b\n"
            "```\n"
            "\n"
            "More prose.\n"
        )
        processor = MultiLanguageProcessorImpl()

        # Must not raise TypeError.
        chunks = processor.process_mixed_file(
            "example.md",
            "markdown",
            content=content,
        )

        assert chunks, "expected at least one chunk from the embedded python block"
        # The embedded python functions should be represented.
        py_chunks = [c for c in chunks if c.language == "python"]
        assert py_chunks, "expected python chunks from the fenced code block"

        # File-relative offsets must slice back to the original content.
        for chunk in py_chunks:
            sliced = content.encode()[chunk.byte_start : chunk.byte_end].decode(
                "utf-8",
                errors="replace",
            )
            assert sliced == chunk.content, (
                "python chunk offsets are not file-relative: "
                f"{sliced!r} != {chunk.content!r}"
            )

    def test_multibyte_prefix_offsets_slice_back_and_ids_distinct(self) -> None:
        """With multibyte text before the code fence, chunk byte offsets must be
        true UTF-8 byte positions (not char indexes) and slice back; two
        identical functions in separate fences must get DISTINCT node_ids
        (SCALE panel: char-vs-byte offset + node_id not recomputed after shift).
        """
        # Multibyte header (emoji + accents) so a char index != a byte offset,
        # then TWO fences each containing a byte-identical function.
        content = (
            "# Café 🚀 documentation with multibyte chars\n"
            "\n"
            "```python\n"
            "def greet():\n"
            "    return 1\n"
            "```\n"
            "\n"
            "more café ☕ prose in between\n"
            "\n"
            "```python\n"
            "def greet():\n"
            "    return 1\n"
            "```\n"
        )
        processor = MultiLanguageProcessorImpl()
        chunks = processor.process_mixed_file("doc.md", "markdown", content=content)
        py = [c for c in chunks if c.language == "python"]
        assert py, "expected python chunks from the fenced blocks"

        src = content.encode("utf-8")
        for chunk in py:
            sliced = src[chunk.byte_start : chunk.byte_end].decode("utf-8")
            assert sliced == chunk.content, (
                f"multibyte offset wrong: {sliced!r} != {chunk.content!r}"
            )

        # The two byte-identical `def greet` functions live at different file
        # positions, so their node_ids must differ (no collision).
        greet = [c for c in py if "def greet" in c.content]
        assert len(greet) >= 2, "expected both fenced greet() functions"
        ids = {c.node_id for c in greet}
        assert len(ids) == len(greet), (
            f"identical functions collapsed to one node_id: {ids}"
        )

    def test_jsx_file_returns_chunks(self) -> None:
        """A JSX source (javascript base region) yields chunks, no TypeError."""
        content = (
            "import React from 'react';\n"
            "\n"
            "function Component() {\n"
            "    return <div style={{color: 'red'}}>Hello</div>;\n"
            "}\n"
            "\n"
            "function Other() {\n"
            "    return null;\n"
            "}\n"
        )
        processor = MultiLanguageProcessorImpl()

        chunks = processor.process_mixed_file(
            "component.jsx",
            "javascript",
            content=content,
        )

        assert chunks, "expected chunks from the jsx base region"
        assert any(c.language == "javascript" for c in chunks)


# ---------------------------------------------------------------------------
# BUG-2: VFS streaming must use the confined handle, parse once, and produce
# non-duplicated, file-relative offsets for both Local and Zip backends.
# ---------------------------------------------------------------------------


class TestVFSStreaming:
    """Streaming chunking over confined-local and zip-backed large files."""

    @staticmethod
    def _assert_stream_ok(chunks: list, content: bytes, expected_names: set[str]) -> None:
        assert chunks, "streaming produced no chunks"

        func_chunks = [c for c in chunks if c.node_type == "function_definition"]
        assert func_chunks, "expected function_definition chunks"

        # (1) File-relative offsets: every chunk slices back to its content.
        for chunk in func_chunks:
            sliced = content[chunk.byte_start : chunk.byte_end].decode(
                "utf-8",
                errors="replace",
            )
            assert sliced == chunk.content, (
                "streaming chunk offsets are not file-relative / slice back "
                f"failed at byte_start={chunk.byte_start}"
            )

        # (2) No duplicated boundary chunks: each unique (byte_start, byte_end)
        # appears once.
        spans = [(c.byte_start, c.byte_end) for c in func_chunks]
        assert len(spans) == len(set(spans)), "duplicate chunk spans detected"

        # (3) Every declared function is captured exactly once.
        seen_names: dict[str, int] = {}
        for chunk in func_chunks:
            first_line = chunk.content.splitlines()[0]
            name = first_line.split("(")[0].removeprefix("def ").strip()
            seen_names[name] = seen_names.get(name, 0) + 1
        for name in expected_names:
            assert seen_names.get(name, 0) == 1, (
                f"function {name} appeared {seen_names.get(name, 0)} times "
                "(expected exactly once)"
            )

    def test_streaming_confined_local_large_file(self, tmp_path: Path) -> None:
        """>2 MiB confined-local file streams with correct file-relative offsets.

        On the pre-fix code LocalFileSystem exposed ``.Path`` so there was no
        AttributeError, but the sliding buffer dropped everything except the
        trailing 1 MiB after each parse and emitted buffer-relative offsets, so
        slice-back fails for any function past the first buffer flush.
        """
        source = _make_large_python_source()
        raw = source.encode()
        assert len(raw) > 2 * 1024 * 1024, "fixture must exceed 2 MiB"

        big = tmp_path / "big.py"
        big.write_bytes(raw)

        # Confined LocalFileSystem rooted at tmp_path — path stays inside root.
        vfs = LocalFileSystem(tmp_path)
        chunker = VFSChunker(vfs)
        chunks = list(
            chunker.chunk_file("big.py", language="python", streaming=True),
        )

        # Sample names spread across the file (first, middle, last) so a
        # dropped-buffer regression is caught wherever it happens.
        expected = {"func_0", "func_20000", "func_39999"}
        self._assert_stream_ok(chunks, raw, expected)

    def test_streaming_zip_backed_large_file(self, tmp_path: Path) -> None:
        """>2 MiB zip member streams: no AttributeError, correct offsets.

        On the pre-fix code ZipFileSystem has no ``.Path`` attribute, so the
        streaming generator raised AttributeError on first iteration.
        """
        source = _make_large_python_source()
        raw = source.encode()
        assert len(raw) > 2 * 1024 * 1024, "fixture must exceed 2 MiB"

        zip_path = tmp_path / "archive.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("big.py", raw)

        # chunk_from_zip must materialize the generator while the archive is
        # open; a lazy generator would read from a closed zip.
        chunks = chunk_from_zip(
            str(zip_path),
            "big.py",
            language="python",
            streaming=True,
        )
        chunks = list(chunks)

        expected = {"func_0", "func_20000", "func_39999"}
        self._assert_stream_ok(chunks, raw, expected)

    def test_streaming_confined_local_rejects_escape(self, tmp_path: Path) -> None:
        """Confinement holds: a traversal path is rejected by the VFS root."""
        (tmp_path / "inside.py").write_text("def f():\n    return 1\n")
        vfs = LocalFileSystem(tmp_path)
        chunker = VFSChunker(vfs)
        with pytest.raises((ValueError, FileNotFoundError)):
            list(
                chunker.chunk_file(
                    "../escape.py",
                    language="python",
                    streaming=True,
                ),
            )
