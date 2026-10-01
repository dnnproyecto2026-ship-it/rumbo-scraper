"""The plans a university publishes only as a brochure image, read by OCR.

The USAL shows each career's plan as a picture (``Folleto…-01.png``) under
"PLAN DE ESTUDIOS" on the career's page: no text, no document. This finds
that picture for each career that has no subjects, keeps it in
``data/planes_folletos/``, reads it with tesseract word by word and takes
the plan `parsers.folleto_usal.plan_del_folleto` gives, which is nothing
when the brochure does not read clean.

As in `planes_documentos`, a plan must reach at least the year before the
career's last: a five-year career whose brochure reads to the third is
missing a column.

The preview keeps its own file (``data/planes_folletos.json``); ``--apply``
writes from it.

    python -m rumbo_scraper.database.planes_folletos
    python -m rumbo_scraper.database.planes_folletos --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rumbo_scraper.database import planes_documentos as pd
from rumbo_scraper.parsers import folleto_usal
from rumbo_scraper.spiders.visitante import Visitante

CACHE = Path("data/planes_folletos")
HALLADOS = Path("data/planes_folletos.json")
# The universities whose pages show the plan as a brochure, and where in the
# page the brochure is.
FOLLETOS = {"USAL": ".propuesta-plan img"}
PAUSA = 1.0


def leer(client: Any, solo: set[str]) -> dict[str, dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all

    universidades = {u["id"]: u for u in select_all(client.table("universidades").select("*"))
                     if u.get("nombre_corto") in FOLLETOS and (not solo or u.get("nombre_corto") in solo)}
    carreras = [c for c in select_all(client.table("carreras").select(
        "id,universidad_id,nombre_carrera,nivel,duracion_anios")) if c["universidad_id"] in universidades]
    con_materias = {m["carrera_id"] for m in select_all(
        client.table("materias").select("carrera_id")) if m["carrera_id"]}
    artefactos = pd._urls_de_los_artefactos()
    url_de = {c["id"]: artefactos.get((universidades[c["universidad_id"]]["nombre_oficial"],
                                       c["nombre_carrera"])) for c in carreras}
    for oferta in select_all(client.table("ofertas_academicas").select("carrera_id,url_oficial")):
        if oferta["url_oficial"] and oferta["carrera_id"] in url_de:
            url_de[oferta["carrera_id"]] = oferta["url_oficial"]

    CACHE.mkdir(parents=True, exist_ok=True)
    planes: dict[str, dict[str, Any]] = {}
    with Visitante(timeout=40) as visitante:
        for carrera in carreras:
            url = url_de.get(carrera["id"])
            # A cycle of complementation is for graduates, not for the
            # students Rumbo serves, and its brochures are drawn tighter:
            # names wrap without a connecting word ("Gestión Estratégica de
            # la Comunicación" over "Institucional").
            if carrera["id"] in con_materias or not url or "complementaci" in carrera["nombre_carrera"].lower():
                continue
            corto = universidades[carrera["universidad_id"]]["nombre_corto"]
            html = visitante.get(url)
            time.sleep(PAUSA)
            imagen = BeautifulSoup(html or "", "html.parser").select_one(FOLLETOS[corto])
            if not imagen or not imagen.get("src"):
                continue
            folleto = urljoin(url, imagen["src"])
            archivo = CACHE / (hashlib.md5(folleto.encode()).hexdigest() + ".png")
            if not archivo.exists():
                try:
                    respuesta = visitante.client.get(folleto)
                    archivo.write_bytes(respuesta.content if respuesta.status_code == 200 else b"")
                except Exception:
                    archivo.write_bytes(b"")
                time.sleep(PAUSA)
            if not archivo.stat().st_size:
                continue
            materias = folleto_usal.plan_del_folleto(folleto_usal.leer(archivo), carrera["nombre_carrera"])
            duracion = carrera.get("duracion_anios") or 0
            if not materias or max(a for _, a in materias) < int(duracion) - 1:
                continue
            planes[carrera["id"]] = {"universidad": corto, "carrera": carrera,
                                     "documento": folleto, "materias": materias}
    return planes


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar los planes publicados como folleto en imagen")
    parser.add_argument("--apply", action="store_true", help=f"Escribir lo que dejó la vista previa en {HALLADOS}")
    parser.add_argument("universidades", nargs="*", help="Nombres cortos; todas las de FOLLETOS si se omite")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if args.apply:
        planes = json.loads(HALLADOS.read_text())
    else:
        planes = leer(client, set(args.universidades))
        HALLADOS.write_text(json.dumps(planes, ensure_ascii=False, indent=1) + "\n")

    filas = []
    for plan in planes.values():
        carrera = plan["carrera"]
        print(f"{plan['universidad']:8} {carrera['nombre_carrera'][:48]:48} {len(plan['materias']):3} "
              f"{dict(Counter(anio for _, anio in plan['materias']))}", flush=True)
        vistas: set[str] = set()
        for materia, anio in plan["materias"]:
            if materia.lower() not in vistas:
                vistas.add(materia.lower())
                filas.append({"universidad_id": carrera["universidad_id"], "carrera_id": carrera["id"],
                              "nombre_materia": materia, "anio_cursada": anio})
    if args.apply and filas:
        for inicio in range(0, len(filas), 500):
            client.table("materias").insert(filas[inicio:inicio + 500]).execute()
        pd.guardar_las_fuentes(planes.values())
    print(f"Planes: {len(planes)}; materias {'cargadas' if args.apply else 'a cargar'}: {len(filas)}", flush=True)


if __name__ == "__main__":
    main()
