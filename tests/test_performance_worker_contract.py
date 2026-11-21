"""Worker contract for the performance tests' process pools.

Consiliency/treesitter-chunker#669: pytest -n bounds only the test processes,
not the pools that tests/test_performance_advanced.py starts. These checks run
that module's real test bodies on simulated hosts, with chunk_files_parallel
and the clock replaced by a recorder, so they start no pools and time nothing.
They check the worker counts the bodies request, that only an explicit
admission adds the 4-worker measurement, and that the owner-approved bars from
Consiliency/treesitter-chunker#660 still decide its outcome.
"""

import ast
import multiprocessing as mp
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace

import psutil
import pytest
import yaml

from tests import test_performance_advanced as perf

ROOT = Path(__file__).resolve().parents[1]
ENV = perf.ADMITTED_SCALING_ENV

# Test bodies whose requested pool sizes are captured at run time. The
# remaining pools use fixed literals, which
# test_every_pool_size_in_the_module_is_bounded checks statically.
POOL_TESTS = [
    ("TestConcurrentPerformance", "test_multiprocess_scaling"),
    ("TestConcurrentPerformance", "test_multiprocess_scaling_four_workers"),
    ("TestScalabilityLimits", "test_many_small_files_performance"),
    ("TestRealWorldScenarios", "test_mixed_file_sizes_performance"),
]
SCALING = [1, 1, 1, 1, 2, 2, 2]  # warm-up, then best of three per count
FOUR_WORKER_SCALING = [1, 1, 1, 1, 4, 4, 4]
ORDINARY = {
    "test_multiprocess_scaling": SCALING,
    "test_multiprocess_scaling_four_workers": [],
    "test_many_small_files_performance": [2],
    "test_mixed_file_sizes_performance": [2],
}


def ideal(num_workers):
    """Simulated seconds per run: perfect scaling, exact in binary."""
    return 1.0 / num_workers


class Recorder:
    """Stands in for chunk_files_parallel and the clock."""

    def __init__(self, seconds):
        self.seconds = seconds
        self.requests = []
        self.now = 0.0

    def clock(self):
        return self.now

    def chunk_files_parallel(self, file_paths, language, num_workers, **_kwargs):
        self.requests.append(num_workers)
        self.now += self.seconds(num_workers)
        # Enough chunks per file for every chunk-count assertion in the module.
        return {Path(path): [object()] * 400 for path in file_paths}


def simulate_host(monkeypatch, cores, physical, admitted):
    """Report `cores` logical and `physical` cores; set or clear the admission."""

    def psutil_cpu_count(logical=True):
        return cores if logical else physical

    monkeypatch.setattr(mp, "cpu_count", lambda: cores)
    monkeypatch.setattr(os, "cpu_count", lambda: cores)
    if hasattr(os, "process_cpu_count"):
        monkeypatch.setattr(os, "process_cpu_count", lambda: cores)
    monkeypatch.setattr(psutil, "cpu_count", psutil_cpu_count)
    if admitted:
        monkeypatch.setenv(ENV, "1")
    else:
        monkeypatch.delenv(ENV, raising=False)
    # Simulated runs are off-hosted unless a test opts in (run_two_worker_test),
    # so CI's own GITHUB_ACTIONS/CI markers never reach them (#660).
    for name in ("GITHUB_ACTIONS", "CI"):
        monkeypatch.delenv(name, raising=False)


def run_pool_tests(module, monkeypatch, tmp_path, seconds=ideal):
    """Run each pool test body; map its name to (requested counts, skip reason)."""
    recorder = Recorder(seconds)
    monkeypatch.setattr(module, "chunk_files_parallel", recorder.chunk_files_parallel)
    monkeypatch.setattr(
        module,
        "time",
        SimpleNamespace(
            perf_counter=recorder.clock, time=recorder.clock, sleep=lambda _s: None
        ),
    )
    observed = {}
    for class_name, name in POOL_TESTS:
        start = len(recorder.requests)
        work = tmp_path / name
        work.mkdir()
        reason = None
        try:
            getattr(getattr(module, class_name), name)(work)
        except pytest.skip.Exception as skip:
            reason = skip.msg
        observed[name] = (recorder.requests[start:], reason)
    return observed


def check_ordinary(observed):
    """The ordinary-mode contract: at most two workers, 4-worker check skipped."""
    requests = {name: counts for name, (counts, _reason) in observed.items()}
    assert requests == ORDINARY
    assert max(n for counts in requests.values() for n in counts) <= 2
    reason = observed["test_multiprocess_scaling_four_workers"][1]
    assert reason is not None and f"{ENV}=1" in reason
    assert all(
        reason is None
        for name, (_counts, reason) in observed.items()
        if name != "test_multiprocess_scaling_four_workers"
    )


@pytest.mark.parametrize("cores", [2, 24, 64])
def test_ordinary_runs_request_at_most_two_workers(cores, monkeypatch, tmp_path):
    """Physical-core count alone never admits more than two workers."""
    simulate_host(monkeypatch, cores=cores, physical=cores, admitted=False)
    check_ordinary(run_pool_tests(perf, monkeypatch, tmp_path))


@pytest.mark.parametrize("value", ["", "0", "true", "4"])
def test_only_exact_opt_in_admits(value, monkeypatch, tmp_path):
    simulate_host(monkeypatch, cores=64, physical=64, admitted=False)
    monkeypatch.setenv(ENV, value)
    check_ordinary(run_pool_tests(perf, monkeypatch, tmp_path))


def test_admitted_run_adds_only_the_four_worker_measurement(monkeypatch, tmp_path):
    simulate_host(monkeypatch, cores=64, physical=64, admitted=True)
    observed = run_pool_tests(perf, monkeypatch, tmp_path)
    assert observed == {
        "test_multiprocess_scaling": (SCALING, None),
        "test_multiprocess_scaling_four_workers": (FOUR_WORKER_SCALING, None),
        "test_many_small_files_performance": ([2], None),
        "test_mixed_file_sizes_performance": ([2], None),
    }


def four_worker_test(monkeypatch, tmp_path, physical, four_worker_seconds):
    simulate_host(monkeypatch, cores=max(physical, 4), physical=physical, admitted=True)
    recorder = Recorder(lambda n: four_worker_seconds if n == 4 else ideal(n))
    monkeypatch.setattr(perf, "chunk_files_parallel", recorder.chunk_files_parallel)
    monkeypatch.setattr(perf, "time", SimpleNamespace(perf_counter=recorder.clock))
    perf.TestConcurrentPerformance.test_multiprocess_scaling_four_workers(tmp_path)
    return recorder.requests


def test_admitted_four_worker_bar_stays_above_two(monkeypatch, tmp_path):
    """A speedup of exactly 2.0x still fails the owner's > 2x bar."""
    with pytest.raises(AssertionError):
        four_worker_test(monkeypatch, tmp_path, physical=4, four_worker_seconds=0.5)


def test_admitted_four_worker_bar_passes_above_two(monkeypatch, tmp_path):
    requests = four_worker_test(
        monkeypatch, tmp_path, physical=4, four_worker_seconds=0.4375
    )
    assert requests == FOUR_WORKER_SCALING


def test_admitted_run_below_four_physical_cores_is_reported(monkeypatch, tmp_path):
    """The 4-worker runs happen, but the unapplied 2x bar is a visible skip."""
    with pytest.raises(pytest.skip.Exception, match=r"2 physical cores.*1\.10x"):
        four_worker_test(
            monkeypatch, tmp_path, physical=2, four_worker_seconds=1.0 / 1.1
        )


def run_two_worker_test(
    monkeypatch, tmp_path, two_worker_seconds, hosted_env, recorder
):
    """Run test_multiprocess_scaling with simulated timings and environment."""
    simulate_host(monkeypatch, cores=2, physical=2, admitted=False)
    for name, value in hosted_env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(perf, "chunk_files_parallel", recorder.chunk_files_parallel)
    monkeypatch.setattr(perf, "time", SimpleNamespace(perf_counter=recorder.clock))
    perf.TestConcurrentPerformance.test_multiprocess_scaling(tmp_path)


def two_worker_recorder(two_worker_seconds):
    return Recorder(lambda n: two_worker_seconds if n == 2 else ideal(n))


@pytest.mark.parametrize(
    ("two_worker_seconds", "passes"),
    [(0.71875, False), (0.6875, True)],
)
def test_two_worker_bar_stays_at_thirty_percent(
    two_worker_seconds, passes, monkeypatch, tmp_path
):
    """Off a hosted runner the 30% bar gates (owner decision, #660)."""
    recorder = two_worker_recorder(two_worker_seconds)
    if passes:
        run_two_worker_test(monkeypatch, tmp_path, two_worker_seconds, {}, recorder)
    else:
        with pytest.raises(AssertionError):
            run_two_worker_test(monkeypatch, tmp_path, two_worker_seconds, {}, recorder)
    assert recorder.requests == SCALING


@pytest.mark.parametrize(
    ("two_worker_seconds", "passes"),
    [(0.71875, True), (0.999, True), (1.0, False), (1.2, False)],
)
def test_hosted_runner_gates_only_a_real_speedup(
    two_worker_seconds, passes, monkeypatch, tmp_path
):
    """On a hosted runner two workers must only be faster; 30% is reported."""
    hosted = {"GITHUB_ACTIONS": "true"}
    recorder = two_worker_recorder(two_worker_seconds)
    if passes:
        with pytest.warns(UserWarning, match=r"treesitter-chunker#660"):
            run_two_worker_test(
                monkeypatch, tmp_path, two_worker_seconds, hosted, recorder
            )
    else:
        with (
            pytest.raises(AssertionError),
            pytest.warns(UserWarning, match=r"not met \(reported only\)"),
        ):
            run_two_worker_test(
                monkeypatch, tmp_path, two_worker_seconds, hosted, recorder
            )
    assert recorder.requests == SCALING


@pytest.mark.parametrize(
    ("env", "hosted"),
    [
        ({}, False),
        ({"GITHUB_ACTIONS": "true"}, True),
        ({"CI": "true"}, True),
        ({"CI": "1"}, True),
        ({"CI": "TRUE"}, True),
        ({"GITHUB_ACTIONS": "1"}, False),
        ({"GITHUB_ACTIONS": "false"}, False),
        ({"CI": "false"}, False),
        ({"CI": "0"}, False),
        ({"CI": "yes"}, False),
        ({"CI": ""}, False),
    ],
)
def test_hosted_detection_is_explicit_and_fails_closed(env, hosted, monkeypatch):
    """Only explicit markers select hosted mode; anything else keeps 30%."""
    for name in ("GITHUB_ACTIONS", "CI"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert perf.hosted_ci_runner() is hosted


# Named mutations of tests/test_performance_advanced.py. Each must break the
# ordinary-mode contract on the listed simulated hosts.
MUTATIONS = {
    # Restore the pre-#669 one-worker-per-core sizing.
    "M669-cpu-count-sizing": (
        [
            ("import os\n", "import multiprocessing as mp\nimport os\n"),
            (
                "best_scaling_times(tmp_path, [1, 2])",
                "best_scaling_times(tmp_path, sorted({1, 2, 4, mp.cpu_count()}))",
            ),
            ("num_workers=ORDINARY_MAX_WORKERS", "num_workers=mp.cpu_count()"),
        ],
        [2, 24, 64],
    ),
    # Treat four physical cores as admission.
    "M669-physical-cores-admit": (
        [
            (
                "if not scaling_admitted():",
                "if (psutil.cpu_count(logical=False) or 0) < 4:",
            ),
        ],
        [24, 64],
    ),
}


def mutant(name):
    source = Path(perf.__file__).read_text(encoding="utf-8")
    for old, new in MUTATIONS[name][0]:
        assert old in source, (name, old)
        source = source.replace(old, new)
    module = ModuleType(f"perf_{name.replace('-', '_')}")
    module.__file__ = perf.__file__
    exec(compile(source, perf.__file__, "exec"), module.__dict__)  # noqa: S102
    return module


@pytest.mark.parametrize(
    ("name", "cores"),
    [(name, cores) for name, (_edits, hosts) in MUTATIONS.items() for cores in hosts],
)
def test_named_mutations_break_the_contract(name, cores, monkeypatch, tmp_path):
    simulate_host(monkeypatch, cores=cores, physical=cores, admitted=False)
    observed = run_pool_tests(mutant(name), monkeypatch, tmp_path)
    with pytest.raises(AssertionError):
        check_ordinary(observed)


def test_only_ci_full_tier_admits_four_workers():
    """Only full-tier steps on hosted runners admit the measurement.

    That is the CI full-tier steps and release validation; scripts never do.
    """
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    admitted = {
        (job_name, step.get("name")): step["env"][ENV]
        for job_name, job in ci["jobs"].items()
        for step in job.get("steps", [])
        if ENV in (step.get("env") or {})
    }
    assert admitted == {
        ("test", "Pytest"): "${{ needs.changes.outputs.full == 'true' && '1' || '0' }}",
        ("platform", "Full suite on primary Python"): "1",
    }
    assert all(ENV not in (job.get("env") or {}) for job in ci["jobs"].values())
    assert ENV not in str(ci.get("env"))
    release = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    release_admitted = {
        (job_name, step.get("name")): step["env"][ENV]
        for job_name, job in release["jobs"].items()
        for step in job.get("steps", [])
        if ENV in (step.get("env") or {})
    }
    assert release_admitted == {
        ("release-validation", "Validate source and full test tier"): "1",
    }
    assert all(ENV not in (job.get("env") or {}) for job in release["jobs"].values())
    assert ENV not in str(release.get("env"))
    for path in [
        *(ROOT / ".github/workflows").glob("*.y*ml"),
        ROOT / "scripts/run_full_suite.py",
        ROOT / "scripts/run_ci_smoke.py",
        ROOT / "scripts/run_platform_core.py",
    ]:
        if path.name not in {"ci.yml", "release.yml"}:
            assert ENV not in path.read_text(encoding="utf-8"), path


def test_every_pool_size_in_the_module_is_bounded():
    """Every num_workers argument is at most 2, a named bound or the scaling helper's.

    This also covers pools that the run-time capture above does not execute,
    so a later edit to any pool size in the module cannot bypass the bound.
    """
    source = Path(perf.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    helper = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "best_scaling_times"
    )
    helper_nodes = {id(node) for node in ast.walk(helper)}
    seen = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.keyword) and node.arg == "num_workers"):
            continue
        value = node.value
        seen.append(ast.unparse(value))
        if isinstance(value, ast.Constant):
            assert isinstance(value.value, int), ast.unparse(value)
            assert 1 <= value.value <= perf.ORDINARY_MAX_WORKERS, ast.unparse(value)
        elif isinstance(value, ast.Name) and value.id == "ORDINARY_MAX_WORKERS":
            pass
        else:
            # Only the scaling helper forwards its own count; its requests
            # are captured by the run-time tests above.
            assert id(node) in helper_nodes, ast.unparse(value)
            assert isinstance(value, ast.Name) and value.id == "num_workers"
    assert len(seen) >= 5, seen
