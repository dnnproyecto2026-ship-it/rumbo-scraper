"""A university's careers, as its official guide lists them.

Some universities publish one page with every career they teach, the unit
that teaches it and a link to its page (`parsers.unc`). Where there is one,
that page is the list of the university's careers, in its own words, and
it beats anything the general reader put together by walking the site. The
UNC is why: the general reader found 39 "careers" there, a third of the
real ones, and beside them subjects and courses it took for careers
("Ingeniería de Microondas", "Profesorado y Concursos") under a faculty
named "Biología Carga Horaria: 100".

For each university with a guide:

- a career of the guide already stored (the same name, "Universitaria" or
  not) keeps its subjects and takes the guide's name, level and unit;
- a career of the guide not stored is added;
- a grado or pregrado career stored and not in the guide is retired, with
  its subjects: the university does not teach it under that name.
  Postgraduates are in their own table and are not touched;
- a unit no career or postgraduate refers to any longer, and not in the
  guide, is retired;
- where the guide lists the campuses a career is taught at (the Provincial's
  regional campuses), the career gets one offer per campus, with the page
  of the career at that campus.

A university not yet in the catalogue is created, with the campus its own
site gives as its address: without a campus the application publishes none
of its offers.

The link of each career goes to ``data/<sigla>_guia_completo.json``, where
the export and the duration and plan readers look for a career's page.

    python -m rumbo_scraper.database.carreras_de_guias UNC UNRC UPC UNL UNCuyo UNT UNR [--apply]
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from rumbo_scraper.database.exportar_catalogo import clave_de_carrera
from rumbo_scraper.parsers import unc as guias
from rumbo_scraper.parsers import guias_nacionales as gn
from rumbo_scraper.parsers import uncuyo, unl, unr, unt
from rumbo_scraper.parsers.unc import CarreraDeLaGuia


@dataclass(frozen=True)
class Guia:
    nombre_oficial: str
    nombre_corto: str
    tipo_gestion: str
    sitio_web: str
    paginas: tuple[tuple[str, Callable[[str, str], list[CarreraDeLaGuia]]], ...]
    # The campus, as the university's own site gives its address; only used
    # to create a university not yet in the catalogue.
    sede: str
    calle: str
    # Fewer careers than this is a guide that came back short, not a
    # university that closed most of them.
    minimo: int
    # The levels the guide lists: a career of another level is not retired
    # for being absent (the UNR's page lists grado only).
    niveles: tuple[str, ...] = ("Grado", "Pregrado")

    @property
    def artefacto(self) -> Path:
        return Path(f"data/{self.nombre_corto.lower()}_guia_completo.json")


GUIAS = {
    "UNC": Guia(
        "Universidad Nacional de Córdoba", "UNC", "Estatal", "https://www.unc.edu.ar",
        ((guias.GUIA_DE_GRADO, lambda h, p: guias.leer_guia(h, p, "Grado")),
         (guias.GUIA_DE_PREGRADO, lambda h, p: guias.leer_guia(h, p, "Pregrado"))),
        "Ciudad Universitaria", "", 80),
    # "Mesa de Entrada Campus Sur. Av. Pablo Ricchieri 1955 Ciudad de las
    # Artes", and the rectorate on Vélez Sarsfield: the page ties neither to
    # a faculty, so the city campus goes without a street.
    "UPC": Guia(
        "Universidad Provincial de Córdoba", "UPC", "Estatal", "https://www.upc.edu.ar",
        ((guias.GUIA_UPC, guias.leer_guia_upc),),
        guias.SEDE_UPC, "", 40),
    # The UNL's catalogue by academic unit; its main campus is the city of
    # Santa Fe, where the rest of its cards say it teaches.
    "UNL": Guia(
        "Universidad Nacional del Litoral", "UNL", "Estatal", "https://www.unl.edu.ar",
        tuple((unl.CATALOGO.format(ua), (lambda s: lambda h, p: unl.leer_unidad(h, p, s))(sigla))
              for ua, sigla in unl.UNIDADES.items()),
        "Santa Fe", "", 60),
    # The UNCuyo's catalogue does not say where each career is taught (the
    # Facultad de Ciencias Aplicadas a la Industria is in San Rafael): its
    # campus is the one the application does not place on the map.
    "UNCuyo": Guia(
        "Universidad Nacional de Cuyo", "UNCuyo", "Estatal", "https://www.uncuyo.edu.ar",
        ((uncuyo.CATALOGO, uncuyo.leer_catalogo),),
        "Sede no informada", "", 60),
    # Expo UNT, faculty by faculty; the UNT teaches in several parts of
    # Tucumán, and the page ties no career to one.
    "UNT": Guia(
        "Universidad Nacional de Tucumán", "UNT", "Estatal", "https://www.unt.edu.ar",
        tuple((unt.INDICE + slug + "/", unt.leer_unidad) for slug in unt.UNIDADES),
        "Sede no informada", "", 60),
    # The UNR's grado careers by faculty, each with the address it is taught
    # at: Rosario, Zavalla (Agrarias) or Casilda (Veterinarias).
    "UNR": Guia(
        "Universidad Nacional de Rosario", "UNR", "Estatal", "https://unr.edu.ar",
        ((unr.GUIA, unr.leer_guia),),
        "Rosario", "", 40, ("Grado",)),
    # "Universidad Nacional de Río Cuarto Ruta Nac. 36 - KM. 601 - Río Cuarto -
    # Córdoba - Argentina", on the foot of every page of unrc.edu.ar.
    "UNRC": Guia(
        "Universidad Nacional de Río Cuarto", "UNRC", "Estatal", "https://www.unrc.edu.ar",
        ((guias.GUIA_UNRC, guias.leer_guia_unrc),),
        "Campus Río Cuarto", "Ruta Nac. 36 - KM. 601", 40),
}

# Universities whose list does not say where each career is taught go under
# the campus the application does not place on the map.
_SIN_SEDE = "Sede no informada"
GUIAS.update({
    "UADER": Guia("Universidad Autónoma de Entre Ríos", "UADER", "Estatal", "https://uader.edu.ar",
                  ((gn.UADER, gn.leer_uader),), "Paraná", "", 60),
    "UNComa": Guia("Universidad Nacional del Comahue", "UNComa", "Estatal", "https://uncoma.edu.ar",
                   ((gn.COMAHUE_GRADO, gn.leer_comahue), (gn.COMAHUE_PREGRADO, gn.leer_comahue)),
                   "Neuquén", "", 50),
    "UNTDF": Guia("Universidad Nacional de Tierra del Fuego, Antártida e Islas del Atlántico Sur",
                  "UNTDF", "Estatal", "https://www.untdf.edu.ar", ((gn.UNTDF, gn.leer_untdf),),
                  "Ushuaia", "", 15),
    "UMendoza": Guia("Universidad de Mendoza", "UMendoza", "Privada", "https://um.edu.ar",
                     ((gn.UM_MENDOZA, gn.leer_um_mendoza),), _SIN_SEDE, "", 20),
    "CAECE": Guia("Universidad CAECE", "CAECE", "Privada", "https://www.ucaece.edu.ar",
                  ((gn.CAECE, gn.leer_caece),), _SIN_SEDE, "", 10),
    "UCH": Guia("Universidad Champagnat", "UCH", "Privada", "https://www.uch.edu.ar",
                ((gn.CHAMPAGNAT, gn.leer_champagnat),), _SIN_SEDE, "", 8),
    "IUCBC": Guia("Instituto Universitario de Ciencias Biomédicas de Córdoba", "IUCBC", "Privada",
                  "https://www.iucbc.edu.ar",
                  ((gn.IUCBC_GRADO, gn.leer_iucbc), (gn.IUCBC_PREGRADO, gn.leer_iucbc)), _SIN_SEDE, "", 6),
    "UNRT": Guia("Universidad Nacional de Río Tercero", "UNRT", "Estatal", "https://unrt.edu.ar",
                 ((gn.UNRT, gn.leer_unrt),), _SIN_SEDE, "", 4),
    "UNMa": Guia("Universidad Nacional Madres de Plaza de Mayo", "UNMa", "Estatal", "https://unma.edu.ar",
                 ((gn.UNMA, gn.leer_unma),), _SIN_SEDE, "", 5),
    "Maimónides": Guia("Universidad Maimónides", "Maimónides", "Privada", "https://www.maimonides.edu",
                       ((gn.MAIMONIDES, gn.leer_maimonides),), _SIN_SEDE, "", 15),
    # The Universidad Evangélica answers this reader with a 403: not read.
    "UCAMI": Guia("Universidad Católica de las Misiones", "UCAMI", "Privada", "https://www.ucami.edu.ar",
                  ((gn.UCAMI, gn.leer_ucami),), _SIN_SEDE, "", 6),
    "IUSM": Guia("Instituto Universitario de Seguridad Marítima", "IUSM", "Estatal", "https://iusm.edu.ar",
                 ((gn.IUSM, gn.leer_iusm),), _SIN_SEDE, "", 6),
})


def clave(nombre: str) -> str:
    """"Licenciatura Universitaria en Astronomía" and "Licenciatura en
    Astronomía" are one career."""
    return re.sub(r"\buniversitari[ao]s?\b", "", clave_de_carrera(nombre)).strip()


def leer(guia: Guia) -> list[CarreraDeLaGuia]:
    """Every entry of the guide: a career it lists at several campuses
    comes once per campus."""
    from rumbo_scraper.spiders.visitante import Visitante

    import inspect
    import time

    carreras: list[CarreraDeLaGuia] = []
    with Visitante(timeout=30) as visitante:
        leidas: dict[str, str] = {}

        def traer(url: str) -> str:
            # A reader that needs a career's own page (the unit or the name the
            # list does not give) asks for it here, once each, unhurried.
            if url not in leidas:
                leidas[url] = visitante.get(url)
                time.sleep(0.5)
            return leidas[url]

        for pagina, lector in guia.paginas:
            if len(inspect.signature(lector).parameters) >= 3:
                carreras += lector(visitante.get(pagina), pagina, traer)
            else:
                carreras += lector(visitante.get(pagina), pagina)
    return carreras


def unicas(entradas: list[CarreraDeLaGuia]) -> list[CarreraDeLaGuia]:
    """One entry per career: the one that names the unit teaching it."""
    por_clave: dict[str, CarreraDeLaGuia] = {}
    for entrada in entradas:
        actual = por_clave.get(clave(entrada.nombre))
        if actual is None or (not actual.unidad and entrada.unidad):
            por_clave[clave(entrada.nombre)] = entrada
    return list(por_clave.values())


def sedes_de(entradas: list[CarreraDeLaGuia]) -> dict[str, dict[str, str]]:
    """The campuses the guide lists each career at, with the page of the
    career at that campus."""
    sedes: dict[str, dict[str, str]] = {}
    for entrada in entradas:
        if entrada.sede:
            sedes.setdefault(clave(entrada.nombre), {}).setdefault(entrada.sede, entrada.url)
    return sedes


def escribir_artefacto(guia: Guia, carreras: list[CarreraDeLaGuia]) -> None:
    guia.artefacto.write_text(json.dumps({
        "universidad": guia.nombre_oficial,
        "fuente_principal": guia.paginas[0][0],
        "metodo": "Guía oficial de carreras de la universidad; sin IA",
        "datos": {
            "universidades": [{"nombre_oficial": guia.nombre_oficial}],
            "ofertas": [{"carrera_nombre": c.nombre, "url_oficial": c.url,
                         "facultad_nombre": c.unidad} for c in carreras],
        },
    }, ensure_ascii=False, indent=1) + "\n")


def plan_de_cambios(carreras: list[CarreraDeLaGuia],
                    guardadas: list[dict[str, Any]]) -> dict[str, Any]:
    """Which stored careers each guide career is, which are new and which
    are retired. Pure, so it can be read before anything is written."""
    por_clave = {clave(c["nombre_carrera"]): c for c in guardadas}
    iguales, nuevas = [], []
    for carrera in carreras:
        guardada = por_clave.pop(clave(carrera.nombre), None)
        (iguales.append((carrera, guardada)) if guardada else nuevas.append(carrera))
    return {"iguales": iguales, "nuevas": nuevas, "retiradas": list(por_clave.values())}


def universidad(client: Any, guia: Guia, crear: bool) -> str | None:
    """The university's id, created with its campus when ``crear``."""
    filas = client.table("universidades").select("id").eq(
        "nombre_oficial", guia.nombre_oficial).execute().data
    if filas or not crear:
        return filas[0]["id"] if filas else None
    universidad_id = client.table("universidades").insert({
        "nombre_oficial": guia.nombre_oficial, "nombre_corto": guia.nombre_corto,
        "tipo_gestion": guia.tipo_gestion, "sitio_web": guia.sitio_web,
    }).execute().data[0]["id"]
    client.table("sedes").insert({
        "universidad_id": universidad_id, "nombre_sede": guia.sede,
        "calle": guia.calle or None, "tipo_sede": "Campus",
    }).execute()
    return universidad_id


def aplicar(client: Any, carreras: list[CarreraDeLaGuia], cambios: dict[str, Any],
            universidad_id: str, sedes: dict[str, dict[str, str]] | None = None) -> dict[str, int]:
    from rumbo_scraper.database.load_utdt import _upsert_one
    from rumbo_scraper.database.supabase import select_all

    unidades: dict[str, str | None] = {"": None}
    for carrera in carreras:
        if carrera.unidad not in unidades:
            unidades[carrera.unidad] = _upsert_one(client, "facultades", {
                "universidad_id": universidad_id, "nombre_facultad": carrera.unidad,
                "tipo_unidad": carrera.tipo_unidad,
            }, "universidad_id,nombre_facultad,tipo_unidad")["id"]

    for carrera, guardada in cambios["iguales"]:
        client.table("carreras").update({
            "nombre_carrera": carrera.nombre, "denominacion_canonica": carrera.nombre,
            "nivel": carrera.nivel, "facultad_id": unidades[carrera.unidad],
            # The duration the guide states, when it states one.
            **({"duracion_anios": carrera.duracion} if carrera.duracion else {}),
        }).eq("id", guardada["id"]).execute()
    for carrera in cambios["nuevas"]:
        client.table("carreras").insert({
            "universidad_id": universidad_id, "facultad_id": unidades[carrera.unidad],
            "nombre_carrera": carrera.nombre, "denominacion_canonica": carrera.nombre,
            "nivel": carrera.nivel, "duracion_anios": carrera.duracion,
        }).execute()
    retiradas = [c["id"] for c in cambios["retiradas"]]
    for inicio in range(0, len(retiradas), 50):
        tanda = retiradas[inicio:inicio + 50]
        client.table("materias").delete().in_("carrera_id", tanda).execute()
        client.table("carreras").delete().in_("id", tanda).execute()

    en_uso = {c["facultad_id"] for c in select_all(
        client.table("carreras").select("facultad_id").eq("universidad_id", universidad_id))}
    en_uso |= {p["facultad_id"] for p in select_all(
        client.table("posgrados").select("facultad_id").eq("universidad_id", universidad_id))}
    sueltas = [f["id"] for f in select_all(
        client.table("facultades").select("id,nombre_facultad").eq("universidad_id", universidad_id))
        if f["id"] not in en_uso and f["nombre_facultad"] not in unidades]
    for sin_uso in sueltas:
        client.table("facultades").delete().eq("id", sin_uso).execute()
    ofertas = _ofertas_por_sede(client, universidad_id, sedes or {})
    return {"unidades": len(unidades) - 1, "actualizadas": len(cambios["iguales"]),
            "nuevas": len(cambios["nuevas"]), "retiradas": len(retiradas),
            "unidades_retiradas": len(sueltas), "ofertas": ofertas}


def _ofertas_por_sede(client: Any, universidad_id: str,
                      sedes: dict[str, dict[str, str]]) -> int:
    """One offer per campus the guide lists a career at, replacing the
    career's offers: the guide is the list of where it is taught."""
    from rumbo_scraper.database.supabase import select_all

    if not sedes:
        return 0
    guardadas = {s["nombre_sede"]: s["id"] for s in select_all(
        client.table("sedes").select("id,nombre_sede").eq("universidad_id", universidad_id))}
    carreras = {clave(c["nombre_carrera"]): c["id"] for c in select_all(
        client.table("carreras").select("id,nombre_carrera").eq("universidad_id", universidad_id))}
    filas = []
    for clave_carrera, por_sede in sedes.items():
        carrera_id = carreras.get(clave_carrera)
        if not carrera_id:
            continue
        client.table("ofertas_academicas").delete().eq("carrera_id", carrera_id).execute()
        for sede, url in por_sede.items():
            if sede not in guardadas:
                guardadas[sede] = client.table("sedes").insert({
                    "universidad_id": universidad_id, "nombre_sede": sede,
                    "tipo_sede": "Otro"}).execute().data[0]["id"]
            filas.append({"carrera_id": carrera_id, "sede_id": guardadas[sede],
                          "url_oficial": url, "activa": True})
    for inicio in range(0, len(filas), 200):
        client.table("ofertas_academicas").insert(filas[inicio:inicio + 200]).execute()
    return len(filas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar carreras desde la guía oficial")
    parser.add_argument("universidades", nargs="+", choices=sorted(GUIAS))
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all

    client = get_supabase_client()
    for sigla in args.universidades:
        guia = GUIAS[sigla]
        entradas = leer(guia)
        carreras = unicas(entradas)
        if len(carreras) < guia.minimo:
            print(f"{sigla}: la guía trajo {len(carreras)} carreras; no se aplica nada.")
            continue
        escribir_artefacto(guia, carreras)
        universidad_id = universidad(client, guia, crear=args.apply)
        guardadas = [c for c in select_all(client.table("carreras").select(
            "id,nombre_carrera,nivel").eq("universidad_id", universidad_id))
            if c["nivel"] in guia.niveles] if universidad_id else []
        cambios = plan_de_cambios(carreras, guardadas)
        for carrera, guardada in cambios["iguales"]:
            print(f"  = {guardada['nombre_carrera']}  →  {carrera.nombre}")
        for carrera in cambios["nuevas"]:
            print(f"  + {carrera.nombre} ({carrera.unidad})")
        for guardada in cambios["retiradas"]:
            print(f"  - {guardada['nombre_carrera']}")
        print(f"{sigla}: guía {len(carreras)} · iguales {len(cambios['iguales'])} · nuevas "
              f"{len(cambios['nuevas'])} · retiradas {len(cambios['retiradas'])} · "
              f"artefacto {guia.artefacto}")
        if args.apply and universidad_id:
            print(sigla, aplicar(client, carreras, cambios, universidad_id, sedes_de(entradas)))


if __name__ == "__main__":
    main()
