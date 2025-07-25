.. TreeSitter Chunker documentation master file

TreeSitter Chunker Documentation
================================

.. image:: https://img.shields.io/pypi/v/treesitter-chunker.svg
   :target: https://pypi.python.org/pypi/treesitter-chunker
   :alt: PyPI Version

.. image:: https://img.shields.io/pypi/l/treesitter-chunker.svg
   :target: https://github.com/Consiliency/treesitter-chunker/blob/main/LICENSE
   :alt: License

.. image:: https://img.shields.io/pypi/pyversions/treesitter-chunker.svg
   :target: https://pypi.python.org/pypi/treesitter-chunker
   :alt: Python Versions

TreeSitter Chunker is a powerful Python library for semantically chunking source code using Tree-sitter parsers. It intelligently splits code into meaningful units like functions, classes, and methods, making it perfect for code analysis, embeddings, and documentation generation.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart
   tutorial

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   basic_usage
   advanced_usage
   configuration
   cli_reference

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/chunker
   api/parser
   api/languages
   api/export
   api/plugins

.. toctree::
   :maxdepth: 2
   :caption: Developer Guide

   architecture
   plugin_development
   contributing
   changelog

Key Features
-----------

* **Semantic Understanding**: Extracts functions, classes, methods based on AST
* **High Performance**: Efficient parser caching and pooling (11.9x speedup)
* **Language Support**: Python, JavaScript, Rust, C, C++ with plugin architecture
* **Multiple Export Formats**: JSON, JSONL, Parquet, GraphML, Neo4j, SQLite
* **Thread Safe**: Designed for concurrent processing
* **Zero Config**: Works out of the box with sensible defaults
* **Universal Language Support**: Auto-download 100+ languages

Quick Example
------------

.. code-block:: python

   from chunker.chunker import chunk_file

   # Chunk a Python file
   chunks = chunk_file("example.py", "python")

   # Process results
   for chunk in chunks:
       print(f"{chunk.node_type} at lines {chunk.start_line}-{chunk.end_line}")
       print(f"  {chunk.content.split(chr(10))[0]}...")

Installation
-----------

.. code-block:: bash

   # Using pip
   pip install treesitter-chunker

   # Using uv (recommended for development)
   uv pip install treesitter-chunker

   # From source
   git clone https://github.com/Consiliency/treesitter-chunker
   cd treesitter-chunker
   pip install -e ".[dev]"

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`