"""Regression tests for grammar artifact provenance."""

import hashlib
from pathlib import Path

import pytest

from chunker.grammar.download import GrammarDownloadManager
from chunker.grammar.integrity import (
    ArtifactIntegrityError,
    probe_native_grammar,
    verify_artifact,
)


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
