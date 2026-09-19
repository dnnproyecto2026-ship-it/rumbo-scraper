"""Validation rules for UTDT scrape results."""

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.parsers.utdt import UTDTCareer, UNIVERSITY


def validate_careers(careers: list[UTDTCareer]) -> None:
    if len(careers) < 10:
        raise ValueError(f"Expected at least 10 UTDT careers, but found {len(careers)}.")
    names = [career.denominacion_canonica for career in careers]
    if len(names) != len(set(names)):
        raise ValueError("The UTDT result contains duplicate careers.")
    if any("utdt.edu" not in career.fuente_url for career in careers):
        raise ValueError("Every UTDT record must reference an official utdt.edu source.")


def validate_dataset(dataset: dict[str, object]) -> None:
    """Validate contract shape and critical cross-section relationships."""
    sections = dataset.get("datos")
    if not isinstance(sections, dict):
        raise ValueError("Dataset is missing the datos section.")
    if set(sections) != set(SECTION_FIELDS):
        raise ValueError("Dataset sections do not match the Excel contract.")
    for section, fields in SECTION_FIELDS.items():
        for row in sections[section]:
            if tuple(row) != fields:
                raise ValueError(f"Invalid columns in section {section}.")
    careers = sections["carreras"]
    if len(careers) != 13:
        raise ValueError(f"Expected 13 careers, found {len(careers)}.")
    if any(row["universidad_nombre"] != UNIVERSITY for row in careers):
        raise ValueError("Career university names are not normalized.")
    career_names = {row["nombre_carrera"] for row in careers}
    if any(row["carrera_nombre"] not in career_names for row in sections["ofertas"]):
        raise ValueError("An offer references an unknown career.")
