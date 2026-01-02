#!/usr/bin/env python3
"""
Intelligent task routing based on:
1. Task characteristics (what capabilities are needed)
2. Agent availability (rate limits, current usage)
3. Priority matrix (which agent is best for this task type)

Usage:
    ./route-task.py "task description" [--agent NAME] [--dry-run] [--json]
"""

import sys
import json
import re
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

SCRIPT_DIR = Path(__file__).parent
ORCHESTRATION_DIR = SCRIPT_DIR.parent
CONFIG_FILE = ORCHESTRATION_DIR / "config.json"
MATRIX_FILE = SCRIPT_DIR / "priority-matrix.json"
LOG_DIR = Path.home() / ".ai-dev-kit" / "logs"


def load_config() -> dict:
    """Load orchestration configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def load_priority_matrix() -> dict:
    """Load priority matrix configuration."""
    if MATRIX_FILE.exists():
        with open(MATRIX_FILE) as f:
            return json.load(f)
    return {}


def get_usage(provider: str) -> int:
    """Get current daily usage for a provider."""
    today = datetime.now().strftime("%Y%m%d")
    counter_file = LOG_DIR / f"agent-calls-{provider}-{today}"
    try:
        return int(counter_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def get_daily_max(provider: str, config: dict) -> int:
    """Get daily max from config."""
    return config.get("providers", {}).get(provider, {}).get("daily_max", 100)


def is_available(provider: str, config: dict, threshold_pct: int = 80) -> bool:
    """Check if provider is below rate limit warning threshold."""
    usage = get_usage(provider)
    daily_max = get_daily_max(provider, config)
    threshold = daily_max * threshold_pct / 100
    return usage < threshold


def is_enabled(provider: str, config: dict) -> bool:
    """Check if provider is enabled in config."""
    provider_info = config.get("providers", {}).get(provider, {})
    if not provider_info.get("enabled", False):
        return False

    cli_command = provider_info.get("cli_command")
    if not cli_command:
        return True

    return shutil.which(cli_command) is not None


def detect_task_type(task: str, matrix: dict) -> str:
    """Detect task type from description using pattern matching."""
    task_lower = task.lower()
    task_types = matrix.get("task_types", {})

    for task_type, info in task_types.items():
        if task_type == "default":
            continue
        patterns = info.get("patterns", [])
        for pattern in patterns:
            if re.search(pattern, task_lower):
                return task_type

    return "default"


def select_provider(task: str, config: dict, matrix: dict, force_provider: Optional[str] = None) -> dict:
    """Select the best available provider for a task."""

    if force_provider:
        if is_enabled(force_provider, config):
            return {
                "provider": force_provider,
                "task_type": "forced",
                "reason": "Explicitly specified by user",
                "usage": get_usage(force_provider),
                "daily_max": get_daily_max(force_provider, config)
            }
        else:
            return {
                "provider": force_provider,
                "task_type": "forced",
                "reason": "Explicitly specified but disabled in config",
                "warning": True,
                "usage": get_usage(force_provider),
                "daily_max": get_daily_max(force_provider, config)
            }

    task_type = detect_task_type(task, matrix)
    task_info = matrix.get("task_types", {}).get(task_type, {})
    priority_list = task_info.get("priority", ["claude", "openai", "gemini", "cursor"])

    threshold_pct = config.get("routing", {}).get("rate_limit_threshold_pct", 80)

    # Find first available provider
    for provider in priority_list:
        if is_enabled(provider, config) and is_available(provider, config, threshold_pct):
            fallbacks = [
                p for p in priority_list
                if p != provider and is_enabled(p, config) and is_available(p, config, threshold_pct)
            ]
            return {
                "provider": provider,
                "task_type": task_type,
                "task_description": task_info.get("description", ""),
                "reason": f"Best available for {task_type}",
                "usage": get_usage(provider),
                "daily_max": get_daily_max(provider, config),
                "fallbacks": fallbacks
            }

    # All providers at limit or disabled - use default anyway with warning
    default_provider = config.get("routing", {}).get("default_provider", "claude")
    return {
        "provider": default_provider,
        "task_type": task_type,
        "reason": "All providers near limits or disabled - using default",
        "warning": True,
        "usage": get_usage(default_provider),
        "daily_max": get_daily_max(default_provider, config)
    }


def get_provider_script(provider: str) -> Optional[Path]:
    """Get the execution script for a provider."""
    provider_scripts = {
        "claude": ORCHESTRATION_DIR / "providers" / "claude-code" / "spawn.sh",
        "openai": ORCHESTRATION_DIR / "providers" / "codex" / "execute.sh",
        "gemini": ORCHESTRATION_DIR / "providers" / "gemini" / "query.sh",
        "cursor": ORCHESTRATION_DIR / "providers" / "cursor" / "agent.sh",
        "opencode": ORCHESTRATION_DIR / "providers" / "opencode" / "execute.sh",
        "ollama": ORCHESTRATION_DIR / "providers" / "ollama" / "query.sh",
    }
    return provider_scripts.get(provider)


def execute_task(task: str, provider: str) -> dict:
    """Execute task using the selected provider."""
    script = get_provider_script(provider)

    if not script or not script.exists():
        return {
            "success": False,
            "error": f"Provider script not found: {script}",
            "provider": provider
        }

    try:
        result = subprocess.run(
            [str(script), task],
            capture_output=True,
            text=True,
            timeout=300
        )

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            output = {
                "success": result.returncode == 0,
                "output": result.stdout,
                "stderr": result.stderr
            }

        output["provider"] = provider
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
    import argparse

    parser = argparse.ArgumentParser(description="Route tasks to the best available AI provider")
    parser.add_argument("task", nargs="?", help="Task description")
    parser.add_argument("--agent", "--provider", dest="provider", help="Force specific provider")
    parser.add_argument("--dry-run", action="store_true", help="Only show routing decision, don't execute")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.task:
        parser.print_help()
        sys.exit(1)

    config = load_config()
    matrix = load_priority_matrix()

    routing = select_provider(args.task, config, matrix, args.provider)

    if args.dry_run:
        routing["task"] = args.task
        routing["dry_run"] = True
        print(json.dumps(routing, indent=2))
        sys.exit(0)

    if args.json:
        result = execute_task(args.task, routing["provider"])
        result["routing"] = routing
        print(json.dumps(result, indent=2))
    else:
        # Human-readable output
        print(f"Routing to: {routing['provider']} ({routing['reason']})")
        if routing.get("warning"):
            print(f"Warning: {routing.get('reason', 'Rate limits or availability issue')}")

        result = execute_task(args.task, routing["provider"])

        if result.get("success"):
            print(f"\nResult:\n{result.get('output', '')}")
        else:
            print(f"\nError: {result.get('error', 'Unknown error')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
