"""The plans the national universities publish as documents.

Most careers of the national universities link their plan from their own
page as a PDF: the annex of the resolution that approved it. The general
reader followed those links and read the PDF's text, and the text of a
resolution is mostly "VISTO el Expediente..." -- it stored nothing, rightly.
This reads the PDF's tables instead (`parsers.plan_por_columnas`, and
`parsers.plan_por_cuatrimestre` for the tables by term), and takes a plan only
when everything says it is this career's whole plan:

- the document is linked by one career only: one linked by several is a
  common cycle or a faculty's catalogue, not any one career's plan;
- the document names the career in its first pages: UNLaM's "Ingeniería
  Mecánica" links the plan of a teacher-training course;
- no two careers come out with the same subjects: that is a common first
  cycle (UNMdP's agronomies) or a degree's plan linked from its
  intermediate title;
- a tecnicatura does not run past its third year, for the same reason;
- no subject name starts in lower case, which is a piece of a name the cell
  wrapped ("social", "de Argentina");
- a plan that does not say the year has at least twenty subjects: fewer is
  the first cycle alone.

Optional subjects ("(optativa)") and the degree's title are not the plan's
sequence and are left out. A career gets subjects only if it has none.
Downloads are kept in ``data/planes_documentos/``. Preview by default;
``--apply`` writes.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rumbo_scraper.database.exportar_catalogo import _urls_de_los_artefactos
from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.parsers import plan_por_columnas, plan_por_cuatrimestre
from rumbo_scraper.spiders.generico import _documento_del_plan, _enlace_al_plan
from rumbo_scraper.spiders.visitante import Visitante

CACHE = Path("data/planes_documentos")
PAUSA = 0.7
MINIMO_SIN_ANIO = 20
_VACIAS = frozenset("de del la las los el y e en a con para por licenciatura tecnicatura "
                    "universitaria carrera profesorado ingenieria ciclo".split())
_FUERA_DEL_PLAN = re.compile(r"(?i)\(optativa\)|^t[íi]tulo\s*:")


def _nombra(texto: str, carrera: str) -> bool:
    palabras = set(re.findall(r"[a-z0-9]+", comparison_key(texto)))
    propias = [p for p in re.findall(r"[a-z0-9]+", comparison_key(carrera)) if p not in _VACIAS]
    return all(p in palabras for p in propias)


def _leer(archivo: Path) -> list[tuple[str, int | None]]:
    try:
        materias = plan_por_columnas.leer_pdf(str(archivo))
        if not materias:
            materias = plan_por_cuatrimestre.leer_pdf(str(archivo))
    except Exception:
        return []
    return [(nombre, anio) for nombre, anio in materias if not _FUERA_DEL_PLAN.search(nombre)]


def _texto(archivo: Path) -> str:
    import pdfplumber

    try:
        with pdfplumber.open(str(archivo)) as pdf:
            return " ".join((pagina.extract_text() or "") for pagina in pdf.pages[:4])
    except Exception:
        return ""


def _parece_el_plan_entero(carrera: str, materias: list[tuple[str, int | None]]) -> bool:
    if len(materias) < 10 or any(nombre[:1].islower() for nombre, _ in materias):
        return False
    anios = [anio for _, anio in materias if anio]
    if not anios:
        return len(materias) >= MINIMO_SIN_ANIO
    if comparison_key(carrera).startswith("tecnicatura") and max(anios) > 3:
        return False
    return True


def leer(client: Any, solo: set[str]) -> dict[str, dict[str, Any]]:
    """For each career that has no subjects, the plan its document gives."""
    from rumbo_scraper.database.supabase import select_all

    universidades = {u["id"]: u for u in select_all(client.table("universidades").select("*"))
                     if u.get("tipo_gestion") == "Estatal"
                     and (not solo or u.get("nombre_corto") in solo)}
    carreras = [c for c in select_all(client.table("carreras").select(
        "id,universidad_id,nombre_carrera,nivel")) if c["universidad_id"] in universidades]
    con_materias = {m["carrera_id"] for m in select_all(
        client.table("materias").select("carrera_id")) if m["carrera_id"]}
    artefactos = _urls_de_los_artefactos()
    url_de = {c["id"]: artefactos.get((universidades[c["universidad_id"]]["nombre_oficial"],
                                       c["nombre_carrera"])) for c in carreras}
    for oferta in select_all(client.table("ofertas_academicas").select("carrera_id,url_oficial")):
        if oferta["url_oficial"] and oferta["carrera_id"] in url_de:
            url_de[oferta["carrera_id"]] = oferta["url_oficial"]

    documento_de: dict[str, str] = {}
    CACHE.mkdir(parents=True, exist_ok=True)
    with Visitante(timeout=30) as visitante:
        for carrera in carreras:
            url = url_de.get(carrera["id"])
            if carrera["id"] in con_materias or not url:
                continue
            host = urlparse(url).netloc.removeprefix("www.")
            dominios = (host, host.split(".", 1)[-1]) if host.count(".") > 2 else (host,)
            html = visitante.get(url)
            time.sleep(PAUSA)
            documento = _documento_del_plan(html, url, dominios)
            if not documento:
                enlace = _enlace_al_plan(html, url, dominios)
                if enlace:
                    documento = _documento_del_plan(visitante.get(enlace), enlace, dominios)
                    time.sleep(PAUSA)
            if not documento:
                continue
            archivo = CACHE / (hashlib.md5(documento.encode()).hexdigest() + ".pdf")
            if not archivo.exists():
                try:
                    respuesta = visitante.client.get(documento)
                    archivo.write_bytes(respuesta.content if respuesta.status_code == 200 else b"")
                except Exception:
                    archivo.write_bytes(b"")
                time.sleep(PAUSA)
            documento_de[carrera["id"]] = documento

    usos = Counter(documento_de.values())
    planes: dict[str, dict[str, Any]] = {}
    for carrera in carreras:
        documento = documento_de.get(carrera["id"])
        if not documento or usos[documento] > 1:
            continue
        archivo = CACHE / (hashlib.md5(documento.encode()).hexdigest() + ".pdf")
        if archivo.stat().st_size < 1000 or not _nombra(_texto(archivo), carrera["nombre_carrera"]):
            continue
        materias = _leer(archivo)
        if _parece_el_plan_entero(carrera["nombre_carrera"], materias):
            planes[carrera["id"]] = {
                "carrera": carrera, "materias": materias, "documento": documento,
                "universidad": universidades[carrera["universidad_id"]].get("nombre_corto"),
            }

    iguales = Counter(tuple(sorted(n.lower() for n, _ in p["materias"])) for p in planes.values())
    return {cid: p for cid, p in planes.items()
            if iguales[tuple(sorted(n.lower() for n, _ in p["materias"]))] == 1}


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar los planes publicados como documento")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    parser.add_argument("universidades", nargs="*", help="Nombres cortos; todas si se omite")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    planes = leer(client, set(args.universidades))

    filas = []
    por_universidad: dict[str, int] = defaultdict(int)
    for plan in planes.values():
        carrera = plan["carrera"]
        por_anio = dict(Counter(anio for _, anio in plan["materias"]))
        print(f"{plan['universidad']:8} {carrera['nombre_carrera'][:48]:48} "
              f"{len(plan['materias']):3} {por_anio}")
        por_universidad[plan["universidad"]] += 1
        vistas: set[str] = set()
        for materia, anio in plan["materias"]:
            if materia.lower() in vistas:
                continue
            vistas.add(materia.lower())
            filas.append({"universidad_id": carrera["universidad_id"], "carrera_id": carrera["id"],
                          "nombre_materia": materia, "anio_cursada": anio})

    if args.apply and filas:
        for inicio in range(0, len(filas), 500):
            client.table("materias").insert(filas[inicio:inicio + 500]).execute()
    print(f"Planes: {len(planes)} {dict(por_universidad)}; materias "
          f"{'cargadas' if args.apply else 'a cargar'}: {len(filas)}")


if __name__ == "__main__":
    main()
