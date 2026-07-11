"""Lifecycle / resource-hygiene tests for the repo processor (SL-5).

These cover three regressions in ``chunker.repo.processor``:

1. A stale/nonexistent ``last_commit`` must fall back to a full scan instead
   of crashing with GitPython ``BadName``.
2. Processing N files must issue a *single* batched ``git check-ignore``
   query, not one subprocess per file.
3. ``watch_repository`` must terminate on a stop signal / bound and must not
   busy-loop a non-git directory.
"""

import json
import tempfile
import threading
from pathlib import Path

import pytest

git = pytest.importorskip("git", reason="GitPython not installed")

from chunker.repo.processor import GitAwareRepoProcessor  # noqa: E402

BAD_COMMIT = "1234567890abcdef1234567890abcdef12345678"


def _init_repo(root: Path, extra_files: dict[str, str] | None = None) -> "git.Repo":
    """Create a git repo with a committed main.py (+ optional extra files)."""
    repo = git.Repo.init(root)
    (root / "main.py").write_text("def main():\n    return 1\n")
    to_add = ["main.py"]
    for name, content in (extra_files or {}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        to_add.append(name)
    # Configure identity so commit() works in a bare CI environment.
    with repo.config_writer() as cw:
        cw.set_value("user", "email", "test@example.com")
        cw.set_value("user", "name", "Test")
    repo.index.add(to_add)
    repo.index.commit("initial")
    return repo


class TestStaleCommitFullScan:
    """Bug 2: stale last_commit must fall back to a full scan, not crash."""

    def test_get_changed_files_raises_on_stale_commit(self):
        """Documents the underlying crash the processor now guards against.

        A vanished ref name surfaces as ``BadName`` and a rewritten-away SHA as
        ``ValueError`` -- the processor must survive both.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            proc = GitAwareRepoProcessor(show_progress=False)
            with pytest.raises(git.BadName):
                proc.get_changed_files(str(root), since_commit="vanished-ref")
            with pytest.raises(ValueError):
                proc.get_changed_files(str(root), since_commit=BAD_COMMIT)

    @pytest.mark.parametrize("stale", [BAD_COMMIT, "vanished-ref"])
    def test_process_repository_stale_commit_full_scan(self, stale):
        """Incremental run with a stale state file scans everything, no crash."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            # Seed a stale/nonexistent last_commit.
            (root / ".chunker_state.json").write_text(
                json.dumps({"last_commit": stale}),
            )
            proc = GitAwareRepoProcessor(show_progress=False)

            # Must not crash; must fall back to processing all files.
            result = proc.process_repository(str(root), incremental=True)

            assert result.total_files >= 1
            assert len(result.file_results) >= 1
            processed = {r.file_path for r in result.file_results}
            assert "main.py" in processed


class TestBatchedIgnoreQuery:
    """Bug 1: N files must not spawn N ``git check-ignore`` subprocesses."""

    def test_single_batched_check_ignore_for_many_files(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extra = {f"mod_{i}.py": f"def f_{i}():\n    return {i}\n" for i in range(5)}
            # A non-empty .gitignore ensures the git-ignore filter path runs.
            extra[".gitignore"] = "ignored/\n*.log\n"
            _init_repo(root, extra_files=extra)

            proc = GitAwareRepoProcessor(show_progress=False)

            # GitPython dispatches git subcommands dynamically, so the real
            # subprocess boundary is Git.execute. Count how many times a
            # `git check-ignore ...` subprocess is spawned.
            original = git.Git.execute
            check_ignore_calls = {"n": 0}

            def counting_execute(self, command, *args, **kwargs):
                if (
                    isinstance(command, (list, tuple))
                    and len(command) > 1
                    and command[1] == "check-ignore"
                ):
                    check_ignore_calls["n"] += 1
                return original(self, command, *args, **kwargs)

            monkeypatch.setattr(git.Git, "execute", counting_execute)

            files = proc.get_processable_files(str(root))
            names = {f.name for f in files}

            # All 6 python files (main + 5 mods) are tracked and not ignored.
            assert names == {"main.py", *[f"mod_{i}.py" for i in range(5)]}
            # The whole batch resolves ignore status with a single subprocess,
            # not one per file (which would be >= 6).
            assert check_ignore_calls["n"] == 1


class TestWatchRepositoryTermination:
    """Bug 3: watch loop must be bounded and must not busy-loop non-git dirs."""

    def test_watch_terminates_on_stop_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            proc = GitAwareRepoProcessor(show_progress=False)

            stop_event = threading.Event()
            updates = []

            def on_update(deltas):
                updates.append(deltas)
                stop_event.set()

            done = threading.Event()

            def run():
                proc.watch_repository(
                    str(root),
                    on_update,
                    poll_interval=0.05,
                    stop_event=stop_event,
                )
                done.set()

            worker = threading.Thread(target=run, daemon=True)
            worker.start()

            assert done.wait(timeout=10), "watch_repository did not terminate on stop"
            assert len(updates) >= 1

    def test_watch_non_git_dir_does_not_busy_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "solo.py").write_text("def solo():\n    return 0\n")
            proc = GitAwareRepoProcessor(show_progress=False)

            updates = []
            done = threading.Event()

            def run():
                proc.watch_repository(
                    str(root),
                    updates.append,
                    poll_interval=0.05,
                )
                done.set()

            worker = threading.Thread(target=run, daemon=True)
            worker.start()

            # A non-git directory has no commit cursor, so the watch must scan
            # once and return rather than spinning forever.
            assert done.wait(timeout=10), "watch_repository busy-looped a non-git dir"
            assert len(updates) == 1

    def test_watch_respects_max_iterations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            proc = GitAwareRepoProcessor(show_progress=False)

            updates = []
            done = threading.Event()

            def run():
                proc.watch_repository(
                    str(root),
                    updates.append,
                    poll_interval=0.01,
                    max_iterations=2,
                )
                done.set()

            worker = threading.Thread(target=run, daemon=True)
            worker.start()

            assert done.wait(timeout=10), "watch_repository ignored max_iterations"
            assert len(updates) == 2
