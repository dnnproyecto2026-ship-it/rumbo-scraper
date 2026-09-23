"""Validation rules for a catalogue read by the general reader."""

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.validators import validate_contract_urls


def validate_dataset(dataset: dict[str, object]) -> None:
    sections = dataset.get("datos")
    if not isinstance(sections, dict) or set(sections) != set(SECTION_FIELDS):
        raise ValueError("El dataset no respeta el contrato de secciones.")
    for section, fields in SECTION_FIELDS.items():
        for row in sections[section]:
            if tuple(row) != fields:
                raise ValueError(f"Columnas inválidas en {section}.")

    university = (sections["universidades"] or [{}])[0].get("nombre_oficial")
    if not university:
        raise ValueError("El dataset no nombra a la universidad.")

    names = [row["nombre_carrera"] for row in sections["carreras"]]
    programmes = [row["nombre_programa"] for row in sections["posgrados"]]
    for label, values in (("carreras", names), ("posgrados", programmes)):
        if len(values) != len(set(values)):
            repeated = sorted({v for v in values if values.count(v) > 1})
            raise ValueError(f"Hay {label} duplicados: {repeated[:3]}")
    if len(sections["ofertas"]) != len(names):
        raise ValueError("Cada carrera debe tener su oferta.")
    for row in sections["carreras"] + sections["posgrados"] + sections["materias"]:
        if row["universidad_nombre"] != university:
            raise ValueError("Hay nombres de universidad no normalizados.")

    # Every subject must belong to a programme of this dataset, or the load
    # would attach it to nothing.
    offered = set(names) | set(programmes)
    orphans = {row["carrera_o_programa"] for row in sections["materias"]} - offered
    if orphans:
        raise ValueError(f"Hay materias sin carrera: {sorted(orphans)[:3]}")

    domain = str(dataset.get("fuente_principal") or "")
    domain = domain.split("//")[-1].split("/")[0].removeprefix("www.")
    validate_contract_urls(sections, domain)
