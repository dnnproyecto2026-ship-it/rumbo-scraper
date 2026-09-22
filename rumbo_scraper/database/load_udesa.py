"""Validate and load the verified UdeSA core dataset into Supabase."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rumbo_scraper.database.load_utdt import (
    _boolean, _faculty_name, _sync_subjects, _upsert_one,
)
from rumbo_scraper.validators.udesa import validate_dataset


DEFAULT_INPUT = Path("data/udesa_completo.json")
CORE_SECTIONS = (
    "localidades", "universidades", "sedes", "facultades", "carreras",
    "ofertas", "areas_tematicas", "materias", "posgrados",
)


def load_file(path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    validate_dataset(dataset)
    return dataset


def preview(dataset: dict[str, Any]) -> dict[str, int]:
    validate_dataset(dataset)
    return {section: len(dataset["datos"][section]) for section in CORE_SECTIONS}


def apply_dataset(dataset: dict[str, Any], client: Any | None = None) -> dict[str, int]:
    """Upsert only the UdeSA sections currently verified by the scraper."""
    validate_dataset(dataset)
    data = dataset["datos"]
    if client is None:
        from rumbo_scraper.database.supabase import get_supabase_client
        client = get_supabase_client()
    counts: dict[str, int] = {}

    locality_ids: dict[str, str] = {}
    for row in data["localidades"]:
        saved = _upsert_one(client, "localidades", row, "nombre_localidad,provincia")
        locality_ids[f"{row['nombre_localidad']} — {row['provincia']}"] = saved["id"]
    counts["localidades"] = len(locality_ids)

    university = _upsert_one(
        client, "universidades", data["universidades"][0], "nombre_oficial"
    )
    university_id = university["id"]
    counts["universidades"] = 1

    campus_ids: dict[str, str] = {}
    for row in data["sedes"]:
        saved = _upsert_one(client, "sedes", {
            "universidad_id": university_id,
            "nombre_sede": row["nombre_sede"],
            "localidad_id": locality_ids.get(str(row["localidad"])),
            "calle": row["calle"], "numero": row["numero"],
            "tipo_sede": row["tipo_sede"],
        }, "universidad_id,nombre_sede")
        campus_ids[row["nombre_sede"]] = saved["id"]
    counts["sedes"] = len(campus_ids)

    faculty_ids: dict[str, str] = {}
    faculty_types = {row["nombre_facultad"]: row["tipo_unidad"] for row in data["facultades"]}
    for row in data["facultades"]:
        saved = _upsert_one(client, "facultades", {
            "universidad_id": university_id,
            "nombre_facultad": row["nombre_facultad"],
            "tipo_unidad": row["tipo_unidad"],
        }, "universidad_id,nombre_facultad,tipo_unidad")
        faculty_ids[row["nombre_facultad"]] = saved["id"]
    counts["facultades"] = len(faculty_ids)

    career_ids: dict[str, str] = {}
    faculty_by_career: dict[str, str] = {}
    for row in data["carreras"]:
        faculty = _faculty_name(row["facultad_nombre"])
        faculty_by_career[row["nombre_carrera"]] = str(faculty)
        saved = _upsert_one(client, "carreras", {
            "universidad_id": university_id,
            "facultad_id": faculty_ids.get(str(faculty)),
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

    linked_faculty_campuses: set[tuple[str, str]] = set()
    for row in data["ofertas"]:
        career_id = career_ids[row["carrera_nombre"]]
        campus_id = campus_ids[row["sede"]]
        _upsert_one(client, "ofertas_academicas", {
            "carrera_id": career_id, "sede_id": campus_id,
            "modalidad": row["modalidad"],
            "regimen_ingreso": row["regimen_ingreso"],
            "coneau_resolucion": row["coneau_resolucion"],
            "coneau_vigencia_hasta": row["coneau_vigencia_hasta"],
            "tiene_pasantias": _boolean(row["tiene_pasantias"]),
            "tiene_bolsa_trabajo": _boolean(row["tiene_bolsa_trabajo"]),
            "url_oficial": row["url_oficial"], "activa": True,
        }, "carrera_id,sede_id,modalidad")
        faculty_id = faculty_ids[faculty_by_career[row["carrera_nombre"]]]
        relation = (faculty_id, campus_id)
        if relation not in linked_faculty_campuses:
            _upsert_one(client, "facultades_sedes", {
                "facultad_id": faculty_id, "sede_id": campus_id,
                "es_sede_principal": row["sede"] == "Campus Victoria",
            }, "facultad_id,sede_id")
            linked_faculty_campuses.add(relation)
    counts["ofertas"] = len(data["ofertas"])

    area_ids: dict[str, str] = {}
    for name in sorted({row["area_tematica"] for row in data["materias"] if row["area_tematica"]}):
        saved = _upsert_one(client, "areas_tematicas", {"nombre": name}, "nombre")
        area_ids[name] = saved["id"]
    counts["areas_tematicas"] = len(area_ids)

    postgraduate_ids: dict[str, str] = {}
    for row in data["posgrados"]:
        saved = _upsert_one(client, "posgrados", {
            "universidad_id": university_id,
            "facultad_id": faculty_ids.get(str(_faculty_name(row["facultad_nombre"]))),
            "nombre_programa": row["nombre_programa"],
            "tipo_posgrado": row["tipo_posgrado"],
            "titulo_otorgado": row["titulo_otorgado"],
            "sede_id": campus_ids.get(str(row["sede"])) if row["sede"] else None,
            "modalidad": row["modalidad"],
            "duracion_meses": row["duracion_meses"],
            "requiere_tesis_trabajo_final": _boolean(row["requiere_tesis_trabajo_final"]),
            "requisito_titulo_previo": row["requisito_titulo_previo"],
            "cohorte_inicio": row["cohorte_inicio"],
            "costo_total_programa": row["costo_total_programa"],
            "moneda": row["moneda"],
            "descripcion_breve": row["descripcion_breve"],
            "url_oficial": row["url_oficial"],
        }, "universidad_id,nombre_programa")
        postgraduate_ids[row["nombre_programa"]] = saved["id"]
    counts["posgrados"] = len(postgraduate_ids)

    # carrera_o_programa is polymorphic: the parent is a degree or a
    # postgraduate programme, never both.
    subjects = [{
        "universidad_id": university_id,
        "carrera_id": career_ids.get(row["carrera_o_programa"]),
        "posgrado_id": postgraduate_ids.get(row["carrera_o_programa"]),
        "nombre_materia": row["nombre_materia"],
        "anio_cursada": row["anio_cursada"], "turno": row["turno"],
        "area_tematica_id": area_ids.get(row["area_tematica"]),
        "descripcion_breve": row["descripcion_breve"],
        "regimen": row["regimen"],
        "carga_horaria_semanal": row["carga_horaria_semanal"],
    } for row in data["materias"]]
    counts["materias"] = _sync_subjects(client, university_id, subjects)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the verified UdeSA core dataset")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--apply", action="store_true", help="Write to Supabase")
    args = parser.parse_args()
    dataset = load_file(args.input)
    counts = apply_dataset(dataset) if args.apply else preview(dataset)
    print("CARGADO" if args.apply else "VALIDADO (sin escribir)")
    for section, count in counts.items():
        print(f"- {section}: {count}")


if __name__ == "__main__":
    main()
