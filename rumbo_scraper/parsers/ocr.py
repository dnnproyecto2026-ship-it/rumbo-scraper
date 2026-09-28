"""A scanned plan of studies, read by OCR and kept only as far as it names
known subjects.

A plan published as a scanned document has no text: `texto` renders each
page (pdftoppm, 300 dpi, grey) and reads it with tesseract in Spanish, and
keeps the text next to the document (``<documento>.ocr.txt``) so no page is
read twice.

OCR misreads: "Al ebra Lineal", "Física ll", "lnglés". So a line counts as a
subject only if it is, nearly letter for letter, the name of a subject some
university already publishes (`vocabulario`: the subjects in the database),
and it is written as that known name. The year is the last year heading
("PRIMER AÑO", "2º Año") above it. A line under a year that reads like a
name but is no known subject is counted as missed: a plan that misses more
than one subject in twenty is not taken (`plan_escaneado` returns nothing),
since what is missing may be a subject the OCR lost.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.parsers.planes_sitios import anio_de, desde_el_primero

PAGINAS = 40
PARECIDO = 90       # rapidfuzz ratio a line needs to be taken as a known subject
FALTANTES = 0.05    # share of name-like lines under a year that may be unknown

_ORDINALES = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4, "quinto": 5,
              "sexto": 6, "septimo": 7, "séptimo": 7, "octavo": 8, "noveno": 9, "decimo": 10, "décimo": 10}
_CUATRIMESTRE_EN_LA_LINEA = re.compile(
    r"(?i)\b(primer|segundo|tercer|cuarto|quinto|sexto|s[ée]ptimo|octavo|noveno|d[ée]cimo|\d{1,2}\s*[°º]?)\s+cuatrimestre\b")
# A table row that lost its name: it starts with a subject's code ("C6", "FB12").
_FILA_CON_CODIGO = re.compile(r"^\W{0,3}[A-Z]{1,3}\d{1,3}\b")
_ANIO_EN_LA_LINEA = re.compile(
    r"(?i)^\W*((?:primer|primero|segundo|tercer|tercero|cuarto|quinto|sexto)\s+a[ñn]o|\d\s*[°ºo]?\s*a[ñn]o)\b")
# What a table row carries besides the name: codes, hours, terms, marks.
_RESTO = re.compile(
    r"(?i)\b(anual|cuatrimestral|semestral|bimestral|obligatori[ao]|optativ[ao]|presencial|virtual|hs\.?|horas?)\b"
    r"|\b[A-Z]{0,3}\d+[\w./-]*\b|[|_\[\]{}=+*#~•·]")


def texto(documento: Path, paginas: int = PAGINAS) -> str:
    """The document's text as tesseract reads it, page after page."""
    guardado = documento.with_suffix(documento.suffix + ".ocr.txt")
    if guardado.exists():
        return guardado.read_text()
    partes: list[str] = []
    with tempfile.TemporaryDirectory() as carpeta:
        for pagina in range(1, paginas + 1):
            imagen = Path(carpeta) / f"p{pagina}"
            hecho = subprocess.run(["pdftoppm", "-r", "400", "-gray", "-png", "-singlefile", "-f", str(pagina),
                                    "-l", str(pagina), str(documento), str(imagen)], capture_output=True)
            if hecho.returncode != 0 or not imagen.with_suffix(".png").exists():
                break
            leido = subprocess.run(["tesseract", str(imagen.with_suffix(".png")), "-", "-l", "spa", "--psm", "4"],
                                   capture_output=True, text=True)
            partes.append(leido.stdout)
    resultado = "\f".join(partes)
    guardado.write_text(resultado)
    return resultado


def vocabulario(nombres: set[str]) -> dict[str, str]:
    """Known subjects by their comparison key: the key a line is matched on,
    the name it is written as."""
    conocidas: dict[str, str] = {}
    for nombre in nombres:
        clave = comparison_key(nombre)
        if len(clave) >= 5 and len(clave.split()) <= 12:
            conocidas.setdefault(clave, nombre)
    return conocidas


def _candidata(linea: str) -> str:
    candidata = clean_text(re.sub(r"\s{2,}", " ", _RESTO.sub(" ", linea))).strip(" .,;:-–()")
    # The row's format after the name: "Física I A" (asignatura), "... T" (taller).
    return re.sub(r"(?<=\S)\s+(?:A|T|P|PPS|ECE)$", "", candidata)


def _parece_un_nombre(candidata: str) -> bool:
    palabras = candidata.split()
    letras = sum(ch.isalpha() for ch in candidata)
    return 1 <= len(palabras) <= 10 and letras >= 5 and letras >= 0.7 * len(candidata.replace(" ", ""))


def _periodo(linea: str) -> tuple[str, int] | None:
    """("anio", 2) for "Segundo año", ("cuatrimestre", 3) for "TERCER CUATRIMESTRE"."""
    rotulo = _ANIO_EN_LA_LINEA.match(linea)
    if rotulo and anio_de(rotulo.group(1)) and len(linea.split()) <= 6:
        return "anio", anio_de(rotulo.group(1))
    cuatrimestre = _CUATRIMESTRE_EN_LA_LINEA.search(linea)
    if cuatrimestre and len(linea.split()) <= 6:
        palabra = cuatrimestre.group(1).lower().rstrip("°º ").strip()
        numero = int(palabra) if palabra.isdigit() else _ORDINALES.get(palabra)
        if numero:
            return "cuatrimestre", numero
    return None


def plan_escaneado(texto_leido: str, conocidas: dict[str, str]) -> list[tuple[str, int]]:
    """The plan the text gives in known subjects, or nothing when a year or
    term heading is missing (its subjects would go to the wrong year) or more
    than `FALTANTES` of the rows under them are no known subject."""
    from rapidfuzz import fuzz, process

    claves = list(conocidas)
    materias: list[tuple[str, int]] = []
    periodos: list[tuple[str, int]] = []
    faltantes = 0
    anio = None
    for linea in texto_leido.splitlines():
        linea = clean_text(linea)
        if not linea:
            continue
        periodo = _periodo(linea)
        if periodo:
            periodos.append(periodo)
            anio = periodo[1] if periodo[0] == "anio" else (periodo[1] + 1) // 2
            continue
        if anio is None:
            continue
        candidata = _candidata(linea)
        hallada = _parece_un_nombre(candidata) and process.extractOne(
            comparison_key(candidata), claves, scorer=fuzz.ratio, score_cutoff=PARECIDO)
        if hallada:
            nombre = conocidas[hallada[0]]
            if (nombre, anio) not in materias:
                materias.append((nombre, anio))
        elif _parece_un_nombre(candidata) or _FILA_CON_CODIGO.match(linea):
            faltantes += 1
    # The headings must follow one another: one lost, and what follows it is
    # counted in the year before.
    tipos = {tipo for tipo, _ in periodos}
    numeros = [numero for _, numero in periodos]
    if len(tipos) != 1 or numeros != list(range(1, len(numeros) + 1)):
        return []
    if not materias or faltantes > FALTANTES * (len(materias) + faltantes):
        return []
    return desde_el_primero(materias)
