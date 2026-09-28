"""Give each career without a degree the one its own page states.

Almost no public university's career says what degree it gives: the
readers read lists of careers. This reads each career's own page (its
offer's address, or the one its reading kept) with `parsers.titulo`, only
if the page is the career's (`es_la_pagina_de`), and only for careers with
no degree stored. The preview keeps what it found in
``data/titulos_hallados.json``; ``--apply`` writes from that file.

    python -m rumbo_scraper.database.completar_titulos UBA UNC
    python -m rumbo_scraper.database.completar_titulos --apply
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
from rumbo_scraper.parsers.titulo import titulo_de_la_pagina
from rumbo_scraper.parsers.unidad import es_la_pagina_de
from rumbo_scraper.spiders.visitante import Visitante

PAUSA = 0.8
HALLADOS = Path("data/titulos_hallados.json")


_TIPOS = frozenset("licenciatura licenciado licenciada tecnicatura tecnico tecnica universitario universitaria "
                   "profesorado profesor profesora ingenieria ingeniero ingeniera".split())


def es_de_la_carrera(titulo: str, carrera: str) -> bool:
    """A degree that names a field ("... en Corretaje Inmobiliario") shares a
    word's root with the career's name: UNR's Derecho page names its sister
    career's degree too. One with no field ("Abogado", "Médico") is not checked."""
    import re as _re

    from rumbo_scraper.normalizers.text import comparison_key

    if " en " not in f" {comparison_key(titulo)} ":
        return True
    raices = lambda texto: {p[:5] for p in _re.findall(r"[a-z]{5,}", comparison_key(texto)) if p not in _TIPOS}
    propias = raices(carrera)
    return not propias or bool(propias & raices(titulo))


def leer(client: Any, solo: set[str] = frozenset()) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all

    universidades = {u["id"]: u for u in select_all(client.table("universidades").select("*"))
                     if not solo or u.get("nombre_corto") in solo}
    carreras = [c for c in select_all(client.table("carreras").select(
        "id,universidad_id,nombre_carrera,titulo_otorgado")) if c["universidad_id"] in universidades]
    artefactos = _urls_de_los_artefactos()
    url_de = {c["id"]: artefactos.get((universidades[c["universidad_id"]]["nombre_oficial"],
                                       c["nombre_carrera"])) for c in carreras}
    for oferta in select_all(client.table("ofertas_academicas").select("carrera_id,url_oficial")):
        if oferta["url_oficial"] and oferta["carrera_id"] in url_de:
            url_de[oferta["carrera_id"]] = oferta["url_oficial"]
    # A page several careers point at is a list: its degrees are not one's.
    compartidas = {u for u, veces in Counter(url_de.values()).items() if u and veces > 1}

    hallados = []
    with Visitante(timeout=25) as visitante:
        for carrera in carreras:
            url = url_de.get(carrera["id"])
            if carrera["titulo_otorgado"] or not url or url in compartidas or _NO_ES_SU_PAGINA.search(url):
                continue
            html = visitante.get(url)
            time.sleep(PAUSA)
            if not es_la_pagina_de(html, carrera["nombre_carrera"]):
                continue
            titulo = titulo_de_la_pagina(html, carrera["nombre_carrera"])
            if not titulo or not es_de_la_carrera(titulo, carrera["nombre_carrera"]):
                continue
            corto = universidades[carrera["universidad_id"]].get("nombre_corto") or ""
            print(f"{corto:9} | {carrera['nombre_carrera'][:50]:50} | {titulo}", flush=True)
            hallados.append({"carrera_id": carrera["id"], "universidad": corto,
                             "carrera": carrera["nombre_carrera"], "titulo": titulo, "url": url})
    return hallados


def main() -> None:
    parser = argparse.ArgumentParser(description="Completar el título que otorga cada carrera")
    parser.add_argument("--apply", action="store_true",
                        help=f"Escribir en Supabase lo que dejó la vista previa en {HALLADOS}")
    parser.add_argument("universidades", nargs="*", help="Nombres cortos; todas si se omite")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if args.apply:
        hallados = json.loads(HALLADOS.read_text())
        for h in hallados:
            client.table("carreras").update({"titulo_otorgado": h["titulo"]}).eq(
                "id", h["carrera_id"]).is_("titulo_otorgado", "null").execute()
        print(f"Carreras con título: {len(hallados)}")
        return
    hallados = leer(client, set(args.universidades))
    HALLADOS.write_text(json.dumps(hallados, ensure_ascii=False, indent=1) + "\n")
    print(f"Con título: {len(hallados)} {dict(Counter(h['universidad'] for h in hallados))}"
          f" — vista previa en {HALLADOS}", flush=True)


if __name__ == "__main__":
    main()
