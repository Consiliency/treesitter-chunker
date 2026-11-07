"""Opt-in handling of positively identified native policy denials in tests."""

import json
from types import SimpleNamespace

import pytest

from chunker.grammar._native_policy import (
    APPLICATION_CONTROL_MESSAGE,
    is_application_control_error,
)


def skip_policy_error(error):
    if is_application_control_error(error):
        pytest.skip(f"WinError {error.winerror}: {APPLICATION_CONTROL_MESSAGE}")


def skip_policy_reply(reply, command, state, nonce):
    """Skip only an intact, request-bound policy failure from the real worker."""
    rc, stdout, stderr, timed_out, overflow = reply
    if (
        rc != 1
        or state is None
        or state.worker_status != 1
        or not state.cleanup_safe
        or not state.discovery_complete
        or state.error
        or state.forced
        or timed_out
        or overflow
        or not state.start_completed
        or not nonce
        or len(command) < 6
    ):
        return
    try:
        pairs = json.loads(stdout, object_pairs_hook=list)
        if not isinstance(pairs, list) or not all(
            isinstance(pair, tuple) and len(pair) == 2 for pair in pairs
        ):
            return
        record = dict(pairs)
    except (ValueError, TypeError, RecursionError):
        return
    expected = {
        "schema": "native_probe.v1",
        "nonce": nonce,
        "language": command[-4],
        "sha256": command[-3],
        "failure": "policy_blocked",
    }
    if record == expected and len(pairs) == len(expected):
        pytest.skip(APPLICATION_CONTROL_MESSAGE)


def skip_policy_reply_under_status_fault(
    reply, command, state, nonce, observed_statuses, injected_error
):
    """Skip a status-fault test only for the same intact policy failure.

    Such a test hides the worker's exit status from the product on purpose, so
    ``state.worker_status`` is unavailable and ``state.error`` is the injected
    fault. The test reads the actual status from the same handle before
    injecting the fault. Only that observed status (always 1) and the product
    error being exactly the injected one stand in for those two fields; every
    other condition of :func:`skip_policy_reply` still applies unchanged.
    """
    if (
        state is None
        or state.worker_status is not None
        or state.error != injected_error
        or not observed_statuses
        or set(observed_statuses) != {1}
    ):
        return
    view = SimpleNamespace(
        worker_status=1,
        cleanup_safe=state.cleanup_safe,
        discovery_complete=state.discovery_complete,
        error="",
        forced=state.forced,
        start_completed=state.start_completed,
    )
    skip_policy_reply(reply, command, view, nonce)


def skip_policy_subprocess(completed):
    """Recognize only the trusted test driver's typed exception record."""
    if completed.returncode != 77:
        return
    try:
        pairs = json.loads(completed.stdout, object_pairs_hook=list)
        if not isinstance(pairs, list) or not all(
            isinstance(pair, tuple) and len(pair) == 2 for pair in pairs
        ):
            return
        record = dict(pairs)
    except (ValueError, TypeError, RecursionError):
        return
    if len(pairs) == len(record) and record == {
        "schema": "native_test.policy_result.v1",
        "reason": "policy_blocked",
    }:
        pytest.skip(APPLICATION_CONTROL_MESSAGE)
    if (
        len(pairs) == len(record)
        and set(record) == {"schema", "winerror"}
        and record["schema"] == "native_test.policy.v1"
        and type(record["winerror"]) is int
        and record["winerror"] in {4551, 1260}
    ):
        pytest.skip(f"WinError {record['winerror']}: {APPLICATION_CONTROL_MESSAGE}")


def run_isolated_baml_parse(root, library, fixture, *, timeout):
    """Keep the real root oracle; identify policy blocks by exception type/code."""
    import subprocess
    import sys

    code = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from chunker.grammar._native_policy import NativePolicyBlockedError
from chunker.grammar_management.core import load_compiled_grammar
try:
    root = load_compiled_grammar(Path(sys.argv[2]), 'baml').parse(Path(sys.argv[3]).read_bytes()).root_node
except NativePolicyBlockedError as error:
    print(json.dumps({'schema': 'native_test.policy.v1', 'winerror': error.winerror}), flush=True)
    raise SystemExit(77)
raise SystemExit(0 if root.type == 'source_file' and not root.has_error else 3)
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", code, str(root), str(library), str(fixture)],
        check=False,
        capture_output=True,
        timeout=timeout,
    )
    skip_policy_subprocess(completed)
    return completed


def policy_aware_native_driver(code):
    """Wrap a trusted test driver, preserving all its success-path assertions."""
    return f"""
import json, sys
sys.path.insert(0, sys.argv[1])
from chunker.grammar._native_policy import NativePolicyBlockedError
try:
    exec({code!r})
except NativePolicyBlockedError as error:
    print(json.dumps({{'schema': 'native_test.policy.v1', 'winerror': error.winerror}}), flush=True)
    raise SystemExit(77)
"""
