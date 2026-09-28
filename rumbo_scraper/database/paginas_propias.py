"""Give each career the page of its own, from its faculty's list of careers.

Some readers found a university's careers on a page that lists many (UBA's
careers point at www.uba.ar/carreras/<faculty>, a list of the faculty's
careers): a page shared by several careers says nothing of any one. Its
faculty's own site has a page per career, and the faculty's list of careers
links it by the career's name.

A page is taken only if the list gives exactly one page by that name
(`pagina_de_la_carrera`) and that page's title names the career
(`es_la_pagina_de`), and no other career of the university is given the
same page. The page replaces the offer's address; a career without an
offer (an offer needs a campus, which the list does not say) keeps it in
``data/urls_propias.json``, which the export reads before the readings.
Nothing else changes.

    python -m rumbo_scraper.database.paginas_propias UBA            (preview)
    python -m rumbo_scraper.database.paginas_propias UBA --apply
"""

from __future__ import annotations

import argparse
import json
import re
import time
from urllib.parse import urlparse
from collections import Counter
from pathlib import Path
from typing import Any

from rumbo_scraper.database.exportar_catalogo import _urls_de_los_artefactos
from rumbo_scraper.parsers.guias_nacionales import pagina_de_la_carrera, paginas_por_nombre
from rumbo_scraper.parsers.unidad import es_la_pagina_de
from rumbo_scraper.spiders.visitante import Visitante

PAUSA = 0.8
HALLADAS = Path("data/paginas_propias.json")
PROPIAS = Path("data/urls_propias.json")

# The faculties' lists of careers.
LISTADOS: dict[str, tuple[str, ...]] = {
    "UBA": ("https://www.agro.uba.ar/carreras", "https://www.fadu.uba.ar/carreras/",
            "https://www.economicas.uba.ar/alumnos", "https://exactas.uba.ar/ensenanza/carreras-de-grado/",
            "https://www.sociales.uba.ar/carreras/", "https://www.ffyb.uba.ar",
            "https://www.filo.uba.ar", "https://www.fi.uba.ar/grado",
            "https://www.fmed.uba.ar/carreras-y-tecnicaturas/carreras-de-grado",
            "https://www.derecho.uba.ar", "https://www.psi.uba.ar"),
    # Humanidades y Artes moved its careers ("/carreras/grado/10/..." is 404).
    "UNR": ("https://fhumyar.unr.edu.ar/carreras-de-grado/", "https://fhumyar.unr.edu.ar/pregrado/"),
}


def leer(client: Any, sigla: str) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all

    universidad = client.table("universidades").select("*").eq("nombre_corto", sigla).execute().data[0]
    carreras = select_all(client.table("carreras").select("id,nombre_carrera").eq("universidad_id", universidad["id"]))
    ids = {c["id"] for c in carreras}
    artefactos = _urls_de_los_artefactos()
    url_de = {c["id"]: artefactos.get((universidad["nombre_oficial"], c["nombre_carrera"])) for c in carreras}
    for oferta in select_all(client.table("ofertas_academicas").select("carrera_id,url_oficial")):
        if oferta["carrera_id"] in ids and oferta["url_oficial"]:
            url_de[oferta["carrera_id"]] = oferta["url_oficial"]
    # A page more than one career points at is a list, not any one's page.
    compartidas = {url for url, veces in Counter(url_de.values()).items() if url and veces > 1}

    halladas = []
    with Visitante(timeout=25) as visitante:
        paginas: dict[str, str] = {}
        for listado in LISTADOS.get(sigla, ()):
            for nombre, url in paginas_por_nombre(visitante.get(listado), listado).items():
                paginas.setdefault(nombre, url)
            time.sleep(PAUSA)
        hosts = {urlparse(listado).netloc for listado in LISTADOS.get(sigla, ())}
        for carrera in carreras:
            actual = url_de.get(carrera["id"])
            # A page of its own that is gone (the faculty moved it) is none.
            if actual and actual not in compartidas and not (
                    urlparse(actual).netloc in hosts and not visitante.get(actual)):
                continue
            # Exactas names its "Licenciatura en Ciencias Biológicas" "Ciencias Biológicas".
            # A name so shortened ("Historia") may be any page's: only a page
            # under the site's careers counts (Agronomía's "/historia" is its own).
            propia = pagina_de_la_carrera(carrera["nombre_carrera"], paginas) or pagina_de_la_carrera(
                re.sub(r"(?i)^licenciatura en\s+", "", carrera["nombre_carrera"]),
                {k: u for k, u in paginas.items() if re.search(r"(?i)/carreras?\b|/carreras-de-grado/", u)})
            if not propia or propia == actual:
                continue
            html = visitante.get(propia)
            time.sleep(PAUSA)
            if not es_la_pagina_de(html, carrera["nombre_carrera"]):
                continue
            print(f"{sigla:6} | {carrera['nombre_carrera'][:55]:55} | {propia}", flush=True)
            halladas.append({"carrera_id": carrera["id"], "carrera": carrera["nombre_carrera"],
                             "universidad": universidad["nombre_oficial"], "antes": actual, "url": propia})
    # A page two careers were given is theirs together: neither's own.
    veces = Counter(h["url"] for h in halladas)
    return [h for h in halladas if veces[h["url"]] == 1]


def aplicar(client: Any, halladas: list[dict[str, Any]]) -> int:
    propias = json.loads(PROPIAS.read_text()) if PROPIAS.exists() else {}
    for hallada in halladas:
        ofertas = client.table("ofertas_academicas").select("id").eq("carrera_id", hallada["carrera_id"]).execute().data
        if ofertas:
            client.table("ofertas_academicas").update({"url_oficial": hallada["url"]}).eq(
                "carrera_id", hallada["carrera_id"]).execute()
        else:
            propias.setdefault(hallada["universidad"], {})[hallada["carrera"]] = hallada["url"]
    PROPIAS.write_text(json.dumps(propias, ensure_ascii=False, indent=1) + "\n")
    return len(halladas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dar a cada carrera su propia página")
    parser.add_argument("universidad", choices=sorted(LISTADOS))
    parser.add_argument("--apply", action="store_true", help=f"Escribir lo que dejó la vista previa en {HALLADAS}")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if args.apply:
        print(f"Actualizadas: {aplicar(client, json.loads(HALLADAS.read_text()))}")
        return
    halladas = leer(client, args.universidad)
    HALLADAS.write_text(json.dumps(halladas, ensure_ascii=False, indent=1) + "\n")
    print(f"{args.universidad}: {len(halladas)} carreras con su página — vista previa en {HALLADAS}")


if __name__ == "__main__":
    main()
