"""Load the teachers a university publishes with the subject each teaches.

A reader (`parsers.docentes_*`) leaves ``data/docentes_<sigla>.json``:

    {"universidad": "UNR", "comisiones": [
        {"materia": "Teoría Política I", "codigo": "fcpolit-teoria-politica-i",
         "anio": 2026, "semestre": 0, "seccion": "Cátedra",
         "fuente_url": "https://fcpolit.unr.edu.ar/course/teoria-politica-i/",
         "docentes": [{"nombre": "Mutti, Gastón", "rol": "Profesor Titular"}]}]}

Each subject goes to ``materias_catalogo`` (linked to the plan's subject of
the same name), each chair to ``comisiones_materia`` (a term the source does not say is
kept as 1 and named in the section: "Cátedra (anual)"), each person to ``personas`` with the page that
names them as their profile -- the verifier checks the name there -- and each
teacher of the chair to ``docentes_comision``.

    python -m rumbo_scraper.database.cargar_docentes UNR [--apply]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from rumbo_scraper.normalizers.text import clean_text, comparison_key

_TITULO = re.compile(r"(?i)^(?:dr|dra|lic|mg|mgter|msc|ing|prof|profa|abog|cdor|cra|arq|esp|ts|psic)\.?\s+")


def nombre_de_persona(texto: str) -> str | None:
    """"Mutti, Gastón" -> "Gastón Mutti"; "Dra. Lucrecia ROMÁN" -> "Lucrecia Román".
    None for what is not a person's name."""
    texto = clean_text(texto).strip(" .;,-")
    while _TITULO.match(texto):
        texto = _TITULO.sub("", texto, count=1)
    if "," in texto:
        apellido, _, nombre = texto.partition(",")
        texto = f"{nombre.strip()} {apellido.strip()}"
    palabras = texto.split()
    if not 2 <= len(palabras) <= 6 or any(ch.isdigit() for ch in texto) or "@" in texto:
        return None
    if texto.isupper() or any(p.isupper() and len(p) > 2 for p in palabras):
        texto = " ".join(p.capitalize() if p.isupper() else p for p in palabras)
    return texto


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar docentes con sus materias")
    parser.add_argument("universidad", help="Nombre corto (lee data/docentes_<sigla>.json)")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    from rumbo_scraper.database.load_utdt_catalog import _upsert_chunks
    from rumbo_scraper.database.supabase import get_supabase_client, select_all

    datos = json.loads(Path(f"data/docentes_{args.universidad.lower()}.json").read_text())
    client = get_supabase_client()
    universidad = client.table("universidades").select("id").eq(
        "nombre_corto", datos["universidad"]).execute().data[0]["id"]

    comisiones = [c for c in datos["comisiones"] if c.get("materia") and c.get("docentes")]
    personas: dict[str, dict[str, Any]] = {}
    for comision in comisiones:
        for docente in comision["docentes"]:
            nombre = nombre_de_persona(docente["nombre"])
            if nombre:
                personas.setdefault(comparison_key(nombre), {"nombre": nombre, "perfil": comision["fuente_url"]})
    print(f"{datos['universidad']}: {len(comisiones)} materias con docentes · {len(personas)} personas")
    if not args.apply:
        for comision in comisiones[:5]:
            print("  ", comision["materia"], "·", [nombre_de_persona(d["nombre"]) for d in comision["docentes"]])
        return

    # The file is the whole of what its readers publish: a subject of theirs
    # that no longer comes (or came under another key) goes, with its chairs.
    prefijos = tuple({c["codigo"].split("-", 1)[0] + "-" for c in comisiones})
    nuevas_claves = {c["codigo"] for c in comisiones}
    sobrantes = [m["id"] for m in select_all(client.table("materias_catalogo").select("id,codigo").eq(
        "universidad_id", universidad)) if m["codigo"].startswith(prefijos) and m["codigo"] not in nuevas_claves]
    for inicio in range(0, len(sobrantes), 100):
        tanda = sobrantes[inicio:inicio + 100]
        viejas = [c["id"] for c in client.table("comisiones_materia").select("id").in_(
            "materia_catalogo_id", tanda).execute().data]
        for sub in range(0, len(viejas), 100):
            client.table("docentes_comision").delete().in_("comision_id", viejas[sub:sub + 100]).execute()
            client.table("horarios_comision").delete().in_("comision_id", viejas[sub:sub + 100]).execute()
            client.table("comisiones_materia").delete().in_("id", viejas[sub:sub + 100]).execute()
        client.table("materias_catalogo_vinculos").delete().in_("materia_catalogo_id", tanda).execute()
        client.table("materias_catalogo").delete().in_("id", tanda).execute()
    if sobrantes:
        print(f"  materias que ya no vienen: {len(sobrantes)}")

    materias = _upsert_chunks(client, "materias_catalogo", [
        {"universidad_id": universidad, "codigo": c["codigo"], "nombre": c["materia"],
         "fuente_url": c["fuente_url"], "activa": True} for c in {c["codigo"]: c for c in comisiones}.values()
    ], "universidad_id,codigo")
    materia_id = {m["codigo"]: m["id"] for m in materias}

    # The subject of the plan with the same name is the one the chair teaches.
    del_plan = defaultdict(list)
    for m in select_all(client.table("materias").select("id,nombre_materia").eq("universidad_id", universidad)):
        del_plan[comparison_key(m["nombre_materia"])].append(m["id"])
    vinculos = [{"materia_id": plan, "materia_catalogo_id": materia_id[c["codigo"]],
                 "metodo": "nombre_exacto", "confianza": 1}
                for c in {c["codigo"]: c for c in comisiones}.values()
                for plan in del_plan.get(comparison_key(c["materia"]), [])]
    if vinculos:
        _upsert_chunks(client, "materias_catalogo_vinculos", vinculos, "materia_id,materia_catalogo_id")

    # The chairs of these subjects are replaced whole: a term the source does
    # not say stays empty, and an empty term cannot be matched on.
    catalogo_ids = list(materia_id.values())
    for inicio in range(0, len(catalogo_ids), 100):
        viejas = [c["id"] for c in client.table("comisiones_materia").select("id").in_(
            "materia_catalogo_id", catalogo_ids[inicio:inicio + 100]).execute().data]
        for tanda in range(0, len(viejas), 100):
            client.table("docentes_comision").delete().in_("comision_id", viejas[tanda:tanda + 100]).execute()
            client.table("horarios_comision").delete().in_("comision_id", viejas[tanda:tanda + 100]).execute()
            client.table("comisiones_materia").delete().in_("id", viejas[tanda:tanda + 100]).execute()
    guardadas = []
    # The table takes a term of 1 or 2; a chair whose source does not say it
    # is kept under 1, and its section says so (the export does not use the
    # term: only who teaches which subject).
    for c in comisiones:
        if c.get("semestre") not in (1, 2):
            c["seccion"] = f"{c.get('seccion') or 'Cátedra'} ({c.get('duracion') or 'cuatrimestre no informado'})"
            c["semestre"] = 1
    nuevas = [{"materia_catalogo_id": materia_id[c["codigo"]], "anio": c.get("anio") or 2026,
               "semestre": c["semestre"], "seccion": c.get("seccion") or "Cátedra",
               "fuente_url": c["fuente_url"]}
              for c in {(c["codigo"], c.get("seccion") or "Cátedra"): c for c in comisiones}.values()]
    for inicio in range(0, len(nuevas), 200):
        guardadas += client.table("comisiones_materia").insert(nuevas[inicio:inicio + 200]).execute().data
    comision_id = {(g["materia_catalogo_id"], g["seccion"]): g["id"] for g in guardadas}

    gente = _upsert_chunks(client, "personas", [
        {"universidad_id": universidad, "nombre_completo": p["nombre"], "perfil_url": p["perfil"],
         "fuente_url": p["perfil"], "activa": True} for p in personas.values()
    ], "universidad_id,nombre_completo")
    persona_id = {comparison_key(p["nombre_completo"]): p["id"] for p in gente}

    ids = list(comision_id.values())
    filas = []
    for c in comisiones:
        cid = comision_id.get((materia_id[c["codigo"]], c.get("seccion") or "Cátedra"))
        for docente in c["docentes"]:
            nombre = nombre_de_persona(docente["nombre"])
            if cid and nombre:
                filas.append({"comision_id": cid, "persona_id": persona_id[comparison_key(nombre)],
                              "nombre_docente_fuente": clean_text(docente["nombre"]),
                              "tipo_clase": docente.get("rol")})
    for inicio in range(0, len(filas), 500):
        client.table("docentes_comision").insert(filas[inicio:inicio + 500]).execute()
    print(f"  materias {len(materia_id)} · vinculadas al plan {len(vinculos)} · comisiones {len(ids)} · "
          f"personas {len(persona_id)} · docentes de comisión {len(filas)}")


if __name__ == "__main__":
    main()
