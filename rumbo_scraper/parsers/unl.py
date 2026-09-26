"""The careers of the Universidad Nacional del Litoral, from its catalogue.

The UNL's "Propuesta Académica" lists its careers by academic unit
(``?i=<id>``), under a heading per level ("Pregrado", "Grado", "Posgrado"),
each as a card that says where it is taught and links its page:

    <p><strong>CURA </strong>- Reconquista</p>
    <p class="titulo_ua"><a href="https://www.unl.edu.ar/carreras/...">Licenciatura en ...</a></p>

The site's own menu names each unit in full ("FICH" is "Facultad de
Ingeniería y Ciencias Hídricas"), and each career page lays out its plan as
a list of subjects, one per bullet, under "plan de estudios".
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers.unc import CarreraDeLaGuia

CATALOGO = "https://www.unl.edu.ar/propuesta-academica/?i={}"
# The units of the catalogue's filter, by the id it gives them.
UNIDADES = {1: "FCE", 2: "FADU", 3: "FBCB", 4: "FCA", 5: "FCJS", 6: "FCM", 7: "FCV",
            8: "FHUC", 9: "FIQ", 10: "FICH", 11: "CURA", 12: "CU-GA", 13: "CURS",
            14: "ESS", 15: "ISM"}
_NIVELES = {"pregrado": "Pregrado", "grado": "Grado"}
# A completion cycle takes a student who holds a degree already, and the
# initial stretch of a career taught at a regional centre is not a career.
_NO_ES_PARA_EMPEZAR = re.compile(r"(?i)^(?:ciclo de|trayecto curricular)")


def nombre_de_la_unidad(html: str, sigla: str) -> str:
    """The unit's full name, as the site's menu gives it in the link's title."""
    for enlace in BeautifulSoup(html or "", "html.parser").find_all("a", title=True):
        if clean_text(enlace.get_text(" ")) == sigla:
            return clean_text(enlace["title"]).replace(" / ", " ")
    return sigla


def tipo_de_unidad(nombre: str) -> str:
    clave = nombre.lower()
    for prefijo, tipo in (("facultad", "Facultad"), ("escuela", "Escuela"),
                          ("instituto", "Instituto"), ("centro", "Centro")):
        if clave.startswith(prefijo):
            return tipo
    return "Facultad"


def leer_unidad(html: str, pagina: str, sigla: str) -> list[CarreraDeLaGuia]:
    """The pregrado and grado careers the catalogue lists for one unit."""
    soup = BeautifulSoup(html or "", "html.parser")
    unidad = nombre_de_la_unidad(html, sigla)
    carreras = []
    nivel = None
    for elemento in soup.find_all(True):
        clases = elemento.get("class") or []
        if "cabecera_nivel_carrera" in clases:
            nivel = _NIVELES.get(clean_text(elemento.get_text(" ")).lower())
            continue
        if "text_ua_box" not in clases or not nivel:
            continue
        enlace = elemento.find("a", class_="linko-carrera", href=True)
        lugar = elemento.find("p")
        if not enlace:
            continue
        nombre = clean_text(enlace.get_text(" "))
        # A cycle the card names as a licenciatura still says what it is in
        # its address: ".../ciclo-de-licenciatura-en-...".
        if not nombre or _NO_ES_PARA_EMPEZAR.match(nombre) or "/ciclo-" in enlace["href"]:
            continue
        # "UNL - SANTA FE", "CURA - Reconquista": the place follows the dash.
        sede = clean_text(lugar.get_text(" ").split("-", 1)[-1]).title() if lugar else None
        carreras.append(CarreraDeLaGuia(
            nombre, unidad, tipo_de_unidad(unidad),
            urljoin(pagina, enlace["href"].strip().split("?")[0]), nivel, sede or None))
    return carreras


_VINETA = re.compile(r"^[•·▪◦]\s*")
_FIN_DEL_PLAN = re.compile(r"(?i)^(?:además de|consulte|consultá)")


def leer_plan(html: str) -> list[str]:
    """The subjects a UNL career page lists under "plan de estudios", one
    per bullet; the cycle headings between them are not subjects."""
    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup.find_all(["script", "style", "nav", "header", "footer"]):
        parte.decompose()
    materias: list[str] = []
    dentro = False
    for linea in soup.get_text("\n").split("\n"):
        linea = clean_text(linea)
        if not linea:
            continue
        if linea.lower() == "plan de estudios":
            dentro = True
            continue
        if not dentro:
            continue
        if _FIN_DEL_PLAN.match(linea):
            break
        if _VINETA.match(linea):
            materia = clean_text(_VINETA.sub("", linea))
            if materia and materia not in materias:
                materias.append(materia)
    return materias
