"""Opt-in committed_boundary.v1 conformance (treesitter-chunker#512).

DRAFT, PLANNED_UNRUN. Real child processes, real git plumbing oracles and a
PID/fd-joined strace oracle. Independent of tests/test_governed_scope.py.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="governed driver has a Linux validation tier"
)

DRIVER = Path(__file__).resolve().parents[1] / "tools/governed_scope.py"
TOKEN = "tok512x"
MARKER_HOOK = "                                marker = True"


def require(condition, name):
    if not condition:
        raise AssertionError(name)


def git_env():
    env = dict(
        os.environ,
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_SYSTEM=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="fixture",
        GIT_AUTHOR_EMAIL="fixture@example.invalid",
        GIT_AUTHOR_DATE="2026-01-01T00:00:00Z",
        GIT_COMMITTER_NAME="fixture",
        GIT_COMMITTER_EMAIL="fixture@example.invalid",
        GIT_COMMITTER_DATE="2026-01-01T00:00:00Z",
    )
    for key in list(env):
        if key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")) or key in (
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_INDEX_FILE",
            "GIT_CONFIG_COUNT",
        ):
            env.pop(key)
    return env


def git(root, *args):
    return subprocess.check_output(
        [
            "git",
            "--no-replace-objects",
            "-c",
            "core.hooksPath=" + os.devnull,
            "-c",
            "commit.gpgsign=false",
            "-C",
            str(root),
            *args,
        ],
        env=git_env(),
        timeout=20,
    )


def put(root, path, body=b"def f():\n    return 1\n"):
    p = root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    return p


def gitmodules_text(paths):
    return "".join(
        '[submodule "%s"]\n\tpath = %s\n\turl = ./%s\n' % (p, p, p) for p in paths
    ).encode()


def committed_repo(root, files, *, object_format="sha1", gitlinks=None, real=()):
    """Commit files plus gitlinks; `real` gitlinks are initialized nested repos."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "--object-format=" + object_format)
    for path, body in files.items():
        put(root, path, body)
    if files:
        git(root, "add", "--", *files)
    links = dict(gitlinks or {})
    for path in real:
        child = root / path
        child.mkdir(parents=True)
        git(child, "init", "-q", "--object-format=" + object_format)
        put(child, "inner.py")
        git(child, "add", "--", "inner.py")
        git(child, "commit", "-q", "-m", "child")
        links[path] = git(child, "rev-parse", "HEAD").decode().strip()
    for path, oid in links.items():
        git(root, "update-index", "--add", "--cacheinfo", "160000,%s,%s" % (oid, path))
    git(root, "commit", "-q", "--allow-empty", "-m", "fixture")
    return (
        git(root, "rev-parse", "HEAD").decode().strip(),
        git(root, "rev-parse", "HEAD^{tree}").decode().strip(),
    )


def blob_id_oracle(object_format, body):
    return hashlib.new(object_format, b"blob %d\0" % len(body) + body).hexdigest()


def expected_metadata(root, object_format="sha1"):
    """Independent oracle from git plumbing; never from the driver."""
    rows = git(root, "ls-tree", "-r", "-z", "--full-tree", "HEAD").split(b"\0")
    gitlinks = []
    for row in filter(None, rows):
        meta, path = row.split(b"\t", 1)
        mode, kind, oid = meta.split(b" ")
        if mode == b"160000":
            require(kind == b"commit", "ORACLE_GITLINK_KIND")
            gitlinks.append({"path": path.decode(), "object_id": oid.decode()})
    root_rows = git(root, "ls-tree", "-z", "--full-tree", "HEAD").split(b"\0")
    blob = None
    for row in filter(None, root_rows):
        meta, path = row.split(b"\t", 1)
        if path == b".gitmodules":
            blob = meta.split(b" ")[2].decode()
            body = git(root, "cat-file", "blob", blob)
            require(
                blob == blob_id_oracle(object_format, body)
                and blob
                == git(root, "hash-object", "--", ".gitmodules").decode().strip(),
                "BLOB_ID_ORACLE",
            )
    return {
        "version": "scope_root_metadata.v2",
        "object_format": object_format,
        "commit": git(root, "rev-parse", "HEAD").decode().strip(),
        "tree": git(root, "rev-parse", "HEAD^{tree}").decode().strip(),
        "gitlinks": sorted(gitlinks, key=lambda g: g["path"]),
        "gitmodules_blob": blob,
    }


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


def declaration_v1():
    d = declaration_v2("fixture-v1")
    del d["policy_version"], d["boundary_transitions"]
    d["version"] = "governed_scope.v1"
    return d


STRACE_SET = "trace=%file,read,pread64,readv,getdents64,close,dup,dup2,dup3,fcntl"


def run(tmp, root, d, m, *, trace=False, optimize=False, driver=DRIVER, env=None):
    request = {
        "declaration": d,
        "source_root": str(root),
        "root_metadata": m,
        "expected_driver_sha256": hashlib.sha256(driver.read_bytes()).hexdigest(),
    }
    tmp.mkdir(parents=True, exist_ok=True)
    rp = tmp / "request.json"
    rp.write_text(json.dumps(request))
    flags = ["-I", "-S"] + (["-O"] if optimize else [])
    argv = [sys.executable, *flags, str(driver), "prepare", "--request", str(rp)]
    argv += ["--output", str(tmp / "output")]
    if trace:
        argv = ["strace", "-f", "-yy", "-o", str(tmp / "trace.log"), "-e", STRACE_SET]
        argv += [sys.executable, *flags, str(driver), "prepare", "--request", str(rp)]
        argv += ["--output", str(tmp / "output")]
    cp = subprocess.run(argv, capture_output=True, timeout=20, env=env)
    return cp, tmp / "output"


def err(cp):
    """Diagnostic-only text of child stderr; never fails on undecodable bytes."""
    return cp.stderr.decode("utf-8", "replace")


def trace_text(out):
    """Lossless, locale-independent text of a retained strace log."""
    return (out.parent / "trace.log").read_text(
        encoding="utf-8", errors="surrogateescape"
    )


def refusal(cp, reason, path="<any>"):
    require(cp.returncode == 1, "TYPED_REFUSAL_EXIT:" + err(cp))
    diag = json.loads(cp.stderr)
    require(diag["version"] == "scope_diagnostic.v1", "DIAGNOSTIC_ENVELOPE")
    require(diag["reason"] == reason, "TYPED_REFUSAL_REASON:" + diag["reason"])
    require(path == "<any>" or diag["path"] == path, "TYPED_REFUSAL_PATH")
    require(not cp.stdout, "REFUSAL_NO_SUCCESS")


def selection(out):
    return json.loads((out / "selection.json").read_bytes())


def opaque(out):
    return [(r["path"], r["reason"]) for r in selection(out)["opaque_boundaries"]]


# --- PID/fd-joined strace oracle -------------------------------------------------

LINE = re.compile(r"^(\d+) +(\w+)\((.*)\) += (-?\d+|\?)(?:<([^>]*)>)?")
FD = re.compile(r"^(-?\d+|AT_FDCWD)(?:<([^>]*)>)?")
STR = re.compile(r'^"((?:[^"\\]|\\.)*)"')
# Only these calls carry a string filesystem operand after the fd; data payloads of
# read/pread64/readv are never decoded or interpreted as paths.
PATH_AT = ("openat", "newfstatat", "readlinkat", "statx")


def _decode(raw):
    """Decode a strace C-escaped path operand to str losslessly (surrogateescape)."""
    data = raw.encode("utf-8", "surrogateescape").decode("unicode_escape")
    return data.encode("latin-1").decode("utf-8", "surrogateescape")


def parse_trace(text):
    """Yield (pid, call, args, result, result_path); joins unfinished/resumed."""
    pending = {}
    for raw in text.splitlines():
        m = re.match(r"^(\d+) +(.*)$", raw)
        if not m:
            continue
        pid, body = m.groups()
        if body.endswith("<unfinished ...>"):
            pending[pid] = body[: -len("<unfinished ...>")].rstrip()
            continue
        resumed = re.match(r"^<\.\.\. \w+ resumed>(.*)$", body)
        if resumed:
            body = pending.pop(pid, "") + resumed.group(1)
        hit = LINE.match(pid + " " + body)
        if hit:
            yield hit.groups()


def _fd_arg(args):
    hit = FD.match(args)
    return (hit.group(1), hit.group(2)) if hit else (None, None)


def _str_arg(args):
    rest = args.split(",", 1)[1].lstrip() if "," in args else ""
    hit = STR.match(rest)
    return _decode(hit.group(1)) if hit else None


def _under(path, base):
    return path == base or path.startswith(base + "/")


def trace_violations(text, forbidden, markers=(), outside=()):
    """Return violations; `forbidden` subtrees allow only their own entry lstat.

    `markers` directories additionally allow: one O_DIRECTORY|O_NOFOLLOW open,
    one fd-relative no-follow `.git` stat, fstat/fcntl bookkeeping and close.
    Anything else naming them or below them (listing, content, marker open,
    readlink, descendants) is a violation. `outside` paths must never be named.
    """
    fds, opened, stats, out = {}, {}, {}, []
    for pid, call, args, result, rpath in parse_trace(text):
        table = fds.setdefault(pid, {})
        fd, fdpath = _fd_arg(args)
        if fd not in (None, "AT_FDCWD") and fdpath and fd in table:
            if table[fd] != fdpath:
                out.append(("FD_JOIN_MISMATCH", pid, call, fd, fdpath))
        base = fdpath or table.get(fd)
        name = _str_arg(args) if call in PATH_AT else None
        target = None
        if call in PATH_AT and name is not None:
            target = name if name.startswith("/") else (base or "") + "/" + name
            if name == "" and "AT_EMPTY_PATH" in args:
                target, call = base, "fstat"
        elif (
            call in ("open", "stat", "lstat", "readlink", "access") and args[:1] == '"'
        ):
            target = _decode(STR.match(args).group(1))
        elif call in ("read", "pread64", "readv", "getdents64", "fstat", "close"):
            target = base
        elif call in ("dup", "dup2", "dup3", "fcntl"):
            target = base
            if result not in ("?", "-1") and int(result) >= 0 and base:
                if call != "fcntl" or "F_DUPFD" in args:
                    table[result] = base
        if call in ("open", "openat") and result not in ("?",) and int(result) >= 0:
            table[result] = rpath or target
        if call == "close" and fd in table:
            table.pop(fd)
        if not target:
            continue
        for path in outside:
            if _under(target, path):
                out.append(("OUTSIDE", pid, call, target))
        for path in forbidden:
            entry_stat = (
                target == path
                and call in ("newfstatat", "statx")
                and "AT_SYMLINK_NOFOLLOW" in args
            )
            if _under(target, path) and not entry_stat:
                out.append(("FORBIDDEN", pid, call, target))
        for path in markers:
            if not _under(target, path):
                continue
            key = (pid, path)
            if (
                target == path
                and call in ("newfstatat", "statx")
                and "AT_SYMLINK_NOFOLLOW" in args
            ):
                continue
            if target == path and call in ("openat", "open"):
                ok = "O_DIRECTORY" in args and "O_NOFOLLOW" in args
                opened[key] = opened.get(key, 0) + 1
                if not ok or opened[key] > 1:
                    out.append(("MARKER_DIR_OPEN", pid, call, target))
                continue
            if target == path and call in ("fstat", "close", "fcntl", "dup", "dup3"):
                continue
            if (
                target == path + "/.git"
                and call in ("newfstatat", "statx")
                and "AT_SYMLINK_NOFOLLOW" in args
                and base == path
            ):
                stats[key] = stats.get(key, 0) + 1
                if stats[key] > 1:
                    out.append(("MARKER_STAT_REPEAT", pid, call, target))
                continue
            out.append(("MARKER", pid, call, target))
    return out


def test_trace_oracle_unit_vectors():
    m = "/r/pkg"
    ok = (
        '7 newfstatat(3</r>, "pkg", {st_mode=S_IFDIR}, AT_SYMLINK_NOFOLLOW) = 0\n'
        '7 openat(3</r>, "pkg", O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_DIRECTORY)'
        " = 4</r/pkg>\n"
        '7 newfstatat(4</r/pkg>, ".git", {st_mode=S_IFREG}, AT_SYMLINK_NOFOLLOW)'
        " = 0\n"
        "7 close(4</r/pkg>) = 0\n"
        '7 write(2</dev/pts/0>, "pkg tok512x /r/pkg/.git", 23) = 23'
    )
    require(trace_violations(ok, (), (m,)) == [], "ORACLE_PERMITS_METADATA")
    bad = {
        "getdents": "7 getdents64(4</r/pkg>, 0x0, 32768) = 48",
        "marker_open": '7 openat(4</r/pkg>, ".git", O_RDONLY) = 5</r/pkg/.git>',
        "marker_read": '7 read(5</r/pkg/.git>, "gitdir", 64) = 6',
        "readlink": '7 readlinkat(4</r/pkg>, ".git", "x", 4096) = 1',
        "descendant": '7 openat(4</r/pkg>, "member.py", O_RDONLY) = 5</r/pkg/member.py>',
        "second_open": '7 openat(3</r>, "pkg", O_RDONLY|O_NOFOLLOW|O_DIRECTORY)'
        " = 6</r/pkg>",
    }
    prefix = ok.rsplit("\n", 2)[0].rsplit("\n", 1)[0]
    for name, line in bad.items():
        require(
            trace_violations(prefix + "\n" + line, (), (m,)) != [],
            "ORACLE_FORBIDS_" + name,
        )
    # dup/fcntl joins: a duplicated fd without a decoded path still maps to pkg.
    dup = prefix + "\n7 fcntl(4</r/pkg>, F_DUPFD_CLOEXEC, 0) = 9\n"
    require(
        trace_violations(dup + "7 getdents64(9, 0x0, 32768) = 48", (), (m,)) != [],
        "ORACLE_JOINS_FCNTL_DUP",
    )
    # PID scoping: fd 4 in another process is not pkg.
    other = prefix + "\n8 getdents64(4, 0x0, 32768) = 48"
    require(trace_violations(other, (), (m,)) == [], "ORACLE_PID_SCOPED")
    # Forbidden subtrees allow only their entry lstat.
    entry = '7 newfstatat(3</r>, "vendor", {}, AT_SYMLINK_NOFOLLOW) = 0'
    require(trace_violations(entry, ("/r/vendor",)) == [], "ORACLE_ENTRY_STAT")
    deep = '7 newfstatat(3</r>, "vendor/.git", {}, AT_SYMLINK_NOFOLLOW) = -1'
    require(trace_violations(deep, ("/r/vendor",)) != [], "ORACLE_NO_DEEP_STAT")
    split = (
        '7 openat(3</r>, "vendor", O_RDONLY <unfinished ...>\n'
        "7 <... openat resumed>) = 5</r/vendor>"
    )
    require(trace_violations(split, ("/r/vendor",)) != [], "ORACLE_RESUMED")


def strace_available():
    require(shutil.which("strace") is not None, "STRACE_REQUIRED_NONPASS")
    require(shutil.which("git") is not None, "GIT_REQUIRED_NONPASS")


# --- fixtures ----------------------------------------------------------------------

FILES = {
    "app.py": b"def app():\n    return 1\n",
    "pkg/member.py": b"def member():\n    return 2\n",
    "vendor/sentinel.py": b"SENTINEL_" + TOKEN.encode() + b"\n",
    ".gitmodules": gitmodules_text(["child", "missing"]),
}


def positive_repo(root):
    commit, tree = committed_repo(
        root, FILES, gitlinks={"missing": "b" * 40}, real=("child",)
    )
    return commit, tree, expected_metadata(root)


def test_v2_committed_positive(tmp_path):
    strace_available()
    root = tmp_path / "src"
    commit, _, m = positive_repo(root)
    results = []
    for optimize in (False, True):
        cp, out = run(
            tmp_path / ("r%d" % optimize),
            root,
            declaration_v2(commit),
            m,
            trace=True,
            optimize=optimize,
        )
        require(cp.returncode == 0, "V2_COMMITTED_READY:" + err(cp))
        sel = selection(out)
        require(
            [r["path"] for r in sel["included_files"]] == ["app.py", "pkg/member.py"],
            "V2_LITERAL_MEMBERSHIP",
        )
        require(
            opaque(out)
            == [
                ("child", "submodule"),
                ("missing", "submodule"),
                ("vendor", "vendored"),
            ],
            "V2_OPAQUE",
        )
        require(
            {r["path"] for r in sel["extraction_exclusions"]}
            == {".git", ".gitmodules"},
            "V2_EXCLUSIONS",
        )
        receipt = json.loads((out / "selection-receipt.json").read_bytes())
        require(
            sel["version"] == "scope_selection.v2"
            and sel["policy_version"] == "committed_boundary.v1"
            and receipt["version"] == "scope_receipt.v2",
            "V2_VERSIONS",
        )
        require(sel["source_revision"] == commit, "V2_SOURCE_REVISION")
        canon = json.dumps(
            m, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        require(
            receipt["metadata_digest"] == hashlib.sha256(canon).hexdigest(),
            "V2_METADATA_DIGEST",
        )
        r = str(root.resolve())
        require(
            trace_violations(
                trace_text(out),
                (r + "/child", r + "/missing", r + "/vendor"),
            )
            == [],
            "V2_NO_EXCLUDED_READ",
        )
        results.append(
            (
                (out / "selection.json").read_bytes(),
                (out / "selection-receipt.json").read_bytes(),
            )
        )
    require(results[0] == results[1], "V2_OPT_PARITY")


def test_v2_sha256_object_format(tmp_path):
    root = tmp_path / "src"
    files = {"app.py": b"x = 1\n", ".gitmodules": gitmodules_text(["dep"])}
    commit, _ = committed_repo(
        root, files, object_format="sha256", gitlinks={"dep": "c" * 64}
    )
    m = expected_metadata(root, "sha256")
    require(
        len(m["commit"]) == len(m["tree"]) == len(m["gitmodules_blob"]) == 64,
        "V2_SHA256_LENGTHS",
    )
    cp, out = run(tmp_path / "r", root, declaration_v2(commit), m)
    require(cp.returncode == 0, "V2_SHA256_BLOB_ID:" + err(cp))


MARKERS = ("gitfile_nonexistent", "gitfile_malformed", "empty_dir", "real_nested_repo")
MARKERS += ("symlink_dangling", "fifo")


def add_marker(root, case):
    pkg = root / "pkg"
    if case == "gitfile_nonexistent":
        put(pkg, ".git", b"gitdir: /nonexistent-" + TOKEN.encode() + b"\n")
    elif case == "gitfile_malformed":
        put(pkg, ".git", b"\xff\x00" + TOKEN.encode())
    elif case == "empty_dir":
        (pkg / ".git").mkdir()
    elif case == "real_nested_repo":
        git(pkg, "init", "-q")
        put(pkg, "inner_" + TOKEN + ".py")
        git(pkg, "add", "--", "inner_" + TOKEN + ".py")
        git(pkg, "commit", "-q", "-m", "inner")
    elif case == "symlink_dangling":
        (pkg / ".git").symlink_to("/nonexistent-" + TOKEN)
    elif case == "fifo":
        os.mkfifo(pkg / ".git")


@pytest.mark.parametrize("case", MARKERS)
def test_v2_uncommitted_marker_refuses_without_read(tmp_path, case):
    strace_available()
    root = tmp_path / "src"
    commit, tree, m = positive_repo(root)
    add_marker(root, case)
    require(
        git(root, "rev-parse", "HEAD").decode().strip() == commit
        and git(root, "rev-parse", "HEAD^{tree}").decode().strip() == tree,
        "V2_METADATA_UNCHANGED",
    )
    r = str(root.resolve())
    for optimize in (False, True):
        cp, out = run(
            tmp_path / ("r%d" % optimize),
            root,
            declaration_v2(commit),
            m,
            trace=True,
            optimize=optimize,
        )
        refusal(cp, "scope_boundary_uncommitted", "pkg")
        sel = selection(out)
        receipt = json.loads((out / "selection-receipt.json").read_bytes())
        require(
            sel["status"] == "blocked"
            and sel["included_files"] == []
            and sel["blockers"]
            == receipt["refusal_reasons"]
            == ["scope_boundary_uncommitted"]
            and not (out / "stage").exists(),
            "V2_BLOCKED_RECEIPT",
        )
        text = trace_text(out)
        require(
            trace_violations(
                text,
                (r + "/child", r + "/missing", r + "/vendor"),
                (r + "/pkg",),
                ("/nonexistent-" + TOKEN,),
            )
            == [],
            "V2_MARKER_NO_READ",
        )


def test_v1_declared_limit_unchanged_on_trigger(tmp_path):
    strace_available()
    root = tmp_path / "src"
    put(root, "app.py")
    put(root, "pkg/member.py")
    add_marker(root, "gitfile_nonexistent")
    m = {"source_revision": "fixture-v1", "submodule_paths": []}
    cp, out = run(tmp_path / "r", root, declaration_v1(), m, trace=True)
    require(cp.returncode == 0, "V1_READY")
    require(("pkg", "nested_repository") in opaque(out), "V1_DECLARED_LIMIT_UNCHANGED")
    require(
        "pkg/member.py" not in [r["path"] for r in selection(out)["included_files"]],
        "V1_DECLARED_LIMIT_MEMBERSHIP",
    )
    r = str(root.resolve())
    text = trace_text(out)
    require(
        trace_violations(text, (), (r + "/pkg",), ("/nonexistent-" + TOKEN,)) == [],
        "V1_DECLARED_LIMIT_NO_READ",
    )


TRANSITION = {
    "prefix": "pkg",
    "decision_ref": "fixture-ratified",
    "kind": "nested_repository",
}


def test_v2_ratified_transition(tmp_path):
    strace_available()
    root = tmp_path / "src"
    commit, _, m = positive_repo(root)
    add_marker(root, "real_nested_repo")
    cp, out = run(
        tmp_path / "r",
        root,
        declaration_v2(commit, transitions=[TRANSITION]),
        m,
        trace=True,
    )
    require(cp.returncode == 0, "V2_TRANSITION_RATIFIED:" + err(cp))
    require(("pkg", "nested_repository") in opaque(out), "V2_TRANSITION_OPAQUE")
    require(
        [r["path"] for r in selection(out)["included_files"]] == ["app.py"],
        "V2_TRANSITION_MEMBERSHIP",
    )
    base = tmp_path / "base-src"
    base_commit, _, base_m = positive_repo(base)
    cp2, out2 = run(tmp_path / "b", base, declaration_v2(base_commit), base_m)
    require(cp2.returncode == 0, "V2_TRANSITION_BASE_READY")
    require(
        selection(out)["declaration_digest"] != selection(out2)["declaration_digest"],
        "V2_TRANSITION_DIGEST",
    )
    r = str(root.resolve())
    text = trace_text(out)
    require(
        trace_violations(text, (r + "/child", r + "/vendor"), (r + "/pkg",)) == [],
        "V2_TRANSITION_NO_READ",
    )


@pytest.mark.parametrize(
    ("case", "reason", "blocked"),
    [
        ("unused", "scope_boundary_transition", True),
        ("overlaps_rule", "scope_schema", False),
        ("overlaps_transition", "scope_schema", False),
        ("overlaps_gitlink", "scope_metadata", False),
        ("parent_path", "scope_path", False),
        ("kind_submodule", "scope_schema", False),
    ],
)
def test_v2_transition_refusals(tmp_path, case, reason, blocked):
    root = tmp_path / "src"
    commit, _, m = positive_repo(root)
    t = dict(TRANSITION)
    rules = []
    transitions = [t]
    if case == "overlaps_rule":
        rules = [
            {
                "prefix": "pkg",
                "decision_ref": "r",
                "disposition": "exclude",
                "reason": "unclassified",
            }
        ]
    elif case == "overlaps_transition":
        transitions = [t, dict(t, prefix="pkg/sub")]
    elif case == "overlaps_gitlink":
        t["prefix"] = "child/inner"
    elif case == "parent_path":
        t["prefix"] = "../x"
    elif case == "kind_submodule":
        t["kind"] = "submodule"
    cp, out = run(
        tmp_path / "r",
        root,
        declaration_v2(commit, rules=rules, transitions=transitions),
        m,
    )
    refusal(cp, reason)
    require(out.exists() == blocked, "V2_TRANSITION_REFUSAL_" + case)
    if blocked:
        require(selection(out)["status"] == "blocked", "V2_TRANSITION_REFUSAL_" + case)


@pytest.mark.parametrize(
    "case",
    ["dirty", "untracked_null", "deleted", "extra_path", "missing_path", "symlink"],
)
def test_v2_gitmodules_binding_refusals(tmp_path, case):
    root = tmp_path / "src"
    if case == "untracked_null":
        files = {"app.py": b"x\n"}
    elif case == "extra_path":
        files = {"app.py": b"x\n", ".gitmodules": gitmodules_text(["child", "other"])}
    elif case == "missing_path":
        files = {"app.py": b"x\n", ".gitmodules": gitmodules_text([])}
    else:
        files = {"app.py": b"x\n", ".gitmodules": gitmodules_text(["child"])}
    links = {} if case == "untracked_null" else {"child": "d" * 40}
    commit, _ = committed_repo(root, files, gitlinks=links)
    m = expected_metadata(root)
    gm = root / ".gitmodules"
    if case == "dirty":
        gm.write_bytes(gm.read_bytes() + b"\n")
    elif case == "untracked_null":
        gm.write_bytes(gitmodules_text([]))
    elif case == "deleted":
        gm.unlink()
    elif case == "symlink":
        body = gm.read_bytes()
        gm.unlink()
        put(tmp_path, "gm-target", body)
        gm.symlink_to(tmp_path / "gm-target")
    cp, out = run(tmp_path / "r", root, declaration_v2(commit), m)
    refusal(cp, "scope_metadata", ".gitmodules")
    require(not out.exists(), "V2_GITMODULES_" + case)


def _schema_case(case, d, m):
    if case == "revision_mismatch":
        d["source_revision"] = "f" * 40
    elif case == "abbreviated":
        d["source_revision"] = d["source_revision"][:12]
    elif case == "uppercase":
        m["commit"] = m["commit"].upper()
    elif case == "wrong_length":
        m["tree"] += "0"
    elif case == "md5":
        m["object_format"] = "md5"
    elif case == "unhashable_format":
        m["object_format"] = ["sha1"]
    elif case == "extra_key":
        m["extra"] = None
    elif case == "v1_metadata":
        m = {"source_revision": d["source_revision"], "submodule_paths": []}
    elif case == "v1_declaration":
        d = declaration_v1()
    elif case == "policy":
        d["policy_version"] = "single_repo.v1"
    elif case == "casefold_gitlinks":
        m["gitlinks"] = [
            {"path": "Dep", "object_id": "e" * 40},
            {"path": "dep", "object_id": "e" * 40},
        ]
    return d, m


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("revision_mismatch", "scope_metadata"),
        ("abbreviated", "scope_schema"),
        ("uppercase", "scope_schema"),
        ("wrong_length", "scope_schema"),
        ("md5", "scope_schema"),
        ("unhashable_format", "scope_schema"),
        ("extra_key", "scope_schema"),
        ("v1_metadata", "scope_schema"),
        ("v1_declaration", "scope_schema"),
        ("policy", "scope_schema"),
        ("casefold_gitlinks", "scope_path"),
    ],
)
def test_v2_metadata_and_schema_refusals(tmp_path, case, reason):
    root = tmp_path / "src"
    commit, _ = committed_repo(root, {"app.py": b"x\n"})
    d, m = _schema_case(case, declaration_v2(commit), expected_metadata(root))
    if case == "v1_declaration":
        m = expected_metadata(root)
    cp, out = run(tmp_path / "r", root, d, m)
    refusal(cp, reason)
    require(not out.exists(), "V2_SCHEMA_" + case)


@pytest.mark.parametrize("value", [None, [], "governed_scope.v2", 2])
@pytest.mark.parametrize("optimize", [False, True])
def test_v2_dispatch_typed_refusal(tmp_path, value, optimize):
    root = tmp_path / "src"
    root.mkdir()
    for meta in (
        {"source_revision": "fixture-v1", "submodule_paths": []},
        {"version": "scope_root_metadata.v2"},
    ):
        tmp = tmp_path / ("r%d" % len(meta))
        cp, out = run(tmp, root, value, meta, optimize=optimize)
        refusal(cp, "scope_schema", None)
        require(not out.exists(), "V2_DISPATCH_TYPED_REFUSAL")


def test_v2_markers_in_non_traversed_dirs(tmp_path):
    strace_available()
    root = tmp_path / "src"
    files = dict(FILES)
    files["third/lib.py"] = b"x\n"
    files["build/x/gen.py"] = b"x\n"
    commit, _ = committed_repo(
        root, files, gitlinks={"missing": "b" * 40}, real=("child",)
    )
    m = expected_metadata(root)
    for path in ("vendor", "third", "build/x"):
        put(root, path + "/.git", b"gitdir: /nonexistent-" + TOKEN.encode() + b"\n")
    rule = {
        "prefix": "third",
        "decision_ref": "r",
        "disposition": "external",
        "reason": "vendored",
    }
    cp, out = run(
        tmp_path / "r", root, declaration_v2(commit, rules=[rule]), m, trace=True
    )
    require(cp.returncode == 0, "V2_NON_TRAVERSED_READY:" + err(cp))
    require(
        ("vendor", "vendored") in opaque(out)
        and ("third", "vendored") in opaque(out)
        and ("child", "submodule") in opaque(out)
        and {"path": "build", "reason": "build_output"}
        in selection(out)["extraction_exclusions"],
        "V2_NON_TRAVERSED_CLASSIFICATION",
    )
    r = str(root.resolve())
    text = trace_text(out)
    require(
        trace_violations(
            text,
            (r + "/vendor", r + "/third", r + "/build", r + "/child"),
            (),
            ("/nonexistent-" + TOKEN,),
        )
        == [],
        "V2_NO_STAT_EXCLUDED_MARKER",
    )


def test_v2_root_pointer_and_content_limit(tmp_path):
    strace_available()
    root = tmp_path / "src"
    outside = tmp_path / "outside-gitdir"
    root.mkdir()
    subprocess.run(
        ["git", "init", "-q", "--separate-git-dir", str(outside), str(root)],
        env=git_env(),
        check=True,
        timeout=20,
    )
    commit, _ = committed_repo(root, {"app.py": b"x = 1\n"})
    m = expected_metadata(root)
    put(root, "app.py", b"x = 2\n")
    put(root, "new.py", b"y = 1\n")
    cp, out = run(tmp_path / "r", root, declaration_v2(commit), m, trace=True)
    require(cp.returncode == 0, "V2_CONTENT_NOT_BOUND:" + err(cp))
    files = {r["path"]: r["sha256"] for r in selection(out)["included_files"]}
    require(
        files
        == {
            "app.py": hashlib.sha256(b"x = 2\n").hexdigest(),
            "new.py": hashlib.sha256(b"y = 1\n").hexdigest(),
        },
        "V2_CONTENT_NOT_BOUND",
    )
    r = str(root.resolve())
    text = trace_text(out)
    require(
        trace_violations(text, (r + "/.git",), (), (str(outside.resolve()),)) == [],
        "V2_ROOT_POINTER_NOT_READ",
    )


def test_v2_relocation_and_permutation(tmp_path):
    outputs = []
    for n, seed in enumerate(("1", "17")):
        root = tmp_path / ("src%d" % n)
        commit, _, m = positive_repo(root)
        add_marker(root, "empty_dir")
        transitions = [TRANSITION, dict(TRANSITION, prefix="zz")]
        put(root, "zz/.git", b"gitdir: /nonexistent\n")
        if n:
            m["gitlinks"].reverse()
            transitions.reverse()
        env = dict(os.environ, PYTHONHASHSEED=seed)
        cp, out = run(
            tmp_path / ("r%d" % n),
            root,
            declaration_v2(commit, transitions=transitions),
            m,
            env=env,
        )
        require(cp.returncode == 0, "V2_RELOCATION_READY:" + err(cp))
        outputs.append(
            (
                (out / "selection.json").read_bytes(),
                (out / "selection-receipt.json").read_bytes(),
            )
        )
    require(outputs[0] == outputs[1], "V2_RELOCATION")


@pytest.mark.parametrize(
    ("mutant", "insert"),
    [
        (
            "marker_read",
            '\n                                os.read(os.open(".git", os.O_RDONLY'
            " | os.O_NONBLOCK, dir_fd=child_fd), 64)",
        ),
        ("marker_listdir", "\n                                os.listdir(child_fd)"),
    ],
)
def test_v2_oracle_detects_marker_read_mutant(tmp_path, mutant, insert):
    strace_available()
    root = tmp_path / "src"
    commit, _, m = positive_repo(root)
    add_marker(root, "gitfile_nonexistent")
    code = DRIVER.read_text(encoding="utf-8")
    require(code.count(MARKER_HOOK) == 1, "V2_MARKER_HOOK_UNIQUE")
    driver = tmp_path / ("mutant-" + mutant + ".py")
    driver.write_text(code.replace(MARKER_HOOK, MARKER_HOOK + insert), encoding="utf-8")
    r = str(root.resolve())
    results = {}
    for name, path in (("original", DRIVER), ("mutant", driver)):
        cp, out = run(
            tmp_path / name, root, declaration_v2(commit), m, trace=True, driver=path
        )
        refusal(cp, "scope_boundary_uncommitted", "pkg")
        text = trace_text(out)
        results[name] = trace_violations(
            text, (r + "/child", r + "/vendor"), (r + "/pkg",)
        )
    require(results["original"] == [], "V2_ORACLE_ORIGINAL_CLEAN")
    require(
        any(v[2] in ("openat", "read", "getdents64") for v in results["mutant"]),
        "V2_ORACLE_DISCRIMINATES",
    )


def test_v2_no_assert_statements():
    for path in (DRIVER, Path(__file__)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        require(not any(isinstance(n, ast.Assert) for n in ast.walk(tree)), "V2_O_SAFE")
