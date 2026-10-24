"""Validate and load the la UCEMA dataset into Supabase.

A whole load syncs the subjects to the reading's, and the reading has none
(UCEMA's plans come from the plan readers): it would delete them. A newer
reading's careers go in with ``--solo-carreras``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rumbo_scraper.database.load_utdt import (
    _boolean, _insert_chunks, _sync_subjects, _upsert_one,
)
from rumbo_scraper.database.load_utn import SCHEMA_CHANNELS
from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.validators.ucema import validate_dataset

DEFAULT_INPUT = Path("data/ucema_completo.json")
CORE_SECTIONS = (
    "universidades", "carreras", "ofertas", "posgrados",
)
LOADABLE_KINDS = frozenset({"Doctorado", "Maestría", "Especialización", "Diplomatura"})


def load_file(path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    validate_dataset(dataset)
    return dataset


def preview(dataset: dict[str, Any]) -> dict[str, int]:
    validate_dataset(dataset)
    data = dataset["datos"]
    counts = {section: len(data[section]) for section in CORE_SECTIONS}
    loadable = [row for row in data["posgrados"] if row["tipo_posgrado"] in LOADABLE_KINDS]
    counts["posgrados"] = len(loadable)
    counts["posgrados_sin_tipo_del_esquema"] = len(data["posgrados"]) - len(loadable)
    return counts


def apply_dataset(dataset: dict[str, Any], client: Any | None = None) -> dict[str, int]:
    validate_dataset(dataset)
    data = dataset["datos"]
    if client is None:
        from rumbo_scraper.database.supabase import get_supabase_client
        client = get_supabase_client()
    counts: dict[str, int] = {}

    university_id = _upsert_one(
        client, "universidades", data["universidades"][0], "nombre_oficial"
    )["id"]
    counts["universidades"] = 1

    campus_ids: dict[str, str] = {}
    for row in data["sedes"]:
        saved = _upsert_one(client, "sedes", {
            "universidad_id": university_id, "nombre_sede": row["nombre_sede"],
            "localidad_id": None, "calle": row["calle"], "numero": row["numero"],
            "tipo_sede": row["tipo_sede"],
        }, "universidad_id,nombre_sede")
        campus_ids[row["nombre_sede"]] = saved["id"]
    counts["sedes"] = len(campus_ids)

    faculty_ids: dict[str, str] = {}
    for row in data["facultades"]:
        saved = _upsert_one(client, "facultades", {
            "universidad_id": university_id,
            "nombre_facultad": row["nombre_facultad"],
            "tipo_unidad": row["tipo_unidad"],
        }, "universidad_id,nombre_facultad,tipo_unidad")
        faculty_ids[row["nombre_facultad"]] = saved["id"]
    counts["facultades"] = len(faculty_ids)

    career_ids: dict[str, str] = {}
    for row in data["carreras"]:
        saved = _upsert_one(client, "carreras", {
            "universidad_id": university_id,
            "facultad_id": faculty_ids.get(str(row["facultad_nombre"])),
            "nombre_carrera": row["nombre_carrera"],
            "denominacion_canonica": row["denominacion_canonica"],
            "nivel": row["nivel"], "titulo_otorgado": row["titulo_otorgado"],
            "tiene_titulo_intermedio": _boolean(row["tiene_titulo_intermedio"]),
            "duracion_anios": row["duracion_anios"],
            "descripcion_breve": row["descripcion_breve"],
            "cantidad_materias_total": row["cantidad_materias_total"],
        }, "universidad_id,nombre_carrera")
        career_ids[row["nombre_carrera"]] = saved["id"]
    counts["carreras"] = len(career_ids)

    # The site names the campuses of the faculty, not the one that teaches
    # each career, and ofertas_academicas.sede_id is NOT NULL.
    counts["ofertas_sin_sede_publicada"] = len(data["ofertas"])

    postgraduate_ids: dict[str, str] = {}
    programmes = [row for row in data["posgrados"] if row["tipo_posgrado"] in LOADABLE_KINDS]
    for row in programmes:
        saved = _upsert_one(client, "posgrados", {
            "universidad_id": university_id,
            "facultad_id": faculty_ids.get(str(row["facultad_nombre"])),
            "nombre_programa": row["nombre_programa"],
            "tipo_posgrado": row["tipo_posgrado"],
            "titulo_otorgado": row["titulo_otorgado"], "sede_id": None,
            "modalidad": row["modalidad"], "duracion_meses": row["duracion_meses"],
            "requiere_tesis_trabajo_final": _boolean(row["requiere_tesis_trabajo_final"]),
            "requisito_titulo_previo": row["requisito_titulo_previo"],
            "cohorte_inicio": row["cohorte_inicio"],
            "costo_total_programa": row["costo_total_programa"],
            "moneda": row["moneda"], "descripcion_breve": row["descripcion_breve"],
            "url_oficial": row["url_oficial"],
        }, "universidad_id,nombre_programa")
        postgraduate_ids[row["nombre_programa"]] = saved["id"]
    counts["posgrados"] = len(postgraduate_ids)
    counts["posgrados_sin_tipo_del_esquema"] = len(data["posgrados"]) - len(programmes)

    subjects = [row for row in data["materias"]
                if career_ids.get(row["carrera_o_programa"])
                or postgraduate_ids.get(row["carrera_o_programa"])]
    counts["materias"] = _sync_subjects(client, university_id, [{
        "universidad_id": university_id,
        "carrera_id": career_ids.get(row["carrera_o_programa"]),
        "posgrado_id": postgraduate_ids.get(row["carrera_o_programa"]),
        "nombre_materia": row["nombre_materia"], "anio_cursada": row["anio_cursada"],
        "turno": row["turno"], "area_tematica_id": None,
        "descripcion_breve": row["descripcion_breve"], "regimen": row["regimen"],
        "carga_horaria_semanal": row["carga_horaria_semanal"],
    } for row in subjects])

    client.table("contactos").delete().eq("universidad_id", university_id).execute()
    if faculty_ids:
        client.table("autoridades").delete().in_(
            "facultad_id", list(faculty_ids.values())
        ).execute()
    authorities = [row for row in data["autoridades"]
                   if faculty_ids.get(str(row["facultad_nombre"]))]
    counts["autoridades"] = _insert_chunks(client, "autoridades", [{
        "facultad_id": faculty_ids[str(row["facultad_nombre"])],
        "carrera_id": None, "cargo": row["cargo"], "tipo": row["tipo"],
        "nombre_autoridad": row["nombre_autoridad"],
    } for row in authorities])

    contacts = [row for row in data["redes_contacto"] if row["canal"] in SCHEMA_CHANNELS]
    counts["redes_contacto"] = _insert_chunks(client, "contactos", [{
        "universidad_id": university_id,
        "facultad_id": faculty_ids.get(str(row["facultad_nombre"])),
        "carrera_id": None, "canal": row["canal"],
        "usuario_o_direccion": row["usuario_o_direccion"],
    } for row in contacts])
    return counts


# Facts a newer reading may give a career the DB holds without them.
_FILLABLE = ("titulo_otorgado", "duracion_anios", "descripcion_breve")


def load_careers(dataset: dict[str, Any], apply: bool,
                 client: Any | None = None) -> list[tuple[str, str, dict[str, Any]]]:
    """Add the careers the scraper DB lacks and fill the facts it lacks of
    the ones it has; nothing else, so the subjects stay. Returns what was
    (or, without ``apply``, would be) written: ("nueva" | "completada",
    name, fields)."""
    validate_dataset(dataset)
    data = dataset["datos"]
    if client is None:
        from rumbo_scraper.database.supabase import get_supabase_client
        client = get_supabase_client()
    university_id = client.table("universidades").select("id").eq(
        "nombre_oficial", data["universidades"][0]["nombre_oficial"]).execute().data[0]["id"]
    loaded = {comparison_key(row["nombre_carrera"]): row for row in client.table("carreras").select(
        "id,nombre_carrera," + ",".join(_FILLABLE)).eq("universidad_id", university_id).execute().data}
    actions: list[tuple[str, str, dict[str, Any]]] = []
    for row in data["carreras"]:
        held = loaded.get(comparison_key(row["nombre_carrera"]))
        if held is None:
            fields = {
                "universidad_id": university_id, "facultad_id": None,
                "nombre_carrera": row["nombre_carrera"],
                "denominacion_canonica": row["denominacion_canonica"],
                "nivel": row["nivel"], "titulo_otorgado": row["titulo_otorgado"],
                "tiene_titulo_intermedio": _boolean(row["tiene_titulo_intermedio"]),
                "duracion_anios": row["duracion_anios"],
                "descripcion_breve": row["descripcion_breve"],
                "cantidad_materias_total": row["cantidad_materias_total"],
            }
            actions.append(("nueva", row["nombre_carrera"], fields))
            if apply:
                _upsert_one(client, "carreras", fields, "universidad_id,nombre_carrera")
            continue
        fields = {key: row[key] for key in _FILLABLE if held[key] is None and row[key] is not None}
        if fields:
            actions.append(("completada", held["nombre_carrera"], fields))
            if apply:
                client.table("carreras").update(fields).eq("id", held["id"]).execute()
    return actions


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar el dataset de la UCEMA")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    # Only careers, into the scraper DB; the reading becomes data/ucema_completo.json.
    parser.add_argument("--solo-carreras", action="store_true")
    args = parser.parse_args()
    dataset = load_file(args.input)
    if args.solo_carreras:
        actions = load_careers(dataset, args.apply)
        if args.apply and args.input.resolve() != DEFAULT_INPUT.resolve():
            # The export takes each career's page from the artefact.
            DEFAULT_INPUT.write_text(args.input.read_text(encoding="utf-8"), encoding="utf-8")
        print("CARGADO" if args.apply else "VISTA PREVIA (sin escribir)")
        for kind, name, fields in actions:
            shown = {k: v for k, v in fields.items() if k not in ("universidad_id", "facultad_id")}
            print(f"- {kind}: {name} {shown}")
        return
    counts = apply_dataset(dataset) if args.apply else preview(dataset)
    print("CARGADO" if args.apply else "VALIDADO (sin escribir)")
    for section, count in counts.items():
        print(f"- {section}: {count}")


if __name__ == "__main__":
    main()
