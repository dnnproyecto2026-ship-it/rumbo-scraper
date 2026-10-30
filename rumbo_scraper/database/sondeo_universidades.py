"""Where each university's missing plans are, offer page by offer page.

    python -m rumbo_scraper.database.sondeo_universidades UCP UNLP ... [--todas] [--actualizar]

Production (read-only) lists the published offers of the universities with no
plan, and the page of each. Every distinct page is read once, politely, and
classified:

- ``plan_en_pagina``: the page itself lists the subjects by year;
- ``pdf_del_plan``: it links a PDF that is called a plan, a curriculum or a
  list of subjects;
- ``pdf_con_texto`` / ``pdf_escaneado``: what ``--pdfs`` makes of a ``pdf_del_plan`` once the file is read (a
  scanned one has no text and needs OCR);
- ``plan_en_otra_pagina``: it links a page of the same site that is called so;
- ``js``: almost no text, built by scripts (needs the browser reader);
- ``caida``: the page did not answer, or answered with a block (never worked
  around);
- ``sin_plan_publicado``: the page says nothing about a plan.

The result goes to ``entregables/avance/sondeo_universidades.csv`` (resumable: a
page already there is not read again). It is the work list for the readers
and, for ``sin_plan_publicado`` and ``caida``, the recorded reason.
"""

from __future__ import annotations

import csv
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

SALIDA = Path("entregables/avance/sondeo_universidades.csv")
CAMPOS = ["universidad", "url", "motivo", "enlace", "ofertas_sin_plan"]
PAUSA = 1.5
_ANIO = re.compile(r"(?i)\b(?:primer|segundo|tercer|cuarto|quinto|sexto)\s+a[ñn]o\b|\b[1-6]\s*[°º]?\s*(?:er|do|ro|to)?\s*a[ñn]o\b")
_ES_PLAN = re.compile(r"(?i)plan(?:es)?[ _-]*(?:de[ _-]*)?estudios?|curr[ií]cula|dise[ñn]o[ _-]*curricular|malla|"
                      r"materias|asignaturas|plan[ _-]*de[ _-]*carrera|programa[ _-]*de[ _-]*la[ _-]*carrera")
_BLOQUEO = re.compile(r"(?i)captcha|cloudflare|access denied|just a moment|attention required")


def clasificar(url: str, html: str, estado: int) -> tuple[str, str]:
    """(motivo, enlace) of one page."""
    sin_scripts = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", sin_scripts))
    # (A block is read in the page's text, not in its code: a CDN's name is in every page's scripts.)
    if estado >= 400 or (len(texto) < 1500 and _BLOQUEO.search(texto)):
        return "caida", ""
    if len(_ANIO.findall(texto)) >= 3 and len(texto) > 1500:
        return "plan_en_pagina", ""
    sitio = urlparse(url).netloc.removeprefix("www.")
    pdf = otra = ""
    for destino, rotulo in re.findall(r'<a\b[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        rotulo = re.sub(r"<[^>]+>", " ", rotulo)
        completa = urljoin(url, destino.replace("&amp;", "&"))
        if not _ES_PLAN.search(rotulo + " " + completa):
            continue
        if completa.lower().split("?")[0].endswith(".pdf"):
            pdf = pdf or completa
        elif urlparse(completa).netloc.removeprefix("www.") == sitio and completa.rstrip("/") != url.rstrip("/"):
            otra = otra or completa
    if pdf:
        return "pdf_del_plan", pdf
    if otra:
        return "plan_en_otra_pagina", otra
    if len(texto) < 1200 and len(html) > 20000:
        return "js", ""
    return "sin_plan_publicado", ""


def texto_del_pdf(contenido: bytes) -> int:
    """How many characters of text a PDF has: an image-only (scanned) one has next to none."""
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf") as archivo:
        archivo.write(contenido)
        archivo.flush()
        salida = subprocess.run(["pdftotext", "-l", "3", archivo.name, "-"], capture_output=True, text=True, timeout=120)
    return len(re.sub(r"\s+", "", salida.stdout))


def revisar_pdfs() -> None:
    """Splits the ``pdf_del_plan`` rows of the survey into ``pdf_con_texto`` and ``pdf_escaneado``."""
    from rumbo_scraper.spiders.visitante import Visitante

    with SALIDA.open(encoding="utf-8-sig") as archivo:
        filas = list(csv.DictReader(archivo, delimiter=";"))
    vistos: dict[str, str] = {}
    with Visitante(timeout=60) as visitante:
        for fila in filas:
            if fila["motivo"] != "pdf_del_plan":
                continue
            enlace = fila["enlace"]
            if enlace not in vistos:
                try:
                    respuesta = visitante.client.get(enlace)
                    vistos[enlace] = ("caida" if respuesta.status_code != 200 else
                                      "pdf_con_texto" if texto_del_pdf(respuesta.content) >= 300 else "pdf_escaneado")
                except Exception:
                    vistos[enlace] = "caida"
                time.sleep(PAUSA)
            fila["motivo"] = vistos[enlace]
    with SALIDA.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CAMPOS, delimiter=";")
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"{len(vistos)} PDFs revisados -> {SALIDA}")


def ofertas_sin_plan(conexion: Any, siglas: list[str]) -> list[tuple[str, str, int]]:
    """(university, page, offers without a plan) from production."""
    filtro = "" if not siglas else "and u.nombre_corto = any(%s)"
    sql = f"""select u.nombre_corto, o.url_oficial, count(*)
        from ofertas_publicadas op join ofertas o on o.id = op.oferta_id
        join carreras c on c.id = o.carrera_id join universidades u on u.id = o.universidad_id
        where c.nivel in ('grado', 'pregrado') and u.tipo_institucion in ('universidad', 'instituto_universitario')
          and coalesce(o.url_oficial, '') <> '' {filtro}
          and not exists (select 1 from planes_estudio pe join planes_materias pm on pm.plan_id = pe.id
                          where pe.oferta_id = o.id and pe.vigente)
        group by 1, 2 order by 1, 2"""
    with conexion.cursor() as cursor:
        cursor.execute(sql, (siglas,) if siglas else None)
        return [(a, b, n) for a, b, n in cursor.fetchall()]


def poner_al_dia(filas: list[list[str]], pendientes: list[tuple[str, str, int]]) -> tuple[list[list[str]], int]:
    """The survey's rows for the pages that still have offers without a plan, with today's count of them, and how
    many rows were dropped because every offer of the page has its plan now."""
    cuantas = {(universidad, url): n for universidad, url, n in pendientes}
    vigentes = []
    for fila in filas:
        n = cuantas.get((fila[0], fila[1]))
        if n:
            vigentes.append(fila[:4] + [str(n)])
    return vigentes, len(filas) - len(vigentes)


def main() -> None:
    from rumbo_scraper.database.avance_produccion import url_de_la_base
    from rumbo_scraper.spiders.visitante import Visitante
    import psycopg

    if "--pdfs" in sys.argv:
        return revisar_pdfs()
    siglas = [a for a in sys.argv[1:] if not a.startswith("--")]
    # (``--actualizar``: first drops the pages whose offers all have a plan now and refreshes the counts.)
    hechas: dict[str, list[str]] = {}
    if SALIDA.exists():
        with SALIDA.open(encoding="utf-8-sig") as archivo:
            hechas = {fila["url"]: [fila[c] for c in CAMPOS] for fila in csv.DictReader(archivo, delimiter=";")}
    with psycopg.connect(url_de_la_base(), autocommit=True) as conexion:
        conexion.execute("set statement_timeout = 120000")
        pendientes = ofertas_sin_plan(conexion, siglas)
    if "--actualizar" in sys.argv and hechas:
        vigentes, quitadas = poner_al_dia([[*f] for f in hechas.values()], pendientes)
        with SALIDA.open("w", newline="", encoding="utf-8-sig") as archivo:
            escritor = csv.writer(archivo, delimiter=";")
            escritor.writerow(CAMPOS)
            escritor.writerows(vigentes)
        hechas = {fila[1]: fila for fila in vigentes}
        print(f"{quitadas} páginas quitadas (ya tienen plan), {len(vigentes)} siguen")
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not SALIDA.exists()
    with SALIDA.open("a", newline="", encoding="utf-8-sig") as archivo, Visitante(timeout=30) as visitante:
        escritor = csv.writer(archivo, delimiter=";")
        if nuevo:
            escritor.writerow(CAMPOS)
        for universidad, url, cuantas in pendientes:
            if url in hechas:
                continue
            try:
                respuesta = visitante.client.get(url)
                motivo, enlace = clasificar(url, respuesta.text, respuesta.status_code)
            except Exception:
                motivo, enlace = "caida", ""
            escritor.writerow([universidad, url, motivo, enlace, cuantas])
            archivo.flush()
            time.sleep(PAUSA)
    print(f"sondeadas {len(pendientes)} páginas -> {SALIDA}")


if __name__ == "__main__":
    main()
