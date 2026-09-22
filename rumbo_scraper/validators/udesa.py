"""Validation rules for the UdeSA deterministic scrape."""

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.normalizers.url import assert_official_url
from rumbo_scraper.parsers.udesa import CAREERS, UNIVERSITY
from rumbo_scraper.validators import validate_contract_urls

DOMAIN = "udesa.edu.ar"


def validate_postgraduates(
    dataset: dict[str, object], sections: dict[str, list[dict[str, object]]]
) -> None:
    """Every discovered programme must be loaded or excluded with a reason.

    The count is not hardcoded: the official index decides how many there are,
    so a new programme is picked up and a disappearing one is visible instead
    of silently reducing the dataset.
    """
    quality = dataset.get("control_calidad") or {}
    discovered = quality.get("posgrados_descubiertos", 0)
    excluded = quality.get("posgrados_excluidos") or []
    programmes = sections["posgrados"]
    if len(programmes) + len(excluded) != discovered:
        raise ValueError(
            f"Se descubrieron {discovered} posgrados pero se resolvieron "
            f"{len(programmes)} cargados y {len(excluded)} excluidos."
        )
    if discovered and not programmes:
        raise ValueError("El índice publicó posgrados y no se pudo leer ninguno.")
    names = [row["nombre_programa"] for row in programmes]
    if len(names) != len(set(names)):
        raise ValueError("Hay posgrados duplicados en UdeSA.")
    if any(row["universidad_nombre"] != UNIVERSITY for row in programmes):
        raise ValueError("Hay posgrados con la universidad sin normalizar.")


def validate_dataset(dataset: dict[str, object]) -> None:
    sections = dataset.get("datos")
    if not isinstance(sections, dict) or set(sections) != set(SECTION_FIELDS):
        raise ValueError("El dataset de UdeSA no respeta el contrato de secciones.")
    for section, fields in SECTION_FIELDS.items():
        for row in sections[section]:
            if tuple(row) != fields:
                raise ValueError(f"Columnas inválidas en {section}.")
    careers = sections["carreras"]
    if len(careers) != len(CAREERS):
        raise ValueError(f"Se esperaban {len(CAREERS)} carreras y se obtuvieron {len(careers)}.")
    names = [row["nombre_carrera"] for row in careers]
    if len(names) != len(set(names)):
        raise ValueError("Hay carreras duplicadas en UdeSA.")
    if any(row["universidad_nombre"] != UNIVERSITY for row in careers):
        raise ValueError("Hay nombres de universidad no normalizados.")
    valid_careers = set(names)
    if any(row["carrera_o_programa"] not in valid_careers for row in sections["materias"]):
        raise ValueError("Una materia referencia una carrera inexistente.")
    validate_postgraduates(dataset, sections)
    validate_contract_urls(sections, DOMAIN)
    for index, resource in enumerate(dataset.get("recursos_publicos", [])):
        assert_official_url(resource.get("url"), DOMAIN, f"recursos_publicos[{index}].url")
