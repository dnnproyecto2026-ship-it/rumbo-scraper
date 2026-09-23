"""Remove the offers a loader wrote more than once.

``ofertas_academicas`` was upserted on ``carrera_id, sede_id, modalidad``, and
the modality of an offer is null wherever the university does not publish one.
In Postgres a null never equals another null, so the conflict never fired and
every reading inserted the same offer again. Two thousand rows held six
hundred and sixty-three distinct offers.

The row kept for each offer is the one something else already points at -- a
timetable or an intake cycle -- because deleting that one would take the
timetable with it. Where nothing points at any of them, the first is kept.
"""

from __future__ import annotations

import argparse
from typing import Any

from rumbo_scraper.database.supabase import get_supabase_client, select_all


def duplicadas(client: Any) -> tuple[list[str], int]:
    """The offers to delete, and how many distinct offers there really are."""
    offers = select_all(client.table("ofertas_academicas").select("id,carrera_id,sede_id"))
    referidas: set[str] = set()
    for table in ("turnos_anio", "ciclos_ingreso", "aranceles"):
        try:
            referidas |= {row["oferta_id"] for row
                          in select_all(client.table(table).select("oferta_id"))
                          if row.get("oferta_id")}
        except Exception:
            continue

    grupos: dict[tuple[str, str], list[str]] = {}
    for offer in offers:
        grupos.setdefault((offer["carrera_id"], offer["sede_id"]), []).append(offer["id"])

    sobran: list[str] = []
    for ids in grupos.values():
        if len(ids) == 1:
            continue
        # Keep one that something else points at, or else the first.
        queda = next((i for i in ids if i in referidas), ids[0])
        sobran += [i for i in ids if i != queda]
    return sobran, len(grupos)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Borrar las ofertas académicas repetidas")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    client = get_supabase_client()
    sobran, distintas = duplicadas(client)
    print(f"Ofertas distintas: {distintas}")
    print(f"Filas repetidas: {len(sobran)}")
    if args.apply and sobran:
        for start in range(0, len(sobran), 50):
            client.table("ofertas_academicas").delete().in_(
                "id", sobran[start:start + 50]).execute()
        total = client.table("ofertas_academicas").select(
            "id", count="exact").limit(1).execute().count
        print(f"BORRADO. Quedan {total} ofertas.")
    else:
        print("LEÍDO (sin escribir)")


if __name__ == "__main__":
    main()
