"""Read a page the way a visitor sees it.

The institutional and student-life readers ask a handful of pages from each
university, and three things kept them from reading pages a person reads
without trouble:

- a site whose certificate is installed without its chain (UNAJ's): a fault
  of the server's setup, not a door it closed, and the general reader reads
  those sites too;
- a home page that only sends the reader elsewhere with a line of script
  (UNDAV's, Morón's), which is followed;
- a page the server sends as an empty shell for the browser to fill (UCA's,
  Morón's, UCES's), which is read in a browser. The browser opens only then,
  and only once per visit.

A page the server does not have is not one a browser would find, and is
returned empty.
"""

from __future__ import annotations

from typing import Any

import httpx

from rumbo_scraper.parsers.generico import se_mudo_a
from rumbo_scraper.spiders.generico import Navegador, _tiene_contenido

USER_AGENT = "RumboScraper/0.4 (+catalogo educativo publico)"


class Visitante:
    def __init__(self, timeout: float = 30) -> None:
        self.client = httpx.Client(headers={"User-Agent": USER_AGENT},
                                   follow_redirects=True, timeout=timeout, verify=False)
        self._navegador: Navegador | None = None
        self._sin_navegador = False

    def __enter__(self) -> "Visitante":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        self.client.close()
        if self._navegador is not None:
            self._navegador.close()

    def _directo(self, url: str) -> str:
        try:
            response = self.client.get(url)
            response.raise_for_status()
            if "html" not in response.headers.get("content-type", ""):
                return ""
            return response.text
        except Exception:
            return ""

    def get(self, url: str, _saltos: int = 2) -> str:
        html = self._directo(url)
        if not html or _tiene_contenido(html):
            return html
        destino = se_mudo_a(html, url)
        if destino and destino.rstrip("/") != url.rstrip("/") and _saltos:
            return self.get(destino, _saltos - 1) or html
        if self._navegador is None and not self._sin_navegador:
            try:
                self._navegador = Navegador()
            except Exception:
                self._sin_navegador = True
        if self._navegador is None:
            return html
        return self._navegador.get(url) or html
