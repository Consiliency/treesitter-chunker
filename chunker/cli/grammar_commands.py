"""CLI commands for grammar management."""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from chunker._internal.user_grammar_tools import UserGrammarTools


def setup_grammar_parser(subparsers: argparse._SubParsersAction) -> None:
    """Set up grammar management subcommands.

    Args:
        subparsers: Subparser action from main argument parser
    """
    grammar_parser = subparsers.add_parser(
        "grammar",
        help="Manage tree-sitter grammar libraries",
    )

    grammar_subparsers = grammar_parser.add_subparsers(
        dest="grammar_command",
        help="Grammar management commands",
    )

    # List command
    list_parser = grammar_subparsers.add_parser(
        "list",
        help="List all installed grammars with their status",
    )
    list_parser.set_defaults(func=cmd_list_grammars)

    # Info command
    info_parser = grammar_subparsers.add_parser(
        "info",
        help="Get detailed information about a specific grammar",
    )
    info_parser.add_argument("language", help="Language name to get information about")
    info_parser.set_defaults(func=cmd_grammar_info)

    # Install command
    install_parser = grammar_subparsers.add_parser(
        "install",
        help="Install a grammar from a repository",
    )
    install_parser.add_argument("language", help="Language name to install")
    install_parser.add_argument("repo_url", help="Git repository URL for the grammar")
    install_parser.add_argument(
        "--branch",
        default="main",
        help="Branch to checkout (default: main)",
    )
    install_parser.set_defaults(func=cmd_install_grammar)

    # Update command
    update_parser = grammar_subparsers.add_parser(
        "update",
        help="Update a grammar to the latest version",
    )
    update_parser.add_argument("language", help="Language name to update")
    update_parser.set_defaults(func=cmd_update_grammar)

    # Remove command
    remove_parser = grammar_subparsers.add_parser(
        "remove",
        help="Remove a grammar and its source",
    )
    remove_parser.add_argument("language", help="Language name to remove")
    remove_parser.set_defaults(func=cmd_remove_grammar)

    # Diagnose command
    diagnose_parser = grammar_subparsers.add_parser(
        "diagnose",
        help="Diagnose issues with a specific grammar",
    )
    diagnose_parser.add_argument("language", help="Language name to diagnose")
    diagnose_parser.set_defaults(func=cmd_diagnose_grammar)

    # Health command
    health_parser = grammar_subparsers.add_parser(
        "health",
        help="Check overall system health for grammar management",
    )
    health_parser.set_defaults(func=cmd_system_health)

    # Validate command
    validate_parser = grammar_subparsers.add_parser(
        "validate",
        help="Validate all installed grammars",
    )
    validate_parser.set_defaults(func=cmd_validate_all)


def get_grammar_tools() -> UserGrammarTools:
    """Get grammar tools instance with default paths.

    Returns:
        UserGrammarTools instance
    """
    # Default paths relative to project root
    project_root = Path(__file__).parent.parent.parent
    build_dir = project_root / "chunker" / "data" / "grammars" / "build"
    grammars_dir = project_root / "grammars"

    return UserGrammarTools(build_dir, grammars_dir)


def cmd_list_grammars(args: argparse.Namespace) -> int:
    """List all installed grammars.

    Args:
        args: Command line arguments

    Returns:
        Exit code
    """
    try:
        tools = get_grammar_tools()
        result = tools.list_installed_grammars()

        print("\n📋 Grammar Status Summary:")
        print(f"   Total grammars: {result['total_grammars']}")
        print(f"   Healthy: {result['healthy_grammars']}")
        print(f"   Problematic: {result['problematic_grammars']}")

        if result["grammars"]:
            print("\n🔍 Individual Grammar Status:")
            for language, info in result["grammars"].items():
                status_emoji = {
                    "healthy": "✅",
                    "corrupted": "❌",
                    "missing": "⚠️",
                    "incompatible": "⚠️",
                    "unknown": "❓",
                }.get(info["status"], "❓")

                print(f"   {status_emoji} {language}: {info['status']}")
                if info["issues"]:
                    for issue in info["issues"]:
                        print(f"      - {issue}")
                if info["recommendations"]:
                    for rec in info["recommendations"]:
                        print(f"      💡 {rec}")
                print()
        else:
            print("\n❌ No grammars found. Use 'grammar install' to add grammars.")

        return 0

    except Exception as e:
        print(f"❌ Error listing grammars: {e}", file=sys.stderr)
        return 1


def cmd_grammar_info(args: argparse.Namespace) -> int:
    """Get detailed information about a specific grammar.

    Args:
        args: Command line arguments

    Returns:
        Exit code
    """
    try:
        tools = get_grammar_tools()
        result = tools.get_grammar_info(args.language)

        print(f"\n📊 Grammar Information: {args.language}")
        print("=" * 50)

        # Health status
        health = result["health"]
        status_emoji = {
            "healthy": "✅",
            "corrupted": "❌",
            "missing": "⚠️",
            "incompatible": "⚠️",
            "unknown": "❓",
        }.get(health.status, "❓")

        print(f"Status: {status_emoji} {health.status}")

        if health.issues:
            print("\n❌ Issues:")
            for issue in health.issues:
                print(f"   - {issue}")

        if health.recommendations:
            print("\n💡 Recommendations:")
            for rec in health.recommendations:
                print(f"   - {rec}")

        # Compatibility info
        compat = result["compatibility"]
        print("\n🔧 Compatibility:")
        print(f"   Tree-sitter version: {compat.tree_sitter_version}")
        print(f"   System architecture: {compat.system_architecture}")
        print(f"   OS platform: {compat.os_platform}")
        print(f"   Compilation date: {compat.compilation_date or 'unknown'}")
        print(f"   Compatibility score: {compat.compatibility_score:.1%}")

        # Source info
        if result["source_info"]:
            source = result["source_info"]
            if "error" not in source:
                print("\n📁 Source Repository:")
                print(f"   URL: {source['repository_url']}")
                print(f"   Latest commit: {source['latest_commit']}")
                print(f"   Directory: {source['source_directory']}")
                print(f"   Has package.json: {source['has_package_json']}")
                print(f"   Has grammar.js: {source['has_grammar_js']}")

        # Recovery plan if needed
        if result["recovery_plan"]:
            plan = result["recovery_plan"]
            print("\n🛠️ Recovery Plan:")
            print(f"   Difficulty: {plan['difficulty']}")
            print(f"   Estimated time: {plan['estimated_time']}")
            print("   Steps:")
            for i, step in enumerate(plan["recovery_steps"], 1):
                print(f"      {i}. {step}")

        return 0

    except Exception as e:
        print(f"❌ Error getting grammar info: {e}", file=sys.stderr)
        return 1


def cmd_install_grammar(args: argparse.Namespace) -> int:
    """Install a grammar from a repository.

    Args:
        args: Command line arguments

    Returns:
        Exit code
    """
    try:
        print(f"🚀 Installing grammar for {args.language}...")
        print(f"   Repository: {args.repo_url}")
        print(f"   Branch: {args.branch}")

        tools = get_grammar_tools()
        result = tools.install_grammar(args.language, args.repo_url, args.branch)

        print("\n📋 Installation Result:")
        print(f"   Status: {result['status']}")

        if result["steps_completed"]:
            print("\n✅ Steps completed:")
            for step in result["steps_completed"]:
                print(f"   - {step}")

        if result["warnings"]:
            print("\n⚠️ Warnings:")
            for warning in result["warnings"]:
                print(f"   - {warning}")

        if result["errors"]:
            print("\n❌ Errors:")
            for error in result["errors"]:
                print(f"   - {error}")
            return 1

        if result["status"] == "success":
            print(f"\n🎉 Successfully installed {args.language} grammar!")
        else:
            print("\n⚠️ Installation completed with warnings.")

        return 0

    except Exception as e:
        print(f"❌ Error installing grammar: {e}", file=sys.stderr)
        return 1


def cmd_update_grammar(args: argparse.Namespace) -> int:
    """Update a grammar to the latest version.

    Args:
        args: Command line arguments

    Returns:
        Exit code
    """
    try:
        print(f"🔄 Updating grammar for {args.language}...")

        tools = get_grammar_tools()
        result = tools.update_grammar(args.language)

        print("\n📋 Update Result:")
        print(f"   Status: {result['status']}")

        if result["steps_completed"]:
            print("\n✅ Steps completed:")
            for step in result["steps_completed"]:
                print(f"   - {step}")

        if result["warnings"]:
            print("\n⚠️ Warnings:")
            for warning in result["warnings"]:
                print(f"   - {warning}")

        if result["errors"]:
            print("\n❌ Errors:")
            for error in result["errors"]:
                print(f"   - {error}")
            return 1

        if result["status"] == "success":
            print(f"\n🎉 Successfully updated {args.language} grammar!")
        else:
            print("\n⚠️ Update completed with warnings.")

        return 0

    except Exception as e:
        print(f"❌ Error updating grammar: {e}", file=sys.stderr)
        return 1


def cmd_remove_grammar(args: argparse.Namespace) -> int:
    """Remove a grammar and its source.

    Args:
        args: Command line arguments

    Returns:
        Exit code
    """
    try:
        print(f"🗑️ Removing grammar for {args.language}...")

        # Confirm removal
        confirm = input(f"Are you sure you want to remove {args.language}? (y/N): ")
        if confirm.lower() != "y":
            print("Removal cancelled.")
            return 0

        tools = get_grammar_tools()
        result = tools.remove_grammar(args.language)

        print("\n📋 Removal Result:")
        print(f"   Status: {result['status']}")

        if result["steps_completed"]:
            print("\n✅ Steps completed:")
            for step in result["steps_completed"]:
                print(f"   - {step}")

        if result["warnings"]:
            print("\n⚠️ Warnings:")
            for warning in result["warnings"]:
                print(f"   - {warning}")

        if result["errors"]:
            print("\n❌ Errors:")
            for error in result["errors"]:
                print(f"   - {error}")
            return 1

        if result["status"] == "success":
            print(f"\n🎉 Successfully removed {args.language} grammar!")

        return 0

    except Exception as e:
        print(f"❌ Error removing grammar: {e}", file=sys.stderr)
        return 1


def cmd_diagnose_grammar(args: argparse.Namespace) -> int:
    """Diagnose issues with a specific grammar.

    Args:
        args: Command line arguments

    Returns:
        Exit code
    """
    try:
        print(f"🔍 Diagnosing grammar for {args.language}...")

        tools = get_grammar_tools()
        result = tools.get_grammar_info(args.language)

        # This is similar to grammar info but focused on issues
        return cmd_grammar_info(args)

    except Exception as e:
        print(f"❌ Error diagnosing grammar: {e}", file=sys.stderr)
        return 1


def cmd_system_health(args: argparse.Namespace) -> int:
    """Check overall system health for grammar management.

    Args:
        args: Command line arguments

    Returns:
        Exit code
    """
    try:
        print("🏥 Checking system health for grammar management...")

        tools = get_grammar_tools()
        result = tools.check_system_health()

        print("\n📋 System Health Report:")
        print("=" * 50)

        # System requirements
        requirements = result["system_requirements"]
        print("\n🔧 System Requirements:")
        for req, available in requirements.items():
            status_emoji = "✅" if available else "❌"
            req_name = req.replace("_", " ").title()
            print(
                f"   {status_emoji} {req_name}: {'Available' if available else 'Missing'}",
            )

        # Directory permissions
        permissions = result["directory_permissions"]
        print("\n📁 Directory Permissions:")
        for dir_name, perm_info in permissions.items():
            if "error" in perm_info:
                print(f"   ❌ {dir_name}: Error - {perm_info['error']}")
            elif perm_info["exists"]:
                status = []
                if perm_info["readable"]:
                    status.append("readable")
                if perm_info["writable"]:
                    status.append("writable")
                if perm_info["executable"]:
                    status.append("executable")
                status_emoji = "✅" if len(status) == 3 else "⚠️"
                print(f"   {status_emoji} {dir_name}: {', '.join(status)}")
            else:
                print(f"   ❌ {dir_name}: Does not exist")

        # Recommendations
        if result["recommendations"]:
            print("\n💡 Recommendations:")
            for rec in result["recommendations"]:
                print(f"   - {rec}")

        # Overall health score
        available_reqs = sum(requirements.values())
        total_reqs = len(requirements)
        health_score = available_reqs / total_reqs if total_reqs > 0 else 0

        print(f"\n📊 Overall Health Score: {health_score:.1%}")
        if health_score == 1.0:
            print("🎉 System is fully ready for grammar management!")
        elif health_score >= 0.8:
            print("✅ System is mostly ready for grammar management.")
        elif health_score >= 0.6:
            print("⚠️ System has some issues but may work for basic operations.")
        else:
            print("❌ System has significant issues that need to be resolved.")

        return 0

    except Exception as e:
        print(f"❌ Error checking system health: {e}", file=sys.stderr)
        return 1


def cmd_validate_all(args: argparse.Namespace) -> int:
    """Validate all installed grammars.

    Args:
        args: Command line arguments

    Returns:
        Exit code
    """
    try:
        print("🔍 Validating all installed grammars...")

        tools = get_grammar_tools()
        result = tools.list_installed_grammars()

        print("\n📋 Validation Results:")
        print(f"   Total grammars: {result['total_grammars']}")
        print(f"   Healthy: {result['healthy_grammars']}")
        print(f"   Problematic: {result['problematic_grammars']}")

        if result["problematic_grammars"] > 0:
            print("\n⚠️ Problematic Grammars:")
            for language, info in result["grammars"].items():
                if info["status"] != "healthy":
                    print(f"   - {language}: {info['status']}")
                    for issue in info["issues"]:
                        print(f"     Issue: {issue}")
                    for rec in info["recommendations"]:
                        print(f"     Recommendation: {rec}")
            return 1
        print("\n🎉 All grammars are healthy!")
        return 0

    except Exception as e:
        print(f"❌ Error validating grammars: {e}", file=sys.stderr)
        return 1
