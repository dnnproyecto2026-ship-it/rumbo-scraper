"""Extract the public UTDT semester course catalogue rendered by Looker Studio."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

from rumbo_scraper.parsers.utdt_catalog import parse_detail_row, parse_schedule_row


REPORT_URL = "https://datastudio.google.com/reporting/30c8c711-0f14-462a-a825-fb5fe501bc1d/page/hAzCD"
DEFAULT_OUTPUT = Path("data/utdt_catalogo_cursos.json")
TABLE_SELECTOR = '[aria-label="Pulsa Intro o Espacio para mostrar el encabezado del gráfico"].simple-table'


def _table_with_headers(page: Any, expected: list[str]) -> Any:
    for table in page.locator(TABLE_SELECTOR).all():
        headers = [value.strip() for value in table.locator(".colName").all_text_contents()]
        if headers == expected:
            return table
    raise RuntimeError(f"No se encontró la tabla de Looker Studio con columnas {expected}")


def _visible_rows(table: Any) -> list[tuple[list[str], str | None]]:
    result: list[tuple[list[str], str | None]] = []
    for row in table.locator(".centerColsContainer .row").all():
        cells = row.locator(".cell")
        if cells.count() == 0:
            continue
        values: list[str] = []
        for cell in cells.all():
            value = cell.locator(".cell-value")
            values.append(value.inner_text().strip() if value.count() else "")
        links = cells.last.locator("a")
        link = links.first.get_attribute("href") if links.count() else None
        result.append((values, link))
    return result


def _collect_current_page(table: Any, page: Any) -> list[tuple[list[str], str | None]]:
    container = table.locator(".centerColsContainer")
    dimensions = container.evaluate("el => ({height: el.clientHeight, total: el.scrollHeight})")
    step = max(int(dimensions["height"]) - 32, 32)
    collected: dict[tuple[str, ...], tuple[list[str], str | None]] = {}
    for offset in range(0, int(dimensions["total"]) + step, step):
        container.evaluate("(el, offset) => { el.scrollTop = offset; }", offset)
        page.wait_for_timeout(40)
        for values, link in _visible_rows(table):
            collected[tuple(values)] = (values, link)
    return list(collected.values())


def _collect_table(table: Any, page: Any) -> list[tuple[list[str], str | None]]:
    collected: list[tuple[list[str], str | None]] = []
    while True:
        label = table.locator(".pageLabel").inner_text().strip()
        numbers = [int(value) for value in re.findall(r"\d+", label)]
        if len(numbers) < 3:
            raise RuntimeError(f"Paginación de Looker Studio no reconocida: {label}")
        collected.extend(_collect_current_page(table, page))
        if len(numbers) < 3 or numbers[1] >= numbers[2]:
            break
        table.locator(".centerColsContainer").evaluate("el => { el.scrollTop = 0; }")
        forward = table.locator(".pageForward")
        forward.click(force=True)
        for _ in range(300):
            page.wait_for_timeout(100)
            if table.locator(".pageLabel").inner_text().strip() != label:
                break
        else:
            raise RuntimeError(f"Looker Studio no avanzó después de la página {label}")
    return collected


def scrape_catalog(year: int, semester: int, report_url: str = REPORT_URL) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Falta Playwright. Ejecutá: pip install -r requirements.txt && playwright install chromium"
        ) from exc

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True, channel="chrome")
        except Exception:
            browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, locale="es-AR")
        page.goto(report_url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_selector(TABLE_SELECTOR, timeout=90_000)
        page.wait_for_timeout(5_000)

        schedule_table = _table_with_headers(
            page, ["MATERIA", "SECCIÓN", "CLASE", "DOCENTES", "DÍA", "HORARIO"]
        )
        detail_table = _table_with_headers(
            page, ["CURSO", "CONTENIDO", "CONDICIONES DE APROBACIÓN", "LINK"]
        )
        schedule_rows = [parse_schedule_row(values) for values, _ in _collect_table(schedule_table, page)]
        detail_rows = [parse_detail_row(values, link) for values, link in _collect_table(detail_table, page)]
        browser.close()

    return {
        "fuente_url": report_url,
        "extraido_at": datetime.now(UTC).isoformat(),
        "periodo": {"anio": year, "semestre": semester},
        "horarios": schedule_rows,
        "detalles": detail_rows,
        "control_calidad": {
            "filas_horarios": len(schedule_rows),
            "filas_detalles": len(detail_rows),
            "horarios_sin_codigo": sum(not row["codigo_materia"] for row in schedule_rows),
            "detalles_sin_contenido": sum(not row["contenido"] for row in detail_rows),
            "detalles_sin_condiciones": sum(not row["condiciones_aprobacion"] for row in detail_rows),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrae el catálogo semestral de cursos de UTDT")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--semester", type=int, choices=(1, 2), required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--url", default=REPORT_URL)
    args = parser.parse_args()
    dataset = scrape_catalog(args.year, args.semester, args.url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {dataset['control_calidad']['filas_horarios']} filas de horarios")
    print(f"OK: {dataset['control_calidad']['filas_detalles']} filas de contenidos")
    print(f"Archivo: {args.output}")


if __name__ == "__main__":
    main()
