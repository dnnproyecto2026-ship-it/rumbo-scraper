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


def nombre_de_la_carrera(titulo: str) -> str | None:
    """The career a degree names, or None when it is not one."""
    titulo = clean_text(titulo)
    if not titulo or _NO_ES_CARRERA.match(titulo):
        return None
    titulo = re.sub(r"(?i)^t[ée]cnic[oa](?:/[oa])?\s+superior\b", "Tecnicatura Superior", titulo)
    titulo = re.sub(r"(?i)^profesor(?:/a|a)?\s+(de|en)\b", r"Profesorado \1", titulo)
    return titulo[0].upper() + titulo[1:]


def _titulo(texto: str) -> str:
    texto = clean_text(texto)
    return con_tildes(texto) if texto.isupper() else texto


def siglas(nombre: str) -> str:
    """"Instituto Superior de Comercio Exterior ISCE" -> "ISCE"; "Instituto
    Superior Santo Domingo" -> "ISSD": the name's own acronym, or its initials."""
    propias = re.findall(r"\b[A-ZÁÉÍÓÚÑ]{2,6}\b", nombre)
    if propias and not nombre.isupper():
        return propias[-1]
    palabras = [p for p in re.findall(r"[\wÁÉÍÓÚÑáéíóúñ]+", nombre)
                if p.lower() not in {"de", "del", "la", "las", "los", "el", "y", "e", "en", "n", "nº", "n°"}]
    iniciales = "".join(p[0].upper() for p in palabras if not p.isdigit())
    numero = next((p for p in palabras if p.isdigit()), "")
    return f"{iniciales[:8]} {numero}".strip()


def _corto(nombre: str, numero: str, clave: str) -> str:
    """"INSTITUTO SUPERIOR DE FORMACIÓN DOCENTE Y TÉCNICA Nº 12" -> "ISFDyT 12"."""
    siglas = (("docente y t[ée]cnica", "ISFDyT"), ("docente", "ISFD"), ("t[ée]cnica", "ISFT"))
    for patron, sigla in siglas:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar institutos superiores no universitarios")
    parser.add_argument("jurisdiccion", choices=["pba", "cba", "salta"])
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
    elif args.jurisdiccion == "salta":
        institutos, sitio, provincia = institutos_salta(distritos), "https://dges-sal.infd.edu.ar", "Salta"
    else:
        from rumbo_scraper.spiders.visitante import Visitante

        with Visitante(timeout=60) as visitante:
            institutos = institutos_cba(visitante.get(CBA_MAPA), distritos)
        sitio, provincia = "https://bd.dges-cba.edu.ar", "Córdoba"
    registro = json.loads(REGISTRO.read_text()) if REGISTRO.exists() else {}
    client = get_supabase_client() if args.apply else None
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
