Chunker Module
==============

.. currentmodule:: chunker

The main chunking functionality.

Main Functions
--------------

.. autofunction:: chunk_file

.. autofunction:: chunk_text_with_token_limit

.. autofunction:: chunk_file_streaming

.. autofunction:: chunk_directory

Classes
-------

.. autoclass:: CodeChunk
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: ChunkerConfig
   :members:
   :undoc-members:
   :show-inheritance:

Examples
--------

Basic usage::

    from chunker import chunk_file

    # Chunk a Python file
    chunks = chunk_file("example.py", language="python")

    for chunk in chunks:
        print(f"{chunk.node_type}: {chunk.start_line}-{chunk.end_line}")

Streaming::

    from chunker import chunk_file_streaming

    for chunk in chunk_file_streaming("large_file.py", language="python"):
        print(f"{chunk.node_type}: {chunk.content[:50]}...")

Parallel processing::

    from chunker import chunk_directory

    results = chunk_directory("src/", language="python", workers=4)

    for result in results:
        print(f"{result.file_path}: {len(result.chunks)} chunks")
