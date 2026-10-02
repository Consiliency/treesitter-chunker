"""Git-aware processing recognizes linked worktrees."""

import subprocess
from pathlib import Path

from chunker import get_parser
from chunker.repo.git_aware import GitAwareProcessorImpl


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/python/app/service.py"
)


def test_linked_worktree_changes_history_and_state(tmp_path: Path) -> None:
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error
    repo = tmp_path / "repo"
    linked = tmp_path / "linked"
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
    (repo / "service.py").write_bytes(source)
    subprocess.run(["git", "-C", str(repo), "add", "service.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-qb", "linked", str(linked)],
        check=True,
    )
    assert (linked / ".git").is_file()
    (linked / "service.py").write_bytes(source + b"\n# changed\n")

    processor = GitAwareProcessorImpl()
    assert processor.get_changed_files(str(linked)) == ["service.py"]
    history = processor.get_file_history("service.py", str(linked))
    assert len(history) == 1
    assert history[0]["message"] == "baseline"

    state: dict[str, object] = {"file_hashes": {}}
    processor.save_incremental_state(str(linked), state)
    assert state["last_commit"]
    assert processor.get_changed_files(str(tmp_path / "not-a-repo")) == []
