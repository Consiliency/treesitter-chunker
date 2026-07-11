"""Validation for grammar source repositories."""

from collections.abc import Collection
from urllib.parse import urlsplit


DEFAULT_GRAMMAR_SOURCE_HOSTS = frozenset({"github.com"})


def validate_grammar_source(
    url: str,
    *,
    allow_hosts: Collection[str] = DEFAULT_GRAMMAR_SOURCE_HOSTS,
) -> str:
    """Return a trusted grammar repository URL or raise ``ValueError``.

    Git treats several non-URL strings as transport helpers, so validation must
    happen before constructing a clone command.
    """
    if not isinstance(url, str) or not url or url.startswith("-"):
        raise ValueError("Grammar source must be a non-option HTTPS URL")
    if url.startswith(("ext::", "file::")):
        raise ValueError("Grammar source transport is not allowed")

    parsed = urlsplit(url)
    allowed = {host.lower() for host in allow_hosts}
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() not in allowed
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
    ):
        raise ValueError("Grammar source must use an allowed HTTPS host")
    return url
