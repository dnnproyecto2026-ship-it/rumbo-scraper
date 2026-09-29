"""The degree, duration and modality a postgraduate programme's page states.

A postgraduate page says its degree the way a grado page does, as a label
("Título: Magíster en Finanzas", "Título que otorga: Especialista en ...")
or in a sentence ("obtendrás el título de Doctor/a en ..."); only the
degree words differ. The degree is kept only if it is this programme's:
most of the words of its subject have to be there, because a faculty's page
of one master's often names its sister specialisation's degree too.

Duration and modality are read from the page's labelled facts
(`generico.leer_datos`), as for any programme.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.parsers import generico
from rumbo_scraper.parsers.titulo import _FRASE

# Where the line stops saying the degree. Unlike a grado degree's, a comma is
# not cut here: "Especialista en Divulgación de la Ciencia, la Tecnología y
# la Innovación" is one name.
_CORTE = re.compile(r"\s*(?:[.;]\s|\.$|\(|\s[-–]\s|\s\|\s|\s+con\s+validez|\s+duraci[óo]n\b|"
                    r"\s+reconocimiento\b|\s+res(?:oluci[óo]n)?\.?\s)")

_UN_TITULO = re.compile(r"(?i)^(?:mag[íi]ster|m[áa]ster|especialista|doctor(?:a|/a|\(a\))?)\s+(?:en|de)\s+\S")
_TIPO = re.compile(r"(?i)^(?:carrera de\s+)?(?:doctorado|maestr[íi]a|mag[íi]ster|m[áa]ster|especializaci[óo]n)"
                   r"\s+(?:en|de|del)\s+")
_VACIAS = frozenset("para como desde sobre entre hacia orientacion mencion".split())


def _palabras(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-z]{4,}", comparison_key(texto)) if p not in _VACIAS}


def limpio(texto: str) -> str | None:
    """The degree as a name: cut where the line goes on, and not shouted."""
    from rumbo_scraper.parsers.posgrados_listas import _titulo

    texto = _CORTE.split(clean_text(texto), maxsplit=1)[0]
    # What the sentence goes on to say: ", se despliegan a lo largo de...",
    # " expedido por la Universidad", ".: Requisitos a cumplir".
    # A comma that goes on with the list of the name ("la Ciencia, la
    # Tecnología y la Innovación", ", mención ...") stays.
    # A colon stays when the name goes on after it ("Lenguas Extranjeras:
    # Problemáticas Sociodidácticas"), and cuts where a sentence starts
    # ("Especialista en Neurociencias: Requisitos a cumplir para...").
    texto = re.split(r"\.\s*:|:\s+(?=\S+\s+[a-záéíóúñ])|,\s+(?!(?:(?:el|la|los|las|y|e)\s+)?[A-ZÁÉÍÓÚÑ]|(?:con\s+)?orientaci[óo]n|menci[óo]n)|"
                     r"\s+(?:expedido|otorgado|emitido)\b", texto, maxsplit=1)[0].strip(" .:;,-–\"'“”")
    if not _UN_TITULO.match(texto) or len(texto) > 120 or len(texto.split()) > 18:
        return None
    # "Magister en Gestión del": the line broke before the subject ended.
    if re.search(r"(?i)\s(?:en|de|del|la|el|los|las|y|e|o|con|para|menci[óo]n)$", texto):
        return None
    if texto.isupper():
        texto = _titulo(texto)
    return texto[0].upper() + texto[1:]


def _lineas(html: str) -> list[str]:
    """The page's lines of content, a label joined to the value under it.

    Menus, header and footer go; a <form> stays, because an ASP.NET site
    wraps the whole page in one. A table's rows become "Header: cell" lines,
    so a table of "Título | Duración" reads like labelled fields.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup.find_all(["nav", "header", "footer", "script", "style", "noscript"]):
        parte.decompose()
    for tabla in soup.find_all("table"):
        filas = tabla.find_all("tr")
        encabezados = [clean_text(c.get_text(" ", strip=True)) for c in filas[0].find_all(["th", "td"])] \
            if filas else []
        lineas = []
        for fila in filas[1:]:
            celdas = [clean_text(c.get_text(" ", strip=True)) for c in fila.find_all(["th", "td"])]
            if len(celdas) == len(encabezados):
                lineas += [f"{e}: {v}" for e, v in zip(encabezados, celdas) if e and v]
        if lineas:
            tabla.replace_with(soup.new_string("\n" + "\n".join(lineas) + "\n"))
    texto = (soup.body or soup).get_text("\n")
    # "Título de Posgrado" as a heading, the degree in the next element.
    texto = re.sub(r"(?im)^(\s*(?:t[íi]tulos?|duraci[óo]n|modalidad|grado\s+(?:acad[ée]mico\s+)?otorgado)"
                   r"[^:\n]{0,40}):?\s*\n+\s*", r"\1: ", texto)
    # "Título con reconocimiento oficial y validez nacional que otorga:" and,
    # on the next line, the degree.
    texto = re.sub(r"(?im)^(\s*[^\n]{0,90}\b(?:t[íi]tulo|otorga)[^\n]{0,90}:)\s*\n+\s*", r"\1 ", texto)
    return [clean_text(l) for l in texto.split("\n") if clean_text(l)]


_ROTULO_DE_TITULO = re.compile(
    r"(?i)(?:^t[íi]tulos?(?:\s+[^:]{0,40})?|^grado\s+(?:acad[ée]mico\s+)?otorgado|"
    r"\b(?:t[íi]tulo|otorga)[^:]{0,90}):\s*(.+)")
# "... otorga validez al título de Magíster en Historia Contemporánea."
_EN_UNA_FRASE = re.compile(r"(?i)\bt[íi]tulo\s+de\s+((?:mag[íi]ster|m[áa]ster|especialista|doctor)\b.+)")
_ROTULO_DE_DURACION = re.compile(r"(?i)^duraci[óo]n(?:\s+[^:]{0,40})?:\s*(.+)")
_ROTULO_DE_MODALIDAD = re.compile(r"(?i)^modalidad(?:\s+[^:]{0,40})?:\s*(.+)")


def es_suyo(titulo: str, programa: str) -> bool:
    """Whether the degree names most of the programme's subject."""
    tema = _palabras(_TIPO.sub("", programa))
    return bool(tema) and len(_palabras(titulo) & tema) * 2 >= len(tema)


def titulo_de_posgrado(lineas: list[str], programa: str) -> str | None:
    """The one postgraduate degree the page gives that is this programme's."""
    hallados: dict[str, str] = {}
    for linea in lineas:
        for patron in (_ROTULO_DE_TITULO, _FRASE, _EN_UNA_FRASE):
            for match in patron.finditer(linea):
                titulo = limpio(match.group(1))
                if titulo:
                    hallados.setdefault(comparison_key(titulo), titulo)
    propios = [t for t in hallados.values() if es_suyo(t, programa)]
    return propios[0] if len(propios) == 1 else None


def _primero(lineas: list[str], patron: re.Pattern, leer) -> object:
    for linea in lineas:
        match = patron.match(linea)
        if match and (valor := leer(match.group(1))) is not None:
            return valor
    return None


def nombra_el_programa(html: str, programa: str) -> bool:
    """Whether the page's content writes the programme's name."""
    return comparison_key(programa) in comparison_key(" ".join(_lineas(html)))


def minimo_de_meses(programa: str) -> int:
    """The fewest months a programme of its kind can last: a doctorate is not
    done in a year, nor a master's in a semester."""
    clave = comparison_key(programa)
    if clave.startswith("doctorado"):
        return 24
    if re.match(r"(?:maestria|magister|master|mba)\b", clave):
        return 12
    return 6


# The degree word each kind of programme gives, as a site writes it.
_GRADO_DEL_TIPO = (
    (re.compile(r"(?:carrera de )?doctorado\b"), r"doctor(?:/a|a|\(a\))?"),
    (re.compile(r"(?:maestria|magister|master)\b"), r"mag[ií]ster|m[aá]ster"),
    (re.compile(r"(?:carrera de )?especializacion\b"), r"especialista"),
)
_TILDES = {"a": "aáà", "e": "eéè", "i": "iíì", "o": "oóò", "u": "uúùü", "n": "nñ"}


def _sin_tildes(palabra: str) -> str:
    """A pattern for a word however its accents are written."""
    return "".join(f"[{_TILDES[c]}]" if c in _TILDES else re.escape(c) for c in comparison_key(palabra))


def titulo_mencionado(lineas: list[str], programa: str) -> str | None:
    """The degree, when a line writes its word before the programme's own
    subject and the subject ends there: "MAGISTER EN DERECHO DEL TRABAJO" in
    the plan of the Maestría en Derecho del Trabajo. Nothing of the name is
    guessed: the subject is the programme's, the degree word the text's. A
    subject that goes on ("Magíster en Ingeniería Química") is another's."""
    clave = comparison_key(programa)
    tema = _TIPO.sub("", programa).strip()
    grado = next((g for patron, g in _GRADO_DEL_TIPO if patron.match(clave)), None)
    if not grado or len(tema) < 4 or tema == programa:
        return None
    patron = re.compile(r"(?i)(?<![\w])(" + grado + r")\s+(?:en|de)\s+" +
                        r"\s+".join(_sin_tildes(w) for w in comparison_key(tema).split()) +
                        r"(?=\s*$|\s*[.,;:()\"“”«»\-–|])")
    for linea in lineas:
        match = patron.search(linea)
        if match:
            palabra = match.group(1)
            palabra = palabra.capitalize() if palabra.isupper() else palabra[:1].upper() + palabra[1:]
            return f"{palabra} en {tema}"
    return None


_NUMEROS = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
            "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "dieciocho": 18,
            "veinte": 20, "veinticuatro": 24, "treinta": 30, "treinta y seis": 36}
_CANTIDAD = r"(\d+(?:[.,]\d)?|treinta y seis|" + "|".join(sorted(_NUMEROS, key=len, reverse=True)) + r")"
_UNIDAD = r"(a[ñn]os?|cuatrimestres?|semestres?|meses)"
_DURACION_EN_FRASE = (
    re.compile(r"(?i)\bduraci[óo]n\b[^.;\n]{0,40}?\b" + _CANTIDAD + r"\s*(?:\([^)]{1,15}\)\s*)?" + _UNIDAD + r"\b"),
    re.compile(r"(?i)\b" + _CANTIDAD + r"\s*(?:\([^)]{1,15}\)\s*)?" + _UNIDAD + r"\s+de\s+duraci[óo]n\b"),
    re.compile(r"(?i)\b(?:se\s+cursa|se\s+desarrolla|se\s+dicta|se\s+extiende)\s+(?:en|a\s+lo\s+largo\s+de|durante)\s+"
               + _CANTIDAD + r"\s*(?:\([^)]{1,15}\)\s*)?" + _UNIDAD + r"\b"),
)
# What the degree the applicant already holds lasts is not the programme's:
# "título de grado universitario de 4 años de duración".
_OTRA_DURACION = re.compile(r"(?i)t[íi]tulo|grado|requisit|admisi|ingres|aspirante|postula|egresad|"
                            r"carrera de|licenciatura|plazo|tesis|beca|prórroga|prorroga|vigencia|"
                            r"como\s+m[íi]nimo|al\s+menos|no\s+menor|m[íi]nimo\s+de|mayores\s+de|o\s+m[áa]s\b|\bhoras\b")


def _meses(cantidad: str, unidad: str) -> int | None:
    clave = comparison_key(cantidad)
    numero = _NUMEROS.get(clave)
    if numero is None:
        try:
            numero = float(cantidad.replace(",", "."))
        except ValueError:
            return None
    unidad = comparison_key(unidad)
    por = 12 if unidad.startswith("ano") else 6 if unidad.startswith(("cuatri", "semes")) else 1
    return round(numero * por)


def _maximo_de_meses(programa: str) -> int:
    """The most months a sentence may give: a master's of four years or a
    specialisation of five is a line about something else."""
    clave = comparison_key(programa)
    if clave.startswith("doctorado"):
        return 72
    if re.match(r"(?:maestria|magister|master|mba)\b", clave):
        return 36
    return 48


def duracion_mencionada(lineas: list[str], programa: str) -> int | None:
    """The months a sentence gives the programme ("tiene una duración de dos
    años", "cuatro cuatrimestres de duración", "se cursa en 18 meses"), when
    the page gives one value only and not about another degree."""
    halladas = set()
    for i, linea in enumerate(lineas):
        # A requirement broken over two lines: "título de grado de" and, on
        # the next, "cuatro (4) años de duración como mínimo".
        antes = lineas[i - 1][-60:] if i else ""
        despues = lineas[i + 1][:40] if i + 1 < len(lineas) else ""
        # ... and "al" / "menos cuatro (4) años de duración".
        if _OTRA_DURACION.search(linea) or _OTRA_DURACION.search(antes) \
                or re.match(r"(?i)\s*m[íi]nimo", despues) \
                or re.match(r"(?i)\s*(?:menos|m[íi]nimo|m[áa]s)\b", linea):
            continue
        for patron in _DURACION_EN_FRASE:
            for match in patron.finditer(linea):
                meses = _meses(match.group(1), match.group(2))
                if meses and minimo_de_meses(programa) <= meses <= _maximo_de_meses(programa):
                    halladas.add(meses)
    return halladas.pop() if len(halladas) == 1 else None


def datos_de_posgrado(html: str, programa: str) -> dict[str, object]:
    """What the page says of the programme: degree, months, modality."""
    lineas = _lineas(html)
    meses = _primero(lineas, _ROTULO_DE_DURACION, generico.duracion_meses)
    if not meses or not minimo_de_meses(programa) <= meses <= 72:
        meses = duracion_mencionada(lineas, programa)
    return {
        "titulo_otorgado": titulo_de_posgrado(lineas, programa),
        "duracion_meses": meses if meses and minimo_de_meses(programa) <= meses <= 72 else None,
        "modalidad": _primero(lineas, _ROTULO_DE_MODALIDAD, generico.modalidad),
    }


# ------------------------------------------------------------- the plan

# The heading a postgraduate's page puts over the list of what it teaches.
_ENCABEZADO_DEL_PLAN = re.compile(
    r"(?i)^(?:el\s+)?(?:plan\s+de\s+estudios?|estructura\s+curricular|asignaturas|materias|"
    r"cursos\s+obligatorios|m[óo]dulos|actividades\s+curriculares|espacios\s+curriculares|"
    r"seminarios\s+obligatorios|malla\s+curricular)\s*:?$")
# What stands between the heading and the subjects, or between two blocks:
# "Módulo 1", "Ciclo de formación básica", "Primer año:", "Horas: 30".
_ANDAMIO = re.compile(
    r"(?i)^(?:m[óo]dulo|ciclo|bloque|eje|[áa]rea|tramo|n[úu]cleo|primer|segundo|tercer|cuarto|"
    r"\d+[°º]?\s*(?:a[ñn]o|cuatrimestre|semestre)|cuatrimestre|semestre|a[ñn]o)\b[^.]{0,50}:?$|"
    r"^(?:horas|carga\s+horaria|cr[ée]ditos|uvacs?)\b[^a-z]{0,20}\d")
_VIÑETA = re.compile(r"^[\s•·\-–—*▪►◦○»]+|^\d{1,2}\s*[.)\-–]\s+")
# What es_materia lets through and a plan never lists: the page's buttons,
# its paperwork, and anything asked or dated.
_NO_ES_ASIGNATURA = re.compile(
    r"(?i)^(?:m[áa]s\s+info|ver\s+m[áa]s|leer\s+m[áa]s|admisi[óo]n|inscrib|inscripci|eventos?|contacto|"
    r"descarg|consult|requisitos|aranceles?|becas|noticias|cronograma|calendario|reglamento|"
    r"resoluci[óo]n|dictamen|acta|disposici|ordenanza|autoridades|direcci[óo]n|coordinaci[óo]n|"
    r"cuerpo\s+docente|docentes|comit[ée]|perfil|objetivos|destinatarios|t[íi]tulo|duraci[óo]n|"
    r"modalidad|sede|horarios?|presentaci[óo]n|fundamentaci[óo]n|campo\s+laboral|alcances|"
    r"tutorial|formulario|modelo\s+de|inicio|home)\b|\?|\d{1,2}\s+de\s+[a-z]+\s+de\s+\d{4}")


# A list that holds any of these is a form, the site's accessibility menu or
# the programme's research lines, not its plan: the whole list goes.
_NO_ES_UN_PLAN = re.compile(
    r"(?i)^(?:nombre|apellido|tel[ée]fono|e-?mail|correo|mensaje|enviar|provincia|pa[íi]s|"
    r"contraste|texto|enlaces|equipo|cursor|tama[ñn]o)\b|solicit|quiero\s+recibir|please|field|"
    r"preinscripci|l[íi]neas\s+de\s+investigaci|[áa]reas\s+estrat[ée]gicas|[áa]reas\s+tem[áa]ticas|"
    r"^\+\s*info|carta\s+del?|intercambio\s+con|^(?:doctorado|maestr[íi]a|especializaci[óo]n)\s+en\b|"
    # The campuses and their addresses: "Av. Alicia Moreau de Justo 1300".
    r"^av(?:enida|\.)\s|\(\s*[a-z]?\d{4}[a-z]*\s*\)|\b\d{3,5}\s*,\s*\(")


# "Mediación y Resolución de Conflictos (64 hs.)": a subject with its hours.
_CON_SUS_HORAS = re.compile(r"^(.+?)\s*\(\s*\d{1,3}\s*hs?\.?\s*\)\s*$", re.I)


def plan_economicas_uba(html: str) -> list[str]:
    """UBA Económicas' programme pages: a tab "PLAN DE ESTUDIOS" (Elementor:
    the title and its panel share ``data-tab``) listing each subject with its
    hours; the rest of the tab (accreditation, totals, the degree) has none."""
    soup = BeautifulSoup(html or "", "html.parser")
    titulo = next((t for t in soup.select(".elementor-tab-title") if "plan de estudio" in t.get_text().lower()), None)
    panel = soup.select_one(f'.elementor-tab-content[data-tab="{titulo.get("data-tab")}"]') if titulo else None
    materias: list[str] = []
    for linea in (panel.get_text("\n", strip=True).split("\n") if panel else []):
        encontrada = _CON_SUS_HORAS.match(clean_text(linea))
        if encontrada and encontrada.group(1) not in materias:
            materias.append(re.sub(r"\s+", " ", encontrada.group(1)).strip())
    return materias


def plan_de_posgrado(html: str) -> list[str]:
    """The subjects a postgraduate's page lists under its plan's heading.

    A structured plan is a list under "Plan de estudios" (or "Cursos
    obligatorios", "Módulos"), one subject per line, maybe split by module
    headings and followed by its hours. The list ends at the first line that
    is none of that. A semi-structured plan (most doctorates) describes its
    cycles in prose instead, and gives nothing: that is right, it has no
    fixed subjects. Fewer than four is not a plan; more than forty is the
    reader running into the rest of the page.
    """
    return plan_en_lineas(_lineas(html))


# What a plan's table puts beside each subject in a document: its code before
# it ("A01", "3."), its hours and credits after it ("60 hs", "4 30").
_CODIGO = re.compile(r"^(?:[A-Z]{1,4}\s?\d{1,3}|\d{1,3})\s*[.\-)]?\s+(?=[A-ZÁÉÍÓÚÑ])")
_CARGA = re.compile(r"(?i)(?:\s+\d+(?:[.,]\d+)?\s*(?:hs?\.?|horas|cr[ée]ditos|uvacs?|ects)?)+\s*$")


def plan_en_lineas(lineas: list[str], documento: bool = False) -> list[str]:
    """The subjects listed under a plan's heading in these lines: a page's,
    or, with ``documento``, a plan's PDF, whose table rows carry a code and
    their hours around each subject."""
    from rumbo_scraper.parsers.generico import es_materia

    if documento:
        lineas = [clean_text(_CARGA.sub("", _CODIGO.sub("", linea))) for linea in lineas]
    for inicio, linea in enumerate(lineas):
        if not _ENCABEZADO_DEL_PLAN.match(linea):
            continue
        materias: list[str] = []
        antes = 0
        for siguiente in lineas[inicio + 1:]:
            texto = clean_text(re.sub(r"\s*\(\*+\)$", "", _VIÑETA.sub("", siguiente)))
            texto = re.sub(r"(?i)^(?:cursos?|seminarios?)\s+(?:obligatorios?|electivos?|optativos?)\s*:\s*",
                           "", texto)
            # A block's heading in capitals ("FUNDAMENTOS", "MÓDULOS") or
            # "Actividades curriculares generales" is structure, not a subject.
            if not texto or _ANDAMIO.match(texto) or (texto.isupper() and len(texto.split()) <= 3) \
                    or re.match(r"(?i)^actividades\s+curriculares|^blank$", texto):
                continue
            # A line that starts in lower case goes on from the one before.
            if texto[0].islower():
                if materias:
                    break
                continue
            if es_materia(texto) and not _NO_ES_ASIGNATURA.search(texto):
                if comparison_key(texto) not in {comparison_key(m) for m in materias}:
                    materias.append(texto)
                continue
            if materias:
                break
            antes += 1
            if antes > 3:
                break
        if 4 <= len(materias) <= 40 and not any(_NO_ES_UN_PLAN.search(m) for m in materias):
            return materias
    return []
