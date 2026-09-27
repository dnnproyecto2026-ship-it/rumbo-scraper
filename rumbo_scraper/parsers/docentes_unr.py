"""The chairs of the UNR's Facultad de Ciencia Política y Relaciones
Internacionales, from its course pages.

``fcpolit.unr.edu.ar/course-search/?carrera=<slug>`` lists each career's
subjects, thirty a page (``/page/2/``); each subject's page names its chair
under "Integrantes", a role per line and the people after it:

    Profesor Titular:
    Mutti, Gastón
    JTP:
    Durand, Luciano; Zampino, Martín

    python -m rumbo_scraper.parsers.docentes_unr    (writes data/docentes_unr.json)
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text

BUSQUEDA = "https://fcpolit.unr.edu.ar/course-search/{pagina}?course-keywords=&carrera={carrera}"
CARRERAS = ("ciencia-politica", "prof-de-comunicacion-educativa", "comunicacion-social",
            "licenciatura-en-gestion-universitaria", "relaciones-internacionales", "seguridad-ciudadana",
            "tecnicatura-relaciones-trabajo", "trabajo-social", "lic-en-turismo")
_ROL = re.compile(r"(?i)^(profesor(?:a)?\s+\w+|jtp|jefe de trabajos pr[áa]cticos|ayudante[^:]*|adscript[oa]s?[^:]*):$")
_FIN = re.compile(r"(?i)^(duraci[óo]n|horas semanales|carga horaria|correlatividades|horarios)")


def duracion(html: str) -> tuple[int | None, str | None]:
    """"Duración: 1° Cuatrimestre" -> (1, None); "Anual" -> (None, "anual")."""
    texto = clean_text(BeautifulSoup(html or "", "html.parser").get_text(" "))
    dicho = re.search(r"(?i)duraci[óo]n:?\s*(anual|(1|2|primer|segundo)\S*\s+cuatrimestre)", texto)
    if not dicho:
        return None, None
    if dicho.group(1).lower() == "anual":
        return None, "anual"
    return (1 if dicho.group(2).lower() in ("1", "primer") else 2), None


def leer_catedra(html: str) -> tuple[str, list[dict[str, str]]]:
    soup = BeautifulSoup(html or "", "html.parser")
    titulo = clean_text((soup.find("h1") or soup.new_tag("x")).get_text(" "))
    for parte in soup.find_all(["script", "style", "nav", "header", "footer"]):
        parte.decompose()
    lineas = [clean_text(l) for l in soup.get_text("\n").split("\n") if clean_text(l)]
    docentes, dentro, rol = [], False, None
    for linea in lineas:
        if linea == "Integrantes":
            dentro = True
            continue
        if not dentro:
            continue
        if _FIN.match(linea):
            break
        encabezado = _ROL.match(linea)
        if encabezado:
            rol = encabezado.group(1)
            continue
        if rol:
            docentes += [{"nombre": n.strip(), "rol": rol} for n in linea.split(";") if n.strip()]
    return titulo, docentes


def main() -> None:
    from rumbo_scraper.spiders.visitante import Visitante

    paginas: dict[str, str] = {}
    with Visitante(timeout=30) as visitante:
        for carrera in CARRERAS:
            for numero in range(1, 10):
                html = visitante.get(BUSQUEDA.format(pagina=f"page/{numero}/" if numero > 1 else "",
                                                     carrera=carrera))
                time.sleep(0.6)
                nuevas = {a["href"] for a in BeautifulSoup(html or "", "html.parser").find_all("a", href=True)
                          if "/course/" in a["href"]} - set(paginas)
                if not nuevas:
                    break
                paginas.update({url: carrera for url in nuevas})
        comisiones = []
        for url in sorted(paginas):
            html = visitante.get(url)
            materia, docentes = leer_catedra(html)
            time.sleep(0.6)
            semestre, anual = duracion(html)
            if materia and docentes:
                comisiones.append({"duracion": anual,"materia": materia, "codigo": "fcpolit-" + url.rstrip("/").rsplit("/", 1)[-1],
                                   "anio": 2026, "semestre": semestre, "seccion": "Cátedra",
                                   "fuente_url": url, "docentes": docentes})
    # The file also holds the chairs other readers found (`docentes_sitios`).
    archivo = Path("data/docentes_unr.json")
    otras = [c for c in (json.loads(archivo.read_text())["comisiones"] if archivo.exists() else [])
             if not c["codigo"].startswith("fcpolit-")]
    archivo.write_text(json.dumps(
        {"universidad": "UNR", "comisiones": otras + comisiones}, ensure_ascii=False, indent=1) + "\n")
    print(f"UNR: {len(paginas)} materias, {len(comisiones)} con docentes")


if __name__ == "__main__":
    main()
