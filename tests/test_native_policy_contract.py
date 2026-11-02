"""Application-control classification remains fail-closed and request-bound."""

import json
import pickle
import sys
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from chunker.grammar import integrity
from chunker.grammar._native_policy import (
    APPLICATION_CONTROL_MESSAGE,
    NativePolicyBlockedError,
    is_application_control_error,
)
from tests.native_policy import (
    skip_policy_error,
    skip_policy_reply,
    skip_policy_reply_under_status_fault,
)


def policy_error(code=4551):
    error = OSError("deliberate OS policy denial")
    error.winerror = code
    return error


@pytest.mark.parametrize(
    ("code", "blocked"),
    [(4551, True), (1260, True), (5, False), (577, False), (13, False)],
)
def test_policy_classification_requires_explicit_os_code(code, blocked):
    assert is_application_control_error(policy_error(code)) is blocked
    assert not is_application_control_error(PermissionError(13, "WinError 4551"))
    assert not is_application_control_error(RuntimeError("Application Control policy"))


def test_direct_loader_policy_error_is_actionable_and_keeps_os_evidence(monkeypatch):
    from chunker.grammar_management import core

    original = policy_error()

    def denied(*args):
        raise original

    monkeypatch.setattr(core.ctypes, "CDLL", denied)
    with pytest.raises(NativePolicyBlockedError) as caught:
        core.load_compiled_grammar(Path("blocked.dll"), "baml")
    assert caught.value.__cause__ is original
    assert caught.value.winerror == 4551
    restored = pickle.loads(pickle.dumps(caught.value))
    assert isinstance(restored, NativePolicyBlockedError)
    assert restored.winerror == 4551
    assert APPLICATION_CONTROL_MESSAGE in str(restored)
    assert APPLICATION_CONTROL_MESSAGE in str(caught.value)
    assert "unsigned" in str(caught.value).lower()
    assert "administrator" in str(caught.value)


@pytest.mark.parametrize(
    ("code", "reason"),
    [(4551, "policy_blocked"), (1260, "policy_blocked"), (5, "load_failed")],
)
def test_real_child_worker_emits_distinct_policy_failure(
    tmp_path, monkeypatch, capsys, code, reason
):
    from chunker.grammar_management import core

    snapshot = tmp_path / "fixture.dll"
    snapshot.write_bytes(b"approved fixture bytes")
    digest = sha256(snapshot.read_bytes()).hexdigest()
    monkeypatch.setattr(integrity, "_worker_ready", lambda *args: None)

    def denied(*args):
        raise policy_error(code)

    monkeypatch.setattr(core, "load_compiled_grammar", denied)
    assert (
        integrity._native_probe_child(str(snapshot), "baml", digest, "", "request") == 1
    )
    record = json.loads(capsys.readouterr().out)
    assert record == {
        "schema": "native_probe.v1",
        "nonce": "request",
        "language": "baml",
        "sha256": digest,
        "failure": reason,
    }
    assert "loader_returned" not in record and "parse_returned" not in record


@pytest.mark.parametrize(
    ("fault", "reason"),
    [
        (None, "policy_blocked"),
        ("nonce", "child_failed"),
        ("digest", "child_failed"),
        ("worker_status", "child_failed"),
        ("forced", "child_failed"),
        ("unsafe", "child_failed"),
        ("empty", "child_failed"),
    ],
)
def test_parent_policy_failure_never_admits_or_inspects(
    tmp_path, monkeypatch, fault, reason
):
    artifact = tmp_path / "fixture.dll"
    artifact.write_bytes(b"approved fixture bytes")
    digest = sha256(artifact.read_bytes()).hexdigest()
    inspected = []

    def child(command, cwd, timeout, *, worker_nonce, lifecycle):
        lifecycle.worker_status = 7 if fault == "worker_status" else 1
        lifecycle.cleanup_safe = fault != "unsafe"
        lifecycle.forced = fault == "forced"
        record = {
            "schema": "native_probe.v1",
            "nonce": worker_nonce,
            "language": "baml",
            "sha256": digest,
            "failure": "policy_blocked",
        }
        if fault == "nonce":
            record["nonce"] = "wrong"
        if fault == "digest":
            record["sha256"] = "0" * 64
        return (
            1,
            b"" if fault == "empty" else json.dumps(record).encode(),
            b"",
            False,
            False,
        )

    monkeypatch.setattr(integrity, "_read_child", child)
    result = integrity.probe_native_grammar(
        artifact,
        "baml",
        provenance={"sha256": digest},
        inspect_artifact=inspected.append,
    )
    assert (
        not result.supported
        and result.reason == reason
        and result.artifact_sha256 is None
    )
    assert inspected == []
    assert result.message == (
        APPLICATION_CONTROL_MESSAGE if reason == "policy_blocked" else None
    )


def test_parent_launch_policy_error_has_distinct_result(tmp_path, monkeypatch):
    artifact = tmp_path / "fixture.dll"
    artifact.write_bytes(b"approved fixture bytes")

    def denied(*args, **kwargs):
        raise policy_error()

    monkeypatch.setattr(integrity.subprocess, "Popen", denied)
    roots = []
    original = integrity.tempfile.mkdtemp

    def root(*args, **kwargs):
        value = original(*args, **kwargs)
        roots.append(Path(value))
        return value

    monkeypatch.setattr(integrity.tempfile, "mkdtemp", root)
    result = integrity.probe_native_grammar(
        artifact,
        "baml",
        provenance={"sha256": sha256(artifact.read_bytes()).hexdigest()},
    )
    assert result == integrity.NativeProbeResult(False, "policy_blocked", None)
    assert result.message == APPLICATION_CONTROL_MESSAGE
    assert roots[
        0
    ].exists(), "policy classification must not erase uncertain launch state"
    # This injected Popen never created a process; fixture cleanup owns this root.
    integrity.shutil.rmtree(roots[0])


def test_policy_guidance_reaches_manager_and_analyzer(tmp_path, monkeypatch):
    from chunker._internal import grammar_management as managers
    from chunker.languages.compatibility import grammar_analyzer as analyzers

    blocked = integrity.NativeProbeResult(False, "policy_blocked", None)
    monkeypatch.setattr(
        managers, "probe_native_grammar", lambda *args, **kwargs: blocked
    )
    monkeypatch.setattr(
        analyzers, "probe_native_grammar", lambda *args, **kwargs: blocked
    )
    (tmp_path / "baml.so").write_bytes(b"fixture")
    manager = managers.SmartGrammarManager(tmp_path, tmp_path / "sources")
    health = manager.diagnose_grammar_issues("baml")
    assert (
        health.status == "incompatible" and health.validation_reason == "policy_blocked"
    )
    assert APPLICATION_CONTROL_MESSAGE in health.issues
    assert not any("Recompile" in item for item in health.recommendations)
    analyzer = analyzers.GrammarAnalyzer(tmp_path)
    report = analyzer.generate_grammar_report("baml")
    assert APPLICATION_CONTROL_MESSAGE in report
    capabilities = analyzer.get_grammar_capabilities("baml")
    assert not capabilities["supported"] and capabilities["artifact_sha256"] is None
    assert capabilities["validation_message"] == APPLICATION_CONTROL_MESSAGE
    exported = tmp_path / "analysis.json"
    analyzer.export_analysis_data(exported)
    record = json.loads(exported.read_text())
    assert record["grammars"] == {}
    assert (
        record["validation_failures"]["baml"]["capabilities"]["validation_message"]
        == APPLICATION_CONTROL_MESSAGE
    )


def assert_not_policy_skip(label, predicate, *args):
    """A rejected case must stay a test failure; an over-accepting predicate fails."""
    try:
        predicate(*args)
    except pytest.skip.Exception as skipped:
        pytest.fail(f"{label} must stay a test failure, not a policy skip: {skipped}")


def valid_policy_reply():
    state = SimpleNamespace(
        worker_status=1,
        cleanup_safe=True,
        discovery_complete=True,
        error="",
        forced=False,
        start_completed=True,
    )
    command = ["python", "snapshot", "baml", "digest", "", "nonce"]
    record = {
        "schema": "native_probe.v1",
        "nonce": "nonce",
        "language": "baml",
        "sha256": "digest",
        "failure": "policy_blocked",
    }
    return state, command, record


def test_test_skip_accepts_only_positive_policy_evidence():
    state, command, record = valid_policy_reply()
    reply = (1, json.dumps(record).encode(), b"", False, False)
    with pytest.raises(
        pytest.skip.Exception, match="Blocked by OS application-control policy"
    ):
        skip_policy_reply(reply, command, state, "nonce")
    with pytest.raises(pytest.skip.Exception, match="4551"):
        skip_policy_error(policy_error())
    for label, error in (
        ("access denied", PermissionError(13, "access denied")),
        ("generic OSError", OSError("generic loader failure")),
        ("winerror 5", policy_error(5)),
        ("winerror 32", policy_error(32)),
        ("bool winerror", policy_error(True)),
    ):
        assert_not_policy_skip(label, skip_policy_error, error)


@pytest.mark.parametrize(
    "fault",
    [
        "empty",
        "nonce",
        "duplicate",
        "malformed",
        "generic",
        "timeout",
        "status",
        "unsafe",
        "forced",
    ],
)
def test_test_skip_preserves_protocol_failures(fault):
    state, command, record = valid_policy_reply()
    if fault == "nonce":
        record["nonce"] = "wrong"
    if fault == "generic":
        record["failure"] = "load_failed"
    if fault == "status":
        state.worker_status = 7
    if fault == "unsafe":
        state.cleanup_safe = False
    if fault == "forced":
        state.forced = True
    stdout = json.dumps(record).encode()
    if fault == "empty":
        stdout = b""
    if fault == "malformed":
        stdout = b"not JSON"
    if fault == "duplicate":
        stdout = stdout[:-1] + b',"failure":"policy_blocked"}'
    assert_not_policy_skip(
        fault,
        skip_policy_reply,
        (1, stdout, b"", fault == "timeout", False),
        command,
        state,
        "nonce",
    )


INJECTED = "GetExitCodeProcess unavailable"


def status_fault_policy_reply():
    state, command, record = valid_policy_reply()
    state.worker_status, state.error = None, INJECTED
    return state, command, (1, json.dumps(record).encode(), b"", False, False)


def test_status_fault_skip_accepts_only_observed_policy_failure():
    state, command, reply = status_fault_policy_reply()
    with pytest.raises(
        pytest.skip.Exception, match="Blocked by OS application-control policy"
    ):
        skip_policy_reply_under_status_fault(
            reply, command, state, "nonce", [1, 1], INJECTED
        )


@pytest.mark.parametrize(
    "fault",
    [
        "no_observation",
        "observed_zero",
        "observed_mixed",
        "other_error",
        "product_status",
        "unsafe",
        "forced",
        "timeout",
        "generic",
    ],
)
def test_status_fault_skip_preserves_protocol_failures(fault):
    state, command, reply = status_fault_policy_reply()
    observed = {"no_observation": [], "observed_zero": [0], "observed_mixed": [1, 0]}
    if fault == "other_error":
        state.error = "WaitForSingleObject unavailable"
    if fault == "product_status":
        state.worker_status = 1
    if fault == "unsafe":
        state.cleanup_safe = False
    if fault == "forced":
        state.forced = True
    if fault == "timeout":
        reply = reply[:3] + (True, False)
    if fault == "generic":
        record = json.loads(reply[1])
        record["failure"] = "load_failed"
        reply = (1, json.dumps(record).encode(), b"", False, False)
    assert_not_policy_skip(
        fault,
        skip_policy_reply_under_status_fault,
        reply,
        command,
        state,
        "nonce",
        observed.get(fault, [1]),
        INJECTED,
    )


def test_isolated_worker_policy_failure_uses_real_protocol(tmp_path, monkeypatch):
    artifact = tmp_path / "fixture.dll"
    artifact.write_bytes(b"approved fixture bytes")
    digest = sha256(artifact.read_bytes()).hexdigest()
    original = integrity._read_child
    observations = []
    denied = (
        "def denied(*args):\n"
        "    error = OSError('deliberate test policy denial')\n"
        "    error.winerror = 4551\n"
        "    raise error\n"
    )

    def read(command, cwd, timeout, **kwargs):
        command = list(command)
        command[3] = command[3].replace(
            "raise SystemExit(_native_probe_child(*sys.argv[2:]))",
            "import chunker.grammar_management.core as core; "
            f"exec({denied!r}); core.load_compiled_grammar=denied; "
            "raise SystemExit(_native_probe_child(*sys.argv[2:]))",
        )
        reply = original(command, cwd, timeout, **kwargs)
        observations.append((reply, kwargs["lifecycle"], cwd))
        return reply

    monkeypatch.setattr(integrity, "_read_child", read)
    inspected = []
    result = integrity.probe_native_grammar(
        artifact,
        "baml",
        provenance={"sha256": digest},
        inspect_artifact=inspected.append,
    )
    assert result == integrity.NativeProbeResult(False, "policy_blocked", None)
    assert result.message == APPLICATION_CONTROL_MESSAGE
    assert inspected == []
    reply, state, root = observations[0]
    assert reply[0] == state.worker_status == 1
    assert not reply[3] and not reply[4] and reply[2] == b""
    assert state.start_completed and state.cleanup_safe and not state.forced
    assert not root.exists()


@pytest.mark.parametrize(
    "fault",
    [None, "generic_exit", "generic_code", "duplicate", "text_only", "malformed"],
)
def test_isolated_positive_control_requires_typed_policy_record(fault):
    from tests.native_policy import skip_policy_subprocess

    stdout = b'{"schema":"native_test.policy.v1","winerror":4551}'
    status = 77
    if fault == "generic_exit":
        status = 1
    if fault == "generic_code":
        stdout = b'{"schema":"native_test.policy.v1","winerror":5}'
    if fault == "duplicate":
        stdout = stdout[:-1] + b',"winerror":4551}'
    if fault == "text_only":
        stdout = b"WinError 4551: blocked by Application Control"
    if fault == "malformed":
        stdout = b"["
    result = SimpleNamespace(returncode=status, stdout=stdout)
    if fault is None:
        with pytest.raises(pytest.skip.Exception, match="WinError 4551"):
            skip_policy_subprocess(result)
    else:
        assert_not_policy_skip(fault, skip_policy_subprocess, result)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows indirect fault launcher")
def test_fault_launcher_preserves_positive_policy_failure(tmp_path, monkeypatch):
    from tests import test_compiled_grammar_analysis_contract as compiled

    artifact = tmp_path / "fixture.dll"
    artifact.write_bytes(b"approved fixture bytes")
    monkeypatch.setattr(compiled, "_compile_probe_fixture", lambda *args: artifact)
    real_read = integrity._read_child
    denied = (
        "def denied(*args):\n"
        "    error = OSError('deliberate test policy denial')\n"
        "    error.winerror = 4551\n"
        "    raise error\n"
    )

    def inject(command, cwd, timeout, **kwargs):
        command = list(command)
        index = command.index("-c") + 1
        command[index] = command[index].replace(
            "import os; result=",
            "import chunker.grammar_management.core as core; "
            f"exec({denied!r}); core.load_compiled_grammar=denied; import os; result=",
        )
        reply = real_read(command, cwd, timeout, **kwargs)
        skip_policy_reply(reply, command, kwargs["lifecycle"], kwargs["worker_nonce"])
        return reply

    monkeypatch.setattr(integrity, "_read_child", inject)
    with pytest.raises(
        pytest.skip.Exception, match="Blocked by OS application-control policy"
    ):
        compiled.test_native_valid_ack_abnormal_worker_launcher_zero(
            tmp_path, monkeypatch
        )


def test_staged_publication_policy_result_preserves_old_bytes_and_guidance(
    tmp_path, monkeypatch
):
    from chunker._internal import user_grammar_tools as tools_module

    build = tmp_path / "build"
    build.mkdir()
    destination = build / "baml.so"
    destination.write_bytes(b"old approved bytes")
    source = tmp_path / "new.dll"
    source.write_bytes(b"new approved fixture bytes")
    blocked = integrity.NativeProbeResult(False, "policy_blocked", None)
    monkeypatch.setattr(
        tools_module, "probe_native_grammar", lambda *args, **kwargs: blocked
    )
    pin = {"sha256": sha256(source.read_bytes()).hexdigest()}
    result = tools_module.publish_native_grammar(
        source, destination, "baml", provenance=pin
    )
    assert result == blocked and result.artifact_sha256 is None
    assert destination.read_bytes() == b"old approved bytes"
    assert list(build.iterdir()) == [destination]
    tools = tools_module.UserGrammarTools(
        build, tmp_path / "grammars", trusted_artifacts={"baml": pin}
    )
    outcome = {"errors": [], "status": "pending"}
    assert not tools._publish_library("baml", source, outcome)
    assert outcome["status"] == "error"
    assert APPLICATION_CONTROL_MESSAGE in outcome["errors"][0]
    assert destination.read_bytes() == b"old approved bytes"


@pytest.mark.parametrize("reason", ["policy_blocked", "child_failed", "load_failed"])
def test_trusted_driver_policy_result_is_narrow(reason):
    from tests.native_policy import skip_policy_subprocess

    result = SimpleNamespace(
        returncode=77,
        stdout=json.dumps({"schema": "native_test.policy_result.v1", "reason": reason}),
    )
    if reason == "policy_blocked":
        with pytest.raises(
            pytest.skip.Exception, match="Blocked by OS application-control policy"
        ):
            skip_policy_subprocess(result)
    else:
        assert_not_policy_skip(reason, skip_policy_subprocess, result)


@pytest.mark.parametrize(
    ("returncode", "stdout", "policy"),
    [
        (
            77,
            '{"schema":"native_test.policy_result.v1","reason":"policy_blocked"}',
            True,
        ),
        (
            1,
            '{"schema":"native_test.policy_result.v1","reason":"policy_blocked"}',
            False,
        ),
        (77, "WinError 4551", False),
        (
            77,
            '{"schema":"native_test.policy_result.v1","reason":"child_failed"}',
            False,
        ),
    ],
)
def test_marker_wait_classifies_only_trusted_policy_result(
    tmp_path, returncode, stdout, policy
):
    from tests.test_compiled_grammar_analysis_contract import _wait_for_file

    class Exited:
        def poll(self):
            return returncode

        def communicate(self, timeout):
            return stdout, ""

    process = Exited()
    process.returncode = returncode
    with pytest.raises(pytest.skip.Exception if policy else AssertionError):
        _wait_for_file(tmp_path / "unpublished", process)
