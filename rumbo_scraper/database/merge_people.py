"""Merge people stored twice under different spellings of the same name.

`personas` is unique over the exact `nombre_completo`, while the loaders match
an existing person with `comparison_key`, which ignores accents and case. When
a loader could not see an existing row it inserted the same person again under
the spelling of its own source -- the course catalogue types teacher names
without accents -- and both rows stayed.

The reading fix in `select_all` stops new duplicates appearing. This tool
repairs the ones already stored: it points every reference at the surviving
row and removes the redundant one.
"""

from __future__ import annotations

import argparse
import collections
from typing import Any

from rumbo_scraper.database.supabase import get_supabase_client, select_all
from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.normalizers.url import is_official_url

REFERENCING_TABLES = ("roles_academicos", "docentes_comision")


def _richness(row: dict[str, Any], domain: str) -> tuple[int, int, int]:
    """Rank a row by the quality of the evidence behind it.

    The spelling is not the criterion. Accents would be a tempting rule, and it
    is wrong: "Juan Carlos Rodriguez" without them comes from the university
    site while the accented one comes from the course catalogue. What decides
    is where the row was read -- a page of the university outranks the
    catalogue rendered by a third-party report.
    """
    return (
        1 if is_official_url(row.get("fuente_url"), domain, require_https=False) else 0,
        1 if row.get("perfil_url") else 0,
        1 if row.get("biografia") else 0,
    )


def find_duplicates(
    client: Any, university_id: str, domain: str
) -> list[list[dict[str, Any]]]:
    """Group the rows that are the same person under different spellings."""
    rows = select_all(
        client.table("personas")
        .select("id,nombre_completo,perfil_url,biografia,fuente_url")
        .eq("universidad_id", university_id)
    )
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        groups[comparison_key(row["nombre_completo"])].append(row)
    return [
        sorted(group, key=lambda row: _richness(row, domain), reverse=True)
        for group in groups.values() if len(group) > 1
    ]


def merge(client: Any, groups: list[list[dict[str, Any]]]) -> dict[str, int]:
    """Repoint every reference at the surviving row and drop the others."""
    moved = 0
    removed = 0
    for group in groups:
        keeper, *redundant = group
        for row in redundant:
            for table in REFERENCING_TABLES:
                references = select_all(
                    client.table(table).select("id").eq("persona_id", row["id"])
                )
                for reference in references:
                    client.table(table).update({"persona_id": keeper["id"]}) \
                        .eq("id", reference["id"]).execute()
                moved += len(references)
            client.table("personas").delete().eq("id", row["id"]).execute()
            removed += 1
    return {"referencias_movidas": moved, "personas_eliminadas": removed}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fusionar personas duplicadas por grafía del nombre"
    )
    parser.add_argument("--universidad", default="Universidad Torcuato Di Tella")
    parser.add_argument("--dominio", default="utdt.edu",
                        help="dominio oficial que decide qué fila se conserva")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    client = get_supabase_client()
    universities = client.table("universidades").select("id") \
        .eq("nombre_oficial", args.universidad).limit(1).execute().data
    if not universities:
        print(f"No existe la universidad {args.universidad!r}.")
        return 1

    groups = find_duplicates(client, universities[0]["id"], args.dominio)
    if not groups:
        print(f"{args.universidad}: sin personas duplicadas.")
        return 0

    print(f"{args.universidad}: {len(groups)} personas duplicadas\n")
    for group in groups:
        keeper, *redundant = group
        print(f"  se conserva  {keeper['nombre_completo']!r}"
              f"   fuente: {str(keeper['fuente_url'])[:52]}")
        for row in redundant:
            print(f"  se elimina   {row['nombre_completo']!r}"
                  f"   fuente: {str(row['fuente_url'])[:52]}")

    if not args.apply:
        print("\nVista previa; usá --apply para fusionarlas.")
        return 0

    counts = merge(client, groups)
    print(f"\nFUSIONADO: {counts['personas_eliminadas']} personas eliminadas, "
          f"{counts['referencias_movidas']} referencias movidas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
