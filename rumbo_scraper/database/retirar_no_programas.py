"""Take out of the catalogue the rows that name a page rather than a programme.

A reading before the reader knew better stored as programmes the parts of a
programme's site ("Ingeniería Biomédica - Admisión", "... - Misión y
Valores"), the call to action glued to a heading ("Licenciatura en Arte
Conocé la carrera"), the minutes of a council ("RES 054 - 2012 \"CS\" CGA
Maestría") and a person with their post ("Emanuel Porcelli | Subsecretario de
Maestrías"). The same rules that now keep them out of a reading find them in
the database.

What happens to each depends on whether the programme it copies is there:

- a row whose clean name exists already is a duplicate, and leaves with its
  subjects, which are the same plan read a second time off a sibling page;
- a row whose clean name does not exist is the only record of a real
  programme, and is renamed rather than lost;
- a row with no clean name at all (a council's minutes, a person) leaves.

Preview by default; ``--apply`` writes.
"""

from __future__ import annotations

import argparse
import re
from typing import Any

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.parsers.generico import _UN_CARGO, _UN_TITULO, _UNA_RESOLUCION, _UNA_SECCION

TABLAS = (("carreras", "nombre_carrera", "carrera_id"),
          ("posgrados", "nombre_programa", "posgrado_id"))
_COLA = re.compile(
    r"\s*(?:[-–—|]\s*[^-–—|]+|\s(?:Conoc[ée] la carrera|M[áa]s informaci[óo]n))$", re.I)


def motivo(nombre: str) -> str | None:
    clave = comparison_key(nombre).lstrip("¡¿\"'«-–— ")
    if _UNA_RESOLUCION.match(clave):
        return "resolucion"
    if _UN_CARGO.search(clave):
        return "cargo"
    if _UNA_SECCION.search(clave):
        return "seccion"
    if _UN_TITULO.match(clave):
        return "titulo"
    return None


# The degree each title is awarded by: a page headed with the title of its
# graduate, "Título: Licenciado en Astronomía (5 años)", is the page of the
# Licenciatura en Astronomía.
_GRADO_DEL_TITULO = (("licenciad[oa]", "Licenciatura"), ("ingenier[oa]", "Ingeniería"),
                     ("profesor[a]?", "Profesorado"), ("tecnic[oa]", "Tecnicatura"))
_EL_TITULO = re.compile(r"(?i)^t[íi]tulo\s*(?:de|:)?\s*(?P<grado>\w+)\s+(?P<resto>(?:en|de)\s+[^()]+?)\s*(?:\(.*)?$")


def _grado_del_titulo(nombre: str) -> str | None:
    match = _EL_TITULO.match(nombre)
    if not match:
        return None
    for patron, grado in _GRADO_DEL_TITULO:
        if re.fullmatch(patron, comparison_key(match.group("grado"))):
            return f"{grado} {match.group('resto').strip()}"
    return None


def nombre_limpio(nombre: str, razon: str) -> str | None:
    """The programme a row copies, when it copies one."""
    if razon == "titulo":
        return _grado_del_titulo(nombre)
    if razon != "seccion":
        return None
    limpio = clean_text(_COLA.sub("", nombre))
    if not limpio or limpio == nombre or motivo(limpio):
        return None
    # "Maestría en Preguntas Frecuentes" has nothing left worth a name.
    if comparison_key(limpio).split()[-1] in {"en", "de"}:
        return None
    return limpio


def planificar(client: Any) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all
    plan: list[dict[str, Any]] = []
    for tabla, columna, clave in TABLAS:
        filas = select_all(client.table(tabla).select(f"id,universidad_id,{columna}"))
        por_nombre = {(f["universidad_id"], f[columna]): f["id"] for f in filas}
        for fila in filas:
            razon = motivo(fila[columna])
            if not razon:
                continue
            limpio = nombre_limpio(fila[columna], razon)
            # A title that names no degree this knows may still be the only
            # record of a real programme; it is left as it is.
            if razon == "titulo" and not limpio:
                continue
            gemelo = por_nombre.get((fila["universidad_id"], limpio)) if limpio else None
            accion = ("borrar_duplicado" if gemelo else
                      "renombrar" if limpio else "borrar")
            plan.append({"tabla": tabla, "columna": columna, "clave": clave,
                         "id": fila["id"], "nombre": fila[columna], "razon": razon,
                         "limpio": limpio, "gemelo": gemelo, "accion": accion})
    return plan


def aplicar(client: Any, plan: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for paso in plan:
        tabla, clave = paso["tabla"], paso["clave"]
        if paso["accion"] == "renombrar":
            client.table(tabla).update({paso["columna"]: paso["limpio"]}).eq(
                "id", paso["id"]).execute()
        else:
            gemelo = paso["gemelo"]
            if gemelo:
                # The clean programme keeps the plan; it takes the copy only
                # when it has none of its own.
                propias = client.table("materias").select("id", count="exact").eq(
                    clave, gemelo).limit(1).execute().count
                if not propias:
                    client.table("materias").update({clave: gemelo}).eq(
                        clave, paso["id"]).execute()
                    counts["materias_trasladadas"] = counts.get("materias_trasladadas", 0) + 1
            for dependiente in ("materias", "actividades"):
                client.table(dependiente).delete().eq(clave, paso["id"]).execute()
            client.table(tabla).delete().eq("id", paso["id"]).execute()
        counts[paso["accion"]] = counts.get(paso["accion"], 0) + 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retirar las filas que nombran una página y no un programa")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()
    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    plan = planificar(client)
    for paso in plan:
        destino = f" -> {paso['limpio']}" if paso["accion"] == "renombrar" else ""
        print(f"{paso['accion']:17} {paso['razon']:10} {paso['nombre']}{destino}")
    if args.apply:
        print("CARGADO", aplicar(client, plan))
    else:
        print(f"VALIDADO (sin escribir): {len(plan)} filas")


if __name__ == "__main__":
    main()
