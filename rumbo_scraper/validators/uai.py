"""Validation rules for the UAI scrape."""

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.parsers.uai import UNIVERSITY
from rumbo_scraper.validators import validate_contract_urls

DOMAIN = "uai.edu.ar"


def validate_dataset(dataset: dict[str, object]) -> None:
    sections = dataset.get("datos")
    if not isinstance(sections, dict) or set(sections) != set(SECTION_FIELDS):
        raise ValueError("El dataset de la UAI no respeta el contrato de secciones.")
    for section, fields in SECTION_FIELDS.items():
        for row in sections[section]:
            if tuple(row) != fields:
                raise ValueError(f"Columnas inválidas en {section}.")

    names = [row["nombre_carrera"] for row in sections["carreras"]]
    programmes = [row["nombre_programa"] for row in sections["posgrados"]]
    for label, values in (("carreras", names), ("posgrados", programmes)):
        if len(values) != len(set(values)):
            repeated = sorted({v for v in values if values.count(v) > 1})
            raise ValueError(f"Hay {label} duplicados en la UAI: {repeated[:3]}")
    if any(row["universidad_nombre"] != UNIVERSITY for row in sections["carreras"]):
        raise ValueError("Hay nombres de universidad no normalizados.")

    faculties = {row["nombre_facultad"] for row in sections["facultades"]}
    stray = {row["facultad_nombre"] for row in sections["carreras"]
             if row["facultad_nombre"] not in faculties}
    stray |= {row["facultad_nombre"] for row in sections["autoridades"]
              if row["facultad_nombre"] not in faculties}
    if stray:
        raise ValueError(f"Filas de facultades desconocidas: {sorted(stray)[:3]}")
    parents = set(names) | set(programmes)
    orphans = {row["carrera_o_programa"] for row in sections["materias"]
               if row["carrera_o_programa"] not in parents}
    if orphans:
        raise ValueError(f"Materias sin programa que las contenga: {sorted(orphans)[:3]}")
    if len(sections["ofertas"]) != len(names):
        raise ValueError("Cada carrera de grado debe tener su oferta.")

    quality = dataset.get("control_calidad") or {}
    discovered = quality.get("carreras_descubiertas", 0)
    excluded = len(quality.get("carreras_excluidas") or [])
    resolved = len(names) + len(programmes) + excluded
    if resolved != discovered:
        raise ValueError(
            f"Se descubrieron {discovered} carreras y se resolvieron {resolved}."
        )
    if discovered and not names:
        raise ValueError("El sitio publicó carreras y no se pudo leer ninguna.")
    validate_contract_urls(sections, DOMAIN)
