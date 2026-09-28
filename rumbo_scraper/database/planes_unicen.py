"""The plans of UNICEN's Facultad de Ciencias Exactas, from its own site.

The UNICEN's careers point at the university's pages, which do not link the
plan. The faculty's site (exa.unicen.edu.ar) has a page per career, linked by
name from its list of careers, and lays the plan out as a table: a cell per
subject (a long name wraps inside it: "Ecuaciones Diferenciales<br>
Ordinarias"), a heading per year in its own cell ("<h4>Tercer Año</h4>"), the
terms' headings ("<h5>Primer Cuatrimestre</h5>") between. A page showing the
current plan and the one before starts the years again: the first is taken.
An elective's slot ("Formativa Técnica (Optativa)") is not a subject.

Only careers with no subjects are given one, and only a plan
`planes_documentos` takes as whole. The preview keeps its own file.

    python -m rumbo_scraper.database.planes_unicen
    python -m rumbo_scraper.database.planes_unicen --apply
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from rumbo_scraper.database import planes_documentos as pd
from rumbo_scraper.parsers.guias_nacionales import pagina_de_la_carrera, paginas_por_nombre
from rumbo_scraper.parsers.planes_sitios import _agregar, _texto, anio_de, desde_el_primero

LISTADO = "https://exa.unicen.edu.ar/carreras/"
HALLADOS = Path("data/planes_unicen.json")


def plan_por_celdas(html: str) -> list[tuple[str, int]]:
    materias: list[tuple[str, int]] = []
    anio = None
    for celda in BeautifulSoup(html or "", "html.parser").find_all("td"):
        titulo = celda.find(["h2", "h3", "h4"])
        if titulo and anio_de(_texto(titulo)):
            nuevo = anio_de(_texto(titulo))
            # The plan before the current one starts its years again.
            if anio and nuevo < anio:
                break
            anio = nuevo
            continue
        if not anio or celda.find(["h5", "h6"]):
            continue
        nombre = " ".join(celda.get_text(" ").split())
        if not re.search(r"(?i)\(optativa\)|\(electiva\)", nombre):
            _agregar(materias, nombre, anio)
    return desde_el_primero(materias)


def leer(client: Any) -> dict[str, dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all
    from rumbo_scraper.spiders.visitante import Visitante

    universidad = client.table("universidades").select("*").eq("nombre_corto", "UNICEN").execute().data[0]
    carreras = select_all(client.table("carreras").select("id,universidad_id,nombre_carrera,nivel,duracion_anios")
                          .eq("universidad_id", universidad["id"]))
    con_materias = {m["carrera_id"] for m in select_all(
        client.table("materias").select("carrera_id").in_("carrera_id", [c["id"] for c in carreras]))}
    planes: dict[str, dict[str, Any]] = {}
    with Visitante(timeout=30) as visitante:
        paginas = {nombre: url for nombre, url in paginas_por_nombre(visitante.get(LISTADO), LISTADO).items()
                   if url.startswith("https://exa.unicen.edu.ar/")}
        for carrera in carreras:
            if carrera["id"] in con_materias:
                continue
            url = pagina_de_la_carrera(carrera["nombre_carrera"], paginas)
            if not url:
                continue
            materias = plan_por_celdas(visitante.get(url))
            time.sleep(pd.PAUSA)
            if pd._parece_el_plan_entero(carrera["nombre_carrera"], materias, carrera.get("duracion_anios")):
                planes[carrera["id"]] = {"carrera": carrera, "materias": materias, "documento": url,
                                         "universidad": "UNICEN"}
    # One page given to two careers is neither's plan.
    usos = Counter(p["documento"] for p in planes.values())
    return {cid: p for cid, p in planes.items() if usos[p["documento"]] == 1}


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar los planes de Exactas de la UNICEN")
    parser.add_argument("--apply", action="store_true", help=f"Escribir lo que dejó la vista previa en {HALLADOS}")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    planes = json.loads(HALLADOS.read_text()) if args.apply else leer(client)
    if not args.apply:
        HALLADOS.write_text(json.dumps(planes, ensure_ascii=False, indent=1) + "\n")
    filas = []
    for plan in planes.values():
        carrera = plan["carrera"]
        print(f"{carrera['nombre_carrera'][:55]:55} {len(plan['materias']):3} "
              f"{dict(Counter(anio for _, anio in plan['materias']))}", flush=True)
        for materia, anio in plan["materias"]:
            filas.append({"universidad_id": carrera["universidad_id"], "carrera_id": carrera["id"],
                          "nombre_materia": materia, "anio_cursada": anio})
    if args.apply and filas:
        client.table("materias").insert(filas).execute()
        pd.guardar_las_fuentes(planes.values())
    print(f"Planes: {len(planes)}; materias {'cargadas' if args.apply else 'a cargar'}: {len(filas)}", flush=True)


if __name__ == "__main__":
    main()
