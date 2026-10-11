"""Give a postgraduate that shares its address with others its own page.

A list read from a faculty's page gives each programme that page's address
when the reading kept no other. Many such pages link each programme to its
own (UBA's Económicas and FADU, UNPA): the programme's page is the link
whose text is its name, with or without its kind ("Maestría en Historia del
Arte" or "Historia del Arte"). A link is taken only when it is the only one
with that text, on the university's own domain, not a document, and no
other programme of the page takes it. The degree, the duration and the plan
are read from that page afterwards (`completar_posgrados`, `planes_posgrados`).

The preview keeps what it found in ``data/paginas_posgrados.json``;
``--apply`` writes from that file.

    python -m rumbo_scraper.database.paginas_posgrados [--sitemaps] [UBA UNPA ...]
    python -m rumbo_scraper.database.paginas_posgrados --apply
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.verificacion import es_oficial

HALLADOS = Path("data/paginas_posgrados.json")
PAUSA = 0.8
_TIPO = re.compile(r"^(?:carrera de )?(?:especializacion|maestria|doctorado|especialista|magister)(?: en| de)? ")
_NO_ES_SU_PAGINA = re.compile(r"(?i)\.(?:pdf|docx?|jpe?g|png)(?:$|\?)|docs\.google|drive\.google|/tag/|/category/"
                              r"|/(?:nosotros|institucional)/")


def _clave(nombre: str) -> str:
    return " ".join(comparison_key(nombre).split())


def enlaces_propios(html: str, url: str, programas: list[str], sitio_web: str) -> dict[str, str]:
    """Programme -> its own page, from the links of the page they share."""
    por_texto: dict[str, set[str]] = defaultdict(set)
    for enlace in BeautifulSoup(html or "", "html.parser").find_all("a", href=True):
        texto = _clave(" ".join(enlace.get_text(" ").split()))
        destino = urljoin(url, enlace["href"]).split("#")[0]
        if texto and destino.rstrip("/") != url.rstrip("/"):
            por_texto[texto].add(destino)
    hallados: dict[str, str] = {}
    for programa in programas:
        clave = _clave(programa)
        # Without its kind, a name of one word is anything's ("Historia" is
        # the university's own history page).
        sin_tipo = _TIPO.sub("", clave)
        destinos = por_texto.get(clave) or (por_texto.get(sin_tipo) if len(sin_tipo.split()) > 1 else None) or set()
        if len(destinos) != 1:
            continue
        destino = next(iter(destinos))
        if _NO_ES_SU_PAGINA.search(destino) or not es_oficial(destino, sitio_web):
            continue
        hallados[programa] = destino
    # A page two programmes would take is neither's.
    usos = Counter(hallados.values())
    return {p: d for p, d in hallados.items() if usos[d] == 1}


_VACIAS = frozenset("de del la las los el y e en a con para por o u al".split())


def _palabras(texto: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", comparison_key(texto)) if w not in _VACIAS}


def direcciones_del_sitio(visitante: Any, url: str) -> list[str]:
    """Every page the site's sitemaps list (WordPress's, Yoast's, robots')."""
    from urllib.parse import urlparse

    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    cola = [base + "/sitemap.xml", base + "/sitemap_index.xml", base + "/wp-sitemap.xml"]
    try:
        cola += re.findall(r"(?im)^sitemap:\s*(\S+)", visitante.client.get(base + "/robots.txt").text)
    except Exception:
        pass
    vistas: set[str] = set()
    paginas: list[str] = []
    while cola and len(vistas) < 60:
        mapa = cola.pop(0)
        if mapa in vistas:
            continue
        vistas.add(mapa)
        try:
            respuesta = visitante.client.get(mapa)
            texto = respuesta.text if respuesta.status_code == 200 else ""
        except Exception:
            texto = ""
        time.sleep(PAUSA)
        for direccion in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", texto):
            direccion = direccion.replace("&amp;", "&")
            (cola if re.search(r"\.xml(?:\.gz)?$|sitemap", direccion) else paginas).append(direccion)
    return paginas


def por_su_direccion(paginas: list[str], programas: list[str]) -> dict[str, str]:
    """Programme -> the one page of the sitemap whose address spells every
    word of its name, and few more ("…/maestria-en-salud-publica/")."""
    from urllib.parse import unquote, urlparse

    # A news item or an event about the programme is not its page.
    noticia = re.compile(r"(?i)/(?:noticias?|novedades|agenda|eventos?|calendarios?|prensa|blog)/|"
                         r"abren|inscripci|se-dictar|acredit|convocatoria|presentaci")
    rutas = [(p, _palabras(unquote(urlparse(p).path).replace("-", " ").replace("_", " ").replace("/", " ")))
             for p in paginas if not _NO_ES_SU_PAGINA.search(p) and not noticia.search(urlparse(p).path)]
    hallados = {}
    for programa in programas:
        palabras = _palabras(programa)
        if len(palabras) < 3:
            continue
        candidatas = {p for p, r in rutas if palabras <= r and len(r) <= len(palabras) + 3}
        if len(candidatas) == 1:
            hallados[programa] = candidatas.pop()
    usos = Counter(hallados.values())
    return {p: d for p, d in hallados.items() if usos[d] == 1}


def leer(client: Any, solo: set[str], sitemaps: bool = False) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all
    from rumbo_scraper.spiders.visitante import Visitante

    universidades = {u["id"]: u for u in select_all(
        client.table("universidades").select("id,nombre_corto,sitio_web"))}
    posgrados = [p for p in select_all(client.table("posgrados").select(
        "id,universidad_id,nombre_programa,url_oficial,tipo_posgrado")) if p["url_oficial"]
        and (not solo or universidades[p["universidad_id"]]["nombre_corto"] in solo)]
    compartidas: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for p in posgrados:
        compartidas[(p["universidad_id"], p["url_oficial"])].append(p)
    cambios = []
    with Visitante(timeout=30) as visitante:
        for (universidad_id, url), programas in compartidas.items():
            if len(programas) < 2:
                continue
            universidad = universidades[universidad_id]
            html = visitante.get(url) or ""
            time.sleep(PAUSA)
            nombres = [p["nombre_programa"] for p in programas]
            propios = enlaces_propios(html, url, nombres, universidad["sitio_web"] or "")
            faltan = [n for n in nombres if n not in propios]
            if sitemaps and faltan:
                # The page lists them without links: the site's sitemaps may
                # still have each one's page, which must then name it.
                from rumbo_scraper.parsers.datos_posgrado import nombra_el_programa

                for nombre, destino in por_su_direccion(direcciones_del_sitio(visitante, url), faltan).items():
                    if es_oficial(destino, universidad["sitio_web"] or "") and \
                            nombra_el_programa(visitante.get(destino) or "", nombre):
                        propios[nombre] = destino
                    time.sleep(PAUSA)
            for p in programas:
                if p["nombre_programa"] in propios:
                    cambios.append({"id": p["id"], "universidad": universidad["nombre_corto"],
                                    "programa": p["nombre_programa"], "antes": url,
                                    "url_oficial": propios[p["nombre_programa"]]})
                    print(f"{universidad['nombre_corto']:8} {p['nombre_programa'][:60]:60} "
                          f"{propios[p['nombre_programa']]}", flush=True)
    return cambios


def main() -> None:
    parser = argparse.ArgumentParser(description="Página propia de los posgrados que comparten una lista")
    parser.add_argument("--apply", action="store_true", help=f"Escribir en Supabase lo que dejó la vista previa en {HALLADOS}")
    parser.add_argument("--sitemaps", action="store_true",
                        help="Buscar también en los sitemaps del sitio la página que la lista no enlaza")
    parser.add_argument("universidades", nargs="*", help="Nombres cortos; todas si se omite")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client

    client = get_supabase_client()
    if args.apply:
        cambios = json.loads(HALLADOS.read_text())
        for cambio in cambios:
            client.table("posgrados").update({"url_oficial": cambio["url_oficial"]}).eq(
                "id", cambio["id"]).eq("url_oficial", cambio["antes"]).execute()
    else:
        cambios = leer(client, set(args.universidades), args.sitemaps)
        HALLADOS.write_text(json.dumps(cambios, ensure_ascii=False, indent=1) + "\n")
    print(f"Posgrados con página propia: {len(cambios)} "
          f"{dict(Counter(c['universidad'] for c in cambios))}{' (escritos)' if args.apply else ''}")


if __name__ == "__main__":
    main()
