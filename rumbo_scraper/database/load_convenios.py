"""Fill the exchange agreements of every university that publishes them.

The list of partner universities sits on the international page of a
university, which the student-life reader already finds. Only a university
with no agreements stored is written: UTDT's six hundred and seventy-one came
from its own adapter.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers import vida
from rumbo_scraper.parsers.convenios import leer_convenios

USER_AGENT = "RumboScraper/0.4 (+catalogo educativo publico)"
MAX_PAGINAS = 6


def _get(client: httpx.Client, url: str) -> str:
    try:
        response = client.get(url)
        response.raise_for_status()
        if "html" not in response.headers.get("content-type", ""):
            return ""
        return response.text
    except Exception:
        return ""


def leer(universidad: dict[str, Any]) -> list[dict[str, Any]]:
    """Read the partner universities one university lists."""
    sitio = clean_text(universidad.get("sitio_web"))
    if not sitio:
        return []
    dominio = (urlparse(sitio).netloc or "").lower().removeprefix("www.")
    hallados: list[dict[str, Any]] = []
    vistos: set[str] = set()
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                      timeout=30) as client:
        inicio = _get(client, sitio)
        if not inicio:
            return []
        paginas = vida.discover_topics(inicio, sitio, dominio)["programas_internacionales"]
        # A page about exchanges links the list of partners one step further.
        for url in list(paginas[:MAX_PAGINAS]):
            html = _get(client, url)
            for fila in leer_convenios(html, url, universidad["nombre_oficial"]):
                clave = fila["universidad_destino"].lower()
                if clave not in vistos:
                    vistos.add(clave)
                    hallados.append(fila)
            if html:
                for otra, lista in vida.discover_topics(html, url, dominio).items():
                    if otra != "programas_internacionales":
                        continue
                    for extra in lista:
                        if extra not in paginas and len(paginas) < MAX_PAGINAS * 2:
                            paginas.append(extra)
        for url in paginas[MAX_PAGINAS:MAX_PAGINAS * 2]:
            for fila in leer_convenios(_get(client, url), url,
                                       universidad["nombre_oficial"]):
                clave = fila["universidad_destino"].lower()
                if clave not in vistos:
                    vistos.add(clave)
                    hallados.append(fila)
    return hallados


def aplicar(client: Any, universidad: dict[str, Any],
            convenios: list[dict[str, Any]]) -> int:
    ya = client.table("convenios_intercambio").select("id").eq(
        "universidad_id", universidad["id"]).limit(1).execute().data
    convenios = [c for c in convenios if c.get("programa")]
    if ya or not convenios:
        return 0
    filas = [{"universidad_id": universidad["id"], "programa_origen": c["programa"],
              "universidad_destino": c["universidad_destino"], "ciudad": None,
              "pais": c["pais"], "latitud": None, "longitud": None,
              "observaciones": None, "fuente_url": c["fuente"],
              "carrera_id": None, "posgrado_id": None} for c in convenios]
    for start in range(0, len(filas), 100):
        client.table("convenios_intercambio").insert(filas[start:start + 100]).execute()
    return len(filas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Completar los convenios de intercambio")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    parser.add_argument("--output", type=Path, default=Path("data/convenios.json"))
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    client = get_supabase_client()
    todo: dict[str, Any] = {}
    for universidad in select_all(client.table("universidades").select("*")):
        convenios = leer(universidad)
        todo[universidad["nombre_oficial"]] = convenios
        if not convenios:
            continue
        escrito = aplicar(client, universidad, convenios) if args.apply else 0
        print(f'{universidad["nombre_oficial"]}: leídos {len(convenios)} | escritos {escrito}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(todo, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print("CARGADO" if args.apply else "LEÍDO (sin escribir)")


if __name__ == "__main__":
    main()
