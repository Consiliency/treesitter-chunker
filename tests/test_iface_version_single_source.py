"""IFACE: the package version is single-sourced and consistent everywhere.

pyproject.toml `version` is the source of truth (surfaced via
importlib.metadata). The __init__ fallback and the _version.py mirror must match
it so no surface (/health, OpenAPI, an uninstalled import) reports a stale value.
"""

import re
from pathlib import Path


def _pyproject_version() -> str:
    text = Path(__file__).resolve().parent.parent.joinpath("pyproject.toml").read_text()
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert m, "no static version in pyproject.toml"
    return m.group(1)


def test_metadata_version_matches_pyproject():
    from importlib.metadata import version

    assert version("treesitter-chunker") == _pyproject_version()


def test_version_py_mirror_matches_pyproject():
    from chunker import _version

    assert _version.__version__ == _pyproject_version()
    assert _version.__version_tuple__ == tuple(
        int(p) for p in _pyproject_version().split(".")
    )


def test_init_fallback_matches_pyproject():
    # The literal fallback in __init__ (used when metadata is unavailable) must
    # equal pyproject, so an editable import never reports a stale version.
    init_src = (
        Path(__file__).resolve().parent.parent.joinpath("chunker/__init__.py").read_text()
    )
    # The fallback is a literal `__version__ = "X.Y.Z"` assignment.
    fallbacks = re.findall(r'__version__ = "(\d+\.\d+\.\d+)"', init_src)
    assert _pyproject_version() in fallbacks, (
        f"__init__ fallback does not match pyproject {_pyproject_version()}: {fallbacks}"
    )
