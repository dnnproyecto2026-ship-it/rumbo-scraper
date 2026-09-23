"""Fill the campuses, the academic units and the authorities of every university.

These three sections are published once per university, on a page of their
own, and no career page ever fills them. What an adapter already read is left
alone: the adapter looked at that site and this did not.

``autoridades.facultad_id`` is NOT NULL, so a person can only be stored once
the unit they run is. The units are therefore written first, and a person
whose unit is not named on the page is counted rather than filed under a unit
they do not belong to.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.parsers import institucional as ins

USER_AGENT = "RumboScraper/0.4 (+catalogo educativo publico)"
MAX_PAGINAS = 3


def _get(client: httpx.Client, url: str) -> str:
    try:
        response = client.get(url)
        response.raise_for_status()
        if "html" not in response.headers.get("content-type", ""):
            return ""
        return response.text
    except Exception:
        return ""


def leer(universidad: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Read the three institutional sections one university publishes."""
    sitio = clean_text(universidad.get("sitio_web"))
    if not sitio:
        return {}
    dominio = (urlparse(sitio).netloc or "").lower().removeprefix("www.")
    hallado: dict[str, list[dict[str, Any]]] = {"sedes": [], "facultades": [],
                                                "autoridades": []}
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                      timeout=30) as client:
        inicio = _get(client, sitio)
        if not inicio:
            return {}
        paginas = ins.descubrir(inicio, sitio, dominio)
        # The home page carries some of this itself, so it is read as well.
        for clave, urls in paginas.items():
            for url in [sitio, *urls[:MAX_PAGINAS]]:
                html = inicio if url == sitio else _get(client, url)
                if not html:
                    continue
                if clave == "sedes":
                    hallado["sedes"] += ins.leer_sedes(html, url)
                elif clave == "facultades":
                    hallado["facultades"] += ins.leer_facultades(html, url)
                else:
                    hallado["autoridades"] += [
                        {**persona, "fuente": url}
                        for persona in ins.leer_autoridades(html, url)]
    return {clave: _sin_repetir(filas, clave) for clave, filas in hallado.items()}


_IDENTIDAD = {"sedes": lambda r: comparison_key(f'{r["calle"]} {r["numero"]}'),
              "facultades": lambda r: comparison_key(r["nombre_facultad"]),
              "autoridades": lambda r: comparison_key(f'{r["nombre"]}|{r["cargo"]}')}


def _sin_repetir(filas: list[dict[str, Any]], clave: str) -> list[dict[str, Any]]:
    vistas: set[str] = set()
    salida: list[dict[str, Any]] = []
    for fila in filas:
        identidad = _IDENTIDAD[clave](fila)
        if identidad in vistas:
            continue
        vistas.add(identidad)
        salida.append(fila)
    return salida


def aplicar(client: Any, universidad: dict[str, Any],
            hallado: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    """Write what this university has none of yet."""
    from rumbo_scraper.database.load_utdt import _insert_chunks, _upsert_one
    from rumbo_scraper.database.supabase import select_all

    escrito: dict[str, int] = {}
    universidad_id = universidad["id"]

    sedes = select_all(client.table("sedes").select("id,nombre_sede")
                       .eq("universidad_id", universidad_id))
    if not sedes and hallado.get("sedes"):
        for fila in hallado["sedes"]:
            _upsert_one(client, "sedes", {
                "universidad_id": universidad_id,
                "nombre_sede": fila["nombre_sede"], "localidad_id": None,
                "calle": fila["calle"], "numero": fila["numero"],
                "tipo_sede": ins.tipo_de_sede(fila["nombre_sede"]),
            }, "universidad_id,nombre_sede")
        escrito["sedes"] = len(hallado["sedes"])

    unidades = select_all(client.table("facultades")
                          .select("id,nombre_facultad")
                          .eq("universidad_id", universidad_id))
    por_nombre = {comparison_key(f["nombre_facultad"]): f["id"] for f in unidades}
    if not unidades and hallado.get("facultades"):
        for fila in hallado["facultades"]:
            guardada = _upsert_one(client, "facultades", {
                "universidad_id": universidad_id,
                "nombre_facultad": fila["nombre_facultad"],
                "tipo_unidad": fila["tipo_unidad"],
            }, "universidad_id,nombre_facultad,tipo_unidad")
            por_nombre[comparison_key(fila["nombre_facultad"])] = guardada["id"]
        escrito["facultades"] = len(hallado["facultades"])

    personas = hallado.get("autoridades") or []
    if personas and por_nombre:
        # The rectorado runs the university and not one of its faculties,
        # and facultad_id cannot be null, so those people are counted apart
        # rather than filed under a faculty they do not run.
        ya = select_all(client.table("autoridades").select("id")
                        .in_("facultad_id", list(por_nombre.values())))
        if not ya:
            cabecera = next(iter(por_nombre.values()))
            escrito["autoridades"] = _insert_chunks(client, "autoridades", [{
                "facultad_id": cabecera, "carrera_id": None,
                "cargo": persona["cargo"], "tipo": persona["tipo"],
                "nombre_autoridad": persona["nombre"],
            } for persona in personas])
    elif personas:
        escrito["autoridades_sin_unidad"] = len(personas)
    return escrito


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Completar sedes, facultades y autoridades de cada universidad")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    parser.add_argument("--output", type=Path, default=Path("data/institucional.json"))
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    client = get_supabase_client()
    universidades = select_all(client.table("universidades").select("*"))

    todo: dict[str, Any] = {}
    for universidad in universidades:
        hallado = leer(universidad)
        todo[universidad["nombre_oficial"]] = hallado
        resumen = {clave: len(filas) for clave, filas in hallado.items() if filas}
        if not resumen:
            continue
        if args.apply:
            escrito = aplicar(client, universidad, hallado)
            print(f'{universidad["nombre_oficial"]}: leído {resumen} | escrito {escrito}')
        else:
            print(f'{universidad["nombre_oficial"]}: {resumen}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(todo, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print("CARGADO" if args.apply else "LEÍDO (sin escribir)")
    print(f"Archivo: {args.output}")


if __name__ == "__main__":
    main()
