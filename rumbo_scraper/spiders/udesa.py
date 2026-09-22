"""Scrape UdeSA degrees and curricula without AI services or API tokens."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from playwright.async_api import Browser, async_playwright

from rumbo_scraper.parsers.udesa import (
    AUTHORITY_URLS, BASE_URL, CAMPUSES_URL, CAREERS, CONTENT_URLS,
    FACULTY_DIRECTORY_URL, INTERNATIONAL_URLS,
    POSTGRADUATE_INDEX_URL, SOURCE_URL,
    build_dataset, discover_graduate_plan_url, discover_plan_url,
    discover_postgraduates,
)
from rumbo_scraper.validators.udesa import validate_dataset


DEFAULT_OUTPUT = Path("data/udesa_completo.json")


async def _fetch_next_data(
    browser: Browser, url: str, errors: list[dict[str, str]], semaphore: asyncio.Semaphore
) -> tuple[dict[str, Any], str] | None:
    async with semaphore:
        page = await browser.new_page()
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            if response is None or response.status >= 400:
                raise RuntimeError(f"HTTP {response.status if response else 'sin respuesta'}")
            node = page.locator("#__NEXT_DATA__")
            await node.wait_for(state="attached", timeout=20_000)
            raw = await node.text_content()
            if not raw:
                raise RuntimeError("La página no contiene __NEXT_DATA__")
            payload = json.loads(raw)
            page_props = payload.get("props", {}).get("pageProps")
            if not isinstance(page_props, dict):
                raise RuntimeError("pageProps no es un objeto")
            return page_props, page.url
        except Exception as exc:  # preserve the URL and continue the audit
            errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
            return None
        finally:
            await page.close()


async def _fetch_rendered_html(
    browser: Browser, url: str, errors: list[dict[str, str]], semaphore: asyncio.Semaphore
) -> str:
    """Return the rendered page. The institutional channels are only linked in
    the footer markup, not in the structured payload."""
    async with semaphore:
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=60_000)
            await page.mouse.wheel(0, 30_000)
            await page.wait_for_timeout(2_000)
            return await page.content()
        except Exception as exc:
            errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
            return ""
        finally:
            await page.close()


async def _run(output: Path) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    semaphore = asyncio.Semaphore(4)
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        try:
            response = await client.get(CAMPUSES_URL, headers={"User-Agent": "RumboScraper/0.3"})
            response.raise_for_status()
            campuses_html = response.text
        except httpx.HTTPError as exc:
            errors.append({"url": CAMPUSES_URL, "error": str(exc)})
            campuses_html = ""

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        landing_task = _fetch_next_data(browser, SOURCE_URL, errors, semaphore)
        career_urls = [urljoin(BASE_URL, config.url) for config in CAREERS]
        career_results = await asyncio.gather(*(
            _fetch_next_data(browser, url, errors, semaphore) for url in career_urls
        ))
        index_result = await _fetch_next_data(
            browser, POSTGRADUATE_INDEX_URL, errors, semaphore
        )
        postgraduate_refs = discover_postgraduates(index_result[0]) if index_result else ()
        postgraduate_urls = [ref.url for ref in postgraduate_refs]
        postgraduate_results = await asyncio.gather(*(
            _fetch_next_data(browser, url, errors, semaphore) for url in postgraduate_urls
        ))
        postgraduate_pages = {
            requested: result
            for requested, result in zip(postgraduate_urls, postgraduate_results, strict=True)
            if result is not None
        }

        postgraduate_plan_urls = sorted({
            plan_url
            for page, final_url in postgraduate_pages.values()
            if (plan_url := discover_graduate_plan_url(page, final_url))
        })
        postgraduate_plan_results = await asyncio.gather(*(
            _fetch_next_data(browser, url, errors, semaphore)
            for url in postgraduate_plan_urls
        ))
        postgraduate_plan_pages = {
            requested: result[0]
            for requested, result in zip(
                postgraduate_plan_urls, postgraduate_plan_results, strict=True
            )
            if result is not None
        }

        directory_result = await _fetch_next_data(
            browser, FACULTY_DIRECTORY_URL, errors, semaphore
        )
        authority_results = await asyncio.gather(*(
            _fetch_next_data(browser, url, errors, semaphore) for url in AUTHORITY_URLS
        ))
        authority_pages = {
            url: result[0]
            for url, result in zip(AUTHORITY_URLS, authority_results, strict=True)
            if result is not None
        }

        content_results = await asyncio.gather(*(
            _fetch_next_data(browser, url, errors, semaphore) for url in CONTENT_URLS
        ))
        content_pages = {
            url: result[0]
            for url, result in zip(CONTENT_URLS, content_results, strict=True)
            if result is not None
        }

        international_results = await asyncio.gather(*(
            _fetch_next_data(browser, url, errors, semaphore) for url in INTERNATIONAL_URLS
        ))
        international_pages = {
            url: result[0]
            for url, result in zip(INTERNATIONAL_URLS, international_results, strict=True)
            if result is not None
        }
        landing_html = await _fetch_rendered_html(browser, SOURCE_URL, errors, semaphore)

        landing_result = await landing_task
        career_pages = {
            requested: result
            for requested, result in zip(career_urls, career_results, strict=True)
            if result is not None
        }

        plan_urls = sorted({
            plan_url
            for requested, (page, final_url) in career_pages.items()
            if (plan_url := discover_plan_url(page, final_url))
        })
        plan_results = await asyncio.gather(*(
            _fetch_next_data(browser, url, errors, semaphore) for url in plan_urls
        ))
        plan_pages = {
            requested: result[0]
            for requested, result in zip(plan_urls, plan_results, strict=True)
            if result is not None
        }
        await browser.close()

    landing_page = landing_result[0] if landing_result else {}
    dataset = build_dataset(
        landing_page, career_pages, plan_pages, campuses_html, errors,
        postgraduate_refs, postgraduate_pages, postgraduate_plan_pages,
        directory_result[0] if directory_result else None, authority_pages,
        content_pages, international_pages, landing_html,
    )
    validate_dataset(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return dataset


def run(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    return asyncio.run(_run(output))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape UdeSA with deterministic rules (no AI or API tokens)"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    dataset = run(args.output)
    data = dataset["datos"]
    quality = dataset["control_calidad"]
    print(f"OK: {len(data['carreras'])} carreras")
    postgraduate_names = {row["nombre_programa"] for row in data["posgrados"]}
    postgraduate_subjects = sum(
        1 for row in data["materias"] if row["carrera_o_programa"] in postgraduate_names
    )
    print(f"OK: {len(data['materias'])} materias de planes de estudio "
          f"({postgraduate_subjects} de posgrado)")
    print(f"OK: {len(data['facultades'])} unidades académicas")
    print(f"OK: {len(data['posgrados'])} posgrados de "
          f"{quality['posgrados_descubiertos']} descubiertos en el índice oficial")
    directory = dataset["directorio_academico"]
    print(f"OK: {len(data['autoridades'])} autoridades")
    print(f"OK: {len(directory['personas'])} personas académicas")
    print(f"OK: {len(directory['roles_academicos'])} roles académicos")
    for section in ("actividades", "redes_contacto", "programas_internacionales",
                    "becas", "servicios_estudiantiles",
                    "actividades_extracurriculares", "alojamiento"):
        print(f"OK: {len(data[section])} {section.replace('_', ' ')}")
    print(f"OK: {len(dataset['recursos_publicos'])} imágenes, documentos y enlaces")
    print(f"Archivo: {args.output}")
    print("Método: algorítmico, sin IA y sin tokens")
    for excluded in quality["posgrados_excluidos"]:
        print(f"Excluido: {excluded['nombre']} — {excluded['motivo']}")
    if quality["errores_descarga"]:
        print(f"Advertencia: {len(quality['errores_descarga'])} páginas no se pudieron descargar")


if __name__ == "__main__":
    main()
