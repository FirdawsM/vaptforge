"""Validation for HTTP(S) targets accepted by the CLI and web UI."""

import re
from urllib.parse import urlsplit


_AUTHORITY = re.compile(r"[A-Za-z0-9.-]+(?::[0-9]{1,5})?")
_SAFE_PATH = re.compile(r"[A-Za-z0-9._~/%-]*")
_HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")


def is_valid_target_url(value: str) -> bool:
    """Accept a conservative, shell-safe HTTP(S) URL with no query or fragment."""
    if not isinstance(value, str) or not value:
        return False

    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False

    if parsed.scheme.lower() not in {"http", "https"}:
        return False
    if not parsed.hostname or not _AUTHORITY.fullmatch(parsed.netloc):
        return False
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    if "?" in value or "#" in value:
        return False
    if not _SAFE_PATH.fullmatch(parsed.path) or _PERCENT_ESCAPE.search(parsed.path):
        return False
    if port is not None and not 1 <= port <= 65535:
        return False

    host = parsed.hostname
    # Bracketed IPv6 URLs fail the authority allowlist; this also rejects colons in hostnames.
    if ":" in host or len(host) > 253:
        return False
    labels = host.rstrip(".").split(".")
    return bool(labels) and all(_HOST_LABEL.fullmatch(label) for label in labels)
