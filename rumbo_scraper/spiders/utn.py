"""Scrape the public catalogue of the Universidad Tecnológica Nacional."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from rumbo_scraper.parsers.utn import (
    CAREER_KINDS, ZONES, build_dataset, catalogue_url, documents_url, offers_url,
    plan_document_url, read_catalogue, zone_url,
)
from rumbo_scraper.validators.utn import validate_dataset

DEFAULT_OUTPUT = Path("data/utn_completo.json")
USER_AGENT = "RumboScraper/0.3"


def _json(client: httpx.Client, url: str, errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Read one answer of the catalogue endpoint.

    An empty body is how the endpoint says "nothing here"; it is an answer,
    not a failure.
    """
    try:
        response = client.get(url)
        response.raise_for_status()
        if not response.text.strip():
            return []
        payload = response.json()
        return payload if isinstance(payload, list) else []
    except (httpx.HTTPError, ValueError) as exc:
        errors.append({"url": url, "error": str(exc)})
        return []


def _pdf(client: httpx.Client, url: str, errors: list[dict[str, str]]) -> bytes:
    try:
        response = client.get(url)
        response.raise_for_status()
        return response.content if response.content[:4] == b"%PDF" else b""
    except httpx.HTTPError as exc:
        errors.append({"url": url, "error": str(exc)})
        return b""


def run(output: Path = DEFAULT_OUTPUT, limit: int | None = None) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                      timeout=90) as client:
        catalogue = {catalogue_url(query): _json(client, catalogue_url(query), errors)
                     for query, _ in CAREER_KINDS}
        careers = read_catalogue(catalogue)
        if limit is not None:
            careers = careers[:limit]

        regionals: dict[str, dict[str, Any]] = {}
        for zone in ZONES:
            for row in _json(client, zone_url(zone), errors):
                regionals[str(row.get("id_regionales"))] = row

        offers: dict[str, list[dict[str, Any]]] = {}
        documents: dict[str, list[dict[str, Any]]] = {}
        for career in careers:
            offers[offers_url(career.id)] = _json(client, offers_url(career.id), errors)
            documents[documents_url(career.id)] = _json(
                client, documents_url(career.id), errors
            )

        plans: dict[str, bytes] = {}
        for records in documents.values():
            url = plan_document_url(records)
            if url and url not in plans:
                plans[url] = _pdf(client, url, errors)

    dataset = build_dataset(
        careers, regionals, offers, documents,
        {url: data for url, data in plans.items() if data}, errors,
    )
    validate_dataset(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrapear la oferta académica pública de la UTN"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    dataset = run(args.output, args.limit)
    data = dataset["datos"]
    quality = dataset["control_calidad"]
    print(f"OK: {len(data['carreras'])} carreras")
    print(f"OK: {len(data['posgrados'])} posgrados")
    print(f"OK: {len(data['materias'])} materias")
    print(f"OK: {len(data['sedes'])} sedes y {len(data['autoridades'])} decanatos")
    print(f"OK: {len(data['ofertas'])} ofertas por sede")
    print(f"Archivo: {args.output}")
    print(f"Planes no legibles: {len(quality['planes_no_legibles'])} "
          f"| posgrados sin tipo del contrato: "
          f"{len(quality['posgrados_sin_tipo_en_contrato'])}")


if __name__ == "__main__":
    main()
