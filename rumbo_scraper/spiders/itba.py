"""Scrape ITBA public pages without AI services or API tokens."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from playwright.async_api import async_playwright

from rumbo_scraper.parsers.itba import (
    AUTHORITIES_URL, BASE_URL, CAMPUSES_URL, TEACHER_SITEMAP_URL,
    build_dataset, discover_programmes, sitemap_urls,
)
from rumbo_scraper.validators.itba import validate_dataset

DEFAULT_OUTPUT = Path("data/itba_completo.json")
USER_AGENT = "RumboScraper/0.3"


async def _menu_links(errors: list[dict[str, str]]) -> list[tuple[str, str]]:
    """Read the rendered menu, the only place the full programme names appear.

    The pages themselves title a degree "Civil"; the menu writes "Ing. Civil",
    which is the name the university publishes for it.
    """
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=90_000)
                await page.wait_for_timeout(4_000)
                pairs = await page.eval_on_selector_all(
                    "a", "els => els.map(e => [e.getAttribute('href'), (e.textContent||'').trim()])"
                )
                return [(href, text) for href, text in pairs if href and text]
            finally:
                await browser.close()
    except Exception as exc:
        errors.append({"url": BASE_URL, "error": f"{type(exc).__name__}: {exc}"})
        return []


def _get(client: httpx.Client, url: str, errors: list[dict[str, str]]) -> str:
    try:
        response = client.get(url)
        response.raise_for_status()
        return response.text
    except httpx.HTTPError as exc:
        errors.append({"url": url, "error": str(exc)})
        return ""


def run(output: Path = DEFAULT_OUTPUT, teacher_limit: int | None = None) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    menu = asyncio.run(_menu_links(errors))
    programmes = discover_programmes(menu)

    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                      timeout=45) as client:
        programme_pages = {ref.url: _get(client, ref.url, errors) for ref in programmes}
        campuses_html = _get(client, CAMPUSES_URL, errors)
        authorities_html = _get(client, AUTHORITIES_URL, errors)
        teacher_urls = sitemap_urls(_get(client, TEACHER_SITEMAP_URL, errors))
        if teacher_limit is not None:
            teacher_urls = teacher_urls[:teacher_limit]
        teacher_pages = {url: _get(client, url, errors) for url in teacher_urls}

    dataset = build_dataset(
        programmes, {url: html for url, html in programme_pages.items() if html},
        campuses_html, authorities_html,
        {url: html for url, html in teacher_pages.items() if html}, errors,
    )
    validate_dataset(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape ITBA con reglas determinísticas")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--teacher-limit", type=int, default=None)
    args = parser.parse_args()
    dataset = run(args.output, args.teacher_limit)
    data = dataset["datos"]
    quality = dataset["control_calidad"]
    print(f"OK: {len(data['carreras'])} carreras de "
          f"{quality['programas_descubiertos']} programas descubiertos")
    print(f"OK: {len(data['posgrados'])} posgrados")
    print(f"OK: {len(data['materias'])} materias")
    print(f"OK: {len(data['sedes'])} sedes")
    print(f"OK: {len(data['autoridades'])} autoridades")
    print(f"OK: {len(dataset['directorio_academico']['personas'])} personas académicas")
    print(f"OK: {len(dataset['recursos_publicos'])} recursos públicos")
    print(f"Archivo: {args.output}")
    if quality["carreras_sin_plan_publicado"]:
        print(f"Sin plan en HTML ({len(quality['carreras_sin_plan_publicado'])}): "
              + ", ".join(quality["carreras_sin_plan_publicado"]))
    for excluded in quality["programas_excluidos"]:
        print(f"Excluido: {excluded['nombre']} — {excluded['motivo']}")
    if quality["errores_descarga"]:
        print(f"Advertencia: {len(quality['errores_descarga'])} páginas no se pudieron descargar")


if __name__ == "__main__":
    main()
