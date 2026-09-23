"""Fill the institutional columns of every university already loaded.

``universidades`` has columns no career page ever fills: the account of the
university on each social network, the mail address and the telephone it
publishes for itself. They live in the footer of the home page, which is the
one part of a site that fifteen different content managers still build the
same way, so they are read here for every university at once instead of once
per adapter.

Nothing is overwritten: a column already filled by an adapter stays as it is,
because the adapter read it from a page about that university and this reads
it from the footer of its home page.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers.perfil import NETWORKS, read_profile

USER_AGENT = "RumboScraper/0.3"
FIELDS = tuple(field for field, _ in NETWORKS) + (
    "mail_contacto", "telefono_area", "telefono_numero",
)
# The home page carries the footer; the page about the institution carries the
# contact. Both are tried and whichever states a column first fills it.
EXTRA_PATHS = ("/", "/contacto", "/institucional", "/la-universidad")


def _get(client: httpx.Client, url: str, attempts: int = 2) -> str:
    for attempt in range(attempts):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError:
            if attempt == attempts - 1:
                return ""
            time.sleep(2)
    return ""


def pages_of(client: httpx.Client, site: str) -> dict[str, str]:
    """Read the few pages of a site that carry its institutional data."""
    pages: dict[str, str] = {}
    for path in EXTRA_PATHS:
        url = urljoin(site.rstrip("/") + "/", path.lstrip("/"))
        if url in pages:
            continue
        html = _get(client, url)
        if html:
            pages[url] = html
    return pages


def rendered_page(url: str) -> str:
    """Fetch a page with a browser, for the sites that need one.

    Two of the fifteen do: one answers a plain request with a 403 and the
    other builds its footer after the page loads. Both publish the same
    footer as the rest once it is there to read.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ""
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch()
            page = browser.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
                return page.content()
            finally:
                page.close()
                browser.close()
    except Exception:
        return ""


def read_all(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Read the profile of every university, keyed by its name."""
    profiles: dict[str, dict[str, Any]] = {}
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                      timeout=45) as client:
        for row in rows:
            site = clean_text(row.get("sitio_web"))
            if not site:
                continue
            domain = (urlparse(site).netloc or "").lower().lstrip("www.")
            pages = pages_of(client, site)
            profile = read_profile(pages, domain)
            if not any(field in profile for field, _ in NETWORKS):
                # Nothing of the footer came back: the site either refused the
                # request or had not built it yet.
                rendered = rendered_page(site)
                if rendered:
                    profile = read_profile({site: rendered}, domain)
            # Only the columns this reader is responsible for, and only the
            # ones the university has not already filled.
            profiles[row["nombre_oficial"]] = {
                field: value for field, value in profile.items()
                if field in FIELDS and not row.get(field)
            }
    return profiles


def apply_profiles(rows: list[dict[str, Any]], profiles: dict[str, dict[str, Any]],
                   client: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        values = profiles.get(row["nombre_oficial"]) or {}
        if not values:
            continue
        client.table("universidades").update(values).eq("id", row["id"]).execute()
        counts[row["nombre_oficial"]] = len(values)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Completar los datos institucionales de cada universidad"
    )
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    parser.add_argument("--output", type=Path, default=Path("data/perfiles.json"))
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    client = get_supabase_client()
    rows = select_all(client.table("universidades").select("*"))
    profiles = read_all(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")

    if args.apply:
        counts = apply_profiles(rows, profiles, client)
        print("CARGADO")
    else:
        counts = {name: len(values) for name, values in profiles.items() if values}
        print("LEÍDO (sin escribir)")
    for name in sorted(counts):
        print(f"- {name}: {counts[name]} campos")
    print(f"Archivo: {args.output}")


if __name__ == "__main__":
    main()
