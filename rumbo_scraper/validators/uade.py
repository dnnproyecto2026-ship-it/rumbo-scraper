"""Validation rules for the UMSA scrape."""

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.parsers.uade import UNIVERSITY
from rumbo_scraper.validators import validate_contract_urls

DOMAIN = "uade.edu.ar"


def validate_dataset(dataset: dict[str, object]) -> None:
    sections = dataset.get("datos")
    if not isinstance(sections, dict) or set(sections) != set(SECTION_FIELDS):
        raise ValueError("El dataset de UADE no respeta el contrato de secciones.")
    for section, fields in SECTION_FIELDS.items():
        for row in sections[section]:
            if tuple(row) != fields:
                raise ValueError(f"Columnas inválidas en {section}.")
    names = [row["nombre_carrera"] for row in sections["carreras"]]
    programmes = [row["nombre_programa"] for row in sections["posgrados"]]
    if len(names) != len(set(names)):
        raise ValueError("Hay carreras duplicadas en UADE.")
    if len(programmes) != len(set(programmes)):
        raise ValueError("Hay posgrados duplicados en UADE.")
    if any(row["universidad_nombre"] != UNIVERSITY for row in sections["carreras"]):
        raise ValueError("Hay nombres de universidad no normalizados.")
    parents = set(names) | set(programmes)
    orphans = {
        row["carrera_o_programa"] for row in sections["materias"]
        if row["carrera_o_programa"] not in parents
    }
    if orphans:
        raise ValueError(f"Materias sin programa que las contenga: {sorted(orphans)[:3]}")

    quality = dataset.get("control_calidad") or {}
    discovered = quality.get("programas_descubiertos", 0)
    failed = [row for row in quality.get("programas_excluidos") or []
              if "no se pudo" in str(row.get("motivo", ""))]
    # A programme published more than once collapses into a single row.
    merged = sum(
        len(row.get("urls", [])) - 1 for row in quality.get("programas_unificados") or []
    )
    resolved = len(names) + len(programmes) + len(failed) + merged
    if resolved != discovered:
        raise ValueError(
            f"Se descubrieron {discovered} programas y se resolvieron {resolved}."
        )
    # Losing every degree is a broken run; a catalogue that only publishes
    # postgraduate programmes is not.
    expected_degrees = discovered - len(programmes) - len(failed) - merged
    if expected_degrees > 0 and not names:
        raise ValueError("El catálogo publicó carreras y no se pudo leer ninguna.")
    validate_contract_urls(sections, DOMAIN)
