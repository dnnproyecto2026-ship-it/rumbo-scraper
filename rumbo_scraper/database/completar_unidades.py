"""Give each career without an academic unit the one its own page names.

The comparison of a career across universities starts from where each one
teaches it: Behavioural Sciences in a business school is not the same
career as in a faculty of health. 742 careers reached the export without
their unit, because the reader that found them read the list of careers and
not the career's page. This reads that page -- the one the offer records --
with `parsers.unidad`, which only answers when the page says it plainly.

A unit the university already published is linked; a new one is created
under the university, with its type. Nothing is overwritten: only careers
with no unit are touched.

Before the page's text, the page's data: a site built with Gatsby (the UCC's)
publishes each page's content as JSON, and the career's record there names
its unit as the university's own CMS holds it (`organizational_unit`). That
is not read off prose, and it is preferred.

A career taught in a campus that is itself a unit (the UTN's regional
faculties) is skipped: the export already names it by its campus.

Reading ~700 pages takes a while, so the preview keeps what it found in
``data/unidades_halladas.json`` and ``--apply`` writes from that file, reading
nothing again.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from rumbo_scraper.database.exportar_catalogo import _urls_de_los_artefactos
from rumbo_scraper.normalizers.text import comparison_key
from urllib.parse import urlparse

from rumbo_scraper.parsers.unidad import Unidad, es_la_pagina_de, unidad_de_la_pagina
from rumbo_scraper.spiders.visitante import Visitante

PAUSA = 1.0
# An address that is not a career's page although a career was filed under it:
# a subject of Medicine's plan at the UNLP ("Psicología", "Bioquímica"), a
# postgraduate, a research group, a tag or a news item. The unit such a page
# names is that page's, not the career's.
_NO_ES_SU_PAGINA = re.compile(
    r"\?view=article|/p(?:o|os)stgrado|/posgrado|/unidades-de-investigacion/|/tag/|/noticias?/")
HALLADAS = Path("data/unidades_halladas.json")


_TIPOS = {"facultad": "Facultad", "escuela": "Escuela",
          "departamento": "Departamento", "instituto": "Instituto"}


def _unidad_en(datos: Any) -> str | None:
    if isinstance(datos, dict):
        unidad = datos.get("organizational_unit")
        if isinstance(unidad, dict) and isinstance(unidad.get("name"), str):
            return unidad["name"]
        valores = datos.values()
    elif isinstance(datos, list):
        valores = datos
    else:
        return None
    for valor in valores:
        if nombre := _unidad_en(valor):
            return nombre
    return None


def unidad_de_los_datos(visitante: Visitante, url: str, html: str) -> Unidad | None:
    """The unit a Gatsby site's data for the page names, if it is one."""
    if "/page-data/" not in html and "gatsby" not in html.lower():
        return None
    partes = urlparse(url)
    datos = f"{partes.scheme}://{partes.netloc}/page-data{partes.path.rstrip('/')}/page-data.json"
    try:
        respuesta = visitante.client.get(datos)
        respuesta.raise_for_status()
        nombre = _unidad_en(respuesta.json())
    except Exception:
        return None
    tipo = _TIPOS.get((nombre or "").split(" ")[0].lower())
    return Unidad(nombre, tipo) if nombre and tipo else None


def leer(client: Any, solo: str | None) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all

    def todo(tabla: str) -> list[dict[str, Any]]:
        return select_all(client.table(tabla).select("*"))

    universidades = {u["id"]: u for u in todo("universidades")}
    unidades_de: dict[str, list[str]] = defaultdict(list)
    for f in todo("facultades"):
        unidades_de[f["universidad_id"]].append(f["nombre_facultad"])
    sedes = {s["id"]: s["nombre_sede"] for s in todo("sedes")}
    carreras = todo("carreras")
    universidad_de = {c["id"]: c["universidad_id"] for c in carreras}
    # The page of each career: the offer's, or the one the reading kept,
    # as the export finds it.
    artefactos = _urls_de_los_artefactos()
    url_de: dict[str, str] = {
        c["id"]: url for c in carreras
        if (url := artefactos.get((universidades[c["universidad_id"]]["nombre_oficial"],
                                   c["nombre_carrera"])))
    }
    en_una_unidad: set[str] = set()
    for oferta in todo("ofertas_academicas"):
        if oferta["url_oficial"]:
            url_de[oferta["carrera_id"]] = oferta["url_oficial"]
        uid = universidad_de.get(oferta["carrera_id"])
        if uid and sedes.get(oferta["sede_id"]) in unidades_de[uid]:
            en_una_unidad.add(oferta["carrera_id"])

    halladas = []
    with Visitante(timeout=20) as visitante:
        for carrera in sorted(carreras, key=lambda c: c["universidad_id"]):
            uid = carrera["universidad_id"]
            corto = universidades[uid].get("nombre_corto") or ""
            if carrera["facultad_id"] or (solo and comparison_key(corto) != comparison_key(solo)):
                continue
            url = url_de.get(carrera["id"])
            if not url or carrera["id"] in en_una_unidad or _NO_ES_SU_PAGINA.search(url):
                continue
            html = visitante.get(url)
            time.sleep(PAUSA)
            unidad = unidad_de_los_datos(visitante, url, html)
            if unidad:
                print(f"{corto:9} | {carrera['nombre_carrera'][:50]:50} | {unidad.nombre}",
                      flush=True)
                halladas.append({"carrera_id": carrera["id"], "universidad_id": uid,
                                 "universidad": corto, "carrera": carrera["nombre_carrera"],
                                 "unidad": unidad.nombre, "tipo": unidad.tipo, "url": url})
                continue
            if not es_la_pagina_de(html, carrera["nombre_carrera"]):
                continue
            firma = (universidades[uid]["nombre_oficial"], corto)
            unidad = unidad_de_la_pagina(html, unidades_de[uid], firma)
            if not unidad:
                continue
            print(f"{corto:9} | {carrera['nombre_carrera'][:50]:50} | {unidad.nombre}", flush=True)
            halladas.append({"carrera_id": carrera["id"], "universidad_id": uid,
                             "universidad": corto, "carrera": carrera["nombre_carrera"],
                             "unidad": unidad.nombre, "tipo": unidad.tipo, "url": url})
    return halladas


def aplicar(client: Any, halladas: list[dict[str, Any]]) -> int:
    from rumbo_scraper.database.supabase import select_all

    unidades_de: dict[str, dict[str, str]] = defaultdict(dict)
    for f in select_all(client.table("facultades").select("*")):
        unidades_de[f["universidad_id"]][f["nombre_facultad"]] = f["id"]
    # "Instituto de Estudios Iniciales" and "Instituto de Estudios Iniciales,
    # Humanidades y Educación" are one institute of the UNAJ, named short on
    # some pages: the short name goes under the full one.
    nombres_de: dict[str, set[str]] = defaultdict(set)
    for h in halladas:
        nombres_de[h["universidad_id"]].add(h["unidad"])
    for h in halladas:
        completo = [n for n in nombres_de[h["universidad_id"]] if n.startswith(h["unidad"] + ",")]
        if len(completo) == 1:
            h["unidad"] = completo[0]

    creadas = 0
    for h in halladas:
        uid = h["universidad_id"]
        fid = unidades_de[uid].get(h["unidad"])
        if fid is None:
            fid = client.table("facultades").insert({
                "universidad_id": uid, "nombre_facultad": h["unidad"], "tipo_unidad": h["tipo"],
            }).execute().data[0]["id"]
            unidades_de[uid][h["unidad"]] = fid
            creadas += 1
        # Only a career that still has none: nothing is overwritten.
        client.table("carreras").update({"facultad_id": fid}).eq(
            "id", h["carrera_id"]).is_("facultad_id", "null").execute()
    return creadas


def main() -> None:
    parser = argparse.ArgumentParser(description="Completar la unidad académica de las carreras")
    parser.add_argument("--apply", action="store_true",
                        help=f"Escribir en Supabase lo que dejó la vista previa en {HALLADAS}")
    parser.add_argument("--universidad", help="Sólo esta (nombre corto)")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()

    if args.apply:
        halladas = json.loads(HALLADAS.read_text())
        creadas = aplicar(client, halladas)
        print(f"Carreras con unidad: {len(halladas)}; unidades nuevas: {creadas}")
        return

    halladas = leer(client, args.universidad)
    HALLADAS.write_text(json.dumps(halladas, ensure_ascii=False, indent=1) + "\n")
    por_universidad: dict[str, int] = defaultdict(int)
    for h in halladas:
        por_universidad[h["universidad"]] += 1
    print(f"Con unidad: {len(halladas)} {dict(por_universidad)} — vista previa en {HALLADAS}")


if __name__ == "__main__":
    main()
