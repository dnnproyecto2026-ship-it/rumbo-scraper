"""Plans proposed by an AI reader, in batch, for the careers the survey says have their plan in a document or a page.

    python -m rumbo_scraper.database.planes_ia UNNE UNComa ... [--paralelo 3] [--limite 40]

For each career of the given universities that has no subjects yet, the survey (``entregables/avance/
sondeo_universidades.csv``) says where its plan is: a PDF (``pdf_con_texto``), the page itself
(``plan_en_pagina``) or a page it links (``plan_en_otra_pagina``). The document is read as the verifier reads it
(``Fuentes.leer``), a ``claude -p`` session reads that text and answers the subjects by year, and the answers go to
``data/planes_ia.csv`` in the sheet ``planes_manuales`` takes. Nothing is written to the database here: that module
loads a row only if every name is written in the document, so an invented or misspelt name is sent back with its
reason. Several sessions run at once; only this process writes the sheet.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

SONDEO = Path("entregables/avance/sondeo_universidades.csv")
SALIDA = Path("data/planes_ia.csv")
CAMPOS = ["universidad", "carrera", "duracion_anios", "donde_buscar", "pista", "link_del_plan_usado",
          "materias (una por renglón: año | nombre)", "cargado_por", "revisado_por", "notas", "nombre_universidad",
          "carrera_id"]
MAXIMO_DE_TEXTO = 60000
INSTRUCCIONES = """Sos el lector de planes de estudio de un catálogo de carreras argentinas. Del texto de abajo (un documento o
una página de la universidad) sacá las materias del plan de la carrera "{carrera}" ({duracion}).

Reglas:
- Copiá cada nombre de materia tal como está escrito en el texto, letra por letra (mayúsculas, tildes, abreviaturas). No lo corrijas ni lo completes.
- "anio" es el año de la carrera en que se cursa, según el propio texto (por año, por cuatrimestre o por semestre: dos cuatrimestres son un año). Si el texto no dice el año, poné null en todas.
- Dejá afuera las optativas y electivas genéricas ("Optativa I"), los seminarios sin nombre, el trabajo final, las prácticas sin nombre, los idiomas a elección y los requisitos de graduación.
- Si el texto tiene más de una carrera o más de un plan, tomá solo el de "{carrera}", el vigente.
- Si el texto no es el plan de esta carrera, o lo cortó o no lo podés leer entero, respondé completo=false y la razón.

Respondé SOLO con un JSON, sin texto antes ni después:
{{"completo": true, "materias": [{{"anio": 1, "nombre": "..."}}], "motivo": ""}}

TEXTO:
{texto}
"""


def respuesta_a_materias(salida: str) -> tuple[list[tuple[str, int | None]], str]:
    """The subjects of the JSON an AI session answered, or the reason it gave none."""
    cuerpo = re.search(r"\{.*\}", salida, re.S)
    if not cuerpo:
        return [], "la respuesta no trae JSON"
    try:
        datos = json.loads(cuerpo.group(0))
    except ValueError:
        return [], "el JSON de la respuesta no se lee"
    if not datos.get("completo"):
        return [], str(datos.get("motivo") or "la IA no lo dio por completo")[:200]
    materias: list[tuple[str, int | None]] = []
    for m in datos.get("materias") or []:
        nombre = " ".join(str(m.get("nombre") or "").split())
        anio = m.get("anio")
        if nombre:
            materias.append((nombre, int(anio) if isinstance(anio, (int, float)) and 1 <= anio <= 7 else None))
    anios = {a for _, a in materias}
    if None in anios and len(anios) > 1:
        return [], "algunas materias con año y otras sin"
    return materias, ""


def enlace_candidato(motivo: str, url: str, enlace: str) -> str | None:
    """Where a survey row says the plan is (a link built by a script, with quotes or '+', is not one)."""
    if motivo in ("pdf_con_texto", "plan_en_otra_pagina") and enlace and not re.search(r"['\"+ ]", enlace):
        return enlace
    return url if motivo == "plan_en_pagina" else None


def a_renglones(materias: list[tuple[str, int | None]]) -> str:
    return "\n".join(f"{a} | {n}" if a else n for n, a in materias)


def _preguntar(tarea: dict[str, Any]) -> dict[str, Any]:
    texto = tarea["texto"][:MAXIMO_DE_TEXTO]
    prompt = INSTRUCCIONES.format(carrera=tarea["carrera"], texto=texto,
                                  duracion=f"{tarea['duracion']} años" if tarea["duracion"] else "duración no indicada")
    try:
        salida = subprocess.run(["claude", "-p", "--model", "sonnet"], input=prompt, capture_output=True, text=True,
                                timeout=420).stdout
    except Exception as error:
        return {**tarea, "materias": [], "motivo": f"falló la sesión: {type(error).__name__}"}
    materias, motivo = respuesta_a_materias(salida)
    return {**tarea, "materias": materias, "motivo": motivo}


def main() -> None:
    parser = argparse.ArgumentParser(description="Planes propuestos por una IA, para verificar con planes_manuales")
    parser.add_argument("siglas", nargs="+")
    parser.add_argument("--paralelo", type=int, default=3)
    parser.add_argument("--limite", type=int, default=60)
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    from rumbo_scraper.database.verificar_catalogo import Fuentes

    cliente = get_supabase_client()
    universidades = {u["id"]: u for u in select_all(cliente.table("universidades").select("id,nombre_corto,nombre_oficial,sitio_web"))
                     if u.get("nombre_corto") in set(args.siglas)}
    carreras = [c for c in select_all(cliente.table("carreras").select("id,universidad_id,nombre_carrera,nivel,duracion_anios"))
                if c["universidad_id"] in universidades]
    con_materias = {m["carrera_id"] for m in select_all(cliente.table("materias").select("carrera_id")) if m["carrera_id"]}
    urls: dict[str, list[str]] = {}
    for o in select_all(cliente.table("ofertas_academicas").select("carrera_id,url_oficial")):
        if o["url_oficial"]:
            urls.setdefault(o["carrera_id"], []).append(o["url_oficial"])
    with SONDEO.open(encoding="utf-8-sig") as archivo:
        sondeo = {f["url"]: f for f in csv.DictReader(archivo, delimiter=";")}

    tareas = []
    for c in carreras:
        if c["id"] in con_materias or len(tareas) >= args.limite:
            continue
        for url in urls.get(c["id"], []):
            fila = sondeo.get(url)
            enlace = enlace_candidato(fila["motivo"], url, fila["enlace"]) if fila else None
            if enlace:
                u = universidades[c["universidad_id"]]
                tareas.append({"universidad": u["nombre_corto"], "nombre_universidad": u["nombre_oficial"], "carrera": c["nombre_carrera"],
                               "carrera_id": c["id"], "duracion": c.get("duracion_anios"), "link": enlace,
                               "sitio": u["sitio_web"]})
                break
    print(f"{len(tareas)} carreras con documento para leer", flush=True)

    fuentes: dict[str, Any] = {}
    legibles = []
    for t in tareas:
        leido = fuentes.setdefault(t["sitio"], Fuentes(t["sitio"])).leer(t["link"])
        if leido["ok"] and len(leido["texto"]) > 800:
            legibles.append({**t, "texto": leido["texto"]})
        else:
            print(f"  sin texto: {t['universidad']} {t['carrera'][:50]}", flush=True)
    for f in fuentes.values():
        f.close()

    with ThreadPoolExecutor(max_workers=args.paralelo) as pool:
        respuestas = list(pool.map(_preguntar, legibles))

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CAMPOS, delimiter=";")
        escritor.writeheader()
        for r in respuestas:
            if not r["materias"]:
                print(f"  sin plan: {r['universidad']} {r['carrera'][:45]} — {r['motivo']}", flush=True)
                continue
            escritor.writerow({"universidad": r["universidad"], "carrera": r["carrera"], "duracion_anios": r["duracion"] or "",
                               "link_del_plan_usado": r["link"], "materias (una por renglón: año | nombre)": a_renglones(r["materias"]),
                               "cargado_por": "IA lector en lote (sesión de Claude; cotejo literal)", "revisado_por": "",
                               "notas": "", "nombre_universidad": r["nombre_universidad"], "carrera_id": r["carrera_id"]})
    print(f"{sum(1 for r in respuestas if r['materias'])} propuestas -> {SALIDA}; "
          f"verificarlas: python -m rumbo_scraper.database.planes_manuales {SALIDA} [--apply]")


if __name__ == "__main__":
    main()
