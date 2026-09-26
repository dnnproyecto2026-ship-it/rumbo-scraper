"""The careers of the Universidad Nacional de Tucumán, from Expo UNT.

The UNT's "Expo UNT" has a page per faculty and school, and each lists its
careers as links to the faculty's page for each, with the years it takes:

    <a href="https://www.facet.unt.edu.ar/ingenieria-industrial/">Ingeniería Industrial - 5 años</a>

A grado career of fewer than three years is a completion cycle for those who
hold a degree or teach already ("Profesorado en Ciencias Económicas - 2
Años"), not a career to start from secondary school, and is left out.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers.unc import CarreraDeLaGuia

INDICE = "https://www.unt.edu.ar/expount/facultades-y-escuelas/"
UNIDADES = ("escuela-de-bellas-artes", "escuela-de-cine-video-y-television",
            "escuela-y-liceo-vocacional-sarmiento", "facultad-de-agronomia-zootecnia-y-veterinaria",
            "facultad-de-arquitectura-y-urbanismo", "facultad-de-artes",
            "facultad-de-bioquimica-quimica-y-farmacia", "facultad-de-ciencias-economicas",
            "facultad-de-ciencias-exactas-y-tecnologia", "facultad-de-ciencias-naturales",
            "facultad-de-derecho", "facultad-de-educacion-fisica", "facultad-de-medicina",
            "facultad-de-odontologia", "facultad-de-psicologia", "filosofia-y-letras",
            "instituto-superior-de-musica", "instituto-tecnico")
_CARRERA = re.compile(
    r"^(?P<nombre>.+?)\s*-\s*(?P<anios>\d+(?:[.,]\d)?)(?P<medio>\s*y\s+medio)?\s*a[ñn]os?\b"
    r"(?P<medio_despues>\s*y\s+medio)?", re.I)
_PREGRADO = re.compile(r"(?i)^(?:tecnicatura|t[ée]cnic[oa]|analista|enfermer[ií]a universitaria)\b")


def tipo_de_unidad(nombre: str) -> str:
    clave = nombre.lower()
    for prefijo, tipo in (("facultad", "Facultad"), ("escuela", "Escuela"), ("instituto", "Instituto")):
        if clave.startswith(prefijo):
            return tipo
    return "Facultad"


def leer_unidad(html: str, pagina: str) -> list[CarreraDeLaGuia]:
    soup = BeautifulSoup(html or "", "html.parser")
    titulo = clean_text(soup.title.get_text(" ")) if soup.title else ""
    unidad = clean_text(re.split(r"\s+[–-]\s+Expo UNT", titulo)[0])
    if not unidad or "no se encontr" in unidad.lower():
        return []
    carreras = []
    for enlace in soup.find_all("a", href=True):
        carrera = _CARRERA.match(clean_text(enlace.get_text(" ")))
        if not carrera:
            continue
        nombre = clean_text(carrera.group("nombre"))
        anios = float(carrera.group("anios").replace(",", ".")) + (0.5 if carrera.group("medio") or carrera.group("medio_despues") else 0)
        nivel = "Pregrado" if _PREGRADO.match(nombre) else "Grado"
        if nivel == "Grado" and anios < 3:
            continue
        carreras.append(CarreraDeLaGuia(
            nombre, unidad, tipo_de_unidad(unidad), urljoin(pagina, enlace["href"].strip()),
            nivel, None, anios))
    return carreras
