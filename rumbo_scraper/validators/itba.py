"""Validation rules for the ITBA scrape."""

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.parsers.itba import UNIVERSITY
from rumbo_scraper.validators import validate_contract_urls

DOMAIN = "itba.edu.ar"


def validate_programmes(dataset: dict[str, object], sections: dict[str, list]) -> None:
    """Every programme the menu published must be loaded or excluded."""
    quality = dataset.get("control_calidad") or {}
    discovered = quality.get("programas_descubiertos", 0)
    excluded = quality.get("programas_excluidos") or []
    resolved = len(sections["carreras"]) + len(sections["posgrados"]) + len(excluded)
    if resolved != discovered:
        raise ValueError(
            f"Se descubrieron {discovered} programas y se resolvieron {resolved}."
        )
    if discovered and not sections["carreras"]:
        raise ValueError("El menú publicó carreras y no se pudo leer ninguna.")


def validate_dataset(dataset: dict[str, object]) -> None:
    sections = dataset.get("datos")
    if not isinstance(sections, dict) or set(sections) != set(SECTION_FIELDS):
        raise ValueError("El dataset de ITBA no respeta el contrato de secciones.")
    for section, fields in SECTION_FIELDS.items():
        for row in sections[section]:
            if tuple(row) != fields:
                raise ValueError(f"Columnas inválidas en {section}.")
    names = [row["nombre_carrera"] for row in sections["carreras"]]
    if len(names) != len(set(names)):
        raise ValueError("Hay carreras duplicadas en ITBA.")
    if any(row["universidad_nombre"] != UNIVERSITY for row in sections["carreras"]):
        raise ValueError("Hay nombres de universidad no normalizados.")
    parents = set(names) | {row["nombre_programa"] for row in sections["posgrados"]}
    orphans = {
        row["carrera_o_programa"] for row in sections["materias"]
        if row["carrera_o_programa"] not in parents
    }
    if orphans:
        raise ValueError(f"Materias sin programa que las contenga: {sorted(orphans)[:3]}")
    validate_programmes(dataset, sections)
    validate_contract_urls(sections, DOMAIN)
