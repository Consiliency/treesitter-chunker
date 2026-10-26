"""Authored test inputs shared by consumers; imports no selector or parser."""

from pathlib import Path
import os
import subprocess


def build(root):
    root = Path(root)
    root.mkdir()
    bodies = {
        "app.py": b"def answer():\n    return 42\n",
        "vendor_tools/owned.py": b"def owned():\n    return 1\n",
        "vendor/sentinel.py": b"EXCLUDED_VENDOR = 1\n",
        "nested/sentinel.py": b"EXCLUDED_NESTED = 1\n",
        "linked/sentinel.py": b"EXCLUDED_LINKED = 1\n",
        "child/sentinel.py": b"EXCLUDED_SUBMODULE = 1\n",
        ".gitmodules": b'[submodule "child"]\n path = child\n[submodule "missing"]\n path = missing\n',
        "linked/.git": b"gitdir: /never-follow-this-test-pointer\n",
        "child/.git": b"gitdir: /never-follow-this-child-pointer\n",
    }
    for path, body in bodies.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    (root / "nested/.git").mkdir()
    env = dict(
        os.environ,
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_SYSTEM=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
    )
    for key in list(env):
        if key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")) or key in (
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_INDEX_FILE",
            "GIT_CONFIG_COUNT",
        ):
            env.pop(key)
    git = [
        "git",
        "-c",
        "core.hooksPath=" + os.devnull,
        "-c",
        "commit.gpgsign=false",
        "-C",
        str(root),
    ]
    subprocess.run([*git, "init", "-q"], env=env, check=True)
    for path in ("child", "missing"):
        subprocess.run(
            [
                *git,
                "update-index",
                "--add",
                "--cacheinfo",
                "160000," + "a" * 40 + "," + path,
            ],
            env=env,
            check=True,
        )
    return {
        "metadata": {
            "source_revision": "fixture-v1",
            "submodule_paths": ["child", "missing"],
        },
        "included": ["app.py", "vendor_tools/owned.py"],
        "opaque": [
            ["child", "submodule"],
            ["linked", "nested_repository"],
            ["missing", "submodule"],
            ["nested", "nested_repository"],
            ["vendor", "vendored"],
        ],
    }


if __name__ == "__main__":
    import json
    import sys

    print(json.dumps(build(sys.argv[1]), sort_keys=True))
