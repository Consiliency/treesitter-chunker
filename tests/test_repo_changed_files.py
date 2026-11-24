from pathlib import Path

from git import Repo

from chunker.repo.processor import GitAwareRepoProcessor


def test_default_diff_returns_existing_rename_destination_and_addition(
    tmp_path: Path,
) -> None:
    with Repo.init(tmp_path) as repo:
        (tmp_path / "old.py").write_bytes(b"def renamed(): pass\n")
        (tmp_path / "removed.py").write_bytes(b"def removed(): pass\n")
        repo.index.add(["old.py", "removed.py"])
        repo.index.commit("Initial files")

        (tmp_path / "old.py").rename(tmp_path / "new.py")
        (tmp_path / "removed.py").unlink()
        (tmp_path / "added.py").write_bytes(b"def added(): pass\n")
        repo.git.add("--all")
        repo.index.commit("Rename, remove and add files")

    processor = GitAwareRepoProcessor(show_progress=False)
    expected = ["added.py", "new.py"]
    assert sorted(processor.get_changed_files(str(tmp_path))) == expected
    assert sorted(processor.get_changed_files(str(tmp_path), "HEAD~1")) == expected
