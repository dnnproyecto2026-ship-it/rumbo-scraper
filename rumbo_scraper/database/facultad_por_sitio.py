"""Give a postgraduate without a faculty the faculty its site belongs to.

Most postgraduates were read from lists that do not say which faculty teaches
each one. Many link to the programme's page on a faculty's own site
(jursoc.unlp.edu.ar, ayv.unrc.edu.ar). When every grado career of the same
university whose page lives on that site belongs to one faculty, and at least
two do, the site is that faculty's, and so is the postgraduate. The
university's main site says nothing: it hosts every faculty.

Only empty faculties are written. Preview by default; ``--apply`` writes.

    python -m rumbo_scraper.database.facultad_por_sitio [--apply]
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from typing import Any
from urllib.parse import urlparse


def _sitio(url: str | None) -> str:
    return (urlparse(url or "").hostname or "").removeprefix("www.")


def asignables(client: Any) -> list[tuple[str, str, str, str]]:
    """(posgrado, facultad, universidad, sitio) for each postgraduate whose
    site belongs to one faculty only."""
    from rumbo_scraper.database.exportar_catalogo import _urls_de_los_artefactos
    from rumbo_scraper.database.supabase import select_all

    universidades = {u["id"]: u for u in select_all(
        client.table("universidades").select("id,nombre_corto,nombre_oficial,sitio_web"))}
    carreras = select_all(client.table("carreras").select("id,universidad_id,facultad_id,nombre_carrera"))
    url_de = {o["carrera_id"]: o["url_oficial"] for o in select_all(
        client.table("ofertas_academicas").select("carrera_id,url_oficial")) if o["url_oficial"]}
    artefactos = _urls_de_los_artefactos()
    facultades_del_sitio: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for carrera in carreras:
        url = url_de.get(carrera["id"]) or artefactos.get(
            (universidades[carrera["universidad_id"]]["nombre_oficial"], carrera["nombre_carrera"]))
        if url:
            facultades_del_sitio[(carrera["universidad_id"], _sitio(url))][carrera["facultad_id"]] += 1

    hallados = []
    for posgrado in select_all(client.table("posgrados").select("id,universidad_id,facultad_id,url_oficial")):
        if posgrado["facultad_id"]:
            continue
        universidad = universidades[posgrado["universidad_id"]]
        sitio = _sitio(posgrado["url_oficial"])
        cuenta = facultades_del_sitio.get((posgrado["universidad_id"], sitio))
        if not cuenta or sitio == _sitio(universidad["sitio_web"]):
            continue
        facultad, veces = cuenta.most_common(1)[0]
        if facultad and veces == sum(cuenta.values()) and veces >= 2:
            hallados.append((posgrado["id"], facultad, universidad["nombre_corto"], sitio))
    return hallados


def main() -> None:
    parser = argparse.ArgumentParser(description="Dar a cada posgrado la facultad de su sitio")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    hallados = asignables(client)
    print(f"Asignables: {len(hallados)} {dict(Counter(h[2] for h in hallados))}")
    if args.apply:
        escritos = sum(len(client.table("posgrados").update({"facultad_id": facultad}).eq(
            "id", posgrado).is_("facultad_id", "null").execute().data)
            for posgrado, facultad, _, _ in hallados)
        print(f"Escritos: {escritos}")


if __name__ == "__main__":
    main()
