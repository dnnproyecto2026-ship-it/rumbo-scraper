"""Scrape Universidad de Belgrano public pages and plan documents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from rumbo_scraper.parsers.ub import (
    INDEX_URLS, build_dataset, discover_programmes, plan_document_url,
)
from rumbo_scraper.validators.ub import validate_dataset

DEFAULT_OUTPUT = Path("data/ub_completo.json")
USER_AGENT = "RumboScraper/0.3"


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


def _links(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return [
        (anchor["href"], " ".join(anchor.get_text(" ", strip=True).split()))
        for anchor in soup.find_all("a", href=True)
    ]


def run(output: Path = DEFAULT_OUTPUT, limit: int | None = None) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                      timeout=60) as client:
        indexes = {url: _links(_get(client, url, errors)) for url in INDEX_URLS}
        programmes = discover_programmes(indexes)
        if limit is not None:
            programmes = programmes[:limit]
        pages = {ref.url: _get(client, ref.url, errors) for ref in programmes}
        documents: dict[str, bytes] = {}
        for html in pages.values():
            url = plan_document_url(html) if html else None
            if url and url not in documents:
                documents[url] = _get_bytes(client, url, errors)

    dataset = build_dataset(
        programmes, {url: html for url, html in pages.items() if html},
        {url: data for url, data in documents.items() if data}, errors,
    )
    validate_dataset(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Universidad de Belgrano con reglas determinísticas"
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
    print(f"OK: {len(data['facultades'])} facultades")
    print(f"Archivo: {args.output}")
    without_sheet = [r for r in quality["programas_excluidos"] if "datos" in r["motivo"]]
    print(f"Sin datos publicados: {len(without_sheet)} "
          f"| otros excluidos: {len(quality['programas_excluidos']) - len(without_sheet)}")


if __name__ == "__main__":
    main()
