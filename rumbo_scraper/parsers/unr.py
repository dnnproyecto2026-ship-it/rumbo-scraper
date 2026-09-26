"""The grado careers of the Universidad Nacional de Rosario.

``unr.edu.ar/carreras-de-grado/`` lists every grado career under its
faculty, each a toggle whose content gives the link to its plan of studies,
the years it takes and the address where it is taught:

    <h2>Ciencias Agrarias</h2>
    <a class="elementor-toggle-title">Ingeniería Agronómica</a>
    <div class="elementor-tab-content"><p><a href="https://fcagr.unr.edu.ar/...">Plan de Estudios</a>
      <br/>Duración: 5 años<br/>Campo Experimental "José Villarino" – C.C. 14 – (2123) Zavalla ...

The address says the town: Agrarias teaches in Zavalla, Veterinarias in
Casilda, the rest in Rosario.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers.unc import CarreraDeLaGuia

GUIA = "https://unr.edu.ar/carreras-de-grado/"
_DURACION = re.compile(r"(?i)duraci[oó]n:?\s*(\d+(?:[.,]\d)?)\s*(y\s+medio)?\s*a[ñn]os?(\s+y\s+medio)?")
_LOCALIDADES = ("Zavalla", "Casilda")
_CICLO = re.compile(r"(?i)^ciclo\b|\bccc\b")


def localidad(texto: str) -> str:
    return next((lugar for lugar in _LOCALIDADES if lugar.lower() in texto.lower()), "Rosario")


def leer_guia(html: str, pagina: str = GUIA) -> list[CarreraDeLaGuia]:
    soup = BeautifulSoup(html or "", "html.parser")
    contenido = soup.find("main") or soup
    carreras: list[CarreraDeLaGuia] = []
    facultad = None
    for elemento in contenido.find_all(["h2", "div"]):
        clases = elemento.get("class") or []
        if elemento.name == "h2" and "elementor-heading-title" in clases:
            facultad = "Facultad de " + clean_text(elemento.get_text(" "))
            continue
        if "elementor-toggle-item" not in clases or not facultad:
            continue
        titulo = elemento.select_one(".elementor-toggle-title")
        detalle = elemento.select_one(".elementor-tab-content")
        if not titulo or not detalle:
            continue
        nombre = clean_text(titulo.get_text(" ").replace("​", ""))
        if not nombre or _CICLO.search(nombre):
            continue
        texto = clean_text(detalle.get_text(" "))
        plan = next((a["href"] for a in detalle.find_all("a", href=True)
                     if "plan" in clean_text(a.get_text(" ")).lower()), None)
        sitio = next((a["href"] for a in detalle.find_all("a", href=True)
                      if a["href"].startswith("http") and "plan" not in a.get_text(" ").lower()), None)
        duracion = _DURACION.search(texto)
        anios = None
        if duracion:
            anios = float(duracion.group(1).replace(",", "."))
            anios += 0.5 if duracion.group(2) or duracion.group(3) else 0
        carreras.append(CarreraDeLaGuia(
            nombre, facultad, "Facultad", urljoin(pagina, (plan or sitio or pagina).strip()),
            "Pregrado" if re.match(r"(?i)^(?:tecnicatura|t[ée]cnic[oa])\b", nombre) else "Grado",
            localidad(texto), anios))
    return carreras
