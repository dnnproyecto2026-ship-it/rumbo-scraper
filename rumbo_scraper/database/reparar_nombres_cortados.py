"""Give back their whole name to the UADE careers stored cut in half.

UADE sets a long name over two headings and its adapter read only the first,
so fifteen careers were stored as "Licenciatura en Ciencias de la". The
adapter reads both now; this reads each of those pages again with it and
renames the row. When the whole name is already stored, the cut row is the
duplicate and leaves, handing its subjects over if the whole one has none.

Preview by default; ``--apply`` writes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from rumbo_scraper.parsers.uade import _SIGUE_EN_OTRO, page_title

UNIVERSIDAD = "Universidad Argentina de la Empresa"


def cortadas(client: Any) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all
    uid = client.table("universidades").select("id").eq(
        "nombre_oficial", UNIVERSIDAD).execute().data[0]["id"]
    filas = select_all(client.table("carreras").select("id,nombre_carrera")
                       .eq("universidad_id", uid))
    urls = {o["carrera_nombre"]: o["url_oficial"] for o in json.loads(
        Path("data/uade_completo.json").read_text(encoding="utf-8"))["datos"]["ofertas"]}
    nombres = {f["nombre_carrera"]: f["id"] for f in filas}
    salida = []
    with httpx.Client(follow_redirects=True, timeout=30,
                      headers={"User-Agent": "RumboScraper/0.4"}) as http:
        for fila in filas:
            nombre = fila["nombre_carrera"]
            if nombre.lower().split()[-1] not in _SIGUE_EN_OTRO or not urls.get(nombre):
                continue
            entero = page_title(http.get(urls[nombre]).text)
            if not entero or entero == nombre or entero.lower().split()[-1] in _SIGUE_EN_OTRO:
                continue
            salida.append({"id": fila["id"], "nombre": nombre, "entero": entero,
                           "gemelo": nombres.get(entero)})
    return salida


def main() -> None:
    parser = argparse.ArgumentParser(description="Reparar los nombres cortados de UADE")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()
    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    plan = cortadas(client)
    for paso in plan:
        print(f"{'duplicada' if paso['gemelo'] else 'renombrar':10} {paso['nombre']} -> {paso['entero']}")
    if not args.apply:
        print(f"VALIDADO (sin escribir): {len(plan)}")
        return
    for paso in plan:
        if paso["gemelo"]:
            propias = client.table("materias").select("id", count="exact").eq(
                "carrera_id", paso["gemelo"]).limit(1).execute().count
            if not propias:
                client.table("materias").update({"carrera_id": paso["gemelo"]}).eq(
                    "carrera_id", paso["id"]).execute()
            for tabla in ("materias", "ofertas_academicas", "actividades"):
                client.table(tabla).delete().eq("carrera_id", paso["id"]).execute()
            client.table("carreras").delete().eq("id", paso["id"]).execute()
        else:
            client.table("carreras").update({
                "nombre_carrera": paso["entero"], "denominacion_canonica": paso["entero"],
            }).eq("id", paso["id"]).execute()
    print(f"CARGADO: {len(plan)}")


if __name__ == "__main__":
    main()
