"""Regression tests for grammar artifact provenance."""

import hashlib
import sys
from pathlib import Path

import pytest

from chunker.grammar.download import GrammarDownloadManager
from chunker.grammar.integrity import (
    ArtifactIntegrityError,
    _read_child,
    probe_native_grammar,
    verify_artifact,
)


def test_child_timeout_still_applies_after_pipes_close(tmp_path):
    code = "import os,time; os.close(1); os.close(2); time.sleep(60)"
    returncode, stdout, stderr, timed_out, overflow = _read_child(
        [sys.executable, "-I", "-c", code], tmp_path, 1
    )
    assert returncode != 0
    assert timed_out and not overflow
    assert stdout == stderr == b""


@pytest.mark.parametrize(("descriptor", "limit"), [(1, 16384), (2, 65536)])
def test_child_diagnostic_overflow_is_bounded(tmp_path, descriptor, limit):
    code = f"import os,time; os.write({descriptor}, b'x' * 131072); time.sleep(60)"
    returncode, stdout, stderr, timed_out, overflow = _read_child(
        [sys.executable, "-I", "-c", code], tmp_path, 5
    )
    assert returncode != 0
    assert overflow and not timed_out
    assert len(stdout if descriptor == 1 else stderr) <= limit


def test_child_closed_pipes_do_not_hide_normal_completion(tmp_path):
    result = _read_child(
        [sys.executable, "-I", "-c", "import os; os.close(1); os.close(2)"],
        tmp_path,
        5,
    )
    assert result == (0, b"", b"", False, False)


def test_child_drains_all_output_after_exit(tmp_path):
    result = _read_child(
        [sys.executable, "-I", "-c", "import os; os.write(1, b'x' * 12000)"],
        tmp_path,
        10,
    )
    assert result == (0, b"x" * 12000, b"", False, False)


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_probe_deadline_is_rejected(tmp_path, timeout):
    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"not native")
    result = probe_native_grammar(candidate, "test", provenance=None, timeout=timeout)
    assert not result.supported and result.reason == "timeout"
    assert result.artifact_sha256 is None


def test_verify_artifact_rejects_checksum_mismatch(tmp_path):
    artifact = tmp_path / "grammar.tar.gz"
    artifact.write_bytes(b"untrusted")

    with pytest.raises(ArtifactIntegrityError, match="checksum"):
        verify_artifact(artifact, {"sha256": "0" * 64})


def test_native_probe_rejects_untrusted_candidates_before_loading(tmp_path):
    missing = tmp_path / "missing.so"
    empty = tmp_path / "empty.so"
    empty.touch()
    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"not a native grammar")

    assert probe_native_grammar(missing, "test", provenance=None).reason == "missing"
    assert probe_native_grammar(empty, "test", provenance=None).reason == "empty"
    assert (
        probe_native_grammar(candidate, "test", provenance=None).reason == "untrusted"
    )
    assert (
        probe_native_grammar(
            candidate,
            "test",
            provenance={"sha256": "0" * 64},
        ).reason
        == "integrity_mismatch"
    )
    assert (
        probe_native_grammar(
            Path("candidate.so"),
            "test",
            provenance={"sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()},
        ).reason
        == "untrusted"
    )


def test_download_refuses_bare_master_default(tmp_path):
    with pytest.raises(ValueError, match="immutable commit"):
        GrammarDownloadManager(cache_dir=tmp_path).download_grammar("python")


def test_download_verifies_manifest_before_extract(tmp_path, monkeypatch):
    manager = GrammarDownloadManager(cache_dir=tmp_path)
    payload = b"trusted archive"
    checksum = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(
        manager,
        "ARTIFACT_MANIFEST",
        {"python@0123456789abcdef": {"sha256": checksum}},
    )
    monkeypatch.setattr(
        manager,
        "_download_file",
        lambda _url, destination, _language, _progress: Path(destination).write_bytes(
            payload,
        ),
    )
    monkeypatch.setattr(
        manager,
        "_extract_archive",
        lambda _archive, destination: destination.mkdir(exist_ok=True),
    )

    assert manager.download_grammar("python", "0123456789abcdef").exists()
