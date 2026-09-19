"""URL normalization helpers."""

from urllib.parse import urlparse, urlunparse


def normalize_supabase_url(value: str) -> str:
    """Accept either the project URL or the displayed Data API URL."""
    cleaned = value.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.path.rstrip("/") == "/rest/v1":
        return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    return cleaned
