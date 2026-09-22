"""Text normalization shared by parsers."""

import re
import unicodedata


def clean_text(value: str | None) -> str:
    """Collapse whitespace and remove invisible non-breaking spaces.

    A missing value normalizes to the empty string. Parsers read optional
    fields straight from the source documents, so raising here would only turn
    an absent label into a crash far from its cause.
    """
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def comparison_key(value: str | None) -> str:
    """Return a lowercase, accent-free key suitable for comparisons."""
    normalized = unicodedata.normalize("NFKD", clean_text(value))
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()
