"""Validation rules for the UBA scrape."""

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.parsers.uba import UNIVERSITY
from rumbo_scraper.validators import validate_contract_urls

DOMAIN = "uba.ar"


def validate_dataset(dataset: dict[str, object]) -> None:
    sections = dataset.get("datos")
    if not isinstance(sections, dict) or set(sections) != set(SECTION_FIELDS):
        raise ValueError("El dataset de la UBA no respeta el contrato de secciones.")
    for section, fields in SECTION_FIELDS.items():
        for row in sections[section]:
            if tuple(row) != fields:
                raise ValueError(f"Columnas inválidas en {section}.")

    names = [row["nombre_carrera"] for row in sections["carreras"]]
    if len(names) != len(set(names)):
        duplicated = sorted({name for name in names if names.count(name) > 1})
        raise ValueError(f"Hay carreras duplicadas en la UBA: {duplicated[:3]}")
    if any(row["universidad_nombre"] != UNIVERSITY for row in sections["carreras"]):
        raise ValueError("Hay nombres de universidad no normalizados.")

    programmes = [row["nombre_programa"] for row in sections["posgrados"]]
    if len(programmes) != len(set(programmes)):
        repeated = sorted({p for p in programmes if programmes.count(p) > 1})
        raise ValueError(f"Hay posgrados duplicados en la UBA: {repeated[:3]}")

    faculties = {row["nombre_facultad"] for row in sections["facultades"]}
    stray = {row["facultad_nombre"] for row in sections["carreras"]
             if row["facultad_nombre"] not in faculties}
    if stray:
        raise ValueError(f"Carreras de facultades desconocidas: {sorted(stray)[:3]}")
    orphan_programmes = {row["facultad_nombre"] for row in sections["posgrados"]
                         if row["facultad_nombre"] not in faculties}
    if orphan_programmes:
        raise ValueError(
            f"Posgrados de facultades desconocidas: {sorted(orphan_programmes)[:3]}"
        )
    # A career is offered where its own faculty is; an offer naming a campus
    # the catalogue never published would be an invented one.
    campuses = {row["nombre_sede"] for row in sections["sedes"]}
    unknown = {row["sede"] for row in sections["ofertas"]
               if row["sede"] is not None and row["sede"] not in campuses}
    if unknown:
        raise ValueError(f"Ofertas en sedes desconocidas: {sorted(unknown)[:3]}")
    if len(sections["ofertas"]) != len(names):
        raise ValueError("Cada carrera del catálogo debe tener su oferta.")

    quality = dataset.get("control_calidad") or {}
    discovered = quality.get("facultades_descubiertas", 0)
    excluded = len(quality.get("facultades_excluidas") or [])
    if len(faculties) + excluded != discovered:
        raise ValueError(
            f"Se descubrieron {discovered} facultades y se resolvieron "
            f"{len(faculties) + excluded}."
        )
    if discovered and not names:
        raise ValueError("El catálogo publicó carreras y no se pudo leer ninguna.")
    validate_contract_urls(sections, DOMAIN)
