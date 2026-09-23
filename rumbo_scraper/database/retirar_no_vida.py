"""Take out of student life the rows that name nothing a university offers.

The student-life reader kept, as scholarships, services and activities, the
addresses to write to ("biblioteca@unimoron.edu.ar"), the degrees taught on
the same pages ("Licenciatura en Gestión Cultural"), links ("https://..."),
headlines, dated calls and menus. The rule that now keeps them out of a
reading finds them in the database. Preview by default; ``--apply`` deletes.
"""

from __future__ import annotations

import argparse
from typing import Any

from rumbo_scraper.parsers.vida import _es_un_nombre

TABLAS = (("becas", "nombre_beca"), ("programas_internacionales", "nombre_programa"),
          ("servicios_estudiantiles", "nombre_servicio"),
          ("actividades_extracurriculares", "nombre_actividad"))


def planificar(client: Any) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all
    plan = []
    for tabla, columna in TABLAS:
        for fila in select_all(client.table(tabla).select(f"id,{columna}")):
            if not _es_un_nombre(fila[columna] or ""):
                plan.append({"tabla": tabla, "id": fila["id"], "nombre": fila[columna]})
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Retirar filas de vida universitaria sin nombre")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()
    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    plan = planificar(client)
    for paso in plan:
        print(f"{paso['tabla']:30} {paso['nombre']}")
    if args.apply:
        for paso in plan:
            client.table(paso["tabla"]).delete().eq("id", paso["id"]).execute()
        print(f"CARGADO: {len(plan)} filas retiradas")
    else:
        print(f"VALIDADO (sin escribir): {len(plan)} filas")


if __name__ == "__main__":
    main()
