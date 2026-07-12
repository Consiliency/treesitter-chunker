# Static version mirror. setuptools-scm is NOT enabled (see pyproject.toml —
# `version` is static), and nothing imports this module at runtime; the package
# version is sourced from importlib.metadata in chunker/__init__.py. This file
# is kept only as a stable literal and MUST match pyproject.toml `version`
# (IFACE: single-sourced version — this was stale at 2.0.0).

__all__ = ["__version__", "__version_tuple__", "version", "version_tuple"]

TYPE_CHECKING = False
if TYPE_CHECKING:

    VERSION_TUPLE = tuple[int | str, ...]
else:
    VERSION_TUPLE = object

version: str
__version__: str
__version_tuple__: VERSION_TUPLE
version_tuple: VERSION_TUPLE

__version__ = version = "4.0.0"
__version_tuple__ = version_tuple = (4, 0, 0)
