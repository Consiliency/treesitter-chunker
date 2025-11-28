Chunker Module
==============

.. currentmodule:: chunker.chunker

The main chunking functionality.

Main Functions
-------------

.. autofunction:: chunk_file

.. autofunction:: chunk_text

.. autofunction:: chunk_file_with_token_limit

.. autofunction:: chunk_text_with_token_limit

.. autofunction:: chunk_directory

.. autofunction:: chunk_files_parallel

.. autofunction:: chunk_directory_parallel

.. autofunction:: chunk_file_streaming

Classes
-------

.. autoclass:: Chunker
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: CodeChunk
   :members:
   :undoc-members:
   :show-inheritance:

Examples
--------

Basic usage::

    from chunker.chunker import chunk_file
    
    # Chunk a Python file
    chunks = chunk_file("example.py", "python")
    
    for chunk in chunks:
        print(f"{chunk.node_type}: {chunk.start_line}-{chunk.end_line}")

Parallel processing::

    from chunker.chunker import chunk_files_parallel
    
    files = ["file1.py", "file2.py", "file3.py"]
    results = chunk_files_parallel(files, "python", max_workers=4)
    
    for file_path, chunks in results.items():
        print(f"{file_path}: {len(chunks)} chunks")