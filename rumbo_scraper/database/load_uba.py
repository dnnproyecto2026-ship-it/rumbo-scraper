"""Validate and load the Universidad de Buenos Aires dataset into Supabase."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rumbo_scraper.database.load_utdt import (
    _boolean, _insert_chunks, _sync_subjects, _upsert_one,
)
from rumbo_scraper.database.load_utn import SCHEMA_CHANNELS
from rumbo_scraper.validators.uba import validate_dataset

DEFAULT_INPUT = Path("data/uba_completo.json")
CORE_SECTIONS = (
    "localidades", "universidades", "sedes", "facultades", "carreras",
    "ofertas", "posgrados", "materias", "autoridades", "redes_contacto",
)
# tipo_posgrado is an enum of degrees; a "Programa de Actualización" is not one
# of them and the column is NOT NULL, so those rows stay out of the database.
LOADABLE_KINDS = frozenset({"Doctorado", "Maestría", "Especialización", "Diplomatura"})


def load_file(path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    validate_dataset(dataset)
    return dataset


def preview(dataset: dict[str, Any]) -> dict[str, int]:
    validate_dataset(dataset)
    data = dataset["datos"]
    counts = {section: len(data[section]) for section in CORE_SECTIONS}
    counts["ofertas_sin_sede_publicada"] = sum(
        1 for row in data["ofertas"] if not row["sede"]
    )
    counts["autoridades_sin_facultad"] = sum(
        1 for row in data["autoridades"] if not row["facultad_nombre"]
    )
    loadable = [row for row in data["posgrados"]
                if row["tipo_posgrado"] in LOADABLE_KINDS]
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

    locality_ids: dict[str, str] = {}
    for row in data["localidades"]:
        saved = _upsert_one(client, "localidades", row, "nombre_localidad,provincia")
        locality_ids[row["nombre_localidad"]] = saved["id"]
    counts["localidades"] = len(locality_ids)

    university_id = _upsert_one(
        client, "universidades", data["universidades"][0], "nombre_oficial"
    )["id"]
    counts["universidades"] = 1

    campus_ids: dict[str, str] = {}
    for row in data["sedes"]:
        saved = _upsert_one(client, "sedes", {
            "universidad_id": university_id, "nombre_sede": row["nombre_sede"],
            "localidad_id": locality_ids.get(str(row["localidad"])),
            "calle": row["calle"], "numero": row["numero"],
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

    # Two faculties publish two buildings and do not say which one teaches
    # each career; ofertas_academicas.sede_id is NOT NULL, so those stay out.
    offers = [row for row in data["ofertas"]
              if campus_ids.get(str(row["sede"])) and career_ids.get(row["carrera_nombre"])]
    counts["ofertas_sin_sede_publicada"] = len(data["ofertas"]) - len(offers)
    for row in offers:
        _upsert_one(client, "ofertas_academicas", {
            "carrera_id": career_ids[row["carrera_nombre"]],
            "sede_id": campus_ids[str(row["sede"])],
            "modalidad": row["modalidad"], "regimen_ingreso": row["regimen_ingreso"],
            "coneau_resolucion": row["coneau_resolucion"],
            "coneau_vigencia_hasta": row["coneau_vigencia_hasta"],
            "tiene_pasantias": _boolean(row["tiene_pasantias"]),
            "tiene_bolsa_trabajo": _boolean(row["tiene_bolsa_trabajo"]),
            "url_oficial": row["url_oficial"], "activa": True,
        }, "carrera_id,sede_id,modalidad")
    counts["ofertas"] = len(offers)

    programmes = [row for row in data["posgrados"]
                  if row["tipo_posgrado"] in LOADABLE_KINDS]
    for row in programmes:
        _upsert_one(client, "posgrados", {
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
    counts["posgrados"] = len(programmes)
    counts["posgrados_sin_tipo_del_esquema"] = len(data["posgrados"]) - len(programmes)

    # Only the careers whose faculty publishes the plan as a table have
    # subjects; the rest keep the link to the document and no rows.
    subjects = [row for row in data["materias"]
                if career_ids.get(row["carrera_o_programa"])]
    counts["materias"] = _sync_subjects(client, university_id, [{
        "universidad_id": university_id,
        "carrera_id": career_ids[row["carrera_o_programa"]],
        "posgrado_id": None,
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

    # The page publishes the authorities of the Rectorado, not of a faculty,
    # and autoridades.facultad_id is NOT NULL, so they have no row.
    counts["autoridades_sin_facultad"] = len(data["autoridades"])

    contacts = [row for row in data["redes_contacto"] if row["canal"] in SCHEMA_CHANNELS]
    counts["redes_contacto"] = _insert_chunks(client, "contactos", [{
        "universidad_id": university_id,
        "facultad_id": faculty_ids.get(str(row["facultad_nombre"])),
        "carrera_id": None, "canal": row["canal"],
        "usuario_o_direccion": row["usuario_o_direccion"],
    } for row in contacts])
    counts["contactos_sin_canal_en_esquema"] = len(data["redes_contacto"]) - len(contacts)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar el dataset de la UBA")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()
    dataset = load_file(args.input)
    counts = apply_dataset(dataset) if args.apply else preview(dataset)
    print("CARGADO" if args.apply else "VALIDADO (sin escribir)")
    for section, count in counts.items():
        print(f"- {section}: {count}")


if __name__ == "__main__":
    main()
