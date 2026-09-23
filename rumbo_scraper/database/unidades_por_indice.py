"""Give a career its academic unit from the unit's own list of careers.

`completar_unidades` asks each career's page which unit it belongs to, and
the pages of most private universities do not say. Their units do: the page
of the Kennedy's "Facultad de Ciencias Jurídicas" lists and links the careers
it teaches. This reads it the other way round:

1. the units a university links from its home page, or from the page it
   calls "Facultades" / "Unidades académicas" -- a link whose text is a unit
   ("Facultad de Ciencias Sociales", "Instituto de Salud Comunitaria");
2. the careers each unit page links from its content, leaving out the menu,
   header and footer, which on many sites list every career;
3. a career linked from exactly one unit belongs to it. One linked from two
   (a unit's page and a department's staff page, say) is left alone.

A career is matched by the address of its page, or by the link's text being
its name. Units of postgraduate studies, languages, admissions and the like
are not units a career belongs to and are not read.

Writes ``data/unidades_por_indice.json`` in the shape `completar_unidades`
applies; ``--apply`` hands it over.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from rumbo_scraper.database.completar_unidades import aplicar
from rumbo_scraper.database.exportar_catalogo import _urls_de_los_artefactos
from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.parsers.unidad import Unidad, conocida
from rumbo_scraper.spiders.visitante import Visitante

PAUSA = 1.0
SALIDA = Path("data/unidades_por_indice.json")
MAX_UNIDADES = 40

_UNA_UNIDAD = re.compile(r"(?i)^(facultad|escuela|departamento|instituto)\s+(?:de|del|en)\s+\S")
_TIPOS = {"facultad": "Facultad", "escuela": "Escuela",
          "departamento": "Departamento", "instituto": "Instituto"}
_NO_ES_UNIDAD_DE_CARRERAS = re.compile(
    r"(?i)posgrado|postgrado|alumnos|ingl[eé]s|idiomas|lenguas|tango|verano|"
    r"secundari|preuniversit|formaci[oó]n continua|extensi[oó]n|contabilidad$")
_UN_INDICE = re.compile(
    r"(?i)^\s*(facultades|unidades acad[eé]micas|escuelas|departamentos|institutos|"
    r"[aá]reas de estudio)\s*$")


def _normal(url: str) -> str:
    partes = urlparse(url)
    host = partes.netloc.lower().removeprefix("www.")
    return f"{host}{partes.path.rstrip('/')}?{partes.query}".rstrip("?").lower()


def _mismo_sitio(url: str, raiz: str) -> bool:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    base = urlparse(raiz).netloc.lower().removeprefix("www.")
    return bool(host) and (host == base or host.endswith("." + base))


def _enlaces(html: str, pagina: str, solo_contenido: bool) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    if solo_contenido:
        for parte in soup.find_all(["nav", "header", "footer", "aside", "script", "style"]):
            parte.decompose()
    return [(clean_text(a.get_text(" ")), urljoin(pagina, a["href"]))
            for a in soup.find_all("a", href=True)]


def unidades_enlazadas(html: str, pagina: str, raiz: str) -> dict[str, tuple[Unidad, str]]:
    """The unit pages a page links, by the unit's name."""
    unidades: dict[str, tuple[Unidad, str]] = {}
    for texto, url in _enlaces(html, pagina, solo_contenido=False):
        match = _UNA_UNIDAD.match(texto)
        if not match or len(texto) > 90 or not _mismo_sitio(url, raiz):
            continue
        if _NO_ES_UNIDAD_DE_CARRERAS.search(texto) or _NO_ES_UNIDAD_DE_CARRERAS.search(url):
            continue
        # "ESCUELA DE FORMACIÓN" and "Escuela de Formación" are one unit.
        nombre = texto if not texto.isupper() else texto.capitalize()
        unidades.setdefault(comparison_key(nombre),
                            (Unidad(nombre, _TIPOS[match.group(1).lower()]), url))
    return unidades


def leer(client: Any) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all

    def todo(tabla: str) -> list[dict[str, Any]]:
        return select_all(client.table(tabla).select("*"))

    universidades = {u["id"]: u for u in todo("universidades")}
    publicadas: dict[str, list[str]] = defaultdict(list)
    for f in todo("facultades"):
        publicadas[f["universidad_id"]].append(f["nombre_facultad"])
    carreras = [c for c in todo("carreras") if not c["facultad_id"]]
    artefactos = _urls_de_los_artefactos()
    url_de = {c["id"]: artefactos.get((universidades[c["universidad_id"]]["nombre_oficial"],
                                       c["nombre_carrera"])) for c in carreras}
    for oferta in todo("ofertas_academicas"):
        if oferta["url_oficial"] and oferta["carrera_id"] in url_de:
            url_de[oferta["carrera_id"]] = oferta["url_oficial"]
    sin_unidad: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in carreras:
        sin_unidad[c["universidad_id"]].append(c)

    halladas: list[dict[str, Any]] = []
    with Visitante(timeout=20) as visitante:
        for uid, pendientes in sin_unidad.items():
            universidad = universidades[uid]
            raiz = universidad.get("sitio_web") or ""
            if not raiz:
                continue
            inicio = visitante.get(raiz)
            unidades = unidades_enlazadas(inicio, raiz, raiz)
            # The page the university calls "Facultades", one level down.
            for texto, url in _enlaces(inicio, raiz, solo_contenido=False):
                if _UN_INDICE.match(texto) and _mismo_sitio(url, raiz):
                    time.sleep(PAUSA)
                    for clave, par in unidades_enlazadas(visitante.get(url), url, raiz).items():
                        unidades.setdefault(clave, par)
            if not unidades:
                continue

            # Which unit pages link each career.
            por_carrera: dict[str, set[str]] = defaultdict(set)
            nombres = {c["id"]: comparison_key(c["nombre_carrera"]) for c in pendientes}
            direcciones = {c["id"]: _normal(url_de[c["id"]]) for c in pendientes
                           if url_de.get(c["id"])}
            for clave, (unidad, url) in list(unidades.items())[:MAX_UNIDADES]:
                time.sleep(PAUSA)
                enlaces = _enlaces(visitante.get(url), url, solo_contenido=True)
                destinos = {_normal(u) for _, u in enlaces}
                textos = {comparison_key(t) for t, _ in enlaces}
                for c in pendientes:
                    if direcciones.get(c["id"]) in destinos or nombres[c["id"]] in textos:
                        por_carrera[c["id"]].add(clave)

            corto = universidad.get("nombre_corto") or ""
            for c in pendientes:
                claves = por_carrera.get(c["id"], set())
                if len(claves) != 1:
                    continue
                unidad = unidades[claves.pop()][0]
                nombre = conocida(unidad, publicadas[uid]) or unidad.nombre
                print(f"{corto:9} | {c['nombre_carrera'][:50]:50} | {nombre}", flush=True)
                halladas.append({"carrera_id": c["id"], "universidad_id": uid,
                                 "universidad": corto, "carrera": c["nombre_carrera"],
                                 "unidad": nombre, "tipo": unidad.tipo,
                                 "url": url_de.get(c["id"]) or ""})
    return halladas


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Completar la unidad académica desde la lista de carreras de cada unidad")
    parser.add_argument("--apply", action="store_true",
                        help=f"Escribir en Supabase lo que dejó la vista previa en {SALIDA}")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if args.apply:
        halladas = json.loads(SALIDA.read_text())
        print(f"Carreras con unidad: {len(halladas)}; unidades nuevas: {aplicar(client, halladas)}")
        return
    halladas = leer(client)
    SALIDA.write_text(json.dumps(halladas, ensure_ascii=False, indent=1) + "\n")
    por_universidad: dict[str, int] = defaultdict(int)
    for h in halladas:
        por_universidad[h["universidad"]] += 1
    print(f"Con unidad: {len(halladas)} {dict(por_universidad)} — vista previa en {SALIDA}")


if __name__ == "__main__":
    main()
