"""The plans of the UBA's careers, faculty by faculty.

The UBA's own site does not link its careers' pages: each of its thirteen
faculties publishes its plans on a site of its own and in a form of its own
-- Medicine as images, Philosophy as council resolutions, Engineering as the
resolution approving each career's plan. So each faculty that publishes its
plan as something a program can read gets a source here, and the others are
left alone rather than guessed.

Each source names the page that lists the plans; the plans are read off
what that page links, never off a search engine's memory of the site.

- Ingeniería: https://www.fi.uba.ar/institucional/plan2020/planes-de-estudio-2023
  links one resolution per career, read by `parsers.plan_por_cuatrimestre`.
- Ciencias Económicas: each career's page lays its plan out in tables, one
  per cycle ("CICLO DE FORMACIÓN GENERAL", "...PROFESIONAL"), a row per
  subject with its code ("» 241  Análisis Matemático I"); the tables of an
  orientation or of electives and optatives, which a student picks from,
  are not the plan's (``plan_de_economicas``). The pages do not say the
  year, so none is given.
- Ciencias Sociales, careers whose page lists each cycle with its count
  ("Ciclo General: Veintidós (22) asignaturas"), read by
  `parsers.plan_por_ciclos`: Ciencia Política. Those pages do not say the
  year, so none is given.

A career gets subjects only if it has none: this does not second-guess a
plan read before. Downloads are kept in ``data/planes_uba/`` so a second run
reads nothing again. Preview by default; ``--apply`` writes.
"""

from __future__ import annotations

import argparse
import difflib
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rumbo_scraper.database.exportar_catalogo import clave_de_carrera
from rumbo_scraper.database.planes_documentos import guardar_las_fuentes
from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.parsers import plan_por_ciclos, plan_por_cuatrimestre
from rumbo_scraper.spiders.visitante import Visitante

CACHE = Path("data/planes_uba")
PAUSA = 1.0
INGENIERIA = "https://www.fi.uba.ar/institucional/plan2020/planes-de-estudio-2023"
ECONOMICAS = {
    "Licenciatura en Economía": "https://www.economicas.uba.ar/carreras/economia",
    "Actuario": "https://www.economicas.uba.ar/carreras/actuario",
    "Contador Público": "https://www.economicas.uba.ar/carreras/contador",
    "Licenciatura en Administración": "https://www.economicas.uba.ar/carreras/administracion",
    "Licenciatura en Sistemas de Información de las Organizaciones": "https://www.economicas.uba.ar/carreras/sistemas",
}
POR_CICLOS = {
    "Licenciatura en Ciencia Política": "https://cienciapolitica.sociales.uba.ar/home/estudiantes/"
                        "info-academica/plan-de-estudios-8558-17/",
}


_NO_ES_DEL_PLAN = re.compile(r"(?i)electiv|optativ|orientaci|competencias")


def plan_de_economicas(html: str) -> list[str]:
    """The subjects of an Económicas career's plan: the rows with a code of
    the tables headed "CARGA HORARIA", unless the heading above the table
    (or the rows' own character) makes them an orientation's, electives or
    optatives; "(vigente en 2026)" is not part of a name. Nothing when a
    code repeats or fewer than ten subjects come out."""
    materias: list[str] = []
    codigos: list[str] = []
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        filas = tabla.find_all("tr")
        if not filas or "CARGA HORARIA" not in filas[0].get_text(" ").upper():
            continue
        encima = [t.get_text(" ", strip=True) for t in tabla.find_all_previous(
            ["h1", "h2", "h3", "h4", "h5", "p", "strong"], limit=3) if t.get_text(strip=True)]
        if encima and _NO_ES_DEL_PLAN.search(encima[0]):
            continue
        for fila in filas[2:]:
            celdas = [" ".join(c.get_text(" ").split()) for c in fila.find_all(["td", "th"])]
            codigo = re.fullmatch(r"»?\s*(\d{2,4})", celdas[0]) if len(celdas) > 2 else None
            if not codigo or _NO_ES_DEL_PLAN.search(" ".join(celdas[1:3])):
                continue
            nombre = re.sub(r"\s*\(vigente[^)]*\)", "", celdas[1]).strip()
            codigos.append(codigo.group(1))
            if nombre and nombre not in materias:
                materias.append(nombre)
    if len(set(codigos)) != len(codigos) or len(materias) < 10:
        return []
    return materias


def documentos_de_ingenieria(html: str) -> dict[str, str]:
    """The plan in force of each Engineering career, by the name the index
    gives it: the last resolution listed beside the career."""
    documento_de: dict[str, str] = {}
    for enlace in BeautifulSoup(html or "", "html.parser").find_all("a", href=True):
        url = urljoin(INGENIERIA, enlace["href"])
        if not url.lower().endswith(".pdf"):
            continue
        fila = enlace.find_parent(["tr", "li", "p", "div"])
        texto = " ".join(fila.get_text(" ").split()) if fila else ""
        carrera = texto.split(" Resoluci")[0].strip()
        if carrera:
            documento_de[carrera] = url
    return documento_de


def planes_de_ingenieria(visitante: Visitante) -> dict[str, list[tuple[str, int]]]:
    """Each Engineering career's plan, by the name the index gives it.

    The index lists a career, then its resolution and, when there is one,
    the resolution that modified it; the last one listed is the plan in
    force, and it is the one read.
    """
    documento_de = documentos_de_ingenieria(visitante.get(INGENIERIA))
    planes = {}
    CACHE.mkdir(parents=True, exist_ok=True)
    for carrera, url in documento_de.items():
        archivo = CACHE / url.rsplit("/", 1)[1]
        if not archivo.exists():
            respuesta = visitante.client.get(url)
            respuesta.raise_for_status()
            archivo.write_bytes(respuesta.content)
            time.sleep(PAUSA)
        planes[carrera] = plan_por_cuatrimestre.leer_pdf(str(archivo))
    return planes


def _emparejar(nombre: str, carreras: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """The career of the university a plan's name names: the same words, or
    a spelling one letter off ("Biongeniería" on the index)."""
    clave = clave_de_carrera(nombre)
    for carrera in carreras.values():
        if clave_de_carrera(carrera["nombre_carrera"]) == clave:
            return carrera
    parecidas = difflib.get_close_matches(comparison_key(nombre),
                                          list(carreras), n=1, cutoff=0.92)
    return carreras[parecidas[0]] if parecidas else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar los planes de estudio de la UBA")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    client = get_supabase_client()
    uba = client.table("universidades").select("id").eq("nombre_corto", "UBA").execute().data[0]
    carreras = {comparison_key(c["nombre_carrera"]): c for c in select_all(
        client.table("carreras").select("id,nombre_carrera").eq("universidad_id", uba["id"]))}
    con_materias = {m["carrera_id"] for m in select_all(
        client.table("materias").select("carrera_id").eq("universidad_id", uba["id"]))}

    with Visitante(timeout=60) as visitante:
        planes: dict[str, list[tuple[str, int | None]]] = dict(planes_de_ingenieria(visitante))
        for carrera, url in POR_CICLOS.items():
            materias = plan_por_ciclos.leer_html(visitante.get(url))
            if materias:
                planes[carrera] = [(materia, None) for materia in materias]
        fuentes = {}
        for carrera, url in ECONOMICAS.items():
            materias = plan_de_economicas(visitante.get(url))
            if materias:
                planes[carrera] = [(materia, None) for materia in materias]
                fuentes[carrera] = url
            time.sleep(PAUSA)

    filas = []
    con_fuente = []
    for nombre, materias in planes.items():
        carrera = _emparejar(nombre, carreras)
        if not carrera:
            print(f"  sin carrera en la base: {nombre}")
            continue
        estado = "ya tiene materias" if carrera["id"] in con_materias else "se carga"
        por_anio = dict(sorted(Counter(anio for _, anio in materias).items()))
        print(f"{carrera['nombre_carrera'][:45]:45} {len(materias):3} materias {por_anio} — {estado}")
        if carrera["id"] in con_materias:
            continue
        if nombre in fuentes:
            con_fuente.append({"universidad": "UBA", "documento": fuentes[nombre],
                               "carrera": {"nombre_carrera": carrera["nombre_carrera"]}})
        vistas: set[str] = set()
        for materia, anio in materias:
            if materia.lower() in vistas:
                continue
            vistas.add(materia.lower())
            filas.append({"universidad_id": uba["id"], "carrera_id": carrera["id"],
                          "nombre_materia": materia, "anio_cursada": anio})

    if args.apply and filas:
        for inicio in range(0, len(filas), 500):
            client.table("materias").insert(filas[inicio:inicio + 500]).execute()
        guardar_las_fuentes(con_fuente)
    print(f"Materias {'cargadas' if args.apply else 'a cargar'}: {len(filas)}"
          + ("" if args.apply else " — vista previa, sin escribir"))


if __name__ == "__main__":
    main()
