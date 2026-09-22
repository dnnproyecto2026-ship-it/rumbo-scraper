"""Validation rules for the UTN scrape."""

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.parsers.utn import UNIVERSITY
from rumbo_scraper.validators import validate_contract_urls

DOMAIN = "utn.edu.ar"


def validate_dataset(dataset: dict[str, object]) -> None:
    sections = dataset.get("datos")
    if not isinstance(sections, dict) or set(sections) != set(SECTION_FIELDS):
        raise ValueError("El dataset de la UTN no respeta el contrato de secciones.")
    for section, fields in SECTION_FIELDS.items():
        for row in sections[section]:
            if tuple(row) != fields:
                raise ValueError(f"Columnas inválidas en {section}.")

    names = [row["nombre_carrera"] for row in sections["carreras"]]
    programmes = [row["nombre_programa"] for row in sections["posgrados"]]
    if len(names) != len(set(names)):
        raise ValueError("Hay carreras duplicadas en la UTN.")
    if len(programmes) != len(set(programmes)):
        raise ValueError("Hay posgrados duplicados en la UTN.")
    if any(row["universidad_nombre"] != UNIVERSITY for row in sections["carreras"]):
        raise ValueError("Hay nombres de universidad no normalizados.")

    parents = set(names) | set(programmes)
    orphans = {row["carrera_o_programa"] for row in sections["materias"]
               if row["carrera_o_programa"] not in parents}
    if orphans:
        raise ValueError(f"Materias sin programa que las contenga: {sorted(orphans)[:3]}")

    # A regional faculty teaches the career; an offer that names a campus the
    # catalogue never listed would be an invented one.
    campuses = {row["nombre_sede"] for row in sections["sedes"]}
    unknown = {row["sede"] for row in sections["ofertas"] if row["sede"] not in campuses}
    if unknown:
        raise ValueError(f"Ofertas en sedes desconocidas: {sorted(unknown)[:3]}")
    faculties = {row["nombre_facultad"] for row in sections["facultades"]}
    stray = {row["facultad_nombre"] for row in sections["autoridades"]
             if row["facultad_nombre"] not in faculties}
    if stray:
        raise ValueError(f"Autoridades de facultades desconocidas: {sorted(stray)[:3]}")

    quality = dataset.get("control_calidad") or {}
    discovered = quality.get("carreras_descubiertas", 0)
    resolved = len(names) + len(programmes)
    if resolved != discovered:
        raise ValueError(
            f"Se descubrieron {discovered} carreras y se resolvieron {resolved}."
        )
    if discovered and not names:
        raise ValueError("El catálogo publicó carreras y no se pudo leer ninguna.")
    validate_contract_urls(sections, DOMAIN)
