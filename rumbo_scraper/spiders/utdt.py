"""Crawl official UTDT pages and build the full Excel-aligned preview."""

import argparse
import json
from pathlib import Path

import httpx

from rumbo_scraper.parsers.utdt import (
    AUTHORITIES_URL, CAREERS, INSTITUTION_URL, SOURCE_URL, build_dataset,
    parse_career_detail,
)
from rumbo_scraper.validators.utdt import validate_dataset


DEFAULT_OUTPUT = Path("data/utdt_completo.json")
USER_AGENT = "RumboScraper/0.2 (+educational data collection)"


def _fetch(client: httpx.Client, url: str, errors: list[dict[str, str]]) -> str:
    try:
        response = client.get(url)
        response.raise_for_status()
        return response.text
    except httpx.HTTPError as exc:
        errors.append({"url": url, "error": str(exc)})
        return ""


def run(output: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    errors: list[dict[str, str]] = []
    detail_pages: dict[str, str] = {}
    plan_pages: dict[str, str] = {}
    with httpx.Client(
        follow_redirects=True,
        timeout=30.0,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        admissions_html = _fetch(client, SOURCE_URL, errors)
        institution_html = _fetch(client, INSTITUTION_URL, errors)
        authorities_html = _fetch(client, AUTHORITIES_URL, errors)
        for config in CAREERS.values():
            html = _fetch(client, config.detail_url, errors)
            detail_pages[config.detail_url] = html
            plan_url = parse_career_detail(html, config).get("plan_url") if html else None
            if plan_url and str(plan_url) not in plan_pages:
                plan_pages[str(plan_url)] = _fetch(client, str(plan_url), errors)

    dataset = build_dataset(
        admissions_html, institution_html, detail_pages, plan_pages, errors,
        authorities_html,
    )
    validate_dataset(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape the full UTDT data contract")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    dataset = run(args.output)
    data = dataset["datos"]
    quality = dataset["control_calidad"]
    print(f"OK: {len(data['carreras'])} carreras")
    print(f"OK: {len(data['materias'])} materias")
    print(f"OK: {len(data['posgrados'])} posgrados descubiertos")
    print(f"Archivo: {args.output}")
    if quality["secciones_vacias"]:
        print("Pendiente por falta de fuente pública: " + ", ".join(quality["secciones_vacias"]))
    if quality["errores_descarga"]:
        print(f"Advertencia: {len(quality['errores_descarga'])} páginas no se pudieron descargar")


if __name__ == "__main__":
    main()
