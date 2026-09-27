"""The plans of the Universidad Católica de Cuyo, from the PDF of each career.

The home's Inertia data gives each career its plan as a PDF
(``storage/planes-estudios/..._Contador Publico.pdf``), all laid out alike:

    1° Año Unidad Curricular
    1° Semestre Filosofía
    Introducción a las Ciencias Sociales
    Anual Contabilidad

This loads the plan of each career that has no subjects yet, when it passes
the same checks as any plan read from a document, and records in
``data/uccuyo_planes.json`` where each was read, for the verifier.

    python -m rumbo_scraper.database.planes_uccuyo [--apply]
"""

from __future__ import annotations

import argparse
import html as entidades
import io
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.parsers import guias_nacionales as gn
from rumbo_scraper.parsers.planes_sitios import _agregar, desde_el_primero

PLANES = Path("data/uccuyo_planes.json")
_ANIO = re.compile(r"^(\d)\s*°\s*Año\b")
_PERIODO = re.compile(r"^(?:\d°\s*(?:Semestre|Cuatrimestre)|Anual|Semestral|Cuatrimestral)\s*")
_FUERA = re.compile(r"(?i)^(?:t[íi]tulo|resoluci[óo]n)\s*:|^unidad curricular$")


def leer_plan(texto: str) -> list[tuple[str, int]]:
    materias: list[tuple[str, int]] = []
    anio, anterior = None, ""
    renglones = []
    for linea in (texto or "").splitlines():
        linea = clean_text(linea)
        encabezado = _ANIO.match(linea)
        if encabezado:
            anio = int(encabezado.group(1))
            continue
        linea = _PERIODO.sub("", linea).strip()
        if not linea or _FUERA.search(linea) or not anio:
            continue
        # A name the cell wrapped: the line goes on lower case, or the one
        # before ended on a joining word.
        if renglones and (linea[0].islower() or re.search(r"(?i)\s(y|de|del|e|la|en)$", anterior)):
            renglones[-1] = (f"{renglones[-1][0]} {linea}", renglones[-1][1])
        else:
            renglones.append((linea, anio))
        anterior = renglones[-1][0]
    for nombre, anio_ in renglones:
        _agregar(materias, nombre, anio_)
    return desde_el_primero(materias)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar los planes de la UCCuyo")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    import pdfplumber

    from rumbo_scraper.database.planes_documentos import _parece_el_plan_entero
    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    from rumbo_scraper.spiders.visitante import Visitante

    client = get_supabase_client()
    universidad = client.table("universidades").select("id").eq("nombre_corto", "UCCuyo").execute().data[0]["id"]
    carreras = {comparison_key(c["nombre_carrera"]): c for c in select_all(client.table("carreras").select(
        "id,nombre_carrera,duracion_anios").eq("universidad_id", universidad))}
    con_materias = {m["carrera_id"] for m in select_all(
        client.table("materias").select("carrera_id").eq("universidad_id", universidad))}

    filas, publicados, vistas = [], [], set()
    with Visitante(timeout=40) as visitante:
        datos = re.search(r'data-page="([^"]+)"', visitante.get(gn.UCCUYO) or "")
        sedes = json.loads(entidades.unescape(datos.group(1)))["props"].get("universidades") or [] if datos else []
        for sede in sedes:
            for facultad in sede.get("facultades") or []:
                for item in facultad.get("carreras") or []:
                    guia = gn._carrera(item.get("nombre") or "", "", gn.UCCUYO)
                    carrera = carreras.get(comparison_key(guia.nombre)) if guia else None
                    ruta = item.get("plan_estudio")
                    if not carrera or not ruta or carrera["id"] in vistas:
                        continue
                    vistas.add(carrera["id"])
                    url = gn.UCCUYO + quote(ruta)
                    try:
                        respuesta = visitante.client.get(url)
                        with pdfplumber.open(io.BytesIO(respuesta.content)) as pdf:
                            texto = "\n".join((p.extract_text() or "") for p in pdf.pages)
                    except Exception:
                        continue
                    materias = leer_plan(texto)
                    if not _parece_el_plan_entero(carrera["nombre_carrera"], materias, carrera.get("duracion_anios")):
                        print(f"  no parece el plan entero: {carrera['nombre_carrera']} ({len(materias)})")
                        continue
                    publicados.append({"nombre": carrera["nombre_carrera"], "url": url})
                    if carrera["id"] in con_materias:
                        continue
                    print(f"  {carrera['nombre_carrera'][:50]:50} {len(materias):3} "
                          f"{dict(Counter(a for _, a in materias))}")
                    filas += [{"universidad_id": universidad, "carrera_id": carrera["id"],
                               "nombre_materia": nombre, "anio_cursada": anio} for nombre, anio in materias]

    PLANES.write_text(json.dumps({"planes": publicados}, ensure_ascii=False, indent=1) + "\n")
    if args.apply and filas:
        for inicio in range(0, len(filas), 500):
            client.table("materias").insert(filas[inicio:inicio + 500]).execute()
    print(f"Planes: {len(publicados)}; materias {'cargadas' if args.apply else 'a cargar'}: {len(filas)}")


if __name__ == "__main__":
    main()
