"""Validate and load the UTDT JSON export into the normalized Supabase schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.validators.utdt import validate_dataset


DEFAULT_INPUT = Path("data/utdt_completo.json")
SKIPPED_SECTIONS = ("turnos_anio", "aranceles")
LEGACY_POSTGRADUATE_NAMES = {
    "Maestría y": "Maestría en Ciencia Política",
    "Maestría y Doctorado en Estudios Internacionales": "Maestría en Estudios Internacionales",
    "Maestría y Especialización en Derecho Penal": "Maestría en Derecho Penal",
    "MBA | Executive MBA (Maestría en Dirección de Empresas": "MBA (Maestría en Dirección de Empresas)",
}


def _boolean(value: object) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"si", "sí", "true", "1"}:
        return True
    if normalized in {"no", "false", "0"}:
        return False
    raise ValueError(f"Valor booleano no reconocido: {value!r}")


def load_file(path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    # Backward-compatible with exports created before postgraduate URLs were
    # added to the contract. A fresh scrape always supplies this value.
    for row in dataset.get("datos", {}).get("posgrados", []):
        row.setdefault("url_oficial", None)
    for row in dataset.get("datos", {}).get("ofertas", []):
        row.setdefault("url_oficial", None)
    validate_dataset(dataset)
    return dataset


def preview(dataset: dict[str, Any]) -> dict[str, int]:
    """Return the records that are eligible for loading, without connecting."""
    data = dataset["datos"]
    return {
        section: len(records)
        for section, records in data.items()
        if section not in SKIPPED_SECTIONS
    }


def _data(response: Any) -> list[dict[str, Any]]:
    rows = getattr(response, "data", None)
    if not isinstance(rows, list):
        raise RuntimeError("Supabase devolvió una respuesta sin datos.")
    return rows


def _upsert_one(client: Any, table: str, row: dict[str, Any], conflict: str) -> dict[str, Any]:
    rows = _data(client.table(table).upsert(row, on_conflict=conflict).execute())
    if not rows:
        raise RuntimeError(f"Supabase no devolvió la fila de {table}.")
    return rows[0]


def _insert_chunks(client: Any, table: str, rows: list[dict[str, Any]], size: int = 100) -> int:
    for start in range(0, len(rows), size):
        _data(client.table(table).insert(rows[start:start + size]).execute())
    return len(rows)


def _upsert_chunks(
    client: Any, table: str, rows: list[dict[str, Any]], conflict: str, size: int = 100
) -> list[dict[str, Any]]:
    saved: list[dict[str, Any]] = []
    for start in range(0, len(rows), size):
        saved.extend(_data(
            client.table(table).upsert(
                rows[start:start + size], on_conflict=conflict
            ).execute()
        ))
    return saved


def _subject_identity(row: dict[str, Any]) -> tuple[str, str, str]:
    """Stable identity that preserves a plan subject's database ID across loads."""
    parent = row.get("carrera_id") or f"posgrado:{row.get('posgrado_id') or ''}"
    year = "" if row.get("anio_cursada") is None else str(row["anio_cursada"])
    return str(parent), comparison_key(row.get("nombre_materia")), year


def _sync_subjects(
    client: Any, university_id: str, rows: list[dict[str, Any]]
) -> int:
    """Synchronize subjects in batches while preserving catalogue-linked IDs."""
    existing = _data(
        client.table("materias")
        .select("id,carrera_id,posgrado_id,nombre_materia,anio_cursada")
        .eq("universidad_id", university_id).execute()
    )
    available: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in existing:
        available.setdefault(_subject_identity(row), []).append(row)

    kept_ids: set[str] = set()
    updates: list[dict[str, Any]] = []
    inserts: list[dict[str, Any]] = []
    for row in rows:
        matches = available.get(_subject_identity(row), [])
        if matches:
            current = matches.pop(0)
            kept_ids.add(current["id"])
            updates.append({"id": current["id"], **row})
        else:
            inserts.append(row)

    # Hundreds of one-row HTTP requests caused timeouts once postgraduate
    # curricula were added. Chunked writes keep the same stable IDs and make a
    # full rerun idempotent after an interrupted load.
    _upsert_chunks(client, "materias", updates, "id")
    _insert_chunks(client, "materias", inserts)

    stale_ids = [row["id"] for row in existing if row["id"] not in kept_ids]
    for start in range(0, len(stale_ids), 100):
        client.table("materias").delete().in_("id", stale_ids[start:start + 100]).execute()
    return len(rows)


def _faculty_name(reference: object) -> str | None:
    if not reference:
        return None
    text = str(reference)
    for marker in (" — Escuela de ", " — Departamento de ", " — Centro de "):
        if marker in text:
            return text.split(marker, 1)[1]
    return text


def _program_name_key(value: object) -> str:
    text = str(value or "")
    text = text.split("(", 1)[0].strip()
    key = comparison_key(text)
    aliases = {
        "licenciatura en administracion en empresas": "licenciatura en administracion de empresas",
        "licenciatura en adminstracion de empresas": "licenciatura en administracion de empresas",
        "licenciatura economia empresarial": "licenciatura en economia empresarial",
        "licenciatura en ciencia politica": "licenciatura en ciencia politica y gobierno",
        "licenciatura de ciencia politica y gobierno": "licenciatura en ciencia politica y gobierno",
    }
    return aliases.get(key, key)


def apply_dataset(dataset: dict[str, Any], client: Any | None = None) -> dict[str, int]:
    """Upsert stable entities and replace UTDT-owned detail rows."""
    validate_dataset(dataset)
    data = dataset["datos"]
    if client is None:
        # Import lazily: preview mode never loads .env or initializes Supabase.
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
        payload = {
            "universidad_id": university_id,
            "nombre_sede": row["nombre_sede"],
            "localidad_id": locality_ids.get(str(row["localidad"])),
            "calle": row["calle"],
            "numero": row["numero"],
            "tipo_sede": row["tipo_sede"],
        }
        saved = _upsert_one(client, "sedes", payload, "universidad_id,nombre_sede")
        campus_ids[row["nombre_sede"]] = saved["id"]
    counts["sedes"] = len(campus_ids)
    default_campus_id = next(iter(campus_ids.values()))

    faculty_ids: dict[str, str] = {}
    for row in data["facultades"]:
        payload = {
            "universidad_id": university_id,
            "nombre_facultad": row["nombre_facultad"],
            "tipo_unidad": row["tipo_unidad"],
        }
        saved = _upsert_one(
            client, "facultades", payload,
            "universidad_id,nombre_facultad,tipo_unidad",
        )
        faculty_ids[row["nombre_facultad"]] = saved["id"]
        _upsert_one(
            client, "facultades_sedes",
            {"facultad_id": saved["id"], "sede_id": default_campus_id, "es_sede_principal": True},
            "facultad_id,sede_id",
        )
    counts["facultades"] = len(faculty_ids)

    career_ids: dict[str, str] = {}
    for row in data["carreras"]:
        payload = {
            "universidad_id": university_id,
            "facultad_id": faculty_ids.get(_faculty_name(row["facultad_nombre"])),
            "nombre_carrera": row["nombre_carrera"],
            "denominacion_canonica": row["denominacion_canonica"],
            "nivel": row["nivel"],
            "titulo_otorgado": row["titulo_otorgado"],
            "tiene_titulo_intermedio": _boolean(row["tiene_titulo_intermedio"]),
            "duracion_anios": row["duracion_anios"],
            "descripcion_breve": row["descripcion_breve"],
            "cantidad_materias_total": row["cantidad_materias_total"],
        }
        saved = _upsert_one(client, "carreras", payload, "universidad_id,nombre_carrera")
        career_ids[row["nombre_carrera"]] = saved["id"]
    counts["carreras"] = len(career_ids)

    offer_ids: dict[str, str] = {}
    for row in data["ofertas"]:
        payload = {
            "carrera_id": career_ids[row["carrera_nombre"]],
            "sede_id": default_campus_id,
            "modalidad": row["modalidad"],
            "regimen_ingreso": row["regimen_ingreso"],
            "coneau_resolucion": row["coneau_resolucion"],
            "coneau_vigencia_hasta": row["coneau_vigencia_hasta"],
            "tiene_pasantias": _boolean(row["tiene_pasantias"]),
            "tiene_bolsa_trabajo": _boolean(row["tiene_bolsa_trabajo"]),
            "url_oficial": row["url_oficial"],
            "activa": True,
        }
        saved = _upsert_one(
            client, "ofertas_academicas", payload, "carrera_id,sede_id,modalidad"
        )
        offer_ids[row["carrera_nombre"]] = saved["id"]
    counts["ofertas"] = len(offer_ids)

    for row in data["ofertas_ciclo"]:
        payload = {
            "oferta_id": offer_ids[row["carrera_nombre"]],
            "ciclo_anio": row["ciclo_anio"],
            "ciclo_nombre": row["ciclo_nombre"],
            "cupo_ingresantes": row["cupo_ingresantes"],
            "fecha_apertura_inscripcion": row["fecha_apertura_inscripcion"],
            "fecha_cierre_inscripcion": row["fecha_cierre_inscripcion"],
            "estado": row["estado"],
        }
        _upsert_one(client, "ciclos_ingreso", payload, "oferta_id,ciclo_anio,ciclo_nombre")
    counts["ofertas_ciclo"] = len(data["ofertas_ciclo"])

    area_names = sorted({row["area_tematica"] for row in data["materias"] if row["area_tematica"]})
    area_ids: dict[str, str] = {}
    for name in area_names:
        saved = _upsert_one(client, "areas_tematicas", {"nombre": name}, "nombre")
        area_ids[name] = saved["id"]
    counts["areas_tematicas"] = len(area_ids)

    posgrad_ids: dict[str, str] = {}
    existing_posgrads = _data(
        client.table("posgrados").select("id,nombre_programa")
        .eq("universidad_id", university_id).execute()
    )
    existing_names = {row["nombre_programa"] for row in existing_posgrads}
    for old_name, new_name in LEGACY_POSTGRADUATE_NAMES.items():
        if old_name in existing_names and new_name not in existing_names:
            client.table("posgrados").update({"nombre_programa": new_name}) \
                .eq("universidad_id", university_id).eq("nombre_programa", old_name).execute()
            existing_names.remove(old_name)
            existing_names.add(new_name)
    for row in data["posgrados"]:
        payload = {
            "universidad_id": university_id,
            "facultad_id": faculty_ids.get(_faculty_name(row["facultad_nombre"])),
            "nombre_programa": row["nombre_programa"],
            "tipo_posgrado": row["tipo_posgrado"],
            "titulo_otorgado": row["titulo_otorgado"],
            "sede_id": default_campus_id,
            "modalidad": row["modalidad"],
            "duracion_meses": row["duracion_meses"],
            "requiere_tesis_trabajo_final": _boolean(row["requiere_tesis_trabajo_final"]),
            "requisito_titulo_previo": row["requisito_titulo_previo"],
            "cohorte_inicio": row["cohorte_inicio"],
            "costo_total_programa": row["costo_total_programa"],
            "moneda": row["moneda"],
            "descripcion_breve": row["descripcion_breve"],
            "url_oficial": row["url_oficial"],
        }
        saved = _upsert_one(client, "posgrados", payload, "universidad_id,nombre_programa")
        posgrad_ids[row["nombre_programa"]] = saved["id"]
    counts["posgrados"] = len(posgrad_ids)

    # These detail tables lack natural unique constraints in the current schema.
    # Subjects are synchronized separately to preserve catalogue relationships.
    for table in ("actividades", "contactos"):
        client.table(table).delete().eq("universidad_id", university_id).execute()
    if faculty_ids:
        client.table("autoridades").delete().in_("facultad_id", list(faculty_ids.values())).execute()

    subjects = [{
        "universidad_id": university_id,
        "carrera_id": career_ids.get(row["carrera_o_programa"]),
        "posgrado_id": posgrad_ids.get(row["carrera_o_programa"]),
        "nombre_materia": row["nombre_materia"],
        "anio_cursada": row["anio_cursada"],
        "turno": row["turno"],
        "area_tematica_id": area_ids.get(row["area_tematica"]),
        "descripcion_breve": row["descripcion_breve"],
        "regimen": row["regimen"],
        "carga_horaria_semanal": row["carga_horaria_semanal"],
    } for row in data["materias"]]
    counts["materias"] = _sync_subjects(client, university_id, subjects)

    activities = [{
        "universidad_id": university_id,
        "carrera_id": career_ids.get(row["carrera_o_programa"]),
        "posgrado_id": posgrad_ids.get(row["carrera_o_programa"]),
        "tipo_actividad": row["tipo_actividad"],
        "nombre_actividad": row["nombre_actividad"],
        "obligatoria": _boolean(row["obligatoria"]),
        "carga_horaria_total": row["carga_horaria_total"],
        "descripcion_breve": row["descripcion_breve"],
    } for row in data["actividades"]]
    counts["actividades"] = _insert_chunks(client, "actividades", activities)

    authorities = [{
        "facultad_id": faculty_ids[_faculty_name(row["facultad_nombre"])],
        "carrera_id": career_ids.get(row["carrera"]),
        "cargo": row["cargo"], "tipo": row["tipo"],
        "nombre_autoridad": row["nombre_autoridad"],
    } for row in data["autoridades"]]
    counts["autoridades"] = _insert_chunks(client, "autoridades", authorities)

    contacts = [{
        "universidad_id": university_id,
        "facultad_id": faculty_ids.get(_faculty_name(row["facultad_nombre"])),
        "carrera_id": None,
        "canal": row["canal"],
        "usuario_o_direccion": row["usuario_o_direccion"],
    } for row in data["redes_contacto"]]
    counts["redes_contacto"] = _insert_chunks(client, "contactos", contacts)

    for table in (
        "becas", "servicios_estudiantiles", "actividades_extracurriculares",
        "alojamientos", "programas_internacionales", "convenios_intercambio",
    ):
        client.table(table).delete().eq("universidad_id", university_id).execute()

    scholarships = [{
        "universidad_id": university_id,
        "nombre_beca": row["nombre_beca"], "nivel": row["nivel"],
        "tipo_beca": row["tipo_beca"],
        "cobertura_descripcion": row["cobertura_descripcion"],
        "porcentaje_maximo": row["porcentaje_maximo"],
        "requisitos": row["requisitos"],
        "proceso_postulacion": row["proceso_postulacion"],
        "renovacion": row["renovacion"], "fecha_cierre": row["fecha_cierre"],
        "url_postulacion": row["url_postulacion"], "contacto": row["contacto"],
        "fuente_url": row["fuente_url"],
    } for row in data["becas"]]
    counts["becas"] = _insert_chunks(client, "becas", scholarships)

    services = [{
        "universidad_id": university_id, "sede_id": default_campus_id,
        "categoria": row["categoria"], "nombre_servicio": row["nombre_servicio"],
        "descripcion": row["descripcion"], "contacto": row["contacto"],
        "url": row["url"], "fuente_url": row["fuente_url"],
    } for row in data["servicios_estudiantiles"]]
    counts["servicios_estudiantiles"] = _insert_chunks(
        client, "servicios_estudiantiles", services
    )

    extracurricular = [{
        "universidad_id": university_id, "sede_id": default_campus_id,
        "categoria": row["categoria"],
        "nombre_actividad": row["nombre_actividad"],
        "descripcion": row["descripcion"], "contacto": row["contacto"],
        "url": row["url"], "fuente_url": row["fuente_url"],
    } for row in data["actividades_extracurriculares"]]
    counts["actividades_extracurriculares"] = _insert_chunks(
        client, "actividades_extracurriculares", extracurricular
    )

    housing = [{
        "universidad_id": university_id, "sede_id": default_campus_id,
        "tipo_apoyo": row["tipo_apoyo"],
        "tipo_alojamiento": row["tipo_alojamiento"],
        "residencia_propia": _boolean(row["residencia_propia"]),
        "descripcion": row["descripcion"], "contacto": row["contacto"],
        "url": row["url"], "fuente_url": row["fuente_url"],
    } for row in data["alojamiento"]]
    counts["alojamiento"] = _insert_chunks(client, "alojamientos", housing)

    international = [{
        "universidad_id": university_id, "nivel": row["nivel"],
        "tipo_programa": row["tipo_programa"],
        "nombre_programa": row["nombre_programa"],
        "cantidad_convenios": row["cantidad_convenios"],
        "duracion_maxima": row["duracion_maxima"],
        "reconocimiento_academico": _boolean(row["reconocimiento_academico"]),
        "arancel_destino_cubierto": _boolean(row["arancel_destino_cubierto"]),
        "requisitos": row["requisitos"], "url": row["url"],
        "fuente_url": row["fuente_url"],
    } for row in data["programas_internacionales"]]
    counts["programas_internacionales"] = _insert_chunks(
        client, "programas_internacionales", international
    )

    career_lookup: dict[str, str] = {}
    for row in data["carreras"]:
        career_id = career_ids[row["nombre_carrera"]]
        career_lookup[_program_name_key(row["nombre_carrera"])] = career_id
        career_lookup[_program_name_key(row["denominacion_canonica"])] = career_id
    posgrad_lookup = {
        _program_name_key(name): posgrad_id for name, posgrad_id in posgrad_ids.items()
    }
    exchange_agreements = [{
        "universidad_id": university_id,
        "carrera_id": career_lookup.get(_program_name_key(row["programa_origen"])),
        "posgrado_id": posgrad_lookup.get(_program_name_key(row["programa_origen"])),
        "programa_origen": row["programa_origen"],
        "universidad_destino": row["universidad_destino"],
        "ciudad": row["ciudad"], "pais": row["pais"],
        "latitud": row["latitud"], "longitud": row["longitud"],
        "observaciones": row["observaciones"], "fuente_url": row["fuente_url"],
    } for row in data["convenios_intercambio"]]
    counts["convenios_intercambio"] = _insert_chunks(
        client, "convenios_intercambio", exchange_agreements
    )

    directory = dataset.get("directorio_academico", {})
    person_payloads = [
        {
            "universidad_id": university_id,
            "nombre_completo": row["nombre_completo"], "email": row["email"],
            "perfil_url": row["perfil_url"], "formacion": row["formacion"],
            "biografia": row["biografia"], "fuente_url": row["fuente_url"],
            "activa": True,
        }
        for row in directory.get("personas", [])
    ]
    saved_people = _upsert_chunks(
        client, "personas", person_payloads, "universidad_id,nombre_completo"
    )
    person_ids = {
        comparison_key(row["nombre_completo"]): row["id"] for row in saved_people
    }
    counts["personas"] = len(person_ids)
    client.table("roles_academicos").delete().eq("universidad_id", university_id).execute()
    academic_roles = [{
        "persona_id": person_ids[comparison_key(row["nombre_completo"])],
        "universidad_id": university_id,
        "facultad_id": faculty_ids.get(_faculty_name(row["facultad_nombre"])),
        "carrera_id": career_ids.get(row["carrera_nombre"]),
        "materia_id": None,
        "cargo": row["cargo"], "tipo_rol": row["tipo_rol"],
        "es_autoridad": row["es_autoridad"], "vigente": True,
        "fuente_url": row["fuente_url"],
    } for row in directory.get("roles_academicos", [])]
    counts["roles_academicos"] = _insert_chunks(
        client, "roles_academicos", academic_roles
    )
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga validada de UTDT a Supabase")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--apply", action="store_true",
        help="Escribe en Supabase. Sin esta opción sólo valida y muestra un resumen.",
    )
    args = parser.parse_args()
    dataset = load_file(args.input)
    counts = apply_dataset(dataset) if args.apply else preview(dataset)
    mode = "CARGADO" if args.apply else "VALIDADO (sin escribir)"
    print(mode)
    for section, count in counts.items():
        print(f"- {section}: {count}")
    print("- turnos_anio: omitido")
    print("- aranceles: omitido")


if __name__ == "__main__":
    main()
