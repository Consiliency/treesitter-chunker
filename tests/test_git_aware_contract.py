"""Git-aware processing respects changed files, ignores, and saved state."""

import subprocess
from pathlib import Path

from chunker import get_parser
from chunker.repo.git_aware import GitAwareProcessorImpl


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/python/app/service.py"
)


def test_changed_source_ignore_and_incremental_state(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Contract Test"],
        check=True,
    )
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error
    source_path = repo / "service.py"
    source_path.write_bytes(source)
    (repo / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)

    source_path.write_bytes(source + b"\n# changed\n")
    (repo / "ignored.py").write_text("pass\n", encoding="utf-8")
    processor = GitAwareProcessorImpl()
    assert processor.get_changed_files(str(repo)) == ["service.py"]
    assert processor.should_process_file("service.py", str(repo))
    assert not processor.should_process_file("ignored.py", str(repo))

    state = {"file_hashes": {"service.py": processor.get_file_hash(source_path)}}
    processor.save_incremental_state(str(repo), state)
    loaded = processor.load_incremental_state(str(repo))
    assert loaded is not None
    assert loaded["file_hashes"] == state["file_hashes"]
    assert loaded["last_commit"]
    assert loaded["version"] == "1.0"
    assert loaded["timestamp"]
