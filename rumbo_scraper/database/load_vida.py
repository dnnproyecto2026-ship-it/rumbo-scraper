"""Fill what a university publishes about student life, for every university.

Scholarships, services, sport and culture, housing and the exchange
programmes are the five sections no career page ever fills. Every site keeps
them in the same shape -- a page per topic, linked from the home page by a
word that names the topic, holding a list of items with a heading -- so they
are read here once for everyone instead of once per adapter.

A university whose adapter already read one of these sections is left alone in
that section. The adapter looked at the site; this did not.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import re


from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers import vida
from rumbo_scraper.parsers.convenios import leer_convenios

USER_AGENT = "RumboScraper/0.4 (+catalogo educativo publico)"
# How many pages of one topic are worth reading. A site that links six pages
# about its scholarships is repeating itself by the third.
MAX_PAGINAS = 4

# The table each topic fills, and how a row of it is written.
DESTINOS: dict[str, str] = {
    "becas": "becas",
    "alojamiento": "alojamientos",
    "programas_internacionales": "programas_internacionales",
    "actividades_extracurriculares": "actividades_extracurriculares",
    "servicios_estudiantiles": "servicios_estudiantiles",
}


def _fila(topic: str, item: dict[str, str], universidad_id: str,
          fuente: str) -> dict[str, Any]:
    """One item of student life, written as the table for it expects."""
    nombre = item["titulo"]
    descripcion = item["descripcion"] or None
    kind = item["tipo"] or None
    if topic == "becas":
        return {"universidad_id": universidad_id, "nombre_beca": nombre,
                "nivel": None, "tipo_beca": kind,
                "cobertura_descripcion": descripcion,
                "porcentaje_maximo": vida.percentage(descripcion or ""),
                "requisitos": None, "proceso_postulacion": None,
                "renovacion": None, "fecha_cierre": None,
                "url_postulacion": None, "contacto": vida.contact_in(descripcion or ""),
                "fuente_url": fuente}
    if topic == "alojamiento":
        # ``tipo_alojamiento`` is NOT NULL, so only an item that names the
        # kind of housing can be written. One that names the help a
        # university gives to find housing elsewhere is left out rather than
        # filed under a kind of housing it never mentioned.
        return {"universidad_id": universidad_id, "sede_id": None,
                "tipo_apoyo": "Residencia", "tipo_alojamiento": kind,
                "residencia_propia": None, "descripcion": descripcion,
                "contacto": None, "url": fuente, "fuente_url": fuente}
    if topic == "programas_internacionales":
        return {"universidad_id": universidad_id, "nivel": None,
                "tipo_programa": kind, "nombre_programa": nombre,
                "cantidad_convenios": None, "duracion_maxima": None,
                "reconocimiento_academico": None, "arancel_destino_cubierto": None,
                "requisitos": None, "url": fuente, "fuente_url": fuente}
    if topic == "actividades_extracurriculares":
        return {"universidad_id": universidad_id, "sede_id": None,
                "categoria": kind, "nombre_actividad": nombre,
                "descripcion": descripcion, "contacto": None,
                "url": fuente, "fuente_url": fuente}
    return {"universidad_id": universidad_id, "sede_id": None,
            "categoria": kind, "nombre_servicio": nombre,
            "descripcion": descripcion, "contacto": None,
            "url": fuente, "fuente_url": fuente}


# What a university calls the page that gathers everything about being a
# student there. Half of them hang student life one click under it rather
# than off the home page.
_LA_PUERTA = re.compile(
    r"(?i)vida\s+(?:universitaria|estudiantil|en el campus)|estudiantes|"
    r"alumnos|bienestar|comunidad")


def _puertas(home: str, site: str, domain: str) -> list[str]:
    """The few pages that gather student life, when the home links one."""
    from bs4 import BeautifulSoup
    found: list[str] = []
    for anchor in BeautifulSoup(home, "html.parser").find_all("a", href=True):
        label = clean_text(anchor.get_text(" ", strip=True))
        if not label or len(label) > 40 or not _LA_PUERTA.search(label):
            continue
        url = urljoin(site, clean_text(anchor["href"])).split("#")[0]
        host = (urlparse(url).netloc or "").lower().removeprefix("www.")
        if host == domain and url not in found:
            found.append(url)
    return found[:3]


def leer(universidad: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Read every topic of student life a university links from its home.

    The home page is read first and then the two or three pages it calls
    "Vida universitaria" or "Estudiantes", because half the universities hang
    the topics under one of those instead of off the home page itself.
    """
    site = clean_text(universidad.get("sitio_web"))
    if not site:
        return {}
    domain = (urlparse(site).netloc or "").lower().removeprefix("www.")
    encontrado: dict[str, list[dict[str, str]]] = {}
    # A visitor's reading: it follows a home page that redirects in script and
    # opens a browser for a site that sends an empty shell.
    from rumbo_scraper.spiders.visitante import Visitante
    with Visitante() as client:
        home = client.get(site)
        if not home:
            return {}
        temas: dict[str, list[str]] = vida.discover_topics(home, site, domain)
        for puerta in _puertas(home, site, domain):
            pagina = client.get(puerta)
            if not pagina:
                continue
            for topic, urls in vida.discover_topics(pagina, puerta, domain).items():
                for url in urls:
                    if url not in temas[topic]:
                        temas[topic].append(url)
        for topic, urls in temas.items():
            vistos: set[str] = set()
            filas: list[dict[str, str]] = []
            for url in urls[:MAX_PAGINAS]:
                html = client.get(url)
                if not html:
                    continue
                for item in vida.read_items(html, topic):
                    clave = item["titulo"].lower()
                    if clave in vistos:
                        continue
                    vistos.add(clave)
                    filas.append({**item, "fuente": url})
            if filas:
                encontrado[topic] = filas

        # The pages about exchange also carry the list of the universities
        # abroad the agreements are with, which is a section of its own.
        convenios: list[dict[str, str]] = []
        vistos: set[str] = set()
        for url in temas.get("programas_internacionales", [])[:MAX_PAGINAS]:
            html = client.get(url)
            if not html:
                continue
            for fila in leer_convenios(html, url, universidad["nombre_oficial"]):
                if fila["universidad_destino"].lower() in vistos:
                    continue
                vistos.add(fila["universidad_destino"].lower())
                convenios.append(fila)
        if convenios:
            encontrado["convenios"] = convenios
    return encontrado


# The universities read by an adapter of their own. What an adapter wrote is
# never replaced here: it looked at that site and this reader did not.
CON_ADAPTADOR = frozenset({
    "Universidad Torcuato Di Tella", "Universidad de San Andrés",
    "Instituto Tecnológico de Buenos Aires", "Universidad Austral",
    "Universidad del Museo Social Argentino",
    "Pontificia Universidad Católica Argentina",
    "Universidad Argentina de la Empresa", "Universidad de Belgrano",
    "Universidad Tecnológica Nacional", "Universidad de Buenos Aires",
    "Universidad Abierta Interamericana", "Universidad de Palermo",
    "Universidad del CEMA",
    "Universidad de Ciencias Empresariales y Sociales",
    "Universidad del Salvador",
})


def aplicar(client: Any, universidad: dict[str, Any],
            hallazgos: dict[str, list[dict[str, str]]],
            rehacer: bool = False) -> dict[str, int]:
    """Write what this university publishes about student life.

    A university read by an adapter of its own keeps what the adapter wrote.
    For the rest, ``rehacer`` replaces what an earlier and rougher reading of
    this same reader left behind, which is the only way a correction to the
    reader reaches the rows it already wrote.
    """
    escrito: dict[str, int] = {}
    propia = universidad["nombre_oficial"] in CON_ADAPTADOR
    # ``convenios_intercambio.programa_origen`` is NOT NULL and holds the
    # career the student leaves from: Di Tella publishes its agreements one
    # list per career. What a university publishes centrally is the list of
    # the institutions it has agreements with, and that list does not say
    # which career each one is for. The agreements are kept in the artifact
    # and counted here; writing them would mean choosing a career the
    # university never named.
    convenios = hallazgos.pop("convenios", None)
    if convenios and not propia:
        escrito["convenios_sin_carrera_de_origen"] = len(convenios)
    for topic, filas in hallazgos.items():
        tabla = DESTINOS[topic]
        ya = client.table(tabla).select("id").eq(
            "universidad_id", universidad["id"]).limit(1).execute().data
        if ya and (propia or not rehacer):
            # Its adapter already read this section, and the adapter looked
            # at the site.
            continue
        if ya and rehacer:
            client.table(tabla).delete().eq(
                "universidad_id", universidad["id"]).execute()
        if topic == "alojamiento":
            filas = [item for item in filas
                     if item["tipo"] and item["tipo"].startswith("Residencia")]
        rows = [_fila(topic, item, universidad["id"], item["fuente"])
                for item in filas if item["tipo"]]
        if not rows:
            continue
        for start in range(0, len(rows), 50):
            client.table(tabla).insert(rows[start:start + 50]).execute()
        escrito[tabla] = len(rows)
    return escrito


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Completar la vida universitaria de cada universidad")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    parser.add_argument("--rehacer", action="store_true",
                        help="Reemplazar lo que dejó una lectura anterior")
    parser.add_argument("--output", type=Path, default=Path("data/vida.json"))
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    client = get_supabase_client()
    universidades = select_all(client.table("universidades").select("*"))

    todo: dict[str, Any] = {}
    for universidad in universidades:
        hallazgos = leer(universidad)
        todo[universidad["nombre_oficial"]] = hallazgos
        if args.apply and hallazgos:
            escrito = aplicar(client, universidad, hallazgos, args.rehacer)
            if escrito:
                print(f'{universidad["nombre_oficial"]}: {escrito}')
        elif hallazgos:
            print(f'{universidad["nombre_oficial"]}: '
                  f'{ {k: len(v) for k, v in hallazgos.items()} }')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(todo, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print("CARGADO" if args.apply else "LEÍDO (sin escribir)")
    print(f"Archivo: {args.output}")


if __name__ == "__main__":
    main()
