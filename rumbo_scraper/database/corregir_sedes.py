"""Correct the campuses stored before the reader knew what an address is not.

Three faults, one pass:

- rows that are not addresses at all ("Alumnos 0800", "Error 404", "Aulas con
  capacidad para 40") leave, when no offer is taught at them;
- rows named "Sede central" by the reader rather than by the university are
  renamed after their street, because the name claimed something no page
  said;
- the universities named on the command line get back the addresses their
  reading found and the shared name made them lose: every unnamed address
  was "Sede central", campuses are stored one per name, and the last one
  read overwrote the others.

Preview by default; ``--apply`` writes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.parsers.institucional import _es_calle, sin_nombre, tipo_de_sede

LECTURA = Path("data/institucional.json")


def planificar(client: Any, reponer: list[str]) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all
    universidades = {u["id"]: u["nombre_oficial"] for u in
                     select_all(client.table("universidades").select("id,nombre_oficial"))}
    sedes = select_all(client.table("sedes").select("id,universidad_id,nombre_sede,calle,numero"))
    plan: list[dict[str, Any]] = []
    nombres = {(s["universidad_id"], s["nombre_sede"]) for s in sedes}
    direcciones = {(s["universidad_id"], comparison_key(f'{s["calle"]} {s["numero"] or ""}'))
                   for s in sedes}
    for sede in sedes:
        numero = str(sede["numero"]) if sede["numero"] else None
        # A campus the university names and gives no address for is a
        # campus; only a line that is not an address is wrong.
        if sede["calle"] and not _es_calle(sede["calle"], numero):
            # With a name of its own it stays and loses the address; with
            # the reader's name it was nothing but the bad line.
            accion = "borrar" if sede["nombre_sede"] == "Sede central" else "sin_direccion"
            plan.append({"accion": accion, **sede})
        elif sede["nombre_sede"] == "Sede central" and sede["calle"]:
            nuevo = sin_nombre(sede["calle"], numero)
            if (sede["universidad_id"], nuevo) not in nombres:
                nombres.add((sede["universidad_id"], nuevo))
                plan.append({"accion": "renombrar", "nuevo": nuevo, **sede})

    if reponer:
        leido = json.loads(LECTURA.read_text(encoding="utf-8"))
        por_nombre = {nombre: uid for uid, nombre in universidades.items()}
        for nombre in reponer:
            uid = por_nombre.get(nombre)
            for fila in (leido.get(nombre) or {}).get("sedes") or []:
                clave = comparison_key(f'{fila["calle"]} {fila["numero"] or ""}')
                if not uid or (uid, clave) in direcciones:
                    continue
                if not _es_calle(fila["calle"], fila["numero"]):
                    continue
                nombre_sede = fila["nombre_sede"]
                if nombre_sede == "Sede central" or nombre_sede.startswith("Sede ") \
                        and (uid, nombre_sede) in nombres:
                    nombre_sede = sin_nombre(fila["calle"], fila["numero"])
                if (uid, nombre_sede) in nombres:
                    continue
                direcciones.add((uid, clave))
                nombres.add((uid, nombre_sede))
                plan.append({"accion": "reponer", "universidad_id": uid,
                             "nombre_sede": nombre_sede, "calle": fila["calle"],
                             "numero": fila["numero"]})
    return plan


def aplicar(client: Any, plan: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for paso in plan:
        if paso["accion"] == "borrar":
            usada = client.table("ofertas_academicas").select("id", count="exact").eq(
                "sede_id", paso["id"]).limit(1).execute().count
            if usada:
                counts["borrar_omitida_por_ofertas"] = counts.get(
                    "borrar_omitida_por_ofertas", 0) + 1
                continue
            client.table("servicios_estudiantiles").update({"sede_id": None}).eq(
                "sede_id", paso["id"]).execute()
            client.table("sedes").delete().eq("id", paso["id"]).execute()
        elif paso["accion"] == "sin_direccion":
            client.table("sedes").update({"calle": None, "numero": None}).eq(
                "id", paso["id"]).execute()
        elif paso["accion"] == "renombrar":
            client.table("sedes").update({"nombre_sede": paso["nuevo"]}).eq(
                "id", paso["id"]).execute()
        else:
            client.table("sedes").insert({
                "universidad_id": paso["universidad_id"], "nombre_sede": paso["nombre_sede"],
                "localidad_id": None, "calle": paso["calle"], "numero": paso["numero"],
                "tipo_sede": tipo_de_sede(paso["nombre_sede"]),
            }).execute()
        counts[paso["accion"]] = counts.get(paso["accion"], 0) + 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Corregir las sedes guardadas")
    parser.add_argument("reponer", nargs="*",
                        help="Nombres oficiales cuyas direcciones leídas se reponen")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()
    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    plan = planificar(client, args.reponer)
    for paso in plan:
        destino = f" -> {paso['nuevo']}" if paso["accion"] == "renombrar" else ""
        print(f"{paso['accion']:10} {paso['nombre_sede']} | {paso['calle']} {paso['numero']}{destino}")
    print("CARGADO", aplicar(client, plan)) if args.apply else print(
        f"VALIDADO (sin escribir): {len(plan)}")


if __name__ == "__main__":
    main()
