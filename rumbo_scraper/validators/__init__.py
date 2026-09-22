"""Validation rules for scraped records."""

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.normalizers.url import assert_official_url

URL_FIELDS: dict[str, tuple[str, ...]] = {
    section: tuple(field for field in fields if "url" in field)
    for section, fields in SECTION_FIELDS.items()
    if any("url" in field for field in fields)
}


def validate_contract_urls(sections: dict[str, list[dict[str, object]]], domain: str) -> None:
    """Every published URL of the contract must point to the official domain.

    An empty value means the source did not publish it and stays valid; a URL
    that exists must be verifiable, because it becomes the evidence a student
    ends up following.
    """
    for section, fields in URL_FIELDS.items():
        for index, row in enumerate(sections.get(section, [])):
            for field in fields:
                value = row.get(field)
                if value in (None, ""):
                    continue
                assert_official_url(value, domain, f"{section}[{index}].{field}")
