"""The plans of the tertiary institutes, from their province's curricular
designs.

An institute of teacher training does not publish its plan: the province
does. Its curricular design for a career (the Province of Buenos Aires'
"Diseño Curricular Profesorado de Educación Secundaria en Matemática") is
the plan every institute of the province that gives the career follows, by
resolution. So one design is the plan of each of them: the career of that
name at every institute of the province's registry
(``relevamiento/terciarios.json``) that has no plan yet.

A design is read by its own reader (``planes_sitios.plan_diseno_pba``: the
"Estructura curricular" table, a row per unit and year) and taken only when
it reads as the whole plan. The design's address is kept as each plan's
source (``data/<institute>_planes.json``), where the verifier checks each
unit against it.

    python -m rumbo_scraper.database.planes_disenos [--apply]
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import subprocess
import time
from collections import Counter
from typing import Any

from rumbo_scraper.database.planes_documentos import (CACHE, _FUERA_DEL_PLAN, _parece_el_plan_entero,
                                                      guardar_las_fuentes)
from rumbo_scraper.database.terciarios import REGISTRO
from rumbo_scraper.parsers import planes_sitios

_PBA = "https://abc.gob.ar/secretarias/sites/default/files/"
_SECUNDARIA = "Profesorado de Educación Secundaria en "
_INICIAL_Y_PRIMARIA = _PBA + ("2021-05/Dise%C3%B1o%20Curricular%20Profesorado%20de%20Educaci%C3%B3n%20Inicial"
                              "%20y%20primaria.pdf")
# The designs in force (the Dirección de Formación Docente Inicial's page
# "Diseño y desarrollo curricular"), by the career's name as the province's
# school map gives it.
DISENOS: dict[str, dict[str, tuple[str, Any]]] = {
    "Buenos Aires": {
        _SECUNDARIA + "Matemática": (_PBA + "2026-08/Matem%C3%A1tica.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Lengua y Literatura": (_PBA + "2026-08/Lengua%20y%20literatura.pdf",
                                              planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Biología": (_PBA + "2024-03/Biolog%C3%ADa.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Economía": (_PBA + "2024-03/Economia.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Geografía": (_PBA + "2024-03/Geograf%C3%ADa.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Química": (_PBA + "2024-03/Qu%C3%ADmica_0.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Física": (_PBA + "2024-03/F%C3%ADsica.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Filosofía": (_PBA + "2024-03/FILOSOF%C3%8DA.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Ciencia Política": (_PBA + "2024-03/C.%20Politica.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Historia": (_PBA + "2024-03/Historia_0.pdf", planes_sitios.plan_diseno_pba),
        "Profesorado de Educación Inicial": (_INICIAL_Y_PRIMARIA,
                                             functools.partial(planes_sitios.plan_indice_pba, "Educación Inicial")),
        "Profesorado de Educación Primaria": (_INICIAL_Y_PRIMARIA,
                                              functools.partial(planes_sitios.plan_indice_pba, "Educación Primaria")),
    },
}
PAUSA = 2.0


def leer_diseno(visitante: Any, url: str, lector: Any, carrera: str) -> list[tuple[str, int]]:
    """The design's plan, or none when it does not read as the whole plan."""
    archivo = CACHE / (hashlib.md5(url.encode()).hexdigest() + ".pdf")
    if not archivo.exists() or archivo.stat().st_size < 1000:
        respuesta = visitante.client.get(url)
        archivo.write_bytes(respuesta.content if respuesta.status_code == 200 else b"")
        time.sleep(PAUSA)
    modo = "-bbox-layout" if getattr(lector, "cajas", False) else "-layout"
    texto = subprocess.run(["pdftotext", modo, str(archivo), "-"], capture_output=True, text=True,
                           timeout=300).stdout
    materias, vistas = [], set()
    for nombre, anio in lector(texto):
        if not _FUERA_DEL_PLAN.search(nombre) and nombre.lower() not in vistas:
            vistas.add(nombre.lower())
            materias.append((nombre, anio))
    return materias if _parece_el_plan_entero(carrera, materias, None) else []


def main() -> None:
    parser = argparse.ArgumentParser(description="Planes de los terciarios según el diseño curricular de su provincia")
    parser.add_argument("--apply", action="store_true", help="Escribir las materias en Supabase")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    from rumbo_scraper.spiders.visitante import Visitante

    client = get_supabase_client()
    registro = json.loads(REGISTRO.read_text())
    universidades = {u["id"]: u for u in select_all(client.table("universidades").select("id,nombre_oficial,nombre_corto"))}
    con_materias = {m["carrera_id"] for m in select_all(client.table("materias").select("carrera_id")) if m["carrera_id"]}
    carreras = select_all(client.table("carreras").select("id,universidad_id,nombre_carrera"))
    planes, filas = [], []
    with Visitante(timeout=180) as visitante:
        for provincia, disenos in DISENOS.items():
            institutos = {i for i, u in universidades.items()
                          if (registro.get(u["nombre_oficial"]) or {}).get("jurisdiccion") == provincia}
            for carrera_nombre, (url, lector) in disenos.items():
                materias = leer_diseno(visitante, url, lector, carrera_nombre)
                destino = [c for c in carreras if c["universidad_id"] in institutos
                           and c["nombre_carrera"] == carrera_nombre and c["id"] not in con_materias]
                print(f"{provincia:14} {carrera_nombre[:55]:55} {len(materias):3} materias "
                      f"{dict(Counter(a for _, a in materias))} -> {len(destino)} institutos", flush=True)
                if not materias:
                    continue
                for carrera in destino:
                    universidad = universidades[carrera["universidad_id"]]
                    planes.append({"universidad": universidad["nombre_corto"], "documento": url,
                                   "carrera": {"nombre_carrera": carrera_nombre}})
                    filas += [{"universidad_id": carrera["universidad_id"], "carrera_id": carrera["id"],
                               "nombre_materia": nombre, "anio_cursada": anio} for nombre, anio in materias]
    if args.apply and filas:
        for inicio in range(0, len(filas), 500):
            client.table("materias").insert(filas[inicio:inicio + 500]).execute()
        guardar_las_fuentes(planes)
    print(f"Planes: {len(planes)}; materias {'cargadas' if args.apply else 'a cargar'}: {len(filas)}")


if __name__ == "__main__":
    main()
