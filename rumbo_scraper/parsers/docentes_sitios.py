"""Teaching staff that universities publish as lists, one reader per source.

Each reader takes the page and returns ``[(subject, teacher, role)]``;
`main` groups them by subject into the file `database.cargar_docentes` loads:

- UBA, Psicología: the table of regular professors (Profesor | Cargo |
  Asignatura | Carrera). Emeritus professors hold no chair.
- UTN, Córdoba, Sistemas: a panel per teacher, each subject with its role
  ("Sistemas Operativos (Plan 2023):Adjunto Interino").

    python -m rumbo_scraper.parsers.docentes_sitios UBA
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import defaultdict
from pathlib import Path

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text, comparison_key


def _texto(elemento) -> str:
    return clean_text(elemento.get_text(" ")) if elemento else ""


def psicologia_uba(html: str) -> list[tuple[str, str, str]]:
    filas = []
    for fila in BeautifulSoup(html or "", "html.parser").select("table tr"):
        celdas = [_texto(c) for c in fila.find_all("td")]
        if len(celdas) == 4 and celdas[2] and celdas[0].lower() != "profesor" \
                and not re.match(r"(?i)em[ée]rit", celdas[1]):
            filas.append((celdas[2], celdas[0], celdas[1]))
    return filas


def sistemas_frc(html: str) -> list[tuple[str, str, str]]:
    filas = []
    for encabezado in BeautifulSoup(html or "", "html.parser").select("div.panel-heading.item-search"):
        nombre = _texto(encabezado.find("strong") or encabezado)
        cuerpo = encabezado.find_next("div", class_="panel-body")
        for li in cuerpo.find_all("li") if cuerpo else []:
            materia, _, rol = _texto(li).rpartition(":")
            materia = re.sub(r"\s*\(Plan \d+\)\s*$", "", materia or rol)
            if materia:
                filas.append((materia, nombre, rol if _ else ""))
    return filas


def fau_unt(html: str) -> list[tuple[str, str, str]]:
    """UNT, Arquitectura: a row of one cell names the subject, and the rows
    after it its teachers (APELLIDO | Nombre | Cargo)."""
    filas, materia = [], None
    for fila in BeautifulSoup(html or "", "html.parser").select("table tr"):
        celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
        llenas = [c for c in celdas if c]
        if len(llenas) == 1:
            materia = llenas[0]
        elif len(celdas) >= 3 and materia and celdas[0] and celdas[0].lower() != "apellido":
            filas.append((materia, f"{celdas[0]}, {celdas[1]}", celdas[2]))
    return filas


_ROL_ENTRE_PARENTESIS = re.compile(r"^\(([A-ZÁÉÍÓÚ. ]+)\)\s*(.+)$")


def asignaturas_facet(html: str) -> list[tuple[str, str, str]]:
    """UNT, FACET career sites: AÑO | MÓDULO | ASIGNATURA | ... | DOCENTES,
    the first teacher on the subject's row and the rest on rows of their own
    ("(ADJ) COPA OCAMPO, Marina")."""
    filas, materia, columna = [], None, None
    for fila in BeautifulSoup(html or "", "html.parser").select("table tr"):
        celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
        mayusculas = [c.upper() for c in celdas]
        if "ASIGNATURA" in mayusculas and "DOCENTES" in mayusculas:
            columna = (mayusculas.index("ASIGNATURA"), mayusculas.index("DOCENTES"), len(celdas))
            continue
        if not columna:
            continue
        if len(celdas) == 1:
            docente = celdas[0]
        elif len(celdas) >= 3:
            # The year and module cells span their rows: a subject's row
            # may come without them, its cells shifted to the left.
            corrida = columna[2] - len(celdas)
            if columna[0] - corrida < 0:
                continue
            materia, docente = celdas[columna[0] - corrida], celdas[-1]
        else:
            continue
        rol = _ROL_ENTRE_PARENTESIS.match(docente)
        if materia and rol:
            filas.append((materia, rol.group(2), rol.group(1)))
    return filas


_CARGO_DERECHO = re.compile(r"(?i)^(titular|asociad[oa]|adjunt[oa](?:/a)?|asociad[oa]/a|titular/a|em[ée]rit[oa](?:/a)?|consult[oa](?:/a)?)\s*$")


def derecho_uba(texto: str) -> list[tuple[str, str, str]]:
    """UBA, Derecho: the PDF of its regular professors, as ``pdftotext
    -layout`` gives it: "Asignatura: Derecho Civil", a role ("Titular",
    "Adjunto/a") and the people under it, indented. Emeritus and consulting
    professors hold no chair."""
    filas, materia, rol = [], None, None
    for linea in (texto or "").splitlines():
        limpia = clean_text(linea)
        if not limpia or re.match(r"(?i)^(facultad de derecho|universidad de buenos aires|profesores|- \w+ \d{4} -|\d+)$", limpia):
            continue
        asignatura = re.match(r"(?i)^asignatura:\s*(.+)$", limpia)
        if asignatura:
            materia, rol = asignatura.group(1), None
            continue
        if re.match(r"(?i)^departamento:", limpia):
            continue
        cargo = _CARGO_DERECHO.match(limpia)
        if cargo:
            rol = cargo.group(1)
            continue
        if materia and rol and linea.startswith("  ") and "," in limpia \
                and not re.match(r"(?i)^(em[ée]rit|consult)", rol):
            filas.append((materia, limpia.rstrip("."), rol))
    return filas


def profesores_palermo(html: str) -> list[tuple[str, str, str]]:
    """Palermo, Ciencias Sociales: a fold per teacher, its content opening
    with "Área:" and the subject; a fold without it only has a biography."""
    filas = []
    for titulo in BeautifulSoup(html or "", "html.parser").select("div.acctitle"):
        contenido = titulo.find_next_sibling("div", class_="acc_content")
        lineas = [clean_text(l) for l in (contenido.get_text("\n") if contenido else "").split("\n") if clean_text(l)]
        texto = " ".join(lineas[:2])
        area = re.match(r"(?i)^[áa]rea\s*:\s*(.+?)(?:\.\s|\.$|$)", lineas[0] if lineas else "")
        if not area and lineas and re.match(r"(?i)^[áa]rea\s*:?$", lineas[0]) and len(lineas) > 1:
            area = re.match(r"(.+?)(?:\.\s|\.$|$)", lineas[1])
        nombre = _texto(titulo)
        if area and nombre and len(area.group(1)) < 90 and not re.search(r"(?i)coordinador|director", area.group(1)):
            # "Cognición, Pensamiento y Lenguaje" is one subject and
            # "Evolución de la Sociedad Argentina, Historia Contemporánea"
            # two: a list the page does not tell apart is not taken.
            if "," not in area.group(1):
                filas.append((area.group(1).strip(" ."), nombre, ""))
    return filas


def comisiones_ungs(texto: str) -> list[tuple[str, str, str]]:
    """UNGS: the PDF of a term's commissions, as ``pdftotext -layout`` gives
    it, a row per commission and slot:

        A0574   ADOLESCENCIA Y EDUCACIÓN SECUNDARIA (A0574)   A0574 COM-03   10/08/2026 ...  Jueves  13:00 a 15:59   Sburlatti Santiago Esteban, Toscano Ana Gracia   AULA 7173

    A long name wraps: above the row (the building's column beside it), and
    "(A0075)" below. A subject is its code, named as a row writes it whole
    when one does. The teachers come "Apellido Nombre" without a comma, so
    they are kept as written; the role is the term the dates fall in."""
    nombres: dict[str, str] = {}
    envueltos: dict[str, str] = {}
    completos: set[str] = set()
    docentes_de: dict[str, list[tuple[str, str]]] = {}
    arriba = ""
    for linea in (texto or "").splitlines():
        partes = re.split(r"\s{2,}", linea.strip())
        comision = next((i for i, p in enumerate(partes) if re.match(r"^[A-Z]\d{4} COM-\d+$", p)), None)
        if comision is None or not re.match(r"^[A-Z]\d{4}$", partes[0]):
            primero = clean_text(partes[0]) if partes else ""
            # The rest of a wrapped name, beside its code: "PÚBLICO (A0154)".
            cola = re.match(r"^(.*?)\s*\(([A-Z]\d{4})\)$", primero)
            if cola and cola.group(2) in envueltos and cola.group(2) not in completos:
                envueltos[cola.group(2)] = clean_text(f"{envueltos[cola.group(2)]} {cola.group(1)}")
                completos.add(cola.group(2))
                continue
            if primero and primero.isupper() and not re.match(r"^(\(|MODULO|AULA|SEDE|COMISIONES)", primero) \
                    and not re.search(r"\d", primero):
                arriba = primero
            continue
        codigo = partes[0]
        if comision == 2:
            nombres.setdefault(codigo, re.sub(rf"\s*\({codigo}\)\s*$", "", partes[1]).strip())
        elif arriba:
            envueltos.setdefault(codigo, arriba)
        if len(partes) <= comision + 5:
            continue
        termino = "1° cuatrimestre" if re.match(r"\d\d/0[1-6]/", partes[comision + 1]) else "2° cuatrimestre"
        for docente in partes[comision + 5].split(","):
            docente = clean_text(docente)
            if docente and not re.search(r"\d|AULA|VT ASINC", docente):
                docentes_de.setdefault(codigo, [])
                if (docente, termino) not in docentes_de[codigo]:
                    docentes_de[codigo].append((docente, termino))
    filas = []
    for codigo, docentes in docentes_de.items():
        nombre = nombres.get(codigo) or envueltos.get(codigo)
        # A name the wrap cut at its start leaves its parentheses unbalanced.
        if nombre and nombre.count("(") == nombre.count(")"):
            filas += [(nombre, docente, termino) for docente, termino in docentes]
    return filas


_FILA_FI_MDP = re.compile(r"^(?P<materia>\S.*?)?\s{2,}(?P<codigo>[A-Z0-9-]+)\s+(?P<cuatr>1|2|Ambos)\s+"
                         r"(?P<docente>\S.*?)\s{2,}\S+@\S+\s*$")
# ("ÁLGEBRA A" ends on its letter, not on a preposition.)
_CORTADA = re.compile(r"(?i)\s(de|del|la|las|los|el|y|e|en|con|para|por)$")


def ingenieria_mdp(texto: str) -> list[tuple[str, str, str]]:
    """UNMdP, Ingeniería: "Docentes por Asignaturas", as ``pdftotext -layout``
    gives it: ASIGNATURA | Cód. | Cuatr. | DOCENTE | MAIL, the person in
    charge. A code that wraps leaves the subject's name on the line above;
    a name that wraps goes on in the line below. The mail only marks the row."""
    filas, pendiente = [], None
    lineas = (texto or "").splitlines()
    for posicion, linea in enumerate(lineas):
        encontrada = re.search(r"\s{2,}(?P<codigo>[A-Z0-9-]+)\s+(?P<cuatr>1|2|Ambos)\s+(?P<docente>\S.*?)\s{2,}\S+@\S+\s*$", linea)
        if not encontrada:
            limpia = clean_text(linea)
            if linea[:1].strip() and limpia and not re.search(r"@|ASIGNATURA|NO SE DICTA", limpia):
                # "ÁLGEBRA I-B    4": a subject whose code goes on below.
                pendiente = re.sub(r"\s+\d+$", "", limpia)
            continue
        materia = clean_text(linea[:encontrada.start()])
        if not materia:
            materia, pendiente = pendiente, None
        if not materia:
            continue
        # The rest of a wrapped name, alone on the next line ("TECNOLÓGICA");
        # a rest that comes garbled ("COMPUTADORASDE COMPUTADORAS") leaves
        # the subject out.
        siguiente = lineas[posicion + 1] if posicion + 1 < len(lineas) else ""
        resto = clean_text(siguiente)
        if siguiente[:1].strip() and resto.isupper() and not re.search(r"\d|@", resto) \
                and not re.search(r"\s{2,}\S", siguiente.strip()):
            palabras = re.findall(r"\w+", resto)
            if len(palabras) != len(set(palabras)) or any(p.endswith(("DE", "DEL")) and len(p) > 5 for p in palabras):
                continue
            materia = f"{materia} {resto}"
        if _CORTADA.search(materia):
            continue
        materia = re.sub(r"(?i)\s*\(alias \d+\)$", "", materia)
        termino = {"1": "1° cuatrimestre", "2": "2° cuatrimestre"}.get(encontrada.group("cuatr"), "")
        filas.append((materia, clean_text(encontrada.group("docente")), termino))
    return filas


_CARGO_CATEDRA = re.compile(r"(?i)^(titular|profesor(?:a|es|as)?|jef[ea]s?|ayudantes?|auxiliar(?:es)?|adscript[oa]s?|docentes?)\b[^:]{0,60}:?$")
_NO_ES_PERSONA = re.compile(r"(?i)\b(c[áa]tedra|contacto|informaci[óo]n|aula|programa|horarios?|planta|docente|virtual)\b")
_PERSONA = re.compile(r"^(?:(?:Dr|Dra|Lic|Mg|Ing|Prof|Arq|Biól|Geól|Antr|Mus|Esp)\.\s*)*"
                      r"[A-ZÁÉÍÓÚÑ][a-záéíóúñü]+(?:[ -][A-ZÁÉÍÓÚÑa-záéíóúñü'.]+){1,5}$")


def catedra_fcnym(html: str) -> list[tuple[str, str, str]]:
    """UNLP, Ciencias Naturales y Museo: a page per chair, its title the
    subject and, after the course's data, each role ("Profesor Titular",
    "Profesores Adjuntos") with its people one per line."""
    soup = BeautifulSoup(html or "", "html.parser")
    materia = _texto(soup.find("h1")).replace("\xad", "")
    for parte in soup.find_all(["script", "style", "nav", "header", "footer"]):
        parte.decompose()
    filas, rol = [], None
    for linea in (clean_text(l) for l in soup.get_text("\n").split("\n")):
        if not linea or re.match(r"(?i)^ver cv$", linea):
            continue
        cargo = _CARGO_CATEDRA.match(linea)
        if cargo and len(linea.split()) <= 8:
            rol = linea.rstrip(":")
            continue
        palabras = re.sub(r"^(?:[A-Za-zÁÉÍÓÚáéíóú]+\.\s*)+", "", linea).split()
        es_persona = _PERSONA.match(linea) and all(
            p[:1].isupper() or p in ("de", "del", "la", "las", "los", "y", "van", "von", "da", "di") for p in palabras)
        if rol and es_persona and not _NO_ES_PERSONA.search(linea):
            filas.append((materia, linea, rol))
        elif rol:
            rol = None
    return filas if materia else []


def paginas_fcnym(visitante) -> list[tuple[str, object]]:
    indice = visitante.get("https://www.fcnym.unlp.edu.ar/buscarCatedras/?q=emptyAllxxxyyyy")
    enlaces = sorted({a["href"] for a in BeautifulSoup(indice or "", "html.parser").find_all("a", href=True)
                      if "/grado/catedras/" in a["href"]})
    return [("https://www.fcnym.unlp.edu.ar" + e.replace("/grado/", "/grado_/").rstrip("/") + "/", catedra_fcnym)
            for e in enlaces]


def cuerpo_docente_frba(html: str) -> list[tuple[str, str, str]]:
    """UTN, Buenos Aires: ASIGNATURA | CURSO | DOCENTE, a subject's further
    courses on rows of two cells. The plan ("(P23)") is not the name."""
    filas, materia = [], None
    for fila in BeautifulSoup(html or "", "html.parser").select("table tr"):
        celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
        if len(celdas) >= 3 and celdas[0].upper() != "ASIGNATURA":
            materia, docente = re.sub(r"\s*\(P\d+[A-Z]?\)\s*$", "", celdas[0]), celdas[2]
        elif len(celdas) == 2 and materia:
            docente = celdas[1]
        else:
            continue
        if docente and "," in docente:
            filas.append((materia, docente, ""))
    return filas


def materias_dc_uba(html: str) -> list[tuple[str, str, str]]:
    """UBA, Computación: a term's subjects, each named as every plan calls it
    ("Introducción a la Programación / Algoritmos y Estructuras de Datos I –
    Mañana"): the first is the plan in force; the shift is not the name."""
    filas = []
    for fila in BeautifulSoup(html or "", "html.parser").select("table tr"):
        celdas = [_texto(c) for c in fila.find_all("td")]
        if len(celdas) >= 4 and celdas[3]:
            materia = re.split(r"\s+/\s+", re.sub(r"\s+[–-]\s+(Mañana|Tarde|Noche|Vespertino)$", "", celdas[0]))[0]
            filas += [(materia, docente.strip(), "") for docente in celdas[3].split(";") if "," in docente]
    return filas


def horarios_eco_mdp(html: str) -> list[tuple[str, str, str]]:
    """UNMdP, Económicas: a term's schedule, Cód | Asignatura | Com | Docente |
    Días y Horarios, a subject's further teachers on shorter rows (a
    commission and its teacher, or the teacher alone). The careers after the
    name ("(carreras: CP, LA)") are not the name; the page says the term."""
    soup = BeautifulSoup(html or "", "html.parser")
    titulo = _texto(soup.find("title")) + " " + _texto(soup.find("h1")) + " " + _texto(soup.find("h2"))
    termino = re.search(r"(?i)([12])\s*[º°o]?\s*(?:do|er|ro)?\s*cuatrimestre", titulo)
    rol = f"{termino.group(1)}° cuatrimestre" if termino else ""
    filas, materia = [], None
    for fila in soup.select("table tr"):
        celdas = [_texto(c) for c in fila.find_all(["td", "th"])]
        if len(celdas) >= 5 and re.match(r"^\d+$", celdas[0]):
            materia, docente = re.sub(r"\s*\(carreras?:[^)]*\)\s*$", "", celdas[1]), celdas[3]
        elif len(celdas) == 4 and re.match(r"^\d+$", celdas[0]):
            docente = celdas[1]
        elif len(celdas) == 3:
            docente = celdas[0]
        else:
            continue
        if materia and docente and len(docente.split()) >= 2 and not re.search(r"\d", docente) \
                and not re.match(r"(?i)^(a designar|a confirmar|vacante|sin docente)", docente):
            filas.append((materia, docente, rol))
    return filas


def paginas_eco_mdp(visitante) -> list[tuple[str, object]]:
    indice = visitante.get("https://eco.mdp.edu.ar/horarios-de-cursada")
    enlaces = sorted({a["href"] for a in BeautifulSoup(indice or "", "html.parser").find_all("a", href=True)
                      if "view=article" in a["href"] and "2026" in a["href"]
                      and re.search(r"horarios-\d-ano|optativas|electivas", a["href"])})
    return [("https://eco.mdp.edu.ar" + e if e.startswith("/") else e, horarios_eco_mdp) for e in enlaces]


def optativas_fiq(html: str) -> list[tuple[str, str, str]]:
    """UNL, Ingeniería Química: its electives, each a heading and then
    "Docente: Eduardo Adam. Optativa de: IQ, IA. Cuatrimestre de cursado:
    Primero." ("Docente: -" when none is named)."""
    soup = BeautifulSoup(html or "", "html.parser")
    for parte in soup.find_all(["script", "style", "nav", "header", "footer"]):
        parte.decompose()
    lineas = [clean_text(l) for l in soup.get_text("\n").split("\n") if clean_text(l)]
    filas, materia = [], None
    for posicion, linea in enumerate(lineas):
        dicho = re.match(r"(?i)^docente[s]?:\s*(.+?)(?:\.\s*optativa.*|\.\s*$|$)", linea)
        if not dicho:
            if linea != "MÁS INFO" and not re.match(r"(?i)^(optativa de|cuatrimestre de cursado)", linea):
                materia = linea
            continue
        resto = " ".join(lineas[posicion:posicion + 3])
        cuando = re.search(r"(?i)cuatrimestre de cursado:\s*(primero|segundo)", resto)
        termino = {"primero": "1° cuatrimestre", "segundo": "2° cuatrimestre"}.get(cuando.group(1).lower(), "") if cuando else ""
        for docente in re.split(r"\s*(?:;|\s+y\s+)\s*", dicho.group(1)):
            if materia and docente.strip(" -") and len(docente.split()) >= 2:
                filas.append((materia, docente.strip(" ."), termino))
    return filas


def horarios_fder_unr(texto: str) -> list[tuple[str, str, str]]:
    """UNR, Derecho: the term's schedule PDF, as ``pdftotext -layout`` gives
    it: a heading per chair ("16.09.1. ECONOMÍA POLÍTICA - CÁT. A") and the
    teachers in the last column, "APELLIDO, Nombre"."""
    filas, materia = [], None
    for linea in (texto or "").splitlines():
        encabezado = re.match(r"^\s*\d+\.\d+\.\d+\.\s+(.+?)\s*\*?\s*$", linea)
        if encabezado:
            # "- CÁT. A", "– CÁTEDRA B", or the dash alone where the heading wraps.
            materia = re.split(r"\s*[-–]\s*C[ÁA]T", clean_text(encabezado.group(1)))[0]
            materia = re.sub(r"\s*[-–]\s*$", "", materia)
            continue
        ultimo = re.split(r"\s{2,}", linea.strip())[-1] if linea.strip() else ""
        if materia and re.match(r"^[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ' .-]+,\s*[A-ZÁÉÍÓÚ][\wÁÉÍÓÚáéíóúñ. ]+$", ultimo):
            filas.append((materia, ultimo, "2° cuatrimestre"))
    return filas


# Sigla -> [(page, reader)], or a function that lists them from an index.
FUENTES = {
    "UNR": [("https://www.fder.unr.edu.ar/wp-content/uploads/2026/07/HORARIOS-2do-CUATRIMESTRE-2026-ABOGACIA-4.pdf",
             horarios_fder_unr)],
    "UP": [(f"https://www.palermo.edu/cienciassociales/profesores/{pagina}.html", profesores_palermo)
           for pagina in ("psicologia", "periodismo", "relaciones_internacionales", "arte",
                          "humanidades-ciencias-sociales", "educacion_superior")],
    "UBA": [("https://www.dc.uba.ar/ya-se-encuentran-publicadas-las-materias-del-segundo-cuatrimestre-de-2026/", materias_dc_uba),
            ("https://www.psi.uba.ar/profesores.php?var=profesores/profesores_regulares.php", psicologia_uba),
            ("https://www.derecho.uba.ar/academica/profesores/Profesores-Regulares-ABRIL-2026.pdf", derecho_uba)],
    "UNT": [("https://www.fau.unt.edu.ar/fau/personal-docente/", fau_unt),
            ("https://www.facet.unt.edu.ar/cic/asignaturas/", asignaturas_facet)],
    "UNGS": [("https://www.ungs.edu.ar/wp-content/uploads/2018/07/COMISIONES-DE-UN-PERIODO-2_2026-ANUAL_2026-v17-CON-AULAS-22026-ANUAL2026.pdf", comisiones_ungs)],
    "UNMdP": lambda visitante: [("https://owncloud.fi.mdp.edu.ar/index.php/s/2h92ttZzcbjFe5e/download", ingenieria_mdp)]
                               + paginas_eco_mdp(visitante),
    "UNLP": paginas_fcnym,
    "UNL": [("https://fiq.unl.edu.ar/vivilafiq/optativas/", optativas_fiq)],
    "UTN": [("https://www.institucional.frc.utn.edu.ar/sistemas/Areas/Academica/Docentes.asp", sistemas_frc),
            ("https://www.frba.utn.edu.ar/mecanica/cuerpo-docente/", cuerpo_docente_frba)],
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Leer los planteles docentes publicados")
    parser.add_argument("universidad", choices=sorted(FUENTES))
    args = parser.parse_args()

    from rumbo_scraper.spiders.visitante import Visitante

    comisiones: dict[str, dict] = {}
    with Visitante(timeout=40) as visitante:
        fuentes = FUENTES[args.universidad]
        for pagina, lector in (fuentes(visitante) if callable(fuentes) else fuentes):
            if pagina.lower().endswith((".pdf", "/download")):
                import subprocess
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".pdf") as archivo:
                    archivo.write(visitante.client.get(pagina).content)
                    archivo.flush()
                    html = subprocess.run(["pdftotext", "-layout", archivo.name, "-"],
                                          capture_output=True, text=True, timeout=120).stdout
            else:
                html = visitante.get(pagina)
            time.sleep(0.6)
            for materia, docente, rol in lector(html):
                materia = re.sub(r"(?i)\s*\(\s*m[áa]s informaci[óo]n\s*\)", "", materia).strip()
                if materia.isupper():
                    from rumbo_scraper.parsers.guias_nacionales import con_tildes

                    materia = re.sub(r"\b(i{1,3}|iv|vi{0,3}|ix|x)\b", lambda m: m.group(1).upper(),
                                     con_tildes(materia), flags=re.I)
                # A subject of one faculty is not another's of the same name
                # ("Sistemas de Representación" in Arquitectura and in Civil).
                fuente = re.sub(r"[^a-z0-9]+", "-", urlparse(pagina).netloc + urlparse(pagina).path).strip("-")[-40:]
                clave = f"{fuente}:{comparison_key(materia)}"
                comision = comisiones.setdefault(clave, {
                    "materia": materia, "codigo": "web-" + (fuente + "-" + comparison_key(materia).replace(" ", "-"))[:120],
                    "anio": 2026, "seccion": "Cátedra", "fuente_url": pagina, "docentes": []})
                # A reader that knows the term, not the role, says it there.
                termino = re.match(r"^([12])° cuatrimestre$", rol or "")
                if termino:
                    comision["semestre"], rol = int(termino.group(1)), ""
                if all(comparison_key(d["nombre"]) != comparison_key(docente) for d in comision["docentes"]):
                    comision["docentes"].append({"nombre": docente, "rol": rol})
    # The file may also hold another reader's chairs (the UNR's Ciencia
    # Política): those stay, these are replaced.
    archivo = Path(f"data/docentes_{args.universidad.lower()}.json")
    otras = [c for c in (json.loads(archivo.read_text())["comisiones"] if archivo.exists() else [])
             if not c["codigo"].startswith("web-")]
    archivo.write_text(json.dumps(
        {"universidad": args.universidad, "comisiones": otras + list(comisiones.values())},
        ensure_ascii=False, indent=1) + "\n")
    print(f"{args.universidad}: {len(comisiones)} materias, "
          f"{len({comparison_key(d['nombre']) for c in comisiones.values() for d in c['docentes']})} docentes")


if __name__ == "__main__":
    main()
