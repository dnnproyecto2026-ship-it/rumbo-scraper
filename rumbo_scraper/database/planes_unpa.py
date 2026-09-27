"""The plans of the Universidad Nacional de la Patagonia Austral.

Its catalogue answers from a public service: the list of careers
(``controladorCarreras.php?opcion=listado``), each career's plan in force
(``opcion=infoCarrera&id=69`` -> ``pdf_plan: IPR07``), and the plan itself
(``descargarPlan.php?plan=IPR07``), a page that carries the PDF as base64:

    PRIMER AÑO
    1527 Química General 1ºC 8
    0901 Análisis y Producción del Discurso A 2

    python -m rumbo_scraper.database.planes_unpa [--apply]
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import re
from collections import Counter
from pathlib import Path

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.parsers import guias_nacionales as gn
from rumbo_scraper.parsers.planes_sitios import _agregar, anio_de, desde_el_primero

BASE = "https://propuestaacademica.unpa.edu.ar/controladores/"
PLANES = Path("data/unpa_planes.json")
_FILA = re.compile(r"^\d{4}\s+(.+?)\s+(?:A|C|\dºC)\s+\d+(?:\s|$)")
_FIN = re.compile(r"(?i)^(?:\(\*|otros requisitos|optativas|grupo de optativas|espacios curriculares optativos)")


def pdf_de_la_pagina(html: str) -> bytes | None:
    """The PDF a page carries as ``pdfAsDataUri = '...'``."""
    datos = re.search(r"pdfAsDataUri\s*=\s*'([A-Za-z0-9+/=\s]+)'", html or "")
    try:
        return base64.b64decode(re.sub(r"\s+", "", datos.group(1))) if datos else None
    except ValueError:
        return None


def leer_plan(texto: str) -> list[tuple[str, int]]:
    materias: list[tuple[str, int]] = []
    anio = None
    for linea in (texto or "").splitlines():
        linea = clean_text(linea)
        if _FIN.match(linea):
            break
        nuevo = anio_de(linea)
        if nuevo:
            anio = nuevo
            continue
        fila = _FILA.match(linea)
        if fila and anio:
            _agregar(materias, re.sub(r"\s*\(\*+\)", "", fila.group(1)), anio)
    return desde_el_primero(materias)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar los planes de la UNPA")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    import pdfplumber

    from rumbo_scraper.database.planes_documentos import _parece_el_plan_entero
    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    from rumbo_scraper.spiders.visitante import Visitante

    client = get_supabase_client()
    universidad = client.table("universidades").select("id").eq("nombre_corto", "UNPA").execute().data[0]["id"]
    carreras = {comparison_key(c["nombre_carrera"]): c for c in select_all(client.table("carreras").select(
        "id,nombre_carrera,duracion_anios").eq("universidad_id", universidad))}
    con_materias = {m["carrera_id"] for m in select_all(
        client.table("materias").select("carrera_id").eq("universidad_id", universidad))}

    filas, publicados, vistas = [], [], set()
    with Visitante(timeout=40) as visitante:
        listado = visitante.client.get(BASE + "controladorCarreras.php?opcion=listado").json().get("data") or []
        for item in listado:
            guia = gn._carrera(item.get("nombre") or "", "", BASE)
            carrera = carreras.get(comparison_key(guia.nombre)) if guia else None
            if not carrera or carrera["id"] in vistas:
                continue
            vistas.add(carrera["id"])
            info = visitante.client.get(BASE + f"controladorCarreras.php?opcion=infoCarrera&id={item['id']}").json()
            plan = next((i.get("pdf_plan") for i in info or [] if i.get("pdf_plan")), None)
            if not plan:
                continue
            url = BASE + f"descargarPlan.php?plan={plan}&nombre=plan"
            contenido = pdf_de_la_pagina(visitante.client.get(url).text)
            if not contenido:
                continue
            with pdfplumber.open(io.BytesIO(contenido)) as pdf:
                materias = leer_plan("\n".join((p.extract_text() or "") for p in pdf.pages))
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
