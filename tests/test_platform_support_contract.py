"""Observable platform metadata used by the build wrapper."""

import platform
import sys
import sysconfig
from pathlib import Path

import pytest

from chunker import get_parser
from chunker.build.system import PlatformSupportImpl

FIXTURE = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"


@pytest.mark.parametrize(
    ("system", "machine", "expected_os", "expected_arch", "expected_tag"),
    [
        ("Windows", "AMD64", "windows", "x86_64", "win_amd64"),
        ("Darwin", "arm64", "macos", "arm64", "macosx_11_0_arm64"),
        ("Linux", "x86_64", "linux", "x86_64", "linux_x86_64"),
    ],
)
def test_build_platform_metadata_uses_normalized_host_tags(
    monkeypatch, system, machine, expected_os, expected_arch, expected_tag
):
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error

    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.setattr(platform, "machine", lambda: machine)
    info = PlatformSupportImpl().detect_platform()

    assert info["os"] == expected_os
    assert info["arch"] == expected_arch
    assert info["platform_tag"] == expected_tag
    assert (
        info["python_version"] == f"{sys.version_info.major}.{sys.version_info.minor}"
    )
    assert info["python_tag"] == f"cp{sys.version_info.major}{sys.version_info.minor}"
    assert info["python_impl"] == platform.python_implementation().lower()
    assert isinstance(info["compiler"], str) and info["compiler"]
    assert (info["libc"] is None) == (expected_os != "linux")


def test_linux_aarch64_wheel_tag_matches_installer_tags(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(sysconfig, "get_platform", lambda: "linux-aarch64")

    info = PlatformSupportImpl().detect_platform()

    assert info["arch"] == "arm64"
    assert info["platform_tag"] == "linux_aarch64"
    assert info["platform_tag"] == sysconfig.get_platform().replace("-", "_")
