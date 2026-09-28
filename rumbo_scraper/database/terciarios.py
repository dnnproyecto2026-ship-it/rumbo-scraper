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


def _corto(nombre: str, numero: str, clave: str) -> str:
    """"INSTITUTO SUPERIOR DE FORMACIÓN DOCENTE Y TÉCNICA Nº 12" -> "ISFDyT 12"."""
    siglas = (("docente y t[ée]cnica", "ISFDyT"), ("docente", "ISFD"), ("t[ée]cnica", "ISFT"))
    for patron, sigla in siglas:
        if re.search(rf"(?i)instituto superior de formaci[óo]n {patron}\s+n", nombre) and numero:
            return f"{sigla} {int(numero)}"
    return clave


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar institutos superiores no universitarios")
    parser.add_argument("jurisdiccion", choices=["pba"])
    parser.add_argument("--distritos", default="", help="Distritos separados por coma; todos si se omite")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    from rumbo_scraper.parsers.terciarios_pba import SALIDA

    distritos = {d.strip() for d in args.distritos.split(",") if d.strip()} or None
    institutos = institutos_pba(json.loads(SALIDA.read_text()), distritos)
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
                    "https://mapaescolar.abc.gob.ar", ((instituto["url"], None),),
                    instituto["localidad"], instituto["calle"], 1, tipo_institucion="instituto_terciario")
        escribir_artefacto(guia, instituto["carreras"])
        universidad_id = universidad(client, guia, crear=True)
        guardadas = select_all(client.table("carreras").select("id,nombre_carrera,nivel").eq(
            "universidad_id", universidad_id))
        aplicar(client, instituto["carreras"], plan_de_cambios(instituto["carreras"], guardadas), universidad_id)
        for carrera, titulo in instituto["titulos"].items():
            client.table("carreras").update({"titulo_otorgado": titulo}).eq(
                "universidad_id", universidad_id).eq("nombre_carrera", carrera).execute()
        registro[instituto["nombre_oficial"]] = {"jurisdiccion": "Buenos Aires", "cue": instituto["cue"],
                                                  "distrito": instituto["distrito"]}
    if args.apply:
        REGISTRO.write_text(json.dumps(registro, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    print(f"{len(institutos)} institutos, {total} carreras{' cargados' if args.apply else ''}")


if __name__ == "__main__":
    main()
