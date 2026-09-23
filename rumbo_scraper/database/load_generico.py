"""Load a catalogue read by the general reader into Supabase.

One loader serves every university read that way, because they all arrive in
the same contract. What it refuses to load it counts and names, so a run says
what the schema kept out rather than losing it quietly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rumbo_scraper.database.load_utdt import _insert_chunks, _sync_subjects, _upsert_one
from rumbo_scraper.database.load_utn import SCHEMA_CHANNELS
from rumbo_scraper.validators.generico import validate_dataset

DEFAULT_DIR = Path("data")
LOADABLE_KINDS = frozenset({"Doctorado", "Maestría", "Especialización", "Diplomatura"})


def load_file(path: Path) -> dict[str, Any]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    validate_dataset(dataset)
    return dataset


def preview(dataset: dict[str, Any]) -> dict[str, int]:
    data = dataset["datos"]
    loadable = [row for row in data["posgrados"] if row["tipo_posgrado"] in LOADABLE_KINDS]
    return {
        "universidades": 1,
        "facultades": len(data["facultades"]),
        "carreras": len(data["carreras"]),
        "posgrados": len(loadable),
        "posgrados_sin_tipo_del_esquema": len(data["posgrados"]) - len(loadable),
        "materias": len(data["materias"]),
        "autoridades": len(data["autoridades"]),
        "redes_contacto": len(data["redes_contacto"]),
        "ofertas_sin_sede_publicada": len(data["ofertas"]),
    }


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
            "tiene_titulo_intermedio": None,
            "duracion_anios": row["duracion_anios"],
            "descripcion_breve": row["descripcion_breve"],
            "cantidad_materias_total": row["cantidad_materias_total"],
        }, "universidad_id,nombre_carrera")
        career_ids[row["nombre_carrera"]] = saved["id"]
    counts["carreras"] = len(career_ids)

    # ofertas_academicas.sede_id is NOT NULL and the general reader does not
    # read which campus teaches a career, so the offers stay in the artifact.
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
            "requiere_tesis_trabajo_final": None,
            "requisito_titulo_previo": row["requisito_titulo_previo"],
            "cohorte_inicio": row["cohorte_inicio"],
            "costo_total_programa": None, "moneda": None,
            "descripcion_breve": row["descripcion_breve"],
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
        "turno": None, "area_tematica_id": None, "descripcion_breve": None,
        "regimen": None, "carga_horaria_semanal": None,
    } for row in subjects])

    # Both tables are rewritten whole: they are read from the same pages as
    # the careers, so a second run should replace them, not double them.
    if faculty_ids:
        client.table("autoridades").delete().in_(
            "facultad_id", list(faculty_ids.values())).execute()
    authorities = [row for row in data["autoridades"]
                   if faculty_ids.get(str(row["facultad_nombre"]))]
    counts["autoridades"] = _insert_chunks(client, "autoridades", [{
        "facultad_id": faculty_ids[str(row["facultad_nombre"])],
        "carrera_id": career_ids.get(str(row["carrera"])),
        "cargo": row["cargo"], "tipo": row["tipo"],
        "nombre_autoridad": row["nombre_autoridad"],
    } for row in authorities])
    counts["autoridades_sin_facultad"] = len(data["autoridades"]) - len(authorities)

    client.table("contactos").delete().eq("universidad_id", university_id).execute()
    channels = [row for row in data["redes_contacto"] if row["canal"] in SCHEMA_CHANNELS]
    counts["redes_contacto"] = _insert_chunks(client, "contactos", [{
        "universidad_id": university_id,
        "facultad_id": faculty_ids.get(str(row["facultad_nombre"])),
        "carrera_id": None, "canal": row["canal"],
        "usuario_o_direccion": row["usuario_o_direccion"],
    } for row in channels])
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar un catálogo leído en general")
    parser.add_argument("universidad", help="Sigla, como figura en catalogo.py")
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    path = args.input or DEFAULT_DIR / f"{args.universidad.lower()}_completo.json"
    dataset = load_file(path)
    counts = apply_dataset(dataset) if args.apply else preview(dataset)
    print("CARGADO" if args.apply else "VALIDADO (sin escribir)")
    for section, count in counts.items():
        print(f"- {section}: {count}")


if __name__ == "__main__":
    main()
