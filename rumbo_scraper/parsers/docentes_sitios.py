"""Teaching staff that universities publish as lists, one reader per source.

Each reader takes the page and returns ``[(subject, teacher, role)]``;
`main` groups them by subject into the file `database.cargar_docentes` loads:

- UBA, Psicología: the table of regular professors (Profesor | Cargo |
  Asignatura | Carrera). Emeritus professors hold no chair.
- UTN, Córdoba, Sistemas: a panel per teacher, each subject with its role
  ("Sistemas Operativos (Plan 2023):Adjunto Interino").

    python -m rumbo_scraper.parsers.docentes_sitios UBA
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import defaultdict
from pathlib import Path

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text, comparison_key


def _texto(elemento) -> str:
    return clean_text(elemento.get_text(" ")) if elemento else ""


def psicologia_uba(html: str) -> list[tuple[str, str, str]]:
    filas = []
    for fila in BeautifulSoup(html or "", "html.parser").select("table tr"):
        celdas = [_texto(c) for c in fila.find_all("td")]
        if len(celdas) == 4 and celdas[2] and celdas[0].lower() != "profesor" \
                and not re.match(r"(?i)em[ée]rit", celdas[1]):
            filas.append((celdas[2], celdas[0], celdas[1]))
    return filas


def sistemas_frc(html: str) -> list[tuple[str, str, str]]:
    filas = []
    for encabezado in BeautifulSoup(html or "", "html.parser").select("div.panel-heading.item-search"):
        nombre = _texto(encabezado.find("strong") or encabezado)
        cuerpo = encabezado.find_next("div", class_="panel-body")
        for li in cuerpo.find_all("li") if cuerpo else []:
            materia, _, rol = _texto(li).rpartition(":")
            materia = re.sub(r"\s*\(Plan \d+\)\s*$", "", materia or rol)
            if materia:
                filas.append((materia, nombre, rol if _ else ""))
    return filas


def fau_unt(html: str) -> list[tuple[str, str, str]]:
    """UNT, Arquitectura: a row of one cell names the subject, and the rows
    after it its teachers (APELLIDO | Nombre | Cargo)."""
    filas, materia = [], None
    for fila in BeautifulSoup(html or "", "html.parser").select("table tr"):
        celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
        llenas = [c for c in celdas if c]
        if len(llenas) == 1:
            materia = llenas[0]
        elif len(celdas) >= 3 and materia and celdas[0] and celdas[0].lower() != "apellido":
            filas.append((materia, f"{celdas[0]}, {celdas[1]}", celdas[2]))
    return filas


_ROL_ENTRE_PARENTESIS = re.compile(r"^\(([A-ZÁÉÍÓÚ. ]+)\)\s*(.+)$")


def asignaturas_facet(html: str) -> list[tuple[str, str, str]]:
    """UNT, FACET career sites: AÑO | MÓDULO | ASIGNATURA | ... | DOCENTES,
    the first teacher on the subject's row and the rest on rows of their own
    ("(ADJ) COPA OCAMPO, Marina")."""
    filas, materia, columna = [], None, None
    for fila in BeautifulSoup(html or "", "html.parser").select("table tr"):
        celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
        mayusculas = [c.upper() for c in celdas]
        if "ASIGNATURA" in mayusculas and "DOCENTES" in mayusculas:
            columna = (mayusculas.index("ASIGNATURA"), mayusculas.index("DOCENTES"), len(celdas))
            continue
        if not columna:
            continue
        if len(celdas) == 1:
            docente = celdas[0]
        elif len(celdas) >= 3:
            # The year and module cells span their rows: a subject's row
            # may come without them, its cells shifted to the left.
            corrida = columna[2] - len(celdas)
            if columna[0] - corrida < 0:
                continue
            materia, docente = celdas[columna[0] - corrida], celdas[-1]
        else:
            continue
        rol = _ROL_ENTRE_PARENTESIS.match(docente)
        if materia and rol:
            filas.append((materia, rol.group(2), rol.group(1)))
    return filas


# Sigla -> [(page, reader)]
FUENTES = {
    "UBA": [("https://www.psi.uba.ar/profesores.php?var=profesores/profesores_regulares.php", psicologia_uba)],
    "UNT": [("https://www.fau.unt.edu.ar/fau/personal-docente/", fau_unt),
            ("https://www.facet.unt.edu.ar/cic/asignaturas/", asignaturas_facet)],
    "UTN": [("https://www.institucional.frc.utn.edu.ar/sistemas/Areas/Academica/Docentes.asp", sistemas_frc)],
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Leer los planteles docentes publicados")
    parser.add_argument("universidad", choices=sorted(FUENTES))
    args = parser.parse_args()

    from rumbo_scraper.spiders.visitante import Visitante

    comisiones: dict[str, dict] = {}
    with Visitante(timeout=40) as visitante:
        for pagina, lector in FUENTES[args.universidad]:
            html = visitante.get(pagina)
            time.sleep(0.6)
            for materia, docente, rol in lector(html):
                materia = re.sub(r"(?i)\s*\(\s*m[áa]s informaci[óo]n\s*\)", "", materia).strip()
                if materia.isupper():
                    from rumbo_scraper.parsers.guias_nacionales import con_tildes

                    materia = re.sub(r"\b(i{1,3}|iv|vi{0,3}|ix|x)\b", lambda m: m.group(1).upper(),
                                     con_tildes(materia), flags=re.I)
                # A subject of one faculty is not another's of the same name
                # ("Sistemas de Representación" in Arquitectura and in Civil).
                fuente = re.sub(r"[^a-z0-9]+", "-", urlparse(pagina).netloc + urlparse(pagina).path).strip("-")[-40:]
                clave = f"{fuente}:{comparison_key(materia)}"
                comision = comisiones.setdefault(clave, {
                    "materia": materia, "codigo": "web-" + (fuente + "-" + comparison_key(materia).replace(" ", "-"))[:120],
                    "anio": 2026, "seccion": "Cátedra", "fuente_url": pagina, "docentes": []})
                if all(comparison_key(d["nombre"]) != comparison_key(docente) for d in comision["docentes"]):
                    comision["docentes"].append({"nombre": docente, "rol": rol})
    Path(f"data/docentes_{args.universidad.lower()}.json").write_text(json.dumps(
        {"universidad": args.universidad, "comisiones": list(comisiones.values())},
        ensure_ascii=False, indent=1) + "\n")
    print(f"{args.universidad}: {len(comisiones)} materias, "
          f"{len({comparison_key(d['nombre']) for c in comisiones.values() for d in c['docentes']})} docentes")


if __name__ == "__main__":
    main()
