"""Private, input-only GROUP proposals over the existing clustering engine."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
from importlib import machinery, metadata
import json
import math
import multiprocessing
import os
from pathlib import Path
import platform
import re
import sys
import time
import unicodedata


LIMITS = {
    "max_symbols": 2000,
    "max_relationships": 20000,
    "max_input_bytes": 16777216,
    "max_output_bytes": 16777216,
}
ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SOURCE = {
    "tools/governed_group.py",
    "chunker/__init__.py",
    "chunker/symbol_graph.py",
    "chunker/clustering/__init__.py",
    *{
        f"chunker/clustering/{name}.py"
        for name in ("engine", "weights", "hierarchy", "metrics")
    },
}
WEIGHTS = "import_weight call_weight inherit_weight type_ref_weight same_file_bonus"
STATUS = {"processed", "processed_no_symbols", "skipped_by_producer_filter", "failed"}


class GroupError(ValueError):
    """A private, phase-specific refusal; not a legacy admission result."""

    def __init__(self, reason, exit_code=1):
        super().__init__(reason)
        self.reason = reason
        self.exit_code = exit_code


def require(condition, reason):
    if not condition:
        raise GroupError(reason)


def encoded(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(label, value):
    return hashlib.sha256(
        ("chunker.group." + label + ".v1\n").encode() + encoded(value)
    ).hexdigest()


def shape(value, names):
    require(
        isinstance(value, dict) and set(value) == set(names.split()), "group_schema"
    )


def string(value):
    require(isinstance(value, str) and bool(value), "group_schema")


def hex_digest(value, size=64):
    require(
        isinstance(value, str)
        and re.fullmatch("[0-9a-f]{" + str(size) + "}", value) is not None,
        "group_schema",
    )


def relative(value):
    return (
        isinstance(value, str)
        and bool(value)
        and "\\" not in value
        and "\0" not in value
        and not value.startswith("/")
        and all(p not in ("", ".", "..") for p in value.split("/"))
    )


def json_domain(value, depth=0):
    require(depth <= 64, "group_schema")
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError as error:
            raise GroupError("group_schema") from error
    elif type(value) is int:
        require(abs(value) <= 2**63 - 1, "group_schema")
    elif type(value) is float:
        require(math.isfinite(value) and abs(value) <= 1e100, "group_schema")
    elif isinstance(value, list):
        for item in value:
            json_domain(item, depth + 1)
    elif isinstance(value, dict):
        for key, item in value.items():
            json_domain(key, depth + 1)
            json_domain(item, depth + 1)


def unique_rows(rows, key):
    require(isinstance(rows, list), "group_schema")
    seen = set()
    for row in rows:
        require(isinstance(row, dict) and key in row, "group_schema")
        string(row[key])
        require(row[key] not in seen, "group_schema")
        seen.add(row[key])


def schema(request):
    json_domain(request)
    shape(request, "schema source_binding graph producer settings policy")
    require(request["schema"] == "chunker.group.request.v1", "group_schema")
    source = request["source_binding"]
    shape(
        source,
        "repo_id source_revision declaration_digest selection_digest metadata_digest included_inventory_digest driver_sha256 graph_digest coverage_records coverage_digest native_identity_profile",
    )
    for key in ("repo_id", "source_revision"):
        string(source[key])
    for key in source.keys() - {
        "repo_id",
        "source_revision",
        "coverage_records",
        "native_identity_profile",
    }:
        hex_digest(source[key])
    profile = source["native_identity_profile"]
    shape(
        profile,
        "producer version symbol_id_algorithm graph_encoding relocation_comparability",
    )
    for key in profile.keys() - {"relocation_comparability"}:
        string(profile[key])
    require(type(profile["relocation_comparability"]) is bool, "group_schema")
    unique_rows(source["coverage_records"], "path")
    for row in source["coverage_records"]:
        require(
            set(row) <= {"path", "status", "diagnostic_refs"} and "status" in row,
            "group_schema",
        )
        require(
            relative(row["path"])
            and isinstance(row["status"], str)
            and row["status"] in STATUS,
            "group_schema",
        )
        require(isinstance(row.get("diagnostic_refs", []), list), "group_schema")
    graph = request["graph"]
    require(
        isinstance(graph, dict) and {"symbol_lookup", "relationships"} <= graph.keys(),
        "group_schema",
    )
    require(isinstance(graph["symbol_lookup"], dict), "group_schema")
    for symbol_id, symbol in graph["symbol_lookup"].items():
        string(symbol_id)
        require(
            isinstance(symbol, dict) and relative(symbol.get("file")), "group_schema"
        )
    for key in ("relationships", "call_facts", "errors"):
        require(isinstance(graph.get(key, []), list), "group_schema")
    for relation in graph["relationships"]:
        require(isinstance(relation, dict), "group_schema")
        if "file" in relation:
            require(relative(relation["file"]), "group_schema")
        if "is_internal" in relation:
            require(
                relation["is_internal"] is None
                or type(relation["is_internal"]) is bool,
                "group_schema",
            )
        for key in ("from", "to", "type", "resolution"):
            require(
                relation.get(key) is None or isinstance(relation[key], str),
                "group_schema",
            )
    producer = request["producer"]
    shape(
        producer,
        "source_commit distribution_label source_files lock_sha256 dependencies python_version unicode_version platform_profile",
    )
    hex_digest(producer["source_commit"], 40)
    hex_digest(producer["lock_sha256"])
    for key in (
        "distribution_label",
        "python_version",
        "unicode_version",
        "platform_profile",
    ):
        string(producer[key])
    for field, key in [("source_files", "path"), ("dependencies", "name")]:
        unique_rows(producer[field], key)
    for row in producer["source_files"]:
        shape(row, "path sha256")
        require(relative(row["path"]), "group_schema")
        hex_digest(row["sha256"])
    for row in producer["dependencies"]:
        shape(row, "name version artifact_sha256")
        require(
            re.fullmatch("[a-z0-9]+(?:-[a-z0-9]+)*", row["name"]) is not None,
            "group_schema",
        )
        string(row["version"])
        if row["artifact_sha256"] is not None:
            hex_digest(row["artifact_sha256"])
    settings = request["settings"]
    shape(
        settings,
        "seed weights coarse_resolution fine_resolution detect_infrastructure infrastructure_threshold limits",
    )
    require(
        type(settings["seed"]) is int and 0 <= settings["seed"] <= 2147483647,
        "group_schema",
    )
    shape(settings["weights"], WEIGHTS)
    for key, value in {
        **settings["weights"],
        **{
            k: settings[k]
            for k in (
                "coarse_resolution",
                "fine_resolution",
                "infrastructure_threshold",
            )
        },
    }.items():
        require(
            type(value) in (int, float) and math.isfinite(value) and value >= 0,
            "group_schema",
        )
        if key.endswith("resolution"):
            require(value > 0, "group_schema")
    require(
        settings["infrastructure_threshold"] <= 1
        and type(settings["detect_infrastructure"]) is bool,
        "group_schema",
    )
    shape(settings["limits"], " ".join(LIMITS))
    require(
        all(type(v) is int and v > 0 for v in settings["limits"].values()),
        "group_schema",
    )
    policy = request["policy"]
    shape(
        policy,
        "mode revision intended_boundary_revision correspondence_digest membership unassigned_ids override_refs",
    )
    require(
        policy["mode"] in ("declared_boundaries", "dependency_assisted"), "group_schema"
    )
    string(policy["revision"])
    string(policy["intended_boundary_revision"])
    hex_digest(policy["correspondence_digest"])
    unique_rows(policy["membership"], "boundary_id")
    for row in policy["membership"]:
        shape(row, "boundary_id members")
        require(isinstance(row["members"], list), "group_schema")
        for member in row["members"]:
            string(member)
    require(
        isinstance(policy["unassigned_ids"], list)
        and isinstance(policy["override_refs"], list),
        "group_schema",
    )
    for member in policy["unassigned_ids"]:
        string(member)


def normalize(request):
    value = copy.deepcopy(request)
    for key in ("relationships", "call_facts", "errors"):
        if key in value["graph"]:
            value["graph"][key].sort(key=encoded)
    records = value["source_binding"]["coverage_records"]
    records.sort(key=lambda r: r["path"])
    for record in records:
        if "diagnostic_refs" in record:
            record["diagnostic_refs"].sort(key=encoded)
    value["policy"]["membership"].sort(key=lambda r: r["boundary_id"])
    for record in value["policy"]["membership"]:
        record["members"].sort()
    value["policy"]["unassigned_ids"].sort()
    value["policy"]["override_refs"].sort(key=encoded)
    value["producer"]["source_files"].sort(key=lambda r: r["path"])
    value["producer"]["dependencies"].sort(key=lambda r: r["name"])
    value["graph"]["symbol_lookup"] = dict(
        sorted(value["graph"]["symbol_lookup"].items())
    )
    return value


def identities(value):
    return {
        "request": digest("request", value),
        "source-binding": digest("source-binding", value["source_binding"]),
        "profile": digest(
            "profile", {k: value[k] for k in ("producer", "settings", "policy")}
        ),
    }


def validate_identity(value, expected):
    actual = identities(value)
    require(actual == expected, "group_identity")
    source = value["source_binding"]
    require(source["graph_digest"] == digest("graph", value["graph"]), "group_identity")
    require(
        source["coverage_digest"] == digest("coverage", source["coverage_records"]),
        "group_identity",
    )
    producer = value["producer"]
    files = {r["path"]: r["sha256"] for r in producer["source_files"]}
    require(files.keys() >= REQUIRED_SOURCE, "group_identity")
    try:
        for name, expected_sha in files.items():
            path = ROOT / name
            require(
                path.resolve().is_relative_to(ROOT) and not path.is_symlink(),
                "group_identity",
            )
            require(
                hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha,
                "group_identity",
            )
        require(
            hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest()
            == producer["lock_sha256"],
            "group_identity",
        )
    except OSError as error:
        raise GroupError("group_identity") from error
    require(
        producer["python_version"] == platform.python_version()
        and producer["unicode_version"] == unicodedata.unidata_version
        and producer["platform_profile"] == sys.platform + ":" + platform.machine(),
        "group_identity",
    )
    return actual


def membership_and_coverage(value):
    symbols = value["graph"]["symbol_lookup"]
    policy = value["policy"]
    members = [
        member for group in policy["membership"] for member in group["members"]
    ] + policy["unassigned_ids"]
    require(
        len(members) == len(set(members)) and set(members) == set(symbols),
        "group_membership",
    )
    records = {r["path"]: r for r in value["source_binding"]["coverage_records"]}
    counts = Counter(symbol["file"] for symbol in symbols.values())
    require(set(counts) <= records.keys(), "group_coverage")
    for path, record in records.items():
        state = record["status"]
        require(
            (state != "processed_no_symbols" or not counts[path])
            and (state != "processed" or counts[path] > 0),
            "group_coverage",
        )
        require(
            state == "processed"
            or bool(record.get("diagnostic_refs"))
            or state == "processed_no_symbols",
            "group_coverage",
        )
        require(
            state != "skipped_by_producer_filter" or not counts[path], "group_coverage"
        )
    for relation in value["graph"]["relationships"]:
        if "file" in relation:
            require(relation["file"] in records, "group_coverage")
    return records


def budget(value):
    require(value["settings"]["limits"] == LIMITS, "group_budget")
    graph = value["graph"]
    require(len(graph["symbol_lookup"]) <= LIMITS["max_symbols"], "group_budget")
    require(
        sum(len(graph.get(k, [])) for k in ("relationships", "call_facts", "errors"))
        <= LIMITS["max_relationships"],
        "group_budget",
    )


def dependency_profile(value):
    installed = {}
    for distribution in metadata.distributions():
        name = re.sub(r"[-_.]+", "-", distribution.metadata["Name"]).lower()
        installed[name] = distribution.version
    requested = {r["name"]: r["version"] for r in value["producer"]["dependencies"]}
    require(
        {"networkx", "igraph", "leidenalg", "psutil"} <= requested.keys(),
        "group_dependency",
    )
    require(requested == installed, "group_dependency")
    for row in value["producer"]["dependencies"]:
        if row["artifact_sha256"] is not None:
            direct = metadata.distribution(row["name"]).read_text("direct_url.json")
            available = (
                json.loads(direct)
                .get("archive_info", {})
                .get("hashes", {})
                .get("sha256")
                if direct
                else None
            )
            require(available == row["artifact_sha256"], "group_dependency")


def load_engine(value):
    try:
        # Native imports follow successful schema, identity, joins and budgets.
        from chunker.clustering.engine import ClusteringEngine  # noqa: PLC0415
        from chunker.clustering.metrics import MetricsCalculator  # noqa: PLC0415
        from chunker.clustering.weights import EdgeWeightConfig  # noqa: PLC0415

        files = {r["path"]: r["sha256"] for r in value["producer"]["source_files"]}
        for name, module in list(sys.modules.items()):
            if name == "chunker" or name.startswith("chunker."):
                if getattr(module, "__file__", None) is None:
                    locations = getattr(module, "__path__", ())
                    require(
                        isinstance(
                            getattr(module, "__loader__", None),
                            machinery.NamespaceLoader,
                        )
                        and bool(locations)
                        and all(
                            Path(p).resolve().is_relative_to(ROOT) for p in locations
                        ),
                        "group_dependency",
                    )
                    continue
                path = Path(module.__file__).resolve()
                require(path.is_relative_to(ROOT), "group_dependency")
                require(
                    files.get(path.relative_to(ROOT).as_posix())
                    == hashlib.sha256(path.read_bytes()).hexdigest(),
                    "group_dependency",
                )
        return ClusteringEngine, MetricsCalculator, EdgeWeightConfig
    except (ImportError, OSError, AttributeError) as error:
        raise GroupError("group_dependency", 2) from error


def compute(value):
    Engine, Calculator, Config = load_engine(value)
    settings = value["settings"]
    symbols = value["graph"]["symbol_lookup"]
    relationships = value["graph"]["relationships"]
    buckets = [
        (r["boundary_id"], r["members"])
        for r in value["policy"]["membership"]
        if r["members"]
    ]
    buckets.append((None, value["policy"]["unassigned_ids"]))
    owners = {member: boundary for boundary, members in buckets for member in members}
    eligible, omitted = [], []
    for index, relation in enumerate(relationships):
        left, right = relation.get("from"), relation.get("to")
        reason = None
        if relation.get("resolution") in ("unresolved", "ambiguous"):
            reason = relation["resolution"]
        elif left is None or right is None:
            reason = "missing_endpoint"
        elif (
            left not in symbols
            or right not in symbols
            or relation.get("is_internal") is False
        ):
            reason = "external"
        elif relation.get("type") not in ("imports", "calls", "inherits", "type_ref"):
            reason = "unsupported_kind"
        elif left == right:
            reason = "self_loop"
        elif owners[left] != owners[right]:
            reason = "cross_hard_boundary"
        if reason:
            omitted.append(
                {"relationship_index": index, "reason": reason, "fact": relation}
            )
        else:
            eligible.append(relation)
    groups, infrastructure, raw_results, weighted = [], [], [], []
    revision = value["policy"]["revision"]

    for boundary, members in buckets:
        subset = {key: symbols[key] for key in sorted(members)}
        edges = [r for r in eligible if r["from"] in subset and r["to"] in subset]
        engine = Engine(
            weight_config=Config(**settings["weights"]),
            seed=settings["seed"],
            coarse_resolution=settings["coarse_resolution"],
            fine_resolution=settings["fine_resolution"],
            detect_infrastructure=settings["detect_infrastructure"],
            infrastructure_threshold=settings["infrastructure_threshold"],
        )
        graph = engine._build_graph(subset, edges)
        calculator = Calculator(graph)
        weighted.extend(
            {"from": min(a, b), "to": max(a, b), "weight": data["weight"]}
            for a, b, data in graph.edges(data=True)
        )

        def add_node(node, parent_id=None, parent_members=None):
            selected = sorted(node["members"])
            require(len(selected) == len(set(selected)), "group_compute")
            require(set(selected) <= set(members), "group_compute")
            preimage = {
                "policy_revision": revision,
                "parent_members": parent_members or [],
                "heuristic_level": node["level"],
                "members": selected,
            }
            identifier = digest("membership", preimage)
            measured = calculator.calculate_cluster_metrics(
                identifier, selected
            ).to_dict()
            groups.append(
                {
                    "id": identifier,
                    "parent_id": parent_id,
                    "heuristic_level": node["level"],
                    "members": selected,
                    "metrics": measured,
                    "reasons": [
                        {
                            "boundary_id": boundary,
                            "mode": value["policy"]["mode"],
                            "authority": "proposal_only",
                        }
                    ],
                }
            )
            children = node["children"]
            if children:
                flattened = [m for child in children for m in child["members"]]
                require(
                    len(flattened) == len(set(flattened))
                    and set(flattened) == set(selected),
                    "group_compute",
                )
                require(
                    len({tuple(sorted(c["members"])) for c in children})
                    == len(children),
                    "group_compute",
                )
                for child in sorted(
                    children, key=lambda c: (sorted(c["members"]), c["level"])
                ):
                    require(child["parent_id"] == node["id"], "group_compute")
                    add_node(child, identifier, selected)

        if value["policy"]["mode"] == "dependency_assisted":
            result = engine.cluster(subset, edges)
            require(
                set(result["hierarchy"]["members"]) == set(members), "group_compute"
            )
            add_node(result["hierarchy"])
            require(set(result["infrastructure"]) <= set(members), "group_compute")
            infrastructure.extend(result["infrastructure"])
            raw_results.append(
                {
                    "boundary_id": boundary,
                    "result": result,
                    "effective_settings": {
                        "seed": engine.seed,
                        "weights": vars(engine.weight_config),
                        "coarse_resolution": engine.coarse_resolution,
                        "fine_resolution": engine.fine_resolution,
                        "detect_infrastructure": engine.detect_infrastructure,
                        "infrastructure_threshold": engine.infrastructure_threshold,
                    },
                }
            )
        else:
            add_node(
                {
                    "id": None,
                    "level": (
                        "declared_boundary" if boundary is not None else "unassigned"
                    ),
                    "members": members,
                    "children": [],
                }
            )
    require(len({g["id"] for g in groups}) == len(groups), "group_compute")
    groups.sort(key=lambda g: g["id"])
    weighted.sort(key=lambda r: (r["from"], r["to"]))
    return {
        "groups": groups,
        "infrastructure_ids": sorted(set(infrastructure)),
        "metrics": {
            "by_group": [g["metrics"] for g in groups],
            "weighted_edges": weighted,
            "semantics": "induced eligible graph; topology metrics are unweighted heuristics",
        },
        "relationships": relationships,
        "omitted_graph_facts": omitted,
    }, raw_results


def worker(value, connection):
    try:
        result, raw = compute(value)
        payload = {
            "status": "ok",
            "result": result,
            "raw_engine": raw,
            "hash_probe": hash("chunker-group-hash-control"),
        }
        require(len(encoded(payload)) <= LIMITS["max_output_bytes"], "group_compute")
    except GroupError as error:
        payload = {"status": error.reason}
    except Exception:
        payload = {"status": "group_compute"}
    try:
        connection.send(payload)
    finally:
        connection.close()


def run_worker(value):
    try:
        import psutil  # noqa: PLC0415 -- after profile validation
    except ImportError as error:
        raise GroupError("group_dependency", 2) from error

    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=worker, args=(value, send))
    started = False
    failed = True
    try:
        process.start()
        started = True
        send.close()
        deadline = time.monotonic() + 120
        peak = 0
        while not receive.poll(0.05):
            require(process.is_alive() and time.monotonic() < deadline, "group_compute")
            try:
                peak = max(peak, psutil.Process(process.pid).memory_info().rss)
            except psutil.NoSuchProcess:
                continue
            require(peak <= 1073741824, "group_compute")
        payload = receive.recv()
        # The receipt precedes interpreter teardown, which can exceed a fixed 1s
        # on a loaded host (treesitter-chunker#514 N2). Wait out the remaining
        # total deadline only; a child still alive after it is refused below.
        process.join(max(0.0, deadline - time.monotonic()))
        require(not process.is_alive() and process.exitcode == 0, "group_compute")
        failed = False
        return payload, {
            "native_worker_pid": process.pid,
            "peak_sampled_rss": peak,
            "native_hash_probe": payload.get("hash_probe"),
            "rss_limit": 1073741824,
            "deadline_seconds": 120,
        }
    except (EOFError, OSError) as error:
        raise GroupError("group_compute") from error
    finally:
        try:
            if started and process.is_alive():
                process.terminate()
                process.join(1)
                if process.is_alive():
                    process.kill()
                    process.join(1)
            receive.close()
            send.close()
        except BaseException:
            if not failed:
                raise


def pairs(rows):
    result = {}
    for key, value in rows:
        require(key not in result, "group_schema")
        result[key] = value
    return result


def execute(args):
    output = Path(args.output)
    require(
        output.is_absolute()
        and output.parent.is_dir()
        and not output.exists()
        and not output.is_symlink()
        and not output.resolve().is_relative_to(ROOT),
        "group_schema",
    )
    with Path(args.request).open("rb") as stream:
        transport = stream.read(LIMITS["max_input_bytes"] + 1)
    require(len(transport) <= LIMITS["max_input_bytes"], "group_budget")
    try:
        original = json.loads(
            transport,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(GroupError("group_schema")),
        )
        schema(original)
    except (UnicodeError, ValueError, RecursionError) as error:
        if isinstance(error, GroupError):
            raise
        raise GroupError("group_schema") from error
    value = normalize(original)
    expected = {
        "request": args.expected_request_sha256,
        "source-binding": args.expected_source_binding_sha256,
        "profile": args.expected_profile_sha256,
    }
    actual = validate_identity(value, expected)
    records = membership_and_coverage(value)
    budget(value)
    try:
        dependency_profile(value)
    except (GroupError, metadata.PackageNotFoundError, OSError) as error:
        raise GroupError("group_dependency", 2) from error
    started = time.time()
    try:
        payload, resource = run_worker(value)
        if payload["status"] == "group_dependency":
            raise GroupError("group_dependency", 2)
        require(payload["status"] == "ok", "group_compute")
        counts = Counter(r["reason"] for r in payload["result"]["omitted_graph_facts"])
        proposal = {
            "schema": "chunker.group.proposal.v1",
            "request_digest": actual["request"],
            "source_binding_digest": actual["source-binding"],
            "profile_digest": actual["profile"],
            **{
                key: value[key]
                for key in ("source_binding", "producer", "settings", "policy")
            },
            **payload["result"],
            "coverage": {
                "records": value["source_binding"]["coverage_records"],
                "status": (
                    "partial"
                    if any(
                        r["status"] in ("failed", "skipped_by_producer_filter")
                        for r in records.values()
                    )
                    or value["graph"].get("errors")
                    else "complete_within_selected_source"
                ),
                "symbols": len(value["graph"]["symbol_lookup"]),
                "relationships": len(value["graph"]["relationships"]),
                "omitted_by_reason": dict(sorted(counts.items())),
                "unknowns": [
                    r
                    for r in value["source_binding"]["coverage_records"]
                    if r["status"] in ("failed", "skipped_by_producer_filter")
                ],
            },
            "approval": "proposal_only",
        }
        proposal["proposal_digest"] = digest("proposal", proposal)
        files = {
            "proposal.json": encoded(proposal),
            "raw_graph.json": encoded(original["graph"]),
            "raw_engine.json": encoded(payload["raw_engine"]),
            "request.json": transport,
        }
        operational = {
            "started_unix": started,
            "finished_unix": time.time(),
            "output": str(output),
            "request": str(Path(args.request).resolve()),
            "resources": resource,
            "artifacts": {
                name: {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
                for name, body in files.items()
            },
            "raw_graph_encoding": "J(original parsed graph); exact request transport retained separately",
            "numeric_summary": "Any native raw cluster_edges weights are legacy integer summaries, not weighted-fact metrics",
        }
        files["operational.json"] = encoded(operational)
        require(
            sum(map(len, files.values())) <= LIMITS["max_output_bytes"], "group_compute"
        )
    except GroupError as error:
        if error.reason == "group_compute":
            output.mkdir()
            (output / "diagnostic.json").write_bytes(encoded({"reason": error.reason}))
        raise
    output.mkdir()
    proposal_bytes = files.pop("proposal.json")
    for name, body in files.items():
        with (output / name).open("xb") as stream:
            stream.write(body)
    with (output / "proposal.pending").open("xb") as stream:
        stream.write(proposal_bytes)
    (output / "proposal.pending").rename(output / "proposal.json")
    return proposal["proposal_digest"]


def report(stream, value):
    """Write one receipt/diagnostic line; return False instead of raising."""
    try:
        # Write straight to the descriptor and require every byte: a buffered
        # write can return None (non-blocking sink) or short without raising.
        stream.flush()
        data = memoryview(encoded(value) + b"\n")
        try:
            descriptor = stream.fileno()
        except (AttributeError, OSError, ValueError):
            # In-memory streams (e.g. captured test output) have no descriptor.
            written = stream.buffer.write(data)
            stream.buffer.flush()
            if written != len(data):
                raise OSError("short report write")
            return True
        while data:
            written = os.write(descriptor, data)
            if not written:
                raise OSError("short report write")
            data = data[written:]
        return True
    except Exception:
        # Drain undeliverable buffered bytes so exit-time flushing cannot fail late.
        try:
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), stream.fileno())
        except Exception:
            pass
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--expected-request-sha256", required=True)
    parser.add_argument("--expected-source-binding-sha256", required=True)
    parser.add_argument("--expected-profile-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = execute(args)
    except GroupError as error:
        report(sys.stderr, {"reason": error.reason})
        return error.exit_code
    except Exception as error:
        report(sys.stderr, {"reason": "group_setup", "type": type(error).__name__})
        return 2
    # proposal.json is already published; a reporting failure cannot unpublish it.
    if report(sys.stdout, {"proposal_digest": result}):
        return 0
    report(sys.stderr, {"reason": "group_report"})
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
