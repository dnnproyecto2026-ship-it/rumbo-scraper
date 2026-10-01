"""Read the exchange agreements every university publishes, and keep them out.

``convenios_intercambio.programa_origen`` is NOT NULL and holds the career a
student leaves from: Di Tella publishes its agreements one list per career,
which is where its six hundred and seventy-one rows come from. Every other
university publishes a single list for the whole institution, and that list
does not say which career each agreement is for.

An earlier version filled the column with the heading of the page the list
was on. What that put in the database was "Últimas Agendas" for thirty-five
agreements and the name of a member of staff for two others. A heading is not
a career, and choosing one would state something the university never said.

So the agreements are read and kept in the artifact, where they can be used
the day the schema has a column for an agreement of the whole university, and
they are counted as blocked rather than written.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers import vida
from rumbo_scraper.parsers.convenios import leer_convenios

USER_AGENT = "RumboScraper/0.4 (+catalogo educativo publico)"
MAX_PAGINAS = 6


def _get(client: httpx.Client, url: str) -> str:
    try:
        response = client.get(url)
        response.raise_for_status()
        if "html" not in response.headers.get("content-type", ""):
            return ""
        return response.text
    except Exception:
        return ""


def leer(universidad: dict[str, Any]) -> list[dict[str, Any]]:
    """Read the partner universities one university lists."""
    sitio = clean_text(universidad.get("sitio_web"))
    if not sitio:
        return []
    dominio = (urlparse(sitio).netloc or "").lower().removeprefix("www.")
    hallados: list[dict[str, Any]] = []
    vistos: set[str] = set()
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                      timeout=30) as client:
        inicio = _get(client, sitio)
        if not inicio:
            return []
        paginas = vida.discover_topics(inicio, sitio, dominio)["programas_internacionales"]
        # A page about exchanges links the list of partners one step further.
        for url in list(paginas[:MAX_PAGINAS]):
            html = _get(client, url)
            for fila in leer_convenios(html, url, universidad["nombre_oficial"]):
                clave = fila["universidad_destino"].lower()
                if clave not in vistos:
                    vistos.add(clave)
                    hallados.append(fila)
            if html:
                for otra, lista in vida.discover_topics(html, url, dominio).items():
                    if otra != "programas_internacionales":
                        continue
                    for extra in lista:
                        if extra not in paginas and len(paginas) < MAX_PAGINAS * 2:
                            paginas.append(extra)
        for url in paginas[MAX_PAGINAS:MAX_PAGINAS * 2]:
            for fila in leer_convenios(_get(client, url), url,
                                       universidad["nombre_oficial"]):
                clave = fila["universidad_destino"].lower()
                if clave not in vistos:
                    vistos.add(clave)
                    hallados.append(fila)
    return hallados


# Universities whose list of partners is read from the source it is published
# in, each with its own reader: a page grouped by country (Palermo), a
# brochure in columns (UB), a table by country with each partner's city
# (UADE, grado and posgrado). Written to ``data/convenios_universidad.json``,
# which the export adds as agreements of the whole university.
FUENTES_PROPIAS: dict[str, list[tuple[str, str]]] = {
    "Universidad de Palermo": [
        ("pagina_por_pais", "https://www.palermo.edu/estudiantes_internacionales/vinculaciones.html")],
    "Universidad de Belgrano": [
        ("folleto_en_columnas", "https://ub.edu.ar/sites/default/files/movilidad_internacional.pdf")],
    "Universidad Argentina de la Empresa": [
        ("tabla_por_pais", "https://www.uade.edu.ar/media/j2gofmnw/grado-convenios-vf.pdf"),
        ("tabla_por_pais", "https://www.uade.edu.ar/media/pv4pfdap/posgrado-convenios-uade-1.pdf")],
}
PROPIOS = Path("data/convenios_universidad.json")


def leer_propios(nombre_oficial: str) -> list[dict[str, Any]]:
    """The partners of one university from its own sources, without repeats."""
    import subprocess
    import tempfile

    from bs4 import BeautifulSoup

    from rumbo_scraper.parsers.convenios import (leer_json_ld, leer_por_pais, leer_tabla_por_pais,
                                                 lineas_por_columnas)
    from rumbo_scraper.normalizers.text import comparison_key

    hallados: list[dict[str, Any]] = []
    vistos: set[str] = set()
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60) as client:
        for forma, url in FUENTES_PROPIAS[nombre_oficial]:
            respuesta = client.get(url)
            respuesta.raise_for_status()
            if forma == "pagina_por_pais":
                soup = BeautifulSoup(respuesta.text, "html.parser")
                for sobra in soup(["script", "style", "nav", "header", "footer"]):
                    sobra.decompose()
                filas = (leer_por_pais(soup.get_text("\n").split("\n"), url, nombre_oficial)
                         + leer_json_ld(respuesta.text, url))
            else:
                with tempfile.NamedTemporaryFile(suffix=".pdf") as archivo:
                    archivo.write(respuesta.content)
                    archivo.flush()
                    if forma == "folleto_en_columnas":
                        filas = leer_por_pais(lineas_por_columnas(archivo.name), url, nombre_oficial)
                    else:
                        texto = subprocess.run(["pdftotext", "-layout", archivo.name, "-"],
                                               capture_output=True, text=True, timeout=60).stdout
                        filas = leer_tabla_por_pais(texto, url, nombre_oficial)
            for fila in filas:
                clave = comparison_key(fila["universidad_destino"])
                if clave not in vistos:
                    vistos.add(clave)
                    hallados.append(fila)
    return hallados


# The partners found one by one in a university's news, resolutions, reports
# and agreement PDFs, each with the page that states it: kept in
# ``relevamiento/convenios_fuentes.json`` ({university: {"slug", "sitio_web",
# "convenios": [{universidad, pais, ciudad, sitio_web, fuente, nota}]}}).
# A partner is taken only if that page, read here, still names it; and a page
# that is not the university's own (the partner's site, an archived copy of
# someone else's, a spreadsheet) has to name the university too.
RELEVADOS = Path("relevamiento/convenios_fuentes.json")
RECHAZADOS = Path("data/convenios_fuentes_rechazados.json")
ESPERA = 2.0  # seconds between two requests to the same site


def _url_de(fuente: str) -> str:
    hallada = re.search(r"https?://[^\s)\]>\"']+", fuente or "")
    return hallada.group(0).rstrip(".,;") if hallada else ""


def _para_leer(url: str) -> str:
    """The address a document is read at: a spreadsheet or a text of Google
    Docs as the page it publishes, a file of Drive as its download."""
    hoja = re.match(r"https://docs\.google\.com/spreadsheets/d/([\w-]+)", url)
    if hoja:
        return f"https://docs.google.com/spreadsheets/d/{hoja.group(1)}/htmlview"
    texto = re.match(r"https://docs\.google\.com/document/d/([\w-]+)", url)
    if texto:
        return f"https://docs.google.com/document/d/{texto.group(1)}/export?format=txt"
    archivo = re.match(r"https://drive\.google\.com/file/d/([\w-]+)", url)
    if archivo:
        return f"https://drive.google.com/uc?export=download&id={archivo.group(1)}"
    return url


def _original(url: str) -> str:
    """The page an archived copy is a copy of."""
    copia = re.match(r"https?://web\.archive\.org/web/[^/]+/(.+)", url)
    return copia.group(1) if copia else url


class _Lector:
    """Reads each page once, waiting between two requests to the same site."""

    def __init__(self) -> None:
        from rumbo_scraper.spiders.visitante import _contexto_tolerante

        self.client = httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                                   timeout=60)
        # A site that serves its certificate without the chain (UNAJ, UNCA):
        # read the way the scraper's visitor reads it.
        self.tolerante = httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                                      timeout=60, verify=_contexto_tolerante())
        self.textos: dict[str, str] = {}
        self.crudos: dict[str, str] = {}  # a page's HTML, links included
        self.ultima: dict[str, float] = {}

    def texto(self, url: str) -> str:
        import subprocess
        import tempfile
        import time

        from bs4 import BeautifulSoup

        if url in self.textos:
            return self.textos[url]
        sitio = urlparse(url).netloc
        espera = self.ultima.get(sitio, 0) + ESPERA - time.monotonic()
        if espera > 0:
            time.sleep(espera)
        texto = ""
        try:
            try:
                respuesta = self.client.get(url)
            except httpx.ConnectError:
                respuesta = self.tolerante.get(url)
            respuesta.raise_for_status()
            tipo = respuesta.headers.get("content-type", "")
            if "pdf" in tipo or respuesta.content[:5] == b"%PDF-":
                with tempfile.NamedTemporaryFile(suffix=".pdf") as archivo:
                    archivo.write(respuesta.content)
                    archivo.flush()
                    texto = subprocess.run(["pdftotext", "-layout", archivo.name, "-"],
                                           capture_output=True, text=True, timeout=120).stdout
            elif "spreadsheetml" in tipo or respuesta.content[:2] == b"PK":
                import io

                import openpyxl

                libro = openpyxl.load_workbook(io.BytesIO(respuesta.content), read_only=True, data_only=True)
                texto = "\n".join(" | ".join(str(c) for c in fila if c is not None)
                                  for hoja in libro.worksheets for fila in hoja.iter_rows(values_only=True))
            elif "html" in tipo or "xml" in tipo:
                self.crudos[url] = respuesta.text
                soup = BeautifulSoup(respuesta.text, "html.parser")
                for sobra in soup(["script", "style"]):
                    sobra.decompose()
                texto = soup.get_text(" ")
            elif tipo.startswith("text/"):
                texto = respuesta.text
        except Exception:
            texto = ""
        self.ultima[sitio] = time.monotonic()
        # An .xlsx uploaded to Drive opens as a page that only names the file:
        # its cells are in the file's download.
        subido = re.match(r"https://docs\.google\.com/spreadsheets/d/([\w-]+)/htmlview", url)
        if subido and len(texto) < 500:
            texto = self.texto(f"https://drive.google.com/uc?export=download&id={subido.group(1)}") or texto
        # A Google Sheet draws its cells with scripts: its download has them all.
        if subido and not any(p in texto for p in (" | ",)):
            texto = self.texto(f"https://docs.google.com/spreadsheets/d/{subido.group(1)}/export?format=xlsx") or texto
        self.textos[url] = texto
        return texto

    def documentos(self, url: str) -> list[str]:
        """The lists a page links (a PDF, a spreadsheet, a document) rather
        than shows: UNTREF's or Agronomía's page of agreements is the link to
        its list."""
        from urllib.parse import urljoin

        from bs4 import BeautifulSoup

        self.texto(url)
        enlaces = []
        for a in BeautifulSoup(self.crudos.get(url, ""), "html.parser").find_all("a", href=True):
            destino = urljoin(url, a["href"].strip())
            # Only a list of agreements: a yearly report that names a
            # university in passing says nothing of an agreement with it.
            nombre = a.get_text(" ") + " " + destino
            if re.search(r"(?i)\.(pdf|xlsx?)(\?|$)|docs\.google\.com/(spreadsheets|document)|drive\.google\.com/file",
                         destino) and re.search(r"(?i)conven|acuerdo", nombre) and destino not in enlaces:
                enlaces.append(destino)
        return enlaces[:12]


def _es_propia(url: str, fuente: str, sitio_web: str, lector: "_Lector") -> bool:
    """Whether a page is the university's own: on its site, or a document its
    site links (the spreadsheet of agreements a faculty's page points to)."""
    raiz = (urlparse(sitio_web).netloc or "").lower().removeprefix("www.")
    tronco = raiz.split(".")[0] if raiz else ""
    if not tronco:
        return False
    def en_su_sitio(direccion: str) -> bool:
        return tronco in (urlparse(_original(direccion)).netloc or "").lower()
    if en_su_sitio(url):
        return True
    documento = re.search(r"/d/([\w-]{20,})", url)
    if documento:
        for otra in re.findall(r"https?://[^\s)\]>\"']+", fuente):
            otra = otra.rstrip(".,;")
            if otra != url and en_su_sitio(otra):
                lector.texto(otra)
                return documento.group(1) in lector.crudos.get(otra, "")
    return False


def verificar_relevados(relevados: dict[str, Any], lector: "_Lector | None" = None,
                        ) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """The partners whose page still names them, and the ones refused."""
    from rumbo_scraper.parsers.convenios import nombrada_en

    lector = lector or _Lector()
    aceptados: dict[str, list[dict[str, Any]]] = {}
    rechazados: list[dict[str, Any]] = []
    for nombre_oficial, datos in relevados.items():
        siglas = [s for s in (datos.get("sigla"), datos.get("slug")) if s]
        for fila in datos["convenios"]:
            url = _url_de(fila.get("fuente", ""))
            motivo = None
            if not url:
                motivo = "sin dirección"
            else:
                texto = lector.texto(_para_leer(url))
                if texto.strip() and not nombrada_en(fila["universidad"], texto):
                    # The page may only link the list: the documents it links count as it.
                    for documento in lector.documentos(_para_leer(url)):
                        enlazado = lector.texto(_para_leer(documento))
                        if nombrada_en(fila["universidad"], enlazado):
                            texto = enlazado
                            break
                if not texto.strip():
                    motivo = "la página no se pudo leer"
                elif not nombrada_en(fila["universidad"], texto):
                    motivo = "la página no la nombra"
                elif not _es_propia(url, fila.get("fuente", ""), datos.get("sitio_web") or "", lector):
                    nombra = nombrada_en(nombre_oficial, texto) or any(
                        re.search(rf"(?<![A-Za-z]){re.escape(s.upper())}(?![A-Za-z])", texto)
                        for s in siglas if len(s) >= 3)
                    if not nombra:
                        motivo = "no es su sitio y no la nombra a ella"
            if motivo:
                rechazados.append({"universidad_origen": nombre_oficial, **fila, "motivo": motivo})
                continue
            aceptados.setdefault(nombre_oficial, []).append({
                "universidad_destino": fila["universidad"], "pais": fila["pais"],
                "ciudad": fila.get("ciudad"), "sitio_web": fila.get("sitio_web"),
                "carreras": fila.get("carreras") or [], "fuente": url,
                "nota": fila.get("nota")})
    return aceptados, rechazados


def aplicar(client: Any, universidad: dict[str, Any],
            convenios: list[dict[str, Any]]) -> int:
    """Nothing is written: see the module docstring. Kept so the day the
    schema can hold a university-wide agreement, only this changes."""
    return 0


def _aplicar_cuando_haya_columna(client: Any, universidad: dict[str, Any],
                                 convenios: list[dict[str, Any]]) -> int:
    ya = client.table("convenios_intercambio").select("id").eq(
        "universidad_id", universidad["id"]).limit(1).execute().data
    convenios = [c for c in convenios if c.get("programa")]
    if ya or not convenios:
        return 0
    filas = [{"universidad_id": universidad["id"], "programa_origen": c["programa"],
              "universidad_destino": c["universidad_destino"], "ciudad": None,
              "pais": c["pais"], "latitud": None, "longitud": None,
              "observaciones": None, "fuente_url": c["fuente"],
              "carrera_id": None, "posgrado_id": None} for c in convenios]
    for start in range(0, len(filas), 100):
        client.table("convenios_intercambio").insert(filas[start:start + 100]).execute()
    return len(filas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Completar los convenios de intercambio")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    parser.add_argument("--output", type=Path, default=Path("data/convenios.json"))
    parser.add_argument("--propios", action="store_true",
                        help=f"Leer las fuentes revisadas una por una y guardarlas en {PROPIOS}")
    parser.add_argument("--relevados", action="store_true",
                        help=f"Leer cada página de {RELEVADOS}, quedarse con los convenios que "
                             f"sigue nombrando y agregarlos a {PROPIOS}")
    parser.add_argument("--entregas", type=Path,
                        help="Escribir lo aceptado como r_<slug>.json en esta carpeta")
    args = parser.parse_args()

    if args.relevados:
        relevados = json.loads(RELEVADOS.read_text())
        aceptados, rechazados = verificar_relevados(relevados)
        todo_propio = json.loads(PROPIOS.read_text()) if PROPIOS.exists() else {}
        for nombre in relevados:
            if nombre in FUENTES_PROPIAS:
                continue  # its own reader reads it whole
            todo_propio[nombre] = aceptados.get(nombre, [])
            print(f"{nombre}: {len(aceptados.get(nombre, []))} de "
                  f"{len(relevados[nombre]['convenios'])}")
        PROPIOS.write_text(json.dumps(todo_propio, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        RECHAZADOS.write_text(json.dumps(rechazados, ensure_ascii=False, indent=1) + "\n",
                              encoding="utf-8")
        print(f"Aceptados {sum(map(len, aceptados.values()))}, rechazados {len(rechazados)}")
        if args.entregas:
            args.entregas.mkdir(parents=True, exist_ok=True)
            for nombre, datos in relevados.items():
                filas = todo_propio.get(nombre) or []
                convenios = [{"universidad": f["universidad_destino"], "pais": f["pais"],
                              "ciudad": f.get("ciudad"), "carreras": f.get("carreras") or [],
                              "sitio_web": f.get("sitio_web"), "fuente": f["fuente"],
                              **({"nota": f["nota"]} if f.get("nota") else {})} for f in filas]
                (args.entregas / f"r_{datos['slug']}.json").write_text(json.dumps(
                    {"slug": datos["slug"], "fuente": datos.get("fuente"), "convenios": convenios,
                     "nota": "Leído y verificado por rumbo-scraper load_convenios --relevados"},
                    ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return

    if args.propios:
        todo_propio = json.loads(PROPIOS.read_text()) if PROPIOS.exists() else {}
        for nombre in FUENTES_PROPIAS:
            todo_propio[nombre] = leer_propios(nombre)
            print(f"{nombre}: {len(todo_propio[nombre])} universidades de destino")
        PROPIOS.write_text(json.dumps(todo_propio, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    client = get_supabase_client()
    todo: dict[str, Any] = {}
    for universidad in select_all(client.table("universidades").select("*")):
        convenios = leer(universidad)
        todo[universidad["nombre_oficial"]] = convenios
        if not convenios:
            continue
        print(f'{universidad["nombre_oficial"]}: leídos {len(convenios)} | '
              f'bloqueados por programa_origen: {len(convenios)}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(todo, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print("LEÍDO. Nada se escribe: la lista no dice para qué carrera es cada convenio.")


if __name__ == "__main__":
    main()
