"""Scrape the public site of the Universidad Abierta Interamericana."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import httpx

from rumbo_scraper.parsers.uai import (
    SITEMAP_URL, build_dataset, discover_careers, parse_plan, parse_plan_reference,
    plan_detail_url, plan_index_url, read_plan_codes,
)
from rumbo_scraper.validators.uai import validate_dataset

DEFAULT_OUTPUT = Path("data/uai_completo.json")
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
        careers = discover_careers(_get(client, SITEMAP_URL, errors))
        if limit is not None:
            careers = careers[:limit]
        pages = {ref.url: _get(client, ref.url, errors) for ref in careers}

        # The plan of a career is served apart, by the code its page declares:
        # first the list of plans, then the newest of them.
        plans: dict[str, list[dict[str, Any]]] = {}
        for ref in careers:
            html = pages.get(ref.url, "")
            code = parse_plan_reference(html)["codigo"] if html else None
            if not code:
                continue
            codes = read_plan_codes(_get(client, plan_index_url(code), errors))
            if not codes:
                continue
            detail = _get(client, plan_detail_url(code, codes[0]), errors)
            subjects = parse_plan(detail, __import__(
                "rumbo_scraper.parsers.uai", fromlist=["career_name"]
            ).career_name(ref.slug)) if detail else []
            if subjects:
                plans[ref.url] = subjects

    dataset = build_dataset(
        careers, {url: html for url, html in pages.items() if html}, plans, errors,
    )
    validate_dataset(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrapear la UAI")
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
    print(f"OK: {len(data['sedes'])} sedes y {len(data['autoridades'])} autoridades")
    print(f"Archivo: {args.output}")
    print(f"Excluidas: {len(quality['carreras_excluidas'])}")


if __name__ == "__main__":
    main()
