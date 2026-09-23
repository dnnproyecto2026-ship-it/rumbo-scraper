"""Reading a study plan out of the document a university publishes for it.

The plans are tables that the text extractor flattens, and no two of the ten
sites write them the same way, so this is a small state machine rather than a
regular expression: an order number opens a row, the words that follow are its
name and the numbers that close it are its columns. The year comes from the
block heading, from a roman numeral in the level column or from the year column
the header declares, and when none of the three is published the subject keeps
a null year instead of a guessed one.

It lives apart from any one university because the layouts do: the UTN and the
UBA publish plans written in the same four shapes.
"""

from __future__ import annotations

import re
from typing import Any

from rumbo_scraper.contracts import blank_record
from rumbo_scraper.normalizers.text import clean_text, comparison_key


_ORDINALS = {
    "primer": 1, "primero": 1, "primera": 1, "segundo": 2, "segunda": 2,
    "tercer": 3, "tercero": 3, "tercera": 3, "cuarto": 4, "cuarta": 4,
    "quinto": 5, "quinta": 5, "sexto": 6, "sexta": 6, "septimo": 7, "septima": 7,
}
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7}
_LEVEL_WORDS = r"(nivel(?:es)?|ano|cuatrimestre|semestre|modulo)"
_HALVES = ("cuatrimestre", "semestre")

_HEADING = re.compile(
    rf"^({'|'.join(_ORDINALS)}|[1-7])\s*[°ºoa]?\s*{_LEVEL_WORDS}\b"
)
# "PRIMER" and "NIVEL" land on two lines when the heading is a merged cell.
_SPLIT_HEADING = re.compile(rf"^({'|'.join(_ORDINALS)}|[1-7])\s*[°ºoa]?$")
_LEVEL_ONLY = re.compile(rf"^{_LEVEL_WORDS}$")
_ROMAN_LINE = re.compile(r"^(i{1,3}|iv|vi{0,2})$")
_ROMAN_ROW = re.compile(r"^(i{1,3}|iv|vi{0,2})\s+\d")

# A line that totals a block is not a subject, and neither is the running head
# the Rectorado prints on every page.
_NOT_A_SUBJECT = re.compile(
    r"^(total(es)?|carga horaria|duracion|plan de estudios?|ordenanza|resolucion|"
    r"universidad|ministerio|rectorado|asignaturas?|espacios? curricular|catedras?|"
    r"codigo|cod\.?|materias?|nivel|regimen|horas|creditos|observaciones|"
    r"correlativas?|anexo|pagina|nota|modalidad|obs\.?|ano)\b"
)
_REGIMES = {"anual": "Anual", "cuatrimestral": "Cuatrimestral",
            "bimestral": "Bimestral", "semestral": "Semestral"}
# Words that belong to a column and never to the name of a subject.
_COLUMN_WORDS = {"cuat", "cuatrimestre", "cuatrimestres", "semestre", "hs", "hrs",
                 "horas", "hora", "reloj", "catedra", "catedras", "presencial",
                 "distancia", "virtual", "anual", "cuatrimestral", "semestral",
                 "bimestral", "integradora", "electiva"}
_TOKEN = re.compile(r"\d+(?:[.,]\d+)?|[^\W\d_][\w'’.&-]*|[°º*]")


def _plan_lines(text: str) -> list[str]:
    return [clean_text(line) for line in text.splitlines() if clean_text(line)]


def _heading_year(line: str) -> int | None:
    """Read the year a block heading announces, or nothing."""
    key = comparison_key(line)
    if len(line) > 70 or _NOT_A_SUBJECT.match(key):
        return None
    match = _HEADING.match(key)
    if not match:
        return None
    word = match.group(1)
    number = int(word) if word.isdigit() else _ORDINALS.get(word)
    if number is None:
        return None
    if match.group(2) in _HALVES:
        # Two terms make a year; the fifth term belongs to the third year.
        return (number + 1) // 2
    return number


def year_column_position(lines: list[str]) -> str | None:
    """Say where the plan keeps the year when it keeps it in a column.

    Some plans have no block headings and write the year in a column of the
    table instead. The header row says which one: ``Año Código Asignatura``
    puts it first, ``Cód. Asignaturas Año Hs.`` puts it after the name.
    """
    for line in lines[:40]:
        key = comparison_key(line)
        if not re.search(r"\b(ano|nivel)\b", key):
            continue
        subject = re.search(r"\b(asignaturas?|espacios?|catedras?|materias?)\b", key)
        if not subject:
            continue
        return "leading" if key.index("ano" if "ano" in key else "nivel") < subject.start() \
            else "trailing"
    return None


def parse_plan_pdf(pdf_bytes: bytes, programme: str, university: str) -> dict[str, Any]:
    """Read the subjects out of a plan document."""
    from io import BytesIO

    from pypdf import PdfReader

    try:
        pages = PdfReader(BytesIO(pdf_bytes)).pages
        text = "\n".join(page.extract_text() or "" for page in pages)
    except Exception:
        return {"materias": [], "motivo": "el documento no pudo leerse", "descartadas": 0}
    return parse_plan_text(text, programme, university)


def parse_plan_text(text: str, programme: str, university: str) -> dict[str, Any]:
    """Read the subjects of a plan out of its extracted text.

    The plans are tables flattened by the text extractor, so the reading is a
    small state machine: an order number opens a row, the words that follow
    are its name and the numbers that close it are its columns. The year comes
    from the block heading, from a roman numeral in the level column or from
    the year column the header declares. When none of the three is published
    the subject keeps a null year instead of a guessed one.
    """
    lines = _plan_lines(text)
    if len(" ".join(lines)) < 200:
        return {"materias": [], "descartadas": 0,
                "motivo": "el plan está publicado como imagen escaneada"}

    column = year_column_position(lines)
    rows: list[dict[str, Any]] = []
    year: int | None = None
    name: list[str] = []
    tail: list[int] = []
    regime: str | None = None
    area: str | None = None
    pending_year: int | None = None

    def flush() -> None:
        nonlocal name, tail, regime, pending_year
        label = clean_text(" ".join(name)).strip(" .,:-–—*")
        letters = len(re.findall(r"[^\W\d_]", label))
        if letters >= 4 and not _NOT_A_SUBJECT.match(comparison_key(label)):
            row_year = year
            hours = tail[0] if tail else None
            if column == "trailing" and tail:
                # The declared year column is the first number of the tail.
                row_year = tail[0] if 1 <= tail[0] <= 7 else row_year
                hours = tail[1] if len(tail) > 1 else None
            elif column == "leading" and pending_year:
                row_year = pending_year
            rows.append({"nombre": label, "anio": row_year, "regimen": regime,
                         "carga_horaria_semanal": hours, "area": area})
        name, tail, regime = [], [], None

    index = 0
    while index < len(lines):
        line = lines[index]
        key = comparison_key(line)
        index += 1
        heading = _heading_year(line)
        if heading is None and _SPLIT_HEADING.match(key) and index < len(lines):
            if _LEVEL_ONLY.match(comparison_key(lines[index])):
                heading = _heading_year(f"{line} {lines[index]}")
                index += 1
        if heading is not None:
            flush()
            year, pending_year, area = heading, heading, None
            continue
        if _ROMAN_LINE.match(key):
            flush()
            year = pending_year = _ROMAN[key]
            continue
        roman_row = _ROMAN_ROW.match(key)
        if roman_row:
            flush()
            year = pending_year = _ROMAN[roman_row.group(1)]
            line = line.split(None, 1)[1]
        if column and year_column_position([line]):
            # The header that declares the column is not a row of the table,
            # and the cover title above it is not one either.
            flush()
            continue
        if column == "leading" and re.fullmatch(r"[1-7]", key):
            # The year sits alone in its own cell of the declared column, so
            # it closes the row above it and opens the block below.
            flush()
            pending_year = year = int(key)
            continue
        # A heading in capitals with no number groups the subjects by area in
        # the plans that publish no year at all.
        if year is None and column is None and line.isupper() and len(line) < 60 \
                and not _NOT_A_SUBJECT.match(key) and not re.search(r"\d", line):
            flush()
            area = clean_text(line).title()
            continue
        for token in _TOKEN.findall(line):
            if token[0].isdigit():
                if name:
                    tail.append(int(float(token.replace(",", "."))))
                continue
            if token in ("°", "º", "*"):
                continue
            word = comparison_key(token).strip(".")
            if word in _REGIMES:
                regime = _REGIMES[word]
                continue
            if word in _COLUMN_WORDS:
                continue
            if tail:
                flush()
            name.append(token)
    flush()

    # The extractor also picks up the cover, the column header and the
    # running head the Rectorado prints on every page. None of them fall
    # inside a year block, so in a plan that publishes years a row without one
    # is noise, and dropping it is safer than keeping a heading as a subject.
    published_years = any(row["anio"] for row in rows)
    subjects: list[dict[str, Any]] = []
    discarded = 0
    seen: set[tuple[str, int | None]] = set()
    for row in rows:
        if published_years and not row["anio"] or len(row["nombre"]) > 120:
            discarded += 1
            continue
        identity = (comparison_key(row["nombre"]), row["anio"])
        if identity in seen:
            continue
        seen.add(identity)
        hours = row["carga_horaria_semanal"]
        subjects.append(blank_record(
            "materias", universidad_nombre=university, carrera_o_programa=programme,
            nombre_materia=row["nombre"], anio_cursada=row["anio"], turno=None,
            area_tematica=row["area"], descripcion_breve=None,
            regimen=row["regimen"],
            # Only a small number can be a weekly load; the wider columns of
            # these tables are the total hours of the subject.
            carga_horaria_semanal=hours if hours and hours <= 30 else None,
        ))
    return {"materias": subjects, "motivo": None, "descartadas": discarded}
