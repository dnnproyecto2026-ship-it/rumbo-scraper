"""Walk the public site of a university and keep the pages that offer a degree.

The walk is deliberately dumb: it asks the site for its own sitemap, and where
there is none it follows links out from the home page. It never guesses an
address. What makes it cheap is that it decides from the address alone whether
a page can possibly hold a career -- a university publishes hundreds of pages
of news for every page of a career -- and only downloads those.

Nothing here is specific to any university. What each one needs said about it
is in ``rumbo_scraper.catalogo``.
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from rumbo_scraper.catalogo import Universidad, buscar
from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers import generico

USER_AGENT = "RumboScraper/0.4 (+catalogo educativo publico)"
MAX_PAGINAS = 2500
HILOS = 5
# The shortest gap between two requests to the same university. Eight at a
# time with no gap made one site answer 1195 of 1364 requests with a 503: a
# reader that is refused service has not read anything, and has spent the
# university's server to do it.
INTERVALO = 0.25
# What a site says when it is being asked for too much, or too fast.
DEMASIADO = (429, 503, 502, 504)
DEFAULT_DIR = Path("data")

_PLAN = re.compile(r"(?i)plan\s*(de\s*)?estudi|materias|asignaturas|"
                   r"estructura\s*curricular|curricula")


class Lector:
    """A polite reader of one site, with its own failures written down."""

    def __init__(self, universidad: Universidad) -> None:
        self.universidad = universidad
        self.dominios = (universidad.dominio,) + tuple(universidad.dominios_extra)
        self.errores: list[dict[str, str]] = []
        self._lock = threading.Lock()
        self._turno = threading.Lock()
        self._ultimo = 0.0
        self._navegador = Navegador() if universidad.navegador else None
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT,
                     "Accept-Language": "es-AR,es;q=0.9"},
            follow_redirects=True, timeout=45,
            limits=httpx.Limits(max_connections=HILOS),
            verify=False,
        )

    def close(self) -> None:
        self.client.close()
        if self._navegador is not None:
            self._navegador.close()

    def get(self, url: str, intentos: int = 2) -> str:
        if self._navegador is not None and not url.endswith(".xml"):
            html = self._navegador.get(url)
            if html:
                return html
            with self._lock:
                self.errores.append({"url": url, "error": "el navegador no cargó la página"})
            return ""
        return self._get_directo(url, intentos)

    def _esperar_turno(self) -> None:
        """Let no two requests leave closer together than the interval."""
        with self._turno:
            gap = time.monotonic() - self._ultimo
            if gap < INTERVALO:
                time.sleep(INTERVALO - gap)
            self._ultimo = time.monotonic()

    def _get_directo(self, url: str, intentos: int = 3) -> str:
        for attempt in range(intentos):
            self._esperar_turno()
            try:
                response = self.client.get(url)
                if response.status_code in DEMASIADO and attempt < intentos - 1:
                    # The site is asking to be left alone for a moment. The
                    # only right answer is to wait longer than last time.
                    time.sleep(4 * (attempt + 1))
                    continue
                response.raise_for_status()
                kind = response.headers.get("content-type", "")
                if "html" not in kind and "xml" not in kind:
                    return ""
                return response.text
            except Exception as exc:  # network, TLS, redirect loops, bad status
                if attempt == intentos - 1:
                    with self._lock:
                        self.errores.append({"url": url, "error": str(exc)[:200]})
                    return ""
                time.sleep(1.5 * (attempt + 1))
        with self._lock:
            self.errores.append({"url": url, "error": "el sitio pidió menos pedidos"})
        return ""

    def get_many(self, urls: list[str]) -> dict[str, str]:
        if self._navegador is not None:
            # One browser, one page at a time: a second tab costs more than
            # it saves and the sites that need a browser are the small ones.
            return {url: html for url, html in
                    ((url, self.get(url)) for url in urls) if html}
        with ThreadPoolExecutor(max_workers=HILOS) as pool:
            pages = list(pool.map(self.get, urls))
        return {url: html for url, html in zip(urls, pages) if html}


class Navegador:
    """A browser, for the sites that build their pages after they load.

    A few universities serve a page of one and a half kilobytes that holds no
    text and no links, and fill it in the reader's browser. Asking such a
    site politely gets an empty document; the only way to read what it
    publishes is to let it finish building it.
    """

    def __init__(self) -> None:
        from playwright.sync_api import sync_playwright
        self._play = sync_playwright().start()
        self._browser = self._play.chromium.launch()
        self._page = self._browser.new_page(user_agent=USER_AGENT)

    def get(self, url: str) -> str:
        # Waiting for the network to fall silent costs up to a minute on a
        # page that polls, and a university site polls. Waiting for the
        # document and then a moment more is enough to read what it built.
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=25000)
            self._page.wait_for_timeout(1200)
            return self._page.content()
        except Exception:
            return ""

    def close(self) -> None:
        for shut in (self._page.close, self._browser.close, self._play.stop):
            try:
                shut()
            except Exception:
                pass


def direcciones(lector: Lector) -> list[str]:
    """Every address of the site, from its sitemap or by following its links."""
    universidad = lector.universidad
    roots = universidad.sitemaps or (
        urljoin(universidad.sitio_web + "/", "sitemap.xml"),
        urljoin(universidad.sitio_web + "/", "sitemap_index.xml"),
        urljoin(universidad.sitio_web + "/", "sitemap-index.xml"),
    )
    found: list[str] = []
    seen: set[str] = set()
    pending = list(roots)
    while pending and len(found) < 60000:
        current = pending.pop(0)
        if current in seen:
            continue
        seen.add(current)
        for url in generico.direcciones_del_sitemap(lector.get(current)):
            if url.endswith(".xml") or url.endswith(".xml.gz"):
                if url not in seen and len(seen) < 120:
                    pending.append(url)
            elif url not in seen:
                seen.add(url)
                found.append(url)
    propios = [url for url in found if _es_propio(url, lector.dominios)]
    return propios


def _es_propio(url: str, dominios: tuple[str, ...]) -> bool:
    return generico.es_del_dominio(url, dominios)


def recorrer(lector: Lector, semillas: list[str], tope: int) -> list[str]:
    """Follow links out from the seeds, keeping to the catalogue of the site.

    Which pages belong to the catalogue is decided from the address, because
    deciding it from the page means downloading every page of a site that
    publishes a hundred pieces of news for every career.

    Some sites number their pages instead of naming them -- "index.php?
    idcateg=7" -- and there the address says nothing at all. When the first
    pass finds no address that reads like a catalogue, every page of the site
    becomes a candidate, up to the cap: a slower read is the only kind
    available.
    """
    seen: set[str] = set()
    catalogue: list[str] = []
    todos: list[str] = []
    frontier = [url for url in semillas if url]
    por_direccion = True
    depth = 0
    while frontier and len(seen) < tope and depth < 4:
        batch = [url for url in frontier if url not in seen][:400]
        for url in batch:
            seen.add(url)
        pages = lector.get_many(batch)
        following: list[str] = []
        for url, html in pages.items():
            # Everything the index of careers links is a career, whatever its
            # address says, so the index is trusted over the addresses.
            indice = generico.es_el_indice(url)
            for link in generico.enlaces(html, url, lector.dominios):
                if link not in todos:
                    todos.append(link)
                if link in seen:
                    continue
                if indice or generico.parece_catalogo(link):
                    if link not in catalogue:
                        catalogue.append(link)
                    following.append(link)
                elif depth == 0 or not por_direccion:
                    following.append(link)
        if depth == 0 and not catalogue:
            # The site names nothing: read it whole rather than not at all.
            por_direccion = False
        frontier = following
        depth += 1
    return catalogue if por_direccion else todos[:tope]


# Below this many careers the sitemap has not shown the catalogue, whatever
# else it showed. A national university teaches more than this.
POCAS_CARRERAS = 15


def leer(universidad: Universidad, tope: int = MAX_PAGINAS,
         limite: int | None = None) -> dict[str, Any]:
    """Read one university whole: its programmes and the plans they publish."""
    lector = Lector(universidad)
    try:
        candidatas = _del_sitemap(lector, tope)
        paginas = lector.get_many(candidatas[:limite] if limite else candidatas)
        programas = _programas_de(paginas)

        # A national university does not keep its careers on the host that
        # carries its sitemap: each faculty publishes its own on a host of its
        # own. When the sitemap comes back short, the links do the rest.
        if len(programas) < POCAS_CARRERAS:
            semillas = [universidad.sitio_web, *universidad.semillas]
            extra = [url for url in recorrer(lector, semillas, tope)
                     if url not in paginas]
            if limite:
                extra = extra[:limite]
            nuevas = lector.get_many(extra[:tope])
            paginas.update(nuevas)
            vistos = {programa.url for programa in programas}
            programas += [programa for programa in _programas_de(nuevas)
                          if programa.url not in vistos]
            candidatas = sorted(set(candidatas) | set(nuevas))

        planes = _planes_de(lector, programas, paginas)
        return generico.build_dataset(
            universidad, programas, paginas, planes, lector.errores,
            descubiertas=len(candidatas),
        )
    finally:
        lector.close()


def _del_sitemap(lector: Lector, tope: int) -> list[str]:
    """The pages of the catalogue the site lists in its own sitemap."""
    universidad = lector.universidad
    todas = direcciones(lector)
    candidatas = [url for url in todas if generico.parece_catalogo(url)]
    if len(candidatas) < 20:
        # Either the site has no sitemap or it keeps its catalogue out of it.
        # Walking out from the home page finds it either way.
        semillas = [universidad.sitio_web, *universidad.semillas]
        candidatas = sorted(set(candidatas) | set(recorrer(lector, semillas, tope)))
    return sorted(set(candidatas))[:tope]


def _programas_de(paginas: dict[str, str]) -> list[generico.Programa]:
    """The pages that turned out to offer a degree."""
    programas: list[generico.Programa] = []
    for url, html in paginas.items():
        programa = generico.leer_programa(html, url)
        if programa is not None:
            programas.append(programa)
    return programas


def _planes_de(lector: Lector, programas: list[generico.Programa],
               paginas: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    """The plan of each programme, from its own page or from the one it links."""
    planes: dict[str, list[dict[str, Any]]] = {}
    faltantes: list[tuple[str, str]] = []
    for programa in programas:
        materias = generico.leer_plan(paginas.get(programa.url, ""))
        if materias:
            planes[programa.url] = materias
            continue
        enlace = _enlace_al_plan(paginas.get(programa.url, ""), programa.url,
                                lector.dominios)
        if enlace:
            faltantes.append((programa.url, enlace))
    aparte = lector.get_many([enlace for _, enlace in faltantes])
    for origen, enlace in faltantes:
        materias = generico.leer_plan(aparte.get(enlace, ""))
        if materias:
            planes[origen] = materias
    return planes


def _enlace_al_plan(html: str, pagina: str, dominios: tuple[str, ...]) -> str | None:
    """The page a programme links to for its plan of studies, if it links one."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    for anchor in soup.find_all("a", href=True):
        label = clean_text(anchor.get_text(" ", strip=True))
        href = clean_text(anchor["href"])
        if not _PLAN.search(label) and not _PLAN.search(href):
            continue
        url = urljoin(pagina, href).split("#")[0]
        if url.lower().endswith(".pdf") or not _es_propio(url, dominios):
            continue
        if url.rstrip("/") != pagina.rstrip("/"):
            return url
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Leer el catálogo público de una universidad")
    parser.add_argument("universidad", help="Sigla, como figura en catalogo.py")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--tope", type=int, default=MAX_PAGINAS)
    args = parser.parse_args()

    universidad = buscar(args.universidad)
    output = args.output or DEFAULT_DIR / f"{universidad.nombre_corto.lower()}_completo.json"
    dataset = leer(universidad, args.tope, args.limit)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    data = dataset["datos"]
    quality = dataset["control_calidad"]
    print(f"{universidad.nombre_oficial}")
    print(f"- páginas del catálogo: {quality['paginas_recorridas']}")
    print(f"- carreras: {len(data['carreras'])}")
    print(f"- posgrados: {len(data['posgrados'])}")
    print(f"- materias: {len(data['materias'])}")
    print(f"- facultades: {len(data['facultades'])}")
    print(f"- errores de descarga: {len(quality['errores_descarga'])}")
    print(f"Archivo: {output}")


if __name__ == "__main__":
    main()
