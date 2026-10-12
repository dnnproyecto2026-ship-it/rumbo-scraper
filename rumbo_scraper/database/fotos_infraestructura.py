"""Photographs of each university's buildings and spaces, for its profile.

The home page's links to the pages about the university's spaces (campus,
sedes, instalaciones, biblioteca, deportes, vida universitaria, galería...)
are followed two steps deep within the university's own site; on each page,
``parsers.fotos`` keeps the photographs whose own words name the space they
show. Each is downloaded once to measure it: one narrower than 1000 pixels is
dropped, and the same photograph published in several sizes (or the same
file under two names) is kept once, at its largest.

The first photograph is the widest landscape view of a campus or building,
for the cover; then one of each type, then the rest, fifteen at most. A
photograph only its page names (one on the page about the library with no
words of its own) goes apart, under ``para_revisar``, for a person to look
at: a page about a space also carries its stock pictures and its posters.

    python -m rumbo_scraper.database.fotos_infraestructura UBA UNC [--paginas 40]

writes ``data/fotos/<university>.json``. Nothing is written to Supabase.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
from pathlib import Path
from typing import Any
from urllib import robotparser
from urllib.parse import urlparse

from PIL import Image

from rumbo_scraper.parsers import fotos
from rumbo_scraper.spiders.visitante import USER_AGENT, Visitante
from rumbo_scraper.verificacion import dominio

SALIDA = Path("data/fotos")
PAUSA = 0.5
MAXIMO = 15


def _robots(visitante: Visitante, sitio: str) -> robotparser.RobotFileParser:
    reglas = robotparser.RobotFileParser()
    try:
        respuesta = visitante.client.get(sitio.rstrip("/") + "/robots.txt")
        reglas.parse(respuesta.text.splitlines() if respuesta.status_code == 200 else [])
    except Exception:
        reglas.parse([])
    return reglas


def paginas_de_espacios(visitante: Visitante, sitio: str, tope: int) -> dict[str, str]:
    propio = dominio(sitio)
    reglas = _robots(visitante, sitio)
    leidas: dict[str, str] = {}
    pendientes = [(sitio, 0)]
    while pendientes and len(leidas) < tope:
        url, paso = pendientes.pop(0)
        if url in leidas or not reglas.can_fetch(USER_AGENT, url):
            continue
        try:
            html = visitante.get(url)
        except Exception:
            html = ""
        time.sleep(PAUSA)
        leidas[url] = html
        if html and paso < 2:
            pendientes += [(e, paso + 1) for e in fotos.enlaces_a_espacios(html, url, propio)
                           if e not in leidas]
    return {u: h for u, h in leidas.items() if h}


def medir(visitante: Visitante, url: str) -> tuple[int, int, str] | None:
    try:
        respuesta = visitante.client.get(url)
        if respuesta.status_code != 200 or not respuesta.headers.get("content-type", "").startswith("image"):
            return None
        with Image.open(io.BytesIO(respuesta.content)) as imagen:
            ancho, alto = imagen.size
        return ancho, alto, hashlib.md5(respuesta.content).hexdigest()
    except Exception:
        return None


def fotos_de(visitante: Visitante, sitio: str,
             tope: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The photographs whose own words name their space, and apart, for a
    person to look at, those only the page they sit on names."""
    candidatas: dict[str, fotos.Candidata] = {}
    for pagina, html in paginas_de_espacios(visitante, sitio, tope).items():
        if fotos.NOTICIAS.search(urlparse(pagina).path):
            continue
        for c in fotos.imagenes_de(html, pagina):
            if dominio(c.url_imagen) != dominio(sitio):
                # A picture served from elsewhere (a stock bank, someone
                # else's site) is not shown as the university's own.
                continue
            if c.url_imagen in candidatas:
                candidatas[c.url_imagen].variantes += c.variantes
            else:
                candidatas[c.url_imagen] = c
    medidas: dict[str, dict[str, Any]] = {}
    for c in candidatas.values():
        # The original first, then each published size, largest kept.
        mejor = None
        for url in dict.fromkeys([c.url_imagen, *c.variantes]):
            medida = medir(visitante, url)
            time.sleep(PAUSA)
            if medida and (mejor is None or medida[0] > mejor[1][0]):
                mejor = (url, medida)
            if medida and medida[0] >= 2000:
                break
        if (mejor is None or mejor[1][0] < fotos.MINIMO_ANCHO
                or mejor[1][0] > fotos.PROPORCION_MAXIMA * mejor[1][1]
                or (c.por_la_pagina and mejor[1][0] < 1.2 * mejor[1][1])):
            continue
        url, (ancho, alto, huella) = mejor
        fila = {"url_imagen": url, "pagina": c.pagina, "tipo": c.tipo, "sede": c.sede,
                "descripcion": fotos.descripcion(c), "texto_alternativo": c.texto_alternativo or c.epigrafe,
                "ancho": ancho, "alto": alto, "credito": c.credito,
                "tipo_segun": "pagina" if c.por_la_pagina else "imagen"}
        if huella not in medidas or medidas[huella]["ancho"] < ancho:
            medidas[huella] = fila
    filas = list(medidas.values())
    return (ordenar([f for f in filas if f["tipo_segun"] == "imagen"]),
            ordenar([f for f in filas if f["tipo_segun"] == "pagina"]))


def ordenar(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    por_calidad = sorted(filas, key=lambda f: (fotos.PRIORIDAD.index(f["tipo"]), f["tipo_segun"] != "imagen",
                                               -(f["ancho"] >= f["alto"]), -f["ancho"]))
    portada = [f for f in por_calidad if f["tipo"] == "campus" and f["ancho"] > f["alto"]][:1]
    una_por_tipo = []
    for tipo in fotos.PRIORIDAD:
        una_por_tipo += [f for f in por_calidad if f["tipo"] == tipo and f not in portada][:1]
    resto = [f for f in por_calidad if f not in portada and f not in una_por_tipo]
    return (portada + una_por_tipo + resto)[:MAXIMO]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fotos de infraestructura de cada universidad")
    parser.add_argument("universidades", nargs="+", help="nombre_corto de cada universidad")
    parser.add_argument("--paginas", type=int, default=40, help="Páginas a leer por universidad")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all

    client = get_supabase_client()
    sitios = {u["nombre_corto"]: u["sitio_web"] for u in select_all(
        client.table("universidades").select("nombre_corto,sitio_web")) if u["sitio_web"]}
    SALIDA.mkdir(parents=True, exist_ok=True)
    with Visitante(timeout=30) as visitante:
        for nombre in args.universidades:
            sitio = sitios.get(nombre)
            if not sitio:
                print(f"{nombre}: sin sitio web")
                continue
            filas, para_revisar = fotos_de(visitante, sitio, args.paginas)
            destino = SALIDA / f"{nombre.lower().replace(' ', '_')}.json"
            destino.write_text(json.dumps({"universidad": nombre, "sitio_web": sitio, "imagenes": filas,
                                          "para_revisar": para_revisar},
                                          ensure_ascii=False, indent=2))
            tipos: dict[str, int] = {}
            for f in filas:
                tipos[f["tipo"]] = tipos.get(f["tipo"], 0) + 1
            print(f"{nombre:8} {len(filas):2} fotos {tipos}, {len(para_revisar)} para revisar → {destino}",
                  flush=True)


if __name__ == "__main__":
    main()
