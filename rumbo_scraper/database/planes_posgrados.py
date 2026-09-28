"""Give each postgraduate without subjects the plan its own page lists.

Most postgraduates were read from lists, and none of those says what each
one teaches. A programme's own page often does, under "Plan de estudios" or
"Cursos obligatorios" (`parsers.datos_posgrado.plan_de_posgrado`). This reads
each postgraduate's page when no other programme shares it and it names the
programme, and writes its subjects only if it has none. A plan the page does
not break into years is written without a year.

The preview keeps what it found in ``data/planes_posgrados_hallados.json``;
``--apply`` writes from that file.

    python -m rumbo_scraper.database.planes_posgrados [UNL UNCuyo ...]
    python -m rumbo_scraper.database.planes_posgrados --apply
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rumbo_scraper.database.completar_unidades import _NO_ES_SU_PAGINA
from rumbo_scraper.parsers.datos_posgrado import nombra_el_programa, plan_de_posgrado
from rumbo_scraper.parsers.unidad import es_la_pagina_de
from rumbo_scraper.spiders.visitante import Visitante

PAUSA = 0.8
SITIOS_A_LA_VEZ = 8
HALLADOS = Path("data/planes_posgrados_hallados.json")


def leer(client: Any, solo: set[str] = frozenset()) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all

    corto = {u["id"]: u.get("nombre_corto") or "" for u in select_all(
        client.table("universidades").select("id,nombre_corto"))}
    # A diplomatura lists its units with their contents: only the careers.
    posgrados = [p for p in select_all(client.table("posgrados").select(
        "id,universidad_id,nombre_programa,url_oficial,tipo_posgrado"))
        if p["tipo_posgrado"] in ("Doctorado", "Maestría", "Especialización")]
    con_materias = {m["posgrado_id"] for m in select_all(
        client.table("materias").select("posgrado_id")) if m["posgrado_id"]}
    veces = Counter(p["url_oficial"] for p in posgrados if p["url_oficial"])
    pendientes = [p for p in posgrados
                  if p["id"] not in con_materias
                  and (not solo or corto.get(p["universidad_id"]) in solo)
                  and p["url_oficial"] and veces[p["url_oficial"]] == 1
                  and not _NO_ES_SU_PAGINA.search(p["url_oficial"])
                  and not p["url_oficial"].lower().endswith(".pdf")]
    por_sitio: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in pendientes:
        por_sitio[urlparse(p["url_oficial"]).hostname or ""].append(p)

    def un_sitio(programas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        hallados = []
        with Visitante(timeout=25) as visitante:
            for p in programas:
                html = visitante.get(p["url_oficial"])
                time.sleep(PAUSA)
                if not html or not (es_la_pagina_de(html, p["nombre_programa"])
                                    or nombra_el_programa(html, p["nombre_programa"])):
                    continue
                materias = plan_de_posgrado(html)
                if materias:
                    u = corto.get(p["universidad_id"], "")
                    print(f"{u:9} | {p['nombre_programa'][:50]:50} | {len(materias):2} | "
                          + " ; ".join(m[:25] for m in materias[:4]), flush=True)
                    hallados.append({"posgrado_id": p["id"], "universidad_id": p["universidad_id"],
                                     "universidad": u, "programa": p["nombre_programa"],
                                     "url": p["url_oficial"], "materias": materias})
        return hallados

    with ThreadPoolExecutor(max_workers=SITIOS_A_LA_VEZ) as pool:
        return [h for lote in pool.map(un_sitio, por_sitio.values()) for h in lote]


def aplicar(client: Any, hallados: list[dict[str, Any]]) -> int:
    from rumbo_scraper.database.load_utdt import _insert_chunks
    from rumbo_scraper.database.supabase import select_all

    # A plan written since the preview is not written twice.
    con_materias = {m["posgrado_id"] for m in select_all(
        client.table("materias").select("posgrado_id")) if m["posgrado_id"]}
    filas = [{
        "universidad_id": h["universidad_id"], "carrera_id": None, "posgrado_id": h["posgrado_id"],
        "nombre_materia": materia, "anio_cursada": None, "turno": None, "area_tematica_id": None,
        "descripcion_breve": None, "regimen": None, "carga_horaria_semanal": None,
    } for h in hallados if h["posgrado_id"] not in con_materias for materia in h["materias"]]
    return _insert_chunks(client, "materias", filas) if filas else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Leer el plan de cada posgrado sin materias")
    parser.add_argument("--apply", action="store_true",
                        help=f"Escribir en Supabase lo que dejó la vista previa en {HALLADOS}")
    parser.add_argument("universidades", nargs="*", help="Nombres cortos; todas si se omite")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if args.apply:
        print("Materias escritas:", aplicar(client, json.loads(HALLADOS.read_text())))
        return
    hallados = leer(client, set(args.universidades))
    HALLADOS.write_text(json.dumps(hallados, ensure_ascii=False, indent=1) + "\n")
    print(f"Posgrados con plan: {len(hallados)}, materias: {sum(len(h['materias']) for h in hallados)}"
          f" — vista previa en {HALLADOS}", flush=True)


if __name__ == "__main__":
    main()
