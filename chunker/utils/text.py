"""Text encoding/decoding utilities.

This module provides safe text decoding with proper fallback handling
for invalid byte sequences.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def safe_decode(
    data: bytes | None,
    encoding: str = "utf-8",
    errors: str = "replace",
) -> str:
    """Safely decode bytes to string with fallback handling.

    Attempts to decode bytes using the specified encoding. If decoding fails,
    uses the specified error handling strategy and logs a warning.

    Args:
        data: Bytes to decode, or None.
        encoding: Target encoding (default: utf-8).
        errors: Error handling strategy for invalid sequences.
            - 'replace': Replace invalid sequences with replacement character (default)
            - 'ignore': Skip invalid sequences
            - 'strict': Raise UnicodeDecodeError (not recommended)

    Returns:
        Decoded string, or empty string if data is None.

    Example:
        >>> text = safe_decode(node.text)
        >>> text = safe_decode(content, encoding="latin-1")
    """
    if data is None:
        return ""

    try:
        return data.decode(encoding)
    except UnicodeDecodeError:
        logger.warning(
            "Invalid %s encoding encountered; using '%s' error handling",
            encoding,
            errors,
        )
        return data.decode(encoding, errors=errors)
    except AttributeError:
        # data might already be a string
        if isinstance(data, str):
            return data
        logger.warning("Expected bytes, got %s", type(data).__name__)
        return str(data)


def safe_decode_bytes(
    data: bytes,
    errors: str = "replace",
) -> str:
    """Decode bytes to string with fallback for source[start:end] patterns.

    This is a simplified version of safe_decode() for the common pattern
    of decoding byte slices from source code. Unlike safe_decode(), this
    function assumes data is always bytes (not None).

    Args:
        data: Bytes to decode.
        errors: Error handling strategy ('replace', 'ignore', 'strict').

    Returns:
        Decoded UTF-8 string.

    Example:
        >>> name = safe_decode_bytes(source[node.start_byte:node.end_byte])
    """
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        logger.warning("Invalid UTF-8 encoding; using '%s' error handling", errors)
        return data.decode("utf-8", errors=errors)


def safe_encode(
    text: str | None,
    encoding: str = "utf-8",
    errors: str = "replace",
) -> bytes:
    """Safely encode string to bytes with fallback handling.

    Args:
        text: String to encode, or None.
        encoding: Target encoding (default: utf-8).
        errors: Error handling strategy for unencodable characters.

    Returns:
        Encoded bytes, or empty bytes if text is None.
    """
    if text is None:
        return b""

    try:
        return text.encode(encoding)
    except UnicodeEncodeError:
        logger.warning(
            "Invalid characters for %s encoding; using '%s' error handling",
            encoding,
            errors,
        )
        return text.encode(encoding, errors=errors)
    except AttributeError:
        # text might already be bytes
        if isinstance(text, bytes):
            return text
        logger.warning("Expected str, got %s", type(text).__name__)
        return str(text).encode(encoding, errors=errors)
