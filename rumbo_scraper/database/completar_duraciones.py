"""Give each career without a duration the one its own page states.

568 of the application's offers say nothing of how long the career takes:
the reader that found them read the list of careers, not the career's page.
This reads that page with `parsers.duracion`, which only answers when the
page states one duration, and only if the page is the career's own
(`es_la_pagina_de`): the UBA's careers point at their faculty's list, and a
list states many durations.

Nothing is overwritten: only careers with no duration are touched. The
preview keeps what it found in ``data/duraciones_halladas.json``;
``--apply`` writes from that file, reading nothing again.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from rumbo_scraper.database.completar_unidades import _NO_ES_SU_PAGINA
from rumbo_scraper.database.exportar_catalogo import _urls_de_los_artefactos
from rumbo_scraper.parsers.duracion import duracion_de_la_pagina
from rumbo_scraper.parsers.unidad import es_la_pagina_de
from rumbo_scraper.spiders.visitante import Visitante

PAUSA = 0.8


# --- The duration its plan of studies gives a grado career -----------------
#
# A plan that lists every year from the first to the Nth, the last a full
# year, is a career of N years: it is the university's own plan saying it.
# Where the database also has a stated duration the two agree 95 times in a
# hundred; where they differ by two years or more the stated one is the
# mistake (Farmacia and Arquitectura stored as two-year careers, with five
# and six full years of subjects). A tecnicatura is left out: one of two
# and a half years has subjects in its "third year". So is a last year with
# far fewer subjects than the others, which is a thesis or a closing block,
# not a year of classes.

ULTIMO_ANIO_COMPLETO = 0.6


def duracion_del_plan(por_anio: dict[int, int]) -> int | None:
    """The years a grado plan runs, from how many subjects each year has."""
    import statistics

    if not por_anio:
        return None
    ultimo = max(por_anio)
    if not 4 <= ultimo <= 6 or any(not por_anio.get(anio) for anio in range(1, ultimo + 1)):
        return None
    tipico = statistics.median(por_anio[anio] for anio in range(1, ultimo))
    return ultimo if por_anio[ultimo] >= ULTIMO_ANIO_COMPLETO * tipico else None


def desde_los_planes(client: Any, solo: set[str] = frozenset()) -> list[dict[str, Any]]:
    """The careers whose duration their plan gives: those with none, and
    those whose stored one the plan contradicts by two years or more."""
    from rumbo_scraper.database.supabase import select_all

    universidades = {u["id"]: u for u in select_all(client.table("universidades").select("*"))
                     if not solo or u.get("nombre_corto") in solo}
    carreras = {c["id"]: c for c in select_all(client.table("carreras").select(
        "id,universidad_id,nombre_carrera,nivel,duracion_anios"))
        if c["universidad_id"] in universidades and c["nivel"] == "Grado"}
    por_carrera: dict[str, Counter] = {}
    for materia in select_all(client.table("materias").select("carrera_id,anio_cursada")):
        if materia["carrera_id"] in carreras and materia["anio_cursada"]:
            por_carrera.setdefault(materia["carrera_id"], Counter())[materia["anio_cursada"]] += 1
    halladas = []
    for carrera_id, por_anio in por_carrera.items():
        carrera = carreras[carrera_id]
        duracion = duracion_del_plan(por_anio)
        guardada = carrera["duracion_anios"]
        if duracion is None or (guardada and abs(float(guardada) - duracion) < 2):
            continue
        halladas.append({"carrera_id": carrera_id,
                         "universidad": universidades[carrera["universidad_id"]].get("nombre_corto"),
                         "carrera": carrera["nombre_carrera"], "duracion": duracion,
                         "antes": guardada, "url": "plan de estudios"})
    return halladas
HALLADAS = Path("data/duraciones_halladas.json")


def leer(client: Any, solo: set[str] = frozenset()) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all

    universidades = {u["id"]: u for u in select_all(client.table("universidades").select("*"))
                     if not solo or u.get("nombre_corto") in solo}
    carreras = [c for c in select_all(client.table("carreras").select(
        "id,universidad_id,nombre_carrera,duracion_anios")) if c["universidad_id"] in universidades]
    artefactos = _urls_de_los_artefactos()
    url_de = {c["id"]: artefactos.get((universidades[c["universidad_id"]]["nombre_oficial"],
                                       c["nombre_carrera"])) for c in carreras}
    for oferta in select_all(client.table("ofertas_academicas").select("carrera_id,url_oficial")):
        if oferta["url_oficial"] and oferta["carrera_id"] in url_de:
            url_de[oferta["carrera_id"]] = oferta["url_oficial"]

    halladas = []
    with Visitante(timeout=25) as visitante:
        for carrera in carreras:
            url = url_de.get(carrera["id"])
            if carrera["duracion_anios"] or not url or _NO_ES_SU_PAGINA.search(url):
                continue
            html = visitante.get(url)
            time.sleep(PAUSA)
            if not es_la_pagina_de(html, carrera["nombre_carrera"]):
                continue
            duracion = duracion_de_la_pagina(html)
            if duracion is None:
                continue
            corto = universidades[carrera["universidad_id"]].get("nombre_corto") or ""
            print(f"{corto:9} | {carrera['nombre_carrera'][:55]:55} | {duracion}", flush=True)
            halladas.append({"carrera_id": carrera["id"], "universidad": corto,
                             "carrera": carrera["nombre_carrera"], "duracion": duracion,
                             "url": url})
    return halladas


def main() -> None:
    parser = argparse.ArgumentParser(description="Completar la duración de las carreras")
    parser.add_argument("--apply", action="store_true",
                        help=f"Escribir en Supabase lo que dejó la vista previa en {HALLADAS}")
    parser.add_argument("universidades", nargs="*", help="Nombres cortos; todas si se omite")
    parser.add_argument("--desde-el-plan", action="store_true",
                        help="La duración que da el plan de estudios, no la página")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if args.apply:
        halladas = json.loads(HALLADAS.read_text())
        for h in halladas:
            cambio = client.table("carreras").update({"duracion_anios": h["duracion"]}).eq(
                "id", h["carrera_id"])
            # Only a duration the plan contradicts by two years is replaced.
            if h.get("antes") is None:
                cambio = cambio.is_("duracion_anios", "null")
            cambio.execute()
        print(f"Carreras con duración: {len(halladas)}")
        return

    if args.desde_el_plan:
        halladas = desde_los_planes(client, set(args.universidades))
        for h in halladas:
            print(f"{h['universidad']:9} | {h['carrera'][:55]:55} | {h['antes']} → {h['duracion']}")
    else:
        halladas = leer(client, set(args.universidades))
    HALLADAS.write_text(json.dumps(halladas, ensure_ascii=False, indent=1) + "\n")
    print(f"Con duración: {len(halladas)} {dict(Counter(h['universidad'] for h in halladas))}"
          f" — vista previa en {HALLADAS}", flush=True)


if __name__ == "__main__":
    main()
