"""The plans of CABA's state technical institutes (IFTS), from the Agencia de
Aprendizaje's own record of each career.

The Agencia's service (``terciarios.CABA_IFTS``, where the IFTS and their
careers were loaded from) gives each career at each IFTS a ``planEstudio``:
the plan, a PDF the Agencia keeps on Drive. It is read by
one of the IFTS readers of ``planes_sitios`` (by code, by number, a table
whose hours add up to the plan's declared total, under year-and-term
headings, or a table of units without years) and taken only when it reads
as the whole plan; one read without its rows' numbers, only when each name
is a whole cell of the document. The verifier reads the
same PDF because the career's record in that service links it.

    python -m rumbo_scraper.database.planes_ifts_caba [--apply]
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import time
from collections import Counter
from typing import Any

from rumbo_scraper.database.planes_documentos import (CACHE, _FUERA_DEL_PLAN, _parece_el_plan_entero,
                                                      guardar_las_fuentes)
from rumbo_scraper.database.terciarios import CABA_IFTS, nombre_de_la_carrera
from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.parsers import planes_sitios

PAUSA = 1.0


def documento_del_plan(enlace: str | None) -> str | None:
    """The address a Drive file downloads from, for its viewer's link."""
    en_drive = re.search(r"drive\.google\.com/file/d/([\w-]+)", enlace or "")
    return f"https://drive.google.com/uc?export=download&id={en_drive.group(1)}" if en_drive else None


def leer_plan(visitante: Any, documento: str, carrera: str) -> list[tuple[str, int | None]]:
    archivo = CACHE / (hashlib.md5(documento.encode()).hexdigest() + ".pdf")
    if not archivo.exists() or archivo.stat().st_size < 1000:
        respuesta = visitante.client.get(documento, follow_redirects=True)
        archivo.write_bytes(respuesta.content if respuesta.status_code == 200 else b"")
        time.sleep(PAUSA)
    texto = subprocess.run(["pdftotext", "-layout", str(archivo), "-"], capture_output=True, text=True,
                           timeout=300).stdout
    # The rows numbered by code or number check themselves; a plan read
    # without numbers is taken only when each name is a whole cell of the
    # document.
    leidas = planes_sitios.plan_codigos_ifts(texto) or planes_sitios.plan_numerado_ifts(texto)
    if not leidas:
        sin_columnas = subprocess.run(["pdftotext", str(archivo), "-"], capture_output=True, text=True,
                                      timeout=300).stdout
        # A table whose hours add up to the plan's declared total, its names
        # whole cells; else one read without numbers, its names whole cells.
        leidas = planes_sitios.plan_horas_ifts(texto, sin_columnas)
        if not leidas:
            leidas = planes_sitios.plan_anio_cuatrimestre_ifts(texto) or planes_sitios.plan_instancias_ifts(texto)
            if not planes_sitios.nombres_en_celdas(leidas, sin_columnas):
                return []
    materias = [(n, a) for n, a in leidas if not _FUERA_DEL_PLAN.search(n)]
    return materias if _parece_el_plan_entero(carrera, materias, None) else []


def main() -> None:
    parser = argparse.ArgumentParser(description="Planes de los IFTS de CABA según la Agencia de Aprendizaje")
    parser.add_argument("--apply", action="store_true", help="Escribir las materias en Supabase")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    from rumbo_scraper.spiders.visitante import Visitante

    client = get_supabase_client()
    universidades = {u["nombre_corto"]: u for u in select_all(
        client.table("universidades").select("id,nombre_corto")) if (u["nombre_corto"] or "").startswith("IFTS ")}
    con_materias = {m["carrera_id"] for m in select_all(client.table("materias").select("carrera_id"))}
    carreras = {(c["universidad_id"], comparison_key(c["nombre_carrera"])): c
                for c in select_all(client.table("carreras").select("id,universidad_id,nombre_carrera"))}
    planes, filas, cuenta = [], [], Counter()
    with Visitante(timeout=60) as visitante:
        for oferta in visitante.client.get(CABA_IFTS, headers={"Accept": "application/json"}).json():
            numero = re.search(r"(\d+)", oferta.get("lugar") or "")
            universidad = universidades.get(f"IFTS {numero.group(1)}") if numero else None
            nombre = nombre_de_la_carrera(oferta.get("name") or "")
            carrera = carreras.get((universidad["id"], comparison_key(nombre))) if universidad and nombre else None
            documento = documento_del_plan(oferta.get("planEstudio"))
            if not (carrera and documento) or carrera["id"] in con_materias:
                cuenta["sin carrera, sin plan o ya con materias"] += 1
                continue
            materias = leer_plan(visitante, documento, carrera["nombre_carrera"])
            cuenta["leído" if materias else "no se lee"] += 1
            print(f"{universidad['nombre_corto']:8} {carrera['nombre_carrera'][:60]:60} {len(materias):3} "
                  f"{dict(Counter(a for _, a in materias))}", flush=True)
            if not materias:
                continue
            con_materias.add(carrera["id"])
            planes.append({"universidad": universidad["nombre_corto"], "documento": documento,
                           "carrera": {"nombre_carrera": carrera["nombre_carrera"]}})
            filas += [{"universidad_id": universidad["id"], "carrera_id": carrera["id"],
                       "nombre_materia": n, "anio_cursada": a} for n, a in materias]
    if args.apply and filas:
        for inicio in range(0, len(filas), 500):
            client.table("materias").insert(filas[inicio:inicio + 500]).execute()
        guardar_las_fuentes(planes)
    print(f"{dict(cuenta)}; planes: {len(planes)}; materias {'cargadas' if args.apply else 'a cargar'}: {len(filas)}")


if __name__ == "__main__":
    main()
