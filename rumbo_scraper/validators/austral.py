"""Validation rules for the Universidad Austral scrape."""

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.parsers.austral import UNIVERSITY
from rumbo_scraper.validators import validate_contract_urls

DOMAIN = "austral.edu.ar"


def validate_dataset(dataset: dict[str, object]) -> None:
    sections = dataset.get("datos")
    if not isinstance(sections, dict) or set(sections) != set(SECTION_FIELDS):
        raise ValueError("El dataset de Austral no respeta el contrato de secciones.")
    for section, fields in SECTION_FIELDS.items():
        for row in sections[section]:
            if tuple(row) != fields:
                raise ValueError(f"Columnas inválidas en {section}.")
    names = [row["nombre_carrera"] for row in sections["carreras"]]
    if len(names) != len(set(names)):
        raise ValueError("Hay carreras duplicadas en Austral.")
    programmes = [row["nombre_programa"] for row in sections["posgrados"]]
    if len(programmes) != len(set(programmes)):
        raise ValueError("Hay posgrados duplicados en Austral.")
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
    failed = [
        row for row in quality.get("programas_excluidos") or []
        if "no se pudo descargar" in str(row.get("motivo", ""))
    ]
    # A programme published more than once collapses into a single row, so the
    # extra entries are accounted for here instead of looking like losses.
    merged = sum(
        len(row.get("urls", [])) - 1 for row in quality.get("programas_unificados") or []
    )
    resolved = len(names) + len(programmes) + len(failed) + merged
    if resolved != discovered:
        raise ValueError(
            f"Se descubrieron {discovered} programas y se resolvieron {resolved}."
        )
    if discovered and not names:
        raise ValueError("El catálogo publicó carreras y no se pudo leer ninguna.")
    validate_contract_urls(sections, DOMAIN)
