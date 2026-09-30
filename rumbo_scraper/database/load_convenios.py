"""Read the exchange agreements every university publishes, and keep them out.

``convenios_intercambio.programa_origen`` is NOT NULL and holds the career a
student leaves from: Di Tella publishes its agreements one list per career,
which is where its six hundred and seventy-one rows come from. Every other
university publishes a single list for the whole institution, and that list
does not say which career each agreement is for.

An earlier version filled the column with the heading of the page the list
was on. What that put in the database was "Últimas Agendas" for thirty-five
agreements and the name of a member of staff for two others. A heading is not
a career, and choosing one would state something the university never said.

So the agreements are read and kept in the artifact, where they can be used
the day the schema has a column for an agreement of the whole university, and
they are counted as blocked rather than written.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers import vida
from rumbo_scraper.parsers.convenios import leer_convenios

USER_AGENT = "RumboScraper/0.4 (+catalogo educativo publico)"
MAX_PAGINAS = 6


def _get(client: httpx.Client, url: str) -> str:
    try:
        response = client.get(url)
        response.raise_for_status()
        if "html" not in response.headers.get("content-type", ""):
            return ""
        return response.text
    except Exception:
        return ""


def leer(universidad: dict[str, Any]) -> list[dict[str, Any]]:
    """Read the partner universities one university lists."""
    sitio = clean_text(universidad.get("sitio_web"))
    if not sitio:
        return []
    dominio = (urlparse(sitio).netloc or "").lower().removeprefix("www.")
    hallados: list[dict[str, Any]] = []
    vistos: set[str] = set()
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                      timeout=30) as client:
        inicio = _get(client, sitio)
        if not inicio:
            return []
        paginas = vida.discover_topics(inicio, sitio, dominio)["programas_internacionales"]
        # A page about exchanges links the list of partners one step further.
        for url in list(paginas[:MAX_PAGINAS]):
            html = _get(client, url)
            for fila in leer_convenios(html, url, universidad["nombre_oficial"]):
                clave = fila["universidad_destino"].lower()
                if clave not in vistos:
                    vistos.add(clave)
                    hallados.append(fila)
            if html:
                for otra, lista in vida.discover_topics(html, url, dominio).items():
                    if otra != "programas_internacionales":
                        continue
                    for extra in lista:
                        if extra not in paginas and len(paginas) < MAX_PAGINAS * 2:
                            paginas.append(extra)
        for url in paginas[MAX_PAGINAS:MAX_PAGINAS * 2]:
            for fila in leer_convenios(_get(client, url), url,
                                       universidad["nombre_oficial"]):
                clave = fila["universidad_destino"].lower()
                if clave not in vistos:
                    vistos.add(clave)
                    hallados.append(fila)
    return hallados


# Universities whose list of partners is read from the source it is published
# in, each with its own reader: a page grouped by country (Palermo), a
# brochure in columns (UB), a table by country with each partner's city
# (UADE, grado and posgrado). Written to ``data/convenios_universidad.json``,
# which the export adds as agreements of the whole university.
FUENTES_PROPIAS: dict[str, list[tuple[str, str]]] = {
    "Universidad de Palermo": [
        ("pagina_por_pais", "https://www.palermo.edu/estudiantes_internacionales/vinculaciones.html")],
    "Universidad de Belgrano": [
        ("folleto_en_columnas", "https://ub.edu.ar/sites/default/files/movilidad_internacional.pdf")],
    "Universidad Argentina de la Empresa": [
        ("tabla_por_pais", "https://www.uade.edu.ar/media/j2gofmnw/grado-convenios-vf.pdf"),
        ("tabla_por_pais", "https://www.uade.edu.ar/media/pv4pfdap/posgrado-convenios-uade-1.pdf")],
}
PROPIOS = Path("data/convenios_universidad.json")


def leer_propios(nombre_oficial: str) -> list[dict[str, Any]]:
    """The partners of one university from its own sources, without repeats."""
    import subprocess
    import tempfile

    from bs4 import BeautifulSoup

    from rumbo_scraper.parsers.convenios import (leer_json_ld, leer_por_pais, leer_tabla_por_pais,
                                                 lineas_por_columnas)
    from rumbo_scraper.normalizers.text import comparison_key

    hallados: list[dict[str, Any]] = []
    vistos: set[str] = set()
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60) as client:
        for forma, url in FUENTES_PROPIAS[nombre_oficial]:
            respuesta = client.get(url)
            respuesta.raise_for_status()
            if forma == "pagina_por_pais":
                soup = BeautifulSoup(respuesta.text, "html.parser")
                for sobra in soup(["script", "style", "nav", "header", "footer"]):
                    sobra.decompose()
                filas = (leer_por_pais(soup.get_text("\n").split("\n"), url, nombre_oficial)
                         + leer_json_ld(respuesta.text, url))
            else:
                with tempfile.NamedTemporaryFile(suffix=".pdf") as archivo:
                    archivo.write(respuesta.content)
                    archivo.flush()
                    if forma == "folleto_en_columnas":
                        filas = leer_por_pais(lineas_por_columnas(archivo.name), url, nombre_oficial)
                    else:
                        texto = subprocess.run(["pdftotext", "-layout", archivo.name, "-"],
                                               capture_output=True, text=True, timeout=60).stdout
                        filas = leer_tabla_por_pais(texto, url, nombre_oficial)
            for fila in filas:
                clave = comparison_key(fila["universidad_destino"])
                if clave not in vistos:
                    vistos.add(clave)
                    hallados.append(fila)
    return hallados


def aplicar(client: Any, universidad: dict[str, Any],
            convenios: list[dict[str, Any]]) -> int:
    """Nothing is written: see the module docstring. Kept so the day the
    schema can hold a university-wide agreement, only this changes."""
    return 0


def _aplicar_cuando_haya_columna(client: Any, universidad: dict[str, Any],
                                 convenios: list[dict[str, Any]]) -> int:
    ya = client.table("convenios_intercambio").select("id").eq(
        "universidad_id", universidad["id"]).limit(1).execute().data
    convenios = [c for c in convenios if c.get("programa")]
    if ya or not convenios:
        return 0
    filas = [{"universidad_id": universidad["id"], "programa_origen": c["programa"],
              "universidad_destino": c["universidad_destino"], "ciudad": None,
              "pais": c["pais"], "latitud": None, "longitud": None,
              "observaciones": None, "fuente_url": c["fuente"],
              "carrera_id": None, "posgrado_id": None} for c in convenios]
    for start in range(0, len(filas), 100):
        client.table("convenios_intercambio").insert(filas[start:start + 100]).execute()
    return len(filas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Completar los convenios de intercambio")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    parser.add_argument("--output", type=Path, default=Path("data/convenios.json"))
    parser.add_argument("--propios", action="store_true",
                        help=f"Leer las fuentes revisadas una por una y guardarlas en {PROPIOS}")
    args = parser.parse_args()

    if args.propios:
        todo_propio = json.loads(PROPIOS.read_text()) if PROPIOS.exists() else {}
        for nombre in FUENTES_PROPIAS:
            todo_propio[nombre] = leer_propios(nombre)
            print(f"{nombre}: {len(todo_propio[nombre])} universidades de destino")
        PROPIOS.write_text(json.dumps(todo_propio, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    client = get_supabase_client()
    todo: dict[str, Any] = {}
    for universidad in select_all(client.table("universidades").select("*")):
        convenios = leer(universidad)
        todo[universidad["nombre_oficial"]] = convenios
        if not convenios:
            continue
        print(f'{universidad["nombre_oficial"]}: leídos {len(convenios)} | '
              f'bloqueados por programa_origen: {len(convenios)}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(todo, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print("LEÍDO. Nada se escribe: la lista no dice para qué carrera es cada convenio.")


if __name__ == "__main__":
    main()
