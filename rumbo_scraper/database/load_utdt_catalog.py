"""Load a scraped UTDT semester catalogue into the normalized Supabase schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

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


def _chunks(values: list[Any], size: int = 100) -> list[list[Any]]:
    return [values[index:index + size] for index in range(0, len(values), size)]


def _teacher_name(value: str) -> str:
    parts = [clean_text(part) for part in value.split(",", 1)]
    if len(parts) == 2:
        return f"{parts[1]} {parts[0]}"
    return clean_text(value)


def _commission_key(code: object, section: object) -> tuple[str, str]:
    return clean_text(str(code or "")), clean_text(str(section or "")) or "0"


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

    course_ids: dict[str, str] = {}
    for code, name in names_by_code.items():
        saved = _upsert_one(
            client, "materias_catalogo",
            {"universidad_id": university_id, "codigo": code, "nombre": name,
             "fuente_url": source_url, "activa": True},
            "universidad_id,codigo",
        )
        course_ids[code] = saved["id"]

    catalog_by_name: dict[str, list[str]] = {}
    for code, name in names_by_code.items():
        catalog_by_name.setdefault(comparison_key(name), []).append(course_ids[code])
    plan_subjects = _data(
        client.table("materias").select("id,nombre_materia")
        .eq("universidad_id", university_id).execute()
    )
    subject_links: list[dict[str, Any]] = []
    for subject in plan_subjects:
        matches = catalog_by_name.get(comparison_key(subject["nombre_materia"]), [])
        if len(matches) == 1:
            subject_links.append({
                "materia_id": subject["id"], "materia_catalogo_id": matches[0],
                "metodo": "nombre_exacto", "confianza": 1,
            })
    for chunk in _chunks(subject_links):
        _data(client.table("materias_catalogo_vinculos").upsert(
            chunk, on_conflict="materia_id,materia_catalogo_id"
        ).execute())

    existing_commissions: list[str] = []
    for course_id_chunk in _chunks(list(course_ids.values())):
        rows = _data(
            client.table("comisiones_materia").select("id")
            .in_("materia_catalogo_id", course_id_chunk)
            .eq("anio", period["anio"]).eq("semestre", period["semestre"]).execute()
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
    commission_ids: dict[tuple[str, str], str] = {}
    for code, section in sorted(commission_keys):
        detail = details.get((code, section), {})
        saved = _upsert_one(
            client, "comisiones_materia",
            {"materia_catalogo_id": course_ids[code], "anio": period["anio"],
             "semestre": period["semestre"], "seccion": section,
             "contenido": detail.get("contenido"),
             "condiciones_aprobacion": detail.get("condiciones_aprobacion"),
             "programa_url": detail.get("programa_url"), "fuente_url": source_url},
            "materia_catalogo_id,anio,semestre,seccion",
        )
        commission_ids[(code, section)] = saved["id"]

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

    people = _data(
        client.table("personas").select("id,nombre_completo")
        .eq("universidad_id", university_id).execute()
    )
    person_ids = {comparison_key(row["nombre_completo"]): row["id"] for row in people}
    teacher_rows: list[dict[str, Any]] = []
    for commission_id, source_name, class_type in sorted(
        teacher_assignments, key=lambda item: (item[0], item[1], item[2] or "")
    ):
        canonical = _teacher_name(source_name)
        key = comparison_key(canonical)
        if key not in person_ids:
            saved = _upsert_one(
                client, "personas",
                {"universidad_id": university_id, "nombre_completo": canonical,
                 "fuente_url": source_url, "activa": True},
                "universidad_id,nombre_completo",
            )
            person_ids[key] = saved["id"]
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
