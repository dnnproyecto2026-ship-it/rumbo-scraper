"""Create an actionable, read-only completeness report for one university.

The report separates two things that look alike in a database and are not the
same: a field that is empty and could be filled from a public page, and a field
that is empty because the university does not publish it. The second kind is
declared by each adapter in its own artifact and is reported apart, so the
backlog stays the list of work that can actually be done.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from rumbo_scraper.database.supabase import select_all

DEFAULT_UNIVERSITY = "Universidad Torcuato Di Tella"

# Where each artifact lives, so the audit can read what its adapter declared as
# unpublished. A university without an artifact is still audited.
ARTIFACTS = {
    "Universidad Torcuato Di Tella": Path("data/utdt_completo.json"),
    "Universidad de San Andrés": Path("data/udesa_completo.json"),
    "Instituto Tecnológico de Buenos Aires": Path("data/itba_completo.json"),
    "Universidad Austral": Path("data/austral_completo.json"),
}

# How each table is scoped to a university: directly, or through the row that
# does carry the key.
DIRECT = "universidad_id"
SCOPES: dict[str, tuple[str, str]] = {
    "carreras": (DIRECT, ""),
    "posgrados": (DIRECT, ""),
    "materias": (DIRECT, ""),
    "personas": (DIRECT, ""),
    "actividades": (DIRECT, ""),
    "actividades_extracurriculares": (DIRECT, ""),
    "convenios_intercambio": (DIRECT, ""),
    "becas": (DIRECT, ""),
    "servicios_estudiantiles": (DIRECT, ""),
    "programas_internacionales": (DIRECT, ""),
    "ofertas_academicas": ("carrera_id", "carreras"),
    "ciclos_ingreso": ("oferta_id", "ofertas_academicas"),
    "turnos_anio": ("oferta_id", "ofertas_academicas"),
}

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
    ("posgrados", "titulo_otorgado", "alta", "Plan o resolución oficial del posgrado"),
    ("posgrados", "modalidad", "alta", "Página individual del posgrado"),
    ("posgrados", "duracion_meses", "alta", "Página individual del posgrado"),
    ("posgrados", "descripcion_breve", "alta", "Página individual del posgrado"),
    ("posgrados", "requiere_tesis_trabajo_final", "media", "Plan o reglamento oficial del posgrado"),
    ("posgrados", "requisito_titulo_previo", "media", "Página de admisión del posgrado"),
    ("materias", "anio_cursada", "media", "Plan de estudios oficial"),
    ("convenios_intercambio", "pais", "alta", "Normalizar ciudad/destino del mapa de intercambio"),
    ("becas", "fecha_cierre", "media", "Convocatoria vigente de la beca"),
    ("servicios_estudiantiles", "contacto", "baja", "Página individual del servicio"),
)

EMPTY_TABLES = (
    ("aranceles", "alta", "Página oficial de aranceles con fecha de vigencia"),
    ("correlatividades", "media", "Planes de estudio y reglamentos"),
    ("turnos_anio", "media", "Horarios publicados por la universidad"),
    ("convenios_intercambio", "media", "Listado público de universidades de destino"),
    ("ciclos_ingreso", "media", "Calendario de admisiones con ciclo de ingreso"),
)

# A section the adapter declared as unpublished maps to the tables it feeds.
UNPUBLISHED_TABLES = {
    "aranceles": ("aranceles",),
    "turnos_anio": ("turnos_anio",),
    "ofertas_ciclo": ("ciclos_ingreso",),
    "convenios_intercambio": ("convenios_intercambio",),
}


def _empty(value: object) -> bool:
    return value is None or value == "" or value == [] or value == {}


def unpublished_sections(university: str) -> dict[str, str]:
    """Read what the adapter of this university declared as unpublished."""
    path = ARTIFACTS.get(university)
    if not path or not path.exists():
        return {}
    try:
        quality = json.loads(path.read_text(encoding="utf-8"))["control_calidad"]
    except (json.JSONDecodeError, KeyError, OSError):
        return {}
    declared: dict[str, str] = {}
    for section, reason in (quality.get("secciones_sin_fuente_publica") or {}).items():
        declared[section] = str(reason)
    if quality.get("materias_sin_anio"):
        declared["materias.anio_cursada"] = str(
            (quality["materias_sin_anio"] or {}).get("motivo", "no publicado")
        )
    return declared


def _scoped_ids(client: Any, table: str, university_id: str,
               cache: dict[str, set[str]]) -> set[str] | None:
    """Return the ids of `table` that belong to this university."""
    if table in cache:
        return cache[table]
    scope = SCOPES.get(table)
    if scope is None:
        return None
    column, parent = scope
    if column == DIRECT:
        ids = {row["id"] for row in select_all(
            client.table(table).select("id").eq("universidad_id", university_id)
        )}
    else:
        parent_ids = _scoped_ids(client, parent, university_id, cache) or set()
        ids = set()
        for row in select_all(client.table(table).select(f"id,{column}")):
            if row.get(column) in parent_ids:
                ids.add(row["id"])
    cache[table] = ids
    return ids


def _rows(client: Any, table: str, columns: str, university_id: str,
          cache: dict[str, set[str]]) -> list[dict[str, Any]]:
    """Read only the rows of this university.

    Reading the whole table was the previous behaviour, and with more than one
    university loaded it attributed every other university's gaps to this one.
    """
    allowed = _scoped_ids(client, table, university_id, cache)
    rows = select_all(client.table(table).select(f"id,{columns}"))
    if allowed is None:
        return rows
    return [row for row in rows if row["id"] in allowed]


def build_report(client: Any, university: str = DEFAULT_UNIVERSITY) -> dict[str, Any]:
    found = select_all(
        client.table("universidades").select("id,nombre_oficial")
        .eq("nombre_oficial", university)
    )
    if not found:
        raise RuntimeError(f"No existe {university!r} en Supabase.")
    university_id = found[0]["id"]
    declared = unpublished_sections(university)
    cache: dict[str, set[str]] = {}
    issues: list[dict[str, Any]] = []
    not_published: list[dict[str, Any]] = []

    def record(table: str, row_id: str | None, field: str | None, priority: str,
               action: str, reason: str) -> None:
        key = f"{table}:{row_id or 'sin_filas'}:{field or 'tabla'}"
        entry = {
            "clave": key, "universidad_id": university_id, "entidad_tipo": table,
            "entidad_id": row_id, "campo": field, "prioridad": priority,
            "motivo": reason, "accion_recomendada": action,
        }
        section = f"{table}.{field}" if field else table
        excuse = declared.get(section) or next(
            (declared[name] for name, tables in UNPUBLISHED_TABLES.items()
             if table in tables and name in declared), None
        )
        if excuse:
            not_published.append({**entry, "motivo": f"No publicado: {excuse}"})
        else:
            issues.append(entry)

    for table, field, priority, source in RULES:
        for row in _rows(client, table, field, university_id, cache):
            if _empty(row.get(field)):
                record(table, row["id"], field, priority,
                       f"Completar desde: {source}", "Campo vacío")

    for table, priority, source in EMPTY_TABLES:
        if _rows(client, table, "id", university_id, cache):
            continue
        record(table, None, None, priority, f"Obtener desde: {source}",
               "Sin registros para esta universidad")

    # Enrichment is only actionable where the university publishes a profile.
    for person in _rows(client, "personas", "perfil_url,formacion,biografia",
                        university_id, cache):
        if not person.get("perfil_url"):
            continue
        for field in ("formacion", "biografia"):
            if _empty(person.get(field)):
                record("personas", person["id"], field, "baja",
                       "Completar desde el perfil académico público",
                       "Perfil público disponible pero campo todavía vacío")

    return {
        "universidad": university,
        "generado_at": datetime.now(UTC).isoformat(),
        "total_pendientes": len(issues),
        "total_no_publicado": len(not_published),
        "resumen": {
            priority: sum(issue["prioridad"] == priority for issue in issues)
            for priority in ("alta", "media", "baja")
        },
        "pendientes": issues,
        "no_publicado": not_published,
    }


def apply_report(client: Any, report: dict[str, Any]) -> None:
    """Synchronise the backlog of this university, leaving the others alone."""
    university_id = next(
        (issue["universidad_id"] for issue in report["pendientes"]), None
    )
    if not university_id:
        return
    current_keys = {issue["clave"] for issue in report["pendientes"]}
    existing = select_all(
        client.table("pendientes_datos").select("id,clave")
        .eq("universidad_id", university_id).eq("estado", "pendiente")
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


def _slug(university: str) -> str:
    from rumbo_scraper.normalizers.text import comparison_key
    known = {
        "universidad torcuato di tella": "utdt",
        "universidad de san andres": "udesa",
        "instituto tecnologico de buenos aires": "itba",
        "universidad austral": "austral",
    }
    key = comparison_key(university)
    return known.get(key, key.replace(" ", "_"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audita los campos pendientes de una universidad"
    )
    parser.add_argument("--universidad", default=DEFAULT_UNIVERSITY)
    parser.add_argument("--todas", action="store_true",
                        help="Auditar cada universidad cargada")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--apply", action="store_true",
                        help="Sincroniza pendientes_datos en Supabase")
    args = parser.parse_args()
    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()

    if args.todas:
        universities = [row["nombre_oficial"] for row in select_all(
            client.table("universidades").select("id,nombre_oficial")
        )]
    else:
        universities = [args.universidad]

    for university in universities:
        report = build_report(client, university)
        output = args.output or Path(f"data/{_slug(university)}_pendientes.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        if args.apply:
            apply_report(client, report)
        summary = " ".join(
            f"{name}={count}" for name, count in report["resumen"].items()
        )
        print(f"{university}: {report['total_pendientes']} pendientes ({summary}) "
              f"| {report['total_no_publicado']} no publicados | {output}")


if __name__ == "__main__":
    main()
