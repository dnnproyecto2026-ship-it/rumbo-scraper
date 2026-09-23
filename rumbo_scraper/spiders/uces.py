"""Scrape the public site of UCES."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import httpx

from rumbo_scraper.parsers.uces import (
    CAREERS_URL, build_dataset, discover_careers, read_faculties,
)
from rumbo_scraper.validators.uces import validate_dataset

DEFAULT_OUTPUT = Path("data/uces_completo.json")
USER_AGENT = "RumboScraper/0.3"


def _get(client: httpx.Client, url: str, errors: list[dict[str, str]],
         attempts: int = 3) -> str:
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
                      timeout=60) as client:
        index = _get(client, CAREERS_URL, errors)
        careers = discover_careers(index)
        faculties = read_faculties(index)
        if limit is not None:
            careers = careers[:limit]
        pages = {ref.url: _get(client, ref.url, errors) for ref in careers}

    dataset = build_dataset(careers, {u: h for u, h in pages.items() if h},
                            faculties, errors)
    validate_dataset(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrapear UCES")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    dataset = run(args.output, args.limit)
    data = dataset["datos"]
    quality = dataset["control_calidad"]
    print(f"OK: {len(data['facultades'])} facultades")
    print(f"OK: {len(data['carreras'])} carreras")
    print(f"OK: {len(data['materias'])} materias")
    print(f"Archivo: {args.output}")
    print(f"Excluidas: {len(quality['carreras_excluidas'])}")


if __name__ == "__main__":
    main()
