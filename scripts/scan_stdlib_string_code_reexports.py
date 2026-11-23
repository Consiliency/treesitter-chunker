"""List the standard library's re-exports of a string-code helper.

treesitter-chunker#699 S2: the Tier 1 string-code rules count a helper's
re-exports by name (``doctest.pdb``, ``trace.pickle``,
``multiprocessing.reduction.ForkingPickler.loads``). This script imports every
standard-library module of the running interpreter (``python -I``) and prints
each module global, and each class attribute, that is one of the helper
modules or one of their loaders. ``tests/test_call_resolution_tier1_py.py``
pins the result (``STDLIB_REEXPORTS``); rerun this on a new interpreter and
classify any new entry. It is not part of the unit run: importing the whole
standard library is slow and has side effects.

Usage::

    uv run --locked --all-extras python -I scripts/scan_stdlib_string_code_reexports.py
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import pkgutil
import sys
import types
import warnings

HELPERS = (
    "cProfile", "profile", "bdb", "pdb", "trace", "timeit", "code", "codeop",
    "doctest", "pickle", "_pickle", "marshal", "runpy", "shelve",
)  # fmt: skip
SKIP = {
    "antigravity", "this", "idlelib", "turtledemo", "tkinter", "turtle",
    "__main__", "test", "ensurepip", "venv", "lib2to3",
}  # fmt: skip


def _import_everything() -> None:
    quiet = contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    )
    with quiet[0], quiet[1]:
        for name in sorted(sys.stdlib_module_names - SKIP):
            with contextlib.suppress(BaseException):
                importlib.import_module(name)
        for name in sorted(sys.stdlib_module_names - SKIP):
            module = sys.modules.get(name)
            if (
                name.startswith("_")
                or module is None
                or not hasattr(module, "__path__")
            ):
                continue
            for info in pkgutil.walk_packages(
                module.__path__, name + ".", onerror=lambda _n: None
            ):
                parts = info.name.split(".")
                if any(p in ("test", "tests", "__main__", "idle_test") for p in parts):
                    continue
                with contextlib.suppress(BaseException):
                    importlib.import_module(info.name)


def main() -> int:
    warnings.simplefilter("ignore")
    _import_everything()
    helpers = {name: sys.modules[name] for name in HELPERS if name in sys.modules}
    targets: dict[int, str] = {}
    for name in ("pickle", "_pickle", "marshal"):
        module = helpers[name]
        for member in ("loads", "load", "Unpickler", "_loads", "_load", "_Unpickler"):
            if hasattr(module, member):
                targets[id(getattr(module, member))] = f"{name}.{member}"
    found: dict[str, list[str]] = {}
    for owner, module in sorted(sys.modules.items()):
        top = owner.split(".")[0]
        if (
            not isinstance(module, types.ModuleType)
            or top not in sys.stdlib_module_names
        ):
            continue
        if top in SKIP:
            continue
        items: list[tuple[str, object]] = []
        with contextlib.suppress(Exception):
            items = list(vars(module).items())
        for key, value in items:
            for helper, helper_module in helpers.items():
                if value is helper_module and owner != helper:
                    found.setdefault(helper, []).append(f"{owner}.{key}")
            if id(value) in targets and top not in ("pickle", "_pickle", "marshal"):
                found.setdefault(targets[id(value)], []).append(f"{owner}.{key}")
            if isinstance(value, type) and str(value.__module__).split(".")[0] == top:
                for attribute, raw in list(vars(value).items()):
                    raw = getattr(raw, "__func__", raw)
                    if id(raw) in targets:
                        found.setdefault(targets[id(raw)], []).append(
                            f"{owner}.{key}.{attribute}"
                        )
    print(sys.version.split()[0])
    print(
        json.dumps(
            {key: sorted(set(value)) for key, value in sorted(found.items())}, indent=1
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
