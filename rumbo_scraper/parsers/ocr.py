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


def texto_de_imagen(contenido: bytes) -> str:
    """The text of a picture (a plan's brochure), read by tesseract in
    Spanish word by word with each word's place, laid out column by column:
    a line's words split where a wide gap parts them, the pieces gathered
    into columns by where they start, each column read top to bottom, so a
    name wrapped over two lines of its column stays whole. The strokes a
    Roman numeral comes out as after a word ("Matemática ll", "Contables |!",
    "Electiva 11", "Siglos XV-XVI!") are written as the numeral; a piece of fewer than three
    letters (the stray marks a table's column letters come out as) is
    dropped. A table whose cells are centred is read again by the centres of
    its pieces. A small picture is read again at twice its size, laid on white
    (a transparent background reads as black once enlarged), its two readings
    one after the other: each loses lines the other keeps. Empty when it
    cannot be read."""
    lecturas = [_lectura(contenido), _lectura(contenido, "centro")]
    try:
        from io import BytesIO

        from PIL import Image
        dibujo = Image.open(BytesIO(contenido)).convert("RGBA")
        if dibujo.width < 2000:
            fondo = Image.new("RGB", dibujo.size, "white")
            fondo.paste(dibujo, mask=dibujo)
            salida = BytesIO()
            fondo.resize((fondo.width * 2, fondo.height * 2), Image.LANCZOS).save(salida, "PNG")
            lecturas += [_lectura(salida.getvalue()), _lectura(salida.getvalue(), "centro")]
    except Exception:
        pass
    return "\n".join(lectura for lectura in lecturas if lectura)


def _lectura(contenido: bytes, por: str = "inicio") -> str:
    """One reading of a picture by tesseract, laid out column by column (see
    ``texto_de_imagen``): the columns told by where the pieces start, or, for
    a table whose cells are centred, by where their centres are (``por``)."""
    with tempfile.TemporaryDirectory() as carpeta:
        imagen = Path(carpeta) / "imagen.png"
        imagen.write_bytes(contenido)
        try:
            tsv = subprocess.run(["tesseract", str(imagen), "-", "-l", "spa", "tsv"], capture_output=True,
                                 text=True, timeout=120).stdout
        except (subprocess.SubprocessError, OSError):
            return ""
    palabras = []
    for fila in tsv.splitlines()[1:]:
        campos = fila.split("\t")
        if len(campos) == 12 and campos[11].strip() and campos[10] not in ("-1",):
            palabras.append({"linea": tuple(campos[2:5]), "x": int(campos[6]), "y": int(campos[7]),
                             "ancho": int(campos[8]), "alto": int(campos[9]), "texto": campos[11]})
    if not palabras:
        return ""
    altos = sorted(p["alto"] for p in palabras)
    hueco = 3 * altos[len(altos) // 2]
    # A line's pieces: its words, cut where a gap wider than three letters' height parts them.
    piezas: list[dict] = []
    por_linea: dict[tuple, list[dict]] = {}
    for palabra in palabras:
        por_linea.setdefault(palabra["linea"], []).append(palabra)
    for linea in por_linea.values():
        linea.sort(key=lambda p: p["x"])
        actual = [linea[0]]
        for palabra in linea[1:]:
            if palabra["x"] - (actual[-1]["x"] + actual[-1]["ancho"]) > hueco:
                piezas.append(actual)
                actual = []
            actual.append(palabra)
        piezas.append(actual)
    # The columns: the pieces' starts, a new column where they jump right.
    ancho = max(p["x"] + p["ancho"] for p in palabras)
    def lugar(pieza: list[dict]) -> int:
        if por == "centro":
            return (pieza[0]["x"] + pieza[-1]["x"] + pieza[-1]["ancho"]) // 2
        return pieza[0]["x"]

    comienzos = sorted({lugar(pieza) for pieza in piezas})
    cortes = [b for a, b in zip(comienzos, comienzos[1:]) if b - a > ancho * (0.08 if por == "centro" else 0.15)]
    columnas: dict[int, list[list[dict]]] = {}
    for pieza in piezas:
        columna = sum(1 for corte in cortes if lugar(pieza) >= corte)
        columnas.setdefault(columna, []).append(pieza)
    renglones = []
    for columna in sorted(columnas):
        for pieza in sorted(columnas[columna], key=lambda p: p[0]["y"]):
            renglon = " ".join(p["texto"] for p in pieza)
            if len(re.findall(r"[a-záéíóúñ]", renglon, re.I)) >= 3 or re.fullmatch(r"[IVX]+|\d+", renglon):
                renglones.append(renglon)
    return _numerales("\n".join(renglones))


def _numerales(texto: str) -> str:
    """The strokes a Roman numeral comes out as, written as the numeral."""
    texto = re.sub(r"(?<=[a-záéíóúñA-ZÁÉÍÓÚÑ]) ([|lI!1]{1,3})(?=[\s,.;:*)]|$)",
                   lambda m: " " + "I" * len(m.group(1)), texto)
    # The same strokes ending a numeral ("Siglos XV-XVI!", "XVI!|-XIX"), and
    # "1er" read as "ler".
    texto = re.sub(r"(?<=\b[XV])([XVI]*)([|l!1]{1,3})(?=[\s,.;:*)-]|$)",
                   lambda m: m.group(1) + "I" * len(m.group(2)), texto)
    return re.sub(r"\bler\b", "1er", texto)


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
