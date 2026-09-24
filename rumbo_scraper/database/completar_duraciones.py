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
HALLADAS = Path("data/duraciones_halladas.json")


def leer(client: Any) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all

    universidades = {u["id"]: u for u in select_all(client.table("universidades").select("*"))}
    carreras = select_all(client.table("carreras").select(
        "id,universidad_id,nombre_carrera,duracion_anios"))
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
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if args.apply:
        halladas = json.loads(HALLADAS.read_text())
        for h in halladas:
            client.table("carreras").update({"duracion_anios": h["duracion"]}).eq(
                "id", h["carrera_id"]).is_("duracion_anios", "null").execute()
        print(f"Carreras con duración: {len(halladas)}")
        return

    halladas = leer(client)
    HALLADAS.write_text(json.dumps(halladas, ensure_ascii=False, indent=1) + "\n")
    print(f"Con duración: {len(halladas)} {dict(Counter(h['universidad'] for h in halladas))}"
          f" — vista previa en {HALLADAS}", flush=True)


if __name__ == "__main__":
    main()
