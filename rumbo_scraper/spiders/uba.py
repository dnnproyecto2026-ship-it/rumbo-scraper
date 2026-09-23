"""Scrape the public catalogue of the Universidad de Buenos Aires."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import httpx

from rumbo_scraper.parsers.uba import (
    AUTHORITIES_URL, DOMAIN, FACULTIES_URL, POSTGRADUATE_URLS, build_dataset,
    discover_faculties, parse_careers, plan_document_url,
)
from rumbo_scraper.normalizers.url import is_official_url
from rumbo_scraper.validators.uba import validate_dataset

DEFAULT_OUTPUT = Path("data/uba_completo.json")
USER_AGENT = "RumboScraper/0.3"


def _get(client: httpx.Client, url: str, errors: list[dict[str, str]],
         attempts: int = 3) -> str:
    """Read one page, retrying a failure that a second attempt can fix.

    The careers of the UBA live on twenty-eight hosts and a run walks them one
    after another; asking that fast makes name resolution fail for a host that
    answers perfectly well on its own, so a lost page is retried before it is
    reported as missing.
    """
    for attempt in range(attempts):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            if attempt == attempts - 1:
                errors.append({"url": url, "error": str(exc)})
                return ""
            time.sleep(2 * (attempt + 1))
    return ""


def run(output: Path = DEFAULT_OUTPUT, limit: int | None = None) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                      timeout=90) as client:
        faculties = discover_faculties(_get(client, FACULTIES_URL, errors))
        if limit is not None:
            faculties = faculties[:limit]
        pages = {ref.url: _get(client, ref.url, errors) for ref in faculties}
        authorities = _get(client, AUTHORITIES_URL, errors)
        # The postgraduate offer is published by each faculty on its own site.
        programmes = {url: _get(client, url, errors) for url in POSTGRADUATE_URLS}

        # Each faculty publishes the plan of its careers on its own site, so
        # the page of every career is read and the document it links is read
        # after it.
        career_urls: list[str] = []
        for html in pages.values():
            for _, url in parse_careers(html):
                if url and is_official_url(url, DOMAIN, require_https=False) \
                        and url not in career_urls:
                    career_urls.append(url)
        career_pages = {url: _get(client, url, errors) for url in career_urls}

    dataset = build_dataset(
        faculties, {url: html for url, html in pages.items() if html},
        authorities, errors,
        {url: html for url, html in programmes.items() if html},
        {url: html for url, html in career_pages.items() if html},
    )
    validate_dataset(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrapear el catálogo público de la UBA"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    dataset = run(args.output, args.limit)
    data = dataset["datos"]
    quality = dataset["control_calidad"]
    print(f"OK: {len(data['facultades'])} facultades")
    print(f"OK: {len(data['carreras'])} carreras")
    print(f"OK: {len(data['sedes'])} sedes")
    print(f"OK: {len(data['posgrados'])} posgrados")
    print(f"OK: {len(data['autoridades'])} autoridades del Rectorado")
    print(f"OK: {len(data['redes_contacto'])} canales de contacto")
    print(f"Archivo: {args.output}")
    print(f"Carreras sin sede publicada: {quality['carreras_sin_sede_publicada']} "
          f"| facultades excluidas: {len(quality['facultades_excluidas'])}")
    linked = sum(1 for row in dataset["recursos_publicos"]
                 if row["tipo_recurso"] == "documento")
    print(f"Planes enlazados: {linked} "
          f"| carreras sin plan publicado: "
          f"{len(quality['carreras_sin_plan_publicado'])}")
    print(f"Facultades con posgrados sin leer: "
          f"{len(quality['posgrados_por_facultad_sin_leer'])} "
          f"| índices vacíos: {len(quality['indices_de_posgrado_vacios'])}")


if __name__ == "__main__":
    main()
