#!/usr/bin/env python
"""Initialize trace artifacts for a spec.

This script is invoked by /ai-dev-kit:trace-init to seed branches, issues,
draft PR templates, and local trace metadata for deterministic orchestration.
"""

import argparse
from pathlib import Path

from ai_dev_kit.trace import TraceInitializer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize trace artifacts for a spec.")
    parser.add_argument("spec_id", help="Specification identifier, e.g., SPEC-123")
    parser.add_argument("--spec-url", help="Link to the spec for traceability")
    parser.add_argument("--repo", help="owner/name repository slug for GitHub automation")
    parser.add_argument("--base-branch", default="main", help="Base branch for the PR (default: main)")
    parser.add_argument(
        "--plan",
        action="append",
        default=[],
        help="Path to a phase/plan markdown file to update with trace markers.",
    )
    parser.add_argument(
        "--lane-manifest",
        action="append",
        default=[],
        help="Lane manifest paths (markdown or json) to update with trace markers.",
    )
    parser.add_argument(
        "--output-dir",
        default=".claude/ai-dev-kit/trace",
        help="Directory for generated artifacts (default: .claude/ai-dev-kit/trace)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip GitHub API calls even if a token is available.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    initializer = TraceInitializer(
        spec_id=args.spec_id,
        spec_url=args.spec_url,
        repo=args.repo,
        base_branch=args.base_branch,
        output_dir=Path(args.output_dir),
    )
    initializer.initialize(
        plan_paths=[Path(path) for path in args.plan],
        lane_manifest_paths=[Path(path) for path in args.lane_manifest],
        use_github=not args.offline,
    )
    print(f"Trace initialized for {args.spec_id} in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
