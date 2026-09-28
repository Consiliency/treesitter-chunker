from setuptools import Extension, setup


setup(
    ext_modules=[
        Extension(
            "treesitter_chunker_baml_grammar._binding",
            sources=["src/binding.c", "src/parser.c"],
            include_dirs=["src"],
            define_macros=[("Py_LIMITED_API", "0x030B0000")],
            py_limited_api=True,
        )
    ],
    options={"bdist_wheel": {"py_limited_api": "cp311"}},
)
