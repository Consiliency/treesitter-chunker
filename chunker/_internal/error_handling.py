"""Error handling utilities for consistent user guidance and error formatting."""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


def format_grammar_error(language: str, error_type: str, details: Dict[str, Any]) -> str:
    """Format grammar-related errors with consistent user guidance.
    
    Args:
        language: The language that caused the error
        error_type: Type of error (missing, load_failed, parse_failed, etc.)
        details: Additional error details
        
    Returns:
        Formatted error message with user guidance
    """
    base_message = f"Grammar error for {language}: {error_type}"
    
    # Add specific guidance based on error type
    if error_type == "missing":
        guidance = _get_missing_grammar_guidance(language, details)
    elif error_type == "load_failed":
        guidance = _get_load_failed_guidance(language, details)
    elif error_type == "parse_failed":
        guidance = _get_parse_failed_guidance(language, details)
    elif error_type == "version_incompatible":
        guidance = _get_version_incompatible_guidance(language, details)
    else:
        guidance = _get_general_guidance(language, details)
    
    return f"{base_message}\n\n{guidance}"


def _get_missing_grammar_guidance(language: str, details: Dict[str, Any]) -> str:
    """Get guidance for missing grammar errors."""
    guidance_parts = [
        "🔧 This grammar is not available:",
        f"   1. Check if {language} grammar source exists in grammars/ directory",
        "   2. Compile the grammar to a .so library",
        "   3. Place the .so file in chunker/data/grammars/build/",
        "",
        "💡 Quick fix:",
        f"   - Clone tree-sitter-{language} repository to grammars/",
        f"   - Run: tree-sitter generate --path grammars/tree-sitter-{language}",
        f"   - Copy the generated .so file to chunker/data/grammars/build/"
    ]
    
    if details.get("available_languages"):
        available = details["available_languages"]
        guidance_parts.extend([
            "",
            f"📋 Currently available languages: {', '.join(sorted(available))}"
        ])
    
    return "\n".join(guidance_parts)


def _get_load_failed_guidance(language: str, details: Dict[str, Any]) -> str:
    """Get guidance for grammar loading failures."""
    reason = details.get("reason", "unknown error")
    
    guidance_parts = [
        "🔧 Failed to load grammar library:",
        f"   Reason: {reason}",
        "",
        "💡 Troubleshooting steps:",
        "   1. Check if the .so file is corrupted or incomplete",
        "   2. Verify the grammar is compatible with your system",
        "   3. Try recompiling the grammar from source",
        "   4. Check file permissions and system compatibility"
    ]
    
    if "symbol" in reason.lower():
        guidance_parts.extend([
            "",
            "🔍 This appears to be a symbol/library issue:",
            "   - The grammar may be compiled for a different architecture",
            "   - Try recompiling on your current system",
            "   - Check if the grammar supports your OS/architecture"
        ])
    
    return "\n".join(guidance_parts)


def _get_parse_failed_guidance(language: str, details: Dict[str, Any]) -> str:
    """Get guidance for parsing failures."""
    reason = details.get("reason", "unknown error")
    
    guidance_parts = [
        "🔧 Failed to parse code with grammar:",
        f"   Reason: {reason}",
        "",
        "💡 This usually indicates:",
        "   1. Your code uses syntax not supported by the grammar",
        "   2. The grammar is outdated for your language version",
        "   3. The grammar doesn't support certain language features",
        "",
        "🛠️ Solutions:",
        "   1. Update the grammar to a newer version",
        "   2. Use alternative syntax that's more widely supported",
        "   3. Check if there are grammar forks with better support",
        "   4. Report the issue to grammar maintainers"
    ]
    
    return "\n".join(guidance_parts)


def _get_version_incompatible_guidance(language: str, details: Dict[str, Any]) -> str:
    """Get guidance for version compatibility issues."""
    current_version = details.get("current_version", "unknown")
    required_version = details.get("required_version", "unknown")
    
    guidance_parts = [
        "🔧 Version compatibility issue:",
        f"   Current grammar version: {current_version}",
        f"   Required version: {required_version}",
        "",
        "💡 This indicates:",
        "   1. Your code uses features from a newer language version",
        "   2. The grammar doesn't support your target language version",
        "   3. There may be breaking changes between versions",
        "",
        "🛠️ Solutions:",
        "   1. Update the grammar to support your language version",
        "   2. Use language features compatible with the grammar version",
        "   3. Check if there are grammar updates available",
        "   4. Consider using an older language version for compatibility"
    ]
    
    return "\n".join(guidance_parts)


def _get_general_guidance(language: str, details: Dict[str, Any]) -> str:
    """Get general guidance for unknown error types."""
    return "\n".join([
        "🔧 General grammar issue encountered:",
        f"   Language: {language}",
        f"   Details: {details}",
        "",
        "💡 General troubleshooting:",
        "   1. Check if the grammar source is up to date",
        "   2. Verify the grammar compiles successfully",
        "   3. Check system compatibility and dependencies",
        "   4. Review grammar documentation and issues",
        "   5. Consider using an alternative grammar if available"
    ])


def log_grammar_discovery_summary(discovered_languages: list[str], 
                                total_expected: int = 30) -> None:
    """Log a summary of grammar discovery results with user guidance.
    
    Args:
        discovered_languages: List of successfully discovered languages
        total_expected: Total number of languages expected to be available
    """
    discovered_count = len(discovered_languages)
    
    if discovered_count == 0:
        logger.warning(
            "❌ No language grammars discovered!",
            extra={
                "discovered": 0,
                "expected": total_expected,
                "status": "critical"
            }
        )
        logger.warning(
            "This indicates a critical issue with grammar compilation or discovery."
        )
    elif discovered_count < total_expected * 0.5:
        logger.warning(
            "⚠️  Only %d/%d language grammars discovered",
            discovered_count, total_expected,
            extra={
                "discovered": discovered_count,
                "expected": total_expected,
                "status": "warning"
            }
        )
        logger.warning(
            "Many expected languages are missing. Check grammar compilation process."
        )
    elif discovered_count < total_expected:
        logger.info(
            "ℹ️  %d/%d language grammars discovered",
            discovered_count, total_expected,
            extra={
                "discovered": discovered_count,
                "expected": total_expected,
                "status": "info"
            }
        )
        logger.info(
            "Some languages are missing but core functionality should work."
        )
    else:
        logger.info(
            "✅ All %d language grammars discovered successfully!",
            discovered_count,
            extra={
                "discovered": discovered_count,
                "expected": total_expected,
                "status": "success"
            }
        )
    
    # Always log the discovered languages for debugging
    if discovered_languages:
        logger.info("Available languages: %s", ", ".join(sorted(discovered_languages)))
    else:
        logger.error("No languages available - system will not function properly")
