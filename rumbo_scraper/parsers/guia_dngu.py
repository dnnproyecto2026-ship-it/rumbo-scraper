"""The national guide of university degrees (Dirección Nacional de Gestión
Universitaria, guiadecarreras.siu.edu.ar): every degree each university
and university institute gives, with its unit, type and length.

The guide is a SIU-Toba application. Its search form opens a results page
whose address is the form's link plus each filter as a parameter; a filter
left empty must be left out (the guide's query does not take an empty one).
One request per institution, unhurried.

    python -m rumbo_scraper.parsers.guia_dngu    # writes data/guia_dngu.json
"""

from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text

GUIA = "https://guiadecarreras.siu.edu.ar/ciie_ofertas/2.0/guia_grado.php"
SALIDA = Path("data/guia_dngu.json")
PAUSA = 3.0
COLUMNAS = ["universidad", "facultad", "titulo", "tipo", "duracion", "ingreso", "domicilio",
            "telefono", "web", "mail"]


def instituciones(pagina: str) -> dict[str, str]:
    """The institutions the guide's form offers, by its code."""
    combo = pagina[pagina.find("filtroinstitucion'"):]
    combo = combo[:combo.find("</select>")]
    return {codigo: clean_text(html.unescape(nombre))
            for codigo, nombre in re.findall(r"<option value='([^']*)'[^>]*>([^<]*)", combo)
            if codigo != "nopar"}


def enlace_de_resultados(pagina: str) -> str:
    """The results page the form's "Buscar" opens (a link of this session)."""
    return re.search(r"agregar_vinculo\('0',\{'url': '([^']+)'", pagina).group(1)


def titulos(pagina: str) -> list[dict[str, str]]:
    """The rows of a results page: one degree each."""
    soup = BeautifulSoup(pagina, "html.parser")
    filas = []
    for tr in soup.find_all("tr"):
        celdas = [clean_text(td.get_text(" ")) for td in tr.find_all("td", recursive=False)]
        if len(celdas) == len(COLUMNAS) and celdas[2] and celdas[0] != "Universidad":
            filas.append(dict(zip(COLUMNAS, celdas)))
    return filas


def leer() -> list[dict[str, Any]]:
    from rumbo_scraper.spiders.visitante import Visitante

    salida: list[dict[str, Any]] = []
    with Visitante(timeout=60) as visitante:
        formulario = visitante.client.get(GUIA).text
        base = "https://guiadecarreras.siu.edu.ar" + enlace_de_resultados(formulario)
        for codigo, nombre in instituciones(formulario).items():
            respuesta = visitante.client.get(f"{base}&institucion={codigo}&nivel=1")
            filas = titulos(respuesta.text)
            print(f"{nombre[:60]:60} {len(filas):4}", flush=True)
            salida += [{"codigo": codigo, **fila} for fila in filas]
            time.sleep(PAUSA)
    return salida


def main() -> None:
    filas = leer()
    SALIDA.write_text(json.dumps(filas, ensure_ascii=False, indent=1) + "\n")
    print(f"Títulos: {len(filas)} → {SALIDA}")


if __name__ == "__main__":
    main()
