"""Write pytest skip reports when CHUNKER_PYTEST_SKIP_REPORT names a JSON file."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


class SkipReport:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.skips: set[tuple[str, str]] = set()

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.skipped and not hasattr(report, "wasxfail"):
            self.record(report)

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.skipped:
            self.record(report)

    def record(self, report: pytest.TestReport | pytest.CollectReport) -> None:
        reason = report.longrepr
        if isinstance(reason, tuple):
            reason = reason[2].removeprefix("Skipped: ")
        self.skips.add((report.nodeid, str(reason)))

    def pytest_sessionfinish(self) -> None:
        rows = [
            {"nodeid": nodeid, "reason": reason}
            for nodeid, reason in sorted(self.skips)
        ]
        self.path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def pytest_configure(config: pytest.Config) -> None:
    path = os.environ.get("CHUNKER_PYTEST_SKIP_REPORT")
    # xdist sends its reports to the controller, which owns the output file.
    if path and not hasattr(config, "workerinput"):
        config.pluginmanager.register(SkipReport(Path(path)))
