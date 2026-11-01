"""Private governed snapshot conformance: real child process and authored oracles."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="governed driver has a Linux validation tier"
)

DRIVER = Path(__file__).resolve().parents[1] / "tools/governed_scope.py"


def require(condition, name):
    if not condition:
        raise AssertionError(name)


def declaration():
    return {
        "version": "governed_scope.v1",
        "repo_id": "fixture",
        "source_revision": "fixture-v1",
        "ownership_assertion": {
            "decision_ref": "test-only",
            "remaining_regular_files": "governed",
        },
        "rules": [],
        "generated_inclusions": [],
        "limits": {"max_files": 100, "max_bytes": 100000},
    }


def put(root, path, body=b"def f():\n    return 1\n"):
    p = root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    return p


def run(tmp, root, *, d=None, m=None, trace=False, driver=DRIVER):
    d = d or declaration()
    m = m or {"source_revision": d["source_revision"], "submodule_paths": []}
    request = {
        "declaration": d,
        "source_root": str(root),
        "root_metadata": m,
        "expected_driver_sha256": hashlib.sha256(driver.read_bytes()).hexdigest(),
    }
    tmp.mkdir(parents=True, exist_ok=True)
    rp = tmp / "request.json"
    rp.write_text(json.dumps(request))
    argv = [
        sys.executable,
        "-I",
        "-S",
        str(driver),
        "prepare",
        "--request",
        str(rp),
        "--output",
        str(tmp / "output"),
    ]
    if trace:
        argv = [
            "strace",
            "-f",
            "-yy",
            "-o",
            str(tmp / "trace.log"),
            "-e",
            "trace=open,openat,read,readlink,newfstatat,getdents64",
            *argv,
        ]
    cp = subprocess.run(argv, capture_output=True, timeout=20)
    out = tmp / "output"
    return cp, out


def refusal(cp, reason):
    require(
        cp.returncode == 1, "TYPED_REFUSAL_EXIT:" + cp.stderr.decode(errors="replace")
    )
    require(json.loads(cp.stderr)["reason"] == reason, "TYPED_REFUSAL_REASON")
    require(not cp.stdout, "REFUSAL_NO_SUCCESS")


def test_literal_membership_and_relocation(tmp_path):
    outputs = []
    for name in ("one", "two"):
        root = tmp_path / name
        root.mkdir()
        put(root, "app.py")
        put(root, "vendor_tools/owned.py")
        put(root, "vendor/sentinel.py")
        put(root, "nested/.git/config", b"metadata")
        put(root, "nested/secret.py")
        cp, out = run(tmp_path / (name + "-result"), root, trace=True)
        require(cp.returncode == 0, "READY:" + cp.stderr.decode())
        trace = (out.parent / "trace.log").read_text()
        require(
            "sentinel.py" not in trace and "secret.py" not in trace,
            "GOVERNED_NO_EXTERNAL_READ",
        )
        sel = json.loads((out / "selection.json").read_bytes())
        require(
            [r["path"] for r in sel["included_files"]]
            == ["app.py", "vendor_tools/owned.py"],
            "GOVERNED_LITERAL_MEMBERSHIP",
        )
        require(
            [(r["path"], r["reason"]) for r in sel["opaque_boundaries"]]
            == [("nested", "nested_repository"), ("vendor", "vendored")],
            "GOVERNED_OPAQUE",
        )
        trace = (out.parent / "trace.log").read_text()
        require(
            "sentinel.py" not in trace and "secret.py" not in trace,
            "GOVERNED_NO_EXTERNAL_READ",
        )
        require(not (out / "stage/vendor").exists(), "GOVERNED_STAGE_MEMBERSHIP")
        outputs.append(
            (
                (out / "selection.json").read_bytes(),
                (out / "selection-receipt.json").read_bytes(),
            )
        )
    require(outputs[0] == outputs[1], "GOVERNED_RELOCATION")


def test_symlinks_and_root_gitfile(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    put(root, "app.py")
    put(root, ".git", b"gitdir: /not-read\n")
    target = put(tmp_path, "outside/never-open.py")
    (root / "link.py").symlink_to(target)
    (root / "cycle").symlink_to(".")
    (root / "dangling").symlink_to("missing")
    cp, out = run(tmp_path / "result", root, trace=True)
    require(cp.returncode == 0, "SYMLINK_READY")
    sel = json.loads((out / "selection.json").read_bytes())
    require(
        [r["path"] for r in sel["included_files"]] == ["app.py"], "SYMLINK_SELECTION"
    )
    require(len(sel["opaque_boundaries"]) == 3, "SYMLINK_REFERENCES")
    require(not (out / "stage/.git").exists(), "ROOT_METADATA_EXCLUDED")
    trace = (out.parent / "trace.log").read_text()
    require(
        not any(
            "open" in line and "never-open.py" in line for line in trace.splitlines()
        ),
        "GOVERNED_NO_SYMLINK_TARGET_READ",
    )


@pytest.mark.parametrize(
    ("case", "reason", "blocked"),
    [
        ("unknown", "scope_ownership_unknown", True),
        ("fifo", "scope_special_file", True),
        ("hardlink", "scope_hardlink", True),
        ("budget", "scope_budget", True),
        ("collision", "scope_path", True),
        ("revision", "scope_metadata", False),
        ("badpath", "scope_path", False),
        ("overlap", "scope_schema", False),
    ],
)
def test_refusals(tmp_path, case, reason, blocked):
    root = tmp_path / "root"
    root.mkdir()
    put(root, "app.py")
    d = declaration()
    m = {"source_revision": "fixture-v1", "submodule_paths": []}
    if case == "unknown":
        d["rules"] = [
            {
                "prefix": "app.py",
                "disposition": "unknown",
                "reason": "unclassified",
                "decision_ref": "test",
            }
        ]
    if case == "fifo":
        os.mkfifo(root / "pipe")
    if case == "hardlink":
        os.link(root / "app.py", root / "other.py")
    if case == "budget":
        d["limits"]["max_bytes"] = 1
    if case == "collision":
        put(root, "APP.py")
    if case == "revision":
        m["source_revision"] = "wrong"
    if case == "badpath":
        d["rules"] = [
            {
                "prefix": "../escape",
                "disposition": "exclude",
                "reason": "vendored",
                "decision_ref": "test",
            }
        ]
        m["source_revision"] = "wrong"
    if case == "overlap":
        d["rules"] = [
            {
                "prefix": p,
                "disposition": "exclude",
                "reason": "vendored",
                "decision_ref": "test",
            }
            for p in ["a", "a/b"]
        ]
    cp, out = run(tmp_path / "result", root, d=d, m=m)
    refusal(cp, reason)
    require((out / "selection.json").exists() == blocked, "BLOCKED_ARTIFACT_PHASE")
    require(not (out / "stage").exists(), "NO_STAGE_BEFORE_COPY")
    if blocked:
        s = json.loads((out / "selection.json").read_bytes())
        r = json.loads((out / "selection-receipt.json").read_bytes())
        require(
            s["status"] == "blocked"
            and s["blockers"] == r["refusal_reasons"] == [reason]
            and s["included_files"] == [],
            "BLOCKED_RECEIPT",
        )


def test_submodule_and_generated(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    put(root, ".gitmodules", b'[submodule "child"]\n path = child\n')
    put(root, "child/.git", b"gitdir: elsewhere")
    put(root, "child/never.py")
    put(root, "build/owned.py")
    put(root, "dist/skip.py")
    d = declaration()
    d["generated_inclusions"] = [{"prefix": "build", "decision_ref": "test"}]
    m = {"source_revision": "fixture-v1", "submodule_paths": ["child"]}
    cp, out = run(tmp_path / "result", root, d=d, m=m)
    require(cp.returncode == 0, "SUBMODULE_READY")
    s = json.loads((out / "selection.json").read_bytes())
    require(
        [r["path"] for r in s["included_files"]] == ["build/owned.py"],
        "GENERATED_SELECTION",
    )
    require(
        [(r["path"], r["reason"]) for r in s["opaque_boundaries"]]
        == [("child", "submodule")],
        "SUBMODULE_PRECEDENCE",
    )
    require(
        {r["path"] for r in s["extraction_exclusions"]} == {".gitmodules", "dist"},
        "METADATA_EXCLUSION",
    )


def test_empty_ready_and_unicode_preimage(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    cp, out = run(tmp_path / "result", root)
    require(cp.returncode == 0, "EMPTY_READY")
    s = json.loads((out / "selection.json").read_bytes())
    require(s["included_files"] == [] and s["blockers"] == [], "EMPTY_INVENTORY")
    b = b'{"note":"a\\nb","path":"caf\xc3\xa9.ts"}'
    require(
        hashlib.sha256(b).hexdigest()
        == "531756fd242d34cec1488ddfbf295825df1c970568b84c43eb04b55d199d879d",
        "SCOPE_PREIMAGE",
    )


@pytest.mark.parametrize(
    ("disposition", "reason", "expected"),
    [
        ("external", "build_output", "scope_schema"),
        ("external", "unclassified", "scope_schema"),
        ("unknown", "vendored", "scope_ownership_unknown"),
    ],
)
def test_total_rule_mapping(tmp_path, disposition, reason, expected):
    root = tmp_path / "source"
    root.mkdir()
    put(root, "owned.py")
    d = declaration()
    d["rules"] = [
        {
            "prefix": "unknown",
            "disposition": disposition,
            "reason": reason,
            "decision_ref": "test",
        }
    ]
    cp, _ = run(tmp_path / "result", root, d=d)
    refusal(cp, expected)


def test_generated_inclusion_does_not_select_siblings(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    put(root, "build/owned/app.py")
    put(root, "build/unowned/hidden.py")
    put(root, "build/stray.py")
    d = declaration()
    d["generated_inclusions"] = [{"prefix": "build/owned", "decision_ref": "test"}]
    cp, out = run(tmp_path / "result", root, d=d)
    require(cp.returncode == 0, "GENERATED_READY")
    require(
        [
            r["path"]
            for r in json.loads((out / "selection.json").read_bytes())["included_files"]
        ]
        == ["build/owned/app.py"],
        "GENERATED_NO_SIBLINGS",
    )


def test_absent_submodule_actual_git_inventory(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    put(root, "owned.py")
    put(root, ".gitmodules", b'[submodule "child"]\n path = child\n')
    env = dict(
        os.environ,
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_SYSTEM=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
    )
    args = [
        "git",
        "-c",
        "core.hooksPath=" + os.devnull,
        "-c",
        "commit.gpgsign=false",
        "-C",
        str(root),
    ]
    subprocess.run([*args, "init", "-q"], env=env, check=True)
    subprocess.run(
        [
            *args,
            "update-index",
            "--add",
            "--cacheinfo",
            "160000," + "a" * 40 + ",child",
        ],
        env=env,
        check=True,
    )
    index = subprocess.check_output([*args, "ls-files", "--stage", "-z"], env=env)
    require(index == b"160000 " + b"a" * 40 + b" 0\tchild\0", "FIXED_GITLINK_METADATA")
    cp, out = run(
        tmp_path / "result",
        root,
        m={"source_revision": "fixture-v1", "submodule_paths": ["child"]},
    )
    require(cp.returncode == 0, "ABSENT_SUBMODULE_READY")
    require(
        [
            (r["path"], r["reason"])
            for r in json.loads((out / "selection.json").read_bytes())[
                "opaque_boundaries"
            ]
        ]
        == [("child", "submodule")],
        "ABSENT_SUBMODULE_REFERENCE",
    )
    cp, out = run(
        tmp_path / "mismatch",
        root,
        m={"source_revision": "fixture-v1", "submodule_paths": []},
    )
    refusal(cp, "scope_metadata")
    require(not out.exists(), "METADATA_DIAGNOSTIC_ONLY")


def test_duplicate_json_and_existing_output(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    put(root, "app.py")
    cp, out = run(tmp_path / "result", root)
    require(cp.returncode == 0, "READY_BEFORE_ROOT_REFUSAL")
    original = (out / "selection.json").read_bytes()
    request = tmp_path / "result/request.json"
    cp = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(DRIVER),
            "prepare",
            "--request",
            str(request),
            "--output",
            str(out),
        ],
        capture_output=True,
    )
    refusal(cp, "scope_root")
    require(
        (out / "selection.json").read_bytes() == original, "EXISTING_OUTPUT_UNCHANGED"
    )
    request.write_text('{"declaration":{},"declaration":{}}')
    cp = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(DRIVER),
            "prepare",
            "--request",
            str(request),
            "--output",
            str(tmp_path / "absent"),
        ],
        capture_output=True,
    )
    refusal(cp, "scope_schema")


def test_phase2_path_wins_over_metadata(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    put(root, "owned.py")
    d = declaration()
    d["rules"] = [
        {
            "prefix": "../escape",
            "decision_ref": "fixture",
            "disposition": "exclude",
            "reason": "vendored",
        }
    ]
    cp, out = run(
        tmp_path / "result",
        root,
        d=d,
        m={"source_revision": "wrong", "submodule_paths": []},
    )
    refusal(cp, "scope_path")
    require(not out.exists(), "PHASE2_PATH_FIRST_DIAGNOSTIC_ONLY")


@pytest.mark.parametrize("value", [True, 1.0, 0, -1])
def test_nonpositive_noninteger_budget(tmp_path, value):
    root = tmp_path / "source"
    root.mkdir()
    d = declaration()
    d["limits"]["max_files"] = value
    cp, out = run(tmp_path / "result", root, d=d)
    refusal(cp, "scope_schema")
    require(not out.exists(), "INVALID_BUDGET_NO_OUTPUT")


def test_detected_copy_change(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    put(root, "owned.py")
    driver = tmp_path / "controlled-driver.py"
    code = DRIVER.read_text()
    old = "            stage.mkdir()"
    require(code.count(old) == 1, "COPY_CHANGE_HOOK_UNIQUE")
    driver.write_text(
        code.replace(
            old,
            old
            + '\n            (root / "owned.py").write_bytes(b"changed after inventory")',
        )
    )
    cp, out = run(tmp_path / "result", root, driver=driver)
    refusal(cp, "scope_source_changed")
    selection = json.loads((out / "selection.json").read_bytes())
    require(
        selection["status"] == "blocked" and selection["included_files"] == [],
        "SOURCE_CHANGE_BLOCKED_NO_PARSE",
    )


def test_unsupported_platform_refuses(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    driver = tmp_path / "unsupported-driver.py"
    driver.write_text(
        DRIVER.read_text().replace('not hasattr(os, "O_NOFOLLOW")', "True", 1)
    )
    cp, out = run(tmp_path / "result", root, driver=driver)
    refusal(cp, "scope_platform_unsupported")
    require(not out.exists(), "UNSUPPORTED_NO_STAGE")


def test_shared_recipe_metadata_and_membership(tmp_path):
    import runpy

    recipe = Path(__file__).parent / "fixtures/governed_scope/recipe.py"
    root = tmp_path / "source"
    expected = runpy.run_path(str(recipe))["build"](root)
    cp, out = run(tmp_path / "result", root, m=expected["metadata"])
    require(cp.returncode == 0, "SHARED_RECIPE_READY")
    selection = json.loads((out / "selection.json").read_bytes())
    require(
        [r["path"] for r in selection["included_files"]] == expected["included"],
        "SHARED_LITERAL_INCLUDED",
    )
    require(
        [[r["path"], r["reason"]] for r in selection["opaque_boundaries"]]
        == expected["opaque"],
        "SHARED_LITERAL_OPAQUE",
    )


def test_rule_reason_shape_refuses(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    d = declaration()
    d["rules"] = [
        {
            "prefix": "foreign",
            "decision_ref": "fixture",
            "disposition": "external",
            "reason": [],
        }
    ]
    cp, out = run(tmp_path / "result", root, d=d)
    refusal(cp, "scope_schema")
    require(not out.exists(), "RULE_SHAPE_DIAGNOSTIC_ONLY")


def test_root_disjointness_and_driver_identity(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    put(root, "owned.py")
    cp, _ = run(tmp_path / "initial", root)
    require(cp.returncode == 0, "ROOT_CONTROL")
    request = tmp_path / "initial/request.json"
    argv = [
        sys.executable,
        "-I",
        "-S",
        str(DRIVER),
        "prepare",
        "--request",
        str(request),
        "--output",
    ]
    for output in (root, root / "inside", tmp_path):
        refusal(subprocess.run([*argv, str(output)], capture_output=True), "scope_root")
    content = json.loads(request.read_text())
    content["expected_driver_sha256"] = "0" * 64
    request.write_text(json.dumps(content))
    refusal(
        subprocess.run([*argv, str(tmp_path / "new")], capture_output=True),
        "scope_driver_identity",
    )
    missing = subprocess.run(
        [sys.executable, "-I", "-S", str(tmp_path / "missing-driver.py")],
        capture_output=True,
    )
    require(missing.returncode == 2, "MISSING_DRIVER_SETUP_ONLY")


def test_permuted_rules_and_seed_receipts(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    put(root, "owned.py")
    expected = None
    for index, seed in enumerate(("1", "17")):
        d = declaration()
        d["rules"] = [
            {
                "prefix": p,
                "decision_ref": "fixture",
                "disposition": "external",
                "reason": "dependency",
            }
            for p in ("other-a", "other-b")
        ]
        if index:
            d["rules"].reverse()
        case = tmp_path / seed
        cp, out = run(case, root, d=d)
        require(cp.returncode == 0, "PERMUTATION_READY")
        request = case / "request.json"
        seeded = case / "seeded"
        env = dict(os.environ, PYTHONHASHSEED=seed)
        cp = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                str(DRIVER),
                "prepare",
                "--request",
                str(request),
                "--output",
                str(seeded),
            ],
            env=env,
            capture_output=True,
        )
        require(cp.returncode == 0, "FRESH_PROCESS_READY")
        actual = [
            (seeded / f).read_bytes()
            for f in ("selection.json", "selection-receipt.json")
        ]
        if expected is not None:
            require(expected == actual, "PERMUTATION_RECEIPT_EQUALITY")
        expected = actual


def test_product_unicode_preimage(tmp_path):
    import runpy

    product = runpy.run_path(str(DRIVER))
    literal = b'{"note":"a\\nb","path":"caf\xc3\xa9.ts"}'
    require(
        product["canonical"]({"path": "café.ts", "note": "a\nb"}) == literal,
        "PRODUCT_SCOPE_PREIMAGE",
    )
    root = tmp_path / "source"
    root.mkdir()
    for name in ("café.ts", "a\nb.py"):
        put(root, name, b"x")
    cp, out = run(tmp_path / "run", root)
    require(cp.returncode == 0, "UNICODE_READY")

    def encoded(value):
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    def sha(value):
        return hashlib.sha256(encoded(value)).hexdigest()

    files = [
        {"path": name, "sha256": hashlib.sha256(b"x").hexdigest(), "size": 1}
        for name in ("a\nb.py", "café.ts")
    ]
    expected = {
        "version": "scope_selection.v1",
        "declaration_digest": sha(declaration()),
        "repo_id": "fixture",
        "source_revision": "fixture-v1",
        "driver_sha256": hashlib.sha256(DRIVER.read_bytes()).hexdigest(),
        "policy_version": "single_repo.v1",
        "included_files": files,
        "opaque_boundaries": [],
        "extraction_exclusions": [],
        "status": "ready",
        "blockers": [],
    }
    receipt = {
        "version": "scope_receipt.v1",
        "selection_digest": sha(expected),
        "declaration_digest": sha(declaration()),
        "metadata_digest": sha(
            {"source_revision": "fixture-v1", "submodule_paths": []}
        ),
        "included_inventory_digest": sha(files),
        "status": "ready",
        "refusal_reasons": [],
    }
    require(
        (out / "selection.json").read_bytes() == encoded(expected),
        "PRODUCT_SELECTION_BYTES",
    )
    require(
        (out / "selection-receipt.json").read_bytes() == encoded(receipt),
        "PRODUCT_RECEIPT_BYTES",
    )


def test_unexpected_recursion_exit(tmp_path):
    request = tmp_path / "deep.json"
    # CPython 3.14 bounds C recursion by stack size, so its json decoder accepts
    # 10,000 levels; 100,000 raises RecursionError on 3.12 and 3.14 alike
    # (treesitter-chunker#502).
    request.write_text("[" * 100000 + "0" + "]" * 100000)
    cp = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(DRIVER),
            "prepare",
            "--request",
            str(request),
            "--output",
            str(tmp_path / "out"),
        ],
        capture_output=True,
    )
    require(
        cp.returncode == 2
        and cp.stderr == b"scope_setup:RecursionError\n"
        and not cp.stdout,
        "UNEXPECTED_SETUP_EXIT",
    )
    root = tmp_path / "source"
    root.mkdir()
    current = root
    created = []
    try:
        for _ in range(1100):
            current /= "d"
            current.mkdir()
            created.append(current)
        cp, _ = run(tmp_path / "tree-result", root)
        require(
            cp.returncode == 2
            and cp.stderr == b"scope_setup:RecursionError\n"
            and not cp.stdout,
            "DEEP_TREE_SETUP_EXIT",
        )
    finally:
        # Only empty directories created by this test; avoid recursive teardown.
        for path in reversed(created):
            path.rmdir()
