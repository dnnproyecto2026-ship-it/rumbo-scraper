"""Check every career, subject and teacher of the catalogue against its source.

Reads what the catalogue exports (``data/catalogo_depurado.json``) and goes
back to the university's site for each row, with the checks of
`rumbo_scraper.verificacion`:

- an offer or a postgraduate programme, against its official page: the page
  answers and names it;
- a subject, against the career's plan: its page, and the plan it links as a
  page or a document; the subject is verified when the plan names it;
- a teacher, against the profile the university publishes: it answers and
  names the person.

Each university is read by its own worker, so no site gets more than one
request at a time. What was fetched is kept in ``data/verificacion/``, and
the result goes to ``data/verificaciones.json``, which the application's
importer reads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rumbo_scraper import verificacion as v
from rumbo_scraper.normalizers.text import comparison_key

CATALOGO = Path("data/catalogo_depurado.json")
CACHE = Path("data/verificacion")
RESULTADO = Path("data/verificaciones.json")
PAUSA = 0.5
HILOS = 6


class Fuentes:
    """The sources of one university, each fetched once and kept on disk."""

    def __init__(self, sitio_web: str) -> None:
        from rumbo_scraper.spiders.visitante import Visitante

        self.sitio_web = sitio_web
        self.visitante = Visitante(timeout=25)
        self.leidas: dict[str, dict[str, Any]] = {}

    def close(self) -> None:
        self.visitante.close()

    def leer(self, url: str, avalada: bool = False) -> dict[str, Any]:
        """``{"ok": bool, "html": str, "texto": plain text}`` of an official
        source; one outside the university's domain is not fetched, unless
        an official page links it as its plan (``avalada``)."""
        if url in self.leidas:
            return self.leidas[url]
        archivo = CACHE / (hashlib.md5(url.encode()).hexdigest() + ".json")
        if archivo.exists():
            leida = json.loads(archivo.read_text())
        elif not avalada and not v.es_oficial(url, self.sitio_web):
            leida = {"ok": False, "html": "", "texto": ""}
        else:
            leida = self._traer(url)
            archivo.write_text(json.dumps(leida, ensure_ascii=False))
            time.sleep(PAUSA)
        self.leidas[url] = leida
        return leida

    def _traer(self, url: str) -> dict[str, Any]:
        from rumbo_scraper.spiders.generico import _tiene_contenido

        # A site that asks to slow down (429) or stumbles (5xx, a timeout)
        # is asked again after a wait: San Andrés answered none of its 1,284
        # profiles in a row, and every one of them opens.
        respuesta = None
        for espera in (0, 10, 30):
            time.sleep(espera)
            try:
                respuesta = self.visitante.client.get(url)
            except Exception:
                respuesta = None
                continue
            if respuesta.status_code != 429 and respuesta.status_code < 500:
                break
        if respuesta is None or respuesta.status_code >= 400:
            return {"ok": False, "html": "", "texto": ""}
        tipo = respuesta.headers.get("content-type", "")
        if "pdf" in tipo or url.lower().split("?")[0].endswith(".pdf"):
            return {"ok": True, "html": "", "texto": v.plano(_texto_del_pdf(respuesta.content))}
        if "json" in tipo:
            try:
                datos = respuesta.json()
            except ValueError:
                return {"ok": False, "html": "", "texto": ""}
            return {"ok": True, "html": "", "crudo": respuesta.text,
                    "texto": v.plano(f" {v.CORTE} ".join(_textos_del_json(datos)))}
        html = respuesta.text
        if not _tiene_contenido(html):
            html = self.visitante.get(url) or html
        return {"ok": True, "html": html, "texto": v.plano(v.texto_de_html(html))}


def _textos_del_json(datos: Any) -> list[str]:
    """Every text a JSON document holds, each on its own."""
    if isinstance(datos, dict):
        return [t for valor in datos.values() for t in _textos_del_json(valor)]
    if isinstance(datos, list):
        return [t for valor in datos for t in _textos_del_json(valor)]
    return [str(datos)] if isinstance(datos, str) else []


def _texto_del_pdf(contenido: bytes) -> str:
    import io

    import pdfplumber

    # The text, and each cell of its tables on its own: a name the cell
    # wraps comes out whole, where the page's text interleaves the columns.
    partes = []
    try:
        with pdfplumber.open(io.BytesIO(contenido)) as pdf:
            for pagina in pdf.pages[:60]:
                partes.append(pagina.extract_text() or "")
                for tabla in pagina.extract_tables():
                    for fila in tabla:
                        partes.append(f" {v.CORTE} ".join(" ".join((c or "").split())
                                                          for c in fila))
                        partes.append(v.CORTE)
    except Exception:
        pass
    return " ".join(partes)


def _dominios(url: str) -> tuple[str, ...]:
    host = urlparse(url).netloc.removeprefix("www.")
    return (host, host.split(".", 1)[-1]) if host.count(".") > 2 else (host,)


def _planes_enlazados(html: str, pagina: str) -> list[str]:
    """The documents an official page links as its plan, wherever they are
    kept: the ITBA keeps its plans on its own Amazon storage, and the page
    that links them is the university saying they are its plans."""
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    from rumbo_scraper.spiders.generico import _NO_ES_EL_PLAN, _PLAN

    halladas = []
    for enlace in BeautifulSoup(html or "", "html.parser").find_all("a", href=True):
        url = urljoin(pagina, enlace["href"].strip())
        if not urlparse(url).path.lower().endswith(".pdf"):
            continue
        junto = re.sub(r"[-_+]+|%20", " ", f"{enlace.get_text(' ', strip=True)} {url}")
        if _PLAN.search(junto) and not _NO_ES_EL_PLAN.search(junto) and url not in halladas:
            halladas.append(url)
    return halladas


def _plan_uai(fuentes: "Fuentes", url: str, html: str, carrera: str) -> list[str]:
    """The UAI serves each plan from its plan service, by the code the
    career's page declares: the index of plans, then the newest."""
    from rumbo_scraper.parsers import uai

    codigo = uai.parse_plan_reference(html)["codigo"]
    if not codigo:
        return []
    planes = uai.read_plan_codes(fuentes.leer(uai.plan_index_url(codigo))["html"])
    return [uai.plan_detail_url(codigo, planes[0])] if planes else []


def _fuentes_utn(fuentes: "Fuentes", url: str, html: str, carrera: str) -> list[str]:
    """The UTN's career page is a search its browser fills in from the
    catalogue's public service: the career's record there, and the plan the
    service files for it."""
    from urllib.parse import parse_qs

    from rumbo_scraper.parsers import utn

    carrera = (parse_qs(urlparse(url).query).get("idSeleccion") or [None])[0]
    if not carrera:
        return []
    documentos = fuentes.leer(utn.documents_url(carrera))
    try:
        plan = utn.plan_document_url(json.loads(documentos.get("crudo") or "[]"))
    except ValueError:
        plan = None
    return [utn.offers_url(carrera)] + ([plan] if plan else [])


def _fuentes_uba(fuentes: "Fuentes", url: str, html: str, carrera: str) -> list[str]:
    """Each UBA faculty links the plan from the career's page with its own
    label; Engineering files every plan in one index of resolutions, and
    Political Science lists its cycles on the students' page."""
    from rumbo_scraper.database import planes_uba
    from rumbo_scraper.parsers import uba

    halladas = [uba.plan_document_url(html, url)] if html else []
    if carrera in planes_uba.POR_CICLOS:
        halladas.append(planes_uba.POR_CICLOS[carrera])
    indice = planes_uba.documentos_de_ingenieria(fuentes.leer(planes_uba.INGENIERIA)["html"])
    carreras = {comparison_key(carrera): {"nombre_carrera": carrera}}
    halladas += [documento for nombre, documento in indice.items()
                 if planes_uba._emparejar(nombre, carreras)]
    return [h for h in halladas if h]


# Where a university keeps a career's data apart from its page, the way its
# own reader found it: a plan service, a catalogue's public API.
_FUENTES_PROPIAS = {"UAI": _plan_uai, "UTN": _fuentes_utn, "UBA": _fuentes_uba}


def _planes_publicados() -> dict[tuple[str, str], str]:
    """The page each plan was read from, by (university, career), from the
    readers that kept it."""
    urls = {}
    for archivo in Path("data").glob("*_planes.json"):
        corto = archivo.name.removesuffix("_planes.json")
        for plan in json.loads(archivo.read_text()).get("planes") or []:
            if plan.get("url"):
                urls[(corto, comparison_key(plan.get("nombre")))] = plan["url"]
    return urls


def verificar_universidad(datos: dict[str, Any], planes: dict[tuple[str, str], str]) -> dict[str, Any]:
    from rumbo_scraper.spiders.generico import _documento_del_plan, _enlace_al_plan
    from rumbo_scraper.database.planes_documentos import _documento_con_su_nombre

    ficha = datos["universidades"][0]
    sitio_web = ficha.get("sitio_web")
    corto = (ficha.get("nombre_corto") or "").lower()
    fuentes = Fuentes(sitio_web)
    resultado: dict[str, list[dict[str, Any]]] = {"ofertas": [], "materias": [], "docentes": []}
    try:
        # --- offers: the page names the career ---------------------------
        paginas_de: dict[str, list[str]] = defaultdict(list)
        programas = [(o.get("url_oficial"), o.get("carrera_nombre")) for o in datos.get("ofertas") or []]
        programas += [(p.get("url_oficial"), p.get("nombre_programa"))
                      for p in datos.get("posgrados") or []]
        for url, carrera in programas:
            if url and carrera and url not in paginas_de[carrera]:
                paginas_de[carrera].append(url)
        propias = _FUENTES_PROPIAS.get(ficha.get("nombre_corto") or "")
        for carrera, urls in paginas_de.items():
            for url in urls:
                leida = fuentes.leer(url) if v.es_oficial(url, sitio_web) else {"ok": False}
                estado = v.estado_de_la_fuente(url, sitio_web, leida["ok"])
                fuente = url
                if estado is None:
                    dice = (v.nombra_la_carrera(leida["html"] or "", carrera)
                            or v.dice(leida["texto"], carrera))
                    # The page a browser fills in says it through the source
                    # it is filled from.
                    for otra in (propias(fuentes, url, leida["html"], carrera)
                                 if propias and not dice else []):
                        propia = fuentes.leer(otra, avalada=True)
                        if propia["ok"] and v.dice(propia["texto"], carrera):
                            dice, fuente = True, otra
                            break
                    estado = v.VERIFICADO if dice else v.NO_LO_DICE
                resultado["ofertas"].append({"carrera": carrera, "url": url, "estado": estado,
                                             "fuente": fuente})

        # --- subjects: the plan names the subject ------------------------
        por_carrera: dict[str, list[str]] = defaultdict(list)
        for materia in datos.get("materias") or []:
            nombre, carrera = materia.get("nombre_materia"), materia.get("carrera_o_programa")
            if nombre and carrera and nombre not in por_carrera[carrera]:
                por_carrera[carrera].append(nombre)
        for carrera, materias in por_carrera.items():
            candidatas = list(paginas_de.get(carrera, []))
            publicada = planes.get((corto, comparison_key(carrera)))
            if publicada and publicada not in candidatas:
                candidatas.append(publicada)
            textos = {}
            for url in candidatas:
                leida = fuentes.leer(url)
                if leida["ok"]:
                    textos[url] = leida["texto"]
            if sum(1 for m in materias if any(v.dice(t, m) for t in textos.values())) \
                    < v.PLAN_HALLADO * len(materias):
                # The page does not have the plan: the plan is the page or
                # the document it links.
                for url in candidatas:
                    html = fuentes.leer(url)["html"]
                    if not html:
                        continue
                    dominios = _dominios(url)
                    enlace = _enlace_al_plan(html, url, dominios)
                    otras = [_documento_del_plan(html, url, dominios),
                             _documento_con_su_nombre(html, url, carrera), enlace]
                    if enlace and fuentes.leer(enlace)["html"]:
                        otras.append(_documento_del_plan(fuentes.leer(enlace)["html"], enlace,
                                                         _dominios(enlace)))
                    for otra in otras:
                        if otra and otra not in textos and v.es_oficial(otra, sitio_web):
                            leida = fuentes.leer(otra)
                            if leida["ok"]:
                                textos[otra] = leida["texto"]
                    for propia in propias(fuentes, url, html, carrera) if propias else []:
                        # Declared here as the university's own: its reader
                        # found the data there.
                        leida = fuentes.leer(propia, avalada=True)
                        if leida["ok"] and propia not in textos:
                            textos[propia] = leida["texto"]
                    if v.es_oficial(url, sitio_web):
                        for documento in _planes_enlazados(html, url):
                            if documento not in textos:
                                leida = fuentes.leer(documento, avalada=True)
                                if leida["ok"]:
                                    textos[documento] = leida["texto"]
            for materia, (estado, fuente, corregida) in v.materias_del_plan(materias, textos).items():
                fila = {"carrera": carrera, "materia": materia, "estado": estado, "fuente": fuente}
                if corregida:
                    fila["como_la_dice_la_fuente"] = corregida
                resultado["materias"].append(fila)

        # --- teachers: the profile names the person ----------------------
        for docente in datos.get("docentes") or []:
            nombre, url = docente.get("nombre"), docente.get("perfil_url")
            leida = fuentes.leer(url) if v.es_oficial(url, sitio_web) else {"ok": False}
            estado = v.estado_de_la_fuente(url, sitio_web, leida["ok"])
            if estado is None:
                estado = (v.VERIFICADO if v.nombra_a_la_persona(leida["texto"], nombre)
                          else v.NO_LO_DICE)
            resultado["docentes"].append({"nombre": nombre, "perfil_url": url, "estado": estado})
    finally:
        fuentes.close()
    return resultado


def resumen(universidad: dict[str, Any]) -> str:
    partes = []
    for tipo in ("ofertas", "materias", "docentes"):
        cuenta = Counter(fila["estado"] for fila in universidad[tipo])
        if cuenta:
            partes.append(f"{tipo} {cuenta[v.VERIFICADO]}/{sum(cuenta.values())}"
                          + "".join(f" {k}={n}" for k, n in cuenta.items() if k != v.VERIFICADO))
    return " · ".join(partes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verificar el catálogo contra las fuentes oficiales")
    parser.add_argument("universidades", nargs="*", help="Nombres cortos; todas si se omite")
    args = parser.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    planes = _planes_publicados()
    entradas = [e["datos"] for e in json.loads(CATALOGO.read_text())["universidades"]
                if not args.universidades
                or e["datos"]["universidades"][0].get("nombre_corto") in args.universidades]
    anterior = json.loads(RESULTADO.read_text()) if RESULTADO.exists() else {}
    universidades = dict(anterior.get("universidades") or {})
    escritura = threading.Lock()

    def una(datos: dict[str, Any]) -> None:
        ficha = datos["universidades"][0]
        inicio = time.monotonic()
        try:
            hallado = verificar_universidad(datos, planes)
        except Exception as error:  # a university that fails leaves the rest
            print(f"{ficha.get('nombre_corto'):9} | error: {error!r}", flush=True)
            return
        print(f"{ficha.get('nombre_corto'):9} | {time.monotonic() - inicio:5.0f}s | "
              f"{resumen(hallado)}", flush=True)
        with escritura:
            universidades[ficha["nombre_oficial"]] = hallado
            RESULTADO.write_text(json.dumps({"fecha": date.today().isoformat(),
                                             "universidades": universidades},
                                            ensure_ascii=False, indent=1) + "\n")

    with ThreadPoolExecutor(HILOS) as grupo:
        list(grupo.map(una, entradas))

    total = defaultdict(Counter)
    for universidad in universidades.values():
        for tipo, filas in universidad.items():
            total[tipo].update(fila["estado"] for fila in filas)
    for tipo, cuenta in total.items():
        print(f"{tipo}: {dict(cuenta)}", flush=True)


if __name__ == "__main__":
    main()
