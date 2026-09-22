"""Scrape UADE public pages, enumerated by its sitemap."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from rumbo_scraper.parsers.uade import (
    BASE_URL, PLAN_SUFFIX, SITEMAP_URL, _PROGRAMME_PATH, build_dataset,
    discover_programmes, page_title, sitemap_paths,
)
from rumbo_scraper.validators.uade import validate_dataset

DEFAULT_OUTPUT = Path("data/uade_completo.json")
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
                      timeout=60) as client:
        paths = sitemap_paths(_get(client, SITEMAP_URL, errors))
        known = set(paths)
        candidates = [
            path for path in paths
            if _PROGRAMME_PATH.match(path) and path + PLAN_SUFFIX in known
        ]
        if limit is not None:
            candidates = candidates[:limit]
        # The name of a programme is the heading of its own page.
        pages = {path: _get(client, f"{BASE_URL}{path}", errors) for path in candidates}
        titles = {
            path: title for path, html in pages.items()
            if html and (title := page_title(html))
        }
        # Discovery needs the whole sitemap: a programme is recognised by the
        # plan page beside it, which is not in the candidate list itself.
        programmes, excluded = discover_programmes(
            [path for path in paths if path in set(candidates) or path.endswith(PLAN_SUFFIX)],
            titles,
        )
        plans = {
            ref.url + PLAN_SUFFIX: _get(client, ref.url + PLAN_SUFFIX, errors)
            for ref in programmes
        }

    dataset = build_dataset(
        programmes,
        {f"{BASE_URL}{path}": html for path, html in pages.items() if html},
        {url: html for url, html in plans.items() if html}, excluded, errors,
    )
    validate_dataset(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape UADE con reglas determinísticas")
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
    failed = [r for r in quality["programas_excluidos"] if "no se pudo" in r["motivo"]]
    print(f"Sin tipo declarado: {len(quality['programas_excluidos']) - len(failed)} "
          f"| no descargados: {len(failed)}")


if __name__ == "__main__":
    main()
