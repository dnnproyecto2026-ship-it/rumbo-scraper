"""Validate and load the verified UdeSA core dataset into Supabase."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rumbo_scraper.database.load_utdt import (
    _boolean, _faculty_name, _insert_chunks, _sync_subjects, _upsert_chunks, _upsert_one,
)
from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.validators.udesa import validate_dataset


DEFAULT_INPUT = Path("data/udesa_completo.json")
CORE_SECTIONS = (
    "localidades", "universidades", "sedes", "facultades", "carreras",
    "ofertas", "areas_tematicas", "materias", "posgrados", "autoridades",
    "becas", "servicios_estudiantiles", "actividades_extracurriculares",
    "alojamiento", "programas_internacionales", "actividades", "redes_contacto",
)


def load_file(path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    validate_dataset(dataset)
    return dataset


def loadable(dataset: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split what the schema accepts from what it rejects.

    A postgraduate without a published type cannot be written, because the
    column is NOT NULL over a four-value enum, and its subjects have no parent
    to hang from.
    """
    data = dataset["datos"]
    programmes = [row for row in data["posgrados"] if row["tipo_posgrado"]]
    parents = {row["nombre_carrera"] for row in data["carreras"]}
    parents |= {row["nombre_programa"] for row in programmes}
    subjects = [row for row in data["materias"] if row["carrera_o_programa"] in parents]
    return programmes, subjects


def preview(dataset: dict[str, Any]) -> dict[str, int]:
    """Count what a load would actually write, not what the file holds."""
    validate_dataset(dataset)
    programmes, subjects = loadable(dataset)
    counts = {section: len(dataset["datos"][section]) for section in CORE_SECTIONS}
    counts["posgrados"] = len(programmes)
    counts["materias"] = len(subjects)
    return counts


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
    # tipo_posgrado is NOT NULL and its enum accepts only Diplomatura,
    # Especialización, Maestría and Doctorado. UdeSA publishes no type for ten
    # programmes -- MBA, the "Master in ..." family, Profesorado Universitario,
    # Programa en Cultura Brasileña -- and inventing one would state something
    # the university does not. They stay in the JSON and out of the database
    # until the shared schema allows an unclassified programme.
    skipped_postgraduates = [
        row["nombre_programa"] for row in data["posgrados"] if not row["tipo_posgrado"]
    ]
    for row in data["posgrados"]:
        if not row["tipo_posgrado"]:
            continue
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
    counts["posgrados_omitidos_sin_tipo"] = len(skipped_postgraduates)

    # carrera_o_programa is polymorphic: the parent is a degree or a
    # postgraduate programme, never both.
    loadable_parents = set(career_ids) | set(postgraduate_ids)
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
    } for row in data["materias"] if row["carrera_o_programa"] in loadable_parents]
    counts["materias"] = _sync_subjects(client, university_id, subjects)

    # These tables have no natural key, so this university's rows are rebuilt.
    for table in ("becas", "servicios_estudiantiles",
                  "actividades_extracurriculares", "alojamientos",
                  "programas_internacionales", "actividades", "contactos"):
        client.table(table).delete().eq("universidad_id", university_id).execute()

    counts["becas"] = _insert_chunks(client, "becas", [{
        "universidad_id": university_id,
        "nombre_beca": row["nombre_beca"], "nivel": row["nivel"],
        "tipo_beca": row["tipo_beca"],
        "cobertura_descripcion": row["cobertura_descripcion"],
        "porcentaje_maximo": row["porcentaje_maximo"], "requisitos": row["requisitos"],
        "proceso_postulacion": row["proceso_postulacion"],
        "renovacion": row["renovacion"], "fecha_cierre": row["fecha_cierre"],
        "url_postulacion": row["url_postulacion"], "contacto": row["contacto"],
        "fuente_url": row["fuente_url"],
    } for row in data["becas"]])

    counts["servicios_estudiantiles"] = _insert_chunks(client, "servicios_estudiantiles", [{
        "universidad_id": university_id, "sede_id": None,
        "categoria": row["categoria"], "nombre_servicio": row["nombre_servicio"],
        "descripcion": row["descripcion"], "contacto": row["contacto"],
        "url": row["url"], "fuente_url": row["fuente_url"],
    } for row in data["servicios_estudiantiles"]])

    counts["actividades_extracurriculares"] = _insert_chunks(
        client, "actividades_extracurriculares", [{
            "universidad_id": university_id, "sede_id": None,
            "categoria": row["categoria"], "nombre_actividad": row["nombre_actividad"],
            "descripcion": row["descripcion"], "contacto": row["contacto"],
            "url": row["url"], "fuente_url": row["fuente_url"],
        } for row in data["actividades_extracurriculares"]])

    counts["alojamiento"] = _insert_chunks(client, "alojamientos", [{
        "universidad_id": university_id, "sede_id": None,
        "tipo_apoyo": row["tipo_apoyo"], "tipo_alojamiento": row["tipo_alojamiento"],
        "residencia_propia": _boolean(row["residencia_propia"]),
        "descripcion": row["descripcion"], "contacto": row["contacto"],
        "url": row["url"], "fuente_url": row["fuente_url"],
    } for row in data["alojamiento"]])

    counts["programas_internacionales"] = _insert_chunks(
        client, "programas_internacionales", [{
            "universidad_id": university_id, "nivel": row["nivel"],
            "tipo_programa": row["tipo_programa"],
            "nombre_programa": row["nombre_programa"],
            "cantidad_convenios": row["cantidad_convenios"],
            "duracion_maxima": row["duracion_maxima"],
            "reconocimiento_academico": _boolean(row["reconocimiento_academico"]),
            "arancel_destino_cubierto": _boolean(row["arancel_destino_cubierto"]),
            "requisitos": row["requisitos"], "url": row["url"],
            "fuente_url": row["fuente_url"],
        } for row in data["programas_internacionales"]])

    counts["actividades"] = _insert_chunks(client, "actividades", [{
        "universidad_id": university_id,
        "carrera_id": career_ids.get(row["carrera_o_programa"]),
        "posgrado_id": postgraduate_ids.get(row["carrera_o_programa"]),
        "tipo_actividad": row["tipo_actividad"],
        "nombre_actividad": row["nombre_actividad"],
        "obligatoria": _boolean(row["obligatoria"]),
        "carga_horaria_total": row["carga_horaria_total"],
        "descripcion_breve": row["descripcion_breve"],
    } for row in data["actividades"]
        if row["carrera_o_programa"] in career_ids
        or row["carrera_o_programa"] in postgraduate_ids])

    counts["redes_contacto"] = _insert_chunks(client, "contactos", [{
        "universidad_id": university_id,
        "facultad_id": faculty_ids.get(str(_faculty_name(row["facultad_nombre"]))),
        "carrera_id": None, "canal": row["canal"],
        "usuario_o_direccion": row["usuario_o_direccion"],
    } for row in data["redes_contacto"]])

    directory = dataset.get("directorio_academico", {})
    saved_people = _upsert_chunks(client, "personas", [{
        "universidad_id": university_id,
        "nombre_completo": row["nombre_completo"], "email": row["email"],
        "perfil_url": row["perfil_url"], "formacion": row["formacion"],
        "biografia": row["biografia"], "fuente_url": row["fuente_url"],
        "activa": True,
    } for row in directory.get("personas", [])], "universidad_id,nombre_completo")
    person_ids = {comparison_key(row["nombre_completo"]): row["id"] for row in saved_people}
    counts["personas"] = len(person_ids)

    # Roles have no natural key, so they are rebuilt for this university only.
    client.table("roles_academicos").delete().eq("universidad_id", university_id).execute()
    # roles_academicos is unique over (persona, facultad, carrera, materia,
    # cargo) and has no postgraduate column, so every role a person holds in
    # postgraduate programmes of one unit collapses into a single faculty-level
    # role. Deduplicating here by the same identity keeps the insert honest
    # instead of letting the database reject the whole batch.
    academic_roles: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in directory.get("roles_academicos", []):
        person_id = person_ids.get(comparison_key(row["nombre_completo"]))
        if person_id is None:
            continue
        payload = {
            "persona_id": person_id,
            "universidad_id": university_id,
            "facultad_id": faculty_ids.get(str(_faculty_name(row["facultad_nombre"]))),
            "carrera_id": career_ids.get(row["carrera_nombre"]),
            "materia_id": None,
            "cargo": row["cargo"], "tipo_rol": row["tipo_rol"],
            "es_autoridad": row["es_autoridad"], "vigente": True,
            "fuente_url": row["fuente_url"],
        }
        identity = (payload["persona_id"], payload["facultad_id"],
                    payload["carrera_id"], payload["materia_id"], payload["cargo"])
        current = academic_roles.get(identity)
        # An authority role carries more information than a teaching one.
        if current is None or (payload["es_autoridad"] and not current["es_autoridad"]):
            academic_roles[identity] = payload
    counts["roles_academicos"] = _insert_chunks(
        client, "roles_academicos", list(academic_roles.values())
    )

    # autoridades.facultad_id is NOT NULL, so an institution-wide authority --
    # the Rector, the Vicerrectora -- has no row to go in. They are still kept
    # as academic roles flagged es_autoridad, and counted here.
    counts["autoridades_sin_facultad"] = sum(
        1 for row in data["autoridades"] if not row["facultad_nombre"]
    )
    client.table("autoridades").delete().in_("facultad_id", list(faculty_ids.values())).execute()
    counts["autoridades"] = _insert_chunks(client, "autoridades", [{
        "facultad_id": faculty_ids.get(str(_faculty_name(row["facultad_nombre"]))),
        "carrera_id": career_ids.get(row["carrera"]),
        "cargo": row["cargo"], "tipo": row["tipo"],
        "nombre_autoridad": row["nombre_autoridad"],
    } for row in data["autoridades"] if row["facultad_nombre"]])
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
    untyped = [row["nombre_programa"] for row in dataset["datos"]["posgrados"]
               if not row["tipo_posgrado"]]
    if untyped:
        print("\nSin cargar porque la fuente no publica su tipo y el esquema lo exige:")
        for name in untyped:
            print(f"- {name}")


if __name__ == "__main__":
    main()
