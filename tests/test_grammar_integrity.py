"""Regression tests for grammar artifact provenance."""

import hashlib
import io
import json
import tarfile
import tempfile
from pathlib import Path
from urllib.error import URLError

import pytest

from chunker.grammar.download import GrammarDownloadManager
from chunker.grammar.integrity import ArtifactIntegrityError, verify_artifact


def test_verify_artifact_rejects_checksum_mismatch(tmp_path):
    artifact = tmp_path / "grammar.tar.gz"
    artifact.write_bytes(b"untrusted")

    with pytest.raises(ArtifactIntegrityError, match="checksum"):
        verify_artifact(artifact, {"sha256": "0" * 64})


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


@pytest.mark.parametrize("outcome", ["success", "checksum", "transport", "extraction"])
def test_download_archive_handle_lifetime(tmp_path, monkeypatch, outcome):
    fixture = Path(__file__).parents[1] / "packages" / "baml-grammar"
    sources = {"src/parser.c": (fixture / "src/parser.c").read_bytes()}
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as output:
        for name, payload in sources.items():
            member = tarfile.TarInfo(f"fixture/{name}")
            member.size = len(payload)
            output.addfile(member, io.BytesIO(payload))
    payload = b"invalid gzip archive" if outcome == "extraction" else archive.getvalue()
    checksum = (
        "0" * 64 if outcome == "checksum" else hashlib.sha256(payload).hexdigest()
    )
    manager = GrammarDownloadManager(cache_dir=tmp_path / "cache")
    version = "0123456789abcdef"
    monkeypatch.setattr(
        manager, "ARTIFACT_MANIFEST", {f"python@{version}": {"sha256": checksum}}
    )
    created = []
    real_temporary_file = tempfile.NamedTemporaryFile

    def record_temporary_file(*args, **kwargs):
        handle = real_temporary_file(*args, **kwargs)
        created.append(handle)
        return handle

    class Response(io.BytesIO):
        headers = {"Content-Length": str(len(payload))}

    def local_response(request):
        assert request.full_url.endswith(f"/{version}.tar.gz")
        assert len(created) == 1
        assert created[0].closed, "Download creation handle must close before transport"
        if outcome == "transport":
            raise URLError("offline transport failure")
        return Response(payload)

    monkeypatch.setattr(
        "chunker.grammar.download.tempfile.NamedTemporaryFile", record_temporary_file
    )
    monkeypatch.setattr("chunker.grammar.download.urlopen", local_response)
    errors = {
        "checksum": (ArtifactIntegrityError, "checksum"),
        "transport": (RuntimeError, "offline transport failure"),
        "extraction": (tarfile.ReadError, "not a gzip file"),
    }
    if outcome == "success":
        destination = manager.download_grammar("python", version)
        assert (destination / "src/parser.c").read_bytes() == sources["src/parser.c"]
        metadata = json.loads(
            (tmp_path / "cache/metadata.json").read_text(encoding="utf-8")
        )
        assert metadata["grammars"]["python"]["path"] == str(destination)
        assert metadata["grammars"]["python"]["version"] == version
    else:
        error, message = errors[outcome]
        with pytest.raises(error, match=message):
            manager.download_grammar("python", version)
        assert manager._metadata["grammars"] == {}
        assert not (tmp_path / "cache/metadata.json").exists()
        if outcome in {"checksum", "transport"}:
            assert not (tmp_path / "cache" / f"python-{version}").exists()
    assert len(created) == 1
    assert created[0].closed
    assert not Path(created[0].name).exists()
