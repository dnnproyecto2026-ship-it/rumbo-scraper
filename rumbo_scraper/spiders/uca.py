"""Scrape UCA public pages with a browser, without AI services or API tokens."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, async_playwright

from rumbo_scraper.parsers.uca import (
    FACULTIES_URL, build_dataset, discover_faculties, discover_programmes,
)
from rumbo_scraper.validators.uca import validate_dataset

DEFAULT_OUTPUT = Path("data/uca_completo.json")
# The site renders on the client and the plan only appears once its section is
# opened, so every page needs a browser and one click.
PLAN_LABEL = "Plan de estudio"


async def _links(page: Any) -> list[tuple[str, str]]:
    pairs = await page.eval_on_selector_all(
        "a", "els => els.map(e => [e.href, (e.textContent||'').trim()])"
    )
    return [(href, text) for href, text in pairs if href]


async def _render(browser: Browser, url: str, errors: list[dict[str, str]],
                  semaphore: asyncio.Semaphore, open_plan: bool = False
                  ) -> tuple[str, list[tuple[str, str]]]:
    async with semaphore:
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            await page.wait_for_timeout(4_000)
            if open_plan:
                try:
                    await page.locator(f"text={PLAN_LABEL}").first.click(timeout=6_000)
                    await page.wait_for_timeout(2_000)
                except Exception:
                    # A programme without a published plan simply has no section.
                    pass
            return await page.content(), await _links(page)
        except Exception as exc:
            errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
            return "", []
        finally:
            await page.close()


async def _run(output: Path, limit: int | None) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    semaphore = asyncio.Semaphore(3)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        _, hub_links = await _render(browser, FACULTIES_URL, errors, semaphore)
        faculties = discover_faculties(hub_links)
        results = await asyncio.gather(*(
            _render(browser, url, errors, semaphore) for url in faculties
        ))
        faculty_pages = {
            url: links for url, (_, links) in zip(faculties, results, strict=True)
        }
        # The site renders on the client, so a faculty page can finish loading
        # its shell before its programme links exist. A page that yielded none
        # is asked again once, which is what made two runs of the same site
        # discover different numbers of programmes.
        empty = [url for url, links in faculty_pages.items()
                 if not any("/carrera" in (href or "") or "/posgrado" in (href or "")
                            for href, _ in links)]
        if empty:
            retried = await asyncio.gather(*(
                _render(browser, url, errors, semaphore) for url in empty
            ))
            for url, (_, links) in zip(empty, retried, strict=True):
                if links:
                    faculty_pages[url] = links
        programmes, excluded = discover_programmes(faculty_pages)
        if limit is not None:
            programmes = programmes[:limit]
        rendered = await asyncio.gather(*(
            _render(browser, ref.url, errors, semaphore, open_plan=True)
            for ref in programmes
        ))
        pages = {
            ref.url: html for ref, (html, _) in zip(programmes, rendered, strict=True)
        }
        await browser.close()

    dataset = build_dataset(
        programmes, {url: html for url, html in pages.items() if html}, excluded, errors
    )
    validate_dataset(dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return dataset


def run(output: Path = DEFAULT_OUTPUT, limit: int | None = None) -> dict[str, Any]:
    return asyncio.run(_run(output, limit))


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape UCA con reglas determinísticas")
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
    failed = [r for r in quality["programas_excluidos"] if "renderizar" in r["motivo"]]
    print(f"Sin nivel declarado: {len(quality['programas_excluidos']) - len(failed)} "
          f"| no renderizados: {len(failed)}")


if __name__ == "__main__":
    main()
