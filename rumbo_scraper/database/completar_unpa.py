"""Give UNPA's careers the duration and plan its offer's own service states.

UNPA's offer (propuestaacademica.unpa.edu.ar) is one page whose careers are
links (``<a id="69" class="modal-trigger ...">``); a click asks a public
service for the career:

    /controladores/controladorCarreras.php?opcion=infoCarrera&id=69

which answers its name ("Ingeniería Química - Título Intermedio Técnico
Universitario en Análisis Químico"), its duration ("5 Años", "4 Años y 1
Ctre.": a term more, "4.0") and its plan's code ("IPR07"). The plan is a
PDF sent inside a page (base64, shown in an iframe):

    /controladores/descargarPlan.php?plan=IPR07

and lays each year out under its heading ("PRIMER AÑO") as rows of code,
subject, term, weekly hours, prerequisites ("1529  Química Inorgánica  2ºC
8  1527"). An elective's slot ("Optativa I") is not a subject.

A career is matched by name, the service's abbreviations ("Tec. Univ. en
Rec. Nat. Renov.") and intermediate title aside. Only careers with no
duration get one, and only careers with no subjects a plan that
`planes_documentos` takes as whole.

    python -m rumbo_scraper.database.completar_unpa           (preview)
    python -m rumbo_scraper.database.completar_unpa --apply
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

from rumbo_scraper.normalizers.text import comparison_key

SITIO = "https://propuestaacademica.unpa.edu.ar"
HALLADOS = Path("data/unpa_hallados.json")


def clave(nombre: str) -> str:
    nombre = re.sub(r"(?i)^tec\.\s*univ\.", "Tecnicatura Universitaria", (nombre or "").strip())
    nombre = re.sub(r"(?i)\s+-\s+t[íi]tulo intermedio.*$", "", nombre)
    return comparison_key(nombre)


def anios(texto: Any) -> float | None:
    """ "5 Años" -> 5; "4 Años y 1 Ctre." -> 4.5; "4.0" -> 4; "" -> None."""
    dicho = re.fullmatch(r"(?i)\s*(\d(?:\.0)?)\s*(?:a[ñn]os?)?\s*(y\s*1\s*c(?:ua)?tr?e?\.?)?\s*", str(texto or ""))
    if not dicho:
        return None
    valor = float(dicho.group(1)) + (0.5 if dicho.group(2) else 0)
    return valor if 1.5 <= valor <= 7 else None


def pdf_de(pagina: str) -> bytes | None:
    """The PDF the download page carries as base64."""
    trozos = re.findall(r"[A-Za-z0-9+/=]{2000,}", pagina or "")
    if not trozos:
        return None
    try:
        datos = base64.b64decode(max(trozos, key=len))
    except ValueError:
        return None
    return datos if datos.startswith(b"%PDF") else None


_FILA = re.compile(r"^\s*\d{3,4}\s+(\S.*?)\s{2,}(?:[12]\s*º\s*C|A|Anual|1C|2C)\b")

_SOLO_CODIGO = re.compile(r"^\s*\d{3,4}\s{10,}(?:[12]\s*º\s*C|A|Anual)\b")


def plan_de(texto: str) -> list[tuple[str, int]]:
    from rumbo_scraper.parsers.planes_sitios import _agregar, anio_de, desde_el_primero

    filas: list[list[Any]] = []
    anio = None
    seguida = False
    pendiente = None
    lineas = texto.split("\n")
    for i, linea in enumerate(lineas):
        encabezado = linea.strip()
        if re.fullmatch(r"(?i)[a-zé]+\s+a[ñn]o", encabezado) and anio_de(encabezado):
            nuevo = anio_de(encabezado)
            # Another plan in the same document starts its years again.
            if anio and nuevo < anio:
                break
            anio, seguida = nuevo, False
            continue
        fila = _FILA.match(linea)
        suelta = re.fullmatch(r" {6,20}([^\d\s][^\d]{0,60}?)\s*", linea) and not encabezado.isupper()
        if anio and fila:
            filas.append([fila.group(1), anio])
            seguida = True
        # A two-line name with its code between: "Enfermería Materno Infantil y Cuidado de la" /
        # "2354  A  8" / "Mujer".
        elif anio and suelta and i + 1 < len(lineas) and _SOLO_CODIGO.match(lineas[i + 1]):
            pendiente = encabezado
        elif anio and pendiente and _SOLO_CODIGO.match(linea):
            filas.append([pendiente, anio])
            pendiente, seguida = None, True
        # A long name wraps under itself: "Didáctica de las Ciencias Económicas y" / "Empresariales".
        elif seguida and suelta:
            filas[-1][0] += " " + encabezado
        else:
            seguida = False
    materias: list[tuple[str, int]] = []
    for nombre, anio_de_la_fila in filas:
        if not re.match(r"(?i)optativ|electiv", nombre):
            _agregar(materias, re.sub(r"\s*\(?\*+\)?$", "", nombre), anio_de_la_fila)
    return desde_el_primero(materias)


def _texto_del_pdf(datos: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as archivo:
        archivo.write(datos)
        archivo.flush()
        return subprocess.run(["pdftotext", "-layout", archivo.name, "-"], capture_output=True,
                              text=True, timeout=60).stdout


def leer(client: Any) -> list[dict[str, Any]]:
    from rumbo_scraper.database import planes_documentos as pd
    from rumbo_scraper.database.supabase import select_all
    from rumbo_scraper.spiders.visitante import Visitante

    universidad = client.table("universidades").select("id").eq("nombre_corto", "UNPA").execute().data[0]["id"]
    carreras = {clave(c["nombre_carrera"]): c for c in select_all(client.table("carreras").select(
        "id,universidad_id,nombre_carrera,duracion_anios").eq("universidad_id", universidad))}
    con_materias = {m["carrera_id"] for m in select_all(
        client.table("materias").select("carrera_id").in_("carrera_id", [c["id"] for c in carreras.values()]))}
    hallados = []
    with Visitante(timeout=40) as visitante:
        ids = sorted(set(re.findall(r'<a id="(\d+)"\s+class="modal-trigger', visitante.get(SITIO + "/vista/index.php") or "")),
                     key=int)
        for id_ in ids:
            respuesta = visitante.client.get(f"{SITIO}/controladores/controladorCarreras.php",
                                             params={"opcion": "infoCarrera", "id": id_})
            time.sleep(0.5)
            try:
                dicha = (json.loads(respuesta.text or "[]") or [None])[0]
            except ValueError:
                dicha = None
            carrera = dicha and carreras.get(clave(dicha.get("nombre_carrera")))
            if not carrera:
                continue
            duracion = None if carrera["duracion_anios"] else anios(dicha.get("duracion_teorica"))
            materias: list[tuple[str, int]] = []
            documento = None
            if carrera["id"] not in con_materias and dicha.get("pdf_plan"):
                documento = f"{SITIO}/controladores/descargarPlan.php?plan={dicha['pdf_plan']}"
                datos = pdf_de(visitante.client.get(documento).text)
                time.sleep(0.5)
                materias = plan_de(_texto_del_pdf(datos)) if datos else []
                if not pd._parece_el_plan_entero(carrera["nombre_carrera"], materias,
                                                 carrera["duracion_anios"] or duracion):
                    materias = []
            if duracion or materias:
                hallados.append({"carrera": carrera, "duracion": duracion, "materias": materias,
                                 "documento": documento, "universidad": "UNPA"})
    return hallados


def main() -> None:
    parser = argparse.ArgumentParser(description="Completar duración y plan de las carreras de la UNPA")
    parser.add_argument("--apply", action="store_true", help=f"Escribir lo que dejó la vista previa en {HALLADOS}")
    args = parser.parse_args()

    from rumbo_scraper.database import planes_documentos as pd
    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if not args.apply:
        hallados = leer(client)
        HALLADOS.write_text(json.dumps(hallados, ensure_ascii=False, indent=1) + "\n")
    else:
        hallados = json.loads(HALLADOS.read_text())
    for h in hallados:
        print(f"{h['carrera']['nombre_carrera'][:60]:60} | {h['duracion'] or '':4} | {len(h['materias']):3} "
              f"{dict(Counter(anio for _, anio in h['materias'])) if h['materias'] else ''}", flush=True)
    if args.apply:
        for h in hallados:
            if h["duracion"]:
                client.table("carreras").update({"duracion_anios": h["duracion"]}).eq(
                    "id", h["carrera"]["id"]).is_("duracion_anios", "null").execute()
        filas = [{"universidad_id": h["carrera"]["universidad_id"], "carrera_id": h["carrera"]["id"],
                  "nombre_materia": materia, "anio_cursada": anio}
                 for h in hallados for materia, anio in h["materias"]]
        if filas:
            client.table("materias").insert(filas).execute()
            pd.guardar_las_fuentes([h for h in hallados if h["materias"]])
    print(f"Duraciones: {sum(1 for h in hallados if h['duracion'])}; planes: "
          f"{sum(1 for h in hallados if h['materias'])}", flush=True)


if __name__ == "__main__":
    main()
