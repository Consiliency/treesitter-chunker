"""Real-process barrier harness for cache transaction tests.

Each participant runs in its own Python subprocess. The child installs the
private ``_transactions._BARRIER`` seam (cache transaction contract, "Test
seam"), reports every seam point as one JSON line on stdout, and blocks on a
stdin line at the points the test asks it to pause. The parent never sleeps to
order events: it waits for a reported event, then writes a line to release the
child. ``SAFETY_TIMEOUT`` only bounds a hung child; no test asserts on time.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SAFETY_TIMEOUT = 240.0

PRELUDE = r'''
import json
import os
import sys
import threading

PAUSES = json.loads(sys.argv[1])
sys.path.insert(0, sys.argv[2])
ARGS = sys.argv[3:]

from chunker.grammar_management import _transactions

_emit_lock = threading.Lock()


def emit(event, **fields):
    line = json.dumps({"event": event, **fields}, default=str)
    with _emit_lock:
        sys.__stdout__.write(line + "\n")
        sys.__stdout__.flush()


def wait():
    """Block until the parent writes one line; exit if the parent is gone."""
    if not sys.stdin.readline():
        os._exit(3)


def _barrier(point, context):
    emit(point, **context)
    for rule in PAUSES:
        if rule["point"] == point and all(
            context.get(key) == value for key, value in rule.get("match", {}).items()
        ):
            if rule.get("action") == "exit":
                os._exit(int(rule.get("code", 17)))
            wait()
            if rule.get("once", True):
                PAUSES.remove(rule)
            break


_transactions._BARRIER = _barrier
'''


class Child:
    """One participant subprocess driven by seam events."""

    def __init__(
        self,
        body: str,
        args: Sequence[str | os.PathLike[str]],
        *,
        pauses: Sequence[Mapping[str, Any]] = (),
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.seen: list[dict[str, Any]] = []
        self._events: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._stderr: list[str] = []
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-c",
                PRELUDE + body,
                json.dumps(list(pauses)),
                str(ROOT),
                *map(str, args),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=dict(env) if env is not None else None,
        )
        self._readers = [
            threading.Thread(target=self._read_events, daemon=True),
            threading.Thread(target=self._read_stderr, daemon=True),
        ]
        for reader in self._readers:
            reader.start()

    def _read_events(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            line = line.strip()
            if line:
                self._events.put(json.loads(line))
        self._events.put(None)

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self._stderr.append(line)

    @property
    def stderr(self) -> str:
        return "".join(self._stderr)

    def expect(self, event: str, **match: str) -> dict[str, Any]:
        """Return the next reported ``event`` whose fields include ``match``."""
        while True:
            try:
                item = self._events.get(timeout=SAFETY_TIMEOUT)
            except queue.Empty:
                raise AssertionError(
                    f"child never reported {event} {match}; seen "
                    f"{[e['event'] for e in self.seen]}\n{self.stderr[-4000:]}"
                ) from None
            if item is None:
                self.process.wait(timeout=SAFETY_TIMEOUT)
                raise AssertionError(
                    f"child exited {self.process.returncode} before {event} "
                    f"{match}; seen {[e['event'] for e in self.seen]}\n"
                    f"{self.stderr[-4000:]}"
                )
            self.seen.append(item)
            if item["event"] == event and all(
                item.get(key) == value for key, value in match.items()
            ):
                return item

    def release(self) -> None:
        """Release the child from its current wait (``ready`` or a pause)."""
        assert self.process.stdin is not None
        self.process.stdin.write("\n")
        self.process.stdin.flush()

    def finish(self) -> dict[str, Any]:
        """Wait for ``done`` and a clean exit; return the ``done`` event."""
        done = self.expect("done")
        returncode = self.process.wait(timeout=SAFETY_TIMEOUT)
        assert returncode == 0, (returncode, self.stderr[-4000:])
        return done

    def exit_code(self) -> int:
        """Wait for the child to exit (for example at an ``exit`` pause)."""
        return self.process.wait(timeout=SAFETY_TIMEOUT)

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=SAFETY_TIMEOUT)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
        for reader in self._readers:
            reader.join(timeout=SAFETY_TIMEOUT)


@contextmanager
def participants() -> Iterator[list[Child]]:
    """Collect children and always kill and reap them."""
    children: list[Child] = []
    try:
        yield children
    finally:
        for child in children:
            child.close()


def pause_at(point: str, **match: str) -> dict[str, Any]:
    return {"point": point, "match": match}


def exit_at(point: str, code: int = 17, **match: str) -> dict[str, Any]:
    return {"point": point, "match": match, "action": "exit", "code": code}


def _mount_mode() -> str | None:
    """How this host can mount a private tmpfs for a test, if at all."""
    if not sys.platform.startswith("linux"):
        return None
    import shutil

    if shutil.which("unshare"):
        probe = subprocess.run(
            ["unshare", "--user", "--map-root-user", "--mount", "true"],
            capture_output=True,
            check=False,
        )
        if probe.returncode == 0:
            return "unshare"
    if shutil.which("sudo"):
        probe = subprocess.run(["sudo", "-n", "true"], capture_output=True, check=False)
        if probe.returncode == 0:
            return "sudo"
    return None


def run_with_tmpfs(
    mount_point: Path, script: str, args: Sequence[str | os.PathLike[str]]
) -> subprocess.CompletedProcess[str]:
    """Run ``python -I -c script ROOT args...`` with a tmpfs at ``mount_point``.

    Uses an unprivileged user and mount namespace when the kernel allows it,
    otherwise passwordless ``sudo`` (hosted Linux runners). Skips the calling
    test when neither is available. The mount never outlives the call.
    """
    import pytest

    mode = _mount_mode()
    if mode is None:
        pytest.skip("mounting a tmpfs needs a user namespace or passwordless sudo")
    mount_point.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-I", "-c", script, str(ROOT), *map(str, args)]
    if mode == "unshare":
        return subprocess.run(
            [
                "unshare",
                "--user",
                "--map-root-user",
                "--mount",
                "sh",
                "-c",
                'mount -t tmpfs tmpfs "$1" && shift && exec "$@"',
                "sh",
                str(mount_point),
                *command,
            ],
            capture_output=True,
            text=True,
            timeout=SAFETY_TIMEOUT,
            check=False,
        )
    owner = f"uid={os.getuid()},gid={os.getgid()}"
    subprocess.run(
        ["sudo", "-n", "mount", "-t", "tmpfs", "-o", owner, "tmpfs", str(mount_point)],
        check=True,
        capture_output=True,
    )
    try:
        return subprocess.run(
            command, capture_output=True, text=True, timeout=SAFETY_TIMEOUT, check=False
        )
    finally:
        subprocess.run(["sudo", "-n", "umount", str(mount_point)], check=False)
