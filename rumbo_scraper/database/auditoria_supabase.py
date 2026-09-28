"""Audit what the database holds, university by university, read-only.

The coverage log (`rumbo_scraper.bitacora`) reads the JSON each adapter left
in ``data/``. Much of what reaches Supabase never passes through one of those
files: student life, institutional pages, exchange agreements, titles and
durations completed afterwards, plans read from documents. So the log
describes what the readers found and not what the application can show.
This reads the tables themselves and says, for each university, how many
rows carry each field a student compares careers by.

A career counts as *comparable* when it states the degree it gives, how long
it lasts, has a plan of study loaded and is offered at a named campus. That
is the least a comparison needs; it is a product choice, not a law.

Nothing is written to the database.

    python -m rumbo_scraper.database.auditoria_supabase
    python -m rumbo_scraper.database.auditoria_supabase --output data/auditoria.md
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Callable

from rumbo_scraper.catalogo import UNIVERSIDADES

DEFAULT_OUTPUT = Path("data/auditoria_supabase.md")

# Each table, the columns the audit needs, and how a row finds its university.
# "universidad_id" is direct; the others go through the row they point at.
TABLAS: dict[str, tuple[str, str]] = {
    "universidades": ("id,nombre_oficial,nombre_corto,tipo_gestion", ""),
    "sedes": ("id,universidad_id,calle,localidad_id", "universidad_id"),
    "facultades": ("id,universidad_id", "universidad_id"),
    "carreras": ("id,universidad_id,facultad_id,nombre_carrera,nivel,titulo_otorgado,"
                 "duracion_anios,descripcion_breve", "universidad_id"),
    "ofertas_academicas": ("id,carrera_id,sede_id,modalidad,regimen_ingreso,url_oficial",
                           "carrera_id"),
    "posgrados": ("id,universidad_id,titulo_otorgado,duracion_meses,modalidad,"
                  "url_oficial,descripcion_breve", "universidad_id"),
    "materias": ("id,universidad_id,carrera_id,posgrado_id,anio_cursada,regimen",
                 "universidad_id"),
    "aranceles": ("id,oferta_id", "oferta_id"),
    "ciclos_ingreso": ("id,oferta_id,fecha_apertura_inscripcion,fecha_cierre_inscripcion",
                       "oferta_id"),
    "turnos_anio": ("id,oferta_id", "oferta_id"),
    "becas": ("id,universidad_id", "universidad_id"),
    "servicios_estudiantiles": ("id,universidad_id", "universidad_id"),
    "actividades_extracurriculares": ("id,universidad_id", "universidad_id"),
    "alojamientos": ("id,universidad_id", "universidad_id"),
    "programas_internacionales": ("id,universidad_id", "universidad_id"),
    "convenios_intercambio": ("id,universidad_id", "universidad_id"),
    "contactos": ("id,universidad_id", "universidad_id"),
    "autoridades": ("id,facultad_id", "facultad_id"),
    "personas": ("id,universidad_id", "universidad_id"),
}

# The fields a student compares by, as (table, field, label).
CAMPOS: tuple[tuple[str, str, str], ...] = (
    ("carreras", "titulo_otorgado", "Título"),
    ("carreras", "duracion_anios", "Duración"),
    ("carreras", "descripcion_breve", "Descripción"),
    ("carreras", "facultad_id", "Unidad"),
    ("ofertas_academicas", "sede_id", "Oferta: sede"),
    ("ofertas_academicas", "modalidad", "Oferta: modalidad"),
    ("ofertas_academicas", "regimen_ingreso", "Oferta: ingreso"),
    ("ofertas_academicas", "url_oficial", "Oferta: URL"),
    ("posgrados", "titulo_otorgado", "Posgrado: título"),
    ("posgrados", "duracion_meses", "Posgrado: duración"),
    ("posgrados", "modalidad", "Posgrado: modalidad"),
    ("posgrados", "url_oficial", "Posgrado: URL"),
    ("materias", "anio_cursada", "Materia: año"),
    ("materias", "regimen", "Materia: régimen"),
)

VIDA = ("becas", "servicios_estudiantiles", "actividades_extracurriculares",
        "alojamientos", "programas_internacionales", "convenios_intercambio")


def _lleno(value: object) -> bool:
    return value not in (None, "", [], {})


def _pct(parte: int, total: int) -> str:
    return "—" if not total else f"{round(100 * parte / total)}%"


def leer_tablas(client: Any) -> dict[str, list[dict[str, Any]] | None]:
    """Read every table the audit needs; ``None`` for one that cannot be read.

    A column the schema does not have makes PostgREST refuse the query, so a
    table is read again whole before it is given up on. The audit then says
    which tables it could not see instead of reporting them as empty.
    """
    from rumbo_scraper.database.supabase import select_all

    tablas: dict[str, list[dict[str, Any]] | None] = {}
    for tabla, (columnas, _) in TABLAS.items():
        for pedido in (columnas, "*"):
            try:
                tablas[tabla] = select_all(client.table(tabla).select(pedido))
                break
            except Exception:  # noqa: BLE001 - any refusal means "cannot read"
                tablas[tabla] = None
    return tablas


def _dueno(tablas: dict[str, list[dict[str, Any]] | None]) -> Callable[[str, dict[str, Any]], str | None]:
    """A function that gives the university a row of a table belongs to."""
    def por_id(tabla: str) -> dict[str, dict[str, Any]]:
        return {fila["id"]: fila for fila in tablas.get(tabla) or []}

    carreras, ofertas, facultades = por_id("carreras"), por_id("ofertas_academicas"), por_id("facultades")

    def de_carrera(carrera_id: Any) -> str | None:
        return (carreras.get(carrera_id) or {}).get("universidad_id")

    def dueno(tabla: str, fila: dict[str, Any]) -> str | None:
        if fila.get("universidad_id"):
            return fila["universidad_id"]
        clave = TABLAS[tabla][1]
        if clave == "carrera_id":
            return de_carrera(fila.get("carrera_id"))
        if clave == "oferta_id":
            return de_carrera((ofertas.get(fila.get("oferta_id")) or {}).get("carrera_id"))
        if clave == "facultad_id":
            return (facultades.get(fila.get("facultad_id")) or {}).get("universidad_id")
        return None

    return dueno


def auditar(tablas: dict[str, list[dict[str, Any]] | None]) -> dict[str, Any]:
    """Count, per university, the rows of each table and the fields they carry."""
    dueno = _dueno(tablas)
    por_uni: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for tabla in TABLAS:
        if tabla == "universidades":
            continue
        for fila in tablas.get(tabla) or []:
            uid = dueno(tabla, fila)
            if uid:
                por_uni[uid][tabla].append(fila)

    universidades = tablas.get("universidades") or []
    resultado: list[dict[str, Any]] = []
    for uni in universidades:
        filas = por_uni.get(uni["id"], {})
        carreras = filas.get("carreras", [])
        ofertas = filas.get("ofertas_academicas", [])
        materias = filas.get("materias", [])

        con_plan = {m["carrera_id"] for m in materias if m.get("carrera_id")}
        con_sede = {o["carrera_id"] for o in ofertas if o.get("sede_id")}
        ofertas_con_arancel = {a["oferta_id"] for a in filas.get("aranceles", [])}
        ofertas_con_ciclo = {c["oferta_id"] for c in filas.get("ciclos_ingreso", [])}

        faltan: dict[str, int] = {"título": 0, "duración": 0, "plan": 0, "sede": 0}
        comparables = 0
        for carrera in carreras:
            huecos = {
                "título": not _lleno(carrera.get("titulo_otorgado")),
                "duración": not _lleno(carrera.get("duracion_anios")),
                "plan": carrera["id"] not in con_plan,
                "sede": carrera["id"] not in con_sede,
            }
            for nombre, falta in huecos.items():
                faltan[nombre] += falta
            comparables += not any(huecos.values())

        campos = {}
        for tabla, campo, _ in CAMPOS:
            lista = filas.get(tabla, [])
            campos[f"{tabla}.{campo}"] = (sum(_lleno(f.get(campo)) for f in lista), len(lista))

        resultado.append({
            "id": uni["id"],
            "nombre": uni["nombre_oficial"],
            "corto": uni.get("nombre_corto"),
            "gestion": uni.get("tipo_gestion"),
            "conteos": {tabla: len(filas.get(tabla, [])) for tabla in TABLAS if tabla != "universidades"},
            "carreras_comparables": comparables,
            "carreras_sin": faltan,
            "ofertas_con_arancel": len(ofertas_con_arancel),
            "ofertas_con_ciclo": len(ofertas_con_ciclo),
            "campos": campos,
        })

    # The biggest gap first: the careers a student cannot yet compare.
    resultado.sort(key=lambda u: (-(u["conteos"]["carreras"] - u["carreras_comparables"]),
                                  u["nombre"]))
    en_base = {u["nombre_oficial"] for u in universidades}
    return {
        "generado_at": datetime.now(UTC).isoformat(),
        "tablas_no_leidas": sorted(t for t, filas in tablas.items() if filas is None),
        "tablas_vacias": sorted(t for t, filas in tablas.items() if filas == []),
        "fuera_de_la_base": sorted(u.nombre_oficial for u in UNIVERSIDADES
                                   if u.nombre_oficial not in en_base),
        "universidades": resultado,
    }


def render(informe: dict[str, Any]) -> str:
    """Render the audit as Markdown."""
    unis = informe["universidades"]
    total = lambda clave: sum(u["conteos"][clave] for u in unis)  # noqa: E731
    carreras = total("carreras")
    comparables = sum(u["carreras_comparables"] for u in unis)
    lines = [
        "# Auditoría de Supabase por universidad",
        "",
        f"Generada el {informe['generado_at'][:10]} por "
        "`python -m rumbo_scraper.database.auditoria_supabase`, leyendo las tablas "
        "de Supabase (no los JSON locales). Sólo lectura.",
        "",
        "Una carrera es **comparable** si tiene título, duración, plan de estudios "
        "cargado y al menos una oferta con sede.",
        "",
        "## Totales",
        "",
        f"- Universidades en la base: {len(unis)}",
        f"- Carreras: {carreras}; comparables: {comparables} ({_pct(comparables, carreras)})",
        f"- Posgrados: {total('posgrados')}; materias: {total('materias')}",
        f"- Ofertas con arancel: {sum(u['ofertas_con_arancel'] for u in unis)} "
        f"de {total('ofertas_academicas')}",
        f"- Ofertas con ciclo de ingreso: {sum(u['ofertas_con_ciclo'] for u in unis)} "
        f"de {total('ofertas_academicas')}",
    ]
    if informe["tablas_no_leidas"]:
        lines.append("- Tablas que no se pudieron leer: "
                     + ", ".join(f"`{t}`" for t in informe["tablas_no_leidas"]))
    if informe["tablas_vacias"]:
        lines.append("- Tablas sin ninguna fila: "
                     + ", ".join(f"`{t}`" for t in informe["tablas_vacias"]))
    if informe["fuera_de_la_base"]:
        lines.append("- En `catalogo.py` pero no en la base: "
                     + ", ".join(informe["fuera_de_la_base"]))

    lines += [
        "",
        "## Carreras comparables, del mayor hueco al menor",
        "",
        "| Universidad | Gestión | Carreras | Comparables | Sin título | Sin duración "
        "| Sin plan | Sin sede | Posgrados | Aranceles | Ciclos | Vida |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for u in unis:
        c, sin = u["conteos"], u["carreras_sin"]
        vida = sum(c[t] for t in VIDA)
        lines.append(
            f"| {u['corto'] or u['nombre']} | {u['gestion'] or '—'} | {c['carreras']} "
            f"| {u['carreras_comparables']} ({_pct(u['carreras_comparables'], c['carreras'])}) "
            f"| {sin['título']} | {sin['duración']} | {sin['plan']} | {sin['sede']} "
            f"| {c['posgrados']} | {u['ofertas_con_arancel']} | {u['ofertas_con_ciclo']} | {vida} |"
        )

    lines += ["", "## Cobertura de campos", "",
              "Porcentaje de filas con el dato, sobre el total de esa tabla en la universidad.", "",
              "| Universidad | " + " | ".join(label for _, _, label in CAMPOS) + " |",
              "|---" + "|---:" * len(CAMPOS) + "|"]
    for u in unis:
        celdas = [_pct(*u["campos"][f"{t}.{f}"]) for t, f, _ in CAMPOS]
        lines.append(f"| {u['corto'] or u['nombre']} | " + " | ".join(celdas) + " |")

    lines += ["", "## Vida universitaria y directorio", "",
              "| Universidad | Sedes | Unidades | Becas | Servicios | Extracurr. | Alojamiento "
              "| Intl. | Convenios | Contactos | Autoridades | Personas |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for u in unis:
        c = u["conteos"]
        lines.append(
            f"| {u['corto'] or u['nombre']} | {c['sedes']} | {c['facultades']} | {c['becas']} "
            f"| {c['servicios_estudiantiles']} | {c['actividades_extracurriculares']} "
            f"| {c['alojamientos']} | {c['programas_internacionales']} "
            f"| {c['convenios_intercambio']} | {c['contactos']} | {c['autoridades']} "
            f"| {c['personas']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audita lo que Supabase tiene de cada universidad (sólo lectura)"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    informe = auditar(leer_tablas(get_supabase_client()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(informe), encoding="utf-8")
    args.output.with_suffix(".json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    unis = informe["universidades"]
    carreras = sum(u["conteos"]["carreras"] for u in unis)
    comparables = sum(u["carreras_comparables"] for u in unis)
    print(f"{len(unis)} universidades, {carreras} carreras, {comparables} comparables "
          f"({_pct(comparables, carreras)}) — {args.output}")


if __name__ == "__main__":
    main()
