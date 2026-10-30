"""Trusted reference producer for scope_root_metadata.v2 (treesitter-chunker#512).

Slim direct contract: small controller-owned bare stores, independent plumbing goldens,
public healthy -I -S / -I -S -O runs, and finite fakes for failure paths (selector,
reads, clock, process, killer, group probe, closer, writes). Eight single-purpose
mutation triplets reuse the same guarantee checkers on fresh module copies.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import traceback

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="governed producer has a Linux validation tier"
)

ROOT = Path(__file__).resolve().parents[1]
PRODUCER = ROOT / "tools/governed_scope_commitment.py"
DRIVER = ROOT / "tools/governed_scope.py"
TOKEN = "tok512p"
HEX_LEN = {"sha1": 40, "sha256": 64}
C1, T1 = "1" * 40, "2" * 40


def require(condition, name):
    if not condition:
        raise AssertionError(name)


def git_env():
    return {
        "PATH": os.environ["PATH"],
        "LC_ALL": "C",
        "HOME": os.devnull,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
    }


def git(cwd, *args, stdin=None, env=None):
    return subprocess.run(
        [
            "git",
            "--no-replace-objects",
            "-c",
            "core.hooksPath=" + os.devnull,
            "-c",
            "commit.gpgsign=false",
            "-C",
            str(cwd),
            *args,
        ],
        input=stdin,
        env=env or git_env(),
        timeout=30,
        capture_output=True,
        check=True,
    ).stdout


def text_out(cwd, *args):
    return git(cwd, *args).decode("ascii", "strict").strip()


def put(root, path, body=b"x = 1\n"):
    p = root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)


def gitmodules_text(paths):
    return "".join(
        '[submodule "%s"]\n\tpath = %s\n\turl = ./%s\n' % (p, p, p) for p in paths
    ).encode()


def trusted_store(tmp, *, object_format="sha1", gitlinks=(), files=None):
    """Controller-owned bare store cloned from a scratch repository."""
    work = tmp / "controller-work"
    work.mkdir(parents=True)
    git(work, "init", "-q", "--object-format=" + object_format)
    for path, body in (files or {"app.py": b"x = 1\n"}).items():
        put(work, path, body)
    if gitlinks:
        put(work, ".gitmodules", gitmodules_text([p for p, _ in gitlinks]))
    git(work, "add", "-A")
    for path, oid in gitlinks:
        git(work, "update-index", "--add", "--cacheinfo", "160000,%s,%s" % (oid, path))
    git(work, "commit", "-q", "-m", "fixture")
    store = tmp / "store.git"
    git(tmp, "clone", "-q", "--bare", "--no-local", str(work), str(store))
    return (
        store,
        text_out(store, "rev-parse", "HEAD"),
        text_out(store, "rev-parse", "HEAD^{tree}"),
    )


def plumbing_commit(store, root_rows):
    lines = "".join("%s %s %s\t%s\n" % row for row in root_rows).encode("ascii")
    tree = git(store, "mktree", stdin=lines).decode("ascii").strip()
    commit = (
        git(store, "commit-tree", tree, "-m", "plumbing", stdin=b"")
        .decode("ascii")
        .strip()
    )
    return commit, tree


def blob(store, body):
    return (
        git(store, "hash-object", "-w", "--stdin", stdin=body).decode("ascii").strip()
    )


def expected_metadata(store, object_format, commit, tree):
    """Independent oracle from separate plumbing calls, never the producer parser."""
    gitlinks = []
    for row in filter(
        None, git(store, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0")
    ):
        meta, path = row.split(b"\t", 1)
        mode, kind, oid = meta.split(b" ")
        if mode == b"160000":
            gitlinks.append(
                {"path": path.decode("utf-8"), "object_id": oid.decode("ascii")}
            )
    gitmodules = None
    for row in filter(
        None, git(store, "ls-tree", "-z", "--full-tree", commit).split(b"\0")
    ):
        meta, path = row.split(b"\t", 1)
        if path == b".gitmodules":
            gitmodules = meta.split(b" ")[2].decode("ascii")
            body = git(store, "cat-file", "blob", gitmodules)
            local = hashlib.new(
                object_format, b"blob %d\0" % len(body) + body
            ).hexdigest()
            require(local == gitmodules, "BLOB_ID_ORACLE")
    return {
        "version": "scope_root_metadata.v2",
        "object_format": object_format,
        "commit": commit,
        "tree": tree,
        "gitlinks": sorted(gitlinks, key=lambda g: g["path"]),
        "gitmodules_blob": gitmodules,
    }


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def produce(
    tmp, store, commit, tree, *, output=None, optimize=False, env=None, cwd=None
):
    """Healthy public run with one finite timeout and owner cleanup.

    On timeout the direct child is killed and reaped within a bound; Git sessions the
    producer may have started are then unknown, so the outcome is reported as cleanup
    uncertainty (a failure), never as a clean teardown.
    """
    out = output or (tmp / "metadata.json")
    flags = ["-I", "-S"] + (["-O"] if optimize else [])
    argv = [
        sys.executable,
        *flags,
        str(PRODUCER),
        "commit",
        "--git-dir",
        str(store),
        "--commit",
        commit,
        "--expected-tree",
        tree,
        "--output",
        str(out),
    ]
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env if env is not None else {"PATH": os.environ["PATH"]},
    )
    try:
        stdout, stderr = proc.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        raise AssertionError(
            "PUBLIC_OWNER_CLEANUP_UNCERTAIN: producer timed out; Git sessions unknown"
        )
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr), out


def refused(cp, reason):
    require(
        cp.returncode == 1,
        "PRODUCER_REFUSAL_EXIT:" + cp.stderr.decode("utf-8", "replace"),
    )
    diag = json.loads(cp.stderr)
    require(
        diag == {"version": "scope_diagnostic.v1", "reason": reason, "path": None},
        "PRODUCER_REFUSAL_REASON:" + cp.stderr.decode("utf-8", "replace"),
    )
    require(cp.stdout == b"", "PRODUCER_REFUSAL_NO_RECEIPT")


def load_producer(path=PRODUCER, name="producer_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def declaration_v2(commit, *, rules=(), transitions=()):
    return {
        "version": "governed_scope.v2",
        "policy_version": "committed_boundary.v1",
        "repo_id": "fixture",
        "source_revision": commit,
        "ownership_assertion": {
            "decision_ref": "test-only",
            "remaining_regular_files": "governed",
        },
        "rules": list(rules),
        "generated_inclusions": [],
        "boundary_transitions": list(transitions),
        "limits": {"max_files": 100, "max_bytes": 100000},
    }


# --- finite fakes ---------------------------------------------------------------------


def fake_store(tmp):
    store = tmp / "store.git"
    (store / "objects").mkdir(parents=True)
    (store / "refs").mkdir()
    (store / "config").write_text("[core]\n\tbare = true\n", encoding="utf-8")
    (store / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    return store


class FakeRunner:
    """Scripted Git plumbing answers; records every command."""

    def __init__(self, *, tree_answer=None, root=b"", recursive=b"", fail_config=None):
        self.calls, self.uncertain = [], False
        self.gitdir = "fake.git"  # same attribute check_config reads from Runner
        self.tree_answer, self.root, self.recursive, self.fail_config = (
            tree_answer,
            root,
            recursive,
            fail_config,
        )

    def git(self, *args):
        self.calls.append(args)
        if args[0] == "config":
            if self.fail_config is not None:
                self.uncertain = True
                raise self.fail_config
            return 0, b""
        if args == ("rev-parse", "--is-bare-repository"):
            return 0, b"true\n"
        if args == ("rev-parse", "--show-object-format"):
            return 0, b"sha1\n"
        if args[:2] == ("cat-file", "-t"):
            return 0, b"commit\n"
        if args[:3] == ("rev-parse", "--verify", "--end-of-options"):
            if args[3].endswith("^{commit}"):
                return 0, (C1 + "\n").encode()
            return 0, ((self.tree_answer or T1) + "\n").encode()
        if args[:3] == ("ls-tree", "-z", "--full-tree"):
            return 0, self.root
        if args[:4] == ("ls-tree", "-r", "-z", "--full-tree"):
            return 0, self.recursive
        raise AssertionError("FAKE_UNEXPECTED_COMMAND:" + repr(args))


class FakePopen:
    """Popen stand-in with real pipes holding finite output; pid is never signalled."""

    created = []

    def __init__(self, argv, **kwargs):
        self.argv, self.kwargs, self.pid, self.returncode = argv, kwargs, -1, None
        out_r, out_w = os.pipe()
        err_r, err_w = os.pipe()
        os.write(out_w, FakePopen.payload)
        os.close(out_w)
        os.close(err_w)
        self.stdout = os.fdopen(out_r, "rb", buffering=0)
        self.stderr = os.fdopen(err_r, "rb", buffering=0)
        FakePopen.created.append(self)

    def wait(self, timeout=None):
        self.returncode = 0
        return 0


class PatchedPopen:
    """Context manager replacing subprocess.Popen used by the producer module."""

    def __init__(self, module, payload=b"sha1\n"):
        self.module, self.payload = module, payload

    def __enter__(self):
        self.saved = self.module.subprocess.Popen
        FakePopen.created, FakePopen.payload = [], self.payload
        self.module.subprocess.Popen = FakePopen
        return FakePopen.created

    def __exit__(self, *exc):
        self.module.subprocess.Popen = self.saved
        return False


class FakeProc:
    """Leader stand-in for clock/wait transcripts (never a real PID)."""

    pid = -1

    def __init__(self, clock, script):
        self.clock, self.script, self.returncode = clock, list(script), None

    def wait(self, timeout=None):
        consume, reaped = self.script.pop(0)
        self.clock[0] += consume
        if reaped:
            self.returncode = 0
            return 0
        raise subprocess.TimeoutExpired("fake", timeout)


class PipeProc:
    def __init__(self, out_fd, err_fd):
        self.stdout = os.fdopen(out_fd, "rb", buffering=0)
        self.stderr = os.fdopen(err_fd, "rb", buffering=0)


def transcript(module, sizes, cap, eof):
    """Run collect over real pipes holding finite bytes; returns (outcome, combined, requests)."""
    pipes = {name: os.pipe() for name in ("stdout", "stderr")}
    for name, (_, write_fd) in pipes.items():
        os.write(write_fd, (b"s" if name == "stdout" else b"e") * sizes[name])
        if eof:
            os.close(write_fd)
    combined, requests = [0], []

    def observed(fd, n):
        requests.append((combined[0], n))
        require(
            n <= min(module.CHUNK, cap - combined[0] + 1), "GUARANTEE_READ_ALLOWANCE"
        )
        data = os.read(fd, n)
        combined[0] += len(data)
        return data

    proc = PipeProc(pipes["stdout"][0], pipes["stderr"][0])
    runner = module.Runner("/nonexistent-" + TOKEN, read=observed, cap=cap)
    try:
        try:
            out = runner.collect(proc)
            outcome = ("eof", out)
        except module.ScopeRefused as exc:
            outcome = ("refused", exc.reason)
    finally:
        proc.stdout.close()
        proc.stderr.close()
        if not eof:
            for _, write_fd in pipes.values():
                os.close(write_fd)
    return outcome, combined[0], requests


# --- guarantee checkers (shared by contract tests and mutation triplets) -----------------


def check_tree_equality(m, tmp):
    store = fake_store(tmp)
    try:
        m.produce(str(store), C1, T1, FakeRunner(tree_answer="3" * 40))
        require(False, "GUARANTEE_TREE_EQUALITY")
    except m.ScopeRefused as exc:
        require(exc.reason == "scope_commitment", "GUARANTEE_TREE_EQUALITY")


def positive_metadata(m, tmp):
    store = fake_store(tmp)
    got = m.produce(str(store), C1, T1, FakeRunner())
    require(
        got
        == {
            "version": "scope_root_metadata.v2",
            "object_format": "sha1",
            "commit": C1,
            "tree": T1,
            "gitlinks": [],
            "gitmodules_blob": None,
        },
        "POSITIVE_METADATA",
    )


HARDENED_ENV_KEYS = {
    "PATH",
    "LC_ALL",
    "HOME",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_TERMINAL_PROMPT",
    "GIT_OPTIONAL_LOCKS",
    "GIT_NO_LAZY_FETCH",
}
HOSTILE = {
    "GIT_DIR": "/hostile",
    "GIT_WORK_TREE": "/hostile",
    "GIT_INDEX_FILE": "/hostile/idx",
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "core.hooksPath",
    "GIT_CONFIG_VALUE_0": "/hostile",
    "GIT_REPLACE_REF_BASE": "refs/replace/",
}


def check_hardened_env(m, tmp):
    store = fake_store(tmp)
    saved = {k: os.environ.get(k) for k in HOSTILE}
    os.environ.update(HOSTILE)
    try:
        with PatchedPopen(m) as created:
            code, out = m.Runner(str(store)).git("rev-parse", "--show-object-format")
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    kw = created[0].kwargs
    env = kw["env"]
    require(
        set(env) == HARDENED_ENV_KEYS
        and env["GIT_NO_LAZY_FETCH"] == "1"
        and env["GIT_TERMINAL_PROMPT"] == "0"
        and env["GIT_CONFIG_GLOBAL"] == os.devnull
        and env["HOME"] == os.devnull,
        "GUARANTEE_HARDENED_ENV",
    )
    argv = created[0].argv
    require(
        argv[0] == "git"
        and argv[1] == "--git-dir=" + str(store)
        and "--no-replace-objects" in argv
        and "--literal-pathspecs" in argv
        and "core.hooksPath=" + os.devnull in argv
        and "protocol.allow=never" in argv
        and "protocol.file.allow=never" in argv,
        "GUARANTEE_HARDENED_ARGV",
    )
    require(
        kw["cwd"] == str(store)
        and kw["start_new_session"] is True
        and kw["shell"] is False
        and kw["stdin"] == subprocess.DEVNULL,
        "GUARANTEE_HARDENED_LAUNCH",
    )
    require((code, out) == (0, b"sha1\n"), "GUARANTEE_HARDENED_RESULT")


def check_read_allowance(m, tmp):
    outcome, combined, requests = transcript(
        m, {"stdout": 8, "stderr": 8}, 10, eof=False
    )
    require(
        outcome == ("refused", "scope_commitment") and combined == 11 and requests,
        "GUARANTEE_READ_ALLOWANCE",
    )


def positive_read_below_cap(m, tmp):
    outcome, combined, _ = transcript(
        m, {"stdout": 5, "stderr": 3}, 4 * 65536, eof=True
    )
    require(outcome == ("eof", b"s" * 5) and combined == 8, "POSITIVE_READ_BELOW_CAP")


def check_shared_deadline(m, tmp):
    store = fake_store(tmp)
    now = [1000.0]
    runner = m.Runner(str(store), clock=lambda: now[0])
    with PatchedPopen(m):
        runner.git("rev-parse", "--show-object-format")
        now[0] += 25.0
        runner.git("rev-parse", "--show-object-format")
    require([b for _, b in runner.journal] == [60.0, 35.0], "GUARANTEE_SHARED_DEADLINE")


def positive_one_command(m, tmp):
    store = fake_store(tmp)
    runner = m.Runner(str(store), clock=lambda: 5.0)
    with PatchedPopen(m):
        require(
            runner.git("rev-parse", "--show-object-format") == (0, b"sha1\n"),
            "POSITIVE_ONE_COMMAND",
        )
    require([b for _, b in runner.journal] == [60.0], "POSITIVE_ONE_COMMAND")


def transcript_runner(m, clock, slice_s, cleanup_s=0.5, reserve_s=0.25):
    runner = m.Runner("/nonexistent-" + TOKEN, clock=lambda: clock[0])
    runner.slice, runner.cleanup_seconds, runner.kill_reserve = (
        slice_s,
        cleanup_s,
        reserve_s,
    )
    kills = []
    runner.killer = lambda pid, sig: kills.append(sig)
    runner.sleep = lambda s: clock.__setitem__(0, clock[0] + s)
    return runner, kills


def check_group_death(m, tmp):
    clock = [0.0]
    runner, _ = transcript_runner(m, clock, 0.125)
    runner.group_probe = lambda pid, sig: None
    proc = FakeProc(clock, [(0.125, True)])
    require(runner.wait_group(proc, 1.0) is False, "GUARANTEE_GROUP_DEATH_REQUIRED")


def positive_group_empty(m, tmp):
    clock = [0.0]
    runner, _ = transcript_runner(m, clock, 0.125)

    def gone(pid, sig):
        raise ProcessLookupError(3, "no such group")

    runner.group_probe = gone
    require(
        runner.wait_group(FakeProc(clock, [(0.125, True)]), 1.0) is True,
        "POSITIVE_GROUP_EMPTY",
    )


def check_first_error(m, tmp):
    store = fake_store(tmp)
    original = RuntimeError("first read failure")

    def interrupted(fd, n):
        raise original

    def failing_killer(pid, sig):
        raise OSError("cleanup failure")

    runner = m.Runner(str(store), read=interrupted)
    runner.killer = failing_killer
    caught = None
    with PatchedPopen(m, payload=b"x"):
        try:
            runner.git("rev-parse", "--show-object-format")
        except BaseException as exc:  # noqa: BLE001 -- classified below
            caught = exc
    frames = (
        [f.name for f in traceback.extract_tb(caught.__traceback__)]
        if caught is not None
        else []
    )
    require(
        caught is original and "interrupted" in frames,
        "GUARANTEE_FIRST_ERROR_PRESERVED",
    )
    require(
        runner.uncertain and runner.cleanup_errors[:2] == ["OSError", "OSError"],
        "GUARANTEE_CLEANUP_UNCERTAIN_RECORDED",
    )


def positive_successful_operation(m, tmp):
    store = fake_store(tmp)
    runner = m.Runner(str(store))
    with PatchedPopen(m, payload=b"x"):
        require(
            runner.git("rev-parse", "--show-object-format") == (0, b"x"),
            "POSITIVE_SUCCESSFUL_OPERATION",
        )
    require(
        not runner.cleanup_errors and not runner.uncertain,
        "POSITIVE_SUCCESSFUL_OPERATION",
    )


def check_exclusive_create(m, tmp):
    target = tmp / "out.json"
    target.write_bytes(b"caller-owned\n")
    before = os.lstat(target)
    try:
        m.write_exclusive(target, b"{}")
        require(False, "GUARANTEE_EXCLUSIVE_CREATE")
    except m.ScopeRefused as exc:
        after = os.lstat(target)
        require(
            exc.reason == "scope_root"
            and target.read_bytes() == b"caller-owned\n"
            and (after.st_ino, after.st_size) == (before.st_ino, before.st_size),
            "GUARANTEE_EXCLUSIVE_CREATE",
        )


def positive_fresh_output(m, tmp):
    target = tmp / "fresh.json"
    m.write_exclusive(target, b"{}")
    require(
        target.read_bytes() == b"{}"
        and stat.S_IMODE(os.lstat(target).st_mode) == 0o600,
        "POSITIVE_FRESH_OUTPUT",
    )


def check_q5_identity(m, tmp):
    target, swapped = tmp / "out.json", tmp / "swap.json"
    swapped.write_bytes(b"replacement\n")
    before = os.lstat(swapped)

    def replaced_then_fail(fd, view):
        swapped.replace(target)
        raise OSError(28, "No space left on device")

    caught = None
    try:
        m.write_exclusive(target, b"{}", write=replaced_then_fail)
    except BaseException as exc:  # noqa: BLE001 -- classified below
        caught = exc
    info = os.lstat(target) if os.path.lexists(target) else None
    require(
        isinstance(caught, m.CleanupUncertain)
        and isinstance(caught.__cause__, OSError)
        and info is not None
        and (info.st_dev, info.st_ino) == (before.st_dev, before.st_ino)
        and target.read_bytes() == b"replacement\n",
        "GUARANTEE_Q5_REPLACEMENT_PRESERVED",
    )


def positive_q5_proven_removal(m, tmp):
    target = tmp / "out.json"

    def fail(fd, view):
        raise OSError(28, "No space left on device")

    try:
        m.write_exclusive(target, b"{}", write=fail)
        require(False, "POSITIVE_Q5_PROVEN_REMOVAL")
    except OSError as exc:
        require(
            exc.errno == 28 and not os.path.lexists(target),
            "POSITIVE_Q5_PROVEN_REMOVAL",
        )


GUARANTEES = {
    "tree_equality": (check_tree_equality, positive_metadata),
    "hardened_env": (check_hardened_env, positive_metadata),
    "read_allowance": (check_read_allowance, positive_read_below_cap),
    "shared_deadline": (check_shared_deadline, positive_one_command),
    "group_death": (check_group_death, positive_group_empty),
    "first_error": (check_first_error, positive_successful_operation),
    "exclusive_create": (check_exclusive_create, positive_fresh_output),
    "q5_identity": (check_q5_identity, positive_q5_proven_removal),
}


@pytest.mark.parametrize("name", list(GUARANTEES))
def test_guarantee_direct(tmp_path, name):
    module = load_producer()
    check, positive = GUARANTEES[name]
    (tmp_path / "check").mkdir()
    (tmp_path / "positive").mkdir()
    check(module, tmp_path / "check")
    positive(module, tmp_path / "positive")


# --- public goldens and integration ----------------------------------------------------------


@pytest.mark.parametrize("optimize", [False, True])
@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
def test_golden_matches_plumbing(tmp_path, object_format, optimize):
    store, commit, tree = trusted_store(
        tmp_path,
        object_format=object_format,
        gitlinks=[("child", "1" * HEX_LEN[object_format])],
    )
    cp, out = produce(tmp_path, store, commit, tree, optimize=optimize)
    require(cp.returncode == 0, "PRODUCER_EXIT:" + cp.stderr.decode("utf-8", "replace"))
    require(("-O" in cp.args) == optimize, "PRODUCER_ACTUAL_CHILD_MODE")
    expected = expected_metadata(store, object_format, commit, tree)
    require(out.read_bytes() == canonical(expected), "PRODUCER_METADATA_EXACT")
    require(
        set(json.loads(out.read_bytes()))
        == {
            "version",
            "object_format",
            "commit",
            "tree",
            "gitlinks",
            "gitmodules_blob",
        },
        "PRODUCER_METADATA_CLOSED_KEYS",
    )
    require(stat.S_IMODE(os.lstat(out).st_mode) == 0o600, "PRODUCER_OUTPUT_MODE")
    receipt = json.loads(cp.stdout)
    require(cp.stdout == canonical(receipt) + b"\n", "PRODUCER_RECEIPT_CANONICAL")
    require(
        receipt
        == {
            "version": "scope_commitment_receipt.v1",
            "metadata_digest": hashlib.sha256(canonical(expected)).hexdigest(),
            "producer_sha256": hashlib.sha256(PRODUCER.read_bytes()).hexdigest(),
        },
        "PRODUCER_RECEIPT",
    )


def test_producer_end_to_end_with_driver(tmp_path):
    files = {
        "app.py": b"def app():\n    return 1\n",
        "pkg/member.py": b"def member():\n    return 2\n",
    }
    store, commit, tree = trusted_store(tmp_path, files=files)
    cp, out = produce(tmp_path, store, commit, tree)
    require(cp.returncode == 0, "PRODUCER_DRIVER_READY:produce")
    metadata = json.loads(out.read_bytes())
    candidate = tmp_path / "candidate"
    for path, body in files.items():
        put(candidate, path, body)
    for case, expect in (("positive", 0), ("trigger", 1)):
        if case == "trigger":
            put(
                candidate, "pkg/.git", b"gitdir: /nonexistent-" + TOKEN.encode() + b"\n"
            )
        request = {
            "declaration": declaration_v2(commit),
            "source_root": str(candidate),
            "root_metadata": metadata,
            "expected_driver_sha256": hashlib.sha256(DRIVER.read_bytes()).hexdigest(),
        }
        rp = tmp_path / (case + ".json")
        rp.write_text(json.dumps(request), encoding="utf-8")
        dcp = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                str(DRIVER),
                "prepare",
                "--request",
                str(rp),
                "--output",
                str(tmp_path / ("out-" + case)),
            ],
            capture_output=True,
            timeout=30,
        )
        require(
            dcp.returncode == expect,
            "PRODUCER_DRIVER_READY:"
            + case
            + ":"
            + dcp.stderr.decode("utf-8", "replace"),
        )
        if case == "trigger":
            diag = json.loads(dcp.stderr)
            require(
                diag["reason"] == "scope_boundary_uncommitted"
                and diag["path"] == "pkg",
                "PRODUCER_DRIVER_TRIGGER",
            )


REFUSALS = [
    "tree_mismatch",
    "ref_name",
    "abbreviated",
    "nonexistent",
    "blob_as_commit",
    "gitmodules_symlink",
    "gitmodules_directory",
    "relative_git_dir",
]


@pytest.mark.parametrize("case", REFUSALS)
def test_producer_refusals(tmp_path, case, monkeypatch):
    store, commit, tree = trusted_store(tmp_path)
    app = text_out(store, "rev-parse", "HEAD:app.py")
    reason, git_dir = "scope_commitment", str(store)
    if case == "gitmodules_symlink":
        commit, tree = plumbing_commit(
            store,
            [
                ("100644", "blob", app, "app.py"),
                ("120000", "blob", blob(store, b"app.py"), ".gitmodules"),
            ],
        )
    elif case == "gitmodules_directory":
        inner = (
            git(
                store, "mktree", stdin=("100644 blob %s\tinner\n" % app).encode("ascii")
            )
            .decode("ascii")
            .strip()
        )
        commit, tree = plumbing_commit(
            store,
            [
                ("100644", "blob", app, "app.py"),
                ("040000", "tree", inner, ".gitmodules"),
            ],
        )
    elif case == "tree_mismatch":
        tree = app
    elif case == "ref_name":
        commit, reason = "HEAD", "scope_schema"
    elif case == "abbreviated":
        commit, reason = commit[:12], "scope_schema"
    elif case == "nonexistent":
        commit = "0" * len(commit)
    elif case == "blob_as_commit":
        commit = app
    elif case == "relative_git_dir":
        monkeypatch.chdir(tmp_path)
        git_dir, reason = "store.git", "scope_root"
    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(b"untouched\n")
    cp, out = produce(tmp_path, Path(git_dir), commit, tree)
    refused(cp, reason)
    require(
        not os.path.lexists(out) and sentinel.read_bytes() == b"untouched\n",
        "PRODUCER_REFUSAL_" + case,
    )


@pytest.mark.parametrize("optimize", [False, True])
def test_producer_preserves_existing_output(tmp_path, optimize):
    store, commit, tree = trusted_store(tmp_path)
    sentinel = tmp_path / "existing.json"
    sentinel.write_bytes(b"caller-owned\n")
    sentinel.chmod(0o640)
    before = os.lstat(sentinel)
    cp, _ = produce(tmp_path, store, commit, tree, output=sentinel, optimize=optimize)
    refused(cp, "scope_root")
    after = os.lstat(sentinel)
    require(
        (after.st_ino, after.st_dev, stat.S_IMODE(after.st_mode), after.st_size)
        == (before.st_ino, before.st_dev, 0o640, before.st_size)
        and sentinel.read_bytes() == b"caller-owned\n",
        "PRODUCER_EXISTING_OUTPUT_PRESERVED",
    )
    dangling = tmp_path / "dangling.json"
    dangling.symlink_to(tmp_path / "nowhere")
    cp, _ = produce(tmp_path, store, commit, tree, output=dangling, optimize=optimize)
    refused(cp, "scope_root")
    require(
        dangling.is_symlink() and not os.path.lexists(tmp_path / "nowhere"),
        "PRODUCER_DANGLING_OUTPUT_PRESERVED",
    )


def test_producer_no_worktree_dependence(tmp_path):
    store, commit, tree = trusted_store(tmp_path / "controller")
    clean, out = produce(tmp_path, store, commit, tree)
    candidate = tmp_path / "candidate"
    put(candidate, "app.py", b"conflicting = True\n")
    put(candidate, ".git", b"gitdir: /nonexistent-" + TOKEN.encode() + b"\n")
    before = {p: p.read_bytes() for p in candidate.rglob("*") if p.is_file()}
    other, out2 = produce(
        tmp_path, store, commit, tree, output=tmp_path / "second.json", cwd=candidate
    )
    require(
        clean.returncode == 0
        and other.returncode == 0
        and out.read_bytes() == out2.read_bytes(),
        "PRODUCER_NO_WORKTREE_DEPENDENCE",
    )
    require(
        {p: p.read_bytes() for p in candidate.rglob("*") if p.is_file()} == before,
        "PRODUCER_WORKTREE_UNTOUCHED",
    )


# --- Q1/Q2/Q4 refusal ordering ------------------------------------------------------------


class SpyRunnerFactory:
    @staticmethod
    def make(module, store):
        class SpyRunner(module.Runner):
            def git(self, *args):
                self.spied.append(args[0])
                return super().git(*args)

        runner = SpyRunner(str(store))
        runner.spied = []
        return runner


FILESYSTEM_ONLY = {
    "alternates": "objects/info/alternates",
    "dangling_alternates": "objects/info/alternates",
    "http_alternates": "objects/info/http-alternates",
}
CONFIG_CASES = {
    "include": "include.path",
    "include_if": None,
    "alternate_refs_command": "core.alternateRefsCommand",
    "core_worktree": "core.worktree",
    "worktree_config": "extensions.worktreeConfig",
}


@pytest.mark.parametrize(
    "case", list(FILESYSTEM_ONLY) + list(CONFIG_CASES) + ["nonbare"]
)
def test_store_refusals_before_traversal(tmp_path, case):
    module = load_producer()
    store, commit, tree = trusted_store(tmp_path)
    target = tmp_path / ("target-" + TOKEN)
    reason = "scope_commitment"
    if case == "nonbare":
        store, reason = tmp_path / "controller-work", "scope_root"
    elif case == "dangling_alternates":
        (store / "objects/info").mkdir(parents=True, exist_ok=True)
        (store / "objects/info/alternates").symlink_to(target)
    elif case in FILESYSTEM_ONLY:
        (store / "objects/info").mkdir(parents=True, exist_ok=True)
        (store / FILESYSTEM_ONLY[case]).write_text(str(target) + "\n", encoding="utf-8")
    else:
        key = CONFIG_CASES[case] or "includeIf.gitdir:" + str(store) + "/.path"
        git(store, "config", key, str(target))
    runner = SpyRunnerFactory.make(module, store)
    try:
        module.produce(str(store), commit, tree, runner)
        require(False, "STORE_REFUSAL_" + case)
    except module.ScopeRefused as exc:
        require(exc.reason == reason, "STORE_REFUSAL_REASON_" + case)
    expected_calls = ["config"] if case in CONFIG_CASES else []
    require(
        runner.spied == expected_calls,
        "STORE_REFUSAL_BEFORE_TRAVERSAL:" + repr(runner.spied),
    )
    require(not os.path.lexists(target), "STORE_REFUSAL_TARGET_UNTOUCHED")


GITLINK_CASES = {
    "invalid_utf8": [b"\xff\xfe"],
    "backslash_path": [b"a\\b"],
    "casefold_duplicate": [b"Child", b"child"],
}


@pytest.mark.parametrize("case", list(GITLINK_CASES))
def test_gitlink_path_refusals(tmp_path, case):
    module = load_producer()
    store = fake_store(tmp_path)
    recursive = b"".join(
        b"160000 commit " + b"1" * 40 + b"\t" + name + b"\0"
        for name in GITLINK_CASES[case]
    )
    try:
        module.produce(str(store), C1, T1, FakeRunner(recursive=recursive))
        require(False, "GITLINK_REFUSAL_" + case)
    except module.ScopeRefused as exc:
        require(exc.reason == "scope_commitment", "GITLINK_REFUSAL_" + case)


@pytest.mark.parametrize("kind", ["040000 tree", "120000 blob", "160000 commit"])
def test_root_gitmodules_type_refused_before_recursive(tmp_path, kind):
    module = load_producer()
    store = fake_store(tmp_path)
    runner = FakeRunner(root=kind.encode() + b" " + b"4" * 40 + b"\t.gitmodules\0")
    try:
        module.produce(str(store), C1, T1, runner)
        require(False, "ROOT_GITMODULES_REFUSED")
    except module.ScopeRefused as exc:
        require(exc.reason == "scope_commitment", "ROOT_GITMODULES_REFUSED")
    require(
        not any(call[:2] == ("ls-tree", "-r") for call in runner.calls),
        "ROOT_GITMODULES_BEFORE_RECURSIVE",
    )


# --- capture, deadline and cleanup transcripts -------------------------------------------------


@pytest.mark.parametrize("case", ["stdout_only", "stderr_only", "mixed"])
def test_capture_overflow(case):
    module = load_producer()
    sizes = {
        "stdout_only": {"stdout": 25, "stderr": 0},
        "stderr_only": {"stdout": 0, "stderr": 25},
        "mixed": {"stdout": 8, "stderr": 8},
    }[case]
    outcome, combined, requests = transcript(module, sizes, 10, eof=False)
    require(
        outcome == ("refused", "scope_commitment") and combined == 11 and requests,
        "CAPTURE_OVERFLOW_" + case,
    )


def test_capture_exact_cap_eof():
    module = load_producer()
    outcome, combined, _ = transcript(module, {"stdout": 6, "stderr": 4}, 10, eof=True)
    require(outcome == ("eof", b"s" * 6) and combined == 10, "CAPTURE_EXACT_CAP_EOF")


def test_eof_while_leader_alive_reaches_deadline():
    module = load_producer()
    clock = [0.0]
    runner, _ = transcript_runner(module, clock, 0.5)
    runner.deadline = 1.0
    proc = FakeProc(clock, [(0.5, False), (0.5, False)])
    try:
        runner.reap(proc)
        require(False, "EOF_IS_NOT_DEATH")
    except TimeoutError:
        pass
    require(runner.waits == [("reap", 0.5), ("reap", 0.5)], "EOF_IS_NOT_DEATH")


def test_post_deadline_reap_rejected():
    module = load_producer()
    clock = [0.0]
    runner, _ = transcript_runner(module, clock, 0.0625)
    runner.deadline = 1.0
    try:
        runner.reap(FakeProc(clock, [(1.25, True)]))
        require(False, "LATE_REAP_REJECTED")
    except TimeoutError:
        pass
    require(
        runner.waits == [("reap", 0.0625)] and clock[0] == 1.25, "LATE_REAP_REJECTED"
    )


def test_cleanup_exhausted_stages_uncertain():
    module = load_producer()
    clock = [10.0]
    runner, kills = transcript_runner(module, clock, 0.125, 0.5, 0.25)
    cause = module.ScopeRefused("scope_commitment")
    runner.stop_guarded(FakeProc(clock, [(0.125, False)] * 4), cause)
    require(
        kills == [module.signal.SIGTERM, module.signal.SIGKILL]
        and runner.uncertain
        and runner.uncertain_cause is cause
        and clock[0] == 10.5,
        "CLEANUP_EXHAUSTED_UNCERTAIN",
    )


def test_cleanup_group_survives_term_then_kill():
    module = load_producer()
    clock = [20.0]
    runner, kills = transcript_runner(module, clock, 0.125, 0.5, 0.25)
    answers = iter([None, "gone"])

    def probe(pid, sig):
        if next(answers) == "gone":
            raise ProcessLookupError(3, "no such group")

    runner.group_probe = probe
    runner.stop_guarded(
        FakeProc(clock, [(0.125, True)]), module.ScopeRefused("scope_commitment")
    )
    require(
        kills == [module.signal.SIGTERM, module.signal.SIGKILL]
        and not runner.uncertain
        and runner.waits == [("cleanup-wait", 0.125), ("cleanup-sleep", 0.125)],
        "CLEANUP_PROGRESSION",
    )


def test_close_one_attempt_per_pipe_and_cancellation_kept(tmp_path):
    module = load_producer()
    store = fake_store(tmp_path)
    late = KeyboardInterrupt("during close")
    closes = []
    runner = module.Runner(str(store))

    def cancelling_close(pipe):
        closes.append(pipe)
        pipe.close()
        raise late

    runner.closer = cancelling_close
    caught = None
    with PatchedPopen(module):
        try:
            runner.git("rev-parse", "--show-object-format")
        except KeyboardInterrupt as exc:  # synchronous injected cancellation only
            caught = exc
    require(
        caught is late
        and len(closes) == 2
        and runner.cleanup_errors == ["KeyboardInterrupt", "KeyboardInterrupt"],
        "CLOSE_ONCE_CANCELLATION_KEPT",
    )


# --- Q3 / receipt / Q5 lifecycle ---------------------------------------------------------------


def test_q3_uncertain_is_setup_with_cause(tmp_path):
    module = load_producer()
    store = fake_store(tmp_path)
    runner = FakeRunner(fail_config=module.ScopeRefused("scope_commitment"))
    args = type(
        "Args",
        (),
        {
            "git_dir": str(store),
            "commit": C1,
            "expected_tree": T1,
            "output": str(tmp_path / "m.json"),
        },
    )()
    code, out, err, error = module.run(args, runner)
    require(
        code == 2 and out == b"" and err == b"scope_setup:CleanupUncertain\n",
        "Q3_UNCERTAIN_IS_SETUP",
    )
    require(
        isinstance(error, module.CleanupUncertain)
        and isinstance(error.__cause__, module.ScopeRefused),
        "Q3_CAUSE_CHAINED",
    )
    require(not os.path.lexists(tmp_path / "m.json"), "Q3_NO_OUTPUT")


def test_receipt_write_failure_is_setup(tmp_path, monkeypatch):
    module = load_producer()
    written = []

    def emit(fd, data):
        if fd == 1:
            raise OSError(28, "No space left on device")
        written.append((fd, data))

    monkeypatch.setattr(
        module, "run", lambda args, runner: (0, b"receipt\n", b"", None)
    )
    monkeypatch.setattr(module, "emit", emit)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "producer",
            "commit",
            "--git-dir",
            str(tmp_path),
            "--commit",
            C1,
            "--expected-tree",
            T1,
            "--output",
            str(tmp_path / "m.json"),
        ],
    )
    require(
        module.main() == 2 and written == [(2, b"scope_setup:OSError\n")],
        "RECEIPT_WRITE_FAILURE_SETUP",
    )


def test_q5_short_write_prefix_then_removal(tmp_path):
    module = load_producer()
    target = tmp_path / "out.json"
    calls = []

    def short_then_fail(fd, view):
        if not calls:
            calls.append(os.write(fd, bytes(view[:5])))
            return calls[0]
        require(
            os.fstat(fd).st_size == 5 and target.read_bytes() == b"01234",
            "Q5_PREFIX_ON_OPEN_FD",
        )
        raise OSError(28, "No space left on device")

    try:
        module.write_exclusive(target, b"0123456789", write=short_then_fail)
        require(False, "Q5_SHORT_WRITE_FAILURE")
    except OSError as exc:
        require(
            exc.errno == 28 and calls == [5] and not os.path.lexists(target),
            "Q5_SHORT_WRITE_REMOVED",
        )


@pytest.mark.parametrize(
    "branch", ["fstat_fails", "unlink_fails", "close_fails_after_write"]
)
def test_q5_failure_branches(tmp_path, branch):
    module = load_producer()
    target = tmp_path / "out.json"

    def fail(fd, view):
        raise OSError(28, "No space left on device")

    def bad_fstat(fd):
        raise OSError(9, "EBADF")

    def bad_unlink(path):
        raise PermissionError(13, "denied")

    def bad_close(fd):
        os.close(fd)
        raise OSError(5, "EIO")

    kwargs = {
        "fstat_fails": {"write": fail, "fstat": bad_fstat},
        "unlink_fails": {"write": fail, "unlink": bad_unlink},
        "close_fails_after_write": {"close": bad_close},
    }[branch]
    try:
        module.write_exclusive(target, b"{}", **kwargs)
        require(False, "Q5_NEVER_SUCCESS")
    except module.CleanupUncertain as exc:
        require(
            isinstance(exc.__cause__, OSError) and os.path.lexists(target),
            "Q5_UNPROVEN_LEFT_" + branch,
        )


def test_no_fetch_installed_git(tmp_path):
    """Local promisor fixture with a transport-helper sentinel; no network endpoint.

    Permitted-fetch positive must connect the sentinel; GIT_NO_LAZY_FETCH alone (protocol
    permitted) must block it; the product (both protections) must refuse without contact.
    An installed Git that cannot show this is a FAILURE, not a skip. Hidden Git-internal
    process enumeration is not claimed.
    """
    module = load_producer()
    origin, commit, tree = trusted_store(tmp_path / "origin")
    git(origin, "config", "uploadpack.allowFilter", "true")
    contact = tmp_path / ("contacted-" + TOKEN)
    helper = tmp_path / ("upload-pack-" + TOKEN)
    helper.write_text(
        "#!/bin/sh\necho x >> '%s'\nexec git-upload-pack \"$@\"\n" % contact,
        encoding="utf-8",
    )
    helper.chmod(0o700)

    def partial(name):
        dest = tmp_path / name
        git(
            tmp_path,
            "clone",
            "-q",
            "--bare",
            "--filter=tree:0",
            "--no-local",
            "--upload-pack=" + str(helper),
            "file://" + str(origin),
            str(dest),
        )
        git(dest, "config", "remote.origin.uploadpack", str(helper))
        return dest

    def contacts():
        return len(contact.read_bytes().splitlines()) if contact.exists() else 0

    def lazy(store, flag):
        env = module.environment()
        if not flag:
            env.pop("GIT_NO_LAZY_FETCH", None)
        return subprocess.run(
            [
                "git",
                "--git-dir=" + str(store),
                "-c",
                "protocol.file.allow=always",
                "cat-file",
                "-t",
                tree,
            ],
            env=env,
            capture_output=True,
            timeout=30,
        )

    positive = partial("positive.git")
    before = contacts()
    cp = lazy(positive, flag=False)
    require(
        cp.returncode == 0 and contacts() == before + 1,
        "NO_FETCH_PERMITTED_POSITIVE_CONNECTED",
    )
    component = partial("component.git")
    before = contacts()
    cp = lazy(component, flag=True)
    require(
        cp.returncode != 0 and contacts() == before,
        "NO_FETCH_GIT_NO_LAZY_FETCH_COMPONENT",
    )
    product = partial("product.git")
    before = contacts()
    pcp, out = produce(tmp_path, product, commit, tree)
    require(contacts() == before, "PRODUCER_NO_LAZY_FETCH")
    refused(pcp, "scope_commitment")
    require(not os.path.lexists(out), "PRODUCER_NO_LAZY_FETCH_NO_OUTPUT")


def test_no_assert_statements():
    for path in (PRODUCER, Path(__file__)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        require(
            not any(isinstance(n, ast.Assert) for n in ast.walk(tree)),
            "PRODUCER_O_SAFE",
        )


# --- eight mutation triplets -------------------------------------------------------------------

MUTATIONS = {
    "m1_tree_equality": (
        'for suffix, expected in (("^{commit}", commit), ("^{tree}", expected_tree)):',
        'for suffix, expected in (("^{commit}", commit),):',
        "tree_equality",
        "GUARANTEE_TREE_EQUALITY",
    ),
    "m2_inherit_env": (
        "            env=environment(),",
        "            env=dict(os.environ),",
        "hardened_env",
        "GUARANTEE_HARDENED_ENV",
    ),
    "m3_read_allowance": (
        "                    request = min(CHUNK, self.cap - total + 1)",
        "                    request = CHUNK",
        "read_allowance",
        "GUARANTEE_READ_ALLOWANCE",
    ),
    "m4_deadline_refresh": (
        '        self.journal.append((args[0] if args else "", budget))',
        '        self.deadline = self.clock() + WORK_SECONDS\n        budget = self.remaining()\n        self.journal.append((args[0] if args else "", budget))',
        "shared_deadline",
        "GUARANTEE_SHARED_DEADLINE",
    ),
    "m5_leader_only_death": (
        "            try:\n                self.group_probe(proc.pid, 0)\n            except ProcessLookupError:\n                return True\n",
        "            return True\n",
        "group_death",
        "GUARANTEE_GROUP_DEATH_REQUIRED",
    ),
    "m6_cleanup_replaces_first_error": (
        "            try:\n                try:  # noqa: SIM105\n                    self.killer(proc.pid, sig)\n                except ProcessLookupError:\n                    pass\n                if self.wait_group(proc, until):\n                    return\n            except (\n                BaseException\n            ) as later:  # noqa: BLE001 -- recorded; progression continues\n                self.cleanup_errors.append(type(later).__name__)\n",
        "            try:  # noqa: SIM105\n                self.killer(proc.pid, sig)\n            except ProcessLookupError:\n                pass\n            if self.wait_group(proc, until):\n                return\n",
        "first_error",
        "GUARANTEE_FIRST_ERROR_PRESERVED",
    ),
    "m7_no_exclusive_create": (
        "    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC",
        "    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC",
        "exclusive_create",
        "GUARANTEE_EXCLUSIVE_CREATE",
    ),
    "m8_skip_q5_identity": (
        "        if same_created_file(fd, path, fstat=fstat, lstat=lstat):",
        "        if True:",
        "q5_identity",
        "GUARANTEE_Q5_REPLACEMENT_PRESERVED",
    ),
}


def classify(check, module, tmp):
    tmp.mkdir()
    try:
        check(module, tmp)
    except AssertionError as exc:
        return "killed:" + str(exc)
    except BaseException as exc:  # noqa: BLE001 -- recorded as a non-kill outcome
        return "error:" + type(exc).__name__
    return "pass"


@pytest.mark.parametrize("case", list(MUTATIONS))
def test_mutation_triplet(tmp_path, case):
    """Baseline, one semantic mutant and restored copy through the same named checker plus
    an unaffected positive. Only the named guarantee assertion counts as a kill."""
    anchor, replacement, guarantee, name = MUTATIONS[case]
    check, positive = GUARANTEES[guarantee]
    source = PRODUCER.read_text(encoding="utf-8")
    original = hashlib.sha256(source.encode("utf-8")).hexdigest()
    require(source.count(anchor) == 1, "MUTATION_ANCHOR_UNIQUE")
    texts = {
        "baseline": source,
        "mutant": source.replace(anchor, replacement),
        "restored": source,
    }
    results = {}
    for role, text in texts.items():
        path = tmp_path / role / "governed_scope_commitment.py"
        path.parent.mkdir()
        path.write_text(text, encoding="utf-8")
        compile(text, str(path), "exec")
        module = load_producer(path, "mutation_%s_%s" % (case, role))
        require(module.__file__ == str(path), "MUTATION_MODULE_PATH")
        results[role] = (
            classify(check, module, tmp_path / role / "check"),
            classify(positive, module, tmp_path / role / "positive"),
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )
    record = {
        "case": case,
        "optimize": sys.flags.optimize,
        "original": original,
        "results": results,
    }
    (tmp_path / "triplet.json").write_text(json.dumps(record), encoding="utf-8")
    require(
        results["baseline"][:2] == ("pass", "pass"),
        "MUTATION_BASELINE_PASSES:" + repr(results["baseline"]),
    )
    require(
        results["mutant"][0] == "killed:" + name,
        "MUTATION_KILLED_BY_NAMED_CHECK:" + repr(results["mutant"]),
    )
    require(
        results["mutant"][1] == "pass",
        "MUTATION_POSITIVE_UNAFFECTED:" + repr(results["mutant"]),
    )
    require(
        results["restored"][:2] == ("pass", "pass")
        and results["restored"][2] == original
        and hashlib.sha256(PRODUCER.read_bytes()).hexdigest() == original,
        "MUTATION_RESTORED_IDENTICAL",
    )
