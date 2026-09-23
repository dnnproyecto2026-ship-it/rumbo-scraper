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
from urllib.parse import urlparse

import httpx

from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers import vida

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


def _get(client: httpx.Client, url: str) -> str:
    try:
        response = client.get(url)
        response.raise_for_status()
        if "html" not in response.headers.get("content-type", ""):
            return ""
        return response.text
    except Exception:
        return ""


def leer(universidad: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Read every topic of student life one university links from its home."""
    site = clean_text(universidad.get("sitio_web"))
    if not site:
        return {}
    domain = (urlparse(site).netloc or "").lower().removeprefix("www.")
    encontrado: dict[str, list[dict[str, str]]] = {}
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                      timeout=30) as client:
        home = _get(client, site)
        if not home:
            return {}
        for topic, urls in vida.discover_topics(home, site, domain).items():
            vistos: set[str] = set()
            filas: list[dict[str, str]] = []
            for url in urls[:MAX_PAGINAS]:
                html = _get(client, url)
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
    return encontrado


def aplicar(client: Any, universidad: dict[str, Any],
            hallazgos: dict[str, list[dict[str, str]]]) -> dict[str, int]:
    """Write the topics this university has nothing in yet."""
    escrito: dict[str, int] = {}
    for topic, filas in hallazgos.items():
        tabla = DESTINOS[topic]
        ya = client.table(tabla).select("id").eq(
            "universidad_id", universidad["id"]).limit(1).execute().data
        if ya:
            # Its adapter already read this section, and the adapter looked
            # at the site.
            continue
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
            escrito = aplicar(client, universidad, hallazgos)
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
