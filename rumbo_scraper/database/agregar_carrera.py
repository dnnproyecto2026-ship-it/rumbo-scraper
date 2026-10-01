"""Add one career a university's reading missed, from its official page.

A crawl or a guide can miss a faculty (UNMdP's reading never reached
Económicas, Psicología, Derecho or Medicina) or a section (UB's virtual
careers, whose addresses the reader did not recognise). This reads the
career's own page with the general reader (name, level, degree, duration,
description), appends the career to the university's artefact (a full
contract gets ``carreras`` and ``ofertas``; a guide's gets its ``ofertas``
row) and inserts it in the scraper DB if no career of that university has
that name. Nothing else changes; the export and its verifier take it from
there. ``--nombre`` names a page whose heading does not ("LICENCIATURA EN
ENFERMERÍA", "Carrera de Medicina"); it must still be a grado or pregrado
career by the reader's own classification.

Check first that the career is not already there under another name: this
does not look.

    python -m rumbo_scraper.database.agregar_carrera SIGLA data/<archivo>.json URL [--nombre "..."]
    python -m rumbo_scraper.database.agregar_carrera SIGLA data/<archivo>.json URL --apply
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from rumbo_scraper.parsers import generico as g


def leer_pagina(html: str, url: str, nombre: str | None = None) -> dict[str, Any]:
    """The career row the page gives, or ValueError if it is not a career."""
    programa = g.leer_programa(html, url)
    nombre = nombre or (programa.nombre if programa else None)
    if not nombre:
        h1 = BeautifulSoup(html or "", "html.parser").find("h1")
        nombre = re.sub(r"(?i)^carrera de\s+", "", " ".join(h1.get_text(" ").split())) if h1 else ""
    clase = g.clasificar(nombre) if nombre else None
    if not clase or clase[0] not in ("Grado", "Pregrado"):
        raise ValueError(f"no es una carrera de grado ni pregrado: {nombre!r}")
    datos = g.leer_datos(html)
    return {"nombre_carrera": nombre, "denominacion_canonica": nombre, "nivel": clase[0],
            "titulo_otorgado": g._titulo(datos.get("titulacion")), "tiene_titulo_intermedio": None,
            "duracion_anios": g.duracion_anios(datos.get("duracion")), "descripcion_breve": g.descripcion(html),
            "cantidad_materias_total": None}


def agregar_al_artefacto(artefacto: dict[str, Any], fila: dict[str, Any], url: str) -> bool:
    """Append the career; False if the artefact already offers one by that name."""
    datos = artefacto["datos"]
    nombre = fila["nombre_carrera"]
    if nombre in {o.get("carrera_nombre") for o in datos["ofertas"]}:
        return False
    if "carreras" in datos:
        oficial = datos["universidades"][0]["nombre_oficial"]
        datos["carreras"].append({"universidad_nombre": oficial, "facultad_nombre": None, **fila})
        datos["ofertas"].append({"universidad_nombre": oficial, "facultad_nombre": None, "carrera_nombre": nombre,
                                 "sede": None, "modalidad": None, "regimen_ingreso": None, "coneau_resolucion": None,
                                 "coneau_vigencia_hasta": None, "tiene_pasantias": None, "tiene_bolsa_trabajo": None,
                                 "url_oficial": url})
    else:
        datos["ofertas"].append({"carrera_nombre": nombre, "url_oficial": url, "facultad_nombre": ""})
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Agregar una carrera desde su página oficial")
    parser.add_argument("universidad", help="Sigla")
    parser.add_argument("artefacto", type=Path, help="data/<sigla>_completo.json o _guia_completo.json")
    parser.add_argument("url")
    parser.add_argument("--nombre", default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    from rumbo_scraper.spiders.visitante import Visitante

    with Visitante(timeout=30) as visitante:
        html = visitante.get(args.url) or ""
    fila = leer_pagina(html, args.url, args.nombre)
    print(json.dumps(fila, ensure_ascii=False, indent=1))
    if not args.apply:
        return
    artefacto = json.loads(args.artefacto.read_text())
    if not agregar_al_artefacto(artefacto, fila, args.url):
        raise SystemExit("ya está en el artefacto")
    args.artefacto.write_text(json.dumps(artefacto, ensure_ascii=False, indent=2) + "\n")

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    uid = client.table("universidades").select("id").eq("nombre_corto", args.universidad).execute().data[0]["id"]
    if not client.table("carreras").select("id").eq("universidad_id", uid).eq(
            "nombre_carrera", fila["nombre_carrera"]).execute().data:
        client.table("carreras").insert({"universidad_id": uid, "facultad_id": None, **fila}).execute()
    print("agregada")


if __name__ == "__main__":
    main()
