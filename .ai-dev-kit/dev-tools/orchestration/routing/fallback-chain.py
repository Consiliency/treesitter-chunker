#!/usr/bin/env python3
"""
Fallback Chain Executor

Executes a task using a sequence of providers. If one fails, it tries the next.
Useful for critical tasks that must be completed even if the primary agent is unavailable.

Usage:
    ./fallback-chain.py "task description" [--chain p1,p2,p3] [--json]
"""

import sys
import json
import argparse
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Any

SCRIPT_DIR = Path(__file__).parent
ORCHESTRATION_DIR = SCRIPT_DIR.parent
CONFIG_FILE = ORCHESTRATION_DIR / "config.json"

def load_config() -> dict:
    """Load orchestration configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def get_provider_script(provider: str) -> Path:
    """Get the execution script for a provider."""
    # This mapping should ideally be shared or discovered
    provider_scripts = {
        "claude": ORCHESTRATION_DIR / "providers" / "claude-code" / "spawn.sh",
        "openai": ORCHESTRATION_DIR / "providers" / "codex" / "execute.sh",
        "gemini": ORCHESTRATION_DIR / "providers" / "gemini" / "query.sh",
        "cursor": ORCHESTRATION_DIR / "providers" / "cursor" / "agent.sh",
        "opencode": ORCHESTRATION_DIR / "providers" / "opencode" / "execute.sh",
        "ollama": ORCHESTRATION_DIR / "providers" / "ollama" / "query.sh",
    }
    return provider_scripts.get(provider)

def is_enabled(provider: str, config: dict) -> bool:
    """Check if provider is enabled and available."""
    info = config.get("providers", {}).get(provider, {})
    if not info.get("enabled", False):
        return False
    cli_command = info.get("cli_command")
    if not cli_command:
        return True
    return shutil.which(cli_command) is not None

def execute_with_provider(task: str, provider: str) -> Dict[str, Any]:
    """Execute task with a specific provider."""
    script = get_provider_script(provider)

    if not script or not script.exists():
        return {
            "success": False,
            "error": f"Provider script not found: {script}",
            "provider": provider
        }

    try:
        # Run the provider script
        # expecting JSON output or plain text
        result = subprocess.run(
            [str(script), task],
            capture_output=True,
            text=True,
            timeout=300
        )

        # Try to parse stdout as JSON
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            # If not JSON, construct a wrapper
            output = {
                "success": result.returncode == 0,
                "output": result.stdout,
                "stderr": result.stderr
            }

        output["provider"] = provider

        # Check success flag if present, otherwise rely on returncode
        # Update output with success status if not already present
        if "success" not in output:
            output["success"] = result.returncode == 0

        return output

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Task timeout (300s)",
            "provider": provider
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "provider": provider
        }

def main():
    parser = argparse.ArgumentParser(description="Execute task with fallback chain")
    parser.add_argument("task", help="Task description")
    parser.add_argument("--chain", help="Comma-separated list of providers (e.g., claude,openai)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    config = load_config()

    # Determine chain
    if args.chain:
        chain = [p.strip() for p in args.chain.split(",")]
    else:
        chain = config.get("routing", {}).get("fallback_order", ["claude", "openai", "gemini", "cursor"])

    attempts = []
    success = False
    final_result = {}

    print(f"Starting fallback chain: {' -> '.join(chain)}", file=sys.stderr)

    for provider in chain:
        if not is_enabled(provider, config):
            if not args.json:
                print(f"Skipping provider (disabled or missing CLI): {provider}", file=sys.stderr)
            continue
        if not args.json:
            print(f"Trying provider: {provider}...", file=sys.stderr)

        result = execute_with_provider(args.task, provider)
        attempts.append(result)

        if result.get("success", False):
            success = True
            final_result = result
            if not args.json:
                print(f"Success with {provider}!", file=sys.stderr)
            break
        else:
            if not args.json:
                print(f"Failed with {provider}: {result.get('error', 'Unknown error')}", file=sys.stderr)

    if args.json:
        output = {
            "success": success,
            "result": final_result,
            "attempts": attempts
        }
        print(json.dumps(output, indent=2))
    else:
        if success:
            print("\nResult:")
            print(final_result.get("output", ""))
        else:
            print("\nAll providers failed.")
            sys.exit(1)

if __name__ == "__main__":
    main()
