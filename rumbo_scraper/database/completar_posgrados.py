"""Give each postgraduate the degree, duration and modality its page states.

The lists the postgraduates were read from name them and nothing else, so
almost none has a degree or a duration. This reads each one's own page
(`url_oficial`, when no other programme shares it and it is the programme's:
its title or its content names it) with `parsers.datos_posgrado`, and fills only what is
empty. Sites are read in parallel, each one politely.

The preview keeps what it found in ``data/posgrados_datos_hallados.json``;
``--apply`` writes from that file.

    python -m rumbo_scraper.database.completar_posgrados [UNL UNCuyo ...]
    python -m rumbo_scraper.database.completar_posgrados --apply
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rumbo_scraper.database.completar_unidades import _NO_ES_SU_PAGINA
from rumbo_scraper.parsers.datos_posgrado import (_ROTULO_DE_DURACION, _lineas, _primero,
                                                datos_de_posgrado, duracion_mencionada, es_suyo, limpio,
                                                minimo_de_meses, nombra_el_programa, titulo_mencionado)
from rumbo_scraper.parsers.generico import duracion_meses as duracion_meses_de
from rumbo_scraper.parsers.unidad import es_la_pagina_de
from rumbo_scraper.spiders.visitante import Visitante

PAUSA = 0.8
SITIOS_A_LA_VEZ = 8
HALLADOS = Path("data/posgrados_datos_hallados.json")
CAMPOS = ("titulo_otorgado", "duracion_meses", "modalidad")


def leer(client: Any, solo: set[str] = frozenset()) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all

    corto = {u["id"]: u.get("nombre_corto") or "" for u in select_all(
        client.table("universidades").select("id,nombre_corto"))}
    posgrados = select_all(client.table("posgrados").select(
        "id,universidad_id,nombre_programa,url_oficial," + ",".join(CAMPOS)))
    # A page several programmes point at is a list: its facts are not one's.
    veces = Counter(p["url_oficial"] for p in posgrados if p["url_oficial"])
    pendientes = [p for p in posgrados
                  if (not solo or corto.get(p["universidad_id"]) in solo)
                  and any(p[c] is None for c in CAMPOS)
                  and p["url_oficial"] and veces[p["url_oficial"]] == 1
                  and not _NO_ES_SU_PAGINA.search(p["url_oficial"])
                  and not p["url_oficial"].lower().endswith(".pdf")]
    por_sitio: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in pendientes:
        por_sitio[urlparse(p["url_oficial"]).hostname or ""].append(p)

    def un_sitio(programas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        hallados = []
        with Visitante(timeout=25) as visitante:
            for p in programas:
                html = visitante.get(p["url_oficial"])
                time.sleep(PAUSA)
                if not html or not (es_la_pagina_de(html, p["nombre_programa"])
                                    or nombra_el_programa(html, p["nombre_programa"])):
                    continue
                datos = {c: v for c, v in datos_de_posgrado(html, p["nombre_programa"]).items()
                         if v is not None and p[c] is None}
                _lo_que_falta(html, p, datos, visitante)
                if datos:
                    u = corto.get(p["universidad_id"], "")
                    print(f"{u:9} | {p['nombre_programa'][:55]:55} | {datos}", flush=True)
                    hallados.append({"posgrado_id": p["id"], "universidad": u,
                                     "programa": p["nombre_programa"], "url": p["url_oficial"], **datos})
        return hallados

    with ThreadPoolExecutor(max_workers=SITIOS_A_LA_VEZ) as pool:
        return [h for lote in pool.map(un_sitio, por_sitio.values()) for h in lote]


MAX_PDFS = 3
MAX_BYTES = 8_000_000


def _documentos(html: str, url: str, visitante: Visitante):
    """The lines of each PDF of the university's own the page links, read one
    at a time and only when asked: a plan or a resolution says the degree
    and the duration the page leaves out. A scanned document has no text."""
    from io import BytesIO
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from pypdf import PdfReader

    sitio = ".".join((urlparse(url).hostname or "").split(".")[-3:])
    documentos: list[str] = []
    for enlace in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        destino = urljoin(url, enlace["href"].strip()).split("#")[0]
        if ".pdf" in destino.lower() and (urlparse(destino).hostname or "").endswith(sitio) \
                and destino not in documentos:
            documentos.append(destino)
    for documento in documentos[:MAX_PDFS]:
        try:
            respuesta = visitante.client.get(documento)
        except Exception:
            continue
        time.sleep(PAUSA)
        if not respuesta.content.startswith(b"%PDF") or len(respuesta.content) > MAX_BYTES:
            continue
        try:
            paginas = PdfReader(BytesIO(respuesta.content)).pages[:8]
            texto = "\n".join(pagina.extract_text() or "" for pagina in paginas)
        except Exception:
            continue
        yield documento, [linea.strip() for linea in texto.split("\n") if linea.strip()]


def _lo_que_falta(html: str, programa: dict[str, Any], datos: dict[str, Any],
                  visitante: Visitante) -> None:
    """The degree and the duration the page's labels did not give: the page
    or its documents mention them (`titulo_mencionado`, `duracion_mencionada`)."""
    nombre, url = programa["nombre_programa"], programa["url_oficial"]
    falta_titulo = programa["titulo_otorgado"] is None and "titulo_otorgado" not in datos
    falta_meses = programa["duracion_meses"] is None and "duracion_meses" not in datos
    if falta_titulo and (titulo := titulo_mencionado(_lineas(html), nombre)):
        datos["titulo_otorgado"], datos["fuente_titulo"] = titulo, url
        falta_titulo = False
    if not (falta_titulo or falta_meses):
        return
    for documento, lineas in _documentos(html, url, visitante):
        if falta_titulo and (titulo := titulo_mencionado(lineas, nombre)):
            datos["titulo_otorgado"], datos["fuente_titulo"] = titulo, documento
            falta_titulo = False
        if falta_meses:
            meses = (_primero(lineas, _ROTULO_DE_DURACION, duracion_meses_de) or
                     duracion_mencionada(lineas, nombre))
            if meses and minimo_de_meses(nombre) <= meses <= 72:
                datos["duracion_meses"], datos["fuente_duracion"] = meses, documento
                falta_meses = False
        if not (falta_titulo or falta_meses):
            return


def aplicar(client: Any, hallados: list[dict[str, Any]]) -> Counter:
    escritos: Counter = Counter()
    for h in hallados:
        # A preview written before a fix to the reader is read with the fix.
        if h.get("titulo_otorgado") is not None:
            titulo = limpio(h["titulo_otorgado"])
            h["titulo_otorgado"] = titulo if titulo and es_suyo(titulo, h["programa"]) else None
        if h.get("duracion_meses") is not None and h["duracion_meses"] < minimo_de_meses(h["programa"]):
            h["duracion_meses"] = None
        for campo in CAMPOS:
            if h.get(campo) is None:
                continue
            # Only an empty field is written: a later reading never overwrites.
            fila = client.table("posgrados").update({campo: h[campo]}).eq(
                "id", h["posgrado_id"]).is_(campo, "null").execute().data
            escritos[campo] += len(fila)
    return escritos


def main() -> None:
    parser = argparse.ArgumentParser(description="Completar título, duración y modalidad de los posgrados")
    parser.add_argument("--apply", action="store_true",
                        help=f"Escribir en Supabase lo que dejó la vista previa en {HALLADOS}")
    parser.add_argument("universidades", nargs="*", help="Nombres cortos; todas si se omite")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if args.apply:
        print("Escritos:", dict(aplicar(client, json.loads(HALLADOS.read_text()))))
        return
    hallados = leer(client, set(args.universidades))
    HALLADOS.write_text(json.dumps(hallados, ensure_ascii=False, indent=1) + "\n")
    cuenta = Counter(c for h in hallados for c in CAMPOS if c in h)
    print(f"Con datos: {len(hallados)} {dict(cuenta)} — vista previa en {HALLADOS}", flush=True)


if __name__ == "__main__":
    main()
