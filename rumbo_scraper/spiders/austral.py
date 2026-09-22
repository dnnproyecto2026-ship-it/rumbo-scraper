"""Scrape Universidad Austral from its public REST API and pages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from rumbo_scraper.parsers.austral import (
    API_URL, UNIVERSITY, build_dataset, discover_programmes, plan_document_url,
)
from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.validators.austral import validate_dataset

DEFAULT_OUTPUT = Path("data/austral_completo.json")
USER_AGENT = "RumboScraper/0.3"
PAGE_SIZE = 100


def _collection(client: httpx.Client, path: str, errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Read every page of a WordPress collection."""
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"{API_URL}/{path}?per_page={PAGE_SIZE}&page={page}"
        try:
            response = client.get(url)
            if response.status_code == 400:  # past the last page
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


def _get_bytes(client: httpx.Client, url: str, errors: list[dict[str, str]]) -> bytes:
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
                      timeout=60) as client:
        products = _collection(client, "productos-austral", errors)
        kinds = _names(_collection(client, "tipo-de-producto", errors))
        areas = _names(_collection(client, "areas-tax", errors))
        campuses = _names(_collection(client, "sedes", errors))
        programmes, excluded = discover_programmes(products, kinds, areas, campuses)
        if limit is not None:
            programmes = programmes[:limit]

        pages = {ref.url: _get(client, ref.url, errors) for ref in programmes}
        plans: dict[str, bytes] = {}
        for url, html in pages.items():
            document_url = plan_document_url(html) if html else None
            if document_url:
                plans[url] = _get_bytes(client, document_url, errors)

        people = [{
            "universidad_nombre": UNIVERSITY,
            "nombre_completo": clean_text((row.get("title") or {}).get("rendered", "")),
            "email": None, "perfil_url": row.get("link"), "foto_url": None,
            "formacion": None, "biografia": None, "fuente_url": row.get("link"),
        } for row in _collection(client, "profesores", errors)]
        authorities = [{
            "facultad_nombre": None, "carrera": None, "cargo": "Autoridad",
            "tipo": "Académico",
            "nombre_autoridad": clean_text((row.get("title") or {}).get("rendered", "")),
        } for row in _collection(client, "autoridades", errors)]

    # A person can be listed twice; the directory keeps one row each.
    unique_people: dict[str, dict[str, Any]] = {}
    for person in people:
        if person["nombre_completo"]:
            unique_people.setdefault(comparison_key(person["nombre_completo"]), person)
    unique_authorities: dict[str, dict[str, Any]] = {}
    for authority in authorities:
        if authority["nombre_autoridad"]:
            unique_authorities.setdefault(
                comparison_key(authority["nombre_autoridad"]), authority
            )

    dataset = build_dataset(
        programmes, {url: html for url, html in pages.items() if html},
        {url: data for url, data in plans.items() if data},
        list(unique_people.values()), list(unique_authorities.values()),
        tuple(sorted(campuses.values())),
        tuple(sorted({ref.area for ref in programmes if ref.area})),
        excluded, errors,
    )
    validate_dataset(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Austral con reglas determinísticas")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    dataset = run(args.output, args.limit)
    data = dataset["datos"]
    quality = dataset["control_calidad"]
    print(f"OK: {len(data['carreras'])} carreras")
    print(f"OK: {len(data['posgrados'])} posgrados")
    print(f"OK: {len(data['materias'])} materias")
    print(f"OK: {len(data['sedes'])} sedes y {len(data['facultades'])} unidades")
    print(f"OK: {len(data['autoridades'])} autoridades")
    print(f"OK: {len(dataset['directorio_academico']['personas'])} personas académicas")
    print(f"Archivo: {args.output}")
    failed = [r for r in quality["programas_excluidos"] if "descargar" in r["motivo"]]
    print(f"Fuera del contrato: {len(quality['programas_excluidos']) - len(failed)} "
          f"| no descargados: {len(failed)}")
    if quality["errores_descarga"]:
        print(f"Advertencia: {len(quality['errores_descarga'])} descargas fallidas")


if __name__ == "__main__":
    main()
