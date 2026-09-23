"""Validation rules for the UCEMA scrape."""

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.parsers.ucema import UNIVERSITY
from rumbo_scraper.validators import validate_contract_urls

DOMAIN = "ucema.edu.ar"


def validate_dataset(dataset: dict[str, object]) -> None:
    sections = dataset.get("datos")
    if not isinstance(sections, dict) or set(sections) != set(SECTION_FIELDS):
        raise ValueError("El dataset de la UCEMA no respeta el contrato de secciones.")
    for section, fields in SECTION_FIELDS.items():
        for row in sections[section]:
            if tuple(row) != fields:
                raise ValueError(f"Columnas inválidas en {section}.")

    names = [row["nombre_carrera"] for row in sections["carreras"]]
    programmes = [row["nombre_programa"] for row in sections["posgrados"]]
    for label, values in (("carreras", names), ("posgrados", programmes)):
        if len(values) != len(set(values)):
            repeated = sorted({v for v in values if values.count(v) > 1})
            raise ValueError(f"Hay {label} duplicados en la UCEMA: {repeated[:3]}")
    if any(row["universidad_nombre"] != UNIVERSITY for row in sections["carreras"]):
        raise ValueError("Hay nombres de universidad no normalizados.")
    if len(sections["ofertas"]) != len(names):
        raise ValueError("Cada carrera de grado debe tener su oferta.")

    quality = dataset.get("control_calidad") or {}
    discovered = quality.get("programas_descubiertos", 0)
    excluded = len(quality.get("programas_excluidos") or [])
    resolved = len(names) + len(programmes) + excluded
    if resolved != discovered:
        raise ValueError(
            f"Se descubrieron {discovered} programas y se resolvieron {resolved}."
        )
    if discovered and not names:
        raise ValueError("El sitio publicó carreras y no se pudo leer ninguna.")
    validate_contract_urls(sections, DOMAIN)
