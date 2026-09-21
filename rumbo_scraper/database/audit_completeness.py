"""Create an actionable, read-only data completeness report for UTDT."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path("data/utdt_pendientes.json")
UNIVERSITY = "Universidad Torcuato Di Tella"

RULES = (
    ("carreras", "titulo_otorgado", "alta", "Página y plan oficial de la carrera"),
    ("carreras", "tiene_titulo_intermedio", "media", "Plan oficial y títulos intermedios"),
    ("carreras", "cantidad_materias_total", "media", "Plan de estudios oficial"),
    ("ofertas_academicas", "url_oficial", "alta", "Página oficial de la carrera"),
    ("ofertas_academicas", "regimen_ingreso", "media", "Admisiones y preguntas frecuentes"),
    ("ciclos_ingreso", "fecha_apertura_inscripcion", "alta", "Calendario de Admisiones"),
    ("ciclos_ingreso", "fecha_cierre_inscripcion", "alta", "Calendario de Admisiones"),
    ("ciclos_ingreso", "estado", "alta", "Calendario de Admisiones"),
    ("actividades", "obligatoria", "media", "Plan oficial de la carrera"),
    ("actividades", "carga_horaria_total", "baja", "Plan o reglamento académico"),
    ("actividades", "descripcion_breve", "baja", "Página o plan oficial"),
    ("actividades_extracurriculares", "descripcion", "baja", "Página pública de cada actividad"),
    ("posgrados", "url_oficial", "alta", "Página individual del posgrado"),
    ("posgrados", "facultad_id", "alta", "Página individual del posgrado"),
    ("posgrados", "modalidad", "alta", "Página individual del posgrado"),
    ("posgrados", "duracion_meses", "alta", "Página individual del posgrado"),
    ("posgrados", "descripcion_breve", "alta", "Página individual del posgrado"),
    ("convenios_intercambio", "pais", "alta", "Normalizar ciudad/destino del mapa de intercambio"),
)

EMPTY_TABLES = (
    ("aranceles", "alta", "Página oficial de aranceles con fecha de vigencia"),
    ("correlatividades", "media", "Planes de estudio y reglamentos"),
    ("turnos_anio", "media", "Derivar de horarios del catálogo semestral"),
)


def _data(response: Any) -> list[dict[str, Any]]:
    rows = getattr(response, "data", None)
    if not isinstance(rows, list):
        raise RuntimeError("Supabase devolvió una respuesta sin datos.")
    return rows


def _empty(value: object) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _all_rows(client: Any, table: str, columns: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = _data(client.table(table).select(columns).range(offset, offset + 999).execute())
        result.extend(page)
        if len(page) < 1000:
            return result
        offset += 1000


def build_report(client: Any) -> dict[str, Any]:
    university_rows = _data(
        client.table("universidades").select("id").eq("nombre_oficial", UNIVERSITY).limit(1).execute()
    )
    if not university_rows:
        raise RuntimeError("No existe la Universidad Torcuato Di Tella en Supabase.")
    university_id = university_rows[0]["id"]
    issues: list[dict[str, Any]] = []
    for table, field, priority, source in RULES:
        for row in _all_rows(client, table, f"id,{field}"):
            if _empty(row.get(field)):
                issues.append({
                    "clave": f"{table}:{row['id']}:{field}",
                    "universidad_id": university_id,
                    "entidad_tipo": table,
                    "entidad_id": row["id"],
                    "campo": field,
                    "prioridad": priority,
                    "motivo": "Campo vacío",
                    "accion_recomendada": f"Completar desde: {source}",
                })

    # The semester catalogue stores descriptions, teachers and schedules in its own
    # normalized tables. The actionable gap is a missing plan-to-catalogue link,
    # not a NULL in the legacy materias columns.
    plan_subjects = _all_rows(client, "materias", "id")
    links = _all_rows(client, "materias_catalogo_vinculos", "materia_id")
    linked_subjects = {row["materia_id"] for row in links}
    for subject in plan_subjects:
        if subject["id"] not in linked_subjects:
            issues.append({
                "clave": f"materias:{subject['id']}:vinculo_catalogo",
                "universidad_id": university_id,
                "entidad_tipo": "materias",
                "entidad_id": subject["id"],
                "campo": "vinculo_catalogo",
                "prioridad": "baja",
                "motivo": "Materia del plan no ofrecida o sin coincidencia inequívoca en el catálogo del período",
                "accion_recomendada": "Reintentar con catálogos de otros semestres; revisar manualmente sólo si sigue sin aparecer",
            })

    # Academic enrichment is only actionable when UTDT actually publishes a
    # profile URL. Catalogue-only teachers must not become thousands of false alarms.
    people = _all_rows(client, "personas", "id,perfil_url,formacion,biografia")
    for person in people:
        if not person.get("perfil_url"):
            continue
        for field in ("formacion", "biografia"):
            if _empty(person.get(field)):
                issues.append({
                    "clave": f"personas:{person['id']}:{field}",
                    "universidad_id": university_id,
                    "entidad_tipo": "personas",
                    "entidad_id": person["id"],
                    "campo": field,
                    "prioridad": "baja",
                    "motivo": "Perfil público disponible pero campo todavía vacío",
                    "accion_recomendada": "Completar desde el perfil académico público",
                })
    for table, priority, source in EMPTY_TABLES:
        rows = _all_rows(client, table, "id")
        if not rows:
            issues.append({
                "clave": f"{table}:sin_filas",
                "universidad_id": university_id,
                "entidad_tipo": table,
                "entidad_id": None,
                "campo": None,
                "prioridad": priority,
                "motivo": "Tabla sin registros",
                "accion_recomendada": f"Obtener desde: {source}",
            })
    return {
        "universidad": UNIVERSITY,
        "generado_at": datetime.now(UTC).isoformat(),
        "total_pendientes": len(issues),
        "resumen": {
            priority: sum(issue["prioridad"] == priority for issue in issues)
            for priority in ("alta", "media", "baja")
        },
        "pendientes": issues,
    }


def apply_report(client: Any, report: dict[str, Any]) -> None:
    university_id = report["pendientes"][0]["universidad_id"] if report["pendientes"] else None
    if not university_id:
        return
    current_keys = {issue["clave"] for issue in report["pendientes"]}
    existing = _data(
        client.table("pendientes_datos").select("id,clave")
        .eq("universidad_id", university_id).eq("estado", "pendiente").execute()
    )
    resolved_ids = [row["id"] for row in existing if row["clave"] not in current_keys]
    for start in range(0, len(resolved_ids), 100):
        client.table("pendientes_datos").update({
            "estado": "resuelto", "resuelto_at": datetime.now(UTC).isoformat()
        }).in_("id", resolved_ids[start:start + 100]).execute()
    payloads = [
        {**issue, "estado": "pendiente", "ultima_deteccion_at": report["generado_at"]}
        for issue in report["pendientes"]
    ]
    for start in range(0, len(payloads), 100):
        client.table("pendientes_datos").upsert(
            payloads[start:start + 100], on_conflict="clave"
        ).execute()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audita campos pendientes de UTDT")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--apply", action="store_true", help="Sincroniza pendientes_datos en Supabase")
    args = parser.parse_args()
    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    report = build_report(client)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.apply:
        apply_report(client, report)
    print(f"PENDIENTES: {report['total_pendientes']}")
    for priority, count in report["resumen"].items():
        print(f"- {priority}: {count}")
    print(f"Archivo: {args.output}")


if __name__ == "__main__":
    main()
