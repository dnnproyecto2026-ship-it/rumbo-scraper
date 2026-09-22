"""URL normalization helpers."""

from urllib.parse import urlparse, urlunparse


def normalize_supabase_url(value: str) -> str:
    """Accept either the project URL or the displayed Data API URL."""
    cleaned = value.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.path.rstrip("/") == "/rest/v1":
        return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    return cleaned


def is_official_url(value: object, domain: str, *, require_https: bool = True) -> bool:
    """Return True when the URL really belongs to the official domain.

    A substring check is not enough: it accepts both a lookalike host such as
    ``utdt.edu.example.com`` and an unrelated host carrying the domain in its
    query string. The host must be the domain itself or one of its subdomains.
    """
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value.strip())
    if require_https and parsed.scheme != "https":
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    expected = domain.lower().strip(".")
    return host == expected or host.endswith("." + expected)


def is_web_url(value: object, *, require_https: bool = True) -> bool:
    """Return True for a real web address, whatever the domain.

    Used for links the university publishes towards somewhere else: a shared
    Drive folder, an external application portal. The address still has to be
    a usable HTTPS one, so a javascript: or relative value is rejected.
    """
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value.strip())
    if parsed.scheme not in ({"https"} if require_https else {"http", "https"}):
        return False
    return bool(parsed.hostname)


def assert_official_url(value: object, domain: str, context: str, *, require_https: bool = True) -> None:
    """Raise ValueError when ``value`` is not an official URL of ``domain``."""
    if not is_official_url(value, domain, require_https=require_https):
        raise ValueError(f"{context}: URL fuera del dominio oficial {domain}: {value!r}")
