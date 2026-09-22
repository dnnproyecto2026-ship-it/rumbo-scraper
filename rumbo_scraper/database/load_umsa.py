"""Validate and load the UMSA dataset into Supabase."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rumbo_scraper.database.load_utdt import (
    _boolean, _insert_chunks, _sync_subjects, _upsert_chunks, _upsert_one,
)
from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.validators.umsa import validate_dataset

DEFAULT_INPUT = Path("data/umsa_completo.json")
CORE_SECTIONS = (
    "localidades", "universidades", "sedes", "facultades", "carreras",
    "ofertas", "materias", "posgrados", "autoridades",
)


def load_file(path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    validate_dataset(dataset)
    return dataset


def loadable(dataset: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split what the shared schema accepts from what it rejects."""
    data = dataset["datos"]
    programmes = [row for row in data["posgrados"] if row["tipo_posgrado"]]
    parents = {row["nombre_carrera"] for row in data["carreras"]}
    parents |= {row["nombre_programa"] for row in programmes}
    subjects = [row for row in data["materias"] if row["carrera_o_programa"] in parents]
    return programmes, subjects


def preview(dataset: dict[str, Any]) -> dict[str, int]:
    validate_dataset(dataset)
    programmes, subjects = loadable(dataset)
    counts = {section: len(dataset["datos"][section]) for section in CORE_SECTIONS}
    counts["posgrados"] = len(programmes)
    counts["materias"] = len(subjects)
    counts["personas"] = len(dataset["directorio_academico"]["personas"])
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
        locality_ids[f"{row['nombre_localidad']} — {row['provincia']}"] = saved["id"]
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

    # UMSA does not state which campus teaches each programme, and
    # ofertas_academicas.sede_id is NOT NULL, so the offers stay out.
    offers = [row for row in data["ofertas"] if campus_ids.get(str(row["sede"]))]
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

    postgraduate_ids: dict[str, str] = {}
    programmes, subjects_rows = loadable(dataset)
    for row in programmes:
        saved = _upsert_one(client, "posgrados", {
            "universidad_id": university_id,
            "facultad_id": faculty_ids.get(str(row["facultad_nombre"])),
            "nombre_programa": row["nombre_programa"],
            "tipo_posgrado": row["tipo_posgrado"],
            "titulo_otorgado": row["titulo_otorgado"],
            "sede_id": campus_ids.get(str(row["sede"])),
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
    counts["posgrados_omitidos_sin_tipo"] = len(data["posgrados"]) - len(programmes)

    counts["materias"] = _sync_subjects(client, university_id, [{
        "universidad_id": university_id,
        "carrera_id": career_ids.get(row["carrera_o_programa"]),
        "posgrado_id": postgraduate_ids.get(row["carrera_o_programa"]),
        "nombre_materia": row["nombre_materia"], "anio_cursada": row["anio_cursada"],
        "turno": row["turno"], "area_tematica_id": None,
        "descripcion_breve": row["descripcion_breve"], "regimen": row["regimen"],
        "carga_horaria_semanal": row["carga_horaria_semanal"],
    } for row in subjects_rows])

    directory = dataset.get("directorio_academico", {})
    saved_people = _upsert_chunks(client, "personas", [{
        "universidad_id": university_id, "nombre_completo": row["nombre_completo"],
        "email": row["email"], "perfil_url": row["perfil_url"],
        "formacion": row["formacion"], "biografia": row["biografia"],
        "fuente_url": row["fuente_url"], "activa": True,
    } for row in directory.get("personas", [])], "universidad_id,nombre_completo")
    counts["personas"] = len({comparison_key(r["nombre_completo"]) for r in saved_people})

    # autoridades.facultad_id is NOT NULL and the catalogue lists the
    # authorities of the university, not of a faculty, so they have no row.
    counts["autoridades_sin_facultad"] = len(data["autoridades"])
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar el dataset de UMSA")
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
