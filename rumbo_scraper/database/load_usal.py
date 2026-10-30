"""Validate and load the la USAL dataset into Supabase.

A whole load syncs the subjects to the reading's, and the reading has none
(USAL's plans come from the plan readers): it would delete them. A newer
reading's careers go in with ``--solo-nuevas``.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from rumbo_scraper.database.load_utdt import (
    _boolean, _insert_chunks, _sync_subjects, _upsert_one,
)
from rumbo_scraper.database.load_utn import SCHEMA_CHANNELS
from rumbo_scraper.parsers.usal import programme_name
from rumbo_scraper.validators.usal import validate_dataset
from rumbo_scraper.verificacion import _VACIAS, plano

DEFAULT_INPUT = Path("data/usal_completo.json")
CORE_SECTIONS = (
    "universidades", "facultades", "carreras", "ofertas", "posgrados", "aranceles",
)
LOADABLE_KINDS = frozenset({"Doctorado", "Maestría", "Especialización", "Diplomatura"})


def load_file(path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    validate_dataset(dataset)
    return dataset


def preview(dataset: dict[str, Any]) -> dict[str, int]:
    validate_dataset(dataset)
    data = dataset["datos"]
    counts = {section: len(data[section]) for section in CORE_SECTIONS}
    loadable = [row for row in data["posgrados"] if row["tipo_posgrado"] in LOADABLE_KINDS]
    counts["posgrados"] = len(loadable)
    counts["posgrados_sin_tipo_del_esquema"] = len(data["posgrados"]) - len(loadable)
    return counts


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

    campus_ids: dict[str, str] = {}
    for row in data["sedes"]:
        saved = _upsert_one(client, "sedes", {
            "universidad_id": university_id, "nombre_sede": row["nombre_sede"],
            "localidad_id": None, "calle": row["calle"], "numero": row["numero"],
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

    # The site names the campuses of the faculty, not the one that teaches
    # each career, and ofertas_academicas.sede_id is NOT NULL.
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
            "requiere_tesis_trabajo_final": _boolean(row["requiere_tesis_trabajo_final"]),
            "requisito_titulo_previo": row["requisito_titulo_previo"],
            "cohorte_inicio": row["cohorte_inicio"],
            "costo_total_programa": row["costo_total_programa"],
            "moneda": row["moneda"], "descripcion_breve": row["descripcion_breve"],
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
        "turno": row["turno"], "area_tematica_id": None,
        "descripcion_breve": row["descripcion_breve"], "regimen": row["regimen"],
        "carga_horaria_semanal": row["carga_horaria_semanal"],
    } for row in subjects])

    client.table("contactos").delete().eq("universidad_id", university_id).execute()
    if faculty_ids:
        client.table("autoridades").delete().in_(
            "facultad_id", list(faculty_ids.values())
        ).execute()
    authorities = [row for row in data["autoridades"]
                   if faculty_ids.get(str(row["facultad_nombre"]))]
    counts["autoridades"] = _insert_chunks(client, "autoridades", [{
        "facultad_id": faculty_ids[str(row["facultad_nombre"])],
        "carrera_id": None, "cargo": row["cargo"], "tipo": row["tipo"],
        "nombre_autoridad": row["nombre_autoridad"],
    } for row in authorities])

    # The USAL is the first source that publishes what a career costs, and the
    # fee hangs off the offer, not off the career. The site does not say in
    # which campus each career is taught, so it has no offer to hang from and
    # the fees stay in the artifact.
    counts["aranceles_sin_oferta"] = len(data["aranceles"])

    contacts = [row for row in data["redes_contacto"] if row["canal"] in SCHEMA_CHANNELS]
    counts["redes_contacto"] = _insert_chunks(client, "contactos", [{
        "universidad_id": university_id,
        "facultad_id": faculty_ids.get(str(row["facultad_nombre"])),
        "carrera_id": None, "canal": row["canal"],
        "usuario_o_direccion": row["usuario_o_direccion"],
    } for row in contacts])
    return counts


def _palabras(nombre: str) -> frozenset[str]:
    """The words that name a career, whatever order and kind-of-degree words
    the site gives them ("Dermatocosmiatría (Tecnicatura)" is the
    "Tecnicatura en Dermatocosmiatría" already loaded)."""
    return frozenset(plano(nombre).split()) - _VACIAS


# A pedagogical cycle for graduates of any discipline ("Profesor en (la
# disciplina que corresponda)") is no career of its own.
_NO_ES_CARRERA = re.compile(r"(?i)^ciclo pedag[óo]gico")


def new_careers(dataset: dict[str, Any], loaded: list[str]) -> list[dict[str, Any]]:
    """The careers of a newer reading that are not among ``loaded``, by
    name or by the words of their name, with the name and level the index
    gives them (a reading written before ``programme_name`` keeps the mark)."""
    known = {_palabras(nombre) for nombre in loaded}
    rows = []
    for row in dataset["datos"]["carreras"]:
        nombre, nivel = programme_name(row["nombre_carrera"], row["nivel"])
        if _palabras(nombre) in known or _NO_ES_CARRERA.match(nombre):
            continue
        rows.append({**row, "nombre_carrera": nombre, "denominacion_canonica": nombre, "nivel": nivel,
                     "_leida_como": row["nombre_carrera"]})
    return rows


def add_new_careers(dataset: dict[str, Any], artefact_path: Path, apply: bool,
                    client: Any | None = None) -> list[dict[str, Any]]:
    """Add the careers a newer reading found and nothing else: the subjects
    of USAL come from the plan readers, not from this reading, so a whole
    load (which syncs subjects to the reading's none) would delete them. The
    careers go to the scraper DB and, with their offer and fee, to the
    artefact the export takes each career's page from."""
    validate_dataset(dataset)
    data = dataset["datos"]
    if client is None:
        from rumbo_scraper.database.supabase import get_supabase_client
        client = get_supabase_client()
    university_id = client.table("universidades").select("id").eq(
        "nombre_oficial", data["universidades"][0]["nombre_oficial"]).execute().data[0]["id"]
    loaded = [row["nombre_carrera"] for row in client.table("carreras").select("nombre_carrera").eq(
        "universidad_id", university_id).execute().data]
    artefact = json.loads(artefact_path.read_text(encoding="utf-8"))
    # New to the artefact (the DB may have it from a load cut short); written
    # to the DB only if new there too.
    rows = new_careers(dataset, [row["nombre_carrera"] for row in artefact["datos"]["carreras"]])
    in_db = {_palabras(nombre) for nombre in loaded}
    if not apply or not rows:
        return rows
    # The artefact first: if it does not validate, nothing is written.
    for row in rows:
        faculty = row["facultad_nombre"]
        if faculty and faculty not in {f["nombre_facultad"] for f in artefact["datos"]["facultades"]}:
            artefact["datos"]["facultades"].append(next(
                f for f in data["facultades"] if f["nombre_facultad"] == faculty))
        leida = row["_leida_como"]
        artefact["datos"]["carreras"].append({k: v for k, v in row.items() if k != "_leida_como"})
        for section in ("ofertas", "aranceles"):
            artefact["datos"][section] += [{**r, "carrera_nombre": row["nombre_carrera"]}
                                           for r in data[section] if r["carrera_nombre"] == leida]
        artefact["detalle_programas"] += [{**d, "nombre": row["nombre_carrera"], "nivel": row["nivel"]}
                                          for d in dataset.get("detalle_programas") or [] if d["nombre"] == leida]
        artefact["control_calidad"]["programas_descubiertos"] += 1
    # A career added by hand (``agregar_carrera``) leaves the artefact's count
    # of discovered programmes behind: everything else is checked.
    quality = artefact["control_calidad"]
    resolved = len(artefact["datos"]["carreras"]) + len(artefact["datos"]["posgrados"]) \
        + len(quality.get("programas_excluidos") or [])
    validate_dataset({**artefact, "control_calidad": {**quality, "programas_descubiertos": resolved}})

    faculty_ids: dict[str, str] = {}
    for row in rows:
        faculty = row["facultad_nombre"]
        if _palabras(row["nombre_carrera"]) in in_db:
            continue
        if faculty and faculty not in faculty_ids:
            faculty_ids[faculty] = _upsert_one(client, "facultades", {
                "universidad_id": university_id, "nombre_facultad": faculty, "tipo_unidad": "Facultad",
            }, "universidad_id,nombre_facultad,tipo_unidad")["id"]
        _upsert_one(client, "carreras", {
            "universidad_id": university_id, "facultad_id": faculty_ids.get(faculty),
            "nombre_carrera": row["nombre_carrera"], "denominacion_canonica": row["denominacion_canonica"],
            "nivel": row["nivel"], "titulo_otorgado": row["titulo_otorgado"],
            "tiene_titulo_intermedio": _boolean(row["tiene_titulo_intermedio"]),
            "duracion_anios": row["duracion_anios"], "descripcion_breve": row["descripcion_breve"],
            "cantidad_materias_total": row["cantidad_materias_total"],
        }, "universidad_id,nombre_carrera")
    artefact_path.write_text(json.dumps(artefact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar el dataset de la USAL")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    # Only the careers the scraper DB lacks, into it and into data/usal_completo.json.
    parser.add_argument("--solo-nuevas", action="store_true")
    args = parser.parse_args()
    dataset = load_file(args.input)
    if args.solo_nuevas:
        rows = add_new_careers(dataset, DEFAULT_INPUT, args.apply)
        print("AGREGADAS" if args.apply else "NUEVAS (sin escribir)")
        for row in rows:
            print(f"- {row['nombre_carrera']} ({row['nivel']}, {row['duracion_anios']} años, {row['titulo_otorgado']})")
        return
    counts = apply_dataset(dataset) if args.apply else preview(dataset)
    print("CARGADO" if args.apply else "VALIDADO (sin escribir)")
    for section, count in counts.items():
        print(f"- {section}: {count}")


if __name__ == "__main__":
    main()
