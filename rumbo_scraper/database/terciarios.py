"""Load non-university higher institutes (institutos superiores de formación
docente y técnica) from a province's official registry of what each teaches.

Each institute is an institution of its own, marked "instituto_terciario";
its careers are the degrees the registry says it gives, named as careers
("Técnica/o Superior en Administración Financiera" is the "Tecnicatura
Superior en Administración Financiera"; "Profesor/a de Educación Secundaria
en Matemáticas" the "Profesorado de Educación Secundaria en Matemáticas").
A certification, a trayecto or a postítulo is not a career.

The registry's own record of the institute's offer is each career's source:
the province's map has no page per institute.

    python -m rumbo_scraper.database.terciarios pba [--distritos "La Plata,Quilmes"] [--apply]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from rumbo_scraper.database.carreras_de_guias import (Guia, escribir_artefacto, plan_de_cambios,
                                                      universidad, aplicar, unicas)
from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers.guias_nacionales import _carrera, con_tildes
from rumbo_scraper.parsers.unc import CarreraDeLaGuia

REGISTRO = Path("relevamiento/terciarios.json")
_NO_ES_CARRERA = re.compile(r"(?i)^(certificaci[óo]n|trayecto|post[íi]tulo|actualizaci[óo]n|especializaci[óo]n|"
                            r"diplomatura|curso)")


_PROFESIONES = ((r"enfermer[oa](?:/[oa])?(?: profesional)?", "Enfermería"),
                (r"trabajador(?:/a|a)? social", "Trabajo Social"),
                (r"psicopedagog[oa](?:/[oa])?", "Psicopedagogía"),
                (r"bibliotecari[oa](?:/[oa])?", "Bibliotecología"),
                (r"guía de turismo|gu[íi]a (?:universitari[oa] )?de turismo", "Guía de Turismo"))


def nombre_de_la_carrera(titulo: str) -> str | None:
    """The career a degree names, or None when it is not one."""
    titulo = clean_text(titulo)
    if not titulo or _NO_ES_CARRERA.match(titulo):
        return None
    # A registry that names the profession ("Enfermero/a"): the career is its field.
    for profesion, carrera in _PROFESIONES:
        if re.fullmatch(profesion, titulo, re.I):
            return carrera
    titulo = re.sub(r"(?i)^t[ée]cnic[oa](?:/[oa])?\s+superior\b", "Tecnicatura Superior", titulo)
    titulo = re.sub(r"(?i)^profesor(?:/a|a)?\s+(de|en)\b", r"Profesorado \1", titulo)
    return titulo[0].upper() + titulo[1:]


def _titulo(texto: str) -> str:
    texto = clean_text(texto)
    # "INSTITUTO SUPERIOR DE FORMACIÓN DOCENTE Nº 28": capitals but for the "º".
    texto = con_tildes(texto) if sum(c.islower() for c in texto) <= 2 else texto
    return re.sub(r"\bN[oº°]\.?\s*(?=\d)", "N° ", texto)


def siglas(nombre: str) -> str:
    """"Instituto Superior de Comercio Exterior ISCE" -> "ISCE"; "Instituto
    Superior Santo Domingo" -> "ISSD": the name's own acronym, or its initials."""
    propias = re.findall(r"\b[A-ZÁÉÍÓÚÑ]{2,6}\b", nombre)
    numero = re.search(r"\b(\d{2,5})\b", nombre)
    if propias and not nombre.isupper():
        # "ISPI N° 4007 Inmaculada Concepción" -> "ISPI 4007": several ISPI.
        return f"{propias[-1]} {numero.group(1)}" if numero else propias[-1]
    palabras = [p for p in re.findall(r"[\wÁÉÍÓÚÑáéíóúñ]+", nombre)
                if p.lower() not in {"de", "del", "la", "las", "los", "el", "y", "e", "en", "n", "nº", "n°"}]
    iniciales = "".join(p[0].upper() for p in palabras if not p.isdigit())
    numero = next((p for p in palabras if p.isdigit()), "")
    return f"{iniciales[:8]} {numero}".strip()


def _corto(nombre: str, numero: str, clave: str) -> str:
    """"INSTITUTO SUPERIOR DE FORMACIÓN DOCENTE Y TÉCNICA Nº 12" -> "ISFDyT 12"."""
    por_tipo = (("docente y t[ée]cnica", "ISFDyT"), ("docente", "ISFD"), ("t[ée]cnica", "ISFT"))
    for patron, sigla in por_tipo:
        if re.search(rf"(?i)instituto superior de formaci[óo]n {patron}\s+n", nombre) and numero:
            return f"{sigla} {int(numero)}"
    return siglas(_titulo(nombre)) or clave


def institutos_pba(datos: dict[str, Any], distritos: set[str] | None = None) -> list[dict[str, Any]]:
    """Each institute of the registry with a record and a career: its name,
    campus and careers."""
    from rumbo_scraper.parsers.terciarios_pba import API

    institutos = []
    for idserv, dato in datos.items():
        escuela = dato.get("escuela")
        if not escuela or (distritos and escuela.get("distrito") not in distritos):
            continue
        url = f"{API}ofertascarreras/{idserv}"
        carreras: list[CarreraDeLaGuia] = []
        for oferta in dato.get("ofertas") or []:
            nombre = nombre_de_la_carrera(oferta.get("titulo") or "")
            carrera = _carrera(nombre, "", url) if nombre else None
            if carrera:
                carreras.append(carrera)
        if not carreras:
            continue
        nombre_oficial = _titulo(escuela["nombre"]).replace('"', "")
        institutos.append({
            "nombre_oficial": nombre_oficial,
            "nombre_corto": _corto(escuela["nombre"], escuela.get("nro_escuela") or "", escuela["clave"]),
            "gestion": "Estatal" if escuela.get("sector") == "Estatal" else "Privada",
            "localidad": _titulo(escuela.get("localidad") or ""), "distrito": escuela.get("distrito"),
            "calle": clean_text(f"{escuela.get('calle') or ''} {escuela.get('nro_calle') or ''}"),
            "cue": escuela.get("cueanexo"), "url": url,
            "titulos": {nombre_de_la_carrera(o["titulo"]): clean_text(o["titulo"])
                        for o in dato.get("ofertas") or [] if nombre_de_la_carrera(o.get("titulo") or "")},
            "carreras": unicas(carreras),
        })
    # Two institutes named alike (a private school's "Instituto Superior San
    # José" in two districts) are told apart by their district.
    nombres = [i["nombre_oficial"] for i in institutos]
    for instituto in institutos:
        if nombres.count(instituto["nombre_oficial"]) > 1:
            instituto["nombre_oficial"] += f" ({instituto['distrito']})"
    return institutos


CBA_MAPA = "https://bd.dges-cba.edu.ar/bd_dges/modulos/mapas/operaciones/mapa_leaf.php?dges=1"


def institutos_cba(html: str, localidades: set[str] | None = None) -> list[dict[str, Any]]:
    """Córdoba's DGES map of its 2026 offer: an array in the page
    ("datosOriginales") of institutes and annexes with their careers. Only
    careers that open in 2026 count; the Universidad Provincial's are the
    university's, already loaded. An annex's careers are its institute's,
    at another campus."""
    datos = re.search(r"datosOriginales\s*=\s*(\[.*?\]);", html or "", re.S)
    filas = json.loads(datos.group(1)) if datos else []
    por_nombre: dict[str, dict[str, Any]] = {}
    for fila in sorted(filas, key=lambda f: f.get("tipo") != "Instituto"):
        nombre = clean_text(re.split(r"\s+(?:Anexo|-\s*Extensi[óo]n)\b", fila["nombre"])[0])
        if localidades and fila.get("loc") not in localidades:
            continue
        instituto = por_nombre.setdefault(nombre, {
            "nombre_oficial": nombre, "nombre_corto": siglas(nombre),
            "gestion": "Privada" if fila.get("gestion") == "Privada" else "Estatal",
            "localidad": fila.get("loc") or "", "distrito": fila.get("depto"), "calle": "", "cue": None,
            "url": CBA_MAPA, "titulos": {}, "carreras": []})
        for dada in fila.get("carreras") or []:
            if dada.get("nivel") == "UPC" or dada.get("abre") != "Si":
                continue
            nombre_carrera = nombre_de_la_carrera(dada.get("nombre") or "")
            carrera = _carrera(nombre_carrera, "", CBA_MAPA) if nombre_carrera else None
            if carrera and carrera.nombre not in {c.nombre for c in instituto["carreras"]}:
                instituto["carreras"].append(carrera)
    return [i for i in por_nombre.values() if i["carreras"]]


SALTA = "https://dges-sal.infd.edu.ar/sitio/6006-2/"


def instituto_salta(html: str, url: str) -> dict[str, Any] | None:
    """A Salta IES's page on the DGES site, as lines: its number ("6001"),
    its name, its street, its town and department ("Salta – Capital"), its
    own site, "Nº de CUE" and the CUE, then its careers after "CARRERAS"
    (profesorados and tecnicaturas side by side)."""
    from bs4 import BeautifulSoup

    contenido = BeautifulSoup(html or "", "html.parser").select_one("div.entry-content")
    lineas = [clean_text(l) for l in (contenido.get_text("\n") if contenido else "").split("\n") if clean_text(l)]
    if len(lineas) < 5 or not re.fullmatch(r"60\d\d", lineas[0]):
        return None
    numero, nombre, calle, localidad = lineas[0], lineas[1], lineas[2], lineas[3]
    cue = next((l for l in lineas if re.fullmatch(r"\d{9}", l)), None)
    sitio = next((l if l.startswith("http") else f"https://{l}" for l in lineas if "infd.edu.ar" in l), None)
    inicio = next((i for i, l in enumerate(lineas) if l.replace(" ", "") == "CARRERAS"), None)
    carreras: list[CarreraDeLaGuia] = []
    for linea in lineas[inicio + 1:] if inicio is not None else []:
        if not re.match(r"(?i)(profesorado|tecnicatura|t[ée]cnic[oa])\s+\w", linea):
            continue
        propio = nombre_de_la_carrera(linea)
        carrera = _carrera(propio, "", url) if propio else None
        if carrera and carrera.nombre not in {c.nombre for c in carreras}:
            carreras.append(carrera)
    return {"nombre_oficial": f"IES N° {numero} {nombre}", "nombre_corto": f"IES {numero}",
            "gestion": "Estatal", "localidad": re.split(r"\s+[–-]\s+", localidad)[0], "distrito": localidad,
            "calle": calle, "cue": cue, "url": url, "sitio": sitio, "titulos": {}, "carreras": carreras}


def institutos_salta(localidades: set[str] | None = None) -> list[dict[str, Any]]:
    import time

    from bs4 import BeautifulSoup
    from rumbo_scraper.spiders.visitante import Visitante

    institutos = []
    with Visitante(timeout=30) as visitante:
        indice = BeautifulSoup(visitante.get(SALTA) or "", "html.parser")
        # An annex's careers are its institute's, at another campus.
        paginas = sorted({a["href"] for a in indice.find_all("a", href=True)
                          if re.search(r"/sitio/60\d\d-\d+/$", a["href"])})
        for pagina in paginas:
            instituto = instituto_salta(visitante.get(pagina), pagina)
            time.sleep(1)
            # The police institute (6045) is loaded from its own guide ("IESP Salta").
            if instituto and "6045" in instituto["nombre_corto"]:
                continue
            if instituto and instituto["carreras"] and (not localidades or instituto["localidad"] in localidades):
                institutos.append(instituto)
    return institutos


INFD = "https://mapa.infd.edu.ar/"
_PROVINCIAS_INFD = {"caba": ("02", "Ciudad Autónoma de Buenos Aires"), "santafe": ("82", "Santa Fe")}


def instituto_infd(respuesta: str, url: str) -> dict[str, Any] | None:
    """An institute's record on INFoD's map (JSON with its panel as HTML):
    its name, address, town, sector, own site and careers ("Oferta
    académica → Carreras")."""
    from bs4 import BeautifulSoup

    try:
        html = json.loads(respuesta or "{}").get("html") or ""
    except ValueError:
        return None
    soup = BeautifulSoup(html, "html.parser")
    titulo = soup.select_one("#nombreCentro div")
    if not titulo:
        return None
    datos = {clean_text(p.find("b").get_text()).rstrip(":"): clean_text(p.get_text(" ").split(":", 1)[-1])
             for p in soup.select("div.info p") if p.find("b")}
    listas = {clean_text(li.select_one("span.nombre").get_text()): [clean_text(o.get_text()) for o in li.select("span.nombreOpcion")]
              for li in soup.select("#campos_adicionales li") if li.select_one("span.nombre")}
    sitio = re.search(r"window\.open\('([^']+)'", html)
    carreras: list[CarreraDeLaGuia] = []
    for dada in listas.get("Carreras", []):
        # INFoD's catalogue labels ("Profesorado de Educación Primaria / Egb").
        propio = nombre_de_la_carrera(re.sub(r"(?i)\s*/\s*(egb|polimodal|nivel medio)\b.*$", "", dada))
        # A course for graduates ("con título de base") completes a degree.
        if propio and re.search(r"(?i)t[íi]tulo de base", propio):
            continue
        propio = propio.replace("ConTrabajo", "Contrabajo") if propio else propio
        carrera = _carrera(propio, "", url) if propio else None
        if carrera and carrera.nombre not in {c.nombre for c in carreras}:
            carreras.append(carrera)
    nombre = clean_text(titulo.get_text(" ")).replace('"', "")
    gestion = (listas.get("Tipo de gestión") or ["Estatal"])[0]
    return {"nombre_oficial": nombre, "nombre_corto": siglas(nombre), "gestion": "Privada" if "rivad" in gestion else "Estatal",
            "localidad": datos.get("Localidad", ""), "distrito": datos.get("Localidad", ""),
            "calle": datos.get("Dirección", ""), "cue": None, "url": url,
            "sitio": sitio.group(1) if sitio else None, "titulos": {}, "carreras": carreras}


def institutos_infd(jurisdiccion: str, localidades: set[str] | None = None) -> list[dict[str, Any]]:
    import time

    from bs4 import BeautifulSoup
    from rumbo_scraper.spiders.visitante import Visitante

    prefijo = _PROVINCIAS_INFD[jurisdiccion][0]
    institutos = []
    with Visitante(timeout=30) as visitante:
        indice = BeautifulSoup(visitante.get(INFD) or "", "html.parser")
        ids = sorted({a["id"] for a in indice.select("a.link-centro[id]") if a["id"].startswith(prefijo)})
        for centro in ids:
            url = f"{INFD}?wAccion=vercentro&idCentro={centro}&wPartial=1"
            try:
                respuesta = visitante.client.get(url).text
            except Exception:
                continue
            time.sleep(1)
            instituto = instituto_infd(respuesta, url)
            if instituto and instituto["carreras"] and (not localidades or instituto["localidad"] in localidades):
                instituto["cue"] = centro
                institutos.append(instituto)
    # An institute renamed ("Instituto Superior de Formación Artística Jorge
    # Donn", now "Escuela Superior de Educación Artística Jorge Donn") is
    # listed under both names with the same careers: once, by its newest id.
    vistos: dict[tuple[str, frozenset[str]], dict[str, Any]] = {}
    for instituto in sorted(institutos, key=lambda i: i["cue"], reverse=True):
        clave = (" ".join(clean_text(instituto["nombre_oficial"]).lower().split()[-2:]),
                 frozenset(c.nombre for c in instituto["carreras"]))
        vistos.setdefault(clave, instituto)
    return list(vistos.values())


CABA_IFTS = ("https://formacionesagencia.bue.edu.ar/inscribiteba/api/formaciones/buscar?"
             "area=Formaci%C3%B3n%20T%C3%A9cnica%20Superior")
CABA_PADRON = ("https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-educacion/"
               "establecimientos-educativos/padron-establecimientos.csv")


def institutos_caba_ifts() -> list[dict[str, Any]]:
    """CABA's state technical institutes (IFTS): the Agencia de Aprendizaje's
    service lists each tecnicatura with the IFTS that gives it ("IFTS 33",
    "90 - GRIERSON Sede Caballito"); the city's open padrón gives each IFTS's
    name and address, its mail carrying its number ("dfts_ifts21_de8@")."""
    import csv
    import io

    from rumbo_scraper.parsers.guias_nacionales import anios
    from rumbo_scraper.spiders.visitante import Visitante

    import time

    def traer(url: str, **opciones: Any) -> Any:
        for _ in range(3):
            try:
                with Visitante(timeout=60) as visitante:
                    return visitante.client.get(url, **opciones)
            except Exception:
                time.sleep(10)
        raise RuntimeError(f"no responde: {url}")

    ofertas = traer(CABA_IFTS, headers={"Accept": "application/json"}).json()
    padron = traer(CABA_PADRON).content.decode("utf-8-sig")
    por_numero: dict[str, dict[str, str]] = {}
    for fila in csv.DictReader(io.StringIO(padron), delimiter=";"):
        numero = re.search(r"ifts(\d+)_", fila.get("email") or "")
        if numero and fila.get("anexo") == "00":
            por_numero.setdefault(numero.group(1), fila)
    institutos: dict[str, dict[str, Any]] = {}
    for oferta in ofertas:
        numero = re.search(r"(\d+)", oferta.get("lugar") or "")
        fila = por_numero.get(numero.group(1)) if numero else None
        if not fila:
            continue
        nombre = re.sub(r"\s+DE\s+\d+$", "", clean_text(fila["nombre_est"]))
        nombre = (f"Instituto de Formación Técnica Superior N° {numero.group(1)}" if nombre.upper().startswith("IFTS")
                  else _titulo(nombre).replace("Inst. ", "Instituto "))
        instituto = institutos.setdefault(numero.group(1), {
            "nombre_oficial": nombre, "nombre_corto": f"IFTS {numero.group(1)}", "gestion": "Estatal",
            "localidad": "Ciudad Autónoma de Buenos Aires", "distrito": _titulo(fila.get("barrio") or ""),
            "calle": _titulo(f"{fila.get('calle') or ''} {fila.get('num') or ''}"), "cue": fila.get("cueanexo"),
            "url": CABA_IFTS, "sitio": "https://formacionesagencia.bue.edu.ar", "titulos": {}, "carreras": []})
        propio = nombre_de_la_carrera(oferta.get("name") or "")
        carrera = _carrera(propio, "", CABA_IFTS, None, anios(oferta.get("duracion") or "")) if propio else None
        if carrera and carrera.nombre not in {c.nombre for c in instituto["carreras"]}:
            instituto["carreras"].append(carrera)
    return [i for i in institutos.values() if i["carreras"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar institutos superiores no universitarios")
    parser.add_argument("jurisdiccion", choices=["pba", "cba", "salta", "caba", "caba_ifts", "santafe"])
    parser.add_argument("--distritos", default="",
                        help="Distritos (PBA) o localidades (Córdoba) separados por coma; todos si se omite")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    from rumbo_scraper.parsers.terciarios_pba import SALIDA

    distritos = {d.strip() for d in args.distritos.split(",") if d.strip()} or None
    if args.jurisdiccion == "pba":
        institutos, sitio, provincia = institutos_pba(json.loads(SALIDA.read_text()), distritos), \
            "https://mapaescolar.abc.gob.ar", "Buenos Aires"
    elif args.jurisdiccion == "caba_ifts":
        institutos, sitio = institutos_caba_ifts(), "https://formacionesagencia.bue.edu.ar"
        provincia = "Ciudad Autónoma de Buenos Aires"
    elif args.jurisdiccion in _PROVINCIAS_INFD:
        institutos, sitio = institutos_infd(args.jurisdiccion, distritos), "https://mapa.infd.edu.ar"
        provincia = _PROVINCIAS_INFD[args.jurisdiccion][1]
    elif args.jurisdiccion == "salta":
        institutos, sitio, provincia = institutos_salta(distritos), "https://dges-sal.infd.edu.ar", "Salta"
    else:
        from rumbo_scraper.spiders.visitante import Visitante

        with Visitante(timeout=60) as visitante:
            institutos = institutos_cba(visitante.get(CBA_MAPA), distritos)
        sitio, provincia = "https://bd.dges-cba.edu.ar", "Córdoba"
    registro = json.loads(REGISTRO.read_text()) if REGISTRO.exists() else {}
    client = get_supabase_client() if args.apply else None
    # A short name is the institution's address in the app (its slug): two
    # institutes may not share one. The second takes its town.
    usados = {u["nombre_corto"]: u["nombre_oficial"] for u in select_all(
        client.table("universidades").select("nombre_corto,nombre_oficial"))} if client else {}
    for instituto in institutos:
        corto = instituto["nombre_corto"]
        if usados.get(corto, instituto["nombre_oficial"]) != instituto["nombre_oficial"]:
            corto = f"{corto} {instituto['localidad']}".strip()
            if usados.get(corto, instituto["nombre_oficial"]) != instituto["nombre_oficial"]:
                corto = f"{corto} {instituto['cue'] or ''}".strip()
        instituto["nombre_corto"] = corto
        usados[corto] = instituto["nombre_oficial"]
    total = 0
    for instituto in institutos:
        total += len(instituto["carreras"])
        print(f"{instituto['nombre_corto']:14} | {instituto['nombre_oficial'][:60]:60} | "
              f"{instituto['localidad']} | {len(instituto['carreras'])} carreras", flush=True)
        if not args.apply:
            continue
        guia = Guia(instituto["nombre_oficial"], instituto["nombre_corto"], instituto["gestion"],
                    instituto.get("sitio") or sitio, ((instituto["url"], None),),
                    instituto["localidad"], instituto["calle"], 1, tipo_institucion="instituto_terciario")
        escribir_artefacto(guia, instituto["carreras"])
        universidad_id = universidad(client, guia, crear=True)
        guardadas = select_all(client.table("carreras").select("id,nombre_carrera,nivel").eq(
            "universidad_id", universidad_id))
        aplicar(client, instituto["carreras"], plan_de_cambios(instituto["carreras"], guardadas), universidad_id)
        for carrera, titulo in instituto["titulos"].items():
            client.table("carreras").update({"titulo_otorgado": titulo}).eq(
                "universidad_id", universidad_id).eq("nombre_carrera", carrera).execute()
        registro[instituto["nombre_oficial"]] = {"jurisdiccion": provincia, "cue": instituto["cue"],
                                                  "distrito": instituto["distrito"]}
    if args.apply:
        REGISTRO.write_text(json.dumps(registro, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    print(f"{len(institutos)} institutos, {total} carreras{' cargados' if args.apply else ''}")


if __name__ == "__main__":
    main()
