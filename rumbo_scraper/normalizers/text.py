"""Text normalization shared by parsers."""

import re
import unicodedata


def clean_text(value: str) -> str:
    """Collapse whitespace and remove invisible non-breaking spaces."""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def comparison_key(value: str) -> str:
    """Return a lowercase, accent-free key suitable for comparisons."""
    normalized = unicodedata.normalize("NFKD", clean_text(value))
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()
