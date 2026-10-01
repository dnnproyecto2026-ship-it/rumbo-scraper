"""The USAL's plans, read from the brochure image each career page shows.

The Universidad del Salvador publishes no plan as text: under "PLAN DE
ESTUDIOS" each career page shows a brochure (``Folleto…-01.png``) with the
subjects in two columns, each year headed "PRIMER AÑO", "SEGUNDO AÑO"…, and a
letter beside each subject for how long it runs (A: anual, C:
cuatrimestral). Tesseract reads the words well, but read as text the two
columns interleave ("PRIMER AÑO CUARTO AÑO") and the Roman numerals come out
as strokes ("Arquitectura lI!", "Tecnología Digital 111").

So the brochure is read word by word with each word's position
(``tesseract … tsv``): a word belongs to the left column if it starts before
the right column's first year heading, and the lines of each column are
read top to bottom. A line is a year heading, a subject, or noise: the
letters of the duration, the legend ("A: Anual - C: Cuatrimestral") and the
degree's name drawn at the bottom are not subjects. A name wrapped over two
lines ends on a connecting word ("Seminario de Interpretación y") and is
joined to the next.

A trailing group of strokes is a Roman numeral: "|", "l", "!", "1" are "I"
("lI!" is "III", "VI!" is "VII"). Since a stroke can be lost ("Historia y
Teoría de la Arquitectura Il" in third year, after I and II in second), a
series that comes out with a number twice or a gap is numbered again in
the order the brochure lists it, which is the order it is taken: I, II,
III. A series with a name in it twice after that is not read.

The plan is kept only if it has every year from the first and at least
fifteen subjects: a brochure that reads worse than that is skipped, never
guessed.
"""

from __future__ import annotations

import csv
import io
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.parsers.planes_sitios import anio_de, desde_el_primero

MINIMO = 15
_CONECTORES = {"y", "e", "de", "del", "la", "las", "los", "el", "en", "a", "para", "con", "o"}
_TRAZOS = "|l!1Iíi"
_ROMANO = re.compile(r"^(?:[VX]?[" + re.escape(_TRAZOS) + r"]{1,4}|[VX]|I?[VX]|[" + re.escape(_TRAZOS) + r"]?[VX][" + re.escape(_TRAZOS) + r"]{0,3})$")
_ORDINAL = re.compile(r"(?i)^(?:primer|primero|segundo|tercer|tercero|cuarto|quinto|sexto)$")
_RUIDO = re.compile(r"(?i)^(?:[ac€e¡¿|!.\-–—•·\s]{1,4}|.*\banual\b.*\bcuatrimestral\b.*"
                    r"|.*resoluci[oó]n.*|.*coneau.*|usal|universidad del salvador.*"
                    r"|(?:\w:\s*)?(?:semanal|cuatrimestral|anual|bimestral)"
                    r"|(?:licenciad[oa]|t[ée]cnic[oa]|traductor[a]?|profesor[a]?)(?:/[oa])?\s+(?:en|de|p[úu]blico|universitari).*)$")
# What is left of the OCR in a name that should have none: a plan with any
# such name is not taken (a brochure in three columns glues two subjects
# with the duration's letter between them).
_ES_PROSA = re.compile(r"(?i)^además\b|deber[áa]s|obligaciones acad[eé]micas|requisitos? de egreso")
_RESTOS = re.compile(r"[|!¡€\[\]_]|\d(?!D\b)")


def leer(imagen: Path) -> str:
    """Tesseract's words with their boxes, as TSV."""
    resultado = subprocess.run(["tesseract", str(imagen), "-", "-l", "spa", "--psm", "4", "tsv"],
                               capture_output=True, text=True, check=False)
    return resultado.stdout


def _palabras(tsv: str) -> list[dict]:
    filas = csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
    return [f for f in filas if f.get("level") == "5" and (f.get("text") or "").strip()]


def _lineas(palabras: list[dict]) -> list[str]:
    """Each column's lines, the left column first, top to bottom."""
    if not palabras:
        return []
    clave = lambda p: (p["block_num"], p["par_num"], p["line_num"])  # noqa: E731
    por_linea: dict[tuple, list[dict]] = defaultdict(list)
    for p in palabras:
        por_linea[clave(p)].append(p)
    lineas = [sorted(ps, key=lambda p: int(p["left"])) for ps in por_linea.values()]
    # The right column starts where its year headings do: the ordinal words
    # ("CUARTO", "QUINTO") that start furthest right. Tesseract may read two
    # headings side by side as one line ("PRIMER AÑO CUARTO AÑO"), so the
    # words are looked at, not the lines.
    ancho = max(int(p["left"]) + int(p["width"]) for p in palabras)
    ordinales = sorted(int(p["left"]) for p in palabras if _ORDINAL.match(p["text"]))
    derecha = [x for x in ordinales if x > ancho * 0.35]
    corte = min(derecha) - 20 if derecha and any(x <= ancho * 0.35 for x in ordinales) else ancho
    columnas: list[list[tuple[int, str]]] = [[], []]
    for ps in lineas:
        for lado in (0, 1):
            suyas = [p for p in ps if (int(p["left"]) < corte) == (lado == 0)]
            if suyas:
                columnas[lado].append((min(int(p["top"]) for p in suyas), " ".join(p["text"] for p in suyas)))
    return [texto for columna in columnas for _, texto in sorted(columna)]


def _romano(ficha: str) -> str | None:
    if not _ROMANO.match(ficha) or not any(c in ficha for c in _TRAZOS + "VX"):
        return None
    romano = "".join("I" if c in _TRAZOS else c for c in ficha)
    return "IV" if romano == "IIII" else romano


_DURACION_AL_FINAL = re.compile(r"\s+(?:[ACac€e¡\[_]{1,2}[aceACE]?|al|el|Cuatrimestral|Anual|_)$")


def _sin_duracion(linea: str) -> str:
    """The duration's letter, read on either side of the name: "C", "Cc",
    "€", "¡a", "[a", "_C", and "al", "el" (a letter and a stroke beside it:
    no subject's name ends on "al" or "el")."""
    linea = re.sub(r"^(?:[ACac€e¡\[_]{1,2}\s+)(?=[A-ZÁÉÍÓÚÑ])", "", linea.strip())
    anterior = None
    while anterior != linea:
        anterior, linea = linea, _DURACION_AL_FINAL.sub("", linea).rstrip("_ ")
    return linea.strip(" .:;")


def _numerar(materias: list[tuple[str, str | None, int]]) -> list[tuple[str, int]] | None:
    """Number each series again in the brochure's order when the strokes
    came out with a number twice or a gap."""
    series: dict[str, list[int]] = defaultdict(list)
    for i, (base, numero, _) in enumerate(materias):
        if numero:
            series[comparison_key(base)].append(i)
    nuevos: dict[int, str] = {}
    for indices in series.values():
        numeros = [materias[i][1] for i in indices]
        esperados = [_a_romano(n) for n in range(1, len(indices) + 1)]
        # One subject of a series keeps its number ("Plástica II" follows
        # "Plástica y Visión I"); a series renumbers only when it repeats a
        # number or skips one.
        sano = len(set(numeros)) == len(numeros) and sorted(numeros, key=_de_romano) == numeros
        nuevos.update({i: n for i, n in zip(indices, numeros if len(indices) == 1 or sano else esperados)})
    salida: list[tuple[str, int]] = []
    vistas: set[str] = set()
    for i, (base, numero, anio) in enumerate(materias):
        nombre = f"{base} {nuevos[i]}" if i in nuevos else base
        if comparison_key(nombre) in vistas:
            return None
        vistas.add(comparison_key(nombre))
        salida.append((nombre, anio))
    return salida


def _de_romano(romano: str) -> int:
    valores = {"I": 1, "V": 5, "X": 10}
    total = 0
    for i, c in enumerate(romano):
        v = valores.get(c, 0)
        total += -v if i + 1 < len(romano) and valores.get(romano[i + 1], 0) > v else v
    return total


def _a_romano(n: int) -> str:
    return {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X"}[n]


def plan_del_folleto(tsv: str, carrera: str = "") -> list[tuple[str, int]]:
    anio: int | None = None
    materias: list[tuple[str, str | None, int]] = []
    pendiente = ""
    for linea in _lineas(_palabras(tsv)):
        linea = clean_text(linea).strip()
        nuevo = anio_de(linea)
        if nuevo and len(linea) < 25:
            anio, pendiente = nuevo, ""
            continue
        if anio is None or _RUIDO.match(linea):
            continue
        # The brochure's footer ends the plan: "Además de las obligaciones
        # académicas, deberás…", then the degree's name drawn large.
        if _ES_PROSA.search(linea):
            break
        abre = linea.rstrip().endswith(":")
        linea = _sin_duracion(linea)
        if _RUIDO.match(linea):
            continue
        if pendiente:
            linea, pendiente = f"{pendiente} {linea}", ""
        fichas = linea.split()
        if not fichas or len(linea) < 4:
            continue
        if fichas[-1].lower() in _CONECTORES or abre:
            # "Proyecto de Título:" over "Arquitectura, Ciudad y Territorio"
            # is one subject, as is "Seminario de Interpretación y" over the
            # line below.
            pendiente = linea + (":" if abre else "")
            continue
        numero = _romano(fichas[-1]) if len(fichas) > 1 else None
        base = " ".join(fichas[:-1]) if numero else linea
        # A name has words, not strokes: "Arq U Iitecto" (the degree drawn
        # at the bottom) has a word of one letter in the middle.
        sueltas = [f for f in base.split() if len(f) == 1 and f.lower() not in ("y", "e", "o", "a")]
        # A word cut in two ("Ind ustrial") leaves a piece that starts in
        # lower case and is no connecting word.
        partidas = [f for f in base.split()[1:] if f[0].islower() and f.lower() not in _CONECTORES
                    and len(f) > 3 and not re.match(r"^[a-záéíóúñ]+$", f) is None and f.lower() == f
                    and f.lower().startswith(("ustri", "strial", "ción", "cion"))]
        if not re.match(r"^[A-ZÁÉÍÓÚÑ]", base) or sueltas or partidas or all(len(f) <= 2 for f in base.split()):
            continue
        materias.append((base, numero, anio))
    # The degree's name, drawn large under the last year ("Licenciado/a en
    # Arte Dramático"), comes out as a word of the career's name.
    raices = {comparison_key(p)[:5] for p in carrera.split() if len(p) > 3}
    while materias and len(materias[-1][0].split()) <= 2 and not materias[-1][1] and all(
            comparison_key(p)[:5] in raices or len(p) <= 3 for p in materias[-1][0].split()):
        materias.pop()
    numeradas = _numerar(materias)
    if not numeradas or len(numeradas) < MINIMO:
        return []
    if any(_RESTOS.search(nombre) or len(nombre) > 90 for nombre, _ in numeradas):
        return []
    return desde_el_primero(numeradas)
