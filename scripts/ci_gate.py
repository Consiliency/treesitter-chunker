"""Evaluate aggregate needs results; never infer success from absent output."""

from __future__ import annotations

import json
import os
from pathlib import Path

JOBS = {"changes", "policy", "test", "platform", "controlled-linux", "docs"}


def evaluate(needs: dict, event: str, phase: str) -> tuple[bool, list[str]]:
    lines = ["| Job | Expected | Actual |", "| --- | --- | --- |"]
    try:
        if phase not in {"A", "C"} or event not in {
            "pull_request",
            "push",
            "schedule",
            "workflow_dispatch",
            "merge_group",
        }:
            raise ValueError("invalid phase/event")
        if phase == "C" and event == "push":
            raise ValueError("phase C has no push trigger")
        if not isinstance(needs, dict) or set(needs) != JOBS:
            raise ValueError("missing or unexpected needs entry")
        if needs["changes"]["result"] != "success":
            raise ValueError("changes did not succeed")
        outputs = needs["changes"]["outputs"]
        if outputs["schema"] != "1" or outputs["policy"] != "true":
            raise ValueError("invalid schema/policy")
        for flag in ("code", "docs", "full"):
            if outputs[flag] not in {"true", "false"}:
                raise ValueError(f"invalid {flag}")
        if outputs["code"] == "true" and outputs["docs"] != "true":
            raise ValueError("code requires docs")
        if (outputs["full"] == "true") != (event in {"schedule", "workflow_dispatch"}):
            raise ValueError("inconsistent full/event")
        if event != "pull_request" and (outputs["code"], outputs["docs"]) != (
            "true",
            "true",
        ):
            raise ValueError("non-PR must run all lanes")
        expected = {
            "changes": True,
            "policy": True,
            "docs": phase == "A" or outputs["docs"] == "true",
        }
        expected.update(
            {
                job: phase == "A" or outputs["code"] == "true"
                for job in ("test", "platform", "controlled-linux")
            }
        )
        passed = True
        for job in sorted(JOBS):
            result = needs[job]["result"]
            required = expected[job]
            valid = result == "success" or (not required and result == "skipped")
            passed &= valid
            lines.append(
                f"| {job} | {'success' if required else 'success or skipped'} | {result} ({'accepted' if valid else 'rejected'}) |"
            )
        return passed, lines
    except (KeyError, TypeError, ValueError) as error:
        return False, lines + [f"Rejected malformed gate input: {error}"]


def main() -> None:
    # Needs is data from env only: no command-line JSON or executable interpolation.
    try:
        needs = json.loads(os.environ["NEEDS_JSON"])
    except (KeyError, ValueError) as error:
        raise SystemExit(f"invalid NEEDS_JSON: {error}") from error
    passed, lines = evaluate(
        needs, os.environ["GITHUB_EVENT_NAME"], os.environ["CI_PHASE"]
    )
    summary = "\n".join(lines) + "\n"
    print(summary)
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
        stream.write(summary)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
