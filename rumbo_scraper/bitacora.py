"""Write the log of what each university publishes and what it does not.

Everything here is read from the artifacts each adapter produced and from the
audit reports; nothing is written by hand. A section that is empty because the
university does not publish it is reported apart from one that is empty and
could still be filled, because they are different kinds of work.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from rumbo_scraper.contracts import SECTION_FIELDS

DEFAULT_OUTPUT = Path("data/bitacora.md")

# Each university, its artifact and its audit report.
SOURCES: tuple[tuple[str, str, str], ...] = (
    ("Universidad Torcuato Di Tella", "utdt_completo", "utdt_pendientes"),
    ("Universidad de San Andrés", "udesa_completo", "udesa_pendientes"),
    ("Instituto Tecnológico de Buenos Aires", "itba_completo", "itba_pendientes"),
    ("Universidad Austral", "austral_completo", "austral_pendientes"),
    ("Universidad del Museo Social Argentino", "umsa_completo", "umsa_pendientes"),
    ("Pontificia Universidad Católica Argentina", "uca_completo", "uca_pendientes"),
    ("Universidad Argentina de la Empresa", "uade_completo", "uade_pendientes"),
    ("Universidad de Belgrano", "ub_completo", "ub_pendientes"),
    ("Universidad Tecnológica Nacional", "utn_completo", "utn_pendientes"),
    ("Universidad de Buenos Aires", "uba_completo", "uba_pendientes"),
    ("Universidad Abierta Interamericana", "uai_completo", "uai_pendientes"),
    ("Universidad de Palermo", "palermo_completo", "palermo_pendientes"),
    ("Universidad del CEMA", "ucema_completo", "ucema_pendientes"),
    ("Universidad de Ciencias Empresariales y Sociales", "uces_completo",
     "uces_pendientes"),
    ("Universidad del Salvador", "usal_completo", "usal_pendientes"),
)

# The sections worth reporting, in the order a reader cares about them.
REPORTED = (
    "sedes", "facultades", "carreras", "ofertas", "posgrados", "materias",
    "becas", "servicios_estudiantiles", "actividades_extracurriculares",
    "alojamiento", "programas_internacionales", "convenios_intercambio",
    "autoridades", "redes_contacto", "aranceles", "turnos_anio", "ofertas_ciclo",
)


def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _filled(rows: list[dict[str, Any]], field: str) -> tuple[int, int]:
    present = sum(1 for row in rows if row.get(field) not in (None, "", [], {}))
    return present, len(rows)


def collect(data_dir: Path = Path("data")) -> list[dict[str, Any]]:
    """Read every artifact and audit report that exists."""
    universities: list[dict[str, Any]] = []
    for name, artifact, audit in SOURCES:
        dataset = _load(data_dir / f"{artifact}.json")
        if dataset is None:
            continue
        report = _load(data_dir / f"{audit}.json") or {}
        quality = dataset.get("control_calidad") or {}
        sections = dataset.get("datos") or {}
        directory = dataset.get("directorio_academico") or {}
        universities.append({
            "nombre": name,
            "extraido_en": dataset.get("extraido_en"),
            "metodo": dataset.get("metodo"),
            "conteos": {section: len(sections.get(section) or []) for section in SECTION_FIELDS},
            "personas": len(directory.get("personas") or []),
            "roles": len(directory.get("roles_academicos") or []),
            "no_publicado": quality.get("secciones_sin_fuente_publica") or {},
            "materias_sin_anio": quality.get("materias_sin_anio") or {},
            "excluidos": quality.get("programas_excluidos") or [],
            "unificados": quality.get("programas_unificados") or [],
            "errores": quality.get("errores_descarga") or [],
            "pendientes": report.get("total_pendientes"),
            "resumen": report.get("resumen") or {},
            "campos": _field_coverage(sections),
        })
    return universities


KEY_FIELDS = (
    ("carreras", "titulo_otorgado"),
    ("carreras", "duracion_anios"),
    ("carreras", "cantidad_materias_total"),
    ("posgrados", "tipo_posgrado"),
    ("posgrados", "titulo_otorgado"),
    ("posgrados", "duracion_meses"),
    ("posgrados", "modalidad"),
    ("materias", "anio_cursada"),
    ("materias", "regimen"),
)


def _field_coverage(sections: dict[str, Any]) -> dict[str, tuple[int, int]]:
    coverage: dict[str, tuple[int, int]] = {}
    for section, field in KEY_FIELDS:
        rows = sections.get(section) or []
        if rows:
            coverage[f"{section}.{field}"] = _filled(rows, field)
    return coverage


def render(universities: list[dict[str, Any]]) -> str:
    """Render the log as Markdown."""
    lines = [
        "# Bitácora de cobertura por universidad",
        "",
        f"Generada el {datetime.now(UTC).date().isoformat()} por "
        "`python -m rumbo_scraper.bitacora`, leyendo los artefactos de cada "
        "adapter y los informes de auditoría. No hay datos escritos a mano.",
        "",
        "## Resumen",
        "",
        "| Universidad | Carreras | Posgrados | Materias | Personas | Pendientes |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in universities:
        counts = item["conteos"]
        lines.append(
            f"| {item['nombre']} | {counts['carreras']} | {counts['posgrados']} "
            f"| {counts['materias']} | {item['personas']} "
            f"| {item['pendientes'] if item['pendientes'] is not None else '—'} |"
        )

    lines += ["", "## Secciones vacías, por universidad", ""]
    for item in universities:
        empty = [s for s in REPORTED if not item["conteos"].get(s)]
        lines.append(f"**{item['nombre']}**")
        if not empty:
            lines += ["", "- Ninguna: todas las secciones reportadas tienen datos.", ""]
            continue
        lines.append("")
        for section in empty:
            reason = item["no_publicado"].get(section)
            lines.append(f"- `{section}` — {reason or 'sin datos, causa no declarada'}")
        lines.append("")

    lines += ["## Cobertura de los campos que más importan", "",
              "Cuántas filas traen el dato sobre el total de esa sección.", ""]
    header = "| Campo | " + " | ".join(
        item["nombre"].replace("Universidad ", "").replace("Pontificia ", "")[:14]
        for item in universities
    ) + " |"
    lines += [header, "|---" * (len(universities) + 1) + "|"]
    for section, field in KEY_FIELDS:
        cells = []
        for item in universities:
            coverage = item["campos"].get(f"{section}.{field}")
            cells.append(f"{coverage[0]}/{coverage[1]}" if coverage else "—")
        lines.append(f"| `{section}.{field}` | " + " | ".join(cells) + " |")

    lines += ["", "## Qué queda fuera y por qué", ""]
    for item in universities:
        lines.append(f"### {item['nombre']}")
        lines.append("")
        lines.append(f"- Método: {item['metodo'] or 'no declarado'}")
        if item["materias_sin_anio"]:
            lines.append(f"- Materias sin año: {item['materias_sin_anio'].get('motivo')}")
        reasons: dict[str, int] = {}
        for row in item["excluidos"]:
            reasons[str(row.get("motivo"))] = reasons.get(str(row.get("motivo")), 0) + 1
        for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1])[:6]:
            lines.append(f"- {count} programa(s) fuera del contrato: {reason}")
        if item["unificados"]:
            lines.append(
                f"- {len(item['unificados'])} programa(s) publicados más de una vez, "
                "unificados en una fila"
            )
        if item["errores"]:
            lines.append(f"- {len(item['errores'])} descarga(s) fallidas en la última corrida")
        summary = item["resumen"]
        if summary:
            lines.append(
                "- Backlog de auditoría: "
                + ", ".join(f"{name} {count}" for name, count in summary.items())
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera la bitácora de cobertura por universidad"
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    universities = collect(args.data_dir)
    if not universities:
        print(f"No hay artefactos en {args.data_dir}.")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(universities), encoding="utf-8")
    print(f"Bitácora de {len(universities)} universidades: {args.output}")


if __name__ == "__main__":
    main()
