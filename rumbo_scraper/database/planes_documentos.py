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
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from rumbo_scraper.database.exportar_catalogo import _urls_de_los_artefactos
from rumbo_scraper.normalizers.text import clean_text, comparison_key
import math

from rumbo_scraper.parsers import plan_por_ciclos, plan_por_columnas, plan_por_cuatrimestre, planes_sitios
from rumbo_scraper.parsers import uncuyo, unl
from rumbo_scraper.parsers.unc import leer_plan_fcefyn, plan_mas_nuevo
from rumbo_scraper.spiders.generico import _documento_del_plan, _enlace_al_plan
from rumbo_scraper.spiders.visitante import Visitante

CACHE = Path("data/planes_documentos")
HALLADOS = Path("data/planes_documentos.json")
# Sites with a reader of their own where the general one, year by year, still
# reads the careers theirs does not (checked by hand, 2026-09-28).
_RESPALDO_POR_ANIOS = ("unl.edu.ar", "uncuyo.edu.ar", "uncoma.edu.ar", "servicios.uns.edu.ar",
                       "csnat.unt.edu.ar", "artes.unt.edu.ar", "humanas.unvm.edu.ar",
                       "sociales.unvm.edu.ar", "unp.edu.ar", "upc.edu.ar", "ucalp.edu.ar",
                       "artes.unne.edu.ar", "unicen.edu.ar")
_PLANES_EN_LA_PAGINA = (("ungs.edu.ar", planes_sitios.plan_ungs), ("upc.edu.ar", planes_sitios.plan_upc), ("uns.edu.ar", planes_sitios.plan_uns),
                        ("unicen.edu.ar", planes_sitios.plan_unicen), ("unp.edu.ar", planes_sitios.plan_unpsjb),
                        ("unne.edu.ar", planes_sitios.plan_unne), ("unse.edu.ar", planes_sitios.plan_tabla_con_anios),
                        ("fcyt.uader.edu.ar", planes_sitios.plan_fcyt_uader),
                        ("uncoma.edu.ar", planes_sitios.plan_uncoma),
                        ("unt.edu.ar", planes_sitios.plan_tabla_con_anios),
                        ("fcpolit.unr.edu.ar", planes_sitios.plan_tablas_por_anio),
                        ("upso.edu.ar", planes_sitios.plan_upso), ("unvm.edu.ar", planes_sitios.plan_unvm),
                        ("ucalp.edu.ar", planes_sitios.plan_ucalp), ("unlpam.edu.ar", planes_sitios.plan_unlpam),
                        ("exactas.unsa.edu.ar", planes_sitios.plan_exa_unsa),
                        ("untdf.edu.ar", planes_sitios.plan_untdf),
                        ("unlu.edu.ar", planes_sitios.plan_unlu),
                        # UNNE Artes: a heading per year and the list under it.
                        ("artes.unne.edu.ar", planes_sitios.plan_titulo_y_lista),
                        ("natura.unsa.edu.ar", planes_sitios.plan_natura_unsa),
                        ("ing.unsa.edu.ar", planes_sitios.plan_ing_unsa),
                        ("exactas.unca.edu.ar", planes_sitios.plan_tabla_con_anios),
                        ("fba.unlp.edu.ar", planes_sitios.plan_fba_unlp),
                        ("fahce.unlp.edu.ar", planes_sitios.plan_fahce_unlp),
                        ("fbqfuntedu.ar", planes_sitios.plan_fbqf_unt),
                        ("exactas.mdp.edu.ar", planes_sitios.plan_tabla_con_anios),
                        ("ucongreso.edu.ar", planes_sitios.plan_ucongreso),
                        # The general reader, year by year, where it was
                        # checked against one career's page each (2026-09-28).
                        *((sitio, planes_sitios.plan_por_anios) for sitio in (
                            "unlc.edu.ar", "ucaece.edu.ar", "fhumyar.unr.edu.ar", "udc.edu.ar",
                            "ugr.edu.ar", "carreras.unsl.edu.ar", "upso.edu.ar", "uean.edu.ar",
                            "exa.unrc.edu.ar", "lenguas.unc.edu.ar", "med.unlp.edu.ar", "iss.edu.ar",
                            "ucu.edu.ar", "udemm.edu.ar", "unsta.edu.ar", "uda.edu.ar", "usi.edu.ar",
                            "uap.edu.ar", "uncaus.edu.ar", "unau.edu.ar", "maimonides.edu",
                            "iuriverplate.edu.ar", "uca.edu.ar", "abarbanel.edu.ar", "upatagonia.edu.ar",
                            "go.eseade.edu.ar", "um.edu.ar", "unraf.edu.ar")),
                        ("huma.unca.edu.ar", planes_sitios.plan_filas_numeradas),
                        ("derecho.unlz.edu.ar", planes_sitios.plan_cr_year),
                        ("fhycs.unam.edu.ar", planes_sitios.plan_anio_y_lista),
                        ("fce.unam.edu.ar", planes_sitios.plan_fce_unam),
                        ("unq.edu.ar", planes_sitios.plan_unq),
                        ("lenguas.unc.edu.ar", planes_sitios.plan_titulo_y_lista),
                        ("carreras.unsl.edu.ar", planes_sitios.plan_titulo_y_lista),
                        ("go.eseade.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("unsta.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("frn.unf.edu.ar", planes_sitios.plan_kt_tabs),
                        ("exa.unrc.edu.ar", planes_sitios.plan_titulo_y_lista),
                        ("hum.unrc.edu.ar", planes_sitios.plan_obligatorias),
                        ("fadu.uba.ar", planes_sitios.plan_fadu),
                        ("fhumyar.unr.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("fveter.unr.edu.ar", planes_sitios.plan_por_codigo),
                        ("umaza.edu.ar", planes_sitios.plan_titulo_y_lista),
                        ("21.edu.ar", planes_sitios.plan_ucalp), ("udemm.edu.ar", planes_sitios.plan_ucalp),
                        ("atlantida.edu.ar", planes_sitios.plan_upso),
                        ("maimonides.edu", planes_sitios.plan_texto_por_anio),
                        ("ugr.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("unsta.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("uean.edu.ar", planes_sitios.plan_titulo_y_lista),
                        ("unimoron.edu.ar", planes_sitios.plan_tabla_con_anios),
                        ("uda.edu.ar", planes_sitios.plan_upso),
                        ("unisud.edu.ar", planes_sitios.plan_titulo_y_lista),
                        ("faud.mdp.edu.ar", planes_sitios.plan_titulo_y_lista),
                        ("unraf.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("upatagonia.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("usba.edu.ar", planes_sitios.plan_titulo_y_lista),
                        ("usi.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("uap.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("musicalesysonoras.una.edu.ar", planes_sitios.plan_en_lista),
                        ("unau.edu.ar", planes_sitios.plan_titulo_y_lista),
                        ("ucema.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("barcelo.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("fono.fcm.unc.edu.ar", planes_sitios.plan_en_lista),
                        ("planesdeestudio.unnoba.edu.ar", planes_sitios.plan_unnoba),
                        ("um.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("ucaece.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("ucsf.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("fcf.unam.edu.ar", planes_sitios.plan_fcf_unam),
                        ("facfor.unam.edu.ar", planes_sitios.plan_fcf_unam),
                        ("csnat.unt.edu.ar", planes_sitios.plan_texto_por_anio),
                        ("unla.edu.ar", planes_sitios.plan_tabla_por_columna))
PAUSA = 0.7
MINIMO_SIN_ANIO = 20
MAS_POR_ANIO = 20
_VACIAS = frozenset("de del la las los el y e en a con para por licenciatura tecnicatura "
                    "universitaria carrera profesorado ingenieria ciclo".split())
# "Mat. Biológicas": an area heading over a plan's last year (UNT's
# Enfermería), not a subject.
# "(*) Régimen promocional: 9 espacios curriculares", "Anuales", "Acreditación
# de Inglés" (UDA, UNSL): a note, a heading, a requirement.
_FUERA_DEL_PLAN = re.compile(r"(?i)\(optativa\)|^t[íi]tulo\s*:|^mat\.\s|^\(\*\)|^anuales$|^acreditaci[óo]n\b"
                             # What the subject filter of the site readers also turns away.
                             r"|^\d+\s*[°º]?\s*cuatrimestre\.?$|^\d+\s+a[ñn]os(?:\s+y\s+medio)?\.?$|^(?:sub)?total$"
                             r"|^\d+\s+horas$|^(?:equipo|docentes|director(?:a)?|coordinador(?:a)?)$|^:\s"
                             # A page's address, and notes about the plan, are not subjects
                             # ("Avda. Benjamín Aráoz 800 | CP 4000", "Paseo del Bosque s/n",
                             # "Computación se podrá acreditar en cualquier momento ...").
                             r"|\bavda\.|\bcp\s*\d{4}\b|\bs/n\b|se podr[áa]n?\s+acreditar|^extracurricular\b"
                             r"|^electivas:\s")


def _nombra(texto: str, carrera: str) -> bool:
    palabras = set(re.findall(r"[a-z0-9]+", comparison_key(texto)))
    propias = [p for p in re.findall(r"[a-z0-9]+", comparison_key(carrera)) if p not in _VACIAS]
    return all(p in palabras for p in propias)


_TITULO_DE_CARRERA = re.compile(r"(?i)^(licenciatura|profesorado|traductorado|tecnicatura|ingenier[íi]a|"
                                r"t[ée]cnic[oa]|analista|contador|abogac[íi]a)\b")


def _es_de_otra_carrera(html: str, carrera: str) -> bool:
    # (UNC's Lenguas titles its pages with an <h1-parallax>.)
    titulo = BeautifulSoup(html or "", "html.parser").find(re.compile(r"^h1"))
    texto = clean_text(titulo.get_text(" ")) if titulo else ""
    return bool(_TITULO_DE_CARRERA.match(texto) and len(texto) < 120 and not _nombra(texto, carrera))


# A word the PDF broke at the end of a line: "Alimen- tos".
_PALABRA_PARTIDA = re.compile(r"(\w)- (?=[a-záéíóúñ])")
_TERMINA_CORTADA = re.compile(r"(?i)\s(de|del|la|las|los|el|y|e|o|u|en|con|para|por|a|al)$")


_PLAN_EN_UN_MARCO = (("fhycs.unju.edu.ar", planes_sitios.plan_list_group),)
_PLAN_EN_OTRA_PAGINA = (("facet.unt.edu.ar", "programas", planes_sitios.plan_en_lista),
                        ("ucalp.edu.ar", "plan de estudio", planes_sitios.plan_ucalp),
                        # UNSa's Económicas: the career's first plan listed, its newest.
                        ("economicas.unsa.edu.ar", re.compile(r"/carreras/[^/]+/item/\d+$"), planes_sitios.plan_eco_unsa),
                        # UNLP Naturales: the career's plan on a page under its own.
                        ("fcnym.unlp.edu.ar", "plan de estudios", planes_sitios.plan_fcnym),
                        # ISALUD: the career's plan on a page of its own.
                        ("isalud.edu.ar", "plan de estudios", planes_sitios.plan_isalud),
                        # UNNOBA: its plans system, the Junín campus' whole plan.
                        ("elegi.unnoba.edu.ar", re.compile(r"planesdeestudio\.unnoba\.edu\.ar/\?planversion="),
                         planes_sitios.plan_unnoba))


def _plan_del_menu(visitante: Any, html: str, url: str, host: str) -> tuple[list, str] | None:
    """The plan a page of the site's menu lists ("Programas", "Programas
    Analíticos"), from the career's page or from the career's own site it
    links ("Sitio web de la carrera")."""
    for dominio, texto, lector in _PLAN_EN_OTRA_PAGINA:
        if not host.endswith(dominio):
            continue
        for _ in range(2):
            enlaces = BeautifulSoup(html or "", "html.parser").find_all("a", href=True)
            # The link is named by its text, or by its address (a pattern).
            pagina = next((urljoin(url, a["href"]) for a in enlaces
                           # (Under the career's own address, or on the other site the pattern names.)
                           if (texto.search(a["href"]) and (urljoin(url, a["href"]).startswith(url.rstrip("/") + "/")
                                                            or urlparse(urljoin(url, a["href"])).netloc != urlparse(url).netloc)
                               if isinstance(texto, re.Pattern)
                               else clean_text(a.get_text(" ")).lower().startswith(texto))), None)
            if pagina:
                materias = lector(visitante.get(pagina))
                time.sleep(PAUSA)
                return (materias, pagina) if materias else None
            sitio = next((urljoin(url, a["href"]) for a in enlaces
                          if clean_text(a.get_text(" ")).lower() == "sitio web de la carrera"), None)
            if not sitio:
                return None
            url, html = sitio, visitante.get(sitio)
            time.sleep(PAUSA)
    return None


# Universities whose plan documents are laid out their own way, read from
# the text as ``pdftotext -layout`` gives it.
_DOCUMENTOS_PROPIOS = (("unahur.edu.ar", planes_sitios.plan_unahur), ("ucse.edu.ar", planes_sitios.plan_ucse), ("fio.unam.edu.ar", planes_sitios.plan_fio_unam),
                       ("ucasal.edu.ar", planes_sitios.plan_ucasal),
                       ("fodonto.unr.edu.ar", planes_sitios.plan_por_codigo_en_texto),
                       # UNSJ's Filosofía: SIU Guaraní's plan report.
                       ("ffha.unsj.edu.ar", planes_sitios.plan_siu_guarani),
                       # The Hospital Italiano's university: its plans are on the hospital's site.
                       ("hiba.hospitalitaliano.org.ar", planes_sitios.plan_uhiba),
                       ("iucbc.edu.ar", planes_sitios.plan_iucbc),
                       ("universidad-policial.edu.ar", planes_sitios.plan_iupfa),
                       ("unpilar.edu.ar", planes_sitios.plan_unpilar),
                       ("ude.edu.ar", planes_sitios.plan_ude),
                       # UNLP Ingeniería: the plan its system prints (plan.php?carrera=...).
                       ("ing.unlp.edu.ar", planes_sitios.plan_ing_unlp),
                       ("filo.unt.edu.ar", planes_sitios.plan_filo_unt))
# Sites that link the plan's document by a word of their own (UNaM's
# Ingeniería: "Plan de Estudios: Resumido | Completo").
_DOCUMENTO_POR_SU_ENLACE = (("fio.unam.edu.ar", "resumido"),
                            ("carreras.hospitalitaliano.edu.ar", "descargá el plan de estudios"),
                            ("unpilar.edu.ar", "plan de la licenciatura"),
                            # The Federal Police's: or by its address ("pdf/PlanesEstudio/plan-Abogacia-...").
                            ("universidad-policial.edu.ar", re.compile(r"(?i)/PlanesEstudio/plan[_-]")),
                            ("ing.unlp.edu.ar", re.compile(r"asignaturas/plan\.php\?carrera=")),
                            # UNT Filosofía: the career's brochure has its plan.
                            ("filo.unt.edu.ar", re.compile(r"/folleto_[^/]+\.pdf$")))


def _documento_por_su_enlace(html: str, url: str, host: str) -> str | None:
    for dominio, texto in _DOCUMENTO_POR_SU_ENLACE:
        if host.endswith(dominio):
            return next((urljoin(url, a["href"]) for a in BeautifulSoup(html or "", "html.parser").find_all("a", href=True)
                         if (texto.search(a["href"]) if isinstance(texto, re.Pattern)
                             else clean_text(a.get_text(" ")).lower() == texto)), None)
    return None


def _leer_documento(archivo: Path, documento: str) -> list[tuple[str, int | None]]:
    host = urlparse(documento).netloc.removeprefix("www.")
    for dominio, lector in _DOCUMENTOS_PROPIOS:
        if host.endswith(dominio):
            import subprocess

            # A reader of a table's cells takes the text's boxes (``-bbox-layout``).
            modo = "-bbox-layout" if getattr(lector, "cajas", False) else "-layout"
            try:
                texto = subprocess.run(["pdftotext", modo, str(archivo), "-"], capture_output=True,
                                       text=True, timeout=60).stdout
            except Exception:
                return []
            return [m for m in lector(texto) if not _FUERA_DEL_PLAN.search(m[0])]
    return _leer(archivo)


def _leer(archivo: Path) -> list[tuple[str, int | None]]:
    # A Ministry resolution's annex (DNGU's table) has a reader of its own;
    # the general ones split its centred names ("Introducción a la" / "Computación").
    import subprocess

    try:
        texto = subprocess.run(["pdftotext", "-layout", str(archivo), "-"], capture_output=True,
                               text=True, timeout=60).stdout
    except Exception:
        texto = ""
    if "DNGU" in texto and "ASIGNATURA" in texto:
        return [m for m in planes_sitios.plan_dngu(texto) if not _FUERA_DEL_PLAN.search(m[0])]
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
    # A completion cycle ("Licenciatura en Administración (CCC)") is part of
    # a degree: UNQ's page for it shows the whole degree's plan.
    if re.search(r"(?i)\(ccc\)|complementaci[óo]n curricular", carrera):
        return False
    # ("Seminario A", "Optativa B": a capital alone is a label, not a cut "a".)
    if len(materias) < 10 or any(nombre[:1].islower() or (_TERMINA_CORTADA.search(nombre)
                                                          and not re.search(r"\s[A-Z]$", nombre))
                                 for nombre, _ in materias):
        return False
    anios = [anio for _, anio in materias if anio]
    if not anios:
        return len(materias) >= MINIMO_SIN_ANIO
    # A plan with its first year, or a year between, missing is a part of
    # the plan (the UNNE's Abogacía from its second year).
    if set(anios) != set(range(1, max(anios) + 1)):
        return False
    # More than twenty subjects in one year is the pool of electives listed
    # under the last year (Río Cuarto's Psicopedagogía: 52 in the fourth).
    if max(Counter(anios).values()) > MAS_POR_ANIO:
        return False
    if comparison_key(carrera).startswith("tecnicatura") and max(anios) > 3:
        return False
    # Terms counted as years: UNL's design pages run to a "seventh year" of
    # a four-year degree. No degree here runs past six (Medicina).
    if max(anios) > 6 or (duracion and max(anios) > math.ceil(duracion) + 1):
        return False
    # Two years with a single subject each are what a profesorado adds to
    # a licenciatura it shares its subjects with (UNS: only the teaching
    # practice from the second year on).
    if sum(1 for veces in Counter(anios).values() if veces == 1) >= 2:
        return False
    if duracion and max(anios) < math.ceil(duracion) - 1:
        return False
    # A short career has no final year of thesis alone: a two-year
    # tecnicatura whose plan stops in the first is half of it.
    if duracion and duracion <= 3 and max(anios) < math.ceil(duracion):
        return False
    # Without a duration, a degree (not a cycle, not a tecnicatura) runs at
    # least four years: UNQ's Informática page lists the first three alone.
    clave = comparison_key(carrera)
    if not duracion and not clave.startswith(("ciclo", "tecnicatura")) and max(anios) < 4:
        return False
    # A licenciatura, Abogacía, an engineering, Medicina or a profesorado
    # stopping in its third year is its first cycle, whatever duration the
    # career carries (UDA's Abogacía and Administración were stored at three).
    if re.match(r"(?:licenciatura|abogacia|ingenieria|arquitectura|medicina|profesorado)\b", clave) \
            and not re.search(r"ciclo|complementaci|para profesionales", clave) and max(anios) < 4:
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
    # Beside the plan, the resolution that approved it names the career too
    # (UNAHUR: "Licenciatura-en-Nutricion.pdf", "RES-1468-21-LIC-EN-NUTRICION.pdf"):
    # the plan is the one that is not a resolution, a FAQ or the prerequisites.
    if len(candidatos) > 1:
        candidatos = {url for url in candidatos if not re.match(
            r"(?i)(res|resoluci[oó]n|di|rm|rcs|disp)[-_ ]|.*preguntas|.*correlativ",
            unquote(urlparse(url).path.rsplit("/", 1)[-1]))}
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
            # A career whose own address is its plan's document (UNCA Exactas: ".../tcd.pdf").
            if urlparse(url).path.lower().endswith(".pdf"):
                archivo = CACHE / (hashlib.md5(url.encode()).hexdigest() + ".pdf")
                if not archivo.exists():
                    try:
                        respuesta = visitante.client.get(url)
                        archivo.write_bytes(respuesta.content if respuesta.status_code == 200 else b"")
                    except Exception:
                        archivo.write_bytes(b"")
                    time.sleep(PAUSA)
                documento_de[carrera["id"]] = url
                continue
            html = visitante.get(url)
            time.sleep(PAUSA)
            # A guide that links a career to another's page (UNC's links its
            # Licenciatura en Lengua y Literatura Italianas to the Inglesas'):
            # the page's own title names the other one, and its plan is not
            # this career's.
            if _es_de_otra_carrera(html, carrera["nombre_carrera"]):
                continue
            # A page that shows the plan in a frame of another page (UNJu's
            # Humanidades: <iframe src="carreras/LicLetras.html">).
            marco = next((lector for dominio, lector in _PLAN_EN_UN_MARCO if host.endswith(dominio)), None)
            iframe = BeautifulSoup(html or "", "html.parser").find("iframe", src=True) if marco else None
            if iframe:
                pagina = urljoin(url, iframe["src"])
                del_marco = marco(visitante.get(pagina))
                time.sleep(PAUSA)
                if del_marco:
                    de_la_pagina[carrera["id"]], pagina_del_plan[carrera["id"]] = del_marco, pagina
                    continue
            # A site that lists the plan on a page of its own menu (the
            # FACET's "Programas"), maybe from the career's own site.
            del_menu = _plan_del_menu(visitante, html, url, host)
            if del_menu:
                de_la_pagina[carrera["id"]], pagina_del_plan[carrera["id"]] = del_menu
                continue
            en_la_pagina = _de_la_pagina(html)
            # The UNL lays its plan out as a list of bullets, without years.
            if not en_la_pagina and host.endswith("unl.edu.ar"):
                en_la_pagina = [(materia, None) for materia in unl.leer_plan(html)]
            # The UNCuyo, year by year and term by term.
            if not en_la_pagina and host.endswith("uncuyo.edu.ar"):
                en_la_pagina = uncuyo.leer_plan(html)
            # Universities that lay the plan out their own way on the page:
            # their reader knows it better than the general one (which read
            # UNLZ Derecho's hours as a plan).
            # Of two readers of one site, the later one's reading, unless only
            # the other's is the whole plan (UNR Piano: the text reader stops
            # in the third year, the year one reads all five).
            lecturas = []
            for dominio, lector in _PLANES_EN_LA_PAGINA:
                if host.endswith(dominio):
                    lecturas += [leido for leido in [lector(html)] if leido]
            enteras = [leido for leido in lecturas if _parece_el_plan_entero(
                carrera["nombre_carrera"], leido, carrera.get("duracion_anios"))]
            en_la_pagina = (enteras or lecturas or [en_la_pagina])[-1]
            # Where the site's own reader finds nothing, the general one, year
            # by year, on the sites it was checked on.
            if not en_la_pagina and any(host.endswith(d) for d in _RESPALDO_POR_ANIOS):
                en_la_pagina = planes_sitios.plan_por_anios(html)
            if en_la_pagina:
                de_la_pagina[carrera["id"]] = en_la_pagina
                continue
            # A page that links its plans as pages of their own, by year
            # ("Plan de estudios 2025", the UNC's engineering faculty): the
            # newest is read.
            # Or links one page as its plan ("plan de estudios", Sociales and
            # the FAUD of the UNC), which says it the way a page does.
            # The newest plan the page links, if it is this career's: a menu
            # links every career's plans (the UNLPam's gave Biología the
            # Química plan of 2023).
            nuevo = plan_mas_nuevo(html, url)
            propia = [p for p in urlparse(url).path.split("/") if len(p) > 5]
            if nuevo and propia and propia[-1] not in nuevo:
                nuevo = None
            nuevo = nuevo or _enlace_al_plan(html, url, dominios)
            if nuevo:
                html_del_plan = visitante.get(nuevo)
                time.sleep(PAUSA)
                del_plan = _de_la_pagina_del_plan(html_del_plan)
                otro_host = urlparse(nuevo).netloc.removeprefix("www.")
                for dominio, lector in _PLANES_EN_LA_PAGINA:
                    if not del_plan and otro_host.endswith(dominio):
                        del_plan = lector(html_del_plan)
                if del_plan:
                    de_la_pagina[carrera["id"]] = del_plan
                    pagina_del_plan[carrera["id"]] = nuevo
                    continue
            # A site's own rule for its plan's link goes first: it is the
            # one that knows (UNLP Ingeniería's page also links a PDF named
            # after the career: its profile).
            documento = (_documento_por_su_enlace(html, url, host)
                         or _documento_del_plan(html, url, dominios)
                         or _documento_con_su_nombre(html, url, carrera["nombre_carrera"]))
            if not documento:
                enlace = _enlace_al_plan(html, url, dominios)
                if enlace:
                    documento = _documento_del_plan(visitante.get(enlace), enlace, dominios)
                    time.sleep(PAUSA)
            if not documento:
                continue
            # A page over https that links its plan over http, on its own
            # site (UNSJ's Filosofía, whose http does not answer).
            if (url.startswith("https://") and documento.startswith("http://")
                    and urlparse(documento).netloc == urlparse(url).netloc):
                documento = "https://" + documento.removeprefix("http://")
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
        materias = [m for m in de_la_pagina.get(carrera["id"]) or [] if not _FUERA_DEL_PLAN.search(m[0])]
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
        materias = _leer_documento(archivo, documento)
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
    if args.apply:
        guardar_las_fuentes(planes.values())
    print(f"Planes: {len(planes)} {dict(por_universidad)}; materias "
          f"{'cargadas' if args.apply else 'a cargar'}: {len(filas)}", flush=True)


def guardar_las_fuentes(planes: Any) -> None:
    """The page or document each plan was read from, kept where the
    verifier looks for it (``data/<university>_planes.json``): a plan read
    from a page the career's own does not link directly (a menu's) is
    verified there."""
    por_universidad: dict[str, dict[str, str]] = defaultdict(dict)
    for plan in planes:
        if plan.get("documento"):
            por_universidad[plan["universidad"].lower()][plan["carrera"]["nombre_carrera"]] = plan["documento"]
    for corto, fuentes in por_universidad.items():
        archivo = Path("data") / f"{corto}_planes.json"
        datos = json.loads(archivo.read_text()) if archivo.exists() else {}
        otros = [p for p in datos.get("planes") or [] if p.get("nombre") not in fuentes]
        datos["planes"] = otros + [{"nombre": nombre, "url": url} for nombre, url in sorted(fuentes.items())]
        archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
