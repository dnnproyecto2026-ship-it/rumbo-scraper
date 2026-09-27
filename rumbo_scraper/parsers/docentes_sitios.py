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


# Sigla -> [(page, reader)]
FUENTES = {
    "UBA": [("https://www.psi.uba.ar/profesores.php?var=profesores/profesores_regulares.php", psicologia_uba)],
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
                clave = comparison_key(materia)
                comision = comisiones.setdefault(clave, {
                    "materia": materia, "codigo": "web-" + clave.replace(" ", "-")[:80],
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
