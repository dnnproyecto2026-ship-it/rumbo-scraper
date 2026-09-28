"""Give a postgraduate without a faculty the faculty its site belongs to.

Most postgraduates were read from lists that do not say which faculty teaches
each one. Many link to the programme's page on a faculty's own site
(jursoc.unlp.edu.ar, ayv.unrc.edu.ar). When every grado career of the same
university whose page lives on that site belongs to one faculty, and at least
two do, the site is that faculty's, and so is the postgraduate. The
university's main site says nothing: it hosts every faculty.

When no grado career lives on that site, the site's own home page may say
whose it is: its title or its main heading names the faculty ("Facultad de
Ciencias Agrarias - UNCuyo"). If exactly one of the university's faculties is
named there, in full, that is the site's faculty (``--por-titulo``).

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
        # An institution loaded while this reads is not in the first query.
        if carrera["universidad_id"] not in universidades:
            continue
        url = url_de.get(carrera["id"]) or artefactos.get(
            (universidades[carrera["universidad_id"]]["nombre_oficial"], carrera["nombre_carrera"]))
        if url:
            facultades_del_sitio[(carrera["universidad_id"], _sitio(url))][carrera["facultad_id"]] += 1

    hallados = []
    for posgrado in select_all(client.table("posgrados").select("id,universidad_id,facultad_id,url_oficial")):
        if posgrado["facultad_id"] or posgrado["universidad_id"] not in universidades:
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


def por_titulo(client: Any) -> list[tuple[str, str, str, str]]:
    """(posgrado, facultad, universidad, sitio) for each postgraduate on a
    site whose home page names one of its university's faculties, in full."""
    from bs4 import BeautifulSoup

    from rumbo_scraper.database.supabase import select_all
    from rumbo_scraper.normalizers.text import comparison_key
    from rumbo_scraper.spiders.visitante import Visitante

    universidades = {u["id"]: u for u in select_all(
        client.table("universidades").select("id,nombre_corto,sitio_web"))}
    facultades: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in select_all(client.table("facultades").select("id,universidad_id,nombre_facultad")):
        facultades[f["universidad_id"]].append(f)
    por_sitio: dict[tuple[str, str], list[str]] = defaultdict(list)
    for posgrado in select_all(client.table("posgrados").select("id,universidad_id,facultad_id,url_oficial")):
        universidad = universidades.get(posgrado["universidad_id"])
        sitio = _sitio(posgrado["url_oficial"])
        if posgrado["facultad_id"] or not universidad or not sitio or sitio == _sitio(universidad["sitio_web"]):
            continue
        por_sitio[(posgrado["universidad_id"], sitio)].append(posgrado["id"])

    hallados = []
    with Visitante(timeout=25) as visitante:
        for (uid, sitio), posgrados in por_sitio.items():
            html = visitante.get(f"https://{sitio}/") or visitante.get(f"http://{sitio}/")
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            partes = [soup.title.get_text(" ") if soup.title else ""]
            partes += [h.get_text(" ") for h in soup.find_all("h1")[:2]]
            partes += [m.get("content", "") for m in soup.find_all("meta", attrs={"property": "og:site_name"})]
            partes += [i.get("alt", "") for i in soup.find_all("img", alt=True)[:3]]
            texto = comparison_key(" ".join(partes))
            nombradas = [f for f in facultades[uid]
                         if len(comparison_key(f["nombre_facultad"])) > 12
                         and comparison_key(f["nombre_facultad"]) in texto]
            # "Facultad de Ciencias" inside "Facultad de Ciencias Agrarias":
            # the longest named is the one, if it contains the others.
            nombradas.sort(key=lambda f: len(f["nombre_facultad"]), reverse=True)
            if nombradas and all(comparison_key(f["nombre_facultad"]) in comparison_key(nombradas[0]["nombre_facultad"])
                                 for f in nombradas):
                corto = universidades[uid]["nombre_corto"]
                print(f"{corto:9} | {sitio:35} | {nombradas[0]['nombre_facultad']} | {len(posgrados)}", flush=True)
                hallados += [(pid, nombradas[0]["id"], corto, sitio) for pid in posgrados]
    return hallados


def main() -> None:
    parser = argparse.ArgumentParser(description="Dar a cada posgrado la facultad de su sitio")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    parser.add_argument("--por-titulo", action="store_true",
                        help="Leer el título de la portada de cada sitio en vez de las carreras de grado")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    hallados = por_titulo(client) if args.por_titulo else asignables(client)
    print(f"Asignables: {len(hallados)} {dict(Counter(h[2] for h in hallados))}")
    if args.apply:
        escritos = sum(len(client.table("posgrados").update({"facultad_id": facultad}).eq(
            "id", posgrado).is_("facultad_id", "null").execute().data)
            for posgrado, facultad, _, _ in hallados)
        print(f"Escritos: {escritos}")


if __name__ == "__main__":
    main()
