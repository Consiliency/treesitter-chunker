"""Literal graphs and independent GROUP identity/profile fixture construction."""

import copy
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import sys
import unicodedata


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def hashed(label, value):
    return hashlib.sha256(
        ("chunker.group." + label + ".v1\n").encode() + canonical(value)
    ).hexdigest()


def wire_path(path, root):
    """Request paths are POSIX-relative on every host."""
    return path.relative_to(root).as_posix()


def normalized(request):
    result = copy.deepcopy(request)
    for key in ("relationships", "call_facts", "errors"):
        if key in result["graph"]:
            result["graph"][key] = sorted(result["graph"][key], key=canonical)
    source = result["source_binding"]
    source["coverage_records"] = sorted(
        source["coverage_records"], key=lambda row: row["path"]
    )
    for record in source["coverage_records"]:
        if "diagnostic_refs" in record:
            record["diagnostic_refs"] = sorted(record["diagnostic_refs"], key=canonical)
    policy = result["policy"]
    policy["membership"] = sorted(
        policy["membership"], key=lambda row: row["boundary_id"]
    )
    for group in policy["membership"]:
        group["members"] = sorted(group["members"])
    policy["unassigned_ids"] = sorted(policy["unassigned_ids"])
    policy["override_refs"] = sorted(policy["override_refs"], key=canonical)
    for key, field in [("source_files", "path"), ("dependencies", "name")]:
        result["producer"][key] = sorted(
            result["producer"][key], key=lambda row: row[field]
        )
    return result


def pins(request):
    value = normalized(request)
    return {
        "request": hashed("request", value),
        "source-binding": hashed("source-binding", value["source_binding"]),
        "profile": hashed(
            "profile", {key: value[key] for key in ("producer", "settings", "policy")}
        ),
    }


def producer(root, commit):
    root = Path(root)
    sources = [
        root / "tools/governed_group.py",
        *sorted((root / "chunker").rglob("*.py")),
    ]
    dependencies = {
        re.sub(r"[-_.]+", "-", d.metadata["Name"]).lower(): d.version
        for d in metadata.distributions()
    }
    return {
        "source_commit": commit,
        "distribution_label": "unpublished-source-overlay; not a new 6.0.0 release",
        "source_files": [
            {
                "path": wire_path(path, root),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in sources
        ],
        "lock_sha256": hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest(),
        "dependencies": [
            {"name": name, "version": version, "artifact_sha256": None}
            for name, version in sorted(dependencies.items())
        ],
        "python_version": platform.python_version(),
        "unicode_version": unicodedata.unidata_version,
        "platform_profile": sys.platform + ":" + platform.machine(),
    }


def literal_graph():
    symbols = {
        key: {
            "name": key,
            "kind": "function",
            "file": file,
            "line": line,
            "end_line": line,
            "module": file,
        }
        for key, file, line in [
            ("a1", "a.py", 1),
            ("a2", "a.py", 2),
            ("a3", "a.py", 3),
            ("a4", "a.py", 4),
            ("b1", "b.py", 1),
            ("b2", "b.py", 2),
            ("u", "empty.py", 1),
        ]
    }
    relationships = [
        {"from": left, "to": right, "type": "calls", "call_site_id": site}
        for left, right, site in [
            ("a1", "a2", "one"),
            ("a1", "a2", "two"),
            ("a3", "a4", "three"),
            ("b1", "b2", "four"),
        ]
    ]
    relationships += [
        {"from": "a2", "to": "b1", "type": "calls", "call_site_id": "cross-" + str(i)}
        for i in range(12)
    ]
    relationships += [
        {"from": "a1", "to": "lost", "type": "calls", "resolution": "unresolved"},
        {
            "from": "a1",
            "to": "maybe",
            "type": "calls",
            "resolution": "ambiguous",
            "candidates": ["a2", "a3"],
        },
        {"from": "b1", "to": "external", "type": "calls", "is_internal": False},
        {"from": "a1", "to": "a1", "type": "calls"},
        {"from": "a1", "to": "a2", "type": "new_unknown_kind", "future": [2, 1]},
        {"from": "a1", "type": "calls"},
    ]
    return {
        "symbol_lookup": symbols,
        "relationships": relationships,
        "call_facts": [{"id": "one", "opaque": [2, 1]}, {"id": "two"}],
        "errors": [],
        "metadata": {"unknown_ordered": [3, 1, 2]},
        "unknown_native": {"ordered": [2, 1]},
    }


def request(
    root, commit, mode="declared_boundaries", graph=None, coverage=None, scope=None
):
    graph = literal_graph() if graph is None else graph
    coverage = (
        [
            {"path": path, "status": "processed", "diagnostic_refs": []}
            for path in sorted({s["file"] for s in graph["symbol_lookup"].values()})
        ]
        if coverage is None
        else coverage
    )
    source = {
        "repo_id": "authored-control",
        "source_revision": "fixture-v1",
        **{
            name: hashlib.sha256(("literal-" + name).encode()).hexdigest()
            for name in [
                "declaration_digest",
                "selection_digest",
                "metadata_digest",
                "included_inventory_digest",
                "driver_sha256",
            ]
        },
        "graph_digest": hashed("graph", normalized_graph(graph)),
        "coverage_records": coverage,
        "coverage_digest": hashed(
            "coverage", sorted(coverage, key=lambda row: row["path"])
        ),
        "native_identity_profile": {
            "producer": "authored-graph-control",
            "version": "1",
            "symbol_id_algorithm": "opaque-literal",
            "graph_encoding": "group-json-v1",
            "relocation_comparability": True,
        },
    }
    if scope:
        source.update(scope)
    members = set(graph["symbol_lookup"])
    a = sorted(members & {"a1", "a2", "a3", "a4"})
    b = sorted(members & {"b1", "b2"})
    return {
        "schema": "chunker.group.request.v1",
        "source_binding": source,
        "graph": graph,
        "producer": producer(root, commit),
        "settings": {
            "seed": 42,
            "weights": {
                "import_weight": 1.0,
                "call_weight": 0.7,
                "inherit_weight": 0.8,
                "type_ref_weight": 0.5,
                "same_file_bonus": 0.3,
            },
            "coarse_resolution": 0.5,
            "fine_resolution": 1.5,
            "detect_infrastructure": True,
            "infrastructure_threshold": 0.95,
            "limits": {
                "max_symbols": 2000,
                "max_relationships": 20000,
                "max_input_bytes": 16777216,
                "max_output_bytes": 16777216,
            },
        },
        "policy": {
            "mode": mode,
            "revision": "literal-policy-v1",
            "intended_boundary_revision": "literal-intent-v1",
            "correspondence_digest": hashlib.sha256(
                b"literal-membership-not-a-Spec-crosswalk"
            ).hexdigest(),
            "membership": [
                {"boundary_id": name, "members": ids}
                for name, ids in [("A", a), ("B", b)]
                if ids
            ],
            "unassigned_ids": sorted(members - set(a) - set(b)),
            "override_refs": [],
        },
    }


def normalized_graph(graph):
    result = copy.deepcopy(graph)
    for key in ("relationships", "call_facts", "errors"):
        if key in result:
            result[key] = sorted(result[key], key=canonical)
    return result


def reverse_arrays(request):
    result = copy.deepcopy(request)
    for key in ("relationships", "call_facts", "errors"):
        if key in result["graph"]:
            result["graph"][key].reverse()
    result["graph"]["symbol_lookup"] = dict(
        reversed(list(result["graph"]["symbol_lookup"].items()))
    )
    result["source_binding"]["coverage_records"].reverse()
    for record in result["source_binding"]["coverage_records"]:
        if "diagnostic_refs" in record:
            record["diagnostic_refs"].reverse()
    result["policy"]["membership"].reverse()
    for record in result["policy"]["membership"]:
        record["members"].reverse()
    for key in ("unassigned_ids", "override_refs"):
        result["policy"][key].reverse()
    for key in ("source_files", "dependencies"):
        result["producer"][key].reverse()
    return result
