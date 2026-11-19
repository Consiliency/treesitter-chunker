"""The locked environment installs from wheels on CPython 3.14 (treesitter-chunker#502).

``uv sync --locked --all-extras --python 3.14`` used to build ``cffi`` 1.17.1
and ``pydantic-core`` 2.33.2 from source. The cffi build needs libffi headers,
and pydantic-core's pyo3 0.24.1 rejects 3.14 outright. Other locked packages
also had no cp314 wheel. This check reads ``uv.lock`` offline.

Since 3.14 became the floor (treesitter-chunker#599), uv keeps no wheel for an
older CPython in the lock. When a package has no wheel for some platform, the
lock simply carries none, so "the wheels present are installable" is not
enough. Instead, the check walks the lock's own dependency graph from the
project, with every extra, once per supported runner platform. It evaluates
each edge's marker for CPython 3.14 on that platform. Every package reached
must then have a wheel that CPython 3.14 can install there: a pure
``py3-none-any`` wheel, ``cp314``, a ``cp3X-abi3`` with X <= 14, or a
Python-agnostic ``py3-none-<platform>`` wheel. A package that markers keep off
a platform (for example ``uvloop`` on Windows) is not reached there.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from packaging.markers import Marker

ROOT = Path(__file__).resolve().parents[1]

# Runner platforms: ubuntu-latest, macos-latest (arm64), Windows amd64. Each
# has a wheel-tag pattern and the marker environment of CPython 3.14 there.
_CPYTHON_314 = {
    "python_version": "3.14",
    "python_full_version": "3.14.0",
    "implementation_name": "cpython",
    "implementation_version": "3.14.0",
    "platform_python_implementation": "CPython",
}
PLATFORMS = {
    "linux-x86_64": (
        re.compile(r"^manylinux.*_x86_64$"),
        {
            **_CPYTHON_314,
            "sys_platform": "linux",
            "platform_system": "Linux",
            "platform_machine": "x86_64",
            "os_name": "posix",
        },
    ),
    "macos-arm64": (
        re.compile(r"^macosx_.*_(arm64|universal2)$"),
        {
            **_CPYTHON_314,
            "sys_platform": "darwin",
            "platform_system": "Darwin",
            "platform_machine": "arm64",
            "os_name": "posix",
        },
    ),
    "windows-amd64": (
        re.compile(r"^win_amd64$"),
        {
            **_CPYTHON_314,
            "sys_platform": "win32",
            "platform_system": "Windows",
            "platform_machine": "AMD64",
            "os_name": "nt",
        },
    ),
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


def _edges(package: dict) -> list[dict]:
    edges = list(package.get("dependencies", []))
    for group in package.get("optional-dependencies", {}).values():
        edges.extend(group)
    for group in package.get("dev-dependencies", {}).values():
        edges.extend(group)
    return edges


def _reached(lock: dict, environment: dict[str, str]) -> list[dict]:
    """Packages installed on one platform, by marker-evaluated graph walk."""
    by_name = {package["name"]: package for package in lock["package"]}
    roots = [p for p in lock["package"] if "editable" in p.get("source", {})]
    seen = {p["name"] for p in roots}
    queue = list(roots)
    while queue:
        for edge in _edges(queue.pop()):
            marker = edge.get("marker")
            if marker and not Marker(marker).evaluate({**environment, "extra": ""}):
                continue
            if edge["name"] not in seen:
                seen.add(edge["name"])
                queue.append(by_name[edge["name"]])
    return [by_name[name] for name in sorted(seen)]


def _gaps(lock: dict) -> list[str]:
    gaps = []
    for platform, (pattern, environment) in PLATFORMS.items():
        for package in _reached(lock, environment):
            if "editable" in package.get("source", {}):
                continue  # the project itself
            label = f"{package['name']}=={package['version']}"
            wheels = [_wheel_tags(wheel["url"]) for wheel in package.get("wheels", [])]
            if not wheels:
                gaps.append(f"{label} (no wheel)")
                continue
            if any(
                tags == ["any"]
                and abi == "none"
                and any(p.startswith("py3") for p in pys)
                for pys, abi, tags in wheels
            ):
                continue  # a pure wheel installs on 3.14 everywhere
            if not any(
                _cp314_installable(pythons, abi)
                for pythons, abi, tags in wheels
                if any(pattern.match(tag) for tag in tags)
            ):
                gaps.append(f"{label} ({platform})")
    return sorted(set(gaps))


def test_every_locked_native_package_has_a_cp314_wheel() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    assert _gaps(lock) == []


def test_walk_reaches_the_locked_environment() -> None:
    """Guard against a vacuous pass: the walk must reach the real dependencies."""
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    for platform, (_pattern, environment) in PLATFORMS.items():
        reached = {package["name"] for package in _reached(lock, environment)}
        assert {"tree-sitter", "pydantic-core", "pytest"} <= reached, platform
        assert len(reached) > 50, platform
    linux = {p["name"] for p in _reached(lock, PLATFORMS["linux-x86_64"][1])}
    windows = {p["name"] for p in _reached(lock, PLATFORMS["windows-amd64"][1])}
    assert "unicodedata2" not in linux | windows  # kept off CPython 3.14
    assert "uvloop" in linux and "uvloop" not in windows  # marker-excluded


def test_exempt_packages_stay_off_cpython_314() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    for requirement in NOT_ON_CPYTHON_314.values():
        assert requirement in dependencies


def _wheel(name: str, python: str, abi: str, platform: str) -> dict:
    return {"url": f"https://files.example/x/{name}-1.0-{python}-{abi}-{platform}.whl"}


def _native(name: str, python: str = "cp314", abi: str = "cp314") -> list[dict]:
    return [
        _wheel(name, python, abi, tag)
        for tag in ("manylinux_2_17_x86_64", "macosx_11_0_arm64", "win_amd64")
    ]


def test_check_detects_a_missing_cp314_wheel() -> None:
    names = [
        "full",
        "pure",
        "stable-abi",
        "linux-only",
        "older-only",
        "sdist-only",
        "posix-only",
        "off-314",
    ]
    markers = {
        "posix-only": "sys_platform != 'win32'",
        "off-314": "python_version != '3.14'",
    }
    project = {
        "name": "project",
        "version": "8.0",
        "source": {"editable": "."},
        "dependencies": [
            {"name": name, **({"marker": markers[name]} if name in markers else {})}
            for name in names[:4]
        ],
        "optional-dependencies": {
            "extra": [
                {"name": name, **({"marker": markers[name]} if name in markers else {})}
                for name in names[4:]
            ]
        },
    }
    lock = {
        "package": [
            project,
            {"name": "full", "version": "1.0", "wheels": _native("full")},
            {
                "name": "pure",
                "version": "1.0",
                "wheels": [_wheel("pure", "py3", "none", "any")],
            },
            {
                "name": "stable-abi",
                "version": "1.0",
                "wheels": _native("stable-abi", "cp311", "abi3"),
            },
            # The case uv produces under the 3.14 floor: wheels for one platform only.
            {
                "name": "linux-only",
                "version": "1.0",
                "wheels": [
                    _wheel("linux-only", "cp314", "cp314", "manylinux_2_17_x86_64")
                ],
            },
            {
                "name": "older-only",
                "version": "1.0",
                "wheels": _native("o", "cp313", "cp313"),
            },
            {"name": "sdist-only", "version": "1.0", "wheels": []},
            # No Windows wheel, but its marker keeps it off Windows: not a gap.
            {
                "name": "posix-only",
                "version": "1.0",
                "wheels": _native("posix-only")[:2],
            },
            {"name": "off-314", "version": "1.0", "wheels": []},
        ]
    }
    assert _gaps(lock) == [
        "linux-only==1.0 (macos-arm64)",
        "linux-only==1.0 (windows-amd64)",
        "older-only==1.0 (linux-x86_64)",
        "older-only==1.0 (macos-arm64)",
        "older-only==1.0 (windows-amd64)",
        "sdist-only==1.0 (no wheel)",
    ]
