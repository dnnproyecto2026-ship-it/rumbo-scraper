"""Validation rules for scraped records."""

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.normalizers.url import (
    assert_official_url, is_official_url, is_web_url,
)

# Two kinds of URL live in the contract and they do not carry the same promise.
# An evidence field states where a fact was read, so it must be a page of the
# university itself. A destination field is a link the university publishes and
# may legitimately leave its own domain -- a shared Drive folder, an external
# application portal -- so it only has to be a real HTTPS address.
EVIDENCE_FIELDS = ("fuente_url", "url_oficial")

URL_FIELDS: dict[str, tuple[str, ...]] = {
    section: tuple(field for field in fields if "url" in field)
    for section, fields in SECTION_FIELDS.items()
    if any("url" in field for field in fields)
}


def validate_contract_urls(sections: dict[str, list[dict[str, object]]], domain: str,
                           *, require_https: bool = True) -> None:
    """Check every published URL of the contract.

    An empty value means the source did not publish it and stays valid.

    ``require_https`` is relaxed for the universities read in general, where a
    good number still publish their own catalogue over plain http. That the
    address is not encrypted is a fact about the university's site, not a
    reason to refuse the career it points at.
    """
    for section, fields in URL_FIELDS.items():
        for index, row in enumerate(sections.get(section, [])):
            for field in fields:
                value = row.get(field)
                if value in (None, ""):
                    continue
                context = f"{section}[{index}].{field}"
                if field in EVIDENCE_FIELDS:
                    assert_official_url(value, domain, context,
                                        require_https=require_https)
                elif not is_web_url(value, require_https=require_https):
                    raise ValueError(f"{context}: URL inválida: {value!r}")


def external_destinations(
    sections: dict[str, list[dict[str, object]]], domain: str
) -> list[dict[str, str]]:
    """List the published links that leave the university's own domain."""
    found: list[dict[str, str]] = []
    for section, fields in URL_FIELDS.items():
        for row in sections.get(section, []):
            for field in fields:
                value = row.get(field)
                if value in (None, "") or field in EVIDENCE_FIELDS:
                    continue
                if not is_official_url(value, domain):
                    found.append({"seccion": section, "campo": field, "url": str(value)})
    return found
