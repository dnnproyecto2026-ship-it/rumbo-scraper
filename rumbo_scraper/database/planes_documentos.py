"""The plans the national universities publish as documents.

Most careers of the national universities link their plan from their own
page as a PDF: the annex of the resolution that approved it. The general
reader followed those links and read the PDF's text, and the text of a
resolution is mostly "VISTO el Expediente..." -- it stored nothing, rightly.
This reads the PDF's tables instead (`parsers.plan_por_columnas`, and
`parsers.plan_por_cuatrimestre` for the tables by term), and takes a plan only
when everything says it is this career's whole plan:

- the document is linked by one career only: one linked by several is a
  common cycle or a faculty's catalogue, not any one career's plan;
- the document names the career in its first pages: UNLaM's "Ingeniería
  Mecánica" links the plan of a teacher-training course;
- no two careers come out with the same subjects: that is a common first
  cycle (UNMdP's agronomies) or a degree's plan linked from its
  intermediate title;
- a tecnicatura does not run past its third year, for the same reason;
- no subject name starts in lower case or ends on a connecting word: both
  are pieces of a name the cell wrapped ("social", "Comprensión y
  Producción de" over "Textos en Artes");
- a plan that does not say the year has at least twenty subjects: fewer is
  the first cycle alone;
- no year has more than twenty: that is the pool of electives listed under
  the last year as if it were taken whole;
- a plan that says the year reaches at least the year before the career's
  last: a five-year career whose plan stops in the third is missing a cycle.

A document is the one the page calls a plan of studies, or, failing that,
a PDF the page links whose file is named after the career: UNAHUR links
"Ingenieria-Metalurgica.pdf" with no word around it.

Before the document, the career's own page: UNQ lays its plans out in HTML
tables, with the terms as rows ("Segundo Cuatrimestre") or each cycle
announced with its count ("Núcleo Básico Obligatorio: 12 asignaturas").

Optional subjects ("(optativa)") and the degree's title are not the plan's
sequence and are left out. A career gets subjects only if it has none.
Downloads are kept in ``data/planes_documentos/``. Reading every career's
page takes a while, so the preview keeps what it found in
``data/planes_documentos.json`` and ``--apply`` writes from that file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rumbo_scraper.database.exportar_catalogo import _urls_de_los_artefactos
from rumbo_scraper.normalizers.text import comparison_key
import math

from rumbo_scraper.parsers import plan_por_ciclos, plan_por_columnas, plan_por_cuatrimestre
from rumbo_scraper.parsers.unc import leer_plan_fcefyn, plan_mas_nuevo
from rumbo_scraper.spiders.generico import _documento_del_plan, _enlace_al_plan
from rumbo_scraper.spiders.visitante import Visitante

CACHE = Path("data/planes_documentos")
HALLADOS = Path("data/planes_documentos.json")
PAUSA = 0.7
MINIMO_SIN_ANIO = 20
MAS_POR_ANIO = 20
_VACIAS = frozenset("de del la las los el y e en a con para por licenciatura tecnicatura "
                    "universitaria carrera profesorado ingenieria ciclo".split())
_FUERA_DEL_PLAN = re.compile(r"(?i)\(optativa\)|^t[íi]tulo\s*:")


def _nombra(texto: str, carrera: str) -> bool:
    palabras = set(re.findall(r"[a-z0-9]+", comparison_key(texto)))
    propias = [p for p in re.findall(r"[a-z0-9]+", comparison_key(carrera)) if p not in _VACIAS]
    return all(p in palabras for p in propias)


# A word the PDF broke at the end of a line: "Alimen- tos".
_PALABRA_PARTIDA = re.compile(r"(\w)- (?=[a-záéíóúñ])")
_TERMINA_CORTADA = re.compile(r"(?i)\s(de|del|la|las|los|el|y|e|o|u|en|con|para|por|a|al)$")


def _leer(archivo: Path) -> list[tuple[str, int | None]]:
    try:
        materias = plan_por_columnas.leer_pdf(str(archivo))
        if not materias:
            materias = plan_por_cuatrimestre.leer_pdf(str(archivo))
    except Exception:
        return []
    return [(_PALABRA_PARTIDA.sub(r"\1", nombre), anio) for nombre, anio in materias
            if not _FUERA_DEL_PLAN.search(nombre)]


def _texto(archivo: Path) -> str:
    import pdfplumber

    try:
        with pdfplumber.open(str(archivo)) as pdf:
            return " ".join((pagina.extract_text() or "") for pagina in pdf.pages[:4])
    except Exception:
        return ""


def _parece_el_plan_entero(carrera: str, materias: list[tuple[str, int | None]],
                           duracion: float | None = None) -> bool:
    if len(materias) < 10 or any(nombre[:1].islower() or _TERMINA_CORTADA.search(nombre)
                                 for nombre, _ in materias):
        return False
    anios = [anio for _, anio in materias if anio]
    if not anios:
        return len(materias) >= MINIMO_SIN_ANIO
    # More than twenty subjects in one year is the pool of electives listed
    # under the last year (Río Cuarto's Psicopedagogía: 52 in the fourth).
    if max(Counter(anios).values()) > MAS_POR_ANIO:
        return False
    if comparison_key(carrera).startswith("tecnicatura") and max(anios) > 3:
        return False
    if duracion and max(anios) < math.ceil(duracion) - 1:
        return False
    # Without a duration, a degree (not a cycle, not a tecnicatura) runs at
    # least four years: UNQ's Informática page lists the first three alone.
    clave = comparison_key(carrera)
    if not duracion and not clave.startswith(("ciclo", "tecnicatura")) and max(anios) < 4:
        return False
    return True


def _de_la_pagina(html: str) -> list[tuple[str, int | None]]:
    materias: list[tuple[str, int | None]] = list(plan_por_columnas.leer_html(html))
    if not materias:
        materias = [(m, None) for m in plan_por_ciclos.leer_tablas_html(html)]
    return materias


def _de_la_pagina_del_plan(html: str) -> list[tuple[str, int | None]]:
    """A page that is the plan itself: by code (the UNC's engineering) or
    in tables. Read as bare lines year by year, the UNC's Nutrición came out
    with "Ingreso" and "Page load link" in its fifth year: not read so."""
    return leer_plan_fcefyn(html) or _de_la_pagina(html)


def _documento_con_su_nombre(html: str, pagina: str, carrera: str) -> str | None:
    """The one PDF the page links whose file name has all the career's words."""
    from bs4 import BeautifulSoup
    from urllib.parse import unquote, urljoin

    candidatos = set()
    for enlace in BeautifulSoup(html or "", "html.parser").find_all("a", href=True):
        url = urljoin(pagina, enlace["href"])
        archivo = unquote(urlparse(url).path.rsplit("/", 1)[-1])
        if not archivo.lower().endswith(".pdf") or urlparse(url).netloc != urlparse(pagina).netloc:
            continue
        if _nombra(re.sub(r"[-_.]+", " ", archivo), carrera):
            candidatos.add(url)
    return candidatos.pop() if len(candidatos) == 1 else None


def leer(client: Any, solo: set[str]) -> dict[str, dict[str, Any]]:
    """For each career that has no subjects, the plan its document gives."""
    from rumbo_scraper.database.supabase import select_all

    universidades = {u["id"]: u for u in select_all(client.table("universidades").select("*"))
                     if not solo or u.get("nombre_corto") in solo}
    carreras = [c for c in select_all(client.table("carreras").select(
        "id,universidad_id,nombre_carrera,nivel,duracion_anios"))
        if c["universidad_id"] in universidades]
    con_materias = {m["carrera_id"] for m in select_all(
        client.table("materias").select("carrera_id")) if m["carrera_id"]}
    artefactos = _urls_de_los_artefactos()
    url_de = {c["id"]: artefactos.get((universidades[c["universidad_id"]]["nombre_oficial"],
                                       c["nombre_carrera"])) for c in carreras}
    for oferta in select_all(client.table("ofertas_academicas").select("carrera_id,url_oficial")):
        if oferta["url_oficial"] and oferta["carrera_id"] in url_de:
            url_de[oferta["carrera_id"]] = oferta["url_oficial"]

    documento_de: dict[str, str] = {}
    de_la_pagina: dict[str, list[tuple[str, int | None]]] = {}
    pagina_del_plan: dict[str, str] = {}
    CACHE.mkdir(parents=True, exist_ok=True)
    with Visitante(timeout=30) as visitante:
        for carrera in carreras:
            url = url_de.get(carrera["id"])
            if carrera["id"] in con_materias or not url:
                continue
            host = urlparse(url).netloc.removeprefix("www.")
            dominios = (host, host.split(".", 1)[-1]) if host.count(".") > 2 else (host,)
            html = visitante.get(url)
            time.sleep(PAUSA)
            en_la_pagina = _de_la_pagina(html)
            if en_la_pagina:
                de_la_pagina[carrera["id"]] = en_la_pagina
                continue
            # A page that links its plans as pages of their own, by year
            # ("Plan de estudios 2025", the UNC's engineering faculty): the
            # newest is read.
            # Or links one page as its plan ("plan de estudios", Sociales and
            # the FAUD of the UNC), which says it the way a page does.
            nuevo = plan_mas_nuevo(html, url) or _enlace_al_plan(html, url, dominios)
            if nuevo:
                html_del_plan = visitante.get(nuevo)
                time.sleep(PAUSA)
                del_plan = _de_la_pagina_del_plan(html_del_plan)
                if del_plan:
                    de_la_pagina[carrera["id"]] = del_plan
                    pagina_del_plan[carrera["id"]] = nuevo
                    continue
            documento = (_documento_del_plan(html, url, dominios)
                         or _documento_con_su_nombre(html, url, carrera["nombre_carrera"]))
            if not documento:
                enlace = _enlace_al_plan(html, url, dominios)
                if enlace:
                    documento = _documento_del_plan(visitante.get(enlace), enlace, dominios)
                    time.sleep(PAUSA)
            if not documento:
                continue
            archivo = CACHE / (hashlib.md5(documento.encode()).hexdigest() + ".pdf")
            if not archivo.exists():
                try:
                    respuesta = visitante.client.get(documento)
                    archivo.write_bytes(respuesta.content if respuesta.status_code == 200 else b"")
                except Exception:
                    archivo.write_bytes(b"")
                time.sleep(PAUSA)
            documento_de[carrera["id"]] = documento

    usos = Counter(documento_de.values())
    planes: dict[str, dict[str, Any]] = {}
    for carrera in carreras:
        materias = de_la_pagina.get(carrera["id"])
        if materias and _parece_el_plan_entero(carrera["nombre_carrera"], materias,
                                               carrera.get("duracion_anios")):
            planes[carrera["id"]] = {
                "carrera": carrera, "materias": materias,
                "documento": pagina_del_plan.get(carrera["id"]) or url_de[carrera["id"]],
                "universidad": universidades[carrera["universidad_id"]].get("nombre_corto"),
            }
            continue
        documento = documento_de.get(carrera["id"])
        if not documento or usos[documento] > 1:
            continue
        archivo = CACHE / (hashlib.md5(documento.encode()).hexdigest() + ".pdf")
        if archivo.stat().st_size < 1000 or not _nombra(_texto(archivo), carrera["nombre_carrera"]):
            continue
        materias = _leer(archivo)
        if _parece_el_plan_entero(carrera["nombre_carrera"], materias,
                                  carrera.get("duracion_anios")):
            planes[carrera["id"]] = {
                "carrera": carrera, "materias": materias, "documento": documento,
                "universidad": universidades[carrera["universidad_id"]].get("nombre_corto"),
            }

    iguales = Counter(tuple(sorted(n.lower() for n, _ in p["materias"])) for p in planes.values())
    return {cid: p for cid, p in planes.items()
            if iguales[tuple(sorted(n.lower() for n, _ in p["materias"]))] == 1}


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar los planes publicados como documento")
    parser.add_argument("--apply", action="store_true",
                        help=f"Escribir en Supabase lo que dejó la vista previa en {HALLADOS}")
    parser.add_argument("universidades", nargs="*", help="Nombres cortos; todas si se omite")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if args.apply:
        planes = json.loads(HALLADOS.read_text())
    else:
        planes = leer(client, set(args.universidades))
        HALLADOS.write_text(json.dumps(planes, ensure_ascii=False, indent=1) + "\n")

    filas = []
    por_universidad: dict[str, int] = defaultdict(int)
    for plan in planes.values():
        carrera = plan["carrera"]
        por_anio = dict(Counter(anio for _, anio in plan["materias"]))
        print(f"{plan['universidad']:8} {carrera['nombre_carrera'][:48]:48} "
              f"{len(plan['materias']):3} {por_anio}", flush=True)
        por_universidad[plan["universidad"]] += 1
        vistas: set[str] = set()
        for materia, anio in plan["materias"]:
            if materia.lower() in vistas:
                continue
            vistas.add(materia.lower())
            filas.append({"universidad_id": carrera["universidad_id"], "carrera_id": carrera["id"],
                          "nombre_materia": materia, "anio_cursada": anio})

    if args.apply and filas:
        for inicio in range(0, len(filas), 500):
            client.table("materias").insert(filas[inicio:inicio + 500]).execute()
    print(f"Planes: {len(planes)} {dict(por_universidad)}; materias "
          f"{'cargadas' if args.apply else 'a cargar'}: {len(filas)}", flush=True)


if __name__ == "__main__":
    main()
