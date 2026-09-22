"""Scrape the public catalogue of the Universidad de Buenos Aires."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from rumbo_scraper.parsers.uba import (
    AUTHORITIES_URL, FACULTIES_URL, build_dataset, discover_faculties,
)
from rumbo_scraper.validators.uba import validate_dataset

DEFAULT_OUTPUT = Path("data/uba_completo.json")
USER_AGENT = "RumboScraper/0.3"


def _get(client: httpx.Client, url: str, errors: list[dict[str, str]]) -> str:
    try:
        response = client.get(url)
        response.raise_for_status()
        return response.text
    except httpx.HTTPError as exc:
        errors.append({"url": url, "error": str(exc)})
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

    dataset = build_dataset(
        faculties, {url: html for url, html in pages.items() if html},
        authorities, errors,
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
    print(f"OK: {len(data['autoridades'])} autoridades del Rectorado")
    print(f"OK: {len(data['redes_contacto'])} canales de contacto")
    print(f"Archivo: {args.output}")
    print(f"Carreras sin sede publicada: {quality['carreras_sin_sede_publicada']} "
          f"| facultades excluidas: {len(quality['facultades_excluidas'])}")


if __name__ == "__main__":
    main()
