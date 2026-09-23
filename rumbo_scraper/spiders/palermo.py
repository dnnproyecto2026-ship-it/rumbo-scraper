"""Scrape the public site of the Universidad de Palermo."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import httpx

from rumbo_scraper.parsers.palermo import (
    INDEX_URLS, build_dataset, decode, discover_careers, plan_url,
)
from rumbo_scraper.validators.palermo import validate_dataset

DEFAULT_OUTPUT = Path("data/palermo_completo.json")
USER_AGENT = "RumboScraper/0.3"


def _get(client: httpx.Client, url: str, errors: list[dict[str, str]],
         attempts: int = 3) -> str:
    for attempt in range(attempts):
        try:
            response = client.get(url)
            response.raise_for_status()
            return decode(response.content, response.encoding)
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
        indexes = {url: _get(client, url, errors) for url in INDEX_URLS}
        careers = discover_careers(indexes)
        if limit is not None:
            careers = careers[:limit]
        plan_of: dict[str, str] = {}
        plan_pages: dict[str, str] = {}
        for ref in careers:
            page = _get(client, ref.url, errors)
            plan = plan_url(page, ref.url) if page else None
            if not plan:
                continue
            plan_of[ref.url] = plan
            if plan not in plan_pages:
                plan_pages[plan] = _get(client, plan, errors)

    dataset = build_dataset(
        careers, {url: html for url, html in plan_pages.items() if html},
        plan_of, errors,
    )
    validate_dataset(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrapear la Universidad de Palermo")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    dataset = run(args.output, args.limit)
    data = dataset["datos"]
    quality = dataset["control_calidad"]
    print(f"OK: {len(data['facultades'])} facultades")
    print(f"OK: {len(data['carreras'])} carreras")
    print(f"OK: {len(data['posgrados'])} posgrados")
    print(f"OK: {len(data['materias'])} materias")
    print(f"Archivo: {args.output}")
    print(f"Sin página de plan: {len(quality['carreras_excluidas'])}")


if __name__ == "__main__":
    main()
