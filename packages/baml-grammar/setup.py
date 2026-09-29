import os

from setuptools import Extension, setup


setup(
    ext_modules=[
        Extension(
            "treesitter_chunker_baml_grammar._binding",
            sources=["src/binding.c", "src/parser.c"],
            include_dirs=["src"],
            define_macros=[
                ("Py_LIMITED_API", "0x030B0000"),
                ("TREE_SITTER_HIDE_SYMBOLS", "1"),
            ],
            extra_compile_args=["-fvisibility=hidden"] if os.name != "nt" else [],
            py_limited_api=True,
        )
    ],
    options={"bdist_wheel": {"py_limited_api": "cp311"}},
)
