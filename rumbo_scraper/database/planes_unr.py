"""The plans of the UNR's Facultad de Ciencias Económicas y Estadística.

Its site is built in the browser from a public service that gives each
career's subjects with their code, the year first ("2.08.1": second year,
eighth subject, first term):

    admin.fceyeua.fcecon.unr.edu.ar/api/paginaweb/slug/getcontenido?slug=carreras/grado/contador-publico

    python -m rumbo_scraper.database.planes_unr [--apply]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.parsers.planes_sitios import _agregar, desde_el_primero

SERVICIO = "https://admin.fceyeua.fcecon.unr.edu.ar/api/paginaweb/slug/getcontenido?slug=carreras/grado/{}"
CARRERAS = ("contador-publico", "licenciatura-en-administracion", "licenciatura-en-economia",
            "licenciatura-en-estadistica", "licenciatura-en-turismo")
PLANES = Path("data/unr_planes.json")


def leer_plan(datos: dict) -> list[tuple[str, int]]:
    materias: list[tuple[str, int]] = []
    for materia in sorted(datos.get("materias") or [], key=lambda m: m.get("cod_materia") or ""):
        codigo = (materia.get("cod_materia") or "").split(".")
        if codigo[0].isdigit():
            _agregar(materias, materia.get("nombre") or "", int(codigo[0]))
    return desde_el_primero(materias)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar los planes de Económicas de la UNR")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    from rumbo_scraper.database.planes_documentos import _parece_el_plan_entero
    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    from rumbo_scraper.spiders.visitante import Visitante

    client = get_supabase_client()
    universidad = client.table("universidades").select("id").eq("nombre_corto", "UNR").execute().data[0]["id"]
    carreras = {comparison_key(c["nombre_carrera"]): c for c in select_all(client.table("carreras").select(
        "id,nombre_carrera,duracion_anios").eq("universidad_id", universidad))}
    con_materias = {m["carrera_id"] for m in select_all(
        client.table("materias").select("carrera_id").eq("universidad_id", universidad))}

    filas = []
    publicados = json.loads(PLANES.read_text()).get("planes", []) if PLANES.exists() else []
    with Visitante(timeout=40) as visitante:
        for slug in CARRERAS:
            url = SERVICIO.format(slug)
            try:
                datos = visitante.client.get(url).json()
            except Exception:
                continue
            carrera = carreras.get(comparison_key(datos.get("nombre_carrera") or ""))
            materias = leer_plan(datos)
            if not carrera or not _parece_el_plan_entero(carrera["nombre_carrera"], materias,
                                                         carrera.get("duracion_anios")):
                print(f"  sin cargar: {slug} ({datos.get('nombre_carrera')}, {len(materias)})")
                continue
            if not any(p["nombre"] == carrera["nombre_carrera"] for p in publicados):
                publicados.append({"nombre": carrera["nombre_carrera"], "url": url})
            if carrera["id"] in con_materias:
                continue
            print(f"  {carrera['nombre_carrera'][:50]:50} {len(materias):3} "
                  f"{dict(Counter(a for _, a in materias))}")
            filas += [{"universidad_id": universidad, "carrera_id": carrera["id"],
                       "nombre_materia": nombre, "anio_cursada": anio} for nombre, anio in materias]

    PLANES.write_text(json.dumps({"planes": publicados}, ensure_ascii=False, indent=1) + "\n")
    if args.apply and filas:
        client.table("materias").insert(filas).execute()
    print(f"Planes: {len(publicados)}; materias {'cargadas' if args.apply else 'a cargar'}: {len(filas)}")


if __name__ == "__main__":
    main()
