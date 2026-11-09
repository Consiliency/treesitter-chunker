"""Fail-closed PR routing. Paths are case-sensitive repository-relative POSIX names.

Only root Markdown and the documented recursive prose/assets allowlists are light.
Git's NUL-delimited --no-renames status stream preserves deletions and odd names.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

SCHEMA = "1"
BUILD_INPUT_ROOT_FILES = {
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "pyproject.toml",
    "setup.py",
    "requirements-build.txt",
    "requirements.txt",
}
DOC_SUFFIXES = {
    ".md",
    ".rst",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".gif",
    ".webp",
    ".css",
}


def classify(changes: list[tuple[str, str]]) -> dict[str, str]:
    code = docs = False
    for status, path in changes:
        if status not in {"A", "M", "D", "T"}:
            raise ValueError("unsupported diff status")
        if (
            not path
            or path.startswith("/")
            or any(p in {"", ".", ".."} for p in path.split("/"))
        ):
            raise ValueError("invalid repository path")
        forced = (
            path == "CHANGELOG.md"
            or (status == "D" and path in BUILD_INPUT_ROOT_FILES)
            or path.startswith("docs/sphinx/")
            or path.startswith("docs/language-coverage.")
            or path
            in {"docs/development/mypy-baseline.txt", "docs/interface-boundary-spec.md"}
        )
        light_docs = (
            ("/" not in path and path.endswith(".md"))
            or path == "mkdocs.yml"
            or (path.startswith("docs/") and Path(path).suffix in DOC_SUFFIXES)
        )
        light_plan = path.startswith(("plans/", "specs/")) and path.endswith(".md")
        if forced or not (light_docs or light_plan):
            code = True
        elif light_docs:
            docs = True
    return {
        "schema": SCHEMA,
        "code": str(code).lower(),
        "docs": str(code or docs).lower(),
        "policy": "true",
        "full": "false",
    }


def git(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout


def oid(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("invalid object ID")
    return value


def fetch_object(url: str, sha: str) -> None:
    git("fetch", "--no-tags", "--", url, sha)
    git("cat-file", "-e", f"{sha}^{{commit}}")


def repo_url(repo: dict) -> str:
    name = repo["full_name"]
    if not isinstance(name, str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name
    ):
        raise ValueError("invalid repository")
    return f"https://github.com/{name}.git"


def parse_diff(raw: bytes) -> list[tuple[str, str]]:
    if raw and not raw.endswith(b"\0"):
        raise ValueError("unterminated diff")
    fields = raw.decode("utf-8", errors="strict").split("\0")[:-1]
    if len(fields) % 2:
        raise ValueError("malformed diff")
    changes = list(zip(fields[::2], fields[1::2]))
    # Validate even when callers only request the parsed stream.
    classify(changes)
    return changes


def pr_changes(event: dict) -> list[tuple[str, str]]:
    pr = event["pull_request"]
    base, head = pr["base"], pr["head"]
    base_sha, head_sha = oid(base["sha"]), oid(head["sha"])
    base_url = repo_url(base["repo"])
    fetch_object(base_url, base_sha)
    fetch_object(repo_url(head["repo"]), head_sha)
    default = event["repository"]["default_branch"]
    if not isinstance(default, str) or not default:
        raise ValueError("missing default branch")
    git("check-ref-format", f"refs/heads/{default}")
    git("fetch", "--no-tags", "--", base_url, f"refs/heads/{default}")
    default_sha = oid(git("rev-parse", "FETCH_HEAD").decode().strip())
    git("cat-file", "-e", f"{default_sha}^{{commit}}")
    tips = [default_sha]
    if base["ref"] != default:
        tips.append(base_sha)
    changes = []
    for tip in tips:
        ancestor = oid(git("merge-base", tip, head_sha).decode().strip())
        changes.extend(
            parse_diff(
                git(
                    "diff",
                    "--no-renames",
                    "--name-status",
                    "-z",
                    ancestor,
                    head_sha,
                    "--",
                )
            )
        )
    return changes


def detect(event_name: str, event: dict) -> dict[str, str]:
    if event_name == "pull_request":
        return classify(pr_changes(event))
    if event_name not in {"schedule", "workflow_dispatch", "merge_group", "push"}:
        raise ValueError("unsupported event")
    return {
        "schema": SCHEMA,
        "code": "true",
        "docs": "true",
        "policy": "true",
        "full": str(event_name in {"schedule", "workflow_dispatch"}).lower(),
    }


def main() -> None:
    event = json.loads(
        Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8")
    )
    outputs = detect(os.environ["GITHUB_EVENT_NAME"], event)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        for key, value in outputs.items():
            stream.write(f"{key}={value}\n")
    summary = "CI routing (schema 1): " + json.dumps(outputs, sort_keys=True)
    summary += "\nReason: " + (
        "full event"
        if os.environ["GITHUB_EVENT_NAME"] != "pull_request"
        else "union of default/base merge-base diffs; unknown/build inputs force code and docs"
    )
    print(summary)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
        stream.write(summary + "\n")


if __name__ == "__main__":
    main()
