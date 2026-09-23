"""Validation rules for the UCES scrape."""

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.parsers.uces import UNIVERSITY
from rumbo_scraper.validators import validate_contract_urls

DOMAIN = "uces.edu.ar"


def validate_dataset(dataset: dict[str, object]) -> None:
    sections = dataset.get("datos")
    if not isinstance(sections, dict) or set(sections) != set(SECTION_FIELDS):
        raise ValueError("El dataset de UCES no respeta el contrato de secciones.")
    for section, fields in SECTION_FIELDS.items():
        for row in sections[section]:
            if tuple(row) != fields:
                raise ValueError(f"Columnas inválidas en {section}.")

    names = [row["nombre_carrera"] for row in sections["carreras"]]
    if len(names) != len(set(names)):
        repeated = sorted({n for n in names if names.count(n) > 1})
        raise ValueError(f"Hay carreras duplicadas en UCES: {repeated[:3]}")
    if any(row["universidad_nombre"] != UNIVERSITY for row in sections["carreras"]):
        raise ValueError("Hay nombres de universidad no normalizados.")

    faculties = {row["nombre_facultad"] for row in sections["facultades"]}
    stray = {row["facultad_nombre"] for row in sections["carreras"]
             if row["facultad_nombre"] is not None
             and row["facultad_nombre"] not in faculties}
    if stray:
        raise ValueError(f"Carreras de facultades desconocidas: {sorted(stray)[:3]}")
    campuses = {row["nombre_sede"] for row in sections["sedes"]}
    unknown = {row["sede"] for row in sections["ofertas"]
               if row["sede"] is not None and row["sede"] not in campuses}
    if unknown:
        raise ValueError(f"Ofertas en sedes desconocidas: {sorted(unknown)[:3]}")
    orphans = {row["carrera_o_programa"] for row in sections["materias"]
               if row["carrera_o_programa"] not in set(names)}
    if orphans:
        raise ValueError(f"Materias sin carrera que las contenga: {sorted(orphans)[:3]}")
    if len(sections["ofertas"]) != len(names):
        raise ValueError("Cada carrera debe tener su oferta.")

    quality = dataset.get("control_calidad") or {}
    discovered = quality.get("carreras_descubiertas", 0)
    excluded = len(quality.get("carreras_excluidas") or [])
    if len(names) + excluded != discovered:
        raise ValueError(
            f"Se descubrieron {discovered} carreras y se resolvieron "
            f"{len(names) + excluded}."
        )
    if discovered and not names:
        raise ValueError("El sitio publicó carreras y no se pudo leer ninguna.")
    validate_contract_urls(sections, DOMAIN)
