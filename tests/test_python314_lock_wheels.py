"""The locked environment installs from wheels on CPython 3.14 (treesitter-chunker#502).

``uv sync --locked --all-extras --python 3.14`` used to build ``cffi`` 1.17.1
and ``pydantic-core`` 2.33.2 from source. The cffi build needs libffi headers,
and pydantic-core's pyo3 0.24.1 rejects 3.14 outright. Other locked packages
also had no cp314 wheel. This check reads ``uv.lock`` offline.

Since 3.14 became the floor (treesitter-chunker#599), uv keeps no wheel for an
older CPython in the lock, so the check no longer compares against cp312 wheels.
Every locked package must ship at least one wheel. A package with a pure
``py3-none-any`` wheel installs everywhere and passes. Otherwise, on each
supported runner platform for which the lock carries any wheel of the package
(uv drops wheels for platforms its markers exclude), one of them must be
installable by CPython 3.14: ``cp314``, a ``cp3X-abi3`` with X <= 14, or a
Python-agnostic ``py3-none-<platform>`` wheel. The editable project itself and
packages that pyproject markers keep off CPython 3.14 are exempt.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Runner platforms: ubuntu-latest, macos-latest (arm64), Windows amd64.
PLATFORMS = {
    "linux-x86_64": re.compile(r"^manylinux.*_x86_64$"),
    "macos-arm64": re.compile(r"^macosx_.*_(arm64|universal2)$"),
    "windows-amd64": re.compile(r"^win_amd64$"),
}

# Package name -> the pyproject dependency text that keeps it off CPython 3.14.
NOT_ON_CPYTHON_314 = {
    "unicodedata2": "unicodedata2==16.0.0; python_version != '3.14' or "
    "platform_python_implementation != 'CPython'",
}


def _wheel_tags(url: str) -> tuple[list[str], str, list[str]]:
    name = url.rsplit("/", 1)[-1].removesuffix(".whl")
    python, abi, platform = name.split("-")[-3:]
    return python.split("."), abi, platform.split(".")


def _cp314_installable(pythons: list[str], abi: str) -> bool:
    if "cp314" in pythons and abi in ("cp314", "abi3", "none"):
        return True
    if abi == "abi3":
        return any(re.fullmatch(r"cp3(\d+)", p) and int(p[3:]) <= 14 for p in pythons)
    if abi == "none":
        return any(re.fullmatch(r"py3(14)?", p) for p in pythons)
    return False


def _gaps(lock: dict) -> list[str]:
    gaps = []
    for package in lock["package"]:
        if package["name"] in NOT_ON_CPYTHON_314:
            continue
        if "editable" in package.get("source", {}):
            continue  # the project itself
        wheels = [_wheel_tags(wheel["url"]) for wheel in package.get("wheels", [])]
        if not wheels:
            gaps.append(f"{package['name']}=={package['version']} (no wheel)")
            continue
        if any(
            tags == ["any"] and abi == "none" and any(p.startswith("py3") for p in pys)
            for pys, abi, tags in wheels
        ):
            continue  # a pure wheel installs on 3.14 everywhere
        for platform, pattern in PLATFORMS.items():
            on_platform = [
                (pythons, abi)
                for pythons, abi, tags in wheels
                if any(pattern.match(tag) for tag in tags)
            ]
            if on_platform and not any(
                _cp314_installable(pythons, abi) for pythons, abi in on_platform
            ):
                gaps.append(f"{package['name']}=={package['version']} ({platform})")
    return gaps


def test_every_locked_native_package_has_a_cp314_wheel() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    assert _gaps(lock) == []


def test_exempt_packages_stay_off_cpython_314() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    for requirement in NOT_ON_CPYTHON_314.values():
        assert requirement in dependencies


def test_check_detects_a_missing_cp314_wheel() -> None:
    url = "https://files.example/x/demo-1.0-{}-{}-manylinux_2_17_x86_64.whl"
    lock = {
        "package": [
            {
                "name": "demo",
                "version": "1.0",
                "wheels": [{"url": url.format("cp312", "cp312")}],
            },
            {
                "name": "fixed",
                "version": "2.0",
                "wheels": [
                    {"url": url.format("cp312", "cp312")},
                    {"url": url.format("cp314", "cp314")},
                ],
            },
            {
                "name": "pure-fallback",
                "version": "4.0",
                "wheels": [
                    {"url": url.format("cp312", "cp312")},
                    {"url": "https://files.example/x/p-4.0-py3-none-any.whl"},
                ],
            },
            {
                "name": "stable-abi",
                "version": "3.0",
                "wheels": [
                    {"url": url.format("cp312", "cp312")},
                    {"url": url.format("cp311", "abi3")},
                ],
            },
            {
                "name": "older-only",
                "version": "5.0",
                "wheels": [{"url": url.format("cp313", "cp313")}],
            },
            {
                "name": "platform-binary",
                "version": "6.0",
                "wheels": [{"url": url.format("py3", "none")}],
            },
            {"name": "sdist-only", "version": "7.0", "wheels": []},
            {"name": "project", "version": "8.0", "source": {"editable": "."}},
        ]
    }
    assert _gaps(lock) == [
        "demo==1.0 (linux-x86_64)",
        "older-only==5.0 (linux-x86_64)",
        "sdist-only==7.0 (no wheel)",
    ]
