"""Load a scraped UTDT semester catalogue into the normalized Supabase schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from rumbo_scraper.database.supabase import select_all
from rumbo_scraper.normalizers.text import clean_text, comparison_key


DEFAULT_INPUT = Path("data/utdt_catalogo_cursos.json")
UNIVERSITY = "Universidad Torcuato Di Tella"


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


def _upsert_chunks(
    client: Any, table: str, rows: list[dict[str, Any]], conflict: str, size: int = 100
) -> list[dict[str, Any]]:
    saved: list[dict[str, Any]] = []
    for chunk in _chunks(rows, size):
        saved.extend(_data(client.table(table).upsert(
            chunk, on_conflict=conflict
        ).execute()))
    return saved


def _chunks(values: list[Any], size: int = 100) -> list[list[Any]]:
    return [values[index:index + size] for index in range(0, len(values), size)]


def _teacher_name(value: str) -> str:
    parts = [clean_text(part) for part in value.split(",", 1)]
    if len(parts) == 2:
        return f"{parts[1]} {parts[0]}"
    return clean_text(value)


def _subject_name_key(value: str) -> str:
    """Normalize harmless plan annotations without confusing numbered subjects."""
    return comparison_key(re.sub(r"\s*\*+\s*$", "", value))


def _equivalent_subject_key(value: str) -> str:
    """Normalize only wording differences that preserve the exact subject meaning."""
    key = _subject_name_key(value)
    key = re.sub(r"^seminario\s*:\s*", "", key)
    key = key.replace("segunda parte", "parte ii").replace("primera parte", "parte i")
    key = re.sub(r"\s*\(proyecto final\)\s*$", "", key)
    return key.replace(" en la argentina", " en argentina")


def _commission_key(code: object, section: object) -> tuple[str, str]:
    return clean_text(str(code or "")), clean_text(str(section or "")) or "0"


def _shift_for_time(value: object) -> str | None:
    """Classify a published class start time into the database shift enum."""
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", clean_text(str(value or "")))
    if not match:
        return None
    minutes = int(match.group(1)) * 60 + int(match.group(2))
    if minutes < 13 * 60:
        return "Mañana"
    if minutes < 18 * 60:
        return "Tarde"
    return "Noche"


def load_file(path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    if not dataset.get("horarios") and not dataset.get("detalles"):
        raise ValueError("El catálogo no contiene horarios ni detalles.")
    period = dataset.get("periodo", {})
    if not period.get("anio") or period.get("semestre") not in {1, 2}:
        raise ValueError("El catálogo no tiene un período válido.")
    return dataset


def preview(dataset: dict[str, Any]) -> dict[str, int]:
    keys = {
        _commission_key(row.get("codigo_materia"), row.get("seccion"))
        for section in ("horarios", "detalles") for row in dataset.get(section, [])
        if row.get("codigo_materia")
    }
    courses = {code for code, _ in keys}
    teachers = {
        _teacher_name(name)
        for row in dataset.get("horarios", []) for name in row.get("docentes", [])
    }
    schedules = {
        (*_commission_key(row.get("codigo_materia"), row.get("seccion")), row.get("tipo_clase"),
         row.get("dia"), row.get("hora_inicio"), row.get("hora_fin"))
        for row in dataset.get("horarios", []) if row.get("codigo_materia")
    }
    return {
        "materias_catalogo": len(courses),
        "comisiones_materia": len(keys),
        "horarios_comision": len(schedules),
        "docentes": len(teachers),
    }


def apply_dataset(dataset: dict[str, Any], client: Any | None = None) -> dict[str, int]:
    if client is None:
        from rumbo_scraper.database.supabase import get_supabase_client
        client = get_supabase_client()
    period = dataset["periodo"]
    source_url = dataset.get("fuente_url")
    university_rows = _data(
        client.table("universidades").select("id").eq("nombre_oficial", UNIVERSITY).limit(1).execute()
    )
    if not university_rows:
        raise RuntimeError("No existe la Universidad Torcuato Di Tella en Supabase.")
    university_id = university_rows[0]["id"]

    all_rows = dataset.get("horarios", []) + dataset.get("detalles", [])
    names_by_code: dict[str, str] = {}
    for row in all_rows:
        code = clean_text(str(row.get("codigo_materia") or ""))
        if code:
            names_by_code.setdefault(code, clean_text(str(row.get("nombre_materia") or code)))

    course_payloads = [
        {"universidad_id": university_id, "codigo": code, "nombre": name,
         "fuente_url": source_url, "activa": True}
        for code, name in names_by_code.items()
    ]
    saved_courses = _upsert_chunks(
        client, "materias_catalogo", course_payloads, "universidad_id,codigo"
    )
    course_ids = {row["codigo"]: row["id"] for row in saved_courses}

    catalog_by_name: dict[str, list[str]] = {}
    catalog_by_equivalent_name: dict[str, list[str]] = {}
    for code, name in names_by_code.items():
        catalog_by_name.setdefault(_subject_name_key(name), []).append(course_ids[code])
        catalog_by_equivalent_name.setdefault(
            _equivalent_subject_key(name), []
        ).append(course_ids[code])
    plan_subjects = select_all(
        client.table("materias").select("id,carrera_id,nombre_materia,anio_cursada")
        .eq("universidad_id", university_id)
    )
    subject_links: list[dict[str, Any]] = []
    for subject in plan_subjects:
        matches = catalog_by_name.get(_subject_name_key(subject["nombre_materia"]), [])
        method = "nombre_exacto"
        confidence = 1
        if len(matches) != 1:
            matches = catalog_by_equivalent_name.get(
                _equivalent_subject_key(subject["nombre_materia"]), []
            )
            method = "nombre_equivalente"
            confidence = 0.99
        if len(matches) == 1:
            subject_links.append({
                "materia_id": subject["id"], "materia_catalogo_id": matches[0],
                "metodo": method, "confianza": confidence,
            })
    for chunk in _chunks(subject_links):
        _data(client.table("materias_catalogo_vinculos").upsert(
            chunk, on_conflict="materia_id,materia_catalogo_id"
        ).execute())

    offers = _data(
        client.table("ofertas_academicas").select("id,carrera_id")
        .in_("carrera_id", list({
            row["carrera_id"] for row in plan_subjects if row.get("carrera_id")
        })).execute()
    )
    offer_by_career = {row["carrera_id"]: row["id"] for row in offers}
    subject_by_id = {row["id"]: row for row in plan_subjects}
    subjects_by_catalog: dict[str, list[dict[str, Any]]] = {}
    for link in subject_links:
        subjects_by_catalog.setdefault(link["materia_catalogo_id"], []).append(
            subject_by_id[link["materia_id"]]
        )

    existing_commissions: list[str] = []
    for course_id_chunk in _chunks(list(course_ids.values())):
        rows = select_all(
            client.table("comisiones_materia").select("id")
            .in_("materia_catalogo_id", course_id_chunk)
            .eq("anio", period["anio"]).eq("semestre", period["semestre"])
        )
        existing_commissions.extend(row["id"] for row in rows)
    for id_chunk in _chunks(existing_commissions):
        client.table("docentes_comision").delete().in_("comision_id", id_chunk).execute()
        client.table("horarios_comision").delete().in_("comision_id", id_chunk).execute()
        client.table("comisiones_materia").delete().in_("id", id_chunk).execute()

    details: dict[tuple[str, str], dict[str, Any]] = {}
    for row in dataset.get("detalles", []):
        key = _commission_key(row.get("codigo_materia"), row.get("seccion"))
        if not key[0]:
            continue
        current = details.setdefault(key, {})
        for field in ("contenido", "condiciones_aprobacion", "programa_url"):
            if row.get(field) and not current.get(field):
                current[field] = row[field]

    commission_keys = {
        _commission_key(row.get("codigo_materia"), row.get("seccion"))
        for row in all_rows if row.get("codigo_materia")
    }
    commission_payloads: list[dict[str, Any]] = []
    for code, section in sorted(commission_keys):
        detail = details.get((code, section), {})
        commission_payloads.append(
            {"materia_catalogo_id": course_ids[code], "anio": period["anio"],
             "semestre": period["semestre"], "seccion": section,
             "contenido": detail.get("contenido"),
             "condiciones_aprobacion": detail.get("condiciones_aprobacion"),
             "programa_url": detail.get("programa_url"), "fuente_url": source_url}
        )
    saved_commissions = _upsert_chunks(
        client, "comisiones_materia", commission_payloads,
        "materia_catalogo_id,anio,semestre,seccion",
    )
    code_by_course_id = {course_id: code for code, course_id in course_ids.items()}
    commission_ids = {
        (code_by_course_id[row["materia_catalogo_id"]], str(row["seccion"])): row["id"]
        for row in saved_commissions
    }

    schedules: dict[tuple[Any, ...], dict[str, Any]] = {}
    teacher_assignments: set[tuple[str, str, str | None]] = set()
    for row in dataset.get("horarios", []):
        key = _commission_key(row.get("codigo_materia"), row.get("seccion"))
        commission_id = commission_ids.get(key)
        if not commission_id:
            continue
        schedule_key = (
            commission_id, row.get("tipo_clase"), row.get("dia"),
            row.get("hora_inicio"), row.get("hora_fin"),
        )
        schedules[schedule_key] = {
            "comision_id": commission_id, "tipo_clase": row.get("tipo_clase"),
            "dia": row.get("dia"), "hora_inicio": row.get("hora_inicio"),
            "hora_fin": row.get("hora_fin"),
        }
        for teacher in row.get("docentes", []):
            teacher_assignments.add((commission_id, teacher, row.get("tipo_clase")))
    for chunk in _chunks(list(schedules.values())):
        _data(client.table("horarios_comision").insert(chunk).execute())

    shifts: set[tuple[str, int, str]] = set()
    for row in dataset.get("horarios", []):
        code = clean_text(str(row.get("codigo_materia") or ""))
        catalog_id = course_ids.get(code)
        shift = _shift_for_time(row.get("hora_inicio"))
        if not catalog_id or not shift:
            continue
        for subject in subjects_by_catalog.get(catalog_id, []):
            offer_id = offer_by_career.get(subject.get("carrera_id"))
            year = subject.get("anio_cursada")
            if offer_id and isinstance(year, int):
                shifts.add((offer_id, year, shift))
    offer_ids = list(offer_by_career.values())
    for chunk in _chunks(offer_ids):
        client.table("turnos_anio").delete().in_("oferta_id", chunk).execute()
    shift_rows = [
        {"oferta_id": offer_id, "anio_carrera": year, "turno": shift}
        for offer_id, year, shift in sorted(shifts)
    ]
    for chunk in _chunks(shift_rows):
        _data(client.table("turnos_anio").insert(chunk).execute())

    # UdeSA and UTDT both hold more than a thousand people, so this read has to
    # be paginated or the loader creates a second copy of everyone past the cap.
    people = select_all(
        client.table("personas").select("id,nombre_completo")
        .eq("universidad_id", university_id)
    )
    person_ids = {comparison_key(row["nombre_completo"]): row["id"] for row in people}
    missing_people: dict[str, str] = {}
    for _, source_name, _ in teacher_assignments:
        canonical = _teacher_name(source_name)
        key = comparison_key(canonical)
        if key not in person_ids:
            missing_people[key] = canonical
    new_people_payloads = [
        {"universidad_id": university_id, "nombre_completo": canonical,
         "fuente_url": source_url, "activa": True}
        for canonical in missing_people.values()
    ]
    if new_people_payloads:
        saved_people = _upsert_chunks(
            client, "personas", new_people_payloads, "universidad_id,nombre_completo"
        )
        person_ids.update({
            comparison_key(row["nombre_completo"]): row["id"] for row in saved_people
        })

    teacher_rows: list[dict[str, Any]] = []
    for commission_id, source_name, class_type in sorted(
        teacher_assignments, key=lambda item: (item[0], item[1], item[2] or "")
    ):
        canonical = _teacher_name(source_name)
        key = comparison_key(canonical)
        teacher_rows.append({
            "comision_id": commission_id, "persona_id": person_ids[key],
            "nombre_docente_fuente": source_name, "tipo_clase": class_type,
        })
    for chunk in _chunks(teacher_rows):
        _data(client.table("docentes_comision").insert(chunk).execute())

    return {
        "materias_catalogo": len(course_ids),
        "materias_plan_vinculadas": len(subject_links),
        "comisiones_materia": len(commission_ids),
        "horarios_comision": len(schedules),
        "docentes_comision": len(teacher_rows),
        "turnos_anio": len(shift_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga el catálogo semestral UTDT en Supabase")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    dataset = load_file(args.input)
    counts = apply_dataset(dataset) if args.apply else preview(dataset)
    print("CARGADO" if args.apply else "VALIDADO (sin escribir)")
    for name, count in counts.items():
        print(f"- {name}: {count}")


if __name__ == "__main__":
    main()
