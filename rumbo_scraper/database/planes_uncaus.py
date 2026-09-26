"""The plans of the Universidad Nacional del Chaco Austral, from its catalogue.

The site is built in the browser from a piece of its script that holds every
career with its plans (`parsers.guias_nacionales.planes_uncaus`). This loads
the plan in force of each career that has no subjects yet, and records in
``data/uncaus_planes.json`` where each plan was read, for the verifier.

    python -m rumbo_scraper.database.planes_uncaus [--apply]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.parsers import guias_nacionales as gn

PLANES = Path("data/uncaus_planes.json")
# More than this many in a year is a pool of electives, not the year.
MAS_POR_ANIO = 20


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar los planes de la UNCAUS")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    from rumbo_scraper.spiders.visitante import Visitante

    with Visitante(timeout=30) as visitante:
        def traer(url: str) -> str:
            return visitante.client.get(url).text if url.endswith(".js") else visitante.get(url)

        catalogo = gn.catalogo_uncaus(traer)
        if not catalogo:
            print("No se encontró el catálogo de la UNCAUS.")
            return
        js = traer(catalogo)
    titulos = {slug: nombre for slug, nombre, _, _ in gn._CARRERA_UNCAUS.findall(js)}
    planes = gn.planes_uncaus(js)

    client = get_supabase_client()
    universidad = client.table("universidades").select("id").eq("nombre_corto", "UNCAUS").execute().data[0]["id"]
    carreras = {comparison_key(c["nombre_carrera"]): c for c in select_all(
        client.table("carreras").select("id,nombre_carrera").eq("universidad_id", universidad))}
    con_materias = {m["carrera_id"] for m in select_all(
        client.table("materias").select("carrera_id").eq("universidad_id", universidad))}

    filas, publicados = [], []
    for slug, materias in planes.items():
        carrera = carreras.get(comparison_key(titulos.get(slug) or ""))
        por_anio = Counter(anio for _, anio in materias)
        if not carrera or max(por_anio.values()) > MAS_POR_ANIO:
            print(f"  sin cargar: {slug}")
            continue
        publicados.append({"nombre": carrera["nombre_carrera"], "url": catalogo})
        if carrera["id"] in con_materias:
            continue
        print(f"  {carrera['nombre_carrera'][:50]:50} {len(materias):3} {dict(por_anio)}")
        filas += [{"universidad_id": universidad, "carrera_id": carrera["id"],
                   "nombre_materia": nombre, "anio_cursada": anio} for nombre, anio in materias]

    PLANES.write_text(json.dumps({"planes": publicados}, ensure_ascii=False, indent=1) + "\n")
    if args.apply and filas:
        for inicio in range(0, len(filas), 500):
            client.table("materias").insert(filas[inicio:inicio + 500]).execute()
    print(f"Planes: {len(publicados)}; materias {'cargadas' if args.apply else 'a cargar'}: {len(filas)}")


if __name__ == "__main__":
    main()
