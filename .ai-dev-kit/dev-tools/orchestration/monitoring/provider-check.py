#!/usr/bin/env python3
"""
Provider availability checks for orchestration.

Usage:
  ./provider-check.py [--json] [--apply] [--all]
"""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR.parent / "config.json"

DEFAULT_PROVIDERS = ["opencode", "ollama"]


def command_available(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def ollama_available() -> bool:
    if not command_available("ollama"):
        return False
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=3)
        return result.returncode == 0
    except Exception:
        return False


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(config: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check provider availability")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--apply", action="store_true", help="Update config enabled flags")
    parser.add_argument("--all", action="store_true", help="Apply updates to all providers")
    args = parser.parse_args()

    config = load_config()
    providers = config.get("providers", {})

    checks = {}
    for provider, info in providers.items():
        cmd = info.get("cli_command")
        available = False

        if provider == "ollama":
            available = ollama_available()
        elif cmd:
            available = command_available(cmd)

        checks[provider] = {
            "command": cmd,
            "available": available,
            "enabled": info.get("enabled", False),
        }

    if args.apply:
        apply_targets = list(checks.keys()) if args.all else DEFAULT_PROVIDERS
        for provider in apply_targets:
            if provider in providers:
                providers[provider]["enabled"] = checks[provider]["available"]

        config["providers"] = providers
        save_config(config)

    if args.json:
        print(json.dumps({"providers": checks, "applied": args.apply, "all": args.all}, indent=2))
        return

    for provider, info in checks.items():
        status = "available" if info["available"] else "missing"
        enabled = "enabled" if info["enabled"] else "disabled"
        print(f"{provider}: {status}, {enabled}")

    if args.apply:
        scope = "all providers" if args.all else ", ".join(DEFAULT_PROVIDERS)
        print(f"Updated enabled flags for: {scope}")


if __name__ == "__main__":
    main()
