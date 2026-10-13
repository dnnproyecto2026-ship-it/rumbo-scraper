"""The plans of the UBA's careers, faculty by faculty.

The UBA's own site does not link its careers' pages: each of its thirteen
faculties publishes its plans on a site of its own and in a form of its own
-- Medicine as images, Philosophy as council resolutions, Engineering as the
resolution approving each career's plan. So each faculty that publishes its
plan as something a program can read gets a source here, and the others are
left alone rather than guessed.

Each source names the page that lists the plans; the plans are read off
what that page links, never off a search engine's memory of the site.

- Ingeniería: https://www.fi.uba.ar/institucional/plan2020/planes-de-estudio-2023
  links one resolution per career, read by `parsers.plan_por_cuatrimestre`.
- Ciencias Económicas: each career's page lays its plan out in tables, one
  per cycle ("CICLO DE FORMACIÓN GENERAL", "...PROFESIONAL"), a row per
  subject with its code ("» 241  Análisis Matemático I"); the tables of an
  orientation or of electives and optatives, which a student picks from,
  are not the plan's (``plan_de_economicas``). The pages do not say the
  year, so none is given.
- Agronomía: each career's page links its plan as a PDF laid out year by
  year in two columns, one per term, a subject as "Name (credits)" with its
  prerequisites under it ("* Botánica Morfológica"); read only when the
  subjects' credits plus the electives' and optatives' the plan asks for add
  up to the career's stated total ("carga horaria total de 234.5 créditos")
  (``plan_de_agronomia``).
- FADU: each design career's page, a table per year, read by
  ``planes_sitios.plan_fadu``.
- Exactas, Ciencias de Datos: its career's site gives the CBC's subjects
  and a table of the rest by term ("3  Álgebra I"), the year each term's
  pair; taken when the table names the same subjects the page lists one by
  one under "Segundo Ciclo de Grado" (``plan_de_datos``). The elective's
  slot and the CBC's electives (two of three) are a choice, not a subject.
- Exactas, the teacher-training careers (ccpems.exactas.uba.ar): a table
  per block, each subject numbered and its hours, a "TOTAL" row; taken when
  the numbers run from 1 without a gap and each block's hours add up to its
  total (``plan_de_profesorado``). The blocks do not say the year.
- Farmacia y Bioquímica, the tecnicaturas' 2022 plans: PDFs read by the
  reader ``planes_documentos`` keeps for ffyb.uba.ar, their subjects
  numbered ("01- TRABAJO Y SOCIEDAD (70) (CBC)"); taken when the numbers run
  from 1 without a gap, the number and the CBC's code left out.
- Exactas, Ciencias Geológicas: its department's page lists the plan year
  by year (``planes_sitios.plan_por_anios``); a section's title after it
  ("Tutores y TFL") is not a subject.
- Ciencias Sociales, careers whose page lists each cycle with its count
  ("Ciclo General: Veintidós (22) asignaturas"), read by
  `parsers.plan_por_ciclos`: Ciencia Política. Those pages do not say the
  year, so none is given.

A career gets subjects only if it has none: this does not second-guess a
plan read before. Downloads are kept in ``data/planes_uba/`` so a second run
reads nothing again. Preview by default; ``--apply`` writes.
"""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rumbo_scraper.database.exportar_catalogo import clave_de_carrera
from rumbo_scraper.database.planes_documentos import guardar_las_fuentes
from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.parsers import plan_por_ciclos, plan_por_cuatrimestre, planes_sitios
from rumbo_scraper.spiders.visitante import Visitante

CACHE = Path("data/planes_uba")
PAUSA = 1.0
INGENIERIA = "https://www.fi.uba.ar/institucional/plan2020/planes-de-estudio-2023"
ECONOMICAS = {
    "Licenciatura en Economía": "https://www.economicas.uba.ar/carreras/economia",
    "Actuario": "https://www.economicas.uba.ar/carreras/actuario",
    "Contador Público": "https://www.economicas.uba.ar/carreras/contador",
    "Licenciatura en Administración": "https://www.economicas.uba.ar/carreras/administracion",
    "Licenciatura en Sistemas de Información de las Organizaciones": "https://www.economicas.uba.ar/carreras/sistemas",
}
FADU = {
    "Diseño Gráfico": "https://www.fadu.uba.ar/diseno-grafico/",
    "Diseño Industrial": "https://www.fadu.uba.ar/nuevo-plan-de-estudios-de-diseno-industrial/",
    "Diseño Textil": "https://www.fadu.uba.ar/diseno-textil/",
    "Diseño de Indumentaria": "https://www.fadu.uba.ar/diseno-de-indumentaria/",
}
PROFESORADOS_EXACTAS = "https://ccpems.exactas.uba.ar/"
FFYB = {
    "Tecnicatura Universitaria en Óptica y Contactología":
        "https://www.ffyb.uba.ar/wp-content/uploads/2022/12/Nuevo-Plan-de-Estudios-2022-TUOC.pdf",
    "Tecnicatura Universitaria en Medicina Nuclear":
        "https://www.ffyb.uba.ar/wp-content/uploads/2022/12/Nuevo-Plan-de-Estudios-2022-TUMN-.pdf",
}
# Plans read before without their source kept: the page that lists them,
# for the verifier.
SOLO_LA_FUENTE = {
    "Sociología": "https://sociologia.sociales.uba.ar/plan-de-estudios/",
    "Licenciatura en Ciencias de la Comunicación": "https://comunicacion.sociales.uba.ar/plan-de-estudios/",
}
DATOS = ("Licenciatura en Ciencias de Datos", "https://lcd.exactas.uba.ar/materias/")
POR_ANIOS = {
    "Licenciatura en Ciencias Geológicas": "https://gl.fcen.uba.ar/lic-geo/",
}
AGRONOMIA = {
    "Agronomía": "https://www.agro.uba.ar/carreras/agronomia",
    "Licenciatura en Gestión de Agroalimentos": "https://www.agro.uba.ar/carreras/agroalimentos",
    "Licenciatura en Economía y Administración Agrarias": "https://www.agro.uba.ar/carreras/leaa",
    "Tecnicatura Universitaria en Turismo Rural": "https://www.agro.uba.ar/carreras/turismo",
    "Tecnicatura Universitaria en Producción Vegetal Orgánica": "https://www.agro.uba.ar/carreras/organica",
    "Tecnicatura Universitaria en Producción Florihortícola": "https://www.agro.uba.ar/carreras/florihorticola",
}
POR_CICLOS = {
    "Licenciatura en Ciencia Política": "https://cienciapolitica.sociales.uba.ar/home/estudiantes/"
                        "info-academica/plan-de-estudios-8558-17/",
}


def plan_de_profesorado(html: str) -> list[tuple[str, None]]:
    """A profesorado's page: a table per block ("Ciclo Básico Común",
    "Módulo de Formación General y Pedagógica"), rows "N° | Asignatura |
    hours a week | total hours | prerequisites" and a "TOTAL" row; the
    optatives' hours are a row without a number. The CBC's subjects carry
    their code ("Álgebra (27)"). Nothing unless the numbers
    run from 1 without a gap and every block's rows add up to its total."""
    materias: list[tuple[str, None]] = []
    numeros: list[int] = []
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        filas = [[" ".join(c.get_text(" ").split()) for c in fila.find_all(["td", "th"])]
                 for fila in tabla.find_all("tr")]
        if not filas or not any(re.match(r"(?i)asignatura", c) for c in filas[0]):
            continue
        # A list of options numbered I, II... without a total (the optatives offered) is not the plan's.
        if not any(fila and fila[0].isdigit() for fila in filas[1:]) and \
                not any(c.upper() == "TOTAL" for fila in filas for c in fila):
            continue
        suma, total = 0, None
        for fila in filas[1:]:
            if any(c.upper() == "TOTAL" for c in fila):
                total = next((int(c) for c in reversed(fila) if c.isdigit()), None)
                continue
            # The optatives' hours ("–  Asignaturas Optativas  –  256") count, but are not a subject.
            if len(fila) >= 4 and not fila[0].isdigit() and fila[3].isdigit():
                suma += int(fila[3])
                continue
            if len(fila) < 4 or not fila[0].isdigit():
                continue
            numeros.append(int(fila[0]))
            suma += int(fila[3]) if fila[3].isdigit() else 0
            nombre = re.sub(r"\s*\(\d{2,3}\)$", "", fila[1]).strip()
            if nombre and comparison_key(nombre) not in {comparison_key(n) for n, _ in materias}:
                materias.append((nombre, None))
        if total is None or suma != total:
            return []
    if not numeros or numeros != list(range(1, len(numeros) + 1)):
        return []
    return materias


def _de_ffyb(visitante: Visitante, carrera: str, documento: str) -> list[tuple[str, int | None]]:
    from rumbo_scraper.database.planes_documentos import _leer_documento

    archivo = CACHE / documento.rsplit("/", 1)[1]
    if not archivo.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        archivo.write_bytes(visitante.client.get(documento).content)
        time.sleep(PAUSA)
    numeros, materias = [], []
    for nombre, anio in _leer_documento(archivo, documento, carrera):
        numero = re.match(r"^(\d{1,2})\s*[-.]+\s*", nombre)
        if not numero:
            return []
        numeros.append(int(numero.group(1)))
        limpio = re.sub(r"(?:\s*\((?:\d{2,3}|CBC)\))+$", "", nombre[numero.end():]).strip(" .")
        materias.append((limpio, anio))
    return materias if numeros == list(range(1, len(numeros) + 1)) else []


def plan_de_datos(html: str) -> list[tuple[str, int]]:
    """Ciencias de Datos' plan page: the CBC's subjects (its first year)
    before "Seleccionar 2 materias electivas", then the table of the rest by
    term. Nothing unless the table's subjects are the ones the page heads one
    by one under "Segundo Ciclo de Grado"."""
    sopa = BeautifulSoup(html or "", "html.parser")
    titulos = sopa.find_all(["h3", "h4"])
    cbc = next((t for t in titulos if t.name == "h3" and "CBC" in t.get_text()), None)
    ciclo = next((t for t in titulos if t.name == "h3" and "Segundo Ciclo" in t.get_text()), None)
    if cbc is None or ciclo is None:
        return []
    materias: list[tuple[str, int]] = []
    for elemento in cbc.find_all_next(string=True):
        texto = " ".join(elemento.split())
        if elemento.find_parent(["h3", "h4"]) is ciclo or texto.lower().startswith("seleccionar"):
            break
        if texto and texto.lower() not in ("cbc", "ciclo básico común") and not elemento.find_parent(["h3", "script"]):
            materias.append((texto, 1))
    listadas = []
    for titulo in titulos[titulos.index(ciclo) + 1:]:
        if titulo.name == "h3":
            break
        listadas.append(comparison_key(re.sub(r"\s*\(\*\)\s*$", "", titulo.get_text(" ", strip=True)).rstrip(" .")))
    en_la_tabla = []
    for tabla in sopa.find_all("table"):
        filas = [[c.get_text(" ", strip=True) for c in fila.find_all(["td", "th"])] for fila in tabla.find_all("tr")]
        if not filas or filas[0][:2] != ["Cuatrimestre", "Asignatura"]:
            continue
        for fila in filas[1:]:
            if len(fila) >= 2 and fila[0].isdigit():
                en_la_tabla.append((fila[1].rstrip(" ."), (int(fila[0]) + 1) // 2))
    if not en_la_tabla or sorted(comparison_key(n) for n, _ in en_la_tabla) != sorted(listadas):
        return []
    materias += [(n, a) for n, a in en_la_tabla if not n.lower().startswith("electiva")]
    return materias


_NO_ES_DEL_PLAN = re.compile(r"(?i)electiv|optativ|orientaci|competencias")


def plan_de_economicas(html: str) -> list[str]:
    """The subjects of an Económicas career's plan: the rows with a code of
    the tables headed "CARGA HORARIA", unless the heading above the table
    (or the rows' own character) makes them an orientation's, electives or
    optatives; "(vigente en 2026)" is not part of a name. Nothing when a
    code repeats or fewer than ten subjects come out."""
    materias: list[str] = []
    codigos: list[str] = []
    for tabla in BeautifulSoup(html or "", "html.parser").find_all("table"):
        filas = tabla.find_all("tr")
        if not filas or "CARGA HORARIA" not in filas[0].get_text(" ").upper():
            continue
        encima = [t.get_text(" ", strip=True) for t in tabla.find_all_previous(
            ["h1", "h2", "h3", "h4", "h5", "p", "strong"], limit=3) if t.get_text(strip=True)]
        if encima and _NO_ES_DEL_PLAN.search(encima[0]):
            continue
        for fila in filas[2:]:
            celdas = [" ".join(c.get_text(" ").split()) for c in fila.find_all(["td", "th"])]
            codigo = re.fullmatch(r"»?\s*(\d{2,4})", celdas[0]) if len(celdas) > 2 else None
            if not codigo or _NO_ES_DEL_PLAN.search(" ".join(celdas[1:3])):
                continue
            nombre = re.sub(r"\s*\(vigente[^)]*\)", "", celdas[1]).strip()
            codigos.append(codigo.group(1))
            if nombre and nombre not in materias:
                materias.append(nombre)
    if len(set(codigos)) != len(codigos) or len(materias) < 10:
        return []
    return materias


_ANIO_AGRO = re.compile(r"(?i)^\s*(Primer|Segundo|Tercer|Cuarto|Quinto|Sexto)\s+A[ñn]o\b")
_ORDEN_AGRO = ("primer", "segundo", "tercer", "cuarto", "quinto", "sexto")
_MATERIA_AGRO = re.compile(r"^#?\s*(?:cod\.?\s*\d+\s*[-.]?\s*)?(.+?)\s*\((\d+(?:[.,]\d+)?)\)$")
_SOLO_CREDITOS = re.compile(r"^\((\d+(?:[.,]\d+)?)\)$")
_NO_ES_NOMBRE_AGRO = re.compile(r"(?i)cuatrimestre|bimestre|^anual$|se acredita|pueden ser|cumplidas|asignaturas|"
                                r"espacios curriculares|correlativ|deber[áa]n|^\(cbc\)$")
_FIN_AGRO = re.compile(r"(?i)asignaturas/espacios curriculares electivos \(|requisitos exigidos|^\s*•")
_TOTAL_AGRO = re.compile(r"(?i)la carrera de[^\n]*?carga horaria total de ([\d.,]+)\s*(cr[ée]ditos|horas)")


def _cifra(texto: str) -> float:
    """"234.5", "13,5" and "2.600" (thousands) as numbers."""
    if re.fullmatch(r"\d{1,3}\.\d{3}", texto):
        return float(texto.replace(".", ""))
    return float(texto.replace(",", "."))


def plan_de_agronomia(texto_con_columnas: str) -> list[tuple[str, int]]:
    """An Agronomía career's plan: year by year ("Segundo Año"), a column per
    term, each subject "Name (credits)" or its name wrapped over lines and
    "(credits)" alone under it, its prerequisites under it starting with
    "*" and any line that goes on with them. The electives listed after the
    plan are not its subjects. Taken only when the subjects' credits, plus
    the electives' and optatives' amounts the plan states, add up to the
    career's total ("La carrera de ... tiene una carga horaria total de
    234.5 créditos")."""
    total = _TOTAL_AGRO.findall(texto_con_columnas)
    if not total:
        return []
    materias: list[tuple[str, float, int]] = []
    anio = 0
    pendiente: dict[int, str] = {}
    for linea in texto_con_columnas.splitlines():
        if _FIN_AGRO.search(linea):
            break
        if not linea.strip():
            # A blank line ends a subject's prerequisites.
            pendiente = {c: p for c, p in pendiente.items() if p != "*"}
            continue
        hallado = _ANIO_AGRO.match(linea.strip() and linea)
        if hallado and len(linea.strip()) < 30:
            nuevo = _ORDEN_AGRO.index(hallado.group(1).lower()) + 1
            if nuevo != anio + 1:
                return []
            anio, pendiente = nuevo, {}
            continue
        for celda in re.finditer(r"\S+(?: \S+)*", linea):
            columna, texto = int(celda.start() >= 50), celda.group()
            if texto.startswith("*"):
                # Its prerequisites, and the lines that go on with them.
                pendiente[columna] = "*"
                continue
            materia = _MATERIA_AGRO.match(texto)
            solo = _SOLO_CREDITOS.match(texto)
            if materia and not texto.startswith("("):
                nombre = materia.group(1)
                previo = pendiente.pop(columna, "")
                if nombre[:1].islower() and previo and previo != "*":
                    nombre = f"{previo} {nombre}"
                materias.append((nombre, _cifra(materia.group(2)), anio))
            elif solo:
                abiertos = [c for c, p in pendiente.items() if p != "*"]
                previo = pendiente.pop(columna if columna in abiertos else (abiertos[0] if len(abiertos) == 1 else -1), "")
                if not previo or previo == "*":
                    return []
                materias.append((previo, _cifra(solo.group(1)), anio))
            elif _NO_ES_NOMBRE_AGRO.search(texto):
                pendiente.pop(columna, None)
            elif pendiente.get(columna) != "*":
                pendiente[columna] = f"{pendiente.get(columna, '')} {texto}".strip()
    if not anio or not materias:
        return []
    # What the student adds of electives and optatives, as the plan states it.
    extras = {0.0}
    lineas = texto_con_columnas.splitlines()
    for numero, linea in enumerate(lineas):
        # The line that names them, or the one under it.
        if re.search(r"(?i)electiv|optativ", " ".join(lineas[max(0, numero - 1):numero + 1])):
            extras |= {_cifra(c) for c in re.findall(r"(?i)(\d+(?:[.,]\d+)?)\s*(?:\)\s*)?(?:cr[ée]ditos|horas|hs)\b", linea)}
            extras |= {_cifra(c) for c in re.findall(r"(?i)electivos?\s*\((\d+(?:[.,]\d+)?)\)", linea)}
    suma = sum(c for _, c, _ in materias)
    declarado = _cifra(total[-1][0])
    if not any(abs(suma + e + o - declarado) < 0.01 for e in extras for o in extras if e != o or e == 0):
        return []
    vistas: list[tuple[str, int]] = []
    for nombre, _, anio_de in materias:
        if nombre not in {n for n, _ in vistas}:
            vistas.append((nombre, anio_de))
    return vistas


def documentos_de_ingenieria(html: str) -> dict[str, str]:
    """The plan in force of each Engineering career, by the name the index
    gives it: the last resolution listed beside the career."""
    documento_de: dict[str, str] = {}
    for enlace in BeautifulSoup(html or "", "html.parser").find_all("a", href=True):
        url = urljoin(INGENIERIA, enlace["href"])
        if not url.lower().endswith(".pdf"):
            continue
        fila = enlace.find_parent(["tr", "li", "p", "div"])
        texto = " ".join(fila.get_text(" ").split()) if fila else ""
        carrera = texto.split(" Resoluci")[0].strip()
        if carrera:
            documento_de[carrera] = url
    return documento_de


def planes_de_ingenieria(visitante: Visitante) -> dict[str, list[tuple[str, int]]]:
    """Each Engineering career's plan, by the name the index gives it.

    The index lists a career, then its resolution and, when there is one,
    the resolution that modified it; the last one listed is the plan in
    force, and it is the one read.
    """
    documento_de = documentos_de_ingenieria(visitante.get(INGENIERIA))
    planes = {}
    CACHE.mkdir(parents=True, exist_ok=True)
    for carrera, url in documento_de.items():
        archivo = CACHE / url.rsplit("/", 1)[1]
        if not archivo.exists():
            respuesta = visitante.client.get(url)
            respuesta.raise_for_status()
            archivo.write_bytes(respuesta.content)
            time.sleep(PAUSA)
        planes[carrera] = plan_por_cuatrimestre.leer_pdf(str(archivo))
    return planes


def _emparejar(nombre: str, carreras: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """The career of the university a plan's name names: the same words, or
    a spelling one letter off ("Biongeniería" on the index)."""
    clave = clave_de_carrera(nombre)
    for carrera in carreras.values():
        if clave_de_carrera(carrera["nombre_carrera"]) == clave:
            return carrera
    parecidas = difflib.get_close_matches(comparison_key(nombre),
                                          list(carreras), n=1, cutoff=0.92)
    return carreras[parecidas[0]] if parecidas else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar los planes de estudio de la UBA")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    client = get_supabase_client()
    uba = client.table("universidades").select("id").eq("nombre_corto", "UBA").execute().data[0]
    carreras = {comparison_key(c["nombre_carrera"]): c for c in select_all(
        client.table("carreras").select("id,nombre_carrera").eq("universidad_id", uba["id"]))}
    con_materias = {m["carrera_id"] for m in select_all(
        client.table("materias").select("carrera_id").eq("universidad_id", uba["id"]))}

    with Visitante(timeout=60) as visitante:
        planes: dict[str, list[tuple[str, int | None]]] = dict(planes_de_ingenieria(visitante))
        for carrera, url in POR_CICLOS.items():
            materias = plan_por_ciclos.leer_html(visitante.get(url))
            if materias:
                planes[carrera] = [(materia, None) for materia in materias]
        fuentes = {}
        for carrera, pagina in AGRONOMIA.items():
            enlace = next((urljoin(pagina, a["href"]) for a in BeautifulSoup(
                visitante.get(pagina) or "", "html.parser").find_all("a", href=True)
                if "plan de estudios" in a.get_text(" ").lower() and a["href"].lower().endswith(".pdf")), None)
            if not enlace:
                continue
            archivo = CACHE / enlace.rsplit("/", 1)[1]
            if not archivo.exists():
                CACHE.mkdir(parents=True, exist_ok=True)
                archivo.write_bytes(visitante.client.get(enlace).content)
                time.sleep(PAUSA)
            texto = subprocess.run(["pdftotext", "-layout", str(archivo), "-"], capture_output=True, text=True,
                                   timeout=120).stdout
            materias = plan_de_agronomia(texto)
            if materias:
                planes[carrera] = materias
                fuentes[carrera] = enlace
        # Each profesorado's page, linked "Ver info" from the site's home, by its title.
        for enlace in BeautifulSoup(visitante.get(PROFESORADOS_EXACTAS) or "", "html.parser").find_all("a", href=True):
            if enlace.get_text(strip=True) != "Ver info" or "anteriores" in enlace["href"]:
                continue
            pagina = urljoin(PROFESORADOS_EXACTAS, enlace["href"])
            html = visitante.get(pagina)
            titulo = BeautifulSoup(html or "", "html.parser").find("h1")
            materias = plan_de_profesorado(html)
            if titulo and materias:
                planes[titulo.get_text(" ", strip=True)] = materias
                fuentes[titulo.get_text(" ", strip=True)] = pagina
            time.sleep(PAUSA)
        for carrera, documento in FFYB.items():
            materias = _de_ffyb(visitante, carrera, documento)
            if materias:
                planes[carrera] = materias
                fuentes[carrera] = documento
        materias = plan_de_datos(visitante.get(DATOS[1]))
        if materias:
            planes[DATOS[0]] = materias
            fuentes[DATOS[0]] = DATOS[1]
        for carrera, url in POR_ANIOS.items():
            html = visitante.get(url)
            # (Its sections' titles: headings, and an accordion's "Tutores y TFL".)
            sopa = BeautifulSoup(html or "", "html.parser")
            titulos = {comparison_key(t.get_text(" ", strip=True)) for t in
                       sopa.find_all(["h1", "h2", "h3", "h4"]) + sopa.select("[class*=toggle-title]")}
            materias = [(n, a) for n, a in planes_sitios.plan_por_anios(html) if comparison_key(n) not in titulos]
            if materias:
                planes[carrera] = materias
                fuentes[carrera] = url
            time.sleep(PAUSA)
        for carrera, url in FADU.items():
            materias = planes_sitios.plan_fadu(visitante.get(url))
            if materias:
                planes[carrera] = materias
                fuentes[carrera] = url
            time.sleep(PAUSA)
        for carrera, url in ECONOMICAS.items():
            materias = plan_de_economicas(visitante.get(url))
            if materias:
                planes[carrera] = [(materia, None) for materia in materias]
                fuentes[carrera] = url
            time.sleep(PAUSA)

    filas = []
    con_fuente = []
    for nombre, materias in planes.items():
        carrera = _emparejar(nombre, carreras)
        if not carrera:
            print(f"  sin carrera en la base: {nombre}")
            continue
        estado = "ya tiene materias" if carrera["id"] in con_materias else "se carga"
        por_anio = dict(sorted(Counter(anio for _, anio in materias).items()))
        print(f"{carrera['nombre_carrera'][:45]:45} {len(materias):3} materias {por_anio} — {estado}")
        if carrera["id"] in con_materias:
            continue
        if nombre in fuentes:
            con_fuente.append({"universidad": "UBA", "documento": fuentes[nombre],
                               "carrera": {"nombre_carrera": carrera["nombre_carrera"]}})
        vistas: set[str] = set()
        for materia, anio in materias:
            if materia.lower() in vistas:
                continue
            vistas.add(materia.lower())
            filas.append({"universidad_id": uba["id"], "carrera_id": carrera["id"],
                          "nombre_materia": materia, "anio_cursada": anio})

    for nombre, url in SOLO_LA_FUENTE.items():
        carrera = _emparejar(nombre, carreras)
        if carrera:
            con_fuente.append({"universidad": "UBA", "documento": url,
                               "carrera": {"nombre_carrera": carrera["nombre_carrera"]}})
    if args.apply:
        for inicio in range(0, len(filas), 500):
            client.table("materias").insert(filas[inicio:inicio + 500]).execute()
        guardar_las_fuentes(con_fuente)
    print(f"Materias {'cargadas' if args.apply else 'a cargar'}: {len(filas)}"
          + ("" if args.apply else " — vista previa, sin escribir"))


if __name__ == "__main__":
    main()
