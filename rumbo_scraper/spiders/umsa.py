"""Scrape UMSA from its public REST API and pages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers.umsa import (
    API_URL, build_dataset, discover_programmes,
)
from rumbo_scraper.validators.umsa import validate_dataset

DEFAULT_OUTPUT = Path("data/umsa_completo.json")
USER_AGENT = "RumboScraper/0.3"
PAGE_SIZE = 100


def _collection(client: httpx.Client, path: str,
                errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"{API_URL}/{path}?per_page={PAGE_SIZE}&page={page}"
        try:
            response = client.get(url)
            if response.status_code == 400:
                return rows
            response.raise_for_status()
        except httpx.HTTPError as exc:
            errors.append({"url": url, "error": str(exc)})
            return rows
        batch = response.json()
        if not isinstance(batch, list) or not batch:
            return rows
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        page += 1


def _names(rows: list[dict[str, Any]]) -> dict[int, str]:
    return {row["id"]: clean_text(row.get("name") or "") for row in rows}


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
                      timeout=60) as client:
        careers = _collection(client, "carrera", errors)
        offers = _collection(client, "oferta", errors)
        titles = _names(_collection(client, "tipo-de-titulo", errors))
        postgraduate_kinds = _names(_collection(client, "tipo-de-posgrado", errors))
        faculties = _names(_collection(client, "facultad", errors))
        offer_kinds = _names(_collection(client, "tipo-de-oferta", errors))
        programmes, excluded = discover_programmes(
            careers, offers, titles, postgraduate_kinds, faculties, offer_kinds
        )
        if limit is not None:
            programmes = programmes[:limit]
        pages = {ref.url: _get(client, ref.url, errors) for ref in programmes}

    dataset = build_dataset(
        programmes, {url: html for url, html in pages.items() if html},
        tuple(sorted(faculties.values())), excluded, errors,
    )
    validate_dataset(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape UMSA con reglas determinísticas")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    dataset = run(args.output, args.limit)
    data = dataset["datos"]
    quality = dataset["control_calidad"]
    print(f"OK: {len(data['carreras'])} carreras")
    print(f"OK: {len(data['posgrados'])} posgrados")
    print(f"OK: {len(data['materias'])} materias")
    print(f"OK: {len(data['facultades'])} facultades")
    print(f"Archivo: {args.output}")
    failed = [r for r in quality["programas_excluidos"] if "descargar" in r["motivo"]]
    print(f"Fuera del contrato: {len(quality['programas_excluidos']) - len(failed)} "
          f"| no descargados: {len(failed)}")


if __name__ == "__main__":
    main()
