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
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urljoin
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
    # What kind of institution it is, when it is not a university:
    # "instituto_terciario" (a police cadet school's "Técnico Superior").
    tipo_institucion: str | None = None

    @property
    def artefacto(self) -> Path:
        # "ISS Neuquén" -> data/iss_neuquen_guia_completo.json
        corto = unicodedata.normalize("NFKD", self.nombre_corto.lower()).encode("ascii", "ignore").decode()
        return Path(f"data/{re.sub(r'[^a-z0-9]+', '_', corto).strip('_')}_guia_completo.json")


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
    "UNICEN": Guia("Universidad Nacional del Centro de la Provincia de Buenos Aires", "UNICEN", "Estatal",
                   "https://www.unicen.edu.ar",
                   tuple((gn.UNICEN.format(p), gn.leer_unicen) for p in range(4)), "Tandil", "", 30),
    "UNS": Guia("Universidad Nacional del Sur", "UNS", "Estatal", "https://www.uns.edu.ar",
                ((gn.UNS, gn.leer_uns),), "Bahía Blanca", "", 50),
    "UCSE": Guia("Universidad Católica de Santiago del Estero", "UCSE", "Privada", "https://www.ucse.edu.ar",
                 ((gn.UCSE, gn.leer_ucse),), _SIN_SEDE, "", 30),
    "UNSE": Guia("Universidad Nacional de Santiago del Estero", "UNSE", "Estatal", "https://www.unse.edu.ar",
                 ((gn.UNSE_GRADO, gn.leer_unse), (gn.UNSE_PREGRADO, gn.leer_unse)), _SIN_SEDE, "", 30),
    "UNRN": Guia("Universidad Nacional de Río Negro", "UNRN", "Estatal", "https://www.unrn.edu.ar",
                 ((gn.UNRN.format(1), gn.leer_unrn), (gn.UNRN.format(5), gn.leer_unrn)),
                 "Sede Atlántica", "", 30),
    "UNER": Guia("Universidad Nacional de Entre Ríos", "UNER", "Estatal", "https://www.uner.edu.ar",
                 tuple((gn.UNER.format(p), gn.leer_uner) for p in range(1, 6)), _SIN_SEDE, "", 25),
    "UNSTA": Guia("Universidad del Norte Santo Tomás de Aquino", "UNSTA", "Privada", "https://www.unsta.edu.ar",
                  ((gn.UNSTA, gn.leer_unsta),), "Sede Central", "", 20),
    "UPSO": Guia("Universidad Provincial del Sudoeste", "UPSO", "Estatal", "https://www.upso.edu.ar",
                 ((gn.UPSO, gn.leer_upso),), _SIN_SEDE, "", 20),
    "UGR": Guia("Universidad del Gran Rosario", "UGR", "Privada", "https://ugr.edu.ar",
                ((gn.UGR_GRADO, gn.leer_ugr), (gn.UGR_PREGRADO, gn.leer_ugr)), _SIN_SEDE, "", 15),
    "UCP": Guia("Universidad de la Cuenca del Plata", "UCP", "Privada", "https://www.ucp.edu.ar",
                tuple((u, gn.leer_ucp) for u in gn.UCP), _SIN_SEDE, "", 15),
    "UMaza": Guia("Universidad Juan Agustín Maza", "UMaza", "Privada", "https://www.umaza.edu.ar",
                  ((gn.UMAZA, gn.leer_umaza),), "Sede Gran Mendoza", "", 20),
    "UdeMM": Guia("Universidad de la Marina Mercante", "UdeMM", "Privada", "https://www.udemm.edu.ar",
                  tuple((u, gn.leer_udemm) for u in gn.UDEMM), _SIN_SEDE, "", 15),
    "UCSF": Guia("Universidad Católica de Santa Fe", "UCSF", "Privada", "https://www.ucsf.edu.ar",
                 ((gn.UCSF, gn.leer_ucsf),), _SIN_SEDE, "", 15),
    "IUPA": Guia("Instituto Universitario Patagónico de las Artes", "IUPA", "Estatal", "https://iupa.edu.ar",
                 ((gn.IUPA, gn.leer_iupa),), _SIN_SEDE, "", 15),
    "UAP": Guia("Universidad Adventista del Plata", "UAP", "Privada", "https://uap.edu.ar",
                ((gn.UAP, gn.leer_uap),), _SIN_SEDE, "", 12),
    "Atlántida": Guia("Universidad Atlántida Argentina", "Atlántida", "Privada", "https://www.atlantida.edu.ar",
                      ((gn.ATLANTIDA, gn.leer_atlantida),), "Mar de Ajó", "", 15),
    "UNPSJB": Guia("Universidad Nacional de la Patagonia San Juan Bosco", "UNPSJB", "Estatal",
                   "https://www.unp.edu.ar", ((gn.UNP, gn.leer_unp),), "Comodoro Rivadavia", "", 40),
    "UNRaf": Guia("Universidad Nacional de Rafaela", "UNRaf", "Estatal", "https://unraf.edu.ar",
                  tuple((u, gn.leer_unraf) for u in gn.UNRAF), _SIN_SEDE, "", 10),
    "IUPFA": Guia("Instituto Universitario de la Policía Federal Argentina", "IUPFA", "Estatal",
                  "https://universidad-policial.edu.ar", ((gn.IUPFA, gn.leer_iupfa),), _SIN_SEDE, "", 8),
    "IUDPT": Guia("Instituto Universitario para el Desarrollo Productivo y Tecnológico Empresarial de la Argentina",
                  "IUDPT", "Privada", "https://iudpt.edu.ar", ((gn.IUDPT, gn.leer_iudpt),), _SIN_SEDE, "", 5),
    "IUCE": Guia("Instituto Universitario de Ciencias Empresariales", "IUCE", "Privada", "https://i-uce.edu.ar",
                 ((gn.IUCE, gn.leer_iuce),), _SIN_SEDE, "", 4),
    "IUYMCA": Guia("Instituto Universitario YMCA", "IUYMCA", "Privada", "https://iuymca.edu.ar",
                   ((gn.IUYMCA, gn.leer_iuymca),), _SIN_SEDE, "", 2),
    "USBA": Guia("Universidad del Sur de Buenos Aires", "USBA", "Privada", "https://usba.edu.ar",
                 ((gn.USBA, gn.leer_usba),), _SIN_SEDE, "", 2),
    "UDE": Guia("Universidad del Este", "UDE", "Privada", "https://www.ude.edu.ar",
                ((gn.UDE, gn.leer_ude),), _SIN_SEDE, "", 10),
    "UCASAL": Guia("Universidad Católica de Salta", "UCASAL", "Privada", "https://www.ucasal.edu.ar",
                   ((gn.UCASAL_GRADO, gn.leer_ucasal), (gn.UCASAL_PREGRADO, gn.leer_ucasal)), _SIN_SEDE, "", 40),
    "UNaM": Guia("Universidad Nacional de Misiones", "UNaM", "Estatal", "https://www.unam.edu.ar",
                 ((gn.UNAM, gn.leer_unam),), "Posadas", "", 40),
    "UNCA": Guia("Universidad Nacional de Catamarca", "UNCA", "Estatal", "https://www.unca.edu.ar",
                 ((gn.UNCA, gn.leer_unca),), _SIN_SEDE, "", 40),
    "UCALP": Guia("Universidad Católica de La Plata", "UCALP", "Privada", "https://www.ucalp.edu.ar",
                  ((gn.UCALP, gn.leer_ucalp),), _SIN_SEDE, "", 40),
    "UNNE": Guia("Universidad Nacional del Nordeste", "UNNE", "Estatal", "https://www.unne.edu.ar",
                 ((gn.UNNE, gn.leer_unne),), _SIN_SEDE, "", 40),
    "UNDEF": Guia("Universidad de la Defensa Nacional", "UNDEF", "Estatal", "https://undef.edu.ar",
                  tuple((u, gn.leer_undef) for u in gn.UNDEF), _SIN_SEDE, "", 20),
    "UNJu": Guia("Universidad Nacional de Jujuy", "UNJu", "Estatal", "https://unju.edu.ar",
                 tuple((u, gn.leer_unju) for u in gn.UNJU), "San Salvador de Jujuy", "", 30),
    "UNLPam": Guia("Universidad Nacional de La Pampa", "UNLPam", "Estatal", "https://www.unlpam.edu.ar",
                   ((gn.UNLPAM, gn.leer_unlpam),), _SIN_SEDE, "", 30),
    "UNSa": Guia("Universidad Nacional de Salta", "UNSa", "Estatal", "https://www.unsa.edu.ar",
                 ((gn.UNSA, gn.leer_unsa),), "Salta", "", 30),
    "USPT": Guia("Universidad San Pablo - Tucumán", "USPT", "Privada", "https://www.uspt.edu.ar",
                 ((gn.USPT, gn.leer_uspt),), "Sede Centro", "", 20),
    "UCU": Guia("Universidad de Concepción del Uruguay", "UCU", "Privada", "https://ucu.edu.ar",
                ((gn.UCU, gn.leer_ucu),), "Concepción del Uruguay", "", 20),
    "UNVM": Guia("Universidad Nacional de Villa María", "UNVM", "Estatal", "https://www.unvm.edu.ar",
                 ((gn.UNVM, gn.leer_unvm),), "Villa María", "", 25),
    "UCongreso": Guia("Universidad de Congreso", "UCongreso", "Privada", "https://www.ucongreso.edu.ar",
                      ((gn.UCONGRESO, gn.leer_ucongreso),), _SIN_SEDE, "", 20),
    "UNPA": Guia("Universidad Nacional de la Patagonia Austral", "UNPA", "Estatal", "https://www.unpa.edu.ar",
                 ((gn.UNPA, gn.leer_unpa),), _SIN_SEDE, "", 20),
    "UCCuyo": Guia("Universidad Católica de Cuyo", "UCCuyo", "Privada", "https://uccuyo.edu.ar",
                   ((gn.UCCUYO, gn.leer_uccuyo),), "San Juan", "", 40),
    "UNLu": Guia("Universidad Nacional de Luján", "UNLu", "Estatal", "https://www.unlu.edu.ar",
                 ((gn.UNLU_GRADO, gn.leer_unlu), (gn.UNLU_PREGRADO, gn.leer_unlu)), _SIN_SEDE, "", 20),
    "UEAN": Guia("Universidad Escuela Argentina de Negocios", "UEAN", "Privada", "https://www.uean.edu.ar",
                 ((gn.UEAN_GRADO, gn.leer_uean), (gn.UEAN_PREGRADO, gn.leer_uean)), _SIN_SEDE, "", 12),
    "UNIPE": Guia("Universidad Pedagógica Nacional", "UNIPE", "Estatal", "https://unipe.edu.ar",
                  ((gn.UNIPE, gn.leer_unipe),), "Sede Pilar", "", 10),
    "UNNOBA": Guia("Universidad Nacional del Noroeste de la Provincia de Buenos Aires", "UNNOBA", "Estatal",
                   "https://www.unnoba.edu.ar", ((gn.UNNOBA, gn.leer_unnoba),), _SIN_SEDE, "", 12),
    "UNDelta": Guia("Universidad Nacional del Delta", "UNDelta", "Estatal", "https://undelta.edu.ar",
                    ((gn.UNDELTA, gn.leer_undelta),), _SIN_SEDE, "", 10),
    "UNSAdA": Guia("Universidad Nacional de San Antonio de Areco", "UNSAdA", "Estatal", "https://www.unsada.edu.ar",
                   ((gn.UNSADA, gn.leer_unsada),), _SIN_SEDE, "", 10),
    "UNSO": Guia("Universidad Nacional Raúl Scalabrini Ortiz", "UNSO", "Estatal", "https://www.unso.edu.ar",
                 ((gn.UNSO, gn.leer_unso),), _SIN_SEDE, "", 8),
    "UNViMe": Guia("Universidad Nacional de Villa Mercedes", "UNViMe", "Estatal", "https://www.unvime.edu.ar",
                   ((gn.UNVIME, gn.leer_unvime),), _SIN_SEDE, "", 10),
    "UNLC": Guia("Universidad Nacional de los Comechingones", "UNLC", "Estatal", "https://unlc.edu.ar",
                 ((gn.UNLC, gn.leer_unlc),), _SIN_SEDE, "", 8),
})


# Grupo D.
GUIAS.update({
    "UNSJ": Guia("Universidad Nacional de San Juan", "UNSJ", "Estatal", "https://www.unsj.edu.ar",
                 tuple((pagina, gn.leer_unsj) for pagina in gn.UNSJ), _SIN_SEDE, "", 45),
    "USI": Guia("Universidad de San Isidro \"Dr. Plácido Marín\"", "USI", "Privada", "https://usi.edu.ar",
                ((gn.USI, gn.leer_usi),), _SIN_SEDE, "", 8),
    "UGD": Guia("Universidad Gastón Dachary", "UGD", "Privada", "https://ugd.edu.ar",
                ((gn.UGD, gn.leer_ugd),), _SIN_SEDE, "", 10, ("Grado",)),
    "UMET": Guia("Universidad Metropolitana para la Educación y el Trabajo", "UMET", "Privada",
                 "https://umet.edu.ar", ((gn.UMET, gn.leer_umet),), _SIN_SEDE, "", 8),
    "UNPilar": Guia("Universidad Nacional de Pilar", "UNPilar", "Estatal", "https://unpilar.edu.ar",
                    ((gn.UNPILAR, gn.leer_unpilar),), _SIN_SEDE, "", 8),
    "UDC": Guia("Universidad del Chubut", "UDC", "Estatal", "https://udc.edu.ar",
                ((gn.UDC, gn.leer_udc),), _SIN_SEDE, "", 10),
    "IUCSB": Guia("Instituto Universitario de Ciencias de la Salud", "IUCSB", "Privada",
                         "https://barcelo.edu.ar", ((gn.BARCELO_GRADO, gn.leer_barcelo),
                                                   (gn.BARCELO_PREGRADO, gn.leer_barcelo)), _SIN_SEDE, "", 4),
    "UPE": Guia("Universidad Provincial de Ezeiza", "UPE", "Estatal", "https://web.upe.edu.ar",
                ((gn.UPE, gn.leer_upe),), _SIN_SEDE, "", 8),
    "IURP": Guia("Instituto Universitario River Plate", "IURP", "Privada", "https://iuriverplate.edu.ar",
                 ((gn.RIVER, gn.leer_river),), _SIN_SEDE, "", 5),
    "UIT": Guia("Universidad de Innovación y Tecnología", "UIT", "Privada", "https://www.uit.edu.ar",
                ((gn.UIT, gn.leer_uit),), _SIN_SEDE, "", 3),
    "IUNIR": Guia("Instituto Universitario Italiano de Rosario", "IUNIR", "Privada", "https://www.iunir.edu.ar",
                  ((gn.IUNIR, gn.leer_iunir),), "Rosario", "", 5),
    "UNISAL": Guia("Universidad Salesiana", "UNISAL", "Privada", "https://www.unisal.edu.ar",
                   ((gn.UNISAL, gn.leer_unisal),), _SIN_SEDE, "", 3),
    "UNAU": Guia("Universidad Nacional del Alto Uruguay", "UNAU", "Estatal", "https://unau.edu.ar",
                 ((gn.UNAU, gn.leer_unau),), _SIN_SEDE, "", 4),
    "IUAS": Guia("Instituto Universitario del Agua y el Saneamiento", "IUAS", "Privada", "https://www.iuas.edu.ar",
                 ((gn.IUAS, gn.leer_iuas),), _SIN_SEDE, "", 4),
    "UNISUD": Guia("Universidad de la Integración Sudamericana", "UNISUD", "Privada", "https://unisud.edu.ar",
                   ((gn.UNISUD, gn.leer_unisud),), _SIN_SEDE, "", 3),
    "UPatagonia": Guia("Universidad Patagonia Argentina", "UPatagonia", "Privada", "https://upatagonia.edu.ar",
                       ((gn.UPATAGONIA, gn.leer_upatagonia),), _SIN_SEDE, "", 5),
})


GUIAS.update({
    "UDA": Guia("Universidad del Aconcagua", "UDA", "Privada", "https://www.uda.edu.ar",
                ((gn.UDA, gn.leer_uda),), _SIN_SEDE, "", 20),
    "IUSE": Guia("Instituto Universitario de Seguridad", "IUSE", "Privada", "https://iuse.edu.ar",
                 ((gn.IUSE, gn.leer_iuse),), _SIN_SEDE, "", 6),
    "UNAB": Guia("Universidad Nacional Guillermo Brown", "UNAB", "Estatal", "https://www.unab.edu.ar",
                 tuple((pagina, gn.leer_unab) for pagina in gn.UNAB), _SIN_SEDE, "", 10),
    "UNICABA": Guia("Universidad de la Ciudad de Buenos Aires", "UNICABA", "Estatal", "https://www.udelaciudad.edu.ar",
                    ((gn.UNICABA, gn.leer_unicaba),), _SIN_SEDE, "", 2),
    "UHIBA": Guia("Universidad Hospital Italiano de Buenos Aires", "UHIBA", "Privada",
                  "https://www.hospitalitaliano.edu.ar", ((gn.HIBA, gn.leer_hiba),), _SIN_SEDE, "", 6),
})


GUIAS.update({
    "IUIA": Guia("Instituto Universitario Isaac Abarbanel", "IUIA", "Privada", "https://abarbanel.edu.ar",
                 ((gn.ABARBANEL, gn.leer_abarbanel),), _SIN_SEDE, "", 1),
    "CEMIC": Guia("Instituto Universitario CEMIC", "CEMIC", "Privada", "https://cemic.edu.ar",
                  ((gn.CEMIC, gn.leer_cemic),), _SIN_SEDE, "", 4),
})


GUIAS.update({
    "UNLZ": Guia("Universidad Nacional de Lomas de Zamora", "UNLZ", "Estatal", "https://www.unlz.edu.ar",
                 ((gn.UNLZ, gn.leer_unlz),), "Lomas de Zamora", "", 30),
    # Its spider read faculty menus, courses among them ("Medicina Interna"):
    # the university's own search replaces it (--reemplazar).
    "UNSL": Guia("Universidad Nacional de San Luis", "UNSL", "Estatal", "https://www.unsl.edu.ar",
                 ((gn.UNSL, gn.leer_unsl),), "San Luis", "Ejército de los Andes 950", 60),
    "IUCOOP": Guia("Instituto Universitario de la Cooperación", "IUCOOP", "Privada", "https://www.iucoop.edu.ar",
                   ((gn.IUCOOP, gn.leer_iucoop),), "Ciudad Autónoma de Buenos Aires", "", 2),
    "ESEADE": Guia("Instituto Universitario ESEADE", "ESEADE", "Privada", "https://www.eseade.edu.ar",
                   ((gn.ESEADE, gn.leer_eseade),), "Ciudad Autónoma de Buenos Aires", "", 5),
    "ISALUD": Guia("Universidad ISALUD", "ISALUD", "Privada", "https://www.isalud.edu.ar",
                   ((gn.ISALUD, gn.leer_isalud),), "Ciudad Autónoma de Buenos Aires", "Venezuela 925", 8),
    "UNaF": Guia("Universidad Nacional de Formosa", "UNaF", "Estatal", "https://www.unf.edu.ar",
                 ((gn.UNAF_FRN, gn.leer_unaf_frn),), "Formosa", "Av. Gutnisky 3200", 4),
    "UNLP": Guia("Universidad Nacional de La Plata", "UNLP", "Estatal", "https://unlp.edu.ar",
                 ((gn.UNLP, gn.leer_unlp),), "La Plata", "", 110),
})


GUIAS.update({
    "UCINE": Guia("Universidad del Cine", "UCINE", "Privada", "https://www.ucine.edu.ar",
                  ((gn.UCINE, gn.leer_ucine),), _SIN_SEDE, "", 5, ("Pregrado",)),
})


GUIAS.update({
    "UNCAUS": Guia("Universidad Nacional del Chaco Austral", "UNCAUS", "Estatal", "https://uncaus.edu.ar",
                   ((gn.UNCAUS, gn.leer_uncaus),), "Presidencia Roque Sáenz Peña", "", 15),
})


GUIAS.update({
    "IUGNA": Guia("Instituto Universitario de Gendarmería Nacional", "IUGNA", "Estatal", "https://www.iugna.edu.ar",
                  ((gn.IUGNA, gn.leer_iugna),), _SIN_SEDE, "", 8),
    "IUPS": Guia("Instituto Universitario Provincial de Seguridad", "IUPS", "Estatal", "https://iups.jujuy.gob.ar",
                 ((gn.IUPS, gn.leer_iups),), "San Salvador de Jujuy", "", 4),
})


# The provinces' police institutes: non-university tertiary titles.
_TERCIARIO = "instituto_terciario"
GUIAS.update({
    "ECP Santa Cruz": Guia("Escuela de Cadetes de la Policía de Santa Cruz", "ECP Santa Cruz", "Estatal",
                           "https://policiadesantacruz.gob.ar",
                           ((gn.POLICIA_SANTA_CRUZ, gn.leer_policia_santa_cruz),), _SIN_SEDE, "", 4,
                           ("Pregrado",), _TERCIARIO),
    "ISS Neuquén": Guia("Instituto Superior en Seguridad", "ISS Neuquén", "Estatal", "https://www.iss.edu.ar",
                        ((gn.ISS_NEUQUEN, gn.leer_menu_terciario),), "Neuquén", "", 3, ("Pregrado",), _TERCIARIO),
    "IESP Salta": Guia("Instituto Superior de Educación Policial N° 6.045", "IESP Salta", "Estatal",
                       "https://ies6045-sal.infd.edu.ar",
                       ((gn.IESP_SALTA, gn.leer_menu_terciario),), "Salta", "", 1, ("Pregrado",), _TERCIARIO),
    "ISeP Santa Fe": Guia("Instituto de Seguridad Pública de Santa Fe", "ISeP Santa Fe", "Estatal",
                          "https://isepsantafe.edu.ar",
                          ((gn.ISEP_SANTA_FE, gn.leer_titulo_terciario),), _SIN_SEDE, "", 1, ("Pregrado",), _TERCIARIO),
    "ISP La Pampa": Guia("Instituto Superior Policial de La Pampa", "ISP La Pampa", "Estatal",
                         "https://recursos.lapampa.edu.ar",
                         ((gn.POLICIAL_LA_PAMPA, gn.leer_titulo_terciario),), _SIN_SEDE, "", 1,
                         ("Pregrado",), _TERCIARIO),
    "ISSP Chaco": Guia("Instituto Superior de Seguridad Pública del Chaco", "ISSP Chaco", "Estatal",
                       "https://isspchaco.edu.ar",
                       ((gn.ISSP_CHACO, gn.leer_titulo_terciario),), _SIN_SEDE, "", 1, ("Pregrado",), _TERCIARIO),
})


# The universities whose own sites turn automated readers away (Cloudflare,
# 403): their careers come from the Ministry's national guide (DNGU), the
# official list of the degrees each one gives. Campus and street are the ones
# the guide gives for most of its rows.
def _dngu(nombre: str) -> tuple[tuple[str, Callable[[str, str], list[CarreraDeLaGuia]]], ...]:
    return ((gn.DNGU, gn.leer_dngu(nombre)),)


GUIAS.update({
    "UNSAM": Guia("Universidad Nacional de San Martín", "UNSAM", "Estatal", "https://www.unsam.edu.ar",
                  _dngu("Universidad Nacional de San Martín"), "San Martín", "Martín de Irigoyen 3100", 30),
    "UNLaR": Guia("Universidad Nacional de La Rioja", "UNLaR", "Estatal", "https://www.unlar.edu.ar",
                  _dngu("Universidad Nacional de La Rioja"), "La Rioja", "Luis M. de la Fuente S/N", 30),
    "UNdeC": Guia("Universidad Nacional de Chilecito", "UNdeC", "Estatal", "https://www.undec.edu.ar",
                  _dngu("Universidad Nacional de Chilecito"), "Chilecito", "Ruta Los Peregrinos s/n, Los Sarmientos", 10),
    "UPLaB": Guia("Universidad Provincial de Laguna Blanca", "UPLaB", "Estatal", "https://www.uplab.edu.ar",
                  _dngu("Universidad Provincial de Laguna Blanca"), "Laguna Blanca", "Ruta Nacional 86 km 1352", 3),
    "UFASTA": Guia("Universidad de la Fraternidad de Agrupaciones Santo Tomás de Aquino", "UFASTA", "Privada",
                   "https://www.ufasta.edu.ar",
                   _dngu("Universidad de la Fraternidad de Agrupaciones Santo Tomás de Aquino"),
                   "Mar del Plata", "Gascón 3145", 20),
    "UCEL": Guia("Universidad del Centro Educativo Latinoamericano", "UCEL", "Privada", "https://www.ucel.edu.ar",
                 _dngu("Universidad del Centro Educativo Latinoamericano"), "Rosario", "Av. Carlos Pellegrini 1332", 10),
    "EUT": Guia("Escuela Universitaria de Teología", "EUT", "Privada", "https://www.cedier.org.ar",
                _dngu("Escuela Universitaria de Teología"), "Mar del Plata", "Pasaje Catedral 1750", 1,
                ("Grado", "Pregrado"), "instituto_universitario"),
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
                # A script or a data file is read as it comes: the visitor
                # takes pages only.
                if re.search(r"\.(?:js|json)(?:\?|$)|/rest/", url):
                    try:
                        leidas[url] = visitante.client.get(url).text
                    except Exception:
                        leidas[url] = ""
                else:
                    leidas[url] = visitante.get(url)
                time.sleep(0.5)
            return leidas[url]

        for pagina, lector in guia.paginas:
            # A university's public service answers JSON, which the visitor
            # (made for pages) does not take: it is read as it comes.
            if re.search(r"/apis?[/.]|/api\.|/rest/", pagina):
                try:
                    html = visitante.client.get(pagina).text
                except Exception:
                    html = ""
            else:
                html = visitante.get(pagina)
            if len(inspect.signature(lector).parameters) >= 3:
                leidas_de_la_pagina = lector(html, pagina, traer)
            else:
                leidas_de_la_pagina = lector(html, pagina)
            # A link the page gives relative ("/tecnicatura-en-meteorologia/")
            # is the page's: the catalogue shows it as a link.
            carreras += [replace(c, url=urljoin(pagina, c.url)) for c in leidas_de_la_pagina]
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
    parser.add_argument("--reemplazar", action="store_true",
                        help="Aplicar la guía a una universidad cuyas carreras vinieron de otra fuente")
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
        universidad_id = universidad(client, guia, crear=False)
        guardadas = [c for c in select_all(client.table("carreras").select(
            "id,nombre_carrera,nivel").eq("universidad_id", universidad_id))
            if c["nivel"] in guia.niveles] if universidad_id else []
        # A university whose careers came from another source (its own
        # spider, with units, plans and subjects) is not the guide's to
        # replace: the guide would retire what it does not list and the
        # units it does not name.
        if guardadas and not guia.artefacto.exists() and not args.reemplazar:
            print(f"{sigla}: ya tiene {len(guardadas)} carreras de otra fuente; no se aplica "
                  "(--reemplazar para hacerlo).")
            continue
        if args.apply:
            escribir_artefacto(guia, carreras)
            universidad_id = universidad(client, guia, crear=True)
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
