#!/usr/bin/env python3
"""Experimental stdlib-only governed snapshot driver; not a public parser API.

Run with -I -S. This enforces declared scope on quiescent snapshots, not a hostile
concurrent filesystem or an authenticated ownership assertion. Opt-in
governed_scope.v2 requests bind boundary classification to supplied committed
metadata (committed_boundary.v1); file content remains unbound.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import unicodedata

OPAQUE = {
    "node_modules": "dependency",
    "vendor": "vendored",
    "third_party": "vendored",
    "third-party": "vendored",
    **dict.fromkeys(
        (
            ".venv",
            "venv",
            ".tox",
            ".toxenv",
            ".eggs",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".dart_tool",
            ".next",
            ".turbo",
            ".cache",
        ),
        "tool_state",
    ),
}
BUILD = {"build", "dist", "out", "coverage"}
VCS = {".git", ".gitmodules", ".hg", ".svn"}
REASONS = {"vendored", "dependency", "build_output", "tool_state", "unclassified"}
V2 = "governed_scope.v2"
POLICY_V2 = "committed_boundary.v1"
HEX_LEN = {"sha1": 40, "sha256": 64}


class ScopeRefused(ValueError):  # noqa: N818 -- private contract names this exception
    def __init__(self, reason, path=None):
        super().__init__(reason)
        self.reason, self.path = reason, path


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def fields(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ScopeRefused("scope_schema")


def text(value):
    if not isinstance(value, str) or not value:
        raise ScopeRefused("scope_schema")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ScopeRefused("scope_schema") from exc


def valid_path(value):
    return (
        isinstance(value, str)
        and bool(value)
        and not value.startswith("/")
        and "\\" not in value
        and "\0" not in value
        and all(part not in ("", ".", "..") for part in value.split("/"))
    )


def below(path, prefix):
    return path == prefix or path.startswith(prefix + "/")


def pairs(rows):
    out = {}
    for key, value in rows:
        if key in out:
            raise ScopeRefused("scope_schema")
        out[key] = value
    return out


def load(path):
    try:
        return json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ScopeRefused("scope_schema")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ScopeRefused("scope_schema") from exc


def hex_id(value, length):
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ScopeRefused("scope_schema")


def schema(request):
    fields(request, "declaration source_root root_metadata expected_driver_sha256")
    d = request["declaration"]
    # Type-only guard before version dispatch: fields() below also closes the v1
    # key set, so it cannot run first for a v2 declaration.
    if not isinstance(d, dict):
        raise ScopeRefused("scope_schema")
    if d.get("version") == V2:
        return schema_v2(request)
    fields(
        d,
        "version repo_id source_revision ownership_assertion rules generated_inclusions limits",
    )
    if d["version"] != "governed_scope.v1":
        raise ScopeRefused("scope_schema")
    for x in (
        d["repo_id"],
        d["source_revision"],
        request["source_root"],
        request["expected_driver_sha256"],
    ):
        text(x)
    fields(d["ownership_assertion"], "decision_ref remaining_regular_files")
    text(d["ownership_assertion"]["decision_ref"])
    if d["ownership_assertion"]["remaining_regular_files"] != "governed":
        raise ScopeRefused("scope_schema")
    fields(d["limits"], "max_files max_bytes")
    if any(type(v) is not int or v <= 0 for v in d["limits"].values()):
        raise ScopeRefused("scope_schema")
    for key in ("rules", "generated_inclusions"):
        if not isinstance(d[key], list):
            raise ScopeRefused("scope_schema")
        seen = []
        for row in d[key]:
            fields(
                row,
                (
                    "prefix decision_ref disposition reason"
                    if key == "rules"
                    else "prefix decision_ref"
                ),
            )
            text(row["prefix"])
            text(row["decision_ref"])
            if any(
                below(row["prefix"], other) or below(other, row["prefix"])
                for other in seen
            ):
                raise ScopeRefused("scope_schema")
            seen.append(row["prefix"])
            if key == "rules":
                text(row["disposition"])
                text(row["reason"])
                if (
                    row["disposition"] not in ("external", "exclude", "unknown")
                    or row["reason"] not in REASONS
                    or (
                        row["disposition"] == "external"
                        and row["reason"]
                        not in ("vendored", "dependency", "tool_state")
                    )
                ):
                    raise ScopeRefused("scope_schema")
    m = request["root_metadata"]
    fields(m, "submodule_paths source_revision")
    text(m["source_revision"])
    if not isinstance(m["submodule_paths"], list):
        raise ScopeRefused("scope_schema")
    for path in m["submodule_paths"]:
        text(path)
    return d, m


def schema_v2(request):
    d = request["declaration"]
    fields(
        d,
        "version policy_version repo_id source_revision ownership_assertion rules"
        " generated_inclusions boundary_transitions limits",
    )
    if d["policy_version"] != POLICY_V2:
        raise ScopeRefused("scope_schema")
    # Shared fields reuse the unchanged v1 validation through a v1-shaped view
    # that aliases the same rule rows; v1 metadata in the view is synthetic.
    view = dict(d, version="governed_scope.v1")
    del view["policy_version"], view["boundary_transitions"]
    schema(
        {
            "declaration": view,
            "source_root": request["source_root"],
            "root_metadata": {
                "submodule_paths": [],
                "source_revision": d["source_revision"],
            },
            "expected_driver_sha256": request["expected_driver_sha256"],
        }
    )
    m = request["root_metadata"]
    fields(m, "version object_format commit tree gitlinks gitmodules_blob")
    if m["version"] != "scope_root_metadata.v2" or not (
        isinstance(m["object_format"], str) and m["object_format"] in HEX_LEN
    ):
        raise ScopeRefused("scope_schema")
    length = HEX_LEN[m["object_format"]]
    for value in (d["source_revision"], m["commit"], m["tree"]):
        hex_id(value, length)
    if m["gitmodules_blob"] is not None:
        hex_id(m["gitmodules_blob"], length)
    if not isinstance(m["gitlinks"], list) or not isinstance(
        d["boundary_transitions"], list
    ):
        raise ScopeRefused("scope_schema")
    for row in m["gitlinks"]:
        fields(row, "path object_id")
        text(row["path"])
        hex_id(row["object_id"], length)
    claimed = [r["prefix"] for r in d["rules"] + d["generated_inclusions"]]
    seen: list[str] = []
    for row in d["boundary_transitions"]:
        fields(row, "prefix decision_ref kind")
        text(row["prefix"])
        text(row["decision_ref"])
        if row["kind"] != "nested_repository" or any(
            below(row["prefix"], other) or below(other, row["prefix"])
            for other in seen + claimed
        ):
            raise ScopeRefused("scope_schema")
        seen.append(row["prefix"])
    return d, m


def check_paths(d, m):
    groups = [
        [r["prefix"] for r in d["rules"]],
        [r["prefix"] for r in d["generated_inclusions"]],
        m["submodule_paths"],
    ]
    for paths in groups:
        if any(not valid_path(p) for p in paths) or len(
            {p.casefold() for p in paths}
        ) != len(paths):
            raise ScopeRefused("scope_path")
    # Canonicalize caller array order before hashing. The accepted schema treats order
    # permutations identically; duplicate/overlapping rules were refused above.
    d["rules"].sort(key=lambda r: r["prefix"])
    d["generated_inclusions"].sort(key=lambda r: r["prefix"])
    m["submodule_paths"].sort()


def check_paths_v2(d, m):
    check_paths(d, {"submodule_paths": [g["path"] for g in m["gitlinks"]]})
    prefixes = [t["prefix"] for t in d["boundary_transitions"]]
    if any(not valid_path(p) for p in prefixes) or len(
        {p.casefold() for p in prefixes}
    ) != len(prefixes):
        raise ScopeRefused("scope_path")
    m["gitlinks"].sort(key=lambda g: g["path"])
    d["boundary_transitions"].sort(key=lambda t: t["prefix"])


def signature(s):
    return (
        s.st_dev,
        s.st_ino,
        s.st_size,
        s.st_mtime_ns,
        s.st_ctime_ns,
        s.st_mode,
        s.st_nlink,
    )


def gitmodules(root_fd):
    """Return root .gitmodules bytes (None when absent) and its submodule paths."""
    paths = []
    body = None
    try:
        st = os.stat(".gitmodules", dir_fd=root_fd, follow_symlinks=False)
    except FileNotFoundError:
        st = None
    if st is not None:
        if not stat.S_ISREG(st.st_mode) or st.st_size > 1048576 or st.st_nlink != 1:
            raise ScopeRefused("scope_metadata", ".gitmodules")
        fd = os.open(
            ".gitmodules", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd
        )
        try:
            if signature(os.fstat(fd)) != signature(st):
                raise ScopeRefused("scope_metadata", ".gitmodules")
            body = os.read(fd, 1048577)
            if len(body) != st.st_size or signature(os.fstat(fd)) != signature(st):
                raise ScopeRefused("scope_metadata", ".gitmodules")
        finally:
            os.close(fd)
        cp = configparser.ConfigParser(interpolation=None, strict=True)
        try:
            cp.read_string(body.decode("utf-8"))
            for section in cp.sections():
                if not section.startswith('submodule "') or not section.endswith('"'):
                    raise ValueError("section")
                path = cp[section]["path"]
                if not valid_path(path):
                    raise ValueError("path")
                paths.append(path)
        except (ValueError, KeyError, configparser.Error, UnicodeError) as exc:
            raise ScopeRefused("scope_metadata", ".gitmodules") from exc
    return body, paths


def metadata(root_fd, d, m):
    if d["source_revision"] != m["source_revision"]:
        raise ScopeRefused("scope_metadata")
    _, paths = gitmodules(root_fd)
    if len(set(paths)) != len(paths) or sorted(paths) != m["submodule_paths"]:
        raise ScopeRefused("scope_metadata", ".gitmodules")


def metadata_v2(root_fd, d, m):
    if d["source_revision"] != m["commit"]:
        raise ScopeRefused("scope_metadata")
    body, paths = gitmodules(root_fd)
    blob = None
    if body is not None:
        blob = hashlib.new(
            m["object_format"], b"blob %d\0" % len(body) + body
        ).hexdigest()
    if blob != m["gitmodules_blob"]:
        raise ScopeRefused("scope_metadata", ".gitmodules")
    gitlinks = [g["path"] for g in m["gitlinks"]]
    if len(set(paths)) != len(paths) or sorted(paths) != gitlinks:
        raise ScopeRefused("scope_metadata", ".gitmodules")
    for row in d["boundary_transitions"]:
        if any(below(row["prefix"], g) or below(g, row["prefix"]) for g in gitlinks):
            raise ScopeRefused("scope_metadata", row["prefix"])


def classify_rule(path, d, is_dir):
    for row in d["rules"]:
        if below(path, row["prefix"]):
            if row["disposition"] == "unknown":
                return "error", "scope_ownership_unknown"
            if row["disposition"] == "exclude":
                return "exclude", "explicit_exclude"
            return "opaque", row["reason"]
    if is_dir:
        name = path.rsplit("/", 1)[-1]
        if name in OPAQUE:
            return "opaque", OPAQUE[name]
    # An inclusion permits its subtree, not siblings encountered while traversing
    # an otherwise excluded build ancestor.
    parent_parts = path.split("/") if is_dir else path.split("/")[:-1]
    if any(part in BUILD for part in parent_parts):
        allowed = any(
            below(path, r["prefix"]) or (is_dir and below(r["prefix"], path))
            for r in d["generated_inclusions"]
        )
        if not allowed:
            return "exclude", "build_output"
    return "include", None


def prepare(request, output):
    d, m = schema(request)
    v2 = d["version"] == V2
    driver_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if driver_sha != request["expected_driver_sha256"]:
        raise ScopeRefused("scope_driver_identity")
    source = Path(request["source_root"])
    out = Path(output)
    if not source.is_absolute() or not out.is_absolute():
        raise ScopeRefused("scope_root")
    root = source.resolve()
    resolved_out = out.resolve()
    if (
        not root.is_dir()
        or out.exists()
        or out.is_symlink()
        or root == resolved_out
        or root in resolved_out.parents
        or resolved_out in root.parents
    ):
        raise ScopeRefused("scope_root")
    if (
        not hasattr(os, "O_NOFOLLOW")
        or os.open not in os.supports_dir_fd
        or os.stat not in os.supports_follow_symlinks
        or os.listdir not in os.supports_fd
    ):
        raise ScopeRefused("scope_platform_unsupported")
    (check_paths_v2 if v2 else check_paths)(d, m)
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        (metadata_v2 if v2 else metadata)(root_fd, d, m)
        selected, opaque, excluded, errors, folded = [], [], [], [], {}

        def boundary(path, reason, link=None):
            opaque.append(
                {
                    "path": path,
                    "reason": reason,
                    "reference_digest": digest(
                        {
                            "path": path,
                            "reason": reason,
                            "link_text_sha256": (
                                hashlib.sha256(link.encode("utf-8")).hexdigest()
                                if link is not None
                                else None
                            ),
                        }
                    ),
                }
            )

        submodules = (
            {g["path"] for g in m["gitlinks"]} if v2 else set(m["submodule_paths"])
        )
        transitions = {t["prefix"] for t in d["boundary_transitions"]} if v2 else set()
        used = set()

        def walk(fd, prefix=""):
            for name in sorted(
                os.listdir(fd)  # noqa: PTH208 -- directory-fd no-follow traversal
            ):
                path = prefix + name
                try:
                    path.encode("utf-8")
                except UnicodeError:
                    errors.append(("scope_path", ""))
                    continue
                if not valid_path(path):
                    errors.append(("scope_path", path))
                    continue
                old = folded.setdefault(path.casefold(), path)
                if old != path:
                    errors.append(("scope_path", min(old, path)))
                    continue
                st = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if name in VCS:
                    excluded.append({"path": path, "reason": "vcs_metadata"})
                    continue
                if path in submodules:
                    boundary(path, "submodule")
                    continue
                if stat.S_ISLNK(st.st_mode):
                    boundary(path, "symlink", os.readlink(name, dir_fd=fd))
                    continue
                is_dir = stat.S_ISDIR(st.st_mode)
                child_fd = None
                if is_dir:
                    child_fd = os.open(
                        name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                    )
                    try:
                        try:
                            os.stat(".git", dir_fd=child_fd, follow_symlinks=False)
                            nested = True
                        except FileNotFoundError:
                            nested = False
                        if nested:
                            boundary(path, "nested_repository")
                            continue
                        kind, reason = classify_rule(path, d, True)
                        if kind == "include":
                            walk(child_fd, path + "/")
                            continue
                    finally:
                        os.close(child_fd)
                elif not stat.S_ISREG(st.st_mode):
                    errors.append(("scope_special_file", path))
                    continue
                else:
                    kind, reason = classify_rule(path, d, False)
                if kind == "opaque":
                    boundary(path, reason)
                elif kind == "exclude":
                    excluded.append({"path": path, "reason": reason})
                elif kind == "error":
                    errors.append((reason, path))
                elif st.st_nlink != 1:
                    errors.append(("scope_hardlink", path))
                else:
                    selected.append((path, st))

        def walk_v2(fd, prefix=""):
            # committed_boundary.v1: rule before marker; a marker is never opened,
            # read or descended into, and only include directories are stat'ed.
            for name in sorted(
                os.listdir(fd)  # noqa: PTH208 -- directory-fd no-follow traversal
            ):
                path = prefix + name
                try:
                    path.encode("utf-8")
                except UnicodeError:
                    errors.append(("scope_path", ""))
                    continue
                if not valid_path(path):
                    errors.append(("scope_path", path))
                    continue
                old = folded.setdefault(path.casefold(), path)
                if old != path:
                    errors.append(("scope_path", min(old, path)))
                    continue
                st = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if name in VCS:
                    excluded.append({"path": path, "reason": "vcs_metadata"})
                    continue
                if path in submodules:
                    boundary(path, "submodule")
                    continue
                if stat.S_ISLNK(st.st_mode):
                    boundary(path, "symlink", os.readlink(name, dir_fd=fd))
                    continue
                if stat.S_ISDIR(st.st_mode):
                    kind, reason = classify_rule(path, d, True)
                    if kind == "include":
                        child_fd = os.open(
                            name,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=fd,
                        )
                        try:
                            try:
                                os.stat(".git", dir_fd=child_fd, follow_symlinks=False)
                                marker = True
                            except FileNotFoundError:
                                marker = False
                            if not marker:
                                walk_v2(child_fd, path + "/")
                            elif path in transitions:
                                used.add(path)
                                boundary(path, "nested_repository")
                            else:
                                errors.append(("scope_boundary_uncommitted", path))
                        finally:
                            os.close(child_fd)
                        continue
                elif not stat.S_ISREG(st.st_mode):
                    errors.append(("scope_special_file", path))
                    continue
                else:
                    kind, reason = classify_rule(path, d, False)
                if kind == "opaque":
                    boundary(path, reason)
                elif kind == "exclude":
                    excluded.append({"path": path, "reason": reason})
                elif kind == "error":
                    errors.append((reason, path))
                elif st.st_nlink != 1:
                    errors.append(("scope_hardlink", path))
                else:
                    selected.append((path, st))

        (walk_v2 if v2 else walk)(root_fd)
        for path in sorted(submodules):
            if not any(
                row["path"] == path or below(path, row["path"])
                for row in opaque + excluded
            ):
                boundary(path, "submodule")
        for row in d["rules"]:
            if row["disposition"] == "unknown":
                errors.append(("scope_ownership_unknown", row["prefix"]))
        for prefix in sorted(transitions - used):
            errors.append(("scope_boundary_transition", prefix))
        selected.sort(key=lambda pair: pair[0])
        opaque.sort(key=lambda row: (row["path"], row["reason"]))
        excluded.sort(key=lambda row: (row["path"], row["reason"]))
        out.mkdir(parents=True, exist_ok=False)
        selection = {
            "version": "scope_selection.v1",
            "declaration_digest": digest(d),
            "repo_id": d["repo_id"],
            "source_revision": d["source_revision"],
            "driver_sha256": driver_sha,
            "policy_version": "single_repo.v1",
            "included_files": [],
            "opaque_boundaries": opaque,
            "extraction_exclusions": excluded,
            "status": "ready",
            "blockers": [],
        }
        if v2:
            selection.update(version="scope_selection.v2", policy_version=POLICY_V2)

        def write_receipts(reason=None):
            if reason:
                selection.update(status="blocked", blockers=[reason], included_files=[])
            (out / "selection.json").write_bytes(canonical(selection))
            receipt = {
                "version": "scope_receipt.v1",
                "selection_digest": digest(selection),
                "declaration_digest": digest(d),
                "metadata_digest": digest(m),
                "included_inventory_digest": digest(selection["included_files"]),
                "status": selection["status"],
                "refusal_reasons": selection["blockers"],
            }
            if v2:
                receipt["version"] = "scope_receipt.v2"
            (out / "selection-receipt.json").write_bytes(canonical(receipt))
            (out / "operational.json").write_bytes(
                canonical(
                    {
                        "source_root": str(root),
                        "output_root": str(out),
                        "python": sys.version,
                        "executable": sys.executable,
                        "unicode_version": unicodedata.unidata_version,
                    }
                )
            )
            return receipt

        try:
            if errors:
                ranks = {
                    v: i
                    for i, v in enumerate(
                        (
                            "scope_path",
                            "scope_boundary_uncommitted",
                            "scope_boundary_transition",
                            "scope_ownership_unknown",
                            "scope_special_file",
                            "scope_hardlink",
                        )
                    )
                }
                reason, path = min(errors, key=lambda row: (ranks[row[0]], row[1]))
                raise ScopeRefused(reason, path or None)
            if (
                len(selected) > d["limits"]["max_files"]
                or sum(s.st_size for _, s in selected) > d["limits"]["max_bytes"]
            ):
                raise ScopeRefused("scope_budget")
            stage = out / "stage"
            stage.mkdir()
            for path, expected in selected:
                fds = []
                try:
                    parent = root_fd
                    for part in path.split("/")[:-1]:
                        parent = os.open(
                            part,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=parent,
                        )
                        fds.append(parent)
                    fd = os.open(
                        path.split("/")[-1],
                        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                        dir_fd=parent,
                    )
                    fds.append(fd)
                    if signature(os.fstat(fd)) != signature(expected):
                        raise ScopeRefused("scope_source_changed", path)
                    target = stage / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    sha = hashlib.sha256()
                    size = 0
                    with target.open("xb") as dest:
                        while True:
                            chunk = os.read(fd, 65536)
                            if not chunk:
                                break
                            size += len(chunk)
                            if size > expected.st_size:
                                raise ScopeRefused("scope_source_changed", path)
                            sha.update(chunk)
                            dest.write(chunk)
                    if size != expected.st_size or signature(os.fstat(fd)) != signature(
                        expected
                    ):
                        raise ScopeRefused("scope_source_changed", path)
                    if signature(
                        os.stat(
                            path.split("/")[-1], dir_fd=parent, follow_symlinks=False
                        )
                    ) != signature(expected):
                        raise ScopeRefused("scope_source_changed", path)
                    target.chmod(0o444)
                    selection["included_files"].append(
                        {"path": path, "sha256": sha.hexdigest(), "size": size}
                    )
                except OSError as exc:
                    raise ScopeRefused("scope_source_changed", path) from exc
                finally:
                    for fd in reversed(fds):
                        os.close(fd)
            return write_receipts()
        except ScopeRefused as exc:
            write_receipts(exc.reason)
            raise
    finally:
        os.close(root_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare"])
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = prepare(load(args.request), args.output)
    except ScopeRefused as exc:
        sys.stderr.buffer.write(
            canonical(
                {
                    "version": "scope_diagnostic.v1",
                    "reason": exc.reason,
                    "path": exc.path,
                }
            )
            + b"\n"
        )
        return 1
    except Exception as exc:
        sys.stderr.write("scope_setup:" + type(exc).__name__ + "\n")
        return 2
    sys.stdout.buffer.write(canonical(result) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
