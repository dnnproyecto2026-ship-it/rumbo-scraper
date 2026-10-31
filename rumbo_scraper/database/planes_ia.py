"""Plans proposed by an AI reader, in batch, for the careers the survey says have their plan in a document or a page.

    python -m rumbo_scraper.database.planes_ia --preparar UNNE UNComa ...      (where production's data is read)
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


TAREAS = Path("data/planes_ia_tareas.csv")


def _clave(nombre: str) -> str:
    import unicodedata

    plano = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", plano).strip()


def preparar(siglas: list[str]) -> None:
    """The work list: the offers production publishes without a plan, the survey's place for each one's plan,
    and the career of the scraper base with the same name (the base the subjects are written to)."""
    import psycopg

    from rumbo_scraper.database.avance_produccion import url_de_la_base
    from rumbo_scraper.database.sondeo_universidades import ofertas_sin_plan
    from rumbo_scraper.database.supabase import get_supabase_client, select_all

    with SONDEO.open(encoding="utf-8-sig") as archivo:
        sondeo = {f["url"]: f for f in csv.DictReader(archivo, delimiter=";")}
    with psycopg.connect(url_de_la_base(), autocommit=True) as conexion:
        conexion.execute("set statement_timeout = 120000")
        sql = """select u.nombre_corto, c.nombre, o.url_oficial from ofertas_publicadas op join ofertas o on o.id = op.oferta_id
            join carreras c on c.id = o.carrera_id join universidades u on u.id = o.universidad_id
            where c.nivel in ('grado', 'pregrado') and u.nombre_corto = any(%s) and coalesce(o.url_oficial, '') <> ''
              and not exists (select 1 from planes_estudio pe join planes_materias pm on pm.plan_id = pe.id
                              where pe.oferta_id = o.id and pe.vigente)"""
        with conexion.cursor() as cursor:
            cursor.execute(sql, (siglas,))
            sin_plan = cursor.fetchall()
    cliente = get_supabase_client()
    universidades = {u["id"]: u for u in select_all(cliente.table("universidades").select("id,nombre_corto,nombre_oficial"))
                     if u.get("nombre_corto") in set(siglas)}
    por_nombre = {(universidades[c["universidad_id"]]["nombre_corto"], _clave(c["nombre_carrera"])): c
                  for c in select_all(cliente.table("carreras").select("id,universidad_id,nombre_carrera,duracion_anios"))
                  if c["universidad_id"] in universidades}
    sitios = {u["nombre_corto"]: u for u in universidades.values()}
    hechas, filas = set(), []
    for sigla, carrera, url in sin_plan:
        fila = sondeo.get(url)
        enlace = enlace_candidato(fila["motivo"], url, fila["enlace"]) if fila else None
        base = por_nombre.get((sigla, _clave(carrera)))
        if not enlace or not base or base["id"] in hechas:
            continue
        hechas.add(base["id"])
        filas.append({"universidad": sigla, "nombre_universidad": sitios[sigla]["nombre_oficial"], "carrera": base["nombre_carrera"],
                      "carrera_id": base["id"], "duracion": base.get("duracion_anios") or "", "link": enlace})
    with TAREAS.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=["universidad", "nombre_universidad", "carrera", "carrera_id", "duracion", "link"],
                                  delimiter=";")
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"{len(filas)} carreras de {len(set(f['universidad'] for f in filas))} universidades -> {TAREAS}")


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
    parser.add_argument("--preparar", action="store_true", help="arma la lista de tareas desde producción")
    args = parser.parse_args()
    if args.preparar:
        return preparar(args.siglas)

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    from rumbo_scraper.database.verificar_catalogo import Fuentes

    cliente = get_supabase_client()
    universidades = {u["nombre_corto"]: u for u in select_all(cliente.table("universidades").select("nombre_corto,sitio_web"))}
    con_materias = {m["carrera_id"] for m in select_all(cliente.table("materias").select("carrera_id")) if m["carrera_id"]}
    with TAREAS.open(encoding="utf-8-sig") as archivo:
        tareas = [{**t, "duracion": float(t["duracion"]) if t["duracion"] else None, "sitio": universidades[t["universidad"]]["sitio_web"]}
                  for t in csv.DictReader(archivo, delimiter=";")
                  if t["universidad"] in set(args.siglas) and t["carrera_id"] not in con_materias
                  and t["universidad"] in universidades][:args.limite]
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
